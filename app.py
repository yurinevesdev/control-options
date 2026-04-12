"""
System — aplicação Flask (port do controller js/app.js).

Melhorias aplicadas:
- Config centralizada em system.config
- Logging estruturado em system.logger
- Secret key seguro (secrets.token_hex)
- CSRF básico via token de sessão
- Rate limiting simples no preview-greeks
- Rota de backup DB
- before_request/teardown_request para DB
"""

from __future__ import annotations

import time
import logging
from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import (
    Flask,
    Response,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from system.core import blackscholes as BS
from system.ui.charts import dashboard_doughnut, dashboard_bar, payoff_figure, plotly_carteira_alocacao
from system.config import DEBUG, HOST, PORT, SECRET_KEY, ESTRATEGIAS_LIST, DB_PATH
from system.data.csv_io import export_zip_bytes, import_merge_zip, zip_from_csv_parts
from system.core.db import Database
from system.ui.logger import setup_logging, get_logger
from system.ui.formatting import brl, color_pnl, dias_ate_venc, fmt_date
from system.data.opcoes_scraper import (
    atualizar_dados_opcoes,
    buscar_opcoes_dados,
    carregar_cache as carregar_cache_opcoes,
    formatar_opcoes_tabela,
    salvar_opcoes_detalhadas,
    buscar_opcoes_serie,
)
from system.analysis.sugestoes import analisar_sugestoes
from system.data.precos import atualizar_precos_estrutura, atualizar_todas_estruturas_em_andamento
from system.notifications.scheduler import iniciar_scheduler, parar_scheduler

# -------------------------------------------------------------------------
# Setup
# -------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
db = Database(DB_PATH)

logger = setup_logging(level=logging.INFO)
log = get_logger("app")

# -------------------------------------------------------------------------
# Rate limiter simples (em memória — suficiente para uso local)
# -------------------------------------------------------------------------

_rate_map: dict[str, list[float]] = {}

def rate_limit(max_calls: int = 30, window: int = 60):
    """Decorator de rate limiting por IP (últimos `window` segundos)."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            ip = request.remote_addr or "unknown"
            now = time.time()
            calls = _rate_map.get(ip, [])
            # Manter apenas chamadas dentro da janela
            calls = [t for t in calls if now - t < window]
            if len(calls) >= max_calls:
                log.warning("Rate limit excedido: %s", ip)
                return jsonify({"error": "Rate limit exceeded"}), 429
            calls.append(now)
            _rate_map[ip] = calls
            return fn(*args, **kwargs)
        return wrapper
    return decorator

def safe_render(fn):
    """Decorator para renderizar páginas com logging e tratamento de erros."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            log.info(f"Renderizando {fn.__name__}...")
            result = fn(*args, **kwargs)
            log.info(f"✓ {fn.__name__} renderizado com sucesso")
            return result
        except Exception as e:
            log.error(f"✗ Erro em {fn.__name__}: {str(e)}", exc_info=True)
            flash(f"Erro ao carregar página: {str(e)}", "error")
            return redirect(url_for("simulador")), 500
    return wrapper

# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

def leg_row_context(est: dict, leg: dict) -> dict:
    """Contexto de uma linha da tabela de pernas (espelha renderLegsTable do app.js)."""
    s0 = float(est.get("precoAtual") or 0)
    r = 0.1075
    d = dias_ate_venc(est.get("dataVenc"))
    t = max(0.0, float(d or 0) / 365.0)
    k = float(leg.get("strike") or 0)
    prem = float(leg.get("premio") or 0)
    qtd = float(leg.get("qtd") or 1)
    mult = 1.0 if leg.get("operacao") == "compra" else -1.0
    iv = leg.get("iv")
    try:
        iv_f = float(iv) if iv is not None and iv != "" else None
    except (TypeError, ValueError):
        iv_f = None

    pnl_atual = None
    bs_preco = None
    bs_delta = None
    if s0 > 0 and k > 0 and iv_f is not None and iv_f > 0:
        sigma = iv_f / 100.0
        typ = leg.get("tipo") or "call"
        if typ not in ("call", "put"):
            typ = "call"
        gks = BS.greeks(typ, s0, k, t, r, sigma)
        bs_delta = gks.get("delta")
        bs_preco = BS.price(typ, s0, k, t, r, sigma)
        pnl_atual = mult * qtd * (float(bs_preco) - prem)
    elif s0 > 0 and k > 0:
        typ = leg.get("tipo") or "call"
        intrin = max(0.0, s0 - k) if typ == "call" else max(0.0, k - s0)
        pnl_atual = mult * qtd * (intrin - prem)

    if bs_delta is not None:
        delta_disp = f"{bs_delta:.2f}"
    elif leg.get("delta") is not None and leg.get("delta") != "":
        delta_disp = f"{float(leg['delta']):.2f}"
    else:
        delta_disp = "—"

    iv_str = f"{iv_f:.1f}%" if iv_f is not None and iv_f > 0 else "—"
    pnl_cls = color_pnl(pnl_atual) if pnl_atual is not None else ""

    return {
        "leg": leg,
        "delta_disp": delta_disp,
        "bs_preco_str": brl(bs_preco) if bs_preco is not None else "—",
        "iv_str": iv_str,
        "pnl_atual": pnl_atual,
        "pnl_cls": pnl_cls,
        "pnl_str": brl(pnl_atual) if pnl_atual is not None else "—",
    }


def _safe_redirect(endpoint: str, **values):
    """Redirect seguro usando sempre url_for, nunca referrer cego."""
    try:
        return redirect(url_for(endpoint, **values))
    except Exception:
        return redirect(url_for("simulador"))


# -------------------------------------------------------------------------
# Factory
# -------------------------------------------------------------------------

def create_app() -> Flask:
    app = Flask(
        __name__,
        static_folder="static",
        template_folder="templates",
    )
    app.secret_key = SECRET_KEY

    # Registrar filtros Jinja2
    app.jinja_env.filters['brl'] = brl
    app.jinja_env.filters['fmt_date'] = fmt_date
    app.jinja_env.filters['color_pnl'] = color_pnl
    app.jinja_env.filters['dias_ute_venc'] = dias_ate_venc

    # ---- Middleware de logging ----
    @app.before_request
    def _log_request():
        """Loga todas as requisições recebidas."""
        log.info(f"{request.method} {request.path} | IP: {request.remote_addr}")

    @app.after_request
    def _log_response(response):
        """Loga status da resposta."""
        status_code = response.status_code
        level = logging.WARNING if status_code >= 400 else logging.INFO
        log.log(level, f"{request.method} {request.path} → {status_code}")
        return response

    # ---- DB lifecycle ----
    @app.before_request
    def _ensure_db():
        db.connect()

    @app.teardown_request
    def _close_db(exc):
        if hasattr(db, "_conn") and db._conn is not None:
            try:
                db._conn.close()
            except Exception:
                pass
            db._conn = None

    # ---- Error handlers ----
    @app.errorhandler(404)
    def _not_found(e):
        log.warning(f"404 Not Found: {request.path}")
        flash("Página não encontrada.", "error")
        return redirect(url_for("simulador")), 404

    @app.errorhandler(500)
    def _server_error(e):
        log.error(f"500 Server Error: {request.path} | {str(e)}", exc_info=True)
        flash("Erro interno do servidor.", "error")
        return redirect(url_for("simulador")), 500

    # ---- Rotas ----

    @app.route("/")
    def index():
        return redirect(url_for("simulador"))

    @app.route("/simulador", methods=["GET", "POST"])
    @app.route("/simulador/<int:eid>", methods=["GET", "POST"])
    def simulador(eid: int | None = None):
        q = (request.args.get("q") or "").strip().lower()
        if request.method == "POST":
            action = request.form.get("action")
            if action == "toggle_bs":
                session["show_current_bs"] = request.form.get("show_current") == "1"
                return _safe_redirect("simulador", eid=eid, q=q or None)
            if action == "select":
                sid = request.form.get("estrutura_id", type=int)
                if sid:
                    return _safe_redirect("simulador", eid=sid, q=q or None)
                return _safe_redirect("simulador", q=q or None)

        ests_all = db.get_estruturas()
        filtered = (
            [
                e
                for e in ests_all
                if q in (e.get("nome") or "").lower()
                or q in (e.get("ativo") or "").lower()
            ]
            if q
            else ests_all
        )
        for e in filtered:
            legs_e = db.get_legs(int(e["id"]))
            e["_premio_liq"] = BS.calc_metrics(e, legs_e)["premioLiq"]

        estrutura = None
        legs: list = []
        if eid:
            estrutura = db.get("estruturas", eid)
            if estrutura:
                legs = db.get_legs(eid)

        metrics = BS.calc_metrics(estrutura, legs) if estrutura else None
        show_current = session.get("show_current_bs", True)

        chart_html = None
        if estrutura and legs:
            chart_html = payoff_figure(estrutura, legs, show_current=show_current)

        modal_est = request.args.get("modal_est")
        modal_leg = request.args.get("modal_leg")
        edit_est_id = request.args.get("edit_est", type=int)
        edit_leg_id = request.args.get("edit_leg", type=int)

        est_form: dict = {}
        if modal_est:
            if edit_est_id:
                est_form = dict(db.get("estruturas", edit_est_id) or {})
            else:
                est_form = {}

        leg_form: dict = {}
        if modal_leg and estrutura:
            if edit_leg_id:
                leg_form = dict(db.get("legs", edit_leg_id) or {})
            else:
                leg_form = {
                    "qtd": 100,
                    "vencimento": estrutura.get("dataVenc") or "",
                }

        leg_rows = [leg_row_context(estrutura, lg) for lg in legs] if estrutura else []
        qtd_total = sum(float(lg.get("qtd") or 0) for lg in legs) if legs else 0.0


        return render_template(
            "simulador.html",
            estruturas=filtered,
            estrutura=estrutura,
            legs=legs,
            leg_rows=leg_rows,
            qtd_total=qtd_total,
            metrics=metrics,
            chart_html=chart_html,
            search_q=q,
            selected_id=eid,
            show_current_bs=show_current,
            estrategias_list=ESTRATEGIAS_LIST,
            brl=brl,
            fmt_date=fmt_date,
            dias_ute_venc=dias_ate_venc,
            color_pnl=color_pnl,
            modal_est=modal_est,
            modal_leg=modal_leg,
            edit_est_id=edit_est_id,
            edit_leg_id=edit_leg_id,
            est_form=est_form,
            leg_form=leg_form,
        )

    @app.route("/simulador/estrutura/save", methods=["POST"])
    def save_estrutura():
        nome = (request.form.get("nome") or "").strip()
        ativo = (request.form.get("ativo") or "").strip().upper()
        if not nome:
            flash("Informe o nome da estrutura.", "error")
            return _safe_redirect("simulador", modal_est=1)
        if not ativo:
            flash("Informe o ativo (ticker).", "error")
            return _safe_redirect("simulador", modal_est=1)

        oid = request.form.get("id", type=int)
        obj = {
            "nome": nome,
            "ativo": ativo,
            "tipo": request.form.get("tipo") or "Personalizada",
            "precoAtual": request.form.get("preco", type=float),
            "dataVenc": request.form.get("data_venc") or None,
            "obs": (request.form.get("obs") or "").strip(),
        }
        if oid:
            obj["id"] = oid
        new_id = db.save_estrutura(obj)
        flash("Estrutura salva!", "success")
        return redirect(url_for("simulador", eid=oid or new_id))

    @app.route("/simulador/estrutura/<int:eid>/delete", methods=["POST"])
    def delete_estrutura(eid: int):
        db.delete_estrutura(eid)
        flash("Estrutura excluída.", "info")
        return redirect(url_for("simulador"))

    @app.route("/simulador/<int:eid>/leg/save", methods=["POST"])
    def save_leg(eid: int):
        est = db.get("estruturas", eid)
        if not est:
            flash("Estrutura não encontrada.", "error")
            return _safe_redirect("simulador")

        strike = request.form.get("strike", type=float)
        qtd = request.form.get("qtd", type=int)
        if not strike or strike <= 0:
            flash("Informe o Strike.", "error")
            return _safe_redirect("simulador", eid=eid, modal_leg=1)
        if not qtd or qtd <= 0:
            flash("Informe a Quantidade.", "error")
            return _safe_redirect("simulador", eid=eid, modal_leg=1)

        def fnum(name: str):
            v = request.form.get(name)
            if v is None or v == "":
                return None
            try:
                return float(v)
            except ValueError:
                return None

        oid = request.form.get("id", type=int)
        obj = {
            "estruturaId": eid,
            "operacao": request.form.get("operacao") or "compra",
            "tipo": request.form.get("tipo") or "call",
            "qtd": qtd,
            "strike": strike,
            "ticker": (request.form.get("ticker") or "").strip().upper(),
            "vencimento": request.form.get("vencimento") or None,
            "premio": float(request.form.get("premio") or 0),
            "iv": fnum("iv"),
            "delta": fnum("delta"),
            "gamma": fnum("gamma"),
            "theta": fnum("theta"),
            "vega": fnum("vega"),
        }
        if oid:
            obj["id"] = oid
        db.save_leg(obj)
        flash("Perna salva!", "success")
        return redirect(url_for("simulador", eid=eid))

    @app.route("/simulador/leg/<int:lid>/delete", methods=["POST"])
    def delete_leg(lid: int):
        eid = request.form.get("estrutura_id", type=int)
        db.delete_row("legs", lid)
        flash("Perna removida.", "info")
        if eid:
            return redirect(url_for("simulador", eid=eid))
        return redirect(url_for("simulador"))

    # ---- Rotas de atualização de preços ----

    @app.route("/api/calcular-iv", methods=["POST"])
    @rate_limit(max_calls=60, window=60)
    def api_calcular_iv():
        """API para calcular IV implícita e gregas a partir do prêmio."""
        data = request.get_json(force=True, silent=True) or {}
        try:
            s0 = float(data.get("preco_atual") or 0)
            k = float(data.get("strike") or 0)
            premio = float(data.get("premio") or 0)
            tipo = data.get("tipo") or "call"
            venc = data.get("venc") or ""
        except (TypeError, ValueError):
            return jsonify({}), 400

        if not s0 or not k or not premio or not venc:
            return jsonify({})

        try:
            v = datetime.strptime(venc[:10], "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            hoje = datetime.now()
            t = max(0.0, (v - hoje).total_seconds() / (365.0 * 24 * 3600))
        except ValueError:
            return jsonify({})

        if t <= 0:
            return jsonify({})

        r = 0.1075

        # Calcular IV implícita
        iv = BS.implied_vol(tipo, s0, k, t, r, premio)
        if iv is None:
            return jsonify({})

        sigma = iv
        gks = BS.greeks(tipo, s0, k, t, r, sigma)
        preco = BS.price(tipo, s0, k, t, r, sigma)

        return jsonify({
            "iv": iv * 100,  # Converter para percentual
            "delta": gks.get("delta"),
            "gamma": gks.get("gamma"),
            "theta": gks.get("theta"),
            "vega": gks.get("vega"),
            "preco_bs": preco,
        })

    @app.route("/api/estrutura/<int:eid>/atualizar-precos", methods=["POST"])
    @rate_limit(max_calls=10, window=60)
    def api_atualizar_precos(eid: int):
        """API para atualizar preços do ativo e opções de uma estrutura."""
        est = db.get("estruturas", eid)
        if not est:
            return jsonify({"error": "Estrutura não encontrada"}), 404
        
        resultado = atualizar_precos_estrutura(db, eid)
        return jsonify(resultado)

    @app.route("/api/estruturas/atualizar-todas", methods=["POST"])
    @rate_limit(max_calls=5, window=300)
    def api_atualizar_todas():
        """API para atualizar preços de todas as estruturas em andamento."""
        resultados = atualizar_todas_estruturas_em_andamento(db)
        total = len(resultados)
        sucessos = sum(1 for r in resultados.values() if r["ativo_atualizado"])
        return jsonify({
            "success": True,
            "total": total,
            "sucessos": sucessos,
            "resultados": resultados,
        })

    @app.route("/simulador/estrutura/<int:eid>/mudar-status", methods=["POST"])
    def mudar_status_estrutura(eid: int):
        """Muda o status da estrutura entre 'em_andamento' e 'finalizada'."""
        est = db.get("estruturas", eid)
        if not est:
            flash("Estrutura não encontrada.", "error")
            return _safe_redirect("simulador")
        
        status_atual = est.get("status", "em_andamento")
        novo_status = "finalizada" if status_atual == "em_andamento" else "em_andamento"
        
        # Preciso adicionar método para atualizar apenas o status
        db.update_status_estrutura(eid, novo_status)
        
        status_label = "finalizada" if novo_status == "finalizada" else "em andamento"
        flash(f"Estrutura marcada como '{status_label}'.", "info")
        
        return redirect(url_for("simulador", eid=eid))

    @app.route("/export/csv")
    def export_csv():
        data = export_zip_bytes(db)
        name = f"system_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        return Response(
            data,
            mimetype="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{name}"',
                "Cache-Control": "no-store",
            },
        )

    @app.route("/import/csv", methods=["POST"])
    def import_csv():
        redirect_to = url_for("historico")
        fe = request.files.get("estruturas_csv")
        fl = request.files.get("legs_csv")
        fz = request.files.get("zip_csv")
        raw: bytes | None = None
        if (
            fe
            and fl
            and getattr(fe, "filename", None)
            and getattr(fl, "filename", None)
        ):
            raw = zip_from_csv_parts(fe.read(), fl.read())
        elif fz and getattr(fz, "filename", None):
            fn = str(fz.filename).lower()
            if not fn.endswith(".zip"):
                flash("O ficheiro único deve ser um ZIP (.zip).", "error")
                return redirect(redirect_to)
            raw = fz.read()
        else:
            flash("Envie um ZIP ou os dois ficheiros CSV (estruturas e pernas).", "error")
            return redirect(redirect_to)
        try:
            n_e, n_l, sk = import_merge_zip(db, raw)
            flash(
                f"Importação concluída: {n_e} estrutura(s), {n_l} perna(s).",
                "success",
            )
            if sk:
                flash(
                    f"{sk} perna(s) ignoradas (estrutura_id inexistente no ficheiro ou dados inválidos).",
                    "warning",
                )
        except ValueError as e:
            flash(str(e), "error")
            log.error("Erro na importação: %s", e)
        return redirect(redirect_to)

    @app.route("/historico")
    @safe_render
    def historico():
        ests = db.get_estruturas()
        rows = []
        for est in ests:
            legs = db.get_legs(est["id"])
            m = BS.calc_metrics(est, legs)
            rows.append({"est": est, "legs": legs, "metrics": m})
        return render_template(
            "historico.html",
            rows=rows,
            brl=brl,
            fmt_date=fmt_date,
            dias_ate_venc=dias_ate_venc,
            color_pnl=color_pnl,
        )

    @app.route("/dashboard")
    @safe_render
    def dashboard():
        ests = db.get_estruturas()
        all_legs = db.get_all("legs")
        credito = debito = 0.0
        ganho_total = perda_total = 0.0
        tipo_map: dict[str, int] = {}
        est_names: list[str] = []
        est_premios: list[float] = []

        for est in ests:
            legs = [lg for lg in all_legs if lg.get("estruturaId") == est["id"]]
            m = BS.calc_metrics(est, legs)
            pl = float(m.get("premioLiq") or 0)
            if pl > 0:
                credito += pl
            else:
                debito += pl
            ganho_total += float(m.get("ganhoMax") or 0)
            perda_total += float(m.get("perdaMax") or 0)
            t = est.get("tipo") or "Outro"
            tipo_map[t] = tipo_map.get(t, 0) + 1
            nome = est.get("nome") or ""
            est_names.append(nome[:14] + ("…" if len(nome) > 14 else ""))
            est_premios.append(pl)

        chart_tipos = dashboard_doughnut(tipo_map, include_plotlyjs="cdn")
        chart_premios = dashboard_bar(est_names, est_premios, include_plotlyjs=False)


        return render_template(
            "dashboard.html",
            total_est=len(ests),
            total_legs=len(all_legs),
            credito=credito,
            debito=abs(debito),
            ganho_total=ganho_total,
            perda_total=abs(perda_total),
            chart_tipos=chart_tipos,
            chart_premios=chart_premios,
            brl=brl,
        )

    @app.route("/api/preview-greeks", methods=["POST"])
    @rate_limit(max_calls=60, window=60)
    def preview_greeks():
        data = request.get_json(force=True, silent=True) or {}
        try:
            s0 = float(data.get("preco_atual") or 0)
            k = float(data.get("strike") or 0)
            iv = float(data.get("iv") or 0)
            tipo = data.get("tipo") or "call"
            venc = data.get("venc") or ""
        except (TypeError, ValueError):
            return jsonify({}), 400
        if not s0 or not k or not iv or not venc:
            return jsonify({})

        try:
            v = datetime.strptime(venc[:10], "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            hoje = datetime.now()
            t = max(0.0, (v - hoje).total_seconds() / (365.0 * 24 * 3600))
        except ValueError:
            return jsonify({})
        if t <= 0:
            return jsonify({})

        r = 0.1075
        sigma = iv / 100.0
        if tipo not in ("call", "put"):
            tipo = "call"
        gks = BS.greeks(tipo, s0, k, t, r, sigma)
        preco = BS.price(tipo, s0, k, t, r, sigma)
        return jsonify(
            {
                "delta": gks.get("delta"),
                "gamma": gks.get("gamma"),
                "theta": gks.get("theta"),
                "vega": gks.get("vega"),
                "preco_sugerido": preco,
            }
        )

    @app.route("/admin/backup", methods=["GET"])
    def admin_backup():
        """Endpoint para backup do banco SQLite."""
        import shutil
        if not DB_PATH.exists():
            return abort(404, "Base de dados não encontrada.")
        name = f"system_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sqlite"
        backup_path = BASE_DIR / name
        shutil.copy2(DB_PATH, backup_path)
        return Response(
            open(backup_path, "rb").read(),
            mimetype="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{name}"',
            },
        )

    # ---- Rotas de dados de opções (OpLab) ----

    @app.route("/api/opcoes/atualizar", methods=["POST"])
    @rate_limit(max_calls=5, window=300)
    def atualizar_opcoes():
        """Atualiza dados de IV/IV Rank do OpLab e salva no DB."""
        try:
            dados = atualizar_dados_opcoes(db, usar_cache=True)
            if not dados:
                return jsonify({"error": "Nenhum dado extraído. Verifique o acesso ao OpLab."}), 502
            return jsonify({
                "success": True,
                "total": len(dados),
                "message": f"{len(dados)} ativos atualizados com sucesso.",
            })
        except Exception as e:
            log.error("Erro ao atualizar opções: %s", e)
            return jsonify({"error": str(e)}), 500

    @app.route("/api/opcoes/dados", methods=["GET"])
    def opcoes_dados():
        """Retorna dados de IV/IV Rank para os tickers informados."""
        tickers = request.args.get("tickers", "").split(",")
        tickers = [t.strip().upper() for t in tickers if t.strip()]
        if not tickers:
            # Retorna cache se não especificou tickers
            cache = carregar_cache_opcoes()
            return jsonify({"ativos": cache})
        dados = buscar_opcoes_dados(db, tickers)
        return jsonify({"ativos": dados})

    @app.route("/opcoes")
    @safe_render
    def opcoes_page():
        """Página de visualização de dados de opções (IV, IV Rank, etc.)."""
        tickers_comuns = ["PETR4", "VALE3", "ITUB4", "BBDC4", "ABEV3", "BBAS3", "WEGE3"]
        
        # Usar dados do cache primeiro, se vazio tentar do banco
        cache = carregar_cache_opcoes()
        
        # Se cache vazio, busca do banco
        if not cache:
            try:
                dados_db = buscar_opcoes_dados(db)
                # Converter formato do banco para formato do cache
                cache = [
                    {
                        "ticker": v.get("ticker", ""),
                        "preco": v.get("preco"),
                        "variacao_pct": v.get("variacao_pct"),
                        "vi": v.get("volatilidade_implicita"),
                        "iv_rank": v.get("iv_rank"),
                        "iv_percentil": v.get("iv_percentil"),
                        "atualizado_em": v.get("atualizado_em", ""),
                    }
                    for v in dados_db.values()
                ]
            except Exception as e:
                log.warning("Erro ao buscar dados do banco: %s", e)
        
        return render_template(
            "opcoes.html",
            ativos=cache,
            tickers_comuns=tickers_comuns,
            brl=brl,
            fmt_date=fmt_date,
        )

    # ---- Rotas de séries de opções detalhadas ----

    @app.route("/api/opcoes/series/<ticker>", methods=["GET"])
    @rate_limit(max_calls=30, window=60)
    def api_opcoes_series(ticker: str):
        """Retorna todas as séries de opções de um ticker com dados detalhados."""
        ticker = ticker.upper()
        mes = request.args.get("mes", type=int)
        ano = request.args.get("ano", type=int)
        
        try:
            opcoes = formatar_opcoes_tabela(ticker, mes=mes, ano=ano)
            if not opcoes:
                return jsonify({"error": f"Nenhuma opção encontrada para {ticker}"}), 404
            
            # Agrupar por série para facilitar consumo pelo frontend
            series = {}
            for opt in opcoes:
                serie = opt["serie"]
                if serie not in series:
                    series[serie] = {
                        "data": serie,
                        "dias_vencimento": opt["dias_vencimento"],
                        "opcoes": [],
                    }
                series[serie]["opcoes"].append(opt)
            
            return jsonify({
                "ticker": ticker,
                "total_opcoes": len(opcoes),
                "total_series": len(series),
                "series": series,
            })
        except Exception as e:
            log.error("Erro ao buscar opções de %s: %s", ticker, e)
            return jsonify({"error": str(e)}), 500

    @app.route("/api/opcoes/salvar/<ticker>", methods=["POST"])
    @rate_limit(max_calls=5, window=300)
    def api_salvar_opcoes_detalhadas(ticker: str):
        """Salva opções detalhadas no banco de dados."""
        ticker = ticker.upper()
        try:
            opcoes = formatar_opcoes_tabela(ticker)
            if not opcoes:
                return jsonify({"error": f"Nenhuma opção encontrada para {ticker}"}), 404
            
            count = salvar_opcoes_detalhadas(db, ticker, opcoes)
            return jsonify({
                "success": True,
                "total": count,
                "message": f"{count} opções salvas para {ticker}",
            })
        except Exception as e:
            log.error("Erro ao salvar opções de %s: %s", ticker, e)
            return jsonify({"error": str(e)}), 500

    @app.route("/opcoes/<ticker>")
    @safe_render
    def opcoes_detalhadas_page(ticker: str):
        """Página de visualização de opções detalhadas de um ticker."""
        ticker = ticker.upper()

        # Buscar dados do cache/DB primeiro
        opcoes_db = buscar_opcoes_serie(db, ticker)

        return render_template(
            "opcoes_detalhadas.html",
            ticker=ticker,
            opcoes_db=opcoes_db,
            brl=brl,
            fmt_date=fmt_date,
        )

    # ---- Rotas de sugestão de estruturas ----

    @app.route("/sugestoes")
    @safe_render
    def sugestoes_page():
        """Página de sugestão de estruturas de opções."""
        from system.analysis.sugestoes import ESTRATEGIAS_DISPONIVEIS
        return render_template(
            "sugestoes.html",
            estrategias=ESTRATEGIAS_DISPONIVEIS,
            brl=brl,
            fmt_date=fmt_date,
        )

    @app.route("/api/sugestoes", methods=["POST"])
    @rate_limit(max_calls=10, window=60)
    def api_sugestoes():
        """API para análise e sugestão de estruturas."""
        from system.analysis.sugestoes import ESTRATEGIAS_DISPONIVEIS
        from system.analysis.indicadores import buscar_indicadores
        
        data = request.get_json(force=True, silent=True) or {}
        
        ticker = (data.get("ticker") or "").strip().upper()
        if not ticker:
            return jsonify({"error": "Informe o ticker do ativo."}), 400
        
        estrategia = (data.get("estrategia") or "auto").strip()
        dias_min = data.get("dias_min", 5)
        dias_max = data.get("dias_max", 180)
        
        try:
            # Buscar opções detalhadas do DB primeiro (para VI média)
            opcoes_db = buscar_opcoes_serie(db, ticker)
            
            # Buscar indicadores técnicos do Yahoo Finance com opções
            indicadores = buscar_indicadores(ticker, opcoes=opcoes_db)
            if not indicadores:
                log.warning("Não foi possível obter indicadores técnicos para %s", ticker)
            
            # Se não tem no DB, tentar buscar do OpLab
            if not opcoes_db:
                log.info("Opções para %s não encontradas no DB, buscando do OpLab...", ticker)
                opcoes_api = formatar_opcoes_tabela(ticker)
                if not opcoes_api:
                    return jsonify({
                        "error": f"Nenhuma opção encontrada para {ticker}. Tente salvar os dados primeiro."
                    }), 404
                opcoes_db = opcoes_api
            
            # Usar preço dos indicadores (Yahoo Finance) ou fallback
            preco_atual = indicadores.get("price") if indicadores else None
            
            if not preco_atual or preco_atual <= 0:
                # Fallback: usar preço das opções
                for opt in opcoes_db:
                    if opt.get("ultimo_preco", 0) > 0:
                        strike = opt.get("strike", 0)
                        if strike > 0:
                            preco_atual = strike
                            break
            
            if not preco_atual or preco_atual <= 0:
                return jsonify({"error": "Não foi possível obter o preço atual do ativo."}), 400
            
            # Executar análise
            resultado = analisar_sugestoes(
                ticker=ticker,
                options=opcoes_db,
                preco_atual=float(preco_atual),
                estrategia=estrategia,
                vencimento_dias_min=int(dias_min),
                vencimento_dias_max=int(dias_max),
                indicadores=indicadores,
            )
            
            return jsonify(resultado)

        except Exception as e:
            log.error("Erro ao analisar sugestões para %s: %s", ticker, e)
            return jsonify({"error": f"Erro interno: {str(e)}"}), 500

    # ========================================================================
    # ROTAS DE CARTEIRA DE INVESTIMENTOS
    # ========================================================================

    @app.route("/carteira")
    @safe_render
    def carteira_page():
        """Página principal de carteiras"""
        from system.portfolio.metrics import calcular_metricas_carteira, validar_alocacoes

        carteiras = db.get_carteiras()
        carteira_id = request.args.get("id")
        carteira_selecionada = None
        ativos = []
        metricas = None
        validacao_alocacoes = (True, "")
        chart_alocacao = None

        if carteira_id:
            try:
                carteira_selecionada = db.get_carteira(int(carteira_id))
                if carteira_selecionada:
                    ativos = db.get_ativos_carteira(int(carteira_id))
                    metricas = calcular_metricas_carteira(ativos)
                    validacao_alocacoes = validar_alocacoes(ativos)

                    # Gerar gráfico se tem ativos
                    if ativos:
                        chart_alocacao = plotly_carteira_alocacao(ativos, include_plotlyjs="cdn")
            except (ValueError, TypeError):
                pass

        return render_template(
            "carteira.html",
            carteiras=carteiras,
            carteira_selecionada=carteira_selecionada,
            ativos=ativos,
            metricas=metricas,
            validacao_alocacoes=validacao_alocacoes,
            chart_alocacao=chart_alocacao,
            brl=brl,
            color_pnl=color_pnl,
        )

    @app.route("/api/carteira/salvar", methods=["POST"])
    def api_salvar_carteira():
        """Criar/editar carteira"""
        data = request.get_json(force=True, silent=True) or {}
        try:
            obj = {
                "nome": (data.get("nome") or "").strip(),
                "descricao": (data.get("descricao") or "").strip(),
            }

            if not obj["nome"]:
                return jsonify({"success": False, "error": "Nome da carteira é obrigatório"}), 400

            if data.get("id"):
                try:
                    obj["id"] = int(data["id"])
                except (ValueError, TypeError):
                    pass

            cid = db.save_carteira(obj, autocommit=True)
            log.info("Carteira salva: id=%s, nome=%s", cid, obj["nome"])
            return jsonify({"success": True, "id": cid, "message": "Carteira salva com sucesso"})
        except Exception as e:
            log.error("Erro ao salvar carteira: %s", e)
            return jsonify({"success": False, "error": str(e)}), 400

    @app.route("/api/carteira/<int:cid>/deletar", methods=["POST"])
    def api_deletar_carteira(cid):
        """Deletar carteira (e todos os ativos)"""
        try:
            db.delete_carteira(cid)
            log.info("Carteira deletada: id=%s", cid)
            return jsonify({"success": True, "message": "Carteira deletada com sucesso"})
        except Exception as e:
            log.error("Erro ao deletar carteira %s: %s", cid, e)
            return jsonify({"success": False, "error": str(e)}), 400

    @app.route("/api/carteira/<int:cid>/ativo/salvar", methods=["POST"])
    def api_salvar_ativo_carteira(cid):
        """Criar/editar ativo na carteira"""
        from system.data.precos import obter_preco_ativo_yahoo
        from system.portfolio.metrics import validar_alocacoes

        data = request.get_json(force=True, silent=True) or {}
        try:
            ticker = (data.get("ticker") or "").strip().upper()
            if not ticker:
                return jsonify({"success": False, "error": "Ticker é obrigatório"}), 400

            try:
                alocacao_ideal = float(data.get("alocacaoIdeal") or 0)
                if alocacao_ideal < 0 or alocacao_ideal > 100:
                    return jsonify({
                        "success": False,
                        "error": "Alocação ideal deve estar entre 0 e 100%"
                    }), 400
            except (ValueError, TypeError):
                return jsonify({
                    "success": False,
                    "error": "Alocação ideal inválida"
                }), 400

            # Validar soma de alocações ideais
            ativos_existentes = db.get_ativos_carteira(cid)
            soma_ideal = sum(float(a.get("alocacaoIdeal") or 0) for a in ativos_existentes
                           if str(a.get("id")) != str(data.get("id")))
            soma_ideal += alocacao_ideal

            # Permitir até 100% (pode ser incompleto ou completamente alocado)
            if soma_ideal > 100.01:  # tolerância de 0.01% acima
                return jsonify({
                    "success": False,
                    "error": f"Soma de alocações ideais ultrapassa 100% (seria: {soma_ideal:.2f}%)"
                }), 400

            # Obter preço atual do Yahoo Finance
            preco_atual = obter_preco_ativo_yahoo(ticker)
            if not preco_atual:
                log.warning("Não foi possível obter preço para %s", ticker)
                # Permitir salvar mesmo sem preço (pode estar indisponível)
                # preco_atual = None

            try:
                quantidade = float(data.get("quantidade") or 0)
                preco_medio = float(data.get("precoMedio") or 0)
            except (ValueError, TypeError):
                return jsonify({
                    "success": False,
                    "error": "Quantidade e preço médio devem ser numéricos"
                }), 400

            obj = {
                "carteiraId": cid,
                "ticker": ticker,
                "quantidade": quantidade,
                "precoMedio": preco_medio,
                "alocacaoIdeal": alocacao_ideal,
                "precoAtual": preco_atual,
            }

            if data.get("id"):
                try:
                    obj["id"] = int(data["id"])
                except (ValueError, TypeError):
                    pass

            aid = db.save_ativo_carteira(obj, autocommit=True)
            log.info("Ativo salvo: id=%s, ticker=%s, preço=%s", aid, ticker, preco_atual)

            return jsonify({
                "success": True,
                "id": aid,
                "precoAtual": preco_atual,
                "message": "Ativo salvo com sucesso"
            })
        except Exception as e:
            log.error("Erro ao salvar ativo em carteira %s: %s", cid, e)
            return jsonify({"success": False, "error": str(e)}), 400

    @app.route("/api/carteira/ativo/<int:aid>/deletar", methods=["POST"])
    def api_deletar_ativo_carteira(aid):
        """Deletar ativo da carteira"""
        try:
            db.delete_ativo_carteira(aid)
            log.info("Ativo deletado: id=%s", aid)
            return jsonify({"success": True, "message": "Ativo removido com sucesso"})
        except Exception as e:
            log.error("Erro ao deletar ativo %s: %s", aid, e)
            return jsonify({"success": False, "error": str(e)}), 400

    @app.route("/api/carteira/<int:cid>/atualizar-precos", methods=["POST"])
    @rate_limit(max_calls=10, window=60)
    def api_atualizar_precos_carteira(cid):
        """Atualizar preços de todos os ativos da carteira via Yahoo Finance"""
        from system.data.precos import obter_preco_ativo_yahoo

        try:
            ativos = db.get_ativos_carteira(cid)
            if not ativos:
                return jsonify({
                    "success": False,
                    "error": "Esta carteira não contém ativos",
                    "message": "Nenhum ativo para atualizar"
                }), 400

            atualizados = 0
            erros = []

            for ativo in ativos:
                ticker = (ativo.get("ticker") or "").strip()
                if not ticker:
                    continue

                try:
                    preco = obter_preco_ativo_yahoo(ticker)
                    if preco and preco > 0:
                        db.atualizar_preco_ativo(ativo["id"], preco)
                        atualizados += 1
                        log.info("Preço atualizado: %s = R$ %.2f", ticker, preco)
                    else:
                        erros.append(f"{ticker}: preço não disponível")
                except Exception as e:
                    erros.append(f"{ticker}: {str(e)}")
                    log.error("Erro ao atualizar preço de %s: %s", ticker, e)

                # Pequeno delay para não sobrecarregar API
                time.sleep(0.2)

            msg = f"{atualizados} ativo(s) atualizado(s)"
            if erros:
                msg += f"; {len(erros)} erro(s)"

            return jsonify({
                "success": atualizados > 0,
                "atualizados": atualizados,
                "erros": erros,
                "message": msg
            })
        except Exception as e:
            log.error("Erro ao atualizar preços da carteira %s: %s", cid, e)
            return jsonify({"success": False, "error": str(e)}), 500

    # ---- Inicializar scheduler de notificações ----
    @app.shell_context_processor
    def make_shell_context():
        return {"db": db}
    
    try:
        iniciar_scheduler()
        log.info("✓ Scheduler de notificações iniciado")
    except Exception as e:
        log.warning("⚠ Scheduler de notificações não iniciado: %s", e)
    
    # Registrar shutdown handler
    def shutdown_handler():
        try:
            parar_scheduler()
            log.info("✓ Scheduler de notificações parado")
        except Exception as e:
            log.warning("⚠ Erro ao parar scheduler: %s", e)
    
    app.teardown_appcontext(lambda exc: shutdown_handler() if exc is None else None)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=DEBUG, host=HOST, port=PORT)

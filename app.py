"""
Eagle System — aplicação Flask (port do controller js/app.js).
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from flask import (
    Flask,
    Response,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from eagle import blackscholes as BS
from eagle.charts import dashboard_bar, dashboard_doughnut, payoff_figure
from eagle.csv_io import export_zip_bytes, import_merge_zip, zip_from_csv_parts
from eagle.db import Database, get_db_path
from eagle.ui_format import brl, color_pnl, dias_ate_venc, fmt_date

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
db = Database(get_db_path(INSTANCE_DIR))


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
        gks = BS.greeks(typ, s0, k, t, r, sigma)  # type: ignore[arg-type]
        bs_delta = gks.get("delta")
        bs_preco = BS.price(typ, s0, k, t, r, sigma)  # type: ignore[arg-type]
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


def create_app() -> Flask:
    app = Flask(
        __name__,
        static_folder="static",
        template_folder="templates",
    )
    app.secret_key = os.environ.get("EAGLE_SECRET", "eagle-dev-secret-change-in-production")

    @app.before_request
    def _ensure_db() -> None:
        db.connect()

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
                if eid:
                    return redirect(url_for("simulador", eid=eid, q=q or None))
                return redirect(url_for("simulador", q=q or None))
            if action == "select":
                sid = request.form.get("estrutura_id", type=int)
                if sid:
                    return redirect(url_for("simulador", eid=sid, q=q or None))
                return redirect(url_for("simulador", q=q or None))

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
            brl=brl,
            fmt_date=fmt_date,
            dias_ate_venc=dias_ate_venc,
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
            return redirect(request.referrer or url_for("simulador", modal_est=1))
        if not ativo:
            flash("Informe o ativo (ticker).", "error")
            return redirect(request.referrer or url_for("simulador", modal_est=1))

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
            return redirect(url_for("simulador"))

        strike = request.form.get("strike", type=float)
        qtd = request.form.get("qtd", type=int)
        if not strike or strike <= 0:
            flash("Informe o Strike.", "error")
            return redirect(url_for("simulador", eid=eid, modal_leg=1))
        if not qtd or qtd <= 0:
            flash("Informe a Quantidade.", "error")
            return redirect(url_for("simulador", eid=eid, modal_leg=1))

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

    @app.route("/export/csv")
    def export_csv():
        data = export_zip_bytes(db)
        name = f"eagle_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
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
        redirect_to = request.referrer or url_for("historico")
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
        return redirect(redirect_to)

    @app.route("/historico")
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
            debito=debito,
            ganho_total=ganho_total,
            perda_total=perda_total,
            chart_tipos=chart_tipos,
            chart_premios=chart_premios,
            brl=brl,
        )

    @app.route("/api/preview-greeks", methods=["POST"])
    def preview_greeks():
        from flask import jsonify

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

        from datetime import datetime

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
        gks = BS.greeks(tipo, s0, k, t, r, sigma)  # type: ignore[arg-type]
        preco = BS.price(tipo, s0, k, t, r, sigma)  # type: ignore[arg-type]
        return jsonify(
            {
                "delta": gks.get("delta"),
                "gamma": gks.get("gamma"),
                "theta": gks.get("theta"),
                "vega": gks.get("vega"),
                "preco_sugerido": preco,
            }
        )

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)

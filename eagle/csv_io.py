"""
Exportação / importação de dados em CSV dentro de um ZIP (UTF-8, BOM).
Formato: estruturas.csv + legs.csv com cabeçalhos em snake_case (alinhados ao SQLite).
"""

from __future__ import annotations

import csv
import io
import zipfile
from datetime import datetime, timezone
from typing import Any

from eagle.db import Database

ESTRUTURAS_CSV = "estruturas.csv"
LEGS_CSV = "legs.csv"

ESTRUTURAS_FIELDS = [
    "id",
    "nome",
    "ativo",
    "tipo",
    "preco_atual",
    "data_venc",
    "obs",
    "criado_em",
    "atualizado_em",
]

LEGS_FIELDS = [
    "id",
    "estrutura_id",
    "operacao",
    "tipo",
    "qtd",
    "strike",
    "ticker",
    "vencimento",
    "premio",
    "iv",
    "delta",
    "gamma",
    "theta",
    "vega",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _cell(v: Any) -> str:
    if v is None:
        return ""
    return str(v)


def _parse_float(s: str | None) -> float | None:
    if s is None:
        return None
    t = str(s).strip()
    if t == "" or t.lower() == "none":
        return None
    t = t.replace(",", ".")
    return float(t)


def _parse_int(s: str | None) -> int | None:
    if s is None:
        return None
    t = str(s).strip()
    if t == "":
        return None
    return int(float(t.replace(",", ".")))


def _parse_opt_float(s: str | None) -> float | None:
    try:
        return _parse_float(s)
    except (TypeError, ValueError):
        return None


def zip_from_csv_parts(estruturas_body: bytes, legs_body: bytes) -> bytes:
    """Monta o mesmo ZIP que o export, a partir de dois CSV em bruto (UTF-8)."""
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(ESTRUTURAS_CSV, estruturas_body)
        zf.writestr(LEGS_CSV, legs_body)
    return out.getvalue()


def export_zip_bytes(db: Database) -> bytes:
    ests = sorted(db.get_all("estruturas"), key=lambda e: e.get("id") or 0)
    legs = sorted(
        db.get_all("legs"),
        key=lambda lg: (lg.get("estruturaId") or 0, lg.get("id") or 0),
    )

    est_buf = io.StringIO()
    w1 = csv.writer(est_buf, lineterminator="\n")
    w1.writerow(ESTRUTURAS_FIELDS)
    for e in ests:
        w1.writerow(
            [
                _cell(e.get("id")),
                _cell(e.get("nome")),
                _cell(e.get("ativo")),
                _cell(e.get("tipo")),
                _cell(e.get("precoAtual")),
                _cell(e.get("dataVenc")),
                _cell(e.get("obs")),
                _cell(e.get("criadoEm")),
                _cell(e.get("atualizadoEm")),
            ]
        )

    leg_buf = io.StringIO()
    w2 = csv.writer(leg_buf, lineterminator="\n")
    w2.writerow(LEGS_FIELDS)
    for lg in legs:
        w2.writerow(
            [
                _cell(lg.get("id")),
                _cell(lg.get("estruturaId")),
                _cell(lg.get("operacao")),
                _cell(lg.get("tipo")),
                _cell(lg.get("qtd")),
                _cell(lg.get("strike")),
                _cell(lg.get("ticker")),
                _cell(lg.get("vencimento")),
                _cell(lg.get("premio")),
                _cell(lg.get("iv")),
                _cell(lg.get("delta")),
                _cell(lg.get("gamma")),
                _cell(lg.get("theta")),
                _cell(lg.get("vega")),
            ]
        )

    out = io.BytesIO()
    est_text = "\ufeff" + est_buf.getvalue()
    leg_text = "\ufeff" + leg_buf.getvalue()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(ESTRUTURAS_CSV, est_text.encode("utf-8"))
        zf.writestr(LEGS_CSV, leg_text.encode("utf-8"))
    return out.getvalue()


def _read_csv_table(text: str, expected: list[str]) -> list[dict[str, str]]:
    f = io.StringIO(text)
    reader = csv.DictReader(f)
    if not reader.fieldnames:
        raise ValueError("CSV sem cabeçalho.")
    colmap: dict[str, str] = {}
    for exp in expected:
        found = None
        for actual in reader.fieldnames:
            if not actual:
                continue
            if actual.strip().lstrip("\ufeff").lower() == exp.lower():
                found = actual
                break
        if not found:
            raise ValueError(f"Cabeçalho em falta ou inválido: {exp}")
        colmap[exp] = found
    rows: list[dict[str, str]] = []
    for raw in reader:
        row: dict[str, str] = {}
        for exp in expected:
            v = raw.get(colmap[exp])
            row[exp] = (v or "").strip() if v is not None else ""
        rows.append(row)
    return rows


def import_merge_zip(db: Database, zip_bytes: bytes) -> tuple[int, int, int]:
    """
    Importa em modo **merge**: insere novas estruturas e pernas; IDs do ficheiro
    são mapeados para novos IDs na base. Devolve (n_estruturas, n_pernas, n_pernas_ignoradas).
    Transação única: tudo ou nada.
    """
    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes), "r")
    except zipfile.BadZipFile as e:
        raise ValueError("Ficheiro ZIP inválido.") from e

    def _zip_find(name: str) -> str | None:
        want = name.lower()
        for n in zf.namelist():
            if n.rstrip("/").rsplit("/", 1)[-1].lower() == want:
                return n
        return None

    if not _zip_find(ESTRUTURAS_CSV) or not _zip_find(LEGS_CSV):
        raise ValueError(
            f'O ZIP deve conter {ESTRUTURAS_CSV} e {LEGS_CSV} (nomes exatos).'
        )

    def read(name: str) -> str:
        path = _zip_find(name)
        if not path:
            raise ValueError(f"Entrada em falta: {name}")
        return zf.read(path).decode("utf-8-sig")

    est_text = read(ESTRUTURAS_CSV)
    leg_text = read(LEGS_CSV)

    est_rows = _read_csv_table(est_text, ESTRUTURAS_FIELDS)
    leg_rows = _read_csv_table(leg_text, LEGS_FIELDS)

    conn = db.connect()
    conn.execute("BEGIN IMMEDIATE")
    skipped = 0
    try:
        id_map: dict[int, int] = {}
        n_est = 0

        # Ordem das linhas no CSV importa se a coluna id estiver vazia (usa-se 1, 2, 3…).
        for i, r in enumerate(est_rows):
            nome = (r.get("nome") or "").strip()
            if not nome:
                continue
            old_id = _parse_int(r.get("id"))
            if old_id is None:
                old_id = i + 1
            obj = {
                "nome": nome,
                "ativo": (r.get("ativo") or "").strip() or None,
                "tipo": (r.get("tipo") or "").strip() or None,
                "precoAtual": _parse_opt_float(r.get("preco_atual")),
                "dataVenc": (r.get("data_venc") or "").strip() or None,
                "obs": (r.get("obs") or "").strip() or None,
                "criadoEm": (r.get("criado_em") or "").strip() or _now_iso(),
                "atualizadoEm": _now_iso(),
            }
            new_id = db.save_estrutura(obj, autocommit=False)
            n_est += 1
            if old_id is not None:
                id_map[old_id] = new_id

        leg_sorted = sorted(
            leg_rows,
            key=lambda r: (
                _parse_int(r.get("estrutura_id")) or 0,
                _parse_int(r.get("id")) or 0,
            ),
        )
        n_leg = 0
        for r in leg_sorted:
            old_eid = _parse_int(r.get("estrutura_id"))
            if old_eid is None or old_eid not in id_map:
                skipped += 1
                continue
            op = (r.get("operacao") or "compra").strip().lower()
            if op not in ("compra", "venda"):
                op = "compra"
            tp = (r.get("tipo") or "call").strip().lower()
            if tp not in ("call", "put"):
                tp = "call"
            try:
                qtd = _parse_float(r.get("qtd"))
                strike = _parse_float(r.get("strike"))
            except (TypeError, ValueError):
                skipped += 1
                continue
            if qtd is None or strike is None or qtd <= 0 or strike <= 0:
                skipped += 1
                continue

            obj = {
                "estruturaId": id_map[old_eid],
                "operacao": op,
                "tipo": tp,
                "qtd": qtd,
                "strike": strike,
                "ticker": ((r.get("ticker") or "").strip().upper() or None),
                "vencimento": (r.get("vencimento") or "").strip() or None,
                "premio": _parse_opt_float(r.get("premio")) or 0.0,
                "iv": _parse_opt_float(r.get("iv")),
                "delta": _parse_opt_float(r.get("delta")),
                "gamma": _parse_opt_float(r.get("gamma")),
                "theta": _parse_opt_float(r.get("theta")),
                "vega": _parse_opt_float(r.get("vega")),
            }
            db.save_leg(obj, autocommit=False)
            n_leg += 1

        conn.commit()
    except Exception:
        conn.rollback()
        raise

    return (n_est, n_leg, skipped)

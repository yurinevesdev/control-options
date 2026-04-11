"""Formatação de UI (equivalente a js/ui.js)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional


def brl(v: Optional[float], decimals: int = 2) -> str:
    if v is None:
        return "—"
    try:
        x = float(v)
    except (TypeError, ValueError):
        return "—"
    if x != x:  # NaN
        return "—"
    neg = x < 0
    x = abs(x)
    s = f"{x:,.{decimals}f}"
    main, frac = s.rsplit(".", 1)
    main = main.replace(",", ".")
    out = f"{main},{frac}"
    return ("- " if neg else "") + "R$ " + out


def pct(v: Optional[float], decimals: int = 1) -> str:
    if v is None:
        return "—"
    try:
        x = float(v)
    except (TypeError, ValueError):
        return "—"
    return f"{(x * 100):.{decimals}f}%"


def num(v: Optional[float], d: int = 2) -> str:
    if v is None:
        return "—"
    try:
        x = float(v)
    except (TypeError, ValueError):
        return "—"
    return f"{x:.{d}f}"


def fmt_date(d: Optional[str]) -> str:
    if not d:
        return "—"
    try:
        dt = datetime.strptime(d[:10], "%Y-%m-%d")
        return dt.strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return "—"


def dias_ate_venc(data_venc: Optional[str]) -> Optional[int]:
    if not data_venc:
        return None
    try:
        venc = datetime.strptime(data_venc[:10], "%Y-%m-%d").replace(
            hour=23, minute=59, second=59
        )
        hoje = datetime.now()
        return int(round((venc - hoje).total_seconds() / (24 * 3600)))
    except (ValueError, TypeError):
        return None


def color_pnl(v: Optional[float]) -> str:
    if v is None:
        return ""
    try:
        x = float(v)
    except (TypeError, ValueError):
        return ""
    if x > 0:
        return "pos"
    if x < 0:
        return "neg"
    return "neu"

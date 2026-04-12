"""
System — Black-Scholes Engine (port fiel do js/blackscholes.js).
"""

from __future__ import annotations

import math
from typing import Any, Literal, Optional, TypedDict

OptionType = Literal["call", "put"]


def norm_cdf(x: float) -> float:
    a1 = 0.254829592
    a2 = -0.284496736
    a3 = 1.421413741
    a4 = -1.453152027
    a5 = 1.061405429
    p = 0.3275911
    sign = -1.0 if x < 0 else 1.0
    ax = abs(x) / math.sqrt(2.0)
    t = 1.0 / (1.0 + p * ax)
    y = 1.0 - (((((a5 * t + a4) * t + a3) * t + a2) * t + a1) * t * math.exp(-ax * ax))
    return 0.5 * (1.0 + sign * y)


def norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)


def d1d2(S: float, K: float, T: float, r: float, sigma: float, q: float = 0.0):
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return float("nan"), float("nan")
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return d1, d2


def price(
    typ: OptionType,
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    q: float = 0.0,
) -> float:
    if T <= 0:
        if typ == "call":
            return max(0.0, S - K)
        return max(0.0, K - S)
    d1, d2 = d1d2(S, K, T, r, sigma, q)
    if math.isnan(d1):
        return 0.0
    if typ == "call":
        return S * math.exp(-q * T) * norm_cdf(d1) - K * math.exp(-r * T) * norm_cdf(d2)
    return K * math.exp(-r * T) * norm_cdf(-d2) - S * math.exp(-q * T) * norm_cdf(-d1)


class GreeksResult(TypedDict, total=False):
    delta: Optional[float]
    gamma: Optional[float]
    theta: Optional[float]
    vega: Optional[float]
    rho: Optional[float]


def greeks(
    typ: OptionType,
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    q: float = 0.0,
) -> GreeksResult:
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return {
            "delta": None,
            "gamma": None,
            "theta": None,
            "vega": None,
            "rho": None,
        }
    d1, d2 = d1d2(S, K, T, r, sigma, q)
    nd1 = norm_pdf(d1)
    eq_t = math.exp(-q * T)
    er_t = math.exp(-r * T)
    sq_t = math.sqrt(T)
    nd1_cdf = norm_cdf(d1)
    nd2_cdf = norm_cdf(d2)

    if typ == "call":
        delta = eq_t * nd1_cdf
        theta = (
            -(S * eq_t * nd1 * sigma) / (2 * sq_t)
            - r * K * er_t * nd2_cdf
            + q * S * eq_t * nd1_cdf
        ) / 365.0
        rho = K * T * er_t * nd2_cdf / 100.0
    else:
        delta = -eq_t * norm_cdf(-d1)
        theta = (
            -(S * eq_t * nd1 * sigma) / (2 * sq_t)
            + r * K * er_t * norm_cdf(-d2)
            - q * S * eq_t * norm_cdf(-d1)
        ) / 365.0
        rho = -K * T * er_t * norm_cdf(-d2) / 100.0

    gamma = (eq_t * nd1) / (S * sigma * sq_t)
    vega = S * eq_t * nd1 * sq_t / 100.0

    return {"delta": delta, "gamma": gamma, "theta": theta, "vega": vega, "rho": rho}


def implied_vol(
    typ: OptionType,
    S: float,
    K: float,
    T: float,
    r: float,
    market_price: float,
    q: float = 0.0,
) -> Optional[float]:
    if T <= 0 or market_price <= 0:
        return None
    sigma = 0.3
    for _ in range(100):
        d1, _ = d1d2(S, K, T, r, sigma, q)
        p = price(typ, S, K, T, r, sigma, q)
        vg = S * math.exp(-q * T) * norm_pdf(d1) * math.sqrt(T)
        diff = p - market_price
        if abs(diff) < 1e-8:
            break
        if abs(vg) < 1e-10:
            break
        sigma = sigma - diff / vg
        if sigma <= 0:
            sigma = 1e-5
        if sigma > 10:
            return None
    if 0.001 <= sigma <= 10:
        return sigma
    return None


def _float_leg(leg: dict, key: str, default: float = 0.0) -> float:
    v = leg.get(key)
    if v is None or v == "":
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def leg_payoff_at_expiry(leg: dict, S: float) -> float:
    K = _float_leg(leg, "strike")
    prem = _float_leg(leg, "premio")
    qtd = _float_leg(leg, "qtd", 1.0)
    mult = 1.0 if leg.get("operacao") == "compra" else -1.0
    if leg.get("tipo") == "call":
        intrinsic = max(0.0, S - K)
    else:
        intrinsic = max(0.0, K - S)
    return mult * qtd * (intrinsic - prem)


def leg_pnl_current(leg: dict, S: float, T: float, r: float = 0.1075) -> float:
    K = _float_leg(leg, "strike")
    prem = _float_leg(leg, "premio")
    qtd = _float_leg(leg, "qtd", 1.0)
    iv = _float_leg(leg, "iv", 30.0)
    mult = 1.0 if leg.get("operacao") == "compra" else -1.0
    sigma = iv / 100.0
    typ = leg.get("tipo") or "call"
    if typ not in ("call", "put"):
        typ = "call"
    current_value = price(typ, S, K, T, r, sigma)  # type: ignore[arg-type]
    return mult * qtd * (current_value - prem)


def _days_to_expiry(data_venc: Optional[str]) -> float:
    if not data_venc:
        return 0.0
    from datetime import date, datetime

    try:
        venc = datetime.strptime(data_venc[:10], "%Y-%m-%d").replace(
            hour=23, minute=59, second=59
        )
        hoje = datetime.now()
        dias = (venc - hoje).total_seconds() / (24 * 3600)
        return max(0.0, dias / 365.0)
    except (ValueError, TypeError):
        return 0.0


def compute_payoff_series(
    estrutura: dict,
    legs: list,
    num_points: int = 300,
):
    if not legs:
        return None

    S0 = float(estrutura.get("precoAtual") or estrutura.get("preco_atual") or 20)
    r = 0.1075

    data_venc = estrutura.get("dataVenc") or estrutura.get("data_venc")
    T = _days_to_expiry(data_venc)

    strikes = []
    for leg in legs:
        k = _float_leg(leg, "strike")
        if k > 0:
            strikes.append(k)
    if not strikes:
        min_str = S0
        max_str = S0
    else:
        min_str = min(S0, min(strikes))
        max_str = max(S0, max(strikes))
    x_min = max(0.01, min_str * 0.6)
    x_max = max_str * 1.4

    labels: list[float] = []
    payoff_expiry: list[float] = []
    payoff_current: list[float] = []

    for i in range(num_points + 1):
        sx = x_min + (x_max - x_min) * (i / num_points)
        labels.append(sx)
        pnl_exp = 0.0
        for leg in legs:
            pnl_exp += leg_payoff_at_expiry(leg, sx)
        payoff_expiry.append(pnl_exp)
        if T > 0.001:
            pnl_cur = 0.0
            for leg in legs:
                pnl_cur += leg_pnl_current(leg, sx, T, r)
            payoff_current.append(pnl_cur)

    payoff_cur_out = payoff_current if payoff_current else None
    return {
        "labels": labels,
        "payoffExpiry": payoff_expiry,
        "payoffCurrent": payoff_cur_out,
        "xMin": x_min,
        "xMax": x_max,
        "T": T,
        "S0": S0,
    }


def calc_metrics(estrutura: dict, legs: list) -> dict[str, Any]:
    zero = {
        "posInicial": 0.0,
        "ganhoMax": 0.0,
        "perdaMax": 0.0,
        "breakEvens": [],
        "margem": 0.0,
        "premioLiq": 0.0,
        "delta": None,
        "gamma": None,
        "theta": None,
        "vega": None,
        "rho": None,
    }
    if not legs:
        return zero

    S0 = float(estrutura.get("precoAtual") or estrutura.get("preco_atual") or 0)
    r = 0.1075
    data_venc = estrutura.get("dataVenc") or estrutura.get("data_venc")
    T = _days_to_expiry(data_venc)

    premio_liq = 0.0
    g_delta = g_gamma = g_theta = g_vega = g_rho = 0.0
    has_greeks = False

    for leg in legs:
        prem = _float_leg(leg, "premio")
        qtd = _float_leg(leg, "qtd", 1.0)
        mult = -1.0 if leg.get("operacao") == "compra" else 1.0
        premio_liq += mult * prem * qtd

        K = _float_leg(leg, "strike")
        iv_pct = leg.get("iv")
        try:
            iv_val = float(iv_pct) if iv_pct is not None and iv_pct != "" else None
        except (TypeError, ValueError):
            iv_val = None
        sigma = iv_val / 100.0 if iv_val and iv_val > 0 else None

        typ = leg.get("tipo") or "call"
        if typ not in ("call", "put"):
            typ = "call"

        g = None
        if sigma and T > 0 and S0 > 0 and K > 0:
            g = greeks(typ, S0, K, T, r, sigma)
            has_greeks = True
        elif leg.get("delta") is not None and leg.get("delta") != "":
            g = {
                "delta": float(leg.get("delta") or 0),
                "gamma": float(leg.get("gamma") or 0),
                "theta": float(leg.get("theta") or 0),
                "vega": float(leg.get("vega") or 0),
                "rho": 0.0,
            }
            has_greeks = True

        if g:
            d = 1.0 if leg.get("operacao") == "compra" else -1.0
            g_delta += d * (g.get("delta") or 0) * qtd
            g_gamma += d * (g.get("gamma") or 0) * qtd
            g_theta += d * (g.get("theta") or 0) * qtd
            g_vega += d * (g.get("vega") or 0) * qtd
            g_rho += d * (g.get("rho") or 0) * qtd

    series = compute_payoff_series(estrutura, legs, 500)
    ganho_max = float("-inf")
    perda_max = float("inf")
    break_evens: list[float] = []

    if series:
        for v in series["payoffExpiry"]:
            if v > ganho_max:
                ganho_max = v
            if v < perda_max:
                perda_max = v
        pe = series["payoffExpiry"]
        lbl = series["labels"]
        for i in range(len(pe) - 1):
            y0, y1 = pe[i], pe[i + 1]
            if (y0 <= 0 and y1 > 0) or (y0 >= 0 and y1 < 0):
                x0, x1 = lbl[i], lbl[i + 1]
                x_be = x0 + (x1 - x0) * (-y0 / (y1 - y0)) if y1 != y0 else x0
                break_evens.append(x_be)

    if ganho_max == float("-inf"):
        ganho_max = 0.0
    if perda_max == float("inf"):
        perda_max = 0.0

    margem = abs(perda_max) if abs(perda_max) > 0 else 0.0

    return {
        "posInicial": premio_liq,
        "ganhoMax": ganho_max,
        "perdaMax": perda_max,
        "breakEvens": break_evens,
        "margem": margem,
        "premioLiq": premio_liq,
        "delta": g_delta if has_greeks else None,
        "gamma": g_gamma if has_greeks else None,
        "theta": g_theta if has_greeks else None,
        "vega": g_vega if has_greeks else None,
        "rho": g_rho if has_greeks else None,
    }

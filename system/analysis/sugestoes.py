"""
Yuri System — Módulo de Sugestão de Estruturas de Opções.

Analisa dados de opções disponíveis e sugere as melhores combinações
baseado na matriz de decisão do ANALISE.md:
- Classifica cenário: Esticado (Topo), Suporte (Fundo), Lateral
- Cruza com IV Rank para definir estratégia ótima
"""

from __future__ import annotations

from typing import Any, Optional

from system.ui.logger import get_logger

log = get_logger("sugestoes")

# ============================================================================
# Configurações
# ============================================================================

# Filtros mínimos
MIN_DAYS_TO_EXPIRY = 5
MAX_DAYS_TO_EXPIRY = 180

# Indicadores técnicos - Thresholds
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30
ADX_STRONG = 35
ADX_WEAK = 20
EMA21_STRETCH_THRESHOLD = 0.05  # 5%

# IV Rank thresholds
IV_RANK_HIGH = 50
IV_RANK_LOW = 30

# Bollinger Width para squeeze detection
BB_WIDTH_MINIMAL = 0.02  # 2% - níveis mínimos

# Delta para probabilidade de sucesso
DELTA_MIN_CREDITO = 0.15
DELTA_MAX_CREDITO = 0.30

# ============================================================================
# Mapas de tradução
# ============================================================================

ESTRATEGIA_NOME = {
    "BEAR_CALL_SPREAD": "Trava de Baixa com CALL (Bear Call Spread)",
    "COMPRA_PUT": "Compra de PUT",
    "PUT_SPREAD": "Trava de Baixa com PUT (Put Spread)",
    "VENDA_PUT": "Venda de PUT (Cash Secured Put)",
    "CREDIT_PUT_SPREAD": "Trava de Alta com PUT (Credit Put Spread)",
    "COMPRA_CALL": "Compra de CALL",
    "CALL_SPREAD": "Trava de Alta com CALL (Call Spread)",
    "IRON_CONDOR": "Iron Condor",
    "CALENDARIO": "Trava de Calendário",
    "NENHUMA": "Aguardar melhor oportunidade",
}

CENARIO_NOME = {
    "TOPO": "Esticado no Topo",
    "FUNDO": "Suporte / Fundo",
    "LATERAL": "Lateral (Consolidação)",
}

IV_NIVEL_NOME = {
    "ALTA": "Alta",
    "BAIXA": "Baixa",
}

# ============================================================================
# Helpers de Indicadores Técnicos
# ============================================================================

def classificar_cenario(
    price: float,
    ema9: float,
    ema21: float,
    ema200: float,
    rsi: Optional[float] = None,
    adx: Optional[float] = None,
    bb_upper: Optional[float] = None,
    bb_lower: Optional[float] = None,
    bb_width: Optional[float] = None,
) -> dict[str, Any]:
    """
    Classifica o cenário do ativo conforme ANALISE.md.
    
    Retorna:
        - cenario: "TOPO", "FUNDO", "LATERAL"
        - adx_forte: bool (ADX > 35)
        - adx_fraco: bool (ADX < 20)
        - rsi_sobrecomprado: bool
        - rsi_sobrevendido: bool
        - bb_squeeze: bool (BB Width em mínimas)
        - preco_esticado: bool (preço > 5% da EMA 21)
        - justificativa: str
    """
    # Calcular distância da EMA 21
    distancia_ema21 = abs(price - ema21) / ema21 if ema21 > 0 else 0
    preco_esticado = distancia_ema21 > EMA21_STRETCH_THRESHOLD
    
    # RSI
    rsi_sobrecomprado = rsi is not None and rsi > RSI_OVERBOUGHT
    rsi_sobrevendido = rsi is not None and rsi < RSI_OVERSOLD
    
    # ADX
    adx_forte = adx is not None and adx > ADX_STRONG
    adx_fraco = adx is not None and adx < ADX_WEAK
    
    # Bollinger
    bb_squeeze = bb_width is not None and bb_width < BB_WIDTH_MINIMAL
    tocando_bb_superior = bb_upper is not None and price >= bb_upper
    tocando_bb_inferior = bb_lower is not None and price <= bb_lower
    
    # Classificação do cenário
    cenario = "LATERAL"
    justificativa = ""
    
    # TOPO: Preço >= Banda Superior AND RSI > 70 AND Afastamento da EMA 21
    if tocando_bb_superior and rsi_sobrecomprado and preco_esticado:
        cenario = "TOPO"
        if adx_forte:
            justificativa = (
                f"Ativo esticado no TOPO. Preço tocou banda superior de Bollinger, "
                f"RSI sobrecomprado ({rsi:.1f}), ADX forte ({adx:.1f}). "
                f"Alerta: tendência de exaustão de alta."
            )
        else:
            justificativa = (
                f"Ativo esticado no TOPO. Preço tocou banda superior de Bollinger, "
                f"RSI sobrecomprado ({rsi:.1f}), distância da EMA21: {distancia_ema21*100:.1f}%. "
                f"Expectativa de queda/correção."
            )
    
    # FUNDO: Preço <= Banda Inferior AND RSI < 30 AND Preço abaixo da EMA 21
    elif tocando_bb_inferior and rsi_sobrevendido and price < ema21:
        cenario = "FUNDO"
        if adx_forte:
            justificativa = (
                f"Ativo em SUPORTE/FUNDO. Preço tocou banda inferior de Bollinger, "
                f"RSI sobrevendido ({rsi:.1f}), ADX forte ({adx:.1f}). "
                f"Alerta: tendência de queda acelerada."
            )
        else:
            justificativa = (
                f"Ativo em SUPORTE/FUNDO. Preço tocou banda inferior de Bollinger, "
                f"RSI sobrevendido ({rsi:.1f}), abaixo da EMA21. "
                f"Expectativa de repique/alta."
            )
    
    # LATERAL: ADX < 20 AND Preço entre Bandas
    elif adx_fraco and not tocando_bb_superior and not tocando_bb_inferior:
        cenario = "LATERAL"
        if bb_squeeze:
            justificativa = (
                f"Mercado LATERAL. ADX fraco ({adx:.1f}), BB Width em mínimas "
                f"({bb_width*100:.2f}%). Atenção: risco de explosão (squeeze). "
                f"Aguardar rompimento."
            )
        else:
            justificativa = (
                f"Mercado LATERAL. ADX fraco ({adx:.1f}), preço oscilando entre "
                f"Bandas de Bollinger. Consolidação em andamento."
            )
    
    # Fallback: verificar tendência
    elif price > ema200 and ema9 > ema21:
        cenario = "TOPO" if rsi_sobrecomprado else "LATERAL"
        justificativa = f"Tendência de alta identificada. RSI: {rsi}, ADX: {adx}."
    elif price < ema200 and ema9 < ema21:
        cenario = "FUNDO" if rsi_sobrevendido else "LATERAL"
        justificativa = f"Tendência de baixa identificada. RSI: {rsi}, ADX: {adx}."
    else:
        justificativa = "Sem configuração clara. Monitorar indicadores."
    
    return {
        "cenario": cenario,
        "adx_forte": adx_forte,
        "adx_fraco": adx_fraco,
        "rsi_sobrecomprado": rsi_sobrecomprado,
        "rsi_sobrevendido": rsi_sobrevendido,
        "bb_squeeze": bb_squeeze,
        "preco_esticado": preco_esticado,
        "distancia_ema21_pct": round(distancia_ema21 * 100, 1),
        "justificativa": justificativa,
    }


def classificar_iv(iv_rank: Optional[float] = None, vi: Optional[float] = None) -> str:
    """Classifica nível da volatilidade implícita."""
    if iv_rank is not None:
        if iv_rank > IV_RANK_HIGH:
            return "ALTA"
        elif iv_rank < IV_RANK_LOW:
            return "BAIXA"
    # Fallback: usar VI absoluta
    if vi is not None:
        if vi > 40:
            return "ALTA"
        elif vi < 25:
            return "BAIXA"
    return "BAIXA"  # Default conservador


def decidir_estrategia(
    cenario: str,
    iv_nivel: str,
    adx_forte: bool = False,
    bb_squeeze: bool = False,
) -> dict[str, Any]:
    """
    Decide estratégia conforme matriz do ANALISE.md.
    
    Regras:
    - TOPO + IV ALTA → Bear Call Spread
    - TOPO + IV BAIXA → Compra de PUT
    - FUNDO + IV ALTA → Venda de PUT
    - FUNDO + IV BAIXA → Compra de CALL
    - LATERAL + IV ALTA → Iron Condor
    - LATERAL + IV BAIXA → Calendário
    
    Filtros de segurança:
    - Anti-Squeeze: não vender vol se BB Width em mínimas
    - ADX > 35: priorizar estruturas de DÉBITO
    """
    estrategia = "NENHUMA"
    justificativa = ""
    
    # Filtro Anti-Squeeze
    if bb_squeeze and iv_nivel == "ALTA":
        return {
            "estrategia": "NENHUMA",
            "justificativa": (
                "FILTRO ANTI-SQUEEZE: BB Width em níveis mínimos. "
                "Risco de explosão de volatilidade. Não operar venda de volatilidade."
            ),
        }
    
    # TOPO
    if cenario == "TOPO":
        if iv_nivel == "ALTA":
            # Bear Call Spread - vende prêmios caros
            estrategia = "BEAR_CALL_SPREAD"
            justificativa = (
                "Topo + IV Alta: Bear Call Spread (Trava de Baixa com CALL). "
                "Vende-se prêmios caros; lucra com queda do ativo e IV Crush."
            )
        else:
            # Compra de PUT - opções baratas
            if adx_forte:
                estrategia = "PUT_SPREAD"
                justificativa = (
                    "Topo + IV Baixa + ADX Forte: Put Spread (Trava de Baixa). "
                    "Estrutura de débito priorizada; ADX forte indica tendência que pode continuar."
                )
            else:
                estrategia = "COMPRA_PUT"
                justificativa = (
                    "Topo + IV Baixa: Compra de PUT. "
                    "Opções baratas (Vega Positivo); lucra com queda e aumento do medo (IV)."
                )
    
    # FUNDO
    elif cenario == "FUNDO":
        if iv_nivel == "ALTA":
            # Venda de PUT - recebe prêmio elevado
            if adx_forte:
                estrategia = "CREDIT_PUT_SPREAD"
                justificativa = (
                    "Fundo + IV Alta + ADX Forte: Credit Put Spread (Trava de Alta com PUT). "
                    "Proteção com compra de put mais abaixo; ADX forte indica risco de continuidade da queda."
                )
            else:
                estrategia = "VENDA_PUT"
                justificativa = (
                    "Fundo + IV Alta: Venda de PUT (Cash Secured Put). "
                    "Recebe prêmio elevado; alta margem de segurança e ganho na retração da IV."
                )
        else:
            # Compra de CALL - baixo custo
            estrategia = "COMPRA_CALL"
            justificativa = (
                "Fundo + IV Baixa: Compra de CALL. "
                "Baixo custo de entrada e risco limitado para capturar retomada."
            )
    
    # LATERAL
    elif cenario == "LATERAL":
        if iv_nivel == "ALTA":
            estrategia = "IRON_CONDOR"
            justificativa = (
                "Lateral + IV Alta: Iron Condor. "
                "Venda de volatilidade em ambos os lados; lucro máximo com passagem do tempo (Theta)."
            )
        else:
            estrategia = "CALENDARIO"
            justificativa = (
                "Lateral + IV Baixa: Trava de Calendário. "
                "Beneficia-se da baixa IV esperando expansão futura; ganho no diferencial de Theta."
            )
    
    return {
        "estrategia": estrategia,
        "justificativa": justificativa,
    }


# ============================================================================
# Helpers de Opções
# ============================================================================

def _liquidez_score(texto: str) -> int:
    """Retorna score de liquidez baseado no texto."""
    if not texto:
        return 0
    texto_lower = texto.lower()
    
    if "alta" in texto_lower and "baixa" not in texto_lower and "nenhuma" not in texto_lower:
        return 100
    if "muitobo" in texto_lower or "muito boa" in texto_lower:
        return 80
    if texto_lower.startswith("boa") or "liquidez boa" in texto_lower:
        return 60
    if "media" in texto_lower or "média" in texto_lower or "razoavel" in texto_lower:
        return 40
    if "baixiss" in texto_lower:
        return 10
    if "baixa" in texto_lower and "nenhuma" not in texto_lower:
        return 20
    if "nenhuma" in texto_lower or "nenhum" in texto_lower:
        return 0
    
    return 0


def _meio_preco(bid: float, ask: float) -> float:
    return (bid + ask) / 2.0


def _preco_opcao(opt: dict) -> float:
    """Obtém preço da opção: último negócio > bid > ask > 0."""
    ultimo = opt.get("ultimo_preco", 0) or 0
    if ultimo > 0:
        return ultimo
    bid = opt.get("bid", 0) or 0
    ask = opt.get("ask", 0) or 0
    if bid > 0 and ask > 0:
        return _meio_preco(bid, ask)
    return 0


def _filtro_opcoes(options: list[dict]) -> list[dict]:
    """Filtra opções com strike válido e VI > 0."""
    filtradas = []
    for opt in options:
        strike = opt.get("strike", 0) or 0
        if strike <= 0:
            continue
        vi = opt.get("vi", 0) or 0
        if vi <= 0:
            ultimo = opt.get("ultimo_preco", 0) or 0
            bid = opt.get("bid", 0) or 0
            ask = opt.get("ask", 0) or 0
            if ultimo <= 0 and bid <= 0 and ask <= 0:
                continue
        filtradas.append(opt)
    return filtradas


def _agrupar_por_serie(options: list[dict]) -> dict[str, list[dict]]:
    series = {}
    for opt in options:
        serie = opt.get("serie", "desconhecido")
        if serie not in series:
            series[serie] = []
        series[serie].append(opt)
    return series


# ============================================================================
# Estratégias - Cálculo de métricas
# ============================================================================

def _calcular_bear_call_spread(call_venda: dict, call_compra: dict, preco_base: float) -> dict[str, Any]:
    """Bear Call Spread (Trava de Baixa com CALL)."""
    premio_venda = _preco_opcao(call_venda)
    premio_compra = _preco_opcao(call_compra)
    k_venda = call_venda.get("strike", 0)
    k_compra = call_compra.get("strike", 0)
    
    credito = premio_venda - premio_compra
    lucro_max = credito
    perda_max = (k_compra - k_venda) - credito
    break_even = k_venda + credito
    retorno = (lucro_max / perda_max * 100) if perda_max > 0 else 0
    
    # Score: crédito positivo, delta na faixa, liquidez
    score = 0
    if credito > 0: score += 30
    delta_venda = abs(call_venda.get("delta", 0) or 0)
    if DELTA_MIN_CREDITO <= delta_venda <= DELTA_MAX_CREDITO:
        score += 25
    score += _liquidez_score(call_venda.get("liquidez_texto", "")) / 5
    score += _liquidez_score(call_compra.get("liquidez_texto", "")) / 5
    
    return {
        "tipo": ESTRATEGIA_NOME["BEAR_CALL_SPREAD"],
        "perna_venda": {"simbolo": call_venda.get("simbolo", ""), "strike": k_venda, "premio": round(premio_venda, 2), "delta": call_venda.get("delta"), "vi": call_venda.get("vi"), "moneyness": call_venda.get("moneyness", "")},
        "perna_compra": {"simbolo": call_compra.get("simbolo", ""), "strike": k_compra, "premio": round(premio_compra, 2), "delta": call_compra.get("delta"), "vi": call_compra.get("vi"), "moneyness": call_compra.get("moneyness", "")},
        "serie": call_venda.get("serie", ""),
        "dias_vencimento": call_venda.get("dias_vencimento", 0),
        "credito": round(credito, 2),
        "lucro_max": round(lucro_max, 2),
        "perda_max": round(perda_max, 2),
        "break_even": round(break_even, 2),
        "retorno_pct": round(retorno, 1),
        "score": round(score, 1),
    }


def _calcular_compra_put(put: dict, preco_base: float) -> dict[str, Any]:
    """Compra de PUT."""
    premio = _preco_opcao(put)
    strike = put.get("strike", 0)
    delta = put.get("delta", 0) or 0
    vi = put.get("vi", 0) or 0
    poe = put.get("poe", 0) or 0
    
    score = 0
    if vi < 30: score += 30  # IV baixa = bom para compra
    if poe < 30: score += 20  # Probabilidade ITM baixa
    score += _liquidez_score(put.get("liquidez_texto", "")) / 5
    
    dist_otm = ((preco_base - strike) / preco_base * 100) if preco_base > 0 else 0
    
    return {
        "tipo": ESTRATEGIA_NOME["COMPRA_PUT"],
        "simbolo": put.get("simbolo", ""),
        "strike": strike,
        "premio": round(premio, 2),
        "delta": delta,
        "vi": vi,
        "moneyness": put.get("moneyness", ""),
        "poe": poe,
        "serie": put.get("serie", ""),
        "dias_vencimento": put.get("dias_vencimento", 0),
        "distancia_otm_pct": round(dist_otm, 1),
        "score": round(score, 1),
    }


def _calcular_put_spread(put_compra: dict, put_venda: dict, preco_base: float) -> dict[str, Any]:
    """Put Spread (Trava de Baixa com PUT)."""
    premio_compra = _preco_opcao(put_compra)
    premio_venda = _preco_opcao(put_venda)
    k_compra = put_compra.get("strike", 0)
    k_venda = put_venda.get("strike", 0)
    
    debito = premio_compra - premio_venda
    lucro_max = (k_compra - k_venda) - debito
    perda_max = debito
    break_even = k_compra - debito
    retorno = (lucro_max / perda_max * 100) if perda_max > 0 else 0
    
    score = 0
    if retorno > 100: score += 30
    elif retorno > 50: score += 20
    score += _liquidez_score(put_compra.get("liquidez_texto", "")) / 5
    score += _liquidez_score(put_venda.get("liquidez_texto", "")) / 5
    
    return {
        "tipo": ESTRATEGIA_NOME["PUT_SPREAD"],
        "perna_compra": {"simbolo": put_compra.get("simbolo", ""), "strike": k_compra, "premio": round(premio_compra, 2), "delta": put_compra.get("delta"), "vi": put_compra.get("vi"), "moneyness": put_compra.get("moneyness", "")},
        "perna_venda": {"simbolo": put_venda.get("simbolo", ""), "strike": k_venda, "premio": round(premio_venda, 2), "delta": put_venda.get("delta"), "vi": put_venda.get("vi"), "moneyness": put_venda.get("moneyness", "")},
        "serie": put_compra.get("serie", ""),
        "dias_vencimento": put_compra.get("dias_vencimento", 0),
        "debito": round(debito, 2),
        "lucro_max": round(lucro_max, 2),
        "perda_max": round(perda_max, 2),
        "break_even": round(break_even, 2),
        "retorno_pct": round(retorno, 1),
        "score": round(score, 1),
    }


def _calcular_venda_put(put: dict, preco_base: float) -> dict[str, Any]:
    """Venda de PUT (Cash Secured Put)."""
    premio = _preco_opcao(put)
    strike = put.get("strike", 0)
    delta = put.get("delta", 0) or 0
    vi = put.get("vi", 0) or 0
    poe = put.get("poe", 0) or 0
    
    score = 0
    if vi > 40: score += 30  # IV alta = bom para venda
    delta_abs = abs(delta)
    if DELTA_MIN_CREDITO <= delta_abs <= DELTA_MAX_CREDITO:
        score += 25
    if poe < 30: score += 20
    score += _liquidez_score(put.get("liquidez_texto", "")) / 5
    
    dist_otm = ((preco_base - strike) / preco_base * 100) if preco_base > 0 else 0
    
    return {
        "tipo": ESTRATEGIA_NOME["VENDA_PUT"],
        "simbolo": put.get("simbolo", ""),
        "strike": strike,
        "premio": round(premio, 2),
        "delta": delta,
        "vi": vi,
        "moneyness": put.get("moneyness", ""),
        "poe": poe,
        "serie": put.get("serie", ""),
        "dias_vencimento": put.get("dias_vencimento", 0),
        "distancia_otm_pct": round(dist_otm, 1),
        "score": round(score, 1),
    }


def _calcular_credit_put_spread(put_venda: dict, put_compra: dict, preco_base: float) -> dict[str, Any]:
    """Credit Put Spread (Trava de Alta com PUT)."""
    premio_venda = _preco_opcao(put_venda)
    premio_compra = _preco_opcao(put_compra)
    k_venda = put_venda.get("strike", 0)
    k_compra = put_compra.get("strike", 0)
    
    credito = premio_venda - premio_compra
    lucro_max = credito
    perda_max = (k_venda - k_compra) - credito
    break_even = k_venda - credito
    retorno = (lucro_max / perda_max * 100) if perda_max > 0 else 0
    
    score = 0
    if credito > 0: score += 30
    delta_venda = abs(put_venda.get("delta", 0) or 0)
    if DELTA_MIN_CREDITO <= delta_venda <= DELTA_MAX_CREDITO:
        score += 25
    score += _liquidez_score(put_venda.get("liquidez_texto", "")) / 5
    score += _liquidez_score(put_compra.get("liquidez_texto", "")) / 5
    
    return {
        "tipo": ESTRATEGIA_NOME["CREDIT_PUT_SPREAD"],
        "perna_venda": {"simbolo": put_venda.get("simbolo", ""), "strike": k_venda, "premio": round(premio_venda, 2), "delta": put_venda.get("delta"), "vi": put_venda.get("vi"), "moneyness": put_venda.get("moneyness", "")},
        "perna_compra": {"simbolo": put_compra.get("simbolo", ""), "strike": k_compra, "premio": round(premio_compra, 2), "delta": put_compra.get("delta"), "vi": put_compra.get("vi"), "moneyness": put_compra.get("moneyness", "")},
        "serie": put_venda.get("serie", ""),
        "dias_vencimento": put_venda.get("dias_vencimento", 0),
        "credito": round(credito, 2),
        "lucro_max": round(lucro_max, 2),
        "perda_max": round(perda_max, 2),
        "break_even": round(break_even, 2),
        "retorno_pct": round(retorno, 1),
        "score": round(score, 1),
    }


def _calcular_compra_call(call: dict, preco_base: float) -> dict[str, Any]:
    """Compra de CALL."""
    premio = _preco_opcao(call)
    strike = call.get("strike", 0)
    delta = call.get("delta", 0) or 0
    vi = call.get("vi", 0) or 0
    poe = call.get("poe", 0) or 0
    
    score = 0
    if vi < 30: score += 30  # IV baixa = bom para compra
    if poe < 30: score += 20
    score += _liquidez_score(call.get("liquidez_texto", "")) / 5
    
    dist_otm = ((strike - preco_base) / preco_base * 100) if preco_base > 0 else 0
    
    return {
        "tipo": ESTRATEGIA_NOME["COMPRA_CALL"],
        "simbolo": call.get("simbolo", ""),
        "strike": strike,
        "premio": round(premio, 2),
        "delta": delta,
        "vi": vi,
        "moneyness": call.get("moneyness", ""),
        "poe": poe,
        "serie": call.get("serie", ""),
        "dias_vencimento": call.get("dias_vencimento", 0),
        "distancia_otm_pct": round(dist_otm, 1),
        "score": round(score, 1),
    }


def _calcular_iron_condor(
    put_venda: dict, put_compra: dict,
    call_venda: dict, call_compra: dict,
    preco_base: float
) -> dict[str, Any]:
    """Iron Condor."""
    pv_put = _preco_opcao(put_venda)
    pc_put = _preco_opcao(put_compra)
    pv_call = _preco_opcao(call_venda)
    pc_call = _preco_opcao(call_compra)
    
    credito = (pv_put + pv_call) - (pc_put + pc_call)
    k_put_venda = put_venda.get("strike", 0)
    k_put_compra = put_compra.get("strike", 0)
    k_call_venda = call_venda.get("strike", 0)
    k_call_compra = call_compra.get("strike", 0)
    
    risco_put = k_put_venda - k_put_compra
    risco_call = k_call_compra - k_call_venda
    perda_max = max(risco_put, risco_call) - credito
    lucro_max = credito
    retorno = (lucro_max / perda_max * 100) if perda_max > 0 else 0
    
    score = 0
    if credito > 0: score += 30
    score += _liquidez_score(put_venda.get("liquidez_texto", "")) / 5
    score += _liquidez_score(call_venda.get("liquidez_texto", "")) / 5
    
    return {
        "tipo": ESTRATEGIA_NOME["IRON_CONDOR"],
        "put_venda": {"simbolo": put_venda.get("simbolo", ""), "strike": k_put_venda, "premio": round(pv_put, 2)},
        "put_compra": {"simbolo": put_compra.get("simbolo", ""), "strike": k_put_compra, "premio": round(pc_put, 2)},
        "call_venda": {"simbolo": call_venda.get("simbolo", ""), "strike": k_call_venda, "premio": round(pv_call, 2)},
        "call_compra": {"simbolo": call_compra.get("simbolo", ""), "strike": k_call_compra, "premio": round(pc_call, 2)},
        "serie": put_venda.get("serie", ""),
        "dias_vencimento": put_venda.get("dias_vencimento", 0),
        "credito": round(credito, 2),
        "lucro_max": round(lucro_max, 2),
        "perda_max": round(perda_max, 2),
        "retorno_pct": round(retorno, 1),
        "score": round(score, 1),
    }


# ============================================================================
# Busca de melhores combinações
# ============================================================================

def _buscar_bear_call_spread(series: dict[str, dict], preco_base: float, max_sugestoes: int = 3) -> list[dict]:
    sugestoes = []
    for serie_nome, dados in series.items():
        calls = dados["calls"]
        for i, call_venda in enumerate(calls):
            k_venda = call_venda.get("strike", 0)
            if k_venda < preco_base * 1.00 or k_venda > preco_base * 1.08:
                continue
            for call_compra in calls[i+1:]:
                k_compra = call_compra.get("strike", 0)
                if k_compra <= k_venda or k_compra > k_venda * 1.10:
                    continue
                sugestoes.append(_calcular_bear_call_spread(call_venda, call_compra, preco_base))
    sugestoes.sort(key=lambda x: x["score"], reverse=True)
    return sugestoes[:max_sugestoes]


def _buscar_compra_put(series: dict[str, dict], preco_base: float, max_sugestoes: int = 3) -> list[dict]:
    sugestoes = []
    for serie_nome, dados in series.items():
        for put in dados["puts"]:
            strike = put.get("strike", 0)
            if strike < preco_base * 0.90 or strike > preco_base * 1.00:
                continue
            sugestoes.append(_calcular_compra_put(put, preco_base))
    sugestoes.sort(key=lambda x: x["score"], reverse=True)
    return sugestoes[:max_sugestoes]


def _buscar_put_spread(series: dict[str, dict], preco_base: float, max_sugestoes: int = 3) -> list[dict]:
    sugestoes = []
    for serie_nome, dados in series.items():
        puts = dados["puts"]
        for i, put_compra in enumerate(puts):
            k_compra = put_compra.get("strike", 0)
            if k_compra < preco_base * 0.95 or k_compra > preco_base * 1.05:
                continue
            for put_venda in puts[:i]:
                k_venda = put_venda.get("strike", 0)
                if k_venda < k_compra * 0.90 or k_venda >= k_compra:
                    continue
                sugestoes.append(_calcular_put_spread(put_compra, put_venda, preco_base))
    sugestoes.sort(key=lambda x: x["score"], reverse=True)
    return sugestoes[:max_sugestoes]


def _buscar_venda_put(series: dict[str, dict], preco_base: float, max_sugestoes: int = 3) -> list[dict]:
    sugestoes = []
    for serie_nome, dados in series.items():
        for put in dados["puts"]:
            strike = put.get("strike", 0)
            if strike < preco_base * 0.85 or strike > preco_base * 0.98:
                continue
            sugestoes.append(_calcular_venda_put(put, preco_base))
    sugestoes.sort(key=lambda x: x["score"], reverse=True)
    return sugestoes[:max_sugestoes]


def _buscar_credit_put_spread(series: dict[str, dict], preco_base: float, max_sugestoes: int = 3) -> list[dict]:
    sugestoes = []
    for serie_nome, dados in series.items():
        puts = dados["puts"]
        for i, put_venda in enumerate(puts):
            k_venda = put_venda.get("strike", 0)
            if k_venda < preco_base * 0.85 or k_venda > preco_base * 0.98:
                continue
            for put_compra in puts[:i]:
                k_compra = put_compra.get("strike", 0)
                if k_compra < k_venda * 0.85 or k_compra >= k_venda:
                    continue
                sugestoes.append(_calcular_credit_put_spread(put_venda, put_compra, preco_base))
    sugestoes.sort(key=lambda x: x["score"], reverse=True)
    return sugestoes[:max_sugestoes]


def _buscar_compra_call(series: dict[str, dict], preco_base: float, max_sugestoes: int = 3) -> list[dict]:
    sugestoes = []
    for serie_nome, dados in series.items():
        for call in dados["calls"]:
            strike = call.get("strike", 0)
            if strike < preco_base * 1.02 or strike > preco_base * 1.15:
                continue
            sugestoes.append(_calcular_compra_call(call, preco_base))
    sugestoes.sort(key=lambda x: x["score"], reverse=True)
    return sugestoes[:max_sugestoes]


def _buscar_iron_condor(series: dict[str, dict], preco_base: float, max_sugestoes: int = 3) -> list[dict]:
    sugestoes = []
    for serie_nome, dados in series.items():
        puts = dados["puts"]
        calls = dados["calls"]
        
        # Encontrar put venda OTM
        for put_venda in puts:
            k_put_v = put_venda.get("strike", 0)
            if k_put_v < preco_base * 0.90 or k_put_v > preco_base * 0.97:
                continue
            # Put compra mais abaixo
            for put_compra in puts:
                k_put_c = put_compra.get("strike", 0)
                if k_put_c >= k_put_v or k_put_c < k_put_v * 0.90:
                    continue
                
                # Call venda OTM
                for call_venda in calls:
                    k_call_v = call_venda.get("strike", 0)
                    if k_call_v < preco_base * 1.03 or k_call_v > preco_base * 1.10:
                        continue
                    # Call compra mais acima
                    for call_compra in calls:
                        k_call_c = call_compra.get("strike", 0)
                        if k_call_c <= k_call_v or k_call_c > k_call_v * 1.10:
                            continue
                        
                        sugestoes.append(_calcular_iron_condor(
                            put_venda, put_compra, call_venda, call_compra, preco_base
                        ))
                        if len(sugestoes) >= max_sugestoes * 3:
                            break
                    if len(sugestoes) >= max_sugestoes * 3:
                        break
                if len(sugestoes) >= max_sugestoes * 3:
                    break
            if len(sugestoes) >= max_sugestoes * 3:
                break
    
    sugestoes.sort(key=lambda x: x["score"], reverse=True)
    return sugestoes[:max_sugestoes]


# ============================================================================
# Função principal
# ============================================================================

ESTRATEGIAS_DISPONIVEIS = [
    ("auto", "Análise Automática (por indicadores)"),
    ("bear_call_spread", "Trava de Baixa com CALL"),
    ("compra_put", "Compra de PUT"),
    ("put_spread", "Trava de Baixa com PUT"),
    ("venda_put", "Venda de PUT"),
    ("credit_put_spread", "Trava de Alta com PUT"),
    ("compra_call", "Compra de CALL"),
    ("iron_condor", "Iron Condor"),
]


def analisar_sugestoes(
    ticker: str,
    options: list[dict],
    preco_atual: float,
    estrategia: str = "auto",
    vencimento_dias_min: int = MIN_DAYS_TO_EXPIRY,
    vencimento_dias_max: int = MAX_DAYS_TO_EXPIRY,
    indicadores: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    Analisa opções e sugere estruturas baseado na matriz ANALISE.md.
    
    Args:
        ticker: Ticker do ativo
        options: Lista de opções disponíveis
        preco_atual: Preço atual do ativo
        estrategia: Tipo de estratégia
        vencimento_dias_min/max: Faixa de dias até vencimento
        indicadores: Indicadores técnicos do Yahoo Finance
    """
    resultado = {
        "ticker": ticker.upper(),
        "preco_atual": preco_atual,
        "timestamp": None,
        "cenario": {},
        "iv_nivel": "",
        "estrategia_sugerida": "",
        "sugestoes": [],
        "observacoes": "",
    }
    
    from datetime import datetime
    resultado["timestamp"] = datetime.now().strftime("%d/%m/%Y %H:%M")
    
    if indicadores is None:
        indicadores = {}
    indicadores["price"] = preco_atual
    
    # Classificar cenário
    cenario = classificar_cenario(
        price=preco_atual,
        ema9=indicadores.get("ema9", 0),
        ema21=indicadores.get("ema21", 0),
        ema200=indicadores.get("ema200", 0),
        rsi=indicadores.get("rsi"),
        adx=indicadores.get("adx"),
        bb_upper=indicadores.get("bb_upper"),
        bb_lower=indicadores.get("bb_lower"),
        bb_width=indicadores.get("bb_width"),
    )
    resultado["cenario"] = cenario
    
    # Classificar IV
    iv_rank = indicadores.get("iv_rank")
    vi_media = indicadores.get("vi_media")
    iv_nivel = classificar_iv(iv_rank, vi_media)
    resultado["iv_nivel"] = IV_NIVEL_NOME.get(iv_nivel, iv_nivel)
    
    # Decidir estratégia
    decisao = decidir_estrategia(
        cenario=cenario["cenario"],
        iv_nivel=iv_nivel,
        adx_forte=cenario["adx_forte"],
        bb_squeeze=cenario["bb_squeeze"],
    )
    resultado["estrategia_sugerida"] = ESTRATEGIA_NOME.get(decisao["estrategia"], decisao["estrategia"])
    resultado["observacoes"] = decisao["justificativa"]
    
    # Filtrar e agrupar opções
    options_filtradas = _filtro_opcoes(options)
    if len(options_filtradas) < 4:
        resultado["observacoes"] += f" Poucas opções disponíveis: {len(options_filtradas)}."
        return resultado
    
    series_brutas = _agrupar_por_serie(options_filtradas)
    series_filtradas = {}
    for s, opts in series_brutas.items():
        dias = opts[0].get("dias_vencimento", 0) if opts else 0
        if vencimento_dias_min <= dias <= vencimento_dias_max:
            series_filtradas[s] = opts
    
    series = {}
    for s, opts in series_filtradas.items():
        calls = sorted([o for o in opts if o.get("tipo") == "CALL"], key=lambda x: x.get("strike", 0))
        puts = sorted([o for o in opts if o.get("tipo") == "PUT"], key=lambda x: x.get("strike", 0))
        if calls and puts:
            series[s] = {"calls": calls, "puts": puts, "dias": opts[0].get("dias_vencimento", 0)}
    
    if not series:
        resultado["observacoes"] += " Não há séries completas com CALLs e PUTs."
        return resultado
    
    # Buscar sugestões conforme estratégia
    estrategia_map = {
        "BEAR_CALL_SPREAD": lambda: _buscar_bear_call_spread(series, preco_atual),
        "COMPRA_PUT": lambda: _buscar_compra_put(series, preco_atual),
        "PUT_SPREAD": lambda: _buscar_put_spread(series, preco_atual),
        "VENDA_PUT": lambda: _buscar_venda_put(series, preco_atual),
        "CREDIT_PUT_SPREAD": lambda: _buscar_credit_put_spread(series, preco_atual),
        "COMPRA_CALL": lambda: _buscar_compra_call(series, preco_atual),
        "IRON_CONDOR": lambda: _buscar_iron_condor(series, preco_atual),
    }
    
    sugestoes = []
    if estrategia == "auto":
        estrat_key = decisao["estrategia"]
        if estrat_key in estrategia_map:
            sugestoes = estrategia_map[estrat_key]()
        
        # Se nao encontrou sugestoes para a estrategia, tentar alternativas
        if not sugestoes:
            # Fallback: buscar venda put e bear call spread
            sugestoes = (
                _buscar_venda_put(series, preco_atual) +
                _buscar_bear_call_spread(series, preco_atual) +
                _buscar_compra_call(series, preco_atual) +
                _buscar_compra_put(series, preco_atual)
            )
            sugestoes.sort(key=lambda x: x.get("score", 0), reverse=True)
            if sugestoes:
                resultado["observacoes"] += f" (Estrategia original '{ESTRATEGIA_NOME.get(estrat_key, estrat_key)}' nao disponivel, alternativas sugeridas.)"
    elif estrategia in estrategia_map:
        sugestoes = estrategia_map[estrategia]()
    
    resultado["sugestoes"] = sugestoes
    
    if not sugestoes and decisao["estrategia"] != "NENHUMA":
        resultado["observacoes"] += " Nenhuma combinação adequada encontrada."
    
    return resultado
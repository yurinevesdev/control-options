"""
Yuri System — Módulo de Sugestão de Estruturas de Opções.

Analisa dados de opções disponíveis e sugere as melhores combinações
para diferentes estratégias (travas, spreads, etc.).

Usa indicadores técnicos (EMA, RSI, ADX, MACD, Bollinger) para
classificar tendência, exaustão, volatilidade e momentum.
"""

from __future__ import annotations

import math
from typing import Any, Optional

from eagle.logger import get_logger

log = get_logger("sugestoes")

# ============================================================================
# Configurações
# ============================================================================

# Filtros mínimos de qualidade
LIQUIDEZ_MIN = "Razoavel"
MAX_BID_ASK_DIFF_PCT = 15
MIN_DAYS_TO_EXPIRY = 5
MAX_IV_RANK = 80

# Indicadores técnicos - Thresholds
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30
ADX_STRONG = 25
ADX_WEAK = 20
EMA21_STRETCH_THRESHOLD = 0.05  # 5%

# Thresholds de volatilidade (bbWidth) - podem ser ajustados dinamicamente
BB_WIDTH_LOW_THRESHOLD = 0.02   # 2%
BB_WIDTH_HIGH_THRESHOLD = 0.06  # 6%

# Pesos para scoring
SCORE_LIQUIDEZ = {
    "Alta": 100,
    "MuitoBoa": 80,
    "Boa": 60,
    "Razoavel": 40,
    "Media": 40,       # Liquidez média
    "Media liquidez": 40,
    "Baixa": 20,
    "Baixa liquidez": 20,
    "MuitoBaixa": 10,
    "Baixissima liquidez": 10,
    "Nenhuma liquidez": 0,
    "Nenhuma": 0,
    "": 0,
}

# ============================================================================
# Helpers de Indicadores Técnicos
# ============================================================================

def classificar_tendencia(
    price: float,
    ema9: float,
    ema21: float,
    ema200: float,
    adx: Optional[float] = None,
) -> dict[str, Any]:
    """
    Classifica tendência do mercado.
    
    Retorna:
        - direcao: "UP", "DOWN", "SIDEWAYS"
        - forca: "STRONG", "WEAK", "MODERATE"
        - adx_level: valor do ADX ou None
    """
    if price > ema200 and ema9 > ema21:
        direcao = "UP"
    elif price < ema200 and ema9 < ema21:
        direcao = "DOWN"
    else:
        direcao = "SIDEWAYS"
    
    if adx is not None:
        if adx >= ADX_STRONG:
            forca = "STRONG"
        elif adx < ADX_WEAK:
            forca = "WEAK"
        else:
            forca = "MODERATE"
    else:
        forca = "MODERATE"
    
    return {
        "direcao": direcao,
        "forca": forca,
        "adx_level": adx,
    }


def identificar_exaustao(
    price: float,
    rsi: Optional[float] = None,
    bb_upper: Optional[float] = None,
    bb_lower: Optional[float] = None,
) -> dict[str, Any]:
    """Identifica exaustão de movimento (sobrecompra/sobrevenda)."""
    sobrecomprado = False
    sobrevendido = False
    
    if rsi is not None:
        if rsi > RSI_OVERBOUGHT:
            sobrecomprado = True
        elif rsi < RSI_OVERSOLD:
            sobrevendido = True
    
    if bb_upper is not None and bb_lower is not None:
        if price >= bb_upper:
            sobrecomprado = True
        elif price <= bb_lower:
            sobrevendido = True
    
    return {
        "sobrecomprado": sobrecomprado,
        "sobrevendido": sobrevendido,
        "rsi": rsi,
    }


def classificar_volatilidade(
    bb_width: Optional[float] = None,
    threshold_low: float = BB_WIDTH_LOW_THRESHOLD,
    threshold_high: float = BB_WIDTH_HIGH_THRESHOLD,
) -> str:
    """Classifica volatilidade com base na largura das bandas de Bollinger."""
    if bb_width is None:
        return "MODERATE"
    if bb_width < threshold_low:
        return "LOW"
    elif bb_width > threshold_high:
        return "HIGH"
    return "MODERATE"


def identificar_momentum(
    macd: Optional[float] = None,
    macd_signal: Optional[float] = None,
) -> str:
    """Identifica momentum pelo MACD."""
    if macd is None or macd_signal is None:
        return "NEUTRAL"
    if macd > macd_signal:
        return "BULLISH"
    elif macd < macd_signal:
        return "BEARISH"
    return "NEUTRAL"


def calcular_distancia_ema21(price: float, ema21: float) -> float:
    """Calcula distância do preço em relação à EMA 21 (em %)."""
    if ema21 <= 0:
        return 0.0
    return abs(price - ema21) / ema21


def ativo_esticado(
    price: float,
    ema21: float,
    threshold: float = EMA21_STRETCH_THRESHOLD,
) -> bool:
    """Verifica se o ativo está 'esticado' (>5% da EMA 21)."""
    return calcular_distancia_ema21(price, ema21) > threshold


# Mapas de tradução para exibição
ESTRATEGIA_NOME = {
    "BULL_SPREAD": "Trava de Alta",
    "BEAR_SPREAD": "Trava de Baixa",
    "SELL_PUT": "Venda de PUT",
    "SELL_CALL": "Venda de CALL",
    "THL": "Operação Lateral (THL)",
    "NO_TRADE": "Não Operar",
}

TENDENCIA_NOME = {
    "UP": "Alta",
    "DOWN": "Baixa",
    "SIDEWAYS": "Lateral",
}

FORCA_NOME = {
    "STRONG": "Forte",
    "MODERATE": "Moderada",
    "WEAK": "Fraca",
}

VOLATILIDADE_NOME = {
    "LOW": "Baixa",
    "MODERATE": "Moderada",
    "HIGH": "Alta",
}

MOMENTUM_NOME = {
    "BULLISH": "Alta (Comprador)",
    "BEARISH": "Baixa (Vendedor)",
    "NEUTRAL": "Neutro",
}


def _traduzir_resultado(decisao: dict[str, Any]) -> dict[str, Any]:
    """Traduz os valores internos para exibição em português."""
    return {
        "tendencia": TENDENCIA_NOME.get(decisao["tendencia"], decisao["tendencia"]),
        "tendencia_forca": FORCA_NOME.get(decisao["tendencia_forca"], decisao["tendencia_forca"]),
        "sobrecomprado": decisao["sobrecomprado"],
        "sobrevendido": decisao["sobrevendido"],
        "volatilidade": VOLATILIDADE_NOME.get(decisao["volatilidade"], decisao["volatilidade"]),
        "momentum": MOMENTUM_NOME.get(decisao["momentum"], decisao["momentum"]),
        "ativo_esticado": decisao["ativo_esticado"],
        "estrategia_sugerida": ESTRATEGIA_NOME.get(decisao["estrategia_sugerida"], decisao["estrategia_sugerida"]),
        "scores": decisao["scores"],
        "justificativa": decisao["justificativa"],
        "indicadores": decisao["indicadores"],
    }


# ============================================================================
# Motor de Decisão
# ============================================================================

def decidir_estrategia(
    indicadores: dict[str, Any],
) -> dict[str, Any]:
    """
    Motor de decisão baseado nos indicadores técnicos.
    
    Entrada esperada:
        - price: Preço atual
        - ema9, ema21, ema200: Médias móveis exponenciais
        - rsi: RSI (14 períodos)
        - adx: ADX
        - macd, macd_signal: MACD e sua linha de sinal
        - bb_upper, bb_lower, bb_width: Bandas de Bollinger
    """
    price = indicadores.get("price", 0)
    ema9 = indicadores.get("ema9", 0)
    ema21 = indicadores.get("ema21", 0)
    ema200 = indicadores.get("ema200", 0)
    rsi = indicadores.get("rsi")
    adx = indicadores.get("adx")
    macd = indicadores.get("macd")
    macd_signal = indicadores.get("macd_signal")
    bb_upper = indicadores.get("bb_upper")
    bb_lower = indicadores.get("bb_lower")
    bb_width = indicadores.get("bb_width")
    
    tendencia = classificar_tendencia(price, ema9, ema21, ema200, adx)
    exaustao = identificar_exaustao(price, rsi, bb_upper, bb_lower)
    volatilidade = classificar_volatilidade(bb_width)
    momentum = identificar_momentum(macd, macd_signal)
    is_esticado = ativo_esticado(price, ema21) if ema21 > 0 else False
    
    # Scores
    trend_score = 0
    if price > ema200:
        trend_score += 33
        if ema9 > ema21:
            trend_score += 33
        if adx is not None and adx >= ADX_STRONG:
            trend_score += 34
        elif adx is not None and adx >= ADX_WEAK:
            trend_score += 17
    elif price < ema200:
        trend_score -= 33
        if ema9 < ema21:
            trend_score -= 33
        if adx is not None and adx >= ADX_STRONG:
            trend_score -= 34
        elif adx is not None and adx >= ADX_WEAK:
            trend_score -= 17
    
    reversal_score = 0
    if rsi is not None:
        if rsi > RSI_OVERBOUGHT:
            reversal_score = -50
        elif rsi < RSI_OVERSOLD:
            reversal_score = 50
        elif rsi > 60:
            reversal_score = -20
        elif rsi < 40:
            reversal_score = 20
    if macd is not None and macd_signal is not None:
        if macd > macd_signal and reversal_score < 0:
            reversal_score += 30
        elif macd < macd_signal and reversal_score > 0:
            reversal_score -= 30
    
    volatility_score = 0
    if bb_width is not None:
        if bb_width < BB_WIDTH_LOW_THRESHOLD:
            volatility_score = -50
        elif bb_width > BB_WIDTH_HIGH_THRESHOLD:
            volatility_score = 50
    if adx is not None:
        if adx >= ADX_STRONG:
            volatility_score += 30
        elif adx < ADX_WEAK:
            volatility_score -= 30
    
    # Lógica de decisão
    estrategia = "NO_TRADE"
    justificativa = ""
    
    # 1. Lateral + baixa volatilidade → THL
    if tendencia["direcao"] == "SIDEWAYS" and tendencia["forca"] == "WEAK" and volatilidade == "LOW":
        estrategia = "THL"
        justificativa = (
            f"Mercado lateral (ADX: {adx:.1f}) com baixa volatilidade. "
            f"Estratégia ideal: operações para mercado lateral (THL)."
        )
    # 2. Lateral com volatilidade não baixa → NÃO operar
    elif tendencia["direcao"] == "SIDEWAYS" and volatilidade != "LOW":
        estrategia = "NO_TRADE"
        justificativa = (
            f"Mercado lateral com volatilidade {volatilidade}. "
            f"Recomenda-se não operar até o mercado se direcionar."
        )
    # 3. Exaustão em tendência de alta
    elif tendencia["direcao"] == "UP" and exaustao["sobrevendido"] and momentum == "BULLISH":
        estrategia = "SELL_PUT"
        justificativa = (
            f"Tendência de alta, ativo sobrevendido (RSI: {rsi}), "
            f"momentum bullish. Venda de PUT recomendada."
        )
    # 4. Exaustão em tendência de baixa
    elif tendencia["direcao"] == "DOWN" and exaustao["sobrecomprado"] and momentum == "BEARISH":
        estrategia = "SELL_CALL"
        justificativa = (
            f"Tendência de baixa, ativo sobrecomprado (RSI: {rsi}), "
            f"momentum bearish. Venda de CALL recomendada."
        )
    # 5. Tendência forte de alta
    elif tendencia["direcao"] == "UP" and tendencia["forca"] == "STRONG" and not exaustao["sobrecomprado"]:
        estrategia = "BULL_SPREAD"
        justificativa = (
            f"Tendência de alta forte (ADX: {adx}), ativo não sobrecomprado. "
            f"Trava de Alta (Bull Spread) recomendada."
        )
    # 6. Tendência forte de baixa
    elif tendencia["direcao"] == "DOWN" and tendencia["forca"] == "STRONG" and not exaustao["sobrevendido"]:
        estrategia = "BEAR_SPREAD"
        justificativa = (
            f"Tendência de baixa forte (ADX: {adx}), ativo não sobrevendido. "
            f"Trava de Baixa (Bear Spread) recomendada."
        )
    # 7. Ativo esticado
    elif is_esticado:
        distancia = calcular_distancia_ema21(price, ema21) * 100
        if tendencia["direcao"] == "UP":
            estrategia = "SELL_PUT"
            justificativa = (
                f"Ativo esticado: preço {distancia:.1f}% acima da EMA21. "
                f"Alta probabilidade de reversão. Venda de PUT sugerida."
            )
        elif tendencia["direcao"] == "DOWN":
            estrategia = "SELL_CALL"
            justificativa = (
                f"Ativo esticado: preço {distancia:.1f}% abaixo da EMA21. "
                f"Alta probabilidade de reversão. Venda de CALL sugerida."
            )
        else:
            estrategia = "NO_TRADE"
            justificativa = f"Ativo esticado ({distancia:.1f}%) em mercado lateral. Aguardar."
    # 8. Fallback tendência moderata
    elif tendencia["direcao"] == "UP":
        estrategia = "BULL_SPREAD"
        justificativa = "Tendência de alta moderada. Trava de Alta recomendada."
    elif tendencia["direcao"] == "DOWN":
        estrategia = "BEAR_SPREAD"
        justificativa = "Tendência de baixa moderada. Trava de Baixa recomendada."
    else:
        estrategia = "NO_TRADE"
        justificativa = "Sem configuração clara de tendência ou exaustão. Não operar."
    
    # Filtro de segurança: evitar operar contra tendência forte
    if estrategia in ("SELL_CALL", "BEAR_SPREAD") and tendencia["direcao"] == "UP" and tendencia["forca"] == "STRONG":
        estrategia = "NO_TRADE"
        justificativa = (
            f"FILTRO DE SEGURANÇA: Tendência de alta forte detectada. "
            f"Evitar operar contra a tendência."
        )
    elif estrategia in ("SELL_PUT", "BULL_SPREAD") and tendencia["direcao"] == "DOWN" and tendencia["forca"] == "STRONG":
        estrategia = "NO_TRADE"
        justificativa = (
            f"FILTRO DE SEGURANÇA: Tendência de baixa forte detectada. "
            f"Evitar operar contra a tendência."
        )
    
    return {
        "tendencia": tendencia["direcao"],
        "tendencia_forca": tendencia["forca"],
        "sobrecomprado": exaustao["sobrecomprado"],
        "sobrevendido": exaustao["sobrevendido"],
        "volatilidade": volatilidade,
        "momentum": momentum,
        "ativo_esticado": is_esticado,
        "estrategia_sugerida": estrategia,
        "scores": {
            "trend_score": round(trend_score, 1),
            "reversal_score": round(reversal_score, 1),
            "volatility_score": round(volatility_score, 1),
        },
        "justificativa": justificativa,
        "indicadores": {
            "price": price,
            "ema9": ema9,
            "ema21": ema21,
            "ema200": ema200,
            "rsi": rsi,
            "adx": adx,
            "macd": macd,
            "macd_signal": macd_signal,
            "bb_upper": bb_upper,
            "bb_lower": bb_lower,
            "bb_width": bb_width,
        },
    }


# ============================================================================
# Helpers de Opções
# ============================================================================

def _liquidez_score(texto: str) -> int:
    """Retorna score de liquidez baseado no texto."""
    if not texto:
        return 0
    texto_lower = texto.lower()
    
    # Match exato primeiro
    if texto_lower in SCORE_LIQUIDEZ:
        return SCORE_LIQUIDEZ[texto_lower]
    
    # Match parcial por palavras-chave
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


def _bid_ask_spread_pct(bid: float, ask: float) -> float:
    if ask <= 0:
        return 999.0
    return ((ask - bid) / ask) * 100


def _meio_preco(bid: float, ask: float) -> float:
    return (bid + ask) / 2.0


def _filtro_opcoes(options: list[dict]) -> list[dict]:
    """Filtra opções com critérios flexíveis. Aceita opções com strike válido e VI > 0."""
    filtradas = []
    for opt in options:
        # Verificar strike primeiro (mais importante)
        strike = opt.get("strike", 0) or 0
        if strike <= 0:
            continue
        
        # Aceitar se tem VI válido (indicador de que a opção existe e tem dados)
        vi = opt.get("vi", 0) or 0
        if vi <= 0:
            # Sem VI, verificar se tem pelo menos um preço de mercado
            bid = opt.get("bid", 0) or 0
            ask = opt.get("ask", 0) or 0
            ultimo = opt.get("ultimo_preco", 0) or 0
            if bid <= 0 and ask <= 0 and ultimo <= 0:
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

def _calcular_trava_alta_put(put_venda: dict, put_compra: dict, preco_base: float) -> dict[str, Any]:
    """Trava de Alta com PUT (Bull Put Spread)."""
    premio_venda = put_venda.get("ultimo_preco", 0) or 0
    if premio_venda <= 0:
        premio_venda = _meio_preco(put_venda.get("bid", 0) or 0, put_venda.get("ask", 0) or 0)
    premio_compra = put_compra.get("ultimo_preco", 0) or 0
    if premio_compra <= 0:
        premio_compra = _meio_preco(put_compra.get("bid", 0) or 0, put_compra.get("ask", 0) or 0)
    k1 = put_venda.get("strike", 0)
    k2 = put_compra.get("strike", 0)
    credito = premio_venda - premio_compra
    lucro_max = credito
    perda_max = (k1 - k2) - credito if credito > 0 else (k1 - k2) + abs(credito)
    break_even = k1 - credito
    retorno = (lucro_max / perda_max * 100) if perda_max > 0 else 0
    
    score = 0
    if retorno > 100: score += 30
    elif retorno > 50: score += 20
    elif retorno > 25: score += 10
    if credito > 0: score += 25
    if preco_base > k1: score += 20
    score += _liquidez_score(put_venda.get("liquidez_texto", "")) / 5
    score += _liquidez_score(put_compra.get("liquidez_texto", "")) / 5
    
    return {
        "tipo": "Trava de Alta com PUT (Bull Put Spread)",
        "perna_venda": {"simbolo": put_venda.get("simbolo", ""), "strike": k1, "premio": round(premio_venda, 2), "delta": put_venda.get("delta"), "vi": put_venda.get("vi"), "moneyness": put_venda.get("moneyness", "")},
        "perna_compra": {"simbolo": put_compra.get("simbolo", ""), "strike": k2, "premio": round(premio_compra, 2), "delta": put_compra.get("delta"), "vi": put_compra.get("vi"), "moneyness": put_compra.get("moneyness", "")},
        "serie": put_venda.get("serie", ""),
        "dias_vencimento": put_venda.get("dias_vencimento", 0),
        "credito": round(credito, 2),
        "lucro_max": round(lucro_max, 2),
        "perda_max": round(perda_max, 2),
        "break_even": round(break_even, 2),
        "retorno_pct": round(retorno, 1),
        "score": round(score, 1),
    }


def _calcular_trava_baixa_put(put_compra: dict, put_venda: dict, preco_base: float) -> dict[str, Any]:
    """Trava de Baixa com PUT (Bear Put Spread)."""
    premio_compra = put_compra.get("ultimo_preco", 0) or 0
    if premio_compra <= 0:
        premio_compra = _meio_preco(put_compra.get("bid", 0) or 0, put_compra.get("ask", 0) or 0)
    premio_venda = put_venda.get("ultimo_preco", 0) or 0
    if premio_venda <= 0:
        premio_venda = _meio_preco(put_venda.get("bid", 0) or 0, put_venda.get("ask", 0) or 0)
    k1 = put_compra.get("strike", 0)
    k2 = put_venda.get("strike", 0)
    debito = premio_compra - premio_venda
    lucro_max = (k1 - k2) - debito
    perda_max = debito
    break_even = k1 - debito
    retorno = (lucro_max / perda_max * 100) if perda_max > 0 else 0
    
    score = 0
    if retorno > 200: score += 30
    elif retorno > 100: score += 20
    elif retorno > 50: score += 10
    if preco_base > k1: score += 20
    score += _liquidez_score(put_compra.get("liquidez_texto", "")) / 5
    score += _liquidez_score(put_venda.get("liquidez_texto", "")) / 5
    spread_c = _bid_ask_spread_pct(put_compra.get("bid", 0), put_compra.get("ask", 0))
    spread_v = _bid_ask_spread_pct(put_venda.get("bid", 0), put_venda.get("ask", 0))
    if spread_c < 10 and spread_v < 10:
        score += 10
    
    return {
        "tipo": "Trava de Baixa com PUT (Bear Put Spread)",
        "perna_compra": {"simbolo": put_compra.get("simbolo", ""), "strike": k1, "premio": round(premio_compra, 2), "delta": put_compra.get("delta"), "vi": put_compra.get("vi"), "moneyness": put_compra.get("moneyness", "")},
        "perna_venda": {"simbolo": put_venda.get("simbolo", ""), "strike": k2, "premio": round(premio_venda, 2), "delta": put_venda.get("delta"), "vi": put_venda.get("vi"), "moneyness": put_venda.get("moneyness", "")},
        "serie": put_compra.get("serie", ""),
        "dias_vencimento": put_compra.get("dias_vencimento", 0),
        "debito": round(debito, 2),
        "lucro_max": round(lucro_max, 2),
        "perda_max": round(perda_max, 2),
        "break_even": round(break_even, 2),
        "retorno_pct": round(retorno, 1),
        "score": round(score, 1),
    }


def _calcular_trava_baixa_call(call_venda: dict, call_compra: dict, preco_base: float) -> dict[str, Any]:
    """Trava de Baixa com CALL (Bear Call Spread)."""
    premio_venda = call_venda.get("ultimo_preco", 0) or 0
    if premio_venda <= 0:
        premio_venda = _meio_preco(call_venda.get("bid", 0) or 0, call_venda.get("ask", 0) or 0)
    premio_compra = call_compra.get("ultimo_preco", 0) or 0
    if premio_compra <= 0:
        premio_compra = _meio_preco(call_compra.get("bid", 0) or 0, call_compra.get("ask", 0) or 0)
    k1 = call_venda.get("strike", 0)
    k2 = call_compra.get("strike", 0)
    credito = premio_venda - premio_compra
    lucro_max = credito
    perda_max = (k2 - k1) - credito
    break_even = k1 + credito
    retorno = (lucro_max / perda_max * 100) if perda_max > 0 else 0
    
    score = 0
    if retorno > 100: score += 30
    elif retorno > 50: score += 20
    elif retorno > 25: score += 10
    if credito > 0: score += 25
    score += _liquidez_score(call_venda.get("liquidez_texto", "")) / 5
    score += _liquidez_score(call_compra.get("liquidez_texto", "")) / 5
    
    return {
        "tipo": "Trava de Baixa com CALL (Bear Call Spread)",
        "perna_venda": {"simbolo": call_venda.get("simbolo", ""), "strike": k1, "premio": round(premio_venda, 2), "delta": call_venda.get("delta"), "vi": call_venda.get("vi"), "moneyness": call_venda.get("moneyness", "")},
        "perna_compra": {"simbolo": call_compra.get("simbolo", ""), "strike": k2, "premio": round(premio_compra, 2), "delta": call_compra.get("delta"), "vi": call_compra.get("vi"), "moneyness": call_compra.get("moneyness", "")},
        "serie": call_venda.get("serie", ""),
        "dias_vencimento": call_venda.get("dias_vencimento", 0),
        "credito": round(credito, 2),
        "lucro_max": round(lucro_max, 2),
        "perda_max": round(perda_max, 2),
        "break_even": round(break_even, 2),
        "retorno_pct": round(retorno, 1),
        "score": round(score, 1),
    }


def _calcular_venda_put(put: dict, preco_base: float) -> dict[str, Any]:
    """Venda de PUT (Cash Secured Put ou parte de THL)."""
    premio = put.get("ultimo_preco", 0) or 0
    if premio <= 0:
        premio = _meio_preco(put.get("bid", 0) or 0, put.get("ask", 0) or 0)
    strike = put.get("strike", 0)
    delta = put.get("delta", 0) or 0
    poe = put.get("poe", 0) or 0
    vi = put.get("vi", 0) or 0
    
    score = 0
    if poe < 30: score += 30
    elif poe < 40: score += 20
    if vi > 40: score += 25
    elif vi > 30: score += 15
    score += _liquidez_score(put.get("liquidez_texto", "")) / 5
    if strike < preco_base: score += 15
    
    dist_otm = ((preco_base - strike) / preco_base * 100) if preco_base > 0 else 0
    
    return {
        "tipo": "Venda de PUT (Cash Secured Put)",
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


def _calcular_venda_call(call: dict, preco_base: float) -> dict[str, Any]:
    """Venda de CALL (Covered Call ou parte de THL)."""
    premio = call.get("ultimo_preco", 0) or 0
    if premio <= 0:
        premio = _meio_preco(call.get("bid", 0) or 0, call.get("ask", 0) or 0)
    strike = call.get("strike", 0)
    delta = call.get("delta", 0) or 0
    poe = call.get("poe", 0) or 0
    vi = call.get("vi", 0) or 0
    
    score = 0
    if poe < 30: score += 30
    elif poe < 40: score += 20
    if vi > 40: score += 25
    elif vi > 30: score += 15
    score += _liquidez_score(call.get("liquidez_texto", "")) / 5
    if strike > preco_base: score += 15
    
    dist_otm = ((strike - preco_base) / preco_base * 100) if preco_base > 0 else 0
    
    return {
        "tipo": "Venda de CALL (Covered Call)",
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


# ============================================================================
# Busca de melhores combinações
# ============================================================================

def _buscar_melhor_bull_spread(series: dict[str, dict], preco_base: float, max_sugestoes: int = 3) -> list[dict]:
    sugestoes = []
    for serie_nome, dados in series.items():
        puts = dados["puts"]
        for i, put_venda in enumerate(puts):
            k_venda = put_venda.get("strike", 0)
            if k_venda < preco_base * 0.80 or k_venda > preco_base * 0.98:
                continue
            for put_compra in puts[:i]:
                k_compra = put_compra.get("strike", 0)
                if k_compra < k_venda * 0.85 or k_compra >= k_venda:
                    continue
                if (k_venda - k_compra) / k_venda > 0.20:
                    continue
                sugestoes.append(_calcular_trava_alta_put(put_venda, put_compra, preco_base))
    sugestoes.sort(key=lambda x: x["score"], reverse=True)
    return sugestoes[:max_sugestoes]


def _buscar_melhor_bear_spread(series: dict[str, dict], preco_base: float, max_sugestoes: int = 3) -> list[dict]:
    sugestoes = []
    for serie_nome, dados in series.items():
        puts = dados["puts"]
        for i, put_compra in enumerate(puts):
            k_compra = put_compra.get("strike", 0)
            if k_compra < preco_base * 0.90 or k_compra > preco_base * 1.05:
                continue
            for put_venda in puts[:i]:
                k_venda = put_venda.get("strike", 0)
                if k_venda < k_compra * 0.85 or k_venda >= k_compra:
                    continue
                if (k_compra - k_venda) / k_compra > 0.20:
                    continue
                sugestoes.append(_calcular_trava_baixa_put(put_compra, put_venda, preco_base))
    sugestoes.sort(key=lambda x: x["score"], reverse=True)
    return sugestoes[:max_sugestoes]


def _buscar_melhor_venda_put(series: dict[str, dict], preco_base: float, max_sugestoes: int = 3) -> list[dict]:
    sugestoes = []
    for serie_nome, dados in series.items():
        for put in dados["puts"]:
            strike = put.get("strike", 0)
            if strike < preco_base * 0.85 or strike > preco_base * 1.0:
                continue
            sugestoes.append(_calcular_venda_put(put, preco_base))
    sugestoes.sort(key=lambda x: x["score"], reverse=True)
    return sugestoes[:max_sugestoes]


def _buscar_melhor_venda_call(series: dict[str, dict], preco_base: float, max_sugestoes: int = 3) -> list[dict]:
    sugestoes = []
    for serie_nome, dados in series.items():
        for call in dados["calls"]:
            strike = call.get("strike", 0)
            if strike < preco_base * 1.02 or strike > preco_base * 1.15:
                continue
            sugestoes.append(_calcular_venda_call(call, preco_base))
    sugestoes.sort(key=lambda x: x["score"], reverse=True)
    return sugestoes[:max_sugestoes]


# ============================================================================
# Função principal
# ============================================================================

ESTRATEGIAS_DISPONIVEIS = [
    ("auto", "Análise Automática (por indicadores)"),
    ("trava_alta_put", "Trava de Alta com PUT"),
    ("trava_baixa_put", "Trava de Baixa com PUT"),
    ("trava_baixa_call", "Trava de Baixa com CALL"),
    ("venda_put", "Venda de PUT"),
    ("venda_call", "Venda de CALL"),
]


def analisar_sugestoes(
    ticker: str,
    options: list[dict],
    preco_atual: float,
    estrategia: str = "auto",
    vencimento_dias_min: int = MIN_DAYS_TO_EXPIRY,
    vencimento_dias_max: int = 180,
    indicadores: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    Analisa as opções disponíveis e sugere as melhores estruturas.
    
    Args:
        ticker: Ticker do ativo
        options: Lista de opções disponíveis
        preco_atual: Preço atual do ativo
        estrategia: Tipo de estratégia
        vencimento_dias_min: Dias mínimos até vencimento
        vencimento_dias_max: Dias máximos até vencimento
        indicadores: Indicadores técnicos (ema9, ema21, ema200, rsi, adx, macd, macd_signal, bb_upper, bb_lower, bb_width)
    """
    resultado = {
        "ticker": ticker.upper(),
        "preco_atual": preco_atual,
        "timestamp": None,
        "analise_tecnica": {},
        "estrategia_sugerida": "",
        "sugestoes": [],
        "observacoes": "",
    }
    
    from datetime import datetime
    resultado["timestamp"] = datetime.now().strftime("%d/%m/%Y %H:%M")
    
    if indicadores is None:
        indicadores = {}
    indicadores["price"] = preco_atual
    
    decisao = decidir_estrategia(indicadores)
    # Traduzir resultado para português
    resultado["analise_tecnica"] = _traduzir_resultado(decisao)
    resultado["estrategia_sugerida"] = ESTRATEGIA_NOME.get(decisao["estrategia_sugerida"], decisao["estrategia_sugerida"])
    
    options_filtradas = _filtro_opcoes(options)
    if len(options_filtradas) < 4:
        resultado["observacoes"] = f"Poucas opções com liquidez adequada. Encontradas apenas {len(options_filtradas)}."
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
        resultado["observacoes"] = "Não há séries completas com CALLs e PUTs."
        return resultado
    
    estrategia_principal = decisao["estrategia_sugerida"]
    sugestoes = []
    
    estrategia_map = {
        "BULL_SPREAD": lambda: _buscar_melhor_bull_spread(series, preco_atual),
        "BEAR_SPREAD": lambda: _buscar_melhor_bear_spread(series, preco_atual),
        "SELL_PUT": lambda: _buscar_melhor_venda_put(series, preco_atual),
        "SELL_CALL": lambda: _buscar_melhor_venda_call(series, preco_atual),
        "THL": lambda: _buscar_melhor_venda_put(series, preco_atual) + _buscar_melhor_venda_call(series, preco_atual),
    }
    
    if estrategia == "auto":
        if estrategia_principal in estrategia_map:
            sugestoes = estrategia_map[estrategia_principal]()
        else:
            sugestoes = (
                _buscar_melhor_bull_spread(series, preco_atual) +
                _buscar_melhor_bear_spread(series, preco_atual) +
                _buscar_melhor_venda_put(series, preco_atual) +
                _buscar_melhor_venda_call(series, preco_atual)
            )
            sugestoes.sort(key=lambda x: x.get("score", 0), reverse=True)
    elif estrategia == "trava_alta_put":
        sugestoes = _buscar_melhor_bull_spread(series, preco_atual)
    elif estrategia == "trava_baixa_put":
        sugestoes = _buscar_melhor_bear_spread(series, preco_atual)
    elif estrategia == "trava_baixa_call":
        sugestoes = _buscar_melhor_trava_baixa_call(series, preco_atual)
    elif estrategia == "venda_put":
        sugestoes = _buscar_melhor_venda_put(series, preco_atual)
    elif estrategia == "venda_call":
        sugestoes = _buscar_melhor_venda_call(series, preco_atual)
    
    resultado["sugestoes"] = sugestoes
    resultado["observacoes"] = decisao["justificativa"]
    
    if not sugestoes and estrategia_principal != "NO_TRADE":
        resultado["observacoes"] += " Nenhuma combinação adequada encontrada."
    
    return resultado


def _buscar_melhor_trava_baixa_call(series: dict[str, dict], preco_base: float, max_sugestoes: int = 3) -> list[dict]:
    """Encontra as melhores Trava de Baixa com CALL."""
    sugestoes = []
    for serie_nome, dados in series.items():
        calls = dados["calls"]
        for i, call_venda in enumerate(calls):
            k_venda = call_venda.get("strike", 0)
            if k_venda < preco_base * 1.02 or k_venda > preco_base * 1.12:
                continue
            for call_compra in calls[i+1:]:
                k_compra = call_compra.get("strike", 0)
                if k_compra <= k_venda or k_compra > k_venda * 1.15:
                    continue
                if (k_compra - k_venda) / k_venda > 0.20:
                    continue
                sugestoes.append(_calcular_trava_baixa_call(call_venda, call_compra, preco_base))
    sugestoes.sort(key=lambda x: x["score"], reverse=True)
    return sugestoes[:max_sugestoes]
"""
Yuri System — Módulo de Sugestão de Estruturas de Opções.

Analisa dados de opções disponíveis e sugere as melhores combinações
para diferentes estratégias (travas, spreads, etc.).
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
LIQUIDEZ_MIN = "Razoavel"  # Mínimo: Baixa, Razoavel, Boa, MuitoBoa, Alta
MAX_BID_ASK_DIFF_PCT = 15  # Diferença máxima entre bid/ask (%)
MIN_DAYS_TO_EXPIRY = 5     # Mínimo de dias até vencimento
MAX_IV_RANK = 80           # IV Rank máximo para estratégias de compra

# Pesos para scoring (quanto melhor, maior o score)
SCORE_LIQUIDEZ = {
    "Alta": 100,
    "MuitoBoa": 80,
    "Boa": 60,
    "Razoavel": 40,
    "Baixa": 20,
    "MuitoBaixa": 10,
    "": 0,
}

# ============================================================================
# Helpers
# ============================================================================

def _liquidez_score(texto: str) -> int:
    """Retorna score de liquidez baseado no texto."""
    for key, val in SCORE_LIQUIDEZ.items():
        if key and key.lower() in texto.lower():
            return val
    return 0


def _bid_ask_spread_pct(bid: float, ask: float) -> float:
    """Calcula spread bid-ask em percentual."""
    if ask <= 0:
        return 999.0
    return ((ask - bid) / ask) * 100


def _meio_preco(bid: float, ask: float) -> float:
    """Retorna o preço médio entre bid e ask."""
    return (bid + ask) / 2.0


def _filtro_opcoes(options: list[dict]) -> list[dict]:
    """Filtra opções por liquidez e qualidade."""
    filtradas = []
    for opt in options:
        liq_text = opt.get("liquidez_texto", "")
        bid = opt.get("bid", 0) or 0
        ask = opt.get("ask", 0) or 0
        
        # Pular se liquidez muito baixa
        liq_score = _liquidez_score(liq_text)
        if liq_score < SCORE_LIQUIDEZ.get(LIQUIDEZ_MIN, 0):
            continue
        
        # Pular spread muito grande
        if bid > 0 and ask > 0:
            spread = _bid_ask_spread_pct(bid, ask)
            if spread > MAX_BID_ASK_DIFF_PCT:
                continue
        
        # Pular se strike zero ou negativo
        strike = opt.get("strike", 0) or 0
        if strike <= 0:
            continue
            
        filtradas.append(opt)
    
    return filtradas


def _agrupar_por_serie(options: list[dict]) -> dict[str, list[dict]]:
    """Agrupa opções por série (data de vencimento)."""
    series = {}
    for opt in options:
        serie = opt.get("serie", "desconhecido")
        if serie not in series:
            series[serie] = []
        series[serie].append(opt)
    return series


def _encontrar_serie_proxima(series: dict[str, list[dict]]) -> str | None:
    """Encontra a série mais próxima (menor dias de vencimento)."""
    melhor_serie = None
    menor_dias = float("inf")
    
    for serie, opcoes in series.items():
        dias = opcoes[0].get("dias_vencimento", 999) if opcoes else 999
        if dias < menor_dias and dias >= MIN_DAYS_TO_EXPIRY:
            menor_dias = dias
            melhor_serie = serie
    
    return melhor_serie


# ============================================================================
# Análise de Tendência (simplificada)
# ============================================================================

def _analisar_tendencia(
    options: list[dict],
    preco_atual: Optional[float] = None
) -> dict[str, Any]:
    """
    Analisa tendência do ativo baseado nas opções.
    
    Retorna:
        - tendencia: "alta", "baixa", "lateral"
        - iv_media: volatilidade implícita média
        - iv_rank_aprox: IV Rank aproximado
        - put_call_ratio: ratio de volume puts/calls
        - forca: 0-100 (força da indicação)
    """
    calls = [o for o in options if o.get("tipo") == "CALL"]
    puts = [o for o in options if o.get("tipo") == "PUT"]
    
    # Calcular volumes
    vol_calls = sum(o.get("volume_financeiro", 0) or 0 for o in calls)
    vol_puts = sum(o.get("volume_financeiro", 0) or 0 for o in puts)
    
    # Put/Call Ratio
    pcr = vol_puts / vol_calls if vol_calls > 0 else 0
    
    # IV média
    iv_calls = [o.get("vi", 0) or 0 for o in calls if o.get("vi")]
    iv_puts = [o.get("vi", 0) or 0 for o in puts if o.get("vi")]
    
    iv_media_calls = sum(iv_calls) / len(iv_calls) if iv_calls else 0
    iv_media_puts = sum(iv_puts) / len(iv_puts) if iv_puts else 0
    iv_media = (iv_media_calls + iv_media_puts) / 2 if (iv_media_calls or iv_media_puts) else 0
    
    # Delta médio das opções ATM (aproximação)
    deltas_calls_atm = [
        o.get("delta", 0) or 0 
        for o in calls 
        if o.get("moneyness") == "ATM"
    ]
    deltas_puts_atm = [
        o.get("delta", 0) or 0 
        for o in puts 
        if o.get("moneyness") == "ATM"
    ]
    
    # Indicador de força baseado em PCR
    # PCR > 1 = mais puts sendo negociadas = sentimento negativo
    # PCR < 1 = mais calls sendo negociadas = sentimento positivo
    forca = 50  # neutro
    if pcr > 1.2:
        tendencia = "baixa"
        forca = min(100, 50 + (pcr - 1.2) * 50)
    elif pcr < 0.7:
        tendencia = "alta"
        forca = min(100, 50 + (0.7 - pcr) * 80)
    else:
        tendencia = "lateral"
        forca = 30 + (1 - abs(pcr - 1.0) * 5) * 20
    
    return {
        "tendencia": tendencia,
        "iv_media": round(iv_media, 2),
        "iv_media_calls": round(iv_media_calls, 2),
        "iv_media_puts": round(iv_media_puts, 2),
        "put_call_ratio": round(pcr, 3),
        "forca": round(forca, 1),
        "volume_calls": vol_calls,
        "volume_puts": vol_puts,
    }


# ============================================================================
# Estratégias
# ============================================================================

def _calcular_trava_baixa_put(
    put_compra: dict,
    put_venda: dict,
    preco_base: float
) -> dict[str, Any]:
    """
    Calcula métricas para Bear Put Spread (Trava de Baixa com PUT).
    
    Estrutura:
    - Compra PUT strike mais alto (K1)
    - Venda PUT strike mais baixo (K2)
    """
    # Preços usando meio do bid-ask
    premio_compra = _meio_preco(put_compra.get("bid", 0) or 0, put_compra.get("ask", 0) or 0)
    premio_venda = _meio_preco(put_venda.get("bid", 0) or 0, put_venda.get("ask", 0) or 0)
    
    k1 = put_compra.get("strike", 0)  # Strike maior (compra)
    k2 = put_venda.get("strike", 0)   # Strike menor (venda)
    
    # Credito/debito (trava de baixa com put geralmente é débito)
    debito = premio_compra - premio_venda  # Pago para entrar
    
    # Lucro máximo: diferença de strikes - débito pago
    lucro_max = (k1 - k2) - debito
    
    # Perda máxima: débito pago
    perda_max = debito
    
    # Break-even: strike maior - débito
    break_even = k1 - debito
    
    # Retorno sobre risco
    retorno = (lucro_max / perda_max * 100) if perda_max > 0 else 0
    
    # Score de qualidade
    score = 0
    
    # Boa relação retorno/risco (ideal > 1.5)
    if retorno > 200:
        score += 30
    elif retorno > 100:
        score += 20
    elif retorno > 50:
        score += 10
    
    # Trava está OTM (preço atual acima do strike de compra)?
    if preco_base > k1:
        score += 20  # Boa para tendência de baixa
    
    # Liquidez das opções
    score += _liquidez_score(put_compra.get("liquidez_texto", "")) / 5
    score += _liquidez_score(put_venda.get("liquidez_texto", "")) / 5
    
    # Spread bid-ask razoável
    spread_compra = _bid_ask_spread_pct(put_compra.get("bid", 0), put_compra.get("ask", 0))
    spread_venda = _bid_ask_spread_pct(put_venda.get("bid", 0), put_venda.get("ask", 0))
    if spread_compra < 10 and spread_venda < 10:
        score += 10
    
    return {
        "tipo": "Bear Put Spread (Trava de Baixa com PUT)",
        "perna_compra": {
            "simbolo": put_compra.get("simbolo", ""),
            "strike": k1,
            "premio": round(premio_compra, 2),
            "delta": put_compra.get("delta"),
            "vi": put_compra.get("vi"),
            "moneyness": put_compra.get("moneyness", ""),
        },
        "perna_venda": {
            "simbolo": put_venda.get("simbolo", ""),
            "strike": k2,
            "premio": round(premio_venda, 2),
            "delta": put_venda.get("delta"),
            "vi": put_venda.get("vi"),
            "moneyness": put_venda.get("moneyness", ""),
        },
        "serie": put_compra.get("serie", ""),
        "dias_vencimento": put_compra.get("dias_vencimento", 0),
        "debito": round(debito, 2),
        "lucro_max": round(lucro_max, 2),
        "perda_max": round(perda_max, 2),
        "break_even": round(break_even, 2),
        "retorno_pct": round(retorno, 1),
        "score": round(score, 1),
    }


def _calcular_trava_alta_call(
    call_venda: dict,
    call_compra: dict,
    preco_base: float
) -> dict[str, Any]:
    """
    Calcula métricas para Bear Call Spread (Trava de Alta com CALL).
    
    Estrutura:
    - Vende CALL strike mais baixo (K1)
    - Compra CALL strike mais alto (K2)
    """
    premio_venda = _meio_preco(call_venda.get("bid", 0) or 0, call_venda.get("ask", 0) or 0)
    premio_compra = _meio_preco(call_compra.get("bid", 0) or 0, call_compra.get("ask", 0) or 0)
    
    k1 = call_venda.get("strike", 0)   # Strike menor (venda)
    k2 = call_compra.get("strike", 0)  # Strike maior (compra)
    
    # Crédito recebido
    credito = premio_venda - premio_compra
    
    # Lucro máximo: crédito recebido
    lucro_max = credito
    
    # Perda máxima: diferença de strikes - crédito
    perda_max = (k2 - k1) - credito
    
    # Break-even: strike da venda + crédito
    break_even = k1 + credito
    
    # Retorno sobre risco
    retorno = (lucro_max / perda_max * 100) if perda_max > 0 else 0
    
    # Score
    score = 0
    if retorno > 100:
        score += 30
    elif retorno > 50:
        score += 20
    elif retorno > 25:
        score += 10
    
    # Crédito é positivo?
    if credito > 0:
        score += 25
    
    score += _liquidez_score(call_venda.get("liquidez_texto", "")) / 5
    score += _liquidez_score(call_compra.get("liquidez_texto", "")) / 5
    
    return {
        "tipo": "Bear Call Spread (Trava de Alta com CALL)",
        "perna_venda": {
            "simbolo": call_venda.get("simbolo", ""),
            "strike": k1,
            "premio": round(premio_venda, 2),
            "delta": call_venda.get("delta"),
            "vi": call_venda.get("vi"),
            "moneyness": call_venda.get("moneyness", ""),
        },
        "perna_compra": {
            "simbolo": call_compra.get("simbolo", ""),
            "strike": k2,
            "premio": round(premio_compra, 2),
            "delta": call_compra.get("delta"),
            "vi": call_compra.get("vi"),
            "moneyness": call_compra.get("moneyness", ""),
        },
        "serie": call_venda.get("serie", ""),
        "dias_vencimento": call_venda.get("dias_vencimento", 0),
        "credito": round(credito, 2),
        "lucro_max": round(lucro_max, 2),
        "perda_max": round(perda_max, 2),
        "break_even": round(break_even, 2),
        "retorno_pct": round(retorno, 1),
        "score": round(score, 1),
    }


def _calcular_trava_alta_put(
    put_venda: dict,
    put_compra: dict,
    preco_base: float
) -> dict[str, Any]:
    """
    Calcula métricas para Bull Put Spread (Trava de Alta com PUT).
    
    Estrutura:
    - Vende PUT strike mais alto (K1)
    - Compra PUT strike mais baixo (K2)
    """
    premio_venda = _meio_preco(put_venda.get("bid", 0) or 0, put_venda.get("ask", 0) or 0)
    premio_compra = _meio_preco(put_compra.get("bid", 0) or 0, put_compra.get("ask", 0) or 0)
    
    k1 = put_venda.get("strike", 0)   # Strike maior (venda)
    k2 = put_compra.get("strike", 0)  # Strike menor (compra)
    
    credito = premio_venda - premio_compra
    lucro_max = credito
    perda_max = (k1 - k2) - credito
    break_even = k1 - credito
    retorno = (lucro_max / perda_max * 100) if perda_max > 0 else 0
    
    score = 0
    if retorno > 100:
        score += 30
    elif retorno > 50:
        score += 20
    elif retorno > 25:
        score += 10
    
    if credito > 0:
        score += 25
    
    if preco_base > k1:
        score += 20  # PUT OTM = bom para trava de alta
    
    score += _liquidez_score(put_venda.get("liquidez_texto", "")) / 5
    score += _liquidez_score(put_compra.get("liquidez_texto", "")) / 5
    
    return {
        "tipo": "Bull Put Spread (Trava de Alta com PUT)",
        "perna_venda": {
            "simbolo": put_venda.get("simbolo", ""),
            "strike": k1,
            "premio": round(premio_venda, 2),
            "delta": put_venda.get("delta"),
            "vi": put_venda.get("vi"),
            "moneyness": put_venda.get("moneyness", ""),
        },
        "perna_compra": {
            "simbolo": put_compra.get("simbolo", ""),
            "strike": k2,
            "premio": round(premio_compra, 2),
            "delta": put_compra.get("delta"),
            "vi": put_compra.get("vi"),
            "moneyness": put_compra.get("moneyness", ""),
        },
        "serie": put_venda.get("serie", ""),
        "dias_vencimento": put_venda.get("dias_vencimento", 0),
        "credito": round(credito, 2),
        "lucro_max": round(lucro_max, 2),
        "perda_max": round(perda_max, 2),
        "break_even": round(break_even, 2),
        "retorno_pct": round(retorno, 1),
        "score": round(score, 1),
    }


def _calcular_call_simples(
    call: dict,
    preco_base: float
) -> dict[str, Any]:
    """Avalia compra simples de CALL."""
    premio = _meio_preco(call.get("bid", 0) or 0, call.get("ask", 0) or 0)
    strike = call.get("strike", 0)
    delta = call.get("delta", 0) or 0
    
    # Alavancagem: quanto do preço do ativo vs prêmio
    alavancagem = (preco_base / premio * 100) if premio > 0 else 0
    
    # Probabilidade de sucesso aproximada (POE)
    poe = call.get("poe", 0) or 0
    
    score = 0
    if poe > 30:
        score += 20
    if alavancagem > 5:
        score += 15
    score += _liquidez_score(call.get("liquidez_texto", "")) / 5
    
    return {
        "tipo": "Compra de CALL",
        "simbolo": call.get("simbolo", ""),
        "strike": strike,
        "premio": round(premio, 2),
        "delta": delta,
        "vi": call.get("vi"),
        "moneyness": call.get("moneyness", ""),
        "poe": poe,
        "serie": call.get("serie", ""),
        "dias_vencimento": call.get("dias_vencimento", 0),
        "alavancagem": round(alavancagem, 1),
        "score": round(score, 1),
    }


def _calcular_put_simples(
    put: dict,
    preco_base: float
) -> dict[str, Any]:
    """Avalia compra simples de PUT."""
    premio = _meio_preco(put.get("bid", 0) or 0, put.get("ask", 0) or 0)
    strike = put.get("strike", 0)
    delta = put.get("delta", 0) or 0
    poe = put.get("poe", 0) or 0
    
    alavancagem = (preco_base / premio * 100) if premio > 0 else 0
    distancia_itm = ((strike - preco_base) / preco_base * 100) if strike > 0 else 0
    
    score = 0
    if poe > 30:
        score += 20
    if alavancagem > 5:
        score += 15
    score += _liquidez_score(put.get("liquidez_texto", "")) / 5
    
    return {
        "tipo": "Compra de PUT",
        "simbolo": put.get("simbolo", ""),
        "strike": strike,
        "premio": round(premio, 2),
        "delta": delta,
        "vi": put.get("vi"),
        "moneyness": put.get("moneyness", ""),
        "poe": poe,
        "serie": put.get("serie", ""),
        "dias_vencimento": put.get("dias_vencimento", 0),
        "alavancagem": round(alavancagem, 1),
        "distancia_itm_pct": round(distancia_itm, 1),
        "score": round(score, 1),
    }


# ============================================================================
# Função principal: Analisar e sugerir
# ============================================================================

def analisar_sugestoes(
    ticker: str,
    options: list[dict],
    preco_atual: float,
    estrategia: str = "auto",
    vencimento_dias_min: int = MIN_DAYS_TO_EXPIRY,
    vencimento_dias_max: int = 180,
) -> dict[str, Any]:
    """
    Analisa as opções disponíveis e sugere as melhores estruturas.
    
    Args:
        ticker: Ticker do ativo (ex: "PETR4")
        options: Lista de opções disponíveis (completa com todas as séries)
        preco_atual: Preço atual do ativo
        estrategia: Tipo de estratégia ou "auto" para análise automática
                   Opções: "auto", "trava_baixa_put", "trava_alta_call",
                          "trava_alta_put", "compra_call", "compra_put"
        vencimento_dias_min: Dias mínimos até vencimento
        vencimento_dias_max: Dias máximos até vencimento
    
    Returns:
        {
            "ticker": str,
            "preco_atual": float,
            "timestamp": str,
            "analise_tendencia": dict,
            "estrategia_solicitada": str,
            "apto_para_estrategia": bool,
            "motivo": str,
            "sugestoes": list[dict],
            "observacoes": str,
        }
    """
    resultado = {
        "ticker": ticker.upper(),
        "preco_atual": preco_atual,
        "timestamp": None,
        "analise_tendencia": {},
        "estrategia_solicitada": estrategia,
        "apto_para_estrategia": True,
        "motivo": "",
        "sugestoes": [],
        "observacoes": "",
    }
    
    from datetime import datetime
    resultado["timestamp"] = datetime.now().strftime("%d/%m/%Y %H:%M")
    
    # Filtrar opções válidas
    options_filtradas = _filtro_opcoes(options)
    
    if len(options_filtradas) < 4:
        resultado["apto_para_estrategia"] = False
        resultado["motivo"] = (
            "Poucas opções com liquidez adequada. "
            f"Encontradas apenas {len(options_filtradas)} opções (mínimo: 4)."
        )
        return resultado
    
    # Agrupar por série
    series = _agrupar_por_serie(options_filtradas)
    
    if len(series) == 0:
        resultado["apto_para_estrategia"] = False
        resultado["motivo"] = "Nenhuma série válida encontrada."
        return resultado
    
    # Analisar tendência
    series_list = list(series.values())
    # Usar série mais próxima para análise
    serie_analise = ""
    for s, opts in series.items():
        dias = opts[0].get("dias_vencimento", 999) if opts else 999
        if vencimento_dias_min <= dias <= vencimento_dias_max:
            serie_analise = s
            break
    
    if not serie_analise and series_list:
        serie_analise = list(series.keys())[0]
    
    options_serie = series.get(serie_analise, options_filtradas)
    tendencia = _analisar_tendencia(options_filtradas, preco_atual)
    resultado["analise_tendencia"] = tendencia
    
    # Filtrar séries por dias
    series_filtradas = {}
    for s, opts in series.items():
        dias = opts[0].get("dias_vencimento", 0) if opts else 0
        if vencimento_dias_min <= dias <= vencimento_dias_max:
            series_filtradas[s] = opts
    
    if not series_filtradas:
        resultado["apto_para_estrategia"] = False
        resultado["motivo"] = (
            f"Nenhuma série encontrada entre {vencimento_dias_min} e {vencimento_dias_max} dias."
        )
        return resultado
    
    # Separar por tipo e série
    series = {}
    for s, opts in series_filtradas.items():
        calls_serie = sorted(
            [o for o in opts if o.get("tipo") == "CALL"],
            key=lambda x: x.get("strike", 0)
        )
        puts_serie = sorted(
            [o for o in opts if o.get("tipo") == "PUT"],
            key=lambda x: x.get("strike", 0)
        )
        
        if calls_serie and puts_serie:
            series[s] = {
                "calls": calls_serie,
                "puts": puts_serie,
                "dias": opts[0].get("dias_vencimento", 0) if opts else 0,
            }
    
    if not series:
        resultado["apto_para_estrategia"] = False
        resultado["motivo"] = "Não há séries completas com CALLs e PUTs."
        return resultado
    
    # ========================================================================
    # Gerar sugestões baseado na estratégia
    # ========================================================================
    sugestoes = []
    
    if estrategia == "auto":
        # Sugere automaticamente baseado na tendência
        if tendencia["tendencia"] == "baixa":
            resultado["observacoes"] = (
                f"Análise indica tendência de {tendencia['tendencia'].upper()} "
                f"(Put/Call Ratio: {tendencia['put_call_ratio']:.2f}). "
                f"Trava de baixa com PUT é recomendada."
            )
        elif tendencia["tendencia"] == "alta":
            resultado["observacoes"] = (
                f"Análise indica tendência de {tendencia['tendencia'].upper()} "
                f"(Put/Call Ratio: {tendencia['put_call_ratio']:.2f}). "
                f"Trava de alta com PUT é recomendada."
            )
        else:
            resultado["observacoes"] = (
                f"Análise indica tendência {tendencia['tendencia'].upper()} "
                f"(Put/Call Ratio: {tendencia['put_call_ratio']:.2f}). "
                f"IV média: {tendencia['iv_media']:.1f}%."
            )
        
        # Gerar sugestões para trava de baixa com PUT
        sug_trava_baixa = _buscar_melhor_trava_baixa_put(series, preco_atual)
        sugestoes.extend(sug_trava_baixa)
        
        # Gerar sugestões para trava de alta com PUT
        sug_trava_alta_put = _buscar_melhor_trava_alta_put(series, preco_atual)
        sugestoes.extend(sug_trava_alta_put)
        
        # Gerar sugestões para trava de alta com CALL
        sug_trava_alta_call = _buscar_melhor_trava_alta_call(series, preco_atual)
        sugestoes.extend(sug_trava_alta_call)
        
        # Ordenar por score
        sugestoes.sort(key=lambda x: x.get("score", 0), reverse=True)
        
    elif estrategia == "trava_baixa_put":
        # Verificar se é bom momento
        if tendencia["tendencia"] == "alta":
            resultado["apto_para_estrategia"] = False
            resultado["motivo"] = (
                f"Ativo em tendência de ALTA (PCR: {tendencia['put_call_ratio']:.2f}). "
                f"Não recomendado para trava de baixa no momento."
            )
            resultado["observacoes"] = (
                f"IV média: {tendencia['iv_media']:.1f}%. "
                f"Aguardar melhor momento ou operar trava de alta."
            )
            result = _buscar_melhor_trava_baixa_put(series, preco_atual)
            sugestoes = result[:1] if result else []
        else:
            resultado["observacoes"] = (
                f"Momento adequado para trava de baixa. "
                f"Tendência: {tendencia['tendencia']}."
            )
            sugestoes = _buscar_melhor_trava_baixa_put(series, preco_atual)
    
    elif estrategia == "trava_alta_put":
        if tendencia["tendencia"] == "baixa":
            resultado["apto_para_estrategia"] = False
            resultado["motivo"] = (
                f"Ativo em tendência de BAIXA (PCR: {tendencia['put_call_ratio']:.2f}). "
                f"Não recomendado para trava de alta no momento."
            )
        else:
            resultado["observacoes"] = "Momento adequado para trava de alta com PUT."
            sugestoes = _buscar_melhor_trava_alta_put(series, preco_atual)
    
    elif estrategia == "trava_alta_call":
        if tendencia["tendencia"] == "alta":
            resultado["apto_para_estrategia"] = False
            resultado["motivo"] = (
                f"Ativo em tendência de ALTA. "
                f"Não recomendado para trava de baixa com CALL no momento."
            )
        else:
            resultado["observacoes"] = "Momento adequado para trava de baixa com CALL."
            sugestoes = _buscar_melhor_trava_alta_call(series, preco_atual)
    
    elif estrategia == "compra_call":
        resultado["observacoes"] = "Análise de CALLs individuais:"
        sugestoes = []
        for s, dados in series.items():
            for call in dados["calls"]:
                if call.get("moneyness") in ["ATM", "OTM"]:
                    sug = _calcular_call_simples(call, preco_atual)
                    sugestoes.append(sug)
        sugestoes.sort(key=lambda x: x.get("score", 0), reverse=True)
    
    elif estrategia == "compra_put":
        resultado["observacoes"] = "Análise de PUTs individuais:"
        sugestoes = []
        for s, dados in series.items():
            for put in dados["puts"]:
                if put.get("moneyness") in ["ATM", "ITM"]:
                    sug = _calcular_put_simples(put, preco_atual)
                    sugestoes.append(sug)
        sugestoes.sort(key=lambda x: x.get("score", 0), reverse=True)
    
    else:
        resultado["observacoes"] = f"Estratégia '{estrategia}' não reconhecida. Use 'auto'."
        sugestoes = _buscar_melhor_trava_baixa_put(series, preco_atual)
    
    resultado["sugestoes"] = sugestoes
    
    # Se nenhuma sugestão encontrada
    if not sugestoes:
        resultado["apto_para_estrategia"] = False
        resultado["motivo"] = "Nenhuma combinação adequada encontrada nos critérios."
    
    return resultado


def _buscar_melhor_trava_baixa_put(
    series: dict[str, dict],
    preco_base: float,
    max_sugestoes: int = 3,
) -> list[dict]:
    """Encontra as melhores combinações para Bear Put Spread."""
    sugestoes = []
    
    for serie_nome, dados in series.items():
        puts = dados["puts"]  # Já ordenados por strike crescente
        
        # Para trava de baixa: comprar PUT strike alto, vender PUT strike baixo
        # Procurar PUTs entre ATM e levemente OTM para compra
        for i, put_compra in enumerate(puts):
            k_compra = put_compra.get("strike", 0)
            
            # Só considerar PUTs próximos do preço (0.85x a 1.05x)
            if k_compra < preco_base * 0.90 or k_compra > preco_base * 1.05:
                continue
            
            # Vender PUT com strike mais baixo (0.85x a 0.95x do preço)
            for put_venda in puts[:i]:  # Strikes menores
                k_venda = put_venda.get("strike", 0)
                if k_venda < k_compra * 0.85 or k_venda >= k_compra:
                    continue
                
                # Distância de strikes razoável
                diff_strikes = k_compra - k_venda
                if diff_strikes / k_compra > 0.20:  # Máx 20% de distância
                    continue
                
                sug = _calcular_trava_baixa_put(put_compra, put_venda, preco_base)
                sugestoes.append(sug)
    
    # Ordenar por score e retornar top N
    sugestoes.sort(key=lambda x: x["score"], reverse=True)
    return sugestoes[:max_sugestoes]


def _buscar_melhor_trava_alta_put(
    series: dict[str, dict],
    preco_base: float,
    max_sugestoes: int = 3,
) -> list[dict]:
    """Encontra as melhores combinações para Bull Put Spread."""
    sugestoes = []
    
    for serie_nome, dados in series.items():
        puts = dados["puts"]
        
        # Para trava de alta: vender PUT strike alto, comprar PUT strike baixo
        # Procurar PUTs OTM (abaixo do preço atual)
        for i, put_venda in enumerate(puts):
            k_venda = put_venda.get("strike", 0)
            
            # Só considerar PUTs OTM (0.85x a 0.98x do preço)
            if k_venda < preco_base * 0.80 or k_venda > preco_base * 0.98:
                continue
            
            # Comprar PUT com strike mais baixo
            for put_compra in puts[:i]:
                k_compra = put_compra.get("strike", 0)
                if k_compra < k_venda * 0.85 or k_compra >= k_venda:
                    continue
                
                diff_strikes = k_venda - k_compra
                if diff_strikes / k_venda > 0.20:
                    continue
                
                sug = _calcular_trava_alta_put(put_venda, put_compra, preco_base)
                sugestoes.append(sug)
    
    sugestoes.sort(key=lambda x: x["score"], reverse=True)
    return sugestoes[:max_sugestoes]


def _buscar_melhor_trava_alta_call(
    series: dict[str, dict],
    preco_base: float,
    max_sugestoes: int = 3,
) -> list[dict]:
    """Encontra as melhores combinações para Bear Call Spread."""
    sugestoes = []
    
    for serie_nome, dados in series.items():
        calls = dados["calls"]
        
        # Para bear call spread: vender call strike baixo, comprar call strike alto
        # Procurar CALLs OTM (acima do preço atual)
        for i, call_venda in enumerate(calls):
            k_venda = call_venda.get("strike", 0)
            
            # CALLs OTM (1.02x a 1.10x do preço)
            if k_venda < preco_base * 1.02 or k_venda > preco_base * 1.12:
                continue
            
            # Comprar CALL com strike mais alto
            for call_compra in calls[i+1:]:
                k_compra = call_compra.get("strike", 0)
                if k_compra <= k_venda or k_compra > k_venda * 1.15:
                    continue
                
                diff_strikes = k_compra - k_venda
                if diff_strikes / k_venda > 0.20:
                    continue
                
                sug = _calcular_trava_alta_call(call_venda, call_compra, preco_base)
                sugestoes.append(sug)
    
    sugestoes.sort(key=lambda x: x["score"], reverse=True)
    return sugestoes[:max_sugestoes]
"""
Módulo de cálculos financeiros para carteira de investimentos.
Calcula métricas como P&L, alocação, rentabilidade, etc.
"""

from typing import Optional


def calcular_valor_investido(ativo: dict) -> float:
    """
    Calcula o valor total investido em um ativo.
    Fórmula: quantidade × preço_médio
    """
    qtd = float(ativo.get("quantidade") or 0)
    preco_medio = float(ativo.get("precoMedio") or 0)
    return qtd * preco_medio


def calcular_valor_atual(ativo: dict) -> float:
    """
    Calcula o valor atual de um ativo.
    Fórmula: quantidade × preço_atual
    """
    qtd = float(ativo.get("quantidade") or 0)
    preco_atual = float(ativo.get("precoAtual") or 0)
    return qtd * preco_atual


def calcular_pnl_absoluto(ativo: dict) -> float:
    """
    Calcula o P&L absoluto (ganho/perda em R$).
    Fórmula: valor_atual - valor_investido
    """
    valor_atual = calcular_valor_atual(ativo)
    valor_investido = calcular_valor_investido(ativo)
    return valor_atual - valor_investido


def calcular_pnl_percentual(ativo: dict) -> float:
    """
    Calcula o P&L percentual (rentabilidade).
    Fórmula: (valor_atual - valor_investido) / valor_investido * 100
    Retorna 0 se valor_investido é 0.
    """
    valor_investido = calcular_valor_investido(ativo)
    if valor_investido == 0:
        return 0.0
    pnl_abs = calcular_pnl_absoluto(ativo)
    return (pnl_abs / valor_investido) * 100


def calcular_alocacao_real(ativo: dict, total_carteira: float) -> float:
    """
    Calcula a alocação real (%) de um ativo na carteira.
    Fórmula: (valor_atual / total_carteira) * 100
    Retorna 0 se total_carteira é 0.
    """
    if total_carteira == 0:
        return 0.0
    valor_atual = calcular_valor_atual(ativo)
    return (valor_atual / total_carteira) * 100


def calcular_alocacao_real_investido(ativo: dict, total_investido: float) -> float:
    """
    Calcula a alocação real baseada no valor investido (%).
    Fórmula: (valor_investido / total_investido) * 100
    Retorna 0 se total_investido é 0.
    """
    if total_investido == 0:
        return 0.0
    valor_investido = calcular_valor_investido(ativo)
    return (valor_investido / total_investido) * 100


def calcular_desvio_alocacao(ativo: dict, total_carteira: float) -> float:
    """
    Calcula o desvio entre alocação real e alocação ideal.
    Fórmula: alocacao_real - alocacao_ideal
    Retorna diferença em pontos percentuais.
    """
    alocacao_ideal = float(ativo.get("alocacaoIdeal") or 0)
    alocacao_real = calcular_alocacao_real(ativo, total_carteira)
    return alocacao_real - alocacao_ideal


def calcular_metricas_ativo(ativo: dict, total_carteira: float, total_investido: float) -> dict:
    """
    Calcula todas as métricas de um ativo individual.
    Retorna dict com valores calculados.
    """
    valor_investido = calcular_valor_investido(ativo)
    valor_atual = calcular_valor_atual(ativo)
    pnl_abs = calcular_pnl_absoluto(ativo)
    pnl_pct = calcular_pnl_percentual(ativo)
    alocacao_real = calcular_alocacao_real(ativo, total_carteira)
    alocacao_ideal = float(ativo.get("alocacaoIdeal") or 0)
    desvio_alocacao = desvio_alocacao = alocacao_real - alocacao_ideal

    return {
        "valorInvestido": round(valor_investido, 2),
        "valorAtual": round(valor_atual, 2),
        "pnlAbsoluto": round(pnl_abs, 2),
        "pnlPercentual": round(pnl_pct, 2),
        "alocacaoReal": round(alocacao_real, 2),
        "alocacaoIdeal": round(alocacao_ideal, 2),
        "desvioAlocacao": round(desvio_alocacao, 2),
    }


def calcular_metricas_carteira(ativos: list[dict]) -> dict:
    """
    Calcula todas as métricas agregadas da carteira.
    Retorna dict com valores consolidados.
    """
    if not ativos:
        return {
            "totalInvestido": 0.0,
            "totalAtual": 0.0,
            "pnlAbsoluto": 0.0,
            "pnlPercentual": 0.0,
            "rentabilidade": 0.0,
            "numAtivos": 0,
        }

    total_investido = sum(calcular_valor_investido(a) for a in ativos)
    total_atual = sum(calcular_valor_atual(a) for a in ativos)
    pnl_absoluto = total_atual - total_investido

    pnl_percentual = 0.0
    if total_investido > 0:
        pnl_percentual = (pnl_absoluto / total_investido) * 100

    return {
        "totalInvestido": round(total_investido, 2),
        "totalAtual": round(total_atual, 2),
        "pnlAbsoluto": round(pnl_absoluto, 2),
        "pnlPercentual": round(pnl_percentual, 2),
        "rentabilidade": round(pnl_percentual, 2),  # alias para pnlPercentual
        "numAtivos": len(ativos),
    }


def validar_alocacoes(ativos: list[dict], tolerancia: float = 0.01) -> tuple[bool, str]:
    """
    Valida se a soma de alocações ideais equals 100%.
    Retorna (válido, mensagem).
    tolerancia: margem de tolerância em % (padrão: 0.01%)
    """
    soma_ideal = sum(float(a.get("alocacaoIdeal") or 0) for a in ativos)
    diferenca = abs(soma_ideal - 100.0)

    if diferenca <= tolerancia:
        return True, f"Alocações válidas (total: {soma_ideal:.2f}%)"
    else:
        return False, f"Soma de alocações ideais deve ser 100% (atual: {soma_ideal:.2f}%)"


def calcular_desvios_alocacao(ativos: list[dict]) -> list[dict]:
    """
    Calcula desvios de alocação para todos os ativos.
    Retorna lista de dicts com ticker e desvio.
    Útil para visualizar quais ativos estão desalinhados.
    """
    total_atual = sum(calcular_valor_atual(a) for a in ativos)
    desvios = []

    for ativo in ativos:
        alocacao_real = calcular_alocacao_real(ativo, total_atual)
        alocacao_ideal = float(ativo.get("alocacaoIdeal") or 0)
        desvio = alocacao_real - alocacao_ideal

        desvios.append({
            "ticker": ativo.get("ticker"),
            "alocacaoIdeal": round(alocacao_ideal, 2),
            "alocacaoReal": round(alocacao_real, 2),
            "desvio": round(desvio, 2),
        })

    # Ordenar por desvio absoluto (maior desvio primeiro)
    desvios.sort(key=lambda x: abs(x["desvio"]), reverse=True)
    return desvios


def simular_rebalanceamento(ativos: list[dict], valor_total: float) -> list[dict]:
    """
    Simula quanto comprar/vender de cada ativo para atingir alocação ideal.
    Retorna lista de operações sugeridas.
    """
    operacoes = []
    total_atual = sum(calcular_valor_atual(a) for a in ativos)

    for ativo in ativos:
        alocacao_ideal = float(ativo.get("alocacaoIdeal") or 0) / 100
        valor_alvo = valor_total * alocacao_ideal
        valor_atual = calcular_valor_atual(ativo)
        diferenca = valor_alvo - valor_atual

        if abs(diferenca) > 1:  # Ignorar diferenças menores que R$ 1
            preco_atual = float(ativo.get("precoAtual") or 0)
            if preco_atual > 0:
                qtd_mudanca = diferenca / preco_atual
                operacao = "comprar" if diferenca > 0 else "vender"
                operacoes.append({
                    "ticker": ativo.get("ticker"),
                    "operacao": operacao,
                    "qtd": abs(qtd_mudanca),
                    "valor": abs(diferenca),
                    "precoAtual": preco_atual,
                })

    return operacoes

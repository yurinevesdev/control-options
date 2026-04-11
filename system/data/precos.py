"""
Yuri System — Módulo de atualização de preços.

Atualiza preços de ativos via Yahoo Finance e preços de opções via OpLab.
"""

from __future__ import annotations

import time
import yfinance as yf
import requests
from bs4 import BeautifulSoup
from typing import Optional

from system.ui.logger import get_logger
from system.data.opcoes_scraper import HEADERS, TIMEOUT, buscar_opcoes_serie

log = get_logger("precos")

# ============================================================================
# Yahoo Finance - Preço do ativo
# ============================================================================

def obter_preco_ativo_yahoo(ticker: str) -> Optional[float]:
    """
    Obtém o preço atual do ativo via Yahoo Finance.
    Retorna o preço de fechamento mais recente ou None se falhar.
    """
    try:
        ticker_yf = ticker
        # Adicionar .SA se for ação brasileira e não tiver
        if not ticker_yf.endswith(".SA") and len(ticker_yf) <= 6 and ticker_yf.isalnum():
            ticker_yf = f"{ticker_yf}.SA"

        yf_ticker = yf.Ticker(ticker_yf)
        hist = yf_ticker.history(period="1d")

        if hist is not None and not hist.empty and "Close" in hist.columns:
            preco = float(hist["Close"].iloc[-1])
            log.info("Yahoo Finance: %s = R$ %.2f", ticker_yf, preco)
            return preco

        # Fallback: tentar info
        info = yf_ticker.info
        if info and info.get("lastPrice"):
            return float(info["lastPrice"])
        if info and info.get("regularMarketPreviousClose"):
            return float(info["regularMarketPreviousClose"])
        if info and info.get("currentPrice"):
            return float(info["currentPrice"])

        log.warning("Não foi possível obter preço do Yahoo para %s", ticker)
        return None

    except Exception as e:
        log.error("Erro ao obter preço do Yahoo para %s: %s", ticker, e)
        return None


# ============================================================================
# OpLab - Preço atual das opções
# ============================================================================

def obter_precos_opcoes_oplab(ticker: str, db=None) -> dict[str, dict]:
    """
    Obtém preços atuais de todas as opções de um ticker via OpLab.
    Retorna dict com chave = simbolo da opção e valor = dados.
    
    {
        "simbolo": {
            "ultimo_preco": float,
            "bid": float,
            "ask": float,
            "volume": int,
        },
        ...
    }
    """
    precos = {}
    
    try:
        # Tentar buscar do DB primeiro se db estiver disponível
        opcoes = []
        if db is not None:
            opcoes = buscar_opcoes_serie(db, ticker)
        
        if opcoes:
            for opt in opcoes:
                simbolo = opt.get("simbolo", "")
                if simbolo:
                    precos[simbolo] = {
                        "ultimo_preco": opt.get("ultimo_preco", 0),
                        "bid": opt.get("bid", 0),
                        "ask": opt.get("ask", 0),
                        "volume": opt.get("volume", 0),
                        "vi": opt.get("vi", 0),
                        "delta": opt.get("delta", 0),
                        "serie": opt.get("serie", ""),
                        "tipo": opt.get("tipo", ""),
                        "strike": opt.get("strike", 0),
                    }
            
            log.info("OpLab (DB): %d opções para %s", len(precos), ticker)
            return precos
        
        # Se não tem no DB, buscar do OpLab
        from system.data.opcoes_scraper import formatar_opcoes_tabela
        
        opcoes_api = formatar_opcoes_tabela(ticker)
        if opcoes_api:
            for opt in opcoes_api:
                simbolo = opt.get("simbolo", "")
                if simbolo:
                    precos[simbolo] = {
                        "ultimo_preco": opt.get("ultimo_preco", 0),
                        "bid": opt.get("bid", 0),
                        "ask": opt.get("ask", 0),
                        "volume": opt.get("volume", 0),
                        "vi": opt.get("vi", 0),
                        "delta": opt.get("delta", 0),
                        "serie": opt.get("serie", ""),
                        "tipo": opt.get("tipo", ""),
                        "strike": opt.get("strike", 0),
                    }
            log.info("OpLab (API): %d opções para %s", len(precos), ticker)
            
    except Exception as e:
        log.error("Erro ao obter preços de opções para %s: %s", ticker, e)
    
    return precos


def obter_preco_opcao_por_strike(
    ticker: str, 
    tipo: str, 
    strike: float, 
    vencimento: str = None,
    preco_opcao_db: float = None,
) -> Optional[float]:
    """
    Tenta obter o preço atual de uma opção específica.
    
    Busca pelo ticker + tipo + strike + vencimento.
    Se não encontrar, retorna o preço do banco se fornecido.
    """
    try:
        precos = obter_precos_opcoes_oplab(ticker)
        
        if precos:
            # Buscar a opção mais próxima
            melhor_match = None
            menor_diff = float("inf")
            
            for simbolo, dados in precos.items():
                if dados.get("tipo", "").upper() != tipo.upper():
                    continue
                
                # Se tem vencimento, filtrar
                if vencimento and dados.get("serie") and dados.get("serie") != vencimento:
                    continue
                
                diff = abs(dados.get("strike", 0) - strike)
                if diff < menor_diff:
                    menor_diff = diff
                    melhor_match = dados
            
            if melhor_match and melhor_match.get("ask", 0) > 0:
                return float(melhor_match["ask"])
            elif melhor_match and melhor_match.get("ultimo_preco", 0) > 0:
                return float(melhor_match["ultimo_preco"])
        
        # Fallback: retornar preço do DB se fornecido
        if preco_opcao_db and preco_opcao_db > 0:
            return float(preco_opcao_db)
            
        return None
            
    except Exception as e:
        log.error("Erro ao obter preço da opção %s %s %.2f: %s", ticker, tipo, strike, e)
        return preco_opcao_db


# ============================================================================
# Pipeline de atualização - Atualiza todos os preços de uma estrutura
# ============================================================================

def atualizar_precos_estrutura(db, estrutura_id: int) -> dict:
    """
    Atualiza todos os preços de uma estrutura:
    - Preço do ativo via Yahoo Finance
    - Preço das opções (pernas) via OpLab
    
    Retorna dict com resultados:
    {
        "ativo_atualizado": bool,
        "opcoes_atualizadas": int,
        "erros": list[str],
        "preco_ativo": float | None,
    }
    """
    resultado = {
        "ativo_atualizado": False,
        "opcoes_atualizadas": 0,
        "erros": [],
        "preco_ativo": None,
    }
    
    estrutura = db.get("estruturas", estrutura_id)
    if not estrutura:
        resultado["erros"].append("Estrutura não encontrada")
        return resultado
    
    ticker = estrutura.get("ativo", "").strip()
    if not ticker:
        resultado["erros"].append("Ativo não informado na estrutura")
        return resultado
    
    # 1. Atualizar preço do ativo via Yahoo Finance
    try:
        preco_ativo = obter_preco_ativo_yahoo(ticker)
        if preco_ativo:
            db.save_estrutura({
                "id": estrutura_id,
                "nome": estrutura.get("nome", ""),
                "ativo": ticker,
                "tipo": estrutura.get("tipo", ""),
                "precoAtual": preco_ativo,
                "dataVenc": estrutura.get("dataVenc"),
                "obs": estrutura.get("obs", ""),
            })
            resultado["ativo_atualizado"] = True
            resultado["preco_ativo"] = preco_ativo
            log.info("Preço do ativo %s atualizado: R$ %.2f", ticker, preco_ativo)
        else:
            resultado["erros"].append(f"Não foi possível obter preço do ativo {ticker}")
    except Exception as e:
        log.error("Erro ao atualizar preço do ativo %s: %s", ticker, e)
        resultado["erros"].append(f"Erro ao atualizar preço do ativo {ticker}: {str(e)}")
    
    # 2. Atualizar preços das opções via OpLab
    precos_opcoes = obter_precos_opcoes_oplab(ticker, db)
    if precos_opcoes:
        legs = db.get_legs(estrutura_id)
        for leg in legs:
            ticker_leg = leg.get("ticker", "").strip()
            tipo_leg = leg.get("tipo", "call")
            strike_leg = leg.get("strike", 0)
            venc_leg = leg.get("vencimento", "")
            premio_atual = leg.get("premio", 0)
            
            # Se tem ticker específico, buscar direto
            novo_premio = None
            if ticker_leg and ticker_leg in precos_opcoes:
                dados = precos_opcoes[ticker_leg]
                # Usar ask (preço de venda) se disponível, senão último preço
                if dados.get("ask", 0) > 0:
                    novo_premio = dados["ask"]
                elif dados.get("ultimo_preco", 0) > 0:
                    novo_premio = dados["ultimo_preco"]
            else:
                # Buscar por strike/tipo mais próximo
                novo_premio = obter_preco_opcao_por_strike(
                    ticker, tipo_leg, strike_leg, venc_leg, premio_atual
                )
            
            if novo_premio and novo_premio != premio_atual:
                # Atualizar o prêmio da perna
                obj_leg = {
                    "estruturaId": estrutura_id,
                    "operacao": leg.get("operacao", "compra"),
                    "tipo": tipo_leg,
                    "qtd": leg.get("qtd", 100),
                    "strike": strike_leg,
                    "ticker": ticker_leg,
                    "vencimento": venc_leg,
                    "premio": novo_premio,
                    "iv": leg.get("iv"),
                    "delta": leg.get("delta"),
                    "gamma": leg.get("gamma"),
                    "theta": leg.get("theta"),
                    "vega": leg.get("vega"),
                }
                if leg.get("id"):
                    obj_leg["id"] = leg["id"]
                    db.save_leg(obj_leg)
                    resultado["opcoes_atualizadas"] += 1
                    log.info(
                        "Prêmio da perna %s atualizado: %.4f -> %.4f",
                        ticker_leg or f"{tipo_leg} {strike_leg}",
                        premio_atual,
                        novo_premio,
                    )
    
    return resultado


def atualizar_todas_estruturas_em_andamento(db) -> dict:
    """
    Atualiza preços de todas as estruturas "em andamento".
    Retorna dict com resultados por estrutura.
    """
    estruturas = db.get_estruturas()
    resultados = {}
    
    for est in estruturas:
        status = est.get("status", "em_andamento")
        if status == "em_andamento":
            resultados[est["id"]] = atualizar_precos_estrutura(db, est["id"])
            # Pequeno delay para não sobrecarregar APIs
            time.sleep(0.5)
    
    return resultados
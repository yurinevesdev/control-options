"""
Yuri System — Busca de indicadores técnicos do Yahoo Finance.

Usa yfinance para obter dados históricos e calcular:
- EMA 9, EMA 21, EMA 200
- RSI (14 períodos)
- ADX (14 períodos)
- MACD e MACD Signal
- Bandas de Bollinger (20 períodos, 2 desvios)
- BB Width
"""

from __future__ import annotations

from typing import Any, Optional

import numpy as np
import pandas as pd
import yfinance as yf

from eagle.logger import get_logger

log = get_logger("indicadores")

# Mapeamento de tickers brasileiros para Yahoo Finance
TICKER_MAP = {
    "PETR4": "PETR4.SA",
    "PETR3": "PETR3.SA",
    "VALE3": "VALE3.SA",
    "ITUB4": "ITUB4.SA",
    "BBDC4": "BBDC4.SA",
    "BBAS3": "BBAS3.SA",
    "ABEV3": "ABEV3.SA",
    "WEGE3": "WEGE3.SA",
    "RENT3": "RENT3.SA",
    "MGLU3": "MGLU3.SA",
    "LREN3": "LREN3.SA",
    "GGBR4": "GGBR4.SA",
    "CSNA3": "CSNA3.SA",
    "USIM5": "USIM5.SA",
    "JBSS3": "JBSS3.SA",
    "SUZB3": "SUZB3.SA",
    "KLBN11": "KLBN11.SA",
    "RADL3": "RADL3.SA",
    "RAIL3": "RAIL3.SA",
    "HAPV3": "HAPV3.SA",
    "BBSE3": "BBSE3.SA",
    "ENBR3": "ENBR3.SA",
    "ELET3": "ELET3.SA",
    "ELET6": "ELET6.SA",
    "CMIG4": "CMIG4.SA",
    "CPLE6": "CPLE6.SA",
    "SBSP3": "SBSP3.SA",
    "SANB11": "SANB11.SA",
    "B3SA3": "B3SA3.SA",
    "VIVT3": "VIVT3.SA",
    "TIMS3": "TIMS3.SA",
    "OIBR3": "OIBR3.SA",
    "GOLL4": "GOLL4.SA",
    "AZUL4": "AZUL4.SA",
    "CVCB3": "CVCB3.SA",
}


def _converter_ticker(ticker: str) -> str:
    """Converte ticker brasileiro para formato Yahoo Finance."""
    ticker = ticker.upper().strip()
    if ticker in TICKER_MAP:
        return TICKER_MAP[ticker]
    if not ticker.endswith(".SA"):
        return ticker + ".SA"
    return ticker


def _calcular_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Calcula RSI (Relative Strength Index)."""
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _calcular_adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Calcula ADX (Average Directional Index)."""
    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0

    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = tr.rolling(window=period).mean()
    plus_di = 100 * plus_dm.rolling(window=period).mean() / atr
    minus_di = 100 * minus_dm.rolling(window=period).mean() / atr

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    adx = dx.rolling(window=period).mean()
    return adx


def _calcular_macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple[pd.Series, pd.Series]:
    """Calcula MACD e linha de sinal."""
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    macd_signal = macd.ewm(span=signal, adjust=False).mean()
    return macd, macd_signal


def _calcular_bollinger(close: pd.Series, period: int = 20, std_dev: float = 2.0) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Calcula Bandas de Bollinger."""
    sma = close.rolling(window=period).mean()
    std = close.rolling(window=period).std()
    upper = sma + std_dev * std
    lower = sma - std_dev * std
    width = (upper - lower) / sma
    return upper, lower, width


def buscar_indicadores(
    ticker: str,
    period: str = "1y",
    interval: str = "1d",
    opcoes: Optional[list[dict]] = None,
) -> Optional[dict[str, Any]]:
    """
    Busca dados do Yahoo Finance e calcula indicadores técnicos.
    
    Args:
        ticker: Ticker do ativo (ex: PETR4, VALE3)
        period: Período para dados históricos (1mo, 3mo, 6mo, 1y, 2y, 5y)
        interval: Intervalo dos dados (1d, 1wk, 1mo)
    
    Returns:
        Dicionário com indicadores ou None se erro.
        {
            "price": float,
            "ema9": float,
            "ema21": float,
            "ema200": float,
            "rsi": float,
            "adx": float,
            "macd": float,
            "macd_signal": float,
            "bb_upper": float,
            "bb_lower": float,
            "bb_width": float,
        }
    """
    ticker_yf = _converter_ticker(ticker)
    
    try:
        log.info("Buscando dados de %s (%s) do Yahoo Finance...", ticker, ticker_yf)
        stock = yf.Ticker(ticker_yf)
        hist = stock.history(period=period, interval=interval)
        
        if hist.empty or len(hist) < 30:
            log.warning("Dados insuficientes para %s (%d registros)", ticker, len(hist))
            return None
        
        close = hist["Close"]
        high = hist["High"]
        low = hist["Low"]
        
        # Preço atual (último fechamento)
        price = float(close.iloc[-1])
        
        # EMAs
        ema9 = float(close.ewm(span=9, adjust=False).mean().iloc[-1])
        ema21 = float(close.ewm(span=21, adjust=False).mean().iloc[-1])
        
        # EMA 200 precisa de mais dados
        if len(close) >= 200:
            ema200 = float(close.ewm(span=200, adjust=False).mean().iloc[-1])
        else:
            # Se não tem 200 dias, usar período mais longo disponível
            ema200 = float(close.ewm(span=min(200, len(close)), adjust=False).mean().iloc[-1])
        
        # RSI
        rsi = float(_calcular_rsi(close).iloc[-1])
        
        # ADX
        adx = float(_calcular_adx(high, low, close).iloc[-1])
        
        # MACD
        macd, macd_signal = _calcular_macd(close)
        macd_val = float(macd.iloc[-1])
        macd_sig = float(macd_signal.iloc[-1])
        
        # Bollinger
        bb_upper, bb_lower, bb_width = _calcular_bollinger(close)
        bb_up = float(bb_upper.iloc[-1])
        bb_lo = float(bb_lower.iloc[-1])
        bb_w = float(bb_width.iloc[-1])
        
        # Calcular VI média das opções se disponíveis
        vi_media = None
        if opcoes:
            vis = [o.get("vi", 0) for o in opcoes if (o.get("vi", 0) or 0) > 0]
            if vis:
                vi_media = round(sum(vis) / len(vis), 2)
        
        resultado = {
            "price": round(price, 2),
            "ema9": round(ema9, 2),
            "ema21": round(ema21, 2),
            "ema200": round(ema200, 2),
            "rsi": round(rsi, 2),
            "adx": round(adx, 2),
            "macd": round(macd_val, 4),
            "macd_signal": round(macd_sig, 4),
            "bb_upper": round(bb_up, 2),
            "bb_lower": round(bb_lo, 2),
            "bb_width": round(bb_w, 4),
            "vi_media": vi_media,
            "iv_rank": None,  # Será calculado quando tivermos histórico
        }
        
        log.info("Indicadores calculados para %s: price=%.2f, RSI=%.1f, ADX=%.1f", ticker, price, rsi, adx)
        return resultado
        
    except Exception as e:
        log.error("Erro ao buscar indicadores para %s: %s", ticker, e)
        return None


def buscar_preco_atual(ticker: str) -> Optional[float]:
    """Busca apenas o preço atual do ativo."""
    ticker_yf = _converter_ticker(ticker)
    try:
        stock = yf.Ticker(ticker_yf)
        hist = stock.history(period="5d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception as e:
        log.error("Erro ao buscar preço de %s: %s", ticker, e)
    return None
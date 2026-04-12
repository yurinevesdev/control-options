"""
System — Scraper de dados de opções (OpLab).

Baseado no projeto sinais-compra-ou-venda/scraping.py
Extrai volatilidade implícita, IV Rank e IV Percentil para uso
nas análises do System.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

from system.ui.logger import get_logger

log = get_logger("opcoes_scraper")

# ============================================================================
# Config
# ============================================================================

OPLAB_BASE = "https://opcoes.oplab.com.br/mercado"
OPLAB_ATIVOS = f"{OPLAB_BASE}"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
TIMEOUT = 15
CACHE_DIR = Path(__file__).resolve().parent.parent / "cache"
CACHE_FILE = CACHE_DIR / "oplab_opcoes.json"


# ============================================================================
# Dataclasses
# ============================================================================

@dataclass
class OpcaoDados:
    ticker: str
    descricao: str = ""
    preco: Optional[float] = None
    variacao_pct: Optional[float] = None
    volatilidade_implicita: Optional[float] = None
    iv_rank: Optional[float] = None
    iv_percentil: Optional[float] = None
    desvio_padrao: Optional[float] = None
    ewma: Optional[float] = None
    beta: Optional[float] = None
    link: str = ""


# ============================================================================
# Helpers
# ============================================================================

def _br_to_float(s: str | None) -> Optional[float]:
    """Converte string BR ('1.234,56' ou '32,50%') para float."""
    if not s or s in ("N/A", "-", ""):
        return None
    try:
        clean = s.replace("%", "").replace(".", "").replace(",", ".").strip()
        return float(clean)
    except (ValueError, AttributeError):
        return None


def _extrair_preco(text: str | None) -> Optional[float]:
    """Extrai preço de texto como 'R$ 1.234,56'."""
    if not text:
        return None
    match = re.search(r"R\$\s*([\d.,]+)", text)
    if match:
        return _br_to_float(match.group(1))
    return None


def _extrair_variacao(text: str | None) -> Optional[float]:
    """Extrai variação percentual de texto como '+1,23%' ou '-0,45%'."""
    if not text:
        return None
    match = re.search(r"([+-]?[\d.,]+)%", text)
    if match:
        return _br_to_float(match.group(1))
    return None


# ============================================================================
# Scraping
# ============================================================================

def baixar_lista_ativos() -> list[dict]:
    """Baixa e parseia a lista de ativos da página principal do OpLab."""
    try:
        resp = requests.get(OPLAB_ATIVOS, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as e:
        log.error("Erro ao acessar OpLab: %s", e)
        return []

    soup = BeautifulSoup(resp.content, "html.parser")
    cards = soup.find_all("a", class_="AssetCard_assetCard__iGiPy")
    ativos = []

    for card in cards:
        try:
            ticker_el = card.find("p", class_="AssetCard_symbol__0AOFx")
            ticker = ticker_el.get_text(strip=True) if ticker_el else ""
            if not ticker:
                continue

            preco_el = card.find("p", class_="AssetCard_close__K127U")
            preco_text = preco_el.get_text(strip=True) if preco_el else ""

            # Variação está no <p> irmão da descrição
            desc_el = card.find("p", class_="AssetCard_description__bvu_R")
            variacao_text = ""
            if desc_el:
                var_p = desc_el.find_next_sibling("p")
                variacao_text = var_p.get_text(strip=True) if var_p else ""

            # Valores de VI, IV Rank, IV Percentil
            vi = iv_rank = iv_perc = None
            labels_div = card.find(
                lambda tag: tag.name == "div" and "Vol. Implícita" in tag.get_text()
            )
            if labels_div:
                valores_div = labels_div.find_next_sibling("div")
                if valores_div:
                    valores_ps = valores_div.find_all("p")
                    if len(valores_ps) >= 3:
                        vi = _br_to_float(valores_ps[0].get_text(strip=True))
                        iv_rank = _br_to_float(valores_ps[1].get_text(strip=True))
                        iv_perc = _br_to_float(valores_ps[2].get_text(strip=True))

            ativos.append({
                "ticker": ticker,
                "preco": _extrair_preco(preco_text),
                "variacao_pct": _extrair_variacao(variacao_text),
                "vi": vi,
                "iv_rank": iv_rank,
                "iv_percentil": iv_perc,
            })
        except Exception as e:
            log.warning("Erro ao processar card: %s", e)
            continue

    log.info("Extraídos %d ativos do OpLab", len(ativos))
    return ativos


def salvar_cache(dados: list[dict]) -> Path:
    """Salva dados extraídos em cache JSON."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "total": len(dados),
        "ativos": dados,
    }
    CACHE_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), "utf-8")
    log.info("Cache salvo: %s (%d ativos)", CACHE_FILE, len(dados))
    return CACHE_FILE


def carregar_cache() -> list[dict]:
    """Carrega dados do cache JSON."""
    if not CACHE_FILE.exists():
        return []
    try:
        data = json.loads(CACHE_FILE.read_text("utf-8"))
        return data.get("ativos", [])
    except (json.JSONDecodeError, KeyError) as e:
        log.warning("Erro ao carregar cache: %s", e)
        return []


# ============================================================================
# Integração com DB do System
# ============================================================================

def salvar_no_db(dados: list[dict], db=None) -> int:
    """
    Salva dados de opções na tabela `opcoes_dados` do SQLite.
    Cria a tabela se não existir.
    Retorna número de registros atualizados.
    """
    if db is None:
        log.error("Database não fornecida")
        return 0

    conn = db.connect()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS opcoes_dados (
            ticker TEXT PRIMARY KEY,
            preco REAL,
            variacao_pct REAL,
            volatilidade_implicita REAL,
            iv_rank REAL,
            iv_percentil REAL,
            atualizado_em TEXT
        )
        """
    )
    conn.commit()

    count = 0
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    for ativo in dados:
        ticker = ativo.get("ticker", "")
        if not ticker:
            continue
        conn.execute(
            """
            INSERT INTO opcoes_dados 
                (ticker, preco, variacao_pct, volatilidade_implicita, iv_rank, iv_percentil, atualizado_em)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticker) DO UPDATE SET
                preco = excluded.preco,
                variacao_pct = excluded.variacao_pct,
                volatilidade_implicita = excluded.volatilidade_implicita,
                iv_rank = excluded.iv_rank,
                iv_percentil = excluded.iv_percentil,
                atualizado_em = excluded.atualizado_em
            """,
            (
                ticker,
                ativo.get("preco"),
                ativo.get("variacao_pct"),
                ativo.get("vi"),
                ativo.get("iv_rank"),
                ativo.get("iv_percentil"),
                now,
            ),
        )
        count += 1

    conn.commit()
    log.info("Salvos %d registros de opções no DB", count)
    return count


def buscar_opcoes_dados(db, tickers: list[str] | None = None) -> dict[str, dict]:
    """Busca dados de opções do DB para os tickers informados."""
    conn = db.connect()
    if tickers:
        placeholders = ",".join("?" for _ in tickers)
        cur = conn.execute(
            f"SELECT * FROM opcoes_dados WHERE ticker IN ({placeholders})", tickers
        )
    else:
        cur = conn.execute("SELECT * FROM opcoes_dados")
    rows = cur.fetchall()
    return {row["ticker"]: dict(row) for row in rows}


# ============================================================================
# CLI
# ============================================================================

def atualizar_dados_opcoes(db=None, usar_cache: bool = True) -> list[dict]:
    """
    Pipeline completo: baixa dados do OpLab, salva cache e DB.
    Se usar_cache=True e cache existir com menos de 24h, usa cache.
    """
    # Verificar idade do cache
    if usar_cache and CACHE_FILE.exists():
        mtime = CACHE_FILE.stat().st_mtime
        idade_horas = (time.time() - mtime) / 3600
        if idade_horas < 24:
            log.info("Usando cache (%.1f horas)", idade_horas)
            return carregar_cache()

    log.info("Atualizando dados do OpLab...")
    dados = baixar_lista_ativos()
    if not dados:
        log.warning("Nenhum dado extraído")
        return []

    salvar_cache(dados)
    if db is not None:
        salvar_no_db(dados, db)

    return dados


# ============================================================================
# Scraping de Séries de Opções (Vencimentos)
# ============================================================================

def extrair_json_next_data(soup: BeautifulSoup) -> Optional[dict]:
    """Extrai o JSON do __NEXT_DATA__ de uma página Next.js do OpLab."""
    next_data = soup.find("script", id="__NEXT_DATA__")
    if next_data and next_data.string:
        try:
            return json.loads(next_data.string)
        except json.JSONDecodeError:
            log.warning("Erro ao parsear __NEXT_DATA__")
            return None
    return None


def baixar_series_opcoes(ticker: str) -> dict:
    """
    Baixa todas as séries de opções de um ticker.
    Retorna o JSON completo com todas as séries, strikes e dados das opções.
    
    Retorna dict com:
        - ticker: ticker do ativo
        - series: lista de séries com strikes e dados de calls/puts
        - total_series: número de séries
        - total_opcoes: número total de opções calls + puts
    """
    url = f"{OPLAB_BASE}/acoes/opcoes/{ticker}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as e:
        log.error("Erro ao acessar %s: %s", url, e)
        return {"error": str(e), "ticker": ticker, "series": []}

    soup = BeautifulSoup(resp.content, "html.parser")
    data = extrair_json_next_data(soup)
    
    if not data:
        log.warning("Não encontrou dados __NEXT_DATA__ para %s", ticker)
        return {"error": "Sem dados", "ticker": ticker, "series": []}

    page_props = data.get("props", {}).get("pageProps", {})
    series = page_props.get("series", [])

    total_opcoes = 0
    for s in series:
        strikes = s.get("strikes", [])
        total_opcoes += len(strikes) * 2  # call + put por strike

    resultado = {
        "ticker": ticker,
        "series": series,
        "total_series": len(series),
        "total_opcoes": total_opcoes,
    }
    
    log.info(
        "Extraídas %d séries com %d opções para %s",
        len(series), total_opcoes, ticker,
    )
    return resultado


def formatar_opcoes_tabela(ticker: str, mes: str = None, ano: int = None) -> list[dict]:
    """
    Baixa opções de um ticker e formata como tabela plana para exibição/DB.
    
    Se mes e ano forem informados, filtra apenas aquela série específica.
    
    Retorna lista de dicts com:
        - ticker_original: ticker do ativo
        - serie: data de vencimento
        - dias_vencimento: dias para vencimento
        - tipo: CALL ou PUT
        - simbolo: símbolo da opção
        - strike: valor do strike
        - ultimo_preco: último preço de fechamento
        - bid: preço de compra
        - ask: preço de venda
        - volume: volume negociado
        - volume_financeiro: volume financeiro
        - variacao_pct: variação percentual
        - vi: volatilidade implícita
        - delta, gamma, vega, theta, rho: gregas
        - moneyness: ITM, ATM ou OTM
        - liquidez_texto: descrição de liquidez
        - poe: probabilidade de estar ITM
        - type: americano ou europeu
    """
    dados = baixar_series_opcoes(ticker)
    if "error" in dados or not dados.get("series"):
        log.warning("Sem opções para %s", ticker)
        return []

    # Mapeamento de mês em português para número
    meses_pt = {
        "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4,
        "maio": 5, "junho": 6, "julho": 7, "agosto": 8,
        "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
    }

    resultado = []
    for serie in dados["series"]:
        due_date = serie.get("due_date", "")
        
        # Filtrar por mês/ano se especificado
        if mes and ano:
            # Extrair mês e ano da data
            if len(due_date) >= 7:
                serie_ano = int(due_date[:4])
                serie_mes = int(due_date[5:7])
                if serie_ano != ano or serie_mes != mes:
                    continue

        dias = serie.get("days_to_maturity", 0)
        strikes = serie.get("strikes", [])

        for strike_data in strikes:
            strike_val = strike_data.get("strike", 0)
            
            # Processar CALL
            call = strike_data.get("call", {})
            if call:
                bs = call.get("bs", {})
                resultado.append({
                    "ticker_original": ticker,
                    "serie": due_date,
                    "dias_vencimento": dias,
                    "tipo": "CALL",
                    "simbolo": call.get("symbol", ""),
                    "strike": strike_val,
                    "ultimo_preco": call.get("close", 0),
                    "bid": call.get("bid", 0),
                    "ask": call.get("ask", 0),
                    "volume": call.get("volume", 0),
                    "volume_financeiro": call.get("financial_volume", 0),
                    "variacao_pct": call.get("variation", 0),
                    "vi": bs.get("vi", 0),
                    "delta": bs.get("delta", 0),
                    "gamma": bs.get("gamma", 0),
                    "vega": bs.get("vega", 0),
                    "theta": bs.get("theta", 0),
                    "rho": bs.get("rho", 0),
                    "moneyness": bs.get("moneyness", ""),
                    "liquidez_texto": bs.get("liquidity-text", ""),
                    "liquidez_level": bs.get("liquidity-level", 0),
                    "poe": bs.get("poe", 0),
                    "maturity_type": call.get("maturity_type", ""),
                    "cost_if_exercised": bs.get("cost-if-exercised", 0),
                    "protection_rate": bs.get("protection-rate", 0),
                    "profit_rate": bs.get("profit-rate", 0),
                    "volatility": bs.get("volatility", 0),
                    "ve": bs.get("ve", 0),
                })

            # Processar PUT
            put = strike_data.get("put", {})
            if put:
                bs = put.get("bs", {})
                resultado.append({
                    "ticker_original": ticker,
                    "serie": due_date,
                    "dias_vencimento": dias,
                    "tipo": "PUT",
                    "simbolo": put.get("symbol", ""),
                    "strike": strike_val,
                    "ultimo_preco": put.get("close", 0),
                    "bid": put.get("bid", 0),
                    "ask": put.get("ask", 0),
                    "volume": put.get("volume", 0),
                    "volume_financeiro": put.get("financial_volume", 0),
                    "variacao_pct": put.get("variation", 0),
                    "vi": bs.get("vi", 0),
                    "delta": bs.get("delta", 0),
                    "gamma": bs.get("gamma", 0),
                    "vega": bs.get("vega", 0),
                    "theta": bs.get("theta", 0),
                    "rho": bs.get("rho", 0),
                    "moneyness": bs.get("moneyness", ""),
                    "liquidez_texto": bs.get("liquidity-text", ""),
                    "liquidez_level": bs.get("liquidity-level", 0),
                    "poe": bs.get("poe", 0),
                    "maturity_type": put.get("maturity_type", ""),
                    "cost_if_exercised": bs.get("cost-if-exercised", 0),
                    "protection_rate": bs.get("protection-rate", 0),
                    "profit_rate": bs.get("profit-rate", 0),
                    "volatility": bs.get("volatility", 0),
                    "ve": bs.get("ve", 0),
                })

    log.info("Formatadas %d opções para %s", len(resultado), ticker)
    return resultado


def salvar_opcoes_detalhadas(db, ticker: str, options_data: list[dict]) -> int:
    """
    Salva dados detalhados de opções na tabela `opcoes_detalhes`.
    Cria a tabela se não existir.
    Retorna número de registros inseridos/atualizados.
    """
    if db is None:
        log.error("Database não fornecida")
        return 0

    conn = db.connect()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS opcoes_detalhes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker_original TEXT NOT NULL,
            simbolo TEXT NOT NULL,
            tipo TEXT NOT NULL,
            serie TEXT NOT NULL,
            dias_vencimento INTEGER,
            strike REAL,
            ultimo_preco REAL,
            bid REAL,
            ask REAL,
            volume INTEGER,
            volume_financeiro REAL,
            variacao_pct REAL,
            vi REAL,
            delta REAL,
            gamma REAL,
            vega REAL,
            theta REAL,
            rho REAL,
            moneyness TEXT,
            liquidez_texto TEXT,
            liquidez_level INTEGER,
            poe REAL,
            maturity_type TEXT,
            cost_if_exercised REAL,
            protection_rate REAL,
            profit_rate REAL,
            volatility REAL,
            ve REAL,
            atualizado_em TEXT
        )
        """
    )
    conn.commit()

    count = 0
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    
    for opt in options_data:
        conn.execute(
            """
            INSERT INTO opcoes_detalhes 
                (ticker_original, simbolo, tipo, serie, dias_vencimento, strike,
                 ultimo_preco, bid, ask, volume, volume_financeiro, variacao_pct,
                 vi, delta, gamma, vega, theta, rho, moneyness, liquidez_texto,
                 liquidez_level, poe, maturity_type, cost_if_exercised, protection_rate,
                 profit_rate, volatility, ve, atualizado_em)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                opt.get("ticker_original"), opt.get("simbolo"), opt.get("tipo"),
                opt.get("serie"), opt.get("dias_vencimento"), opt.get("strike"),
                opt.get("ultimo_preco"), opt.get("bid"), opt.get("ask"),
                opt.get("volume"), opt.get("volume_financeiro"), opt.get("variacao_pct"),
                opt.get("vi"), opt.get("delta"), opt.get("gamma"), opt.get("vega"),
                opt.get("theta"), opt.get("rho"), opt.get("moneyness"),
                opt.get("liquidez_texto"), opt.get("liquidez_level"), opt.get("poe"),
                opt.get("maturity_type"), opt.get("cost_if_exercised"),
                opt.get("protection_rate"), opt.get("profit_rate"),
                opt.get("volatility"), opt.get("ve"), now,
            ),
        )
        count += 1

    conn.commit()
    log.info("Salvos %d registros de opções detalhadas no DB", count)
    return count


def buscar_opcoes_serie(db, ticker: str, serie: str = None) -> list[dict]:
    """Busca opções detalhadas do DB para um ticker, opcionalmente filtra por série."""
    conn = db.connect()
    
    # Garantir que a tabela existe antes de consultar
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS opcoes_detalhes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker_original TEXT NOT NULL,
            simbolo TEXT NOT NULL,
            tipo TEXT NOT NULL,
            serie TEXT NOT NULL,
            dias_vencimento INTEGER,
            strike REAL,
            ultimo_preco REAL,
            bid REAL,
            ask REAL,
            volume INTEGER,
            volume_financeiro REAL,
            variacao_pct REAL,
            vi REAL,
            delta REAL,
            gamma REAL,
            vega REAL,
            theta REAL,
            rho REAL,
            moneyness TEXT,
            liquidez_texto TEXT,
            liquidez_level INTEGER,
            poe REAL,
            maturity_type TEXT,
            cost_if_exercised REAL,
            protection_rate REAL,
            profit_rate REAL,
            volatility REAL,
            ve REAL,
            atualizado_em TEXT
        )
        """
    )
    conn.commit()
    
    if serie:
        cur = conn.execute(
            "SELECT * FROM opcoes_detalhes WHERE ticker_original = ? AND serie = ? ORDER BY strike, tipo",
            (ticker, serie),
        )
    else:
        cur = conn.execute(
            "SELECT * FROM opcoes_detalhes WHERE ticker_original = ? ORDER BY serie, strike, tipo",
            (ticker,),
        )
    return [dict(row) for row in cur.fetchall()]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from system.core.db import Database
    from pathlib import Path as P

    instance_dir = P(__file__).resolve().parent.parent / "instance"
    _db = Database(get_db_path(instance_dir))
    resultados = atualizar_dados_opcoes(_db, usar_cache=False)
    print(f"✅ {len(resultados)} ativos atualizados")
    for a in resultados[:5]:
        print(f"  {a['ticker']}: VI={a.get('vi')}% IVR={a.get('iv_rank')}%")
    
    # Testar novo scraping de séries
    print("\n=== Testando scraping de séries de opções ===")
    ticker = "PETR4"
    opcoes = formatar_opcoes_tabela(ticker)
    if opcoes:
        print(f"✅ {len(opcoes)} opções encontradas para {ticker}")
        print(f"\nPrimeiras 3 opções:")
        for opt in opcoes[:3]:
            print(f"  {opt['simbolo']} | {opt['tipo']} | Strike: {opt['strike']} | VI: {opt['vi']}% | Moneyness: {opt['moneyness']}")

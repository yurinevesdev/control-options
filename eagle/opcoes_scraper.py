"""
Yuri System — Scraper de dados de opções (OpLab).

Baseado no projeto sinais-compra-ou-venda/scraping.py
Extrai volatilidade implícita, IV Rank e IV Percentil para uso
nas análises do Yuri System.
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

from eagle.logger import get_logger

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
# Integração com DB do Yuri System
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


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from eagle.db import Database, get_db_path
    from pathlib import Path as P

    instance_dir = P(__file__).resolve().parent.parent / "instance"
    _db = Database(get_db_path(instance_dir))
    resultados = atualizar_dados_opcoes(_db, usar_cache=False)
    print(f"✅ {len(resultados)} ativos atualizados")
    for a in resultados[:5]:
        print(f"  {a['ticker']}: VI={a.get('vi')}% IVR={a.get('iv_rank')}%")
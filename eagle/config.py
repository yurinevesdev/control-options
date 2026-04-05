"""
Yuri System — Configuração centralizada.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Any

# ============================================================================
# Black-Scholes
# ============================================================================

BS_RATE: float = float(os.environ.get("EAGLE_RATE", "0.1075"))
BS_DIVIDEND_YIELD: float = float(os.environ.get("EAGLE_DIVIDEND_YIELD", "0.0"))

# ============================================================================
# Base de dados
# ============================================================================

DB_DIR: Path = Path(__file__).resolve().parent.parent / "instance"
DB_FILENAME: str = os.environ.get("EAGLE_DB", "eagle_opcoes_v2.sqlite")
DB_PATH: Path = DB_DIR / DB_FILENAME

# ============================================================================
# Aplicação
# ============================================================================

SECRET_KEY: str = os.environ.get("EAGLE_SECRET", secrets.token_hex(32))
DEBUG: bool = os.environ.get("EAGLE_DEBUG", "1").lower() in ("1", "true", "yes")
HOST: str = os.environ.get("EAGLE_HOST", "127.0.0.1")
PORT: int = int(os.environ.get("EAGLE_PORT", "5000"))

# ============================================================================
# Tipos de estratégia predefinidos
# ============================================================================

ESTRATEGIAS: dict[str, dict[str, Any]] = {
    "Bull Call Spread": {
        "pernas": [
            {"operacao": "compra", "tipo": "call", "premio_pct": 0.05},
            {"operacao": "venda", "tipo": "call", "premio_pct": 0.02},
        ],
    },
    "Bear Put Spread": {
        "pernas": [
            {"operacao": "compra", "tipo": "put", "premio_pct": 0.05},
            {"operacao": "venda", "tipo": "put", "premio_pct": 0.02},
        ],
    },
    "Iron Condor": {
        "pernas": [
            {"operacao": "compra", "tipo": "put", "premio_pct": 0.02},
            {"operacao": "venda", "tipo": "put", "premio_pct": 0.03},
            {"operacao": "venda", "tipo": "call", "premio_pct": 0.03},
            {"operacao": "compra", "tipo": "call", "premio_pct": 0.02},
        ],
    },
    "Iron Butterfly": {
        "pernas": [
            {"operacao": "compra", "tipo": "put", "premio_pct": 0.02},
            {"operacao": "venda", "tipo": "put", "premio_pct": 0.05},
            {"operacao": "venda", "tipo": "call", "premio_pct": 0.05},
            {"operacao": "compra", "tipo": "call", "premio_pct": 0.02},
        ],
    },
    "Butterfly Call": {
        "pernas": [
            {"operacao": "compra", "tipo": "call", "premio_pct": 0.07},
            {"operacao": "venda", "tipo": "call", "premio_pct": 0.03},
            {"operacao": "venda", "tipo": "call", "premio_pct": 0.03},
            {"operacao": "compra", "tipo": "call", "premio_pct": 0.01},
        ],
    },
    "Put Butterfly": {
        "pernas": [
            {"operacao": "compra", "tipo": "put", "premio_pct": 0.07},
            {"operacao": "venda", "tipo": "put", "premio_pct": 0.03},
            {"operacao": "venda", "tipo": "put", "premio_pct": 0.03},
            {"operacao": "compra", "tipo": "put", "premio_pct": 0.01},
        ],
    },
    "Straddle": {
        "pernas": [
            {"operacao": "compra", "tipo": "call", "premio_pct": 0.04},
            {"operacao": "compra", "tipo": "put", "premio_pct": 0.04},
        ],
    },
    "Strangle": {
        "pernas": [
            {"operacao": "compra", "tipo": "call", "premio_pct": 0.02},
            {"operacao": "compra", "tipo": "put", "premio_pct": 0.02},
        ],
    },
    "Calendária Call": {
        "pernas": [
            {"operacao": "venda", "tipo": "call", "premio_pct": 0.03},
        ],
        "nota": "Adicionar perna de vencimento mais longo manualmente",
    },
}

ESTRATEGIAS_LIST = ["Personalizada"] + list(ESTRATEGIAS.keys())
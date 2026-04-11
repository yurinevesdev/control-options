"""
Yuri System — Configuração centralizada.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

ROOT_DIR = Path(__file__).resolve().parent.parent
DOTENV_PATH = ROOT_DIR / ".env"

if load_dotenv is not None:
    load_dotenv(dotenv_path=DOTENV_PATH)

# ============================================================================
# Black-Scholes
# ============================================================================

BS_RATE: float = float(os.environ.get("SYSTEM_RATE", "0.1075"))
BS_DIVIDEND_YIELD: float = float(os.environ.get("SYSTEM_DIVIDEND_YIELD", "0.0"))

# ============================================================================
# Base de dados
# ============================================================================

DB_DIR: Path = Path(__file__).resolve().parent.parent / "instance"
DB_FILENAME: str = os.environ.get("SYSTEM_DB", "SYSTEM_opcoes_v2.sqlite")
DB_PATH: Path = DB_DIR / DB_FILENAME

# ============================================================================
# Aplicação
# ============================================================================

SECRET_KEY: str = os.environ.get("SYSTEM_SECRET", secrets.token_hex(32))
DEBUG: bool = os.environ.get("SYSTEM_DEBUG", "1").lower() in ("1", "true", "yes")
HOST: str = os.environ.get("SYSTEM_HOST", "127.0.0.1")
PORT: int = int(os.environ.get("SYSTEM_PORT", "5000"))

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

# ============================================================================
# Notificações por E-mail
# ============================================================================

# Configurações SMTP (Gmail)
SMTP_SERVER: str = os.environ.get("SYSTEM_SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT: int = int(os.environ.get("SYSTEM_SMTP_PORT", "587"))
FROM_EMAIL: str = os.environ.get("SYSTEM_FROM_EMAIL", "yurineves1934@gmail.com")
EMAIL_PASSWORD: str = os.environ.get("SYSTEM_EMAIL_PASSWORD", "")  # App password do Gmail
TO_EMAIL: str = os.environ.get("SYSTEM_TO_EMAIL", "yurineves1934@gmail.com")

# Alerta: quantos dias antes do vencimento enviar notificação
DIAS_ALERTA: int = int(os.environ.get("SYSTEM_DIAS_ALERTA", "2"))

# Background scheduler: hora para disparar verificação diária (formato 24h: "09:00")
SCHEDULER_HORA: str = os.environ.get("SYSTEM_SCHEDULER_HORA", "09:00")

# Ativar notificações por e-mail
EMAIL_NOTIFICACOES_ATIVAS: bool = os.environ.get("SYSTEM_EMAIL_NOTIF", "1").lower() in ("1", "true", "yes")
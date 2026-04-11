"""Yuri System - System package

Módulos organizados por funcionalidade:
- core: motor matemático (Black-Scholes) e persistência (DB)
- ui: interface, logger, formatação
- data: scraping, importação/exportação, atualização de dados
- analysis: indicadores e sugestões
- notifications: alertas e agendador
"""

# Expor módulos principais para compatibilidade de imports
from system.core import Database, blackscholes  # noqa: F401
from system.config import *  # noqa: F401, F403
from system.ui import get_logger, setup_logging, brl, color_pnl, dias_ate_venc, fmt_date  # noqa: F401


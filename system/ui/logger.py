"""
System — Configuração de logging.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_initialized: bool = False


def setup_logging(
    level: int = logging.INFO,
    log_file: Path | str | None = None,
    colorize: bool = True,
) -> logging.Logger:
    """Configura logging global e devolve o logger raiz."""
    global _initialized
    if _initialized:
        return logging.getLogger("system")

    _initialized = True

    fmt = "%(asctime)s [%(levelname)-7s] %(name)s — %(message)s"

    # Colorização simples para dev
    class _ColorFormatter(logging.Formatter):
        COLORS = {
            logging.DEBUG: "\033[36m",
            logging.INFO: "\033[32m",
            logging.WARNING: "\033[33m",
            logging.ERROR: "\033[31m",
            logging.CRITICAL: "\033[35m",
        }
        RESET = "\033[0m"

        def format(self, record: logging.LogRecord) -> str:
            color = self.COLORS.get(record.levelno, "") if colorize else ""
            record.levelname = f"{color}{record.levelname}{self.RESET}"
            return super().format(record)

    formatter = _ColorFormatter(fmt, datefmt="%Y-%m-%d %H:%M:%S")

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)

    # Criar arquivo de log se não existir
    if log_file is None:
        log_file = Path(__file__).resolve().parent.parent.parent / "logs" / "app.log"

    log_file = Path(log_file)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(logging.Formatter(fmt))
    root.addHandler(fh)

    # Suprimir logs ruidosos
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    logging.getLogger("sqlite3").setLevel(logging.WARNING)
    logging.getLogger("flask").setLevel(logging.WARNING)

    return logging.getLogger("system")


def get_logger(name: str = "system") -> logging.Logger:
    """Obtém logger do módulo."""
    return logging.getLogger(name)
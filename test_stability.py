#!/usr/bin/env python3
"""
Script para testar de forma controlada e detectar quando o servidor trava.
Acessa cada página e monitora respostas.
"""

import sys
import time
import requests
from datetime import datetime
from pathlib import Path

# Cores
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

BASE_URL = "http://localhost:5000"

PAGES = [
    ("/", "Índice"),
    ("/simulador", "Simulador"),
    ("/historico", "Histórico"),
    ("/dashboard", "Dashboard"),
    ("/opcoes", "Opções"),
    ("/sugestoes", "Sugestões"),
    ("/carteira", "Carteira"),
]

def log_time():
    return datetime.now().strftime("%H:%M:%S")

def test_page(path, name):
    """Testa uma página e reporta resultado."""
    try:
        print(f"{BLUE}[{log_time()}]{RESET} Testando {name:20} {path:20} ", end="", flush=True)

        start = time.time()
        response = requests.get(f"{BASE_URL}{path}", timeout=10)
        elapsed = time.time() - start

        if response.status_code == 200:
            print(f"{GREEN}✓ OK{RESET} ({elapsed:.2f}s)")
            return True
        else:
            print(f"{YELLOW}⚠ {response.status_code}{RESET} ({elapsed:.2f}s)")
            return False

    except requests.Timeout:
        print(f"{RED}✗ TIMEOUT{RESET} (>10s) — SERVIDOR PODE ESTAR TRAVADO!")
        return False
    except requests.ConnectionError:
        print(f"{RED}✗ CONEXÃO RECUSADA{RESET} — SERVIDOR PAROU!")
        return False
    except Exception as e:
        print(f"{RED}✗ ERRO{RESET}: {str(e)}")
        return False

def main():
    print(f"""
{BLUE}╔══════════════════════════════════════════════════════════════════╗
║           🔍 TESTADOR DE ESTABILIDADE DO SERVIDOR                ║
║                                                                  ║
║  Este script testa cada página para detectar travamentos        ║
║  Se alguma página não responder em 10s, o servidor TRAVOU       ║
╚══════════════════════════════════════════════════════════════════╝{RESET}
""")

    # Verificar se servidor está online
    try:
        requests.get(BASE_URL, timeout=5)
    except Exception as e:
        print(f"{RED}✗ Erro: Servidor não está respondendo em {BASE_URL}{RESET}")
        print(f"  Inicie o servidor com: python app.py")
        sys.exit(1)

    print(f"{GREEN}✓ Servidor detectado em {BASE_URL}{RESET}\n")

    iterations = 1
    while True:
        print(f"{BLUE}━━━ Iteração {iterations} ━━━{RESET}")

        failed = 0
        for path, name in PAGES:
            if not test_page(path, name):
                failed += 1

        if failed > 0:
            print(f"\n{RED}✗ {failed} página(s) falharam!{RESET}")
            print(f"{YELLOW}Verifique logs/app.log para mais detalhes:{RESET}")
            print(f"  tail -50 logs/app.log")
        else:
            print(f"{GREEN}✓ Todas as páginas responderam com sucesso!{RESET}")

        print()
        print(f"{BLUE}Próximo teste em 10 segundos (Ctrl+C para parar)...{RESET}")
        try:
            time.sleep(10)
        except KeyboardInterrupt:
            print(f"\n{BLUE}Teste interrompido.{RESET}")
            break

        iterations += 1

if __name__ == "__main__":
    main()

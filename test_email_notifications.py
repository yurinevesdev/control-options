#!/usr/bin/env python3
"""
Script de teste para funcionalidade de notificações por e-mail.
Verifica configuração e envia notificação de teste.
"""

import sys
import os
from pathlib import Path

# Adicionar diretório ao path
sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """Testa se todos os módulos podem ser importados."""
    print("\n🔍 Testando imports...")
    try:
        from eagle.email_notifier import criar_notificador
        print("  ✓ email_notifier")
        
        from eagle.scheduler import iniciar_scheduler
        print("  ✓ scheduler")
        
        from eagle.db import Database
        print("  ✓ database")
        
        from eagle import config
        print("  ✓ config")
        
        return True
    except ImportError as e:
        print(f"  ✗ Erro de importação: {e}")
        return False


def test_config():
    """Testa se as configurações estão presentes."""
    print("\n⚙️  Testando configurações...")
    from eagle import config
    
    required_vars = [
        "SMTP_SERVER",
        "SMTP_PORT", 
        "FROM_EMAIL",
        "EMAIL_PASSWORD",
        "TO_EMAIL",
        "DIAS_ALERTA",
        "SCHEDULER_HORA",
        "EMAIL_NOTIFICACOES_ATIVAS"
    ]
    
    missing = []
    for var in required_vars:
        value = getattr(config, var, None)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(var)
            print(f"  ⚠ {var}: vazio ou não configurado")
        else:
            if var == "EMAIL_PASSWORD":
                print(f"  ✓ {var}: ***")
            else:
                print(f"  ✓ {var}: {value}")
    
    if missing:
        print(f"\n⚠️  Variáveis não configuradas: {', '.join(missing)}")
        print("   Configure variáveis de ambiente ou .env e tente novamente")
        return False
    
    return True


def test_smtp_connection():
    """Testa conexão com servidor SMTP."""
    print("\n🔗 Testando conexão SMTP...")
    
    try:
        from eagle.email_notifier import criar_notificador
        from eagle import config
        
        if not config.EMAIL_PASSWORD:
            print("  ⚠ EMAIL_PASSWORD não configurado")
            return False
        
        notificador = criar_notificador()
        server = notificador._conectar_smtp()
        server.quit()
        print("  ✓ Conexão SMTP bem-sucedida")
        return True
        
    except Exception as e:
        print(f"  ✗ Erro na conexão SMTP: {e}")
        print("\n💡 Dicas:")
        print("  - Verifique se 2FA está ativado no Gmail")
        print("  - Use App Password, não senha comum")
        print("  - Remova espaços da App Password em .env")
        print("  - Verifique configurações de firewall/VPN")
        return False


def test_database():
    """Testa acesso ao banco de dados."""
    print("\n💾 Testando banco de dados...")
    
    try:
        from eagle import config
        from eagle.db import Database
        db = Database(config.DB_PATH)
        conn = db.connect()  # ← connect() retorna a conexão diretamente
        
        # Verificar se tabelas existem
        cursor = conn.cursor()  # ← usar o retorno do connect()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        if not tables:
            print("  ⚠ Nenhuma tabela encontrada no banco")
            db.close()
            return False
        
        print(f"  ✓ Banco acessível ({len(tables)} tabelas)")
        db.close()
        return True
        
    except Exception as e:
        print(f"  ✗ Erro ao acessar banco: {e}")
        return False


def test_send_notification():
    """Envia notificação de teste."""
    print("\n📧 Testando envio de notificação...")
    
    try:
        from eagle.email_notifier import criar_notificador
        from eagle.db import Database
        
        from eagle import config
        db = Database(config.DB_PATH)
        db.connect()
        
        notificador = criar_notificador()
        opcoes = notificador.obter_opcoes_proximas_vencimento(db)
        
        if not opcoes:
            print("  ⚠ Nenhuma opção próxima do vencimento encontrada")
            print("  (Crie uma estrutura com vencimento em 2 dias para testar)")
            db.close()
            return True  # Não é falha, apenas sem dados
        
        print(f"  ✓ Encontradas {len(opcoes)} opções próximas ao vencimento")
        
        sucesso = notificador.enviar_notificacao(db)
        if sucesso:
            print("  ✓ E-mail enviado com sucesso!")
        else:
            print("  ⚠ E-mail não foi enviado (sem opções próximas)")
        
        db.close()
        return sucesso
        
    except Exception as e:
        print(f"  ✗ Erro ao enviar notificação: {e}")
        return False

def test_force_send():
    """Força envio de e-mail com dados fictícios para validar SMTP."""
    print("\n📤 Forçando envio com dados fictícios...")
    
    try:
        from eagle.email_notifier import criar_notificador
        
        notificador = criar_notificador()
        
        # Dados fictícios para teste
        opcoes_fake = [
            {
                "estrutura_id": 1,
                "estrutura_nome": "Teste Iron Condor",
                "leg_id": 1,
                "tipo": "CALL",
                "strike": 120.00,
                "vencimento": "2026-04-13",
                "dias_faltam": 2.0,
                "preco_spot": 125.50,
                "preco_atual": 3.20,
                "operacao": "venda",
                "intrinseco": 5.50,
                "sera_exercida": True,
                "status": "SIM - ITM (S=125.50 > K=120.00)",
            },
            {
                "estrutura_id": 1,
                "estrutura_nome": "Teste Iron Condor",
                "leg_id": 2,
                "tipo": "PUT",
                "strike": 110.00,
                "vencimento": "2026-04-13",
                "dias_faltam": 2.0,
                "preco_spot": 125.50,
                "preco_atual": 0.80,
                "operacao": "compra",
                "intrinseco": 0.0,
                "sera_exercida": False,
                "status": "NÃO - OTM (K=110.00 ≤ S=125.50)",
            },
        ]
        
        # Gerar HTML e enviar diretamente
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        msg = MIMEMultipart("alternative")
        msg["From"] = notificador.from_email
        msg["To"] = notificador.to_email
        msg["Subject"] = "🧪 Yuri System — Teste de Notificação (dados fictícios)"
        
        html = notificador._gerar_html_email(opcoes_fake)
        msg.attach(MIMEText(html, "html", _charset="utf-8"))
        
        server = notificador._conectar_smtp()
        server.send_message(msg)
        server.quit()
        
        print(f"  ✓ E-mail enviado para {notificador.to_email}")
        print("  ✓ Verifique sua caixa de entrada (e spam)")
        return True
        
    except Exception as e:
        print(f"  ✗ Erro: {e}")
        return False

def main():
    """Executa todos os testes."""
    print("\n" + "="*60)
    print("🧪 Teste de Notificações por E-mail — Yuri System")
    print("="*60)
    
    results = {}
    
    results['imports'] = test_imports()
    if not results['imports']:
        print("\n❌ Falha ao importar módulos. Instale dependências:")
        print("   pip install -r requirements.txt")
        return False
    
    results['config'] = test_config()
    if not results['config']:
        print("\n📝 Configure as variáveis:")
        print("   Copie .env.example para .env e preencha as variáveis")
        return False
    
    results['smtp'] = test_smtp_connection()
    if not results['smtp']:
        return False
    
    results['db'] = test_database()
    
    results['notify'] = test_send_notification()

    results['force_send'] = test_force_send()

    # Resumo
    print("\n" + "="*60)
    print("📊 Resumo dos Testes:")
    print("="*60)
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"\n✓ {passed}/{total} testes passaram")
    
    if passed == total:
        print("\n✅ Tudo OK! Notificações por e-mail estão configuradas.")
        print("\n📌 Próximos passos:")
        print("  1. Inicie a aplicação: python3 app.py")
        print("  2. O scheduler disparará verificações diárias")
        print("  3. Veja os logs: tail -f debug-logs/*.log")
        return True
    else:
        print("\n❌ Alguns testes falharam. Veja os detalhes acima.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

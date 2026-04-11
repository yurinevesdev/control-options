# 📧 Configuração de Notificações por E-mail — Yuri System

## Visão Geral

O Yuri System inclui uma funcionalidade de **notificação automática por e-mail** que:
- ✅ Verifica opções próximas do vencimento diariamente
- ✅ Determina se serão exercidas (ITM/OTM)
- ✅ Envia relatório formatado com situação das opções

---

## 1. Configuração com Gmail (Recomendado)

### Passo 1: Ativar 2FA no Gmail
1. Acesse [myaccount.google.com/security](https://myaccount.google.com/security)
2. Verifique se a **Verificação em Duas Etapas** está **ativada**
3. Se não estiver, realize a configuração

### Passo 2: Gerar App Password
1. Acesso [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. Selecione:
   - **App:** Mail
   - **Dispositivo:** Windows/Mac/Linux
3. Clique em **Gerar**
4. Copie a senha gerada (16 caracteres com espaços)
   - Exemplo: `abcd efgh ijkl mnop`

### Passo 3: Configurar Variáveis de Ambiente

#### No Linux/macOS (arquivo `.env` na raiz do projeto):
```bash
# .env

# Configurações de E-mail (Gmail)
EAGLE_FROM_EMAIL=yurineves1934@gmail.com
EAGLE_EMAIL_PASSWORD=abcdefghijklmnop  # App password (sem espaços)
EAGLE_TO_EMAIL=yurineves1934@gmail.com
EAGLE_SMTP_SERVER=smtp.gmail.com
EAGLE_SMTP_PORT=587

# Dias antes do vencimento para enviar alerta
EAGLE_DIAS_ALERTA=2

# Hora do dia para disparar verificação (formato 24h: HH:MM)
EAGLE_SCHEDULER_HORA=09:00

# Ativar/desativar notificações
EAGLE_EMAIL_NOTIF=1
```

#### No Windows (PowerShell):
```powershell
# PowerShell como Admin
[Environment]::SetEnvironmentVariable("EAGLE_FROM_EMAIL", "yurineves1934@gmail.com", "User")
[Environment]::SetEnvironmentVariable("EAGLE_EMAIL_PASSWORD", "abcdefghijklmnop", "User")
[Environment]::SetEnvironmentVariable("EAGLE_TO_EMAIL", "yurineves1934@gmail.com", "User")
[Environment]::SetEnvironmentVariable("EAGLE_SMTP_SERVER", "smtp.gmail.com", "User")
[Environment]::SetEnvironmentVariable("EAGLE_SMTP_PORT", "587", "User")
[Environment]::SetEnvironmentVariable("EAGLE_DIAS_ALERTA", "2", "User")
[Environment]::SetEnvironmentVariable("EAGLE_SCHEDULER_HORA", "09:00", "User")
[Environment]::SetEnvironmentVariable("EAGLE_EMAIL_NOTIF", "1", "User")
```

### Passo 4: Instalar Dependências
```bash
pip install -r requirements.txt
```

### Passo 5: Executar a Aplicação
```bash
python3 app.py
```

Ao iniciar, você verá:
```
✓ Scheduler iniciado | Tarefa diária agendada para 09:00
```

---

## 2. Configuração com Outros Provedores SMTP

### Outlook / Hotmail
```bash
EAGLE_SMTP_SERVER=smtp-mail.outlook.com
EAGLE_SMTP_PORT=587
EAGLE_FROM_EMAIL=seu_email@outlook.com
EAGLE_EMAIL_PASSWORD=sua_senha
EAGLE_TO_EMAIL=seu_email@outlook.com
```

### Gmail (Without App Password)
Se preferir usar sua senha normal (menos seguro):
```bash
EAGLE_FROM_EMAIL=yurineves1934@gmail.com
EAGLE_EMAIL_PASSWORD=sua_senha_gmail
```

### Servidor SMTP Customizado
```bash
EAGLE_SMTP_SERVER=smtp.seuservidor.com
EAGLE_SMTP_PORT=587  # ou 465 para SSL
EAGLE_FROM_EMAIL=usuario@seuservidor.com
EAGLE_EMAIL_PASSWORD=sua_senha
EAGLE_TO_EMAIL=destinatario@email.com
```

---

## 3. Variáveis de Configuração

| Variável | Default | Descrição |
|----------|---------|-----------|
| `EAGLE_FROM_EMAIL` | yurineves1934@gmail.com | E-mail do remetente |
| `EAGLE_EMAIL_PASSWORD` | `` | Senha ou app password (OBRIGATÓRIO) |
| `EAGLE_TO_EMAIL` | yurineves1934@gmail.com | E-mail do destinatário |
| `EAGLE_SMTP_SERVER` | smtp.gmail.com | Servidor SMTP |
| `EAGLE_SMTP_PORT` | 587 | Porta SMTP (587 = TLS, 465 = SSL) |
| `EAGLE_DIAS_ALERTA` | 2 | Dias antes do vencimento (1-30) |
| `EAGLE_SCHEDULER_HORA` | 09:00 | Hora da verificação diária |
| `EAGLE_EMAIL_NOTIF` | 1 | Habilita (1) ou desabilita (0) notificações |

---

## 4. Conteúdo do E-mail

### Exemplo de Notificação Recebida

```
Subject: 🔔 Yuri System - Alerta de 4 Opção(ões) Próximas ao Vencimento

┌─────────────────────────────────────────────────────────────┐
│ 📊 Bull Call Spread (PETR4)                                │
├─────────────────────────────────────────────────────────────┤
│ Tipo  │ Strike  │ Vencimento │ Dias │ Spot  │ Intrínseco │ Exercida? │
├───────┼─────────┼────────────┼──────┼───────┼────────────┼───────────┤
│ CALL  │ 28.00   │ 2026-04-20 │  9   │ 29.50 │ 1.50       │ SIM - ITM │
│ CALL  │ 30.00   │ 2026-04-20 │  9   │ 29.50 │ 0.00       │ NÃO - OTM │
└─────────────────────────────────────────────────────────────┘
```

**Informações incluídas:**
- ✅ Estrutura (nome da estratégia)
- ✅ Tipo de opção (CALL/PUT)
- ✅ Strike e vencimento
- ✅ Dias até vencimento
- ✅ Preço spot (S) vs Strike (K)
- ✅ Valor intrínseco
- ✅ Status: **SIM (Verde)** = será exercida | **NÃO (Laranja)** = não será exercida

---

## 5. Verificação Manual

### Teste de Conectividade SMTP
```bash
python3 -c "
from eagle.email_notifier import criar_notificador
from eagle.config import Config
notificador = criar_notificador()
try:
    server = notificador._conectar_smtp()
    server.quit()
    print('✓ Conexão SMTP OK')
except Exception as e:
    print(f'✗ Erro: {e}')
"
```

### Forçar Envio Manual
```bash
python3 -c "
from eagle.email_notifier import criar_notificador
from eagle.db import Database
db = Database()
notificador = criar_notificador()
sucesso = notificador.enviar_notificacao(db)
db.close()
if sucesso:
    print('✓ E-mail enviado')
else:
    print('⚠ Nenhuma opção próxima ou erro')
"
```

---

## 6. Troubleshooting

### Erro: "SMTP authentication failed"
- Verifique se digitou a **App Password** corretamente (sem espaços)
- Verifique se o 2FA está ativado no Gmail
- Tente gerar uma nova App Password

### Erro: "Connection refused / Timeout"
- Verifique sua conexão de internet
- Tente uma porta diferente: `EAGLE_SMTP_PORT=465`
- Se usa VPN/Proxy, desative temporariamente

### E-mail não é recebido
- Verifique spam/lixo eletrônico
- Confirme que `EAGLE_TO_EMAIL` está correto
- Verifique os logs: `tail -f debug-logs/*.log`

### Scheduler não inicia
- Verifique se `apscheduler` foi instalado: `pip install apscheduler`
- Verifique formato da hora: `EAGLE_SCHEDULER_HORA=09:00` (24h)
- Veja os logs da aplicação

---

## 7. Desabilitar Notificações

Para desabilitar temporariamente as notificações sem remover configurações:

```bash
# .env
EAGLE_EMAIL_NOTIF=0
```

Reinicie a aplicação. O scheduler não será iniciado.

---

## 8. Logs de Notificacão

Os logs de scheduled notificações são salvos em:
- `debug-logs/scheduler.log` (criado automaticamente)
- `debug-logs/email_notifier.log`

Acompanhe em tempo real:
```bash
tail -f debug-logs/*.log | grep -E "(scheduler|email_notifier|✓|✗|Tarefa)"
```

---

## 9. Backup & Segurança

### ⚠️ Não commitar App Password
Adicione ao `.gitignore`:
```bash
.env
.env.local
*.env
```

### Como fazer backup das configurações
```bash
# Salve as variáveis de ambiente em local seguro
env | grep EAGLE_ > ~/eagle_config.backup
```

---

## 10. Limites de Taxa (Rate Limits)

- **Gmail:** ~100 mensagens/dia (por App Password)
- **Scheduler:** 1 execução/dia (horário configurável)

Se precisar enviar mais mensagens, considere um serviço como SendGrid ou Mailgun.

---

## Suporte

Se encontrar problemas:

1. Verifique os logs: `cat debug-logs/email_notifier.log`
2. Teste conexão SMTP manualmente
3. Confirme todas as variáveis de ambiente
4. Verifique ACL/firewall local

---

**Última atualização:** 11/04/2026

# 🚀 Guia Rápido — Notificações por E-mail

## Objetivo

Receber **e-mail diário** com alertas de opções próximas do vencimento, indicando se serão exercidas ou não.

---

## ⚡ Setup Rápido (5 min)

### 1️⃣ Configurar Gmail

**No Gmail (myaccount.google.com):**
1. Ative **2FA** (Verificação em Duas Etapas) se ainda não estiver
2. Vá para **myaccount.google.com/apppasswords**
3. Selecione: **Mail** + **Linux/Mac** (seu SO)
4. Clique em **Gerar**
5. Copie a senha (16 caracteres com espaços)

### 2️⃣ Configurar Arquivo `.env`

Copie `.env.example` e renomeie para `.env`:

```bash
cp .env.example .env
nano .env
```

Edite e preenchche:
```bash
EAGLE_FROM_EMAIL=yurineves1934@gmail.com
EAGLE_EMAIL_PASSWORD=abcd efgh ijkl mnop  # App password (SEM espaços na prática)
EAGLE_TO_EMAIL=yurineves1934@gmail.com
EAGLE_DIAS_ALERTA=2
EAGLE_SCHEDULER_HORA=09:00
EAGLE_EMAIL_NOTIF=1
```

### 3️⃣ Instalar Dependências

```bash
pip install -r requirements.txt
```

### 4️⃣ Testar

```bash
python3 test_email_notifications.py
```

**Esperado:**
```
✓ email_notifier
✓ scheduler
✓ database
✓ Conexão SMTP bem-sucedida
✓ Banco acessível
✓ Tudo OK! Notificações por e-mail estão configuradas.
```

---

## ▶️ Iniciar a Aplicação

```bash
python3 app.py
```

Você verá:
```
✓ Scheduler iniciado | Tarefa diária agendada para 09:00
```

---

## 📧 O que Você Recebe

**Exemplo de e-mail:**

```
🔔 Yuri System - Alerta de 2 Opção(ões) Próximas ao Vencimento

📊 Bull Call Spread (PETR4)

┌────────────────────────────────────────────────┐
│ Tipo │ Strike │ Vencimento │ Dias │ Será Exer. │
├────────────────────────────────────────────────┤
│ CALL │ 28.00  │ 2026-04-20 │  2   │ SIM - ITM  │
│ CALL │ 30.00  │ 2026-04-20 │  2   │ NÃO - OTM  │
└────────────────────────────────────────────────┘
```

---

## 🆘 Problemas?

| Erro | Solução |
|------|---------|
| "SMTP authentication failed" | Verifique app password, remova espaços |
| "Connection refused" | Verifique firewall/VPN, tente porta 465 |
| "No module named apscheduler" | `pip install apscheduler` |
| "Nenhuma opção próxima" | Crie estrutura com vencimento em ≤ 2 dias |

---

## 📋 Variáveis de Ambiente

| Variável | Default | O que é |
|----------|---------|---------|
| `EAGLE_FROM_EMAIL` | seu_email | Remetente |
| `EAGLE_EMAIL_PASSWORD` | - | App password do Gmail |
| `EAGLE_TO_EMAIL` | seu_email | Destinatário |
| `EAGLE_DIAS_ALERTA` | 2 | Alertar X dias antes |
| `EAGLE_SCHEDULER_HORA` | 09:00 | Hora da verificação |
| `EAGLE_EMAIL_NOTIF` | 1 | 1=ativa, 0=desativa |

---

## 📖 Documentação Completa

Veja [README.EMAIL.md](README.EMAIL.md) para:
- Setup com Outlook/outros
- Configuração manual de SMTP
- Troubleshooting detalhado
- Backup & Segurança

---

## ✅ Pronto!

Seu Yuri System agora **notifica você automaticamente** quando opções estão perto de vencer! 🎉


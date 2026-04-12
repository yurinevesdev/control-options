# 🔍 Capturando o Travamento do Servidor

Seu servidor está **parando silenciosamente**. Com os novos logs e ferramentas, vamos identificar exatamente quando e por quê!

## 🚀 Como Debugar

### Terminal 1: Ver logs em tempo real

```bash
./watch_logs.sh
```

Ou manualmente:
```bash
tail -f logs/app.log
```

### Terminal 2: Testar servidor automaticamente

```bash
python test_stability.py
```

Este script:
- ✅ Acessa cada página da aplicação
- ⏱️ Se alguma demorar >10s → **SERVIDOR TRAVOU**
- 📋 Repete a cada 10 segundos para capturar quando falha
- 🔴 Mostra exatamente em qual página/ação trava

### Terminal 3: Rodar o servidor

```bash
python app.py
```

---

## 📊 Interpretando os Resultados

### Situação 1: Resposta Lenta (Pode levar à trava)
```
14:35:22 Testando Dashboard         ... ✓ OK (8.5s)
         ↑ Sistema tem resposta, mas muito lento
```
**Ação:** Aumentar timeout ou investigar DB lento

### Situação 2: Timeout (SERVIDOR TRAVOU!)
```
14:35:22 Testando Dashboard         ... ✗ TIMEOUT (>10s)
         ↑ Servidor não respondeu! TRAVOU!
```
**Ação:** Olhe os logs - haverá ERROR apontando o problema

### Situação 3: Conexão Recusada (SERVIDOR MORREU)
```
14:35:22 Testando Dashboard         ... ✗ CONEXÃO RECUSADA
         ↑ Servidor fechou completamente!
```
**Ação:** Verifique `logs/app.log` para descobrir por quê

---

## 🔧 Passos para Encontrar o Problema

### 1. Rode o test_stability.py
```bash
python test_stability.py
```

### 2. Monitore logs simultaneamente
```bash
tail -f logs/app.log
```

### 3. Procure por ERROR quando o teste falhar:
```bash
# Ver os últimos 30 linhas de erro
grep ERROR logs/app.log | tail -30

# Ver erro de uma página específica
grep ERROR logs/app.log | grep dashboard
```

### 4. Analise o stack trace
```
2026-04-12 14:35:23 [ERROR] app — ✗ Erro em dashboard: ...
Traceback (most recent call last):
  File "app.py", line 580, in dashboard
    ests = db.get_estruturas()  ← AQUI é o problema!
  File "system/core/db.py", line 45, in get_estruturas
    ...
```

---

## 🎯 Pontos Principais que Podem Travar

Com os logs agora você verá:

1. **DB travado/bloqueado** → `ERROR ao conectar DB`
2. **Requisição impossível** → `Renderizando ... ✗ Erro em ...`
3. **Import quebrado** → Aparecerá no startup
4. **Timeout em API externa** → `⏱ >5s` nos logs
5. **Loop infinito** → Resposta nunca volta

---

## 💡 Exemplo de Fluxo Completo

### Terminal 1 (Logs):
```
2026-04-12 14:35:22 [INFO ] app — GET /dashboard | IP: 127.0.0.1
2026-04-12 14:35:22 [INFO ] app — Renderizando dashboard...
2026-04-12 14:35:27 [ERROR] app — ✗ Erro em dashboard: database is locked
Traceback (most recent call last):
  File "app.py", line 580, in dashboard
    ests = db.get_estruturas()
  File "system/core/db.py", line 45, in get_estruturas
    rows = cursor.execute(...).fetchall()  ← DB BLOQUEADO!
sqlite3.OperationalError: database is locked
2026-04-12 14:35:27 [WARNING] app — GET /dashboard → 500 (⏱ 5.23s)
```

### Terminal 2 (Teste):
```
14:35:22 Testando Dashboard         ... ✗ TIMEOUT (>10s) — SERVIDOR PODE ESTAR TRAVADO!
```

**Conclusão:** Database está bloqueado! Feche outras conexões.

---

## 📝 Checklist quando Encontrar Erro

- [ ] Qual página causa travamento?
- [ ] Qual função/rota no stack trace?
- [ ] Qual é a linha de código exata?
- [ ] O erro é consistente ou aleatório?
- [ ] Quantas vezes trava antes de conseguir?

Compartilhe essas informações e o erro será corrigido rapidinho! 🚀

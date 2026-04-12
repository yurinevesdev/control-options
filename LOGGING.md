# 📋 Guia de Logging do Projeto

## Localização dos Logs

Os logs são salvos em: **`./logs/app.log`**

Este arquivo é criado automaticamente na primeira execução.

## Níveis de Log

- **INFO** (🟢) - Operações normais, requisições bem-sucedidas
- **WARNING** (🟡) - Situações anormais, rate limit, 404s
- **ERROR** (🔴) - Erros de execução, exceções
- **DEBUG** (🔵) - Informações detalhadas (pode ser ativado se necessário)

## O que é Registrado

### Log de Requisições
```
2026-04-12 14:23:45 [INFO    ] app — GET /opcoes | IP: 127.0.0.1
2026-04-12 14:23:46 [INFO    ] app — GET /opcoes → 200
```
- Toda requisição recebida
- Status da resposta (200, 500, 404, etc)

### Log de Renderização de Páginas
```
2026-04-12 14:23:45 [INFO    ] app — Renderizando historico...
2026-04-12 14:23:46 [INFO    ] app — ✓ historico renderizado com sucesso
```
- Quando começa a renderizar uma página
- Se sucesso ou falha

### Log de Erros
```
2026-04-12 14:24:15 [ERROR   ] app — ✗ Erro em dashboard: division by zero
Traceback (most recent call last):
  File "app.py", line 580, in dashboard
    ...
```
- Stack trace completo
- Arquivo e linha exata do erro

## Páginas Monitoradas

Estas rotas têm logging automático:
- ✅ `/` - Índice
- ✅ `/simulador` - Simulador
- ✅ `/historico` - Histórico
- ✅ `/dashboard` - Dashboard
- ✅ `/opcoes` - Opções
- ✅ `/opcoes/<ticker>` - Opções detalhadas
- ✅ `/sugestoes` - Sugestões
- ✅ `/carteira` - Carteira

## Como Usar

### Ver logs em tempo real (terminal)
```bash
tail -f logs/app.log
```

### Ver últimas 50 linhas
```bash
tail -50 logs/app.log
```

### Filtrar apenas erros
```bash
grep ERROR logs/app.log
```

### Filtrar por endpoint específico
```bash
grep "/dashboard" logs/app.log
```

### Ver logs com timestamp recente
```bash
grep "2026-04-12 14:2" logs/app.log
```

## Interpretando o Log

**Requisição bem-sucedida:**
```
INFO  GET /simulador → 200          ✅ OK
```

**Erro 404:**
```
WARNING  GET /pagina-invalida → 404  ⚠️ Página não encontrada
```

**Erro 500:**
```
ERROR  GET /dashboard → 500          ❌ Erro na renderização
ERROR  ✗ Erro em dashboard: ...      (detalhes do erro)
```

## Debugging

Se uma página "parar":

1. **Verifique o log:**
   ```bash
   tail -20 logs/app.log
   ```

2. **Procure por ERROR ou a rota específica:**
   ```bash
   grep "ERROR\|/sua-rota" logs/app.log | tail -10
   ```

3. **Leia o stack trace** - mostra exatamente onde o erro ocorreu

4. **Compartilhe a linha de erro** ao reportar o problema

## Configuração

Para alterar o nível de log, edite `app.py` linha 62:

```python
logger = setup_logging(level=logging.INFO)  # INFO, DEBUG, WARNING, ERROR
```

## Exemplo Completo

Um fluxo de requisição bem-sucedida:
```
2026-04-12 14:30:22 [INFO    ] app — GET /dashboard | IP: 127.0.0.1
2026-04-12 14:30:22 [INFO    ] app — Renderizando dashboard...
2026-04-12 14:30:23 [INFO    ] app — ✓ dashboard renderizado com sucesso
2026-04-12 14:30:23 [INFO    ] app — GET /dashboard → 200
```

Um fluxo com erro:
```
2026-04-12 14:31:05 [INFO    ] app — GET /opcoes | IP: 127.0.0.1
2026-04-12 14:31:05 [INFO    ] app — Renderizando opcoes_page...
2026-04-12 14:31:06 [ERROR   ] app — ✗ Erro em opcoes_page: KeyError: 'ticker'
Traceback (most recent call last):
  File "app.py", line 719, in opcoes_page
    cache = carregar_cache_opcoes()
  File "system/data/opcoes_scraper.py", line 145, in carregar_cache_opcoes
    ...
2026-04-12 14:31:06 [INFO    ] app — GET /opcoes → 500
```

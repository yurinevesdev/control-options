# System — Contexto da Aplicação

> Simulador de estratégias de opções (B3): Black-Scholes, payoff, gregas e persistência local. Use este documento como referência para melhorias e novas features.

---

## 1. Visão geral

**System** roda como **aplicação web em Python (Flask)** servida localmente (ou em servidor). O utilizador monta estruturas com várias pernas (legs), vê o payoff e métricas (ganho/perda máximos, break-evens, gregas). **Persistência:** SQLite em ficheiro no disco (`instance/SYSTEM_opcoes_v2.sqlite`), não IndexedDB.

**Público-alvo:** traders de opções da B3 (Bull Spread, Iron Condor, Butterfly, etc.).

---

## 2. Stack

| Camada | Tecnologia | Papel |
|--------|------------|--------|
| Backend | Python 3.10+ | Lógica, API, templates |
| Framework | Flask 3.x | Rotas, sessão, Jinja2 |
| Matemática | `system/blackscholes.py` | Black-Scholes (mesmo modelo que o antigo JS) |
| Base de dados | SQLite | Ficheiro `instance/SYSTEM_opcoes_v2.sqlite` |
| UI | Jinja2 + HTML | `templates/` |
| Estilo | CSS3 | `static/css/style.css` |
| Gráficos | Plotly (Python → HTML) | Payoff + dashboard (CDN Plotly.js no HTML gerado) |
| Fontes | Google Fonts | Syne + JetBrains Mono |
| Scraping | requests + BeautifulSoup | Extração de IV/IV Rank do OpLab |

**Cliente:** navegador. **JS mínimo:** modais/toasts (fechar overlay e ESC), `fetch` JSON em `/api/preview-greeks` ao alterar IV na perna, `fetch` em `/api/opcoes/atualizar` para atualizar dados de opções.

**Dependências:** ver `requirements.txt` (`flask`, `plotly`, `requests`, `beautifulsoup4`).

---

## 3. Estrutura de ficheiros

```
control-options/
├── app.py                 # Flask: rotas, sessão, orquestração
├── requirements.txt
├── instance/
│   └── SYSTEM_opcoes_v2.sqlite
├── system/
│   ├── __init__.py
│   ├── config.py          # ★ NOVO: Config centralizada (BD, BS, estratégias, secrets)
│   ├── logger.py          # ★ NOVO: Logging estruturado com cores
│   ├── blackscholes.py    # Motor BS: price, greeks, payoff, métricas
│   ├── db.py              # SQLite (com WAL, índices, backup)
│   ├── csv_io.py          # Export/import ZIP com estruturas.csv + legs.csv
│   ├── ui_format.py       # brl, datas, color_pnl
│   ├── charts.py          # Plotly payoff + dashboard
│   └── opcoes_scraper.py  # ★ NOVO: Scraping IV/IV Rank do OpLab
├── templates/
│   ├── base.html          # Layout base + toasts auto-dismiss + Ctrl+S + nav Opções
│   ├── simulador.html     # Página principal (validações HTML5, estratégias)
│   ├── historico.html
│   ├── dashboard.html
│   └── opcoes.html        # ★ NOVO: Página de dados de opções (IV, IV Rank)
└── static/css/style.css   # Design system
```

**Execução:** `python3 app.py` → `http://127.0.0.1:5000` (ou `flask --app app run`).

### 3.1 Configuração (system/config.py)

Todas as configurações centralizadas via variáveis de ambiente com defaults seguros:

| Variável | Default | Descrição |
|----------|---------|-----------|
| `SYSTEM_SECRET` | `secrets.token_hex(32)` | Chave de sessão (gerada automaticamente) |
| `SYSTEM_DB` | `system_opcoes_v2.sqlite` | Nome do ficheiro DB |
| `SYSTEM_RATE` | `0.1075` | Taxa de juro usada no BS |
| `SYSTEM_DEBUG` | `1` | Modo debug |
| `SYSTEM_HOST` | `127.0.0.1` | Host do servidor |
| `SYSTEM_PORT` | `5000` | Porta do servidor |

### 3.2 Estratégias predefinidas

O sistema inclui templates de estratégias (`ESTRATEGIAS_LIST`):

- Personalizada (default)
- Bull Call Spread
- Bear Put Spread
- Iron Condor
- Iron Butterfly
- Butterfly Call
- Put Butterfly
- Straddle
- Strangle
- Calendária Call

### 3.3 Scraping de Opções (system/opcoes_scraper.py)

Módulo para extrair dados de volatilidade implícita do **OpLab** (opcoes.oplab.com.br):

| Função | Descrição |
|--------|-----------|
| `baixar_lista_ativos()` | Scraping da página principal do OpLab |
| `salvar_cache(dados)` | Salva dados em `cache/oplab_opcoes.json` |
| `carregar_cache()` | Carrega dados do cache (válido por 24h) |
| `salvar_no_db(dados, db)` | Upsert na tabela `opcoes_dados` |
| `buscar_opcoes_dados(db, tickers)` | Busca dados do DB por tickers |
| `atualizar_dados_opcoes(db)` | Pipeline completo: scrape → cache → DB |

**Tabela `opcoes_dados`:** `ticker` (PK), `preco`, `variacao_pct`, `volatilidade_implicita`, `iv_rank`, `iv_percentil`, `atualizado_em`.

**Cache:** ficheiro JSON em `cache/oplab_opcoes.json`, válido por 24 horas.

### 3.4 CSV — exportação e importação

| Rota | Descrição |
|------|-----------|
| `GET /export/csv` | Descarrega `SYSTEM_export_YYYYMMDD_HHMMSS.zip` |
| `POST /import/csv` | Formulário na página **Histórico** (multipart) |

**ZIP:** contém `estruturas.csv` e `legs.csv` (UTF-8 com BOM), cabeçalhos em **snake_case**.

---

## 4. Módulo `system/blackscholes.py` — motor matemático

Funções em **snake_case**; comportamento numérico replica o antigo `BS.*` em JS.

### 4.1 Base

- **CDF normal:** Abramowitz & Stegun (erro < 1.5e-7).
- **d1, d2:** como no documento original; `NaN` se T ≤ 0, σ ≤ 0, S ≤ 0 ou K ≤ 0.
- **Preço:** Call/Put europeus; se T = 0, intrínseco.
- **Gregas:** Theta ÷ 365 (R$/dia); Vega e Rho ÷ 100 (por 1% de IV/taxa).
- **IV:** Newton-Raphson, σ₀ = 0.3, até 100 iterações, σ ∈ [0.001, 10].

---

## 5. Módulo `system/db.py` — SQLite

- **Ficheiro:** `instance/SYSTEM_opcoes_v2.sqlite` (criado automaticamente).
- **WAL mode** ativado para melhor performance.
- **Índices:** `tipo`, `ativo`, `data_venc` em `estruturas`; `tipo`, `strike`, `vencimento`, `ticker` em `legs`.
- **Métodos novos:** `backup(dest)`, `close()`, `stats()`.

---

## 6. Módulo `system/logger.py` — Logging

Logging estruturado com cores para desenvolvimento:

```python
from system.logger import setup_logging, get_logger
log = get_logger("app")
log.info("Estrutura salva: id=%s", eid)
```

---

## 7. Módulo `system/config.py` — Configuração

Configuração centralizada com variáveis de ambiente e lista de estratégias predefinidas.

---

## 8. Aplicação `app.py` — rotas e melhorias

### 8.1 Melhorias aplicadas

| Melhoria | Descrição |
|----------|-----------|
| **Secret key seguro** | `secrets.token_hex(32)` em vez de string hardcoded |
| **Logging** | Logger com cores em dev, log de operações críticas |
| **Rate limiting** | `/api/preview-greeks` limitado a 60 req/min por IP |
| **Redirects seguros** | `_safe_redirect()` usa `url_for()` em vez de `request.referrer` |
| **DB lifecycle** | `before_request`/`teardown_request` para abrir/feçar conexões |
| **Error handlers** | 404 e 500 com flash messages |
| **Backup DB** | `GET /admin/backup` gera dump SQLite |
| **WAL mode** | Melhor performance de escrita no SQLite |
| **Scraping OpLab** | IV/IV Rank automáticos com cache de 24h |

### 8.2 Rotas

| Rota | Descrição |
|------|-----------|
| `GET /` | Redireciona para `/simulador` |
| `GET /simulador`, `GET /simulador/<id>` | Simulador |
| `POST /simulador/estrutura/save` | Criar/editar estrutura |
| `POST /simulador/estrutura/<id>/delete` | Eliminar estrutura e pernas |
| `POST /simulador/<eid>/leg/save` | Criar/editar perna |
| `POST /simulador/leg/<lid>/delete` | Eliminar perna |
| `GET /export/csv` | Exportar dados (ZIP) |
| `POST /import/csv` | Importar dados (ZIP ou CSVs) |
| `GET /historico` | Histórico de estruturas |
| `GET /dashboard` | Dashboard com métricas agregadas |
| `POST /api/preview-greeks` | JSON: gregas + preço sugerido |
| `GET /admin/backup` | Download backup SQLite |
| `POST /api/opcoes/atualizar` | Atualiza dados IV/IV Rank do OpLab (rate: 5 req/5min) |
| `GET /api/opcoes/dados` | Retorna dados de opções (cache ou DB por tickers) |
| `GET /opcoes` | Página de visualização de dados de opções |

---

## 9. UX — Melhorias

| Melhoria | Descrição |
|----------|-----------|
| **Toasts auto-dismiss** | 5 segundos com transição suave |
| **Ctrl+S** | Submete formulário do modal activo |
| **Loading state** | Botão desactivado com texto "Salvando..." ao submeter |
| **Validações HTML5** | `required`, `min`, `step` em campos obrigatórios |
| **Confirmação de exclusão** | Mensagem mais clara nos alerts |

---

## 10. Regras de negócio (inalteradas)

1. Estrutura = trade; N pernas sem limite fixo.
2. `premio` sempre positivo por contrato; sentido financeiro via `operacao`.
3. Gregas automáticas com IV quando aplicável; fallback manual.
4. `r = 0.1075` e `q = 0` no núcleo BS.
5. Tipos de estratégia: lista configurável em `system/config.py`.
6. Exclusão em cascata ao apagar estrutura.
7. Margem ≈ `abs(perdaMax)`.
8. Break-evens por cruzamento zero na curva de expiração.

---

## 11. Limitações

- BS europeu, vol constante; exercício americano não modelado.
- `q = 0`; taxa fixa; margem simplificada.
- Dados no ficheiro SQLite da máquina que corre o servidor.
- Import CSV é **adição** de registos, não substituição total automática.
- Curva "atual" BS depende de IV nas pernas.
- Scraping do OpLab depende da estrutura HTML do site (pode quebrar com atualizações do site).
- Cache de 24h pode não refletir dados em tempo real.

---

## 12. Convenções Python

- Tipagem e nomes em **snake_case** nos módulos `system/`.
- Dicts vindos da BD/templates com chaves **camelCase** para estruturas/pernas.
- Alterações focadas; alinhar estilo aos ficheiros existentes.

## 13. Como estender (rápido)

| Alteração | Onde |
|-----------|------|
| Campo novo na estrutura | Coluna em `db.py` + `save_estrutura`; formulário em `simulador.html`; rota `save_estrutura` |
| Campo novo na perna | Idem em `legs` + modal perna + `save_leg` |
| Novo cálculo BS | `system/blackscholes.py` |
| Novo gráfico | `system/charts.py` + template da página |
| Nova página | Nova rota em `app.py` + template + link em `base.html` |
| Nova fonte de dados | Novo módulo em `system/` + rota API + template |

## 14. Migração JS → Python

O cliente deixou de ser uma SPA só estática: **não há** `index.html` nem pasta `js/` no repositório. Dados antigos em **IndexedDB** não migram automaticamente para SQLite; export/import manual se necessário.

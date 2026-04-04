# Eagle System — Contexto da Aplicação

> Simulador de estratégias de opções (B3): Black-Scholes, payoff, gregas e persistência local. Use este documento como referência para melhorias e novas features.

---

## 1. Visão geral

**Eagle System** roda como **aplicação web em Python (Flask)** servida localmente (ou em servidor). O utilizador monta estruturas com várias pernas (legs), vê o payoff e métricas (ganho/perda máximos, break-evens, gregas). **Persistência:** SQLite em ficheiro no disco (`instance/eagle_opcoes_v2.sqlite`), não IndexedDB.

**Público-alvo:** traders de opções da B3 (Bull Spread, Iron Condor, Butterfly, etc.).

---

## 2. Stack

| Camada | Tecnologia | Papel |
|--------|------------|--------|
| Backend | Python 3.10+ | Lógica, API, templates |
| Framework | Flask 3.x | Rotas, sessão, Jinja2 |
| Matemática | `eagle/blackscholes.py` | Black-Scholes (mesmo modelo que o antigo JS) |
| Base de dados | SQLite | Ficheiro `instance/eagle_opcoes_v2.sqlite` |
| UI | Jinja2 + HTML | `templates/` |
| Estilo | CSS3 | `static/css/style.css` (fonte de verdade; cópia em `css/style.css`) |
| Gráficos | Plotly (Python → HTML) | Payoff + dashboard (CDN Plotly.js no HTML gerado) |
| Fontes | Google Fonts | Syne + JetBrains Mono |

**Cliente:** navegador. **JS mínimo:** modais/toasts (fechar overlay e ESC), `fetch` JSON em `/api/preview-greeks` ao alterar IV na perna (equivalente ao antigo `onIVChange`).

**Dependências:** ver `requirements.txt` (`flask`, `plotly`).

---

## 3. Estrutura de ficheiros

```
control-options/
├── app.py                 # Flask: rotas, sessão, orquestração (ex-app.js)
├── requirements.txt
├── instance/
│   └── eagle_opcoes_v2.sqlite
├── eagle/
│   ├── blackscholes.py    # Motor BS: price, greeks, payoff, métricas
│   ├── db.py              # SQLite (ex-db.js)
│   ├── csv_io.py          # Export/import ZIP com estruturas.csv + legs.csv
│   ├── ui_format.py       # brl, datas, color_pnl (ex-ui.js)
│   └── charts.py          # Plotly payoff + dashboard (ex-chart.js)
├── templates/
│   ├── base.html
│   ├── simulador.html
│   ├── historico.html
│   └── dashboard.html
└── static/css/style.css   # Design system
```

**Execução:** `python3 app.py` → `http://127.0.0.1:5000` (ou `flask --app app run`).

### 3.1 CSV — exportação e importação

| Rota | Descrição |
|------|-----------|
| `GET /export/csv` | Descarrega `eagle_export_YYYYMMDD_HHMMSS.zip` |
| `POST /import/csv` | Formulário na página **Histórico** (multipart) |

**ZIP:** contém `estruturas.csv` e `legs.csv` (UTF-8 com BOM), cabeçalhos em **snake_case** alinhados ao SQLite (`preco_atual`, `data_venc`, `estrutura_id`, …).

**Importação (merge):** insere **novas** linhas; IDs do ficheiro são mapeados para novos IDs na base. Ligação perna→estrutura via `estrutura_id` do CSV. Se `id` de estrutura estiver vazio, usa-se a ordem da linha (1, 2, 3…). Pernas com `estrutura_id` inválido ou strike/qtd inválidos são contadas como ignoradas (aviso). Transação única (tudo ou nada).

**Alternativa:** enviar os dois CSV em separado no mesmo POST (sem ZIP). **Não** substitui a base inteira por defeito (não há “restore completo” por ficheiro único sem apagar dados manualmente).

---

## 4. Módulo `eagle/blackscholes.py` — motor matemático

Funções em **snake_case**; o comportamento numérico replica o antigo `BS.*` em JS.

| JS (legado) | Python |
|-------------|--------|
| `normCDF` / `normPDF` | `norm_cdf`, `norm_pdf` |
| `d1d2` | `d1d2` |
| `price` | `price` |
| `greeks` | `greeks` |
| `impliedVol` | `implied_vol` |
| `legPayoffAtExpiry` | `leg_payoff_at_expiry` |
| `legPnLCurrent` | `leg_pnl_current` |
| `computePayoffSeries` | `compute_payoff_series` |
| `calcMetrics` | `calc_metrics` |

### 4.1 Base

- **CDF normal:** Abramowitz & Stegun (erro &lt; 1.5e-7).
- **d1, d2:** como no documento original; `NaN` se T ≤ 0, σ ≤ 0, S ≤ 0 ou K ≤ 0.
- **Preço:** Call/Put europeus; se T = 0, intrínseco.
- **Gregas:** Theta ÷ 365 (R$/dia); Vega e Rho ÷ 100 (por 1% de IV/taxa).
- **IV:** Newton-Raphson, σ₀ = 0.3, até 100 iterações, σ ∈ [0.001, 10].

### 4.2 Objetos `estrutura` e `leg`

O código Python aceita dicts com chaves **camelCase** (como no front/templates), alinhadas ao modelo mental original:

- Estrutura: `precoAtual`, `dataVenc`, …
- Leg: `operacao`, `tipo`, `qtd`, `strike`, `premio`, `iv`, gregas manuais opcionais, etc.

### 4.3 Fórmulas principais (referência)

- **d1, d2:** `d1 = [ln(S/K) + (r − q + σ²/2)·T] / (σ√T)`, `d2 = d1 − σ√T`.
- **Call:** `C = S·e^(−qT)·N(d1) − K·e^(−rT)·N(d2)` · **Put:** `P = K·e^(−rT)·N(−d2) − S·e^(−qT)·N(−d1)`.
- **Gregas:** Delta/Gamma/Vega/Rho conforme BS padrão; Theta anualizado dividido por **365**; Vega e Rho reportados por **1%** de movimento em IV/taxa.

### 4.4 Payoff e métricas

- **Payoff no vencimento por perna:** `mult × qtd × (intrínseco − premio)` com `mult` +1 compra / −1 venda.
- **Série do gráfico:** `compute_payoff_series` — range X (~0.6× a ~1.4× strikes/spot), `payoffExpiry`, opcionalmente `payoffCurrent` se T &gt; 0.001; `r = 0.1075`.
- **Métricas:** `calc_metrics` — `premioLiq` / `posInicial`, max/min da curva de expiração (500 pontos), break-evens por interpolação linear, gregas agregadas (BS se IV+T+S0, senão manual se `delta` preenchido).

**Prêmio líquido (estrutura):** `Σ mult(op) × premio × qtd` com `mult(compra) = −1`, `mult(venda) = +1` (crédito se positivo).

**Prioridade de gregas por perna:** (1) IV &gt; 0 e T &gt; 0 e S0 &gt; 0 → BS; (2) senão, valores manuais se `delta` informado; (3) caso contrário agregado fica sem gregas úteis.

---

## 5. Módulo `eagle/db.py` — SQLite

- **Ficheiro:** `instance/eagle_opcoes_v2.sqlite` (criado automaticamente).
- **Tabelas SQL** usam **snake_case** (`preco_atual`, `data_venc`, `estrutura_id`, `criado_em`, …). As funções públicas devolvem dicts com **camelCase** onde aplicável (`precoAtual`, `dataVenc`, `estruturaId`, …) para compatibilidade com `blackscholes` e templates.

**Operações principais:** `save_estrutura`, `save_leg`, `delete_estrutura` (apaga legs da estrutura), `get_estruturas` (ordenado `id` desc, campo auxiliar `_legsCount`), `get_legs`, `get`, `get_all`, `delete_row`.

---

## 6. Módulo `eagle/ui_format.py`

Equivalente ao antigo `UI` para formatação server-side: `brl`, `pct`, `num`, `fmt_date`, `dias_ate_venc`, `color_pnl`.

---

## 7. Módulo `eagle/charts.py` — Plotly

- **Payoff:** áreas verde/vermelho (expiração), curvas âmbar tracejadas (BS atual se toggled e T &gt; 0.001), linha vertical no spot, eixo zero. Cores alinhadas ao CSS (`#4ade80`, `#f87171`, `#fbbf24`, `#60a5fa`).
- **Dashboard:** doughnut por tipo de estratégia; barras de prêmio líquido por estrutura.

---

## 8. Aplicação `app.py` — rotas e fluxo

### 8.1 Rotas principais

| Rota | Descrição |
|------|-----------|
| `GET /` | Redireciona para `/simulador` |
| `GET /simulador`, `GET /simulador/<id>` | Simulador; query `q` = busca; `modal_est`, `modal_leg`, `edit_est`, `edit_leg` controlam modais |
| `POST /simulador/estrutura/save` | Criar/editar estrutura |
| `POST /simulador/estrutura/<id>/delete` | Eliminar estrutura e pernas |
| `POST /simulador/<eid>/leg/save` | Criar/editar perna |
| `POST /simulador/leg/<lid>/delete` | Eliminar perna (`estrutura_id` no form) |
| `POST /simulador` (action `toggle_bs`) | Alternar curva BS atual (sessão `show_current_bs`) |
| `GET /historico`, `GET /dashboard` | Páginas homónimas |
| `POST /api/preview-greeks` | JSON: `preco_atual`, `strike`, `iv`, `tipo`, `venc` → gregas + preço sugerido |

### 8.2 Estado

- **Sessão Flask:** `show_current_bs` (default verdadeiro) para o checkbox do gráfico.
- **Seleção de estrutura:** URL `/simulador/<id>` (não SPA).

### 8.3 Feedback

- **Flash messages** → toasts em `base.html` (categorias `success`, `error`, `warning`, `info`).

---

## 9. Templates e UI (`templates/` + `static/css/style.css`)

- **Navegação:** links com classe `nav-btn` (incl. `a.nav-btn` estilizado no CSS).
- **Modais:** classe `.open` em `.modal-overlay`; fecho por overlay, botão, links “Cancelar”, ESC.
- **IDs úteis:** mesmos conceitos do antigo `index.html` (`struct-list`, `legs-tbody`, `m-*`, `g-*`, modais `#modal-estrutura`, `#modal-leg`, campos `est-*`, `leg-*`). O gráfico deixa de ser `<canvas>` Chart.js e passa a ser div Plotly embutido (`chart_html`).

---

## 10. Regras de negócio (inalteradas na migração)

1. Estrutura = trade; N pernas sem limite fixo.
2. `premio` sempre positivo por contrato; sentido financeiro via `operacao` (compra paga, venda recebe).
3. Gregas automáticas com IV quando aplicável; fallback manual.
4. `r = 0.1075` e `q = 0` no núcleo BS (ajustáveis em `blackscholes.py`).
5. Tipos de estratégia: lista nos templates (select), incluindo “Personalizada”.
6. Exclusão em cascata ao apagar estrutura.
7. Margem ≈ `abs(perdaMax)` (aproximação, não regra B3).
8. Break-evens por cruzamento zero na curva de expiração.

---

## 11. Limitações

- BS europeu, vol constante; exercício americano não modelado.
- `q = 0`; taxa fixa; margem simplificada.
- Dados no ficheiro SQLite da máquina que corre o servidor (sem auth/sync).
- Import CSV é **adição** de registos, não substituição total automática da base.
- Curva “atual” BS depende de IV nas pernas.

---

## 12. Convenções Python

- Tipagem e nomes em **snake_case** nos módulos `eagle/`.
- Dicts vindos da BD/templates com chaves **camelCase** para estruturas/pernas onde já documentado.
- Alterações focadas; alinhar estilo aos ficheiros existentes.

---

## 13. Como estender (rápido)

| Alteração | Onde |
|-----------|------|
| Campo novo na estrutura | Coluna em `db.py` + `save_estrutura` / leitura; formulário em `simulador.html`; rota `save_estrutura` |
| Campo novo na perna | Idem em `legs` + modal perna + `save_leg` |
| Novo cálculo BS | `eagle/blackscholes.py` |
| Novo gráfico | `eagle/charts.py` + template da página |
| Nova página | Nova rota em `app.py` + template + link em `base.html` |

---

## 14. Migração JS → Python

O cliente deixou de ser uma SPA só estática: **não há** `index.html` nem pasta `js/` no repositório. Dados antigos em **IndexedDB** não migram automaticamente para SQLite; export/import manual se necessário.

# Eagle System — Contexto Completo da Aplicação

> Este documento descreve em detalhes toda a arquitetura, módulos, cálculos, convenções e regras de negócio do Eagle System. Use-o como contexto ao pedir melhorias, correções ou novas features à IA.

---

## 1. Visão Geral

**Eagle System** é um simulador de estratégias de opções financeiras (mercado brasileiro, B3). Roda 100% no navegador — sem servidor, sem backend. O usuário monta estruturas compostas por múltiplas "pernas" (legs), visualiza o gráfico de payoff calculado via Black-Scholes, e acompanha métricas como ganho máximo, perda máxima, break-evens e gregas consolidadas. Todos os dados ficam salvos localmente via IndexedDB.

**Público-alvo:** Traders de opções da B3 que operam estruturas como Bull Spread, Iron Condor, Butterfly, etc.

---

## 2. Stack de Tecnologias

| Camada | Tecnologia | Versão | Papel |
|---|---|---|---|
| Linguagem | JavaScript (ES2020+) | — | Toda a lógica da aplicação |
| Estilo | CSS3 puro | — | Sem framework CSS; design system próprio com variáveis CSS |
| Banco de dados | IndexedDB (Web API) | — | Persistência local, sem servidor |
| Gráficos | Chart.js | 4.4.1 | Gráfico de payoff |
| Anotações no gráfico | chartjs-plugin-annotation | 3.0.1 | Linha do spot, linha do zero |
| Fontes | Google Fonts | — | Syne (UI) + JetBrains Mono (números) |
| CDN | cdnjs.cloudflare.com | — | Única origem externa permitida |

**Sem frameworks JS** (sem React, Vue, Angular). Vanilla JS com padrão IIFE/módulo manual.

---

## 3. Estrutura de Arquivos

```
eagle-system/
├── index.html              # HTML estrutural + carrega todos os scripts
├── css/
│   └── style.css           # Design system completo (377 linhas)
└── js/
    ├── blackscholes.js     # Engine matemática — Black-Scholes (352 linhas)
    ├── db.js               # Camada de banco IndexedDB (121 linhas)
    ├── ui.js               # Utilitários de interface (143 linhas)
    ├── chart.js            # Módulo do gráfico de payoff (201 linhas)
    └── app.js              # Controller principal — orquestra tudo (593 linhas)
```

**Ordem de carregamento** (todos com `defer` no `index.html`):
1. `blackscholes.js` — sem dependências
2. `db.js` — sem dependências
3. `ui.js` — sem dependências
4. `chart.js` — depende de `BS` e `UI`
5. `app.js` — depende de todos os anteriores + `Chart` (global do CDN)

---

## 4. Módulo: `js/blackscholes.js` — Engine Matemática

Namespace global: `BS`

### 4.1 Funções Matemáticas Base

#### `normCDF(x)` — Distribuição Normal Acumulada
Implementação via aproximação de Abramowitz & Stegun (erro < 1.5e-7). Usada em todas as fórmulas de precificação e gregas.

#### `normPDF(x)` — Função de Densidade Normal
`N'(x) = exp(-0.5·x²) / √(2π)` — usada para Gamma, Theta, Vega.

#### `d1d2(S, K, T, r, sigma, q=0)` — Parâmetros BS
```
d1 = [ln(S/K) + (r - q + 0.5·σ²)·T] / (σ·√T)
d2 = d1 - σ·√T
```
Retorna `{ d1, d2 }`. Retorna `NaN` se T ≤ 0, σ ≤ 0, S ≤ 0 ou K ≤ 0.

### 4.2 `BS.price(type, S, K, T, r, sigma, q=0)` — Preço Teórico

Modelo Black-Scholes para opções europeias:

```
Call: C = S·e^(-qT)·N(d1) - K·e^(-rT)·N(d2)
Put:  P = K·e^(-rT)·N(-d2) - S·e^(-qT)·N(-d1)
```

Se `T = 0` (vencimento), retorna o valor intrínseco:
- Call: `max(0, S - K)`
- Put:  `max(0, K - S)`

**Parâmetros:**
- `S` — preço spot atual do ativo-objeto
- `K` — strike da opção
- `T` — tempo até vencimento em **anos** (ex: 30 dias = 30/365 ≈ 0.0822)
- `r` — taxa livre de risco anualizada (padrão: 0.1075 — Selic aproximada)
- `sigma` — volatilidade implícita anualizada em decimal (ex: 30% → 0.30)
- `q` — dividend yield contínuo (padrão: 0)

### 4.3 `BS.greeks(type, S, K, T, r, sigma, q=0)` — Gregas

Retorna `{ delta, gamma, theta, vega, rho }`.

| Grega | Fórmula Call | Fórmula Put | Unidade |
|---|---|---|---|
| **Delta (Δ)** | `e^(-qT)·N(d1)` | `-e^(-qT)·N(-d1)` | adimensional (0 a ±1) |
| **Gamma (Γ)** | `e^(-qT)·N'(d1) / (S·σ·√T)` | idem | por R$ de S |
| **Theta (Θ)** | fórmula completa ÷ **365** | fórmula completa ÷ 365 | R$/dia |
| **Vega (ν)** | `S·e^(-qT)·N'(d1)·√T` ÷ **100** | idem | R$ por 1% de IV |
| **Rho (ρ)** | `K·T·e^(-rT)·N(d2)` ÷ **100** | `-K·T·e^(-rT)·N(-d2)` ÷ 100 | R$ por 1% de taxa |

**Theta completo (Call):**
```
θ = [-(S·e^(-qT)·N'(d1)·σ) / (2·√T) - r·K·e^(-rT)·N(d2) + q·S·e^(-qT)·N(d1)] / 365
```

### 4.4 `BS.impliedVol(type, S, K, T, r, marketPrice, q=0)` — IV via Newton-Raphson

Encontra σ tal que `BS.price(type, S, K, T, r, σ) = marketPrice`.

Algoritmo:
1. Chute inicial: `σ = 0.30` (30%)
2. Até 100 iterações: `σ_{n+1} = σ_n - (price - marketPrice) / vega_raw`
3. Guarda: `σ ∈ [0.001, 10]`; retorna `null` se não convergir

### 4.5 `BS.legPayoffAtExpiry(leg, S)` — Payoff de Uma Perna no Vencimento

```
intrinsic = max(0, S - K)   // call
intrinsic = max(0, K - S)   // put

mult = +1   // compra (long)
mult = -1   // venda (short)

P&L = mult × qtd × (intrinsic - premio)
```

**Regra de sinal fundamental:**
- **Compra (long):** pagou o prêmio → ganha se intrínseco > prêmio
- **Venda (short):** recebeu o prêmio → ganha se intrínseco < prêmio

### 4.6 `BS.legPnLCurrent(leg, S, T, r)` — P&L Atual (antes do vencimento)

Usa `BS.price()` para calcular o valor teórico atual da opção e subtrai o prêmio de entrada:

```
valor_atual = BS.price(tipo, S, K, T, r, IV/100)
P&L = mult × qtd × (valor_atual - premio)
```

Requer que `leg.iv` esteja preenchido (volatilidade implícita em %).

### 4.7 `BS.computePayoffSeries(estrutura, legs, numPoints=300)` — Série para o Gráfico

Gera arrays de pontos `x = preço do ativo` vs `y = P&L da estrutura`:

- **Range X:** de `min(strikes) × 0.6` a `max(strikes) × 1.4` (cobre toda a estrutura com margem)
- **`payoffExpiry[]`:** calculado com `legPayoffAtExpiry()` — curva sólida no gráfico
- **`payoffCurrent[]`:** calculado com `legPnLCurrent()` — curva tracejada, só se `T > 0.001`
- Retorna também `{ xMin, xMax, T, S0 }`

Taxa de juros fixa: `r = 0.1075` (Selic aproximada, configurável diretamente no código).

### 4.8 `BS.calcMetrics(estrutura, legs)` — Métricas da Estrutura

Retorna:

| Campo | Cálculo |
|---|---|
| `premioLiq` | Soma de: `+premio × qtd` (venda) e `-premio × qtd` (compra). Positivo = crédito líquido. |
| `posInicial` | Igual a `premioLiq` |
| `ganhoMax` | `max(payoffExpiry[])` com 500 pontos |
| `perdaMax` | `min(payoffExpiry[])` com 500 pontos |
| `breakEvens[]` | Cruzamentos de zero na curva de payoff (interpolação linear) |
| `margem` | `abs(perdaMax)` — estimativa de garantia exigida |
| `delta/gamma/theta/vega/rho` | Soma ponderada das gregas de cada perna (BS se IV informado, manual caso contrário) |

**Prioridade de gregas por perna:**
1. Se `leg.iv > 0` e `T > 0` e `S0 > 0`: usa BS calculado automaticamente
2. Se `leg.delta` preenchido manualmente: usa valores manuais
3. Caso contrário: retorna `null`

---

## 5. Módulo: `js/db.js` — Banco de Dados IndexedDB

Namespace global: `DB`

### 5.1 Banco de Dados

- **Nome:** `eagle_opcoes_v2`
- **Versão:** 2

### 5.2 Object Stores (Tabelas)

#### `estruturas`
| Campo | Tipo | Descrição |
|---|---|---|
| `id` | Integer (PK, auto) | Identificador único |
| `nome` | String | Nome da estrutura (obrigatório) |
| `ativo` | String | Ticker do ativo-objeto (ex: PETR4) |
| `tipo` | String | Tipo de estratégia (Bull Spread, Iron Condor, etc.) |
| `precoAtual` | Float\|null | Preço spot do ativo-objeto |
| `dataVenc` | String\|null | Data de vencimento `"YYYY-MM-DD"` |
| `obs` | String | Observações livres |
| `criadoEm` | ISO String | Timestamp de criação |
| `atualizadoEm` | ISO String | Timestamp de última atualização |

Índice: `criadoEm` (não único).

#### `legs`
| Campo | Tipo | Descrição |
|---|---|---|
| `id` | Integer (PK, auto) | Identificador único |
| `estruturaId` | Integer (FK) | Referência à estrutura pai |
| `operacao` | `'compra'\|'venda'` | Long ou Short |
| `tipo` | `'call'\|'put'` | Tipo da opção |
| `qtd` | Integer | Quantidade de contratos |
| `strike` | Float | Preço de exercício (K) |
| `ticker` | String | Código da série (ex: PETRD186) |
| `vencimento` | String\|null | `"YYYY-MM-DD"` da perna específica |
| `premio` | Float | Prêmio pago (compra) ou recebido (venda) por contrato |
| `iv` | Float\|null | Volatilidade Implícita em % (ex: 30.5 para 30.5%) |
| `delta` | Float\|null | Delta manual (ou calculado por BS) |
| `gamma` | Float\|null | Gamma manual (ou calculado por BS) |
| `theta` | Float\|null | Theta manual por dia |
| `vega` | Float\|null | Vega manual por 1% de IV |

Índice: `estruturaId` (não único) — permite busca de todas as pernas de uma estrutura.

### 5.3 API Pública do DB

```js
DB.open()                          // inicializa o banco (chamado em App.init())
DB.saveEstrutura(obj)              // insert ou update (upsert por id)
DB.saveLeg(obj)                    // insert ou update (upsert por id)
DB.deleteEstrutura(id)             // deleta estrutura + todas as suas legs
DB.getEstruturas()                 // retorna todas as estruturas ordenadas por id desc
DB.getLegs(estruturaId)            // retorna legs de uma estrutura
DB.get('estruturas'|'legs', id)    // busca por PK
DB.getAll('estruturas'|'legs')     // busca todos os registros da tabela
DB.del('legs', id)                 // deleta um registro
```

---

## 6. Módulo: `js/ui.js` — Utilitários de Interface

Namespace global: `UI`

### 6.1 Formatação

| Função | Uso |
|---|---|
| `UI.brl(v, decimals=2)` | Formata como moeda BRL: `R$ 1.234,56` |
| `UI.pct(v, decimals=1)` | Formata como percentual: `35.2%` (v já em decimal) |
| `UI.num(v, d=2)` | Formata número com casas decimais fixas |
| `UI.fmtDate(d)` | Converte `"YYYY-MM-DD"` → `"DD/MM/AAAA"` |
| `UI.diasAteVenc(dataVenc)` | Retorna inteiro de dias até vencimento (negativo = vencido) |
| `UI.colorPnl(v)` | Retorna `'pos'`, `'neg'` ou `'neu'` — classe CSS de cor |

### 6.2 Modais

- `UI.openModal(id)` / `UI.closeModal(id)` — adiciona/remove classe `.open`
- Fecha com clique no overlay (`.modal-overlay`)
- Fecha com tecla ESC

### 6.3 Toasts

```js
UI.toast('Mensagem', 'success'|'error'|'warning'|'info', durationMs=3000)
```
Cria elemento `.toast` no `#toast-container` (criado automaticamente se não existir), anima com CSS, auto-remove.

### 6.4 DOM Helpers

| Função | Uso |
|---|---|
| `UI.val(id)` | `document.getElementById(id).value.trim()` |
| `UI.setVal(id, v)` | Define value de um input |
| `UI.setText(id, v)` | Define textContent |
| `UI.setHtml(id, v)` | Define innerHTML |
| `UI.el(tag, cls, html)` | Cria elemento DOM |
| `UI.qs(sel, ctx)` | querySelector |
| `UI.qsa(sel, ctx)` | querySelectorAll → Array |

---

## 7. Módulo: `js/chart.js` — Gráfico de Payoff

Namespace global: `ChartModule`

### 7.1 `ChartModule.render(canvasId, estrutura, legs, showCurrent=true)`

Destrói o gráfico anterior (se existir) e cria um novo. Usa `BS.computePayoffSeries()` para obter os dados.

**Datasets criados:**

| Dataset | Cor | Preenchimento | Quando |
|---|---|---|---|
| Lucro (Exp.) | `#4ade80` (verde) | área verde | sempre |
| Perda (Exp.) | `#f87171` (vermelho) | área vermelha | sempre |
| Lucro (Atual BS) | `#fbbf24` (âmbar) tracejado | área âmbar leve | se `showCurrent && T > 0.001` |
| Perda (Atual BS) | `#fbbf24` tracejado | sem fill | se `showCurrent && T > 0.001` |

A separação em datasets positivo/negativo é necessária para colorir áreas corretamente no Chart.js.

**Anotações (chartjs-plugin-annotation):**
- `spotLine`: linha vertical azul no preço atual (`S0`)
- `zeroLine`: linha horizontal branca/transparente em y=0

**Tooltip:** mostra preço do ativo no título, P&L de cada curva no corpo, e total no vencimento no rodapé.

**Eixo X:** tipo `linear`, labels formatadas como `R$XX.XX`. Range: `xMin` a `xMax` vindos de `computePayoffSeries()`.

**Eixo Y:** valores em R$; abreviação `k` para valores ≥ 1000.

### 7.2 `ChartModule.destroy()`

Destrói o chart atual sem criar novo. Chamado quando nenhuma estrutura está selecionada.

---

## 8. Módulo: `js/app.js` — Controller Principal

Namespace global: `App`

### 8.1 Estado Global (`state`)

```js
{
  estrutura:  object|null,   // estrutura selecionada atualmente
  legs:       array,         // pernas da estrutura selecionada
  editLegId:  number|null,   // id da perna em edição (null = nova)
  editEstId:  number|null,   // id da estrutura em edição (null = nova)
  page:       string,        // 'simulador'|'historico'|'dashboard'
  dashCharts: array,         // instâncias Chart.js do dashboard (para destroy)
}
```

### 8.2 Fluxo de Inicialização

```
App.init()
  └── DB.open()
  └── UI.setText('db-badge', '● DB Ativo')
  └── renderSidebar()
  └── bindEvents()
        ├── search-input → renderSidebar()
        ├── [data-page] buttons → showPage()
        └── toggle-atual → refreshChart()
```

### 8.3 Fluxo de Seleção de Estrutura

```
selectEstrutura(id)
  ├── DB.get('estruturas', id) → state.estrutura
  ├── DB.getLegs(id) → state.legs
  ├── Mostra #section-main, oculta #section-empty
  └── renderStructView()
        ├── renderMetrics(metrics, est)
        ├── renderGreeks(metrics)
        ├── renderLegsTable(legs, est)
        └── refreshChart()
              └── ChartModule.render(...)
```

### 8.4 Fluxo de Salvamento de Perna

```
App.openAddLeg() / App.openEditLeg(id)
  └── Preenche modal, UI.openModal('modal-leg')

App.onIVChange()                          // disparado no input de IV
  └── Calcula T, chama BS.greeks()
  └── Preenche campos delta/gamma/theta/vega automaticamente
  └── Sugere prêmio BS se campo vazio

App.saveLeg()
  ├── Valida strike e qtd
  ├── DB.saveLeg(obj)
  ├── Recarrega state.legs
  └── renderStructView() + renderSidebar()
```

### 8.5 Lógica de Negócio — Prêmio Líquido

```
premioLiq = Σ [ mult(operacao) × premio × qtd ]

onde:
  mult('compra') = -1  (pagou prêmio → saída de caixa)
  mult('venda')  = +1  (recebeu prêmio → entrada de caixa)
```

Positivo = estrutura de **crédito** (recebeu mais do que pagou).
Negativo = estrutura de **débito** (pagou mais do que recebeu).

### 8.6 Páginas

| Página | ID do elemento | Função de render |
|---|---|---|
| Simulador | `#page-simulador` | `renderStructView()` (via selectEstrutura) |
| Histórico | `#page-historico` | `renderHistorico()` |
| Dashboard | `#page-dashboard` | `renderDashboard()` |

### 8.7 API Pública do App (chamável do HTML)

```js
App.init()
App.openNewEstrutura()
App.openEditEstrutura()
App.saveEstrutura()
App.deleteEstrutura()
App.openAddLeg()
App.openEditLeg(id)
App.saveLeg()
App.deleteLeg(id)
App.onIVChange()
App.goToEstrutura(id)
App.showPage(page)
```

---

## 9. Módulo: `css/style.css` — Design System

### 9.1 Paleta de Cores (CSS Variables)

```css
--bg:      #0d0f14   /* fundo principal */
--bg2:     #13161e   /* cards, sidebar, header */
--bg3:     #1a1e2a   /* inputs, métricas, linhas da tabela */
--bg4:     #222636   /* botões, hover states */
--bg5:     #2a2f45   /* hover intenso */
--border:  rgba(255,255,255,0.07)   /* bordas suaves */
--border2: rgba(255,255,255,0.14)   /* bordas médias */
--border3: rgba(255,255,255,0.22)   /* bordas fortes */
--text:    #e8eaf0   /* texto primário */
--text2:   #8b90a0   /* texto secundário */
--text3:   #555c70   /* texto terciário / labels */
--accent:  #4ade80   /* verde — cor de destaque primária */
--cyan:    #22d3ee   /* azul-ciano — foco de inputs */
--blue:    #60a5fa   /* azul — tags CALL, spot line */
--amber:   #fbbf24   /* âmbar — venda, curva BS atual */
--red:     #f87171   /* vermelho — perda, PUT, danger */
--green:   #4ade80   /* verde — lucro, compra */
--purple:  #a78bfa   /* roxo — não usado atualmente */
--orange:  #fb923c   /* laranja — reservado */
```

### 9.2 Tipografia

- **UI geral:** `'Syne'` (weights 400, 500, 600, 700) — carregada via Google Fonts
- **Números/monospace:** `'JetBrains Mono'` (weights 400, 500) — usada em preços, gregas, strikes
- **Tamanho base:** 14px

### 9.3 Grid do Layout Principal

```css
#page-simulador {
  display: grid;
  grid-template-columns: 280px 1fr;
  height: calc(100vh - 56px);  /* 56px = altura do header */
}
```

### 9.4 Classes Utilitárias de P&L

| Classe | Cor | Uso |
|---|---|---|
| `.pos` | `var(--green)` | Valores positivos |
| `.neg` | `var(--red)` | Valores negativos |
| `.neu` | `var(--text)` | Valores neutros/break-even |
| `.amber` | `var(--amber)` | Avisos / vencimento próximo |

### 9.5 Componentes Principais

**`.card`** — container padrão (bg2, border, radius-lg, padding 16px)

**`.metric`** — card de métrica (bg3, border, radius, padding 12px):
```html
<div class="metric">
  <div class="metric-label">Nome</div>
  <div class="metric-value pos" id="m-X">R$ 0,00</div>
  <div class="metric-sub" id="m-X-sub">subtítulo</div>
</div>
```

**`.greek-box`** — caixa de grega (bg3, border, centered):
```html
<div class="greek-box">
  <div class="greek-name">Delta (Δ)</div>
  <div class="greek-val" id="g-delta">—</div>
</div>
```

**`.tag`** + modificadores:
```html
<span class="tag tag-call">CALL</span>   <!-- azul -->
<span class="tag tag-put">PUT</span>     <!-- vermelho -->
<span class="tag tag-buy">Compra</span>  <!-- verde -->
<span class="tag tag-sell">Venda</span>  <!-- âmbar -->
```

**`.modal-overlay`** + **`.modal`** — modal dialog (toggle via classe `.open`)

**`.btn`** + modificadores: `btn-primary`, `btn-danger`, `btn-sm`, `btn-full`, `btn-icon`

**`.toast`** + `toast-success|error|warning|info` — notificações slide-in

---

## 10. `index.html` — Estrutura HTML

### 10.1 IDs de Elementos Importantes

#### Header
- `#db-badge` — exibe status do banco

#### Navegação
- `[data-page="simulador|historico|dashboard"]` — botões de navegação

#### Páginas
- `#page-simulador` — grid 2 colunas (sidebar + content)
- `#page-historico` — tabela histórico
- `#page-dashboard` — métricas + gráficos

#### Sidebar
- `#search-input` — busca de estruturas
- `#struct-list` — container das estruturas (renderizado dinamicamente)

#### Seções do Simulador
- `#section-empty` — estado vazio (nenhuma estrutura selecionada)
- `#section-main` — conteúdo da estrutura selecionada

#### Header da Estrutura
- `#struct-title` — nome da estrutura
- `#struct-subtitle` — ativo · tipo · vencimento

#### Métricas (IDs com padrão `m-*`)
- `#m-inicial`, `#m-inicial-sub`
- `#m-ganho`, `#m-ganho-sub`
- `#m-perda`, `#m-perda-sub`
- `#m-be1` — break-even(s)
- `#m-margem`, `#m-margem-sub`
- `#m-premio`, `#m-premio-sub`
- `#m-preco` — preço atual do ativo

#### Gregas (IDs com padrão `g-*`)
- `#g-delta`, `#g-gamma`, `#g-theta`, `#g-vega`, `#g-rho`

#### Tabela de Pernas
- `#legs-tbody` — tbody da tabela de pernas

#### Gráfico
- `#payoff-canvas` — canvas do Chart.js
- `#chart-info` — faixa de informações acima do gráfico
- `#toggle-atual` — checkbox "Curva atual (Black-Scholes)"

#### Modais
- `#modal-estrutura` — nova/editar estrutura
- `#modal-leg` — nova/editar perna

#### Campos do Modal Estrutura (IDs com prefixo `est-`)
- `#est-nome`, `#est-ativo`, `#est-tipo`, `#est-preco`, `#est-venc`, `#est-obs`

#### Campos do Modal Perna (IDs com prefixo `leg-`)
- `#leg-op` — select compra/venda
- `#leg-tipo` — select call/put
- `#leg-qtd`, `#leg-strike`, `#leg-ticker`, `#leg-venc`
- `#leg-premio` — prêmio de entrada
- `#leg-iv` — volatilidade implícita (auto-calcula gregas via `App.onIVChange()`)
- `#leg-delta`, `#leg-gamma`, `#leg-theta`, `#leg-vega` — manuais/calculados

#### Histórico
- `#hist-tbody`

#### Dashboard
- `#dash-total`, `#dash-pernas`, `#dash-credito`, `#dash-debito`
- `#dash-ganho-max`, `#dash-perda-max`
- `#dash-chart-tipos` — canvas doughnut
- `#dash-chart-premios` — canvas bar

---

## 11. Fluxos de Dados Completos

### 11.1 Criar nova estrutura
```
User clica "+ Nova"
→ App.openNewEstrutura() → state.editEstId = null → UI.openModal('modal-estrutura')
→ User preenche e clica "Salvar"
→ App.saveEstrutura()
  → DB.saveEstrutura(obj) → retorna id
  → selectEstrutura(id)
    → state.estrutura, state.legs atualizados
    → renderStructView() → renderSidebar()
```

### 11.2 Adicionar perna com cálculo automático de gregas
```
User abre modal de perna
→ Preenche Strike, IV%, Data de vencimento
→ Campo IV dispara App.onIVChange()
  → Calcula T = (dataVenc - hoje) / 365
  → BS.greeks(tipo, S0, K, T, r, IV/100)
  → Preenche #leg-delta, #leg-gamma, #leg-theta, #leg-vega automaticamente
  → Se #leg-premio vazio: sugere BS.price(...) como prêmio
→ User confirma → App.saveLeg()
  → DB.saveLeg(obj)
  → state.legs recarregado
  → renderStructView() → renderSidebar() → refreshChart()
```

### 11.3 Renderização do gráfico
```
refreshChart()
→ ChartModule.render('payoff-canvas', estrutura, legs, showCurrent)
  → BS.computePayoffSeries(estrutura, legs, 300)
    → Para cada ponto x = preço do ativo:
      → payoffExpiry[x] = Σ legPayoffAtExpiry(leg, x)   // intrínseco - prêmio
      → payoffCurrent[x] = Σ legPnLCurrent(leg, x, T, r) // BS - prêmio
  → Chart.js: 2 datasets sólidos (pos/neg expiração) + 2 tracejados (BS atual)
  → Anotação: linha vertical em S0
```

### 11.4 Cálculo de métricas
```
BS.calcMetrics(estrutura, legs)
→ premioLiq = Σ mult(op) × premio × qtd
→ computePayoffSeries(..., 500 pontos)
→ ganhoMax = max(payoffExpiry)
→ perdaMax = min(payoffExpiry)
→ breakEvens = cruzamentos de zero (interpolação linear)
→ gregas = Σ por leg (BS se IV disponível, manual caso contrário)
```

---

## 12. Regras de Negócio

1. **Estrutura** agrupa logicamente as pernas de uma estratégia. Uma estrutura = um trade/posição.

2. **Perna (leg)** = uma opção individual dentro da estrutura. Uma estrutura pode ter N pernas (sem limite).

3. **Sinal do prêmio:** o campo `premio` sempre armazena o valor **positivo** por contrato. O sinal é determinado pela `operacao`:
   - Compra → pagou o prêmio (reduz caixa)
   - Venda → recebeu o prêmio (aumenta caixa)

4. **IV vs. gregas manuais:** Se `iv > 0` E `dataVenc` definido E `precoAtual` definido → BS calcula as gregas automaticamente. Gregas manuais são usadas como fallback ou para quando o usuário já sabe os valores.

5. **Taxa de juros:** fixada em `r = 0.1075` (10.75% a.a., Selic aproximada). Ajustável diretamente em `blackscholes.js` e `app.js`.

6. **Dividend yield:** assume `q = 0` (sem dividendos contínuos). Adequado para opções de ações brasileiras de curto prazo.

7. **Tipos de estratégia disponíveis:** Bull Spread, Bear Spread, Butterfly, Iron Butterfly, Condor, Iron Condor, Straddle, Strangle, Covered Call, Protective Put, Calendar Spread, Diagonal Spread, Ratio Spread, Personalizada.

8. **Exclusão em cascata:** ao excluir uma estrutura, todas as suas pernas são automaticamente deletadas.

9. **Margem estimada:** calculada como `abs(perdaMax)` — é uma aproximação; não reflete as regras exatas da B3/clearing.

10. **Break-even:** encontrado numericamente por interpolação linear entre pontos consecutivos onde o P&L cruza zero. Pode haver 0, 1 ou 2 break-evens (estruturas mais complexas podem ter mais).

---

## 13. Limitações Conhecidas e Pontos de Melhoria

- **Modelo:** Black-Scholes assume volatilidade constante e log-normal — não reflete smile/skew de volatilidade.
- **Estilo de exercício:** implementado como europeu (sem exercício antecipado). Opções brasileiras são americanas — para calls profundas, a diferença é pequena; para puts profundas, pode ser relevante.
- **Dividendos:** assume q=0. Ações com dividendos altos terão precificação menos precisa.
- **Taxa de juros:** hardcoded em 10.75%. Deveria ser configurável ou atualizada dinamicamente.
- **Margem:** cálculo simplificado. A B3 usa metodologia CORE (margem de carteira).
- **Sem autenticação:** dados são locais ao navegador; não há sincronização entre dispositivos.
- **Sem exportação/importação:** não há como exportar dados para CSV/Excel ou importar de outras fontes.
- **IV para gráfico atual:** se nenhuma perna tem IV preenchido, a curva BS atual não é exibida.

---

## 14. Convenções de Código

- **Padrão:** IIFE com namespace global — `const NomeModulo = (() => { ... return API; })()`
- **Strict mode:** `'use strict'` em todos os arquivos JS
- **Async/await:** usado no `app.js` e `db.js` para operações IndexedDB
- **Sem dependências externas** (exceto Chart.js via CDN)
- **Sem transpilação/build:** código roda diretamente no navegador moderno (ES2020+)
- **Nomenclatura:** camelCase para variáveis/funções, PascalCase para namespaces de módulo
- **Comentários:** JSDoc nos módulos matemáticos; comentários de bloco nos controllers

---

## 15. Como Adicionar uma Nova Feature (Guia Rápido)

### Novo campo na estrutura
1. Adicionar `<input>` no `#modal-estrutura` em `index.html`
2. Ler com `UI.val('novo-campo')` em `App.saveEstrutura()` em `app.js`
3. Exibir em `renderStructView()` ou `renderSidebar()` em `app.js`
4. Não precisa alterar `db.js` — IndexedDB é schema-less

### Nova perna / campo na perna
1. Adicionar campo no `#modal-leg` em `index.html`
2. Ler/salvar em `App.saveLeg()` em `app.js`
3. Exibir em `renderLegsTable()` em `app.js`

### Novo cálculo matemático
1. Adicionar função em `js/blackscholes.js` dentro do IIFE
2. Exportar na linha `return { ..., novaFuncao }` do BS
3. Chamar como `BS.novaFuncao(...)` de qualquer módulo

### Novo gráfico no dashboard
1. Adicionar `<canvas id="novo-canvas">` em `index.html` (dentro de `#page-dashboard`)
2. Criar instância Chart.js em `App.renderDashboard()` em `app.js`
3. Adicionar ao `state.dashCharts.push(...)` para garantir destroy correto

### Nova página
1. Adicionar `<div id="page-nova" class="page">` em `index.html`
2. Adicionar botão `<button data-page="nova">` no header
3. Adicionar case em `App.showPage()` em `app.js`

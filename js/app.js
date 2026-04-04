/**
 * Eagle System — App Controller
 * Orquestra DB, BS, UI e ChartModule
 */

'use strict';

const App = (() => {

    // ── Estado ─────────────────────────────────────────────
    const state = {
        estrutura: null,   // estrutura selecionada
        legs: [],
        editLegId: null,
        editEstId: null,
        page: 'simulador',
        dashCharts: [],
    };

    // ── Init ────────────────────────────────────────────────
    async function init() {
        await DB.open();
        UI.setText('db-badge', '● DB Ativo');
        await renderSidebar();
        bindEvents();
    }

    // ── Eventos globais ─────────────────────────────────────
    function bindEvents() {
        // Busca na sidebar
        document.getElementById('search-input')?.addEventListener('input', renderSidebar);

        // Tabs de navegação
        document.querySelectorAll('[data-page]').forEach(btn => {
            btn.addEventListener('click', () => showPage(btn.dataset.page));
        });

        // Toggle curva atual no gráfico
        document.getElementById('toggle-atual')?.addEventListener('change', refreshChart);
    }

    // ── Páginas ─────────────────────────────────────────────
    function showPage(page) {
        state.page = page;
        document.querySelectorAll('.page').forEach(p => p.style.display = 'none');
        document.querySelectorAll('[data-page]').forEach(b => b.classList.remove('active'));

        const pageEl = document.getElementById(`page-${page}`);
        if (pageEl) pageEl.style.display = page === 'simulador' ? 'grid' : 'block';

        const navBtn = document.querySelector(`[data-page="${page}"]`);
        if (navBtn) navBtn.classList.add('active');

        if (page === 'historico') renderHistorico();
        if (page === 'dashboard') renderDashboard();
    }

    // ── Sidebar ─────────────────────────────────────────────
    async function renderSidebar() {
        const q = (document.getElementById('search-input')?.value || '').toLowerCase();
        const list = document.getElementById('struct-list');
        const ests = await DB.getEstruturas();

        const filtered = q
            ? ests.filter(e => e.nome.toLowerCase().includes(q) || (e.ativo || '').toLowerCase().includes(q))
            : ests;

        if (!filtered.length) {
            list.innerHTML = '<div class="empty-state"><div class="empty-icon">📂</div><div>Nenhuma estrutura</div><div class="empty-sub">Clique em "+ Nova" para começar</div></div>';
            return;
        }

        list.innerHTML = '';
        for (const est of filtered) {
            const legs = await DB.getLegs(est.id);
            const metrics = BS.calcMetrics(est, legs);
            const dias = UI.diasAteVenc(est.dataVenc);
            const diasStr = dias !== null ? (dias >= 0 ? `${dias}d` : `vencido`) : '';
            const pnlCls = UI.colorPnl(metrics.premioLiq);

            const item = UI.el('div', `struct-item${state.estrutura?.id === est.id ? ' active' : ''}`);
            item.innerHTML = `
        <div class="struct-item-row">
          <div class="struct-item-info">
            <div class="struct-nome">${est.nome}</div>
            <div class="struct-meta">${est.ativo || '?'} · ${est.tipo || '—'}</div>
          </div>
          <div class="struct-pnl ${pnlCls}">${UI.brl(metrics.premioLiq)}</div>
        </div>
        <div class="struct-footer">
          <span>${legs.length} perna${legs.length !== 1 ? 's' : ''}</span>
          ${diasStr ? `<span>${diasStr} para venc.</span>` : ''}
        </div>
      `;
            item.addEventListener('click', () => selectEstrutura(est.id));
            list.appendChild(item);
        }
    }

    // ── Selecionar estrutura ─────────────────────────────────
    async function selectEstrutura(id) {
        state.estrutura = await DB.get('estruturas', id);
        state.legs = await DB.getLegs(id);

        document.getElementById('section-empty').style.display = 'none';
        document.getElementById('section-main').style.display = '';

        await renderStructView();
        await renderSidebar();
    }

    async function renderStructView() {
        const est = state.estrutura;
        const legs = state.legs;
        if (!est) return;

        // Header
        UI.setText('struct-title', est.nome);
        const dias = UI.diasAteVenc(est.dataVenc);
        const diasStr = dias !== null
            ? (dias >= 0 ? `Vencimento: ${UI.fmtDate(est.dataVenc)} (${dias}d)` : `Vencimento: ${UI.fmtDate(est.dataVenc)} ⚠ Vencido`)
            : `Vencimento: —`;
        UI.setText('struct-subtitle', `${est.ativo || '?'} · ${est.tipo || '—'} · ${diasStr}`);

        // Métricas
        const m = BS.calcMetrics(est, legs);
        renderMetrics(m, est);

        // Gregas
        renderGreeks(m);

        // Tabela de pernas
        renderLegsTable(legs, est);

        // Gráfico
        refreshChart();
    }

    function renderMetrics(m, est) {
        // Posição inicial (prêmio líquido)
        setMetric('m-inicial', m.posInicial, true, 'Prêmio ' + (m.posInicial >= 0 ? 'recebido (crédito)' : 'pago (débito)'));

        // Ganho máximo
        setMetric('m-ganho', m.ganhoMax, true, m.ganhoMax < 1e9 ? 'Limitado' : 'Ilimitado');

        // Perda máxima
        setMetric('m-perda', m.perdaMax, true, m.perdaMax > -1e9 ? 'Limitada' : 'Ilimitada');

        // Break-even
        const beEl = document.getElementById('m-be1');
        if (beEl) {
            if (m.breakEvens.length === 0) {
                beEl.textContent = '—';
                beEl.className = 'metric-value neu';
            } else {
                beEl.textContent = m.breakEvens.map(v => UI.brl(v)).join(' / ');
                beEl.className = 'metric-value neu';
            }
        }

        // Margem
        setMetric('m-margem', m.margem, false, 'Garantia aprox.');

        // Prêmio líquido por lote
        const qtdTotal = state.legs.reduce((acc, l) => acc + (parseFloat(l.qtd) || 0), 0);
        setMetric('m-premio', m.premioLiq, true, `${qtdTotal} opções no total`);

        // Preço atual do ativo
        const s0 = parseFloat(est.precoAtual);
        UI.setText('m-preco', isNaN(s0) ? '—' : UI.brl(s0));
    }

    function setMetric(id, value, color, sub) {
        const el = document.getElementById(id);
        const sub_el = document.getElementById(id + '-sub');
        if (!el) return;
        el.textContent = UI.brl(value);
        if (color) el.className = 'metric-value ' + UI.colorPnl(value);
        if (sub_el) sub_el.textContent = sub || '';
    }

    function renderGreeks(m) {
        const fmt = (v, d = 4) => v !== null ? parseFloat(v).toFixed(d) : '—';
        UI.setText('g-delta', fmt(m.delta, 2));
        UI.setText('g-gamma', fmt(m.gamma, 4));
        UI.setText('g-theta', fmt(m.theta, 4));
        UI.setText('g-vega', fmt(m.vega, 4));
        UI.setText('g-rho', fmt(m.rho, 4));
        // Colorir delta e theta
        const dEl = document.getElementById('g-delta');
        if (dEl && m.delta !== null) dEl.className = 'greek-val ' + (m.delta > 0 ? 'pos' : m.delta < 0 ? 'neg' : '');
        const tEl = document.getElementById('g-theta');
        if (tEl && m.theta !== null) tEl.className = 'greek-val ' + (m.theta > 0 ? 'pos' : m.theta < 0 ? 'neg' : '');
    }

    function renderLegsTable(legs, est) {
        const tbody = document.getElementById('legs-tbody');
        if (!legs.length) {
            tbody.innerHTML = '<tr><td colspan="11" class="empty-cell">Nenhuma perna adicionada. Clique em "+ Perna".</td></tr>';
            return;
        }

        const S0 = parseFloat(est.precoAtual) || 0;
        const r = 0.1075;
        let T = 0;
        if (est.dataVenc) {
            const dias = UI.diasAteVenc(est.dataVenc);
            T = Math.max(0, (dias || 0) / 365);
        }

        tbody.innerHTML = '';
        legs.forEach(leg => {
            const K = parseFloat(leg.strike) || 0;
            const prem = parseFloat(leg.premio) || 0;
            const qtd = parseFloat(leg.qtd) || 1;
            const mult = leg.operacao === 'compra' ? 1 : -1;
            const iv = parseFloat(leg.iv);

            // P&L atual e BS
            let pnlAtual = null;
            let bsDelta = null, bsGamma = null, bsTheta = null, bsVega = null;
            let bsPreco = null;

            if (S0 > 0 && K > 0 && !isNaN(iv) && iv > 0) {
                const sigma = iv / 100;
                const gks = BS.greeks(leg.tipo, S0, K, T, r, sigma);
                bsDelta = gks.delta;
                bsGamma = gks.gamma;
                bsTheta = gks.theta;
                bsVega = gks.vega;
                bsPreco = BS.price(leg.tipo, S0, K, T, r, sigma);
                pnlAtual = mult * qtd * (bsPreco - prem);
            } else if (S0 > 0 && K > 0) {
                // Sem IV: só payoff na expiração
                const intrin = leg.tipo === 'call' ? Math.max(0, S0 - K) : Math.max(0, K - S0);
                pnlAtual = mult * qtd * (intrin - prem);
            }

            const deltaDisp = bsDelta !== null ? bsDelta.toFixed(2)
                : (leg.delta !== null && leg.delta !== '' ? parseFloat(leg.delta).toFixed(2) : '—');
            const opTag = leg.operacao === 'compra'
                ? '<span class="tag tag-buy">Compra</span>'
                : '<span class="tag tag-sell">Venda</span>';
            const tipoTag = leg.tipo === 'call'
                ? '<span class="tag tag-call">CALL</span>'
                : '<span class="tag tag-put">PUT</span>';

            const pnlCls = pnlAtual !== null ? UI.colorPnl(pnlAtual) : '';
            const bsPrecoStr = bsPreco !== null ? UI.brl(bsPreco) : '—';
            const ivStr = (!isNaN(iv) && iv > 0) ? iv.toFixed(1) + '%' : '—';

            const tr = document.createElement('tr');
            tr.innerHTML = `
        <td>${opTag}</td>
        <td>${tipoTag}</td>
        <td class="mono">${qtd}</td>
        <td class="mono">${UI.brl(K)}</td>
        <td class="ticker-cell">${leg.ticker || '—'}</td>
        <td>${UI.fmtDate(leg.vencimento)}</td>
        <td class="mono">${UI.brl(prem)}</td>
        <td class="mono">${bsPrecoStr}</td>
        <td class="mono">${ivStr}</td>
        <td class="mono">${deltaDisp}</td>
        <td class="mono ${pnlCls}">${pnlAtual !== null ? UI.brl(pnlAtual) : '—'}</td>
        <td>
          <div class="action-btns">
            <button class="btn btn-icon" title="Editar" onclick="App.openEditLeg(${leg.id})">✎</button>
            <button class="btn btn-icon btn-danger" title="Excluir" onclick="App.deleteLeg(${leg.id})">✕</button>
          </div>
        </td>
      `;
            tbody.appendChild(tr);
        });
    }

    function refreshChart() {
        if (!state.estrutura || !state.legs.length) { ChartModule.destroy(); return; }
        const showCurrent = document.getElementById('toggle-atual')?.checked ?? true;
        ChartModule.render('payoff-canvas', state.estrutura, state.legs, showCurrent);
    }

    // ── Modal: Nova / Editar Estrutura ───────────────────────
    function openNewEstrutura() {
        state.editEstId = null;
        UI.setVal('est-nome', '');
        UI.setVal('est-ativo', '');
        UI.setVal('est-tipo', 'Bull Spread');
        UI.setVal('est-preco', '');
        UI.setVal('est-venc', '');
        UI.setVal('est-obs', '');
        UI.setText('modal-est-title', 'Nova Estrutura');
        UI.openModal('modal-estrutura');
    }

    function openEditEstrutura() {
        if (!state.estrutura) return;
        const e = state.estrutura;
        state.editEstId = e.id;
        UI.setVal('est-nome', e.nome || '');
        UI.setVal('est-ativo', e.ativo || '');
        UI.setVal('est-tipo', e.tipo || 'Personalizada');
        UI.setVal('est-preco', e.precoAtual || '');
        UI.setVal('est-venc', e.dataVenc || '');
        UI.setVal('est-obs', e.obs || '');
        UI.setText('modal-est-title', 'Editar Estrutura');
        UI.openModal('modal-estrutura');
    }

    async function saveEstrutura() {
        const nome = UI.val('est-nome');
        const ativo = UI.val('est-ativo').toUpperCase();
        if (!nome) { UI.toast('Informe o nome da estrutura.', 'error'); return; }
        if (!ativo) { UI.toast('Informe o ativo (ticker).', 'error'); return; }

        const obj = {
            nome, ativo,
            tipo: UI.val('est-tipo'),
            precoAtual: parseFloat(UI.val('est-preco')) || null,
            dataVenc: UI.val('est-venc') || null,
            obs: UI.val('est-obs'),
        };
        if (state.editEstId) obj.id = state.editEstId;

        const id = await DB.saveEstrutura(obj);
        UI.closeModal('modal-estrutura');
        UI.toast('Estrutura salva!', 'success');
        await selectEstrutura(state.editEstId || id);
    }

    async function deleteEstrutura() {
        if (!state.estrutura) return;
        if (!UI.confirm(`Excluir "${state.estrutura.nome}" e todas as suas pernas? Esta ação não pode ser desfeita.`)) return;
        await DB.deleteEstrutura(state.estrutura.id);
        state.estrutura = null;
        state.legs = [];
        ChartModule.destroy();
        document.getElementById('section-empty').style.display = '';
        document.getElementById('section-main').style.display = 'none';
        await renderSidebar();
        UI.toast('Estrutura excluída.', 'info');
    }

    // ── Modal: Adicionar / Editar Perna ──────────────────────
    function openAddLeg() {
        if (!state.estrutura) { UI.toast('Selecione uma estrutura primeiro.', 'error'); return; }
        state.editLegId = null;
        UI.setText('modal-leg-title', 'Adicionar Perna');
        UI.setVal('leg-op', 'compra');
        UI.setVal('leg-tipo', 'call');
        UI.setVal('leg-qtd', '100');
        UI.setVal('leg-strike', '');
        UI.setVal('leg-ticker', '');
        UI.setVal('leg-venc', state.estrutura.dataVenc || '');
        UI.setVal('leg-premio', '');
        UI.setVal('leg-iv', '');
        UI.setVal('leg-delta', '');
        UI.setVal('leg-gamma', '');
        UI.setVal('leg-theta', '');
        UI.setVal('leg-vega', '');
        UI.openModal('modal-leg');
    }

    async function openEditLeg(id) {
        const leg = await DB.get('legs', id);
        if (!leg) return;
        state.editLegId = id;
        UI.setText('modal-leg-title', 'Editar Perna');
        UI.setVal('leg-op', leg.operacao);
        UI.setVal('leg-tipo', leg.tipo);
        UI.setVal('leg-qtd', leg.qtd);
        UI.setVal('leg-strike', leg.strike);
        UI.setVal('leg-ticker', leg.ticker || '');
        UI.setVal('leg-venc', leg.vencimento || '');
        UI.setVal('leg-premio', leg.premio);
        UI.setVal('leg-iv', leg.iv !== null ? leg.iv : '');
        UI.setVal('leg-delta', leg.delta !== null ? leg.delta : '');
        UI.setVal('leg-gamma', leg.gamma !== null ? leg.gamma : '');
        UI.setVal('leg-theta', leg.theta !== null ? leg.theta : '');
        UI.setVal('leg-vega', leg.vega !== null ? leg.vega : '');
        UI.openModal('modal-leg');
    }

    // Auto-calcular gregas ao preencher IV
    function onIVChange() {
        const S0 = parseFloat(state.estrutura?.precoAtual) || 0;
        const K = parseFloat(UI.val('leg-strike')) || 0;
        const iv = parseFloat(UI.val('leg-iv')) || 0;
        const tipo = UI.val('leg-tipo');
        const venc = UI.val('leg-venc');
        if (!S0 || !K || !iv || !venc) return;

        const hoje = new Date();
        const v = new Date(venc + 'T23:59:59');
        const T = Math.max(0, (v - hoje) / (1000 * 60 * 60 * 24 * 365));
        if (T <= 0) return;

        const r = 0.1075;
        const sigma = iv / 100;
        const gks = BS.greeks(tipo, S0, K, T, r, sigma);
        const preco = BS.price(tipo, S0, K, T, r, sigma);

        if (gks.delta !== null) {
            UI.setVal('leg-delta', gks.delta.toFixed(4));
            UI.setVal('leg-gamma', gks.gamma.toFixed(6));
            UI.setVal('leg-theta', gks.theta.toFixed(6));
            UI.setVal('leg-vega', gks.vega.toFixed(6));
            // sugerir prêmio BS se campo vazio
            if (!UI.val('leg-premio')) UI.setVal('leg-premio', preco.toFixed(4));
        }
    }

    async function saveLeg() {
        const strike = parseFloat(UI.val('leg-strike'));
        const qtd = parseInt(UI.val('leg-qtd'));
        if (!strike || strike <= 0) { UI.toast('Informe o Strike.', 'error'); return; }
        if (!qtd || qtd <= 0) { UI.toast('Informe a Quantidade.', 'error'); return; }

        const obj = {
            estruturaId: state.estrutura.id,
            operacao: UI.val('leg-op'),
            tipo: UI.val('leg-tipo'),
            qtd,
            strike,
            ticker: UI.val('leg-ticker').toUpperCase(),
            vencimento: UI.val('leg-venc') || null,
            premio: parseFloat(UI.val('leg-premio')) || 0,
            iv: parseFloat(UI.val('leg-iv')) || null,
            delta: UI.val('leg-delta') !== '' ? parseFloat(UI.val('leg-delta')) : null,
            gamma: UI.val('leg-gamma') !== '' ? parseFloat(UI.val('leg-gamma')) : null,
            theta: UI.val('leg-theta') !== '' ? parseFloat(UI.val('leg-theta')) : null,
            vega: UI.val('leg-vega') !== '' ? parseFloat(UI.val('leg-vega')) : null,
        };
        if (state.editLegId) obj.id = state.editLegId;

        await DB.saveLeg(obj);
        UI.closeModal('modal-leg');
        state.legs = await DB.getLegs(state.estrutura.id);
        await renderStructView();
        await renderSidebar();
        UI.toast('Perna salva!', 'success');
    }

    async function deleteLeg(id) {
        if (!UI.confirm('Excluir esta perna?')) return;
        await DB.del('legs', id);
        state.legs = await DB.getLegs(state.estrutura.id);
        await renderStructView();
        await renderSidebar();
        UI.toast('Perna removida.', 'info');
    }

    // ── Histórico ────────────────────────────────────────────
    async function renderHistorico() {
        const tbody = document.getElementById('hist-tbody');
        if (!tbody) return;
        const ests = await DB.getEstruturas();
        if (!ests.length) {
            tbody.innerHTML = '<tr><td colspan="8" class="empty-cell">Nenhuma estrutura cadastrada.</td></tr>';
            return;
        }
        tbody.innerHTML = '';
        for (const est of ests) {
            const legs = await DB.getLegs(est.id);
            const metrics = BS.calcMetrics(est, legs);
            const dias = UI.diasAteVenc(est.dataVenc);
            const statusCls = dias === null ? '' : dias < 0 ? 'neg' : dias <= 7 ? 'amber' : 'pos';
            const statusTxt = dias === null ? '—' : dias < 0 ? 'Vencido' : dias <= 7 ? `${dias}d ⚠` : `${dias}d`;

            const tr = document.createElement('tr');
            tr.innerHTML = `
        <td style="font-weight:500">${est.nome}</td>
        <td><span class="tag tag-call">${est.ativo || '?'}</span></td>
        <td>${est.tipo || '—'}</td>
        <td>${UI.fmtDate(est.criadoEm?.substring(0, 10))}</td>
        <td class="mono">${legs.length}</td>
        <td class="mono ${UI.colorPnl(metrics.premioLiq)}">${UI.brl(metrics.premioLiq)}</td>
        <td class="mono ${UI.colorPnl(metrics.ganhoMax)}">${UI.brl(metrics.ganhoMax)}</td>
        <td class="mono ${statusCls}">${statusTxt}</td>
        <td>
          <button class="btn btn-sm" onclick="App.goToEstrutura(${est.id})">Ver ↗</button>
        </td>
      `;
            tbody.appendChild(tr);
        }
    }

    async function goToEstrutura(id) {
        showPage('simulador');
        await selectEstrutura(id);
    }

    // ── Dashboard ────────────────────────────────────────────
    async function renderDashboard() {
        const ests = await DB.getEstruturas();
        const allLegs = await DB.getAll('legs');

        UI.setText('dash-total', ests.length);
        UI.setText('dash-pernas', allLegs.length);

        let credito = 0, debito = 0, ganhoTotal = 0, perdaTotal = 0;
        const tipoMap = {};
        const estNames = [], estPremios = [];

        for (const est of ests) {
            const legs = allLegs.filter(l => l.estruturaId === est.id);
            const metrics = BS.calcMetrics(est, legs);
            if (metrics.premioLiq > 0) credito += metrics.premioLiq;
            else debito += metrics.premioLiq;
            ganhoTotal += metrics.ganhoMax;
            perdaTotal += metrics.perdaMax;
            tipoMap[est.tipo || 'Outro'] = (tipoMap[est.tipo || 'Outro'] || 0) + 1;
            estNames.push(est.nome.substring(0, 14));
            estPremios.push(metrics.premioLiq);
        }

        UI.setText('dash-credito', UI.brl(credito));
        UI.setText('dash-debito', UI.brl(Math.abs(debito)));
        UI.setText('dash-ganho-max', UI.brl(ganhoTotal));
        UI.setText('dash-perda-max', UI.brl(perdaTotal));

        // Destruir gráficos antigos
        state.dashCharts.forEach(c => c.destroy());
        state.dashCharts = [];

        // Gráfico pizza: tipos
        const ctx1 = document.getElementById('dash-chart-tipos')?.getContext('2d');
        if (ctx1 && Object.keys(tipoMap).length) {
            state.dashCharts.push(new Chart(ctx1, {
                type: 'doughnut',
                data: {
                    labels: Object.keys(tipoMap),
                    datasets: [{
                        data: Object.values(tipoMap),
                        backgroundColor: ['#4ade80', '#60a5fa', '#fbbf24', '#a78bfa', '#f87171', '#22d3ee', '#f472b6', '#fb923c']
                    }]
                },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    plugins: {
                        legend: { labels: { color: '#8b90a0', font: { size: 11 }, boxWidth: 12, boxHeight: 12 } }
                    }
                }
            }));
        }

        // Gráfico barras: prêmio por estrutura
        const ctx2 = document.getElementById('dash-chart-premios')?.getContext('2d');
        if (ctx2 && estNames.length) {
            state.dashCharts.push(new Chart(ctx2, {
                type: 'bar',
                data: {
                    labels: estNames,
                    datasets: [{
                        label: 'Prêmio Líquido',
                        data: estPremios,
                        backgroundColor: estPremios.map(v => v >= 0 ? 'rgba(74,222,128,0.6)' : 'rgba(248,113,113,0.6)'),
                        borderRadius: 4,
                    }]
                },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        x: { ticks: { color: '#8b90a0', font: { size: 10 } }, grid: { display: false } },
                        y: {
                            ticks: { color: '#8b90a0', callback: v => UI.brl(v) },
                            grid: { color: 'rgba(255,255,255,0.05)' }
                        }
                    }
                }
            }));
        }
    }

    // ── API Pública ─────────────────────────────────────────
    return {
        init,
        openNewEstrutura,
        openEditEstrutura,
        saveEstrutura,
        deleteEstrutura,
        openAddLeg,
        openEditLeg,
        saveLeg,
        deleteLeg,
        onIVChange,
        goToEstrutura,
        showPage,
    };
})();

// Boot
document.addEventListener('DOMContentLoaded', () => App.init());
/**
 * Eagle System — Chart Module
 * Gráfico de payoff correto usando Black-Scholes
 */

'use strict';

const ChartModule = (() => {
    let _chart = null;

    const COLORS = {
        profit: 'rgba(74, 222, 128, 0.20)',
        profitLine: '#4ade80',
        loss: 'rgba(248, 113, 113, 0.20)',
        lossLine: '#f87171',
        current: '#fbbf24',
        currentFill: 'rgba(251, 191, 36, 0.08)',
        spot: '#60a5fa',
        zero: 'rgba(255,255,255,0.15)',
        grid: 'rgba(255,255,255,0.05)',
        tick: '#555c70',
    };

    /**
     * Destrói e recria o gráfico de payoff
     * @param {string} canvasId
     * @param {object} estrutura
     * @param {Array}  legs
     * @param {boolean} showCurrent - mostrar curva BS atual
     */
    function render(canvasId, estrutura, legs, showCurrent = true) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;

        if (_chart) { _chart.destroy(); _chart = null; }
        if (!legs.length) return;

        const data = BS.computePayoffSeries(estrutura, legs);
        if (!data) return;

        const { labels, payoffExpiry, payoffCurrent, S0, T } = data;
        const brl = UI.brl;

        // Separar positivo/negativo para colorir áreas
        const posExpiry = payoffExpiry.map(v => v >= 0 ? v : 0);
        const negExpiry = payoffExpiry.map(v => v < 0 ? v : 0);

        const datasets = [
            // Área positiva (lucro)
            {
                label: 'Lucro (Exp.)',
                data: posExpiry,
                borderColor: COLORS.profitLine,
                backgroundColor: COLORS.profit,
                fill: true,
                tension: 0.2,
                pointRadius: 0,
                borderWidth: 2,
                order: 2,
            },
            // Área negativa (perda)
            {
                label: 'Perda (Exp.)',
                data: negExpiry,
                borderColor: COLORS.lossLine,
                backgroundColor: COLORS.loss,
                fill: true,
                tension: 0.2,
                pointRadius: 0,
                borderWidth: 2,
                order: 3,
            },
        ];

        // Curva Black-Scholes atual (se T > 0 e showCurrent)
        if (showCurrent && payoffCurrent && T > 0.001) {
            const posCurrent = payoffCurrent.map(v => v >= 0 ? v : 0);
            const negCurrent = payoffCurrent.map(v => v < 0 ? v : 0);
            datasets.push({
                label: 'Lucro (Atual BS)',
                data: posCurrent,
                borderColor: COLORS.current,
                backgroundColor: COLORS.currentFill,
                fill: true,
                tension: 0.3,
                pointRadius: 0,
                borderWidth: 1.5,
                borderDash: [6, 3],
                order: 1,
            });
            datasets.push({
                label: 'Perda (Atual BS)',
                data: negCurrent,
                borderColor: COLORS.current,
                backgroundColor: 'transparent',
                fill: false,
                tension: 0.3,
                pointRadius: 0,
                borderWidth: 1.5,
                borderDash: [6, 3],
                order: 1,
            });
        }

        const ctx = canvas.getContext('2d');

        _chart = new Chart(ctx, {
            type: 'line',
            data: { labels, datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: { duration: 300 },
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: '#1a1e2a',
                        borderColor: 'rgba(255,255,255,0.1)',
                        borderWidth: 1,
                        padding: 10,
                        callbacks: {
                            title: (items) => `Preço: ${brl(parseFloat(items[0].label))}`,
                            label: (item) => {
                                if (item.dataset.label.includes('Atual')) return `P&L Atual (BS): ${brl(item.raw)}`;
                                const v = item.raw;
                                return `P&L Exp.: ${brl(v)}`;
                            },
                            afterBody: (items) => {
                                // Calcular P&L total no vencimento nesse ponto
                                const idx = items[0].dataIndex;
                                const totalExp = payoffExpiry[idx];
                                return [`━━━━━━━━━━━━━━`, `Total Exp.: ${brl(totalExp)}`];
                            }
                        }
                    },
                    // Linha vertical no preço atual
                    annotation: S0 > 0 ? {
                        annotations: {
                            spotLine: {
                                type: 'line',
                                xMin: S0,
                                xMax: S0,
                                borderColor: COLORS.spot,
                                borderWidth: 1.5,
                                borderDash: [4, 4],
                                label: {
                                    content: `Spot: ${brl(S0)}`,
                                    display: true,
                                    color: COLORS.spot,
                                    font: { size: 11 },
                                    position: 'start',
                                    backgroundColor: 'rgba(96,165,250,0.15)',
                                    padding: { x: 6, y: 3 },
                                }
                            },
                            zeroLine: {
                                type: 'line',
                                yMin: 0,
                                yMax: 0,
                                borderColor: COLORS.zero,
                                borderWidth: 1,
                            }
                        }
                    } : {}
                },
                scales: {
                    x: {
                        type: 'linear',
                        ticks: {
                            maxTicksLimit: 10,
                            color: COLORS.tick,
                            font: { size: 11 },
                            callback: v => 'R$' + parseFloat(v).toFixed(2)
                        },
                        grid: { color: COLORS.grid }
                    },
                    y: {
                        ticks: {
                            color: COLORS.tick,
                            font: { size: 11 },
                            callback: v => {
                                if (Math.abs(v) >= 1000) return 'R$' + (v / 1000).toFixed(1) + 'k';
                                return 'R$' + v.toFixed(0);
                            }
                        },
                        grid: { color: COLORS.grid }
                    }
                }
            }
        });

        return _chart;
    }

    function destroy() {
        if (_chart) { _chart.destroy(); _chart = null; }
    }

    return { render, destroy };
})();
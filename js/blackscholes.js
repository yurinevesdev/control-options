/**
 * Eagle System — Black-Scholes Engine
 * Implementação correta do modelo Black-Scholes para:
 *   - Preço teórico de opções europeias (Call e Put)
 *   - Gregas: Delta, Gamma, Theta, Vega, Rho
 *   - Volatilidade Implícita (Newton-Raphson)
 *   - Cálculo de payoff na expiração e antes (usando BS)
 */

'use strict';

const BS = (() => {

    // Função de distribuição normal acumulada (CDF) — Abramowitz & Stegun
    function normCDF(x) {
        const a1 = 0.254829592;
        const a2 = -0.284496736;
        const a3 = 1.421413741;
        const a4 = -1.453152027;
        const a5 = 1.061405429;
        const p = 0.3275911;
        const sign = x < 0 ? -1 : 1;
        x = Math.abs(x) / Math.sqrt(2);
        const t = 1.0 / (1.0 + p * x);
        const y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * Math.exp(-x * x);
        return 0.5 * (1.0 + sign * y);
    }

    // Função densidade de probabilidade normal (PDF)
    function normPDF(x) {
        return Math.exp(-0.5 * x * x) / Math.sqrt(2 * Math.PI);
    }

    /**
     * Calcula d1 e d2 do modelo Black-Scholes
     * @param {number} S  - Preço spot do ativo
     * @param {number} K  - Strike da opção
     * @param {number} T  - Tempo até vencimento em ANOS
     * @param {number} r  - Taxa de juros livre de risco (ex: 0.10 para 10%)
     * @param {number} sigma - Volatilidade implícita anualizada (ex: 0.30 para 30%)
     * @param {number} [q=0] - Dividend yield contínuo
     */
    function d1d2(S, K, T, r, sigma, q = 0) {
        if (T <= 0 || sigma <= 0 || S <= 0 || K <= 0) return { d1: NaN, d2: NaN };
        const d1 = (Math.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / (sigma * Math.sqrt(T));
        const d2 = d1 - sigma * Math.sqrt(T);
        return { d1, d2 };
    }

    /**
     * Preço Black-Scholes de uma opção europeia
     * @param {'call'|'put'} type
     * @param {number} S  - Preço spot
     * @param {number} K  - Strike
     * @param {number} T  - Tempo em anos
     * @param {number} r  - Taxa livre de risco
     * @param {number} sigma - Volatilidade
     * @param {number} [q=0] - Dividend yield
     * @returns {number} Preço teórico
     */
    function price(type, S, K, T, r, sigma, q = 0) {
        if (T <= 0) {
            // No vencimento: valor intrínseco
            if (type === 'call') return Math.max(0, S - K);
            return Math.max(0, K - S);
        }
        const { d1, d2 } = d1d2(S, K, T, r, sigma, q);
        if (isNaN(d1)) return 0;
        if (type === 'call') {
            return S * Math.exp(-q * T) * normCDF(d1) - K * Math.exp(-r * T) * normCDF(d2);
        } else {
            return K * Math.exp(-r * T) * normCDF(-d2) - S * Math.exp(-q * T) * normCDF(-d1);
        }
    }

    /**
     * Gregas Black-Scholes completas
     * @returns {{ delta, gamma, theta, vega, rho }}
     *   theta: por DIA (dividido por 365)
     *   vega:  por 1% de mudança em vol (dividido por 100)
     *   rho:   por 1% de mudança na taxa (dividido por 100)
     */
    function greeks(type, S, K, T, r, sigma, q = 0) {
        if (T <= 0 || sigma <= 0 || S <= 0 || K <= 0) {
            return { delta: null, gamma: null, theta: null, vega: null, rho: null };
        }
        const { d1, d2 } = d1d2(S, K, T, r, sigma, q);
        const Nd1 = normCDF(d1);
        const Nd2 = normCDF(d2);
        const nd1 = normPDF(d1);
        const eqT = Math.exp(-q * T);
        const erT = Math.exp(-r * T);
        const sqT = Math.sqrt(T);

        let delta, theta, rho;

        if (type === 'call') {
            delta = eqT * Nd1;
            theta = (-(S * eqT * nd1 * sigma) / (2 * sqT)
                - r * K * erT * Nd2
                + q * S * eqT * Nd1) / 365;
            rho = K * T * erT * Nd2 / 100;
        } else {
            delta = -eqT * normCDF(-d1);
            theta = (-(S * eqT * nd1 * sigma) / (2 * sqT)
                + r * K * erT * normCDF(-d2)
                - q * S * eqT * normCDF(-d1)) / 365;
            rho = -K * T * erT * normCDF(-d2) / 100;
        }

        const gamma = (eqT * nd1) / (S * sigma * sqT);
        const vega = S * eqT * nd1 * sqT / 100;

        return { delta, gamma, theta, vega, rho };
    }

    /**
     * Volatilidade Implícita via Newton-Raphson
     * @param {'call'|'put'} type
     * @param {number} S, K, T, r, q
     * @param {number} marketPrice - Preço de mercado da opção
     * @returns {number|null} IV (0.01 a 5.00) ou null se não convergir
     */
    function impliedVol(type, S, K, T, r, marketPrice, q = 0) {
        if (T <= 0 || marketPrice <= 0) return null;
        let sigma = 0.3; // chute inicial: 30%
        for (let i = 0; i < 100; i++) {
            const { d1 } = d1d2(S, K, T, r, sigma, q);
            const p = price(type, S, K, T, r, sigma, q);
            const vg = S * Math.exp(-q * T) * normPDF(d1) * Math.sqrt(T); // vega sem divisão por 100
            const diff = p - marketPrice;
            if (Math.abs(diff) < 1e-8) break;
            if (Math.abs(vg) < 1e-10) break;
            sigma = sigma - diff / vg;
            if (sigma <= 0) sigma = 1e-5;
            if (sigma > 10) return null;
        }
        return sigma >= 0.001 && sigma <= 10 ? sigma : null;
    }

    /**
     * Payoff de UMA perna na expiração (T=0)
     * Fórmula exata: valor intrínseco menos prêmio pago/recebido
     * @param {object} leg - { operacao:'compra'|'venda', tipo:'call'|'put', strike, premio, qtd }
     * @param {number} S   - Preço do ativo na expiração
     * @returns {number} P&L da perna no vencimento
     */
    function legPayoffAtExpiry(leg, S) {
        const K = parseFloat(leg.strike) || 0;
        const prem = parseFloat(leg.premio) || 0;
        const qtd = parseFloat(leg.qtd) || 1;
        const mult = leg.operacao === 'compra' ? 1 : -1; // compra: long, venda: short

        let intrinsic;
        if (leg.tipo === 'call') intrinsic = Math.max(0, S - K);
        else intrinsic = Math.max(0, K - S);

        // P&L = direção × qtd × (valor_intrínseco - prêmio_pago)
        // compra: pagamos prêmio → P&L = intrínseco - prêmio
        // venda:  recebemos prêmio → P&L = -(intrínseco - prêmio) = prêmio - intrínseco
        return mult * qtd * (intrinsic - prem);
    }

    /**
     * P&L atual de uma perna com Black-Scholes (antes do vencimento)
     * @param {object} leg  - com iv (volatilidade implícita em %)
     * @param {number} S    - Preço atual
     * @param {number} T    - Tempo até vencimento em anos
     * @param {number} r    - Taxa de juros
     * @returns {number} P&L atual da perna
     */
    function legPnLCurrent(leg, S, T, r = 0.1075) {
        const K = parseFloat(leg.strike) || 0;
        const prem = parseFloat(leg.premio) || 0;
        const qtd = parseFloat(leg.qtd) || 1;
        const iv = parseFloat(leg.iv) || 30;
        const mult = leg.operacao === 'compra' ? 1 : -1;
        const sigma = iv / 100;
        const currentValue = price(leg.tipo, S, K, T, r, sigma);
        return mult * qtd * (currentValue - prem);
    }

    /**
     * Gera série de pontos para o gráfico de payoff
     * @param {object} estrutura - { precoAtual, dataVenc }
     * @param {Array}  legs
     * @param {number} [numPoints=300]
     * @returns {{ labels, payoffExpiry, payoffCurrent, xMin, xMax }}
     */
    function computePayoffSeries(estrutura, legs, numPoints = 300) {
        if (!legs.length) return null;

        const S0 = parseFloat(estrutura.precoAtual) || 20;
        const r = 0.1075; // Selic aproximada

        // Tempo até vencimento
        let T = 0;
        if (estrutura.dataVenc) {
            const hoje = new Date();
            const venc = new Date(estrutura.dataVenc + 'T23:59:59');
            const dias = (venc - hoje) / (1000 * 60 * 60 * 24);
            T = Math.max(0, dias / 365);
        }

        // Range de preços: de 50% a 150% do spot, alargando para cobrir strikes
        const strikes = legs.map(l => parseFloat(l.strike)).filter(s => s > 0);
        const minStr = Math.min(S0, ...strikes);
        const maxStr = Math.max(S0, ...strikes);
        const xMin = Math.max(0.01, minStr * 0.6);
        const xMax = maxStr * 1.4;

        const labels = [];
        const payoffExpiry = [];
        const payoffCurrent = [];

        for (let i = 0; i <= numPoints; i++) {
            const S = xMin + (xMax - xMin) * (i / numPoints);
            labels.push(S);

            // Payoff na expiração (T=0, valor intrínseco)
            let pnlExp = 0;
            for (const leg of legs) {
                pnlExp += legPayoffAtExpiry(leg, S);
            }
            payoffExpiry.push(pnlExp);

            // P&L atual (Black-Scholes se T > 0)
            if (T > 0.001) {
                let pnlCur = 0;
                for (const leg of legs) {
                    pnlCur += legPnLCurrent(leg, S, T, r);
                }
                payoffCurrent.push(pnlCur);
            }
        }

        return { labels, payoffExpiry, payoffCurrent: payoffCurrent.length ? payoffCurrent : null, xMin, xMax, T, S0 };
    }

    /**
     * Calcula métricas completas da estrutura
     */
    function calcMetrics(estrutura, legs) {
        const zero = { posInicial: 0, ganhoMax: 0, perdaMax: 0, breakEvens: [], margem: 0, premioLiq: 0, delta: null, gamma: null, theta: null, vega: null, rho: null };
        if (!legs.length) return zero;

        const S0 = parseFloat(estrutura.precoAtual) || 0;
        const r = 0.1075;

        // Tempo até vencimento
        let T = 0;
        if (estrutura.dataVenc) {
            const hoje = new Date();
            const venc = new Date(estrutura.dataVenc + 'T23:59:59');
            const dias = (venc - hoje) / (1000 * 60 * 60 * 24);
            T = Math.max(0, dias / 365);
        }

        // Prêmio líquido: compra paga, venda recebe
        let premioLiq = 0;
        let gDelta = 0, gGamma = 0, gTheta = 0, gVega = 0, gRho = 0;
        let hasGreeks = false;

        for (const leg of legs) {
            const prem = parseFloat(leg.premio) || 0;
            const qtd = parseFloat(leg.qtd) || 1;
            const mult = leg.operacao === 'compra' ? -1 : 1; // compra paga, venda recebe
            premioLiq += mult * prem * qtd;

            // Gregas: usar BS se tiver IV, senão usar valores manuais
            const K = parseFloat(leg.strike) || 0;
            const iv_pct = parseFloat(leg.iv);
            const sigma = (iv_pct > 0) ? iv_pct / 100 : null;

            let g;
            if (sigma && T > 0 && S0 > 0 && K > 0) {
                g = greeks(leg.tipo, S0, K, T, r, sigma);
                hasGreeks = true;
            } else if (leg.delta !== null && leg.delta !== '') {
                // Usar valores manuais
                g = {
                    delta: parseFloat(leg.delta) || 0,
                    gamma: parseFloat(leg.gamma) || 0,
                    theta: parseFloat(leg.theta) || 0,
                    vega: parseFloat(leg.vega) || 0,
                    rho: 0
                };
                hasGreeks = true;
            } else {
                g = null;
            }

            if (g) {
                const d = leg.operacao === 'compra' ? 1 : -1;
                gDelta += d * (g.delta || 0) * qtd;
                gGamma += d * (g.gamma || 0) * qtd;
                gTheta += d * (g.theta || 0) * qtd;
                gVega += d * (g.vega || 0) * qtd;
                gRho += d * (g.rho || 0) * qtd;
            }
        }

        // Calcular payoff para encontrar max/min/breakeven
        const series = computePayoffSeries(estrutura, legs, 500);
        let ganhoMax = -Infinity, perdaMax = Infinity;
        const breakEvens = [];

        if (series) {
            for (const v of series.payoffExpiry) {
                if (v > ganhoMax) ganhoMax = v;
                if (v < perdaMax) perdaMax = v;
            }
            // Break-even: cruzamentos de zero
            for (let i = 0; i < series.payoffExpiry.length - 1; i++) {
                const y0 = series.payoffExpiry[i];
                const y1 = series.payoffExpiry[i + 1];
                if ((y0 <= 0 && y1 > 0) || (y0 >= 0 && y1 < 0)) {
                    const x0 = series.labels[i];
                    const x1 = series.labels[i + 1];
                    const xBE = x0 + (x1 - x0) * (-y0 / (y1 - y0));
                    breakEvens.push(xBE);
                }
            }
        }

        if (ganhoMax === -Infinity) ganhoMax = 0;
        if (perdaMax === Infinity) perdaMax = 0;

        // Margem: aproximação para estruturas de crédito (máxima perda)
        const margem = Math.abs(perdaMax) > 0 ? Math.abs(perdaMax) : 0;

        return {
            posInicial: premioLiq,
            ganhoMax,
            perdaMax,
            breakEvens,
            margem,
            premioLiq,
            delta: hasGreeks ? gDelta : null,
            gamma: hasGreeks ? gGamma : null,
            theta: hasGreeks ? gTheta : null,
            vega: hasGreeks ? gVega : null,
            rho: hasGreeks ? gRho : null,
        };
    }

    return { price, greeks, impliedVol, legPayoffAtExpiry, legPnLCurrent, computePayoffSeries, calcMetrics, normCDF };

})();

// Exporta para uso nos módulos
if (typeof module !== 'undefined') module.exports = BS;
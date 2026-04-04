/**
 * Eagle System — UI Utilities
 */

'use strict';

const UI = (() => {

    // ── Formatação ──────────────────────────────────────────
    const brl = (v, decimals = 2) => {
        if (v === null || v === undefined || isNaN(v)) return '—';
        return new Intl.NumberFormat('pt-BR', {
            style: 'currency', currency: 'BRL',
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals
        }).format(v);
    };

    const pct = (v, decimals = 1) => {
        if (v === null || v === undefined || isNaN(v)) return '—';
        return (v * 100).toFixed(decimals) + '%';
    };

    const num = (v, d = 2) => {
        if (v === null || v === undefined || isNaN(v)) return '—';
        return parseFloat(v).toFixed(d);
    };

    const fmtDate = (d) => {
        if (!d) return '—';
        return new Date(d + 'T12:00:00').toLocaleDateString('pt-BR');
    };

    const diasAteVenc = (dataVenc) => {
        if (!dataVenc) return null;
        const hoje = new Date();
        const venc = new Date(dataVenc + 'T23:59:59');
        const diff = Math.round((venc - hoje) / (1000 * 60 * 60 * 24));
        return diff;
    };

    const colorPnl = (v) => {
        if (v === null || v === undefined || isNaN(v)) return '';
        return v > 0 ? 'pos' : v < 0 ? 'neg' : 'neu';
    };

    // ── Modais ──────────────────────────────────────────────
    function openModal(id) {
        const el = document.getElementById(id);
        if (el) { el.classList.add('open'); el.focus(); }
    }

    function closeModal(id) {
        const el = document.getElementById(id);
        if (el) el.classList.remove('open');
    }

    // Fechar modal clicando no overlay
    document.addEventListener('click', e => {
        if (e.target.classList.contains('modal-overlay')) {
            e.target.classList.remove('open');
        }
    });

    // ESC fecha qualquer modal aberto
    document.addEventListener('keydown', e => {
        if (e.key === 'Escape') {
            document.querySelectorAll('.modal-overlay.open').forEach(m => m.classList.remove('open'));
        }
    });

    // ── Toast / Notificações ────────────────────────────────
    function toast(msg, type = 'info', duration = 3000) {
        const container = document.getElementById('toast-container') || createToastContainer();
        const el = document.createElement('div');
        el.className = `toast toast-${type}`;
        el.innerHTML = `<span class="toast-icon">${{ info: 'ℹ', success: '✓', error: '✕', warning: '⚠' }[type] || 'ℹ'}</span><span>${msg}</span>`;
        container.appendChild(el);
        setTimeout(() => el.classList.add('show'), 10);
        setTimeout(() => {
            el.classList.remove('show');
            setTimeout(() => el.remove(), 300);
        }, duration);
    }

    function createToastContainer() {
        const c = document.createElement('div');
        c.id = 'toast-container';
        document.body.appendChild(c);
        return c;
    }

    // ── Helpers DOM ─────────────────────────────────────────
    function qs(sel, ctx = document) { return ctx.querySelector(sel); }
    function qsa(sel, ctx = document) { return [...ctx.querySelectorAll(sel)]; }
    function el(tag, cls, html) {
        const e = document.createElement(tag);
        if (cls) e.className = cls;
        if (html) e.innerHTML = html;
        return e;
    }

    // Valor de input por ID
    function val(id) {
        const e = document.getElementById(id);
        return e ? e.value.trim() : '';
    }
    function setVal(id, v) {
        const e = document.getElementById(id);
        if (e) e.value = v ?? '';
    }
    function setText(id, v) {
        const e = document.getElementById(id);
        if (e) e.textContent = v ?? '—';
    }
    function setHtml(id, v) {
        const e = document.getElementById(id);
        if (e) e.innerHTML = v ?? '';
    }

    // Limpar formulário
    function clearForm(ids) {
        ids.forEach(id => setVal(id, ''));
    }

    // ── Confirm Dialog ──────────────────────────────────────
    function confirm(msg) {
        return window.confirm(msg);
    }

    // ── Tag HTML ────────────────────────────────────────────
    function tag(text, cls) {
        return `<span class="tag ${cls}">${text}</span>`;
    }

    return {
        brl, pct, num, fmtDate, diasAteVenc, colorPnl,
        openModal, closeModal,
        toast,
        qs, qsa, el, val, setVal, setText, setHtml, clearForm,
        confirm, tag
    };
})();
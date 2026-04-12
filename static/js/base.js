// Auto-dismiss toasts (5s)
document.querySelectorAll('[data-toast]').forEach(function (el) {
    setTimeout(function () {
        el.classList.remove('show');
        setTimeout(function () { if (el.parentNode) el.remove(); }, 300);
    }, 5000);
});

// Fechar modais
document.addEventListener('click', function (e) {
    if (e.target.classList.contains('modal-overlay')) e.target.classList.remove('open');
});
document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
        document.querySelectorAll('.modal-overlay.open').forEach(function (m) { m.classList.remove('open'); });
    }
});

// Atalho Ctrl+S para submeter formulário visível
document.addEventListener('keydown', function (e) {
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        var modals = document.querySelectorAll('.modal-overlay.open');
        if (modals.length) {
            e.preventDefault();
            var form = modals[modals.length - 1].querySelector('form');
            if (form) form.requestSubmit();
        }
    }
});

// Desabilitar botão ao submeter (evita duplo clique)
document.querySelectorAll('form[method="POST"]').forEach(function (f) {
    f.addEventListener('submit', function () {
        var btn = this.querySelector('button[type="submit"]');
        if (btn && !btn.disabled) {
            btn.disabled = true;
            btn.dataset.originalText = btn.textContent;
            btn.textContent = 'Salvando...';
        }
    });
});

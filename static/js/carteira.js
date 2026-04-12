document.addEventListener('DOMContentLoaded', function () {
    const page = document.getElementById('page-carteira');
    if (!page) return;

    const carteiraId = page.dataset.carteiraId || '';
    const carteiraUrl = page.dataset.carteiraUrl || '/carteira';

    function closeModal(modalId) {
        document.getElementById(modalId)?.classList.remove('open');
    }

    function openModalCarteira(id) {
        const modal = document.getElementById('modal-carteira');
        if (!modal) return;

        if (id) {
            document.getElementById('modal-carteira-title').textContent = 'Editar Carteira';
            document.getElementById('carteira-id').value = id;
        } else {
            document.getElementById('modal-carteira-title').textContent = 'Nova Carteira';
            document.getElementById('form-carteira')?.reset();
            document.getElementById('carteira-id').value = '';
        }

        modal.classList.add('open');
    }

    function openModalAtivo(id) {
        const modal = document.getElementById('modal-ativo');
        if (!modal) return;

        if (id) {
            document.getElementById('modal-ativo-title').textContent = 'Editar Ativo';
            document.getElementById('ativo-id').value = id;
        } else {
            document.getElementById('modal-ativo-title').textContent = 'Novo Ativo';
            document.getElementById('form-ativo')?.reset();
            document.getElementById('ativo-id').value = '';
        }

        modal.classList.add('open');
    }

    function showToast(message, category) {
        const toast = document.createElement('div');
        toast.className = 'toast toast-' + (category || 'info');
        toast.setAttribute('data-toast', '');
        toast.innerHTML = '<span>' + message + '</span>';
        document.body.appendChild(toast);

        setTimeout(function () {
            toast.classList.add('show');
        }, 10);

        setTimeout(function () {
            toast.classList.remove('show');
            setTimeout(function () {
                toast.remove();
            }, 300);
        }, 5000);
    }

    document.getElementById('btn-nova-carteira')?.addEventListener('click', function () {
        openModalCarteira();
    });

    document.getElementById('btn-nova-carteira-empty')?.addEventListener('click', function () {
        openModalCarteira();
    });

    document.getElementById('btn-editar-carteira')?.addEventListener('click', function () {
        openModalCarteira(carteiraId);
    });

    document.querySelectorAll('#btn-novo-ativo').forEach(function (button) {
        button.addEventListener('click', function () {
            openModalAtivo();
        });
    });

    document.querySelectorAll('[data-close-modal]').forEach(function (button) {
        button.addEventListener('click', function () {
            closeModal(button.dataset.closeModal);
        });
    });

    document.getElementById('form-carteira')?.addEventListener('submit', async function (e) {
        e.preventDefault();

        const id = document.getElementById('carteira-id').value;
        const nome = document.getElementById('carteira-nome').value;
        const descricao = document.getElementById('carteira-descricao').value;
        const data = { nome: nome, descricao: descricao };

        if (id) data.id = id;

        try {
            const response = await fetch('/api/carteira/salvar', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            const result = await response.json();

            if (result.success) {
                showToast(result.message, 'success');
                closeModal('modal-carteira');
                setTimeout(function () {
                    location.reload();
                }, 500);
            } else {
                showToast(result.error || 'Erro ao salvar carteira', 'error');
            }
        } catch (err) {
            showToast('Erro ao salvar carteira', 'error');
        }
    });

    document.getElementById('form-ativo')?.addEventListener('submit', async function (e) {
        e.preventDefault();

        if (!carteiraId) {
            showToast('Selecione uma carteira', 'error');
            return;
        }

        const id = document.getElementById('ativo-id').value;
        const ticker = document.getElementById('ativo-ticker').value.toUpperCase();
        const quantidade = parseFloat(document.getElementById('ativo-quantidade').value);
        const precoMedio = parseFloat(document.getElementById('ativo-preco-medio').value);
        const alocacaoIdeal = parseFloat(document.getElementById('ativo-alocacao').value);
        const data = {
            ticker: ticker,
            quantidade: quantidade,
            precoMedio: precoMedio,
            alocacaoIdeal: alocacaoIdeal
        };

        if (id) data.id = id;

        try {
            const response = await fetch('/api/carteira/' + carteiraId + '/ativo/salvar', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            const result = await response.json();

            if (result.success) {
                showToast(result.message, 'success');
                closeModal('modal-ativo');
                setTimeout(function () {
                    location.reload();
                }, 500);
            } else {
                showToast(result.error || 'Erro ao salvar ativo', 'error');
            }
        } catch (err) {
            showToast('Erro ao salvar ativo', 'error');
        }
    });

    document.getElementById('btn-deletar-carteira')?.addEventListener('click', async function () {
        if (!carteiraId) return;
        if (!confirm('Tem certeza que deseja deletar esta carteira? Todos os ativos serão removidos.')) return;

        try {
            const response = await fetch('/api/carteira/' + carteiraId + '/deletar', {
                method: 'POST'
            });
            const result = await response.json();

            if (result.success) {
                showToast(result.message, 'success');
                setTimeout(function () {
                    location.href = carteiraUrl;
                }, 500);
            } else {
                showToast(result.error || 'Erro ao deletar carteira', 'error');
            }
        } catch (err) {
            showToast('Erro ao deletar carteira', 'error');
        }
    });

    document.querySelectorAll('.delete-ativo').forEach(function (button) {
        button.addEventListener('click', async function () {
            const ativoId = button.dataset.id;
            if (!confirm('Remover este ativo?')) return;

            try {
                const response = await fetch('/api/carteira/ativo/' + ativoId + '/deletar', {
                    method: 'POST'
                });
                const result = await response.json();

                if (result.success) {
                    showToast(result.message, 'success');
                    setTimeout(function () {
                        location.reload();
                    }, 500);
                } else {
                    showToast(result.error || 'Erro ao deletar ativo', 'error');
                }
            } catch (err) {
                showToast('Erro ao deletar ativo', 'error');
            }
        });
    });

    document.querySelectorAll('.edit-ativo').forEach(function (button) {
        button.addEventListener('click', function () {
            openModalAtivo(button.dataset.id);
        });
    });

    document.getElementById('btn-atualizar-precos')?.addEventListener('click', async function () {
        if (!carteiraId) return;

        const button = this;
        button.disabled = true;
        button.textContent = 'Atualizando...';

        try {
            const response = await fetch('/api/carteira/' + carteiraId + '/atualizar-precos', {
                method: 'POST'
            });
            const result = await response.json();

            if (result.success || result.atualizados > 0) {
                showToast(result.message, 'success');
                setTimeout(function () {
                    location.reload();
                }, 1000);
            } else {
                showToast(result.message || result.error || 'Erro ao atualizar preços', 'warning');
            }
        } catch (err) {
            showToast('Erro ao atualizar preços', 'error');
        } finally {
            button.disabled = false;
            button.textContent = 'Atualizar Preços';
        }
    });

    document.querySelectorAll('.modal-overlay').forEach(function (overlay) {
        overlay.addEventListener('click', function (e) {
            if (e.target === overlay) closeModal(overlay.id);
        });
    });

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') {
            document.querySelectorAll('.modal-overlay').forEach(function (modal) {
                modal.classList.remove('open');
            });
        }
    });

    document.addEventListener('keydown', function (e) {
        if ((e.ctrlKey || e.metaKey) && e.key === 's') {
            const openModal = document.querySelector('.modal-overlay.open');
            if (!openModal) return;

            e.preventDefault();
            const form = openModal.querySelector('form');
            if (form) form.requestSubmit();
        }
    });
});

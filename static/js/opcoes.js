async function atualizarDados() {
    const btn = document.getElementById('btn-atualizar');
    const status = document.getElementById('status-atualizacao');

    btn.disabled = true;
    btn.textContent = '⏳ Atualizando...';
    status.textContent = 'Buscando dados do OpLab...';
    status.className = 'status-text status-loading';

    try {
        const resp = await fetch('/api/opcoes/atualizar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
        });

        const data = await resp.json();

        if (resp.ok && data.success) {
            status.textContent = `✅ ${data.message}`;
            status.className = 'status-text status-success';
            setTimeout(() => location.reload(), 1500);
        } else {
            status.textContent = `❌ ${data.error || 'Erro ao atualizar'}`;
            status.className = 'status-text status-error';
        }
    } catch (err) {
        status.textContent = `❌ Erro de rede: ${err.message}`;
        status.className = 'status-text status-error';
    } finally {
        btn.disabled = false;
        btn.textContent = '🔄 Atualizar Dados';
    }
}

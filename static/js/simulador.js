const ESTRUTURA_ATIVO = window.ESTRUTURA_ATIVO || '';
const ESTRUTURA_PRECO = window.ESTRUTURA_PRECO || 0;
const ESTRUTURA_DATA_VENC = window.ESTRUTURA_DATA_VENC || '';

// Dados de opções do OpLab (carregados do DB)
let opcoesData = {};
let vencimentos = [];

// Carregar dados de opções do OpLab
function carregarOpcoes() {
    const ativo = ESTRUTURA_ATIVO;
    if (!ativo) return;

    fetch('/api/opcoes/series/' + ativo)
        .then(r => r.json())
        .then(data => {
            if (data.series) {
                opcoesData = data.series;
                preencherVencimentos();
            }
        })
        .catch(function () {
            console.log('Não foi possível carregar opções do OpLab');
            document.getElementById('leg-vencimento-select').innerHTML = '<option value="">Sem dados do OpLab</option>';
        });
}

// Preencher dropdown de vencimentos
function preencherVencimentos() {
    const select = document.getElementById('leg-vencimento-select');
    vencimentos = Object.keys(opcoesData).sort();

    if (vencimentos.length === 0) {
        select.innerHTML = '<option value="">Nenhum vencimento disponível</option>';
        return;
    }

    let html = '<option value="">Selecione o vencimento...</option>';
    vencimentos.forEach(function (venc) {
        const serie = opcoesData[venc];
        const dias = serie.dias_vencimento || 0;
        const dataFormatada = formatarData(venc);
        const selected = ESTRUTURA_DATA_VENC && venc.startsWith(ESTRUTURA_DATA_VENC.substring(0, 7)) ? 'selected' : '';
        html += '<option value="' + venc + '" ' + selected + '>' + dataFormatada + ' (' + dias + 'd)</option>';
    });
    select.innerHTML = html;
}

// Formatar data YYYY-MM-DD para DD/MM/YYYY
function formatarData(dateStr) {
    if (!dateStr) return '';
    const parts = dateStr.split('-');
    if (parts.length === 3) {
        return parts[2] + '/' + parts[1] + '/' + parts[0];
    }
    return dateStr;
}

// Ao selecionar vencimento, carregar strikes
document.addEventListener('DOMContentLoaded', function () {
    const vencSelect = document.getElementById('leg-vencimento-select');
    if (vencSelect) {
        vencSelect.addEventListener('change', function () {
            const venc = this.value;
            const strikeSelect = document.getElementById('leg-strike-select');

            if (!venc || !opcoesData[venc]) {
                strikeSelect.innerHTML = '<option value="">Selecione um vencimento primeiro</option>';
                strikeSelect.disabled = true;
                return;
            }

            const serie = opcoesData[venc];
            const tipoSelecionado = document.getElementById('leg-tipo').value;

            // Filtrar opções pelo tipo
            const opcoes = serie.opcoes.filter(function (opt) {
                return opt.tipo.toLowerCase() === tipoSelecionado.toLowerCase();
            });

            // Ordenar por strike
            opcoes.sort(function (a, b) { return a.strike - b.strike; });

            let html = '<option value="">Selecione o strike...</option>';
            opcoes.forEach(function (opt) {
                const moneyness = opt.moneyness || '';
                const vi = opt.vi ? opt.vi.toFixed(1) + '%' : '';
                const ask = opt.ask ? 'R$ ' + opt.ask.toFixed(4) : '';
                html += '<option value="' + opt.strike + '" data-ticker="' + opt.simbolo + '" data-iv="' + (opt.vi || '') + '" data-delta="' + (opt.delta || '') + '" data-moneyness="' + moneyness + '" data-bid="' + (opt.bid || '') + '" data-ask="' + (opt.ask || '') + '">' +
                    'R$ ' + opt.strike.toFixed(2) + ' ' + moneyness + (vi ? ' | IV: ' + vi : '') + '</option>';
            });
            strikeSelect.innerHTML = html;
            strikeSelect.disabled = false;
        });
    }

    // Ao selecionar strike, preencher info e calcular gregas
    const strikeSelect = document.getElementById('leg-strike-select');
    if (strikeSelect) {
        strikeSelect.addEventListener('change', function () {
            const option = this.options[this.selectedIndex];
            if (!option.value) {
                document.getElementById('opcao-info').style.display = 'none';
                return;
            }

            const ticker = option.dataset.ticker;
            const iv = parseFloat(option.dataset.iv) || 0;
            const delta = parseFloat(option.dataset.delta) || 0;
            const moneyness = option.dataset.moneyness;
            const bid = parseFloat(option.dataset.bid) || 0;
            const ask = parseFloat(option.dataset.ask) || 0;
            const strike = parseFloat(option.value);

            // Preencher campos hidden
            document.getElementById('leg-strike-hidden').value = strike;
            document.getElementById('leg-vencimento-hidden').value = document.getElementById('leg-vencimento-select').value;
            document.getElementById('leg-ticker-hidden').value = ticker;

            // Sugerir prêmio (ask)
            if (ask > 0 && !document.getElementById('leg-premio').value) {
                document.getElementById('leg-premio').value = ask.toFixed(4);
            }

            // Mostrar info da opção
            document.getElementById('opt-simbolo').textContent = ticker;
            document.getElementById('opt-iv').textContent = iv ? iv.toFixed(1) + '%' : '—';
            document.getElementById('opt-delta').textContent = delta ? delta.toFixed(4) : '—';
            document.getElementById('opt-moneyness').textContent = moneyness || '—';
            document.getElementById('opt-bid').textContent = bid ? 'R$ ' + bid.toFixed(4) : '—';
            document.getElementById('opt-ask').textContent = ask ? 'R$ ' + ask.toFixed(4) : '—';
            document.getElementById('opcao-info').style.display = 'block';

            // Calcular gregas se temos IV
            if (iv > 0) {
                calcularGregas(strike, iv);
            }
        });
    }

    // Recalcular gregas quando mudar tipo
    const tipoSelect = document.getElementById('leg-tipo');
    if (tipoSelect) {
        tipoSelect.addEventListener('change', function () {
            const strikeSelect = document.getElementById('leg-strike-select');
            if (strikeSelect.value) {
                strikeSelect.dispatchEvent(new Event('change'));
            }
        });
    }

    // Calcular gregas quando mudar prêmio manualmente
    const premioInput = document.getElementById('leg-premio');
    if (premioInput) {
        premioInput.addEventListener('blur', function () {
            const premio = parseFloat(this.value) || 0;
            const strike = parseFloat(document.getElementById('leg-strike-hidden').value) || 0;
            const S0 = parseFloat(ESTRUTURA_PRECO) || 0;
            const tipo = document.getElementById('leg-tipo').value;
            const venc = document.getElementById('leg-vencimento-select').value;

            // Se tem vencimento, tentar calcular IV implícita
            if (premio > 0 && strike > 0 && S0 > 0 && venc) {
                // Usar API para calcular IV implícita
                fetch('/api/calcular-iv', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ preco_atual: S0, strike: strike, premio: premio, tipo: tipo, venc: venc })
                }).then(r => r.json()).then(d => {
                    if (d.iv) {
                        document.getElementById('leg-iv').value = Number(d.iv).toFixed(1);
                        document.getElementById('leg-delta').value = Number(d.delta || 0).toFixed(4);
                        document.getElementById('leg-gamma').value = Number(d.gamma || 0).toFixed(6);
                        document.getElementById('leg-theta').value = Number(d.theta || 0).toFixed(6);
                        document.getElementById('leg-vega').value = Number(d.vega || 0).toFixed(6);
                    }
                }).catch(function () { });
            }
        });
    }

    // Carregar opções ao abrir modal
    if (document.getElementById('modal-leg')) {
        carregarOpcoes();
    }
});

// Calcular gregas via API
function calcularGregas(strike, iv) {
    const S0 = parseFloat(ESTRUTURA_PRECO) || 0;
    const tipo = document.getElementById('leg-tipo').value;
    const venc = document.getElementById('leg-vencimento-select').value;

    if (!S0 || !strike || !iv || !venc) return;

    fetch('/preview_greeks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ preco_atual: S0, strike: strike, iv: iv, tipo: tipo, venc: venc })
    }).then(r => r.json()).then(d => {
        if (d.delta == null) return;
        document.getElementById('leg-delta').value = Number(d.delta).toFixed(4);
        document.getElementById('leg-gamma').value = Number(d.gamma).toFixed(6);
        document.getElementById('leg-theta').value = Number(d.theta).toFixed(6);
        document.getElementById('leg-vega').value = Number(d.vega).toFixed(6);
        document.getElementById('leg-iv').value = iv.toFixed(1);
    }).catch(function () { });
}

// Função para atualizar preços via AJAX
function atualizarPrecos(eid) {
    const btn = document.getElementById('btn-atualizar-precos');
    if (!btn || btn.classList.contains('loading')) return;

    btn.classList.add('loading');
    btn.textContent = 'Atualizando...';

    fetch('/api/estrutura/' + eid + '/atualizar-precos', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    })
        .then(r => r.json())
        .then(dados => {
            btn.classList.remove('loading');

            if (dados.error) {
                alert('Erro: ' + dados.error);
                return;
            }

            let msg = 'Atualização concluída!\n\n';
            msg += 'Ativo: ' + (dados.ativo_atualizado ? '✓ Atualizado' : '✗ Falha');
            if (dados.preco_ativo) msg += ' (R$ ' + dados.preco_ativo.toFixed(2) + ')';
            msg += '\n';
            msg += 'Opções: ' + dados.opcoes_atualizadas + ' atualizada(s)';

            if (dados.erros && dados.erros.length > 0) {
                msg += '\n\nErros:\n' + dados.erros.join('\n');
            }

            alert(msg);

            if (dados.ativo_atualizado || dados.opcoes_atualizadas > 0) {
                window.location.reload();
            }
        })
        .catch(err => {
            btn.classList.remove('loading');
            alert('Erro ao atualizar preços. Tente novamente.');
            console.error('Erro:', err);
        });
}

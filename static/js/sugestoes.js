async function analisar() {
    const ticker = document.getElementById('ticker-input').value.trim().toUpperCase();
    const estrategia = document.getElementById('estrategia-select').value;
    const diasMin = parseInt(document.getElementById('dias-min').value) || 5;
    const diasMax = parseInt(document.getElementById('dias-max').value) || 180;
    const btn = document.getElementById('btn-analisar');
    const status = document.getElementById('status-msg');
    const loadingArea = document.getElementById('loading-area');
    const resultadoArea = document.getElementById('resultado-area');

    if (!ticker) {
        status.textContent = 'Informe o ticker do ativo.';
        status.className = 'status-text status-erro';
        return;
    }

    btn.disabled = true;
    btn.textContent = 'Analisando...';
    status.textContent = '';
    loadingArea.style.display = 'block';
    resultadoArea.style.display = 'none';

    try {
        const body = { ticker: ticker, estrategia: estrategia, dias_min: diasMin, dias_max: diasMax };

        const resp = await fetch('/api/sugestoes', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });

        const data = await resp.json();

        if (!resp.ok) {
            throw new Error(data.error || 'Erro ao analisar');
        }

        renderizarResultado(data);

    } catch (err) {
        status.textContent = err.message;
        status.className = 'status-text status-erro';
        loadingArea.style.display = 'none';
    } finally {
        btn.disabled = false;
        btn.textContent = 'Analisar';
    }
}

function renderizarResultado(data) {
    const loadingArea = document.getElementById('loading-area');
    const resultadoArea = document.getElementById('resultado-area');
    loadingArea.style.display = 'none';
    resultadoArea.style.display = 'block';

    // Cenário e IV (novo formato ANALISE.md)
    const cenario = data.cenario || {};
    const ivNivel = data.iv_nivel || 'N/A';
    const cenarioMap = {
        'TOPO': { nome: 'Esticado no Topo', badge: 'badge-DOWN' },
        'FUNDO': { nome: 'Suporte / Fundo', badge: 'badge-UP' },
        'LATERAL': { nome: 'Lateral (Consolidacao)', badge: 'badge-SIDEWAYS' },
    };
    const cenarioInfo = cenarioMap[cenario.cenario] || { nome: cenario.cenario || 'N/A', badge: '' };
    const ivBadge = ivNivel === 'Alta' ? 'badge-DOWN' : ivNivel === 'Baixa' ? 'badge-UP' : '';

    const cenarioHtml = '<div class="indicadores-grid">' +
        '<div class="indicador-item"><span class="indicador-label">Cenario</span><span class="tendencia-badge ' + cenarioInfo.badge + '">' + cenarioInfo.nome + '</span></div>' +
        '<div class="indicador-item"><span class="indicador-label">Nivel IV</span><span class="tendencia-badge ' + ivBadge + '">' + ivNivel + '</span></div>' +
        '<div class="indicador-item"><span class="indicador-label">Dist. EMA21</span><span class="indicador-value">' + (cenario.distancia_ema21_pct || '-') + '%</span></div>' +
        '<div class="indicador-item"><span class="indicador-label">RSI Sobrecomprado</span><span class="indicador-value">' + (cenario.rsi_sobrecomprado ? 'Sim' : 'Nao') + '</span></div>' +
        '<div class="indicador-item"><span class="indicador-label">RSI Sobrevendido</span><span class="indicador-value">' + (cenario.rsi_sobrevendido ? 'Sim' : 'Nao') + '</span></div>' +
        '<div class="indicador-item"><span class="indicador-label">BB Squeeze</span><span class="indicador-value">' + (cenario.bb_squeeze ? 'Sim' : 'Nao') + '</span></div>' +
        '</div>' +
        '<div class="observacoes-box" style="margin-top:0.75rem">' + (cenario.justificativa || '') + '</div>';
    document.getElementById('indicadores-content').innerHTML = cenarioHtml;

    // Indicadores tecnicos
    const ind = data.analise_tecnica?.indicadores || {};
    if (ind.price) {
        const indHtml = '<div class="indicadores-grid">' +
            '<div class="indicador-item"><span class="indicador-label">Preco</span><span class="indicador-value">R$ ' + ind.price + '</span></div>' +
            '<div class="indicador-item"><span class="indicador-label">EMA 9</span><span class="indicador-value">' + (ind.ema9 || '-') + '</span></div>' +
            '<div class="indicador-item"><span class="indicador-label">EMA 21</span><span class="indicador-value">' + (ind.ema21 || '-') + '</span></div>' +
            '<div class="indicador-item"><span class="indicador-label">EMA 200</span><span class="indicador-value">' + (ind.ema200 || '-') + '</span></div>' +
            '<div class="indicador-item"><span class="indicador-label">RSI</span><span class="indicador-value">' + (ind.rsi || '-') + '</span></div>' +
            '<div class="indicador-item"><span class="indicador-label">ADX</span><span class="indicador-value">' + (ind.adx || '-') + '</span></div>' +
            '<div class="indicador-item"><span class="indicador-label">MACD</span><span class="indicador-value">' + (ind.macd || '-') + '</span></div>' +
            '<div class="indicador-item"><span class="indicador-label">MACD Signal</span><span class="indicador-value">' + (ind.macd_signal || '-') + '</span></div>' +
            '<div class="indicador-item"><span class="indicador-label">BB Upper</span><span class="indicador-value">' + (ind.bb_upper || '-') + '</span></div>' +
            '<div class="indicador-item"><span class="indicador-label">BB Lower</span><span class="indicador-value">' + (ind.bb_lower || '-') + '</span></div>' +
            '<div class="indicador-item"><span class="indicador-label">BB Width</span><span class="indicador-value">' + (ind.bb_width || '-') + '</span></div>' +
            (ind.vi_media ? '<div class="indicador-item"><span class="indicador-label">VI Media</span><span class="indicador-value">' + ind.vi_media + '%</span></div>' : '') +
            '</div>';
        document.getElementById('tendencia-content').innerHTML = indHtml;
    }

    // Status
    const apdo = data.estrategia_sugerida !== 'Aguardar melhor oportunidade';
    let statusHtml = '';
    if (apdo) {
        statusHtml = '<div class="observacoes-box status-sucesso">' +
            'Estrategia sugerida: <b>' + data.estrategia_sugerida + '</b><br>' +
            (data.observacoes || 'Estrategia recomendada.') +
            '</div>';
    } else {
        statusHtml = '<div class="nao-apto-box status-info">' +
            '<strong>Nao recomendado operar no momento.</strong><br>' +
            (data.observacoes || 'Aguardar melhor oportunidade.') +
            '</div>';
    }
    document.getElementById('status-content').innerHTML = statusHtml;

    // Sugestoes
    const sugestoes = data.sugestoes || [];
    const sugestoesCard = document.getElementById('sugestoes-card');

    if (sugestoes.length === 0) {
        sugestoesCard.style.display = 'none';
    } else {
        sugestoesCard.style.display = 'block';
        let sugestoesHtml = '';

        for (const sug of sugestoes) {
            const score = sug.score || 0;
            const scoreClass = score >= 60 ? 'score-high' : score >= 30 ? 'score-medium' : 'score-low';

            sugestoesHtml += '<div class="sugestao-card">' +
                '<div class="sugestao-header">' +
                '<span class="sugestao-tipo">' + (sug.tipo || 'Estrategia') + '</span>' +
                '<span class="sugestao-score ' + scoreClass + '">Score: ' + score + '</span>' +
                '</div>';

            // Pernas (para spreads)
            if (sug.perna_compra || sug.perna_venda) {
                sugestoesHtml += '<div class="sugestao-pernas">';

                if (sug.perna_compra) {
                    sugestoesHtml += '<div class="perna-box">' +
                        '<div class="perna-label">Compra</div>' +
                        '<div class="perna-simbolo">' + (sug.perna_compra.simbolo || 'N/A') + '</div>' +
                        '<div class="perna-detalhes">' +
                        'Strike: <b>' + (sug.perna_compra.strike || 0).toFixed(2) + '</b> | ' +
                        'Premio: R$ ' + (sug.perna_compra.premio || 0).toFixed(2) +
                        '</div>' +
                        '<div class="perna-detalhes">' +
                        'VI: ' + (sug.perna_compra.vi || 0).toFixed(1) + '% | ' +
                        'Moneyness: ' + (sug.perna_compra.moneyness || 'N/A') +
                        '</div>' +
                        '</div>';
                }

                if (sug.perna_venda) {
                    sugestoesHtml += '<div class="perna-box">' +
                        '<div class="perna-label">Venda</div>' +
                        '<div class="perna-simbolo">' + (sug.perna_venda.simbolo || 'N/A') + '</div>' +
                        '<div class="perna-detalhes">' +
                        'Strike: <b>' + (sug.perna_venda.strike || 0).toFixed(2) + '</b> | ' +
                        'Premio: R$ ' + (sug.perna_venda.premio || 0).toFixed(2) +
                        '</div>' +
                        '<div class="perna-detalhes">' +
                        'VI: ' + (sug.perna_venda.vi || 0).toFixed(1) + '% | ' +
                        'Moneyness: ' + (sug.perna_venda.moneyness || 'N/A') +
                        '</div>' +
                        '</div>';
                }

                sugestoesHtml += '</div>';
            } else if (sug.simbolo) {
                sugestoesHtml += '<div style="background: var(--bg4); padding: 0.5rem; border-radius: 4px; margin-bottom: 0.75rem;">' +
                    '<div class="perna-simbolo">' + sug.simbolo + '</div>' +
                    '<div class="perna-detalhes">' +
                    'Strike: <b>' + (sug.strike || 0).toFixed(2) + '</b> | ' +
                    'Premio: R$ ' + (sug.premio || 0).toFixed(2) + ' | ' +
                    'VI: ' + (sug.vi || 0).toFixed(1) + '%' +
                    '</div>' +
                    '</div>';
            }

            // Metricas
            sugestoesHtml += '<div class="sugestao-metricas">';

            if (sug.debito !== undefined) {
                sugestoesHtml += '<div class="metrica-item">' +
                    '<span class="metrica-label">Debito</span>' +
                    '<span class="metrica-valor negativo">R$ ' + sug.debito.toFixed(2) + '</span>' +
                    '</div>';
            }
            if (sug.credito !== undefined) {
                sugestoesHtml += '<div class="metrica-item">' +
                    '<span class="metrica-label">Credito</span>' +
                    '<span class="metrica-valor positivo">R$ ' + sug.credito.toFixed(2) + '</span>' +
                    '</div>';
            }
            if (sug.lucro_max !== undefined) {
                sugestoesHtml += '<div class="metrica-item">' +
                    '<span class="metrica-label">Lucro Max.</span>' +
                    '<span class="metrica-valor positivo">R$ ' + sug.lucro_max.toFixed(2) + '</span>' +
                    '</div>';
            }
            if (sug.perda_max !== undefined) {
                sugestoesHtml += '<div class="metrica-item">' +
                    '<span class="metrica-label">Perda Max.</span>' +
                    '<span class="metrica-valor negativo">R$ ' + sug.perda_max.toFixed(2) + '</span>' +
                    '</div>';
            }
            if (sug.break_even !== undefined) {
                sugestoesHtml += '<div class="metrica-item">' +
                    '<span class="metrica-label">Break-Even</span>' +
                    '<span class="metrica-valor">R$ ' + sug.break_even.toFixed(2) + '</span>' +
                    '</div>';
            }
            if (sug.retorno_pct !== undefined) {
                sugestoesHtml += '<div class="metrica-item">' +
                    '<span class="metrica-label">Retorno/Risco</span>' +
                    '<span class="metrica-valor ' + (sug.retorno_pct > 100 ? 'positivo' : '') + '">' + sug.retorno_pct.toFixed(0) + '%</span>' +
                    '</div>';
            }
            if (sug.dias_vencimento !== undefined) {
                sugestoesHtml += '<div class="metrica-item">' +
                    '<span class="metrica-label">Dias ate Venc.</span>' +
                    '<span class="metrica-valor">' + sug.dias_vencimento + '</span>' +
                    '</div>';
            }
            if (sug.poe !== undefined) {
                sugestoesHtml += '<div class="metrica-item">' +
                    '<span class="metrica-label">Prob. ITM</span>' +
                    '<span class="metrica-valor">' + sug.poe.toFixed(1) + '%</span>' +
                    '</div>';
            }

            sugestoesHtml += '</div></div>';
        }

        document.getElementById('sugestoes-content').innerHTML = sugestoesHtml;
    }
}

// Input uppercase
document.getElementById('ticker-input').addEventListener('input', function () {
    this.value = this.value.toUpperCase().replace(/[^A-Z0-9]/g, '');
});

// Enter key
document.querySelectorAll('.sugestoes-controls input').forEach(function (el) {
    el.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
            analisar();
        }
    });
});

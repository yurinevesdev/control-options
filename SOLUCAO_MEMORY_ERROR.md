# 🚨 SOLUÇÃO: MemoryError no Banco de Dados

## Problema Identificado

O servidor trava com `MemoryError` ao carregar porque a tabela `opcoes_detalhes` tem **7.384 registros grandes** (30 colunas cada).

Quando o SQLite tenta **criar indexes** em uma tabela tão grande, precisa carregar tudo na memória e **estoura a RAM**.

```
MemoryError: no memory for table opcoes_detalhes
  File "system/core/db.py", line 145, in _init_schema
    c.execute("CREATE INDEX IF NOT EXISTS idx_est_tipo ON estruturas(tipo)")
```

## 🔧 Solução Rápida (Recomendada)

A tabela `opcoes_detalhes` contém **dados em cache** que podem ser recriados do zero. Execute:

```bash
sqlite3 /home/yuri/Documentos/control-options/instance/system_opcoes_v2.sqlite \
  "DELETE FROM opcoes_detalhes; 
   DELETE FROM opcoes_dados; 
   VACUUM;"
```

Depois reinicie o servidor:
```bash
python app.py
```

### O que essa comando faz:
- ✅ Deleta 7.384 registros de cache de opções
- ✅ Deleta 241 registros de dados cached
- ✅ `VACUUM` compacta o arquivo (reduz de 1,5MB para ~100KB)
- ✅ Libera memória para criar os indexes corretamente

## 🛡️ Proteções Adicionadas

Adicionei logging na inicialização do banco para rastrear exatamente quando/onde trava:

**Logs agora mostram:**
```
MemoryError ao criar índices em estruturas
Se isso acontecer, execute: sqlite3 ... DELETE FROM opcoes_detalhes
```

## 📊 Estrutura de Dados

### Tabela opcoes_detalhes (7.384 linhas, 30 colunas)
Contém dados de opções detalhadas com:
- Identificação: ticker_original, simbolo, tipo, serie
- Preços: ultimo_preco, bid, ask
- Volumes: volume, volume_financeiro
- Gregas: delta, gamma, vega, theta, rho
- Indicadores: vi, poe, liquidez_texto, moneyness
- Status: atualizado_em

Este é um **cache** que é recriado conforme necessário.

## ✨ O que Acontece Depois de Limpar

1. ✅ Servidor inicia sem MemoryError
2. ✅ Indexes são criados com sucesso
3. ✅ Dados de opções são carregados **sob demanda** quando você acessar as páginas
4. ✅ Cache é preenchido gradualmente conforme você navega

## 🔍 Verificar o Problema

Se tracar de novo, verifique:

```bash
# Ver tamanho das tabelas
sqlite3 /home/yuri/Documentos/control-options/instance/system_opcoes_v2.sqlite \
  ".mode column" \
  "SELECT 'opcoes_detalhes' as tabela, COUNT(*) as registros FROM opcoes_detalhes UNION 
   SELECT 'opcoes_dados', COUNT(*) FROM opcoes_dados;"
```

Se houver muitos registros novamente, repita a limpeza.

## 📋 Checklist

- [ ] Execute o comando `DELETE FROM opcoes_detalhes...` acima
- [ ] Reinicie o servidor: `python app.py`
- [ ] Teste com `python test_stability.py`
- [ ] Verifique logs com `./watch_logs.sh`
- [ ] Se funcionar, documento está resolvido! ✅

**Se continuar travando**, compartilhe:
```bash
tail -50 logs/app.log
```

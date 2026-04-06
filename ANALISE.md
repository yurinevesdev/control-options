# 📈 Sistema de Apoio à Decisão: Estruturas de Opções

## 1. Objetivo do Sistema
Classificar o cenário do ativo subjacente (Topo, Fundo ou Lateral) através de indicadores técnicos e cruzar com a **Volatilidade Implícita (IV)** para sugerir a estrutura de opções com a maior vantagem estatística (*Edge*).

---

## 2. Parâmetros de Entrada (Indicadores)

| Indicador | Função Técnica | Gatilhos de Alerta |
| :--- | :--- | :--- |
| **RSI (14)** | Identifica exaustão ou sobrevenda | > 70 (Sobrecomprado) / < 30 (Sobrevendido) |
| **EMA 9 & 21** | Mede o afastamento do preço médio | Preço > 5% da EMA 21 (Esticado) |
| **B. Bollinger** | Mede desvios padrões e volatilidade | Preço toca/rompe bandas; BB Width (Squeeze) |
| **ADX (14)** | Filtro de força de tendência | < 20 (Lateral) / > 30 (Tendência Forte) |
| **IV Rank** | Define o custo do prêmio | > 50% (Venda de Vol) / < 30% (Compra de Vol) |

---

## 3. Matriz de Classificação de Cenário

O sistema deve processar os indicadores em confluência para definir o estado atual:

* **ESTADO: ESTICADO (TOPO)**
    * *Gatilhos:* Preço ≥ Banda Superior **AND** RSI > 70 **AND** Afastamento significativo da EMA 21.
    * *Nota:* Se ADX > 35, alertar para "Tendência de Exaustão de Alta".

* **ESTADO: SUPORTE (FUNDO)**
    * *Gatilhos:* Preço ≤ Banda Inferior **AND** RSI < 30 **AND** Preço abaixo da EMA 21.
    * *Nota:* Se ADX > 35, alertar para "Tendência de Queda Acelerada".

* **ESTADO: LATERAL (CONSOLIDAÇÃO)**
    * *Gatilhos:* ADX < 20 **AND** Preço oscilando entre as Bandas de Bollinger.
    * *Nota:* Monitorar BB Width. Se estiver em mínimas, aguardar rompimento.

---

## 4. Regras de Decisão (Cenário + IV)

### 🔴 Cenário: Esticado no Topo (Expectativa de Queda/Correção)
* **IV ALTA:** * **Estratégia:** `Bear Call Spread` (Trava de Baixa com Call)
    * **Justificativa:** Vende-se prêmios caros; lucra com a queda do ativo e com o *IV Crush*.
* **IV BAIXA:** * **Estratégia:** `Compra de PUT` (ou Put Spread)
    * **Justificativa:** Opções baratas (Vega Positivo); lucra com a queda e com o aumento do medo (IV).

### 🟢 Cenário: Suporte / Fundo (Expectativa de Repique/Alta)
* **IV ALTA:** * **Estratégia:** `Venda de PUT` (ou Credit Put Spread)
    * **Justificativa:** Recebe prêmio elevado; alta margem de segurança e ganho na retração da IV.
* **IV BAIXA:** * **Estratégia:** `Compra de CALL` (ou Call Spread)
    * **Justificativa:** Baixo custo de entrada e risco limitado para capturar retomada.

### 🟡 Cenário: Lateral (ADX Baixo)
* **IV ALTA:** * **Estratégia:** `Iron Condor`
    * **Justificativa:** Venda de volatilidade em ambos os lados; lucro máximo com a passagem do tempo (Theta).
* **IV BAIXA:** * **Estratégia:** `Trava de Linha` (Calendário)
    * **Justificativa:** Beneficia-se da baixa IV esperando expansão futura; ganho no diferencial de Theta.

---

## 5. Filtros de Segurança e Gerenciamento
1.  **Filtro Anti-Squeeze:** Não sugerir estratégias de venda de volatilidade se o *BB Width* estiver em níveis mínimos históricos (risco de explosão).
2.  **Proteção de Tendência:** Se ADX > 35, priorizar estruturas de **DÉBITO**, pois o preço pode ignorar o RSI e continuar a tendência.
3.  **Probabilidade (POP):** Para estratégias de crédito (Venda), buscar Strikes com **Delta entre 0.15 e 0.30**.

---
> **Nota de Implementação:** Este arquivo serve como a base lógica para o processamento do motor de decisão do sistema de análise de investimentos.
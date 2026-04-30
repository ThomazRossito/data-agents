---
domain: industry
industry: financial-services
updated_at: 2026-04-30
agents: [catalog-intelligence, business-analyst, governance-auditor, data-quality-steward]
---

# Financial Services — Knowledge Base de Indústria

Referência de casos de uso, schemas típicos, KPIs e contexto regulatório para times de dados
atuando em bancos, fintechs, seguradoras, gestoras de ativos e corretoras.

---

## Casos de Uso de Dados por Objetivo

### Risco e Crédito

| Caso de Uso | Descrição | Domínios de Dados | Agentes |
|-------------|-----------|-------------------|---------|
| Credit Scoring em tempo real | Modelo ML que avalia risco de crédito em milissegundos na aprovação de empréstimos | `customers`, `credit_history`, `transactions`, `bureau_data` | spark-expert, sql-expert |
| Detecção de Fraude Transacional | Identificar padrões anômalos em transações via ML ou regras | `transactions`, `devices`, `ip_geolocation`, `fraud_labels` | spark-expert, data-quality-steward |
| Stress Testing de Carteira | Simulação de cenários macroeconômicos no portfólio de crédito | `portfolio`, `market_data`, `economic_scenarios` | sql-expert |
| Provisioning IFRS 9 / PCLD | Cálculo de Perda Esperada (ECL) por estágio de inadimplência | `contracts`, `payments`, `collateral`, `rating_history` | spark-expert |

### Compliance e Regulatório

| Caso de Uso | Descrição | Domínios de Dados | Regulação |
|-------------|-----------|-------------------|-----------|
| Anti-Money Laundering (AML) | Identificar padrões de lavagem via grafos de transação | `transactions`, `accounts`, `beneficial_owners` | COAF, FATF |
| Know Your Customer (KYC) | Onboarding com validação de identidade e sanções | `customers`, `documents`, `pep_lists`, `sanctions` | Banco Central, CVM |
| Relatório BACEN / COSIF | Geração automática de arquivos regulatórios mensais | `accounting`, `positions`, `portfolio` | BACEN 4.557 |
| LGPD na Área Financeira | Mapeamento de PII, consentimento e direito ao esquecimento | `customers`, `consents`, `audit_trail` | LGPD, GDPR |

### Analytics e Negócio

| Caso de Uso | Descrição | KPIs Gerados |
|-------------|-----------|--------------|
| Churn de Clientes | Predição de saída de conta corrente / cancelamento de cartão | Churn Rate, LTV, NPS por segmento |
| Next Best Offer (NBO) | Recomendação de produto financeiro por perfil | Conversão, Uptake Rate, Revenue per Customer |
| LTV de Cliente | Valor vitalício do cliente por segmento e produto | LTV, CAC, ROI por canal |
| Dashboard Executivo Financeiro | P&L, NII, inadimplência, crescimento de carteira | NII, NIM, ROE, ROAA, Inadimplência 90+ |

---

## Schemas Típicos (Reference Architecture)

### Core Banking

```sql
-- Clientes
CREATE TABLE gold.dim_customers (
  customer_id       STRING NOT NULL,
  cpf_hash          STRING,           -- NUNCA CPF em claro — sempre hash SHA-256
  name_masked       STRING,           -- primeiros 3 chars + *** + sobrenome
  segment           STRING,           -- VAREJO | ALTA_RENDA | CORPORATE | PJ
  risk_tier         STRING,           -- A | B | C | D | E | F
  onboarding_date   DATE,
  status            STRING,           -- ACTIVE | BLOCKED | CLOSED
  PRIMARY KEY (customer_id)
);

-- Contratos de crédito
CREATE TABLE gold.fct_contracts (
  contract_id       STRING NOT NULL,
  customer_id       STRING NOT NULL,
  product_type      STRING,           -- CREDIT_CARD | PERSONAL_LOAN | MORTGAGE | AUTO
  original_amount   DECIMAL(18,2),
  outstanding_balance DECIMAL(18,2),
  interest_rate     DECIMAL(8,6),
  maturity_date     DATE,
  days_past_due     INT,              -- DPD — dias em atraso
  stage_ifrs9       INT,              -- 1 | 2 | 3 (IFRS 9 staging)
  ecl_amount        DECIMAL(18,2),    -- Expected Credit Loss provisionado
  origination_date  DATE,
  PRIMARY KEY (contract_id)
);

-- Transações financeiras
CREATE TABLE silver.fct_transactions (
  transaction_id    STRING NOT NULL,
  account_id        STRING NOT NULL,
  customer_id       STRING NOT NULL,
  transaction_ts    TIMESTAMP NOT NULL,
  amount            DECIMAL(18,2),
  transaction_type  STRING,           -- DEBIT | CREDIT | PIX | TED | DOC | BOLETO
  channel           STRING,           -- APP | WEB | ATM | BRANCH | POS
  merchant_id       STRING,
  merchant_category STRING,           -- MCC code
  is_fraud          BOOLEAN,
  fraud_score       DECIMAL(5,4),     -- 0.0000 a 1.0000
  PRIMARY KEY (transaction_id)
)
PARTITIONED BY (DATE(transaction_ts));
```

### Mercado de Capitais

```sql
-- Posições de carteira
CREATE TABLE gold.fct_portfolio_positions (
  position_id       STRING NOT NULL,
  portfolio_id      STRING NOT NULL,
  asset_id          STRING NOT NULL,
  position_date     DATE NOT NULL,
  quantity          DECIMAL(18,6),
  avg_cost          DECIMAL(18,6),
  market_value      DECIMAL(18,2),
  pnl_unrealized    DECIMAL(18,2),
  asset_class       STRING,           -- EQUITY | FIXED_INCOME | FX | DERIVATIVES
  PRIMARY KEY (position_id)
)
PARTITIONED BY (position_date);
```

---

## KPIs de Referência

| KPI | Fórmula / Definição | Threshold Típico |
|-----|---------------------|-----------------|
| **NIM** (Net Interest Margin) | (Receita Juros − Custo Captação) / Ativos Rentáveis | Bancos BR: 7–12% |
| **ROE** | Lucro Líquido / Patrimônio Líquido Médio | Mínimo saudável: > 12% |
| **Inadimplência 90+** | Contratos com DPD ≥ 90 / Carteira Total | Alerta: > 5% |
| **LTV** | Receita Total do Cliente / Custo de Aquisição (CAC) | Meta: LTV/CAC > 3x |
| **Churn Rate Mensal** | Clientes Encerrados no Mês / Base Início do Mês | Alerta: > 2% |
| **Fraud Loss Rate** | Perdas com Fraude / Volume Transacionado | Alerta: > 0.1% |
| **Coverage Ratio (PCLD)** | Provisão Acumulada / Carteira 90+ | Mínimo regulatório: 100% |
| **Cost-to-Income** | Despesas Operacionais / Receita Total | Meta: < 50% |

---

## Regras de Qualidade de Dados Críticas

```sql
-- CPF/CNPJ nunca em claro em tabelas Silver/Gold
-- Verificar ausência de PII exposta
SELECT COUNT(*) as pii_exposed
FROM information_schema.columns
WHERE table_schema IN ('silver', 'gold')
  AND (
    column_name ILIKE '%cpf%'
    OR column_name ILIKE '%ssn%'
    OR column_name ILIKE '%cnpj%'
  )
  AND column_name NOT ILIKE '%hash%'
  AND column_name NOT ILIKE '%mask%';
-- Esperado: 0

-- Consistência de saldo: soma de transações deve bater com saldo da conta
-- Chave de reconciliação financeira
SELECT
  account_id,
  ABS(SUM(CASE WHEN transaction_type = 'CREDIT' THEN amount ELSE -amount END)
    - MAX(current_balance)) AS reconciliation_gap
FROM silver.fct_transactions t
JOIN silver.dim_accounts a USING (account_id)
WHERE transaction_date = current_date() - 1
GROUP BY account_id
HAVING ABS(reconciliation_gap) > 0.01;  -- tolerância: 1 centavo
```

---

## Contexto Regulatório Relevante

| Regulação | Órgão | Impacto em Dados |
|-----------|-------|-----------------|
| **LGPD** | ANPD | PII deve ser mascarada em ambientes não-produção, consentimento rastreável |
| **Bacen 4.557** | BACEN | Gestão de riscos: crédito, mercado, liquidez, operacional — dados por 5 anos |
| **IFRS 9** | IASB | Staging de contratos em 3 estágios + ECL por contrato — calcular mensalmente |
| **CVM 175** | CVM | Fundos: cota diária, carteira consolidada, stress testing trimestral |
| **COAF** | MJ | Operações suspeitas > R$50k em espécie → comunicação automática |
| **Open Finance** | BACEN | APIs de compartilhamento de dados — consentimento + auditoria |
| **PCI-DSS** | PCI SSC | Dados de cartão: tokenização obrigatória, sem PAN em logs |

---

## Anti-Padrões Específicos de Financial Services

| ID | Anti-padrão | Risco |
|----|-------------|-------|
| FS01 | CPF, CNPJ ou número de conta em claro em tabela Silver/Gold | CRITICAL — violação LGPD + BACEN |
| FS02 | Saldo calculado por agregação de transações sem reconciliação | HIGH — inconsistência financeira |
| FS03 | Staging IFRS 9 calculado sem histórico de DPD de 12 meses | HIGH — provisão incorreta |
| FS04 | Transações duplicadas sem controle de idempotência | HIGH — double-counting de receita |
| FS05 | Dados de mercado sem timestamp de validade (stale market data) | HIGH — VaR incorreto |
| FS06 | Relatório regulatório gerado sem validação de totalização | CRITICAL — risco regulatório |

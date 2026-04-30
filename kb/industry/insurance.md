---
domain: industry
industry: insurance
updated_at: 2026-04-30
agents: [catalog-intelligence, business-analyst, governance-auditor, data-quality-steward]
---

# Insurance (Seguros) — Knowledge Base de Indústria

Referência de casos de uso, schemas típicos, KPIs e conformidade para times de dados
atuando em seguradoras (vida, auto, patrimonial, saúde, agrícola), resseguradoras,
corretoras e plataformas insurtech.

---

## Casos de Uso de Dados por Objetivo

### Pricing e Subscrição

| Caso de Uso | Descrição | Domínios de Dados |
|-------------|-----------|-------------------|
| Precificação de Risco (GLM/ML) | Modelagem de frequência e severidade de sinistros para pricing de apólices | `policies`, `claims`, `insured_profiles`, `exposure_data`, `external_enrichment` |
| Score de Subscrição | Avaliação automática de risco na emissão de apólice (aceitar / recusar / subpreço) | `insured_profiles`, `claims_history`, `credit_bureau`, `telematics` |
| Telemática (Auto) | Precificação baseada em comportamento de direção (UBI — Usage-Based Insurance) | `telematics_events`, `trips`, `driver_scores`, `dim_vehicles` |
| Seguro Agrícola (PROAGRO) | Avaliação de sinistro agrícola por evento climático ou praga | `weather_events`, `ndvi_data`, `field_inspections`, `harvest_estimates` |

### Sinistros

| Caso de Uso | Descrição | Domínios de Dados |
|-------------|-----------|-------------------|
| Detecção de Fraude | Identificação de sinistros fraudulentos via padrões de comportamento e rede de relações | `claims`, `claimants`, `witnesses`, `repair_shops`, `social_graph` |
| Reservas IBNR | Cálculo de sinistros ocorridos mas não reportados (Incurred But Not Reported) | `claims`, `reporting_delays`, `development_triangles`, `actuarial_assumptions` |
| Triage Automático | Classificação de sinistros por complexidade (fast track vs complex) | `claims`, `claim_photos`, `initial_descriptions`, `historical_similar_claims` |
| Fraud Network Analysis | Detecção de redes de fraude organizadas (corretoras, oficinas, médicos) | `claims`, `service_providers`, `claimants`, `payments`, `entity_graph` |

### Operações e Retenção

| Caso de Uso | Descrição | Domínios de Dados |
|-------------|-----------|-------------------|
| Churn de Apólices | Predição de cancelamento de apólice no próximo ciclo de renovação | `policies`, `renewals`, `claims_history`, `payment_history`, `interactions` |
| Cross-sell e Up-sell | Oferta de coberturas adicionais com base no perfil do segurado | `policies`, `insured_profiles`, `life_events`, `competitor_data` |
| NPS e Satisfação | Análise de satisfação por canal, produto e touchpoint | `nps_surveys`, `claim_interactions`, `contact_center_logs`, `digital_journeys` |

---

## Schemas Típicos (Reference Architecture)

```sql
-- Apólices (núcleo do negócio de seguros)
CREATE TABLE silver.dim_policies (
  policy_id             STRING NOT NULL,
  policy_number         STRING,                -- número público da apólice
  insured_id_hash       STRING,                -- SHA-256 do CPF/CNPJ do segurado
  product_code          STRING,                -- AUTO | VIDA | RESIDENCIAL | EMPRESARIAL | RURAL
  coverage_type         STRING,                -- COMPREENSIVO | BASICO | TERCEIROS
  inception_date        DATE NOT NULL,
  expiry_date           DATE,
  premium_annual_brl    DECIMAL(14,4),         -- prêmio anual (R$)
  insured_sum_brl       DECIMAL(16,4),         -- importância segurada (R$)
  broker_id             STRING,
  channel               STRING,                -- BROKER | DIGITAL | DIRECT | BANCASSURANCE
  status                STRING,                -- ACTIVE | CANCELLED | EXPIRED | SUSPENDED
  cancellation_reason   STRING,
  PRIMARY KEY (policy_id)
)
PARTITIONED BY (inception_date);

-- Sinistros
CREATE TABLE silver.fct_claims (
  claim_id              STRING NOT NULL,
  policy_id             STRING NOT NULL,
  claimant_id_hash      STRING,                -- SHA-256 do CPF/CNPJ do reclamante
  occurrence_date       DATE NOT NULL,
  notification_date     DATE,                  -- data de comunicação do sinistro
  closing_date          DATE,
  reporting_delay_days  INT,                   -- notification_date - occurrence_date
  claim_type            STRING,                -- COLISAO | ROUBO | INCENDIO | MORTE | INVALIDEZ | etc.
  claimed_amount_brl    DECIMAL(14,4),         -- valor reclamado
  paid_amount_brl       DECIMAL(14,4),         -- valor pago
  reserved_amount_brl   DECIMAL(14,4),         -- reserva IBNR/IBNER
  status                STRING,                -- OPEN | CLOSED_PAID | CLOSED_DENIED | REOPEN | FRAUD_SUSPECTED
  fraud_score           DECIMAL(5,4),          -- 0.0-1.0 — modelo de fraude
  fast_track            BOOLEAN,               -- elegível para liquidação rápida
  PRIMARY KEY (claim_id)
)
PARTITIONED BY (occurrence_date);

-- Exposição de Risco (para cálculo de sinistralidade ponderada)
CREATE TABLE gold.fct_exposure (
  exposure_id           STRING NOT NULL,
  policy_id             STRING NOT NULL,
  product_code          STRING,
  risk_period_start     DATE NOT NULL,
  risk_period_end       DATE NOT NULL,
  earned_premium_brl    DECIMAL(14,4),         -- prêmio ganho no período
  exposure_years        DECIMAL(8,6),          -- anos de exposição (para frequência)
  sum_insured_brl       DECIMAL(16,4),
  PRIMARY KEY (exposure_id)
)
PARTITIONED BY (risk_period_start);

-- Triângulos de Desenvolvimento (atuarial — IBNR)
CREATE TABLE gold.fct_development_triangles (
  triangle_id           STRING NOT NULL,
  product_code          STRING NOT NULL,
  accident_year         INT NOT NULL,          -- ano de ocorrência
  development_year      INT NOT NULL,          -- lag de desenvolvimento (1, 2, 3...)
  cumulative_paid_brl   DECIMAL(16,4),         -- sinistros pagos acumulados
  cumulative_incurred_brl DECIMAL(16,4),       -- sinistros incorridos acumulados (pago + reserva)
  case_reserves_brl     DECIMAL(14,4),         -- reservas de caso no período
  PRIMARY KEY (triangle_id)
);

-- Telemática de Motoristas (Auto — UBI)
CREATE TABLE silver.fct_telematics_trips (
  trip_id               STRING NOT NULL,
  device_id             STRING NOT NULL,       -- anonimizado — não vincular diretamente ao CPF
  policy_id             STRING NOT NULL,
  trip_start_ts         TIMESTAMP NOT NULL,
  trip_end_ts           TIMESTAMP,
  distance_km           DECIMAL(8,2),
  duration_minutes      INT,
  avg_speed_kmh         DECIMAL(6,2),
  max_speed_kmh         DECIMAL(6,2),
  hard_braking_events   INT,
  sharp_acceleration    INT,
  night_driving_pct     DECIMAL(5,2),          -- % do tempo em horário noturno (22h-6h)
  driver_score          DECIMAL(5,2),          -- 0-100 (100 = melhor)
  PRIMARY KEY (trip_id)
)
PARTITIONED BY (DATE(trip_start_ts));
```

---

## KPIs de Referência

### Resultado Técnico

| KPI | Fórmula | Threshold |
|-----|---------|-----------|
| **Sinistralidade** (Loss Ratio) | Sinistros pagos / Prêmios ganhos × 100 | SUSEP alerta: > 70% (varia por produto) |
| **Combined Ratio** | (Sinistros + Despesas) / Prêmios ganhos × 100 | < 100% = resultado técnico positivo |
| **Expense Ratio** | Despesas operacionais / Prêmios emitidos × 100 | Benchmark: 25-35% |
| **IBNR Adequacy** | Reserva IBNR / Sinistros esperados não reportados | Monitorar desvio vs. realizado |
| **Frequência de Sinistros** | Nº de sinistros / Exposição (apólice-ano) | Benchmark por produto e região |
| **Severidade Média** | Valor total pago / Nº de sinistros fechados | Monitorar inflation trends |

### Operacional

| KPI | Fórmula | Meta |
|-----|---------|------|
| **Cycle Time** (sinistro) | Data fechamento − Data comunicação | Auto simples: < 15 dias; complexo: < 60 dias |
| **Fast Track Rate** | Sinistros fast track / Total × 100 | Meta: > 40% (reduz custo operacional) |
| **Fraud Detection Rate** | Sinistros identificados como fraude / Total investigado | Benchmark: 8-15% do volume investigado |
| **Retention Rate** | Apólices renovadas / Total vencidas × 100 | Meta: > 75% (vida), > 65% (auto) |

---

## Conformidade e Privacidade

### LGPD em Seguros

```sql
-- Dados de sinistros contêm dados sensíveis (saúde, morte, invalidez) — LGPD Art. 11
-- CPF/CNPJ do segurado e beneficiários → dados pessoais obrigatoriamente pseudonimizados

-- Verificação: garantir que dados identificadores estão hasheados em Silver/Gold
SELECT
  COUNT(*) AS pii_exposure_count
FROM silver.fct_claims
WHERE LENGTH(claimant_id_hash) != 64  -- SHA-256 = 64 chars hex
   OR claimant_id_hash IS NULL;

-- Prazo de retenção: SUSEP exige manutenção de dados por mínimo 5 anos após encerramento
-- Apólices vida: prazo especial (pode ser indefinido por natureza do risco)
```

### SUSEP — Regulação Setorial

```sql
-- Circular SUSEP 517/2015 — Provisões técnicas obrigatórias
-- PPNG (Prêmios Não Ganhos), PSinistros (Provisão de Sinistros), IBNR

-- Validação de adequação de reservas (simplificada)
SELECT
  product_code,
  accident_year,
  SUM(cumulative_incurred_brl) AS total_incurred,
  SUM(case_reserves_brl) AS total_reserves,
  ROUND(SUM(case_reserves_brl) / SUM(cumulative_incurred_brl) * 100, 1) AS reserve_adequacy_pct
FROM gold.fct_development_triangles
WHERE development_year = (SELECT MAX(development_year) FROM gold.fct_development_triangles)
GROUP BY product_code, accident_year
ORDER BY accident_year DESC, product_code;
-- Adequacy < 80% → alerta para revisão atuarial
```

---

## Anti-Padrões Específicos de Insurance

| ID | Anti-padrão | Risco |
|----|-------------|-------|
| IS01 | CPF/CNPJ ou dados de saúde em claro em tabelas Silver/Gold | CRITICAL — violação LGPD Art. 11 + SUSEP |
| IS02 | Sinistralidade calculada com prêmios emitidos em vez de ganhos (earned) | HIGH — superestima resultado positivo; usar prêmio ganho pro-rata |
| IS03 | IBNR calculado sem triângulo de desenvolvimento por accident year | HIGH — reserva subestimada; provisão inadequada perante SUSEP |
| IS04 | Dados de telemática vinculados diretamente ao CPF (sem device_id intermediário) | HIGH — dado de localização pessoal sem camada de anonimização |
| IS05 | Frequência de fraude calculada sobre total de sinistros (não sobre investigados) | MEDIUM — taxa artificialmente baixa; calcular apenas sobre investigados |
| IS06 | Combined Ratio calculado sem separar earning period do writing period | MEDIUM — distorce análise de resultado por safra de apólice |

---
domain: industry
industry: telecom
updated_at: 2026-04-30
agents: [catalog-intelligence, business-analyst, governance-auditor, data-quality-steward]
---

# Telecom — Knowledge Base de Indústria

Referência de casos de uso, schemas típicos, KPIs e conformidade para times de dados
atuando em operadoras móveis (MNO), operadoras virtuais (MVNO), provedores de internet
(ISP), empresas de telecomunicações fixas e corporativas.

---

## Casos de Uso de Dados por Objetivo

### Análise de Rede e Qualidade de Serviço

| Caso de Uso | Descrição | Domínios de Dados |
|-------------|-----------|-------------------|
| Network KPI Monitoring | Dashboard em tempo real de KPIs de rede (drop rate, throughput, latência) por célula e região | `network_events`, `cell_kpis`, `dim_cell_towers`, `dim_geography` |
| Root Cause Analysis (RCA) | Identificação automática de causa raiz de degradação de rede por correlação de alarmes | `network_alarms`, `cell_kpis`, `change_events`, `dim_equipment` |
| Capacity Planning | Previsão de tráfego por célula e planejamento de expansão de capacidade | `traffic_volumes`, `subscriber_activity`, `forecast_models`, `dim_cell_towers` |
| QoE (Quality of Experience) | Correlação entre KPIs de rede e experiência percebida pelo usuário | `speed_tests`, `app_performance`, `network_kpis`, `dim_subscribers` |

### Analytics de Assinantes e Churn

| Caso de Uso | Descrição | Domínios de Dados |
|-------------|-----------|-------------------|
| Churn Prediction | Predição de cancelamento de contrato 30/60/90 dias à frente — pós-pago e pré-pago | `cdr`, `billing`, `customer_interactions`, `plan_changes`, `network_quality` |
| ARPU Segmentation | Segmentação de assinantes por receita, plano, uso e risco de churn | `billing`, `dim_subscribers`, `plan_types`, `usage_history` |
| NBO/Next-Best-Offer | Recomendação de upgrade, add-on ou plano mais adequado ao perfil de uso | `usage_history`, `billing`, `competitor_offers`, `dim_subscribers` |
| Lifetime Value (LTV) | Estimativa de receita líquida total por assinante durante o relacionamento | `billing`, `cac`, `churn_probability`, `plan_margins` |

### CDR e Uso

| Caso de Uso | Descrição | Domínios de Dados |
|-------------|-----------|-------------------|
| CDR Analysis | Análise de padrões de chamada, dados e SMS por assinante, célula e período | `fct_call_detail_records`, `dim_subscribers`, `dim_cell_towers` |
| Data Traffic Analysis | Análise de consumo de dados por app, tecnologia (4G/5G) e horário | `data_sessions`, `app_classification`, `network_events` |
| Roaming Analytics | Receita e custo de roaming internacional; parceiros com melhor cobertura | `roaming_cdr`, `roaming_agreements`, `partner_settlements` |
| Fraud Detection | Detecção de SIM swapping, wangiri, bypass de interconnect e fraude de crédito | `cdr`, `sim_events`, `location_events`, `billing_anomalies` |

---

## Schemas Típicos (Reference Architecture)

```sql
-- Call Detail Records (CDR) — núcleo analítico de telecom
-- CRÍTICO: Contém dados de comunicação — proteção constitucional (art. 5, XII CF/88) + LGPD
CREATE TABLE silver.fct_call_detail_records (
  cdr_id              STRING NOT NULL,
  subscriber_id_hash  STRING NOT NULL,           -- SHA-256 do MSISDN — nunca em claro
  calling_hash        STRING,                    -- número chamador pseudonimizado
  called_hash         STRING,                    -- número chamado pseudonimizado
  call_start_ts       TIMESTAMP NOT NULL,
  call_end_ts         TIMESTAMP,
  duration_seconds    INT,                       -- duração da chamada (0 para tentativas)
  call_type           STRING,                    -- VOICE | SMS | DATA | MMS | ROAMING_VOICE | ROAMING_DATA
  direction           STRING,                    -- OUTGOING | INCOMING | FORWARDED
  call_status         STRING,                    -- COMPLETED | FAILED | BUSY | NO_ANSWER | CANCELLED
  cell_id_start       STRING,                    -- célula no início da chamada
  cell_id_end         STRING,                    -- célula no final (handover)
  technology          STRING,                    -- 2G | 3G | 4G | 5G | WIFI_CALLING
  charged_units       DECIMAL(12,4),             -- unidades cobradas (minutos, MB, SMS)
  charged_amount_brl  DECIMAL(10,4),             -- valor cobrado na moeda local
  is_on_net           BOOLEAN,                   -- chamada dentro da mesma operadora
  roaming_country     STRING,                    -- ISO 3166-1 alpha-2 se em roaming
  PRIMARY KEY (cdr_id)
)
PARTITIONED BY (DATE(call_start_ts));            -- obrigatório — CDR: bilhões de linhas/mês

-- Assinantes (dim — sem PII direta)
CREATE TABLE silver.dim_subscribers (
  subscriber_id       STRING NOT NULL,           -- ID interno — nunca MSISDN em claro
  msisdn_hash         STRING,                    -- SHA-256 do número
  imsi_hash           STRING,                    -- SHA-256 do IMSI
  plan_id             STRING,
  plan_type           STRING,                    -- PREPAID | POSTPAID | HYBRID | CORPORATE
  activation_date     DATE,
  deactivation_date   DATE,
  segment             STRING,                    -- MASS | HIGH_VALUE | YOUTH | SENIOR | CORPORATE
  state_code          STRING,                    -- UF (BR) — sem endereço completo
  churn_risk_score    DECIMAL(5,4),              -- 0.0 a 1.0 — atualizado diariamente
  ltv_estimate_brl    DECIMAL(12,2),             -- LTV estimado pelo modelo
  PRIMARY KEY (subscriber_id)
);

-- Antenas/Torres (dim)
CREATE TABLE silver.dim_cell_towers (
  cell_id             STRING NOT NULL,
  site_id             STRING,                    -- site físico (pode ter múltiplas células)
  cell_name           STRING,
  technology          STRING,                    -- 2G | 3G | 4G | 5G
  band_mhz            INT,                       -- banda de frequência (700, 850, 1800, 2600, 3500)
  azimuth_deg         INT,                       -- azimute da antena (0-360°)
  latitude            DECIMAL(10,7),
  longitude           DECIMAL(10,7),
  state_code          STRING,
  municipality        STRING,
  region              STRING,                    -- região de rede (ex: SP-CENTRO, RJ-NORTE)
  max_capacity_erlangs DECIMAL(8,2),             -- capacidade máxima em Erlangs
  PRIMARY KEY (cell_id)
);

-- KPIs de Rede por Célula (agregado horário)
CREATE TABLE gold.fct_cell_kpis (
  kpi_id              STRING NOT NULL,
  cell_id             STRING NOT NULL,
  hour_ts             TIMESTAMP NOT NULL,        -- truncado para hora
  technology          STRING,
  -- Acessibilidade
  call_setup_success_rate DECIMAL(5,4),          -- CSSR: chamadas estabelecidas / tentativas
  -- Retenção
  call_drop_rate      DECIMAL(5,4),              -- CDR: chamadas caídas / estabelecidas
  handover_success_rate DECIMAL(5,4),            -- HOSR
  -- Tráfego
  traffic_erlangs     DECIMAL(10,4),             -- tráfego total em Erlangs
  active_subscribers  INT,                       -- assinantes ativos na hora
  data_throughput_mbps DECIMAL(12,4),            -- throughput médio (Mbps)
  -- Qualidade
  avg_signal_dbm      DECIMAL(8,2),              -- sinal médio recebido (dBm)
  interference_level  DECIMAL(5,4),              -- nível de interferência
  packet_loss_rate    DECIMAL(5,4),              -- perda de pacotes
  avg_latency_ms      DECIMAL(8,2),              -- latência média (ms)
  PRIMARY KEY (kpi_id)
)
PARTITIONED BY (DATE(hour_ts));

-- Billing / Faturamento (assinante × ciclo)
CREATE TABLE gold.fct_billing (
  billing_id          STRING NOT NULL,
  subscriber_id       STRING NOT NULL,
  billing_cycle_start DATE NOT NULL,
  billing_cycle_end   DATE NOT NULL,
  plan_revenue_brl    DECIMAL(12,4),             -- receita de plano (mensalidade)
  usage_revenue_brl   DECIMAL(12,4),             -- receita excedente (acima do plano)
  roaming_revenue_brl DECIMAL(12,4),
  discount_brl        DECIMAL(12,4),
  total_revenue_brl   DECIMAL(12,4),             -- receita bruta
  tax_amount_brl      DECIMAL(12,4),             -- ICMS + PIS/COFINS
  net_revenue_brl     DECIMAL(12,4),             -- receita líquida
  payment_status      STRING,                    -- PAID | PENDING | OVERDUE | DISPUTED | WRITTEN_OFF
  PRIMARY KEY (billing_id)
)
PARTITIONED BY (billing_cycle_start);
```

---

## KPIs de Referência

### Financeiros

| KPI | Fórmula | Benchmark |
|-----|---------|-----------|
| **ARPU** (Average Revenue Per User) | Total revenue / Assinantes ativos | Pós-pago BR: R$55–90/mês; Pré-pago: R$15–25/mês |
| **ARPU Blended** | (Receita pós + pré) / (Assinantes pós + pré) | Monitorar tendência mês a mês |
| **Churn Rate** | Assinantes cancelados / Assinantes início do período × 100 | Pós-pago: < 1.5%/mês; Pré-pago: < 4%/mês |
| **Customer LTV** | ARPU × Margem × (1 / Churn Rate mensal) | Benchmarking interno por segmento |
| **CAC** (Customer Acquisition Cost) | Custo total de aquisição / Novos assinantes | Monitorar CAC/LTV ratio — meta: > 3x |

### Rede — KPIs ITU/3GPP

| KPI | Fórmula | Threshold |
|-----|---------|-----------|
| **CSSR** (Call Setup Success Rate) | Chamadas estabelecidas / Tentativas × 100 | > 98.5% (ANATEL padrão) |
| **CDR** (Call Drop Rate) | Chamadas caídas / Estabelecidas × 100 | < 1.5% (ANATEL) |
| **HOSR** (Handover Success Rate) | Handovers bem-sucedidos / Tentativas × 100 | > 97% |
| **Network Availability** | Horas de operação / Horas totais × 100 | > 99.9% (SLA) |
| **Data Throughput** | Mbps médio por usuário ativo | 4G: > 30 Mbps DL; 5G: > 200 Mbps DL |
| **Latency** | RTT médio em ms | 4G: < 50ms; 5G: < 10ms |

### Qualidade de Experiência

| KPI | Fórmula | Meta |
|-----|---------|------|
| **NPS** | % Promotores − % Detratores | > 30 (benchmark operadora BR) |
| **First Call Resolution** | Problemas resolvidos no 1º contato / Total | > 75% |
| **App Score** | Rating médio na app store | > 4.0 |

---

## Conformidade e Privacidade

### LGPD + Sigilo de Comunicações (CF/88)

```sql
-- Dados de CDR têm proteção constitucional (Art. 5, XII CF/88)
-- + são dados pessoais sob LGPD Art. 5 (I)
-- NUNCA expor MSISDN, IMSI ou número chamado/chamador em claro

-- Política de retenção obrigatória
-- ANATEL: CDR retidos por mínimo 5 anos (Res. 614/2013)
-- LGPD: prazo mínimo legal prevalece sobre preferência do titular

-- Verificação: garantir pseudonimização em Silver/Gold
SELECT
  COUNT(*) AS records_with_pii_exposure
FROM silver.fct_call_detail_records
WHERE calling_hash IS NULL    -- MSISDN em claro detectado
   OR called_hash IS NULL
   OR LENGTH(calling_hash) != 64;  -- hash SHA-256 = 64 chars hex

-- Requisição de acesso ANATEL/Judiciário (quebra de sigilo autorizada)
-- Deve passar por processo formal — NUNCA retornar MSISDN diretamente em queries analíticas
```

### ANATEL — Regulação

```sql
-- Indicadores de qualidade obrigatórios (RGQ — Resolução ANATEL 717/2019)
-- SMP (Serviço Móvel Pessoal): reportar mensalmente por UF

SELECT
  t.state_code AS uf,
  DATE_TRUNC('month', k.hour_ts) AS reference_month,
  AVG(k.call_setup_success_rate) AS avg_cssr,
  AVG(k.call_drop_rate) AS avg_cdr,
  AVG(k.handover_success_rate) AS avg_hosr,
  AVG(k.data_throughput_mbps) AS avg_throughput_mbps,
  -- ANATEL thresholds: CSSR >= 98.5%, CDR <= 1.5%, HOSR >= 97%
  SUM(CASE WHEN k.call_setup_success_rate < 0.985 THEN 1 ELSE 0 END) AS cssr_violations,
  SUM(CASE WHEN k.call_drop_rate > 0.015 THEN 1 ELSE 0 END) AS cdr_violations
FROM gold.fct_cell_kpis k
JOIN silver.dim_cell_towers t USING (cell_id)
WHERE k.hour_ts >= DATE_TRUNC('month', ADD_MONTHS(CURRENT_DATE, -1))
  AND k.technology = '4G'
GROUP BY t.state_code, DATE_TRUNC('month', k.hour_ts)
ORDER BY avg_cdr DESC;
```

---

## Anti-Padrões Específicos de Telecom

| ID | Anti-padrão | Risco |
|----|-------------|-------|
| TC01 | MSISDN ou IMSI em claro em qualquer tabela Silver/Gold | CRITICAL — violação constitucional (Art. 5 XII CF/88) + LGPD + ANATEL |
| TC02 | CDR sem particionamento por data | CRITICAL — CDR de grande operadora: 5–20 bilhões de linhas/mês; full scan inviável |
| TC03 | Churn calculado incluindo suspensões temporárias como cancelamento | HIGH — infla churn rate; distinguir CANCELLED de SUSPENDED no status |
| TC04 | ARPU calculado dividindo por assinantes totais (incluindo inativos) | HIGH — subestima ARPU real; usar apenas assinantes ativos com faturamento no período |
| TC05 | Sessões de dados não deduplicadas antes de calcular throughput | HIGH — sessões TCP/IP geram múltiplos registros; deduplicate por session_id |
| TC06 | KPIs de rede calculados por célula sem distinção por tecnologia (2G/3G/4G/5G) | MEDIUM — métricas incomparáveis; sempre filtrar ou agregar por technology |
| TC07 | Retenção de CDR inferior a 5 anos | HIGH — violação Res. ANATEL 614/2013; risco de multa e cassação de licença |

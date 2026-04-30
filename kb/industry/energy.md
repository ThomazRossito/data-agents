---
domain: industry
industry: energy
updated_at: 2026-04-30
agents: [catalog-intelligence, business-analyst, governance-auditor, data-quality-steward]
---

# Energy — Knowledge Base de Indústria

Referência de casos de uso, schemas típicos, KPIs e conformidade para times de dados
atuando em geradoras, transmissoras, distribuidoras (utilities), oil & gas upstream/downstream,
biocombustíveis e smart grid.

---

## Casos de Uso de Dados por Objetivo

### Utilities (Distribuição e Transmissão)

| Caso de Uso | Descrição | Domínios de Dados |
|-------------|-----------|-------------------|
| Smart Meter Analytics | Análise de consumo horário por unidade consumidora — detecção de perdas técnicas e não-técnicas | `meter_readings`, `consumers`, `substations`, `tariff_classes` |
| Detecção de Fraude (Furto de Energia) | Identificação de ligações clandestinas e adulteração de medidores via anomalia de consumo | `meter_readings`, `field_inspections`, `consumption_history` |
| SAIDI/SAIFI — Qualidade de Fornecimento | Cálculo de indicadores regulatórios de continuidade de serviço por conjunto/subconjunto | `outages`, `consumers_affected`, `restoration_events`, `dem_sets` |
| Previsão de Demanda | Forecast de carga por subestação para planejamento de capacidade e despacho | `meter_readings`, `weather_data`, `historical_load`, `calendar` |
| Manutenção Preditiva de Ativos | Predição de falha em transformadores, chaves e cabos via dados de monitoramento | `asset_telemetry`, `maintenance_history`, `failure_events`, `dim_assets` |

### Oil & Gas (Upstream e Downstream)

| Caso de Uso | Descrição | Domínios de Dados |
|-------------|-----------|-------------------|
| Production Optimization | Maximização de produção de poços via análise de parâmetros operacionais (pressão, vazão, GOR) | `well_telemetry`, `production_allocations`, `reservoir_data` |
| Downtime & Deferment | Rastreamento de perdas de produção por causa raiz (equipamento, processo, mercado) | `production_events`, `downtime_log`, `planned_maintenance` |
| Pipeline Integrity | Monitoramento de corrosão, pressão e vazamentos em dutos via sensores distribuídos | `pipeline_telemetry`, `inspection_records`, `pig_runs` |
| Refinery Throughput | Otimização de throughput de refinaria: carga processada vs capacidade instalada por unidade | `process_units`, `feed_rates`, `product_yields`, `lab_quality` |
| Energy Trading | P&L de operações de compra/venda de energia no mercado livre (CCEE/ACL/ACR) | `contracts`, `spot_prices`, `generation_schedule`, `settlements` |

### Geração Renovável

| Caso de Uso | Descrição | Domínios de Dados |
|-------------|-----------|-------------------|
| Solar Capacity Factor | Eficiência de geração solar vs irradiância esperada (perdas por sujeira, temperatura, sombreamento) | `inverter_telemetry`, `weather_stations`, `irradiance_data` |
| Wind Performance | Potência real vs curva de potência do fabricante — detecção de desvios por turbina | `turbine_telemetry`, `wind_measurements`, `theoretical_power` |
| Hydro Reservoir Management | Gestão de nível de reservatório, afluência natural e geração futura | `reservoir_levels`, `rainfall`, `inflow_forecasts`, `dispatch_schedule` |

---

## Schemas Típicos (Reference Architecture)

```sql
-- Leituras de Medidores (Smart Grid — séries temporais de alta frequência)
-- CRÍTICO: Dados PII — identificam unidade consumidora e padrão de uso
CREATE TABLE silver.fct_meter_readings (
  reading_id          STRING NOT NULL,
  meter_id            STRING NOT NULL,           -- chave estrangeira para dim_meters
  consumer_id_hash    STRING,                    -- SHA-256 do código UC — nunca em claro
  reading_ts          TIMESTAMP NOT NULL,        -- timestamp com timezone
  active_energy_kwh   DECIMAL(12,4),             -- energia ativa consumida (kWh)
  reactive_energy_kvarh DECIMAL(12,4),           -- energia reativa (kVArh)
  demand_kw           DECIMAL(10,4),             -- demanda medida (kW)
  reading_quality     STRING,                    -- VALID | ESTIMATED | SUBSTITUTED | MISSING
  channel             INT,                       -- canal do medidor (1=importação, 2=exportação GD)
  PRIMARY KEY (reading_id)
)
PARTITIONED BY (DATE(reading_ts));               -- obrigatório — tabelas chegam a bilhões de linhas

-- Ativos de Rede (Transformadores, Chaves, Cabos)
CREATE TABLE silver.dim_assets (
  asset_id            STRING NOT NULL,
  asset_type          STRING,                    -- TRANSFORMER | SWITCH | CABLE | BUSBAR | INVERTER | TURBINE
  substation_id       STRING,
  voltage_kv          DECIMAL(8,2),              -- tensão nominal (kV)
  capacity_kva        DECIMAL(12,2),             -- capacidade nominal (kVA)
  installation_date   DATE,
  manufacturer        STRING,
  model               STRING,
  criticality         STRING,                    -- CRITICAL | HIGH | MEDIUM | LOW
  coordinates_lat     DECIMAL(10,7),
  coordinates_lon     DECIMAL(10,7),
  PRIMARY KEY (asset_id)
);

-- Interrupções de Fornecimento (base para SAIDI/SAIFI)
CREATE TABLE silver.fct_outages (
  outage_id           STRING NOT NULL,
  asset_id            STRING NOT NULL,           -- asset que originou a interrupção
  dem_set_id          STRING,                    -- conjunto de medição (ANEEL)
  outage_start_ts     TIMESTAMP NOT NULL,
  outage_end_ts       TIMESTAMP,                 -- null se ainda em andamento
  duration_minutes    INT,                       -- outage_end_ts - outage_start_ts
  consumers_affected  INT,                       -- UC impactadas
  cause_code          STRING,                    -- ANIMAL | TREE | EQUIPMENT | WEATHER | HUMAN | UNKNOWN
  cause_category      STRING,                    -- TECHNICAL | EXTERNAL | COMMERCIAL
  is_planned          BOOLEAN,                   -- manutenção programada vs não-programada
  restoration_method  STRING,                    -- AUTOMATIC | MANUAL | CREW_DISPATCH
  PRIMARY KEY (outage_id)
)
PARTITIONED BY (DATE(outage_start_ts));

-- Telemetria de Poços (Oil & Gas Upstream)
CREATE TABLE silver.fct_well_telemetry (
  telemetry_id        STRING NOT NULL,
  well_id             STRING NOT NULL,
  recorded_ts         TIMESTAMP NOT NULL,
  wellhead_pressure_bar DECIMAL(10,4),           -- pressão na cabeça do poço (bar)
  bottomhole_temp_c   DECIMAL(8,2),              -- temperatura de fundo (°C)
  oil_rate_m3d        DECIMAL(12,4),             -- vazão de óleo (m³/dia)
  gas_rate_mm3d       DECIMAL(12,4),             -- vazão de gás (MMm³/dia)
  water_rate_m3d      DECIMAL(12,4),             -- vazão de água (m³/dia)
  gor_m3m3            DECIMAL(10,4),             -- gas-oil ratio (m³/m³)
  bsw_pct             DECIMAL(5,2),              -- base sedimentos e água (%)
  pump_frequency_hz   DECIMAL(8,2),              -- frequência da bomba (Hz)
  is_anomaly          BOOLEAN,                   -- detectado por modelo de anomalia
  PRIMARY KEY (telemetry_id)
)
PARTITIONED BY (DATE(recorded_ts), well_id);

-- Produção Alocada (upstream — após processo de allocation)
CREATE TABLE gold.fct_production_allocations (
  allocation_id       STRING NOT NULL,
  well_id             STRING NOT NULL,
  field_id            STRING NOT NULL,
  production_date     DATE NOT NULL,
  oil_allocated_bbl   DECIMAL(14,4),             -- barris de óleo alocados
  gas_allocated_mscf  DECIMAL(14,4),             -- gás alocado (mscf)
  water_allocated_bbl DECIMAL(14,4),             -- água produzida alocada
  uptime_hours        DECIMAL(6,2),              -- horas de operação no dia
  downtime_hours      DECIMAL(6,2),              -- horas paradas (24 - uptime)
  deferment_cause     STRING,                    -- causa de deferimento se aplicável
  PRIMARY KEY (allocation_id)
)
PARTITIONED BY (production_date);
```

---

## KPIs de Referência

### Utilities — Qualidade de Fornecimento (ANEEL)

| KPI | Fórmula | Threshold Regulatório |
|-----|---------|----------------------|
| **SAIDI** (System Average Interruption Duration Index) | Σ(duração × UCs afetadas) / total UCs | Varia por conjunto ANEEL — meta definida por contrato de concessão |
| **SAIFI** (System Average Interruption Frequency Index) | Σ interrupções × UCs afetadas / total UCs | Varia por conjunto — tipicamente < 10 int/ano em urbano |
| **DIC** (Duração Interrupção Individual) | Duração total de interrupções por UC | ANEEL RES 956/2021: depende da classe |
| **FIC** (Frequência Interrupção Individual) | Nº de interrupções por UC no período | ANEEL RES 956/2021 |
| **Perdas Técnicas** | (Energia injetada - Energia faturada - Perdas Comerciais) / Energia injetada | Meta ANEEL por concessão |
| **Perdas Não-Técnicas** | Energia faturável não recuperada (furto, fraude, erros) | Benchmark: < 5% em urbano |

### Oil & Gas — Produção

| KPI | Fórmula | Benchmark |
|-----|---------|-----------|
| **Uptime** | Horas de produção / Horas totais × 100 | Meta: > 95% em campo maduro |
| **Deferment** | Produção potencial − Produção real (bbl/d) | Monitorar causas raiz |
| **GOR** (Gas-Oil Ratio) | Vazão de gás / Vazão de óleo (m³/m³) | Varia por campo — baseline definido por reservatório |
| **BSW** (Base Sedimentos e Água) | % de água e sedimentos no óleo produzido | < 0.5% para exportação |
| **Lifting Cost** | Opex total / Produção total (USD/bbl) | Benchmark Bacia de Santos: < 8 USD/bbl |

### Geração Renovável

| KPI | Fórmula | Benchmark |
|-----|---------|-----------|
| **Capacity Factor (Solar)** | Energia gerada real / (Capacidade instalada × horas) | PR > 75% (performance ratio) |
| **Availability Factor (Eólica)** | Horas disponíveis / Horas totais | Meta: > 97% por turbina |
| **Curtailment** | Energia não gerada por restrição de rede | Monitorar por ONS |

---

## Conformidade e Privacidade

### Brasil — Regulação Setorial

```sql
-- ANEEL — Relatório mensal de continuidade (PRODIST Módulo 8)
-- Cálculo de SAIDI por conjunto de medição
SELECT
  dem_set_id,
  DATE_TRUNC('month', outage_start_ts) AS reference_month,
  SUM(duration_minutes * consumers_affected) / MAX(total_consumers) AS saidi_minutes,
  COUNT(DISTINCT outage_id) * SUM(consumers_affected) / MAX(total_consumers) / COUNT(DISTINCT outage_id) AS saifi,
  SUM(CASE WHEN is_planned = FALSE THEN duration_minutes * consumers_affected ELSE 0 END)
    / MAX(total_consumers) AS saidi_unplanned
FROM silver.fct_outages o
JOIN dim_dem_sets d USING (dem_set_id)
WHERE is_planned = FALSE    -- DEC/FEC calculados apenas para não-programadas
  AND DATE(outage_start_ts) >= ADD_MONTHS(CURRENT_DATE, -1)
GROUP BY dem_set_id, DATE_TRUNC('month', outage_start_ts);

-- ANP — Produção fiscalizada (Resolução ANP 43/2007)
-- Relatório mensal de produção por campo e reservatório
SELECT
  field_id,
  DATE_TRUNC('month', production_date) AS reference_month,
  SUM(oil_allocated_bbl) AS total_oil_bbl,
  SUM(gas_allocated_mscf) AS total_gas_mscf,
  SUM(water_allocated_bbl) AS total_water_bbl,
  AVG(uptime_hours / 24.0) AS avg_uptime_pct
FROM gold.fct_production_allocations
WHERE production_date >= ADD_MONTHS(CURRENT_DATE, -1)
GROUP BY field_id, DATE_TRUNC('month', production_date)
ORDER BY reference_month, total_oil_bbl DESC;
```

### LGPD em Energy

- Dados de medidores identificam padrão de vida do consumidor → **dados pessoais** (LGPD Art. 5, I)
- Consumer ID deve ser pseudonimizado (hash SHA-256) em Silver e Gold
- Dados de faturamento → finalidade específica de cobrança; uso para analytics requer consentimento
- Geolocalização de UCs → restrição de acesso por área (não expor em dashboards públicos)

---

## Anti-Padrões Específicos de Energy

| ID | Anti-padrão | Risco |
|----|-------------|-------|
| EG01 | Leituras de medidor sem particionamento por data | CRITICAL — tabelas chegam a bilhões de linhas/ano; full scan destrói cluster |
| EG02 | SAIDI/SAIFI calculado incluindo interrupções programadas | HIGH — inflaciona indicador de qualidade; viola metodologia ANEEL PRODIST |
| EG03 | GOR calculado com vazão instantânea em vez de alocada | HIGH — GOR instantâneo varia muito; usar produção alocada diária |
| EG04 | Furto de energia detectado apenas por threshold fixo | MEDIUM — padrão de consumo varia por estação; usar z-score por perfil de UC |
| EG05 | Consumer ID em claro em tabelas Silver/Gold | CRITICAL — violação LGPD; dados de medidor são dados pessoais |
| EG06 | Previsão de demanda sem features de calendário (feriados, horário de verão) | HIGH — erros > 20% em dias especiais |

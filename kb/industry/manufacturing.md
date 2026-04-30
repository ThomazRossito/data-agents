---
domain: industry
industry: manufacturing
updated_at: 2026-04-30
agents: [catalog-intelligence, business-analyst, data-quality-steward]
---

# Manufacturing — Knowledge Base de Indústria

Referência de casos de uso, schemas típicos, KPIs e padrões de dados para times atuando
em manufatura discreta, contínua (processo), montagem e supply chain industrial.

---

## Casos de Uso de Dados por Objetivo

### Qualidade e Produção

| Caso de Uso | Descrição | Domínios de Dados |
|-------------|-----------|-------------------|
| OEE Monitoring | Disponibilidade × Performance × Qualidade de cada linha de produção em tempo real | `machine_events`, `production_orders`, `downtime_log`, `scrap_log` |
| Predictive Maintenance | Predição de falha de equipamento antes que ocorra, baseada em séries temporais de sensores | `sensor_readings`, `maintenance_history`, `failure_events`, `asset_master` |
| Root Cause Analysis (RCA) | Identificação automática de causa-raiz de defeitos e não-conformidades | `defect_log`, `process_parameters`, `materials`, `operators` |
| Statistical Process Control (SPC) | Controle estatístico de processo: Cp, Cpk, gráficos de controle em tempo real | `measurements`, `control_charts`, `specification_limits` |
| Yield Optimization | Maximizar o rendimento (% de produto bom) minimizando refugo e retrabalho | `production_orders`, `scrap_log`, `rework_log`, `process_params` |

### Supply Chain e Logística

| Caso de Uso | Descrição | KPIs Gerados |
|-------------|-----------|--------------|
| Demand Planning (S&OP) | Previsão de demanda para Planejamento de Vendas e Operações | Forecast Accuracy (MAPE), Bias |
| MRP / Materials Requirement | Cálculo de necessidades de matéria-prima com base no plano de produção | On-Time Delivery, Inventory Turns |
| Supplier Performance | Scorecard de fornecedores: qualidade, prazo, preço | OTIF, Rejections Rate, Lead Time |
| Warehouse Optimization | Otimização de layout e rotas de picking no armazém | Pick Rate, Fill Rate, Space Utilization |

### Manutenção e Ativos

| Caso de Uso | Descrição | Benefício |
|-------------|-----------|-----------|
| MTBF / MTTR Dashboard | Tempo médio entre falhas e tempo médio de reparo por ativo | Redução de downtime não planejado |
| Spare Parts Optimization | Nível ótimo de estoque de peças de reposição | Redução de capital parado |
| Energy Consumption | Análise de consumo energético por linha/turno/produto | Redução de custo e Escopo 2 (carbono) |

---

## Schemas Típicos (Reference Architecture)

```sql
-- Ativos / Equipamentos (Asset Master)
CREATE TABLE gold.dim_assets (
  asset_id          STRING NOT NULL,
  asset_name        STRING,
  asset_type        STRING,                   -- MACHINE | ROBOT | CONVEYOR | FURNACE | PRESS
  plant_id          STRING,
  line_id           STRING,
  cell_id           STRING,
  manufacturer      STRING,
  model             STRING,
  installation_date DATE,
  criticality       STRING,                   -- A | B | C (impacto no OEE da linha)
  PRIMARY KEY (asset_id)
);

-- Leituras de sensores IoT (Alta frequência — particionada por hora)
CREATE TABLE silver.fct_sensor_readings (
  reading_id        STRING NOT NULL,
  asset_id          STRING NOT NULL,
  sensor_id         STRING NOT NULL,
  reading_ts        TIMESTAMP NOT NULL,
  parameter_name    STRING,                   -- TEMPERATURE | VIBRATION | PRESSURE | CURRENT | RPM
  value             DOUBLE,
  unit              STRING,                   -- Celsius | mm/s | bar | A | rpm
  is_anomaly        BOOLEAN DEFAULT FALSE,    -- flag de anomalia detectada por ML
  anomaly_score     DECIMAL(5,4)
)
PARTITIONED BY (DATE(reading_ts), HOUR(reading_ts));

-- Ordens de Produção
CREATE TABLE gold.fct_production_orders (
  order_id          STRING NOT NULL,
  product_id        STRING NOT NULL,
  plant_id          STRING,
  line_id           STRING,
  planned_start_ts  TIMESTAMP,
  actual_start_ts   TIMESTAMP,
  planned_end_ts    TIMESTAMP,
  actual_end_ts     TIMESTAMP,
  planned_qty       INT,
  produced_qty      INT,
  good_qty          INT,
  scrap_qty         INT,
  rework_qty        INT,
  yield_pct         DECIMAL(6,4),            -- good_qty / produced_qty
  status            STRING,                   -- PLANNED | RELEASED | IN_PROGRESS | COMPLETED | CANCELLED
  PRIMARY KEY (order_id)
)
PARTITIONED BY (DATE(actual_start_ts));

-- Log de Downtime (paradas)
CREATE TABLE silver.fct_downtime_log (
  downtime_id       STRING NOT NULL,
  asset_id          STRING NOT NULL,
  line_id           STRING,
  start_ts          TIMESTAMP NOT NULL,
  end_ts            TIMESTAMP,
  duration_minutes  INT,
  downtime_type     STRING,                   -- PLANNED | UNPLANNED | CHANGEOVER | QUALITY | LOGISTICS
  downtime_reason   STRING,
  root_cause        STRING,
  reported_by       STRING,
  PRIMARY KEY (downtime_id)
)
PARTITIONED BY (DATE(start_ts));

-- Histórico de Manutenção
CREATE TABLE gold.fct_maintenance_history (
  work_order_id     STRING NOT NULL,
  asset_id          STRING NOT NULL,
  maintenance_type  STRING,                   -- PREVENTIVE | CORRECTIVE | PREDICTIVE | CONDITION_BASED
  start_ts          TIMESTAMP,
  end_ts            TIMESTAMP,
  duration_hours    DECIMAL(6,2),
  parts_used        ARRAY<STRUCT<part_id:STRING, qty:INT>>,
  labor_hours       DECIMAL(6,2),
  total_cost        DECIMAL(10,2),
  failure_mode      STRING,
  PRIMARY KEY (work_order_id)
);
```

---

## KPIs de Referência

| KPI | Fórmula | Benchmark |
|-----|---------|-----------|
| **OEE** (Overall Equipment Effectiveness) | Disponibilidade × Performance × Qualidade | Classe mundial: > 85% |
| **Availability** | (Tempo Planejado − Downtime) / Tempo Planejado | Meta: > 95% |
| **Performance** | (Prod. Real × Ciclo Ideal) / Tempo Disponível | Meta: > 95% |
| **Quality (First Pass Yield)** | Peças Boas / Total Produzido | Meta: > 98% |
| **MTBF** (Mean Time Between Failures) | Tempo Total / Número de Falhas | Quanto maior, melhor |
| **MTTR** (Mean Time to Repair) | Tempo Total de Reparo / Número de Reparos | Quanto menor, melhor |
| **Scrap Rate** | Scrap / Total Produzido × 100 | Meta: < 1% |
| **Rework Rate** | Retrabalho / Total Produzido × 100 | Meta: < 0.5% |
| **Forecast Accuracy** | 1 − MAPE (Mean Absolute Percentage Error) | Meta: > 85% |
| **OTIF** (On Time In Full) | Pedidos entregues no prazo e quantidade / Total | Meta: > 95% |
| **Inventory Turns** | Custo dos Produtos Vendidos / Estoque Médio | Benchmark: 8–12x/ano (indústria) |
| **Energy Intensity** | kWh / unidade produzida | Redução contínua (ESG) |

---

## Padrões de Integração IoT / Time Series

```python
# Pattern: ingestão de sensores via Auto Loader (alta frequência)
import dlt
from pyspark.sql.functions import col, from_json, schema_of_json

SENSOR_SCHEMA = "reading_id STRING, asset_id STRING, sensor_id STRING, reading_ts TIMESTAMP, parameter_name STRING, value DOUBLE, unit STRING"

@dlt.table(
    name="bronze_sensor_readings",
    comment="Raw IoT sensor data from plant floor — append only",
    table_properties={"quality": "bronze", "delta.autoOptimize.optimizeWrite": "true"},
)
def bronze_sensor_readings():
    return (
        spark.readStream
        .format("cloudFiles")
        .option("cloudFiles.format", "json")
        .option("cloudFiles.schemaLocation", "/mnt/checkpoints/sensor_schema")
        .load("/mnt/iot-raw/sensors/")
        .select(from_json(col("value"), SENSOR_SCHEMA).alias("data"))
        .select("data.*")
    )

# Anomaly detection Silver (Z-score simples)
@dlt.table(name="silver_sensor_readings")
@dlt.expect_or_drop("valid_reading", "value IS NOT NULL AND value > -9999")
def silver_sensor_readings():
    from pyspark.sql.functions import stddev, avg, abs as spark_abs
    df = dlt.read_stream("bronze_sensor_readings")
    stats = (
        df.groupBy("asset_id", "sensor_id", "parameter_name")
        .agg(avg("value").alias("mean_val"), stddev("value").alias("std_val"))
    )
    return (
        df.join(stats, ["asset_id", "sensor_id", "parameter_name"])
        .withColumn("z_score", spark_abs((col("value") - col("mean_val")) / col("std_val")))
        .withColumn("is_anomaly", col("z_score") > 3.0)
        .withColumn("anomaly_score", col("z_score") / 10.0)
    )
```

---

## Anti-Padrões Específicos de Manufacturing

| ID | Anti-padrão | Risco |
|----|-------------|-------|
| MF01 | OEE calculado sem separar perdas planejadas de não planejadas | HIGH — OEE inflado, esconde downtime real |
| MF02 | Sensores IoT sem timestamp de geração (só de recebimento) | HIGH — análise temporal incorreta |
| MF03 | Yield calculado incluindo retrabalho no numerador | MEDIUM — FPY (First Pass Yield) subestimado |
| MF04 | Dados de manutenção sem vínculo ao ativo específico (só à linha) | HIGH — MTBF/MTTR por ativo impossível |
| MF05 | Séries temporais de sensores sem tratamento de outliers antes de ML | HIGH — modelo de manutenção preditiva com viés |
| MF06 | OTIF calculado por pedido, não por linha de pedido | MEDIUM — penaliza fornecedor por item único atrasado |

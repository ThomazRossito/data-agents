---
domain: industry
industry: logistics
updated_at: 2026-04-30
agents: [catalog-intelligence, business-analyst, governance-auditor, data-quality-steward]
---

# Logistics & Transportation — Knowledge Base de Indústria

Referência de casos de uso, schemas típicos, KPIs e conformidade para times de dados
atuando em transportadoras, operadores logísticos (3PL/4PL), e-commerce fulfillment,
last-mile delivery, armazéns, portos e cadeias de suprimentos.

---

## Casos de Uso de Dados por Objetivo

### Operações de Transporte

| Caso de Uso | Descrição | Domínios de Dados |
|-------------|-----------|-------------------|
| OTIF (On-Time In-Full) | Monitoramento de entregas no prazo e volume correto por cliente e rota | `shipments`, `deliveries`, `orders`, `dim_customers`, `dim_routes` |
| Otimização de Rotas | Redução de custo e tempo de entrega via roteamento dinâmico | `vehicle_telemetry`, `traffic_data`, `dim_stops`, `delivery_windows` |
| Track & Trace | Visibilidade end-to-end da posição de cargas em tempo real | `tracking_events`, `dim_shipments`, `carrier_milestones`, `iot_sensors` |
| Previsão de Atrasos | Detecção antecipada de entregas em risco via ML (clima, tráfego, capacidade) | `shipments`, `weather_data`, `traffic_events`, `historical_delays` |
| Gestão de Frota | Monitoramento de disponibilidade, manutenção e performance de veículos | `vehicle_telemetry`, `maintenance_records`, `dim_vehicles`, `fuel_consumption` |

### Armazém e Fulfillment

| Caso de Uso | Descrição | Domínios de Dados |
|-------------|-----------|-------------------|
| Slotting Optimization | Posicionamento de SKUs no armazém para minimizar movimentação | `order_history`, `picking_patterns`, `dim_locations`, `dim_skus` |
| Picking Performance | Análise de produtividade de separação por operador e zona | `picking_events`, `dim_operators`, `dim_zones`, `wms_orders` |
| Acuracidade de Inventário | Desvio entre estoque físico e sistêmico detectado em contagens cíclicas | `inventory_counts`, `wms_positions`, `dim_skus`, `dim_locations` |
| Cross-Docking | Eficiência de operações sem armazenagem: recebimento → expedição direto | `inbound_shipments`, `outbound_shipments`, `dock_events`, `dwell_time` |

### Cadeia de Suprimentos

| Caso de Uso | Descrição | Domínios de Dados |
|-------------|-----------|-------------------|
| Demand Sensing | Sinal de demanda de curto prazo (dias) para abastecimento de DCs | `pos_data`, `orders_history`, `inventory_positions`, `promotional_calendar` |
| Supply Chain Risk | Identificação de fornecedores de risco (único fornecedor, concentração geográfica) | `supplier_data`, `order_history`, `geo_risk_scores`, `lead_times` |
| Carbon Footprint Logístico | Mensuração de emissões de CO₂ por modal e rota | `shipments`, `vehicle_fuel_consumption`, `emission_factors`, `modal_mix` |

---

## Schemas Típicos (Reference Architecture)

```sql
-- Remessas / Embarques
CREATE TABLE silver.fct_shipments (
  shipment_id           STRING NOT NULL,
  order_id              STRING NOT NULL,
  shipper_id            STRING,
  consignee_id_hash     STRING,                -- SHA-256 se PF; CNPJ em claro se PJ
  carrier_id            STRING,
  origin_location_id    STRING,
  destination_location_id STRING,
  ship_date             DATE NOT NULL,
  promised_delivery_date DATE,                 -- data prometida ao cliente
  actual_delivery_date  DATE,
  weight_kg             DECIMAL(10,4),
  volume_m3             DECIMAL(10,4),
  freight_cost_brl      DECIMAL(12,4),
  shipment_status       STRING,                -- CREATED | IN_TRANSIT | DELIVERED | FAILED | RETURNED
  failure_reason        STRING,
  is_on_time            BOOLEAN,               -- actual_delivery_date <= promised_delivery_date
  is_in_full            BOOLEAN,               -- volume/itens entregues = volume/itens pedidos
  otif                  BOOLEAN,               -- is_on_time AND is_in_full
  PRIMARY KEY (shipment_id)
)
PARTITIONED BY (ship_date);

-- Eventos de Rastreamento (Track & Trace)
CREATE TABLE silver.fct_tracking_events (
  event_id              STRING NOT NULL,
  shipment_id           STRING NOT NULL,
  event_ts              TIMESTAMP NOT NULL,
  event_type            STRING,                -- PICKUP | IN_TRANSIT | HUB_ARRIVAL | OUT_FOR_DELIVERY | DELIVERED | FAILED_ATTEMPT | RETURNED
  location_id           STRING,
  location_lat          DECIMAL(10,7),
  location_lon          DECIMAL(10,7),
  carrier_code          STRING,
  milestone_sequence    INT,                   -- ordem esperada do evento
  is_exception          BOOLEAN,               -- evento fora do fluxo normal
  exception_reason      STRING,
  PRIMARY KEY (event_id)
)
PARTITIONED BY (DATE(event_ts));

-- Telemetria de Veículos (IoT — séries temporais)
CREATE TABLE silver.fct_vehicle_telemetry (
  telemetry_id          STRING NOT NULL,
  vehicle_id            STRING NOT NULL,
  driver_id_hash        STRING,                -- SHA-256 — dado pessoal do motorista
  recorded_ts           TIMESTAMP NOT NULL,
  latitude              DECIMAL(10,7),
  longitude             DECIMAL(10,7),
  speed_kmh             DECIMAL(6,2),
  fuel_level_pct        DECIMAL(5,2),
  odometer_km           DECIMAL(10,2),
  engine_status         STRING,               -- ON | OFF | IDLE
  harsh_braking         BOOLEAN,
  harsh_acceleration    BOOLEAN,
  is_speeding           BOOLEAN,              -- velocidade > limite + threshold
  PRIMARY KEY (telemetry_id)
)
PARTITIONED BY (DATE(recorded_ts), vehicle_id);

-- Posições de Inventário em Armazém
CREATE TABLE silver.fct_inventory_positions (
  position_id           STRING NOT NULL,
  sku_id                STRING NOT NULL,
  location_id           STRING NOT NULL,       -- endereço no WMS (corredor-prateleira-nível)
  warehouse_id          STRING NOT NULL,
  snapshot_date         DATE NOT NULL,
  quantity_on_hand      INT,
  quantity_reserved     INT,
  quantity_available    INT,                   -- on_hand - reserved
  lot_number            STRING,
  expiry_date           DATE,                  -- para produtos perecíveis
  PRIMARY KEY (position_id)
)
PARTITIONED BY (snapshot_date);

-- KPIs de OTIF por cliente e período
CREATE TABLE gold.fct_otif_metrics (
  metric_id             STRING NOT NULL,
  customer_id           STRING NOT NULL,
  metric_date           DATE NOT NULL,
  total_shipments       INT,
  on_time_shipments     INT,
  in_full_shipments     INT,
  otif_shipments        INT,
  on_time_rate          DECIMAL(5,4),          -- on_time_shipments / total_shipments
  in_full_rate          DECIMAL(5,4),
  otif_rate             DECIMAL(5,4),
  avg_delay_days        DECIMAL(6,2),          -- média de dias de atraso
  PRIMARY KEY (metric_id)
)
PARTITIONED BY (metric_date);
```

---

## KPIs de Referência

### Entrega e Serviço

| KPI | Fórmula | Benchmark |
|-----|---------|-----------|
| **OTIF** | Entregas no prazo e volume correto / Total × 100 | E-commerce BR: > 95%; B2B: > 98% |
| **On-Time Rate** | Entregas no prazo / Total × 100 | Meta: > 96% |
| **First Attempt Delivery Rate** | Entregas na 1ª tentativa / Total × 100 | Last-mile: > 85% |
| **Average Lead Time** | Dias entre order e entrega | Varia por modal e distância |
| **SLA Breach Rate** | Entregas fora do SLA / Total × 100 | Meta: < 2% |

### Eficiência Operacional

| KPI | Fórmula | Benchmark |
|-----|---------|-----------|
| **Custo por Entrega** | Custo total de frete / Nº de entregas | Monitorar por modal e região |
| **Custo por km** | Custo operacional / km rodado | Rodoviário: R$ 4,5–6,5/km (depende do veículo) |
| **Taxa de Ocupação (Load Factor)** | Peso/volume transportado / Capacidade × 100 | Meta: > 80% de ocupação |
| **Carbon per Shipment** | kg CO₂e / remessa | Meta ESG: reduzir 20%/ano |

### Armazém

| KPI | Fórmula | Benchmark |
|-----|---------|-----------|
| **Acuracidade de Inventário** | SKUs sem divergência / Total SKUs × 100 | Meta: > 99.5% |
| **Picking Productivity** | Linhas separadas / Hora/operador | Benchmark: 80-120 linhas/hora (manual) |
| **Order Fill Rate** | Pedidos atendidos completamente / Total × 100 | Meta: > 98% |
| **Dwell Time (Cross-dock)** | Horas entre recebimento e expedição | Meta cross-dock: < 4 horas |

---

## Conformidade e Privacidade

### LGPD em Logistics

- Dados de motoristas (localização GPS, velocidade, comportamento) → dados pessoais
- Dados de destinatários pessoa física (nome, CPF, endereço) → dados pessoais
- Telemetria de veículo associada ao motorista → dado pessoal mesmo sem nome explícito
- **Minimização**: armazenar apenas coordenadas agregadas (por rota) em Gold; dados brutos de GPS apenas em Bronze com retenção limitada

### Regulação Setorial (Brasil)

- **ANTT** — Agência Nacional de Transporte Terrestre: registros obrigatórios de transportadoras
- **CTe** (Conhecimento de Transporte Eletrônico) — documento fiscal obrigatório por remessa
- **MDF-e** (Manifesto de Documentos Fiscais) — declaração de carga por veículo por viagem
- **Cabotagem**: normas ANTAQ para transporte aquaviário de carga

---

## Anti-Padrões Específicos de Logistics

| ID | Anti-padrão | Risco |
|----|-------------|-------|
| LG01 | OTIF calculado considerando data de despacho em vez de data de entrega | HIGH — OTIF superestimado; usar sempre actual_delivery_date |
| LG02 | Telemetria de veículo sem anonimização do motorista em Silver/Gold | HIGH — dado pessoal de localização; pseudonimizar driver_id |
| LG03 | Inventário calculado por saldo acumulado em vez de snapshot diário | HIGH — divergências de contagem cíclica ficam ocultas |
| LG04 | Lead time calculado do ship_date (saída do armazém) em vez do order_date | MEDIUM — subestima o tempo total percebido pelo cliente |
| LG05 | Carbon footprint calculado sem fator de emissão por modal e tipo de combustível | MEDIUM — emissões incorretas para relatório ESG |
| LG06 | Dados de endereço do destinatário PF em tabelas Gold sem mascaramento | CRITICAL — dado pessoal (endereço completo) exposto sem finalidade específica |

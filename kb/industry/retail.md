---
domain: industry
industry: retail
updated_at: 2026-04-30
agents: [catalog-intelligence, business-analyst, data-quality-steward]
---

# Retail — Knowledge Base de Indústria

Referência de casos de uso, schemas típicos, KPIs e padrões de dados para times atuando
em varejo físico, e-commerce, marketplaces e varejo omnichannel.

---

## Casos de Uso de Dados por Objetivo

### Demanda e Estoque

| Caso de Uso | Descrição | Domínios de Dados |
|-------------|-----------|-------------------|
| Demand Forecasting | Previsão de demanda por SKU/loja/canal para reposição de estoque | `sales`, `products`, `calendar`, `promotions`, `external_weather` |
| Stockout Detection | Alertas em tempo real de ruptura de estoque por SKU/loja | `inventory`, `sales_velocity`, `store_capacity` |
| Replenishment Automático | Trigger de pedido ao fornecedor baseado em estoque mínimo + lead time | `inventory`, `purchase_orders`, `suppliers`, `lead_times` |
| Markdown Optimization | Preço ótimo de liquidação para produtos próximos do vencimento/fim de estação | `products`, `inventory`, `price_history`, `demand_elasticity` |

### Clientes e Personalização

| Caso de Uso | Descrição | KPIs Gerados |
|-------------|-----------|--------------|
| Segmentação RFM | Classificar clientes por Recência, Frequência e Valor Monetário | Segmentos: Champions, At Risk, Lost, New |
| Churn de Clientes | Predição de clientes que vão parar de comprar | Churn Rate, Win-back Rate |
| Next Best Product (NBP) | Recomendação de produto no próximo purchase occasion | Click-through Rate, Conversion, AOV |
| Customer Lifetime Value | Valor total esperado do cliente ao longo do relacionamento | LTV, CAC, LTV/CAC Ratio |
| Basket Analysis | Produtos comprados juntos com maior frequência (market basket) | Lift, Support, Confidence |

### Operações e Pricing

| Caso de Uso | Descrição | KPIs Gerados |
|-------------|-----------|--------------|
| Dynamic Pricing | Ajuste automático de preço baseado em demanda, competição e estoque | Margem Bruta %, GMV, Competitiveness Index |
| Shrinkage / Perda | Detecção de diferenças entre estoque contábil e físico (furto, erro) | Shrinkage Rate (%), $ de perda |
| Sell-Through Rate | % do estoque comprado que foi vendido no período | Sell-Through Rate, Estoque Parado (dias) |
| Omnichannel Attribution | Atribuição de conversão entre canais (loja física, app, web) | ROAS, Attribution by Channel, Cross-channel Rate |

---

## Schemas Típicos (Reference Architecture)

```sql
-- Produtos (dimensão central do varejo)
CREATE TABLE gold.dim_products (
  product_id        STRING NOT NULL,
  sku               STRING NOT NULL,
  ean               STRING,                   -- código de barras EAN-13
  product_name      STRING,
  brand             STRING,
  category_l1       STRING,                   -- ex: Eletronicos
  category_l2       STRING,                   -- ex: Smartphones
  category_l3       STRING,                   -- ex: Android
  supplier_id       STRING,
  cost_price        DECIMAL(10,2),
  list_price        DECIMAL(10,2),
  is_active         BOOLEAN,
  PRIMARY KEY (product_id)
);

-- Vendas (fato central)
CREATE TABLE gold.fct_sales (
  sale_id           STRING NOT NULL,
  order_id          STRING NOT NULL,
  customer_id       STRING,                   -- nullable: compras sem cadastro
  product_id        STRING NOT NULL,
  store_id          STRING NOT NULL,
  sale_date         DATE NOT NULL,
  quantity          INT,
  unit_price        DECIMAL(10,2),
  discount_amount   DECIMAL(10,2),
  gross_revenue     DECIMAL(12,2),            -- quantity * unit_price
  net_revenue       DECIMAL(12,2),            -- gross - discount
  cost              DECIMAL(12,2),
  gross_margin      DECIMAL(12,2),            -- net_revenue - cost
  channel           STRING,                   -- STORE | ECOMMERCE | APP | MARKETPLACE | WHATSAPP
  payment_method    STRING,                   -- CREDIT | DEBIT | PIX | BOLETO | VOUCHER
  PRIMARY KEY (sale_id)
)
PARTITIONED BY (sale_date);

-- Estoque (snapshot diário)
CREATE TABLE silver.fct_inventory_snapshot (
  snapshot_date     DATE NOT NULL,
  store_id          STRING NOT NULL,
  product_id        STRING NOT NULL,
  quantity_on_hand  INT,
  quantity_reserved INT,
  quantity_in_transit INT,
  reorder_point     INT,
  days_of_supply    DECIMAL(6,1),             -- estoque / venda média diária
  PRIMARY KEY (snapshot_date, store_id, product_id)
)
PARTITIONED BY (snapshot_date);

-- Clientes
CREATE TABLE gold.dim_customers (
  customer_id       STRING NOT NULL,
  cpf_hash          STRING,                   -- nunca CPF em claro
  first_purchase_date DATE,
  last_purchase_date  DATE,
  total_orders      INT,
  total_revenue     DECIMAL(12,2),
  rfm_segment       STRING,                   -- CHAMPION | LOYAL | AT_RISK | LOST | NEW
  preferred_channel STRING,
  preferred_category STRING,
  PRIMARY KEY (customer_id)
);

-- Promoções
CREATE TABLE gold.dim_promotions (
  promotion_id      STRING NOT NULL,
  promotion_name    STRING,
  promotion_type    STRING,                   -- PERCENT_DISCOUNT | FIXED_DISCOUNT | BOGO | BUNDLE
  start_date        DATE,
  end_date          DATE,
  discount_value    DECIMAL(6,2),
  applies_to        STRING,                   -- ALL | CATEGORY | SKU | CUSTOMER_SEGMENT
  PRIMARY KEY (promotion_id)
);
```

---

## KPIs de Referência

| KPI | Fórmula | Threshold / Benchmark |
|-----|---------|----------------------|
| **GMV** (Gross Merchandise Value) | Soma de `gross_revenue` no período | Crescimento esperado: > inflation |
| **Margem Bruta %** | `(net_revenue - cost) / net_revenue * 100` | Varejo BR: 30–45% (fashion), 15–25% (eletro) |
| **AOV** (Average Order Value) | `GMV / nº de pedidos` | Benchmarking por categoria |
| **Conversion Rate** | Pedidos / Visitantes únicos | E-commerce BR: 1–3% |
| **Churn Rate** | Clientes sem compra em 90 dias / Base ativa | Alerta: > 30% ao ano |
| **LTV** | Receita média por cliente × vida útil estimada | LTV/CAC mínimo: 3x |
| **Sell-Through Rate** | Unidades vendidas / Unidades compradas × 100 | Meta: > 75% na estação |
| **Shrinkage Rate** | (Estoque contábil − Físico) / Estoque contábil | Alerta: > 1.5% |
| **Stockout Rate** | SKUs com ruptura / Total SKUs ativos × 100 | Alerta: > 3% |
| **Days of Supply** | Estoque atual / Venda média diária | Meta: 30–60 dias (categoria-dependente) |
| **ROAS** (Return on Ad Spend) | Receita gerada / Investimento em mídia | Meta: > 4x |
| **NPS** (Net Promoter Score) | % Promotores − % Detratores | Excelente: > 50 |

---

## Padrões de Schema por Setor

### E-commerce / Marketplace

```sql
-- Funil de conversão digital
CREATE TABLE silver.fct_web_events (
  session_id        STRING,
  user_id           STRING,                   -- nullable: sessão anônima
  event_ts          TIMESTAMP NOT NULL,
  event_type        STRING,                   -- PAGE_VIEW | PRODUCT_VIEW | ADD_TO_CART | CHECKOUT | PURCHASE | ABANDON
  product_id        STRING,
  page_url          STRING,
  utm_source        STRING,
  utm_medium        STRING,
  utm_campaign      STRING,
  device_type       STRING                    -- MOBILE | DESKTOP | TABLET
)
PARTITIONED BY (DATE(event_ts));
```

### Varejo Físico (Brick & Mortar)

```sql
-- Loja física
CREATE TABLE gold.dim_stores (
  store_id          STRING NOT NULL,
  store_name        STRING,
  store_type        STRING,                   -- FLAGSHIP | STANDARD | EXPRESS | OUTLET
  region            STRING,
  state             STRING,
  city              STRING,
  square_meters     INT,
  sales_per_sqm     DECIMAL(10,2),            -- produtividade por m²
  cluster           STRING                    -- HIGH_VOLUME | MEDIUM | LOW
);
```

---

## Regras de Qualidade de Dados Críticas

```sql
-- Verificar vendas com margem negativa (possível erro de custo ou fraude)
SELECT product_id, COUNT(*) as negative_margin_sales
FROM gold.fct_sales
WHERE gross_margin < 0
  AND sale_date >= current_date() - 7
GROUP BY product_id
HAVING COUNT(*) > 5;

-- Verificar stockout: produtos sem movimento por mais de X dias
SELECT product_id, store_id, days_of_supply
FROM silver.fct_inventory_snapshot
WHERE snapshot_date = current_date() - 1
  AND days_of_supply = 0
  AND quantity_in_transit = 0
ORDER BY days_of_supply;

-- Reconciliação: GMV por canal deve somar ao total
SELECT
  SUM(gross_revenue)                        AS total_gmv,
  SUM(CASE WHEN channel = 'STORE' THEN gross_revenue END) AS store_gmv,
  SUM(CASE WHEN channel = 'ECOMMERCE' THEN gross_revenue END) AS ecommerce_gmv,
  SUM(CASE WHEN channel = 'APP' THEN gross_revenue END) AS app_gmv
FROM gold.fct_sales
WHERE sale_date = current_date() - 1;
```

---

## Anti-Padrões Específicos de Retail

| ID | Anti-padrão | Risco |
|----|-------------|-------|
| RT01 | GMV calculado sem excluir devoluções e cancelamentos | HIGH — inflação de receita |
| RT02 | Margem calculada com custo desatualizado (sem FIFO/FEFO) | HIGH — margem incorreta |
| RT03 | Estoque snapshot sem tratamento de ajustes de inventário | MEDIUM — ruptura falsa |
| RT04 | Segmentação RFM sem janela temporal explícita | MEDIUM — segmentos instáveis |
| RT05 | Forecast de demanda sem sazonalidade e datas comemorativas | HIGH — ruptura em picos |
| RT06 | Attribution 100% last-click sem modelo multi-touch | MEDIUM — sub-investimento em canais upper-funnel |

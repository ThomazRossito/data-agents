# Star Schema

## Conceitos
- **Tabela Fato**: eventos ou transações mensuráveis (orders, events, clicks). Contém métricas + FKs para dimensões.
- **Tabela Dimensão**: contexto descritivo (clientes, produtos, datas, regiões). Contém attributes + SK como PK.
- **Conforming Dimension**: mesma dimensão usada em múltiplos fatos (dim_date usada por fato_vendas e fato_estoque).

## Exemplo — DDL
```sql
-- Fato
CREATE TABLE fact_orders (
    order_sk        BIGINT GENERATED ALWAYS AS IDENTITY,
    order_nk        STRING NOT NULL,
    customer_sk     BIGINT NOT NULL,
    product_sk      BIGINT NOT NULL,
    date_sk         INT NOT NULL,       -- formato YYYYMMDD
    quantity        INT,
    amount          DECIMAL(18,2),
    _ingestion_ts   TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
USING DELTA
PARTITIONED BY (date_sk);

-- Dimensão
CREATE TABLE dim_product (
    product_sk      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    product_nk      STRING NOT NULL,
    name            STRING,
    category        STRING,
    brand           STRING
)
USING DELTA;

-- Dimensão Tempo (populada uma vez)
CREATE TABLE dim_date (
    date_sk         INT PRIMARY KEY,    -- YYYYMMDD
    full_date       DATE,
    year            INT,
    month           INT,
    quarter         INT,
    week            INT,
    is_weekend      BOOLEAN
)
USING DELTA;
```

## Snowflake Schema — Quando Vale
Snowflake normaliza dimensões em sub-dimensões:
```
dim_product
    └── dim_category
            └── dim_department
```
Útil se: dimensão muito larga com atributos hierárquicos usados separadamente.
Problema: mais joins, mais complexidade em modelos BI.

## Conforming Dimensions
```sql
-- dim_date usada por múltiplos fatos
SELECT f1.amount, f2.quantity, d.month
FROM fact_orders f1
JOIN fact_inventory f2 ON f1.product_sk = f2.product_sk AND f1.date_sk = f2.date_sk
JOIN dim_date d ON f1.date_sk = d.date_sk
WHERE d.year = 2026;
```

## Anti-padrões
| Evite | Prefira |
|-------|---------|
| FK para natural key na fato | FK para surrogate key |
| Métricas na dimensão | Métricas só na fato |
| Dimensão com 100+ colunas | Quebrar em sub-dimensões |
| NULL em métricas de fato | 0 como default ou fato degenerada |

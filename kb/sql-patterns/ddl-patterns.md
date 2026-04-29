# KB: SQL — DDL Patterns

## Tabela Delta Padrão

```sql
CREATE TABLE IF NOT EXISTS catalog.schema.raw_customers (
  customer_id   BIGINT        NOT NULL COMMENT 'PK surrogate',
  source_id     STRING        NOT NULL COMMENT 'ID de origem',
  full_name     STRING        NOT NULL,
  email         STRING                 COMMENT 'PII: email',
  birth_date    DATE,
  is_active_flag BOOLEAN      NOT NULL DEFAULT true,
  created_ts    TIMESTAMP     NOT NULL DEFAULT current_timestamp(),
  updated_ts    TIMESTAMP     NOT NULL DEFAULT current_timestamp()
)
USING DELTA
PARTITIONED BY (CAST(created_ts AS DATE))
TBLPROPERTIES (
  'delta.autoOptimize.optimizeWrite' = 'true',
  'delta.autoOptimize.autoCompact'   = 'true',
  'quality'                          = 'raw',
  'pii'                              = 'true'
)
COMMENT 'Clientes ingeridos do sistema de origem X. PII: email.';
```

## Tags de PII no Unity Catalog

```sql
ALTER TABLE catalog.schema.raw_customers
  ALTER COLUMN email SET TAGS ('pii' = 'true', 'sensitivity' = 'high');
```

## Z-ORDER para queries frequentes

```sql
OPTIMIZE catalog.schema.slv_orders
ZORDER BY (customer_id, order_date);
```

## ANALYZE TABLE

```sql
ANALYZE TABLE catalog.schema.gld_revenue
COMPUTE STATISTICS FOR ALL COLUMNS;
```

## Regras

- `COMMENT` obrigatório em toda tabela com dado sensível
- `TBLPROPERTIES` deve declarar `quality` (raw/bronze/silver/gold)
- `autoOptimize` habilitado em tabelas que recebem escrita incremental
- `PARTITIONED BY` apenas em tabelas > 10M linhas com filtro por data predominante

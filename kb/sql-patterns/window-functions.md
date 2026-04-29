# KB: SQL — Window Functions

## Deduplicação com ROW_NUMBER

```sql
-- Mantém o registro mais recente por chave de negócio
WITH dedup AS (
  SELECT *,
    ROW_NUMBER() OVER (
      PARTITION BY source_id
      ORDER BY updated_ts DESC
    ) AS rn
  FROM catalog.schema.raw_customers
)
SELECT * EXCEPT (rn)
FROM dedup
WHERE rn = 1;
```

## SCD Type 2 com MERGE

```sql
MERGE INTO catalog.schema.slv_customers AS target
USING (
  SELECT
    source_id,
    full_name,
    email,
    current_timestamp() AS valid_from,
    CAST('9999-12-31' AS TIMESTAMP) AS valid_to,
    true AS is_current_flag
  FROM staging
) AS source
ON target.source_id = source.source_id
   AND target.is_current_flag = true
WHEN MATCHED AND (
  target.full_name  <> source.full_name OR
  target.email      <> source.email
) THEN UPDATE SET
  target.valid_to         = current_timestamp(),
  target.is_current_flag  = false
WHEN NOT MATCHED THEN INSERT *;
```

## LAG / LEAD — Delta entre eventos consecutivos

```sql
SELECT
  order_id,
  customer_id,
  order_ts,
  LAG(order_ts) OVER (PARTITION BY customer_id ORDER BY order_ts) AS prev_order_ts,
  DATEDIFF(order_ts, LAG(order_ts) OVER (PARTITION BY customer_id ORDER BY order_ts)) AS days_since_last
FROM catalog.schema.slv_orders;
```

## Running Total

```sql
SELECT
  order_date,
  daily_revenue,
  SUM(daily_revenue) OVER (
    PARTITION BY YEAR(order_date)
    ORDER BY order_date
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  ) AS cumulative_revenue_ytd
FROM catalog.schema.gld_daily_revenue;
```

## Regras

- `ROW_NUMBER()` para deduplicar — nunca `GROUP BY` com `MAX()` em colunas não-numéricas
- Window functions repartem por `PARTITION BY` para evitar shuffle global
- `MERGE` preferível a `INSERT OVERWRITE` para preservar histórico Delta

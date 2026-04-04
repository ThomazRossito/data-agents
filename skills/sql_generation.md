# Skill: Geração de SQL para Databricks e Fabric

## Spark SQL — Criação de Tabela Delta no Unity Catalog

```sql
CREATE TABLE IF NOT EXISTS catalog.schema.tabela_nome (
    id          STRING      NOT NULL COMMENT 'Identificador único',
    data_evento DATE        COMMENT 'Data do evento',
    valor       DOUBLE      COMMENT 'Valor monetário',
    categoria   STRING      COMMENT 'Categoria do produto',
    _ingestion_timestamp TIMESTAMP COMMENT 'Timestamp de ingestão'
)
USING DELTA
PARTITIONED BY (data_evento)
TBLPROPERTIES (
    'delta.autoOptimize.optimizeWrite' = 'true',
    'delta.autoOptimize.autoCompact'   = 'true'
)
COMMENT 'Tabela de vendas processadas';
```

## Spark SQL — OPTIMIZE e Z-ORDER

```sql
-- Compactar small files e indexar por colunas de filtro frequente
OPTIMIZE catalog.schema.tabela_nome
ZORDER BY (categoria, data_evento);

-- Limpar versões antigas (retenção de 7 dias)
VACUUM catalog.schema.tabela_nome RETAIN 168 HOURS;
```

## Spark SQL — CTE com Window Function

```sql
WITH ranked AS (
    SELECT
        id,
        categoria,
        valor,
        data_evento,
        ROW_NUMBER() OVER (
            PARTITION BY categoria
            ORDER BY valor DESC
        ) AS rn
    FROM catalog.schema.tabela_nome
    WHERE data_evento >= DATE_SUB(CURRENT_DATE(), 30)
      AND valor > 0
)
SELECT
    categoria,
    id,
    valor,
    data_evento
FROM ranked
WHERE rn <= 10
ORDER BY categoria, valor DESC;
```

## KQL — Query Eventhouse (Fabric RTI)

```kql
// Últimas 1 hora de eventos, agregados por minuto
eventos
| where ingestion_time() > ago(1h)
| where status == "success"
| summarize
    total = count(),
    valor_medio = avg(valor)
    by bin(Timestamp, 1m), categoria
| order by Timestamp desc
```

## T-SQL — Fabric Synapse (Data Warehouse)

```sql
-- Top 10 produtos por receita no último mês
SELECT TOP 10
    p.nome_produto,
    SUM(v.valor * v.quantidade)     AS receita_total,
    COUNT(DISTINCT v.id_cliente)    AS clientes_unicos
FROM vendas v
INNER JOIN produtos p ON v.id_produto = p.id
WHERE v.data_venda >= DATEADD(MONTH, -1, GETDATE())
GROUP BY p.nome_produto
ORDER BY receita_total DESC;
```

## Conversão T-SQL → Spark SQL

| T-SQL                        | Spark SQL                          |
|------------------------------|------------------------------------|
| TOP N                        | LIMIT N                            |
| GETDATE()                    | CURRENT_TIMESTAMP()                |
| DATEADD(month, -1, d)        | DATE_SUB(d, 30) ou ADD_MONTHS(d,-1)|
| ISNULL(col, 'default')       | COALESCE(col, 'default')           |
| CONVERT(DATE, col)           | CAST(col AS DATE)                  |
| STRING_AGG(col, ',')         | COLLECT_LIST(col) + ARRAY_JOIN     |
| ROW_NUMBER() OVER (...)      | Idêntico em Spark SQL              |

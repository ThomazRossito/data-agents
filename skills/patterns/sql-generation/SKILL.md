---
name: sql-generation
description: "Sintaxe de SQL para Databricks/Unity Catalog (Liquid Clustering com CLUSTER BY), Fabric Synapse (T-SQL), KQL para Eventhouse e tabela de conversão T-SQL→Spark SQL. Use ao gerar DDL ou queries para qualquer das plataformas suportadas."
---

# Skill: Geração de SQL para Databricks e Fabric

<!-- type: concept -->
## Spark SQL — Criação de Tabela Delta no Unity Catalog

```sql
-- PADRÃO MODERNO: Liquid Clustering com CLUSTER BY (Databricks 2024+)
-- Substitui PARTITIONED BY + ZORDER BY (padrões depreciados para tabelas Delta gerenciadas)
CREATE TABLE IF NOT EXISTS catalog.schema.tabela_nome (
    id          STRING      NOT NULL COMMENT 'Identificador único',
    data_evento DATE        COMMENT 'Data do evento',
    valor       DOUBLE      COMMENT 'Valor monetário',
    categoria   STRING      COMMENT 'Categoria do produto',
    _ingestion_timestamp TIMESTAMP COMMENT 'Timestamp de ingestão'
)
USING DELTA
CLUSTER BY (data_evento, categoria)   -- Liquid Clustering: substitui PARTITIONED BY + ZORDER BY
TBLPROPERTIES (
    'delta.autoOptimize.optimizeWrite' = 'true',
    'delta.autoOptimize.autoCompact'   = 'true'
)
COMMENT 'Tabela de vendas processadas';
```

<!-- type: constraint -->
> **Nota:** `PARTITIONED BY` + `ZORDER BY` são padrões legados. Para tabelas Delta novas no
> Unity Catalog, use sempre `CLUSTER BY` (Liquid Clustering). Oferece melhor performance de
> leitura e elimina a necessidade de definir partições estáticas.

<!-- type: pattern -->
## Spark SQL — OPTIMIZE (com Liquid Clustering)

```sql
-- Com Liquid Clustering, o OPTIMIZE reorganiza os dados automaticamente
-- NÃO use ZORDER BY — o CLUSTER BY já gerencia o layout dos arquivos
OPTIMIZE catalog.schema.tabela_nome;

-- Limpar versões antigas (retenção de 7 dias)
VACUUM catalog.schema.tabela_nome RETAIN 168 HOURS;
```

<!-- type: example -->
## Spark SQL — Adicionar Liquid Clustering a Tabela Existente

```sql
-- Migrar tabela legada (com PARTITION BY / ZORDER) para Liquid Clustering
ALTER TABLE catalog.schema.tabela_nome
CLUSTER BY (data_evento, categoria);

-- Após alterar, executar OPTIMIZE para reorganizar os arquivos existentes
OPTIMIZE catalog.schema.tabela_nome;
```

<!-- type: example -->
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

<!-- type: example -->
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

<!-- type: example -->
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

<!-- type: pattern -->
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

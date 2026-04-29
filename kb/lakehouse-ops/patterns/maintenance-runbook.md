# Pattern: Maintenance Runbook

## Schedule de manutenção por camada

| Camada | OPTIMIZE | VACUUM | Z-ORDER |
|---|---|---|---|
| Bronze | Diário (após ingestão) | Semanal (retain 168h) | Nunca (append only) |
| Silver | Diário | Semanal | Mensal (por coluna de filtro frequente) |
| Gold | Após cada rebuild | Quinzenal | Após Z-ORDER de Silver |

## OPTIMIZE — melhores práticas

```python
# Otimizar tabela completa
spark.sql("OPTIMIZE prod.sales_silver.order_curated")

# Otimizar apenas partição recente (mais rápido)
spark.sql("""
    OPTIMIZE prod.sales_silver.order_curated
    WHERE event_date >= current_date() - INTERVAL 7 DAYS
""")

# Verificar antes: quantos arquivos small?
spark.sql("DESCRIBE DETAIL prod.sales_silver.order_curated").select(
    "numFiles", "sizeInBytes"
).show()
```

## VACUUM — seguro vs agressivo

```python
# Verificar quais arquivos seriam removidos (DRY RUN)
spark.sql("VACUUM prod.sales_bronze.order_raw RETAIN 168 HOURS DRY RUN")

# Executar VACUUM (never < 168h em prod)
spark.sql("VACUUM prod.sales_bronze.order_raw RETAIN 168 HOURS")
```

⚠️ Se usar Delta Sharing ou streaming readers, manter retain ≥ 7 dias.

## Z-ORDER — quando e como

```python
# Só Z-ORDER em colunas usadas em filtros frequentes (alto cardinalidade)
spark.sql("""
    OPTIMIZE prod.sales_gold.order_summary
    ZORDER BY (customer_id, order_date)
""")
```

Regra: no máximo 4 colunas em ZORDER. Mais colunas = diminishing returns.

## Compaction automática (Databricks)

```python
# Habilitar auto-compaction na tabela (evita small files)
spark.sql("""
    ALTER TABLE prod.sales_bronze.order_raw
    SET TBLPROPERTIES (
        'delta.autoOptimize.optimizeWrite' = 'true',
        'delta.autoOptimize.autoCompact'   = 'true'
    )
""")
```

## Job de manutenção (DABs task)

```yaml
# Em databricks.yml, adicionar task de manutenção
tasks:
  - task_key: daily_maintenance
    depends_on: []
    notebook_task:
      notebook_path: notebooks/maintenance/optimize_vacuum
    job_cluster_key: maintenance_cluster
    cron_schedule:
      quartz_cron_expression: "0 30 2 * * ?"  # 02:30 todo dia
      timezone_id: "America/Sao_Paulo"
```

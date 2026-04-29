# Lakehouse Ops — Quick Reference

## Comandos Delta essenciais

| Comando | Quando usar | Cuidado |
|---|---|---|
| `VACUUM <table> RETAIN <N> HOURS` | Remover arquivos obsoletos | N ≥ 168h (7 dias) em prod |
| `OPTIMIZE <table>` | Compactar small files (< 128 MB) | Pode levar horas em tabelas grandes |
| `OPTIMIZE <table> ZORDER BY (col)` | Melhorar filtros por coluna | Só usar em colunas de alto cardinalidade com filtros frequentes |
| `DESCRIBE HISTORY <table>` | Ver log de transações | Limite: 30 dias padrão |
| `RESTORE TABLE <table> TO VERSION AS OF <n>` | Rollback | Arquivos devem estar dentro do retention period |

## Thresholds de alerta operacional

| Métrica | Warning | Critical |
|---|---|---|
| Small files por tabela | > 500 | > 2.000 |
| Transaction log entries sem OPTIMIZE | > 1.000 | > 5.000 |
| Tempo de VACUUM | > 30 min | > 2 h |
| Taxa de falha de job | > 5% | > 20% |
| Latência de ingestão vs SLA | > 50% do SLA | > 80% do SLA |

## Runbook de Incidente (triage rápida)

```
1. Identificar: job falhou / dados atrasados / qualidade degradada?
2. Verificar logs: Spark UI → Stage → Task → Exception
3. Identificar causa: OOM / timeout / schema mismatch / permissão?
4. Mitigar: reiniciar / escalar cluster / rollback tabela
5. Resolver: fix código / config / permissão
6. Pós-incidente: ajustar alertas e documentar
```

## Custo — Thresholds Databricks

| Cluster type | DBU/h típico | Quando usar |
|---|---|---|
| Interactive (All-Purpose) | Alto (billing 24/7 se não for auto-terminated) | Dev apenas |
| Job Cluster | Médio (billing por run) | Prod (remover após job) |
| Serverless SQL Warehouse | Por query | Adhoc / BI |
| Serverless Jobs | Por compute-second | Pipelines curtos |

## Custo — Thresholds Fabric

| Item que mais consome CU | Ação |
|---|---|
| Spark jobs longos | Usar cluster pools, otimizar partições |
| Dataflow Gen2 pesado | Prefer Spark notebook para transformações grandes |
| Direct Lake fallback para DirectQuery | Rever tamanho das tabelas |
| Pipelines Copy Activity em alta frequência | Consolidar em batch maior |

## Observabilidade essencial

### Databricks
```python
# Listar tabelas com mais de 1000 arquivos pequenos
spark.sql("""
SELECT table_name, num_files, size_in_bytes / 1e9 as size_gb
FROM (
  SELECT table_name,
         json_tuple(operationParameters, 'numFiles') as num_files,
         json_tuple(operationMetrics, 'numTargetFilesAdded') as files_added
  FROM (DESCRIBE HISTORY prod.sales_bronze.order_raw)
)
""")
```

### Fabric
- Capacity Metrics app (workspace → Admin → Capacity Metrics)
- Monitor tab de cada Lakehouse para item-level CU consumption

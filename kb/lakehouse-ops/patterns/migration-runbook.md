# Pattern: Migration Runbook

## Fases de migração de Lakehouse

### Fase 1 — Inventário (Semana 1)

```python
# Listar todas as tabelas no schema de origem (Databricks)
spark.sql("SHOW TABLES IN source_catalog.source_schema").show(100)

# Para cada tabela: rowcount, schema, format, size
spark.sql("""
    SELECT
        table_name,
        table_type,
        data_source_format,
        created,
        last_altered
    FROM information_schema.tables
    WHERE table_schema = 'source_schema'
""").show(truncate=False)
```

### Fase 2 — Conversão de DDL
- Identificar tipos incompatíveis entre plataformas
- Databricks → Fabric: STRUCT/MAP/ARRAY precisam de conversão se usando Direct Lake
- Synapse → Databricks: `UNIQUEIDENTIFIER` → `STRING`, `DATETIME2` → `TIMESTAMP`
- Validar constraints: Fabric não suporta FK constraints em tabelas Delta

### Fase 3 — Estratégia de cutover

| Estratégia | Quando usar | Risco |
|---|---|---|
| Big Bang | Tabelas < 100GB, janela de manutenção disponível | Alto |
| Incremental (histórico + CDC) | Tabelas > 100GB, zero downtime necessário | Médio |
| Dual Write | Crítico, rollback imediato necessário | Baixo (custo dobrado) |

### Fase 4 — Pipeline de migração

```python
# Template: batch migration com checkpointing
def migrate_table(
    source_table: str,
    target_table: str,
    partition_col: str = "event_date",
    batch_days: int = 30,
) -> None:
    min_date, max_date = spark.sql(
        f"SELECT min({partition_col}), max({partition_col}) FROM {source_table}"
    ).first()

    current = min_date
    while current <= max_date:
        batch_end = current + timedelta(days=batch_days)
        (
            spark.table(source_table)
            .filter(f"{partition_col} >= '{current}' AND {partition_col} < '{batch_end}'")
            .write.format("delta")
            .mode("append")
            .saveAsTable(target_table)
        )
        current = batch_end
        logger.info("Migrated up to %s", batch_end)
```

### Fase 5 — Reconciliação

```python
# Validar contagem por partição
src_count = spark.sql(f"SELECT COUNT(*) FROM {source_table}").first()[0]
tgt_count = spark.sql(f"SELECT COUNT(*) FROM {target_table}").first()[0]

assert src_count == tgt_count, (
    f"Count mismatch: source={src_count}, target={tgt_count}"
)

# Checksum de colunas críticas
spark.sql(f"""
    SELECT
        SUM(amount) as total_amount,
        COUNT(DISTINCT order_id) as distinct_orders
    FROM {source_table}
""").show()
```

### Fase 6 — Cutover
1. Freeze source (read-only mode ou stop ingestão)
2. Executar batch final de reconciliação
3. Atualizar connection strings / catalog references nos jobs downstream
4. Validar Power BI reports / dashboards
5. Monitorar 24h antes de descomissionar source

## Rollback plan
- Manter source table ativa por 30 dias pós-cutover
- Documentar última versão migrada para rollback via RESTORE
- Alertas duplicados em source e target durante período de guardia

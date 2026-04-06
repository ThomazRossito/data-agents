# KB: Padrões Spark — Índice

**Domínio:** Geração e otimização de código PySpark para Databricks e Fabric.
**Agentes:** spark-expert, pipeline-architect

---

## Conteúdo Disponível

| Arquivo                        | Conteúdo                                                                  |
|--------------------------------|---------------------------------------------------------------------------|
| `sdp-lakeflow-rules.md`        | Regras mandatórias para Spark Declarative Pipelines (SDP/LakeFlow)        |
| `streaming-patterns.md`        | Padrões de Spark Structured Streaming e Auto Loader                       |
| `delta-lake-operations.md`     | MERGE, OPTIMIZE, VACUUM, Time Travel, SCD1/SCD2                           |
| `performance-best-practices.md`| Broadcast joins, repartition, cache/persist, UDF avoidance                |

---

## Regras de Negócio Críticas

### API Moderna — Spark Declarative Pipelines
- Use `from pyspark import pipelines as dp`. NUNCA use `import dlt` (API legada).
- Defina expectations via `@dp.expect`, `@dp.expect_or_drop`, `@dp.expect_all`.

### Camadas Medallion
- **Bronze**: SEMPRE use `cloud_files()` (SQL) ou `cloudFiles` (Python) para ingestão via Auto Loader.
- **Silver**: SEMPRE use `STREAMING TABLE` consumindo via `stream()`. NUNCA use `MATERIALIZED VIEW` na Silver.
- **Silver SCD2**: SEMPRE use `AUTO CDC INTO` (SQL) ou `dp.create_auto_cdc_flow()` (Python). NUNCA implemente SCD2 manual com LAG/LEAD/ROW_NUMBER/SHA2.
- **Gold**: Use `MATERIALIZED VIEW` para agregações finais e Star Schema.

### Segurança
- NUNCA hardcode credentials. Use `dbutils.secrets` (Databricks) ou Key Vault (Azure).
- Variáveis de ambiente para qualquer informação sensível.

### Performance
- Prefira DataFrame API sobre RDD API.
- Evite UDFs quando existir função nativa em `pyspark.sql.functions`.
- Use `broadcast()` para joins com tabelas < 100MB.

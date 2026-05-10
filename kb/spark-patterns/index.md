---
mcp_validated: "2026-04-15"
---

# KB: Padrões Spark — Índice

**Domínio:** Geração e otimização de código PySpark para Databricks e Fabric.
**Agentes:** spark-expert, pipeline-architect

---

## Conteúdo Disponível

### Conceitos (`concepts/`)

| Arquivo                              | Conteúdo                                                              |
|--------------------------------------|-----------------------------------------------------------------------|
| `concepts/sdp-rules.md`              | Regras mandatórias SDP/LakeFlow: API moderna, expectations, camadas  |
| `concepts/streaming-concepts.md`     | Structured Streaming: triggers, checkpoints, watermark — conceitos   |
| `concepts/delta-lake-concepts.md`    | Delta: ACID, Time Travel, SCD1/SCD2, liquid clustering               |
| `concepts/performance-concepts.md`   | Broadcast, repartition, cache, UDF avoidance — quando e por quê      |

### Padrões (`patterns/`)

| Arquivo                              | Conteúdo                                                              |
|--------------------------------------|-----------------------------------------------------------------------|
| `patterns/lakeflow-patterns.md`      | Python SDP completo: Bronze/Silver/Gold, expectations, CDC           |
| `patterns/streaming-patterns.md`     | Auto Loader Python/SQL, Structured Streaming, Delta Live Tables      |
| `patterns/delta-lake-patterns.md`    | MERGE SQL, OPTIMIZE+VACUUM, Time Travel queries, SCD2 completo       |
| `patterns/performance-patterns.md`   | Broadcast SQL, repartition Python, AQE config, UDF → built-in       |

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

# KB: Databricks — Índice

**Domínio:** Arquitetura, padrões e boas práticas da plataforma Databricks.
**Agentes:** pipeline-architect, sql-expert, spark-expert

---

## Conteúdo Disponível

| Arquivo                        | Conteúdo                                                                  |
|--------------------------------|---------------------------------------------------------------------------|
| `unity-catalog-rules.md`       | Hierarquia Catalog→Schema→Table, grants, volumes e lineage                |
| `compute-patterns.md`          | Clusters, SQL Warehouses, Serverless e seleção de compute                 |
| `jobs-workflows-patterns.md`   | Jobs multi-task, Workflows, dependências e retry policies                 |
| `bundles-cicd.md`              | Asset Bundles, CI/CD e deployment patterns                                |
| `ai-ml-patterns.md`            | MLflow, Model Serving, Vector Search, AI Functions                        |

---

## Regras de Negócio Críticas

### Unity Catalog
- Hierarquia obrigatória: `catalog.schema.table` (three-level namespace).
- NUNCA crie tabelas sem catalog explícito (evita uso do `hive_metastore` legado).
- Use `GRANT` e `REVOKE` para controle de acesso granular por grupo.
- Volumes são o padrão para armazenamento de arquivos não-tabulares.
- System Tables (`system.access`, `system.lineage`) são a fonte de verdade para auditoria.

### Compute
- Prefira Serverless para SQL Warehouses (menor latência de startup, custo por query).
- Use Job Clusters (não Interactive Clusters) para pipelines de produção.
- Nunca inicie clusters maiores que `Standard_DS3_v2` sem aprovação do Supervisor.
- Configure auto-termination em todos os clusters interativos.

### Jobs e Workflows
- Jobs multi-task devem ter retry policy configurada (mínimo 1 retry com exponential backoff).
- Sempre configure alertas de falha por email ou webhook.
- Use `run_job_now` com `idempotency_token` para evitar execuções duplicadas.

### API Moderna — Spark Declarative Pipelines
- Use `from pyspark import pipelines as dp` (SDP/LakeFlow). NUNCA `import dlt`.
- Pipelines SDP são preferidos sobre Jobs Spark para pipelines de dados contínuos.
- Use `CLUSTER BY` em tabelas Delta (nunca `ZORDER BY` em tabelas novas).

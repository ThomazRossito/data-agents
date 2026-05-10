---
mcp_validated: "2026-04-15"
---

# KB: Design de Pipelines — Índice

**Domínio:** Arquitetura e padrões de pipelines ETL/ELT cross-platform.
**Agentes:** pipeline-architect, spark-expert

---

## Conteúdo Disponível

### Conceitos (`concepts/`)

| Arquivo                                | Conteúdo                                                              |
|----------------------------------------|-----------------------------------------------------------------------|
| `concepts/medallion-concepts.md`       | Bronze/Silver/Gold — definições, regras, quando usar cada camada     |
| `concepts/cross-platform-concepts.md`  | Estratégias Fabric ↔ Databricks, critérios de decisão               |

### Padrões (`patterns/`)

| Arquivo                                        | Conteúdo                                                           |
|------------------------------------------------|--------------------------------------------------------------------|
| `patterns/medallion-patterns.md`               | SQL Bronze/Silver/Gold completos, Auto Loader, SCD2, Golds        |
| `patterns/cross-platform-patterns.md`          | ABFSS setup, Shortcuts API, Export/Upload Python, Data Factory    |
| `patterns/star-schema-cross-reference.md`      | Pipeline DAG e validação — **canonical em** `kb/sql-patterns/concepts/star-schema-source-of-truth.md` |
| `patterns/orchestration-databricks.md`         | Jobs multi-task YAML, run_if, SDK monitoring                      |
| `patterns/orchestration-fabric.md`             | Fabric Data Pipelines JSON, round-trip orchestration              |
| `patterns/orchestration-cross-platform.md`     | DABs multi-env, Data Factory cross-cloud, DABs vs Fabric tabela   |

---

## Regras de Negócio Críticas

### Arquitetura Medallion Moderna
- **Bronze**: Ingestão raw via Auto Loader (`cloud_files`). NUNCA transforme na Bronze.
- **Silver**: Limpeza, tipagem e SCD2 via `AUTO CDC`. NUNCA use `MATERIALIZED VIEW` na Silver.
- **Gold**: Agregações e Star Schema via `MATERIALIZED VIEW`. Use `CLUSTER BY`.

### Star Schema — Regras Invioláveis
- `dim_*` são entidades independentes. NUNCA derivam de silver transacional.
- `dim_data` é gerada sinteticamente via `SEQUENCE(...)` + `EXPLODE`. NUNCA via `SELECT DISTINCT`.
- `fact_*` faz `INNER JOIN` com TODAS as dimensões. NUNCA apenas `FROM silver_vendas`.
- O DAG deve ser: `silver_entidade → dim_entidade → fact_*`.

### Cross-Platform (Fabric ↔ Databricks)
- Estratégia preferida: ABFSS paths compartilhados (mesma storage account).
- Alternativa: OneLake Shortcuts para acesso direto sem movimentação de dados.
- Fallback: export/upload via OneLake API para casos sem storage compartilhado.

### DABs — Declarative Automation Bundles

> **Atenção:** a partir de 2024 o acrônimo DAB continua o mesmo, mas o nome completo mudou de
> _Databricks Asset Bundles_ → **Declarative Automation Bundles** (CLI v0.279.0+).

**O que mudou no CLI v0.279.0:**

- **Engine de deployment direto**: o Databricks CLI deixou de depender do Terraform para implantar bundles. A geração de planos Terraform ainda é suportada como fallback, mas o modo padrão agora é o engine nativo.
- **Novo comando de migração**: `databricks bundle migrate` converte projetos que usavam o provider Terraform (`databricks/databricks`) para o formato nativo — sem reescrita manual.
- **Diff de deployment**: `databricks bundle plan -o json` gera saída estruturada para revisão em CI/CD (ex: GitHub Actions, Azure DevOps).

**Fluxo de trabalho recomendado:**

```bash
# Validar bundle antes de implantar
databricks bundle validate

# Ver diff do que será aplicado (JSON estruturado para CI)
databricks bundle plan -o json

# Implantar sem Terraform
databricks bundle deploy

# Migrar projetos legados (Terraform → engine nativo)
databricks bundle migrate
```

**Quando usar DABs vs Data Factory / Fabric Pipelines:**

| Cenário | Ferramenta recomendada |
|---|---|
| Jobs Databricks com múltiplas tasks, dependências e parâmetros | DABs |
| Orquestração cross-platform (Fabric + Databricks) | Data Factory / Fabric Data Pipelines |
| Streaming contínuo com triggers automáticos | Databricks Workflows + Auto Loader |
| Deploy de notebooks + jobs como código versionado | DABs com `databricks bundle deploy` |

### Validação Obrigatória pós-Pipeline
- Sempre execute `SELECT count(*) FROM tabela_destino` após carga.
- Verifique lineage via `mcp__fabric_community__get_lineage` para pipelines Fabric.
- Para Databricks, monitore via `list_job_runs` até status `SUCCEEDED`.

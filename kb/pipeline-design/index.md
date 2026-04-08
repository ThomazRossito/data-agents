# KB: Design de Pipelines — Índice

**Domínio:** Arquitetura e padrões de pipelines ETL/ELT cross-platform.
**Agentes:** pipeline-architect, spark-expert

---

## Conteúdo Disponível

| Arquivo                        | Conteúdo                                                                  |
|--------------------------------|---------------------------------------------------------------------------|
| `medallion-architecture.md`    | Padrões Bronze→Silver→Gold para Databricks e Fabric                       |
| `cross-platform-patterns.md`   | Estratégias de movimentação Fabric ↔ Databricks                           |
| `star-schema-design.md`        | Regras de Star Schema: dim_*, fact_*, dim_data, INNER JOINs               |
| `orchestration-patterns.md`    | Padrões de orquestração: Jobs, Workflows, Data Factory                    |

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

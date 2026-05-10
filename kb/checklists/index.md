---
domain: checklists
updated_at: 2026-04-30
agents: [pipeline-architect, spark-expert, sql-expert, migration-expert, semantic-modeler, business-analyst]
---

# Checklists — Índice de Definition of Done

Critérios de aceite por tipo de artefato. Leia o checklist correspondente antes de declarar
uma entrega concluída.

| Checklist | Arquivo | Aplica a |
|-----------|---------|----------|
| **Pipeline ETL/ELT** | `kb/checklists/pipeline-dod.md` | Pipelines Bronze→Silver→Gold, DLT, ADF |
| **Migração** | `kb/checklists/migration-dod.md` | SQL Server / PostgreSQL → Databricks / Fabric |
| **Modelo Semântico** | `kb/checklists/semantic-dod.md` | Star Schema, DAX, Direct Lake, Genie Spaces |

## Níveis de Severidade

- **Nível 1 — Obrigatório**: bloqueia entrega. Nenhum item pode ser pulado.
- **Nível 2 — Recomendado**: deve ser justificado se ausente.
- **Nível 3 — Pipelines Críticos**: exigido apenas para workloads de produção com SLA.

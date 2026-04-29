# KB: Orchestration

## Domínio
Orquestração de pipelines: Apache Airflow, Databricks Workflows, Microsoft Fabric Pipelines. Decisão entre orquestradores, padrões de DAGs, retry, dependências.

## Quando Consultar
- Escolher entre Airflow / Databricks Workflows / Fabric Pipelines
- Criar DAG Airflow para pipeline Databricks
- Configurar job com `depends_on` no Databricks Workflows
- Monitorar e fazer repair_run
- Padrão de fan-out / fan-in

## Arquivos de Referência Rápida
| Recurso | Arquivo |
|---------|---------|
| Comparativo orquestradores | [quick-reference.md](quick-reference.md) |
| Databricks Workflows | [patterns/databricks-workflows.md](patterns/databricks-workflows.md) |
| Airflow Patterns | [patterns/airflow-patterns.md](patterns/airflow-patterns.md) |
| Decision spec | [specs/orchestration-decision.yaml](specs/orchestration-decision.yaml) |

## Agentes Relacionados
- `pipeline_architect` — agente primário para deploy
- `spark_expert` — código dos jobs/tasks
- `devops_engineer` — CI/CD dos pipelines

## Última Atualização
2026-04-25

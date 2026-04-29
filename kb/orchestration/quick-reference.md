# Orchestration Quick Reference

## Comparativo de Orquestradores
| Critério | Airflow | Databricks Workflows | Fabric Pipelines |
|----------|---------|---------------------|-----------------|
| **Plataforma** | Self-managed / MWAA | Nativo Databricks | Nativo Fabric |
| **Código** | Python (DAG) | YAML/JSON (bundle) | GUI + YAML |
| **Scheduler** | Cron + sensors | Cron + events | Cron + triggers |
| **Integração Databricks** | DatabricksSubmitRunOperator | Native | Via connector |
| **Integração Fabric** | REST API | Limitada | Native |
| **Complexidade Infra** | Alta (cluster, workers) | Zero (serverless scheduler) | Zero |
| **Custo** | Infra própria | Incluído no workspace | Fabric CU |
| **Dependency mgmt** | Avançado (upstream/downstream) | `depends_on` por task | Atividades em série/paralelo |
| **Observability** | Grafana + Prometheus externo | Databricks Workflows UI | Fabric Monitoring Hub |
| **Multi-cloud** | ✓ Sim | ✗ Databricks only | ✗ Fabric only |

## Decisão Rápida
- **Databricks apenas** → Databricks Workflows
- **Fabric apenas** → Fabric Pipelines
- **Multi-plataforma / legacy** → Airflow
- **Cross-cloud ou fora Azure** → Airflow

## Padrão de Execução — Airflow
```python
# Topologia linear (mais comum)
task_a >> task_b >> task_c

# Fan-out / Fan-in
task_a >> [task_b, task_c] >> task_d
```

## Padrão de Execução — Databricks Workflows
```yaml
tasks:
  - task_key: ingest
  - task_key: transform
    depends_on: [{task_key: ingest}]
  - task_key: quality_check
    depends_on: [{task_key: transform}]
```

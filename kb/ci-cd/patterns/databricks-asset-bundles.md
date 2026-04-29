# Databricks Asset Bundles (DABs)

## O que são DABs
Asset Bundles são a forma oficial do Databricks de versionar e deployar jobs, pipelines, notebooks e outros recursos como Infrastructure as Code.

## Estrutura do Bundle
```
project/
├── databricks.yml          ← config principal
├── resources/
│   ├── jobs.yml            ← definição de jobs
│   └── pipelines.yml       ← definição de DLT pipelines
├── src/
│   └── pipeline.py         ← código PySpark
└── .databricks/
    └── bundle/             ← state (não commitar)
```

## databricks.yml Mínimo
```yaml
bundle:
  name: my-pipeline

workspace:
  host: ${var.databricks_host}

variables:
  databricks_host:
    description: "Databricks workspace URL"

targets:
  dev:
    mode: development
    default: true
    workspace:
      host: https://dev-workspace.azuredatabricks.net
  
  prod:
    mode: production
    workspace:
      host: https://prod-workspace.azuredatabricks.net
    run_as:
      service_principal_name: svc-databricks-prod@tenant.com

resources:
  jobs:
    ingest_bronze:
      name: "[${bundle.target}] Ingest Bronze Orders"
      job_clusters:
        - job_cluster_key: main
          new_cluster:
            spark_version: "14.3.x-scala2.12"
            node_type_id: "Standard_DS3_v2"
            num_workers: 4
      tasks:
        - task_key: run_pipeline
          job_cluster_key: main
          python_file: src/pipeline.py
```

## Targets — dev vs prod
| | dev | prod |
|--|-----|------|
| mode | development | production |
| Prefix no nome | `[dev] ` | sem prefix |
| Run as | usuário atual | service principal |
| Cluster | auto-menor | conforme config |

## Validate + Deploy + Run
```bash
# Validar (sem afetar Databricks)
databricks bundle validate

# Deploy recursos
databricks bundle deploy -t dev

# Executar job após deploy
databricks bundle run ingest_bronze -t dev

# Deploy em prod (CI/CD)
databricks bundle deploy -t prod --auto-approve
```

## Resources Suportados
- `jobs` (Jobs com tasks)
- `pipelines` (DLT / LakeFlow)
- `clusters` (cluster definitions reutilizáveis)
- `dashboards` (AI/BI dashboards)
- `alerts` (SQL alerts)
- `experiments` (MLflow)
- `model_serving_endpoints`

---
name: databricks-jobs
updated_at: 2026-04-23
source: web_search
---

# Databricks Lakeflow Jobs

> ⚠️ **Breaking change — renomeação DABs (CLI ≥ 0.266.0):** "Databricks Asset Bundles" foi oficialmente renomeado para **Declarative Automation Bundles (DABs)**. Documentação, comandos e templates usam o novo nome. Os comandos `databricks bundle *` **não mudam**, mas referências a "Asset Bundles" em docs e mensagens de erro podem aparecer com o novo nome. Atualize pipelines de CI/CD e links internos de documentação.

> ⚠️ **Breaking change — resolução de caminhos relativos (CLI ≥ 0.266.0):** O mecanismo de fallback para resolução de caminhos relativos entre arquivos de configuração foi removido. Caminhos devem ser relativos ao arquivo onde são definidos. Versões `0.252–0.265` emitem `Warn`; `≥ 0.266` falham em deploy.

## Overview

Databricks Jobs orchestrate data workflows with multi-task DAGs, flexible triggers, and comprehensive monitoring. Jobs support diverse task types and can be managed via Python SDK, CLI, or Declarative Automation Bundles (formerly Asset Bundles).

## Reference Files

| Use Case | Reference File |
|----------|----------------|
| Configure task types (notebook, Python, SQL, dbt, etc.) | [task-types.md](task-types.md) |
| Set up triggers and schedules | [triggers-schedules.md](triggers-schedules.md) |
| Configure notifications and health monitoring | [notifications-monitoring.md](notifications-monitoring.md) |
| Complete working examples | [examples.md](examples.md) |

## Quick Start

### Python SDK

```python
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.jobs import Task, NotebookTask, Source

w = WorkspaceClient()

job = w.jobs.create(
    name="my-etl-job",
    tasks=[
        Task(
            task_key="extract",
            notebook_task=NotebookTask(
                notebook_path="/Workspace/Users/user@example.com/extract",
                source=Source.WORKSPACE
            )
        )
    ]
)
print(f"Created job: {job.job_id}")
```

### CLI

```bash
databricks jobs create --json '{
  "name": "my-etl-job",
  "tasks": [{
    "task_key": "extract",
    "notebook_task": {
      "notebook_path": "/Workspace/Users/user@example.com/extract",
      "source": "WORKSPACE"
    }
  }]
}'
```

### Declarative Automation Bundles (DABs)

> Formerly known as Databricks Asset Bundles. Commands (`databricks bundle *`) não mudam.

```yaml
# resources/jobs.yml
resources:
  jobs:
    my_etl_job:
      name: "[${bundle.target}] My ETL Job"
      tasks:
        - task_key: extract
          notebook_task:
            notebook_path: ../src/notebooks/extract.py
```

## Core Concepts

### Multi-Task Workflows

Jobs support DAG-based task dependencies:

```yaml
tasks:
  - task_key: extract
    notebook_task:
      notebook_path: ../src/extract.py

  - task_key: transform
    depends_on:
      - task_key: extract
    notebook_task:
      notebook_path: ../src/transform.py

  - task_key: load
    depends_on:
      - task_key: transform
    run_if: ALL_SUCCESS  # Only run if all dependencies succeed
    notebook_task:
      notebook_path: ../src/load.py
```

**run_if conditions:**
- `ALL_SUCCESS` (default) - Run when all dependencies succeed
- `ALL_DONE` - Run when all dependencies complete (success or failure)
- `AT_LEAST_ONE_SUCCESS` - Run when at least one dependency succeeds
- `NONE_FAILED` - Run when no dependencies failed
- `ALL_FAILED` - Run when all dependencies failed
- `AT_LEAST_ONE_FAILED` - Run when at least one dependency failed

### Task Types Summary

> ⚠️ **Novo task type — `alert_task` (Beta/Preview):** Adicionado ao SDK Python (`databricks.sdk.service.jobs.Task`) e à Jobs API. Permite executar um Databricks SQL Alert como parte de um job, integrando monitoramento baseado em alertas ao pipeline. Requer workspace admin habilitando o preview e um SQL warehouse serverless ou pro. O SQL alert task **não suporta parâmetros customizados**.

| Task Type | Use Case | Reference |
|-----------|----------|-----------|
| `notebook_task` | Run notebooks | [task-types.md#notebook-task](task-types.md#notebook-task) |
| `spark_python_task` | Run Python scripts | [task-types.md#spark-python-task](task-types.md#spark-python-task) |
| `python_wheel_task` | Run Python wheels | [task-types.md#python-wheel-task](task-types.md#python-wheel-task) |
| `sql_task` | Run SQL queries/files/alerts | [task-types.md#sql-task](task-types.md#sql-task) |
| `alert_task` | Run SQL Alert as job task (Beta) | [task-types.md#alert-task](task-types.md#alert-task) |
| `dbt_task` | Run dbt projects | [task-types.md#dbt-task](task-types.md#dbt-task) |
| `pipeline_task` | Trigger DLT/SDP pipelines | [task-types.md#pipeline-task](task-types.md#pipeline-task) |
| `spark_jar_task` | Run Spark JARs | [task-types.md#spark-jar-task](task-types.md#spark-jar-task) |
| `run_job_task` | Trigger other jobs | [task-types.md#run-job-task](task-types.md#run-job-task) |
| `for_each_task` | Loop over inputs | [task-types.md#for-each-task](task-types.md#for-each-task) |

### Trigger Types Summary

| Trigger Type | Use Case | Reference |
|--------------|----------|-----------|
| `schedule` | Cron-based scheduling | [triggers-schedules.md#cron-schedule](triggers-schedules.md#cron-schedule) |
| `trigger.periodic` | Interval-based | [triggers-schedules.md#periodic-trigger](triggers-schedules.md#periodic-trigger) |
| `trigger.file_arrival` | File arrival events (GA) | [triggers-schedules.md#file-arrival-trigger](triggers-schedules.md#file-arrival-trigger) |
| `trigger.table_update` | Table change events | [triggers-schedules.md#table-update-trigger](triggers-schedules.md#table-update-trigger) |
| `continuous` | Always-running jobs | [triggers-schedules.md#continuous-jobs](triggers-schedules.md#continuous-jobs) |

> **Nota:** File arrival trigger com file events passou a GA em 2025. Use `trigger.file_arrival` com `file_events` para melhor performance em external locations.

## Compute Configuration

### Job Clusters (Recommended)

> ⚠️ **Runtime atualizado:** O LTS atual é `16.4.x-scala2.12` (Apache Spark 3.5.2). Atualize jobs que ainda usam `15.4.x` (ainda suportado, mas não é o LTS mais recente).

Define reusable cluster configurations:

```yaml
job_clusters:
  - job_cluster_key: shared_cluster
    new_cluster:
      spark_version: "16.4.x-scala2.12"   # LTS atual — era 15.4.x
      node_type_id: "i3.xlarge"
      num_workers: 2
      spark_conf:
        spark.speculation: "true"

tasks:
  - task_key: my_task
    job_cluster_key: shared_cluster
    notebook_task:
      notebook_path: ../src/notebook.py
```

### Autoscaling Clusters

```yaml
new_cluster:
  spark_version: "16.4.x-scala2.12"   # LTS atual
  node_type_id: "i3.xlarge"
  autoscale:
    min_workers: 2
    max_workers: 8
```

### Existing Cluster

```yaml
tasks:
  - task_key: my_task
    existing_cluster_id: "0123-456789-abcdef12"
    notebook_task:
      notebook_path: ../src/notebook.py
```

### Serverless Compute

Para notebook e Python tasks, omita a configuração de cluster para usar serverless. Para Python script, Python wheel e dbt tasks, `environment_key` é obrigatório:

```yaml
tasks:
  - task_key: serverless_notebook
    notebook_task:
      notebook_path: ../src/notebook.py
    # No cluster config = serverless

  - task_key: serverless_python
    spark_python_task:
      python_file: ../src/main.py
    environment_key: default   # Obrigatório para Python/wheel/dbt no serverless

environments:
  - environment_key: default
    spec:
      environment_version: "2"
      dependencies:
        - my-library
```

## Job Parameters

### Define Parameters

```yaml
parameters:
  - name: env
    default: "dev"
  - name: date
    default: "{{start_date}}"  # Dynamic value reference
```

### Access in Notebook

```python
# In notebook
dbutils.widgets.get("env")
dbutils.widgets.get("date")
```

### Pass to Tasks

```yaml
tasks:
  - task_key: my_task
    notebook_task:
      notebook_path: ../src/notebook.py
      base_parameters:
        env: "{{job.parameters.env}}"
        custom_param: "value"
```

## Common Operations

### Python SDK Operations

> ⚠️ **Depreciação — `sql_params` no `run_now`:** O campo `sql_params` está depreciado. Use `job_parameters` para passar informações a tasks. O SQL alert task não suporta parâmetros customizados.

```python
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

# List jobs
jobs = w.jobs.list(expand_tasks=False)  # expand_tasks controla nível de detalhe

# Get job details
job = w.jobs.get(job_id=12345)

# Run job now
run = w.jobs.run_now(job_id=12345)

# Run with parameters (use job_parameters, não sql_params — depreciado)
run = w.jobs.run_now(
    job_id=12345,
    job_parameters={"env": "prod", "date": "2024-01-15"}
)

# Cancel run
w.jobs.cancel_run(run_id=run.run_id)

# Cancel all active runs of a job
w.jobs.cancel_all_runs(job_id=12345)  # all_queued_runs=True para cancelar fila

# Delete job
w.jobs.delete(job_id=12345)
```

### CLI Operations

```bash
# List jobs
databricks jobs list

# Get job details
databricks jobs get 12345

# Run job
databricks jobs run-now 12345

# Run with parameters
databricks jobs run-now 12345 --job-params '{"env": "prod"}'

# Cancel run
databricks jobs cancel-run 67890

# Delete job
databricks jobs delete 12345
```

### Declarative Automation Bundles Operations

```bash
# Validate configuration
databricks bundle validate

# Deploy job
databricks bundle deploy

# Run job
databricks bundle run my_job_resource_key

# Deploy to specific target
databricks bundle deploy -t prod

# Generate YAML from existing resource
databricks bundle generate --existing-job-id 12345

# Destroy resources
databricks bundle destroy
```

> **Dica:** Use `databricks bundle generate` para criar YAML a partir de jobs existentes criados via UI ou API, facilitando a migração para DABs.

## Declarative Automation Bundles — Novidades

### Python para DABs (GA)

Além de YAML, jobs podem ser definidos como código Python, permitindo geração dinâmica de jobs com metadados e modificação de jobs definidos em YAML durante o deploy:

```python
# databricks.yml continua como ponto de entrada
# Recursos podem ser definidos/modificados via Python
```

Consulte a documentação em [Bundle configuration in Python](https://docs.databricks.com/en/dev-tools/bundles/python.html).

### DABs no Workspace (GA)

É possível colaborar em bundles diretamente pelo workspace UI — editar, commitar, testar e fazer deploy sem CLI local.

### Preset `artifacts_dynamic_version`

Novo preset para atualizar automaticamente a versão de artefatos `.whl` durante o deploy:

```yaml
bundle:
  deployment:
    artifacts_dynamic_version: true
```

## Permissions (DABs)

```yaml
resources:
  jobs:
    my_job:
      name: "My Job"
      permissions:
        - level: CAN_VIEW
          group_name: "data-analysts"
        - level: CAN_MANAGE_RUN
          group_name: "data-engineers"
        - level: CAN_MANAGE
          user_name: "admin@example.com"
```

**Permission levels:**
- `CAN_VIEW` - View job and run history
- `CAN_MANAGE_RUN` - View, trigger, and cancel runs
- `CAN_MANAGE` - Full control including edit and delete

## Common Issues

| Issue | Solution |
|-------|----------|
| Job cluster startup slow | Use job clusters with `job_cluster_key` for reuse across tasks |
| Task dependencies not working | Verify `task_key` references match exactly in `depends_on` |
| Schedule not triggering | Check `pause_status: UNPAUSED` and valid timezone |
| File arrival not detecting | Ensure path has proper permissions and uses cloud storage URL |
| Table update trigger missing events | Verify Unity Catalog table and proper grants |
| Parameter not accessible | Use `dbutils.widgets.get()` in notebooks |
| "admins" group error | Cannot modify admins permissions on jobs |
| Serverless task fails | Ensure task type supports serverless; para Python/wheel/dbt use `environment_key` |
| Path resolution error (CLI ≥ 0.266) | Corrija caminhos para serem relativos ao arquivo onde são definidos |
| `sql_params` deprecation warning | Migre para `job_parameters` em `run_now` |
| `alert_task` not available | Habilite o preview via workspace admin settings |

## Lakeflow System Tables — Novas Colunas (Dez/2025)

A tabela `jobs` do system catalog ganhou novas colunas para monitoramento avançado:

- `trigger`, `trigger_type` — tipo e configuração do trigger
- `run_as_user_name`, `creator_user_name` — identidades
- `paused`, `timeout_seconds`, `health_rules`, `deployment`

> Colunas não são populadas para linhas emitidas antes de dezembro de 2025.

## Related Skills

- **[databricks-bundles](../databricks-bundles/SKILL.md)** - Deploy jobs via Declarative Automation Bundles
- **[databricks-spark-declarative-pipelines](../databricks-spark-declarative-pipelines/SKILL.md)** - Configure pipelines triggered by jobs

## Resources

- [Jobs API Reference](https://docs.databricks.com/api/workspace/jobs)
- [Jobs Documentation](https://docs.databricks.com/en/jobs/index.html)
- [DABs Job Task Types](https://docs.databricks.com/en/dev-tools/bundles/job-task-types.html)
- [Declarative Automation Bundles (formerly DABs)](https://docs.databricks.com/en/dev-tools/bundles/index.html)
- [Bundle Configuration in Python (GA)](https://docs.databricks.com/en/dev-tools/bundles/python.html)
- [SQL Alert Task for Jobs](https://docs.databricks.com/en/jobs/alert.html)
- [Bundle Examples Repository](https://github.com/databricks/bundle-examples)
- [Databricks Runtime 16.4 LTS Release Notes](https://docs.databricks.com/en/release-notes/runtime/16.4lts.html)

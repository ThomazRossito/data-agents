# Databricks Workflows

## Job com Múltiplas Tasks
```yaml
# resources/jobs.yml (Asset Bundle)
resources:
  jobs:
    medallion_pipeline:
      name: "[${bundle.target}] Medallion Pipeline"
      
      job_clusters:
        - job_cluster_key: bronze_cluster
          new_cluster:
            spark_version: "14.3.x-scala2.12"
            node_type_id: "Standard_DS3_v2"
            num_workers: 2
      
      tasks:
        - task_key: ingest_bronze
          job_cluster_key: bronze_cluster
          python_file: src/bronze/ingest.py
          parameters:
            - name: "--date"
              value: "{{job.run_date}}"

        - task_key: transform_silver
          depends_on:
            - task_key: ingest_bronze
          job_cluster_key: bronze_cluster
          python_file: src/silver/transform.py

        - task_key: quality_check
          depends_on:
            - task_key: transform_silver
          job_cluster_key: bronze_cluster
          python_file: src/quality/check.py

        - task_key: gold_aggregate
          depends_on:
            - task_key: quality_check
          job_cluster_key: bronze_cluster
          python_file: src/gold/aggregate.py

      schedule:
        quartz_cron_expression: "0 0 6 * * ?"
        timezone_id: "America/Sao_Paulo"
        pause_status: UNPAUSED

      email_notifications:
        on_failure:
          - team-data@company.com
```

## Task Dependencies — Padrões
```yaml
# Fan-out: 1 → muitos
- task_key: bronze
- task_key: silver_a
  depends_on: [{task_key: bronze}]
- task_key: silver_b
  depends_on: [{task_key: bronze}]

# Fan-in: muitos → 1
- task_key: gold
  depends_on:
    - task_key: silver_a
    - task_key: silver_b
```

## Repair Run (Re-executar task com falha)
```bash
# Via CLI
databricks runs repair --run-id 12345 --rerun-tasks quality_check

# Via API
POST /api/2.1/jobs/runs/repair
{
  "run_id": 12345,
  "rerun_tasks": ["quality_check"]
}
```

## Parâmetros Dinâmicos (Job Parameters)
```yaml
tasks:
  - task_key: ingest
    python_file: src/ingest.py
    parameters:
      - name: "--env"
        value: "{{bundle.target}}"
      - name: "--date"
        value: "{{job.run_date}}"
      - name: "--source"
        value: "${var.source_path}"
```

## Webhook Notifications
```yaml
webhook_notifications:
  on_success:
    - id: "webhook-uuid-here"
  on_failure:
    - id: "webhook-uuid-here"
```

## Monitoramento
- Workflows UI → All Runs → filtro por job/status
- `databricks runs list --job-id <id>` — via CLI
- Databricks SQL: `SELECT * FROM system.workflow.run_timeline WHERE job_id = <id>`

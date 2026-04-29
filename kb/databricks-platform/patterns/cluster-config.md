# Cluster Config

## Job Cluster vs Interactive vs Serverless

### Job Cluster (Recomendado para Produção)
```json
{
  "job_cluster_key": "main_cluster",
  "new_cluster": {
    "spark_version": "14.3.x-scala2.12",
    "node_type_id": "Standard_DS3_v2",
    "num_workers": 4,
    "autoscale": {
      "min_workers": 2,
      "max_workers": 8
    },
    "spark_conf": {
      "spark.sql.adaptive.enabled": "true",
      "spark.databricks.delta.optimizeWrite.enabled": "true"
    },
    "init_scripts": [
      {"workspace": {"destination": "/Shared/init/install_libs.sh"}}
    ]
  }
}
```

### Interactive Cluster
```json
{
  "cluster_name": "dev-exploracao",
  "spark_version": "14.3.x-scala2.12",
  "node_type_id": "Standard_DS3_v2",
  "autoscale": {"min_workers": 1, "max_workers": 4},
  "autotermination_minutes": 30,
  "single_user_name": "usuario@tenant.com"
}
```

### Serverless (SQL Warehouse para queries)
- Nenhuma configuração de cluster necessária
- Billable por segundo de compute
- Warm start: ~2-5s (vs 3-5min do job cluster)

## Autoscaling — Boas Práticas
- `min_workers` ≥ 1 para evitar cold start completo
- `max_workers` = estimativa conservadora (evitar runaway costs)
- Monitorar Ganglia / Spark UI para verificar utilização
- Com AQE ativo, autoscaling é mais estável

## Compute Policies
Permitem restringir configurações de cluster por grupo/time:

```json
{
  "policy_name": "data-engineering-policy",
  "definition": {
    "spark_version": {"type": "allowlist", "values": ["14.3.x-scala2.12"]},
    "node_type_id": {"type": "allowlist", "values": ["Standard_DS3_v2", "Standard_DS4_v2"]},
    "autoscale.max_workers": {"type": "range", "maxValue": 10}
  }
}
```

## Init Scripts
Scripts executados em cada node durante bootstrap do cluster:
```bash
#!/bin/bash
# install_libs.sh
pip install -q great-expectations==0.18.0 dask==2024.1.0
```
- Manter scripts idempotentes
- Testar em cluster dev antes de aplicar em prod
- Logs em `/databricks/driver/init_scripts.log`

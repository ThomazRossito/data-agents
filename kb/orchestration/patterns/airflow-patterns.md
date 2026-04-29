# Airflow Patterns para Data Engineering

## DAG — Conceitos Fundamentais
- **DAG**: Directed Acyclic Graph — Grafo direcionado sem ciclos
- **Single Data Pipeline**: cada DAG representa 1 pipeline de dados
- **Linear (A → B)**: tarefas executam em sequência, sem loops
- **Acíclico**: impossível voltar a uma tarefa anterior no mesmo contexto de execução

> DAG é o "plano de voo" do pipeline — define QUANDO e EM QUE ORDEM as tarefas rodam, não O QUE rodam.

## Estrutura Básica de um DAG
```python
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.databricks.operators.databricks import DatabricksSubmitRunOperator
from datetime import datetime, timedelta

default_args = {
    "owner": "data-eng",
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": True,
    "email": ["data-team@company.com"],
}

with DAG(
    dag_id="medallion_pipeline",
    default_args=default_args,
    start_date=datetime(2026, 1, 1),
    schedule_interval="0 6 * * *",  # todo dia às 6h
    catchup=False,
    tags=["bronze", "databricks"],
) as dag:

    ingest = DatabricksSubmitRunOperator(
        task_id="ingest_bronze",
        databricks_conn_id="databricks_default",
        existing_cluster_id="cluster-abc123",
        notebook_task={"notebook_path": "/Repos/main/bronze/ingest"},
    )

    transform = DatabricksSubmitRunOperator(
        task_id="transform_silver",
        databricks_conn_id="databricks_default",
        existing_cluster_id="cluster-abc123",
        spark_python_task={"python_file": "dbfs:/scripts/silver/transform.py"},
    )

    quality = PythonOperator(
        task_id="data_quality_check",
        python_callable=run_quality_checks,
        op_kwargs={"table": "silver.orders"},
    )

    ingest >> transform >> quality
```

## DatabricksSubmitRunOperator vs DatabricksRunNowOperator
| Operador | Quando Usar |
|----------|------------|
| `SubmitRunOperator` | Cria job sob demanda (sem pre-configurado) |
| `RunNowOperator` | Dispara job já existente no workspace |

## Sensors — Esperar Condição
```python
from airflow.sensors.filesystem import FileSensor
from airflow.providers.databricks.sensors.databricks_partition import DatabricksPartitionSensor

# Esperar arquivo chegar
wait_file = FileSensor(
    task_id="wait_for_source_file",
    filepath="/data/raw/orders_{{ ds }}.csv",
    poke_interval=300,  # verificar a cada 5min
    timeout=3600,       # timeout 1h
    mode="reschedule",  # ← não bloquear worker
)

# Esperar partição Delta
wait_partition = DatabricksPartitionSensor(
    task_id="wait_bronze_partition",
    databricks_conn_id="databricks_default",
    catalog="prod",
    schema="bronze",
    table_name="orders",
    partitions={"date": "{{ ds }}"},
)

wait_file >> wait_partition >> transform
```

## XCom — Passar Dados Entre Tasks
```python
# Push
def push_value(**context):
    context['ti'].xcom_push(key='row_count', value=1234)

# Pull
def use_value(**context):
    count = context['ti'].xcom_pull(task_ids='ingest', key='row_count')
    if count == 0:
        raise ValueError("Zero rows ingested")
```

## Boas Práticas
- Uma DAG por pipeline lógico (não uma DAG "master" para tudo)
- `catchup=False` em DAGs de produção (evitar backfill acidental)
- `mode="reschedule"` em sensors (libera worker slot)
- Usar `task_group` para agrupar tasks logicamente
- Parametrizar com `Variables` ou `Connections` — não hardcode
- Retry ≤ 3 com `retry_delay` exponencial para evitar thundering herd

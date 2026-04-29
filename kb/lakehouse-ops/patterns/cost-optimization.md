# Pattern: Cost Optimization

## Databricks — principais alavancas

### 1. Cluster right-sizing
```
Interactive clusters → NUNCA em prod (billing 24/7 se não auto-terminated)
Job clusters        → padrão para prod (billing apenas durante execução)
Serverless Jobs     → melhor custo para pipelines < 30 min
Serverless SQL WH   → adhoc queries e BI (billing por query-second)
```

### 2. Cluster pools
```json
{
  "pool_name": "prod-pool",
  "min_idle_instances": 2,
  "max_capacity": 10,
  "idle_instance_autotermination_minutes": 10,
  "node_type_id": "Standard_DS3_v2"
}
```
Pools reduzem cold start de ~5 min para ~30 seg e evitam instâncias ociosas.

### 3. Autoscaling inteligente
```json
{
  "autoscale": {
    "min_workers": 2,
    "max_workers": 8
  },
  "spark_conf": {
    "spark.databricks.adaptive.autoOptimizeShufflePartitions.enabled": "true"
  }
}
```
Não usar autoscale em jobs de streaming contínuo → prefira fixed size.

### 4. Spot instances (Azure Spot VMs)
```json
{
  "azure_attributes": {
    "availability": "SPOT_WITH_FALLBACK_AZURE",
    "spot_bid_price_percent": 100
  }
}
```
Economia de 60–80% vs on-demand. Aceitar interrupções (reiniciar job).

### 5. Photon (apenas se valer o custo)
Photon tem surcharge de ~30% em DBU. Só ativar se:
- Delta MERGE em tabelas > 100M linhas
- SQL warehouses com queries analíticas pesadas
- Pipeline já otimizado e ainda lento

## Fabric — principais alavancas

### 1. Não deixar notebooks/jobs rodando sem necessidade
- Todo notebook Spark que não é streaming deve ter `trigger(availableNow=True)`
- Spark Jobs Definition: configurar timeout

### 2. Monitorar throttling
- Capacity Metrics app → se CU% > 80% consistentemente → upgrade de SKU ou otimizar jobs
- Throttling = jobs na fila = latência aumenta

### 3. Dataflow Gen2 vs Spark Notebook
- Dataflow Gen2: mais CU para transformações grandes (usa Power Query engine)
- Prefer Spark Notebook para transformações em datasets > 10M linhas

### 4. Direct Lake vs Import no Power BI
- Direct Lake: zero custo de cópia, refresh automático
- Import: consome CU de refresh e armazenamento adicional
- Regra: sempre usar Direct Lake se tabela ≤ capacidade de cache do SKU

## Storage cost (ADLS Gen2)

```python
# Verificar tamanho real de tabelas Delta (após VACUUM)
spark.sql("""
    SELECT
        table_schema,
        table_name,
        ROUND(bytes_total / 1e9, 2) AS size_gb
    FROM information_schema.table_storage_metrics
    ORDER BY bytes_total DESC
    LIMIT 20
""")
```

- Hot tier: dados acessados diariamente → manter
- Cool tier: Bronze > 90 dias → mover para cool storage (economia ~50%)
- Archive: dados > 2 anos raramente acessados → archive tier (economia ~80%)

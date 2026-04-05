# SKILL: Microsoft Fabric Lakehouse — Medallion Architecture

> **Fonte:** Microsoft Learn (learn.microsoft.com/fabric) + Fabric Blog
> **Atualizado:** Janeiro 2026
> **Uso:** Leia este arquivo ANTES de projetar ou gerar qualquer pipeline Fabric Lakehouse.

---

## O que é o Fabric Lakehouse?

O Microsoft Fabric Lakehouse combina a flexibilidade de um data lake com a capacidade analítica de um data warehouse. Dados são armazenados em **Delta Lake** no **OneLake** (storage único baseado em Azure Data Lake Storage Gen2). O acesso é possível via:
- **Apache Spark** (Notebooks PySpark / SparkSQL — engine Synapse)
- **SQL Analytics Endpoint** (T-SQL read-only automático sobre as tabelas Delta)
- **Direct Lake** (Power BI lê diretamente os arquivos Parquet sem importar)

---

## Estrutura de Workspaces Recomendada

```
Workspace Bronze  →  Lakehouse Bronze  (ingestão raw)
Workspace Silver  →  Lakehouse Silver  (limpeza e conformação)
Workspace Gold    →  Lakehouse Gold    (star schema, métricas)
```

> **Importante:** A Microsoft recomenda **um workspace por camada** para separar controle de acesso e capacidade de compute. Em projetos menores, um único workspace com três Lakehouses separados é aceitável.

---

## Camada BRONZE — Ingestão Raw

### Princípios
- Armazena dados **exatamente como chegaram** da fonte (zero transformações).
- Adicione colunas de metadata: `_ingestion_timestamp`, `_source_file`, `_source_system`.
- Nunca force tipos (sem `CAST`) nesta camada.
- Prefira o formato **Delta** mesmo no Bronze para auditoria e time travel.

### Ferramentas de Ingestão por Cenário

| Cenário                         | Ferramenta Recomendada                              |
|---------------------------------|-----------------------------------------------------|
| Arquivos CSV/Parquet/JSON (lote)| Data Factory Copy Activity ou Notebooks Spark       |
| Banco relacional (batch)        | Dataflows Gen2 (query folding) ou Copy Activity     |
| Streaming (Kafka, Event Hub)    | Eventstreams → Lakehouse destino                    |
| API REST (incremental)          | Notebooks PySpark com requisição HTTP               |
| Arquivos no OneLake já existente| Shortcuts (sem movimentação de dados)               |

### Código PySpark — Bronze com metadata

```python
from pyspark.sql import functions as F

# Leitura do arquivo fonte (Files/ area do Lakehouse)
df_raw = spark.read.format("json").load("Files/raw/orders/")

# Adicionar colunas de metadata obrigatórias
df_bronze = df_raw \
    .withColumn("_ingestion_timestamp", F.current_timestamp()) \
    .withColumn("_source_file", F.input_file_name()) \
    .withColumn("_source_system", F.lit("orders_api"))

# Escrita na camada Tables/ (tabela Delta gerenciada pelo Lakehouse)
df_bronze.write \
    .format("delta") \
    .mode("append") \
    .saveAsTable("bronze_orders")
```

### Ingestão Incremental com Auto Loader (PySpark Structured Streaming)

```python
# Auto Loader no Fabric — monitora chegada de novos arquivos
df_stream = spark.readStream \
    .format("cloudFiles") \
    .option("cloudFiles.format", "csv") \
    .option("cloudFiles.schemaLocation", "Files/checkpoints/orders_schema") \
    .load("Files/raw/orders/")

df_stream \
    .withColumn("_ingestion_timestamp", F.current_timestamp()) \
    .writeStream \
    .format("delta") \
    .option("checkpointLocation", "Files/checkpoints/bronze_orders") \
    .trigger(availableNow=True) \
    .toTable("bronze_orders")
```

---

## Camada SILVER — Limpeza e Conformação

### Princípios
- Tabelas **Delta** na pasta `Tables/` do Lakehouse Silver.
- Aplicar: limpeza de tipos, desduplicação, padronização de strings, tratamento de nulls.
- Usar **MERGE** (upsert) para manter histórico de transações.
- Nunca usar Materialized Views na Silver (reservadas para Gold).
- V-Order **habilitado por padrão** nas escritas Spark no Fabric — não desabilitar.

### MERGE — Upsert padrão Silver (PySpark)

```python
from delta.tables import DeltaTable
from pyspark.sql import functions as F

# Leitura incremental do Bronze
df_new = spark.read.table("bronze.bronze_orders") \
    .filter(F.col("_ingestion_timestamp") > spark.sql(
        "SELECT COALESCE(MAX(_updated_at), '1900-01-01') FROM silver.silver_orders"
    ).collect()[0][0])

# Transformações Silver
df_silver = df_new \
    .withColumn("order_date", F.to_date("order_date_raw", "yyyy-MM-dd")) \
    .withColumn("amount", F.col("amount_raw").cast("double")) \
    .withColumn("customer_id", F.trim(F.upper("customer_id_raw"))) \
    .withColumn("_updated_at", F.current_timestamp()) \
    .dropDuplicates(["order_id"])

# MERGE na tabela Silver
if DeltaTable.isDeltaTable(spark, "Tables/silver_orders"):
    silver_table = DeltaTable.forName(spark, "silver.silver_orders")
    silver_table.alias("target").merge(
        df_silver.alias("source"),
        "target.order_id = source.order_id"
    ).whenMatchedUpdateAll() \
     .whenNotMatchedInsertAll() \
     .execute()
else:
    df_silver.write.format("delta").mode("overwrite").saveAsTable("silver.silver_orders")
```

### Configuração V-Order (confirmação explícita)

```python
# V-Order é habilitado por padrão no Fabric — confirmar que não foi desativado
spark.conf.set("spark.sql.parquet.vorder.enabled", "true")
spark.conf.set("spark.microsoft.delta.optimizeWrite.enabled", "true")
spark.conf.set("spark.microsoft.delta.optimizeWrite.binSize", "1073741824")  # 1GB bins
```

---

## Camada GOLD — Star Schema e Métricas

### Princípios
- Tabelas **Delta** otimizadas para consumo analítico e Direct Lake.
- V-Order **obrigatório** — garante performance máxima no Direct Lake / Power BI.
- Aplicar `OPTIMIZE` após cargas significativas.
- Estrutura Star Schema: tabelas Fato + Dimensões.
- Nunca exponha dados PII brutos na Gold.

### Gold — Tabela Fato (PySpark)

```python
# Construção da tabela fato Gold a partir da Silver
df_fato = spark.sql("""
    SELECT
        o.order_id,
        o.customer_id,
        o.order_date,
        o.amount,
        c.region,
        c.segment,
        p.product_category,
        o._updated_at AS _gold_updated_at
    FROM silver.silver_orders o
    LEFT JOIN silver.silver_customers c ON o.customer_id = c.customer_id
    LEFT JOIN silver.silver_products p ON o.product_id = p.product_id
""")

# Escrita com V-Order explícito (já é padrão, mas documentar é bom)
df_fato.write \
    .format("delta") \
    .option("vorder", "true") \
    .mode("overwrite") \
    .option("overwriteSchema", "true") \
    .saveAsTable("gold.fato_orders")

# OPTIMIZE após escrita para consolidar arquivos
spark.sql("OPTIMIZE gold.fato_orders")
```

---

## Padrão Medallion com SparkSQL (Notebooks)

```sql
-- Bronze → Silver via SparkSQL
CREATE OR REPLACE TABLE silver.silver_customers
USING DELTA
AS
SELECT
    TRIM(UPPER(customer_id))          AS customer_id,
    INITCAP(name)                     AS name,
    LOWER(email)                      AS email,
    CAST(created_date AS DATE)        AS created_date,
    region,
    segment,
    current_timestamp()               AS _updated_at
FROM bronze.bronze_customers
WHERE customer_id IS NOT NULL
  AND email IS NOT NULL
QUALIFY ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY _ingestion_timestamp DESC) = 1;
```

---

## Manutenção e Otimização

```python
# Executar após cargas grandes ou semanalmente
tables = ["bronze_orders", "silver_orders", "silver_customers", "gold.fato_orders"]

for table in tables:
    # Consolida small files (crítico para Direct Lake performance)
    spark.sql(f"OPTIMIZE {table}")
    # Remove versões antigas (manter 7 dias para auditoria)
    spark.sql(f"VACUUM {table} RETAIN 168 HOURS")
```

---

## Checklist de Qualidade por Camada

### Bronze
- [ ] Colunas `_ingestion_timestamp` e `_source_file` presentes
- [ ] Schema inferido ou declarado explicitamente
- [ ] Checkpoint configurado para ingestão streaming
- [ ] Particionamento por data de ingestão para tabelas > 10M linhas

### Silver
- [ ] Tipos de dados explícitos (sem `inferSchema` em produção)
- [ ] Nulls tratados (drop obrigatórios, fill opcionais)
- [ ] Deduplicação aplicada (`QUALIFY ROW_NUMBER()` ou `dropDuplicates`)
- [ ] MERGE implementado para evitar duplicatas em reprocessamento
- [ ] V-Order habilitado

### Gold
- [ ] Star Schema documentado (chaves de relacionamento identificadas)
- [ ] Sem PII exposto
- [ ] `OPTIMIZE` executado após cada carga
- [ ] V-Order habilitado
- [ ] Semântica de negócio validada com stakeholders

---

## Referências

- [Implement Medallion Lakehouse Architecture](https://learn.microsoft.com/en-us/fabric/onelake/onelake-medallion-lakehouse-architecture)
- [Delta Optimization and V-Order in Fabric](https://learn.microsoft.com/en-us/fabric/data-engineering/delta-optimization-and-v-order)
- [Lakehouse end-to-end scenario](https://learn.microsoft.com/en-us/fabric/data-engineering/tutorial-lakehouse-introduction)

---
updated_at: 2026-04-16
source: kb/fabric (lakehouse-concepts, lakehouse-patterns, shortcut-patterns, data-factory-patterns, cross-platform-concepts)
---

# SKILL: Microsoft Fabric Lakehouse — Medallion Architecture

> **Fonte:** Microsoft Learn (learn.microsoft.com/fabric) + Fabric Blog + KB interna do projeto
> **Atualizado:** Abril 2026
> **Uso:** Leia este arquivo ANTES de projetar ou gerar qualquer pipeline Fabric Lakehouse.

---

## O que é o Fabric Lakehouse?

O Microsoft Fabric Lakehouse combina a flexibilidade de um data lake com a capacidade analítica de um data warehouse. Dados são armazenados em **Delta Lake** no **OneLake** (storage único baseado em Azure Data Lake Storage Gen2). O acesso é possível via:
- **Apache Spark** (Notebooks PySpark / SparkSQL — engine Synapse)
- **SQL Analytics Endpoint** (T-SQL read-only automático sobre as tabelas Delta)
- **Direct Lake** (Power BI lê diretamente os arquivos Parquet sem importar)

### Tables vs Files

| Aspecto | Tables (`/Tables/`) | Files (`/Files/`) |
|---------|---------------------|-------------------|
| **Formato** | Delta Lake (.parquet + _delta_log) | Parquet, CSV, JSON, qualquer formato |
| **Transações** | ACID completo | Nenhum (imutável) |
| **Consultas** | SQL/Spark nativo + SQL Analytics Endpoint | Requer leitura explícita via Spark |
| **Uso Ideal** | Dados estruturados para BI e pipelines | Raw files, archives, landing zone |
| **Direct Lake** | Suportado (com V-Order) | Não suportado |

> Regra: dados que serão consumidos por Power BI ou SQL Analytics Endpoint devem sempre ir para `/Tables/`. Use `/Files/` apenas para landing zone temporária e arquivos de referência.

---

## Caminhos ABFSS (OneLake)

```
# Formato padrão
abfss://{workspace-name}@onelake.dfs.fabric.microsoft.com/{lakehouse-name}.Lakehouse/Tables/{table}
abfss://{workspace-name}@onelake.dfs.fabric.microsoft.com/{lakehouse-name}.Lakehouse/Files/{path}

# Exemplo concreto
abfss://Analytics@onelake.dfs.fabric.microsoft.com/SalesLakehouse.Lakehouse/Tables/silver_orders
```

> Ao referenciar tabelas registradas no Lakehouse, prefira `spark.read.table("schema.tabela")` ao invés do path ABFSS direto — é mais portável e respeita o metastore.

---

## Estrutura de Workspaces Recomendada

```
Workspace Bronze  →  Lakehouse Bronze  (ingestão raw)
Workspace Silver  →  Lakehouse Silver  (limpeza e conformação)
Workspace Gold    →  Lakehouse Gold    (star schema, métricas)
```

> **Importante:** A Microsoft recomenda **um workspace por camada** para separar controle de acesso e capacidade de compute. Em projetos menores, um único workspace com três Lakehouses separados é aceitável.

### Criação do Lakehouse com Multi-Schema (`enable_schemas`)

Lakehouses podem ser criados com suporte a múltiplos schemas lógicos, evitando a criação de múltiplos Lakehouses para separação por domínio:

```http
POST /workspaces/{workspace-id}/lakehouses
Content-Type: application/json

{
  "displayName": "SalesLakehouse",
  "description": "Lakehouse for sales analytics",
  "creationPayload": {
    "enableSchemas": true
  }
}
```

Com `enableSchemas: true`, a organização fica:

```
SalesLakehouse.bronze.orders         (schema=bronze)
SalesLakehouse.silver.orders         (schema=silver)
SalesLakehouse.gold.fato_orders      (schema=gold)
SalesLakehouse.governance.audit_logs (schema=governance)
```

> Benefício: isolamento lógico sem criar múltiplos Lakehouses — menor overhead de governança. Recomendado para projetos com múltiplos domínios em um workspace.

---

## Políticas de Retenção por Camada

| Camada | Dados | Retenção Recomendada | Transformações |
|--------|-------|----------------------|----------------|
| **Bronze** | Cópia 1:1 dos dados brutos | 30–90 dias | Nenhuma |
| **Silver** | Limpos, deduplicados, PII mascarado | 1–2 anos | Limpeza, joins iniciais |
| **Gold** | Otimizados para consumo (BI, ML) | 3+ anos (compliance) | Agregações, V-Order |

```python
# Executar semanalmente — retenção alinhada às políticas acima
spark.sql("VACUUM bronze.bronze_orders RETAIN 720 HOURS")    # 30 dias
spark.sql("VACUUM silver.silver_orders RETAIN 8760 HOURS")   # 1 ano
spark.sql("VACUUM gold.fato_orders RETAIN 26280 HOURS")      # 3 anos
```

---

## Camada BRONZE — Ingestão Raw

### Princípios
- Armazena dados **exatamente como chegaram** da fonte (zero transformações).
- Adicione colunas de metadata: `_ingestion_timestamp`, `_source_file`, `_source_system`.
- Nunca force tipos (sem `CAST`) nesta camada.
- Prefira o formato **Delta** mesmo no Bronze para auditoria e time travel.
- Não crie partições dinâmicas no Bronze — aplique apenas após transformação (Silver/Gold).

### Ferramentas de Ingestão por Cenário

| Cenário | Ferramenta Recomendada |
|---------|------------------------|
| Arquivos CSV/Parquet/JSON (lote) | Data Factory Copy Activity ou Notebooks Spark |
| Banco relacional (batch) | Dataflows Gen2 (query folding) ou Copy Activity |
| Streaming (Kafka, Event Hub) | Eventstreams → Lakehouse destino |
| API REST (incremental) | Notebooks PySpark com requisição HTTP |
| Arquivos no OneLake já existente | Shortcuts (sem movimentação de dados) |
| Databricks Unity Catalog → Fabric | Mirroring (sincronização contínua automática) |

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
    .saveAsTable("bronze.bronze_orders")
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
    .toTable("bronze.bronze_orders")
```

---

## Camada SILVER — Limpeza e Conformação

### Princípios
- Tabelas **Delta** na pasta `Tables/` do Lakehouse Silver.
- Aplicar: limpeza de tipos, desduplicação, padronização de strings, tratamento de nulls, mascaramento de PII.
- Usar **MERGE** (upsert) para manter histórico de transações.
- Nunca usar Materialized Views na Silver (reservadas para Gold).
- V-Order **habilitado por padrão** nas escritas Spark no Fabric — não desabilitar.
- Tipos de dados explícitos obrigatórios — sem `inferSchema` em produção.

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

### Padrão Silver via Dataflows Gen2

Para ingestão de bancos relacionais com query folding, Dataflows Gen2 é preferível a Notebooks por ter V-Order habilitado por padrão e não exigir cluster Spark ativo:

```python
# Equivalente PySpark ao Dataflow Gen2 para Silver
from pyspark.sql import functions as F

df_raw = spark.read.table("bronze.bronze_customer")

df_clean = df_raw \
    .filter(F.col("customer_id").isNotNull()) \
    .withColumn("updated_at", F.to_timestamp("updated_at_raw", "yyyy-MM-dd")) \
    .dropDuplicates(["customer_id"])

df_clean.write.format("delta").mode("overwrite") \
    .option("path", "abfss://Analytics@onelake.dfs.fabric.microsoft.com/SilverLH.Lakehouse/Tables/customer_silver") \
    .saveAsTable("silver.customer_silver")
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
- Use **surrogate keys inteiras** nas tabelas Fato (melhor performance VertiPaq no Direct Lake).
- Use `CLUSTER BY` — nunca `PARTITION BY` — em tabelas destinadas ao Direct Lake.
- Não crie views T-SQL sobre tabelas Gold para expor no modelo semântico — views causam fallback para DirectQuery no Power BI.

### Gold — Tabela Fato (PySpark)

```python
# Construção da tabela fato Gold a partir da Silver
df_fato = spark.sql("""
    SELECT
        CAST(ROW_NUMBER() OVER (ORDER BY o.order_id) AS INT) AS sk_order,
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

# OPTIMIZE após escrita para consolidar arquivos (crítico para Direct Lake)
spark.sql("OPTIMIZE gold.fato_orders")
```

### Gold — Tabela Dimensão com TBLPROPERTIES

```sql
-- Criar dimensão com V-Order via SparkSQL
CREATE OR REPLACE TABLE gold.dim_clientes
USING DELTA
TBLPROPERTIES ('delta.parquet.vorder.enabled' = 'true')
AS
SELECT
    CAST(ROW_NUMBER() OVER (ORDER BY customer_id) AS INT) AS sk_cliente,
    customer_id,
    name,
    region,
    segment
FROM silver.silver_clientes
WHERE is_active = true;
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

## Shortcuts — Acesso Zero-Copy

Shortcuts são **links lógicos** para dados externos sem cópia física. Usados no Bronze para integrar fontes externas sem mover dados para o OneLake.

| Propriedade | Shortcut | Copy Activity |
|-------------|----------|---------------|
| **Storage** | Referência ao original | Cópia local no OneLake |
| **Latência** | 1–5ms (rede) | Instantâneo (local) |
| **Custo** | Apenas query | Query + storage |
| **Update** | Real-time (fonte) | Requer resync manual |
| **Governança** | Controle na fonte | Dados duplicados |

### Tipos de Shortcut Suportados

| Tipo | Caso de Uso |
|------|-------------|
| **OneLake (Cross-Workspace)** | Compartilhar tabelas Gold entre workspaces Fabric |
| **ADLS Gen2** | Dados em Azure Data Lake Storage externo |
| **Amazon S3** | Dados em buckets AWS |
| **Azure Blob Storage** | Arquivos em Blob externo |
| **Dataverse** | Dados do Microsoft Dynamics / Power Apps |
| **Google Cloud Storage** | Dados em GCS |
| **S3-Compatible** | MinIO e outros armazenamentos compatíveis com S3 |

### Criar Shortcut — OneLake Cross-Workspace (REST)

```http
POST /workspaces/{workspace-id}/items/{lakehouse-id}/shortcuts
{
  "path": "Tables",
  "name": "shared_dim_customer",
  "target": {
    "oneLake": {
      "itemId": "source-lakehouse-id",
      "path": "/Gold/CRM/dim_customer",
      "workspace_id": "source-workspace-id"
    }
  },
  "shortcutConflictPolicy": "Abort"
}
```

### Conflict Policies para Shortcuts

| Policy | Ação | Quando usar |
|--------|------|-------------|
| `Abort` | Falha se já existe (padrão) | Evitar overwrites acidentais |
| `GenerateUniqueName` | `dim_customer_1`, `dim_customer_2` | Coexistência de versões |
| `CreateOrOverwrite` | Sobrescreve se existe | Atualizar shortcut existente |
| `OverwriteOnly` | Erro se não existe | Atualização controlada (append-only) |

> Prefira `Abort` em produção. Use `CreateOrOverwrite` apenas em scripts de infraestrutura idempotentes.

---

## Manutenção e Otimização

```python
# Executar após cargas grandes ou semanalmente
tables = [
    ("bronze.bronze_orders", 720),    # 30 dias
    ("silver.silver_orders", 8760),   # 1 ano
    ("silver.silver_customers", 8760),
    ("gold.fato_orders", 26280),      # 3 anos
    ("gold.dim_clientes", 26280),
]

for table, retain_hours in tables:
    # Consolida small files (crítico para Direct Lake performance)
    spark.sql(f"OPTIMIZE {table}")
    # Remove versões antigas respeitando política de retenção
    spark.sql(f"VACUUM {table} RETAIN {retain_hours} HOURS")
```

> Execute `OPTIMIZE` sempre após cargas significativas na Gold. O Direct Lake exige arquivos Parquet consolidados para performance máxima.

---

## Regras Gold para Direct Lake (resumo)

Estas regras evitam **fallback para DirectQuery** no Power BI:

| Causa de Fallback | Prevenção |
|-------------------|-----------|
| Views T-SQL no modelo semântico | Materializar como tabela Delta — nunca expor views |
| Tabelas sem V-Order | Reescrever com V-Order + OPTIMIZE |
| Tipos complexos (arrays, structs) | Fazer unnesting/flatten na Silver |
| Exceder limite de linhas do SKU | Aumentar SKU ou agregar na Gold |
| Muitos small files | Executar OPTIMIZE para consolidar |
| `PARTITION BY` em tabelas Gold | Usar `CLUSTER BY` ao invés |

---

## Checklist de Qualidade por Camada

### Bronze
- [ ] Colunas `_ingestion_timestamp` e `_source_file` presentes
- [ ] Schema inferido ou declarado explicitamente
- [ ] Checkpoint configurado para ingestão streaming
- [ ] Particionamento por data de ingestão apenas para tabelas > 10M linhas
- [ ] Sem `CAST` ou transformações de tipo (dados raw)

### Silver
- [ ] Tipos de dados explícitos (sem `inferSchema` em produção)
- [ ] Nulls tratados (drop obrigatórios, fill opcionais)
- [ ] Deduplicação aplicada (`QUALIFY ROW_NUMBER()` ou `dropDuplicates`)
- [ ] MERGE implementado para evitar duplicatas em reprocessamento
- [ ] V-Order habilitado
- [ ] PII mascarado ou removido antes de promover à Gold

### Gold
- [ ] Star Schema documentado (chaves de relacionamento identificadas)
- [ ] Surrogate keys inteiras nas tabelas Fato
- [ ] Sem PII exposto
- [ ] `OPTIMIZE` executado após cada carga
- [ ] V-Order habilitado (via `TBLPROPERTIES` ou `spark.conf`)
- [ ] Nenhuma view T-SQL exposta para o modelo semântico
- [ ] `CLUSTER BY` usado (não `PARTITION BY`) quando aplicável
- [ ] Semântica de negócio validada com stakeholders
- [ ] Lineage documentado no OneLake Data Catalog

---

## Referências

- [Implement Medallion Lakehouse Architecture](https://learn.microsoft.com/en-us/fabric/onelake/onelake-medallion-lakehouse-architecture)
- [Delta Optimization and V-Order in Fabric](https://learn.microsoft.com/en-us/fabric/data-engineering/delta-optimization-and-v-order)
- [Lakehouse end-to-end scenario](https://learn.microsoft.com/en-us/fabric/data-engineering/tutorial-lakehouse-introduction)
- [OneLake Shortcuts](https://learn.microsoft.com/en-us/fabric/onelake/onelake-shortcuts)
- [Direct Lake overview](https://learn.microsoft.com/en-us/fabric/fundamentals/direct-lake-overview)
- [Lakehouse schemas (enable_schemas)](https://learn.microsoft.com/en-us/fabric/data-engineering/lakehouse-schemas)

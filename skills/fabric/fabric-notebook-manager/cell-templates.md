# Cell Templates — Fabric Notebook Manager

> **Uso:** Catálogo de templates de células PySpark prontos para uso em notebooks Microsoft Fabric.
> Cada template representa o `source` de uma célula `.ipynb` e segue os padrões da arquitetura
> Medallion (Bronze → Silver → Gold) com as regras da KB Fabric e KB Pipeline Design.
>
> **Convenção de placeholders:** valores entre `{{duplas_chaves}}` devem ser substituídos
> pelo pipeline-architect antes de injetar a célula no notebook.

---

## Índice de Templates

| ID                          | Camada        | Caso de Uso                                              |
|-----------------------------|---------------|----------------------------------------------------------|
| `spark-config-vorder`       | Configuração  | V-Order + optimize write habilitados (padrão Fabric)     |
| `spark-config-external-adls`| Configuração  | Acesso a ADLS Gen2 externo via Service Principal         |
| `bronze-batch-ingest`       | Bronze        | Ingestão batch CSV/JSON/Parquet com colunas de metadata  |
| `bronze-autoloader`         | Bronze        | Ingestão incremental com Auto Loader (cloudFiles)        |
| `silver-merge-upsert`       | Silver        | MERGE/Upsert com deduplicação e limpeza de tipos         |
| `silver-scd2`               | Silver        | Slowly Changing Dimension Type 2                         |
| `gold-star-schema-fact`     | Gold          | Tabela fato com JOINs de todas as dimensões              |
| `gold-star-schema-dim`      | Gold          | Dimensão Gold a partir da Silver                         |
| `gold-dim-calendario`       | Gold          | Dimensão calendário gerada via SEQUENCE (sintética)      |
| `gold-optimize-vacuum`      | Gold          | Manutenção: OPTIMIZE + VACUUM para tabelas Gold          |
| `markdown-header`           | Utilidade     | Célula markdown com metadados do notebook                |
| `data-profiling-quick`      | Utilidade     | Profiling rápido: count, nulls, distincts, min/max       |

---

## Configuração

### `spark-config-vorder`

**Descrição:** Célula de configuração padrão para qualquer notebook Fabric. Habilita
explicitamente V-Order e Optimize Write — ambos são padrão no Fabric, mas declarar
garante que não foram desativados por configurações anteriores na sessão.

**Variáveis:** nenhuma.

**Tipo de célula:** `code`

```python
# ============================================================
# Configuração padrão Fabric — V-Order + Optimize Write
# Deve ser a primeira célula de código de todo notebook.
# ============================================================

# V-Order: ordena os dados dentro dos arquivos Parquet durante a escrita,
# maximizando a performance de leitura pelo Direct Lake e SQL Endpoint.
spark.conf.set("spark.sql.parquet.vorder.enabled", "true")

# Optimize Write: agrupa small files automaticamente durante a escrita Delta,
# reduzindo a necessidade de OPTIMIZE manual frequente.
spark.conf.set("spark.microsoft.delta.optimizeWrite.enabled", "true")

# Tamanho do bin para o Optimize Write (1 GB é o padrão recomendado pela Microsoft).
spark.conf.set("spark.microsoft.delta.optimizeWrite.binSize", "1073741824")

print("Configuracao Fabric aplicada: V-Order=ON | OptimizeWrite=ON")
```

---

### `spark-config-external-adls`

**Descrição:** Configura acesso a uma conta ADLS Gen2 externa ao Lakehouse via
Service Principal. Credenciais são lidas do Azure Key Vault — nunca hardcoded.

**Variáveis:**
- `{{key_vault_url}}` — URL do Azure Key Vault (ex: `https://meu-kv.vault.azure.net/`)
- `{{secret_tenant_id}}` — nome do secret no KV que contém o Tenant ID
- `{{secret_client_id}}` — nome do secret no KV que contém o Client ID
- `{{secret_client_secret}}` — nome do secret no KV que contém o Client Secret
- `{{storage_account_name}}` — nome da storage account (ex: `myadlsgen2`)

**Tipo de célula:** `code`

```python
# ============================================================
# Configuração de acesso a ADLS Gen2 externo via Service Principal
# Credenciais lidas do Azure Key Vault — NUNCA hardcode.
# ============================================================
from notebookutils import mssparkutils

# Leitura das credenciais do Key Vault
tenant_id     = mssparkutils.credentials.getSecret("{{key_vault_url}}", "{{secret_tenant_id}}")
client_id     = mssparkutils.credentials.getSecret("{{key_vault_url}}", "{{secret_client_id}}")
client_secret = mssparkutils.credentials.getSecret("{{key_vault_url}}", "{{secret_client_secret}}")

storage_account = "{{storage_account_name}}"

# Configuração do Service Principal no Spark
spark.conf.set(
    f"fs.azure.account.auth.type.{storage_account}.dfs.core.windows.net",
    "OAuth"
)
spark.conf.set(
    f"fs.azure.account.oauth.provider.type.{storage_account}.dfs.core.windows.net",
    "org.apache.hadoop.fs.azurebfs.oauth2.ClientCredsTokenProvider"
)
spark.conf.set(
    f"fs.azure.account.oauth2.client.id.{storage_account}.dfs.core.windows.net",
    client_id
)
spark.conf.set(
    f"fs.azure.account.oauth2.client.secret.{storage_account}.dfs.core.windows.net",
    client_secret
)
spark.conf.set(
    f"fs.azure.account.oauth2.client.endpoint.{storage_account}.dfs.core.windows.net",
    f"https://login.microsoftonline.com/{tenant_id}/oauth2/token"
)

print(f"Acesso configurado para storage account: {storage_account}")
# Exemplo de uso:
# df = spark.read.parquet(f"abfss://{{container}}@{storage_account}.dfs.core.windows.net/caminho/")
```

---

## Bronze

### `bronze-batch-ingest`

**Descrição:** Ingestão batch de arquivos CSV, JSON ou Parquet para a camada Bronze.
Adiciona as três colunas de metadata obrigatórias (`_ingestion_timestamp`, `_source_file`,
`_source_system`) e escreve em modo append na tabela Delta do Lakehouse Bronze.
NUNCA aplica transformações de negócio nesta camada.

**Variáveis:**
- `{{file_format}}` — formato do arquivo: `csv`, `json` ou `parquet`
- `{{source_path}}` — caminho dentro de `Files/` (ex: `Files/raw/pedidos/`)
- `{{source_system}}` — identificador da fonte (ex: `erp_sap`, `api_orders`)
- `{{bronze_table_name}}` — nome da tabela Delta destino (ex: `bronze_pedidos`)
- `{{csv_header}}` — `true` ou `false` (usado somente quando `file_format=csv`)
- `{{csv_delimiter}}` — delimitador do CSV (ex: `,` ou `;`) — ignorado para outros formatos

**Tipo de célula:** `code`

```python
# ============================================================
# Bronze — Ingestão Batch
# Camada: Bronze | Formato: {{file_format}}
# Fonte  : {{source_path}}
# Sistema: {{source_system}}
# Destino: {{bronze_table_name}}
# ============================================================
from pyspark.sql import functions as F

# --- Leitura do arquivo fonte (Files/ area do Lakehouse) ---
reader = spark.read.format("{{file_format}}")

# Opções específicas de CSV (ignoradas para JSON/Parquet)
if "{{file_format}}" == "csv":
    reader = (
        reader
        .option("header", "{{csv_header}}")
        .option("delimiter", "{{csv_delimiter}}")
        .option("inferSchema", "true")      # Bronze aceita schema inferido
        .option("encoding", "UTF-8")
    )

df_raw = reader.load("{{source_path}}")

# --- Adição das colunas de metadata obrigatórias (Bronze) ---
# NUNCA aplique transformações de negócio aqui — apenas metadata.
df_bronze = (
    df_raw
    .withColumn("_ingestion_timestamp", F.current_timestamp())
    .withColumn("_source_file", F.input_file_name())
    .withColumn("_source_system", F.lit("{{source_system}}"))
)

# --- Escrita na tabela Delta do Lakehouse (Tables/ area) ---
df_bronze.write \
    .format("delta") \
    .mode("append") \
    .saveAsTable("{{bronze_table_name}}")

# --- Validação pós-carga ---
count = spark.sql("SELECT COUNT(*) AS total FROM {{bronze_table_name}}").collect()[0]["total"]
print(f"Carga concluida. Total de registros em {{bronze_table_name}}: {count:,}")
```

---

### `bronze-autoloader`

**Descrição:** Ingestão incremental com Auto Loader (`cloudFiles`) no Fabric. Monitora
a chegada de novos arquivos no caminho fonte e processa apenas os arquivos ainda não
consumidos, usando checkpoint para garantir exatamente-uma-vez. Ideal para pipelines
contínuos ou agendados.

**Variáveis:**
- `{{file_format}}` — formato: `csv`, `json` ou `parquet`
- `{{source_path}}` — caminho monitorado em `Files/` (ex: `Files/landing/pedidos/`)
- `{{schema_checkpoint_path}}` — caminho para o schema checkpoint (ex: `Files/checkpoints/pedidos_schema`)
- `{{stream_checkpoint_path}}` — caminho para o stream checkpoint (ex: `Files/checkpoints/bronze_pedidos`)
- `{{source_system}}` — identificador da fonte (ex: `api_orders`)
- `{{bronze_table_name}}` — tabela Delta destino (ex: `bronze_pedidos`)

**Tipo de célula:** `code`

```python
# ============================================================
# Bronze — Ingestão Incremental com Auto Loader (cloudFiles)
# Camada: Bronze | Formato: {{file_format}}
# Fonte  : {{source_path}}
# Sistema: {{source_system}}
# Destino: {{bronze_table_name}}
# ============================================================
from pyspark.sql import functions as F

# --- Leitura incremental com Auto Loader ---
# O Auto Loader rastreia automaticamente os arquivos já processados via checkpoint.
# cloudFiles.schemaLocation evita reler o schema a cada execução.
df_stream = (
    spark.readStream
    .format("cloudFiles")
    .option("cloudFiles.format", "{{file_format}}")
    .option("cloudFiles.schemaLocation", "{{schema_checkpoint_path}}")
    .option("cloudFiles.inferColumnTypes", "true")
    .load("{{source_path}}")
)

# --- Adição das colunas de metadata obrigatórias ---
df_bronze_stream = (
    df_stream
    .withColumn("_ingestion_timestamp", F.current_timestamp())
    .withColumn("_source_file", F.input_file_name())
    .withColumn("_source_system", F.lit("{{source_system}}"))
)

# --- Escrita incremental na tabela Delta ---
# trigger(availableNow=True): processa todos os arquivos pendentes e para,
# comportamento ideal para execução agendada (não-contínua).
query = (
    df_bronze_stream
    .writeStream
    .format("delta")
    .outputMode("append")
    .option("checkpointLocation", "{{stream_checkpoint_path}}")
    .trigger(availableNow=True)
    .toTable("{{bronze_table_name}}")
)

# Aguarda a conclusão do micro-batch antes de continuar o notebook
query.awaitTermination()

count = spark.sql("SELECT COUNT(*) AS total FROM {{bronze_table_name}}").collect()[0]["total"]
print(f"Auto Loader concluido. Total acumulado em {{bronze_table_name}}: {count:,}")
```

---

## Silver

### `silver-merge-upsert`

**Descrição:** Padrão MERGE/Upsert da camada Silver. Lê incrementalmente da Bronze,
aplica limpeza de tipos, deduplicação e escreve via MERGE na tabela Silver. Na primeira
execução (tabela ainda não existe), cria a tabela via `saveAsTable`.

**Variáveis:**
- `{{bronze_table_name}}` — tabela Bronze de origem (ex: `bronze_pedidos`)
- `{{silver_table_name}}` — tabela Silver de destino (ex: `silver_pedidos`)
- `{{merge_key}}` — coluna(s) de chave de negócio para o MERGE (ex: `order_id`)
- `{{dedup_key}}` — coluna(s) para deduplicação (ex: `order_id`)
- `{{timestamp_col}}` — coluna de timestamp para filtro incremental (ex: `updated_at`)
- `{{date_col_raw}}` — coluna de data raw para cast (ex: `order_date_raw`)
- `{{date_col}}` — nome da coluna de data tratada (ex: `order_date`)
- `{{date_format}}` — formato da data (ex: `yyyy-MM-dd`)
- `{{amount_col_raw}}` — coluna de valor raw (ex: `amount_raw`)
- `{{amount_col}}` — nome da coluna de valor tratada (ex: `amount`)
- `{{string_col_raw}}` — coluna de string para padronização (ex: `customer_id_raw`)
- `{{string_col}}` — nome da coluna de string tratada (ex: `customer_id`)

**Tipo de célula:** `code`

```python
# ============================================================
# Silver — MERGE/Upsert com Deduplicação e Limpeza de Tipos
# Origem : {{bronze_table_name}}
# Destino: {{silver_table_name}}
# Chave  : {{merge_key}}
# ============================================================
from pyspark.sql import functions as F
from delta.tables import DeltaTable

# --- Leitura incremental da Bronze ---
# Filtra apenas registros mais novos que o máximo já carregado na Silver.
# COALESCE garante que a primeira carga (tabela vazia) funcione corretamente.
ultimo_carregado = spark.sql(f"""
    SELECT COALESCE(MAX(_updated_at), CAST('1900-01-01' AS TIMESTAMP))
    FROM {{silver_table_name}}
""").collect()[0][0]

df_incremento = spark.read.table("{{bronze_table_name}}") \
    .filter(F.col("_ingestion_timestamp") > ultimo_carregado)

# --- Transformações Silver: limpeza de tipos e padronização ---
df_silver = (
    df_incremento
    # Cast de data com formato explícito
    .withColumn("{{date_col}}", F.to_date(F.col("{{date_col_raw}}"), "{{date_format}}"))
    # Cast de valor numérico
    .withColumn("{{amount_col}}", F.col("{{amount_col_raw}}").cast("double"))
    # Padronização de string: remove espaços e converte para maiúsculas
    .withColumn("{{string_col}}", F.trim(F.upper(F.col("{{string_col_raw}}"))))
    # Substitui strings vazias por null (padronização)
    .withColumn("{{string_col}}", F.nullif(F.col("{{string_col}}"), F.lit("")))
    # Timestamp de atualização Silver
    .withColumn("_updated_at", F.current_timestamp())
    # Deduplicação: mantém a linha mais recente por chave
    .dropDuplicates(["{{dedup_key}}"])
)

# --- MERGE na tabela Silver ---
# Se a tabela ainda não existe, cria na primeira execução.
if DeltaTable.isDeltaTable(spark, f"Tables/{{silver_table_name}}"):
    silver_dt = DeltaTable.forName(spark, "{{silver_table_name}}")
    (
        silver_dt.alias("target")
        .merge(
            df_silver.alias("source"),
            "target.{{merge_key}} = source.{{merge_key}}"
        )
        .whenMatchedUpdateAll()
        .whenNotMatchedInsertAll()
        .execute()
    )
    print("MERGE executado com sucesso.")
else:
    # Primeira carga: cria a tabela Delta gerenciada
    df_silver.write \
        .format("delta") \
        .mode("overwrite") \
        .option("overwriteSchema", "true") \
        .saveAsTable("{{silver_table_name}}")
    print("Tabela Silver criada (primeira carga).")

# --- Validação pós-carga ---
count = spark.sql("SELECT COUNT(*) AS total FROM {{silver_table_name}}").collect()[0]["total"]
print(f"Total de registros em {{silver_table_name}}: {count:,}")
```

---

### `silver-scd2`

**Descrição:** Implementa Slowly Changing Dimension Type 2 na camada Silver via Delta Lake.
Mantém histórico completo das alterações com colunas `scd_valid_from`, `scd_valid_to` e
`scd_is_current`. Usa MERGE com cláusulas explícitas para expirar o registro anterior e
inserir o novo, sem dependência de LAG/LEAD/ROW_NUMBER.

**Variáveis:**
- `{{bronze_table_name}}` — tabela Bronze de origem (ex: `bronze_clientes`)
- `{{silver_scd2_table_name}}` — tabela Silver SCD2 de destino (ex: `silver_dim_clientes`)
- `{{business_key}}` — chave de negócio da dimensão (ex: `cliente_id`)
- `{{tracked_cols}}` — lista Python de colunas rastreadas para mudança (ex: `["nome", "email", "segmento"]`)

**Tipo de célula:** `code`

```python
# ============================================================
# Silver — SCD Type 2 via Delta MERGE
# Origem : {{bronze_table_name}}
# Destino: {{silver_scd2_table_name}}
# Chave  : {{business_key}}
# Colunas rastreadas: {{tracked_cols}}
# ============================================================
from pyspark.sql import functions as F
from pyspark.sql.window import Window
from delta.tables import DeltaTable

# Colunas rastreadas para detectar mudanças (definidas pelo usuário)
TRACKED_COLS: list[str] = {{tracked_cols}}

# --- Leitura da Bronze: registro mais recente por chave ---
# Resolve duplicatas mantendo a versão mais recente por _ingestion_timestamp.
window_dedup = Window.partitionBy("{{business_key}}").orderBy(F.desc("_ingestion_timestamp"))

df_novos = (
    spark.read.table("{{bronze_table_name}}")
    .withColumn("_row_num", F.row_number().over(window_dedup))
    .filter(F.col("_row_num") == 1)
    .drop("_row_num")
)

# --- Hash das colunas rastreadas para detectar mudanças ---
# Comparar hash é mais eficiente que comparar coluna a coluna no MERGE.
df_novos = df_novos.withColumn(
    "_scd_hash",
    F.md5(F.concat_ws("|", *[F.coalesce(F.col(c).cast("string"), F.lit("")) for c in TRACKED_COLS]))
)

now = F.current_timestamp()

# --- Primeira carga: inicializa a tabela SCD2 ---
if not DeltaTable.isDeltaTable(spark, f"Tables/{{silver_scd2_table_name}}"):
    df_inicial = (
        df_novos
        .withColumn("scd_valid_from", now)
        .withColumn("scd_valid_to", F.lit(None).cast("timestamp"))
        .withColumn("scd_is_current", F.lit(True))
        .withColumn("_updated_at", now)
    )
    df_inicial.write \
        .format("delta") \
        .mode("overwrite") \
        .option("overwriteSchema", "true") \
        .saveAsTable("{{silver_scd2_table_name}}")
    print("Tabela SCD2 inicializada (primeira carga).")
else:
    scd2_dt = DeltaTable.forName(spark, "{{silver_scd2_table_name}}")

    # MERGE em duas etapas:
    # 1) Expira o registro atual quando o hash mudou (whenMatchedUpdate com condição)
    # 2) Insere o novo registro como scd_is_current=True (whenNotMatched)
    (
        scd2_dt.alias("target")
        .merge(
            df_novos.alias("source"),
            "target.{{business_key}} = source.{{business_key}} AND target.scd_is_current = true"
        )
        # Expira o registro atual apenas quando alguma coluna rastreada mudou
        .whenMatchedUpdate(
            condition="target._scd_hash <> source._scd_hash",
            set={
                "scd_valid_to":  "source._ingestion_timestamp",
                "scd_is_current": "false",
                "_updated_at":    "current_timestamp()",
            }
        )
        # Insere novos registros (chave nunca vista ou chave expirada no passo anterior)
        .whenNotMatchedInsert(
            values={
                **{col: f"source.{col}" for col in df_novos.columns if not col.startswith("_scd")},
                "scd_valid_from":  "source._ingestion_timestamp",
                "scd_valid_to":    "null",
                "scd_is_current":  "true",
                "_scd_hash":       "source._scd_hash",
                "_updated_at":     "current_timestamp()",
            }
        )
        .execute()
    )
    print("SCD2 MERGE executado com sucesso.")

# --- Validação pós-carga ---
spark.sql(f"""
    SELECT scd_is_current, COUNT(*) AS total
    FROM {{silver_scd2_table_name}}
    GROUP BY scd_is_current
    ORDER BY scd_is_current DESC
""").show()
```

---

## Gold

### `gold-star-schema-fact`

**Descrição:** Constrói a tabela fato Gold fazendo INNER JOIN com TODAS as dimensões
relacionadas. Segue a regra mandatória: `fact_*` NUNCA deriva apenas da Silver sem
os JOINs de dimensão. Escreve com V-Order e executa OPTIMIZE após a carga.

**Variáveis:**
- `{{fact_table_name}}` — nome da tabela fato (ex: `fact_vendas`)
- `{{silver_fact_table}}` — tabela Silver transacional (ex: `silver_pedidos`)
- `{{dim_cliente_table}}` — tabela dimensão cliente (ex: `dim_cliente`)
- `{{dim_produto_table}}` — tabela dimensão produto (ex: `dim_produto`)
- `{{dim_data_table}}` — tabela dimensão data (ex: `dim_data`)
- `{{fact_date_col}}` — coluna de data da fact (ex: `data_pedido`)
- `{{cluster_col}}` — coluna para CLUSTER BY (ex: `data_pedido`)

**Tipo de célula:** `code`

```python
# ============================================================
# Gold — Tabela Fato com Star Schema
# Destino: {{fact_table_name}}
# Origem : {{silver_fact_table}} + dimensões
# Regra  : INNER JOIN com TODAS as dimensões (nunca LEFT JOIN em dims)
# ============================================================
from pyspark.sql import functions as F

# --- Construção da tabela fato via SparkSQL ---
# INNER JOIN garante integridade referencial: registros sem dimensão correspondente
# são descartados (sinalizar para investigação se count divergir do Silver).
df_fact = spark.sql("""
    SELECT
        -- Chaves de dimensão (surrogate keys)
        cli.sk_cliente,
        prod.sk_produto,
        dat.sk_data,

        -- Métricas da fato
        f.pedido_id,
        f.quantidade,
        f.valor_unitario,
        f.valor_total,
        f.desconto,

        -- Atributos degenerados (sem dimensão própria)
        f.canal_venda,
        f.status_pedido,

        -- Metadado de controle
        current_timestamp() AS _gold_updated_at

    FROM {{silver_fact_table}} f

    -- INNER JOIN obrigatório com dimensão cliente
    INNER JOIN {{dim_cliente_table}} cli
        ON f.cliente_id = cli.cliente_id
       AND cli.scd_is_current = true

    -- INNER JOIN obrigatório com dimensão produto
    INNER JOIN {{dim_produto_table}} prod
        ON f.produto_id = prod.produto_id

    -- INNER JOIN obrigatório com dimensão data
    INNER JOIN {{dim_data_table}} dat
        ON CAST(f.{{fact_date_col}} AS DATE) = dat.data_completa
""")

# --- Escrita com V-Order explícito ---
# V-Order otimiza a leitura pelo Direct Lake / Power BI.
df_fact.write \
    .format("delta") \
    .mode("overwrite") \
    .option("overwriteSchema", "true") \
    .option("vorder", "true") \
    .saveAsTable("{{fact_table_name}}")

# --- OPTIMIZE após escrita para consolidar arquivos ---
spark.sql("OPTIMIZE {{fact_table_name}} ZORDER BY ({{cluster_col}})")

# --- Validação: comparar contagem com Silver ---
count_silver = spark.sql("SELECT COUNT(*) FROM {{silver_fact_table}}").collect()[0][0]
count_fact   = spark.sql("SELECT COUNT(*) FROM {{fact_table_name}}").collect()[0][0]
perda = count_silver - count_fact

print(f"Silver  : {count_silver:,} registros")
print(f"Fato    : {count_fact:,} registros")
print(f"Perda   : {perda:,} registros (sem dimensao correspondente)")
if perda / count_silver > 0.01:
    print("ATENCAO: perda superior a 1% — investigar integridade referencial.")
```

---

### `gold-star-schema-dim`

**Descrição:** Constrói uma tabela dimensão Gold a partir da Silver, aplicando
enriquecimento de atributos e geração de surrogate key. A dimensão é sempre uma
entidade independente — nunca derivada diretamente de uma tabela transacional Silver.

**Variáveis:**
- `{{dim_table_name}}` — nome da dimensão (ex: `dim_cliente`)
- `{{silver_entity_table}}` — tabela Silver da entidade (ex: `silver_clientes`)
- `{{business_key}}` — chave de negócio (ex: `cliente_id`)
- `{{sk_col}}` — nome da surrogate key (ex: `sk_cliente`)
- `{{cluster_col}}` — coluna para CLUSTER BY (ex: `segmento`)

**Tipo de célula:** `code`

```python
# ============================================================
# Gold — Dimensão Star Schema
# Destino: {{dim_table_name}}
# Origem : {{silver_entity_table}} (entidade independente)
# Regra  : dim_* NUNCA derivam de tabelas transacionais Silver.
# ============================================================
from pyspark.sql import functions as F

# --- Leitura da Silver da entidade (somente registros correntes em SCD2) ---
df_silver = spark.read.table("{{silver_entity_table}}") \
    .filter(F.col("scd_is_current") == True)

# --- Construção da dimensão Gold ---
df_dim = (
    df_silver
    # Surrogate key: hash determinístico da chave de negócio
    # Garante reprodutibilidade sem depender de sequências auto-incrementais.
    .withColumn(
        "{{sk_col}}",
        F.conv(F.substring(F.md5(F.col("{{business_key}}").cast("string")), 1, 8), 16, 10).cast("bigint")
    )
    # Timestamp de atualização Gold
    .withColumn("_gold_updated_at", F.current_timestamp())
    # Remover colunas internas da Silver (prefixo _ exceto sk e _gold_updated_at)
    .drop("_ingestion_timestamp", "_source_file", "_source_system", "_updated_at", "_scd_hash")
)

# --- Escrita com V-Order ---
df_dim.write \
    .format("delta") \
    .mode("overwrite") \
    .option("overwriteSchema", "true") \
    .option("vorder", "true") \
    .saveAsTable("{{dim_table_name}}")

# OPTIMIZE para consolidar arquivos e otimizar leitura
spark.sql("OPTIMIZE {{dim_table_name}} ZORDER BY ({{cluster_col}})")

count = spark.sql("SELECT COUNT(*) AS total FROM {{dim_table_name}}").collect()[0]["total"]
print(f"Dimensao {{dim_table_name}} carregada com {count:,} registros.")
```

---

### `gold-dim-calendario`

**Descrição:** Gera a dimensão calendário de forma sintética usando `SEQUENCE` + `EXPLODE`.
Esta abordagem é OBRIGATÓRIA — nunca use `SELECT DISTINCT data FROM silver_*`, pois isso
cria dependência de dados transacionais e gera um calendário incompleto (apenas datas com
transações, sem datas futuras ou passadas sem eventos).

**Variáveis:**
- `{{start_date}}` — data de início do calendário (ex: `2020-01-01`)
- `{{end_date}}` — data de fim do calendário (ex: `2030-12-31`)
- `{{dim_data_table}}` — nome da tabela destino (ex: `dim_data`)
- `{{locale_holiday}}` — locale para feriados nacionais (ex: `BR` para Brasil)

**Tipo de célula:** `code`

```python
# ============================================================
# Gold — Dimensão Calendário (Geração Sintética via SEQUENCE)
# Destino: {{dim_data_table}}
# Período: {{start_date}} a {{end_date}}
#
# REGRA CRITICA: geração OBRIGATÓRIA via SEQUENCE + EXPLODE.
# NUNCA use SELECT DISTINCT data FROM silver_* — isso criaria
# um calendário incompleto dependente de dados transacionais.
# ============================================================
from pyspark.sql import functions as F
from pyspark.sql.types import BooleanType
import pandas as pd

# --- Geração do range de datas via SEQUENCE ---
# SEQUENCE gera um array com todas as datas entre start e end (inclusive).
# EXPLODE transforma o array em linhas individuais.
df_datas = spark.sql("""
    SELECT explode(
        sequence(
            DATE '{{start_date}}',
            DATE '{{end_date}}',
            INTERVAL 1 DAY
        )
    ) AS data_completa
""")

# --- Enriquecimento com atributos calendário ---
df_calendario = (
    df_datas
    .withColumn("sk_data",           F.date_format("data_completa", "yyyyMMdd").cast("int"))
    .withColumn("ano",                F.year("data_completa"))
    .withColumn("semestre",           F.ceil(F.month("data_completa") / 6).cast("int"))
    .withColumn("trimestre",          F.quarter("data_completa"))
    .withColumn("mes",                F.month("data_completa"))
    .withColumn("nome_mes",           F.date_format("data_completa", "MMMM"))
    .withColumn("semana_ano",         F.weekofyear("data_completa"))
    .withColumn("dia_mes",            F.dayofmonth("data_completa"))
    .withColumn("dia_semana_num",     F.dayofweek("data_completa"))   # 1=Dom, 7=Sab
    .withColumn("nome_dia_semana",    F.date_format("data_completa", "EEEE"))
    .withColumn("e_fim_de_semana",    F.dayofweek("data_completa").isin([1, 7]))
    .withColumn("ano_mes",            F.date_format("data_completa", "yyyy-MM").cast("string"))
    .withColumn("ano_trimestre",      F.concat_ws("-T", F.year("data_completa"), F.quarter("data_completa")))
    .withColumn("primeiro_dia_mes",   F.trunc("data_completa", "MM"))
    .withColumn("ultimo_dia_mes",     F.last_day("data_completa"))
    .withColumn("_gold_updated_at",   F.current_timestamp())
)

# --- Marcação de feriados nacionais via pandas UDF ---
# A biblioteca 'holidays' precisa estar instalada no cluster.
# Para instalar: %pip install holidays
@F.pandas_udf(BooleanType())
def is_feriado_nacional(datas: pd.Series) -> pd.Series:
    try:
        import holidays
        feriados = holidays.country_holidays("{{locale_holiday}}")
        return datas.apply(lambda d: d in feriados)
    except ImportError:
        # Se a biblioteca não estiver disponível, retorna False para todas as datas
        return pd.Series([False] * len(datas))

df_calendario = df_calendario.withColumn(
    "e_feriado_nacional",
    is_feriado_nacional(F.col("data_completa"))
)

# --- Escrita com V-Order ---
df_calendario.write \
    .format("delta") \
    .mode("overwrite") \
    .option("overwriteSchema", "true") \
    .option("vorder", "true") \
    .saveAsTable("{{dim_data_table}}")

spark.sql("OPTIMIZE {{dim_data_table}}")

count = spark.sql("SELECT COUNT(*) AS total FROM {{dim_data_table}}").collect()[0]["total"]
print(f"Dimensao calendario gerada com {count:,} datas ({{start_date}} a {{end_date}}).")
```

---

### `gold-optimize-vacuum`

**Descrição:** Célula de manutenção para tabelas Gold. Executa `OPTIMIZE` (consolida
small files, melhora performance do Direct Lake) e `VACUUM` (remove versões antigas,
libera storage). Deve ser executada após cargas significativas ou de forma agendada.

**Variáveis:**
- `{{gold_tables}}` — lista Python de tabelas a manter (ex: `["fact_vendas", "dim_cliente", "dim_data"]`)
- `{{vacuum_retain_hours}}` — horas de retenção para o VACUUM (mínimo 168 = 7 dias)
- `{{zorder_col}}` — coluna para Z-ORDER no OPTIMIZE (ex: `data_pedido`)

**Tipo de célula:** `code`

```python
# ============================================================
# Gold — Manutenção: OPTIMIZE + VACUUM
# Tabelas: {{gold_tables}}
# Retencao VACUUM: {{vacuum_retain_hours}} horas
# ============================================================

# Tabelas Gold que receberão manutenção
GOLD_TABLES: list[str] = {{gold_tables}}

# Retenção mínima recomendada: 168h (7 dias) para permitir time travel de auditoria.
# Nunca use valor abaixo de 168h em produção.
VACUUM_RETAIN_HOURS: int = {{vacuum_retain_hours}}

# Desabilita o guard de segurança do VACUUM somente se a retenção for >= 168h
if VACUUM_RETAIN_HOURS < 168:
    raise ValueError(
        f"vacuum_retain_hours={VACUUM_RETAIN_HOURS} esta abaixo do minimo recomendado de 168h. "
        "Ajuste o parametro para pelo menos 168."
    )

print(f"Iniciando manutencao de {len(GOLD_TABLES)} tabelas Gold...")
print(f"Retencao VACUUM: {VACUUM_RETAIN_HOURS}h\n")

resultados = []

for table in GOLD_TABLES:
    print(f"--- {table} ---")

    # OPTIMIZE: consolida small files em arquivos maiores.
    # Critico para performance do Direct Lake no Power BI.
    print(f"  OPTIMIZE {table}...")
    spark.sql(f"OPTIMIZE {table} ZORDER BY ({{zorder_col}})")

    # VACUUM: remove versoes Delta mais antigas que a janela de retencao.
    # Libera espaco no OneLake e reduz custo de storage.
    print(f"  VACUUM {table} RETAIN {VACUUM_RETAIN_HOURS} HOURS...")
    spark.sql(f"VACUUM {table} RETAIN {VACUUM_RETAIN_HOURS} HOURS")

    # Registra estatísticas pós-manutenção
    stats = spark.sql(f"""
        DESCRIBE DETAIL {table}
    """).select("numFiles", "sizeInBytes").collect()[0]

    resultados.append({
        "tabela": table,
        "num_files": stats["numFiles"],
        "size_mb": round(stats["sizeInBytes"] / 1024 / 1024, 2),
    })
    print(f"  Resultado: {stats['numFiles']} arquivos | {round(stats['sizeInBytes']/1024/1024, 2)} MB\n")

print("Manutencao concluida.")
print("\nResumo:")
for r in resultados:
    print(f"  {r['tabela']}: {r['num_files']} arquivos | {r['size_mb']} MB")
```

---

## Utilidade

### `markdown-header`

**Descrição:** Célula markdown padrão para o cabeçalho de notebooks Fabric. Define título,
descrição, camada, responsável e data de criação para documentação e rastreabilidade.

**Variáveis:**
- `{{notebook_title}}` — título do notebook (ex: `Silver — Pedidos`)
- `{{notebook_description}}` — descrição do propósito (ex: `Pipeline de limpeza e upsert da entidade Pedidos Bronze → Silver`)
- `{{layer}}` — camada Medallion (ex: `Silver`)
- `{{owner}}` — responsável pelo notebook (ex: `time-dados@empresa.com.br`)
- `{{created_date}}` — data de criação (ex: `2026-04-09`)
- `{{source_tables}}` — tabelas de entrada (ex: `bronze_pedidos`)
- `{{target_tables}}` — tabelas de saída (ex: `silver_pedidos`)

**Tipo de célula:** `markdown`

```markdown
# {{notebook_title}}

**Descricao:** {{notebook_description}}

---

| Atributo         | Valor                    |
|------------------|--------------------------|
| Camada           | {{layer}}                |
| Responsavel      | {{owner}}                |
| Criado em        | {{created_date}}         |
| Tabelas entrada  | `{{source_tables}}`      |
| Tabelas saida    | `{{target_tables}}`      |
| Plataforma       | Microsoft Fabric         |
| Formato          | Delta Lake               |

---

> **Aviso:** este notebook faz parte da arquitetura Medallion.
> Nao execute celulas fora de ordem. Consulte o pipeline-architect antes de alterar a logica de MERGE ou SCD.
```

---

### `data-profiling-quick`

**Descrição:** Profiling rápido de uma tabela Delta: contagem total, percentual de nulls
por coluna, contagem de distintos e min/max para colunas numéricas e de data. Útil para
validação pós-carga e exploração de novas fontes.

**Variáveis:**
- `{{table_name}}` — tabela a ser perfilada (ex: `silver_pedidos`)
- `{{sample_fraction}}` — fração para amostragem em tabelas grandes (ex: `1.0` para 100%, `0.1` para 10%)

**Tipo de célula:** `code`

```python
# ============================================================
# Utilidade — Data Profiling Rapido
# Tabela: {{table_name}}
# Amostra: {{sample_fraction}} (1.0 = 100% dos dados)
# ============================================================
from pyspark.sql import functions as F
from pyspark.sql.types import NumericType, DateType, TimestampType

TABELA: str = "{{table_name}}"
SAMPLE: float = float("{{sample_fraction}}")

print(f"Profiling: {TABELA} (amostra={SAMPLE*100:.0f}%)\n")

# --- Carregamento (com amostragem opcional para tabelas grandes) ---
df = spark.read.table(TABELA)
total_rows = df.count()

if SAMPLE < 1.0:
    df_sample = df.sample(fraction=SAMPLE, seed=42)
    print(f"Amostra aplicada: {df_sample.count():,} de {total_rows:,} registros.\n")
else:
    df_sample = df
    print(f"Total de registros: {total_rows:,}\n")

# --- Analise de nulls por coluna ---
print("=" * 60)
print("NULLS POR COLUNA")
print("=" * 60)

null_exprs = [
    F.round(F.sum(F.col(c).isNull().cast("int")) / F.count("*") * 100, 2).alias(c)
    for c in df_sample.columns
]
df_nulls = df_sample.select(null_exprs)

# Transpoe o resultado para exibicao legivel
rows = df_nulls.collect()[0].asDict()
for col_name, pct in sorted(rows.items(), key=lambda x: -x[1]):
    flag = " [ATENCAO]" if pct > 5 else ""
    print(f"  {col_name:<40} {pct:>6.2f}%{flag}")

# --- Contagem de valores distintos ---
print("\n" + "=" * 60)
print("DISTINTOS POR COLUNA")
print("=" * 60)

distinct_exprs = [F.countDistinct(c).alias(c) for c in df_sample.columns]
df_distincts = df_sample.select(distinct_exprs)
rows_d = df_distincts.collect()[0].asDict()
for col_name, cnt in sorted(rows_d.items(), key=lambda x: -x[1]):
    print(f"  {col_name:<40} {cnt:>10,}")

# --- Min/Max para colunas numericas e de data ---
print("\n" + "=" * 60)
print("MIN / MAX (numericas e datas)")
print("=" * 60)

cols_numericas = [
    f.name for f in df_sample.schema.fields
    if isinstance(f.dataType, (NumericType, DateType, TimestampType))
]

if cols_numericas:
    minmax_exprs = []
    for c in cols_numericas:
        minmax_exprs.extend([F.min(c).alias(f"min_{c}"), F.max(c).alias(f"max_{c}")])
    row_mm = df_sample.select(minmax_exprs).collect()[0].asDict()
    for c in cols_numericas:
        print(f"  {c:<40} min={row_mm[f'min_{c}']} | max={row_mm[f'max_{c}']}")
else:
    print("  Nenhuma coluna numerica ou de data encontrada.")

print("\nProfiling concluido.")
```

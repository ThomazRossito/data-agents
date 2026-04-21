# Exemplos Praticos: fabric-notebook-manager

> **Uso:** Exemplos prontos para copiar e adaptar. Todos seguem padroes do time
> (Medallion Architecture, V-Order, Delta Lake).

---

## Exemplo 1: Adicionar celula PySpark de leitura da tabela Bronze

Cenario: Voce tem um notebook Silver e precisa adicionar a celula que le os dados
da camada Bronze.

```python
from notebook_manager import add_cell

add_cell(
    workspace_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    item_id="11111111-2222-3333-4444-555555555555",
    source="""from pyspark.sql import functions as F

# Leitura incremental da Bronze (apenas registros novos)
last_watermark = spark.sql(
    "SELECT COALESCE(MAX(_updated_at), '1900-01-01') AS wm FROM silver.silver_orders"
).collect()[0]["wm"]

df_bronze = spark.read.table("bronze.bronze_orders") \\
    .filter(F.col("_ingestion_timestamp") > last_watermark)

print(f"Registros novos na Bronze: {df_bronze.count()}")
display(df_bronze.limit(5))""",
    cell_type="code",
    position=1  # Logo apos o header markdown
)
```

**Resultado esperado:**
```json
{"status": "success", "total_cells": 6, "new_cell_index": 1}
```

---

## Exemplo 2: Adicionar celula de configuracao Spark (V-Order, Optimize Write)

Cenario: Todo notebook Fabric de producao deve ter uma celula de configuracao no inicio,
habilitando V-Order e Optimize Write para performance maxima com Direct Lake.

```python
from notebook_manager import add_cell

add_cell(
    workspace_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    item_id="11111111-2222-3333-4444-555555555555",
    source="""# Configuracoes Spark para producao Fabric
# V-Order: otimiza layout Parquet para Direct Lake / Power BI
# Optimize Write: consolida small files automaticamente

spark.conf.set("spark.sql.parquet.vorder.enabled", "true")
spark.conf.set("spark.microsoft.delta.optimizeWrite.enabled", "true")
spark.conf.set("spark.microsoft.delta.optimizeWrite.binSize", "1073741824")  # 1GB

# Configuracao de retry para operacoes de escrita
spark.conf.set("spark.sql.files.ignoreMissingFiles", "true")

print("Configuracoes Spark aplicadas com sucesso.")""",
    cell_type="code",
    position=1  # Posicao 1: logo apos a celula markdown de titulo (posicao 0)
)
```

**Resultado esperado:**
```json
{"status": "success", "total_cells": 7, "new_cell_index": 1}
```

---

## Exemplo 3: Atualizar celula existente com nova query SQL

Cenario: A celula no indice 3 contem uma query de transformacao Silver que precisa
ser atualizada para incluir um novo filtro de data e uma coluna calculada.

```python
from notebook_manager import update_cell

update_cell(
    workspace_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    item_id="11111111-2222-3333-4444-555555555555",
    cell_index=3,
    new_source="""# Transformacao Silver -> Gold (atualizada com filtro de data)
df_gold = spark.sql(\"\"\"
    SELECT
        o.order_id,
        o.customer_id,
        d.date_key,
        o.order_date,
        o.amount,
        o.amount * 0.10 AS tax_amount,
        o.amount * 1.10 AS total_with_tax,
        c.region,
        c.segment,
        p.product_category,
        current_timestamp() AS _gold_updated_at
    FROM silver.silver_orders o
    INNER JOIN dim_data d ON o.order_date = d.full_date
    INNER JOIN dim_customer c ON o.customer_id = c.customer_id
    INNER JOIN dim_product p ON o.product_id = p.product_id
    WHERE o.order_date >= '2025-01-01'
\"\"\")

print(f"Registros Gold: {df_gold.count()}")
display(df_gold.limit(10))"""
)
```

**Resultado esperado:**
```json
{"status": "success", "cell_index": 3, "source_preview": "# Transformacao Silver -> Gold (atualizada com filtro de data)\ndf_gold = spark.sql(\"\"\"\n    SELECT\n   "}
```

---

## Exemplo 4: Remover celula de debug/teste

Cenario: Durante desenvolvimento, uma celula de debug foi adicionada no indice 5.
Antes de promover o notebook para producao, a celula deve ser removida.

Primeiro, verifique as celulas existentes para confirmar o indice:

```python
from notebook_manager import get_notebook_cells, delete_cell

# Passo 1: Listar celulas para confirmar qual remover
cells = get_notebook_cells(
    workspace_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    item_id="11111111-2222-3333-4444-555555555555"
)

for c in cells:
    print(f"[{c['index']}] {c['cell_type']:10s} | {c['source'][:60]}")

# Saida:
# [0] markdown   | # Pipeline Orders Bronze -> Silver -> Gold
# [1] code       | spark.conf.set("spark.sql.parquet.vorder.enabled", "true")
# [2] code       | df_bronze = spark.read.table("bronze.bronze_orders")
# [3] code       | df_silver = df_bronze.withColumn("order_date", F.to_date(
# [4] code       | df_silver.write.format("delta").mode("overwrite").saveAsTa
# [5] code       | # DEBUG: verificar schema -- REMOVER ANTES DE PRODUCAO
# [6] code       | spark.sql("OPTIMIZE silver.silver_orders")

# Passo 2: Confirmar e remover a celula de debug
delete_cell(
    workspace_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    item_id="11111111-2222-3333-4444-555555555555",
    cell_index=5
)
```

**Resultado esperado:**
```json
{"status": "success", "total_cells": 6, "removed_index": 5}
```

---

## Exemplo 5: Criar notebook do zero com 3 celulas

Cenario: Criar (ou reescrever completamente) um notebook de pipeline Bronze -> Silver
com 3 celulas: header markdown, configuracao Spark e codigo de transformacao.

> **Nota:** Este exemplo usa `replace_notebook_content`, que substitui TODAS as celulas
> do notebook. Use com cuidado -- o notebook deve ja existir no workspace (criado via
> UI ou API `createItem`).

```python
from notebook_manager import replace_notebook_content

cells = [
    {
        "source": "# Pipeline: Bronze -> Silver (Orders)\n\n"
                  "**Responsavel:** Time de Data Engineering\n"
                  "**Frequencia:** Diaria (06:00 BRT)\n"
                  "**Fonte:** bronze.bronze_orders\n"
                  "**Destino:** silver.silver_orders",
        "cell_type": "markdown"
    },
    {
        "source": "# Configuracoes de producao\n"
                  "spark.conf.set('spark.sql.parquet.vorder.enabled', 'true')\n"
                  "spark.conf.set('spark.microsoft.delta.optimizeWrite.enabled', 'true')\n"
                  "spark.conf.set('spark.microsoft.delta.optimizeWrite.binSize', '1073741824')\n"
                  "print('Configuracoes aplicadas.')",
        "cell_type": "code"
    },
    {
        "source": "from pyspark.sql import functions as F\n"
                  "from delta.tables import DeltaTable\n"
                  "\n"
                  "# Leitura incremental do Bronze\n"
                  "last_wm = spark.sql(\n"
                  "    \"SELECT COALESCE(MAX(_updated_at), '1900-01-01') FROM silver.silver_orders\"\n"
                  ").collect()[0][0]\n"
                  "\n"
                  "df_new = spark.read.table('bronze.bronze_orders') \\\n"
                  "    .filter(F.col('_ingestion_timestamp') > last_wm)\n"
                  "\n"
                  "# Transformacoes Silver\n"
                  "df_silver = df_new \\\n"
                  "    .withColumn('order_date', F.to_date('order_date_raw', 'yyyy-MM-dd')) \\\n"
                  "    .withColumn('amount', F.col('amount_raw').cast('double')) \\\n"
                  "    .withColumn('customer_id', F.trim(F.upper('customer_id_raw'))) \\\n"
                  "    .withColumn('_updated_at', F.current_timestamp()) \\\n"
                  "    .dropDuplicates(['order_id'])\n"
                  "\n"
                  "# MERGE na Silver\n"
                  "if DeltaTable.isDeltaTable(spark, 'Tables/silver_orders'):\n"
                  "    target = DeltaTable.forName(spark, 'silver.silver_orders')\n"
                  "    target.alias('t').merge(\n"
                  "        df_silver.alias('s'),\n"
                  "        't.order_id = s.order_id'\n"
                  "    ).whenMatchedUpdateAll() \\\n"
                  "     .whenNotMatchedInsertAll() \\\n"
                  "     .execute()\n"
                  "else:\n"
                  "    df_silver.write.format('delta').mode('overwrite').saveAsTable('silver.silver_orders')\n"
                  "\n"
                  "# Validacao\n"
                  "count = spark.read.table('silver.silver_orders').count()\n"
                  "print(f'silver.silver_orders: {count} registros')\n"
                  "\n"
                  "# Otimizacao pos-carga\n"
                  "spark.sql('OPTIMIZE silver.silver_orders')",
        "cell_type": "code"
    }
]

result = replace_notebook_content(
    workspace_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    item_id="11111111-2222-3333-4444-555555555555",
    cells=cells
)

print(result)
```

**Resultado esperado:**
```json
{"status": "success", "total_cells": 3}
```

---

## Dicas de Uso

### Descobrir workspace_id e item_id

Se voce nao tem os IDs memorizados, use as ferramentas MCP para descobri-los:

```python
# 1. Listar workspaces para encontrar o workspace_id
# -> mcp__fabric_official__list_workspaces()

# 2. Listar items do workspace para encontrar o notebook item_id
# -> mcp__fabric_official__list_items(workspace="meu-workspace", item_type="Notebook")
```

### Ordem recomendada de celulas em notebooks de producao

```
[0] markdown  -- Titulo, descricao, responsavel, frequencia
[1] code      -- Configuracoes Spark (V-Order, optimize write, etc.)
[2] code      -- Imports e funcoes auxiliares
[3] code      -- Leitura de dados (Bronze / fonte)
[4] code      -- Transformacoes (limpeza, tipagem, joins)
[5] code      -- Escrita no destino (Silver / Gold)
[6] code      -- Validacao e metricas (count, display sample)
[7] code      -- Otimizacao pos-carga (OPTIMIZE, VACUUM)
```

### Encadear multiplas operacoes

Para multiplas modificacoes no mesmo notebook, prefira `replace_notebook_content` em vez
de chamar `add_cell` varias vezes. Isso reduz de N ciclos `getDefinition/updateDefinition`
para apenas 1:

```python
# Ruim: N chamadas API (2*N+1 requests ao total)
add_cell(ws, nb, "celula 1")
add_cell(ws, nb, "celula 2")
add_cell(ws, nb, "celula 3")

# Bom: 1 chamada API (3 requests ao total)
replace_notebook_content(ws, nb, [
    {"source": "celula 1", "cell_type": "code"},
    {"source": "celula 2", "cell_type": "code"},
    {"source": "celula 3", "cell_type": "code"}
])
```

# SKILL: Microsoft Fabric + Databricks — Integração Cross-Platform

> **Fonte:** Microsoft Learn + Microsoft Fabric Blog + Databricks Documentation
> **Atualizado:** Janeiro 2026
> **Uso:** Leia este arquivo ANTES de projetar pipelines cross-platform entre Fabric e Databricks.

---

## Panorama da Integração em 2026

Microsoft e Databricks estabeleceram uma parceria de interoperabilidade que permite que ambas as plataformas trabalhem sobre **o mesmo dado Delta Lake**, sem duplicação. As integrações disponíveis são:

| Integração                         | Status (Jan 2026)  | Direção                    |
|------------------------------------|--------------------|----------------------------|
| Mirroring Databricks → OneLake     | ✅ GA              | Databricks → Fabric        |
| Shortcuts Fabric → ADLS            | ✅ GA              | Fabric lê dados externos   |
| Fabric Notebooks leem ADLS/Databricks ABFSS | ✅ GA    | Fabric lê diretamente      |
| Databricks lê OneLake (Unity Catalog) | Preview 2025   | Databricks → OneLake       |
| Iceberg REST Catalog (OneLake)     | Preview 2025       | Leitura Iceberg cross-platform |

---

## Estratégia 1: OneLake Shortcuts (Sem Movimentação de Dados)

Shortcuts são ponteiros de metadados no OneLake que apontam para dados em ADLS Gen2, S3, GCS ou outro OneLake. Dados **não são duplicados** — é referência virtual.

### Quando usar Shortcuts
- Dados já existem no ADLS Gen2 que o Databricks usa
- Databricks grava no ADLS, Fabric consome via Shortcut
- Zero ETL, latência mínima (Fabric lê direto da mesma storage)

### Como criar um Shortcut (via UI ou API)

```
Fabric Lakehouse → New Shortcut
  ├── Source: Azure Data Lake Storage Gen2
  ├── Connection: selecionar ADLS account do Databricks
  ├── Path: /mnt/databricks-delta/silver/orders/   (path do Unity Catalog)
  └── Name: "silver_orders_databricks"
```

```python
# Criação via Fabric REST API
import requests

workspace_id = "<FABRIC_WORKSPACE_ID>"
lakehouse_id = "<FABRIC_LAKEHOUSE_ID>"

payload = {
    "name": "silver_orders_databricks",
    "type": "AdlsGen2",
    "target": {
        "type": "AdlsGen2",
        "location": "https://<storage_account>.dfs.core.windows.net",
        "subpath": "/mnt/databricks/silver/orders"
    }
}

response = requests.post(
    f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}/lakehouses/{lakehouse_id}/shortcuts",
    headers={"Authorization": f"Bearer {token}"},
    json=payload
)
```

### Limitações dos Shortcuts
- Dados do Shortcut não são cobertos pelo OneLake security por padrão
- OPTIMIZE e VACUUM não podem ser executados pelo Fabric sobre tabelas Shortcut
- Para Direct Lake: tabelas via Shortcut precisam de V-Order ativo na escrita do Databricks

---

## Estratégia 2: Mirroring Databricks → Fabric (Zero-ETL)

O **Mirroring** sincroniza tabelas do Unity Catalog do Databricks para o OneLake automaticamente, mantendo os dados no formato Delta Lake. Não há duplicação física — o Fabric trabalha sobre a mesma storage via espelhamento de metadados.

### Configuração (via Fabric UI)

```
New Item → Mirrored Azure Databricks Catalog
  ├── Databricks workspace URL: https://<workspace>.azuredatabricks.net
  ├── Authentication: Service Principal ou OAuth
  ├── Unity Catalog: selecionar catálogo e schemas
  └── Tabelas: selecionar tabelas a espelhar (ou "All")
```

### O que o Mirroring suporta

| Feature                          | Suportado?                              |
|----------------------------------|-----------------------------------------|
| Tabelas Delta gerenciadas UC     | ✅ Sim                                  |
| Views do Unity Catalog           | ❌ Não (apenas tabelas)                |
| Atualização incremental (CDC)    | ✅ Sim (via Delta Change Data Feed)    |
| Tabelas externas Databricks      | ✅ Sim (se storage acessível)          |
| Controle de acesso OneLake       | ✅ GA (row/column level security)      |
| Latência de sincronização        | Segundos a minutos (quasi real-time)    |

### Acesso às tabelas espelhadas no Fabric

```python
# Após Mirroring configurado, tabelas ficam disponíveis no Lakehouse Fabric
# Acesso via Spark (Fabric Notebooks)
df = spark.read.table("mirrored_databricks.silver.orders")
df.show()

# Acesso via T-SQL (SQL Analytics Endpoint do Lakehouse)
# SELECT TOP 100 * FROM mirrored_databricks.silver.orders
```

---

## Estratégia 3: ABFSS Path Compartilhado

Quando Fabric e Databricks compartilham a **mesma Azure Data Lake Storage Gen2**, ambos podem ler e escrever no mesmo caminho ABFSS.

```python
# Databricks grava em ADLS
df_silver.write \
    .format("delta") \
    .mode("overwrite") \
    .save("abfss://silver@<storage_account>.dfs.core.windows.net/orders/")

# Fabric Notebook lê o mesmo path
df = spark.read.format("delta") \
    .load("abfss://silver@<storage_account>.dfs.core.windows.net/orders/")
```

### Autenticação no Fabric Notebook para ADLS externo

```python
# Via Service Principal (registrar nas configurações do workspace)
spark.conf.set(
    "fs.azure.account.auth.type.<storage>.dfs.core.windows.net", "OAuth"
)
spark.conf.set(
    "fs.azure.account.oauth.provider.type.<storage>.dfs.core.windows.net",
    "org.apache.hadoop.fs.azurebfs.oauth2.ClientCredsTokenProvider"
)
spark.conf.set(
    "fs.azure.account.oauth2.client.id.<storage>.dfs.core.windows.net",
    "<AZURE_CLIENT_ID>"
)
spark.conf.set(
    "fs.azure.account.oauth2.client.secret.<storage>.dfs.core.windows.net",
    "<AZURE_CLIENT_SECRET>"  # Usar Key Vault — NUNCA hardcode
)
spark.conf.set(
    "fs.azure.account.oauth2.client.endpoint.<storage>.dfs.core.windows.net",
    f"https://login.microsoftonline.com/<AZURE_TENANT_ID>/oauth2/token"
)
```

---

## Estratégia 4: Export OneLake → Volume Databricks (Fallback)

Quando não há storage compartilhado, use a API do OneLake para baixar arquivos e fazer upload para Databricks Volumes.

```python
# Baixar arquivo do OneLake via Fabric Files API
import requests

onelake_url = (
    f"https://onelake.dfs.fabric.microsoft.com"
    f"/{workspace_id}/{lakehouse_id}/Files/bronze/orders.parquet"
)
response = requests.get(onelake_url, headers={"Authorization": f"Bearer {token}"})

# Salvar localmente e fazer upload para Databricks Volume
with open("/tmp/orders.parquet", "wb") as f:
    f.write(response.content)

# No Databricks:
# dbutils.fs.cp("file:/tmp/orders.parquet", "dbfs:/Volumes/main/data/bronze/orders.parquet")
```

---

## Padrões de Pipeline Cross-Platform

### Padrão 1: Fabric é destino (Databricks processa → Fabric consome)

```
Fonte External
     │
     ▼
Databricks (Bronze → Silver → Gold via SDP/LakeFlow)
     │
     ├── Unity Catalog ADLS path
     │
     ▼
Fabric OneLake (via Shortcut ou Mirroring)
     │
     ▼
Power BI Direct Lake (zero cópia)
```

### Padrão 2: Fabric é origem (dados no OneLake → Databricks processa)

```
Fonte (ERP, API, SaaS)
     │
     ▼
Fabric Data Factory (Copy Activity → Lakehouse Bronze)
     │
     ▼
OneLake (Delta files)
     │  ← Shortcut ou ABFSS compartilhado
     ▼
Databricks (lê via Unity Catalog external location)
     │
     ▼
Processamento Spark avançado (ML, análises complexas)
     │
     ▼
Resultado de volta ao OneLake
```

### Padrão 3: Dual Write (ambos escrevem no mesmo storage)

```
Databricks Jobs → ADLS Gen2 (Silver, Gold em Delta)
Fabric Pipelines → mesmo ADLS Gen2 (Bronze)
Fabric Shortcuts → aponta para Silver/Gold do Databricks
Power BI → Direct Lake sobre Gold
```

---

## Considerações de Segurança Cross-Platform

| Aspecto                    | Recomendação                                                    |
|----------------------------|-----------------------------------------------------------------|
| Autenticação               | Service Principal com mínimo de permissões (Reader em ADLS)     |
| Credentials                | Azure Key Vault — nunca hardcode em notebooks                   |
| Acesso ao OneLake          | OneLake RBAC — configurar no Fabric Admin portal                |
| Network                    | VNet/Private Endpoint se dados sensíveis                        |
| Auditoria                  | Microsoft Purview para lineage cross-platform                   |

---

## Checklist Cross-Platform

- [ ] Estratégia de integração definida (Mirroring / Shortcut / ABFSS / Export)
- [ ] Service Principal com permissões mínimas criado
- [ ] Credentials em Key Vault (nunca hardcoded)
- [ ] V-Order habilitado na escrita Databricks (para Direct Lake no Fabric)
- [ ] Network connectivity validada (ADLS acessível de ambas as plataformas)
- [ ] Schema de tabelas compatível entre as plataformas (Delta Lake)
- [ ] Testes de leitura de ponta a ponta antes de produção

---

## Referências

- [Microsoft and Databricks interoperability](https://blog.fabric.microsoft.com/en-us/blog/microsoft-and-databricks-advancing-openness-and-interoperability-with-onelake)
- [Fabric Mirrored Azure Databricks](https://learn.microsoft.com/en-us/fabric/mirroring/azure-databricks-tutorial)
- [OneLake Shortcuts overview](https://learn.microsoft.com/en-us/fabric/onelake/onelake-shortcuts)
- [Integrate Fabric with external systems](https://learn.microsoft.com/en-us/fabric/fundamentals/external-integration)

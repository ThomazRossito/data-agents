---
name: fabric-cross-platform
description: Integração cross-platform Fabric + Databricks via Mirroring, Shortcut OneLake e Delta Lake compartilhado.
updated_at: 2026-04-23
source: web_search
---

# SKILL: Microsoft Fabric + Databricks — Integração Cross-Platform

> **Fonte:** Microsoft Learn + Microsoft Fabric Blog + Databricks Documentation
> **Atualizado:** Abril 2026
> **Uso:** Leia este arquivo ANTES de projetar pipelines cross-platform entre Fabric e Databricks.

---

## Panorama da Integração em 2026

Microsoft e Databricks estabeleceram uma parceria de interoperabilidade que permite que ambas as plataformas trabalhem sobre **o mesmo dado Delta Lake**, sem duplicação. As integrações disponíveis são:

| Integração                                              | Status (Abr 2026)         | Direção                         |
|---------------------------------------------------------|---------------------------|---------------------------------|
| Mirroring Databricks UC → OneLake                       | ✅ GA (jul 2025)          | Databricks → Fabric             |
| Shortcuts Fabric → ADLS / S3 / GCS                     | ✅ GA                     | Fabric lê dados externos        |
| Shortcut Transformations (Delta, AI transforms)         | ✅ GA (mar 2026)          | Fabric transforma ao importar   |
| Delegated Shortcuts (Entra identity, cross-tenant)      | Preview (mar 2026)        | OneLake → OneLake cross-tenant  |
| Fabric Notebooks leem ADLS/Databricks ABFSS             | ✅ GA                     | Fabric lê diretamente           |
| Databricks lê OneLake via UC Catalog Federation         | ✅ Public Preview (mar 2026) | Databricks → OneLake (read-only) |
| Databricks escreve direto no OneLake                    | Em desenvolvimento (roadmap) | Databricks → OneLake (write)  |
| Iceberg REST Catalog (OneLake ↔ Snowflake)              | ✅ GA (mar 2026)          | Leitura Iceberg cross-platform  |

> **Novidade FabCon 2026 (mar 2026):** A Microsoft e o Databricks trabalham conjuntamente para liberar escrita nativa do Databricks direto no OneLake — timeline a ser anunciado. A leitura do OneLake via Unity Catalog saiu de Beta para **Public Preview** e já suporta cargas de produção.

---

## Estratégia 1: OneLake Shortcuts (Sem Movimentação de Dados)

Shortcuts são ponteiros de metadados no OneLake que apontam para dados em ADLS Gen2, S3, GCS ou outro OneLake. Dados **não são duplicados** — é referência virtual.

> ⚠️ **Novidade GA (mar 2026):** **Shortcut Transformations** agora são GA. Ao criar um Shortcut, é possível aplicar transformações inline — conversão para Delta Lake, sumarização via AI, tradução e classificação de documentos — sem ETL separado. Além disso, **Delegated Shortcuts** (Preview) permitem apontar para dados em outro tenant do OneLake usando identidade Entra delegada.

### Quando usar Shortcuts
- Dados já existem no ADLS Gen2 que o Databricks usa
- Databricks grava no ADLS, Fabric consome via Shortcut
- Zero ETL, latência mínima (Fabric lê direto da mesma storage)
- Shortcut Transformations: quando você quer Delta Lake na chegada, sem pipeline extra

### Como criar um Shortcut (via UI ou API)

```
Fabric Lakehouse → New Shortcut
  ├── Source: Azure Data Lake Storage Gen2
  ├── Connection: selecionar ADLS account do Databricks
  ├── Path: /mnt/databricks-delta/silver/orders/   (path do Unity Catalog)
  ├── Name: "silver_orders_databricks"
  └── Transform (opcional): "Convert to Delta Lake"  ← novo passo GA mar/2026
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

### Discovery de tabelas Delta e Iceberg no Shortcut

Desde 2025, ao criar um Shortcut apontando para ADLS/S3, o OneLake faz **discovery automático** de tabelas Delta e Iceberg, permitindo navegar e selecionar tabelas diretamente na UI de criação do Shortcut. Não é necessário saber o path exato de cada tabela.

### Limitações dos Shortcuts
- OPTIMIZE e VACUUM não podem ser executados pelo Fabric sobre tabelas Shortcut (execute no Databricks)
- Para Direct Lake: tabelas via Shortcut precisam de V-Order ativo na escrita do Databricks
- Shortcuts externos usam **passthrough auth** (a identidade do usuário é passada ao sistema de origem) — o acesso é limitado pelo que o usuário tem no ADLS/storage subjacente
- Delegated Shortcuts (cross-tenant) ainda em Preview — não usar em produção crítica
- Nomes de tabelas com espaço não são reconhecidos como tabelas Delta no lakehouse

### OneLake Security com Shortcuts

O OneLake Security (Public Preview, caminhando para GA em 2026) permite definir roles com permissões de folder, row e column level diretamente no OneLake. Quando combinado com Shortcuts:
- Dados acessados via Shortcut ainda respeitam as regras de OneLake Security do lakehouse de origem
- Usuários downstream que consomem via Shortcut veem apenas o que o data owner permitiu
- Use OneLake Security para compartilhar dados via Shortcut sem criar cópias e sem perder controle de acesso

---

## Estratégia 2: Mirroring Databricks → Fabric (Zero-ETL)

> ⚠️ **Status atualizado:** Mirroring para Azure Databricks Unity Catalog atingiu **GA em julho de 2025** ("Unified by design"). O arquivo anterior listava o status como genérico — confirme que seu ambiente usa a versão GA.

O **Mirroring** sincroniza tabelas do Unity Catalog do Databricks para o OneLake automaticamente. Internamente, cria managed shortcuts para os mesmos dados Delta — sem duplicação física. Fabric trabalha sobre a mesma storage via espelhamento de metadados.

### Configuração (via Fabric UI)

```
New Item → Mirrored Azure Databricks Catalog
  ├── Databricks workspace URL: https://<workspace>.azuredatabricks.net
  ├── Authentication: Service Principal ou OAuth (Managed Identity preferível)
  ├── Unity Catalog: selecionar catálogo e schemas
  ├── Tabelas: selecionar tabelas a espelhar (ou "All")
  └── Auto metadata sync: habilitado por padrão — novas tabelas/schemas
      aparecem automaticamente no Fabric
```

**Pré-requisito no Databricks:** O metastore admin deve habilitar a configuração `External Data Access` no metastore Unity Catalog (desligada por padrão). O usuário/SP configurador precisa do privilégio `EXTERNAL USE SCHEMA` nos schemas a espelhar.

### O que o Mirroring suporta

| Feature                              | Suportado?                                         |
|--------------------------------------|----------------------------------------------------|
| Tabelas Delta gerenciadas UC         | ✅ Sim                                             |
| Tabelas externas UC                  | ✅ Sim (se storage acessível)                      |
| Views / Materialized Views UC        | ❌ Não (apenas tabelas físicas)                   |
| Atualização incremental (CDC)        | ✅ Sim (via Delta Change Data Feed)               |
| Auto-sync de novos schemas/tabelas   | ✅ Sim (habilitado por padrão)                    |
| Controle de acesso OneLake (RLS/CLS) | ✅ GA                                              |
| ADLS com firewall habilitado         | ✅ Sim (suporte a ADLS firewalled — GA)            |
| API pública (criar/gerenciar/monitorar) | ✅ Sim (integração com CI/CD)                   |
| Latência de sincronização            | Segundos a minutos (quasi real-time)               |

> ⚠️ **Importante sobre governança:** As permissões do Unity Catalog **não são transportadas automaticamente** para o Fabric. Você deve re-aplicar a governança no Fabric usando OneLake Security roles e RLS para os consumidores de BI. O SP/usuário configurador do Mirroring é a identidade usada para todas as interações com o Databricks workspace.

### Acesso às tabelas espelhadas no Fabric

```python
# Após Mirroring configurado, tabelas ficam disponíveis no Lakehouse Fabric
# Acesso via Spark (Fabric Notebooks)
df = spark.read.table("mirrored_databricks.silver.orders")
df.show()

# Acesso via T-SQL (SQL Analytics Endpoint do Lakehouse)
# SELECT TOP 100 * FROM mirrored_databricks.silver.orders

# Direct Lake (Power BI) — sem scheduled refresh, latência mínima
# Criar semantic model diretamente sobre o Mirrored item na UI do Fabric
```

---

## Estratégia 3: Databricks lê OneLake via Unity Catalog Catalog Federation

> ⚠️ **Breaking change de status (mar 2026):** O que era "Preview 2025" na versão anterior agora é **Public Preview** (anunciado no FabCon, março de 2026) e suportado para cargas de produção. A abordagem mudou: não é mais Iceberg REST Catalog genérico, mas **OneLake Catalog Federation** via Databricks Lakehouse Federation.

Permite que o Databricks leia tabelas do OneLake (Lakehouse ou Warehouse do Fabric) diretamente via Unity Catalog, **sem copiar dados**. O acesso é **read-only**.

### Requisitos

- Databricks Runtime **18.0 ou superior**, modo de acesso Standard
- SQL Warehouses versão **2025.40 ou superior**
- Fabric Admin: habilitar `Allow apps running outside of Fabric to access data via OneLake`
- No workspace Fabric: habilitar `Authenticate with OneLake user-delegated SAS tokens` (Workspace Settings → Delegated Settings → OneLake Settings)
- Autenticação recomendada: **Azure Managed Identity** via Databricks Access Connector (suporta mesmo tenant); Service Principal para cross-tenant

### Configuração (Databricks SQL / Notebook)

```sql
-- 1. Criar storage credential (via UI do Unity Catalog ou SQL)
-- (requer managed identity do Access Connector ou Service Principal)

-- 2. Criar connection para OneLake
CREATE CONNECTION onelake_connection
TYPE onelake
OPTIONS (
  workspace '<fabric-workspace-id>',
  credential '<storage-credential-name>'
);

-- 3. Criar foreign catalog apontando para item do Fabric
CREATE FOREIGN CATALOG fabric_silver
USING CONNECTION onelake_connection
OPTIONS (item '<fabric-lakehouse-or-warehouse-id>');

-- 4. Consultar normalmente via Unity Catalog
SELECT * FROM fabric_silver.schema_name.table_name LIMIT 100;
```

```python
# Acesso via PySpark no Databricks (DBR 18.0+)
df = spark.sql("SELECT * FROM fabric_silver.silver.orders")
df.show()
```

### Limitações (Public Preview)
- Acesso **read-only** — escrita nativa no OneLake via Databricks ainda em roadmap
- Views, Materialized Views e Streaming Tables do Fabric não são suportadas
- Delta Sharing catalogs e Lakehouse Federation catalogs não suportados
- Verificar [documentação de limitações do Beta](https://learn.microsoft.com/en-us/azure/databricks/query-federation/onelake) antes de usar em produção

---

## Estratégia 4: ABFSS Path Compartilhado

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

> **Alternativa recomendada 2026:** Use **Workspace Identity** no Fabric para autenticação sem credenciais armazenadas. Serviços como Shortcuts, Pipelines, Semantic Models e Dataflows Gen2 podem usar a Workspace Identity para acessar fontes protegidas sem armazenar ou rotacionar chaves.

---

## Estratégia 5: Export OneLake → Volume Databricks (Fallback)

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

> **Nota:** Esta estratégia (Fallback) deve ser usada apenas quando Mirroring, Shortcuts ou ABFSS compartilhado não são viáveis. Prefira as estratégias zero-copy sempre que possível.

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
Fabric OneLake (via Mirroring [preferido] ou Shortcut)
     │
     ▼
Power BI Direct Lake (zero cópia, sem scheduled refresh)
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
     │  ← UC Catalog Federation (Public Preview, read-only)
     │    ou ABFSS compartilhado
     ▼
Databricks (lê via Unity Catalog — DBR 18.0+)
     │
     ▼
Processamento Spark avançado (ML, análises complexas)
     │
     ▼
Resultado de volta ao OneLake (via ABFSS ou [futuro] write nativo)
```

### Padrão 3: Dual Write (ambos escrevem no mesmo storage)

```
Databricks Jobs → ADLS Gen2 (Silver, Gold em Delta)
Fabric Pipelines → mesmo ADLS Gen2 (Bronze)
Fabric Shortcuts → aponta para Silver/Gold do Databricks
Power BI → Direct Lake sobre Gold
```

### Padrão 4 (novo): Mirroring bidirecional com OneLake como hub

```
Azure Databricks (Unity Catalog)
     │
     ├─── Mirroring (GA) ──────────────────►  Fabric OneLake
     │                                              │
     │                                         Power BI Direct Lake
     │                                         Fabric Notebooks / SQL
     │
     │◄── UC Catalog Federation (Preview) ────  Fabric Lakehouse / Warehouse
          (read-only, DBR 18.0+)
```

---

## Considerações de Segurança Cross-Platform

| Aspecto                    | Recomendação                                                                           |
|----------------------------|----------------------------------------------------------------------------------------|
| Autenticação               | Workspace Identity (preferido) ou Service Principal com mínimo de permissões           |
| Credentials                | Azure Key Vault — nunca hardcode em notebooks. Integração nativa com OneLake Shortcuts |
| Acesso ao OneLake          | OneLake Security (Preview → GA 2026): roles com folder/row/column permissions          |
| Governança cross-platform  | Permissões UC **não** são herdadas no Fabric — re-aplicar OneLake Security roles       |
| Network                    | VNet/Private Endpoint se dados sensíveis; ADLS com firewall suportado no Mirroring GA  |
| Auditoria                  | Microsoft Purview para lineage cross-platform                                           |
| Outbound Access Protection | OAP (GA para Spark/SQL Endpoints) — restringe conexões de saída a endpoints aprovados  |

---

## Checklist Cross-Platform

- [ ] Estratégia de integração definida (Mirroring / Shortcut / UC Federation / ABFSS / Export)
- [ ] Service Principal ou Workspace Identity com permissões mínimas criado
- [ ] Credentials em Key Vault (nunca hardcoded)
- [ ] V-Order habilitado na escrita Databricks (para Direct Lake no Fabric)
- [ ] Network connectivity validada (ADLS acessível de ambas as plataformas)
- [ ] Schema de tabelas compatível entre as plataformas (Delta Lake)
- [ ] `External Data Access` habilitado no metastore UC do Databricks (para Mirroring)
- [ ] `EXTERNAL USE SCHEMA` concedido ao SP/usuário configurador do Mirroring
- [ ] OneLake Security roles re-definidas no Fabric (UC permissions não propagam)
- [ ] Para UC Catalog Federation: DBR 18.0+ e setting `user-delegated SAS tokens` ativo
- [ ] Testes de leitura de ponta a ponta antes de produção

---

## Referências

- [Unified by design: Mirroring Azure Databricks UC → Fabric (GA, jul 2025)](https://blog.fabric.microsoft.com/en-us/blog/unified-by-design-mirroring-azure-databricks-unity-catalog-in-microsoft-fabric-now-generally-available)
- [Zero-copy access to OneLake in Azure Databricks (Preview, fev 2026)](https://blog.fabric.microsoft.com/en-us/blog/zero-copy-access-to-onelake-data-in-azure-databricks-preview)
- [Enable OneLake catalog federation — Azure Databricks Docs](https://learn.microsoft.com/en-us/azure/databricks/query-federation/onelake)
- [FabCon 2026: What's new in Microsoft OneLake (mar 2026)](https://blog.fabric.microsoft.com/en-us/blog/fabcon-and-sqlcon-2026-whats-new-in-microsoft-onelake/)
- [Microsoft and Databricks — Advancing Openness and Interoperability (nov 2025)](https://blog.fabric.microsoft.com/en-us/blog/microsoft-and-databricks-advancing-openness-and-interoperability-with-onelake)
- [Fabric Mirrored Azure Databricks — Tutorial](https://learn.microsoft.com/en-us/fabric/mirroring/azure-databricks-tutorial)
- [OneLake Shortcuts overview](https://learn.microsoft.com/en-us/fabric/onelake/onelake-shortcuts)
- [Understanding OneLake Security with Shortcuts](https://blog.fabric.microsoft.com/en-us/blog/understanding-onelake-security-with-shortcuts/)
- [Use Microsoft Fabric to read Unity Catalog data — Databricks Docs](https://learn.microsoft.com/en-us/azure/databricks/partners/bi/fabric)

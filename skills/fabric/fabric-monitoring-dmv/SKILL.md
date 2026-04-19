---
name: fabric-monitoring-dmv
description: Monitoramento de modelos semânticos Fabric via DMV/TMSCHEMA no endpoint XMLA — refreshes, saúde do modelo e capacidade.
updated_at: 2026-04-16
---

# SKILL: fabric-monitoring-dmv

> **Fonte:** Microsoft Fabric XMLA Endpoint (pyadomd, Power BI API)
> **Atualizado:** Abril 2026
> **Uso:** Leia este arquivo ANTES de monitorar modelos semanticos Fabric via DMV.

---

## Overview

Monitora modelos semanticos Fabric e capacidade programaticamente via DMV (Dynamic Management Views) --
executa queries TMSCHEMA contra endpoint XMLA, monitora refreshes, consulta saude de modelo e
capacidade utilizada via REST API.

### O Problema

Monitoramento manual de modelo semantico Fabric (saude, partitions, memoria, refresh status)
requer conexao direta a endpoint XMLA com pyadomd ou DAX Studio, e nao escala para multiplos modelos.
Alem disso, rastrear historico de refresh e correlacionar com capacidade consumida requer multiplas
fontes de dados (DMV + Power BI API).

### A Solucao

Esta skill encapsula monitoramento completo:

- Conexao via XMLA endpoint com credenciais SPN ou User
- Queries DMV (TMSCHEMA_TABLES, TMSCHEMA_PARTITIONS, TMSCHEMA_MEASURES, etc)
- Monitoramento de refresh (status, tempo, historico)
- Consultas DAX customizadas contra modelo
- Analise de tamanho de modelo, partitions, overhead de memoria
- Integracao com Power BI API para refresh scheduling

**Resultado:** Observabilidade completa de modelo semantico com 1-2 queries encapsuladas.

---

## Quick Start

Exemplo mais comum -- conectar a XMLA, obter partitions enriquecidas e status de refresh:

```python
from monitoring_dmv import (
    set_dmv_connection_string_spn,
    dmv_fetch_partitions_enriched,
    get_semantic_model_refreshes
)

# 1. Construir connection string
conn_str = set_dmv_connection_string_spn(
    client_id="00000000-0000-0000-0000-000000000001",
    client_secret="your-secret",
    tenant_id="00000000-0000-0000-0000-000000000002",
    workspace_name="analytics",
    semantic_model_name="SalesModel"
)

# 2. Obter partitions enriquecidas
partitions_df = dmv_fetch_partitions_enriched(conn_str)
print(f"Partitions: {len(partitions_df)}")
print(partitions_df[['TableName', 'Name', 'RefreshedTime']])

# 3. Obter historico de refresh
refreshes = get_semantic_model_refreshes(
    workspace="analytics",
    semantic_model="SalesModel",
    top=10
)
print(f"Ultimos refreshes: {refreshes}")
```

---

## Common Patterns

### 1. `set_dmv_connection_string_spn` -- Connection com SPN

Constrói connection string para XMLA endpoint com Service Principal.

**Parametros:**

| Parametro          | Tipo | Obrigatorio | Descricao                  |
|--------------------|------|-------------|----------------------------|
| `client_id`        | str  | Sim         | Application ID do SPN      |
| `client_secret`    | str  | Sim         | Client secret do SPN       |
| `tenant_id`        | str  | Sim         | Tenant ID do Azure         |
| `workspace_name`   | str  | Sim         | Nome do workspace Fabric   |
| `semantic_model_name` | str | Sim        | Nome do modelo semantico   |

**Fluxo interno:**
1. Validar parametros nao vazios
2. Construir connection string com formato XMLA/ADOMD
3. Retorna string pronta para pyadomd

**Exemplo:**

```python
from monitoring_dmv import set_dmv_connection_string_spn

conn_str = set_dmv_connection_string_spn(
    client_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    client_secret="secret123",
    tenant_id="bbbbbbbb-cccc-dddd-eeee-ffffffffffff",
    workspace_name="DataLake",
    semantic_model_name="FactSales"
)
# conn_str: Data Source=powerbi://api.powerbi.com/v1.0/myorg/DataLake;Initial Catalog=FactSales;...
```

---

### 2. `set_dmv_connection_string_user` -- Connection com User

Constrói connection string com credenciais de usuario (AAD).

**Parametros:**

| Parametro          | Tipo | Obrigatorio | Descricao                 |
|--------------------|------|-------------|---------------------------|
| `user_email`       | str  | Sim         | Email do usuario AAD       |
| `password`         | str  | Sim         | Senha do usuario           |
| `workspace_name`   | str  | Sim         | Nome do workspace Fabric   |
| `semantic_model_name` | str | Sim        | Nome do modelo semantico   |

**Fluxo interno:**
1. Construir connection string com user_email e password
2. Retorna string pronta para pyadomd

**Exemplo:**

```python
from monitoring_dmv import set_dmv_connection_string_user

conn_str = set_dmv_connection_string_user(
    user_email="analyst@company.com",
    password="userpassword",
    workspace_name="DataLake",
    semantic_model_name="FactSales"
)
```

---

### 3. `dmv_fetch_partitions_enriched` -- Obter partitions com metadata

Consulta TMSCHEMA_PARTITIONS e enriquece com nomes de tabelas.

**Parametros:**

| Parametro | Tipo | Obrigatorio | Descricao       |
|-----------|------|-------------|-----------------|
| `conn_str` | str | Sim         | Connection string |

**Fluxo interno:**
1. Executar DMV query: `SELECT * FROM $SYSTEM.TMSCHEMA_PARTITIONS`
2. Executar DMV query: `SELECT * FROM $SYSTEM.TMSCHEMA_TABLES` para nomes
3. Merge (join) com TableID para preencher TableName
4. Retorna DataFrame sorted por TableName, RefreshedTime descendente

**Exemplo:**

```python
from monitoring_dmv import dmv_fetch_partitions_enriched

partitions = dmv_fetch_partitions_enriched(conn_str)
for _, row in partitions.iterrows():
    print(f"{row['TableName']} | {row['Name']} | {row['RefreshedTime']}")
```

---

### 4. `evaluate_dmv_queries` -- Executar query DMV customizada

Executa query DMV customizada contra modelo semantico.

**Parametros:**

| Parametro | Tipo | Obrigatorio | Descricao                 |
|-----------|------|-------------|---------------------------|
| `conn_str` | str | Sim         | Connection string XMLA    |
| `query`   | str  | Sim         | Query DMV (DAX/MDX)      |

**Fluxo interno:**
1. Conectar a XMLA endpoint via pyadomd
2. Executar query
3. Retorna DataFrame com resultados

**Exemplo:**

```python
from monitoring_dmv import evaluate_dmv_queries

query = """
SELECT
    TABLE_NAME as TableName,
    COLUMN_NAME as ColumnName,
    DATA_TYPE as DataType
FROM $SYSTEM.TMSCHEMA_COLUMNS
"""

cols = evaluate_dmv_queries(conn_str, query)
print(cols.head())
```

---

### 5. `get_semantic_model_refreshes` -- Historico de refresh via Power BI API

Obtem historico de operacoes de refresh de um modelo semantico via REST API.

**Parametros:**

| Parametro       | Tipo | Obrigatorio | Descricao                  |
|-----------------|------|-------------|----------------------------|
| `workspace`     | str  | Sim         | ID ou nome do workspace    |
| `semantic_model` | str  | Sim         | ID ou nome do modelo       |
| `top`           | int  | Nao         | Max resultados (padrao: todos) |

**Fluxo interno:**
1. Resolver workspace e modelo para IDs
2. `GET /v1/groups/{workspaceId}/datasets/{modelId}/refreshes`
3. Retorna lista com status, startTime, endTime, duration

**Exemplo:**

```python
from monitoring_dmv import get_semantic_model_refreshes

refreshes = get_semantic_model_refreshes(
    workspace="analytics",
    semantic_model="FactSales",
    top=20
)

for refresh in refreshes:
    print(f"{refresh['startTime']} | {refresh['status']} | {refresh.get('duration')}")
```

---

### 6. `refresh_semantic_model` -- Iniciar refresh via Power BI API

Inicia refresh de modelo semantico com opcoes customizadas.

**Parametros:**

| Parametro          | Tipo | Obrigatorio | Descricao                          |
|--------------------|------|-------------|-------------------------------------|
| `workspace`        | str  | Sim         | ID ou nome do workspace            |
| `semantic_model`   | str  | Sim         | ID ou nome do modelo               |
| `type`             | str  | Nao         | Full, DataOnly, Calculate, etc     |
| `notify_option`    | str  | Nao         | MailOnCompletion, NoNotification   |
| `objects`          | list | Nao         | Tables/partitions selecionadas     |

**Fluxo interno:**
1. Resolver workspace e modelo para IDs
2. Construir payload com type, notifyOption, objects
3. `POST /v1/groups/{workspaceId}/datasets/{modelId}/refreshes`
4. Retorna 202 Accepted

**Exemplo:**

```python
from monitoring_dmv import refresh_semantic_model

refresh_semantic_model(
    workspace="analytics",
    semantic_model="FactSales",
    type="Full",
    notify_option="MailOnCompletion",
    objects=[
        {"table": "FactSales", "partition": "2024"}
    ]
)
```

---

## Reference Files

- [dmv-queries.md](dmv-queries.md) -- Queries DMV comuns (TMSCHEMA), connection strings, DAX queries, refresh monitoring

---

## Common Issues

| Issue | Solution |
|-------|----------|
| **Pyadomd nao importa** | Instale: `pip install pyadomd`. Requer DAX Studio ou .NET Framework. |
| **Connection timeout (401)** | Token expirado ou SPN sem permissao. Renew credenciais. |
| **Query retorna vazio** | Modelo pode ser Import vs DirectLake. Verifique estrutura com TMSCHEMA_TABLES. |
| **Partition nao encontrada** | Modelo pode estar em modo DirectLake (sem partitions). Verifique TMSCHEMA_PARTITIONS. |
| **XMLA endpoint desabilitado** | Workspace deve ter XMLA read/write ativado (configuracao Fabric). |
| **Refresh retorna 202** | Refresh aceito; monitorar com `get_semantic_model_refreshes()` ate conclusao. |
| **DMV query syntax error** | Usar sintaxe DAX/DMV. Validar com `$SYSTEM.` prefix. |
| **User credentials prompt** | Interactive login necessario. Configure SPN para automacao. |

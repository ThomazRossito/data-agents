---
name: fabric-monitoring-dmv
description: Monitoramento de modelos semânticos Fabric via DMV/TMSCHEMA no endpoint XMLA — refreshes, saúde do modelo e capacidade.
updated_at: 2026-04-23
source: web_search
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

## Dependências e Versões

> ⚠️ **Breaking change em v19.82.0 (ADOMD):** O pacote NuGet foi renomeado. O novo pacote
> multi-runtime é `Microsoft.AnalysisServices.AdomdClient` (sem sufixo). Os pacotes legados
> `.retail.amd64` (Framework) e `.NetCore.retail.amd64` (Core) ainda existem no NuGet para
> compatibilidade, mas prefira o novo pacote unificado para projetos novos.

| Componente | Versão atual | Notas |
|---|---|---|
| `pyadomd` (PyPI) | `0.1.1` | Estável; sem breaking changes recentes |
| `Microsoft.AnalysisServices.AdomdClient` (NuGet) | `19.113.7` | Pacote multi-runtime recomendado |
| ADOMD `AccessToken` property | desde `19.67.0` | Permite OAuth token externo sem senha inline |
| ADOMD SPN Profiles | desde `19.82.0` | Para cenários multi-tenant; não funciona em PPU |

**Instalação pyadomd:**
```bash
pip install pyadomd
```
O pyadomd requer que o DLL do ADOMD.NET esteja no `sys.path` **antes** do import:

```python
from sys import path
path.append(r'C:\Program Files\Microsoft.NET\ADOMD.NET\150')
from pyadomd import Pyadomd
```

---

## XMLA Endpoint — Mudanças de Plataforma (2025)

> ⚠️ **Breaking change em junho 2025:** A partir de **9 de junho de 2025**, todos os SKUs
> de capacidade Fabric e Power BI passaram a ter XMLA **leitura e escrita habilitados por padrão**.
> Antes dessa data, capacidades no modo padrão só permitiam leitura, e admins precisavam habilitar
> manualmente o modo read/write. Se seu código verificava/forçava essa configuração, revise.

---

## Limitações de DMV via XMLA Endpoint

> ⚠️ **Restrição confirmada (sem versão específica — comportamento atual):**
> DMVs do tipo `$SYSTEM.DISCOVER_*` **não são suportados** via XMLA endpoint no Fabric/Power BI Premium.
> Apenas as famílias abaixo funcionam:
>
> - `$SYSTEM.TMSCHEMA_*` — metadados do modelo tabular (tabelas, partitions, measures, colunas, etc.)
> - `$SYSTEM.DMSCHEMA_*` — schema de mineração de dados
> - `$SYSTEM.MDSCHEMA_*` — schema multidimensional
>
> O DMV `$SYSTEM.DISCOVER_M_EXPRESSIONS` em particular **não é suportado** via XMLA; para obter
> expressões M, use o Tabular Object Model (TOM) diretamente.
>
> DMVs do tipo `$SYSTEM.DISCOVER_STORAGE_TABLE_COLUMN_SEGMENTS`, `$SYSTEM.DISCOVER_DB_CONNECTIONS`
> e similares retornam erro de permissão via XMLA endpoint — eles exigem permissão de server admin
> do Analysis Services, que não é concedida ao contexto Fabric.

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

**Formato da connection string SPN (ADOMD ≥ 19.67.0):**

```
Data Source=powerbi://api.powerbi.com/v1.0/myorg/<WorkspaceName>;
Initial Catalog=<ModelName>;
User ID=app:<client_id>@<tenant_id>;
Password=<client_secret>
```

> 💡 **Alternativa com AccessToken (ADOMD ≥ 19.67.0):** Se você já possui um token OAuth
> (ex: obtido via `azure-identity`), pode passar diretamente via propriedade `AccessToken`
> no objeto `AdomdConnection`, evitando expor `client_secret` na connection string.

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

> ⚠️ **Aviso:** Autenticação interativa (usuário/senha inline) não funciona em ambientes
> headless (ex: pipelines CI/CD, Databricks Jobs). Para automação, prefira SPN (`set_dmv_connection_string_spn`).

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

> ⚠️ **Limitação DMV:** `JOIN` não é suportado na sintaxe DMV — o merge é feito em Python
> (pandas), não na query. Nunca tente usar `JOIN` direto na DMV query; ela retornará erro de sintaxe.

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

> ⚠️ **Famílias DMV suportadas via XMLA Fabric:**
> Use **apenas** `$SYSTEM.TMSCHEMA_*`, `$SYSTEM.DMSCHEMA_*` ou `$SYSTEM.MDSCHEMA_*`.
> Queries contra `$SYSTEM.DISCOVER_*` retornam erro de permissão.
> Sintaxe DMV **não suporta** `JOIN`, `GROUP BY`, `LIKE`, `CAST` ou `CONVERT`.

**Exemplo:**

```python
from monitoring_dmv import evaluate_dmv_queries

# OK: TMSCHEMA_COLUMNS é suportado
query = """
SELECT
    TABLE_NAME as TableName,
    COLUMN_NAME as ColumnName,
    DATA_TYPE as DataType
FROM $SYSTEM.TMSCHEMA_COLUMNS
"""

cols = evaluate_dmv_queries(conn_str, query)
print(cols.head())

# EVITE: $SYSTEM.DISCOVER_STORAGE_TABLE_COLUMN_SEGMENTS retorna 403 via XMLA Fabric
# query = "SELECT * FROM $SYSTEM.DISCOVER_STORAGE_TABLE_COLUMN_SEGMENTS"  # NÃO FAÇA
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
2. `GET /v1.0/myorg/groups/{workspaceId}/datasets/{modelId}/refreshes`
3. Retorna lista com status, startTime, endTime, duration

> 💡 **Nota de nomenclatura da API:** A Power BI REST API ainda usa `datasets` na URL mesmo
> para modelos semânticos Fabric (o termo "dataset" não foi renomeado na URL). Isso é esperado
> e documentado; não troque por `semanticmodels`.

> ⚠️ **Avisos de refresh não aparecem na resposta da API:** Se o refresh foi iniciado via
> REST API, warnings são gravados no histórico mas os endpoints `Get Refresh History` e
> `Get Refresh Execution Details` **não retornam os warnings** na resposta JSON. Para inspecionar
> warnings, use XMLA (resposta inline) ou o Fabric Monitoring Hub.

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

> ⚠️ **Breaking change (comportamento confirmado 2025):** Para que o refresh seja classificado
> como **"enhanced refresh"** (e não refresh simples "via API"), o payload DEVE incluir pelo menos
> um dos parametros enhanced: `commitMode`, `maxParallelism`, `retryCount` ou `objects`.
> Além disso, o workspace **DEVE** estar em capacidade **Premium, PPU ou Fabric** — workspaces
> Shared/Pro não suportam enhanced refresh via SPN. Em Pro/Shared, SPN retorna 403.

**Parametros:**

| Parametro          | Tipo | Obrigatorio | Descricao                          |
|--------------------|------|-------------|-------------------------------------|
| `workspace`        | str  | Sim         | ID ou nome do workspace            |
| `semantic_model`   | str  | Sim         | ID ou nome do modelo               |
| `type`             | str  | Nao         | `Full`, `DataOnly`, `Calculate`, `Automatic`, etc |
| `notify_option`    | str  | Nao         | `MailOnCompletion`, `NoNotification` |
| `commit_mode`      | str  | Nao         | `transactional` ou `partialBatch` (enhanced) |
| `max_parallelism`  | int  | Nao         | Grau de paralelismo (enhanced)     |
| `retry_count`      | int  | Nao         | Tentativas em caso de falha (enhanced) |
| `objects`          | list | Nao         | Tables/partitions selecionadas (enhanced) |

**Fluxo interno:**
1. Resolver workspace e modelo para IDs
2. Construir payload com type, notifyOption e parametros enhanced (se fornecidos)
3. `POST /v1.0/myorg/groups/{workspaceId}/datasets/{modelId}/refreshes`
4. Retorna 202 Accepted; monitorar com `get_semantic_model_refreshes()`

**Exemplo — refresh simples:**

```python
from monitoring_dmv import refresh_semantic_model

refresh_semantic_model(
    workspace="analytics",
    semantic_model="FactSales",
    type="Full",
    notify_option="MailOnCompletion"
)
```

**Exemplo — enhanced refresh (requer Premium/PPU/Fabric):**

```python
from monitoring_dmv import refresh_semantic_model

# Inclui commitMode/maxParallelism -> classificado como "via enhanced API"
refresh_semantic_model(
    workspace="analytics",
    semantic_model="FactSales",
    type="Full",
    commit_mode="transactional",
    max_parallelism=2,
    retry_count=1,
    objects=[
        {"table": "FactSales", "partition": "2024"}
    ]
)
```

> 💡 **Dica:** Enhanced refresh **não atualiza tile caches** automaticamente. Caches só
> são atualizados quando um usuario acessa o report. Considere isso em pipelines que
> dependem de caches atualizados imediatamente apos o refresh.

---

## Reference Files

- [dmv-queries.md](dmv-queries.md) -- Queries DMV comuns (TMSCHEMA), connection strings, DAX queries, refresh monitoring

---

## Common Issues

| Issue | Solution |
|-------|----------|
| **Pyadomd nao importa** | Instale: `pip install pyadomd`. Adicione o path do `Microsoft.AnalysisServices.AdomdClient.dll` ao `sys.path` **antes** do import. Pacote NuGet recomendado: `Microsoft.AnalysisServices.AdomdClient` ≥ 19.113.7. |
| **Connection timeout (401)** | Token expirado ou SPN sem permissao. Renew credenciais. TLS 1.2+ obrigatório — atualize o AdomdClient se necessário. |
| **Query retorna vazio** | Modelo pode ser Import vs DirectLake. Verifique estrutura com TMSCHEMA_TABLES. |
| **Partition nao encontrada** | Modelo pode estar em modo DirectLake (sem partitions). Verifique TMSCHEMA_PARTITIONS. |
| **XMLA endpoint desabilitado** | Desde junho 2025, XMLA read/write é padrão em todos os SKUs Fabric/Power BI. Se ainda estiver desabilitado, verifique configurações de capacidade no admin portal. |
| **Refresh retorna 202** | Refresh aceito; monitorar com `get_semantic_model_refreshes()` ate conclusao. |
| **DMV query syntax error** | Usar sintaxe DAX/DMV com `$SYSTEM.` prefix. DMV **não suporta** `JOIN`, `GROUP BY`, `LIKE`, `CAST` ou `CONVERT`. |
| **DMV retorna 403 (DISCOVER_*)** | `$SYSTEM.DISCOVER_*` DMVs não são suportados via XMLA Fabric (exigem server admin do AS). Use apenas `TMSCHEMA_*`, `DMSCHEMA_*` ou `MDSCHEMA_*`. |
| **DISCOVER_M_EXPRESSIONS não suportado** | Este DMV não é suportado via XMLA endpoint. Use Tabular Object Model (TOM) para obter expressões M. |
| **User credentials prompt** | Interactive login necessario. Configure SPN para automacao. |
| **Refresh retorna "via API" em vez de "via enhanced API"** | Inclua pelo menos um parametro enhanced no payload: `commitMode`, `maxParallelism`, `retryCount` ou `objects`. Workspace deve ser Premium/PPU/Fabric. |
| **SPN retorna 403 no refresh** | Refresh via SPN só funciona em workspaces Premium, PPU ou Fabric. Em workspaces Pro/Shared, use master user account como workaround. |
| **Warnings de refresh ausentes na resposta da API** | Esperado: os endpoints `Get Refresh History` e `Get Refresh Execution Details` não retornam warnings. Consulte o Fabric Monitoring Hub para inspeção detalhada. |

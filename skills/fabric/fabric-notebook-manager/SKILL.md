---
updated_at: "2026-04-16"
source: firecrawl + knowledge-base
status: current
---

# SKILL: fabric-notebook-manager

> **Fonte:** Microsoft Fabric REST API (api.fabric.microsoft.com/v1)
> **Atualizado:** Abril 2026
> **Uso:** Leia este arquivo ANTES de manipular notebooks Fabric programaticamente via REST API.

---

## Overview

Gerencia notebooks Microsoft Fabric programaticamente -- adiciona, edita, remove e lista
celulas via REST API (`getDefinition` / `updateDefinition`).

### O Problema

Modificar um notebook Fabric programaticamente exige 4 chamadas REST separadas:

1. `getDefinition` -- ler estado atual do notebook (retorna payload base64)
2. Decodificar base64, parsear JSON .ipynb, modificar as celulas
3. `updateDefinition` -- enviar o notebook atualizado (inicia Long Running Operation)
4. `getDefinition` -- validar que a mudanca foi aplicada corretamente

Esse fluxo consome tokens do agente e introduz complexidade desnecessaria quando repetido
multiplas vezes numa sessao.

### A Solucao

Esta skill encapsula o ciclo completo `getDefinition -> modificar -> updateDefinition -> validar`
em operacoes atomicas reutilizaveis. Cada operacao cuida internamente de:

- Decodificacao/codificacao base64 do payload
- Parsing do formato Jupyter Notebook (.ipynb)
- Aguardar o LRO (Long Running Operation) ate conclusao
- Validacao pos-escrita via re-leitura do notebook

**Resultado:** de ~4 chamadas manuais para 1 operacao encapsulada por modificacao.

---

## Criacao de Notebooks via API

Alem de editar notebooks existentes, e possivel criar notebooks diretamente via API usando
`createItem` com o payload de definition incluido na requisicao.

**Endpoint:**

```
POST /v1/workspaces/{workspaceId}/items
```

**Request body (criar notebook com definition inline):**

```json
{
  "displayName": "meu_notebook_pipeline",
  "type": "Notebook",
  "definition": {
    "format": "ipynb",
    "parts": [
      {
        "path": "artifact/notebook-content.py",
        "payload": "<base64-encoded-ipynb-json>",
        "payloadType": "InlineBase64"
      }
    ]
  }
}
```

> **Nota sobre o `path`:** O campo `path` no payload de Notebook usa
> `"artifact/notebook-content.py"` (prefixo `artifact/`). Ao fazer `getDefinition`
> a API retorna o mesmo path. Mantenha consistencia ao reconstruir o payload para
> `updateDefinition`.

> **Nota sobre o `format`:** A partir de 2024, o parametro `format=ipynb` pode ser
> passado como query string no `getDefinition` para garantir retorno no formato
> Jupyter Notebook padrao: `POST /getDefinition?format=ipynb`

**Exemplo Python -- criar notebook:**

```python
import base64
import json
import requests
from azure.identity import DefaultAzureCredential

def create_notebook(workspace_id: str, display_name: str, cells: list[dict]) -> str:
    """
    Cria um novo notebook Fabric com as celulas fornecidas.
    Retorna o item_id do notebook criado.
    """
    credential = DefaultAzureCredential()
    token = credential.get_token("https://api.fabric.microsoft.com/.default").token
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Montar o .ipynb
    notebook_json = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "language_info": {"name": "python"},
            "kernel_info": {"name": "synapse_pyspark"},
            "kernelspec": {
                "display_name": "Synapse PySpark",
                "language": "Python",
                "name": "synapse_pyspark"
            }
        },
        "cells": [_make_cell(c["source"], c.get("cell_type", "code")) for c in cells]
    }

    payload_b64 = base64.b64encode(
        json.dumps(notebook_json, ensure_ascii=False).encode("utf-8")
    ).decode("utf-8")

    body = {
        "displayName": display_name,
        "type": "Notebook",
        "definition": {
            "format": "ipynb",
            "parts": [
                {
                    "path": "artifact/notebook-content.py",
                    "payload": payload_b64,
                    "payloadType": "InlineBase64"
                }
            ]
        }
    }

    resp = requests.post(
        f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}/items",
        headers=headers,
        json=body
    )

    if resp.status_code == 202:
        # LRO -- aguardar
        operation_url = resp.headers["Location"]
        wait_for_lro(operation_url, headers)
        # Recuperar o item criado
        result_resp = requests.get(resp.headers.get("Location"), headers=headers)
        result_resp.raise_for_status()
        return result_resp.json().get("resourceLocation", "")

    resp.raise_for_status()
    return resp.json().get("id", "")
```

---

## Quick Start

Exemplo mais comum -- adicionar uma celula de codigo PySpark ao final de um notebook:

```python
from notebook_manager import add_cell

add_cell(
    workspace_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    item_id="11111111-2222-3333-4444-555555555555",
    source="df = spark.read.table('bronze.bronze_orders')\ndisplay(df.limit(10))",
    cell_type="code",
    position=None  # None = adiciona ao final
)
# Retorno: {"status": "success", "total_cells": 8, "new_cell_index": 7}
```

---

## Execucao de Notebooks via API (Run On-Demand)

Para executar um notebook programaticamente (disparar uma run sem Scheduled Job):

**Endpoint:**

```
POST /v1/workspaces/{workspaceId}/items/{itemId}/jobs/instances?jobType=RunNotebook
```

**Request body (opcional -- parametros do notebook):**

```json
{
  "executionData": {
    "parameters": {
      "param_date": {
        "value": "2026-04-16",
        "type": "string"
      },
      "param_env": {
        "value": "production",
        "type": "string"
      }
    }
  }
}
```

**Resposta (202 -- job iniciado):**

O header `Location` contem a URL para acompanhar o status da execucao:

```
Location: https://api.fabric.microsoft.com/v1/workspaces/{workspaceId}/items/{itemId}/jobs/instances/{jobInstanceId}
```

**Exemplo Python -- disparar e aguardar notebook:**

```python
import time
import requests
from azure.identity import DefaultAzureCredential

def run_notebook(
    workspace_id: str,
    item_id: str,
    parameters: dict | None = None,
    timeout: int = 600
) -> dict:
    """
    Dispara a execucao de um notebook e aguarda conclusao.
    Retorna o resultado do job instance.

    parameters: dict no formato {"nome_param": {"value": ..., "type": "string|int|bool|float"}}
    """
    credential = DefaultAzureCredential()
    token = credential.get_token("https://api.fabric.microsoft.com/.default").token
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    body = {}
    if parameters:
        body["executionData"] = {"parameters": parameters}

    url = (
        f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}"
        f"/items/{item_id}/jobs/instances?jobType=RunNotebook"
    )
    resp = requests.post(url, headers=headers, json=body)

    if resp.status_code not in (200, 202):
        resp.raise_for_status()

    job_url = resp.headers.get("Location")
    if not job_url:
        return resp.json()

    # Polling do status do job
    start = time.time()
    while time.time() - start < timeout:
        job_resp = requests.get(job_url, headers=headers)
        job_resp.raise_for_status()
        job_data = job_resp.json()
        status = job_data.get("status", "")

        if status == "Completed":
            return job_data
        elif status in ("Failed", "Cancelled", "Deduped"):
            raise RuntimeError(
                f"Notebook run falhou com status '{status}': "
                f"{job_data.get('failureReason', {}).get('message', 'sem detalhes')}"
            )

        retry_after = int(job_resp.headers.get("Retry-After", 10))
        time.sleep(retry_after)

    raise TimeoutError(f"Notebook run nao concluiu em {timeout} segundos")


# Exemplo de uso:
result = run_notebook(
    workspace_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    item_id="11111111-2222-3333-4444-555555555555",
    parameters={
        "param_date": {"value": "2026-04-16", "type": "string"},
        "param_env": {"value": "production", "type": "string"}
    }
)
print(result["status"])  # "Completed"
```

**Status possiveis do job:**
- `NotStarted` -- aguardando alocacao de recursos
- `InProgress` -- em execucao
- `Completed` -- concluido com sucesso
- `Failed` -- falhou (verificar `failureReason`)
- `Cancelled` -- cancelado pelo usuario ou sistema
- `Deduped` -- job duplicado descartado

---

## Common Patterns

### 1. `list_cells` -- Listar celulas do notebook

Leitura somente. Executa apenas `getDefinition` + decode (sem escrita).

**Parametros:**

| Parametro      | Tipo   | Obrigatorio | Descricao                          |
|----------------|--------|-------------|------------------------------------|
| `workspace_id` | str    | Sim         | ID do workspace Fabric             |
| `item_id`      | str    | Sim         | ID do notebook (ou notebook_name)  |

**Fluxo interno:**
1. `POST /v1/workspaces/{workspaceId}/items/{itemId}/getDefinition?format=ipynb`
2. Decodifica `definition.parts[].payload` de base64 para JSON
3. Retorna lista de celulas com indice, tipo e preview do conteudo

**Exemplo:**

```python
from notebook_manager import get_notebook_cells

cells = get_notebook_cells(
    workspace_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    item_id="11111111-2222-3333-4444-555555555555"
)

for i, cell in enumerate(cells):
    preview = cell["source"][:80] if cell["source"] else "(vazio)"
    print(f"[{i}] {cell['cell_type']:10s} | {preview}")

# Saida:
# [0] markdown   | # Pipeline Bronze -> Silver
# [1] code       | spark.conf.set("spark.sql.parquet.vorder.enabled", "true")
# [2] code       | df = spark.read.table("bronze.bronze_orders")
# [3] code       | df_silver.write.format("delta").mode("overwrite")...
```

---

### 2. `add_cell` -- Adicionar celula(s)

Adiciona uma ou mais celulas ao notebook em posicao especifica ou ao final.

**Parametros:**

| Parametro      | Tipo       | Obrigatorio | Descricao                                            |
|----------------|------------|-------------|------------------------------------------------------|
| `workspace_id` | str        | Sim         | ID do workspace Fabric                               |
| `item_id`      | str        | Sim         | ID do notebook                                       |
| `source`       | str / list | Sim         | Codigo da celula (str) ou lista de linhas            |
| `cell_type`    | str        | Nao         | `"code"` (padrao) ou `"markdown"`                    |
| `position`     | int / None | Nao         | Indice de insercao. `None` = final do notebook       |

**Fluxo interno:**
1. `getDefinition` -- obter estado atual
2. Decodificar base64, parsear JSON .ipynb
3. Construir objeto de celula no formato Jupyter e inserir no array `cells`
4. Recodificar para base64, chamar `updateDefinition`
5. Aguardar LRO ate `status == "Succeeded"`
6. `getDefinition` -- validar que a celula foi adicionada

**Exemplo:**

```python
from notebook_manager import add_cell

# Adicionar celula markdown no inicio (posicao 0)
add_cell(
    workspace_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    item_id="11111111-2222-3333-4444-555555555555",
    source="# Pipeline de Vendas\n\nProcessamento Bronze -> Silver -> Gold",
    cell_type="markdown",
    position=0
)

# Adicionar celula de codigo ao final
add_cell(
    workspace_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    item_id="11111111-2222-3333-4444-555555555555",
    source="display(spark.sql('SELECT count(*) FROM gold.fato_vendas'))",
    cell_type="code"
)
```

---

### 3. `update_cell` -- Atualizar celula existente

Atualiza o conteudo de uma celula identificada pelo indice.

**Parametros:**

| Parametro      | Tipo       | Obrigatorio | Descricao                                   |
|----------------|------------|-------------|---------------------------------------------|
| `workspace_id` | str        | Sim         | ID do workspace Fabric                      |
| `item_id`      | str        | Sim         | ID do notebook                              |
| `cell_index`   | int        | Sim         | Indice da celula a atualizar (0-based)      |
| `new_source`   | str / list | Sim         | Novo conteudo da celula                     |

**Fluxo interno:**
1. `getDefinition` -- obter estado atual
2. Decodificar e validar que `cell_index` esta dentro do range
3. Substituir `cells[cell_index]["source"]` pelo novo conteudo
4. Recodificar e chamar `updateDefinition`
5. Aguardar LRO
6. `getDefinition` -- validar mudanca

**Exemplo:**

```python
from notebook_manager import update_cell

# Atualizar celula no indice 2 com nova query
update_cell(
    workspace_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    item_id="11111111-2222-3333-4444-555555555555",
    cell_index=2,
    new_source="df = spark.sql('SELECT * FROM silver.silver_orders WHERE order_date >= \"2026-01-01\"')"
)
```

---

### 4. `delete_cell` -- Remover celula

Remove uma celula do notebook pelo indice.

**Parametros:**

| Parametro      | Tipo | Obrigatorio | Descricao                              |
|----------------|------|-------------|----------------------------------------|
| `workspace_id` | str  | Sim         | ID do workspace Fabric                 |
| `item_id`      | str  | Sim         | ID do notebook                         |
| `cell_index`   | int  | Sim         | Indice da celula a remover (0-based)   |

**Fluxo interno:**
1. `getDefinition` -- obter estado atual
2. Decodificar e validar que `cell_index` esta dentro do range
3. Remover `cells[cell_index]` do array
4. Recodificar e chamar `updateDefinition`
5. Aguardar LRO
6. `getDefinition` -- validar remocao

**Exemplo:**

```python
from notebook_manager import delete_cell

# Remover celula de debug no indice 4
delete_cell(
    workspace_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    item_id="11111111-2222-3333-4444-555555555555",
    cell_index=4
)
# Retorno: {"status": "success", "total_cells": 6, "removed_index": 4}
```

---

### 5. `replace_notebook` -- Substituir conteudo completo

Substitui todas as celulas do notebook por um novo conjunto.

**Parametros:**

| Parametro      | Tipo | Obrigatorio | Descricao                                        |
|----------------|------|-------------|--------------------------------------------------|
| `workspace_id` | str  | Sim         | ID do workspace Fabric                           |
| `item_id`      | str  | Sim         | ID do notebook                                   |
| `cells`        | list | Sim         | Lista de dicts `{"source": ..., "cell_type": ...}` |

**Fluxo interno:**
1. `getDefinition` -- obter estado atual (preservar metadata do notebook)
2. Decodificar, substituir array `cells` inteiro mantendo `metadata` e `nbformat`
3. Recodificar e chamar `updateDefinition`
4. Aguardar LRO
5. `getDefinition` -- validar que o numero de celulas corresponde

**Exemplo:**

```python
from notebook_manager import replace_notebook_content

cells = [
    {"source": "# Notebook Gerado Automaticamente", "cell_type": "markdown"},
    {"source": "spark.conf.set('spark.sql.parquet.vorder.enabled', 'true')", "cell_type": "code"},
    {"source": "df = spark.read.table('bronze.bronze_vendas')\ndisplay(df.limit(5))", "cell_type": "code"}
]

replace_notebook_content(
    workspace_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    item_id="11111111-2222-3333-4444-555555555555",
    cells=cells
)
# Retorno: {"status": "success", "total_cells": 3}
```

---

## Reference Files

- [notebook-operations.md](notebook-operations.md) -- Referencia tecnica completa: estrutura JSON .ipynb, API REST, codigo Python, tratamento de erros
- [examples.md](examples.md) -- Exemplos praticos de uso em cenarios reais de pipeline Medallion

---

## Common Issues

| Issue | Solution |
|-------|----------|
| **LRO retorna status "Failed"** | Verifique se o JSON .ipynb esta valido. Erros comuns: `source` como string ao inves de lista, `cell_type` invalido. Veja tratamento em [notebook-operations.md](notebook-operations.md). |
| **Notebook nao encontrado (404)** | Confirme `workspace_id` e `item_id`. Use `mcp__fabric_official__list_items` para buscar o ID correto do notebook. |
| **Indice fora do range** | Use `list_cells` antes de `update_cell` ou `delete_cell` para confirmar o numero de celulas existentes. |
| **Conflito de edicao concorrente (409)** | Outro usuario ou processo editou o notebook entre `getDefinition` e `updateDefinition`. Re-execute a operacao (retry automatico com backoff). |
| **Token expirado (401)** | Renove o Bearer token via Azure Identity / MSAL. Nunca hardcode tokens -- use Azure Key Vault ou Managed Identity. |
| **Timeout no LRO** | O padrao e 120 segundos de polling. Para notebooks grandes (>50 celulas), aumente o timeout para 300 segundos. |
| **Path incorreto no payload (400)** | Certifique-se de usar `"artifact/notebook-content.py"` como `path` (com prefixo `artifact/`). O path sem prefixo pode causar erro na API. |
| **Notebook run nao aceita parametros (400)** | Parametros devem incluir o campo `type` explicitamente: `{"value": "x", "type": "string"}`. Tipos validos: `string`, `int`, `bool`, `float`. |

---

## Changelog

### 2026-04-16 (refresh)
- Adicionada secao **Criacao de Notebooks via API** com `createItem` + definition inline
- Adicionada secao **Execucao de Notebooks via API (Run On-Demand)** com `jobs/instances?jobType=RunNotebook`, polling de status e parametrizacao
- Atualizado endpoint de `getDefinition` com parametro `?format=ipynb` (recomendado desde 2024)
- Corrigido `path` do payload para `"artifact/notebook-content.py"` (com prefixo `artifact/`)
- Adicionados dois novos itens em Common Issues: path incorreto e parametros de run
- Adicionado frontmatter com `updated_at`, `source` e `status`
- Adicionado `Changelog` como secao permanente

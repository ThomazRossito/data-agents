# Referencia Tecnica: Operacoes em Notebooks Fabric via REST API

> **Fonte:** Microsoft Fabric REST API (api.fabric.microsoft.com/v1)
> **Atualizado:** Abril 2026
> **Uso:** Referencia interna do skill `fabric-notebook-manager`. Consulte para detalhes de
> implementacao, estrutura JSON e tratamento de erros.

---

## 1. Estrutura do JSON .ipynb do Fabric

Notebooks Fabric seguem o formato Jupyter Notebook padrao (nbformat 4). O payload retornado
pela API esta codificado em base64 e, quando decodificado, possui a seguinte estrutura:

```json
{
  "nbformat": 4,
  "nbformat_minor": 5,
  "metadata": {
    "language_info": {
      "name": "python"
    },
    "a]]365_notebook_info": {
      "description": "",
      "isLakehouseDefault": true,
      "lakehouse": {
        "default_lakehouse": "<lakehouse-id>",
        "default_lakehouse_name": "lakehouse_silver",
        "default_lakehouse_workspace_id": "<workspace-id>"
      }
    },
    "kernel_info": {
      "name": "synapse_pyspark"
    },
    "kernelspec": {
      "display_name": "Synapse PySpark",
      "language": "Python",
      "name": "synapse_pyspark"
    }
  },
  "cells": [
    {
      "cell_type": "markdown",
      "metadata": {},
      "source": [
        "# Titulo do Notebook\n",
        "\n",
        "Descricao do pipeline."
      ]
    },
    {
      "cell_type": "code",
      "metadata": {},
      "source": [
        "df = spark.read.table('bronze.bronze_orders')\n",
        "display(df.limit(10))"
      ],
      "outputs": [],
      "execution_count": null
    }
  ]
}
```

### Detalhes dos campos de celula

| Campo             | Tipo       | Descricao                                                    |
|-------------------|------------|--------------------------------------------------------------|
| `cell_type`       | str        | `"code"` ou `"markdown"`. Fabric tambem aceita `"raw"`.     |
| `source`          | list[str]  | **Lista de strings**, cada elemento e uma linha do codigo. Quebras de linha incluem `\n` ao final de cada elemento exceto o ultimo. |
| `metadata`        | dict       | Metadata da celula. Pode conter `tags`, `name`, etc. Usar `{}` como padrao. |
| `outputs`         | list       | Apenas para `cell_type: "code"`. Lista de outputs de execucao. Usar `[]` para celulas novas. |
| `execution_count` | int / null | Apenas para `cell_type: "code"`. `null` para celulas nao executadas. |

**Regra critica:** O campo `source` e uma **lista de strings**, nao uma string unica.
Ao construir uma celula, converta o codigo-fonte com `source.split("\n")` e adicione `\n`
ao final de cada linha exceto a ultima:

```python
def format_source(code: str) -> list[str]:
    """Converte string de codigo para formato source do .ipynb."""
    lines = code.split("\n")
    formatted = [line + "\n" for line in lines[:-1]]
    formatted.append(lines[-1])  # ultima linha sem \n
    return formatted
```

---

## 2. API REST Fabric para Notebooks

### Base URL

```
https://api.fabric.microsoft.com/v1
```

### Headers obrigatorios

```python
headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json"
}
```

**Obtencao do token:** Use `azure.identity.DefaultAzureCredential` ou MSAL. Nunca hardcode
tokens. Para producao, use Azure Key Vault ou Managed Identity.

```python
from azure.identity import DefaultAzureCredential

credential = DefaultAzureCredential()
token = credential.get_token("https://api.fabric.microsoft.com/.default").token
```

---

### 2.1 `getDefinition` -- Ler notebook

**Endpoint:**

```
POST /v1/workspaces/{workspaceId}/items/{itemId}/getDefinition
```

> **Nota:** Apesar de ser uma operacao de leitura, o metodo HTTP e `POST` (nao `GET`).
> Isso ocorre porque a API pode retornar um LRO para notebooks grandes.

**Resposta (200 -- resposta direta):**

```json
{
  "definition": {
    "parts": [
      {
        "path": "notebook-content.py",
        "payload": "<base64-encoded-ipynb-json>",
        "payloadType": "InlineBase64"
      }
    ]
  }
}
```

**Resposta (202 -- Long Running Operation):**

Retorna header `Location` com URL para polling:

```
Location: https://api.fabric.microsoft.com/v1/operations/{operationId}
Retry-After: 5
```

Neste caso, faca polling ate obter o resultado (veja secao 2.3).

**Decodificacao do payload:**

```python
import base64
import json

payload_b64 = response_json["definition"]["parts"][0]["payload"]
notebook_json = json.loads(base64.b64decode(payload_b64).decode("utf-8"))
cells = notebook_json["cells"]
```

---

### 2.2 `updateDefinition` -- Atualizar notebook

**Endpoint:**

```
POST /v1/workspaces/{workspaceId}/items/{itemId}/updateDefinition
```

**Request body:**

```json
{
  "definition": {
    "parts": [
      {
        "path": "notebook-content.py",
        "payload": "<base64-encoded-ipynb-json>",
        "payloadType": "InlineBase64"
      }
    ]
  }
}
```

**Codificacao do payload:**

```python
import base64
import json

notebook_bytes = json.dumps(notebook_json, ensure_ascii=False).encode("utf-8")
payload_b64 = base64.b64encode(notebook_bytes).decode("utf-8")
```

**Resposta (200):** Atualizacao aplicada imediatamente (raro para notebooks grandes).

**Resposta (202):** Long Running Operation iniciada. Seguir polling (secao 2.3).

**Resposta (409):** Conflito -- notebook foi modificado por outro processo entre a leitura e
a escrita. Necessario retry com re-leitura.

---

### 2.3 Aguardar Long Running Operation (LRO)

Quando a API retorna 202, o header `Location` contem a URL do LRO:

```
Location: https://api.fabric.microsoft.com/v1/operations/{operationId}
```

**Polling:**

```python
import time
import requests

def wait_for_lro(operation_url: str, headers: dict, timeout: int = 120) -> dict:
    """Aguarda LRO ate conclusao ou timeout."""
    start = time.time()
    while time.time() - start < timeout:
        resp = requests.get(operation_url, headers=headers)
        resp.raise_for_status()
        result = resp.json()
        status = result.get("status", "")

        if status == "Succeeded":
            return result
        elif status in ("Failed", "Cancelled"):
            raise RuntimeError(
                f"LRO falhou com status '{status}': "
                f"{result.get('error', {}).get('message', 'sem detalhes')}"
            )

        # Respeitar Retry-After se presente, senao usar 3 segundos
        retry_after = int(resp.headers.get("Retry-After", 3))
        time.sleep(retry_after)

    raise TimeoutError(f"LRO nao concluiu em {timeout} segundos")
```

---

## 3. Codigo Python de Referencia

Todas as funcoes abaixo seguem o ciclo completo:
`getDefinition -> modificar -> updateDefinition -> aguardar LRO -> getDefinition (validar)`

### 3.0 Funcoes auxiliares compartilhadas

```python
import base64
import json
import time
import requests
from azure.identity import DefaultAzureCredential

BASE_URL = "https://api.fabric.microsoft.com/v1"

def _get_headers() -> dict:
    """Obtem headers com Bearer token renovado."""
    credential = DefaultAzureCredential()
    token = credential.get_token("https://api.fabric.microsoft.com/.default").token
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

def _format_source(code: str) -> list[str]:
    """Converte string para formato source .ipynb (lista de linhas)."""
    if not code:
        return [""]
    lines = code.split("\n")
    if len(lines) == 1:
        return [lines[0]]
    formatted = [line + "\n" for line in lines[:-1]]
    formatted.append(lines[-1])
    return formatted

def _make_cell(source: str, cell_type: str = "code") -> dict:
    """Cria objeto de celula no formato .ipynb."""
    cell = {
        "cell_type": cell_type,
        "metadata": {},
        "source": _format_source(source)
    }
    if cell_type == "code":
        cell["outputs"] = []
        cell["execution_count"] = None
    return cell

def _get_definition(workspace_id: str, item_id: str) -> dict:
    """Executa getDefinition e retorna o JSON do notebook decodificado."""
    headers = _get_headers()
    url = f"{BASE_URL}/workspaces/{workspace_id}/items/{item_id}/getDefinition"
    resp = requests.post(url, headers=headers)

    if resp.status_code == 202:
        # LRO -- aguardar
        operation_url = resp.headers["Location"]
        wait_for_lro(operation_url, headers)
        # Apos LRO, refazer a chamada para obter o resultado
        resp = requests.post(url, headers=headers)

    resp.raise_for_status()
    data = resp.json()
    payload_b64 = data["definition"]["parts"][0]["payload"]
    notebook_json = json.loads(base64.b64decode(payload_b64).decode("utf-8"))
    return notebook_json

def _update_definition(workspace_id: str, item_id: str, notebook_json: dict) -> None:
    """Executa updateDefinition com o notebook JSON e aguarda LRO."""
    headers = _get_headers()
    url = f"{BASE_URL}/workspaces/{workspace_id}/items/{item_id}/updateDefinition"

    notebook_bytes = json.dumps(notebook_json, ensure_ascii=False).encode("utf-8")
    payload_b64 = base64.b64encode(notebook_bytes).decode("utf-8")

    body = {
        "definition": {
            "parts": [
                {
                    "path": "notebook-content.py",
                    "payload": payload_b64,
                    "payloadType": "InlineBase64"
                }
            ]
        }
    }

    resp = requests.post(url, headers=headers, json=body)

    if resp.status_code == 202:
        operation_url = resp.headers["Location"]
        wait_for_lro(operation_url, headers)
    elif resp.status_code == 409:
        raise RuntimeError(
            "Conflito de edicao concorrente (409). "
            "O notebook foi modificado entre getDefinition e updateDefinition. "
            "Re-execute a operacao."
        )
    else:
        resp.raise_for_status()

def wait_for_lro(operation_url: str, headers: dict, timeout: int = 120) -> dict:
    """Aguarda LRO ate conclusao ou timeout com exponential backoff."""
    start = time.time()
    attempt = 0
    while time.time() - start < timeout:
        resp = requests.get(operation_url, headers=headers)
        resp.raise_for_status()
        result = resp.json()
        status = result.get("status", "")

        if status == "Succeeded":
            return result
        elif status in ("Failed", "Cancelled"):
            raise RuntimeError(
                f"LRO falhou com status '{status}': "
                f"{result.get('error', {}).get('message', 'sem detalhes')}"
            )

        retry_after = int(resp.headers.get("Retry-After", min(3 * (2 ** attempt), 30)))
        time.sleep(retry_after)
        attempt += 1

    raise TimeoutError(f"LRO nao concluiu em {timeout} segundos")
```

---

### 3.1 `get_notebook_cells` -- Listar celulas

```python
def get_notebook_cells(workspace_id: str, item_id: str) -> list[dict]:
    """
    Retorna lista de celulas do notebook com indice, tipo e conteudo.

    Fluxo: getDefinition -> decode -> retorna cells
    """
    notebook_json = _get_definition(workspace_id, item_id)
    cells = []
    for i, cell in enumerate(notebook_json.get("cells", [])):
        source_text = "".join(cell.get("source", []))
        cells.append({
            "index": i,
            "cell_type": cell.get("cell_type", "code"),
            "source": source_text,
            "metadata": cell.get("metadata", {})
        })
    return cells
```

---

### 3.2 `add_cell` -- Adicionar celula

```python
def add_cell(
    workspace_id: str,
    item_id: str,
    source: str,
    cell_type: str = "code",
    position: int | None = None
) -> dict:
    """
    Adiciona celula ao notebook.

    Fluxo: getDefinition -> inserir celula -> updateDefinition -> LRO -> validar
    """
    # 1. Ler estado atual
    notebook_json = _get_definition(workspace_id, item_id)

    # 2. Construir nova celula
    new_cell = _make_cell(source, cell_type)

    # 3. Inserir na posicao desejada
    if position is None:
        notebook_json["cells"].append(new_cell)
        inserted_at = len(notebook_json["cells"]) - 1
    else:
        if position < 0 or position > len(notebook_json["cells"]):
            raise IndexError(
                f"position={position} fora do range. "
                f"O notebook tem {len(notebook_json['cells'])} celulas (indices 0-{len(notebook_json['cells'])})"
            )
        notebook_json["cells"].insert(position, new_cell)
        inserted_at = position

    # 4. Enviar de volta
    _update_definition(workspace_id, item_id, notebook_json)

    # 5. Validar
    updated_notebook = _get_definition(workspace_id, item_id)
    total_cells = len(updated_notebook.get("cells", []))

    return {
        "status": "success",
        "total_cells": total_cells,
        "new_cell_index": inserted_at
    }
```

---

### 3.3 `update_cell` -- Atualizar celula existente

```python
def update_cell(
    workspace_id: str,
    item_id: str,
    cell_index: int,
    new_source: str
) -> dict:
    """
    Atualiza o conteudo de uma celula existente.

    Fluxo: getDefinition -> validar indice -> substituir source -> updateDefinition -> LRO -> validar
    """
    # 1. Ler estado atual
    notebook_json = _get_definition(workspace_id, item_id)
    cells = notebook_json.get("cells", [])

    # 2. Validar indice
    if cell_index < 0 or cell_index >= len(cells):
        raise IndexError(
            f"cell_index={cell_index} fora do range. "
            f"O notebook tem {len(cells)} celulas (indices 0-{len(cells) - 1})"
        )

    # 3. Substituir source
    notebook_json["cells"][cell_index]["source"] = _format_source(new_source)

    # 4. Enviar de volta
    _update_definition(workspace_id, item_id, notebook_json)

    # 5. Validar
    updated_notebook = _get_definition(workspace_id, item_id)
    updated_source = "".join(updated_notebook["cells"][cell_index].get("source", []))

    return {
        "status": "success",
        "cell_index": cell_index,
        "source_preview": updated_source[:120]
    }
```

---

### 3.4 `delete_cell` -- Remover celula

```python
def delete_cell(
    workspace_id: str,
    item_id: str,
    cell_index: int
) -> dict:
    """
    Remove uma celula do notebook pelo indice.

    Fluxo: getDefinition -> validar indice -> remover -> updateDefinition -> LRO -> validar
    """
    # 1. Ler estado atual
    notebook_json = _get_definition(workspace_id, item_id)
    cells = notebook_json.get("cells", [])

    # 2. Validar indice
    if cell_index < 0 or cell_index >= len(cells):
        raise IndexError(
            f"cell_index={cell_index} fora do range. "
            f"O notebook tem {len(cells)} celulas (indices 0-{len(cells) - 1})"
        )

    # 3. Remover celula
    original_count = len(cells)
    del notebook_json["cells"][cell_index]

    # 4. Enviar de volta
    _update_definition(workspace_id, item_id, notebook_json)

    # 5. Validar
    updated_notebook = _get_definition(workspace_id, item_id)
    new_count = len(updated_notebook.get("cells", []))

    if new_count != original_count - 1:
        raise RuntimeError(
            f"Validacao falhou: esperava {original_count - 1} celulas, "
            f"encontrou {new_count}"
        )

    return {
        "status": "success",
        "total_cells": new_count,
        "removed_index": cell_index
    }
```

---

### 3.5 `replace_notebook_content` -- Substituir conteudo completo

```python
def replace_notebook_content(
    workspace_id: str,
    item_id: str,
    cells: list[dict]
) -> dict:
    """
    Substitui todas as celulas do notebook mantendo metadata original.

    Parametro cells: lista de dicts com {"source": str, "cell_type": str}

    Fluxo: getDefinition -> preservar metadata -> substituir cells -> updateDefinition -> LRO -> validar
    """
    # 1. Ler estado atual (preservar metadata do notebook)
    notebook_json = _get_definition(workspace_id, item_id)

    # 2. Construir novo array de celulas
    new_cells = []
    for cell_def in cells:
        source = cell_def.get("source", "")
        cell_type = cell_def.get("cell_type", "code")
        new_cells.append(_make_cell(source, cell_type))

    # 3. Substituir celulas mantendo tudo mais (metadata, nbformat, etc.)
    notebook_json["cells"] = new_cells

    # 4. Enviar de volta
    _update_definition(workspace_id, item_id, notebook_json)

    # 5. Validar
    updated_notebook = _get_definition(workspace_id, item_id)
    actual_count = len(updated_notebook.get("cells", []))

    if actual_count != len(cells):
        raise RuntimeError(
            f"Validacao falhou: esperava {len(cells)} celulas, "
            f"encontrou {actual_count}"
        )

    return {
        "status": "success",
        "total_cells": actual_count
    }
```

---

## 4. Tratamento de Erros

### 4.1 LRO falhou (status "Failed")

```python
# O wait_for_lro ja levanta RuntimeError. O chamador deve tratar:
try:
    add_cell(workspace_id, item_id, source="print('hello')")
except RuntimeError as e:
    if "LRO falhou" in str(e):
        # Possivel causa: JSON .ipynb malformado
        # Acao: verificar estrutura do notebook e tentar novamente
        print(f"Erro no LRO: {e}")
```

**Causas comuns:**
- Campo `source` como string em vez de lista de strings
- `cell_type` com valor invalido (aceitos: `code`, `markdown`, `raw`)
- JSON malformado (encoding incorreto)

### 4.2 Notebook nao encontrado (404)

```python
# Quando item_id nao existe no workspace
try:
    cells = get_notebook_cells(workspace_id, item_id)
except requests.exceptions.HTTPError as e:
    if e.response.status_code == 404:
        print("Notebook nao encontrado. Verifique workspace_id e item_id.")
        # Use mcp__fabric_official__list_items para buscar IDs corretos
```

### 4.3 Indice fora do range

```python
# Todas as funcoes que recebem cell_index validam o range
try:
    update_cell(workspace_id, item_id, cell_index=99, new_source="...")
except IndexError as e:
    print(f"Indice invalido: {e}")
    # Use get_notebook_cells() para ver os indices disponiveis
```

### 4.4 Conflito de edicao concorrente (409)

```python
# _update_definition ja levanta RuntimeError para 409
# Estrategia: retry com re-leitura (maximo 3 tentativas)
MAX_RETRIES = 3

for attempt in range(MAX_RETRIES):
    try:
        add_cell(workspace_id, item_id, source="# nova celula")
        break
    except RuntimeError as e:
        if "409" in str(e) and attempt < MAX_RETRIES - 1:
            wait_seconds = 2 ** attempt  # exponential backoff: 1s, 2s, 4s
            time.sleep(wait_seconds)
            continue
        raise
```

### 4.5 Token expirado (401)

```python
# _get_headers() renova o token a cada chamada via DefaultAzureCredential.
# Se ainda assim receber 401:
# 1. Verifique que o Service Principal tem role "Contributor" no workspace
# 2. Verifique que o scope e "https://api.fabric.microsoft.com/.default"
# 3. Em ambientes locais, faca login via `az login` antes de executar
```

### 4.6 Timeout no LRO

```python
# Para notebooks grandes (>50 celulas), aumente o timeout:
# Edite wait_for_lro(..., timeout=300) nas funcoes auxiliares
# Ou passe o parametro diretamente se a implementacao aceitar
```

---

## 5. Otimizacao de Tokens

### Antes (sem esta skill) -- 4 chamadas por operacao

```
Chamada 1: Agente descreve como chamar getDefinition, monta URL, headers, etc.
Chamada 2: Agente descreve como parsear base64, montar a nova celula no formato .ipynb
Chamada 3: Agente descreve como codificar, chamar updateDefinition, aguardar LRO
Chamada 4: Agente descreve como validar via getDefinition final
```

Custo estimado: ~2000-3000 tokens por operacao (descricao + codigo + tratamento de erros).

### Depois (com esta skill) -- 1 chamada encapsulada

```
Chamada unica: add_cell(workspace_id, item_id, source="...", cell_type="code", position=2)
```

Custo estimado: ~200-400 tokens por operacao.

**Reducao: ~85-90% de tokens por operacao de notebook.**

Para sessoes que modificam multiplas celulas (ex: criar notebook do zero com 5-10 celulas),
a economia acumulada e ainda maior pois `replace_notebook_content` faz tudo em uma unica
chamada, independente do numero de celulas.

---

## Referencias

- [Fabric REST API -- Items: getDefinition](https://learn.microsoft.com/en-us/rest/api/fabric/core/items/get-item-definition)
- [Fabric REST API -- Items: updateDefinition](https://learn.microsoft.com/en-us/rest/api/fabric/core/items/update-item-definition)
- [Fabric REST API -- Long Running Operations](https://learn.microsoft.com/en-us/rest/api/fabric/core/long-running-operations)
- [Jupyter Notebook Format (nbformat 4)](https://nbformat.readthedocs.io/en/latest/format_description.html)
- [Azure Identity -- DefaultAzureCredential](https://learn.microsoft.com/en-us/python/api/azure-identity/azure.identity.defaultazurecredential)

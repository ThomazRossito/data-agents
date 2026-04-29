# Pattern: Fabric Lakehouse Setup

## Pré-requisitos
- Capacidade Fabric ativa (F2 mínimo)
- Workspace criado e associado à capacidade
- Permissões: Workspace Admin ou Member

## Estrutura OneLake
```
tenant
└── workspace: <env>-<domain>
    └── Lakehouse: <domain>_lh
        ├── Tables/         (Delta Parquet — gerenciadas pelo Fabric)
        └── Files/          (raw, landing zone)
```

## Criação via REST API
```python
import requests

WORKSPACE_ID = "..."
TOKEN = "..."

payload = {
    "displayName": "finance_lh",
    "description": "Lakehouse do domínio financeiro"
}

resp = requests.post(
    f"https://api.fabric.microsoft.com/v1/workspaces/{WORKSPACE_ID}/lakehouses",
    headers={"Authorization": f"Bearer {TOKEN}"},
    json=payload,
)
resp.raise_for_status()
lakehouse_id = resp.json()["id"]
```

## Shortcuts (OneLake Shortcuts)
Conectar dados externos sem copiar:
```python
# ADLS Gen2 Shortcut
shortcut_payload = {
    "path": "Files/external",
    "name": "adls_raw",
    "target": {
        "type": "AdlsGen2",
        "location": "https://mystorageaccount.dfs.core.windows.net",
        "subpath": "/container/raw"
    }
}

resp = requests.post(
    f"https://api.fabric.microsoft.com/v1/workspaces/{WORKSPACE_ID}"
    f"/lakehouses/{lakehouse_id}/shortcuts",
    headers={"Authorization": f"Bearer {TOKEN}"},
    json=shortcut_payload,
)
```

Tipos de shortcut suportados: `AdlsGen2`, `AmazonS3`, `GoogleCloudStorage`,
`OneLake` (cross-workspace), `DataverseLink`.

## Tabelas Delta no Lakehouse
```python
# Via Spark (notebook Fabric)
df.write.format("delta") \
    .mode("overwrite") \
    .saveAsTable("finance_lh.bronze_transaction")
```

## Direct Lake (modo Power BI)
Direct Lake lê diretamente do OneLake sem importar dados:
- Requisito: tabela Delta no Lakehouse (não Files/)
- Criar Semantic Model apontando para o Lakehouse
- Fallback automático para DirectQuery se tabela muito grande para cache

```
Direct Lake > Import (latência menor)
Direct Lake > DirectQuery (performance melhor em tabelas médias)
```

## Dataflow Gen2 (ingestão sem código)
- Conectar a 150+ fontes via Power Query
- Destino: Lakehouse Table (gravação Delta automática)
- Agendamento: via pipeline ou manual

## Pipeline Fabric (ADF-like)
```
Copy Activity → Lakehouse (destino)
  - Formato fonte: CSV, Parquet, JSON, ORC, Delta
  - Destino: Tables/ (gera Delta) ou Files/ (raw)
  - Partition: none | fixed | dynamic (por coluna)
```

## Anti-padrões
- NÃO gravar com Spark em Files/ e depois expor como Table → schema não gerenciado
- NÃO usar Import mode no Power BI se Direct Lake disponível
- NÃO criar shortcuts para dados que precisam de transformação antes de consumo
- NÃO ignorar throttling de CU → monitorar Fabric Capacity Metrics app

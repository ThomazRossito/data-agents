# Azure Integration

## Entra ID (Azure Active Directory)
- Databricks usa Entra ID como IdP principal
- Service Principals (SP) para automação/CI-CD
- Grupos Entra ID podem ser mapeados para workspace groups

```python
# Autenticar SP via Databricks SDK
from databricks.sdk import WorkspaceClient
w = WorkspaceClient(
    host="https://<workspace>.azuredatabricks.net",
    azure_client_id=os.environ["AZURE_CLIENT_ID"],
    azure_client_secret=os.environ["AZURE_CLIENT_SECRET"],
    azure_tenant_id=os.environ["AZURE_TENANT_ID"]
)
```

## ADLS Gen2 — Mount vs Unity Catalog

### Mount (legado, evitar em novos projetos)
```python
dbutils.fs.mount(
    source="abfss://container@account.dfs.core.windows.net/",
    mount_point="/mnt/datalake",
    extra_configs={"fs.azure.account.key.account.dfs.core.windows.net": key}
)
```

### Unity Catalog External Location (recomendado)
```sql
-- 1. Criar storage credential (uma vez por conta storage)
CREATE STORAGE CREDENTIAL my_adls_cred
USING AZURE_MANAGED_IDENTITY;

-- 2. Criar external location
CREATE EXTERNAL LOCATION my_data_lake
URL 'abfss://container@account.dfs.core.windows.net/'
WITH (STORAGE CREDENTIAL my_adls_cred);

-- 3. Criar tabela externa apontando para external location
CREATE TABLE prod.bronze.events
LOCATION 'abfss://container@account.dfs.core.windows.net/events/';
```

## Azure Key Vault — Secrets
```python
# Usar secret scope backed por Key Vault
secret = dbutils.secrets.get(scope="kv-databricks", key="my-secret-key")

# Criação do scope via CLI
databricks secrets create-scope \
  --scope kv-databricks \
  --scope-backend-type AZURE_KEYVAULT \
  --resource-id /subscriptions/.../vaults/my-vault \
  --dns-name https://my-vault.vault.azure.net/
```

## Managed Identity
Databricks accesses Azure resources via Managed Identity do cluster (sem credenciais hardcode):
- Access ADLS sem montar (Unity Catalog)
- Access Key Vault sem PAT
- Requer atribuição de `Storage Blob Data Contributor` no RBAC do storage

## Network — Private Link
```
Databricks workspace → Private Endpoint → ADLS Gen2
                                        → Azure SQL
                                        → Key Vault
```
- Bloquear acesso público em produção
- Usar NSG para controle de tráfego de saída

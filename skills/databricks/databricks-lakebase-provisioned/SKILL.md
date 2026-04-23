---
name: databricks-lakebase-provisioned
description: "Patterns and best practices for Lakebase Provisioned (Databricks managed PostgreSQL) for OLTP workloads. Use when creating Lakebase instances, connecting applications or Databricks Apps to PostgreSQL, implementing reverse ETL via synced tables, storing agent or chat memory, or configuring OAuth authentication for Lakebase."
updated_at: 2026-04-23
source: web_search
---

# Lakebase Provisioned

Patterns and best practices for using Lakebase Provisioned (Databricks managed PostgreSQL) for OLTP workloads.

> ⚠️ **Breaking change em 2026-03-12 — "Autoscaling by default":**
> A partir de 12 de março de 2026, todas as novas instâncias Lakebase são criadas como **projetos Lakebase Autoscaling**, mesmo quando você usa a API `w.database.create_database_instance()` ou o CLI. Instâncias existentes de Lakebase Provisioned **não são afetadas** e continuam funcionando normalmente. Automation existente continua operando, mas novas instâncias rodam na plataforma Autoscaling com precificação Autoscaling. Capacity units (`CU_1`, `CU_2`, `CU_4`, `CU_8`) são mapeados automaticamente para ranges de CU do Autoscaling. Veja [Autoscaling by default](https://docs.databricks.com/aws/en/oltp/upgrade-to-autoscaling) para detalhes completos.
>
> Novo desenvolvimento de features está focado em Lakebase Autoscaling. Considere a skill [`databricks-lakebase-autoscaling`] para projetos novos que exijam scale-to-zero, branching ou instant restore.

## When to Use

Use this skill when:
- Mantendo instâncias **existentes** de Lakebase Provisioned em produção
- Building applications que precisam de PostgreSQL para cargas transacionais usando a **Database Instance API** (ainda funcional para novas instâncias, que rodarão como Autoscaling sob o capô)
- Adding persistent state to Databricks Apps
- Implementing reverse ETL from Delta Lake to an operational database (synced tables via `w.database` — a API Postgres ainda não suporta provisionamento programático de sync tables)
- Storing chat/agent memory for LangChain applications

## Overview

Lakebase Provisioned é a oferta original do Databricks para banco de dados PostgreSQL gerenciado para cargas OLTP. Está **GA (Generally Available)** desde janeiro de 2026. Ela fornece um banco PostgreSQL totalmente gerenciado integrado ao Unity Catalog com autenticação via token OAuth.

> ℹ️ **Lakebase Autoscaling** é a versão mais recente, com autoscaling, scale-to-zero, branching e instant restore. Desde março de 2026, novas instâncias são criadas como Autoscaling mesmo via Database Instance API.

| Feature | Description |
|---------|-------------|
| **Managed PostgreSQL** | Instâncias totalmente gerenciadas com provisionamento automático |
| **OAuth Authentication** | Autenticação via token Databricks SDK (expiração em 1 hora) |
| **Unity Catalog** | Registro de bancos para governança |
| **Reverse ETL** | Sync de Delta tables para PostgreSQL (apenas via Database Instance API) |
| **Apps Integration** | Suporte first-class em Databricks Apps |
| **Readable Secondaries** | Nós HA com endpoint read-only separado; acessíveis do SQL Editor |
| **SQL Editor** | Conexão direta de read-only para readable secondaries via SQL Editor (desde dez/2025) |
| **Bundles (DAB)** | Deploy de instâncias, catálogos e synced tables via `databricks bundle deploy` |

**Available Regions (AWS):** us-east-1, us-east-2, us-west-2, eu-central-1, eu-west-1, ap-south-1, ap-southeast-1, ap-southeast-2

## Quick Start

Create and connect to a Lakebase Provisioned instance:

```python
from databricks.sdk import WorkspaceClient
import uuid

# Initialize client
w = WorkspaceClient()

# Create a database instance
# NOTA: a partir de março/2026 novas instâncias são criadas como Autoscaling projects.
# A API Database Instance continua funcionando, mas o resultado roda na plataforma Autoscaling.
instance = w.database.create_database_instance(
    name="my-lakebase-instance",
    capacity="CU_1",  # CU_1, CU_2, CU_4, CU_8 → mapeados para CU ranges do Autoscaling
    stopped=False
)
print(f"Instance created: {instance.name}")
print(f"DNS endpoint: {instance.read_write_dns}")
```

### Mapeamento de Capacity para Autoscaling CUs

Quando criado via `create_database_instance` após março/2026, o `capacity` é mapeado automaticamente:

| Provisioned Capacity | Autoscaling Min CU | Autoscaling Max CU |
|---------------------|--------------------|--------------------|
| `CU_1` | 4 | 8 |
| `CU_2` | 8 | 16 |
| `CU_4` | 16 | 32 |
| `CU_8` | 64 (fixo) | 64 (fixo) |

> RAM por unidade: no Provisioned, 1 capacity unit = 16 GB RAM. No Autoscaling, 1 CU = 2 GB RAM.

## Common Patterns

### Generate OAuth Token

```python
from databricks.sdk import WorkspaceClient
import uuid

w = WorkspaceClient()

# Generate OAuth token for database connection
cred = w.database.generate_database_credential(
    request_id=str(uuid.uuid4()),
    instance_names=["my-lakebase-instance"]
)
token = cred.token  # Use this as password in connection string
```

### Connect from Notebook

```python
import psycopg
from databricks.sdk import WorkspaceClient
import uuid

# Get instance details
w = WorkspaceClient()
instance = w.database.get_database_instance(name="my-lakebase-instance")

# Generate token
cred = w.database.generate_database_credential(
    request_id=str(uuid.uuid4()),
    instance_names=["my-lakebase-instance"]
)

# Connect using psycopg3
conn_string = (
    f"host={instance.read_write_dns} "
    f"dbname=postgres "
    f"user={w.current_user.me().user_name} "
    f"password={cred.token} "
    f"sslmode=require"
)
with psycopg.connect(conn_string) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT version()")
        print(cur.fetchone())
```

### Connect to Readable Secondary (Read-Only)

Para workloads read-only, use o endpoint `-ro-` separado (disponível quando HA com readable secondaries está ativo):

```python
# O endpoint read-only usa o formato: instance-ro-{uuid} em vez de instance-{uuid}
# Disponível via instance.read_only_dns quando readable secondaries estão habilitados
instance = w.database.get_database_instance(name="my-lakebase-instance")

if hasattr(instance, 'read_only_dns') and instance.read_only_dns:
    ro_conn_string = (
        f"host={instance.read_only_dns} "
        f"dbname=postgres "
        f"user={w.current_user.me().user_name} "
        f"password={cred.token} "
        f"sslmode=require"
    )
```

### SQLAlchemy with Token Refresh (Production)

For long-running applications, tokens must be refreshed (expire after 1 hour):

```python
import asyncio
import os
import uuid
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from databricks.sdk import WorkspaceClient

# Token refresh state
_current_token = None
_token_refresh_task = None
TOKEN_REFRESH_INTERVAL = 50 * 60  # 50 minutes (before 1-hour expiry)

def _generate_token(instance_name: str) -> str:
    """Generate fresh OAuth token."""
    w = WorkspaceClient()
    cred = w.database.generate_database_credential(
        request_id=str(uuid.uuid4()),
        instance_names=[instance_name]
    )
    return cred.token

async def _token_refresh_loop(instance_name: str):
    """Background task to refresh token every 50 minutes."""
    global _current_token
    while True:
        await asyncio.sleep(TOKEN_REFRESH_INTERVAL)
        _current_token = await asyncio.to_thread(_generate_token, instance_name)

def init_database(instance_name: str, database_name: str, username: str) -> AsyncEngine:
    """Initialize database with OAuth token injection."""
    global _current_token

    w = WorkspaceClient()
    instance = w.database.get_database_instance(name=instance_name)

    # Generate initial token
    _current_token = _generate_token(instance_name)

    # Build URL (password injected via do_connect)
    url = f"postgresql+psycopg://{username}@{instance.read_write_dns}:5432/{database_name}"

    engine = create_async_engine(
        url,
        pool_size=5,
        max_overflow=10,
        pool_recycle=3600,
        connect_args={"sslmode": "require"}
    )

    # Inject token on each connection
    @event.listens_for(engine.sync_engine, "do_connect")
    def provide_token(dialect, conn_rec, cargs, cparams):
        cparams["password"] = _current_token

    return engine
```

### Databricks Apps Integration

For Databricks Apps, use environment variables for configuration:

```python
# Environment variables set by Databricks Apps:
# - LAKEBASE_INSTANCE_NAME: Instance name
# - LAKEBASE_DATABASE_NAME: Database name
# - LAKEBASE_USERNAME: Username (optional, defaults to service principal)

import os

def is_lakebase_configured() -> bool:
    """Check if Lakebase is configured for this app."""
    return bool(
        os.environ.get("LAKEBASE_PG_URL") or
        (os.environ.get("LAKEBASE_INSTANCE_NAME") and
         os.environ.get("LAKEBASE_DATABASE_NAME"))
    )
```

Add Lakebase as an app resource via CLI:

```bash
databricks apps add-resource $APP_NAME \
    --resource-type database \
    --resource-name lakebase \
    --database-instance my-lakebase-instance
```

### Register with Unity Catalog

```python
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

# Register database in Unity Catalog
w.database.register_database_instance(
    name="my-lakebase-instance",
    catalog="my_catalog",
    schema="my_schema"
)
```

### MLflow Model Resources

Declare Lakebase as a model resource for automatic credential provisioning:

```python
from mlflow.models.resources import DatabricksLakebase

resources = [
    DatabricksLakebase(database_instance_name="my-lakebase-instance"),
]

# When logging model
mlflow.langchain.log_model(
    model,
    artifact_path="model",
    resources=resources,
    pip_requirements=["databricks-langchain[memory]"]
)
```

### Databricks Asset Bundles (DAB)

Desde agosto de 2025, é possível declarar instâncias, catálogos e synced tables em bundles e fazer deploy com um único comando:

```yaml
# databricks.yml
resources:
  database_instances:
    my_lakebase:
      name: my-lakebase-instance
      capacity: CU_1

  database_catalogs:
    my_catalog:
      name: my-lakebase-catalog
      instance_name: my-lakebase-instance

  synced_database_tables:
    my_synced_table:
      instance_name: my-lakebase-instance
      source_table: catalog.schema.delta_table
      target_table: my-lakebase-catalog.schema.postgres_table
      scheduling_policy: TRIGGERED
```

```bash
databricks bundle deploy
```

> Ao fazer deploy de um bundle com uma instância de banco de dados, a instância inicia imediatamente após o deploy.

## MCP Tools

The following MCP tools are available for managing Lakebase infrastructure. Use `type="provisioned"` for Lakebase Provisioned.

### manage_lakebase_database - Database Management

| Action | Description | Required Params |
|--------|-------------|-----------------|
| `create_or_update` | Create or update a database | name |
| `get` | Get database details | name |
| `list` | List all databases | (none, optional type filter) |
| `delete` | Delete database and resources | name |

**Example usage:**
```python
# Create a provisioned database
# NOTA: a partir de março/2026 criará um projeto Autoscaling sob o capô
manage_lakebase_database(
    action="create_or_update",
    name="my-lakebase-instance",
    type="provisioned",
    capacity="CU_1"
)

# Get database details
manage_lakebase_database(action="get", name="my-lakebase-instance", type="provisioned")

# List all databases
manage_lakebase_database(action="list")

# Delete with cascade
manage_lakebase_database(action="delete", name="my-lakebase-instance", type="provisioned", force=True)
```

### manage_lakebase_sync - Reverse ETL

> ⚠️ **Nota (2026):** Provisionamento programático de synced tables **não é suportado na Postgres API** (Lakebase Autoscaling). Use sempre a **Database Instance API** (`manage_lakebase_sync`) para sync tables. Esse gap será fechado em versão futura.

| Action | Description | Required Params |
|--------|-------------|-----------------|
| `create_or_update` | Set up reverse ETL from Delta to Lakebase | instance_name, source_table_name, target_table_name |
| `delete` | Remove synced table (and optionally catalog) | table_name |

**Example usage:**
```python
# Set up reverse ETL
manage_lakebase_sync(
    action="create_or_update",
    instance_name="my-lakebase-instance",
    source_table_name="catalog.schema.delta_table",
    target_table_name="lakebase_catalog.schema.postgres_table",
    scheduling_policy="TRIGGERED"  # or SNAPSHOT, CONTINUOUS
)

# Delete synced table
manage_lakebase_sync(action="delete", table_name="lakebase_catalog.schema.postgres_table")
```

**Limitações de synced tables (confirmadas na doc oficial):**
- Continuous sync: atualiza no mínimo a cada **15 segundos**.
- Cada sync pode usar até **16 conexões** simultâneas com a instância.
- Apenas **schema changes aditivos** (ex.: nova coluna) são refletidos em modo Triggered/Continuous.
- Duplicate primary keys causam falha no pipeline — use `timeseries_key` para deduplicação (com penalidade de performance).
- Mapeamento de `TIMESTAMP` foi alterado em **agosto de 2025**: tabelas criadas antes disso mapeiam para `TIMESTAMP WITHOUT TIME ZONE`; novas seguem o novo mapeamento.

### generate_lakebase_credential - OAuth Tokens

Generate OAuth token (~1hr) for PostgreSQL connections. Use as password with `sslmode=require`.

```python
# For provisioned instances
generate_lakebase_credential(instance_names=["my-lakebase-instance"])
```

## Reference Files

- [connection-patterns.md](connection-patterns.md) - Detailed connection patterns for different use cases
- [reverse-etl.md](reverse-etl.md) - Syncing data from Delta Lake to Lakebase

## CLI Quick Reference

```bash
# Create instance
# NOTA: a partir de março/2026 cria um projeto Autoscaling
databricks database create-database-instance \
    --name my-lakebase-instance \
    --capacity CU_1

# Get instance details
databricks database get-database-instance --name my-lakebase-instance

# Generate credentials
databricks database generate-database-credential \
    --request-id $(uuidgen) \
    --json '{"instance_names": ["my-lakebase-instance"]}'

# List instances
databricks database list-database-instances

# Stop instance (saves cost)
databricks database stop-database-instance --name my-lakebase-instance

# Start instance
databricks database start-database-instance --name my-lakebase-instance
```

## High Availability & Readable Secondaries

Para habilitar HA e readable secondaries via API REST:

```bash
curl -s -X PATCH \
  --header "Authorization: Bearer ${DATABRICKS_TOKEN}" \
  $DBR_URL/database/instances/my-instance \
  -d '{"node_count": 3, "enable_readable_secondaries": true}'
```

- Com HA ativo, o endpoint read-only segue o padrão `instance-ro-{uuid}`.
- Readable secondaries podem ser consultados diretamente do **SQL Editor** do Databricks (GA desde dez/2025).
- Se `node_count` for 1, HA e readable secondaries são desabilitados.

## Common Issues

| Issue | Solution |
|-------|----------|
| **Token expired during long query** | Implement token refresh loop (see SQLAlchemy with Token Refresh section); tokens expire after 1 hour |
| **DNS resolution fails on macOS** | Use `dig` command to resolve hostname, pass `hostaddr` to psycopg |
| **Connection refused** | Ensure instance is not stopped; check `instance.state` |
| **Permission denied** | User must be granted access to the Lakebase instance |
| **SSL required error** | Always use `sslmode=require` in connection string |
| **Sync table TIMESTAMP mismatch** | Tabelas criadas antes de agosto/2025 usam `TIMESTAMP WITHOUT TIME ZONE`; recrie a synced table para obter o mapeamento atual |
| **Sync table failing with PSQLException 0x00** | Null bytes (`0x00`) em colunas STRING/ARRAY/MAP/STRUCT não são suportados em Postgres TEXT/JSONB; corrija os dados na tabela Delta de origem |
| **Pricing inesperada em nova instância** | Novas instâncias (desde março/2026) usam precificação Lakebase Autoscaling, não Provisioned |

## SDK Version Requirements

- **Databricks SDK for Python**: >= 0.61.0 (0.103.0 recomendado — versão mais recente, lançada 2026-04-20)
- **psycopg**: 3.x (supports `hostaddr` parameter for DNS workaround)
- **SQLAlchemy**: 2.x with `postgresql+psycopg` driver
- **Python**: >= 3.10 (requisito do SDK a partir de versões recentes)

```python
%pip install -U "databricks-sdk>=0.103.0" "psycopg[binary]>=3.0" sqlalchemy
```

> O SDK está em Beta mas é suportado para uso em produção. Recomenda-se fixar a versão minor (ex: `>=0.103.0,<0.104.0`) para evitar quebras em futuras atualizações.

## Notes

- **Capacity values** usam compute unit sizing: `CU_1`, `CU_2`, `CU_4`, `CU_8`. A partir de março/2026, são mapeados para CU ranges do Autoscaling em novas instâncias.
- **Lakebase está GA** desde janeiro de 2026 (saiu de preview).
- **Lakebase Autoscaling** é a versão mais recente e recebe todo o desenvolvimento de novas features. Esta skill foca em **Lakebase Provisioned** para instâncias existentes e casos onde a Database Instance API é obrigatória (ex.: sync tables programáticos).
- Para memory/state em agentes LangChain, use `databricks-langchain[memory]` que inclui suporte a Lakebase.
- Tokens são short-lived (1 hora) — apps em produção **DEVEM** implementar token refresh.
- **Scale-to-zero** está desabilitado por padrão em novas instâncias criadas via Database Instance API (comportamento idêntico ao Provisioned original). Pode ser habilitado via Postgres API ou UI do Autoscaling.

## Related Skills

- **[databricks-app-apx](../databricks-app-apx/SKILL.md)** - full-stack apps that can use Lakebase for persistence
- **[databricks-app-python](../databricks-app-python/SKILL.md)** - Python apps with Lakebase backend
- **[databricks-python-sdk](../databricks-python-sdk/SKILL.md)** - SDK used for instance management and token generation
- **[databricks-bundles](../databricks-bundles/SKILL.md)** - deploying apps and Lakebase resources via DAB
- **[databricks-jobs](../databricks-jobs/SKILL.md)** - scheduling reverse ETL sync jobs

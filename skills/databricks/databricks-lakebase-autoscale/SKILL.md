---
name: databricks-lakebase-autoscale
description: "Patterns and best practices for Lakebase Autoscaling (next-gen managed PostgreSQL). Use when creating or managing Lakebase Autoscaling projects, configuring autoscaling compute or scale-to-zero, working with database branching for dev/test workflows, implementing reverse ETL via synced tables or Lakehouse Sync (Postgres→Delta), or connecting applications to Lakebase with OAuth credentials."
updated_at: 2026-04-23
source: web_search
---

# Lakebase Autoscaling

Patterns and best practices for using Lakebase Autoscaling, the next-generation managed PostgreSQL on Databricks with autoscaling compute, branching, scale-to-zero, and instant restore.

> ⚠️ **Breaking change em março de 2026:** Desde 12/03/2026, **toda nova instância Lakebase é criada como um projeto Autoscaling** por padrão — tanto via UI quanto via Database instance API, Terraform ou SDK. Não é mais possível criar instâncias Provisioned pela UI. Instâncias Provisioned existentes continuam funcionando sem alteração. Veja [Autoscaling by default](https://docs.databricks.com/aws/en/oltp/upgrade-to-autoscaling).

> ⚠️ **Breaking change em fevereiro de 2026 (GA):** Lakebase Autoscaling saiu de Public Preview e está **Geralmente Disponível** em AWS. Azure está em rollout. Billing estava habilitado desde janeiro de 2026.

## When to Use

Use this skill when:
- Building applications that need a PostgreSQL database with autoscaling compute
- Working with database branching for dev/test/staging workflows
- Adding persistent state to applications with scale-to-zero cost savings
- Implementing reverse ETL from Delta Lake to an operational database via synced tables
- Implementing Postgres→Delta replication via Lakehouse Sync (Beta)
- Managing Lakebase Autoscaling projects, branches, computes, or credentials
- Exposing database data via the Lakebase Data API (PostgREST-compatible REST interface)

## Overview

Lakebase Autoscaling is Databricks' next-generation managed PostgreSQL service for OLTP workloads. It provides autoscaling compute, Git-like branching, scale-to-zero, and instant point-in-time restore.

| Feature | Description |
|---------|-------------|
| **Autoscaling Compute** | 0.5–112 CU com 2 GB RAM por CU; escala dinamicamente pela carga |
| **Scale-to-Zero** | Compute suspende após inatividade configurável (desabilitado por default em novos projetos) |
| **Branching** | Ambientes isolados de banco de dados (como branches Git) para dev/test |
| **Instant Restore** | Point-in-time restore de qualquer momento dentro da janela configurada (até **30 dias**) |
| **OAuth Authentication** | Token via Databricks SDK (expiração em 1 hora) |
| **Reverse ETL (Synced Tables)** | Sync de Delta tables para PostgreSQL (Delta→Postgres) |
| **Lakehouse Sync** | Replicação contínua de tabelas Lakebase para Unity Catalog como Delta tables (Postgres→Delta, **Beta**) |
| **Data API** | Interface REST PostgREST-compatible para acesso CRUD direto ao banco via HTTP |
| **Unity Catalog** | Registro e federação do banco como catálogo no Unity Catalog |

> ⚠️ **Breaking change em fevereiro de 2026:** A **janela máxima de restore (PITR)** em Autoscaling é **30 dias** (era documentada como 35 dias, que se aplica apenas ao Lakebase Provisioned). Se seu workflow depende de janela > 30 dias, mantenha Provisioned.

**Available Regions (AWS — GA):** us-east-1, us-east-2, eu-central-1, eu-west-1, eu-west-2, ap-south-1, ap-southeast-1, ap-southeast-2

**Available Regions (Azure — em rollout/Beta):** eastus2, westeurope, westus — verificar disponibilidade atual em [Region availability](https://docs.databricks.com/aws/en/oltp/projects/about).

## Project Hierarchy

Understanding the hierarchy is essential for working with Lakebase Autoscaling:

```
Project (top-level container)
  └── Branch(es) (isolated database environments)
        ├── Compute (primary R/W endpoint)
        ├── Read Replica(s) (optional, read-only endpoints)
        ├── Role(s) (Postgres roles)
        └── Database(s) (Postgres databases)
              └── Schema(s)
```

| Object | Description |
|--------|-------------|
| **Project** | Top-level container. Criado via `w.postgres.create_project()`. |
| **Branch** | Ambiente isolado de banco com copy-on-write storage. Branch default é `production`. |
| **Compute** | Servidor Postgres de um branch. CU configurável com autoscaling. Scale-to-zero **desabilitado por padrão** em novos projetos. |
| **Database** | Banco Postgres padrão dentro do branch. Default é `databricks_postgres`. |

> **Nota:** Novos projetos usam **regional hostnames** (incluem o código da região, ex: `us-east-1`). Isso difere do Lakebase Provisioned que usa hostname global. Atualize allowlists de IP e configurações de Private Link para novos projetos.

## Quick Start

Create a project and connect:

```python
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.postgres import Project, ProjectSpec

w = WorkspaceClient()

# Create a project (long-running operation)
# Projetos criados via Autoscaling UI ou Postgres API usam PG 17 por padrão.
# Projetos criados via Database instance API herdam PG 16 (compatibilidade com Provisioned).
operation = w.postgres.create_project(
    project=Project(
        spec=ProjectSpec(
            display_name="My Application",
            pg_version="17"
        )
    ),
    project_id="my-app"
)
result = operation.wait()
print(f"Created project: {result.name}")
```

> ⚠️ **Breaking change em março de 2026:** Projetos criados via **Database instance API** (não via Postgres API) recebem **PostgreSQL 16** por padrão (mantém compatibilidade com Provisioned). Projetos criados via UI ou Postgres API recebem **PostgreSQL 17** por padrão.

## Common Patterns

### Generate OAuth Token

```python
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

# Generate database credential for connecting (optionally scoped to an endpoint)
cred = w.postgres.generate_database_credential(
    endpoint="projects/my-app/branches/production/endpoints/ep-primary"
)
token = cred.token  # Use as password in connection string
# Token expires after 1 hour
```

### Connect from Notebook

```python
import psycopg
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

# Get endpoint details
endpoint = w.postgres.get_endpoint(
    name="projects/my-app/branches/production/endpoints/ep-primary"
)
host = endpoint.status.hosts.host
# Novos projetos têm regional hostname (ex: "my-app.postgres.us-east-1.cloud.databricks.com")

# Generate token (scoped to endpoint)
cred = w.postgres.generate_database_credential(
    endpoint="projects/my-app/branches/production/endpoints/ep-primary"
)

# Connect using psycopg3
conn_string = (
    f"host={host} "
    f"dbname=databricks_postgres "
    f"user={w.current_user.me().user_name} "
    f"password={cred.token} "
    f"sslmode=require"
)
with psycopg.connect(conn_string) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT version()")
        print(cur.fetchone())
```

### Create a Branch for Development

```python
from databricks.sdk.service.postgres import Branch, BranchSpec, Duration

# Create a dev branch with 7-day expiration
branch = w.postgres.create_branch(
    parent="projects/my-app",
    branch=Branch(
        spec=BranchSpec(
            source_branch="projects/my-app/branches/production",
            ttl=Duration(seconds=604800)  # 7 days
        )
    ),
    branch_id="development"
).wait()
print(f"Branch created: {branch.name}")
```

### Resize Compute (Autoscaling)

> ⚠️ **Breaking change:** O range máximo entre min e max CU passou de 8 para **16 CU** (`max - min ≤ 16`). Exemplo válido: 0.5–16.5 CU. Configurações anteriores com range ≤ 8 continuam válidas.

```python
from databricks.sdk.service.postgres import Endpoint, EndpointSpec, FieldMask

# Update compute to autoscale between 2-8 CU (range de 6 CU, dentro do limite de 16)
w.postgres.update_endpoint(
    name="projects/my-app/branches/production/endpoints/ep-primary",
    endpoint=Endpoint(
        name="projects/my-app/branches/production/endpoints/ep-primary",
        spec=EndpointSpec(
            autoscaling_limit_min_cu=2.0,
            autoscaling_limit_max_cu=8.0
        )
    ),
    update_mask=FieldMask(field_mask=[
        "spec.autoscaling_limit_min_cu",
        "spec.autoscaling_limit_max_cu"
    ])
).wait()
```

> **Nota de sizing:** Autoscaling suporta escala automática até 32 CU. Tamanhos maiores (incluindo 64 CU) são fixed-size (sem autoscaling dentro do range).

### Manage Databases via SDK (novo em SDK recente)

```python
# Novos métodos adicionados ao w.postgres para gerenciar databases diretamente
from databricks.sdk.service.postgres import DatabaseSpec

# Criar um database adicional
db = w.postgres.create_database(
    parent="projects/my-app/branches/production",
    database_id="my-secondary-db",
    # spec conforme DatabaseSpec
).wait()

# Listar databases
for db in w.postgres.list_databases(parent="projects/my-app/branches/production"):
    print(db.name)

# Deletar database
w.postgres.delete_database(name="projects/my-app/branches/production/databases/my-secondary-db").wait()
```

### Read Replica Endpoint (novo campo)

```python
# EndpointHosts agora expõe read_only_host para endpoints de réplica
endpoint = w.postgres.get_endpoint(
    name="projects/my-app/branches/production/endpoints/ep-replica"
)
read_only_host = endpoint.status.hosts.read_only_host  # campo novo
```

### Lakehouse Sync — Postgres→Delta (Beta)

Replica tabelas do Lakebase para Unity Catalog como Delta tables via CDC. Requer PG 17 e preview habilitado no workspace.

```python
# Configurar via UI: Branch overview → aba "Lakehouse sync" → Start sync
# As tabelas aparecem no Unity Catalog como lb_<nome_da_tabela>_history
# Monitorar via SQL Editor no Lakebase:
# SELECT * FROM wal2delta.tables;
```

> Use `reverse-etl.md` para Delta→Postgres (synced tables). Use Lakehouse Sync para Postgres→Delta.

## MCP Tools

The following MCP tools are available for managing Lakebase infrastructure. Use `type="autoscale"` for Lakebase Autoscaling.

### manage_lakebase_database - Project Management

| Action | Description | Required Params |
|--------|-------------|-----------------|
| `create_or_update` | Create or update a project | name |
| `get` | Get project details (includes branches/endpoints) | name |
| `list` | List all projects | (none, optional type filter) |
| `delete` | Delete project and all branches/computes/data | name |

**Example usage:**
```python
# Create an autoscale project
manage_lakebase_database(
    action="create_or_update",
    name="my-app",
    type="autoscale",
    display_name="My Application",
    pg_version="17"
)

# Get project with branches
manage_lakebase_database(action="get", name="my-app", type="autoscale")

# Delete project
manage_lakebase_database(action="delete", name="my-app", type="autoscale")
```

### manage_lakebase_branch - Branch Management

| Action | Description | Required Params |
|--------|-------------|-----------------|
| `create_or_update` | Create/update branch with compute endpoint | project_name, branch_id |
| `delete` | Delete branch and endpoints | name (full branch name) |

**Example usage:**
```python
# Create a dev branch with 7-day TTL
manage_lakebase_branch(
    action="create_or_update",
    project_name="my-app",
    branch_id="development",
    source_branch="production",
    ttl_seconds=604800,  # 7 days
    autoscaling_limit_min_cu=0.5,
    autoscaling_limit_max_cu=4.0,
    scale_to_zero_seconds=300
)

# Delete branch
manage_lakebase_branch(action="delete", name="projects/my-app/branches/development")
```

### generate_lakebase_credential - OAuth Tokens

Generate OAuth token (~1hr) for PostgreSQL connections. Use as password with `sslmode=require`.

```python
# For autoscale endpoints
generate_lakebase_credential(endpoint="projects/my-app/branches/production/endpoints/ep-primary")
```

## Reference Files

- [projects.md](projects.md) - Project management patterns and settings
- [branches.md](branches.md) - Branching workflows, protection, and expiration
- [computes.md](computes.md) - Compute sizing, autoscaling, and scale-to-zero
- [connection-patterns.md](connection-patterns.md) - Connection patterns for different use cases
- [reverse-etl.md](reverse-etl.md) - Synced tables from Delta Lake to Lakebase (Delta→Postgres)

## CLI Quick Reference

```bash
# Create a project
databricks postgres create-project \
    --project-id my-app \
    --json '{"spec": {"display_name": "My App", "pg_version": "17"}}'

# List projects
databricks postgres list-projects

# Get project details
databricks postgres get-project projects/my-app

# Create a branch
databricks postgres create-branch projects/my-app development \
    --json '{"spec": {"source_branch": "projects/my-app/branches/production", "no_expiry": true}}'

# List branches
databricks postgres list-branches projects/my-app

# Get endpoint details
databricks postgres get-endpoint projects/my-app/branches/production/endpoints/ep-primary

# Delete a project
databricks postgres delete-project projects/my-app
```

## Key Differences from Lakebase Provisioned

| Aspect | Provisioned | Autoscaling |
|--------|-------------|-------------|
| SDK module | `w.database` | `w.postgres` |
| Top-level resource | Instance | Project |
| Capacity | CU_1, CU_2, CU_4, CU_8 (16 GB/CU) | 0.5–112 CU (2 GB/CU) |
| Branching | Not supported | Full branching support |
| Scale-to-zero | Not supported | Configurable timeout (desabilitado por padrão) |
| Operations | Synchronous | Long-running operations (LRO) |
| Read replicas | Readable secondaries | Dedicated read-only endpoints |
| Restore window | Até 35 dias | Até **30 dias** |
| Hostname format | Global (sem região) | **Regional** (inclui código da região) |
| Postgres→Delta sync | Forward ETL (private preview) | **Lakehouse Sync** (Beta, CDC) |
| Default em novos projetos | ❌ (deprecated como default) | ✅ (padrão desde 12/03/2026) |
| Databricks Apps resource | Suportado | **Suportado** (desde março 2026) |

## Common Issues

| Issue | Solution |
|-------|----------|
| **Token expired during long query** | Implement token refresh loop; tokens expire after 1 hour |
| **Connection refused after scale-to-zero** | Compute wakes automatically on connection; reactivation takes a few hundred ms; implement retry logic |
| **DNS resolution fails on macOS** | Use `dig` command to resolve hostname, pass `hostaddr` to psycopg |
| **Branch deletion blocked** | Delete child branches first; cannot delete branches with children |
| **Autoscaling range too wide** | Max - min **cannot exceed 16 CU** (ex: 0.5–16.5 CU é válido, 0.5–32 CU não é para autoscaling — acima de 32 CU é fixed-size) |
| **SSL required error** | Always use `sslmode=require` in connection string |
| **Update mask required** | All update operations require an `update_mask` specifying fields to modify |
| **Connection closed after 24h idle** | All connections have a 24-hour idle timeout and 3-day max lifetime; implement retry logic |
| **409 Conflict on API call** | Maintenance operation in progress or concurrent ops limit reached; retry the request |
| **IP allowlist blocking new project** | Novos projetos usam regional ingress IPs — atualize allowlists de IP para a região do projeto |
| **Private Link não conecta** | Autoscaling usa dois endpoints Private Link: front-end (workspace) e Service Direct (regional, para Postgres clients) — configure ambos |

## Current Limitations

Estas features têm restrições ou não são suportadas em Lakebase Autoscaling:

- **Lakehouse Sync** (Postgres→Delta) requer **Postgres 17** e preview habilitado no workspace (Beta)
- Compliance standards suportados: HIPAA, C5, TISAX ou None — outros não são suportados
- Migração direta de Lakebase Provisioned não suportada — use `pg_dump`/`pg_restore` ou reverse ETL
- Custom billing tags e serverless budget policies ainda não disponíveis
- Synced tables (Delta→Postgres) em modo Triggered/Continuous suportam apenas additive schema changes

> ✅ **Anteriormente limitados, agora suportados:**
> - **Databricks Apps UI integration** — Apps podem adicionar Lakebase como app resource nativamente (desde março 2026)
> - **Feature Store / Online Feature Store** — Lakebase referenciado como online store para ML models
> - **Agent state para AI agents** — armazenamento de estado transacional suportado
> - **Postgres→Delta sync** — disponível via **Lakehouse Sync** (Beta, CDC, Postgres 17)

## SDK Version Requirements

> ⚠️ Os métodos `create_database`, `delete_database`, `get_database`, `list_databases`, `update_database` e `update_role` foram adicionados em versões recentes do SDK. Use sempre a versão mais recente disponível.

- **Databricks SDK for Python**: >= 0.81.0 (para módulo `w.postgres`); recomenda-se versão mais recente para `create_database`, `update_role`, `read_only_host`
- **psycopg**: 3.x (suporta parâmetro `hostaddr` para workaround de DNS)
- **SQLAlchemy**: 2.x com driver `postgresql+psycopg`

```python
%pip install -U "databricks-sdk>=0.81.0" "psycopg[binary]>=3.0" sqlalchemy
```

## Notes

- **Compute Units** em Autoscaling fornecem ~2 GB RAM cada (vs 16 GB em Provisioned).
- **Resource naming** segue paths hierárquicos: `projects/{id}/branches/{id}/endpoints/{id}`.
- **Scale-to-zero** é **desabilitado por padrão** em novos projetos (inclusive production branch) para manter compatibilidade comportamental com Provisioned.
- Todos os create/update/delete são **long-running** — use `.wait()` no SDK.
- Tokens são de curta duração (1 hora) — apps de produção DEVEM implementar refresh de token.
- **Postgres versions** 16 e 17 são suportados. Lakehouse Sync requer Postgres 17.
- **Regional hostnames** — novos projetos usam hostname com região, diferente do Provisioned.
- **Data API** (PostgREST-compatible): expõe tabelas como endpoints REST HTTP com autenticação OAuth. Habilitado via Lakebase App UI.
- **`enable_pg_native_login`** — novo campo em `ProjectSpec`/`ProjectStatus` para habilitar login nativo Postgres (além do OAuth).

## Related Skills

- **[databricks-lakebase-provisioned](../databricks-lakebase-provisioned/SKILL.md)** - fixed-capacity managed PostgreSQL (predecessor, mantido para instâncias existentes)
- **[databricks-app-apx](../databricks-app-apx/SKILL.md)** - full-stack apps que podem usar Lakebase como resource nativo
- **[databricks-app-python](../databricks-app-python/SKILL.md)** - Python apps with Lakebase backend
- **[databricks-python-sdk](../databricks-python-sdk/SKILL.md)** - SDK usado para gerenciamento de projetos e geração de tokens
- **[databricks-bundles](../databricks-bundles/SKILL.md)** - deploying apps with Lakebase resources via Declarative Automation
- **[databricks-jobs](../databricks-jobs/SKILL.md)** - scheduling reverse ETL sync jobs

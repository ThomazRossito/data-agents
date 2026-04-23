---
name: databricks-app-python
description: "Builds Python-based Databricks applications using Dash, Streamlit, Gradio, Flask, FastAPI, or Reflex. Handles OAuth authorization (app and user auth), app resources, SQL warehouse and Lakebase connectivity, model serving integration, foundation model APIs, LLM integration, and deployment. Use when building Python web apps, dashboards, ML demos, or REST APIs for Databricks, or when the user mentions Streamlit, Dash, Gradio, Flask, FastAPI, Reflex, or Databricks app."
updated_at: 2026-04-23
source: web_search
---

# Databricks Python Application

Build Python-based Databricks applications. For full examples and recipes, see the **[Databricks Apps Cookbook](https://apps-cookbook.dev/)**.

---

## Critical Rules (always follow)

- **MUST** confirm framework choice or use [Framework Selection](#framework-selection) below
- **MUST** use SDK `Config()` for authentication (never hardcode tokens)
- **MUST** use `app.yaml` `valueFrom` for resources (never hardcode resource IDs)
- **MUST** use `dash-bootstrap-components` for Dash app layout and styling
- **MUST** use `@st.cache_resource` for Streamlit database connections
- **MUST** deploy Flask with Gunicorn, FastAPI with uvicorn (not dev servers)

## Required Steps

Copy this checklist and verify each item:
```
- [ ] Framework selected
- [ ] Auth strategy decided: app auth, user auth, or both
- [ ] App resources identified (SQL warehouse, Lakebase, serving endpoint, etc.)
- [ ] Backend data strategy decided (SQL warehouse, Lakebase, or SDK)
- [ ] Dependency strategy decided: pip (requirements.txt) or uv (pyproject.toml + uv.lock)
- [ ] Deployment method: CLI, DABs (Declarative Automation Bundles), or Git repository
```

---

## Framework Selection

| Framework | Best For | app.yaml Command |
|-----------|----------|------------------|
| **Dash** | Production dashboards, BI tools, complex interactivity | `["python", "app.py"]` |
| **Streamlit** | Rapid prototyping, data science apps, internal tools | `["streamlit", "run", "app.py"]` |
| **Gradio** | ML demos, model interfaces, chat UIs | `["python", "app.py"]` |
| **Flask** | Custom REST APIs, lightweight apps, webhooks | `["gunicorn", "app:app", "-w", "4", "-b", "0.0.0.0:8000"]` |
| **FastAPI** | Async APIs, auto-generated OpenAPI docs | `["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]` |
| **Reflex** | Full-stack Python apps without JavaScript | `["reflex", "run", "--env", "prod"]` |

**Default**: Recommend **Streamlit** for prototypes, **Dash** for production dashboards, **FastAPI** for APIs, **Gradio** for ML demos.

---

## Quick Reference

| Concept | Details |
|---------|---------|
| **Runtime** | Python 3.11, Ubuntu 22.04, 2 vCPU, 6 GB RAM (default Medium) |
| **Pre-installed** | Dash 2.18.1, Streamlit 1.38.0, Gradio 4.44.0, Flask 3.0.3, FastAPI 0.115.0 |
| **Auth (app)** | Service principal via `Config()` — auto-injected `DATABRICKS_CLIENT_ID`/`DATABRICKS_CLIENT_SECRET` |
| **Auth (user)** | `x-forwarded-access-token` header — see [1-authorization.md](1-authorization.md) |
| **Resources** | `valueFrom` in app.yaml — see [2-app-resources.md](2-app-resources.md) |
| **Cookbook** | https://apps-cookbook.dev/ |
| **Docs** | https://docs.databricks.com/aws/en/dev-tools/databricks-apps/ |

---

## Detailed Guides

**Authorization**: Use [1-authorization.md](1-authorization.md) when configuring app or user authorization — covers service principal auth, on-behalf-of user tokens, OAuth scopes, and per-framework code examples. (Keywords: OAuth, service principal, user auth, on-behalf-of, access token, scopes)

**App resources**: Use [2-app-resources.md](2-app-resources.md) when connecting your app to Databricks resources — covers SQL warehouses, Lakebase, model serving, secrets, volumes, and the `valueFrom` pattern. (Keywords: resources, valueFrom, SQL warehouse, model serving, secrets, volumes, connections)

**Frameworks**: See [3-frameworks.md](3-frameworks.md) for Databricks-specific patterns per framework — covers Dash, Streamlit, Gradio, Flask, FastAPI, and Reflex with auth integration, deployment commands, and Cookbook links. (Keywords: Dash, Streamlit, Gradio, Flask, FastAPI, Reflex, framework selection)

**Deployment**: Use [4-deployment.md](4-deployment.md) when deploying your app — covers Databricks CLI, Declarative Automation Bundles (DABs), Git repository deployment, app.yaml configuration, and post-deployment verification. (Keywords: deploy, CLI, DABs, declarative automation bundles, asset bundles, app.yaml, logs, git)

**Lakebase**: Use [5-lakebase.md](5-lakebase.md) when using Lakebase (PostgreSQL) as your app's data layer — covers auto-injected env vars, psycopg2/asyncpg patterns, and when to choose Lakebase vs SQL warehouse. (Keywords: Lakebase, PostgreSQL, psycopg2, asyncpg, transactional, PGHOST)

**MCP tools**: Use [6-mcp-approach.md](6-mcp-approach.md) for managing app lifecycle via MCP tools — covers creating, deploying, monitoring, and deleting apps programmatically. (Keywords: MCP, create app, deploy app, app logs)

**Foundation Models**: See [examples/llm_config.py](examples/llm_config.py) for calling Databricks foundation model APIs — covers OAuth M2M auth, OpenAI-compatible client wiring, and token caching. (Keywords: foundation model, LLM, OpenAI client, chat completions)

---

## Workflow

1. Determine the task type:

   **New app from scratch?** → Use [Framework Selection](#framework-selection), then read [3-frameworks.md](3-frameworks.md)
   **Setting up authorization?** → Read [1-authorization.md](1-authorization.md)
   **Connecting to data/resources?** → Read [2-app-resources.md](2-app-resources.md)
   **Using Lakebase (PostgreSQL)?** → Read [5-lakebase.md](5-lakebase.md)
   **Deploying to Databricks?** → Read [4-deployment.md](4-deployment.md)
   **Using MCP tools?** → Read [6-mcp-approach.md](6-mcp-approach.md)
   **Calling foundation model/LLM APIs?** → See [examples/llm_config.py](examples/llm_config.py)

2. Follow the instructions in the relevant guide
3. For full code examples, browse https://apps-cookbook.dev/

---

## Core Architecture

All Python Databricks apps follow this pattern:

```
app-directory/
├── app.py                 # Main application (or framework-specific name)
├── models.py              # Pydantic data models
├── backend.py             # Data access layer
├── requirements.txt       # Additional Python dependencies (pip-based)
│                          # OR pyproject.toml + uv.lock (uv-based — see Dependency Management)
├── app.yaml               # Databricks Apps configuration
└── README.md
```

### Backend Toggle Pattern

```python
import os
from databricks.sdk.core import Config

USE_MOCK = os.getenv("USE_MOCK_BACKEND", "true").lower() == "true"

if USE_MOCK:
    from backend_mock import MockBackend as Backend
else:
    from backend_real import RealBackend as Backend

backend = Backend()
```

### SQL Warehouse Connection (shared across all frameworks)

```python
from databricks.sdk.core import Config
from databricks import sql

cfg = Config()  # Auto-detects credentials from environment
conn = sql.connect(
    server_hostname=cfg.host,
    http_path=f"/sql/1.0/warehouses/{os.getenv('DATABRICKS_WAREHOUSE_ID')}",
    credentials_provider=lambda: cfg.authenticate,
)
```

### Pydantic Models

```python
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

class Status(str, Enum):
    ACTIVE = "active"
    PENDING = "pending"

class EntityOut(BaseModel):
    id: str
    name: str
    status: Status
    created_at: datetime

class EntityIn(BaseModel):
    name: str = Field(..., min_length=1)
    status: Status = Status.PENDING
```

---

## Dependency Management

> ⚠️ **New in March 2026**: Databricks Apps now supports `uv` + `pyproject.toml` as an alternative to `requirements.txt`. Choose one strategy per app — they are mutually exclusive at deploy time.

The platform selects the install strategy based on which files are present:

| Strategy | Files required | Python version |
|----------|---------------|----------------|
| **pip** (default) | `requirements.txt` | Fixed: Python 3.11 |
| **uv** | `pyproject.toml` + `uv.lock` (no `requirements.txt`) | Any version via `requires-python` |

**Rule**: `requirements.txt` always takes precedence — if both exist, `uv` is ignored.

### pip / requirements.txt (standard)

```txt
# requirements.txt
# Override a pre-installed package version
dash==2.10.0
# Add packages not pre-installed
requests==2.31.0
numpy==1.24.3
scikit-learn>=1.2.0,<1.3.0
```

- Pre-installed packages do **not** need to be listed unless you need a different version.
- To install wheels from Unity Catalog volumes, hardcode the full path: `/Volumes/<catalog>/<schema>/<volume>/my_package-1.0.0-py3-none-any.whl`
- Environment variable references are **not** supported inside `requirements.txt` — always hardcode paths.

### uv / pyproject.toml (recommended for new projects needing reproducibility or a custom Python version)

```toml
# pyproject.toml
[project]
name = "my-app"
requires-python = ">=3.12"   # can be any version, unlike pip-based apps
dependencies = [
    "dash==2.10.0",
    "requests==2.31.0",
]
```

Generate the lockfile locally before deploying:

```bash
uv lock   # generates uv.lock — commit both files
```

Pre-installed libraries are **not** available for uv-based apps — declare all dependencies in `pyproject.toml`.

### Node.js dependencies

If your app includes a frontend (e.g., React + Vite bundled with FastAPI), add a `package.json` in the app root. Databricks runs `npm install` automatically during deployment.

```jsonc
// package.json (example for React + Vite)
{
  "name": "my-app",
  "scripts": { "build": "vite build frontend" },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "vite": "^5.0.0"
  }
}
```

> Note: No Node.js libraries are pre-installed. List **all** Node.js packages under `dependencies`, not `devDependencies`, if they are needed for `npm run build` (setting `NODE_ENV=production` skips `devDependencies`).

---

## Compute Sizing

> ⚠️ **New in January 2026 (GA)**: App compute sizing is now generally available. You can choose between Medium and Large at app creation time or in the UI.

| Size | vCPUs | Memory | Use When |
|------|-------|--------|----------|
| **Medium** (default) | 2 vCPU | 6 GB | Most apps, prototypes, lightweight APIs |
| **Large** | 4 vCPU | 12 GB | Heavy computation, large model inference, high-concurrency dashboards |

Configure via the Databricks UI or `app.yaml`. See [Configure compute resources for a Databricks app](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/).

---

## Common Issues

| Issue | Solution |
|-------|----------|
| **Connection exhausted** | Use `@st.cache_resource` (Streamlit) or connection pooling |
| **Auth token not found** | Check `x-forwarded-access-token` header — only available when deployed, not locally |
| **App won't start** | Check `app.yaml` command matches framework; check `databricks apps logs <name>` |
| **Resource not accessible** | Add resource via UI, verify SP has permissions, use `valueFrom` in app.yaml |
| **Import error on deploy** | Add missing packages to `requirements.txt` (pre-installed packages don't need listing) |
| **Import error on deploy (uv)** | With uv, pre-installed packages are NOT available — declare ALL deps in `pyproject.toml` |
| **Lakebase app crashes on start** | `psycopg2`/`asyncpg` are NOT pre-installed — MUST add to `requirements.txt` or `pyproject.toml` |
| **Port conflict** | Apps must bind to `DATABRICKS_APP_PORT` env var (defaults to 8000). Never use 8080. Streamlit is auto-configured; for others, read the env var in code or use 8000 in app.yaml command |
| **Streamlit: set_page_config error** | `st.set_page_config()` must be the first Streamlit command |
| **Dash: unstyled layout** | Add `dash-bootstrap-components`; use `dbc.themes.BOOTSTRAP` |
| **Slow queries** | Use Lakebase for transactional/low-latency; SQL warehouse for analytical queries |
| **uv.lock missing** | Run `uv lock` locally and commit `uv.lock` alongside `pyproject.toml` before deploying |
| **requirements.txt + pyproject.toml conflict** | If both exist, pip/requirements.txt always wins — remove `requirements.txt` to activate uv |

---

## Platform Constraints

| Constraint | Details |
|------------|---------|
| **Runtime** | Python 3.11, Ubuntu 22.04 LTS (pip-based); any Python version (uv-based) |
| **Compute (default)** | 2 vCPUs, 6 GB memory (Medium) |
| **Compute (large)** | 4 vCPUs, 12 GB memory (Large) — GA since January 2026 |
| **Node.js** | Node.js 22.16 available; no pre-installed libraries — use `package.json` |
| **Pre-installed frameworks** | Dash, Streamlit, Gradio, Flask, FastAPI, Shiny (pip-based apps only) |
| **Custom packages (pip)** | Add to `requirements.txt` in app root |
| **Custom packages (uv)** | Declare all in `pyproject.toml` + commit `uv.lock` |
| **Network** | Apps can reach Databricks APIs; external access depends on workspace config |
| **User auth** | Public Preview — workspace admin must enable before adding scopes |
| **Git deployment** | GA since April 2026 — configure Git ref and source path in app settings |

---

## Deployment Options

> ⚠️ **Rename in March 2026**: "Databricks Asset Bundles (DABs)" has been officially renamed to **Declarative Automation Bundles**. The CLI commands and YAML schema are unchanged — only the marketing name changed. References in docs and older guides using "DABs" or "Asset Bundles" refer to the same tool.

Three supported deployment methods:

| Method | When to Use |
|--------|-------------|
| **Databricks CLI** (`databricks apps deploy`) | Quick manual deploys, dev iteration |
| **Declarative Automation Bundles** (formerly DABs) | CI/CD pipelines, multi-environment promotion |
| **Git repository** (April 2026) | Source-of-truth Git workflows; enforce Git-only deployments workspace-wide |

For Git deployment: configure a Git reference and source code path in the app settings. Optionally enforce Git-only deployments at the workspace level.

See [4-deployment.md](4-deployment.md) for full details.

---

## Official Documentation

- **[Databricks Apps Overview](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/)** — main docs hub
- **[Apps Cookbook](https://apps-cookbook.dev/)** — ready-to-use code snippets (Streamlit, Dash, Reflex, FastAPI)
- **[Authorization](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/auth)** — app auth and user auth
- **[Resources](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/resources)** — SQL warehouse, Lakebase, serving, secrets
- **[app.yaml Reference](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/app-runtime)** — command and env config
- **[System Environment](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/system-env)** — runtime details, env vars, port bindings
- **[Manage Dependencies](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/dependencies)** — pip, uv, and Node.js dependency management

## Related Skills

- **[databricks-app-apx](../databricks-app-apx/SKILL.md)** - full-stack apps with FastAPI + React
- **[databricks-bundles](../databricks-bundles/SKILL.md)** - deploying apps via Declarative Automation Bundles (formerly DABs)
- **[databricks-python-sdk](../databricks-python-sdk/SKILL.md)** - backend SDK integration
- **[databricks-lakebase-provisioned](../databricks-lakebase-provisioned/SKILL.md)** - adding persistent PostgreSQL state
- **[databricks-model-serving](../databricks-model-serving/SKILL.md)** - serving ML models for app integration

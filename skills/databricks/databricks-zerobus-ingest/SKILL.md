---
name: databricks-zerobus-ingest
description: "Build Zerobus Ingest clients for near real-time data ingestion into Databricks Delta tables via gRPC. Use when creating producers that write directly to Unity Catalog tables without a message bus, working with the Zerobus Ingest SDK in Python/Java/Go/TypeScript/Rust, generating Protobuf schemas from UC tables, or implementing stream-based ingestion with ACK handling and retry logic."
updated_at: 2026-04-23
source: web_search
---

# Zerobus Ingest

Build clients that ingest data directly into Databricks Delta tables via the Zerobus gRPC API.

**Status:** GA (Generally Available since February 2026; billed under **Jobs Serverless** SKU on AWS / **Automated Serverless** SKU on Azure)

> ⚠️ **Nota de billing por cloud (confirmado Abr/2026):** No AWS o SKU é `"Jobs Serverless"`; no Azure o SKU é `"Automated Serverless"`. A interface OpenTelemetry (OTLP), em Beta, ainda não é cobrada em nenhuma cloud.

**Documentation:**
- [Zerobus Overview](https://docs.databricks.com/aws/en/ingestion/zerobus-overview)
- [Zerobus Ingest SDK](https://docs.databricks.com/aws/en/ingestion/zerobus-ingest)
- [Zerobus Limits](https://docs.databricks.com/aws/en/ingestion/zerobus-limits)
- [Zerobus OTLP (Beta)](https://docs.databricks.com/aws/en/ingestion/opentelemetry/configure)

---

## What Is Zerobus Ingest?

Zerobus Ingest is a serverless connector that enables direct, record-by-record data ingestion into Delta tables. It supports three interfaces: **gRPC** (via SDKs, máximo throughput), **REST** (Beta, ideal para frotas de dispositivos "chatty" de baixo volume), e **OpenTelemetry / OTLP** (Beta, para pipelines OTel já existentes sem bibliotecas customizadas). Elimina a necessidade de message bus (Kafka, Kinesis, Event Hub) para dados com destino único ao lakehouse. O serviço valida schemas, materializa dados nas tabelas-alvo e devolve ACKs de durabilidade ao cliente.

**Core pattern (gRPC/SDK):** SDK init -> create stream -> ingest records -> handle ACKs -> flush -> close

---

## Quick Decision: What Are You Building?

| Scenario | Language | Serialization | Reference |
|----------|----------|---------------|-----------|
| Quick prototype / test harness | Python | JSON | [2-python-client.md](2-python-client.md) |
| Production Python producer | Python | Protobuf | [2-python-client.md](2-python-client.md) + [4-protobuf-schema.md](4-protobuf-schema.md) |
| JVM microservice *(Public Preview)* | Java | Protobuf | [3-multilanguage-clients.md](3-multilanguage-clients.md) |
| Go service (Go 1.21+) | Go | JSON or Protobuf | [3-multilanguage-clients.md](3-multilanguage-clients.md) |
| Node.js / TypeScript app | TypeScript | JSON | [3-multilanguage-clients.md](3-multilanguage-clients.md) |
| High-performance system service | Rust | JSON or Protobuf | [3-multilanguage-clients.md](3-multilanguage-clients.md) |
| Schema generation from UC table | Any | Protobuf | [4-protobuf-schema.md](4-protobuf-schema.md) |
| Retry / reconnection logic | Any | Any | [5-operations-and-limits.md](5-operations-and-limits.md) |
| OTel observability / telemetry (traces, logs, metrics) | Any OTLP collector | OTLP (Beta) | [Zerobus OTLP docs](https://docs.databricks.com/aws/en/ingestion/opentelemetry/configure) |

> ⚠️ **Java SDK em Public Preview:** O SDK Java ainda não é GA. Minor versions podem conter breaking changes. Use com cautela em produção e monitore o CHANGELOG.

If not specified, default to python.

---

## Common Libraries

Estas bibliotecas são essenciais para ingestão via Zerobus:

- **databricks-sdk>=0.85.0**: Databricks workspace client para autenticação e metadados
- **databricks-zerobus-ingest-sdk>=1.1.0**: SDK Python para ingestão de alta performance (PyO3/Rust-backed; requer Python 3.9+)
  - A versão 0.3.0 foi **yanked** do PyPI por conter breaking changes. Sempre use `>=1.1.0`.
- **grpcio-tools** *(apenas se precisar compilar arquivos `.proto` customizados)*: não é necessário para operar o SDK Python padrão.

Tipicamente NÃO estão pré-instaladas no Databricks. Instale com `execute_code`:

```python
# Instalar SDK principal (obrigatório)
%pip install databricks-sdk>=0.85.0 databricks-zerobus-ingest-sdk>=1.1.0

# Instalar grpcio-tools apenas se for compilar .proto customizados
# Verifique a versão do protobuf em runtime antes de instalar:
import google.protobuf
runtime_version = google.protobuf.__version__
print(f"Runtime protobuf version: {runtime_version}")

if runtime_version.startswith("5.26") or runtime_version.startswith("5.29"):
    %pip install grpcio-tools==1.62.0
else:
    %pip install grpcio-tools  # Use latest para versões de protobuf mais novas
```

> ⚠️ **Breaking change SDK Python (yanked v0.3.0 → v1.0.0):** A versão `0.3.0` foi removida do PyPI por breaking changes. O pin mínimo correto é `>=1.1.0` (lançada Mar 2026, estável).

Salve o `cluster_id` e `context_id` retornados para chamadas subsequentes.

---

## Prerequisites

Nunca execute a skill sem confirmar que os objetos abaixo são válidos:

1. **Uma Delta table gerenciada no Unity Catalog** como destino da ingestão
2. **Um service principal (client_id + secret)** com `MODIFY` e `SELECT` na tabela-alvo
3. **O endpoint Zerobus** do workspace (formato varia por cloud — veja abaixo)
4. **O Zerobus Ingest SDK** instalado para seu language-alvo

**Formatos de endpoint por cloud:**
- AWS: `https://<id>.zerobus.<região>.cloud.databricks.com`
- Azure: `https://<id>.zerobus.<região>.azuredatabricks.net`

See [1-setup-and-authentication.md](1-setup-and-authentication.md) para instruções completas.

---

## Minimal Python Example (JSON)

```python
import json
import logging
from zerobus.sdk.sync import ZerobusSdk
from zerobus.sdk.shared import RecordType, StreamConfigurationOptions, TableProperties

# Logging recomendado para debug de conexão e ACKs
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

sdk = ZerobusSdk(server_endpoint, workspace_url)
options = StreamConfigurationOptions(record_type=RecordType.JSON)
table_props = TableProperties(table_name)

stream = sdk.create_stream(client_id, client_secret, table_props, options)
try:
    record = {"device_name": "sensor-1", "temp": 22, "humidity": 55}
    stream.ingest_record(json.dumps(record))
    stream.flush()
finally:
    stream.close()
```

> O SDK Python usa PyO3 bindings para o Rust SDK, entregando até 40× maior throughput que Python puro. Suporta sync (`zerobus.sdk.sync`) e async (`zerobus.sdk.aio`), e 3 métodos de ingestão: **future-based**, **offset-based** e **fire-and-forget**.

---

## Detailed guides

| Topic | File | When to Read |
|-------|------|--------------|
| Setup & Auth | [1-setup-and-authentication.md](1-setup-and-authentication.md) | Endpoint formats por cloud, service principals, SDK install |
| Python Client | [2-python-client.md](2-python-client.md) | Sync/async Python, JSON e Protobuf, 3 métodos de ingestão, reusable client class |
| Multi-Language | [3-multilanguage-clients.md](3-multilanguage-clients.md) | Java (Public Preview), Go (1.21+), TypeScript, Rust |
| Protobuf Schema | [4-protobuf-schema.md](4-protobuf-schema.md) | Gerar .proto a partir de UC table, compilar, type mappings |
| Operations & Limits | [5-operations-and-limits.md](5-operations-and-limits.md) | ACK handling, retries, reconnection, throughput limits, quotas |

---

You must always follow all the steps in the Workflow

## Workflow
0. **Display the plan of your execution**
1. **Determinate the type of client**
2. **Get schema** Always use 4-protobuf-schema.md. Execute usando o MCP tool `execute_code`
3. **Write Python code to a local file** seguindo o guia relevante (e.g., `scripts/zerobus_ingest.py`)
4. **Execute on Databricks** using the `execute_code` MCP tool (with `file_path` parameter)
5. **If execution fails**: Edit the local file to fix the error, then re-execute
6. **Reuse the context** for follow-up executions passing `cluster_id` and `context_id`

---

## Important
- Never install local packages
- Always validate MCP server requirement before execution
- **Serverless limitation**: The Zerobus SDK cannot pip-install on serverless compute. Use classic compute clusters, or use the [Zerobus REST API](https://docs.databricks.com/aws/en/ingestion/zerobus-ingest) (Beta) for notebook-based ingestion without the SDK.
- **Explicit table grants**: Service principals need explicit `MODIFY` and `SELECT` grants on the target table. Schema-level inherited permissions may not be sufficient for the `authorization_details` OAuth flow.
- **Compliance workspaces not supported**: Zerobus Ingest não é suportado em workspaces com compliance security profile (FedRAMP, HIPAA, PCI-DSS).
- **Catalog commits incompatível**: Não use Zerobus Ingest em Delta tables com catalog commits habilitado.

---

### Context Reuse Pattern

The first execution auto-selects a running cluster and creates an execution context. **Reuse this context for follow-up calls** - it's much faster (~1s vs ~15s) and shares variables/imports:

**First execution** - use `execute_code` tool:
- `file_path`: "scripts/zerobus_ingest.py"

Returns: `{ success, output, error, cluster_id, context_id, ... }`

Save `cluster_id` and `context_id` for follow-up calls.

**If execution fails:**
1. Read the error from the result
2. Edit the local Python file to fix the issue
3. Re-execute with same context using `execute_code` tool:
   - `file_path`: "scripts/zerobus_ingest.py"
   - `cluster_id`: "<saved_cluster_id>"
   - `context_id`: "<saved_context_id>"

**Follow-up executions** reuse the context (faster, shares state):
- `file_path`: "scripts/validate_ingestion.py"
- `cluster_id`: "<saved_cluster_id>"
- `context_id`: "<saved_context_id>"

### Handling Failures

When execution fails:
1. Read the error from the result
2. **Edit the local Python file** to fix the issue
3. Re-execute using the same `cluster_id` and `context_id` (faster, keeps installed libraries)
4. If the context is corrupted, omit `context_id` to create a fresh one

---

### Installing Libraries

Databricks provides Spark, pandas, numpy, and common data libraries by default. **Only install a library if you get an import error.**

Use `execute_code` tool:
- `code`: "%pip install databricks-zerobus-ingest-sdk>=1.1.0"
- `cluster_id`: "<cluster_id>"
- `context_id`: "<context_id>"

The library is immediately available in the same context.

**Note:** Keeping the same `context_id` means installed libraries persist across calls.

## 🚨 Critical Learning: Timestamp Format Fix

**BREAKTHROUGH**: ZeroBus requires **timestamp fields as Unix integer timestamps**, NOT string timestamps.
The timestamp generation must use microseconds for Databricks.

---

## Key Concepts

- **gRPC + Protobuf**: Zerobus usa gRPC como protocolo primário. Qualquer aplicação que suporte gRPC e Protobuf pode produzir para o Zerobus.
- **3 interfaces disponíveis**:
  - **gRPC SDK** (GA): alta performance, conexões persistentes, melhor throughput — "connection tax" (cada stream conta contra cotas de concorrência).
  - **REST API** (Beta): stateless, handshake por request — "throughput tax" — ideal para frotas massivas de dispositivos que reportam com baixa frequência.
  - **OpenTelemetry / OTLP** (Beta, não cobrado ainda): para ambientes já instrumentados com OTel; ingere traces, logs e métricas em tabelas Delta com schemas pré-definidos, sem bibliotecas customizadas.
- **JSON or Protobuf serialization**: JSON para prototipação; Protobuf para type safety, forward compatibility e performance em produção.
- **At-least-once delivery**: O conector garante at-least-once. Projete consumidores para tolerar duplicatas.
- **Durability ACKs**: Cada registro ingerido retorna um `RecordAcknowledgment`. Use `flush()` para garantir que todos os registros bufferizados foram escritos de forma durável, ou `wait_for_offset(offset)` para rastreamento por offset.
- **No table management**: Zerobus não cria nem altera tabelas. Você deve pré-criar a tabela-alvo e gerenciar evolução de schema por conta própria.
- **Schema evolution (parcial)**: Colunas Delta **nullable** adicionadas à tabela são aceitas sem falha — campos ausentes são preenchidos com NULL. Colunas obrigatórias adicionadas ou remoções de colunas são breaking changes.
- **Rejected data on schema-break**: Se houver uma breaking change no schema da tabela após o Zerobus tornar os dados duráveis mas antes de publicá-los, os dados são salvos em `_zerobus/table_rejected_parquets/` dentro do storage root da tabela.
- **Single-AZ durability**: O serviço opera em uma única availability zone. Planeje para possíveis indisponibilidades de zona.
- **Liquid clustered tables (Beta)**: Escrita em liquid clustered tables está em Beta. Mantenha predictive optimization habilitado na tabela-alvo.
- **Partition limit**: Máximo de 1000 partições por janela de 5 segundos ao escrever em tabelas particionadas.

---

## Common Issues

| Issue | Solution |
|-------|----------|
| **Connection refused** | Verifique o formato do endpoint (AWS vs Azure). Adicione o IP ao allowlist do firewall. |
| **Authentication failed** | Confirme client_id/secret do service principal. Verifique os GRANTs explícitos na tabela. |
| **Schema mismatch** | Garanta que os campos do record correspondem exatamente ao schema da tabela. Regenere o .proto se a tabela mudou. |
| **Stream closed unexpectedly** | Implemente retry com exponential backoff e reinicialização do stream. Veja [5-operations-and-limits.md](5-operations-and-limits.md). |
| **Throughput limits hit** | Máx 100 MB/s e 15.000 rows/s por stream. Abra múltiplos streams ou contate o Databricks. |
| **Region not supported** | Verifique regiões suportadas em [5-operations-and-limits.md](5-operations-and-limits.md). |
| **Table not found** | Garanta que a tabela é uma Delta table gerenciada numa região suportada com nome three-part correto. |
| **SDK install fails on serverless** | O Zerobus SDK não pode ser instalado via pip em serverless compute. Use classic compute clusters ou a REST API (Beta). |
| **Error 4024 / authorization_details** | Service principal sem grants explícitos no nível da tabela. Conceda `MODIFY` e `SELECT` diretamente na tabela-alvo — grants herdados do schema podem ser insuficientes. |
| **Data disappeared after table schema change** | Dados rejeitados por breaking schema change ficam em `_zerobus/table_rejected_parquets/` no storage root da tabela. |
| **SDK version 0.3.0 import errors** | Versão yanked do PyPI por breaking changes. Faça upgrade para `>=1.1.0`. |
| **Compliance workspace error** | Zerobus Ingest não é suportado em workspaces FedRAMP, HIPAA ou PCI-DSS. Use um workspace sem compliance security profile. |
| **Catalog commits error** | Desabilite catalog commits na tabela-alvo antes de usar Zerobus Ingest. |
| **OTel token expires** | OAuth tokens expiram em 1h. Para aplicações de longa duração, use um OpenTelemetry Collector com `oauth2clientauthextension` para refresh automático. |

---

## Related Skills

- **[databricks-python-sdk](../databricks-python-sdk/SKILL.md)** - General SDK patterns and WorkspaceClient for table/schema management
- **[databricks-spark-declarative-pipelines](../databricks-spark-declarative-pipelines/SKILL.md)** - Downstream pipeline processing of ingested data
- **[databricks-unity-catalog](../databricks-unity-catalog/SKILL.md)** - Managing catalogs, schemas, and tables that Zerobus writes to
- **[databricks-synthetic-data-gen](../databricks-synthetic-data-gen/SKILL.md)** - Generate test data to feed into Zerobus producers
- **[databricks-config](../databricks-config/SKILL.md)** - Profile and authentication setup

## Resources

- [Zerobus Overview](https://docs.databricks.com/aws/en/ingestion/zerobus-overview)
- [Zerobus Ingest SDK](https://docs.databricks.com/aws/en/ingestion/zerobus-ingest)
- [Zerobus Limits](https://docs.databricks.com/aws/en/ingestion/zerobus-limits)
- [Zerobus OTLP (Beta) - Configure](https://docs.databricks.com/aws/en/ingestion/opentelemetry/configure)
- [Zerobus OTLP - Table Reference](https://docs.databricks.com/aws/en/ingestion/opentelemetry/table-reference)
- [GA Announcement Blog](https://www.databricks.com/blog/announcing-general-availability-zerobus-ingest-part-lakeflow-connect)

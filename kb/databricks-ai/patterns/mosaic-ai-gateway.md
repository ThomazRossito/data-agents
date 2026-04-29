# Mosaic AI Gateway & Unity AI Gateway

## Mosaic AI Gateway — Para LLMs Externos
Proxy unificado que governa todas as chamadas a LLMs (OpenAI, Anthropic, Azure OpenAI, etc.) com uma única API endpoint no Databricks.

```python
# Criar endpoint de modelo externo via Mosaic AI Gateway
import mlflow.deployments

client = mlflow.deployments.get_deploy_client("databricks")
client.create_endpoint(
    name="openai-gpt4o-gateway",
    config={
        "served_entities": [{
            "external_model": {
                "name": "gpt-4o",
                "provider": "openai",
                "task": "llm/v1/chat",
                "openai_config": {
                    "openai_api_key": "{{secrets/openai-scope/api-key}}"
                }
            }
        }],
        "rate_limits": [
            {"calls": 100, "key": "user", "renewal_period": "minute"}
        ],
        "guardrails": {
            "input": {
                "invalid_keywords": ["competitor_name"],
                "pii": {"behavior": "BLOCK"},
            },
            "output": {
                "toxicity": {"behavior": "WARN"}
            }
        }
    }
)
```

## Unity AI Gateway — MCPs Externos (GA Abril/2026)
Governa conexões a MCP servers externos com autenticação, rate limiting e audit trail nativo do Unity Catalog.

```python
# Registrar MCP externo no UC
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
w.ai_gateway.create_mcp_connection(
    name="github-mcp",
    provider="github",
    auth_type="oauth",
    oauth_config={
        "client_id": "{{secrets/github-scope/client-id}}",
        "client_secret": "{{secrets/github-scope/client-secret}}",
    },
    rate_limits={"calls_per_minute": 60},
    allowed_principals=["group:data-engineers"],
)
```

**Problema resolvido:** Sem Unity AI Gateway, cada agente/notebook conecta direto ao MCP server — sem auditoria, sem rate limit centralizado, sem controle de quem acessa o quê. Com o Gateway, toda chamada MCP é auditada no UC Audit Log.

## Métricas de Observability (Mosaic AI Gateway)
Métricas automáticas por endpoint:
- `latency_p50/p95/p99` — percentis de latência
- `tokens_input/output` — consumo de tokens
- `requests_total` — throughput
- `error_rate` — % de erros por tipo

Acessar via:
```sql
SELECT * FROM system.ai.endpoint_metrics
WHERE endpoint_name = 'openai-gpt4o-gateway'
AND timestamp >= DATEADD(HOUR, -24, CURRENT_TIMESTAMP())
```

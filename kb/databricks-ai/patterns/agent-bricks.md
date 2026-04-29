# Agent Bricks (GA Abril/2026)

## O que é Agent Bricks
Framework oficial do Databricks para construir, registrar e governar agentes de AI com integração nativa ao Unity Catalog.

## Agent Registry no Unity Catalog
Agentes são objetos de primeira classe no UC — com versionamento, lineage, ACL e audit trail.

```python
import mlflow
from databricks.agents import deploy

# Registrar agente no UC
with mlflow.start_run():
    mlflow.pyfunc.log_model(
        artifact_path="agent",
        python_model=MyAgent(),
        registered_model_name="prod.agents.sales_analyst",
    )

# Deploy como endpoint
deploy(
    model_name="prod.agents.sales_analyst",
    model_version=1,
    scale_to_zero=True,
)
```

## Tool Sharing
Agentes podem compartilhar ferramentas registradas no UC:
```python
from databricks.agents.tools import UCTool

query_tool = UCTool(
    func_name="prod.tools.query_sales_data",
    description="Query sales data by date range and region",
)

agent = create_react_agent(
    llm=llm,
    tools=[query_tool],
)
```

## Bug Checkpointing (>90 min)
Para workflows de agentes longos (>90 min), usar checkpointing para retomar sem re-executar do início:
```python
from databricks.agents import AgentWorkflow

workflow = AgentWorkflow(
    checkpoint_enabled=True,
    checkpoint_location="abfss://agent-checkpoints@account.dfs.core.windows.net/workflows/",
)

# Workflow retoma do último checkpoint se interrompido
result = workflow.run(task="Analyse full Q1 sales data")
```

## Mosaic AI Gateway Integration
Agent Bricks integra automaticamente com Mosaic AI Gateway para:
- Métricas de latência e throughput por agente
- Guardrails de input/output
- Rate limiting por endpoint de agente
```python
# Configurado no endpoint de deploy
deploy(
    model_name="prod.agents.sales_analyst",
    model_version=1,
    guardrails={
        "input": {"pii": {"behavior": "BLOCK"}},
        "output": {"toxicity": {"behavior": "BLOCK"}},
    }
)
```

## Lineage no UC
- Cada chamada ao agente é auditada no UC Audit Log
- Lineage: quais tabelas/views o agente leu durante execução
- ACL: controle de quem pode chamar o endpoint do agente

# Databricks AI Quick Reference

## Products Map (Abril 2026)
| Produto | Função | Status |
|---------|--------|--------|
| **Agent Bricks** | Framework de agentes com UC Registry | GA Abr/2026 |
| **Mosaic AI Gateway** | Governa chamadas a LLMs (guardrails, métricas, rate limit) | GA |
| **Unity AI Gateway** | Proxy para MCPs externos com auth + audit | GA Abr/2026 |
| **Genie** | Analytics autônomo (text → SQL → insights) com Agent Mode | GA Abr/2026 |
| **MLflow** | Tracking, Model Registry, Evaluation | GA |
| **Model Serving** | Endpoints REST para modelos (Foundation + custom) | GA |
| **Feature Store** | Features compartilhadas para treino e serving | GA |
| **Lakehouse Monitoring** | Drift detection e data quality em tabelas | GA |
| **AutoML** | Geração automática de modelos baseline | GA |

## Model Serving — Tipos de Endpoint
| Tipo | Modelo | Caso de Uso |
|------|--------|------------|
| Foundation Model | LLama, Mistral, DBRX | Chat, completion, embedding |
| External Model | OpenAI, Anthropic | Proxy unificado via Gateway |
| Custom Model | MLflow model | Modelos treinados internamente |
| Feature & Function | Python UDF | Feature serving realtime |

## Agent Memory Types
| Tipo | Duração | Implementação |
|------|---------|---------------|
| Short-term | Durante sessão | Context window |
| Long-term | Entre sessões | Vector DB / Delta Table |
| Episodic | Por episódio | Checkpoint no UC |

## MLflow — Entities Principais
```
Experiment → Runs → Artifacts → Metrics/Params
                 ↓
          Model Registry → Versions → Aliases (champion/challenger)
```

## Guardrails — Categorias
- **Input**: PII detection, topic restriction, prompt injection detection
- **Output**: toxicity, hallucination detection, citation check
- **Rate limiting**: por usuário/app/endpoint

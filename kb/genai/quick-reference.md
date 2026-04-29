# GenAI Architecture Quick Reference

> Tabelas de lookup rápido. Para exemplos completos ver arquivos linkados.

## Topologias de Orquestração

| Topologia | Estrutura | Melhor para | Complexidade |
|-----------|-----------|-------------|-------------|
| Sequential | Cadeia A→B→C | Pipelines step-by-step | Baixa |
| Fan-out | Hub→[A,B,C] | Tarefas independentes em paralelo | Média |
| Hub-and-Spoke | Supervisor + Specialists | Coordenação centralizada (este projeto) | Média |
| Mesh | Peer-to-peer | Sistemas distribuídos resilientes | Alta |
| Plan-and-Execute | Planner + Executor | Multi-step cost-optimized | Alta |

## Tipos de Guardrail

| Tipo | Camada | Propósito | Exemplo no projeto |
|------|--------|-----------|-------------------|
| Input rails | Pré-LLM | Filtrar inputs destrutivos | `security_hook.py` |
| Output rails | Pós-LLM | Validar respostas | Pydantic + rubric |
| Topic rails | Pré-LLM | Restringir escopo | Regex de routing |
| Confidence threshold | Routing | Recusar se score < threshold | `_assess_confidence` |
| Budget guard | Runtime | Limitar tokens/custo | `cost_guard_hook.py` |

## Métricas de Avaliação

| Métrica | Mede | Range | Onde usar |
|---------|------|-------|-----------|
| Pass Rate | % queries que passam rubric | 0–1 | `evals/runner.py` (CI) |
| Routing Precision | Agente correto selecionado | 0/1 | must_include de evals |
| Faithfulness | Grounding no KB/contexto | 0–1 | Avaliação periódica |
| Answer Relevancy | Alinhamento query-resposta | 0–1 | Avaliação periódica |

## Model Tiering

| Tier | Modelo | Max Turns | Use Case |
|------|--------|-----------|----------|
| T1 | claude-sonnet-4-6 | 20 | Orquestração, código complexo, arquitetura |
| T2 | gpt-4.1 | 12 | Domínio específico: auditoria, dbt, qualidade |
| T3 | gpt-4.1-mini | 5 | Conceitual, FAQ — ~95% mais barato |

## Confidence Thresholds

| Criticidade | Threshold | On Failure | Exemplos |
|------------|----------|-----------|---------|
| CRITICAL | 0.98 | REFUSE | DROP TABLE, secrets, DELETE sem WHERE |
| IMPORTANT | 0.95 | ASK | ALTER TABLE, deploy em produção, migrations |
| STANDARD | 0.90 | PROCEED | pipeline logic, transforms, Silver→Gold |
| ADVISORY | 0.80 | PROCEED | documentação, otimização, conceitual |

## Decision Matrix

| Cenário | Solução |
|---------|---------|
| Q&A conceitual sem MCP | T3 (geral) — mais barato |
| Código PySpark complexo | T1 (spark_expert) |
| Auditoria PII / LGPD | T2 (governance_auditor) |
| Pipeline E2E com execução | T1 (pipeline_architect) |
| Múltiplos agentes em paralelo | Party Mode (/party) |
| Tarefa ambígua | Supervisor → PRD → delegação |
| Tarefa CRITICAL com confidence baixa | REFUSE imediato |

## Common Pitfalls

| Evite | Prefira |
|-------|---------|
| Modelo frontier para todo step | Model tiering por criticidade |
| Sem métricas de avaliação | Rubric determinística desde o início |
| Agentes monolíticos | Specialists com domínio claro + handoffs explícitos |
| Guardrails apenas no output | Layered: input + routing + output |
| Chamar MCP diretamente sem KB | KB-First sempre: kb/ antes de MCP |

## Related

| Tópico | Arquivo |
|--------|---------|
| Supervisor + Specialist (implementação) | patterns/agentic-workflow.md |
| Rubric vs LLM-as-judge | patterns/evaluation-framework.md |
| Thresholds de confiança | specs/genai-patterns.yaml |

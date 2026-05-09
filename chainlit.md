# Data Agents — Copiloto de Engenharia de Dados

**Databricks + Microsoft Fabric · 14 agentes especialistas · 15 MCPs**

---

## Agentes Disponíveis

| Tier | Agente | Especialidade |
|------|--------|---------------|
| T1 | `databricks-engineer` | SQL, PySpark, DLT, Jobs, Genie, AI/BI, CDC |
| T1 | `databricks-ai` | RAG, Vector Search, LLMOps, Streaming, Kafka/Flink |
| T1 | `fabric-engineer` | Medallion, Semantic Models, DAX, FinOps, Star Schema |
| T1 | `migration-expert` | SQL Server/PostgreSQL → Databricks/Fabric |
| T1 | `python-expert` | Python puro: pacotes, APIs, CLIs, testes |
| T2 | `dbt-expert` | dbt Core: models, testes, snapshots, docs |
| T2 | `data-quality-steward` | Expectations, profiling, SLA, drift detection |
| T2 | `governance-auditor` | LGPD, PII, linhagem, RLS/OLS, auditoria |
| T2 | `data-contracts-engineer` | ODCS, SLA contratual, breaking changes |
| T2 | `data-mesh-architect` | Data Mesh, Data Products, governança federada |
| T2 | `fabric-rti` | Eventhouse, KQL, Eventstream, Activator |
| T2 | `fabric-ontology` | OWL 2, RDF, SPARQL, Fabric IQ Ontology |
| T3 | `business-analyst` | Intake de requisitos, backlog estruturado |
| T0 | `geral` | Perguntas conceituais, respostas rápidas sem MCP |

---

## Comandos Mais Usados

```
/sql <query>          → SQL/Spark SQL direto no Databricks
/pipeline <tarefa>    → Pipeline ETL Databricks
/fabric <tarefa>      → Microsoft Fabric
/quality <tarefa>     → Qualidade de dados
/governance <tarefa>  → Auditoria e governança
/migrate <fonte>      → Migração de banco relacional
/dbt <tarefa>         → dbt Core
/party <query>        → Multi-agente paralelo com perspectivas independentes
/plan <objetivo>      → Planejamento com thinking habilitado
/geral <pergunta>     → Resposta direta sem Supervisor (~95% mais barato)
```

---

## Dicas

- **Seja específico**: mencione nomes de tabelas, schemas, workspaces quando relevante.
- **`/party`** traz múltiplos especialistas respondendo em paralelo — ótimo para decisões de arquitetura.
- **`/plan`** ativa extended thinking — use para tarefas complexas que envolvem múltiplos agentes.
- **`/geral`** para perguntas conceituais rápidas — usa Haiku 4.5 diretamente, sem orquestração.

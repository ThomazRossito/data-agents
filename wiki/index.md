# Data Agents — Índice Central

Sistema multi-agente construído sobre o Claude Agent SDK da Anthropic.
Orquestra 14 agentes especialistas em Engenharia, Qualidade, Governança, Análise de Dados, Streaming, FinOps e Web Semântica.

---

## Regras e Governança

- [[constitution]] — Regras invioláveis de todos os agentes
- [[collaboration-workflows]] — Workflows colaborativos WF-01 a WF-05
- [[task_routing]] — Mapa de delegação e roteamento de tarefas

---

## Agentes

### Tier 1 — Engineering Core
- [[databricks-engineer]] — SQL (Unity Catalog/Spark SQL), PySpark, LakeFlow/DLT, CDC, Jobs, diagnóstico Spark, Genie, AI/BI Dashboards
- [[databricks-ai]] — RAG, Vector Search, embeddings, LLMOps, AI Functions, Kafka, Flink, Spark Structured Streaming
- [[fabric-engineer]] — Fabric completo: Medallion, Data Factory, Star Schema, Semantic Models, DAX, Catalog, FinOps
- [[migration-expert]] — Migração SQL Server/PostgreSQL → Databricks/Fabric
- [[python-expert]] — Python puro: pacotes, APIs, CLIs, testes

### Tier 2 — Especializados
- [[dbt-expert]] — dbt Core: models, testes, snapshots
- [[data-quality-steward]] — Validação, profiling, SLA cross-platform
- [[governance-auditor]] — Auditoria, LGPD, linhagem, RLS/OLS
- [[data-contracts-engineer]] — ODCS, SLA contratual, breaking changes
- [[data-mesh-architect]] — Data Mesh, Data Products, governança federada
- [[fabric-rti]] — Fabric Real-Time Intelligence: Eventhouse, KQL, Eventstream, Activator
- [[fabric-ontology]] — OWL 2, RDF, SPARQL, Fabric IQ Ontology

### Tier 3 — Conversacionais
- [[business-analyst]] — Intake de requisitos, /brief, /ship

### Tier 0 — Direto (sem MCP)
- [[geral]] — Perguntas conceituais, zero MCP (Haiku)

---

## Knowledge Base (KB)

> Consultada pelos agentes antes de qualquer tarefa (KB-First protocol)

- [[kb/constitution]] — Regras centrais
- [[kb/pipeline-design/index]] — Medallion, cross-platform, orquestração
- [[kb/databricks/index]] — Jobs, Bundles, Unity Catalog, AI/ML
- [[kb/fabric/index]] — Lakehouse, Direct Lake, RTI, Data Factory
- [[kb/sql-patterns/index]] — SQL dialetos, boas práticas
- [[kb/spark-patterns/index]] — Spark, DataFrame, streaming
- [[kb/semantic-modeling/index]] — DAX, Genie Spaces
- [[kb/data-quality/index]] — Profiling, validação, SLA
- [[kb/governance/index]] — Auditoria, PII, compliance
- [[kb/python-patterns/index]] — Packaging, testes, padrões
- [[kb/migration/index]] — Assessment, SQL Server/PostgreSQL

---

## Skills Operacionais

> Playbooks de como executar tarefas (lidos on-demand pelos agentes)

- [[skills/pipeline_design]] — Design de pipelines
- [[skills/sql_generation]] — Geração de SQL
- [[skills/spark_patterns]] — Padrões PySpark
- [[skills/star_schema_design]] — Modelagem Star Schema
- [[skills/data_quality]] — Qualidade de dados

---

## Memórias do Sistema

> Capturadas automaticamente durante sessões

- [[memory/data/index]] — Índice de todas as memórias ativas

---

## Documentação Estratégica

- [[to_do/ANALISE_ESTRATEGICA_E_ROADMAP]] — Roadmap S0–S6
- [[to_do/PLANO_EXECUCAO]] — Plano de execução faseado
- [[to_do/GAPS_E_MELHORIAS]] — Backlog de melhorias
- [[README]] — Guia completo do projeto
- [[CHANGELOG]] — Histórico de versões

---

## Configuração

- [[.claude/CLAUDE.md]] — Guia para Claude Code (este projeto)
- [[Dashboard]] — Dashboard com queries Dataview

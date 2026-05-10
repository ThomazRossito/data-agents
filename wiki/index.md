# Data Agents — Índice Central

Sistema multi-agente construído sobre o Claude Agent SDK da Anthropic.
Orquestra 13 agentes especialistas em Engenharia, Qualidade, Governança e Análise de Dados.

---

## Regras e Governança

- [[constitution]] — Regras invioláveis de todos os agentes
- [[collaboration-workflows]] — Workflows colaborativos WF-01 a WF-05
- [[task_routing]] — Mapa de delegação e roteamento de tarefas

---

## Agentes

### Tier 1 — Core (Pipelines Complexos)
- [[sql-expert]] — SQL, schemas, catálogos Databricks e Fabric
- [[spark-expert]] — PySpark, DLT, Delta Lake
- [[python-expert]] — Python puro: pacotes, APIs, CLIs, testes
- [[pipeline-architect]] — ETL/ELT cross-platform
- [[migration-expert]] — Migração SQL Server/PostgreSQL → Databricks/Fabric

### Tier 2 — Especializados
- [[dbt-expert]] — dbt Core: models, testes, snapshots
- [[data-quality-steward]] — Validação, profiling, SLA
- [[governance-auditor]] — Auditoria, LGPD, linhagem
- [[semantic-modeler]] — Modelos semânticos, DAX, Genie
- [[business-monitor]] — Q&A interativo sobre alertas

### Tier 3 — Conversacionais
- [[business-analyst]] — Intake de requisitos, /brief
- [[geral]] — Perguntas conceituais, zero MCP

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

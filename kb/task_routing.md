# Task Routing — Mapa de KBs, Skills e Agentes

Fonte única de verdade para roteamento de tarefas. Leia com `Read("kb/task_routing.md")`
ANTES de planejar qualquer tarefa no Supervisor ou no Party Mode.

Este arquivo substitui as tabelas que antes viviam duplicadas em
`agents/prompts/supervisor_prompt.py`. Atualizações aqui são automaticamente refletidas
em runtime pelo Supervisor via `Read()`.

---

## 1. KB-First — Mapa por Tipo de Tarefa

Antes de planejar, leia a KB indicada. Skills são opcionais (detalhes operacionais).

| Tipo de Tarefa                                       | KB a Ler Primeiro                   | Skill Operacional                                                                                    |
|------------------------------------------------------|-------------------------------------|------------------------------------------------------------------------------------------------------|
| Pipeline SDP/LakeFlow (Spark Declarative)            | `kb/pipeline-design/index.md`       | `skills/databricks/databricks-spark-declarative-pipelines/SKILL.md` + `skills/patterns/pipeline-design/SKILL.md`    |
| Pipeline Spark Structured Streaming                  | `kb/spark-patterns/index.md`        | `skills/databricks/databricks-spark-structured-streaming/SKILL.md`                                   |
| DDL / Tabelas Delta / Unity Catalog                  | `kb/sql-patterns/index.md`          | `skills/patterns/sql-generation/SKILL.md` + `skills/databricks/databricks-unity-catalog/SKILL.md`                   |
| SQL Warehouse / Materialized Views                   | `kb/databricks/index.md`            | `skills/databricks/databricks-dbsql/SKILL.md`                                                        |
| Databricks Jobs / Workflows / Orquestração           | `kb/databricks/index.md`            | `skills/databricks/databricks-jobs/SKILL.md`                                                         |
| Databricks Asset Bundles / CI-CD                     | `kb/databricks/index.md`            | `skills/databricks/databricks-bundles/SKILL.md`                                                      |
| Model Serving / MLflow / Deploy de Agentes           | `kb/databricks/index.md`            | `skills/databricks/databricks-model-serving/SKILL.md`                                                |
| Vector Search / RAG                                  | `kb/databricks/index.md`            | `skills/databricks/databricks-vector-search/SKILL.md`                                                |
| AI Functions (ai_query, ai_forecast)                 | `kb/databricks/index.md`            | `skills/databricks/databricks-ai-functions/SKILL.md`                                                 |
| Genie Space (criar/atualizar — Conversational BI)    | `kb/semantic-modeling/index.md`     | `skills/databricks/databricks-genie/SKILL.md`                                                        |
| AI/BI Dashboard (criar/publicar)                     | `kb/semantic-modeling/index.md`     | `skills/databricks/databricks-aibi-dashboards/SKILL.md`                                              |
| Knowledge Assistants / Mosaic AI Agents (KA/MAS)     | `kb/databricks/index.md`            | `skills/databricks/databricks-agent-bricks/SKILL.md`                                                 |
| Execução de código serverless                        | `kb/databricks/index.md`            | *(use `mcp__databricks__execute_code`)*                                                              |
| Múltiplas queries SQL em paralelo                    | `kb/sql-patterns/index.md`          | `skills/patterns/sql-generation/SKILL.md` (use `execute_sql_multi`)                                                 |
| Fabric Lakehouse / Medallion                         | `kb/fabric/index.md`                | `skills/fabric/fabric-medallion/SKILL.md` + `skills/patterns/pipeline-design/SKILL.md`                              |
| Fabric Direct Lake / Power BI                        | `kb/fabric/index.md`                | `skills/fabric/fabric-direct-lake/SKILL.md`                                                          |
| Semantic Model Fabric (análise/criação/DAX)          | `kb/semantic-modeling/index.md`     | `skills/fabric/fabric-direct-lake/SKILL.md`                                                          |
| Fabric RTI / Eventhouse / KQL / Activator            | `kb/fabric/index.md`                | `skills/fabric/fabric-eventhouse-rti/SKILL.md`                                                       |
| Fabric Data Factory / Dataflows Gen2                 | `kb/fabric/index.md`                | `skills/fabric/fabric-data-factory/SKILL.md`                                                         |
| Fabric ↔ Databricks (Cross-Platform)                 | `kb/pipeline-design/index.md`       | `skills/fabric/fabric-cross-platform/SKILL.md` + `skills/patterns/pipeline-design/SKILL.md`                         |
| Qualidade de Dados / Expectations / Profiling        | `kb/data-quality/index.md`          | `skills/patterns/data-quality/SKILL.md`                                                                             |
| Governança / Auditoria / Linhagem / PII              | `kb/governance/index.md`            | `skills/databricks/databricks-unity-catalog/SKILL.md`                                                |
| Modelagem Semântica / DAX / Direct Lake              | `kb/semantic-modeling/index.md`     | `skills/fabric/fabric-direct-lake/SKILL.md`                                                          |
| Star Schema / Modelagem Dimensional (Gold)           | `kb/pipeline-design/index.md`       | `skills/patterns/star-schema-design/SKILL.md`                                                                       |
| Databricks Metric Views / Semantic Layer             | `kb/semantic-modeling/index.md`     | `skills/databricks/databricks-metric-views/SKILL.md`                                                 |
| Padrões Spark genéricos                              | `kb/spark-patterns/index.md`        | `skills/patterns/spark-patterns/SKILL.md`                                                                           |
| Pipeline End-to-End / Multi-Agente / Workflow        | `kb/collaboration-workflows.md`     | `templates/pipeline-spec.md` ou `templates/star-schema-spec.md`                                      |
| Migração Cross-Platform / Multi-Plataforma           | `kb/collaboration-workflows.md`     | `templates/cross-platform-spec.md`                                                                   |
| Transcript / Briefing / Requisitos não estruturados  | *(delegar ao business-analyst)*    | `templates/backlog.md`                                                                               |

---

## 2. Roteamento por Situação — Qual Agente Acionar

> **Fonte de verdade:** `agents/delegation_map.yaml`.
> Esta tabela é gerada por `agents.delegation.render_routing_table()`. Para adicionar
> ou alterar um route, edite o YAML e regenere com:
> `python -c "from agents.delegation import render_routing_table; print(render_routing_table())"`

<!-- BEGIN delegation_map (auto-gerado) -->
| Situação                                             | Agente a Acionar     |
|------------------------------------------------------|----------------------|
| Migração SQL Server/PostgreSQL → Databricks/Fabric   | migration-expert     |
| /migrate ou assessment de banco relacional           | migration-expert     |
| DDL de origem extraído → propor Medallion            | migration-expert     |
| Transcript / briefing / notas brutas                 | business-analyst     |
| Input não estruturado antes do /plan                 | business-analyst     |
| Tabela nova ingerida → validar qualidade             | data-quality-steward |
| Alerta de qualidade disparado → investigar           | data-quality-steward |
| Schema drift em streaming                            | data-quality-steward |
| Pipeline modificado → verificar conformidade         | governance-auditor   |
| Acesso incomum detectado → auditar                   | governance-auditor   |
| Dados PII expostos → classificar e proteger          | governance-auditor   |
| Gold Layer criada → preparar para consumo BI         | semantic-modeler     |
| Semantic Model mencionado (Fabric/Power BI/DAX)      | semantic-modeler     |
| Criar/atualizar Genie Space (Databricks)             | semantic-modeler     |
| Criar/publicar AI/BI Dashboard (Databricks)          | semantic-modeler     |
| Consultar endpoint de modelo ML/GenAI                | semantic-modeler     |
| Relatório de métricas / análise consumível           | semantic-modeler     |
| Criar Knowledge Assistant (KA) / Mosaic (MAS)        | pipeline-architect   |
| Executar código serverless / criar cluster/warehouse | pipeline-architect   |
| Múltiplas queries SQL independentes em paralelo      | sql-expert           |
| PySpark / Spark SQL / DLT                            | spark-expert         |
| dbt (models, refs, sources, testes, snapshots)       | dbt-expert           |
| Python puro (pacotes, APIs, CLIs, pandas/polars)     | python-expert        |
| Alerta de negócio recebido (estoque, vendas, SLA)    | business-monitor     |
| Pergunta conceitual sem MCP                          | geral                |
<!-- END delegation_map -->


---

## 3. Workflow Context Cache — Template

Antes de invocar o primeiro agente de qualquer workflow **WF-01 a WF-05**, o Supervisor
DEVE compilar um arquivo de contexto unificado em `output/workflow-context/{wf_id}-context.md`
com o seguinte formato:

```markdown
# [{WF-ID}] {Nome do Workflow} — Contexto Compilado

**Gerado:** {data e hora}
**Workflow:** {nome}
**Agentes envolvidos:** {lista em ordem de execução}
**Spec:** {caminho da spec ou "não gerada"}

---

## Especificação do Workflow
{Conteúdo completo da spec, ou resumo da tarefa se não existir spec}

---

## Regras Constitucionais Aplicáveis
{Excertos de kb/constitution.md relevantes: §4 Medallion/Star, §5 Plataforma,
 §6 Segurança, §7 Qualidade — incluir apenas o que se aplica ao workflow em curso}

---

## Sequência de Handoff
{Tabela: etapa | agente | input esperado | output esperado}
```

No prompt de **cada agente** do workflow, o Supervisor inclui:

> 📋 Contexto compilado do workflow: `output/workflow-context/{wf_id}-context.md`
> Leia este arquivo com Read() ANTES de iniciar sua tarefa. Ele contém a spec,
> regras constitucionais e a sequência completa do workflow.

**Benefícios:** contexto idêntico para todos os agentes; menos tokens totais;
auditoria facilitada.

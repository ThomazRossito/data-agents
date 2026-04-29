"""workflow.dag — Definição dos workflows e detecção de triggers."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# ── Padrões de detecção ──────────────────────────────────────────────────────

WORKFLOW_PATTERN = re.compile(r"WF-0([1-7])", re.IGNORECASE)

WF_TRIGGER_PATTERNS: dict[str, re.Pattern] = {
    "WF-01": re.compile(
        r"(criar|construir|implementar|desenvolver|montar|gerar)\s+"
        r"(?:um\s+|o\s+|novo\s+)?pipeline\s+(completo|end.to.end|"
        r"bronze\s+at[eé]\s+gold)|"
        r"pipeline\s+e2e|b2g",
        re.IGNORECASE,
    ),
    "WF-02": re.compile(
        r"(criar|construir|implementar|modelar|desenhar)\s+"
        r"(?:um\s+|uma\s+|o\s+)?(star\s+schema|modelo\s+dimensional|"
        r"tabela\s+fato|camada\s+gold)|"
        r"fato\s+e\s+dimens",
        re.IGNORECASE,
    ),
    # WF-05/06/07 antes do WF-03 — mais específicos (lakehouse) têm prioridade
    "WF-05": re.compile(
        r"(implantar|criar|montar|provisionar|construir|desenhar|setup)\s+"
        r"(?:um\s+|uma\s+|o\s+|a\s+|novo\s+|nova\s+){0,2}lakehouse|"
        r"lakehouse\s+(do\s+)?zero",
        re.IGNORECASE,
    ),
    "WF-06": re.compile(
        r"migrar?\s+(o\s+|a\s+|do\s+|de\s+)?(lakehouse|synapse)",
        re.IGNORECASE,
    ),
    "WF-07": re.compile(
        r"(sustent\w*|otimizar|monitorar|fazer\s+vacuum|observabilidade|"
        r"reduzir\s+custo)\s+(?:do\s+|no\s+|em\s+|de\s+)?lakehouse",
        re.IGNORECASE,
    ),
    "WF-03": re.compile(
        r"migrar?\s+(?:.*\s+)?para\s+(fabric|databricks)|"
        r"(?:mover|portar)\s+(?:.*\s+)?(para|de)\s+(fabric|databricks)",
        re.IGNORECASE,
    ),
    "WF-04": re.compile(
        r"(fazer|executar|realizar|conduzir|rodar)\s+"
        r"(uma\s+|a\s+|um\s+)?(auditoria|relat[oó]rio\s+de\s+compliance|"
        r"naming\s+audit|auditar\s+nomenclatura|governan[cç]a\s+completa)",
        re.IGNORECASE,
    ),
}


@dataclass
class WorkflowStep:
    agent_name: str
    description: str
    output_key: str  # chave para guardar resultado no contexto


@dataclass
class WorkflowDef:
    id: str
    name: str
    trigger_description: str
    steps: list[WorkflowStep] = field(default_factory=list)


# ── Definições dos Workflows ─────────────────────────────────────────────────

WORKFLOWS: dict[str, WorkflowDef] = {
    "WF-01": WorkflowDef(
        id="WF-01",
        name="Pipeline End-to-End (Bronze → Gold)",
        trigger_description="pipeline completo, end-to-end, bronze até gold",
        steps=[
            WorkflowStep(
                agent_name="spark_expert",
                description=(
                    "Criar DDL + código PySpark Medallion "
                    "(Bronze→Silver→Gold)"
                ),
                output_key="pipeline_code",
            ),
            WorkflowStep(
                agent_name="data_quality",
                description=(
                    "Definir expectations de qualidade e profiling "
                    "para as tabelas geradas na etapa anterior"
                ),
                output_key="quality_report",
            ),
        ],
    ),
    "WF-02": WorkflowDef(
        id="WF-02",
        name="Star Schema Design + Implementação",
        trigger_description="star schema, camada gold, modelo dimensional",
        steps=[
            WorkflowStep(
                agent_name="sql_expert",
                description=(
                    "Criar DDL de tabelas fato e dimensão (Gold) "
                    "com constraints e comentários"
                ),
                output_key="ddl",
            ),
            WorkflowStep(
                agent_name="spark_expert",
                description=(
                    "Criar pipeline PySpark para popular o star schema "
                    "usando o DDL da etapa anterior"
                ),
                output_key="pipeline_code",
            ),
            WorkflowStep(
                agent_name="data_quality",
                description=(
                    "Validar integridade referencial e definir expectations "
                    "para as tabelas criadas"
                ),
                output_key="quality_report",
            ),
        ],
    ),
    "WF-03": WorkflowDef(
        id="WF-03",
        name="Migração Cross-Platform",
        trigger_description="migrar, mover para Fabric, mover para Databricks",
        steps=[
            WorkflowStep(
                agent_name="pipeline_architect",
                description=(
                    "Definir estratégia de conectividade e plano de migração "
                    "entre as plataformas"
                ),
                output_key="migration_plan",
            ),
            WorkflowStep(
                agent_name="sql_expert",
                description=(
                    "Converter DDL entre dialetos SQL conforme o plano "
                    "de migração da etapa anterior"
                ),
                output_key="converted_ddl",
            ),
            WorkflowStep(
                agent_name="spark_expert",
                description=(
                    "Criar pipeline PySpark de movimentação de dados "
                    "usando o DDL convertido"
                ),
                output_key="migration_pipeline",
            ),
        ],
    ),
    "WF-04": WorkflowDef(
        id="WF-04",
        name="Auditoria de Governança",
        trigger_description=(
            "auditoria, governança completa, compliance, naming audit"
        ),
        steps=[
            WorkflowStep(
                agent_name="naming_guard",
                description=(
                    "Auditar nomenclatura de todos os objetos mencionados "
                    "e listar violações com sugestões de rename"
                ),
                output_key="naming_violations",
            ),
            WorkflowStep(
                agent_name="governance_auditor",
                description=(
                    "Auditar PII, LGPD e controles de acesso usando "
                    "os objetos identificados nas etapas anteriores"
                ),
                output_key="governance_report",
            ),
            WorkflowStep(
                agent_name="data_quality",
                description=(
                    "Verificar SLAs de qualidade e gerar checklist final "
                    "de conformidade para os objetos auditados"
                ),
                output_key="quality_sla_report",
            ),
        ],
    ),
    "WF-05": WorkflowDef(
        id="WF-05",
        name="Implantação de Lakehouse",
        trigger_description="implantar, criar lakehouse, novo lakehouse, setup lakehouse",
        steps=[
            WorkflowStep(
                agent_name="pipeline_architect",
                description=(
                    "Definir arquitetura do Lakehouse: camadas medallion, "
                    "estratégia de particionamento e modelo de dados inicial"
                ),
                output_key="architecture_plan",
            ),
            WorkflowStep(
                agent_name="fabric_expert",
                description=(
                    "Configurar Lakehouse no Fabric (OneLake, shortcuts, "
                    "Direct Lake) ou Databricks (Unity Catalog, external location) "
                    "conforme o plano da etapa anterior"
                ),
                output_key="platform_setup",
            ),
            WorkflowStep(
                agent_name="spark_expert",
                description=(
                    "Criar DDL das tabelas Delta e pipeline PySpark inicial "
                    "para ingestão de dados usando o setup da etapa anterior"
                ),
                output_key="pipeline_code",
            ),
            WorkflowStep(
                agent_name="devops_engineer",
                description=(
                    "Criar bundle de infraestrutura (DAB ou Fabric CI/CD) "
                    "para deployment automatizado do Lakehouse"
                ),
                output_key="infra_bundle",
            ),
            WorkflowStep(
                agent_name="governance_auditor",
                description=(
                    "Validar controles de acesso, PII e LGPD para o Lakehouse "
                    "implantado, gerando checklist de conformidade"
                ),
                output_key="governance_checklist",
            ),
        ],
    ),
    "WF-06": WorkflowDef(
        id="WF-06",
        name="Migração de Lakehouse",
        trigger_description=(
            "migrar lakehouse, migrar para Databricks, migrar para Fabric, "
            "migrar Synapse"
        ),
        steps=[
            WorkflowStep(
                agent_name="sql_expert",
                description=(
                    "Inventariar e converter DDL de origem para o dialeto de destino, "
                    "identificando incompatibilidades de tipos e funções"
                ),
                output_key="ddl_conversion",
            ),
            WorkflowStep(
                agent_name="pipeline_architect",
                description=(
                    "Definir estratégia de migração (big bang vs incremental), "
                    "plano de cutover e rollback usando o DDL convertido"
                ),
                output_key="migration_plan",
            ),
            WorkflowStep(
                agent_name="spark_expert",
                description=(
                    "Criar pipeline PySpark de movimentação de dados "
                    "com validação checksum e controle de idempotência"
                ),
                output_key="migration_pipeline",
            ),
            WorkflowStep(
                agent_name="devops_engineer",
                description=(
                    "Configurar pipeline CI/CD para deploy do Lakehouse destino "
                    "e automação do cutover"
                ),
                output_key="cicd_pipeline",
            ),
            WorkflowStep(
                agent_name="data_quality",
                description=(
                    "Executar reconciliação pós-migração: contagem de registros, "
                    "checksums e expectations de qualidade no destino"
                ),
                output_key="reconciliation_report",
            ),
            WorkflowStep(
                agent_name="governance_auditor",
                description=(
                    "Validar que permissões, PII masking e controles de LGPD "
                    "foram replicados corretamente no destino"
                ),
                output_key="governance_sign_off",
            ),
        ],
    ),
    "WF-07": WorkflowDef(
        id="WF-07",
        name="Sustentação de Lakehouse",
        trigger_description=(
            "sustentação, otimizar lakehouse, monitorar lakehouse, vacuum, "
            "observabilidade, custo lakehouse"
        ),
        steps=[
            WorkflowStep(
                agent_name="spark_expert",
                description=(
                    "Analisar performance: planos de execução, particionamento, "
                    "VACUUM/OPTIMIZE agendando e identificando tabelas degradadas"
                ),
                output_key="performance_analysis",
            ),
            WorkflowStep(
                agent_name="data_quality",
                description=(
                    "Verificar SLAs de qualidade, profiling de dados e "
                    "alertas de degradação usando a análise da etapa anterior"
                ),
                output_key="sla_report",
            ),
            WorkflowStep(
                agent_name="governance_auditor",
                description=(
                    "Revisar logs de acesso, anomalias de PII e drift de schema "
                    "para garantir conformidade contínua"
                ),
                output_key="compliance_review",
            ),
            WorkflowStep(
                agent_name="pipeline_architect",
                description=(
                    "Recomendar otimizações de custo e arquitetura (compactação, "
                    "tier de armazenamento, reparticionamento) com base nos "
                    "relatórios das etapas anteriores"
                ),
                output_key="optimization_recommendations",
            ),
        ],
    ),
}


def detect_workflow(task: str) -> WorkflowDef | None:
    """Detecta qual workflow pré-definido se aplica à tarefa, se algum."""
    for wf_id, pattern in WF_TRIGGER_PATTERNS.items():
        if pattern.search(task):
            return WORKFLOWS[wf_id]
    return None

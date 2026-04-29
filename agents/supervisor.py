"""Supervisor: coordena roteamento e delegação entre agentes especialistas."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

from agents.base import AgentResult, BaseAgent
from agents.loader import AGENT_COMMANDS, load_all
from hooks.output_compressor import compress
from workflow.dag import detect_workflow
from workflow.executor import execute_workflow

if TYPE_CHECKING:
    from orchestrator.models import TaskSpec

logger = logging.getLogger("data_agents.supervisor")

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "prd"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
KB_DIR = Path(__file__).parent.parent / "kb"
NAMING_CONVENTION_FILE = (
    Path(__file__).parent.parent / "resources" / "naming convention.md"
)

_COMPLEX_KEYWORDS = re.compile(
    r"\b(pipeline|bronze|silver|gold|migr|end.to.end|"
    r"criar|construir|implementar|star.schema|auditoria|"
    r"fabric|airflow|bundle|devops|scd|cluster|lakehouse|orchestration)\b",
    re.IGNORECASE,
)
_TABLE_CREATION_PATTERN = re.compile(
    # DDL real (CREATE TABLE), intent verb forte (crie/vou criar) ou
    # "criar tabela <nome_qualificado>" (ex: "criar tabela bronze.orders").
    # Não casa perguntas conceituais como "como criar uma tabela com SCD2?".
    r"\bcreate\s+(or\s+replace\s+)?table\b|"
    r"\b(crie|criarei|vou\s+criar)\s+(uma\s+|a\s+|nova\s+)?tabela\b|"
    r"\bcriar\s+tabela\s+[a-zA-Z_][\w]*\.[a-zA-Z_][\w]*",
    re.IGNORECASE,
)
_GOVERNANCE_PATTERN = re.compile(
    r"\b(alter\s+table|drop\s+table|rename\s+table|"
    r"audit(?:ar)?|nomenclatura|naming\s+conv(?:ention)?|"
    r"criar\s+schema|create\s+schema|data\s+governance|"
    r"padr[aã]o\s+de\s+nomenclatura)\b",
    re.IGNORECASE,
)

# Agentes válidos para PRD auto-delegação
_PRD_AGENTS = (
    "spark_expert|sql_expert|pipeline_architect|data_quality|"
    "naming_guard|dbt_expert|governance_auditor|python_expert|geral|"
    "fabric_expert|databricks_ai|devops_engineer|lakehouse_engineer"
)
_PRD_AGENT_RE = re.compile(
    r"\b(" + _PRD_AGENTS + r")\b",
    re.IGNORECASE,
)

# Padrões para post-routing de escalation
_ESCALATE_PATTERN = re.compile(r"ESCALATE_TO:\s*(\w+)", re.IGNORECASE)
_KB_MISS_PATTERN = re.compile(r"KB_MISS:\s*true", re.IGNORECASE)

# Criticidade por padrão de tarefa
# Padrão para injetar contexto do repo fabric-ci-cd
_FABRIC_CICD_PATTERN = re.compile(
    r"\b(fabric.*ci.?cd|cicd.*fabric|fabric.*git.*integr|fabric.*devops|"
    r"fabric.*azure.*devops|deploy.*fabric|git.*fabric|fabric.*pipeline.*deploy)"
    r"\b",
    re.IGNORECASE,
)

_CRITICALITY_PATTERNS: dict[str, re.Pattern[str]] = {
    "CRITICAL": re.compile(
        r"\b(drop\s+table|drop\s+database|drop\s+schema|drop\s+catalog|"
        r"delete\s+from|truncate\s+table|rm\s+-rf|"
        r"password|secret|token|credential)\b",
        re.IGNORECASE,
    ),
    "IMPORTANT": re.compile(
        r"\b(alter\s+table|schema\s+change|migrar|deploy|produção|"
        r"\bprod\b|grant|revoke|rotate\s+secret)\b",
        re.IGNORECASE,
    ),
    "STANDARD": re.compile(
        r"\b(pipeline|transform|silver|gold|criar|construir|implementar|"
        r"bronze|end.to.end|star.schema|dbt|incremental)\b",
        re.IGNORECASE,
    ),
}
_CONFIDENCE_THRESHOLDS: dict[str, float] = {
    "CRITICAL": 0.98,
    "IMPORTANT": 0.95,
    "STANDARD": 0.90,
    "ADVISORY": 0.80,
}


class Supervisor:
    def __init__(self) -> None:
        self._agents = load_all()
        self._supervisor_agent: BaseAgent = self._agents["supervisor"]
        self._memory_enabled = _try_init_memory()
        self._kg_enabled = _try_init_kg()
        self._session = _init_session()

    def route(self, user_input: str) -> AgentResult:
        """Roteia o input para o agente correto."""
        parts = user_input.strip().split(maxsplit=1)
        command = parts[0].lower() if parts[0].startswith("/") else None
        task = parts[1] if (command and len(parts) > 1) else user_input

        # 1. Comandos especiais (sem LLM)
        if command == "/health":
            return self._route_health()
        if command == "/resume":
            return self._route_resume(task)
        if command == "/sessions":
            return self._route_sessions()
        if command == "/kg":
            return self._route_kg(task)
        if command == "/assessment":
            return self._route_assessment(task)

        # 2. Party Mode
        if command == "/party":
            result = self._route_party(task)
            self._post_process(user_input, result, agent_name="party")
            return _compress_result(result)

        # 3. Governança automática — CREATE/ALTER/DROP TABLE e nomenclatura
        if _TABLE_CREATION_PATTERN.search(user_input) or (
            _GOVERNANCE_PATTERN.search(user_input) and not command
        ):
            result = self._route_governance(user_input)
            self._post_process(user_input, result, agent_name="naming_guard")
            return _compress_result(result)

        # 4. Comando explícito (/naming, /sql, /python, /dbt, etc.)
        if command and command in AGENT_COMMANDS:
            agent_name = AGENT_COMMANDS[command]
            # Comandos especiais já tratados acima; aqui só agentes reais
            if agent_name.startswith("_"):
                return AgentResult(
                    content=f"Comando `{command}` não implementado.",
                    tool_calls_count=0,
                    tokens_used=0,
                )
            agent = self._agents.get(agent_name, self._supervisor_agent)
            kb_ctx = self._load_kb_context(agent_name)
            mem_ctx = self._load_memory_context(task)
            # Injetar contexto externo se aplicável
            ext_ctx = self._load_external_context(agent_name, task)
            preflight = self._inject_preflight_context(agent_name, task, kb_ctx)
            context = "\n\n".join(filter(None, [preflight, kb_ctx, ext_ctx, mem_ctx]))
            result = agent.run(task, context=context)
            result = self._check_escalation(result, task)
            self._post_process(user_input, result, agent_name=agent_name)
            return _compress_result(result)

        # 5. Detecção automática de workflow
        workflow = detect_workflow(user_input)
        if workflow:
            logger.info("Workflow detectado: %s", workflow.id)
            result = execute_workflow(
                workflow, user_input, self._agents, self._supervisor_agent,
                fail_fast=True,
            )
            self._post_process(user_input, result, agent_name=f"workflow:{workflow.id}")
            return _compress_result(result)

        # 6. Tarefa complexa → PRD + delegação
        if _COMPLEX_KEYWORDS.search(user_input):
            result = self._plan_and_delegate(user_input)
            self._post_process(user_input, result, agent_name="prd_delegate")
            return _compress_result(result)

        # 7. Geral
        agent = self._agents.get("geral", self._supervisor_agent)
        result = agent.run(user_input)
        self._post_process(user_input, result, agent_name="geral")
        return _compress_result(result)

    # ── Handlers especiais ──────────────────────────────────────────────────

    def _route_health(self) -> AgentResult:
        from agents.health import run_health_check
        return run_health_check()

    def _route_resume(self, task: str) -> AgentResult:
        from utils.session import SessionManager
        context = SessionManager.load_last_session()
        if task.strip():
            agent = self._agents.get("geral", self._supervisor_agent)
            full_context = context + "\n\n---\n" + self._load_memory_context(task)
            return agent.run(task, context=full_context)
        return AgentResult(content=context, tool_calls_count=0, tokens_used=0)

    def _route_sessions(self) -> AgentResult:
        from utils.session import SessionManager
        return AgentResult(
            content=SessionManager.list_sessions(),
            tool_calls_count=0,
            tokens_used=0,
        )

    def _route_kg(self, task: str) -> AgentResult:
        """Subcomandos: lineage <table>, list, add <src> FEEDS_INTO <tgt>."""
        if not self._kg_enabled:
            return AgentResult(
                content="KG não disponível.",
                tool_calls_count=0,
                tokens_used=0,
            )
        from memory.kg import KnowledgeGraph
        kg = KnowledgeGraph()
        parts = task.strip().split()
        if not parts or parts[0] in ("list", "ls"):
            entities = kg.all_entities()
            if not entities:
                txt = "KG vazio — nenhuma entidade registrada."
            else:
                lines = ["| id | tipo | layer |", "|---|---|---|"]
                for e in entities[:50]:
                    layer = e.props.get("layer", "-")
                    lines.append(f"| `{e.id}` | {e.type} | {layer} |")
                txt = f"## Knowledge Graph — {len(entities)} entidade(s)\n\n"
                txt += "\n".join(lines)
            return AgentResult(
                content=txt, tool_calls_count=0, tokens_used=0
            )
        if parts[0] == "lineage" and len(parts) >= 2:
            return AgentResult(
                content=kg.format_lineage(parts[1]),
                tool_calls_count=0,
                tokens_used=0,
            )
        if parts[0] == "add" and len(parts) >= 4:
            # add <src> FEEDS_INTO <tgt>
            src = parts[1]
            rel = parts[2].upper()
            tgt = parts[3]
            kg.add_relation(src, tgt, rel)
            return AgentResult(
                content=f"✅ Relação adicionada: `{src}` --[{rel}]--> `{tgt}`",
                tool_calls_count=0,
                tokens_used=0,
            )
        return AgentResult(
            content=(
                "Uso: `/kg list` | `/kg lineage <tabela>` | "
                "`/kg add <src> FEEDS_INTO <tgt>`"
            ),
            tool_calls_count=0,
            tokens_used=0,
        )

    def _route_party(self, task: str) -> AgentResult:
        from agents.party import parse_party_command, run_party
        agent_names, query = parse_party_command(task)
        if not query:
            query = task
        kb_ctx = self._load_kb_for_task(query)
        return run_party(query, self._agents, agent_names, context=kb_ctx)

    def _route_assessment(self, task: str) -> AgentResult:
        """Executa fabricgov e passa os findings para governance_auditor interpretar."""
        from integrations.fabricgov import format_result, run_assessment

        # Parâmetros opcionais extraídos do task: /assessment --days 28 --lang en
        days = 7
        lang = "pt"
        command = "all"
        if "--days" in task:
            try:
                days = int(task.split("--days")[1].strip().split()[0])
            except (IndexError, ValueError):
                pass
        if "--lang" in task:
            lang = task.split("--lang")[1].strip().split()[0]
        if "--collect" in task:
            command = task.split("--collect")[1].strip().split()[0]

        assessment_result = run_assessment(command=command, days=days, lang=lang)
        raw_output = format_result(assessment_result)

        if assessment_result["status"] == "error":
            return AgentResult(content=raw_output, tool_calls_count=0, tokens_used=0)

        # Agente governance_auditor interpreta os findings
        gov_agent = self._agents.get("governance_auditor", self._supervisor_agent)
        kb_ctx = self._load_kb_context("governance_auditor")
        prompt = (
            "Com base nos findings de governança abaixo coletados pelo fabricgov, "
            "gere recomendações priorizadas (CRÍTICO / IMPORTANTE / INFORMATIVO) "
            "com ações concretas para cada finding.\n\n"
            f"Findings:\n{assessment_result.get('findings_stdout', '')}"
        )
        agent_result = gov_agent.run(prompt, context=kb_ctx)
        return AgentResult(
            content=(
                raw_output
                + "\n\n---\n\n## Análise do Governance Auditor\n\n"
                + agent_result.content
            ),
            tool_calls_count=agent_result.tool_calls_count,
            tokens_used=agent_result.tokens_used,
        )

    def _route_governance(self, user_input: str) -> AgentResult:
        naming_agent = self._agents.get("naming_guard", self._supervisor_agent)
        naming_ctx = self._load_naming_convention_context()
        kb_ctx = self._load_kb_context("naming_guard")
        context = "\n\n".join(filter(None, [kb_ctx, naming_ctx]))
        result = naming_agent.run(user_input, context=context)
        self._save_memory(user_input, result.content)
        return result

    def _plan_and_delegate(self, task: str) -> AgentResult:
        kb_ctx = self._load_kb_for_task(task)

        # Confidence assessment — sem MCP externo, baseado em KB hit
        criticality, threshold, confidence, decision = self._assess_confidence(
            task, kb_ctx
        )
        exec_header = (
            f"> **TASK:** {task[:80]}{'...' if len(task) > 80 else ''} "
            f"| **TYPE:** {criticality} "
            f"| **CONFIDENCE:** {confidence:.2f} "
            f"| **DECISION:** {decision}\n\n"
        )

        if decision == "REFUSE":
            return AgentResult(
                content=(
                    exec_header
                    + f"⛔ Operação recusada — confiança {confidence:.2f} abaixo do "
                    f"threshold {threshold:.2f} para operações **{criticality}**. "
                    "Solicite aprovação explícita do usuário antes de prosseguir."
                ),
                tool_calls_count=0,
                tokens_used=0,
            )

        mem_ctx = self._load_memory_context(task)
        prd_prompt = (
            "Crie um PRD conciso para a tarefa abaixo.\n"
            "Retorne APENAS JSON válido no formato:\n"
            '{"agent_name": "<agente>", "prd": "<conteúdo markdown do PRD>"}\n\n'
            f"Agentes válidos: {_PRD_AGENTS.replace('|', ', ')}\n\n"
            "O PRD deve incluir: Objetivo, Entradas esperadas, Saídas esperadas, "
            f"Agente responsável, Riscos.\n\nTarefa: {task}"
        )
        supervisor_context = "\n\n".join(filter(None, [kb_ctx, mem_ctx]))
        prd_result = self._supervisor_agent.run(
            prd_prompt, context=supervisor_context, json_mode=True
        )
        prd_raw = prd_result.content
        try:
            prd_data = json.loads(prd_raw)
            agent_name = str(prd_data.get("agent_name", "")).lower().strip()
            prd_content = str(prd_data.get("prd", prd_raw))
            if agent_name not in _PRD_AGENTS.split("|"):
                agent_name = ""
        except (json.JSONDecodeError, AttributeError):
            logger.warning("_plan_and_delegate: JSON inválido no PRD, fallback regex")
            prd_content = prd_raw
            agent_name = ""

        if not agent_name:
            agent_match = _PRD_AGENT_RE.search(prd_content)
            agent_name = agent_match.group(1).lower() if agent_match else "supervisor"

        prd_file = OUTPUT_DIR / f"prd_{hashlib.sha1(task.encode()).hexdigest()[:8]}.md"
        prd_file.write_text(prd_content)

        agent = self._agents.get(agent_name, self._supervisor_agent)
        preflight = self._inject_preflight_context(agent_name, task, kb_ctx)
        agent_kb_ctx = self._load_kb_context(agent_name)
        ext_ctx = self._load_external_context(agent_name, task)
        exec_context = "\n\n".join(
            filter(None, [preflight, agent_kb_ctx, ext_ctx, prd_content, mem_ctx])
        )
        execution_result = agent.run(task, context=exec_context)
        execution_result = self._check_escalation(execution_result, task)
        self._save_memory(task, execution_result.content)
        return AgentResult(
            content=(
                exec_header
                + f"**PRD gerado:** `{prd_file.name}`\n\n---\n\n"
                + execution_result.content
            ),
            tool_calls_count=(
                prd_result.tool_calls_count + execution_result.tool_calls_count
            ),
            tokens_used=prd_result.tokens_used + execution_result.tokens_used,
        )

    # ── Preflight & Escalation ───────────────────────────────────────────────

    def _inject_preflight_context(self, agent_name: str, task: str, kb_ctx: str) -> str:
        """Gera cabeçalho de preflight para injetar no context do agente."""
        criticality, threshold, confidence, decision = self._assess_confidence(
            task, kb_ctx
        )
        kb_hit = len(kb_ctx.strip()) > 200
        return (
            f"## Supervisor Pre-flight\n"
            f"AGENT: {agent_name} | TYPE: {criticality} | "
            f"CONFIDENCE: {confidence:.2f} | KB_HIT: {kb_hit} | THRESHOLD: {threshold}\n"
            f"STATUS: {decision} — preencha o Execution Template na sua resposta.\n"
        )

    def _check_escalation(self, result: AgentResult, original_task: str) -> AgentResult:
        """Post-routing: detecta KB_MISS e ESCALATE_TO no response do agente."""
        if _KB_MISS_PATTERN.search(result.content):
            note = (
                "\n\n> **KB_MISS detectado** — O KB local não cobre completamente esta "
                "demanda. Considere buscar referência externa ou expandir o KB com "
                "novos padrões para este domínio."
            )
            return AgentResult(
                content=result.content + note,
                tool_calls_count=result.tool_calls_count,
                tokens_used=result.tokens_used,
            )
        match = _ESCALATE_PATTERN.search(result.content)
        if match:
            escalate_to = match.group(1).lower()
            fallback_agent = self._agents.get(escalate_to)
            if fallback_agent:
                logger.info("Escalando para agente: %s", escalate_to)
                kb_ctx = self._load_kb_context(escalate_to)
                preflight = self._inject_preflight_context(escalate_to, original_task, kb_ctx)
                context = "\n\n".join(filter(None, [preflight, kb_ctx]))
                return fallback_agent.run(original_task, context=context)
        return result

    # ── Confidence ──────────────────────────────────────────────────────────

    def _assess_confidence(
        self, task: str, kb_ctx: str
    ) -> tuple[str, float, float, str]:
        """Retorna (criticality, threshold, confidence, decision).

        Baseado em Agreement Matrix sem MCP externo:
          - KB hit + conteúdo carregado     → confidence 0.75
          - KB sem conteúdo relevante        → confidence 0.50
          - Criticality ADVISORY             → bump para 0.85
        """
        kb_hit = len(kb_ctx.strip()) > 200

        criticality = "ADVISORY"
        for level in ("CRITICAL", "IMPORTANT", "STANDARD"):
            if _CRITICALITY_PATTERNS[level].search(task):
                criticality = level
                break

        threshold = _CONFIDENCE_THRESHOLDS[criticality]

        if criticality == "ADVISORY":
            confidence = 0.85
        elif kb_hit:
            _kb_confidence = {"CRITICAL": 0.85, "IMPORTANT": 0.82, "STANDARD": 0.78}
            confidence = _kb_confidence.get(criticality, 0.78)
        else:
            confidence = 0.50

        if confidence >= threshold:
            decision = "PROCEED"
        elif criticality == "CRITICAL":
            decision = "REFUSE"
        else:
            decision = "PROCEED"

        return criticality, threshold, confidence, decision

    # ── KB ──────────────────────────────────────────────────────────────────

    def _load_kb_context(self, agent_name: str) -> str:
        agent = self._agents.get(agent_name)
        domains = list(agent.config.kb_domains) if agent else []
        return self._load_kb_domains(domains)

    def _load_kb_for_task(self, task: str) -> str:
        """Mapeia keywords -> domínios de KB usando regex com word boundary.

        Word boundary evita falsos positivos: "model" não casa em "data model"
        ou "modelagem"; "workflow" não casa em "workflows" genéricos sem
        contexto de orquestração.
        """
        domains: list[str] = []
        rules: list[tuple[str, list[str]]] = [
            (r"\b(sql|query|select|schema)\b", ["sql-patterns"]),
            (r"\b(spark|pyspark|delta|streaming)\b", ["spark-patterns"]),
            (r"\b(repartition|coalesce|catalyst|shuffle|narrow|wide)\b",
             ["spark-internals"]),
            (r"\b(pipeline|bronze|silver|gold|etl|elt)\b", ["pipeline-design"]),
            (r"\b(qualidade|valida[cç][aã]o|expectation|dqx)\b", ["data-quality"]),
            (r"\b(governan[cç]a|naming|pii|lgpd|gdpr)\b", ["governance"]),
            (r"\b(dbt|dbt-core|dbt-cloud)\b", ["pipeline-design"]),
            (r"\b(fabric|lakehouse|onelake|direct\s+lake|eventstream)\b", ["fabric"]),
            (r"\b(implantar|sustent\w*|vacuum|optimize|small\s+files|"
             r"incidente|cutover|runbook)\b", ["lakehouse-design", "lakehouse-ops"]),
            (r"\b(cluster|unity\s+catalog|dbr|runtime|databricks\s+platform)\b",
             ["databricks-platform"]),
            (r"\b(bundle|dab|ci/cd|cicd|devops|azure\s+devops|git)\b", ["ci-cd"]),
            (r"\b(scd|star\s+schema|dimension|modelagem|acid)\b", ["data-modeling"]),
            (r"\b(airflow|orquestr\w*|orchestrat\w*|\bdag\b)\b", ["orchestration"]),
            (r"\b(agent\s+bricks|genie|mosaic|mlflow|model\s+serving)\b",
             ["databricks-ai"]),
        ]
        for pattern, doms in rules:
            if re.search(pattern, task, re.IGNORECASE):
                domains.extend(doms)
        if not domains:
            domains.append("shared")
        # dedup preservando ordem
        seen: set[str] = set()
        unique = [d for d in domains if not (d in seen or seen.add(d))]
        return self._load_kb_domains(unique)

    def _load_kb_domains(self, domains: list[str]) -> str:
        parts: list[str] = []
        constitution = KB_DIR / "constitution.md"
        if constitution.exists():
            parts.append(
                "## Constituição (regras invioláveis)\n"
                + constitution.read_text(encoding="utf-8")
            )
        _SKIP_ROOT = {"index.md", "quick-reference.md"}
        for domain in domains:
            domain_dir = KB_DIR / domain
            domain_parts: list[str] = []
            index_path = domain_dir / "index.md"
            if index_path.exists():
                domain_parts.append(index_path.read_text(encoding="utf-8"))
            qr_path = domain_dir / "quick-reference.md"
            if qr_path.exists():
                domain_parts.append(qr_path.read_text(encoding="utf-8"))
            # Arquivos de conteúdo no root do domínio (ex: delta-lake.md)
            for rf in sorted(domain_dir.glob("*.md")):
                if rf.name in _SKIP_ROOT:
                    continue
                raw = rf.read_text(encoding="utf-8")
                domain_parts.append(raw[:4000] if len(raw) > 4000 else raw)
            # Arquivos em patterns/ — até 5, ordenados por última modificação
            patterns_dir = domain_dir / "patterns"
            if patterns_dir.is_dir():
                pattern_files = sorted(
                    patterns_dir.glob("*.md"),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )[:5]
                for pf in pattern_files:
                    raw = pf.read_text(encoding="utf-8")
                    domain_parts.append(raw[:3000] if len(raw) > 3000 else raw)
            if domain_parts:
                parts.append(
                    "## KB: " + domain + "\n"
                    + "\n\n".join(domain_parts)
                )
        return "\n\n".join(parts)

    def _load_naming_convention_context(self) -> str:
        if not NAMING_CONVENTION_FILE.exists():
            return ""
        content = NAMING_CONVENTION_FILE.read_text(encoding="utf-8").strip()
        if not content:
            return ""
        return "Use estritamente as convenções abaixo:\n\n" + content

    def _load_external_context(self, agent_name: str, task: str) -> str:
        """Injeta contexto de repos externos conforme agente e tarefa.

        Atualmente:
          - devops_engineer + task com CI/CD Fabric → scripts do alisonpezzott/fabric-ci-cd
        """
        if agent_name in ("devops_engineer", "fabric_expert") and _FABRIC_CICD_PATTERN.search(task):
            try:
                from integrations.github_context import fetch_fabric_cicd_context
                return fetch_fabric_cicd_context()
            except Exception as exc:
                logger.debug("fabric-ci-cd context fetch falhou: %s", exc)
        return ""

    # ── Memória ─────────────────────────────────────────────────────────────

    def _load_memory_context(self, task: str) -> str:
        if not self._memory_enabled:
            return ""
        try:
            from memory.retrieval import (
                format_memories_for_injection,
                retrieve_relevant_memories,
            )
            from memory.store import MemoryStore

            store = MemoryStore()
            memories = retrieve_relevant_memories(task, store)
            return format_memories_for_injection(memories)
        except Exception:
            return ""

    def _save_memory(self, task: str, result_content: str) -> None:
        if not self._memory_enabled:
            return
        try:
            from memory.extractor import extract_and_save
            from memory.store import MemoryStore

            extract_and_save(task, result_content, MemoryStore())
        except Exception:
            pass
        if self._kg_enabled:
            try:
                from memory.kg import KnowledgeGraph, extract_lineage_from_text
                extract_lineage_from_text(result_content, KnowledgeGraph())
            except Exception:
                pass

    # ── Post-process (session + memory) ─────────────────────────────────────

    def _post_process(
        self, user_input: str, result: AgentResult, agent_name: str = "supervisor"
    ) -> None:
        # QW6: verificar output por padrões destrutivos
        from hooks import audit_hook, security_hook

        ok, reason = security_hook.check_output(result.content)
        if not ok:
            logger.warning(
                "security_hook bloqueou output do agente %s: %s", agent_name, reason
            )
            result.content = (
                f"⚠️ **Output bloqueado pelo security_hook:** {reason}\n\n"
                "O agente gerou conteúdo com padrão potencialmente destrutivo. "
                "Revise a tarefa e execute com /governance se necessário."
            )
        # QW7: registrar agente real na auditoria
        audit_hook.record(
            agent=agent_name,
            task=user_input,
            tokens_used=result.tokens_used,
            tool_calls=result.tool_calls_count,
        )
        if self._session is not None:
            try:
                self._session.record(user_input, result.content)
            except Exception:
                pass
        self._save_memory(user_input, result.content)

    # ── QA Protocol ──────────────────────────────────────────────────────────

    def draft_spec(self, task: str) -> tuple[TaskSpec, int, int]:
        from orchestrator.models import TaskSpec, parse_json_from_llm

        valid_agents = (
            "spark_expert", "sql_expert", "pipeline_architect", "data_quality",
            "naming_guard", "dbt_expert", "governance_auditor", "python_expert",
            "geral", "fabric_expert", "databricks_ai", "devops_engineer",
            "lakehouse_engineer",
        )
        prompt = (
            "Crie uma TaskSpec estruturada para a tarefa abaixo. "
            "Retorne APENAS JSON válido, sem texto adicional.\n\n"
            f"Tarefa: {task}\n\n"
            "Formato:\n"
            '{"objective": "descrição clara", '
            '"deliverables": ["item 1", "item 2"], '
            '"acceptance_criteria": ["critério mensurável 1"], '
            f'"agent_name": "um de: {", ".join(valid_agents)}", '
            '"risks": ["risco 1"]}'
        )
        result = self._supervisor_agent.run(prompt, json_mode=True)
        data = parse_json_from_llm(result.content)
        agent_name = data.get("agent_name", "geral")
        if agent_name not in valid_agents:
            agent_name = "geral"
        spec = TaskSpec(
            task_id=TaskSpec.new_id(),
            objective=data.get("objective", task[:100]),
            deliverables=data.get("deliverables", ["Resposta ao usuário"]),
            acceptance_criteria=data.get(
                "acceptance_criteria", ["Tarefa respondida"]
            ),
            agent_name=agent_name,
            risks=data.get("risks", []),
        )
        return spec, result.tokens_used, result.tool_calls_count

    def revise_spec(
        self, spec: TaskSpec, feedback: str, proposed_additions: list[str]
    ) -> tuple[TaskSpec, int, int]:
        from orchestrator.models import TaskSpec, parse_json_from_llm

        additions_str = "\n".join(f"- {a}" for a in proposed_additions)
        prompt = (
            "Revise a TaskSpec incorporando o feedback. "
            "Retorne APENAS JSON válido, sem texto adicional.\n\n"
            f"## Spec Atual (v{spec.version})\n{spec.to_json_str()}\n\n"
            f"## Feedback\n{feedback}\n\n"
            f"## Adições propostas\n{additions_str or '(nenhuma)'}\n\n"
            "Mantenha o mesmo schema. Incremente version em 1."
        )
        result = self._supervisor_agent.run(prompt, json_mode=True)
        data = parse_json_from_llm(result.content)
        new_spec = TaskSpec(
            task_id=spec.task_id,
            objective=data.get("objective", spec.objective),
            deliverables=data.get("deliverables", spec.deliverables),
            acceptance_criteria=data.get(
                "acceptance_criteria", spec.acceptance_criteria
            ),
            agent_name=data.get("agent_name", spec.agent_name),
            risks=data.get("risks", spec.risks),
            version=spec.version + 1,
        )
        return new_spec, result.tokens_used, result.tool_calls_count

    def list_agents(self) -> list[str]:
        return list(self._agents.keys())

    def get_agent(self, name: str) -> BaseAgent | None:
        """Acesso público ao agente por nome."""
        return self._agents.get(name)


# ── Helpers de módulo ────────────────────────────────────────────────────────

def _compress_result(result: AgentResult) -> AgentResult:
    compressed = compress(result.content)
    if compressed is result.content:
        return result
    return AgentResult(
        content=compressed,
        tool_calls_count=result.tool_calls_count,
        tokens_used=result.tokens_used,
    )


def _try_init_memory() -> bool:
    try:
        from memory.store import MemoryStore  # noqa: F401
        return True
    except ImportError:
        return False


def _try_init_kg() -> bool:
    try:
        from memory.kg import KnowledgeGraph  # noqa: F401
        return True
    except ImportError:
        return False


def _init_session():
    try:
        from utils.session import SessionManager
        return SessionManager()
    except Exception:
        return None

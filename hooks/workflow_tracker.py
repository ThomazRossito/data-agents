"""
Hook de rastreamento de Workflows e Clarity Checkpoint.

Registra eventos de workflow (WF-01 a WF-04), execuções do Clarity Checkpoint
e delegações de agentes em logs/workflows.jsonl para análise no dashboard.

Integra-se com o audit_hook existente via PostToolUse — intercepta chamadas
ao tool "Agent" para rastrear delegações e encadeamentos.

Eventos rastreados:
  - agent_delegation: Cada delegação do supervisor para um sub-agente
  - workflow_step: Etapas de workflows WF-01 a WF-04
  - clarity_checkpoint: Execuções do Clarity Checkpoint (score e resultado)
  - spec_generated: Quando um spec-first é gerado

Log format: JSONL em logs/workflows.jsonl (uma linha por evento).
"""

import json
import logging
import os
import re
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.settings import settings

logger = logging.getLogger("data_agents.workflow_tracker")

# ─── Callback system ────────────────────────────────────────────────────────
# CLI e UI podem registrar callbacks para receber eventos de progresso em tempo
# real. Callbacks são chamados de forma síncrona, devem ser rápidos (sem I/O).

_progress_callbacks: list[Callable[[str, dict[str, Any]], None]] = []

# Rastreia tempo de início por tool_use_id para calcular duração
_tool_start_times: dict[str, float] = {}


def register_progress_callback(callback: Callable[[str, dict[str, Any]], None]) -> None:
    """
    Registra um callback para receber eventos de progresso em tempo real.

    O callback recebe (event_name: str, data: dict) onde event_name é um de:
      - "agent_start"  — data: {"agent": str, "tool_use_id": str}
      - "tool_call"    — data: {"tool": str, "args_preview": str, "tool_use_id": str}
      - "agent_done"   — data: {"agent": str, "duration": float, "tool_use_id": str}

    Útil para o CLI (Rich spinner) e UI (st.status) mostrarem progresso em tempo real.
    Os callbacks são chamados de forma síncrona — devem ser rápidos.
    """
    if callback not in _progress_callbacks:
        _progress_callbacks.append(callback)


def unregister_progress_callback(callback: Callable[[str, dict[str, Any]], None]) -> None:
    """Remove um callback previamente registrado."""
    try:
        _progress_callbacks.remove(callback)
    except ValueError:
        pass


def clear_progress_callbacks() -> None:
    """Remove todos os callbacks registrados."""
    _progress_callbacks.clear()


def _emit_progress(event_name: str, data: dict[str, Any]) -> None:
    """Emite um evento de progresso para todos os callbacks registrados."""
    for cb in _progress_callbacks:
        try:
            cb(event_name, data)
        except Exception as exc:
            logger.debug(f"Callback de progresso falhou (ignorado): {exc}")


# Caminho do log de workflows (mesmo diretório dos outros logs)
WORKFLOWS_LOG_PATH: Path = Path(settings.audit_log_path).parent / "workflows.jsonl"

# ─── Padrões de detecção ────────────────────────────────────────────────

# Detecta referências a workflows no prompt de delegação
WORKFLOW_PATTERN = re.compile(r"WF-0([1-4])", re.IGNORECASE)

# Detecta nomes de agentes conhecidos
KNOWN_AGENTS = {
    "sql-expert",
    "spark-expert",
    "pipeline-architect",
    "data-quality-steward",
    "governance-auditor",
    "semantic-modeler",
    "business-analyst",
}

# Detecta referências ao Clarity Checkpoint
CLARITY_PATTERN = re.compile(
    r"(?:clarity|clareza|checkpoint).*?(\d)\s*/\s*5",
    re.IGNORECASE,
)

# Detecta geração de specs
SPEC_PATTERN = re.compile(
    r"(?:spec|especificação).*?(pipeline|star.?schema|cross.?platform)",
    re.IGNORECASE,
)


def _write_event(event: dict[str, Any]) -> None:
    """Grava um evento no workflows.jsonl com fallback silencioso."""
    try:
        log_line = json.dumps(event, ensure_ascii=False) + "\n"
        os.makedirs(os.path.dirname(str(WORKFLOWS_LOG_PATH)), exist_ok=True)
        with open(WORKFLOWS_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(log_line)
    except OSError as e:
        logger.warning(f"Falha ao gravar workflow event: {e}")


def _extract_agent_name(tool_input: dict[str, Any]) -> str:
    """Extrai o nome do agente do input do tool Agent."""
    # O Claude Agent SDK usa subagent_type como campo principal (ex: "sql-expert")
    return (
        tool_input.get("subagent_type")
        or tool_input.get("agent_name")
        or tool_input.get("name")
        or tool_input.get("agent")
        or "unknown"
    )


def _extract_prompt_preview(tool_input: dict[str, Any]) -> str:
    """Extrai preview do prompt de delegação (máximo 200 chars)."""
    # Prioriza o prompt completo; description é mais curto mas sempre presente
    prompt = tool_input.get("prompt", "") or tool_input.get("description", "") or ""
    return prompt[:200]


def _normalize_agent_name(raw: str) -> str:
    """Normaliza o nome do agente para exibição no dashboard."""
    # Mapeia nomes internos para nomes legíveis
    _DISPLAY_NAMES = {
        "sql-expert": "SQL Expert",
        "spark-expert": "Spark Expert",
        "pipeline-architect": "Pipeline Architect",
        "data-quality-steward": "Data Quality Steward",
        "governance-auditor": "Governance Auditor",
        "semantic-modeler": "Semantic Modeler",
        "business-analyst": "Business Analyst",
    }
    return _DISPLAY_NAMES.get(raw, raw)


async def pre_track_workflow_events(
    input_data: dict[str, Any],
    tool_use_id: str | None,
    context: Any,
) -> dict[str, Any]:
    """
    PreToolUse hook — emite eventos de progresso ANTES da tool executar.

    Emite "agent_start" quando o Supervisor delega para um sub-agente,
    e "tool_call" para qualquer tool MCP relevante. Registra o tempo de
    início para que o PostToolUse possa calcular a duração.
    """
    if not input_data or not isinstance(input_data, dict):
        return {}

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    if not tool_name:
        return {}

    # Registra tempo de início para calcular duração no PostToolUse
    tid = tool_use_id or tool_name
    _tool_start_times[tid] = time.monotonic()

    # Emite evento de delegação de agente
    if tool_name == "Agent":
        agent_name = _extract_agent_name(tool_input)
        _emit_progress(
            "agent_start",
            {"agent": agent_name, "tool_use_id": tid},
        )

    # Emite evento de tool call para qualquer ferramenta
    elif tool_name:
        # Preview dos args (sem segredos — apenas campos não-sensíveis)
        safe_keys = {
            "query",
            "command",
            "statement",
            "path",
            "file_path",
            "catalog",
            "schema",
            "table",
            "database",
        }
        args_preview = ", ".join(
            f"{k}={str(v)[:40]}" for k, v in (tool_input or {}).items() if k in safe_keys and v
        )
        _emit_progress(
            "tool_call",
            {"tool": tool_name, "args_preview": args_preview, "tool_use_id": tid},
        )

    return {}


async def track_workflow_events(
    input_data: dict[str, Any],
    tool_use_id: str | None,
    context: Any,
) -> dict[str, Any]:
    """
    PostToolUse hook que rastreia delegações de agentes e eventos de workflow.

    Intercepta chamadas ao tool "Agent" e analisa o prompt de delegação
    para detectar workflows, Clarity Checkpoint e specs.
    Também intercepta "Write" para detectar specs salvos em output/specs/.
    Emite "agent_done" para delegações concluídas.
    """
    if not input_data or not isinstance(input_data, dict):
        return {}

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    if not tool_name:
        return {}

    timestamp = datetime.now(timezone.utc).isoformat()

    # ── Emitir agent_done com duração calculada ──
    if tool_name == "Agent":
        tid = tool_use_id or tool_name
        start = _tool_start_times.pop(tid, None)
        duration = (time.monotonic() - start) if start is not None else 0.0
        raw_agent_name = _extract_agent_name(tool_input)
        _emit_progress(
            "agent_done",
            {"agent": raw_agent_name, "duration": duration, "tool_use_id": tid},
        )
    else:
        # Limpa entradas de outras tools para não acumular memória indefinidamente
        _tool_start_times.pop(tool_use_id or tool_name, None)

    # ── Rastrear delegações de agentes ──
    if tool_name == "Agent":
        agent_name = _normalize_agent_name(_extract_agent_name(tool_input))
        prompt_preview = _extract_prompt_preview(tool_input)

        # Evento base: delegação
        event: dict[str, Any] = {
            "timestamp": timestamp,
            "event": "agent_delegation",
            "agent": agent_name,
            "tool_use_id": tool_use_id,
            "prompt_preview": prompt_preview,
        }

        # Detectar workflow no prompt
        wf_match = WORKFLOW_PATTERN.search(prompt_preview)
        if wf_match:
            wf_number = int(wf_match.group(1))
            event["event"] = "workflow_step"
            event["workflow"] = f"WF-0{wf_number}"

            # Tentar extrair etapa do workflow
            step_match = re.search(r"[Ee]tapa\s*:?\s*(\d+)", prompt_preview)
            if step_match:
                event["step"] = int(step_match.group(1))

        # Detectar Clarity Checkpoint no prompt
        clarity_match = CLARITY_PATTERN.search(prompt_preview)
        if clarity_match:
            score = int(clarity_match.group(1))
            clarity_event: dict[str, Any] = {
                "timestamp": timestamp,
                "event": "clarity_checkpoint",
                "score": score,
                "max_score": 5,
                "passed": score >= 3,
                "tool_use_id": tool_use_id,
                "prompt_preview": prompt_preview,
            }
            _write_event(clarity_event)

        _write_event(event)

    # ── Rastrear geração de specs ──
    elif tool_name == "Write":
        file_path = tool_input.get("file_path", "") or ""
        if "output/specs/" in file_path or "spec" in file_path.lower():
            spec_type = "unknown"
            spec_match = SPEC_PATTERN.search(file_path)
            if spec_match:
                spec_type = spec_match.group(1).lower().replace(" ", "-")
            elif "pipeline" in file_path.lower():
                spec_type = "pipeline"
            elif "star" in file_path.lower() or "schema" in file_path.lower():
                spec_type = "star-schema"
            elif "cross" in file_path.lower():
                spec_type = "cross-platform"

            spec_event: dict[str, Any] = {
                "timestamp": timestamp,
                "event": "spec_generated",
                "spec_type": spec_type,
                "file_path": file_path,
                "tool_use_id": tool_use_id,
            }
            _write_event(spec_event)

    # ── Rastrear uso de AskUserQuestion (possível Clarity Checkpoint) ──
    elif tool_name == "AskUserQuestion":
        question = tool_input.get("question", "") or ""
        # Detectar se é um esclarecimento do Clarity Checkpoint
        if any(
            kw in question.lower()
            for kw in ["clareza", "clarity", "esclarecer", "qual plataforma", "qual ambiente"]
        ):
            clarification_event: dict[str, Any] = {
                "timestamp": timestamp,
                "event": "clarity_clarification_requested",
                "question_preview": question[:200],
                "tool_use_id": tool_use_id,
            }
            _write_event(clarification_event)

    return {}


# ─── Funções de leitura para o dashboard ────────────────────────────────


def load_workflow_history() -> list[dict]:
    """Lê todos os eventos de workflows.jsonl."""
    events: list[dict] = []
    if not WORKFLOWS_LOG_PATH.exists():
        return events
    try:
        with open(WORKFLOWS_LOG_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except OSError:
        pass
    return events


def get_workflow_summary() -> dict[str, Any]:
    """
    Calcula resumo agregado de workflows e delegações.

    Returns:
        Dict com métricas de workflows, delegações por agente,
        Clarity Checkpoint e specs gerados.
    """
    events = load_workflow_history()

    summary: dict[str, Any] = {
        "total_events": len(events),
        "total_delegations": 0,
        "delegations_by_agent": {},
        "workflows_triggered": {},
        "workflow_steps": [],
        "clarity_checks": [],
        "clarity_pass_rate": 0.0,
        "specs_generated": [],
        "clarifications_requested": 0,
        "events_by_date": {},
    }

    agent_counts: dict[str, int] = {}
    wf_counts: dict[str, int] = {}
    clarity_checks: list[dict] = []
    date_counts: dict[str, int] = {}

    for event in events:
        event_type = event.get("event", "")
        date_key = event.get("timestamp", "")[:10]
        date_counts[date_key] = date_counts.get(date_key, 0) + 1

        if event_type == "agent_delegation":
            summary["total_delegations"] += 1
            agent = event.get("agent", "unknown")
            agent_counts[agent] = agent_counts.get(agent, 0) + 1

        elif event_type == "workflow_step":
            summary["total_delegations"] += 1
            agent = event.get("agent", "unknown")
            agent_counts[agent] = agent_counts.get(agent, 0) + 1
            wf = event.get("workflow", "unknown")
            wf_counts[wf] = wf_counts.get(wf, 0) + 1
            summary["workflow_steps"].append(event)

        elif event_type == "clarity_checkpoint":
            clarity_checks.append(event)

        elif event_type == "spec_generated":
            summary["specs_generated"].append(event)

        elif event_type == "clarity_clarification_requested":
            summary["clarifications_requested"] += 1

    summary["delegations_by_agent"] = dict(sorted(agent_counts.items(), key=lambda x: -x[1]))
    summary["workflows_triggered"] = dict(sorted(wf_counts.items(), key=lambda x: -x[1]))
    summary["clarity_checks"] = clarity_checks
    summary["events_by_date"] = dict(sorted(date_counts.items()))

    if clarity_checks:
        passed = sum(1 for c in clarity_checks if c.get("passed", False))
        summary["clarity_pass_rate"] = round(passed / len(clarity_checks) * 100, 1)

    return summary

"""
workflow.tracker — Hooks PreToolUse / PostToolUse para rastreamento de workflows.

Grava eventos em `logs/workflows.jsonl` e emite callbacks de progresso síncrono
para a UI (CLI / Chainlit / Streamlit).

Eventos persistidos:
  - `agent_delegation` — cada delegação do Supervisor para um sub-agente
  - `workflow_step`    — etapas de workflows WF-01..WF-05
  - `clarity_checkpoint` — execuções do Clarity Checkpoint (score e resultado)
  - `spec_generated`   — quando um spec-first é gerado
  - `prd_modified`     — PRD modificado; dispara `spec_needs_review` nas specs relacionadas
  - `clarity_clarification_requested` — AskUserQuestion relacionado a Clarity

Callbacks de progresso (síncronos, não fazem I/O):
  - `agent_start` / `tool_call` (PreToolUse)
  - `agent_done` (PostToolUse, com duração calculada)
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

from workflow.dag import (
    CLARITY_PATTERN,
    PRD_PATTERN,
    SPEC_PATTERN,
    WORKFLOW_PATTERN,
    display_name_for,
)
from workflow.executor import WORKFLOWS_LOG_PATH

logger = logging.getLogger("data_agents.workflow.tracker")

# ─── Callback system ────────────────────────────────────────────────────────

_progress_callbacks: list[Callable[[str, dict[str, Any]], None]] = []

# Rastreia tempo de início por tool_use_id para calcular duração no PostToolUse
_tool_start_times: dict[str, float] = {}


def register_progress_callback(callback: Callable[[str, dict[str, Any]], None]) -> None:
    """
    Registra um callback para receber eventos de progresso em tempo real.

    O callback recebe `(event_name: str, data: dict)` onde `event_name` é um de:
      - `agent_start`  — `data: {"agent": str, "tool_use_id": str}`
      - `tool_call`    — `data: {"tool": str, "args_preview": str, "tool_use_id": str}`
      - `agent_done`   — `data: {"agent": str, "duration": float, "tool_use_id": str}`

    Útil para o CLI (Rich spinner) e UI (st.status). Chamadas são síncronas —
    callbacks devem ser rápidos e não fazer I/O bloqueante.
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
    for cb in _progress_callbacks:
        try:
            cb(event_name, data)
        except Exception as exc:
            logger.debug(f"Callback de progresso falhou (ignorado): {exc}")


# ─── Helpers ────────────────────────────────────────────────────────────────


def _find_related_specs(prd_path: str) -> list[str]:
    """Lista specs irmãs de um PRD — `output/<feat>/prd/*.md` → `output/<feat>/specs/*.md`."""
    prd_p = Path(prd_path)
    specs_dir = prd_p.parent.parent / "specs"
    if specs_dir.exists():
        return [str(p) for p in sorted(specs_dir.rglob("*.md"))]
    return []


def _write_event(event: dict[str, Any]) -> None:
    """Persiste um evento em `logs/workflows.jsonl` com fallback silencioso."""
    try:
        log_line = json.dumps(event, ensure_ascii=False) + "\n"
        os.makedirs(os.path.dirname(str(WORKFLOWS_LOG_PATH)), exist_ok=True)
        with open(WORKFLOWS_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(log_line)
    except OSError as e:
        logger.warning(f"Falha ao gravar workflow event: {e}")


def _extract_agent_name(tool_input: dict[str, Any]) -> str:
    """Extrai o nome do agente do input do tool Agent."""
    return (
        tool_input.get("subagent_type")
        or tool_input.get("agent_name")
        or tool_input.get("name")
        or tool_input.get("agent")
        or "unknown"
    )


def _extract_prompt_preview(tool_input: dict[str, Any]) -> str:
    """Preview do prompt de delegação (máximo 200 chars)."""
    prompt = tool_input.get("prompt", "") or tool_input.get("description", "") or ""
    return prompt[:200]


# ─── Hooks ──────────────────────────────────────────────────────────────────


async def pre_track_workflow_events(
    input_data: dict[str, Any],
    tool_use_id: str | None,
    context: Any,
) -> dict[str, Any]:
    """
    PreToolUse hook — emite `agent_start`/`tool_call` antes da execução e
    marca o tempo de início para cálculo de duração.
    """
    if not input_data or not isinstance(input_data, dict):
        return {}

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    if not tool_name:
        return {}

    tid = tool_use_id or tool_name
    _tool_start_times[tid] = time.monotonic()

    if tool_name == "Agent":
        agent_name = _extract_agent_name(tool_input)
        _emit_progress("agent_start", {"agent": agent_name, "tool_use_id": tid})
    else:
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
    PostToolUse hook — rastreia delegações, detecta workflows/Clarity/specs,
    emite `agent_done` com duração, persiste eventos estruturados no JSONL.
    """
    if not input_data or not isinstance(input_data, dict):
        return {}

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    if not tool_name:
        return {}

    timestamp = datetime.now(timezone.utc).isoformat()

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
        _tool_start_times.pop(tool_use_id or tool_name, None)

    if tool_name == "Agent":
        agent_name = display_name_for(_extract_agent_name(tool_input))
        prompt_preview = _extract_prompt_preview(tool_input)

        event: dict[str, Any] = {
            "timestamp": timestamp,
            "event": "agent_delegation",
            "agent": agent_name,
            "tool_use_id": tool_use_id,
            "prompt_preview": prompt_preview,
        }

        wf_match = WORKFLOW_PATTERN.search(prompt_preview)
        if wf_match:
            wf_number = int(wf_match.group(1))
            event["event"] = "workflow_step"
            event["workflow"] = f"WF-0{wf_number}"
            step_match = re.search(r"[Ee]tapa\s*:?\s*(\d+)", prompt_preview)
            if step_match:
                event["step"] = int(step_match.group(1))

        clarity_match = CLARITY_PATTERN.search(prompt_preview)
        if clarity_match:
            score = int(clarity_match.group(1))
            _write_event(
                {
                    "timestamp": timestamp,
                    "event": "clarity_checkpoint",
                    "score": score,
                    "max_score": 5,
                    "passed": score >= 3,
                    "tool_use_id": tool_use_id,
                    "prompt_preview": prompt_preview,
                }
            )

        _write_event(event)

    elif tool_name in ("Write", "Edit"):
        file_path = tool_input.get("file_path", "") or ""

        if file_path and ("output/specs/" in file_path or "spec" in file_path.lower()):
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

            _write_event(
                {
                    "timestamp": timestamp,
                    "event": "spec_generated",
                    "spec_type": spec_type,
                    "file_path": file_path,
                    "tool_use_id": tool_use_id,
                }
            )

        if file_path and PRD_PATTERN.search(file_path):
            related_specs = _find_related_specs(file_path)
            _write_event(
                {
                    "timestamp": timestamp,
                    "event": "prd_modified",
                    "prd_path": file_path,
                    "cascade_status": "specs_need_review",
                    "related_specs": related_specs,
                    "tool_use_id": tool_use_id,
                }
            )
            for spec_path in related_specs:
                _write_event(
                    {
                        "timestamp": timestamp,
                        "event": "spec_needs_review",
                        "spec_path": spec_path,
                        "triggered_by_prd": file_path,
                        "tool_use_id": tool_use_id,
                    }
                )

    elif tool_name == "AskUserQuestion":
        question = tool_input.get("question", "") or ""
        if any(
            kw in question.lower()
            for kw in ["clareza", "clarity", "esclarecer", "qual plataforma", "qual ambiente"]
        ):
            _write_event(
                {
                    "timestamp": timestamp,
                    "event": "clarity_clarification_requested",
                    "question_preview": question[:200],
                    "tool_use_id": tool_use_id,
                }
            )

    return {}

"""cli.runner — Carrega e executa arquivos de tarefa YAML ou Markdown."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from agents.base import AgentResult

TASKS_DIR = Path(__file__).parent.parent / "tasks"

_SUPPORTED_EXTS = {".yaml", ".yml", ".md"}


def load_task_file(path: Path) -> dict:
    """Parse de arquivo de tarefa.

    Formatos suportados:
    - YAML puro (.yaml / .yml)
    - Markdown com frontmatter YAML (--- ... ---) (.md)
    - Markdown puro — agent=auto, task=conteúdo completo
    """
    raw = path.read_text(encoding="utf-8")

    # Markdown com frontmatter YAML
    fm_match = re.match(r"^---\n(.*?)\n---\n(.*)", raw, re.DOTALL)
    if fm_match:
        meta = yaml.safe_load(fm_match.group(1)) or {}
        meta.setdefault("agent", "auto")
        meta["task"] = fm_match.group(2).strip()
        return meta

    # YAML puro
    if path.suffix in (".yaml", ".yml"):
        data = yaml.safe_load(raw) or {}
        data.setdefault("agent", "auto")
        return data

    # Markdown puro — sem frontmatter
    return {"agent": "auto", "task": raw.strip()}


def resolve_context(task_def: dict, base_dir: Path) -> str:
    """Carrega arquivos de context_files restritos ao project root.

    Bloqueia path traversal: caminhos absolutos são ignorados, e qualquer
    candidato resolvido fora de `project_root` é descartado.
    """
    files = task_def.get("context_files", []) or []
    parts = []
    project_root = (Path(__file__).parent.parent).resolve()
    base_dir = base_dir.resolve()

    for f in files:
        f_path = Path(f)
        if f_path.is_absolute():
            # Recusa absolute paths — sem conhecê-los, qualquer arquivo do FS é alcançável
            continue
        for cand in (base_dir / f, project_root / f):
            try:
                resolved = cand.resolve()
            except (OSError, RuntimeError):
                continue
            if not resolved.is_relative_to(project_root):
                continue
            if resolved.is_file():
                parts.append(
                    f"## Contexto: {f}\n{resolved.read_text(encoding='utf-8')}"
                )
                break

    return "\n\n".join(parts)


def run_task_file(path: Path, supervisor) -> AgentResult:
    """Carrega e executa um arquivo de tarefa via supervisor."""
    if path.suffix not in _SUPPORTED_EXTS:
        raise ValueError(f"Formato não suportado: {path.suffix}. Use {_SUPPORTED_EXTS}")

    task_def = load_task_file(path)
    task_text = (task_def.get("task") or "").strip()
    agent_name = task_def.get("agent", "auto")
    context = resolve_context(task_def, path.parent)

    if not task_text:
        raise ValueError(f"Campo 'task' vazio em {path}")

    result = _dispatch(agent_name, task_text, context, supervisor)
    saved = _save_output(task_def, result)

    if saved:
        from rich.console import Console
        Console().print(f"[dim]Output salvo em: {saved}[/dim]")

    return result


def _dispatch(agent_name: str, task_text: str, context: str, supervisor) -> AgentResult:
    """Roteia para agente direto (com context) ou supervisor (sem)."""
    from agents.loader import AGENT_COMMANDS

    is_auto = agent_name in ("auto", "supervisor", "")

    if not is_auto:
        # Chamada direta ao agente para preservar context_files
        agent = supervisor.get_agent(agent_name)
        if agent:
            return agent.run(task_text, context=context)
        # Agente não encontrado — tenta via comando
        cmd = next((c for c, a in AGENT_COMMANDS.items() if a == agent_name), None)
        user_input = f"{cmd} {task_text}" if cmd else task_text
    else:
        user_input = task_text

    return supervisor.route(user_input)


def _save_output(task_def: dict, result: AgentResult) -> Path | None:
    output = task_def.get("output")
    if not output:
        return None
    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(result.content, encoding="utf-8")
    return out_path


def list_task_files(directory: Path | None = None) -> list[Path]:
    """Retorna todos os arquivos de tarefa na pasta tasks/."""
    root = directory or TASKS_DIR
    if not root.exists():
        return []
    return sorted(
        p for p in root.rglob("*") if p.suffix in _SUPPORTED_EXTS and not p.name.startswith("_")
    )

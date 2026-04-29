"""Testes para cli/runner.py."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

from agents.base import AgentConfig, AgentResult, BaseAgent


def _make_agent(name="mock", content="resposta") -> BaseAgent:
    cfg = AgentConfig(name=name, tier="T2", system_prompt="mock")
    agent = MagicMock(spec=BaseAgent)
    agent.config = cfg
    agent.run.return_value = AgentResult(content=content, tool_calls_count=0, tokens_used=10)
    return agent


def _make_supervisor(agent_content="resposta do supervisor"):
    sup = MagicMock()
    sup.route.return_value = AgentResult(content=agent_content, tool_calls_count=0, tokens_used=5)
    sup.get_agent.return_value = None
    sup.list_agents.return_value = ["geral", "sql_expert"]
    return sup


# ---------------------------------------------------------------------------
# load_task_file
# ---------------------------------------------------------------------------

def test_load_yaml_pure(tmp_path):
    from cli.runner import load_task_file

    f = tmp_path / "task.yaml"
    f.write_text("agent: sql_expert\ntask: SELECT 1\n")
    data = load_task_file(f)
    assert data["agent"] == "sql_expert"
    assert data["task"] == "SELECT 1"


def test_load_yaml_sets_default_agent(tmp_path):
    from cli.runner import load_task_file

    f = tmp_path / "task.yaml"
    f.write_text("task: SELECT 1\n")
    data = load_task_file(f)
    assert data["agent"] == "auto"


def test_load_markdown_with_frontmatter(tmp_path):
    from cli.runner import load_task_file

    f = tmp_path / "task.md"
    f.write_text("---\nagent: spark_expert\noutput: out.md\n---\nCrie pipeline.\n")
    data = load_task_file(f)
    assert data["agent"] == "spark_expert"
    assert data["output"] == "out.md"
    assert data["task"] == "Crie pipeline."


def test_load_markdown_pure(tmp_path):
    from cli.runner import load_task_file

    f = tmp_path / "task.md"
    f.write_text("Crie um pipeline sem frontmatter.\n")
    data = load_task_file(f)
    assert data["agent"] == "auto"
    assert "pipeline" in data["task"]


def test_load_unsupported_extension(tmp_path):
    from cli.runner import run_task_file

    f = tmp_path / "task.txt"
    f.write_text("texto")
    sup = _make_supervisor()
    with pytest.raises(ValueError, match="Formato não suportado"):
        run_task_file(f, sup)


# ---------------------------------------------------------------------------
# resolve_context
# ---------------------------------------------------------------------------

def test_resolve_context_with_existing_file(tmp_path, monkeypatch):
    """Usa caminho relativo dentro do project_root (absolute paths são rejeitados por segurança)."""
    from cli import runner
    from cli.runner import resolve_context

    # Aponta o "project_root" para tmp_path (sandbox seguro)
    monkeypatch.setattr(runner, "__file__", str(tmp_path / "cli" / "runner.py"))
    ctx_file = tmp_path / "naming.md"
    ctx_file.write_text("## Naming\nuse snake_case")
    task_def = {"context_files": ["naming.md"]}
    result = resolve_context(task_def, tmp_path)
    assert "snake_case" in result


def test_resolve_context_rejects_absolute_path_traversal(tmp_path):
    """Path traversal protection: absolute paths são silenciosamente ignorados."""
    from cli.runner import resolve_context

    task_def = {"context_files": ["/etc/passwd"]}
    result = resolve_context(task_def, tmp_path)
    assert result == ""


def test_resolve_context_missing_file_ignored(tmp_path):
    from cli.runner import resolve_context

    task_def = {"context_files": ["nonexistent_file.md"]}
    result = resolve_context(task_def, tmp_path)
    assert result == ""


def test_resolve_context_empty(tmp_path):
    from cli.runner import resolve_context

    result = resolve_context({}, tmp_path)
    assert result == ""


# ---------------------------------------------------------------------------
# run_task_file
# ---------------------------------------------------------------------------

def test_run_task_file_auto_routes_supervisor(tmp_path):
    from cli.runner import run_task_file

    f = tmp_path / "task.yaml"
    f.write_text("agent: auto\ntask: o que é Delta Lake?\n")
    sup = _make_supervisor("Delta Lake é...")
    result = run_task_file(f, sup)
    sup.route.assert_called_once_with("o que é Delta Lake?")
    assert result.content == "Delta Lake é..."


def test_run_task_file_named_agent_uses_get_agent(tmp_path):
    from cli.runner import run_task_file

    f = tmp_path / "task.yaml"
    f.write_text("agent: spark_expert\ntask: otimizar join\n")
    mock_agent = _make_agent("spark_expert", "join otimizado")
    sup = _make_supervisor()
    sup.get_agent.return_value = mock_agent
    result = run_task_file(f, sup)
    mock_agent.run.assert_called_once_with("otimizar join", context="")
    assert result.content == "join otimizado"


def test_run_task_file_named_agent_not_found_falls_back(tmp_path):
    from cli.runner import run_task_file

    f = tmp_path / "task.yaml"
    f.write_text("agent: spark_expert\ntask: otimizar join\n")
    sup = _make_supervisor("fallback")
    sup.get_agent.return_value = None  # agente não encontrado
    run_task_file(f, sup)
    # Deve cair no supervisor.route
    sup.route.assert_called()


def test_run_task_file_saves_output(tmp_path):
    from cli.runner import run_task_file

    out_file = tmp_path / "out.md"
    f = tmp_path / "task.yaml"
    f.write_text(f"agent: auto\ntask: tarefa\noutput: {out_file}\n")
    sup = _make_supervisor("conteúdo gerado")
    run_task_file(f, sup)
    assert out_file.exists()
    assert "conteúdo gerado" in out_file.read_text()


def test_run_task_file_empty_task_raises(tmp_path):
    from cli.runner import run_task_file

    f = tmp_path / "task.yaml"
    f.write_text("agent: auto\ntask: \n")
    sup = _make_supervisor()
    with pytest.raises(ValueError, match="vazio"):
        run_task_file(f, sup)


def test_run_task_file_no_output_field(tmp_path):
    from cli.runner import run_task_file

    f = tmp_path / "task.yaml"
    f.write_text("agent: auto\ntask: tarefa simples\n")
    sup = _make_supervisor("resposta")
    result = run_task_file(f, sup)
    assert result.content == "resposta"


# ---------------------------------------------------------------------------
# list_task_files
# ---------------------------------------------------------------------------

def test_list_task_files_finds_yaml_and_md(tmp_path):
    from cli.runner import list_task_files

    (tmp_path / "sql").mkdir()
    (tmp_path / "sql" / "query.yaml").write_text("task: x\n")
    (tmp_path / "spark" ).mkdir()
    (tmp_path / "spark" / "pipeline.md").write_text("---\nagent: auto\n---\ntask")
    (tmp_path / "_template.yaml").write_text("task: x\n")  # deve ser ignorado

    files = list_task_files(tmp_path)
    names = [f.name for f in files]
    assert "query.yaml" in names
    assert "pipeline.md" in names
    assert "_template.yaml" not in names  # prefixo _ ignorado


def test_list_task_files_empty_dir(tmp_path):
    from cli.runner import list_task_files

    assert list_task_files(tmp_path) == []


def test_list_task_files_nonexistent_dir():
    from cli.runner import list_task_files

    assert list_task_files(Path("/nonexistent/path/xyz")) == []


# ---------------------------------------------------------------------------
# Arquivos de exemplo existem
# ---------------------------------------------------------------------------

def test_example_task_files_are_valid_yaml():
    """Verifica que todos os YAMLs de exemplo no tasks/ são válidos."""
    from cli.runner import TASKS_DIR, list_task_files

    for f in list_task_files(TASKS_DIR):
        if f.suffix in (".yaml", ".yml"):
            data = yaml.safe_load(f.read_text())
            assert data is not None, f"{f} retornou None"
        # MD puro não precisa de validação YAML

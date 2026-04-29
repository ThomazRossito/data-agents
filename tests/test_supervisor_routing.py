"""Testes unitários para roteamento do Supervisor."""

from __future__ import annotations


def test_workflow_pattern_covers_wf05_to_wf07():
    from workflow.dag import WORKFLOW_PATTERN

    for wf_id in ("WF-05", "WF-06", "WF-07"):
        assert WORKFLOW_PATTERN.search(wf_id), f"{wf_id} não encontrado no WORKFLOW_PATTERN"


def test_wf04_has_three_steps():
    from workflow.dag import WORKFLOWS

    wf04 = WORKFLOWS["WF-04"]
    assert len(wf04.steps) == 3
    agent_names = [s.agent_name for s in wf04.steps]
    assert "naming_guard" in agent_names
    assert "governance_auditor" in agent_names
    assert "data_quality" in agent_names


def test_wf05_implantation_workflow_exists():
    from workflow.dag import WORKFLOWS

    assert "WF-05" in WORKFLOWS
    wf05 = WORKFLOWS["WF-05"]
    assert len(wf05.steps) == 5
    agent_names = [s.agent_name for s in wf05.steps]
    assert "pipeline_architect" in agent_names
    assert "governance_auditor" in agent_names
    assert "devops_engineer" in agent_names


def test_wf06_migration_workflow_exists():
    from workflow.dag import WORKFLOWS

    assert "WF-06" in WORKFLOWS
    wf06 = WORKFLOWS["WF-06"]
    assert len(wf06.steps) == 6


def test_wf07_sustentation_workflow_exists():
    from workflow.dag import WORKFLOWS

    assert "WF-07" in WORKFLOWS
    wf07 = WORKFLOWS["WF-07"]
    assert len(wf07.steps) == 4


def test_detect_workflow_implantation():
    from workflow.dag import detect_workflow

    result = detect_workflow("implantar um novo lakehouse no Fabric")
    assert result is not None
    assert result.id == "WF-05"


def test_detect_workflow_migration():
    from workflow.dag import detect_workflow

    result = detect_workflow("migrar lakehouse do Synapse para Databricks")
    assert result is not None
    assert result.id == "WF-06"


def test_detect_workflow_sustentation():
    from workflow.dag import detect_workflow

    result = detect_workflow("sustentação do lakehouse de produção")
    assert result is not None
    assert result.id == "WF-07"


def test_detect_workflow_returns_none_for_unknown():
    from workflow.dag import detect_workflow

    result = detect_workflow("como funciona o Python?")
    assert result is None


def test_skills_dir_path_points_to_skills_skills():
    from pathlib import Path

    import agents.base as base_module

    expected_suffix = Path("skills") / "skills"
    assert str(base_module.SKILLS_DIR).endswith(str(expected_suffix)), (
        f"SKILLS_DIR aponta para {base_module.SKILLS_DIR}, esperado sufixo '{expected_suffix}'"
    )


def test_kb_index_has_18_domains():
    from pathlib import Path

    import yaml

    index_path = Path(__file__).parent.parent / "kb" / "_index.yaml"
    data = yaml.safe_load(index_path.read_text())
    domains = data.get("domains", {})
    assert len(domains) == 18, (
        f"Esperado 18 domínios, encontrado {len(domains)}: {list(domains.keys())}"
    )

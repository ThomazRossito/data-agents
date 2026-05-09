"""Testes do comando /analyze-project."""

from commands.analyze import (
    ANALYZE_GROUPS,
    ANALYZE_PROMPTS,
    _DEFAULT_ANALYZE_PROMPT,
    build_report,
    parse_analyze_args,
)


class TestParseAnalyzeArgs:
    """Testes para o parser de argumentos do /analyze-project."""

    def test_default_group_no_flags(self):
        agents, description = parse_analyze_args("/analyze-project meu pipeline de dados")
        assert agents == ANALYZE_GROUPS["default"]
        assert description == "meu pipeline de dados"

    def test_default_group_no_description(self):
        agents, description = parse_analyze_args("/analyze-project")
        assert agents == ANALYZE_GROUPS["default"]
        assert description == ""

    def test_quality_flag(self):
        agents, description = parse_analyze_args("/analyze-project --quality projeto X")
        assert agents == ANALYZE_GROUPS["quality"]
        assert description == "projeto X"

    def test_arch_flag(self):
        agents, description = parse_analyze_args("/analyze-project --arch projeto Y")
        assert agents == ANALYZE_GROUPS["arch"]
        assert description == "projeto Y"

    def test_databricks_flag(self):
        agents, description = parse_analyze_args("/analyze-project --databricks pipeline Medallion")
        assert agents == ANALYZE_GROUPS["databricks"]
        assert description == "pipeline Medallion"

    def test_fabric_flag(self):
        agents, description = parse_analyze_args("/analyze-project --fabric lakehouse produção")
        assert agents == ANALYZE_GROUPS["fabric"]
        assert description == "lakehouse produção"

    def test_quality_flag_no_description(self):
        agents, description = parse_analyze_args("/analyze-project --quality")
        assert agents == ANALYZE_GROUPS["quality"]
        assert description == ""

    def test_unknown_flag_treated_as_description(self):
        agents, description = parse_analyze_args("/analyze-project --unknown algo")
        assert agents == ANALYZE_GROUPS["default"]
        assert description == "--unknown algo"


class TestAnalyzeGroups:
    """Testes para os grupos de agentes."""

    def test_default_group_has_four_agents(self):
        assert len(ANALYZE_GROUPS["default"]) == 4

    def test_default_group_members(self):
        assert "databricks-engineer" in ANALYZE_GROUPS["default"]
        assert "fabric-engineer" in ANALYZE_GROUPS["default"]
        assert "data-quality-steward" in ANALYZE_GROUPS["default"]
        assert "governance-auditor" in ANALYZE_GROUPS["default"]

    def test_quality_group_has_three_agents(self):
        assert len(ANALYZE_GROUPS["quality"]) == 3

    def test_arch_group_has_three_agents(self):
        assert len(ANALYZE_GROUPS["arch"]) == 3

    def test_databricks_group_is_single_agent(self):
        assert ANALYZE_GROUPS["databricks"] == ["databricks-engineer"]

    def test_fabric_group_is_single_agent(self):
        assert ANALYZE_GROUPS["fabric"] == ["fabric-engineer"]

    def test_all_agents_in_groups_have_prompts(self):
        all_agents = set()
        for agents in ANALYZE_GROUPS.values():
            all_agents.update(agents)
        for agent in all_agents:
            assert agent in ANALYZE_PROMPTS or _DEFAULT_ANALYZE_PROMPT, (
                f"Agent {agent} has no dedicated prompt"
            )


class TestAnalyzePrompts:
    """Testes para os prompts de análise."""

    def test_all_default_agents_have_dedicated_prompts(self):
        for agent in ANALYZE_GROUPS["default"]:
            assert agent in ANALYZE_PROMPTS, f"Agent {agent} missing from ANALYZE_PROMPTS"

    def test_all_prompts_have_task_placeholder(self):
        for agent, prompt in ANALYZE_PROMPTS.items():
            assert "{task}" in prompt, f"Agent {agent} prompt missing {{task}} placeholder"

    def test_prompts_are_non_empty(self):
        for agent, prompt in ANALYZE_PROMPTS.items():
            assert len(prompt) > 100, f"Agent {agent} prompt suspiciously short"

    def test_default_prompt_has_task_placeholder(self):
        assert "{task}" in _DEFAULT_ANALYZE_PROMPT


class TestBuildReport:
    """Testes para o consolidador de relatório."""

    def test_basic_report_structure(self):
        results = [
            ("databricks-engineer", "Pipeline está bem estruturado.", 0.001),
            ("fabric-engineer", "Lakehouse precisa de otimização.", 0.002),
        ]
        report = build_report(
            results, "Projeto de teste", ["databricks-engineer", "fabric-engineer"]
        )
        assert "# Relatório de Análise" in report
        assert "databricks-engineer" in report
        assert "fabric-engineer" in report
        assert "Pipeline está bem estruturado." in report
        assert "Lakehouse precisa de otimização." in report

    def test_report_includes_total_cost(self):
        results = [
            ("data-quality-steward", "Qualidade OK.", 0.003),
        ]
        report = build_report(results, "", ["data-quality-steward"])
        assert "$0.00300" in report

    def test_report_includes_project_description_when_provided(self):
        results = [("governance-auditor", "Governança OK.", 0.001)]
        report = build_report(results, "Pipeline de vendas B2B", ["governance-auditor"])
        assert "Pipeline de vendas B2B" in report

    def test_report_skips_project_description_when_empty(self):
        results = [("governance-auditor", "Governança OK.", 0.001)]
        report = build_report(results, "", ["governance-auditor"])
        assert "## Contexto do Projeto" not in report

    def test_report_skips_empty_agent_results(self):
        results = [
            ("databricks-engineer", "", 0.0),
            ("fabric-engineer", "Resultado válido.", 0.001),
        ]
        report = build_report(results, "", ["databricks-engineer", "fabric-engineer"])
        assert "## databricks-engineer" not in report
        assert "## fabric-engineer" in report

    def test_report_includes_agent_names_header(self):
        results = [("data-quality-steward", "OK.", 0.001)]
        report = build_report(results, "", ["data-quality-steward"])
        assert "data-quality-steward" in report

    def test_report_has_markdown_separator(self):
        results = [("fabric-engineer", "Análise completa.", 0.002)]
        report = build_report(results, "Contexto", ["fabric-engineer"])
        assert "---" in report

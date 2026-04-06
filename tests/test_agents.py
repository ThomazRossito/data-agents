"""
Testes de definição e carregamento dos agentes.

Cobre:
  - Loader dinâmico (agents/loader.py): parsing de frontmatter, resolução de tools, carga completa
  - Agentes T1 (Core): sql-expert, spark-expert, pipeline-architect
  - Agentes T2 (Especializados): data-quality-steward, governance-auditor, semantic-modeler
  - Compatibilidade retroativa com as factories Python legadas (definitions/)
"""

from pathlib import Path

import pytest

from agents.loader import load_agent, load_all_agents, _parse_frontmatter, _resolve_tools


# ─── Testes do Loader Dinâmico ────────────────────────────────────────────────

class TestFrontmatterParser:
    """Testes para o parser de frontmatter YAML."""

    def test_parse_valid_frontmatter(self, tmp_path):
        content = "---\nname: test-agent\ndescription: \"Agente de teste.\"\nmodel: claude-sonnet-4-6\ntools: [Read, Grep]\n---\n# Body\nConteúdo do agente."
        meta, body = _parse_frontmatter(content)
        assert meta["name"] == "test-agent"
        assert meta["description"] == "Agente de teste."
        assert meta["model"] == "claude-sonnet-4-6"
        assert meta["tools"] == ["Read", "Grep"]
        assert "# Body" in body

    def test_parse_frontmatter_with_mcp_servers(self):
        content = "---\nname: test\ndescription: \"Desc.\"\nmodel: claude-sonnet-4-6\ntools: [Read]\nmcp_servers: [databricks, fabric]\n---\nBody."
        meta, _ = _parse_frontmatter(content)
        assert meta["mcp_servers"] == ["databricks", "fabric"]

    def test_parse_frontmatter_without_mcp_servers(self):
        content = "---\nname: test\ndescription: \"Desc.\"\nmodel: claude-sonnet-4-6\ntools: [Read]\n---\nBody."
        meta, _ = _parse_frontmatter(content)
        assert "mcp_servers" not in meta

    def test_parse_frontmatter_missing_raises(self):
        content = "# Sem frontmatter\nApenas conteúdo."
        with pytest.raises(ValueError, match="frontmatter YAML"):
            _parse_frontmatter(content)


class TestToolResolver:
    """Testes para a resolução de aliases de tool sets."""

    def test_literal_tools_passthrough(self):
        tools = _resolve_tools(["Read", "Grep", "Glob", "Write"])
        assert tools == ["Read", "Grep", "Glob", "Write"]

    def test_databricks_readonly_alias_expands(self):
        tools = _resolve_tools(["databricks_readonly"])
        assert len(tools) > 0
        assert all("databricks" in t for t in tools)

    def test_fabric_all_alias_expands(self):
        tools = _resolve_tools(["fabric_all"])
        assert len(tools) > 0
        assert any("fabric" in t for t in tools)

    def test_mixed_literals_and_aliases(self):
        tools = _resolve_tools(["Read", "databricks_readonly"])
        assert "Read" in tools
        assert any("databricks" in t for t in tools)


class TestLoadAllAgents:
    """Testes para o carregamento completo do registry."""

    def test_load_all_agents_returns_dict(self):
        agents = load_all_agents()
        assert isinstance(agents, dict)

    def test_all_expected_agents_loaded(self):
        agents = load_all_agents()
        expected = [
            "sql-expert",
            "spark-expert",
            "pipeline-architect",
            "data-quality-steward",
            "governance-auditor",
            "semantic-modeler",
        ]
        for name in expected:
            assert name in agents, f"Agente '{name}' não encontrado no registry"

    def test_template_not_loaded(self):
        """Arquivo _template.md não deve ser carregado como agente."""
        agents = load_all_agents()
        assert "_template" not in agents

    def test_all_agents_have_description(self):
        agents = load_all_agents()
        for name, agent in agents.items():
            assert agent.description, f"Agente '{name}' sem description"
            assert len(agent.description) > 20, f"Description do agente '{name}' muito curta"

    def test_all_agents_have_prompt(self):
        agents = load_all_agents()
        for name, agent in agents.items():
            assert agent.prompt, f"Agente '{name}' sem prompt (body)"
            assert len(agent.prompt) > 100, f"Prompt do agente '{name}' muito curto"

    def test_all_agents_have_model(self):
        agents = load_all_agents()
        valid_models = {"claude-sonnet-4-6", "claude-opus-4-6"}
        for name, agent in agents.items():
            assert agent.model in valid_models, (
                f"Agente '{name}' com model inválido: {agent.model}"
            )


# ─── Testes dos Agentes T1 (Core) ────────────────────────────────────────────

class TestSqlExpert:
    """Testes específicos para o sql-expert."""

    def test_sql_expert_has_no_bash(self):
        agents = load_all_agents()
        agent = agents["sql-expert"]
        assert "Bash" not in (agent.tools or []), "SQL Expert não deve ter Bash"

    def test_sql_expert_has_rti_tools(self):
        agents = load_all_agents()
        agent = agents["sql-expert"]
        rti_tools = [t for t in (agent.tools or []) if "fabric_rti" in t]
        assert len(rti_tools) > 0, "SQL Expert deve ter tools do Fabric RTI para KQL"

    def test_sql_expert_has_databricks_tools(self):
        agents = load_all_agents()
        agent = agents["sql-expert"]
        db_tools = [t for t in (agent.tools or []) if "databricks" in t]
        assert len(db_tools) > 0, "SQL Expert deve ter tools do Databricks"


class TestSparkExpert:
    """Testes específicos para o spark-expert."""

    def test_spark_expert_has_no_mcp_tools(self):
        agents = load_all_agents()
        agent = agents["spark-expert"]
        mcp_tools = [t for t in (agent.tools or []) if t.startswith("mcp__")]
        assert len(mcp_tools) == 0, f"Spark Expert não deve ter MCP tools: {mcp_tools}"

    def test_spark_expert_model_is_sonnet(self):
        agents = load_all_agents()
        agent = agents["spark-expert"]
        assert "sonnet" in agent.model.lower()


class TestPipelineArchitect:
    """Testes específicos para o pipeline-architect."""

    def test_pipeline_architect_has_both_platforms(self):
        agents = load_all_agents()
        agent = agents["pipeline-architect"]
        tools = agent.tools or []
        has_databricks = any("databricks" in t for t in tools)
        has_fabric = any("fabric" in t for t in tools)
        assert has_databricks, "Pipeline Architect deve ter tools do Databricks"
        assert has_fabric, "Pipeline Architect deve ter tools do Fabric"

    def test_pipeline_architect_model_is_opus(self):
        agents = load_all_agents()
        agent = agents["pipeline-architect"]
        assert "opus" in agent.model.lower()


# ─── Testes dos Agentes T2 (Especializados) ──────────────────────────────────

class TestDataQualitySteward:
    """Testes específicos para o data-quality-steward."""

    def test_data_quality_steward_has_execute_sql(self):
        """Data Quality Steward precisa de execute_sql para profiling."""
        agents = load_all_agents()
        agent = agents["data-quality-steward"]
        assert "mcp__databricks__execute_sql" in (agent.tools or []), (
            "Data Quality Steward deve ter execute_sql para profiling"
        )

    def test_data_quality_steward_has_no_write_mcp(self):
        """Data Quality Steward não deve ter tools de escrita no Fabric."""
        agents = load_all_agents()
        agent = agents["data-quality-steward"]
        write_tools = [
            t for t in (agent.tools or [])
            if "upload" in t or "create" in t or "ingest" in t
        ]
        assert len(write_tools) == 0, (
            f"Data Quality Steward não deve ter tools de escrita: {write_tools}"
        )

    def test_data_quality_steward_has_rti_query(self):
        """Data Quality Steward precisa de KQL para monitoramento em tempo real."""
        agents = load_all_agents()
        agent = agents["data-quality-steward"]
        assert "mcp__fabric_rti__kusto_query" in (agent.tools or []), (
            "Data Quality Steward deve ter kusto_query para monitoramento RTI"
        )


class TestGovernanceAuditor:
    """Testes específicos para o governance-auditor."""

    def test_governance_auditor_has_lineage_tool(self):
        """Governance Auditor precisa de get_lineage para documentar linhagem."""
        agents = load_all_agents()
        agent = agents["governance-auditor"]
        assert "mcp__fabric_community__get_lineage" in (agent.tools or []), (
            "Governance Auditor deve ter get_lineage"
        )

    def test_governance_auditor_has_no_rti_write(self):
        """Governance Auditor não deve ter tools de escrita no RTI."""
        agents = load_all_agents()
        agent = agents["governance-auditor"]
        rti_write = [
            t for t in (agent.tools or [])
            if "fabric_rti" in t and ("ingest" in t or "create" in t)
        ]
        assert len(rti_write) == 0, (
            f"Governance Auditor não deve ter tools de escrita RTI: {rti_write}"
        )

    def test_governance_auditor_has_execute_sql(self):
        """Governance Auditor precisa de execute_sql para consultar System Tables."""
        agents = load_all_agents()
        agent = agents["governance-auditor"]
        assert "mcp__databricks__execute_sql" in (agent.tools or []), (
            "Governance Auditor deve ter execute_sql para System Tables de auditoria"
        )


class TestSemanticModeler:
    """Testes específicos para o semantic-modeler."""

    def test_semantic_modeler_has_fabric_tools(self):
        """Semantic Modeler precisa de tools do Fabric para inspecionar tabelas Gold."""
        agents = load_all_agents()
        agent = agents["semantic-modeler"]
        fabric_tools = [t for t in (agent.tools or []) if "fabric" in t]
        assert len(fabric_tools) > 0, "Semantic Modeler deve ter tools do Fabric"

    def test_semantic_modeler_has_no_rti_tools(self):
        """Semantic Modeler não usa RTI — foca em modelagem semântica, não streaming."""
        agents = load_all_agents()
        agent = agents["semantic-modeler"]
        rti_tools = [t for t in (agent.tools or []) if "fabric_rti" in t]
        assert len(rti_tools) == 0, (
            f"Semantic Modeler não deve ter tools RTI: {rti_tools}"
        )

    def test_semantic_modeler_model_is_sonnet(self):
        agents = load_all_agents()
        agent = agents["semantic-modeler"]
        assert "sonnet" in agent.model.lower()


# ─── Testes de Arquivos de Registry ──────────────────────────────────────────

class TestRegistryFiles:
    """Testes de integridade dos arquivos de registry."""

    REGISTRY_DIR = Path(__file__).parent.parent / "agents" / "registry"

    def test_all_registry_files_have_valid_frontmatter(self):
        """Todos os arquivos .md no registry (exceto _template) devem ter frontmatter válido."""
        files = [f for f in self.REGISTRY_DIR.glob("*.md") if not f.name.startswith("_")]
        assert len(files) > 0, "Nenhum arquivo de agente encontrado no registry"
        for path in files:
            content = path.read_text(encoding="utf-8")
            try:
                meta, body = _parse_frontmatter(content)
            except ValueError as e:
                pytest.fail(f"Arquivo '{path.name}' com frontmatter inválido: {e}")

    def test_all_registry_files_have_required_fields(self):
        """Todos os arquivos de agente devem ter os campos obrigatórios."""
        files = [f for f in self.REGISTRY_DIR.glob("*.md") if not f.name.startswith("_")]
        for path in files:
            content = path.read_text(encoding="utf-8")
            meta, _ = _parse_frontmatter(content)
            for field in ["name", "description", "model", "tools"]:
                assert field in meta, (
                    f"Arquivo '{path.name}' sem campo obrigatório: '{field}'"
                )

    def test_template_file_exists(self):
        """O arquivo de template deve existir para orientar novos agentes."""
        template = self.REGISTRY_DIR / "_template.md"
        assert template.exists(), "Arquivo _template.md não encontrado no registry"

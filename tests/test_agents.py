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

from agents.loader import load_all_agents, _parse_frontmatter, _resolve_tools


# ─── Testes do Loader Dinâmico ────────────────────────────────────────────────


class TestFrontmatterParser:
    """Testes para o parser de frontmatter YAML."""

    def test_parse_valid_frontmatter(self, tmp_path):
        content = '---\nname: test-agent\ndescription: "Agente de teste."\nmodel: claude-sonnet-4-6\ntools: [Read, Grep]\n---\n# Body\nConteúdo do agente.'
        meta, body = _parse_frontmatter(content)
        assert meta["name"] == "test-agent"
        assert meta["description"] == "Agente de teste."
        assert meta["model"] == "claude-sonnet-4-6"
        assert meta["tools"] == ["Read", "Grep"]
        assert "# Body" in body

    def test_parse_frontmatter_with_mcp_servers(self):
        content = '---\nname: test\ndescription: "Desc."\nmodel: claude-sonnet-4-6\ntools: [Read]\nmcp_servers: [databricks, fabric]\n---\nBody.'
        meta, _ = _parse_frontmatter(content)
        assert meta["mcp_servers"] == ["databricks", "fabric"]

    def test_parse_frontmatter_without_mcp_servers(self):
        content = '---\nname: test\ndescription: "Desc."\nmodel: claude-sonnet-4-6\ntools: [Read]\n---\nBody.'
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

    def test_fabric_semantic_all_alias_expands(self):
        tools = _resolve_tools(["fabric_semantic_all"])
        assert len(tools) > 0
        assert all("fabric_semantic" in t for t in tools)

    def test_fabric_semantic_readonly_is_subset_of_all(self):
        all_tools = set(_resolve_tools(["fabric_semantic_all"]))
        readonly_tools = set(_resolve_tools(["fabric_semantic_readonly"]))
        assert readonly_tools.issubset(all_tools)
        # execute_dax não deve estar no readonly
        assert not any("execute_dax" in t for t in readonly_tools)


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
            "dbt-expert",
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
        valid_models = {
            "claude-sonnet-4-6",
            "claude-opus-4-6",
            "bedrock/anthropic.claude-4-6-sonnet",  # modelo do proxy Flow LiteLLM (produção)
        }
        for name, agent in agents.items():
            assert agent.model in valid_models, f"Agente '{name}' com model inválido: {agent.model}"


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
        # spark-expert gera código localmente — não executa queries nem acessa catálogos.
        # MCPs de plataformas de dados (Databricks, Fabric) não são permitidos.
        # MCPs utilitários sem credenciais (ex: context7 para docs atualizadas) são permitidos.
        UTILITY_MCP_PREFIXES = ("mcp__context7__", "mcp__memory_mcp__")
        platform_mcp_tools = [
            t
            for t in (agent.tools or [])
            if t.startswith("mcp__") and not t.startswith(UTILITY_MCP_PREFIXES)
        ]
        assert len(platform_mcp_tools) == 0, (
            f"Spark Expert não deve ter MCP tools de plataforma de dados: {platform_mcp_tools}"
        )

    def test_spark_expert_model_is_sonnet(self):
        agents = load_all_agents()
        agent = agents["spark-expert"]
        # Aceita bedrock/anthropic.claude-4-6-sonnet (proxy Flow) ou claude-sonnet-4-6 (local)
        assert "sonnet" in agent.model.lower() or "bedrock" in agent.model.lower()


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
        # Aceita bedrock/anthropic.claude-4-6-sonnet (proxy Flow) ou claude-opus-4-6 (local)
        assert "opus" in agent.model.lower() or "bedrock" in agent.model.lower()


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
            t for t in (agent.tools or []) if "upload" in t or "create" in t or "ingest" in t
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
            t for t in (agent.tools or []) if "fabric_rti" in t and ("ingest" in t or "create" in t)
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


class TestDbtExpert:
    """Testes específicos para o dbt-expert."""

    def test_dbt_expert_model_is_sonnet(self):
        agents = load_all_agents()
        agent = agents["dbt-expert"]
        assert "sonnet" in agent.model.lower() or "bedrock" in agent.model.lower()

    def test_dbt_expert_has_no_platform_mcp_tools(self):
        """dbt-expert não executa queries em Databricks/Fabric diretamente."""
        agents = load_all_agents()
        agent = agents["dbt-expert"]
        ALLOWED_MCP_PREFIXES = ("mcp__context7__", "mcp__postgres__")
        platform_mcp_tools = [
            t
            for t in (agent.tools or [])
            if t.startswith("mcp__") and not t.startswith(ALLOWED_MCP_PREFIXES)
        ]
        assert len(platform_mcp_tools) == 0, (
            f"dbt-expert não deve ter MCP tools de plataforma de dados: {platform_mcp_tools}"
        )

    def test_dbt_expert_has_context7(self):
        """dbt-expert precisa de context7 para buscar docs atualizadas do dbt."""
        agents = load_all_agents()
        agent = agents["dbt-expert"]
        context7_tools = [t for t in (agent.tools or []) if "context7" in t]
        assert len(context7_tools) > 0, "dbt-expert deve ter tools do context7"

    def test_dbt_expert_tier_is_t2(self):
        from agents.loader import _parse_frontmatter, AGENTS_REGISTRY_DIR

        path = AGENTS_REGISTRY_DIR / "dbt-expert.md"
        content = path.read_text(encoding="utf-8")
        meta, _ = _parse_frontmatter(content)
        assert meta.get("tier") == "T2", "dbt-expert deve ter tier: T2"


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
        assert len(rti_tools) == 0, f"Semantic Modeler não deve ter tools RTI: {rti_tools}"

    def test_semantic_modeler_model_is_sonnet(self):
        agents = load_all_agents()
        agent = agents["semantic-modeler"]
        assert "sonnet" in agent.model.lower() or "bedrock" in agent.model.lower()


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
                assert field in meta, f"Arquivo '{path.name}' sem campo obrigatório: '{field}'"

    def test_template_file_exists(self):
        """O arquivo de template deve existir para orientar novos agentes."""
        template = self.REGISTRY_DIR / "_template.md"
        assert template.exists(), "Arquivo _template.md não encontrado no registry"


# ─── Testes de Token Budgets por Tier (Ch. 5 — Agent Loop) ──────────────────


class TestTokenBudgetsByTier:
    """Testes para maxTurns e effort por tier (Ch. 5 — Agent Loop)."""

    def test_tier_turns_map_sets_max_turns_on_agents(self):
        """tier_turns_map deve definir maxTurns nos agentes conforme o tier."""
        tier_map = {"T1": 20, "T2": 10, "T3": 3}
        agents = load_all_agents(tier_turns_map=tier_map, inject_cache_prefix=False)

        for name, agent in agents.items():
            if name == "sql-expert":  # T1
                assert agent.maxTurns == 20, "sql-expert (T1) deveria ter maxTurns=20"
            if name == "data-quality-steward":  # T2
                assert agent.maxTurns == 10, "data-quality-steward (T2) deveria ter maxTurns=10"

    def test_tier_effort_map_sets_effort_on_agents(self):
        """tier_effort_map deve definir effort nos agentes conforme o tier."""
        effort_map = {"T1": "high", "T2": "medium", "T3": "low"}
        agents = load_all_agents(tier_effort_map=effort_map, inject_cache_prefix=False)

        for name, agent in agents.items():
            if name == "pipeline-architect":  # T1
                assert agent.effort == "high"
            if name == "governance-auditor":  # T2
                assert agent.effort == "medium"

    def test_no_tier_map_leaves_max_turns_none(self):
        """Sem tier_turns_map, maxTurns deve ser None (sem limite por tier)."""
        agents = load_all_agents(tier_turns_map=None, inject_cache_prefix=False)
        for name, agent in agents.items():
            assert agent.maxTurns is None, f"Agente '{name}' deveria ter maxTurns=None"

    def test_no_effort_map_leaves_effort_none(self):
        """Sem tier_effort_map, effort deve ser None."""
        agents = load_all_agents(tier_effort_map=None, inject_cache_prefix=False)
        for name, agent in agents.items():
            assert agent.effort is None, f"Agente '{name}' deveria ter effort=None"

    def test_frontmatter_max_turns_overrides_tier_map(self, tmp_path):
        """max_turns no frontmatter tem prioridade sobre tier_turns_map."""
        agent_file = tmp_path / "custom-agent.md"
        agent_file.write_text(
            '---\nname: custom-agent\ndescription: "Agente custom."\n'
            "model: claude-sonnet-4-6\ntools: [Read]\ntier: T1\nmax_turns: 7\n---\n# Body\n"
            "Conteúdo do agente de teste.",
            encoding="utf-8",
        )

        from agents.loader import load_agent

        _, agent = load_agent(
            agent_file,
            tier_turns_map={"T1": 20},  # tier diz 20, frontmatter diz 7
            inject_cache_prefix=False,
        )
        assert agent.maxTurns == 7, "Frontmatter max_turns=7 deve prevalecer sobre tier T1=20"

    def test_frontmatter_effort_overrides_tier_map(self, tmp_path):
        """effort no frontmatter tem prioridade sobre tier_effort_map."""
        agent_file = tmp_path / "effort-agent.md"
        agent_file.write_text(
            '---\nname: effort-agent\ndescription: "Agente effort."\n'
            "model: claude-sonnet-4-6\ntools: [Read]\ntier: T2\neffort: high\n---\n# Body\n"
            "Conteúdo.",
            encoding="utf-8",
        )

        from agents.loader import load_agent

        _, agent = load_agent(
            agent_file,
            tier_effort_map={"T2": "medium"},  # tier diz medium, frontmatter diz high
            inject_cache_prefix=False,
        )
        assert agent.effort == "high", (
            "Frontmatter effort=high deve prevalecer sobre tier T2=medium"
        )

    def test_partial_tier_map_only_affects_covered_tiers(self):
        """tier_turns_map parcial não deve afetar tiers não listados."""
        partial_map = {"T1": 25}  # só T1, T2 e T3 ficam sem limite
        agents = load_all_agents(tier_turns_map=partial_map, inject_cache_prefix=False)

        for name, agent in agents.items():
            # T2 agents não devem ter maxTurns setado pelo mapa
            if name in ("data-quality-steward", "governance-auditor", "semantic-modeler"):
                assert agent.maxTurns is None, (
                    f"Agente T2 '{name}' não deve ter maxTurns com mapa parcial T1-only"
                )


# ─── Testes de Model Routing por Tier ───────────────────────────────────────


class TestModelRoutingByTier:
    """Testes para model routing via tier_model_map no loader."""

    def test_load_without_tier_map_uses_frontmatter_model(self):
        """Sem tier_model_map, cada agente usa o model do seu frontmatter."""
        agents = load_all_agents(tier_model_map=None)
        # sql-expert é T1 — frontmatter pode declarar sonnet ou bedrock (proxy Flow)
        assert (
            "sonnet" in agents["sql-expert"].model.lower()
            or "bedrock" in agents["sql-expert"].model.lower()
        )
        # pipeline-architect é T1 — frontmatter pode declarar opus ou bedrock (proxy Flow)
        assert (
            "opus" in agents["pipeline-architect"].model.lower()
            or "bedrock" in agents["pipeline-architect"].model.lower()
        )

    def test_load_with_empty_tier_map_uses_frontmatter_model(self):
        """Com tier_model_map vazio, comportamento idêntico a None."""
        agents = load_all_agents(tier_model_map={})
        assert (
            "sonnet" in agents["sql-expert"].model.lower()
            or "bedrock" in agents["sql-expert"].model.lower()
        )
        assert (
            "opus" in agents["pipeline-architect"].model.lower()
            or "bedrock" in agents["pipeline-architect"].model.lower()
        )

    def test_load_with_tier_map_overrides_model(self):
        """Com tier_model_map populado, o modelo do tier sobrescreve o do frontmatter."""
        tier_map = {"T1": "claude-opus-4-6", "T2": "claude-haiku-3-5"}
        agents = load_all_agents(tier_model_map=tier_map)
        # sql-expert é T1 → deve receber claude-opus-4-6
        assert agents["sql-expert"].model == "claude-opus-4-6"
        # data-quality-steward é T2 → deve receber claude-haiku-3-5
        assert agents["data-quality-steward"].model == "claude-haiku-3-5"

    def test_load_with_partial_tier_map(self):
        """Se o tier_model_map não cobre todos os tiers, apenas os cobertos são roteados."""
        tier_map = {"T2": "claude-haiku-3-5"}
        agents = load_all_agents(tier_model_map=tier_map)
        # sql-expert é T1, não está no mapa → mantém frontmatter (sonnet)
        assert "sonnet" in agents["sql-expert"].model.lower()
        # data-quality-steward é T2 → recebe haiku
        assert agents["data-quality-steward"].model == "claude-haiku-3-5"

    def test_all_t1_agents_have_tier_field(self):
        """Todos os agentes T1 devem declarar tier no frontmatter."""
        from agents.loader import _parse_frontmatter, AGENTS_REGISTRY_DIR

        t1_agents = ["sql-expert", "spark-expert", "pipeline-architect"]
        for name in t1_agents:
            path = AGENTS_REGISTRY_DIR / f"{name}.md"
            content = path.read_text(encoding="utf-8")
            meta, _ = _parse_frontmatter(content)
            assert meta.get("tier") == "T1", f"Agente '{name}' deve ter tier: T1"

    def test_all_t2_agents_have_tier_field(self):
        """Todos os agentes T2 devem declarar tier no frontmatter."""
        from agents.loader import _parse_frontmatter, AGENTS_REGISTRY_DIR

        t2_agents = ["data-quality-steward", "governance-auditor", "semantic-modeler", "dbt-expert"]
        for name in t2_agents:
            path = AGENTS_REGISTRY_DIR / f"{name}.md"
            content = path.read_text(encoding="utf-8")
            meta, _ = _parse_frontmatter(content)
            assert meta.get("tier") == "T2", f"Agente '{name}' deve ter tier: T2"


# ─── Testes de KB Injection ─────────────────────────────────────────────────


class TestKBInjection:
    """Testes para injeção de index.md das KBs no prompt dos agentes."""

    def test_load_with_kb_injection_adds_content_to_prompt(self):
        """Com inject_kb_index=True, o prompt dos agentes deve conter conteúdo da KB."""
        agents = load_all_agents(inject_kb_index=True)
        # sql-expert tem kb_domains: [sql-patterns, databricks, fabric]
        agent = agents["sql-expert"]
        assert "Knowledge Base" in agent.prompt
        assert "sql-patterns" in agent.prompt.lower() or "Padrões SQL" in agent.prompt

    def test_load_without_kb_injection_preserves_original_prompt(self):
        """Com inject_kb_index=False e inject_skills_index=False, sem contexto injetado."""
        agents = load_all_agents(inject_kb_index=False, inject_skills_index=False)
        agent = agents["sql-expert"]
        assert "[Contexto Injetado]" not in agent.prompt

    def test_load_with_kb_injection_default_false_preserves_prompt(self):
        """O default de inject_kb_index é False — sem injeção de KB index."""
        agents = load_all_agents()
        agent = agents["sql-expert"]
        # KB index não é injetado por padrão (o marcador específico de injeção não aparece)
        assert "[Contexto Injetado] Knowledge Base" not in agent.prompt

    def test_load_without_any_injection_preserves_prompt(self):
        """Com ambas injeções desabilitadas, o prompt não deve ter contexto injetado."""
        agents = load_all_agents(inject_kb_index=False, inject_skills_index=False)
        agent = agents["sql-expert"]
        assert "[Contexto Injetado]" not in agent.prompt

    def test_all_agents_with_kb_domains_get_injection(self):
        """Todos os agentes que declaram kb_domains devem receber injeção quando ativado."""
        agents = load_all_agents(inject_kb_index=True)
        agents_with_kb = [
            "sql-expert",
            "spark-expert",
            "pipeline-architect",
            "semantic-modeler",
            "data-quality-steward",
            "governance-auditor",
            "dbt-expert",
        ]
        for name in agents_with_kb:
            assert "[Contexto Injetado]" in agents[name].prompt, (
                f"Agente '{name}' deveria ter KB injetada no prompt"
            )

    def test_kb_injection_includes_all_declared_domains(self):
        """A injeção deve incluir conteúdo de todos os domínios declarados no kb_domains."""
        agents = load_all_agents(inject_kb_index=True)
        # pipeline-architect tem kb_domains: [pipeline-design, databricks, fabric]
        prompt = agents["pipeline-architect"].prompt
        assert "Design de Pipelines" in prompt or "pipeline-design" in prompt.lower()
        assert "Databricks" in prompt
        assert "Fabric" in prompt

    def test_kb_injection_with_invalid_domain_ignores_gracefully(self, tmp_path):
        """Domínios inválidos no kb_domains são silenciosamente ignorados."""
        from agents.loader import _load_kb_indexes

        result = _load_kb_indexes(["dominio-inexistente"], kb_base_dir=tmp_path)
        assert result == ""

    def test_load_kb_indexes_returns_empty_for_empty_list(self):
        """Lista vazia de kb_domains retorna string vazia."""
        from agents.loader import _load_kb_indexes

        result = _load_kb_indexes([])
        assert result == ""


# ─── Testes de Cache Prefix (Ch. 9 — Fork Agents & Prompt Cache) ─────────────


class TestCachePrefix:
    """
    Testes para o prefixo de cache compartilhado.

    Invariante crítico: o prefixo deve ser byte-idêntico em TODOS os agentes.
    Qualquer diferença de um único byte invalida o cache para aquele agente.
    """

    def test_load_cache_prefix_returns_string(self):
        """_load_cache_prefix deve retornar uma string não-vazia."""
        from agents.loader import _load_cache_prefix

        prefix = _load_cache_prefix()
        assert isinstance(prefix, str)
        assert len(prefix) > 0

    def test_load_cache_prefix_missing_file_returns_empty(self, tmp_path):
        """Se o arquivo não existe, retorna string vazia sem lançar exceção."""
        from agents.loader import _load_cache_prefix

        nonexistent = tmp_path / "nao_existe.md"
        result = _load_cache_prefix(nonexistent)
        assert result == ""

    def test_load_cache_prefix_content_is_stable(self):
        """Duas chamadas seguidas devem retornar bytes idênticos."""
        from agents.loader import _load_cache_prefix

        first = _load_cache_prefix()
        second = _load_cache_prefix()
        assert first == second, "Cache prefix não é determinístico — contém conteúdo dinâmico?"

    def test_all_agents_share_identical_prefix(self):
        """
        INVARIANTE CENTRAL: todos os agentes devem ter o MESMO prefixo no início do prompt.

        Se qualquer agente tiver um prefixo diferente, o cache de prompt da API
        do Claude não será ativado para aquele agente.
        """
        from agents.loader import _load_cache_prefix

        agents = load_all_agents(inject_cache_prefix=True)
        prefix = _load_cache_prefix()

        assert prefix, "Cache prefix está vazio — cache sharing não vai funcionar"

        for name, agent in agents.items():
            assert agent.prompt.startswith(prefix), (
                f"Agente '{name}' não começa com o cache prefix esperado.\n"
                f"Esperado início: {prefix[:80]!r}...\n"
                f"Prompt atual início: {agent.prompt[:80]!r}..."
            )

    def test_prefix_separator_present_between_prefix_and_body(self):
        """O separador '---' deve estar presente entre o prefixo e o corpo do agente."""
        from agents.loader import _load_cache_prefix, _CACHE_PREFIX_SEPARATOR

        agents = load_all_agents(inject_cache_prefix=True)
        prefix = _load_cache_prefix()

        for name, agent in agents.items():
            # O separador deve aparecer logo após o prefixo
            expected_start = prefix + _CACHE_PREFIX_SEPARATOR
            assert agent.prompt.startswith(expected_start), (
                f"Agente '{name}': separador ausente entre prefixo e corpo."
            )

    def test_inject_cache_prefix_false_omits_prefix(self, tmp_path):
        """Com inject_cache_prefix=False, o prompt não deve conter o prefixo."""
        from agents.loader import _load_cache_prefix

        prefix = _load_cache_prefix()
        agents_without = load_all_agents(inject_cache_prefix=False)

        for name, agent in agents_without.items():
            assert not agent.prompt.startswith(prefix), (
                f"Agente '{name}' tem prefixo mesmo com inject_cache_prefix=False."
            )

    def test_inject_cache_prefix_default_is_true(self):
        """O padrão de inject_cache_prefix deve ser True (cache ativado por padrão)."""
        from agents.loader import _load_cache_prefix

        prefix = _load_cache_prefix()
        # load_all_agents() sem argumentos deve incluir o prefixo
        agents_default = load_all_agents()

        for name, agent in agents_default.items():
            assert agent.prompt.startswith(prefix), (
                f"Agente '{name}': inject_cache_prefix=True deveria ser o padrão."
            )

    def test_prefix_length_is_cache_worthy(self):
        """
        O prefixo deve ter comprimento suficiente para justificar o cache.

        O Claude API cria cache a partir de ~1024 tokens (~800 chars).
        Um prefixo muito curto não seria cacheado de forma eficiente.
        """
        from agents.loader import _load_cache_prefix

        prefix = _load_cache_prefix()
        assert len(prefix) >= 500, (
            f"Cache prefix muito curto ({len(prefix)} chars). "
            "Prefixos abaixo de ~800 chars podem não ser cacheados pela API."
        )

    def test_prefix_contains_no_dynamic_content(self):
        """
        O prefixo NÃO deve conter marcadores que mudam entre execuções.

        Timestamps, IDs de sessão ou qualquer conteúdo variável invalida o cache.
        """
        from agents.loader import _load_cache_prefix
        import re

        prefix = _load_cache_prefix()

        # Padrões suspeitos de conteúdo dinâmico
        dynamic_patterns = [
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}",  # ISO timestamp
            r"session[_-]id\s*[:=]",  # session ID
            r"request[_-]id\s*[:=]",  # request ID
        ]
        for pattern in dynamic_patterns:
            assert not re.search(pattern, prefix, re.IGNORECASE), (
                f"Cache prefix contém possível conteúdo dinâmico (padrão: {pattern!r}). "
                "Isso invalidaria o cache da API do Claude."
            )

    def test_custom_prefix_path_is_used(self, tmp_path):
        """Deve ser possível fornecer um arquivo de prefixo alternativo."""
        custom_prefix_file = tmp_path / "custom_prefix.md"
        custom_prefix_file.write_text("# Prefixo Custom\n\nConteúdo alternativo.", encoding="utf-8")

        # Cria um agente de teste simples
        agent_file = tmp_path / "test-agent.md"
        agent_file.write_text(
            '---\nname: test-agent\ndescription: "Agente de teste."\n'
            "model: claude-sonnet-4-6\ntools: [Read]\n---\n# Body\nConteúdo.",
            encoding="utf-8",
        )

        from agents.loader import load_agent

        _, agent = load_agent(
            agent_file,
            inject_cache_prefix=True,
            cache_prefix_path=custom_prefix_file,
        )
        assert agent.prompt.startswith("# Prefixo Custom"), (
            "Prefixo alternativo não foi usado corretamente."
        )

"""
Bateria de Testes Funcionais — Data Agents v8.x

Cobre 10+ cenários críticos introduzidos ou impactados pelas mudanças:
  1. DOMA Renaming — nenhuma ocorrência de "BMAD" em arquivos de código
  2. CommandResult usa doma_prompt / doma_mode (não mais bmad_*)
  3. Party Mode — parse de argumentos (flags, agentes explícitos, padrão)
  4. Party Mode — grupos temáticos estão completos e com agentes válidos
  5. Party Mode — command /party registrado no registry
  6. Party Mode — personas cobertas para todos os agentes dos grupos
  7. Workflow Context Cache — diretório output/workflow-context existe
  8. Workflow Context Cache — instrução W8 presente em collaboration-workflows.md
  9. Workflow Context Cache — instrução "Context Cache" no supervisor_prompt.py
 10. Supervisor prompt sem referência BMAD — usa DOMA
 11. Integridade do registry: /party é internal e sem agente alvo
 12. UI consistency: ui/chainlit_app.py usa doma_mode/doma_prompt
 13. Import health: commands/party.py importa corretamente sem erros
 14. Party Mode — parse retorna query correta em cada modo de invocação
 15. Tiers de agentes do Party Mode batem com o registry real
"""

from __future__ import annotations

from pathlib import Path

import pytest

# ── Constantes de caminho ────────────────────────────────────────────────────

ROOT = Path(__file__).parent.parent


# ══════════════════════════════════════════════════════════════════════════════
# TESTE 1 — DOMA Renaming: nenhum "BMAD" em arquivos Python do projeto
# ══════════════════════════════════════════════════════════════════════════════
class TestDOMARenamingNoBMADInCode:
    """BMAD não deve mais existir em nenhum arquivo .py do projeto."""

    PY_FILES_TO_CHECK = [
        "commands/parser.py",
        "commands/party.py",
        "main.py",
        "agents/supervisor.py",
        "agents/prompts/supervisor_prompt.py",
        "ui/chainlit_app.py",
        "hooks/cost_guard_hook.py",
        "monitoring/app.py",
        "tests/test_commands.py",
    ]

    @pytest.mark.parametrize("rel_path", PY_FILES_TO_CHECK)
    def test_no_bmad_string_in_file(self, rel_path):
        """Arquivo não deve conter a string 'BMAD' (case-sensitive)."""
        path = ROOT / rel_path
        if not path.exists():
            pytest.skip(f"Arquivo não encontrado: {rel_path}")
        content = path.read_text(encoding="utf-8")
        occurrences = [i for i, line in enumerate(content.splitlines(), 1) if "BMAD" in line]
        assert not occurrences, f"'{rel_path}' ainda contém 'BMAD' nas linhas: {occurrences[:5]}"


# ══════════════════════════════════════════════════════════════════════════════
# TESTE 2 — CommandResult usa doma_prompt / doma_mode
# ══════════════════════════════════════════════════════════════════════════════
class TestCommandResultFieldNames:
    """CommandResult deve ter doma_prompt e doma_mode, não bmad_*."""

    def test_command_result_has_doma_prompt(self):
        from commands.parser import CommandResult
        import dataclasses

        field_names = {f.name for f in dataclasses.fields(CommandResult)}
        assert "doma_prompt" in field_names, "CommandResult deve ter campo 'doma_prompt'"
        assert "bmad_prompt" not in field_names, "Campo 'bmad_prompt' não deve mais existir"

    def test_command_result_has_doma_mode(self):
        from commands.parser import CommandResult
        import dataclasses

        field_names = {f.name for f in dataclasses.fields(CommandResult)}
        assert "doma_mode" in field_names, "CommandResult deve ter campo 'doma_mode'"
        assert "bmad_mode" not in field_names, "Campo 'bmad_mode' não deve mais existir"

    def test_parse_sql_returns_doma_fields(self):
        from commands.parser import parse_command

        result = parse_command("/sql SELECT 1")
        assert result is not None
        assert result.doma_mode == "express"
        assert "sql-expert" in result.doma_prompt
        assert "DOMA EXPRESS" in result.doma_prompt

    def test_parse_plan_returns_full_mode(self):
        from commands.parser import parse_command

        result = parse_command("/plan criar pipeline Medallion")
        assert result is not None
        assert result.doma_mode == "full"

    def test_parse_health_returns_internal_mode(self):
        from commands.parser import parse_command

        result = parse_command("/health")
        assert result is not None
        assert result.doma_mode == "internal"


# ══════════════════════════════════════════════════════════════════════════════
# TESTE 3 — Party Mode: parse de argumentos
# ══════════════════════════════════════════════════════════════════════════════
class TestPartyModeArgParsing:
    """parse_party_args deve extrair corretamente agentes e query."""

    def test_default_group_no_flag(self):
        from commands.party import parse_party_args, PARTY_GROUPS

        agents, query = parse_party_args("/party qual a diferença entre Delta Lake e Parquet?")
        assert agents == PARTY_GROUPS["default"]
        assert "Delta Lake" in query

    def test_quality_flag(self):
        from commands.party import parse_party_args, PARTY_GROUPS

        agents, query = parse_party_args("/party --quality como validar dados incrementais?")
        assert agents == PARTY_GROUPS["quality"]
        assert "incrementais" in query

    def test_arch_flag(self):
        from commands.party import parse_party_args, PARTY_GROUPS

        agents, query = parse_party_args("/party --arch descreva a arquitetura Medallion")
        assert agents == PARTY_GROUPS["arch"]
        assert "Medallion" in query

    def test_full_flag(self):
        from commands.party import parse_party_args, PARTY_GROUPS

        agents, query = parse_party_args("/party --full explique o Unity Catalog")
        assert agents == PARTY_GROUPS["full"]
        assert "Unity Catalog" in query

    def test_explicit_agents(self):
        from commands.party import parse_party_args

        agents, query = parse_party_args("/party sql-expert spark-expert analise este schema")
        assert "sql-expert" in agents
        assert "spark-expert" in agents
        assert "analise este schema" in query

    def test_empty_query_returns_empty_string(self):
        from commands.party import parse_party_args

        agents, query = parse_party_args("/party")
        assert query == ""
        assert len(agents) > 0  # grupo padrão

    def test_default_group_has_three_agents(self):
        from commands.party import PARTY_GROUPS

        assert len(PARTY_GROUPS["default"]) == 3

    def test_full_group_has_at_least_six_agents(self):
        from commands.party import PARTY_GROUPS

        assert len(PARTY_GROUPS["full"]) >= 6


# ══════════════════════════════════════════════════════════════════════════════
# TESTE 4 — Party Mode: grupos temáticos e agentes válidos
# ══════════════════════════════════════════════════════════════════════════════
class TestPartyModeGroups:
    """Todos os agentes nos grupos do Party Mode devem existir no registry."""

    VALID_AGENTS = {
        "sql-expert",
        "spark-expert",
        "pipeline-architect",
        "python-expert",
        "migration-expert",
        "data-quality-steward",
        "governance-auditor",
        "semantic-modeler",
        "dbt-expert",
        "business-analyst",
        "geral",
    }

    def test_all_group_agents_are_valid(self):
        from commands.party import PARTY_GROUPS

        for group_name, agents in PARTY_GROUPS.items():
            for agent in agents:
                assert agent in self.VALID_AGENTS, (
                    f"Grupo '{group_name}' contém agente inválido: '{agent}'"
                )

    def test_quality_group_has_data_quality_steward(self):
        from commands.party import PARTY_GROUPS

        assert "data-quality-steward" in PARTY_GROUPS["quality"]

    def test_quality_group_has_governance_auditor(self):
        from commands.party import PARTY_GROUPS

        assert "governance-auditor" in PARTY_GROUPS["quality"]

    def test_default_group_has_pipeline_architect(self):
        from commands.party import PARTY_GROUPS

        assert "pipeline-architect" in PARTY_GROUPS["default"]

    def test_no_duplicate_agents_in_any_group(self):
        from commands.party import PARTY_GROUPS

        for group_name, agents in PARTY_GROUPS.items():
            assert len(agents) == len(set(agents)), (
                f"Grupo '{group_name}' tem agentes duplicados: {agents}"
            )


# ══════════════════════════════════════════════════════════════════════════════
# TESTE 5 — Party Mode: /party registrado no COMMAND_REGISTRY
# ══════════════════════════════════════════════════════════════════════════════
class TestPartyCommandInRegistry:
    """/party deve estar presente e bem configurado no COMMAND_REGISTRY."""

    def test_party_in_registry(self):
        from commands.parser import COMMAND_REGISTRY

        assert "party" in COMMAND_REGISTRY, "/party não encontrado no COMMAND_REGISTRY"

    def test_party_is_internal_mode(self):
        from commands.parser import COMMAND_REGISTRY

        assert COMMAND_REGISTRY["party"].doma_mode == "internal"

    def test_party_has_no_agent(self):
        from commands.parser import COMMAND_REGISTRY

        assert COMMAND_REGISTRY["party"].agent is None, (
            "/party não deve ter agente alvo (é tratado diretamente no CLI)"
        )

    def test_party_parse_returns_correct_command(self):
        from commands.parser import parse_command

        result = parse_command("/party teste query")
        assert result is not None
        assert result.command == "/party"
        assert result.doma_mode == "internal"

    def test_party_appears_in_help_text(self):
        from commands.parser import get_help_text

        help_text = get_help_text()
        assert "/party" in help_text


# ══════════════════════════════════════════════════════════════════════════════
# TESTE 6 — Party Mode: personas cobertas para todos os agentes dos grupos
# ══════════════════════════════════════════════════════════════════════════════
class TestPartyModePersonas:
    """Todos os agentes nos grupos default/quality/arch/full devem ter persona definida."""

    def test_all_default_agents_have_persona(self):
        from commands.party import PARTY_GROUPS, AGENT_PERSONAS

        for agent in PARTY_GROUPS["default"]:
            assert agent in AGENT_PERSONAS, (
                f"Agente '{agent}' do grupo 'default' sem persona em AGENT_PERSONAS"
            )

    def test_all_quality_agents_have_persona(self):
        from commands.party import PARTY_GROUPS, AGENT_PERSONAS

        for agent in PARTY_GROUPS["quality"]:
            assert agent in AGENT_PERSONAS, (
                f"Agente '{agent}' do grupo 'quality' sem persona em AGENT_PERSONAS"
            )

    def test_all_full_agents_have_persona(self):
        from commands.party import PARTY_GROUPS, AGENT_PERSONAS

        for agent in PARTY_GROUPS["full"]:
            assert agent in AGENT_PERSONAS, (
                f"Agente '{agent}' do grupo 'full' sem persona em AGENT_PERSONAS"
            )

    def test_all_personas_mention_data_engineering(self):
        from commands.party import AGENT_PERSONAS

        keywords = [
            "Databricks",
            "Fabric",
            "Spark",
            "SQL",
            "dados",
            "pipeline",
            "qualidade",
            "governança",
            "semântica",
            "DAX",
            "Delta",
        ]
        for agent, persona in AGENT_PERSONAS.items():
            has_keyword = any(kw.lower() in persona.lower() for kw in keywords)
            assert has_keyword, (
                f"Persona do agente '{agent}' não menciona nenhum termo de Engenharia de Dados"
            )

    def test_all_personas_instruct_language(self):
        from commands.party import AGENT_PERSONAS

        for agent, persona in AGENT_PERSONAS.items():
            p = persona.lower()
            instructs_language = (
                "português" in p or "brasileiro" in p or "english" in p or "en-us" in p
            )
            assert instructs_language, f"Persona de '{agent}' não instrui idioma de resposta"


# ══════════════════════════════════════════════════════════════════════════════
# TESTE 7 — Workflow Context Cache: diretório existe
# ══════════════════════════════════════════════════════════════════════════════
class TestWorkflowContextCacheDirectory:
    """output/workflow-context/ deve existir no projeto."""

    def test_workflow_context_dir_exists(self):
        cache_dir = ROOT / "output" / "workflow-context"
        assert cache_dir.exists(), (
            "Diretório 'output/workflow-context/' não encontrado. "
            "Execute: mkdir -p output/workflow-context"
        )
        assert cache_dir.is_dir(), "'output/workflow-context' existe mas não é um diretório"


# ══════════════════════════════════════════════════════════════════════════════
# TESTE 8 — Workflow Context Cache: regra W8 em collaboration-workflows.md
# ══════════════════════════════════════════════════════════════════════════════
class TestWorkflowContextCacheKB:
    """kb/collaboration-workflows.md deve ter a regra W8 sobre Context Cache."""

    def test_w8_rule_present(self):
        kb_file = ROOT / "kb" / "collaboration-workflows.md"
        assert kb_file.exists(), "kb/collaboration-workflows.md não encontrado"
        content = kb_file.read_text(encoding="utf-8")
        assert "W8" in content, "Regra W8 não encontrada em collaboration-workflows.md"

    def test_w8_mentions_workflow_context(self):
        kb_file = ROOT / "kb" / "collaboration-workflows.md"
        content = kb_file.read_text(encoding="utf-8")
        assert "workflow-context" in content.lower() or "Context Cache" in content, (
            "Regra W8 deve mencionar 'workflow-context' ou 'Context Cache'"
        )

    def test_doma_party_mode_reference(self):
        """A referência ao Party Mode deve usar DOMA, não BMAD."""
        kb_file = ROOT / "kb" / "collaboration-workflows.md"
        content = kb_file.read_text(encoding="utf-8")
        assert "DOMA Party Mode" in content, "Referência ao Party Mode deve ser 'DOMA Party Mode'"
        assert "BMAD Party Mode" not in content, (
            "'BMAD Party Mode' ainda presente — renaming incompleto"
        )


# ══════════════════════════════════════════════════════════════════════════════
# TESTE 9 — Workflow Context Cache: instrução no supervisor_prompt.py
# ══════════════════════════════════════════════════════════════════════════════
class TestWorkflowContextCacheSupervisorPrompt:
    """supervisor_prompt.py deve conter a instrução de Context Cache."""

    def _get_prompt(self) -> str:
        path = ROOT / "agents" / "prompts" / "supervisor_prompt.py"
        return path.read_text(encoding="utf-8")

    def test_context_cache_instruction_present(self):
        content = self._get_prompt()
        assert "Workflow Context Cache" in content, (
            "Instrução 'Workflow Context Cache' não encontrada em supervisor_prompt.py"
        )

    def test_context_cache_mentions_output_dir(self):
        content = self._get_prompt()
        assert "output/workflow-context" in content, (
            "supervisor_prompt.py deve mencionar o diretório 'output/workflow-context'"
        )

    def test_context_cache_covers_all_workflows(self):
        content = self._get_prompt()
        # O prompt usa notação de range "WF-01 a WF-05" — verifica a presença da cobertura
        # seja via lista explícita ou via range
        covers_all = (
            (
                "WF-01" in content
                and "WF-02" in content
                and "WF-03" in content
                and "WF-04" in content
                and "WF-05" in content
            )
            or ("WF-01 a WF-05" in content)
            or ("WF-01 to WF-05" in content)
        )
        assert covers_all, (
            "supervisor_prompt.py deve mencionar todos os workflows WF-01 a WF-05 "
            "(seja individualmente, via range 'WF-01 a WF-05' ou 'WF-01 to WF-05')"
        )

    def test_context_cache_instructs_read_tool(self):
        content = self._get_prompt()
        assert "Read()" in content, (
            "Instrução de Context Cache deve orientar agentes a usar 'Read()'"
        )


# ══════════════════════════════════════════════════════════════════════════════
# TESTE 10 — Supervisor prompt usa DOMA (não BMAD)
# ══════════════════════════════════════════════════════════════════════════════
class TestSupervisorPromptUsesDOMA:
    """supervisor_prompt.py deve referenciar DOMA, não BMAD."""

    def _get_prompt(self) -> str:
        path = ROOT / "agents" / "prompts" / "supervisor_prompt.py"
        return path.read_text(encoding="utf-8")

    def test_no_bmad_string(self):
        content = self._get_prompt()
        lines_with_bmad = [
            (i + 1, line) for i, line in enumerate(content.splitlines()) if "BMAD" in line
        ]
        assert not lines_with_bmad, (
            f"supervisor_prompt.py ainda contém 'BMAD' nas linhas: "
            f"{[ln for ln, _ in lines_with_bmad]}"
        )

    def test_doma_present(self):
        content = self._get_prompt()
        assert "DOMA" in content, "supervisor_prompt.py deve mencionar 'DOMA'"

    def test_protocolo_uses_doma(self):
        content = self._get_prompt()
        assert "KB-FIRST + DOMA" in content, "Cabeçalho do protocolo deve ser 'KB-FIRST + DOMA'"

    def test_formato_resposta_uses_doma(self):
        content = self._get_prompt()
        assert "FORMATO DE RESPOSTA (DOMA)" in content or "RESPONSE FORMAT (DOMA)" in content, (
            "Seção de formato de resposta deve ser '# FORMATO DE RESPOSTA (DOMA)' ou '# RESPONSE FORMAT (DOMA)'"
        )

    def test_intake_uses_doma(self):
        content = self._get_prompt()
        assert "[DOMA Intake]" in content, "Formato de intake deve ser '[DOMA Intake]'"


# ══════════════════════════════════════════════════════════════════════════════
# TESTE 11 — Integridade do registry: /party é internal sem agente alvo
# ══════════════════════════════════════════════════════════════════════════════
class TestRegistryIntegrity:
    """O registry completo deve estar íntegro após as mudanças."""

    def test_all_commands_use_doma_mode(self):
        from commands.parser import COMMAND_REGISTRY
        import dataclasses

        for name, definition in COMMAND_REGISTRY.items():
            fields = {f.name for f in dataclasses.fields(definition)}
            assert "doma_mode" in fields, f"Comando '/{name}' não tem campo 'doma_mode'"
            assert "bmad_mode" not in fields, f"Comando '/{name}' ainda tem campo 'bmad_mode'"

    def test_all_express_commands_have_doma_express_in_prompt(self):
        from commands.parser import COMMAND_REGISTRY

        express_commands = [
            name for name, d in COMMAND_REGISTRY.items() if d.doma_mode == "express"
        ]
        for name in express_commands:
            definition = COMMAND_REGISTRY[name]
            assert (
                "DOMA EXPRESS" in definition.prompt_template or "DOMA" in definition.prompt_template
            ), f"Comando '/{name}' (express) deve ter 'DOMA' no prompt_template"

    def test_brief_command_has_doma_intake_in_prompt(self):
        from commands.parser import COMMAND_REGISTRY

        assert "DOMA INTAKE" in COMMAND_REGISTRY["brief"].prompt_template

    def test_plan_command_has_doma_passo_1_in_prompt(self):
        from commands.parser import COMMAND_REGISTRY

        assert "DOMA Passo 1" in COMMAND_REGISTRY["plan"].prompt_template

    def test_total_commands_count(self):
        """Verifica que o /party foi adicionado sem remover nenhum command existente."""
        from commands.parser import COMMAND_REGISTRY

        # Os 13 originais + /party = 14
        expected_minimum = 14
        assert len(COMMAND_REGISTRY) >= expected_minimum, (
            f"Registry tem {len(COMMAND_REGISTRY)} comandos, esperado >= {expected_minimum}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# TESTE 12 — UI consistency: chainlit_app.py usa doma_*
# ══════════════════════════════════════════════════════════════════════════════
class TestUIConsistency:
    """Arquivos de UI devem usar doma_mode e doma_prompt, não bmad_*."""

    @pytest.mark.parametrize("rel_path", ["ui/chainlit_app.py"])
    def test_no_bmad_prompt_in_ui(self, rel_path):
        path = ROOT / rel_path
        if not path.exists():
            pytest.skip(f"Arquivo não encontrado: {rel_path}")
        content = path.read_text(encoding="utf-8")
        assert "bmad_prompt" not in content, f"'{rel_path}' ainda usa 'bmad_prompt'"
        assert "bmad_mode" not in content, f"'{rel_path}' ainda usa 'bmad_mode'"

    def test_chainlit_uses_doma_mode(self):
        path = ROOT / "ui" / "chainlit_app.py"
        if not path.exists():
            pytest.skip("ui/chainlit_app.py não encontrado")
        content = path.read_text(encoding="utf-8")
        assert "doma_mode" in content, "ui/chainlit_app.py deve usar 'doma_mode'"

    def test_chainlit_badge_uses_doma(self):
        path = ROOT / "ui" / "chainlit_app.py"
        if not path.exists():
            pytest.skip("ui/chainlit_app.py não encontrado")
        content = path.read_text(encoding="utf-8")
        assert "DOMA Full" in content or "DOMA Express" in content, (
            "ui/chainlit_app.py deve exibir badges 'DOMA Full' / 'DOMA Express'"
        )


# ══════════════════════════════════════════════════════════════════════════════
# TESTE 13 — Import health: commands/party.py importa sem erros
# ══════════════════════════════════════════════════════════════════════════════
class TestPartyModuleImport:
    """commands/party.py deve importar corretamente e exportar os símbolos necessários."""

    def test_party_module_imports_without_error(self):
        try:
            import commands.party as party_module  # noqa: F401
        except ImportError as e:
            pytest.fail(f"commands/party.py falhou ao importar: {e}")

    def test_party_module_exports_run_party_query(self):
        from commands.party import run_party_query

        assert callable(run_party_query)

    def test_party_module_exports_parse_party_args(self):
        from commands.party import parse_party_args

        assert callable(parse_party_args)

    def test_party_module_exports_party_groups(self):
        from commands.party import PARTY_GROUPS

        assert isinstance(PARTY_GROUPS, dict)
        assert len(PARTY_GROUPS) > 0

    def test_party_module_exports_agent_personas(self):
        from commands.party import AGENT_PERSONAS

        assert isinstance(AGENT_PERSONAS, dict)
        assert len(AGENT_PERSONAS) > 0


# ══════════════════════════════════════════════════════════════════════════════
# TESTE 14 — Party Mode: parse retorna query correta em cada modo
# ══════════════════════════════════════════════════════════════════════════════
class TestPartyModeQueryExtraction:
    """Query extraída pelo parse_party_args deve ser precisa em cada modo."""

    def test_default_preserves_full_query(self):
        from commands.party import parse_party_args

        _, query = parse_party_args("/party explique Delta Lake em detalhes")
        assert query == "explique Delta Lake em detalhes"

    def test_quality_flag_removes_flag_from_query(self):
        from commands.party import parse_party_args

        _, query = parse_party_args("/party --quality valide os dados de vendas")
        assert "--quality" not in query
        assert "valide os dados de vendas" == query

    def test_arch_flag_removes_flag_from_query(self):
        from commands.party import parse_party_args

        _, query = parse_party_args("/party --arch pipeline cross-platform")
        assert "--arch" not in query
        assert "pipeline cross-platform" == query

    def test_explicit_agents_removes_agent_names_from_query(self):
        from commands.party import parse_party_args

        _, query = parse_party_args("/party sql-expert como otimizar queries no Databricks?")
        assert "sql-expert" not in query
        assert "como otimizar queries no Databricks?" == query

    def test_multi_word_query_preserved(self):
        from commands.party import parse_party_args

        long_query = "qual é a melhor estratégia de particionamento para tabelas Delta com bilhões de registros?"
        _, query = parse_party_args(f"/party {long_query}")
        assert query == long_query


# ══════════════════════════════════════════════════════════════════════════════
# TESTE 15 — Tiers dos agentes do Party Mode batem com registry real
# ══════════════════════════════════════════════════════════════════════════════
class TestPartyModeAgentTiers:
    """Agentes do Party Mode devem existir no registry e ter tier correto."""

    def test_party_agents_exist_in_registry(self):
        from commands.party import PARTY_GROUPS
        from agents.loader import load_all_agents

        agents = load_all_agents()
        all_party_agents = set()
        for group in PARTY_GROUPS.values():
            all_party_agents.update(group)

        for agent_name in all_party_agents:
            assert agent_name in agents, (
                f"Agente do Party Mode '{agent_name}' não encontrado no registry"
            )

    def test_party_default_agents_have_valid_prompts(self):
        """Agentes do grupo default devem ter prompts completos no registry."""
        from commands.party import PARTY_GROUPS
        from agents.loader import load_all_agents

        agents = load_all_agents()
        for agent_name in PARTY_GROUPS["default"]:
            agent = agents[agent_name]
            assert len(agent.prompt) > 200, (
                f"Agente '{agent_name}' tem prompt muito curto: {len(agent.prompt)} chars"
            )

    def test_party_quality_agents_are_tier_2(self):
        """Agentes do grupo quality devem ser T2 no registry."""
        from agents.loader import _parse_frontmatter, AGENTS_REGISTRY_DIR
        from commands.party import PARTY_GROUPS

        for agent_name in PARTY_GROUPS["quality"]:
            path = AGENTS_REGISTRY_DIR / f"{agent_name}.md"
            if not path.exists():
                continue
            content = path.read_text(encoding="utf-8")
            meta, _ = _parse_frontmatter(content)
            tier = meta.get("tier", "")
            assert tier == "T2", (
                f"Agente '{agent_name}' do grupo quality deveria ser T2, é '{tier}'"
            )

    def test_party_default_core_agents_are_tier_1(self):
        """sql-expert, spark-expert e pipeline-architect devem ser T1."""
        from agents.loader import _parse_frontmatter, AGENTS_REGISTRY_DIR

        tier1_in_default = ["sql-expert", "spark-expert", "pipeline-architect"]
        for agent_name in tier1_in_default:
            path = AGENTS_REGISTRY_DIR / f"{agent_name}.md"
            content = path.read_text(encoding="utf-8")
            meta, _ = _parse_frontmatter(content)
            tier = meta.get("tier", "")
            assert tier == "T1", (
                f"Agente '{agent_name}' do grupo default deveria ser T1, é '{tier}'"
            )

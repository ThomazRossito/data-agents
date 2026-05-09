"""Testes do parser de slash commands."""

from commands.parser import parse_command, get_help_text, COMMAND_REGISTRY


class TestParseCommand:
    """Testes para o parsing de slash commands."""

    def test_sql_command(self):
        result = parse_command("/sql SELECT * FROM tabela")
        assert result is not None
        assert result.command == "/sql"
        assert result.agent == "databricks-engineer"
        assert result.doma_mode == "express"
        assert "databricks-engineer" in result.doma_prompt

    def test_spark_command(self):
        result = parse_command("/spark Crie um DataFrame com filtro")
        assert result is not None
        assert result.command == "/spark"
        assert result.agent == "databricks-engineer"
        assert result.doma_mode == "express"

    def test_pipeline_command(self):
        result = parse_command("/pipeline Crie um pipeline Medallion")
        assert result is not None
        assert result.command == "/pipeline"
        assert result.agent == "databricks-engineer"
        assert result.doma_mode == "express"

    def test_fabric_command(self):
        result = parse_command("/fabric Crie um Lakehouse com Direct Lake")
        assert result is not None
        assert result.command == "/fabric"
        assert result.agent == "fabric-engineer"
        assert result.doma_mode == "express"
        assert "Fabric" in result.doma_prompt

    def test_fabric_semantic_model_routes_to_fabric_engineer(self):
        """Semantic Model tasks devem ser roteadas para fabric-engineer."""
        result = parse_command("/fabric analise o semantic model do microsoft fabric")
        assert result is not None
        assert result.command == "/fabric"
        assert result.agent == "fabric-engineer"
        assert "fabric-engineer" in result.doma_prompt
        assert "analise o semantic model do microsoft fabric" in result.doma_prompt

    def test_fabric_command_includes_task_in_prompt(self):
        """O prompt do /fabric deve incluir a tarefa do usuário."""
        result = parse_command("/fabric crie medidas DAX para o modelo Power BI")
        assert result is not None
        assert result.agent == "fabric-engineer"
        assert "fabric-engineer" in result.doma_prompt
        assert "crie medidas DAX para o modelo Power BI" in result.doma_prompt

    def test_fabric_pipeline_task_routes_to_fabric_engineer(self):
        """Tasks de pipeline no /fabric devem ir para fabric-engineer."""
        result = parse_command("/fabric crie um pipeline de ingestão Bronze")
        assert result is not None
        assert result.agent == "fabric-engineer"
        assert "fabric-engineer" in result.doma_prompt

    def test_fabric_routing_covers_direct_lake(self):
        """Direct Lake tasks devem ser roteadas para fabric-engineer."""
        result = parse_command("/fabric otimize as tabelas para Direct Lake")
        assert result is not None
        assert result.agent == "fabric-engineer"
        assert "Direct Lake" in result.doma_prompt  # task is embedded in prompt

    def test_plan_command(self):
        result = parse_command("/plan Crie um pipeline completo com SCD2")
        assert result is not None
        assert result.command == "/plan"
        assert result.agent is None
        assert result.doma_mode == "full"
        assert "PRD" in result.doma_prompt

    def test_health_command(self):
        result = parse_command("/health")
        assert result is not None
        assert result.command == "/health"
        assert result.doma_mode == "internal"
        # /health é tratado localmente — doma_prompt vazio é esperado
        assert result.agent is None

    def test_status_command(self):
        result = parse_command("/status")
        assert result is not None
        assert result.command == "/status"
        assert result.doma_mode == "internal"

    def test_review_command(self):
        result = parse_command("/review prd_pipeline.md")
        assert result is not None
        assert result.command == "/review"
        assert result.doma_mode == "internal"

    def test_quality_command(self):
        result = parse_command("/quality Valide a tabela silver_vendas")
        assert result is not None
        assert result.command == "/quality"
        assert result.agent == "data-quality-steward"
        assert result.doma_mode == "express"
        assert "data-quality-steward" in result.doma_prompt

    def test_governance_command(self):
        result = parse_command("/governance Audite acessos ao catálogo de produção")
        assert result is not None
        assert result.command == "/governance"
        assert result.agent == "governance-auditor"
        assert result.doma_mode == "express"
        assert "governance-auditor" in result.doma_prompt

    def test_semantic_command(self):
        result = parse_command("/semantic Crie modelo semântico para tabelas Gold")
        assert result is not None
        assert result.command == "/semantic"
        assert result.agent == "fabric-engineer"
        assert result.doma_mode == "express"
        assert "fabric-engineer" in result.doma_prompt

    def test_unknown_command_returns_none(self):
        result = parse_command("/unknown teste")
        assert result is None

    def test_non_command_returns_none(self):
        result = parse_command("Analise a tabela de vendas")
        assert result is None

    def test_empty_string_returns_none(self):
        result = parse_command("")
        assert result is None

    def test_command_without_args(self):
        # /status não requer args e ainda produz doma_prompt (vai ao Supervisor)
        result = parse_command("/status")
        assert result is not None
        assert result.doma_prompt  # Deve ter prompt mesmo sem args

    def test_case_insensitive_command(self):
        result = parse_command("/SQL SELECT 1")
        assert result is not None
        assert result.command == "/sql"

    def test_task_is_injected_in_prompt(self):
        result = parse_command("/sql SELECT count(*) FROM users")
        assert "SELECT count(*) FROM users" in result.doma_prompt


class TestCommandRegistry:
    """Testes para o registry de comandos."""

    def test_all_commands_have_required_fields(self):
        for name, definition in COMMAND_REGISTRY.items():
            assert definition.name == name
            assert definition.doma_mode in ("express", "full", "internal")
            assert definition.description
            assert definition.prompt_template
            assert definition.display_template

    def test_express_commands_have_agent(self):
        for name, definition in COMMAND_REGISTRY.items():
            if definition.doma_mode == "express":
                assert definition.agent is not None, f"/{name} express sem agent"

    def test_prompt_template_has_task_placeholder(self):
        for name, definition in COMMAND_REGISTRY.items():
            if definition.doma_mode in ("express", "full"):
                assert "{task}" in definition.prompt_template, (
                    f"/{name} sem {{task}} no prompt_template"
                )


class TestHelpText:
    """Testes para o texto de ajuda."""

    def test_help_text_lists_all_commands(self):
        help_text = get_help_text()
        for name in COMMAND_REGISTRY:
            assert f"/{name}" in help_text

    def test_help_text_includes_exit(self):
        help_text = get_help_text()
        assert "/exit" in help_text

    def test_help_text_includes_help(self):
        help_text = get_help_text()
        assert "/help" in help_text

"""
Testes para AgentMeta e preload_registry() em agents/loader.py (Ch. 12).

Cobre:
  - AgentMeta: estrutura de dados, campos esperados
  - preload_registry(): leitura apenas de frontmatter, sem carregar prompts
  - Tratamento de erros (arquivo inválido, frontmatter faltando)
  - Templates e arquivos com _ são ignorados
"""

from pathlib import Path


from agents.loader import AgentMeta, preload_registry


# ─── Fixture: registry temporário ────────────────────────────────────────────


def _write_agent_file(registry_dir: Path, name: str, content: str) -> Path:
    path = registry_dir / f"{name}.md"
    path.write_text(content, encoding="utf-8")
    return path


VALID_AGENT_CONTENT = """\
---
name: test-agent
description: "Agente de teste para preload."
model: claude-sonnet-4-6
tools: [Read, Grep]
tier: T2
mcp_servers: []
kb_domains: [sql-patterns]
max_turns: 10
effort: medium
---
# Test Agent
Este é o corpo do prompt que NÃO deve ser carregado no preload.
Com múltiplos parágrafos de conteúdo extenso...
"""

MINIMAL_AGENT_CONTENT = """\
---
name: minimal-agent
description: "Agente mínimo."
model: claude-haiku-3-5
tools: [Read]
---
# Minimal Agent
Corpo mínimo.
"""

INVALID_NO_NAME_CONTENT = """\
---
description: "Sem nome."
model: claude-sonnet-4-6
tools: []
---
# Sem nome
"""

INVALID_NO_FRONTMATTER = """\
# Arquivo sem frontmatter
Apenas corpo sem delimitadores ---.
"""


# ─── AgentMeta ───────────────────────────────────────────────────────────────


class TestAgentMeta:
    def test_has_expected_fields(self):
        meta = AgentMeta(
            name="test",
            description="desc",
            model="claude-sonnet-4-6",
            tier="T2",
        )
        assert meta.name == "test"
        assert meta.description == "desc"
        assert meta.model == "claude-sonnet-4-6"
        assert meta.tier == "T2"

    def test_default_lists_are_empty(self):
        meta = AgentMeta(name="x", description="d", model="m", tier="T1")
        assert meta.tools == []
        assert meta.mcp_servers == []
        assert meta.kb_domains == []

    def test_optional_fields_default_to_none(self):
        meta = AgentMeta(name="x", description="d", model="m", tier="T1")
        assert meta.max_turns is None
        assert meta.effort is None

    def test_accepts_max_turns(self):
        meta = AgentMeta(name="x", description="d", model="m", tier="T1", max_turns=15)
        assert meta.max_turns == 15

    def test_accepts_effort(self):
        meta = AgentMeta(name="x", description="d", model="m", tier="T1", effort="high")
        assert meta.effort == "high"


# ─── preload_registry ────────────────────────────────────────────────────────


class TestPreloadRegistry:
    def test_returns_dict(self, tmp_path):
        _write_agent_file(tmp_path, "test-agent", VALID_AGENT_CONTENT)
        result = preload_registry(tmp_path)
        assert isinstance(result, dict)

    def test_loads_agent_by_name(self, tmp_path):
        _write_agent_file(tmp_path, "test-agent", VALID_AGENT_CONTENT)
        result = preload_registry(tmp_path)
        assert "test-agent" in result

    def test_loaded_meta_has_correct_name(self, tmp_path):
        _write_agent_file(tmp_path, "test-agent", VALID_AGENT_CONTENT)
        meta = preload_registry(tmp_path)["test-agent"]
        assert meta.name == "test-agent"

    def test_loaded_meta_has_correct_description(self, tmp_path):
        _write_agent_file(tmp_path, "test-agent", VALID_AGENT_CONTENT)
        meta = preload_registry(tmp_path)["test-agent"]
        assert "teste" in meta.description.lower() or "test" in meta.description.lower()

    def test_loaded_meta_has_correct_model(self, tmp_path):
        _write_agent_file(tmp_path, "test-agent", VALID_AGENT_CONTENT)
        meta = preload_registry(tmp_path)["test-agent"]
        assert meta.model == "claude-sonnet-4-6"

    def test_loaded_meta_has_correct_tier(self, tmp_path):
        _write_agent_file(tmp_path, "test-agent", VALID_AGENT_CONTENT)
        meta = preload_registry(tmp_path)["test-agent"]
        assert meta.tier == "T2"

    def test_loaded_meta_has_correct_tools(self, tmp_path):
        _write_agent_file(tmp_path, "test-agent", VALID_AGENT_CONTENT)
        meta = preload_registry(tmp_path)["test-agent"]
        assert "Read" in meta.tools
        assert "Grep" in meta.tools

    def test_loaded_meta_has_max_turns(self, tmp_path):
        _write_agent_file(tmp_path, "test-agent", VALID_AGENT_CONTENT)
        meta = preload_registry(tmp_path)["test-agent"]
        assert meta.max_turns == 10

    def test_loaded_meta_has_effort(self, tmp_path):
        _write_agent_file(tmp_path, "test-agent", VALID_AGENT_CONTENT)
        meta = preload_registry(tmp_path)["test-agent"]
        assert meta.effort == "medium"

    def test_loaded_meta_has_path(self, tmp_path):
        _write_agent_file(tmp_path, "test-agent", VALID_AGENT_CONTENT)
        meta = preload_registry(tmp_path)["test-agent"]
        assert meta.path.exists()
        assert meta.path.name == "test-agent.md"

    def test_minimal_agent_loaded_without_optional_fields(self, tmp_path):
        _write_agent_file(tmp_path, "minimal-agent", MINIMAL_AGENT_CONTENT)
        result = preload_registry(tmp_path)
        assert "minimal-agent" in result
        meta = result["minimal-agent"]
        assert meta.max_turns is None
        assert meta.effort is None

    def test_ignores_files_starting_with_underscore(self, tmp_path):
        _write_agent_file(tmp_path, "_template", VALID_AGENT_CONTENT)
        result = preload_registry(tmp_path)
        assert "_template" not in result
        # Garante que o arquivo foi ignorado, não falhou
        assert len(result) == 0

    def test_ignores_agent_without_name(self, tmp_path):
        _write_agent_file(tmp_path, "no-name", INVALID_NO_NAME_CONTENT)
        result = preload_registry(tmp_path)
        assert len(result) == 0

    def test_handles_invalid_frontmatter_gracefully(self, tmp_path):
        _write_agent_file(tmp_path, "bad-file", INVALID_NO_FRONTMATTER)
        # Não deve levantar exceção — apenas ignorar o arquivo inválido
        result = preload_registry(tmp_path)
        assert isinstance(result, dict)

    def test_loads_multiple_agents(self, tmp_path):
        _write_agent_file(tmp_path, "agent-a", VALID_AGENT_CONTENT.replace("test-agent", "agent-a"))
        _write_agent_file(tmp_path, "agent-b", MINIMAL_AGENT_CONTENT)
        result = preload_registry(tmp_path)
        assert "agent-a" in result
        assert "minimal-agent" in result

    def test_empty_registry_returns_empty_dict(self, tmp_path):
        result = preload_registry(tmp_path)
        assert result == {}

    def test_uses_default_registry_dir_when_none_provided(self):
        """Sem registry_dir, usa o diretório padrão (agents/registry/)."""
        # Só verifica que não levanta exceção e retorna dict
        result = preload_registry()
        assert isinstance(result, dict)
        # O registry real deve ter pelo menos um agente
        assert len(result) > 0

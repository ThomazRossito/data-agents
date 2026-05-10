"""
Testes de descoberta de Skills no formato nativo Anthropic.

Garantem que:
  - As 5 Skills canônicas em skills/patterns/ existem com frontmatter válido (name + description)
  - _load_skills_index(["patterns"]) indexa todas elas
  - _load_skills_index não quebra com domínios inexistentes
  - Agentes com skill_domains recebem o índice injetado; sem domínios, nada é injetado
  - O campo `description` do frontmatter é usado como hint (não a primeira linha do corpo)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agents.loader import (
    SKILLS_BASE_DIR,
    _load_skills_index,
    _parse_frontmatter,
    load_all_agents,
)

PATTERN_SKILLS = [
    "data-quality",
    "pipeline-design",
    "sql-generation",
    "spark-patterns",
    "star-schema-design",
]


class TestPatternSkillsFrontmatter:
    """As 5 Skills canônicas em skills/patterns/ devem ter frontmatter válido."""

    @pytest.mark.parametrize("skill_name", PATTERN_SKILLS)
    def test_skill_file_exists(self, skill_name: str):
        path = SKILLS_BASE_DIR / "patterns" / skill_name / "SKILL.md"
        assert path.exists(), f"Skill ausente: {path}"

    @pytest.mark.parametrize("skill_name", PATTERN_SKILLS)
    def test_skill_has_name_matching_directory(self, skill_name: str):
        path = SKILLS_BASE_DIR / "patterns" / skill_name / "SKILL.md"
        metadata, _ = _parse_frontmatter(path.read_text(encoding="utf-8"))
        assert metadata.get("name") == skill_name, (
            f"{path}: frontmatter 'name' deve ser '{skill_name}', é '{metadata.get('name')}'"
        )

    @pytest.mark.parametrize("skill_name", PATTERN_SKILLS)
    def test_skill_has_non_empty_description(self, skill_name: str):
        path = SKILLS_BASE_DIR / "patterns" / skill_name / "SKILL.md"
        metadata, _ = _parse_frontmatter(path.read_text(encoding="utf-8"))
        description = metadata.get("description", "")
        assert isinstance(description, str) and len(description) >= 20, (
            f"{path}: frontmatter 'description' vazio ou muito curto ({len(description)} chars)"
        )


class TestLoadSkillsIndex:
    """_load_skills_index deve descobrir Skills no formato nativo."""

    def test_patterns_domain_indexes_all_five_skills(self):
        index = _load_skills_index(["patterns"])
        assert index, "Índice vazio para o domínio 'patterns'"
        for skill_name in PATTERN_SKILLS:
            assert f"skills/patterns/{skill_name}/SKILL.md" in index, (
                f"Skill '{skill_name}' não indexada no domínio 'patterns'"
            )

    def test_indexed_entry_uses_frontmatter_description(self):
        index = _load_skills_index(["patterns"])
        # A descrição do frontmatter deve aparecer no índice, não o título markdown.
        assert "# Skill:" not in index, (
            "Índice inclui títulos markdown (# Skill: ...) — deveria usar frontmatter description"
        )
        assert "Padrões de validação" in index, "Descrição do data-quality não encontrada no índice"

    def test_nonexistent_domain_is_silently_ignored(self, tmp_path: Path):
        result = _load_skills_index(["dominio-inexistente"], skills_base_dir=tmp_path)
        assert result == ""

    def test_empty_domain_list_returns_empty_string(self):
        assert _load_skills_index([]) == ""

    def test_multiple_domains_are_merged(self):
        index_patterns = _load_skills_index(["patterns"])
        index_combined = _load_skills_index(["patterns", "databricks"])
        # combined deve ser ao menos tão rico quanto patterns sozinho
        assert len(index_combined) >= len(index_patterns)

    def test_template_directories_are_excluded(self, tmp_path: Path):
        domain_dir = tmp_path / "domain"
        domain_dir.mkdir()
        # SKILL.md válida
        (domain_dir / "valida").mkdir()
        (domain_dir / "valida" / "SKILL.md").write_text(
            '---\nname: valida\ndescription: "Skill válida para teste."\n---\n# Body',
            encoding="utf-8",
        )
        # Template que DEVE ser excluído
        (domain_dir / "_template").mkdir()
        (domain_dir / "_template" / "SKILL.md").write_text(
            '---\nname: _template\ndescription: "Template."\n---\n# Body',
            encoding="utf-8",
        )
        (domain_dir / "TEMPLATE").mkdir()
        (domain_dir / "TEMPLATE" / "SKILL.md").write_text(
            '---\nname: TEMPLATE\ndescription: "Template uppercase."\n---\n# Body',
            encoding="utf-8",
        )

        index = _load_skills_index(["domain"], skills_base_dir=tmp_path)
        assert "domain/valida/SKILL.md" in index
        # Exclusão é por nome de diretório de skill, não por substring do path
        assert "domain/_template/SKILL.md" not in index
        assert "domain/TEMPLATE/SKILL.md" not in index


class TestSkillInjectionInAgents:
    """Agentes com skill_domains devem receber o índice injetado no prompt."""

    def test_agent_with_patterns_domain_gets_skills_injected(self):
        agents = load_all_agents(inject_skills_index=True)
        # pipeline-architect: [databricks, fabric, patterns]
        prompt = agents["pipeline-architect"].prompt
        assert "[Contexto Injetado] Skills Disponíveis" in prompt
        assert "skills/patterns/pipeline-design/SKILL.md" in prompt
        assert "skills/patterns/star-schema-design/SKILL.md" in prompt

    def test_agent_without_skill_domains_gets_no_skills_injection(self):
        agents = load_all_agents(inject_skills_index=True)
        # geral: skill_domains: [] → nenhuma injeção de skills
        prompt = agents["geral"].prompt
        assert "[Contexto Injetado] Skills Disponíveis" not in prompt

    def test_inject_skills_index_false_omits_injection(self):
        agents = load_all_agents(inject_skills_index=False)
        for name, agent in agents.items():
            assert "[Contexto Injetado] Skills Disponíveis" not in agent.prompt, (
                f"Agente '{name}': injeção de skills presente mesmo com inject_skills_index=False"
            )

    def test_no_agent_references_old_flat_skill_paths(self):
        """Nenhum prompt de agente deve mencionar os paths legados do skills/*.md."""
        agents = load_all_agents(inject_skills_index=True)
        legacy_paths = [
            "skills/data_quality.md",
            "skills/pipeline_design.md",
            "skills/sql_generation.md",
            "skills/spark_patterns.md",
            "skills/star_schema_design.md",
        ]
        for name, agent in agents.items():
            for legacy in legacy_paths:
                assert legacy not in agent.prompt, (
                    f"Agente '{name}' ainda referencia path legado: {legacy}"
                )

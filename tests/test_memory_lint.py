"""
Testes para memory/lint.py.

Cobre os 7 health checks:
  1. orphan_reference — referências a IDs inexistentes
  2. broken_supersede — cadeias de supersede quebradas
  3. stale_progress — memórias PROGRESS com confidence muito baixa
  4. empty_content — memórias sem conteúdo significativo
  5. duplicate_summary — resumos idênticos entre memórias ativas
  6. missing_index / stale_index — index.md ausente ou desatualizado
  7. tag_format / tag_singletons — tags mal formatadas
"""

from datetime import datetime, timezone, timedelta

import pytest

from memory.types import Memory, MemoryType
from memory.store import MemoryStore
from memory.lint import lint_memories, LintReport, LintIssue


# ─── Fixture ─────────────────────────────────────────────────────────


@pytest.fixture
def store(tmp_path):
    return MemoryStore(data_dir=tmp_path / "mem_data")


def _make_memory(**kwargs) -> Memory:
    defaults = {
        "type": MemoryType.ARCHITECTURE,
        "content": "Conteúdo da memória de teste com mais de 10 caracteres.",
        "summary": "Resumo único de teste",
        "tags": ["test"],
        "confidence": 1.0,
    }
    defaults.update(kwargs)
    return Memory(**defaults)


# ─── LintReport ───────────────────────────────────────────────────────


class TestLintReport:
    def test_has_errors_when_error_present(self):
        report = LintReport()
        report.issues.append(LintIssue("error", "test_check", "id1", "Mensagem"))
        assert report.has_errors is True

    def test_no_errors_when_only_warnings(self):
        report = LintReport()
        report.issues.append(LintIssue("warning", "test_check", "id1", "Aviso"))
        assert report.has_errors is False

    def test_summary_contains_counts(self):
        report = LintReport()
        report.issues.append(LintIssue("error", "c1", "id1", "msg"))
        report.issues.append(LintIssue("warning", "c2", "id2", "msg"))
        summary = report.summary
        assert "1 error" in summary
        assert "1 warning" in summary

    def test_to_markdown_contains_header(self):
        report = LintReport()
        md = report.to_markdown()
        assert "Memory Lint Report" in md

    def test_to_markdown_healthy_message(self):
        report = LintReport()
        md = report.to_markdown()
        assert "saudável" in md.lower() or "Nenhuma issue" in md

    def test_to_markdown_lists_issues(self):
        report = LintReport()
        report.issues.append(LintIssue("error", "broken_supersede", "abc", "Msg de erro"))
        md = report.to_markdown()
        assert "broken_supersede" in md
        assert "Msg de erro" in md


# ─── Check 1: orphan_reference ────────────────────────────────────────


class TestOrphanReference:
    def test_no_issue_when_reference_valid(self, store):
        mem1 = _make_memory(id="id_a")
        mem2 = _make_memory(id="id_b", related_ids=["id_a"])
        store.save(mem1)
        store.save(mem2)
        report = lint_memories(store)
        orphan_issues = [i for i in report.issues if i.check == "orphan_reference"]
        assert len(orphan_issues) == 0

    def test_reports_orphan_reference(self, store):
        mem = _make_memory(related_ids=["nonexistent_id_xyz"])
        store.save(mem)
        report = lint_memories(store)
        orphan_issues = [i for i in report.issues if i.check == "orphan_reference"]
        assert len(orphan_issues) >= 1

    def test_no_issue_with_empty_related_ids(self, store):
        mem = _make_memory(related_ids=[])
        store.save(mem)
        report = lint_memories(store)
        orphan_issues = [i for i in report.issues if i.check == "orphan_reference"]
        assert len(orphan_issues) == 0


# ─── Check 2: broken_supersede ────────────────────────────────────────


class TestBrokenSupersede:
    def test_reports_broken_supersede(self, store):
        mem = _make_memory(superseded_by="nonexistent_superseder")
        store.save(mem)
        report = lint_memories(store)
        issues = [i for i in report.issues if i.check == "broken_supersede"]
        assert len(issues) >= 1

    def test_no_issue_when_superseder_exists(self, store):
        newer = _make_memory(id="newer_id")
        older = _make_memory(id="older_id", superseded_by="newer_id")
        store.save(newer)
        store.save(older)
        report = lint_memories(store)
        issues = [i for i in report.issues if i.check == "broken_supersede"]
        assert len(issues) == 0


# ─── Check 3: stale_progress ──────────────────────────────────────────


class TestStaleProgress:
    def test_reports_stale_progress_memory(self, store):
        # Cria PROGRESS com 20 dias de idade (confidence muito baixa)
        old_created = datetime.now(timezone.utc) - timedelta(days=20)
        mem = Memory(
            type=MemoryType.PROGRESS,
            content="Progresso antigo que deveria ter decaído.",
            summary="Progresso antigo",
            tags=["task"],
            confidence=1.0,
            created_at=old_created,
        )
        store.save(mem)
        report = lint_memories(store)
        stale_issues = [i for i in report.issues if i.check == "stale_progress"]
        assert len(stale_issues) >= 1

    def test_no_issue_for_fresh_progress(self, store):
        mem = Memory(
            type=MemoryType.PROGRESS,
            content="Progresso recente ainda relevante.",
            summary="Tarefa em andamento",
            tags=["task"],
            confidence=1.0,
        )
        store.save(mem)
        report = lint_memories(store)
        stale_issues = [i for i in report.issues if i.check == "stale_progress"]
        assert len(stale_issues) == 0

    def test_no_issue_for_architecture_regardless_of_age(self, store):
        """ARCHITECTURE não tem decay → nunca fica stale."""
        mem = Memory(
            type=MemoryType.ARCHITECTURE,
            content="Decisão arquitetural permanente.",
            summary="Decisão arq antiga",
            tags=["arch"],
            confidence=1.0,
            created_at=datetime.now(timezone.utc) - timedelta(days=365),
        )
        store.save(mem)
        report = lint_memories(store)
        stale_issues = [i for i in report.issues if i.check == "stale_progress"]
        assert len(stale_issues) == 0


# ─── Check 4: empty_content ───────────────────────────────────────────


class TestEmptyContent:
    def test_reports_empty_content(self, store):
        mem = _make_memory(content="ok")  # < 10 chars
        store.save(mem)
        report = lint_memories(store)
        issues = [i for i in report.issues if i.check == "empty_content"]
        assert len(issues) >= 1

    def test_no_issue_with_adequate_content(self, store):
        mem = _make_memory(content="Este é um conteúdo com mais de 10 caracteres.")
        store.save(mem)
        report = lint_memories(store)
        issues = [i for i in report.issues if i.check == "empty_content"]
        assert len(issues) == 0


# ─── Check 5: duplicate_summary ───────────────────────────────────────


class TestDuplicateSummary:
    def test_reports_duplicate_summaries(self, store):
        mem1 = _make_memory(id="dup_1", summary="Resumo idêntico entre as duas")
        mem2 = _make_memory(id="dup_2", summary="Resumo idêntico entre as duas")
        store.save(mem1)
        store.save(mem2)
        report = lint_memories(store)
        issues = [i for i in report.issues if i.check == "duplicate_summary"]
        assert len(issues) >= 1

    def test_no_issue_for_unique_summaries(self, store):
        mem1 = _make_memory(id="u_1", summary="Primeiro resumo único")
        mem2 = _make_memory(id="u_2", summary="Segundo resumo único")
        store.save(mem1)
        store.save(mem2)
        report = lint_memories(store)
        issues = [i for i in report.issues if i.check == "duplicate_summary"]
        assert len(issues) == 0

    def test_inactive_memories_not_checked_for_dupes(self, store):
        active = _make_memory(id="active_id", summary="Resumo comum")
        inactive = _make_memory(id="inactive_id", summary="Resumo comum", confidence=0.0)
        store.save(active)
        store.save(inactive)
        report = lint_memories(store)
        issues = [i for i in report.issues if i.check == "duplicate_summary"]
        assert len(issues) == 0


# ─── Check 6: missing_index / stale_index ─────────────────────────────


class TestIndexChecks:
    def test_reports_missing_index(self, store):
        # Store vazio sem index.md
        report = lint_memories(store)
        issues = [i for i in report.issues if i.check == "missing_index"]
        assert len(issues) >= 1

    def test_no_missing_issue_when_index_present(self, store):
        mem = _make_memory()
        store.save(mem)
        store.build_index()
        report = lint_memories(store)
        issues = [i for i in report.issues if i.check == "missing_index"]
        assert len(issues) == 0

    def test_reports_stale_index_when_old(self, store, tmp_path):
        # Cria index e altera o mtime para mais de 24h atrás
        mem = _make_memory()
        store.save(mem)
        store.build_index()
        index_path = store.data_dir / "index.md"

        import os

        old_time = datetime.now(timezone.utc) - timedelta(hours=25)
        os.utime(index_path, (old_time.timestamp(), old_time.timestamp()))

        report = lint_memories(store)
        issues = [i for i in report.issues if i.check == "stale_index"]
        assert len(issues) >= 1


# ─── Check 7: tag_format / tag_singletons ─────────────────────────────


class TestTagHygiene:
    def test_reports_uppercase_tag(self, store):
        mem = _make_memory(tags=["Databricks", "pipeline"])
        store.save(mem)
        report = lint_memories(store)
        issues = [i for i in report.issues if i.check == "tag_format"]
        assert len(issues) >= 1

    def test_reports_tag_with_space(self, store):
        mem = _make_memory(tags=["my pipeline", "databricks"])
        store.save(mem)
        report = lint_memories(store)
        issues = [i for i in report.issues if i.check == "tag_format"]
        assert len(issues) >= 1

    def test_no_tag_format_issue_with_clean_tags(self, store):
        mem = _make_memory(tags=["databricks", "pipeline", "bronze"])
        store.save(mem)
        report = lint_memories(store)
        issues = [i for i in report.issues if i.check == "tag_format"]
        assert len(issues) == 0


# ─── lint_memories: stats ─────────────────────────────────────────────


class TestLintStats:
    def test_stats_total_is_correct(self, store):
        store.save(_make_memory(id="s1"))
        store.save(_make_memory(id="s2"))
        report = lint_memories(store)
        assert report.stats["total_memories"] == 2

    def test_stats_active_counts_correctly(self, store):
        store.save(_make_memory(id="a1", confidence=1.0))
        store.save(_make_memory(id="a2", confidence=0.0))
        report = lint_memories(store)
        assert report.stats["active"] == 1

    def test_empty_store_has_zero_stats(self, store):
        report = lint_memories(store)
        assert report.stats["total_memories"] == 0


# ─── lint_memories: clean store ───────────────────────────────────────


class TestCleanStore:
    def test_healthy_store_has_no_errors(self, store):
        """Um store bem configurado não deve ter erros."""
        mem = _make_memory(
            tags=["databricks", "pipeline"],
            content="Conteúdo suficientemente longo para não disparar o check de empty_content.",
            summary="Resumo único e bem definido",
        )
        store.save(mem)
        store.build_index()
        report = lint_memories(store)
        assert report.has_errors is False

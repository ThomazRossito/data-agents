"""
Testes para memory/store.py.

Cobre:
  - MemoryStore._ensure_dirs(): cria estrutura de diretórios
  - save() / load() / delete(): operações CRUD básicas
  - supersede(): cadeia de substituição de memórias
  - list_all(): filtragem por tipo, active_only, min_confidence
  - list_by_tags(): match parcial e match total
  - get_stats(): contagens por tipo
  - append_daily_log(): criação e append
  - list_daily_logs(): todos e não processados
  - build_index(): geração do index.md
"""

from datetime import datetime, timezone

import pytest

from memory.types import Memory, MemoryType
from memory.store import MemoryStore


# ─── Fixture ─────────────────────────────────────────────────────────


@pytest.fixture
def store(tmp_path):
    """MemoryStore com diretório temporário isolado."""
    return MemoryStore(data_dir=tmp_path / "memory_data")


def _make_memory(**kwargs) -> Memory:
    defaults = {
        "type": MemoryType.ARCHITECTURE,
        "content": "Conteúdo da memória de teste.",
        "summary": "Resumo de teste",
        "tags": ["test"],
        "confidence": 1.0,
    }
    defaults.update(kwargs)
    return Memory(**defaults)


# ─── _ensure_dirs ─────────────────────────────────────────────────────


class TestEnsureDirs:
    def test_creates_type_directories(self, tmp_path):
        MemoryStore(data_dir=tmp_path / "data")
        for mt in MemoryType:
            assert (tmp_path / "data" / mt.value).exists()

    def test_creates_daily_directory(self, tmp_path):
        MemoryStore(data_dir=tmp_path / "data")
        assert (tmp_path / "data" / "daily").exists()


# ─── save / load ──────────────────────────────────────────────────────


class TestSaveLoad:
    def test_save_creates_file(self, store, tmp_path):
        mem = _make_memory()
        path = store.save(mem)
        assert path.exists()

    def test_save_returns_correct_path(self, store):
        mem = _make_memory(type=MemoryType.USER)
        path = store.save(mem)
        assert mem.type.value in str(path)
        assert mem.id in str(path)

    def test_load_returns_same_memory(self, store):
        mem = _make_memory(
            type=MemoryType.ARCHITECTURE,
            content="Conteúdo específico.",
            summary="Resumo específico",
            tags=["databricks", "pipeline"],
        )
        store.save(mem)
        loaded = store.load(mem.id, MemoryType.ARCHITECTURE)
        assert loaded is not None
        assert loaded.id == mem.id
        assert loaded.content == "Conteúdo específico."
        assert loaded.summary == "Resumo específico"

    def test_load_returns_none_when_not_found(self, store):
        result = store.load("nonexistent_id", MemoryType.PROGRESS)
        assert result is None

    def test_save_updates_updated_at(self, store):
        mem = _make_memory()
        before = datetime.now(timezone.utc)
        store.save(mem)
        after = datetime.now(timezone.utc)
        assert before <= mem.updated_at <= after

    def test_save_overwrites_existing(self, store):
        mem = _make_memory(content="Original")
        store.save(mem)
        mem.content = "Atualizado"
        store.save(mem)
        loaded = store.load(mem.id, mem.type)
        assert loaded.content == "Atualizado"

    def test_tags_roundtrip(self, store):
        mem = _make_memory(tags=["alpha", "beta", "gamma"])
        store.save(mem)
        loaded = store.load(mem.id, mem.type)
        assert set(loaded.tags) == {"alpha", "beta", "gamma"}

    def test_confidence_roundtrip(self, store):
        mem = _make_memory(confidence=0.73)
        store.save(mem)
        loaded = store.load(mem.id, mem.type)
        assert abs(loaded.confidence - 0.73) < 0.001

    def test_related_ids_roundtrip(self, store):
        mem = _make_memory(related_ids=["ref1", "ref2"])
        store.save(mem)
        loaded = store.load(mem.id, mem.type)
        assert "ref1" in loaded.related_ids

    def test_superseded_by_roundtrip(self, store):
        mem = _make_memory(superseded_by="newer_abc")
        store.save(mem)
        loaded = store.load(mem.id, mem.type)
        assert loaded.superseded_by == "newer_abc"


# ─── delete ───────────────────────────────────────────────────────────


class TestDelete:
    def test_delete_removes_file(self, store):
        mem = _make_memory()
        store.save(mem)
        result = store.delete(mem.id, mem.type)
        assert result is True
        assert store.load(mem.id, mem.type) is None

    def test_delete_returns_false_when_not_found(self, store):
        result = store.delete("nonexistent", MemoryType.USER)
        assert result is False


# ─── supersede ────────────────────────────────────────────────────────


class TestSupersede:
    def test_supersede_marks_old_as_inactive(self, store):
        old = _make_memory(id="old_memory_id")
        store.save(old)
        new = _make_memory(id="new_memory_id", content="Versão atualizada.")
        store.supersede("old_memory_id", old.type, new)
        old_loaded = store.load("old_memory_id", old.type)
        assert old_loaded.superseded_by == "new_memory_id"
        assert old_loaded.confidence == 0.0

    def test_supersede_saves_new_memory(self, store):
        old = _make_memory(id="old_id")
        store.save(old)
        new = _make_memory(id="new_id")
        store.supersede("old_id", old.type, new)
        new_loaded = store.load("new_id", new.type)
        assert new_loaded is not None

    def test_supersede_adds_related_id_to_new(self, store):
        old = _make_memory(id="old_id")
        store.save(old)
        new = _make_memory(id="new_id")
        store.supersede("old_id", old.type, new)
        assert "old_id" in new.related_ids

    def test_supersede_handles_missing_old_gracefully(self, store):
        """Não deve lançar exceção se a memória antiga não existir."""
        new = _make_memory()
        result = store.supersede("nonexistent_old", MemoryType.ARCHITECTURE, new)
        assert result is not None


# ─── list_all ─────────────────────────────────────────────────────────


class TestListAll:
    def test_list_returns_saved_memories(self, store):
        mem1 = _make_memory(type=MemoryType.USER, id="uid1")
        mem2 = _make_memory(type=MemoryType.PROGRESS, id="pid1")
        store.save(mem1)
        store.save(mem2)
        all_memories = store.list_all(active_only=False)
        ids = [m.id for m in all_memories]
        assert "uid1" in ids
        assert "pid1" in ids

    def test_list_filters_by_type(self, store):
        user_mem = _make_memory(type=MemoryType.USER)
        arch_mem = _make_memory(type=MemoryType.ARCHITECTURE)
        store.save(user_mem)
        store.save(arch_mem)
        result = store.list_all(memory_type=MemoryType.USER)
        assert all(m.type == MemoryType.USER for m in result)

    def test_list_excludes_inactive_when_active_only(self, store):
        active = _make_memory(confidence=1.0)
        inactive = _make_memory(confidence=0.0)
        store.save(active)
        store.save(inactive)
        result = store.list_all(active_only=True)
        ids = [m.id for m in result]
        assert active.id in ids
        assert inactive.id not in ids

    def test_list_includes_inactive_when_not_active_only(self, store):
        inactive = _make_memory(confidence=0.0)
        store.save(inactive)
        result = store.list_all(active_only=False, min_confidence=0.0)
        ids = [m.id for m in result]
        assert inactive.id in ids

    def test_list_empty_store_returns_empty_list(self, store):
        result = store.list_all()
        assert result == []


# ─── list_by_tags ─────────────────────────────────────────────────────


class TestListByTags:
    def test_finds_memory_by_partial_tag_match(self, store):
        mem = _make_memory(tags=["databricks", "pipeline"])
        store.save(mem)
        result = store.list_by_tags(["databricks"])
        assert any(m.id == mem.id for m in result)

    def test_match_all_requires_all_tags(self, store):
        mem = _make_memory(tags=["databricks", "pipeline"])
        store.save(mem)
        # Tem databricks mas não tem bronze
        result = store.list_by_tags(["databricks", "bronze"], match_all=True)
        assert not any(m.id == mem.id for m in result)

    def test_match_all_returns_when_all_present(self, store):
        mem = _make_memory(tags=["databricks", "pipeline", "bronze"])
        store.save(mem)
        result = store.list_by_tags(["databricks", "bronze"], match_all=True)
        assert any(m.id == mem.id for m in result)

    def test_no_match_returns_empty(self, store):
        mem = _make_memory(tags=["databricks"])
        store.save(mem)
        result = store.list_by_tags(["fabric"])
        assert result == []


# ─── get_stats ────────────────────────────────────────────────────────


class TestGetStats:
    def test_stats_counts_total(self, store):
        store.save(_make_memory(type=MemoryType.USER))
        store.save(_make_memory(type=MemoryType.PROGRESS))
        stats = store.get_stats()
        assert stats["total"] == 2

    def test_stats_counts_active(self, store):
        store.save(_make_memory(confidence=1.0))
        store.save(_make_memory(confidence=0.0))
        stats = store.get_stats()
        assert stats["active"] == 1
        assert stats["superseded"] == 1

    def test_stats_has_by_type_dict(self, store):
        stats = store.get_stats()
        for mt in MemoryType:
            assert mt.value in stats["by_type"]

    def test_stats_empty_store(self, store):
        stats = store.get_stats()
        assert stats["total"] == 0
        assert stats["active"] == 0


# ─── append_daily_log ─────────────────────────────────────────────────


class TestAppendDailyLog:
    def test_creates_daily_log_file(self, store):
        path = store.append_daily_log("Conteúdo da memória.")
        assert path.exists()

    def test_log_file_named_by_date(self, store):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        path = store.append_daily_log("Teste.")
        assert today in path.name

    def test_appends_to_existing_log(self, store):
        store.append_daily_log("Primeira entrada.")
        store.append_daily_log("Segunda entrada.")
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log_path = store.data_dir / "daily" / f"{today}.md"
        content = log_path.read_text(encoding="utf-8")
        assert "Primeira entrada." in content
        assert "Segunda entrada." in content

    def test_log_has_header_on_first_creation(self, store):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        store.append_daily_log("Conteúdo.")
        log_path = store.data_dir / "daily" / f"{today}.md"
        content = log_path.read_text(encoding="utf-8")
        assert "Daily Log" in content


# ─── list_daily_logs ──────────────────────────────────────────────────


class TestListDailyLogs:
    def test_lists_all_logs(self, store):
        store.append_daily_log("Entry 1.")
        logs = store.list_daily_logs()
        assert len(logs) == 1

    def test_unprocessed_only_excludes_compiled(self, store):
        path = store.append_daily_log("Conteúdo.")
        # Simula log compilado
        with open(path, "a") as f:
            f.write("\n<!-- COMPILED 2026-01-01 -->")
        unprocessed = store.list_daily_logs(unprocessed_only=True)
        assert len(unprocessed) == 0

    def test_unprocessed_returns_non_compiled_logs(self, store):
        store.append_daily_log("Não compilado.")
        unprocessed = store.list_daily_logs(unprocessed_only=True)
        assert len(unprocessed) == 1


# ─── build_index ──────────────────────────────────────────────────────


class TestBuildIndex:
    def test_creates_index_file(self, store):
        mem = _make_memory(summary="Resumo para o index")
        store.save(mem)
        store.build_index()
        index_path = store.data_dir / "index.md"
        assert index_path.exists()

    def test_index_contains_memory_summary(self, store):
        mem = _make_memory(summary="Pipeline Medallion com 3 camadas")
        store.save(mem)
        content = store.build_index()
        assert "Pipeline Medallion com 3 camadas" in content

    def test_index_contains_memory_id(self, store):
        mem = _make_memory()
        store.save(mem)
        content = store.build_index()
        assert mem.id in content

    def test_index_empty_when_no_memories(self, store):
        content = store.build_index()
        assert "# Memory Index" in content

    def test_index_groups_by_type(self, store):
        store.save(_make_memory(type=MemoryType.USER, summary="User pref"))
        store.save(_make_memory(type=MemoryType.ARCHITECTURE, summary="Arch decision"))
        content = store.build_index()
        assert "USER" in content
        assert "ARCHITECTURE" in content

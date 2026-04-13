"""
Testes para memory/compiler.py.

Cobre:
  - _parse_daily_entries(): parse de seções de log
  - _entry_to_memory(): conversão de dict para Memory
  - _filter_contradiction_candidates(): pré-filtro de candidatos a contradição
  - _heuristic_contradiction(): fallback word-overlap
  - _sonnet_check_contradiction(): chamada Sonnet (mockada)
  - _find_contradiction(): orquestração completa (pré-filtro + Sonnet/heurística)
  - _mark_as_compiled(): marcação de log processado
  - compile_daily_logs(): pipeline completo (end-to-end)
"""

from unittest.mock import patch, MagicMock
import json

import pytest

from memory.types import Memory, MemoryType
from memory.store import MemoryStore
from memory.compiler import (
    _parse_daily_entries,
    _entry_to_memory,
    _filter_contradiction_candidates,
    _heuristic_contradiction,
    _sonnet_check_contradiction,
    _find_contradiction,
    _mark_as_compiled,
    compile_daily_logs,
)


# ─── Fixture ─────────────────────────────────────────────────────────


@pytest.fixture
def store(tmp_path):
    return MemoryStore(data_dir=tmp_path / "mem_data")


# ─── _parse_daily_entries ─────────────────────────────────────────────


class TestParseDailyEntries:
    def test_parses_single_entry(self):
        content = """# Daily Log

---

type: architecture
summary: Pipeline Bronze configurado
tags: pipeline, bronze
confidence: 1.0

Conteúdo detalhado do pipeline."""
        entries = _parse_daily_entries(content)
        assert len(entries) >= 1

    def test_parses_multiple_entries(self):
        content = """# Daily Log

---

type: architecture
summary: Entrada 1
tags: tag1

Corpo 1.

---

type: user
summary: Entrada 2
tags: tag2

Corpo 2."""
        entries = _parse_daily_entries(content)
        assert len(entries) == 2

    def test_ignores_header_section(self):
        content = """# Daily Log — 2026-04-13

---

type: feedback
summary: Feedback importante
tags: feedback

Não use SELECT *."""
        entries = _parse_daily_entries(content)
        # A seção de header não deve ser uma entrada válida
        valid = [e for e in entries if e.get("type")]
        assert len(valid) == 1

    def test_returns_empty_for_empty_log(self):
        entries = _parse_daily_entries("")
        assert entries == []

    def test_entry_has_required_fields(self):
        content = """# Daily Log

---

type: progress
summary: Tarefa em andamento
tags: pipeline

Progresso atual."""
        entries = _parse_daily_entries(content)
        valid = [e for e in entries if e.get("type") and e.get("summary")]
        assert len(valid) >= 1


# ─── _entry_to_memory ─────────────────────────────────────────────────


class TestEntryToMemory:
    def _make_entry(self, **overrides):
        base = {
            "type": "architecture",
            "summary": "Resumo da decisão",
            "content": "Corpo da memória.",
            "tags": ["databricks"],
        }
        base.update(overrides)
        return base

    def test_creates_memory_from_valid_entry(self):
        mem = _entry_to_memory(self._make_entry())
        assert mem is not None
        assert mem.type == MemoryType.ARCHITECTURE

    def test_invalid_type_returns_none(self):
        result = _entry_to_memory(self._make_entry(type="invalid_type"))
        assert result is None

    def test_tags_preserved(self):
        mem = _entry_to_memory(self._make_entry(tags=["alpha", "beta"]))
        assert set(mem.tags) == {"alpha", "beta"}

    def test_content_preserved(self):
        mem = _entry_to_memory(self._make_entry(content="Conteúdo específico."))
        assert mem.content == "Conteúdo específico."

    def test_default_confidence_is_one(self):
        mem = _entry_to_memory(self._make_entry())
        assert mem.confidence == 1.0

    def test_custom_confidence_preserved(self):
        mem = _entry_to_memory(self._make_entry(confidence=0.8))
        assert abs(mem.confidence - 0.8) < 0.001


# ─── _find_contradiction ──────────────────────────────────────────────


class TestFindContradiction:
    def _make_arch_memory(self, summary, tags):
        return Memory(
            type=MemoryType.ARCHITECTURE,
            summary=summary,
            tags=tags,
            confidence=1.0,
        )

    def test_finds_contradiction_same_type_and_tags(self):
        existing = [
            self._make_arch_memory(
                summary="Pipeline usa Auto Loader na Bronze",
                tags=["pipeline", "bronze", "auto-loader"],
            )
        ]
        new_mem = self._make_arch_memory(
            summary="Pipeline usa Auto Loader atualizado na Bronze",
            tags=["pipeline", "bronze", "auto-loader"],
        )
        result = _find_contradiction(new_mem, existing, use_sonnet=False)
        assert result is not None

    def test_no_contradiction_different_type(self):
        existing = [
            Memory(
                type=MemoryType.PROGRESS,
                summary="Pipeline Bronze finalizado",
                tags=["pipeline", "bronze"],
                confidence=1.0,
            )
        ]
        new_mem = self._make_arch_memory(
            summary="Pipeline Bronze finalizado",
            tags=["pipeline", "bronze"],
        )
        result = _find_contradiction(new_mem, existing, use_sonnet=False)
        assert result is None

    def test_no_contradiction_different_tags(self):
        existing = [
            self._make_arch_memory(
                summary="Fabric configurado",
                tags=["fabric", "direct-lake"],
            )
        ]
        new_mem = self._make_arch_memory(
            summary="Databricks configurado",
            tags=["databricks", "unity-catalog"],
        )
        result = _find_contradiction(new_mem, existing, use_sonnet=False)
        assert result is None

    def test_no_contradiction_for_memory_without_tags(self):
        existing = [self._make_arch_memory("Resumo", ["tag1"])]
        new_mem = Memory(type=MemoryType.ARCHITECTURE, summary="Outro", tags=[])
        result = _find_contradiction(new_mem, existing, use_sonnet=False)
        assert result is None

    def test_inactive_memory_not_matched(self):
        existing_mem = self._make_arch_memory(
            summary="Pipeline Bronze",
            tags=["pipeline", "bronze"],
        )
        existing_mem.confidence = 0.0  # Inativa
        new_mem = self._make_arch_memory(
            summary="Pipeline Bronze atualizado",
            tags=["pipeline", "bronze"],
        )
        result = _find_contradiction(new_mem, [existing_mem], use_sonnet=False)
        assert result is None


# ─── _filter_contradiction_candidates ────────────────────────────────


class TestFilterContradictionCandidates:
    def _arch(self, summary, tags, confidence=1.0):
        return Memory(
            type=MemoryType.ARCHITECTURE, summary=summary, tags=tags, confidence=confidence
        )

    def test_returns_same_type_with_shared_tag(self):
        existing = [self._arch("Pipeline usa Auto Loader", ["pipeline", "bronze"])]
        new_mem = self._arch("Pipeline usa COPY INTO", ["pipeline"])
        result = _filter_contradiction_candidates(new_mem, existing)
        assert len(result) == 1

    def test_excludes_different_type(self):
        existing = [
            Memory(
                type=MemoryType.PROGRESS,
                summary="Pipeline Bronze",
                tags=["pipeline"],
                confidence=1.0,
            )
        ]
        new_mem = self._arch("Pipeline Bronze", ["pipeline"])
        result = _filter_contradiction_candidates(new_mem, existing)
        assert result == []

    def test_excludes_no_tag_overlap(self):
        existing = [self._arch("Databricks config", ["databricks"])]
        new_mem = self._arch("Fabric config", ["fabric"])
        result = _filter_contradiction_candidates(new_mem, existing)
        assert result == []

    def test_excludes_inactive_memory(self):
        mem = self._arch("Pipeline Bronze", ["pipeline"], confidence=0.0)
        new_mem = self._arch("Pipeline Bronze updated", ["pipeline"])
        result = _filter_contradiction_candidates(new_mem, [mem])
        assert result == []

    def test_returns_multiple_candidates(self):
        existing = [
            self._arch("Auto Loader v1", ["pipeline", "bronze"]),
            self._arch("Auto Loader v2", ["pipeline", "bronze"]),
        ]
        new_mem = self._arch("COPY INTO substitui Auto Loader", ["pipeline"])
        result = _filter_contradiction_candidates(new_mem, existing)
        assert len(result) == 2

    def test_no_tags_falls_back_to_keyword_overlap(self):
        """Memória sem tags usa sobreposição de palavras-chave do summary."""
        existing = [self._arch("Pipeline Bronze usa Parquet como formato", [])]
        new_mem = Memory(
            type=MemoryType.ARCHITECTURE, summary="Pipeline Bronze usa Delta como formato", tags=[]
        )
        result = _filter_contradiction_candidates(new_mem, existing)
        # "pipeline", "bronze", "como", "formato" em comum → deve ser candidato
        assert len(result) == 1

    def test_no_tags_empty_existing_returns_empty(self):
        new_mem = Memory(type=MemoryType.ARCHITECTURE, summary="Algo", tags=[])
        result = _filter_contradiction_candidates(new_mem, [])
        assert result == []


# ─── _heuristic_contradiction ─────────────────────────────────────────


class TestHeuristicContradiction:
    def _arch(self, summary, tags=None):
        return Memory(type=MemoryType.ARCHITECTURE, summary=summary, tags=tags or ["pipeline"])

    def test_high_word_overlap_returns_true(self):
        a = self._arch("Pipeline Bronze usa Auto Loader para ingestão")
        b = self._arch("Pipeline Bronze usa Auto Loader para ingestão incremental")
        assert _heuristic_contradiction(b, a) is True

    def test_low_word_overlap_returns_false(self):
        a = self._arch("Pipeline usa Auto Loader")
        b = self._arch("Fabric Eventhouse configurado com KQL")
        assert _heuristic_contradiction(b, a) is False

    def test_empty_summaries_returns_false(self):
        a = Memory(type=MemoryType.ARCHITECTURE, summary="", tags=[])
        b = Memory(type=MemoryType.ARCHITECTURE, summary="", tags=[])
        assert _heuristic_contradiction(b, a) is False


# ─── _sonnet_check_contradiction ─────────────────────────────────────


def _make_sonnet_response(
    is_contradiction: bool, confidence: float = 0.9, reason: str = "test"
) -> MagicMock:
    """Cria mock de resposta HTTP do Sonnet."""
    body = json.dumps(
        {
            "content": [
                {
                    "text": json.dumps(
                        {
                            "is_contradiction": is_contradiction,
                            "confidence": confidence,
                            "reason": reason,
                        }
                    )
                }
            ],
            "usage": {"input_tokens": 400, "output_tokens": 60},
        }
    ).encode("utf-8")
    mock_resp = MagicMock()
    mock_resp.read.return_value = body
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


class TestSonnetCheckContradiction:
    def _arch(self, summary, tags=None):
        return Memory(
            type=MemoryType.ARCHITECTURE,
            summary=summary,
            tags=tags or ["pipeline"],
            content="Detalhes.",
        )

    def test_returns_true_when_sonnet_confirms_high_confidence(self):
        new_mem = self._arch("Pipeline usa COPY INTO")
        candidate = self._arch("Pipeline usa Auto Loader")
        mock_resp = _make_sonnet_response(True, confidence=0.92)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            assert _sonnet_check_contradiction(new_mem, candidate) is True

    def test_returns_false_when_sonnet_denies(self):
        new_mem = self._arch("Novo campo adicionado à camada Silver")
        candidate = self._arch("Camada Silver tem colunas de auditoria")
        mock_resp = _make_sonnet_response(False, confidence=0.95)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            assert _sonnet_check_contradiction(new_mem, candidate) is False

    def test_returns_false_when_confidence_below_threshold(self):
        """Contradição com confidence < 0.7 deve ser ignorada (incerto demais)."""
        new_mem = self._arch("Pipeline possivelmente muda formato")
        candidate = self._arch("Pipeline usa Parquet")
        mock_resp = _make_sonnet_response(True, confidence=0.55)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            assert _sonnet_check_contradiction(new_mem, candidate) is False

    def test_falls_back_to_heuristic_on_http_error(self):
        """Se Sonnet falhar, usa heurística word-overlap como fallback."""
        # Summaries com alta sobreposição → heurística retorna True
        new_mem = self._arch("Pipeline Bronze usa Auto Loader para ingestão")
        candidate = self._arch("Pipeline Bronze usa Auto Loader para ingestão de dados")
        with patch("urllib.request.urlopen", side_effect=OSError("timeout")):
            result = _sonnet_check_contradiction(new_mem, candidate)
        # Fallback heurístico — overlap alto → True
        assert result is True

    def test_falls_back_to_heuristic_on_invalid_json(self):
        """Resposta não-JSON do Sonnet dispara fallback heurístico."""
        new_mem = self._arch("Algo completamente diferente")
        candidate = self._arch("Fabric Eventhouse configurado")
        mock_resp = MagicMock()
        mock_resp.read.return_value = '{"content": [{"text": "Resposta invalida"}]}'.encode("utf-8")
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = _sonnet_check_contradiction(new_mem, candidate)
        # Sem sobreposição → fallback retorna False
        assert result is False

    def test_response_with_code_fence_stripped(self):
        """Code fence ```json ... ``` na resposta deve ser removido antes do parse."""
        body_text = (
            "```json\n"
            + json.dumps({"is_contradiction": True, "confidence": 0.88, "reason": "ok"})
            + "\n```"
        )
        body = json.dumps(
            {
                "content": [{"text": body_text}],
                "usage": {"input_tokens": 400, "output_tokens": 60},
            }
        ).encode("utf-8")
        mock_resp = MagicMock()
        mock_resp.read.return_value = body
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        new_mem = self._arch("Pipeline usa COPY INTO")
        candidate = self._arch("Pipeline usa Auto Loader")
        with patch("urllib.request.urlopen", return_value=mock_resp):
            assert _sonnet_check_contradiction(new_mem, candidate) is True


# ─── _find_contradiction (orquestração) ──────────────────────────────


class TestFindContradictionOrchestration:
    def _arch(self, summary, tags=None, confidence=1.0):
        return Memory(
            type=MemoryType.ARCHITECTURE,
            summary=summary,
            tags=tags or ["pipeline"],
            confidence=confidence,
        )

    def test_returns_none_when_no_candidates(self):
        existing = [self._arch("Databricks SQL config", ["databricks"])]
        new_mem = self._arch("Fabric Eventhouse KQL", ["fabric"])
        result = _find_contradiction(new_mem, existing, use_sonnet=False)
        assert result is None

    def test_uses_heuristic_when_use_sonnet_false(self):
        """use_sonnet=False nunca chama urllib — usa heurística diretamente."""
        candidate = self._arch("Pipeline Bronze usa Auto Loader para ingestão")
        new_mem = self._arch(
            "Pipeline Bronze usa Auto Loader para ingestão incremental", ["pipeline"]
        )
        with patch("urllib.request.urlopen") as mock_url:
            result = _find_contradiction(new_mem, [candidate], use_sonnet=False)
            mock_url.assert_not_called()
        assert result is candidate

    def test_calls_sonnet_when_use_sonnet_true(self):
        """use_sonnet=True deve chamar urlopen para confirmar."""
        candidate = self._arch("Pipeline usa Auto Loader", ["pipeline", "bronze"])
        new_mem = self._arch("Pipeline usa COPY INTO agora", ["pipeline"])
        mock_resp = _make_sonnet_response(True, confidence=0.90)
        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_url:
            result = _find_contradiction(new_mem, [candidate], use_sonnet=True)
            mock_url.assert_called_once()
        assert result is candidate

    def test_returns_none_when_sonnet_denies_all_candidates(self):
        candidate = self._arch("Pipeline usa Auto Loader", ["pipeline", "bronze"])
        new_mem = self._arch("Novo campo adicionado", ["pipeline"])
        mock_resp = _make_sonnet_response(False, confidence=0.95)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = _find_contradiction(new_mem, [candidate], use_sonnet=True)
        assert result is None

    def test_skips_sonnet_when_no_candidates_pass_prefilter(self):
        """Sem candidatos após pré-filtro, urlopen não é chamado."""
        existing = [self._arch("Fabric config", ["fabric"])]
        new_mem = self._arch("Databricks config", ["databricks"])
        with patch("urllib.request.urlopen") as mock_url:
            _find_contradiction(new_mem, existing, use_sonnet=True)
            mock_url.assert_not_called()


# ─── _mark_as_compiled ────────────────────────────────────────────────


class TestMarkAsCompiled:
    def test_adds_compiled_marker(self, tmp_path):
        log_path = tmp_path / "2026-04-13.md"
        log_path.write_text("# Daily Log\n\nConteúdo.", encoding="utf-8")
        _mark_as_compiled(log_path)
        content = log_path.read_text(encoding="utf-8")
        assert "COMPILED" in content

    def test_handles_write_error_gracefully(self, tmp_path):
        log_path = tmp_path / "log.md"
        log_path.write_text("Conteúdo.")
        from unittest.mock import patch

        with patch("builtins.open", side_effect=OSError("permission denied")):
            # Não deve lançar exceção
            _mark_as_compiled(log_path)


# ─── compile_daily_logs (end-to-end) ─────────────────────────────────


class TestCompileDailyLogs:
    def _write_daily_log(self, store: MemoryStore, entry_text: str):
        """Helper: escreve uma entrada no daily log de hoje."""
        store.append_daily_log(entry_text)

    def test_no_unprocessed_logs_returns_zero_metrics(self, store):
        metrics = compile_daily_logs(store)
        assert metrics["processed_logs"] == 0
        assert metrics["new_memories"] == 0

    def test_compiles_single_log_entry(self, store):
        self._write_daily_log(
            store,
            (
                "type: architecture\n"
                "summary: Pipeline Medallion Bronze Silver Gold\n"
                "tags: pipeline, medallion\n"
                "confidence: 1.0\n\n"
                "A arquitetura usa três camadas: Bronze, Silver e Gold."
            ),
        )
        metrics = compile_daily_logs(store, apply_decay_on_compile=False)
        assert metrics["new_memories"] >= 1
        assert metrics["processed_logs"] == 1

    def test_compiled_log_not_reprocessed(self, store):
        self._write_daily_log(
            store, ("type: progress\nsummary: Tarefa concluída hoje\ntags: task\n\nConteúdo.")
        )
        compile_daily_logs(store, apply_decay_on_compile=False)
        # Segunda execução: log já está marcado como compilado
        metrics = compile_daily_logs(store, apply_decay_on_compile=False)
        assert metrics["processed_logs"] == 0

    def test_duplicate_summaries_skipped(self, store):
        entry = "type: architecture\nsummary: Pipeline idêntico\ntags: pipeline\n\nCorpo."
        self._write_daily_log(store, entry)
        compile_daily_logs(store, apply_decay_on_compile=False)

        # Segundo log com mesmo summary
        self._write_daily_log(store, entry)
        metrics = compile_daily_logs(store, apply_decay_on_compile=False)
        assert metrics["skipped_dupes"] >= 1

    def test_regenerates_index_after_compile(self, store):
        self._write_daily_log(
            store,
            ("type: user\nsummary: Usuário usa Databricks\ntags: user, databricks\n\nDetalhe."),
        )
        compile_daily_logs(store, apply_decay_on_compile=False)
        index_path = store.data_dir / "index.md"
        assert index_path.exists()

    def test_new_memories_saved_to_store(self, store):
        self._write_daily_log(
            store,
            (
                "type: feedback\n"
                "summary: Nunca usar SELECT * sem WHERE\n"
                "tags: sql, feedback\n\n"
                "O usuário corrigiu o agente: sempre adicionar WHERE ou LIMIT."
            ),
        )
        compile_daily_logs(store, apply_decay_on_compile=False)
        memories = store.list_all(active_only=True)
        assert len(memories) >= 1

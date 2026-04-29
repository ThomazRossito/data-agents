"""Testes para hooks — audit_hook, security_hook, cost_guard_hook."""

from __future__ import annotations

import json
from unittest.mock import patch

from hooks import audit_hook, cost_guard_hook, security_hook

# ---------------------------------------------------------------------------
# audit_hook
# ---------------------------------------------------------------------------

def test_audit_hook_record_writes_jsonl(tmp_path):
    audit_file = tmp_path / "audit.jsonl"
    with patch.object(audit_hook, "AUDIT_FILE", audit_file):
        audit_hook.record(
            agent="spark_expert",
            task="cria pipeline bronze",
            tokens_used=123,
            tool_calls=2,
        )

    lines = audit_file.read_text().strip().split("\n")
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["agent"] == "spark_expert"
    assert entry["tokens_used"] == 123
    assert entry["tool_calls"] == 2
    assert "timestamp" in entry


def test_audit_hook_record_multiple_entries(tmp_path):
    audit_file = tmp_path / "audit.jsonl"
    with patch.object(audit_hook, "AUDIT_FILE", audit_file):
        for i in range(3):
            audit_hook.record(agent=f"agent_{i}", task="t", tokens_used=i, tool_calls=0)

    lines = audit_file.read_text().strip().split("\n")
    assert len(lines) == 3


def test_audit_hook_task_preview_truncated(tmp_path):
    audit_file = tmp_path / "audit.jsonl"
    long_task = "x" * 500
    with patch.object(audit_hook, "AUDIT_FILE", audit_file):
        audit_hook.record(agent="a", task=long_task, tokens_used=0, tool_calls=0)

    entry = json.loads(audit_file.read_text().strip())
    assert len(entry["task_preview"]) <= 200


# ---------------------------------------------------------------------------
# security_hook
# ---------------------------------------------------------------------------

def test_security_hook_allows_clean_content():
    ok, reason = security_hook.check("SELECT id FROM customers WHERE id = 1 LIMIT 10")
    assert ok is True
    assert reason == ""


def test_security_hook_blocks_drop_table():
    ok, reason = security_hook.check("DROP TABLE customers")
    assert ok is False
    assert reason != ""


def test_security_hook_blocks_drop_database():
    ok, reason = security_hook.check("DROP DATABASE prod_db")
    assert ok is False


def test_security_hook_blocks_truncate():
    ok, reason = security_hook.check("TRUNCATE TABLE sales_bronze")
    assert ok is False


def test_security_hook_blocks_rm_rf():
    ok, reason = security_hook.check("rm -rf /data/prod")
    assert ok is False


def test_security_hook_blocks_delete_without_where():
    ok, reason = security_hook.check("DELETE FROM orders")
    assert ok is False


def test_security_hook_allows_delete_with_where():
    ok, reason = security_hook.check("DELETE FROM orders WHERE id = 99")
    assert ok is True


def test_security_hook_blocks_select_star_no_limit():
    ok, reason = security_hook.check("SELECT * FROM big_table")
    assert ok is False


def test_security_hook_allows_select_star_with_limit():
    ok, reason = security_hook.check("SELECT * FROM big_table LIMIT 100")
    assert ok is True


def test_security_hook_blocks_git_force_push():
    ok, reason = security_hook.check("git push --force origin main")
    assert ok is False


def test_security_hook_blocks_dotenv():
    ok, reason = security_hook.check("cat .env")
    assert ok is False


def test_check_input_alias_for_check():
    ok, reason = security_hook.check_input("DROP TABLE x")
    assert ok is False


def test_check_output_allows_select_star_in_docs():
    """SELECT * em output de agente (documentação) não deve ser bloqueado."""
    ok, reason = security_hook.check_output(
        "Exemplo de query:\n```sql\nSELECT * FROM tabela\n```"
    )
    assert ok is True


def test_check_output_allows_delete_without_where_in_docs():
    ok, reason = security_hook.check_output(
        "Evite usar `DELETE FROM tabela` sem WHERE."
    )
    assert ok is True


def test_check_output_still_blocks_rm_rf():
    ok, reason = security_hook.check_output("execute: rm -rf /data")
    assert ok is False


def test_check_output_still_blocks_drop_table():
    ok, reason = security_hook.check_output("DROP TABLE prod.customers")
    assert ok is False


# ---------------------------------------------------------------------------
# cost_guard_hook
# ---------------------------------------------------------------------------

def setup_function():
    """Reset contadores antes de cada teste."""
    cost_guard_hook.reset()


def test_classify_high():
    assert cost_guard_hook.classify_operation("execute_job") == "HIGH"
    assert cost_guard_hook.classify_operation("start_cluster") == "HIGH"
    assert cost_guard_hook.classify_operation("create_pipeline") == "HIGH"


def test_classify_medium():
    assert cost_guard_hook.classify_operation("execute_sql") == "MEDIUM"
    assert cost_guard_hook.classify_operation("run_query") == "MEDIUM"


def test_classify_low():
    assert cost_guard_hook.classify_operation("list_tables") == "LOW"
    assert cost_guard_hook.classify_operation("general") == "LOW"


def test_track_accumulates_tokens():
    cost_guard_hook._session_total_tokens = 0
    cost_guard_hook.track("list_tables", 100)
    cost_guard_hook.track("list_tables", 200)
    assert cost_guard_hook._session_total_tokens == 300


def test_track_increments_high_count():
    cost_guard_hook._session_high_count = 0
    cost_guard_hook.track("execute_job", 100)
    cost_guard_hook.track("start_cluster", 50)
    assert cost_guard_hook._session_high_count == 2


def test_track_logs_warning_at_high_ops(caplog):
    import logging
    cost_guard_hook._session_high_count = 5
    with caplog.at_level(logging.WARNING, logger="hooks.cost_guard_hook"):
        cost_guard_hook.track("execute_job", 10)
    assert any("HIGH" in r.message or "ALERTA" in r.message for r in caplog.records)


def test_track_logs_critical_at_95pct(caplog):
    import logging
    from unittest.mock import patch

    cost_guard_hook._session_total_tokens = 0
    with patch.object(cost_guard_hook, "settings") as ms, \
         caplog.at_level(logging.ERROR, logger="hooks.cost_guard_hook"):
        ms.max_budget_tokens = 100
        cost_guard_hook.track("general", 96)
    assert any("95" in r.message or "CRÍTICO" in r.message for r in caplog.records)


def test_session_summary_keys():
    cost_guard_hook._session_total_tokens = 500
    cost_guard_hook._session_high_count = 2
    summary = cost_guard_hook.session_summary()
    assert "total_tokens" in summary
    assert "high_ops" in summary
    assert "budget" in summary


def test_reset_clears_counters():
    cost_guard_hook._session_total_tokens = 999
    cost_guard_hook._session_high_count = 7
    cost_guard_hook.reset()
    assert cost_guard_hook._session_total_tokens == 0
    assert cost_guard_hook._session_high_count == 0


# ---------------------------------------------------------------------------
# output_compressor
# ---------------------------------------------------------------------------

def test_compress_short_text_unchanged():
    from hooks.output_compressor import compress

    short = "texto curto que não precisa truncar"
    assert compress(short, max_chars=8000) == short


def test_compress_long_text_truncated():
    from hooks.output_compressor import compress

    long_text = "x" * 10000
    result = compress(long_text, max_chars=8000)
    assert len(result) < len(long_text)
    assert "truncados" in result


def test_compress_preserves_head_and_tail():
    from hooks.output_compressor import compress

    head = "INICIO " * 500
    tail = " FIM" * 500
    text = head + "MEIO " * 1000 + tail
    result = compress(text, max_chars=8000)
    assert result.startswith("INICIO")
    assert "FIM" in result[-500:]


def test_compress_exact_limit_not_truncated():
    from hooks.output_compressor import compress

    text = "a" * 8000
    assert compress(text, max_chars=8000) == text


def test_compress_marker_shows_removed_count():
    from hooks.output_compressor import compress

    text = "a" * 20000
    result = compress(text, max_chars=8000)
    assert "caracteres truncados" in result

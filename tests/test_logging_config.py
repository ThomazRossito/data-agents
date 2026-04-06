"""
Testes para config/logging_config.py.

Cobre:
  - JSONLFormatter: formato JSON, campos extras, exception info
  - setup_logging: console, arquivo, nenhum handler, nível de log
"""

import json
import logging
import os
import sys
import tempfile

from config.logging_config import JSONLFormatter, setup_logging


class TestJSONLFormatter:
    """Testes para o formatter de saída JSONL."""

    def _make_record(
        self,
        msg: str = "Test message",
        level: int = logging.INFO,
        name: str = "test.logger",
        exc_info=None,
    ) -> logging.LogRecord:
        return logging.LogRecord(
            name=name,
            level=level,
            pathname="",
            lineno=0,
            msg=msg,
            args=(),
            exc_info=exc_info,
        )

    def test_format_produces_valid_json(self):
        """Verifica que o output é JSON válido."""
        formatter = JSONLFormatter()
        record = self._make_record("Hello World")
        result = formatter.format(record)
        data = json.loads(result)
        assert isinstance(data, dict)

    def test_format_contains_required_fields(self):
        """Verifica campos obrigatórios no JSON."""
        formatter = JSONLFormatter()
        record = self._make_record("Test msg", level=logging.WARNING, name="my.logger")
        data = json.loads(formatter.format(record))
        assert data["level"] == "WARNING"
        assert data["message"] == "Test msg"
        assert data["logger"] == "my.logger"
        assert "timestamp" in data

    def test_format_timestamp_is_iso_format(self):
        """Verifica que o timestamp está em formato ISO 8601."""
        formatter = JSONLFormatter()
        record = self._make_record()
        data = json.loads(formatter.format(record))
        # ISO 8601 com timezone UTC termina com +00:00
        assert "+00:00" in data["timestamp"] or "Z" in data["timestamp"]

    def test_format_with_tool_name_extra(self):
        """Verifica que campos extras customizados aparecem no JSON."""
        formatter = JSONLFormatter()
        record = self._make_record("Tool called")
        record.tool_name = "Bash"
        record.platform = "databricks"
        data = json.loads(formatter.format(record))
        assert data["tool_name"] == "Bash"
        assert data["platform"] == "databricks"

    def test_format_with_all_extra_fields(self):
        """Verifica todos os campos extras suportados."""
        formatter = JSONLFormatter()
        record = self._make_record("Operation complete")
        record.tool_name = "Read"
        record.platform = "fabric"
        record.tool_use_id = "toolu_abc123"
        record.operation_type = "read"
        data = json.loads(formatter.format(record))
        assert data["tool_name"] == "Read"
        assert data["platform"] == "fabric"
        assert data["tool_use_id"] == "toolu_abc123"
        assert data["operation_type"] == "read"

    def test_format_without_extra_fields(self):
        """Verifica que campos extras ausentes não aparecem no JSON."""
        formatter = JSONLFormatter()
        record = self._make_record("Basic log")
        data = json.loads(formatter.format(record))
        assert "tool_name" not in data
        assert "platform" not in data
        assert "tool_use_id" not in data

    def test_format_with_exception_info(self):
        """Verifica que exception info é capturada no JSON."""
        formatter = JSONLFormatter()
        try:
            raise ValueError("Test exception")
        except ValueError:
            exc_info = sys.exc_info()
        record = self._make_record("Error occurred", level=logging.ERROR, exc_info=exc_info)
        data = json.loads(formatter.format(record))
        assert "exception" in data
        assert "ValueError" in data["exception"]

    def test_format_without_exception_no_exception_field(self):
        """Verifica que sem exceção não há campo exception no JSON."""
        formatter = JSONLFormatter()
        record = self._make_record("Normal log")
        data = json.loads(formatter.format(record))
        assert "exception" not in data

    def test_format_non_ascii_message(self):
        """Verifica mensagens com caracteres não-ASCII."""
        formatter = JSONLFormatter()
        record = self._make_record("Análise concluída com sucesso: configuração válida")
        result = formatter.format(record)
        data = json.loads(result)
        assert "Análise" in data["message"]


class TestSetupLogging:
    """Testes para a função setup_logging."""

    def setup_method(self):
        """Limpa handlers do root logger antes de cada teste."""
        root = logging.getLogger()
        root.handlers.clear()

    def teardown_method(self):
        """Restaura estado do root logger após cada teste."""
        root = logging.getLogger()
        for handler in root.handlers[:]:
            try:
                handler.close()
            except Exception:
                pass
        root.handlers.clear()

    def test_setup_console_only_adds_handler(self):
        """Verifica que console handler é adicionado quando enable_console=True."""
        setup_logging(enable_console=True, enable_file=False)
        root = logging.getLogger()
        assert len(root.handlers) >= 1

    def test_setup_no_handlers_when_both_disabled(self):
        """Verifica que nenhum handler é adicionado quando ambos estão desabilitados."""
        setup_logging(enable_console=False, enable_file=False)
        root = logging.getLogger()
        assert len(root.handlers) == 0

    def test_setup_with_file_handler(self):
        """Verifica que file handler é adicionado com caminho válido."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.jsonl")
            setup_logging(enable_console=False, enable_file=True, log_file=log_file)
            root = logging.getLogger()
            assert len(root.handlers) >= 1

    def test_setup_file_handler_uses_jsonl_formatter(self):
        """Verifica que o file handler usa o JSONLFormatter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.jsonl")
            setup_logging(enable_console=False, enable_file=True, log_file=log_file)
            root = logging.getLogger()
            file_handlers = [
                h for h in root.handlers if isinstance(h, logging.handlers.RotatingFileHandler)
            ]
            assert len(file_handlers) == 1
            assert isinstance(file_handlers[0].formatter, JSONLFormatter)

    def test_setup_root_logger_level_is_debug(self):
        """Verifica que root logger captura todos os níveis (DEBUG+)."""
        setup_logging(enable_console=True, enable_file=False)
        root = logging.getLogger()
        assert root.level == logging.DEBUG

    def test_setup_debug_level_on_console(self):
        """Verifica configuração de nível DEBUG no console."""
        setup_logging(log_level="DEBUG", enable_console=True, enable_file=False)
        root = logging.getLogger()
        assert root.level == logging.DEBUG

    def test_setup_clears_existing_handlers(self):
        """Verifica que handlers existentes são removidos antes de adicionar novos."""
        # Adicionar handler falso
        root = logging.getLogger()
        root.addHandler(logging.NullHandler())
        setup_logging(enable_console=True, enable_file=False)
        # O NullHandler deve ter sido removido e substituído (setup_logging chama root.handlers.clear())
        assert not any(isinstance(h, logging.NullHandler) for h in root.handlers)

    def test_setup_invalid_log_path_does_not_raise(self):
        """Verifica que path inválido para log não bloqueia o startup."""
        # Não deve levantar exceção — deve apenas logar warning
        setup_logging(
            enable_console=False,
            enable_file=True,
            log_file="/nonexistent/deeply/nested/path/app.jsonl",
        )

    def test_setup_silences_noisy_loggers(self):
        """Verifica que loggers de dependências são configurados para WARNING+."""
        setup_logging(enable_console=False, enable_file=False)
        for noisy in ("httpx", "httpcore", "asyncio", "urllib3"):
            assert logging.getLogger(noisy).level == logging.WARNING

    def test_setup_console_and_file_together(self):
        """Verifica que console + file handlers coexistem."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "combined.jsonl")
            setup_logging(enable_console=True, enable_file=True, log_file=log_file)
            root = logging.getLogger()
            assert len(root.handlers) == 2

    def test_setup_idempotent_when_called_twice(self):
        """Verifica que chamar setup_logging duas vezes não duplica handlers."""
        setup_logging(enable_console=True, enable_file=False)
        count_after_first = len(logging.getLogger().handlers)
        setup_logging(enable_console=True, enable_file=False)
        count_after_second = len(logging.getLogger().handlers)
        # Handlers são limpos antes de adicionar novos — não deve duplicar
        assert count_after_second == count_after_first

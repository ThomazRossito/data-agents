"""Testes do Business Monitor: alerter, slash commands e daemon helpers."""

from __future__ import annotations

import json
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# utils/monitor_alerter.py
# ─────────────────────────────────────────────────────────────────────────────


class TestGenerateAlertId:
    def test_format(self):
        from utils.monitor_alerter import generate_alert_id

        alert_id = generate_alert_id("TestMonitor")
        parts = alert_id.split("_")
        assert parts[0] == "alert"
        assert len(parts[1]) == 8  # YYYYMMDD
        assert len(parts[2]) == 6  # HHMMSS
        assert len(parts[3]) == 6  # hash

    def test_unique(self):
        from utils.monitor_alerter import generate_alert_id

        ids = {generate_alert_id("M") for _ in range(5)}
        assert len(ids) >= 1  # ao menos diferentes entre si na maioria dos casos


class TestGetAlertsFile:
    def test_today(self):
        from utils.monitor_alerter import get_alerts_file

        f = get_alerts_file()
        assert date.today().isoformat() in f.name

    def test_specific_date(self):
        from utils.monitor_alerter import get_alerts_file

        d = date(2025, 1, 15)
        f = get_alerts_file(d)
        assert "2025-01-15" in f.name


class TestEmitHeartbeat:
    def test_writes_ok_entry(self, tmp_path):
        from utils.monitor_alerter import emit_heartbeat
        import utils.monitor_alerter as alerter

        original = alerter.OUTPUT_DIR
        alerter.OUTPUT_DIR = tmp_path
        try:
            emit_heartbeat("TestMonitor", "databricks", "schema.tabela")
            files = list(tmp_path.glob("monitor_alerts_*.jsonl"))
            assert len(files) == 1
            entry = json.loads(files[0].read_text())
            assert entry["type"] == "OK"
            assert entry["monitor"] == "TestMonitor"
            assert entry["platform"] == "databricks"
            assert entry["table"] == "schema.tabela"
            assert entry["alert_id"] is None
        finally:
            alerter.OUTPUT_DIR = original


class TestLoadRecentAlerts:
    def test_empty_when_no_files(self, tmp_path):
        import utils.monitor_alerter as alerter

        original = alerter.OUTPUT_DIR
        alerter.OUTPUT_DIR = tmp_path
        try:
            result = alerter.load_recent_alerts(days=3)
            assert result == []
        finally:
            alerter.OUTPUT_DIR = original

    def test_loads_alert_entries(self, tmp_path):
        import utils.monitor_alerter as alerter

        original = alerter.OUTPUT_DIR
        alerter.OUTPUT_DIR = tmp_path
        try:
            today = date.today()
            f = tmp_path / f"monitor_alerts_{today.isoformat()}.jsonl"
            alert = {
                "alert_id": "alert_test_001",
                "timestamp": "2025-01-15T10:00:00",
                "type": "ALERT",
                "monitor": "Estoque Crítico",
                "severity": "CRITICA",
                "platform": "databricks",
                "table": "demo.bronze.estoque",
                "message": "3 produtos abaixo do mínimo",
                "records_affected": 3,
                "sample": [],
            }
            ok_entry = {"type": "OK", "monitor": "X", "platform": "databricks", "table": "t"}
            f.write_text(
                json.dumps(alert) + "\n" + json.dumps(ok_entry) + "\n",
                encoding="utf-8",
            )
            result = alerter.load_recent_alerts(days=1)
            assert len(result) == 1
            assert result[0]["monitor"] == "Estoque Crítico"
        finally:
            alerter.OUTPUT_DIR = original

    def test_skips_invalid_json(self, tmp_path):
        import utils.monitor_alerter as alerter

        original = alerter.OUTPUT_DIR
        alerter.OUTPUT_DIR = tmp_path
        try:
            today = date.today()
            f = tmp_path / f"monitor_alerts_{today.isoformat()}.jsonl"
            f.write_text("not-json\n", encoding="utf-8")
            result = alerter.load_recent_alerts(days=1)
            assert result == []
        finally:
            alerter.OUTPUT_DIR = original


class TestEmitAlert:
    def test_returns_alert_id_and_writes_jsonl(self, tmp_path):
        import utils.monitor_alerter as alerter

        original = alerter.OUTPUT_DIR
        alerter.OUTPUT_DIR = tmp_path
        try:
            with patch.object(alerter, "_send_email", return_value=False):
                alert_id = alerter.emit_alert(
                    monitor_name="Estoque Crítico",
                    severity="CRITICA",
                    platform="databricks",
                    table="demo.bronze.estoque",
                    message="3 produtos abaixo do mínimo",
                    records_affected=3,
                    sample_data=[{"sku": "SKU-001", "estoque_atual": 0}],
                )

            assert alert_id.startswith("alert_")
            files = list(tmp_path.glob("monitor_alerts_*.jsonl"))
            assert len(files) == 1
            entry = json.loads(files[0].read_text().strip())
            assert entry["alert_id"] == alert_id
            assert entry["type"] == "ALERT"
            assert entry["severity"] == "CRITICA"
            assert entry["records_affected"] == 3
        finally:
            alerter.OUTPUT_DIR = original

    def test_email_failure_does_not_raise(self, tmp_path):
        import utils.monitor_alerter as alerter

        original = alerter.OUTPUT_DIR
        alerter.OUTPUT_DIR = tmp_path
        try:
            with patch.object(alerter, "_send_email", side_effect=Exception("SMTP error")):
                alert_id = alerter.emit_alert(
                    monitor_name="TestMonitor",
                    severity="ALTA",
                    platform="databricks",
                    table="t",
                    message="erro",
                    records_affected=1,
                    sample_data=[],
                )
            assert alert_id.startswith("alert_")
        finally:
            alerter.OUTPUT_DIR = original


class TestSendEmailNotConfigured:
    def test_returns_false_when_no_smtp(self):
        """Quando SMTP não está configurado, _send_email retorna False sem enviar nada."""
        from utils.monitor_alerter import _send_email

        # _send_email faz `from config.settings import settings` internamente e verifica
        # se smtp_host/smtp_user/smtp_password/to_email estão preenchidos.
        # Em ambiente de CI nenhuma dessas variáveis está configurada → deve retornar False.
        payload = {
            "severity": "ALTA",
            "monitor": "T",
            "alert_id": "x",
            "timestamp": "2025-01-01T00:00:00",
            "platform": "db",
            "table": "t",
            "records_affected": 1,
            "message": "m",
            "sample": [],
        }
        # config/__init__.py faz `from config.settings import settings`, o que faz
        # `import config.settings` retornar a instância Pydantic em vez do módulo.
        # Usamos sys.modules para obter o módulo real e patchear corretamente.
        import sys
        import importlib

        settings_mod = sys.modules.get("config.settings") or importlib.import_module(
            "config.settings"
        )

        mock_settings = MagicMock()
        mock_settings.smtp_host = ""
        mock_settings.smtp_user = ""
        mock_settings.smtp_password = ""
        mock_settings.monitor_alert_email_to = ""
        mock_settings.smtp_port = 587

        with patch.object(settings_mod, "settings", mock_settings):
            result = _send_email(payload)
        assert result is False

    def test_password_comment_stripping(self):
        """Garante que comentários inline no SMTP_PASSWORD são removidos antes do login."""
        from utils.monitor_alerter import _send_email

        mock_settings = MagicMock()
        mock_settings.smtp_host = "smtp.gmail.com"
        mock_settings.smtp_port = 587
        mock_settings.smtp_user = "user@gmail.com"
        # Simula o que start_chainlit.sh exporta (sem remover o comentário inline)
        mock_settings.smtp_password = "myje chbr vkms rmms   # App Password do Gmail (não a senha)"
        mock_settings.monitor_alert_email_to = "dest@gmail.com"

        captured_password = []

        def fake_login(user, pwd):
            captured_password.append(pwd)

        mock_smtp = MagicMock()
        mock_smtp.__enter__ = lambda s: s
        mock_smtp.__exit__ = MagicMock(return_value=False)
        mock_smtp.login = fake_login
        mock_smtp.sendmail = MagicMock()

        import sys
        import importlib

        settings_mod = sys.modules.get("config.settings") or importlib.import_module(
            "config.settings"
        )

        with (
            patch("smtplib.SMTP", return_value=mock_smtp),
            patch.object(settings_mod, "settings", mock_settings),
        ):
            _send_email(
                {
                    "severity": "CRITICA",
                    "monitor": "Test",
                    "alert_id": "a1",
                    "timestamp": "2025-01-01T10:00:00",
                    "platform": "databricks",
                    "table": "t",
                    "records_affected": 1,
                    "message": "msg",
                    "sample": [],
                }
            )

        assert len(captured_password) == 1
        # Senha deve estar sem comentário e sem espaços
        assert "#" not in captured_password[0]
        assert "não" not in captured_password[0]
        assert captured_password[0] == "myjechbrvkmsrmms"


# ─────────────────────────────────────────────────────────────────────────────
# commands/monitor.py
# ─────────────────────────────────────────────────────────────────────────────


class TestMonitorState:
    def test_write_and_read_state(self, tmp_path):
        import commands.monitor as monitor_cmd

        original = monitor_cmd.STATE_FILE
        monitor_cmd.STATE_FILE = tmp_path / "monitor_state.json"
        try:
            monitor_cmd._write_state(True, reason="teste", actor="pytest")
            state = monitor_cmd._read_state()
            assert state["enabled"] is True
            assert state["updated_by"] == "pytest"
            assert state["reason"] == "teste"
        finally:
            monitor_cmd.STATE_FILE = original

    def test_read_state_defaults_to_enabled(self, tmp_path):
        import commands.monitor as monitor_cmd

        original = monitor_cmd.STATE_FILE
        monitor_cmd.STATE_FILE = tmp_path / "nonexistent.json"
        try:
            state = monitor_cmd._read_state()
            assert state["enabled"] is True
        finally:
            monitor_cmd.STATE_FILE = original

    def test_read_state_handles_corrupt_file(self, tmp_path):
        import commands.monitor as monitor_cmd

        original = monitor_cmd.STATE_FILE
        state_file = tmp_path / "monitor_state.json"
        state_file.write_text("not-json", encoding="utf-8")
        monitor_cmd.STATE_FILE = state_file
        try:
            state = monitor_cmd._read_state()
            assert state["enabled"] is True
        finally:
            monitor_cmd.STATE_FILE = original


class TestHandleMonitorOnOff:
    def test_on_sets_enabled_true(self, tmp_path):
        import commands.monitor as monitor_cmd

        original = monitor_cmd.STATE_FILE
        monitor_cmd.STATE_FILE = tmp_path / "state.json"
        try:
            result = monitor_cmd.handle_monitor_on()
            assert "ATIVADO" in result
            assert monitor_cmd._read_state()["enabled"] is True
        finally:
            monitor_cmd.STATE_FILE = original

    def test_off_sets_enabled_false(self, tmp_path):
        import commands.monitor as monitor_cmd

        original = monitor_cmd.STATE_FILE
        monitor_cmd.STATE_FILE = tmp_path / "state.json"
        try:
            result = monitor_cmd.handle_monitor_off()
            assert "DESATIVADO" in result
            assert monitor_cmd._read_state()["enabled"] is False
        finally:
            monitor_cmd.STATE_FILE = original


class TestHandleMonitorStatus:
    def test_status_no_alerts(self, tmp_path):
        import commands.monitor as monitor_cmd

        original_state = monitor_cmd.STATE_FILE
        original_output = monitor_cmd.OUTPUT_DIR
        monitor_cmd.STATE_FILE = tmp_path / "state.json"
        monitor_cmd.OUTPUT_DIR = tmp_path
        try:
            result = monitor_cmd.handle_monitor_status()
            assert "Business Monitor" in result
            assert "Alertas emitidos" in result
        finally:
            monitor_cmd.STATE_FILE = original_state
            monitor_cmd.OUTPUT_DIR = original_output

    def test_status_with_alerts(self, tmp_path):
        import commands.monitor as monitor_cmd

        original_state = monitor_cmd.STATE_FILE
        original_output = monitor_cmd.OUTPUT_DIR
        monitor_cmd.STATE_FILE = tmp_path / "state.json"
        monitor_cmd.OUTPUT_DIR = tmp_path

        # Cria arquivo de alertas do dia
        today = date.today()
        alerts_file = tmp_path / f"monitor_alerts_{today.isoformat()}.jsonl"
        entry = {
            "alert_id": "alert_test_001",
            "timestamp": "2025-04-17T10:00:00",
            "type": "ALERT",
            "monitor": "Estoque Crítico",
            "severity": "CRITICA",
            "platform": "databricks",
            "table": "demo.bronze.estoque",
            "message": "3 produtos",
            "records_affected": 3,
        }
        alerts_file.write_text(json.dumps(entry) + "\n", encoding="utf-8")

        try:
            result = monitor_cmd.handle_monitor_status()
            assert "Estoque Crítico" in result
            assert "1" in result  # 1 alerta
        finally:
            monitor_cmd.STATE_FILE = original_state
            monitor_cmd.OUTPUT_DIR = original_output


class TestHandleMonitorStop:
    def test_no_pid_file(self, tmp_path):
        import commands.monitor as monitor_cmd

        original = monitor_cmd.PID_FILE
        monitor_cmd.PID_FILE = tmp_path / "nonexistent.pid"
        try:
            result = monitor_cmd.handle_monitor_stop()
            assert "Nenhum daemon encontrado" in result
        finally:
            monitor_cmd.PID_FILE = original

    def test_invalid_pid_file(self, tmp_path):
        import commands.monitor as monitor_cmd

        original = monitor_cmd.PID_FILE
        pid_file = tmp_path / "monitor_daemon.pid"
        pid_file.write_text("not-a-pid", encoding="utf-8")
        monitor_cmd.PID_FILE = pid_file
        try:
            result = monitor_cmd.handle_monitor_stop()
            assert "PID" in result or "inválido" in result
        finally:
            monitor_cmd.PID_FILE = original

    def test_process_not_found(self, tmp_path):
        import commands.monitor as monitor_cmd

        original_pid = monitor_cmd.PID_FILE
        original_state = monitor_cmd.STATE_FILE
        pid_file = tmp_path / "monitor_daemon.pid"
        pid_file.write_text("999999999", encoding="utf-8")  # PID improvável de existir
        monitor_cmd.PID_FILE = pid_file
        monitor_cmd.STATE_FILE = tmp_path / "state.json"
        try:
            result = monitor_cmd.handle_monitor_stop()
            assert "não encontrado" in result or "encerrado" in result
        finally:
            monitor_cmd.PID_FILE = original_pid
            monitor_cmd.STATE_FILE = original_state


class TestLoadAlerts:
    def test_load_today_alerts_empty(self, tmp_path):
        import commands.monitor as monitor_cmd

        original = monitor_cmd.OUTPUT_DIR
        monitor_cmd.OUTPUT_DIR = tmp_path
        try:
            result = monitor_cmd._load_today_alerts()
            assert result == []
        finally:
            monitor_cmd.OUTPUT_DIR = original

    def test_load_recent_alerts_multiday(self, tmp_path):
        import commands.monitor as monitor_cmd

        original = monitor_cmd.OUTPUT_DIR
        monitor_cmd.OUTPUT_DIR = tmp_path
        try:
            # Cria alertas em 2 dias diferentes
            for i in range(2):
                d = date.today() - timedelta(days=i)
                f = tmp_path / f"monitor_alerts_{d.isoformat()}.jsonl"
                entry = {
                    "type": "ALERT",
                    "alert_id": f"alert_day_{i}",
                    "timestamp": f"2025-04-{15 - i}T10:00:00",
                    "monitor": "Test",
                    "severity": "ALTA",
                }
                f.write_text(json.dumps(entry) + "\n", encoding="utf-8")

            result = monitor_cmd._load_recent_alerts(days=7)
            assert len(result) == 2
        finally:
            monitor_cmd.OUTPUT_DIR = original


class TestRunMonitorCommandDispatcher:
    @pytest.mark.asyncio
    async def test_on_command(self, tmp_path):
        import commands.monitor as monitor_cmd

        original = monitor_cmd.STATE_FILE
        monitor_cmd.STATE_FILE = tmp_path / "state.json"
        try:
            result = await monitor_cmd.run_monitor_command("on")
            assert "ATIVADO" in result
        finally:
            monitor_cmd.STATE_FILE = original

    @pytest.mark.asyncio
    async def test_off_command(self, tmp_path):
        import commands.monitor as monitor_cmd

        original = monitor_cmd.STATE_FILE
        monitor_cmd.STATE_FILE = tmp_path / "state.json"
        try:
            result = await monitor_cmd.run_monitor_command("off")
            assert "DESATIVADO" in result
        finally:
            monitor_cmd.STATE_FILE = original

    @pytest.mark.asyncio
    async def test_status_command(self, tmp_path):
        import commands.monitor as monitor_cmd

        original_state = monitor_cmd.STATE_FILE
        original_output = monitor_cmd.OUTPUT_DIR
        monitor_cmd.STATE_FILE = tmp_path / "state.json"
        monitor_cmd.OUTPUT_DIR = tmp_path
        try:
            result = await monitor_cmd.run_monitor_command("status")
            assert "Business Monitor" in result
        finally:
            monitor_cmd.STATE_FILE = original_state
            monitor_cmd.OUTPUT_DIR = original_output

    @pytest.mark.asyncio
    async def test_unknown_subcommand(self):
        from commands.monitor import run_monitor_command

        result = await run_monitor_command("xyz")
        assert "desconhecido" in result.lower() or "Subcomando" in result

    @pytest.mark.asyncio
    async def test_ask_without_question(self):
        from commands.monitor import run_monitor_command

        result = await run_monitor_command("ask")
        assert "Use:" in result or "pergunta" in result.lower()


# ─────────────────────────────────────────────────────────────────────────────
# scripts/monitor_daemon.py — helpers puros (sem I/O real)
# ─────────────────────────────────────────────────────────────────────────────


class TestDaemonHelpers:
    def test_load_manifest(self):
        from scripts.monitor_daemon import load_manifest

        manifest = load_manifest()
        assert "monitors" in manifest
        assert isinstance(manifest["monitors"], list)

    def test_is_within_schedule_mocked(self):
        from scripts.monitor_daemon import is_within_schedule

        manifest = {"global": {"start_hour": 8, "end_hour": 23}}

        with patch("scripts.monitor_daemon.datetime") as mock_dt:
            mock_dt.now.return_value.hour = 12
            result = is_within_schedule(manifest)
        assert result is True

    def test_outside_schedule(self):
        from scripts.monitor_daemon import is_within_schedule

        manifest = {"global": {"start_hour": 8, "end_hour": 23}}

        with patch("scripts.monitor_daemon.datetime") as mock_dt:
            mock_dt.now.return_value.hour = 3
            result = is_within_schedule(manifest)
        assert result is False

    def test_read_state_no_file(self, tmp_path):
        import scripts.monitor_daemon as daemon

        original = daemon.STATE_FILE
        daemon.STATE_FILE = tmp_path / "nonexistent.json"
        try:
            state = daemon.read_state()
            assert state["enabled"] is True
        finally:
            daemon.STATE_FILE = original

    def test_write_and_read_state(self, tmp_path):
        import scripts.monitor_daemon as daemon

        original = daemon.STATE_FILE
        daemon.STATE_FILE = tmp_path / "state.json"
        try:
            daemon.write_state(False, reason="test", actor="pytest")
            state = daemon.read_state()
            assert state["enabled"] is False
            assert state["updated_by"] == "pytest"
        finally:
            daemon.STATE_FILE = original

    @pytest.mark.asyncio
    async def test_run_single_monitor_inactive(self):
        from scripts.monitor_daemon import run_single_monitor

        monitor = {"name": "TestInativo", "active": False}
        result = await run_single_monitor(monitor)
        assert result["status"] == "SKIPPED"

    @pytest.mark.asyncio
    async def test_run_single_monitor_dry_run(self):
        from scripts.monitor_daemon import run_single_monitor

        monitor = {
            "name": "TestDryRun",
            "active": True,
            "platform": "databricks",
            "table": "demo.bronze.t",
            "check_sql": "SELECT 1",
            "severity": "MEDIA",
            "message_template": "Erro.",
        }
        result = await run_single_monitor(monitor, dry_run=True)
        assert result["status"] == "DRY_RUN"

    @pytest.mark.asyncio
    async def test_run_single_monitor_no_rows_ok(self, tmp_path):
        import utils.monitor_alerter as alerter
        from scripts.monitor_daemon import run_single_monitor

        original_output = alerter.OUTPUT_DIR
        alerter.OUTPUT_DIR = tmp_path
        try:
            monitor = {
                "name": "TestOK",
                "active": True,
                "platform": "databricks",
                "table": "demo.bronze.t",
                "check_sql": "SELECT 1",
                "severity": "MEDIA",
                "message_template": "Erro.",
            }
            with patch("scripts.monitor_daemon._execute_check", new=AsyncMock(return_value=[])):
                result = await run_single_monitor(monitor)
            assert result["status"] == "OK"
            assert result["records_affected"] == 0
        finally:
            alerter.OUTPUT_DIR = original_output

    @pytest.mark.asyncio
    async def test_run_single_monitor_alert_emitted(self, tmp_path):
        import utils.monitor_alerter as alerter
        from scripts.monitor_daemon import run_single_monitor

        original_output = alerter.OUTPUT_DIR
        alerter.OUTPUT_DIR = tmp_path
        try:
            monitor = {
                "name": "Estoque Crítico",
                "active": True,
                "platform": "databricks",
                "table": "demo.bronze.controle_estoque",
                "check_sql": "SELECT sku FROM t WHERE estoque < minimo",
                "severity": "CRITICA",
                "message_template": "{count} produto(s) com estoque abaixo do mínimo!",
            }
            fake_rows = [
                {
                    "sku": "SKU-001",
                    "nome_produto": "Produto A",
                    "estoque_atual": 0,
                    "estoque_minimo": 10,
                },
                {
                    "sku": "SKU-002",
                    "nome_produto": "Produto B",
                    "estoque_atual": 2,
                    "estoque_minimo": 10,
                },
            ]
            with (
                patch(
                    "scripts.monitor_daemon._execute_check", new=AsyncMock(return_value=fake_rows)
                ),
                patch("utils.monitor_alerter._send_email", return_value=False),
            ):
                result = await run_single_monitor(monitor)

            assert result["status"] == "ALERT"
            assert result["records_affected"] == 2
            assert result["severity"] == "CRITICA"
            assert result["alert_id"].startswith("alert_")

            # Verifica que foi persistido no JSONL
            files = list(tmp_path.glob("monitor_alerts_*.jsonl"))
            assert len(files) == 1
        finally:
            alerter.OUTPUT_DIR = original_output

    @pytest.mark.asyncio
    async def test_run_monitor_cycle_disabled(self, tmp_path):
        import scripts.monitor_daemon as daemon

        original_state = daemon.STATE_FILE
        daemon.STATE_FILE = tmp_path / "state.json"
        daemon.write_state(False, reason="test")
        try:
            results = await daemon.run_monitor_cycle(ignore_schedule=True)
            assert results == []
        finally:
            daemon.STATE_FILE = original_state

    @pytest.mark.asyncio
    async def test_run_monitor_cycle_outside_schedule(self, tmp_path):
        import scripts.monitor_daemon as daemon

        original_state = daemon.STATE_FILE
        daemon.STATE_FILE = tmp_path / "state.json"
        daemon.write_state(True, reason="test")
        try:
            with patch("scripts.monitor_daemon.is_within_schedule", return_value=False):
                results = await daemon.run_monitor_cycle(ignore_schedule=False)
            assert results == []
        finally:
            daemon.STATE_FILE = original_state


class TestMonitorCommandParser:
    def test_monitor_registered(self):
        from commands.parser import COMMAND_REGISTRY

        # COMMAND_REGISTRY é dict[str, CommandDefinition] — as chaves são os nomes
        assert "monitor" in COMMAND_REGISTRY

    def test_monitor_internal_mode(self):
        from commands.parser import COMMAND_REGISTRY

        cmd = COMMAND_REGISTRY["monitor"]
        assert cmd.doma_mode == "internal"

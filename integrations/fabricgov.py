"""Wrapper para a CLI fabricgov — assessment de governança do Microsoft Fabric.

Auth auto-detectado por prioridade:
  1. FABRICGOV_CLIENT_ID + FABRICGOV_CLIENT_SECRET + FABRICGOV_TENANT_ID → SP
  2. AZURE_CLIENT_ID + AZURE_CLIENT_SECRET + AZURE_TENANT_ID (do settings) → SP
  3. FABRICGOV_AUTH_MODE=keyvault + FABRICGOV_VAULT_URL → Key Vault
  4. fallback → Device Flow (interativo — para uso manual)
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys

logger = logging.getLogger(__name__)

_PACKAGE = "fabricgov"


def is_installed() -> bool:
    result = subprocess.run(
        [sys.executable, "-m", "pip", "show", _PACKAGE],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def install() -> bool:
    logger.info("fabricgov não encontrado — instalando via pip...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", _PACKAGE],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.error("Falha ao instalar fabricgov: %s", result.stderr)
    return result.returncode == 0


def detect_auth_mode() -> str:
    """Detecta qual modo de auth está disponível no ambiente atual."""
    env = os.environ
    has_sp = (
        (env.get("FABRICGOV_CLIENT_ID") or env.get("AZURE_CLIENT_ID"))
        and (env.get("FABRICGOV_CLIENT_SECRET") or env.get("AZURE_CLIENT_SECRET"))
        and (env.get("FABRICGOV_TENANT_ID") or env.get("AZURE_TENANT_ID"))
    )
    if has_sp:
        return "sp"
    if env.get("FABRICGOV_AUTH_MODE") == "keyvault" and env.get("FABRICGOV_VAULT_URL"):
        return "keyvault"
    return "device"


def _build_env(auth_mode: str) -> dict:
    """Monta env vars para o subprocess com as credenciais corretas."""
    env = os.environ.copy()

    if auth_mode == "sp":
        # SP: prefere FABRICGOV_*, cai para AZURE_* do settings como fallback
        from config.settings import settings

        env.setdefault("FABRICGOV_TENANT_ID", env.get("AZURE_TENANT_ID", settings.azure_tenant_id))
        env.setdefault("FABRICGOV_CLIENT_ID", env.get("AZURE_CLIENT_ID", settings.azure_client_id))
        env.setdefault(
            "FABRICGOV_CLIENT_SECRET",
            env.get("AZURE_CLIENT_SECRET", settings.azure_client_secret),
        )
    # keyvault e device não precisam de vars extras — fabricgov lida internamente

    return env


def run_assessment(
    command: str = "all",
    output_dir: str | None = None,
    days: int = 7,
    lang: str = "pt",
    auth_mode: str | None = None,
) -> dict:
    """Executa fabricgov collect + analyze + report.

    Args:
        command:    Subcomando de collect ("all", "inventory", "activity", etc.)
        output_dir: Diretório de saída (None = padrão fabricgov)
        days:       Dias de histórico de atividade (só para "all" e "activity")
        lang:       Idioma do relatório ("pt" ou "en")
        auth_mode:  "sp", "device" ou "keyvault" (None = auto-detectar)

    Returns:
        dict com chaves: status, auth_mode, collect_stdout,
                         findings_stdout, report_returncode, report_path, error
    """
    if not is_installed() and not install():
        return {
            "status": "error",
            "error": "Não foi possível instalar fabricgov. Rode: pip install fabricgov",
        }

    _auth = auth_mode or detect_auth_mode()
    env = _build_env(_auth)
    result: dict = {"status": "ok", "auth_mode": _auth}

    # ── 1. collect ───────────────────────────────────────────────────────────
    collect_args = ["fabricgov", "collect", command]
    if command in ("all", "activity") and days:
        collect_args += ["--days", str(days)]
    if output_dir:
        collect_args += ["--output", output_dir]

    logger.info("Executando: %s", " ".join(collect_args))
    proc = subprocess.run(
        collect_args,
        capture_output=True,
        text=True,
        env=env,
        timeout=600,
    )
    # Captura apenas os últimos 3000 chars para não inflar o contexto
    result["collect_stdout"] = proc.stdout[-3000:] if proc.stdout else ""
    result["collect_returncode"] = proc.returncode

    if proc.returncode != 0:
        result["status"] = "error"
        result["error"] = proc.stderr[-1000:] if proc.stderr else "Erro desconhecido"
        return result

    # ── 2. analyze ──────────────────────────────────────────────────────────
    analyze_args = ["fabricgov", "analyze", "--lang", lang]
    if output_dir:
        analyze_args += ["--from", output_dir]

    proc_analyze = subprocess.run(
        analyze_args,
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    result["findings_stdout"] = proc_analyze.stdout[-4000:] if proc_analyze.stdout else ""

    # ── 3. report ───────────────────────────────────────────────────────────
    report_args = ["fabricgov", "report", "--lang", lang]
    if output_dir:
        report_args += ["--from", output_dir]

    proc_report = subprocess.run(
        report_args,
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    result["report_returncode"] = proc_report.returncode
    result["report_path"] = (
        f"{output_dir}/report.html" if output_dir else "output/<run>/report.html"
    )

    return result


def format_result(result: dict) -> str:
    """Formata o resultado do assessment como Markdown para o usuário."""
    if result["status"] == "error":
        return (
            f"❌ **fabricgov falhou**\n\n"
            f"Auth mode: `{result.get('auth_mode', 'desconhecido')}`\n\n"
            f"Erro:\n```\n{result.get('error', '')}\n```\n\n"
            "Verifique as credenciais no `.env` e se o Service Principal tem "
            "`Tenant.Read.All` nas APIs Admin do Fabric."
        )

    auth = result.get("auth_mode", "desconhecido")
    findings = result.get("findings_stdout", "").strip()
    collect_out = result.get("collect_stdout", "").strip()
    report_path = result.get("report_path", "")

    parts = [
        "## fabricgov Assessment — Microsoft Fabric",
        f"**Auth:** `{auth}` | **Relatório:** `{report_path}`",
        "",
    ]

    if collect_out:
        parts += ["### Coleta", f"```\n{collect_out}\n```", ""]

    if findings:
        parts += ["### Findings de Governança", findings, ""]

    parts += [
        "---",
        f"> Relatório HTML completo gerado em `{report_path}`",
    ]

    return "\n".join(parts)

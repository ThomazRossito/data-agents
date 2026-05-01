"""
Bootstrap interativo do Data Agents.

Gera um `.env` mínimo com apenas as credenciais essenciais:
  - ANTHROPIC_API_KEY (obrigatório)
  - Databricks (opcional)
  - Microsoft Fabric (opcional)

Uso:
    python scripts/bootstrap.py
    make bootstrap

Se o `.env` já existir, pergunta antes de sobrescrever.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = REPO_ROOT / ".env"


def _prompt(question: str, default: str = "", required: bool = False) -> str:
    """Pergunta ao usuário, com valor default opcional."""
    suffix = f" [{default}]" if default else ""
    while True:
        try:
            answer = input(f"{question}{suffix}: ").strip()
        except EOFError:
            answer = ""
        if not answer and default:
            return default
        if answer:
            return answer
        if not required:
            return ""
        print("  ⚠️  Campo obrigatório. Tente de novo.")


def _prompt_yes_no(question: str, default: bool = False) -> bool:
    hint = "S/n" if default else "s/N"
    answer = _prompt(f"{question} ({hint})").lower()
    if not answer:
        return default
    return answer in ("s", "sim", "y", "yes")


def _validate_anthropic_key(key: str) -> bool:
    """Anthropic keys começam com sk-ant-; Bedrock/Azure são livres."""
    if not key:
        return False
    if key.startswith("sk-ant-"):
        return True
    # Aceita keys customizadas para proxies LiteLLM/Bedrock sem warning barulhento.
    print("  ℹ️  Chave não começa com 'sk-ant-'. Seguindo assumindo proxy (Bedrock/Azure).")
    return True


def _confirm_overwrite() -> bool:
    print(f"⚠️  {ENV_PATH} já existe.")
    return _prompt_yes_no("Sobrescrever?", default=False)


def _collect_anthropic() -> dict[str, str]:
    print("\n━━━ Anthropic / Claude (obrigatório) ━━━")
    print("Obtenha sua chave em: https://console.anthropic.com/account/keys")
    while True:
        key = _prompt("ANTHROPIC_API_KEY", required=True)
        if _validate_anthropic_key(key):
            break
    base_url = ""
    if _prompt_yes_no("Usar proxy (LiteLLM/Bedrock/Azure)?", default=False):
        base_url = _prompt("ANTHROPIC_BASE_URL (ex: https://proxy.exemplo.com)")
    return {"ANTHROPIC_API_KEY": key, "ANTHROPIC_BASE_URL": base_url}


def _collect_databricks() -> dict[str, str]:
    if not _prompt_yes_no("\nConfigurar Databricks agora?", default=False):
        return {}
    print("━━━ Databricks ━━━")
    host = _prompt("DATABRICKS_HOST (ex: https://adb-xxx.azuredatabricks.net)", required=True)
    token = _prompt("DATABRICKS_TOKEN (começa com dapi)", required=True)
    warehouse = _prompt("DATABRICKS_SQL_WAREHOUSE_ID (opcional, tecle ENTER se não tiver)")
    return {
        "DATABRICKS_HOST": host,
        "DATABRICKS_TOKEN": token,
        "DATABRICKS_SQL_WAREHOUSE_ID": warehouse,
    }


def _collect_fabric() -> dict[str, str]:
    if not _prompt_yes_no("\nConfigurar Microsoft Fabric agora?", default=False):
        return {}
    print("━━━ Microsoft Fabric / Azure ━━━")
    print("Necessário um Service Principal com acesso ao workspace.")
    tenant = _prompt("AZURE_TENANT_ID (UUID)", required=True)
    client_id = _prompt("AZURE_CLIENT_ID (UUID do SP)", required=True)
    client_secret = _prompt("AZURE_CLIENT_SECRET", required=True)
    workspace = _prompt("FABRIC_WORKSPACE_ID (UUID do workspace)", required=True)
    return {
        "AZURE_TENANT_ID": tenant,
        "AZURE_CLIENT_ID": client_id,
        "AZURE_CLIENT_SECRET": client_secret,
        "FABRIC_WORKSPACE_ID": workspace,
    }


def _render_env(sections: dict[str, dict[str, str]]) -> str:
    """Gera o conteúdo do .env mínimo, omitindo chaves vazias."""
    lines: list[str] = [
        "# Data Agents — .env gerado por `make bootstrap`",
        "# Para configuração completa, veja .env.example",
        "",
    ]
    for section_name, entries in sections.items():
        filled = {k: v for k, v in entries.items() if v}
        if not filled:
            continue
        lines.append(f"# ─── {section_name} ───")
        for key, value in filled.items():
            lines.append(f"{key}={value}")
        lines.append("")

    # Defaults razoáveis sempre presentes
    lines.extend(
        [
            "# ─── Sistema ───",
            "DEFAULT_MODEL=claude-sonnet-4-6",
            "MAX_BUDGET_USD=1.0",
            "MAX_TURNS=50",
            "LOG_LEVEL=INFO",
            "CONSOLE_LOG_LEVEL=WARNING",
            "AUDIT_LOG_PATH=./logs/audit.jsonl",
            "",
            "# ─── Memória persistente ───",
            "MEMORY_ENABLED=true",
            "MEMORY_RETRIEVAL_ENABLED=true",
            "MEMORY_CAPTURE_ENABLED=true",
        ]
    )
    return "\n".join(lines) + "\n"


def _next_steps(has_databricks: bool, has_fabric: bool) -> None:
    print("\n" + "━" * 60)
    print("✅ .env criado em", ENV_PATH)
    print("━" * 60)
    print("\nPróximos passos:")
    print("  1. make demo          # testa o sistema com uma query canônica")
    print("  2. make run           # modo interativo no terminal")
    if has_databricks:
        print("  3. make health-databricks   # valida conexão com Databricks")
    if has_fabric:
        print("  3. make health-fabric       # valida conexão com Fabric")
    if not (has_databricks or has_fabric):
        print("\n💡 Sem Databricks/Fabric o agente `/geral` (Haiku) funciona 100%.")
        print("   Para configurar plataformas depois, edite .env manualmente.")
    print()


def main() -> int:
    print("━" * 60)
    print(" Data Agents — Bootstrap")
    print("━" * 60)
    print("Este wizard cria um .env mínimo. Pode completar depois via .env.example.\n")

    if ENV_PATH.exists() and not _confirm_overwrite():
        print("Nenhuma mudança feita. Saindo.")
        return 0

    sections = {
        "Anthropic / Claude": _collect_anthropic(),
        "Databricks ": _collect_databricks(),
        "Microsoft Fabric": _collect_fabric(),
    }

    try:
        ENV_PATH.write_text(_render_env(sections), encoding="utf-8")
    except OSError as e:
        print(f"\n❌ Erro ao gravar {ENV_PATH}: {e}")
        return 1

    has_databricks = bool(sections["Databricks"])
    has_fabric = bool(sections["Microsoft Fabric"])
    _next_steps(has_databricks, has_fabric)
    return 0


if __name__ == "__main__":
    sys.exit(main())

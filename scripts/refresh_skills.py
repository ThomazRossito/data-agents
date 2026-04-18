"""
Skill Refresh — Atualiza Skills operacionais com documentação recente.

Chama a Anthropic Messages API diretamente (sem Claude Agent SDK, sem MCPs) e
usa o tool nativo `web_search` para buscar docs recentes. Cada SKILL.md é passada
num request one-shot: o modelo devolve o arquivo atualizado em um bloco marcado,
e o script escreve em disco.

Uso:
  python scripts/refresh_skills.py                    # refresh dos domínios configurados
  python scripts/refresh_skills.py --domains databricks fabric
  python scripts/refresh_skills.py --domains databricks --force
  python scripts/refresh_skills.py --dry-run          # lista skills sem atualizar

Configuração via .env:
  ANTHROPIC_API_KEY=sk-ant-...
  SKILL_REFRESH_ENABLED=true
  SKILL_REFRESH_INTERVAL_DAYS=3      # pula skills atualizadas há menos de N dias
  SKILL_REFRESH_DOMAINS=databricks,fabric
  SKILL_REFRESH_MODEL=claude-sonnet-4-6   # opcional; padrão usa o memory_extractor_model
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from config.settings import settings  # noqa: E402
from config.logging_config import setup_logging  # noqa: E402

logger = logging.getLogger("data_agents.refresh_skills")

_SKILLS_DIR = _PROJECT_ROOT / "skills"

# Preços Anthropic (USD por 1M tokens) — Sonnet 4.6 (ajuste quando mudar modelo).
_PRICE_INPUT_PER_MTOK = 3.00
_PRICE_OUTPUT_PER_MTOK = 15.00

# Delimitadores usados para que o modelo marque o SKILL.md atualizado no output.
_SKILL_BEGIN = "<<<SKILL_BEGIN>>>"
_SKILL_END = "<<<SKILL_END>>>"

_SYSTEM_PROMPT = """Você é o Skill Updater do projeto data-agents. Sua tarefa: receber
uma SKILL.md existente e devolver o arquivo atualizado com base em documentação
recente das plataformas (Databricks, Fabric, dbt, PySpark, etc.).

Use o tool `web_search` para consultar docs oficiais e changelogs quando precisar
confirmar ou completar informação. Prefira fontes canônicas: docs.databricks.com,
learn.microsoft.com/fabric, docs.getdbt.com, spark.apache.org.

## Regras de edição

- Preserve a estrutura de seções da SKILL atual — não reorganize sem motivo.
- Preserve o tom opinionado do projeto ("use X, evite Y porque Z").
- Atualize apenas o que mudou na plataforma: APIs depreciadas ou renomeadas,
  novos parâmetros relevantes, exemplos com sintaxe atual.
- Sinalize breaking changes com "> ⚠️ Breaking change em [versão]: ..." no topo
  da seção afetada.
- NUNCA remova seções ou exemplos sem substituição equivalente.
- NUNCA invente APIs — apenas documente o que foi confirmado via web_search.
- Mantenha frontmatter se existir; atualize `updated_at: YYYY-MM-DD` e
  `source:` (web_search | manual).

## Formato da resposta

1. Um parágrafo curto (≤3 linhas) resumindo o que mudou.
2. O arquivo SKILL.md completo atualizado, delimitado exatamente assim:

{begin}
---
name: ...
updated_at: YYYY-MM-DD
source: web_search
---
# Skill atualizada

... corpo completo ...
{end}

Se após as buscas você concluir que o arquivo atual já está correto e nada deve
mudar, responda APENAS com a linha: NO_CHANGE — sem os delimitadores.
""".format(begin=_SKILL_BEGIN, end=_SKILL_END)


def _get_skill_paths(domains: list[str]) -> list[Path]:
    """Retorna todos os SKILL.md dos domínios especificados."""
    paths: list[Path] = []
    for domain in domains:
        domain_dir = _SKILLS_DIR / domain
        if not domain_dir.exists():
            logger.warning(f"Domínio não encontrado: {domain_dir}")
            continue
        skill_files = sorted(
            p
            for p in domain_dir.rglob("SKILL.md")
            if not any(part.startswith("_") or part.upper() == "TEMPLATE" for part in p.parts)
        )
        paths.extend(skill_files)
    return paths


def _get_skill_age_days(skill_path: Path) -> float | None:
    """
    Retorna quantos dias atrás a skill foi atualizada.

    Lê o campo `updated_at` do frontmatter se existir; fallback para mtime.
    """
    try:
        content = skill_path.read_text(encoding="utf-8")

        if content.startswith("---"):
            end = content.find("---", 3)
            if end != -1:
                frontmatter = content[3:end]
                for line in frontmatter.splitlines():
                    if line.strip().startswith("updated_at:"):
                        date_str = line.split(":", 1)[1].strip()
                        try:
                            updated = datetime.strptime(date_str, "%Y-%m-%d").replace(
                                tzinfo=timezone.utc
                            )
                            return (datetime.now(timezone.utc) - updated).days
                        except ValueError:
                            break

        mtime = datetime.fromtimestamp(os.path.getmtime(skill_path), tz=timezone.utc)
        return (datetime.now(timezone.utc) - mtime).days
    except Exception:
        return None


def _should_refresh(skill_path: Path, interval_days: int, force: bool) -> tuple[bool, str]:
    """Decide se uma skill precisa ser atualizada."""
    if force:
        return True, "force=True"
    age = _get_skill_age_days(skill_path)
    if age is None:
        return True, "não foi possível determinar a idade"
    if age >= interval_days:
        return True, f"{age} dias desde o último refresh (intervalo: {interval_days} dias)"
    return False, f"atualizada há {age} dias (intervalo: {interval_days} dias)"


def _extract_updated_skill(response_text: str) -> str | None:
    """
    Extrai o conteúdo SKILL.md atualizado do output do modelo.

    Retorna None se o modelo sinalizou NO_CHANGE ou se os delimitadores estão ausentes.
    """
    if _SKILL_BEGIN not in response_text:
        return None
    match = re.search(
        rf"{re.escape(_SKILL_BEGIN)}\s*\n?(.*?)\n?\s*{re.escape(_SKILL_END)}",
        response_text,
        re.DOTALL,
    )
    if not match:
        return None
    return match.group(1).strip() + "\n"


def _estimate_cost(input_tokens: int, output_tokens: int) -> float:
    return (
        input_tokens / 1_000_000 * _PRICE_INPUT_PER_MTOK
        + output_tokens / 1_000_000 * _PRICE_OUTPUT_PER_MTOK
    )


async def _refresh_skill(skill_path: Path, model: str) -> dict:
    """
    Chama a Messages API para atualizar um SKILL.md.

    Returns: {"skill", "status", "cost", "preview"}
    """
    from anthropic import AsyncAnthropic

    rel_path = skill_path.relative_to(_PROJECT_ROOT)
    current_content = skill_path.read_text(encoding="utf-8")
    today = datetime.now().strftime("%Y-%m-%d")

    user_prompt = (
        f"Arquivo: `{rel_path}`\n"
        f"Data de hoje: {today}\n\n"
        f"SKILL.md ATUAL:\n\n{current_content}\n\n"
        f"Busque documentação atualizada da biblioteca/ferramenta correspondente e "
        f"devolva o arquivo atualizado conforme as regras do system prompt."
    )

    client = AsyncAnthropic()  # usa ANTHROPIC_API_KEY do ambiente
    response = await client.messages.create(
        model=model,
        max_tokens=8_000,
        system=_SYSTEM_PROMPT,
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}],
        messages=[{"role": "user", "content": user_prompt}],
    )

    response_text = "".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    )
    updated = _extract_updated_skill(response_text)
    cost = _estimate_cost(response.usage.input_tokens, response.usage.output_tokens)

    if response_text.strip().startswith("NO_CHANGE"):
        return {"skill": str(rel_path), "status": "no_change", "cost": cost, "preview": ""}

    if updated is None:
        return {
            "skill": str(rel_path),
            "status": "empty_response",
            "cost": cost,
            "preview": response_text[:200],
        }

    skill_path.write_text(updated, encoding="utf-8")
    return {
        "skill": str(rel_path),
        "status": "ok",
        "cost": cost,
        "preview": response_text[:200],
    }


async def run_refresh(
    domains: list[str],
    interval_days: int,
    force: bool = False,
    dry_run: bool = False,
    max_concurrent: int = 2,
    model: str | None = None,
) -> dict:
    """Executa o refresh de todas as skills dos domínios especificados."""
    model = model or os.environ.get("SKILL_REFRESH_MODEL") or settings.memory_extractor_model
    skill_paths = _get_skill_paths(domains)

    metrics: dict = {
        "total": len(skill_paths),
        "refreshed": 0,
        "skipped": 0,
        "no_change": 0,
        "errors": 0,
        "cost": 0.0,
        "details": [],
    }

    if not skill_paths:
        logger.warning(f"Nenhuma SKILL.md encontrada para os domínios: {domains}")
        return metrics

    print(f"\n{'=' * 60}")
    print(f"Skill Refresh — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"Modelo: {model}")
    print(f"Domínios: {', '.join(domains)} | Intervalo: {interval_days}d | Force: {force}")
    print(f"Skills encontradas: {len(skill_paths)}")
    print(f"{'=' * 60}\n")

    to_refresh: list[Path] = []
    for skill_path in skill_paths:
        should, reason = _should_refresh(skill_path, interval_days, force)
        rel = skill_path.relative_to(_PROJECT_ROOT)
        if should:
            print(f"  ⏳ {rel} — {reason}")
            to_refresh.append(skill_path)
        else:
            print(f"  ✓  {rel} — pulada ({reason})")
            metrics["skipped"] += 1

    if not to_refresh:
        print("\nNenhuma skill precisa de atualização.")
        return metrics

    if dry_run:
        print(f"\n[dry-run] {len(to_refresh)} skills seriam atualizadas.")
        metrics["refreshed"] = len(to_refresh)
        return metrics

    print(f"\nAtualizando {len(to_refresh)} skills (max {max_concurrent} simultâneas)...\n")

    for i in range(0, len(to_refresh), max_concurrent):
        batch = to_refresh[i : i + max_concurrent]
        tasks = [_refresh_skill(path, model) for path in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for skill_path, result in zip(batch, results):
            rel = skill_path.relative_to(_PROJECT_ROOT)
            if isinstance(result, Exception):
                print(f"  ✗ {rel} — ERRO: {result}")
                metrics["errors"] += 1
                metrics["details"].append(
                    {"skill": str(rel), "status": "error", "error": str(result)}
                )
                continue

            status = result["status"]
            cost = result["cost"]
            metrics["cost"] += cost
            metrics["details"].append(result)
            if status == "ok":
                print(f"  ✅ {rel} — atualizada (${cost:.4f})")
                metrics["refreshed"] += 1
            elif status == "no_change":
                print(f"  ✓  {rel} — sem alterações (${cost:.4f})")
                metrics["no_change"] += 1
            else:
                print(f"  ⚠️  {rel} — {status} (${cost:.4f})")
                metrics["errors"] += 1

    print(f"\n{'=' * 60}")
    print(
        f"Resultado: {metrics['refreshed']} atualizadas | "
        f"{metrics['no_change']} sem alteração | "
        f"{metrics['skipped']} puladas | "
        f"{metrics['errors']} erros | "
        f"Custo: ${metrics['cost']:.4f}"
    )
    print(f"{'=' * 60}\n")

    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Atualiza Skills operacionais com documentação recente (via Anthropic Messages API + web_search)."
    )
    parser.add_argument(
        "--domains",
        nargs="+",
        default=None,
        help=f"Domínios a atualizar (ex: databricks fabric). Padrão: {settings.skill_refresh_domains}",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=None,
        help=f"Intervalo mínimo em dias entre refreshes. Padrão: {settings.skill_refresh_interval_days}",
    )
    parser.add_argument("--force", action="store_true", help="Atualiza todas.")
    parser.add_argument("--dry-run", action="store_true", help="Lista sem modificar.")
    parser.add_argument("--concurrent", type=int, default=2, help="Skills em paralelo. Padrão: 2.")
    parser.add_argument("--model", type=str, default=None, help="Override do modelo Anthropic.")

    args = parser.parse_args()

    domains = args.domains or [
        d.strip() for d in settings.skill_refresh_domains.split(",") if d.strip()
    ]
    interval = args.interval or settings.skill_refresh_interval_days

    if not settings.skill_refresh_enabled and not args.force:
        print("Skill refresh desabilitado (SKILL_REFRESH_ENABLED=false). Use --force para forçar.")
        sys.exit(0)

    setup_logging(log_level="WARNING", enable_console=False)

    asyncio.run(
        run_refresh(
            domains=domains,
            interval_days=interval,
            force=args.force,
            dry_run=args.dry_run,
            max_concurrent=args.concurrent,
            model=args.model,
        )
    )


if __name__ == "__main__":
    main()

"""
Skill Refresh — Atualiza Skills operacionais com documentação recente.

Chama a Anthropic Messages API diretamente (sem Claude Agent SDK, sem MCPs) via
**Batch API** — todas as skills pendentes viram uma única submissão com 50% de
desconto sobre input+output. Cada skill usa o tool nativo `web_search` para buscar
docs recentes; o modelo devolve o arquivo atualizado em um bloco marcado e o script
escreve em disco após o batch concluir.

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

Notas sobre Batch API:
- SLA oficial: 24h. Batches pequenos (≤20 skills) concluem em minutos.
- Em caso de Ctrl+C, o batch **continua rodando** no servidor. Use
  `anthropic batches cancel <batch_id>` (CLI oficial) ou espere o resultado
  na próxima execução — tokens são cobrados mesmo assim.
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
# Batch API aplica 50% de desconto sobre input e output.
_PRICE_INPUT_PER_MTOK = 3.00
_PRICE_OUTPUT_PER_MTOK = 15.00
_BATCH_DISCOUNT = 0.5

# Polling do batch: a API tem SLA de 24h mas batches pequenos costumam concluir
# em minutos. Intervalo conservador para não gastar quota de retrieve.
_BATCH_POLL_INTERVAL_S = 10
_BATCH_TIMEOUT_S = 24 * 60 * 60

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


def _estimate_cost(input_tokens: int, output_tokens: int, batch: bool = True) -> float:
    base = (
        input_tokens / 1_000_000 * _PRICE_INPUT_PER_MTOK
        + output_tokens / 1_000_000 * _PRICE_OUTPUT_PER_MTOK
    )
    return base * _BATCH_DISCOUNT if batch else base


def _build_user_prompt(skill_path: Path, current_content: str) -> str:
    rel_path = skill_path.relative_to(_PROJECT_ROOT)
    today = datetime.now().strftime("%Y-%m-%d")
    return (
        f"Arquivo: `{rel_path}`\n"
        f"Data de hoje: {today}\n\n"
        f"SKILL.md ATUAL:\n\n{current_content}\n\n"
        f"Busque documentação atualizada da biblioteca/ferramenta correspondente e "
        f"devolva o arquivo atualizado conforme as regras do system prompt."
    )


def _build_batch_request(skill_path: Path, custom_id: str, model: str) -> dict:
    """Monta uma entrada de batch para uma skill."""
    current_content = skill_path.read_text(encoding="utf-8")
    return {
        "custom_id": custom_id,
        "params": {
            "model": model,
            "max_tokens": 8_000,
            "system": _SYSTEM_PROMPT,
            "tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}],
            "messages": [
                {"role": "user", "content": _build_user_prompt(skill_path, current_content)}
            ],
        },
    }


def _process_batch_result(skill_path: Path, message) -> dict:
    """Processa o Message de um item succeeded do batch e escreve o SKILL.md atualizado."""
    rel_path = skill_path.relative_to(_PROJECT_ROOT)
    response_text = "".join(
        block.text for block in message.content if getattr(block, "type", None) == "text"
    )
    cost = _estimate_cost(message.usage.input_tokens, message.usage.output_tokens, batch=True)

    if response_text.strip().startswith("NO_CHANGE"):
        return {"skill": str(rel_path), "status": "no_change", "cost": cost, "preview": ""}

    updated = _extract_updated_skill(response_text)
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


async def _submit_and_poll_batch(client, requests: list[dict]) -> str:
    """Submete um batch e aguarda até ended. Retorna o batch_id."""
    import asyncio as _asyncio

    batch = await client.messages.batches.create(requests=requests)
    batch_id = batch.id
    logger.info(f"Batch submetido: {batch_id} ({len(requests)} requests)")
    print(f"  Batch ID: {batch_id} (pode ser cancelado com `anthropic batches cancel {batch_id}`)")

    elapsed = 0
    while elapsed < _BATCH_TIMEOUT_S:
        batch = await client.messages.batches.retrieve(batch_id)
        if batch.processing_status == "ended":
            return batch_id
        counts = batch.request_counts
        print(
            f"  ⏳ processing… succeeded={counts.succeeded} "
            f"errored={counts.errored} expired={counts.expired} "
            f"canceled={counts.canceled} processing={counts.processing}",
            flush=True,
        )
        await _asyncio.sleep(_BATCH_POLL_INTERVAL_S)
        elapsed += _BATCH_POLL_INTERVAL_S

    raise TimeoutError(f"Batch {batch_id} não concluiu em {_BATCH_TIMEOUT_S}s (SLA 24h)")


async def run_refresh(
    domains: list[str],
    interval_days: int,
    force: bool = False,
    dry_run: bool = False,
    model: str | None = None,
) -> dict:
    """Executa o refresh de todas as skills dos domínios via Batch API (50% desconto)."""
    from anthropic import AsyncAnthropic

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
        "batch_id": None,
    }

    if not skill_paths:
        logger.warning(f"Nenhuma SKILL.md encontrada para os domínios: {domains}")
        return metrics

    print(f"\n{'=' * 60}")
    print(f"Skill Refresh — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"Modelo: {model} (via Batch API, 50% desconto)")
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

    # custom_id → skill_path para mapear resultados do batch de volta aos arquivos
    id_to_path: dict[str, Path] = {}
    requests: list[dict] = []
    for i, skill_path in enumerate(to_refresh):
        custom_id = f"skill-{i:03d}"
        id_to_path[custom_id] = skill_path
        requests.append(_build_batch_request(skill_path, custom_id, model))

    print(f"\nSubmetendo batch com {len(requests)} skills ao Anthropic...\n")

    client = AsyncAnthropic()
    try:
        batch_id = await _submit_and_poll_batch(client, requests)
    except Exception as e:
        logger.error(f"Falha no batch: {e}")
        metrics["errors"] = len(to_refresh)
        metrics["details"].append({"status": "batch_error", "error": str(e)})
        return metrics

    metrics["batch_id"] = batch_id
    print(f"\nBatch {batch_id} concluído. Processando resultados...\n")

    # results() é um iterador assíncrono quando usado com AsyncAnthropic
    async for entry in await client.messages.batches.results(batch_id):
        custom_id = entry.custom_id
        skill_path = id_to_path.get(custom_id)
        if skill_path is None:
            logger.warning(f"custom_id desconhecido no resultado: {custom_id}")
            continue
        rel = skill_path.relative_to(_PROJECT_ROOT)

        if entry.result.type != "succeeded":
            err_type = entry.result.type
            err_detail = getattr(entry.result, "error", None)
            print(f"  ✗ {rel} — {err_type}: {err_detail}")
            metrics["errors"] += 1
            metrics["details"].append(
                {"skill": str(rel), "status": err_type, "error": str(err_detail)}
            )
            continue

        result = _process_batch_result(skill_path, entry.result.message)
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
        f"Custo: ${metrics['cost']:.4f} (Batch API)"
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
            model=args.model,
        )
    )


if __name__ == "__main__":
    main()

"""
Config Snapshot — Snapshot imutável de configuração no startup (Ch. 12).

Inspirado no capítulo 12 de "Claude Code from Source": capturar um snapshot
imutável das configurações críticas no momento do startup permite detectar
drift de configuração em runtime — sintoma comum de prompt injection attacks
que tentam mudar o modelo ou os parâmetros de custo/segurança durante a sessão.

Uso:
    from config.settings import settings
    from config.snapshot import freeze, detect_drift

    # No startup, antes de aceitar qualquer input:
    _startup_snapshot = freeze(settings)

    # Mais tarde, para verificar integridade:
    drifts = detect_drift(settings, _startup_snapshot)
    if drifts:
        logger.error(f"Drift de configuração detectado: {drifts}")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from config.settings import Settings

logger = logging.getLogger("data_agents.config.snapshot")


@dataclass(frozen=True)
class ConfigSnapshot:
    """
    Snapshot imutável das configurações críticas em tempo de startup (Ch. 12).

    Usando frozen=True, qualquer tentativa de mutação lança FrozenInstanceError —
    o snapshot é literalmente imutável após a criação.

    Os dicionários de tier maps são convertidos para tuplas ordenadas de pares
    para que o dataclass seja hashable e comparável sem referência.
    """

    default_model: str
    max_turns: int
    max_budget_usd: float
    tier_model_map: tuple[tuple[str, str], ...]
    tier_turns_map: tuple[tuple[str, int], ...]
    tier_effort_map: tuple[tuple[str, str], ...]
    inject_kb_index: bool
    memory_enabled: bool
    created_at: str  # ISO 8601 UTC


def freeze(settings: Settings) -> ConfigSnapshot:
    """
    Cria um snapshot imutável das configurações críticas de startup.

    Deve ser chamado uma única vez antes de aceitar qualquer input do usuário.
    O snapshot é usado como referência de comparação para detect_drift().

    Args:
        settings: Instância do Settings carregada do .env.

    Returns:
        ConfigSnapshot imutável com os valores atuais das configurações.
    """
    snapshot = ConfigSnapshot(
        default_model=settings.default_model,
        max_turns=settings.max_turns,
        max_budget_usd=settings.max_budget_usd,
        tier_model_map=tuple(sorted(settings.tier_model_map.items())),
        tier_turns_map=tuple(sorted(settings.tier_turns_map.items())),
        tier_effort_map=tuple(sorted(settings.tier_effort_map.items())),
        inject_kb_index=settings.inject_kb_index,
        memory_enabled=settings.memory_enabled,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    logger.debug(
        f"Config snapshot criado: model={snapshot.default_model}, "
        f"max_turns={snapshot.max_turns}, budget=${snapshot.max_budget_usd}"
    )
    return snapshot


def detect_drift(settings: Settings, snapshot: ConfigSnapshot) -> list[str]:
    """
    Detecta diferenças entre o estado atual do settings e o snapshot de startup.

    Útil para identificar prompt injection attacks que tentam alterar o modelo,
    orçamento ou políticas de segurança em runtime.

    Args:
        settings: Instância atual do Settings.
        snapshot: Snapshot imutável criado no startup via freeze().

    Returns:
        Lista de strings descrevendo cada campo que divergiu. Vazio = sem drift.
    """
    drifts: list[str] = []

    if settings.default_model != snapshot.default_model:
        drifts.append(f"default_model: {snapshot.default_model!r} → {settings.default_model!r}")

    if settings.max_turns != snapshot.max_turns:
        drifts.append(f"max_turns: {snapshot.max_turns} → {settings.max_turns}")

    if settings.max_budget_usd != snapshot.max_budget_usd:
        drifts.append(f"max_budget_usd: {snapshot.max_budget_usd} → {settings.max_budget_usd}")

    if settings.inject_kb_index != snapshot.inject_kb_index:
        drifts.append(f"inject_kb_index: {snapshot.inject_kb_index} → {settings.inject_kb_index}")

    if settings.memory_enabled != snapshot.memory_enabled:
        drifts.append(f"memory_enabled: {snapshot.memory_enabled} → {settings.memory_enabled}")

    current_tier_model = tuple(sorted(settings.tier_model_map.items()))
    if current_tier_model != snapshot.tier_model_map:
        drifts.append(
            f"tier_model_map: {dict(snapshot.tier_model_map)!r} → {settings.tier_model_map!r}"
        )

    current_tier_turns = tuple(sorted(settings.tier_turns_map.items()))
    if current_tier_turns != snapshot.tier_turns_map:
        drifts.append(
            f"tier_turns_map: {dict(snapshot.tier_turns_map)!r} → {settings.tier_turns_map!r}"
        )

    current_tier_effort = tuple(sorted(settings.tier_effort_map.items()))
    if current_tier_effort != snapshot.tier_effort_map:
        drifts.append(
            f"tier_effort_map: {dict(snapshot.tier_effort_map)!r} → {settings.tier_effort_map!r}"
        )

    if drifts:
        logger.error(
            f"🚨 DRIFT DE CONFIGURAÇÃO DETECTADO ({len(drifts)} campos): {drifts}. "
            f"Possível prompt injection ou mutação de runtime."
        )
    else:
        logger.debug("Config drift check: sem alterações desde o snapshot de startup.")

    return drifts

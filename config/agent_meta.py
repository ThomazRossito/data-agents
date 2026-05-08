"""
config/agent_meta.py — Fonte única de verdade para metadados de agentes.

Exporta funções cacheadas que lêem dinamicamente do registry (agents/registry/*.md),
eliminando duplicação de AGENT_TIERS e KNOWN_AGENTS espalhados por main.py,
commands/party.py, ui/ui_config.py e workflow/dag.py.

Importação lazy: preload_registry() só é chamado na primeira invocação de cada
função; depois o resultado é cacheado via lru_cache (sem overhead de I/O).
"""

from functools import lru_cache


@lru_cache(maxsize=1)
def get_agent_tiers() -> dict[str, str]:
    """Retorna mapeamento {agent_name: tier} lido do registry (cacheado)."""
    from agents.loader import preload_registry

    return {name: meta.tier for name, meta in preload_registry().items() if meta.tier}


@lru_cache(maxsize=1)
def get_known_agents() -> frozenset[str]:
    """Retorna frozenset com todos os nomes de agentes do registry (cacheado)."""
    from agents.loader import preload_registry

    return frozenset(preload_registry().keys())

"""
Loader do mapa de delegação declarativo (`agents/delegation_map.yaml`).

Expõe:
  - `load_delegation_map()` → lista de `Route` carregada do YAML
  - `render_routing_table()` → markdown da tabela "Situação → Agente"
    (usada por `kb/task_routing.md` §2)
  - `classify(text)`         → matching simples por keywords (heurística, não LLM)

Fonte única de verdade: `agents/delegation_map.yaml`.
"""

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Route:
    situation: str
    agent: str
    tier: str
    keywords: tuple[str, ...] = field(default_factory=tuple)


_YAML_PATH = Path(__file__).resolve().parent / "delegation_map.yaml"


@lru_cache(maxsize=1)
def load_delegation_map() -> tuple[Route, ...]:
    """Carrega e valida o YAML. Cacheado — reiniciar o processo para recarregar."""
    with _YAML_PATH.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    routes = []
    for entry in data.get("routes", []):
        routes.append(
            Route(
                situation=entry["situation"],
                agent=entry["agent"],
                tier=entry.get("tier", ""),
                keywords=tuple(entry.get("keywords") or ()),
            )
        )
    return tuple(routes)


def render_routing_table() -> str:
    """Gera o markdown da tabela usada em kb/task_routing.md §2."""
    routes = load_delegation_map()
    sit_w = max(len(r.situation) for r in routes)
    agent_w = max(len(r.agent) for r in routes)
    sit_w = max(sit_w, len("Situação"))
    agent_w = max(agent_w, len("Agente a Acionar"))

    lines = [
        f"| {'Situação'.ljust(sit_w)} | {'Agente a Acionar'.ljust(agent_w)} |",
        f"|{'-' * (sit_w + 2)}|{'-' * (agent_w + 2)}|",
    ]
    for r in routes:
        lines.append(f"| {r.situation.ljust(sit_w)} | {r.agent.ljust(agent_w)} |")
    return "\n".join(lines)


def classify(text: str) -> str | None:
    """
    Heurística simples: retorna o agente cuja primeira keyword aparecer em `text`.
    Útil para pré-classificação determinística antes de chamar o LLM.
    Não substitui o Supervisor — é fallback/telemetria.
    """
    text_lower = text.lower()
    for route in load_delegation_map():
        for kw in route.keywords:
            if kw.lower() in text_lower:
                return route.agent
    return None

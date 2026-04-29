"""memory.kg — Knowledge Graph de linhagem de dados.

Armazena entidades (tabelas, pipelines, decisões) e relações tipadas
(FEEDS_INTO, DEPENDS_ON, etc.) em JSON persistente.

Uso básico:
    kg = KnowledgeGraph()
    kg.add_entity("raw_orders", "TABLE", layer="raw")
    kg.add_relation("raw_orders", "brz_orders", "FEEDS_INTO")
    print(kg.format_lineage("raw_orders"))
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("data_agents.memory.kg")

_KG_FILE = Path(__file__).parent / "data" / "kg" / "graph.json"

ENTITY_TYPES = frozenset({"TABLE", "PIPELINE", "DECISION", "COLUMN", "SCHEMA"})
RELATION_TYPES = frozenset({"FEEDS_INTO", "DEPENDS_ON", "OWNED_BY", "CONTAINS"})

# Regex para detectar nomes de tabela Medallion
_TABLE_PATTERN = re.compile(
    r"\b(raw|brz|slv|gld|bronze|silver|gold)_[a-z][a-z0-9_]{1,60}\b",
    re.IGNORECASE,
)
# Fluxo explícito: "X -> Y", "X → Y", "X feeds Y"
_FLOW_PATTERN = re.compile(
    r"((?:raw|brz|slv|gld|bronze|silver|gold)_[a-z][a-z0-9_]{1,60})"
    r"\s*(?:->|→|feeds|para|into)\s*"
    r"((?:raw|brz|slv|gld|bronze|silver|gold)_[a-z][a-z0-9_]{1,60})",
    re.IGNORECASE,
)
# INSERT INTO X ... FROM Y
_INSERT_PATTERN = re.compile(
    r"INSERT\s+(?:INTO\s+)?([\w.]+)"
    r".*?(?:FROM|JOIN)\s+([\w.]+)",
    re.IGNORECASE | re.DOTALL,
)


@dataclass
class KGEntity:
    id: str
    type: str
    props: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )


@dataclass
class KGRelation:
    from_id: str
    to_id: str
    type: str
    created_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )


class KnowledgeGraph:
    """Grafo de entidades e relações — persistido em JSON."""

    def __init__(self, path: Path | str | None = None) -> None:
        self._path = Path(path) if path is not None else _KG_FILE
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._entities: dict[str, KGEntity] = {}
        self._relations: list[KGRelation] = []
        self._load()

    # ── Persistência ────────────────────────────────────────────────────────

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            for e in data.get("entities", []):
                ent = KGEntity(
                    id=e["id"],
                    type=e["type"],
                    props=e.get("props", {}),
                    created_at=e.get("created_at", ""),
                )
                self._entities[ent.id] = ent
            for r in data.get("relations", []):
                self._relations.append(
                    KGRelation(
                        from_id=r["from_id"],
                        to_id=r["to_id"],
                        type=r["type"],
                        created_at=r.get("created_at", ""),
                    )
                )
        except (json.JSONDecodeError, KeyError) as exc:
            logger.warning("KG corrompido, iniciando vazio: %s", exc)

    def _save(self) -> None:
        data = {
            "entities": [
                {
                    "id": e.id,
                    "type": e.type,
                    "props": e.props,
                    "created_at": e.created_at,
                }
                for e in self._entities.values()
            ],
            "relations": [
                {
                    "from_id": r.from_id,
                    "to_id": r.to_id,
                    "type": r.type,
                    "created_at": r.created_at,
                }
                for r in self._relations
            ],
        }
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        os.replace(tmp, self._path)

    # ── Escrita ─────────────────────────────────────────────────────────────

    def add_entity(
        self,
        entity_id: str,
        entity_type: str,
        **props: Any,
    ) -> None:
        if entity_type not in ENTITY_TYPES:
            logger.warning("Tipo de entidade desconhecido: %s", entity_type)
        with self._lock:
            if entity_id not in self._entities:
                self._entities[entity_id] = KGEntity(
                    id=entity_id, type=entity_type, props=props
                )
                self._save()

    def add_relation(
        self,
        from_id: str,
        to_id: str,
        relation_type: str,
    ) -> None:
        if relation_type not in RELATION_TYPES:
            logger.warning("Tipo de relação desconhecido: %s", relation_type)
        for entity_id in (from_id, to_id):
            if entity_id not in self._entities:
                self.add_entity(entity_id, "TABLE")
        with self._lock:
            already = any(
                r.from_id == from_id
                and r.to_id == to_id
                and r.type == relation_type
                for r in self._relations
            )
            if not already:
                self._relations.append(
                    KGRelation(from_id=from_id, to_id=to_id, type=relation_type)
                )
                self._save()

    # ── Leitura ─────────────────────────────────────────────────────────────

    def upstream(self, entity_id: str) -> list[str]:
        """Entidades que alimentam entity_id (FEEDS_INTO + DEPENDS_ON)."""
        return [
            r.from_id
            for r in self._relations
            if r.to_id == entity_id
            and r.type in {"FEEDS_INTO", "DEPENDS_ON"}
        ]

    def downstream(self, entity_id: str) -> list[str]:
        """Entidades alimentadas por entity_id."""
        return [
            r.to_id
            for r in self._relations
            if r.from_id == entity_id
            and r.type in {"FEEDS_INTO", "DEPENDS_ON"}
        ]

    def neighbors(self, entity_id: str) -> list[tuple[str, str, str]]:
        """Todas as relações de entity_id: (from, to, type)."""
        return [
            (r.from_id, r.to_id, r.type)
            for r in self._relations
            if r.from_id == entity_id or r.to_id == entity_id
        ]

    def all_entities(
        self, entity_type: str | None = None
    ) -> list[KGEntity]:
        entities = list(self._entities.values())
        if entity_type:
            entities = [e for e in entities if e.type == entity_type]
        return entities

    def get_entity(self, entity_id: str) -> KGEntity | None:
        return self._entities.get(entity_id)

    # ── Formatação ──────────────────────────────────────────────────────────

    def format_lineage(self, entity_id: str) -> str:
        """Formata upstream/downstream de uma entidade para injeção em contexto."""
        if entity_id not in self._entities:
            return f"Entidade `{entity_id}` não encontrada no Knowledge Graph."

        entity = self._entities[entity_id]
        lines = [
            f"## Linhagem: `{entity_id}` [{entity.type}]",
        ]
        if entity.props:
            for k, v in entity.props.items():
                lines.append(f"  {k}: {v}")

        ups = self.upstream(entity_id)
        downs = self.downstream(entity_id)
        all_rels = self.neighbors(entity_id)

        if ups:
            lines.append(f"\n### Upstream ({len(ups)})")
            for u in ups:
                etype = self._entities.get(u, KGEntity(u, "?")).type
                lines.append(f"  ← {u} [{etype}]")

        if downs:
            lines.append(f"\n### Downstream ({len(downs)})")
            for d in downs:
                etype = self._entities.get(d, KGEntity(d, "?")).type
                lines.append(f"  → {d} [{etype}]")

        other = [
            r for r in all_rels
            if r[2] not in {"FEEDS_INTO", "DEPENDS_ON"}
        ]
        if other:
            lines.append("\n### Outras relações")
            for f, t, rt in other:
                lines.append(f"  {f} --[{rt}]--> {t}")

        return "\n".join(lines)

    def summary(self) -> str:
        n_ent = len(self._entities)
        n_rel = len(self._relations)
        tables = [e for e in self._entities.values() if e.type == "TABLE"]
        return (
            f"KG: {n_ent} entidades, {n_rel} relações, "
            f"{len(tables)} tabelas"
        )


# ── Extração automática ──────────────────────────────────────────────────────

def extract_lineage_from_text(
    text: str,
    kg: KnowledgeGraph,
    require_explicit_flow: bool = True,
) -> None:
    """
    Extrai relações de linhagem de texto livre e popula o KG.

    Detecta:
    - "X -> Y" / "X → Y" / "X feeds Y" / "X para Y"
    - INSERT INTO X ... FROM Y

    Args:
        require_explicit_flow: Se True (default), só popula o KG quando o texto
            contém relacção explícita (FLOW ou INSERT). Evita ruído de tabelas
            mencionadas isoladamente como "raw_data", "bronze_xxx".
    """
    has_explicit = False

    # Fluxos explícitos
    for match in _FLOW_PATTERN.finditer(text):
        has_explicit = True
        src = match.group(1).lower()
        tgt = match.group(2).lower()
        _infer_entity(src, kg)
        _infer_entity(tgt, kg)
        kg.add_relation(src, tgt, "FEEDS_INTO")

    # INSERT INTO ... FROM ...
    for match in _INSERT_PATTERN.finditer(text):
        tgt = match.group(1).lower().split(".")[-1]
        src = match.group(2).lower().split(".")[-1]
        if _TABLE_PATTERN.match(tgt) and _TABLE_PATTERN.match(src):
            has_explicit = True
            _infer_entity(src, kg)
            _infer_entity(tgt, kg)
            kg.add_relation(src, tgt, "FEEDS_INTO")

    # Tabelas Medallion isoladas — só registra se require_explicit_flow=False
    # ou se o texto já demonstrou linhagem explícita
    if not require_explicit_flow or has_explicit:
        for match in _TABLE_PATTERN.finditer(text):
            name = match.group(0).lower()
            if kg.get_entity(name) is None:
                _infer_entity(name, kg)


def _infer_entity(name: str, kg: KnowledgeGraph) -> None:
    prefix = name.split("_")[0].lower()
    layer_map = {
        "raw": "raw", "brz": "bronze", "bronze": "bronze",
        "slv": "silver", "silver": "silver",
        "gld": "gold", "gold": "gold",
    }
    layer = layer_map.get(prefix, "unknown")
    kg.add_entity(name, "TABLE", layer=layer)

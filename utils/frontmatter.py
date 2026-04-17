"""
Parser de frontmatter YAML para arquivos Markdown.

Centraliza a lógica de parsing compartilhada entre agents/loader.py e memory/store.py.
Suporta o subset de YAML usado nos arquivos .md do projeto:
  - Strings simples e com aspas (simples ou duplas)
  - Listas inline: [item1, item2]
  - Booleanos: true / false
  - Números inteiros e floats (incluindo negativos)
  - None / vazio
  - URLs: valores com múltiplos ':' são preservados corretamente
  - Strings numéricas: aspas preservam o tipo ("123" → "123", não 123)
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger("data_agents.utils.frontmatter")

_FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)", re.DOTALL)


def parse_yaml_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """
    Faz o parse de frontmatter YAML de um arquivo Markdown.

    Args:
        content: Conteúdo completo do arquivo (incluindo frontmatter).

    Returns:
        Tupla (metadata, body) onde metadata é o dict do frontmatter
        e body é o conteúdo após o segundo '---'.

    Raises:
        ValueError: Se o arquivo não tiver frontmatter YAML válido.
    """
    match = _FRONTMATTER_PATTERN.match(content)
    if not match:
        raise ValueError("Arquivo sem frontmatter YAML válido (esperado: --- ... ---)")

    yaml_block = match.group(1)
    body = match.group(2).strip()

    metadata: dict[str, Any] = {}
    for line in yaml_block.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue

        key, _, raw_value = line.partition(":")
        key = key.strip()
        raw_value = raw_value.strip()

        metadata[key] = _parse_yaml_value(raw_value)

    return metadata, body


def _parse_yaml_value(raw: str) -> Any:
    """Converte um valor YAML simples para o tipo Python adequado."""
    if not raw or raw.lower() == "none":
        return None

    # Lista inline: [item1, item2, ...]
    if raw.startswith("[") and raw.endswith("]"):
        items = raw[1:-1].split(",")
        return [i.strip().strip('"').strip("'") for i in items if i.strip()]

    # String entre aspas duplas — preserva tipo (ex: "123" permanece string)
    if raw.startswith('"') and raw.endswith('"') and len(raw) >= 2:
        return raw[1:-1]

    # String entre aspas simples
    if raw.startswith("'") and raw.endswith("'") and len(raw) >= 2:
        return raw[1:-1]

    # Booleanos
    if raw.lower() == "true":
        return True
    if raw.lower() == "false":
        return False

    # URL ou valor com múltiplos ':' — retorna como string sem tentar converter
    # (ex: https://example.com, 2024-01-01T00:00:00+00:00)
    if raw.count(":") > 0 and (raw.startswith("http") or raw.startswith("/")):
        return raw

    # Float: contém ponto decimal e é numérico (aceita negativos)
    if "." in raw:
        stripped = raw.lstrip("-")
        if stripped.replace(".", "", 1).isdigit():
            try:
                return float(raw)
            except ValueError:
                pass

    # Int: é numérico (aceita negativos)
    stripped = raw.lstrip("-")
    if stripped.isdigit() and stripped:
        try:
            return int(raw)
        except ValueError:
            pass

    # Fallback: string literal
    return raw

# Padrão: Validation Prompts

## Contexto

Validar output de LLM antes de usar downstream. Evita alucinações em nomes de colunas, schemas e código SQL usando Pydantic como schema de validação.

## Solução

```python
from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, field_validator


class ColumnDefinition(BaseModel):
    name: str
    data_type: Literal["STRING", "INTEGER", "BIGINT", "DOUBLE", "TIMESTAMP", "BOOLEAN"]
    nullable: bool = True
    pii: bool = False


class TableSchema(BaseModel):
    table_name: str
    layer: Literal["brz_", "slv_", "gld_", "mrt_"]
    columns: list[ColumnDefinition]

    @field_validator("table_name")
    @classmethod
    def validate_naming(cls, v: str) -> str:
        if not v.islower() or " " in v:
            raise ValueError(f"table_name deve ser snake_case: {v!r}")
        return v


def validate_llm_schema(raw_llm_output: str) -> TableSchema:
    """Converte output JSON do LLM em schema validado ou lança ValueError."""
    try:
        data = json.loads(raw_llm_output)
        return TableSchema.model_validate(data)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(
            f"Output do LLM inválido: {exc}\n\nOutput recebido:\n{raw_llm_output}"
        ) from exc
```

## Tradeoffs

| Vantagem | Desvantagem |
|----------|------------|
| Detecta alucinações antes de usar | LLM precisa ser instruído a retornar JSON |
| Schema versionável e testável | Mais código de plumbing |
| Reutiliza Pydantic (já no projeto) | Nem todo output é estruturável |

## Related

- [agent-prompt-template.md](agent-prompt-template.md)
- [../specs/prompt-formats.yaml](../specs/prompt-formats.yaml)

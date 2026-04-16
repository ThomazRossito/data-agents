# Estruturas de Dados Python — Quando Usar Cada Uma

## Mapa de Decisão

```
Precisa de validação de dados externos?        → Pydantic BaseModel
Precisa ler de env vars / .env?                → Pydantic BaseSettings
Estrutura interna sem validação, com métodos?  → dataclass
Estrutura imutável e hashável?                 → NamedTuple ou frozen dataclass
Dict passado entre funções com tipos fixos?    → TypedDict
Conjunto de valores nomeados constantes?       → Enum / StrEnum
```

## dataclass — Padrão para Estruturas Internas

```python
from dataclasses import dataclass, field

@dataclass(slots=True)          # slots=True reduz memória ~40% em alta frequência
class Pipeline:
    name: str
    source: str
    target: str
    retries: int = 3
    tags: list[str] = field(default_factory=list)

    def is_valid(self) -> bool:
        return bool(self.name and self.source and self.target)
```

`frozen=True` torna a instância imutável e hashável (usável em sets/dict keys):

```python
@dataclass(frozen=True, slots=True)
class TableRef:
    catalog: str
    schema: str
    table: str

    def fqn(self) -> str:
        return f"{self.catalog}.{self.schema}.{self.table}"
```

## Pydantic v2 — Validação e Serialização

```python
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic import ConfigDict

class DatasetConfig(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)
    path: str
    format: Literal["parquet", "csv", "delta"]
    partition_cols: list[str] = Field(default_factory=list)

    @field_validator("path")
    @classmethod
    def path_must_be_absolute(cls, v: str) -> str:
        if not v.startswith("/") and not v.startswith("abfss://"):
            raise ValueError("path must be absolute or abfss://")
        return v

    @model_validator(mode="after")
    def csv_has_no_partitions(self) -> "DatasetConfig":
        if self.format == "csv" and self.partition_cols:
            raise ValueError("CSV format does not support partition_cols")
        return self
```

### Pydantic BaseSettings — Configuração via Env

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str
    api_key: str
    max_retries: int = 3
    debug: bool = False

settings = AppSettings()  # lê automaticamente de env vars / .env
```

## NamedTuple — Tuplas Nomeadas Imutáveis

Use quando a estrutura é simples, imutável e precisa ser desempacotada ou usada como chave:

```python
from typing import NamedTuple

class Coordinate(NamedTuple):
    lat: float
    lon: float
    altitude: float = 0.0

coord = Coordinate(lat=-23.5, lon=-46.6)
lat, lon = coord          # desempacotamento funciona
d = {coord: "São Paulo"}  # hashável — pode ser chave de dict
```

## Enum — Valores Constantes

```python
from enum import StrEnum, auto

class LayerEnum(StrEnum):
    BRONZE = auto()   # valor = "bronze"
    SILVER = auto()
    GOLD = auto()

# StrEnum: comparação com string funciona diretamente
assert LayerEnum.BRONZE == "bronze"
```

## Anti-Padrões a Evitar

```python
# ❌ dict genérico sem tipo
config = {"host": "localhost", "port": 5432}

# ✅ TypedDict ou dataclass
class DbConfig(TypedDict):
    host: str
    port: int

# ❌ tuple sem nome
def get_bounds() -> tuple:
    return (0, 100)

# ✅ NamedTuple ou dataclass
class Bounds(NamedTuple):
    min: float
    max: float

# ❌ Pydantic para estruturas internas sem validação (overhead desnecessário)
class InternalCounter(BaseModel):
    value: int = 0

# ✅ dataclass simples
@dataclass
class InternalCounter:
    value: int = 0
```

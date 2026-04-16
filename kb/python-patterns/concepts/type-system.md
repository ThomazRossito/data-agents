# Type System Python Moderno

## Hierarquia de Tipos — Quando Usar

```
Any          ← nunca em código interno; só em boundaries de sistema
object       ← base, evitar como hint
Union / |    ← Python 3.10+: int | str | None
Optional[T]  ← equivale a T | None; preferir T | None em 3.10+
```

### Generics

```python
from typing import TypeVar, Generic

T = TypeVar("T")
K = TypeVar("K")
V = TypeVar("V")

class Repository(Generic[T]):
    def get(self, id: int) -> T | None: ...
    def list(self) -> list[T]: ...
```

### Protocol — Duck Typing Estrutural

Use `Protocol` quando não controla a classe concreta (bibliotecas externas, injeção):

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class Readable(Protocol):
    def read(self, n: int = -1) -> bytes: ...

def process(source: Readable) -> bytes:
    return source.read()
```

### ParamSpec — Decorators com Tipagem Preservada

```python
from typing import ParamSpec, TypeVar, Callable
import functools

P = ParamSpec("P")
R = TypeVar("R")

def retry(times: int) -> Callable[[Callable[P, R]], Callable[P, R]]:
    def decorator(fn: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(fn)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            for attempt in range(times):
                try:
                    return fn(*args, **kwargs)
                except Exception:
                    if attempt == times - 1:
                        raise
            raise RuntimeError("unreachable")
        return wrapper
    return decorator
```

### TypedDict — Dicts com Shape Conhecido

```python
from typing import TypedDict, Required, NotRequired

class Config(TypedDict):
    host: Required[str]
    port: Required[int]
    timeout: NotRequired[float]  # chave opcional
```

### Pydantic v2 vs dataclass vs TypedDict

| Cenário | Escolha | Motivo |
|---------|---------|--------|
| Dados externos (API, arquivo, env) | Pydantic BaseModel | Validação + coerção + serialização |
| Configuração da aplicação | Pydantic BaseSettings | Lê de env vars automaticamente |
| Estrutura interna sem validação | dataclass | Overhead zero, suporte a `__slots__` |
| Dict passado entre funções com shape fixo | TypedDict | Compatível com dicts existentes |
| Enum com comportamento | Enum/IntEnum | Type safe + iterável |

## mypy strict — Configuração Mínima

```toml
# pyproject.toml
[tool.mypy]
strict = true
warn_return_any = true
warn_unused_ignores = true
no_implicit_reexport = true
```

Erros comuns com `strict` e como resolver:

```python
# ❌ erro: Missing return type annotation
def load(path):
    ...

# ✅
def load(path: str | Path) -> dict[str, Any]:
    ...

# ❌ erro: Argument 1 has incompatible type "str | None"
def parse(text: str) -> int:
    return int(text)

# ✅
def parse(text: str | None) -> int | None:
    return int(text) if text is not None else None
```

## Regras de Ouro

1. **Nunca use `Any` em código interno** — use `object` como fallback ou crie um Protocol.
2. **Prefira `T | None` a `Optional[T]`** em Python 3.10+.
3. **`__all__` em todo módulo público** — controla o que `mypy` e IDEs expõem.
4. **`TypeGuard` para narrowing manual** quando isinstance não for suficiente.

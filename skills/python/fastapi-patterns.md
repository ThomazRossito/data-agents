# FastAPI — Padrões e Boas Práticas

## Estrutura de Projeto

```
app/
  main.py           # lifespan, app factory
  routers/
    users.py        # APIRouter por domínio
    items.py
  models/
    user.py         # Pydantic v2 schemas (input/output separados)
  services/
    user_service.py # lógica de negócio (sem HTTP context)
  dependencies.py   # Depends() reutilizáveis
  config.py         # BaseSettings para env vars
```

## App Factory com Lifespan

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    yield
    # shutdown

def create_app() -> FastAPI:
    app = FastAPI(title="API", lifespan=lifespan)
    app.include_router(router, prefix="/v1")
    return app

app = create_app()
```

## Pydantic v2 — Schemas

```python
from pydantic import BaseModel, Field, model_validator

class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: str

class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    model_config = {"from_attributes": True}  # ORM mode
```

## Dependency Injection

```python
from fastapi import Depends, HTTPException, status
from typing import Annotated

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    ...

CurrentUser = Annotated[User, Depends(get_current_user)]

@router.get("/me")
async def read_me(user: CurrentUser) -> UserResponse:
    return user
```

## Error Handling

```python
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})
```

## Configuração via BaseSettings

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    secret_key: str
    debug: bool = False
    model_config = {"env_file": ".env"}

settings = Settings()
```

## Anti-padrões a Evitar

- ❌ Lógica de negócio dentro do endpoint — mova para service
- ❌ `response_model=dict` — use Pydantic
- ❌ `except Exception: pass` — sempre logar ou re-raise
- ❌ Sincronia em endpoints async — use `run_in_executor` para IO bloqueante
- ❌ Importar `settings` no nível do módulo em testes — use `override_settings` fixture

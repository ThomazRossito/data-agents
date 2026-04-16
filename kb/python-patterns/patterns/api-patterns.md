# Padrões de API com FastAPI

## Estrutura de Projeto FastAPI

```
src/myapi/
├── __init__.py
├── main.py            ← cria a app FastAPI + inclui routers
├── routers/
│   ├── __init__.py
│   ├── datasets.py
│   └── pipelines.py
├── models/            ← Pydantic schemas (request/response)
│   ├── __init__.py
│   └── dataset.py
├── services/          ← lógica de negócio (sem HTTP)
│   └── dataset_service.py
└── dependencies.py    ← DI: auth, db, settings
```

## App Factory + Lifespan

```python
# main.py
from contextlib import asynccontextmanager
from typing import AsyncGenerator
import httpx
from fastapi import FastAPI
from myapi.routers import datasets, pipelines

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # startup
    app.state.http_client = httpx.AsyncClient(timeout=30.0)
    yield
    # shutdown
    await app.state.http_client.aclose()

def create_app() -> FastAPI:
    app = FastAPI(
        title="Data API",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.include_router(datasets.router, prefix="/datasets", tags=["datasets"])
    app.include_router(pipelines.router, prefix="/pipelines", tags=["pipelines"])
    return app

app = create_app()
```

## Router com Dependency Injection

```python
# routers/datasets.py
from fastapi import APIRouter, Depends, HTTPException, status
from myapi.dependencies import get_current_user, get_service
from myapi.models.dataset import DatasetCreate, DatasetResponse
from myapi.services.dataset_service import DatasetService

router = APIRouter()

@router.post("/", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
async def create_dataset(
    payload: DatasetCreate,
    service: DatasetService = Depends(get_service),
    user: str = Depends(get_current_user),
) -> DatasetResponse:
    return await service.create(payload, owner=user)

@router.get("/{dataset_id}", response_model=DatasetResponse)
async def get_dataset(
    dataset_id: int,
    service: DatasetService = Depends(get_service),
) -> DatasetResponse:
    dataset = await service.get(dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return dataset
```

## Modelos Pydantic v2

```python
# models/dataset.py
from pydantic import BaseModel, Field, ConfigDict

class DatasetBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    format: Literal["parquet", "csv", "delta"]
    path: str

class DatasetCreate(DatasetBase):
    pass

class DatasetResponse(DatasetBase):
    model_config = ConfigDict(from_attributes=True)  # ORM mode

    id: int
    owner: str
    created_at: datetime
```

## Error Handlers Globais

```python
# main.py
from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )

@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )
```

## Dependency Injection — Auth via Header

```python
# dependencies.py
from fastapi import Header, HTTPException, Depends
from myapi.services.dataset_service import DatasetService

async def get_current_user(x_api_key: str = Header(...)) -> str:
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return "authenticated_user"

def get_service() -> DatasetService:
    return DatasetService(db_url=settings.database_url)
```

## Anti-Padrões

```python
# ❌ Lógica de negócio no router
@router.post("/")
async def create(payload: DatasetCreate):
    conn = create_connection()    # nunca abrir conexão no router
    result = conn.execute(...)    # lógica de DB no router
    return result

# ✅ Delegar para service via DI

# ❌ Retornar dict genérico sem modelo de resposta
@router.get("/{id}")
async def get(id: int):
    return {"id": id, "data": ...}   # sem type check, sem documentação automática

# ✅ response_model explícito

# ❌ Tratar Exception genérica no router
@router.get("/")
async def list_all():
    try:
        return service.list()
    except Exception as e:
        return {"error": str(e)}    # expõe stack trace ao cliente

# ✅ exception_handler global + logging interno
```

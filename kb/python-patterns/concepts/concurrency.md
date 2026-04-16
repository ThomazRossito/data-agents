# Concorrência e Paralelismo Python

## Modelo Mental — Quando Usar Cada Abordagem

```
Tarefa bloqueante por I/O (HTTP, disco, DB)?     → asyncio / async/await
Múltiplas tarefas I/O independentes?              → asyncio.gather() / TaskGroup
CPU-bound (cálculo, compressão, parsing pesado)?  → multiprocessing / ProcessPoolExecutor
I/O bloqueante legado sem suporte async?          → ThreadPoolExecutor (contorna GIL)
Paralelismo simples sem estado compartilhado?     → concurrent.futures (abstração unificada)
```

## asyncio — I/O Concorrente

```python
import asyncio
import httpx

async def fetch(client: httpx.AsyncClient, url: str) -> dict:
    response = await client.get(url, timeout=30.0)
    response.raise_for_status()
    return response.json()

async def fetch_all(urls: list[str]) -> list[dict]:
    async with httpx.AsyncClient() as client:
        # TaskGroup cancela tudo se qualquer tarefa falhar (Python 3.11+)
        async with asyncio.TaskGroup() as tg:
            tasks = [tg.create_task(fetch(client, url)) for url in urls]
    return [t.result() for t in tasks]
```

### asyncio.gather vs TaskGroup

| | `asyncio.gather` | `TaskGroup` (3.11+) |
|---|---|---|
| Cancelamento em falha | manual | automático |
| Return_exceptions | suportado | não |
| Preferência | Python < 3.11 | Python 3.11+ |

### Context Manager Async

```python
from contextlib import asynccontextmanager
from typing import AsyncGenerator

@asynccontextmanager
async def managed_connection(url: str) -> AsyncGenerator[Connection, None]:
    conn = await create_connection(url)
    try:
        yield conn
    finally:
        await conn.close()
```

## concurrent.futures — Abstração Unificada

```python
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed

# I/O bloqueante legado — ThreadPoolExecutor
def download(url: str) -> bytes:
    import urllib.request
    with urllib.request.urlopen(url) as r:
        return r.read()

with ThreadPoolExecutor(max_workers=10) as executor:
    futures = {executor.submit(download, url): url for url in urls}
    for future in as_completed(futures):
        url = futures[future]
        try:
            data = future.result()
        except Exception as e:
            print(f"Failed {url}: {e}")

# CPU-bound — ProcessPoolExecutor
import json

def parse_file(path: str) -> dict:
    with open(path) as f:
        return json.load(f)

with ProcessPoolExecutor() as executor:
    results = list(executor.map(parse_file, file_paths))
```

## threading — Quando Usar

Use `threading` apenas quando:
- Integrando com código que usa callbacks/eventos baseados em threads (ex: `tkinter`, `watchdog`)
- Biblioteca C extension que libera o GIL (numpy, pandas, I/O de arquivo)

```python
import threading

class PeriodicTask:
    def __init__(self, interval: float, fn: Callable[[], None]) -> None:
        self._interval = interval
        self._fn = fn
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.wait(self._interval):
            self._fn()
```

## Anti-Padrões

```python
# ❌ asyncio + time.sleep (bloqueia o event loop)
async def bad():
    time.sleep(1)

# ✅
async def good():
    await asyncio.sleep(1)

# ❌ ProcessPoolExecutor para I/O (overhead de pickling desnecessário)
with ProcessPoolExecutor() as ex:
    ex.map(requests.get, urls)  # I/O → use ThreadPoolExecutor

# ❌ asyncio.run dentro de função async já em execução
async def nested():
    asyncio.run(other_coroutine())  # RuntimeError

# ✅
async def nested():
    await other_coroutine()
    # ou, para rodar em thread separada:
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, blocking_fn)
```

## Regras de Ouro

1. **asyncio para I/O novo** — nunca misturar `time.sleep` com `async def`.
2. **ProcessPoolExecutor para CPU-bound** — GIL impede threading de paralelizar Python puro.
3. **ThreadPoolExecutor para I/O legado** — integração com libs síncronas sem reescrita.
4. **TaskGroup (3.11+) em vez de gather** — cancelamento automático evita tarefas órfãs.
5. **Nunca compartilhar estado mutável entre threads sem lock** — use `threading.Lock` ou `queue.Queue`.

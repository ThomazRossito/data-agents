# asyncio — Padrões e Boas Práticas

## Conceitos Fundamentais

```python
import asyncio

# Coroutine: definição e execução
async def fetch(url: str) -> str:
    await asyncio.sleep(0)  # yield ao event loop
    return url

asyncio.run(fetch("https://exemplo.com"))  # entry point
```

## Paralelismo com gather

```python
import asyncio
import httpx

async def fetch_all(urls: list[str]) -> list[str]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        tasks = [client.get(url) for url in urls]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
    return [
        r.text if not isinstance(r, Exception) else f"ERRO: {r}"
        for r in responses
    ]
```

## Timeout com wait_for

```python
async def fetch_with_timeout(url: str, timeout: float = 5.0) -> str | None:
    try:
        return await asyncio.wait_for(fetch(url), timeout=timeout)
    except asyncio.TimeoutError:
        return None
```

## Task e Cancelamento

```python
async def worker(name: str) -> None:
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        # cleanup antes de propagar
        raise

async def main() -> None:
    task = asyncio.create_task(worker("bg"), name="background")
    await asyncio.sleep(3)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
```

## Queue — Producer/Consumer

```python
async def producer(queue: asyncio.Queue[str], items: list[str]) -> None:
    for item in items:
        await queue.put(item)
    await queue.put(None)  # sentinel

async def consumer(queue: asyncio.Queue[str]) -> list[str]:
    results: list[str] = []
    while (item := await queue.get()) is not None:
        results.append(item.upper())
        queue.task_done()
    return results

async def pipeline(items: list[str]) -> list[str]:
    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=10)
    await asyncio.gather(producer(queue, items), consumer(queue))
    return []
```

## asynccontextmanager

```python
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

@asynccontextmanager
async def managed_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    client = httpx.AsyncClient()
    try:
        yield client
    finally:
        await client.aclose()

async def use() -> None:
    async with managed_client() as client:
        resp = await client.get("https://exemplo.com")
```

## run_in_executor — Código Bloqueante

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=4)

async def read_file(path: str) -> str:
    loop = asyncio.get_running_loop()
    # executa I/O bloqueante sem travar o event loop
    return await loop.run_in_executor(executor, Path(path).read_text)
```

## Semáforo — Limitar Concorrência

```python
sem = asyncio.Semaphore(5)  # máximo 5 requisições simultâneas

async def limited_fetch(client: httpx.AsyncClient, url: str) -> str:
    async with sem:
        resp = await client.get(url)
        return resp.text
```

## Anti-padrões a Evitar

- ❌ `time.sleep()` em código async — trava o event loop; use `await asyncio.sleep()`
- ❌ `asyncio.run()` dentro de função async — use `await` diretamente
- ❌ `asyncio.gather()` sem `return_exceptions=True` quando uma task pode falhar — uma exceção cancela todas
- ❌ `loop.run_until_complete()` — depreciado; use `asyncio.run()` no entry point
- ❌ Criar tasks sem guardar referência — Python pode coletar o lixo prematuramente; use `asyncio.create_task()` e guarde em set/list

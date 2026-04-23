# Chapter 7: Async and Batch Requests

## 7.1 Why Async?

Sync: One request at a time, blocks while waiting.
Async: Multiple requests concurrently, no blocking.

```python
# Sync - 10 requests × 2 seconds = 20 seconds
for prompt in prompts:
    response = client.messages.create(...)  # blocks

# Async - 10 requests concurrently ≈ 2-3 seconds
responses = await asyncio.gather(*[
    async_client.messages.create(...) for prompt in prompts
])
```

## 7.2 Basic Async Usage

```python
import anthropic
import asyncio

client = anthropic.AsyncAnthropic()

async def call_api(prompt: str) -> str:
    response = await client.messages.create(
        model="claude-3-5-sonnet",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text

async def main():
    result = await call_api("Hello!")
    print(result)

asyncio.run(main())
```

## 7.3 Concurrent Requests

```python
async def process_multiple(prompts: list[str]) -> list[str]:
    tasks = [call_api(prompt) for prompt in prompts]
    results = await asyncio.gather(*tasks)
    return results

# Process 10 prompts concurrently
prompts = [f"Summarize topic {i}" for i in range(10)]
results = await process_multiple(prompts)
```

## 7.4 Controlled Concurrency

Limit concurrent requests to avoid overwhelming the API:

```python
async def process_with_semaphore(
    prompts: list[str],
    max_concurrent: int = 5
) -> list[str]:
    semaphore = asyncio.Semaphore(max_concurrent)

    async def bounded_call(prompt: str) -> str:
        async with semaphore:
            return await call_api(prompt)

    tasks = [bounded_call(prompt) for prompt in prompts]
    return await asyncio.gather(*tasks)

# Only 5 requests at a time
results = await process_with_semaphore(prompts, max_concurrent=5)
```

## 7.5 Batch Processing with Progress

```python
from tqdm.asyncio import tqdm

async def batch_process(
    prompts: list[str],
    max_concurrent: int = 10
) -> list[dict]:
    semaphore = asyncio.Semaphore(max_concurrent)
    results = []

    async def process_one(index: int, prompt: str):
        async with semaphore:
            try:
                response = await call_api(prompt)
                return {"index": index, "result": response, "error": None}
            except Exception as e:
                return {"index": index, "result": None, "error": str(e)}

    tasks = [process_one(i, p) for i, p in enumerate(prompts)]

    for coro in tqdm.as_completed(tasks, total=len(tasks)):
        result = await coro
        results.append(result)

    return sorted(results, key=lambda x: x["index"])
```

## 7.6 Error Handling in Batch

```python
async def resilient_batch(
    prompts: list[str],
    max_retries: int = 3
) -> list[dict]:
    results = [None] * len(prompts)

    async def process_with_retry(index: int, prompt: str):
        for attempt in range(max_retries):
            try:
                response = await call_api(prompt)
                return {"success": True, "data": response}
            except anthropic.RateLimitError:
                await asyncio.sleep(2 ** attempt)
            except Exception as e:
                if attempt == max_retries - 1:
                    return {"success": False, "error": str(e)}
        return {"success": False, "error": "Max retries exceeded"}

    tasks = [process_with_retry(i, p) for i, p in enumerate(prompts)]
    results = await asyncio.gather(*tasks)
    return results
```

## 7.7 Streaming in Async

```python
async def stream_response(prompt: str):
    async with client.messages.stream(
        model="claude-3-5-sonnet",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    ) as stream:
        async for text in stream.text_stream:
            yield text

# Usage
async for chunk in stream_response("Write a story"):
    print(chunk, end="")
```

## 7.8 Producer-Consumer Pattern

```python
async def batch_with_queue(
    prompts: list[str],
    num_workers: int = 5
):
    queue = asyncio.Queue()
    results = {}

    # Add all prompts to queue
    for i, prompt in enumerate(prompts):
        await queue.put((i, prompt))

    async def worker(worker_id: int):
        while True:
            try:
                index, prompt = await asyncio.wait_for(
                    queue.get(),
                    timeout=1.0
                )
                response = await call_api(prompt)
                results[index] = response
                queue.task_done()
            except asyncio.TimeoutError:
                break

    # Start workers
    workers = [
        asyncio.create_task(worker(i))
        for i in range(num_workers)
    ]

    # Wait for queue to empty
    await queue.join()

    # Cancel workers
    for w in workers:
        w.cancel()

    return [results[i] for i in range(len(prompts))]
```

## 7.9 Mixing Sync and Async

```python
import asyncio

# Call async from sync
def sync_wrapper(prompt: str) -> str:
    return asyncio.run(call_api(prompt))

# Call sync from async (for blocking operations)
async def async_wrapper(blocking_func, *args):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, blocking_func, *args)
```

## 7.10 Complete Batch Processor

```python
import asyncio
from dataclasses import dataclass
from typing import Callable

@dataclass
class BatchConfig:
    max_concurrent: int = 10
    max_retries: int = 3
    timeout: float = 60.0

class BatchProcessor:
    def __init__(self, client, config: BatchConfig = None):
        self.client = client
        self.config = config or BatchConfig()

    async def process(
        self,
        items: list,
        process_fn: Callable
    ) -> list[dict]:
        semaphore = asyncio.Semaphore(self.config.max_concurrent)
        results = []

        async def process_one(index: int, item):
            async with semaphore:
                for attempt in range(self.config.max_retries):
                    try:
                        async with asyncio.timeout(self.config.timeout):
                            result = await process_fn(item)
                            return {"index": index, "success": True, "data": result}
                    except asyncio.TimeoutError:
                        if attempt == self.config.max_retries - 1:
                            return {"index": index, "success": False, "error": "timeout"}
                    except Exception as e:
                        if attempt == self.config.max_retries - 1:
                            return {"index": index, "success": False, "error": str(e)}
                        await asyncio.sleep(2 ** attempt)

        tasks = [process_one(i, item) for i, item in enumerate(items)]
        results = await asyncio.gather(*tasks)
        return sorted(results, key=lambda x: x["index"])

# Usage
processor = BatchProcessor(client, BatchConfig(max_concurrent=20))

async def summarize(text: str) -> str:
    response = await client.messages.create(
        model="claude-3-5-sonnet",
        max_tokens=500,
        messages=[{"role": "user", "content": f"Summarize: {text}"}]
    )
    return response.content[0].text

results = await processor.process(documents, summarize)
```

## 7.11 Summary

| Pattern | Use Case |
|---------|----------|
| `asyncio.gather` | Simple concurrent execution |
| Semaphore | Limit concurrency |
| Queue + Workers | Complex workflows |
| Streaming | Real-time output |

**Best practices**:
- Use async for any batch operations
- Limit concurrency to respect rate limits
- Handle errors per-item, don't fail entire batch
- Add progress tracking for long batches
- Use timeouts to prevent hanging

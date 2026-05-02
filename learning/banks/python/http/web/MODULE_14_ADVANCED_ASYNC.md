# Module 14: Advanced Async Patterns

## Overview

This module covers advanced patterns for production async applications: structured concurrency, synchronization primitives, mixing sync and async code, and testing.

---

## Learning Objectives

By the end of this module, you will be able to:

1. Use TaskGroups for structured concurrency
2. Apply async synchronization primitives
3. Integrate sync code with async
4. Test async code effectively
5. Debug async applications

---

## 14.1 Structured Concurrency (Python 3.11+)

### TaskGroup

```python
import asyncio

async def fetch(url):
    await asyncio.sleep(1)
    return f"Data from {url}"

async def main():
    async with asyncio.TaskGroup() as tg:
        task1 = tg.create_task(fetch("url1"))
        task2 = tg.create_task(fetch("url2"))
        task3 = tg.create_task(fetch("url3"))

    # All tasks complete when exiting the block
    print(task1.result(), task2.result(), task3.result())

# If any task raises, all are cancelled
async def main_with_error():
    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(fetch("url1"))
            tg.create_task(failing_task())  # Raises
    except* ValueError as eg:
        print(f"Caught errors: {eg.exceptions}")
```

### Exception Groups (Python 3.11+)

```python
# Multiple exceptions from concurrent tasks
try:
    async with asyncio.TaskGroup() as tg:
        tg.create_task(task_that_raises_value_error())
        tg.create_task(task_that_raises_type_error())
except* ValueError as eg:
    for exc in eg.exceptions:
        print(f"ValueError: {exc}")
except* TypeError as eg:
    for exc in eg.exceptions:
        print(f"TypeError: {exc}")
```

---

## 14.2 Synchronization Primitives

### Lock

```python
import asyncio

lock = asyncio.Lock()

async def protected_operation():
    async with lock:
        # Only one coroutine at a time
        await do_something()

# Or explicit acquire/release
async def explicit_lock():
    await lock.acquire()
    try:
        await do_something()
    finally:
        lock.release()
```

### Semaphore

```python
# Limit concurrent operations
semaphore = asyncio.Semaphore(10)  # Max 10 concurrent

async def rate_limited_fetch(url):
    async with semaphore:
        return await fetch(url)

# Bounded semaphore (error if released too many times)
bounded = asyncio.BoundedSemaphore(10)
```

### Event

```python
event = asyncio.Event()

async def waiter():
    print("Waiting for event...")
    await event.wait()
    print("Event received!")

async def setter():
    await asyncio.sleep(2)
    event.set()  # Wake all waiters
```

### Condition

```python
condition = asyncio.Condition()

async def consumer():
    async with condition:
        await condition.wait()  # Release lock, wait, reacquire
        print("Notified!")

async def producer():
    await asyncio.sleep(1)
    async with condition:
        condition.notify()  # Wake one waiter
        # condition.notify_all()  # Wake all waiters
```

### Queue

```python
queue = asyncio.Queue(maxsize=100)

async def producer():
    for i in range(10):
        await queue.put(i)  # Blocks if full
    await queue.put(None)  # Sentinel

async def consumer():
    while True:
        item = await queue.get()  # Blocks if empty
        if item is None:
            break
        print(f"Processing: {item}")
        queue.task_done()

async def main():
    async with asyncio.TaskGroup() as tg:
        tg.create_task(producer())
        tg.create_task(consumer())

    await queue.join()  # Wait for all items processed
```

---

## 14.3 Mixing Sync and Async

### Run Sync in Thread Pool

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=4)

async def main():
    loop = asyncio.get_running_loop()

    # Run blocking function in thread pool
    result = await loop.run_in_executor(
        executor,
        blocking_function,
        arg1, arg2
    )

    # Default executor (None)
    result = await loop.run_in_executor(None, blocking_io)
```

### Run Sync in Process Pool

```python
from concurrent.futures import ProcessPoolExecutor

process_executor = ProcessPoolExecutor(max_workers=4)

async def main():
    loop = asyncio.get_running_loop()

    # Run CPU-bound function in process
    result = await loop.run_in_executor(
        process_executor,
        cpu_intensive_function,
        data
    )
```

### Run Async from Sync

```python
# From synchronous code
def sync_function():
    result = asyncio.run(async_function())
    return result

# For running async code in existing loop thread
def sync_call_async(coro):
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)

# For nested event loops (not recommended)
import nest_asyncio
nest_asyncio.apply()
```

---

## 14.4 Timeouts and Cancellation

### Timeout Patterns

```python
# Simple timeout
try:
    result = await asyncio.wait_for(slow_operation(), timeout=5.0)
except asyncio.TimeoutError:
    print("Operation timed out")

# Timeout context manager (Python 3.11+)
async with asyncio.timeout(5.0):
    await slow_operation()

# Non-raising timeout
async with asyncio.timeout_at(deadline):
    try:
        await operation()
    except asyncio.CancelledError:
        # Handle timeout
        pass
```

### Graceful Cancellation

```python
async def graceful_operation():
    try:
        while True:
            await do_work()
    except asyncio.CancelledError:
        # Cleanup
        await cleanup()
        raise  # Always re-raise

async def main():
    task = asyncio.create_task(graceful_operation())
    await asyncio.sleep(5)

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        print("Task cancelled gracefully")
```

### Shield from Cancellation

```python
async def main():
    task = asyncio.create_task(important_operation())

    try:
        # Shield prevents outer cancellation
        await asyncio.shield(task)
    except asyncio.CancelledError:
        # Outer was cancelled, but task continues
        await task  # Wait for task to finish
```

---

## 14.5 Testing Async Code

### pytest-asyncio

```python
import pytest

@pytest.mark.asyncio
async def test_async_function():
    result = await async_function()
    assert result == expected

@pytest.mark.asyncio
async def test_with_fixture(async_client):
    response = await async_client.get('/')
    assert response.status == 200

@pytest.fixture
async def async_client():
    async with AsyncClient() as client:
        yield client
```

### Manual Testing

```python
import unittest

class TestAsync(unittest.TestCase):
    def test_async_function(self):
        result = asyncio.run(async_function())
        self.assertEqual(result, expected)

    def test_with_timeout(self):
        async def test():
            result = await asyncio.wait_for(
                slow_function(),
                timeout=5.0
            )
            self.assertIsNotNone(result)

        asyncio.run(test())
```

### Mocking Async

```python
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_with_mock():
    mock = AsyncMock(return_value="mocked")

    with patch('module.async_function', mock):
        result = await function_under_test()
        assert result == "mocked"
        mock.assert_awaited_once()
```

---

## 14.6 Debugging Async

### Debug Mode

```python
# Enable debug mode
asyncio.run(main(), debug=True)

# Or via environment
# PYTHONASYNCIODEBUG=1 python script.py

# Check for slow callbacks
import warnings
warnings.filterwarnings("default", category=ResourceWarning)
```

### Common Issues

```python
# 1. Unawaited coroutine
async def main():
    async_func()  # RuntimeWarning: coroutine was never awaited

# 2. Blocking the loop
async def bad():
    time.sleep(1)  # Blocks everything

# 3. Creating tasks that aren't awaited
async def main():
    asyncio.create_task(something())
    # Task may be garbage collected before running

# Fix: Keep reference or await
async def main():
    task = asyncio.create_task(something())
    await task  # or use TaskGroup
```

---

## Exercises

### Exercise 14.1: Connection Pool

Implement async connection pool:
- Max connections limit
- Acquire/release pattern
- Health checks

### Exercise 14.2: Retry Logic

Implement async retry decorator:
- Exponential backoff
- Max retries
- Specific exception types

### Exercise 14.3: Pub/Sub

Implement async pub/sub:
- Multiple publishers
- Multiple subscribers
- Topic filtering

---

## Summary

You've mastered advanced async:
1. **TaskGroups**: Structured concurrency
2. **Synchronization**: Lock, Semaphore, Event, Queue
3. **Integration**: Sync/async mixing
4. **Timeouts**: Cancellation patterns
5. **Testing**: pytest-asyncio, mocking
6. **Debugging**: Debug mode, common issues

---

## Next Module

**[Module 15: WSGI Deep Dive →](./MODULE_15_WSGI.md)**

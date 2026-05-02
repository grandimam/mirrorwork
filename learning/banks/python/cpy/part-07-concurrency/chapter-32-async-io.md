# Chapter 32: Asynchronous I/O

## 32.1 Event Loop Fundamentals

Asynchronous I/O allows single-threaded concurrency without the GIL limitations:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Event Loop Model                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Single Thread with Event Loop:                                  │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    Event Loop                            │    │
│  │  ┌──────────────────────────────────────────────────┐   │    │
│  │  │  Ready Queue: [task1, task2, task3]              │   │    │
│  │  └──────────────────────────────────────────────────┘   │    │
│  │                        │                                 │    │
│  │                        ▼                                 │    │
│  │  while tasks:                                            │    │
│  │      task = get_ready_task()                            │    │
│  │      run_until_await(task)  # Runs Python code          │    │
│  │      if task.waiting_on_io:                             │    │
│  │          register_io_callback(task)                     │    │
│  │      check_io_completions()  # OS level, no GIL needed │    │
│  │                                                          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Key: Tasks voluntarily yield at await points                   │
│       I/O waiting happens at OS level (no Python code)          │
│       Single thread, no GIL contention                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 32.2 `asyncio` Module Architecture

```python
import asyncio

async def fetch_data(url):
    """Coroutine that fetches data."""
    print(f"Fetching {url}")
    await asyncio.sleep(1)  # Simulated I/O
    return f"Data from {url}"

async def main():
    # Run multiple coroutines concurrently
    results = await asyncio.gather(
        fetch_data("url1"),
        fetch_data("url2"),
        fetch_data("url3"),
    )
    print(results)

# Run the event loop
asyncio.run(main())
```

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                  asyncio Architecture                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  User Code (coroutines)                                          │
│       │                                                          │
│       ▼                                                          │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  High-Level API                                          │    │
│  │  asyncio.run(), asyncio.gather(), asyncio.create_task() │    │
│  └─────────────────────────────────────────────────────────┘    │
│       │                                                          │
│       ▼                                                          │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Event Loop                                              │    │
│  │  Schedules and runs coroutines, manages I/O             │    │
│  └─────────────────────────────────────────────────────────┘    │
│       │                                                          │
│       ▼                                                          │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Selector (I/O Multiplexing)                            │    │
│  │  select/poll/epoll/kqueue                               │    │
│  └─────────────────────────────────────────────────────────┘    │
│       │                                                          │
│       ▼                                                          │
│  Operating System                                                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 32.3 Coroutines and `async`/`await`

### Defining Coroutines

```python
import asyncio

# Coroutine function (defined with async def)
async def my_coroutine():
    print("Start")
    await asyncio.sleep(1)  # Yield control
    print("End")
    return "Result"

# Calling creates a coroutine object (doesn't run it)
coro = my_coroutine()
print(type(coro))  # <class 'coroutine'>

# Must be awaited or scheduled to run
result = asyncio.run(my_coroutine())
```

### How `await` Works

```python
async def outer():
    print("1. Start outer")
    result = await inner()  # Suspends outer, runs inner
    print(f"4. Got result: {result}")
    return "outer done"

async def inner():
    print("2. Start inner")
    await asyncio.sleep(0.1)  # Suspends inner
    print("3. End inner")
    return "inner result"

asyncio.run(outer())
# Output:
# 1. Start outer
# 2. Start inner
# 3. End inner
# 4. Got result: inner result
```

## 32.4 Tasks and Futures

### Creating Tasks

```python
import asyncio

async def worker(name, delay):
    print(f"{name} starting")
    await asyncio.sleep(delay)
    print(f"{name} done")
    return f"{name} result"

async def main():
    # Create tasks (schedule coroutines)
    task1 = asyncio.create_task(worker("A", 2))
    task2 = asyncio.create_task(worker("B", 1))

    # Tasks run concurrently
    # Wait for both
    result1 = await task1
    result2 = await task2

    print(result1, result2)

asyncio.run(main())
# Output:
# A starting
# B starting
# B done (after 1 second)
# A done (after 2 seconds)
# A result B result
```

### Futures

```python
import asyncio

async def main():
    loop = asyncio.get_event_loop()

    # Create a future
    future = loop.create_future()

    # Set result from somewhere (e.g., callback)
    async def set_result():
        await asyncio.sleep(1)
        future.set_result("Future result!")

    asyncio.create_task(set_result())

    # Wait for future
    result = await future
    print(result)

asyncio.run(main())
```

## 32.5 `asyncio` Internals

### Event Loop Implementation

```python
# Simplified event loop concept
class SimpleEventLoop:
    def __init__(self):
        self.ready = []  # Ready to run
        self.waiting = {}  # Waiting for I/O

    def run_until_complete(self, coro):
        self.ready.append(coro)

        while self.ready or self.waiting:
            # Run ready tasks
            while self.ready:
                task = self.ready.pop(0)
                try:
                    # Run until next await
                    result = task.send(None)
                    if isinstance(result, IOWait):
                        self.waiting[result.fd] = task
                    else:
                        self.ready.append(task)
                except StopIteration as e:
                    return e.value

            # Check I/O (simplified)
            ready_fds = select(self.waiting.keys())
            for fd in ready_fds:
                task = self.waiting.pop(fd)
                self.ready.append(task)
```

### Selector-Based I/O

```python
import selectors
import socket

# Low-level async I/O with selectors
sel = selectors.DefaultSelector()

def accept(sock):
    conn, addr = sock.accept()
    conn.setblocking(False)
    sel.register(conn, selectors.EVENT_READ, read)

def read(conn):
    data = conn.recv(1000)
    if data:
        conn.send(data)  # Echo
    else:
        sel.unregister(conn)
        conn.close()

# Server socket
sock = socket.socket()
sock.bind(('localhost', 8080))
sock.listen()
sock.setblocking(False)
sel.register(sock, selectors.EVENT_READ, accept)

# Event loop
while True:
    events = sel.select()
    for key, mask in events:
        callback = key.data
        callback(key.fileobj)
```

## 32.6 Selectors and I/O Multiplexing

### Available Selectors

| Selector | Platform | Scalability |
|----------|----------|-------------|
| `select` | All | O(n) - limited |
| `poll` | Unix | O(n) - no fd limit |
| `epoll` | Linux | O(1) - best |
| `kqueue` | BSD/macOS | O(1) - best |

```python
import selectors

# Get the best selector for the platform
selector = selectors.DefaultSelector()
print(type(selector))
# Linux: EpollSelector
# macOS: KqueueSelector
# Windows: SelectSelector
```

## 32.7 Single-Threaded Concurrency

### Why Async Works Without Threads

```python
import asyncio
import time

async def cpu_work(name):
    """CPU-bound work blocks the event loop!"""
    print(f"{name}: starting CPU work")
    total = sum(range(10**7))  # Blocks!
    print(f"{name}: done")
    return total

async def io_work(name):
    """I/O-bound work yields control."""
    print(f"{name}: starting I/O")
    await asyncio.sleep(1)  # Yields control
    print(f"{name}: done")
    return f"{name} result"

async def main():
    # I/O-bound: runs concurrently
    start = time.time()
    await asyncio.gather(
        io_work("A"),
        io_work("B"),
        io_work("C"),
    )
    print(f"I/O time: {time.time() - start:.2f}s")  # ~1 second

    # CPU-bound: runs sequentially (blocks!)
    start = time.time()
    await asyncio.gather(
        cpu_work("X"),
        cpu_work("Y"),
        cpu_work("Z"),
    )
    print(f"CPU time: {time.time() - start:.2f}s")  # ~3 seconds

asyncio.run(main())
```

### Running CPU Work in Executor

```python
import asyncio
from concurrent.futures import ProcessPoolExecutor

def cpu_work(n):
    return sum(range(n))

async def main():
    loop = asyncio.get_event_loop()

    # Run CPU work in process pool
    with ProcessPoolExecutor() as pool:
        results = await asyncio.gather(
            loop.run_in_executor(pool, cpu_work, 10**7),
            loop.run_in_executor(pool, cpu_work, 10**7),
            loop.run_in_executor(pool, cpu_work, 10**7),
        )
    print(results)

asyncio.run(main())
```

## 32.8 `async for` and `async with`

### Async Iteration

```python
import asyncio

class AsyncRange:
    def __init__(self, n):
        self.n = n
        self.i = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.i >= self.n:
            raise StopAsyncIteration
        await asyncio.sleep(0.1)
        self.i += 1
        return self.i

async def main():
    async for i in AsyncRange(5):
        print(i)

asyncio.run(main())
```

### Async Context Manager

```python
import asyncio

class AsyncResource:
    async def __aenter__(self):
        print("Acquiring resource...")
        await asyncio.sleep(0.5)
        print("Resource acquired")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        print("Releasing resource...")
        await asyncio.sleep(0.5)
        print("Resource released")

async def main():
    async with AsyncResource() as resource:
        print("Using resource")

asyncio.run(main())
```

## 32.9 Third-Party Async Frameworks

### uvloop

```python
# pip install uvloop
import uvloop
import asyncio

# Use uvloop (faster than default)
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

async def main():
    await asyncio.sleep(1)

asyncio.run(main())
```

### Trio

```python
# pip install trio
import trio

async def worker(name):
    print(f"{name} starting")
    await trio.sleep(1)
    print(f"{name} done")

async def main():
    async with trio.open_nursery() as nursery:
        nursery.start_soon(worker, "A")
        nursery.start_soon(worker, "B")

trio.run(main)
```

## Summary

- **Event loops** enable single-threaded concurrency
- **`async`/`await`** syntax for coroutines
- **Tasks** schedule coroutines for concurrent execution
- **No GIL issues** - single thread, voluntary yielding
- **Best for I/O-bound** work, not CPU-bound
- **Selectors** provide efficient I/O multiplexing
- Use **executors** for CPU-bound work in async code

## Practice Exercises

1. Implement a concurrent web scraper with asyncio
2. Compare asyncio vs threading for I/O-bound tasks
3. Build an async chat server
4. Profile an async application to find bottlenecks

---

[← Previous: Multiprocessing](chapter-31-multiprocessing.md) | [Next: Subinterpreters →](chapter-33-subinterpreters.md)

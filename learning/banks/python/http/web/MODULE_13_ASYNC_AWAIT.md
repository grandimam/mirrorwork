# Module 13: Async/Await and Coroutines

## Overview

Coroutines solve callback hell by letting you write asynchronous code that looks synchronous. This module covers Python's async/await from the ground up—generators, native coroutines, and asyncio internals.

---

## Learning Objectives

By the end of this module, you will be able to:

1. Understand generators and yield
2. Explain how coroutines work internally
3. Use async/await effectively
4. Understand asyncio event loop internals
5. Build async HTTP servers

---

## 13.1 Generator Refresher

### Basic Generators

```python
def count_up(n):
    """Generator that yields 0 to n-1."""
    i = 0
    while i < n:
        yield i  # Pause and return value
        i += 1

# Usage
gen = count_up(3)
print(next(gen))  # 0
print(next(gen))  # 1
print(next(gen))  # 2
```

### Generator States

```
Created ─────▶ Running ─────▶ Suspended ─────▶ Running ─────▶ Closed
           start         yield            next          return/StopIteration
```

### send() and throw()

```python
def accumulator():
    total = 0
    while True:
        value = yield total  # Receive value, yield total
        if value is not None:
            total += value

acc = accumulator()
next(acc)           # Initialize (returns 0)
acc.send(10)        # Send 10, returns 10
acc.send(20)        # Send 20, returns 30
acc.throw(ValueError)  # Raise exception in generator
```

---

## 13.2 Generator-Based Coroutines (Legacy)

### yield from

```python
def sub_task():
    yield 1
    yield 2
    return "done"

def main_task():
    result = yield from sub_task()  # Delegate to sub-generator
    print(f"Sub-task returned: {result}")
    yield 3

for value in main_task():
    print(value)
# Output: 1, 2, Sub-task returned: done, 3
```

### Coroutine Pattern

```python
# Old-style coroutine (pre-3.5)
@asyncio.coroutine
def fetch_data():
    yield from asyncio.sleep(1)
    return "data"
```

---

## 13.3 Native Coroutines (async/await)

### Basic Syntax

```python
import asyncio

async def fetch_data():
    """Native coroutine."""
    await asyncio.sleep(1)  # Pause without blocking
    return "data"

# Running
async def main():
    result = await fetch_data()
    print(result)

asyncio.run(main())
```

### How async/await Works

```python
# async def creates a coroutine function
async def my_coroutine():
    return 42

# Calling it returns a coroutine object
coro = my_coroutine()
print(type(coro))  # <class 'coroutine'>

# await runs the coroutine
result = await coro  # Only works inside async function
```

### Under the Hood

```python
# Coroutine object has these methods:
coro.send(None)   # Start/resume coroutine
coro.throw(exc)   # Raise exception in coroutine
coro.close()      # Close coroutine

# await is syntactic sugar for yield from
# But only works with awaitables
```

---

## 13.4 Awaitables

### What Can Be Awaited?

1. **Coroutines** (async def functions)
2. **Tasks** (scheduled coroutines)
3. **Futures** (low-level awaitable)
4. **Objects with __await__**

### Custom Awaitable

```python
class AsyncResult:
    """Custom awaitable."""

    def __init__(self, value, delay):
        self.value = value
        self.delay = delay

    def __await__(self):
        # Must yield something awaitable
        yield from asyncio.sleep(self.delay).__await__()
        return self.value

async def main():
    result = await AsyncResult("hello", 1.0)
    print(result)
```

---

## 13.5 asyncio Event Loop

### Core Components

```python
import asyncio

# Get/create event loop
loop = asyncio.get_event_loop()      # Deprecated in 3.10+
loop = asyncio.new_event_loop()       # Create new loop
loop = asyncio.get_running_loop()    # Inside async function

# Run coroutine
asyncio.run(main())  # Recommended (3.7+)

# Lower level
loop.run_until_complete(main())
loop.run_forever()
loop.stop()
loop.close()
```

### Tasks

```python
async def main():
    # Create task - starts running immediately
    task = asyncio.create_task(fetch_data())

    # Do other work...

    # Wait for task
    result = await task

# Task methods
task.cancel()       # Request cancellation
task.cancelled()    # Check if cancelled
task.done()         # Check if completed
task.result()       # Get result (raises if not done)
task.exception()    # Get exception (if any)
task.add_done_callback(fn)  # Add completion callback
```

### Concurrent Execution

```python
async def main():
    # Run concurrently
    results = await asyncio.gather(
        fetch_url("http://example1.com"),
        fetch_url("http://example2.com"),
        fetch_url("http://example3.com"),
    )

    # First to complete
    done, pending = await asyncio.wait(
        [task1, task2, task3],
        return_when=asyncio.FIRST_COMPLETED
    )

    # With timeout
    try:
        result = await asyncio.wait_for(slow_operation(), timeout=5.0)
    except asyncio.TimeoutError:
        print("Timed out!")
```

---

## 13.6 asyncio Streams

### TCP Client

```python
async def tcp_client():
    reader, writer = await asyncio.open_connection('localhost', 8080)

    writer.write(b"Hello\n")
    await writer.drain()  # Ensure data sent

    data = await reader.read(1024)
    print(f"Received: {data}")

    writer.close()
    await writer.wait_closed()
```

### TCP Server

```python
async def handle_client(reader, writer):
    addr = writer.get_extra_info('peername')
    print(f"Connection from {addr}")

    while True:
        data = await reader.read(1024)
        if not data:
            break

        writer.write(data)  # Echo back
        await writer.drain()

    writer.close()
    await writer.wait_closed()


async def main():
    server = await asyncio.start_server(
        handle_client, '0.0.0.0', 8080
    )

    async with server:
        await server.serve_forever()

asyncio.run(main())
```

---

## 13.7 Protocol and Transport

### Lower-Level API

```python
class EchoProtocol(asyncio.Protocol):
    """Echo protocol using Transport/Protocol API."""

    def connection_made(self, transport):
        self.transport = transport
        self.peername = transport.get_extra_info('peername')
        print(f"Connection from {self.peername}")

    def data_received(self, data):
        self.transport.write(data)  # Echo

    def connection_lost(self, exc):
        print(f"Connection closed: {self.peername}")


async def main():
    loop = asyncio.get_running_loop()

    server = await loop.create_server(
        lambda: EchoProtocol(),
        '0.0.0.0', 8080
    )

    async with server:
        await server.serve_forever()
```

---

## 13.8 Async HTTP Server

```python
"""
Complete async HTTP server.
"""

import asyncio
from typing import Callable, Awaitable


class AsyncHTTPServer:
    """Async HTTP server using asyncio."""

    def __init__(self, host='0.0.0.0', port=8080):
        self.host = host
        self.port = port
        self.routes = {}

    def route(self, method: str, path: str):
        def decorator(handler):
            self.routes[(method, path)] = handler
            return handler
        return decorator

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle single client connection."""
        addr = writer.get_extra_info('peername')

        try:
            while True:
                # Read request line
                line = await asyncio.wait_for(reader.readline(), timeout=30)
                if not line:
                    break

                # Parse request
                parts = line.decode().strip().split()
                if len(parts) < 3:
                    break

                method, path, _ = parts

                # Read headers
                headers = {}
                while True:
                    header_line = await reader.readline()
                    if header_line == b'\r\n':
                        break
                    name, _, value = header_line.decode().partition(':')
                    headers[name.strip().lower()] = value.strip()

                # Read body if present
                body = b''
                if 'content-length' in headers:
                    length = int(headers['content-length'])
                    body = await reader.readexactly(length)

                # Route to handler
                handler = self.routes.get((method, path))
                if handler:
                    response = await handler({'method': method, 'path': path, 'headers': headers, 'body': body})
                else:
                    response = b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n"

                # Send response
                writer.write(response)
                await writer.drain()

                # Check connection
                if headers.get('connection', '').lower() == 'close':
                    break

        except asyncio.TimeoutError:
            pass
        except Exception as e:
            print(f"Error: {e}")
        finally:
            writer.close()
            await writer.wait_closed()

    async def run(self):
        """Start the server."""
        server = await asyncio.start_server(
            self.handle_client,
            self.host, self.port
        )

        print(f"Async server on http://{self.host}:{self.port}")

        async with server:
            await server.serve_forever()


# Usage
app = AsyncHTTPServer()

@app.route('GET', '/')
async def index(request):
    body = b"Hello, Async World!"
    return (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: text/plain\r\n"
        b"Content-Length: " + str(len(body)).encode() + b"\r\n"
        b"\r\n" + body
    )

@app.route('GET', '/slow')
async def slow(request):
    await asyncio.sleep(1)  # Non-blocking sleep
    body = b"Slow response"
    return (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Length: " + str(len(body)).encode() + b"\r\n"
        b"\r\n" + body
    )

if __name__ == '__main__':
    asyncio.run(app.run())
```

---

## 13.9 Common Pitfalls

### Blocking the Event Loop

```python
# BAD: Blocks entire loop
async def bad_handler():
    time.sleep(1)  # Blocks!
    return result

# GOOD: Use async version
async def good_handler():
    await asyncio.sleep(1)  # Non-blocking
    return result

# For CPU-bound work, use executor
async def cpu_bound_handler():
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, heavy_computation)
    return result
```

### Missing await

```python
# BAD: Coroutine never runs
async def main():
    fetch_data()  # Warning: coroutine never awaited

# GOOD
async def main():
    await fetch_data()  # or
    task = asyncio.create_task(fetch_data())
    await task
```

### Task Cancellation

```python
async def cancellable_operation():
    try:
        while True:
            await asyncio.sleep(1)
            print("Working...")
    except asyncio.CancelledError:
        print("Cancelled! Cleaning up...")
        raise  # Re-raise to propagate

task = asyncio.create_task(cancellable_operation())
await asyncio.sleep(5)
task.cancel()
try:
    await task
except asyncio.CancelledError:
    print("Task was cancelled")
```

---

## Exercises

### Exercise 13.1: Async Web Crawler

Build an async web crawler:
- Fetch multiple URLs concurrently
- Respect rate limits
- Handle errors gracefully

### Exercise 13.2: Chat Server

Build async chat server:
- Multiple connected clients
- Broadcast messages to all
- Private messages

### Exercise 13.3: Rate Limiter

Implement async rate limiter:
- Token bucket algorithm
- Per-client limits

---

## Summary

You've learned:
1. **Generators**: yield, send, throw
2. **Coroutines**: async def, await
3. **asyncio**: Tasks, gather, wait_for
4. **Streams**: High-level async I/O
5. **Protocol/Transport**: Low-level API
6. **Patterns**: Error handling, cancellation

Next: Advanced async patterns and production techniques.

---

## Next Module

**[Module 14: Advanced Async Patterns →](./MODULE_14_ADVANCED_ASYNC.md)**

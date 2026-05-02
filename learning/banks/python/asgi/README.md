n# ASGI: The Complete Guide

ASGI (Asynchronous Server Gateway Interface) is the standard interface between async Python web servers and applications. It's the spiritual successor to WSGI, designed for the async era.

## Table of Contents

1. [Core Interface](#core-interface)
2. [Scope](#scope)
3. [Events](#events)
4. [Event Internals](#event-internals)
5. [HTTP Protocol](#http-protocol)
6. [WebSocket Protocol](#websocket-protocol)
7. [Lifespan Protocol](#lifespan-protocol)
8. [Middleware](#middleware)
9. [Server Implementations](#server-implementations)
10. [ASGI vs WSGI](#asgi-vs-wsgi)
11. [Type Definitions](#type-definitions)
12. [References](#references)

## Core Interface

An ASGI application is a single async callable:

```python
async def application(scope: dict, receive: Callable, send: Callable) -> None:
    ...
```

That's it. Three parameters, no return value.

### The Three Components

| Component | Type             | Purpose                                   |
| --------- | ---------------- | ----------------------------------------- |
| `scope`   | `dict`           | Connection metadata (one-time, read-only) |
| `receive` | `async callable` | Get events from client/server             |
| `send`    | `async callable` | Send events to client/server              |

### Scope vs Receive

`scope` and `receive` serve fundamentally different roles, separated by **timing**.

`scope` is the **"what"** — static metadata describing the connection. It's created once when the connection starts and doesn't change. Think of it like the envelope of a letter: who sent it, where it's going, what protocol, what path, what headers. It's read-only and available immediately.

`receive` is the **"incoming data stream"** — an async callable you `await` to get events _over time_ from the client. The server knows the path, method, and headers as soon as the request starts, but the **body** may not have arrived yet. HTTP request bodies can be large and streamed in chunks. `receive()` lets you pull those chunks as they arrive:

```python
async def app(scope, receive, send):
    # scope is already here — I know it's POST /upload
    body = b""
    while True:
        event = await receive()  # wait for body chunks
        body += event.get("body", b"")
        if not event.get("more_body"):
            break
```

For **WebSockets**, the split is even more clear: `scope` has the initial connection info, but `receive()` is called repeatedly over the lifetime of the connection to get each incoming message.

| Aspect      | `scope`               | `receive`                        |
| ----------- | --------------------- | -------------------------------- |
| Nature      | Static metadata       | Dynamic event stream             |
| Timing      | Available immediately | Awaited over time                |
| Mutability  | Read-only             | Yields new events each call      |
| Cardinality | One per connection    | Called many times per connection |

### Who Defines This?

The **ASGI specification** is maintained by the Django Software Foundation:

- Spec: https://asgi.readthedocs.io
- Reference implementation: https://github.com/django/asgiref

The spec is a **contract** between:

- **Servers** (Uvicorn, Hypercorn) — implement the server side
- **Applications** (FastAPI, Starlette, your code) — implement the app side

### Minimal Application

```python
from typing import Any, Awaitable, Callable

Scope = dict[str, Any]
Receive = Callable[[], Awaitable[dict]]
Send = Callable[[dict], Awaitable[None]]


async def app(scope: Scope, receive: Receive, send: Send) -> None:
    if scope["type"] == "http":
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"text/plain")],
        })
        await send({
            "type": "http.response.body",
            "body": b"Hello, World!",
        })
```

---

## Scope

Scope is a dictionary containing connection metadata. It's created once per connection and passed to your application.

### Scope Types

ASGI defines three protocol types via `scope["type"]`:

| Type          | Description             |
| ------------- | ----------------------- |
| `"http"`      | HTTP request/response   |
| `"websocket"` | WebSocket connection    |
| `"lifespan"`  | Server startup/shutdown |

### Common Scope Fields

These fields appear in all scope types:

| Field   | Type   | Description          |
| ------- | ------ | -------------------- |
| `type`  | `str`  | Protocol type        |
| `asgi`  | `dict` | ASGI version info    |
| `state` | `dict` | Shared mutable state |

### HTTP Scope

```python
scope = {
    "type": "http",
    "asgi": {"version": "3.0", "spec_version": "2.4"},
    "http_version": "1.1",
    "method": "GET",
    "scheme": "https",
    "path": "/users/123",
    "raw_path": b"/users/123",
    "query_string": b"include=posts",
    "root_path": "",
    "headers": [
        (b"host", b"example.com"),
        (b"accept", b"application/json"),
        (b"authorization", b"Bearer xyz"),
    ],
    "server": ("example.com", 443),
    "client": ("10.0.0.1", 54321),
    "state": {},
}
```

| Field          | Type                        | Description                       |
| -------------- | --------------------------- | --------------------------------- |
| `http_version` | `str`                       | `"1.0"`, `"1.1"`, `"2"`, or `"3"` |
| `method`       | `str`                       | HTTP method (uppercase)           |
| `scheme`       | `str`                       | `"http"` or `"https"`             |
| `path`         | `str`                       | URL path (percent-decoded)        |
| `raw_path`     | `bytes`                     | URL path (original, optional)     |
| `query_string` | `bytes`                     | Query string without `?`          |
| `root_path`    | `str`                       | SCRIPT_NAME equivalent            |
| `headers`      | `list[tuple[bytes, bytes]]` | Headers (lowercase names)         |
| `server`       | `tuple[str, int] \| None`   | Server host and port              |
| `client`       | `tuple[str, int] \| None`   | Client host and port              |

### WebSocket Scope

```python
scope = {
    "type": "websocket",
    "asgi": {"version": "3.0"},
    "http_version": "1.1",
    "scheme": "wss",
    "path": "/ws/chat",
    "query_string": b"room=general",
    "root_path": "",
    "headers": [(b"host", b"example.com")],
    "server": ("example.com", 443),
    "client": ("10.0.0.1", 54321),
    "subprotocols": ["graphql-ws"],
    "state": {},
}
```

Additional field:

| Field          | Type        | Description                   |
| -------------- | ----------- | ----------------------------- |
| `subprotocols` | `list[str]` | Client-requested subprotocols |

### Lifespan Scope

```python
scope = {
    "type": "lifespan",
    "asgi": {"version": "3.0", "spec_version": "2.0"},
    "state": {},
}
```

The `state` dict is shared with all HTTP/WebSocket connections.

### Scope Rules

1. **Read-only** — Don't mutate scope directly; copy first
2. **Connection-scoped** — One scope per connection
3. **state is special** — Mutable, shared across middleware

---

## Events

Events are dictionaries passed through `receive()` and `send()`. Every event has a `type` field.

### Event Naming Convention

```
{protocol}.{action}[.{modifier}]
```

Examples:

- `http.request`
- `http.response.start`
- `websocket.connect`
- `lifespan.startup.complete`

### Event Directionality

| Direction    | Function    | Description               |
| ------------ | ----------- | ------------------------- |
| Server → App | `receive()` | Events from server/client |
| App → Server | `send()`    | Events to server/client   |

### HTTP Events

#### Receive Events

**`http.request`** — Request body chunk

```python
{
    "type": "http.request",
    "body": b"...",        # Body bytes (may be empty)
    "more_body": False,    # True if more chunks coming
}
```

**`http.disconnect`** — Client disconnected

```python
{
    "type": "http.disconnect",
}
```

#### Send Events

**`http.response.start`** — Begin response (must be first)

```python
{
    "type": "http.response.start",
    "status": 200,
    "headers": [(b"content-type", b"text/plain")],
    "trailers": False,  # Optional, HTTP/2+ only
}
```

**`http.response.body`** — Response body chunk

```python
{
    "type": "http.response.body",
    "body": b"...",        # Body bytes
    "more_body": False,    # True for streaming
}
```

### WebSocket Events

#### Receive Events

**`websocket.connect`** — Client initiating connection

```python
{"type": "websocket.connect"}
```

**`websocket.receive`** — Message from client

```python
{
    "type": "websocket.receive",
    "text": "hello",  # OR
    "bytes": b"...",  # Never both
}
```

**`websocket.disconnect`** — Client disconnected

```python
{
    "type": "websocket.disconnect",
    "code": 1000,
}
```

#### Send Events

**`websocket.accept`** — Accept connection

```python
{
    "type": "websocket.accept",
    "subprotocol": "graphql-ws",  # Optional
    "headers": [],                 # Optional
}
```

**`websocket.send`** — Send message

```python
{
    "type": "websocket.send",
    "text": "hello",  # OR
    "bytes": b"...",  # Never both
}
```

**`websocket.close`** — Close connection

```python
{
    "type": "websocket.close",
    "code": 1000,
    "reason": "",  # Optional
}
```

### Lifespan Events

#### Receive Events

```python
{"type": "lifespan.startup"}   # Server starting
{"type": "lifespan.shutdown"}  # Server stopping
```

#### Send Events

```python
{"type": "lifespan.startup.complete"}
{"type": "lifespan.startup.failed", "message": "..."}
{"type": "lifespan.shutdown.complete"}
{"type": "lifespan.shutdown.failed", "message": "..."}
```

### Event Ordering Rules

#### HTTP

```
receive: http.request* → http.disconnect?
send:    http.response.start → http.response.body+
```

- Must send `http.response.start` before `http.response.body`
- Last `http.response.body` must have `more_body: False`

#### WebSocket

```
receive: websocket.connect → websocket.receive* → websocket.disconnect
send:    websocket.accept → websocket.send* → websocket.close?
```

- Must respond to `websocket.connect` with `websocket.accept` or `websocket.close`
- After accept, can send/receive in any order

---

## Event Internals

### Events Are Just Dicts

No magic. An event is a Python dictionary:

```python
event = {"type": "http.request", "body": b"hello", "more_body": False}
```

### receive() and send() Are Closures

The server creates these functions for each connection:

```python
async def receive() -> dict:
    """Get the next event from the server"""
    return await self._receive_queue.get()

async def send(event: dict) -> None:
    """Send an event to the server"""
    await self._process_event(event)
```

They're closures that capture connection state. Each connection gets its own pair.

### Server-Side Implementation

Simplified server implementation:

```python
import asyncio
from typing import Any

class HTTPConnection:
    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        self.reader = reader
        self.writer = writer
        self._receive_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._response_started = False

    async def receive(self) -> dict[str, Any]:
        return await self._receive_queue.get()

    async def send(self, event: dict[str, Any]) -> None:
        event_type = event["type"]

        if event_type == "http.response.start":
            if self._response_started:
                raise RuntimeError("Response already started")
            self._response_started = True
            await self._write_status_and_headers(event)

        elif event_type == "http.response.body":
            if not self._response_started:
                raise RuntimeError("Response not started")
            await self._write_body(event)

    async def _write_status_and_headers(self, event: dict) -> None:
        status = event["status"]
        headers = event.get("headers", [])

        self.writer.write(f"HTTP/1.1 {status} OK\r\n".encode())
        for name, value in headers:
            self.writer.write(name + b": " + value + b"\r\n")
        self.writer.write(b"\r\n")
        await self.writer.drain()

    async def _write_body(self, event: dict) -> None:
        body = event.get("body", b"")
        if body:
            self.writer.write(body)
            await self.writer.drain()

    async def feed_request_body(self, body: bytes, more: bool) -> None:
        await self._receive_queue.put({
            "type": "http.request",
            "body": body,
            "more_body": more,
        })
```

### Connection Lifecycle

```
1. Client connects (TCP)
         │
         ▼
2. Server parses HTTP headers → creates scope
         │
         ▼
3. Server creates receive/send closures
         │
         ▼
4. Server calls: await app(scope, receive, send)
         │
         ├─────────────────────────────────┐
         │                                 │
         ▼                                 ▼
5. App awaits receive()            Server reads body
         │                                 │
         │◀────── http.request ───────────┘
         │
         ▼
6. App processes request
         │
         ▼
7. App calls send(http.response.start)
         │
         └────── writes to socket ────────▶
         │
         ▼
8. App calls send(http.response.body)
         │
         └────── writes to socket ────────▶
         │
         ▼
9. App returns → server closes connection
```

### Concurrency Model

`receive()` and `send()` block independently, enabling:

**Streaming request bodies:**

```python
async def app(scope: Scope, receive: Receive, send: Send) -> None:
    total = 0
    while True:
        event = await receive()  # Blocks until chunk arrives
        total += len(event.get("body", b""))
        if not event.get("more_body"):
            break
```

**Streaming responses:**

```python
async def app(scope: Scope, receive: Receive, send: Send) -> None:
    await send({"type": "http.response.start", "status": 200, "headers": []})

    async for chunk in generate_chunks():
        await send({
            "type": "http.response.body",
            "body": chunk,
            "more_body": True,
        })

    await send({"type": "http.response.body", "body": b"", "more_body": False})
```

**Bidirectional streaming (WebSocket):**

```python
async def app(scope: Scope, receive: Receive, send: Send) -> None:
    await send({"type": "websocket.accept"})

    async def reader() -> None:
        while True:
            event = await receive()
            if event["type"] == "websocket.disconnect":
                break
            print(f"Got: {event.get('text')}")

    async def writer() -> None:
        for i in range(10):
            await send({"type": "websocket.send", "text": f"msg {i}"})
            await asyncio.sleep(1)

    await asyncio.gather(reader(), writer())
```

### Backpressure

Servers implement backpressure to prevent memory exhaustion:

```python
async def send(self, event: dict) -> None:
    self.writer.write(event.get("body", b""))
    await self.writer.drain()  # Blocks if client is slow
```

### State Machine

Servers enforce valid event sequences:

```python
from enum import Enum, auto

class HTTPState(Enum):
    REQUEST = auto()
    RESPONSE_STARTED = auto()
    CLOSED = auto()

class HTTPConnection:
    def __init__(self) -> None:
        self._state = HTTPState.REQUEST

    async def send(self, event: dict) -> None:
        if event["type"] == "http.response.start":
            if self._state != HTTPState.REQUEST:
                raise RuntimeError("Invalid state for response.start")
            self._state = HTTPState.RESPONSE_STARTED

        elif event["type"] == "http.response.body":
            if self._state != HTTPState.RESPONSE_STARTED:
                raise RuntimeError("Must send response.start first")
            if not event.get("more_body", False):
                self._state = HTTPState.CLOSED
```

### Memory Model

Events are **not copied**. Server and app share the same dict:

```python
# Server
event = {"type": "http.request", "body": large_bytes}
await queue.put(event)

# App
event = await receive()  # Same object
```

**Rule:** Don't mutate received events.

---

## HTTP Protocol

### Reading Request Body

```python
async def read_body(receive: Receive) -> bytes:
    body_parts: list[bytes] = []

    while True:
        event = await receive()
        body_parts.append(event.get("body", b""))
        if not event.get("more_body", False):
            break

    return b"".join(body_parts)


async def app(scope: Scope, receive: Receive, send: Send) -> None:
    if scope["type"] != "http":
        return

    body = await read_body(receive)

    await send({
        "type": "http.response.start",
        "status": 200,
        "headers": [(b"content-type", b"text/plain")],
    })
    await send({
        "type": "http.response.body",
        "body": f"Received {len(body)} bytes".encode(),
    })
```

### Streaming Response

```python
import asyncio

async def app(scope: Scope, receive: Receive, send: Send) -> None:
    await send({
        "type": "http.response.start",
        "status": 200,
        "headers": [(b"content-type", b"text/event-stream")],
    })

    for i in range(10):
        await send({
            "type": "http.response.body",
            "body": f"data: event {i}\n\n".encode(),
            "more_body": True,
        })
        await asyncio.sleep(1)

    await send({
        "type": "http.response.body",
        "body": b"",
        "more_body": False,
    })
```

### Detecting Client Disconnect

```python
async def app(scope: Scope, receive: Receive, send: Send) -> None:
    receive_task = asyncio.create_task(receive())
    work_task = asyncio.create_task(expensive_computation())

    done, pending = await asyncio.wait(
        [receive_task, work_task],
        return_when=asyncio.FIRST_COMPLETED,
    )

    if receive_task in done:
        event = receive_task.result()
        if event["type"] == "http.disconnect":
            work_task.cancel()
            return

    # work_task completed first
    result = work_task.result()
    receive_task.cancel()

    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": result})
```

### JSON API Example

```python
import json

async def app(scope: Scope, receive: Receive, send: Send) -> None:
    if scope["type"] != "http":
        return

    method = scope["method"]
    path = scope["path"]

    if method == "GET" and path == "/users":
        users = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
        body = json.dumps(users).encode()

        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"application/json")],
        })
        await send({"type": "http.response.body", "body": body})

    elif method == "POST" and path == "/users":
        request_body = await read_body(receive)
        user = json.loads(request_body)

        await send({
            "type": "http.response.start",
            "status": 201,
            "headers": [(b"content-type", b"application/json")],
        })
        await send({
            "type": "http.response.body",
            "body": json.dumps({"id": 3, **user}).encode(),
        })

    else:
        await send({
            "type": "http.response.start",
            "status": 404,
            "headers": [(b"content-type", b"application/json")],
        })
        await send({
            "type": "http.response.body",
            "body": b'{"error": "Not Found"}',
        })
```

---

## WebSocket Protocol

### WebSocket Handshake

```python
async def app(scope: Scope, receive: Receive, send: Send) -> None:
    if scope["type"] != "websocket":
        return

    event = await receive()
    assert event["type"] == "websocket.connect"

    # Option 1: Accept
    await send({"type": "websocket.accept"})

    # Option 2: Accept with subprotocol
    await send({
        "type": "websocket.accept",
        "subprotocol": scope["subprotocols"][0] if scope["subprotocols"] else None,
    })

    # Option 3: Reject
    await send({"type": "websocket.close", "code": 4000})
```

### Echo Server

```python
async def app(scope: Scope, receive: Receive, send: Send) -> None:
    if scope["type"] != "websocket":
        return

    while True:
        event = await receive()

        if event["type"] == "websocket.connect":
            await send({"type": "websocket.accept"})

        elif event["type"] == "websocket.receive":
            if "text" in event:
                await send({"type": "websocket.send", "text": event["text"]})
            elif "bytes" in event:
                await send({"type": "websocket.send", "bytes": event["bytes"]})

        elif event["type"] == "websocket.disconnect":
            break
```

### Chat Room

```python
from typing import Any

rooms: dict[str, set[Send]] = {}


async def app(scope: Scope, receive: Receive, send: Send) -> None:
    if scope["type"] != "websocket":
        return

    # Get room from query string
    query = scope["query_string"].decode()
    room = query.split("=")[1] if "=" in query else "default"

    event = await receive()
    if event["type"] != "websocket.connect":
        return

    await send({"type": "websocket.accept"})

    # Join room
    if room not in rooms:
        rooms[room] = set()
    rooms[room].add(send)

    try:
        while True:
            event = await receive()

            if event["type"] == "websocket.disconnect":
                break

            if event["type"] == "websocket.receive":
                message = event.get("text", "")

                # Broadcast to room
                for member_send in rooms[room]:
                    await member_send({
                        "type": "websocket.send",
                        "text": message,
                    })
    finally:
        rooms[room].discard(send)
        if not rooms[room]:
            del rooms[room]
```

### WebSocket Close Codes

| Code      | Meaning              |
| --------- | -------------------- |
| 1000      | Normal closure       |
| 1001      | Going away           |
| 1002      | Protocol error       |
| 1003      | Unsupported data     |
| 1008      | Policy violation     |
| 1011      | Server error         |
| 4000-4999 | Application-specific |

---

## Lifespan Protocol

### What Is Lifespan?

Lifespan handles application startup and shutdown:

1. **Startup** — Initialize resources before serving requests
2. **Shutdown** — Clean up resources when server stops

It's a separate "connection" the server makes to your app.

### Lifespan Flow

```
Server starts
      │
      ▼
Server calls app(lifespan_scope, receive, send)
      │
      ▼
Server sends lifespan.startup via receive()
      │
      ├─── App initializes resources ───┐
      │                                 │
      ▼                                 ▼
App sends                          App sends
lifespan.startup.complete          lifespan.startup.failed
      │                                 │
      ▼                                 ▼
Server accepts requests            Server exits
      │
      │ ... handles requests ...
      │
      ▼
Server receives SIGTERM
      │
      ▼
Server sends lifespan.shutdown via receive()
      │
      ▼
App cleans up resources
      │
      ▼
App sends lifespan.shutdown.complete
      │
      ▼
Server exits cleanly
```

### Basic Implementation

```python
from typing import Any, Callable

async def app(scope: dict[str, Any], receive: Callable, send: Callable) -> None:
    if scope["type"] == "lifespan":
        await handle_lifespan(scope, receive, send)
    elif scope["type"] == "http":
        await handle_http(scope, receive, send)


async def handle_lifespan(
    scope: dict[str, Any],
    receive: Callable,
    send: Callable,
) -> None:
    while True:
        event = await receive()

        if event["type"] == "lifespan.startup":
            try:
                scope["state"]["db"] = await create_db_pool()
                scope["state"]["redis"] = await create_redis_client()
                await send({"type": "lifespan.startup.complete"})
            except Exception as e:
                await send({
                    "type": "lifespan.startup.failed",
                    "message": str(e),
                })
                return

        elif event["type"] == "lifespan.shutdown":
            await scope["state"]["db"].close()
            await scope["state"]["redis"].close()
            await send({"type": "lifespan.shutdown.complete"})
            return
```

### State Sharing

The `state` dict is shared across all connections:

```
┌─────────────────────────────────────────────────────────────┐
│                     Lifespan Scope                          │
│  scope["state"] = {"db": <Pool>, "redis": <Client>}         │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ same dict reference
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│  HTTP Scope 1 │     │  HTTP Scope 2 │     │  HTTP Scope 3 │
│  state = {...}│     │  state = {...}│     │  state = {...}│
└───────────────┘     └───────────────┘     └───────────────┘
```

### Context Manager Pattern

```python
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Callable

@asynccontextmanager
async def lifespan_context(state: dict[str, Any]) -> AsyncIterator[None]:
    # Startup
    state["db"] = await create_db_pool()
    state["redis"] = await create_redis_client()

    try:
        yield
    finally:
        # Shutdown (always runs)
        await state["redis"].close()
        await state["db"].close()


async def handle_lifespan(
    scope: dict[str, Any],
    receive: Callable,
    send: Callable,
) -> None:
    event = await receive()
    assert event["type"] == "lifespan.startup"

    try:
        async with lifespan_context(scope["state"]):
            await send({"type": "lifespan.startup.complete"})
            event = await receive()
            assert event["type"] == "lifespan.shutdown"

        await send({"type": "lifespan.shutdown.complete"})

    except Exception as e:
        await send({
            "type": "lifespan.startup.failed",
            "message": str(e),
        })
```

### FastAPI Pattern

```python
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.db = await create_db_pool()
    yield
    await app.state.db.close()


app = FastAPI(lifespan=lifespan)


@app.get("/users")
async def get_users(request: Request) -> list[dict]:
    db = request.app.state.db
    return await db.fetch("SELECT * FROM users")
```

### Common Patterns

**Database pool:**

```python
async def startup(state: dict) -> None:
    state["db"] = await asyncpg.create_pool(
        "postgresql://localhost/mydb",
        min_size=5,
        max_size=20,
    )

async def shutdown(state: dict) -> None:
    await state["db"].close()
```

**HTTP client:**

```python
import httpx

async def startup(state: dict) -> None:
    state["http"] = httpx.AsyncClient(timeout=30.0)

async def shutdown(state: dict) -> None:
    await state["http"].aclose()
```

**Background tasks:**

```python
async def startup(state: dict) -> None:
    async def cleanup_job() -> None:
        while True:
            await asyncio.sleep(3600)
            await cleanup_old_sessions()

    state["tasks"] = {asyncio.create_task(cleanup_job())}

async def shutdown(state: dict) -> None:
    for task in state["tasks"]:
        task.cancel()
    await asyncio.gather(*state["tasks"], return_exceptions=True)
```

**ML model:**

```python
async def startup(state: dict) -> None:
    state["model"] = await asyncio.to_thread(load_model, "model.pkl")

async def shutdown(state: dict) -> None:
    del state["model"]
```

---

## Middleware

### What Is Middleware?

Middleware wraps an ASGI app to intercept requests and responses:

```
┌──────────────────────────────────────────────────────────────────┐
│                           SERVER                                 │
└──────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                      Middleware 1                                │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                     Middleware 2                           │  │
│  │  ┌──────────────────────────────────────────────────────┐  │  │
│  │  │                   APPLICATION                        │  │  │
│  │  └──────────────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

### Basic Pattern

```python
from typing import Any, Callable

ASGIApp = Callable[..., Any]


class Middleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(
        self,
        scope: dict,
        receive: Callable,
        send: Callable,
    ) -> None:
        # Before
        await self.app(scope, receive, send)
        # After
```

### Three Interception Points

#### 1. Scope Modification

```python
class PathPrefixMiddleware:
    def __init__(self, app: ASGIApp, prefix: str) -> None:
        self.app = app
        self.prefix = prefix

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        if scope["type"] == "http" and scope["path"].startswith(self.prefix):
            scope = dict(scope)
            scope["path"] = scope["path"][len(self.prefix):]

        await self.app(scope, receive, send)
```

#### 2. Receive Wrapping

```python
class BodyLoggingMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        body_parts: list[bytes] = []

        async def receive_wrapper() -> dict:
            event = await receive()
            if event["type"] == "http.request":
                body_parts.append(event.get("body", b""))
                if not event.get("more_body"):
                    print(f"Body: {b''.join(body_parts)}")
            return event

        await self.app(scope, receive_wrapper, send)
```

#### 3. Send Wrapping

```python
class ResponseHeaderMiddleware:
    def __init__(self, app: ASGIApp, headers: list[tuple[bytes, bytes]]) -> None:
        self.app = app
        self.headers = headers

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(event: dict) -> None:
            if event["type"] == "http.response.start":
                event = dict(event)
                event["headers"] = list(event.get("headers", [])) + self.headers
            await send(event)

        await self.app(scope, receive, send_wrapper)
```

### Middleware Composition

```python
app = MyApplication()
app = AuthMiddleware(app)
app = LoggingMiddleware(app)
app = CORSMiddleware(app)

# Request:  CORS → Logging → Auth → App
# Response: App → Auth → Logging → CORS
```

### Common Middleware

#### Timing

```python
import time

class TimingMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.perf_counter()
        status = 0

        async def send_wrapper(event: dict) -> None:
            nonlocal status
            if event["type"] == "http.response.start":
                status = event["status"]
            await send(event)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            elapsed = time.perf_counter() - start
            print(f"{scope['method']} {scope['path']} → {status} in {elapsed:.3f}s")
```

#### Authentication

```python
class AuthMiddleware:
    def __init__(self, app: ASGIApp, secret: str) -> None:
        self.app = app
        self.secret = secret

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        auth = headers.get(b"authorization", b"").decode()

        if not auth.startswith("Bearer "):
            await self._unauthorized(send)
            return

        token = auth[7:]
        try:
            user = verify_jwt(token, self.secret)
            scope = dict(scope)
            scope["user"] = user
            await self.app(scope, receive, send)
        except InvalidToken:
            await self._unauthorized(send)

    async def _unauthorized(self, send: Callable) -> None:
        await send({
            "type": "http.response.start",
            "status": 401,
            "headers": [(b"content-type", b"application/json")],
        })
        await send({
            "type": "http.response.body",
            "body": b'{"error": "Unauthorized"}',
        })
```

#### CORS

```python
class CORSMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        origins: list[str],
        methods: list[str] = ["GET", "POST", "PUT", "DELETE"],
    ) -> None:
        self.app = app
        self.origins = origins
        self.methods = methods

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        origin = headers.get(b"origin", b"").decode()

        if origin not in self.origins and "*" not in self.origins:
            await self.app(scope, receive, send)
            return

        if scope["method"] == "OPTIONS":
            await self._preflight(send, origin)
            return

        async def send_wrapper(event: dict) -> None:
            if event["type"] == "http.response.start":
                event = dict(event)
                event["headers"] = list(event.get("headers", [])) + [
                    (b"access-control-allow-origin", origin.encode()),
                ]
            await send(event)

        await self.app(scope, receive, send_wrapper)

    async def _preflight(self, send: Callable, origin: str) -> None:
        await send({
            "type": "http.response.start",
            "status": 204,
            "headers": [
                (b"access-control-allow-origin", origin.encode()),
                (b"access-control-allow-methods", ", ".join(self.methods).encode()),
                (b"access-control-max-age", b"86400"),
            ],
        })
        await send({"type": "http.response.body", "body": b""})
```

#### Error Handling

```python
import traceback

class ErrorMiddleware:
    def __init__(self, app: ASGIApp, debug: bool = False) -> None:
        self.app = app
        self.debug = debug

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        response_started = False

        async def send_wrapper(event: dict) -> None:
            nonlocal response_started
            if event["type"] == "http.response.start":
                response_started = True
            await send(event)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            if response_started:
                raise

            body = traceback.format_exc() if self.debug else "Internal Server Error"

            await send({
                "type": "http.response.start",
                "status": 500,
                "headers": [(b"content-type", b"text/plain")],
            })
            await send({
                "type": "http.response.body",
                "body": body.encode(),
            })
```

#### Rate Limiting

```python
import time
from collections import defaultdict

class RateLimitMiddleware:
    def __init__(self, app: ASGIApp, rpm: int = 60) -> None:
        self.app = app
        self.rpm = rpm
        self.requests: dict[str, list[float]] = defaultdict(list)

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        client = scope.get("client")
        if not client:
            await self.app(scope, receive, send)
            return

        ip = client[0]
        now = time.time()

        # Clean old entries
        self.requests[ip] = [t for t in self.requests[ip] if t > now - 60]

        if len(self.requests[ip]) >= self.rpm:
            await send({
                "type": "http.response.start",
                "status": 429,
                "headers": [(b"retry-after", b"60")],
            })
            await send({
                "type": "http.response.body",
                "body": b"Too Many Requests",
            })
            return

        self.requests[ip].append(now)
        await self.app(scope, receive, send)
```

### Testing Middleware

```python
async def test_cors_middleware() -> None:
    async def app(scope: dict, receive: Callable, send: Callable) -> None:
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"OK"})

    middleware = CORSMiddleware(app, origins=["https://example.com"])

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(b"origin", b"https://example.com")],
    }

    events: list[dict] = []

    async def receive() -> dict:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(event: dict) -> None:
        events.append(event)

    await middleware(scope, receive, send)

    headers = dict(events[0]["headers"])
    assert headers[b"access-control-allow-origin"] == b"https://example.com"
```

---

## Server Implementations

### Popular Servers

| Server        | Features                       |
| ------------- | ------------------------------ |
| **Uvicorn**   | Fast, minimal, based on uvloop |
| **Hypercorn** | HTTP/2, HTTP/3, WebSocket      |
| **Daphne**    | Django Channels server         |
| **Granian**   | Rust-based, very fast          |

### Running Applications

```bash
# Uvicorn
uvicorn app:app --host 0.0.0.0 --port 8000 --reload

# Hypercorn
hypercorn app:app --bind 0.0.0.0:8000

# Granian
granian app:app --host 0.0.0.0 --port 8000
```

### Server Configuration

```python
# uvicorn programmatic
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        workers=4,
    )
```

---

## ASGI vs WSGI

| Aspect           | WSGI                        | ASGI                     |
| ---------------- | --------------------------- | ------------------------ |
| Interface        | `(environ, start_response)` | `(scope, receive, send)` |
| Concurrency      | Sync only                   | Async native             |
| Protocols        | HTTP only                   | HTTP, WebSocket, custom  |
| Streaming        | Limited                     | First-class              |
| Long connections | Not supported               | Native                   |

### WSGI

```python
def wsgi_app(environ, start_response):
    start_response("200 OK", [("Content-Type", "text/plain")])
    return [b"Hello, World!"]
```

### ASGI

```python
async def asgi_app(scope, receive, send):
    await send({
        "type": "http.response.start",
        "status": 200,
        "headers": [(b"content-type", b"text/plain")],
    })
    await send({
        "type": "http.response.body",
        "body": b"Hello, World!",
    })
```

---

## Type Definitions

```python
from typing import Any, Awaitable, Callable, TypeAlias

# Core types
Scope: TypeAlias = dict[str, Any]
Message: TypeAlias = dict[str, Any]
Receive: TypeAlias = Callable[[], Awaitable[Message]]
Send: TypeAlias = Callable[[Message], Awaitable[None]]
ASGIApp: TypeAlias = Callable[[Scope, Receive, Send], Awaitable[None]]

# Middleware type
Middleware: TypeAlias = Callable[[ASGIApp], ASGIApp]
```

### Typed Application

```python
from typing import Any, Awaitable, Callable

Scope = dict[str, Any]
Receive = Callable[[], Awaitable[dict[str, Any]]]
Send = Callable[[dict[str, Any]], Awaitable[None]]


async def app(scope: Scope, receive: Receive, send: Send) -> None:
    if scope["type"] == "http":
        await handle_http(scope, receive, send)
    elif scope["type"] == "websocket":
        await handle_websocket(scope, receive, send)
    elif scope["type"] == "lifespan":
        await handle_lifespan(scope, receive, send)


async def handle_http(scope: Scope, receive: Receive, send: Send) -> None:
    body = b""
    while True:
        event = await receive()
        body += event.get("body", b"")
        if not event.get("more_body", False):
            break

    await send({
        "type": "http.response.start",
        "status": 200,
        "headers": [(b"content-type", b"text/plain")],
    })
    await send({
        "type": "http.response.body",
        "body": f"Received {len(body)} bytes".encode(),
    })


async def handle_websocket(scope: Scope, receive: Receive, send: Send) -> None:
    while True:
        event = await receive()
        if event["type"] == "websocket.connect":
            await send({"type": "websocket.accept"})
        elif event["type"] == "websocket.receive":
            await send({"type": "websocket.send", "text": event.get("text", "")})
        elif event["type"] == "websocket.disconnect":
            break


async def handle_lifespan(scope: Scope, receive: Receive, send: Send) -> None:
    while True:
        event = await receive()
        if event["type"] == "lifespan.startup":
            await send({"type": "lifespan.startup.complete"})
        elif event["type"] == "lifespan.shutdown":
            await send({"type": "lifespan.shutdown.complete"})
            return
```

---

## References

- [ASGI Specification](https://asgi.readthedocs.io/en/latest/)
- [HTTP Connection Scope](https://asgi.readthedocs.io/en/latest/specs/www.html)
- [WebSocket Specification](https://asgi.readthedocs.io/en/latest/specs/www.html#websocket)
- [Lifespan Protocol](https://asgi.readthedocs.io/en/latest/specs/lifespan.html)
- [asgiref on GitHub](https://github.com/django/asgiref)
- [Uvicorn](https://www.uvicorn.org/)
- [Starlette](https://www.starlette.io/)
- [FastAPI](https://fastapi.tiangolo.com/)

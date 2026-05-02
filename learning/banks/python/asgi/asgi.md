# ASGI: The Complete Guide

ASGI (Asynchronous Server Gateway Interface) is the standard interface between async Python web servers and applications. It's the spiritual successor to WSGI, designed for the async era.

## Table of Contents

1. [Core Interface](#core-interface)
   - [The Three Components](#the-three-components)
   - [Scope vs Receive](#scope-vs-receive)
2. [Scope](#scope)
   - [Scope Types](#scope-types)
   - [HTTP Scope](#http-scope)
   - [WebSocket Scope](#websocket-scope)
   - [Lifespan Scope](#lifespan-scope)
   - [Extensions](#extensions)
3. [Receive](#receive)
   - [What receive() Does](#what-receive-does)
   - [HTTP Receive](#http-receive)
   - [WebSocket Receive](#websocket-receive)
   - [Lifespan Receive](#lifespan-receive)
   - [Receive Rules](#receive-rules)
4. [Send](#send)
   - [What send() Does](#what-send-does)
   - [HTTP Send](#http-send)
   - [WebSocket Send](#websocket-send)
   - [Lifespan Send](#lifespan-send)
   - [Send Rules](#send-rules)
5. [Events](#events)
   - [Event Naming Convention](#event-naming-convention)
   - [Event Directionality](#event-directionality)
   - [HTTP Events](#http-events)
   - [WebSocket Events](#websocket-events)
   - [Lifespan Events](#lifespan-events)
   - [Event Ordering Rules](#event-ordering-rules)
6. [Event Internals](#event-internals)
   - [Events Are Just Dicts](#events-are-just-dicts)
   - [receive() and send() Are Closures](#receive-and-send-are-closures)
   - [Server-Side Implementation](#server-side-implementation)
   - [Connection Lifecycle](#connection-lifecycle)
   - [Concurrency Model](#concurrency-model)
   - [Backpressure](#backpressure)
   - [State Machine](#state-machine)
   - [Memory Model](#memory-model)
7. [HTTP Protocol](#http-protocol)
   - [Reading Request Body](#reading-request-body)
   - [Streaming Response](#streaming-response)
   - [Detecting Client Disconnect](#detecting-client-disconnect)
   - [JSON API Example](#json-api-example)
   - [Error Handling](#error-handling)
   - [Routing](#routing)
   - [Server-Sent Events (SSE)](#server-sent-events-sse)
8. [WebSocket Protocol](#websocket-protocol)
   - [WebSocket Handshake](#websocket-handshake)
   - [Echo Server](#echo-server)
   - [Chat Room](#chat-room)
   - [WebSocket Close Codes](#websocket-close-codes)
9. [Lifespan Protocol](#lifespan-protocol)
   - [What Is Lifespan?](#what-is-lifespan)
   - [Lifespan Flow](#lifespan-flow)
   - [Basic Implementation](#basic-implementation)
   - [State Sharing](#state-sharing)
   - [Context Manager Pattern](#context-manager-pattern)
   - [FastAPI Pattern](#fastapi-pattern)
   - [Common Patterns](#common-patterns)
10. [Middleware](#middleware)
    - [What Is Middleware?](#what-is-middleware)
    - [Basic Pattern](#basic-pattern)
    - [Three Interception Points](#three-interception-points)
    - [Middleware Composition](#middleware-composition)
    - [Common Middleware](#common-middleware)
    - [Testing Middleware](#testing-middleware)
11. [Testing](#testing)
    - [Raw ASGI Testing](#raw-asgi-testing)
    - [Using httpx with ASGI Transport](#using-httpx-with-asgi-transport)
    - [Using Starlette TestClient](#using-starlette-testclient)
    - [Testing Lifespan](#testing-lifespan)
    - [Testing WebSockets](#testing-websockets)
12. [Request Lifecycle: From Socket to Response](#request-lifecycle-from-socket-to-response)
    - [The Big Picture](#the-big-picture)
    - [Step-by-Step Breakdown](#step-by-step-breakdown)
    - [How Multiple Requests Run Concurrently](#how-multiple-requests-run-concurrently)
    - [What Blocks the Event Loop (and Kills Throughput)](#what-blocks-the-event-loop-and-kills-throughput)
    - [Multiple Workers](#multiple-workers)
13. [Server Implementations](#server-implementations)
    - [Popular Servers](#popular-servers)
    - [Running Applications](#running-applications)
    - [HTTP/2 and HTTP/3](#http2-and-http3)
    - [Server Configuration](#server-configuration)
14. [ASGI vs WSGI](#asgi-vs-wsgi)
    - [WSGI](#wsgi)
    - [ASGI](#asgi)
    - [WSGI-to-ASGI Bridging](#wsgi-to-asgi-bridging)
15. [ASGI 3.0 Specification](#asgi-30-specification)
    - [Version vs Spec Version](#version-vs-spec-version)
    - [Single-Callable Interface (3.0)](#single-callable-interface-30)
    - [Double-Callable Interface (2.0)](#double-callable-interface-20)
    - [Migrating from 2.0 to 3.0](#migrating-from-20-to-30)
    - [Spec Versions by Protocol](#spec-versions-by-protocol)
    - [The `asgi` Scope Field](#the-asgi-scope-field)
16. [Security Considerations](#security-considerations)
    - [Header Injection](#header-injection)
    - [WebSocket Origin Validation](#websocket-origin-validation)
    - [Content-Length Correctness](#content-length-correctness)
    - [Request Size Limits](#request-size-limits)
    - [Timing Attacks](#timing-attacks)
17. [Type Definitions](#type-definitions)
    - [Typed Application](#typed-application)
18. [References](#references)

## Core Interface

An ASGI application is a single async callable:

```python
async def application(scope: dict, receive: Callable, send: Callable) -> None:
    ...
```

That's it. Three parameters, no return value.

> **ASGI versions:** ASGI 3.0 uses this single-callable pattern. ASGI 2.0 used a double-callable pattern where the first call received `scope` and returned a coroutine that accepted `receive` and `send`. If you encounter older code like `app = MyApp(scope)` followed by `await app(receive, send)`, that's the 2.0 style. The `asgiref` library provides `double_to_single_callable()` to convert between them.

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

## Scope

Scope is a dictionary containing connection metadata. It's created once per connection and passed to your application.

### Scope Types

ASGI defines three protocol types via `scope["type"]`:

| Type          | Description             |
| ------------- | ----------------------- |
| `"http"`      | HTTP request/response   |
| `"websocket"` | WebSocket connection    |
| `"lifespan"`  | Server startup/shutdown |

These are the **common scope** fields appear in all scope types:

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

### Extensions

Servers can advertise optional capabilities via `scope["extensions"]`:

```python
scope = {
    "type": "http",
    "extensions": {
        "http.response.pathsend": {},    # Zero-copy file sending
        "http.response.zerocopysend": {},
    },
    ...
}
```

Common extensions:

| Extension                    | Description                              |
| ---------------------------- | ---------------------------------------- |
| `http.response.pathsend`     | Send a file by path (server handles I/O) |
| `http.response.zerocopysend` | Zero-copy file sending                   |
| `websocket.http.response`    | Send HTTP response to reject WebSocket   |
| `http.response.trailers`     | HTTP trailer headers (HTTP/2+)           |

Check before using:

```python
async def app(scope: Scope, receive: Receive, send: Send) -> None:
    extensions = scope.get("extensions", {})

    if "http.response.pathsend" in extensions:
        await send({"type": "http.response.pathsend", "path": "/var/www/big-file.zip"})
    else:
        # Fall back to reading and sending manually
        ...
```

## Receive

`receive` is an async callable provided by the server. Your application calls `await receive()` to get the next inbound event — data flowing **from the client (or server lifecycle) to your application**.

### What receive() Does

```python
async def receive() -> dict:
    ...
```

Each call returns a single event dictionary with a `type` field. The call **blocks** (awaits) until an event is available. This is how ASGI delivers data incrementally — your app pulls events at its own pace.

```python
async def app(scope, receive, send):
    event = await receive()  # blocks until data arrives
    print(event["type"])     # e.g., "http.request"
```

### HTTP Receive

For HTTP connections, `receive()` yields request body chunks:

```python
# Event: http.request
{
    "type": "http.request",
    "body": b"chunk of body data",  # bytes, may be empty
    "more_body": True,              # False on final chunk
}
```

Reading the full body:

```python
async def read_body(receive):
    body = b""
    while True:
        event = await receive()
        body += event.get("body", b"")
        if not event.get("more_body"):
            break
    return body
```

After the body is fully received, calling `receive()` again will return an `http.disconnect` event when the client disconnects:

```python
# Event: http.disconnect
{
    "type": "http.disconnect",
}
```

### WebSocket Receive

For WebSocket connections, `receive()` yields connection and message events:

```python
# Event: websocket.connect (first event)
{
    "type": "websocket.connect",
}

# Event: websocket.receive (text message)
{
    "type": "websocket.receive",
    "text": "hello world",
}

# Event: websocket.receive (binary message)
{
    "type": "websocket.receive",
    "bytes": b"\x89\x00",
}

# Event: websocket.disconnect (client closed)
{
    "type": "websocket.disconnect",
    "code": 1000,
}
```

A typical WebSocket receive loop:

```python
async def ws_app(scope, receive, send):
    event = await receive()  # websocket.connect
    await send({"type": "websocket.accept"})

    while True:
        event = await receive()
        if event["type"] == "websocket.disconnect":
            break
        # event["type"] == "websocket.receive"
        message = event.get("text") or event.get("bytes")
        # process message...
```

### Lifespan Receive

For lifespan connections, `receive()` yields startup and shutdown signals:

```python
# Event: lifespan.startup
{
    "type": "lifespan.startup",
}

# Event: lifespan.shutdown
{
    "type": "lifespan.shutdown",
}
```

## Send

`send` is an async callable provided by the server. Your application calls `await send(event)` to push outbound events — data flowing **from your application to the client (or server lifecycle)**.

### What send() Does

```python
async def send(event: dict) -> None:
    ...
```

Each call sends a single event dictionary with a `type` field. The call may **block** if the server's write buffer is full (backpressure).

```python
async def app(scope, receive, send):
    await send({
        "type": "http.response.start",
        "status": 200,
        "headers": [(b"content-type", b"text/plain")],
    })
    await send({
        "type": "http.response.body",
        "body": b"Hello, world!",
    })
```

### HTTP Send

For HTTP connections, you send response headers then body chunks:

```python
# Event: http.response.start (must be sent first, exactly once)
{
    "type": "http.response.start",
    "status": 200,
    "headers": [
        (b"content-type", b"application/json"),
        (b"x-request-id", b"abc123"),
    ],
    "trailers": False,  # optional, indicates if trailers will follow
}

# Event: http.response.body (one or more chunks)
{
    "type": "http.response.body",
    "body": b"response data",
    "more_body": False,  # True if more chunks follow
}
```

Streaming a response in chunks:

```python
async def streaming_app(scope, receive, send):
    await send({
        "type": "http.response.start",
        "status": 200,
        "headers": [(b"content-type", b"text/plain")],
    })
    for chunk in [b"chunk1", b"chunk2", b"chunk3"]:
        await send({
            "type": "http.response.body",
            "body": chunk,
            "more_body": True,
        })
    await send({
        "type": "http.response.body",
        "body": b"",
        "more_body": False,  # signals end of response
    })
```

### WebSocket Send

For WebSocket connections, you send accept/close and message events:

```python
# Event: websocket.accept
{
    "type": "websocket.accept",
    "subprotocol": None,  # optional, selected subprotocol
    "headers": [],        # optional, additional response headers
}

# Event: websocket.send (text)
{
    "type": "websocket.send",
    "text": "hello back",
}

# Event: websocket.send (binary)
{
    "type": "websocket.send",
    "bytes": b"\x89\x00",
}

# Event: websocket.close
{
    "type": "websocket.close",
    "code": 1000,
    "reason": "",
}
```

Rejecting a WebSocket (requires `websocket.http.response` extension):

```python
# Event: websocket.http.response.start
{
    "type": "websocket.http.response.start",
    "status": 403,
    "headers": [(b"content-type", b"text/plain")],
}

# Event: websocket.http.response.body
{
    "type": "websocket.http.response.body",
    "body": b"Forbidden",
    "more_body": False,
}
```

### Lifespan Send

For lifespan connections, you send completion or failure signals:

```python
# Event: lifespan.startup.complete
{
    "type": "lifespan.startup.complete",
}

# Event: lifespan.startup.failed
{
    "type": "lifespan.startup.failed",
    "message": "Database connection refused",  # optional
}

# Event: lifespan.shutdown.complete
{
    "type": "lifespan.shutdown.complete",
}

# Event: lifespan.shutdown.failed
{
    "type": "lifespan.shutdown.failed",
    "message": "Failed to flush cache",  # optional
}
```

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

**`http.request`** _(receive)_ — Request body chunk

```python
{
    "type": "http.request",
    "body": b"...",        # Body bytes (may be empty)
    "more_body": False,    # True if more chunks coming
}
```

**`http.disconnect`** _(receive)_ — Client disconnected

```python
{
    "type": "http.disconnect",
}
```

**`http.response.start`** _(send)_ — Begin response (must be first)

```python
{
    "type": "http.response.start",
    "status": 200,
    "headers": [(b"content-type", b"text/plain")],
    "trailers": False,  # Optional, HTTP/2+ only — if True, server expects http.response.trailers event after body
}
```

**`http.response.body`** _(send)_ — Response body chunk

```python
{
    "type": "http.response.body",
    "body": b"...",        # Body bytes
    "more_body": False,    # True for streaming
}
```

### WebSocket Events

**`websocket.connect`** _(receive)_ — Client initiating connection

```python
{"type": "websocket.connect"}
```

**`websocket.receive`** _(receive)_ — Message from client

```python
{
    "type": "websocket.receive",
    "text": "hello",  # OR
    "bytes": b"...",  # Never both
}
```

**`websocket.disconnect`** _(receive)_ — Client disconnected

```python
{
    "type": "websocket.disconnect",
    "code": 1000,
}
```

**`websocket.accept`** _(send)_ — Accept connection

```python
{
    "type": "websocket.accept",
    "subprotocol": "graphql-ws",  # Optional
    "headers": [],                 # Optional
}
```

**`websocket.send`** _(send)_ — Send message

```python
{
    "type": "websocket.send",
    "text": "hello",  # OR
    "bytes": b"...",  # Never both
}
```

**`websocket.close`** _(send)_ — Close connection

```python
{
    "type": "websocket.close",
    "code": 1000,
    "reason": "",  # Optional
}
```

### Lifespan Events

**`lifespan.startup`** _(receive)_ — Server starting

```python
{"type": "lifespan.startup"}
```

**`lifespan.shutdown`** _(receive)_ — Server stopping

```python
{"type": "lifespan.shutdown"}
```

**`lifespan.startup.complete`** _(send)_ — Startup succeeded

```python
{"type": "lifespan.startup.complete"}
```

**`lifespan.startup.failed`** _(send)_ — Startup failed

```python
{"type": "lifespan.startup.failed", "message": "..."}
```

**`lifespan.shutdown.complete`** _(send)_ — Shutdown succeeded

```python
{"type": "lifespan.shutdown.complete"}
```

**`lifespan.shutdown.failed`** _(send)_ — Shutdown failed

```python
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

### Error Handling

What happens when your app raises an exception depends on **when** it occurs:

**Before `http.response.start`** — The server can still send an error response:

```python
async def app(scope: Scope, receive: Receive, send: Send) -> None:
    try:
        result = await process_request(scope, receive)
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": result})
    except Exception:
        await send({
            "type": "http.response.start",
            "status": 500,
            "headers": [(b"content-type", b"text/plain")],
        })
        await send({"type": "http.response.body", "body": b"Internal Server Error"})
```

**After `http.response.start`** — Headers are already on the wire. The server will typically close the connection abruptly. The client sees an incomplete response. There's no way to "take back" the status code:

```python
# DON'T do this — response.start already sent, second one will raise
await send({"type": "http.response.start", "status": 200, "headers": []})
await send({"type": "http.response.body", "body": chunk1, "more_body": True})
# If this raises, client gets a truncated response with status 200
await send({"type": "http.response.body", "body": chunk2, "more_body": False})
```

**Server behavior varies:** Uvicorn logs the traceback and closes the connection. Hypercorn does the same. Neither will send a 500 if headers were already sent. Always handle errors _before_ starting the response.

### Routing

Basic path-based routing at the ASGI level:

```python
from typing import Any, Callable

ASGIApp = Callable[..., Any]
Routes = dict[str, ASGIApp]


class Router:
    def __init__(self, routes: Routes) -> None:
        self.routes = routes

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        if scope["type"] not in ("http", "websocket"):
            # Pass lifespan through to a default handler
            return

        handler = self.routes.get(scope["path"])
        if handler is not None:
            await handler(scope, receive, send)
        else:
            await self._not_found(send)

    async def _not_found(self, send: Callable) -> None:
        await send({
            "type": "http.response.start",
            "status": 404,
            "headers": [(b"content-type", b"text/plain")],
        })
        await send({"type": "http.response.body", "body": b"Not Found"})


# Usage
app = Router({
    "/": home,
    "/users": users_handler,
    "/health": health_check,
})
```

For path parameters, use regex matching:

```python
import re


class RegexRouter:
    def __init__(self) -> None:
        self.routes: list[tuple[re.Pattern, ASGIApp]] = []

    def route(self, pattern: str) -> Callable:
        def decorator(func: ASGIApp) -> ASGIApp:
            self.routes.append((re.compile(f"^{pattern}$"), func))
            return func
        return decorator

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        for pattern, handler in self.routes:
            match = pattern.match(scope.get("path", ""))
            if match:
                scope = dict(scope, path_params=match.groupdict())
                await handler(scope, receive, send)
                return
        await self._not_found(send)


router = RegexRouter()


@router.route(r"/users/(?P<user_id>\d+)")
async def get_user(scope: dict, receive: Callable, send: Callable) -> None:
    user_id = scope["path_params"]["user_id"]
    ...
```

### Server-Sent Events (SSE)

The streaming response example uses `text/event-stream` but SSE has a specific protocol format:

```python
import asyncio
import json


async def sse_app(scope: Scope, receive: Receive, send: Send) -> None:
    if scope["type"] != "http":
        return

    await send({
        "type": "http.response.start",
        "status": 200,
        "headers": [
            (b"content-type", b"text/event-stream"),
            (b"cache-control", b"no-cache"),
            (b"connection", b"keep-alive"),
        ],
    })

    # Check for Last-Event-ID (client reconnection)
    headers = dict(scope.get("headers", []))
    last_id = headers.get(b"last-event-id", b"0").decode()
    start_from = int(last_id)

    for i in range(start_from + 1, start_from + 11):
        # SSE format: each field on its own line, blank line terminates event
        event = (
            f"id: {i}\n"
            f"event: update\n"
            f"data: {json.dumps({'count': i})}\n"
            f"retry: 5000\n"  # Client reconnect interval in ms
            f"\n"
        )
        await send({
            "type": "http.response.body",
            "body": event.encode(),
            "more_body": True,
        })
        await asyncio.sleep(1)

    await send({"type": "http.response.body", "body": b"", "more_body": False})
```

SSE format rules:

- Each event is one or more `field: value\n` lines followed by a blank line (`\n\n`)
- Fields: `data`, `event`, `id`, `retry`
- Multi-line data: use multiple `data:` lines
- The `id` field sets `Last-Event-ID` for automatic reconnection
- The `retry` field tells the browser how long to wait before reconnecting

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

## Lifespan Protocol

### What Is Lifespan?

Lifespan is a protocol for managing application startup and shutdown. Unlike HTTP or WebSocket, lifespan is not a network protocol — it's a control channel between the server and your application.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              ASGI Server                                 │
│                                                                         │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐  │
│  │    Lifespan     │  │      HTTP       │  │       WebSocket         │  │
│  │   (1 per app)   │  │  (per request)  │  │    (per connection)     │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────┘  │
│          │                    │                        │                │
│          └────────────────────┴────────────────────────┘                │
│                               │                                         │
│                               ▼                                         │
│                      ┌─────────────────┐                                │
│                      │   Your ASGI App │                                │
│                      └─────────────────┘                                │
└─────────────────────────────────────────────────────────────────────────┘
```

The lifespan protocol serves two purposes:

1. **Startup** — Initialize resources before the server accepts requests
2. **Shutdown** — Clean up resources when the server stops

### Why Use Lifespan?

Without lifespan, you might initialize resources lazily on first request:

```python
db_pool: Pool | None = None

async def get_db() -> Pool:
    global db_pool
    if db_pool is None:
        db_pool = await asyncpg.create_pool(...)  # First request is slow
    return db_pool
```

Problems with this approach:

| Issue | Description |
|-------|-------------|
| Cold start latency | First request pays initialization cost |
| Race conditions | Multiple requests may initialize simultaneously |
| No graceful shutdown | Resources leak when server stops |
| Error handling | Initialization errors surface as request errors |

Lifespan solves all of these by providing explicit startup/shutdown hooks.

### Lifespan Scope

When the server starts, it creates a lifespan scope:

```python
scope = {
    "type": "lifespan",
    "asgi": {
        "version": "3.0",
        "spec_version": "2.0",
    },
    "state": {},  # Shared with all connections (spec 2.0+)
}
```

| Field | Type | Description |
|-------|------|-------------|
| `type` | `str` | Always `"lifespan"` |
| `asgi.version` | `str` | ASGI version (`"3.0"` for single-callable) |
| `asgi.spec_version` | `str` | Lifespan spec version (default `"2.0"`) |
| `state` | `dict` | Mutable dict shared across all connections |

### Lifespan Events

#### Receive Events (Server → App)

| Event | Description |
|-------|-------------|
| `lifespan.startup` | Server is ready for app to initialize |
| `lifespan.shutdown` | Server is shutting down |

```python
# lifespan.startup
{"type": "lifespan.startup"}

# lifespan.shutdown
{"type": "lifespan.shutdown"}
```

#### Send Events (App → Server)

| Event | Description |
|-------|-------------|
| `lifespan.startup.complete` | App initialized successfully |
| `lifespan.startup.failed` | App failed to initialize |
| `lifespan.shutdown.complete` | App cleaned up successfully |
| `lifespan.shutdown.failed` | App failed to clean up |

```python
# Success
{"type": "lifespan.startup.complete"}
{"type": "lifespan.shutdown.complete"}

# Failure (message is optional)
{"type": "lifespan.startup.failed", "message": "Database connection refused"}
{"type": "lifespan.shutdown.failed", "message": "Failed to flush cache"}
```

### Lifespan Flow

```
Server process starts
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  Server calls app(lifespan_scope, receive, send)        │
└─────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  App awaits receive() → gets lifespan.startup           │
└─────────────────────────────────────────────────────────┘
         │
         ├──────────────────────────────────────┐
         │                                      │
         ▼                                      ▼
┌─────────────────────┐              ┌─────────────────────┐
│  Initialize OK      │              │  Initialize FAILED  │
│  - DB pool          │              │  - Connection error │
│  - Redis client     │              │  - Bad config       │
│  - Load ML model    │              │  - Missing deps     │
└─────────────────────┘              └─────────────────────┘
         │                                      │
         ▼                                      ▼
┌─────────────────────┐              ┌─────────────────────┐
│  send(startup.      │              │  send(startup.      │
│       complete)     │              │       failed)       │
└─────────────────────┘              └─────────────────────┘
         │                                      │
         ▼                                      ▼
┌─────────────────────┐              ┌─────────────────────┐
│  Server binds port  │              │  Server exits with  │
│  Accepts requests   │              │  error code         │
└─────────────────────┘              └─────────────────────┘
         │
         │  ... handles HTTP/WebSocket requests ...
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  Server receives SIGTERM/SIGINT                         │
│  Stops accepting new connections                        │
│  Waits for in-flight requests to complete               │
└─────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  App awaits receive() → gets lifespan.shutdown          │
└─────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  App cleans up resources                                │
│  - Close DB connections                                 │
│  - Flush caches                                         │
│  - Cancel background tasks                              │
└─────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  send(lifespan.shutdown.complete)                       │
└─────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  Server exits cleanly                                   │
└─────────────────────────────────────────────────────────┘
```

### Basic Implementation

#### Pattern 1: Event Loop

The most explicit pattern — handle events in a while loop:

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

#### Pattern 2: Context Manager

Cleaner separation using `@asynccontextmanager`:

```python
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Callable

@asynccontextmanager
async def lifespan_context(state: dict[str, Any]) -> AsyncIterator[None]:
    # ──────────── STARTUP ────────────
    state["db"] = await create_db_pool()
    state["redis"] = await create_redis_client()

    try:
        yield  # ← App runs here (server accepts requests)
    finally:
        # ──────────── SHUTDOWN ────────────
        # Always runs, even if startup.complete was never sent
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

The context manager pattern guarantees cleanup via `finally`, even if an exception occurs.

#### Pattern 3: FastAPI/Starlette

Frameworks simplify this further:

```python
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Startup
    app.state.db = await create_db_pool()
    app.state.redis = await create_redis_client()

    yield  # App runs

    # Shutdown
    await app.state.redis.close()
    await app.state.db.close()


app = FastAPI(lifespan=lifespan)


@app.get("/users")
async def get_users(request: Request) -> list[dict]:
    db = request.app.state.db
    return await db.fetch("SELECT * FROM users")
```

### State Sharing

The `state` dict in lifespan scope is shared with all HTTP/WebSocket connections:

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

This is the recommended way to share resources. Each HTTP request can access:

```python
async def handle_http(
    scope: dict[str, Any],
    receive: Callable,
    send: Callable,
) -> None:
    db = scope["state"]["db"]
    result = await db.fetch("SELECT * FROM users")
    # ...
```

In FastAPI/Starlette, access via `request.state`:

```python
@app.get("/items")
async def get_items(request: Request) -> list[dict]:
    db = request.app.state.db  # or request.state if copied
    return await db.fetch("SELECT * FROM items")
```

### Dependency Ordering

Resources often depend on each other. Initialize in dependency order, shutdown in reverse:

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # ──────────── STARTUP (dependency order) ────────────
    # 1. Config first (others depend on it)
    app.state.config = load_config()

    # 2. Database (uses config)
    app.state.db = await asyncpg.create_pool(app.state.config.db_url)

    # 3. Cache (uses config)
    app.state.cache = await aioredis.from_url(app.state.config.redis_url)

    # 4. Services (use db and cache)
    app.state.user_service = UserService(app.state.db, app.state.cache)

    yield

    # ──────────── SHUTDOWN (reverse order) ────────────
    # 4. Services first
    del app.state.user_service

    # 3. Cache
    await app.state.cache.close()

    # 2. Database
    await app.state.db.close()

    # 1. Config last
    del app.state.config
```

For complex dependencies, use a dependency graph:

```python
from typing import Any, AsyncIterator
from contextlib import asynccontextmanager, AsyncExitStack


class Resource:
    def __init__(self, name: str, deps: list[str] | None = None) -> None:
        self.name = name
        self.deps = deps or []

    @asynccontextmanager
    async def acquire(self, state: dict[str, Any]) -> AsyncIterator[Any]:
        raise NotImplementedError


class DatabaseResource(Resource):
    @asynccontextmanager
    async def acquire(self, state: dict[str, Any]) -> AsyncIterator[Any]:
        pool = await asyncpg.create_pool(state["config"].db_url)
        try:
            yield pool
        finally:
            await pool.close()


class CacheResource(Resource):
    @asynccontextmanager
    async def acquire(self, state: dict[str, Any]) -> AsyncIterator[Any]:
        client = await aioredis.from_url(state["config"].redis_url)
        try:
            yield client
        finally:
            await client.close()


async def initialize_resources(
    resources: list[Resource],
    state: dict[str, Any],
    stack: AsyncExitStack,
) -> None:
    initialized: set[str] = set()

    async def init_resource(resource: Resource) -> None:
        # Initialize dependencies first
        for dep in resource.deps:
            if dep not in initialized:
                dep_resource = next(r for r in resources if r.name == dep)
                await init_resource(dep_resource)

        # Initialize this resource
        value = await stack.enter_async_context(resource.acquire(state))
        state[resource.name] = value
        initialized.add(resource.name)

    for resource in resources:
        if resource.name not in initialized:
            await init_resource(resource)
```

### Error Handling Strategies

#### Startup Failures

If any resource fails to initialize, send `startup.failed` and exit:

```python
async def handle_lifespan(
    scope: dict[str, Any],
    receive: Callable,
    send: Callable,
) -> None:
    event = await receive()
    assert event["type"] == "lifespan.startup"

    try:
        # Initialize resources
        scope["state"]["db"] = await create_db_pool()
        scope["state"]["cache"] = await create_cache()
        await send({"type": "lifespan.startup.complete"})

    except asyncpg.PostgresError as e:
        await send({
            "type": "lifespan.startup.failed",
            "message": f"Database error: {e}",
        })
        return

    except Exception as e:
        await send({
            "type": "lifespan.startup.failed",
            "message": f"Unexpected error: {e}",
        })
        return

    # Wait for shutdown
    event = await receive()
    assert event["type"] == "lifespan.shutdown"

    # Cleanup...
    await send({"type": "lifespan.shutdown.complete"})
```

#### Partial Initialization Cleanup

If initialization fails midway, clean up what was already created:

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    resources_to_cleanup: list[Callable[[], Awaitable[None]]] = []

    try:
        # Each successful init adds its cleanup
        app.state.db = await create_db_pool()
        resources_to_cleanup.append(app.state.db.close)

        app.state.cache = await create_cache()  # May fail
        resources_to_cleanup.append(app.state.cache.close)

        app.state.queue = await create_queue()  # May fail
        resources_to_cleanup.append(app.state.queue.close)

        yield

    finally:
        # Cleanup in reverse order
        for cleanup in reversed(resources_to_cleanup):
            try:
                await cleanup()
            except Exception:
                pass  # Log but continue
```

Or use `AsyncExitStack` for automatic cleanup:

```python
from contextlib import asynccontextmanager, AsyncExitStack


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with AsyncExitStack() as stack:
        # Each enter_async_context registers cleanup automatically
        app.state.db = await stack.enter_async_context(create_db_pool())
        app.state.cache = await stack.enter_async_context(create_cache())
        app.state.queue = await stack.enter_async_context(create_queue())

        yield
        # AsyncExitStack cleans up in reverse order
```

#### Shutdown Failures

Shutdown failures are logged but typically don't prevent exit:

```python
async def shutdown(state: dict[str, Any]) -> None:
    errors: list[str] = []

    # Attempt all cleanups
    try:
        await state["db"].close()
    except Exception as e:
        errors.append(f"DB: {e}")

    try:
        await state["cache"].close()
    except Exception as e:
        errors.append(f"Cache: {e}")

    if errors:
        # Log but don't fail shutdown
        logger.error(f"Shutdown errors: {errors}")
```

### Graceful Shutdown Patterns

#### Timeout-Based Shutdown

Set a maximum time for cleanup:

```python
import asyncio


async def shutdown_with_timeout(
    state: dict[str, Any],
    timeout: float = 30.0,
) -> None:
    async def cleanup() -> None:
        await state["db"].close()
        await state["cache"].close()
        await state["queue"].close()

    try:
        await asyncio.wait_for(cleanup(), timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning(f"Shutdown timed out after {timeout}s")
```

#### Draining Connections

Wait for active connections to complete:

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.active_connections: set[asyncio.Task] = set()
    app.state.shutting_down = False

    yield

    # Signal shutdown
    app.state.shutting_down = True

    # Wait for active connections (with timeout)
    if app.state.active_connections:
        await asyncio.wait(
            app.state.active_connections,
            timeout=30.0,
        )

    # Force cancel remaining
    for task in app.state.active_connections:
        task.cancel()
```

#### Background Task Cancellation

Properly cancel and await background tasks:

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Start background tasks
    async def worker() -> None:
        while True:
            await process_queue()
            await asyncio.sleep(1)

    tasks = {
        asyncio.create_task(worker(), name="queue-worker"),
        asyncio.create_task(cleanup_job(), name="cleanup"),
    }

    yield

    # Cancel all tasks
    for task in tasks:
        task.cancel()

    # Wait for cancellation to complete
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Log any unexpected errors (CancelledError is expected)
    for task, result in zip(tasks, results):
        if isinstance(result, Exception) and not isinstance(result, asyncio.CancelledError):
            logger.error(f"Task {task.get_name()} failed: {result}")
```

### Common Resource Patterns

#### Database Connection Pool

```python
import asyncpg
from contextlib import asynccontextmanager


@asynccontextmanager
async def create_db_pool() -> AsyncIterator[asyncpg.Pool]:
    pool = await asyncpg.create_pool(
        "postgresql://user:pass@localhost/db",
        min_size=5,
        max_size=20,
        max_inactive_connection_lifetime=300,
    )
    try:
        yield pool
    finally:
        await pool.close()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with create_db_pool() as pool:
        app.state.db = pool
        yield
```

#### Redis Client

```python
import redis.asyncio as aioredis


@asynccontextmanager
async def create_redis() -> AsyncIterator[aioredis.Redis]:
    client = await aioredis.from_url(
        "redis://localhost:6379",
        encoding="utf-8",
        decode_responses=True,
    )
    try:
        yield client
    finally:
        await client.close()
```

#### HTTP Client

```python
import httpx


@asynccontextmanager
async def create_http_client() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        timeout=30.0,
        limits=httpx.Limits(max_connections=100),
    ) as client:
        yield client
```

#### Background Task Manager

```python
import asyncio
from typing import Callable, Coroutine, Any


class TaskManager:
    def __init__(self) -> None:
        self.tasks: set[asyncio.Task] = set()

    def create_task(
        self,
        coro: Coroutine[Any, Any, Any],
        name: str | None = None,
    ) -> asyncio.Task:
        task = asyncio.create_task(coro, name=name)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return task

    async def shutdown(self, timeout: float = 30.0) -> None:
        for task in self.tasks:
            task.cancel()

        if self.tasks:
            await asyncio.wait(self.tasks, timeout=timeout)


@asynccontextmanager
async def create_task_manager() -> AsyncIterator[TaskManager]:
    manager = TaskManager()
    try:
        yield manager
    finally:
        await manager.shutdown()
```

#### ML Model Loading

```python
import asyncio
from typing import Any


@asynccontextmanager
async def load_ml_model(path: str) -> AsyncIterator[Any]:
    # Load in thread pool to avoid blocking
    model = await asyncio.to_thread(joblib.load, path)
    try:
        yield model
    finally:
        # Explicit cleanup if needed
        del model
```

#### Message Queue Consumer

```python
import aio_pika


@asynccontextmanager
async def create_queue_connection() -> AsyncIterator[aio_pika.Connection]:
    connection = await aio_pika.connect_robust("amqp://guest:guest@localhost/")
    try:
        yield connection
    finally:
        await connection.close()
```

### Health Checks During Startup

Verify resources are actually working:

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Initialize
    app.state.db = await asyncpg.create_pool(DATABASE_URL)
    app.state.cache = await aioredis.from_url(REDIS_URL)

    # Health checks
    try:
        await app.state.db.fetchval("SELECT 1")
    except Exception as e:
        await app.state.db.close()
        raise RuntimeError(f"Database health check failed: {e}")

    try:
        await app.state.cache.ping()
    except Exception as e:
        await app.state.db.close()
        await app.state.cache.close()
        raise RuntimeError(f"Redis health check failed: {e}")

    yield

    await app.state.cache.close()
    await app.state.db.close()
```

### Lazy Initialization

For expensive resources that may not be needed:

```python
from typing import TypeVar, Generic, Callable, Awaitable

T = TypeVar("T")


class LazyResource(Generic[T]):
    def __init__(self, factory: Callable[[], Awaitable[T]]) -> None:
        self._factory = factory
        self._value: T | None = None
        self._lock = asyncio.Lock()

    async def get(self) -> T:
        if self._value is None:
            async with self._lock:
                if self._value is None:
                    self._value = await self._factory()
        return self._value

    async def close(self, cleanup: Callable[[T], Awaitable[None]]) -> None:
        if self._value is not None:
            await cleanup(self._value)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # ML model only loaded if endpoint is called
    app.state.model = LazyResource(lambda: asyncio.to_thread(load_model))

    yield

    await app.state.model.close(lambda m: asyncio.to_thread(lambda: None))
```

### Server-Specific Behavior

Different servers handle lifespan differently:

| Server | Lifespan Default | Disable Flag |
|--------|------------------|--------------|
| Uvicorn | Enabled (`auto`) | `--lifespan off` |
| Hypercorn | Enabled | Config option |
| Daphne | Enabled | N/A |
| Granian | Enabled | N/A |

#### Uvicorn Lifespan Modes

```bash
# Auto-detect (default) - enables if app handles lifespan
uvicorn app:app --lifespan auto

# Always enable - error if app doesn't handle lifespan
uvicorn app:app --lifespan on

# Disable - skip lifespan entirely
uvicorn app:app --lifespan off
```

#### Handling Missing Lifespan Support

If your app might run on servers without lifespan support:

```python
async def app(
    scope: dict[str, Any],
    receive: Callable,
    send: Callable,
) -> None:
    if scope["type"] == "lifespan":
        await handle_lifespan(scope, receive, send)
    elif scope["type"] == "http":
        # Fallback: lazy initialization if lifespan wasn't called
        if "db" not in scope.get("state", {}):
            scope.setdefault("state", {})["db"] = await create_db_pool()
        await handle_http(scope, receive, send)
```

### Testing Lifespan

#### Using asgi-lifespan

```python
import httpx
import pytest
from asgi_lifespan import LifespanManager


@pytest.mark.anyio
async def test_app_with_lifespan():
    async with LifespanManager(app) as manager:
        transport = httpx.ASGITransport(app=manager.app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            response = await client.get("/users")
            assert response.status_code == 200
```

#### Manual Testing

```python
async def test_lifespan_manually():
    scope = {"type": "lifespan", "asgi": {"version": "3.0"}, "state": {}}
    events: list[dict] = []

    async def receive() -> dict:
        if not events:
            events.append({"type": "lifespan.startup"})
        return events.pop(0)

    sent: list[dict] = []

    async def send(event: dict) -> None:
        sent.append(event)
        if event["type"] == "lifespan.startup.complete":
            events.append({"type": "lifespan.shutdown"})

    await app(scope, receive, send)

    assert sent[0]["type"] == "lifespan.startup.complete"
    assert sent[1]["type"] == "lifespan.shutdown.complete"
    assert "db" in scope["state"]
```

### Common Pitfalls

#### 1. Not Handling Lifespan at All

```python
# BAD: Ignores lifespan, server hangs waiting for response
async def app(scope: dict, receive: Callable, send: Callable) -> None:
    if scope["type"] == "http":
        await handle_http(scope, receive, send)
    # Missing lifespan handler!


# GOOD: Handle or explicitly pass through
async def app(scope: dict, receive: Callable, send: Callable) -> None:
    if scope["type"] == "lifespan":
        await handle_lifespan(scope, receive, send)
    elif scope["type"] == "http":
        await handle_http(scope, receive, send)
```

#### 2. Blocking the Event Loop

```python
# BAD: Blocks during startup
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.model = load_large_model()  # Sync, blocks event loop
    yield


# GOOD: Use thread pool for blocking operations
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.model = await asyncio.to_thread(load_large_model)
    yield
```

#### 3. Not Cleaning Up on Failure

```python
# BAD: If cache fails, db connection leaks
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.db = await create_db_pool()
    app.state.cache = await create_cache()  # If this fails, db leaks
    yield
    await app.state.cache.close()
    await app.state.db.close()


# GOOD: Use AsyncExitStack for automatic cleanup
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with AsyncExitStack() as stack:
        app.state.db = await stack.enter_async_context(create_db_pool())
        app.state.cache = await stack.enter_async_context(create_cache())
        yield
```

#### 4. Race Conditions with State

```python
# BAD: Multiple workers might initialize simultaneously
db_pool = None

async def get_db() -> Pool:
    global db_pool
    if db_pool is None:
        db_pool = await create_pool()  # Race condition!
    return db_pool


# GOOD: Initialize once in lifespan, access via state
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.db = await create_pool()
    yield
    await app.state.db.close()
```

#### 5. Forgetting to Cancel Background Tasks

```python
# BAD: Tasks keep running after shutdown
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    task = asyncio.create_task(background_worker())
    yield
    # Task is orphaned!


# GOOD: Cancel and await
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    task = asyncio.create_task(background_worker())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
```

#### 6. Swallowing Startup Errors

```python
# BAD: Hides the real error
async def handle_lifespan(scope: dict, receive: Callable, send: Callable) -> None:
    event = await receive()
    try:
        await initialize()
        await send({"type": "lifespan.startup.complete"})
    except Exception:
        await send({"type": "lifespan.startup.failed"})  # No message!


# GOOD: Include error details
async def handle_lifespan(scope: dict, receive: Callable, send: Callable) -> None:
    event = await receive()
    try:
        await initialize()
        await send({"type": "lifespan.startup.complete"})
    except Exception as e:
        await send({
            "type": "lifespan.startup.failed",
            "message": f"{type(e).__name__}: {e}",
        })
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
                (b"access-control-allow-headers", b"content-type, authorization"),
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
    """Simple in-memory rate limiter. Not safe for multi-worker/multi-process
    deployments — use Redis or a shared store for production."""

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

## Testing

### Raw ASGI Testing

Test any ASGI app without a server by providing mock `receive` and `send`:

```python
import asyncio


async def call_asgi(
    app,
    scope: dict,
    body: bytes = b"",
) -> tuple[int, list[tuple[bytes, bytes]], bytes]:
    """Call an ASGI app and return (status, headers, body)."""
    request_complete = False
    response_started = False
    status = 0
    headers: list[tuple[bytes, bytes]] = []
    body_parts: list[bytes] = []

    async def receive() -> dict:
        nonlocal request_complete
        if not request_complete:
            request_complete = True
            return {"type": "http.request", "body": body, "more_body": False}
        # Block until disconnect (never in tests)
        await asyncio.Event().wait()
        return {"type": "http.disconnect"}

    async def send(event: dict) -> None:
        nonlocal response_started, status
        if event["type"] == "http.response.start":
            response_started = True
            status = event["status"]
            headers.extend(event.get("headers", []))
        elif event["type"] == "http.response.body":
            body_parts.append(event.get("body", b""))

    await app(scope, receive, send)
    return status, headers, b"".join(body_parts)


# Usage
async def test_my_app() -> None:
    status, headers, body = await call_asgi(
        app,
        {"type": "http", "method": "GET", "path": "/", "headers": []},
    )
    assert status == 200
    assert body == b"Hello, World!"
```

### Using httpx with ASGI Transport

`httpx` can call ASGI apps directly — no server needed:

```python
import httpx
import pytest


@pytest.mark.anyio
async def test_get_users():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/users")
        assert response.status_code == 200
        assert len(response.json()) > 0


@pytest.mark.anyio
async def test_post_user():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/users", json={"name": "Alice"})
        assert response.status_code == 201
```

### Using Starlette TestClient

Starlette's `TestClient` wraps `httpx` and adds sync convenience:

```python
from starlette.testclient import TestClient


def test_homepage():
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200


def test_websocket():
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.send_text("hello")
        data = ws.receive_text()
        assert data == "hello"
```

### Testing Lifespan

Use `asgi-lifespan` to trigger startup/shutdown in tests:

```python
import httpx
from asgi_lifespan import LifespanManager


@pytest.mark.anyio
async def test_with_lifespan():
    async with LifespanManager(app) as manager:
        transport = httpx.ASGITransport(app=manager.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/users")
            assert response.status_code == 200
```

### Testing WebSockets

```python
import asyncio


async def test_websocket_echo() -> None:
    events_received: list[dict] = []
    messages_to_send = [
        {"type": "websocket.connect"},
        {"type": "websocket.receive", "text": "hello"},
        {"type": "websocket.disconnect", "code": 1000},
    ]
    send_index = 0

    async def receive() -> dict:
        nonlocal send_index
        event = messages_to_send[send_index]
        send_index += 1
        return event

    async def send(event: dict) -> None:
        events_received.append(event)

    scope = {"type": "websocket", "path": "/ws", "headers": [], "query_string": b""}
    await app(scope, receive, send)

    assert events_received[0] == {"type": "websocket.accept"}
    assert events_received[1] == {"type": "websocket.send", "text": "hello"}
```

## Request Lifecycle: From Socket to Response

This section traces exactly what happens from the moment a TCP connection arrives at Uvicorn to when your ASGI application sends back a response.

### The Big Picture

```
Client                    OS                     Uvicorn                    Your App
  |                        |                        |                           |
  |--- TCP SYN ----------->|                        |                           |
  |<-- TCP SYN-ACK --------|                        |                           |
  |--- TCP ACK ----------->|                        |                           |
  |                        |-- fd ready (readable)->|                           |
  |--- HTTP request ------>|                        |                           |
  |                        |-- epoll/kqueue wakes ->|                           |
  |                        |                        |-- accept() returns fd     |
  |                        |                        |-- parse HTTP headers      |
  |                        |                        |-- build scope dict        |
  |                        |                        |-- create receive queue    |
  |                        |                        |-- create send callback    |
  |                        |                        |-- await app(scope, receive, send)
  |                        |                        |                           |
  |                        |                        |                   await receive()
  |                        |                        |-- push body event -->     |
  |                        |                        |                   process request
  |                        |                        |                   await send(headers)
  |                        |                        |<-- write headers --|      |
  |                        |                        |                   await send(body)
  |                        |                        |<-- write body ----|       |
  |<-- HTTP response ------|------------------------|                           |
  |                        |                        |-- coroutine returns       |
  |                        |                        |-- close connection        |
```

### Step-by-Step Breakdown

#### 1. Server Boots — Event Loop Starts

When you run `uvicorn app:app`, this happens:

```python
# Simplified version of what uvicorn does internally
import asyncio
import uvloop  # if available

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
loop = asyncio.new_event_loop()

# Create a TCP server on the specified host:port
server = await asyncio.start_server(handle_connection, host="0.0.0.0", port=8000)

# The event loop now listens for incoming connections
loop.run_forever()
```

At this point, the event loop is idle — it's registered with the OS kernel's I/O notification mechanism (`kqueue` on macOS, `epoll` on Linux) and consumes zero CPU while waiting.

#### 2. Connection Arrives — OS Notifies the Event Loop

When a client sends a TCP SYN packet:

1. The OS kernel completes the TCP three-way handshake
2. The new connection lands in the server socket's **accept queue** (backlog)
3. The kernel marks the server socket's file descriptor as "readable"
4. `kqueue`/`epoll` wakes up the event loop — "hey, there's a connection waiting"
5. The event loop calls `accept()` to get a new file descriptor for this connection

```python
# This is what asyncio.start_server does under the hood
client_fd = server_socket.accept()  # returns immediately, connection already queued
```

#### 3. HTTP Parsing — Reading from the Socket

The event loop registers the new client fd for read events. When HTTP data arrives:

```python
# Uvicorn uses httptools (C extension) for fast HTTP parsing
from httptools import HttpRequestParser

class RequestParser:
    def on_url(self, url: bytes):
        self.url = url

    def on_header(self, name: bytes, value: bytes):
        self.headers.append((name.lower(), value))

    def on_headers_complete(self):
        # All headers received — we can now build the ASGI scope
        self.headers_done = True

    def on_body(self, body: bytes):
        # Body chunk received — queue it for receive()
        self.body_chunks.append(body)
```

The parser is event-driven — it processes bytes as they arrive from the socket, without blocking the event loop.

#### 4. Scope Construction — The Handoff Point

Once headers are fully parsed, Uvicorn builds the `scope` dictionary:

```python
scope = {
    "type": "http",
    "asgi": {"version": "3.0"},
    "http_version": "1.1",
    "method": "GET",
    "path": "/users/42",
    "query_string": b"format=json",
    "root_path": "",
    "headers": [
        (b"host", b"example.com"),
        (b"accept", b"application/json"),
    ],
    "server": ("0.0.0.0", 8000),
    "client": ("192.168.1.100", 54321),
}
```

It also creates the `receive` and `send` callables — these are closures that bridge your app back to the server's I/O layer.

#### 5. App Invocation — Your Coroutine Starts

```python
# Uvicorn does essentially this:
coroutine = app(scope, receive, send)
task = loop.create_task(coroutine)
```

This creates a **Task** on the event loop. The event loop schedules it, and your app's `__call__` (or the function) starts executing.

**Key point**: `create_task` does not block. Uvicorn immediately returns to the event loop, which can accept more connections while your app runs.

#### 6. Your App Calls `await receive()`

When your app needs the request body:

```python
async def app(scope, receive, send):
    event = await receive()  # What happens here?
```

Inside Uvicorn, `receive()` checks an internal queue:

```python
# Simplified Uvicorn receive implementation
class HTTPProtocol:
    def __init__(self):
        self.body_queue = asyncio.Queue()

    async def receive(self) -> dict:
        # If body already arrived and was queued by the parser, returns immediately
        # If body hasn't arrived yet, this awaits — yielding control to the event loop
        event = await self.body_queue.get()
        return event

    def on_body(self, data: bytes):
        # Called by httptools parser when body bytes arrive from socket
        self.body_queue.put_nowait({
            "type": "http.request",
            "body": data,
            "more_body": False,
        })
```

Two scenarios:

- **Body already buffered**: `receive()` returns immediately, no event loop yield
- **Body not yet arrived**: `await` suspends your coroutine, the event loop processes other tasks (other requests!), and resumes your coroutine when body data arrives on the socket

#### 7. Your App Calls `await send()`

```python
# Your app sends the response
await send({
    "type": "http.response.start",
    "status": 200,
    "headers": [(b"content-type", b"application/json")],
})
await send({
    "type": "http.response.body",
    "body": b'{"id": 42, "name": "Alice"}',
})
```

Inside Uvicorn:

```python
class HTTPProtocol:
    async def send(self, event: dict) -> None:
        if event["type"] == "http.response.start":
            # Format HTTP status line + headers, write to socket buffer
            self.transport.write(
                b"HTTP/1.1 200 OK\r\n"
                b"content-type: application/json\r\n"
                b"\r\n"
            )
        elif event["type"] == "http.response.body":
            self.transport.write(event.get("body", b""))
            if not event.get("more_body"):
                # Response complete — close or keep-alive
                self.transport.close()
```

The `transport.write()` call is **non-blocking** — it copies data to the kernel's send buffer. If the buffer is full (slow client), `await drain()` yields back to the event loop until the kernel signals the socket is writable again.

#### 8. Coroutine Returns — Connection Cleanup

When your app function returns (or the last `send()` with `more_body=False` completes):

1. The Task is marked as done
2. Uvicorn closes the connection (or keeps it alive for HTTP/1.1 keep-alive)
3. The file descriptor is deregistered from `kqueue`/`epoll`
4. All closures (`receive`, `send`) and the `scope` dict become garbage-collectible

### How Multiple Requests Run Concurrently

The event loop is **single-threaded** but handles many requests by never blocking:

```
Event Loop (single thread)
│
├─ Iteration 1:
│   ├─ accept() new connection → create Task A
│   ├─ resume Task B (body arrived) → B calls send()
│   └─ resume Task C (socket writable) → C finishes send()
│
├─ Iteration 2:
│   ├─ accept() new connection → create Task D
│   ├─ resume Task A (headers parsed) → A calls receive()
│   └─ Task C done → cleanup
│
├─ Iteration 3:
│   ├─ resume Task A (body arrived) → A processes, calls send()
│   ├─ resume Task D (headers parsed) → D calls receive()
│   └─ resume Task B (socket writable) → B continues streaming
│
└─ ... (continues forever)
```

Every `await` is a **yield point** — the coroutine voluntarily gives control back to the event loop, which picks up the next ready task. No thread switching, no locks, no context-switch overhead.

### What Blocks the Event Loop (and Kills Throughput)

If any coroutine does synchronous/CPU-bound work without yielding:

```python
async def bad_app(scope, receive, send):
    # This blocks the ENTIRE event loop for 5 seconds
    # No other request can be accepted or processed
    import time
    time.sleep(5)  # WRONG — use await asyncio.sleep(5)

    # This also blocks — CPU-bound with no yield points
    result = compute_fibonacci(10_000_000)  # WRONG — use run_in_executor
```

While a coroutine is blocking, the event loop cannot:

- Accept new connections
- Read data from other sockets
- Resume other coroutines
- Send responses to other clients

The fix: offload blocking work to a thread pool:

```python
async def good_app(scope, receive, send):
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, compute_fibonacci, 10_000_000)
    # Event loop was free to handle other requests while executor thread worked
```

### Multiple Workers

A single Uvicorn process runs one event loop on one CPU core. To utilize multiple cores, you run multiple **worker processes**.

```
                         Master Process (uvicorn --workers 4)
                                |
                    fork() fork() fork() fork()
                     |       |       |       |
                 Worker 1  Worker 2  Worker 3  Worker 4
                 (pid 101) (pid 102) (pid 103) (pid 104)
                     |       |       |       |
                 Event Loop Event Loop Event Loop Event Loop
```

#### How Connections Get Distributed

Uvicorn with `--workers` uses the **pre-fork model** (via Gunicorn's process manager). The master process creates the listening socket, then `fork()`s. All children inherit the same file descriptor. When a connection arrives, the OS wakes one worker to `accept()` it:

```python
# Master process (simplified)
server_socket = socket.socket()
server_socket.bind(("0.0.0.0", 8000))
server_socket.listen(backlog=128)

for _ in range(4):
    pid = os.fork()
    if pid == 0:
        # Child process — runs its own event loop on the shared socket
        loop = asyncio.new_event_loop()
        loop.run_until_complete(serve(server_socket, app))
```

```
Client A ──┐
Client B ──┤── kernel ──┬── Worker 1 accepts Client A
Client C ──┤            ├── Worker 2 accepts Client B
Client D ──┘            ├── Worker 3 accepts Client C
                        └── Worker 4 accepts Client D
```

#### What's Shared and What's Not

|                            | Shared across workers | Per-worker                  |
| -------------------------- | --------------------- | --------------------------- |
| Listening socket           | Yes (inherited fd)    | —                           |
| Event loop                 | —                     | Each has its own            |
| Memory / Python objects    | —                     | Completely isolated         |
| In-memory caches, globals  | —                     | Not shared                  |
| `scope`, `receive`, `send` | —                     | Belong to one worker        |
| Database connection pools  | —                     | Each worker creates its own |

Since workers are **separate OS processes**, they bypass the GIL entirely. 4 workers = 4 Python interpreters = 4 CPU cores utilized. But there are tradeoffs:

- **No shared state** — if Worker 1 caches something in a Python dict, Worker 2 doesn't see it. You need Redis, a database, or shared memory for cross-worker state.
- **No shared connections** — a WebSocket connected to Worker 1 can't be accessed from Worker 2. This is why sticky sessions or a pub/sub layer (like Redis) matter for real-time features.
- **Memory multiplied** — each worker loads the full application into its own memory space. 4 workers with a 200MB app = ~800MB total (copy-on-write helps initially, but diverges as each worker processes different requests).

#### When More Workers Help (and When They Don't)

```
1 worker:   1 event loop, 1 CPU core, handles thousands of concurrent I/O-bound requests
4 workers:  4 event loops, 4 CPU cores, handles thousands × 4 concurrent requests
```

| Scenario                                        | More workers help? | Why                                     |
| ----------------------------------------------- | ------------------ | --------------------------------------- |
| CPU-bound work saturating one core              | Yes                | Each worker gets its own core           |
| Fault isolation needed                          | Yes                | One worker crashing doesn't kill others |
| Bottleneck is a slow database                   | No                 | All workers wait on the same DB         |
| Already I/O-bound, single loop handles the load | No                 | Adding workers just wastes memory       |

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

### HTTP/2 and HTTP/3

ASGI is protocol-agnostic — your app code doesn't change between HTTP versions. The differences show up in `scope["http_version"]` and server capabilities:

| Version  | `http_version` | Key Features                     | Server Support           |
| -------- | -------------- | -------------------------------- | ------------------------ |
| HTTP/1.1 | `"1.1"`        | Keep-alive, chunked transfer     | All servers              |
| HTTP/2   | `"2"`          | Multiplexing, header compression | Hypercorn, Granian       |
| HTTP/3   | `"3"`          | QUIC-based, faster handshakes    | Hypercorn (experimental) |

From the app's perspective, the only visible difference is `scope["http_version"]`. Multiplexing and stream management are handled by the server. Trailers (`http.response.trailers` extension) are only available on HTTP/2+.

```bash
# Hypercorn with HTTP/2
hypercorn app:app --bind 0.0.0.0:443 --certfile cert.pem --keyfile key.pem

# Hypercorn with HTTP/3 (experimental)
hypercorn app:app --quic-bind 0.0.0.0:443 --certfile cert.pem --keyfile key.pem
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

### WSGI-to-ASGI Bridging

You can wrap existing WSGI apps to run inside ASGI servers. This is common in Django projects migrating to async:

```python
# Using asgiref
from asgiref.wsgi import WsgiToAsgi

def wsgi_app(environ, start_response):
    start_response("200 OK", [("Content-Type", "text/plain")])
    return [b"Hello from WSGI"]

asgi_app = WsgiToAsgi(wsgi_app)
```

```python
# Django's built-in ASGI handler
# django/project/asgi.py
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")
application = get_asgi_application()
```

**How it works:** The bridge runs the sync WSGI callable in a thread pool (`asyncio.to_thread`) and translates between `environ`/`start_response` and ASGI's `scope`/`receive`/`send`.

**Limitations:**

- WSGI apps wrapped this way still run synchronously — they just don't block the event loop
- WebSocket and lifespan protocols are not available to the WSGI app
- Each request occupies a thread from the pool

---

## ASGI 3.0 Specification

ASGI has two versioning layers: the **ASGI version** (the callable interface) and **spec versions** (per-protocol details). Understanding both is essential for building and debugging ASGI applications.

### Version vs Spec Version

| Concept      | What It Describes                                 | Example        |
| ------------ | ------------------------------------------------- | -------------- |
| ASGI version | The callable signature (how server calls the app) | `"3.0"`        |
| Spec version | Protocol-specific event and scope details         | `"2.4"` (HTTP) |

The ASGI version changes rarely — it defines the fundamental contract. Spec versions evolve independently per protocol as new fields, events, or extensions are added.

### Single-Callable Interface (3.0)

ASGI 3.0 defines the application as a **single async callable** that receives all three arguments at once:

```python
async def application(scope: dict, receive: Callable, send: Callable) -> None:
    ...
```

This is the current standard. All modern frameworks (Starlette, FastAPI, Django 3.0+, Quart, Litestar) use this interface.

Key properties:

- **One call per connection** — the server calls `application()` once for each HTTP request, WebSocket connection, or lifespan event
- **Non-blocking** — the callable is `async`, so it must not block the event loop
- **No return value** — communication happens entirely through `receive()` and `send()`
- **Stateless between calls** — each invocation is independent; shared state lives in `scope["state"]` or external stores

### Double-Callable Interface (2.0)

ASGI 2.0 used a **double-callable** pattern where the first call received only `scope` and returned a coroutine:

```python
# ASGI 2.0 — DEPRECATED
class Application:
    def __init__(self, scope: dict) -> None:
        self.scope = scope

    async def __call__(self, receive: Callable, send: Callable) -> None:
        ...

# Or as nested callables:
def application(scope: dict) -> Callable:
    async def asgi_coroutine(receive: Callable, send: Callable) -> None:
        ...
    return asgi_coroutine
```

The rationale was to allow per-connection initialization in `__init__`, but this added complexity without real benefit — the same initialization can happen at the start of a single callable.

**Why 2.0 was replaced:**

- The double-callable pattern encouraged class-based apps with mutable instance state, which was error-prone
- It was harder to compose middleware (middleware had to handle both call phases)
- The single-callable is simpler to understand, implement, and type-check
- No performance benefit — the "initialization" phase didn't save any work

### Migrating from 2.0 to 3.0

The `asgiref` library provides utilities to convert between versions:

```python
from asgiref.compatibility import double_to_single_callable, guarantee_single_callable

# Convert a 2.0 app to 3.0
legacy_app = LegacyApplication  # double-callable
modern_app = double_to_single_callable(legacy_app)

# Auto-detect and normalize to 3.0
# Works with both 2.0 and 3.0 apps
normalized = guarantee_single_callable(some_app)
```

**How `guarantee_single_callable` works:** It inspects the callable's signature. If calling it with `(scope, receive, send)` raises `TypeError`, it falls back to the double-callable pattern: `instance = app(scope)` then `await instance(receive, send)`.

```python
# Django uses this internally
import django
from django.core.asgi import get_asgi_application

# Returns a 3.0-compatible callable, even if internal
# components use older patterns
application = get_asgi_application()
```

### Spec Versions by Protocol

Each protocol has its own spec version that evolves independently:

#### HTTP Spec Versions

| Spec Version | Key Changes                                                   |
| ------------ | ------------------------------------------------------------- |
| `2.0`        | Initial HTTP spec for ASGI 3.0                                |
| `2.1`        | Added `headers` to `http.disconnect` event                    |
| `2.2`        | Added `http.response.pathsend` extension                      |
| `2.3`        | Added `http.response.zerocopysend` extension                  |
| `2.4`        | Added `http.response.trailers` extension for HTTP/2+ trailers |

#### WebSocket Spec Versions

| Spec Version | Key Changes                                                                |
| ------------ | -------------------------------------------------------------------------- |
| `2.0`        | Initial WebSocket spec for ASGI 3.0                                        |
| `2.1`        | Added `reason` field to `websocket.close`                                  |
| `2.3`        | Added `websocket.http.response` extension for rejection with HTTP response |
| `2.4`        | Added `headers` to `websocket.accept`                                      |

#### Lifespan Spec Versions

| Spec Version | Key Changes                                                             |
| ------------ | ----------------------------------------------------------------------- |
| `1.0`        | Initial lifespan spec (startup/shutdown events)                         |
| `2.0`        | Added `state` dict to lifespan scope for sharing state with connections |

### The `asgi` Scope Field

Every ASGI scope includes an `asgi` dict that identifies the versions in use:

```python
scope["asgi"] = {
    "version": "3.0",          # ASGI callable version (always "3.0" for modern apps)
    "spec_version": "2.4",     # Protocol spec version (varies by protocol)
}
```

| Field          | Type  | Description                                                                                      |
| -------------- | ----- | ------------------------------------------------------------------------------------------------ |
| `version`      | `str` | ASGI version — `"3.0"` for single-callable, `"2.0"` for double-callable                          |
| `spec_version` | `str` | Protocol-specific spec version (optional, defaults to `"2.0"` for HTTP/WS, `"1.0"` for lifespan) |

Use `spec_version` to check feature availability:

```python
async def app(scope: Scope, receive: Receive, send: Send) -> None:
    asgi = scope.get("asgi", {})
    spec = asgi.get("spec_version", "2.0")

    if scope["type"] == "http":
        # Trailers available in spec 2.4+
        major, minor = (int(x) for x in spec.split("."))
        supports_trailers = (major, minor) >= (2, 4)

    elif scope["type"] == "lifespan":
        # State sharing available in spec 2.0+
        major, minor = (int(x) for x in spec.split("."))
        supports_state = (major, minor) >= (2, 0)
```

**In practice**, most applications don't need to check spec versions — servers advertise capabilities via `scope["extensions"]`, which is the preferred way to detect optional features. Spec version checks are mainly useful for libraries and middleware that need to handle multiple server implementations.

## Security Considerations

### Header Injection

Headers in ASGI are raw bytes. Never pass unsanitized user input into header values:

```python
# DANGEROUS — user controls header value
await send({
    "type": "http.response.start",
    "status": 200,
    "headers": [
        (b"x-request-id", user_input.encode()),  # Could inject \r\n headers
    ],
})

# SAFE — validate or sanitize first
import re

def sanitize_header_value(value: str) -> str:
    return re.sub(r"[\r\n]", "", value)
```

### WebSocket Origin Validation

Always validate the `Origin` header for WebSocket connections to prevent cross-site WebSocket hijacking:

```python
ALLOWED_ORIGINS = {"https://example.com", "https://app.example.com"}

async def app(scope: Scope, receive: Receive, send: Send) -> None:
    if scope["type"] != "websocket":
        return

    headers = dict(scope.get("headers", []))
    origin = headers.get(b"origin", b"").decode()

    event = await receive()
    assert event["type"] == "websocket.connect"

    if origin not in ALLOWED_ORIGINS:
        await send({"type": "websocket.close", "code": 4003, "reason": "Forbidden origin"})
        return

    await send({"type": "websocket.accept"})
    ...
```

### Content-Length Correctness

When sending non-streaming responses, include `Content-Length` to prevent response smuggling and client hangs:

```python
body = b"Hello, World!"
await send({
    "type": "http.response.start",
    "status": 200,
    "headers": [
        (b"content-type", b"text/plain"),
        (b"content-length", str(len(body)).encode()),
    ],
})
await send({"type": "http.response.body", "body": body})
```

### Request Size Limits

ASGI servers don't enforce body size limits by default. Protect against oversized payloads:

```python
MAX_BODY_SIZE = 1_048_576  # 1 MB

async def read_body_limited(receive: Receive, max_size: int = MAX_BODY_SIZE) -> bytes:
    body_parts: list[bytes] = []
    total = 0

    while True:
        event = await receive()
        chunk = event.get("body", b"")
        total += len(chunk)
        if total > max_size:
            raise ValueError(f"Request body exceeds {max_size} bytes")
        body_parts.append(chunk)
        if not event.get("more_body", False):
            break

    return b"".join(body_parts)
```

### Timing Attacks

When comparing secrets (tokens, API keys), use constant-time comparison:

```python
import hmac

def safe_compare(a: bytes, b: bytes) -> bool:
    return hmac.compare_digest(a, b)
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
- [ASGI Extensions](https://asgi.readthedocs.io/en/latest/extensions.html)
- [HTTP Connection Scope](https://asgi.readthedocs.io/en/latest/specs/www.html)
- [WebSocket Specification](https://asgi.readthedocs.io/en/latest/specs/www.html#websocket)
- [Lifespan Protocol](https://asgi.readthedocs.io/en/latest/specs/lifespan.html)
- [asgiref on GitHub](https://github.com/django/asgiref)
- [Uvicorn](https://www.uvicorn.org/)
- [Hypercorn](https://github.com/pgjones/hypercorn)
- [Granian](https://github.com/emmett-framework/granian)
- [Starlette](https://www.starlette.io/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [httpx ASGI Transport](https://www.python-httpx.org/async/#calling-into-python-web-apps)
- [asgi-lifespan](https://github.com/florimondmanca/asgi-lifespan)

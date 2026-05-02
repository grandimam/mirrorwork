# Building Middleware Stacks with ASGI

A comprehensive guide to writing, composing, and testing ASGI middleware from first principles. All examples use raw ASGI -- no frameworks.

## Table of Contents

1. [What Middleware Is](#what-middleware-is)
2. [The Fundamental Pattern](#the-fundamental-pattern)
3. [Three Interception Points](#three-interception-points)
4. [Scope Modification Middleware](#scope-modification-middleware)
5. [Request Interception Middleware](#request-interception-middleware)
6. [Response Interception Middleware](#response-interception-middleware)
7. [Short-Circuit Middleware](#short-circuit-middleware)
8. [Middleware Composition and Ordering](#middleware-composition-and-ordering)
9. [Practical Examples](#practical-examples)
10. [Middleware Factories and Configuration](#middleware-factories-and-configuration)
11. [Testing Middleware in Isolation](#testing-middleware-in-isolation)
12. [Common Pitfalls](#common-pitfalls)

---

## What Middleware Is

An ASGI application is an async callable with this signature:

```python
async def app(scope: dict, receive: Callable, send: Callable) -> None:
    ...
```

- **scope** -- a dict describing the connection (type, path, headers, query string, etc.).
- **receive** -- an async callable that returns the next inbound event (request body chunks, WebSocket messages).
- **send** -- an async callable that transmits an outbound event (response start, response body chunks).

**Middleware is an ASGI application that wraps another ASGI application.** It sits between the server and the inner app (or between two other middleware layers), intercepting `scope`, `receive`, and/or `send` to add behaviour without modifying the inner app. There is no special middleware interface or base class. If it accepts `(scope, receive, send)` and calls another callable with the same signature, it is middleware.

```
Server
  |
  v
Middleware A  (outermost)
  |
  v
Middleware B
  |
  v
Application   (innermost)
```

The server calls Middleware A. Middleware A (possibly after doing work) calls Middleware B. Middleware B calls the Application. Responses flow back in the reverse direction through the `send` wrappers each middleware installed.

## The Fundamental Pattern

Every ASGI middleware follows the same skeleton. The class form is the most common:

```python
from typing import Any, Callable

Scope = dict[str, Any]
Receive = Callable[[], Any]
Send = Callable[[dict[str, Any]], Any]
ASGIApp = Callable[..., Any]


class MiddlewareSkeleton:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # --- BEFORE the inner app ---
        # Modify scope, wrap receive, wrap send, or short-circuit.

        await self.app(scope, receive, send)

        # --- AFTER the inner app ---
        # The inner app has finished. For HTTP, the full response has been
        # sent by the time we reach this line. Useful for cleanup and logging,
        # but you cannot send additional HTTP events here.
```

The functional form works identically:

```python
def middleware_factory(app: ASGIApp) -> ASGIApp:
    async def middleware(scope: Scope, receive: Receive, send: Send) -> None:
        await app(scope, receive, send)
    return middleware
```

Both forms are valid ASGI apps. The class form is preferred when the middleware carries configuration or mutable state.

### Scope type guard

Almost every middleware should pass through non-HTTP scopes unchanged. Lifespan and WebSocket scopes have different event semantics, and naively wrapping them will break things.

```python
async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
    if scope["type"] != "http":
        await self.app(scope, receive, send)
        return

    # HTTP-specific logic here
    ...
```

If your middleware genuinely needs to handle WebSocket or lifespan events, gate on `scope["type"]` explicitly and handle each protocol's event contract.

---

## Three Interception Points

A middleware can intervene at three distinct moments:

### 1. Before the app -- modify scope and/or receive

This is where you alter what the inner app sees: rewrite paths, inject state into scope, replace or wrap the `receive` callable to transform inbound events.

```python
async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
    # Mutate scope (always copy first)
    scope = dict(scope)
    scope["custom_key"] = "custom_value"

    # Optionally wrap receive
    async def new_receive() -> dict:
        event = await receive()
        # transform event
        return event

    await self.app(scope, new_receive, send)
```

### 2. During the app -- wrap send

The inner app calls `send` to emit response events. By replacing `send` with a wrapper, you can inspect or modify response headers, status codes, and body chunks as they flow out.

```python
async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
    async def new_send(event: dict) -> None:
        if event["type"] == "http.response.start":
            # inspect or modify headers/status
            pass
        await send(event)

    await self.app(scope, receive, new_send)
```

### 3. After the app -- post-processing

Code after `await self.app(...)` runs once the inner app has fully completed. At this point the response has already been sent to the client. This is the place for timing, logging, and cleanup -- not for modifying the response.

```python
async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
    start = time.monotonic()
    await self.app(scope, receive, send)
    elapsed = time.monotonic() - start
    logger.info("Request took %.3fs", elapsed)
```

---

## Scope Modification Middleware

Scope is a plain dict. The ASGI spec says scope is **created by the server and should not be mutated** -- but in practice, middleware routinely creates a shallow copy and modifies it. The rule: **copy before mutating** so you do not affect sibling middleware or the server's internal state.

### State injection

Inject shared state (database pools, config, feature flags) so every downstream layer can access it.

```python
class StateInjectionMiddleware:
    """Inject application state into scope so handlers can access it."""

    def __init__(self, app: ASGIApp, state: dict[str, Any]) -> None:
        self.app = app
        self.state = state

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        scope = dict(scope)
        scope.setdefault("state", {})
        scope["state"].update(self.state)
        await self.app(scope, receive, send)
```

Usage:

```python
state = {"db": db_pool, "cache": redis_client}
app = StateInjectionMiddleware(inner_app, state=state)
```

The handler reads `scope["state"]["db"]` without needing global variables.

### Path rewriting

Strip a prefix so a sub-application sees root-relative paths.

```python
class PathStripMiddleware:
    """Strip a prefix from the request path."""

    def __init__(self, app: ASGIApp, prefix: str) -> None:
        self.app = app
        self.prefix = prefix.rstrip("/")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"].startswith(self.prefix):
            scope = dict(scope)
            scope["path"] = scope["path"][len(self.prefix):] or "/"
            scope["root_path"] = scope.get("root_path", "") + self.prefix
        await self.app(scope, receive, send)
```

### Injecting custom scope keys

Any key that does not collide with the ASGI spec is fair game. A common pattern is to attach a unique request ID early in the stack so every downstream layer can reference it.

```python
import uuid


class RequestIDMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        scope = dict(scope)
        # Honour an incoming header if present; otherwise generate one.
        headers = dict(scope.get("headers", []))
        request_id = headers.get(b"x-request-id", b"").decode() or str(uuid.uuid4())
        scope["request_id"] = request_id

        async def send_with_id(event: dict) -> None:
            if event["type"] == "http.response.start":
                event = dict(event)
                event["headers"] = list(event.get("headers", [])) + [
                    (b"x-request-id", request_id.encode()),
                ]
            await send(event)

        await self.app(scope, receive, send_with_id)
```

---

## Request Interception Middleware

Wrapping `receive` lets middleware observe or transform inbound events before the inner app sees them.

### Body buffering

Buffer the entire request body so multiple downstream consumers can read it. Without this, calling `receive()` twice yields an empty second read because the body stream is consumed.

```python
class BodyBufferMiddleware:
    """Buffer the full request body and replay it on every receive() call."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Consume the entire body.
        body_parts: list[bytes] = []
        while True:
            event = await receive()
            body_parts.append(event.get("body", b""))
            if event["type"] == "http.request" and not event.get("more_body", False):
                break

        full_body = b"".join(body_parts)
        sent = False

        async def replay_receive() -> dict:
            nonlocal sent
            if not sent:
                sent = True
                return {
                    "type": "http.request",
                    "body": full_body,
                    "more_body": False,
                }
            # After the body has been delivered, any subsequent receive()
            # should block until disconnect. We wait on the original receive
            # to detect client disconnect.
            return await receive()

        await self.app(scope, replay_receive, send)
```

### Request body size limiting

Reject payloads that exceed a threshold without letting the full body into memory.

```python
class MaxBodySizeMiddleware:
    def __init__(self, app: ASGIApp, max_bytes: int = 1_048_576) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        total = 0

        async def limited_receive() -> dict:
            nonlocal total
            event = await receive()
            if event["type"] == "http.request":
                total += len(event.get("body", b""))
                if total > self.max_bytes:
                    raise BodyTooLargeError(self.max_bytes)
            return event

        try:
            await self.app(scope, limited_receive, send)
        except BodyTooLargeError as exc:
            await send({
                "type": "http.response.start",
                "status": 413,
                "headers": [(b"content-type", b"text/plain")],
            })
            await send({
                "type": "http.response.body",
                "body": f"Request body exceeds {exc.limit} bytes".encode(),
            })


class BodyTooLargeError(Exception):
    def __init__(self, limit: int) -> None:
        self.limit = limit
        super().__init__(f"Body exceeds {limit} bytes")
```

### Logging incoming body

Observe the body without altering it. The wrapper calls the original `receive`, logs, and returns the event unchanged.

```python
import logging

logger = logging.getLogger("asgi.body")


class BodyLoggingMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        chunks: list[bytes] = []

        async def logging_receive() -> dict:
            event = await receive()
            if event["type"] == "http.request":
                chunks.append(event.get("body", b""))
                if not event.get("more_body", False):
                    logger.debug(
                        "%s %s body=%d bytes",
                        scope.get("method"),
                        scope.get("path"),
                        sum(len(c) for c in chunks),
                    )
            return event

        await self.app(scope, logging_receive, send)
```

---

## Response Interception Middleware

Wrapping `send` lets you inspect and transform outbound events. The HTTP response is a two-event sequence:

1. `http.response.start` -- contains `status` (int) and `headers` (list of 2-tuples of bytes).
2. `http.response.body` -- contains `body` (bytes) and optionally `more_body` (bool).

For streamed responses, multiple `http.response.body` events are sent with `more_body=True` until the final chunk.

### Modifying response headers

```python
class ServerHeaderMiddleware:
    """Add a Server header to every HTTP response."""

    def __init__(self, app: ASGIApp, server_name: str = "barq") -> None:
        self.app = app
        self.server_name = server_name

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def add_server_header(event: dict) -> None:
            if event["type"] == "http.response.start":
                event = dict(event)
                event["headers"] = list(event.get("headers", [])) + [
                    (b"server", self.server_name.encode()),
                ]
            await send(event)

        await self.app(scope, receive, add_server_header)
```

### Capturing response status

```python
class StatusCaptureMiddleware:
    """Capture the response status code for post-request logging."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        status_code = 0

        async def capture_send(event: dict) -> None:
            nonlocal status_code
            if event["type"] == "http.response.start":
                status_code = event["status"]
            await send(event)

        await self.app(scope, receive, capture_send)
        logger.info("%s %s -> %d", scope["method"], scope["path"], status_code)
```

### Rewriting the response body (non-streaming)

When you need to transform the entire response body -- for example, to minify HTML or inject analytics tags -- you must buffer all body chunks, transform them, and send the result. This breaks streaming intentionally.

```python
class BodyRewriteMiddleware:
    """Buffer the full response body, apply a transform, then send."""

    def __init__(self, app: ASGIApp, transform: Callable[[bytes], bytes]) -> None:
        self.app = app
        self.transform = transform

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        response_start: dict | None = None
        body_parts: list[bytes] = []

        async def buffer_send(event: dict) -> None:
            nonlocal response_start
            if event["type"] == "http.response.start":
                response_start = event
            elif event["type"] == "http.response.body":
                body_parts.append(event.get("body", b""))
                if not event.get("more_body", False):
                    # All chunks received. Transform and send.
                    full_body = self.transform(b"".join(body_parts))
                    # Update content-length.
                    headers = [
                        (k, v) for k, v in response_start.get("headers", [])
                        if k.lower() != b"content-length"
                    ]
                    headers.append(
                        (b"content-length", str(len(full_body)).encode())
                    )
                    response_start["headers"] = headers
                    await send(response_start)
                    await send({
                        "type": "http.response.body",
                        "body": full_body,
                    })

        await self.app(scope, receive, buffer_send)
```

---

## Short-Circuit Middleware

Sometimes middleware should respond directly, bypassing the inner app entirely. Authentication rejection, cached responses, IP blocking, and rate limiting all follow this pattern.

The key mechanic: call `send` with a complete response (`http.response.start` followed by `http.response.body`) and `return` without ever calling `self.app`.

### Authentication gate

```python
class AuthGateMiddleware:
    """Reject unauthenticated requests before they reach the app."""

    def __init__(
        self,
        app: ASGIApp,
        verify: Callable[[str], dict | None],
        exempt_paths: set[str] | None = None,
    ) -> None:
        self.app = app
        self.verify = verify
        self.exempt_paths = exempt_paths or set()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if scope["path"] in self.exempt_paths:
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        token = headers.get(b"authorization", b"").decode()

        if not token.startswith("Bearer "):
            await self._reject(send, 401, b'{"error":"missing token"}')
            return

        user = self.verify(token[7:])
        if user is None:
            await self._reject(send, 403, b'{"error":"invalid token"}')
            return

        scope = dict(scope)
        scope["user"] = user
        await self.app(scope, receive, send)

    @staticmethod
    async def _reject(send: Send, status: int, body: bytes) -> None:
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        })
        await send({
            "type": "http.response.body",
            "body": body,
        })
```

### Cache middleware

Return a cached response without invoking the inner app.

```python
import time


class SimpleCacheMiddleware:
    """In-memory cache for GET requests keyed by path + query string."""

    def __init__(self, app: ASGIApp, ttl: float = 60.0) -> None:
        self.app = app
        self.ttl = ttl
        self._cache: dict[str, tuple[float, int, list, bytes]] = {}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] != "GET":
            await self.app(scope, receive, send)
            return

        cache_key = scope["path"] + "?" + scope.get("query_string", b"").decode()
        now = time.monotonic()

        # Cache hit.
        cached = self._cache.get(cache_key)
        if cached is not None:
            ts, status, headers, body = cached
            if now - ts < self.ttl:
                await send({
                    "type": "http.response.start",
                    "status": status,
                    "headers": headers,
                })
                await send({
                    "type": "http.response.body",
                    "body": body,
                })
                return

        # Cache miss -- call the inner app and capture the response.
        response_start: dict | None = None
        body_parts: list[bytes] = []

        async def caching_send(event: dict) -> None:
            nonlocal response_start
            if event["type"] == "http.response.start":
                response_start = event
            elif event["type"] == "http.response.body":
                body_parts.append(event.get("body", b""))
            await send(event)

        await self.app(scope, receive, caching_send)

        if response_start is not None and response_start.get("status", 500) < 400:
            self._cache[cache_key] = (
                now,
                response_start["status"],
                list(response_start.get("headers", [])),
                b"".join(body_parts),
            )
```

### IP allowlist / blocklist

```python
import ipaddress


class IPFilterMiddleware:
    """Block or allow requests based on client IP."""

    def __init__(
        self,
        app: ASGIApp,
        allow: list[str] | None = None,
        deny: list[str] | None = None,
    ) -> None:
        self.app = app
        self.allow = [ipaddress.ip_network(n) for n in (allow or [])]
        self.deny = [ipaddress.ip_network(n) for n in (deny or [])]

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        client = scope.get("client")
        if client is None:
            await self.app(scope, receive, send)
            return

        addr = ipaddress.ip_address(client[0])

        # If an allowlist is configured, reject anything not in it.
        if self.allow and not any(addr in net for net in self.allow):
            await self._forbidden(send)
            return

        # If a denylist is configured, reject anything in it.
        if self.deny and any(addr in net for net in self.deny):
            await self._forbidden(send)
            return

        await self.app(scope, receive, send)

    @staticmethod
    async def _forbidden(send: Send) -> None:
        await send({
            "type": "http.response.start",
            "status": 403,
            "headers": [(b"content-type", b"text/plain")],
        })
        await send({
            "type": "http.response.body",
            "body": b"Forbidden",
        })
```

---

## Middleware Composition and Ordering

Middleware is composed by nesting. The outermost middleware runs first on the request and last on the response.

```python
app = Application()
app = ErrorHandlerMiddleware(app)
app = AuthGateMiddleware(app, verify=verify_jwt)
app = CORSMiddleware(app, origins=["https://example.com"])
app = RequestIDMiddleware(app)
app = AccessLogMiddleware(app)
```

Execution order for a request:

```
                     REQUEST FLOW
AccessLogMiddleware     (1) enter, start timer
  RequestIDMiddleware   (2) enter, inject ID into scope
    CORSMiddleware      (3) enter, check origin
      AuthGateMiddleware(4) enter, verify token
        ErrorHandler    (5) enter, install try/except
          Application   (6) handle request, call send()

                     RESPONSE FLOW  (via send wrappers)
          Application   (6) send() called
        ErrorHandler    (5) guarded_send wrapper
      AuthGateMiddleware(4) pass-through
    CORSMiddleware      (3) cors_send adds CORS headers
  RequestIDMiddleware   (2) send_with_id adds X-Request-ID
AccessLogMiddleware     (1) logging_send captures status; after app, logs elapsed time
```

### Helper function for composing middleware

```python
from typing import Sequence


def build_middleware_stack(
    app: ASGIApp,
    middleware: Sequence[tuple[type, dict[str, Any]]],
) -> ASGIApp:
    """Apply middleware bottom-up. The first item in the list is outermost."""
    for cls, kwargs in reversed(middleware):
        app = cls(app, **kwargs)
    return app


# Usage
app = build_middleware_stack(inner_app, [
    (AccessLogMiddleware, {}),
    (RequestIDMiddleware, {}),
    (CORSMiddleware, {"origins": ["*"]}),
    (AuthGateMiddleware, {"verify": verify_jwt}),
    (ErrorHandlerMiddleware, {"debug": True}),
])
```

### Ordering principles

| Concern              | Position              | Reason                                                      |
| -------------------- | --------------------- | ----------------------------------------------------------- |
| Timing / access logs | Outermost             | Capture total wall time including all middleware            |
| Request ID           | Near outer            | So every log line downstream includes the ID                |
| CORS                 | Before auth           | Preflight OPTIONS must succeed without auth                 |
| Authentication       | Before business logic | Reject early, before any processing                         |
| Error handling       | Innermost wrapper     | Catch exceptions from the application                       |
| Compression          | Near outer            | Compress the final response bytes after all transformations |

---

## Practical Examples

### CORS middleware (full implementation)

Handles preflight requests, simple requests, and credentialed requests.

```python
class CORSMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        origins: list[str],
        methods: list[str] | None = None,
        headers: list[str] | None = None,
        expose_headers: list[str] | None = None,
        allow_credentials: bool = False,
        max_age: int = 86400,
    ) -> None:
        self.app = app
        self.origins = set(origins)
        self.allow_all_origins = "*" in self.origins
        self.methods = methods or ["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"]
        self.allowed_headers = headers or ["content-type", "authorization"]
        self.expose_headers = expose_headers or []
        self.allow_credentials = allow_credentials
        self.max_age = max_age

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_headers = dict(scope.get("headers", []))
        origin = request_headers.get(b"origin", b"").decode()

        if not origin:
            await self.app(scope, receive, send)
            return

        if not self._is_origin_allowed(origin):
            await self.app(scope, receive, send)
            return

        # Preflight
        if scope["method"] == "OPTIONS":
            await self._preflight_response(send, origin)
            return

        # Actual request -- attach CORS headers to the response.
        cors_headers = self._build_cors_headers(origin)

        async def cors_send(event: dict) -> None:
            if event["type"] == "http.response.start":
                event = dict(event)
                event["headers"] = list(event.get("headers", [])) + cors_headers
            await send(event)

        await self.app(scope, receive, cors_send)

    def _is_origin_allowed(self, origin: str) -> bool:
        if self.allow_all_origins:
            return True
        return origin in self.origins

    def _build_cors_headers(self, origin: str) -> list[tuple[bytes, bytes]]:
        h: list[tuple[bytes, bytes]] = []
        if self.allow_all_origins and not self.allow_credentials:
            h.append((b"access-control-allow-origin", b"*"))
        else:
            h.append((b"access-control-allow-origin", origin.encode()))
            h.append((b"vary", b"Origin"))
        if self.allow_credentials:
            h.append((b"access-control-allow-credentials", b"true"))
        if self.expose_headers:
            h.append((
                b"access-control-expose-headers",
                ", ".join(self.expose_headers).encode(),
            ))
        return h

    async def _preflight_response(self, send: Send, origin: str) -> None:
        headers = self._build_cors_headers(origin) + [
            (b"access-control-allow-methods", ", ".join(self.methods).encode()),
            (b"access-control-allow-headers", ", ".join(self.allowed_headers).encode()),
            (b"access-control-max-age", str(self.max_age).encode()),
            (b"content-length", b"0"),
        ]
        await send({
            "type": "http.response.start",
            "status": 204,
            "headers": headers,
        })
        await send({"type": "http.response.body", "body": b""})
```

### Logging and timing middleware

```python
import time
import logging

logger = logging.getLogger("asgi.access")


class AccessLogMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.perf_counter()
        status = 0
        response_size = 0

        async def logging_send(event: dict) -> None:
            nonlocal status, response_size
            if event["type"] == "http.response.start":
                status = event["status"]
            elif event["type"] == "http.response.body":
                response_size += len(event.get("body", b""))
            await send(event)

        try:
            await self.app(scope, receive, logging_send)
        finally:
            elapsed = time.perf_counter() - start
            client = scope.get("client", ("unknown", 0))
            logger.info(
                '%s:%s - "%s %s" %d %d %.3fs',
                client[0],
                client[1],
                scope.get("method", "?"),
                scope.get("path", "/"),
                status,
                response_size,
                elapsed,
            )
```

### Authentication middleware

See the [AuthGateMiddleware](#authentication-gate) in the Short-Circuit section above for the full implementation. The pattern:

1. Extract the `Authorization` header from scope.
2. Validate the token using the configured `verify` callable.
3. On failure, short-circuit with 401 or 403.
4. On success, inject the user into a copied scope and forward to the inner app.

### Compression middleware (gzip)

Compress response bodies when the client advertises `Accept-Encoding: gzip`. This implementation buffers the full body, so it is incompatible with streaming responses.

```python
import gzip as gzip_mod


class GzipMiddleware:
    def __init__(self, app: ASGIApp, minimum_size: int = 500) -> None:
        self.app = app
        self.minimum_size = minimum_size

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_headers = dict(scope.get("headers", []))
        accept_encoding = request_headers.get(b"accept-encoding", b"").decode()

        if "gzip" not in accept_encoding:
            await self.app(scope, receive, send)
            return

        # Buffer the response so we can compress it.
        response_start: dict | None = None
        body_parts: list[bytes] = []

        async def buffer_send(event: dict) -> None:
            nonlocal response_start
            if event["type"] == "http.response.start":
                response_start = event
            elif event["type"] == "http.response.body":
                body_parts.append(event.get("body", b""))
                if not event.get("more_body", False):
                    # Final chunk -- compress and send.
                    full_body = b"".join(body_parts)
                    if len(full_body) < self.minimum_size:
                        # Too small to bother compressing.
                        await send(response_start)
                        await send(event)
                        return

                    compressed = gzip_mod.compress(full_body)

                    # Rewrite headers.
                    headers = [
                        (k, v)
                        for k, v in response_start.get("headers", [])
                        if k.lower() not in (b"content-length", b"content-encoding")
                    ]
                    headers.append((b"content-encoding", b"gzip"))
                    headers.append((b"content-length", str(len(compressed)).encode()))
                    response_start = dict(response_start)
                    response_start["headers"] = headers

                    await send(response_start)
                    await send({
                        "type": "http.response.body",
                        "body": compressed,
                    })

        await self.app(scope, receive, buffer_send)
```

### Error handling middleware

Catch exceptions from the inner app and return a structured error response. Must track whether the response has already started -- once `http.response.start` has been sent, a new response cannot be initiated.

```python
import traceback
import json


class ErrorHandlerMiddleware:
    def __init__(self, app: ASGIApp, debug: bool = False) -> None:
        self.app = app
        self.debug = debug

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        response_started = False

        async def guarded_send(event: dict) -> None:
            nonlocal response_started
            if event["type"] == "http.response.start":
                response_started = True
            await send(event)

        try:
            await self.app(scope, receive, guarded_send)
        except Exception as exc:
            if response_started:
                raise

            if self.debug:
                body = json.dumps({
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                }).encode()
            else:
                body = json.dumps({
                    "error": "Internal Server Error",
                }).encode()

            await send({
                "type": "http.response.start",
                "status": 500,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            })
            await send({
                "type": "http.response.body",
                "body": body,
            })
```

### Request ID injection

See the [RequestIDMiddleware](#injecting-custom-scope-keys) in the Scope Modification section. It demonstrates both scope injection (setting `scope["request_id"]`) and send wrapping (adding the `X-Request-ID` response header).

### IP allowlist / blocklist

See the [IPFilterMiddleware](#ip-allowlist--blocklist) in the Short-Circuit section.

---

## Middleware Factories and Configuration

When middleware needs runtime configuration, use a factory that returns a configured middleware class or closure.

### Class-based factory with dataclass config

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class RateLimitConfig:
    requests_per_second: float = 10.0
    burst: int = 20
    key_func: Callable[[Scope], str] = lambda scope: scope.get("client", ("anon",))[0]
    status_code: int = 429
    retry_after: int = 60


class RateLimitMiddleware:
    def __init__(self, app: ASGIApp, config: RateLimitConfig | None = None) -> None:
        self.app = app
        self.config = config or RateLimitConfig()
        self._buckets: dict[str, list[float]] = {}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        key = self.config.key_func(scope)
        now = time.monotonic()

        # Sliding window.
        window = self._buckets.setdefault(key, [])
        cutoff = now - 1.0
        self._buckets[key] = window = [t for t in window if t > cutoff]

        if len(window) >= self.config.requests_per_second:
            await send({
                "type": "http.response.start",
                "status": self.config.status_code,
                "headers": [
                    (b"content-type", b"text/plain"),
                    (b"retry-after", str(self.config.retry_after).encode()),
                ],
            })
            await send({
                "type": "http.response.body",
                "body": b"Rate limit exceeded",
            })
            return

        window.append(now)
        await self.app(scope, receive, send)
```

### Functional factory

```python
def make_header_middleware(
    headers: dict[str, str],
) -> Callable[[ASGIApp], ASGIApp]:
    """Factory that creates a middleware adding fixed response headers."""
    encoded_headers = [
        (k.lower().encode(), v.encode()) for k, v in headers.items()
    ]

    def wrapper(app: ASGIApp) -> ASGIApp:
        async def middleware(scope: Scope, receive: Receive, send: Send) -> None:
            if scope["type"] != "http":
                await app(scope, receive, send)
                return

            async def augmented_send(event: dict) -> None:
                if event["type"] == "http.response.start":
                    event = dict(event)
                    event["headers"] = list(event.get("headers", [])) + encoded_headers
                await send(event)

            await app(scope, receive, augmented_send)

        return middleware

    return wrapper


# Usage
add_security_headers = make_header_middleware({
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
})

app = add_security_headers(inner_app)
```

### Conditional middleware

Apply middleware only when a predicate is true.

```python
class ConditionalMiddleware:
    """Wrap an inner middleware and only activate it when predicate(scope) is True."""

    def __init__(
        self,
        app: ASGIApp,
        middleware_cls: type,
        predicate: Callable[[Scope], bool],
        **middleware_kwargs: Any,
    ) -> None:
        self.app = app
        self.wrapped = middleware_cls(app, **middleware_kwargs)
        self.predicate = predicate

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if self.predicate(scope):
            await self.wrapped(scope, receive, send)
        else:
            await self.app(scope, receive, send)
```

---

## Testing Middleware in Isolation

Middleware can be tested without a real ASGI server by constructing minimal scope dicts and mock `receive`/`send` callables.

### Test harness

```python
from typing import Any


class MockSend:
    """Collect events sent by the application."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    async def __call__(self, event: dict[str, Any]) -> None:
        self.events.append(event)

    @property
    def status(self) -> int:
        for e in self.events:
            if e["type"] == "http.response.start":
                return e["status"]
        raise AssertionError("No response.start event found")

    @property
    def headers(self) -> dict[bytes, bytes]:
        for e in self.events:
            if e["type"] == "http.response.start":
                return dict(e.get("headers", []))
        return {}

    @property
    def body(self) -> bytes:
        parts = []
        for e in self.events:
            if e["type"] == "http.response.body":
                parts.append(e.get("body", b""))
        return b"".join(parts)


def mock_receive(body: bytes = b"") -> Receive:
    """Return a receive callable that yields the given body then blocks."""
    called = False

    async def receive() -> dict:
        nonlocal called
        if not called:
            called = True
            return {"type": "http.request", "body": body, "more_body": False}
        # Simulate waiting for disconnect.
        import asyncio
        await asyncio.sleep(3600)
        return {"type": "http.disconnect"}

    return receive


def make_scope(
    method: str = "GET",
    path: str = "/",
    headers: list[tuple[bytes, bytes]] | None = None,
    query_string: bytes = b"",
) -> Scope:
    return {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "path": path,
        "root_path": "",
        "query_string": query_string,
        "headers": headers or [],
        "client": ("127.0.0.1", 8000),
    }
```

### Example tests

```python
import asyncio


async def test_request_id_middleware():
    """RequestIDMiddleware injects X-Request-ID into scope and response."""

    captured_scope: dict | None = None

    async def inner_app(scope, receive, send):
        nonlocal captured_scope
        captured_scope = scope
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"text/plain")],
        })
        await send({
            "type": "http.response.body",
            "body": b"ok",
        })

    app = RequestIDMiddleware(inner_app)
    send = MockSend()

    await app(make_scope(), mock_receive(), send)

    # The response should have X-Request-ID.
    assert b"x-request-id" in send.headers
    # The scope passed to the inner app should have request_id.
    assert "request_id" in captured_scope
    # They should match.
    assert captured_scope["request_id"].encode() == send.headers[b"x-request-id"]


async def test_auth_gate_rejects_missing_token():
    """AuthGateMiddleware returns 401 when no token is present."""

    async def inner_app(scope, receive, send):
        raise AssertionError("Inner app should not be called")

    app = AuthGateMiddleware(
        inner_app,
        verify=lambda t: {"sub": "user1"},
    )
    send = MockSend()

    await app(make_scope(), mock_receive(), send)

    assert send.status == 401


async def test_auth_gate_passes_valid_token():
    """AuthGateMiddleware forwards to the inner app with user in scope."""

    captured_scope = None

    async def inner_app(scope, receive, send):
        nonlocal captured_scope
        captured_scope = scope
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    app = AuthGateMiddleware(
        inner_app,
        verify=lambda t: {"sub": "user1"} if t == "valid" else None,
    )
    send = MockSend()

    scope = make_scope(headers=[(b"authorization", b"Bearer valid")])
    await app(scope, mock_receive(), send)

    assert send.status == 200
    assert captured_scope["user"] == {"sub": "user1"}


async def test_gzip_compresses_large_body():
    """GzipMiddleware compresses responses above minimum_size."""

    body = b"x" * 1000

    async def inner_app(scope, receive, send):
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"text/plain")],
        })
        await send({
            "type": "http.response.body",
            "body": body,
        })

    app = GzipMiddleware(inner_app, minimum_size=500)
    send = MockSend()

    scope = make_scope(headers=[(b"accept-encoding", b"gzip, deflate")])
    await app(scope, mock_receive(), send)

    assert send.headers.get(b"content-encoding") == b"gzip"
    assert len(send.body) < len(body)
    assert gzip_mod.decompress(send.body) == body


async def test_ip_filter_blocks_denied():
    """IPFilterMiddleware returns 403 for denied IPs."""

    async def inner_app(scope, receive, send):
        raise AssertionError("Should not be called")

    app = IPFilterMiddleware(inner_app, deny=["127.0.0.0/8"])
    send = MockSend()

    await app(make_scope(), mock_receive(), send)

    assert send.status == 403


async def test_cors_preflight():
    """CORSMiddleware handles preflight OPTIONS without calling inner app."""

    async def inner_app(scope, receive, send):
        raise AssertionError("Preflight should not reach the app")

    app = CORSMiddleware(inner_app, origins=["https://example.com"])
    send = MockSend()

    scope = make_scope(
        method="OPTIONS",
        headers=[(b"origin", b"https://example.com")],
    )
    await app(scope, mock_receive(), send)

    assert send.status == 204
    assert send.headers[b"access-control-allow-origin"] == b"https://example.com"
```

### Running the tests

These are plain async functions. Run them directly:

```python
if __name__ == "__main__":
    asyncio.run(test_request_id_middleware())
    asyncio.run(test_auth_gate_rejects_missing_token())
    asyncio.run(test_auth_gate_passes_valid_token())
    asyncio.run(test_gzip_compresses_large_body())
    asyncio.run(test_ip_filter_blocks_denied())
    asyncio.run(test_cors_preflight())
    print("All tests passed.")
```

Or with pytest and `pytest-asyncio`:

```python
import pytest


@pytest.mark.asyncio
async def test_error_handler_catches_exception():
    async def broken_app(scope, receive, send):
        raise ValueError("something broke")

    app = ErrorHandlerMiddleware(broken_app, debug=False)
    send = MockSend()

    await app(make_scope(), mock_receive(), send)

    assert send.status == 500
    assert b"Internal Server Error" in send.body


@pytest.mark.asyncio
async def test_error_handler_reraises_after_response_started():
    async def partially_broken_app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        raise RuntimeError("crash mid-stream")

    app = ErrorHandlerMiddleware(partially_broken_app)
    send = MockSend()

    with pytest.raises(RuntimeError, match="crash mid-stream"):
        await app(make_scope(), mock_receive(), send)
```

---

## Common Pitfalls

### 1. Consuming receive() twice

`receive()` is a stream, not a replayable source. Once a body chunk is consumed, it is gone. If two middleware layers both call `receive()` to read the body, the second one gets nothing.

```python
# BROKEN: Two middleware layers both try to read the body.
class MiddlewareA:
    async def __call__(self, scope, receive, send):
        event = await receive()  # Consumes the body.
        await self.app(scope, receive, send)

class MiddlewareB:
    async def __call__(self, scope, receive, send):
        event = await receive()  # Gets an empty event or blocks forever.
        ...
```

**Fix:** Use a `BodyBufferMiddleware` early in the stack that consumes the body once and provides a replay-capable `receive` wrapper downstream.

### 2. Breaking streaming responses

Middleware that buffers `http.response.body` events to inspect or transform the full body will prevent the client from receiving data incrementally. This breaks Server-Sent Events, chunked downloads, and any long-running streamed response.

```python
# This middleware breaks streaming because it holds all body events
# until the final chunk arrives.
async def buffer_send(event):
    if event["type"] == "http.response.body":
        parts.append(event.get("body", b""))
        if not event.get("more_body", False):
            # Only now do we send everything.
            ...
```

**Fix:** If your middleware only needs to inspect headers or status, do not buffer body events -- pass them through immediately. If you must buffer, document that the middleware is incompatible with streaming, or detect streaming content types (e.g. `text/event-stream`) and bypass the buffering logic:

```python
async def smart_send(event: dict) -> None:
    nonlocal response_start, is_streaming
    if event["type"] == "http.response.start":
        response_start = event
        content_type = dict(event.get("headers", [])).get(b"content-type", b"")
        is_streaming = b"text/event-stream" in content_type
    if is_streaming:
        await send(event)  # Pass through without buffering.
    else:
        # Buffer logic here.
        ...
```

### 3. Mutating headers after http.response.start has been sent

Once `http.response.start` has been passed to `send`, the status and headers are committed to the wire. You cannot send a second `http.response.start` event.

```python
# BROKEN: Tries to add headers after the response has started.
async def bad_send(event):
    await send(event)
    if event["type"] == "http.response.start":
        # Too late -- the event has already been sent to the server.
        event["headers"].append((b"x-extra", b"value"))
```

**Fix:** Always modify the event **before** calling `await send(event)`.

### 4. Forgetting to copy scope or event dicts

Scope and event dicts may be shared references. Mutating them in place can cause subtle bugs in other middleware or the server.

```python
# BROKEN: Mutates the original scope dict.
async def __call__(self, scope, receive, send):
    scope["path"] = "/rewritten"  # Other middleware sees this too.
    await self.app(scope, receive, send)

# CORRECT: Shallow copy first.
async def __call__(self, scope, receive, send):
    scope = dict(scope)
    scope["path"] = "/rewritten"
    await self.app(scope, receive, send)
```

The same applies to event dicts in `send` wrappers:

```python
# CORRECT
async def send_wrapper(event):
    if event["type"] == "http.response.start":
        event = dict(event)
        event["headers"] = list(event.get("headers", [])) + extra_headers
    await send(event)
```

### 5. Not handling non-HTTP scope types

Lifespan and WebSocket scopes have completely different event vocabularies. A middleware that blindly wraps `send` assuming HTTP events will break WebSocket or lifespan handling.

```python
# BROKEN: Assumes all scopes are HTTP.
async def __call__(self, scope, receive, send):
    async def send_wrapper(event):
        if event["type"] == "http.response.start":
            ...  # Never matches for WebSocket/lifespan.
        await send(event)
    await self.app(scope, receive, send_wrapper)
```

This particular example is harmless (the `if` just never triggers), but middleware that buffers events, reorders them, or makes assumptions about event sequencing will corrupt non-HTTP protocols.

**Fix:** Always check `scope["type"]` and pass through unhandled scope types without wrapping.

### 6. Raising exceptions after response has started

If middleware catches an exception and tries to send an error response, but the inner app has already sent `http.response.start`, the second `http.response.start` violates the ASGI protocol. Most servers will raise or terminate the connection.

```python
# BROKEN
try:
    await self.app(scope, receive, send)
except Exception:
    await send({"type": "http.response.start", "status": 500, ...})  # Protocol violation
```

**Fix:** Track whether `http.response.start` has been sent. If it has, re-raise the exception and let the server close the connection.

```python
response_started = False

async def tracking_send(event):
    nonlocal response_started
    if event["type"] == "http.response.start":
        response_started = True
    await send(event)

try:
    await self.app(scope, receive, tracking_send)
except Exception:
    if response_started:
        raise  # Cannot send a new response.
    await send({"type": "http.response.start", "status": 500, "headers": []})
    await send({"type": "http.response.body", "body": b"Internal Server Error"})
```

### 7. Middleware ordering mistakes

Placing authentication before CORS means preflight `OPTIONS` requests get rejected with 401. Placing error handling outside compression means error responses are uncompressed (usually acceptable) but placing compression inside error handling means error pages bypass compression entirely.

**Fix:** Refer to the ordering table in [Middleware Composition and Ordering](#middleware-composition-and-ordering). Think about which middleware needs to see the request first and which needs to wrap the response last.

### 8. Blocking the event loop

ASGI middleware runs on an async event loop. Synchronous operations -- CPU-heavy compression, disk I/O, DNS lookups -- block all concurrent requests.

```python
# BROKEN: Synchronous gzip blocks the event loop.
compressed = gzip_mod.compress(huge_body)  # Blocks for seconds on large bodies.
```

**Fix:** Offload CPU-bound work to a thread pool.

```python
import asyncio

loop = asyncio.get_running_loop()
compressed = await loop.run_in_executor(None, gzip_mod.compress, huge_body)
```

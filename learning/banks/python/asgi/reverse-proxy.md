# Reverse Proxies and API Gateways with Raw ASGI

A reverse proxy sits between clients and backend services, forwarding requests and relaying responses. An API gateway is a reverse proxy with opinions -- it adds routing, authentication, rate limiting, and transformation on top of plain forwarding. ASGI gives you the primitive you need to build both: an async callable that receives bytes from a client and sends bytes back, with full control over every header and every chunk of the body.

## Table of Contents

1. [Why ASGI for Proxying](#why-asgi-for-proxying)
2. [Basic Proxying](#basic-proxying)
   - [The Simplest Proxy](#the-simplest-proxy)
   - [Streaming the Request Body](#streaming-the-request-body)
   - [Streaming the Response Back](#streaming-the-response-back)
   - [Full Streaming Proxy](#full-streaming-proxy)
3. [Path-Based Routing](#path-based-routing)
   - [Static Route Table](#static-route-table)
   - [Prefix Matching with Path Rewriting](#prefix-matching-with-path-rewriting)
4. [Header Manipulation](#header-manipulation)
   - [Adding Forwarded Headers](#adding-forwarded-headers)
   - [Stripping Internal Headers](#stripping-internal-headers)
   - [Hop-by-Hop Header Filtering](#hop-by-hop-header-filtering)
5. [Load Balancing](#load-balancing)
   - [Round-Robin](#round-robin)
   - [Least Connections](#least-connections)
   - [Weighted Round-Robin](#weighted-round-robin)
6. [Rate Limiting](#rate-limiting)
   - [Token Bucket per Client IP](#token-bucket-per-client-ip)
   - [Sliding Window Counter](#sliding-window-counter)
   - [Rate Limiter as Middleware](#rate-limiter-as-middleware)
7. [Request and Response Transformation](#request-and-response-transformation)
   - [Aggregating Multiple Upstreams](#aggregating-multiple-upstreams)
   - [Response Body Rewriting](#response-body-rewriting)
8. [Health Checks and Circuit Breakers](#health-checks-and-circuit-breakers)
   - [Active Health Checking](#active-health-checking)
   - [Circuit Breaker Pattern](#circuit-breaker-pattern)
   - [Integrating the Circuit Breaker with the Proxy](#integrating-the-circuit-breaker-with-the-proxy)
9. [Authentication at the Gateway](#authentication-at-the-gateway)
   - [JWT Validation Before Forwarding](#jwt-validation-before-forwarding)
   - [Auth Middleware Wrapping the Proxy](#auth-middleware-wrapping-the-proxy)
10. [Putting It All Together](#putting-it-all-together)

---

## Why ASGI for Proxying

ASGI applications have the signature:

```python
async def app(scope, receive, send):
    ...
```

- `scope` is a dict containing connection metadata (method, path, headers, client address).
- `receive` is an async callable that yields incoming events (request body chunks, disconnects).
- `send` is an async callable that pushes outgoing events (response start, body chunks).

This design maps directly to what a proxy does. A proxy reads from the client (`receive`), forwards to an upstream, reads from the upstream, and writes back to the client (`send`). Because both sides are async, you can stream in both directions without buffering entire bodies in memory. There is no framework overhead, no middleware chain you did not ask for, and no magic. You control every byte.

Compared to building on top of nginx or HAProxy, an ASGI proxy gives you:

- Arbitrary Python logic in the request path (auth, transformation, aggregation).
- The same deployment model as the rest of your Python services.
- Trivial integration with your existing async libraries (database clients, caches, message queues).

The tradeoff is raw throughput. nginx will always be faster at shuffling bytes. But when you need programmability, ASGI is the right layer.

---

## Basic Proxying

### The Simplest Proxy

The minimal proxy reads the full request, forwards it to a hardcoded upstream, and sends the full response back. This is not production-ready (it buffers everything), but it establishes the pattern.

```python
import httpx


async def proxy(scope, receive, send):
    if scope["type"] == "lifespan":
        return

    assert scope["type"] == "http"

    # 1. Collect the full request body
    body = b""
    while True:
        event = await receive()
        body += event.get("body", b"")
        if not event.get("more_body", False):
            break

    # 2. Build the upstream URL
    path = scope["path"]
    query_string = scope.get("query_string", b"").decode("latin-1")
    upstream_url = f"http://localhost:8001{path}"
    if query_string:
        upstream_url += f"?{query_string}"

    # 3. Forward to upstream
    method = scope["method"]
    headers = dict(scope["headers"])  # list of (name, value) byte pairs
    request_headers = {
        k.decode("latin-1"): v.decode("latin-1")
        for k, v in scope["headers"]
    }

    async with httpx.AsyncClient() as client:
        upstream_resp = await client.request(
            method=method,
            url=upstream_url,
            headers=request_headers,
            content=body,
        )

    # 4. Send response start
    response_headers = [
        (k.lower().encode("latin-1"), v.encode("latin-1"))
        for k, v in upstream_resp.headers.multi_items()
    ]
    await send({
        "type": "http.response.start",
        "status": upstream_resp.status_code,
        "headers": response_headers,
    })

    # 5. Send response body
    await send({
        "type": "http.response.body",
        "body": upstream_resp.content,
        "more_body": False,
    })
```

Run it behind uvicorn:

```
uvicorn proxy:proxy --port 8000
```

Every request to `localhost:8000` is now forwarded to `localhost:8001`.

### Streaming the Request Body

Buffering the full request body defeats the purpose of async. ASGI gives you the body in chunks via `receive()`. To stream it upstream, use httpx's async streaming support with an async generator.

```python
async def stream_request_body(receive):
    """Yield request body chunks as they arrive from the client."""
    while True:
        event = await receive()
        body = event.get("body", b"")
        if body:
            yield body
        if not event.get("more_body", False):
            break
```

### Streaming the Response Back

Similarly, you can stream the upstream response back to the client chunk by chunk, without buffering the full response in memory.

```python
async def stream_response(upstream_resp, send):
    """Stream an httpx response back through ASGI send()."""
    response_headers = [
        (k.lower().encode("latin-1"), v.encode("latin-1"))
        for k, v in upstream_resp.headers.multi_items()
    ]

    await send({
        "type": "http.response.start",
        "status": upstream_resp.status_code,
        "headers": response_headers,
    })

    async for chunk in upstream_resp.aiter_bytes(chunk_size=8192):
        await send({
            "type": "http.response.body",
            "body": chunk,
            "more_body": True,
        })

    await send({
        "type": "http.response.body",
        "body": b"",
        "more_body": False,
    })
```

### Full Streaming Proxy

Combining both directions into a single application that never buffers more than one chunk at a time.

```python
import httpx


# Shared client -- created once, reused across requests.
# In production, manage this via lifespan events.
_client = httpx.AsyncClient()


async def stream_request_body(receive):
    while True:
        event = await receive()
        body = event.get("body", b"")
        if body:
            yield body
        if not event.get("more_body", False):
            break


async def streaming_proxy(scope, receive, send):
    if scope["type"] != "http":
        return

    path = scope["path"]
    qs = scope.get("query_string", b"").decode("latin-1")
    upstream_url = f"http://localhost:8001{path}"
    if qs:
        upstream_url += f"?{qs}"

    method = scope["method"]
    request_headers = {
        k.decode("latin-1"): v.decode("latin-1")
        for k, v in scope["headers"]
    }

    # Stream request body to upstream, stream response back to client
    req = _client.build_request(
        method=method,
        url=upstream_url,
        headers=request_headers,
        content=stream_request_body(receive),
    )

    upstream_resp = await _client.send(req, stream=True)

    try:
        response_headers = [
            (k.lower().encode("latin-1"), v.encode("latin-1"))
            for k, v in upstream_resp.headers.multi_items()
        ]

        await send({
            "type": "http.response.start",
            "status": upstream_resp.status_code,
            "headers": response_headers,
        })

        async for chunk in upstream_resp.aiter_bytes(chunk_size=8192):
            await send({
                "type": "http.response.body",
                "body": chunk,
                "more_body": True,
            })

        await send({
            "type": "http.response.body",
            "body": b"",
            "more_body": False,
        })
    finally:
        await upstream_resp.aclose()
```

The `finally` block ensures the upstream connection is closed even if the client disconnects mid-stream.

## Path-Based Routing

### Static Route Table

An API gateway typically routes different path prefixes to different backend services. Since an ASGI app is just a function, routing is just a dict lookup.

```python
import httpx


ROUTES = {
    "/users": "http://users-service:8001",
    "/orders": "http://orders-service:8002",
    "/products": "http://products-service:8003",
}

_client = httpx.AsyncClient()


def match_route(path: str) -> tuple[str, str] | None:
    """Return (upstream_base, remaining_path) or None."""
    for prefix, upstream in ROUTES.items():
        if path == prefix or path.startswith(prefix + "/"):
            remaining = path[len(prefix):] or "/"
            return upstream, remaining
    return None


async def send_error(send, status: int, message: bytes):
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [(b"content-type", b"text/plain")],
    })
    await send({
        "type": "http.response.body",
        "body": message,
        "more_body": False,
    })


async def routing_proxy(scope, receive, send):
    if scope["type"] != "http":
        return

    path = scope["path"]
    match = match_route(path)

    if match is None:
        await send_error(send, 404, b"No upstream configured for this path")
        return

    upstream_base, remaining_path = match
    qs = scope.get("query_string", b"").decode("latin-1")
    upstream_url = f"{upstream_base}{remaining_path}"
    if qs:
        upstream_url += f"?{qs}"

    method = scope["method"]
    request_headers = {
        k.decode("latin-1"): v.decode("latin-1")
        for k, v in scope["headers"]
    }

    # Collect body (for simplicity; use streaming in production)
    body = b""
    while True:
        event = await receive()
        body += event.get("body", b"")
        if not event.get("more_body", False):
            break

    upstream_resp = await _client.request(
        method=method,
        url=upstream_url,
        headers=request_headers,
        content=body,
    )

    response_headers = [
        (k.lower().encode("latin-1"), v.encode("latin-1"))
        for k, v in upstream_resp.headers.multi_items()
    ]

    await send({
        "type": "http.response.start",
        "status": upstream_resp.status_code,
        "headers": response_headers,
    })
    await send({
        "type": "http.response.body",
        "body": upstream_resp.content,
        "more_body": False,
    })
```

### Prefix Matching with Path Rewriting

Sometimes you want `/api/v1/users/123` at the gateway to arrive at `/users/123` on the upstream. This is path rewriting, and it is just string manipulation.

```python
ROUTE_RULES = [
    # (gateway_prefix, upstream_base, strip_prefix)
    ("/api/v1/users", "http://users-service:8001", True),
    ("/api/v1/orders", "http://orders-service:8002", True),
    ("/internal", "http://internal-service:9000", False),
]


def match_rule(path: str) -> tuple[str, str] | None:
    for prefix, upstream, strip in ROUTE_RULES:
        if path == prefix or path.startswith(prefix + "/"):
            if strip:
                remaining = path[len(prefix):] or "/"
            else:
                remaining = path
            return upstream, remaining
    return None
```

The rest of the proxy code is identical to the static route table example. Swap `match_route` for `match_rule`.

## Header Manipulation

### Adding Forwarded Headers

Upstream services need to know the original client's IP and protocol. The standard headers are `X-Forwarded-For`, `X-Forwarded-Proto`, and `X-Forwarded-Host`. These are constructed from the ASGI scope.

```python
def get_client_ip(scope) -> str:
    """Extract client IP from scope."""
    client = scope.get("client")
    if client:
        return client[0]
    return "unknown"


def build_forwarded_headers(scope) -> list[tuple[bytes, bytes]]:
    """Build X-Forwarded-* headers from the ASGI scope."""
    client_ip = get_client_ip(scope)
    scheme = scope.get("scheme", "http")

    # Extract the Host header from the original request
    host = b"unknown"
    for name, value in scope["headers"]:
        if name == b"host":
            host = value
            break

    return [
        (b"x-forwarded-for", client_ip.encode("latin-1")),
        (b"x-forwarded-proto", scheme.encode("latin-1")),
        (b"x-forwarded-host", host),
    ]


def inject_forwarded_headers(
    original_headers: list[tuple[bytes, bytes]],
    scope: dict,
) -> list[tuple[bytes, bytes]]:
    """Return a new header list with forwarded headers appended.

    If X-Forwarded-For already exists (from a downstream proxy),
    append the client IP to the existing value.
    """
    forwarded = build_forwarded_headers(scope)
    forwarded_names = {name for name, _ in forwarded}

    result = []
    xff_existing = None

    for name, value in original_headers:
        if name == b"x-forwarded-for":
            xff_existing = value
            continue  # will be replaced
        if name not in forwarded_names:
            result.append((name, value))

    # Append to existing XFF chain
    client_ip = get_client_ip(scope).encode("latin-1")
    if xff_existing:
        result.append((b"x-forwarded-for", xff_existing + b", " + client_ip))
    else:
        result.append((b"x-forwarded-for", client_ip))

    # Add the rest
    for name, value in forwarded:
        if name != b"x-forwarded-for":
            result.append((name, value))

    return result
```

### Stripping Internal Headers

You often want to prevent clients from sending headers that should only be set by internal services (e.g., `X-Internal-User-Id`). Strip them before forwarding.

```python
STRIPPED_REQUEST_HEADERS = {
    b"x-internal-user-id",
    b"x-internal-role",
    b"x-internal-trace-id",
}

STRIPPED_RESPONSE_HEADERS = {
    b"x-upstream-node",
    b"x-debug-timing",
    b"server",
}


def strip_headers(
    headers: list[tuple[bytes, bytes]],
    stripped: set[bytes],
) -> list[tuple[bytes, bytes]]:
    return [(name, value) for name, value in headers if name not in stripped]
```

Use this in the proxy before forwarding:

```python
clean_request_headers = strip_headers(scope["headers"], STRIPPED_REQUEST_HEADERS)
```

And before sending the response back:

```python
clean_response_headers = strip_headers(response_headers, STRIPPED_RESPONSE_HEADERS)
```

### Hop-by-Hop Header Filtering

HTTP/1.1 defines hop-by-hop headers that must not be forwarded by proxies. These include `Connection`, `Keep-Alive`, `Transfer-Encoding`, `TE`, `Trailer`, `Upgrade`, and `Proxy-Authorization`.

```python
HOP_BY_HOP = {
    b"connection",
    b"keep-alive",
    b"transfer-encoding",
    b"te",
    b"trailer",
    b"upgrade",
    b"proxy-authorization",
    b"proxy-authenticate",
}


def filter_hop_by_hop(
    headers: list[tuple[bytes, bytes]],
) -> list[tuple[bytes, bytes]]:
    return [(name, value) for name, value in headers if name not in HOP_BY_HOP]
```

In a real proxy you would chain all three: strip internal headers, filter hop-by-hop, then inject forwarded headers.

## Load Balancing

When an upstream service has multiple replicas, the gateway needs a strategy to distribute requests across them.

### Round-Robin

The simplest strategy. Rotate through backends in order.

```python
import itertools


class RoundRobin:
    def __init__(self, backends: list[str]):
        self._cycle = itertools.cycle(backends)

    def next(self) -> str:
        return next(self._cycle)


# Usage
users_lb = RoundRobin([
    "http://users-1:8001",
    "http://users-2:8001",
    "http://users-3:8001",
])

# In the proxy:
upstream_base = users_lb.next()
```

This is not thread-safe across multiple asyncio tasks -- but since `next()` on `itertools.cycle` is atomic in CPython (GIL), it works in practice. For correctness under other runtimes, add a lock.

```python
import asyncio


class SafeRoundRobin:
    def __init__(self, backends: list[str]):
        self._backends = backends
        self._index = 0
        self._lock = asyncio.Lock()

    async def next(self) -> str:
        async with self._lock:
            backend = self._backends[self._index % len(self._backends)]
            self._index += 1
            return backend
```

### Least Connections

Route to the backend with the fewest active connections. This requires tracking in-flight requests.

```python
import asyncio


class LeastConnections:
    def __init__(self, backends: list[str]):
        self._backends = backends
        self._active: dict[str, int] = {b: 0 for b in backends}
        self._lock = asyncio.Lock()

    async def acquire(self) -> str:
        """Pick the backend with fewest active connections and increment."""
        async with self._lock:
            backend = min(self._active, key=self._active.get)
            self._active[backend] += 1
            return backend

    async def release(self, backend: str):
        """Decrement the active count for a backend."""
        async with self._lock:
            self._active[backend] = max(0, self._active[backend] - 1)

    @property
    def stats(self) -> dict[str, int]:
        return dict(self._active)
```

Used in the proxy like this:

```python
lb = LeastConnections([
    "http://users-1:8001",
    "http://users-2:8001",
])

async def proxy_with_lc(scope, receive, send):
    if scope["type"] != "http":
        return

    backend = await lb.acquire()
    try:
        # ... forward request to `backend` ...
        pass
    finally:
        await lb.release(backend)
```

The `try/finally` is essential. If the upstream call fails or the client disconnects, the connection count must still be decremented.

### Weighted Round-Robin

Some backends are more powerful than others. Assign weights.

```python
class WeightedRoundRobin:
    def __init__(self, backends: list[tuple[str, int]]):
        """backends is a list of (url, weight) tuples."""
        self._pool: list[str] = []
        for url, weight in backends:
            self._pool.extend([url] * weight)
        self._index = 0

    def next(self) -> str:
        backend = self._pool[self._index % len(self._pool)]
        self._index += 1
        return backend


# A backend with weight 3 gets 3x the traffic of weight 1
lb = WeightedRoundRobin([
    ("http://big-box:8001", 3),
    ("http://small-box:8001", 1),
])
```

## Rate Limiting

### Token Bucket per Client IP

The token bucket algorithm allows bursts up to a maximum, then throttles to a steady rate. Each client IP gets its own bucket.

```python
import asyncio
import time


class TokenBucket:
    def __init__(self, rate: float, capacity: int):
        """
        rate: tokens added per second
        capacity: maximum tokens in the bucket
        """
        self.rate = rate
        self.capacity = capacity
        self._tokens: float = capacity
        self._last_refill: float = time.monotonic()
        self._lock = asyncio.Lock()

    async def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens. Returns True if allowed, False if denied."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(
                self.capacity,
                self._tokens + elapsed * self.rate,
            )
            self._last_refill = now

            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False


class PerClientRateLimiter:
    def __init__(self, rate: float, capacity: int):
        self.rate = rate
        self.capacity = capacity
        self._buckets: dict[str, TokenBucket] = {}
        self._lock = asyncio.Lock()

    async def allow(self, client_ip: str) -> bool:
        async with self._lock:
            if client_ip not in self._buckets:
                self._buckets[client_ip] = TokenBucket(
                    self.rate, self.capacity
                )
        bucket = self._buckets[client_ip]
        return await bucket.consume()
```

### Sliding Window Counter

An alternative to token bucket. Count requests in a sliding time window. Simpler to reason about, but no burst tolerance.

```python
import asyncio
import time
from collections import defaultdict


class SlidingWindowRateLimiter:
    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def allow(self, client_ip: str) -> bool:
        async with self._lock:
            now = time.monotonic()
            cutoff = now - self.window_seconds

            # Prune old entries
            timestamps = self._requests[client_ip]
            self._requests[client_ip] = [
                t for t in timestamps if t > cutoff
            ]

            if len(self._requests[client_ip]) >= self.max_requests:
                return False

            self._requests[client_ip].append(now)
            return True
```

### Rate Limiter as Middleware

Wrap the proxy app with rate limiting. This is the ASGI middleware pattern: a callable that takes an inner app and returns a new ASGI app.

```python
import json


def rate_limit_middleware(app, rate: float = 10.0, capacity: int = 20):
    """
    Wrap an ASGI app with per-IP rate limiting.
    rate: tokens per second
    capacity: burst size
    """
    limiter = PerClientRateLimiter(rate, capacity)

    async def middleware(scope, receive, send):
        if scope["type"] != "http":
            await app(scope, receive, send)
            return

        client_ip = scope.get("client", ("unknown",))[0]

        if not await limiter.allow(client_ip):
            body = json.dumps({
                "error": "rate_limit_exceeded",
                "message": "Too many requests",
            }).encode("utf-8")

            await send({
                "type": "http.response.start",
                "status": 429,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"retry-after", b"1"),
                    (b"content-length", str(len(body)).encode("latin-1")),
                ],
            })
            await send({
                "type": "http.response.body",
                "body": body,
                "more_body": False,
            })
            return

        await app(scope, receive, send)

    return middleware


# Usage: wrap the proxy
app = rate_limit_middleware(streaming_proxy, rate=10.0, capacity=20)
```

## Request and Response Transformation

### Aggregating Multiple Upstreams

A common gateway pattern: the client makes one request, and the gateway fans out to multiple backend services, aggregates the results, and returns a single response.

```python
import asyncio
import json
import httpx


_client = httpx.AsyncClient()


async def aggregate_user_profile(user_id: str) -> dict:
    """Fetch user data, orders, and preferences in parallel."""
    urls = {
        "user": f"http://users-service:8001/users/{user_id}",
        "orders": f"http://orders-service:8002/users/{user_id}/orders",
        "preferences": f"http://prefs-service:8003/users/{user_id}/prefs",
    }

    async def fetch(key: str, url: str) -> tuple[str, dict | None]:
        try:
            resp = await _client.get(url, timeout=5.0)
            if resp.status_code == 200:
                return key, resp.json()
            return key, None
        except httpx.RequestError:
            return key, None

    tasks = [fetch(key, url) for key, url in urls.items()]
    results = await asyncio.gather(*tasks)

    return {key: data for key, data in results if data is not None}


async def aggregation_gateway(scope, receive, send):
    if scope["type"] != "http":
        return

    path = scope["path"]

    # Match /profiles/{user_id}
    if path.startswith("/profiles/") and scope["method"] == "GET":
        user_id = path.split("/")[2]
        profile = await aggregate_user_profile(user_id)

        body = json.dumps(profile).encode("utf-8")

        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("latin-1")),
            ],
        })
        await send({
            "type": "http.response.body",
            "body": body,
            "more_body": False,
        })
        return

    # Everything else: 404
    await send({
        "type": "http.response.start",
        "status": 404,
        "headers": [(b"content-type", b"text/plain")],
    })
    await send({
        "type": "http.response.body",
        "body": b"Not Found",
        "more_body": False,
    })
```

### Response Body Rewriting

Sometimes you need to modify the upstream's response before returning it to the client. This requires buffering the response body, since you cannot modify `http.response.start` after it has been sent.

```python
import json
import httpx


_client = httpx.AsyncClient()


async def rewriting_proxy(scope, receive, send):
    """Proxy that redacts sensitive fields from JSON responses."""
    if scope["type"] != "http":
        return

    REDACTED_FIELDS = {"ssn", "password", "secret_key", "credit_card"}

    # Collect request body
    body = b""
    while True:
        event = await receive()
        body += event.get("body", b"")
        if not event.get("more_body", False):
            break

    # Forward to upstream
    path = scope["path"]
    qs = scope.get("query_string", b"").decode("latin-1")
    url = f"http://localhost:8001{path}"
    if qs:
        url += f"?{qs}"

    headers = {
        k.decode("latin-1"): v.decode("latin-1")
        for k, v in scope["headers"]
    }

    resp = await _client.request(
        method=scope["method"],
        url=url,
        headers=headers,
        content=body,
    )

    # Check if response is JSON
    content_type = resp.headers.get("content-type", "")
    response_body = resp.content

    if "application/json" in content_type:
        try:
            data = resp.json()
            data = redact_fields(data, REDACTED_FIELDS)
            response_body = json.dumps(data).encode("utf-8")
        except (json.JSONDecodeError, ValueError):
            pass  # forward as-is

    response_headers = [
        (k.lower().encode("latin-1"), v.encode("latin-1"))
        for k, v in resp.headers.multi_items()
        if k.lower() != "content-length"
    ]
    response_headers.append(
        (b"content-length", str(len(response_body)).encode("latin-1"))
    )

    await send({
        "type": "http.response.start",
        "status": resp.status_code,
        "headers": response_headers,
    })
    await send({
        "type": "http.response.body",
        "body": response_body,
        "more_body": False,
    })


def redact_fields(data, fields: set[str]):
    """Recursively redact fields from a dict/list structure."""
    if isinstance(data, dict):
        return {
            k: "[REDACTED]" if k in fields else redact_fields(v, fields)
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [redact_fields(item, fields) for item in data]
    return data
```

## Health Checks and Circuit Breakers

### Active Health Checking

Periodically probe upstream services and remove unhealthy ones from the load balancer pool.

```python
import asyncio
import httpx
import time


class HealthChecker:
    def __init__(
        self,
        backends: list[str],
        check_path: str = "/health",
        interval: float = 10.0,
        timeout: float = 3.0,
        unhealthy_threshold: int = 3,
        healthy_threshold: int = 2,
    ):
        self._backends = backends
        self._check_path = check_path
        self._interval = interval
        self._timeout = timeout
        self._unhealthy_threshold = unhealthy_threshold
        self._healthy_threshold = healthy_threshold

        self._healthy: set[str] = set(backends)
        self._fail_counts: dict[str, int] = {b: 0 for b in backends}
        self._success_counts: dict[str, int] = {b: 0 for b in backends}
        self._client = httpx.AsyncClient()
        self._task: asyncio.Task | None = None

    @property
    def healthy_backends(self) -> list[str]:
        return [b for b in self._backends if b in self._healthy]

    async def start(self):
        self._task = asyncio.create_task(self._check_loop())

    async def stop(self):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self._client.aclose()

    async def _check_loop(self):
        while True:
            await asyncio.gather(
                *(self._check_one(b) for b in self._backends),
                return_exceptions=True,
            )
            await asyncio.sleep(self._interval)

    async def _check_one(self, backend: str):
        try:
            resp = await self._client.get(
                f"{backend}{self._check_path}",
                timeout=self._timeout,
            )
            if 200 <= resp.status_code < 300:
                self._fail_counts[backend] = 0
                self._success_counts[backend] += 1
                if self._success_counts[backend] >= self._healthy_threshold:
                    self._healthy.add(backend)
            else:
                self._on_failure(backend)
        except (httpx.RequestError, httpx.TimeoutException):
            self._on_failure(backend)

    def _on_failure(self, backend: str):
        self._success_counts[backend] = 0
        self._fail_counts[backend] += 1
        if self._fail_counts[backend] >= self._unhealthy_threshold:
            self._healthy.discard(backend)
```

### Circuit Breaker Pattern

A circuit breaker stops sending requests to a failing upstream after a threshold of consecutive failures, then periodically allows a single probe to check if the upstream has recovered.

States:

- **Closed**: requests flow normally. Failures are counted.
- **Open**: all requests are immediately rejected. After a timeout, transitions to half-open.
- **Half-Open**: one request is allowed through. If it succeeds, close the circuit. If it fails, open it again.

```python
import asyncio
import time
from enum import Enum


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 1,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._half_open_calls = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if time.monotonic() - self._last_failure_time > self.recovery_timeout:
                return CircuitState.HALF_OPEN
        return self._state

    async def allow_request(self) -> bool:
        async with self._lock:
            current = self.state

            if current == CircuitState.CLOSED:
                return True

            if current == CircuitState.OPEN:
                return False

            # half_open
            if self._half_open_calls < self.half_open_max_calls:
                self._half_open_calls += 1
                return True
            return False

    async def record_success(self):
        async with self._lock:
            self._failure_count = 0
            self._half_open_calls = 0
            self._state = CircuitState.CLOSED

    async def record_failure(self):
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()

            if self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                self._half_open_calls = 0
```

### Integrating the Circuit Breaker with the Proxy

```python
import httpx
import json


_client = httpx.AsyncClient()

# One circuit breaker per upstream
_circuits: dict[str, CircuitBreaker] = {}


def get_circuit(backend: str) -> CircuitBreaker:
    if backend not in _circuits:
        _circuits[backend] = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=30.0,
        )
    return _circuits[backend]


async def proxy_with_circuit_breaker(scope, receive, send):
    if scope["type"] != "http":
        return

    backend = "http://upstream:8001"  # or from load balancer
    circuit = get_circuit(backend)

    if not await circuit.allow_request():
        body = json.dumps({
            "error": "service_unavailable",
            "message": "Circuit breaker is open",
        }).encode("utf-8")
        await send({
            "type": "http.response.start",
            "status": 503,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("latin-1")),
            ],
        })
        await send({
            "type": "http.response.body",
            "body": body,
            "more_body": False,
        })
        return

    # Collect request body
    request_body = b""
    while True:
        event = await receive()
        request_body += event.get("body", b"")
        if not event.get("more_body", False):
            break

    try:
        path = scope["path"]
        qs = scope.get("query_string", b"").decode("latin-1")
        url = f"{backend}{path}"
        if qs:
            url += f"?{qs}"

        headers = {
            k.decode("latin-1"): v.decode("latin-1")
            for k, v in scope["headers"]
        }

        resp = await _client.request(
            method=scope["method"],
            url=url,
            headers=headers,
            content=request_body,
            timeout=10.0,
        )

        if resp.status_code >= 500:
            await circuit.record_failure()
        else:
            await circuit.record_success()

        response_headers = [
            (k.lower().encode("latin-1"), v.encode("latin-1"))
            for k, v in resp.headers.multi_items()
        ]
        await send({
            "type": "http.response.start",
            "status": resp.status_code,
            "headers": response_headers,
        })
        await send({
            "type": "http.response.body",
            "body": resp.content,
            "more_body": False,
        })

    except (httpx.RequestError, httpx.TimeoutException):
        await circuit.record_failure()

        body = json.dumps({
            "error": "upstream_error",
            "message": "Failed to reach upstream",
        }).encode("utf-8")
        await send({
            "type": "http.response.start",
            "status": 502,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("latin-1")),
            ],
        })
        await send({
            "type": "http.response.body",
            "body": body,
            "more_body": False,
        })
```

---

## Authentication at the Gateway

### JWT Validation Before Forwarding

Validate JWTs at the gateway so upstream services do not need to handle authentication. The gateway decodes the token, checks the signature and expiry, and either forwards the request with extracted claims or rejects it.

```python
import json
import time
import hashlib
import hmac
import base64


def _b64decode(s: str) -> bytes:
    """Base64url decode with padding."""
    s += "=" * (4 - len(s) % 4)
    return base64.urlsafe_b64decode(s)


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def validate_jwt(token: str, secret: str) -> dict | None:
    """
    Validate an HS256 JWT. Returns the payload dict if valid, None otherwise.

    In production, use a proper JWT library (PyJWT, python-jose).
    This is intentionally minimal to avoid framework dependencies.
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None

        header_b64, payload_b64, signature_b64 = parts

        # Verify signature (HS256)
        signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
        expected_sig = hmac.new(
            secret.encode("utf-8"),
            signing_input,
            hashlib.sha256,
        ).digest()

        actual_sig = _b64decode(signature_b64)

        if not hmac.compare_digest(expected_sig, actual_sig):
            return None

        # Decode header
        header = json.loads(_b64decode(header_b64))
        if header.get("alg") != "HS256":
            return None

        # Decode payload
        payload = json.loads(_b64decode(payload_b64))

        # Check expiry
        exp = payload.get("exp")
        if exp is not None and time.time() > exp:
            return None

        return payload

    except Exception:
        return None
```

### Auth Middleware Wrapping the Proxy

```python
import json


JWT_SECRET = "your-secret-key"  # In production, load from env/secrets manager

# Paths that do not require authentication
PUBLIC_PATHS = {"/health", "/ready", "/login", "/register"}


def auth_middleware(app):
    async def middleware(scope, receive, send):
        if scope["type"] != "http":
            await app(scope, receive, send)
            return

        path = scope["path"]

        # Skip auth for public paths
        if path in PUBLIC_PATHS:
            await app(scope, receive, send)
            return

        # Extract Authorization header
        auth_header = None
        for name, value in scope["headers"]:
            if name == b"authorization":
                auth_header = value.decode("latin-1")
                break

        if not auth_header or not auth_header.startswith("Bearer "):
            body = json.dumps({
                "error": "unauthorized",
                "message": "Missing or invalid Authorization header",
            }).encode("utf-8")
            await send({
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("latin-1")),
                    (b"www-authenticate", b"Bearer"),
                ],
            })
            await send({
                "type": "http.response.body",
                "body": body,
                "more_body": False,
            })
            return

        token = auth_header[7:]  # strip "Bearer "
        claims = validate_jwt(token, JWT_SECRET)

        if claims is None:
            body = json.dumps({
                "error": "unauthorized",
                "message": "Invalid or expired token",
            }).encode("utf-8")
            await send({
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("latin-1")),
                    (b"www-authenticate", b"Bearer"),
                ],
            })
            await send({
                "type": "http.response.body",
                "body": body,
                "more_body": False,
            })
            return

        # Inject claims as headers for upstream services
        extra_headers = [
            (b"x-auth-user-id", str(claims.get("sub", "")).encode("latin-1")),
            (b"x-auth-role", str(claims.get("role", "")).encode("latin-1")),
        ]

        # Create a new scope with the extra headers
        new_headers = list(scope["headers"]) + extra_headers
        new_scope = {**scope, "headers": new_headers}

        await app(new_scope, receive, send)

    return middleware


# Usage: wrap the proxy
app = auth_middleware(streaming_proxy)
```

---

## Putting It All Together

A complete API gateway that combines routing, header manipulation, rate limiting, circuit breaking, authentication, and health checking. This is a single file you can run with `uvicorn gateway:app`.

```python
import asyncio
import json
import time
import hashlib
import hmac
import base64
import itertools
from enum import Enum

import httpx


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

JWT_SECRET = "change-me-in-production"

ROUTES = {
    "/users": ["http://users-1:8001", "http://users-2:8001"],
    "/orders": ["http://orders-1:8002"],
    "/products": ["http://products-1:8003", "http://products-2:8003"],
}

PUBLIC_PATHS = {"/health", "/ready", "/login"}

RATE_LIMIT_RATE = 20.0       # tokens per second
RATE_LIMIT_CAPACITY = 40     # burst size

CIRCUIT_FAILURE_THRESHOLD = 5
CIRCUIT_RECOVERY_TIMEOUT = 30.0


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

HOP_BY_HOP = {
    b"connection", b"keep-alive", b"transfer-encoding",
    b"te", b"trailer", b"upgrade",
    b"proxy-authorization", b"proxy-authenticate",
}

STRIPPED_REQUEST_HEADERS = {b"x-auth-user-id", b"x-auth-role"}


def get_client_ip(scope) -> str:
    client = scope.get("client")
    return client[0] if client else "unknown"


def prepare_request_headers(scope) -> list[tuple[bytes, bytes]]:
    headers = [
        (name, value)
        for name, value in scope["headers"]
        if name not in HOP_BY_HOP and name not in STRIPPED_REQUEST_HEADERS
    ]
    client_ip = get_client_ip(scope).encode("latin-1")
    scheme = scope.get("scheme", "http").encode("latin-1")

    host = b"unknown"
    for name, value in scope["headers"]:
        if name == b"host":
            host = value
            break

    headers.extend([
        (b"x-forwarded-for", client_ip),
        (b"x-forwarded-proto", scheme),
        (b"x-forwarded-host", host),
    ])
    return headers


def prepare_response_headers(
    resp_headers: list[tuple[str, str]],
) -> list[tuple[bytes, bytes]]:
    return [
        (k.lower().encode("latin-1"), v.encode("latin-1"))
        for k, v in resp_headers
        if k.lower().encode("latin-1") not in HOP_BY_HOP
    ]


async def send_json(send, status: int, data: dict):
    body = json.dumps(data).encode("utf-8")
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode("latin-1")),
        ],
    })
    await send({
        "type": "http.response.body",
        "body": body,
        "more_body": False,
    })


async def read_body(receive) -> bytes:
    body = b""
    while True:
        event = await receive()
        body += event.get("body", b"")
        if not event.get("more_body", False):
            break
    return body


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------

def _b64decode(s: str) -> bytes:
    s += "=" * (4 - len(s) % 4)
    return base64.urlsafe_b64decode(s)


def validate_jwt(token: str, secret: str) -> dict | None:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header_b64, payload_b64, sig_b64 = parts
        signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
        expected = hmac.new(
            secret.encode("utf-8"), signing_input, hashlib.sha256
        ).digest()
        if not hmac.compare_digest(expected, _b64decode(sig_b64)):
            return None
        header = json.loads(_b64decode(header_b64))
        if header.get("alg") != "HS256":
            return None
        payload = json.loads(_b64decode(payload_b64))
        if payload.get("exp") and time.time() > payload["exp"]:
            return None
        return payload
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Rate Limiter
# ---------------------------------------------------------------------------

class TokenBucket:
    def __init__(self, rate: float, capacity: int):
        self.rate = rate
        self.capacity = capacity
        self._tokens: float = capacity
        self._last: float = time.monotonic()
        self._lock = asyncio.Lock()

    async def consume(self) -> bool:
        async with self._lock:
            now = time.monotonic()
            self._tokens = min(
                self.capacity,
                self._tokens + (now - self._last) * self.rate,
            )
            self._last = now
            if self._tokens >= 1:
                self._tokens -= 1
                return True
            return False


class RateLimiter:
    def __init__(self, rate: float, capacity: int):
        self._rate = rate
        self._capacity = capacity
        self._buckets: dict[str, TokenBucket] = {}

    async def allow(self, key: str) -> bool:
        if key not in self._buckets:
            self._buckets[key] = TokenBucket(self._rate, self._capacity)
        return await self._buckets[key].consume()


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------

class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(self, failure_threshold: int, recovery_timeout: float):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._state = CircuitState.CLOSED
        self._failures = 0
        self._last_failure: float = 0.0
        self._lock = asyncio.Lock()

    async def allow(self) -> bool:
        async with self._lock:
            if self._state == CircuitState.CLOSED:
                return True
            if self._state == CircuitState.OPEN:
                if time.monotonic() - self._last_failure > self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    return True
                return False
            return True  # half-open: allow one probe

    async def record_success(self):
        async with self._lock:
            self._failures = 0
            self._state = CircuitState.CLOSED

    async def record_failure(self):
        async with self._lock:
            self._failures += 1
            self._last_failure = time.monotonic()
            if self._failures >= self.failure_threshold:
                self._state = CircuitState.OPEN


# ---------------------------------------------------------------------------
# Load Balancer
# ---------------------------------------------------------------------------

class RoundRobinLB:
    def __init__(self, backends: list[str]):
        self._cycle = itertools.cycle(backends)
        self._backends = backends

    def next(self) -> str:
        return next(self._cycle)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

class Router:
    def __init__(self, routes: dict[str, list[str]]):
        self._rules: list[tuple[str, RoundRobinLB]] = []
        for prefix, backends in routes.items():
            self._rules.append((prefix, RoundRobinLB(backends)))

    def match(self, path: str) -> tuple[str, str] | None:
        for prefix, lb in self._rules:
            if path == prefix or path.startswith(prefix + "/"):
                backend = lb.next()
                remaining = path[len(prefix):] or "/"
                return backend, remaining
        return None


# ---------------------------------------------------------------------------
# Gateway Application
# ---------------------------------------------------------------------------

_client: httpx.AsyncClient | None = None
_rate_limiter = RateLimiter(RATE_LIMIT_RATE, RATE_LIMIT_CAPACITY)
_router = Router(ROUTES)
_circuits: dict[str, CircuitBreaker] = {}


def _get_circuit(backend: str) -> CircuitBreaker:
    if backend not in _circuits:
        _circuits[backend] = CircuitBreaker(
            CIRCUIT_FAILURE_THRESHOLD, CIRCUIT_RECOVERY_TIMEOUT
        )
    return _circuits[backend]


async def _handle_lifespan(scope, receive, send):
    while True:
        event = await receive()
        if event["type"] == "lifespan.startup":
            global _client
            _client = httpx.AsyncClient()
            await send({"type": "lifespan.startup.complete"})
        elif event["type"] == "lifespan.shutdown":
            if _client:
                await _client.aclose()
            await send({"type": "lifespan.shutdown.complete"})
            return


async def _handle_health(scope, receive, send):
    await send_json(send, 200, {"status": "ok"})


async def app(scope, receive, send):
    # ---- Lifespan ----
    if scope["type"] == "lifespan":
        await _handle_lifespan(scope, receive, send)
        return

    if scope["type"] != "http":
        return

    path = scope["path"]

    # ---- Health endpoint ----
    if path == "/health":
        await _handle_health(scope, receive, send)
        return

    # ---- Rate limiting ----
    client_ip = get_client_ip(scope)
    if not await _rate_limiter.allow(client_ip):
        await send_json(send, 429, {
            "error": "rate_limit_exceeded",
            "message": "Too many requests",
        })
        return

    # ---- Authentication ----
    if path not in PUBLIC_PATHS:
        auth_header = None
        for name, value in scope["headers"]:
            if name == b"authorization":
                auth_header = value.decode("latin-1")
                break

        if not auth_header or not auth_header.startswith("Bearer "):
            await send_json(send, 401, {
                "error": "unauthorized",
                "message": "Missing Bearer token",
            })
            return

        claims = validate_jwt(auth_header[7:], JWT_SECRET)
        if claims is None:
            await send_json(send, 401, {
                "error": "unauthorized",
                "message": "Invalid or expired token",
            })
            return

        # Inject identity headers for upstream
        scope = {
            **scope,
            "headers": list(scope["headers"]) + [
                (b"x-auth-user-id", str(claims.get("sub", "")).encode()),
                (b"x-auth-role", str(claims.get("role", "")).encode()),
            ],
        }

    # ---- Routing ----
    match = _router.match(path)
    if match is None:
        await send_json(send, 404, {
            "error": "not_found",
            "message": f"No upstream for {path}",
        })
        return

    backend, remaining_path = match

    # ---- Circuit breaker ----
    circuit = _get_circuit(backend)
    if not await circuit.allow():
        await send_json(send, 503, {
            "error": "service_unavailable",
            "message": "Circuit breaker is open",
        })
        return

    # ---- Proxy the request ----
    request_body = await read_body(receive)

    qs = scope.get("query_string", b"").decode("latin-1")
    url = f"{backend}{remaining_path}"
    if qs:
        url += f"?{qs}"

    req_headers = prepare_request_headers(scope)
    headers_dict = {
        k.decode("latin-1"): v.decode("latin-1")
        for k, v in req_headers
    }

    try:
        resp = await _client.request(
            method=scope["method"],
            url=url,
            headers=headers_dict,
            content=request_body,
            timeout=10.0,
        )

        if resp.status_code >= 500:
            await circuit.record_failure()
        else:
            await circuit.record_success()

        resp_headers = prepare_response_headers(
            list(resp.headers.multi_items())
        )

        await send({
            "type": "http.response.start",
            "status": resp.status_code,
            "headers": resp_headers,
        })
        await send({
            "type": "http.response.body",
            "body": resp.content,
            "more_body": False,
        })

    except (httpx.RequestError, httpx.TimeoutException):
        await circuit.record_failure()
        await send_json(send, 502, {
            "error": "bad_gateway",
            "message": "Upstream connection failed",
        })
```

Run it:

```
uvicorn gateway:app --host 0.0.0.0 --port 8000
```

What this gives you:

- **Lifespan management**: creates and closes the httpx client cleanly.
- **Health endpoint**: `/health` returns 200 without auth or rate limiting.
- **Rate limiting**: per-IP token bucket. Returns 429 when exceeded.
- **JWT authentication**: validates HS256 tokens, injects `x-auth-user-id` and `x-auth-role` headers for upstreams.
- **Path-based routing**: matches prefixes, strips them, round-robins across backends.
- **Circuit breakers**: per-backend. Opens after 5 failures, closes after 30s recovery.
- **Header sanitization**: strips hop-by-hop headers and internal headers, adds `X-Forwarded-*`.
- **Error handling**: returns structured JSON for all error conditions.

Every component is a plain Python class with no framework dependencies. You can test each one independently, swap implementations (e.g., replace round-robin with least-connections), or extract any piece into its own middleware.

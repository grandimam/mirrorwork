# Module 22: Middleware Systems

## Overview

Middleware is code that runs between receiving a request and sending a response. It enables cross-cutting concerns like authentication, logging, and compression without cluttering route handlers. This module covers middleware patterns, composition, and building a flexible middleware system.

---

## Learning Objectives

By the end of this module, you will be able to:

1. Design middleware interfaces
2. Implement common middleware patterns
3. Build middleware pipelines
4. Handle middleware ordering and dependencies
5. Create composable middleware systems

---

## 22.1 Middleware Concepts

### The Onion Model

```
┌─────────────────────────────────────────────────────────────┐
│                     Middleware Stack                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│    Request  ─────────────────────────────────▶             │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Logging Middleware                                  │   │
│  │  ┌─────────────────────────────────────────────┐    │   │
│  │  │  Authentication Middleware                   │    │   │
│  │  │  ┌───────────────────────────────────────┐  │    │   │
│  │  │  │  Rate Limiting Middleware              │  │    │   │
│  │  │  │  ┌─────────────────────────────────┐  │  │    │   │
│  │  │  │  │  Compression Middleware          │  │  │    │   │
│  │  │  │  │  ┌───────────────────────────┐  │  │  │    │   │
│  │  │  │  │  │                           │  │  │  │    │   │
│  │  │  │  │  │     Route Handler         │  │  │  │    │   │
│  │  │  │  │  │                           │  │  │  │    │   │
│  │  │  │  │  └───────────────────────────┘  │  │  │    │   │
│  │  │  │  └─────────────────────────────────┘  │  │    │   │
│  │  │  └───────────────────────────────────────┘  │    │   │
│  │  └─────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│    Response ◀─────────────────────────────────             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Middleware Responsibilities

| Middleware | Request Phase | Response Phase |
|------------|---------------|----------------|
| Logging | Log request start | Log request end, duration |
| Authentication | Verify token, set user | - |
| Rate Limiting | Check/update limits | - |
| Compression | - | Compress response body |
| CORS | Handle preflight | Add headers |
| Error Handling | - | Catch and format errors |

---

## 22.2 Middleware Interface

### ASGI-Style Middleware

```python
from typing import Callable, Awaitable

# Type definitions
Scope = dict
Receive = Callable[[], Awaitable[dict]]
Send = Callable[[dict], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]


class Middleware:
    """Base middleware class."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        """Process request through middleware."""
        # Default: pass through to next middleware/handler
        await self.app(scope, receive, send)


# Function-style middleware
def middleware(handler: Callable[[ASGIApp], ASGIApp]) -> Callable[[ASGIApp], ASGIApp]:
    """Decorator for creating middleware."""
    return handler


@middleware
def logging_middleware(app: ASGIApp) -> ASGIApp:
    async def middleware_handler(scope: Scope, receive: Receive, send: Send):
        if scope['type'] == 'http':
            print(f"Request: {scope['method']} {scope['path']}")
        await app(scope, receive, send)
    return middleware_handler
```

### Request/Response Middleware Pattern

```python
from dataclasses import dataclass
from typing import Optional, Any


@dataclass
class Request:
    method: str
    path: str
    headers: dict
    body: bytes
    state: dict  # Middleware can attach data here


@dataclass
class Response:
    status: int
    headers: dict
    body: bytes


# Middleware as function
MiddlewareFunc = Callable[[Request, Callable], Awaitable[Response]]


class MiddlewareChain:
    """Chain of middleware functions."""

    def __init__(self):
        self.middlewares: list[MiddlewareFunc] = []

    def use(self, middleware: MiddlewareFunc):
        """Add middleware to chain."""
        self.middlewares.append(middleware)

    async def execute(self, request: Request,
                     handler: Callable[[Request], Awaitable[Response]]) -> Response:
        """Execute middleware chain."""
        async def build_chain(index: int):
            if index >= len(self.middlewares):
                return await handler(request)

            middleware = self.middlewares[index]
            return await middleware(request, lambda: build_chain(index + 1))

        return await build_chain(0)
```

---

## 22.3 Common Middleware Implementations

### Logging Middleware

```python
import time
import logging

logger = logging.getLogger(__name__)


class LoggingMiddleware:
    """Log request/response details."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        start_time = time.perf_counter()
        method = scope['method']
        path = scope['path']
        status_code = 0

        async def send_wrapper(message):
            nonlocal status_code
            if message['type'] == 'http.response.start':
                status_code = message['status']
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration = (time.perf_counter() - start_time) * 1000
            logger.info(
                f"{method} {path} - {status_code} - {duration:.2f}ms"
            )
```

### Authentication Middleware

```python
from typing import Optional, List


class AuthenticationMiddleware:
    """JWT authentication middleware."""

    def __init__(self, app: ASGIApp,
                 jwt_handler,
                 exclude_paths: List[str] = None):
        self.app = app
        self.jwt_handler = jwt_handler
        self.exclude_paths = exclude_paths or []

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        # Check if path is excluded
        if scope['path'] in self.exclude_paths:
            return await self.app(scope, receive, send)

        # Extract token
        token = self._extract_token(scope)
        if not token:
            return await self._unauthorized(send, "Missing token")

        # Verify token
        payload = self.jwt_handler.verify_token(token)
        if not payload:
            return await self._unauthorized(send, "Invalid token")

        # Add user to scope
        scope['user'] = payload
        await self.app(scope, receive, send)

    def _extract_token(self, scope: Scope) -> Optional[str]:
        for name, value in scope.get('headers', []):
            if name == b'authorization':
                auth = value.decode()
                if auth.startswith('Bearer '):
                    return auth[7:]
        return None

    async def _unauthorized(self, send: Send, message: str):
        await send({
            'type': 'http.response.start',
            'status': 401,
            'headers': [(b'content-type', b'application/json')],
        })
        await send({
            'type': 'http.response.body',
            'body': f'{{"error": "{message}"}}'.encode(),
        })
```

### CORS Middleware

```python
from dataclasses import dataclass
from typing import List


@dataclass
class CORSConfig:
    allow_origins: List[str] = None
    allow_methods: List[str] = None
    allow_headers: List[str] = None
    expose_headers: List[str] = None
    allow_credentials: bool = False
    max_age: int = 600

    def __post_init__(self):
        self.allow_origins = self.allow_origins or ['*']
        self.allow_methods = self.allow_methods or ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']
        self.allow_headers = self.allow_headers or ['*']
        self.expose_headers = self.expose_headers or []


class CORSMiddleware:
    """Cross-Origin Resource Sharing middleware."""

    def __init__(self, app: ASGIApp, config: CORSConfig = None):
        self.app = app
        self.config = config or CORSConfig()

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        origin = self._get_origin(scope)
        method = scope['method']

        # Handle preflight
        if method == 'OPTIONS':
            await self._handle_preflight(send, origin)
            return

        # Add CORS headers to response
        async def send_wrapper(message):
            if message['type'] == 'http.response.start':
                headers = list(message.get('headers', []))
                headers.extend(self._cors_headers(origin))
                message = {**message, 'headers': headers}
            await send(message)

        await self.app(scope, receive, send_wrapper)

    def _get_origin(self, scope: Scope) -> Optional[str]:
        for name, value in scope.get('headers', []):
            if name == b'origin':
                return value.decode()
        return None

    def _cors_headers(self, origin: str) -> List[tuple]:
        headers = []

        # Allow origin
        if '*' in self.config.allow_origins:
            headers.append((b'access-control-allow-origin', b'*'))
        elif origin in self.config.allow_origins:
            headers.append((b'access-control-allow-origin', origin.encode()))

        # Credentials
        if self.config.allow_credentials:
            headers.append((b'access-control-allow-credentials', b'true'))

        # Expose headers
        if self.config.expose_headers:
            headers.append((
                b'access-control-expose-headers',
                ', '.join(self.config.expose_headers).encode()
            ))

        return headers

    async def _handle_preflight(self, send: Send, origin: str):
        headers = self._cors_headers(origin)

        # Add preflight-specific headers
        headers.extend([
            (b'access-control-allow-methods',
             ', '.join(self.config.allow_methods).encode()),
            (b'access-control-allow-headers',
             ', '.join(self.config.allow_headers).encode()),
            (b'access-control-max-age', str(self.config.max_age).encode()),
        ])

        await send({
            'type': 'http.response.start',
            'status': 204,
            'headers': headers,
        })
        await send({
            'type': 'http.response.body',
            'body': b'',
        })
```

### Compression Middleware

```python
import gzip
import zlib
from typing import Optional


class CompressionMiddleware:
    """Response compression middleware."""

    def __init__(self, app: ASGIApp, minimum_size: int = 500):
        self.app = app
        self.minimum_size = minimum_size

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        # Check Accept-Encoding
        encoding = self._get_encoding(scope)
        if not encoding:
            return await self.app(scope, receive, send)

        # Collect response
        response_started = False
        response_headers = []
        body_parts = []

        async def send_wrapper(message):
            nonlocal response_started, response_headers

            if message['type'] == 'http.response.start':
                response_started = True
                response_headers = list(message.get('headers', []))
                # Don't send yet - wait for body

            elif message['type'] == 'http.response.body':
                body = message.get('body', b'')
                body_parts.append(body)

                if not message.get('more_body', False):
                    # End of body - compress and send
                    full_body = b''.join(body_parts)
                    await self._send_compressed(
                        send, response_headers, full_body, encoding
                    )

        await self.app(scope, receive, send_wrapper)

    def _get_encoding(self, scope: Scope) -> Optional[str]:
        for name, value in scope.get('headers', []):
            if name == b'accept-encoding':
                encodings = value.decode().lower()
                if 'gzip' in encodings:
                    return 'gzip'
                if 'deflate' in encodings:
                    return 'deflate'
        return None

    async def _send_compressed(self, send: Send, headers: list,
                              body: bytes, encoding: str):
        # Skip if too small
        if len(body) < self.minimum_size:
            await self._send_uncompressed(send, headers, body)
            return

        # Skip if already compressed
        for name, value in headers:
            if name == b'content-encoding':
                await self._send_uncompressed(send, headers, body)
                return

        # Compress
        if encoding == 'gzip':
            compressed = gzip.compress(body)
        else:
            compressed = zlib.compress(body)

        # Update headers
        new_headers = [
            (name, value) for name, value in headers
            if name not in (b'content-length', b'content-encoding')
        ]
        new_headers.append((b'content-encoding', encoding.encode()))
        new_headers.append((b'content-length', str(len(compressed)).encode()))

        await send({
            'type': 'http.response.start',
            'status': 200,  # Preserve original status
            'headers': new_headers,
        })
        await send({
            'type': 'http.response.body',
            'body': compressed,
        })

    async def _send_uncompressed(self, send: Send, headers: list, body: bytes):
        await send({
            'type': 'http.response.start',
            'status': 200,
            'headers': headers,
        })
        await send({
            'type': 'http.response.body',
            'body': body,
        })
```

### Error Handling Middleware

```python
import json
import traceback


class ErrorHandlingMiddleware:
    """Global error handling middleware."""

    def __init__(self, app: ASGIApp, debug: bool = False):
        self.app = app
        self.debug = debug

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        try:
            await self.app(scope, receive, send)

        except HTTPException as e:
            await self._send_error(send, e.status_code, e.detail)

        except ValidationError as e:
            await self._send_error(send, 400, str(e))

        except Exception as e:
            logger.exception("Unhandled exception")

            if self.debug:
                detail = {
                    'error': str(e),
                    'traceback': traceback.format_exc()
                }
            else:
                detail = {'error': 'Internal Server Error'}

            await self._send_error(send, 500, detail)

    async def _send_error(self, send: Send, status: int, detail):
        body = json.dumps(detail if isinstance(detail, dict) else {'error': detail})

        await send({
            'type': 'http.response.start',
            'status': status,
            'headers': [(b'content-type', b'application/json')],
        })
        await send({
            'type': 'http.response.body',
            'body': body.encode(),
        })


class HTTPException(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail


class ValidationError(Exception):
    pass
```

---

## 22.4 Middleware Pipeline

### Pipeline Builder

```python
from typing import List, Callable, Type, Union


class MiddlewarePipeline:
    """Build and manage middleware pipeline."""

    def __init__(self):
        self._middlewares: List[tuple] = []

    def use(self, middleware: Union[Type, Callable], **kwargs):
        """Add middleware to pipeline."""
        self._middlewares.append((middleware, kwargs))
        return self

    def build(self, app: ASGIApp) -> ASGIApp:
        """Build the middleware stack."""
        # Apply in reverse order (first added = outermost)
        for middleware, kwargs in reversed(self._middlewares):
            if isinstance(middleware, type):
                app = middleware(app, **kwargs)
            else:
                app = middleware(app)
        return app


# Usage
pipeline = MiddlewarePipeline()
pipeline.use(ErrorHandlingMiddleware, debug=True)
pipeline.use(LoggingMiddleware)
pipeline.use(CORSMiddleware, config=CORSConfig(allow_origins=['*']))
pipeline.use(AuthenticationMiddleware, jwt_handler=jwt, exclude_paths=['/login'])
pipeline.use(CompressionMiddleware, minimum_size=1000)

app = pipeline.build(router)
```

### Conditional Middleware

```python
class ConditionalMiddleware:
    """Apply middleware only when condition is met."""

    def __init__(self, app: ASGIApp, middleware: ASGIApp,
                 condition: Callable[[Scope], bool]):
        self.app = app
        self.middleware = middleware(app)
        self.condition = condition

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if self.condition(scope):
            await self.middleware(scope, receive, send)
        else:
            await self.app(scope, receive, send)


# Usage
def is_api_request(scope: Scope) -> bool:
    return scope.get('path', '').startswith('/api')


app = ConditionalMiddleware(
    app,
    AuthenticationMiddleware,
    condition=is_api_request
)
```

### Path-Based Middleware

```python
import re
from typing import Pattern


class PathMiddleware:
    """Apply middleware to specific paths."""

    def __init__(self, app: ASGIApp):
        self.app = app
        self._path_middlewares: List[tuple[Pattern, ASGIApp]] = []

    def mount(self, path_pattern: str, middleware_cls, **kwargs):
        """Mount middleware for path pattern."""
        pattern = re.compile(path_pattern)
        wrapped = middleware_cls(self.app, **kwargs)
        self._path_middlewares.append((pattern, wrapped))
        return self

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        path = scope['path']
        for pattern, middleware in self._path_middlewares:
            if pattern.match(path):
                return await middleware(scope, receive, send)

        await self.app(scope, receive, send)


# Usage
app = PathMiddleware(router)
app.mount(r'^/api/.*', AuthenticationMiddleware, jwt_handler=jwt)
app.mount(r'^/admin/.*', AdminAuthMiddleware)
```

---

## 22.5 Middleware State Management

### Request State

```python
from typing import Any


class RequestState:
    """Mutable state attached to request scope."""

    def __init__(self):
        self._state: dict[str, Any] = {}

    def __setattr__(self, name: str, value: Any):
        if name.startswith('_'):
            super().__setattr__(name, value)
        else:
            self._state[name] = value

    def __getattr__(self, name: str) -> Any:
        try:
            return self._state[name]
        except KeyError:
            raise AttributeError(f"'{type(self).__name__}' has no attribute '{name}'")

    def __contains__(self, name: str) -> bool:
        return name in self._state


class StateMiddleware:
    """Initialize request state."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope['type'] == 'http':
            scope['state'] = RequestState()
        await self.app(scope, receive, send)


# Usage in other middleware
class UserMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope['type'] == 'http':
            # Add user to state
            scope['state'].user = await get_user(scope)
            scope['state'].request_id = generate_id()

        await self.app(scope, receive, send)


# Access in handler
async def handler(scope, receive, send):
    user = scope['state'].user
    request_id = scope['state'].request_id
    # ...
```

### Dependency Injection via Middleware

```python
class DependencyMiddleware:
    """Inject dependencies into request scope."""

    def __init__(self, app: ASGIApp, dependencies: dict):
        self.app = app
        self.dependencies = dependencies

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope['type'] == 'http':
            scope['dependencies'] = {}

            for name, factory in self.dependencies.items():
                if callable(factory):
                    scope['dependencies'][name] = await self._resolve(factory, scope)
                else:
                    scope['dependencies'][name] = factory

        try:
            await self.app(scope, receive, send)
        finally:
            # Cleanup
            for dep in scope.get('dependencies', {}).values():
                if hasattr(dep, 'close'):
                    if asyncio.iscoroutinefunction(dep.close):
                        await dep.close()
                    else:
                        dep.close()

    async def _resolve(self, factory, scope):
        if asyncio.iscoroutinefunction(factory):
            return await factory(scope)
        return factory(scope)


# Usage
async def get_db_session(scope):
    session = await db.acquire()
    return session


dependencies = {
    'db': get_db_session,
    'cache': redis_client,
}

app = DependencyMiddleware(router, dependencies)


# In handler
async def handler(scope, receive, send):
    db = scope['dependencies']['db']
    cache = scope['dependencies']['cache']
    # ...
```

---

## 22.6 Middleware Ordering

### Order Matters

```python
"""
Middleware order is crucial. Outer middleware executes first on request,
last on response.

Recommended order (outermost to innermost):
1. Error Handling - Catch all errors
2. Logging - Log all requests
3. CORS - Handle preflight early
4. Rate Limiting - Reject early if rate limited
5. Authentication - Identify user
6. Authorization - Check permissions
7. Validation - Validate request
8. Compression - Compress response (inner to run last)
"""


class Application:
    """Application with ordered middleware."""

    def __init__(self):
        self.middlewares = []

    def use(self, middleware, priority: int = 50):
        """Add middleware with priority (lower = outer)."""
        self.middlewares.append((priority, middleware))

    def build(self, app: ASGIApp) -> ASGIApp:
        # Sort by priority (lower first = applied last = outermost)
        sorted_middlewares = sorted(
            self.middlewares,
            key=lambda x: x[0],
            reverse=True
        )

        for _, middleware in sorted_middlewares:
            app = middleware(app)

        return app


# Predefined priorities
class Priority:
    ERROR_HANDLING = 10
    LOGGING = 20
    CORS = 30
    RATE_LIMITING = 40
    AUTHENTICATION = 50
    AUTHORIZATION = 60
    VALIDATION = 70
    COMPRESSION = 90


# Usage
app = Application()
app.use(CompressionMiddleware, Priority.COMPRESSION)
app.use(AuthenticationMiddleware, Priority.AUTHENTICATION)
app.use(LoggingMiddleware, Priority.LOGGING)
app.use(ErrorHandlingMiddleware, Priority.ERROR_HANDLING)
```

---

## 22.7 Advanced Middleware Patterns

### Before/After Hooks

```python
class HookMiddleware:
    """Middleware with before/after hooks."""

    def __init__(self, app: ASGIApp):
        self.app = app
        self._before_hooks: List[Callable] = []
        self._after_hooks: List[Callable] = []

    def before(self, hook: Callable):
        """Add before request hook."""
        self._before_hooks.append(hook)
        return hook

    def after(self, hook: Callable):
        """Add after request hook."""
        self._after_hooks.append(hook)
        return hook

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        # Run before hooks
        for hook in self._before_hooks:
            result = hook(scope) if not asyncio.iscoroutinefunction(hook) else await hook(scope)
            if result is False:
                return  # Short-circuit

        # Run app
        await self.app(scope, receive, send)

        # Run after hooks
        for hook in self._after_hooks:
            if asyncio.iscoroutinefunction(hook):
                await hook(scope)
            else:
                hook(scope)


# Usage
hooks = HookMiddleware(router)

@hooks.before
async def check_maintenance(scope):
    if is_maintenance_mode():
        return False  # Block request

@hooks.after
async def cleanup(scope):
    # Cleanup after request
    pass
```

### Retry Middleware

```python
class RetryMiddleware:
    """Retry failed requests."""

    def __init__(self, app: ASGIApp, max_retries: int = 3,
                 retry_codes: set = None):
        self.app = app
        self.max_retries = max_retries
        self.retry_codes = retry_codes or {502, 503, 504}

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        for attempt in range(self.max_retries):
            status_code = None
            response_parts = []

            async def capture_send(message):
                nonlocal status_code
                if message['type'] == 'http.response.start':
                    status_code = message['status']
                response_parts.append(message)

            try:
                await self.app(scope, receive, capture_send)

                if status_code not in self.retry_codes:
                    # Success - send captured response
                    for part in response_parts:
                        await send(part)
                    return

                # Retry
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    continue

            except Exception:
                if attempt >= self.max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)

        # Send last captured response
        for part in response_parts:
            await send(part)
```

### Response Caching Middleware

```python
import hashlib
from typing import Optional


class CacheMiddleware:
    """Cache GET responses."""

    def __init__(self, app: ASGIApp, cache, ttl: int = 60):
        self.app = app
        self.cache = cache
        self.ttl = ttl

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope['type'] != 'http' or scope['method'] != 'GET':
            return await self.app(scope, receive, send)

        # Check cache
        cache_key = self._make_key(scope)
        cached = await self.cache.get(cache_key)

        if cached:
            await self._send_cached(send, cached)
            return

        # Capture response
        response_parts = []

        async def capture_send(message):
            response_parts.append(message)
            await send(message)

        await self.app(scope, receive, capture_send)

        # Cache if successful
        if self._is_cacheable(response_parts):
            await self.cache.set(cache_key, response_parts, self.ttl)

    def _make_key(self, scope: Scope) -> str:
        path = scope['path']
        query = scope.get('query_string', b'').decode()
        return hashlib.md5(f"{path}?{query}".encode()).hexdigest()

    def _is_cacheable(self, parts: list) -> bool:
        for part in parts:
            if part['type'] == 'http.response.start':
                return 200 <= part['status'] < 300
        return False

    async def _send_cached(self, send: Send, parts: list):
        for part in parts:
            await send(part)
```

---

## 22.8 Testing Middleware

```python
import pytest
from unittest.mock import AsyncMock, MagicMock


class TestMiddleware:
    """Test utilities for middleware."""

    @staticmethod
    async def call_middleware(middleware_cls, scope: dict,
                             body: bytes = b'',
                             **middleware_kwargs) -> tuple[int, dict, bytes]:
        """Call middleware and return response."""
        response = {'status': None, 'headers': [], 'body': b''}

        async def receive():
            return {'type': 'http.request', 'body': body, 'more_body': False}

        async def send(message):
            if message['type'] == 'http.response.start':
                response['status'] = message['status']
                response['headers'] = dict(message.get('headers', []))
            elif message['type'] == 'http.response.body':
                response['body'] += message.get('body', b'')

        # Create dummy app
        async def app(scope, receive, send):
            await send({'type': 'http.response.start', 'status': 200, 'headers': []})
            await send({'type': 'http.response.body', 'body': b'OK'})

        middleware = middleware_cls(app, **middleware_kwargs)
        await middleware(scope, receive, send)

        return response['status'], response['headers'], response['body']


# Tests
@pytest.mark.asyncio
async def test_auth_middleware_missing_token():
    status, _, body = await TestMiddleware.call_middleware(
        AuthenticationMiddleware,
        {'type': 'http', 'method': 'GET', 'path': '/api/users', 'headers': []},
        jwt_handler=MagicMock()
    )

    assert status == 401
    assert b'Missing token' in body


@pytest.mark.asyncio
async def test_cors_preflight():
    status, headers, _ = await TestMiddleware.call_middleware(
        CORSMiddleware,
        {
            'type': 'http',
            'method': 'OPTIONS',
            'path': '/api/data',
            'headers': [(b'origin', b'http://example.com')]
        },
        config=CORSConfig(allow_origins=['http://example.com'])
    )

    assert status == 204
    assert b'access-control-allow-origin' in headers
```

---

## Exercises

### Exercise 22.1: Request ID Middleware

Create middleware that:
- Generates unique request ID
- Adds to response headers
- Makes ID available to handlers

### Exercise 22.2: Timeout Middleware

Create middleware that:
- Enforces request timeout
- Returns 504 on timeout
- Logs slow requests

### Exercise 22.3: Request Validation Middleware

Create middleware that:
- Validates Content-Type for POST/PUT
- Validates request body against schema
- Returns 400 with validation errors

---

## Summary

Middleware patterns:

1. **Onion model**: Request flows in, response flows out
2. **Composition**: Chain middlewares in order
3. **Common middleware**: Auth, CORS, logging, compression
4. **State management**: Attach data for later use
5. **Ordering**: Error handling outer, compression inner

---

## Next Module

**[Module 23: Dependency Injection →](./MODULE_23_DEPENDENCY_INJECTION.md)**

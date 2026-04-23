# Module 24: Request/Response Lifecycle

## Overview

Understanding the complete lifecycle of an HTTP request is essential for building robust web frameworks. This module traces a request from socket to response, covering parsing, routing, handling, and response generation with all the hooks and extension points in between.

---

## Learning Objectives

By the end of this module, you will be able to:

1. Trace complete request/response flow
2. Implement lifecycle hooks and events
3. Design extensible request processing pipelines
4. Handle request/response transformations
5. Build a complete request context system

---

## 24.1 Request Lifecycle Overview

### Complete Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Request Lifecycle                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Client ──▶ TCP ──▶ TLS ──▶ HTTP Parse ──▶ Middleware ──▶ Router ──▶ Handler│
│                                                                             │
│  1. Connection     2. Security    3. Protocol    4. Processing    5. Logic  │
│     Accept            Handshake      Parsing        Pipeline        Execute │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Handler ──▶ Response Build ──▶ Middleware ──▶ Serialize ──▶ Send ──▶ Client│
│                                                                             │
│  5. Logic    6. Response      7. Processing    8. Protocol   9. Connection  │
│     Return      Creation         Pipeline         Format        Write       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Lifecycle Phases

| Phase | Description | Hooks |
|-------|-------------|-------|
| Connection | TCP accept, TLS handshake | on_connect |
| Request Start | Headers received | on_request_start |
| Body Receive | Body streaming | on_body_chunk |
| Routing | Match handler | on_route_match |
| Before Handler | Pre-processing | before_request |
| Handler | Execute logic | - |
| After Handler | Post-processing | after_request |
| Response Start | Headers sent | on_response_start |
| Response Body | Body streaming | on_response_chunk |
| Completion | Request done | on_request_end |

---

## 24.2 Request Context

### Complete Request Context

```python
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, List, Callable
from datetime import datetime
import uuid
import time


@dataclass
class RequestContext:
    """Complete request context with lifecycle tracking."""

    # Request identification
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.utcnow)
    start_time: float = field(default_factory=time.perf_counter)

    # Connection info
    client_ip: str = ""
    client_port: int = 0
    server_ip: str = ""
    server_port: int = 0
    is_secure: bool = False

    # HTTP request
    method: str = ""
    path: str = ""
    query_string: str = ""
    http_version: str = "1.1"
    headers: Dict[str, str] = field(default_factory=dict)
    body: bytes = b""

    # Parsed data
    path_params: Dict[str, str] = field(default_factory=dict)
    query_params: Dict[str, str] = field(default_factory=dict)
    json_body: Optional[Any] = None
    form_data: Optional[Dict[str, Any]] = None

    # State
    state: Dict[str, Any] = field(default_factory=dict)
    user: Optional[Any] = None
    session: Optional[Dict[str, Any]] = None

    # Route info
    matched_route: Optional[str] = None
    handler: Optional[Callable] = None

    # Response tracking
    response_status: int = 0
    response_headers: Dict[str, str] = field(default_factory=dict)
    response_size: int = 0

    # Lifecycle
    phase: str = "created"
    errors: List[Exception] = field(default_factory=list)

    @property
    def elapsed_ms(self) -> float:
        """Time since request started."""
        return (time.perf_counter() - self.start_time) * 1000

    @property
    def url(self) -> str:
        """Full request URL."""
        scheme = "https" if self.is_secure else "http"
        host = self.headers.get("host", f"{self.server_ip}:{self.server_port}")
        query = f"?{self.query_string}" if self.query_string else ""
        return f"{scheme}://{host}{self.path}{query}"

    def set_phase(self, phase: str):
        """Update lifecycle phase."""
        self.phase = phase

    def add_error(self, error: Exception):
        """Track error."""
        self.errors.append(error)


class ContextManager:
    """Manage request context lifecycle."""

    def __init__(self):
        self._context_var: ContextVar[Optional[RequestContext]] = ContextVar(
            'request_context', default=None
        )

    @property
    def current(self) -> Optional[RequestContext]:
        return self._context_var.get()

    def create(self, **kwargs) -> RequestContext:
        """Create new context."""
        ctx = RequestContext(**kwargs)
        self._context_var.set(ctx)
        return ctx

    def clear(self):
        """Clear current context."""
        self._context_var.set(None)

    @contextmanager
    def scope(self, **kwargs):
        """Context manager for request scope."""
        ctx = self.create(**kwargs)
        try:
            yield ctx
        finally:
            self.clear()


# Global context manager
context = ContextManager()


def get_request_context() -> RequestContext:
    """Get current request context."""
    ctx = context.current
    if not ctx:
        raise RuntimeError("No active request context")
    return ctx
```

---

## 24.3 Lifecycle Hooks System

### Hook Registry

```python
from typing import Callable, List, Awaitable
from enum import Enum
from dataclasses import dataclass


class HookType(Enum):
    ON_STARTUP = "on_startup"
    ON_SHUTDOWN = "on_shutdown"
    ON_CONNECT = "on_connect"
    ON_REQUEST_START = "on_request_start"
    ON_BODY_RECEIVED = "on_body_received"
    BEFORE_ROUTE = "before_route"
    AFTER_ROUTE = "after_route"
    BEFORE_HANDLER = "before_handler"
    AFTER_HANDLER = "after_handler"
    ON_RESPONSE_START = "on_response_start"
    ON_RESPONSE_BODY = "on_response_body"
    ON_REQUEST_END = "on_request_end"
    ON_ERROR = "on_error"


@dataclass
class Hook:
    hook_type: HookType
    callback: Callable
    priority: int = 50


class HookRegistry:
    """Registry for lifecycle hooks."""

    def __init__(self):
        self._hooks: Dict[HookType, List[Hook]] = {
            hook_type: [] for hook_type in HookType
        }

    def register(self, hook_type: HookType, callback: Callable,
                 priority: int = 50):
        """Register a hook."""
        hook = Hook(hook_type, callback, priority)
        self._hooks[hook_type].append(hook)
        # Sort by priority
        self._hooks[hook_type].sort(key=lambda h: h.priority)

    def on(self, hook_type: HookType, priority: int = 50):
        """Decorator to register hook."""
        def decorator(func: Callable):
            self.register(hook_type, func, priority)
            return func
        return decorator

    async def execute(self, hook_type: HookType, *args, **kwargs):
        """Execute all hooks of a type."""
        for hook in self._hooks[hook_type]:
            try:
                result = hook.callback(*args, **kwargs)
                if asyncio.iscoroutine(result):
                    await result
            except StopPropagation:
                break
            except Exception as e:
                if hook_type != HookType.ON_ERROR:
                    await self.execute(HookType.ON_ERROR, e, *args, **kwargs)


class StopPropagation(Exception):
    """Raised to stop hook propagation."""
    pass


# Global hooks
hooks = HookRegistry()


# Decorator shortcuts
def on_startup(func):
    return hooks.on(HookType.ON_STARTUP)(func)

def on_shutdown(func):
    return hooks.on(HookType.ON_SHUTDOWN)(func)

def before_request(func):
    return hooks.on(HookType.BEFORE_HANDLER)(func)

def after_request(func):
    return hooks.on(HookType.AFTER_HANDLER)(func)

def on_error(func):
    return hooks.on(HookType.ON_ERROR)(func)
```

### Using Hooks

```python
@on_startup
async def initialize_database():
    """Initialize database on startup."""
    await db.connect()
    print("Database connected")


@on_shutdown
async def cleanup_database():
    """Cleanup on shutdown."""
    await db.close()
    print("Database disconnected")


@before_request
async def authenticate_request(ctx: RequestContext):
    """Authenticate before handling."""
    token = ctx.headers.get("authorization", "").replace("Bearer ", "")
    if token:
        ctx.user = await validate_token(token)


@after_request
async def log_request(ctx: RequestContext):
    """Log after handling."""
    logger.info(
        f"{ctx.method} {ctx.path} - {ctx.response_status} "
        f"- {ctx.elapsed_ms:.2f}ms"
    )


@on_error
async def handle_error(error: Exception, ctx: RequestContext):
    """Handle errors."""
    ctx.add_error(error)
    logger.exception(f"Error processing {ctx.path}")
```

---

## 24.4 Request Processing Pipeline

### Pipeline Implementation

```python
from typing import Callable, Awaitable, List, Optional
from abc import ABC, abstractmethod


class PipelineStep(ABC):
    """Abstract pipeline step."""

    @abstractmethod
    async def process(self, ctx: RequestContext,
                     next_step: Callable) -> Optional['Response']:
        """Process request and optionally call next step."""
        pass


class Pipeline:
    """Request processing pipeline."""

    def __init__(self):
        self._steps: List[PipelineStep] = []

    def add(self, step: PipelineStep) -> 'Pipeline':
        """Add step to pipeline."""
        self._steps.append(step)
        return self

    async def execute(self, ctx: RequestContext,
                     handler: Callable) -> 'Response':
        """Execute pipeline."""
        async def run_step(index: int) -> 'Response':
            if index >= len(self._steps):
                # End of pipeline - call handler
                return await handler(ctx)

            step = self._steps[index]
            return await step.process(
                ctx,
                lambda: run_step(index + 1)
            )

        return await run_step(0)


# Pipeline steps
class LoggingStep(PipelineStep):
    """Log requests."""

    async def process(self, ctx: RequestContext, next_step: Callable):
        logger.info(f"→ {ctx.method} {ctx.path}")
        start = time.perf_counter()

        response = await next_step()

        elapsed = (time.perf_counter() - start) * 1000
        logger.info(f"← {ctx.response_status} - {elapsed:.2f}ms")

        return response


class AuthenticationStep(PipelineStep):
    """Authenticate requests."""

    def __init__(self, auth_service):
        self.auth_service = auth_service

    async def process(self, ctx: RequestContext, next_step: Callable):
        token = ctx.headers.get("authorization", "").replace("Bearer ", "")

        if token:
            ctx.user = await self.auth_service.validate(token)

        return await next_step()


class RateLimitStep(PipelineStep):
    """Rate limit requests."""

    def __init__(self, limiter):
        self.limiter = limiter

    async def process(self, ctx: RequestContext, next_step: Callable):
        key = ctx.client_ip

        if not await self.limiter.is_allowed(key):
            return Response.json(
                {"error": "Rate limit exceeded"},
                status=429
            )

        return await next_step()


class ValidationStep(PipelineStep):
    """Validate request data."""

    async def process(self, ctx: RequestContext, next_step: Callable):
        # Parse JSON body if present
        if ctx.headers.get("content-type") == "application/json":
            try:
                ctx.json_body = json.loads(ctx.body)
            except json.JSONDecodeError:
                return Response.json(
                    {"error": "Invalid JSON"},
                    status=400
                )

        return await next_step()


class ErrorHandlingStep(PipelineStep):
    """Handle errors."""

    def __init__(self, debug: bool = False):
        self.debug = debug

    async def process(self, ctx: RequestContext, next_step: Callable):
        try:
            return await next_step()

        except HTTPException as e:
            return Response.json(
                {"error": e.detail},
                status=e.status_code
            )

        except ValidationError as e:
            return Response.json(
                {"error": str(e), "details": e.details},
                status=400
            )

        except Exception as e:
            ctx.add_error(e)
            logger.exception("Unhandled error")

            if self.debug:
                return Response.json(
                    {"error": str(e), "traceback": traceback.format_exc()},
                    status=500
                )
            return Response.json(
                {"error": "Internal Server Error"},
                status=500
            )


# Build pipeline
pipeline = Pipeline()
pipeline.add(ErrorHandlingStep(debug=True))
pipeline.add(LoggingStep())
pipeline.add(RateLimitStep(rate_limiter))
pipeline.add(AuthenticationStep(auth_service))
pipeline.add(ValidationStep())
```

---

## 24.5 Request Parsing

### Complete Request Parser

```python
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
from urllib.parse import parse_qs, unquote
import json


@dataclass
class ParsedRequest:
    """Fully parsed HTTP request."""
    method: str
    path: str
    query_string: str
    query_params: Dict[str, List[str]]
    http_version: str
    headers: Dict[str, str]
    body: bytes
    content_type: Optional[str]
    content_length: int


class RequestParser:
    """HTTP request parser with streaming support."""

    def __init__(self, max_headers: int = 100,
                 max_header_size: int = 8192,
                 max_body_size: int = 10 * 1024 * 1024):
        self.max_headers = max_headers
        self.max_header_size = max_header_size
        self.max_body_size = max_body_size

    async def parse(self, reader: asyncio.StreamReader) -> ParsedRequest:
        """Parse complete request."""
        # Parse request line
        line = await self._read_line(reader)
        method, path, version = self._parse_request_line(line)

        # Parse path and query
        path, query_string = self._parse_path(path)
        query_params = parse_qs(query_string)

        # Parse headers
        headers = await self._parse_headers(reader)

        # Parse body
        body = await self._parse_body(reader, headers)

        return ParsedRequest(
            method=method,
            path=path,
            query_string=query_string,
            query_params=query_params,
            http_version=version,
            headers=headers,
            body=body,
            content_type=headers.get('content-type'),
            content_length=len(body)
        )

    async def _read_line(self, reader: asyncio.StreamReader) -> str:
        """Read line with size limit."""
        line = await reader.readline()
        if len(line) > self.max_header_size:
            raise RequestTooLarge("Header line too long")
        return line.decode('latin-1').rstrip('\r\n')

    def _parse_request_line(self, line: str) -> Tuple[str, str, str]:
        """Parse request line."""
        parts = line.split(' ')
        if len(parts) != 3:
            raise BadRequest("Invalid request line")

        method, path, version = parts
        if not version.startswith('HTTP/'):
            raise BadRequest("Invalid HTTP version")

        return method, path, version[5:]

    def _parse_path(self, path: str) -> Tuple[str, str]:
        """Split path and query string."""
        if '?' in path:
            path, query = path.split('?', 1)
            return unquote(path), query
        return unquote(path), ''

    async def _parse_headers(self, reader: asyncio.StreamReader) -> Dict[str, str]:
        """Parse headers."""
        headers = {}
        count = 0

        while True:
            line = await self._read_line(reader)
            if not line:
                break

            count += 1
            if count > self.max_headers:
                raise RequestTooLarge("Too many headers")

            if ':' not in line:
                raise BadRequest("Invalid header")

            name, value = line.split(':', 1)
            headers[name.lower().strip()] = value.strip()

        return headers

    async def _parse_body(self, reader: asyncio.StreamReader,
                         headers: Dict[str, str]) -> bytes:
        """Parse request body."""
        # Check content-length
        content_length = headers.get('content-length')
        if content_length:
            length = int(content_length)
            if length > self.max_body_size:
                raise RequestTooLarge("Body too large")
            return await reader.readexactly(length)

        # Check chunked encoding
        if headers.get('transfer-encoding', '').lower() == 'chunked':
            return await self._parse_chunked(reader)

        return b''

    async def _parse_chunked(self, reader: asyncio.StreamReader) -> bytes:
        """Parse chunked body."""
        body = bytearray()

        while True:
            # Read chunk size
            line = await self._read_line(reader)
            chunk_size = int(line, 16)

            if chunk_size == 0:
                break

            if len(body) + chunk_size > self.max_body_size:
                raise RequestTooLarge("Body too large")

            # Read chunk data
            chunk = await reader.readexactly(chunk_size)
            body.extend(chunk)

            # Read trailing CRLF
            await reader.readline()

        return bytes(body)


class BadRequest(Exception):
    pass


class RequestTooLarge(Exception):
    pass
```

---

## 24.6 Response Building

### Response Builder

```python
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Iterator, AsyncIterator
import json


@dataclass
class Response:
    """HTTP response with builder pattern."""
    status: int = 200
    headers: Dict[str, str] = field(default_factory=dict)
    body: bytes = b""
    _stream: Optional[AsyncIterator[bytes]] = None

    # Builder methods
    def with_status(self, status: int) -> 'Response':
        self.status = status
        return self

    def with_header(self, name: str, value: str) -> 'Response':
        self.headers[name] = value
        return self

    def with_headers(self, headers: Dict[str, str]) -> 'Response':
        self.headers.update(headers)
        return self

    def with_body(self, body: bytes | str) -> 'Response':
        if isinstance(body, str):
            body = body.encode('utf-8')
        self.body = body
        self.headers['content-length'] = str(len(body))
        return self

    def with_stream(self, stream: AsyncIterator[bytes]) -> 'Response':
        self._stream = stream
        return self

    # Factory methods
    @classmethod
    def json(cls, data: Any, status: int = 200, **kwargs) -> 'Response':
        body = json.dumps(data, **kwargs).encode('utf-8')
        return cls(
            status=status,
            headers={
                'content-type': 'application/json',
                'content-length': str(len(body))
            },
            body=body
        )

    @classmethod
    def html(cls, content: str, status: int = 200) -> 'Response':
        body = content.encode('utf-8')
        return cls(
            status=status,
            headers={
                'content-type': 'text/html; charset=utf-8',
                'content-length': str(len(body))
            },
            body=body
        )

    @classmethod
    def text(cls, content: str, status: int = 200) -> 'Response':
        body = content.encode('utf-8')
        return cls(
            status=status,
            headers={
                'content-type': 'text/plain; charset=utf-8',
                'content-length': str(len(body))
            },
            body=body
        )

    @classmethod
    def redirect(cls, location: str, permanent: bool = False) -> 'Response':
        return cls(
            status=301 if permanent else 302,
            headers={'location': location}
        )

    @classmethod
    def file(cls, path: str, content_type: str = None,
             filename: str = None) -> 'Response':
        """Stream file response."""
        import aiofiles
        import os
        import mimetypes

        if not content_type:
            content_type = mimetypes.guess_type(path)[0] or 'application/octet-stream'

        async def stream_file():
            async with aiofiles.open(path, 'rb') as f:
                while chunk := await f.read(65536):
                    yield chunk

        headers = {'content-type': content_type}

        if filename:
            headers['content-disposition'] = f'attachment; filename="{filename}"'

        # Get file size
        try:
            size = os.path.getsize(path)
            headers['content-length'] = str(size)
        except OSError:
            pass

        return cls(headers=headers)._with_stream(stream_file())

    @classmethod
    def stream(cls, generator: AsyncIterator[bytes],
               content_type: str = 'application/octet-stream') -> 'Response':
        """Create streaming response."""
        return cls(
            headers={
                'content-type': content_type,
                'transfer-encoding': 'chunked'
            }
        ).with_stream(generator)

    # ASGI sending
    async def send(self, scope: dict, receive: Callable, send: Callable):
        """Send response via ASGI."""
        # Send headers
        await send({
            'type': 'http.response.start',
            'status': self.status,
            'headers': [
                (k.lower().encode(), v.encode())
                for k, v in self.headers.items()
            ]
        })

        # Send body
        if self._stream:
            async for chunk in self._stream:
                await send({
                    'type': 'http.response.body',
                    'body': chunk,
                    'more_body': True
                })
            await send({
                'type': 'http.response.body',
                'body': b'',
                'more_body': False
            })
        else:
            await send({
                'type': 'http.response.body',
                'body': self.body,
                'more_body': False
            })


class ResponseBuilder:
    """Fluent response builder."""

    def __init__(self):
        self._status = 200
        self._headers: Dict[str, str] = {}
        self._cookies: List[str] = []
        self._body: Optional[bytes] = None
        self._stream: Optional[AsyncIterator[bytes]] = None

    def status(self, code: int) -> 'ResponseBuilder':
        self._status = code
        return self

    def header(self, name: str, value: str) -> 'ResponseBuilder':
        self._headers[name] = value
        return self

    def cookie(self, name: str, value: str, **options) -> 'ResponseBuilder':
        parts = [f"{name}={value}"]
        if 'max_age' in options:
            parts.append(f"Max-Age={options['max_age']}")
        if 'path' in options:
            parts.append(f"Path={options['path']}")
        if options.get('secure'):
            parts.append("Secure")
        if options.get('httponly'):
            parts.append("HttpOnly")
        if 'samesite' in options:
            parts.append(f"SameSite={options['samesite']}")

        self._cookies.append("; ".join(parts))
        return self

    def json(self, data: Any) -> 'ResponseBuilder':
        self._body = json.dumps(data).encode()
        self._headers['content-type'] = 'application/json'
        return self

    def html(self, content: str) -> 'ResponseBuilder':
        self._body = content.encode()
        self._headers['content-type'] = 'text/html; charset=utf-8'
        return self

    def stream(self, generator: AsyncIterator[bytes]) -> 'ResponseBuilder':
        self._stream = generator
        self._headers['transfer-encoding'] = 'chunked'
        return self

    def build(self) -> Response:
        headers = self._headers.copy()

        for cookie in self._cookies:
            # Multiple Set-Cookie headers need special handling
            pass

        if self._body:
            headers['content-length'] = str(len(self._body))

        return Response(
            status=self._status,
            headers=headers,
            body=self._body or b'',
            _stream=self._stream
        )
```

---

## 24.7 Complete Request Handler

### Application Class

```python
class Application:
    """Complete web application with lifecycle management."""

    def __init__(self):
        self.router = Router()
        self.hooks = HookRegistry()
        self.pipeline = Pipeline()
        self.middleware: List[Callable] = []
        self.context_manager = ContextManager()

        # Setup default pipeline
        self._setup_default_pipeline()

    def _setup_default_pipeline(self):
        """Setup default processing pipeline."""
        self.pipeline.add(ErrorHandlingStep())
        self.pipeline.add(LoggingStep())

    # Route decorators
    def get(self, path: str):
        return self.router.route('GET', path)

    def post(self, path: str):
        return self.router.route('POST', path)

    def put(self, path: str):
        return self.router.route('PUT', path)

    def delete(self, path: str):
        return self.router.route('DELETE', path)

    # Hook decorators
    def on_startup(self, func):
        self.hooks.register(HookType.ON_STARTUP, func)
        return func

    def on_shutdown(self, func):
        self.hooks.register(HookType.ON_SHUTDOWN, func)
        return func

    def before_request(self, func):
        self.hooks.register(HookType.BEFORE_HANDLER, func)
        return func

    def after_request(self, func):
        self.hooks.register(HookType.AFTER_HANDLER, func)
        return func

    # Middleware
    def use(self, middleware: Callable):
        """Add middleware."""
        self.middleware.append(middleware)
        return self

    # ASGI interface
    async def __call__(self, scope: dict, receive: Callable, send: Callable):
        """ASGI application entry point."""
        if scope['type'] == 'lifespan':
            await self._handle_lifespan(scope, receive, send)
        elif scope['type'] == 'http':
            await self._handle_http(scope, receive, send)

    async def _handle_lifespan(self, scope, receive, send):
        """Handle lifespan events."""
        while True:
            message = await receive()

            if message['type'] == 'lifespan.startup':
                try:
                    await self.hooks.execute(HookType.ON_STARTUP)
                    await send({'type': 'lifespan.startup.complete'})
                except Exception as e:
                    await send({
                        'type': 'lifespan.startup.failed',
                        'message': str(e)
                    })

            elif message['type'] == 'lifespan.shutdown':
                try:
                    await self.hooks.execute(HookType.ON_SHUTDOWN)
                    await send({'type': 'lifespan.shutdown.complete'})
                except Exception:
                    await send({'type': 'lifespan.shutdown.complete'})
                return

    async def _handle_http(self, scope, receive, send):
        """Handle HTTP request."""
        # Create request context
        ctx = self._create_context(scope)

        try:
            # Execute hooks: request start
            ctx.set_phase("request_start")
            await self.hooks.execute(HookType.ON_REQUEST_START, ctx)

            # Read body
            ctx.set_phase("body_receive")
            ctx.body = await self._read_body(receive)
            await self.hooks.execute(HookType.ON_BODY_RECEIVED, ctx)

            # Route matching
            ctx.set_phase("routing")
            await self.hooks.execute(HookType.BEFORE_ROUTE, ctx)
            handler, path_params = self.router.match(ctx.method, ctx.path)
            ctx.path_params = path_params
            ctx.handler = handler
            await self.hooks.execute(HookType.AFTER_ROUTE, ctx)

            if not handler:
                response = Response.json({"error": "Not Found"}, status=404)
            else:
                # Execute pipeline with handler
                ctx.set_phase("handler")
                await self.hooks.execute(HookType.BEFORE_HANDLER, ctx)

                response = await self.pipeline.execute(ctx, handler)

                await self.hooks.execute(HookType.AFTER_HANDLER, ctx)

            # Send response
            ctx.set_phase("response")
            ctx.response_status = response.status
            await self.hooks.execute(HookType.ON_RESPONSE_START, ctx)

            await response.send(scope, receive, send)

            ctx.response_size = len(response.body)
            await self.hooks.execute(HookType.ON_RESPONSE_BODY, ctx)

        except Exception as e:
            ctx.add_error(e)
            await self.hooks.execute(HookType.ON_ERROR, e, ctx)

            error_response = Response.json(
                {"error": "Internal Server Error"},
                status=500
            )
            await error_response.send(scope, receive, send)

        finally:
            ctx.set_phase("complete")
            await self.hooks.execute(HookType.ON_REQUEST_END, ctx)

    def _create_context(self, scope: dict) -> RequestContext:
        """Create request context from ASGI scope."""
        client = scope.get('client', ('', 0))
        server = scope.get('server', ('', 0))

        headers = {}
        for name, value in scope.get('headers', []):
            headers[name.decode()] = value.decode()

        return self.context_manager.create(
            method=scope.get('method', 'GET'),
            path=scope.get('path', '/'),
            query_string=scope.get('query_string', b'').decode(),
            http_version=scope.get('http_version', '1.1'),
            headers=headers,
            client_ip=client[0],
            client_port=client[1],
            server_ip=server[0],
            server_port=server[1],
            is_secure=scope.get('scheme') == 'https'
        )

    async def _read_body(self, receive: Callable) -> bytes:
        """Read request body."""
        body = bytearray()

        while True:
            message = await receive()
            body.extend(message.get('body', b''))

            if not message.get('more_body', False):
                break

        return bytes(body)
```

---

## 24.8 Request/Response Transforms

### Request Transforms

```python
class RequestTransform:
    """Transform request before handling."""

    async def transform(self, ctx: RequestContext) -> RequestContext:
        return ctx


class JSONBodyTransform(RequestTransform):
    """Parse JSON body."""

    async def transform(self, ctx: RequestContext) -> RequestContext:
        content_type = ctx.headers.get('content-type', '')

        if 'application/json' in content_type and ctx.body:
            try:
                ctx.json_body = json.loads(ctx.body)
            except json.JSONDecodeError as e:
                raise BadRequest(f"Invalid JSON: {e}")

        return ctx


class FormDataTransform(RequestTransform):
    """Parse form data."""

    async def transform(self, ctx: RequestContext) -> RequestContext:
        content_type = ctx.headers.get('content-type', '')

        if 'application/x-www-form-urlencoded' in content_type:
            ctx.form_data = parse_qs(ctx.body.decode())

        elif 'multipart/form-data' in content_type:
            ctx.form_data = await self._parse_multipart(ctx)

        return ctx

    async def _parse_multipart(self, ctx: RequestContext) -> dict:
        # Multipart parsing implementation
        pass


class QueryParamsTransform(RequestTransform):
    """Parse query parameters."""

    async def transform(self, ctx: RequestContext) -> RequestContext:
        if ctx.query_string:
            ctx.query_params = parse_qs(ctx.query_string)
        return ctx
```

### Response Transforms

```python
class ResponseTransform:
    """Transform response before sending."""

    async def transform(self, response: Response,
                       ctx: RequestContext) -> Response:
        return response


class CompressionTransform(ResponseTransform):
    """Compress response body."""

    def __init__(self, min_size: int = 500):
        self.min_size = min_size

    async def transform(self, response: Response,
                       ctx: RequestContext) -> Response:
        # Check if client accepts compression
        accept = ctx.headers.get('accept-encoding', '')
        if 'gzip' not in accept:
            return response

        # Check size
        if len(response.body) < self.min_size:
            return response

        # Compress
        import gzip
        compressed = gzip.compress(response.body)

        return Response(
            status=response.status,
            headers={
                **response.headers,
                'content-encoding': 'gzip',
                'content-length': str(len(compressed))
            },
            body=compressed
        )


class SecurityHeadersTransform(ResponseTransform):
    """Add security headers."""

    async def transform(self, response: Response,
                       ctx: RequestContext) -> Response:
        security_headers = {
            'x-content-type-options': 'nosniff',
            'x-frame-options': 'DENY',
            'x-xss-protection': '1; mode=block',
        }

        return Response(
            status=response.status,
            headers={**response.headers, **security_headers},
            body=response.body
        )
```

---

## Exercises

### Exercise 24.1: Custom Lifecycle Hook

Implement a hook that:
- Tracks request timing
- Stores in context
- Logs slow requests (>1s)

### Exercise 24.2: Request Validation Pipeline

Create a validation pipeline step that:
- Validates request body against schema
- Returns 400 on validation errors
- Attaches validated data to context

### Exercise 24.3: Response Caching Transform

Implement response caching that:
- Caches GET responses
- Uses ETag headers
- Returns 304 for unchanged content

---

## Summary

Request/Response lifecycle fundamentals:

1. **Context**: Complete request state tracking
2. **Hooks**: Extension points throughout lifecycle
3. **Pipeline**: Composable processing steps
4. **Parsing**: Request data extraction
5. **Building**: Response construction
6. **Transforms**: Request/response modification

---

## Next Module

**[Module 25: Advanced Framework Features →](./MODULE_25_ADVANCED_FEATURES.md)**

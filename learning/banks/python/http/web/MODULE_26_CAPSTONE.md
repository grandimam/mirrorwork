# Module 26: Capstone - Build a Production Web Framework

## Overview

This capstone project brings together everything you've learned to build a complete, production-ready web framework from scratch. You'll implement core features, advanced functionality, and production infrastructure—proving deep understanding of web server internals.

---

## Project Goals

By completing this capstone, you will:

1. Build a complete async web framework
2. Implement ASGI server and application
3. Create routing, middleware, and DI systems
4. Add security, performance, and observability
5. Package and document for distribution

---

## Phase 1: Core Server

### 1.1 ASGI Server Implementation

Build a minimal but functional ASGI server.

```python
"""
File: swiftapi/server.py
ASGI 3.0 compliant server implementation.
"""

import asyncio
import logging
from typing import Callable, Optional
import socket

logger = logging.getLogger(__name__)


class ASGIServer:
    """
    Production ASGI server with:
    - HTTP/1.1 support
    - Keep-alive connections
    - Graceful shutdown
    - Configurable workers
    """

    def __init__(
        self,
        app: Callable,
        host: str = "127.0.0.1",
        port: int = 8000,
        workers: int = 1,
        backlog: int = 128,
        timeout_keep_alive: int = 5,
    ):
        self.app = app
        self.host = host
        self.port = port
        self.workers = workers
        self.backlog = backlog
        self.timeout_keep_alive = timeout_keep_alive
        self._server: Optional[asyncio.Server] = None
        self._shutdown_event = asyncio.Event()

    async def serve(self):
        """Start serving requests."""
        # Create server socket
        sock = self._create_socket()

        # Start server
        self._server = await asyncio.start_server(
            self._handle_connection,
            sock=sock,
            backlog=self.backlog,
        )

        logger.info(f"Server started on http://{self.host}:{self.port}")

        async with self._server:
            await self._shutdown_event.wait()

    async def shutdown(self):
        """Graceful shutdown."""
        logger.info("Shutting down...")
        self._shutdown_event.set()

        if self._server:
            self._server.close()
            await self._server.wait_closed()

    def _create_socket(self) -> socket.socket:
        """Create and configure server socket."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        if hasattr(socket, 'SO_REUSEPORT'):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)

        sock.bind((self.host, self.port))
        sock.setblocking(False)
        return sock

    async def _handle_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter
    ):
        """Handle a single connection."""
        try:
            while True:
                # Parse HTTP request
                request = await self._read_request(reader)
                if not request:
                    break

                # Build ASGI scope
                scope = self._build_scope(request, writer)

                # Create receive/send callables
                body_received = False
                body = request.get('body', b'')

                async def receive():
                    nonlocal body_received
                    if not body_received:
                        body_received = True
                        return {
                            'type': 'http.request',
                            'body': body,
                            'more_body': False
                        }
                    await asyncio.sleep(3600)
                    return {'type': 'http.disconnect'}

                async def send(message):
                    await self._send_response(writer, message)

                # Call ASGI app
                await self.app(scope, receive, send)

                # Check keep-alive
                if not self._should_keep_alive(request):
                    break

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.exception(f"Connection error: {e}")
        finally:
            writer.close()
            await writer.wait_closed()

    async def _read_request(self, reader: asyncio.StreamReader) -> Optional[dict]:
        """Read and parse HTTP request."""
        try:
            # Read request line
            line = await asyncio.wait_for(
                reader.readline(),
                timeout=self.timeout_keep_alive
            )
            if not line:
                return None

            method, path, version = line.decode().strip().split(' ')

            # Read headers
            headers = []
            content_length = 0

            while True:
                line = await reader.readline()
                if line == b'\r\n':
                    break

                name, value = line.decode().strip().split(':', 1)
                name = name.lower().strip()
                value = value.strip()
                headers.append((name.encode(), value.encode()))

                if name == 'content-length':
                    content_length = int(value)

            # Read body
            body = b''
            if content_length > 0:
                body = await reader.readexactly(content_length)

            # Parse path and query
            if '?' in path:
                path, query_string = path.split('?', 1)
            else:
                query_string = ''

            return {
                'method': method,
                'path': path,
                'query_string': query_string,
                'http_version': version.split('/')[1],
                'headers': headers,
                'body': body,
            }

        except asyncio.TimeoutError:
            return None
        except Exception:
            return None

    def _build_scope(self, request: dict, writer) -> dict:
        """Build ASGI scope from parsed request."""
        peername = writer.get_extra_info('peername')

        return {
            'type': 'http',
            'asgi': {'version': '3.0', 'spec_version': '2.3'},
            'http_version': request['http_version'],
            'method': request['method'],
            'scheme': 'http',
            'path': request['path'],
            'query_string': request['query_string'].encode(),
            'root_path': '',
            'headers': request['headers'],
            'server': (self.host, self.port),
            'client': peername,
        }

    async def _send_response(self, writer, message: dict):
        """Send ASGI response message."""
        if message['type'] == 'http.response.start':
            status = message['status']
            headers = message.get('headers', [])

            # Status line
            response = f"HTTP/1.1 {status} {self._status_phrase(status)}\r\n"

            # Headers
            for name, value in headers:
                if isinstance(name, bytes):
                    name = name.decode()
                if isinstance(value, bytes):
                    value = value.decode()
                response += f"{name}: {value}\r\n"

            response += "\r\n"
            writer.write(response.encode())

        elif message['type'] == 'http.response.body':
            body = message.get('body', b'')
            if body:
                writer.write(body)

            if not message.get('more_body', False):
                await writer.drain()

    def _status_phrase(self, status: int) -> str:
        """Get HTTP status phrase."""
        phrases = {
            200: 'OK', 201: 'Created', 204: 'No Content',
            301: 'Moved Permanently', 302: 'Found', 304: 'Not Modified',
            400: 'Bad Request', 401: 'Unauthorized', 403: 'Forbidden',
            404: 'Not Found', 405: 'Method Not Allowed',
            500: 'Internal Server Error', 502: 'Bad Gateway',
            503: 'Service Unavailable',
        }
        return phrases.get(status, 'Unknown')

    def _should_keep_alive(self, request: dict) -> bool:
        """Check if connection should be kept alive."""
        for name, value in request['headers']:
            if name == b'connection':
                return value.lower() == b'keep-alive'
        return request['http_version'] >= '1.1'


def run(app: Callable, host: str = "127.0.0.1", port: int = 8000, **kwargs):
    """Run ASGI application."""
    server = ASGIServer(app, host, port, **kwargs)
    asyncio.run(server.serve())
```

### 1.2 Request/Response Objects

```python
"""
File: swiftapi/requests.py
Request and Response objects.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, AsyncIterator
from urllib.parse import parse_qs
import json


@dataclass
class Request:
    """HTTP Request object."""

    scope: dict
    _receive: Any
    _body: Optional[bytes] = None
    _json: Optional[Any] = None
    _form: Optional[dict] = None

    @property
    def method(self) -> str:
        return self.scope['method']

    @property
    def path(self) -> str:
        return self.scope['path']

    @property
    def query_params(self) -> dict:
        qs = self.scope.get('query_string', b'').decode()
        return parse_qs(qs)

    @property
    def headers(self) -> dict:
        return {
            k.decode(): v.decode()
            for k, v in self.scope.get('headers', [])
        }

    @property
    def path_params(self) -> dict:
        return self.scope.get('path_params', {})

    @property
    def client(self) -> tuple:
        return self.scope.get('client', ('', 0))

    async def body(self) -> bytes:
        if self._body is None:
            chunks = []
            while True:
                message = await self._receive()
                chunks.append(message.get('body', b''))
                if not message.get('more_body', False):
                    break
            self._body = b''.join(chunks)
        return self._body

    async def json(self) -> Any:
        if self._json is None:
            body = await self.body()
            self._json = json.loads(body)
        return self._json

    async def form(self) -> dict:
        if self._form is None:
            body = await self.body()
            content_type = self.headers.get('content-type', '')

            if 'application/x-www-form-urlencoded' in content_type:
                self._form = parse_qs(body.decode())
            else:
                self._form = {}
        return self._form


class Response:
    """HTTP Response object."""

    def __init__(
        self,
        content: Any = None,
        status_code: int = 200,
        headers: dict = None,
        media_type: str = None,
    ):
        self.status_code = status_code
        self.headers = headers or {}
        self.media_type = media_type
        self.body = self._encode_content(content)

        if self.media_type:
            self.headers['content-type'] = self.media_type
        if self.body:
            self.headers['content-length'] = str(len(self.body))

    def _encode_content(self, content: Any) -> bytes:
        if content is None:
            return b''
        if isinstance(content, bytes):
            return content
        if isinstance(content, str):
            return content.encode('utf-8')
        return str(content).encode('utf-8')

    async def __call__(self, scope, receive, send):
        """ASGI interface."""
        await send({
            'type': 'http.response.start',
            'status': self.status_code,
            'headers': [
                (k.lower().encode(), v.encode())
                for k, v in self.headers.items()
            ],
        })
        await send({
            'type': 'http.response.body',
            'body': self.body,
        })


class JSONResponse(Response):
    """JSON response."""

    def __init__(self, content: Any, status_code: int = 200, **kwargs):
        super().__init__(
            content=json.dumps(content),
            status_code=status_code,
            media_type='application/json',
            **kwargs
        )


class HTMLResponse(Response):
    """HTML response."""

    def __init__(self, content: str, status_code: int = 200, **kwargs):
        super().__init__(
            content=content,
            status_code=status_code,
            media_type='text/html; charset=utf-8',
            **kwargs
        )


class RedirectResponse(Response):
    """Redirect response."""

    def __init__(self, url: str, status_code: int = 302):
        super().__init__(
            status_code=status_code,
            headers={'location': url}
        )


class StreamingResponse(Response):
    """Streaming response."""

    def __init__(
        self,
        content: AsyncIterator[bytes],
        status_code: int = 200,
        media_type: str = None,
        headers: dict = None,
    ):
        self.body_iterator = content
        self.status_code = status_code
        self.media_type = media_type
        self.headers = headers or {}

        if self.media_type:
            self.headers['content-type'] = self.media_type

    async def __call__(self, scope, receive, send):
        await send({
            'type': 'http.response.start',
            'status': self.status_code,
            'headers': [
                (k.lower().encode(), v.encode())
                for k, v in self.headers.items()
            ],
        })

        async for chunk in self.body_iterator:
            await send({
                'type': 'http.response.body',
                'body': chunk,
                'more_body': True,
            })

        await send({
            'type': 'http.response.body',
            'body': b'',
            'more_body': False,
        })
```

---

## Phase 2: Routing System

### 2.1 Router Implementation

```python
"""
File: swiftapi/routing.py
URL routing with path parameters.
"""

import re
from typing import Callable, Dict, List, Optional, Tuple, Any
from dataclasses import dataclass


@dataclass
class Route:
    """Single route definition."""
    path: str
    endpoint: Callable
    methods: List[str]
    name: Optional[str] = None

    # Compiled regex for matching
    _regex: Optional[re.Pattern] = None
    _param_names: List[str] = None

    def __post_init__(self):
        self._compile()

    def _compile(self):
        """Compile path pattern to regex."""
        # Convert {param} to named groups
        pattern = self.path
        self._param_names = []

        def replace_param(match):
            name = match.group(1)
            self._param_names.append(name)
            return f'(?P<{name}>[^/]+)'

        pattern = re.sub(r'\{(\w+)\}', replace_param, pattern)
        pattern = f'^{pattern}$'
        self._regex = re.compile(pattern)

    def match(self, path: str) -> Optional[Dict[str, str]]:
        """Match path and extract parameters."""
        match = self._regex.match(path)
        if match:
            return match.groupdict()
        return None


class Router:
    """URL router with method-based routing."""

    def __init__(self):
        self.routes: List[Route] = []

    def add_route(
        self,
        path: str,
        endpoint: Callable,
        methods: List[str] = None,
        name: str = None
    ):
        """Add a route."""
        methods = methods or ['GET']
        route = Route(
            path=path,
            endpoint=endpoint,
            methods=[m.upper() for m in methods],
            name=name
        )
        self.routes.append(route)

    def route(self, path: str, methods: List[str] = None, name: str = None):
        """Decorator to add route."""
        def decorator(func: Callable):
            self.add_route(path, func, methods, name)
            return func
        return decorator

    def get(self, path: str, name: str = None):
        return self.route(path, ['GET'], name)

    def post(self, path: str, name: str = None):
        return self.route(path, ['POST'], name)

    def put(self, path: str, name: str = None):
        return self.route(path, ['PUT'], name)

    def delete(self, path: str, name: str = None):
        return self.route(path, ['DELETE'], name)

    def match(self, path: str, method: str) -> Tuple[Optional[Route], Dict[str, str]]:
        """Find matching route."""
        method = method.upper()

        for route in self.routes:
            params = route.match(path)
            if params is not None:
                if method in route.methods:
                    return route, params
                # Method not allowed
                return None, {}

        return None, {}

    def url_for(self, name: str, **path_params) -> str:
        """Generate URL for named route."""
        for route in self.routes:
            if route.name == name:
                path = route.path
                for key, value in path_params.items():
                    path = path.replace(f'{{{key}}}', str(value))
                return path
        raise ValueError(f"No route named '{name}'")
```

---

## Phase 3: Application Class

### 3.1 Main Application

```python
"""
File: swiftapi/applications.py
Main application class.
"""

from typing import Callable, List, Dict, Any, Type
import asyncio

from .routing import Router
from .requests import Request, Response, JSONResponse
from .middleware import MiddlewareStack
from .exceptions import HTTPException


class SwiftAPI:
    """
    Main application class.

    Example:
        app = SwiftAPI()

        @app.get("/")
        async def home(request):
            return {"message": "Hello, World!"}

        @app.get("/users/{user_id}")
        async def get_user(request):
            user_id = request.path_params['user_id']
            return {"user_id": user_id}
    """

    def __init__(
        self,
        title: str = "SwiftAPI",
        version: str = "1.0.0",
        debug: bool = False,
    ):
        self.title = title
        self.version = version
        self.debug = debug

        self.router = Router()
        self.middleware = MiddlewareStack()
        self.exception_handlers: Dict[Type[Exception], Callable] = {}

        self._startup_handlers: List[Callable] = []
        self._shutdown_handlers: List[Callable] = []

        # Register default exception handler
        self.exception_handlers[HTTPException] = self._handle_http_exception
        self.exception_handlers[Exception] = self._handle_exception

    # Route decorators
    def get(self, path: str, **kwargs):
        return self.router.get(path, **kwargs)

    def post(self, path: str, **kwargs):
        return self.router.post(path, **kwargs)

    def put(self, path: str, **kwargs):
        return self.router.put(path, **kwargs)

    def delete(self, path: str, **kwargs):
        return self.router.delete(path, **kwargs)

    def route(self, path: str, methods: List[str] = None, **kwargs):
        return self.router.route(path, methods, **kwargs)

    # Middleware
    def add_middleware(self, middleware_class: Type, **options):
        """Add middleware to stack."""
        self.middleware.add(middleware_class, **options)

    # Exception handlers
    def exception_handler(self, exc_class: Type[Exception]):
        """Register exception handler."""
        def decorator(func: Callable):
            self.exception_handlers[exc_class] = func
            return func
        return decorator

    # Lifecycle hooks
    def on_startup(self, func: Callable):
        """Register startup handler."""
        self._startup_handlers.append(func)
        return func

    def on_shutdown(self, func: Callable):
        """Register shutdown handler."""
        self._shutdown_handlers.append(func)
        return func

    # ASGI interface
    async def __call__(self, scope: dict, receive: Callable, send: Callable):
        """ASGI entry point."""
        scope_type = scope['type']

        if scope_type == 'lifespan':
            await self._handle_lifespan(scope, receive, send)
        elif scope_type == 'http':
            await self._handle_http(scope, receive, send)
        elif scope_type == 'websocket':
            await self._handle_websocket(scope, receive, send)

    async def _handle_lifespan(self, scope, receive, send):
        """Handle lifespan events."""
        while True:
            message = await receive()

            if message['type'] == 'lifespan.startup':
                try:
                    for handler in self._startup_handlers:
                        if asyncio.iscoroutinefunction(handler):
                            await handler()
                        else:
                            handler()
                    await send({'type': 'lifespan.startup.complete'})
                except Exception as e:
                    await send({
                        'type': 'lifespan.startup.failed',
                        'message': str(e)
                    })

            elif message['type'] == 'lifespan.shutdown':
                try:
                    for handler in self._shutdown_handlers:
                        if asyncio.iscoroutinefunction(handler):
                            await handler()
                        else:
                            handler()
                except Exception:
                    pass
                await send({'type': 'lifespan.shutdown.complete'})
                return

    async def _handle_http(self, scope, receive, send):
        """Handle HTTP request."""
        request = Request(scope, receive)

        try:
            # Run through middleware
            response = await self.middleware.process(
                request,
                lambda req: self._dispatch(req)
            )
        except Exception as exc:
            response = await self._handle_exception_response(exc, request)

        await response(scope, receive, send)

    async def _dispatch(self, request: Request) -> Response:
        """Dispatch request to handler."""
        route, path_params = self.router.match(request.path, request.method)

        if route is None:
            raise HTTPException(404, "Not Found")

        # Add path params to scope
        request.scope['path_params'] = path_params

        # Call handler
        response = await route.endpoint(request)

        # Convert dict to JSON response
        if isinstance(response, dict):
            response = JSONResponse(response)

        return response

    async def _handle_http_exception(
        self,
        request: Request,
        exc: HTTPException
    ) -> Response:
        """Handle HTTP exception."""
        return JSONResponse(
            {'detail': exc.detail},
            status_code=exc.status_code
        )

    async def _handle_exception(
        self,
        request: Request,
        exc: Exception
    ) -> Response:
        """Handle generic exception."""
        if self.debug:
            import traceback
            return JSONResponse(
                {
                    'detail': str(exc),
                    'traceback': traceback.format_exc()
                },
                status_code=500
            )
        return JSONResponse(
            {'detail': 'Internal Server Error'},
            status_code=500
        )

    async def _handle_exception_response(
        self,
        exc: Exception,
        request: Request
    ) -> Response:
        """Find and call appropriate exception handler."""
        for exc_class in type(exc).__mro__:
            if exc_class in self.exception_handlers:
                handler = self.exception_handlers[exc_class]
                return await handler(request, exc)

        # Fallback
        return await self._handle_exception(request, exc)

    async def _handle_websocket(self, scope, receive, send):
        """Handle WebSocket connection."""
        # Implement WebSocket handling
        pass
```

---

## Phase 4: Middleware System

### 4.1 Middleware Stack

```python
"""
File: swiftapi/middleware.py
Middleware system.
"""

from typing import Callable, List, Type, Any
from .requests import Request, Response


class MiddlewareStack:
    """Middleware processing stack."""

    def __init__(self):
        self._middleware: List[tuple] = []

    def add(self, middleware_class: Type, **options):
        """Add middleware to stack."""
        self._middleware.append((middleware_class, options))

    async def process(
        self,
        request: Request,
        handler: Callable[[Request], Response]
    ) -> Response:
        """Process request through middleware stack."""

        async def call_next(index: int, req: Request) -> Response:
            if index >= len(self._middleware):
                return await handler(req)

            middleware_class, options = self._middleware[index]
            middleware = middleware_class(**options)

            return await middleware(
                req,
                lambda r: call_next(index + 1, r)
            )

        return await call_next(0, request)


class BaseMiddleware:
    """Base middleware class."""

    async def __call__(
        self,
        request: Request,
        call_next: Callable
    ) -> Response:
        return await call_next(request)


class CORSMiddleware(BaseMiddleware):
    """CORS middleware."""

    def __init__(
        self,
        allow_origins: List[str] = None,
        allow_methods: List[str] = None,
        allow_headers: List[str] = None,
        allow_credentials: bool = False,
        max_age: int = 600,
    ):
        self.allow_origins = allow_origins or ['*']
        self.allow_methods = allow_methods or ['*']
        self.allow_headers = allow_headers or ['*']
        self.allow_credentials = allow_credentials
        self.max_age = max_age

    async def __call__(self, request: Request, call_next: Callable) -> Response:
        origin = request.headers.get('origin', '')

        # Handle preflight
        if request.method == 'OPTIONS':
            return self._preflight_response(origin)

        # Process request
        response = await call_next(request)

        # Add CORS headers
        self._add_cors_headers(response, origin)

        return response

    def _preflight_response(self, origin: str) -> Response:
        headers = self._cors_headers(origin)
        headers['access-control-allow-methods'] = ', '.join(self.allow_methods)
        headers['access-control-allow-headers'] = ', '.join(self.allow_headers)
        headers['access-control-max-age'] = str(self.max_age)
        return Response(status_code=204, headers=headers)

    def _add_cors_headers(self, response: Response, origin: str):
        cors_headers = self._cors_headers(origin)
        response.headers.update(cors_headers)

    def _cors_headers(self, origin: str) -> dict:
        headers = {}

        if '*' in self.allow_origins:
            headers['access-control-allow-origin'] = '*'
        elif origin in self.allow_origins:
            headers['access-control-allow-origin'] = origin

        if self.allow_credentials:
            headers['access-control-allow-credentials'] = 'true'

        return headers


class LoggingMiddleware(BaseMiddleware):
    """Request logging middleware."""

    async def __call__(self, request: Request, call_next: Callable) -> Response:
        import time
        import logging

        logger = logging.getLogger('swiftapi')

        start = time.perf_counter()
        logger.info(f"→ {request.method} {request.path}")

        response = await call_next(request)

        elapsed = (time.perf_counter() - start) * 1000
        logger.info(f"← {response.status_code} - {elapsed:.2f}ms")

        return response
```

---

## Phase 5: Dependency Injection

### 5.1 DI Container

```python
"""
File: swiftapi/dependencies.py
Dependency injection system.
"""

from typing import Type, TypeVar, Callable, Dict, Any, Optional
import inspect
import asyncio
from functools import wraps

T = TypeVar('T')


class Depends:
    """Dependency marker."""

    def __init__(self, dependency: Callable):
        self.dependency = dependency


class Container:
    """Dependency injection container."""

    def __init__(self):
        self._singletons: Dict[Type, Any] = {}
        self._factories: Dict[Type, Callable] = {}

    def singleton(self, interface: Type[T], implementation: Type[T] = None):
        """Register singleton."""
        impl = implementation or interface

        async def factory():
            if interface not in self._singletons:
                self._singletons[interface] = await self._create(impl)
            return self._singletons[interface]

        self._factories[interface] = factory

    def transient(self, interface: Type[T], implementation: Type[T] = None):
        """Register transient."""
        impl = implementation or interface
        self._factories[interface] = lambda: self._create(impl)

    def factory(self, interface: Type[T], factory: Callable):
        """Register factory function."""
        self._factories[interface] = factory

    async def resolve(self, interface: Type[T]) -> T:
        """Resolve dependency."""
        if interface in self._factories:
            result = self._factories[interface]()
            if asyncio.iscoroutine(result):
                return await result
            return result

        # Try auto-wiring
        return await self._create(interface)

    async def _create(self, cls: Type[T]) -> T:
        """Create instance with resolved dependencies."""
        sig = inspect.signature(cls.__init__)
        kwargs = {}

        for name, param in sig.parameters.items():
            if name == 'self':
                continue

            if param.annotation != inspect.Parameter.empty:
                kwargs[name] = await self.resolve(param.annotation)

        return cls(**kwargs)


# Global container
container = Container()


def inject(func: Callable) -> Callable:
    """Decorator to inject dependencies into handler."""
    sig = inspect.signature(func)

    @wraps(func)
    async def wrapper(request, *args, **kwargs):
        # Resolve dependencies from type hints
        for name, param in sig.parameters.items():
            if name in ('request', 'self'):
                continue

            # Check for Depends marker
            if param.default != inspect.Parameter.empty:
                if isinstance(param.default, Depends):
                    dep = param.default.dependency
                    if asyncio.iscoroutinefunction(dep):
                        kwargs[name] = await dep(request)
                    else:
                        kwargs[name] = dep(request)
                    continue

            # Resolve from container
            if param.annotation != inspect.Parameter.empty:
                kwargs[name] = await container.resolve(param.annotation)

        return await func(request, *args, **kwargs)

    return wrapper
```

---

## Phase 6: Testing & Documentation

### 6.1 Test Client

```python
"""
File: swiftapi/testclient.py
Test client for testing applications.
"""

from typing import Optional, Dict, Any
import json


class TestClient:
    """Test client for SwiftAPI applications."""

    def __init__(self, app):
        self.app = app

    async def request(
        self,
        method: str,
        path: str,
        headers: Dict[str, str] = None,
        json_data: Any = None,
        data: bytes = None,
    ) -> 'TestResponse':
        """Make test request."""
        headers = headers or {}
        body = b''

        if json_data is not None:
            body = json.dumps(json_data).encode()
            headers['content-type'] = 'application/json'

        if data is not None:
            body = data

        # Build scope
        scope = {
            'type': 'http',
            'asgi': {'version': '3.0'},
            'http_version': '1.1',
            'method': method.upper(),
            'path': path,
            'query_string': b'',
            'headers': [(k.lower().encode(), v.encode()) for k, v in headers.items()],
            'server': ('testserver', 80),
            'client': ('testclient', 0),
        }

        # Capture response
        response = {'status': None, 'headers': [], 'body': []}
        body_sent = False

        async def receive():
            nonlocal body_sent
            if not body_sent:
                body_sent = True
                return {'type': 'http.request', 'body': body, 'more_body': False}
            return {'type': 'http.disconnect'}

        async def send(message):
            if message['type'] == 'http.response.start':
                response['status'] = message['status']
                response['headers'] = message.get('headers', [])
            elif message['type'] == 'http.response.body':
                response['body'].append(message.get('body', b''))

        await self.app(scope, receive, send)

        return TestResponse(
            status_code=response['status'],
            headers=dict((k.decode(), v.decode()) for k, v in response['headers']),
            content=b''.join(response['body'])
        )

    async def get(self, path: str, **kwargs) -> 'TestResponse':
        return await self.request('GET', path, **kwargs)

    async def post(self, path: str, **kwargs) -> 'TestResponse':
        return await self.request('POST', path, **kwargs)

    async def put(self, path: str, **kwargs) -> 'TestResponse':
        return await self.request('PUT', path, **kwargs)

    async def delete(self, path: str, **kwargs) -> 'TestResponse':
        return await self.request('DELETE', path, **kwargs)


class TestResponse:
    """Test response object."""

    def __init__(self, status_code: int, headers: dict, content: bytes):
        self.status_code = status_code
        self.headers = headers
        self.content = content

    def json(self) -> Any:
        return json.loads(self.content)

    @property
    def text(self) -> str:
        return self.content.decode()
```

---

## Phase 7: Package Structure

### Final Project Structure

```
swiftapi/
├── __init__.py
├── applications.py      # Main SwiftAPI class
├── routing.py           # Router and Route classes
├── requests.py          # Request/Response objects
├── middleware.py        # Middleware system
├── dependencies.py      # Dependency injection
├── exceptions.py        # HTTP exceptions
├── server.py           # ASGI server
├── testclient.py       # Test client
├── static.py           # Static file serving
├── templates.py        # Template rendering
├── security/
│   ├── __init__.py
│   ├── authentication.py
│   ├── authorization.py
│   └── cors.py
├── observability/
│   ├── __init__.py
│   ├── logging.py
│   ├── metrics.py
│   └── tracing.py
└── utils/
    ├── __init__.py
    └── helpers.py

tests/
├── __init__.py
├── test_routing.py
├── test_middleware.py
├── test_dependencies.py
└── test_application.py

docs/
├── index.md
├── quickstart.md
├── routing.md
├── middleware.md
├── dependencies.md
└── api-reference.md

examples/
├── basic/
│   └── main.py
├── rest-api/
│   └── main.py
└── full-app/
    ├── main.py
    ├── routes/
    ├── models/
    └── services/

pyproject.toml
README.md
LICENSE
```

---

## Deliverables Checklist

### Core Features
- [ ] ASGI 3.0 compliant server
- [ ] HTTP/1.1 request parsing
- [ ] Response building and streaming
- [ ] URL routing with path parameters
- [ ] Request/Response objects
- [ ] JSON handling

### Advanced Features
- [ ] Middleware pipeline
- [ ] Dependency injection
- [ ] Exception handling
- [ ] Static file serving
- [ ] Template rendering
- [ ] WebSocket support

### Production Features
- [ ] CORS middleware
- [ ] Authentication (JWT)
- [ ] Rate limiting
- [ ] Request validation
- [ ] Logging middleware
- [ ] Metrics collection

### Quality
- [ ] Comprehensive test suite (>80% coverage)
- [ ] Type hints throughout
- [ ] Documentation
- [ ] Example applications
- [ ] Benchmarks

### Packaging
- [ ] pyproject.toml
- [ ] README with examples
- [ ] API documentation
- [ ] Changelog

---

## Evaluation Criteria

| Category | Weight | Criteria |
|----------|--------|----------|
| Correctness | 30% | All features work as specified |
| Code Quality | 25% | Clean, readable, maintainable code |
| Performance | 20% | Handles high load efficiently |
| Testing | 15% | Comprehensive test coverage |
| Documentation | 10% | Clear docs and examples |

---

## Bonus Challenges

1. **HTTP/2 Support**: Implement HTTP/2 protocol handling
2. **GraphQL**: Add GraphQL endpoint support
3. **OpenAPI**: Auto-generate OpenAPI specification
4. **CLI Tool**: Create command-line interface for development
5. **Hot Reload**: Implement hot reloading for development

---

## Conclusion

Congratulations on completing this capstone project! You've built a production-ready web framework from scratch, demonstrating deep understanding of:

- Network protocols and socket programming
- HTTP specification and parsing
- Async programming patterns
- Middleware architecture
- Dependency injection
- Security best practices
- Performance optimization
- Production infrastructure

You now have the knowledge to build, debug, and optimize any web server or framework.

---

## Next Steps

1. **Contribute**: Share your framework on GitHub
2. **Benchmark**: Compare performance with existing frameworks
3. **Extend**: Add features like GraphQL, gRPC, or WebSockets
4. **Learn More**: Study source code of FastAPI, Starlette, Django
5. **Build**: Create real applications with your framework

---

## Appendices

**[Appendix A: Reference Implementations →](./APPENDIX_A_REFERENCES.md)**

**[Appendix B: RFC Quick Reference →](./APPENDIX_B_RFCS.md)**

**[Appendix C: Debugging Cheatsheet →](./APPENDIX_C_DEBUGGING.md)**

**[Appendix D: Performance Benchmarks →](./APPENDIX_D_BENCHMARKS.md)**

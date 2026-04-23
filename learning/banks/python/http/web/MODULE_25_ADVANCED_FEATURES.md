# Module 25: Advanced Framework Features

## Overview

Modern web frameworks provide many advanced features that simplify development. This module covers templating, static files, sessions, background tasks, and other features that make a framework production-ready.

---

## Learning Objectives

By the end of this module, you will be able to:

1. Implement template rendering systems
2. Serve static files efficiently
3. Build session management
4. Handle background tasks
5. Implement WebSocket integration

---

## 25.1 Template Rendering

### Simple Template Engine

```python
import re
from typing import Any, Dict, Callable
from pathlib import Path


class TemplateEngine:
    """Simple template engine with variable substitution and control flow."""

    def __init__(self, template_dir: str = "templates"):
        self.template_dir = Path(template_dir)
        self.cache: Dict[str, str] = {}
        self.filters: Dict[str, Callable] = {}

        # Register default filters
        self._register_default_filters()

    def _register_default_filters(self):
        """Register built-in filters."""
        self.filters['escape'] = self._escape_html
        self.filters['upper'] = str.upper
        self.filters['lower'] = str.lower
        self.filters['title'] = str.title
        self.filters['length'] = len
        self.filters['default'] = lambda v, d: v if v else d

    def _escape_html(self, value: str) -> str:
        """Escape HTML special characters."""
        import html
        return html.escape(str(value))

    def render(self, template_name: str, context: Dict[str, Any] = None) -> str:
        """Render template with context."""
        context = context or {}

        # Load template
        template = self._load_template(template_name)

        # Process includes
        template = self._process_includes(template)

        # Process extends/blocks
        template = self._process_inheritance(template, context)

        # Process control structures
        template = self._process_for_loops(template, context)
        template = self._process_if_statements(template, context)

        # Process variables
        template = self._process_variables(template, context)

        return template

    def _load_template(self, name: str) -> str:
        """Load template from file."""
        if name in self.cache:
            return self.cache[name]

        path = self.template_dir / name
        if not path.exists():
            raise TemplateNotFound(f"Template not found: {name}")

        content = path.read_text()
        self.cache[name] = content
        return content

    def _process_variables(self, template: str, context: Dict) -> str:
        """Process {{ variable }} expressions."""
        pattern = r'\{\{\s*(.+?)\s*\}\}'

        def replace(match):
            expr = match.group(1)

            # Handle filters: {{ value|filter }}
            if '|' in expr:
                parts = expr.split('|')
                value = self._resolve(parts[0].strip(), context)
                for filter_expr in parts[1:]:
                    value = self._apply_filter(filter_expr.strip(), value)
                return str(value)

            return str(self._resolve(expr, context))

        return re.sub(pattern, replace, template)

    def _resolve(self, expr: str, context: Dict) -> Any:
        """Resolve expression to value."""
        # Handle dot notation: user.name
        parts = expr.split('.')
        value = context

        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            elif hasattr(value, part):
                value = getattr(value, part)
            else:
                return ''

        return value if value is not None else ''

    def _apply_filter(self, filter_expr: str, value: Any) -> Any:
        """Apply filter to value."""
        # Handle filter with args: default('N/A')
        match = re.match(r'(\w+)\((.*)\)', filter_expr)
        if match:
            name, args_str = match.groups()
            args = [arg.strip().strip("'\"") for arg in args_str.split(',')]
            filter_func = self.filters.get(name)
            if filter_func:
                return filter_func(value, *args)

        # Simple filter
        filter_func = self.filters.get(filter_expr)
        if filter_func:
            return filter_func(value)

        return value

    def _process_for_loops(self, template: str, context: Dict) -> str:
        """Process {% for item in items %} ... {% endfor %}."""
        pattern = r'\{%\s*for\s+(\w+)\s+in\s+(\w+)\s*%\}(.*?)\{%\s*endfor\s*%\}'

        def replace(match):
            var_name, list_name, body = match.groups()
            items = context.get(list_name, [])
            result = []

            for i, item in enumerate(items):
                loop_context = {
                    **context,
                    var_name: item,
                    'loop': {
                        'index': i + 1,
                        'index0': i,
                        'first': i == 0,
                        'last': i == len(items) - 1,
                        'length': len(items)
                    }
                }
                result.append(self._process_variables(body, loop_context))

            return ''.join(result)

        return re.sub(pattern, replace, template, flags=re.DOTALL)

    def _process_if_statements(self, template: str, context: Dict) -> str:
        """Process {% if condition %} ... {% endif %}."""
        pattern = r'\{%\s*if\s+(.+?)\s*%\}(.*?)(?:\{%\s*else\s*%\}(.*?))?\{%\s*endif\s*%\}'

        def replace(match):
            condition, if_body, else_body = match.groups()
            else_body = else_body or ''

            # Evaluate condition
            value = self._resolve(condition, context)
            if value:
                return if_body
            return else_body

        return re.sub(pattern, replace, template, flags=re.DOTALL)

    def _process_includes(self, template: str) -> str:
        """Process {% include 'partial.html' %}."""
        pattern = r'\{%\s*include\s+[\'"](.+?)[\'"]\s*%\}'

        def replace(match):
            include_name = match.group(1)
            return self._load_template(include_name)

        return re.sub(pattern, replace, template)

    def _process_inheritance(self, template: str, context: Dict) -> str:
        """Process {% extends 'base.html' %} and {% block %}."""
        # Check for extends
        extends_match = re.search(r'\{%\s*extends\s+[\'"](.+?)[\'"]\s*%\}', template)

        if not extends_match:
            return template

        base_name = extends_match.group(1)
        base_template = self._load_template(base_name)

        # Extract blocks from child
        block_pattern = r'\{%\s*block\s+(\w+)\s*%\}(.*?)\{%\s*endblock\s*%\}'
        child_blocks = dict(re.findall(block_pattern, template, re.DOTALL))

        # Replace blocks in base
        def replace_block(match):
            block_name = match.group(1)
            default_content = match.group(2)
            return child_blocks.get(block_name, default_content)

        return re.sub(block_pattern, replace_block, base_template, flags=re.DOTALL)


class TemplateNotFound(Exception):
    pass


# Integration with framework
class TemplateResponse(Response):
    """Response that renders a template."""

    def __init__(self, template_name: str, context: Dict = None,
                 status: int = 200, engine: TemplateEngine = None):
        self.engine = engine or default_engine
        content = self.engine.render(template_name, context)

        super().__init__(
            status=status,
            headers={'content-type': 'text/html; charset=utf-8'},
            body=content.encode()
        )


# Global template engine
default_engine = TemplateEngine()


# Helper function
def render_template(name: str, **context) -> Response:
    """Render template and return response."""
    return TemplateResponse(name, context)
```

---

## 25.2 Static File Serving

### Static Files Handler

```python
import os
import mimetypes
from pathlib import Path
from datetime import datetime
import hashlib


class StaticFiles:
    """Static file serving with caching support."""

    def __init__(self, directory: str = "static",
                 prefix: str = "/static",
                 cache_max_age: int = 86400):
        self.directory = Path(directory).resolve()
        self.prefix = prefix.rstrip('/')
        self.cache_max_age = cache_max_age

        # Ensure directory exists
        if not self.directory.exists():
            raise ValueError(f"Static directory not found: {directory}")

    async def __call__(self, scope, receive, send):
        """ASGI handler for static files."""
        if scope['type'] != 'http':
            return

        path = scope['path']
        if not path.startswith(self.prefix):
            await self._not_found(send)
            return

        # Get file path
        file_path = path[len(self.prefix):].lstrip('/')
        full_path = self.directory / file_path

        # Security: prevent directory traversal
        try:
            full_path = full_path.resolve()
            if not str(full_path).startswith(str(self.directory)):
                await self._not_found(send)
                return
        except (ValueError, OSError):
            await self._not_found(send)
            return

        if not full_path.exists() or not full_path.is_file():
            await self._not_found(send)
            return

        # Handle conditional requests
        method = scope.get('method', 'GET')
        headers = dict(scope.get('headers', []))

        etag = self._generate_etag(full_path)
        last_modified = self._get_last_modified(full_path)

        # Check If-None-Match
        if_none_match = headers.get(b'if-none-match', b'').decode()
        if if_none_match == etag:
            await self._not_modified(send, etag, last_modified)
            return

        # Check If-Modified-Since
        if_modified = headers.get(b'if-modified-since', b'').decode()
        if if_modified and self._not_modified_since(full_path, if_modified):
            await self._not_modified(send, etag, last_modified)
            return

        # Serve file
        await self._serve_file(send, full_path, etag, last_modified, method)

    def _generate_etag(self, path: Path) -> str:
        """Generate ETag from file stats."""
        stat = path.stat()
        content = f"{stat.st_mtime}-{stat.st_size}"
        return f'"{hashlib.md5(content.encode()).hexdigest()}"'

    def _get_last_modified(self, path: Path) -> str:
        """Get Last-Modified header value."""
        mtime = path.stat().st_mtime
        dt = datetime.utcfromtimestamp(mtime)
        return dt.strftime('%a, %d %b %Y %H:%M:%S GMT')

    def _not_modified_since(self, path: Path, if_modified: str) -> bool:
        """Check if file was modified since the given date."""
        try:
            from email.utils import parsedate_to_datetime
            client_date = parsedate_to_datetime(if_modified)
            file_date = datetime.utcfromtimestamp(path.stat().st_mtime)
            return file_date <= client_date
        except (ValueError, TypeError):
            return False

    async def _serve_file(self, send, path: Path, etag: str,
                         last_modified: str, method: str):
        """Serve the file with proper headers."""
        content_type = mimetypes.guess_type(str(path))[0] or 'application/octet-stream'
        size = path.stat().st_size

        headers = [
            (b'content-type', content_type.encode()),
            (b'content-length', str(size).encode()),
            (b'etag', etag.encode()),
            (b'last-modified', last_modified.encode()),
            (b'cache-control', f'max-age={self.cache_max_age}'.encode()),
        ]

        await send({
            'type': 'http.response.start',
            'status': 200,
            'headers': headers
        })

        if method == 'HEAD':
            await send({
                'type': 'http.response.body',
                'body': b''
            })
            return

        # Stream file
        with open(path, 'rb') as f:
            while chunk := f.read(65536):
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

    async def _not_found(self, send):
        await send({
            'type': 'http.response.start',
            'status': 404,
            'headers': [(b'content-type', b'text/plain')]
        })
        await send({
            'type': 'http.response.body',
            'body': b'Not Found'
        })

    async def _not_modified(self, send, etag: str, last_modified: str):
        await send({
            'type': 'http.response.start',
            'status': 304,
            'headers': [
                (b'etag', etag.encode()),
                (b'last-modified', last_modified.encode())
            ]
        })
        await send({
            'type': 'http.response.body',
            'body': b''
        })


# Mount static files in application
class Application:
    def __init__(self):
        self.routes = {}
        self.static_handler = None

    def mount_static(self, prefix: str = "/static", directory: str = "static"):
        """Mount static file handler."""
        self.static_handler = StaticFiles(directory, prefix)

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return

        path = scope['path']

        # Check static files first
        if self.static_handler and path.startswith(self.static_handler.prefix):
            await self.static_handler(scope, receive, send)
            return

        # Route to handlers
        # ...
```

---

## 25.3 Session Management

### Server-Side Sessions

```python
import uuid
import json
import time
from typing import Any, Dict, Optional
from dataclasses import dataclass, field
from abc import ABC, abstractmethod


@dataclass
class Session:
    """User session."""
    id: str
    data: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    modified_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None

    def __getitem__(self, key: str) -> Any:
        return self.data.get(key)

    def __setitem__(self, key: str, value: Any):
        self.data[key] = value
        self.modified_at = time.time()

    def __delitem__(self, key: str):
        del self.data[key]
        self.modified_at = time.time()

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def pop(self, key: str, default: Any = None) -> Any:
        self.modified_at = time.time()
        return self.data.pop(key, default)

    def clear(self):
        self.data.clear()
        self.modified_at = time.time()

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at


class SessionStore(ABC):
    """Abstract session store."""

    @abstractmethod
    async def get(self, session_id: str) -> Optional[Session]:
        pass

    @abstractmethod
    async def set(self, session: Session):
        pass

    @abstractmethod
    async def delete(self, session_id: str):
        pass


class MemorySessionStore(SessionStore):
    """In-memory session store."""

    def __init__(self):
        self._sessions: Dict[str, Session] = {}

    async def get(self, session_id: str) -> Optional[Session]:
        session = self._sessions.get(session_id)
        if session and session.is_expired:
            del self._sessions[session_id]
            return None
        return session

    async def set(self, session: Session):
        self._sessions[session.id] = session

    async def delete(self, session_id: str):
        self._sessions.pop(session_id, None)


class RedisSessionStore(SessionStore):
    """Redis-based session store."""

    def __init__(self, redis, prefix: str = "session:"):
        self.redis = redis
        self.prefix = prefix

    async def get(self, session_id: str) -> Optional[Session]:
        data = await self.redis.get(f"{self.prefix}{session_id}")
        if not data:
            return None

        session_data = json.loads(data)
        return Session(
            id=session_id,
            data=session_data.get('data', {}),
            created_at=session_data.get('created_at', time.time()),
            modified_at=session_data.get('modified_at', time.time())
        )

    async def set(self, session: Session):
        data = {
            'data': session.data,
            'created_at': session.created_at,
            'modified_at': session.modified_at
        }

        ttl = None
        if session.expires_at:
            ttl = int(session.expires_at - time.time())

        await self.redis.set(
            f"{self.prefix}{session.id}",
            json.dumps(data),
            ex=ttl
        )

    async def delete(self, session_id: str):
        await self.redis.delete(f"{self.prefix}{session_id}")


class SessionMiddleware:
    """Session management middleware."""

    def __init__(self, app,
                 store: SessionStore = None,
                 cookie_name: str = "session_id",
                 max_age: int = 86400 * 7,  # 1 week
                 secure: bool = True,
                 httponly: bool = True,
                 samesite: str = "lax"):
        self.app = app
        self.store = store or MemorySessionStore()
        self.cookie_name = cookie_name
        self.max_age = max_age
        self.secure = secure
        self.httponly = httponly
        self.samesite = samesite

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        # Get session ID from cookie
        session_id = self._get_session_id(scope)
        session = None
        is_new = False

        if session_id:
            session = await self.store.get(session_id)

        if not session:
            session = Session(
                id=str(uuid.uuid4()),
                expires_at=time.time() + self.max_age
            )
            is_new = True

        # Add session to scope
        scope['session'] = session

        # Track if session was modified
        original_modified = session.modified_at

        async def send_wrapper(message):
            if message['type'] == 'http.response.start':
                # Save session if modified or new
                if session.modified_at != original_modified or is_new:
                    await self.store.set(session)

                    # Set cookie
                    headers = list(message.get('headers', []))
                    headers.append((
                        b'set-cookie',
                        self._make_cookie(session).encode()
                    ))
                    message = {**message, 'headers': headers}

            await send(message)

        await self.app(scope, receive, send_wrapper)

    def _get_session_id(self, scope) -> Optional[str]:
        """Extract session ID from cookies."""
        for name, value in scope.get('headers', []):
            if name == b'cookie':
                cookies = self._parse_cookies(value.decode())
                return cookies.get(self.cookie_name)
        return None

    def _parse_cookies(self, cookie_string: str) -> Dict[str, str]:
        """Parse cookie header."""
        cookies = {}
        for item in cookie_string.split(';'):
            if '=' in item:
                key, value = item.split('=', 1)
                cookies[key.strip()] = value.strip()
        return cookies

    def _make_cookie(self, session: Session) -> str:
        """Create Set-Cookie header value."""
        parts = [f"{self.cookie_name}={session.id}"]
        parts.append(f"Max-Age={self.max_age}")
        parts.append("Path=/")

        if self.secure:
            parts.append("Secure")
        if self.httponly:
            parts.append("HttpOnly")
        if self.samesite:
            parts.append(f"SameSite={self.samesite}")

        return "; ".join(parts)


# Usage in handlers
async def login(request):
    session = request.scope['session']
    session['user_id'] = user.id
    session['logged_in_at'] = time.time()
    return Response.json({'status': 'logged in'})


async def logout(request):
    session = request.scope['session']
    session.clear()
    return Response.json({'status': 'logged out'})


async def profile(request):
    session = request.scope['session']
    user_id = session.get('user_id')
    if not user_id:
        return Response.json({'error': 'Not logged in'}, status=401)
    # ...
```

---

## 25.4 Background Tasks

### Task Queue

```python
import asyncio
from typing import Callable, Any, Dict
from dataclasses import dataclass
from enum import Enum
import uuid
import traceback


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Task:
    id: str
    func: Callable
    args: tuple
    kwargs: dict
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: str = None


class BackgroundTasks:
    """Background task manager."""

    def __init__(self, max_workers: int = 10):
        self.max_workers = max_workers
        self.queue: asyncio.Queue[Task] = asyncio.Queue()
        self.tasks: Dict[str, Task] = {}
        self._workers: list = []
        self._running = False

    async def start(self):
        """Start background workers."""
        self._running = True
        for i in range(self.max_workers):
            worker = asyncio.create_task(self._worker(i))
            self._workers.append(worker)

    async def stop(self):
        """Stop background workers."""
        self._running = False

        # Cancel pending tasks
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        # Wait for workers
        for worker in self._workers:
            worker.cancel()

        await asyncio.gather(*self._workers, return_exceptions=True)

    def add_task(self, func: Callable, *args, **kwargs) -> str:
        """Add task to queue."""
        task = Task(
            id=str(uuid.uuid4()),
            func=func,
            args=args,
            kwargs=kwargs
        )
        self.tasks[task.id] = task
        self.queue.put_nowait(task)
        return task.id

    def get_task(self, task_id: str) -> Task:
        """Get task by ID."""
        return self.tasks.get(task_id)

    async def _worker(self, worker_id: int):
        """Worker coroutine."""
        while self._running:
            try:
                task = await asyncio.wait_for(
                    self.queue.get(),
                    timeout=1.0
                )
            except asyncio.TimeoutError:
                continue

            task.status = TaskStatus.RUNNING

            try:
                if asyncio.iscoroutinefunction(task.func):
                    result = await task.func(*task.args, **task.kwargs)
                else:
                    result = task.func(*task.args, **task.kwargs)

                task.result = result
                task.status = TaskStatus.COMPLETED

            except Exception as e:
                task.error = traceback.format_exc()
                task.status = TaskStatus.FAILED


# Request-scoped background tasks
class RequestBackgroundTasks:
    """Background tasks that run after response is sent."""

    def __init__(self):
        self._tasks: list = []

    def add(self, func: Callable, *args, **kwargs):
        """Add task to run after response."""
        self._tasks.append((func, args, kwargs))

    async def execute(self):
        """Execute all tasks."""
        for func, args, kwargs in self._tasks:
            try:
                if asyncio.iscoroutinefunction(func):
                    await func(*args, **kwargs)
                else:
                    func(*args, **kwargs)
            except Exception:
                logger.exception("Background task failed")


class BackgroundTaskMiddleware:
    """Middleware to handle request background tasks."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        # Create request-scoped tasks
        tasks = RequestBackgroundTasks()
        scope['background_tasks'] = tasks

        await self.app(scope, receive, send)

        # Execute background tasks after response
        await tasks.execute()


# Usage in handler
async def create_user(request):
    data = await request.json()
    user = await db.create_user(data)

    # Add background task
    request.scope['background_tasks'].add(
        send_welcome_email,
        user.email,
        user.name
    )

    return Response.json(user, status=201)
```

---

## 25.5 WebSocket Integration

### WebSocket Handler

```python
from typing import Callable, Dict, Set
import asyncio


class WebSocketRoute:
    """WebSocket route handler."""

    def __init__(self, path: str, handler: Callable):
        self.path = path
        self.handler = handler


class WebSocketRouter:
    """Router for WebSocket connections."""

    def __init__(self):
        self.routes: Dict[str, WebSocketRoute] = {}

    def route(self, path: str):
        """Decorator to register WebSocket handler."""
        def decorator(handler: Callable):
            self.routes[path] = WebSocketRoute(path, handler)
            return handler
        return decorator

    def match(self, path: str) -> WebSocketRoute:
        return self.routes.get(path)


class WebSocketConnection:
    """WebSocket connection wrapper."""

    def __init__(self, scope, receive, send):
        self.scope = scope
        self._receive = receive
        self._send = send
        self.accepted = False
        self.closed = False

    async def accept(self, subprotocol: str = None):
        """Accept the WebSocket connection."""
        message = {'type': 'websocket.accept'}
        if subprotocol:
            message['subprotocol'] = subprotocol
        await self._send(message)
        self.accepted = True

    async def receive_text(self) -> str:
        """Receive text message."""
        message = await self._receive()
        if message['type'] == 'websocket.disconnect':
            self.closed = True
            raise WebSocketDisconnect(message.get('code', 1000))
        return message.get('text', '')

    async def receive_bytes(self) -> bytes:
        """Receive binary message."""
        message = await self._receive()
        if message['type'] == 'websocket.disconnect':
            self.closed = True
            raise WebSocketDisconnect(message.get('code', 1000))
        return message.get('bytes', b'')

    async def send_text(self, data: str):
        """Send text message."""
        await self._send({
            'type': 'websocket.send',
            'text': data
        })

    async def send_bytes(self, data: bytes):
        """Send binary message."""
        await self._send({
            'type': 'websocket.send',
            'bytes': data
        })

    async def send_json(self, data: Any):
        """Send JSON message."""
        await self.send_text(json.dumps(data))

    async def close(self, code: int = 1000):
        """Close the connection."""
        if not self.closed:
            await self._send({
                'type': 'websocket.close',
                'code': code
            })
            self.closed = True


class WebSocketDisconnect(Exception):
    def __init__(self, code: int = 1000):
        self.code = code


class WebSocketManager:
    """Manage WebSocket connections."""

    def __init__(self):
        self.active_connections: Set[WebSocketConnection] = set()
        self.rooms: Dict[str, Set[WebSocketConnection]] = {}

    async def connect(self, websocket: WebSocketConnection):
        """Register new connection."""
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocketConnection):
        """Remove connection."""
        self.active_connections.discard(websocket)
        # Remove from all rooms
        for room in self.rooms.values():
            room.discard(websocket)

    def join_room(self, websocket: WebSocketConnection, room: str):
        """Add connection to room."""
        if room not in self.rooms:
            self.rooms[room] = set()
        self.rooms[room].add(websocket)

    def leave_room(self, websocket: WebSocketConnection, room: str):
        """Remove connection from room."""
        if room in self.rooms:
            self.rooms[room].discard(websocket)

    async def broadcast(self, message: str):
        """Send to all connections."""
        for conn in list(self.active_connections):
            try:
                await conn.send_text(message)
            except Exception:
                self.disconnect(conn)

    async def broadcast_to_room(self, room: str, message: str):
        """Send to all connections in room."""
        if room not in self.rooms:
            return

        for conn in list(self.rooms[room]):
            try:
                await conn.send_text(message)
            except Exception:
                self.disconnect(conn)


# Usage
ws_router = WebSocketRouter()
ws_manager = WebSocketManager()


@ws_router.route('/ws/chat')
async def chat_handler(websocket: WebSocketConnection):
    await ws_manager.connect(websocket)

    try:
        # Get room from query
        room = websocket.scope.get('query_params', {}).get('room', 'general')
        ws_manager.join_room(websocket, room)

        while True:
            message = await websocket.receive_text()
            data = json.loads(message)

            await ws_manager.broadcast_to_room(
                room,
                json.dumps({
                    'type': 'message',
                    'text': data['text']
                })
            )

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
```

---

## 25.6 File Uploads

### Multipart Parser

```python
import re
from typing import Dict, List, BinaryIO
from dataclasses import dataclass
import tempfile


@dataclass
class UploadFile:
    """Uploaded file."""
    filename: str
    content_type: str
    file: BinaryIO

    async def read(self) -> bytes:
        return self.file.read()

    async def save(self, path: str):
        with open(path, 'wb') as f:
            self.file.seek(0)
            f.write(self.file.read())

    def close(self):
        self.file.close()


class MultipartParser:
    """Parse multipart/form-data requests."""

    def __init__(self, max_file_size: int = 10 * 1024 * 1024):
        self.max_file_size = max_file_size

    async def parse(self, body: bytes, content_type: str) -> Dict[str, any]:
        """Parse multipart body."""
        # Extract boundary
        match = re.search(r'boundary=([^\s;]+)', content_type)
        if not match:
            raise ValueError("No boundary in content-type")

        boundary = match.group(1).encode()

        # Split into parts
        parts = body.split(b'--' + boundary)
        result = {'fields': {}, 'files': {}}

        for part in parts[1:-1]:  # Skip first and last
            if not part.strip() or part.strip() == b'--':
                continue

            # Split headers and content
            header_end = part.find(b'\r\n\r\n')
            if header_end == -1:
                continue

            headers_raw = part[:header_end]
            content = part[header_end + 4:].rstrip(b'\r\n')

            # Parse headers
            headers = self._parse_headers(headers_raw)
            disposition = headers.get('content-disposition', '')

            # Extract name and filename
            name_match = re.search(r'name="([^"]+)"', disposition)
            filename_match = re.search(r'filename="([^"]+)"', disposition)

            if not name_match:
                continue

            name = name_match.group(1)

            if filename_match:
                # File upload
                filename = filename_match.group(1)
                content_type = headers.get('content-type', 'application/octet-stream')

                # Save to temp file
                temp = tempfile.SpooledTemporaryFile(max_size=1024 * 1024)
                temp.write(content)
                temp.seek(0)

                result['files'][name] = UploadFile(
                    filename=filename,
                    content_type=content_type,
                    file=temp
                )
            else:
                # Form field
                result['fields'][name] = content.decode()

        return result

    def _parse_headers(self, raw: bytes) -> Dict[str, str]:
        """Parse part headers."""
        headers = {}
        for line in raw.decode().split('\r\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                headers[key.lower().strip()] = value.strip()
        return headers


# Usage
@app.post('/upload')
async def upload_file(request):
    parser = MultipartParser()
    data = await parser.parse(request.body, request.content_type)

    file = data['files'].get('document')
    if file:
        await file.save(f'/uploads/{file.filename}')
        file.close()
        return Response.json({'filename': file.filename})

    return Response.json({'error': 'No file uploaded'}, status=400)
```

---

## 25.7 API Documentation

### OpenAPI Generator

```python
from typing import Dict, List, Any, Type, get_type_hints
from dataclasses import dataclass, fields, is_dataclass
import inspect


class OpenAPIGenerator:
    """Generate OpenAPI specification from routes."""

    def __init__(self, title: str, version: str, description: str = ""):
        self.title = title
        self.version = version
        self.description = description
        self.paths: Dict[str, Dict] = {}
        self.schemas: Dict[str, Dict] = {}

    def add_route(self, method: str, path: str, handler: Callable,
                 tags: List[str] = None, summary: str = None):
        """Add route to spec."""
        if path not in self.paths:
            self.paths[path] = {}

        # Get handler info
        doc = handler.__doc__ or ""
        hints = get_type_hints(handler) if handler else {}

        operation = {
            'summary': summary or doc.split('\n')[0],
            'description': doc,
            'tags': tags or [],
            'responses': {
                '200': {'description': 'Successful response'}
            }
        }

        # Extract parameters from path
        params = self._extract_path_params(path)
        if params:
            operation['parameters'] = params

        # Extract request body from type hints
        if 'body' in hints:
            body_type = hints['body']
            schema_name = self._add_schema(body_type)
            operation['requestBody'] = {
                'content': {
                    'application/json': {
                        'schema': {'$ref': f'#/components/schemas/{schema_name}'}
                    }
                }
            }

        # Extract response from return type
        if 'return' in hints:
            return_type = hints['return']
            schema_name = self._add_schema(return_type)
            operation['responses']['200']['content'] = {
                'application/json': {
                    'schema': {'$ref': f'#/components/schemas/{schema_name}'}
                }
            }

        self.paths[path][method.lower()] = operation

    def _extract_path_params(self, path: str) -> List[Dict]:
        """Extract path parameters."""
        params = []
        import re
        for match in re.finditer(r'\{(\w+)\}', path):
            params.append({
                'name': match.group(1),
                'in': 'path',
                'required': True,
                'schema': {'type': 'string'}
            })
        return params

    def _add_schema(self, type_hint: Type) -> str:
        """Add schema for type."""
        name = type_hint.__name__

        if name in self.schemas:
            return name

        if is_dataclass(type_hint):
            properties = {}
            required = []

            for field in fields(type_hint):
                prop_type = self._get_json_type(field.type)
                properties[field.name] = prop_type

                if field.default is field.default_factory:
                    required.append(field.name)

            self.schemas[name] = {
                'type': 'object',
                'properties': properties,
                'required': required
            }

        return name

    def _get_json_type(self, python_type: Type) -> Dict:
        """Convert Python type to JSON schema type."""
        type_map = {
            str: {'type': 'string'},
            int: {'type': 'integer'},
            float: {'type': 'number'},
            bool: {'type': 'boolean'},
            list: {'type': 'array'},
            dict: {'type': 'object'},
        }
        return type_map.get(python_type, {'type': 'string'})

    def generate(self) -> Dict:
        """Generate OpenAPI spec."""
        return {
            'openapi': '3.0.0',
            'info': {
                'title': self.title,
                'version': self.version,
                'description': self.description
            },
            'paths': self.paths,
            'components': {
                'schemas': self.schemas
            }
        }


# Integration
def setup_docs(app, title: str, version: str):
    """Setup API documentation."""
    generator = OpenAPIGenerator(title, version)

    # Register routes
    for (method, path), handler in app.router.routes.items():
        generator.add_route(method, path, handler)

    @app.get('/openapi.json')
    async def openapi_spec(request):
        return Response.json(generator.generate())

    @app.get('/docs')
    async def swagger_ui(request):
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{title} - API Docs</title>
            <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@4/swagger-ui.css">
        </head>
        <body>
            <div id="swagger-ui"></div>
            <script src="https://unpkg.com/swagger-ui-dist@4/swagger-ui-bundle.js"></script>
            <script>
                SwaggerUIBundle({{
                    url: '/openapi.json',
                    dom_id: '#swagger-ui'
                }})
            </script>
        </body>
        </html>
        """
        return Response.html(html)
```

---

## Exercises

### Exercise 25.1: Template Inheritance

Extend the template engine to support:
- Multiple levels of inheritance
- Super block content (call parent block)
- Macros

### Exercise 25.2: Session Flash Messages

Implement flash messages:
- Store messages in session
- Display once and clear
- Support different types (success, error, info)

### Exercise 25.3: Background Job Scheduler

Create a job scheduler that:
- Supports cron-like scheduling
- Persists jobs across restarts
- Handles job failures with retries

---

## Summary

Advanced framework features:

1. **Templates**: Variable substitution, control flow, inheritance
2. **Static Files**: Efficient serving with caching
3. **Sessions**: Server-side state management
4. **Background Tasks**: Post-response and queued tasks
5. **WebSockets**: Real-time communication
6. **File Uploads**: Multipart parsing
7. **API Docs**: OpenAPI specification

---

## Next Module

**[Module 26: Capstone - Build a Production Web Framework →](./MODULE_26_CAPSTONE.md)**

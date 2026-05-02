# Appendix A: Reference Implementations

## Overview

This appendix provides reference implementations for key components discussed throughout the syllabus. These are complete, working examples you can study and adapt.

---

## A.1 Minimal HTTP Server (50 Lines)

```python
"""
Minimal HTTP server in 50 lines.
Demonstrates core concepts without complexity.
"""

import socket


def serve(host='127.0.0.1', port=8080):
    """Start HTTP server."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen(5)
    print(f"Serving on http://{host}:{port}")

    while True:
        client, addr = server.accept()
        handle_request(client)


def handle_request(client):
    """Handle single HTTP request."""
    try:
        data = client.recv(4096)
        if not data:
            return

        # Parse request line
        lines = data.decode().split('\r\n')
        method, path, _ = lines[0].split(' ')

        # Route
        if path == '/':
            body = b'<h1>Hello, World!</h1>'
            status = '200 OK'
        elif path == '/api':
            body = b'{"message": "Hello, API!"}'
            status = '200 OK'
        else:
            body = b'<h1>404 Not Found</h1>'
            status = '404 Not Found'

        # Build response
        response = f'HTTP/1.1 {status}\r\n'
        response += f'Content-Length: {len(body)}\r\n'
        response += 'Content-Type: text/html\r\n'
        response += '\r\n'

        client.send(response.encode() + body)
    finally:
        client.close()


if __name__ == '__main__':
    serve()
```

---

## A.2 Async HTTP Server

```python
"""
Complete async HTTP server with routing.
"""

import asyncio
import re
from typing import Callable, Dict, Tuple, Optional


class AsyncHTTPServer:
    def __init__(self, host='127.0.0.1', port=8080):
        self.host = host
        self.port = port
        self.routes: Dict[Tuple[str, str], Callable] = {}

    def route(self, method: str, path: str):
        def decorator(handler: Callable):
            pattern = self._compile_path(path)
            self.routes[(method.upper(), pattern)] = handler
            return handler
        return decorator

    def _compile_path(self, path: str) -> str:
        return re.sub(r'\{(\w+)\}', r'(?P<\1>[^/]+)', path)

    async def handle_connection(self, reader, writer):
        try:
            # Read request
            data = await reader.read(65536)
            if not data:
                return

            # Parse
            request = self._parse_request(data)

            # Route
            handler, params = self._find_handler(
                request['method'],
                request['path']
            )

            if handler:
                request['params'] = params
                response = await handler(request)
            else:
                response = {'status': 404, 'body': 'Not Found'}

            # Send response
            await self._send_response(writer, response)

        finally:
            writer.close()
            await writer.wait_closed()

    def _parse_request(self, data: bytes) -> dict:
        lines = data.decode().split('\r\n')
        method, path, _ = lines[0].split(' ')

        headers = {}
        for line in lines[1:]:
            if ':' in line:
                key, value = line.split(':', 1)
                headers[key.lower()] = value.strip()
            elif line == '':
                break

        body_start = data.find(b'\r\n\r\n') + 4
        body = data[body_start:]

        return {
            'method': method,
            'path': path,
            'headers': headers,
            'body': body
        }

    def _find_handler(self, method: str, path: str) -> Tuple[Optional[Callable], dict]:
        for (route_method, pattern), handler in self.routes.items():
            if route_method != method:
                continue
            match = re.match(f'^{pattern}$', path)
            if match:
                return handler, match.groupdict()
        return None, {}

    async def _send_response(self, writer, response: dict):
        status = response.get('status', 200)
        body = response.get('body', '')
        headers = response.get('headers', {})

        if isinstance(body, dict):
            import json
            body = json.dumps(body)
            headers['Content-Type'] = 'application/json'

        if isinstance(body, str):
            body = body.encode()

        headers['Content-Length'] = len(body)

        # Build response
        resp = f'HTTP/1.1 {status} OK\r\n'
        for key, value in headers.items():
            resp += f'{key}: {value}\r\n'
        resp += '\r\n'

        writer.write(resp.encode() + body)
        await writer.drain()

    async def serve(self):
        server = await asyncio.start_server(
            self.handle_connection,
            self.host,
            self.port
        )
        print(f'Serving on http://{self.host}:{self.port}')
        async with server:
            await server.serve_forever()


# Usage
app = AsyncHTTPServer()


@app.route('GET', '/')
async def home(request):
    return {'body': '<h1>Home</h1>', 'headers': {'Content-Type': 'text/html'}}


@app.route('GET', '/users/{user_id}')
async def get_user(request):
    user_id = request['params']['user_id']
    return {'body': {'user_id': user_id, 'name': 'John'}}


@app.route('POST', '/users')
async def create_user(request):
    import json
    data = json.loads(request['body'])
    return {'status': 201, 'body': {'id': 1, **data}}


if __name__ == '__main__':
    asyncio.run(app.serve())
```

---

## A.3 Thread Pool Server

```python
"""
Thread pool HTTP server for comparison with async.
"""

import socket
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Dict


class ThreadPoolServer:
    def __init__(self, host='127.0.0.1', port=8080, workers=10):
        self.host = host
        self.port = port
        self.workers = workers
        self.routes: Dict[tuple, Callable] = {}

    def route(self, method: str, path: str):
        def decorator(handler):
            self.routes[(method.upper(), path)] = handler
            return handler
        return decorator

    def serve(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((self.host, self.port))
        server.listen(128)

        print(f'Serving on http://{self.host}:{self.port} with {self.workers} workers')

        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            while True:
                client, addr = server.accept()
                executor.submit(self.handle_request, client)

    def handle_request(self, client):
        try:
            data = client.recv(65536)
            if not data:
                return

            request = self._parse_request(data)
            handler = self.routes.get((request['method'], request['path']))

            if handler:
                response = handler(request)
            else:
                response = {'status': 404, 'body': 'Not Found'}

            self._send_response(client, response)

        finally:
            client.close()

    def _parse_request(self, data: bytes) -> dict:
        lines = data.decode().split('\r\n')
        method, path, _ = lines[0].split(' ')
        return {'method': method, 'path': path}

    def _send_response(self, client, response: dict):
        status = response.get('status', 200)
        body = response.get('body', '').encode()

        resp = f'HTTP/1.1 {status} OK\r\n'
        resp += f'Content-Length: {len(body)}\r\n'
        resp += '\r\n'

        client.send(resp.encode() + body)


# Usage
app = ThreadPoolServer()


@app.route('GET', '/')
def home(request):
    return {'body': 'Hello from thread pool!'}


if __name__ == '__main__':
    app.serve()
```

---

## A.4 WSGI Application

```python
"""
Complete WSGI application example.
"""


def application(environ, start_response):
    """WSGI application."""
    method = environ['REQUEST_METHOD']
    path = environ['PATH_INFO']

    # Simple router
    if path == '/' and method == 'GET':
        status = '200 OK'
        body = b'<h1>Home</h1>'
        content_type = 'text/html'

    elif path == '/api' and method == 'GET':
        status = '200 OK'
        body = b'{"message": "Hello, WSGI!"}'
        content_type = 'application/json'

    elif path == '/api' and method == 'POST':
        # Read request body
        content_length = int(environ.get('CONTENT_LENGTH', 0))
        body_input = environ['wsgi.input'].read(content_length)

        import json
        data = json.loads(body_input)

        status = '201 Created'
        body = json.dumps({'received': data}).encode()
        content_type = 'application/json'

    else:
        status = '404 Not Found'
        body = b'Not Found'
        content_type = 'text/plain'

    headers = [
        ('Content-Type', content_type),
        ('Content-Length', str(len(body)))
    ]

    start_response(status, headers)
    return [body]


# Simple WSGI server
def run_wsgi(app, host='127.0.0.1', port=8080):
    """Minimal WSGI server."""
    import socket

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen(5)

    print(f'WSGI server on http://{host}:{port}')

    while True:
        client, addr = server.accept()
        handle_wsgi_request(client, app)


def handle_wsgi_request(client, app):
    """Handle single WSGI request."""
    try:
        data = client.recv(65536)
        lines = data.decode().split('\r\n')
        request_line = lines[0]
        method, path, _ = request_line.split(' ')

        # Parse headers
        headers = {}
        body_start = 0
        for i, line in enumerate(lines[1:], 1):
            if line == '':
                body_start = i + 1
                break
            if ':' in line:
                key, value = line.split(':', 1)
                headers[key.strip()] = value.strip()

        # Build environ
        from io import BytesIO
        body = '\r\n'.join(lines[body_start:]).encode()

        environ = {
            'REQUEST_METHOD': method,
            'PATH_INFO': path,
            'CONTENT_TYPE': headers.get('Content-Type', ''),
            'CONTENT_LENGTH': headers.get('Content-Length', '0'),
            'wsgi.input': BytesIO(body),
            'wsgi.errors': None,
            'wsgi.url_scheme': 'http',
        }

        # Call app
        response_started = []
        response_headers = []

        def start_response(status, headers):
            response_started.append(status)
            response_headers.extend(headers)

        body_parts = list(app(environ, start_response))

        # Send response
        status = response_started[0]
        response = f'HTTP/1.1 {status}\r\n'
        for name, value in response_headers:
            response += f'{name}: {value}\r\n'
        response += '\r\n'

        client.send(response.encode())
        for part in body_parts:
            client.send(part)

    finally:
        client.close()


if __name__ == '__main__':
    run_wsgi(application)
```

---

## A.5 ASGI Application

```python
"""
Complete ASGI application example.
"""


async def app(scope, receive, send):
    """ASGI application."""
    if scope['type'] == 'lifespan':
        await handle_lifespan(scope, receive, send)
    elif scope['type'] == 'http':
        await handle_http(scope, receive, send)
    elif scope['type'] == 'websocket':
        await handle_websocket(scope, receive, send)


async def handle_lifespan(scope, receive, send):
    """Handle lifespan events."""
    while True:
        message = await receive()
        if message['type'] == 'lifespan.startup':
            print('Starting up...')
            await send({'type': 'lifespan.startup.complete'})
        elif message['type'] == 'lifespan.shutdown':
            print('Shutting down...')
            await send({'type': 'lifespan.shutdown.complete'})
            return


async def handle_http(scope, receive, send):
    """Handle HTTP request."""
    method = scope['method']
    path = scope['path']

    # Read body
    body = b''
    while True:
        message = await receive()
        body += message.get('body', b'')
        if not message.get('more_body', False):
            break

    # Route
    if path == '/' and method == 'GET':
        await send_response(send, 200, b'<h1>ASGI Home</h1>', 'text/html')

    elif path == '/api' and method == 'GET':
        import json
        data = json.dumps({'message': 'Hello, ASGI!'}).encode()
        await send_response(send, 200, data, 'application/json')

    elif path == '/api' and method == 'POST':
        import json
        request_data = json.loads(body)
        response_data = json.dumps({'received': request_data}).encode()
        await send_response(send, 201, response_data, 'application/json')

    else:
        await send_response(send, 404, b'Not Found', 'text/plain')


async def handle_websocket(scope, receive, send):
    """Handle WebSocket connection."""
    # Wait for connect
    message = await receive()
    if message['type'] != 'websocket.connect':
        return

    # Accept
    await send({'type': 'websocket.accept'})

    # Echo loop
    try:
        while True:
            message = await receive()
            if message['type'] == 'websocket.receive':
                text = message.get('text', '')
                await send({'type': 'websocket.send', 'text': f'Echo: {text}'})
            elif message['type'] == 'websocket.disconnect':
                break
    except Exception:
        pass


async def send_response(send, status: int, body: bytes, content_type: str):
    """Send HTTP response."""
    await send({
        'type': 'http.response.start',
        'status': status,
        'headers': [
            (b'content-type', content_type.encode()),
            (b'content-length', str(len(body)).encode()),
        ],
    })
    await send({
        'type': 'http.response.body',
        'body': body,
    })


# Run with: uvicorn reference_asgi:app
```

---

## A.6 Event Loop Implementation

```python
"""
Minimal event loop implementation for educational purposes.
"""

import selectors
import heapq
import time
from typing import Callable, Optional
from dataclasses import dataclass, field


@dataclass(order=True)
class TimerHandle:
    when: float
    callback: Callable = field(compare=False)
    args: tuple = field(compare=False, default=())


class EventLoop:
    """Simple event loop."""

    def __init__(self):
        self.selector = selectors.DefaultSelector()
        self.timers: list = []
        self.ready: list = []
        self.running = False

    def run_forever(self):
        self.running = True
        while self.running:
            self._run_once()

    def stop(self):
        self.running = False

    def _run_once(self):
        # Process ready callbacks
        while self.ready:
            callback, args = self.ready.pop(0)
            callback(*args)

        # Calculate timeout
        timeout = self._get_timeout()

        # Wait for I/O
        events = self.selector.select(timeout)
        for key, mask in events:
            self.ready.append((key.data, (key.fileobj, mask)))

        # Process timers
        now = time.monotonic()
        while self.timers and self.timers[0].when <= now:
            handle = heapq.heappop(self.timers)
            self.ready.append((handle.callback, handle.args))

    def _get_timeout(self) -> Optional[float]:
        if self.ready:
            return 0
        if self.timers:
            return max(0, self.timers[0].when - time.monotonic())
        return 1.0

    def call_soon(self, callback: Callable, *args):
        self.ready.append((callback, args))

    def call_later(self, delay: float, callback: Callable, *args):
        when = time.monotonic() + delay
        handle = TimerHandle(when, callback, args)
        heapq.heappush(self.timers, handle)

    def add_reader(self, fd, callback: Callable):
        try:
            self.selector.register(fd, selectors.EVENT_READ, callback)
        except KeyError:
            self.selector.modify(fd, selectors.EVENT_READ, callback)

    def remove_reader(self, fd):
        try:
            self.selector.unregister(fd)
        except KeyError:
            pass


# Usage example
if __name__ == '__main__':
    import socket

    loop = EventLoop()

    def on_connection(server, mask):
        client, addr = server.accept()
        client.setblocking(False)
        print(f'Connection from {addr}')
        loop.add_reader(client.fileno(), lambda: on_data(client))

    def on_data(client):
        data = client.recv(1024)
        if data:
            client.send(b'HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\nHello')
        loop.remove_reader(client.fileno())
        client.close()

    # Setup server
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.setblocking(False)
    server.bind(('127.0.0.1', 8080))
    server.listen(5)

    loop.add_reader(server.fileno(), lambda: on_connection(server, None))
    print('Event loop server on http://127.0.0.1:8080')
    loop.run_forever()
```

---

## Summary

These reference implementations demonstrate:

1. **Minimal HTTP**: Core concepts in 50 lines
2. **Async Server**: Full async implementation with routing
3. **Thread Pool**: Traditional multi-threaded approach
4. **WSGI**: Synchronous Python web standard
5. **ASGI**: Asynchronous Python web standard
6. **Event Loop**: Understanding async internals

Use these as starting points for your own implementations.

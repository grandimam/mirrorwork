# Module 16: ASGI Deep Dive

## Overview

ASGI (Asynchronous Server Gateway Interface) extends WSGI for async Python. It supports WebSockets, HTTP/2, and long-lived connections. This module covers the ASGI spec and building ASGI servers.

---

## Learning Objectives

By the end of this module, you will be able to:

1. Explain ASGI vs WSGI
2. Write ASGI applications
3. Handle lifespan, HTTP, and WebSocket protocols
4. Build an ASGI server
5. Implement ASGI middleware

---

## 16.1 ASGI Specification

### The Interface

```python
async def application(scope: dict, receive: callable, send: callable):
    """
    ASGI application.

    Args:
        scope: Connection info (type, path, headers, etc.)
        receive: Async callable to receive messages
        send: Async callable to send messages
    """
    pass
```

### Scope Types

```python
# HTTP connection
scope = {
    'type': 'http',
    'asgi': {'version': '3.0'},
    'http_version': '1.1',
    'method': 'GET',
    'scheme': 'http',
    'path': '/hello',
    'query_string': b'name=world',
    'headers': [(b'host', b'localhost:8080')],
    'server': ('localhost', 8080),
    'client': ('127.0.0.1', 54321),
}

# WebSocket connection
scope = {
    'type': 'websocket',
    'path': '/ws',
    'headers': [...],
    'subprotocols': ['graphql-ws'],
}

# Lifespan
scope = {
    'type': 'lifespan',
    'asgi': {'version': '3.0'},
}
```

---

## 16.2 HTTP Protocol

### Simple HTTP Application

```python
async def app(scope, receive, send):
    if scope['type'] != 'http':
        return

    # Receive request body
    body = b''
    while True:
        message = await receive()
        body += message.get('body', b'')
        if not message.get('more_body', False):
            break

    # Send response
    await send({
        'type': 'http.response.start',
        'status': 200,
        'headers': [
            (b'content-type', b'text/plain'),
        ],
    })

    await send({
        'type': 'http.response.body',
        'body': b'Hello, ASGI!',
    })
```

### HTTP Messages

```python
# Request body
message = await receive()
# {'type': 'http.request', 'body': b'...', 'more_body': True/False}

# Response start
await send({
    'type': 'http.response.start',
    'status': 200,
    'headers': [(b'name', b'value'), ...],
})

# Response body (can be chunked)
await send({
    'type': 'http.response.body',
    'body': b'chunk 1',
    'more_body': True,
})
await send({
    'type': 'http.response.body',
    'body': b'chunk 2',
    'more_body': False,  # Last chunk
})
```

---

## 16.3 WebSocket Protocol

```python
async def websocket_app(scope, receive, send):
    if scope['type'] != 'websocket':
        return

    # Accept connection
    await send({'type': 'websocket.accept'})

    try:
        while True:
            message = await receive()

            if message['type'] == 'websocket.receive':
                text = message.get('text', '')
                data = message.get('bytes', b'')

                # Echo back
                if text:
                    await send({
                        'type': 'websocket.send',
                        'text': f'Echo: {text}'
                    })

            elif message['type'] == 'websocket.disconnect':
                break

    except Exception:
        await send({'type': 'websocket.close', 'code': 1000})
```

### WebSocket Messages

```python
# Client connects
{'type': 'websocket.connect'}

# Accept connection
await send({'type': 'websocket.accept', 'subprotocol': 'graphql-ws'})

# Receive message
{'type': 'websocket.receive', 'text': '...'}  # or 'bytes': b'...'

# Send message
await send({'type': 'websocket.send', 'text': '...'})

# Client disconnects
{'type': 'websocket.disconnect', 'code': 1000}

# Server closes
await send({'type': 'websocket.close', 'code': 1000})
```

---

## 16.4 Lifespan Protocol

```python
async def app(scope, receive, send):
    if scope['type'] == 'lifespan':
        while True:
            message = await receive()

            if message['type'] == 'lifespan.startup':
                # Initialize resources
                await startup()
                await send({'type': 'lifespan.startup.complete'})

            elif message['type'] == 'lifespan.shutdown':
                # Cleanup resources
                await shutdown()
                await send({'type': 'lifespan.shutdown.complete'})
                return

    elif scope['type'] == 'http':
        # Handle HTTP
        pass
```

---

## 16.5 Complete ASGI Application

```python
"""
Complete ASGI application with HTTP, WebSocket, and lifespan.
"""

class ASGIApp:
    """Full-featured ASGI application."""

    def __init__(self):
        self.routes = {}
        self.ws_routes = {}
        self.db = None

    async def __call__(self, scope, receive, send):
        if scope['type'] == 'lifespan':
            await self.lifespan(scope, receive, send)
        elif scope['type'] == 'http':
            await self.http(scope, receive, send)
        elif scope['type'] == 'websocket':
            await self.websocket(scope, receive, send)

    async def lifespan(self, scope, receive, send):
        while True:
            message = await receive()
            if message['type'] == 'lifespan.startup':
                self.db = await create_db_pool()
                await send({'type': 'lifespan.startup.complete'})
            elif message['type'] == 'lifespan.shutdown':
                await self.db.close()
                await send({'type': 'lifespan.shutdown.complete'})
                return

    async def http(self, scope, receive, send):
        path = scope['path']
        method = scope['method']

        handler = self.routes.get((method, path))
        if handler:
            await handler(scope, receive, send)
        else:
            await self.not_found(send)

    async def websocket(self, scope, receive, send):
        path = scope['path']
        handler = self.ws_routes.get(path)
        if handler:
            await handler(scope, receive, send)
        else:
            await send({'type': 'websocket.close', 'code': 4004})

    async def not_found(self, send):
        await send({
            'type': 'http.response.start',
            'status': 404,
            'headers': [(b'content-type', b'text/plain')],
        })
        await send({
            'type': 'http.response.body',
            'body': b'Not Found',
        })

    def route(self, method, path):
        def decorator(handler):
            self.routes[(method, path)] = handler
            return handler
        return decorator

    def websocket_route(self, path):
        def decorator(handler):
            self.ws_routes[path] = handler
            return handler
        return decorator


# Usage
app = ASGIApp()

@app.route('GET', '/')
async def index(scope, receive, send):
    await send({
        'type': 'http.response.start',
        'status': 200,
        'headers': [(b'content-type', b'text/html')],
    })
    await send({
        'type': 'http.response.body',
        'body': b'<h1>ASGI App</h1>',
    })

@app.websocket_route('/ws')
async def ws_handler(scope, receive, send):
    await send({'type': 'websocket.accept'})

    while True:
        msg = await receive()
        if msg['type'] == 'websocket.receive':
            await send({
                'type': 'websocket.send',
                'text': f"Echo: {msg.get('text', '')}"
            })
        elif msg['type'] == 'websocket.disconnect':
            break
```

---

## 16.6 Building an ASGI Server

```python
"""
Simple ASGI server (HTTP only).
"""

import asyncio
from typing import Callable


class ASGIServer:
    """Minimal ASGI server."""

    def __init__(self, app: Callable, host='0.0.0.0', port=8080):
        self.app = app
        self.host = host
        self.port = port

    async def handle_connection(self, reader, writer):
        """Handle HTTP connection."""
        try:
            # Read request
            data = await reader.read(65536)
            if not data:
                return

            # Parse request
            scope = self.parse_request(data, writer)

            # Create receive/send
            body_received = False
            body = self.extract_body(data)

            async def receive():
                nonlocal body_received
                if not body_received:
                    body_received = True
                    return {
                        'type': 'http.request',
                        'body': body,
                        'more_body': False
                    }
                # Wait for disconnect
                await asyncio.sleep(3600)
                return {'type': 'http.disconnect'}

            async def send(message):
                if message['type'] == 'http.response.start':
                    status = message['status']
                    headers = message.get('headers', [])

                    response = f"HTTP/1.1 {status} OK\r\n"
                    for name, value in headers:
                        response += f"{name.decode()}: {value.decode()}\r\n"
                    response += "\r\n"

                    writer.write(response.encode())

                elif message['type'] == 'http.response.body':
                    body = message.get('body', b'')
                    writer.write(body)

                    if not message.get('more_body', False):
                        await writer.drain()

            # Call ASGI app
            await self.app(scope, receive, send)

        except Exception as e:
            print(f"Error: {e}")
        finally:
            writer.close()
            await writer.wait_closed()

    def parse_request(self, data: bytes, writer) -> dict:
        """Parse HTTP request into ASGI scope."""
        lines = data.split(b'\r\n')
        request_line = lines[0].decode()
        method, path, _ = request_line.split(' ')

        # Parse headers
        headers = []
        for line in lines[1:]:
            if line == b'':
                break
            name, _, value = line.partition(b':')
            headers.append((name.lower(), value.strip()))

        # Path and query
        if b'?' in path.encode():
            path, query = path.split('?', 1)
            query_string = query.encode()
        else:
            query_string = b''

        peername = writer.get_extra_info('peername')

        return {
            'type': 'http',
            'asgi': {'version': '3.0'},
            'http_version': '1.1',
            'method': method,
            'scheme': 'http',
            'path': path,
            'query_string': query_string,
            'headers': headers,
            'server': (self.host, self.port),
            'client': peername,
        }

    def extract_body(self, data: bytes) -> bytes:
        """Extract body from raw request."""
        parts = data.split(b'\r\n\r\n', 1)
        return parts[1] if len(parts) > 1 else b''

    async def run(self):
        """Start server."""
        server = await asyncio.start_server(
            self.handle_connection,
            self.host, self.port
        )

        print(f"ASGI Server on http://{self.host}:{self.port}")

        async with server:
            await server.serve_forever()


# Run
if __name__ == '__main__':
    async def simple_app(scope, receive, send):
        await send({
            'type': 'http.response.start',
            'status': 200,
            'headers': [(b'content-type', b'text/plain')],
        })
        await send({
            'type': 'http.response.body',
            'body': b'Hello from ASGI Server!',
        })

    server = ASGIServer(simple_app)
    asyncio.run(server.run())
```

---

## 16.7 ASGI Middleware

```python
class ASGIMiddleware:
    """Base ASGI middleware."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        await self.app(scope, receive, send)


class LoggingMiddleware(ASGIMiddleware):
    """Log requests."""

    async def __call__(self, scope, receive, send):
        if scope['type'] == 'http':
            print(f"{scope['method']} {scope['path']}")
        await self.app(scope, receive, send)


class CORSMiddleware(ASGIMiddleware):
    """Add CORS headers."""

    def __init__(self, app, origins=['*']):
        super().__init__(app)
        self.origins = origins

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        async def send_wrapper(message):
            if message['type'] == 'http.response.start':
                headers = list(message.get('headers', []))
                headers.append((b'access-control-allow-origin', b'*'))
                message = {**message, 'headers': headers}
            await send(message)

        await self.app(scope, receive, send_wrapper)
```

---

## Exercises

### Exercise 16.1: Server-Sent Events

Implement SSE support in ASGI:
```python
@app.route('GET', '/events')
async def events(scope, receive, send):
    # Stream events to client
    pass
```

### Exercise 16.2: File Upload

Handle multipart file uploads in ASGI.

### Exercise 16.3: WebSocket Chat

Build a chat room using ASGI WebSockets.

---

## Summary

You've mastered ASGI:
1. **Scope/Receive/Send**: The async interface
2. **HTTP**: Request/response messages
3. **WebSocket**: Full-duplex communication
4. **Lifespan**: Startup/shutdown hooks
5. **Middleware**: Composable async processing

---

## Next Module

**[Module 17: WebSockets →](./MODULE_17_WEBSOCKETS.md)**

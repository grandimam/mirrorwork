# Module 15: WSGI Deep Dive

## Overview

WSGI (Web Server Gateway Interface) is the standard interface between Python web servers and frameworks. This module covers PEP 3333 in depth—you'll build both a WSGI server and understand how frameworks like Flask work.

---

## Learning Objectives

By the end of this module, you will be able to:

1. Explain the WSGI specification
2. Write WSGI applications
3. Implement WSGI middleware
4. Build a complete WSGI server
5. Understand how Flask/Django use WSGI

---

## 15.1 The WSGI Specification (PEP 3333)

### The Interface

```python
def application(environ: dict, start_response: callable) -> Iterable[bytes]:
    """
    WSGI application callable.

    Args:
        environ: Dictionary with request info and server variables
        start_response: Callable to begin response

    Returns:
        Iterable of response body bytes
    """
    status = '200 OK'
    headers = [('Content-Type', 'text/plain')]

    start_response(status, headers)

    return [b'Hello, WSGI World!']
```

### The environ Dictionary

```python
# CGI variables
environ = {
    'REQUEST_METHOD': 'GET',
    'SCRIPT_NAME': '',
    'PATH_INFO': '/hello',
    'QUERY_STRING': 'name=world',
    'CONTENT_TYPE': 'text/plain',
    'CONTENT_LENGTH': '0',
    'SERVER_NAME': 'localhost',
    'SERVER_PORT': '8080',
    'SERVER_PROTOCOL': 'HTTP/1.1',

    # HTTP headers (prefixed with HTTP_)
    'HTTP_HOST': 'localhost:8080',
    'HTTP_USER_AGENT': 'curl/7.68.0',
    'HTTP_ACCEPT': '*/*',

    # WSGI variables
    'wsgi.version': (1, 0),
    'wsgi.url_scheme': 'http',
    'wsgi.input': <file-like object>,  # Request body
    'wsgi.errors': <file-like object>,  # Error output
    'wsgi.multithread': True,
    'wsgi.multiprocess': False,
    'wsgi.run_once': False,
}
```

### The start_response Callable

```python
def start_response(status: str, response_headers: list, exc_info=None):
    """
    Begin HTTP response.

    Args:
        status: Status line like '200 OK'
        response_headers: List of (name, value) tuples
        exc_info: Exception info for error handling

    Returns:
        write() callable (deprecated, avoid using)
    """
    pass
```

---

## 15.2 Writing WSGI Applications

### Simple Application

```python
def hello_app(environ, start_response):
    """Simple hello world."""
    start_response('200 OK', [('Content-Type', 'text/plain')])
    return [b'Hello, World!']
```

### With Request Parsing

```python
from urllib.parse import parse_qs

def query_app(environ, start_response):
    """Application that reads query string."""
    query = parse_qs(environ.get('QUERY_STRING', ''))
    name = query.get('name', ['World'])[0]

    body = f'Hello, {name}!'.encode('utf-8')

    start_response('200 OK', [
        ('Content-Type', 'text/plain'),
        ('Content-Length', str(len(body)))
    ])

    return [body]
```

### Reading Request Body

```python
def echo_app(environ, start_response):
    """Echo POST body."""
    content_length = int(environ.get('CONTENT_LENGTH', 0))
    body = environ['wsgi.input'].read(content_length)

    start_response('200 OK', [
        ('Content-Type', 'text/plain'),
        ('Content-Length', str(len(body)))
    ])

    return [body]
```

### Streaming Response

```python
def stream_app(environ, start_response):
    """Streaming response."""
    def generate():
        for i in range(10):
            yield f'Chunk {i}\n'.encode()

    start_response('200 OK', [('Content-Type', 'text/plain')])
    return generate()
```

### Full Application Example

```python
import json
from urllib.parse import parse_qs

class WSGIApp:
    """Class-based WSGI application."""

    def __call__(self, environ, start_response):
        method = environ['REQUEST_METHOD']
        path = environ['PATH_INFO']

        # Routing
        if path == '/' and method == 'GET':
            return self.index(environ, start_response)
        elif path == '/api/data' and method == 'GET':
            return self.get_data(environ, start_response)
        elif path == '/api/data' and method == 'POST':
            return self.post_data(environ, start_response)
        else:
            return self.not_found(environ, start_response)

    def index(self, environ, start_response):
        body = b'<h1>Welcome</h1>'
        start_response('200 OK', [
            ('Content-Type', 'text/html'),
            ('Content-Length', str(len(body)))
        ])
        return [body]

    def get_data(self, environ, start_response):
        data = {'items': [1, 2, 3]}
        body = json.dumps(data).encode()
        start_response('200 OK', [
            ('Content-Type', 'application/json'),
            ('Content-Length', str(len(body)))
        ])
        return [body]

    def post_data(self, environ, start_response):
        length = int(environ.get('CONTENT_LENGTH', 0))
        body = environ['wsgi.input'].read(length)
        data = json.loads(body)

        response = json.dumps({'received': data}).encode()
        start_response('201 Created', [
            ('Content-Type', 'application/json'),
            ('Content-Length', str(len(response)))
        ])
        return [response]

    def not_found(self, environ, start_response):
        body = b'Not Found'
        start_response('404 Not Found', [
            ('Content-Type', 'text/plain'),
            ('Content-Length', str(len(body)))
        ])
        return [body]

application = WSGIApp()
```

---

## 15.3 WSGI Middleware

### Middleware Pattern

```python
class Middleware:
    """Base middleware class."""

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        return self.app(environ, start_response)
```

### Logging Middleware

```python
import time
import sys

class LoggingMiddleware:
    """Log requests."""

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        start = time.time()

        # Capture status
        status_code = [None]

        def custom_start_response(status, headers, exc_info=None):
            status_code[0] = status
            return start_response(status, headers, exc_info)

        # Call app
        response = self.app(environ, custom_start_response)

        # Log
        duration = time.time() - start
        print(f"{environ['REQUEST_METHOD']} {environ['PATH_INFO']} "
              f"{status_code[0]} {duration:.3f}s", file=sys.stderr)

        return response
```

### Authentication Middleware

```python
import base64

class BasicAuthMiddleware:
    """HTTP Basic authentication."""

    def __init__(self, app, users: dict):
        self.app = app
        self.users = users

    def __call__(self, environ, start_response):
        auth = environ.get('HTTP_AUTHORIZATION', '')

        if auth.startswith('Basic '):
            try:
                decoded = base64.b64decode(auth[6:]).decode()
                username, password = decoded.split(':', 1)

                if self.users.get(username) == password:
                    environ['REMOTE_USER'] = username
                    return self.app(environ, start_response)
            except:
                pass

        # Unauthorized
        start_response('401 Unauthorized', [
            ('WWW-Authenticate', 'Basic realm="Protected"'),
            ('Content-Type', 'text/plain')
        ])
        return [b'Authentication required']
```

### Composing Middleware

```python
app = WSGIApp()
app = BasicAuthMiddleware(app, {'admin': 'secret'})
app = LoggingMiddleware(app)

# Request flows: LoggingMiddleware → BasicAuthMiddleware → WSGIApp
```

---

## 15.4 Building a WSGI Server

```python
"""
Complete WSGI server implementation.
"""

import socket
import io
import sys
from typing import Callable, Dict, List, Tuple


class WSGIServer:
    """Simple WSGI server."""

    def __init__(self, host='0.0.0.0', port=8080):
        self.host = host
        self.port = port
        self.app = None

    def set_app(self, app: Callable):
        self.app = app

    def serve_forever(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.host, self.port))
        sock.listen(128)

        print(f"WSGI Server on http://{self.host}:{self.port}")

        while True:
            client, addr = sock.accept()
            self.handle_request(client)

    def handle_request(self, client: socket.socket):
        """Handle single request."""
        try:
            # Read request
            raw = client.recv(65536)
            if not raw:
                client.close()
                return

            # Parse request
            environ = self.parse_request(raw, client)

            # Call WSGI app
            response_started = [False]
            status = [None]
            headers = [None]

            def start_response(s, h, exc_info=None):
                if exc_info:
                    try:
                        if response_started[0]:
                            raise exc_info[1].with_traceback(exc_info[2])
                    finally:
                        exc_info = None

                status[0] = s
                headers[0] = h
                response_started[0] = True

                return lambda data: None  # write() callable (deprecated)

            # Get response body
            result = self.app(environ, start_response)

            # Send response
            self.send_response(client, status[0], headers[0], result)

        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
        finally:
            client.close()

    def parse_request(self, raw: bytes, client: socket.socket) -> Dict:
        """Parse HTTP request into WSGI environ."""
        # Split request
        lines = raw.split(b'\r\n')
        request_line = lines[0].decode('ascii')
        method, path, protocol = request_line.split(' ')

        # Parse headers
        headers = {}
        body_start = 0
        for i, line in enumerate(lines[1:], 1):
            if line == b'':
                body_start = i + 1
                break
            name, _, value = line.decode('ascii').partition(':')
            headers[name.strip()] = value.strip()

        # Get body
        body = b'\r\n'.join(lines[body_start:]) if body_start else b''

        # Parse path and query
        if '?' in path:
            path_info, query_string = path.split('?', 1)
        else:
            path_info, query_string = path, ''

        # Build environ
        environ = {
            'REQUEST_METHOD': method,
            'SCRIPT_NAME': '',
            'PATH_INFO': path_info,
            'QUERY_STRING': query_string,
            'CONTENT_TYPE': headers.get('Content-Type', ''),
            'CONTENT_LENGTH': headers.get('Content-Length', ''),
            'SERVER_NAME': self.host,
            'SERVER_PORT': str(self.port),
            'SERVER_PROTOCOL': protocol,

            'wsgi.version': (1, 0),
            'wsgi.url_scheme': 'http',
            'wsgi.input': io.BytesIO(body),
            'wsgi.errors': sys.stderr,
            'wsgi.multithread': False,
            'wsgi.multiprocess': False,
            'wsgi.run_once': False,
        }

        # Add HTTP headers
        for name, value in headers.items():
            key = 'HTTP_' + name.upper().replace('-', '_')
            environ[key] = value

        return environ

    def send_response(self, client: socket.socket, status: str,
                      headers: List[Tuple], body_iter):
        """Send HTTP response."""
        # Status line
        response = f"HTTP/1.1 {status}\r\n"

        # Headers
        for name, value in headers:
            response += f"{name}: {value}\r\n"
        response += "\r\n"

        client.sendall(response.encode('ascii'))

        # Body
        for chunk in body_iter:
            client.sendall(chunk)


def make_server(host, port, app):
    """Create WSGI server."""
    server = WSGIServer(host, port)
    server.set_app(app)
    return server


# Usage
if __name__ == '__main__':
    def app(environ, start_response):
        start_response('200 OK', [('Content-Type', 'text/plain')])
        return [b'Hello from WSGI Server!']

    server = make_server('0.0.0.0', 8080, app)
    server.serve_forever()
```

---

## 15.5 How Flask Uses WSGI

```python
# Flask is a WSGI application
from flask import Flask
app = Flask(__name__)

@app.route('/')
def index():
    return 'Hello'

# app is callable: app(environ, start_response)
# Run with any WSGI server:
# gunicorn app:app
# uwsgi --http :8080 --wsgi-file app.py
```

---

## Exercises

### Exercise 15.1: Static File Middleware

Implement middleware that serves static files from a directory.

### Exercise 15.2: Session Middleware

Implement cookie-based session middleware.

### Exercise 15.3: Error Handler Middleware

Implement middleware that catches exceptions and returns proper error pages.

---

## Summary

You've mastered WSGI:
1. **The spec**: environ, start_response, iterable body
2. **Applications**: Functions and classes
3. **Middleware**: Composable request/response processing
4. **Server**: Parse requests, call app, send response

---

## Next Module

**[Module 16: ASGI Deep Dive →](./MODULE_16_ASGI.md)**

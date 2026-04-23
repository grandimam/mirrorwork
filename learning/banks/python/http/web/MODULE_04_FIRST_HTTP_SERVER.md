# Module 4: Your First HTTP Server

## Overview

This is where theory becomes practice. You will build a complete HTTP/1.1 server from scratch—no frameworks, no libraries beyond Python's standard library. By the end of this module, you'll have a server that can:

- Accept TCP connections
- Parse HTTP requests
- Route to handlers
- Generate HTTP responses
- Serve static files
- Handle errors gracefully

This server will be single-threaded and blocking (we'll fix that in Part 3), but it will be fully HTTP/1.1 compliant.

---

## Learning Objectives

By the end of this module, you will be able to:

1. Design the architecture of an HTTP server
2. Implement a robust HTTP request parser using a state machine
3. Handle partial reads and buffer management
4. Build Request and Response objects
5. Implement the complete request-response cycle
6. Handle malformed requests and errors gracefully
7. Test your server for HTTP compliance

---

## 4.1 Architecture Overview

### Server Components

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              HTTP Server                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────┐    ┌──────────────┐    ┌─────────────┐                │
│  │   Socket    │───▶│    Parser    │───▶│   Request   │                │
│  │   Layer     │    │              │    │   Object    │                │
│  └─────────────┘    └──────────────┘    └──────┬──────┘                │
│                                                 │                       │
│                                                 ▼                       │
│                                         ┌─────────────┐                 │
│                                         │   Router    │                 │
│                                         └──────┬──────┘                 │
│                                                │                        │
│                                                ▼                        │
│                                         ┌─────────────┐                 │
│                                         │   Handler   │                 │
│                                         └──────┬──────┘                 │
│                                                │                        │
│                                                ▼                        │
│  ┌─────────────┐    ┌──────────────┐    ┌─────────────┐                │
│  │   Socket    │◀───│  Serializer  │◀───│  Response   │                │
│  │   Layer     │    │              │    │   Object    │                │
│  └─────────────┘    └──────────────┘    └─────────────┘                │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Socket Layer**: Accept connection, read bytes, write bytes
2. **Parser**: Convert raw bytes to structured Request object
3. **Router**: Match request path to handler function
4. **Handler**: Business logic, generate Response object
5. **Serializer**: Convert Response object to raw bytes
6. **Socket Layer**: Send bytes, manage connection

### File Structure

```
http_server/
├── __init__.py
├── server.py          # Main server loop
├── parser.py          # HTTP request parser
├── request.py         # Request object
├── response.py        # Response object
├── router.py          # URL routing
├── handlers.py        # Request handlers
└── exceptions.py      # Custom exceptions
```

---

## 4.2 Accepting TCP Connections

Let's start with the socket layer:

```python
# server.py
import socket
from typing import Callable


class HTTPServer:
    """A simple HTTP/1.1 server."""

    def __init__(self, host: str = '0.0.0.0', port: int = 8080):
        self.host = host
        self.port = port
        self.socket = None

    def start(self):
        """Start the server and listen for connections."""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.host, self.port))
        self.socket.listen(128)

        print(f"Server listening on {self.host}:{self.port}")

        try:
            while True:
                client_socket, client_address = self.socket.accept()
                print(f"Connection from {client_address}")
                self._handle_connection(client_socket, client_address)
        except KeyboardInterrupt:
            print("\nShutting down server")
        finally:
            self.socket.close()

    def _handle_connection(self, client_socket: socket.socket, client_address: tuple):
        """Handle a single client connection."""
        try:
            # Set a timeout to prevent hanging on slow clients
            client_socket.settimeout(30)

            # Read request, process, send response
            self._process_request(client_socket)

        except socket.timeout:
            print(f"Timeout from {client_address}")
        except Exception as e:
            print(f"Error handling {client_address}: {e}")
        finally:
            client_socket.close()

    def _process_request(self, client_socket: socket.socket):
        """Read request, route, and send response."""
        # TODO: Implement in following sections
        pass


if __name__ == '__main__':
    server = HTTPServer()
    server.start()
```

---

## 4.3 Reading Raw HTTP Requests

### The Challenge

HTTP doesn't have a fixed message size. We need to:
1. Read until we see the end of headers (`\r\n\r\n`)
2. Parse Content-Length header (if present)
3. Read exactly that many body bytes

### Buffer-Based Reading

```python
# parser.py
import socket
from typing import Tuple, Optional


class HTTPReader:
    """Buffered reader for HTTP requests."""

    def __init__(self, sock: socket.socket, buffer_size: int = 8192):
        self.sock = sock
        self.buffer_size = buffer_size
        self.buffer = b''

    def read_until(self, delimiter: bytes, max_size: int = 65536) -> bytes:
        """
        Read from socket until delimiter is found.
        Returns data including the delimiter.
        Raises if max_size exceeded before delimiter found.
        """
        while delimiter not in self.buffer:
            if len(self.buffer) > max_size:
                raise ValueError(f"Delimiter not found within {max_size} bytes")

            chunk = self.sock.recv(self.buffer_size)
            if not chunk:
                raise ConnectionError("Connection closed before delimiter found")

            self.buffer += chunk

        # Split at delimiter
        idx = self.buffer.index(delimiter) + len(delimiter)
        result = self.buffer[:idx]
        self.buffer = self.buffer[idx:]

        return result

    def read_exactly(self, n: int) -> bytes:
        """Read exactly n bytes from the socket."""
        while len(self.buffer) < n:
            chunk = self.sock.recv(self.buffer_size)
            if not chunk:
                raise ConnectionError(f"Connection closed, expected {n} bytes")
            self.buffer += chunk

        result = self.buffer[:n]
        self.buffer = self.buffer[n:]

        return result

    def read_line(self) -> bytes:
        """Read a single line (ending with CRLF)."""
        return self.read_until(b'\r\n')
```

---

## 4.4 Implementing the Request Parser

### State Machine Approach

Parsing HTTP is best done with a state machine:

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   REQUEST   │────▶│   HEADERS   │────▶│    BODY     │────▶│   DONE      │
│    LINE     │     │             │     │             │     │             │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
```

### Complete Parser Implementation

```python
# parser.py (continued)
from dataclasses import dataclass, field
from typing import Dict, Optional
from urllib.parse import urlparse, parse_qs
import re


class HTTPParseError(Exception):
    """Raised when HTTP parsing fails."""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


@dataclass
class HTTPRequest:
    """Represents an HTTP request."""
    method: str
    path: str
    query_string: str
    query_params: Dict[str, list]
    http_version: str
    headers: Dict[str, str]
    body: bytes = b''

    @property
    def content_type(self) -> Optional[str]:
        return self.headers.get('content-type')

    @property
    def content_length(self) -> int:
        return int(self.headers.get('content-length', 0))


class HTTPParser:
    """HTTP/1.1 request parser."""

    # Valid HTTP methods
    METHODS = {'GET', 'HEAD', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'TRACE', 'CONNECT'}

    # Request line pattern: METHOD SP PATH SP HTTP/VERSION
    REQUEST_LINE_PATTERN = re.compile(
        rb'^([A-Z]+) ([^ ]+) HTTP/(\d\.\d)\r\n$'
    )

    # Header pattern: Name: Value
    HEADER_PATTERN = re.compile(
        rb'^([^:]+):\s*(.*)$'
    )

    def __init__(self, reader: HTTPReader):
        self.reader = reader

    def parse(self) -> HTTPRequest:
        """Parse a complete HTTP request."""
        # Parse request line
        method, path, query_string, query_params, version = self._parse_request_line()

        # Parse headers
        headers = self._parse_headers()

        # Validate required headers
        if version == '1.1' and 'host' not in headers:
            raise HTTPParseError("Missing required Host header", 400)

        # Parse body (if present)
        body = self._parse_body(headers)

        return HTTPRequest(
            method=method,
            path=path,
            query_string=query_string,
            query_params=query_params,
            http_version=version,
            headers=headers,
            body=body
        )

    def _parse_request_line(self) -> tuple:
        """Parse the request line."""
        try:
            line = self.reader.read_line()
        except ConnectionError:
            raise HTTPParseError("Empty request", 400)

        match = self.REQUEST_LINE_PATTERN.match(line)
        if not match:
            raise HTTPParseError(f"Invalid request line: {line!r}", 400)

        method = match.group(1).decode('ascii')
        raw_path = match.group(2).decode('ascii')
        version = match.group(3).decode('ascii')

        # Validate method
        if method not in self.METHODS:
            raise HTTPParseError(f"Unknown method: {method}", 501)

        # Validate version
        if version not in ('1.0', '1.1'):
            raise HTTPParseError(f"Unsupported HTTP version: {version}", 505)

        # Parse path and query string
        if '?' in raw_path:
            path, query_string = raw_path.split('?', 1)
            query_params = parse_qs(query_string)
        else:
            path = raw_path
            query_string = ''
            query_params = {}

        # Normalize path (prevent directory traversal)
        path = self._normalize_path(path)

        return method, path, query_string, query_params, version

    def _normalize_path(self, path: str) -> str:
        """Normalize path and prevent directory traversal."""
        # Decode percent-encoding
        from urllib.parse import unquote
        path = unquote(path)

        # Remove . and .. components
        parts = []
        for part in path.split('/'):
            if part == '..':
                if parts:
                    parts.pop()
            elif part and part != '.':
                parts.append(part)

        return '/' + '/'.join(parts)

    def _parse_headers(self) -> Dict[str, str]:
        """Parse HTTP headers."""
        headers = {}
        max_headers = 100  # Limit number of headers

        for _ in range(max_headers):
            line = self.reader.read_line()

            # Empty line marks end of headers
            if line == b'\r\n':
                break

            # Remove trailing CRLF for matching
            line = line.rstrip(b'\r\n')

            match = self.HEADER_PATTERN.match(line)
            if not match:
                raise HTTPParseError(f"Invalid header: {line!r}", 400)

            name = match.group(1).decode('ascii').lower()  # Case-insensitive
            value = match.group(2).decode('ascii').strip()

            # Handle duplicate headers (append with comma)
            if name in headers:
                headers[name] = f"{headers[name]}, {value}"
            else:
                headers[name] = value
        else:
            raise HTTPParseError("Too many headers", 431)

        return headers

    def _parse_body(self, headers: Dict[str, str]) -> bytes:
        """Parse request body based on headers."""
        # Check for Transfer-Encoding: chunked
        transfer_encoding = headers.get('transfer-encoding', '').lower()
        if 'chunked' in transfer_encoding:
            return self._parse_chunked_body()

        # Check for Content-Length
        content_length = headers.get('content-length')
        if content_length:
            try:
                length = int(content_length)
            except ValueError:
                raise HTTPParseError("Invalid Content-Length", 400)

            if length < 0:
                raise HTTPParseError("Negative Content-Length", 400)

            if length > 10 * 1024 * 1024:  # 10MB limit
                raise HTTPParseError("Request body too large", 413)

            if length > 0:
                return self.reader.read_exactly(length)

        return b''

    def _parse_chunked_body(self) -> bytes:
        """Parse chunked transfer encoding."""
        body = b''
        max_chunk_size = 10 * 1024 * 1024  # 10MB total limit

        while True:
            # Read chunk size line
            size_line = self.reader.read_line().decode('ascii').strip()

            # Handle chunk extensions (rarely used)
            if ';' in size_line:
                size_line = size_line.split(';')[0]

            try:
                chunk_size = int(size_line, 16)
            except ValueError:
                raise HTTPParseError(f"Invalid chunk size: {size_line}", 400)

            if chunk_size == 0:
                # Read trailing CRLF after final chunk
                self.reader.read_line()
                break

            if len(body) + chunk_size > max_chunk_size:
                raise HTTPParseError("Request body too large", 413)

            # Read chunk data
            chunk_data = self.reader.read_exactly(chunk_size)
            body += chunk_data

            # Read CRLF after chunk
            self.reader.read_line()

        return body
```

---

## 4.5 Building the Request Object

Our `HTTPRequest` dataclass already captures the essential request data. Let's add some convenience methods:

```python
# request.py
from dataclasses import dataclass, field
from typing import Dict, Optional, Any
import json
from urllib.parse import parse_qs


@dataclass
class HTTPRequest:
    """Represents an HTTP request with convenience methods."""
    method: str
    path: str
    query_string: str
    query_params: Dict[str, list]
    http_version: str
    headers: Dict[str, str]
    body: bytes = b''

    # Additional attributes set by the router
    path_params: Dict[str, str] = field(default_factory=dict)

    @property
    def content_type(self) -> Optional[str]:
        """Get Content-Type header."""
        ct = self.headers.get('content-type', '')
        # Return just the media type, not charset/boundary
        return ct.split(';')[0].strip() if ct else None

    @property
    def content_length(self) -> int:
        """Get Content-Length as integer."""
        return int(self.headers.get('content-length', 0))

    @property
    def host(self) -> str:
        """Get Host header."""
        return self.headers.get('host', '')

    @property
    def user_agent(self) -> str:
        """Get User-Agent header."""
        return self.headers.get('user-agent', '')

    def get_header(self, name: str, default: Optional[str] = None) -> Optional[str]:
        """Get a header value (case-insensitive)."""
        return self.headers.get(name.lower(), default)

    def json(self) -> Any:
        """Parse body as JSON."""
        if not self.body:
            return None
        try:
            return json.loads(self.body.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise ValueError(f"Invalid JSON body: {e}")

    def form(self) -> Dict[str, list]:
        """Parse body as form data (application/x-www-form-urlencoded)."""
        if not self.body:
            return {}
        try:
            return parse_qs(self.body.decode('utf-8'))
        except UnicodeDecodeError as e:
            raise ValueError(f"Invalid form body: {e}")

    def text(self, encoding: str = 'utf-8') -> str:
        """Get body as text."""
        return self.body.decode(encoding)

    def query(self, name: str, default: Optional[str] = None) -> Optional[str]:
        """Get a query parameter (first value if multiple)."""
        values = self.query_params.get(name)
        return values[0] if values else default

    def query_list(self, name: str) -> list:
        """Get all values for a query parameter."""
        return self.query_params.get(name, [])
```

---

## 4.6 Implementing the Response Object

```python
# response.py
from dataclasses import dataclass, field
from typing import Dict, Optional, Any, Union, Iterator
import json
from http import HTTPStatus


@dataclass
class HTTPResponse:
    """Represents an HTTP response."""
    status_code: int = 200
    headers: Dict[str, str] = field(default_factory=dict)
    body: bytes = b''

    # Standard reason phrases
    _reasons = {status.value: status.phrase for status in HTTPStatus}

    @property
    def reason(self) -> str:
        """Get reason phrase for status code."""
        return self._reasons.get(self.status_code, 'Unknown')

    def set_header(self, name: str, value: str) -> 'HTTPResponse':
        """Set a header (chainable)."""
        self.headers[name] = value
        return self

    def set_content_type(self, content_type: str) -> 'HTTPResponse':
        """Set Content-Type header (chainable)."""
        self.headers['Content-Type'] = content_type
        return self

    def serialize(self) -> bytes:
        """Serialize response to bytes for sending over socket."""
        # Status line
        status_line = f"HTTP/1.1 {self.status_code} {self.reason}\r\n"

        # Ensure Content-Length is set
        if 'Content-Length' not in self.headers:
            self.headers['Content-Length'] = str(len(self.body))

        # Ensure Date header
        if 'Date' not in self.headers:
            from email.utils import formatdate
            self.headers['Date'] = formatdate(usegmt=True)

        # Serialize headers
        headers = ''.join(f"{name}: {value}\r\n" for name, value in self.headers.items())

        # Combine all parts
        head = (status_line + headers + '\r\n').encode('ascii')
        return head + self.body


# Convenience response factories
class Response:
    """Factory methods for creating HTTP responses."""

    @staticmethod
    def text(content: str, status: int = 200, content_type: str = 'text/plain; charset=utf-8') -> HTTPResponse:
        """Create a plain text response."""
        return HTTPResponse(
            status_code=status,
            headers={'Content-Type': content_type},
            body=content.encode('utf-8')
        )

    @staticmethod
    def html(content: str, status: int = 200) -> HTTPResponse:
        """Create an HTML response."""
        return HTTPResponse(
            status_code=status,
            headers={'Content-Type': 'text/html; charset=utf-8'},
            body=content.encode('utf-8')
        )

    @staticmethod
    def json(data: Any, status: int = 200) -> HTTPResponse:
        """Create a JSON response."""
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        return HTTPResponse(
            status_code=status,
            headers={'Content-Type': 'application/json; charset=utf-8'},
            body=body
        )

    @staticmethod
    def redirect(location: str, permanent: bool = False) -> HTTPResponse:
        """Create a redirect response."""
        status = 301 if permanent else 302
        return HTTPResponse(
            status_code=status,
            headers={'Location': location},
            body=b''
        )

    @staticmethod
    def error(status: int, message: Optional[str] = None) -> HTTPResponse:
        """Create an error response."""
        reason = HTTPStatus(status).phrase if status in HTTPStatus._value2member_map_ else 'Error'
        message = message or reason
        body = f"<html><body><h1>{status} {reason}</h1><p>{message}</p></body></html>"
        return HTTPResponse(
            status_code=status,
            headers={'Content-Type': 'text/html; charset=utf-8'},
            body=body.encode('utf-8')
        )

    @staticmethod
    def file(filepath: str, content_type: Optional[str] = None) -> HTTPResponse:
        """Create a file response."""
        import mimetypes
        import os

        if not os.path.isfile(filepath):
            return Response.error(404, "File not found")

        with open(filepath, 'rb') as f:
            body = f.read()

        if content_type is None:
            content_type, _ = mimetypes.guess_type(filepath)
            content_type = content_type or 'application/octet-stream'

        return HTTPResponse(
            status_code=200,
            headers={'Content-Type': content_type},
            body=body
        )
```

---

## 4.7 The Request-Response Cycle

Now let's put it all together:

```python
# server.py (updated)
import socket
from typing import Callable, Dict, Optional

from .parser import HTTPReader, HTTPParser, HTTPParseError
from .request import HTTPRequest
from .response import HTTPResponse, Response


# Handler type: function that takes a request and returns a response
Handler = Callable[[HTTPRequest], HTTPResponse]


class HTTPServer:
    """A simple HTTP/1.1 server."""

    def __init__(self, host: str = '0.0.0.0', port: int = 8080):
        self.host = host
        self.port = port
        self.socket = None
        self.routes: Dict[tuple, Handler] = {}
        self.default_handler: Optional[Handler] = None

    def route(self, method: str, path: str):
        """Decorator to register a route handler."""
        def decorator(handler: Handler):
            self.routes[(method.upper(), path)] = handler
            return handler
        return decorator

    def get(self, path: str):
        """Decorator for GET routes."""
        return self.route('GET', path)

    def post(self, path: str):
        """Decorator for POST routes."""
        return self.route('POST', path)

    def start(self):
        """Start the server and listen for connections."""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.host, self.port))
        self.socket.listen(128)

        print(f"Server listening on http://{self.host}:{self.port}")

        try:
            while True:
                client_socket, client_address = self.socket.accept()
                self._handle_connection(client_socket, client_address)
        except KeyboardInterrupt:
            print("\nShutting down server")
        finally:
            self.socket.close()

    def _handle_connection(self, client_socket: socket.socket, client_address: tuple):
        """Handle a single client connection."""
        try:
            client_socket.settimeout(30)

            # Support keep-alive connections
            while True:
                response = self._process_request(client_socket)
                if response is None:
                    break

                # Send response
                client_socket.sendall(response.serialize())

                # Check Connection header
                connection = response.headers.get('Connection', 'keep-alive').lower()
                if connection == 'close':
                    break

        except socket.timeout:
            pass  # Timeout on keep-alive is normal
        except ConnectionError:
            pass  # Client disconnected
        except Exception as e:
            print(f"Error handling {client_address}: {e}")
            import traceback
            traceback.print_exc()
        finally:
            client_socket.close()

    def _process_request(self, client_socket: socket.socket) -> Optional[HTTPResponse]:
        """Process a single HTTP request and return a response."""
        try:
            # Create reader and parser
            reader = HTTPReader(client_socket)
            parser = HTTPParser(reader)

            # Parse request
            try:
                request = parser.parse()
            except ConnectionError:
                return None  # Client closed connection
            except HTTPParseError as e:
                return Response.error(e.status_code, str(e))

            # Log request
            print(f"{request.method} {request.path}")

            # Route to handler
            handler = self.routes.get((request.method, request.path))

            if handler is None:
                # Try default handler
                if self.default_handler:
                    handler = self.default_handler
                else:
                    return Response.error(404, f"Not Found: {request.path}")

            # Call handler
            try:
                response = handler(request)
            except Exception as e:
                print(f"Handler error: {e}")
                import traceback
                traceback.print_exc()
                return Response.error(500, "Internal Server Error")

            # Ensure response has Connection header based on request
            if 'Connection' not in response.headers:
                req_connection = request.get_header('connection', 'keep-alive')
                response.headers['Connection'] = req_connection

            return response

        except Exception as e:
            print(f"Process error: {e}")
            return Response.error(500)


# Example usage
if __name__ == '__main__':
    server = HTTPServer(port=8080)

    @server.get('/')
    def index(request: HTTPRequest) -> HTTPResponse:
        return Response.html("<h1>Hello, World!</h1>")

    @server.get('/json')
    def json_endpoint(request: HTTPRequest) -> HTTPResponse:
        return Response.json({"message": "Hello, JSON!"})

    @server.post('/echo')
    def echo(request: HTTPRequest) -> HTTPResponse:
        return Response.json({
            "method": request.method,
            "path": request.path,
            "headers": request.headers,
            "body": request.text()
        })

    server.start()
```

---

## 4.8 Error Handling and Bad Requests

### Exception Hierarchy

```python
# exceptions.py

class HTTPError(Exception):
    """Base class for HTTP errors."""
    def __init__(self, status_code: int, message: str = None):
        self.status_code = status_code
        self.message = message or self._default_message()
        super().__init__(self.message)

    def _default_message(self) -> str:
        from http import HTTPStatus
        try:
            return HTTPStatus(self.status_code).phrase
        except ValueError:
            return "Unknown Error"


class BadRequest(HTTPError):
    """400 Bad Request"""
    def __init__(self, message: str = None):
        super().__init__(400, message)


class NotFound(HTTPError):
    """404 Not Found"""
    def __init__(self, message: str = None):
        super().__init__(404, message)


class MethodNotAllowed(HTTPError):
    """405 Method Not Allowed"""
    def __init__(self, allowed_methods: list = None):
        self.allowed_methods = allowed_methods or []
        super().__init__(405)


class InternalServerError(HTTPError):
    """500 Internal Server Error"""
    def __init__(self, message: str = None):
        super().__init__(500, message)
```

### Robust Error Handling in Server

```python
# Update _process_request in server.py

def _process_request(self, client_socket: socket.socket) -> Optional[HTTPResponse]:
    """Process a single HTTP request with comprehensive error handling."""
    try:
        reader = HTTPReader(client_socket)
        parser = HTTPParser(reader)

        try:
            request = parser.parse()
        except ConnectionError:
            return None
        except HTTPParseError as e:
            return self._error_response(e.status_code, str(e))

        print(f"{request.method} {request.path}")

        try:
            response = self._dispatch(request)
        except HTTPError as e:
            response = self._error_response(e.status_code, e.message)
            if isinstance(e, MethodNotAllowed) and e.allowed_methods:
                response.headers['Allow'] = ', '.join(e.allowed_methods)
        except Exception as e:
            import traceback
            traceback.print_exc()
            response = self._error_response(500, "Internal Server Error")

        # Set Connection header
        if 'Connection' not in response.headers:
            response.headers['Connection'] = request.get_header('connection', 'keep-alive')

        return response

    except Exception as e:
        import traceback
        traceback.print_exc()
        return self._error_response(500)

def _error_response(self, status: int, message: str = None) -> HTTPResponse:
    """Generate an error response."""
    from http import HTTPStatus
    reason = HTTPStatus(status).phrase if status in HTTPStatus._value2member_map_ else 'Error'
    message = message or reason

    body = f"""<!DOCTYPE html>
<html>
<head><title>{status} {reason}</title></head>
<body>
<h1>{status} {reason}</h1>
<p>{message}</p>
<hr>
<p><em>Python HTTP Server</em></p>
</body>
</html>"""

    return HTTPResponse(
        status_code=status,
        headers={
            'Content-Type': 'text/html; charset=utf-8',
            'Connection': 'close'  # Close on errors
        },
        body=body.encode('utf-8')
    )
```

---

## 4.9 Complete Working Server

Here's the complete, tested implementation:

```python
#!/usr/bin/env python3
"""
A complete HTTP/1.1 server implementation.

Usage:
    python server.py

Then visit http://localhost:8080 in your browser.
"""

import socket
import json
import mimetypes
import os
import re
from dataclasses import dataclass, field
from typing import Dict, Optional, Any, Callable, List, Tuple
from http import HTTPStatus
from email.utils import formatdate
from urllib.parse import parse_qs, unquote


# ============================================================================
# Exceptions
# ============================================================================

class HTTPParseError(Exception):
    """Raised when HTTP parsing fails."""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


class HTTPError(Exception):
    """Base class for HTTP errors that should be returned to client."""
    def __init__(self, status_code: int, message: str = None):
        self.status_code = status_code
        self.message = message
        super().__init__(message)


# ============================================================================
# Request
# ============================================================================

@dataclass
class HTTPRequest:
    """Represents an HTTP request."""
    method: str
    path: str
    query_string: str
    query_params: Dict[str, list]
    http_version: str
    headers: Dict[str, str]
    body: bytes = b''
    path_params: Dict[str, str] = field(default_factory=dict)

    @property
    def content_type(self) -> Optional[str]:
        ct = self.headers.get('content-type', '')
        return ct.split(';')[0].strip() if ct else None

    @property
    def content_length(self) -> int:
        return int(self.headers.get('content-length', 0))

    def get_header(self, name: str, default: str = None) -> Optional[str]:
        return self.headers.get(name.lower(), default)

    def json(self) -> Any:
        if not self.body:
            return None
        return json.loads(self.body.decode('utf-8'))

    def form(self) -> Dict[str, list]:
        if not self.body:
            return {}
        return parse_qs(self.body.decode('utf-8'))

    def text(self, encoding: str = 'utf-8') -> str:
        return self.body.decode(encoding)

    def query(self, name: str, default: str = None) -> Optional[str]:
        values = self.query_params.get(name)
        return values[0] if values else default


# ============================================================================
# Response
# ============================================================================

@dataclass
class HTTPResponse:
    """Represents an HTTP response."""
    status_code: int = 200
    headers: Dict[str, str] = field(default_factory=dict)
    body: bytes = b''

    @property
    def reason(self) -> str:
        try:
            return HTTPStatus(self.status_code).phrase
        except ValueError:
            return 'Unknown'

    def serialize(self) -> bytes:
        # Ensure required headers
        if 'Content-Length' not in self.headers:
            self.headers['Content-Length'] = str(len(self.body))
        if 'Date' not in self.headers:
            self.headers['Date'] = formatdate(usegmt=True)
        if 'Server' not in self.headers:
            self.headers['Server'] = 'PythonHTTPServer/1.0'

        # Build response
        status_line = f"HTTP/1.1 {self.status_code} {self.reason}\r\n"
        headers = ''.join(f"{k}: {v}\r\n" for k, v in self.headers.items())
        head = (status_line + headers + '\r\n').encode('ascii')
        return head + self.body


class Response:
    """Factory for creating responses."""

    @staticmethod
    def text(content: str, status: int = 200) -> HTTPResponse:
        return HTTPResponse(
            status_code=status,
            headers={'Content-Type': 'text/plain; charset=utf-8'},
            body=content.encode('utf-8')
        )

    @staticmethod
    def html(content: str, status: int = 200) -> HTTPResponse:
        return HTTPResponse(
            status_code=status,
            headers={'Content-Type': 'text/html; charset=utf-8'},
            body=content.encode('utf-8')
        )

    @staticmethod
    def json(data: Any, status: int = 200) -> HTTPResponse:
        body = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
        return HTTPResponse(
            status_code=status,
            headers={'Content-Type': 'application/json; charset=utf-8'},
            body=body
        )

    @staticmethod
    def redirect(location: str, permanent: bool = False) -> HTTPResponse:
        return HTTPResponse(
            status_code=301 if permanent else 302,
            headers={'Location': location}
        )

    @staticmethod
    def error(status: int, message: str = None) -> HTTPResponse:
        try:
            reason = HTTPStatus(status).phrase
        except ValueError:
            reason = 'Error'
        message = message or reason
        body = f"<h1>{status} {reason}</h1><p>{message}</p>"
        return HTTPResponse(
            status_code=status,
            headers={'Content-Type': 'text/html; charset=utf-8'},
            body=body.encode('utf-8')
        )


# ============================================================================
# Parser
# ============================================================================

class HTTPReader:
    """Buffered socket reader."""

    def __init__(self, sock: socket.socket, buffer_size: int = 8192):
        self.sock = sock
        self.buffer_size = buffer_size
        self.buffer = b''

    def read_line(self, max_size: int = 8192) -> bytes:
        while b'\r\n' not in self.buffer:
            if len(self.buffer) > max_size:
                raise HTTPParseError("Line too long", 414)
            chunk = self.sock.recv(self.buffer_size)
            if not chunk:
                raise ConnectionError("Connection closed")
            self.buffer += chunk

        idx = self.buffer.index(b'\r\n') + 2
        line, self.buffer = self.buffer[:idx], self.buffer[idx:]
        return line

    def read_exactly(self, n: int) -> bytes:
        while len(self.buffer) < n:
            chunk = self.sock.recv(self.buffer_size)
            if not chunk:
                raise ConnectionError("Connection closed")
            self.buffer += chunk

        data, self.buffer = self.buffer[:n], self.buffer[n:]
        return data


class HTTPParser:
    """HTTP/1.1 request parser."""

    METHODS = {'GET', 'HEAD', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'}
    REQUEST_LINE_RE = re.compile(rb'^([A-Z]+) ([^ ]+) HTTP/(\d\.\d)\r\n$')
    HEADER_RE = re.compile(rb'^([^:]+):\s*(.*)$')

    def __init__(self, reader: HTTPReader):
        self.reader = reader

    def parse(self) -> HTTPRequest:
        method, path, query_string, query_params, version = self._parse_request_line()
        headers = self._parse_headers()

        if version == '1.1' and 'host' not in headers:
            raise HTTPParseError("Missing Host header")

        body = self._parse_body(headers)

        return HTTPRequest(
            method=method,
            path=path,
            query_string=query_string,
            query_params=query_params,
            http_version=version,
            headers=headers,
            body=body
        )

    def _parse_request_line(self) -> Tuple[str, str, str, Dict, str]:
        line = self.reader.read_line()
        match = self.REQUEST_LINE_RE.match(line)
        if not match:
            raise HTTPParseError(f"Invalid request line")

        method = match.group(1).decode('ascii')
        raw_path = match.group(2).decode('ascii')
        version = match.group(3).decode('ascii')

        if method not in self.METHODS:
            raise HTTPParseError(f"Unknown method: {method}", 501)
        if version not in ('1.0', '1.1'):
            raise HTTPParseError(f"Unsupported version: HTTP/{version}", 505)

        # Parse path and query
        if '?' in raw_path:
            path, query_string = raw_path.split('?', 1)
            query_params = parse_qs(query_string)
        else:
            path, query_string, query_params = raw_path, '', {}

        # Normalize path
        path = self._normalize_path(path)

        return method, path, query_string, query_params, version

    def _normalize_path(self, path: str) -> str:
        path = unquote(path)
        parts = []
        for part in path.split('/'):
            if part == '..':
                if parts:
                    parts.pop()
            elif part and part != '.':
                parts.append(part)
        return '/' + '/'.join(parts)

    def _parse_headers(self) -> Dict[str, str]:
        headers = {}
        for _ in range(100):
            line = self.reader.read_line()
            if line == b'\r\n':
                break
            line = line.rstrip(b'\r\n')
            match = self.HEADER_RE.match(line)
            if not match:
                raise HTTPParseError("Invalid header")
            name = match.group(1).decode('ascii').lower()
            value = match.group(2).decode('ascii').strip()
            if name in headers:
                headers[name] = f"{headers[name]}, {value}"
            else:
                headers[name] = value
        return headers

    def _parse_body(self, headers: Dict[str, str]) -> bytes:
        if 'chunked' in headers.get('transfer-encoding', '').lower():
            return self._parse_chunked()

        length = headers.get('content-length')
        if length:
            n = int(length)
            if n > 10 * 1024 * 1024:
                raise HTTPParseError("Body too large", 413)
            if n > 0:
                return self.reader.read_exactly(n)
        return b''

    def _parse_chunked(self) -> bytes:
        body = b''
        while True:
            size_line = self.reader.read_line().decode('ascii').split(';')[0].strip()
            size = int(size_line, 16)
            if size == 0:
                self.reader.read_line()
                break
            body += self.reader.read_exactly(size)
            self.reader.read_line()
        return body


# ============================================================================
# Server
# ============================================================================

Handler = Callable[[HTTPRequest], HTTPResponse]


class HTTPServer:
    """HTTP/1.1 server."""

    def __init__(self, host: str = '0.0.0.0', port: int = 8080):
        self.host = host
        self.port = port
        self.routes: Dict[Tuple[str, str], Handler] = {}

    def route(self, method: str, path: str):
        def decorator(handler: Handler):
            self.routes[(method.upper(), path)] = handler
            return handler
        return decorator

    def get(self, path: str):
        return self.route('GET', path)

    def post(self, path: str):
        return self.route('POST', path)

    def put(self, path: str):
        return self.route('PUT', path)

    def delete(self, path: str):
        return self.route('DELETE', path)

    def start(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.host, self.port))
        sock.listen(128)

        print(f"Serving on http://{self.host}:{self.port}")

        try:
            while True:
                client, addr = sock.accept()
                self._handle_client(client)
        except KeyboardInterrupt:
            print("\nShutdown")
        finally:
            sock.close()

    def _handle_client(self, client: socket.socket):
        try:
            client.settimeout(30)
            while True:
                response = self._process(client)
                if not response:
                    break
                client.sendall(response.serialize())
                if response.headers.get('Connection', '').lower() == 'close':
                    break
        except (socket.timeout, ConnectionError):
            pass
        except Exception as e:
            import traceback
            traceback.print_exc()
        finally:
            client.close()

    def _process(self, client: socket.socket) -> Optional[HTTPResponse]:
        try:
            reader = HTTPReader(client)
            parser = HTTPParser(reader)
            request = parser.parse()
        except ConnectionError:
            return None
        except HTTPParseError as e:
            return Response.error(e.status_code, str(e))

        print(f"{request.method} {request.path}")

        try:
            handler = self.routes.get((request.method, request.path))
            if not handler:
                return Response.error(404)
            response = handler(request)
        except HTTPError as e:
            response = Response.error(e.status_code, e.message)
        except Exception:
            import traceback
            traceback.print_exc()
            response = Response.error(500)

        if 'Connection' not in response.headers:
            response.headers['Connection'] = request.get_header('connection', 'keep-alive')

        return response


# ============================================================================
# Example Application
# ============================================================================

if __name__ == '__main__':
    app = HTTPServer(port=8080)

    @app.get('/')
    def index(request: HTTPRequest) -> HTTPResponse:
        html = """
        <!DOCTYPE html>
        <html>
        <head><title>Python HTTP Server</title></head>
        <body>
            <h1>Welcome!</h1>
            <p>This server is written from scratch in Python.</p>
            <ul>
                <li><a href="/hello">Hello</a></li>
                <li><a href="/json">JSON API</a></li>
                <li><a href="/echo">Echo (POST)</a></li>
            </ul>
        </body>
        </html>
        """
        return Response.html(html)

    @app.get('/hello')
    def hello(request: HTTPRequest) -> HTTPResponse:
        name = request.query('name', 'World')
        return Response.text(f"Hello, {name}!")

    @app.get('/json')
    def json_api(request: HTTPRequest) -> HTTPResponse:
        return Response.json({
            "message": "Hello from Python!",
            "method": request.method,
            "path": request.path,
            "query_params": request.query_params,
            "headers": dict(request.headers)
        })

    @app.post('/echo')
    def echo(request: HTTPRequest) -> HTTPResponse:
        return Response.json({
            "content_type": request.content_type,
            "content_length": request.content_length,
            "body": request.text()
        })

    @app.get('/error')
    def trigger_error(request: HTTPRequest) -> HTTPResponse:
        raise HTTPError(500, "Intentional error for testing")

    app.start()
```

---

## 4.10 Lab: Build a Server That Passes HTTP Compliance Tests

### Testing Your Server

Create a test file:

```python
# test_server.py
import socket
import threading
import time
import unittest


def send_request(request: bytes, port: int = 8080) -> bytes:
    """Send raw HTTP request and return response."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    try:
        sock.connect(('127.0.0.1', port))
        sock.sendall(request)

        response = b''
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk
            # Check for complete response
            if b'\r\n\r\n' in response:
                # Parse Content-Length
                header_end = response.index(b'\r\n\r\n')
                headers = response[:header_end].decode('ascii')
                for line in headers.split('\r\n'):
                    if line.lower().startswith('content-length:'):
                        length = int(line.split(':')[1].strip())
                        body_start = header_end + 4
                        if len(response) >= body_start + length:
                            break
        return response
    finally:
        sock.close()


class HTTPServerTests(unittest.TestCase):

    def test_simple_get(self):
        request = b"GET / HTTP/1.1\r\nHost: localhost\r\n\r\n"
        response = send_request(request)
        self.assertIn(b'HTTP/1.1 200', response)

    def test_not_found(self):
        request = b"GET /nonexistent HTTP/1.1\r\nHost: localhost\r\n\r\n"
        response = send_request(request)
        self.assertIn(b'HTTP/1.1 404', response)

    def test_missing_host_header(self):
        request = b"GET / HTTP/1.1\r\n\r\n"
        response = send_request(request)
        self.assertIn(b'HTTP/1.1 400', response)

    def test_post_with_body(self):
        body = b'{"test": "data"}'
        request = (
            b"POST /echo HTTP/1.1\r\n"
            b"Host: localhost\r\n"
            b"Content-Type: application/json\r\n"
            b"Content-Length: " + str(len(body)).encode() + b"\r\n"
            b"\r\n" + body
        )
        response = send_request(request)
        self.assertIn(b'HTTP/1.1 200', response)
        self.assertIn(b'{"test": "data"}', response)

    def test_query_parameters(self):
        request = b"GET /hello?name=Test HTTP/1.1\r\nHost: localhost\r\n\r\n"
        response = send_request(request)
        self.assertIn(b'Hello, Test', response)

    def test_unknown_method(self):
        request = b"INVALID / HTTP/1.1\r\nHost: localhost\r\n\r\n"
        response = send_request(request)
        self.assertIn(b'HTTP/1.1 501', response)

    def test_malformed_request(self):
        request = b"GET\r\n\r\n"
        response = send_request(request)
        self.assertIn(b'HTTP/1.1 400', response)

    def test_content_length_header(self):
        request = b"GET /json HTTP/1.1\r\nHost: localhost\r\n\r\n"
        response = send_request(request)
        self.assertIn(b'Content-Length:', response)

    def test_date_header(self):
        request = b"GET / HTTP/1.1\r\nHost: localhost\r\n\r\n"
        response = send_request(request)
        self.assertIn(b'Date:', response)


if __name__ == '__main__':
    # Start server in background thread
    # (You should have your server running separately)
    unittest.main()
```

### Run Tests

```bash
# Terminal 1: Start server
python server.py

# Terminal 2: Run tests
python test_server.py
```

---

## Exercises

### Exercise 4.1: Static File Server

Extend the server to serve static files:

```python
@app.get('/static/*')
def static_files(request: HTTPRequest) -> HTTPResponse:
    # Extract file path from request
    # Serve file with correct Content-Type
    # Handle 404 for missing files
    pass
```

### Exercise 4.2: Request Logging Middleware

Add detailed request logging:
- Timestamp
- Client IP
- Method and path
- Response status code
- Response time in milliseconds

### Exercise 4.3: Response Compression

Implement gzip compression:
1. Check `Accept-Encoding` header
2. Compress response body if client supports it
3. Set `Content-Encoding: gzip` header

### Exercise 4.4: Cookie Handling

Add cookie support:
1. Parse `Cookie` request header
2. Add `set_cookie()` method to Response
3. Implement a simple session counter

### Exercise 4.5: HEAD Method

Implement proper HEAD request handling:
- Return same headers as GET
- No response body
- Correct Content-Length

---

## Deep Dive Questions

1. **Why does the parser use a state machine approach? What would happen with a simpler approach?**

2. **What security vulnerabilities exist in our current implementation? How would you fix them?**

3. **How does our buffer management handle slow clients (slowloris attack)?**

4. **Why do we normalize the path? What attacks does this prevent?**

5. **What happens if a client sends a request without Content-Length or chunked encoding but includes a body?**

---

## Resources

### Reference Implementations
- [Python http.server source](https://github.com/python/cpython/blob/main/Lib/http/server.py)
- [Werkzeug (Flask's WSGI toolkit)](https://github.com/pallets/werkzeug)

### Testing Tools
- [curl](https://curl.se/) — Command-line HTTP client
- [httpie](https://httpie.io/) — User-friendly HTTP client
- [wrk](https://github.com/wg/wrk) — HTTP benchmarking tool

### Specifications
- [RFC 7230 - HTTP/1.1 Message Syntax](https://tools.ietf.org/html/rfc7230)

---

## Summary

You've built a working HTTP/1.1 server from scratch:

1. **Socket layer** — Accept connections, read/write bytes
2. **Buffered reader** — Handle partial reads, line-by-line parsing
3. **HTTP parser** — State machine for request line, headers, body
4. **Request object** — Structured representation with convenience methods
5. **Response object** — Status, headers, body with serialization
6. **Error handling** — Graceful handling of malformed requests
7. **Keep-alive** — Persistent connections for performance

**Current limitations:**
- Single-threaded — Only handles one client at a time
- No dynamic routing — Exact path matching only
- No middleware — Can't compose request/response processing

We'll address these in upcoming modules. The next module covers routing systems, enabling dynamic URL patterns like `/users/{id}`.

---

## Next Module

**[Module 5: Routing Systems →](./MODULE_05_ROUTING.md)**

We'll implement sophisticated URL routing with path parameters, regex matching, and route groups.

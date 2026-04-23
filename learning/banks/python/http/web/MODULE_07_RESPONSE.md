# Module 7: Response Generation

## Overview

A web server's job is to generate responses. This module covers everything you need to create responses: from simple text and JSON to streaming files, compressed content, and Server-Sent Events. You'll build a response system that's both powerful and ergonomic.

---

## Learning Objectives

By the end of this module, you will be able to:

1. Design flexible Response objects
2. Serialize responses correctly to HTTP format
3. Generate responses for all common content types
4. Stream large responses efficiently
5. Implement compression (gzip, deflate, brotli)
6. Serve static files with caching headers
7. Implement range requests for partial content
8. Create Server-Sent Events streams

---

## 7.1 Response Object Design

### Core Response Class

```python
from dataclasses import dataclass, field
from typing import Dict, Optional, Any, Union, Iterator, Callable
from http import HTTPStatus
from email.utils import formatdate
import json


@dataclass
class Response:
    """
    HTTP Response object.

    Attributes:
        status_code: HTTP status code (200, 404, etc.)
        headers: Response headers
        body: Response body (bytes, string, or iterator)
    """
    status_code: int = 200
    headers: Dict[str, str] = field(default_factory=dict)
    body: Union[bytes, str, Iterator[bytes], None] = None

    # Internal state
    _cookies: list = field(default_factory=list, repr=False)

    @property
    def reason(self) -> str:
        """Get reason phrase for status code."""
        try:
            return HTTPStatus(self.status_code).phrase
        except ValueError:
            return "Unknown"

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300

    @property
    def is_redirect(self) -> bool:
        return 300 <= self.status_code < 400

    @property
    def is_error(self) -> bool:
        return self.status_code >= 400

    def set_header(self, name: str, value: str) -> 'Response':
        """Set a header (chainable)."""
        self.headers[name] = value
        return self

    def set_cookie(
        self,
        name: str,
        value: str,
        max_age: Optional[int] = None,
        expires: Optional[str] = None,
        path: str = '/',
        domain: Optional[str] = None,
        secure: bool = False,
        httponly: bool = False,
        samesite: Optional[str] = None
    ) -> 'Response':
        """Set a cookie (chainable)."""
        cookie = f"{name}={value}"

        if max_age is not None:
            cookie += f"; Max-Age={max_age}"
        if expires:
            cookie += f"; Expires={expires}"
        if path:
            cookie += f"; Path={path}"
        if domain:
            cookie += f"; Domain={domain}"
        if secure:
            cookie += "; Secure"
        if httponly:
            cookie += "; HttpOnly"
        if samesite:
            cookie += f"; SameSite={samesite}"

        self._cookies.append(cookie)
        return self

    def delete_cookie(self, name: str, path: str = '/') -> 'Response':
        """Delete a cookie by setting it to expire."""
        return self.set_cookie(
            name, '',
            max_age=0,
            expires='Thu, 01 Jan 1970 00:00:00 GMT',
            path=path
        )

    def get_body_bytes(self) -> bytes:
        """Convert body to bytes."""
        if self.body is None:
            return b''
        if isinstance(self.body, bytes):
            return self.body
        if isinstance(self.body, str):
            return self.body.encode('utf-8')
        # Iterator - consume it
        return b''.join(self.body)

    def is_streaming(self) -> bool:
        """Check if response body is a stream/iterator."""
        return hasattr(self.body, '__iter__') and not isinstance(self.body, (bytes, str))

    def serialize_headers(self) -> bytes:
        """Serialize status line and headers."""
        lines = [f"HTTP/1.1 {self.status_code} {self.reason}"]

        # Add standard headers if not present
        if 'Date' not in self.headers:
            self.headers['Date'] = formatdate(usegmt=True)

        if 'Server' not in self.headers:
            self.headers['Server'] = 'PythonHTTP/1.0'

        # Add Content-Length for non-streaming responses
        if not self.is_streaming() and 'Content-Length' not in self.headers:
            body_bytes = self.get_body_bytes()
            self.headers['Content-Length'] = str(len(body_bytes))

        # Add headers
        for name, value in self.headers.items():
            lines.append(f"{name}: {value}")

        # Add cookies
        for cookie in self._cookies:
            lines.append(f"Set-Cookie: {cookie}")

        lines.append('')  # Empty line before body
        lines.append('')

        return '\r\n'.join(lines).encode('ascii')

    def serialize(self) -> bytes:
        """Serialize complete response to bytes."""
        if self.is_streaming():
            raise ValueError("Cannot serialize streaming response; use iterate()")

        return self.serialize_headers() + self.get_body_bytes()

    def iterate(self) -> Iterator[bytes]:
        """
        Iterate over response for streaming.

        Yields:
            Headers first, then body chunks
        """
        yield self.serialize_headers()

        if self.body is None:
            return

        if isinstance(self.body, bytes):
            yield self.body
        elif isinstance(self.body, str):
            yield self.body.encode('utf-8')
        else:
            for chunk in self.body:
                yield chunk
```

---

## 7.2 Response Factories

### Text Responses

```python
def text_response(
    content: str,
    status: int = 200,
    content_type: str = 'text/plain; charset=utf-8'
) -> Response:
    """Create a plain text response."""
    return Response(
        status_code=status,
        headers={'Content-Type': content_type},
        body=content.encode('utf-8')
    )
```

### HTML Responses

```python
def html_response(
    content: str,
    status: int = 200
) -> Response:
    """Create an HTML response."""
    return Response(
        status_code=status,
        headers={'Content-Type': 'text/html; charset=utf-8'},
        body=content.encode('utf-8')
    )
```

### JSON Responses

```python
def json_response(
    data: Any,
    status: int = 200,
    indent: Optional[int] = None,
    ensure_ascii: bool = False
) -> Response:
    """
    Create a JSON response.

    Args:
        data: Data to serialize
        status: HTTP status code
        indent: JSON indentation (None for compact)
        ensure_ascii: Escape non-ASCII characters
    """
    body = json.dumps(
        data,
        indent=indent,
        ensure_ascii=ensure_ascii,
        default=str  # Handle non-serializable types
    ).encode('utf-8')

    return Response(
        status_code=status,
        headers={'Content-Type': 'application/json; charset=utf-8'},
        body=body
    )
```

### Redirect Responses

```python
def redirect_response(
    location: str,
    permanent: bool = False,
    preserve_method: bool = False
) -> Response:
    """
    Create a redirect response.

    Args:
        location: Target URL
        permanent: 301/308 if True, 302/307 if False
        preserve_method: Use 307/308 to preserve HTTP method
    """
    if permanent:
        status = 308 if preserve_method else 301
    else:
        status = 307 if preserve_method else 302

    return Response(
        status_code=status,
        headers={'Location': location},
        body=b''
    )
```

### Error Responses

```python
def error_response(
    status: int,
    message: Optional[str] = None,
    details: Optional[dict] = None
) -> Response:
    """
    Create an error response.

    Supports both HTML and JSON error formats.
    """
    try:
        reason = HTTPStatus(status).phrase
    except ValueError:
        reason = 'Error'

    message = message or reason

    # JSON error format
    if details is not None:
        return json_response({
            'error': {
                'status': status,
                'message': message,
                'details': details
            }
        }, status=status)

    # HTML error format
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>{status} {reason}</title>
    <style>
        body {{ font-family: sans-serif; padding: 40px; }}
        h1 {{ color: #333; }}
    </style>
</head>
<body>
    <h1>{status} {reason}</h1>
    <p>{message}</p>
</body>
</html>"""

    return html_response(html, status=status)
```

### Empty Response

```python
def empty_response(status: int = 204) -> Response:
    """Create an empty response (typically 204 No Content)."""
    return Response(
        status_code=status,
        headers={'Content-Length': '0'},
        body=b''
    )
```

---

## 7.3 Status Code Helpers

```python
class HTTPResponses:
    """Factory methods for common HTTP responses."""

    # 2xx Success
    @staticmethod
    def ok(body: Any = None, **kwargs) -> Response:
        if body is None:
            return empty_response(200)
        if isinstance(body, dict):
            return json_response(body, **kwargs)
        return text_response(str(body), **kwargs)

    @staticmethod
    def created(location: str, body: Any = None) -> Response:
        response = json_response(body, status=201) if body else empty_response(201)
        response.headers['Location'] = location
        return response

    @staticmethod
    def accepted(body: Any = None) -> Response:
        return json_response(body, status=202) if body else empty_response(202)

    @staticmethod
    def no_content() -> Response:
        return empty_response(204)

    # 3xx Redirection
    @staticmethod
    def moved_permanently(location: str) -> Response:
        return redirect_response(location, permanent=True)

    @staticmethod
    def found(location: str) -> Response:
        return redirect_response(location, permanent=False)

    @staticmethod
    def see_other(location: str) -> Response:
        return Response(status_code=303, headers={'Location': location})

    @staticmethod
    def not_modified() -> Response:
        return empty_response(304)

    # 4xx Client Errors
    @staticmethod
    def bad_request(message: str = None) -> Response:
        return error_response(400, message)

    @staticmethod
    def unauthorized(realm: str = 'Restricted') -> Response:
        response = error_response(401, 'Authentication required')
        response.headers['WWW-Authenticate'] = f'Bearer realm="{realm}"'
        return response

    @staticmethod
    def forbidden(message: str = None) -> Response:
        return error_response(403, message)

    @staticmethod
    def not_found(message: str = None) -> Response:
        return error_response(404, message)

    @staticmethod
    def method_not_allowed(allowed: list) -> Response:
        response = error_response(405, 'Method not allowed')
        response.headers['Allow'] = ', '.join(allowed)
        return response

    @staticmethod
    def conflict(message: str = None) -> Response:
        return error_response(409, message)

    @staticmethod
    def unprocessable_entity(errors: dict = None) -> Response:
        return error_response(422, 'Validation failed', errors)

    @staticmethod
    def too_many_requests(retry_after: int = None) -> Response:
        response = error_response(429, 'Too many requests')
        if retry_after:
            response.headers['Retry-After'] = str(retry_after)
        return response

    # 5xx Server Errors
    @staticmethod
    def internal_error(message: str = None) -> Response:
        return error_response(500, message or 'Internal server error')

    @staticmethod
    def not_implemented() -> Response:
        return error_response(501, 'Not implemented')

    @staticmethod
    def bad_gateway() -> Response:
        return error_response(502, 'Bad gateway')

    @staticmethod
    def service_unavailable(retry_after: int = None) -> Response:
        response = error_response(503, 'Service unavailable')
        if retry_after:
            response.headers['Retry-After'] = str(retry_after)
        return response
```

---

## 7.4 Streaming Responses

### Generator-Based Streaming

```python
from typing import Generator


def streaming_response(
    generator: Generator[bytes, None, None],
    content_type: str = 'application/octet-stream'
) -> Response:
    """
    Create a streaming response from a generator.

    Uses chunked transfer encoding automatically.
    """
    return Response(
        status_code=200,
        headers={
            'Content-Type': content_type,
            'Transfer-Encoding': 'chunked'
        },
        body=generator
    )


def stream_large_data():
    """Example: Stream large dataset."""
    for i in range(1000000):
        yield f"line {i}\n".encode()


# Usage:
response = streaming_response(stream_large_data(), 'text/plain')
```

### Chunked Encoding Wrapper

```python
def chunked_body(iterator: Iterator[bytes]) -> Iterator[bytes]:
    """
    Wrap iterator in HTTP chunked encoding.

    Yields properly formatted chunks for Transfer-Encoding: chunked.
    """
    for chunk in iterator:
        if chunk:
            # Chunk format: size in hex + CRLF + data + CRLF
            size = hex(len(chunk))[2:]
            yield f"{size}\r\n".encode() + chunk + b"\r\n"

    # Final chunk
    yield b"0\r\n\r\n"


class ChunkedResponse(Response):
    """Response that uses chunked transfer encoding."""

    def __init__(self, generator: Iterator[bytes], content_type: str = 'text/plain'):
        super().__init__(
            status_code=200,
            headers={
                'Content-Type': content_type,
                'Transfer-Encoding': 'chunked'
            }
        )
        self._generator = generator

    def iterate(self) -> Iterator[bytes]:
        yield self.serialize_headers()
        yield from chunked_body(self._generator)
```

---

## 7.5 File Responses

### Basic File Serving

```python
import os
import mimetypes
from pathlib import Path


def file_response(
    filepath: str,
    filename: Optional[str] = None,
    content_type: Optional[str] = None,
    download: bool = False
) -> Response:
    """
    Serve a file.

    Args:
        filepath: Path to file
        filename: Override filename for Content-Disposition
        content_type: Override MIME type
        download: Force download (vs inline display)
    """
    path = Path(filepath)

    if not path.exists():
        return error_response(404, 'File not found')

    if not path.is_file():
        return error_response(404, 'Not a file')

    # Determine content type
    if content_type is None:
        content_type, _ = mimetypes.guess_type(str(path))
        content_type = content_type or 'application/octet-stream'

    # Get file info
    stat = path.stat()
    size = stat.st_size
    mtime = stat.st_mtime

    # Build response
    response = Response(
        status_code=200,
        headers={
            'Content-Type': content_type,
            'Content-Length': str(size),
            'Last-Modified': formatdate(mtime, usegmt=True),
            'Accept-Ranges': 'bytes'
        }
    )

    # Content-Disposition
    if download or filename:
        disposition = 'attachment' if download else 'inline'
        fname = filename or path.name
        response.headers['Content-Disposition'] = f'{disposition}; filename="{fname}"'

    # Read file
    with open(path, 'rb') as f:
        response.body = f.read()

    return response
```

### Streaming File Response

```python
def stream_file(filepath: str, chunk_size: int = 65536) -> Iterator[bytes]:
    """Stream file in chunks."""
    with open(filepath, 'rb') as f:
        while chunk := f.read(chunk_size):
            yield chunk


def streaming_file_response(
    filepath: str,
    content_type: Optional[str] = None
) -> Response:
    """
    Serve large file with streaming.

    Memory efficient for large files.
    """
    path = Path(filepath)

    if not path.exists():
        return error_response(404, 'File not found')

    if content_type is None:
        content_type, _ = mimetypes.guess_type(str(path))
        content_type = content_type or 'application/octet-stream'

    size = path.stat().st_size

    return Response(
        status_code=200,
        headers={
            'Content-Type': content_type,
            'Content-Length': str(size)
        },
        body=stream_file(str(path))
    )
```

### Range Request Support

```python
from typing import Tuple, List


def parse_range_header(
    range_header: str,
    file_size: int
) -> List[Tuple[int, int]]:
    """
    Parse Range header and return list of (start, end) tuples.

    Range: bytes=0-499
    Range: bytes=0-499, 1000-1499
    Range: bytes=-500 (last 500 bytes)
    Range: bytes=1000- (from byte 1000 to end)
    """
    if not range_header.startswith('bytes='):
        raise ValueError("Only bytes ranges supported")

    ranges = []
    range_spec = range_header[6:]  # Remove 'bytes='

    for part in range_spec.split(','):
        part = part.strip()

        if part.startswith('-'):
            # Suffix range: last N bytes
            suffix_length = int(part[1:])
            start = max(0, file_size - suffix_length)
            end = file_size - 1
        elif part.endswith('-'):
            # Open-ended range
            start = int(part[:-1])
            end = file_size - 1
        else:
            # Explicit range
            start_str, end_str = part.split('-')
            start = int(start_str)
            end = int(end_str)

        # Validate
        if start > end or start >= file_size:
            raise ValueError(f"Invalid range: {part}")

        # Clamp end to file size
        end = min(end, file_size - 1)

        ranges.append((start, end))

    return ranges


def range_file_response(
    filepath: str,
    range_header: str
) -> Response:
    """
    Serve partial file content for range requests.
    """
    path = Path(filepath)

    if not path.exists():
        return error_response(404)

    file_size = path.stat().st_size
    content_type, _ = mimetypes.guess_type(str(path))
    content_type = content_type or 'application/octet-stream'

    try:
        ranges = parse_range_header(range_header, file_size)
    except ValueError as e:
        # Invalid range
        response = error_response(416, 'Invalid range')
        response.headers['Content-Range'] = f'bytes */{file_size}'
        return response

    if len(ranges) == 1:
        # Single range
        start, end = ranges[0]
        content_length = end - start + 1

        with open(path, 'rb') as f:
            f.seek(start)
            body = f.read(content_length)

        return Response(
            status_code=206,
            headers={
                'Content-Type': content_type,
                'Content-Length': str(content_length),
                'Content-Range': f'bytes {start}-{end}/{file_size}',
                'Accept-Ranges': 'bytes'
            },
            body=body
        )

    else:
        # Multiple ranges - use multipart response
        boundary = 'RANGE_BOUNDARY_' + os.urandom(8).hex()
        parts = []

        with open(path, 'rb') as f:
            for start, end in ranges:
                f.seek(start)
                data = f.read(end - start + 1)

                part = (
                    f"--{boundary}\r\n"
                    f"Content-Type: {content_type}\r\n"
                    f"Content-Range: bytes {start}-{end}/{file_size}\r\n"
                    f"\r\n"
                ).encode() + data + b"\r\n"

                parts.append(part)

        body = b''.join(parts) + f"--{boundary}--\r\n".encode()

        return Response(
            status_code=206,
            headers={
                'Content-Type': f'multipart/byteranges; boundary={boundary}',
                'Content-Length': str(len(body))
            },
            body=body
        )
```

---

## 7.6 Compression

### Gzip Compression

```python
import gzip
import zlib
from io import BytesIO


def compress_gzip(data: bytes, level: int = 6) -> bytes:
    """Compress data with gzip."""
    buf = BytesIO()
    with gzip.GzipFile(fileobj=buf, mode='wb', compresslevel=level) as f:
        f.write(data)
    return buf.getvalue()


def compress_deflate(data: bytes, level: int = 6) -> bytes:
    """Compress data with deflate."""
    return zlib.compress(data, level)


try:
    import brotli

    def compress_brotli(data: bytes, quality: int = 4) -> bytes:
        """Compress data with brotli."""
        return brotli.compress(data, quality=quality)

except ImportError:
    compress_brotli = None
```

### Compression Middleware

```python
def should_compress(
    content_type: str,
    content_length: int,
    min_size: int = 1024
) -> bool:
    """Determine if response should be compressed."""
    # Don't compress small responses
    if content_length < min_size:
        return False

    # Only compress text-based content
    compressible_types = [
        'text/',
        'application/json',
        'application/javascript',
        'application/xml',
        'application/xhtml+xml',
        'image/svg+xml'
    ]

    return any(content_type.startswith(t) for t in compressible_types)


def select_encoding(accept_encoding: str) -> Optional[str]:
    """Select best compression encoding from Accept-Encoding header."""
    encodings = []

    for part in accept_encoding.split(','):
        part = part.strip()
        if ';' in part:
            encoding, params = part.split(';', 1)
            encoding = encoding.strip()
            # Parse quality
            for param in params.split(';'):
                if param.strip().startswith('q='):
                    try:
                        q = float(param.strip()[2:])
                    except ValueError:
                        q = 1.0
                    break
            else:
                q = 1.0
        else:
            encoding = part
            q = 1.0

        if q > 0:
            encodings.append((encoding, q))

    # Sort by quality
    encodings.sort(key=lambda x: x[1], reverse=True)

    # Select best available
    for encoding, _ in encodings:
        if encoding == 'br' and compress_brotli:
            return 'br'
        if encoding == 'gzip':
            return 'gzip'
        if encoding == 'deflate':
            return 'deflate'

    return None


def compress_response(
    response: Response,
    accept_encoding: str
) -> Response:
    """Apply compression to response if appropriate."""
    # Skip if already encoded
    if 'Content-Encoding' in response.headers:
        return response

    # Skip streaming responses
    if response.is_streaming():
        return response

    content_type = response.headers.get('Content-Type', '')
    body = response.get_body_bytes()

    if not should_compress(content_type, len(body)):
        return response

    encoding = select_encoding(accept_encoding)
    if not encoding:
        return response

    # Compress
    if encoding == 'gzip':
        compressed = compress_gzip(body)
    elif encoding == 'deflate':
        compressed = compress_deflate(body)
    elif encoding == 'br' and compress_brotli:
        compressed = compress_brotli(body)
    else:
        return response

    # Only use compression if it actually helps
    if len(compressed) >= len(body):
        return response

    response.body = compressed
    response.headers['Content-Encoding'] = encoding
    response.headers['Content-Length'] = str(len(compressed))
    response.headers['Vary'] = 'Accept-Encoding'

    return response
```

---

## 7.7 Server-Sent Events (SSE)

### SSE Format

```
data: Hello\n
\n

data: {"message": "World"}\n
id: 1\n
\n

event: update\n
data: New data\n
retry: 5000\n
\n
```

### SSE Implementation

```python
from dataclasses import dataclass
from typing import Optional, Iterator, Any


@dataclass
class SSEEvent:
    """Server-Sent Event."""
    data: str
    event: Optional[str] = None
    id: Optional[str] = None
    retry: Optional[int] = None

    def serialize(self) -> str:
        """Serialize to SSE format."""
        lines = []

        if self.event:
            lines.append(f"event: {self.event}")

        if self.id:
            lines.append(f"id: {self.id}")

        if self.retry:
            lines.append(f"retry: {self.retry}")

        # Data can be multiline
        for line in self.data.split('\n'):
            lines.append(f"data: {line}")

        lines.append('')  # Empty line ends the event
        return '\n'.join(lines) + '\n'


def sse_response(events: Iterator[SSEEvent]) -> Response:
    """
    Create a Server-Sent Events response.

    Args:
        events: Iterator yielding SSEEvent objects

    Example:
        def event_stream():
            for i in range(10):
                yield SSEEvent(data=f"Count: {i}", id=str(i))
                time.sleep(1)

        return sse_response(event_stream())
    """
    def generate():
        for event in events:
            yield event.serialize().encode('utf-8')

    return Response(
        status_code=200,
        headers={
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'  # Disable nginx buffering
        },
        body=generate()
    )


def sse_json(data: Any, event: str = None, id: str = None) -> SSEEvent:
    """Create SSE event with JSON data."""
    return SSEEvent(
        data=json.dumps(data, ensure_ascii=False),
        event=event,
        id=id
    )
```

### SSE Example Usage

```python
import time
import queue
from threading import Thread


# Simple real-time notification system
class NotificationStream:
    def __init__(self):
        self.clients: list[queue.Queue] = []

    def subscribe(self) -> Iterator[SSEEvent]:
        """Subscribe to notifications."""
        q = queue.Queue()
        self.clients.append(q)

        try:
            # Send initial connection event
            yield SSEEvent(data='connected', event='connect')

            while True:
                try:
                    event = q.get(timeout=30)
                    yield event
                except queue.Empty:
                    # Send keepalive
                    yield SSEEvent(data='ping', event='keepalive')
        finally:
            self.clients.remove(q)

    def broadcast(self, event: SSEEvent):
        """Send event to all connected clients."""
        for q in self.clients:
            q.put(event)


notifications = NotificationStream()


@app.get('/events')
def stream_events(request):
    return sse_response(notifications.subscribe())


@app.post('/notify')
def send_notification(request):
    data = request.json()
    notifications.broadcast(SSEEvent(
        data=json.dumps(data),
        event='notification'
    ))
    return json_response({'sent': len(notifications.clients)})
```

---

## 7.8 Caching Headers

### Static File Caching

```python
import hashlib
from datetime import datetime, timedelta


def static_file_response(
    filepath: str,
    request_headers: dict,
    max_age: int = 86400  # 1 day
) -> Response:
    """
    Serve static file with proper caching headers.

    Handles:
    - ETag validation
    - If-None-Match
    - If-Modified-Since
    - Cache-Control
    """
    path = Path(filepath)

    if not path.exists():
        return error_response(404)

    stat = path.stat()
    mtime = stat.st_mtime
    size = stat.st_size

    # Generate ETag
    etag_source = f"{filepath}:{size}:{mtime}"
    etag = '"' + hashlib.md5(etag_source.encode()).hexdigest() + '"'

    # Check If-None-Match
    if_none_match = request_headers.get('if-none-match')
    if if_none_match and (if_none_match == etag or if_none_match == '*'):
        return Response(
            status_code=304,
            headers={'ETag': etag}
        )

    # Check If-Modified-Since
    if_modified_since = request_headers.get('if-modified-since')
    if if_modified_since:
        try:
            from email.utils import parsedate_to_datetime
            ims_time = parsedate_to_datetime(if_modified_since)
            file_time = datetime.fromtimestamp(mtime, tz=ims_time.tzinfo)
            if file_time <= ims_time:
                return Response(
                    status_code=304,
                    headers={
                        'ETag': etag,
                        'Last-Modified': formatdate(mtime, usegmt=True)
                    }
                )
        except (ValueError, TypeError):
            pass  # Invalid date, ignore

    # Determine content type
    content_type, _ = mimetypes.guess_type(str(path))
    content_type = content_type or 'application/octet-stream'

    # Read file
    with open(path, 'rb') as f:
        body = f.read()

    return Response(
        status_code=200,
        headers={
            'Content-Type': content_type,
            'Content-Length': str(len(body)),
            'ETag': etag,
            'Last-Modified': formatdate(mtime, usegmt=True),
            'Cache-Control': f'public, max-age={max_age}',
            'Accept-Ranges': 'bytes'
        },
        body=body
    )


def immutable_file_response(filepath: str) -> Response:
    """
    Serve file with immutable caching (for hashed filenames).

    E.g., app.abc123.js - can be cached forever.
    """
    response = file_response(filepath)
    response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
    return response
```

---

## 7.9 Complete Response System

```python
"""
Complete Response System

Integrates all response types into a unified API.
"""

from typing import Union, Any, Iterator, Optional
from pathlib import Path


class ResponseBuilder:
    """Fluent interface for building responses."""

    def __init__(self):
        self._status = 200
        self._headers: dict = {}
        self._body: Any = None
        self._cookies: list = []

    def status(self, code: int) -> 'ResponseBuilder':
        self._status = code
        return self

    def header(self, name: str, value: str) -> 'ResponseBuilder':
        self._headers[name] = value
        return self

    def headers(self, headers: dict) -> 'ResponseBuilder':
        self._headers.update(headers)
        return self

    def content_type(self, ct: str) -> 'ResponseBuilder':
        self._headers['Content-Type'] = ct
        return self

    def cookie(self, name: str, value: str, **opts) -> 'ResponseBuilder':
        self._cookies.append((name, value, opts))
        return self

    def body(self, content: Union[bytes, str, Iterator[bytes]]) -> 'ResponseBuilder':
        self._body = content
        return self

    def json(self, data: Any) -> 'ResponseBuilder':
        self._headers['Content-Type'] = 'application/json; charset=utf-8'
        self._body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        return self

    def html(self, content: str) -> 'ResponseBuilder':
        self._headers['Content-Type'] = 'text/html; charset=utf-8'
        self._body = content.encode('utf-8')
        return self

    def text(self, content: str) -> 'ResponseBuilder':
        self._headers['Content-Type'] = 'text/plain; charset=utf-8'
        self._body = content.encode('utf-8')
        return self

    def file(self, path: str, download: bool = False) -> 'ResponseBuilder':
        p = Path(path)
        ct, _ = mimetypes.guess_type(str(p))
        self._headers['Content-Type'] = ct or 'application/octet-stream'

        if download:
            self._headers['Content-Disposition'] = f'attachment; filename="{p.name}"'

        with open(p, 'rb') as f:
            self._body = f.read()

        return self

    def stream(self, generator: Iterator[bytes]) -> 'ResponseBuilder':
        self._headers['Transfer-Encoding'] = 'chunked'
        self._body = generator
        return self

    def redirect(self, location: str, permanent: bool = False) -> 'ResponseBuilder':
        self._status = 301 if permanent else 302
        self._headers['Location'] = location
        return self

    def cache(self, max_age: int = 3600, public: bool = True) -> 'ResponseBuilder':
        scope = 'public' if public else 'private'
        self._headers['Cache-Control'] = f'{scope}, max-age={max_age}'
        return self

    def no_cache(self) -> 'ResponseBuilder':
        self._headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
        return self

    def build(self) -> Response:
        response = Response(
            status_code=self._status,
            headers=self._headers,
            body=self._body
        )

        for name, value, opts in self._cookies:
            response.set_cookie(name, value, **opts)

        return response


# Convenience function
def response() -> ResponseBuilder:
    """Create a new response builder."""
    return ResponseBuilder()


# Usage examples:
# response().json({'key': 'value'}).build()
# response().status(201).header('Location', '/new').json({'id': 1}).build()
# response().file('/path/to/file.pdf', download=True).build()
# response().stream(my_generator).content_type('text/plain').build()
```

---

## 7.10 Lab: Build a Static File Server

### Requirements

Build a static file server that:

1. Serves files from a directory
2. Returns proper MIME types
3. Supports ETag-based caching
4. Supports Range requests
5. Compresses text-based responses
6. Prevents directory traversal attacks

### Implementation

```python
import os
from pathlib import Path


class StaticFileServer:
    """
    Production-quality static file server.
    """

    def __init__(
        self,
        root: str,
        index_files: list = None,
        max_age: int = 86400
    ):
        self.root = Path(root).resolve()
        self.index_files = index_files or ['index.html', 'index.htm']
        self.max_age = max_age

    def serve(self, request) -> Response:
        """Handle request for static file."""
        path = request.path

        # Security: Normalize and validate path
        try:
            file_path = self._resolve_path(path)
        except ValueError as e:
            return error_response(400, str(e))

        if file_path is None:
            return error_response(404)

        # Handle directory
        if file_path.is_dir():
            # Try index files
            for index in self.index_files:
                index_path = file_path / index
                if index_path.is_file():
                    file_path = index_path
                    break
            else:
                return error_response(403, 'Directory listing not allowed')

        # Check if file exists
        if not file_path.is_file():
            return error_response(404)

        # Handle range request
        range_header = request.headers.get('range')
        if range_header:
            return self._serve_range(file_path, range_header)

        # Handle conditional request
        response = self._serve_with_cache(
            file_path,
            request.headers.get('if-none-match'),
            request.headers.get('if-modified-since')
        )

        # Apply compression if requested
        accept_encoding = request.headers.get('accept-encoding', '')
        if accept_encoding and not response.is_streaming():
            response = compress_response(response, accept_encoding)

        return response

    def _resolve_path(self, url_path: str) -> Optional[Path]:
        """Resolve URL path to filesystem path safely."""
        # Remove leading slash and decode
        url_path = url_path.lstrip('/')

        # Build path
        file_path = (self.root / url_path).resolve()

        # Security check: ensure path is under root
        try:
            file_path.relative_to(self.root)
        except ValueError:
            raise ValueError("Path traversal detected")

        if not file_path.exists():
            return None

        return file_path

    def _serve_with_cache(
        self,
        file_path: Path,
        if_none_match: Optional[str],
        if_modified_since: Optional[str]
    ) -> Response:
        """Serve file with caching validation."""
        stat = file_path.stat()
        mtime = stat.st_mtime
        size = stat.st_size

        # Generate ETag
        etag = f'"{file_path.name}-{size}-{int(mtime)}"'

        # Check If-None-Match
        if if_none_match == etag:
            return Response(status_code=304, headers={'ETag': etag})

        # Determine content type
        content_type, _ = mimetypes.guess_type(str(file_path))
        content_type = content_type or 'application/octet-stream'

        # Read file
        with open(file_path, 'rb') as f:
            body = f.read()

        return Response(
            status_code=200,
            headers={
                'Content-Type': content_type,
                'Content-Length': str(len(body)),
                'ETag': etag,
                'Last-Modified': formatdate(mtime, usegmt=True),
                'Cache-Control': f'public, max-age={self.max_age}',
                'Accept-Ranges': 'bytes'
            },
            body=body
        )

    def _serve_range(self, file_path: Path, range_header: str) -> Response:
        """Serve partial content."""
        return range_file_response(str(file_path), range_header)
```

---

## Exercises

### Exercise 7.1: JSONP Response

Implement JSONP (JSON with Padding) for legacy browser support:

```python
def jsonp_response(data: Any, callback: str) -> Response:
    """Create JSONP response."""
    # Validate callback name (security!)
    # Return: callback({"data": ...})
    pass
```

### Exercise 7.2: XML Response

Implement XML response generation:

```python
def xml_response(data: dict, root: str = 'root') -> Response:
    """Create XML response from dictionary."""
    pass
```

### Exercise 7.3: CSV Download

Implement streaming CSV download:

```python
def csv_response(rows: Iterator[list], filename: str) -> Response:
    """Stream CSV data as download."""
    pass
```

### Exercise 7.4: Content Negotiation

Implement content negotiation based on Accept header:

```python
def negotiate_response(data: Any, accept: str) -> Response:
    """Return JSON, XML, or HTML based on Accept header."""
    pass
```

### Exercise 7.5: Response Timing

Add response timing headers:

```python
def timed_response(start_time: float, response: Response) -> Response:
    """Add Server-Timing header with processing time."""
    pass
```

---

## Deep Dive Questions

1. **Why does HTTP use `Transfer-Encoding: chunked` instead of just streaming without length?**

2. **What security implications exist with Content-Disposition filenames?**

3. **Why is `Cache-Control: immutable` not widely used?**

4. **How does HTTP/2 server push differ from SSE?**

5. **What's the difference between `no-cache` and `no-store` in Cache-Control?**

---

## Resources

### RFCs
- [RFC 7234 - HTTP Caching](https://tools.ietf.org/html/rfc7234)
- [RFC 7233 - Range Requests](https://tools.ietf.org/html/rfc7233)
- [W3C Server-Sent Events](https://www.w3.org/TR/eventsource/)

### Libraries
- [brotli](https://github.com/google/brotli) — Brotli compression
- [python-mimetypes](https://docs.python.org/3/library/mimetypes.html) — MIME type detection

---

## Summary

You've built a complete response system:

1. **Response Object** — Flexible status, headers, body representation
2. **Response Factories** — JSON, HTML, text, error, redirect
3. **Streaming** — Generator-based chunked responses
4. **File Serving** — Static files with caching and ranges
5. **Compression** — gzip, deflate, brotli with content negotiation
6. **Server-Sent Events** — Real-time server push
7. **Caching** — ETag, Last-Modified, Cache-Control
8. **Fluent Builder** — Chainable response construction

You now have all the building blocks for a complete HTTP server. The next part of this syllabus tackles the critical challenge of handling multiple concurrent connections.

---

## Next Module

**[Module 8: The Concurrency Problem →](./MODULE_08_CONCURRENCY_PROBLEM.md)**

We'll explore why single-threaded servers fail under load and survey the solutions: threading, multiprocessing, and async I/O.

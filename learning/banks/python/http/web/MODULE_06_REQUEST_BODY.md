# Module 6: Request Body Handling

## Overview

When clients send data to your server—form submissions, JSON payloads, file uploads—that data arrives as raw bytes in the request body. This module teaches you how to parse every common body format, handle streaming data efficiently, and protect against malicious payloads.

By the end, you'll have implemented parsers for JSON, URL-encoded forms, multipart file uploads, and streaming bodies.

---

## Learning Objectives

By the end of this module, you will be able to:

1. Read request bodies based on Content-Length and Transfer-Encoding
2. Parse JSON bodies with proper error handling
3. Parse URL-encoded form data
4. Parse multipart form data with file uploads
5. Handle streaming request bodies
6. Implement size limits and security measures
7. Build a unified body parsing interface

---

## 6.1 Content-Length Based Reading

### How Body Length is Determined

HTTP/1.1 bodies are delimited by:

1. **Content-Length header**: Exact byte count
2. **Transfer-Encoding: chunked**: Size in each chunk
3. **Connection close**: Read until EOF (HTTP/1.0 only)

### Reading Fixed-Length Bodies

```python
from typing import Optional


class BodyReader:
    """Read request bodies from socket."""

    def __init__(self, reader: HTTPReader, headers: dict):
        self.reader = reader
        self.headers = headers
        self._body: Optional[bytes] = None

    def read(self, max_size: int = 10 * 1024 * 1024) -> bytes:
        """
        Read entire body into memory.

        Args:
            max_size: Maximum body size in bytes (default 10MB)

        Returns:
            Body as bytes

        Raises:
            BodyTooLargeError: If body exceeds max_size
            ValueError: If Content-Length is invalid
        """
        if self._body is not None:
            return self._body

        # Check Transfer-Encoding
        transfer_encoding = self.headers.get('transfer-encoding', '').lower()
        if 'chunked' in transfer_encoding:
            self._body = self._read_chunked(max_size)
            return self._body

        # Check Content-Length
        content_length = self.headers.get('content-length')
        if content_length is None:
            # No body
            self._body = b''
            return self._body

        try:
            length = int(content_length)
        except ValueError:
            raise ValueError(f"Invalid Content-Length: {content_length}")

        if length < 0:
            raise ValueError(f"Negative Content-Length: {length}")

        if length > max_size:
            raise BodyTooLargeError(f"Body too large: {length} > {max_size}")

        if length == 0:
            self._body = b''
            return self._body

        # Read exact number of bytes
        self._body = self.reader.read_exactly(length)
        return self._body

    def _read_chunked(self, max_size: int) -> bytes:
        """Read chunked transfer encoding."""
        body = b''

        while True:
            # Read chunk size line
            size_line = self.reader.read_line()
            size_str = size_line.decode('ascii').split(';')[0].strip()

            try:
                chunk_size = int(size_str, 16)
            except ValueError:
                raise ValueError(f"Invalid chunk size: {size_str}")

            if chunk_size == 0:
                # Final chunk - read trailing CRLF
                self.reader.read_line()
                break

            if len(body) + chunk_size > max_size:
                raise BodyTooLargeError(f"Chunked body exceeds {max_size}")

            # Read chunk data and trailing CRLF
            chunk = self.reader.read_exactly(chunk_size)
            self.reader.read_line()

            body += chunk

        return body


class BodyTooLargeError(Exception):
    """Request body exceeds size limit."""
    pass
```

---

## 6.2 Chunked Transfer Encoding

### Chunk Format Review

```
HTTP/1.1 200 OK
Transfer-Encoding: chunked

a\r\n                    # 10 bytes (hex)
1234567890\r\n           # chunk data
5\r\n                    # 5 bytes
12345\r\n                # chunk data
0\r\n                    # final chunk
\r\n                     # end
```

### Chunk Extensions

Chunks can have extensions (rarely used):

```
a;name=value;other\r\n
1234567890\r\n
```

### Trailer Headers

After the final chunk, optional trailer headers:

```
0\r\n
Content-MD5: abc123\r\n
\r\n
```

### Complete Chunked Parser

```python
from typing import Generator, Tuple, Dict


def parse_chunked_stream(reader: HTTPReader) -> Generator[bytes, None, Dict[str, str]]:
    """
    Generator that yields chunks and returns trailers.

    Usage:
        chunks = parse_chunked_stream(reader)
        for chunk in chunks:
            process(chunk)
        trailers = chunks.value  # After iteration completes
    """
    while True:
        # Read chunk header
        header_line = reader.read_line().decode('ascii').strip()

        # Parse size and extensions
        if ';' in header_line:
            size_str, _ = header_line.split(';', 1)
        else:
            size_str = header_line

        chunk_size = int(size_str, 16)

        if chunk_size == 0:
            break

        # Read chunk data
        chunk_data = reader.read_exactly(chunk_size)
        reader.read_line()  # Trailing CRLF

        yield chunk_data

    # Parse trailer headers
    trailers = {}
    while True:
        line = reader.read_line()
        if line == b'\r\n':
            break
        name, _, value = line.decode('ascii').partition(':')
        trailers[name.strip().lower()] = value.strip()

    return trailers
```

---

## 6.3 Form Data Parsing (application/x-www-form-urlencoded)

### Format

URL-encoded form data:

```
name=John+Doe&email=john%40example.com&interests=python&interests=web
```

Special encoding:
- Space → `+` or `%20`
- Special chars → `%XX` (hex)
- Multiple values → repeated keys

### Parser Implementation

```python
from urllib.parse import parse_qs, unquote_plus
from typing import Dict, List


def parse_form_urlencoded(body: bytes, encoding: str = 'utf-8') -> Dict[str, List[str]]:
    """
    Parse application/x-www-form-urlencoded body.

    Args:
        body: Raw body bytes
        encoding: Character encoding (default UTF-8)

    Returns:
        Dictionary mapping field names to lists of values
    """
    try:
        text = body.decode(encoding)
    except UnicodeDecodeError as e:
        raise ValueError(f"Invalid {encoding} encoding: {e}")

    # parse_qs handles all the decoding
    return parse_qs(
        text,
        keep_blank_values=True,  # Include empty values
        strict_parsing=False,    # Don't raise on malformed
        encoding=encoding,
        errors='replace'         # Replace invalid chars
    )


def parse_form_urlencoded_single(body: bytes, encoding: str = 'utf-8') -> Dict[str, str]:
    """
    Parse form data, returning only first value for each field.

    Useful when you don't expect multi-value fields.
    """
    multi = parse_form_urlencoded(body, encoding)
    return {k: v[0] for k, v in multi.items()}


# Example usage:
body = b"name=John+Doe&email=john%40example.com&tags=python&tags=web"
parsed = parse_form_urlencoded(body)
# {'name': ['John Doe'], 'email': ['john@example.com'], 'tags': ['python', 'web']}

single = parse_form_urlencoded_single(body)
# {'name': 'John Doe', 'email': 'john@example.com', 'tags': 'python'}
```

---

## 6.4 Multipart Form Data (multipart/form-data)

### When Multipart is Used

Multipart is required for:
- File uploads
- Binary data
- Mixed text and binary

### Format Structure

```
POST /upload HTTP/1.1
Content-Type: multipart/form-data; boundary=----WebKitFormBoundary7MA4YWxk

------WebKitFormBoundary7MA4YWxk
Content-Disposition: form-data; name="title"

My Photo
------WebKitFormBoundary7MA4YWxk
Content-Disposition: form-data; name="photo"; filename="cat.jpg"
Content-Type: image/jpeg

<binary image data>
------WebKitFormBoundary7MA4YWxk--
```

### Part Structure

Each part has:
1. Boundary line: `--{boundary}`
2. Part headers (Content-Disposition, Content-Type, etc.)
3. Empty line
4. Part body
5. Final boundary: `--{boundary}--`

### Complete Multipart Parser

```python
from dataclasses import dataclass
from typing import Dict, List, Optional, BinaryIO, Union
import re
import tempfile
import os


@dataclass
class FormField:
    """A form field from multipart data."""
    name: str
    value: str


@dataclass
class UploadedFile:
    """An uploaded file from multipart data."""
    name: str              # Form field name
    filename: str          # Original filename
    content_type: str      # MIME type
    size: int              # Size in bytes
    file: BinaryIO         # File-like object with content

    def read(self) -> bytes:
        """Read entire file content."""
        self.file.seek(0)
        return self.file.read()

    def save(self, path: str) -> None:
        """Save file to disk."""
        with open(path, 'wb') as f:
            self.file.seek(0)
            while chunk := self.file.read(8192):
                f.write(chunk)

    def close(self) -> None:
        """Close and clean up temporary file."""
        self.file.close()


@dataclass
class MultipartData:
    """Parsed multipart form data."""
    fields: Dict[str, List[str]]
    files: Dict[str, List[UploadedFile]]

    def get_field(self, name: str, default: str = None) -> Optional[str]:
        """Get first value for a field."""
        values = self.fields.get(name)
        return values[0] if values else default

    def get_file(self, name: str) -> Optional[UploadedFile]:
        """Get first uploaded file for a field."""
        files = self.files.get(name)
        return files[0] if files else None

    def close(self) -> None:
        """Clean up all uploaded files."""
        for file_list in self.files.values():
            for f in file_list:
                f.close()


class MultipartParser:
    """
    Parser for multipart/form-data.

    Handles file uploads by streaming to temporary files
    to avoid memory issues with large uploads.
    """

    # Regex for Content-Disposition header
    CONTENT_DISPOSITION_RE = re.compile(
        r'form-data;\s*name="([^"]+)"(?:;\s*filename="([^"]*)")?',
        re.IGNORECASE
    )

    def __init__(
        self,
        max_file_size: int = 100 * 1024 * 1024,  # 100MB
        max_field_size: int = 1 * 1024 * 1024,   # 1MB
        max_files: int = 100,
        max_fields: int = 1000
    ):
        self.max_file_size = max_file_size
        self.max_field_size = max_field_size
        self.max_files = max_files
        self.max_fields = max_fields

    def parse(
        self,
        body: bytes,
        content_type: str
    ) -> MultipartData:
        """
        Parse multipart form data.

        Args:
            body: Raw request body
            content_type: Content-Type header value

        Returns:
            MultipartData with fields and files
        """
        boundary = self._extract_boundary(content_type)
        if not boundary:
            raise ValueError("Missing boundary in Content-Type")

        boundary_bytes = f'--{boundary}'.encode('ascii')
        end_boundary = f'--{boundary}--'.encode('ascii')

        fields: Dict[str, List[str]] = {}
        files: Dict[str, List[UploadedFile]] = {}
        field_count = 0
        file_count = 0

        # Split by boundary
        parts = body.split(boundary_bytes)

        # Skip preamble (first part before first boundary)
        parts = parts[1:]

        for part in parts:
            # Skip if this is the final boundary
            if part.strip() == b'--' or part.strip() == b'':
                continue

            # Remove leading CRLF
            if part.startswith(b'\r\n'):
                part = part[2:]

            # Remove trailing boundary markers
            if part.endswith(b'--\r\n'):
                part = part[:-4]
            elif part.endswith(b'\r\n'):
                part = part[:-2]

            # Split headers and body
            header_end = part.find(b'\r\n\r\n')
            if header_end == -1:
                continue

            header_bytes = part[:header_end]
            body_bytes = part[header_end + 4:]

            # Parse part headers
            headers = self._parse_headers(header_bytes)

            # Extract Content-Disposition
            disposition = headers.get('content-disposition', '')
            match = self.CONTENT_DISPOSITION_RE.search(disposition)

            if not match:
                continue

            name = match.group(1)
            filename = match.group(2)

            if filename:
                # File upload
                if file_count >= self.max_files:
                    raise ValueError(f"Too many files: max {self.max_files}")
                if len(body_bytes) > self.max_file_size:
                    raise ValueError(f"File too large: max {self.max_file_size}")

                content_type = headers.get('content-type', 'application/octet-stream')
                uploaded = self._create_upload(name, filename, content_type, body_bytes)

                if name not in files:
                    files[name] = []
                files[name].append(uploaded)
                file_count += 1

            else:
                # Regular field
                if field_count >= self.max_fields:
                    raise ValueError(f"Too many fields: max {self.max_fields}")
                if len(body_bytes) > self.max_field_size:
                    raise ValueError(f"Field too large: max {self.max_field_size}")

                # Decode field value
                charset = self._get_charset(headers.get('content-type', ''))
                value = body_bytes.decode(charset, errors='replace')

                if name not in fields:
                    fields[name] = []
                fields[name].append(value)
                field_count += 1

        return MultipartData(fields=fields, files=files)

    def _extract_boundary(self, content_type: str) -> Optional[str]:
        """Extract boundary from Content-Type header."""
        for part in content_type.split(';'):
            part = part.strip()
            if part.lower().startswith('boundary='):
                boundary = part[9:]
                # Remove quotes if present
                if boundary.startswith('"') and boundary.endswith('"'):
                    boundary = boundary[1:-1]
                return boundary
        return None

    def _parse_headers(self, header_bytes: bytes) -> Dict[str, str]:
        """Parse MIME headers."""
        headers = {}
        for line in header_bytes.split(b'\r\n'):
            if b':' in line:
                name, _, value = line.partition(b':')
                headers[name.decode('ascii').lower()] = value.decode('ascii').strip()
        return headers

    def _get_charset(self, content_type: str) -> str:
        """Extract charset from Content-Type, default to UTF-8."""
        for part in content_type.split(';'):
            part = part.strip()
            if part.lower().startswith('charset='):
                return part[8:].strip('"')
        return 'utf-8'

    def _create_upload(
        self,
        name: str,
        filename: str,
        content_type: str,
        data: bytes
    ) -> UploadedFile:
        """Create UploadedFile from data."""
        # Use temp file to handle large uploads
        temp = tempfile.SpooledTemporaryFile(
            max_size=1024 * 1024,  # Keep in memory if < 1MB
            mode='w+b'
        )
        temp.write(data)
        temp.seek(0)

        return UploadedFile(
            name=name,
            filename=filename,
            content_type=content_type,
            size=len(data),
            file=temp
        )


# Usage example:
content_type = 'multipart/form-data; boundary=----WebKitFormBoundary7MA4YWxk'
body = b'''------WebKitFormBoundary7MA4YWxk\r
Content-Disposition: form-data; name="title"\r
\r
My Photo\r
------WebKitFormBoundary7MA4YWxk\r
Content-Disposition: form-data; name="photo"; filename="cat.jpg"\r
Content-Type: image/jpeg\r
\r
<binary data>\r
------WebKitFormBoundary7MA4YWxk--\r
'''

parser = MultipartParser()
data = parser.parse(body, content_type)

print(data.get_field('title'))  # 'My Photo'
photo = data.get_file('photo')
print(photo.filename)           # 'cat.jpg'
print(photo.content_type)       # 'image/jpeg'
```

---

## 6.5 JSON Body Parsing

### Basic JSON Parsing

```python
import json
from typing import Any, Optional


class JSONParseError(Exception):
    """JSON parsing failed."""
    pass


def parse_json(
    body: bytes,
    encoding: str = 'utf-8',
    max_size: int = 10 * 1024 * 1024
) -> Any:
    """
    Parse JSON request body.

    Args:
        body: Raw body bytes
        encoding: Character encoding
        max_size: Maximum body size

    Returns:
        Parsed JSON data

    Raises:
        JSONParseError: If parsing fails
    """
    if len(body) > max_size:
        raise JSONParseError(f"Body too large: {len(body)} > {max_size}")

    if not body:
        return None

    try:
        text = body.decode(encoding)
    except UnicodeDecodeError as e:
        raise JSONParseError(f"Invalid {encoding} encoding: {e}")

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise JSONParseError(f"Invalid JSON: {e}")
```

### JSON with Validation

```python
from typing import TypeVar, Type, get_type_hints
from dataclasses import dataclass, fields, is_dataclass


T = TypeVar('T')


def parse_json_as(
    body: bytes,
    model: Type[T],
    encoding: str = 'utf-8'
) -> T:
    """
    Parse JSON and convert to a dataclass.

    Args:
        body: Raw body bytes
        model: Dataclass type to convert to

    Returns:
        Instance of model

    Example:
        @dataclass
        class CreateUser:
            name: str
            email: str
            age: Optional[int] = None

        user = parse_json_as(body, CreateUser)
    """
    data = parse_json(body, encoding)

    if not isinstance(data, dict):
        raise JSONParseError(f"Expected object, got {type(data).__name__}")

    if not is_dataclass(model):
        raise TypeError(f"{model} must be a dataclass")

    # Get field information
    field_names = {f.name for f in fields(model)}
    hints = get_type_hints(model)

    # Check for required fields
    kwargs = {}
    for f in fields(model):
        if f.name in data:
            # TODO: Add type validation/coercion here
            kwargs[f.name] = data[f.name]
        elif f.default is not f.default_factory:
            # Has default value
            pass
        else:
            raise JSONParseError(f"Missing required field: {f.name}")

    return model(**kwargs)
```

### Streaming JSON Parsing

For very large JSON arrays, parse incrementally:

```python
import ijson  # pip install ijson


def parse_json_stream(file_obj, prefix: str = 'item'):
    """
    Parse large JSON arrays incrementally.

    Args:
        file_obj: File-like object
        prefix: JSON path to items (e.g., 'items.item' for {"items": [...]})

    Yields:
        Individual items from the array
    """
    for item in ijson.items(file_obj, prefix):
        yield item


# Usage:
# with open('large.json', 'rb') as f:
#     for record in parse_json_stream(f, 'records.item'):
#         process(record)
```

---

## 6.6 Streaming Request Bodies

### Why Stream?

For large uploads (video, backups), loading entire body into memory is impractical:

- 1GB upload = 1GB RAM usage
- Multiple concurrent uploads = memory exhaustion
- Slower time-to-first-byte

### Streaming Interface

```python
from typing import Iterator, Callable


class StreamingBody:
    """
    Stream request body in chunks without loading entirely into memory.
    """

    def __init__(
        self,
        reader: HTTPReader,
        content_length: Optional[int],
        is_chunked: bool,
        chunk_size: int = 65536  # 64KB chunks
    ):
        self.reader = reader
        self.content_length = content_length
        self.is_chunked = is_chunked
        self.chunk_size = chunk_size
        self._bytes_read = 0
        self._exhausted = False

    def __iter__(self) -> Iterator[bytes]:
        """Iterate over body chunks."""
        return self.stream()

    def stream(self) -> Iterator[bytes]:
        """
        Yield body data in chunks.

        For Content-Length bodies, yields chunks until length reached.
        For chunked encoding, yields each decoded chunk.
        """
        if self._exhausted:
            return

        if self.is_chunked:
            yield from self._stream_chunked()
        elif self.content_length:
            yield from self._stream_fixed()

        self._exhausted = True

    def _stream_fixed(self) -> Iterator[bytes]:
        """Stream fixed-length body."""
        remaining = self.content_length

        while remaining > 0:
            to_read = min(remaining, self.chunk_size)
            chunk = self.reader.read_exactly(to_read)
            remaining -= len(chunk)
            self._bytes_read += len(chunk)
            yield chunk

    def _stream_chunked(self) -> Iterator[bytes]:
        """Stream chunked body."""
        while True:
            # Read chunk size
            size_line = self.reader.read_line().decode('ascii').split(';')[0]
            chunk_size = int(size_line.strip(), 16)

            if chunk_size == 0:
                self.reader.read_line()  # Final CRLF
                break

            # Read chunk data in sub-chunks if large
            remaining = chunk_size
            while remaining > 0:
                to_read = min(remaining, self.chunk_size)
                data = self.reader.read_exactly(to_read)
                remaining -= len(data)
                self._bytes_read += len(data)
                yield data

            self.reader.read_line()  # Chunk-ending CRLF

    def read(self, size: int = -1) -> bytes:
        """
        Read body into memory.

        Args:
            size: Max bytes to read (-1 for all)

        Returns:
            Body bytes
        """
        chunks = []
        total = 0

        for chunk in self.stream():
            if size >= 0 and total >= size:
                break
            chunks.append(chunk)
            total += len(chunk)

        return b''.join(chunks)

    @property
    def bytes_read(self) -> int:
        """Number of bytes read so far."""
        return self._bytes_read


# Usage example:
def handle_upload(request):
    """Stream upload directly to disk."""
    with open('/tmp/upload.bin', 'wb') as f:
        for chunk in request.body.stream():
            f.write(chunk)

    return Response.json({"size": request.body.bytes_read})
```

---

## 6.7 Body Size Limits and Security

### Attack Vectors

1. **Memory exhaustion**: Huge Content-Length, infinite chunks
2. **Slowloris**: Slow body transmission ties up connections
3. **Decompression bombs**: Small compressed data expands massively
4. **Billion laughs**: Recursive/nested structures in JSON/XML

### Protection Strategies

```python
@dataclass
class BodyLimits:
    """Configurable body size limits."""
    max_content_length: int = 10 * 1024 * 1024    # 10MB
    max_json_size: int = 1 * 1024 * 1024          # 1MB
    max_form_size: int = 1 * 1024 * 1024          # 1MB
    max_multipart_size: int = 100 * 1024 * 1024   # 100MB
    max_file_size: int = 50 * 1024 * 1024         # 50MB
    max_field_size: int = 1 * 1024 * 1024         # 1MB
    max_files: int = 10
    max_fields: int = 100
    body_timeout: float = 60.0                    # seconds


class SecureBodyReader:
    """Body reader with security limits."""

    def __init__(self, reader: HTTPReader, headers: dict, limits: BodyLimits = None):
        self.reader = reader
        self.headers = headers
        self.limits = limits or BodyLimits()

    def read(self) -> bytes:
        """Read body with size validation."""
        # Check Content-Length upfront
        content_length = self.headers.get('content-length')
        if content_length:
            length = int(content_length)
            if length > self.limits.max_content_length:
                raise BodyTooLargeError(
                    f"Content-Length {length} exceeds limit {self.limits.max_content_length}"
                )

        # Read with limit
        body = b''
        remaining = self.limits.max_content_length

        if 'chunked' in self.headers.get('transfer-encoding', '').lower():
            for chunk in self._read_chunked():
                if len(body) + len(chunk) > self.limits.max_content_length:
                    raise BodyTooLargeError("Chunked body exceeds limit")
                body += chunk
        elif content_length:
            body = self.reader.read_exactly(int(content_length))
        else:
            body = b''

        return body

    def _read_chunked(self) -> Iterator[bytes]:
        """Read chunks with size tracking."""
        total = 0
        while True:
            size_line = self.reader.read_line().decode('ascii').split(';')[0]
            chunk_size = int(size_line.strip(), 16)

            if chunk_size == 0:
                self.reader.read_line()
                break

            total += chunk_size
            if total > self.limits.max_content_length:
                raise BodyTooLargeError("Chunked body exceeds limit")

            yield self.reader.read_exactly(chunk_size)
            self.reader.read_line()

    def json(self) -> Any:
        """Parse as JSON with limits."""
        body = self.read()
        if len(body) > self.limits.max_json_size:
            raise BodyTooLargeError("JSON body exceeds limit")
        return parse_json(body)

    def form(self) -> Dict[str, List[str]]:
        """Parse as form data with limits."""
        body = self.read()
        if len(body) > self.limits.max_form_size:
            raise BodyTooLargeError("Form body exceeds limit")
        return parse_form_urlencoded(body)

    def multipart(self) -> MultipartData:
        """Parse as multipart with limits."""
        content_type = self.headers.get('content-type', '')
        body = self.read()  # Already limited by max_content_length

        parser = MultipartParser(
            max_file_size=self.limits.max_file_size,
            max_field_size=self.limits.max_field_size,
            max_files=self.limits.max_files,
            max_fields=self.limits.max_fields
        )

        return parser.parse(body, content_type)
```

### JSON Depth Limits

```python
def parse_json_safe(body: bytes, max_depth: int = 100) -> Any:
    """
    Parse JSON with depth limit to prevent stack overflow.

    Note: json.loads has some built-in protections, but
    this adds explicit depth checking.
    """
    text = body.decode('utf-8')

    # Count nesting before parsing
    depth = 0
    max_seen = 0
    in_string = False
    escape = False

    for char in text:
        if escape:
            escape = False
            continue
        if char == '\\' and in_string:
            escape = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char in '[{':
            depth += 1
            max_seen = max(max_seen, depth)
            if max_seen > max_depth:
                raise JSONParseError(f"JSON depth exceeds {max_depth}")
        elif char in ']}':
            depth -= 1

    return json.loads(text)
```

---

## 6.8 Unified Body Parser

### Request Object Integration

```python
from typing import Union
from enum import Enum, auto


class BodyType(Enum):
    NONE = auto()
    JSON = auto()
    FORM = auto()
    MULTIPART = auto()
    RAW = auto()


class RequestBody:
    """
    Unified interface for accessing request body.

    Lazily parses body on first access based on Content-Type.
    """

    def __init__(
        self,
        reader: SecureBodyReader,
        content_type: Optional[str]
    ):
        self._reader = reader
        self._content_type = content_type or ''
        self._raw: Optional[bytes] = None
        self._parsed: Any = None
        self._body_type: Optional[BodyType] = None

    @property
    def content_type(self) -> str:
        """Content-Type without parameters."""
        return self._content_type.split(';')[0].strip().lower()

    @property
    def body_type(self) -> BodyType:
        """Determine body type from Content-Type."""
        if self._body_type:
            return self._body_type

        ct = self.content_type
        if not ct:
            self._body_type = BodyType.NONE
        elif ct == 'application/json':
            self._body_type = BodyType.JSON
        elif ct == 'application/x-www-form-urlencoded':
            self._body_type = BodyType.FORM
        elif ct.startswith('multipart/'):
            self._body_type = BodyType.MULTIPART
        else:
            self._body_type = BodyType.RAW

        return self._body_type

    def raw(self) -> bytes:
        """Get raw body bytes."""
        if self._raw is None:
            self._raw = self._reader.read()
        return self._raw

    def text(self, encoding: str = 'utf-8') -> str:
        """Get body as text."""
        return self.raw().decode(encoding)

    def json(self) -> Any:
        """Parse body as JSON."""
        if self._body_type == BodyType.JSON and self._parsed is not None:
            return self._parsed

        self._parsed = self._reader.json()
        self._body_type = BodyType.JSON
        return self._parsed

    def form(self) -> Dict[str, List[str]]:
        """Parse body as URL-encoded form."""
        if self._body_type == BodyType.FORM and self._parsed is not None:
            return self._parsed

        self._parsed = self._reader.form()
        self._body_type = BodyType.FORM
        return self._parsed

    def multipart(self) -> MultipartData:
        """Parse body as multipart form data."""
        if self._body_type == BodyType.MULTIPART and self._parsed is not None:
            return self._parsed

        self._parsed = self._reader.multipart()
        self._body_type = BodyType.MULTIPART
        return self._parsed

    def auto(self) -> Union[dict, MultipartData, bytes, None]:
        """
        Automatically parse based on Content-Type.

        Returns:
            - dict for JSON
            - dict for form (single values)
            - MultipartData for multipart
            - bytes for other content types
            - None for empty body
        """
        bt = self.body_type

        if bt == BodyType.NONE:
            return None
        elif bt == BodyType.JSON:
            return self.json()
        elif bt == BodyType.FORM:
            return parse_form_urlencoded_single(self.raw())
        elif bt == BodyType.MULTIPART:
            return self.multipart()
        else:
            return self.raw()


# Integration with HTTPRequest
@dataclass
class HTTPRequest:
    method: str
    path: str
    headers: Dict[str, str]
    _body: RequestBody = None

    @property
    def body(self) -> RequestBody:
        return self._body

    def json(self) -> Any:
        return self._body.json()

    def form(self) -> Dict[str, List[str]]:
        return self._body.form()
```

---

## 6.9 Lab: Build a File Upload Server

### Requirements

Build a server that:

1. Accepts multipart file uploads
2. Validates file types (only images)
3. Limits file size to 5MB
4. Saves files with UUID names
5. Returns metadata about uploaded files

### Implementation

```python
import uuid
import os
from pathlib import Path


UPLOAD_DIR = Path('/tmp/uploads')
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_TYPES = {'image/jpeg', 'image/png', 'image/gif', 'image/webp'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


@app.post('/upload')
def handle_upload(request: HTTPRequest) -> HTTPResponse:
    """Handle file upload."""
    if request.body.body_type != BodyType.MULTIPART:
        return Response.error(400, "Expected multipart/form-data")

    try:
        data = request.body.multipart()
    except ValueError as e:
        return Response.error(400, str(e))

    uploaded = []

    for file_list in data.files.values():
        for file in file_list:
            # Validate content type
            if file.content_type not in ALLOWED_TYPES:
                return Response.error(
                    415,
                    f"Unsupported file type: {file.content_type}"
                )

            # Validate size
            if file.size > MAX_FILE_SIZE:
                return Response.error(
                    413,
                    f"File too large: {file.size} > {MAX_FILE_SIZE}"
                )

            # Generate safe filename
            ext = Path(file.filename).suffix.lower()
            if ext not in {'.jpg', '.jpeg', '.png', '.gif', '.webp'}:
                ext = '.bin'

            new_filename = f"{uuid.uuid4()}{ext}"
            save_path = UPLOAD_DIR / new_filename

            # Save file
            file.save(str(save_path))

            uploaded.append({
                "original_name": file.filename,
                "saved_as": new_filename,
                "size": file.size,
                "content_type": file.content_type,
                "url": f"/files/{new_filename}"
            })

    # Cleanup
    data.close()

    return Response.json({
        "uploaded": len(uploaded),
        "files": uploaded
    })


@app.get('/files/{filename}')
def serve_file(request: HTTPRequest) -> HTTPResponse:
    """Serve uploaded file."""
    filename = request.path_params['filename']

    # Prevent directory traversal
    if '..' in filename or '/' in filename:
        return Response.error(400, "Invalid filename")

    filepath = UPLOAD_DIR / filename
    if not filepath.exists():
        return Response.error(404, "File not found")

    return Response.file(str(filepath))
```

---

## Exercises

### Exercise 6.1: Content-Type Detection

Implement automatic content-type detection for uploads without Content-Type:

```python
def detect_content_type(data: bytes) -> str:
    """Detect content type from magic bytes."""
    # Implement magic byte detection for common formats
    pass
```

### Exercise 6.2: Streaming JSON

Implement streaming JSON response for large datasets:

```python
def stream_json_array(items: Iterator) -> Iterator[bytes]:
    """Stream items as JSON array without loading all in memory."""
    pass
```

### Exercise 6.3: Base64 Decoding

Some APIs send files as base64 in JSON. Implement handling:

```python
@dataclass
class Base64File:
    data: str  # base64 encoded
    filename: str
    content_type: str

    def decode(self) -> bytes:
        """Decode base64 data."""
        pass
```

### Exercise 6.4: Resumable Uploads

Implement resumable uploads using Content-Range:

```python
@app.patch('/upload/{id}')
def resume_upload(request: HTTPRequest) -> HTTPResponse:
    """Resume a partial upload."""
    # Parse Content-Range header
    # Append data to existing file
    pass
```

### Exercise 6.5: Request Body Validation

Add schema validation for JSON bodies:

```python
from typing import TypedDict


class CreateUser(TypedDict):
    name: str
    email: str
    age: int


def validate_json(body: bytes, schema: Type[TypedDict]) -> dict:
    """Validate JSON against TypedDict schema."""
    pass
```

---

## Deep Dive Questions

1. **Why does multipart use boundaries instead of Content-Length for each part?**

2. **What security risks exist with accepting arbitrary filenames from uploads?**

3. **How would you implement upload progress tracking in an HTTP server?**

4. **Why might chunked encoding be used for requests (not just responses)?**

5. **What happens if a client sends Content-Length but then sends fewer bytes?**

---

## Resources

### RFCs
- [RFC 7578 - Returning Values from Forms: multipart/form-data](https://tools.ietf.org/html/rfc7578)
- [RFC 7231 - HTTP/1.1 Semantics and Content](https://tools.ietf.org/html/rfc7231)

### Libraries
- [python-multipart](https://github.com/andrew-d/python-multipart) — Streaming multipart parser
- [ijson](https://github.com/ICRAR/ijson) — Iterative JSON parser

### Security
- [OWASP File Upload](https://owasp.org/www-community/vulnerabilities/Unrestricted_File_Upload)

---

## Summary

You've mastered request body handling:

1. **Content-Length** — Fixed-size body reading
2. **Chunked encoding** — Variable-size streaming
3. **URL-encoded forms** — Simple key-value parsing
4. **Multipart forms** — File uploads with proper parsing
5. **JSON** — Parsing with validation and depth limits
6. **Streaming** — Memory-efficient large body handling
7. **Security** — Size limits, type validation, timeout protection
8. **Unified interface** — Auto-detection and lazy parsing

The next module covers the other half of the equation: generating responses.

---

## Next Module

**[Module 7: Response Generation →](./MODULE_07_RESPONSE.md)**

We'll implement response builders for text, JSON, HTML, files, streaming, and compression.

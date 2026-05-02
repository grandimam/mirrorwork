# Building a Static File Server on Raw ASGI

## Table of Contents

1. [Why Build a Static File Server on ASGI](#why-build-a-static-file-server-on-asgi)
2. [Basic File Serving](#basic-file-serving)
3. [Content-Type Detection](#content-type-detection)
4. [Streaming Large Files in Chunks](#streaming-large-files-in-chunks)
5. [Directory Listing](#directory-listing)
6. [404 Handling](#404-handling)
7. [Security: Path Traversal Prevention](#security-path-traversal-prevention)
8. [Caching: ETags, Last-Modified, Cache-Control](#caching)
9. [Range Requests (206 Partial Content)](#range-requests)
10. [Gzip Compression](#gzip-compression)
11. [SPA Fallback](#spa-fallback)
12. [Mounting as a Sub-Application](#mounting-as-a-sub-application)
13. [Complete Working Implementation](#complete-working-implementation)

---

## Why Build a Static File Server on ASGI

ASGI (Asynchronous Server Gateway Interface) provides a low-level, protocol-agnostic
interface between Python async web servers and applications. Building a static file server
directly on ASGI -- without frameworks like Starlette or FastAPI -- offers several
advantages:

- **Zero dependencies.** The entire server runs on the Python standard library plus an
  ASGI server like `uvicorn` or `hypercorn`.
- **Full control over HTTP semantics.** You decide exactly which headers to send, how to
  handle range requests, and how caching behaves. There is no framework magic to debug.
- **Educational value.** Understanding the raw ASGI protocol makes you a better user of
  the frameworks built on top of it.
- **Minimal overhead.** No middleware stack, no routing abstraction, no request/response
  object allocation. Just dictionaries and byte strings.
- **Embeddable.** A raw ASGI static file app can be mounted into any ASGI application
  tree without importing a framework.

The ASGI callable signature is:

```python
async def app(scope: dict, receive: Callable, send: Callable) -> None:
    ...
```

Where:
- `scope` is a dictionary of connection metadata (type, path, headers, query string, etc.)
- `receive` is an async callable that returns the next incoming event
- `send` is an async callable that dispatches an outgoing event

For HTTP, the relevant event types are `http.request` (incoming body) and
`http.response.start` / `http.response.body` (outgoing response).

---

## Basic File Serving

The simplest possible static file server reads the request path from `scope["path"]`,
maps it to a file on disk, reads the bytes, and sends them back.

```python
import os

STATIC_ROOT = "/var/www/static"


async def app(scope, receive, send):
    assert scope["type"] == "http"

    # Extract the request path and map it to a filesystem path.
    request_path = scope["path"]
    file_path = os.path.join(STATIC_ROOT, request_path.lstrip("/"))

    if not os.path.isfile(file_path):
        await send_404(send)
        return

    with open(file_path, "rb") as f:
        body = f.read()

    await send({
        "type": "http.response.start",
        "status": 200,
        "headers": [
            [b"content-type", b"application/octet-stream"],
            [b"content-length", str(len(body)).encode()],
        ],
    })
    await send({
        "type": "http.response.body",
        "body": body,
    })


async def send_404(send):
    body = b"Not Found"
    await send({
        "type": "http.response.start",
        "status": 404,
        "headers": [
            [b"content-type", b"text/plain"],
            [b"content-length", str(len(body)).encode()],
        ],
    })
    await send({
        "type": "http.response.body",
        "body": body,
    })
```

This works, but it has serious problems: no content-type detection, no streaming, no
security, and no caching. The rest of this document addresses each of these.

---

## Content-Type Detection

The `mimetypes` module in the standard library maps file extensions to MIME types. This
is the canonical way to determine `Content-Type` without pulling in third-party packages.

```python
import mimetypes

# Ensure the module has loaded its database.
mimetypes.init()


def guess_content_type(file_path: str) -> str:
    """Return a MIME type for the given file path, with a sensible default."""
    content_type, encoding = mimetypes.guess_type(file_path)
    if content_type is None:
        return "application/octet-stream"
    # If the file is gzip-encoded (e.g., .tar.gz), the content_type will be
    # the inner type and encoding will be "gzip". For serving static files,
    # we typically want to return the outer type as-is.
    return content_type
```

Common mappings that `mimetypes` knows about:

| Extension | MIME Type                |
|-----------|--------------------------|
| `.html`   | `text/html`              |
| `.css`    | `text/css`               |
| `.js`     | `application/javascript` |
| `.json`   | `application/json`       |
| `.png`    | `image/png`              |
| `.svg`    | `image/svg+xml`          |
| `.woff2`  | `font/woff2`             |

For text types, appending `; charset=utf-8` is good practice:

```python
def content_type_header(file_path: str) -> bytes:
    ct = guess_content_type(file_path)
    if ct.startswith("text/") or ct in (
        "application/javascript",
        "application/json",
        "image/svg+xml",
    ):
        ct += "; charset=utf-8"
    return ct.encode()
```

---

## Streaming Large Files in Chunks

Reading an entire file into memory is unacceptable for large assets (videos, archives,
disk images). ASGI supports streaming by sending multiple `http.response.body` events
with `more_body=True`.

```python
import os
import asyncio

CHUNK_SIZE = 64 * 1024  # 64 KB


async def send_file_streaming(send, file_path: str, status: int = 200,
                               headers: list = None):
    """Stream a file to the client in chunks."""
    file_size = os.path.getsize(file_path)
    content_type = content_type_header(file_path)

    response_headers = [
        [b"content-type", content_type],
        [b"content-length", str(file_size).encode()],
    ]
    if headers:
        response_headers.extend(headers)

    await send({
        "type": "http.response.start",
        "status": status,
        "headers": response_headers,
    })

    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                # Final empty send to signal end of body.
                await send({
                    "type": "http.response.body",
                    "body": b"",
                    "more_body": False,
                })
                break
            # Determine if there is more data after this chunk.
            more = f.tell() < file_size
            await send({
                "type": "http.response.body",
                "body": chunk,
                "more_body": more,
            })
            if not more:
                break
```

Key points:

- `more_body=True` tells the ASGI server to keep the connection open for additional
  body chunks.
- `more_body=False` (or omitting it, since `False` is the default) signals that the
  response is complete.
- The `Content-Length` header is still set so clients know the total size.
- For truly async I/O, you could use `aiofiles` or run file reads in a thread pool via
  `asyncio.get_event_loop().run_in_executor(None, f.read, CHUNK_SIZE)`. The synchronous
  version shown here is acceptable for most workloads because file I/O on local disks
  is fast and non-blocking in practice.

Using a thread pool executor for non-blocking reads:

```python
async def read_chunk(f, size):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, f.read, size)
```

---

## Directory Listing

When the request path maps to a directory, you can generate an HTML listing of its
contents. This is useful for development servers and internal tooling, but should usually
be disabled in production.

```python
import os
import html


def build_directory_listing(dir_path: str, url_path: str) -> bytes:
    """Generate an HTML page listing the contents of a directory."""
    entries = sorted(os.listdir(dir_path))
    lines = [
        "<!DOCTYPE html>",
        "<html><head>",
        f"<title>Index of {html.escape(url_path)}</title>",
        "<style>",
        "  body { font-family: monospace; padding: 2rem; }",
        "  a { text-decoration: none; }",
        "  a:hover { text-decoration: underline; }",
        "  .entry { padding: 0.2rem 0; }",
        "  .size { color: #666; margin-left: 1rem; }",
        "</style>",
        "</head><body>",
        f"<h1>Index of {html.escape(url_path)}</h1>",
        "<hr>",
    ]

    # Parent directory link (unless we are at the root).
    if url_path != "/":
        parent = os.path.dirname(url_path.rstrip("/")) or "/"
        lines.append(f'<div class="entry"><a href="{parent}">../</a></div>')

    for entry in entries:
        full = os.path.join(dir_path, entry)
        display = html.escape(entry)
        href = os.path.join(url_path, entry)
        if os.path.isdir(full):
            display += "/"
            href += "/"
            size_str = "-"
        else:
            size_str = format_size(os.path.getsize(full))
        lines.append(
            f'<div class="entry">'
            f'<a href="{href}">{display}</a>'
            f'<span class="size">{size_str}</span>'
            f'</div>'
        )

    lines.extend(["<hr>", "</body></html>"])
    return "\n".join(lines).encode("utf-8")


def format_size(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024:
            return f"{size:.1f} {unit}" if unit != "B" else f"{size} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


async def send_directory_listing(send, dir_path: str, url_path: str):
    body = build_directory_listing(dir_path, url_path)
    await send({
        "type": "http.response.start",
        "status": 200,
        "headers": [
            [b"content-type", b"text/html; charset=utf-8"],
            [b"content-length", str(len(body)).encode()],
        ],
    })
    await send({
        "type": "http.response.body",
        "body": body,
    })
```

Integrate it into the main app by checking `os.path.isdir()` before `os.path.isfile()`:

```python
if os.path.isdir(file_path):
    # Optionally redirect /dir to /dir/ to normalize URLs.
    if not request_path.endswith("/"):
        await send_redirect(send, request_path + "/")
        return
    # Check for index.html first.
    index = os.path.join(file_path, "index.html")
    if os.path.isfile(index):
        await send_file_streaming(send, index)
    else:
        await send_directory_listing(send, file_path, request_path)
    return
```

---

## 404 Handling

A proper 404 response should include a `Content-Type` header and a meaningful body.
You may want to serve a custom 404.html if one exists.

```python
NOT_FOUND_BODY = b"""<!DOCTYPE html>
<html>
<head><title>404 Not Found</title></head>
<body>
<h1>404 Not Found</h1>
<p>The requested resource does not exist on this server.</p>
</body>
</html>"""


async def send_404(send):
    await send({
        "type": "http.response.start",
        "status": 404,
        "headers": [
            [b"content-type", b"text/html; charset=utf-8"],
            [b"content-length", str(len(NOT_FOUND_BODY)).encode()],
        ],
    })
    await send({
        "type": "http.response.body",
        "body": NOT_FOUND_BODY,
    })


async def send_405(send):
    """Only GET and HEAD are valid for static files."""
    body = b"Method Not Allowed"
    await send({
        "type": "http.response.start",
        "status": 405,
        "headers": [
            [b"content-type", b"text/plain"],
            [b"content-length", str(len(body)).encode()],
            [b"allow", b"GET, HEAD"],
        ],
    })
    await send({
        "type": "http.response.body",
        "body": body,
    })
```

---

## Security: Path Traversal Prevention

This is the most critical section. A naive `os.path.join(root, user_input)` is
vulnerable to path traversal attacks where an attacker sends `GET /../../etc/passwd`.

### The Attack

```
GET /../../etc/passwd HTTP/1.1
GET /%2e%2e/%2e%2e/etc/passwd HTTP/1.1
GET /..%252f..%252f/etc/passwd HTTP/1.1
```

Note that ASGI servers typically decode percent-encoding in `scope["path"]`, so `%2e`
becomes `.` before your application sees it. However, double-encoding and other tricks
may bypass naive checks.

### The Defense: `os.path.realpath` + Prefix Check

The only reliable defense is to resolve the absolute, canonical path and verify it starts
with the static root:

```python
import os


def safe_file_path(root: str, request_path: str) -> str | None:
    """
    Resolve the request path to a canonical filesystem path.
    Return None if the resolved path escapes the root directory.
    """
    # os.path.join ignores the first argument if the second is absolute,
    # so strip leading slashes from the request path.
    cleaned = request_path.lstrip("/")

    # Join with the root.
    joined = os.path.join(root, cleaned)

    # Resolve to a canonical absolute path. This collapses ../, resolves
    # symlinks, and normalizes the path.
    real = os.path.realpath(joined)

    # Ensure the real root is used for comparison (it may differ if root
    # itself contains symlinks).
    real_root = os.path.realpath(root)

    # The resolved path must start with the root path followed by a separator
    # (or be exactly the root path for directory requests).
    if real == real_root or real.startswith(real_root + os.sep):
        return real

    return None
```

### Symlink Policy

`os.path.realpath` resolves symlinks, which means a symlink inside your static root that
points outside of it will be rejected by the prefix check. This is the safe default.

If you explicitly want to allow certain symlinks, you can use `os.path.abspath` (which
normalizes `..` without resolving symlinks) and then separately check the symlink target:

```python
def safe_file_path_allow_symlinks(root: str, request_path: str) -> str | None:
    """Like safe_file_path, but allows symlinks within the root."""
    cleaned = request_path.lstrip("/")
    joined = os.path.join(root, cleaned)
    absolute = os.path.abspath(joined)
    abs_root = os.path.abspath(root)

    if absolute == abs_root or absolute.startswith(abs_root + os.sep):
        return absolute
    return None
```

Be aware that this is less safe -- a symlink inside the root can point anywhere.

### Hidden File Filtering

Files starting with `.` (dotfiles) are conventionally hidden on Unix systems. Serving
`.env`, `.git/config`, or `.htaccess` is a security risk.

```python
def has_hidden_component(path: str, root: str) -> bool:
    """Return True if any component of the path (relative to root) is hidden."""
    relative = os.path.relpath(path, root)
    parts = relative.split(os.sep)
    return any(part.startswith(".") for part in parts)
```

Integrate these checks into the main application:

```python
async def app(scope, receive, send):
    assert scope["type"] == "http"

    method = scope.get("method", "GET")
    if method not in ("GET", "HEAD"):
        await send_405(send)
        return

    file_path = safe_file_path(STATIC_ROOT, scope["path"])
    if file_path is None:
        await send_404(send)
        return

    if has_hidden_component(file_path, STATIC_ROOT):
        await send_404(send)
        return

    # ... continue with file serving
```

---

## Caching

Proper caching headers drastically reduce bandwidth and latency. There are three
complementary mechanisms.

### ETag + If-None-Match

An ETag is an opaque identifier for a specific version of a resource. A common strategy
is to hash the file's modification time and size:

```python
import hashlib
import os


def compute_etag(file_path: str) -> str:
    """Compute a weak ETag based on mtime and size."""
    stat = os.stat(file_path)
    raw = f"{stat.st_mtime_ns}-{stat.st_size}".encode()
    digest = hashlib.md5(raw).hexdigest()
    return f'W/"{digest}"'
```

A strong ETag would hash the file contents, but that defeats the purpose if you have to
read the file to generate it. The weak ETag above is sufficient for static file caching.

### Last-Modified + If-Modified-Since

```python
import email.utils
import time


def last_modified_header(file_path: str) -> bytes:
    mtime = os.path.getmtime(file_path)
    formatted = email.utils.formatdate(mtime, usegmt=True)
    return formatted.encode()


def parse_http_date(date_str: str) -> float | None:
    """Parse an HTTP date string to a Unix timestamp."""
    try:
        return email.utils.parsedate_to_datetime(date_str).timestamp()
    except (ValueError, TypeError):
        return None
```

### 304 Not Modified Logic

Extract request headers from `scope["headers"]` (a list of `[name, value]` byte pairs):

```python
def get_request_header(scope: dict, name: bytes) -> bytes | None:
    """Extract a request header value by name (case-insensitive)."""
    name_lower = name.lower()
    for header_name, header_value in scope.get("headers", []):
        if header_name.lower() == name_lower:
            return header_value
    return None


async def serve_file_with_caching(scope, send, file_path: str):
    stat = os.stat(file_path)
    etag = compute_etag(file_path)
    mtime = stat.st_mtime

    # Check If-None-Match.
    if_none_match = get_request_header(scope, b"if-none-match")
    if if_none_match is not None:
        # The header may contain multiple ETags separated by commas.
        client_etags = [t.strip() for t in if_none_match.decode().split(",")]
        if etag in client_etags or "*" in client_etags:
            await send_304(send, etag, mtime)
            return

    # Check If-Modified-Since (only if If-None-Match was not present).
    if_modified_since = get_request_header(scope, b"if-modified-since")
    if if_modified_since is not None:
        since = parse_http_date(if_modified_since.decode())
        if since is not None and mtime <= since:
            await send_304(send, etag, mtime)
            return

    # Serve the file with caching headers.
    headers = [
        [b"etag", etag.encode()],
        [b"last-modified", last_modified_header(file_path)],
        [b"cache-control", b"public, max-age=3600"],
    ]
    await send_file_streaming(send, file_path, headers=headers)


async def send_304(send, etag: str, mtime: float):
    await send({
        "type": "http.response.start",
        "status": 304,
        "headers": [
            [b"etag", etag.encode()],
            [b"last-modified",
             email.utils.formatdate(mtime, usegmt=True).encode()],
            [b"cache-control", b"public, max-age=3600"],
        ],
    })
    await send({
        "type": "http.response.body",
        "body": b"",
    })
```

### Cache-Control Strategies

Different file types deserve different caching policies:

```python
def cache_control_for(file_path: str) -> bytes:
    """Return an appropriate Cache-Control header value."""
    ct = guess_content_type(file_path)

    # Immutable assets with hashed filenames (e.g., app.a1b2c3.js).
    basename = os.path.basename(file_path)
    if has_content_hash(basename):
        return b"public, max-age=31536000, immutable"

    # HTML should always be revalidated.
    if ct == "text/html":
        return b"public, no-cache"

    # Everything else: cache for 1 hour.
    return b"public, max-age=3600"


def has_content_hash(filename: str) -> bool:
    """Heuristic: check if the filename contains a hex hash before the extension."""
    # Matches patterns like: app.a1b2c3d4.js, style.8f3e2a.css
    parts = filename.rsplit(".", 2)
    if len(parts) >= 3:
        potential_hash = parts[-2]
        return len(potential_hash) >= 6 and all(
            c in "0123456789abcdef" for c in potential_hash
        )
    return False
```

---

## Range Requests

Range requests allow clients to fetch a portion of a file. This is essential for
resumable downloads and media seeking. A client sends `Range: bytes=0-1023` and the
server responds with `206 Partial Content`.

```python
def parse_range_header(range_header: str, file_size: int) -> list[tuple[int, int]] | None:
    """
    Parse an HTTP Range header and return a list of (start, end) byte ranges.
    Returns None if the header is invalid or unsatisfiable.
    end is inclusive (per HTTP spec).
    """
    if not range_header.startswith("bytes="):
        return None

    ranges = []
    for part in range_header[6:].split(","):
        part = part.strip()
        if part.startswith("-"):
            # Suffix range: last N bytes.
            suffix_length = int(part[1:])
            if suffix_length == 0:
                return None
            start = max(0, file_size - suffix_length)
            end = file_size - 1
        elif part.endswith("-"):
            # Open-ended range: from start to end of file.
            start = int(part[:-1])
            end = file_size - 1
        else:
            start_str, end_str = part.split("-", 1)
            start = int(start_str)
            end = int(end_str)

        if start > end or start >= file_size:
            return None

        # Clamp the end to file_size - 1.
        end = min(end, file_size - 1)
        ranges.append((start, end))

    return ranges if ranges else None


async def send_range_response(send, file_path: str, start: int, end: int,
                                file_size: int, extra_headers: list = None):
    """Send a 206 Partial Content response for a single byte range."""
    content_length = end - start + 1
    content_type = content_type_header(file_path)

    headers = [
        [b"content-type", content_type],
        [b"content-length", str(content_length).encode()],
        [b"content-range", f"bytes {start}-{end}/{file_size}".encode()],
        [b"accept-ranges", b"bytes"],
    ]
    if extra_headers:
        headers.extend(extra_headers)

    await send({
        "type": "http.response.start",
        "status": 206,
        "headers": headers,
    })

    with open(file_path, "rb") as f:
        f.seek(start)
        remaining = content_length
        while remaining > 0:
            chunk_size = min(CHUNK_SIZE, remaining)
            chunk = f.read(chunk_size)
            if not chunk:
                break
            remaining -= len(chunk)
            await send({
                "type": "http.response.body",
                "body": chunk,
                "more_body": remaining > 0,
            })


async def send_416(send, file_size: int):
    """416 Range Not Satisfiable."""
    body = b"Range Not Satisfiable"
    await send({
        "type": "http.response.start",
        "status": 416,
        "headers": [
            [b"content-type", b"text/plain"],
            [b"content-range", f"bytes */{file_size}".encode()],
            [b"content-length", str(len(body)).encode()],
        ],
    })
    await send({
        "type": "http.response.body",
        "body": body,
    })
```

Integration into the file serving flow:

```python
# Always advertise range support.
base_headers = [
    [b"accept-ranges", b"bytes"],
]

range_header = get_request_header(scope, b"range")
if range_header is not None:
    file_size = os.path.getsize(file_path)
    ranges = parse_range_header(range_header.decode(), file_size)
    if ranges is None:
        await send_416(send, file_size)
        return
    # For simplicity, handle only single-range requests.
    start, end = ranges[0]
    await send_range_response(send, file_path, start, end, file_size)
    return
```

---

## Gzip Compression

Compressing text-based responses (HTML, CSS, JS, JSON, SVG) saves bandwidth. Check
whether the client accepts gzip via the `Accept-Encoding` header.

```python
import gzip
import io

COMPRESSIBLE_TYPES = {
    "text/html",
    "text/css",
    "text/plain",
    "text/xml",
    "application/javascript",
    "application/json",
    "application/xml",
    "image/svg+xml",
}

# Only compress files larger than this threshold.
MIN_COMPRESS_SIZE = 256


def client_accepts_gzip(scope: dict) -> bool:
    ae = get_request_header(scope, b"accept-encoding")
    if ae is None:
        return False
    return b"gzip" in ae.lower()


def should_compress(file_path: str, file_size: int) -> bool:
    ct = guess_content_type(file_path)
    return ct in COMPRESSIBLE_TYPES and file_size >= MIN_COMPRESS_SIZE


async def send_file_gzipped(send, file_path: str, headers: list = None):
    """Read the file, gzip it in memory, and send it."""
    with open(file_path, "rb") as f:
        raw = f.read()

    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", compresslevel=6) as gz:
        gz.write(raw)
    compressed = buf.getvalue()

    content_type = content_type_header(file_path)
    response_headers = [
        [b"content-type", content_type],
        [b"content-encoding", b"gzip"],
        [b"content-length", str(len(compressed)).encode()],
        # Vary is critical: caches must store separate versions for
        # gzip and non-gzip clients.
        [b"vary", b"Accept-Encoding"],
    ]
    if headers:
        response_headers.extend(headers)

    await send({
        "type": "http.response.start",
        "status": 200,
        "headers": response_headers,
    })
    await send({
        "type": "http.response.body",
        "body": compressed,
    })
```

For very large text files, you can stream the gzip compression. However, streaming gzip
changes the content length (you cannot know it in advance), so you would need to use
chunked transfer encoding or omit `Content-Length`:

```python
async def send_file_gzipped_streaming(send, file_path: str, headers: list = None):
    """Stream a gzip-compressed file. No Content-Length header."""
    content_type = content_type_header(file_path)
    response_headers = [
        [b"content-type", content_type],
        [b"content-encoding", b"gzip"],
        [b"vary", b"Accept-Encoding"],
    ]
    if headers:
        response_headers.extend(headers)

    await send({
        "type": "http.response.start",
        "status": 200,
        "headers": response_headers,
    })

    compressor = gzip.open(file_path, "rb")
    try:
        while True:
            chunk = compressor.read(CHUNK_SIZE)
            if not chunk:
                await send({
                    "type": "http.response.body",
                    "body": b"",
                    "more_body": False,
                })
                break
            await send({
                "type": "http.response.body",
                "body": chunk,
                "more_body": True,
            })
    finally:
        compressor.close()
```

A better production strategy: pre-compress files at build time (generating `.gz`
siblings) and serve the pre-compressed version when available:

```python
def precompressed_path(file_path: str) -> str | None:
    gz_path = file_path + ".gz"
    if os.path.isfile(gz_path):
        # Ensure the .gz file is not stale.
        if os.path.getmtime(gz_path) >= os.path.getmtime(file_path):
            return gz_path
    return None
```

---

## SPA Fallback

Single-page applications need the server to return `index.html` for any path that does
not match a real file. Client-side routing then takes over.

```python
SPA_INDEX = os.path.join(STATIC_ROOT, "index.html")


async def app_with_spa_fallback(scope, receive, send):
    assert scope["type"] == "http"

    method = scope.get("method", "GET")
    if method not in ("GET", "HEAD"):
        await send_405(send)
        return

    is_head = method == "HEAD"
    request_path = scope["path"]

    file_path = safe_file_path(STATIC_ROOT, request_path)

    # Serve the file if it exists.
    if file_path is not None and os.path.isfile(file_path):
        await serve_file_with_caching(scope, send, file_path)
        return

    # SPA fallback: serve index.html for HTML requests.
    accept = get_request_header(scope, b"accept")
    if accept is not None and b"text/html" in accept:
        if os.path.isfile(SPA_INDEX):
            await send_file_streaming(send, SPA_INDEX, headers=[
                # Do not cache the SPA shell -- it must always be fresh.
                [b"cache-control", b"public, no-cache"],
            ])
            return

    await send_404(send)
```

The `Accept` header check is important: API calls (which typically send
`Accept: application/json`) should get a proper 404 instead of HTML.

---

## Mounting as a Sub-Application

To serve static files under a prefix like `/static/`, create a wrapper that strips the
prefix from the scope before passing it to the static file app:

```python
class MountedApp:
    """Mount an ASGI app at a given path prefix."""

    def __init__(self, path: str, app):
        # Normalize: /static/ -> /static
        self.path = path.rstrip("/")
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_path = scope["path"]

        # Check if the request path matches the mount prefix.
        if request_path == self.path or request_path.startswith(self.path + "/"):
            # Strip the prefix from the path.
            inner_path = request_path[len(self.path):] or "/"
            # Create a new scope with the adjusted path and root_path.
            inner_scope = dict(scope)
            inner_scope["path"] = inner_path
            inner_scope["root_path"] = scope.get("root_path", "") + self.path
            await self.app(inner_scope, receive, send)
        else:
            # Not our prefix -- return 404 or delegate to another app.
            await send_404(send)
```

Usage:

```python
# Mount the static file server at /static/.
mounted_static = MountedApp("/static", static_file_app)

# Compose with other apps.
async def root_app(scope, receive, send):
    path = scope.get("path", "/")
    if path.startswith("/static"):
        await mounted_static(scope, receive, send)
    elif path.startswith("/api"):
        await api_app(scope, receive, send)
    else:
        await spa_app(scope, receive, send)
```

---

## Complete Working Implementation

Below is a self-contained static file server that combines every technique from this
document. Save it as `static_server.py` and run with:

```bash
uvicorn static_server:app --host 0.0.0.0 --port 8000
```

```python
"""
A complete ASGI static file server.

Features:
- Content-Type detection via mimetypes
- Streaming response for large files
- Directory listing with HTML UI
- Path traversal prevention
- Hidden file filtering
- ETag and Last-Modified caching with 304 support
- Cache-Control with content-hash detection
- Range requests (206 Partial Content)
- Gzip compression for text-based files
- SPA fallback (serve index.html for unmatched HTML requests)
- Mountable under a URL prefix

Usage:
    STATIC_ROOT=/path/to/files uvicorn static_server:app
"""

import asyncio
import email.utils
import gzip
import hashlib
import html
import io
import mimetypes
import os

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

STATIC_ROOT = os.environ.get("STATIC_ROOT", os.path.join(os.getcwd(), "static"))
CHUNK_SIZE = 64 * 1024  # 64 KB
MIN_COMPRESS_SIZE = 256
ENABLE_DIRECTORY_LISTING = os.environ.get("DIRECTORY_LISTING", "0") == "1"
ENABLE_SPA_FALLBACK = os.environ.get("SPA_FALLBACK", "0") == "1"
MOUNT_PREFIX = os.environ.get("MOUNT_PREFIX", "")  # e.g., "/static"

mimetypes.init()

COMPRESSIBLE_TYPES = {
    "text/html", "text/css", "text/plain", "text/xml",
    "application/javascript", "application/json",
    "application/xml", "image/svg+xml",
}

NOT_FOUND_BODY = b"""<!DOCTYPE html>
<html>
<head><title>404 Not Found</title></head>
<body><h1>404 Not Found</h1>
<p>The requested resource does not exist on this server.</p>
</body></html>"""


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def guess_content_type(file_path: str) -> str:
    content_type, _ = mimetypes.guess_type(file_path)
    return content_type or "application/octet-stream"


def content_type_header(file_path: str) -> bytes:
    ct = guess_content_type(file_path)
    if ct.startswith("text/") or ct in (
        "application/javascript", "application/json", "image/svg+xml",
    ):
        ct += "; charset=utf-8"
    return ct.encode()


def get_request_header(scope: dict, name: bytes) -> bytes | None:
    name_lower = name.lower()
    for header_name, header_value in scope.get("headers", []):
        if header_name.lower() == name_lower:
            return header_value
    return None


def safe_file_path(root: str, request_path: str) -> str | None:
    cleaned = request_path.lstrip("/")
    joined = os.path.join(root, cleaned)
    real = os.path.realpath(joined)
    real_root = os.path.realpath(root)
    if real == real_root or real.startswith(real_root + os.sep):
        return real
    return None


def has_hidden_component(path: str, root: str) -> bool:
    relative = os.path.relpath(path, root)
    parts = relative.split(os.sep)
    return any(part.startswith(".") for part in parts)


def compute_etag(stat_result: os.stat_result) -> str:
    raw = f"{stat_result.st_mtime_ns}-{stat_result.st_size}".encode()
    digest = hashlib.md5(raw).hexdigest()
    return f'W/"{digest}"'


def format_mtime(mtime: float) -> bytes:
    return email.utils.formatdate(mtime, usegmt=True).encode()


def parse_http_date(date_str: str) -> float | None:
    try:
        return email.utils.parsedate_to_datetime(date_str).timestamp()
    except (ValueError, TypeError):
        return None


def has_content_hash(filename: str) -> bool:
    parts = filename.rsplit(".", 2)
    if len(parts) >= 3:
        h = parts[-2]
        return len(h) >= 6 and all(c in "0123456789abcdef" for c in h)
    return False


def cache_control_for(file_path: str) -> bytes:
    if has_content_hash(os.path.basename(file_path)):
        return b"public, max-age=31536000, immutable"
    ct = guess_content_type(file_path)
    if ct == "text/html":
        return b"public, no-cache"
    return b"public, max-age=3600"


def client_accepts_gzip(scope: dict) -> bool:
    ae = get_request_header(scope, b"accept-encoding")
    return ae is not None and b"gzip" in ae.lower()


def parse_range_header(header: str, file_size: int) -> list[tuple[int, int]] | None:
    if not header.startswith("bytes="):
        return None
    ranges = []
    for part in header[6:].split(","):
        part = part.strip()
        try:
            if part.startswith("-"):
                suffix = int(part[1:])
                if suffix == 0:
                    return None
                start = max(0, file_size - suffix)
                end = file_size - 1
            elif part.endswith("-"):
                start = int(part[:-1])
                end = file_size - 1
            else:
                s, e = part.split("-", 1)
                start, end = int(s), int(e)
        except ValueError:
            return None
        if start > end or start >= file_size:
            return None
        end = min(end, file_size - 1)
        ranges.append((start, end))
    return ranges if ranges else None


def format_size(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024:
            return f"{size:.1f} {unit}" if unit != "B" else f"{size} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


def build_directory_listing(dir_path: str, url_path: str) -> bytes:
    entries = sorted(os.listdir(dir_path))
    lines = [
        "<!DOCTYPE html>",
        "<html><head>",
        f"<title>Index of {html.escape(url_path)}</title>",
        "<style>",
        "body{font-family:monospace;padding:2rem}",
        "a{text-decoration:none}a:hover{text-decoration:underline}",
        ".e{padding:.2rem 0}.s{color:#666;margin-left:1rem}",
        "</style></head><body>",
        f"<h1>Index of {html.escape(url_path)}</h1><hr>",
    ]
    if url_path != "/":
        parent = os.path.dirname(url_path.rstrip("/")) or "/"
        lines.append(f'<div class="e"><a href="{parent}">../</a></div>')
    for entry in entries:
        if entry.startswith("."):
            continue
        full = os.path.join(dir_path, entry)
        display = html.escape(entry)
        href = os.path.join(url_path, entry)
        if os.path.isdir(full):
            display += "/"
            href += "/"
            sz = "-"
        else:
            sz = format_size(os.path.getsize(full))
        lines.append(f'<div class="e"><a href="{href}">{display}</a>'
                     f'<span class="s">{sz}</span></div>')
    lines.extend(["<hr>", "</body></html>"])
    return "\n".join(lines).encode("utf-8")


# ---------------------------------------------------------------------------
# Response senders
# ---------------------------------------------------------------------------

async def send_response(send, status: int, headers: list, body: bytes):
    headers.append([b"content-length", str(len(body)).encode()])
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body})


async def send_404(send):
    await send_response(send, 404,
                        [[b"content-type", b"text/html; charset=utf-8"]],
                        NOT_FOUND_BODY)


async def send_405(send):
    await send_response(send, 405,
                        [[b"content-type", b"text/plain"], [b"allow", b"GET, HEAD"]],
                        b"Method Not Allowed")


async def send_304(send, etag: str, mtime: float, cache_control: bytes):
    await send({
        "type": "http.response.start",
        "status": 304,
        "headers": [
            [b"etag", etag.encode()],
            [b"last-modified", format_mtime(mtime)],
            [b"cache-control", cache_control],
        ],
    })
    await send({"type": "http.response.body", "body": b""})


async def send_redirect(send, location: str):
    await send_response(send, 301,
                        [[b"location", location.encode()]],
                        b"")


async def send_416(send, file_size: int):
    await send_response(send, 416,
                        [[b"content-type", b"text/plain"],
                         [b"content-range", f"bytes */{file_size}".encode()]],
                        b"Range Not Satisfiable")


async def send_file_streamed(send, file_path: str, file_size: int,
                              status: int, headers: list,
                              offset: int = 0, length: int | None = None):
    """Stream file bytes from offset for length bytes."""
    if length is None:
        length = file_size - offset
    headers.append([b"content-length", str(length).encode()])
    await send({"type": "http.response.start", "status": status, "headers": headers})

    with open(file_path, "rb") as f:
        if offset:
            f.seek(offset)
        remaining = length
        while remaining > 0:
            to_read = min(CHUNK_SIZE, remaining)
            chunk = f.read(to_read)
            if not chunk:
                break
            remaining -= len(chunk)
            await send({
                "type": "http.response.body",
                "body": chunk,
                "more_body": remaining > 0,
            })
    # If the loop ended early (file shorter than expected), close the body.
    if remaining > 0:
        await send({"type": "http.response.body", "body": b"", "more_body": False})


async def send_file_gzipped(send, file_path: str, headers: list):
    """Compress the file with gzip and send the full response."""
    with open(file_path, "rb") as f:
        raw = f.read()
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", compresslevel=6) as gz:
        gz.write(raw)
    compressed = buf.getvalue()
    headers.extend([
        [b"content-encoding", b"gzip"],
        [b"vary", b"Accept-Encoding"],
    ])
    await send_response(send, 200, headers, compressed)


# ---------------------------------------------------------------------------
# Core serving logic
# ---------------------------------------------------------------------------

async def serve_static_file(scope, send, file_path: str, is_head: bool):
    """Serve a single file with caching, compression, and range support."""
    stat = os.stat(file_path)
    file_size = stat.st_size
    etag = compute_etag(stat)
    mtime = stat.st_mtime
    cc = cache_control_for(file_path)

    # -- 304 checks --------------------------------------------------------
    if_none_match = get_request_header(scope, b"if-none-match")
    if if_none_match is not None:
        tags = [t.strip() for t in if_none_match.decode().split(",")]
        if etag in tags or "*" in tags:
            await send_304(send, etag, mtime, cc)
            return

    if_modified_since = get_request_header(scope, b"if-modified-since")
    if if_modified_since is not None and if_none_match is None:
        since = parse_http_date(if_modified_since.decode())
        if since is not None and mtime <= since:
            await send_304(send, etag, mtime, cc)
            return

    # -- Common headers ----------------------------------------------------
    base_headers = [
        [b"etag", etag.encode()],
        [b"last-modified", format_mtime(mtime)],
        [b"cache-control", cc],
        [b"accept-ranges", b"bytes"],
        [b"content-type", content_type_header(file_path)],
    ]

    if is_head:
        base_headers.append([b"content-length", str(file_size).encode()])
        await send({"type": "http.response.start", "status": 200,
                     "headers": base_headers})
        await send({"type": "http.response.body", "body": b""})
        return

    # -- Range requests ----------------------------------------------------
    range_header = get_request_header(scope, b"range")
    if range_header is not None:
        ranges = parse_range_header(range_header.decode(), file_size)
        if ranges is None:
            await send_416(send, file_size)
            return
        start, end = ranges[0]
        length = end - start + 1
        range_headers = list(base_headers)
        range_headers.append(
            [b"content-range", f"bytes {start}-{end}/{file_size}".encode()]
        )
        await send_file_streamed(send, file_path, file_size, 206,
                                  range_headers, offset=start, length=length)
        return

    # -- Gzip compression --------------------------------------------------
    ct = guess_content_type(file_path)
    if (ct in COMPRESSIBLE_TYPES
            and file_size >= MIN_COMPRESS_SIZE
            and client_accepts_gzip(scope)):
        # Check for pre-compressed sibling.
        gz_path = file_path + ".gz"
        if (os.path.isfile(gz_path)
                and os.path.getmtime(gz_path) >= mtime):
            gz_size = os.path.getsize(gz_path)
            gz_headers = list(base_headers)
            gz_headers.extend([
                [b"content-encoding", b"gzip"],
                [b"vary", b"Accept-Encoding"],
            ])
            await send_file_streamed(send, gz_path, gz_size, 200, gz_headers)
        else:
            await send_file_gzipped(send, file_path, list(base_headers))
        return

    # -- Normal streaming response -----------------------------------------
    await send_file_streamed(send, file_path, file_size, 200, list(base_headers))


# ---------------------------------------------------------------------------
# Main ASGI application
# ---------------------------------------------------------------------------

async def static_app(scope, receive, send):
    """Core static file ASGI application."""
    if scope["type"] != "http":
        return

    method = scope.get("method", "GET")
    if method not in ("GET", "HEAD"):
        await send_405(send)
        return

    is_head = method == "HEAD"
    request_path = scope["path"]

    # -- Security: resolve and validate the path ---------------------------
    file_path = safe_file_path(STATIC_ROOT, request_path)
    if file_path is None or has_hidden_component(file_path, STATIC_ROOT):
        await send_404(send)
        return

    # -- Directory handling ------------------------------------------------
    if os.path.isdir(file_path):
        if not request_path.endswith("/"):
            prefix = scope.get("root_path", "")
            await send_redirect(send, prefix + request_path + "/")
            return
        index = os.path.join(file_path, "index.html")
        if os.path.isfile(index):
            await serve_static_file(scope, send, index, is_head)
            return
        if ENABLE_DIRECTORY_LISTING:
            body = build_directory_listing(file_path, request_path)
            await send_response(send, 200,
                                [[b"content-type", b"text/html; charset=utf-8"]],
                                body)
            return
        await send_404(send)
        return

    # -- File handling -----------------------------------------------------
    if os.path.isfile(file_path):
        await serve_static_file(scope, send, file_path, is_head)
        return

    # -- SPA fallback ------------------------------------------------------
    if ENABLE_SPA_FALLBACK:
        spa_index = os.path.join(STATIC_ROOT, "index.html")
        accept = get_request_header(scope, b"accept")
        if accept is not None and b"text/html" in accept and os.path.isfile(spa_index):
            await serve_static_file(scope, send, spa_index, is_head)
            return

    await send_404(send)


# ---------------------------------------------------------------------------
# Mounted wrapper
# ---------------------------------------------------------------------------

class MountedStaticFiles:
    """Mount the static file server at a URL prefix."""

    def __init__(self, prefix: str, root: str = STATIC_ROOT):
        self.prefix = prefix.rstrip("/")
        self.root = root

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return
        path = scope["path"]
        if path == self.prefix or path.startswith(self.prefix + "/"):
            inner_path = path[len(self.prefix):] or "/"
            inner_scope = dict(scope)
            inner_scope["path"] = inner_path
            inner_scope["root_path"] = scope.get("root_path", "") + self.prefix
            await static_app(inner_scope, receive, send)
        else:
            await send_404(send)


# ---------------------------------------------------------------------------
# Application entry point
# ---------------------------------------------------------------------------

if MOUNT_PREFIX:
    app = MountedStaticFiles(MOUNT_PREFIX)
else:
    app = static_app
```

### Running the server

```bash
# Serve ./static directory on port 8000.
STATIC_ROOT=./static uvicorn static_server:app

# Enable directory listing and SPA fallback, mounted at /static/.
STATIC_ROOT=./public \
  DIRECTORY_LISTING=1 \
  SPA_FALLBACK=1 \
  MOUNT_PREFIX=/static \
  uvicorn static_server:app --host 0.0.0.0 --port 8000
```

### Testing with curl

```bash
# Basic file request.
curl -i http://localhost:8000/style.css

# Conditional request (ETag).
ETAG=$(curl -si http://localhost:8000/style.css | grep -i etag | awk '{print $2}')
curl -i -H "If-None-Match: $ETAG" http://localhost:8000/style.css
# Expected: 304 Not Modified

# Range request (first 1024 bytes).
curl -i -H "Range: bytes=0-1023" http://localhost:8000/large-file.bin
# Expected: 206 Partial Content

# Gzip compression.
curl -i -H "Accept-Encoding: gzip" http://localhost:8000/app.js
# Expected: Content-Encoding: gzip

# Directory listing.
curl -i http://localhost:8000/images/
```

---

## Summary

| Feature                | Key Technique                                          |
|------------------------|--------------------------------------------------------|
| Basic serving          | `scope["path"]` to filesystem, read and send bytes     |
| Content-Type           | `mimetypes.guess_type()`                               |
| Streaming              | Multiple `http.response.body` events, `more_body=True` |
| Directory listing      | `os.listdir()` to HTML                                 |
| 404 handling           | Check `os.path.isfile()`, send status 404              |
| Path traversal defense | `os.path.realpath()` + prefix check                    |
| Hidden files           | Filter path components starting with `.`               |
| ETag caching           | MD5 of `mtime_ns + size`, compare `If-None-Match`      |
| Last-Modified          | `email.utils.formatdate()`, compare `If-Modified-Since` |
| Cache-Control          | Content-hash detection for immutable assets            |
| Range requests         | Parse `Range` header, seek + partial read, 206 status  |
| Gzip compression       | `gzip` module, check `Accept-Encoding`, set `Vary`     |
| SPA fallback           | Serve `index.html` when file not found + HTML accepted |
| Sub-app mounting       | Strip prefix from `scope["path"]`, adjust `root_path`  |

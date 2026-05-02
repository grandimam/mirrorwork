# Module 3: The HTTP Protocol — Complete Specification

## Overview

HTTP (Hypertext Transfer Protocol) is the language of the web. Every request your web server receives and every response it sends follows this protocol. This module is a deep dive into HTTP—not a surface-level overview, but a complete specification-level understanding.

You will read raw HTTP requests and responses, understand every header, and internalize the semantics of the protocol. By the end, you'll be ready to implement an HTTP parser from scratch.

---

## Learning Objectives

By the end of this module, you will be able to:

1. Trace the evolution of HTTP from 0.9 to 3
2. Parse HTTP request lines, headers, and bodies by hand
3. Construct valid HTTP responses with appropriate status codes
4. Explain the semantics of every common HTTP method
5. Understand content negotiation, caching, cookies, and authentication
6. Identify and handle HTTP edge cases (chunked encoding, keep-alive, pipelining)
7. Read and interpret relevant RFCs

---

## 3.1 HTTP History and Evolution

### HTTP/0.9 — The One-Liner (1991)

The original HTTP was trivial:

**Request:**
```
GET /page.html
```

**Response:**
```html
<html>
  <body>Hello World</body>
</html>
```

That's it. No headers. No status codes. Only GET. Only HTML. Connection closed after response.

### HTTP/1.0 — Headers and Status Codes (1996)

HTTP/1.0 (RFC 1945) added:
- Request headers
- Response status codes
- Content types beyond HTML
- HEAD and POST methods

**Request:**
```
GET /page.html HTTP/1.0
Host: www.example.com
User-Agent: Mozilla/5.0

```

**Response:**
```
HTTP/1.0 200 OK
Content-Type: text/html
Content-Length: 1234

<html>...</html>
```

**Limitation:** One request per connection. Open → Request → Response → Close. Repeated for every resource.

### HTTP/1.1 — Persistent Connections (1997)

HTTP/1.1 (RFC 2616, later RFC 7230-7235) is still the dominant version:

**Key additions:**
- **Persistent connections**: Connection stays open for multiple requests
- **Host header required**: Virtual hosting (multiple sites per IP)
- **Chunked transfer encoding**: Stream responses without knowing size upfront
- **Additional methods**: PUT, DELETE, OPTIONS, TRACE, CONNECT
- **Cache controls**: ETags, Cache-Control headers
- **Content negotiation**: Accept-* headers

**Request:**
```
GET /api/users HTTP/1.1
Host: api.example.com
Connection: keep-alive
Accept: application/json

```

### HTTP/2 — Binary Framing (2015)

HTTP/2 (RFC 7540) is a complete redesign of the wire format:

**Key changes:**
- **Binary protocol**: Not human-readable on the wire
- **Multiplexing**: Multiple requests/responses over single connection
- **Header compression**: HPACK algorithm
- **Server push**: Server can send resources before client requests
- **Stream prioritization**: Important resources first

```
┌─────────────────────────────────────────────────────────────┐
│                    Single TCP Connection                     │
├─────────────────────────────────────────────────────────────┤
│ Stream 1 │ Stream 3 │ Stream 5 │ Stream 7 │ Stream 9 │ ...  │
│ GET /    │ GET /css │ GET /js  │ GET /img │ GET /api │      │
│ ──────▶  │ ──────▶  │ ──────▶  │ ──────▶  │ ──────▶  │      │
│ ◀──────  │ ◀──────  │ ◀──────  │ ◀──────  │ ◀──────  │      │
└─────────────────────────────────────────────────────────────┘
```

HTTP/2 semantics (methods, status codes, headers) are the same as HTTP/1.1.

### HTTP/3 — QUIC (2022)

HTTP/3 (RFC 9114) replaces TCP with QUIC (over UDP):

**Why UDP?**
- TCP's head-of-line blocking: One lost packet blocks all streams
- QUIC: Each stream independent; lost packet only blocks that stream
- Built-in TLS 1.3: Faster connection establishment
- Connection migration: Survives IP changes (mobile networks)

```
HTTP/1.1, HTTP/2:          HTTP/3:
┌──────────────────┐       ┌──────────────────┐
│       HTTP       │       │       HTTP       │
├──────────────────┤       ├──────────────────┤
│       TLS        │       │       QUIC       │
├──────────────────┤       │   (includes TLS) │
│       TCP        │       ├──────────────────┤
├──────────────────┤       │       UDP        │
│       IP         │       ├──────────────────┤
└──────────────────┘       │       IP         │
                           └──────────────────┘
```

### Which Version Will You Implement?

This syllabus focuses on **HTTP/1.1** because:
1. It's text-based and human-readable
2. Understanding it is prerequisite to HTTP/2 and HTTP/3
3. Most concepts (methods, headers, semantics) carry forward
4. Many servers still serve HTTP/1.1

---

## 3.2 HTTP Request Anatomy

### Request Structure

```
┌─────────────────────────────────────────────────────────┐
│  Request Line                                           │
│  GET /api/users?page=1 HTTP/1.1                         │
├─────────────────────────────────────────────────────────┤
│  Headers                                                │
│  Host: api.example.com                                  │
│  User-Agent: Mozilla/5.0                                │
│  Accept: application/json                               │
│  Authorization: Bearer eyJhbGc...                       │
│  Content-Type: application/json                         │
│  Content-Length: 42                                     │
├─────────────────────────────────────────────────────────┤
│  Empty Line (CRLF)                                      │
│                                                         │
├─────────────────────────────────────────────────────────┤
│  Body (optional)                                        │
│  {"name": "John", "email": "john@example.com"}          │
└─────────────────────────────────────────────────────────┘
```

### The Request Line

```
METHOD SP REQUEST-URI SP HTTP-VERSION CRLF

GET /api/users?page=1&limit=10 HTTP/1.1\r\n
```

**Components:**
- **METHOD**: GET, POST, PUT, DELETE, etc.
- **REQUEST-URI**: Path + query string (not including scheme/host)
- **HTTP-VERSION**: HTTP/1.0 or HTTP/1.1
- **SP**: Space character (0x20)
- **CRLF**: Carriage Return + Line Feed (\r\n)

**URI Structure:**
```
/path/to/resource?query=string&another=value#fragment
│                 │                          │
│                 │                          └── Fragment (not sent to server)
│                 └── Query String
└── Path
```

Note: The fragment (#) is never sent to the server. It's handled client-side only.

### Header Format

```
Header-Name: Header-Value CRLF
Header-Name: Header-Value CRLF
...
CRLF  (empty line marks end of headers)
```

**Header rules:**
- Name is case-insensitive: `Content-Type` = `content-type` = `CONTENT-TYPE`
- Value may have leading/trailing whitespace (should be trimmed)
- Headers can span multiple lines (obsolete, but you may encounter it):
  ```
  X-Custom-Header: value
   continued on next line
  ```
- Order generally doesn't matter (with some exceptions)

### Common Request Headers

| Header | Purpose | Example |
|--------|---------|---------|
| `Host` | Required in HTTP/1.1. Target host. | `Host: www.example.com` |
| `User-Agent` | Client identification | `User-Agent: Mozilla/5.0...` |
| `Accept` | Acceptable response media types | `Accept: text/html, application/json` |
| `Accept-Language` | Preferred languages | `Accept-Language: en-US, en;q=0.9` |
| `Accept-Encoding` | Acceptable compression | `Accept-Encoding: gzip, deflate, br` |
| `Content-Type` | Media type of body | `Content-Type: application/json` |
| `Content-Length` | Size of body in bytes | `Content-Length: 348` |
| `Authorization` | Authentication credentials | `Authorization: Bearer token123` |
| `Cookie` | Cookies for this domain | `Cookie: session=abc123` |
| `Connection` | Connection management | `Connection: keep-alive` |
| `Cache-Control` | Caching directives | `Cache-Control: no-cache` |
| `If-None-Match` | Conditional GET (ETag) | `If-None-Match: "abc123"` |
| `If-Modified-Since` | Conditional GET (date) | `If-Modified-Since: Wed, 21 Oct 2015...` |

### Request Body

The body follows the empty line after headers. Its presence and format depend on:

1. **Content-Length header**: Body is exactly this many bytes
2. **Transfer-Encoding: chunked**: Body is chunked (see 3.2.2)
3. **Neither**: No body (GET, HEAD, DELETE typically)

**Example POST with body:**
```
POST /api/users HTTP/1.1
Host: api.example.com
Content-Type: application/json
Content-Length: 42

{"name": "John", "email": "john@test.com"}
```

---

## 3.3 HTTP Response Anatomy

### Response Structure

```
┌─────────────────────────────────────────────────────────┐
│  Status Line                                            │
│  HTTP/1.1 200 OK                                        │
├─────────────────────────────────────────────────────────┤
│  Headers                                                │
│  Content-Type: application/json                         │
│  Content-Length: 1234                                   │
│  Cache-Control: max-age=3600                            │
│  Set-Cookie: session=xyz789; HttpOnly                   │
├─────────────────────────────────────────────────────────┤
│  Empty Line (CRLF)                                      │
│                                                         │
├─────────────────────────────────────────────────────────┤
│  Body                                                   │
│  {"users": [...]}                                       │
└─────────────────────────────────────────────────────────┘
```

### The Status Line

```
HTTP-VERSION SP STATUS-CODE SP REASON-PHRASE CRLF

HTTP/1.1 200 OK\r\n
HTTP/1.1 404 Not Found\r\n
HTTP/1.1 500 Internal Server Error\r\n
```

**Components:**
- **HTTP-VERSION**: HTTP/1.0 or HTTP/1.1
- **STATUS-CODE**: 3-digit integer
- **REASON-PHRASE**: Human-readable (informational only, can be ignored)

### Status Code Categories

```
1xx — Informational
    Request received, continuing process

2xx — Success
    Request successfully received, understood, and accepted

3xx — Redirection
    Further action needed to complete request

4xx — Client Error
    Request contains bad syntax or cannot be fulfilled

5xx — Server Error
    Server failed to fulfill valid request
```

### Complete Status Code Reference

#### 1xx Informational

| Code | Name | Use |
|------|------|-----|
| 100 | Continue | Client should continue with request body |
| 101 | Switching Protocols | Server switching to protocol in Upgrade header (WebSocket) |
| 102 | Processing | WebDAV: request received, still processing |
| 103 | Early Hints | Preload resources while server prepares response |

#### 2xx Success

| Code | Name | Use |
|------|------|-----|
| 200 | OK | Standard success response |
| 201 | Created | Resource created (POST). Include Location header. |
| 202 | Accepted | Request accepted for processing (async) |
| 204 | No Content | Success but no body to return (DELETE) |
| 206 | Partial Content | Range request fulfilled |

#### 3xx Redirection

| Code | Name | Use |
|------|------|-----|
| 301 | Moved Permanently | Resource permanently at new URL. Cache. |
| 302 | Found | Temporary redirect (historical: was "Moved Temporarily") |
| 303 | See Other | Redirect to different resource (after POST) |
| 304 | Not Modified | Conditional GET: use cached version |
| 307 | Temporary Redirect | Like 302, but MUST NOT change method |
| 308 | Permanent Redirect | Like 301, but MUST NOT change method |

**301 vs 308 / 302 vs 307:**
- 301/302: Browsers may change POST to GET on redirect (historical behavior)
- 307/308: Method MUST be preserved

#### 4xx Client Errors

| Code | Name | Use |
|------|------|-----|
| 400 | Bad Request | Malformed request syntax |
| 401 | Unauthorized | Authentication required |
| 403 | Forbidden | Authenticated but not authorized |
| 404 | Not Found | Resource doesn't exist |
| 405 | Method Not Allowed | Method not supported for this resource |
| 406 | Not Acceptable | Cannot produce acceptable response (Accept headers) |
| 408 | Request Timeout | Client took too long |
| 409 | Conflict | Conflict with current state (concurrent edits) |
| 410 | Gone | Resource permanently removed (unlike 404) |
| 411 | Length Required | Content-Length header required |
| 413 | Payload Too Large | Request body too large |
| 414 | URI Too Long | Request URI too long |
| 415 | Unsupported Media Type | Content-Type not supported |
| 422 | Unprocessable Entity | Semantically invalid (validation failed) |
| 429 | Too Many Requests | Rate limited |
| 431 | Request Header Fields Too Large | Headers too big |

#### 5xx Server Errors

| Code | Name | Use |
|------|------|-----|
| 500 | Internal Server Error | Generic server error |
| 501 | Not Implemented | Method not implemented |
| 502 | Bad Gateway | Upstream server error (proxy) |
| 503 | Service Unavailable | Server overloaded or maintenance |
| 504 | Gateway Timeout | Upstream server timeout (proxy) |
| 505 | HTTP Version Not Supported | HTTP version not supported |

### Common Response Headers

| Header | Purpose | Example |
|--------|---------|---------|
| `Content-Type` | Media type of body | `Content-Type: application/json; charset=utf-8` |
| `Content-Length` | Size of body | `Content-Length: 1234` |
| `Content-Encoding` | Compression used | `Content-Encoding: gzip` |
| `Transfer-Encoding` | Transfer coding | `Transfer-Encoding: chunked` |
| `Cache-Control` | Caching directives | `Cache-Control: max-age=3600, public` |
| `ETag` | Entity tag for caching | `ETag: "abc123"` |
| `Last-Modified` | When resource changed | `Last-Modified: Wed, 21 Oct 2015 07:28:00 GMT` |
| `Location` | Redirect URL | `Location: https://example.com/new-path` |
| `Set-Cookie` | Set a cookie | `Set-Cookie: session=abc; HttpOnly; Secure` |
| `WWW-Authenticate` | Authentication challenge | `WWW-Authenticate: Bearer realm="api"` |
| `Access-Control-*` | CORS headers | `Access-Control-Allow-Origin: *` |

---

## 3.4 HTTP Methods — Semantics

### Method Properties

| Method | Safe | Idempotent | Has Body |
|--------|------|------------|----------|
| GET | Yes | Yes | No |
| HEAD | Yes | Yes | No |
| POST | No | No | Yes |
| PUT | No | Yes | Yes |
| PATCH | No | No | Yes |
| DELETE | No | Yes | No* |
| OPTIONS | Yes | Yes | No |
| TRACE | Yes | Yes | No |
| CONNECT | No | No | Yes |

**Safe**: Doesn't modify server state. Can be cached, prefetched.
**Idempotent**: Multiple identical requests = same result as single request.

### GET — Retrieve Resource

```
GET /api/users/123 HTTP/1.1
Host: api.example.com
Accept: application/json
```

- Retrieve representation of resource
- MUST be safe and idempotent
- Should never have side effects
- Response should be cacheable

### HEAD — Get Headers Only

```
HEAD /api/users/123 HTTP/1.1
Host: api.example.com
```

- Identical to GET but without response body
- Used to check if resource exists, get metadata
- Response headers should be identical to GET

### POST — Create or Process

```
POST /api/users HTTP/1.1
Host: api.example.com
Content-Type: application/json
Content-Length: 42

{"name": "John", "email": "john@test.com"}
```

- Create a new resource
- Submit data for processing
- NOT idempotent (multiple POSTs create multiple resources)
- Response often includes `Location` header with new resource URL

### PUT — Replace Resource

```
PUT /api/users/123 HTTP/1.1
Host: api.example.com
Content-Type: application/json
Content-Length: 42

{"name": "John Updated", "email": "john@test.com"}
```

- Replace entire resource at URL
- Idempotent: Same PUT multiple times = same result
- Create if doesn't exist (in some implementations)
- Client specifies the full resource state

### PATCH — Partial Update

```
PATCH /api/users/123 HTTP/1.1
Host: api.example.com
Content-Type: application/json-patch+json
Content-Length: 38

[{"op": "replace", "path": "/name", "value": "New Name"}]
```

- Partial modification of resource
- NOT necessarily idempotent
- Various patch formats: JSON Patch, JSON Merge Patch

### DELETE — Remove Resource

```
DELETE /api/users/123 HTTP/1.1
Host: api.example.com
Authorization: Bearer token123
```

- Remove the resource
- Idempotent: DELETE same resource multiple times = resource gone
- May return 200 (with body), 202 (accepted), or 204 (no content)

### OPTIONS — Get Capabilities

```
OPTIONS /api/users HTTP/1.1
Host: api.example.com
```

Response:
```
HTTP/1.1 200 OK
Allow: GET, POST, OPTIONS
Access-Control-Allow-Methods: GET, POST, PUT, DELETE
Access-Control-Allow-Headers: Content-Type, Authorization
```

- Describes communication options for target resource
- Used by CORS preflight requests
- `Allow` header lists supported methods

### TRACE — Echo Request (Rarely Used)

```
TRACE /path HTTP/1.1
Host: example.com
```

- Server echoes back the request
- Used for debugging proxies
- Often disabled for security (XST attacks)

### CONNECT — Establish Tunnel

```
CONNECT example.com:443 HTTP/1.1
Host: example.com:443
```

- Requests proxy to establish TCP tunnel
- Used for HTTPS through HTTP proxy
- After success, connection becomes transparent tunnel

---

## 3.5 Content Negotiation

Content negotiation allows client and server to agree on the best representation.

### Accept Header — Media Type

```
Accept: text/html, application/xhtml+xml, application/xml;q=0.9, */*;q=0.8
```

**Quality values (q):**
- Range: 0 to 1 (default is 1)
- Higher = more preferred
- `*/*` is wildcard

**Parsing order:**
1. `text/html` — q=1.0 (most preferred)
2. `application/xhtml+xml` — q=1.0
3. `application/xml` — q=0.9
4. `*/*` — q=0.8 (anything else)

### Accept-Language — Language Preference

```
Accept-Language: en-US, en;q=0.9, de;q=0.8
```

- Primary tag: language (en, de, fr)
- Subtag: region (US, GB, DE)

### Accept-Encoding — Compression

```
Accept-Encoding: gzip, deflate, br
```

Common encodings:
- `gzip` — Most widely supported
- `deflate` — Raw deflate
- `br` — Brotli (better compression, newer)
- `identity` — No encoding

### Accept-Charset (Obsolete)

```
Accept-Charset: utf-8, iso-8859-1;q=0.5
```

Modern practice: Always use UTF-8. This header is effectively obsolete.

### Server Response: Vary Header

```
Vary: Accept, Accept-Encoding, Accept-Language
```

Tells caches: "I returned different content based on these request headers. Cache separately."

### Content Negotiation in Practice

```
Request:
GET /api/data HTTP/1.1
Accept: application/json, text/xml;q=0.9

Response (server chooses JSON):
HTTP/1.1 200 OK
Content-Type: application/json
Vary: Accept

{"data": "value"}
```

---

## 3.6 Caching Mechanics

Caching is crucial for web performance. Understanding it is essential.

### Cache-Control Request Directives

```
Cache-Control: max-age=0
Cache-Control: no-cache
Cache-Control: no-store
Cache-Control: only-if-cached
```

| Directive | Meaning |
|-----------|---------|
| `max-age=N` | Accept cached response if age < N seconds |
| `max-stale=N` | Accept stale response up to N seconds old |
| `min-fresh=N` | Response must be fresh for at least N more seconds |
| `no-cache` | Revalidate with origin before using cached copy |
| `no-store` | Don't store this request/response |
| `only-if-cached` | Only return cached response, or 504 |

### Cache-Control Response Directives

```
Cache-Control: max-age=3600, public
Cache-Control: private, no-cache
Cache-Control: no-store
Cache-Control: must-revalidate
```

| Directive | Meaning |
|-----------|---------|
| `max-age=N` | Response fresh for N seconds |
| `s-maxage=N` | Override max-age for shared caches (CDN) |
| `public` | Any cache may store |
| `private` | Only browser cache, not CDN/proxy |
| `no-cache` | Cache but revalidate before use |
| `no-store` | Never cache |
| `must-revalidate` | Once stale, MUST revalidate |
| `immutable` | Never changes; don't revalidate |

### ETag Validation

Server provides entity tag:
```
HTTP/1.1 200 OK
ETag: "33a64df5"
Content-Type: application/json

{"data": "value"}
```

Client validates with conditional request:
```
GET /api/data HTTP/1.1
If-None-Match: "33a64df5"
```

Server responds:
```
HTTP/1.1 304 Not Modified
ETag: "33a64df5"
```

(No body — client uses cached version)

### Last-Modified Validation

Server provides last modified date:
```
HTTP/1.1 200 OK
Last-Modified: Wed, 21 Oct 2015 07:28:00 GMT
Content-Type: application/json

{"data": "value"}
```

Client validates:
```
GET /api/data HTTP/1.1
If-Modified-Since: Wed, 21 Oct 2015 07:28:00 GMT
```

Server responds with 304 (not modified) or 200 (new version).

### Cache Decision Flowchart

```
         Request arrives
               │
               ▼
      ┌────────────────┐
      │ In cache?      │──No──▶ Fetch from origin
      └────────┬───────┘                │
               │Yes                     │
               ▼                        ▼
      ┌────────────────┐        Store in cache
      │ Fresh?         │                │
      └────────┬───────┘                │
               │                        │
         Yes ◀─┴─▶ No                   │
          │         │                   │
          ▼         ▼                   │
      Return    Revalidate              │
      cached    with origin             │
               (If-None-Match/          │
                If-Modified-Since)      │
                    │                   │
              ┌─────┴─────┐             │
              │           │             │
          304 Not     200 OK            │
          Modified    (new)             │
              │           │             │
              ▼           ▼             │
          Return      Update ◀──────────┘
          cached      cache
```

---

## 3.7 Cookies and State Management

HTTP is stateless. Cookies add state.

### Set-Cookie Header (Response)

```
Set-Cookie: session_id=abc123; Path=/; HttpOnly; Secure; SameSite=Strict
Set-Cookie: preferences=dark_mode; Max-Age=31536000; Path=/
```

### Cookie Attributes

| Attribute | Purpose |
|-----------|---------|
| `Expires=date` | Absolute expiration (HTTP date format) |
| `Max-Age=seconds` | Relative expiration (takes precedence over Expires) |
| `Domain=domain` | Which hosts receive the cookie |
| `Path=/path` | URL path that must exist for cookie to be sent |
| `Secure` | Only send over HTTPS |
| `HttpOnly` | Not accessible via JavaScript (XSS protection) |
| `SameSite=Strict` | Only send with same-site requests (CSRF protection) |
| `SameSite=Lax` | Send with same-site + top-level navigation |
| `SameSite=None` | Send with cross-site requests (requires Secure) |

### Cookie Header (Request)

```
Cookie: session_id=abc123; preferences=dark_mode; tracking_id=xyz789
```

All cookies for the domain sent as semicolon-separated pairs.

### Cookie Security Considerations

1. **HttpOnly**: Prevents JavaScript access → mitigates XSS
2. **Secure**: HTTPS only → prevents sniffing
3. **SameSite**: Restricts cross-site sending → mitigates CSRF
4. **Short expiration**: Session cookies (no Max-Age) cleared on browser close
5. **Minimal scope**: Use specific Path and Domain

---

## 3.8 Authentication Schemes

### Basic Authentication

```
Authorization: Basic dXNlcm5hbWU6cGFzc3dvcmQ=
```

The value is base64(username:password). **NOT ENCRYPTED.** Only use over HTTPS.

**Challenge:**
```
HTTP/1.1 401 Unauthorized
WWW-Authenticate: Basic realm="Access to site"
```

### Bearer Token Authentication

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

Common with JWTs and OAuth 2.0. Token format is opaque to HTTP.

**Challenge:**
```
HTTP/1.1 401 Unauthorized
WWW-Authenticate: Bearer realm="api", error="invalid_token"
```

### Digest Authentication (Rarely Used)

More secure than Basic (uses MD5 hash), but complex. Superseded by TLS + Basic or Bearer.

### Custom Authentication

Many APIs use custom headers:
```
X-API-Key: your-api-key-here
X-Auth-Token: your-token-here
```

Not part of HTTP spec, but widely used.

---

## 3.9 Transfer Encoding: Chunked

When you don't know the response size upfront:

```
HTTP/1.1 200 OK
Content-Type: text/plain
Transfer-Encoding: chunked

7\r\n
Hello, \r\n
6\r\n
World!\r\n
0\r\n
\r\n
```

### Chunk Format

```
chunk-size (hex) CRLF
chunk-data CRLF
...
0 CRLF
CRLF
```

### Parsing Chunked Encoding

```python
def read_chunked_body(sock):
    body = b''
    while True:
        # Read chunk size line
        size_line = read_line(sock)
        chunk_size = int(size_line.strip(), 16)

        if chunk_size == 0:
            read_line(sock)  # Final CRLF
            break

        # Read chunk data
        chunk_data = read_exactly(sock, chunk_size)
        body += chunk_data
        read_line(sock)  # CRLF after chunk

    return body
```

### Trailer Headers

Chunked encoding can include trailing headers after the final chunk:

```
HTTP/1.1 200 OK
Transfer-Encoding: chunked
Trailer: Content-MD5

7\r\n
Hello, \r\n
6\r\n
World!\r\n
0\r\n
Content-MD5: Q2hlY2sgSW50ZWdyaXR5IQ==\r\n
\r\n
```

---

## 3.10 Connection Management

### Keep-Alive (HTTP/1.1 Default)

```
Connection: keep-alive
Keep-Alive: timeout=5, max=1000
```

In HTTP/1.1, connections are persistent by default. Close explicitly with:

```
Connection: close
```

### Pipelining

Client can send multiple requests without waiting for responses:

```
Client                                Server
   │                                     │
   │──── GET /a ────────────────────────▶│
   │──── GET /b ────────────────────────▶│
   │──── GET /c ────────────────────────▶│
   │                                     │
   │◀─── Response /a ────────────────────│
   │◀─── Response /b ────────────────────│
   │◀─── Response /c ────────────────────│
```

**Head-of-line blocking**: Responses must be sent in order. Slow /a blocks /b and /c.

Pipelining is rarely used in practice (HTTP/2 solves this better).

---

## 3.11 Lab: Build an HTTP Protocol Parser

### The Goal

Write a Python function that parses raw HTTP request bytes into a structured object.

### Starter Code

```python
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class HttpRequest:
    method: str
    path: str
    query_string: str
    http_version: str
    headers: Dict[str, str]
    body: bytes


class HttpParseError(Exception):
    pass


def parse_request(data: bytes) -> HttpRequest:
    """
    Parse raw HTTP request bytes into an HttpRequest object.

    Raises HttpParseError on invalid input.
    """
    # TODO: Implement this
    pass
```

### Requirements

1. Parse the request line (method, path, query string, HTTP version)
2. Parse all headers (handle case-insensitivity)
3. Extract body based on Content-Length
4. Handle missing or malformed components gracefully
5. Return structured HttpRequest object

### Test Cases

```python
def test_simple_get():
    raw = b"GET /path HTTP/1.1\r\nHost: example.com\r\n\r\n"
    req = parse_request(raw)
    assert req.method == "GET"
    assert req.path == "/path"
    assert req.headers["host"] == "example.com"

def test_post_with_body():
    raw = (
        b"POST /api/users HTTP/1.1\r\n"
        b"Host: example.com\r\n"
        b"Content-Type: application/json\r\n"
        b"Content-Length: 13\r\n"
        b"\r\n"
        b'{"name":"Jo"}'
    )
    req = parse_request(raw)
    assert req.method == "POST"
    assert req.body == b'{"name":"Jo"}'

def test_query_string():
    raw = b"GET /search?q=hello&page=1 HTTP/1.1\r\nHost: example.com\r\n\r\n"
    req = parse_request(raw)
    assert req.path == "/search"
    assert req.query_string == "q=hello&page=1"
```

---

## Exercises

### Exercise 3.1: Manual HTTP Conversation

Using only `nc` (netcat), have a complete HTTP conversation:

1. Connect to httpbin.org port 80
2. Send a valid HTTP/1.1 GET request
3. Observe and document the response headers
4. Try POST with a JSON body

### Exercise 3.2: Header Case Sensitivity

Write a test that proves HTTP header names are case-insensitive:

1. Send requests with differently-cased header names
2. Verify server treats them the same
3. Test with your own server

### Exercise 3.3: Chunked Encoding Parser

Implement a chunked encoding decoder:

```python
def decode_chunked(data: bytes) -> bytes:
    """Decode chunked transfer encoding."""
    pass
```

Test with:
```python
chunked = b"5\r\nHello\r\n6\r\n World\r\n0\r\n\r\n"
assert decode_chunked(chunked) == b"Hello World"
```

### Exercise 3.4: Cache Headers

For a given resource, design the appropriate caching strategy:

1. A static JavaScript file that never changes
2. A user's profile page
3. A real-time stock price
4. A blog post that might be edited

Write the Cache-Control and related headers for each.

### Exercise 3.5: Content Negotiation

Implement server-side content negotiation:

```python
def negotiate_content_type(accept_header: str, available: list) -> str:
    """
    Given an Accept header and list of available types,
    return the best match or None.
    """
    pass

# Test
assert negotiate_content_type(
    "application/json, text/html;q=0.9",
    ["text/html", "application/json"]
) == "application/json"
```

### Exercise 3.6: Cookie Parser

Implement a Cookie header parser:

```python
def parse_cookies(cookie_header: str) -> dict:
    """Parse Cookie header into dict."""
    pass

assert parse_cookies("session=abc; user=john") == {"session": "abc", "user": "john"}
```

---

## Deep Dive Questions

1. **Why is the Host header required in HTTP/1.1 but not HTTP/1.0?**

2. **What's the difference between 301 and 308 redirects? When would the distinction matter?**

3. **Why does HTTP/2 use binary framing instead of text?**

4. **How does HTTP/3 solve head-of-line blocking that HTTP/2 still suffers from?**

5. **Why might a server send both Content-Length and Transfer-Encoding: chunked? Which takes precedence?**

6. **What security vulnerability does the SameSite cookie attribute prevent?**

---

## Resources

### RFCs (Read These)

- [RFC 7230 - HTTP/1.1 Message Syntax and Routing](https://tools.ietf.org/html/rfc7230)
- [RFC 7231 - HTTP/1.1 Semantics and Content](https://tools.ietf.org/html/rfc7231)
- [RFC 7232 - HTTP/1.1 Conditional Requests](https://tools.ietf.org/html/rfc7232)
- [RFC 7233 - HTTP/1.1 Range Requests](https://tools.ietf.org/html/rfc7233)
- [RFC 7234 - HTTP/1.1 Caching](https://tools.ietf.org/html/rfc7234)
- [RFC 7235 - HTTP/1.1 Authentication](https://tools.ietf.org/html/rfc7235)
- [RFC 7540 - HTTP/2](https://tools.ietf.org/html/rfc7540)
- [RFC 9114 - HTTP/3](https://tools.ietf.org/html/rfc9114)
- [RFC 6265 - HTTP Cookies](https://tools.ietf.org/html/rfc6265)

### Tools

- [httpbin.org](https://httpbin.org) — HTTP testing service
- [curl](https://curl.se/) — Command-line HTTP client
- [Postman](https://www.postman.com/) — GUI HTTP client
- [Wireshark](https://www.wireshark.org/) — See HTTP on the wire

### Books

- "HTTP: The Definitive Guide" by David Gourley — Comprehensive reference
- "High Performance Browser Networking" by Ilya Grigorik — Free online

---

## Summary

You now have a complete understanding of HTTP:

1. **Evolution**: 0.9 → 1.0 → 1.1 → 2 → 3 (each solving previous limitations)
2. **Request structure**: Request line, headers, body
3. **Response structure**: Status line, headers, body
4. **Status codes**: Informational, Success, Redirection, Client Error, Server Error
5. **Methods**: GET, POST, PUT, DELETE (and their semantics)
6. **Content negotiation**: Accept headers and quality values
7. **Caching**: Cache-Control, ETag, Last-Modified, 304 responses
8. **Cookies**: Stateful sessions in a stateless protocol
9. **Authentication**: Basic, Bearer, and custom schemes
10. **Transfer encoding**: Chunked for streaming responses

You're now ready to implement a real HTTP server. In the next module, you'll combine sockets and HTTP knowledge to build your first working web server.

---

## Next Module

**[Module 4: Your First HTTP Server →](./MODULE_04_FIRST_HTTP_SERVER.md)**

We'll build a complete HTTP/1.1 server from scratch, implementing the parser and request/response cycle.

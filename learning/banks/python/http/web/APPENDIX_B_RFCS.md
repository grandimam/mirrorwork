# Appendix B: RFC Quick Reference

## Overview

This appendix provides quick reference to the most important RFCs for web server development. Understanding these specifications is essential for building compliant servers.

---

## B.1 Core HTTP RFCs

### RFC 9110 - HTTP Semantics

**Key Sections:**

| Section | Topic | Importance |
|---------|-------|------------|
| 4 | Identifiers (URIs) | How to parse URLs |
| 5 | Fields (Headers) | Header syntax and handling |
| 6 | Message Abstraction | Request/response structure |
| 8 | Status Codes | All status code definitions |
| 9 | Methods | GET, POST, PUT, DELETE, etc. |
| 10 | Message Context | Host, Date, Location headers |
| 12 | Content Negotiation | Accept headers handling |

**Essential Status Codes:**

```
1xx - Informational
  100 Continue           - Expect handling
  101 Switching Protocols - WebSocket upgrade

2xx - Success
  200 OK                 - Standard success
  201 Created            - Resource created
  204 No Content         - Success, no body

3xx - Redirection
  301 Moved Permanently  - Permanent redirect
  302 Found              - Temporary redirect
  304 Not Modified       - Caching response

4xx - Client Error
  400 Bad Request        - Malformed request
  401 Unauthorized       - Auth required
  403 Forbidden          - Auth failed
  404 Not Found          - Resource missing
  405 Method Not Allowed - Wrong method
  429 Too Many Requests  - Rate limited

5xx - Server Error
  500 Internal Error     - Server bug
  502 Bad Gateway        - Upstream error
  503 Service Unavailable - Overloaded
  504 Gateway Timeout    - Upstream timeout
```

### RFC 9111 - HTTP Caching

**Key Headers:**

```
Cache-Control: max-age=3600, public
Cache-Control: no-cache, no-store
Cache-Control: private, must-revalidate

ETag: "abc123"
If-None-Match: "abc123"

Last-Modified: Wed, 21 Oct 2023 07:28:00 GMT
If-Modified-Since: Wed, 21 Oct 2023 07:28:00 GMT

Age: 60
Expires: Wed, 21 Oct 2024 07:28:00 GMT
Vary: Accept-Encoding, Accept-Language
```

**Cache-Control Directives:**

| Directive | Description |
|-----------|-------------|
| max-age=N | Cache for N seconds |
| s-maxage=N | Shared cache max age |
| no-cache | Must revalidate |
| no-store | Never cache |
| public | Cacheable by any cache |
| private | Only browser cache |
| must-revalidate | Must check on stale |
| immutable | Never changes |

### RFC 9112 - HTTP/1.1

**Message Format:**

```
Request:
  GET /path HTTP/1.1\r\n
  Host: example.com\r\n
  Header-Name: Header-Value\r\n
  \r\n
  [body]

Response:
  HTTP/1.1 200 OK\r\n
  Content-Type: text/html\r\n
  Content-Length: 1234\r\n
  \r\n
  [body]
```

**Key Requirements:**

1. Host header is REQUIRED for HTTP/1.1
2. Persistent connections are default
3. Connection: close to disable keep-alive
4. Transfer-Encoding: chunked for streaming
5. Content-Length for fixed-size bodies

**Chunked Encoding:**

```
HTTP/1.1 200 OK
Transfer-Encoding: chunked

7\r\n
Mozilla\r\n
9\r\n
Developer\r\n
7\r\n
Network\r\n
0\r\n
\r\n
```

---

## B.2 Security RFCs

### RFC 6749 - OAuth 2.0

**Grant Types:**

```
1. Authorization Code (for server apps)
   /authorize?response_type=code&client_id=...
   /token with grant_type=authorization_code

2. Implicit (for SPA - deprecated)
   /authorize?response_type=token&client_id=...

3. Client Credentials (for machine-to-machine)
   /token with grant_type=client_credentials

4. Resource Owner Password (legacy)
   /token with grant_type=password
```

### RFC 7519 - JWT

**Structure:**

```
header.payload.signature

Header:
{
  "alg": "HS256",
  "typ": "JWT"
}

Payload:
{
  "sub": "user123",
  "iat": 1516239022,
  "exp": 1516242622,
  "iss": "auth.example.com"
}

Signature:
HMACSHA256(
  base64UrlEncode(header) + "." +
  base64UrlEncode(payload),
  secret
)
```

**Registered Claims:**

| Claim | Description |
|-------|-------------|
| iss | Issuer |
| sub | Subject (user ID) |
| aud | Audience |
| exp | Expiration time |
| nbf | Not before |
| iat | Issued at |
| jti | JWT ID (unique) |

### RFC 6265 - HTTP Cookies

**Set-Cookie Header:**

```
Set-Cookie: session=abc123; Path=/; HttpOnly; Secure; SameSite=Strict
Set-Cookie: prefs=dark; Max-Age=31536000; Path=/
```

**Attributes:**

| Attribute | Description |
|-----------|-------------|
| Expires | Absolute expiration date |
| Max-Age | Seconds until expiration |
| Domain | Cookie domain scope |
| Path | Cookie path scope |
| Secure | HTTPS only |
| HttpOnly | No JavaScript access |
| SameSite | CSRF protection |

**SameSite Values:**

- `Strict`: Only same-site requests
- `Lax`: GET from other sites allowed
- `None`: Cross-site allowed (requires Secure)

---

## B.3 WebSocket RFC

### RFC 6455 - WebSocket Protocol

**Opening Handshake:**

```
Client:
GET /chat HTTP/1.1
Host: server.example.com
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==
Sec-WebSocket-Version: 13

Server:
HTTP/1.1 101 Switching Protocols
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=
```

**Key Calculation:**

```python
import hashlib
import base64

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

def accept_key(client_key):
    combined = client_key + GUID
    sha1 = hashlib.sha1(combined.encode()).digest()
    return base64.b64encode(sha1).decode()
```

**Frame Format:**

```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-------+-+-------------+-------------------------------+
|F|R|R|R| opcode|M| Payload len |    Extended payload length    |
|I|S|S|S|  (4)  |A|     (7)     |             (16/64)           |
|N|V|V|V|       |S|             |   (if payload len==126/127)   |
+-+-+-+-+-------+-+-------------+-------------------------------+
```

**Opcodes:**

| Code | Type |
|------|------|
| 0x0 | Continuation |
| 0x1 | Text |
| 0x2 | Binary |
| 0x8 | Close |
| 0x9 | Ping |
| 0xA | Pong |

---

## B.4 Content Types

### RFC 7231 - Content Negotiation

**Accept Header:**

```
Accept: text/html, application/xhtml+xml, application/xml;q=0.9, */*;q=0.8
Accept-Language: en-US, en;q=0.9, fr;q=0.8
Accept-Encoding: gzip, deflate, br
Accept-Charset: utf-8, iso-8859-1;q=0.5
```

**Quality Values:**

```
text/html           - q=1.0 (default)
application/xml;q=0.9
*/*;q=0.8
```

### RFC 7578 - Multipart Form Data

**Format:**

```
POST /upload HTTP/1.1
Content-Type: multipart/form-data; boundary=----WebKitFormBoundary

------WebKitFormBoundary
Content-Disposition: form-data; name="field1"

value1
------WebKitFormBoundary
Content-Disposition: form-data; name="file"; filename="test.txt"
Content-Type: text/plain

file contents here
------WebKitFormBoundary--
```

---

## B.5 CORS

### Fetch Standard (CORS)

**Simple Requests:**

- Methods: GET, HEAD, POST
- Headers: Accept, Accept-Language, Content-Language, Content-Type (limited)
- Content-Type: application/x-www-form-urlencoded, multipart/form-data, text/plain

**Preflight Request:**

```
OPTIONS /api/data HTTP/1.1
Origin: https://example.com
Access-Control-Request-Method: POST
Access-Control-Request-Headers: Content-Type, Authorization

HTTP/1.1 204 No Content
Access-Control-Allow-Origin: https://example.com
Access-Control-Allow-Methods: POST, GET, OPTIONS
Access-Control-Allow-Headers: Content-Type, Authorization
Access-Control-Max-Age: 86400
```

**Response Headers:**

```
Access-Control-Allow-Origin: https://example.com
Access-Control-Allow-Credentials: true
Access-Control-Expose-Headers: X-Custom-Header
Access-Control-Max-Age: 86400
```

---

## B.6 Compression

### RFC 7932 - Brotli

**Accept-Encoding:**

```
Accept-Encoding: gzip, deflate, br
```

**Content-Encoding:**

```
Content-Encoding: br
Content-Encoding: gzip
Content-Encoding: deflate
```

**Compression Comparison:**

| Format | Ratio | Speed | Browser Support |
|--------|-------|-------|-----------------|
| gzip | Good | Fast | Universal |
| deflate | Good | Fast | Universal |
| br (Brotli) | Better | Slower | Modern |
| zstd | Best | Fast | Limited |

---

## B.7 Quick Reference Table

| Topic | RFC | Key Sections |
|-------|-----|--------------|
| HTTP Semantics | 9110 | Methods, Status Codes |
| HTTP Caching | 9111 | Cache-Control |
| HTTP/1.1 | 9112 | Message Format |
| HTTP/2 | 9113 | Streams, HPACK |
| HTTP/3 | 9114 | QUIC, QPACK |
| URIs | 3986 | URL Parsing |
| Cookies | 6265 | Set-Cookie |
| OAuth 2.0 | 6749 | Grant Types |
| JWT | 7519 | Token Format |
| WebSocket | 6455 | Handshake, Frames |
| TLS 1.3 | 8446 | Handshake |
| CORS | Fetch Spec | Preflight |
| Multipart | 7578 | Form Uploads |
| Brotli | 7932 | Compression |

---

## Summary

Key RFCs to study:

1. **RFC 9110-9114**: HTTP core specifications
2. **RFC 6455**: WebSocket protocol
3. **RFC 6265**: Cookie handling
4. **RFC 7519**: JWT tokens
5. **RFC 6749**: OAuth 2.0

Read the actual RFCs for authoritative information. This appendix provides quick reference only.

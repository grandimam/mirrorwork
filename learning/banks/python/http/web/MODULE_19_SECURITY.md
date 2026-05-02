# Module 19: Security Hardening

## Overview

Web servers are prime targets for attacks. This module covers security fundamentals, common vulnerabilities (OWASP Top 10), secure coding practices, and hardening techniques. Security is not a feature—it's a requirement.

---

## Learning Objectives

By the end of this module, you will be able to:

1. Identify and prevent common web vulnerabilities
2. Implement secure input validation and output encoding
3. Configure TLS/SSL properly
4. Implement authentication and authorization
5. Apply defense-in-depth principles

---

## 19.1 Security Principles

### Defense in Depth

```
┌─────────────────────────────────────────────────────────────┐
│                      Network Layer                          │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                    Firewall                            │  │
│  │  ┌─────────────────────────────────────────────────┐  │  │
│  │  │               Rate Limiting                      │  │  │
│  │  │  ┌───────────────────────────────────────────┐  │  │  │
│  │  │  │              TLS/SSL                       │  │  │  │
│  │  │  │  ┌─────────────────────────────────────┐  │  │  │  │
│  │  │  │  │        Input Validation              │  │  │  │  │
│  │  │  │  │  ┌───────────────────────────────┐  │  │  │  │  │
│  │  │  │  │  │    Authentication/Authz       │  │  │  │  │  │
│  │  │  │  │  │  ┌─────────────────────────┐  │  │  │  │  │  │
│  │  │  │  │  │  │    Application Code     │  │  │  │  │  │  │
│  │  │  │  │  │  │  ┌───────────────────┐  │  │  │  │  │  │  │
│  │  │  │  │  │  │  │      Data         │  │  │  │  │  │  │  │
│  │  │  │  │  │  │  └───────────────────┘  │  │  │  │  │  │  │
│  │  │  │  │  │  └─────────────────────────┘  │  │  │  │  │  │
│  │  │  │  │  └───────────────────────────────┘  │  │  │  │  │
│  │  │  │  └─────────────────────────────────────┘  │  │  │  │
│  │  │  └───────────────────────────────────────────┘  │  │  │
│  │  └─────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Security Principles

1. **Least Privilege**: Grant minimum necessary permissions
2. **Fail Secure**: Deny access on errors
3. **Defense in Depth**: Multiple layers of security
4. **Trust No Input**: Validate everything
5. **Secure by Default**: Safe configuration out of the box

---

## 19.2 Input Validation

### Never Trust User Input

```python
import re
from typing import Optional
from dataclasses import dataclass


class ValidationError(Exception):
    """Input validation failed."""
    pass


@dataclass
class Validator:
    """Input validation utilities."""

    @staticmethod
    def string(value: str, min_len: int = 0, max_len: int = 10000,
               pattern: Optional[str] = None) -> str:
        """Validate string input."""
        if not isinstance(value, str):
            raise ValidationError("Expected string")

        if len(value) < min_len:
            raise ValidationError(f"Too short (min {min_len})")

        if len(value) > max_len:
            raise ValidationError(f"Too long (max {max_len})")

        if pattern and not re.match(pattern, value):
            raise ValidationError("Invalid format")

        return value

    @staticmethod
    def integer(value, min_val: Optional[int] = None,
                max_val: Optional[int] = None) -> int:
        """Validate integer input."""
        try:
            num = int(value)
        except (TypeError, ValueError):
            raise ValidationError("Expected integer")

        if min_val is not None and num < min_val:
            raise ValidationError(f"Too small (min {min_val})")

        if max_val is not None and num > max_val:
            raise ValidationError(f"Too large (max {max_val})")

        return num

    @staticmethod
    def email(value: str) -> str:
        """Validate email address."""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, value):
            raise ValidationError("Invalid email")
        return value.lower()

    @staticmethod
    def uuid(value: str) -> str:
        """Validate UUID format."""
        pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        if not re.match(pattern, value.lower()):
            raise ValidationError("Invalid UUID")
        return value.lower()

    @staticmethod
    def path(value: str) -> str:
        """Validate and sanitize file path."""
        # Prevent path traversal
        if '..' in value or value.startswith('/'):
            raise ValidationError("Invalid path")

        # Only allow safe characters
        if not re.match(r'^[a-zA-Z0-9_\-./]+$', value):
            raise ValidationError("Invalid path characters")

        return value


# Usage
def handle_user_create(data: dict):
    try:
        username = Validator.string(
            data.get('username', ''),
            min_len=3, max_len=50,
            pattern=r'^[a-zA-Z0-9_]+$'
        )
        email = Validator.email(data.get('email', ''))
        age = Validator.integer(data.get('age'), min_val=0, max_val=150)

        return create_user(username, email, age)

    except ValidationError as e:
        return Response.json({'error': str(e)}, status=400)
```

### Request Size Limits

```python
class RequestLimiter:
    """Limit request sizes to prevent DoS."""

    def __init__(self,
                 max_body_size: int = 10 * 1024 * 1024,  # 10 MB
                 max_header_size: int = 8 * 1024,  # 8 KB
                 max_headers: int = 100):
        self.max_body_size = max_body_size
        self.max_header_size = max_header_size
        self.max_headers = max_headers

    async def validate_request(self, request):
        """Validate request limits."""
        # Check header count
        if len(request.headers) > self.max_headers:
            raise SecurityError("Too many headers")

        # Check header sizes
        for name, value in request.headers.items():
            if len(name) + len(value) > self.max_header_size:
                raise SecurityError("Header too large")

        # Check content length
        content_length = request.headers.get('content-length')
        if content_length:
            if int(content_length) > self.max_body_size:
                raise SecurityError("Request body too large")

        return True


# Middleware
class SizeLimitMiddleware:
    def __init__(self, app, max_size: int = 10_000_000):
        self.app = app
        self.max_size = max_size

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        # Check content-length header
        for name, value in scope.get('headers', []):
            if name == b'content-length':
                if int(value) > self.max_size:
                    await send({
                        'type': 'http.response.start',
                        'status': 413,
                        'headers': [(b'content-type', b'text/plain')],
                    })
                    await send({
                        'type': 'http.response.body',
                        'body': b'Request Entity Too Large',
                    })
                    return

        await self.app(scope, receive, send)
```

---

## 19.3 Output Encoding

### Prevent XSS

```python
import html
from typing import Any


def escape_html(value: str) -> str:
    """Escape HTML special characters."""
    return html.escape(value, quote=True)


def escape_js(value: str) -> str:
    """Escape for JavaScript context."""
    replacements = {
        '\\': '\\\\',
        "'": "\\'",
        '"': '\\"',
        '\n': '\\n',
        '\r': '\\r',
        '<': '\\u003c',
        '>': '\\u003e',
        '&': '\\u0026',
    }
    for char, replacement in replacements.items():
        value = value.replace(char, replacement)
    return value


def escape_url(value: str) -> str:
    """Escape for URL context."""
    from urllib.parse import quote
    return quote(value, safe='')


class SafeHTML:
    """Wrapper for pre-escaped HTML."""

    def __init__(self, value: str):
        self._value = value

    def __str__(self):
        return self._value


def render_template(template: str, context: dict) -> str:
    """Simple template with auto-escaping."""
    result = template

    for key, value in context.items():
        placeholder = f'{{{{{key}}}}}'  # {{key}}

        if isinstance(value, SafeHTML):
            escaped = str(value)
        else:
            escaped = escape_html(str(value))

        result = result.replace(placeholder, escaped)

    return result


# Usage
template = """
<html>
<body>
    <h1>Hello, {{username}}!</h1>
    <p>{{message}}</p>
</body>
</html>
"""

# Safe: Auto-escaped
html = render_template(template, {
    'username': '<script>alert("xss")</script>',
    'message': 'Welcome!'
})
# Output: <h1>Hello, &lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;!</h1>
```

### Content Security Policy

```python
class CSPMiddleware:
    """Add Content-Security-Policy header."""

    def __init__(self, app, policy: dict = None):
        self.app = app
        self.policy = policy or {
            'default-src': ["'self'"],
            'script-src': ["'self'"],
            'style-src': ["'self'", "'unsafe-inline'"],
            'img-src': ["'self'", 'data:', 'https:'],
            'font-src': ["'self'"],
            'connect-src': ["'self'"],
            'frame-ancestors': ["'none'"],
            'base-uri': ["'self'"],
            'form-action': ["'self'"],
        }

    def build_policy(self) -> str:
        parts = []
        for directive, sources in self.policy.items():
            sources_str = ' '.join(sources)
            parts.append(f"{directive} {sources_str}")
        return '; '.join(parts)

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        async def send_wrapper(message):
            if message['type'] == 'http.response.start':
                headers = list(message.get('headers', []))
                headers.append((
                    b'content-security-policy',
                    self.build_policy().encode()
                ))
                message = {**message, 'headers': headers}
            await send(message)

        await self.app(scope, receive, send_wrapper)
```

---

## 19.4 SQL Injection Prevention

### Parameterized Queries

```python
import asyncpg
from typing import Any, List


class SecureDatabase:
    """Database wrapper with parameterized queries only."""

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def fetch_one(self, query: str, *args) -> dict:
        """Fetch single row with parameters."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, *args)
            return dict(row) if row else None

    async def fetch_all(self, query: str, *args) -> List[dict]:
        """Fetch multiple rows with parameters."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *args)
            return [dict(row) for row in rows]

    async def execute(self, query: str, *args) -> str:
        """Execute query with parameters."""
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)


# DANGEROUS - SQL Injection vulnerable
async def get_user_bad(db, username: str):
    # Never do this!
    query = f"SELECT * FROM users WHERE username = '{username}'"
    return await db.fetch_one(query)


# SAFE - Parameterized query
async def get_user_good(db: SecureDatabase, username: str):
    query = "SELECT * FROM users WHERE username = $1"
    return await db.fetch_one(query, username)


# SAFE - For dynamic column names, use allowlist
ALLOWED_COLUMNS = {'username', 'email', 'created_at'}
ALLOWED_ORDER = {'ASC', 'DESC'}

async def search_users(db: SecureDatabase, column: str,
                       value: str, order: str = 'ASC'):
    if column not in ALLOWED_COLUMNS:
        raise ValueError("Invalid column")
    if order.upper() not in ALLOWED_ORDER:
        raise ValueError("Invalid order")

    query = f"SELECT * FROM users WHERE {column} = $1 ORDER BY created_at {order}"
    return await db.fetch_all(query, value)
```

---

## 19.5 Authentication

### Password Hashing

```python
import hashlib
import secrets
from typing import Tuple


class PasswordHasher:
    """Secure password hashing using PBKDF2."""

    def __init__(self, iterations: int = 600000):
        self.iterations = iterations
        self.algorithm = 'sha256'

    def hash(self, password: str) -> str:
        """Hash password with random salt."""
        salt = secrets.token_hex(32)
        dk = hashlib.pbkdf2_hmac(
            self.algorithm,
            password.encode(),
            salt.encode(),
            self.iterations
        )
        hash_hex = dk.hex()
        return f"{self.algorithm}${self.iterations}${salt}${hash_hex}"

    def verify(self, password: str, stored: str) -> bool:
        """Verify password against stored hash."""
        try:
            algorithm, iterations, salt, hash_hex = stored.split('$')
            dk = hashlib.pbkdf2_hmac(
                algorithm,
                password.encode(),
                salt.encode(),
                int(iterations)
            )
            return secrets.compare_digest(dk.hex(), hash_hex)
        except (ValueError, AttributeError):
            return False


# Better: Use argon2-cffi
try:
    from argon2 import PasswordHasher as Argon2Hasher
    from argon2.exceptions import VerifyMismatchError

    class SecurePasswordHasher:
        def __init__(self):
            self.hasher = Argon2Hasher()

        def hash(self, password: str) -> str:
            return self.hasher.hash(password)

        def verify(self, password: str, stored: str) -> bool:
            try:
                return self.hasher.verify(stored, password)
            except VerifyMismatchError:
                return False

except ImportError:
    SecurePasswordHasher = PasswordHasher


# Usage
hasher = SecurePasswordHasher()

def create_user(username: str, password: str):
    password_hash = hasher.hash(password)
    # Store password_hash in database
    return {'username': username, 'password_hash': password_hash}

def authenticate(username: str, password: str) -> bool:
    user = get_user_from_db(username)
    if not user:
        # Prevent timing attacks - hash anyway
        hasher.hash(password)
        return False
    return hasher.verify(password, user['password_hash'])
```

### JWT Tokens

```python
import jwt
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class JWTConfig:
    secret_key: str
    algorithm: str = 'HS256'
    access_token_expire: int = 900  # 15 minutes
    refresh_token_expire: int = 604800  # 7 days


class JWTHandler:
    """JWT token handling."""

    def __init__(self, config: JWTConfig):
        self.config = config

    def create_access_token(self, user_id: str,
                           claims: Dict[str, Any] = None) -> str:
        """Create access token."""
        payload = {
            'sub': user_id,
            'type': 'access',
            'iat': int(time.time()),
            'exp': int(time.time()) + self.config.access_token_expire,
            **(claims or {})
        }
        return jwt.encode(payload, self.config.secret_key,
                         algorithm=self.config.algorithm)

    def create_refresh_token(self, user_id: str) -> str:
        """Create refresh token."""
        payload = {
            'sub': user_id,
            'type': 'refresh',
            'iat': int(time.time()),
            'exp': int(time.time()) + self.config.refresh_token_expire,
        }
        return jwt.encode(payload, self.config.secret_key,
                         algorithm=self.config.algorithm)

    def verify_token(self, token: str,
                    token_type: str = 'access') -> Optional[Dict[str, Any]]:
        """Verify and decode token."""
        try:
            payload = jwt.decode(
                token,
                self.config.secret_key,
                algorithms=[self.config.algorithm]
            )

            if payload.get('type') != token_type:
                return None

            return payload

        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None


# Authentication middleware
class AuthMiddleware:
    """JWT authentication middleware."""

    def __init__(self, app, jwt_handler: JWTHandler,
                 exclude_paths: list = None):
        self.app = app
        self.jwt_handler = jwt_handler
        self.exclude_paths = exclude_paths or ['/login', '/register']

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        path = scope['path']
        if path in self.exclude_paths:
            return await self.app(scope, receive, send)

        # Get token from header
        token = None
        for name, value in scope.get('headers', []):
            if name == b'authorization':
                auth_header = value.decode()
                if auth_header.startswith('Bearer '):
                    token = auth_header[7:]
                break

        if not token:
            return await self._unauthorized(send)

        payload = self.jwt_handler.verify_token(token)
        if not payload:
            return await self._unauthorized(send)

        # Add user to scope
        scope['user'] = payload
        await self.app(scope, receive, send)

    async def _unauthorized(self, send):
        await send({
            'type': 'http.response.start',
            'status': 401,
            'headers': [(b'content-type', b'application/json')],
        })
        await send({
            'type': 'http.response.body',
            'body': b'{"error": "Unauthorized"}',
        })
```

---

## 19.6 TLS/SSL Configuration

### Server TLS Setup

```python
import ssl
import asyncio


def create_ssl_context(cert_file: str, key_file: str,
                       ca_file: str = None) -> ssl.SSLContext:
    """Create secure SSL context."""
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)

    # Minimum TLS 1.2
    context.minimum_version = ssl.TLSVersion.TLSv1_2

    # Load certificate and key
    context.load_cert_chain(cert_file, key_file)

    # Load CA for client verification (optional)
    if ca_file:
        context.load_verify_locations(ca_file)
        context.verify_mode = ssl.CERT_REQUIRED

    # Security settings
    context.options |= ssl.OP_NO_SSLv2
    context.options |= ssl.OP_NO_SSLv3
    context.options |= ssl.OP_NO_TLSv1
    context.options |= ssl.OP_NO_TLSv1_1

    # Cipher suites (strong ciphers only)
    context.set_ciphers(
        'ECDHE+AESGCM:DHE+AESGCM:ECDHE+CHACHA20:DHE+CHACHA20:'
        '!aNULL:!MD5:!DSS:!RC4:!3DES'
    )

    return context


async def run_https_server(app, host: str, port: int,
                          cert_file: str, key_file: str):
    """Run server with HTTPS."""
    ssl_context = create_ssl_context(cert_file, key_file)

    server = await asyncio.start_server(
        lambda r, w: handle_connection(app, r, w),
        host, port,
        ssl=ssl_context
    )

    print(f"HTTPS server on https://{host}:{port}")
    async with server:
        await server.serve_forever()


# HSTS header middleware
class HSTSMiddleware:
    """HTTP Strict Transport Security."""

    def __init__(self, app, max_age: int = 31536000,
                 include_subdomains: bool = True,
                 preload: bool = False):
        self.app = app
        self.header_value = f"max-age={max_age}"
        if include_subdomains:
            self.header_value += "; includeSubDomains"
        if preload:
            self.header_value += "; preload"

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        async def send_wrapper(message):
            if message['type'] == 'http.response.start':
                headers = list(message.get('headers', []))
                headers.append((
                    b'strict-transport-security',
                    self.header_value.encode()
                ))
                message = {**message, 'headers': headers}
            await send(message)

        await self.app(scope, receive, send_wrapper)
```

---

## 19.7 Rate Limiting

### Token Bucket Algorithm

```python
import time
from typing import Dict
from dataclasses import dataclass, field
import asyncio


@dataclass
class TokenBucket:
    """Token bucket rate limiter."""
    capacity: int
    refill_rate: float  # tokens per second
    tokens: float = field(init=False)
    last_update: float = field(init=False)

    def __post_init__(self):
        self.tokens = self.capacity
        self.last_update = time.monotonic()

    def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens. Returns True if allowed."""
        now = time.monotonic()
        elapsed = now - self.last_update
        self.last_update = now

        # Refill tokens
        self.tokens = min(
            self.capacity,
            self.tokens + elapsed * self.refill_rate
        )

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False


class RateLimiter:
    """IP-based rate limiter."""

    def __init__(self, requests_per_second: int = 10,
                 burst: int = 20):
        self.buckets: Dict[str, TokenBucket] = {}
        self.requests_per_second = requests_per_second
        self.burst = burst
        self._lock = asyncio.Lock()

    async def is_allowed(self, key: str) -> bool:
        """Check if request is allowed."""
        async with self._lock:
            if key not in self.buckets:
                self.buckets[key] = TokenBucket(
                    capacity=self.burst,
                    refill_rate=self.requests_per_second
                )
            return self.buckets[key].consume()

    async def cleanup(self, max_age: float = 3600):
        """Remove old buckets."""
        async with self._lock:
            now = time.monotonic()
            expired = [
                key for key, bucket in self.buckets.items()
                if now - bucket.last_update > max_age
            ]
            for key in expired:
                del self.buckets[key]


class RateLimitMiddleware:
    """Rate limiting middleware."""

    def __init__(self, app, limiter: RateLimiter):
        self.app = app
        self.limiter = limiter

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        # Get client IP
        client = scope.get('client', ('unknown', 0))
        client_ip = client[0]

        # Check rate limit
        if not await self.limiter.is_allowed(client_ip):
            await send({
                'type': 'http.response.start',
                'status': 429,
                'headers': [
                    (b'content-type', b'application/json'),
                    (b'retry-after', b'60'),
                ],
            })
            await send({
                'type': 'http.response.body',
                'body': b'{"error": "Too Many Requests"}',
            })
            return

        await self.app(scope, receive, send)
```

### Distributed Rate Limiting with Redis

```python
import aioredis
import time


class RedisRateLimiter:
    """Redis-based distributed rate limiter."""

    def __init__(self, redis: aioredis.Redis,
                 requests: int = 100,
                 window: int = 60):
        self.redis = redis
        self.requests = requests
        self.window = window

    async def is_allowed(self, key: str) -> tuple[bool, dict]:
        """Check if request allowed (sliding window)."""
        now = int(time.time())
        window_start = now - self.window

        pipe = self.redis.pipeline()
        full_key = f"ratelimit:{key}"

        # Remove old entries
        pipe.zremrangebyscore(full_key, 0, window_start)
        # Add current request
        pipe.zadd(full_key, {str(now): now})
        # Count requests in window
        pipe.zcard(full_key)
        # Set expiry
        pipe.expire(full_key, self.window)

        results = await pipe.execute()
        count = results[2]

        allowed = count <= self.requests
        info = {
            'limit': self.requests,
            'remaining': max(0, self.requests - count),
            'reset': now + self.window
        }

        return allowed, info
```

---

## 19.8 Security Headers

```python
class SecurityHeadersMiddleware:
    """Add comprehensive security headers."""

    def __init__(self, app):
        self.app = app
        self.headers = [
            # Prevent clickjacking
            (b'x-frame-options', b'DENY'),
            # Prevent MIME sniffing
            (b'x-content-type-options', b'nosniff'),
            # XSS protection
            (b'x-xss-protection', b'1; mode=block'),
            # Referrer policy
            (b'referrer-policy', b'strict-origin-when-cross-origin'),
            # Permissions policy
            (b'permissions-policy',
             b'geolocation=(), microphone=(), camera=()'),
        ]

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        async def send_wrapper(message):
            if message['type'] == 'http.response.start':
                headers = list(message.get('headers', []))
                headers.extend(self.headers)
                message = {**message, 'headers': headers}
            await send(message)

        await self.app(scope, receive, send_wrapper)
```

---

## 19.9 CSRF Protection

```python
import secrets
import hmac
import hashlib
from typing import Optional


class CSRFProtection:
    """CSRF token generation and validation."""

    def __init__(self, secret_key: str):
        self.secret_key = secret_key

    def generate_token(self, session_id: str) -> str:
        """Generate CSRF token for session."""
        random_value = secrets.token_hex(32)
        signature = self._sign(f"{session_id}:{random_value}")
        return f"{random_value}:{signature}"

    def validate_token(self, session_id: str, token: str) -> bool:
        """Validate CSRF token."""
        try:
            random_value, signature = token.split(':')
            expected = self._sign(f"{session_id}:{random_value}")
            return hmac.compare_digest(signature, expected)
        except (ValueError, AttributeError):
            return False

    def _sign(self, data: str) -> str:
        return hmac.new(
            self.secret_key.encode(),
            data.encode(),
            hashlib.sha256
        ).hexdigest()


class CSRFMiddleware:
    """CSRF protection middleware."""

    def __init__(self, app, csrf: CSRFProtection,
                 safe_methods: set = None):
        self.app = app
        self.csrf = csrf
        self.safe_methods = safe_methods or {'GET', 'HEAD', 'OPTIONS'}

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        method = scope.get('method', 'GET')
        if method in self.safe_methods:
            return await self.app(scope, receive, send)

        # Get session ID from scope (set by session middleware)
        session_id = scope.get('session', {}).get('id')
        if not session_id:
            return await self._forbidden(send, "No session")

        # Get CSRF token from header or body
        csrf_token = None
        for name, value in scope.get('headers', []):
            if name == b'x-csrf-token':
                csrf_token = value.decode()
                break

        if not csrf_token or not self.csrf.validate_token(session_id, csrf_token):
            return await self._forbidden(send, "Invalid CSRF token")

        await self.app(scope, receive, send)

    async def _forbidden(self, send, message: str):
        await send({
            'type': 'http.response.start',
            'status': 403,
            'headers': [(b'content-type', b'application/json')],
        })
        await send({
            'type': 'http.response.body',
            'body': f'{{"error": "{message}"}}'.encode(),
        })
```

---

## 19.10 Security Checklist

### Input/Output

```
□ All inputs validated on server
□ SQL queries parameterized
□ HTML output escaped
□ JSON encoding used for API responses
□ File uploads validated and sandboxed
□ Path traversal prevented
```

### Authentication

```
□ Passwords hashed with Argon2/bcrypt
□ JWT tokens with short expiry
□ Refresh token rotation
□ Account lockout after failures
□ Password complexity requirements
□ Multi-factor authentication (high-security)
```

### Transport

```
□ TLS 1.2+ only
□ Strong cipher suites
□ HSTS enabled
□ Certificate pinning (mobile apps)
□ Secure cookies (Secure, HttpOnly, SameSite)
```

### Headers

```
□ Content-Security-Policy
□ X-Frame-Options
□ X-Content-Type-Options
□ X-XSS-Protection
□ Referrer-Policy
□ Permissions-Policy
```

### Application

```
□ Rate limiting implemented
□ CSRF protection for forms
□ Session fixation prevention
□ Sensitive data not logged
□ Error messages don't leak info
□ Dependencies up to date
```

---

## Exercises

### Exercise 19.1: Security Audit

Audit your server for:
1. Input validation gaps
2. Missing security headers
3. SQL injection vulnerabilities
4. XSS vulnerabilities

### Exercise 19.2: Implement Auth System

Build a complete authentication system:
- User registration with password hashing
- Login with JWT tokens
- Refresh token rotation
- Logout with token revocation

### Exercise 19.3: Rate Limit by Endpoint

Implement rate limiting that:
- Different limits per endpoint
- Authenticated users get higher limits
- Returns Retry-After header

---

## Summary

Security essentials:

1. **Trust no input**: Validate everything
2. **Encode output**: Prevent XSS
3. **Use parameters**: Prevent SQL injection
4. **Hash passwords**: Use Argon2/bcrypt
5. **Encrypt transport**: TLS 1.2+
6. **Rate limit**: Prevent abuse
7. **Add headers**: CSP, HSTS, etc.

---

## Next Module

**[Module 20: Reliability Engineering →](./MODULE_20_RELIABILITY.md)**

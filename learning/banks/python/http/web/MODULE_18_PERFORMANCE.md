# Module 18: Performance Engineering

## Overview

Performance is not an afterthought—it's designed in. This module covers profiling, benchmarking, optimization techniques, and understanding where time goes in a web server. You'll learn to measure, analyze, and improve performance systematically.

---

## Learning Objectives

By the end of this module, you will be able to:

1. Profile Python web servers accurately
2. Identify performance bottlenecks
3. Optimize I/O, CPU, and memory usage
4. Implement connection pooling and caching
5. Configure OS-level optimizations

---

## 18.1 Performance Fundamentals

### Where Time Goes

```
Typical HTTP Request Breakdown:

┌─────────────────────────────────────────────────────────────┐
│ DNS Resolution                     │████░░░░░░│  5%         │
│ TCP Handshake                      │████░░░░░░│  5%         │
│ TLS Handshake                      │██████████│ 15%         │
│ Server Processing                  │██████████████████│ 40% │
│   ├─ Request Parsing               │██░░░░░░░░│  3%         │
│   ├─ Routing                       │█░░░░░░░░░│  1%         │
│   ├─ Business Logic                │████░░░░░░│  6%         │
│   ├─ Database Query                │████████████████│ 25%   │
│   └─ Response Serialization        │███░░░░░░░│  5%         │
│ Response Transfer                  │██████████████│ 25%     │
│ Client Rendering                   │██████░░░░│ 10%         │
└─────────────────────────────────────────────────────────────┘
```

### Key Metrics

| Metric | What It Measures | Target |
|--------|------------------|--------|
| **Latency (p50/p99)** | Response time distribution | < 100ms / < 500ms |
| **Throughput (RPS)** | Requests per second | Depends on hardware |
| **TTFB** | Time to first byte | < 200ms |
| **Error Rate** | Failed requests | < 0.1% |
| **CPU Usage** | Processing overhead | < 70% sustained |
| **Memory Usage** | RAM consumption | Stable, no leaks |

### Little's Law

```
L = λ × W

Where:
L = Average concurrent requests
λ = Arrival rate (requests/second)
W = Average response time (seconds)

Example:
- 1000 RPS, 100ms response time
- L = 1000 × 0.1 = 100 concurrent requests
```

---

## 18.2 Profiling Tools

### cProfile - CPU Profiling

```python
import cProfile
import pstats
from io import StringIO

def profile_request():
    """Profile a single request handler."""
    profiler = cProfile.Profile()
    profiler.enable()

    # Code to profile
    handle_request()

    profiler.disable()

    # Analyze results
    stream = StringIO()
    stats = pstats.Stats(profiler, stream=stream)
    stats.sort_stats('cumulative')
    stats.print_stats(20)

    print(stream.getvalue())


# As decorator
def profile(func):
    """Profiling decorator."""
    def wrapper(*args, **kwargs):
        profiler = cProfile.Profile()
        result = profiler.runcall(func, *args, **kwargs)

        stats = pstats.Stats(profiler)
        stats.strip_dirs()
        stats.sort_stats('cumulative')
        stats.print_stats(10)

        return result
    return wrapper
```

### line_profiler - Line-by-Line

```python
# pip install line_profiler

@profile  # Decorator from line_profiler
def parse_request(data: bytes) -> dict:
    """Parse HTTP request (profiled line by line)."""
    lines = data.split(b'\r\n')  # Time: 0.1ms
    method, path, _ = lines[0].split()  # Time: 0.05ms
    headers = {}
    for line in lines[1:]:  # Time: 0.3ms total
        if b':' in line:
            key, value = line.split(b':', 1)
            headers[key.decode().lower()] = value.decode().strip()
    return {'method': method, 'path': path, 'headers': headers}

# Run: kernprof -l -v script.py
```

### memory_profiler - Memory Usage

```python
# pip install memory_profiler

from memory_profiler import profile

@profile
def process_large_file(path: str):
    """Memory profile file processing."""
    with open(path, 'rb') as f:
        data = f.read()  # Memory spike here
    result = transform(data)
    return result

# Run: python -m memory_profiler script.py
```

### py-spy - Sampling Profiler

```bash
# pip install py-spy

# Profile running process
py-spy top --pid 12345

# Generate flame graph
py-spy record -o profile.svg --pid 12345

# Profile a command
py-spy record -o profile.svg -- python server.py
```

### asyncio Profiling

```python
import asyncio
import time


class AsyncProfiler:
    """Profile async code execution."""

    def __init__(self):
        self.timings = {}

    def profile(self, name: str):
        """Decorator for async functions."""
        def decorator(func):
            async def wrapper(*args, **kwargs):
                start = time.perf_counter()
                try:
                    return await func(*args, **kwargs)
                finally:
                    elapsed = time.perf_counter() - start
                    if name not in self.timings:
                        self.timings[name] = []
                    self.timings[name].append(elapsed)
            return wrapper
        return decorator

    def report(self):
        """Generate timing report."""
        for name, times in self.timings.items():
            avg = sum(times) / len(times)
            max_time = max(times)
            min_time = min(times)
            print(f"{name}: avg={avg*1000:.2f}ms, "
                  f"min={min_time*1000:.2f}ms, "
                  f"max={max_time*1000:.2f}ms, "
                  f"count={len(times)}")


profiler = AsyncProfiler()


@profiler.profile("handle_request")
async def handle_request(request):
    user = await get_user(request)
    data = await fetch_data(user)
    return Response(data)


@profiler.profile("get_user")
async def get_user(request):
    await asyncio.sleep(0.01)  # Simulate DB
    return {"id": 1}


@profiler.profile("fetch_data")
async def fetch_data(user):
    await asyncio.sleep(0.05)  # Simulate external API
    return {"data": "..."}
```

---

## 18.3 Benchmarking

### wrk - HTTP Benchmarking

```bash
# Basic benchmark
wrk -t12 -c400 -d30s http://localhost:8080/

# With Lua script for POST
wrk -t12 -c400 -d30s -s post.lua http://localhost:8080/api

# post.lua
wrk.method = "POST"
wrk.body = '{"key": "value"}'
wrk.headers["Content-Type"] = "application/json"
```

### hey - Simple Benchmarking

```bash
# 10000 requests, 200 concurrent
hey -n 10000 -c 200 http://localhost:8080/

# With request body
hey -n 10000 -c 200 -m POST -d '{"key":"value"}' \
    -H "Content-Type: application/json" \
    http://localhost:8080/api
```

### Python Benchmarking Framework

```python
"""
Benchmark framework for web servers.
"""

import asyncio
import aiohttp
import time
import statistics
from dataclasses import dataclass
from typing import List


@dataclass
class BenchmarkResult:
    total_requests: int
    successful: int
    failed: int
    total_time: float
    latencies: List[float]

    @property
    def rps(self) -> float:
        return self.total_requests / self.total_time

    @property
    def p50(self) -> float:
        return statistics.median(self.latencies) * 1000

    @property
    def p99(self) -> float:
        sorted_lat = sorted(self.latencies)
        idx = int(len(sorted_lat) * 0.99)
        return sorted_lat[idx] * 1000

    @property
    def avg(self) -> float:
        return statistics.mean(self.latencies) * 1000

    def report(self):
        print(f"Requests:     {self.total_requests}")
        print(f"Successful:   {self.successful}")
        print(f"Failed:       {self.failed}")
        print(f"Total time:   {self.total_time:.2f}s")
        print(f"RPS:          {self.rps:.2f}")
        print(f"Latency avg:  {self.avg:.2f}ms")
        print(f"Latency p50:  {self.p50:.2f}ms")
        print(f"Latency p99:  {self.p99:.2f}ms")


async def benchmark(url: str, requests: int = 1000,
                   concurrency: int = 100) -> BenchmarkResult:
    """Run HTTP benchmark."""
    latencies = []
    successful = 0
    failed = 0
    semaphore = asyncio.Semaphore(concurrency)

    async def make_request(session: aiohttp.ClientSession):
        nonlocal successful, failed
        async with semaphore:
            start = time.perf_counter()
            try:
                async with session.get(url) as resp:
                    await resp.read()
                    if resp.status == 200:
                        successful += 1
                    else:
                        failed += 1
            except Exception:
                failed += 1
            finally:
                latencies.append(time.perf_counter() - start)

    start_time = time.perf_counter()

    async with aiohttp.ClientSession() as session:
        tasks = [make_request(session) for _ in range(requests)]
        await asyncio.gather(*tasks)

    total_time = time.perf_counter() - start_time

    return BenchmarkResult(
        total_requests=requests,
        successful=successful,
        failed=failed,
        total_time=total_time,
        latencies=latencies
    )


# Usage
async def main():
    result = await benchmark("http://localhost:8080/", requests=10000, concurrency=200)
    result.report()


if __name__ == '__main__':
    asyncio.run(main())
```

---

## 18.4 I/O Optimization

### Connection Pooling

```python
import asyncio
from typing import Dict, Optional
from contextlib import asynccontextmanager


class ConnectionPool:
    """Async connection pool."""

    def __init__(self, factory, min_size: int = 5, max_size: int = 20):
        self.factory = factory
        self.min_size = min_size
        self.max_size = max_size
        self._pool: asyncio.Queue = asyncio.Queue(maxsize=max_size)
        self._size = 0
        self._lock = asyncio.Lock()

    async def initialize(self):
        """Pre-create minimum connections."""
        for _ in range(self.min_size):
            conn = await self.factory()
            await self._pool.put(conn)
            self._size += 1

    @asynccontextmanager
    async def acquire(self):
        """Acquire a connection from pool."""
        conn = await self._get_connection()
        try:
            yield conn
        finally:
            await self._return_connection(conn)

    async def _get_connection(self):
        # Try to get from pool
        try:
            return self._pool.get_nowait()
        except asyncio.QueueEmpty:
            pass

        # Create new if under limit
        async with self._lock:
            if self._size < self.max_size:
                conn = await self.factory()
                self._size += 1
                return conn

        # Wait for available connection
        return await self._pool.get()

    async def _return_connection(self, conn):
        try:
            self._pool.put_nowait(conn)
        except asyncio.QueueFull:
            # Pool is full, close connection
            await conn.close()
            async with self._lock:
                self._size -= 1


# Database pool example
class DatabasePool:
    """PostgreSQL connection pool."""

    def __init__(self, dsn: str, min_size: int = 5, max_size: int = 20):
        self.dsn = dsn
        self.pool = None

    async def initialize(self):
        import asyncpg
        self.pool = await asyncpg.create_pool(
            self.dsn,
            min_size=5,
            max_size=20,
            command_timeout=60
        )

    async def execute(self, query: str, *args):
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetch(self, query: str, *args):
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)
```

### HTTP Client Pooling

```python
import aiohttp
from typing import Optional


class HTTPClient:
    """Pooled HTTP client."""

    _instance: Optional['HTTPClient'] = None
    _session: Optional[aiohttp.ClientSession] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def initialize(self):
        connector = aiohttp.TCPConnector(
            limit=100,  # Total connections
            limit_per_host=30,  # Per-host limit
            ttl_dns_cache=300,  # DNS cache TTL
            enable_cleanup_closed=True
        )
        timeout = aiohttp.ClientTimeout(total=30)
        self._session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout
        )

    async def get(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        return await self._session.get(url, **kwargs)

    async def post(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        return await self._session.post(url, **kwargs)

    async def close(self):
        if self._session:
            await self._session.close()


# Usage
http_client = HTTPClient()

async def startup():
    await http_client.initialize()

async def shutdown():
    await http_client.close()

async def fetch_data(url: str):
    async with await http_client.get(url) as resp:
        return await resp.json()
```

### Socket Optimization

```python
import socket


def optimize_server_socket(sock: socket.socket):
    """Apply performance optimizations to server socket."""
    # Reuse address immediately
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # Reuse port (multiple processes)
    if hasattr(socket, 'SO_REUSEPORT'):
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)

    # TCP optimizations
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    # Increase buffer sizes
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)

    # Quick ACK
    if hasattr(socket, 'TCP_QUICKACK'):
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_QUICKACK, 1)


def optimize_client_socket(sock: socket.socket):
    """Optimize client connection socket."""
    # Disable Nagle's algorithm
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    # Keep-alive
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

    # Linux-specific keep-alive tuning
    if hasattr(socket, 'TCP_KEEPIDLE'):
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 60)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 6)
```

---

## 18.5 CPU Optimization

### Avoid Repeated Work

```python
import re
from functools import lru_cache


# Bad: Compile regex every call
def parse_path_bad(path: str):
    match = re.match(r'/users/(\d+)', path)
    return match.group(1) if match else None


# Good: Compile once
PATH_PATTERN = re.compile(r'/users/(\d+)')

def parse_path_good(path: str):
    match = PATH_PATTERN.match(path)
    return match.group(1) if match else None


# Cache expensive computations
@lru_cache(maxsize=1000)
def compute_etag(content: bytes) -> str:
    import hashlib
    return hashlib.md5(content).hexdigest()


# Precompute constants
HTTP_HEADERS = {
    b'content-type': b'Content-Type',
    b'content-length': b'Content-Length',
    # ... more headers
}

def normalize_header(name: bytes) -> bytes:
    """Fast header normalization."""
    return HTTP_HEADERS.get(name.lower(), name.title())
```

### Efficient Data Structures

```python
from collections import defaultdict
from typing import Dict, Any


# Bad: O(n) lookup in list
class SlowRouter:
    def __init__(self):
        self.routes = []

    def add_route(self, path, handler):
        self.routes.append((path, handler))

    def match(self, path):
        for route_path, handler in self.routes:  # O(n)
            if route_path == path:
                return handler
        return None


# Good: O(1) lookup in dict
class FastRouter:
    def __init__(self):
        self.routes: Dict[str, Any] = {}

    def add_route(self, path, handler):
        self.routes[path] = handler

    def match(self, path):
        return self.routes.get(path)  # O(1)


# For prefix matching, use a trie
class TrieRouter:
    """Radix trie for fast route matching."""

    def __init__(self):
        self.root = {}
        self.handlers = {}

    def add_route(self, path: str, handler):
        parts = path.strip('/').split('/')
        node = self.root

        for part in parts:
            if part not in node:
                node[part] = {}
            node = node[part]

        self.handlers[path] = handler

    def match(self, path: str):
        # Implementation for O(path_length) matching
        pass
```

### String Operations

```python
# Bad: String concatenation in loop
def build_response_bad(headers: dict, body: str) -> str:
    response = "HTTP/1.1 200 OK\r\n"
    for key, value in headers.items():
        response += f"{key}: {value}\r\n"  # Creates new string each time
    response += "\r\n"
    response += body
    return response


# Good: Use join
def build_response_good(headers: dict, body: str) -> str:
    lines = ["HTTP/1.1 200 OK"]
    lines.extend(f"{k}: {v}" for k, v in headers.items())
    lines.append("")
    lines.append(body)
    return "\r\n".join(lines)


# Better: Use bytes and bytearray
def build_response_best(headers: dict, body: bytes) -> bytes:
    buffer = bytearray(b"HTTP/1.1 200 OK\r\n")
    for key, value in headers.items():
        buffer.extend(f"{key}: {value}\r\n".encode())
    buffer.extend(b"\r\n")
    buffer.extend(body)
    return bytes(buffer)
```

### JSON Performance

```python
import json
from functools import lru_cache

# Use orjson for better performance
try:
    import orjson

    def json_dumps(obj) -> bytes:
        return orjson.dumps(obj)

    def json_loads(data: bytes):
        return orjson.loads(data)

except ImportError:
    def json_dumps(obj) -> bytes:
        return json.dumps(obj).encode()

    def json_loads(data: bytes):
        return json.loads(data)


# Cache serialized responses
@lru_cache(maxsize=100)
def get_cached_response(key: str) -> bytes:
    data = fetch_data(key)
    return json_dumps(data)
```

---

## 18.6 Memory Optimization

### Streaming Large Responses

```python
async def stream_large_file(path: str, chunk_size: int = 65536):
    """Stream file without loading into memory."""
    async with aiofiles.open(path, 'rb') as f:
        while True:
            chunk = await f.read(chunk_size)
            if not chunk:
                break
            yield chunk


async def handle_download(request):
    """Handle file download with streaming."""
    path = get_file_path(request)

    async def generate():
        async for chunk in stream_large_file(path):
            yield chunk

    return StreamingResponse(
        generate(),
        media_type='application/octet-stream'
    )
```

### Object Reuse

```python
from typing import Optional


class RequestPool:
    """Pool of reusable request objects."""

    def __init__(self, size: int = 100):
        self._pool = [Request() for _ in range(size)]
        self._available = list(range(size))

    def acquire(self) -> Optional['Request']:
        if self._available:
            idx = self._available.pop()
            return self._pool[idx]
        return Request()  # Create new if pool empty

    def release(self, request: 'Request'):
        request.reset()
        if len(self._available) < len(self._pool):
            idx = self._pool.index(request)
            self._available.append(idx)


class Request:
    """Reusable request object."""

    __slots__ = ['method', 'path', 'headers', 'body', '_idx']

    def __init__(self):
        self.reset()

    def reset(self):
        self.method = None
        self.path = None
        self.headers = {}
        self.body = None
```

### __slots__ for Memory Efficiency

```python
# Without __slots__: Each instance has a __dict__
class HeaderBad:
    def __init__(self, name, value):
        self.name = name
        self.value = value


# With __slots__: Fixed attributes, no __dict__
class HeaderGood:
    __slots__ = ['name', 'value']

    def __init__(self, name, value):
        self.name = name
        self.value = value


# Memory comparison (1 million objects):
# HeaderBad:  ~150 MB
# HeaderGood: ~50 MB
```

### Generator-Based Processing

```python
# Bad: Load all into memory
def process_lines_bad(path: str) -> list:
    with open(path) as f:
        lines = f.readlines()  # All in memory
    return [process(line) for line in lines]


# Good: Generator (lazy evaluation)
def process_lines_good(path: str):
    with open(path) as f:
        for line in f:  # One line at a time
            yield process(line)


# Async generator
async def process_requests(reader):
    async for line in reader:
        yield await parse_request(line)
```

---

## 18.7 Caching Strategies

### In-Memory Cache

```python
import time
from typing import Any, Optional
from collections import OrderedDict
from threading import Lock


class LRUCache:
    """Thread-safe LRU cache with TTL."""

    def __init__(self, maxsize: int = 1000, ttl: float = 300):
        self.maxsize = maxsize
        self.ttl = ttl
        self._cache: OrderedDict = OrderedDict()
        self._timestamps: dict = {}
        self._lock = Lock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key not in self._cache:
                return None

            # Check TTL
            if time.time() - self._timestamps[key] > self.ttl:
                del self._cache[key]
                del self._timestamps[key]
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            return self._cache[key]

    def set(self, key: str, value: Any):
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            else:
                if len(self._cache) >= self.maxsize:
                    # Remove oldest
                    oldest = next(iter(self._cache))
                    del self._cache[oldest]
                    del self._timestamps[oldest]

            self._cache[key] = value
            self._timestamps[key] = time.time()

    def delete(self, key: str):
        with self._lock:
            self._cache.pop(key, None)
            self._timestamps.pop(key, None)


# Usage
cache = LRUCache(maxsize=10000, ttl=60)

async def get_user(user_id: int):
    cached = cache.get(f"user:{user_id}")
    if cached:
        return cached

    user = await db.fetch_user(user_id)
    cache.set(f"user:{user_id}", user)
    return user
```

### Response Caching Middleware

```python
import hashlib
from typing import Callable


class CacheMiddleware:
    """HTTP response caching middleware."""

    def __init__(self, app: Callable, cache: LRUCache):
        self.app = app
        self.cache = cache

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        # Only cache GET requests
        if scope['method'] != 'GET':
            return await self.app(scope, receive, send)

        # Generate cache key
        cache_key = self._make_key(scope)

        # Check cache
        cached = self.cache.get(cache_key)
        if cached:
            await self._send_cached(cached, send)
            return

        # Capture response
        response_parts = []

        async def capture_send(message):
            response_parts.append(message)
            await send(message)

        await self.app(scope, receive, capture_send)

        # Cache successful responses
        if self._is_cacheable(response_parts):
            self.cache.set(cache_key, response_parts)

    def _make_key(self, scope) -> str:
        path = scope['path']
        query = scope.get('query_string', b'').decode()
        return hashlib.md5(f"{path}?{query}".encode()).hexdigest()

    def _is_cacheable(self, parts) -> bool:
        for part in parts:
            if part['type'] == 'http.response.start':
                return 200 <= part['status'] < 300
        return False

    async def _send_cached(self, parts, send):
        for part in parts:
            await send(part)
```

### Redis Caching

```python
import aioredis
import json
from typing import Optional, Any


class RedisCache:
    """Redis-based distributed cache."""

    def __init__(self, url: str = "redis://localhost"):
        self.url = url
        self.redis = None

    async def connect(self):
        self.redis = await aioredis.from_url(
            self.url,
            encoding="utf-8",
            decode_responses=True
        )

    async def get(self, key: str) -> Optional[Any]:
        data = await self.redis.get(key)
        if data:
            return json.loads(data)
        return None

    async def set(self, key: str, value: Any, ttl: int = 300):
        data = json.dumps(value)
        await self.redis.setex(key, ttl, data)

    async def delete(self, key: str):
        await self.redis.delete(key)

    async def get_or_set(self, key: str, factory: Callable,
                         ttl: int = 300) -> Any:
        """Get from cache or compute and cache."""
        cached = await self.get(key)
        if cached is not None:
            return cached

        value = await factory()
        await self.set(key, value, ttl)
        return value


# Usage
redis_cache = RedisCache()

async def get_user_profile(user_id: int):
    return await redis_cache.get_or_set(
        f"profile:{user_id}",
        lambda: db.fetch_profile(user_id),
        ttl=600
    )
```

---

## 18.8 OS-Level Optimization

### Linux Kernel Tuning

```bash
# /etc/sysctl.conf

# Increase max connections
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 65535

# Reuse TIME_WAIT connections
net.ipv4.tcp_tw_reuse = 1

# Increase local port range
net.ipv4.ip_local_port_range = 1024 65535

# TCP keepalive
net.ipv4.tcp_keepalive_time = 60
net.ipv4.tcp_keepalive_intvl = 10
net.ipv4.tcp_keepalive_probes = 6

# File descriptors
fs.file-max = 2097152
fs.nr_open = 2097152

# Network buffer sizes
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
net.ipv4.tcp_rmem = 4096 87380 16777216
net.ipv4.tcp_wmem = 4096 87380 16777216
```

### ulimit Settings

```bash
# /etc/security/limits.conf

# Increase open file limit
* soft nofile 1048576
* hard nofile 1048576

# Increase process limit
* soft nproc 65535
* hard nproc 65535
```

### Python Runtime Optimization

```python
import gc
import sys


def optimize_runtime():
    """Apply Python runtime optimizations."""
    # Disable GC during critical sections
    gc.disable()

    # Set recursion limit
    sys.setrecursionlimit(10000)

    # Hash randomization (security, slight perf cost)
    # PYTHONHASHSEED=0 for deterministic hashing


# Context manager for GC
from contextlib import contextmanager

@contextmanager
def pause_gc():
    """Temporarily pause garbage collection."""
    gc.disable()
    try:
        yield
    finally:
        gc.enable()


# Usage
async def handle_batch(items):
    with pause_gc():
        results = []
        for item in items:
            results.append(await process(item))
        return results
```

---

## 18.9 Performance Checklist

### Before Production

```
□ Profile critical paths
□ Benchmark with realistic load
□ Test under sustained load (30+ minutes)
□ Monitor memory for leaks
□ Test error paths under load
□ Verify graceful degradation
```

### Server Configuration

```
□ Connection pooling configured
□ Keep-alive enabled and tuned
□ Appropriate worker count
□ Buffer sizes optimized
□ Timeout values set
□ Backpressure handling
```

### Code Optimization

```
□ Regex patterns pre-compiled
□ Expensive computations cached
□ Large responses streamed
□ Database queries optimized
□ N+1 queries eliminated
□ JSON library optimized (orjson)
```

### OS Configuration

```
□ File descriptor limits increased
□ TCP parameters tuned
□ Kernel settings optimized
□ NUMA awareness (multi-socket)
□ CPU affinity configured
```

---

## Exercises

### Exercise 18.1: Profile Your Server

Profile your server handling 1000 requests:
1. Identify top 5 time-consuming functions
2. Find memory allocations
3. Create optimization plan

### Exercise 18.2: Implement Caching

Add response caching to your server:
- Cache GET responses for 60 seconds
- Support cache invalidation
- Add cache-hit headers

### Exercise 18.3: Optimize JSON

Replace stdlib JSON with orjson:
- Benchmark before/after
- Handle edge cases (datetime, UUID)
- Measure memory impact

---

## Summary

Performance engineering fundamentals:

1. **Measure first**: Profile before optimizing
2. **I/O matters most**: Pool connections, optimize sockets
3. **Cache aggressively**: Memory cache, Redis, HTTP caching
4. **Avoid allocations**: Reuse objects, stream large data
5. **Tune the OS**: Kernel parameters, file limits

---

## Next Module

**[Module 19: Security Hardening →](./MODULE_19_SECURITY.md)**

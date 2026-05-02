# Module 6: Performance Optimization

---

## 6.1 Caching Strategies

### In-Memory Caching

```python
from fastapi import FastAPI, Depends
from functools import lru_cache
from datetime import datetime, timedelta
from typing import Any, Optional
import asyncio
import time

app = FastAPI()

# Simple LRU cache for synchronous functions
@lru_cache(maxsize=100)
def get_config_value(key: str) -> str:
    # Expensive operation cached
    return f"value_for_{key}"


# Time-based cache
class TTLCache:
    def __init__(self, ttl_seconds: int = 300):
        self.ttl = ttl_seconds
        self.cache: dict[str, tuple[Any, float]] = {}
        self.lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        async with self.lock:
            if key in self.cache:
                value, timestamp = self.cache[key]
                if time.time() - timestamp < self.ttl:
                    return value
                del self.cache[key]
            return None

    async def set(self, key: str, value: Any) -> None:
        async with self.lock:
            self.cache[key] = (value, time.time())

    async def delete(self, key: str) -> None:
        async with self.lock:
            self.cache.pop(key, None)

    async def clear(self) -> None:
        async with self.lock:
            self.cache.clear()


# Global cache instance
cache = TTLCache(ttl_seconds=300)


@app.get("/data/{key}")
async def get_data(key: str):
    # Try cache first
    cached = await cache.get(key)
    if cached is not None:
        return {"data": cached, "source": "cache"}

    # Expensive operation
    data = await fetch_expensive_data(key)

    # Store in cache
    await cache.set(key, data)

    return {"data": data, "source": "database"}


# LRU cache with size limit
class LRUCache:
    def __init__(self, maxsize: int = 100):
        self.maxsize = maxsize
        self.cache: dict[str, Any] = {}
        self.order: list[str] = []

    def get(self, key: str) -> Optional[Any]:
        if key in self.cache:
            # Move to end (most recently used)
            self.order.remove(key)
            self.order.append(key)
            return self.cache[key]
        return None

    def set(self, key: str, value: Any) -> None:
        if key in self.cache:
            self.order.remove(key)
        elif len(self.cache) >= self.maxsize:
            # Remove least recently used
            oldest = self.order.pop(0)
            del self.cache[oldest]

        self.cache[key] = value
        self.order.append(key)


# Async LRU decorator
from cachetools import TTLCache as CacheTTL
from cachetools.keys import hashkey

def async_ttl_cache(ttl: int = 300, maxsize: int = 100):
    cache = CacheTTL(maxsize=maxsize, ttl=ttl)

    def decorator(func):
        async def wrapper(*args, **kwargs):
            key = hashkey(*args, **kwargs)
            if key in cache:
                return cache[key]
            result = await func(*args, **kwargs)
            cache[key] = result
            return result
        return wrapper
    return decorator


@async_ttl_cache(ttl=60, maxsize=50)
async def get_user_profile(user_id: int) -> dict:
    # This result will be cached for 60 seconds
    return await db.get_user(user_id)


# Per-request memoization
class RequestCache:
    def __init__(self):
        self.cache: dict = {}

    def get_or_set(self, key: str, factory):
        if key not in self.cache:
            self.cache[key] = factory()
        return self.cache[key]


def get_request_cache() -> RequestCache:
    return RequestCache()


@app.get("/user/{user_id}/full")
async def get_user_full(
    user_id: int,
    request_cache: RequestCache = Depends(get_request_cache)
):
    # User data fetched once per request even if called multiple times
    user = request_cache.get_or_set(
        f"user:{user_id}",
        lambda: db.get_user(user_id)
    )
    return user
```

### Redis Integration

```python
from fastapi import FastAPI, Depends
import redis.asyncio as redis
from typing import Optional, Any
import json
import hashlib
from contextlib import asynccontextmanager

# Redis connection pool
redis_pool = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_pool
    redis_pool = redis.ConnectionPool.from_url(
        "redis://localhost:6379",
        max_connections=10,
        decode_responses=True
    )
    yield
    await redis_pool.disconnect()

app = FastAPI(lifespan=lifespan)


async def get_redis() -> redis.Redis:
    return redis.Redis(connection_pool=redis_pool)


# Cache decorator for endpoints
def cache_response(ttl: int = 300, prefix: str = "cache"):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = f"{prefix}:{func.__name__}:{hash(str(args) + str(kwargs))}"

            r = await get_redis()

            # Try to get from cache
            cached = await r.get(cache_key)
            if cached:
                return json.loads(cached)

            # Execute function
            result = await func(*args, **kwargs)

            # Store in cache
            await r.setex(cache_key, ttl, json.dumps(result))

            return result
        return wrapper
    return decorator


@app.get("/products/{product_id}")
@cache_response(ttl=3600)
async def get_product(product_id: int):
    return await db.get_product(product_id)


# Cache service class
class CacheService:
    def __init__(self, redis: redis.Redis):
        self.redis = redis

    async def get(self, key: str) -> Optional[Any]:
        data = await self.redis.get(key)
        if data:
            return json.loads(data)
        return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int = 300,
        nx: bool = False  # Only set if not exists
    ) -> bool:
        data = json.dumps(value, default=str)
        if nx:
            return await self.redis.setnx(key, data)
        await self.redis.setex(key, ttl, data)
        return True

    async def delete(self, key: str) -> None:
        await self.redis.delete(key)

    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern"""
        keys = []
        async for key in self.redis.scan_iter(pattern):
            keys.append(key)
        if keys:
            return await self.redis.delete(*keys)
        return 0

    async def get_or_set(
        self,
        key: str,
        factory,
        ttl: int = 300
    ) -> Any:
        """Get from cache or compute and store"""
        cached = await self.get(key)
        if cached is not None:
            return cached

        value = await factory()
        await self.set(key, value, ttl)
        return value


async def get_cache_service(
    r: redis.Redis = Depends(get_redis)
) -> CacheService:
    return CacheService(r)


@app.get("/users")
async def list_users(
    page: int = 1,
    cache: CacheService = Depends(get_cache_service)
):
    cache_key = f"users:list:page:{page}"

    return await cache.get_or_set(
        cache_key,
        lambda: db.get_users(page=page),
        ttl=60
    )


# Cache-aside pattern with write-through
class UserRepository:
    def __init__(self, db, cache: CacheService):
        self.db = db
        self.cache = cache

    async def get(self, user_id: int) -> Optional[dict]:
        # Try cache first
        cached = await self.cache.get(f"user:{user_id}")
        if cached:
            return cached

        # Fetch from database
        user = await self.db.get_user(user_id)
        if user:
            await self.cache.set(f"user:{user_id}", user, ttl=3600)
        return user

    async def update(self, user_id: int, data: dict) -> dict:
        # Update database
        user = await self.db.update_user(user_id, data)

        # Update cache (write-through)
        await self.cache.set(f"user:{user_id}", user, ttl=3600)

        return user

    async def delete(self, user_id: int) -> None:
        # Delete from database
        await self.db.delete_user(user_id)

        # Invalidate cache
        await self.cache.delete(f"user:{user_id}")
```

### Cache Invalidation Patterns

```python
from fastapi import FastAPI, Depends
import redis.asyncio as redis
from typing import Set
import json

app = FastAPI()

class CacheInvalidator:
    def __init__(self, redis: redis.Redis):
        self.redis = redis

    async def invalidate_key(self, key: str) -> None:
        """Invalidate single key"""
        await self.redis.delete(key)

    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all keys matching pattern"""
        count = 0
        async for key in self.redis.scan_iter(match=pattern):
            await self.redis.delete(key)
            count += 1
        return count

    async def invalidate_tags(self, tags: Set[str]) -> int:
        """Invalidate all keys associated with tags"""
        count = 0
        for tag in tags:
            tag_key = f"tag:{tag}"
            members = await self.redis.smembers(tag_key)
            if members:
                await self.redis.delete(*members)
                await self.redis.delete(tag_key)
                count += len(members)
        return count


class TaggedCache:
    """Cache with tag-based invalidation"""

    def __init__(self, redis: redis.Redis):
        self.redis = redis

    async def set(
        self,
        key: str,
        value: any,
        ttl: int = 300,
        tags: Set[str] = None
    ) -> None:
        # Store value
        await self.redis.setex(key, ttl, json.dumps(value))

        # Associate with tags
        if tags:
            pipe = self.redis.pipeline()
            for tag in tags:
                pipe.sadd(f"tag:{tag}", key)
                pipe.expire(f"tag:{tag}", ttl)
            await pipe.execute()

    async def get(self, key: str) -> any:
        data = await self.redis.get(key)
        return json.loads(data) if data else None

    async def invalidate_by_tag(self, tag: str) -> int:
        """Invalidate all entries with given tag"""
        tag_key = f"tag:{tag}"
        keys = await self.redis.smembers(tag_key)

        if keys:
            await self.redis.delete(*keys, tag_key)

        return len(keys)


# Usage example
@app.get("/products/{product_id}")
async def get_product(
    product_id: int,
    cache: TaggedCache = Depends(get_tagged_cache)
):
    cache_key = f"product:{product_id}"
    tags = {f"product:{product_id}", "products", "catalog"}

    cached = await cache.get(cache_key)
    if cached:
        return cached

    product = await db.get_product(product_id)
    await cache.set(cache_key, product, ttl=3600, tags=tags)
    return product


@app.put("/products/{product_id}")
async def update_product(
    product_id: int,
    data: ProductUpdate,
    cache: TaggedCache = Depends(get_tagged_cache)
):
    product = await db.update_product(product_id, data)

    # Invalidate all caches related to this product
    await cache.invalidate_by_tag(f"product:{product_id}")

    return product


@app.post("/products/bulk-update")
async def bulk_update_products(
    data: BulkUpdate,
    cache: TaggedCache = Depends(get_tagged_cache)
):
    await db.bulk_update(data)

    # Invalidate entire catalog cache
    await cache.invalidate_by_tag("catalog")

    return {"status": "updated"}


# Event-driven invalidation
class CacheEventHandler:
    def __init__(self, cache: TaggedCache):
        self.cache = cache

    async def on_user_updated(self, user_id: int):
        await self.cache.invalidate_by_tag(f"user:{user_id}")
        await self.cache.invalidate_by_tag("user_list")

    async def on_order_created(self, order_id: int, user_id: int):
        await self.cache.invalidate_by_tag(f"user:{user_id}:orders")
        await self.cache.invalidate_by_tag("orders_list")
        await self.cache.invalidate_by_tag("dashboard")


# Versioned cache keys
class VersionedCache:
    def __init__(self, redis: redis.Redis):
        self.redis = redis

    async def get_version(self, namespace: str) -> int:
        version = await self.redis.get(f"version:{namespace}")
        return int(version) if version else 1

    async def increment_version(self, namespace: str) -> int:
        return await self.redis.incr(f"version:{namespace}")

    async def make_key(self, namespace: str, key: str) -> str:
        version = await self.get_version(namespace)
        return f"{namespace}:v{version}:{key}"

    async def invalidate_namespace(self, namespace: str) -> None:
        """Invalidate all keys in namespace by incrementing version"""
        await self.increment_version(namespace)
```

### Response Caching

```python
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import hashlib
import json

app = FastAPI()

class ResponseCacheMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, redis, default_ttl: int = 60):
        super().__init__(app)
        self.redis = redis
        self.default_ttl = default_ttl

    async def dispatch(self, request: Request, call_next):
        # Only cache GET requests
        if request.method != "GET":
            return await call_next(request)

        # Check cache headers
        if request.headers.get("Cache-Control") == "no-cache":
            response = await call_next(request)
            response.headers["X-Cache"] = "BYPASS"
            return response

        # Generate cache key
        cache_key = self._generate_key(request)

        # Try cache
        cached = await self.redis.get(cache_key)
        if cached:
            data = json.loads(cached)
            response = JSONResponse(
                content=data["body"],
                status_code=data["status"],
                headers=data["headers"]
            )
            response.headers["X-Cache"] = "HIT"
            return response

        # Execute request
        response = await call_next(request)

        # Cache successful responses
        if response.status_code == 200:
            body = b""
            async for chunk in response.body_iterator:
                body += chunk

            ttl = self._get_ttl(response)
            cache_data = {
                "body": json.loads(body),
                "status": response.status_code,
                "headers": dict(response.headers)
            }

            await self.redis.setex(
                cache_key,
                ttl,
                json.dumps(cache_data)
            )

            response = JSONResponse(
                content=cache_data["body"],
                status_code=response.status_code,
                headers=dict(response.headers)
            )

        response.headers["X-Cache"] = "MISS"
        return response

    def _generate_key(self, request: Request) -> str:
        # Include query params and relevant headers
        key_parts = [
            request.url.path,
            str(sorted(request.query_params.items())),
            request.headers.get("Accept-Language", ""),
        ]
        key_string = "|".join(key_parts)
        return f"response:{hashlib.md5(key_string.encode()).hexdigest()}"

    def _get_ttl(self, response: Response) -> int:
        cache_control = response.headers.get("Cache-Control", "")
        if "max-age=" in cache_control:
            import re
            match = re.search(r"max-age=(\d+)", cache_control)
            if match:
                return int(match.group(1))
        return self.default_ttl


# Conditional requests (ETag/Last-Modified)
from datetime import datetime

@app.get("/resource/{id}")
async def get_resource(
    id: int,
    request: Request,
    response: Response
):
    resource = await db.get_resource(id)
    etag = hashlib.md5(json.dumps(resource).encode()).hexdigest()
    last_modified = resource["updated_at"]

    # Check If-None-Match
    if_none_match = request.headers.get("If-None-Match")
    if if_none_match == etag:
        return Response(status_code=304)

    # Check If-Modified-Since
    if_modified_since = request.headers.get("If-Modified-Since")
    if if_modified_since:
        ims_date = datetime.strptime(
            if_modified_since,
            "%a, %d %b %Y %H:%M:%S GMT"
        )
        if last_modified <= ims_date:
            return Response(status_code=304)

    # Set cache headers
    response.headers["ETag"] = etag
    response.headers["Last-Modified"] = last_modified.strftime(
        "%a, %d %b %Y %H:%M:%S GMT"
    )
    response.headers["Cache-Control"] = "private, max-age=3600"

    return resource
```

### Cache Headers

```python
from fastapi import FastAPI, Response
from datetime import datetime, timedelta
from typing import Optional

app = FastAPI()

class CacheControl:
    """Helper for building Cache-Control headers"""

    def __init__(self):
        self.directives = []

    def public(self):
        self.directives.append("public")
        return self

    def private(self):
        self.directives.append("private")
        return self

    def no_cache(self):
        self.directives.append("no-cache")
        return self

    def no_store(self):
        self.directives.append("no-store")
        return self

    def max_age(self, seconds: int):
        self.directives.append(f"max-age={seconds}")
        return self

    def s_maxage(self, seconds: int):
        """Shared cache max age (CDN)"""
        self.directives.append(f"s-maxage={seconds}")
        return self

    def must_revalidate(self):
        self.directives.append("must-revalidate")
        return self

    def stale_while_revalidate(self, seconds: int):
        self.directives.append(f"stale-while-revalidate={seconds}")
        return self

    def stale_if_error(self, seconds: int):
        self.directives.append(f"stale-if-error={seconds}")
        return self

    def immutable(self):
        self.directives.append("immutable")
        return self

    def build(self) -> str:
        return ", ".join(self.directives)


def set_cache_headers(
    response: Response,
    max_age: int = 0,
    private: bool = True,
    must_revalidate: bool = False,
    no_cache: bool = False,
    no_store: bool = False,
    etag: Optional[str] = None,
    last_modified: Optional[datetime] = None,
    vary: Optional[list[str]] = None
):
    """Helper to set cache headers on response"""

    cache_control = CacheControl()

    if no_store:
        cache_control.no_store()
    elif no_cache:
        cache_control.no_cache()
    else:
        if private:
            cache_control.private()
        else:
            cache_control.public()

        if max_age > 0:
            cache_control.max_age(max_age)

        if must_revalidate:
            cache_control.must_revalidate()

    response.headers["Cache-Control"] = cache_control.build()

    if etag:
        response.headers["ETag"] = f'"{etag}"'

    if last_modified:
        response.headers["Last-Modified"] = last_modified.strftime(
            "%a, %d %b %Y %H:%M:%S GMT"
        )

    if vary:
        response.headers["Vary"] = ", ".join(vary)


# Usage examples
@app.get("/static-data")
async def get_static_data(response: Response):
    """Long-lived, public cache"""
    data = {"static": "content"}

    set_cache_headers(
        response,
        max_age=86400,  # 24 hours
        private=False
    )

    return data


@app.get("/user/profile")
async def get_user_profile(response: Response, user_id: int):
    """Private, short cache"""
    profile = await get_profile(user_id)

    set_cache_headers(
        response,
        max_age=300,  # 5 minutes
        private=True,
        etag=hashlib.md5(json.dumps(profile).encode()).hexdigest(),
        vary=["Authorization"]
    )

    return profile


@app.get("/sensitive-data")
async def get_sensitive_data(response: Response):
    """No caching"""
    set_cache_headers(response, no_store=True)
    return {"secret": "data"}


@app.get("/api/config")
async def get_config(response: Response):
    """Stale-while-revalidate pattern"""
    config = await load_config()

    cache_control = (
        CacheControl()
        .public()
        .max_age(60)
        .stale_while_revalidate(300)
        .stale_if_error(3600)
        .build()
    )
    response.headers["Cache-Control"] = cache_control

    return config
```

---

## 6.2 Performance Tuning

### Async vs Sync Endpoint Decisions

```python
from fastapi import FastAPI
import asyncio
import httpx
import time

app = FastAPI()

# Use ASYNC for:
# - I/O bound operations (database, HTTP calls, file I/O)
# - Multiple concurrent operations
# - Long-running I/O operations

@app.get("/async-io")
async def async_io_example():
    """Good use of async - multiple concurrent I/O operations"""
    async with httpx.AsyncClient() as client:
        # Run concurrently
        results = await asyncio.gather(
            client.get("https://api1.example.com/data"),
            client.get("https://api2.example.com/data"),
            client.get("https://api3.example.com/data"),
        )
    return [r.json() for r in results]


@app.get("/async-db")
async def async_db_example(db: AsyncSession = Depends(get_async_db)):
    """Good use of async - async database operations"""
    users = await db.execute(select(User))
    items = await db.execute(select(Item))
    return {"users": users.scalars().all(), "items": items.scalars().all()}


# Use SYNC for:
# - CPU-bound operations (calculations, data processing)
# - Operations that use synchronous libraries
# - Quick operations that don't benefit from async

@app.get("/sync-cpu")
def sync_cpu_example():
    """Sync is fine for CPU-bound work"""
    result = complex_calculation()  # CPU-bound
    return {"result": result}


@app.get("/sync-quick")
def sync_quick():
    """Sync is fine for quick operations"""
    return {"time": time.time()}


# AVOID: Blocking in async functions
@app.get("/bad-async")
async def bad_async_example():
    """BAD: Blocking call in async function"""
    time.sleep(1)  # This blocks the event loop!
    return {"status": "done"}


# CORRECT: Use asyncio.sleep or run_in_executor
@app.get("/good-async")
async def good_async_example():
    """GOOD: Non-blocking sleep"""
    await asyncio.sleep(1)
    return {"status": "done"}


@app.get("/blocking-in-async")
async def blocking_in_async():
    """GOOD: Run blocking code in thread pool"""
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,  # Default executor
        blocking_operation  # Sync function
    )
    return {"result": result}


# Mixed sync and async in same endpoint
@app.get("/mixed")
async def mixed_operations():
    """Combining async I/O with CPU-bound work"""
    # Async I/O
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.example.com/data")
        data = response.json()

    # CPU-bound in executor
    loop = asyncio.get_event_loop()
    processed = await loop.run_in_executor(
        None,
        process_data,  # CPU-bound sync function
        data
    )

    return {"processed": processed}


# Performance comparison
import timeit

async def benchmark_async():
    """Benchmark async operations"""
    async with httpx.AsyncClient() as client:
        tasks = [client.get(f"http://example.com/{i}") for i in range(10)]
        await asyncio.gather(*tasks)

def benchmark_sync():
    """Benchmark sync operations"""
    import requests
    for i in range(10):
        requests.get(f"http://example.com/{i}")

# Async will be faster for I/O-heavy workloads
```

### Database Query Optimization

```python
from fastapi import FastAPI, Depends
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload, joinedload, lazyload
from sqlalchemy.ext.asyncio import AsyncSession

app = FastAPI()

# Eager loading - avoid N+1 queries
@app.get("/users-with-posts-bad")
async def get_users_bad(db: AsyncSession = Depends(get_db)):
    """BAD: N+1 query problem"""
    result = await db.execute(select(User))
    users = result.scalars().all()

    # This causes N additional queries!
    for user in users:
        posts = user.posts  # Lazy load

    return users


@app.get("/users-with-posts-good")
async def get_users_good(db: AsyncSession = Depends(get_db)):
    """GOOD: Eager loading with selectinload"""
    result = await db.execute(
        select(User).options(selectinload(User.posts))
    )
    users = result.scalars().all()
    return users


# Joinedload for one-to-one or many-to-one
@app.get("/posts-with-author")
async def get_posts_with_author(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Post).options(joinedload(Post.author))
    )
    return result.scalars().all()


# Select only needed columns
@app.get("/users-list")
async def get_users_list(db: AsyncSession = Depends(get_db)):
    """Select only columns you need"""
    result = await db.execute(
        select(User.id, User.username, User.email)
    )
    return [{"id": r.id, "username": r.username, "email": r.email} for r in result]


# Pagination
@app.get("/users")
async def get_users_paginated(
    db: AsyncSession = Depends(get_db),
    page: int = 1,
    per_page: int = 20
):
    offset = (page - 1) * per_page

    # Get total count efficiently
    count_result = await db.execute(select(func.count(User.id)))
    total = count_result.scalar()

    # Get page data
    result = await db.execute(
        select(User)
        .order_by(User.id)
        .offset(offset)
        .limit(per_page)
    )
    users = result.scalars().all()

    return {
        "data": users,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page
    }


# Use indexes
"""
-- Add indexes for frequently queried columns
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_posts_user_id ON posts(user_id);
CREATE INDEX idx_posts_created_at ON posts(created_at DESC);

-- Composite index for common query patterns
CREATE INDEX idx_orders_user_status ON orders(user_id, status);
"""


# Batch operations
@app.post("/users/bulk")
async def create_users_bulk(
    users: list[UserCreate],
    db: AsyncSession = Depends(get_db)
):
    """Batch insert for better performance"""
    db_users = [User(**u.model_dump()) for u in users]
    db.add_all(db_users)
    await db.commit()
    return {"created": len(db_users)}


# Raw SQL for complex queries
@app.get("/analytics/user-stats")
async def get_user_stats(db: AsyncSession = Depends(get_db)):
    """Raw SQL for complex analytics"""
    result = await db.execute(
        text("""
            SELECT
                DATE(created_at) as date,
                COUNT(*) as new_users,
                COUNT(CASE WHEN is_active THEN 1 END) as active_users
            FROM users
            WHERE created_at >= NOW() - INTERVAL '30 days'
            GROUP BY DATE(created_at)
            ORDER BY date DESC
        """)
    )
    return [dict(r) for r in result]


# Cursor-based pagination (better for large datasets)
@app.get("/posts")
async def get_posts_cursor(
    db: AsyncSession = Depends(get_db),
    cursor: int = None,
    limit: int = 20
):
    query = select(Post).order_by(Post.id.desc()).limit(limit + 1)

    if cursor:
        query = query.where(Post.id < cursor)

    result = await db.execute(query)
    posts = result.scalars().all()

    has_more = len(posts) > limit
    if has_more:
        posts = posts[:-1]

    next_cursor = posts[-1].id if posts and has_more else None

    return {
        "data": posts,
        "next_cursor": next_cursor,
        "has_more": has_more
    }
```

### Connection Pool Tuning

```python
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import QueuePool, NullPool

# Sync engine with tuned pool
sync_engine = create_engine(
    "postgresql://user:pass@localhost/db",

    # Pool configuration
    poolclass=QueuePool,

    # Number of connections to maintain
    pool_size=10,

    # Additional connections when pool exhausted
    max_overflow=20,

    # Recycle connections after N seconds
    pool_recycle=3600,

    # Validate connections before use
    pool_pre_ping=True,

    # Wait time for connection from pool
    pool_timeout=30,

    # Use LIFO to reuse warm connections
    pool_use_lifo=True,

    # Echo SQL for debugging (disable in production)
    echo=False,
)


# Async engine with tuned pool
async_engine = create_async_engine(
    "postgresql+asyncpg://user:pass@localhost/db",
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,
    pool_pre_ping=True,

    # Asyncpg specific settings
    connect_args={
        "server_settings": {
            "application_name": "myapp",
            "statement_timeout": "30000",  # 30 seconds
        },
        "command_timeout": 60,
    }
)


# Serverless / Lambda configuration (no pooling)
serverless_engine = create_async_engine(
    "postgresql+asyncpg://user:pass@localhost/db",
    poolclass=NullPool,  # No connection pooling
)


# Connection pool monitoring
from sqlalchemy import event

@event.listens_for(sync_engine, "checkout")
def on_checkout(dbapi_conn, connection_record, connection_proxy):
    """Called when connection is checked out from pool"""
    connection_record.info["checkout_time"] = time.time()


@event.listens_for(sync_engine, "checkin")
def on_checkin(dbapi_conn, connection_record):
    """Called when connection is returned to pool"""
    checkout_time = connection_record.info.get("checkout_time")
    if checkout_time:
        duration = time.time() - checkout_time
        if duration > 5:  # Warn on long-held connections
            logger.warning(f"Connection held for {duration:.2f}s")


@event.listens_for(sync_engine, "connect")
def on_connect(dbapi_conn, connection_record):
    """Called when new connection is created"""
    logger.info("New database connection created")


# Pool status endpoint
@app.get("/health/db-pool")
async def db_pool_status():
    pool = sync_engine.pool
    return {
        "pool_size": pool.size(),
        "checked_out": pool.checkedout(),
        "overflow": pool.overflow(),
        "checked_in": pool.checkedin(),
    }


# Dynamic pool sizing based on load
class DynamicPoolManager:
    def __init__(self, engine, min_size: int = 5, max_size: int = 50):
        self.engine = engine
        self.min_size = min_size
        self.max_size = max_size

    async def adjust_pool(self, current_load: float):
        """Adjust pool size based on load (0.0 to 1.0)"""
        target_size = int(
            self.min_size + (self.max_size - self.min_size) * current_load
        )

        # SQLAlchemy doesn't support dynamic resizing,
        # so we'd need to recreate the engine or use pgbouncer


# External connection pooler (pgbouncer)
"""
# pgbouncer.ini
[databases]
mydb = host=localhost dbname=mydb

[pgbouncer]
listen_port = 6432
listen_addr = 127.0.0.1
auth_type = md5
auth_file = /etc/pgbouncer/userlist.txt
pool_mode = transaction
max_client_conn = 1000
default_pool_size = 25
min_pool_size = 5
reserve_pool_size = 5
"""

# Connect to pgbouncer instead of database directly
pgbouncer_engine = create_async_engine(
    "postgresql+asyncpg://user:pass@localhost:6432/mydb",
    # Minimal pooling since pgbouncer handles it
    pool_size=5,
    max_overflow=0,
)
```

### Payload Compression

```python
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse
from starlette.middleware.gzip import GZipMiddleware
import gzip
import zlib
import brotli
from io import BytesIO

app = FastAPI()

# Built-in GZip middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)


# Custom compression middleware with multiple algorithms
class CompressionMiddleware:
    def __init__(self, app, minimum_size: int = 500):
        self.app = app
        self.minimum_size = minimum_size

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Get accepted encodings
        headers = dict(scope.get("headers", []))
        accept_encoding = headers.get(b"accept-encoding", b"").decode()

        response_started = False
        initial_message = None
        body_parts = []

        async def send_wrapper(message):
            nonlocal response_started, initial_message

            if message["type"] == "http.response.start":
                initial_message = message
                return

            if message["type"] == "http.response.body":
                body_parts.append(message.get("body", b""))

                if not message.get("more_body", False):
                    # Complete body received
                    full_body = b"".join(body_parts)

                    if len(full_body) >= self.minimum_size:
                        compressed_body, encoding = self._compress(
                            full_body, accept_encoding
                        )

                        if compressed_body:
                            # Update headers
                            headers = list(initial_message.get("headers", []))
                            headers = [
                                h for h in headers
                                if h[0] != b"content-length"
                            ]
                            headers.append((b"content-encoding", encoding.encode()))
                            headers.append((b"content-length", str(len(compressed_body)).encode()))
                            initial_message["headers"] = headers

                            full_body = compressed_body

                    await send(initial_message)
                    await send({
                        "type": "http.response.body",
                        "body": full_body
                    })

        await self.app(scope, receive, send_wrapper)

    def _compress(self, body: bytes, accept_encoding: str) -> tuple:
        # Try Brotli first (best compression)
        if "br" in accept_encoding:
            try:
                return brotli.compress(body), "br"
            except:
                pass

        # Fall back to gzip
        if "gzip" in accept_encoding:
            buffer = BytesIO()
            with gzip.GzipFile(fileobj=buffer, mode="wb") as f:
                f.write(body)
            return buffer.getvalue(), "gzip"

        # Try deflate
        if "deflate" in accept_encoding:
            return zlib.compress(body), "deflate"

        return None, None


# Request decompression
@app.post("/data")
async def receive_compressed_data(request: Request):
    content_encoding = request.headers.get("content-encoding", "")
    body = await request.body()

    if content_encoding == "gzip":
        body = gzip.decompress(body)
    elif content_encoding == "br":
        body = brotli.decompress(body)
    elif content_encoding == "deflate":
        body = zlib.decompress(body)

    return {"received_bytes": len(body)}


# Streaming compression for large responses
@app.get("/large-file")
async def stream_large_file():
    async def generate():
        with gzip.open("large_file.csv.gz", "wt") as gz:
            # Stream and compress
            for chunk in read_large_data():
                compressed = gzip.compress(chunk.encode())
                yield compressed

    return StreamingResponse(
        generate(),
        media_type="application/gzip",
        headers={"Content-Encoding": "gzip"}
    )


# Pre-compressed static files
from fastapi.staticfiles import StaticFiles

# Serve pre-compressed versions if available
class CompressedStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope) -> Response:
        accept_encoding = ""
        for header, value in scope.get("headers", []):
            if header == b"accept-encoding":
                accept_encoding = value.decode()
                break

        # Try .br version
        if "br" in accept_encoding:
            br_path = path + ".br"
            response = await super().get_response(br_path, scope)
            if response.status_code == 200:
                response.headers["Content-Encoding"] = "br"
                return response

        # Try .gz version
        if "gzip" in accept_encoding:
            gz_path = path + ".gz"
            response = await super().get_response(gz_path, scope)
            if response.status_code == 200:
                response.headers["Content-Encoding"] = "gzip"
                return response

        return await super().get_response(path, scope)

app.mount("/static", CompressedStaticFiles(directory="static"), name="static")
```

### Lazy Loading Patterns

```python
from fastapi import FastAPI, Depends
from functools import cached_property
from typing import Optional
import asyncio

app = FastAPI()

# Lazy initialization of expensive resources
class LazyResource:
    def __init__(self):
        self._resource: Optional[ExpensiveResource] = None
        self._lock = asyncio.Lock()

    async def get(self) -> ExpensiveResource:
        if self._resource is None:
            async with self._lock:
                if self._resource is None:
                    self._resource = await self._initialize()
        return self._resource

    async def _initialize(self) -> ExpensiveResource:
        # Expensive initialization
        return await create_expensive_resource()


lazy_resource = LazyResource()


@app.get("/data")
async def get_data():
    resource = await lazy_resource.get()
    return resource.fetch_data()


# Lazy loaded configuration
class LazyConfig:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
        return cls._instance

    @cached_property
    def settings(self):
        # Load on first access
        return load_settings_from_file()

    @cached_property
    def feature_flags(self):
        return fetch_feature_flags()


config = LazyConfig()


# Lazy relationship loading in responses
class UserResponse(BaseModel):
    id: int
    username: str

    class Config:
        from_attributes = True


class UserWithPostsResponse(UserResponse):
    posts: list[PostResponse] = []


@app.get("/users/{user_id}")
async def get_user(
    user_id: int,
    include_posts: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """Lazy load relationships based on query params"""
    query = select(User).where(User.id == user_id)

    if include_posts:
        query = query.options(selectinload(User.posts))

    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(404)

    if include_posts:
        return UserWithPostsResponse.model_validate(user)
    return UserResponse.model_validate(user)


# Field-level lazy loading
class LazyField:
    def __init__(self, loader):
        self.loader = loader
        self._value = None
        self._loaded = False

    async def get(self):
        if not self._loaded:
            self._value = await self.loader()
            self._loaded = True
        return self._value


class UserProfile:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self._avatar = LazyField(lambda: fetch_avatar(user_id))
        self._stats = LazyField(lambda: fetch_user_stats(user_id))

    async def get_avatar(self):
        return await self._avatar.get()

    async def get_stats(self):
        return await self._stats.get()


# Lazy JSON serialization
class LazyJSONResponse(JSONResponse):
    def render(self, content) -> bytes:
        # Only serialize when actually sending
        if callable(content):
            content = content()
        return super().render(content)


@app.get("/expensive")
async def expensive_endpoint():
    def lazy_content():
        # Only executed if response is actually sent
        return compute_expensive_data()

    return LazyJSONResponse(content=lazy_content)
```

### Profiling FastAPI Applications

```python
from fastapi import FastAPI, Request
import time
import cProfile
import pstats
import io
from contextlib import contextmanager
import tracemalloc
import linecache

app = FastAPI()

# Request timing middleware
@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start

    response.headers["X-Process-Time"] = f"{duration:.4f}"

    if duration > 1.0:  # Log slow requests
        logger.warning(
            f"Slow request: {request.method} {request.url.path} "
            f"took {duration:.2f}s"
        )

    return response


# CPU profiling decorator
def profile_endpoint(func):
    async def wrapper(*args, **kwargs):
        profiler = cProfile.Profile()
        profiler.enable()

        result = await func(*args, **kwargs)

        profiler.disable()

        # Print stats
        stream = io.StringIO()
        stats = pstats.Stats(profiler, stream=stream)
        stats.sort_stats("cumulative")
        stats.print_stats(20)
        print(stream.getvalue())

        return result
    return wrapper


@app.get("/profiled")
@profile_endpoint
async def profiled_endpoint():
    return await slow_operation()


# Memory profiling
@contextmanager
def memory_profile():
    tracemalloc.start()
    try:
        yield
    finally:
        snapshot = tracemalloc.take_snapshot()
        top_stats = snapshot.statistics("lineno")

        print("[ Top 10 memory allocations ]")
        for stat in top_stats[:10]:
            print(stat)

        tracemalloc.stop()


@app.get("/memory-profiled")
async def memory_profiled_endpoint():
    with memory_profile():
        result = await memory_heavy_operation()
    return result


# py-spy for production profiling
"""
# Install: pip install py-spy

# Record flame graph
py-spy record -o profile.svg -- python -m uvicorn main:app

# Top-like view
py-spy top -- python -m uvicorn main:app

# Dump current call stacks
py-spy dump --pid <PID>
"""


# Prometheus metrics
from prometheus_client import Counter, Histogram, generate_latest
from starlette.responses import Response

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"]
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint"]
)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start

    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code
    ).inc()

    REQUEST_LATENCY.labels(
        method=request.method,
        endpoint=request.url.path
    ).observe(duration)

    return response


@app.get("/metrics")
async def metrics():
    return Response(
        content=generate_latest(),
        media_type="text/plain"
    )


# OpenTelemetry tracing
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

# Setup tracing
trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)

otlp_exporter = OTLPSpanExporter(endpoint="http://localhost:4317")
trace.get_tracer_provider().add_span_processor(
    BatchSpanProcessor(otlp_exporter)
)

# Instrument FastAPI
FastAPIInstrumentor.instrument_app(app)


# Custom spans
@app.get("/traced")
async def traced_endpoint():
    with tracer.start_as_current_span("custom-operation") as span:
        span.set_attribute("operation.type", "data-fetch")
        result = await fetch_data()
        span.set_attribute("result.count", len(result))
    return result
```

---

## 6.3 Scaling Considerations

### Gunicorn/Uvicorn Worker Configuration

```python
# gunicorn.conf.py
import multiprocessing
import os

# Server socket
bind = os.getenv("BIND", "0.0.0.0:8000")
backlog = 2048

# Worker processes
workers = int(os.getenv("WORKERS", multiprocessing.cpu_count() * 2 + 1))
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
max_requests = 10000  # Restart workers after N requests
max_requests_jitter = 1000  # Add randomness to prevent thundering herd

# Timeouts
timeout = 30  # Worker timeout
graceful_timeout = 30  # Graceful shutdown timeout
keepalive = 5  # Keep-alive connections timeout

# Logging
accesslog = "-"  # stdout
errorlog = "-"  # stderr
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "myapp"

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# SSL (optional)
# keyfile = "/path/to/key.pem"
# certfile = "/path/to/cert.pem"

# Hooks
def on_starting(server):
    """Called just before the master process is initialized."""
    pass

def on_reload(server):
    """Called to recycle workers during a reload via SIGHUP."""
    pass

def worker_int(worker):
    """Called when a worker receives SIGINT or SIGQUIT."""
    pass

def worker_abort(worker):
    """Called when a worker receives SIGABRT."""
    pass


# Run command:
# gunicorn main:app -c gunicorn.conf.py


# Uvicorn standalone configuration
"""
uvicorn main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 4 \
    --loop uvloop \
    --http httptools \
    --timeout-keep-alive 5 \
    --access-log \
    --log-level info
"""


# Programmatic Uvicorn configuration
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        workers=4,
        loop="uvloop",
        http="httptools",
        timeout_keep_alive=5,
        access_log=True,
        log_level="info",
        reload=False,  # Disable in production
        server_header=False,  # Hide server header
        date_header=True,
    )


# Worker calculation guidelines
"""
CPU-bound workloads:
    workers = cpu_count

I/O-bound workloads:
    workers = cpu_count * 2 + 1

Memory-constrained:
    workers = available_memory / worker_memory_usage
"""
```

### Horizontal Scaling Patterns

```python
# Docker Compose for horizontal scaling
"""
# docker-compose.yml
version: '3.8'

services:
  api:
    build: .
    deploy:
      replicas: 4
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
    environment:
      - DATABASE_URL=postgresql://user:pass@db/mydb
      - REDIS_URL=redis://redis:6379
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    depends_on:
      - api
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro

  db:
    image: postgres:15
    environment:
      POSTGRES_PASSWORD: pass
      POSTGRES_DB: mydb

  redis:
    image: redis:7
"""


# nginx.conf for load balancing
"""
upstream api_servers {
    least_conn;  # Load balancing algorithm
    server api:8000 weight=1;

    # Health checks
    keepalive 32;
}

server {
    listen 80;

    location / {
        proxy_pass http://api_servers;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;

        # Buffering
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
    }

    location /health {
        access_log off;
        proxy_pass http://api_servers/health;
    }
}
"""


# Kubernetes deployment
"""
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: fastapi-app
spec:
  replicas: 3
  selector:
    matchLabels:
      app: fastapi-app
  template:
    metadata:
      labels:
        app: fastapi-app
    spec:
      containers:
      - name: api
        image: myapp:latest
        ports:
        - containerPort: 8000
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-secret
              key: url

---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: fastapi-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: fastapi-app
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
"""


# Health and readiness endpoints
from fastapi import FastAPI
import asyncio

app = FastAPI()

@app.get("/health")
async def health():
    """Liveness probe - is the app running?"""
    return {"status": "healthy"}


@app.get("/ready")
async def ready():
    """Readiness probe - is the app ready to receive traffic?"""
    checks = await asyncio.gather(
        check_database(),
        check_redis(),
        check_external_services(),
        return_exceptions=True
    )

    all_healthy = all(c is True for c in checks)

    if not all_healthy:
        raise HTTPException(503, "Not ready")

    return {"status": "ready"}


async def check_database() -> bool:
    try:
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except:
        return False
```

### Stateless Design Principles

```python
from fastapi import FastAPI, Depends, Request
import redis.asyncio as redis
import json

app = FastAPI()

# BAD: In-memory state (not scalable)
user_sessions_bad = {}  # Lost when instance restarts

@app.post("/login-bad")
async def login_bad(username: str):
    session_id = create_session_id()
    user_sessions_bad[session_id] = {"username": username}  # BAD!
    return {"session_id": session_id}


# GOOD: External session store (Redis)
@app.post("/login-good")
async def login_good(
    username: str,
    r: redis.Redis = Depends(get_redis)
):
    session_id = create_session_id()
    await r.setex(
        f"session:{session_id}",
        3600,  # 1 hour TTL
        json.dumps({"username": username})
    )
    return {"session_id": session_id}


# GOOD: JWT tokens (stateless authentication)
@app.post("/login-jwt")
async def login_jwt(username: str):
    token = create_jwt_token({"sub": username})
    return {"access_token": token}


# BAD: File uploads stored locally
@app.post("/upload-bad")
async def upload_bad(file: UploadFile):
    path = f"/uploads/{file.filename}"  # BAD: Local storage
    with open(path, "wb") as f:
        f.write(await file.read())
    return {"path": path}


# GOOD: File uploads to S3/object storage
import boto3

@app.post("/upload-good")
async def upload_good(file: UploadFile):
    s3 = boto3.client("s3")
    key = f"uploads/{uuid.uuid4()}/{file.filename}"

    s3.upload_fileobj(
        file.file,
        "my-bucket",
        key
    )

    return {"url": f"https://my-bucket.s3.amazonaws.com/{key}"}


# BAD: Scheduled tasks in-process
import threading

def run_scheduler_bad():
    # BAD: Only runs on one instance
    while True:
        cleanup_old_data()
        time.sleep(3600)

threading.Thread(target=run_scheduler_bad).start()


# GOOD: Distributed task queue (Celery/ARQ)
from celery import Celery

celery_app = Celery("tasks", broker="redis://localhost:6379")

@celery_app.task
def cleanup_old_data():
    # Runs on any worker
    pass

# Schedule with celery beat (separate process)


# Request-scoped state
class RequestState:
    def __init__(self):
        self.user_id: Optional[int] = None
        self.request_id: str = ""
        self.start_time: float = 0

@app.middleware("http")
async def request_state_middleware(request: Request, call_next):
    # Initialize per-request state
    request.state.custom = RequestState()
    request.state.custom.request_id = str(uuid.uuid4())
    request.state.custom.start_time = time.time()

    response = await call_next(request)

    # State is discarded after request
    return response


# Idempotency for safe retries
@app.post("/orders")
async def create_order(
    order: OrderCreate,
    idempotency_key: str = Header(...),
    r: redis.Redis = Depends(get_redis)
):
    # Check if already processed
    existing = await r.get(f"idempotency:{idempotency_key}")
    if existing:
        return json.loads(existing)

    # Process order
    result = await process_order(order)

    # Store result for idempotency
    await r.setex(
        f"idempotency:{idempotency_key}",
        86400,  # 24 hours
        json.dumps(result)
    )

    return result
```

---

## Summary

Module 6 covered performance optimization strategies:

1. **Caching Strategies** - In-memory caching (LRU, TTL), Redis integration, cache invalidation patterns, response caching, and cache headers

2. **Performance Tuning** - Async vs sync decisions, database query optimization, connection pool tuning, payload compression, lazy loading, and profiling

3. **Scaling Considerations** - Gunicorn/Uvicorn worker configuration, horizontal scaling patterns, and stateless design principles

These optimizations ensure your FastAPI application can handle high loads efficiently and scale horizontally.

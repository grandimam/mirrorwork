# Module 10: Mastery Topics

## 10.1 Advanced Async Patterns

### Understanding the Event Loop

```python
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator
import logging

from fastapi import FastAPI, Request
from starlette.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)


# Accessing the event loop
async def get_event_loop_info():
    """Get information about the current event loop."""
    loop = asyncio.get_running_loop()
    return {
        "running": loop.is_running(),
        "closed": loop.is_closed(),
        "debug": loop.get_debug(),
        "time": loop.time(),
    }


# Custom event loop policy for production
class ProductionEventLoopPolicy(asyncio.DefaultEventLoopPolicy):
    """Custom event loop policy with production settings."""

    def new_event_loop(self):
        loop = super().new_event_loop()
        # Disable debug mode in production
        loop.set_debug(False)
        # Set custom exception handler
        loop.set_exception_handler(self._exception_handler)
        return loop

    def _exception_handler(self, loop, context):
        exception = context.get("exception")
        message = context.get("message", "Unhandled exception")
        logger.error(
            f"Event loop exception: {message}",
            exc_info=exception,
            extra={"context": context}
        )


# Apply custom policy (do this before creating the app)
# asyncio.set_event_loop_policy(ProductionEventLoopPolicy())
```

### Managing Connection Pools

```python
import asyncio
from contextlib import asynccontextmanager
from typing import Any
import aiohttp
import asyncpg
from redis import asyncio as aioredis

from fastapi import FastAPI, Depends, Request


class ConnectionPools:
    """Centralized connection pool management."""

    def __init__(self):
        self.db_pool: asyncpg.Pool | None = None
        self.redis_pool: aioredis.Redis | None = None
        self.http_session: aiohttp.ClientSession | None = None
        self._initialized = False

    async def initialize(
        self,
        database_url: str,
        redis_url: str,
        db_min_size: int = 10,
        db_max_size: int = 50,
    ):
        """Initialize all connection pools."""
        if self._initialized:
            return

        # Database pool with health checks
        self.db_pool = await asyncpg.create_pool(
            database_url,
            min_size=db_min_size,
            max_size=db_max_size,
            max_inactive_connection_lifetime=300,
            command_timeout=60,
            setup=self._setup_connection,
        )

        # Redis pool
        self.redis_pool = await aioredis.from_url(
            redis_url,
            max_connections=20,
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
        )

        # HTTP client session with connection pooling
        connector = aiohttp.TCPConnector(
            limit=100,  # Total connection limit
            limit_per_host=30,  # Per-host limit
            ttl_dns_cache=300,  # DNS cache TTL
            enable_cleanup_closed=True,
        )
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        self.http_session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
        )

        self._initialized = True

    async def _setup_connection(self, connection: asyncpg.Connection):
        """Setup each new database connection."""
        # Set session parameters
        await connection.execute("SET timezone = 'UTC'")
        await connection.execute("SET statement_timeout = '30s'")

    async def close(self):
        """Close all connection pools gracefully."""
        if self.http_session:
            await self.http_session.close()

        if self.redis_pool:
            await self.redis_pool.close()

        if self.db_pool:
            await self.db_pool.close()

        self._initialized = False

    async def health_check(self) -> dict[str, bool]:
        """Check health of all connections."""
        results = {}

        # Database health
        try:
            async with self.db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            results["database"] = True
        except Exception:
            results["database"] = False

        # Redis health
        try:
            await self.redis_pool.ping()
            results["redis"] = True
        except Exception:
            results["redis"] = False

        # HTTP client health (check if session is open)
        results["http_client"] = (
            self.http_session is not None
            and not self.http_session.closed
        )

        return results


# Global pools instance
pools = ConnectionPools()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan with connection pool management."""
    # Initialize pools
    await pools.initialize(
        database_url="postgresql://user:pass@localhost/db",
        redis_url="redis://localhost:6379",
    )

    yield {"pools": pools}

    # Cleanup pools
    await pools.close()


app = FastAPI(lifespan=lifespan)


# Dependencies to access pools
async def get_db(request: Request) -> asyncpg.Pool:
    return request.state.pools.db_pool


async def get_redis(request: Request) -> aioredis.Redis:
    return request.state.pools.redis_pool


async def get_http_client(request: Request) -> aiohttp.ClientSession:
    return request.state.pools.http_session
```

### Semaphores and Concurrency Control

```python
import asyncio
from functools import wraps
from typing import Callable, TypeVar, ParamSpec
from collections import defaultdict

from fastapi import FastAPI, HTTPException, Request, Depends

P = ParamSpec("P")
T = TypeVar("T")


class ConcurrencyLimiter:
    """
    Limit concurrent execution of async functions.
    Prevents overwhelming external services or database.
    """

    def __init__(self, max_concurrent: int = 10):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.active_count = 0
        self.waiting_count = 0

    @property
    def stats(self) -> dict:
        return {
            "active": self.active_count,
            "waiting": self.waiting_count,
            "available": self.semaphore._value,
        }

    async def __aenter__(self):
        self.waiting_count += 1
        await self.semaphore.acquire()
        self.waiting_count -= 1
        self.active_count += 1
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.active_count -= 1
        self.semaphore.release()
        return False


class KeyedSemaphore:
    """
    Per-key semaphore for resource-specific concurrency control.
    Useful for limiting concurrent operations per user/tenant/resource.
    """

    def __init__(self, max_per_key: int = 5):
        self.max_per_key = max_per_key
        self._semaphores: dict[str, asyncio.Semaphore] = defaultdict(
            lambda: asyncio.Semaphore(self.max_per_key)
        )
        self._locks = defaultdict(asyncio.Lock)

    async def acquire(self, key: str) -> bool:
        """Acquire semaphore for a specific key."""
        semaphore = self._semaphores[key]
        return await semaphore.acquire()

    def release(self, key: str):
        """Release semaphore for a specific key."""
        if key in self._semaphores:
            self._semaphores[key].release()

    @asynccontextmanager
    async def limit(self, key: str):
        """Context manager for limiting by key."""
        await self.acquire(key)
        try:
            yield
        finally:
            self.release(key)


# Global limiters
external_api_limiter = ConcurrencyLimiter(max_concurrent=20)
user_operation_limiter = KeyedSemaphore(max_per_key=3)


def limit_concurrency(limiter: ConcurrencyLimiter):
    """Decorator to limit concurrent executions."""
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            async with limiter:
                return await func(*args, **kwargs)
        return wrapper
    return decorator


# Usage in endpoints
@app.get("/external-data")
@limit_concurrency(external_api_limiter)
async def fetch_external_data():
    """Endpoint with global concurrency limit."""
    # This will only allow 20 concurrent requests
    async with aiohttp.ClientSession() as session:
        async with session.get("https://api.example.com/data") as resp:
            return await resp.json()


@app.post("/user/{user_id}/heavy-operation")
async def user_heavy_operation(user_id: str):
    """Endpoint with per-user concurrency limit."""
    async with user_operation_limiter.limit(user_id):
        # Only 3 concurrent operations per user
        await asyncio.sleep(5)  # Simulate heavy work
        return {"status": "completed"}


# Bounded concurrency for batch operations
async def process_items_bounded(
    items: list[Any],
    processor: Callable[[Any], Any],
    max_concurrent: int = 10,
) -> list[Any]:
    """
    Process items with bounded concurrency.
    Prevents spawning too many concurrent tasks.
    """
    semaphore = asyncio.Semaphore(max_concurrent)

    async def bounded_process(item: Any) -> Any:
        async with semaphore:
            return await processor(item)

    tasks = [bounded_process(item) for item in items]
    return await asyncio.gather(*tasks)


# Rate-limited async generator
async def rate_limited_generator(
    items: list[Any],
    items_per_second: float = 10,
):
    """Generate items at a controlled rate."""
    interval = 1.0 / items_per_second

    for item in items:
        yield item
        await asyncio.sleep(interval)
```

### Graceful Shutdown

```python
import asyncio
import signal
from contextlib import asynccontextmanager
from typing import Set
import logging

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class GracefulShutdown:
    """Manage graceful shutdown of the application."""

    def __init__(self):
        self.is_shutting_down = False
        self.active_requests: Set[asyncio.Task] = set()
        self.shutdown_event = asyncio.Event()
        self.request_timeout = 30  # Max time to wait for requests
        self.background_tasks: Set[asyncio.Task] = set()

    def start_shutdown(self):
        """Signal that shutdown has started."""
        logger.info("Graceful shutdown initiated")
        self.is_shutting_down = True
        self.shutdown_event.set()

    def register_request(self, task: asyncio.Task):
        """Register an active request."""
        self.active_requests.add(task)
        task.add_done_callback(self.active_requests.discard)

    def register_background_task(self, task: asyncio.Task):
        """Register a background task that should complete before shutdown."""
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)

    async def wait_for_completion(self):
        """Wait for all active requests and tasks to complete."""
        if self.active_requests:
            logger.info(
                f"Waiting for {len(self.active_requests)} active requests"
            )
            try:
                # Wait with timeout
                done, pending = await asyncio.wait(
                    self.active_requests,
                    timeout=self.request_timeout,
                )

                # Cancel any still-pending requests
                for task in pending:
                    logger.warning(f"Cancelling request: {task.get_name()}")
                    task.cancel()

            except Exception as e:
                logger.error(f"Error waiting for requests: {e}")

        # Wait for background tasks
        if self.background_tasks:
            logger.info(
                f"Waiting for {len(self.background_tasks)} background tasks"
            )
            try:
                await asyncio.wait(
                    self.background_tasks,
                    timeout=self.request_timeout,
                )
            except Exception as e:
                logger.error(f"Error waiting for background tasks: {e}")


shutdown_handler = GracefulShutdown()


class GracefulShutdownMiddleware(BaseHTTPMiddleware):
    """Middleware to track active requests and reject new ones during shutdown."""

    async def dispatch(self, request: Request, call_next):
        if shutdown_handler.is_shutting_down:
            # Return 503 during shutdown
            from starlette.responses import JSONResponse
            return JSONResponse(
                status_code=503,
                content={
                    "detail": "Service is shutting down",
                    "retry_after": 30,
                },
                headers={"Retry-After": "30"},
            )

        # Track this request
        current_task = asyncio.current_task()
        shutdown_handler.register_request(current_task)

        try:
            response = await call_next(request)
            return response
        finally:
            pass  # Cleanup handled by done callback


def setup_signal_handlers(app: FastAPI):
    """Setup signal handlers for graceful shutdown."""
    loop = asyncio.get_event_loop()

    def signal_handler(sig):
        logger.info(f"Received signal {sig.name}")
        shutdown_handler.start_shutdown()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: signal_handler(s))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan with graceful shutdown support."""
    # Setup
    setup_signal_handlers(app)

    yield

    # Shutdown
    shutdown_handler.start_shutdown()
    await shutdown_handler.wait_for_completion()
    logger.info("Graceful shutdown complete")


app = FastAPI(lifespan=lifespan)
app.add_middleware(GracefulShutdownMiddleware)


# Long-running endpoint example
@app.post("/long-operation")
async def long_operation():
    """Long operation that respects shutdown signals."""
    for i in range(100):
        if shutdown_handler.is_shutting_down:
            # Save state and return early
            return {"status": "interrupted", "progress": i}

        await asyncio.sleep(0.1)  # Simulate work

    return {"status": "completed"}


# Background task that respects shutdown
async def background_job():
    """Background job that checks for shutdown."""
    while not shutdown_handler.is_shutting_down:
        try:
            # Do work
            await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("Background job cancelled")
            break

    # Cleanup
    logger.info("Background job shutting down gracefully")
```

### Task Groups and Structured Concurrency

```python
import asyncio
from typing import Any
from contextlib import asynccontextmanager


class TaskGroup:
    """
    Structured concurrency with task groups.
    Python 3.11+ has asyncio.TaskGroup built-in.
    """

    def __init__(self):
        self.tasks: list[asyncio.Task] = []
        self.errors: list[Exception] = []

    def create_task(self, coro) -> asyncio.Task:
        """Create and track a task."""
        task = asyncio.create_task(coro)
        self.tasks.append(task)
        return task

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Wait for all tasks
        if self.tasks:
            results = await asyncio.gather(
                *self.tasks,
                return_exceptions=True,
            )

            # Collect errors
            for result in results:
                if isinstance(result, Exception):
                    self.errors.append(result)

        # Propagate first error if any
        if self.errors:
            raise ExceptionGroup("Task errors", self.errors)

        return False


# Python 3.11+ native task group usage
async def fetch_all_data():
    """Use native task groups for structured concurrency."""
    results = {}

    async with asyncio.TaskGroup() as tg:
        # All tasks in the group run concurrently
        # If any fails, all are cancelled

        async def fetch_users():
            results["users"] = await get_users()

        async def fetch_products():
            results["products"] = await get_products()

        async def fetch_orders():
            results["orders"] = await get_orders()

        tg.create_task(fetch_users())
        tg.create_task(fetch_products())
        tg.create_task(fetch_orders())

    return results


# Error handling with task groups
async def fetch_with_fallback():
    """Handle task group errors gracefully."""
    results = {}

    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(fetch_critical_data(results))
            tg.create_task(fetch_optional_data(results))

    except* ValueError as eg:
        # Handle specific error types (Python 3.11+)
        for exc in eg.exceptions:
            logger.warning(f"ValueError in task: {exc}")

    except* ConnectionError as eg:
        # Handle connection errors
        for exc in eg.exceptions:
            logger.error(f"Connection error: {exc}")
        raise  # Re-raise if critical

    return results


# Timeout wrapper for task groups
@asynccontextmanager
async def timeout_task_group(timeout: float):
    """Task group with timeout."""
    async with asyncio.timeout(timeout):
        async with asyncio.TaskGroup() as tg:
            yield tg
```

---

## 10.2 Multi-Tenancy

### Tenant Isolation Strategies

```python
from enum import Enum
from typing import Optional
from contextvars import ContextVar
from dataclasses import dataclass

from fastapi import FastAPI, Request, Depends, HTTPException
from sqlalchemy import event
from sqlalchemy.orm import Session


class TenantIsolationStrategy(Enum):
    """Different strategies for tenant isolation."""
    SHARED_DATABASE_SHARED_SCHEMA = "shared"  # Discriminator column
    SHARED_DATABASE_SEPARATE_SCHEMA = "schema"  # Schema per tenant
    SEPARATE_DATABASE = "database"  # Database per tenant


@dataclass
class Tenant:
    """Tenant information."""
    id: str
    name: str
    schema_name: Optional[str] = None
    database_url: Optional[str] = None
    isolation_strategy: TenantIsolationStrategy = (
        TenantIsolationStrategy.SHARED_DATABASE_SHARED_SCHEMA
    )
    settings: dict = None

    def __post_init__(self):
        self.settings = self.settings or {}


# Context variable for current tenant
current_tenant: ContextVar[Optional[Tenant]] = ContextVar(
    "current_tenant", default=None
)


class TenantRegistry:
    """Registry for tenant information."""

    def __init__(self):
        self._tenants: dict[str, Tenant] = {}

    def register(self, tenant: Tenant):
        """Register a tenant."""
        self._tenants[tenant.id] = tenant

    def get(self, tenant_id: str) -> Optional[Tenant]:
        """Get tenant by ID."""
        return self._tenants.get(tenant_id)

    async def get_by_domain(self, domain: str) -> Optional[Tenant]:
        """Get tenant by domain (for subdomain-based routing)."""
        # In production, query from database
        for tenant in self._tenants.values():
            if tenant.settings.get("domain") == domain:
                return tenant
        return None


tenant_registry = TenantRegistry()


# Initialize some tenants
tenant_registry.register(Tenant(
    id="tenant-a",
    name="Tenant A",
    schema_name="tenant_a",
    settings={"domain": "tenant-a.example.com"},
))
tenant_registry.register(Tenant(
    id="tenant-b",
    name="Tenant B",
    schema_name="tenant_b",
    settings={"domain": "tenant-b.example.com"},
))
```

### Tenant Identification Middleware

```python
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware


class TenantMiddleware(BaseHTTPMiddleware):
    """Middleware to identify and set current tenant."""

    async def dispatch(self, request: Request, call_next):
        tenant = await self._identify_tenant(request)

        if tenant is None:
            return JSONResponse(
                status_code=404,
                content={"detail": "Tenant not found"},
            )

        # Set tenant in context
        token = current_tenant.set(tenant)

        # Store in request state for easy access
        request.state.tenant = tenant

        try:
            response = await call_next(request)
            return response
        finally:
            current_tenant.reset(token)

    async def _identify_tenant(self, request: Request) -> Optional[Tenant]:
        """
        Identify tenant from request.
        Can use: subdomain, header, path prefix, or JWT claim.
        """
        # Strategy 1: Header-based
        tenant_id = request.headers.get("X-Tenant-ID")
        if tenant_id:
            return tenant_registry.get(tenant_id)

        # Strategy 2: Subdomain-based
        host = request.headers.get("host", "")
        if "." in host:
            subdomain = host.split(".")[0]
            tenant = tenant_registry.get(subdomain)
            if tenant:
                return tenant

        # Strategy 3: Path prefix (e.g., /api/tenant-a/...)
        path = request.url.path
        if path.startswith("/api/"):
            parts = path.split("/")
            if len(parts) >= 3:
                tenant = tenant_registry.get(parts[2])
                if tenant:
                    return tenant

        # Strategy 4: JWT claim (if authenticated)
        # Check after auth middleware runs
        if hasattr(request.state, "user"):
            tenant_id = request.state.user.tenant_id
            return tenant_registry.get(tenant_id)

        return None


app = FastAPI()
app.add_middleware(TenantMiddleware)


# Dependency to get current tenant
def get_tenant(request: Request) -> Tenant:
    """Get current tenant from request."""
    tenant = current_tenant.get()
    if not tenant:
        raise HTTPException(status_code=400, detail="Tenant not identified")
    return tenant
```

### Shared Database with Discriminator Column

```python
from sqlalchemy import Column, String, ForeignKey, event
from sqlalchemy.orm import Session, Query, declared_attr
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class TenantMixin:
    """Mixin that adds tenant_id to models."""

    @declared_attr
    def tenant_id(cls):
        return Column(String(50), index=True, nullable=False)


class User(TenantMixin, Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    email = Column(String, nullable=False)
    name = Column(String)

    # Composite index for tenant queries
    __table_args__ = (
        Index("ix_users_tenant_email", "tenant_id", "email", unique=True),
    )


class Product(TenantMixin, Base):
    __tablename__ = "products"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    price = Column(Numeric(10, 2))


# Automatic tenant filtering
class TenantQuery(Query):
    """Query class that automatically filters by tenant."""

    def __init__(self, entities, session=None):
        super().__init__(entities, session)
        self._add_tenant_filter()

    def _add_tenant_filter(self):
        tenant = current_tenant.get()
        if tenant and hasattr(self.column_descriptions[0]["entity"], "tenant_id"):
            self._criterion = self._criterion & (
                self.column_descriptions[0]["entity"].tenant_id == tenant.id
            )


class TenantSession(Session):
    """Session that uses tenant-aware queries."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._query_cls = TenantQuery


# SQLAlchemy event listeners for automatic tenant assignment
@event.listens_for(Session, "before_flush")
def set_tenant_id(session, flush_context, instances):
    """Automatically set tenant_id on new objects."""
    tenant = current_tenant.get()
    if not tenant:
        return

    for obj in session.new:
        if hasattr(obj, "tenant_id") and obj.tenant_id is None:
            obj.tenant_id = tenant.id


# Prevent cross-tenant data access
@event.listens_for(Session, "before_flush")
def validate_tenant_access(session, flush_context, instances):
    """Validate that modifications are within tenant scope."""
    tenant = current_tenant.get()
    if not tenant:
        return

    for obj in session.dirty | session.deleted:
        if hasattr(obj, "tenant_id"):
            if obj.tenant_id != tenant.id:
                raise ValueError(
                    f"Cannot modify object from different tenant: {obj}"
                )
```

### Schema-per-Tenant Pattern

```python
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool


class SchemaBasedTenantManager:
    """Manage separate schemas for each tenant."""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine = create_engine(
            database_url,
            poolclass=QueuePool,
            pool_size=10,
            max_overflow=20,
        )

    async def create_tenant_schema(self, tenant: Tenant):
        """Create schema for a new tenant."""
        schema_name = tenant.schema_name

        with self.engine.connect() as conn:
            # Create schema
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_name}"))

            # Create tables in the schema
            # You could also use Alembic with schema-aware migrations
            conn.execute(text(f"""
                CREATE TABLE IF NOT EXISTS {schema_name}.users (
                    id VARCHAR PRIMARY KEY,
                    email VARCHAR NOT NULL UNIQUE,
                    name VARCHAR
                )
            """))

            conn.execute(text(f"""
                CREATE TABLE IF NOT EXISTS {schema_name}.products (
                    id VARCHAR PRIMARY KEY,
                    name VARCHAR NOT NULL,
                    price DECIMAL(10, 2)
                )
            """))

            conn.commit()

    def get_session(self, tenant: Tenant) -> Session:
        """Get session configured for tenant's schema."""
        # Create session with search_path set
        session = sessionmaker(bind=self.engine)()

        # Set search path to tenant's schema
        session.execute(
            text(f"SET search_path TO {tenant.schema_name}, public")
        )

        return session


# Dependency for schema-based sessions
def get_tenant_session(
    tenant: Tenant = Depends(get_tenant),
) -> Session:
    """Get database session for current tenant's schema."""
    manager = SchemaBasedTenantManager(settings.database_url)
    session = manager.get_session(tenant)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
```

### Database-per-Tenant Pattern

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from typing import Dict


class DatabasePerTenantManager:
    """Manage separate databases for each tenant."""

    def __init__(self):
        self._engines: Dict[str, Engine] = {}
        self._session_factories: Dict[str, sessionmaker] = {}

    def get_engine(self, tenant: Tenant) -> Engine:
        """Get or create engine for tenant."""
        if tenant.id not in self._engines:
            self._engines[tenant.id] = create_engine(
                tenant.database_url,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True,
            )
        return self._engines[tenant.id]

    def get_session(self, tenant: Tenant) -> Session:
        """Get session for tenant's database."""
        if tenant.id not in self._session_factories:
            engine = self.get_engine(tenant)
            self._session_factories[tenant.id] = sessionmaker(bind=engine)

        return self._session_factories[tenant.id]()

    async def create_tenant_database(self, tenant: Tenant):
        """Create a new database for tenant."""
        # Connect to admin database
        admin_engine = create_engine(settings.admin_database_url)

        with admin_engine.connect() as conn:
            # PostgreSQL requires autocommit for CREATE DATABASE
            conn.execution_options(isolation_level="AUTOCOMMIT")

            db_name = f"tenant_{tenant.id}"
            conn.execute(text(f"CREATE DATABASE {db_name}"))

        # Update tenant with database URL
        tenant.database_url = (
            f"postgresql://user:pass@localhost/{db_name}"
        )

        # Run migrations on new database
        await self._run_migrations(tenant)

    async def _run_migrations(self, tenant: Tenant):
        """Run migrations on tenant database."""
        from alembic import command
        from alembic.config import Config

        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", tenant.database_url)
        command.upgrade(alembic_cfg, "head")


db_manager = DatabasePerTenantManager()


# FastAPI dependency
def get_tenant_db(tenant: Tenant = Depends(get_tenant)) -> Session:
    """Get database session for current tenant."""
    session = db_manager.get_session(tenant)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
```

### Tenant-Aware Caching

```python
from functools import wraps
from typing import Callable
import hashlib
import json

from redis import asyncio as aioredis


class TenantAwareCache:
    """Cache with tenant isolation."""

    def __init__(self, redis: aioredis.Redis):
        self.redis = redis

    def _make_key(self, tenant_id: str, key: str) -> str:
        """Create tenant-namespaced cache key."""
        return f"tenant:{tenant_id}:{key}"

    async def get(self, key: str, tenant: Tenant = None) -> Optional[Any]:
        """Get value from tenant-isolated cache."""
        tenant = tenant or current_tenant.get()
        if not tenant:
            raise ValueError("No tenant context")

        full_key = self._make_key(tenant.id, key)
        value = await self.redis.get(full_key)

        if value:
            return json.loads(value)
        return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int = 3600,
        tenant: Tenant = None,
    ):
        """Set value in tenant-isolated cache."""
        tenant = tenant or current_tenant.get()
        if not tenant:
            raise ValueError("No tenant context")

        full_key = self._make_key(tenant.id, key)
        await self.redis.set(
            full_key,
            json.dumps(value),
            ex=ttl,
        )

    async def delete(self, key: str, tenant: Tenant = None):
        """Delete from tenant-isolated cache."""
        tenant = tenant or current_tenant.get()
        if not tenant:
            raise ValueError("No tenant context")

        full_key = self._make_key(tenant.id, key)
        await self.redis.delete(full_key)

    async def clear_tenant_cache(self, tenant: Tenant):
        """Clear all cache entries for a tenant."""
        pattern = f"tenant:{tenant.id}:*"

        async for key in self.redis.scan_iter(match=pattern):
            await self.redis.delete(key)


def tenant_cached(ttl: int = 3600):
    """Decorator for tenant-aware caching."""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            tenant = current_tenant.get()
            if not tenant:
                return await func(*args, **kwargs)

            # Create cache key from function name and arguments
            key_data = {
                "func": func.__name__,
                "args": str(args),
                "kwargs": str(sorted(kwargs.items())),
            }
            key = hashlib.md5(
                json.dumps(key_data).encode()
            ).hexdigest()

            cache = TenantAwareCache(get_redis())

            # Try cache
            cached = await cache.get(key)
            if cached is not None:
                return cached

            # Call function
            result = await func(*args, **kwargs)

            # Cache result
            await cache.set(key, result, ttl=ttl)

            return result

        return wrapper
    return decorator


# Usage
@tenant_cached(ttl=300)
async def get_tenant_settings():
    """Get settings for current tenant (cached per tenant)."""
    tenant = current_tenant.get()
    # Fetch from database
    return {"theme": "dark", "features": ["a", "b"]}
```

---

## 10.3 Advanced Security

### OAuth2 with External Providers

```python
from authlib.integrations.starlette_client import OAuth
from starlette.config import Config
from fastapi import FastAPI, Request, Depends
from fastapi.responses import RedirectResponse
import secrets

config = Config(".env")
oauth = OAuth(config)

# Register OAuth providers
oauth.register(
    name="google",
    client_id=config("GOOGLE_CLIENT_ID"),
    client_secret=config("GOOGLE_CLIENT_SECRET"),
    server_metadata_url=(
        "https://accounts.google.com/.well-known/openid-configuration"
    ),
    client_kwargs={"scope": "openid email profile"},
)

oauth.register(
    name="github",
    client_id=config("GITHUB_CLIENT_ID"),
    client_secret=config("GITHUB_CLIENT_SECRET"),
    access_token_url="https://github.com/login/oauth/access_token",
    authorize_url="https://github.com/login/oauth/authorize",
    api_base_url="https://api.github.com/",
    client_kwargs={"scope": "user:email"},
)

oauth.register(
    name="microsoft",
    client_id=config("AZURE_CLIENT_ID"),
    client_secret=config("AZURE_CLIENT_SECRET"),
    server_metadata_url=(
        "https://login.microsoftonline.com/common/v2.0/"
        ".well-known/openid-configuration"
    ),
    client_kwargs={"scope": "openid email profile"},
)


app = FastAPI()


# Session middleware for OAuth state
from starlette.middleware.sessions import SessionMiddleware
app.add_middleware(
    SessionMiddleware,
    secret_key=config("SESSION_SECRET"),
    max_age=3600,
)


@app.get("/auth/{provider}/login")
async def oauth_login(request: Request, provider: str):
    """Initiate OAuth login flow."""
    if provider not in ["google", "github", "microsoft"]:
        raise HTTPException(status_code=400, detail="Unknown provider")

    client = oauth.create_client(provider)
    redirect_uri = request.url_for("oauth_callback", provider=provider)

    # Generate and store state for CSRF protection
    state = secrets.token_urlsafe(32)
    request.session["oauth_state"] = state

    return await client.authorize_redirect(
        request,
        redirect_uri,
        state=state,
    )


@app.get("/auth/{provider}/callback")
async def oauth_callback(request: Request, provider: str):
    """Handle OAuth callback."""
    client = oauth.create_client(provider)

    # Verify state
    state = request.query_params.get("state")
    stored_state = request.session.get("oauth_state")

    if not state or state != stored_state:
        raise HTTPException(status_code=400, detail="Invalid state")

    # Clear state
    del request.session["oauth_state"]

    # Exchange code for token
    token = await client.authorize_access_token(request)

    # Get user info based on provider
    if provider == "google":
        user_info = token.get("userinfo")
        if not user_info:
            user_info = await client.parse_id_token(request, token)
    elif provider == "github":
        resp = await client.get("user", token=token)
        user_info = resp.json()
        # Get primary email
        emails_resp = await client.get("user/emails", token=token)
        emails = emails_resp.json()
        primary_email = next(
            (e["email"] for e in emails if e["primary"]),
            None
        )
        user_info["email"] = primary_email
    else:
        user_info = token.get("userinfo")

    # Create or update user in database
    user = await create_or_update_user_from_oauth(
        provider=provider,
        provider_user_id=str(user_info.get("sub") or user_info.get("id")),
        email=user_info.get("email"),
        name=user_info.get("name"),
    )

    # Create session/JWT for the user
    access_token = create_access_token(user)

    # Redirect to frontend with token
    frontend_url = config("FRONTEND_URL")
    return RedirectResponse(
        f"{frontend_url}/auth/callback?token={access_token}"
    )


async def create_or_update_user_from_oauth(
    provider: str,
    provider_user_id: str,
    email: str,
    name: str,
) -> User:
    """Create or update user from OAuth data."""
    # Check for existing OAuth link
    oauth_account = await db.oauth_accounts.find_one({
        "provider": provider,
        "provider_user_id": provider_user_id,
    })

    if oauth_account:
        # Update existing user
        user = await db.users.find_one({"_id": oauth_account["user_id"]})
        return user

    # Check for existing user by email
    user = await db.users.find_one({"email": email})

    if not user:
        # Create new user
        user = await db.users.insert_one({
            "email": email,
            "name": name,
            "created_at": datetime.utcnow(),
        })
        user = await db.users.find_one({"_id": user.inserted_id})

    # Link OAuth account
    await db.oauth_accounts.insert_one({
        "user_id": user["_id"],
        "provider": provider,
        "provider_user_id": provider_user_id,
    })

    return user
```

### OpenID Connect Implementation

```python
from jose import jwt, JWTError
import httpx
from typing import Optional
from pydantic import BaseModel
from cachetools import TTLCache


class OpenIDConfig(BaseModel):
    """OpenID Connect configuration."""
    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    userinfo_endpoint: str
    jwks_uri: str
    scopes_supported: list[str]
    response_types_supported: list[str]
    claims_supported: list[str]


class OpenIDConnectValidator:
    """Validate OpenID Connect tokens."""

    def __init__(self):
        self._config_cache: TTLCache = TTLCache(maxsize=10, ttl=3600)
        self._jwks_cache: TTLCache = TTLCache(maxsize=10, ttl=3600)

    async def get_openid_config(self, issuer: str) -> OpenIDConfig:
        """Fetch OpenID configuration from well-known endpoint."""
        if issuer in self._config_cache:
            return self._config_cache[issuer]

        config_url = f"{issuer}/.well-known/openid-configuration"

        async with httpx.AsyncClient() as client:
            response = await client.get(config_url)
            response.raise_for_status()
            config = OpenIDConfig(**response.json())

        self._config_cache[issuer] = config
        return config

    async def get_jwks(self, jwks_uri: str) -> dict:
        """Fetch JSON Web Key Set."""
        if jwks_uri in self._jwks_cache:
            return self._jwks_cache[jwks_uri]

        async with httpx.AsyncClient() as client:
            response = await client.get(jwks_uri)
            response.raise_for_status()
            jwks = response.json()

        self._jwks_cache[jwks_uri] = jwks
        return jwks

    async def validate_id_token(
        self,
        token: str,
        issuer: str,
        client_id: str,
        nonce: Optional[str] = None,
    ) -> dict:
        """
        Validate an OpenID Connect ID token.
        """
        # Get configuration and keys
        config = await self.get_openid_config(issuer)
        jwks = await self.get_jwks(config.jwks_uri)

        # Decode header to get key ID
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")

        # Find the signing key
        signing_key = None
        for key in jwks.get("keys", []):
            if key.get("kid") == kid:
                signing_key = key
                break

        if not signing_key:
            raise ValueError("Signing key not found in JWKS")

        # Validate token
        try:
            payload = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256", "RS384", "RS512"],
                audience=client_id,
                issuer=issuer,
            )
        except JWTError as e:
            raise ValueError(f"Token validation failed: {e}")

        # Validate nonce if provided
        if nonce and payload.get("nonce") != nonce:
            raise ValueError("Invalid nonce")

        # Validate at_hash if access token present
        # (implementation depends on your needs)

        return payload


oidc_validator = OpenIDConnectValidator()


# FastAPI dependency for OIDC tokens
async def validate_oidc_token(
    authorization: str = Header(),
) -> dict:
    """Validate OIDC bearer token."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header",
        )

    token = authorization[7:]

    try:
        # Determine issuer from token (decode without verification first)
        unverified = jwt.get_unverified_claims(token)
        issuer = unverified.get("iss")

        if not issuer or issuer not in settings.ALLOWED_ISSUERS:
            raise HTTPException(
                status_code=401,
                detail="Unknown or untrusted issuer",
            )

        # Validate token
        claims = await oidc_validator.validate_id_token(
            token=token,
            issuer=issuer,
            client_id=settings.CLIENT_ID,
        )

        return claims

    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
```

### Advanced JWT Patterns

```python
from datetime import datetime, timedelta
from typing import Optional
import secrets
from jose import jwt, JWTError
from pydantic import BaseModel
from redis import asyncio as aioredis


class TokenPair(BaseModel):
    """Access and refresh token pair."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class JWTManager:
    """Advanced JWT management with security features."""

    def __init__(
        self,
        secret_key: str,
        algorithm: str = "HS256",
        access_token_expire_minutes: int = 15,
        refresh_token_expire_days: int = 7,
        redis: aioredis.Redis = None,
    ):
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.access_token_expire = timedelta(minutes=access_token_expire_minutes)
        self.refresh_token_expire = timedelta(days=refresh_token_expire_days)
        self.redis = redis

    def create_token_pair(
        self,
        user_id: str,
        additional_claims: dict = None,
    ) -> TokenPair:
        """Create access and refresh token pair."""
        now = datetime.utcnow()
        jti = secrets.token_urlsafe(32)  # Unique token ID

        # Access token claims
        access_claims = {
            "sub": user_id,
            "type": "access",
            "jti": jti,
            "iat": now,
            "exp": now + self.access_token_expire,
            **(additional_claims or {}),
        }

        access_token = jwt.encode(
            access_claims,
            self.secret_key,
            algorithm=self.algorithm,
        )

        # Refresh token claims (minimal)
        refresh_claims = {
            "sub": user_id,
            "type": "refresh",
            "jti": secrets.token_urlsafe(32),
            "access_jti": jti,  # Link to access token
            "iat": now,
            "exp": now + self.refresh_token_expire,
        }

        refresh_token = jwt.encode(
            refresh_claims,
            self.secret_key,
            algorithm=self.algorithm,
        )

        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=int(self.access_token_expire.total_seconds()),
        )

    async def refresh_tokens(
        self,
        refresh_token: str,
        additional_claims: dict = None,
    ) -> TokenPair:
        """
        Refresh token pair with rotation.
        Old refresh token becomes invalid after use.
        """
        try:
            payload = jwt.decode(
                refresh_token,
                self.secret_key,
                algorithms=[self.algorithm],
            )
        except JWTError:
            raise ValueError("Invalid refresh token")

        if payload.get("type") != "refresh":
            raise ValueError("Not a refresh token")

        # Check if token is revoked
        if self.redis:
            is_revoked = await self.redis.get(
                f"revoked:refresh:{payload['jti']}"
            )
            if is_revoked:
                # Possible token reuse attack
                # Revoke all user tokens
                await self.revoke_all_user_tokens(payload["sub"])
                raise ValueError("Token reuse detected")

            # Revoke old refresh token
            await self.redis.set(
                f"revoked:refresh:{payload['jti']}",
                "1",
                ex=int(self.refresh_token_expire.total_seconds()),
            )

            # Also revoke the old access token
            if payload.get("access_jti"):
                await self.redis.set(
                    f"revoked:access:{payload['access_jti']}",
                    "1",
                    ex=int(self.access_token_expire.total_seconds()),
                )

        # Create new token pair
        return self.create_token_pair(
            user_id=payload["sub"],
            additional_claims=additional_claims,
        )

    async def verify_access_token(self, token: str) -> dict:
        """Verify access token and check revocation."""
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
            )
        except JWTError as e:
            raise ValueError(f"Invalid token: {e}")

        if payload.get("type") != "access":
            raise ValueError("Not an access token")

        # Check revocation
        if self.redis:
            is_revoked = await self.redis.get(
                f"revoked:access:{payload['jti']}"
            )
            if is_revoked:
                raise ValueError("Token has been revoked")

        return payload

    async def revoke_token(self, token: str):
        """Revoke a specific token."""
        if not self.redis:
            return

        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                options={"verify_exp": False},  # Allow revoking expired tokens
            )
        except JWTError:
            return

        token_type = payload.get("type", "access")
        ttl = (
            self.refresh_token_expire
            if token_type == "refresh"
            else self.access_token_expire
        )

        await self.redis.set(
            f"revoked:{token_type}:{payload['jti']}",
            "1",
            ex=int(ttl.total_seconds()),
        )

    async def revoke_all_user_tokens(self, user_id: str):
        """Revoke all tokens for a user."""
        if not self.redis:
            return

        # Store a "revoked before" timestamp
        await self.redis.set(
            f"user:revoked_before:{user_id}",
            datetime.utcnow().isoformat(),
            ex=int(self.refresh_token_expire.total_seconds()),
        )


jwt_manager = JWTManager(
    secret_key=settings.SECRET_KEY,
    redis=redis_client,
)
```

### Security Headers and HTTPS

```python
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # XSS protection
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Content Security Policy
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self'; "
            "connect-src 'self' https://api.example.com; "
            "frame-ancestors 'none';"
        )

        # HTTPS enforcement
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; preload"
        )

        # Referrer policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions policy
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), "
            "camera=(), "
            "geolocation=(), "
            "gyroscope=(), "
            "magnetometer=(), "
            "microphone=(), "
            "payment=(), "
            "usb=()"
        )

        return response


class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
    """Redirect HTTP to HTTPS in production."""

    async def dispatch(self, request: Request, call_next):
        # Check if behind a proxy
        forwarded_proto = request.headers.get("X-Forwarded-Proto")

        if forwarded_proto == "http":
            url = request.url.replace(scheme="https")
            return Response(
                status_code=301,
                headers={"Location": str(url)},
            )

        return await call_next(request)


app = FastAPI()

if settings.ENVIRONMENT == "production":
    app.add_middleware(HTTPSRedirectMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
```

### Input Validation and Sanitization

```python
import re
import html
from typing import Annotated
from pydantic import BaseModel, field_validator, BeforeValidator


def sanitize_html(value: str) -> str:
    """Remove HTML tags and escape special characters."""
    # Remove HTML tags
    clean = re.sub(r"<[^>]+>", "", value)
    # Escape HTML entities
    return html.escape(clean)


def sanitize_sql_identifier(value: str) -> str:
    """Sanitize SQL identifiers (table/column names)."""
    # Only allow alphanumeric and underscore
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", value):
        raise ValueError("Invalid SQL identifier")
    return value


def validate_no_script(value: str) -> str:
    """Validate that value doesn't contain script tags."""
    if re.search(r"<script", value, re.IGNORECASE):
        raise ValueError("Script tags not allowed")
    return value


# Annotated types for automatic validation
SafeString = Annotated[str, BeforeValidator(sanitize_html)]
SQLIdentifier = Annotated[str, BeforeValidator(sanitize_sql_identifier)]
NoScript = Annotated[str, BeforeValidator(validate_no_script)]


class UserInput(BaseModel):
    """Model with input sanitization."""

    # Automatically sanitized
    name: SafeString
    bio: SafeString

    # Custom validation
    email: str
    website: str | None = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Validate email format."""
        pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
        if not re.match(pattern, v):
            raise ValueError("Invalid email format")
        return v.lower()

    @field_validator("website")
    @classmethod
    def validate_website(cls, v: str | None) -> str | None:
        """Validate website URL."""
        if v is None:
            return None

        # Only allow http/https
        if not v.startswith(("http://", "https://")):
            raise ValueError("Website must start with http:// or https://")

        # Prevent SSRF by blocking internal URLs
        blocked_patterns = [
            r"localhost",
            r"127\.0\.0\.1",
            r"0\.0\.0\.0",
            r"10\.\d+\.\d+\.\d+",
            r"172\.(1[6-9]|2\d|3[01])\.\d+\.\d+",
            r"192\.168\.\d+\.\d+",
        ]

        for pattern in blocked_patterns:
            if re.search(pattern, v, re.IGNORECASE):
                raise ValueError("Internal URLs not allowed")

        return v


# Path traversal prevention
def safe_join_path(base_dir: str, filename: str) -> str:
    """Safely join paths preventing traversal attacks."""
    import os

    # Normalize and resolve
    base = os.path.realpath(base_dir)
    full_path = os.path.realpath(os.path.join(base, filename))

    # Ensure result is under base
    if not full_path.startswith(base):
        raise ValueError("Path traversal detected")

    return full_path
```

---

## 10.4 Debugging & Troubleshooting

### Debugging Async Code

```python
import asyncio
import sys
import traceback
from typing import Coroutine
import logging

logger = logging.getLogger(__name__)


# Enable asyncio debug mode
def enable_async_debug():
    """Enable asyncio debug mode for development."""
    loop = asyncio.get_event_loop()
    loop.set_debug(True)

    # Slow callback threshold (default is 0.1s)
    loop.slow_callback_duration = 0.05

    # Enable tracemalloc for better tracebacks
    import tracemalloc
    tracemalloc.start()


# Custom exception handler for event loop
def setup_exception_handler():
    """Setup global exception handler for asyncio."""
    loop = asyncio.get_event_loop()

    def handle_exception(loop, context):
        exception = context.get("exception")
        message = context.get("message", "Unhandled exception")

        # Log with full context
        logger.error(
            f"Async exception: {message}",
            exc_info=exception,
            extra={
                "future": context.get("future"),
                "handle": context.get("handle"),
                "protocol": context.get("protocol"),
                "transport": context.get("transport"),
                "socket": context.get("socket"),
            }
        )

        # Optionally, you can stop the loop on critical errors
        # loop.stop()

    loop.set_exception_handler(handle_exception)


# Debug decorator for coroutines
def debug_async(func):
    """Decorator to add debugging to async functions."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        func_name = f"{func.__module__}.{func.__name__}"
        logger.debug(f"Starting: {func_name}")

        try:
            start = asyncio.get_event_loop().time()
            result = await func(*args, **kwargs)
            duration = asyncio.get_event_loop().time() - start

            logger.debug(f"Completed: {func_name} ({duration:.3f}s)")
            return result

        except asyncio.CancelledError:
            logger.warning(f"Cancelled: {func_name}")
            raise

        except Exception as e:
            logger.error(
                f"Error in {func_name}: {e}",
                exc_info=True,
            )
            raise

    return wrapper


# Track pending tasks
class TaskTracker:
    """Track and debug pending async tasks."""

    def __init__(self):
        self.tasks: dict[str, asyncio.Task] = {}

    def create_task(
        self,
        coro: Coroutine,
        name: str = None,
    ) -> asyncio.Task:
        """Create and track a task."""
        task = asyncio.create_task(coro, name=name)
        task_id = f"{name or 'task'}_{id(task)}"

        self.tasks[task_id] = task

        # Add callback to remove when done
        task.add_done_callback(
            lambda t: self.tasks.pop(task_id, None)
        )

        return task

    def get_pending_tasks(self) -> list[dict]:
        """Get information about pending tasks."""
        pending = []

        for task_id, task in self.tasks.items():
            if not task.done():
                coro = task.get_coro()
                pending.append({
                    "id": task_id,
                    "name": task.get_name(),
                    "coro": coro.__qualname__,
                    "state": "pending" if not task.cancelled() else "cancelled",
                    "stack": "".join(traceback.format_stack(coro.cr_frame))
                    if coro.cr_frame else None,
                })

        return pending

    async def cancel_all(self, timeout: float = 5.0):
        """Cancel all tracked tasks."""
        for task in self.tasks.values():
            if not task.done():
                task.cancel()

        if self.tasks:
            await asyncio.wait(
                self.tasks.values(),
                timeout=timeout,
            )


task_tracker = TaskTracker()


# Debug endpoint
@app.get("/debug/tasks")
async def debug_tasks():
    """Show pending async tasks (development only)."""
    if not settings.DEBUG:
        raise HTTPException(status_code=404)

    all_tasks = asyncio.all_tasks()

    return {
        "tracked_tasks": task_tracker.get_pending_tasks(),
        "all_tasks": [
            {
                "name": t.get_name(),
                "done": t.done(),
                "cancelled": t.cancelled(),
            }
            for t in all_tasks
        ],
    }
```

### Memory Leak Detection

```python
import gc
import sys
import tracemalloc
from collections import defaultdict
from typing import Any
import objgraph

from fastapi import FastAPI, Request


class MemoryProfiler:
    """Memory profiling and leak detection."""

    def __init__(self):
        self.snapshots: list = []
        self.is_running = False

    def start(self):
        """Start memory tracking."""
        if not self.is_running:
            tracemalloc.start()
            self.is_running = True

    def stop(self):
        """Stop memory tracking."""
        if self.is_running:
            tracemalloc.stop()
            self.is_running = False

    def take_snapshot(self) -> dict:
        """Take a memory snapshot."""
        if not self.is_running:
            self.start()

        snapshot = tracemalloc.take_snapshot()
        self.snapshots.append(snapshot)

        # Get top allocations
        top_stats = snapshot.statistics("lineno")[:20]

        return {
            "top_allocations": [
                {
                    "file": str(stat.traceback),
                    "size_kb": stat.size / 1024,
                    "count": stat.count,
                }
                for stat in top_stats
            ],
            "total_mb": sum(s.size for s in top_stats) / (1024 * 1024),
        }

    def compare_snapshots(
        self,
        snapshot1_idx: int = -2,
        snapshot2_idx: int = -1,
    ) -> dict:
        """Compare two snapshots to find memory growth."""
        if len(self.snapshots) < 2:
            return {"error": "Need at least 2 snapshots"}

        old = self.snapshots[snapshot1_idx]
        new = self.snapshots[snapshot2_idx]

        diff = new.compare_to(old, "lineno")

        # Find biggest increases
        increases = [
            {
                "file": str(stat.traceback),
                "size_diff_kb": stat.size_diff / 1024,
                "count_diff": stat.count_diff,
            }
            for stat in diff[:20]
            if stat.size_diff > 0
        ]

        return {
            "increases": increases,
            "total_increase_kb": sum(i["size_diff_kb"] for i in increases),
        }

    def get_object_counts(self) -> dict:
        """Get counts of Python objects by type."""
        gc.collect()

        counts = defaultdict(int)
        for obj in gc.get_objects():
            counts[type(obj).__name__] += 1

        # Sort by count
        sorted_counts = sorted(
            counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:30]

        return dict(sorted_counts)

    def find_leaks(self, type_name: str) -> list[dict]:
        """Find potential memory leaks for a specific type."""
        gc.collect()

        # Find objects of the specified type
        objects = objgraph.by_type(type_name)

        leaks = []
        for obj in objects[:10]:  # Limit to prevent huge output
            # Get reference chain
            chain = objgraph.find_backref_chain(
                obj,
                objgraph.is_proper_module,
                max_depth=10,
            )

            leaks.append({
                "object": repr(obj)[:200],
                "refs": len(gc.get_referrers(obj)),
                "chain": [type(c).__name__ for c in chain],
            })

        return leaks


profiler = MemoryProfiler()


# Debug endpoints
@app.get("/debug/memory/snapshot")
async def memory_snapshot():
    """Take memory snapshot."""
    if not settings.DEBUG:
        raise HTTPException(status_code=404)
    return profiler.take_snapshot()


@app.get("/debug/memory/compare")
async def memory_compare():
    """Compare memory snapshots."""
    if not settings.DEBUG:
        raise HTTPException(status_code=404)
    return profiler.compare_snapshots()


@app.get("/debug/memory/objects")
async def memory_objects():
    """Get object counts by type."""
    if not settings.DEBUG:
        raise HTTPException(status_code=404)
    return profiler.get_object_counts()


@app.get("/debug/memory/gc")
async def memory_gc():
    """Run garbage collection and return stats."""
    if not settings.DEBUG:
        raise HTTPException(status_code=404)

    gc.collect()

    return {
        "garbage": len(gc.garbage),
        "counts": gc.get_count(),
        "threshold": gc.get_threshold(),
        "stats": gc.get_stats(),
    }
```

### Request/Response Debugging

```python
import json
import time
from uuid import uuid4
from contextvars import ContextVar

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

# Request context for debugging
request_context: ContextVar[dict] = ContextVar("request_context", default={})


class DebugMiddleware(BaseHTTPMiddleware):
    """Comprehensive debugging middleware."""

    async def dispatch(self, request: Request, call_next):
        if not settings.DEBUG:
            return await call_next(request)

        request_id = str(uuid4())
        start_time = time.perf_counter()

        # Build debug context
        context = {
            "request_id": request_id,
            "method": request.method,
            "url": str(request.url),
            "headers": dict(request.headers),
            "client": request.client.host if request.client else None,
            "start_time": time.time(),
        }

        # Try to capture body
        if request.method in ("POST", "PUT", "PATCH"):
            body = await request.body()
            try:
                context["body"] = json.loads(body)
            except json.JSONDecodeError:
                context["body"] = body.decode("utf-8", errors="replace")[:1000]

            # Reconstruct request with body
            async def receive():
                return {"type": "http.request", "body": body}
            request = Request(request.scope, receive)

        # Set context
        token = request_context.set(context)

        try:
            response = await call_next(request)

            # Capture response info
            duration = time.perf_counter() - start_time
            context["response"] = {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "duration_ms": round(duration * 1000, 2),
            }

            # Log debug info
            logger.debug(f"Request completed", extra=context)

            # Add debug headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time"] = f"{duration * 1000:.2f}ms"

            return response

        except Exception as e:
            context["error"] = {
                "type": type(e).__name__,
                "message": str(e),
                "traceback": traceback.format_exc(),
            }
            logger.error("Request failed", extra=context)
            raise

        finally:
            request_context.reset(token)


# Debug info in exceptions
class DebugHTTPException(HTTPException):
    """HTTP exception with debug information."""

    def __init__(
        self,
        status_code: int,
        detail: str,
        debug_info: dict = None,
    ):
        super().__init__(status_code=status_code, detail=detail)

        if settings.DEBUG and debug_info:
            self.detail = {
                "message": detail,
                "debug": debug_info,
                "request_id": request_context.get().get("request_id"),
            }


# SQL query debugging
from sqlalchemy import event
from sqlalchemy.engine import Engine


@event.listens_for(Engine, "before_cursor_execute")
def log_query(conn, cursor, statement, parameters, context, executemany):
    """Log SQL queries in debug mode."""
    if settings.DEBUG:
        context._query_start_time = time.perf_counter()
        logger.debug(
            f"SQL: {statement}",
            extra={
                "parameters": parameters,
                "request_id": request_context.get().get("request_id"),
            }
        )


@event.listens_for(Engine, "after_cursor_execute")
def log_query_time(conn, cursor, statement, parameters, context, executemany):
    """Log SQL query execution time."""
    if settings.DEBUG and hasattr(context, "_query_start_time"):
        duration = time.perf_counter() - context._query_start_time
        logger.debug(
            f"SQL completed in {duration * 1000:.2f}ms",
            extra={
                "duration_ms": duration * 1000,
                "request_id": request_context.get().get("request_id"),
            }
        )
```

### Performance Profiling

```python
import cProfile
import pstats
import io
from functools import wraps
import yappi  # For async profiling


class ProfilerManager:
    """Manage code profiling."""

    def __init__(self):
        self.cpu_profiler = None
        self.is_profiling = False

    def start_cpu_profiling(self):
        """Start CPU profiling."""
        if self.is_profiling:
            return

        # yappi supports async code
        yappi.start()
        self.is_profiling = True

    def stop_cpu_profiling(self) -> dict:
        """Stop CPU profiling and return results."""
        if not self.is_profiling:
            return {}

        yappi.stop()
        self.is_profiling = False

        # Get function statistics
        func_stats = yappi.get_func_stats()

        results = []
        for stat in func_stats[:50]:  # Top 50
            results.append({
                "name": stat.name,
                "module": stat.module,
                "calls": stat.ncall,
                "total_time": stat.ttot,
                "avg_time": stat.tavg,
                "builtin": stat.builtin,
            })

        yappi.clear_stats()

        return {
            "functions": results,
            "total_functions": len(func_stats),
        }

    def profile_function(self, func):
        """Decorator to profile a specific function."""
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            profiler = cProfile.Profile()
            profiler.enable()

            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                profiler.disable()

                # Print stats
                stream = io.StringIO()
                stats = pstats.Stats(profiler, stream=stream)
                stats.sort_stats("cumulative")
                stats.print_stats(20)

                logger.debug(f"Profile for {func.__name__}:\n{stream.getvalue()}")

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            profiler = cProfile.Profile()
            profiler.enable()

            try:
                result = func(*args, **kwargs)
                return result
            finally:
                profiler.disable()

                stream = io.StringIO()
                stats = pstats.Stats(profiler, stream=stream)
                stats.sort_stats("cumulative")
                stats.print_stats(20)

                logger.debug(f"Profile for {func.__name__}:\n{stream.getvalue()}")

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper


profiler_manager = ProfilerManager()


# Profiling endpoints
@app.post("/debug/profiler/start")
async def start_profiler():
    """Start CPU profiling."""
    if not settings.DEBUG:
        raise HTTPException(status_code=404)

    profiler_manager.start_cpu_profiling()
    return {"status": "profiling started"}


@app.post("/debug/profiler/stop")
async def stop_profiler():
    """Stop CPU profiling and get results."""
    if not settings.DEBUG:
        raise HTTPException(status_code=404)

    return profiler_manager.stop_cpu_profiling()


# Line profiler for detailed analysis
def line_profile(func):
    """Decorator for line-by-line profiling."""
    try:
        from line_profiler import LineProfiler
    except ImportError:
        return func

    profiler = LineProfiler()

    @wraps(func)
    def wrapper(*args, **kwargs):
        profiler.add_function(func)
        profiler.enable()

        try:
            result = func(*args, **kwargs)
            return result
        finally:
            profiler.disable()

            stream = io.StringIO()
            profiler.print_stats(stream=stream)
            logger.debug(f"Line profile:\n{stream.getvalue()}")

    return wrapper
```

### Troubleshooting Common Issues

```python
"""
Common FastAPI Issues and Solutions
"""

# Issue 1: Blocking the event loop
# Problem: Using sync I/O in async endpoints
# Solution: Use run_in_threadpool or async libraries

from starlette.concurrency import run_in_threadpool

# Bad - blocks event loop
@app.get("/bad")
async def bad_endpoint():
    import requests  # Sync library
    return requests.get("https://api.example.com").json()

# Good - runs in thread pool
@app.get("/good")
async def good_endpoint():
    import requests
    result = await run_in_threadpool(
        requests.get, "https://api.example.com"
    )
    return result.json()

# Better - use async library
@app.get("/better")
async def better_endpoint():
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.example.com")
        return response.json()


# Issue 2: Dependency lifecycle issues
# Problem: Resources not cleaned up properly
# Solution: Use proper context managers

# Bad - no cleanup
def get_db_bad():
    return Session()

# Good - with cleanup
def get_db_good():
    db = Session()
    try:
        yield db
    finally:
        db.close()


# Issue 3: Circular imports
# Problem: Dependencies create circular imports
# Solution: Use lazy imports or restructure

# In dependencies.py - avoid importing models at module level
def get_user_service():
    from app.services.user import UserService  # Lazy import
    return UserService()


# Issue 4: N+1 queries
# Problem: Fetching related objects in a loop
# Solution: Use eager loading

from sqlalchemy.orm import selectinload, joinedload

# Bad - N+1 queries
@app.get("/users-bad")
async def get_users_bad(db: Session = Depends(get_db)):
    users = db.query(User).all()
    for user in users:
        # Each access triggers a query
        _ = user.posts
    return users

# Good - eager loading
@app.get("/users-good")
async def get_users_good(db: Session = Depends(get_db)):
    users = db.query(User).options(
        selectinload(User.posts)  # Load all posts in one query
    ).all()
    return users


# Issue 5: Memory leaks from keeping references
# Problem: Global lists/dicts growing unbounded
# Solution: Use WeakRef or bounded collections

from weakref import WeakValueDictionary
from collections import deque

# Bad - unbounded growth
active_connections = []  # Never cleaned up

# Good - weak references
active_connections = WeakValueDictionary()

# Good - bounded collection
recent_requests = deque(maxlen=1000)


# Issue 6: Background tasks not completing
# Problem: Background tasks dropped on shutdown
# Solution: Use proper task tracking

@app.post("/task-safe")
async def create_task_safe(background_tasks: BackgroundTasks):
    # Track task completion
    async def tracked_task():
        try:
            await do_work()
        except Exception as e:
            logger.error(f"Background task failed: {e}")

    background_tasks.add_task(tracked_task)
    return {"status": "task queued"}


# Issue 7: WebSocket connection handling
# Problem: Connections not cleaned up on errors
# Solution: Use try/finally

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connection_manager.connect(websocket)

    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Echo: {data}")
    except WebSocketDisconnect:
        pass
    finally:
        # Always clean up
        connection_manager.disconnect(websocket)


# Debug utility function
async def diagnose_slow_endpoint(endpoint_func):
    """Diagnose why an endpoint is slow."""
    import time

    # Check for blocking calls
    blocking_modules = ["requests", "urllib", "time.sleep"]

    # Check for N+1 patterns
    query_count = 0

    # Monkey-patch to count queries
    original_execute = Session.execute

    def counting_execute(self, *args, **kwargs):
        nonlocal query_count
        query_count += 1
        return original_execute(self, *args, **kwargs)

    Session.execute = counting_execute

    try:
        start = time.perf_counter()
        await endpoint_func()
        duration = time.perf_counter() - start

        return {
            "duration_ms": duration * 1000,
            "query_count": query_count,
            "potential_n_plus_1": query_count > 10,
        }
    finally:
        Session.execute = original_execute
```

---

## Summary

Module 10 covers mastery-level topics for FastAPI:

1. **Advanced Async Patterns**: Event loop management, connection pools, semaphores, graceful shutdown, and task groups
2. **Multi-Tenancy**: Isolation strategies, tenant identification, schema/database per tenant, tenant-aware caching
3. **Advanced Security**: OAuth2 with external providers, OpenID Connect, advanced JWT patterns, security headers
4. **Debugging & Troubleshooting**: Async debugging, memory leak detection, request tracing, performance profiling

These topics represent the deepest level of FastAPI expertise, enabling you to build enterprise-grade applications with proper isolation, security, and observability.

---

This completes the FastAPI syllabus from intermediate to mastery level.

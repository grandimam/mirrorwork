# Module 20: Reliability Engineering

## Overview

Reliability is the probability your server will work when needed. This module covers graceful degradation, circuit breakers, retries, timeouts, health checks, and designing for failure. Building reliable systems means expecting and handling failures.

---

## Learning Objectives

By the end of this module, you will be able to:

1. Design for failure with graceful degradation
2. Implement circuit breakers and retry logic
3. Configure timeouts at every layer
4. Build health check endpoints
5. Handle backpressure and overload

---

## 20.1 Designing for Failure

### Failure Modes

```
┌─────────────────────────────────────────────────────────────┐
│                    Failure Categories                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Network Failures          Service Failures                 │
│  ├─ Connection refused     ├─ Timeouts                     │
│  ├─ Connection reset       ├─ 5xx errors                   │
│  ├─ DNS resolution         ├─ Malformed responses          │
│  └─ Packet loss            └─ Resource exhaustion          │
│                                                             │
│  Infrastructure Failures   Application Failures             │
│  ├─ Server crash           ├─ Out of memory                │
│  ├─ Disk full              ├─ Deadlock                     │
│  ├─ Region outage          ├─ Infinite loop                │
│  └─ Database down          └─ Unhandled exception          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### The Reliability Mindset

```python
# Unreliable: Assumes everything works
async def get_user_data(user_id: int):
    user = await db.fetch_user(user_id)
    profile = await profile_service.get(user_id)
    preferences = await preferences_service.get(user_id)
    return {**user, **profile, **preferences}


# Reliable: Handles partial failures
async def get_user_data_reliable(user_id: int):
    try:
        user = await db.fetch_user(user_id)
        if not user:
            return None
    except DatabaseError:
        raise ServiceUnavailable("Database unavailable")

    # Optional data - graceful degradation
    profile = {}
    preferences = {}

    try:
        profile = await asyncio.wait_for(
            profile_service.get(user_id),
            timeout=2.0
        )
    except (asyncio.TimeoutError, ServiceError):
        pass  # Use empty profile

    try:
        preferences = await asyncio.wait_for(
            preferences_service.get(user_id),
            timeout=2.0
        )
    except (asyncio.TimeoutError, ServiceError):
        preferences = DEFAULT_PREFERENCES

    return {**user, 'profile': profile, 'preferences': preferences}
```

---

## 20.2 Timeouts

### Timeout Everywhere

```python
import asyncio
from typing import TypeVar, Awaitable
from contextlib import asynccontextmanager


T = TypeVar('T')


async def with_timeout(coro: Awaitable[T], timeout: float,
                       default: T = None) -> T:
    """Execute coroutine with timeout."""
    try:
        return await asyncio.wait_for(coro, timeout)
    except asyncio.TimeoutError:
        return default


@asynccontextmanager
async def timeout_context(seconds: float):
    """Context manager for timeout."""
    try:
        async with asyncio.timeout(seconds):
            yield
    except asyncio.TimeoutError:
        raise TimeoutError(f"Operation timed out after {seconds}s")


# Timeout configuration
class TimeoutConfig:
    """Centralized timeout configuration."""

    # Connection timeouts
    CONNECT_TIMEOUT = 5.0
    READ_TIMEOUT = 30.0
    WRITE_TIMEOUT = 30.0

    # Service timeouts
    DATABASE_TIMEOUT = 10.0
    CACHE_TIMEOUT = 1.0
    EXTERNAL_API_TIMEOUT = 15.0

    # Request timeouts
    REQUEST_TIMEOUT = 60.0

    # Graceful shutdown
    SHUTDOWN_TIMEOUT = 30.0


# HTTP client with timeouts
class ReliableHTTPClient:
    """HTTP client with comprehensive timeouts."""

    def __init__(self):
        self.timeout = aiohttp.ClientTimeout(
            total=TimeoutConfig.EXTERNAL_API_TIMEOUT,
            connect=TimeoutConfig.CONNECT_TIMEOUT,
            sock_read=TimeoutConfig.READ_TIMEOUT,
        )

    async def get(self, url: str, **kwargs):
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.get(url, **kwargs) as response:
                return await response.json()
```

### Cascading Timeouts

```python
class RequestContext:
    """Track remaining time budget for request."""

    def __init__(self, total_timeout: float):
        self.deadline = time.monotonic() + total_timeout

    @property
    def remaining(self) -> float:
        return max(0, self.deadline - time.monotonic())

    @property
    def expired(self) -> bool:
        return self.remaining <= 0


async def handle_request(request):
    ctx = RequestContext(total_timeout=30.0)

    # Allocate time budget to operations
    user = await with_timeout(
        get_user(request.user_id),
        timeout=min(5.0, ctx.remaining)
    )

    if ctx.expired:
        return partial_response(user)

    orders = await with_timeout(
        get_orders(user.id),
        timeout=min(10.0, ctx.remaining)
    )

    if ctx.expired:
        return partial_response(user, orders)

    recommendations = await with_timeout(
        get_recommendations(user),
        timeout=ctx.remaining
    )

    return full_response(user, orders, recommendations)
```

---

## 20.3 Circuit Breaker

### State Machine

```
┌─────────────────────────────────────────────────────────────┐
│                    Circuit Breaker States                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│    ┌──────────┐                      ┌──────────┐          │
│    │  CLOSED  │───failures exceed────▶│   OPEN   │          │
│    │ (normal) │     threshold        │ (failing)│          │
│    └────▲─────┘                      └────┬─────┘          │
│         │                                 │                 │
│         │                          timeout expires          │
│         │                                 │                 │
│         │                          ┌──────▼─────┐          │
│    success                         │ HALF-OPEN  │          │
│         │                          │  (testing) │          │
│         └──────────────────────────┴────┬───────┘          │
│                                         │                   │
│                                    failure                  │
│                                         │                   │
│                                    ┌────▼─────┐            │
│                                    │   OPEN   │            │
│                                    └──────────┘            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Implementation

```python
import asyncio
import time
from enum import Enum
from dataclasses import dataclass, field
from typing import Callable, Awaitable, TypeVar, Optional


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5
    success_threshold: int = 2
    timeout: float = 30.0
    half_open_max_calls: int = 3


class CircuitBreaker:
    """Circuit breaker for external service calls."""

    def __init__(self, name: str, config: CircuitBreakerConfig = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failures = 0
        self.successes = 0
        self.last_failure_time = 0
        self.half_open_calls = 0
        self._lock = asyncio.Lock()

    async def call(self, func: Callable[..., Awaitable], *args, **kwargs):
        """Execute function through circuit breaker."""
        async with self._lock:
            self._maybe_reset()

            if self.state == CircuitState.OPEN:
                raise CircuitOpenError(f"Circuit {self.name} is open")

            if self.state == CircuitState.HALF_OPEN:
                if self.half_open_calls >= self.config.half_open_max_calls:
                    raise CircuitOpenError(f"Circuit {self.name} half-open limit")
                self.half_open_calls += 1

        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except Exception as e:
            await self._on_failure()
            raise

    async def _on_success(self):
        async with self._lock:
            self.failures = 0

            if self.state == CircuitState.HALF_OPEN:
                self.successes += 1
                if self.successes >= self.config.success_threshold:
                    self._close()

    async def _on_failure(self):
        async with self._lock:
            self.failures += 1
            self.last_failure_time = time.monotonic()

            if self.state == CircuitState.HALF_OPEN:
                self._open()
            elif self.failures >= self.config.failure_threshold:
                self._open()

    def _maybe_reset(self):
        """Check if circuit should transition from open to half-open."""
        if self.state == CircuitState.OPEN:
            if time.monotonic() - self.last_failure_time >= self.config.timeout:
                self._half_open()

    def _open(self):
        self.state = CircuitState.OPEN
        self.successes = 0
        self.half_open_calls = 0

    def _half_open(self):
        self.state = CircuitState.HALF_OPEN
        self.successes = 0
        self.half_open_calls = 0

    def _close(self):
        self.state = CircuitState.CLOSED
        self.failures = 0
        self.successes = 0


class CircuitOpenError(Exception):
    pass


# Usage
payment_circuit = CircuitBreaker("payment-service")

async def process_payment(order):
    try:
        return await payment_circuit.call(
            payment_api.charge,
            order.amount,
            order.payment_method
        )
    except CircuitOpenError:
        # Fallback: queue for later processing
        await payment_queue.enqueue(order)
        return PaymentPending()
```

### Circuit Breaker Registry

```python
class CircuitBreakerRegistry:
    """Manage multiple circuit breakers."""

    def __init__(self):
        self._breakers: dict[str, CircuitBreaker] = {}

    def get(self, name: str,
            config: CircuitBreakerConfig = None) -> CircuitBreaker:
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(name, config)
        return self._breakers[name]

    def status(self) -> dict:
        return {
            name: {
                'state': cb.state.value,
                'failures': cb.failures,
            }
            for name, cb in self._breakers.items()
        }


circuits = CircuitBreakerRegistry()

# Usage in different parts of code
async def call_user_service():
    cb = circuits.get("user-service")
    return await cb.call(user_api.get_user, user_id)

async def call_inventory_service():
    cb = circuits.get("inventory-service")
    return await cb.call(inventory_api.check, product_id)
```

---

## 20.4 Retry with Backoff

### Exponential Backoff

```python
import asyncio
import random
from typing import Callable, Awaitable, TypeVar, Type
from dataclasses import dataclass


T = TypeVar('T')


@dataclass
class RetryConfig:
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    retryable_exceptions: tuple = (Exception,)


class Retry:
    """Retry with exponential backoff and jitter."""

    def __init__(self, config: RetryConfig = None):
        self.config = config or RetryConfig()

    async def execute(self, func: Callable[..., Awaitable[T]],
                     *args, **kwargs) -> T:
        """Execute function with retries."""
        last_exception = None

        for attempt in range(self.config.max_attempts):
            try:
                return await func(*args, **kwargs)
            except self.config.retryable_exceptions as e:
                last_exception = e

                if attempt == self.config.max_attempts - 1:
                    break

                delay = self._calculate_delay(attempt)
                await asyncio.sleep(delay)

        raise last_exception

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay with exponential backoff and jitter."""
        delay = self.config.base_delay * (
            self.config.exponential_base ** attempt
        )
        delay = min(delay, self.config.max_delay)

        if self.config.jitter:
            # Add random jitter (±25%)
            jitter = delay * 0.25 * (2 * random.random() - 1)
            delay += jitter

        return delay


# Decorator version
def retry(max_attempts: int = 3,
          base_delay: float = 1.0,
          exceptions: tuple = (Exception,)):
    """Retry decorator."""
    config = RetryConfig(
        max_attempts=max_attempts,
        base_delay=base_delay,
        retryable_exceptions=exceptions
    )
    retrier = Retry(config)

    def decorator(func):
        async def wrapper(*args, **kwargs):
            return await retrier.execute(func, *args, **kwargs)
        return wrapper
    return decorator


# Usage
@retry(max_attempts=3, base_delay=0.5, exceptions=(ConnectionError, TimeoutError))
async def fetch_data(url: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()
```

### Retry with Circuit Breaker

```python
class ResilientCaller:
    """Combines retry and circuit breaker."""

    def __init__(self, name: str,
                 circuit_config: CircuitBreakerConfig = None,
                 retry_config: RetryConfig = None):
        self.circuit = CircuitBreaker(name, circuit_config)
        self.retry = Retry(retry_config)

    async def call(self, func: Callable[..., Awaitable[T]],
                   *args, **kwargs) -> T:
        """Call with retry inside circuit breaker."""
        async def retried_func():
            return await self.retry.execute(func, *args, **kwargs)

        return await self.circuit.call(retried_func)


# Usage
api_caller = ResilientCaller(
    "external-api",
    circuit_config=CircuitBreakerConfig(failure_threshold=5),
    retry_config=RetryConfig(max_attempts=3)
)

async def get_external_data():
    return await api_caller.call(external_api.fetch)
```

---

## 20.5 Health Checks

### Health Check Types

```python
from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Optional
import asyncio


class HealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class HealthCheckResult:
    name: str
    status: HealthStatus
    message: Optional[str] = None
    latency_ms: Optional[float] = None
    details: Optional[dict] = None


class HealthChecker:
    """Comprehensive health check system."""

    def __init__(self):
        self.checks: Dict[str, callable] = {}

    def register(self, name: str, check: callable):
        """Register a health check."""
        self.checks[name] = check

    async def check_all(self, timeout: float = 5.0) -> Dict[str, HealthCheckResult]:
        """Run all health checks."""
        results = {}

        async def run_check(name: str, check: callable):
            start = time.monotonic()
            try:
                result = await asyncio.wait_for(check(), timeout)
                latency = (time.monotonic() - start) * 1000

                if isinstance(result, HealthCheckResult):
                    result.latency_ms = latency
                    return name, result

                return name, HealthCheckResult(
                    name=name,
                    status=HealthStatus.HEALTHY,
                    latency_ms=latency
                )

            except asyncio.TimeoutError:
                return name, HealthCheckResult(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    message="Health check timed out"
                )
            except Exception as e:
                return name, HealthCheckResult(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    message=str(e)
                )

        tasks = [run_check(name, check) for name, check in self.checks.items()]
        check_results = await asyncio.gather(*tasks)

        return dict(check_results)

    async def overall_status(self) -> HealthStatus:
        """Get overall health status."""
        results = await self.check_all()

        if all(r.status == HealthStatus.HEALTHY for r in results.values()):
            return HealthStatus.HEALTHY

        if any(r.status == HealthStatus.UNHEALTHY for r in results.values()):
            return HealthStatus.UNHEALTHY

        return HealthStatus.DEGRADED


# Health check implementations
async def database_health_check(pool) -> HealthCheckResult:
    """Check database connectivity."""
    try:
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return HealthCheckResult(
            name="database",
            status=HealthStatus.HEALTHY
        )
    except Exception as e:
        return HealthCheckResult(
            name="database",
            status=HealthStatus.UNHEALTHY,
            message=str(e)
        )


async def redis_health_check(redis) -> HealthCheckResult:
    """Check Redis connectivity."""
    try:
        await redis.ping()
        return HealthCheckResult(
            name="redis",
            status=HealthStatus.HEALTHY
        )
    except Exception as e:
        return HealthCheckResult(
            name="redis",
            status=HealthStatus.UNHEALTHY,
            message=str(e)
        )


async def disk_space_check(threshold: float = 0.9) -> HealthCheckResult:
    """Check disk space."""
    import shutil
    total, used, free = shutil.disk_usage("/")
    usage = used / total

    if usage > threshold:
        return HealthCheckResult(
            name="disk",
            status=HealthStatus.UNHEALTHY,
            message=f"Disk usage at {usage:.1%}",
            details={"usage": usage, "free_gb": free / (1024**3)}
        )

    return HealthCheckResult(
        name="disk",
        status=HealthStatus.HEALTHY,
        details={"usage": usage, "free_gb": free / (1024**3)}
    )


# Setup
health = HealthChecker()
health.register("database", lambda: database_health_check(db_pool))
health.register("redis", lambda: redis_health_check(redis_client))
health.register("disk", disk_space_check)
```

### Health Endpoints

```python
class HealthEndpoints:
    """Health check HTTP endpoints."""

    def __init__(self, checker: HealthChecker):
        self.checker = checker

    async def liveness(self, request) -> Response:
        """
        Liveness probe - is the process running?
        Used by Kubernetes to restart unhealthy pods.
        """
        return Response.json({"status": "alive"}, status=200)

    async def readiness(self, request) -> Response:
        """
        Readiness probe - can the service handle requests?
        Used by Kubernetes to route traffic.
        """
        status = await self.checker.overall_status()

        if status == HealthStatus.UNHEALTHY:
            return Response.json(
                {"status": "not ready"},
                status=503
            )

        return Response.json({"status": "ready"}, status=200)

    async def health(self, request) -> Response:
        """
        Detailed health check for monitoring.
        """
        results = await self.checker.check_all()
        overall = await self.checker.overall_status()

        response = {
            "status": overall.value,
            "checks": {
                name: {
                    "status": result.status.value,
                    "message": result.message,
                    "latency_ms": result.latency_ms,
                    "details": result.details,
                }
                for name, result in results.items()
            }
        }

        status_code = 200 if overall == HealthStatus.HEALTHY else 503
        return Response.json(response, status=status_code)


# Register routes
health_endpoints = HealthEndpoints(health)
app.route('GET', '/health/live', health_endpoints.liveness)
app.route('GET', '/health/ready', health_endpoints.readiness)
app.route('GET', '/health', health_endpoints.health)
```

---

## 20.6 Graceful Shutdown

```python
import signal
import asyncio
from typing import Set


class GracefulShutdown:
    """Handle graceful shutdown of server."""

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout
        self.shutdown_event = asyncio.Event()
        self.active_connections: Set = set()
        self._shutdown_handlers: list = []

    def setup_signals(self):
        """Setup signal handlers."""
        loop = asyncio.get_event_loop()

        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(
                sig,
                lambda: asyncio.create_task(self.shutdown())
            )

    def add_shutdown_handler(self, handler: callable):
        """Register shutdown handler."""
        self._shutdown_handlers.append(handler)

    def track_connection(self, conn):
        """Track active connection."""
        self.active_connections.add(conn)

    def untrack_connection(self, conn):
        """Untrack completed connection."""
        self.active_connections.discard(conn)

    @property
    def is_shutting_down(self) -> bool:
        return self.shutdown_event.is_set()

    async def shutdown(self):
        """Initiate graceful shutdown."""
        if self.shutdown_event.is_set():
            return

        print("Initiating graceful shutdown...")
        self.shutdown_event.set()

        # Stop accepting new connections
        # (handled by main server loop checking is_shutting_down)

        # Wait for active connections
        if self.active_connections:
            print(f"Waiting for {len(self.active_connections)} connections...")

            try:
                await asyncio.wait_for(
                    self._wait_for_connections(),
                    timeout=self.timeout
                )
            except asyncio.TimeoutError:
                print(f"Timeout: {len(self.active_connections)} connections remaining")

        # Run shutdown handlers
        for handler in self._shutdown_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler()
                else:
                    handler()
            except Exception as e:
                print(f"Shutdown handler error: {e}")

        print("Shutdown complete")

    async def _wait_for_connections(self):
        """Wait until all connections are closed."""
        while self.active_connections:
            await asyncio.sleep(0.1)


# Usage in server
class ReliableServer:
    """Server with graceful shutdown."""

    def __init__(self, app):
        self.app = app
        self.shutdown = GracefulShutdown(timeout=30.0)
        self.server = None

    async def start(self, host: str, port: int):
        """Start server."""
        self.shutdown.setup_signals()

        # Register cleanup handlers
        self.shutdown.add_shutdown_handler(self.close_database)
        self.shutdown.add_shutdown_handler(self.close_redis)

        self.server = await asyncio.start_server(
            self.handle_connection,
            host, port
        )

        print(f"Server started on {host}:{port}")

        async with self.server:
            await self.shutdown.shutdown_event.wait()

    async def handle_connection(self, reader, writer):
        """Handle connection with shutdown awareness."""
        if self.shutdown.is_shutting_down:
            writer.close()
            return

        self.shutdown.track_connection(writer)

        try:
            await self.app.handle(reader, writer)
        finally:
            self.shutdown.untrack_connection(writer)
            writer.close()

    async def close_database(self):
        await db_pool.close()

    async def close_redis(self):
        await redis.close()
```

---

## 20.7 Backpressure Handling

```python
import asyncio
from typing import Generic, TypeVar


T = TypeVar('T')


class BoundedQueue(Generic[T]):
    """Queue with backpressure."""

    def __init__(self, maxsize: int = 1000):
        self.queue = asyncio.Queue(maxsize=maxsize)
        self.dropped = 0

    async def put(self, item: T, timeout: float = None) -> bool:
        """Put item with optional timeout."""
        try:
            if timeout:
                await asyncio.wait_for(
                    self.queue.put(item),
                    timeout=timeout
                )
            else:
                self.queue.put_nowait(item)
            return True
        except (asyncio.TimeoutError, asyncio.QueueFull):
            self.dropped += 1
            return False

    async def get(self) -> T:
        return await self.queue.get()

    @property
    def size(self) -> int:
        return self.queue.qsize()

    @property
    def full(self) -> bool:
        return self.queue.full()


class LoadShedder:
    """Shed load when system is overloaded."""

    def __init__(self, max_concurrent: int = 100):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.rejected = 0

    async def acquire(self) -> bool:
        """Try to acquire slot."""
        if self.semaphore.locked():
            self.rejected += 1
            return False
        await self.semaphore.acquire()
        return True

    def release(self):
        """Release slot."""
        self.semaphore.release()


class LoadSheddingMiddleware:
    """Middleware to shed excess load."""

    def __init__(self, app, max_concurrent: int = 100):
        self.app = app
        self.shedder = LoadShedder(max_concurrent)

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        if not await self.shedder.acquire():
            # Service overloaded
            await send({
                'type': 'http.response.start',
                'status': 503,
                'headers': [
                    (b'content-type', b'application/json'),
                    (b'retry-after', b'5'),
                ],
            })
            await send({
                'type': 'http.response.body',
                'body': b'{"error": "Service Overloaded"}',
            })
            return

        try:
            await self.app(scope, receive, send)
        finally:
            self.shedder.release()
```

---

## 20.8 Bulkhead Pattern

```python
class Bulkhead:
    """Isolate failures to prevent cascade."""

    def __init__(self, name: str, max_concurrent: int = 10):
        self.name = name
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.rejected = 0
        self.active = 0

    async def execute(self, func: callable, *args, **kwargs):
        """Execute within bulkhead."""
        try:
            async with asyncio.timeout(0):  # Non-blocking acquire
                await self.semaphore.acquire()
        except asyncio.TimeoutError:
            self.rejected += 1
            raise BulkheadFullError(f"Bulkhead {self.name} is full")

        self.active += 1
        try:
            return await func(*args, **kwargs)
        finally:
            self.active -= 1
            self.semaphore.release()


class BulkheadFullError(Exception):
    pass


# Usage - isolate different services
class ServiceClients:
    """Service clients with bulkhead isolation."""

    def __init__(self):
        self.user_bulkhead = Bulkhead("users", max_concurrent=20)
        self.order_bulkhead = Bulkhead("orders", max_concurrent=30)
        self.payment_bulkhead = Bulkhead("payments", max_concurrent=10)

    async def get_user(self, user_id: int):
        return await self.user_bulkhead.execute(
            user_api.get, user_id
        )

    async def get_orders(self, user_id: int):
        return await self.order_bulkhead.execute(
            order_api.list, user_id
        )

    async def process_payment(self, order_id: int):
        return await self.payment_bulkhead.execute(
            payment_api.charge, order_id
        )
```

---

## 20.9 Fallback Strategies

```python
from typing import Callable, TypeVar, Optional


T = TypeVar('T')


class Fallback:
    """Fallback strategies for failures."""

    @staticmethod
    async def with_default(func: Callable, default: T, *args, **kwargs) -> T:
        """Return default value on failure."""
        try:
            return await func(*args, **kwargs)
        except Exception:
            return default

    @staticmethod
    async def with_cache(func: Callable, cache_key: str,
                         cache, *args, **kwargs) -> T:
        """Fall back to cached value on failure."""
        try:
            result = await func(*args, **kwargs)
            await cache.set(cache_key, result)
            return result
        except Exception:
            cached = await cache.get(cache_key)
            if cached is not None:
                return cached
            raise

    @staticmethod
    async def with_alternative(primary: Callable, secondary: Callable,
                               *args, **kwargs) -> T:
        """Fall back to alternative function."""
        try:
            return await primary(*args, **kwargs)
        except Exception:
            return await secondary(*args, **kwargs)


# Usage examples
async def get_user_with_fallbacks(user_id: int):
    # Try primary database
    try:
        return await primary_db.get_user(user_id)
    except DatabaseError:
        pass

    # Try read replica
    try:
        return await replica_db.get_user(user_id)
    except DatabaseError:
        pass

    # Try cache
    cached = await cache.get(f"user:{user_id}")
    if cached:
        return cached

    # Return minimal user object
    return {"id": user_id, "status": "unknown"}
```

---

## 20.10 Reliability Checklist

### Timeouts

```
□ Connection timeout configured
□ Read/write timeouts configured
□ Request timeout enforced
□ Database query timeouts
□ External API timeouts
□ Cascading timeout budgets
```

### Resilience Patterns

```
□ Circuit breakers for external calls
□ Retry with exponential backoff
□ Bulkheads for isolation
□ Fallback strategies defined
□ Graceful degradation
```

### Health & Monitoring

```
□ Liveness probe endpoint
□ Readiness probe endpoint
□ Detailed health checks
□ Dependency health monitoring
□ Alert thresholds defined
```

### Shutdown

```
□ Signal handlers registered
□ Graceful shutdown implemented
□ Connection draining
□ Resource cleanup
□ Shutdown timeout
```

---

## Exercises

### Exercise 20.1: Implement Circuit Breaker

Add circuit breaker to database calls:
- Open after 5 failures
- Half-open after 30 seconds
- Close after 3 successes

### Exercise 20.2: Cascading Timeouts

Implement request timeout budget:
- Total request: 30 seconds
- Allocate time to DB, cache, external API
- Return partial response if timeout

### Exercise 20.3: Graceful Degradation

Build endpoint that:
- Returns full data when all services healthy
- Returns partial data when some fail
- Returns cached data when database fails

---

## Summary

Reliability engineering fundamentals:

1. **Expect failure**: Design for it
2. **Timeout everything**: Prevent hanging
3. **Circuit breakers**: Stop cascading failures
4. **Retry wisely**: With backoff and limits
5. **Health checks**: Know your system state
6. **Graceful shutdown**: Clean exits
7. **Backpressure**: Shed load when overloaded

---

## Next Module

**[Module 21: Observability →](./MODULE_21_OBSERVABILITY.md)**

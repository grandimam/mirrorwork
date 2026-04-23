# Module 3: Advanced Request Handling

---

## 3.1 Middleware

### Creating Custom Middleware

```python
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import time
import uuid

app = FastAPI()

# Basic middleware using BaseHTTPMiddleware
class TimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.perf_counter()

        response = await call_next(request)

        process_time = time.perf_counter() - start_time
        response.headers["X-Process-Time"] = f"{process_time:.4f}"

        return response

app.add_middleware(TimingMiddleware)


# Request ID middleware
class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # Get or generate request ID
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = str(uuid.uuid4())

        # Store in request state for access in routes
        request.state.request_id = request_id

        response = await call_next(request)

        # Add to response headers
        response.headers["X-Request-ID"] = request_id

        return response

app.add_middleware(RequestIDMiddleware)


# Pure ASGI middleware (more performant)
from starlette.types import ASGIApp, Receive, Scope, Send

class PureASGIMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start_time = time.perf_counter()

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                process_time = time.perf_counter() - start_time
                headers = list(message.get("headers", []))
                headers.append((b"x-process-time", f"{process_time:.4f}".encode()))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_wrapper)

app.add_middleware(PureASGIMiddleware)


# Middleware with dependencies
class DatabaseMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, db_url: str):
        super().__init__(app)
        self.db_url = db_url
        self.pool = None

    async def dispatch(self, request: Request, call_next) -> Response:
        # Attach database connection to request
        async with self.get_connection() as conn:
            request.state.db = conn
            response = await call_next(request)
        return response

    async def get_connection(self):
        # Return connection from pool
        pass

app.add_middleware(DatabaseMiddleware, db_url="postgresql://...")
```

### Middleware Ordering and Execution Flow

```python
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

app = FastAPI()

# Middleware executes in reverse order of registration
# Last added = first to run on request, last to run on response

class FirstMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        print("1. First middleware - request")
        response = await call_next(request)
        print("6. First middleware - response")
        return response

class SecondMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        print("2. Second middleware - request")
        response = await call_next(request)
        print("5. Second middleware - response")
        return response

class ThirdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        print("3. Third middleware - request")
        response = await call_next(request)
        print("4. Third middleware - response")
        return response

# Registration order
app.add_middleware(FirstMiddleware)   # Runs first (outermost)
app.add_middleware(SecondMiddleware)  # Runs second
app.add_middleware(ThirdMiddleware)   # Runs third (innermost, closest to route)

# Execution flow:
# Request:  First -> Second -> Third -> Route Handler
# Response: Third -> Second -> First -> Client


# Controlling middleware order with app.middleware decorator
@app.middleware("http")
async def custom_middleware(request: Request, call_next):
    """This runs AFTER add_middleware registered ones"""
    print("Custom middleware")
    response = await call_next(request)
    return response


# Conditional middleware application
class ConditionalMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, paths: list[str]):
        super().__init__(app)
        self.paths = paths

    async def dispatch(self, request: Request, call_next) -> Response:
        # Only apply to specific paths
        if any(request.url.path.startswith(p) for p in self.paths):
            print(f"Applying middleware to {request.url.path}")
            # Do middleware logic
            pass

        return await call_next(request)

app.add_middleware(ConditionalMiddleware, paths=["/api/v1", "/api/v2"])
```

### Request/Response Modification

```python
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response, StreamingResponse
import json
import gzip
from io import BytesIO

app = FastAPI()

# Modify request body
class RequestBodyModifier(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # Read the original body
        body = await request.body()

        # Modify it (example: add timestamp to JSON)
        if request.headers.get("content-type") == "application/json" and body:
            data = json.loads(body)
            data["_timestamp"] = datetime.utcnow().isoformat()
            modified_body = json.dumps(data).encode()

            # Create new request with modified body
            async def receive():
                return {"type": "http.request", "body": modified_body}

            request._receive = receive

        return await call_next(request)


# Modify request headers
class HeaderModifier(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # Add/modify headers (need to create new scope)
        headers = dict(request.headers)
        headers["x-custom-header"] = "added-by-middleware"

        # Headers are immutable, but we can set on state
        request.state.custom_headers = headers

        return await call_next(request)


# Modify response body
class ResponseBodyModifier(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # Only modify JSON responses
        if response.headers.get("content-type", "").startswith("application/json"):
            # Read response body
            body = b""
            async for chunk in response.body_iterator:
                body += chunk

            # Modify it
            data = json.loads(body)
            data["_modified"] = True
            modified_body = json.dumps(data).encode()

            # Create new response
            return Response(
                content=modified_body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type="application/json"
            )

        return response


# Response compression middleware
class GzipMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, minimum_size: int = 500):
        super().__init__(app)
        self.minimum_size = minimum_size

    async def dispatch(self, request: Request, call_next) -> Response:
        # Check if client accepts gzip
        accept_encoding = request.headers.get("accept-encoding", "")
        if "gzip" not in accept_encoding:
            return await call_next(request)

        response = await call_next(request)

        # Don't compress if already compressed or streaming
        if (
            response.headers.get("content-encoding")
            or isinstance(response, StreamingResponse)
        ):
            return response

        # Read body
        body = b""
        async for chunk in response.body_iterator:
            body += chunk

        # Only compress if above minimum size
        if len(body) < self.minimum_size:
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type
            )

        # Compress
        compressed = gzip.compress(body)

        headers = dict(response.headers)
        headers["content-encoding"] = "gzip"
        headers["content-length"] = str(len(compressed))

        return Response(
            content=compressed,
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type
        )

app.add_middleware(GzipMiddleware, minimum_size=1000)
```

### Exception Handling in Middleware

```python
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import traceback
import logging

app = FastAPI()
logger = logging.getLogger(__name__)

# Global exception handler middleware
class ExceptionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        try:
            return await call_next(request)
        except Exception as exc:
            # Log the exception
            logger.error(
                f"Unhandled exception: {exc}\n{traceback.format_exc()}"
            )

            # Return generic error response
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal server error",
                    "request_id": getattr(request.state, "request_id", None)
                }
            )

app.add_middleware(ExceptionMiddleware)


# Exception with custom handling per type
class DetailedExceptionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        try:
            return await call_next(request)

        except HTTPException:
            # Let FastAPI handle HTTP exceptions
            raise

        except ValueError as exc:
            return JSONResponse(
                status_code=400,
                content={"error": "Invalid value", "detail": str(exc)}
            )

        except PermissionError as exc:
            return JSONResponse(
                status_code=403,
                content={"error": "Permission denied", "detail": str(exc)}
            )

        except TimeoutError:
            return JSONResponse(
                status_code=504,
                content={"error": "Request timeout"}
            )

        except Exception as exc:
            # Log and return generic error
            logger.exception("Unhandled exception")
            return JSONResponse(
                status_code=500,
                content={"error": "Internal server error"}
            )


# Circuit breaker middleware
class CircuitBreakerMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, failure_threshold: int = 5, reset_timeout: int = 60):
        super().__init__(app)
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.failures = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open

    async def dispatch(self, request: Request, call_next) -> Response:
        # Check circuit state
        if self.state == "open":
            if time.time() - self.last_failure_time > self.reset_timeout:
                self.state = "half-open"
            else:
                return JSONResponse(
                    status_code=503,
                    content={"error": "Service temporarily unavailable"}
                )

        try:
            response = await call_next(request)

            # Reset on success
            if response.status_code < 500:
                if self.state == "half-open":
                    self.state = "closed"
                self.failures = 0

            return response

        except Exception as exc:
            self.failures += 1
            self.last_failure_time = time.time()

            if self.failures >= self.failure_threshold:
                self.state = "open"
                logger.warning("Circuit breaker opened")

            raise
```

### Timing and Logging Middleware

```python
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import time
import logging
import json
from datetime import datetime

app = FastAPI()

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger("api")

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # Generate request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # Capture start time
        start_time = time.perf_counter()

        # Log request
        request_log = {
            "timestamp": datetime.utcnow().isoformat(),
            "type": "request",
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "query": str(request.query_params),
            "client_ip": request.client.host,
            "user_agent": request.headers.get("user-agent")
        }
        logger.info(json.dumps(request_log))

        # Process request
        try:
            response = await call_next(request)
            status_code = response.status_code
            error = None
        except Exception as exc:
            status_code = 500
            error = str(exc)
            raise
        finally:
            # Calculate duration
            duration = time.perf_counter() - start_time

            # Log response
            response_log = {
                "timestamp": datetime.utcnow().isoformat(),
                "type": "response",
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": status_code,
                "duration_ms": round(duration * 1000, 2),
                "error": error
            }
            logger.info(json.dumps(response_log))

        # Add timing header
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{duration * 1000:.2f}ms"

        return response

app.add_middleware(LoggingMiddleware)


# Slow request detection
class SlowRequestMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, threshold_ms: float = 1000):
        super().__init__(app)
        self.threshold_ms = threshold_ms

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000

        if duration_ms > self.threshold_ms:
            logger.warning(
                f"Slow request: {request.method} {request.url.path} "
                f"took {duration_ms:.2f}ms"
            )

        return response

app.add_middleware(SlowRequestMiddleware, threshold_ms=500)


# Request/response body logging (be careful with sensitive data)
class BodyLoggingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, log_paths: list[str] = None):
        super().__init__(app)
        self.log_paths = log_paths or []

    async def dispatch(self, request: Request, call_next) -> Response:
        # Only log specific paths
        if not any(request.url.path.startswith(p) for p in self.log_paths):
            return await call_next(request)

        # Log request body
        body = await request.body()
        if body:
            # Mask sensitive fields
            try:
                data = json.loads(body)
                data = self._mask_sensitive(data)
                logger.debug(f"Request body: {json.dumps(data)}")
            except:
                logger.debug(f"Request body: {len(body)} bytes")

        # Create new receive to restore body
        async def receive():
            return {"type": "http.request", "body": body}
        request._receive = receive

        response = await call_next(request)

        return response

    def _mask_sensitive(self, data: dict) -> dict:
        sensitive_keys = {"password", "token", "secret", "api_key", "credit_card"}
        masked = {}
        for key, value in data.items():
            if key.lower() in sensitive_keys:
                masked[key] = "***MASKED***"
            elif isinstance(value, dict):
                masked[key] = self._mask_sensitive(value)
            else:
                masked[key] = value
        return masked
```

### Authentication Middleware Patterns

```python
from fastapi import FastAPI, Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response, JSONResponse
import jwt

app = FastAPI()

class AuthenticationMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        secret_key: str,
        exclude_paths: list[str] = None,
        exclude_methods: list[str] = None
    ):
        super().__init__(app)
        self.secret_key = secret_key
        self.exclude_paths = exclude_paths or ["/health", "/docs", "/openapi.json"]
        self.exclude_methods = exclude_methods or ["OPTIONS"]

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip authentication for excluded paths/methods
        if request.method in self.exclude_methods:
            return await call_next(request)

        if any(request.url.path.startswith(p) for p in self.exclude_paths):
            return await call_next(request)

        # Get token
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"error": "Missing authentication token"},
                headers={"WWW-Authenticate": "Bearer"}
            )

        token = auth_header.replace("Bearer ", "")

        try:
            # Decode and validate token
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=["HS256"]
            )

            # Attach user info to request state
            request.state.user_id = payload.get("sub")
            request.state.user_roles = payload.get("roles", [])
            request.state.token_payload = payload

        except jwt.ExpiredSignatureError:
            return JSONResponse(
                status_code=401,
                content={"error": "Token expired"}
            )
        except jwt.InvalidTokenError as e:
            return JSONResponse(
                status_code=401,
                content={"error": f"Invalid token: {str(e)}"}
            )

        return await call_next(request)

app.add_middleware(
    AuthenticationMiddleware,
    secret_key="your-secret-key",
    exclude_paths=["/health", "/docs", "/openapi.json", "/auth/login"]
)


# API Key authentication middleware
class APIKeyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, api_keys: dict[str, dict], header_name: str = "X-API-Key"):
        super().__init__(app)
        self.api_keys = api_keys
        self.header_name = header_name

    async def dispatch(self, request: Request, call_next) -> Response:
        api_key = request.headers.get(self.header_name)

        if not api_key:
            return JSONResponse(
                status_code=401,
                content={"error": "API key required"}
            )

        key_data = self.api_keys.get(api_key)
        if not key_data:
            return JSONResponse(
                status_code=403,
                content={"error": "Invalid API key"}
            )

        # Attach key info to request
        request.state.api_key = api_key
        request.state.api_key_data = key_data

        return await call_next(request)


# Multi-tenant middleware
class TenantMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, tenant_header: str = "X-Tenant-ID"):
        super().__init__(app)
        self.tenant_header = tenant_header

    async def dispatch(self, request: Request, call_next) -> Response:
        tenant_id = request.headers.get(self.tenant_header)

        if not tenant_id:
            # Try to extract from subdomain
            host = request.headers.get("host", "")
            if "." in host:
                tenant_id = host.split(".")[0]

        if not tenant_id:
            return JSONResponse(
                status_code=400,
                content={"error": "Tenant ID required"}
            )

        # Validate tenant
        tenant = await self.get_tenant(tenant_id)
        if not tenant:
            return JSONResponse(
                status_code=404,
                content={"error": "Tenant not found"}
            )

        request.state.tenant_id = tenant_id
        request.state.tenant = tenant

        return await call_next(request)

    async def get_tenant(self, tenant_id: str) -> dict | None:
        # Fetch from database/cache
        return {"id": tenant_id, "name": f"Tenant {tenant_id}"}
```

---

## 3.2 Background Tasks & Async Patterns

### Background Tasks for Post-Response Work

```python
from fastapi import FastAPI, BackgroundTasks, Depends
from pydantic import BaseModel, EmailStr
import asyncio
import aiosmtplib

app = FastAPI()

# Simple background task
def write_log(message: str):
    with open("log.txt", "a") as f:
        f.write(f"{datetime.utcnow()}: {message}\n")

@app.post("/items")
async def create_item(
    item: dict,
    background_tasks: BackgroundTasks
):
    # Create item first
    item_id = 1  # save to database

    # Log in background after response
    background_tasks.add_task(write_log, f"Created item {item_id}")

    return {"item_id": item_id}


# Async background task
async def send_email_async(to: str, subject: str, body: str):
    await aiosmtplib.send(
        message=f"Subject: {subject}\n\n{body}",
        sender="noreply@example.com",
        recipients=[to],
        hostname="smtp.example.com",
        port=587
    )

@app.post("/register")
async def register_user(
    email: EmailStr,
    background_tasks: BackgroundTasks
):
    # Create user
    user_id = 1

    # Send welcome email in background
    background_tasks.add_task(
        send_email_async,
        to=email,
        subject="Welcome!",
        body="Thanks for registering."
    )

    return {"user_id": user_id, "message": "Registration complete"}


# Multiple background tasks
@app.post("/orders")
async def create_order(
    order: dict,
    background_tasks: BackgroundTasks
):
    order_id = 1

    # Queue multiple background tasks
    background_tasks.add_task(send_order_confirmation, order_id)
    background_tasks.add_task(notify_warehouse, order_id)
    background_tasks.add_task(update_inventory, order["items"])
    background_tasks.add_task(log_analytics, "order_created", order_id)

    return {"order_id": order_id}


# Background tasks in dependencies
async def get_audit_logger(background_tasks: BackgroundTasks):
    def log(action: str, details: dict):
        background_tasks.add_task(write_audit_log, action, details)
    return log

@app.post("/sensitive-action")
async def sensitive_action(
    data: dict,
    audit_log: callable = Depends(get_audit_logger)
):
    # Perform action
    result = {"success": True}

    # Log will happen after response
    audit_log("sensitive_action", {"data": data, "result": result})

    return result
```

### Task Queues with Celery/ARQ/RQ

```python
# Celery setup (celery_config.py)
from celery import Celery

celery_app = Celery(
    "tasks",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/1"
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_routes={
        "tasks.email.*": {"queue": "email"},
        "tasks.heavy.*": {"queue": "heavy"},
    }
)

# Celery tasks (tasks.py)
from celery_config import celery_app

@celery_app.task(bind=True, max_retries=3)
def send_email_task(self, to: str, subject: str, body: str):
    try:
        # Send email logic
        pass
    except Exception as exc:
        self.retry(exc=exc, countdown=60)

@celery_app.task
def process_video(video_id: int):
    # Heavy processing
    pass

@celery_app.task
def generate_report(report_id: int) -> dict:
    # Generate and return result
    return {"report_id": report_id, "status": "complete"}


# FastAPI integration
from fastapi import FastAPI
from tasks import send_email_task, process_video, generate_report
from celery.result import AsyncResult

app = FastAPI()

@app.post("/send-email")
async def send_email(to: str, subject: str, body: str):
    task = send_email_task.delay(to, subject, body)
    return {"task_id": task.id}

@app.post("/process-video/{video_id}")
async def start_video_processing(video_id: int):
    task = process_video.delay(video_id)
    return {"task_id": task.id, "status": "processing"}

@app.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    result = AsyncResult(task_id)
    return {
        "task_id": task_id,
        "status": result.status,
        "result": result.result if result.ready() else None
    }


# ARQ setup (faster, async-native)
from arq import create_pool
from arq.connections import RedisSettings

# Worker functions
async def send_email_arq(ctx, to: str, subject: str, body: str):
    # Async email sending
    pass

async def process_data_arq(ctx, data_id: int):
    # Access shared resources via ctx
    db = ctx["db"]
    result = await db.execute(...)
    return result

# Worker settings
class WorkerSettings:
    functions = [send_email_arq, process_data_arq]
    redis_settings = RedisSettings()

    @staticmethod
    async def on_startup(ctx):
        ctx["db"] = await create_db_pool()

    @staticmethod
    async def on_shutdown(ctx):
        await ctx["db"].close()

# FastAPI with ARQ
from arq.connections import ArqRedis

app = FastAPI()

@app.on_event("startup")
async def startup():
    app.state.arq = await create_pool(RedisSettings())

@app.on_event("shutdown")
async def shutdown():
    await app.state.arq.close()

@app.post("/async-task")
async def enqueue_task(data_id: int):
    job = await app.state.arq.enqueue_job("process_data_arq", data_id)
    return {"job_id": job.job_id}

@app.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    job = await app.state.arq.job(job_id)
    status = await job.status()
    result = await job.result() if status == "complete" else None
    return {"job_id": job_id, "status": status, "result": result}
```

### Async Context Managers

```python
from fastapi import FastAPI, Depends
from contextlib import asynccontextmanager
from typing import AsyncGenerator
import asyncpg
import aioredis
import httpx

# Application lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    app.state.db_pool = await asyncpg.create_pool(
        "postgresql://user:pass@localhost/db"
    )
    app.state.redis = await aioredis.from_url("redis://localhost")
    app.state.http_client = httpx.AsyncClient()

    yield

    # Shutdown
    await app.state.db_pool.close()
    await app.state.redis.close()
    await app.state.http_client.aclose()

app = FastAPI(lifespan=lifespan)


# Database connection context manager
@asynccontextmanager
async def get_db_connection() -> AsyncGenerator[asyncpg.Connection, None]:
    conn = await app.state.db_pool.acquire()
    try:
        yield conn
    finally:
        await app.state.db_pool.release(conn)

# Transaction context manager
@asynccontextmanager
async def transaction(conn: asyncpg.Connection):
    tr = conn.transaction()
    await tr.start()
    try:
        yield
        await tr.commit()
    except Exception:
        await tr.rollback()
        raise

@app.post("/transfer")
async def transfer_funds(from_id: int, to_id: int, amount: float):
    async with get_db_connection() as conn:
        async with transaction(conn):
            await conn.execute(
                "UPDATE accounts SET balance = balance - $1 WHERE id = $2",
                amount, from_id
            )
            await conn.execute(
                "UPDATE accounts SET balance = balance + $1 WHERE id = $2",
                amount, to_id
            )
    return {"status": "success"}


# HTTP client context manager
@asynccontextmanager
async def http_client_with_auth(token: str):
    async with httpx.AsyncClient(
        headers={"Authorization": f"Bearer {token}"},
        timeout=30.0
    ) as client:
        yield client

@app.get("/external-data")
async def get_external_data():
    async with http_client_with_auth("api-token") as client:
        response = await client.get("https://api.example.com/data")
        return response.json()


# Distributed lock context manager
@asynccontextmanager
async def distributed_lock(key: str, timeout: int = 10):
    lock_key = f"lock:{key}"
    lock_id = str(uuid.uuid4())

    # Acquire lock
    acquired = await app.state.redis.set(
        lock_key, lock_id, nx=True, ex=timeout
    )

    if not acquired:
        raise Exception("Could not acquire lock")

    try:
        yield
    finally:
        # Release lock (only if we own it)
        script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        await app.state.redis.eval(script, 1, lock_key, lock_id)

@app.post("/singleton-operation")
async def singleton_operation():
    async with distributed_lock("singleton-op"):
        # Only one instance runs at a time
        await perform_operation()
    return {"status": "done"}
```

### Concurrent Request Handling

```python
from fastapi import FastAPI
import asyncio
import httpx

app = FastAPI()

# Parallel external API calls
@app.get("/aggregate")
async def aggregate_data():
    async with httpx.AsyncClient() as client:
        # Run all requests concurrently
        results = await asyncio.gather(
            client.get("https://api1.example.com/data"),
            client.get("https://api2.example.com/data"),
            client.get("https://api3.example.com/data"),
            return_exceptions=True  # Don't fail all if one fails
        )

    # Process results
    data = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            data.append({"source": i, "error": str(result)})
        else:
            data.append({"source": i, "data": result.json()})

    return data


# Concurrent database operations
@app.get("/dashboard")
async def get_dashboard(db: AsyncSession = Depends(get_db)):
    # Run queries concurrently
    user_count, order_count, revenue = await asyncio.gather(
        db.scalar(select(func.count(User.id))),
        db.scalar(select(func.count(Order.id))),
        db.scalar(select(func.sum(Order.total)))
    )

    return {
        "users": user_count,
        "orders": order_count,
        "revenue": revenue
    }


# Timeout handling
@app.get("/with-timeout")
async def fetch_with_timeout():
    try:
        async with asyncio.timeout(5.0):  # Python 3.11+
            result = await slow_external_call()
            return {"result": result}
    except asyncio.TimeoutError:
        return {"error": "Request timed out"}


# For Python < 3.11
@app.get("/with-timeout-legacy")
async def fetch_with_timeout_legacy():
    try:
        result = await asyncio.wait_for(
            slow_external_call(),
            timeout=5.0
        )
        return {"result": result}
    except asyncio.TimeoutError:
        return {"error": "Request timed out"}


# Fan-out pattern with controlled concurrency
@app.post("/notify-all")
async def notify_all_users(message: str):
    users = await get_all_users()

    # Limit concurrent notifications to 10
    semaphore = asyncio.Semaphore(10)

    async def notify_with_semaphore(user):
        async with semaphore:
            return await send_notification(user, message)

    results = await asyncio.gather(
        *[notify_with_semaphore(user) for user in users],
        return_exceptions=True
    )

    success = sum(1 for r in results if not isinstance(r, Exception))
    return {"notified": success, "total": len(users)}


# Task groups (Python 3.11+)
@app.get("/task-group")
async def with_task_group():
    results = []

    async with asyncio.TaskGroup() as tg:
        for url in ["https://api1.com", "https://api2.com"]:
            tg.create_task(fetch_url(url))

    # All tasks complete here
    return {"status": "all done"}
```

### Asyncio Patterns in FastAPI

```python
from fastapi import FastAPI
import asyncio
from asyncio import Queue
from typing import AsyncIterator

app = FastAPI()

# Producer-Consumer pattern
class MessageQueue:
    def __init__(self):
        self.queue: Queue = asyncio.Queue()
        self.subscribers: list[Queue] = []

    async def publish(self, message: dict):
        for subscriber in self.subscribers:
            await subscriber.put(message)

    async def subscribe(self) -> AsyncIterator[dict]:
        queue = asyncio.Queue()
        self.subscribers.append(queue)
        try:
            while True:
                message = await queue.get()
                yield message
        finally:
            self.subscribers.remove(queue)

message_queue = MessageQueue()

@app.post("/publish")
async def publish_message(message: dict):
    await message_queue.publish(message)
    return {"status": "published"}

@app.get("/subscribe")
async def subscribe_to_messages():
    async def event_stream():
        async for message in message_queue.subscribe():
            yield f"data: {json.dumps(message)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream"
    )


# Event-based coordination
class AsyncEvent:
    def __init__(self):
        self._event = asyncio.Event()
        self._data = None

    async def wait(self, timeout: float = None):
        if timeout:
            await asyncio.wait_for(self._event.wait(), timeout)
        else:
            await self._event.wait()
        return self._data

    def set(self, data=None):
        self._data = data
        self._event.set()

    def clear(self):
        self._event.clear()
        self._data = None

pending_requests: dict[str, AsyncEvent] = {}

@app.post("/request/{request_id}")
async def create_request(request_id: str, data: dict):
    event = AsyncEvent()
    pending_requests[request_id] = event

    # Process asynchronously
    asyncio.create_task(process_request(request_id, data))

    return {"request_id": request_id, "status": "processing"}

@app.get("/request/{request_id}/result")
async def get_request_result(request_id: str):
    event = pending_requests.get(request_id)
    if not event:
        raise HTTPException(404, "Request not found")

    try:
        result = await asyncio.wait_for(event.wait(), timeout=30)
        return {"result": result}
    except asyncio.TimeoutError:
        return {"status": "still processing"}

async def process_request(request_id: str, data: dict):
    await asyncio.sleep(5)  # Simulate processing
    result = {"processed": data}

    if request_id in pending_requests:
        pending_requests[request_id].set(result)


# Periodic tasks
class PeriodicTask:
    def __init__(self, interval: float, func, *args, **kwargs):
        self.interval = interval
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self._task: asyncio.Task | None = None

    async def _run(self):
        while True:
            try:
                await self.func(*self.args, **self.kwargs)
            except Exception as e:
                logger.error(f"Periodic task error: {e}")
            await asyncio.sleep(self.interval)

    def start(self):
        self._task = asyncio.create_task(self._run())

    def stop(self):
        if self._task:
            self._task.cancel()

# Usage with lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start periodic tasks
    cleanup_task = PeriodicTask(3600, cleanup_old_data)
    health_check = PeriodicTask(60, check_dependencies)

    cleanup_task.start()
    health_check.start()

    yield

    cleanup_task.stop()
    health_check.stop()
```

### Managing Shared State

```python
from fastapi import FastAPI, Request
import asyncio
from dataclasses import dataclass, field
from typing import Dict, Any
import threading

app = FastAPI()

# Thread-safe state (for sync code mixed with async)
class ThreadSafeState:
    def __init__(self):
        self._lock = threading.Lock()
        self._data: Dict[str, Any] = {}

    def get(self, key: str, default=None):
        with self._lock:
            return self._data.get(key, default)

    def set(self, key: str, value: Any):
        with self._lock:
            self._data[key] = value

    def delete(self, key: str):
        with self._lock:
            self._data.pop(key, None)


# Async-safe state
class AsyncState:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._data: Dict[str, Any] = {}

    async def get(self, key: str, default=None):
        async with self._lock:
            return self._data.get(key, default)

    async def set(self, key: str, value: Any):
        async with self._lock:
            self._data[key] = value

    async def update(self, key: str, func):
        """Atomic read-modify-write"""
        async with self._lock:
            current = self._data.get(key)
            self._data[key] = func(current)
            return self._data[key]


# Rate limiter with shared state
@dataclass
class RateLimiterState:
    requests: Dict[str, list] = field(default_factory=dict)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def check_and_increment(
        self,
        key: str,
        max_requests: int,
        window_seconds: int
    ) -> bool:
        async with self.lock:
            now = time.time()
            cutoff = now - window_seconds

            # Clean old requests
            self.requests[key] = [
                t for t in self.requests.get(key, [])
                if t > cutoff
            ]

            if len(self.requests[key]) >= max_requests:
                return False

            self.requests[key].append(now)
            return True


# Application state management
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize shared state
    app.state.rate_limiter = RateLimiterState()
    app.state.cache = AsyncState()
    app.state.metrics = {
        "requests": 0,
        "errors": 0,
        "lock": asyncio.Lock()
    }

    yield

    # Cleanup if needed

app = FastAPI(lifespan=lifespan)

@app.middleware("http")
async def track_metrics(request: Request, call_next):
    async with request.app.state.metrics["lock"]:
        request.app.state.metrics["requests"] += 1

    try:
        response = await call_next(request)
        return response
    except Exception:
        async with request.app.state.metrics["lock"]:
            request.app.state.metrics["errors"] += 1
        raise

@app.get("/metrics")
async def get_metrics(request: Request):
    async with request.app.state.metrics["lock"]:
        return dict(request.app.state.metrics)
```

---

## 3.3 WebSockets

### WebSocket Endpoints

```python
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

app = FastAPI()

# Basic WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    try:
        while True:
            # Receive message
            data = await websocket.receive_text()

            # Process and respond
            response = f"You said: {data}"
            await websocket.send_text(response)

    except WebSocketDisconnect:
        print("Client disconnected")


# WebSocket with different message types
@app.websocket("/ws/typed")
async def typed_websocket(websocket: WebSocket):
    await websocket.accept()

    try:
        while True:
            # Can receive different types
            message = await websocket.receive()

            if message["type"] == "websocket.receive":
                if "text" in message:
                    # Text message
                    await websocket.send_text(f"Text: {message['text']}")
                elif "bytes" in message:
                    # Binary message
                    await websocket.send_bytes(message["bytes"])

    except WebSocketDisconnect:
        pass


# WebSocket with JSON
@app.websocket("/ws/json")
async def json_websocket(websocket: WebSocket):
    await websocket.accept()

    try:
        while True:
            data = await websocket.receive_json()

            # Process based on message type
            action = data.get("action")

            if action == "ping":
                await websocket.send_json({"action": "pong"})
            elif action == "echo":
                await websocket.send_json({"action": "echo", "data": data.get("data")})
            elif action == "subscribe":
                await websocket.send_json({"action": "subscribed", "channel": data.get("channel")})

    except WebSocketDisconnect:
        pass


# WebSocket with path parameters
@app.websocket("/ws/room/{room_id}")
async def room_websocket(websocket: WebSocket, room_id: str):
    await websocket.accept()
    await websocket.send_text(f"Connected to room: {room_id}")

    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"[{room_id}] {data}")
    except WebSocketDisconnect:
        pass


# WebSocket with query parameters
@app.websocket("/ws/chat")
async def chat_websocket(
    websocket: WebSocket,
    username: str = "anonymous",
    room: str = "general"
):
    await websocket.accept()
    await websocket.send_json({
        "type": "connected",
        "username": username,
        "room": room
    })

    try:
        while True:
            data = await websocket.receive_json()
            data["username"] = username
            data["room"] = room
            await websocket.send_json(data)
    except WebSocketDisconnect:
        pass
```

### Connection Management

```python
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import Dict, Set
import asyncio

app = FastAPI()

class ConnectionManager:
    def __init__(self):
        # All active connections
        self.active_connections: Dict[str, WebSocket] = {}
        # Room-based connections
        self.rooms: Dict[str, Set[str]] = {}
        # User metadata
        self.user_data: Dict[str, dict] = {}

    async def connect(
        self,
        websocket: WebSocket,
        client_id: str,
        user_data: dict = None
    ):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        self.user_data[client_id] = user_data or {}

    def disconnect(self, client_id: str):
        self.active_connections.pop(client_id, None)
        self.user_data.pop(client_id, None)

        # Remove from all rooms
        for room in self.rooms.values():
            room.discard(client_id)

    async def send_personal(self, client_id: str, message: dict):
        websocket = self.active_connections.get(client_id)
        if websocket:
            try:
                await websocket.send_json(message)
            except:
                self.disconnect(client_id)

    async def broadcast(self, message: dict, exclude: str = None):
        disconnected = []

        for client_id, websocket in self.active_connections.items():
            if client_id == exclude:
                continue
            try:
                await websocket.send_json(message)
            except:
                disconnected.append(client_id)

        for client_id in disconnected:
            self.disconnect(client_id)

    def join_room(self, client_id: str, room: str):
        if room not in self.rooms:
            self.rooms[room] = set()
        self.rooms[room].add(client_id)

    def leave_room(self, client_id: str, room: str):
        if room in self.rooms:
            self.rooms[room].discard(client_id)

    async def broadcast_to_room(
        self,
        room: str,
        message: dict,
        exclude: str = None
    ):
        if room not in self.rooms:
            return

        disconnected = []

        for client_id in self.rooms[room]:
            if client_id == exclude:
                continue

            websocket = self.active_connections.get(client_id)
            if websocket:
                try:
                    await websocket.send_json(message)
                except:
                    disconnected.append(client_id)

        for client_id in disconnected:
            self.disconnect(client_id)

    def get_room_members(self, room: str) -> list:
        if room not in self.rooms:
            return []
        return [
            {"client_id": cid, **self.user_data.get(cid, {})}
            for cid in self.rooms[room]
        ]

    @property
    def connection_count(self) -> int:
        return len(self.active_connections)


manager = ConnectionManager()


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(websocket, client_id)

    try:
        # Notify others
        await manager.broadcast(
            {"type": "user_joined", "client_id": client_id},
            exclude=client_id
        )

        while True:
            data = await websocket.receive_json()

            if data["type"] == "message":
                await manager.broadcast({
                    "type": "message",
                    "from": client_id,
                    "content": data["content"]
                })

            elif data["type"] == "join_room":
                manager.join_room(client_id, data["room"])
                await manager.broadcast_to_room(
                    data["room"],
                    {"type": "room_join", "user": client_id}
                )

            elif data["type"] == "room_message":
                await manager.broadcast_to_room(
                    data["room"],
                    {
                        "type": "room_message",
                        "room": data["room"],
                        "from": client_id,
                        "content": data["content"]
                    },
                    exclude=client_id
                )

    except WebSocketDisconnect:
        manager.disconnect(client_id)
        await manager.broadcast(
            {"type": "user_left", "client_id": client_id}
        )
```

### Broadcasting Patterns

```python
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import asyncio
from typing import Set, Dict
from dataclasses import dataclass, field
from enum import Enum

app = FastAPI()

# Pub/Sub pattern
class PubSubManager:
    def __init__(self):
        self.channels: Dict[str, Set[WebSocket]] = {}

    async def subscribe(self, websocket: WebSocket, channel: str):
        if channel not in self.channels:
            self.channels[channel] = set()
        self.channels[channel].add(websocket)

    def unsubscribe(self, websocket: WebSocket, channel: str = None):
        if channel:
            if channel in self.channels:
                self.channels[channel].discard(websocket)
        else:
            # Unsubscribe from all
            for ch in self.channels.values():
                ch.discard(websocket)

    async def publish(self, channel: str, message: dict):
        if channel not in self.channels:
            return

        dead_connections = set()

        for websocket in self.channels[channel]:
            try:
                await websocket.send_json({
                    "channel": channel,
                    "data": message
                })
            except:
                dead_connections.add(websocket)

        # Clean up dead connections
        self.channels[channel] -= dead_connections

    async def publish_pattern(self, pattern: str, message: dict):
        """Publish to channels matching pattern (e.g., 'user.*')"""
        import fnmatch

        for channel in self.channels.keys():
            if fnmatch.fnmatch(channel, pattern):
                await self.publish(channel, message)


pubsub = PubSubManager()


@app.websocket("/ws/pubsub")
async def pubsub_endpoint(websocket: WebSocket):
    await websocket.accept()

    try:
        while True:
            data = await websocket.receive_json()

            if data["action"] == "subscribe":
                await pubsub.subscribe(websocket, data["channel"])
                await websocket.send_json({
                    "action": "subscribed",
                    "channel": data["channel"]
                })

            elif data["action"] == "unsubscribe":
                pubsub.unsubscribe(websocket, data["channel"])
                await websocket.send_json({
                    "action": "unsubscribed",
                    "channel": data["channel"]
                })

            elif data["action"] == "publish":
                await pubsub.publish(data["channel"], data["message"])

    except WebSocketDisconnect:
        pubsub.unsubscribe(websocket)


# HTTP endpoint to publish
@app.post("/publish/{channel}")
async def publish_message(channel: str, message: dict):
    await pubsub.publish(channel, message)
    return {"status": "published", "channel": channel}


# Fan-out with backpressure
class BroadcastManager:
    def __init__(self, max_queue_size: int = 100):
        self.connections: Set[WebSocket] = set()
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        self._broadcaster_task = None

    async def start(self):
        self._broadcaster_task = asyncio.create_task(self._broadcast_loop())

    async def stop(self):
        if self._broadcaster_task:
            self._broadcaster_task.cancel()

    async def add_connection(self, websocket: WebSocket):
        await websocket.accept()
        self.connections.add(websocket)

    def remove_connection(self, websocket: WebSocket):
        self.connections.discard(websocket)

    async def queue_broadcast(self, message: dict):
        try:
            self.queue.put_nowait(message)
        except asyncio.QueueFull:
            # Handle backpressure - drop oldest or reject
            _ = self.queue.get_nowait()
            await self.queue.put(message)

    async def _broadcast_loop(self):
        while True:
            message = await self.queue.get()
            dead = set()

            # Broadcast with timeout per connection
            for ws in self.connections:
                try:
                    await asyncio.wait_for(
                        ws.send_json(message),
                        timeout=1.0
                    )
                except:
                    dead.add(ws)

            self.connections -= dead


broadcast_manager = BroadcastManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await broadcast_manager.start()
    yield
    await broadcast_manager.stop()
```

### Authentication in WebSockets

```python
from fastapi import (
    FastAPI, WebSocket, WebSocketDisconnect,
    Depends, HTTPException, Query, status
)
from fastapi.security import OAuth2PasswordBearer
import jwt

app = FastAPI()

SECRET_KEY = "your-secret-key"

# Method 1: Query parameter token
async def get_token_from_query(
    token: str = Query(...)
) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


@app.websocket("/ws/auth")
async def authenticated_websocket(
    websocket: WebSocket,
    token: str = Query(...)
):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("sub")
    except jwt.InvalidTokenError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()

    try:
        await websocket.send_json({
            "type": "authenticated",
            "user_id": user_id
        })

        while True:
            data = await websocket.receive_json()
            await websocket.send_json({
                "user_id": user_id,
                "received": data
            })
    except WebSocketDisconnect:
        pass


# Method 2: First message authentication
@app.websocket("/ws/auth-first-message")
async def auth_first_message(websocket: WebSocket):
    await websocket.accept()

    try:
        # Wait for auth message with timeout
        auth_data = await asyncio.wait_for(
            websocket.receive_json(),
            timeout=10.0
        )

        if auth_data.get("type") != "auth":
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        token = auth_data.get("token")
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            user_id = payload["sub"]
        except:
            await websocket.send_json({"type": "auth_failed"})
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        await websocket.send_json({"type": "auth_success", "user_id": user_id})

        # Normal message loop
        while True:
            data = await websocket.receive_json()
            await websocket.send_json({"echo": data})

    except asyncio.TimeoutError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
    except WebSocketDisconnect:
        pass


# Method 3: Cookie authentication
@app.websocket("/ws/auth-cookie")
async def auth_cookie(websocket: WebSocket):
    # Get cookie from websocket headers
    cookies = websocket.cookies
    session_token = cookies.get("session")

    if not session_token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Validate session
    user = await validate_session(session_token)
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()

    try:
        while True:
            data = await websocket.receive_json()
            await websocket.send_json({"user": user["id"], "data": data})
    except WebSocketDisconnect:
        pass


# Method 4: Subprotocol authentication
@app.websocket("/ws/auth-subprotocol")
async def auth_subprotocol(websocket: WebSocket):
    # Token passed as subprotocol
    # Client: new WebSocket(url, ['token', 'Bearer xxx'])
    subprotocols = websocket.scope.get("subprotocols", [])

    token = None
    for i, proto in enumerate(subprotocols):
        if proto.lower() == "bearer" and i + 1 < len(subprotocols):
            token = subprotocols[i + 1]
            break

    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept(subprotocol="bearer")

    # Continue with authenticated connection
    ...
```

### Handling Disconnections

```python
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import asyncio
from enum import IntEnum

app = FastAPI()

class CloseCode(IntEnum):
    NORMAL = 1000
    GOING_AWAY = 1001
    PROTOCOL_ERROR = 1002
    UNSUPPORTED = 1003
    NO_STATUS = 1005
    ABNORMAL = 1006
    INVALID_DATA = 1007
    POLICY_VIOLATION = 1008
    MESSAGE_TOO_BIG = 1009
    EXTENSION_ERROR = 1010
    INTERNAL_ERROR = 1011
    SERVICE_RESTART = 1012
    TRY_AGAIN_LATER = 1013
    BAD_GATEWAY = 1014


# Graceful disconnection handling
@app.websocket("/ws/graceful")
async def graceful_websocket(websocket: WebSocket):
    await websocket.accept()
    client_id = str(uuid.uuid4())

    try:
        # Register connection
        await register_connection(client_id, websocket)

        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=30.0  # Heartbeat timeout
                )

                if data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                else:
                    await process_message(data)

            except asyncio.TimeoutError:
                # Send ping to check if alive
                try:
                    await websocket.send_json({"type": "ping"})
                except:
                    break

    except WebSocketDisconnect as e:
        # Access close code and reason
        print(f"Client {client_id} disconnected: code={e.code}")

    finally:
        # Always clean up
        await unregister_connection(client_id)
        await notify_disconnection(client_id)


# Reconnection support
class ReconnectionManager:
    def __init__(self, timeout: int = 300):
        self.timeout = timeout
        self.sessions: Dict[str, dict] = {}

    async def save_session(self, session_id: str, state: dict):
        self.sessions[session_id] = {
            "state": state,
            "expires": time.time() + self.timeout
        }

    async def restore_session(self, session_id: str) -> dict | None:
        session = self.sessions.get(session_id)
        if session and session["expires"] > time.time():
            return session["state"]
        self.sessions.pop(session_id, None)
        return None

    async def cleanup(self):
        now = time.time()
        expired = [
            sid for sid, s in self.sessions.items()
            if s["expires"] < now
        ]
        for sid in expired:
            del self.sessions[sid]


reconnection = ReconnectionManager()


@app.websocket("/ws/reconnect")
async def reconnectable_websocket(
    websocket: WebSocket,
    session_id: str = Query(None)
):
    await websocket.accept()

    # Try to restore previous session
    state = None
    if session_id:
        state = await reconnection.restore_session(session_id)
        if state:
            await websocket.send_json({
                "type": "session_restored",
                "state": state
            })

    if not session_id:
        session_id = str(uuid.uuid4())

    await websocket.send_json({
        "type": "connected",
        "session_id": session_id
    })

    current_state = state or {"messages": []}

    try:
        while True:
            data = await websocket.receive_json()
            current_state["messages"].append(data)
            await websocket.send_json({"type": "ack", "data": data})

    except WebSocketDisconnect:
        # Save state for potential reconnection
        await reconnection.save_session(session_id, current_state)


# Connection health monitoring
class HealthMonitor:
    def __init__(self):
        self.connections: Dict[str, dict] = {}

    async def start_monitoring(self, client_id: str, websocket: WebSocket):
        self.connections[client_id] = {
            "websocket": websocket,
            "last_ping": time.time(),
            "missed_pings": 0
        }

    async def record_activity(self, client_id: str):
        if client_id in self.connections:
            self.connections[client_id]["last_ping"] = time.time()
            self.connections[client_id]["missed_pings"] = 0

    async def check_health(self):
        """Run periodically to check connection health"""
        now = time.time()
        dead_connections = []

        for client_id, conn in self.connections.items():
            if now - conn["last_ping"] > 60:  # 60 seconds timeout
                conn["missed_pings"] += 1

                if conn["missed_pings"] >= 3:
                    dead_connections.append(client_id)
                else:
                    # Try to ping
                    try:
                        await conn["websocket"].send_json({"type": "ping"})
                    except:
                        dead_connections.append(client_id)

        for client_id in dead_connections:
            conn = self.connections.pop(client_id, None)
            if conn:
                try:
                    await conn["websocket"].close(
                        code=CloseCode.GOING_AWAY
                    )
                except:
                    pass
```

### Scaling WebSocket Connections

```python
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import redis.asyncio as redis
import json
import asyncio
from typing import Set

app = FastAPI()

# Redis pub/sub for cross-instance communication
class DistributedWebSocketManager:
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.redis: redis.Redis | None = None
        self.pubsub: redis.client.PubSub | None = None
        self.local_connections: dict[str, WebSocket] = {}
        self.subscriptions: dict[str, Set[str]] = {}  # channel -> client_ids
        self._listener_task = None

    async def connect(self):
        self.redis = await redis.from_url(self.redis_url)
        self.pubsub = self.redis.pubsub()
        self._listener_task = asyncio.create_task(self._listen())

    async def disconnect(self):
        if self._listener_task:
            self._listener_task.cancel()
        if self.pubsub:
            await self.pubsub.close()
        if self.redis:
            await self.redis.close()

    async def _listen(self):
        """Listen for messages from other instances"""
        await self.pubsub.psubscribe("ws:*")

        async for message in self.pubsub.listen():
            if message["type"] == "pmessage":
                channel = message["channel"].decode().replace("ws:", "")
                data = json.loads(message["data"])
                await self._deliver_local(channel, data)

    async def _deliver_local(self, channel: str, data: dict):
        """Deliver message to local connections"""
        client_ids = self.subscriptions.get(channel, set())

        for client_id in client_ids:
            websocket = self.local_connections.get(client_id)
            if websocket:
                try:
                    await websocket.send_json(data)
                except:
                    await self.remove_connection(client_id)

    async def add_connection(self, client_id: str, websocket: WebSocket):
        await websocket.accept()
        self.local_connections[client_id] = websocket

        # Register in Redis for presence
        await self.redis.sadd("ws:online", client_id)

    async def remove_connection(self, client_id: str):
        self.local_connections.pop(client_id, None)

        # Remove from all local subscriptions
        for clients in self.subscriptions.values():
            clients.discard(client_id)

        # Remove from Redis
        await self.redis.srem("ws:online", client_id)

    async def subscribe(self, client_id: str, channel: str):
        if channel not in self.subscriptions:
            self.subscriptions[channel] = set()
        self.subscriptions[channel].add(client_id)

    async def publish(self, channel: str, message: dict):
        # Publish to Redis - all instances receive it
        await self.redis.publish(
            f"ws:{channel}",
            json.dumps(message)
        )

    async def get_online_users(self) -> Set[str]:
        return await self.redis.smembers("ws:online")


ws_manager = DistributedWebSocketManager("redis://localhost:6379")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await ws_manager.connect()
    yield
    await ws_manager.disconnect()

app = FastAPI(lifespan=lifespan)


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await ws_manager.add_connection(client_id, websocket)

    try:
        while True:
            data = await websocket.receive_json()

            if data["action"] == "subscribe":
                await ws_manager.subscribe(client_id, data["channel"])

            elif data["action"] == "publish":
                await ws_manager.publish(data["channel"], {
                    "from": client_id,
                    "message": data["message"]
                })

    except WebSocketDisconnect:
        await ws_manager.remove_connection(client_id)


# Sticky sessions alternative - route to specific instance
# Requires load balancer configuration (e.g., NGINX ip_hash)
# or connection ID-based routing
```

---

## 3.4 Server-Sent Events (SSE)

### Implementing SSE Endpoints

```python
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
import asyncio
import json
from datetime import datetime

app = FastAPI()

# Basic SSE endpoint
@app.get("/events")
async def event_stream():
    async def generate():
        while True:
            data = {"time": datetime.utcnow().isoformat()}
            yield f"data: {json.dumps(data)}\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


# SSE with event types and IDs
@app.get("/events/typed")
async def typed_events():
    async def generate():
        event_id = 0

        while True:
            event_id += 1

            # Different event types
            yield f"id: {event_id}\n"
            yield f"event: heartbeat\n"
            yield f"data: {json.dumps({'time': datetime.utcnow().isoformat()})}\n\n"

            await asyncio.sleep(1)

            event_id += 1
            yield f"id: {event_id}\n"
            yield f"event: update\n"
            yield f"data: {json.dumps({'value': event_id})}\n\n"

            await asyncio.sleep(1)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream"
    )


# SSE with retry directive
@app.get("/events/retry")
async def events_with_retry():
    async def generate():
        # Tell client to retry after 5 seconds if disconnected
        yield "retry: 5000\n\n"

        while True:
            yield f"data: {datetime.utcnow().isoformat()}\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream"
    )


# SSE endpoint with parameters
@app.get("/events/channel/{channel}")
async def channel_events(channel: str, request: Request):
    async def generate():
        # Get last event ID for resumption
        last_id = request.headers.get("Last-Event-ID")
        event_id = int(last_id) if last_id else 0

        while True:
            # Check if client disconnected
            if await request.is_disconnected():
                break

            event_id += 1
            event = {
                "channel": channel,
                "id": event_id,
                "timestamp": datetime.utcnow().isoformat()
            }

            yield f"id: {event_id}\n"
            yield f"event: message\n"
            yield f"data: {json.dumps(event)}\n\n"

            await asyncio.sleep(1)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream"
    )
```

### Event Formatting

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import json
from dataclasses import dataclass
from typing import Optional

app = FastAPI()

@dataclass
class SSEEvent:
    data: str
    event: Optional[str] = None
    id: Optional[str] = None
    retry: Optional[int] = None

    def encode(self) -> str:
        lines = []

        if self.id is not None:
            lines.append(f"id: {self.id}")

        if self.event is not None:
            lines.append(f"event: {self.event}")

        if self.retry is not None:
            lines.append(f"retry: {self.retry}")

        # Data can be multi-line
        for line in self.data.split("\n"):
            lines.append(f"data: {line}")

        # Events separated by blank line
        lines.append("")
        lines.append("")

        return "\n".join(lines)


def format_sse(
    data: dict | str,
    event: str = None,
    id: str = None,
    retry: int = None
) -> str:
    """Helper function to format SSE messages"""
    if isinstance(data, dict):
        data = json.dumps(data)

    return SSEEvent(
        data=data,
        event=event,
        id=id,
        retry=retry
    ).encode()


# Usage
@app.get("/events/formatted")
async def formatted_events():
    async def generate():
        # Initial retry setting
        yield format_sse({"type": "connected"}, retry=5000)

        event_id = 0
        while True:
            event_id += 1

            # Regular event
            yield format_sse(
                {"message": f"Event {event_id}"},
                event="message",
                id=str(event_id)
            )

            await asyncio.sleep(1)

            # Status event
            yield format_sse(
                {"status": "active", "connections": 42},
                event="status"
            )

            await asyncio.sleep(1)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream"
    )


# Multi-line data
@app.get("/events/multiline")
async def multiline_events():
    async def generate():
        log_entry = """Line 1: Starting process
Line 2: Processing data
Line 3: Complete"""

        yield format_sse(log_entry, event="log")

        # JSON with pretty print
        data = {
            "users": [
                {"id": 1, "name": "Alice"},
                {"id": 2, "name": "Bob"}
            ]
        }
        yield format_sse(
            json.dumps(data, indent=2),
            event="data"
        )

    return StreamingResponse(
        generate(),
        media_type="text/event-stream"
    )
```

### Client Reconnection Handling

```python
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
import asyncio
import json
from collections import deque
from typing import Deque
from dataclasses import dataclass, field
from datetime import datetime

app = FastAPI()

# Event history for reconnection
@dataclass
class EventHistory:
    max_events: int = 1000
    events: Deque = field(default_factory=deque)
    current_id: int = 0

    def add_event(self, event_type: str, data: dict) -> int:
        self.current_id += 1
        self.events.append({
            "id": self.current_id,
            "type": event_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        })

        # Trim old events
        while len(self.events) > self.max_events:
            self.events.popleft()

        return self.current_id

    def get_events_since(self, last_id: int) -> list:
        return [e for e in self.events if e["id"] > last_id]


history = EventHistory()


# Background task to generate events
async def event_generator():
    while True:
        event_type = "update"
        data = {"value": datetime.utcnow().timestamp()}
        history.add_event(event_type, data)
        await asyncio.sleep(1)

@app.on_event("startup")
async def start_generator():
    asyncio.create_task(event_generator())


@app.get("/events/resumable")
async def resumable_events(request: Request):
    # Get Last-Event-ID from header
    last_event_id = request.headers.get("Last-Event-ID")
    last_id = int(last_event_id) if last_event_id else 0

    async def generate():
        # Send any missed events
        missed_events = history.get_events_since(last_id)
        for event in missed_events:
            yield f"id: {event['id']}\n"
            yield f"event: {event['type']}\n"
            yield f"data: {json.dumps(event['data'])}\n\n"

        # Continue with live events
        current_id = history.current_id

        while True:
            if await request.is_disconnected():
                break

            # Check for new events
            new_events = history.get_events_since(current_id)
            for event in new_events:
                yield f"id: {event['id']}\n"
                yield f"event: {event['type']}\n"
                yield f"data: {json.dumps(event['data'])}\n\n"
                current_id = event["id"]

            await asyncio.sleep(0.1)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )


# Per-client event streams with replay
class ClientEventStream:
    def __init__(self, client_id: str):
        self.client_id = client_id
        self.queue: asyncio.Queue = asyncio.Queue()
        self.last_event_id: int = 0
        self.connected: bool = False

    async def send(self, event_id: int, event_type: str, data: dict):
        await self.queue.put({
            "id": event_id,
            "type": event_type,
            "data": data
        })

client_streams: dict[str, ClientEventStream] = {}

@app.get("/events/client/{client_id}")
async def client_events(client_id: str, request: Request):
    # Get or create client stream
    if client_id not in client_streams:
        client_streams[client_id] = ClientEventStream(client_id)

    stream = client_streams[client_id]

    # Handle reconnection
    last_id = request.headers.get("Last-Event-ID")
    if last_id:
        # Replay missed events from history
        missed = history.get_events_since(int(last_id))
        for event in missed:
            await stream.queue.put(event)

    stream.connected = True

    async def generate():
        try:
            while True:
                if await request.is_disconnected():
                    break

                try:
                    event = await asyncio.wait_for(
                        stream.queue.get(),
                        timeout=30.0
                    )
                    yield f"id: {event['id']}\n"
                    yield f"event: {event['type']}\n"
                    yield f"data: {json.dumps(event['data'])}\n\n"
                    stream.last_event_id = event["id"]

                except asyncio.TimeoutError:
                    # Send keepalive
                    yield ": keepalive\n\n"

        finally:
            stream.connected = False

    return StreamingResponse(
        generate(),
        media_type="text/event-stream"
    )
```

### Use Cases vs WebSockets

```python
"""
SSE vs WebSocket Decision Guide

Use SSE when:
- Server-to-client only communication
- Simple event streaming (notifications, updates, logs)
- Auto-reconnection is important (built into SSE)
- Need to work through HTTP/1.1 proxies
- Simpler protocol (text-based, no framing)

Use WebSockets when:
- Bidirectional communication needed
- Low latency is critical
- Binary data transfer
- Complex protocols (gaming, chat with typing indicators)
- Need to send data from client frequently
"""

from fastapi import FastAPI, WebSocket
from fastapi.responses import StreamingResponse
import asyncio

app = FastAPI()

# Example: Live Dashboard (SSE is better)
# - Server pushes metrics to clients
# - Clients just display data
# - Auto-reconnect on network issues

@app.get("/dashboard/metrics")
async def dashboard_metrics():
    async def generate():
        yield "retry: 5000\n\n"  # Auto-reconnect

        while True:
            metrics = await get_current_metrics()
            yield f"event: metrics\n"
            yield f"data: {json.dumps(metrics)}\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream"
    )


# Example: Chat Application (WebSocket is better)
# - Users send and receive messages
# - Typing indicators
# - Low latency needed

@app.websocket("/chat/{room}")
async def chat_room(websocket: WebSocket, room: str):
    await websocket.accept()

    try:
        while True:
            data = await websocket.receive_json()

            if data["type"] == "message":
                await broadcast_to_room(room, data)
            elif data["type"] == "typing":
                await broadcast_typing(room, data["user"])

    except WebSocketDisconnect:
        await notify_left(room)


# Example: Log Streaming (SSE is better)
# - Server sends log entries
# - Client displays in real-time
# - Need resumption from last position

@app.get("/logs/stream")
async def stream_logs(request: Request):
    last_id = request.headers.get("Last-Event-ID")

    async def generate():
        position = int(last_id) if last_id else 0

        # Catch up on missed logs
        for log in get_logs_since(position):
            yield f"id: {log['id']}\n"
            yield f"data: {json.dumps(log)}\n\n"

        # Stream new logs
        async for log in tail_logs():
            yield f"id: {log['id']}\n"
            yield f"data: {json.dumps(log)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream"
    )


# Example: Collaborative Editing (WebSocket is better)
# - Users send cursor positions
# - Real-time text changes
# - Conflict resolution needs bidirectional

@app.websocket("/doc/{doc_id}")
async def collaborative_doc(websocket: WebSocket, doc_id: str):
    await websocket.accept()

    try:
        while True:
            data = await websocket.receive_json()

            if data["type"] == "cursor":
                await broadcast_cursor(doc_id, data)
            elif data["type"] == "change":
                resolved = resolve_conflict(data)
                await broadcast_change(doc_id, resolved)
                # Send acknowledgment
                await websocket.send_json({"type": "ack", "id": data["id"]})

    except WebSocketDisconnect:
        pass


# Hybrid approach: SSE for updates, POST for commands
@app.get("/hybrid/events")
async def hybrid_events():
    async def generate():
        async for event in event_stream():
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream"
    )

@app.post("/hybrid/command")
async def hybrid_command(command: dict):
    # Process command
    result = await process_command(command)

    # Event will be pushed via SSE to all clients
    await publish_event({"type": "update", "data": result})

    return {"status": "ok"}
```

---

## Summary

Module 3 covered advanced request handling patterns:

1. **Middleware** - Custom middleware creation, ordering, request/response modification, exception handling, timing/logging, and authentication patterns

2. **Background Tasks & Async** - Background tasks, task queues (Celery/ARQ), async context managers, concurrent handling, asyncio patterns, and shared state management

3. **WebSockets** - Endpoints, connection management, broadcasting, authentication, disconnection handling, and scaling strategies

4. **Server-Sent Events** - Implementation, event formatting, reconnection handling, and comparison with WebSockets

These patterns enable building real-time, scalable, and robust FastAPI applications.

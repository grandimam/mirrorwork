# Module 7: Production Architecture

---

## 7.1 Application Structure

### Project Layout Patterns

```
# Flat structure (small projects)
myapp/
├── main.py
├── models.py
├── schemas.py
├── crud.py
├── database.py
├── dependencies.py
├── config.py
└── utils.py


# Modular structure (medium projects)
myapp/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── dependencies.py
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── v1/
│   │   │   ├── __init__.py
│   │   │   ├── router.py
│   │   │   ├── users.py
│   │   │   ├── items.py
│   │   │   └── orders.py
│   │   └── deps.py
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── security.py
│   │   ├── config.py
│   │   └── exceptions.py
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── item.py
│   │   └── order.py
│   │
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── item.py
│   │   └── order.py
│   │
│   └── services/
│       ├── __init__.py
│       ├── user_service.py
│       └── email_service.py
│
├── tests/
├── alembic/
├── requirements.txt
└── pyproject.toml


# Domain-driven structure (large projects)
myapp/
├── src/
│   └── myapp/
│       ├── __init__.py
│       ├── main.py
│       ├── config.py
│       │
│       ├── shared/
│       │   ├── __init__.py
│       │   ├── database.py
│       │   ├── dependencies.py
│       │   ├── exceptions.py
│       │   └── middleware.py
│       │
│       ├── users/
│       │   ├── __init__.py
│       │   ├── router.py
│       │   ├── models.py
│       │   ├── schemas.py
│       │   ├── service.py
│       │   ├── repository.py
│       │   └── exceptions.py
│       │
│       ├── orders/
│       │   ├── __init__.py
│       │   ├── router.py
│       │   ├── models.py
│       │   ├── schemas.py
│       │   ├── service.py
│       │   ├── repository.py
│       │   └── events.py
│       │
│       └── payments/
│           ├── __init__.py
│           ├── router.py
│           ├── models.py
│           ├── schemas.py
│           ├── service.py
│           └── gateway.py
│
├── tests/
│   ├── conftest.py
│   ├── users/
│   ├── orders/
│   └── payments/
│
├── alembic/
├── docker/
├── scripts/
└── pyproject.toml
```

```python
# src/myapp/main.py - Application factory pattern
from fastapi import FastAPI
from contextlib import asynccontextmanager

from myapp.config import settings
from myapp.shared.database import init_db, close_db
from myapp.shared.middleware import setup_middleware
from myapp.shared.exceptions import setup_exception_handlers


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup
        await init_db()
        yield
        # Shutdown
        await close_db()

    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )

    setup_middleware(app)
    setup_exception_handlers(app)
    setup_routes(app)

    return app


def setup_routes(app: FastAPI):
    from myapp.users.router import router as users_router
    from myapp.orders.router import router as orders_router
    from myapp.payments.router import router as payments_router

    app.include_router(users_router, prefix="/api/v1/users", tags=["users"])
    app.include_router(orders_router, prefix="/api/v1/orders", tags=["orders"])
    app.include_router(payments_router, prefix="/api/v1/payments", tags=["payments"])


app = create_app()
```

### Router Organization

```python
# api/v1/router.py - Central router
from fastapi import APIRouter

from .users import router as users_router
from .items import router as items_router
from .orders import router as orders_router

api_router = APIRouter()

api_router.include_router(users_router, prefix="/users", tags=["users"])
api_router.include_router(items_router, prefix="/items", tags=["items"])
api_router.include_router(orders_router, prefix="/orders", tags=["orders"])


# api/v1/users.py - Users router
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_user
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.services.user_service import UserService

router = APIRouter()


def get_user_service(db: AsyncSession = Depends(get_db)) -> UserService:
    return UserService(db)


@router.get("/", response_model=List[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    service: UserService = Depends(get_user_service)
):
    return await service.get_users(skip=skip, limit=limit)


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user: UserCreate,
    service: UserService = Depends(get_user_service)
):
    return await service.create_user(user)


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user = Depends(get_current_user)
):
    return current_user


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    service: UserService = Depends(get_user_service)
):
    user = await service.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_update: UserUpdate,
    current_user = Depends(get_current_user),
    service: UserService = Depends(get_user_service)
):
    if current_user.id != user_id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")
    return await service.update_user(user_id, user_update)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    current_user = Depends(get_current_user),
    service: UserService = Depends(get_user_service)
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin required")
    await service.delete_user(user_id)


# Nested routers
@router.get("/{user_id}/orders", response_model=List[OrderResponse])
async def get_user_orders(
    user_id: int,
    service: UserService = Depends(get_user_service)
):
    return await service.get_user_orders(user_id)
```

### Settings Management with pydantic-settings

```python
# core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, SecretStr, PostgresDsn, RedisDsn, validator
from typing import List, Optional
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Application
    app_name: str = "MyApp"
    version: str = "1.0.0"
    debug: bool = False
    environment: str = Field(default="development", alias="ENV")

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4
    reload: bool = False

    # Database
    database_url: PostgresDsn
    database_pool_size: int = 5
    database_max_overflow: int = 10
    database_pool_recycle: int = 3600

    # Redis
    redis_url: RedisDsn
    redis_max_connections: int = 10

    # Security
    secret_key: SecretStr
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # CORS
    cors_origins: List[str] = ["http://localhost:3000"]
    cors_allow_credentials: bool = True

    # External Services
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[SecretStr] = None
    smtp_from_email: str = "noreply@example.com"

    sentry_dsn: Optional[str] = None
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[SecretStr] = None
    aws_region: str = "us-east-1"
    s3_bucket: Optional[str] = None

    # Feature flags
    enable_docs: bool = True
    enable_metrics: bool = True
    enable_rate_limiting: bool = True

    @validator("cors_origins", pre=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    @property
    def database_url_async(self) -> str:
        """Convert sync URL to async"""
        url = str(self.database_url)
        return url.replace("postgresql://", "postgresql+asyncpg://")


# Environment-specific settings
class DevelopmentSettings(Settings):
    debug: bool = True
    reload: bool = True
    enable_docs: bool = True


class ProductionSettings(Settings):
    debug: bool = False
    reload: bool = False
    workers: int = 4
    enable_docs: bool = False


class TestSettings(Settings):
    database_url: PostgresDsn = "postgresql://test:test@localhost/test"
    redis_url: RedisDsn = "redis://localhost:6379/1"


def get_settings_class():
    import os
    env = os.getenv("ENVIRONMENT", "development")
    settings_map = {
        "development": DevelopmentSettings,
        "production": ProductionSettings,
        "test": TestSettings
    }
    return settings_map.get(env, Settings)


@lru_cache
def get_settings() -> Settings:
    settings_class = get_settings_class()
    return settings_class()


settings = get_settings()
```

### Environment-Based Configuration

```python
# config/environments/__init__.py
import os
from pathlib import Path

# Determine environment
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# Load environment-specific .env file
ENV_FILE = Path(__file__).parent.parent.parent / f".env.{ENVIRONMENT}"
if not ENV_FILE.exists():
    ENV_FILE = Path(__file__).parent.parent.parent / ".env"


# config/base.py - Base configuration
from pydantic_settings import BaseSettings

class BaseConfig(BaseSettings):
    # Common settings for all environments
    app_name: str = "MyApp"
    api_prefix: str = "/api/v1"
    timezone: str = "UTC"


# config/development.py
class DevelopmentConfig(BaseConfig):
    debug: bool = True
    log_level: str = "DEBUG"
    database_echo: bool = True
    cors_origins: list = ["*"]


# config/production.py
class ProductionConfig(BaseConfig):
    debug: bool = False
    log_level: str = "INFO"
    database_echo: bool = False
    cors_origins: list = []  # Set from env


# config/testing.py
class TestingConfig(BaseConfig):
    testing: bool = True
    database_url: str = "sqlite:///./test.db"


# config/__init__.py - Config loader
import os

def load_config():
    env = os.getenv("ENVIRONMENT", "development")

    configs = {
        "development": DevelopmentConfig,
        "production": ProductionConfig,
        "testing": TestingConfig
    }

    config_class = configs.get(env, DevelopmentConfig)
    return config_class()

config = load_config()


# Usage with different .env files
"""
# .env.development
DEBUG=true
DATABASE_URL=postgresql://dev:dev@localhost/devdb
REDIS_URL=redis://localhost:6379/0

# .env.production
DEBUG=false
DATABASE_URL=postgresql://prod:prod@db.example.com/proddb
REDIS_URL=redis://redis.example.com:6379/0

# .env.testing
DEBUG=true
DATABASE_URL=sqlite:///./test.db
REDIS_URL=redis://localhost:6379/1
"""


# Docker environment handling
"""
# docker-compose.yml
services:
  api:
    build: .
    environment:
      - ENVIRONMENT=production
    env_file:
      - .env.production

  api-dev:
    build: .
    environment:
      - ENVIRONMENT=development
    env_file:
      - .env.development
"""
```

### Feature Flags

```python
from pydantic_settings import BaseSettings
from typing import Dict, Any, Optional
from functools import lru_cache
import json
import redis.asyncio as redis

# Simple boolean feature flags
class FeatureFlags(BaseSettings):
    # Feature toggles
    enable_new_checkout: bool = False
    enable_dark_mode: bool = True
    enable_beta_features: bool = False
    enable_experimental_api: bool = False

    # Percentage rollouts
    new_algorithm_percentage: int = 0  # 0-100


# Usage in endpoints
from fastapi import Depends, HTTPException

def require_feature(feature_name: str):
    def dependency(flags: FeatureFlags = Depends(get_feature_flags)):
        if not getattr(flags, feature_name, False):
            raise HTTPException(404, "Feature not available")
    return dependency


@app.get("/beta/feature")
async def beta_feature(_: None = Depends(require_feature("enable_beta_features"))):
    return {"feature": "beta"}


# Percentage-based rollout
import hashlib

def is_feature_enabled_for_user(feature: str, user_id: int, percentage: int) -> bool:
    if percentage == 0:
        return False
    if percentage == 100:
        return True

    # Consistent hashing for user
    hash_input = f"{feature}:{user_id}"
    hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
    return (hash_value % 100) < percentage


@app.get("/new-algorithm")
async def new_algorithm(
    current_user = Depends(get_current_user),
    flags: FeatureFlags = Depends(get_feature_flags)
):
    if is_feature_enabled_for_user(
        "new_algorithm",
        current_user.id,
        flags.new_algorithm_percentage
    ):
        return {"algorithm": "new"}
    return {"algorithm": "old"}


# Remote feature flag service
class RemoteFeatureFlagService:
    def __init__(self, redis: redis.Redis):
        self.redis = redis
        self.cache_ttl = 60  # seconds

    async def is_enabled(self, feature: str) -> bool:
        value = await self.redis.get(f"feature:{feature}")
        return value == "true"

    async def get_percentage(self, feature: str) -> int:
        value = await self.redis.get(f"feature:{feature}:percentage")
        return int(value) if value else 0

    async def is_enabled_for_user(
        self,
        feature: str,
        user_id: int,
        attributes: Dict[str, Any] = None
    ) -> bool:
        # Check if globally enabled
        if not await self.is_enabled(feature):
            return False

        # Check percentage rollout
        percentage = await self.get_percentage(feature)
        if percentage < 100:
            if not is_feature_enabled_for_user(feature, user_id, percentage):
                return False

        # Check user attributes (beta users, regions, etc.)
        if attributes:
            rules = await self.redis.get(f"feature:{feature}:rules")
            if rules:
                return self._evaluate_rules(json.loads(rules), attributes)

        return True

    async def set_flag(self, feature: str, enabled: bool, percentage: int = 100):
        await self.redis.set(f"feature:{feature}", "true" if enabled else "false")
        await self.redis.set(f"feature:{feature}:percentage", str(percentage))


# Admin endpoint to manage flags
@app.post("/admin/features/{feature}")
async def set_feature_flag(
    feature: str,
    enabled: bool,
    percentage: int = 100,
    admin_user = Depends(require_admin),
    flag_service: RemoteFeatureFlagService = Depends(get_flag_service)
):
    await flag_service.set_flag(feature, enabled, percentage)
    return {"feature": feature, "enabled": enabled, "percentage": percentage}
```

---

## 7.2 Logging & Monitoring

### Structured Logging Setup

```python
import logging
import sys
import json
from datetime import datetime
from typing import Any
from contextvars import ContextVar

# Context variables for request tracking
request_id_var: ContextVar[str] = ContextVar("request_id", default="")
user_id_var: ContextVar[str] = ContextVar("user_id", default="")


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add context variables
        if request_id := request_id_var.get():
            log_data["request_id"] = request_id
        if user_id := user_id_var.get():
            log_data["user_id"] = user_id

        # Add extra fields
        if hasattr(record, "extra_data"):
            log_data.update(record.extra_data)

        # Add exception info
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info)
            }

        return json.dumps(log_data, default=str)


def setup_logging(level: str = "INFO", json_format: bool = True):
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)

    if json_format:
        console_handler.setFormatter(JSONFormatter())
    else:
        console_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
        )

    root_logger.addHandler(console_handler)

    # Suppress noisy loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


# Custom logger with context
class ContextLogger:
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)

    def _log(self, level: int, message: str, **kwargs):
        record = self.logger.makeRecord(
            self.logger.name,
            level,
            "",
            0,
            message,
            (),
            None
        )
        record.extra_data = kwargs
        self.logger.handle(record)

    def debug(self, message: str, **kwargs):
        self._log(logging.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs):
        self._log(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs):
        self._log(logging.WARNING, message, **kwargs)

    def error(self, message: str, exc_info: bool = False, **kwargs):
        if exc_info:
            kwargs["exc_info"] = sys.exc_info()
        self._log(logging.ERROR, message, **kwargs)

    def critical(self, message: str, **kwargs):
        self._log(logging.CRITICAL, message, **kwargs)


logger = ContextLogger("app")


# Usage
logger.info("User created", user_id=123, email="user@example.com")
logger.error("Database error", exc_info=True, query="SELECT * FROM users")
```

### Request ID Tracking

```python
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
import uuid
from contextvars import ContextVar

app = FastAPI()

# Context variable for request ID
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Get or generate request ID
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = str(uuid.uuid4())

        # Set in context variable
        token = request_id_ctx.set(request_id)

        # Store in request state
        request.state.request_id = request_id

        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            request_id_ctx.reset(token)


app.add_middleware(RequestIDMiddleware)


# Dependency to get request ID
def get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


# Usage in endpoints
@app.get("/test")
async def test_endpoint(request_id: str = Depends(get_request_id)):
    logger.info("Processing request", request_id=request_id)
    return {"request_id": request_id}


# Propagate request ID to external services
import httpx

async def call_external_service(data: dict, request_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://external.service.com/api",
            json=data,
            headers={"X-Request-ID": request_id}
        )
        return response.json()


# Logging with automatic request ID
class RequestLogger:
    def __init__(self):
        self.logger = logging.getLogger("request")

    def log(self, level: int, message: str, **extra):
        request_id = request_id_ctx.get()
        extra["request_id"] = request_id
        self.logger.log(level, message, extra=extra)

    def info(self, message: str, **extra):
        self.log(logging.INFO, message, **extra)

    def error(self, message: str, **extra):
        self.log(logging.ERROR, message, **extra)


request_logger = RequestLogger()
```

### Distributed Tracing (OpenTelemetry)

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.b3 import B3MultiFormat


def setup_tracing(app: FastAPI, service_name: str):
    # Create resource with service info
    resource = Resource.create({
        "service.name": service_name,
        "service.version": "1.0.0",
        "deployment.environment": settings.environment
    })

    # Create tracer provider
    provider = TracerProvider(resource=resource)

    # Add OTLP exporter
    otlp_exporter = OTLPSpanExporter(
        endpoint=settings.otlp_endpoint,
        insecure=True
    )
    provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

    # Set as global tracer provider
    trace.set_tracer_provider(provider)

    # Set up propagator (for distributed tracing)
    set_global_textmap(B3MultiFormat())

    # Instrument FastAPI
    FastAPIInstrumentor.instrument_app(app)

    # Instrument other libraries
    SQLAlchemyInstrumentor().instrument(engine=engine)
    HTTPXClientInstrumentor().instrument()
    RedisInstrumentor().instrument()


# Get tracer for manual instrumentation
tracer = trace.get_tracer(__name__)


# Manual span creation
@app.get("/complex-operation")
async def complex_operation():
    with tracer.start_as_current_span("complex-operation") as span:
        span.set_attribute("operation.type", "complex")

        # Sub-operation 1
        with tracer.start_as_current_span("fetch-data") as fetch_span:
            data = await fetch_from_database()
            fetch_span.set_attribute("data.count", len(data))

        # Sub-operation 2
        with tracer.start_as_current_span("process-data") as process_span:
            result = process_data(data)
            process_span.set_attribute("result.size", len(result))

        # Add event
        span.add_event("Processing complete", {"items": len(result)})

        return result


# Async context manager for spans
from contextlib import asynccontextmanager

@asynccontextmanager
async def traced_operation(name: str, **attributes):
    with tracer.start_as_current_span(name) as span:
        for key, value in attributes.items():
            span.set_attribute(key, value)
        try:
            yield span
        except Exception as e:
            span.set_status(trace.Status(trace.StatusCode.ERROR))
            span.record_exception(e)
            raise


# Usage
async with traced_operation("external-api-call", api="payment") as span:
    result = await call_payment_api()
    span.set_attribute("transaction_id", result.id)
```

### Metrics Collection (Prometheus)

```python
from prometheus_client import Counter, Histogram, Gauge, Info, generate_latest
from prometheus_client import CONTENT_TYPE_LATEST
from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import time

app = FastAPI()

# Define metrics
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"]
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

REQUESTS_IN_PROGRESS = Gauge(
    "http_requests_in_progress",
    "Number of HTTP requests in progress",
    ["method", "endpoint"]
)

DB_POOL_SIZE = Gauge(
    "database_pool_size",
    "Database connection pool size"
)

DB_POOL_CHECKEDOUT = Gauge(
    "database_pool_checkedout",
    "Database connections checked out"
)

APP_INFO = Info(
    "app",
    "Application information"
)

# Business metrics
ORDERS_CREATED = Counter(
    "orders_created_total",
    "Total orders created",
    ["status"]
)

PAYMENT_AMOUNT = Histogram(
    "payment_amount_dollars",
    "Payment amounts in dollars",
    buckets=[10, 50, 100, 500, 1000, 5000]
)

ACTIVE_USERS = Gauge(
    "active_users",
    "Number of active users"
)


class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        method = request.method
        endpoint = request.url.path

        # Track in-progress requests
        REQUESTS_IN_PROGRESS.labels(method=method, endpoint=endpoint).inc()

        start_time = time.perf_counter()

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            status_code = 500
            raise
        finally:
            duration = time.perf_counter() - start_time

            REQUEST_COUNT.labels(
                method=method,
                endpoint=endpoint,
                status_code=status_code
            ).inc()

            REQUEST_LATENCY.labels(
                method=method,
                endpoint=endpoint
            ).observe(duration)

            REQUESTS_IN_PROGRESS.labels(method=method, endpoint=endpoint).dec()

        return response


app.add_middleware(PrometheusMiddleware)


# Metrics endpoint
@app.get("/metrics")
async def metrics():
    # Update pool metrics
    pool = engine.pool
    DB_POOL_SIZE.set(pool.size())
    DB_POOL_CHECKEDOUT.set(pool.checkedout())

    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


# Set app info
APP_INFO.info({
    "version": settings.version,
    "environment": settings.environment
})


# Business metric usage
@app.post("/orders")
async def create_order(order: OrderCreate):
    result = await order_service.create(order)
    ORDERS_CREATED.labels(status=result.status).inc()
    PAYMENT_AMOUNT.observe(float(result.total))
    return result
```

### Health Check Endpoints

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional
import asyncio
from datetime import datetime

app = FastAPI()


class HealthStatus(BaseModel):
    status: str  # "healthy", "degraded", "unhealthy"
    timestamp: str
    version: str
    checks: Dict[str, dict]


class ComponentHealth(BaseModel):
    status: str
    latency_ms: Optional[float] = None
    message: Optional[str] = None


async def check_database() -> ComponentHealth:
    try:
        start = datetime.now()
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        latency = (datetime.now() - start).total_seconds() * 1000
        return ComponentHealth(status="healthy", latency_ms=latency)
    except Exception as e:
        return ComponentHealth(status="unhealthy", message=str(e))


async def check_redis() -> ComponentHealth:
    try:
        start = datetime.now()
        await redis_client.ping()
        latency = (datetime.now() - start).total_seconds() * 1000
        return ComponentHealth(status="healthy", latency_ms=latency)
    except Exception as e:
        return ComponentHealth(status="unhealthy", message=str(e))


async def check_external_api() -> ComponentHealth:
    try:
        start = datetime.now()
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.example.com/health",
                timeout=5.0
            )
        latency = (datetime.now() - start).total_seconds() * 1000

        if response.status_code == 200:
            return ComponentHealth(status="healthy", latency_ms=latency)
        else:
            return ComponentHealth(
                status="degraded",
                latency_ms=latency,
                message=f"Status {response.status_code}"
            )
    except Exception as e:
        return ComponentHealth(status="unhealthy", message=str(e))


@app.get("/health", response_model=HealthStatus)
async def health_check():
    """Comprehensive health check"""
    checks = await asyncio.gather(
        check_database(),
        check_redis(),
        check_external_api(),
        return_exceptions=True
    )

    results = {
        "database": checks[0] if not isinstance(checks[0], Exception) else
            ComponentHealth(status="unhealthy", message=str(checks[0])),
        "redis": checks[1] if not isinstance(checks[1], Exception) else
            ComponentHealth(status="unhealthy", message=str(checks[1])),
        "external_api": checks[2] if not isinstance(checks[2], Exception) else
            ComponentHealth(status="degraded", message=str(checks[2])),
    }

    # Determine overall status
    statuses = [r.status for r in results.values()]

    if all(s == "healthy" for s in statuses):
        overall = "healthy"
    elif any(s == "unhealthy" for s in statuses):
        overall = "unhealthy"
    else:
        overall = "degraded"

    return HealthStatus(
        status=overall,
        timestamp=datetime.utcnow().isoformat() + "Z",
        version=settings.version,
        checks={k: v.model_dump() for k, v in results.items()}
    )


@app.get("/health/live")
async def liveness():
    """Kubernetes liveness probe - is the app running?"""
    return {"status": "alive"}


@app.get("/health/ready")
async def readiness():
    """Kubernetes readiness probe - can the app handle traffic?"""
    db_health = await check_database()
    redis_health = await check_redis()

    if db_health.status == "unhealthy" or redis_health.status == "unhealthy":
        raise HTTPException(status_code=503, detail="Not ready")

    return {"status": "ready"}


@app.get("/health/startup")
async def startup_probe():
    """Kubernetes startup probe - has the app started?"""
    # Check if all required services are initialized
    if not hasattr(app.state, "initialized") or not app.state.initialized:
        raise HTTPException(status_code=503, detail="Not started")
    return {"status": "started"}
```

### Alerting Strategies

```python
import asyncio
import httpx
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Callable, Dict, List
import logging

logger = logging.getLogger(__name__)


class AlertManager:
    def __init__(self):
        self.alert_handlers: List[Callable] = []
        self.alert_history: Dict[str, List[datetime]] = defaultdict(list)
        self.silenced_alerts: Dict[str, datetime] = {}

    def add_handler(self, handler: Callable):
        self.alert_handlers.append(handler)

    async def send_alert(
        self,
        alert_id: str,
        title: str,
        message: str,
        severity: str = "warning",
        dedup_window: int = 300  # seconds
    ):
        # Check if silenced
        if alert_id in self.silenced_alerts:
            if datetime.utcnow() < self.silenced_alerts[alert_id]:
                return

        # Deduplicate
        now = datetime.utcnow()
        cutoff = now - timedelta(seconds=dedup_window)
        recent = [t for t in self.alert_history[alert_id] if t > cutoff]

        if recent:
            return  # Already sent recently

        self.alert_history[alert_id].append(now)

        # Send to all handlers
        alert_data = {
            "alert_id": alert_id,
            "title": title,
            "message": message,
            "severity": severity,
            "timestamp": now.isoformat()
        }

        for handler in self.alert_handlers:
            try:
                await handler(alert_data)
            except Exception as e:
                logger.error(f"Alert handler failed: {e}")

    def silence(self, alert_id: str, duration: timedelta):
        self.silenced_alerts[alert_id] = datetime.utcnow() + duration


alert_manager = AlertManager()


# Slack alert handler
async def slack_alert_handler(alert: dict):
    webhook_url = settings.slack_webhook_url
    if not webhook_url:
        return

    color = {
        "critical": "#ff0000",
        "warning": "#ffcc00",
        "info": "#0066ff"
    }.get(alert["severity"], "#808080")

    payload = {
        "attachments": [{
            "color": color,
            "title": alert["title"],
            "text": alert["message"],
            "fields": [
                {"title": "Severity", "value": alert["severity"], "short": True},
                {"title": "Alert ID", "value": alert["alert_id"], "short": True},
            ],
            "ts": datetime.utcnow().timestamp()
        }]
    }

    async with httpx.AsyncClient() as client:
        await client.post(webhook_url, json=payload)


# PagerDuty alert handler
async def pagerduty_alert_handler(alert: dict):
    if alert["severity"] not in ["critical", "error"]:
        return

    routing_key = settings.pagerduty_routing_key
    if not routing_key:
        return

    payload = {
        "routing_key": routing_key,
        "event_action": "trigger",
        "dedup_key": alert["alert_id"],
        "payload": {
            "summary": alert["title"],
            "severity": "critical" if alert["severity"] == "critical" else "error",
            "source": "fastapi-app",
            "custom_details": {
                "message": alert["message"]
            }
        }
    }

    async with httpx.AsyncClient() as client:
        await client.post(
            "https://events.pagerduty.com/v2/enqueue",
            json=payload
        )


# Register handlers
alert_manager.add_handler(slack_alert_handler)
alert_manager.add_handler(pagerduty_alert_handler)


# Usage in code
async def check_error_rate():
    error_rate = await get_error_rate_last_5_min()

    if error_rate > 0.1:  # 10% error rate
        await alert_manager.send_alert(
            alert_id="high-error-rate",
            title="High Error Rate Alert",
            message=f"Error rate is {error_rate:.1%} in the last 5 minutes",
            severity="critical"
        )


# Health check alerting
@app.on_event("startup")
async def start_health_monitor():
    async def monitor():
        while True:
            health = await health_check()
            if health.status == "unhealthy":
                await alert_manager.send_alert(
                    alert_id=f"health-check-failed",
                    title="Health Check Failed",
                    message=f"Service is unhealthy: {health.checks}",
                    severity="critical"
                )
            await asyncio.sleep(60)

    asyncio.create_task(monitor())
```

---

## 7.3 Deployment

### Docker Containerization

```dockerfile
# Dockerfile
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# Production image
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create non-root user
RUN useradd --create-home --shell /bin/bash app
USER app

# Copy application code
COPY --chown=app:app . .

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health/live || exit 1

EXPOSE ${PORT}

# Run application
CMD ["gunicorn", "app.main:app", "-c", "gunicorn.conf.py"]
```

```python
# gunicorn.conf.py for Docker
import os

# Server socket
bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"

# Worker processes
workers = int(os.getenv("WORKERS", "4"))
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000

# Timeouts
timeout = 120
graceful_timeout = 30
keepalive = 5

# Logging
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info")

# Process naming
proc_name = "myapp"

# Preloading
preload_app = True

def on_starting(server):
    print("Starting Gunicorn server...")

def on_exit(server):
    print("Shutting down Gunicorn server...")
```

### Docker Compose for Development

```yaml
# docker-compose.yml
version: '3.8'

services:
  api:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - ENVIRONMENT=development
      - DATABASE_URL=postgresql://user:password@db:5432/myapp
      - REDIS_URL=redis://redis:6379/0
    volumes:
      - .:/app
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  db:
    image: postgres:15-alpine
    environment:
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=password
      - POSTGRES_DB=myapp
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U user -d myapp"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  celery-worker:
    build: .
    command: celery -A app.celery_app worker --loglevel=info
    environment:
      - DATABASE_URL=postgresql://user:password@db:5432/myapp
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis

  celery-beat:
    build: .
    command: celery -A app.celery_app beat --loglevel=info
    environment:
      - DATABASE_URL=postgresql://user:password@db:5432/myapp
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis

volumes:
  postgres_data:
  redis_data:
```

### Kubernetes Deployment Patterns

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: fastapi-app
  labels:
    app: fastapi-app
spec:
  replicas: 3
  selector:
    matchLabels:
      app: fastapi-app
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  template:
    metadata:
      labels:
        app: fastapi-app
    spec:
      containers:
      - name: api
        image: myregistry/myapp:latest
        ports:
        - containerPort: 8000
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: app-secrets
              key: database-url
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: app-secrets
              key: redis-url
        - name: SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: app-secrets
              key: secret-key
        livenessProbe:
          httpGet:
            path: /health/live
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 3
        startupProbe:
          httpGet:
            path: /health/startup
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
          failureThreshold: 30

---
# k8s/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: fastapi-app
spec:
  selector:
    app: fastapi-app
  ports:
  - port: 80
    targetPort: 8000
  type: ClusterIP

---
# k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: fastapi-app
  annotations:
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - api.example.com
    secretName: api-tls
  rules:
  - host: api.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: fastapi-app
            port:
              number: 80

---
# k8s/hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: fastapi-app
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: fastapi-app
  minReplicas: 3
  maxReplicas: 20
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
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 10
        periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 0
      policies:
      - type: Percent
        value: 100
        periodSeconds: 15
```

### Serverless Deployment

```python
# AWS Lambda with Mangum
from fastapi import FastAPI
from mangum import Mangum

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Hello from Lambda"}

# Lambda handler
handler = Mangum(app, lifespan="off")


# serverless.yml (Serverless Framework)
"""
service: fastapi-lambda

provider:
  name: aws
  runtime: python3.11
  region: us-east-1
  memorySize: 512
  timeout: 30
  environment:
    DATABASE_URL: ${ssm:/myapp/database-url}

functions:
  api:
    handler: app.main.handler
    events:
      - httpApi:
          path: /{proxy+}
          method: any
      - httpApi:
          path: /
          method: any

plugins:
  - serverless-python-requirements

custom:
  pythonRequirements:
    dockerizePip: true
    slim: true
"""


# GCP Cloud Run
"""
# Dockerfile.cloudrun
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

CMD exec uvicorn app.main:app --host 0.0.0.0 --port $PORT

# Deploy command:
# gcloud run deploy myapp --source . --region us-central1
"""


# Azure Functions
from azure.functions import AsgiMiddleware

app = FastAPI()

@app.get("/api/hello")
async def hello():
    return {"message": "Hello from Azure Functions"}

# Azure handler
main = AsgiMiddleware(app).handle
```

### Reverse Proxy Configuration

```nginx
# nginx.conf
upstream api_backend {
    least_conn;
    server api:8000 weight=1 max_fails=3 fail_timeout=30s;
    keepalive 32;
}

server {
    listen 80;
    server_name api.example.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.example.com;

    # SSL Configuration
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain application/json application/javascript text/css;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;

    location / {
        limit_req zone=api_limit burst=20 nodelay;

        proxy_pass http://api_backend;
        proxy_http_version 1.1;

        # Headers
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Request-ID $request_id;

        # WebSocket support
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;

        # Buffering
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
        proxy_busy_buffers_size 8k;
    }

    location /health {
        access_log off;
        proxy_pass http://api_backend/health;
    }

    location /metrics {
        # Internal only
        allow 10.0.0.0/8;
        deny all;
        proxy_pass http://api_backend/metrics;
    }
}
```

### SSL/TLS Termination

```python
# Using Traefik as reverse proxy
"""
# traefik.yml
entryPoints:
  web:
    address: ":80"
    http:
      redirections:
        entryPoint:
          to: websecure
          scheme: https
  websecure:
    address: ":443"

certificatesResolvers:
  letsencrypt:
    acme:
      email: admin@example.com
      storage: /letsencrypt/acme.json
      httpChallenge:
        entryPoint: web

providers:
  docker:
    exposedByDefault: false
"""

# docker-compose.yml with Traefik
"""
version: '3.8'

services:
  traefik:
    image: traefik:v2.10
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./traefik.yml:/etc/traefik/traefik.yml:ro
      - letsencrypt:/letsencrypt

  api:
    build: .
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.api.rule=Host(`api.example.com`)"
      - "traefik.http.routers.api.entrypoints=websecure"
      - "traefik.http.routers.api.tls.certresolver=letsencrypt"
      - "traefik.http.services.api.loadbalancer.server.port=8000"

volumes:
  letsencrypt:
"""


# Direct SSL in Uvicorn (development/testing)
"""
uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 443 \
    --ssl-keyfile /path/to/key.pem \
    --ssl-certfile /path/to/cert.pem
"""

# Generate self-signed cert for development
"""
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes
"""
```

---

## Summary

Module 7 covered production architecture essentials:

1. **Application Structure** - Project layouts, router organization, settings management, environment configuration, and feature flags

2. **Logging & Monitoring** - Structured logging, request ID tracking, distributed tracing with OpenTelemetry, Prometheus metrics, health checks, and alerting

3. **Deployment** - Docker containerization, Docker Compose, Kubernetes patterns, serverless deployment, reverse proxy configuration, and SSL/TLS

These patterns ensure your FastAPI application is production-ready, observable, and deployable across various platforms.

# Module 23: Dependency Injection

## Overview

Dependency Injection (DI) is a design pattern where objects receive their dependencies rather than creating them. This module covers DI principles, implementing a DI container, request-scoped dependencies, and integrating DI into your web framework.

---

## Learning Objectives

By the end of this module, you will be able to:

1. Explain dependency injection principles
2. Implement a dependency injection container
3. Handle different dependency lifecycles
4. Integrate DI with request handling
5. Test code with injected dependencies

---

## 23.1 Dependency Injection Principles

### The Problem Without DI

```python
# Tight coupling - hard to test, hard to change
class UserService:
    def __init__(self):
        self.db = PostgresDatabase()  # Hardcoded dependency
        self.cache = RedisCache()      # Hardcoded dependency
        self.mailer = SMTPMailer()     # Hardcoded dependency

    async def get_user(self, user_id: int):
        cached = await self.cache.get(f"user:{user_id}")
        if cached:
            return cached

        user = await self.db.query("SELECT * FROM users WHERE id = $1", user_id)
        await self.cache.set(f"user:{user_id}", user)
        return user


# Testing requires real database, cache, and mail server!
```

### With Dependency Injection

```python
# Loose coupling - easy to test, easy to change
class UserService:
    def __init__(self, db: Database, cache: Cache, mailer: Mailer):
        self.db = db
        self.cache = cache
        self.mailer = mailer

    async def get_user(self, user_id: int):
        cached = await self.cache.get(f"user:{user_id}")
        if cached:
            return cached

        user = await self.db.query("SELECT * FROM users WHERE id = $1", user_id)
        await self.cache.set(f"user:{user_id}", user)
        return user


# Testing with mocks
async def test_get_user():
    mock_db = MockDatabase()
    mock_cache = MockCache()
    mock_mailer = MockMailer()

    service = UserService(mock_db, mock_cache, mock_mailer)
    user = await service.get_user(1)

    assert mock_cache.get_called
```

### Types of Injection

```python
# 1. Constructor Injection (preferred)
class UserHandler:
    def __init__(self, user_service: UserService):
        self.user_service = user_service


# 2. Method Injection
class UserHandler:
    async def get_user(self, user_id: int, db: Database):
        return await db.query("SELECT * FROM users WHERE id = $1", user_id)


# 3. Property Injection (avoid - hidden dependencies)
class UserHandler:
    user_service: UserService = None  # Set later
```

---

## 23.2 Dependency Container

### Simple Container

```python
from typing import Type, TypeVar, Callable, Any, Dict, Optional
from dataclasses import dataclass
from enum import Enum
import inspect
import asyncio


T = TypeVar('T')


class Lifecycle(Enum):
    SINGLETON = "singleton"      # One instance for app lifetime
    SCOPED = "scoped"           # One instance per request
    TRANSIENT = "transient"     # New instance every time


@dataclass
class Registration:
    """Dependency registration."""
    interface: Type
    implementation: Type | Callable
    lifecycle: Lifecycle
    instance: Any = None  # For singletons


class Container:
    """Dependency injection container."""

    def __init__(self):
        self._registrations: Dict[Type, Registration] = {}
        self._scoped_instances: Dict[Type, Any] = {}

    def register(self, interface: Type[T],
                 implementation: Type[T] | Callable[..., T] = None,
                 lifecycle: Lifecycle = Lifecycle.TRANSIENT):
        """Register a dependency."""
        impl = implementation or interface
        self._registrations[interface] = Registration(
            interface=interface,
            implementation=impl,
            lifecycle=lifecycle
        )

    def register_singleton(self, interface: Type[T],
                          implementation: Type[T] = None):
        """Register singleton dependency."""
        self.register(interface, implementation, Lifecycle.SINGLETON)

    def register_scoped(self, interface: Type[T],
                       implementation: Type[T] = None):
        """Register scoped dependency."""
        self.register(interface, implementation, Lifecycle.SCOPED)

    def register_instance(self, interface: Type[T], instance: T):
        """Register existing instance as singleton."""
        self._registrations[interface] = Registration(
            interface=interface,
            implementation=type(instance),
            lifecycle=Lifecycle.SINGLETON,
            instance=instance
        )

    async def resolve(self, interface: Type[T]) -> T:
        """Resolve a dependency."""
        if interface not in self._registrations:
            raise DependencyNotFoundError(f"No registration for {interface}")

        reg = self._registrations[interface]

        # Check for existing instance
        if reg.lifecycle == Lifecycle.SINGLETON and reg.instance:
            return reg.instance

        if reg.lifecycle == Lifecycle.SCOPED:
            if interface in self._scoped_instances:
                return self._scoped_instances[interface]

        # Create instance
        instance = await self._create_instance(reg)

        # Store based on lifecycle
        if reg.lifecycle == Lifecycle.SINGLETON:
            reg.instance = instance
        elif reg.lifecycle == Lifecycle.SCOPED:
            self._scoped_instances[interface] = instance

        return instance

    async def _create_instance(self, reg: Registration) -> Any:
        """Create instance with resolved dependencies."""
        impl = reg.implementation

        # If it's a factory function
        if callable(impl) and not isinstance(impl, type):
            if asyncio.iscoroutinefunction(impl):
                return await impl(self)
            return impl(self)

        # Get constructor parameters
        sig = inspect.signature(impl.__init__)
        params = sig.parameters

        # Resolve constructor dependencies
        kwargs = {}
        for name, param in params.items():
            if name == 'self':
                continue

            if param.annotation != inspect.Parameter.empty:
                dep_type = param.annotation
                kwargs[name] = await self.resolve(dep_type)

        return impl(**kwargs)

    def create_scope(self) -> 'ScopedContainer':
        """Create a scoped container for request."""
        return ScopedContainer(self)

    def clear_scoped(self):
        """Clear scoped instances."""
        self._scoped_instances.clear()


class ScopedContainer:
    """Scoped container for request lifecycle."""

    def __init__(self, parent: Container):
        self._parent = parent
        self._scoped_instances: Dict[Type, Any] = {}

    async def resolve(self, interface: Type[T]) -> T:
        """Resolve with scoped instances."""
        if interface not in self._parent._registrations:
            raise DependencyNotFoundError(f"No registration for {interface}")

        reg = self._parent._registrations[interface]

        if reg.lifecycle == Lifecycle.SCOPED:
            if interface in self._scoped_instances:
                return self._scoped_instances[interface]

            instance = await self._parent._create_instance(reg)
            self._scoped_instances[interface] = instance
            return instance

        return await self._parent.resolve(interface)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        # Cleanup scoped instances
        for instance in self._scoped_instances.values():
            if hasattr(instance, 'close'):
                if asyncio.iscoroutinefunction(instance.close):
                    await instance.close()
                else:
                    instance.close()
        self._scoped_instances.clear()


class DependencyNotFoundError(Exception):
    pass
```

### Usage Example

```python
# Define interfaces (protocols)
from typing import Protocol


class Database(Protocol):
    async def query(self, sql: str, *args) -> Any: ...
    async def close(self): ...


class Cache(Protocol):
    async def get(self, key: str) -> Optional[Any]: ...
    async def set(self, key: str, value: Any, ttl: int = 0): ...


class UserRepository(Protocol):
    async def get(self, user_id: int) -> Optional[dict]: ...
    async def create(self, data: dict) -> dict: ...


# Implementations
class PostgresDatabase:
    def __init__(self):
        self.pool = None

    async def connect(self, dsn: str):
        self.pool = await asyncpg.create_pool(dsn)

    async def query(self, sql: str, *args):
        async with self.pool.acquire() as conn:
            return await conn.fetch(sql, *args)

    async def close(self):
        await self.pool.close()


class RedisCache:
    def __init__(self):
        self.client = None

    async def connect(self, url: str):
        self.client = await aioredis.from_url(url)

    async def get(self, key: str):
        return await self.client.get(key)

    async def set(self, key: str, value: Any, ttl: int = 0):
        await self.client.set(key, value, ex=ttl or None)


class SQLUserRepository:
    def __init__(self, db: Database):
        self.db = db

    async def get(self, user_id: int) -> Optional[dict]:
        rows = await self.db.query(
            "SELECT * FROM users WHERE id = $1", user_id
        )
        return dict(rows[0]) if rows else None

    async def create(self, data: dict) -> dict:
        # ...
        pass


# Service that uses repositories
class UserService:
    def __init__(self, repo: UserRepository, cache: Cache):
        self.repo = repo
        self.cache = cache

    async def get_user(self, user_id: int) -> Optional[dict]:
        # Check cache
        cached = await self.cache.get(f"user:{user_id}")
        if cached:
            return cached

        # Get from database
        user = await self.repo.get(user_id)
        if user:
            await self.cache.set(f"user:{user_id}", user, ttl=300)

        return user


# Configure container
container = Container()

# Register singletons (app lifetime)
container.register_singleton(Database, PostgresDatabase)
container.register_singleton(Cache, RedisCache)

# Register scoped (request lifetime)
container.register_scoped(UserRepository, SQLUserRepository)

# Register transient (new instance each time)
container.register(UserService)
```

---

## 23.3 Auto-Wiring

### Type-Based Resolution

```python
import inspect
from typing import get_type_hints


class AutoWiringContainer(Container):
    """Container with automatic dependency resolution."""

    async def resolve(self, interface: Type[T]) -> T:
        # Try registered first
        if interface in self._registrations:
            return await super().resolve(interface)

        # Auto-wire based on type hints
        return await self._auto_wire(interface)

    async def _auto_wire(self, cls: Type[T]) -> T:
        """Automatically create instance by resolving constructor params."""
        if not inspect.isclass(cls):
            raise DependencyNotFoundError(f"Cannot auto-wire {cls}")

        # Get type hints for constructor
        try:
            hints = get_type_hints(cls.__init__)
        except Exception:
            hints = {}

        # Remove 'return' hint if present
        hints.pop('return', None)

        # Resolve each dependency
        kwargs = {}
        for name, dep_type in hints.items():
            kwargs[name] = await self.resolve(dep_type)

        return cls(**kwargs)


# Usage - no need to register UserService
container = AutoWiringContainer()
container.register_singleton(Database, PostgresDatabase)
container.register_singleton(Cache, RedisCache)
container.register_scoped(UserRepository, SQLUserRepository)

# UserService is auto-wired from its type hints
user_service = await container.resolve(UserService)
```

### Decorator-Based Registration

```python
from functools import wraps


def injectable(lifecycle: Lifecycle = Lifecycle.TRANSIENT):
    """Mark class as injectable."""
    def decorator(cls):
        cls._injectable = True
        cls._lifecycle = lifecycle
        return cls
    return decorator


def singleton(cls):
    """Mark class as singleton."""
    return injectable(Lifecycle.SINGLETON)(cls)


def scoped(cls):
    """Mark class as scoped."""
    return injectable(Lifecycle.SCOPED)(cls)


# Usage
@singleton
class DatabasePool:
    pass


@scoped
class RequestContext:
    pass


@injectable()
class UserService:
    def __init__(self, db: DatabasePool, ctx: RequestContext):
        self.db = db
        self.ctx = ctx


# Auto-discover and register
def register_injectables(container: Container, module):
    """Register all injectable classes from module."""
    for name in dir(module):
        obj = getattr(module, name)
        if hasattr(obj, '_injectable') and obj._injectable:
            container.register(obj, lifecycle=obj._lifecycle)
```

---

## 23.4 Request-Scoped Dependencies

### Integration with Web Framework

```python
from contextvars import ContextVar


# Current scope context
_current_scope: ContextVar[Optional[ScopedContainer]] = ContextVar(
    'current_scope', default=None
)


class DependencyMiddleware:
    """Middleware that manages request-scoped dependencies."""

    def __init__(self, app: ASGIApp, container: Container):
        self.app = app
        self.container = container

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        # Create scoped container for this request
        async with self.container.create_scope() as scoped:
            # Set in context var for access anywhere
            token = _current_scope.set(scoped)

            # Add to scope for handler access
            scope['container'] = scoped

            try:
                await self.app(scope, receive, send)
            finally:
                _current_scope.reset(token)


# Helper to get current container
def get_container() -> ScopedContainer:
    container = _current_scope.get()
    if not container:
        raise RuntimeError("No active request scope")
    return container


# Resolve dependency in handler
async def resolve(interface: Type[T]) -> T:
    return await get_container().resolve(interface)
```

### Request-Scoped Services

```python
@scoped
class RequestContext:
    """Per-request context."""

    def __init__(self):
        self.request_id = str(uuid.uuid4())
        self.start_time = time.time()
        self.user = None

    @property
    def elapsed_ms(self) -> float:
        return (time.time() - self.start_time) * 1000


@scoped
class DatabaseSession:
    """Per-request database session with transaction support."""

    def __init__(self, pool: DatabasePool):
        self.pool = pool
        self.conn = None
        self.transaction = None

    async def begin(self):
        self.conn = await self.pool.acquire()
        self.transaction = self.conn.transaction()
        await self.transaction.start()

    async def commit(self):
        if self.transaction:
            await self.transaction.commit()

    async def rollback(self):
        if self.transaction:
            await self.transaction.rollback()

    async def close(self):
        if self.conn:
            await self.pool.release(self.conn)


# Handler using request-scoped dependencies
async def create_order(scope, receive, send):
    container = scope['container']

    ctx = await container.resolve(RequestContext)
    session = await container.resolve(DatabaseSession)
    order_service = await container.resolve(OrderService)

    try:
        await session.begin()
        order = await order_service.create(ctx.user, order_data)
        await session.commit()

        return Response.json(order)
    except Exception:
        await session.rollback()
        raise
```

---

## 23.5 Factory Functions

```python
class Container:
    """Extended container with factory support."""

    def register_factory(self, interface: Type[T],
                        factory: Callable[..., T | Awaitable[T]],
                        lifecycle: Lifecycle = Lifecycle.TRANSIENT):
        """Register factory function."""
        self._registrations[interface] = Registration(
            interface=interface,
            implementation=factory,
            lifecycle=lifecycle
        )


# Factory examples
async def database_factory(container: Container) -> Database:
    """Factory for database connection."""
    config = await container.resolve(Config)
    db = PostgresDatabase()
    await db.connect(config.database_url)
    return db


async def http_client_factory(container: Container) -> HTTPClient:
    """Factory for HTTP client with configuration."""
    config = await container.resolve(Config)
    return HTTPClient(
        timeout=config.http_timeout,
        retry_count=config.http_retries
    )


# Parameterized factory
def cache_factory(prefix: str) -> Callable:
    """Create cache factory with prefix."""
    async def factory(container: Container) -> Cache:
        redis = await container.resolve(RedisClient)
        return PrefixedCache(redis, prefix)
    return factory


# Registration
container.register_factory(Database, database_factory, Lifecycle.SINGLETON)
container.register_factory(HTTPClient, http_client_factory)
container.register_factory(UserCache, cache_factory("user:"), Lifecycle.SCOPED)
```

---

## 23.6 Dependency Injection in Handlers

### Function-Based Handlers

```python
from typing import Annotated


class Depends:
    """Dependency marker for handlers."""

    def __init__(self, dependency: Type):
        self.dependency = dependency


# Type alias for cleaner syntax
def Inject(dep: Type[T]) -> T:
    return Annotated[T, Depends(dep)]


# Handler with injected dependencies
async def get_user(
    user_id: int,
    user_service: Inject[UserService],
    ctx: Inject[RequestContext]
) -> Response:
    user = await user_service.get_user(user_id)
    if not user:
        raise HTTPException(404, "User not found")

    return Response.json({
        'user': user,
        'request_id': ctx.request_id
    })


# Dependency-aware router
class DIRouter:
    """Router that injects dependencies into handlers."""

    def __init__(self, container: Container):
        self.container = container
        self.routes: Dict[tuple, Callable] = {}

    def route(self, method: str, path: str):
        def decorator(handler: Callable):
            self.routes[(method, path)] = handler
            return handler
        return decorator

    async def handle(self, scope: Scope, receive: Receive, send: Send):
        method = scope['method']
        path = scope['path']

        handler = self.routes.get((method, path))
        if not handler:
            # 404
            return

        # Inject dependencies
        kwargs = await self._resolve_dependencies(handler, scope)

        # Call handler
        response = await handler(**kwargs)
        await response.send(scope, receive, send)

    async def _resolve_dependencies(self, handler: Callable,
                                    scope: Scope) -> dict:
        """Resolve handler dependencies."""
        hints = get_type_hints(handler, include_extras=True)
        container = scope['container']
        kwargs = {}

        for name, hint in hints.items():
            if name == 'return':
                continue

            # Check for Depends annotation
            if hasattr(hint, '__metadata__'):
                for meta in hint.__metadata__:
                    if isinstance(meta, Depends):
                        kwargs[name] = await container.resolve(meta.dependency)
                        break
            else:
                # Try to resolve by type
                try:
                    kwargs[name] = await container.resolve(hint)
                except DependencyNotFoundError:
                    pass

        return kwargs
```

### Class-Based Handlers

```python
class BaseHandler:
    """Base handler with dependency injection."""

    def __init__(self, container: ScopedContainer):
        self._container = container
        self._resolved: Dict[Type, Any] = {}

    async def _get(self, interface: Type[T]) -> T:
        """Get dependency."""
        if interface not in self._resolved:
            self._resolved[interface] = await self._container.resolve(interface)
        return self._resolved[interface]

    @property
    async def db(self) -> Database:
        return await self._get(Database)

    @property
    async def cache(self) -> Cache:
        return await self._get(Cache)


class UserHandler(BaseHandler):
    """User API handler."""

    async def get_user(self, user_id: int) -> Response:
        db = await self.db
        user = await db.query("SELECT * FROM users WHERE id = $1", user_id)
        return Response.json(user)

    async def create_user(self, data: dict) -> Response:
        db = await self.db
        cache = await self.cache

        user = await db.query(
            "INSERT INTO users (name, email) VALUES ($1, $2) RETURNING *",
            data['name'], data['email']
        )

        await cache.delete(f"users:list")
        return Response.json(user, status=201)
```

---

## 23.7 Testing with DI

### Mock Dependencies

```python
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_container():
    """Create container with mock dependencies."""
    container = Container()

    # Mock database
    mock_db = AsyncMock(spec=Database)
    mock_db.query.return_value = [{'id': 1, 'name': 'Test User'}]
    container.register_instance(Database, mock_db)

    # Mock cache
    mock_cache = AsyncMock(spec=Cache)
    mock_cache.get.return_value = None
    container.register_instance(Cache, mock_cache)

    return container


@pytest.fixture
def user_service(mock_container):
    """Create user service with mocks."""
    return await mock_container.resolve(UserService)


@pytest.mark.asyncio
async def test_get_user_from_db(user_service, mock_container):
    """Test getting user from database when not cached."""
    user = await user_service.get_user(1)

    assert user['id'] == 1
    assert user['name'] == 'Test User'

    # Verify cache was checked
    cache = await mock_container.resolve(Cache)
    cache.get.assert_called_once_with('user:1')

    # Verify cache was updated
    cache.set.assert_called_once()


@pytest.mark.asyncio
async def test_get_user_from_cache(user_service, mock_container):
    """Test getting user from cache."""
    cache = await mock_container.resolve(Cache)
    cache.get.return_value = {'id': 1, 'name': 'Cached User'}

    user = await user_service.get_user(1)

    assert user['name'] == 'Cached User'

    # Database should not be called
    db = await mock_container.resolve(Database)
    db.query.assert_not_called()
```

### Test Container

```python
class TestContainer(Container):
    """Container optimized for testing."""

    def __init__(self):
        super().__init__()
        self._mocks: Dict[Type, Any] = {}

    def mock(self, interface: Type[T], **mock_returns) -> AsyncMock:
        """Create and register mock for interface."""
        mock = AsyncMock(spec=interface)

        # Configure return values
        for method, value in mock_returns.items():
            getattr(mock, method).return_value = value

        self.register_instance(interface, mock)
        self._mocks[interface] = mock
        return mock

    def get_mock(self, interface: Type[T]) -> AsyncMock:
        """Get registered mock."""
        return self._mocks.get(interface)


# Usage
@pytest.fixture
def test_container():
    container = TestContainer()

    container.mock(Database, query=[{'id': 1}])
    container.mock(Cache, get=None)
    container.mock(Mailer)

    return container
```

---

## 23.8 Advanced Patterns

### Lazy Dependencies

```python
from typing import Generic


class Lazy(Generic[T]):
    """Lazy dependency resolution."""

    def __init__(self, container: Container, interface: Type[T]):
        self._container = container
        self._interface = interface
        self._instance: Optional[T] = None

    async def get(self) -> T:
        if self._instance is None:
            self._instance = await self._container.resolve(self._interface)
        return self._instance


# Usage
class EmailService:
    def __init__(self, mailer: Lazy[Mailer]):
        self._mailer = mailer

    async def send_email(self, to: str, subject: str, body: str):
        # Only resolve mailer when actually needed
        mailer = await self._mailer.get()
        await mailer.send(to, subject, body)
```

### Conditional Dependencies

```python
class ConditionalContainer(Container):
    """Container with conditional registration."""

    def __init__(self, config: dict):
        super().__init__()
        self.config = config

    def register_conditional(self, interface: Type,
                            implementations: Dict[str, Type],
                            config_key: str):
        """Register based on configuration."""
        value = self.config.get(config_key)
        if value in implementations:
            self.register(interface, implementations[value])
        else:
            raise ValueError(f"Unknown {config_key}: {value}")


# Usage
container = ConditionalContainer({
    'cache_backend': 'redis',
    'database': 'postgres'
})

container.register_conditional(
    Cache,
    {
        'redis': RedisCache,
        'memory': MemoryCache,
        'memcached': MemcachedCache,
    },
    'cache_backend'
)
```

### Decorator Dependencies

```python
class LoggingDecorator:
    """Decorator that adds logging to any service."""

    def __init__(self, wrapped, logger):
        self._wrapped = wrapped
        self._logger = logger

    def __getattr__(self, name):
        attr = getattr(self._wrapped, name)
        if callable(attr):
            return self._wrap_method(name, attr)
        return attr

    def _wrap_method(self, name, method):
        async def wrapper(*args, **kwargs):
            self._logger.info(f"Calling {name}")
            try:
                result = await method(*args, **kwargs)
                self._logger.info(f"{name} completed")
                return result
            except Exception as e:
                self._logger.error(f"{name} failed: {e}")
                raise
        return wrapper


# Factory with decoration
async def user_service_factory(container: Container) -> UserService:
    service = await container.resolve(UserService)
    logger = await container.resolve(Logger)

    if container.config.get('debug'):
        return LoggingDecorator(service, logger)
    return service
```

---

## 23.9 Complete DI System

```python
"""
Complete dependency injection system for web framework.
"""

from typing import Type, TypeVar, Callable, Any, Dict, Optional, List
from dataclasses import dataclass
from enum import Enum
from contextvars import ContextVar
import inspect
import asyncio


T = TypeVar('T')


class Lifecycle(Enum):
    SINGLETON = "singleton"
    SCOPED = "scoped"
    TRANSIENT = "transient"


@dataclass
class ServiceDescriptor:
    interface: Type
    implementation: Type | Callable
    lifecycle: Lifecycle
    instance: Any = None


class ServiceCollection:
    """Builder for configuring services."""

    def __init__(self):
        self._services: Dict[Type, ServiceDescriptor] = {}

    def add_singleton(self, interface: Type[T],
                     implementation: Type[T] = None) -> 'ServiceCollection':
        self._register(interface, implementation, Lifecycle.SINGLETON)
        return self

    def add_scoped(self, interface: Type[T],
                  implementation: Type[T] = None) -> 'ServiceCollection':
        self._register(interface, implementation, Lifecycle.SCOPED)
        return self

    def add_transient(self, interface: Type[T],
                     implementation: Type[T] = None) -> 'ServiceCollection':
        self._register(interface, implementation, Lifecycle.TRANSIENT)
        return self

    def add_instance(self, interface: Type[T], instance: T) -> 'ServiceCollection':
        self._services[interface] = ServiceDescriptor(
            interface=interface,
            implementation=type(instance),
            lifecycle=Lifecycle.SINGLETON,
            instance=instance
        )
        return self

    def add_factory(self, interface: Type[T],
                   factory: Callable,
                   lifecycle: Lifecycle = Lifecycle.TRANSIENT) -> 'ServiceCollection':
        self._services[interface] = ServiceDescriptor(
            interface=interface,
            implementation=factory,
            lifecycle=lifecycle
        )
        return self

    def _register(self, interface: Type, implementation: Type,
                 lifecycle: Lifecycle):
        self._services[interface] = ServiceDescriptor(
            interface=interface,
            implementation=implementation or interface,
            lifecycle=lifecycle
        )

    def build(self) -> 'ServiceProvider':
        return ServiceProvider(self._services)


class ServiceProvider:
    """Dependency injection container."""

    def __init__(self, services: Dict[Type, ServiceDescriptor]):
        self._services = services
        self._singletons: Dict[Type, Any] = {}

    async def get_service(self, interface: Type[T]) -> T:
        """Resolve a service."""
        if interface not in self._services:
            raise ServiceNotFoundError(f"Service not found: {interface}")

        desc = self._services[interface]

        # Return singleton if exists
        if desc.lifecycle == Lifecycle.SINGLETON:
            if desc.instance:
                return desc.instance
            if interface in self._singletons:
                return self._singletons[interface]

        # Create instance
        instance = await self._create_instance(desc)

        # Cache singleton
        if desc.lifecycle == Lifecycle.SINGLETON:
            self._singletons[interface] = instance

        return instance

    async def _create_instance(self, desc: ServiceDescriptor) -> Any:
        impl = desc.implementation

        # Factory function
        if callable(impl) and not isinstance(impl, type):
            if asyncio.iscoroutinefunction(impl):
                return await impl(self)
            return impl(self)

        # Class - resolve constructor dependencies
        sig = inspect.signature(impl.__init__)
        kwargs = {}

        for name, param in sig.parameters.items():
            if name == 'self':
                continue

            if param.annotation != inspect.Parameter.empty:
                kwargs[name] = await self.get_service(param.annotation)

        return impl(**kwargs)

    def create_scope(self) -> 'ServiceScope':
        """Create a scoped service provider."""
        return ServiceScope(self)


class ServiceScope:
    """Scoped service provider for request lifetime."""

    def __init__(self, root: ServiceProvider):
        self._root = root
        self._scoped: Dict[Type, Any] = {}

    async def get_service(self, interface: Type[T]) -> T:
        desc = self._root._services.get(interface)
        if not desc:
            raise ServiceNotFoundError(f"Service not found: {interface}")

        if desc.lifecycle == Lifecycle.SCOPED:
            if interface not in self._scoped:
                self._scoped[interface] = await self._root._create_instance(desc)
            return self._scoped[interface]

        return await self._root.get_service(interface)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        for instance in self._scoped.values():
            if hasattr(instance, 'dispose'):
                await instance.dispose()
        self._scoped.clear()


class ServiceNotFoundError(Exception):
    pass


# Context variable for current scope
_scope: ContextVar[Optional[ServiceScope]] = ContextVar('scope', default=None)


def get_service(interface: Type[T]) -> T:
    """Get service from current scope."""
    scope = _scope.get()
    if not scope:
        raise RuntimeError("No active service scope")
    return scope.get_service(interface)


# ASGI Middleware
class DIMiddleware:
    def __init__(self, app, provider: ServiceProvider):
        self.app = app
        self.provider = provider

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        async with self.provider.create_scope() as service_scope:
            token = _scope.set(service_scope)
            scope['services'] = service_scope
            try:
                await self.app(scope, receive, send)
            finally:
                _scope.reset(token)


# Usage Example
services = ServiceCollection()
services.add_singleton(Config)
services.add_singleton(Database, PostgresDatabase)
services.add_scoped(UserRepository, SQLUserRepository)
services.add_transient(UserService)

provider = services.build()
app = DIMiddleware(router, provider)
```

---

## Exercises

### Exercise 23.1: Implement Lifecycle Management

Extend the container to:
- Call `initialize()` on services after creation
- Call `dispose()` on scoped services at scope end
- Support async lifecycle methods

### Exercise 23.2: Add Validation

Add registration validation:
- Detect circular dependencies
- Validate all dependencies can be resolved
- Warn about missing registrations

### Exercise 23.3: Create a Testing Helper

Build a test helper that:
- Auto-mocks all dependencies
- Allows overriding specific mocks
- Provides assertion helpers

---

## Summary

Dependency Injection principles:

1. **Inversion of Control**: Don't create, receive dependencies
2. **Lifecycles**: Singleton, scoped, transient
3. **Containers**: Manage registration and resolution
4. **Auto-wiring**: Resolve from type hints
5. **Testing**: Easy mocking with DI

---

## Next Module

**[Module 24: Request/Response Lifecycle →](./MODULE_24_REQUEST_LIFECYCLE.md)**

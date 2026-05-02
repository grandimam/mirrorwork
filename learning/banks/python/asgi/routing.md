# Routing

Barq uses a **path-centric, fluent routing API** that improves on existing Python frameworks by being chainable, composable, and supporting both class-based and functional handlers.

## Core Concepts

### Path-First Design

Routes are defined by path first, then methods are attached. This eliminates repetition and groups related operations together.

```python
from barq import Router

router = Router()

@router.path("/users/{user_id}")
class UserRoute:
    async def get(self, user_id: int) -> User: ...
    async def put(self, user_id: int, body: UserUpdate) -> User: ...
    async def delete(self, user_id: int) -> None: ...
```

### Dual Mode: Class or Functional

Use classes for resources with multiple methods, or functional style for simple endpoints.

**Class-based:**

```python
@router.path("/users")
class Users:
    async def get(self) -> list[User]: ...
    async def post(self, body: CreateUser) -> User: ...
```

**Functional:**

```python
router.path("/health").get(health_check)
router.path("/metrics").get(get_metrics).head(get_metrics)
```

## Chainable API

Methods return `self`, enabling fluent chaining:

```python
router.path("/posts").get(list_posts).post(create_post)

router.path("/posts/{post_id}").get(get_post).put(update_post).delete(delete_post)
```

## Guards and Middleware

Attach guards fluently with `.guard()`. Guards execute left-to-right before the handler.

```python
router.path("/admin").guard(require_auth, require_admin).get(admin_dashboard)

router.path("/users").guard(require_auth).get(list_users).post(create_user)
```

Multiple guards can be chained:

```python
router.path("/sensitive").guard(auth).guard(rate_limit).guard(audit_log).get(handler)
```

## Route Groups

Use context managers to group routes with shared prefixes and guards.

```python
with router.group("/api", guards=[cors]) as api:
    api.path("/health").get(health_check)

    with api.group("/v1", guards=[auth]) as v1:
        v1.path("/users").get(list_users).post(create_user)
        v1.path("/orders").get(list_orders)

    with api.group("/v2", guards=[auth]) as v2:
        v2.path("/users").get(list_users_v2)
```

This produces:

| Path | Guards |
|------|--------|
| `/api/health` | `cors` |
| `/api/v1/users` | `cors`, `auth` |
| `/api/v1/orders` | `cors`, `auth` |
| `/api/v2/users` | `cors`, `auth` |

## Path Parameters

Path parameters use `{param}` syntax with optional type hints:

```python
@router.path("/users/{user_id}")
class UserRoute:
    async def get(self, user_id: int) -> User: ...

@router.path("/files/{path:path}")
class FileRoute:
    async def get(self, path: str) -> bytes: ...
```

Supported parameter types:

| Syntax | Type | Pattern |
|--------|------|---------|
| `{id}` | `str` | `[^/]+` |
| `{id:int}` | `int` | `\d+` |
| `{id:uuid}` | `UUID` | UUID pattern |
| `{id:path}` | `str` | `.+` (including slashes) |

## Route Introspection

Access the route table for debugging or OpenAPI generation:

```python
for route in router.routes:
    print(f"{route.methods} {route.path} -> {route.handler.__name__}")
```

Output:

```
['GET', 'POST'] /users -> Users
['GET', 'PUT', 'DELETE'] /users/{user_id} -> UserRoute
['GET'] /health -> health_check
```

## Complete Example

```python
from barq import Router
from barq.guards import require_auth, require_role, rate_limit

router = Router()

# Simple health check
router.path("/health").get(lambda: {"status": "ok"})

# Public endpoints
router.path("/auth/login").post(login)
router.path("/auth/register").post(register)

# Protected API
with router.group("/api/v1", guards=[require_auth]) as api:

    # User operations
    @api.path("/users")
    class Users:
        async def get(self) -> list[User]: ...
        async def post(self, body: CreateUser) -> User: ...

    @api.path("/users/{user_id}")
    class UserDetail:
        async def get(self, user_id: int) -> User: ...
        async def put(self, user_id: int, body: UpdateUser) -> User: ...
        async def delete(self, user_id: int) -> None: ...

    # Admin only
    api.path("/admin/stats").guard(require_role("admin")).get(get_stats)

# Rate limited public API
router.path("/public/search").guard(rate_limit(100)).get(search)
```

## Comparison with Other Frameworks

| Feature | FastAPI | Flask | Starlette | Barq |
|---------|---------|-------|-----------|------|
| Path-centric | No | No | No | Yes |
| Chainable methods | No | No | No | Yes |
| Class + functional | No | No | No | Yes |
| Fluent guards | No | No | No | Yes |
| Context manager groups | No | Yes | No | Yes |
| Route introspection | Yes | Yes | Yes | Yes |

# Module 4: API Design & Documentation

---

## 4.1 OpenAPI Customization

### Custom OpenAPI Schema Generation

```python
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from typing import Dict, Any

app = FastAPI()

# Custom OpenAPI schema
def custom_openapi() -> Dict[str, Any]:
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="My Custom API",
        version="2.0.0",
        summary="A comprehensive API for managing resources",
        description="""
## Overview

This API provides endpoints for managing users, items, and orders.

## Authentication

All endpoints require Bearer token authentication.

## Rate Limiting

- Standard users: 100 requests/minute
- Premium users: 1000 requests/minute

## Error Codes

| Code | Description |
|------|-------------|
| 400 | Bad Request |
| 401 | Unauthorized |
| 403 | Forbidden |
| 404 | Not Found |
| 429 | Rate Limited |
| 500 | Server Error |
        """,
        routes=app.routes,
        terms_of_service="https://example.com/terms",
        contact={
            "name": "API Support",
            "url": "https://example.com/support",
            "email": "support@example.com"
        },
        license_info={
            "name": "MIT",
            "url": "https://opensource.org/licenses/MIT"
        }
    )

    # Add custom extensions
    openapi_schema["info"]["x-logo"] = {
        "url": "https://example.com/logo.png"
    }

    # Add servers
    openapi_schema["servers"] = [
        {
            "url": "https://api.example.com",
            "description": "Production server"
        },
        {
            "url": "https://staging-api.example.com",
            "description": "Staging server"
        },
        {
            "url": "http://localhost:8000",
            "description": "Development server"
        }
    ]

    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "bearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT"
        },
        "apiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key"
        },
        "oauth2": {
            "type": "oauth2",
            "flows": {
                "authorizationCode": {
                    "authorizationUrl": "https://auth.example.com/authorize",
                    "tokenUrl": "https://auth.example.com/token",
                    "scopes": {
                        "read": "Read access",
                        "write": "Write access",
                        "admin": "Admin access"
                    }
                }
            }
        }
    }

    # Add global security requirement
    openapi_schema["security"] = [{"bearerAuth": []}]

    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi


# Programmatically modify existing schema
def modify_openapi():
    schema = app.openapi()

    # Add webhooks (OpenAPI 3.1)
    schema["webhooks"] = {
        "orderCreated": {
            "post": {
                "summary": "Order created webhook",
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/Order"}
                        }
                    }
                },
                "responses": {
                    "200": {"description": "Webhook processed"}
                }
            }
        }
    }

    # Add common response schemas
    schema["components"]["responses"] = {
        "NotFound": {
            "description": "Resource not found",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "detail": {"type": "string"}
                        }
                    }
                }
            }
        },
        "Unauthorized": {
            "description": "Authentication required",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "detail": {"type": "string"}
                        }
                    }
                }
            }
        }
    }

    return schema
```

### Adding Examples and Descriptions

```python
from fastapi import FastAPI, Path, Query, Body
from pydantic import BaseModel, Field
from typing import Annotated
from enum import Enum

app = FastAPI()

class ItemStatus(str, Enum):
    """Status of an item in the inventory"""
    available = "available"
    reserved = "reserved"
    sold = "sold"

class Item(BaseModel):
    """Represents an item in the catalog"""

    name: str = Field(
        ...,
        title="Item Name",
        description="The unique name of the item",
        min_length=1,
        max_length=100,
        examples=["Widget Pro", "Gadget Plus"]
    )
    price: float = Field(
        ...,
        title="Item Price",
        description="Price in USD",
        gt=0,
        examples=[19.99, 49.99, 99.99]
    )
    status: ItemStatus = Field(
        default=ItemStatus.available,
        description="Current status of the item"
    )
    tags: list[str] = Field(
        default=[],
        description="List of tags for categorization",
        examples=[["electronics", "sale"], ["home", "new"]]
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "Widget Pro",
                    "price": 29.99,
                    "status": "available",
                    "tags": ["electronics", "bestseller"]
                },
                {
                    "name": "Basic Widget",
                    "price": 9.99,
                    "status": "available",
                    "tags": ["electronics", "budget"]
                }
            ]
        }
    }


class ItemCreate(BaseModel):
    name: str
    price: float
    tags: list[str] = []

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "New Product",
                "price": 39.99,
                "tags": ["new", "featured"]
            }
        }
    }


@app.post(
    "/items",
    response_model=Item,
    summary="Create a new item",
    description="""
Create a new item in the catalog.

## Rules

- Item names must be unique
- Price must be positive
- Tags are optional but recommended

## Example

```python
import requests

response = requests.post(
    "/items",
    json={"name": "Widget", "price": 9.99}
)
```
    """,
    response_description="The created item with generated ID",
    responses={
        201: {
            "description": "Item created successfully",
            "content": {
                "application/json": {
                    "example": {
                        "name": "Widget",
                        "price": 9.99,
                        "status": "available",
                        "tags": []
                    }
                }
            }
        },
        400: {
            "description": "Invalid item data",
            "content": {
                "application/json": {
                    "example": {"detail": "Item name already exists"}
                }
            }
        }
    }
)
async def create_item(
    item: Annotated[
        ItemCreate,
        Body(
            openapi_examples={
                "simple": {
                    "summary": "Simple item",
                    "description": "A basic item with minimal fields",
                    "value": {
                        "name": "Basic Widget",
                        "price": 9.99
                    }
                },
                "full": {
                    "summary": "Full item",
                    "description": "Item with all optional fields",
                    "value": {
                        "name": "Premium Widget",
                        "price": 99.99,
                        "tags": ["premium", "featured", "new"]
                    }
                }
            }
        )
    ]
):
    return Item(**item.model_dump())


@app.get(
    "/items/{item_id}",
    response_model=Item,
    summary="Get item by ID",
    responses={
        404: {
            "description": "Item not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Item with ID 123 not found"}
                }
            }
        }
    }
)
async def get_item(
    item_id: Annotated[
        int,
        Path(
            title="Item ID",
            description="The unique identifier of the item",
            ge=1,
            examples=[1, 42, 100]
        )
    ],
    include_metadata: Annotated[
        bool,
        Query(
            description="Include additional metadata in response",
            examples=[True, False]
        )
    ] = False
):
    return Item(name="Widget", price=9.99)
```

### Grouping with Tags and Metadata

```python
from fastapi import FastAPI, APIRouter
from enum import Enum

# Define tags with metadata
tags_metadata = [
    {
        "name": "users",
        "description": "Operations with users. Manage user accounts and profiles.",
        "externalDocs": {
            "description": "User management docs",
            "url": "https://docs.example.com/users"
        }
    },
    {
        "name": "items",
        "description": "Manage items in the catalog.",
    },
    {
        "name": "orders",
        "description": "Order processing and management.",
    },
    {
        "name": "admin",
        "description": "**Admin only** operations. Requires admin role.",
    },
    {
        "name": "internal",
        "description": "_Internal use only_. Not for public consumption.",
    }
]

app = FastAPI(
    title="E-Commerce API",
    openapi_tags=tags_metadata
)

# Router with default tags
users_router = APIRouter(
    prefix="/users",
    tags=["users"],
    responses={401: {"description": "Unauthorized"}}
)

items_router = APIRouter(
    prefix="/items",
    tags=["items"]
)

orders_router = APIRouter(
    prefix="/orders",
    tags=["orders"]
)

admin_router = APIRouter(
    prefix="/admin",
    tags=["admin"]
)


@users_router.get("/")
async def list_users():
    """List all users"""
    return []

@users_router.get("/{user_id}")
async def get_user(user_id: int):
    """Get a specific user by ID"""
    return {"id": user_id}

@users_router.post("/")
async def create_user():
    """Create a new user"""
    return {"id": 1}


@items_router.get("/")
async def list_items():
    return []

@items_router.post("/")
async def create_item():
    return {}


# Endpoint with multiple tags
@app.get("/dashboard", tags=["users", "admin"])
async def dashboard():
    """Dashboard showing user and admin info"""
    return {}


# Deprecated tag handling
@app.get(
    "/legacy/items",
    tags=["items"],
    deprecated=True,
    summary="List items (deprecated)",
    description="**Deprecated**: Use `/items` instead. Will be removed in v3.0."
)
async def legacy_list_items():
    return []


# Include routers
app.include_router(users_router)
app.include_router(items_router)
app.include_router(orders_router)
app.include_router(admin_router)


# Dynamic tag generation
class ResourceTag(str, Enum):
    USERS = "users"
    ITEMS = "items"
    ORDERS = "orders"

def create_crud_router(resource: ResourceTag):
    router = APIRouter(prefix=f"/{resource.value}", tags=[resource.value])

    @router.get("/")
    async def list_resources():
        return []

    @router.post("/")
    async def create_resource():
        return {}

    @router.get("/{id}")
    async def get_resource(id: int):
        return {"id": id}

    @router.put("/{id}")
    async def update_resource(id: int):
        return {"id": id}

    @router.delete("/{id}")
    async def delete_resource(id: int):
        return {"deleted": True}

    return router
```

### Hiding Endpoints from Docs

```python
from fastapi import FastAPI, APIRouter

app = FastAPI()

# Hide individual endpoint
@app.get("/health", include_in_schema=False)
async def health_check():
    """Internal health check - not shown in docs"""
    return {"status": "healthy"}

@app.get("/internal/metrics", include_in_schema=False)
async def metrics():
    """Internal metrics endpoint"""
    return {"requests": 1000}


# Hide entire router
internal_router = APIRouter(
    prefix="/internal",
    include_in_schema=False
)

@internal_router.get("/debug")
async def debug():
    return {"debug": "info"}

@internal_router.get("/cache/clear")
async def clear_cache():
    return {"cleared": True}

app.include_router(internal_router)


# Conditional hiding based on environment
import os

def should_show_in_docs(endpoint_name: str) -> bool:
    env = os.getenv("ENVIRONMENT", "development")
    hidden_in_prod = ["debug", "test", "internal"]

    if env == "production":
        return endpoint_name not in hidden_in_prod
    return True

@app.get(
    "/debug/info",
    include_in_schema=should_show_in_docs("debug")
)
async def debug_info():
    return {"env": os.getenv("ENVIRONMENT")}


# Hide deprecated endpoints from new docs version
@app.get(
    "/v1/items",
    include_in_schema=False,  # Hidden in main docs
    deprecated=True
)
async def v1_items():
    return []

@app.get("/v2/items")
async def v2_items():
    """Current version - shown in docs"""
    return []


# Generate separate OpenAPI schemas
def get_public_openapi():
    """OpenAPI schema for public consumption"""
    from fastapi.openapi.utils import get_openapi

    public_routes = [
        route for route in app.routes
        if hasattr(route, "include_in_schema") and route.include_in_schema
        and not getattr(route, "deprecated", False)
    ]

    return get_openapi(
        title="Public API",
        version="1.0.0",
        routes=public_routes
    )

def get_internal_openapi():
    """Full OpenAPI schema including internal endpoints"""
    from fastapi.openapi.utils import get_openapi

    return get_openapi(
        title="Internal API",
        version="1.0.0",
        routes=app.routes
    )

@app.get("/openapi-public.json", include_in_schema=False)
async def public_openapi():
    return get_public_openapi()

@app.get("/openapi-internal.json", include_in_schema=False)
async def internal_openapi():
    return get_internal_openapi()
```

### Custom Documentation UI

```python
from fastapi import FastAPI
from fastapi.openapi.docs import (
    get_swagger_ui_html,
    get_redoc_html,
    get_swagger_ui_oauth2_redirect_html
)
from fastapi.staticfiles import StaticFiles

# Disable default docs
app = FastAPI(docs_url=None, redoc_url=None)

# Custom Swagger UI
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - Swagger UI",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
        swagger_ui_parameters={
            "persistAuthorization": True,
            "displayRequestDuration": True,
            "filter": True,
            "showExtensions": True,
            "showCommonExtensions": True,
            "docExpansion": "none",
            "defaultModelsExpandDepth": 0,
            "syntaxHighlight.theme": "monokai"
        }
    )

@app.get(app.swagger_ui_oauth2_redirect_url, include_in_schema=False)
async def swagger_ui_redirect():
    return get_swagger_ui_oauth2_redirect_html()


# Custom ReDoc
@app.get("/redoc", include_in_schema=False)
async def custom_redoc_html():
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - ReDoc",
        redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@latest/bundles/redoc.standalone.js"
    )


# Fully custom docs page
from fastapi.responses import HTMLResponse

@app.get("/custom-docs", include_in_schema=False)
async def custom_docs():
    return HTMLResponse("""
<!DOCTYPE html>
<html>
<head>
    <title>API Documentation</title>
    <link rel="stylesheet" type="text/css" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
    <style>
        body { margin: 0; padding: 0; }
        .topbar { display: none; }
        .swagger-ui .info { margin: 20px; }
        .swagger-ui .info .title { color: #333; }
        /* Custom branding */
        .swagger-ui .info:before {
            content: '';
            display: block;
            height: 50px;
            background: url('/static/logo.png') no-repeat;
            background-size: contain;
            margin-bottom: 20px;
        }
    </style>
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script>
        window.onload = function() {
            SwaggerUIBundle({
                url: "/openapi.json",
                dom_id: '#swagger-ui',
                presets: [
                    SwaggerUIBundle.presets.apis,
                    SwaggerUIBundle.SwaggerUIStandalonePreset
                ],
                layout: "StandaloneLayout",
                persistAuthorization: true,
                displayRequestDuration: true
            });
        }
    </script>
</body>
</html>
    """)


# Multiple documentation versions
@app.get("/docs/v1", include_in_schema=False)
async def docs_v1():
    return get_swagger_ui_html(
        openapi_url="/openapi-v1.json",
        title="API v1 Documentation"
    )

@app.get("/docs/v2", include_in_schema=False)
async def docs_v2():
    return get_swagger_ui_html(
        openapi_url="/openapi-v2.json",
        title="API v2 Documentation"
    )


# Elements (alternative to Swagger/ReDoc)
@app.get("/elements", include_in_schema=False)
async def elements_docs():
    return HTMLResponse("""
<!DOCTYPE html>
<html>
<head>
    <title>API Documentation</title>
    <script src="https://unpkg.com/@stoplight/elements/web-components.min.js"></script>
    <link rel="stylesheet" href="https://unpkg.com/@stoplight/elements/styles.min.css">
</head>
<body>
    <elements-api
        apiDescriptionUrl="/openapi.json"
        router="hash"
        layout="sidebar"
    />
</body>
</html>
    """)
```

### Extending OpenAPI Spec

```python
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from typing import Dict, Any

app = FastAPI()

def custom_openapi() -> Dict[str, Any]:
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="Extended API",
        version="1.0.0",
        routes=app.routes
    )

    # Add custom x-* extensions
    for path, methods in openapi_schema.get("paths", {}).items():
        for method, details in methods.items():
            if method in ["get", "post", "put", "delete", "patch"]:
                # Add rate limit info
                details["x-ratelimit"] = {
                    "limit": 100,
                    "window": "1m"
                }

                # Add code samples
                details["x-codeSamples"] = [
                    {
                        "lang": "Python",
                        "label": "Python (requests)",
                        "source": generate_python_sample(path, method)
                    },
                    {
                        "lang": "JavaScript",
                        "label": "JavaScript (fetch)",
                        "source": generate_js_sample(path, method)
                    },
                    {
                        "lang": "cURL",
                        "source": generate_curl_sample(path, method)
                    }
                ]

    # Add custom components
    openapi_schema["components"]["x-webhooks"] = {
        "orderCreated": {
            "summary": "Order created event",
            "payload": {
                "$ref": "#/components/schemas/Order"
            }
        }
    }

    # Add API changelog
    openapi_schema["info"]["x-changelog"] = [
        {
            "version": "1.0.0",
            "date": "2024-01-15",
            "changes": ["Initial release"]
        },
        {
            "version": "1.1.0",
            "date": "2024-02-01",
            "changes": [
                "Added batch endpoints",
                "Improved error messages"
            ]
        }
    ]

    # Add links between operations
    for path, methods in openapi_schema.get("paths", {}).items():
        if "get" in methods and "{" in path:
            # Add link to list endpoint
            list_path = path.split("{")[0].rstrip("/")
            if list_path in openapi_schema["paths"]:
                methods["get"]["links"] = {
                    "ListAll": {
                        "operationRef": f"#/paths/{list_path.replace('/', '~1')}/get",
                        "description": "List all resources"
                    }
                }

    app.openapi_schema = openapi_schema
    return app.openapi_schema

def generate_python_sample(path: str, method: str) -> str:
    return f'''import requests

response = requests.{method}(
    "https://api.example.com{path}",
    headers={{"Authorization": "Bearer YOUR_TOKEN"}}
)
print(response.json())'''

def generate_js_sample(path: str, method: str) -> str:
    return f'''fetch("https://api.example.com{path}", {{
    method: "{method.upper()}",
    headers: {{
        "Authorization": "Bearer YOUR_TOKEN",
        "Content-Type": "application/json"
    }}
}})
.then(response => response.json())
.then(data => console.log(data));'''

def generate_curl_sample(path: str, method: str) -> str:
    return f'''curl -X {method.upper()} "https://api.example.com{path}" \\
    -H "Authorization: Bearer YOUR_TOKEN" \\
    -H "Content-Type: application/json"'''

app.openapi = custom_openapi
```

---

## 4.2 API Versioning Strategies

### URL Path Versioning

```python
from fastapi import FastAPI, APIRouter

app = FastAPI()

# Version 1 Router
v1_router = APIRouter(prefix="/api/v1", tags=["v1"])

@v1_router.get("/users")
async def v1_list_users():
    """V1: Returns basic user list"""
    return [
        {"id": 1, "name": "John"}
    ]

@v1_router.get("/users/{user_id}")
async def v1_get_user(user_id: int):
    return {"id": user_id, "name": "John"}


# Version 2 Router
v2_router = APIRouter(prefix="/api/v2", tags=["v2"])

@v2_router.get("/users")
async def v2_list_users():
    """V2: Returns enhanced user list with pagination"""
    return {
        "data": [
            {"id": 1, "name": "John", "email": "john@example.com"}
        ],
        "pagination": {
            "total": 1,
            "page": 1,
            "per_page": 10
        }
    }

@v2_router.get("/users/{user_id}")
async def v2_get_user(user_id: int):
    return {
        "id": user_id,
        "name": "John",
        "email": "john@example.com",
        "created_at": "2024-01-15T10:00:00Z"
    }


app.include_router(v1_router)
app.include_router(v2_router)


# Shared business logic
class UserService:
    async def get_user(self, user_id: int) -> dict:
        return {"id": user_id, "name": "John", "email": "john@example.com"}

    async def list_users(self) -> list:
        return [{"id": 1, "name": "John", "email": "john@example.com"}]

user_service = UserService()

# V1 and V2 share service, differ in response format
@v1_router.get("/items")
async def v1_items():
    users = await user_service.list_users()
    # V1 format: simple list
    return [{"id": u["id"], "name": u["name"]} for u in users]

@v2_router.get("/items")
async def v2_items():
    users = await user_service.list_users()
    # V2 format: with metadata
    return {
        "data": users,
        "meta": {"total": len(users)}
    }
```

### Header-Based Versioning

```python
from fastapi import FastAPI, Header, HTTPException, Depends
from typing import Annotated
from enum import Enum

app = FastAPI()

class APIVersion(str, Enum):
    V1 = "1"
    V2 = "2"
    V3 = "3"

def get_api_version(
    api_version: Annotated[
        str | None,
        Header(alias="X-API-Version")
    ] = None,
    accept: str = Header(default="")
) -> APIVersion:
    """
    Get API version from headers.
    Supports: X-API-Version header or Accept header with version
    """
    # Check X-API-Version header
    if api_version:
        try:
            return APIVersion(api_version)
        except ValueError:
            raise HTTPException(
                400,
                f"Invalid API version. Supported: {[v.value for v in APIVersion]}"
            )

    # Check Accept header (e.g., application/vnd.myapi.v2+json)
    if "vnd.myapi" in accept:
        import re
        match = re.search(r"vnd\.myapi\.v(\d+)", accept)
        if match:
            try:
                return APIVersion(match.group(1))
            except ValueError:
                pass

    # Default to latest version
    return APIVersion.V2


Version = Annotated[APIVersion, Depends(get_api_version)]


@app.get("/users")
async def list_users(version: Version):
    if version == APIVersion.V1:
        return [{"id": 1, "name": "John"}]
    elif version == APIVersion.V2:
        return {
            "data": [{"id": 1, "name": "John", "email": "john@example.com"}],
            "version": "2"
        }
    else:
        return {
            "users": [
                {
                    "id": 1,
                    "name": "John",
                    "email": "john@example.com",
                    "profile": {"bio": "Developer"}
                }
            ],
            "meta": {"version": "3", "total": 1}
        }


@app.get("/users/{user_id}")
async def get_user(user_id: int, version: Version):
    base_user = {"id": user_id, "name": "John"}

    match version:
        case APIVersion.V1:
            return base_user
        case APIVersion.V2:
            return {**base_user, "email": "john@example.com"}
        case APIVersion.V3:
            return {
                **base_user,
                "email": "john@example.com",
                "profile": {"bio": "Developer", "avatar": "url"}
            }


# Version-specific middleware
from starlette.middleware.base import BaseHTTPMiddleware

class VersionHeaderMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)

        # Add version to response headers
        version = request.headers.get("X-API-Version", "2")
        response.headers["X-API-Version"] = version
        response.headers["X-API-Deprecated"] = "true" if version == "1" else "false"

        return response

app.add_middleware(VersionHeaderMiddleware)
```

### Query Parameter Versioning

```python
from fastapi import FastAPI, Query, HTTPException
from typing import Annotated, Literal

app = FastAPI()

def get_version(
    version: Annotated[
        str | None,
        Query(
            description="API version (1, 2, or 'latest')",
            examples=["1", "2", "latest"]
        )
    ] = "latest"
) -> int:
    if version == "latest":
        return 2
    try:
        v = int(version)
        if v not in [1, 2]:
            raise ValueError()
        return v
    except ValueError:
        raise HTTPException(400, "Invalid version. Use 1, 2, or 'latest'")

Version = Annotated[int, Depends(get_version)]


@app.get("/api/users")
async def get_users(version: Version):
    """
    Get users. Use ?version=1 or ?version=2
    """
    if version == 1:
        return [{"id": 1, "name": "John"}]
    else:
        return {"data": [{"id": 1, "name": "John", "email": "john@example.com"}]}


# Alternative: Literal type for explicit versions
@app.get("/api/items")
async def get_items(
    v: Annotated[
        Literal["1.0", "2.0", "2.1"],
        Query(description="API version")
    ] = "2.1"
):
    versions = {
        "1.0": lambda: [{"id": 1}],
        "2.0": lambda: {"data": [{"id": 1, "name": "Item"}]},
        "2.1": lambda: {"data": [{"id": 1, "name": "Item", "sku": "ABC123"}]}
    }
    return versions[v]()


# Date-based versioning
from datetime import date

@app.get("/api/orders")
async def get_orders(
    api_date: Annotated[
        date | None,
        Query(
            description="API version date (YYYY-MM-DD). Defaults to latest.",
            examples=["2024-01-01", "2024-06-01"]
        )
    ] = None
):
    """
    Version by date allows gradual API evolution.
    Changes made after the specified date won't be applied.
    """
    version_date = api_date or date.today()

    # Apply version-specific behavior
    result = {"orders": [{"id": 1, "total": 100}]}

    if version_date >= date(2024, 3, 1):
        # Added tax field in March 2024
        result["orders"][0]["tax"] = 10

    if version_date >= date(2024, 6, 1):
        # Added shipping in June 2024
        result["orders"][0]["shipping"] = 5

    return result
```

### Router-Based Version Management

```python
from fastapi import FastAPI, APIRouter
from typing import Type
from pydantic import BaseModel
import importlib

app = FastAPI()

# Version configuration
SUPPORTED_VERSIONS = ["v1", "v2", "v3"]
DEPRECATED_VERSIONS = ["v1"]
LATEST_VERSION = "v3"

# Base models that versions can extend
class UserBase(BaseModel):
    id: int
    name: str

# Version-specific models
class UserV1(UserBase):
    pass

class UserV2(UserBase):
    email: str

class UserV3(UserBase):
    email: str
    profile: dict


# Version router factory
def create_version_router(version: str) -> APIRouter:
    router = APIRouter(prefix=f"/api/{version}")

    # Mark deprecated versions
    if version in DEPRECATED_VERSIONS:
        router.tags = [f"{version} (deprecated)"]
    else:
        router.tags = [version]

    return router


# Version 1
v1 = create_version_router("v1")

@v1.get("/users", response_model=list[UserV1], deprecated=True)
async def v1_users():
    return [UserV1(id=1, name="John")]


# Version 2
v2 = create_version_router("v2")

@v2.get("/users", response_model=list[UserV2])
async def v2_users():
    return [UserV2(id=1, name="John", email="john@example.com")]


# Version 3
v3 = create_version_router("v3")

@v3.get("/users", response_model=list[UserV3])
async def v3_users():
    return [UserV3(id=1, name="John", email="john@example.com", profile={})]


# Include all versions
for router in [v1, v2, v3]:
    app.include_router(router)


# Alias latest version
@app.get("/api/latest/users")
async def latest_users():
    """Redirects to latest version"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(f"/api/{LATEST_VERSION}/users")


# Dynamic version loading
def load_version_module(version: str):
    """Load version-specific module dynamically"""
    try:
        module = importlib.import_module(f"api.{version}")
        return module.router
    except ImportError:
        return None

# Register all available versions
for version in SUPPORTED_VERSIONS:
    router = load_version_module(version)
    if router:
        app.include_router(router)


# Version negotiation middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse

class VersionNegotiationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path

        # Handle /api/users -> /api/v3/users
        if path.startswith("/api/") and not any(
            path.startswith(f"/api/{v}/") for v in SUPPORTED_VERSIONS
        ):
            # Extract endpoint after /api/
            endpoint = path[5:]  # Remove "/api/"
            new_path = f"/api/{LATEST_VERSION}/{endpoint}"
            return RedirectResponse(new_path)

        return await call_next(request)

app.add_middleware(VersionNegotiationMiddleware)
```

### Deprecation Strategies

```python
from fastapi import FastAPI, APIRouter, Header, HTTPException, Response
from typing import Annotated
from datetime import date, datetime
import warnings

app = FastAPI()

# Deprecation configuration
DEPRECATION_CONFIG = {
    "/api/v1/users": {
        "deprecated_since": date(2024, 1, 1),
        "sunset_date": date(2024, 7, 1),
        "replacement": "/api/v2/users",
        "migration_guide": "https://docs.example.com/migration/v1-to-v2"
    },
    "/api/v1/items": {
        "deprecated_since": date(2024, 3, 1),
        "sunset_date": date(2024, 9, 1),
        "replacement": "/api/v2/items"
    }
}


# Deprecation middleware
from starlette.middleware.base import BaseHTTPMiddleware

class DeprecationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path
        response = await call_next(request)

        # Check if endpoint is deprecated
        config = DEPRECATION_CONFIG.get(path)
        if config:
            response.headers["Deprecation"] = config["deprecated_since"].isoformat()
            response.headers["Sunset"] = config["sunset_date"].isoformat()
            response.headers["Link"] = f'<{config["replacement"]}>; rel="successor-version"'

            if "migration_guide" in config:
                response.headers["X-Migration-Guide"] = config["migration_guide"]

            # Warn if past sunset date
            if date.today() > config["sunset_date"]:
                response.headers["Warning"] = '299 - "This endpoint has been sunset"'

        return response

app.add_middleware(DeprecationMiddleware)


# Deprecated endpoint decorator
from functools import wraps

def deprecated(
    since: str,
    sunset: str,
    replacement: str = None,
    message: str = None
):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, response: Response, **kwargs):
            # Add deprecation headers
            response.headers["Deprecation"] = since
            response.headers["Sunset"] = sunset

            if replacement:
                response.headers["Link"] = f'<{replacement}>; rel="successor-version"'

            # Add warning header
            warn_msg = message or f"Deprecated since {since}, sunset on {sunset}"
            response.headers["Warning"] = f'299 - "{warn_msg}"'

            return await func(*args, **kwargs)
        return wrapper
    return decorator


@app.get(
    "/legacy/endpoint",
    deprecated=True,
    summary="Legacy endpoint (deprecated)",
    description="**Deprecated**: Use `/new/endpoint` instead."
)
@deprecated(
    since="2024-01-01",
    sunset="2024-07-01",
    replacement="/new/endpoint"
)
async def legacy_endpoint(response: Response):
    return {"message": "This is deprecated"}


# Sunset enforcement
class SunsetEnforcementMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path
        config = DEPRECATION_CONFIG.get(path)

        if config and date.today() > config["sunset_date"]:
            # Option 1: Return 410 Gone
            return JSONResponse(
                status_code=410,
                content={
                    "error": "This endpoint has been removed",
                    "sunset_date": config["sunset_date"].isoformat(),
                    "replacement": config.get("replacement"),
                    "migration_guide": config.get("migration_guide")
                },
                headers={
                    "Sunset": config["sunset_date"].isoformat()
                }
            )

        return await call_next(request)


# Deprecation logging
import logging

logger = logging.getLogger("deprecation")

class DeprecationLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path

        if path in DEPRECATION_CONFIG:
            logger.warning(
                f"Deprecated endpoint called: {path}",
                extra={
                    "path": path,
                    "client_ip": request.client.host,
                    "user_agent": request.headers.get("user-agent"),
                    "deprecation_config": DEPRECATION_CONFIG[path]
                }
            )

        return await call_next(request)
```

---

## 4.3 Error Handling Architecture

### Custom Exception Classes

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Any
from enum import Enum

app = FastAPI()

# Error codes enum
class ErrorCode(str, Enum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    CONFLICT = "CONFLICT"
    RATE_LIMITED = "RATE_LIMITED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    BAD_REQUEST = "BAD_REQUEST"


# Base exception with structured error
class APIException(Exception):
    def __init__(
        self,
        status_code: int,
        error_code: ErrorCode,
        message: str,
        details: dict | None = None,
        headers: dict | None = None
    ):
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        self.details = details or {}
        self.headers = headers
        super().__init__(message)


# Specific exceptions
class NotFoundException(APIException):
    def __init__(
        self,
        resource: str,
        resource_id: Any,
        message: str | None = None
    ):
        super().__init__(
            status_code=404,
            error_code=ErrorCode.NOT_FOUND,
            message=message or f"{resource} with ID {resource_id} not found",
            details={"resource": resource, "resource_id": str(resource_id)}
        )


class ValidationException(APIException):
    def __init__(self, errors: list[dict], message: str = "Validation failed"):
        super().__init__(
            status_code=422,
            error_code=ErrorCode.VALIDATION_ERROR,
            message=message,
            details={"errors": errors}
        )


class UnauthorizedException(APIException):
    def __init__(self, message: str = "Authentication required"):
        super().__init__(
            status_code=401,
            error_code=ErrorCode.UNAUTHORIZED,
            message=message,
            headers={"WWW-Authenticate": "Bearer"}
        )


class ForbiddenException(APIException):
    def __init__(
        self,
        message: str = "Access denied",
        required_permission: str | None = None
    ):
        details = {}
        if required_permission:
            details["required_permission"] = required_permission

        super().__init__(
            status_code=403,
            error_code=ErrorCode.FORBIDDEN,
            message=message,
            details=details
        )


class ConflictException(APIException):
    def __init__(
        self,
        resource: str,
        conflict_field: str,
        conflict_value: Any,
        message: str | None = None
    ):
        super().__init__(
            status_code=409,
            error_code=ErrorCode.CONFLICT,
            message=message or f"{resource} with {conflict_field}='{conflict_value}' already exists",
            details={
                "resource": resource,
                "conflict_field": conflict_field,
                "conflict_value": str(conflict_value)
            }
        )


class RateLimitedException(APIException):
    def __init__(
        self,
        limit: int,
        window: str,
        retry_after: int
    ):
        super().__init__(
            status_code=429,
            error_code=ErrorCode.RATE_LIMITED,
            message=f"Rate limit exceeded: {limit} requests per {window}",
            details={
                "limit": limit,
                "window": window,
                "retry_after": retry_after
            },
            headers={"Retry-After": str(retry_after)}
        )


class ServiceUnavailableException(APIException):
    def __init__(
        self,
        service: str,
        retry_after: int | None = None,
        message: str | None = None
    ):
        headers = {}
        if retry_after:
            headers["Retry-After"] = str(retry_after)

        super().__init__(
            status_code=503,
            error_code=ErrorCode.SERVICE_UNAVAILABLE,
            message=message or f"Service '{service}' is temporarily unavailable",
            details={"service": service},
            headers=headers if headers else None
        )


# Usage
@app.get("/users/{user_id}")
async def get_user(user_id: int):
    user = await find_user(user_id)
    if not user:
        raise NotFoundException("User", user_id)
    return user

@app.post("/users")
async def create_user(email: str):
    if await user_exists(email):
        raise ConflictException("User", "email", email)
    return {"email": email}
```

### Exception Handlers Registration

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import ValidationError
import traceback
import logging

app = FastAPI()
logger = logging.getLogger(__name__)

# Error response model
class ErrorResponse(BaseModel):
    error: str
    error_code: str
    message: str
    details: dict = {}
    request_id: str | None = None
    timestamp: str


def create_error_response(
    request: Request,
    status_code: int,
    error_code: str,
    message: str,
    details: dict = None
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": error_code,
            "error_code": error_code,
            "message": message,
            "details": details or {},
            "request_id": getattr(request.state, "request_id", None),
            "timestamp": datetime.utcnow().isoformat()
        }
    )


# Handle custom API exceptions
@app.exception_handler(APIException)
async def api_exception_handler(request: Request, exc: APIException):
    logger.warning(
        f"API Exception: {exc.error_code} - {exc.message}",
        extra={
            "error_code": exc.error_code,
            "status_code": exc.status_code,
            "details": exc.details,
            "request_id": getattr(request.state, "request_id", None)
        }
    )

    response = create_error_response(
        request,
        exc.status_code,
        exc.error_code.value,
        exc.message,
        exc.details
    )

    if exc.headers:
        for key, value in exc.headers.items():
            response.headers[key] = value

    return response


# Handle Starlette HTTP exceptions
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    error_code_map = {
        400: ErrorCode.BAD_REQUEST,
        401: ErrorCode.UNAUTHORIZED,
        403: ErrorCode.FORBIDDEN,
        404: ErrorCode.NOT_FOUND,
        409: ErrorCode.CONFLICT,
        429: ErrorCode.RATE_LIMITED,
        500: ErrorCode.INTERNAL_ERROR,
        503: ErrorCode.SERVICE_UNAVAILABLE
    }

    error_code = error_code_map.get(exc.status_code, ErrorCode.INTERNAL_ERROR)

    return create_error_response(
        request,
        exc.status_code,
        error_code.value,
        exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    )


# Handle Pydantic validation errors
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError
):
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })

    return create_error_response(
        request,
        422,
        ErrorCode.VALIDATION_ERROR.value,
        "Request validation failed",
        {"errors": errors}
    )


# Handle unexpected exceptions
@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    # Log the full exception
    logger.error(
        f"Unhandled exception: {exc}",
        exc_info=True,
        extra={
            "request_id": getattr(request.state, "request_id", None),
            "path": request.url.path,
            "method": request.method
        }
    )

    # Don't expose internal details in production
    import os
    if os.getenv("ENVIRONMENT") == "development":
        details = {
            "exception_type": type(exc).__name__,
            "traceback": traceback.format_exc()
        }
    else:
        details = {}

    return create_error_response(
        request,
        500,
        ErrorCode.INTERNAL_ERROR.value,
        "An internal error occurred",
        details
    )


# Per-router exception handlers
from fastapi import APIRouter

admin_router = APIRouter(prefix="/admin")

@admin_router.exception_handler(APIException)
async def admin_api_exception_handler(request: Request, exc: APIException):
    # Log admin exceptions differently
    logger.error(f"Admin API Exception: {exc.error_code}")
    # ... custom handling
```

### Structured Error Responses

```python
from fastapi import FastAPI, Request
from pydantic import BaseModel, Field
from typing import List, Optional, Any
from datetime import datetime
from enum import Enum

app = FastAPI()

# RFC 7807 Problem Details
class ProblemDetail(BaseModel):
    type: str = Field(
        default="about:blank",
        description="URI reference identifying the problem type"
    )
    title: str = Field(
        description="Short, human-readable summary"
    )
    status: int = Field(
        description="HTTP status code"
    )
    detail: str = Field(
        description="Human-readable explanation specific to this occurrence"
    )
    instance: Optional[str] = Field(
        default=None,
        description="URI reference identifying the specific occurrence"
    )
    # Extensions
    error_code: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    request_id: Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "type": "https://api.example.com/errors/not-found",
                "title": "Resource Not Found",
                "status": 404,
                "detail": "User with ID 123 was not found",
                "instance": "/users/123",
                "error_code": "USER_NOT_FOUND",
                "timestamp": "2024-01-15T10:30:00Z",
                "request_id": "req_abc123"
            }
        }
    }


class ValidationErrorDetail(BaseModel):
    field: str
    message: str
    code: str
    value: Any = None


class ValidationProblemDetail(ProblemDetail):
    errors: List[ValidationErrorDetail]


# Error type URIs
ERROR_TYPES = {
    "not_found": "https://api.example.com/errors/not-found",
    "validation": "https://api.example.com/errors/validation",
    "unauthorized": "https://api.example.com/errors/unauthorized",
    "forbidden": "https://api.example.com/errors/forbidden",
    "conflict": "https://api.example.com/errors/conflict",
    "rate_limit": "https://api.example.com/errors/rate-limit",
    "internal": "https://api.example.com/errors/internal"
}


def create_problem_response(
    request: Request,
    status: int,
    error_type: str,
    title: str,
    detail: str,
    **extra
) -> JSONResponse:
    problem = ProblemDetail(
        type=ERROR_TYPES.get(error_type, "about:blank"),
        title=title,
        status=status,
        detail=detail,
        instance=str(request.url.path),
        request_id=getattr(request.state, "request_id", None),
        **extra
    )

    return JSONResponse(
        status_code=status,
        content=problem.model_dump(exclude_none=True),
        media_type="application/problem+json"
    )


@app.exception_handler(NotFoundException)
async def not_found_handler(request: Request, exc: NotFoundException):
    return create_problem_response(
        request,
        status=404,
        error_type="not_found",
        title="Resource Not Found",
        detail=exc.message,
        error_code=exc.error_code.value
    )


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    errors = [
        ValidationErrorDetail(
            field=".".join(str(loc) for loc in error["loc"]),
            message=error["msg"],
            code=error["type"],
            value=error.get("input")
        )
        for error in exc.errors()
    ]

    problem = ValidationProblemDetail(
        type=ERROR_TYPES["validation"],
        title="Validation Error",
        status=422,
        detail="One or more fields failed validation",
        instance=str(request.url.path),
        request_id=getattr(request.state, "request_id", None),
        errors=errors
    )

    return JSONResponse(
        status_code=422,
        content=problem.model_dump(exclude_none=True),
        media_type="application/problem+json"
    )


# Standardized error response for all endpoints
@app.get(
    "/users/{user_id}",
    responses={
        404: {
            "model": ProblemDetail,
            "description": "User not found"
        },
        422: {
            "model": ValidationProblemDetail,
            "description": "Validation error"
        }
    }
)
async def get_user(user_id: int):
    user = await find_user(user_id)
    if not user:
        raise NotFoundException("User", user_id)
    return user
```

### Validation Error Customization

```python
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field, field_validator, ValidationError
from typing import Any

app = FastAPI()

# Custom validation messages
VALIDATION_MESSAGES = {
    "string_too_short": "Must be at least {min_length} characters",
    "string_too_long": "Must be at most {max_length} characters",
    "value_error.missing": "This field is required",
    "type_error.integer": "Must be a valid integer",
    "type_error.float": "Must be a valid number",
    "value_error.email": "Must be a valid email address",
    "value_error.url": "Must be a valid URL",
    "value_error.any_str.min_length": "Must be at least {limit_value} characters",
    "value_error.any_str.max_length": "Must be at most {limit_value} characters",
    "value_error.number.not_gt": "Must be greater than {limit_value}",
    "value_error.number.not_ge": "Must be greater than or equal to {limit_value}",
    "value_error.number.not_lt": "Must be less than {limit_value}",
    "value_error.number.not_le": "Must be less than or equal to {limit_value}"
}

def get_friendly_message(error: dict) -> str:
    """Convert Pydantic error to user-friendly message"""
    error_type = error["type"]

    # Check for custom message in ctx
    if "ctx" in error and "error" in error["ctx"]:
        return str(error["ctx"]["error"])

    # Look up template
    template = VALIDATION_MESSAGES.get(error_type)
    if template:
        ctx = error.get("ctx", {})
        try:
            return template.format(**ctx)
        except KeyError:
            pass

    # Fall back to default message
    return error["msg"]


def get_field_name(loc: tuple) -> str:
    """Convert location tuple to readable field name"""
    parts = []
    for item in loc:
        if isinstance(item, int):
            parts.append(f"[{item}]")
        elif item not in ("body", "query", "path"):
            parts.append(str(item))

    return ".".join(parts) if parts else "request"


@app.exception_handler(RequestValidationError)
async def custom_validation_handler(
    request: Request,
    exc: RequestValidationError
):
    errors = []

    for error in exc.errors():
        field = get_field_name(error["loc"])
        message = get_friendly_message(error)

        errors.append({
            "field": field,
            "message": message,
            "code": error["type"],
            "input": error.get("input")
        })

    # Group errors by field
    grouped = {}
    for error in errors:
        field = error["field"]
        if field not in grouped:
            grouped[field] = []
        grouped[field].append(error["message"])

    return JSONResponse(
        status_code=422,
        content={
            "error": "VALIDATION_ERROR",
            "message": "Please correct the following errors",
            "errors": errors,
            "errors_by_field": grouped
        }
    )


# Custom validators with friendly messages
class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=30)
    email: str
    password: str = Field(min_length=8)
    age: int = Field(ge=13, le=120)

    @field_validator("username")
    @classmethod
    def username_valid(cls, v: str) -> str:
        if not v.isalnum():
            raise ValueError("Username can only contain letters and numbers")
        if v[0].isdigit():
            raise ValueError("Username cannot start with a number")
        return v

    @field_validator("email")
    @classmethod
    def email_valid(cls, v: str) -> str:
        if "@" not in v:
            raise ValueError("Please enter a valid email address")
        return v

    @field_validator("password")
    @classmethod
    def password_strong(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one number")
        return v


# Localized error messages
LOCALIZED_MESSAGES = {
    "en": {
        "required": "This field is required",
        "too_short": "Must be at least {min} characters",
        "invalid_email": "Please enter a valid email"
    },
    "es": {
        "required": "Este campo es obligatorio",
        "too_short": "Debe tener al menos {min} caracteres",
        "invalid_email": "Por favor ingrese un correo válido"
    },
    "fr": {
        "required": "Ce champ est requis",
        "too_short": "Doit contenir au moins {min} caractères",
        "invalid_email": "Veuillez entrer un email valide"
    }
}

def get_localized_message(
    error_key: str,
    locale: str = "en",
    **kwargs
) -> str:
    messages = LOCALIZED_MESSAGES.get(locale, LOCALIZED_MESSAGES["en"])
    template = messages.get(error_key, error_key)
    return template.format(**kwargs)
```

### Logging Errors Appropriately

```python
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
import logging
import json
import traceback
from typing import Any
import sys

# Configure structured logging
class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add extra fields
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        if hasattr(record, "error_code"):
            log_data["error_code"] = record.error_code
        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id
        if hasattr(record, "path"):
            log_data["path"] = record.path

        # Add exception info
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info)
            }

        return json.dumps(log_data)


# Setup logger
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JSONFormatter())

logger = logging.getLogger("api")
logger.setLevel(logging.INFO)
logger.addHandler(handler)

app = FastAPI()


# Context-aware logging
class ErrorLogger:
    def __init__(self, request: Request):
        self.request = request
        self.extra = {
            "request_id": getattr(request.state, "request_id", None),
            "path": request.url.path,
            "method": request.method,
            "client_ip": request.client.host if request.client else None,
            "user_id": getattr(request.state, "user_id", None)
        }

    def info(self, message: str, **kwargs):
        logger.info(message, extra={**self.extra, **kwargs})

    def warning(self, message: str, **kwargs):
        logger.warning(message, extra={**self.extra, **kwargs})

    def error(self, message: str, exc_info: bool = False, **kwargs):
        logger.error(message, exc_info=exc_info, extra={**self.extra, **kwargs})


# Exception handlers with logging
@app.exception_handler(APIException)
async def api_exception_handler(request: Request, exc: APIException):
    error_logger = ErrorLogger(request)

    # Log based on severity
    if exc.status_code >= 500:
        error_logger.error(
            f"Server error: {exc.message}",
            error_code=exc.error_code.value,
            status_code=exc.status_code,
            details=exc.details
        )
    elif exc.status_code >= 400:
        error_logger.warning(
            f"Client error: {exc.message}",
            error_code=exc.error_code.value,
            status_code=exc.status_code
        )

    return create_error_response(request, exc)


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    error_logger = ErrorLogger(request)

    # Log validation errors (usually INFO level)
    error_logger.info(
        "Validation error",
        error_count=len(exc.errors()),
        errors=[
            {"field": ".".join(str(l) for l in e["loc"]), "type": e["type"]}
            for e in exc.errors()
        ]
    )

    return create_validation_response(request, exc)


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    error_logger = ErrorLogger(request)

    # Always log unexpected exceptions as ERROR with traceback
    error_logger.error(
        f"Unhandled exception: {type(exc).__name__}: {exc}",
        exc_info=True,
        exception_type=type(exc).__name__
    )

    return create_error_response(
        request,
        status_code=500,
        error_code="INTERNAL_ERROR",
        message="An internal error occurred"
    )


# Sensitive data filtering
SENSITIVE_FIELDS = {"password", "token", "secret", "api_key", "credit_card"}

def filter_sensitive(data: Any) -> Any:
    """Remove sensitive fields from data before logging"""
    if isinstance(data, dict):
        return {
            k: "***REDACTED***" if k.lower() in SENSITIVE_FIELDS else filter_sensitive(v)
            for k, v in data.items()
        }
    elif isinstance(data, list):
        return [filter_sensitive(item) for item in data]
    return data


# Error aggregation for alerting
from collections import defaultdict
from datetime import datetime, timedelta
import asyncio

class ErrorAggregator:
    def __init__(self, window_seconds: int = 60, threshold: int = 10):
        self.window = window_seconds
        self.threshold = threshold
        self.errors: dict[str, list[datetime]] = defaultdict(list)
        self.alerted: set[str] = set()

    def record_error(self, error_type: str) -> bool:
        """Record error and return True if threshold exceeded"""
        now = datetime.utcnow()
        cutoff = now - timedelta(seconds=self.window)

        # Clean old errors
        self.errors[error_type] = [
            t for t in self.errors[error_type] if t > cutoff
        ]

        # Add current error
        self.errors[error_type].append(now)

        # Check threshold
        if len(self.errors[error_type]) >= self.threshold:
            if error_type not in self.alerted:
                self.alerted.add(error_type)
                return True

        return False

    def reset_alert(self, error_type: str):
        self.alerted.discard(error_type)


error_aggregator = ErrorAggregator()

async def check_error_threshold(error_type: str):
    if error_aggregator.record_error(error_type):
        # Send alert (Slack, PagerDuty, etc.)
        logger.critical(
            f"Error threshold exceeded for {error_type}",
            extra={"error_type": error_type, "alert": True}
        )
        await send_alert(f"High error rate for {error_type}")
```

### Client-Friendly Error Messages

```python
from fastapi import FastAPI, Request
from pydantic import BaseModel
from typing import Optional, Dict, Any

app = FastAPI()

# Error message templates
ERROR_TEMPLATES: Dict[str, Dict[str, str]] = {
    "USER_NOT_FOUND": {
        "title": "User Not Found",
        "message": "We couldn't find the user you're looking for.",
        "suggestion": "Please check the user ID and try again.",
        "help_link": "/docs/errors/user-not-found"
    },
    "INVALID_CREDENTIALS": {
        "title": "Invalid Credentials",
        "message": "The email or password you entered is incorrect.",
        "suggestion": "Please check your credentials and try again. If you forgot your password, use the 'Forgot Password' link.",
        "help_link": "/docs/errors/invalid-credentials"
    },
    "RATE_LIMITED": {
        "title": "Too Many Requests",
        "message": "You've made too many requests in a short period.",
        "suggestion": "Please wait a moment and try again.",
        "help_link": "/docs/rate-limiting"
    },
    "VALIDATION_ERROR": {
        "title": "Invalid Input",
        "message": "Some of the information you provided is invalid.",
        "suggestion": "Please review the errors below and correct your input.",
        "help_link": "/docs/api/validation"
    },
    "INTERNAL_ERROR": {
        "title": "Something Went Wrong",
        "message": "We encountered an unexpected error while processing your request.",
        "suggestion": "Please try again later. If the problem persists, contact support.",
        "help_link": "/support"
    }
}


class ClientFriendlyError(BaseModel):
    # For developers
    error_code: str
    technical_message: str

    # For end users
    title: str
    message: str
    suggestion: str
    help_link: Optional[str] = None

    # For debugging
    request_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


def create_friendly_error(
    request: Request,
    error_code: str,
    technical_message: str,
    details: Dict[str, Any] = None,
    custom_message: str = None
) -> ClientFriendlyError:
    template = ERROR_TEMPLATES.get(error_code, ERROR_TEMPLATES["INTERNAL_ERROR"])

    return ClientFriendlyError(
        error_code=error_code,
        technical_message=technical_message,
        title=template["title"],
        message=custom_message or template["message"],
        suggestion=template["suggestion"],
        help_link=template.get("help_link"),
        request_id=getattr(request.state, "request_id", None),
        details=details if details else None
    )


@app.exception_handler(APIException)
async def friendly_error_handler(request: Request, exc: APIException):
    error = create_friendly_error(
        request,
        exc.error_code.value,
        exc.message,
        exc.details
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=error.model_dump(exclude_none=True)
    )


# Field-level error messages
def format_field_errors(errors: list[dict]) -> dict:
    """Format validation errors in user-friendly way"""
    field_messages = {}

    FIELD_ERROR_MESSAGES = {
        "username": {
            "string_too_short": "Username must be at least 3 characters",
            "string_too_long": "Username cannot exceed 30 characters",
            "value_error": "Username can only contain letters and numbers"
        },
        "email": {
            "value_error.email": "Please enter a valid email address"
        },
        "password": {
            "string_too_short": "Password must be at least 8 characters",
            "value_error": "Password must include uppercase, lowercase, and numbers"
        },
        "age": {
            "greater_than_equal": "You must be at least 13 years old",
            "less_than_equal": "Please enter a valid age"
        }
    }

    for error in errors:
        field = error.get("field", "").split(".")[-1]
        error_type = error.get("type", "")

        # Get field-specific message
        if field in FIELD_ERROR_MESSAGES:
            message = FIELD_ERROR_MESSAGES[field].get(
                error_type,
                error.get("message", "Invalid value")
            )
        else:
            message = error.get("message", "Invalid value")

        if field not in field_messages:
            field_messages[field] = []
        field_messages[field].append(message)

    return field_messages


# Response with recovery actions
class ErrorWithRecovery(BaseModel):
    error_code: str
    message: str
    recovery_actions: list[dict]


RECOVERY_ACTIONS = {
    "SESSION_EXPIRED": [
        {"action": "refresh_token", "label": "Refresh Session", "endpoint": "/auth/refresh"},
        {"action": "login", "label": "Log In Again", "endpoint": "/auth/login"}
    ],
    "RATE_LIMITED": [
        {"action": "wait", "label": "Wait and Retry", "wait_seconds": 60},
        {"action": "upgrade", "label": "Upgrade Plan", "endpoint": "/billing/upgrade"}
    ],
    "PAYMENT_FAILED": [
        {"action": "update_payment", "label": "Update Payment Method", "endpoint": "/billing/payment"},
        {"action": "contact_support", "label": "Contact Support", "endpoint": "/support"}
    ]
}

def get_recovery_error(error_code: str, message: str) -> ErrorWithRecovery:
    return ErrorWithRecovery(
        error_code=error_code,
        message=message,
        recovery_actions=RECOVERY_ACTIONS.get(error_code, [])
    )
```

---

## Summary

Module 4 covered API design and documentation best practices:

1. **OpenAPI Customization** - Custom schema generation, examples, descriptions, tags, hiding endpoints, custom docs UI, and extending the spec

2. **API Versioning** - URL path versioning, header-based versioning, query parameter versioning, router-based management, and deprecation strategies

3. **Error Handling Architecture** - Custom exception classes, exception handlers, structured responses (RFC 7807), validation customization, logging, and user-friendly messages

These patterns ensure your API is well-documented, properly versioned, and provides excellent error feedback to consumers.

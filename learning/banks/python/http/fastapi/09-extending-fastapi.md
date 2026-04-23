# Module 9: Extending FastAPI

---

## 9.1 Custom Components

### Creating Custom APIRoute Classes

```python
from fastapi import FastAPI, APIRouter, Request, Response
from fastapi.routing import APIRoute
from typing import Callable, List
import time
import gzip

# Custom APIRoute with timing
class TimingRoute(APIRoute):
    def get_route_handler(self) -> Callable:
        original_route_handler = super().get_route_handler()

        async def custom_route_handler(request: Request) -> Response:
            start_time = time.perf_counter()
            response = await original_route_handler(request)
            process_time = time.perf_counter() - start_time
            response.headers["X-Process-Time"] = f"{process_time:.4f}"
            return response

        return custom_route_handler


# APIRoute with request validation logging
class LoggingRoute(APIRoute):
    def get_route_handler(self) -> Callable:
        original_route_handler = super().get_route_handler()

        async def custom_route_handler(request: Request) -> Response:
            logger.info(
                f"Request: {request.method} {request.url.path}",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "query_params": dict(request.query_params)
                }
            )

            try:
                response = await original_route_handler(request)
                logger.info(f"Response: {response.status_code}")
                return response
            except Exception as e:
                logger.error(f"Error: {e}", exc_info=True)
                raise

        return custom_route_handler


# APIRoute with response compression
class GzipRoute(APIRoute):
    def get_route_handler(self) -> Callable:
        original_route_handler = super().get_route_handler()

        async def custom_route_handler(request: Request) -> Response:
            response = await original_route_handler(request)

            accept_encoding = request.headers.get("Accept-Encoding", "")
            if "gzip" not in accept_encoding:
                return response

            if response.body:
                compressed = gzip.compress(response.body)
                return Response(
                    content=compressed,
                    status_code=response.status_code,
                    headers={**dict(response.headers), "Content-Encoding": "gzip"},
                    media_type=response.media_type
                )

            return response

        return custom_route_handler


# APIRoute with caching
class CachedRoute(APIRoute):
    cache = {}
    cache_ttl = 60

    def get_route_handler(self) -> Callable:
        original_route_handler = super().get_route_handler()

        async def custom_route_handler(request: Request) -> Response:
            if request.method != "GET":
                return await original_route_handler(request)

            cache_key = f"{request.url.path}?{request.query_params}"

            if cache_key in self.cache:
                cached_time, cached_response = self.cache[cache_key]
                if time.time() - cached_time < self.cache_ttl:
                    cached_response.headers["X-Cache"] = "HIT"
                    return cached_response

            response = await original_route_handler(request)

            if response.status_code == 200:
                self.cache[cache_key] = (time.time(), response)

            response.headers["X-Cache"] = "MISS"
            return response

        return custom_route_handler


# Using custom route classes
app = FastAPI()

# Apply to entire router
router = APIRouter(route_class=TimingRoute)

@router.get("/timed")
async def timed_endpoint():
    return {"message": "This endpoint is timed"}

app.include_router(router)


# Apply to specific endpoint
@app.get("/custom", route_class=LoggingRoute)
async def custom_endpoint():
    return {"message": "Custom route"}


# Combining multiple route behaviors
class CombinedRoute(TimingRoute, LoggingRoute, GzipRoute):
    def get_route_handler(self) -> Callable:
        # Chain the handlers
        handler = super().get_route_handler()
        return handler
```

### Custom Request/Response Classes

```python
from fastapi import FastAPI, Request
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response, JSONResponse
from typing import Any, Dict
import json
import orjson

# Custom Request with additional methods
class EnhancedRequest(StarletteRequest):
    @property
    def is_ajax(self) -> bool:
        return self.headers.get("X-Requested-With") == "XMLHttpRequest"

    @property
    def is_json(self) -> bool:
        content_type = self.headers.get("Content-Type", "")
        return "application/json" in content_type

    @property
    def real_ip(self) -> str:
        """Get real IP considering proxy headers"""
        forwarded = self.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return self.client.host if self.client else "unknown"

    async def json_safe(self) -> Dict[str, Any]:
        """Get JSON body with error handling"""
        try:
            return await self.json()
        except json.JSONDecodeError:
            return {}

    def get_language(self) -> str:
        """Get preferred language from Accept-Language"""
        accept_lang = self.headers.get("Accept-Language", "en")
        return accept_lang.split(",")[0].split("-")[0]


# Custom Request class factory
def create_request_class(request: Request) -> EnhancedRequest:
    return EnhancedRequest(request.scope, request.receive)


# Using in dependencies
async def get_enhanced_request(request: Request) -> EnhancedRequest:
    return EnhancedRequest(request.scope, request.receive)


@app.get("/test")
async def test_endpoint(request: EnhancedRequest = Depends(get_enhanced_request)):
    return {
        "is_ajax": request.is_ajax,
        "real_ip": request.real_ip,
        "language": request.get_language()
    }


# Custom Response with orjson for faster JSON
class ORJSONResponse(JSONResponse):
    media_type = "application/json"

    def render(self, content: Any) -> bytes:
        return orjson.dumps(
            content,
            option=orjson.OPT_NON_STR_KEYS | orjson.OPT_SERIALIZE_NUMPY
        )


# Use as default response class
app = FastAPI(default_response_class=ORJSONResponse)


# Custom response with envelope
class EnvelopedResponse(JSONResponse):
    def __init__(
        self,
        content: Any,
        status_code: int = 200,
        success: bool = True,
        message: str = None,
        **kwargs
    ):
        envelope = {
            "success": success,
            "data": content,
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        }
        super().__init__(content=envelope, status_code=status_code, **kwargs)


@app.get("/enveloped")
async def enveloped_endpoint():
    return EnvelopedResponse(
        content={"items": [1, 2, 3]},
        message="Data retrieved successfully"
    )


# Custom streaming response
class SSEResponse(Response):
    media_type = "text/event-stream"

    def __init__(
        self,
        content: Any,
        status_code: int = 200,
        headers: Dict[str, str] = None,
        **kwargs
    ):
        headers = headers or {}
        headers["Cache-Control"] = "no-cache"
        headers["Connection"] = "keep-alive"
        super().__init__(content, status_code, headers, **kwargs)


# Custom response with HATEOAS links
class HATEOASResponse(JSONResponse):
    def __init__(
        self,
        content: Any,
        links: Dict[str, str] = None,
        **kwargs
    ):
        if isinstance(content, dict):
            content["_links"] = links or {}
        super().__init__(content=content, **kwargs)


@app.get("/resources/{id}")
async def get_resource(id: int):
    return HATEOASResponse(
        content={"id": id, "name": "Resource"},
        links={
            "self": f"/resources/{id}",
            "update": f"/resources/{id}",
            "delete": f"/resources/{id}",
            "collection": "/resources"
        }
    )
```

### Building Reusable Routers

```python
from fastapi import APIRouter, Depends, HTTPException
from typing import TypeVar, Generic, Type, List, Optional
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

ModelType = TypeVar("ModelType")
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)
ResponseSchemaType = TypeVar("ResponseSchemaType", bound=BaseModel)


# Generic CRUD router factory
def create_crud_router(
    model: Type[ModelType],
    create_schema: Type[CreateSchemaType],
    update_schema: Type[UpdateSchemaType],
    response_schema: Type[ResponseSchemaType],
    prefix: str,
    tags: List[str] = None
) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=tags or [prefix.strip("/")])

    @router.get("/", response_model=List[response_schema])
    async def list_items(
        skip: int = 0,
        limit: int = 100,
        db: AsyncSession = Depends(get_db)
    ):
        result = await db.execute(
            select(model).offset(skip).limit(limit)
        )
        return result.scalars().all()

    @router.get("/{item_id}", response_model=response_schema)
    async def get_item(item_id: int, db: AsyncSession = Depends(get_db)):
        item = await db.get(model, item_id)
        if not item:
            raise HTTPException(404, "Item not found")
        return item

    @router.post("/", response_model=response_schema, status_code=201)
    async def create_item(
        item: create_schema,
        db: AsyncSession = Depends(get_db)
    ):
        db_item = model(**item.model_dump())
        db.add(db_item)
        await db.commit()
        await db.refresh(db_item)
        return db_item

    @router.put("/{item_id}", response_model=response_schema)
    async def update_item(
        item_id: int,
        item: update_schema,
        db: AsyncSession = Depends(get_db)
    ):
        db_item = await db.get(model, item_id)
        if not db_item:
            raise HTTPException(404, "Item not found")

        for field, value in item.model_dump(exclude_unset=True).items():
            setattr(db_item, field, value)

        await db.commit()
        await db.refresh(db_item)
        return db_item

    @router.delete("/{item_id}", status_code=204)
    async def delete_item(item_id: int, db: AsyncSession = Depends(get_db)):
        db_item = await db.get(model, item_id)
        if not db_item:
            raise HTTPException(404, "Item not found")

        await db.delete(db_item)
        await db.commit()

    return router


# Usage
user_router = create_crud_router(
    model=User,
    create_schema=UserCreate,
    update_schema=UserUpdate,
    response_schema=UserResponse,
    prefix="/users",
    tags=["users"]
)

app.include_router(user_router)


# Configurable router with hooks
class CRUDRouter(APIRouter, Generic[ModelType]):
    def __init__(
        self,
        model: Type[ModelType],
        schema: Type[BaseModel],
        create_schema: Type[BaseModel] = None,
        update_schema: Type[BaseModel] = None,
        prefix: str = "",
        **kwargs
    ):
        super().__init__(prefix=prefix, **kwargs)
        self.model = model
        self.schema = schema
        self.create_schema = create_schema or schema
        self.update_schema = update_schema or schema

        self._register_routes()

    def _register_routes(self):
        self.add_api_route("/", self._list, methods=["GET"])
        self.add_api_route("/{id}", self._get, methods=["GET"])
        self.add_api_route("/", self._create, methods=["POST"])
        self.add_api_route("/{id}", self._update, methods=["PUT"])
        self.add_api_route("/{id}", self._delete, methods=["DELETE"])

    # Override these methods for custom behavior
    async def before_create(self, item: BaseModel, db: AsyncSession) -> BaseModel:
        return item

    async def after_create(self, item: ModelType, db: AsyncSession):
        pass

    async def before_update(
        self, id: int, item: BaseModel, db: AsyncSession
    ) -> BaseModel:
        return item

    async def after_update(self, item: ModelType, db: AsyncSession):
        pass

    async def before_delete(self, id: int, db: AsyncSession):
        pass

    async def after_delete(self, id: int, db: AsyncSession):
        pass

    async def _list(self, db: AsyncSession = Depends(get_db)):
        result = await db.execute(select(self.model))
        return result.scalars().all()

    async def _get(self, id: int, db: AsyncSession = Depends(get_db)):
        item = await db.get(self.model, id)
        if not item:
            raise HTTPException(404)
        return item

    async def _create(
        self,
        item: BaseModel,
        db: AsyncSession = Depends(get_db)
    ):
        item = await self.before_create(item, db)
        db_item = self.model(**item.model_dump())
        db.add(db_item)
        await db.commit()
        await db.refresh(db_item)
        await self.after_create(db_item, db)
        return db_item

    async def _update(
        self,
        id: int,
        item: BaseModel,
        db: AsyncSession = Depends(get_db)
    ):
        db_item = await db.get(self.model, id)
        if not db_item:
            raise HTTPException(404)

        item = await self.before_update(id, item, db)

        for field, value in item.model_dump(exclude_unset=True).items():
            setattr(db_item, field, value)

        await db.commit()
        await db.refresh(db_item)
        await self.after_update(db_item, db)
        return db_item

    async def _delete(self, id: int, db: AsyncSession = Depends(get_db)):
        await self.before_delete(id, db)
        db_item = await db.get(self.model, id)
        if not db_item:
            raise HTTPException(404)

        await db.delete(db_item)
        await db.commit()
        await self.after_delete(id, db)


# Custom implementation with hooks
class UserRouter(CRUDRouter[User]):
    async def after_create(self, user: User, db: AsyncSession):
        await send_welcome_email(user.email)

    async def before_delete(self, id: int, db: AsyncSession):
        # Check if user has active orders
        orders = await db.execute(
            select(Order).where(Order.user_id == id, Order.status == "active")
        )
        if orders.scalars().first():
            raise HTTPException(400, "Cannot delete user with active orders")
```

### Plugin Architecture Patterns

```python
from fastapi import FastAPI
from typing import Protocol, List, Callable, Any
from abc import ABC, abstractmethod
import importlib
import pkgutil

# Plugin protocol
class FastAPIPlugin(Protocol):
    name: str
    version: str

    def register(self, app: FastAPI) -> None:
        """Register the plugin with the FastAPI app"""
        ...

    def unregister(self, app: FastAPI) -> None:
        """Unregister the plugin from the FastAPI app"""
        ...


# Base plugin class
class BasePlugin(ABC):
    name: str = "base"
    version: str = "1.0.0"

    @abstractmethod
    def register(self, app: FastAPI) -> None:
        pass

    def unregister(self, app: FastAPI) -> None:
        pass


# Plugin manager
class PluginManager:
    def __init__(self, app: FastAPI):
        self.app = app
        self.plugins: dict[str, FastAPIPlugin] = {}

    def register(self, plugin: FastAPIPlugin) -> None:
        if plugin.name in self.plugins:
            raise ValueError(f"Plugin {plugin.name} already registered")

        plugin.register(self.app)
        self.plugins[plugin.name] = plugin

    def unregister(self, plugin_name: str) -> None:
        if plugin_name not in self.plugins:
            return

        plugin = self.plugins[plugin_name]
        plugin.unregister(self.app)
        del self.plugins[plugin_name]

    def get_plugin(self, name: str) -> FastAPIPlugin:
        return self.plugins.get(name)

    def load_plugins_from_package(self, package_name: str) -> None:
        """Automatically discover and load plugins from a package"""
        package = importlib.import_module(package_name)

        for _, module_name, _ in pkgutil.iter_modules(package.__path__):
            module = importlib.import_module(f"{package_name}.{module_name}")

            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, BasePlugin)
                    and attr is not BasePlugin
                ):
                    plugin = attr()
                    self.register(plugin)


# Example plugins
class CORSPlugin(BasePlugin):
    name = "cors"
    version = "1.0.0"

    def __init__(self, origins: List[str] = None):
        self.origins = origins or ["*"]

    def register(self, app: FastAPI) -> None:
        from fastapi.middleware.cors import CORSMiddleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=self.origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"]
        )


class MetricsPlugin(BasePlugin):
    name = "metrics"
    version = "1.0.0"

    def register(self, app: FastAPI) -> None:
        from prometheus_client import generate_latest

        @app.get("/metrics")
        async def metrics():
            return Response(content=generate_latest(), media_type="text/plain")


class HealthPlugin(BasePlugin):
    name = "health"
    version = "1.0.0"

    def register(self, app: FastAPI) -> None:
        @app.get("/health")
        async def health():
            return {"status": "healthy"}

        @app.get("/ready")
        async def ready():
            return {"status": "ready"}


# Hook-based plugin system
class HookManager:
    def __init__(self):
        self.hooks: dict[str, List[Callable]] = {}

    def register_hook(self, name: str, callback: Callable) -> None:
        if name not in self.hooks:
            self.hooks[name] = []
        self.hooks[name].append(callback)

    async def execute_hook(self, name: str, *args, **kwargs) -> List[Any]:
        results = []
        for callback in self.hooks.get(name, []):
            if asyncio.iscoroutinefunction(callback):
                result = await callback(*args, **kwargs)
            else:
                result = callback(*args, **kwargs)
            results.append(result)
        return results


hook_manager = HookManager()


# Usage
app = FastAPI()
plugin_manager = PluginManager(app)

# Register plugins
plugin_manager.register(CORSPlugin(origins=["http://localhost:3000"]))
plugin_manager.register(MetricsPlugin())
plugin_manager.register(HealthPlugin())

# Auto-discover plugins
plugin_manager.load_plugins_from_package("myapp.plugins")
```

---

## 9.2 Integrations

### Admin Panel Integration (SQLAdmin)

```python
from fastapi import FastAPI
from sqladmin import Admin, ModelView
from sqladmin.authentication import AuthenticationBackend
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette.requests import Request
from starlette.responses import RedirectResponse

app = FastAPI()

# Admin authentication
class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        username = form.get("username")
        password = form.get("password")

        # Validate credentials
        if username == "admin" and password == "admin":
            request.session.update({"admin": True})
            return True
        return False

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        return request.session.get("admin", False)


# Create admin
admin = Admin(
    app,
    engine,
    authentication_backend=AdminAuth(secret_key="your-secret-key")
)


# Model views
class UserAdmin(ModelView, model=User):
    column_list = [User.id, User.username, User.email, User.is_active, User.created_at]
    column_searchable_list = [User.username, User.email]
    column_sortable_list = [User.id, User.username, User.created_at]
    column_default_sort = [(User.created_at, True)]

    form_columns = [User.username, User.email, User.is_active]
    form_excluded_columns = [User.hashed_password]

    can_create = True
    can_edit = True
    can_delete = True
    can_view_details = True

    name = "User"
    name_plural = "Users"
    icon = "fa-solid fa-user"


class PostAdmin(ModelView, model=Post):
    column_list = [Post.id, Post.title, Post.author, Post.created_at]
    column_searchable_list = [Post.title, Post.content]

    form_columns = [Post.title, Post.content, Post.author]

    # Custom formatting
    column_formatters = {
        Post.created_at: lambda m, a: m.created_at.strftime("%Y-%m-%d %H:%M")
    }

    # Custom validation
    async def on_model_change(self, data: dict, model: Post, is_created: bool) -> None:
        if len(data.get("title", "")) < 5:
            raise ValueError("Title must be at least 5 characters")


class OrderAdmin(ModelView, model=Order):
    column_list = [Order.id, Order.user, Order.status, Order.total, Order.created_at]
    column_searchable_list = [Order.id]

    form_columns = [Order.user, Order.status, Order.total]
    form_widget_args = {
        Order.status: {"choices": [("pending", "Pending"), ("paid", "Paid"), ("shipped", "Shipped")]}
    }

    # Custom action
    async def after_model_change(self, data: dict, model: Order, is_created: bool) -> None:
        if not is_created and data.get("status") == "shipped":
            await send_shipping_notification(model.user.email, model.id)


# Register views
admin.add_view(UserAdmin)
admin.add_view(PostAdmin)
admin.add_view(OrderAdmin)
```

### Task Scheduling (APScheduler)

```python
from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.jobstores.redis import RedisJobStore
from contextlib import asynccontextmanager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Scheduler configuration
jobstores = {
    "default": RedisJobStore(host="localhost", port=6379, db=2)
}

scheduler = AsyncIOScheduler(
    jobstores=jobstores,
    timezone="UTC"
)


# Scheduled tasks
async def cleanup_expired_sessions():
    """Run every hour"""
    logger.info("Cleaning up expired sessions...")
    await db.execute(
        delete(Session).where(Session.expires_at < datetime.utcnow())
    )
    await db.commit()
    logger.info("Session cleanup complete")


async def send_daily_report():
    """Run daily at 9 AM"""
    logger.info("Generating daily report...")
    report = await generate_report()
    await send_email_to_admins(report)
    logger.info("Daily report sent")


async def sync_external_data():
    """Run every 5 minutes"""
    logger.info("Syncing external data...")
    data = await fetch_external_api()
    await update_local_cache(data)
    logger.info("External data synced")


async def process_pending_orders():
    """Run every minute"""
    orders = await get_pending_orders()
    for order in orders:
        try:
            await process_order(order)
        except Exception as e:
            logger.error(f"Failed to process order {order.id}: {e}")


# FastAPI integration
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Add jobs
    scheduler.add_job(
        cleanup_expired_sessions,
        trigger=IntervalTrigger(hours=1),
        id="cleanup_sessions",
        replace_existing=True
    )

    scheduler.add_job(
        send_daily_report,
        trigger=CronTrigger(hour=9, minute=0),
        id="daily_report",
        replace_existing=True
    )

    scheduler.add_job(
        sync_external_data,
        trigger=IntervalTrigger(minutes=5),
        id="sync_external",
        replace_existing=True
    )

    scheduler.add_job(
        process_pending_orders,
        trigger=IntervalTrigger(minutes=1),
        id="process_orders",
        replace_existing=True
    )

    # Start scheduler
    scheduler.start()
    logger.info("Scheduler started")

    yield

    # Shutdown
    scheduler.shutdown()
    logger.info("Scheduler shutdown")


app = FastAPI(lifespan=lifespan)


# API endpoints for job management
@app.get("/scheduler/jobs")
async def list_jobs():
    jobs = scheduler.get_jobs()
    return [
        {
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger)
        }
        for job in jobs
    ]


@app.post("/scheduler/jobs/{job_id}/run")
async def run_job_now(job_id: str):
    job = scheduler.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    scheduler.modify_job(job_id, next_run_time=datetime.utcnow())
    return {"message": f"Job {job_id} scheduled to run now"}


@app.post("/scheduler/jobs/{job_id}/pause")
async def pause_job(job_id: str):
    scheduler.pause_job(job_id)
    return {"message": f"Job {job_id} paused"}


@app.post("/scheduler/jobs/{job_id}/resume")
async def resume_job(job_id: str):
    scheduler.resume_job(job_id)
    return {"message": f"Job {job_id} resumed"}


# Dynamic job creation
@app.post("/scheduler/jobs")
async def create_job(
    job_id: str,
    interval_seconds: int,
    function_name: str
):
    function_map = {
        "cleanup": cleanup_expired_sessions,
        "sync": sync_external_data
    }

    func = function_map.get(function_name)
    if not func:
        raise HTTPException(400, "Unknown function")

    scheduler.add_job(
        func,
        trigger=IntervalTrigger(seconds=interval_seconds),
        id=job_id,
        replace_existing=True
    )

    return {"message": f"Job {job_id} created"}
```

### Email Sending Patterns

```python
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel, EmailStr
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import aiosmtplib
from jinja2 import Environment, FileSystemLoader
from pathlib import Path

# Email configuration
class EmailSettings(BaseModel):
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str
    smtp_password: str
    from_email: str
    from_name: str = "My App"


settings = EmailSettings()

# Template environment
templates = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates" / "email")
)


class EmailService:
    def __init__(self, settings: EmailSettings):
        self.settings = settings

    async def send_email(
        self,
        to: str,
        subject: str,
        body_html: str,
        body_text: str = None
    ) -> bool:
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = f"{self.settings.from_name} <{self.settings.from_email}>"
        message["To"] = to

        if body_text:
            message.attach(MIMEText(body_text, "plain"))
        message.attach(MIMEText(body_html, "html"))

        try:
            await aiosmtplib.send(
                message,
                hostname=self.settings.smtp_host,
                port=self.settings.smtp_port,
                username=self.settings.smtp_user,
                password=self.settings.smtp_password,
                start_tls=True
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    async def send_template(
        self,
        to: str,
        template_name: str,
        subject: str,
        context: dict
    ) -> bool:
        template = templates.get_template(f"{template_name}.html")
        html = template.render(**context)

        text_template = templates.get_template(f"{template_name}.txt")
        text = text_template.render(**context) if text_template else None

        return await self.send_email(to, subject, html, text)

    async def send_welcome(self, user_email: str, username: str) -> bool:
        return await self.send_template(
            to=user_email,
            template_name="welcome",
            subject="Welcome to Our App!",
            context={"username": username}
        )

    async def send_password_reset(
        self,
        user_email: str,
        reset_token: str
    ) -> bool:
        reset_url = f"https://app.example.com/reset-password?token={reset_token}"
        return await self.send_template(
            to=user_email,
            template_name="password_reset",
            subject="Password Reset Request",
            context={"reset_url": reset_url}
        )

    async def send_order_confirmation(
        self,
        user_email: str,
        order: dict
    ) -> bool:
        return await self.send_template(
            to=user_email,
            template_name="order_confirmation",
            subject=f"Order Confirmation #{order['id']}",
            context={"order": order}
        )


email_service = EmailService(settings)


# Usage in endpoints
app = FastAPI()


@app.post("/auth/register")
async def register(
    user: UserCreate,
    background_tasks: BackgroundTasks
):
    db_user = await create_user(user)

    # Send email in background
    background_tasks.add_task(
        email_service.send_welcome,
        db_user.email,
        db_user.username
    )

    return db_user


@app.post("/auth/forgot-password")
async def forgot_password(
    email: EmailStr,
    background_tasks: BackgroundTasks
):
    user = await get_user_by_email(email)
    if user:
        token = create_reset_token(user.id)
        background_tasks.add_task(
            email_service.send_password_reset,
            email,
            token
        )

    # Always return success to prevent email enumeration
    return {"message": "If the email exists, a reset link will be sent"}


# Email queue with Celery
from celery import Celery

celery_app = Celery("emails", broker="redis://localhost:6379/0")


@celery_app.task
def send_email_task(to: str, subject: str, body_html: str):
    import asyncio
    loop = asyncio.get_event_loop()
    loop.run_until_complete(
        email_service.send_email(to, subject, body_html)
    )


@app.post("/send-bulk-email")
async def send_bulk_email(emails: List[str], subject: str, body: str):
    for email in emails:
        send_email_task.delay(email, subject, body)

    return {"message": f"Queued {len(emails)} emails"}
```

### File Storage (S3, Local, Cloud)

```python
from fastapi import FastAPI, UploadFile, HTTPException
from abc import ABC, abstractmethod
from pathlib import Path
import boto3
from botocore.exceptions import ClientError
import aiofiles
import uuid
from typing import BinaryIO

# Storage interface
class StorageBackend(ABC):
    @abstractmethod
    async def upload(self, file: BinaryIO, path: str) -> str:
        pass

    @abstractmethod
    async def download(self, path: str) -> bytes:
        pass

    @abstractmethod
    async def delete(self, path: str) -> bool:
        pass

    @abstractmethod
    def get_url(self, path: str) -> str:
        pass


# Local storage
class LocalStorage(StorageBackend):
    def __init__(self, base_path: str = "./uploads"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def upload(self, file: BinaryIO, path: str) -> str:
        full_path = self.base_path / path
        full_path.parent.mkdir(parents=True, exist_ok=True)

        async with aiofiles.open(full_path, "wb") as f:
            content = file.read()
            await f.write(content)

        return path

    async def download(self, path: str) -> bytes:
        full_path = self.base_path / path
        if not full_path.exists():
            raise FileNotFoundError(path)

        async with aiofiles.open(full_path, "rb") as f:
            return await f.read()

    async def delete(self, path: str) -> bool:
        full_path = self.base_path / path
        if full_path.exists():
            full_path.unlink()
            return True
        return False

    def get_url(self, path: str) -> str:
        return f"/files/{path}"


# S3 storage
class S3Storage(StorageBackend):
    def __init__(
        self,
        bucket: str,
        region: str = "us-east-1",
        access_key: str = None,
        secret_key: str = None
    ):
        self.bucket = bucket
        self.region = region
        self.s3 = boto3.client(
            "s3",
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key
        )

    async def upload(self, file: BinaryIO, path: str) -> str:
        try:
            self.s3.upload_fileobj(file, self.bucket, path)
            return path
        except ClientError as e:
            raise Exception(f"Upload failed: {e}")

    async def download(self, path: str) -> bytes:
        try:
            response = self.s3.get_object(Bucket=self.bucket, Key=path)
            return response["Body"].read()
        except ClientError as e:
            raise FileNotFoundError(path)

    async def delete(self, path: str) -> bool:
        try:
            self.s3.delete_object(Bucket=self.bucket, Key=path)
            return True
        except ClientError:
            return False

    def get_url(self, path: str, expires_in: int = 3600) -> str:
        return self.s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": path},
            ExpiresIn=expires_in
        )


# Google Cloud Storage
from google.cloud import storage as gcs

class GCSStorage(StorageBackend):
    def __init__(self, bucket: str):
        self.client = gcs.Client()
        self.bucket = self.client.bucket(bucket)

    async def upload(self, file: BinaryIO, path: str) -> str:
        blob = self.bucket.blob(path)
        blob.upload_from_file(file)
        return path

    async def download(self, path: str) -> bytes:
        blob = self.bucket.blob(path)
        return blob.download_as_bytes()

    async def delete(self, path: str) -> bool:
        blob = self.bucket.blob(path)
        blob.delete()
        return True

    def get_url(self, path: str, expires_in: int = 3600) -> str:
        blob = self.bucket.blob(path)
        return blob.generate_signed_url(expiration=timedelta(seconds=expires_in))


# Storage factory
def get_storage() -> StorageBackend:
    storage_type = settings.storage_type

    if storage_type == "local":
        return LocalStorage(settings.local_storage_path)
    elif storage_type == "s3":
        return S3Storage(
            bucket=settings.s3_bucket,
            region=settings.s3_region,
            access_key=settings.aws_access_key,
            secret_key=settings.aws_secret_key
        )
    elif storage_type == "gcs":
        return GCSStorage(settings.gcs_bucket)
    else:
        raise ValueError(f"Unknown storage type: {storage_type}")


# FastAPI endpoints
app = FastAPI()


@app.post("/upload")
async def upload_file(
    file: UploadFile,
    storage: StorageBackend = Depends(get_storage)
):
    # Generate unique filename
    ext = Path(file.filename).suffix
    path = f"uploads/{uuid.uuid4()}{ext}"

    # Upload
    await storage.upload(file.file, path)

    return {
        "filename": file.filename,
        "path": path,
        "url": storage.get_url(path)
    }


@app.get("/files/{path:path}")
async def download_file(
    path: str,
    storage: StorageBackend = Depends(get_storage)
):
    try:
        content = await storage.download(path)
        return Response(content=content)
    except FileNotFoundError:
        raise HTTPException(404, "File not found")


@app.delete("/files/{path:path}")
async def delete_file(
    path: str,
    storage: StorageBackend = Depends(get_storage)
):
    deleted = await storage.delete(path)
    if not deleted:
        raise HTTPException(404, "File not found")
    return {"deleted": True}
```

### Search Integration (Elasticsearch)

```python
from fastapi import FastAPI, HTTPException
from elasticsearch import AsyncElasticsearch
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

# Elasticsearch client
es = AsyncElasticsearch(
    hosts=["http://localhost:9200"],
    basic_auth=("elastic", "password")
)

app = FastAPI()


# Index configuration
PRODUCT_INDEX = "products"
PRODUCT_MAPPING = {
    "mappings": {
        "properties": {
            "name": {"type": "text", "analyzer": "standard"},
            "description": {"type": "text", "analyzer": "standard"},
            "category": {"type": "keyword"},
            "price": {"type": "float"},
            "tags": {"type": "keyword"},
            "created_at": {"type": "date"},
            "suggest": {
                "type": "completion",
                "analyzer": "simple"
            }
        }
    },
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0
    }
}


# Initialize index
@app.on_event("startup")
async def create_index():
    if not await es.indices.exists(index=PRODUCT_INDEX):
        await es.indices.create(index=PRODUCT_INDEX, body=PRODUCT_MAPPING)


# Search models
class SearchQuery(BaseModel):
    query: str
    category: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    tags: Optional[List[str]] = None
    page: int = 1
    size: int = 10


class SearchResult(BaseModel):
    total: int
    items: List[dict]
    took_ms: int


# Search service
class SearchService:
    def __init__(self, client: AsyncElasticsearch):
        self.es = client

    async def search_products(self, query: SearchQuery) -> SearchResult:
        # Build query
        must = []
        filter_queries = []

        # Full-text search
        if query.query:
            must.append({
                "multi_match": {
                    "query": query.query,
                    "fields": ["name^2", "description", "tags"],
                    "fuzziness": "AUTO"
                }
            })

        # Filters
        if query.category:
            filter_queries.append({"term": {"category": query.category}})

        if query.min_price is not None or query.max_price is not None:
            range_query = {"range": {"price": {}}}
            if query.min_price is not None:
                range_query["range"]["price"]["gte"] = query.min_price
            if query.max_price is not None:
                range_query["range"]["price"]["lte"] = query.max_price
            filter_queries.append(range_query)

        if query.tags:
            filter_queries.append({"terms": {"tags": query.tags}})

        # Build final query
        body = {
            "query": {
                "bool": {
                    "must": must if must else [{"match_all": {}}],
                    "filter": filter_queries
                }
            },
            "from": (query.page - 1) * query.size,
            "size": query.size,
            "highlight": {
                "fields": {
                    "name": {},
                    "description": {}
                }
            },
            "aggs": {
                "categories": {"terms": {"field": "category"}},
                "price_ranges": {
                    "range": {
                        "field": "price",
                        "ranges": [
                            {"to": 50},
                            {"from": 50, "to": 100},
                            {"from": 100, "to": 500},
                            {"from": 500}
                        ]
                    }
                }
            }
        }

        result = await self.es.search(index=PRODUCT_INDEX, body=body)

        items = []
        for hit in result["hits"]["hits"]:
            item = hit["_source"]
            item["_id"] = hit["_id"]
            item["_score"] = hit["_score"]
            if "highlight" in hit:
                item["_highlight"] = hit["highlight"]
            items.append(item)

        return SearchResult(
            total=result["hits"]["total"]["value"],
            items=items,
            took_ms=result["took"]
        )

    async def index_product(self, product: dict) -> str:
        # Add suggestion field
        product["suggest"] = {
            "input": [product["name"]] + product.get("tags", [])
        }

        result = await self.es.index(
            index=PRODUCT_INDEX,
            document=product
        )
        return result["_id"]

    async def delete_product(self, product_id: str) -> bool:
        try:
            await self.es.delete(index=PRODUCT_INDEX, id=product_id)
            return True
        except:
            return False

    async def suggest(self, prefix: str, size: int = 5) -> List[str]:
        body = {
            "suggest": {
                "product-suggest": {
                    "prefix": prefix,
                    "completion": {
                        "field": "suggest",
                        "size": size
                    }
                }
            }
        }

        result = await self.es.search(index=PRODUCT_INDEX, body=body)
        suggestions = result["suggest"]["product-suggest"][0]["options"]
        return [s["text"] for s in suggestions]


search_service = SearchService(es)


# API endpoints
@app.post("/search", response_model=SearchResult)
async def search(query: SearchQuery):
    return await search_service.search_products(query)


@app.get("/suggest")
async def suggest(q: str, size: int = 5):
    suggestions = await search_service.suggest(q, size)
    return {"suggestions": suggestions}


@app.post("/products/index")
async def index_product(product: dict):
    product_id = await search_service.index_product(product)
    return {"id": product_id}


# Sync database with Elasticsearch
async def sync_products_to_elasticsearch():
    products = await db.execute(select(Product))

    for product in products.scalars():
        await search_service.index_product(product.to_dict())
```

---

## 9.3 Starlette Internals

### Understanding ASGI

```python
from fastapi import FastAPI
from starlette.types import ASGIApp, Receive, Send, Scope, Message
import json

# ASGI application signature
async def app(scope: Scope, receive: Receive, send: Send) -> None:
    """
    scope: Contains request information (type, path, headers, etc.)
    receive: Async callable to receive incoming messages
    send: Async callable to send outgoing messages
    """
    pass


# Simple ASGI app
async def simple_app(scope: Scope, receive: Receive, send: Send):
    if scope["type"] == "http":
        # Send response headers
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"application/json")]
        })

        # Send response body
        await send({
            "type": "http.response.body",
            "body": json.dumps({"message": "Hello"}).encode()
        })


# ASGI middleware
class LoggingMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] == "http":
            print(f"Request: {scope['method']} {scope['path']}")

        await self.app(scope, receive, send)


# Pure ASGI middleware with response modification
class ResponseHeaderMiddleware:
    def __init__(self, app: ASGIApp, headers: dict):
        self.app = app
        self.headers = [
            (k.encode(), v.encode())
            for k, v in headers.items()
        ]

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message: Message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend(self.headers)
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_wrapper)


# Request body reading in ASGI
class RequestBodyMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Read entire body
        body_parts = []
        while True:
            message = await receive()
            body_parts.append(message.get("body", b""))
            if not message.get("more_body", False):
                break

        body = b"".join(body_parts)

        # Log body
        print(f"Request body: {body.decode()}")

        # Create new receive that returns the cached body
        body_sent = False

        async def receive_wrapper():
            nonlocal body_sent
            if not body_sent:
                body_sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            return {"type": "http.disconnect"}

        await self.app(scope, receive_wrapper, send)


# Using with FastAPI
app = FastAPI()

# Add ASGI middleware
app = LoggingMiddleware(app)
app = ResponseHeaderMiddleware(app, {"X-Custom-Header": "value"})
```

### Starlette Components FastAPI Uses

```python
from starlette.applications import Starlette
from starlette.routing import Route, Mount, WebSocketRoute
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
from starlette.background import BackgroundTask
from starlette.exceptions import HTTPException
from starlette.websockets import WebSocket

# Starlette application (what FastAPI extends)
async def homepage(request: Request):
    return JSONResponse({"message": "Hello"})

async def user_page(request: Request):
    user_id = request.path_params["user_id"]
    return JSONResponse({"user_id": user_id})

routes = [
    Route("/", homepage),
    Route("/users/{user_id:int}", user_page),
    Mount("/static", StaticFiles(directory="static"), name="static"),
]

middleware = [
    Middleware(CORSMiddleware, allow_origins=["*"])
]

starlette_app = Starlette(routes=routes, middleware=middleware)


# Starlette components used by FastAPI
from fastapi import FastAPI
from fastapi.routing import APIRoute

# Request (Starlette's Request with extensions)
from starlette.requests import Request

@app.get("/")
async def read_root(request: Request):
    # Access Starlette request features
    client = request.client  # ClientInfo
    cookies = request.cookies  # dict
    headers = request.headers  # Headers
    query_params = request.query_params  # QueryParams
    path_params = request.path_params  # dict
    url = request.url  # URL

    # State (per-request data)
    request.state.user_id = 123

    return {"client": str(client)}


# Response classes
from starlette.responses import (
    Response,
    HTMLResponse,
    PlainTextResponse,
    JSONResponse,
    RedirectResponse,
    StreamingResponse,
    FileResponse
)

@app.get("/responses")
async def various_responses():
    # All these are available in FastAPI
    return JSONResponse({"data": "value"})


# Background tasks
from starlette.background import BackgroundTask

@app.get("/background")
async def with_background():
    def log_message(message: str):
        print(message)

    return Response(
        content="OK",
        background=BackgroundTask(log_message, "Request completed")
    )


# WebSocket
from starlette.websockets import WebSocket, WebSocketDisconnect

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Echo: {data}")
    except WebSocketDisconnect:
        pass


# Middleware classes
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.sessions import SessionMiddleware

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["example.com"])
app.add_middleware(SessionMiddleware, secret_key="secret")
```

### Lifespan Events (Startup/Shutdown)

```python
from fastapi import FastAPI
from contextlib import asynccontextmanager
from typing import AsyncIterator

# Modern lifespan context manager (recommended)
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Startup
    print("Starting up...")
    app.state.db_pool = await create_db_pool()
    app.state.redis = await create_redis_client()
    app.state.http_client = httpx.AsyncClient()

    # Initialize cache
    await app.state.redis.flushdb()

    # Start background tasks
    app.state.scheduler = AsyncIOScheduler()
    app.state.scheduler.start()

    yield

    # Shutdown
    print("Shutting down...")
    await app.state.db_pool.close()
    await app.state.redis.close()
    await app.state.http_client.aclose()
    app.state.scheduler.shutdown()


app = FastAPI(lifespan=lifespan)


# Access state in endpoints
@app.get("/")
async def root(request: Request):
    db_pool = request.app.state.db_pool
    async with db_pool.acquire() as conn:
        result = await conn.fetchone("SELECT 1")
    return {"result": result}


# Legacy approach (deprecated)
@app.on_event("startup")
async def startup_event():
    app.state.db = await create_db_connection()

@app.on_event("shutdown")
async def shutdown_event():
    await app.state.db.close()


# Multiple startup tasks
async def init_database():
    app.state.db = await create_db_pool()
    await run_migrations()

async def init_cache():
    app.state.cache = await create_redis_client()

async def init_services():
    app.state.email_service = EmailService()
    app.state.payment_service = PaymentService()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Run startup tasks concurrently
    await asyncio.gather(
        init_database(),
        init_cache(),
        init_services()
    )

    yield

    # Cleanup
    await app.state.db.close()
    await app.state.cache.close()


# Graceful shutdown handling
import signal

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup
    app.state.is_shutting_down = False

    def handle_signal(signum, frame):
        app.state.is_shutting_down = True

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    yield

    # Wait for in-flight requests
    while app.state.active_requests > 0:
        await asyncio.sleep(0.1)


# Health check using state
@app.get("/health")
async def health(request: Request):
    if request.app.state.is_shutting_down:
        raise HTTPException(503, "Shutting down")
    return {"status": "healthy"}
```

### State Management

```python
from fastapi import FastAPI, Request, Depends
from starlette.datastructures import State
from contextvars import ContextVar
from typing import Optional

app = FastAPI()

# Application state (shared across all requests)
# Access via app.state or request.app.state

@app.on_event("startup")
async def setup_state():
    # Shared resources
    app.state.db_pool = await create_pool()
    app.state.cache = {}
    app.state.config = load_config()
    app.state.feature_flags = {}


# Request state (per-request, not shared)
@app.middleware("http")
async def request_state_middleware(request: Request, call_next):
    # Set per-request state
    request.state.request_id = str(uuid.uuid4())
    request.state.start_time = time.time()
    request.state.user = None

    response = await call_next(request)

    # Access after request
    duration = time.time() - request.state.start_time
    logger.info(f"Request {request.state.request_id} took {duration:.2f}s")

    return response


# Context variables for async-safe state
user_context: ContextVar[Optional[dict]] = ContextVar("user", default=None)
request_id_context: ContextVar[str] = ContextVar("request_id", default="")

@app.middleware("http")
async def context_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    token = request_id_context.set(request_id)

    try:
        response = await call_next(request)
        return response
    finally:
        request_id_context.reset(token)


# Access context in any async function
async def get_current_request_id() -> str:
    return request_id_context.get()


# Typed state with dependency
class AppServices:
    def __init__(self, request: Request):
        self.db = request.app.state.db_pool
        self.cache = request.app.state.cache
        self.config = request.app.state.config


def get_services(request: Request) -> AppServices:
    return AppServices(request)


@app.get("/")
async def endpoint(services: AppServices = Depends(get_services)):
    async with services.db.acquire() as conn:
        return await conn.fetchone("SELECT 1")


# Thread-safe counter
import asyncio
from dataclasses import dataclass, field

@dataclass
class Counter:
    value: int = 0
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def increment(self) -> int:
        async with self._lock:
            self.value += 1
            return self.value

    async def decrement(self) -> int:
        async with self._lock:
            self.value -= 1
            return self.value


@app.on_event("startup")
async def setup_counter():
    app.state.request_counter = Counter()


@app.middleware("http")
async def count_requests(request: Request, call_next):
    await request.app.state.request_counter.increment()
    try:
        return await call_next(request)
    finally:
        await request.app.state.request_counter.decrement()


@app.get("/metrics")
async def metrics(request: Request):
    return {
        "active_requests": request.app.state.request_counter.value
    }
```

### Custom Exception Handlers at Starlette Level

```python
from fastapi import FastAPI
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse, HTMLResponse
from fastapi.exceptions import RequestValidationError
import traceback

app = FastAPI()


# Custom exception
class AppException(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict = None
    ):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}


# Exception handler for custom exception
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details
            }
        }
    )


# Override Starlette's HTTPException handler
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    # Check Accept header for response format
    accept = request.headers.get("accept", "")

    if "text/html" in accept:
        return HTMLResponse(
            content=f"<h1>{exc.status_code}</h1><p>{exc.detail}</p>",
            status_code=exc.status_code
        )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": f"HTTP_{exc.status_code}",
                "message": exc.detail
            }
        }
    )


# Override validation error handler
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError
):
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(x) for x in error["loc"][1:]),
            "message": error["msg"],
            "type": error["type"]
        })

    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "errors": errors
            }
        }
    )


# Catch-all exception handler
@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    # Log the exception
    logger.error(
        f"Unhandled exception: {exc}",
        exc_info=True,
        extra={
            "path": request.url.path,
            "method": request.method
        }
    )

    # Return error response
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An internal error occurred"
            }
        }
    )


# Using in middleware
from starlette.middleware.base import BaseHTTPMiddleware

class ExceptionHandlingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except Exception as exc:
            # Handle at middleware level
            logger.exception("Error in request")

            return JSONResponse(
                status_code=500,
                content={"error": "Internal server error"}
            )


# Register globally via exception_handlers dict
exception_handlers = {
    404: lambda request, exc: JSONResponse(
        status_code=404,
        content={"error": "Not found"}
    ),
    500: lambda request, exc: JSONResponse(
        status_code=500,
        content={"error": "Internal error"}
    )
}

app = FastAPI(exception_handlers=exception_handlers)
```

---

## Summary

Module 9 covered extending FastAPI's capabilities:

1. **Custom Components** - Custom APIRoute classes for timing/logging/caching, custom Request/Response classes, reusable CRUD routers, and plugin architecture

2. **Integrations** - SQLAdmin for admin panels, APScheduler for task scheduling, email sending patterns, file storage backends, and Elasticsearch search

3. **Starlette Internals** - ASGI understanding, Starlette components, lifespan events, state management, and custom exception handlers

These patterns enable building highly customizable and feature-rich FastAPI applications.

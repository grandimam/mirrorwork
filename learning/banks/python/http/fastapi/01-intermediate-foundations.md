# Module 1: Intermediate Foundations

---

## 1.1 Request & Response Deep Dive

### Path Parameters with Validation and Metadata

Path parameters are extracted from the URL path and can be validated using Python type hints and Pydantic.

```python
from fastapi import FastAPI, Path
from enum import Enum

app = FastAPI()

class ItemCategory(str, Enum):
    electronics = "electronics"
    clothing = "clothing"
    food = "food"

@app.get("/items/{item_id}")
async def get_item(
    item_id: int = Path(
        ...,
        title="Item ID",
        description="The unique identifier of the item",
        gt=0,
        le=10000,
        examples=[1, 42, 100]
    )
):
    return {"item_id": item_id}

@app.get("/categories/{category}")
async def get_category(category: ItemCategory):
    return {"category": category, "message": f"Looking at {category.value}"}
```

### Query Parameters: Optional, Required, Lists, and Aliases

```python
from fastapi import FastAPI, Query
from typing import Annotated

app = FastAPI()

@app.get("/search")
async def search_items(
    # Required query parameter
    q: str,
    # Optional with default
    skip: int = 0,
    limit: int = Query(default=10, le=100),
    # Optional (None default)
    category: str | None = None,
    # List of values: /search?tags=python&tags=fastapi
    tags: list[str] = Query(default=[]),
    # Alias: /search?q=test&item-query=another
    item_query: str | None = Query(default=None, alias="item-query"),
    # Deprecated parameter
    old_param: str | None = Query(
        default=None,
        deprecated=True,
        description="Use 'q' instead"
    )
):
    return {
        "q": q,
        "skip": skip,
        "limit": limit,
        "category": category,
        "tags": tags,
        "item_query": item_query
    }
```

### Request Body with Nested Pydantic Models

```python
from fastapi import FastAPI
from pydantic import BaseModel, Field
from datetime import datetime

app = FastAPI()

class Address(BaseModel):
    street: str
    city: str
    country: str
    postal_code: str = Field(pattern=r"^\d{5}(-\d{4})?$")

class UserProfile(BaseModel):
    bio: str | None = None
    website: str | None = None
    social_links: dict[str, str] = {}

class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: str
    password: str = Field(min_length=8)
    address: Address
    profile: UserProfile | None = None
    tags: list[str] = []

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "username": "johndoe",
                    "email": "john@example.com",
                    "password": "secretpass123",
                    "address": {
                        "street": "123 Main St",
                        "city": "Boston",
                        "country": "USA",
                        "postal_code": "02101"
                    },
                    "profile": {
                        "bio": "Developer",
                        "website": "https://example.com"
                    },
                    "tags": ["developer", "python"]
                }
            ]
        }
    }

@app.post("/users")
async def create_user(user: UserCreate):
    return {"message": "User created", "username": user.username}
```

### Form Data and File Uploads

```python
from fastapi import FastAPI, File, UploadFile, Form
from typing import Annotated

app = FastAPI()

# Simple form data
@app.post("/login")
async def login(
    username: Annotated[str, Form()],
    password: Annotated[str, Form()]
):
    return {"username": username}

# Single file upload
@app.post("/upload")
async def upload_file(
    file: UploadFile,
    description: Annotated[str, Form()] = ""
):
    contents = await file.read()
    return {
        "filename": file.filename,
        "content_type": file.content_type,
        "size": len(contents),
        "description": description
    }

# Multiple file uploads
@app.post("/upload-multiple")
async def upload_multiple_files(
    files: list[UploadFile],
    category: Annotated[str, Form()]
):
    file_info = []
    for file in files:
        contents = await file.read()
        file_info.append({
            "filename": file.filename,
            "size": len(contents)
        })
    return {"category": category, "files": file_info}

# File with size/type validation
@app.post("/upload-image")
async def upload_image(
    file: UploadFile = File(description="Image file (max 5MB)")
):
    # Manual validation
    if file.content_type not in ["image/jpeg", "image/png", "image/gif"]:
        raise HTTPException(400, "Invalid image type")

    contents = await file.read()
    if len(contents) > 5 * 1024 * 1024:  # 5MB
        raise HTTPException(400, "File too large")

    return {"filename": file.filename, "size": len(contents)}
```

### Response Models and Status Codes

```python
from fastapi import FastAPI, status
from pydantic import BaseModel, EmailStr

app = FastAPI()

class UserIn(BaseModel):
    username: str
    email: EmailStr
    password: str

class UserOut(BaseModel):
    id: int
    username: str
    email: EmailStr

class UserDB(UserIn):
    id: int
    hashed_password: str

def fake_save_user(user: UserIn) -> UserDB:
    hashed = "hashed_" + user.password
    return UserDB(id=1, **user.model_dump(), hashed_password=hashed)

@app.post(
    "/users",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    response_model_exclude_unset=True,
    summary="Create a new user",
    description="Creates a new user and returns the user data without password"
)
async def create_user(user: UserIn):
    user_db = fake_save_user(user)
    return user_db  # password and hashed_password are filtered out

# Multiple response models
from typing import Union

class ItemBase(BaseModel):
    name: str
    price: float

class ItemPublic(ItemBase):
    pass

class ItemAdmin(ItemBase):
    secret_code: str
    cost: float

@app.get("/items/{item_id}", response_model=Union[ItemAdmin, ItemPublic])
async def get_item(item_id: int, admin: bool = False):
    item = {"name": "Widget", "price": 99.99, "secret_code": "ABC", "cost": 50.0}
    if admin:
        return ItemAdmin(**item)
    return ItemPublic(**item)
```

### Custom Response Classes

```python
from fastapi import FastAPI
from fastapi.responses import (
    JSONResponse,
    HTMLResponse,
    PlainTextResponse,
    RedirectResponse,
    StreamingResponse,
    FileResponse
)
import json

app = FastAPI()

# JSON with custom settings
@app.get("/custom-json")
async def custom_json():
    data = {"message": "Hello", "unicode": "こんにちは"}
    return JSONResponse(
        content=data,
        status_code=200,
        headers={"X-Custom-Header": "value"},
        media_type="application/json; charset=utf-8"
    )

# HTML response
@app.get("/html", response_class=HTMLResponse)
async def get_html():
    return """
    <!DOCTYPE html>
    <html>
        <head><title>FastAPI</title></head>
        <body><h1>Hello from FastAPI</h1></body>
    </html>
    """

# Plain text
@app.get("/text", response_class=PlainTextResponse)
async def get_text():
    return "Plain text response"

# Redirect
@app.get("/redirect")
async def redirect():
    return RedirectResponse(url="/html", status_code=302)

# Streaming response
@app.get("/stream")
async def stream_data():
    async def generate():
        for i in range(10):
            yield f"data: {i}\n\n"
            await asyncio.sleep(0.5)
    return StreamingResponse(generate(), media_type="text/event-stream")

# File response
@app.get("/download")
async def download_file():
    return FileResponse(
        path="report.pdf",
        filename="monthly-report.pdf",
        media_type="application/pdf"
    )
```

### Response Headers and Cookies

```python
from fastapi import FastAPI, Response, Cookie
from fastapi.responses import JSONResponse

app = FastAPI()

# Setting headers via Response parameter
@app.get("/headers")
async def set_headers(response: Response):
    response.headers["X-Custom-Header"] = "custom-value"
    response.headers["X-Process-Time"] = "0.123"
    return {"message": "Check the headers"}

# Setting cookies
@app.post("/login")
async def login(response: Response):
    response.set_cookie(
        key="session_id",
        value="abc123xyz",
        max_age=3600,
        httponly=True,
        secure=True,
        samesite="lax"
    )
    return {"message": "Logged in"}

# Reading cookies
@app.get("/me")
async def get_current_user(
    session_id: str | None = Cookie(default=None)
):
    if not session_id:
        return {"message": "Not logged in"}
    return {"session_id": session_id}

# Deleting cookies
@app.post("/logout")
async def logout(response: Response):
    response.delete_cookie("session_id")
    return {"message": "Logged out"}

# Using JSONResponse directly for full control
@app.get("/full-control")
async def full_control():
    response = JSONResponse(
        content={"message": "Full control"},
        headers={"X-Custom": "value"}
    )
    response.set_cookie("tracking", "xyz", max_age=86400)
    return response
```

---

## 1.2 Pydantic Mastery

### Field Validators and Model Validators

```python
from pydantic import (
    BaseModel,
    field_validator,
    model_validator,
    ValidationError,
    Field
)
from typing import Self

class UserRegistration(BaseModel):
    username: str
    email: str
    password: str
    password_confirm: str
    age: int

    # Field validator - runs on a single field
    @field_validator("username")
    @classmethod
    def username_alphanumeric(cls, v: str) -> str:
        if not v.isalnum():
            raise ValueError("Username must be alphanumeric")
        return v.lower()

    @field_validator("email")
    @classmethod
    def email_valid(cls, v: str) -> str:
        if "@" not in v:
            raise ValueError("Invalid email format")
        return v.lower()

    @field_validator("age")
    @classmethod
    def age_valid(cls, v: int) -> int:
        if v < 13:
            raise ValueError("Must be at least 13 years old")
        if v > 120:
            raise ValueError("Invalid age")
        return v

    # Model validator - runs on the entire model
    @model_validator(mode="after")
    def check_passwords_match(self) -> Self:
        if self.password != self.password_confirm:
            raise ValueError("Passwords do not match")
        return self

    # Before validation (access raw input)
    @model_validator(mode="before")
    @classmethod
    def check_required_fields(cls, data: dict) -> dict:
        if isinstance(data, dict):
            # Normalize keys to lowercase
            return {k.lower(): v for k, v in data.items()}
        return data


# Validator with multiple fields
class DateRange(BaseModel):
    start_date: str
    end_date: str

    @model_validator(mode="after")
    def validate_date_range(self) -> Self:
        from datetime import datetime
        start = datetime.fromisoformat(self.start_date)
        end = datetime.fromisoformat(self.end_date)
        if end < start:
            raise ValueError("end_date must be after start_date")
        return self
```

### Custom Types and Constrained Types

```python
from pydantic import (
    BaseModel,
    Field,
    constr,
    conint,
    confloat,
    conlist,
    AfterValidator,
    BeforeValidator
)
from typing import Annotated
from datetime import datetime

# Constrained types
class Product(BaseModel):
    name: constr(min_length=1, max_length=100, strip_whitespace=True)
    sku: constr(pattern=r"^[A-Z]{3}-\d{4}$")  # ABC-1234
    price: confloat(gt=0, le=1000000)
    quantity: conint(ge=0)
    tags: conlist(str, min_length=1, max_length=10)


# Custom types with Annotated
def validate_isbn(v: str) -> str:
    """Validate ISBN-13 format"""
    clean = v.replace("-", "").replace(" ", "")
    if len(clean) != 13 or not clean.isdigit():
        raise ValueError("Invalid ISBN-13 format")
    return clean

ISBN = Annotated[str, AfterValidator(validate_isbn)]

def parse_flexible_date(v: str | datetime) -> datetime:
    """Accept multiple date formats"""
    if isinstance(v, datetime):
        return v
    for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%m-%d-%Y"]:
        try:
            return datetime.strptime(v, fmt)
        except ValueError:
            continue
    raise ValueError("Could not parse date")

FlexibleDate = Annotated[datetime, BeforeValidator(parse_flexible_date)]

class Book(BaseModel):
    title: str
    isbn: ISBN
    published: FlexibleDate


# Reusable custom types
PositiveInt = Annotated[int, Field(gt=0)]
EmailStr = Annotated[str, Field(pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")]
Slug = Annotated[str, Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")]

class Article(BaseModel):
    id: PositiveInt
    slug: Slug
    author_email: EmailStr
```

### Computed Fields

```python
from pydantic import BaseModel, computed_field, Field
from datetime import datetime, date

class Order(BaseModel):
    items: list[dict]
    tax_rate: float = 0.08
    discount_percent: float = 0

    @computed_field
    @property
    def subtotal(self) -> float:
        return sum(item["price"] * item["quantity"] for item in self.items)

    @computed_field
    @property
    def discount_amount(self) -> float:
        return self.subtotal * (self.discount_percent / 100)

    @computed_field
    @property
    def tax_amount(self) -> float:
        return (self.subtotal - self.discount_amount) * self.tax_rate

    @computed_field
    @property
    def total(self) -> float:
        return self.subtotal - self.discount_amount + self.tax_amount


class Person(BaseModel):
    first_name: str
    last_name: str
    birth_date: date

    @computed_field
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @computed_field
    @property
    def age(self) -> int:
        today = date.today()
        age = today.year - self.birth_date.year
        if (today.month, today.day) < (self.birth_date.month, self.birth_date.day):
            age -= 1
        return age
```

### Model Inheritance and Composition

```python
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Generic, TypeVar

# Basic inheritance
class TimestampMixin(BaseModel):
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime | None = None

class BaseEntity(TimestampMixin):
    id: int

class User(BaseEntity):
    username: str
    email: str

class Post(BaseEntity):
    title: str
    content: str
    author_id: int


# Composition
class Address(BaseModel):
    street: str
    city: str
    country: str

class ContactInfo(BaseModel):
    email: str
    phone: str | None = None
    address: Address

class Company(BaseModel):
    name: str
    contact: ContactInfo
    employees: list["Employee"] = []

class Employee(BaseModel):
    name: str
    position: str
    contact: ContactInfo


# Request/Response model pattern
class UserBase(BaseModel):
    username: str
    email: str

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    username: str | None = None
    email: str | None = None
    password: str | None = None

class UserInDB(UserBase):
    id: int
    hashed_password: str
    is_active: bool = True

class UserResponse(UserBase):
    id: int
    is_active: bool

    model_config = {"from_attributes": True}
```

### Serialization Modes

```python
from pydantic import BaseModel, Field, field_serializer
from datetime import datetime
from enum import Enum

class Status(str, Enum):
    active = "active"
    inactive = "inactive"

class User(BaseModel):
    id: int
    name: str
    email: str
    password: str = Field(exclude=True)  # Never serialize
    status: Status
    created_at: datetime
    secret_token: str | None = None

    @field_serializer("created_at")
    def serialize_datetime(self, dt: datetime) -> str:
        return dt.strftime("%Y-%m-%d %H:%M:%S")

user = User(
    id=1,
    name="John",
    email="john@example.com",
    password="secret",
    status=Status.active,
    created_at=datetime.now(),
    secret_token="abc123"
)

# Different serialization modes
print(user.model_dump())
# {'id': 1, 'name': 'John', 'email': 'john@example.com',
#  'status': 'active', 'created_at': '2024-01-15 10:30:00', 'secret_token': 'abc123'}

print(user.model_dump(exclude={"secret_token"}))
# Excludes secret_token

print(user.model_dump(include={"id", "name", "email"}))
# Only includes specified fields

print(user.model_dump(exclude_none=True))
# Excludes fields with None values

print(user.model_dump(exclude_unset=True))
# Excludes fields not explicitly set

print(user.model_dump(by_alias=True))
# Uses field aliases

print(user.model_dump_json(indent=2))
# Returns JSON string

print(user.model_json_schema())
# Returns JSON Schema dict
```

### Generic Models

```python
from pydantic import BaseModel
from typing import Generic, TypeVar

T = TypeVar("T")

class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def has_prev(self) -> bool:
        return self.page > 1


class User(BaseModel):
    id: int
    name: str

class Product(BaseModel):
    id: int
    name: str
    price: float

# Usage
user_page = PaginatedResponse[User](
    items=[User(id=1, name="John"), User(id=2, name="Jane")],
    total=50,
    page=1,
    page_size=10,
    total_pages=5
)

product_page = PaginatedResponse[Product](
    items=[Product(id=1, name="Widget", price=9.99)],
    total=100,
    page=2,
    page_size=20,
    total_pages=5
)


# API Response wrapper
class APIResponse(BaseModel, Generic[T]):
    success: bool
    data: T | None = None
    error: str | None = None

    @classmethod
    def ok(cls, data: T) -> "APIResponse[T]":
        return cls(success=True, data=data)

    @classmethod
    def fail(cls, error: str) -> "APIResponse[T]":
        return cls(success=False, error=error)
```

### Discriminated Unions

```python
from pydantic import BaseModel, Field
from typing import Literal, Union, Annotated
from datetime import datetime

# Discriminated union with literal types
class CreditCardPayment(BaseModel):
    type: Literal["credit_card"]
    card_number: str
    expiry: str
    cvv: str

class PayPalPayment(BaseModel):
    type: Literal["paypal"]
    email: str

class BankTransfer(BaseModel):
    type: Literal["bank_transfer"]
    account_number: str
    routing_number: str

# Using discriminator
Payment = Annotated[
    Union[CreditCardPayment, PayPalPayment, BankTransfer],
    Field(discriminator="type")
]

class Order(BaseModel):
    id: int
    amount: float
    payment: Payment

# FastAPI automatically handles this
from fastapi import FastAPI
app = FastAPI()

@app.post("/orders")
async def create_order(order: Order):
    match order.payment:
        case CreditCardPayment():
            return {"method": "Processing credit card"}
        case PayPalPayment():
            return {"method": "Redirecting to PayPal"}
        case BankTransfer():
            return {"method": "Awaiting bank transfer"}


# Event sourcing example
class UserCreated(BaseModel):
    event_type: Literal["user_created"]
    user_id: int
    username: str
    timestamp: datetime

class UserUpdated(BaseModel):
    event_type: Literal["user_updated"]
    user_id: int
    changes: dict
    timestamp: datetime

class UserDeleted(BaseModel):
    event_type: Literal["user_deleted"]
    user_id: int
    timestamp: datetime

UserEvent = Annotated[
    Union[UserCreated, UserUpdated, UserDeleted],
    Field(discriminator="event_type")
]

class EventBatch(BaseModel):
    events: list[UserEvent]
```

---

## 1.3 Dependency Injection System

### Function Dependencies

```python
from fastapi import FastAPI, Depends, Query, HTTPException
from typing import Annotated

app = FastAPI()

# Simple dependency
async def common_parameters(
    q: str | None = None,
    skip: int = 0,
    limit: int = Query(default=100, le=100)
) -> dict:
    return {"q": q, "skip": skip, "limit": limit}

CommonParams = Annotated[dict, Depends(common_parameters)]

@app.get("/items")
async def list_items(params: CommonParams):
    return {"params": params}

@app.get("/users")
async def list_users(params: CommonParams):
    return {"params": params}


# Dependency with validation
async def verify_token(token: str = Query(...)) -> str:
    if token != "valid-token":
        raise HTTPException(status_code=401, detail="Invalid token")
    return token

@app.get("/protected")
async def protected_route(token: Annotated[str, Depends(verify_token)]):
    return {"token": token}


# Dependency that returns data
async def get_current_user(token: Annotated[str, Depends(verify_token)]) -> dict:
    # In reality, decode token and fetch user
    return {"id": 1, "username": "john", "token": token}

CurrentUser = Annotated[dict, Depends(get_current_user)]

@app.get("/me")
async def get_me(user: CurrentUser):
    return user
```

### Class-Based Dependencies

```python
from fastapi import FastAPI, Depends, Query
from typing import Annotated

app = FastAPI()

# Callable class dependency
class Pagination:
    def __init__(
        self,
        page: int = Query(1, ge=1),
        page_size: int = Query(10, ge=1, le=100)
    ):
        self.page = page
        self.page_size = page_size
        self.offset = (page - 1) * page_size

@app.get("/items")
async def list_items(pagination: Annotated[Pagination, Depends()]):
    return {
        "page": pagination.page,
        "page_size": pagination.page_size,
        "offset": pagination.offset
    }


# Class with initialization
class DatabaseSession:
    def __init__(self):
        self.connection = None

    def __call__(self):
        # Create and return session
        self.connection = "db_connection"
        return self

db_session = DatabaseSession()

@app.get("/data")
async def get_data(db: Annotated[DatabaseSession, Depends(db_session)]):
    return {"connection": db.connection}


# Service class pattern
class ItemService:
    def __init__(self, db: Annotated[DatabaseSession, Depends(db_session)]):
        self.db = db

    def get_items(self) -> list:
        return [{"id": 1, "name": "Item 1"}]

    def get_item(self, item_id: int) -> dict:
        return {"id": item_id, "name": f"Item {item_id}"}

@app.get("/items")
async def list_items(service: Annotated[ItemService, Depends()]):
    return service.get_items()
```

### Nested Dependencies

```python
from fastapi import FastAPI, Depends, Header, HTTPException
from typing import Annotated

app = FastAPI()

# Layer 1: Extract token
async def get_token(authorization: str = Header(...)) -> str:
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Invalid authorization header")
    return authorization.replace("Bearer ", "")

# Layer 2: Validate and decode token
async def decode_token(token: Annotated[str, Depends(get_token)]) -> dict:
    # Simulate JWT decoding
    if token == "invalid":
        raise HTTPException(401, "Invalid token")
    return {"user_id": 1, "role": "admin"}

# Layer 3: Fetch user from database
async def get_current_user(payload: Annotated[dict, Depends(decode_token)]) -> dict:
    # Simulate database lookup
    return {
        "id": payload["user_id"],
        "username": "john",
        "role": payload["role"]
    }

# Layer 4: Role-based access
def require_role(required_role: str):
    async def check_role(user: Annotated[dict, Depends(get_current_user)]) -> dict:
        if user["role"] != required_role:
            raise HTTPException(403, f"Requires {required_role} role")
        return user
    return check_role

CurrentUser = Annotated[dict, Depends(get_current_user)]
AdminUser = Annotated[dict, Depends(require_role("admin"))]

@app.get("/profile")
async def get_profile(user: CurrentUser):
    return user

@app.get("/admin")
async def admin_panel(user: AdminUser):
    return {"message": "Welcome admin", "user": user}
```

### Yield Dependencies with Cleanup

```python
from fastapi import FastAPI, Depends
from typing import Annotated, Generator
from contextlib import contextmanager

app = FastAPI()

# Database session with cleanup
class DBSession:
    def __init__(self):
        self.connected = False

    def connect(self):
        self.connected = True
        print("Database connected")

    def close(self):
        self.connected = False
        print("Database disconnected")

    def query(self, sql: str) -> list:
        return [{"id": 1}]

def get_db() -> Generator[DBSession, None, None]:
    db = DBSession()
    db.connect()
    try:
        yield db
    finally:
        db.close()

DB = Annotated[DBSession, Depends(get_db)]

@app.get("/items")
async def get_items(db: DB):
    return db.query("SELECT * FROM items")


# File handling dependency
def get_temp_file():
    import tempfile
    import os

    fd, path = tempfile.mkstemp()
    file = os.fdopen(fd, 'w+')
    try:
        yield file, path
    finally:
        file.close()
        os.unlink(path)

@app.post("/process")
async def process_data(temp: Annotated[tuple, Depends(get_temp_file)]):
    file, path = temp
    file.write("temporary data")
    return {"temp_path": path}


# Async generator dependency
async def get_async_client():
    import httpx
    async with httpx.AsyncClient() as client:
        yield client

@app.get("/external")
async def fetch_external(client: Annotated["httpx.AsyncClient", Depends(get_async_client)]):
    response = await client.get("https://api.example.com/data")
    return response.json()
```

### Dependency Caching and Scopes

```python
from fastapi import FastAPI, Depends
from typing import Annotated
import uuid

app = FastAPI()

# By default, dependencies are cached per request
def get_request_id() -> str:
    return str(uuid.uuid4())

RequestID = Annotated[str, Depends(get_request_id)]

@app.get("/test")
async def test(
    id1: RequestID,
    id2: RequestID  # Same value as id1 (cached)
):
    return {"id1": id1, "id2": id2, "same": id1 == id2}


# Disable caching with use_cache=False
def get_unique_id() -> str:
    return str(uuid.uuid4())

@app.get("/unique")
async def unique(
    id1: Annotated[str, Depends(get_unique_id)],
    id2: Annotated[str, Depends(get_unique_id, use_cache=False)]  # Different value
):
    return {"id1": id1, "id2": id2, "same": id1 == id2}


# Shared state across requests (module-level)
class AppState:
    def __init__(self):
        self.counter = 0
        self.cache = {}

app_state = AppState()

def get_app_state() -> AppState:
    return app_state

@app.get("/counter")
async def increment(state: Annotated[AppState, Depends(get_app_state)]):
    state.counter += 1
    return {"count": state.counter}
```

### Global Dependencies

```python
from fastapi import FastAPI, Depends, Header, HTTPException, Request
from typing import Annotated

# Dependency applied to all routes
async def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != "secret-api-key":
        raise HTTPException(401, "Invalid API key")

# Apply to entire app
app = FastAPI(dependencies=[Depends(verify_api_key)])

@app.get("/items")
async def list_items():
    return {"items": []}

@app.get("/users")
async def list_users():
    return {"users": []}


# Apply to router
from fastapi import APIRouter

async def log_request(request: Request):
    print(f"Request: {request.method} {request.url.path}")

router = APIRouter(
    prefix="/admin",
    dependencies=[Depends(log_request)]
)

@router.get("/dashboard")
async def dashboard():
    return {"dashboard": "data"}

@router.get("/settings")
async def settings():
    return {"settings": "data"}

app.include_router(router)


# Conditional global dependencies
from functools import wraps

def conditional_dependency(condition: bool):
    async def dependency():
        if condition:
            # Do something
            pass
    return dependency

app_with_condition = FastAPI(
    dependencies=[Depends(conditional_dependency(True))]
)
```

### Overriding Dependencies for Testing

```python
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from typing import Annotated

app = FastAPI()

# Real dependency
async def get_database():
    return {"type": "production", "host": "prod-db.example.com"}

async def get_current_user(db: Annotated[dict, Depends(get_database)]) -> dict:
    return {"id": 1, "username": "real_user", "db": db["type"]}

CurrentUser = Annotated[dict, Depends(get_current_user)]

@app.get("/profile")
async def get_profile(user: CurrentUser):
    return user


# Test file
def test_profile():
    # Mock dependencies
    async def mock_database():
        return {"type": "test", "host": "localhost"}

    async def mock_current_user():
        return {"id": 999, "username": "test_user", "db": "test"}

    # Override dependencies
    app.dependency_overrides[get_database] = mock_database
    app.dependency_overrides[get_current_user] = mock_current_user

    client = TestClient(app)
    response = client.get("/profile")

    assert response.status_code == 200
    assert response.json()["username"] == "test_user"

    # Clean up
    app.dependency_overrides.clear()


# Fixture-based approach with pytest
import pytest

@pytest.fixture
def override_deps():
    async def mock_user():
        return {"id": 1, "username": "fixture_user"}

    app.dependency_overrides[get_current_user] = mock_user
    yield
    app.dependency_overrides.clear()

def test_with_fixture(override_deps):
    client = TestClient(app)
    response = client.get("/profile")
    assert response.json()["username"] == "fixture_user"
```

---

## 1.4 Database Integration

### SQLAlchemy Setup with FastAPI

```python
# database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = "postgresql://user:password@localhost/dbname"

engine = create_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


# models.py
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    posts = relationship("Post", back_populates="author")


class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    content = Column(String)
    author_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

    author = relationship("User", back_populates="posts")


# dependencies.py
from fastapi import Depends
from sqlalchemy.orm import Session
from typing import Annotated, Generator

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

DB = Annotated[Session, Depends(get_db)]


# main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

class UserCreate(BaseModel):
    email: str
    username: str
    password: str

class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    is_active: bool

    model_config = {"from_attributes": True}

@app.post("/users", response_model=UserResponse)
def create_user(user: UserCreate, db: DB):
    db_user = User(
        email=user.email,
        username=user.username,
        hashed_password=f"hashed_{user.password}"
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@app.get("/users/{user_id}", response_model=UserResponse)
def get_user(user_id: int, db: DB):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    return user
```

### Sync vs Async Database Drivers

```python
# Synchronous (traditional)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

SYNC_DATABASE_URL = "postgresql://user:password@localhost/db"

sync_engine = create_engine(SYNC_DATABASE_URL)
SyncSession = sessionmaker(bind=sync_engine)


# Asynchronous with asyncpg
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

ASYNC_DATABASE_URL = "postgresql+asyncpg://user:password@localhost/db"

async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    pool_size=5,
    max_overflow=10
)

AsyncSessionLocal = sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)


# Async dependency
from typing import AsyncGenerator

async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


# Async CRUD operations
from sqlalchemy import select
from fastapi import FastAPI, Depends
from typing import Annotated

app = FastAPI()

AsyncDB = Annotated[AsyncSession, Depends(get_async_db)]

@app.get("/users/{user_id}")
async def get_user(user_id: int, db: AsyncDB):
    result = await db.execute(
        select(User).filter(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")
    return user

@app.post("/users")
async def create_user(user: UserCreate, db: AsyncDB):
    db_user = User(
        email=user.email,
        username=user.username,
        hashed_password=f"hashed_{user.password}"
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

@app.get("/users")
async def list_users(db: AsyncDB, skip: int = 0, limit: int = 100):
    result = await db.execute(
        select(User).offset(skip).limit(limit)
    )
    return result.scalars().all()
```

### Session Management Patterns

```python
from contextlib import contextmanager, asynccontextmanager
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

# Context manager for manual session control
@contextmanager
def session_scope():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

# Usage
def do_something():
    with session_scope() as session:
        user = User(email="test@example.com", username="test")
        session.add(user)
    # Auto-commits on exit


# Async context manager
@asynccontextmanager
async def async_session_scope():
    session = AsyncSessionLocal()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


# Transaction decorator
from functools import wraps

def transactional(func):
    @wraps(func)
    async def wrapper(*args, db: AsyncSession, **kwargs):
        async with db.begin():
            return await func(*args, db=db, **kwargs)
    return wrapper

@app.post("/transfer")
@transactional
async def transfer_funds(
    from_id: int,
    to_id: int,
    amount: float,
    db: AsyncDB
):
    # All operations in single transaction
    from_account = await db.get(Account, from_id)
    to_account = await db.get(Account, to_id)

    from_account.balance -= amount
    to_account.balance += amount
    # Commits automatically on success, rollback on error


# Nested transactions with savepoints
@app.post("/complex-operation")
async def complex_operation(db: AsyncDB):
    async with db.begin():
        # Outer transaction
        user = User(email="new@example.com", username="new")
        db.add(user)

        try:
            async with db.begin_nested():
                # Savepoint
                risky_operation()
        except Exception:
            # Savepoint rolled back, outer transaction continues
            pass

        # This still commits
        await db.commit()
```

### Repository Pattern Implementation

```python
# repositories/base.py
from typing import Generic, TypeVar, Type, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.orm import DeclarativeBase

ModelType = TypeVar("ModelType", bound=DeclarativeBase)

class BaseRepository(Generic[ModelType]):
    def __init__(self, model: Type[ModelType], db: AsyncSession):
        self.model = model
        self.db = db

    async def get(self, id: int) -> Optional[ModelType]:
        return await self.db.get(self.model, id)

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 100
    ) -> List[ModelType]:
        result = await self.db.execute(
            select(self.model).offset(skip).limit(limit)
        )
        return result.scalars().all()

    async def create(self, **kwargs) -> ModelType:
        instance = self.model(**kwargs)
        self.db.add(instance)
        await self.db.commit()
        await self.db.refresh(instance)
        return instance

    async def update(self, id: int, **kwargs) -> Optional[ModelType]:
        await self.db.execute(
            update(self.model)
            .where(self.model.id == id)
            .values(**kwargs)
        )
        await self.db.commit()
        return await self.get(id)

    async def delete(self, id: int) -> bool:
        result = await self.db.execute(
            delete(self.model).where(self.model.id == id)
        )
        await self.db.commit()
        return result.rowcount > 0


# repositories/user.py
from sqlalchemy import select

class UserRepository(BaseRepository[User]):
    def __init__(self, db: AsyncSession):
        super().__init__(User, db)

    async def get_by_email(self, email: str) -> Optional[User]:
        result = await self.db.execute(
            select(User).filter(User.email == email)
        )
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> Optional[User]:
        result = await self.db.execute(
            select(User).filter(User.username == username)
        )
        return result.scalar_one_or_none()

    async def get_active_users(self) -> List[User]:
        result = await self.db.execute(
            select(User).filter(User.is_active == True)
        )
        return result.scalars().all()


# dependencies.py
def get_user_repository(db: AsyncDB) -> UserRepository:
    return UserRepository(db)

UserRepo = Annotated[UserRepository, Depends(get_user_repository)]


# routes/users.py
@app.get("/users/{user_id}")
async def get_user(user_id: int, repo: UserRepo):
    user = await repo.get(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    return user

@app.post("/users")
async def create_user(user: UserCreate, repo: UserRepo):
    existing = await repo.get_by_email(user.email)
    if existing:
        raise HTTPException(400, "Email already registered")

    return await repo.create(
        email=user.email,
        username=user.username,
        hashed_password=f"hashed_{user.password}"
    )
```

### Database Migrations with Alembic

```bash
# Install alembic
pip install alembic

# Initialize alembic in project
alembic init alembic
```

```python
# alembic/env.py
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# Import your models
from app.database import Base
from app.models import User, Post  # Import all models

config = context.config

# Set database URL from your config
from app.config import settings
config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata

def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

```bash
# Generate migration
alembic revision --autogenerate -m "Add users table"

# Run migrations
alembic upgrade head

# Rollback
alembic downgrade -1

# View history
alembic history

# View current version
alembic current
```

```python
# Example migration file: alembic/versions/xxx_add_users_table.py
from alembic import op
import sqlalchemy as sa

revision = 'abc123'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('username', sa.String(), nullable=False),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    op.create_index('ix_users_username', 'users', ['username'], unique=True)

def downgrade():
    op.drop_index('ix_users_username', table_name='users')
    op.drop_index('ix_users_email', table_name='users')
    op.drop_table('users')
```

### Connection Pooling Configuration

```python
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine

# Sync engine with pooling
sync_engine = create_engine(
    "postgresql://user:pass@localhost/db",

    # Pool size (number of connections to keep open)
    pool_size=5,

    # Additional connections when pool is exhausted
    max_overflow=10,

    # Recycle connections after N seconds
    pool_recycle=3600,

    # Check connection validity before using
    pool_pre_ping=True,

    # Timeout waiting for connection from pool
    pool_timeout=30,

    # Log all SQL statements
    echo=False,

    # Use LIFO to reuse recent connections
    pool_use_lifo=True
)

# Async engine with pooling
async_engine = create_async_engine(
    "postgresql+asyncpg://user:pass@localhost/db",
    pool_size=5,
    max_overflow=10,
    pool_recycle=3600,
    pool_pre_ping=True
)


# NullPool for serverless environments
from sqlalchemy.pool import NullPool

serverless_engine = create_engine(
    DATABASE_URL,
    poolclass=NullPool
)


# Connection pool monitoring
from sqlalchemy import event

@event.listens_for(sync_engine, "checkout")
def on_checkout(dbapi_conn, connection_record, connection_proxy):
    print("Connection checked out from pool")

@event.listens_for(sync_engine, "checkin")
def on_checkin(dbapi_conn, connection_record):
    print("Connection returned to pool")

# Check pool status
print(f"Pool size: {sync_engine.pool.size()}")
print(f"Checked out: {sync_engine.pool.checkedout()}")
print(f"Overflow: {sync_engine.pool.overflow()}")
```

### Multiple Database Support

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from fastapi import FastAPI, Depends
from typing import Annotated

# Multiple database engines
engines = {
    "primary": create_async_engine("postgresql+asyncpg://user:pass@primary/db"),
    "replica": create_async_engine("postgresql+asyncpg://user:pass@replica/db"),
    "analytics": create_async_engine("postgresql+asyncpg://user:pass@analytics/db")
}

sessions = {
    name: sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    for name, engine in engines.items()
}


# Database-specific dependencies
async def get_primary_db():
    async with sessions["primary"]() as session:
        yield session

async def get_replica_db():
    async with sessions["replica"]() as session:
        yield session

async def get_analytics_db():
    async with sessions["analytics"]() as session:
        yield session

PrimaryDB = Annotated[AsyncSession, Depends(get_primary_db)]
ReplicaDB = Annotated[AsyncSession, Depends(get_replica_db)]
AnalyticsDB = Annotated[AsyncSession, Depends(get_analytics_db)]


app = FastAPI()

# Write to primary
@app.post("/users")
async def create_user(user: UserCreate, db: PrimaryDB):
    db_user = User(**user.model_dump())
    db.add(db_user)
    await db.commit()
    return db_user

# Read from replica
@app.get("/users")
async def list_users(db: ReplicaDB):
    result = await db.execute(select(User))
    return result.scalars().all()

# Analytics queries
@app.get("/analytics/user-stats")
async def user_stats(db: AnalyticsDB):
    result = await db.execute("""
        SELECT DATE(created_at), COUNT(*)
        FROM users
        GROUP BY DATE(created_at)
    """)
    return result.all()


# Routing database selection based on request
def get_db_for_operation(write: bool = False):
    async def dependency():
        db_name = "primary" if write else "replica"
        async with sessions[db_name]() as session:
            yield session
    return dependency

@app.get("/items")
async def list_items(
    db: Annotated[AsyncSession, Depends(get_db_for_operation(write=False))]
):
    result = await db.execute(select(Item))
    return result.scalars().all()
```

---

## Summary

Module 1 covered the foundational topics for intermediate FastAPI development:

1. **Request & Response** - Deep understanding of path/query parameters, request bodies, file uploads, response models, and custom responses
2. **Pydantic Mastery** - Validators, custom types, computed fields, inheritance, serialization, generics, and discriminated unions
3. **Dependency Injection** - Function/class dependencies, nesting, yield dependencies, caching, global dependencies, and testing overrides
4. **Database Integration** - SQLAlchemy setup, sync/async drivers, session management, repository pattern, Alembic migrations, connection pooling, and multiple databases

These concepts form the foundation for building robust FastAPI applications and are prerequisites for the advanced topics in subsequent modules.

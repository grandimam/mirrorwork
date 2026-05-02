# Module 5: Testing Strategies

---

## 5.1 Unit Testing

### TestClient Usage

```python
from fastapi import FastAPI, Depends, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

app = FastAPI()

class Item(BaseModel):
    name: str
    price: float

items_db = {}

@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.get("/items/{item_id}")
async def get_item(item_id: int):
    if item_id not in items_db:
        raise HTTPException(status_code=404, detail="Item not found")
    return items_db[item_id]

@app.post("/items", status_code=201)
async def create_item(item: Item):
    item_id = len(items_db) + 1
    items_db[item_id] = item.model_dump()
    return {"id": item_id, **item.model_dump()}


# Basic TestClient usage
client = TestClient(app)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Hello World"}

def test_create_item():
    response = client.post(
        "/items",
        json={"name": "Widget", "price": 9.99}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Widget"
    assert data["price"] == 9.99
    assert "id" in data

def test_get_item_not_found():
    response = client.get("/items/9999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Item not found"


# Testing with headers
def test_with_headers():
    response = client.get(
        "/protected",
        headers={"Authorization": "Bearer test-token"}
    )
    assert response.status_code == 200

# Testing with query parameters
def test_with_query_params():
    response = client.get(
        "/search",
        params={"q": "test", "limit": 10}
    )
    assert response.status_code == 200

# Testing file uploads
def test_file_upload():
    with open("test.txt", "rb") as f:
        response = client.post(
            "/upload",
            files={"file": ("test.txt", f, "text/plain")}
        )
    assert response.status_code == 200

# Testing form data
def test_form_data():
    response = client.post(
        "/login",
        data={"username": "john", "password": "secret"}
    )
    assert response.status_code == 200

# Testing cookies
def test_cookies():
    response = client.get(
        "/protected",
        cookies={"session_id": "abc123"}
    )
    assert response.status_code == 200

# Testing response cookies
def test_response_cookies():
    response = client.post("/login", data={"username": "john", "password": "secret"})
    assert "session_id" in response.cookies

# Testing redirects
def test_redirect():
    response = client.get("/old-url", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/new-url"

    # Following redirects
    response = client.get("/old-url", follow_redirects=True)
    assert response.status_code == 200
```

### Testing with Pytest

```python
# conftest.py
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.database import Base, get_db

# Test database
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session")
def db_engine():
    """Create test database engine"""
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session(db_engine):
    """Create a fresh database session for each test"""
    connection = db_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def client(db_session):
    """Create test client with overridden dependencies"""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers():
    """Fixture for authentication headers"""
    return {"Authorization": "Bearer test-token"}


@pytest.fixture
def sample_user():
    """Fixture for sample user data"""
    return {
        "username": "testuser",
        "email": "test@example.com",
        "password": "testpass123"
    }


# test_users.py
class TestUserEndpoints:
    def test_create_user(self, client, sample_user):
        response = client.post("/users", json=sample_user)
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == sample_user["username"]
        assert data["email"] == sample_user["email"]
        assert "password" not in data

    def test_create_user_duplicate_email(self, client, sample_user):
        # Create first user
        client.post("/users", json=sample_user)
        # Try to create duplicate
        response = client.post("/users", json=sample_user)
        assert response.status_code == 409

    def test_get_user(self, client, sample_user):
        # Create user
        create_response = client.post("/users", json=sample_user)
        user_id = create_response.json()["id"]

        # Get user
        response = client.get(f"/users/{user_id}")
        assert response.status_code == 200
        assert response.json()["username"] == sample_user["username"]

    def test_list_users(self, client, sample_user):
        # Create multiple users
        for i in range(3):
            user = {**sample_user, "email": f"test{i}@example.com", "username": f"user{i}"}
            client.post("/users", json=user)

        response = client.get("/users")
        assert response.status_code == 200
        assert len(response.json()) >= 3

    def test_update_user(self, client, sample_user, auth_headers):
        # Create user
        create_response = client.post("/users", json=sample_user)
        user_id = create_response.json()["id"]

        # Update user
        response = client.put(
            f"/users/{user_id}",
            json={"username": "updated"},
            headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["username"] == "updated"

    def test_delete_user(self, client, sample_user, auth_headers):
        # Create user
        create_response = client.post("/users", json=sample_user)
        user_id = create_response.json()["id"]

        # Delete user
        response = client.delete(f"/users/{user_id}", headers=auth_headers)
        assert response.status_code == 204

        # Verify deleted
        response = client.get(f"/users/{user_id}")
        assert response.status_code == 404


# Parametrized tests
@pytest.mark.parametrize("email,expected_status", [
    ("valid@example.com", 201),
    ("invalid-email", 422),
    ("", 422),
    ("a@b.c", 201),
])
def test_user_email_validation(client, email, expected_status):
    response = client.post("/users", json={
        "username": "test",
        "email": email,
        "password": "testpass123"
    })
    assert response.status_code == expected_status


@pytest.mark.parametrize("password,should_pass", [
    ("short", False),
    ("longenoughpassword", True),
    ("NoNumbers!", False),
    ("HasNumbers123", True),
])
def test_password_validation(client, password, should_pass):
    response = client.post("/users", json={
        "username": "test",
        "email": "test@example.com",
        "password": password
    })
    if should_pass:
        assert response.status_code == 201
    else:
        assert response.status_code == 422
```

### Mocking Dependencies

```python
from fastapi import FastAPI, Depends
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import pytest

app = FastAPI()

# Service to mock
class EmailService:
    async def send_email(self, to: str, subject: str, body: str) -> bool:
        # Real implementation sends email
        return True

class PaymentService:
    async def charge(self, amount: float, card_token: str) -> dict:
        # Real implementation charges card
        return {"transaction_id": "real_txn_123"}

def get_email_service() -> EmailService:
    return EmailService()

def get_payment_service() -> PaymentService:
    return PaymentService()

@app.post("/register")
async def register(
    email: str,
    email_service: EmailService = Depends(get_email_service)
):
    # Create user logic...
    await email_service.send_email(email, "Welcome!", "Thanks for joining")
    return {"message": "User created"}

@app.post("/checkout")
async def checkout(
    amount: float,
    card_token: str,
    payment_service: PaymentService = Depends(get_payment_service)
):
    result = await payment_service.charge(amount, card_token)
    return {"transaction_id": result["transaction_id"]}


# Test with dependency override
def test_register_with_mock_email():
    mock_email_service = Mock(spec=EmailService)
    mock_email_service.send_email = AsyncMock(return_value=True)

    app.dependency_overrides[get_email_service] = lambda: mock_email_service

    client = TestClient(app)
    response = client.post("/register", params={"email": "test@example.com"})

    assert response.status_code == 200
    mock_email_service.send_email.assert_called_once_with(
        "test@example.com",
        "Welcome!",
        "Thanks for joining"
    )

    app.dependency_overrides.clear()


# Fixture for mocking
@pytest.fixture
def mock_payment_service():
    mock = Mock(spec=PaymentService)
    mock.charge = AsyncMock(return_value={"transaction_id": "mock_txn_123"})
    app.dependency_overrides[get_payment_service] = lambda: mock
    yield mock
    app.dependency_overrides.clear()

def test_checkout_success(mock_payment_service):
    client = TestClient(app)
    response = client.post(
        "/checkout",
        params={"amount": 99.99, "card_token": "tok_123"}
    )

    assert response.status_code == 200
    assert response.json()["transaction_id"] == "mock_txn_123"
    mock_payment_service.charge.assert_called_once_with(99.99, "tok_123")


def test_checkout_failure(mock_payment_service):
    mock_payment_service.charge = AsyncMock(side_effect=Exception("Payment failed"))

    client = TestClient(app)
    response = client.post(
        "/checkout",
        params={"amount": 99.99, "card_token": "tok_invalid"}
    )

    assert response.status_code == 500


# Mocking with patch decorator
@patch("app.services.external_api.fetch_data")
def test_with_patch(mock_fetch):
    mock_fetch.return_value = {"data": "mocked"}

    client = TestClient(app)
    response = client.get("/external-data")

    assert response.json()["data"] == "mocked"


# Context manager mocking
def test_with_context_manager():
    with patch("app.services.EmailService") as MockEmailService:
        mock_instance = MockEmailService.return_value
        mock_instance.send_email = AsyncMock(return_value=True)

        client = TestClient(app)
        response = client.post("/register", params={"email": "test@example.com"})

        assert response.status_code == 200


# Mocking database
@pytest.fixture
def mock_db():
    mock = MagicMock()
    mock.query.return_value.filter.return_value.first.return_value = {
        "id": 1,
        "name": "Test User"
    }
    return mock

def test_get_user_with_mock_db(mock_db):
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)
    response = client.get("/users/1")

    assert response.status_code == 200
    app.dependency_overrides.clear()
```

### Testing Async Endpoints

```python
import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
import asyncio

app = FastAPI()

@app.get("/async-data")
async def get_async_data():
    await asyncio.sleep(0.1)  # Simulate async operation
    return {"data": "async result"}

@app.post("/async-process")
async def async_process(data: dict):
    result = await process_data(data)
    return {"processed": result}


# Using pytest-asyncio
@pytest.mark.asyncio
async def test_async_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/async-data")
        assert response.status_code == 200
        assert response.json()["data"] == "async result"


@pytest.mark.asyncio
async def test_async_post():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/async-process",
            json={"input": "test"}
        )
        assert response.status_code == 200


# Fixture for async client
@pytest.fixture
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_with_async_client_fixture(async_client):
    response = await async_client.get("/async-data")
    assert response.status_code == 200


# Testing concurrent requests
@pytest.mark.asyncio
async def test_concurrent_requests():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Make multiple concurrent requests
        tasks = [
            client.get("/async-data")
            for _ in range(10)
        ]
        responses = await asyncio.gather(*tasks)

        for response in responses:
            assert response.status_code == 200


# Testing WebSocket
@pytest.mark.asyncio
async def test_websocket():
    from starlette.testclient import TestClient

    with TestClient(app) as client:
        with client.websocket_connect("/ws") as websocket:
            websocket.send_json({"message": "hello"})
            data = websocket.receive_json()
            assert data["message"] == "hello"


# Mocking async dependencies
@pytest.fixture
async def mock_async_service():
    mock = AsyncMock()
    mock.fetch_data.return_value = {"mocked": True}
    app.dependency_overrides[get_async_service] = lambda: mock
    yield mock
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_with_async_mock(async_client, mock_async_service):
    response = await async_client.get("/data")
    assert response.status_code == 200
    mock_async_service.fetch_data.assert_called_once()
```

### Database Testing Strategies

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, get_db
from app.models import User, Item

# In-memory SQLite for testing
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture(scope="function")
def test_db():
    """Create a fresh database for each test"""
    engine = create_engine(
        SQLALCHEMY_TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Create tables
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(test_db):
    """TestClient with test database"""
    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# Test with seeded data
@pytest.fixture
def seeded_db(test_db):
    """Database with initial data"""
    users = [
        User(username="user1", email="user1@example.com"),
        User(username="user2", email="user2@example.com"),
    ]
    test_db.add_all(users)
    test_db.commit()

    items = [
        Item(name="Item 1", price=10.0, owner_id=users[0].id),
        Item(name="Item 2", price=20.0, owner_id=users[0].id),
    ]
    test_db.add_all(items)
    test_db.commit()

    return test_db


def test_list_users(client, seeded_db):
    response = client.get("/users")
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_user_items(client, seeded_db):
    response = client.get("/users/1/items")
    assert response.status_code == 200
    assert len(response.json()) == 2


# Transaction rollback pattern
@pytest.fixture(scope="function")
def db_session(db_engine):
    """Each test runs in a transaction that rolls back"""
    connection = db_engine.connect()
    transaction = connection.begin()

    Session = sessionmaker(bind=connection)
    session = Session()

    # Nested transaction for savepoint support
    session.begin_nested()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


# Factory fixtures
@pytest.fixture
def user_factory(test_db):
    """Factory for creating test users"""
    def create_user(
        username: str = "testuser",
        email: str = None,
        **kwargs
    ) -> User:
        email = email or f"{username}@example.com"
        user = User(username=username, email=email, **kwargs)
        test_db.add(user)
        test_db.commit()
        test_db.refresh(user)
        return user
    return create_user


def test_with_factory(client, user_factory):
    user = user_factory(username="john", email="john@example.com")
    response = client.get(f"/users/{user.id}")
    assert response.status_code == 200
    assert response.json()["username"] == "john"


# Testing with factory_boy
from factory import Factory, Faker, SubFactory
from factory.alchemy import SQLAlchemyModelFactory

class UserFactory(SQLAlchemyModelFactory):
    class Meta:
        model = User
        sqlalchemy_session_persistence = "commit"

    username = Faker("user_name")
    email = Faker("email")

class ItemFactory(SQLAlchemyModelFactory):
    class Meta:
        model = Item
        sqlalchemy_session_persistence = "commit"

    name = Faker("word")
    price = Faker("pyfloat", min_value=1, max_value=1000)
    owner = SubFactory(UserFactory)


@pytest.fixture
def user_factory_boy(test_db):
    UserFactory._meta.sqlalchemy_session = test_db
    return UserFactory

def test_with_factory_boy(client, user_factory_boy):
    user = user_factory_boy()
    response = client.get(f"/users/{user.id}")
    assert response.status_code == 200
```

### Fixtures and Factories

```python
import pytest
from datetime import datetime, timedelta
from typing import Generator
from fastapi.testclient import TestClient
from app.main import app
from app.auth import create_access_token

# Scope levels: function (default), class, module, session

# Session-scoped fixture (created once per test session)
@pytest.fixture(scope="session")
def base_url() -> str:
    return "http://test"


# Module-scoped fixture (created once per test module)
@pytest.fixture(scope="module")
def shared_config() -> dict:
    return {
        "timeout": 30,
        "retries": 3
    }


# Function-scoped fixture (created for each test)
@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c


# Fixture with cleanup
@pytest.fixture
def temp_file():
    import tempfile
    import os

    fd, path = tempfile.mkstemp()
    yield path
    os.close(fd)
    os.unlink(path)


# Fixture depending on other fixtures
@pytest.fixture
def authenticated_client(client, auth_token):
    client.headers["Authorization"] = f"Bearer {auth_token}"
    return client


@pytest.fixture
def auth_token() -> str:
    return create_access_token(
        data={"sub": "testuser"},
        expires_delta=timedelta(hours=1)
    )


# Fixture with parameters
@pytest.fixture(params=["admin", "user", "guest"])
def user_role(request) -> str:
    return request.param

def test_role_permissions(client, user_role):
    # Test runs 3 times with different roles
    response = client.get(f"/check-role/{user_role}")
    assert response.status_code == 200


# Factory fixture pattern
@pytest.fixture
def make_user():
    """Returns a factory function"""
    created_users = []

    def _make_user(
        username: str = "testuser",
        email: str = None,
        role: str = "user"
    ) -> dict:
        user = {
            "id": len(created_users) + 1,
            "username": username,
            "email": email or f"{username}@example.com",
            "role": role,
            "created_at": datetime.utcnow().isoformat()
        }
        created_users.append(user)
        return user

    yield _make_user

    # Cleanup
    created_users.clear()


def test_with_factory(make_user):
    user1 = make_user(username="alice")
    user2 = make_user(username="bob", role="admin")

    assert user1["id"] == 1
    assert user2["id"] == 2
    assert user2["role"] == "admin"


# Complex factory with dependencies
@pytest.fixture
def order_factory(make_user, db_session):
    def _make_order(
        user: dict = None,
        items: list = None,
        status: str = "pending"
    ) -> dict:
        if user is None:
            user = make_user()

        order = {
            "id": 1,
            "user_id": user["id"],
            "items": items or [{"name": "Item 1", "price": 10.0}],
            "status": status,
            "total": sum(item["price"] for item in (items or [{"price": 10.0}]))
        }
        return order

    return _make_order


# Reusable assertion helpers
@pytest.fixture
def assert_valid_user_response():
    def _assert(response):
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "username" in data
        assert "email" in data
        assert "password" not in data  # Should not expose password
        return data
    return _assert

def test_get_user(client, make_user, assert_valid_user_response):
    user = make_user()
    response = client.get(f"/users/{user['id']}")
    data = assert_valid_user_response(response)
    assert data["username"] == user["username"]


# Combining fixtures
@pytest.fixture
def test_scenario(client, make_user, order_factory):
    """Complete test scenario with user and orders"""
    user = make_user(username="customer", role="user")
    orders = [
        order_factory(user=user, status="completed"),
        order_factory(user=user, status="pending")
    ]
    return {
        "client": client,
        "user": user,
        "orders": orders
    }

def test_user_orders(test_scenario):
    scenario = test_scenario
    response = scenario["client"].get(
        f"/users/{scenario['user']['id']}/orders"
    )
    assert response.status_code == 200
```

---

## 5.2 Integration Testing

### Testing with Real Databases

```python
import pytest
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, get_db

# PostgreSQL container for integration tests
@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("postgres:15") as postgres:
        yield postgres


@pytest.fixture(scope="session")
def postgres_engine(postgres_container):
    engine = create_engine(postgres_container.get_connection_url())
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def postgres_session(postgres_engine):
    connection = postgres_engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def integration_client(postgres_session):
    def override_get_db():
        yield postgres_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


# Redis container
@pytest.fixture(scope="session")
def redis_container():
    with RedisContainer("redis:7") as redis:
        yield redis


@pytest.fixture(scope="function")
def redis_client(redis_container):
    import redis as redis_lib
    client = redis_lib.from_url(redis_container.get_connection_url())
    yield client
    client.flushall()


# Integration test with real database
def test_user_workflow(integration_client, postgres_session):
    # Create user
    response = integration_client.post("/users", json={
        "username": "testuser",
        "email": "test@example.com",
        "password": "securepass123"
    })
    assert response.status_code == 201
    user_id = response.json()["id"]

    # Verify in database
    from app.models import User
    db_user = postgres_session.query(User).filter(User.id == user_id).first()
    assert db_user is not None
    assert db_user.username == "testuser"

    # Update user
    response = integration_client.put(f"/users/{user_id}", json={
        "username": "updateduser"
    })
    assert response.status_code == 200

    # Verify update in database
    postgres_session.refresh(db_user)
    assert db_user.username == "updateduser"

    # Delete user
    response = integration_client.delete(f"/users/{user_id}")
    assert response.status_code == 204

    # Verify deletion
    db_user = postgres_session.query(User).filter(User.id == user_id).first()
    assert db_user is None


# Test with Redis caching
def test_caching(integration_client, redis_client):
    # First request - cache miss
    response = integration_client.get("/cached-data/key1")
    assert response.status_code == 200
    assert response.headers.get("X-Cache") == "MISS"

    # Second request - cache hit
    response = integration_client.get("/cached-data/key1")
    assert response.status_code == 200
    assert response.headers.get("X-Cache") == "HIT"

    # Verify in Redis
    cached = redis_client.get("cached-data:key1")
    assert cached is not None


# Test database constraints
def test_unique_constraint(integration_client):
    # Create user
    integration_client.post("/users", json={
        "username": "unique",
        "email": "unique@example.com",
        "password": "pass123"
    })

    # Try to create duplicate
    response = integration_client.post("/users", json={
        "username": "unique",
        "email": "unique@example.com",
        "password": "pass123"
    })
    assert response.status_code == 409


# Test foreign key relationships
def test_relationships(integration_client, postgres_session):
    # Create user
    user_response = integration_client.post("/users", json={
        "username": "owner",
        "email": "owner@example.com",
        "password": "pass123"
    })
    user_id = user_response.json()["id"]

    # Create items for user
    for i in range(3):
        integration_client.post("/items", json={
            "name": f"Item {i}",
            "price": 10.0 * i,
            "owner_id": user_id
        })

    # Get user with items
    response = integration_client.get(f"/users/{user_id}/items")
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 3

    # Delete user (should cascade delete items or fail based on constraint)
    response = integration_client.delete(f"/users/{user_id}")
    # Assert based on your cascade rules
```

### Test Containers

```python
import pytest
from testcontainers.postgres import PostgresContainer
from testcontainers.mongodb import MongoDbContainer
from testcontainers.redis import RedisContainer
from testcontainers.elasticsearch import ElasticsearchContainer
from testcontainers.rabbitmq import RabbitMqContainer
from testcontainers.localstack import LocalStackContainer
from testcontainers.core.waiting_utils import wait_for_logs

# Multiple containers for complex integration tests
@pytest.fixture(scope="session")
def containers():
    """Start all required containers"""
    postgres = PostgresContainer("postgres:15")
    redis = RedisContainer("redis:7")
    mongo = MongoDbContainer("mongo:6")

    # Start containers
    postgres.start()
    redis.start()
    mongo.start()

    yield {
        "postgres": postgres,
        "redis": redis,
        "mongo": mongo
    }

    # Cleanup
    postgres.stop()
    redis.stop()
    mongo.stop()


@pytest.fixture(scope="session")
def elasticsearch_container():
    with ElasticsearchContainer("elasticsearch:8.8.0") as es:
        # Wait for Elasticsearch to be ready
        wait_for_logs(es, "started")
        yield es


@pytest.fixture(scope="session")
def rabbitmq_container():
    with RabbitMqContainer("rabbitmq:3-management") as rabbitmq:
        yield rabbitmq


# LocalStack for AWS services
@pytest.fixture(scope="session")
def localstack_container():
    with LocalStackContainer("localstack/localstack:latest") as localstack:
        localstack.with_services("s3", "sqs", "dynamodb")
        yield localstack


@pytest.fixture
def s3_client(localstack_container):
    import boto3
    client = boto3.client(
        "s3",
        endpoint_url=localstack_container.get_url(),
        aws_access_key_id="test",
        aws_secret_access_key="test",
        region_name="us-east-1"
    )
    # Create test bucket
    client.create_bucket(Bucket="test-bucket")
    yield client


def test_s3_upload(integration_client, s3_client):
    # Upload file through API
    response = integration_client.post(
        "/upload",
        files={"file": ("test.txt", b"Hello World", "text/plain")}
    )
    assert response.status_code == 200

    # Verify in S3
    obj = s3_client.get_object(Bucket="test-bucket", Key="test.txt")
    assert obj["Body"].read() == b"Hello World"


# Custom container with wait strategy
from testcontainers.core.container import DockerContainer
from testcontainers.core.waiting_utils import wait_container_is_ready

class CustomServiceContainer(DockerContainer):
    def __init__(self):
        super().__init__("mycompany/custom-service:latest")
        self.with_exposed_ports(8080)
        self.with_env("ENV", "test")

    @wait_container_is_ready()
    def _connect(self):
        import requests
        url = f"http://{self.get_container_host_ip()}:{self.get_exposed_port(8080)}/health"
        response = requests.get(url)
        if response.status_code != 200:
            raise Exception("Service not ready")

    def start(self):
        super().start()
        self._connect()
        return self

    def get_connection_url(self) -> str:
        host = self.get_container_host_ip()
        port = self.get_exposed_port(8080)
        return f"http://{host}:{port}"


@pytest.fixture(scope="session")
def custom_service():
    with CustomServiceContainer() as container:
        yield container
```

### API Contract Testing

```python
import pytest
from pydantic import BaseModel, ValidationError
from typing import List, Optional
from fastapi.testclient import TestClient
from app.main import app

# Define API contracts
class UserContract(BaseModel):
    id: int
    username: str
    email: str
    created_at: str

class UserListContract(BaseModel):
    users: List[UserContract]
    total: int
    page: int
    per_page: int

class ErrorContract(BaseModel):
    error: str
    message: str
    details: Optional[dict] = None


# Contract tests
client = TestClient(app)

def test_get_user_contract():
    """Test that GET /users/{id} returns valid UserContract"""
    response = client.get("/users/1")

    if response.status_code == 200:
        try:
            user = UserContract(**response.json())
            assert user.id == 1
        except ValidationError as e:
            pytest.fail(f"Response does not match UserContract: {e}")
    elif response.status_code == 404:
        try:
            error = ErrorContract(**response.json())
            assert error.error is not None
        except ValidationError as e:
            pytest.fail(f"Error response does not match ErrorContract: {e}")


def test_list_users_contract():
    """Test that GET /users returns valid UserListContract"""
    response = client.get("/users")
    assert response.status_code == 200

    try:
        data = UserListContract(**response.json())
        assert data.total >= 0
        assert data.page >= 1
        for user in data.users:
            assert isinstance(user.id, int)
            assert isinstance(user.username, str)
    except ValidationError as e:
        pytest.fail(f"Response does not match UserListContract: {e}")


# Schema validation with schemathesis
# pip install schemathesis
import schemathesis

# Generate tests from OpenAPI schema
schema = schemathesis.from_uri("http://localhost:8000/openapi.json")

@schema.parametrize()
def test_api_schema(case):
    """Test all endpoints against OpenAPI schema"""
    response = case.call()
    case.validate_response(response)


# Stateful testing
@schema.parametrize(method="POST")
def test_create_then_read(case):
    """Test create operations and verify the resource can be read"""
    if case.path == "/users":
        # Create
        create_response = case.call()
        if create_response.status_code == 201:
            user_id = create_response.json()["id"]

            # Read back
            read_response = client.get(f"/users/{user_id}")
            assert read_response.status_code == 200


# Pact contract testing (consumer-driven)
# pip install pact-python
from pact import Consumer, Provider

@pytest.fixture(scope="session")
def pact():
    pact = Consumer("UserService").has_pact_with(
        Provider("AuthService"),
        pact_dir="./pacts"
    )
    pact.start_service()
    yield pact
    pact.stop_service()


def test_auth_service_contract(pact):
    expected = {
        "user_id": 1,
        "token": "abc123",
        "expires_in": 3600
    }

    (pact
        .given("a user exists with id 1")
        .upon_receiving("a request to authenticate")
        .with_request("POST", "/auth/token", body={"username": "test", "password": "pass"})
        .will_respond_with(200, body=expected))

    with pact:
        # Make actual request to pact mock server
        response = client.post(
            f"{pact.uri}/auth/token",
            json={"username": "test", "password": "pass"}
        )
        assert response.status_code == 200
        assert response.json() == expected
```

### End-to-End Test Patterns

```python
import pytest
from fastapi.testclient import TestClient
from app.main import app
import time

client = TestClient(app)


class TestUserJourney:
    """End-to-end test for complete user journey"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup before each test method"""
        self.user_data = {
            "username": f"e2euser_{int(time.time())}",
            "email": f"e2e_{int(time.time())}@example.com",
            "password": "SecurePass123!"
        }
        self.user_id = None
        self.auth_token = None
        yield
        # Cleanup
        if self.user_id and self.auth_token:
            client.delete(
                f"/users/{self.user_id}",
                headers={"Authorization": f"Bearer {self.auth_token}"}
            )

    def test_complete_user_journey(self):
        # Step 1: Register
        response = client.post("/auth/register", json=self.user_data)
        assert response.status_code == 201, f"Registration failed: {response.json()}"
        self.user_id = response.json()["id"]

        # Step 2: Login
        response = client.post("/auth/login", data={
            "username": self.user_data["email"],
            "password": self.user_data["password"]
        })
        assert response.status_code == 200, f"Login failed: {response.json()}"
        self.auth_token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {self.auth_token}"}

        # Step 3: Get profile
        response = client.get("/users/me", headers=headers)
        assert response.status_code == 200
        assert response.json()["email"] == self.user_data["email"]

        # Step 4: Update profile
        response = client.put(
            f"/users/{self.user_id}",
            json={"bio": "Hello, I'm an E2E test user"},
            headers=headers
        )
        assert response.status_code == 200

        # Step 5: Create item
        response = client.post(
            "/items",
            json={"name": "E2E Test Item", "price": 99.99},
            headers=headers
        )
        assert response.status_code == 201
        item_id = response.json()["id"]

        # Step 6: Get item
        response = client.get(f"/items/{item_id}")
        assert response.status_code == 200
        assert response.json()["name"] == "E2E Test Item"

        # Step 7: Delete item
        response = client.delete(f"/items/{item_id}", headers=headers)
        assert response.status_code == 204

        # Step 8: Verify item deleted
        response = client.get(f"/items/{item_id}")
        assert response.status_code == 404


class TestOrderWorkflow:
    """E2E test for order workflow"""

    def test_order_placement_and_fulfillment(self, integration_client, seeded_db):
        # Login
        login_response = integration_client.post("/auth/login", data={
            "username": "testuser@example.com",
            "password": "testpass"
        })
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Browse items
        items_response = integration_client.get("/items")
        items = items_response.json()["items"]
        assert len(items) > 0

        # Add to cart
        cart_response = integration_client.post(
            "/cart/items",
            json={"item_id": items[0]["id"], "quantity": 2},
            headers=headers
        )
        assert cart_response.status_code == 200

        # Checkout
        order_response = integration_client.post(
            "/orders",
            json={
                "shipping_address": {
                    "street": "123 Test St",
                    "city": "Test City",
                    "zip": "12345"
                },
                "payment_method": "card"
            },
            headers=headers
        )
        assert order_response.status_code == 201
        order_id = order_response.json()["id"]
        assert order_response.json()["status"] == "pending"

        # Simulate payment webhook
        integration_client.post(
            "/webhooks/payment",
            json={
                "order_id": order_id,
                "status": "paid",
                "transaction_id": "txn_123"
            }
        )

        # Check order status
        order = integration_client.get(f"/orders/{order_id}", headers=headers)
        assert order.json()["status"] == "paid"

        # Admin fulfills order
        admin_token = get_admin_token(integration_client)
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        fulfill_response = integration_client.post(
            f"/admin/orders/{order_id}/fulfill",
            json={"tracking_number": "TRACK123"},
            headers=admin_headers
        )
        assert fulfill_response.status_code == 200

        # Customer checks order
        final_order = integration_client.get(f"/orders/{order_id}", headers=headers)
        assert final_order.json()["status"] == "shipped"
        assert final_order.json()["tracking_number"] == "TRACK123"
```

---

## 5.3 Test Organization

### Test Structure and Conventions

```
tests/
├── conftest.py              # Shared fixtures
├── __init__.py
│
├── unit/                    # Unit tests
│   ├── __init__.py
│   ├── conftest.py          # Unit test specific fixtures
│   ├── test_models.py
│   ├── test_services.py
│   ├── test_utils.py
│   └── test_validators.py
│
├── integration/             # Integration tests
│   ├── __init__.py
│   ├── conftest.py          # Integration fixtures (containers)
│   ├── test_api_users.py
│   ├── test_api_items.py
│   ├── test_api_orders.py
│   └── test_database.py
│
├── e2e/                     # End-to-end tests
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_user_journey.py
│   └── test_order_workflow.py
│
├── fixtures/                # Test data
│   ├── users.json
│   ├── items.json
│   └── orders.json
│
└── utils/                   # Test utilities
    ├── __init__.py
    ├── factories.py
    ├── assertions.py
    └── helpers.py
```

```python
# tests/conftest.py - Root conftest
import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture(scope="session")
def app_instance():
    return app

@pytest.fixture
def client(app_instance):
    with TestClient(app_instance) as c:
        yield c


# tests/unit/conftest.py - Unit test fixtures
import pytest
from unittest.mock import Mock

@pytest.fixture
def mock_db():
    return Mock()

@pytest.fixture
def mock_email_service():
    return Mock()


# tests/integration/conftest.py - Integration fixtures
import pytest
from testcontainers.postgres import PostgresContainer

@pytest.fixture(scope="session")
def postgres():
    with PostgresContainer("postgres:15") as container:
        yield container


# Test file naming conventions
# test_<module>_<functionality>.py
# test_users_crud.py
# test_orders_workflow.py
# test_auth_jwt.py

# Test function naming
# test_<action>_<scenario>_<expected_result>
def test_create_user_with_valid_data_returns_201():
    pass

def test_create_user_with_duplicate_email_returns_409():
    pass

def test_get_user_when_not_found_returns_404():
    pass


# Test class organization
class TestUserCRUD:
    """Group related tests"""

    class TestCreate:
        def test_with_valid_data(self):
            pass

        def test_with_invalid_email(self):
            pass

        def test_with_duplicate_username(self):
            pass

    class TestRead:
        def test_existing_user(self):
            pass

        def test_nonexistent_user(self):
            pass

    class TestUpdate:
        def test_own_profile(self):
            pass

        def test_other_user_forbidden(self):
            pass

    class TestDelete:
        def test_soft_delete(self):
            pass

        def test_cascade_items(self):
            pass
```

### Coverage Strategies

```python
# pytest.ini or pyproject.toml
"""
[tool.pytest.ini_options]
minversion = "7.0"
addopts = [
    "-ra",
    "-q",
    "--strict-markers",
    "--cov=app",
    "--cov-report=term-missing",
    "--cov-report=html",
    "--cov-fail-under=80"
]
testpaths = ["tests"]
markers = [
    "unit: Unit tests",
    "integration: Integration tests",
    "e2e: End-to-end tests",
    "slow: Slow tests"
]

[tool.coverage.run]
branch = true
source = ["app"]
omit = [
    "app/migrations/*",
    "app/tests/*",
    "app/__init__.py"
]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
    "if TYPE_CHECKING:",
    "if __name__ == .__main__.:"
]
"""

# Run specific test categories
# pytest -m unit
# pytest -m integration
# pytest -m "not slow"

# Coverage commands
# pytest --cov=app --cov-report=html
# pytest --cov=app --cov-branch --cov-report=term-missing

# Exclude from coverage
def function_not_tested():  # pragma: no cover
    pass


# Coverage per module
"""
# .coveragerc
[run]
source = app

[report]
show_missing = true
precision = 2

[html]
directory = coverage_html
"""


# tests/utils/coverage_helpers.py
import subprocess
import json

def run_coverage_check():
    """Run coverage and return results"""
    result = subprocess.run(
        ["pytest", "--cov=app", "--cov-report=json"],
        capture_output=True
    )

    with open("coverage.json") as f:
        coverage_data = json.load(f)

    return {
        "total": coverage_data["totals"]["percent_covered"],
        "files": {
            name: data["summary"]["percent_covered"]
            for name, data in coverage_data["files"].items()
        }
    }


def check_coverage_threshold(threshold: float = 80.0):
    """Fail if coverage below threshold"""
    coverage = run_coverage_check()
    if coverage["total"] < threshold:
        raise AssertionError(
            f"Coverage {coverage['total']:.2f}% below threshold {threshold}%"
        )

    # Check individual files
    low_coverage = {
        name: pct for name, pct in coverage["files"].items()
        if pct < threshold
    }
    if low_coverage:
        print(f"Files below threshold: {low_coverage}")
```

### Performance Testing Basics

```python
import pytest
import time
from fastapi.testclient import TestClient
from app.main import app
import statistics
import asyncio
from concurrent.futures import ThreadPoolExecutor

client = TestClient(app)


# Simple performance test
def test_endpoint_response_time():
    """Ensure endpoint responds within acceptable time"""
    start = time.perf_counter()
    response = client.get("/users")
    duration = time.perf_counter() - start

    assert response.status_code == 200
    assert duration < 0.5, f"Response took {duration:.2f}s, expected < 0.5s"


# Statistical performance test
def test_endpoint_performance_stats():
    """Measure endpoint performance statistics"""
    durations = []

    for _ in range(100):
        start = time.perf_counter()
        response = client.get("/users/1")
        durations.append(time.perf_counter() - start)

        assert response.status_code in [200, 404]

    stats = {
        "min": min(durations),
        "max": max(durations),
        "mean": statistics.mean(durations),
        "median": statistics.median(durations),
        "stdev": statistics.stdev(durations),
        "p95": sorted(durations)[int(len(durations) * 0.95)],
        "p99": sorted(durations)[int(len(durations) * 0.99)]
    }

    print(f"\nPerformance stats: {stats}")

    # Assertions
    assert stats["p95"] < 0.2, f"P95 latency {stats['p95']:.3f}s exceeds 200ms"
    assert stats["mean"] < 0.1, f"Mean latency {stats['mean']:.3f}s exceeds 100ms"


# Concurrent request test
def test_concurrent_requests():
    """Test endpoint under concurrent load"""
    num_requests = 50
    results = []

    def make_request():
        start = time.perf_counter()
        response = client.get("/items")
        duration = time.perf_counter() - start
        return {
            "status": response.status_code,
            "duration": duration
        }

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(make_request) for _ in range(num_requests)]
        results = [f.result() for f in futures]

    # Analyze results
    success_count = sum(1 for r in results if r["status"] == 200)
    error_count = num_requests - success_count
    durations = [r["duration"] for r in results]

    assert success_count == num_requests, f"{error_count} requests failed"
    assert max(durations) < 2.0, "Some requests took too long"


# Async performance test
@pytest.mark.asyncio
async def test_async_performance():
    """Test async endpoint performance"""
    from httpx import AsyncClient, ASGITransport

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        tasks = []
        for _ in range(100):
            tasks.append(client.get("/async-endpoint"))

        start = time.perf_counter()
        responses = await asyncio.gather(*tasks)
        total_time = time.perf_counter() - start

    success = sum(1 for r in responses if r.status_code == 200)
    throughput = len(responses) / total_time

    print(f"\nThroughput: {throughput:.2f} req/s")
    assert success == 100
    assert throughput > 50, f"Throughput {throughput:.2f} below 50 req/s"


# Memory usage test
def test_memory_usage():
    """Test endpoint doesn't leak memory"""
    import tracemalloc

    tracemalloc.start()
    initial = tracemalloc.get_traced_memory()[0]

    for _ in range(1000):
        client.get("/users")

    final = tracemalloc.get_traced_memory()[0]
    tracemalloc.stop()

    memory_increase = (final - initial) / 1024 / 1024  # MB
    print(f"\nMemory increase: {memory_increase:.2f} MB")

    assert memory_increase < 50, f"Memory increased by {memory_increase:.2f} MB"


# pytest-benchmark integration
def test_endpoint_benchmark(benchmark):
    """Benchmark endpoint using pytest-benchmark"""
    result = benchmark(lambda: client.get("/users"))
    assert result.status_code == 200


# Locust load test (separate file: locustfile.py)
"""
from locust import HttpUser, task, between

class APIUser(HttpUser):
    wait_time = between(1, 3)

    @task(3)
    def list_users(self):
        self.client.get("/users")

    @task(2)
    def get_user(self):
        self.client.get("/users/1")

    @task(1)
    def create_user(self):
        self.client.post("/users", json={
            "username": "loadtest",
            "email": "load@test.com",
            "password": "testpass123"
        })

# Run: locust -f locustfile.py --host=http://localhost:8000
"""
```

### CI/CD Integration

```yaml
# .github/workflows/test.yml
name: Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-test.txt

      - name: Run unit tests
        run: pytest tests/unit -v --cov=app --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml

  integration-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
          POSTGRES_DB: testdb
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

      redis:
        image: redis:7
        ports:
          - 6379:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-test.txt

      - name: Run integration tests
        env:
          DATABASE_URL: postgresql://test:test@localhost:5432/testdb
          REDIS_URL: redis://localhost:6379
        run: pytest tests/integration -v

  e2e-tests:
    runs-on: ubuntu-latest
    needs: [unit-tests, integration-tests]
    steps:
      - uses: actions/checkout@v4

      - name: Build and start services
        run: docker-compose -f docker-compose.test.yml up -d

      - name: Wait for services
        run: |
          sleep 10
          curl --retry 10 --retry-delay 5 http://localhost:8000/health

      - name: Run E2E tests
        run: pytest tests/e2e -v

      - name: Cleanup
        if: always()
        run: docker-compose -f docker-compose.test.yml down

  performance-tests:
    runs-on: ubuntu-latest
    needs: [e2e-tests]
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4

      - name: Build and start services
        run: docker-compose up -d

      - name: Run performance tests
        run: |
          pip install locust
          locust -f tests/performance/locustfile.py \
            --headless \
            --users 100 \
            --spawn-rate 10 \
            --run-time 60s \
            --host http://localhost:8000 \
            --html report.html

      - name: Upload performance report
        uses: actions/upload-artifact@v3
        with:
          name: performance-report
          path: report.html
```

```python
# tests/conftest.py - CI-aware fixtures
import os
import pytest

def is_ci():
    return os.getenv("CI") == "true"

@pytest.fixture(scope="session")
def database_url():
    if is_ci():
        return os.getenv("DATABASE_URL")
    return "sqlite:///./test.db"

@pytest.fixture(scope="session")
def skip_slow():
    """Skip slow tests in CI unless explicitly enabled"""
    if is_ci() and not os.getenv("RUN_SLOW_TESTS"):
        pytest.skip("Skipping slow tests in CI")


# Conditional test execution
@pytest.mark.skipif(is_ci(), reason="Not run in CI")
def test_local_only():
    pass

@pytest.mark.skipif(not is_ci(), reason="Only run in CI")
def test_ci_only():
    pass
```

---

## Summary

Module 5 covered comprehensive testing strategies:

1. **Unit Testing** - TestClient usage, pytest integration, mocking dependencies, async testing, database testing, and fixtures/factories

2. **Integration Testing** - Real database testing with containers, test containers for various services, API contract testing, and E2E patterns

3. **Test Organization** - Project structure, naming conventions, coverage strategies, performance testing basics, and CI/CD integration

These testing practices ensure reliability, maintainability, and confidence in your FastAPI application.

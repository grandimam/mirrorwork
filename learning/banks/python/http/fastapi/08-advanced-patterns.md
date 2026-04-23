# Module 8: Advanced Patterns

---

## 8.1 Event-Driven Architecture

### Publishing Events from Endpoints

```python
from fastapi import FastAPI, Depends, BackgroundTasks
from pydantic import BaseModel
from datetime import datetime
from typing import Any, Dict, List, Callable
from enum import Enum
import asyncio

app = FastAPI()

# Event types
class EventType(str, Enum):
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    USER_DELETED = "user.deleted"
    ORDER_CREATED = "order.created"
    ORDER_PAID = "order.paid"
    ORDER_SHIPPED = "order.shipped"


# Event model
class Event(BaseModel):
    id: str
    type: EventType
    timestamp: datetime
    data: Dict[str, Any]
    metadata: Dict[str, Any] = {}


# Simple in-memory event bus
class EventBus:
    def __init__(self):
        self._handlers: Dict[EventType, List[Callable]] = {}
        self._queue: asyncio.Queue = asyncio.Queue()

    def subscribe(self, event_type: EventType, handler: Callable):
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    async def publish(self, event: Event):
        """Publish event to all subscribers"""
        handlers = self._handlers.get(event.type, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.error(f"Event handler error: {e}", event=event)

    async def publish_async(self, event: Event):
        """Queue event for async processing"""
        await self._queue.put(event)

    async def process_events(self):
        """Background task to process queued events"""
        while True:
            event = await self._queue.get()
            await self.publish(event)


event_bus = EventBus()


# Event handlers
async def send_welcome_email(event: Event):
    user_email = event.data.get("email")
    await email_service.send_welcome(user_email)


async def update_analytics(event: Event):
    await analytics_service.track(event.type, event.data)


async def notify_admin(event: Event):
    await slack_service.notify(f"New event: {event.type}")


# Register handlers
event_bus.subscribe(EventType.USER_CREATED, send_welcome_email)
event_bus.subscribe(EventType.USER_CREATED, update_analytics)
event_bus.subscribe(EventType.ORDER_CREATED, notify_admin)


# Publishing from endpoints
@app.post("/users")
async def create_user(
    user: UserCreate,
    background_tasks: BackgroundTasks
):
    # Create user
    db_user = await user_service.create(user)

    # Create event
    event = Event(
        id=str(uuid.uuid4()),
        type=EventType.USER_CREATED,
        timestamp=datetime.utcnow(),
        data={
            "user_id": db_user.id,
            "email": db_user.email,
            "username": db_user.username
        },
        metadata={
            "source": "api",
            "request_id": request_id_ctx.get()
        }
    )

    # Publish asynchronously
    background_tasks.add_task(event_bus.publish, event)

    return db_user


# Event publishing decorator
def publishes_event(event_type: EventType):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)

            event = Event(
                id=str(uuid.uuid4()),
                type=event_type,
                timestamp=datetime.utcnow(),
                data=result if isinstance(result, dict) else result.model_dump()
            )
            await event_bus.publish_async(event)

            return result
        return wrapper
    return decorator


@app.post("/orders")
@publishes_event(EventType.ORDER_CREATED)
async def create_order(order: OrderCreate):
    return await order_service.create(order)
```

### Message Broker Integration (RabbitMQ, Kafka)

```python
# RabbitMQ with aio-pika
import aio_pika
from aio_pika import Message, ExchangeType
import json

class RabbitMQPublisher:
    def __init__(self, url: str):
        self.url = url
        self.connection = None
        self.channel = None
        self.exchange = None

    async def connect(self):
        self.connection = await aio_pika.connect_robust(self.url)
        self.channel = await self.connection.channel()
        self.exchange = await self.channel.declare_exchange(
            "events",
            ExchangeType.TOPIC,
            durable=True
        )

    async def publish(self, routing_key: str, message: dict):
        await self.exchange.publish(
            Message(
                body=json.dumps(message).encode(),
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT
            ),
            routing_key=routing_key
        )

    async def close(self):
        if self.connection:
            await self.connection.close()


class RabbitMQConsumer:
    def __init__(self, url: str):
        self.url = url
        self.connection = None
        self.channel = None

    async def connect(self):
        self.connection = await aio_pika.connect_robust(self.url)
        self.channel = await self.connection.channel()
        await self.channel.set_qos(prefetch_count=10)

    async def consume(self, queue_name: str, routing_keys: List[str], handler: Callable):
        exchange = await self.channel.declare_exchange(
            "events", ExchangeType.TOPIC, durable=True
        )
        queue = await self.channel.declare_queue(queue_name, durable=True)

        for key in routing_keys:
            await queue.bind(exchange, routing_key=key)

        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    data = json.loads(message.body)
                    await handler(data)


# Kafka with aiokafka
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer

class KafkaPublisher:
    def __init__(self, bootstrap_servers: str):
        self.bootstrap_servers = bootstrap_servers
        self.producer = None

    async def start(self):
        self.producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode()
        )
        await self.producer.start()

    async def publish(self, topic: str, key: str, value: dict):
        await self.producer.send_and_wait(
            topic,
            key=key.encode(),
            value=value
        )

    async def stop(self):
        if self.producer:
            await self.producer.stop()


class KafkaConsumer:
    def __init__(self, bootstrap_servers: str, group_id: str):
        self.bootstrap_servers = bootstrap_servers
        self.group_id = group_id
        self.consumer = None

    async def start(self, topics: List[str]):
        self.consumer = AIOKafkaConsumer(
            *topics,
            bootstrap_servers=self.bootstrap_servers,
            group_id=self.group_id,
            value_deserializer=lambda v: json.loads(v.decode())
        )
        await self.consumer.start()

    async def consume(self, handler: Callable):
        async for message in self.consumer:
            await handler(message.value)

    async def stop(self):
        if self.consumer:
            await self.consumer.stop()


# FastAPI integration
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    app.state.kafka_publisher = KafkaPublisher(settings.kafka_bootstrap_servers)
    await app.state.kafka_publisher.start()

    # Start consumer in background
    consumer = KafkaConsumer(
        settings.kafka_bootstrap_servers,
        "my-service-group"
    )
    await consumer.start(["events"])
    asyncio.create_task(consumer.consume(handle_event))

    yield

    # Shutdown
    await app.state.kafka_publisher.stop()
    await consumer.stop()

app = FastAPI(lifespan=lifespan)


@app.post("/events")
async def publish_event(event: EventCreate, request: Request):
    await request.app.state.kafka_publisher.publish(
        topic="events",
        key=event.type,
        value=event.model_dump()
    )
    return {"status": "published"}
```

### Event Sourcing Basics

```python
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional, Type
from abc import ABC, abstractmethod
import json

# Base event
class DomainEvent(BaseModel):
    event_id: str
    aggregate_id: str
    aggregate_type: str
    event_type: str
    timestamp: datetime
    version: int
    data: dict


# Event store interface
class EventStore(ABC):
    @abstractmethod
    async def append(self, events: List[DomainEvent]) -> None:
        pass

    @abstractmethod
    async def get_events(
        self,
        aggregate_id: str,
        after_version: int = 0
    ) -> List[DomainEvent]:
        pass


# PostgreSQL event store
class PostgresEventStore(EventStore):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def append(self, events: List[DomainEvent]) -> None:
        for event in events:
            await self.db.execute(
                text("""
                    INSERT INTO events (
                        event_id, aggregate_id, aggregate_type,
                        event_type, timestamp, version, data
                    ) VALUES (
                        :event_id, :aggregate_id, :aggregate_type,
                        :event_type, :timestamp, :version, :data
                    )
                """),
                {
                    "event_id": event.event_id,
                    "aggregate_id": event.aggregate_id,
                    "aggregate_type": event.aggregate_type,
                    "event_type": event.event_type,
                    "timestamp": event.timestamp,
                    "version": event.version,
                    "data": json.dumps(event.data)
                }
            )
        await self.db.commit()

    async def get_events(
        self,
        aggregate_id: str,
        after_version: int = 0
    ) -> List[DomainEvent]:
        result = await self.db.execute(
            text("""
                SELECT * FROM events
                WHERE aggregate_id = :aggregate_id
                AND version > :after_version
                ORDER BY version ASC
            """),
            {"aggregate_id": aggregate_id, "after_version": after_version}
        )
        return [DomainEvent(**row) for row in result]


# Aggregate base
class Aggregate(ABC):
    def __init__(self, aggregate_id: str):
        self.aggregate_id = aggregate_id
        self.version = 0
        self._pending_events: List[DomainEvent] = []

    def apply_event(self, event: DomainEvent):
        handler_name = f"_apply_{event.event_type}"
        handler = getattr(self, handler_name, None)
        if handler:
            handler(event)
        self.version = event.version

    def raise_event(self, event_type: str, data: dict):
        event = DomainEvent(
            event_id=str(uuid.uuid4()),
            aggregate_id=self.aggregate_id,
            aggregate_type=self.__class__.__name__,
            event_type=event_type,
            timestamp=datetime.utcnow(),
            version=self.version + 1,
            data=data
        )
        self._pending_events.append(event)
        self.apply_event(event)

    def get_pending_events(self) -> List[DomainEvent]:
        events = self._pending_events.copy()
        self._pending_events.clear()
        return events


# Order aggregate example
class Order(Aggregate):
    def __init__(self, order_id: str):
        super().__init__(order_id)
        self.status = None
        self.items = []
        self.total = 0.0

    def create(self, customer_id: str, items: List[dict]):
        self.raise_event("order_created", {
            "customer_id": customer_id,
            "items": items
        })

    def pay(self, payment_id: str):
        if self.status != "pending":
            raise ValueError("Order cannot be paid")
        self.raise_event("order_paid", {"payment_id": payment_id})

    def ship(self, tracking_number: str):
        if self.status != "paid":
            raise ValueError("Order cannot be shipped")
        self.raise_event("order_shipped", {"tracking_number": tracking_number})

    def _apply_order_created(self, event: DomainEvent):
        self.status = "pending"
        self.items = event.data["items"]
        self.total = sum(item["price"] * item["quantity"] for item in self.items)

    def _apply_order_paid(self, event: DomainEvent):
        self.status = "paid"

    def _apply_order_shipped(self, event: DomainEvent):
        self.status = "shipped"


# Repository
class OrderRepository:
    def __init__(self, event_store: EventStore):
        self.event_store = event_store

    async def get(self, order_id: str) -> Order:
        events = await self.event_store.get_events(order_id)
        if not events:
            return None

        order = Order(order_id)
        for event in events:
            order.apply_event(event)
        return order

    async def save(self, order: Order):
        events = order.get_pending_events()
        if events:
            await self.event_store.append(events)


# Usage in endpoint
@app.post("/orders")
async def create_order(
    request: OrderCreateRequest,
    repo: OrderRepository = Depends(get_order_repository)
):
    order = Order(str(uuid.uuid4()))
    order.create(request.customer_id, request.items)
    await repo.save(order)

    return {"order_id": order.aggregate_id, "status": order.status}


@app.post("/orders/{order_id}/pay")
async def pay_order(
    order_id: str,
    payment: PaymentRequest,
    repo: OrderRepository = Depends(get_order_repository)
):
    order = await repo.get(order_id)
    if not order:
        raise HTTPException(404)

    order.pay(payment.payment_id)
    await repo.save(order)

    return {"status": order.status}
```

### CQRS Patterns with FastAPI

```python
from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import Generic, TypeVar, List

# Command/Query separation
TResult = TypeVar("TResult")


class Command(ABC):
    pass


class Query(ABC, Generic[TResult]):
    pass


class CommandHandler(ABC):
    @abstractmethod
    async def handle(self, command: Command) -> None:
        pass


class QueryHandler(ABC, Generic[TResult]):
    @abstractmethod
    async def handle(self, query: Query[TResult]) -> TResult:
        pass


# Commands
class CreateOrderCommand(Command):
    customer_id: str
    items: List[dict]


class PayOrderCommand(Command):
    order_id: str
    payment_id: str


# Queries
class GetOrderQuery(Query["OrderReadModel"]):
    order_id: str


class ListCustomerOrdersQuery(Query[List["OrderReadModel"]]):
    customer_id: str
    page: int = 1
    per_page: int = 20


# Read model (optimized for queries)
class OrderReadModel(BaseModel):
    id: str
    customer_id: str
    status: str
    items: List[dict]
    total: float
    created_at: datetime


# Command handlers (write side)
class CreateOrderCommandHandler(CommandHandler):
    def __init__(self, repo: OrderRepository, event_publisher):
        self.repo = repo
        self.event_publisher = event_publisher

    async def handle(self, command: CreateOrderCommand) -> str:
        order = Order(str(uuid.uuid4()))
        order.create(command.customer_id, command.items)
        await self.repo.save(order)

        # Publish events for read model update
        for event in order.get_pending_events():
            await self.event_publisher.publish(event)

        return order.aggregate_id


# Query handlers (read side)
class GetOrderQueryHandler(QueryHandler[OrderReadModel]):
    def __init__(self, read_db: AsyncSession):
        self.db = read_db

    async def handle(self, query: GetOrderQuery) -> OrderReadModel:
        result = await self.db.execute(
            select(OrderReadModel).where(OrderReadModel.id == query.order_id)
        )
        return result.scalar_one_or_none()


# Read model projector (updates read model from events)
class OrderProjector:
    def __init__(self, read_db: AsyncSession):
        self.db = read_db

    async def project(self, event: DomainEvent):
        handler = getattr(self, f"_handle_{event.event_type}", None)
        if handler:
            await handler(event)

    async def _handle_order_created(self, event: DomainEvent):
        order = OrderReadModel(
            id=event.aggregate_id,
            customer_id=event.data["customer_id"],
            status="pending",
            items=event.data["items"],
            total=sum(i["price"] * i["quantity"] for i in event.data["items"]),
            created_at=event.timestamp
        )
        self.db.add(order)
        await self.db.commit()

    async def _handle_order_paid(self, event: DomainEvent):
        await self.db.execute(
            update(OrderReadModel)
            .where(OrderReadModel.id == event.aggregate_id)
            .values(status="paid")
        )
        await self.db.commit()


# Mediator pattern for dispatching
class Mediator:
    def __init__(self):
        self._command_handlers: Dict[Type[Command], CommandHandler] = {}
        self._query_handlers: Dict[Type[Query], QueryHandler] = {}

    def register_command(self, command_type: Type[Command], handler: CommandHandler):
        self._command_handlers[command_type] = handler

    def register_query(self, query_type: Type[Query], handler: QueryHandler):
        self._query_handlers[query_type] = handler

    async def send(self, command: Command):
        handler = self._command_handlers.get(type(command))
        if not handler:
            raise ValueError(f"No handler for {type(command)}")
        return await handler.handle(command)

    async def query(self, query: Query[TResult]) -> TResult:
        handler = self._query_handlers.get(type(query))
        if not handler:
            raise ValueError(f"No handler for {type(query)}")
        return await handler.handle(query)


# FastAPI integration
mediator = Mediator()

@app.post("/commands/create-order")
async def create_order_command(command: CreateOrderCommand):
    order_id = await mediator.send(command)
    return {"order_id": order_id}


@app.get("/queries/orders/{order_id}")
async def get_order_query(order_id: str):
    query = GetOrderQuery(order_id=order_id)
    result = await mediator.query(query)
    if not result:
        raise HTTPException(404)
    return result
```

### Webhook Implementation

```python
from fastapi import FastAPI, Request, HTTPException, Header, BackgroundTasks
from pydantic import BaseModel, HttpUrl
from typing import List, Optional
import hmac
import hashlib
import httpx
from datetime import datetime
import asyncio

app = FastAPI()


# Webhook subscription model
class WebhookSubscription(BaseModel):
    id: str
    url: HttpUrl
    events: List[str]
    secret: str
    is_active: bool = True
    created_at: datetime


# Webhook delivery model
class WebhookDelivery(BaseModel):
    id: str
    subscription_id: str
    event_type: str
    payload: dict
    status: str  # pending, delivered, failed
    attempts: int = 0
    last_attempt: Optional[datetime] = None
    response_code: Optional[int] = None


# Webhook manager
class WebhookManager:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.max_retries = 3
        self.retry_delays = [60, 300, 3600]  # seconds

    def sign_payload(self, payload: str, secret: str) -> str:
        return hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()

    async def get_subscriptions(self, event_type: str) -> List[WebhookSubscription]:
        result = await self.db.execute(
            select(WebhookSubscription)
            .where(WebhookSubscription.is_active == True)
            .where(WebhookSubscription.events.contains([event_type]))
        )
        return result.scalars().all()

    async def deliver(self, subscription: WebhookSubscription, event: dict):
        payload = json.dumps(event)
        signature = self.sign_payload(payload, subscription.secret)

        delivery = WebhookDelivery(
            id=str(uuid.uuid4()),
            subscription_id=subscription.id,
            event_type=event["type"],
            payload=event,
            status="pending"
        )

        success = await self._attempt_delivery(delivery, subscription, payload, signature)

        if not success:
            # Schedule retries
            asyncio.create_task(self._retry_delivery(delivery, subscription))

    async def _attempt_delivery(
        self,
        delivery: WebhookDelivery,
        subscription: WebhookSubscription,
        payload: str,
        signature: str
    ) -> bool:
        delivery.attempts += 1
        delivery.last_attempt = datetime.utcnow()

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    str(subscription.url),
                    content=payload,
                    headers={
                        "Content-Type": "application/json",
                        "X-Webhook-Signature": signature,
                        "X-Webhook-Event": delivery.event_type,
                        "X-Webhook-Delivery": delivery.id
                    },
                    timeout=30.0
                )

            delivery.response_code = response.status_code

            if 200 <= response.status_code < 300:
                delivery.status = "delivered"
                return True
            else:
                delivery.status = "failed"
                return False

        except Exception as e:
            delivery.status = "failed"
            logger.error(f"Webhook delivery failed: {e}")
            return False

    async def _retry_delivery(
        self,
        delivery: WebhookDelivery,
        subscription: WebhookSubscription
    ):
        for delay in self.retry_delays:
            if delivery.attempts >= self.max_retries:
                break

            await asyncio.sleep(delay)

            payload = json.dumps(delivery.payload)
            signature = self.sign_payload(payload, subscription.secret)

            if await self._attempt_delivery(delivery, subscription, payload, signature):
                break

    async def trigger(self, event_type: str, data: dict):
        event = {
            "id": str(uuid.uuid4()),
            "type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data
        }

        subscriptions = await self.get_subscriptions(event_type)

        for subscription in subscriptions:
            asyncio.create_task(self.deliver(subscription, event))


# Webhook endpoints
@app.post("/webhooks/subscriptions")
async def create_subscription(
    url: HttpUrl,
    events: List[str],
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    secret = secrets.token_urlsafe(32)
    subscription = WebhookSubscription(
        id=str(uuid.uuid4()),
        url=url,
        events=events,
        secret=secret,
        created_at=datetime.utcnow()
    )
    db.add(subscription)
    await db.commit()

    return {
        "id": subscription.id,
        "secret": secret,  # Only shown once
        "url": str(url),
        "events": events
    }


@app.get("/webhooks/subscriptions")
async def list_subscriptions(
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(WebhookSubscription)
        .where(WebhookSubscription.user_id == current_user.id)
    )
    return result.scalars().all()


# Incoming webhook handler
@app.post("/webhooks/incoming/{provider}")
async def handle_incoming_webhook(
    provider: str,
    request: Request,
    x_signature: str = Header(None, alias="X-Webhook-Signature")
):
    body = await request.body()

    # Verify signature
    secret = get_webhook_secret(provider)
    expected_sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(x_signature or "", expected_sig):
        raise HTTPException(401, "Invalid signature")

    # Process webhook
    data = json.loads(body)
    await process_webhook(provider, data)

    return {"status": "received"}
```

---

## 8.2 Microservices Patterns

### Service Discovery

```python
import httpx
from typing import Optional, List
import random
import asyncio
from datetime import datetime, timedelta

# Consul service discovery
class ConsulServiceDiscovery:
    def __init__(self, consul_url: str = "http://localhost:8500"):
        self.consul_url = consul_url
        self._cache: dict[str, list] = {}
        self._cache_ttl = 30  # seconds

    async def register(
        self,
        service_name: str,
        service_id: str,
        address: str,
        port: int,
        health_check_url: str
    ):
        async with httpx.AsyncClient() as client:
            await client.put(
                f"{self.consul_url}/v1/agent/service/register",
                json={
                    "Name": service_name,
                    "ID": service_id,
                    "Address": address,
                    "Port": port,
                    "Check": {
                        "HTTP": health_check_url,
                        "Interval": "10s",
                        "Timeout": "5s"
                    }
                }
            )

    async def deregister(self, service_id: str):
        async with httpx.AsyncClient() as client:
            await client.put(
                f"{self.consul_url}/v1/agent/service/deregister/{service_id}"
            )

    async def get_service_instances(self, service_name: str) -> List[dict]:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.consul_url}/v1/health/service/{service_name}",
                params={"passing": "true"}
            )
            services = response.json()

            return [
                {
                    "address": svc["Service"]["Address"],
                    "port": svc["Service"]["Port"]
                }
                for svc in services
            ]

    async def get_service_url(self, service_name: str) -> Optional[str]:
        instances = await self.get_service_instances(service_name)
        if not instances:
            return None

        # Load balancing: random selection
        instance = random.choice(instances)
        return f"http://{instance['address']}:{instance['port']}"


# DNS-based service discovery (Kubernetes)
import socket

class KubernetesServiceDiscovery:
    def __init__(self, namespace: str = "default"):
        self.namespace = namespace

    def get_service_url(self, service_name: str) -> str:
        # Kubernetes DNS: service-name.namespace.svc.cluster.local
        return f"http://{service_name}.{self.namespace}.svc.cluster.local"

    async def get_service_endpoints(self, service_name: str) -> List[str]:
        # Headless service returns all pod IPs
        hostname = f"{service_name}.{self.namespace}.svc.cluster.local"
        try:
            _, _, ips = socket.gethostbyname_ex(hostname)
            return [f"http://{ip}" for ip in ips]
        except socket.gaierror:
            return []


# Service client with discovery
class ServiceClient:
    def __init__(self, discovery: ConsulServiceDiscovery):
        self.discovery = discovery
        self._client = httpx.AsyncClient()

    async def call(
        self,
        service_name: str,
        method: str,
        path: str,
        **kwargs
    ) -> httpx.Response:
        url = await self.discovery.get_service_url(service_name)
        if not url:
            raise Exception(f"Service {service_name} not found")

        return await self._client.request(
            method,
            f"{url}{path}",
            **kwargs
        )


# FastAPI integration
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Register service
    discovery = ConsulServiceDiscovery()
    await discovery.register(
        service_name="user-service",
        service_id=f"user-service-{uuid.uuid4()}",
        address=settings.host,
        port=settings.port,
        health_check_url=f"http://{settings.host}:{settings.port}/health"
    )

    app.state.discovery = discovery
    app.state.service_client = ServiceClient(discovery)

    yield

    # Deregister on shutdown
    await discovery.deregister(app.state.service_id)

app = FastAPI(lifespan=lifespan)


@app.get("/users/{user_id}/orders")
async def get_user_orders(user_id: int, request: Request):
    client = request.app.state.service_client
    response = await client.call(
        "order-service",
        "GET",
        f"/orders?user_id={user_id}"
    )
    return response.json()
```

### Inter-Service Communication

```python
import httpx
from typing import Optional, TypeVar, Generic
from pydantic import BaseModel
import asyncio

T = TypeVar("T")


# gRPC service (with grpcio)
"""
# user_service.proto
syntax = "proto3";

service UserService {
    rpc GetUser (GetUserRequest) returns (UserResponse);
    rpc ListUsers (ListUsersRequest) returns (stream UserResponse);
}

message GetUserRequest {
    int32 user_id = 1;
}

message UserResponse {
    int32 id = 1;
    string username = 2;
    string email = 3;
}
"""

# Generated client usage
import grpc
from user_pb2 import GetUserRequest
from user_pb2_grpc import UserServiceStub

class GRPCUserClient:
    def __init__(self, host: str = "user-service:50051"):
        self.channel = grpc.aio.insecure_channel(host)
        self.stub = UserServiceStub(self.channel)

    async def get_user(self, user_id: int):
        request = GetUserRequest(user_id=user_id)
        response = await self.stub.GetUser(request)
        return response


# REST client with retry
class ServiceClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client = httpx.AsyncClient(
            base_url=base_url,
            timeout=30.0
        )

    async def get(
        self,
        path: str,
        retry_count: int = 3,
        retry_delay: float = 1.0
    ) -> dict:
        for attempt in range(retry_count):
            try:
                response = await self.client.get(path)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                if e.response.status_code >= 500 and attempt < retry_count - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))
                    continue
                raise
            except httpx.RequestError as e:
                if attempt < retry_count - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))
                    continue
                raise

    async def post(self, path: str, data: dict) -> dict:
        response = await self.client.post(path, json=data)
        response.raise_for_status()
        return response.json()


# Request context propagation
class ContextPropagatingClient:
    def __init__(self, base_url: str):
        self.base_url = base_url

    async def request(self, method: str, path: str, **kwargs):
        # Get context from current request
        request_id = request_id_ctx.get()
        user_id = user_id_ctx.get()
        trace_id = trace_id_ctx.get()

        headers = kwargs.pop("headers", {})
        headers.update({
            "X-Request-ID": request_id,
            "X-User-ID": str(user_id) if user_id else "",
            "X-Trace-ID": trace_id
        })

        async with httpx.AsyncClient(base_url=self.base_url) as client:
            return await client.request(method, path, headers=headers, **kwargs)


# Async communication with message queue
class OrderServiceClient:
    def __init__(self, message_broker):
        self.broker = message_broker

    async def create_order(self, order_data: dict) -> str:
        # Send command message
        correlation_id = str(uuid.uuid4())

        await self.broker.publish(
            "orders.commands.create",
            {
                "correlation_id": correlation_id,
                "data": order_data,
                "reply_to": "orders.replies"
            }
        )

        # Wait for response
        response = await self.broker.wait_for_reply(correlation_id, timeout=30)
        return response["order_id"]

    async def create_order_async(self, order_data: dict):
        # Fire and forget
        await self.broker.publish(
            "orders.commands.create",
            {"data": order_data}
        )
```

### Circuit Breaker Pattern

```python
from enum import Enum
from datetime import datetime, timedelta
from typing import Callable, TypeVar, Optional
import asyncio
from functools import wraps

T = TypeVar("T")


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout: int = 60,
        expected_exception: type = Exception
    ):
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout = timeout
        self.expected_exception = expected_exception

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None

    def can_execute(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            if datetime.utcnow() - self.last_failure_time > timedelta(seconds=self.timeout):
                self.state = CircuitState.HALF_OPEN
                return True
            return False

        return True  # HALF_OPEN

    def record_success(self):
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
        else:
            self.failure_count = 0

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()

        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            self.success_count = 0
        elif self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN


class CircuitBreakerOpen(Exception):
    pass


def circuit_breaker(
    failure_threshold: int = 5,
    timeout: int = 60
):
    breaker = CircuitBreaker(failure_threshold=failure_threshold, timeout=timeout)

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not breaker.can_execute():
                raise CircuitBreakerOpen("Circuit is open")

            try:
                result = await func(*args, **kwargs)
                breaker.record_success()
                return result
            except Exception as e:
                breaker.record_failure()
                raise

        wrapper.breaker = breaker
        return wrapper
    return decorator


# Usage
@circuit_breaker(failure_threshold=5, timeout=30)
async def call_external_service(data: dict):
    async with httpx.AsyncClient() as client:
        response = await client.post("https://api.external.com/data", json=data)
        response.raise_for_status()
        return response.json()


# With fallback
async def call_with_fallback(data: dict):
    try:
        return await call_external_service(data)
    except CircuitBreakerOpen:
        # Return cached or default data
        return get_cached_data(data)


# Circuit breaker registry
class CircuitBreakerRegistry:
    def __init__(self):
        self._breakers: dict[str, CircuitBreaker] = {}

    def get_or_create(
        self,
        name: str,
        failure_threshold: int = 5,
        timeout: int = 60
    ) -> CircuitBreaker:
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(
                failure_threshold=failure_threshold,
                timeout=timeout
            )
        return self._breakers[name]

    def get_status(self) -> dict:
        return {
            name: {
                "state": breaker.state.value,
                "failure_count": breaker.failure_count,
                "last_failure": breaker.last_failure_time
            }
            for name, breaker in self._breakers.items()
        }


registry = CircuitBreakerRegistry()


# Health endpoint for circuit status
@app.get("/health/circuits")
async def get_circuit_status():
    return registry.get_status()
```

### Retry Strategies

```python
from typing import Callable, TypeVar, Optional, Type, Tuple
import asyncio
import random
from functools import wraps

T = TypeVar("T")


class RetryConfig:
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retry_exceptions: Tuple[Type[Exception], ...] = (Exception,)
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retry_exceptions = retry_exceptions

    def get_delay(self, attempt: int) -> float:
        delay = self.base_delay * (self.exponential_base ** attempt)
        delay = min(delay, self.max_delay)

        if self.jitter:
            delay = delay * (0.5 + random.random())

        return delay


def retry(config: RetryConfig = None):
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_exception = None

            for attempt in range(config.max_attempts):
                try:
                    return await func(*args, **kwargs)
                except config.retry_exceptions as e:
                    last_exception = e

                    if attempt < config.max_attempts - 1:
                        delay = config.get_delay(attempt)
                        logger.warning(
                            f"Retry {attempt + 1}/{config.max_attempts} "
                            f"after {delay:.2f}s: {e}"
                        )
                        await asyncio.sleep(delay)

            raise last_exception

        return wrapper
    return decorator


# Usage
@retry(RetryConfig(
    max_attempts=5,
    base_delay=1.0,
    retry_exceptions=(httpx.HTTPStatusError, httpx.RequestError)
))
async def fetch_data(url: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()


# Retry with backoff strategies
class BackoffStrategy:
    def get_delay(self, attempt: int) -> float:
        raise NotImplementedError


class ConstantBackoff(BackoffStrategy):
    def __init__(self, delay: float):
        self.delay = delay

    def get_delay(self, attempt: int) -> float:
        return self.delay


class LinearBackoff(BackoffStrategy):
    def __init__(self, initial_delay: float, increment: float):
        self.initial_delay = initial_delay
        self.increment = increment

    def get_delay(self, attempt: int) -> float:
        return self.initial_delay + (self.increment * attempt)


class ExponentialBackoff(BackoffStrategy):
    def __init__(self, base_delay: float, max_delay: float = 60):
        self.base_delay = base_delay
        self.max_delay = max_delay

    def get_delay(self, attempt: int) -> float:
        delay = self.base_delay * (2 ** attempt)
        return min(delay, self.max_delay)


class DecorrelatedJitterBackoff(BackoffStrategy):
    """AWS-style decorrelated jitter"""
    def __init__(self, base_delay: float, max_delay: float = 60):
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.last_delay = base_delay

    def get_delay(self, attempt: int) -> float:
        delay = random.uniform(self.base_delay, self.last_delay * 3)
        delay = min(delay, self.max_delay)
        self.last_delay = delay
        return delay


# Retry with condition
def retry_if(
    condition: Callable[[Exception], bool],
    max_attempts: int = 3,
    backoff: BackoffStrategy = None
):
    if backoff is None:
        backoff = ExponentialBackoff(1.0)

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if not condition(e):
                        raise

                    last_exception = e

                    if attempt < max_attempts - 1:
                        await asyncio.sleep(backoff.get_delay(attempt))

            raise last_exception
        return wrapper
    return decorator


# Only retry on specific status codes
@retry_if(
    lambda e: isinstance(e, httpx.HTTPStatusError) and e.response.status_code >= 500,
    max_attempts=3
)
async def call_service(data: dict):
    async with httpx.AsyncClient() as client:
        response = await client.post("https://api.service.com", json=data)
        response.raise_for_status()
        return response.json()
```

### API Gateway Patterns

```python
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import Response
import httpx
from typing import Dict
from dataclasses import dataclass

app = FastAPI()


@dataclass
class ServiceRoute:
    name: str
    url: str
    strip_prefix: bool = True
    timeout: float = 30.0


# Service registry
SERVICES: Dict[str, ServiceRoute] = {
    "users": ServiceRoute("users", "http://user-service:8000", strip_prefix=True),
    "orders": ServiceRoute("orders", "http://order-service:8000", strip_prefix=True),
    "products": ServiceRoute("products", "http://product-service:8000", strip_prefix=True),
}


# Simple API gateway
@app.api_route("/{service}/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def gateway(service: str, path: str, request: Request):
    if service not in SERVICES:
        raise HTTPException(404, f"Service '{service}' not found")

    route = SERVICES[service]

    # Build target URL
    target_path = path if route.strip_prefix else f"{service}/{path}"
    target_url = f"{route.url}/{target_path}"

    # Add query params
    if request.query_params:
        target_url += f"?{request.query_params}"

    # Forward request
    body = await request.body()
    headers = dict(request.headers)
    headers.pop("host", None)

    # Add gateway headers
    headers["X-Forwarded-For"] = request.client.host
    headers["X-Request-ID"] = headers.get("X-Request-ID", str(uuid.uuid4()))

    async with httpx.AsyncClient() as client:
        try:
            response = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body,
                timeout=route.timeout
            )

            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=dict(response.headers)
            )
        except httpx.TimeoutException:
            raise HTTPException(504, "Gateway timeout")
        except httpx.RequestError as e:
            raise HTTPException(502, f"Bad gateway: {e}")


# Gateway with authentication
@app.middleware("http")
async def gateway_auth(request: Request, call_next):
    # Skip auth for certain paths
    if request.url.path in ["/health", "/docs", "/openapi.json"]:
        return await call_next(request)

    # Validate token
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return Response(
            content='{"error": "Unauthorized"}',
            status_code=401,
            media_type="application/json"
        )

    token = auth_header.replace("Bearer ", "")

    try:
        payload = validate_token(token)
        request.state.user = payload
    except Exception:
        return Response(
            content='{"error": "Invalid token"}',
            status_code=401,
            media_type="application/json"
        )

    return await call_next(request)


# Rate limiting at gateway
from collections import defaultdict
from datetime import datetime

class GatewayRateLimiter:
    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.requests: Dict[str, list] = defaultdict(list)

    def is_allowed(self, client_id: str) -> bool:
        now = datetime.utcnow()
        minute_ago = now - timedelta(minutes=1)

        # Clean old requests
        self.requests[client_id] = [
            t for t in self.requests[client_id] if t > minute_ago
        ]

        if len(self.requests[client_id]) >= self.requests_per_minute:
            return False

        self.requests[client_id].append(now)
        return True


rate_limiter = GatewayRateLimiter(requests_per_minute=100)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_id = request.headers.get("X-API-Key", request.client.host)

    if not rate_limiter.is_allowed(client_id):
        return Response(
            content='{"error": "Rate limit exceeded"}',
            status_code=429,
            media_type="application/json",
            headers={"Retry-After": "60"}
        )

    return await call_next(request)


# Aggregation endpoint
@app.get("/api/dashboard")
async def dashboard(request: Request):
    """Aggregate data from multiple services"""
    async with httpx.AsyncClient() as client:
        user_task = client.get(f"{SERVICES['users'].url}/users/me")
        orders_task = client.get(f"{SERVICES['orders'].url}/orders/recent")
        products_task = client.get(f"{SERVICES['products'].url}/products/featured")

        user_resp, orders_resp, products_resp = await asyncio.gather(
            user_task, orders_task, products_task,
            return_exceptions=True
        )

    return {
        "user": user_resp.json() if not isinstance(user_resp, Exception) else None,
        "recent_orders": orders_resp.json() if not isinstance(orders_resp, Exception) else [],
        "featured_products": products_resp.json() if not isinstance(products_resp, Exception) else []
    }
```

---

## 8.3 GraphQL Integration

### Strawberry GraphQL with FastAPI

```python
from fastapi import FastAPI, Depends
import strawberry
from strawberry.fastapi import GraphQLRouter
from strawberry.types import Info
from typing import List, Optional

# Types
@strawberry.type
class User:
    id: int
    username: str
    email: str


@strawberry.type
class Post:
    id: int
    title: str
    content: str
    author_id: int

    @strawberry.field
    async def author(self) -> User:
        return await get_user(self.author_id)


@strawberry.type
class PaginatedPosts:
    items: List[Post]
    total: int
    has_next: bool


# Input types
@strawberry.input
class CreateUserInput:
    username: str
    email: str
    password: str


@strawberry.input
class CreatePostInput:
    title: str
    content: str


# Query
@strawberry.type
class Query:
    @strawberry.field
    async def user(self, id: int) -> Optional[User]:
        return await get_user(id)

    @strawberry.field
    async def users(self, limit: int = 10, offset: int = 0) -> List[User]:
        return await get_users(limit=limit, offset=offset)

    @strawberry.field
    async def post(self, id: int) -> Optional[Post]:
        return await get_post(id)

    @strawberry.field
    async def posts(
        self,
        limit: int = 10,
        offset: int = 0,
        author_id: Optional[int] = None
    ) -> PaginatedPosts:
        posts, total = await get_posts(limit, offset, author_id)
        return PaginatedPosts(
            items=posts,
            total=total,
            has_next=offset + limit < total
        )


# Mutations
@strawberry.type
class Mutation:
    @strawberry.mutation
    async def create_user(self, input: CreateUserInput) -> User:
        return await create_user(input)

    @strawberry.mutation
    async def create_post(
        self,
        input: CreatePostInput,
        info: Info
    ) -> Post:
        # Get current user from context
        user = info.context["user"]
        return await create_post(input, user.id)

    @strawberry.mutation
    async def delete_post(self, id: int, info: Info) -> bool:
        user = info.context["user"]
        post = await get_post(id)

        if post.author_id != user.id:
            raise Exception("Not authorized")

        await delete_post(id)
        return True


# Subscriptions
@strawberry.type
class Subscription:
    @strawberry.subscription
    async def post_created(self) -> Post:
        async for post in post_created_stream():
            yield post

    @strawberry.subscription
    async def user_activity(self, user_id: int) -> str:
        async for activity in user_activity_stream(user_id):
            yield activity


# Schema
schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    subscription=Subscription
)


# Context getter
async def get_context(request: Request):
    # Get authenticated user
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    user = await authenticate(token) if token else None

    return {
        "request": request,
        "user": user,
        "db": get_db()
    }


# GraphQL router
graphql_router = GraphQLRouter(
    schema,
    context_getter=get_context,
    graphiql=True
)


# FastAPI app
app = FastAPI()
app.include_router(graphql_router, prefix="/graphql")
```

### Schema Design

```python
import strawberry
from strawberry import UNSET
from typing import List, Optional, Union
from enum import Enum
from datetime import datetime

# Enums
@strawberry.enum
class OrderStatus(Enum):
    PENDING = "pending"
    PAID = "paid"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


@strawberry.enum
class SortDirection(Enum):
    ASC = "asc"
    DESC = "desc"


# Interfaces
@strawberry.interface
class Node:
    id: strawberry.ID


@strawberry.interface
class Timestamped:
    created_at: datetime
    updated_at: Optional[datetime]


# Types implementing interfaces
@strawberry.type
class User(Node, Timestamped):
    id: strawberry.ID
    username: str
    email: str
    created_at: datetime
    updated_at: Optional[datetime]

    @strawberry.field
    async def orders(
        self,
        status: Optional[OrderStatus] = None,
        limit: int = 10
    ) -> List["Order"]:
        return await get_user_orders(self.id, status, limit)


@strawberry.type
class Order(Node, Timestamped):
    id: strawberry.ID
    status: OrderStatus
    total: float
    created_at: datetime
    updated_at: Optional[datetime]

    @strawberry.field
    async def user(self) -> User:
        return await get_user(self.user_id)

    @strawberry.field
    async def items(self) -> List["OrderItem"]:
        return await get_order_items(self.id)


# Union types
@strawberry.type
class Product(Node):
    id: strawberry.ID
    name: str
    price: float


@strawberry.type
class Service(Node):
    id: strawberry.ID
    name: str
    hourly_rate: float


SearchResult = strawberry.union("SearchResult", [Product, Service, User])


@strawberry.type
class Query:
    @strawberry.field
    async def search(self, query: str) -> List[SearchResult]:
        return await search_all(query)


# Input types with validation
@strawberry.input
class PaginationInput:
    limit: int = strawberry.field(default=10)
    offset: int = strawberry.field(default=0)

    def __post_init__(self):
        if self.limit < 1 or self.limit > 100:
            raise ValueError("Limit must be between 1 and 100")
        if self.offset < 0:
            raise ValueError("Offset must be non-negative")


@strawberry.input
class OrderInput:
    field: str
    direction: SortDirection = SortDirection.ASC


@strawberry.input
class UserFilterInput:
    username_contains: Optional[str] = None
    email_contains: Optional[str] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None


# Relay-style pagination
@strawberry.type
class PageInfo:
    has_next_page: bool
    has_previous_page: bool
    start_cursor: Optional[str]
    end_cursor: Optional[str]


@strawberry.type
class UserEdge:
    cursor: str
    node: User


@strawberry.type
class UserConnection:
    edges: List[UserEdge]
    page_info: PageInfo
    total_count: int


@strawberry.type
class Query:
    @strawberry.field
    async def users_connection(
        self,
        first: Optional[int] = None,
        after: Optional[str] = None,
        last: Optional[int] = None,
        before: Optional[str] = None
    ) -> UserConnection:
        return await get_users_connection(first, after, last, before)
```

### Resolvers and Data Loaders

```python
import strawberry
from strawberry.dataloader import DataLoader
from typing import List, Optional
from collections import defaultdict

# Data loaders for N+1 prevention
async def load_users(user_ids: List[int]) -> List[User]:
    users = await db.execute(
        select(UserModel).where(UserModel.id.in_(user_ids))
    )
    users_by_id = {u.id: u for u in users}
    return [users_by_id.get(id) for id in user_ids]


async def load_posts_by_author(author_ids: List[int]) -> List[List[Post]]:
    posts = await db.execute(
        select(PostModel).where(PostModel.author_id.in_(author_ids))
    )

    posts_by_author = defaultdict(list)
    for post in posts:
        posts_by_author[post.author_id].append(post)

    return [posts_by_author[id] for id in author_ids]


# Context with data loaders
async def get_context(request: Request):
    return {
        "request": request,
        "user_loader": DataLoader(load_fn=load_users),
        "posts_loader": DataLoader(load_fn=load_posts_by_author)
    }


# Using data loaders in resolvers
@strawberry.type
class Post:
    id: int
    title: str
    author_id: int

    @strawberry.field
    async def author(self, info: Info) -> User:
        loader = info.context["user_loader"]
        return await loader.load(self.author_id)


@strawberry.type
class User:
    id: int
    username: str

    @strawberry.field
    async def posts(self, info: Info) -> List[Post]:
        loader = info.context["posts_loader"]
        return await loader.load(self.id)


# Field-level permissions
from strawberry.permission import BasePermission

class IsAuthenticated(BasePermission):
    message = "User is not authenticated"

    async def has_permission(self, source, info: Info, **kwargs) -> bool:
        return info.context.get("user") is not None


class IsAdmin(BasePermission):
    message = "Admin access required"

    async def has_permission(self, source, info: Info, **kwargs) -> bool:
        user = info.context.get("user")
        return user and user.is_admin


class IsOwner(BasePermission):
    message = "You can only access your own data"

    async def has_permission(self, source, info: Info, **kwargs) -> bool:
        user = info.context.get("user")
        return user and source.user_id == user.id


@strawberry.type
class Query:
    @strawberry.field(permission_classes=[IsAuthenticated])
    async def me(self, info: Info) -> User:
        return info.context["user"]

    @strawberry.field(permission_classes=[IsAdmin])
    async def all_users(self) -> List[User]:
        return await get_all_users()


@strawberry.type
class Mutation:
    @strawberry.mutation(permission_classes=[IsAuthenticated])
    async def update_profile(self, input: UpdateProfileInput, info: Info) -> User:
        user = info.context["user"]
        return await update_user(user.id, input)


# Custom scalars
@strawberry.scalar(
    name="DateTime",
    description="ISO datetime string"
)
class DateTime:
    @staticmethod
    def serialize(value: datetime) -> str:
        return value.isoformat()

    @staticmethod
    def parse_value(value: str) -> datetime:
        return datetime.fromisoformat(value)


@strawberry.scalar(name="JSON")
class JSON:
    @staticmethod
    def serialize(value: dict) -> dict:
        return value

    @staticmethod
    def parse_value(value: dict) -> dict:
        return value
```

### Combining REST and GraphQL

```python
from fastapi import FastAPI, Depends
import strawberry
from strawberry.fastapi import GraphQLRouter

app = FastAPI()

# REST endpoints
@app.get("/api/users/{user_id}")
async def get_user_rest(user_id: int):
    return await get_user(user_id)


@app.post("/api/users")
async def create_user_rest(user: UserCreate):
    return await create_user(user)


@app.get("/api/posts")
async def list_posts_rest(limit: int = 10, offset: int = 0):
    return await get_posts(limit, offset)


# GraphQL schema
@strawberry.type
class Query:
    @strawberry.field
    async def user(self, id: int) -> User:
        return await get_user(id)

    @strawberry.field
    async def posts(self, limit: int = 10, offset: int = 0) -> List[Post]:
        posts, _ = await get_posts(limit, offset)
        return posts


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def create_user(self, input: CreateUserInput) -> User:
        return await create_user(input)


schema = strawberry.Schema(query=Query, mutation=Mutation)

graphql_router = GraphQLRouter(schema, graphiql=True)
app.include_router(graphql_router, prefix="/graphql")


# Shared service layer
class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, user_id: int) -> Optional[User]:
        result = await self.db.execute(
            select(UserModel).where(UserModel.id == user_id)
        )
        return result.scalar_one_or_none()

    async def create(self, data: dict) -> User:
        user = UserModel(**data)
        self.db.add(user)
        await self.db.commit()
        return user


# Both REST and GraphQL use the same service
def get_user_service(db: AsyncSession = Depends(get_db)) -> UserService:
    return UserService(db)


# REST with service
@app.get("/api/users/{user_id}")
async def get_user_rest(
    user_id: int,
    service: UserService = Depends(get_user_service)
):
    user = await service.get(user_id)
    if not user:
        raise HTTPException(404)
    return user


# GraphQL with service in context
async def get_context(request: Request, db: AsyncSession = Depends(get_db)):
    return {
        "request": request,
        "user_service": UserService(db)
    }


@strawberry.type
class Query:
    @strawberry.field
    async def user(self, id: int, info: Info) -> Optional[User]:
        service = info.context["user_service"]
        return await service.get(id)
```

---

## Summary

Module 8 covered advanced architectural patterns:

1. **Event-Driven Architecture** - Event publishing, message brokers (RabbitMQ, Kafka), event sourcing, CQRS, and webhook implementation

2. **Microservices Patterns** - Service discovery, inter-service communication, circuit breakers, retry strategies, and API gateway patterns

3. **GraphQL Integration** - Strawberry GraphQL setup, schema design, resolvers with data loaders, and combining REST with GraphQL

These patterns enable building sophisticated, scalable, and resilient distributed systems with FastAPI.

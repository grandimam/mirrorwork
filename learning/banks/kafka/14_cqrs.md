# Chapter 14: CQRS with Kafka

## Overview

CQRS (Command Query Responsibility Segregation) separates read and write models. Kafka is an excellent backbone for CQRS systems, enabling independent scaling and optimization of each side.

## Learning Objectives

By the end of this chapter, you will:

- Separate read and write models
- Build read-optimized views
- Handle eventual consistency
- Design CQRS architectures with Kafka

## Resources

| Resource | Time |
|----------|------|
| Read: CQRS pattern | 30 min |
| Hands-on: Implement CQRS with Kafka | 1 hr |

## Core Concepts

### Traditional vs CQRS

```
Traditional Architecture:
─────────────────────────
┌──────────────┐     ┌──────────────┐
│   Service    │ ──► │   Database   │
│  (Read/Write)│ ◄── │   (Single)   │
└──────────────┘     └──────────────┘

Same model for reads and writes
Contention between read and write workloads
Compromised optimization

CQRS Architecture:
──────────────────
┌──────────────┐     ┌──────────────┐
│    Write     │ ──► │  Write DB    │
│   Service    │     │  (Optimized  │
└──────┬───────┘     │  for writes) │
       │             └──────────────┘
       │ Events
       ▼
┌──────────────┐     ┌──────────────┐
│    Kafka     │ ──► │   Read DB    │
│   (Events)   │     │  (Optimized  │
└──────────────┘     │  for reads)  │
       │             └──────────────┘
       │
       ▼
┌──────────────┐
│    Read      │
│   Service    │
└──────────────┘

Separated concerns, independent scaling
Each side optimized for its workload
```

### CQRS with Kafka

```
Commands ──► Write Model ──► Kafka ──► Read Model ──► Queries
                │                          │
                ▼                          ▼
           PostgreSQL              Elasticsearch
           (source of truth)       (search-optimized)
                                          │
                                          ▼
                                   Redis (cache)
                                          │
                                          ▼
                                   ClickHouse (analytics)
```

## Key Questions to Understand

- Why separate read and write models?
- How do you handle eventual consistency?
- When is CQRS worth the complexity?

## Hands-On Exercises

### Exercise 1: Write Side - Command Handler

```python
from confluent_kafka import Producer
import json

class OrderCommandHandler:
    def __init__(self, db, producer: Producer):
        self.db = db
        self.producer = producer

    def create_order(self, order_data: dict):
        """
        Write side: validate, persist, publish event
        """
        # Validate
        if order_data['amount'] <= 0:
            raise ValueError('Invalid amount')

        # Persist to write DB (source of truth)
        order_id = self.db.execute("""
            INSERT INTO orders (customer_id, amount, status)
            VALUES (?, ?, 'pending')
            RETURNING id
        """, (order_data['customer_id'], order_data['amount']))

        # Publish event for read side
        event = {
            'type': 'OrderCreated',
            'order_id': order_id,
            'customer_id': order_data['customer_id'],
            'amount': order_data['amount'],
            'status': 'pending',
            'timestamp': datetime.utcnow().isoformat(),
        }
        self.producer.produce(
            'order-events',
            key=str(order_id).encode(),
            value=json.dumps(event).encode()
        )
        self.producer.flush()

        return order_id

    def ship_order(self, order_id: int):
        # Validate current state
        order = self.db.query("SELECT * FROM orders WHERE id = ?", (order_id,))
        if order['status'] != 'pending':
            raise ValueError('Order cannot be shipped')

        # Update write DB
        self.db.execute(
            "UPDATE orders SET status = 'shipped' WHERE id = ?",
            (order_id,)
        )

        # Publish event
        event = {
            'type': 'OrderShipped',
            'order_id': order_id,
            'timestamp': datetime.utcnow().isoformat(),
        }
        self.producer.produce('order-events', key=str(order_id).encode(), value=json.dumps(event).encode())
        self.producer.flush()
```

### Exercise 2: Read Side - Projections

```python
from confluent_kafka import Consumer
from elasticsearch import Elasticsearch

class OrderReadProjection:
    """
    Consumes events and builds read-optimized views
    """
    def __init__(self, bootstrap_servers: str):
        self.es = Elasticsearch()
        self.consumer = Consumer({
            'bootstrap.servers': bootstrap_servers,
            'group.id': 'order-read-projection',
            'auto.offset.reset': 'earliest',
        })

    def run(self):
        self.consumer.subscribe(['order-events'])

        while True:
            msg = self.consumer.poll(1.0)
            if msg is None:
                continue

            event = json.loads(msg.value())
            self.handle_event(event)

    def handle_event(self, event: dict):
        if event['type'] == 'OrderCreated':
            # Index in Elasticsearch for search
            self.es.index(
                index='orders',
                id=event['order_id'],
                document={
                    'order_id': event['order_id'],
                    'customer_id': event['customer_id'],
                    'amount': event['amount'],
                    'status': event['status'],
                    'created_at': event['timestamp'],
                }
            )

        elif event['type'] == 'OrderShipped':
            # Update existing document
            self.es.update(
                index='orders',
                id=event['order_id'],
                doc={
                    'status': 'shipped',
                    'shipped_at': event['timestamp'],
                }
            )
```

### Exercise 3: Multiple Projections

```python
class AnalyticsProjection:
    """
    Different projection for analytics queries
    """
    def __init__(self, clickhouse):
        self.ch = clickhouse
        self.consumer = Consumer({
            'bootstrap.servers': 'localhost:9092',
            'group.id': 'order-analytics-projection',
            'auto.offset.reset': 'earliest',
        })

    def handle_event(self, event: dict):
        if event['type'] == 'OrderCreated':
            # Optimized for time-series analytics
            self.ch.execute("""
                INSERT INTO order_events (
                    event_time, event_type, order_id, customer_id, amount
                ) VALUES
            """, [
                event['timestamp'],
                event['type'],
                event['order_id'],
                event['customer_id'],
                event['amount'],
            ])


class CacheProjection:
    """
    Projection for fast lookups
    """
    def __init__(self, redis):
        self.redis = redis

    def handle_event(self, event: dict):
        if event['type'] == 'OrderCreated':
            self.redis.hset(
                f"order:{event['order_id']}",
                mapping={
                    'customer_id': event['customer_id'],
                    'amount': event['amount'],
                    'status': event['status'],
                }
            )
            # Add to customer's orders list
            self.redis.lpush(
                f"customer:{event['customer_id']}:orders",
                event['order_id']
            )
```

### Exercise 4: Query Service

```python
from fastapi import FastAPI, HTTPException

app = FastAPI()

class OrderQueryService:
    def __init__(self, es, redis):
        self.es = es
        self.redis = redis

    def get_order(self, order_id: int) -> dict:
        """Fast single order lookup from cache"""
        cached = self.redis.hgetall(f"order:{order_id}")
        if cached:
            return cached

        # Fallback to Elasticsearch
        result = self.es.get(index='orders', id=order_id)
        return result['_source']

    def search_orders(self, customer_id: str = None, status: str = None) -> list:
        """Complex search from Elasticsearch"""
        query = {'bool': {'must': []}}

        if customer_id:
            query['bool']['must'].append({'term': {'customer_id': customer_id}})
        if status:
            query['bool']['must'].append({'term': {'status': status}})

        result = self.es.search(index='orders', query=query)
        return [hit['_source'] for hit in result['hits']['hits']]

    def get_customer_orders(self, customer_id: str) -> list:
        """Fast list from Redis"""
        order_ids = self.redis.lrange(f"customer:{customer_id}:orders", 0, -1)
        return [self.get_order(oid) for oid in order_ids]


@app.get("/orders/{order_id}")
async def get_order(order_id: int):
    return query_service.get_order(order_id)

@app.get("/orders")
async def search_orders(customer_id: str = None, status: str = None):
    return query_service.search_orders(customer_id, status)
```

## Handling Eventual Consistency

```python
# Problem: User creates order, immediately queries, doesn't see it

# Solution 1: Return created entity from command
@app.post("/orders")
async def create_order(order: OrderCreate):
    order_id = command_handler.create_order(order.dict())
    # Return what we know, don't query read side
    return {"order_id": order_id, "status": "pending"}

# Solution 2: Polling with timeout
async def wait_for_order(order_id: int, timeout: float = 5.0):
    start = time.time()
    while time.time() - start < timeout:
        try:
            return query_service.get_order(order_id)
        except NotFound:
            await asyncio.sleep(0.1)
    raise TimeoutError("Order not yet available")

# Solution 3: Optimistic UI
# Frontend shows "Creating order..." while polling
# Most systems: read-after-write consistency not critical
```

## When to Use CQRS

| Use CQRS When | Avoid CQRS When |
|---------------|-----------------|
| Read/write workloads differ significantly | Simple CRUD application |
| Need different read models | Single data store sufficient |
| Complex domain with many views | Team unfamiliar with pattern |
| Event sourcing already in use | Consistency requirements critical |
| Independent scaling required | Low traffic, simple queries |

## Interview Questions

- "What is CQRS and when would you use it?"
  - Not: "It separates reads and writes"
  - But: "CQRS separates the model for reading from the model for writing. Use it when read and write patterns differ significantly - like an e-commerce site with complex search (Elasticsearch) but simple order storage (PostgreSQL). Kafka connects them via events."

- "How do you handle consistency in CQRS?"
  - "Accept eventual consistency where possible. For user-facing creates, return the created entity directly from the command handler. For critical reads, either read from write DB or implement read-your-writes semantics with polling/waiting."

- "What are the downsides of CQRS?"
  - "Complexity: multiple databases to maintain, eventual consistency to handle, more failure modes. Debugging is harder - have to trace events through projections. Overkill for simple applications."

## Common Pitfalls

1. **Applying CQRS everywhere** - Use only where beneficial
2. **Ignoring eventual consistency** - Users confused by stale reads
3. **Projection falling behind** - Monitor lag
4. **No rebuild capability** - Projections should be rebuildable
5. **Coupling projections** - Each should be independent

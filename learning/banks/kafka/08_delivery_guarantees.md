# Chapter 8: Message Delivery Guarantees

## Overview

Understanding delivery semantics is critical for building reliable systems. Kafka offers different guarantees with different tradeoffs.

## Learning Objectives

By the end of this chapter, you will:

- Understand at-most-once, at-least-once, exactly-once
- Configure for your requirements
- Handle duplicate messages
- Implement idempotent processing

## Resources

| Resource | Time |
|----------|------|
| Read: Kafka delivery semantics | 30 min |

## Core Concepts

### Delivery Guarantees Spectrum

```
At-Most-Once              At-Least-Once             Exactly-Once
    │                          │                         │
    ▼                          ▼                         ▼
May lose messages        May duplicate              No loss, no dups
Fastest                  Middle ground              Slowest
Metrics, logs            Most applications          Financial, critical
```

### At-Most-Once

```
Producer                    Broker                   Consumer
   │                          │                         │
   ├──── send message ───────►│                         │
   │                          │◄── commit offset ───────┤
   │                          │                         │
   │                          │    (crash!)             │
   │                          │                         │
   │                          │    (restart)            │
   │                          │                         │
   │                          │    Offset already       │
   │                          │    committed, message   │
   │                          │    never processed      │
   │                          │    = LOST               │
```

**How to achieve:**
- Commit offset before processing
- Auto-commit enabled (default)

**Use case:** Metrics, logs where loss is acceptable

### At-Least-Once

```
Producer                    Broker                   Consumer
   │                          │                         │
   ├──── send message ───────►│                         │
   │                          │──── deliver message ───►│
   │                          │                         │ process
   │                          │                         │
   │                          │                         │ (crash before commit!)
   │                          │                         │
   │                          │    (restart)            │
   │                          │                         │
   │                          │──── deliver AGAIN ─────►│
   │                          │                         │ process AGAIN
   │                          │◄── commit offset ───────┤
   │                          │                         │
   │                          │    Same message         │
   │                          │    processed twice      │
   │                          │    = DUPLICATE          │
```

**How to achieve:**
- Commit offset after processing
- Manual commit or auto-commit after poll

**Use case:** Most applications (with idempotent consumers)

### Exactly-Once

```
Producer                    Broker                   Consumer
   │                          │                         │
   │  begin transaction       │                         │
   ├──────────────────────────┤                         │
   │                          │                         │
   ├──── send message ───────►│                         │
   │                          │                         │
   │  commit transaction      │                         │
   ├──────────────────────────┤                         │
   │                          │                         │
   │                          │    Transaction          │
   │                          │    committed atomically │
   │                          │    with offset          │
```

**How to achieve:**
- Idempotent producer + transactions
- Read committed isolation level
- Atomic offset commits within transaction

**Use case:** Financial transactions, critical data

## Delivery Guarantees Summary

| Guarantee | How to Achieve | Use Case |
|-----------|---------------|----------|
| At-most-once | Auto-commit before processing | Metrics, logs |
| At-least-once | Commit after processing | Most applications |
| Exactly-once | Idempotent producer + transactions | Financial, critical |

## Key Questions to Understand

- What does "exactly-once" really mean in Kafka?
- How do you handle duplicates with at-least-once?
- When is at-most-once acceptable?

## Hands-On Exercises

### Exercise 1: At-Least-Once Pattern

```python
from confluent_kafka import Consumer

config = {
    'bootstrap.servers': 'localhost:9092',
    'group.id': 'processor',
    'auto.offset.reset': 'earliest',
    'enable.auto.commit': False,  # Manual commit
}

consumer = Consumer(config)
consumer.subscribe(['orders'])

while True:
    msg = consumer.poll(1.0)
    if msg is None:
        continue
    if msg.error():
        continue

    # Process message FIRST
    try:
        process_order(msg.value())

        # Commit AFTER successful processing
        consumer.commit(msg)
    except Exception as e:
        # Don't commit - message will be redelivered
        log_error(e)
```

### Exercise 2: Handling Duplicates (Idempotency)

```python
import redis

redis_client = redis.Redis()

def process_order(order):
    order_id = order['order_id']

    # Check if already processed (idempotency key)
    if redis_client.sismember('processed_orders', order_id):
        print(f'Skipping duplicate: {order_id}')
        return

    # Process order
    db.execute("INSERT INTO orders ...")

    # Mark as processed (with TTL for cleanup)
    redis_client.sadd('processed_orders', order_id)
    redis_client.expire('processed_orders', 86400 * 7)  # 7 days
```

### Exercise 3: Database Idempotency

```python
def process_order_idempotent(order):
    order_id = order['order_id']

    # Use database constraints for idempotency
    try:
        db.execute("""
            INSERT INTO orders (order_id, amount, status)
            VALUES (?, ?, ?)
            ON CONFLICT (order_id) DO NOTHING
        """, (order_id, order['amount'], 'pending'))

        # Check if insert happened
        if db.rowcount > 0:
            print(f'Processed: {order_id}')
        else:
            print(f'Duplicate: {order_id}')
    except Exception as e:
        raise
```

### Exercise 4: Idempotent Producer

```python
from confluent_kafka import Producer

config = {
    'bootstrap.servers': 'localhost:9092',
    'enable.idempotence': True,  # Prevents duplicates on retry
    'acks': 'all',               # Required for idempotence
    'max.in.flight.requests.per.connection': 5,
}

producer = Producer(config)

# Even if this message is retried, it won't duplicate
producer.produce('orders', key='order-123', value='...')
producer.flush()
```

**How idempotent producer works:**
```
Producer ID (PID) = unique ID assigned by broker
Sequence number = increments per message

Message 1: PID=1, Seq=0 → Broker accepts
Message 2: PID=1, Seq=1 → Broker accepts
Retry of Message 1: PID=1, Seq=0 → Broker rejects (duplicate)
```

## At-Least-Once Best Practices

1. **Make consumers idempotent** - Always safe to process twice
2. **Use unique IDs** - Every message should have a dedup key
3. **Commit after processing** - Not before
4. **Handle partial failures** - What if processing half-completes?

```python
# Pattern: Outbox table for exactly-once to external systems
def process_with_outbox(order):
    with db.transaction():
        # Process order
        db.execute("INSERT INTO orders ...")

        # Record in outbox (same transaction)
        db.execute("""
            INSERT INTO outbox (id, processed)
            VALUES (?, false)
            ON CONFLICT (id) DO NOTHING
        """, (order['id'],))

    # Later: separate process reads outbox, sends to external system
```

## Interview Questions

- "How do you handle duplicate messages?"
  - Not: "Kafka has exactly-once"
  - But: "At-least-once is my default. I make consumers idempotent using a deduplication key stored in Redis or the database. For database writes, I use INSERT ON CONFLICT DO NOTHING. Exactly-once adds overhead and is only for critical paths."

- "What's the difference between idempotent producer and transactions?"
  - "Idempotent producer prevents duplicates from retries to the SAME topic. Transactions allow atomic writes to MULTIPLE topics and atomic offset commits. For simple produce, idempotence is enough. For consume-process-produce patterns, I need transactions."

- "When would you use at-most-once?"
  - "When data loss is acceptable and latency matters. Examples: real-time metrics where missing a data point is OK, click tracking where approximate counts are fine, log aggregation where completeness isn't critical."

## Common Pitfalls

1. **Assuming exactly-once is free** - It has latency cost
2. **Not making consumers idempotent** - Duplicates cause bugs
3. **Committing before processing** - Data loss
4. **Relying on message order for idempotency** - Order not guaranteed across partitions
5. **Forgetting partial failures** - What if DB commits but commit fails?

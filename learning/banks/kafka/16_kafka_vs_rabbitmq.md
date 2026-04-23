# Chapter 16: Kafka vs Message Queues (RabbitMQ)

## Overview

Choosing between Kafka and traditional message queues like RabbitMQ is a common architectural decision. Understanding their fundamental differences helps make the right choice.

## Learning Objectives

By the end of this chapter, you will:

- Know when to use Kafka vs RabbitMQ
- Understand architectural differences
- Choose the right tool for specific use cases
- Articulate trade-offs in interviews

## Core Concepts

### Fundamental Architecture Difference

```
RabbitMQ (Traditional Queue):
────────────────────────────
Producer → [Queue] → Consumer
                  ↳ Message DELETED after acknowledgment

- Push-based (broker pushes to consumers)
- Message deleted after processing
- One consumer per message (competing consumers)
- Complex routing via exchanges

Kafka (Distributed Log):
───────────────────────
Producer → [Log: 0,1,2,3,4,5...] ← Consumer A (offset 3)
                                 ← Consumer B (offset 1)
                                 ← Consumer C (offset 5)

- Pull-based (consumers pull from broker)
- Messages RETAINED (configurable time/size)
- Multiple independent consumers
- Partition-based routing
```

### Message Lifecycle

```
RabbitMQ:
Message → Queue → Delivered → Acknowledged → DELETED
                              (or rejected → requeue/DLQ)

Kafka:
Message → Log → Consumed → Consumed again → Consumed again...
                                          → Eventually deleted by retention
```

## Detailed Comparison

| Aspect | Kafka | RabbitMQ |
|--------|-------|----------|
| Model | Distributed log (pull) | Message queue (push) |
| Retention | Retained after consume | Deleted after ack |
| Consumer model | Consumer groups | Competing consumers |
| Multiple consumers | Yes, independent | Shared queue |
| Replay | Yes, from any offset | No |
| Ordering | Per partition | Per queue |
| Routing | Partition key | Exchange/routing key |
| Protocol | Custom binary | AMQP, STOMP, MQTT |
| Throughput | Millions/sec | Thousands/sec |
| Latency | Higher (batching) | Lower (single message) |
| Message size | Designed for small | Any size (with limits) |
| Persistence | Always persistent | Optional |

### Routing Patterns

```
RabbitMQ Exchanges:
──────────────────
Direct: route by exact key match
Topic: route by pattern (*.orders.#)
Fanout: broadcast to all queues
Headers: route by header values

┌──────────┐     exchange     ┌─────────┐
│ Producer │ ───────────────► │ Queue 1 │
└──────────┘         │        └─────────┘
                     │        ┌─────────┐
                     └──────► │ Queue 2 │
                              └─────────┘

Kafka Partitioning:
──────────────────
Single strategy: key → hash → partition

┌──────────┐     key=A     ┌─────────────┐
│ Producer │ ────────────► │ Partition 0 │
└──────────┘   key=B       ├─────────────┤
               ──────────► │ Partition 1 │
                           └─────────────┘
```

## When to Use What

### Use Kafka When

1. **Multiple consumers need same data independently**
   ```
   Order placed → Inventory service (updates stock)
                → Notification service (sends email)
                → Analytics service (records sale)

   Each service reads independently at its own pace
   ```

2. **Replay/reprocessing is needed**
   ```
   Bug discovered → Fix consumer → Replay from beginning
   New analytics → Start from offset 0
   Audit requirements → Complete history available
   ```

3. **High throughput is required**
   ```
   Millions of events per second
   Log aggregation
   Clickstream data
   IoT telemetry
   ```

4. **Event sourcing/CQRS**
   ```
   Events are source of truth
   Multiple read models derived from same events
   ```

5. **Stream processing**
   ```
   Real-time aggregations
   Joining streams
   Windowed computations
   ```

### Use RabbitMQ When

1. **Task queue (work distribution)**
   ```
   Job → Queue → Worker 1 processes → Done
             → Worker 2 processes → Done
             → Worker 3 processes → Done

   Each job processed once, then deleted
   ```

2. **Complex routing patterns**
   ```
   Route by headers, topic patterns
   Dynamic queue binding
   Message filtering at broker
   ```

3. **Request-reply pattern**
   ```
   Client → Request → Server
   Client ← Reply ←──┘

   Built-in reply-to and correlation ID
   ```

4. **Lower latency for single messages**
   ```
   Push model delivers immediately
   No batching overhead
   ```

5. **Message priority**
   ```
   Priority queues built-in
   Critical messages processed first
   ```

6. **Dead letter handling**
   ```
   Failed messages → Dead letter queue
   Rich retry policies
   ```

## Decision Matrix

| Use Case | Kafka | RabbitMQ | Why |
|----------|-------|----------|-----|
| Event sourcing | ✓ | | Replay, retention |
| Task queue | | ✓ | Delete after process |
| Multiple consumers same data | ✓ | | Independent consumption |
| Complex routing | | ✓ | Exchange patterns |
| Audit log | ✓ | | Immutable log |
| Request-reply | | ✓ | Built-in support |
| High throughput | ✓ | | Designed for scale |
| Simple app | | ✓ | Easier to operate |
| Stream processing | ✓ | | Native support |
| Message priority | | ✓ | Built-in |

## Code Comparison

### Kafka Producer

```python
from confluent_kafka import Producer

producer = Producer({'bootstrap.servers': 'localhost:9092'})
producer.produce('orders', key='user-123', value='order data')
producer.flush()
```

### RabbitMQ Producer

```python
import pika

connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()
channel.queue_declare(queue='orders')
channel.basic_publish(exchange='', routing_key='orders', body='order data')
connection.close()
```

### Kafka Consumer

```python
from confluent_kafka import Consumer

consumer = Consumer({
    'bootstrap.servers': 'localhost:9092',
    'group.id': 'my-group',
})
consumer.subscribe(['orders'])
while True:
    msg = consumer.poll(1.0)
    if msg:
        process(msg.value())
        # Offset committed, but message still in topic
```

### RabbitMQ Consumer

```python
import pika

connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()

def callback(ch, method, properties, body):
    process(body)
    ch.basic_ack(delivery_tag=method.delivery_tag)
    # Message deleted from queue

channel.basic_consume(queue='orders', on_message_callback=callback)
channel.start_consuming()
```

## Interview Questions

- "When would you choose Kafka over RabbitMQ?"
  - Not: "Kafka is better for big data"
  - But: "It depends on the use case. For event-driven architectures where multiple services need the same events independently, or when I need replay capability, I'd choose Kafka. For task queues where messages should be deleted after processing, or when I need complex routing patterns, RabbitMQ is simpler."

- "Can RabbitMQ do what Kafka does?"
  - "Partially. RabbitMQ has streams (since 3.9) for log-like behavior, but Kafka is purpose-built for high-throughput event streaming. Similarly, Kafka can do task queues but RabbitMQ is simpler for that use case. Choose the tool designed for your primary use case."

- "What about using both?"
  - "Sometimes makes sense. Kafka for event backbone (audit, analytics, event sourcing), RabbitMQ for task queues (email sending, video processing). But adds operational complexity. Usually better to standardize on one."

## Common Mistakes

1. **Using Kafka as a task queue** - Consumers must handle offsets carefully
2. **Using RabbitMQ for event sourcing** - Messages deleted after ack
3. **Choosing based on popularity** - Choose based on requirements
4. **Ignoring operational complexity** - Kafka requires more infrastructure
5. **Not considering team expertise** - Factor in learning curve

## Summary

```
KAFKA = Distributed Commit Log
- Retain messages
- Multiple independent consumers
- Replay from any point
- High throughput
- Event streaming

RABBITMQ = Message Broker
- Delete after acknowledge
- Competing consumers
- Complex routing
- Lower latency
- Task queues
```

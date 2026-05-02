# Chapter 3: Producers

## Overview

Producers are applications that publish records to Kafka topics. Understanding producer configuration is critical for balancing reliability, performance, and durability.

## Learning Objectives

By the end of this chapter, you will:

- Configure producer for reliability vs performance
- Understand acknowledgment modes
- Handle producer failures
- Implement idempotent producers

## Resources

| Resource | Time |
|----------|------|
| Read: https://kafka.apache.org/documentation/#producerconfigs | 30 min |
| Hands-on: Write producer with different configs | 45 min |

## Core Concepts

### Producer Workflow

```
Application
    │
    ▼
┌─────────────────────────────────────────┐
│              Producer                    │
│  ┌──────────┐  ┌──────────┐  ┌────────┐│
│  │Serializer│→ │Partitioner│→ │ Buffer ││
│  └──────────┘  └──────────┘  └────────┘│
│                                    │    │
│                              ┌─────▼───┐│
│                              │ Sender  ││
│                              └─────────┘│
└─────────────────────────────────────────┘
    │
    ▼
Kafka Broker
```

### Producer Acknowledgments (acks)

| acks | Durability | Latency | Use Case |
|------|------------|---------|----------|
| 0 | None | Lowest | Metrics, logs (loss OK) |
| 1 | Leader only | Medium | Most use cases |
| all (-1) | All replicas | Highest | Critical data |

**acks=0**: Fire and forget. No confirmation. Fastest but may lose data.

**acks=1**: Leader confirms write. If leader crashes before replication, data lost.

**acks=all**: All in-sync replicas confirm. Highest durability, highest latency.

### Key Producer Settings

```properties
# Required
bootstrap.servers=localhost:9092

# Reliability
acks=all                          # Wait for all replicas
retries=3                         # Retry on failure
retry.backoff.ms=100              # Wait between retries
enable.idempotence=true           # Prevent duplicates

# Performance
batch.size=16384                  # Batch size in bytes
linger.ms=5                       # Wait for batch to fill
buffer.memory=33554432            # Total buffer memory
compression.type=snappy           # Compress batches

# Timeouts
request.timeout.ms=30000          # Request timeout
delivery.timeout.ms=120000        # Total delivery timeout
```

## Key Questions to Understand

- What's the difference between acks=0, 1, and all?
- When would you use async vs sync sending?
- What happens if the broker is unavailable?

## Hands-On Exercises

### Exercise 1: Basic Python Producer

```python
from confluent_kafka import Producer

config = {
    'bootstrap.servers': 'localhost:9092',
    'acks': 'all',
    'retries': 3,
    'retry.backoff.ms': 100,
}

producer = Producer(config)

def delivery_callback(err, msg):
    if err:
        print(f'Delivery failed: {err}')
    else:
        print(f'Delivered to {msg.topic()}[{msg.partition()}]@{msg.offset()}')

# Send message
producer.produce(
    topic='orders',
    key='user-123',
    value='{"order_id": 1, "amount": 99.99}',
    callback=delivery_callback
)

producer.flush()  # Wait for all messages to be delivered
```

### Exercise 2: Idempotent Producer

```python
# Enable exactly-once producer semantics
config = {
    'bootstrap.servers': 'localhost:9092',
    'enable.idempotence': True,  # Prevents duplicates on retry
    'acks': 'all',               # Required for idempotence
    'max.in.flight.requests.per.connection': 5,  # Max with idempotence
}

producer = Producer(config)
```

**How idempotence works:**
- Producer gets a unique ID (PID)
- Each message gets a sequence number
- Broker deduplicates based on PID + sequence
- Retries don't create duplicates

### Exercise 3: Async vs Sync Sending

```python
# Async (non-blocking, higher throughput)
for order in orders:
    producer.produce('orders', value=order, callback=callback)
    producer.poll(0)  # Trigger delivery reports
producer.flush()

# Sync (blocking, lower throughput, simpler error handling)
for order in orders:
    producer.produce('orders', value=order)
    producer.flush()  # Wait for each message
```

### Exercise 4: Error Handling

```python
from confluent_kafka import KafkaException

def delivery_callback(err, msg):
    if err:
        if err.retriable():
            print(f'Retriable error: {err}')
        else:
            print(f'Fatal error: {err}')
            # Log to dead letter queue, alert, etc.
    else:
        print(f'Success: {msg.topic()}[{msg.partition()}]@{msg.offset()}')

try:
    producer.produce('orders', value='test')
    producer.flush(timeout=10)
except KafkaException as e:
    print(f'Kafka error: {e}')
except BufferError:
    print('Buffer full, slow down!')
```

## Batching and Performance

```
Without batching:
[msg1] → network → broker
[msg2] → network → broker
[msg3] → network → broker
3 round trips

With batching (linger.ms=5):
Wait 5ms...
[msg1, msg2, msg3] → network → broker
1 round trip, compressed
```

**Key settings for throughput:**

```properties
batch.size=65536          # Larger batches
linger.ms=10              # Wait longer to fill batches
compression.type=lz4      # Compress batches
buffer.memory=67108864    # More buffer space
```

## Interview Questions

- "How do you ensure no message loss?"
  - Not: "Set acks=all"
  - But: "acks=all ensures all replicas acknowledge. Combined with min.insync.replicas=2 and enable.idempotence=true, I get durability with exactly-once semantics. I also handle delivery callbacks to catch failures."

- "How do you optimize producer throughput?"
  - "Increase batch.size and linger.ms to batch more messages. Use compression (snappy/lz4). Send async with poll(0) instead of blocking. But watch buffer.memory to avoid OOM."

## Common Pitfalls

1. **Not calling flush()** - Messages may be lost on shutdown
2. **Ignoring delivery callbacks** - Silent failures
3. **acks=0 for critical data** - Data loss risk
4. **Too small batch.size** - Poor throughput
5. **Not handling BufferError** - Producer overwhelmed

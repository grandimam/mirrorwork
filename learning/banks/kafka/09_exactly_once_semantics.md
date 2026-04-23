# Chapter 9: Exactly-Once Semantics

## Overview

Exactly-once semantics (EOS) is Kafka's mechanism for ensuring messages are processed exactly once, even in the presence of failures. Understanding when and how to use it is crucial.

## Learning Objectives

By the end of this chapter, you will:

- Understand idempotent producers
- Use transactions for exactly-once
- Know the limitations and performance impact
- Decide when exactly-once is necessary

## Resources

| Resource | Time |
|----------|------|
| Read: https://www.confluent.io/blog/exactly-once-semantics-are-possible-heres-how-apache-kafka-does-it/ | 30 min |

## Core Concepts

### The Exactly-Once Challenge

```
Without EOS:

Producer sends message
    ↓
Broker receives, writes to log
    ↓
Broker crashes before sending ack
    ↓
Producer retries (doesn't know it succeeded)
    ↓
DUPLICATE MESSAGE in topic
```

### Idempotent Producer

Prevents duplicates from producer retries to a single partition.

```
How it works:

1. Broker assigns Producer ID (PID) to producer
2. Producer maintains sequence number per partition
3. Each message: (PID, Partition, Sequence)
4. Broker tracks last sequence per (PID, Partition)
5. Duplicate = same PID + same sequence → rejected

Message flow:
Producer: PID=1, Seq=0 → Broker accepts, stores Seq=0
Producer: PID=1, Seq=1 → Broker accepts, stores Seq=1
Producer: PID=1, Seq=0 (retry) → Broker rejects (duplicate)
Producer: PID=1, Seq=3 (out of order) → Broker rejects (gap)
```

**Configuration:**

```python
config = {
    'bootstrap.servers': 'localhost:9092',
    'enable.idempotence': True,  # Enable idempotent producer
    'acks': 'all',               # Required
    'max.in.flight.requests.per.connection': 5,  # Max allowed
}
```

### Transactions

Atomic writes across multiple partitions/topics AND atomic offset commits.

```
Transaction scope:

┌─────────────────────────────────────────────────────────┐
│                    TRANSACTION                          │
│                                                         │
│  Write to topic-A partition 0  ────┐                   │
│  Write to topic-A partition 1  ────┼── All succeed     │
│  Write to topic-B partition 0  ────┤   or all fail     │
│  Commit offsets for input topic ───┘                   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## Key Questions to Understand

- What's the difference between idempotent producer and transactions?
- What's the performance impact of exactly-once?
- When do you actually need exactly-once?

## Hands-On Exercises

### Exercise 1: Idempotent Producer

```python
from confluent_kafka import Producer

config = {
    'bootstrap.servers': 'localhost:9092',
    'enable.idempotence': True,
    'acks': 'all',
}

producer = Producer(config)

# These won't create duplicates even if retried
for i in range(100):
    producer.produce('orders', key=f'order-{i}', value=f'data-{i}')

producer.flush()
```

### Exercise 2: Transactional Producer

```python
from confluent_kafka import Producer

config = {
    'bootstrap.servers': 'localhost:9092',
    'transactional.id': 'my-transactional-producer',  # Required
    'enable.idempotence': True,  # Implied by transactional.id
}

producer = Producer(config)

# Initialize transactions (call once)
producer.init_transactions()

try:
    # Begin transaction
    producer.begin_transaction()

    # All these writes are atomic
    producer.produce('topic1', value='msg1')
    producer.produce('topic2', value='msg2')
    producer.produce('topic3', value='msg3')

    # Commit transaction
    producer.commit_transaction()
    print('Transaction committed')

except Exception as e:
    # Abort on any failure
    producer.abort_transaction()
    print(f'Transaction aborted: {e}')
```

### Exercise 3: Consume-Transform-Produce Pattern

```python
from confluent_kafka import Consumer, Producer

# Consumer config
consumer_config = {
    'bootstrap.servers': 'localhost:9092',
    'group.id': 'processor-group',
    'isolation.level': 'read_committed',  # Only see committed messages
    'enable.auto.commit': False,
}

# Producer config
producer_config = {
    'bootstrap.servers': 'localhost:9092',
    'transactional.id': 'processor-1',
}

consumer = Consumer(consumer_config)
producer = Producer(producer_config)

consumer.subscribe(['input-topic'])
producer.init_transactions()

while True:
    msgs = consumer.consume(100, timeout=1.0)
    if not msgs:
        continue

    producer.begin_transaction()
    try:
        for msg in msgs:
            # Transform
            result = transform(msg.value())

            # Produce to output
            producer.produce('output-topic', value=result)

        # Commit offsets as part of transaction
        producer.send_offsets_to_transaction(
            consumer.position(consumer.assignment()),
            consumer.consumer_group_metadata()
        )

        producer.commit_transaction()

    except Exception as e:
        producer.abort_transaction()
        print(f'Transaction failed: {e}')
```

## Transaction Internals

```
Transaction Coordinator (one per broker):
- Manages transaction state
- Writes to __transaction_state topic
- Coordinates two-phase commit

Transaction flow:
1. Producer: begin_transaction()
2. Producer: produce() to multiple partitions
   - Messages written with transaction marker
3. Producer: commit_transaction()
4. Coordinator: writes PREPARE to all partitions
5. Coordinator: writes COMMIT to all partitions
6. Messages become visible to consumers

Abort flow:
1. Producer: abort_transaction()
2. Coordinator: writes ABORT to all partitions
3. Messages discarded (never visible)
```

### Isolation Levels

```python
# Consumer isolation level
'isolation.level': 'read_uncommitted'  # See all messages (default)
'isolation.level': 'read_committed'    # Only see committed transactions
```

```
Timeline:
T1: begin_transaction()
T2: produce(msg1)
T3: produce(msg2)
T4: commit_transaction()

read_uncommitted consumer sees: msg1 at T2, msg2 at T3
read_committed consumer sees: msg1, msg2 at T4 (after commit)
```

## Performance Impact

| Feature | Overhead | Why |
|---------|----------|-----|
| Idempotent producer | ~3% | Sequence tracking |
| Transactions | ~20% | Two-phase commit, markers |
| read_committed | Variable | May wait for transaction completion |

### When to Use What

| Scenario | Solution |
|----------|----------|
| Simple produce, prevent retry dups | Idempotent producer |
| Produce to multiple topics atomically | Transactions |
| Consume-process-produce exactly-once | Transactions + read_committed |
| Maximum throughput, loss OK | Neither (acks=1) |

## Interview Questions

- "What does exactly-once mean in Kafka?"
  - Not: "Each message is processed exactly once"
  - But: "Within Kafka's boundaries - from produce to consume - messages appear exactly once. This doesn't extend to external systems. For external systems, I still need idempotent consumers."

- "When would you NOT use exactly-once?"
  - "When the overhead isn't worth it. For metrics, logs, or any use case where duplicates or small losses are acceptable. Also when processing is already idempotent - making the consumer handle duplicates may be cheaper than transaction overhead."

- "How do transactions affect latency?"
  - "Transaction markers add latency. read_committed consumers may wait for in-progress transactions to complete before reading. For latency-sensitive applications, I'd use idempotent producer without transactions if possible."

## Limitations

1. **Doesn't extend to external systems**
   - Writing to database still needs idempotency
   - Only guarantees within Kafka

2. **Transactional.id must be unique per producer instance**
   - Fencing: old producer with same ID is blocked
   - Use instance-specific IDs

3. **Transaction timeout**
   - Default 60 seconds
   - Long transactions may be aborted

4. **No nested transactions**
   - One transaction at a time per producer

## Common Pitfalls

1. **Thinking EOS covers external systems** - It doesn't
2. **Reusing transactional.id across instances** - Causes fencing
3. **Long-running transactions** - Risk of timeout
4. **Not using read_committed** - Consumers see uncommitted data
5. **Forgetting to call init_transactions()** - Required once

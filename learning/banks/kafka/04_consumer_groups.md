# Chapter 4: Consumer Groups

## Overview

Consumer groups are Kafka's mechanism for parallel consumption and fault tolerance. Understanding how they work is essential for building scalable applications.

## Learning Objectives

By the end of this chapter, you will:

- Understand consumer group coordination
- Know partition assignment strategies
- Handle rebalancing
- Configure offset management

## Resources

| Resource | Time |
|----------|------|
| Read: https://kafka.apache.org/documentation/#intro_consumers | 30 min |
| Watch: Consumer groups explained | 20 min |
| Hands-on: Multi-consumer setup | 45 min |

## Core Concepts

### Consumer Groups

A consumer group is a set of consumers that cooperatively consume from a topic.

```
Topic: orders (3 partitions)
├── Partition 0 ─────► Consumer 1 ┐
├── Partition 1 ─────► Consumer 2 ├── group: "order-processor"
└── Partition 2 ─────► Consumer 3 ┘
```

**Key rules:**
- Each partition is assigned to exactly one consumer in a group
- A consumer can handle multiple partitions
- Different groups consume independently (each gets all messages)

### Partition Assignment

```
3 partitions, 2 consumers:
├── Partition 0, 1 ──► Consumer 1
└── Partition 2     ──► Consumer 2

3 partitions, 3 consumers:
├── Partition 0 ──► Consumer 1
├── Partition 1 ──► Consumer 2
└── Partition 2 ──► Consumer 3

3 partitions, 4 consumers:
├── Partition 0 ──► Consumer 1
├── Partition 1 ──► Consumer 2
├── Partition 2 ──► Consumer 3
└── Consumer 4 sits idle (no partition)
```

### Offset Management

Kafka tracks what each consumer group has read via offsets.

```
Partition 0: [0] [1] [2] [3] [4] [5] [6] [7]
                              ↑
                    Committed offset for group "processor"

Consumer reads 5, 6, 7...
After commit: offset moves to 7
```

### Rebalancing

Rebalancing occurs when:
- Consumer joins the group
- Consumer leaves or crashes
- Partitions added to topic
- Consumer heartbeat timeout

```
Before: 2 consumers
├── P0, P1 ──► Consumer 1
└── P2     ──► Consumer 2

Consumer 2 crashes...
Rebalance triggered...

After: 1 consumer
└── P0, P1, P2 ──► Consumer 1
```

## Key Questions to Understand

- What happens if you have more consumers than partitions?
- How does Kafka track what each consumer has read?
- What triggers a rebalance?

## Hands-On Exercises

### Exercise 1: Basic Consumer Group

```bash
# Terminal 1: Start consumer in group
kafka-console-consumer --topic orders \
  --bootstrap-server localhost:9092 \
  --group order-processor

# Terminal 2: Start second consumer in same group
kafka-console-consumer --topic orders \
  --bootstrap-server localhost:9092 \
  --group order-processor

# Terminal 3: Produce messages, observe distribution
kafka-console-producer --topic orders \
  --bootstrap-server localhost:9092

# Check consumer group status
kafka-consumer-groups --describe --group order-processor \
  --bootstrap-server localhost:9092
```

### Exercise 2: Python Consumer

```python
from confluent_kafka import Consumer

config = {
    'bootstrap.servers': 'localhost:9092',
    'group.id': 'order-processor',
    'auto.offset.reset': 'earliest',  # or 'latest'
    'enable.auto.commit': True,
    'auto.commit.interval.ms': 5000,
}

consumer = Consumer(config)
consumer.subscribe(['orders'])

try:
    while True:
        msg = consumer.poll(timeout=1.0)
        if msg is None:
            continue
        if msg.error():
            print(f'Error: {msg.error()}')
            continue

        print(f'Received: {msg.value().decode()} '
              f'from partition {msg.partition()} '
              f'at offset {msg.offset()}')

        # Process message here
        # Offset auto-committed every 5 seconds
finally:
    consumer.close()
```

### Exercise 3: Manual Offset Commit

```python
config = {
    'bootstrap.servers': 'localhost:9092',
    'group.id': 'order-processor',
    'auto.offset.reset': 'earliest',
    'enable.auto.commit': False,  # Manual commit
}

consumer = Consumer(config)
consumer.subscribe(['orders'])

try:
    while True:
        msg = consumer.poll(timeout=1.0)
        if msg is None:
            continue

        # Process message
        process_order(msg.value())

        # Commit AFTER successful processing
        consumer.commit(msg)
finally:
    consumer.close()
```

### Exercise 4: Rebalance Callback

```python
def on_assign(consumer, partitions):
    print(f'Assigned partitions: {partitions}')
    # Initialize state for new partitions

def on_revoke(consumer, partitions):
    print(f'Revoked partitions: {partitions}')
    # Commit offsets, cleanup state
    consumer.commit()

consumer.subscribe(['orders'], on_assign=on_assign, on_revoke=on_revoke)
```

## Consumer Configuration

```properties
# Group coordination
group.id=order-processor
session.timeout.ms=10000          # Time to detect failure
heartbeat.interval.ms=3000        # Heartbeat frequency
max.poll.interval.ms=300000       # Max time between polls

# Offset management
enable.auto.commit=true           # Auto commit offsets
auto.commit.interval.ms=5000      # Commit interval
auto.offset.reset=earliest        # Where to start if no offset

# Fetching
fetch.min.bytes=1                 # Min data to fetch
fetch.max.wait.ms=500             # Max wait for min bytes
max.poll.records=500              # Max records per poll
```

## Assignment Strategies

| Strategy | Description | Use Case |
|----------|-------------|----------|
| Range | Consecutive partitions per consumer | Co-partitioned topics |
| RoundRobin | Partitions distributed evenly | General purpose |
| Sticky | Minimize reassignment on rebalance | Stateful consumers |
| CooperativeSticky | Incremental rebalance | Minimize downtime |

## Interview Questions

- "What happens if a consumer is slow?"
  - Not: "It gets kicked out"
  - But: "If processing takes longer than max.poll.interval.ms (default 5 min), the consumer is considered dead and triggers rebalance. Solution: increase the timeout or process in batches."

- "How do you handle consumer failures?"
  - "Kafka tracks committed offsets. If a consumer crashes, its partitions are reassigned to other consumers who resume from the last committed offset. With auto-commit, there's a window for duplicates."

## Common Pitfalls

1. **More consumers than partitions** - Idle consumers
2. **Auto-commit before processing** - Message loss on crash
3. **Long processing time** - Rebalance triggered
4. **Not closing consumer** - Delayed rebalance
5. **Ignoring rebalance callbacks** - Lost state

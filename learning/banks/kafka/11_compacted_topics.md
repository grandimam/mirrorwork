# Chapter 11: Compacted Topics

## Overview

Log compaction is an alternative retention mechanism that keeps the latest value for each key, making Kafka suitable for changelog and state storage use cases.

## Learning Objectives

By the end of this chapter, you will:

- Understand log compaction
- Use compacted topics for state
- Know when to use compaction vs retention
- Configure compaction settings

## Resources

| Resource | Time |
|----------|------|
| Read: https://kafka.apache.org/documentation/#compaction | 20 min |
| Hands-on: Create and observe compacted topic | 30 min |

## Core Concepts

### Compaction vs Deletion

```
Time-based retention (cleanup.policy=delete):
─────────────────────────────────────────────
Day 1: [A:v1, B:v1, A:v2, C:v1]
Day 7: [A:v1, B:v1, A:v2, C:v1] ← still here
Day 8: [] ← ALL deleted after retention period

Log compaction (cleanup.policy=compact):
────────────────────────────────────────
Before: [A:v1, B:v1, A:v2, C:v1, B:v2, A:v3]

After:  [A:v3, B:v2, C:v1]

Only latest value per key retained
Old values removed, but NEVER time-based deletion
```

### How Compaction Works

```
Log before compaction:
Offset 0: key=A, value=v1   ← will be removed
Offset 1: key=B, value=v1   ← will be removed
Offset 2: key=A, value=v2   ← will be removed
Offset 3: key=C, value=v1   ← kept (latest for C)
Offset 4: key=B, value=v2   ← kept (latest for B)
Offset 5: key=A, value=v3   ← kept (latest for A)

Log after compaction:
Offset 3: key=C, value=v1
Offset 4: key=B, value=v2
Offset 5: key=A, value=v3

Note: offsets are preserved, only duplicates removed
```

### Tombstones (Deletion)

```
To delete a key, send message with null value:

Before: [A:v1, A:v2, A:v3]
Send:   key=A, value=null  ← tombstone

After compaction:
[A:null]  ← tombstone retained for delete.retention.ms
[nothing] ← tombstone eventually removed
```

### Clean vs Dirty Segments

```
Log:
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│   Segment 1 │  │   Segment 2 │  │   Segment 3 │
│   (cleaned) │  │   (dirty)   │  │   (active)  │
└─────────────┘  └─────────────┘  └─────────────┘
                       ↑
                 Cleaner point

Clean: Already compacted, no duplicate keys
Dirty: May have duplicate keys, needs compaction
Active: Currently being written to
```

## Key Questions to Understand

- How is compaction different from deletion?
- What happens to messages with null values?
- When would you use a compacted topic?

## Use Cases for Compacted Topics

| Use Case | Example | Why Compaction |
|----------|---------|----------------|
| Database CDC | User table changes | Latest state per user |
| Configuration | App config updates | Current config value |
| User profiles | Profile updates | Latest profile |
| Materialized views | Aggregation results | Current aggregation |
| KTable backing | Kafka Streams state | State recovery |

## Hands-On Exercises

### Exercise 1: Create Compacted Topic

```bash
# Create compacted topic
kafka-topics --create --topic user-profiles \
  --bootstrap-server localhost:9092 \
  --partitions 3 \
  --config cleanup.policy=compact \
  --config min.cleanable.dirty.ratio=0.1 \
  --config segment.ms=100

# Verify configuration
kafka-configs --describe --topic user-profiles \
  --bootstrap-server localhost:9092
```

### Exercise 2: Observe Compaction

```bash
# Produce multiple values for same key
kafka-console-producer --topic user-profiles \
  --bootstrap-server localhost:9092 \
  --property parse.key=true \
  --property key.separator=:
> user1:{"name": "Alice", "version": 1}
> user2:{"name": "Bob", "version": 1}
> user1:{"name": "Alice Updated", "version": 2}
> user1:{"name": "Alice Final", "version": 3}
> user2:{"name": "Bob Updated", "version": 2}

# Wait for compaction, then consume
kafka-console-consumer --topic user-profiles \
  --bootstrap-server localhost:9092 \
  --from-beginning \
  --property print.key=true

# Should see only latest values per key
```

### Exercise 3: Delete with Tombstone

```bash
# Send tombstone (null value)
kafka-console-producer --topic user-profiles \
  --bootstrap-server localhost:9092 \
  --property parse.key=true \
  --property key.separator=: \
  --property null.marker=NULL
> user1:NULL

# After compaction, user1 will be deleted
```

### Exercise 4: Python Compacted Topic Client

```python
from confluent_kafka import Producer, Consumer
import json

# Producer: update user profile
def update_profile(user_id: str, profile: dict):
    producer.produce(
        'user-profiles',
        key=user_id.encode(),
        value=json.dumps(profile).encode()
    )
    producer.flush()

# Producer: delete user profile
def delete_profile(user_id: str):
    producer.produce(
        'user-profiles',
        key=user_id.encode(),
        value=None  # Tombstone
    )
    producer.flush()

# Consumer: build local state from compacted topic
def load_profiles() -> dict:
    profiles = {}

    consumer = Consumer({
        'bootstrap.servers': 'localhost:9092',
        'group.id': 'profile-loader',
        'auto.offset.reset': 'earliest',
        'enable.auto.commit': False,
    })

    consumer.subscribe(['user-profiles'])

    # Read to end
    while True:
        msg = consumer.poll(1.0)
        if msg is None:
            # Check if we've reached the end
            positions = consumer.position(consumer.assignment())
            end_offsets = consumer.get_watermark_offsets(consumer.assignment()[0])
            if all(p.offset >= end_offsets[1] for p in positions):
                break
            continue

        if msg.error():
            continue

        key = msg.key().decode()
        if msg.value() is None:
            # Tombstone - delete
            profiles.pop(key, None)
        else:
            # Update
            profiles[key] = json.loads(msg.value())

    consumer.close()
    return profiles
```

## Compaction Configuration

```properties
# Enable compaction
cleanup.policy=compact

# Or both (compact then delete after retention)
cleanup.policy=compact,delete

# Trigger compaction when 50% of log is dirty
min.cleanable.dirty.ratio=0.5

# Minimum time before message can be compacted
min.compaction.lag.ms=0

# How long to retain tombstones
delete.retention.ms=86400000  # 24 hours

# Segment settings
segment.ms=604800000          # 7 days
segment.bytes=1073741824      # 1GB

# Cleaner threads (broker level)
log.cleaner.threads=1
log.cleaner.io.max.bytes.per.second=unlimited
```

### Compaction Guarantees

```
1. Messages with same key are reduced to latest
2. Ordering within key is preserved
3. Offsets are never reused
4. Active segment is never compacted
5. Tombstones retained for delete.retention.ms

NOT guaranteed:
- When compaction happens (background process)
- Exact timing of duplicate removal
```

## Compaction vs Time Retention

| Aspect | Compaction | Time Retention |
|--------|-----------|----------------|
| Space | Grows with unique keys | Grows with time |
| Oldest message | Kept forever (if latest) | Deleted after retention |
| Use case | State, changelog | Events, logs |
| Recovery | Full state available | Limited history |
| Key required | Yes | No |

## Interview Questions

- "When would you use a compacted topic?"
  - Not: "When you want to save space"
  - But: "When I need to maintain current state - like database CDC where I want the latest row value, or Kafka Streams state stores. Consumers can rebuild complete state by reading from beginning."

- "How does Kafka Streams use compacted topics?"
  - "KTables are backed by compacted topics. State stores are persisted to changelog topics with compaction. On restart, Streams can restore state by reading the compacted changelog."

- "What happens if you never send a tombstone?"
  - "The key exists forever. Unlike time-based retention, compacted topics keep at least one message per key indefinitely. For user deletion (GDPR), you must send tombstones."

## Common Pitfalls

1. **Forgetting tombstones** - Keys never deleted
2. **Too high dirty ratio** - Compaction rarely runs
3. **No key in messages** - Can't compact
4. **Expecting immediate compaction** - It's async
5. **Large messages** - Compaction copies data, memory pressure

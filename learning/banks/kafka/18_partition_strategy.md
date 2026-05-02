# Chapter 18: Partition Strategy

## Overview

Partition strategy determines data distribution, parallelism, and ordering guarantees. Poor partition design leads to hot spots, underutilized consumers, and lost ordering guarantees.

## Learning Objectives

By the end of this chapter, you will:

- Choose partition count
- Design partition keys
- Handle hot partitions
- Understand partition assignment strategies

## Resources

| Resource | Time |
|----------|------|
| Read: Kafka partitioning best practices | 30 min |
| Hands-on: Test partition key designs | 30 min |

## Core Concepts

### Partition Count Decision

```
Factors to consider:

1. Throughput needed
   - Each partition can handle ~10 MB/s write
   - More partitions = more parallel writes

2. Consumer parallelism
   - Partitions >= consumer count
   - Extra partitions allow scaling

3. Ordering requirements
   - Fewer partitions = simpler ordering
   - Can only order within partition

4. Overhead
   - Each partition = memory on broker
   - Each partition = open files
   - Each partition = slower rebalancing

Starting formula:
max(throughput_mb_s / 10, expected_consumers) × 2
```

### Partition Key Design

```python
# GOOD: Even distribution, maintains order per entity
producer.produce('orders', key=order.customer_id, value=order)
# Customer A's orders always go to same partition = ordered

# GOOD: Order ID for even distribution
producer.produce('orders', key=order.order_id, value=order)
# Orders distributed evenly, but no per-customer ordering

# BAD: Null key (round-robin)
producer.produce('orders', key=None, value=order)
# No ordering guarantees at all

# BAD: Single key
producer.produce('orders', key='all', value=order)
# ALL messages to one partition = no parallelism

# BAD: Hot key
producer.produce('orders', key='amazon', value=order)
# If Amazon is 50% of orders, one partition overloaded
```

### Partitioner Behavior

```
Default Partitioner:
key present → hash(key) % num_partitions → partition
key absent  → round-robin (sticky partitioning in newer versions)

Murmur2 hash used by default:
same key → always same partition
different keys → distributed across partitions
```

## Key Questions to Understand

- How do you decide partition count?
- What causes hot partitions?
- Can you add partitions later?

## Hands-On Exercises

### Exercise 1: Observe Partition Distribution

```python
from confluent_kafka import Producer
from collections import defaultdict

producer = Producer({'bootstrap.servers': 'localhost:9092'})
partition_counts = defaultdict(int)

def delivery_callback(err, msg):
    if not err:
        partition_counts[msg.partition()] += 1

# Produce with different key strategies
for i in range(10000):
    # Strategy 1: User ID
    producer.produce('test', key=f'user-{i % 100}', callback=delivery_callback)

producer.flush()
print("Distribution:", dict(partition_counts))
```

### Exercise 2: Detect Hot Partitions

```bash
# Check partition sizes
kafka-log-dirs --describe --bootstrap-server localhost:9092 \
  --topic-list orders

# Check consumer lag per partition
kafka-consumer-groups --describe --group order-processor \
  --bootstrap-server localhost:9092

# Output shows lag per partition - high lag = hot partition
```

### Exercise 3: Handling Hot Keys

```python
import random

def salted_key(key: str, salt_factor: int = 10) -> str:
    """
    Add salt to spread hot keys across partitions.
    Trade-off: loses per-key ordering.
    """
    salt = hash(key) % salt_factor
    return f"{key}:{salt}"

# Before: All 'amazon' orders go to partition 3
producer.produce('orders', key='amazon', value=order)

# After: 'amazon' orders spread across 10 partitions
producer.produce('orders', key=salted_key('amazon', 10), value=order)

# Result:
# Partition 0: amazon:0
# Partition 1: amazon:1
# ...
# Partition 9: amazon:9
```

### Exercise 4: Custom Partitioner

```python
from confluent_kafka import Producer

def custom_partitioner(key, all_partitions, available_partitions):
    """
    Custom partitioning logic.

    Example: Route VIP customers to dedicated partitions.
    """
    if key and key.startswith(b'vip-'):
        # VIP customers to first 2 partitions
        return hash(key) % 2
    else:
        # Regular customers to remaining partitions
        return 2 + (hash(key) % (len(all_partitions) - 2))

# Note: confluent-kafka doesn't support custom partitioner directly
# Use manual partition assignment instead:

def produce_with_custom_partition(key, value):
    if key.startswith('vip-'):
        partition = hash(key) % 2
    else:
        partition = 2 + (hash(key) % (num_partitions - 2))

    producer.produce('orders', key=key, value=value, partition=partition)
```

### Exercise 5: Partition Reassignment

```bash
# When adding brokers, rebalance partitions

# Step 1: Generate plan
cat > topics.json << EOF
{"topics": [{"topic": "orders"}], "version": 1}
EOF

kafka-reassign-partitions --bootstrap-server localhost:9092 \
  --broker-list "1,2,3,4" \
  --topics-to-move-json-file topics.json \
  --generate > reassignment.json

# Step 2: Review and execute
kafka-reassign-partitions --bootstrap-server localhost:9092 \
  --reassignment-json-file reassignment.json \
  --execute

# Step 3: Monitor progress
kafka-reassign-partitions --bootstrap-server localhost:9092 \
  --reassignment-json-file reassignment.json \
  --verify
```

## Adding Partitions

```bash
# Add partitions to existing topic
kafka-topics --alter --topic orders \
  --partitions 12 \
  --bootstrap-server localhost:9092
```

**WARNING: Adding partitions breaks key-based routing!**

```
Before (6 partitions):
key="user-123" → hash → partition 2

After (12 partitions):
key="user-123" → hash → partition 8

Same key, different partition!
Messages for user-123 now split across partitions 2 AND 8
Ordering guarantee broken for existing keys
```

**Mitigation strategies:**

1. Over-provision partitions initially
2. Create new topic with more partitions, migrate
3. Use sticky partitioning at application level

## Partition Assignment Strategies (Consumer Side)

| Strategy | Behavior | Use Case |
|----------|----------|----------|
| Range | Consecutive partitions per consumer | Co-located topics |
| RoundRobin | Even distribution across consumers | General purpose |
| Sticky | Minimize movement on rebalance | Stateful consumers |
| CooperativeSticky | Incremental rebalance | Production default |

```python
# Configure assignment strategy
consumer = Consumer({
    'bootstrap.servers': 'localhost:9092',
    'group.id': 'my-group',
    'partition.assignment.strategy': 'cooperative-sticky',
})
```

## Interview Questions

- "How do you choose a partition key?"
  - Not: "Use the primary key"
  - But: "It depends on ordering and distribution needs. For per-customer ordering, use customer_id. For even distribution without ordering needs, use a high-cardinality field like order_id. Watch for hot keys that create imbalanced partitions."

- "What do you do about hot partitions?"
  - "First identify the hot key. Options: salt the key to spread load (loses ordering), increase partitions (breaks existing routing), or accept imbalance if ordering is critical. For truly hot keys like 'default' or 'null', fix at the source."

- "Can you reduce partition count?"
  - "No, you can only add partitions. To reduce, create a new topic with fewer partitions and migrate data. This is why it's important to think carefully about initial partition count."

## Common Pitfalls

1. **Starting with too few partitions** - Can't easily add later
2. **Null keys everywhere** - No ordering guarantees
3. **Low cardinality keys** - Hot partitions
4. **Adding partitions to keyed topics** - Breaks routing
5. **Assuming even distribution** - Monitor actual distribution

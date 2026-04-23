# Chapter 2: Core Concepts (Topics, Partitions, Offsets)

## Overview

Understanding topics, partitions, and offsets is fundamental to working with Kafka. These concepts determine how data is organized, distributed, and consumed.

## Learning Objectives

By the end of this chapter, you will:

- Understand topic/partition architecture
- Know how offsets work
- Understand message ordering guarantees
- Design partition strategies

## Resources

| Resource | Time |
|----------|------|
| Read: https://kafka.apache.org/documentation/#intro_concepts_and_terms | 30 min |
| Hands-on: Create topics, explore partitions | 30 min |

## Core Concepts

### Topics

A topic is a category or feed name to which records are published. Topics in Kafka are always multi-subscriber - they can have zero, one, or many consumers.

```
Topic: orders      - All order events
Topic: payments    - All payment events
Topic: users       - All user events
```

### Partitions

Each topic is divided into partitions - ordered, immutable sequences of records.

```
Topic: orders
├── Partition 0: [msg0, msg3, msg6, msg9]  → offset 0,1,2,3
├── Partition 1: [msg1, msg4, msg7]        → offset 0,1,2
└── Partition 2: [msg2, msg5, msg8]        → offset 0,1,2
```

**Why partitions?**

- **Parallelism** - Multiple consumers can read different partitions simultaneously
- **Scalability** - Data spread across multiple brokers
- **Ordering** - Messages within a partition are strictly ordered

### Offsets

Each record within a partition has a unique sequential identifier called an offset.

```
Partition 0: [0] [1] [2] [3] [4] [5] [6] [7]
                          ↑
                    Current consumer offset
```

- Offsets are per-partition
- Consumers track their position via offsets
- Can replay by resetting offset to earlier position

### Message Keys and Partitioning

```
Key: "user-123" → hash → always same partition
No key: round-robin across partitions
```

Messages with the same key always go to the same partition, guaranteeing order for that key.

## Key Questions to Understand

- Why have multiple partitions?
- What ordering guarantees does Kafka provide?
- What happens when you send a message without a key?

## Ordering Guarantees

| Scope | Guarantee |
|-------|-----------|
| Within partition | Total order guaranteed |
| Across partitions | No ordering guarantee |
| Same key | Same partition = ordered |

## Hands-On Exercises

### Exercise 1: Create Topic with Partitions

```bash
# Create topic with partitions
kafka-topics --create --topic orders \
  --bootstrap-server localhost:9092 \
  --partitions 3 --replication-factor 1

# Describe topic
kafka-topics --describe --topic orders \
  --bootstrap-server localhost:9092
```

### Exercise 2: Produce with Keys

```bash
# Produce with keys (same key = same partition)
kafka-console-producer --topic orders \
  --bootstrap-server localhost:9092 \
  --property parse.key=true \
  --property key.separator=:
> user1:order1
> user2:order2
> user1:order3
```

Messages with `user1` key will always go to the same partition.

### Exercise 3: Consume and Check Partition Assignment

```bash
# Check partition assignment
kafka-console-consumer --topic orders \
  --bootstrap-server localhost:9092 \
  --from-beginning \
  --property print.key=true \
  --property print.partition=true
```

### Exercise 4: View Topic Details

```bash
# List all topics
kafka-topics --list --bootstrap-server localhost:9092

# Get topic configuration
kafka-configs --describe --topic orders \
  --bootstrap-server localhost:9092

# Get partition offsets
kafka-run-class kafka.tools.GetOffsetShell \
  --broker-list localhost:9092 \
  --topic orders
```

## Architecture Visualization

```
Producer
    │
    ├── key="user-A" ──► Partition 0 ──► [msg1, msg4, msg7]
    ├── key="user-B" ──► Partition 1 ──► [msg2, msg5, msg8]
    └── key="user-C" ──► Partition 2 ──► [msg3, msg6, msg9]
                              │
                              ▼
                    Consumer Group "processor"
                    ├── Consumer 1 ◄── Partition 0
                    ├── Consumer 2 ◄── Partition 1
                    └── Consumer 3 ◄── Partition 2
```

## Interview Questions

- "How does Kafka ensure message ordering?"
  - Not: "Kafka orders all messages"
  - But: "Kafka guarantees order within a partition only. To maintain order for related events, use the same key (like customer_id) so they go to the same partition."

- "How many partitions should a topic have?"
  - Not: "As many as possible"
  - But: "It depends on throughput needs and consumer parallelism. A good starting point is number of consumers you expect. More partitions = more parallelism but also more overhead."

## Common Pitfalls

1. **Assuming global ordering** - Only partition ordering is guaranteed
2. **Too few partitions** - Limits parallelism
3. **Too many partitions** - Increases memory, slower recovery
4. **Random keys** - Defeats ordering guarantees
5. **Changing partition count** - Breaks key-based routing for existing data

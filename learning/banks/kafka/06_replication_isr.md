# Chapter 6: Replication and ISR

## Overview

Replication is how Kafka achieves fault tolerance and durability. Understanding leader/follower replication and In-Sync Replicas (ISR) is essential for operating Kafka reliably.

## Learning Objectives

By the end of this chapter, you will:

- Understand leader/follower replication
- Know what ISR (In-Sync Replicas) means
- Configure for durability vs availability
- Handle replica failures

## Resources

| Resource | Time |
|----------|------|
| Read: https://kafka.apache.org/documentation/#replication | 30 min |
| Hands-on: Set up replication, kill brokers | 45 min |

## Core Concepts

### Replication Model

```
Topic: orders, partition 0, RF=3

Broker 1 (Leader)    Broker 2 (Follower)    Broker 3 (Follower)
┌────────────────┐   ┌────────────────┐     ┌────────────────┐
│ [0,1,2,3,4,5] │──►│ [0,1,2,3,4,5] │     │ [0,1,2,3,4]   │
│ Leader         │   │ ISR            │     │ Not in ISR    │
└────────────────┘   └────────────────┘     │ (lagging)     │
                                            └────────────────┘
        ▲
        │
    All reads
    and writes
```

**Key points:**
- One leader per partition handles all reads/writes
- Followers replicate from leader
- Clients only talk to leader

### In-Sync Replicas (ISR)

ISR = replicas that are "caught up" with the leader.

A replica falls out of ISR when:
- It hasn't fetched for `replica.lag.time.max.ms` (default 30s)
- It's too far behind (removed in newer versions)

```
Leader: [0,1,2,3,4,5,6,7,8,9]
                           ↑ Leader offset

Follower 1: [0,1,2,3,4,5,6,7,8,9]  ✓ In ISR (caught up)
Follower 2: [0,1,2,3,4,5,6,7]      ✓ In ISR (within lag)
Follower 3: [0,1,2,3]              ✗ Not in ISR (too far behind)
```

### High Water Mark (HWM)

The offset up to which all ISR replicas have replicated.

```
Leader:     [0,1,2,3,4,5,6,7,8,9]
Follower 1: [0,1,2,3,4,5,6,7,8,9]
Follower 2: [0,1,2,3,4,5,6,7]
                           ↑
                    High Water Mark = 7

Consumers can only read up to HWM
Messages 8,9 exist but aren't "committed"
```

### acks and min.insync.replicas

```
acks=all + min.insync.replicas=2:

Producer writes message
    ↓
Leader receives, writes to log
    ↓
Leader waits for ISR replicas to ack
    ↓
If < min.insync.replicas available → Error!
If >= min.insync.replicas ack → Success!
```

## Key Questions to Understand

- What's the difference between replication factor and min.insync.replicas?
- When does a replica fall out of ISR?
- What happens if all ISR replicas are down?

## Critical Settings

```properties
# Topic level
replication.factor=3               # Number of replicas
min.insync.replicas=2              # Min replicas for acks=all

# Broker level
default.replication.factor=3       # Default for new topics
min.insync.replicas=2              # Default for topics

# Producer level (client)
acks=all                           # Wait for all ISR replicas
```

### Durability Matrix

| RF | min.isr | acks | Survives | Trade-off |
|----|---------|------|----------|-----------|
| 3 | 1 | all | 2 failures | May lose data |
| 3 | 2 | all | 1 failure | Blocks writes if 2 down |
| 3 | 2 | 1 | 2 failures | May lose recent data |
| 5 | 3 | all | 2 failures | Higher durability |

## Hands-On Exercises

### Exercise 1: Create Replicated Topic

```bash
# Create topic with replication factor 3
kafka-topics --create --topic orders \
  --bootstrap-server localhost:9092 \
  --replication-factor 3 \
  --partitions 3

# Describe to see replica assignment
kafka-topics --describe --topic orders \
  --bootstrap-server localhost:9092

# Output:
# Topic: orders  Partition: 0  Leader: 1  Replicas: 1,2,3  Isr: 1,2,3
```

### Exercise 2: Monitor ISR

```bash
# Watch ISR changes
kafka-topics --describe --topic orders \
  --bootstrap-server localhost:9092 \
  --under-replicated-partitions

# Check all partition state
kafka-metadata --snapshot /var/lib/kafka/data/__cluster_metadata-0/00000000000000000000.log \
  --command "topic orders"
```

### Exercise 3: Simulate Broker Failure

```bash
# Check current state
kafka-topics --describe --topic orders --bootstrap-server localhost:9092

# Stop one broker
docker stop kafka-2

# Check ISR (should shrink)
kafka-topics --describe --topic orders --bootstrap-server localhost:9092

# Restart broker
docker start kafka-2

# Watch ISR recover
watch -n 1 'kafka-topics --describe --topic orders --bootstrap-server localhost:9092'
```

### Exercise 4: Configure min.insync.replicas

```bash
# Set min.insync.replicas
kafka-configs --alter --topic orders \
  --bootstrap-server localhost:9092 \
  --add-config min.insync.replicas=2

# Test: stop 2 brokers and try to produce with acks=all
kafka-console-producer --topic orders \
  --bootstrap-server localhost:9092 \
  --producer-property acks=all

# Should get NotEnoughReplicasException
```

## Replication Flow

```
1. Producer sends to Leader
   Producer ──────────────────────────► Leader (Broker 1)

2. Leader writes to local log
   Leader: [0,1,2,3,4,NEW]

3. Followers fetch from Leader
   Follower 1 ◄──── fetch ──── Leader
   Follower 2 ◄──── fetch ──── Leader

4. Followers write and ack
   Follower 1: [0,1,2,3,4,NEW] ──► ack
   Follower 2: [0,1,2,3,4,NEW] ──► ack

5. Leader advances HWM, acks producer (if acks=all)
   HWM = 5, Producer ack sent
```

## Interview Questions

- "How does Kafka ensure data isn't lost?"
  - Not: "Replication"
  - But: "Replication factor of 3 with min.insync.replicas=2 and acks=all. This means 2 replicas must acknowledge before producer gets success. Can survive 1 broker failure without data loss."

- "What happens if ISR shrinks to just the leader?"
  - "Depends on min.insync.replicas. If it's 2 and only leader is in ISR, producers with acks=all will fail. The topic is unavailable for writes until another replica catches up."

- "Why would a replica fall out of ISR?"
  - "If it hasn't fetched from leader for replica.lag.time.max.ms (default 30s). This could be due to network issues, disk I/O problems, or broker being overloaded."

## Common Pitfalls

1. **min.insync.replicas > RF** - Topic becomes unavailable
2. **acks=1 with RF=3** - False sense of durability
3. **Not monitoring ISR** - Silent degradation
4. **Ignoring under-replicated partitions** - Data at risk
5. **Same rack for all replicas** - Rack failure loses all

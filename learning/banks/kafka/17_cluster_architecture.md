# Chapter 17: Cluster Architecture

## Overview

Understanding Kafka cluster architecture is essential for designing, deploying, and maintaining production systems. This chapter covers cluster sizing, broker responsibilities, and capacity planning.

## Learning Objectives

By the end of this chapter, you will:

- Design Kafka clusters
- Understand broker responsibilities
- Plan for capacity
- Configure for production workloads

## Resources

| Resource | Time |
|----------|------|
| Read: Kafka cluster sizing | 30 min |
| Hands-on: Set up multi-broker cluster | 45 min |

## Core Concepts

### Cluster Components

```
┌─────────────────────────────────────────────────────────────────┐
│                        Kafka Cluster                            │
│                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐        │
│  │  Broker 1   │    │  Broker 2   │    │  Broker 3   │        │
│  │ Controller  │    │             │    │             │        │
│  │ Partitions: │    │ Partitions: │    │ Partitions: │        │
│  │  orders-0   │    │  orders-1   │    │  orders-2   │        │
│  │  users-1    │    │  users-2    │    │  users-0    │        │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘        │
│         │                   │                   │              │
│         └───────────────────┼───────────────────┘              │
│                             │                                   │
│                    ┌────────┴────────┐                         │
│                    │   ZooKeeper /   │                         │
│                    │     KRaft       │                         │
│                    └─────────────────┘                         │
└─────────────────────────────────────────────────────────────────┘
              ▲                   ▲                   ▲
              │                   │                   │
         Producers            Consumers         Admin Tools
```

### Broker Responsibilities

```
Each Broker:
├── Stores partition data (log segments)
├── Handles produce requests (write)
├── Handles fetch requests (read)
├── Replicates as leader or follower
├── Participates in consumer group coordination
└── Reports metrics

One Broker (Controller):
├── All of the above, plus:
├── Manages partition leadership
├── Handles broker membership
├── Coordinates replica assignment
└── Manages topic creation/deletion
```

### ZooKeeper vs KRaft

```
ZooKeeper Mode (Legacy):
────────────────────────
Kafka Cluster ←──────→ ZooKeeper Ensemble
                       ├── Stores cluster metadata
                       ├── Elects controller
                       └── Manages broker registration

KRaft Mode (New):
─────────────────
Kafka Cluster (self-managing)
├── Controller quorum (Raft consensus)
├── Metadata stored in internal topic
└── No external dependency

KRaft benefits:
- Simpler operations (no ZooKeeper)
- Better scalability
- Faster metadata operations
- Single security model
```

## Cluster Sizing Guidelines

### Broker Count

```
Minimum Production: 3 brokers
- Allows RF=3 for fault tolerance
- Survives single broker failure

Medium Workload: 6-12 brokers
- Higher throughput
- Better load distribution
- More failure tolerance

Large Workload: 20+ brokers
- Very high throughput
- Geographic distribution
- Complex topologies
```

### Partitions per Topic

```
Starting point: num_brokers × 2

Example:
- 6 brokers → start with 12 partitions
- Adjust based on:
  - Throughput needs (more partitions = more parallelism)
  - Consumer count (partitions >= consumers)
  - Message ordering (fewer partitions = simpler ordering)

Limits to consider:
- More partitions = more memory (on broker and clients)
- More partitions = more open files
- More partitions = slower leader election
- Kafka recommendation: < 4000 partitions per broker
```

### Replication Factor

```
RF=1: No fault tolerance (dev only)
RF=2: Survives 1 failure (not recommended)
RF=3: Survives 1-2 failures (production standard)
RF=5: Very high durability (critical data)

Formula:
RF=3 + min.insync.replicas=2 + acks=all
= Survives 1 failure without data loss
= Blocks writes if 2 brokers fail
```

## Hardware Recommendations

### CPU

```
Kafka is I/O bound, not CPU bound
- Modern multi-core processor sufficient
- Compression uses CPU (snappy/lz4 recommended)
- SSL/TLS increases CPU usage

Recommendation: 8-16 cores per broker
```

### Memory

```
JVM Heap: 4-6 GB
- Don't set higher (GC pauses)
- Kafka relies on OS page cache

OS Page Cache: Rest of available RAM
- More cache = better read performance
- Hot data served from memory

Recommendation: 32-64 GB total RAM
- 6 GB for JVM heap
- 26-58 GB for page cache
```

### Disk

```
Type:
- SSD: Better for most workloads
- HDD: OK for high-throughput, sequential access

Configuration:
- JBOD (Just a Bunch Of Disks): Kafka handles disk failures
- RAID-10: More traditional, Kafka less aware of disks
- Avoid RAID-5/6: Write penalty, Kafka replication is better

Sizing:
storage = messages_per_sec × avg_message_size × retention_seconds × RF
        + 10-20% overhead

Example:
10,000 msg/sec × 1KB × 604,800 sec (7 days) × 3 RF
= ~18 TB
```

### Network

```
Bandwidth:
- 1 Gbps minimum
- 10 Gbps recommended for high throughput

Consideration:
- Replication traffic (RF-1 × produce rate)
- Consumer traffic
- Cross-datacenter replication

Example calculation:
- Produce: 100 MB/s
- Replication: 200 MB/s (RF=3, so 2x)
- Consume: 300 MB/s (3 consumer groups)
- Total: 600 MB/s = need 10 Gbps
```

## Hands-On Exercises

### Exercise 1: Multi-Broker Docker Setup

```yaml
# docker-compose.yml
version: '3'
services:
  kafka-1:
    image: confluentinc/cp-kafka:latest
    environment:
      KAFKA_NODE_ID: 1
      KAFKA_PROCESS_ROLES: broker,controller
      KAFKA_LISTENERS: PLAINTEXT://:9092,CONTROLLER://:9093
      KAFKA_CONTROLLER_QUORUM_VOTERS: 1@kafka-1:9093,2@kafka-2:9093,3@kafka-3:9093
    ports:
      - "9092:9092"

  kafka-2:
    image: confluentinc/cp-kafka:latest
    environment:
      KAFKA_NODE_ID: 2
      KAFKA_PROCESS_ROLES: broker,controller
      KAFKA_LISTENERS: PLAINTEXT://:9092,CONTROLLER://:9093
      KAFKA_CONTROLLER_QUORUM_VOTERS: 1@kafka-1:9093,2@kafka-2:9093,3@kafka-3:9093
    ports:
      - "9093:9092"

  kafka-3:
    image: confluentinc/cp-kafka:latest
    environment:
      KAFKA_NODE_ID: 3
      KAFKA_PROCESS_ROLES: broker,controller
      KAFKA_LISTENERS: PLAINTEXT://:9092,CONTROLLER://:9093
      KAFKA_CONTROLLER_QUORUM_VOTERS: 1@kafka-1:9093,2@kafka-2:9093,3@kafka-3:9093
    ports:
      - "9094:9092"
```

### Exercise 2: Check Cluster State

```bash
# List brokers
kafka-metadata --snapshot /path/to/metadata --command "brokers"

# Check controller
kafka-metadata --snapshot /path/to/metadata --command "controller"

# Describe cluster
kafka-broker-api-versions --bootstrap-server localhost:9092

# Check partition distribution
kafka-topics --describe --bootstrap-server localhost:9092
```

### Exercise 3: Partition Reassignment

```bash
# Generate reassignment plan
kafka-reassign-partitions --bootstrap-server localhost:9092 \
  --broker-list "1,2,3" \
  --topics-to-move-json-file topics.json \
  --generate

# Execute reassignment
kafka-reassign-partitions --bootstrap-server localhost:9092 \
  --reassignment-json-file reassignment.json \
  --execute

# Verify completion
kafka-reassign-partitions --bootstrap-server localhost:9092 \
  --reassignment-json-file reassignment.json \
  --verify
```

## Production Configuration

```properties
# broker.properties

# Broker identity
broker.id=1
listeners=PLAINTEXT://:9092
advertised.listeners=PLAINTEXT://broker1.example.com:9092

# Replication
default.replication.factor=3
min.insync.replicas=2
unclean.leader.election.enable=false

# Log settings
log.dirs=/data/kafka-logs
log.retention.hours=168
log.segment.bytes=1073741824
log.retention.check.interval.ms=300000

# Network
num.network.threads=8
num.io.threads=16
socket.send.buffer.bytes=102400
socket.receive.buffer.bytes=102400
socket.request.max.bytes=104857600

# ZooKeeper (if not using KRaft)
zookeeper.connect=zk1:2181,zk2:2181,zk3:2181

# Performance
num.partitions=12
num.replica.fetchers=4
replica.fetch.max.bytes=1048576
```

## Interview Questions

- "How would you size a Kafka cluster?"
  - Not: "More brokers = better"
  - But: "Start with 3 brokers minimum for RF=3. Calculate storage based on throughput × retention × RF. Size memory for page cache (not JVM heap). Network bandwidth must handle produce + replication + consume. Add brokers for throughput or storage, not just availability."

- "How many partitions should a topic have?"
  - "Start with broker_count × 2. More partitions = more parallelism but also more memory, files, and slower rebalancing. Match partition count to expected consumer parallelism. For ordering, use fewer partitions with good key design."

- "ZooKeeper or KRaft?"
  - "KRaft is the future - simpler operations, better scalability, no external dependency. For new clusters, use KRaft if your Kafka version supports it (3.3+). For existing clusters, plan migration but no rush - ZooKeeper still works."

## Common Pitfalls

1. **Under-provisioned disk** - Calculate retention × throughput × RF
2. **Too much JVM heap** - 6GB max, rest for page cache
3. **Single controller** - Use 3 or 5 controller nodes
4. **Too many partitions** - Increases memory, slows recovery
5. **Not monitoring** - Problems invisible until crisis

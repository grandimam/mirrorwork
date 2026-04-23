# Kafka Learning Curriculum

A comprehensive, hands-on learning strategy for Apache Kafka mastery. Focus on understanding, not memorization.

## Quick Start

```bash
# Run Kafka locally (using Redpanda - Kafka-compatible, easier setup)
docker run -d --name redpanda -p 9092:9092 -p 9644:9644 \
  redpandadata/redpanda redpanda start --smp 1 --memory 1G \
  --overprovisioned --kafka-addr 0.0.0.0:9092 \
  --advertise-kafka-addr localhost:9092

# Or use Confluent's all-in-one
docker run -d --name kafka -p 9092:9092 \
  -e KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://localhost:9092 \
  confluentinc/cp-kafka:latest

# Install CLI tools
brew install kafka  # macOS - includes kafka-console-producer/consumer
```

---

## Module 1: Foundations

| Chapter | Topic | Time |
|---------|-------|------|
| [Chapter 1](01_what_is_kafka.md) | What is Kafka and Why It Exists | 1.5 hr |
| [Chapter 2](02_core_concepts.md) | Core Concepts (Topics, Partitions, Offsets) | 1 hr |
| [Chapter 3](03_producers.md) | Producers | 1.5 hr |
| [Chapter 4](04_consumer_groups.md) | Consumer Groups | 1.5 hr |

---

## Module 2: Internals

| Chapter | Topic | Time |
|---------|-------|------|
| [Chapter 5](05_log_storage_segments.md) | Log Storage and Segments | 1 hr |
| [Chapter 6](06_replication_isr.md) | Replication and ISR | 1.5 hr |
| [Chapter 7](07_leader_election.md) | Leader Election | 1 hr |
| [Chapter 8](08_delivery_guarantees.md) | Message Delivery Guarantees | 1 hr |

---

## Module 3: Advanced Concepts

| Chapter | Topic | Time |
|---------|-------|------|
| [Chapter 9](09_exactly_once_semantics.md) | Exactly-Once Semantics | 1 hr |
| [Chapter 10](10_transactions.md) | Transactions | 1.5 hr |
| [Chapter 11](11_compacted_topics.md) | Compacted Topics | 1 hr |
| [Chapter 12](12_schema_registry.md) | Schema Registry | 1.5 hr |

---

## Module 4: Patterns and Use Cases

| Chapter | Topic | Time |
|---------|-------|------|
| [Chapter 13](13_event_sourcing.md) | Event Sourcing | 1.5 hr |
| [Chapter 14](14_cqrs.md) | CQRS with Kafka | 1.5 hr |
| [Chapter 15](15_stream_processing.md) | Stream Processing Basics | 1.5 hr |
| [Chapter 16](16_kafka_vs_rabbitmq.md) | Kafka vs Message Queues (RabbitMQ) | 1 hr |

---

## Module 5: Production Operations

| Chapter | Topic | Time |
|---------|-------|------|
| [Chapter 17](17_cluster_architecture.md) | Cluster Architecture | 1.5 hr |
| [Chapter 18](18_partition_strategy.md) | Partition Strategy | 1 hr |
| [Chapter 19](19_consumer_lag_monitoring.md) | Consumer Lag and Monitoring | 1 hr |
| [Chapter 20](20_failure_recovery.md) | Failure Modes and Recovery | 1.5 hr |

---

## What "Understanding" Looks Like

| Question | Not This | But This |
|----------|----------|----------|
| "Why Kafka over RabbitMQ?" | "Kafka is better for big data" | "I needed multiple consumers to read the same events independently and replay historical data. RabbitMQ deletes after ack, Kafka retains. Also, Kafka's partitioning gives me ordered processing per customer." |
| "How do you handle duplicates?" | "Kafka has exactly-once" | "At-least-once is my default. I make consumers idempotent using a deduplication key stored in Redis or the database. Exactly-once adds overhead and is only for critical paths." |
| "What if a consumer is slow?" | "Add more consumers" | "First check if it's I/O bound or CPU bound. Then either add consumers (up to partition count), increase partitions, or optimize processing. Monitor consumer lag and set alerts." |
| "How many partitions?" | "As many as possible" | "Start with broker_count × 2. More partitions = more parallelism but also more memory, more files, slower rebalancing. I'd measure actual throughput needs." |

---

## Learning Timeline

| Time Available | Focus |
|----------------|-------|
| 1 week | Modules 1-2 (foundations + internals) |
| 2 weeks | Modules 1-4 (add patterns) |
| 3 weeks | Full curriculum including production |

---

## Daily Practice Routine

| Time | Activity |
|------|----------|
| 20 min | Read one chapter section |
| 30 min | Hands-on exercises |
| 10 min | Write down what you learned |

Total: ~1 hour/day

---

## Key Interview Topics by Priority

### Must Know (Asked in most interviews)

1. Topics, Partitions, Offsets - Chapter 2
2. Consumer Groups - Chapter 4
3. Replication and ISR - Chapter 6
4. Delivery Guarantees - Chapter 8
5. Kafka vs RabbitMQ - Chapter 16

### Should Know (Asked in senior interviews)

1. Producer Configuration - Chapter 3
2. Leader Election - Chapter 7
3. Exactly-Once Semantics - Chapter 9
4. Log Compaction - Chapter 11
5. Consumer Lag Monitoring - Chapter 19

### Nice to Know (Bonus points)

1. Transactions - Chapter 10
2. Schema Registry - Chapter 12
3. Stream Processing - Chapter 15
4. Partition Strategy - Chapter 18
5. Failure Recovery - Chapter 20

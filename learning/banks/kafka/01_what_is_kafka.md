# Chapter 1: What is Kafka and Why It Exists

## Overview

Apache Kafka is a distributed event streaming platform originally developed at LinkedIn. Understanding _why_ Kafka exists is crucial before diving into _how_ to use it.

## Learning Objectives

By the end of this chapter, you will:

- Understand Kafka's origin and design goals
- Know when to use Kafka vs traditional message queues
- Understand the log-based architecture
- Be able to articulate Kafka's value proposition in interviews

## Resources

| Resource | Time |
|----------|------|
| Watch: https://www.youtube.com/watch?v=aj9CDZm0Glc | 15 min |
| Read: https://kafka.apache.org/intro | 30 min |
| Read: The Log (Jay Kreps) https://engineering.linkedin.com/distributed-systems/log-what-every-software-engineer-should-know-about-real-time-datas-unifying | 45 min |

## Core Concepts

### The Key Insight

> Kafka is NOT a message queue. It's a distributed commit log. Messages aren't deleted after consumption - they're retained. Multiple consumers can read the same messages independently.

### Why LinkedIn Built Kafka

Traditional message queues like RabbitMQ are optimized for:

- Point-to-point messaging (one consumer per message)
- Message deletion after acknowledgment
- Complex routing patterns
- Request-reply patterns

But they struggle with:

- Multiple independent consumers reading same data
- Replay capability (re-processing historical data)
- High throughput (millions of messages/second)
- Durable, ordered event logs

Kafka fills the gap by providing:

- **Distributed commit log** - Immutable, append-only log
- **Multiple consumers** - Independent consumption of same data
- **Retention** - Messages kept for configurable time, not deleted on read
- **High throughput** - Designed for millions of messages per second
- **Durability** - Replicated across multiple brokers

### Log-Based Architecture

```
Traditional Queue:
Producer → [Queue] → Consumer
                  ↳ Message deleted after ack

Kafka:
Producer → [Log: 0, 1, 2, 3, 4, 5, ...] ← Consumer A (offset 3)
                                        ← Consumer B (offset 1)
                                        ← Consumer C (offset 5)

Messages retained, multiple consumers at different positions
```

## Key Questions to Understand

- Why did LinkedIn build Kafka instead of using existing message queues?
- What makes a log-based system different from a traditional queue?
- Why is Kafka called a "distributed commit log"?

## Hands-On Exercises

### Exercise 1: Setup Kafka Locally

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

### Exercise 2: Create Topic and Produce Messages

```bash
# Create a topic
kafka-topics --create --topic test \
  --bootstrap-server localhost:9092 \
  --partitions 3 --replication-factor 1

# Produce messages
kafka-console-producer --topic test \
  --bootstrap-server localhost:9092
> message 1
> message 2
> message 3
```

### Exercise 3: Consume and Observe Retention

```bash
# Consume from beginning (new terminal)
kafka-console-consumer --topic test \
  --bootstrap-server localhost:9092 \
  --from-beginning

# Consume again - messages still there!
kafka-console-consumer --topic test \
  --bootstrap-server localhost:9092 \
  --from-beginning
```

Notice how the same messages can be read multiple times. This is fundamentally different from traditional message queues.

## Interview Questions

- "Why would you choose Kafka over RabbitMQ?"
  - Not: "Kafka is faster"
  - But: "I needed multiple consumers to read the same events independently and replay historical data. RabbitMQ deletes after ack, Kafka retains. Also, Kafka's partitioning gives me ordered processing per customer."

## When to Use Kafka

**Good Use Cases:**

- Event-driven architectures
- Microservice communication
- Real-time data pipelines
- Change data capture (CDC)
- Activity tracking and audit logs
- Stream processing

**When NOT to Use Kafka:**

- Simple task queues (RabbitMQ simpler)
- Request-reply patterns
- Small scale applications
- When message order doesn't matter and you need complex routing

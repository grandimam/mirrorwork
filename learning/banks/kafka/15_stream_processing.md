# Chapter 15: Stream Processing Basics

## Overview

Stream processing transforms data as it flows through Kafka. Understanding when to use stream processing frameworks vs simple consumers is crucial for building efficient data pipelines.

## Learning Objectives

By the end of this chapter, you will:

- Understand stream processing concepts
- Use Kafka Streams basics
- Know when to use streams vs consumers
- Choose the right stream processing framework

## Resources

| Resource | Time |
|----------|------|
| Read: https://kafka.apache.org/documentation/streams/ | 30 min |
| Hands-on: Build simple stream processing app | 45 min |

## Core Concepts

### Stream Processing vs Batch Processing

```
Batch Processing:
─────────────────
Data → Store → Wait → Process all → Store
        │           │
        │ (hours)   │
        ▼           ▼
     [D1,D2,D3,D4,D5] → Process → Results

Latency: hours
Example: Daily ETL jobs

Stream Processing:
──────────────────
Data → Process immediately → Store
 D1 → Process → Result1
 D2 → Process → Result2
 D3 → Process → Result3
        │
        │ (milliseconds)
        ▼

Latency: milliseconds
Example: Real-time fraud detection
```

### KStream vs KTable

```
KStream: Unbounded sequence of events
─────────────────────────────────────
Each record is independent
INSERT semantics

Timeline: [A:1] [B:2] [A:3] [B:4] [A:5]
All records processed, A has values 1, 3, 5

KTable: Changelog of latest value per key
────────────────────────────────────────
Compacted view
UPSERT semantics

Timeline: [A:1] [B:2] [A:3] [B:4] [A:5]
Current state: A=5, B=4
```

### Stream-Table Duality

```
Stream → Table: Aggregate stream into current state
Table → Stream: Emit changes as events

Orders Stream:                Users Table:
[order1, user=A]             [A: {name: Alice}]
[order2, user=B]             [B: {name: Bob}]
[order3, user=A]

Join: Enrich orders with user info
[{order1, user=A, name=Alice}]
[{order2, user=B, name=Bob}]
[{order3, user=A, name=Alice}]
```

## Key Questions to Understand

- What's the difference between Kafka Streams and a consumer?
- What are KTables and KStreams?
- When would you use Kafka Streams vs Flink/Spark?

## Simple Consumer vs Kafka Streams

```
Simple Consumer (Python/confluent-kafka):
─────────────────────────────────────────
+ Simple to understand
+ Any language
+ Full control
- Manual state management
- Manual scaling/rebalancing
- No built-in windowing

Kafka Streams:
──────────────
+ Built-in state stores
+ Automatic scaling with consumer groups
+ Windowing, joins, aggregations
+ Exactly-once semantics
- JVM only
- Learning curve
```

## Hands-On Exercises

### Exercise 1: Simple Filter (Java/Kotlin)

```java
import org.apache.kafka.streams.KafkaStreams;
import org.apache.kafka.streams.StreamsBuilder;
import org.apache.kafka.streams.kstream.KStream;

Properties props = new Properties();
props.put(StreamsConfig.APPLICATION_ID_CONFIG, "order-filter");
props.put(StreamsConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");

StreamsBuilder builder = new StreamsBuilder();

// Read orders stream
KStream<String, Order> orders = builder.stream("orders");

// Filter high-value orders
KStream<String, Order> highValue = orders
    .filter((key, order) -> order.getAmount() > 1000);

// Write to new topic
highValue.to("high-value-orders");

KafkaStreams streams = new KafkaStreams(builder.build(), props);
streams.start();
```

### Exercise 2: Aggregation

```java
StreamsBuilder builder = new StreamsBuilder();

KStream<String, Order> orders = builder.stream("orders");

// Count orders per customer
KTable<String, Long> orderCounts = orders
    .groupBy((key, order) -> order.getCustomerId())
    .count();

// Write counts to topic
orderCounts.toStream().to("customer-order-counts");
```

### Exercise 3: Windowed Aggregation

```java
import org.apache.kafka.streams.kstream.TimeWindows;
import java.time.Duration;

// Count orders per customer in 5-minute windows
KTable<Windowed<String>, Long> windowedCounts = orders
    .groupBy((key, order) -> order.getCustomerId())
    .windowedBy(TimeWindows.of(Duration.ofMinutes(5)))
    .count();

// Access window info
windowedCounts.toStream()
    .foreach((windowedKey, count) -> {
        String customerId = windowedKey.key();
        long windowStart = windowedKey.window().start();
        long windowEnd = windowedKey.window().end();
        System.out.println(customerId + " had " + count +
            " orders between " + windowStart + " and " + windowEnd);
    });
```

### Exercise 4: Stream-Table Join

```java
// Orders stream
KStream<String, Order> orders = builder.stream("orders");

// Customers table (compacted topic)
KTable<String, Customer> customers = builder.table("customers");

// Enrich orders with customer info
KStream<String, EnrichedOrder> enriched = orders
    .selectKey((key, order) -> order.getCustomerId())  // Re-key by customer
    .join(
        customers,
        (order, customer) -> new EnrichedOrder(order, customer)
    );

enriched.to("enriched-orders");
```

### Exercise 5: Python with Faust (Alternative)

```python
import faust

app = faust.App('order-processor', broker='kafka://localhost:9092')

class Order(faust.Record):
    order_id: str
    customer_id: str
    amount: float

orders_topic = app.topic('orders', value_type=Order)
high_value_topic = app.topic('high-value-orders', value_type=Order)

# Simple filter
@app.agent(orders_topic)
async def process_orders(orders):
    async for order in orders:
        if order.amount > 1000:
            await high_value_topic.send(value=order)

# Windowed count
order_counts = app.Table(
    'order-counts',
    default=int,
).tumbling(timedelta(minutes=5))

@app.agent(orders_topic)
async def count_orders(orders):
    async for order in orders:
        order_counts[order.customer_id] += 1

# Run with: faust -A app worker
```

## Stream Processing Frameworks Comparison

| Framework | Language | Deployment | Use Case |
|-----------|----------|------------|----------|
| Kafka Streams | JVM | Embedded (no cluster) | Microservices |
| Apache Flink | Java/Scala/Python | Cluster | Complex event processing |
| Apache Spark Streaming | Scala/Java/Python | Cluster | ML pipelines, batch+stream |
| Faust | Python | Embedded | Python microservices |
| ksqlDB | SQL | Server | SQL-based streaming |

### When to Use What

```
Simple filtering/transformation → Kafka Streams or Faust
Complex windowing, exactly-once → Kafka Streams or Flink
ML pipelines → Spark Streaming
SQL-based queries → ksqlDB
Already have Flink cluster → Flink
Prototyping → ksqlDB or Faust
```

## State Stores

Kafka Streams maintains state locally:

```
┌──────────────────────────────────────────┐
│           Kafka Streams App              │
│  ┌────────────────────────────────────┐  │
│  │         State Store                │  │
│  │  (RocksDB by default)              │  │
│  │  key → value                       │  │
│  │  customer_A → 15 (order count)     │  │
│  │  customer_B → 8                    │  │
│  └────────────────────────────────────┘  │
│               ↑↓                         │
│  ┌────────────────────────────────────┐  │
│  │      Changelog Topic               │  │
│  │  (for fault tolerance)             │  │
│  └────────────────────────────────────┘  │
└──────────────────────────────────────────┘
```

- State stored locally (fast)
- Backed by changelog topic (recoverable)
- Automatically restored on restart

## Interview Questions

- "When would you use Kafka Streams vs a simple consumer?"
  - Not: "Kafka Streams is more powerful"
  - But: "For simple filtering or transformation, a consumer is fine. Kafka Streams shines when I need stateful operations (aggregations, joins), windowing, or exactly-once semantics. It handles state management and scaling automatically."

- "How does Kafka Streams handle state?"
  - "Local state stores (RocksDB) for fast access, backed by changelog topics for fault tolerance. If instance crashes, new instance rebuilds state from changelog. This gives both performance and durability."

- "Kafka Streams vs Flink?"
  - "Kafka Streams is embedded (no separate cluster), simpler deployment, good for microservices. Flink is more powerful for complex event processing, better for data engineering teams with cluster expertise. Choose based on team skills and use case complexity."

## Common Pitfalls

1. **Stateful operations without understanding state stores** - OOM, slow recovery
2. **Wrong windowing type** - Tumbling vs hopping vs session
3. **Not handling late events** - Grace period needed
4. **Over-engineering** - Simple consumer often sufficient
5. **Ignoring serialization** - Use Avro/Protobuf for evolving schemas

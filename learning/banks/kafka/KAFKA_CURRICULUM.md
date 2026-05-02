# Kafka Learning Curriculum

A comprehensive, hands-on learning strategy for Apache Kafka mastery. Focus on understanding, not memorization.

---

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

### Chapter 1: What is Kafka and Why It Exists

**Learning Objectives**
- Understand Kafka's origin and design goals
- Know when to use Kafka vs traditional message queues
- Understand the log-based architecture

| Resource | Time |
|----------|------|
| Watch: https://www.youtube.com/watch?v=aj9CDZm0Glc | 15 min |
| Read: https://kafka.apache.org/intro | 30 min |
| Read: The Log (Jay Kreps) https://engineering.linkedin.com/distributed-systems/log-what-every-software-engineer-should-know-about-real-time-datas-unifying | 45 min |

**Key Questions to Understand**
- Why did LinkedIn build Kafka instead of using existing message queues?
- What makes a log-based system different from a traditional queue?
- Why is Kafka called a "distributed commit log"?

**The Key Insight**
> Kafka is NOT a message queue. It's a distributed commit log. Messages aren't deleted after consumption - they're retained. Multiple consumers can read the same messages independently.

**Hands-On Exercise**
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

# Consume from beginning (new terminal)
kafka-console-consumer --topic test \
  --bootstrap-server localhost:9092 \
  --from-beginning

# Consume again - messages still there!
kafka-console-consumer --topic test \
  --bootstrap-server localhost:9092 \
  --from-beginning
```

---

### Chapter 2: Core Concepts (Topics, Partitions, Offsets)

**Learning Objectives**
- Understand topic/partition architecture
- Know how offsets work
- Understand message ordering guarantees

| Resource | Time |
|----------|------|
| Read: https://kafka.apache.org/documentation/#intro_concepts_and_terms | 30 min |
| Hands-on: Create topics, explore partitions | 30 min |

**Key Questions to Understand**
- Why have multiple partitions?
- What ordering guarantees does Kafka provide?
- What happens when you send a message without a key?

**Architecture Diagram**
```
Topic: orders
├── Partition 0: [msg0, msg3, msg6, msg9]  → offset 0,1,2,3
├── Partition 1: [msg1, msg4, msg7]        → offset 0,1,2
└── Partition 2: [msg2, msg5, msg8]        → offset 0,1,2

Key: "user-123" → hash → always same partition
No key: round-robin across partitions
```

**Hands-On Exercise**
```bash
# Create topic with partitions
kafka-topics --create --topic orders \
  --bootstrap-server localhost:9092 \
  --partitions 3 --replication-factor 1

# Describe topic
kafka-topics --describe --topic orders \
  --bootstrap-server localhost:9092

# Produce with keys (same key = same partition)
kafka-console-producer --topic orders \
  --bootstrap-server localhost:9092 \
  --property parse.key=true \
  --property key.separator=:
> user1:order1
> user2:order2
> user1:order3  # same partition as order1

# Check partition assignment
kafka-console-consumer --topic orders \
  --bootstrap-server localhost:9092 \
  --from-beginning \
  --property print.key=true \
  --property print.partition=true
```

**Ordering Guarantee**
- Within partition: total order guaranteed
- Across partitions: no ordering guarantee
- Same key = same partition = ordered

---

### Chapter 3: Producers

**Learning Objectives**
- Configure producer for reliability vs performance
- Understand acknowledgment modes
- Handle producer failures

| Resource | Time |
|----------|------|
| Read: https://kafka.apache.org/documentation/#producerconfigs | 30 min |
| Hands-on: Write producer with different configs | 45 min |

**Key Questions to Understand**
- What's the difference between acks=0, 1, and all?
- When would you use async vs sync sending?
- What happens if the broker is unavailable?

**Producer Acks**

| acks | Durability | Latency | Use Case |
|------|------------|---------|----------|
| 0 | None | Lowest | Metrics, logs (loss OK) |
| 1 | Leader only | Medium | Most use cases |
| all (-1) | All replicas | Highest | Critical data |

**Python Producer Example**
```python
from confluent_kafka import Producer

config = {
    'bootstrap.servers': 'localhost:9092',
    'acks': 'all',  # wait for all replicas
    'retries': 3,
    'retry.backoff.ms': 100,
    'enable.idempotence': True,  # exactly-once semantics
}

producer = Producer(config)

def delivery_callback(err, msg):
    if err:
        print(f'Delivery failed: {err}')
    else:
        print(f'Delivered to {msg.topic()}[{msg.partition()}]@{msg.offset()}')

# Send message
producer.produce(
    topic='orders',
    key='user-123',
    value='{"order_id": 1, "amount": 99.99}',
    callback=delivery_callback
)

producer.flush()  # wait for all messages to be delivered
```

**Idempotent Producer**
```python
# Enable exactly-once producer semantics
config = {
    'enable.idempotence': True,  # prevents duplicates on retry
    'acks': 'all',               # required for idempotence
    'max.in.flight.requests.per.connection': 5,  # max with idempotence
}
```

---

### Chapter 4: Consumer Groups

**Learning Objectives**
- Understand consumer group coordination
- Know partition assignment strategies
- Handle rebalancing

| Resource | Time |
|----------|------|
| Read: https://kafka.apache.org/documentation/#intro_consumers | 30 min |
| Watch: Consumer groups explained | 20 min |
| Hands-on: Multi-consumer setup | 45 min |

**Key Questions to Understand**
- What happens if you have more consumers than partitions?
- How does Kafka track what each consumer has read?
- What triggers a rebalance?

**Consumer Group Diagram**
```
Topic: orders (3 partitions)
├── Partition 0 ─────► Consumer 1 ┐
├── Partition 1 ─────► Consumer 2 ├── group: "order-processor"
└── Partition 2 ─────► Consumer 3 ┘

Add Consumer 4: no partition, sits idle
Remove Consumer 3: P2 reassigned to Consumer 1 or 2
```

**Hands-On Exercise**
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

**Python Consumer Example**
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

---

## Module 2: Internals

### Chapter 5: Log Storage and Segments

**Learning Objectives**
- Understand how Kafka stores messages on disk
- Know segment files and indexes
- Understand retention policies

| Resource | Time |
|----------|------|
| Read: Kafka storage internals | 30 min |
| Hands-on: Explore log directory structure | 30 min |

**Key Questions to Understand**
- Why does Kafka write sequentially to disk?
- What's in a segment file vs an index file?
- How does log compaction work?

**Log Directory Structure**
```
/var/lib/kafka/data/orders-0/
├── 00000000000000000000.log    # messages
├── 00000000000000000000.index  # offset index
├── 00000000000000000000.timeindex  # timestamp index
├── 00000000000000005000.log    # new segment after 5000
└── leader-epoch-checkpoint
```

**Retention Policies**
```properties
# Time-based (default 7 days)
log.retention.hours=168
log.retention.minutes=
log.retention.ms=

# Size-based
log.retention.bytes=1073741824  # 1GB per partition

# Segment size (when to roll new segment)
log.segment.bytes=1073741824    # 1GB
log.segment.ms=604800000        # 7 days
```

---

### Chapter 6: Replication and ISR

**Learning Objectives**
- Understand leader/follower replication
- Know what ISR (In-Sync Replicas) means
- Configure for durability vs availability

| Resource | Time |
|----------|------|
| Read: https://kafka.apache.org/documentation/#replication | 30 min |
| Hands-on: Set up replication, kill brokers | 45 min |

**Key Questions to Understand**
- What's the difference between replication factor and min.insync.replicas?
- When does a replica fall out of ISR?
- What happens if all ISR replicas are down?

**Replication Diagram**
```
Topic: orders, partition 0, RF=3

Broker 1 (Leader)    Broker 2 (Follower)    Broker 3 (Follower)
┌────────────────┐   ┌────────────────┐     ┌────────────────┐
│ [0,1,2,3,4,5] │──►│ [0,1,2,3,4,5] │     │ [0,1,2,3,4]   │
│ Leader         │   │ ISR            │     │ Not in ISR    │
└────────────────┘   └────────────────┘     │ (lagging)     │
                                            └────────────────┘
```

**Critical Settings**
```properties
# Replication factor when creating topic
kafka-topics --create --topic orders \
  --replication-factor 3 \
  --partitions 3

# Minimum replicas that must acknowledge
min.insync.replicas=2

# With acks=all, this means:
# - 2 replicas must confirm write
# - Survives 1 broker failure
# - Blocks writes if only 1 replica available
```

---

### Chapter 7: Leader Election

**Learning Objectives**
- Understand how leaders are elected
- Know the role of the controller
- Handle leader failures

| Resource | Time |
|----------|------|
| Read: Kafka controller deep dive | 30 min |

**Key Questions to Understand**
- Who decides which broker is the leader?
- What happens during leader election?
- What's "unclean leader election" and why is it dangerous?

**Leader Election**
```
1. Controller (one broker) monitors all brokers via ZooKeeper/KRaft
2. When leader fails, controller elects new leader from ISR
3. New leader becomes responsible for reads/writes
4. Followers now replicate from new leader

Time: typically < 1 second for failover
```

**Unclean Leader Election**
```properties
# Allow non-ISR replica to become leader (risk of data loss)
unclean.leader.election.enable=false  # recommended

# If true: availability over durability
# If false: durability over availability (may become unavailable)
```

---

### Chapter 8: Message Delivery Guarantees

**Learning Objectives**
- Understand at-most-once, at-least-once, exactly-once
- Configure for your requirements
- Handle duplicate messages

| Resource | Time |
|----------|------|
| Read: Kafka delivery semantics | 30 min |

**Key Questions to Understand**
- What does "exactly-once" really mean in Kafka?
- How do you handle duplicates with at-least-once?
- When is at-most-once acceptable?

**Delivery Guarantees**

| Guarantee | How to Achieve | Use Case |
|-----------|---------------|----------|
| At-most-once | Auto-commit before processing | Metrics, logs |
| At-least-once | Commit after processing | Most applications |
| Exactly-once | Idempotent producer + transactions | Financial, critical |

**At-Least-Once Pattern**
```python
consumer = Consumer({
    'enable.auto.commit': False,  # manual commit
})

while True:
    msg = consumer.poll(1.0)
    if msg is None:
        continue

    # Process message
    process(msg)

    # Commit AFTER successful processing
    consumer.commit(msg)
```

**Handling Duplicates (Idempotency)**
```python
def process_order(order):
    order_id = order['order_id']

    # Check if already processed (idempotency key)
    if redis.sismember('processed_orders', order_id):
        return  # skip duplicate

    # Process order
    db.execute("INSERT INTO orders ...")

    # Mark as processed
    redis.sadd('processed_orders', order_id)
```

---

## Module 3: Advanced Concepts

### Chapter 9: Exactly-Once Semantics

**Learning Objectives**
- Understand idempotent producers
- Use transactions for exactly-once
- Know the limitations

| Resource | Time |
|----------|------|
| Read: https://www.confluent.io/blog/exactly-once-semantics-are-possible-heres-how-apache-kafka-does-it/ | 30 min |

**Key Questions to Understand**
- What's the difference between idempotent producer and transactions?
- What's the performance impact of exactly-once?
- When do you actually need exactly-once?

**Idempotent Producer**
```python
# Prevents duplicates from producer retries
producer = Producer({
    'enable.idempotence': True,
    'acks': 'all',
})
```

**Transactional Producer**
```python
producer = Producer({
    'transactional.id': 'my-transactional-producer',
    'enable.idempotence': True,
})

producer.init_transactions()

try:
    producer.begin_transaction()

    producer.produce('topic1', value='msg1')
    producer.produce('topic2', value='msg2')

    producer.commit_transaction()
except Exception as e:
    producer.abort_transaction()
```

---

### Chapter 10: Transactions

**Learning Objectives**
- Use read-process-write patterns
- Consume and produce atomically
- Handle transaction failures

**Read-Process-Write Pattern**
```python
# Atomic: consume from input, produce to output
producer = Producer({'transactional.id': 'processor-1'})
consumer = Consumer({
    'group.id': 'processor-group',
    'isolation.level': 'read_committed',  # only see committed
})

producer.init_transactions()

while True:
    msgs = consumer.consume(100, timeout=1.0)

    producer.begin_transaction()
    try:
        for msg in msgs:
            result = process(msg)
            producer.produce('output-topic', value=result)

        # Commit offsets as part of transaction
        producer.send_offsets_to_transaction(
            consumer.position(consumer.assignment()),
            consumer.consumer_group_metadata()
        )

        producer.commit_transaction()
    except Exception:
        producer.abort_transaction()
```

---

### Chapter 11: Compacted Topics

**Learning Objectives**
- Understand log compaction
- Use compacted topics for state
- Know when to use compaction vs retention

| Resource | Time |
|----------|------|
| Read: https://kafka.apache.org/documentation/#compaction | 20 min |

**Key Questions to Understand**
- How is compaction different from deletion?
- What happens to messages with null values?
- When would you use a compacted topic?

**Compaction Behavior**
```
Before compaction:
key=A:v1, key=B:v1, key=A:v2, key=C:v1, key=B:v2, key=A:v3

After compaction:
key=A:v3, key=B:v2, key=C:v1

Only latest value per key retained
```

**Use Cases**
- Database CDC (change data capture)
- User profiles / settings
- Configuration distribution
- Materialized views

**Create Compacted Topic**
```bash
kafka-topics --create --topic user-profiles \
  --bootstrap-server localhost:9092 \
  --config cleanup.policy=compact \
  --config min.cleanable.dirty.ratio=0.5 \
  --config segment.ms=100
```

**Delete a Key**
```python
# Send null value (tombstone)
producer.produce('user-profiles', key='user-123', value=None)
```

---

### Chapter 12: Schema Registry

**Learning Objectives**
- Understand schema evolution
- Use Avro/Protobuf with Kafka
- Configure compatibility modes

| Resource | Time |
|----------|------|
| Read: https://docs.confluent.io/platform/current/schema-registry/index.html | 30 min |

**Key Questions to Understand**
- Why not just use JSON?
- What's schema compatibility and why does it matter?
- How does the registry prevent breaking changes?

**Compatibility Modes**

| Mode | Adding Fields | Removing Fields | Use Case |
|------|--------------|-----------------|----------|
| BACKWARD | New optional OK | Old optional OK | Consumers first |
| FORWARD | Old optional OK | New optional OK | Producers first |
| FULL | Optional only | Optional only | Both directions |
| NONE | Anything | Anything | Development |

**Avro Example**
```python
from confluent_kafka import SerializingProducer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer

schema_str = """
{
  "type": "record",
  "name": "Order",
  "fields": [
    {"name": "order_id", "type": "string"},
    {"name": "amount", "type": "double"},
    {"name": "customer_id", "type": "string"}
  ]
}
"""

schema_registry = SchemaRegistryClient({'url': 'http://localhost:8081'})
avro_serializer = AvroSerializer(schema_registry, schema_str)

producer = SerializingProducer({
    'bootstrap.servers': 'localhost:9092',
    'value.serializer': avro_serializer,
})

producer.produce('orders', value={'order_id': '123', 'amount': 99.99, 'customer_id': 'C1'})
```

---

## Module 4: Patterns and Use Cases

### Chapter 13: Event Sourcing

**Learning Objectives**
- Understand event sourcing pattern
- Build event-sourced systems with Kafka
- Handle event replay and snapshots

**Key Questions to Understand**
- How is event sourcing different from CRUD?
- Why is Kafka a good fit for event sourcing?
- How do you rebuild state from events?

**Event Sourcing Pattern**
```
Traditional CRUD:
UPDATE accounts SET balance = 150 WHERE id = 1

Event Sourcing:
Event 1: AccountCreated { id: 1, balance: 0 }
Event 2: MoneyDeposited { id: 1, amount: 100 }
Event 3: MoneyDeposited { id: 1, amount: 100 }
Event 4: MoneyWithdrawn { id: 1, amount: 50 }

Current state = replay all events = balance: 150
```

**Implementation Pattern**
```python
# Event store (compacted topic for latest state, regular for events)
EVENT_TOPIC = 'account-events'  # all events, time-retained
STATE_TOPIC = 'account-state'   # compacted, latest state

def handle_command(command):
    # Load current state
    state = load_state(command.account_id)

    # Validate and create event
    if command.type == 'withdraw':
        if state.balance < command.amount:
            raise InsufficientFunds()
        event = MoneyWithdrawn(command.account_id, command.amount)

    # Publish event
    producer.produce(EVENT_TOPIC, key=command.account_id, value=event)

    # Update state (or let consumer do it)
    new_state = apply_event(state, event)
    producer.produce(STATE_TOPIC, key=command.account_id, value=new_state)
```

---

### Chapter 14: CQRS with Kafka

**Learning Objectives**
- Separate read and write models
- Build read-optimized views
- Handle eventual consistency

**CQRS Architecture**
```
Commands ──► Write Model ──► Kafka ──► Read Model ──► Queries
                │                          │
                ▼                          ▼
           PostgreSQL              Elasticsearch
           (source of truth)       (search-optimized)
```

**Implementation**
```python
# Write side: validate and publish events
def create_order(order):
    validate(order)
    event = OrderCreated(order)
    producer.produce('orders', key=order.id, value=event)

# Read side: consume events, build view
def orders_consumer():
    for msg in consumer:
        event = deserialize(msg.value)
        if event.type == 'OrderCreated':
            elasticsearch.index('orders', event.order)
        elif event.type == 'OrderShipped':
            elasticsearch.update('orders', event.order_id, {'status': 'shipped'})
```

---

### Chapter 15: Stream Processing Basics

**Learning Objectives**
- Understand stream processing concepts
- Use Kafka Streams basics
- Know when to use streams vs consumers

| Resource | Time |
|----------|------|
| Read: https://kafka.apache.org/documentation/streams/ | 30 min |

**Key Questions to Understand**
- What's the difference between Kafka Streams and a consumer?
- What are KTables and KStreams?
- When would you use Kafka Streams vs Flink/Spark?

**Kafka Streams Concepts**
```
KStream: unbounded sequence of events
  - Each record is independent
  - INSERT semantics

KTable: changelog of latest value per key
  - Compacted view
  - UPSERT semantics

Stream-Table Join:
  - Enrich events with lookup data
  - Orders stream + Customers table
```

**Simple Stream Processing**
```java
StreamsBuilder builder = new StreamsBuilder();

// Read orders stream
KStream<String, Order> orders = builder.stream("orders");

// Filter high-value orders
KStream<String, Order> highValue = orders
    .filter((key, order) -> order.getAmount() > 1000);

// Write to new topic
highValue.to("high-value-orders");

// Aggregate by customer
KTable<String, Long> orderCounts = orders
    .groupBy((key, order) -> order.getCustomerId())
    .count();

orderCounts.toStream().to("customer-order-counts");
```

---

### Chapter 16: Kafka vs Message Queues (RabbitMQ)

**Learning Objectives**
- Know when to use Kafka vs RabbitMQ
- Understand architectural differences
- Choose the right tool

**Comparison**

| Aspect | Kafka | RabbitMQ |
|--------|-------|----------|
| Model | Log (pull) | Queue (push) |
| Message retention | Retained after consume | Deleted after ack |
| Consumer count | Many independent consumers | Competing consumers |
| Replay | Yes, from any offset | No |
| Ordering | Per partition | Per queue |
| Routing | Partition key | Exchange/routing key |
| Protocol | Custom binary | AMQP |
| Throughput | Millions/sec | Thousands/sec |

**When to Use What**

| Use Case | Choice | Why |
|----------|--------|-----|
| Event sourcing | Kafka | Need replay, retention |
| Task queue | RabbitMQ | Delete after processing |
| Multiple consumers same data | Kafka | Independent consumption |
| Complex routing | RabbitMQ | Exchange patterns |
| Audit log | Kafka | Immutable log |
| Request-reply | RabbitMQ | Built-in reply-to |
| High throughput | Kafka | Designed for scale |

**The Right Answer in Interviews**
> "It depends on the use case. For event-driven architectures where multiple services need the same events independently, or when I need replay capability, I'd choose Kafka. For task queues where messages should be deleted after processing, or when I need complex routing patterns, RabbitMQ is simpler."

---

## Module 5: Production Operations

### Chapter 17: Cluster Architecture

**Learning Objectives**
- Design Kafka clusters
- Understand broker responsibilities
- Plan for capacity

| Resource | Time |
|----------|------|
| Read: Kafka cluster sizing | 30 min |

**Cluster Sizing Guidelines**
```
Brokers:
- Minimum 3 for production (RF=3)
- Typically 6-12 for medium workloads
- Scale based on throughput and storage

Partitions per topic:
- Start with #brokers × 2
- More partitions = more parallelism
- But: more partitions = more memory, slower recovery

Replication factor:
- RF=3 for production
- Survives 2 broker failures (with min.isr=2, survives 1)
```

**Broker Hardware**
```
CPU: Modern multi-core (Kafka is I/O bound)
Memory: 64GB+ (OS page cache is key)
Disk: SSD or fast HDD, JBOD OK
Network: 10 Gbps+

JVM heap: 4-6GB (rest for page cache!)
```

---

### Chapter 18: Partition Strategy

**Learning Objectives**
- Choose partition count
- Design partition keys
- Handle hot partitions

**Key Questions to Understand**
- How do you decide partition count?
- What causes hot partitions?
- Can you add partitions later?

**Partition Key Design**
```python
# Good: even distribution, maintains order per entity
producer.produce('orders', key=order.customer_id, value=order)

# Bad: hot partition (all nulls go to same partition)
producer.produce('orders', key=None, value=order)  # round-robin
producer.produce('orders', key='all', value=order)  # single partition!

# Bad: hot key (one popular customer)
producer.produce('orders', key='amazon', value=order)  # overloaded
```

**Handling Hot Partitions**
```python
# Add salt to spread hot keys
def salted_key(key, salt_factor=10):
    salt = hash(key) % salt_factor
    return f"{key}:{salt}"

# Partition 0: amazon:0
# Partition 1: amazon:1
# ...spreads load but loses ordering
```

---

### Chapter 19: Consumer Lag and Monitoring

**Learning Objectives**
- Monitor consumer lag
- Set up alerting
- Debug slow consumers

| Resource | Time |
|----------|------|
| Hands-on: Set up lag monitoring | 30 min |

**Consumer Lag**
```bash
# Check consumer lag
kafka-consumer-groups --describe --group order-processor \
  --bootstrap-server localhost:9092

# Output:
GROUP           TOPIC    PARTITION  CURRENT-OFFSET  LOG-END-OFFSET  LAG
order-processor orders   0          100             150             50
order-processor orders   1          95              95              0
order-processor orders   2          80              200             120
```

**Key Metrics to Monitor**
- Consumer lag (messages behind)
- Under-replicated partitions
- Active controller count (should be 1)
- Request latency (produce/fetch)
- Bytes in/out per second
- Disk usage per broker

**Lag Alert Thresholds**
```
Warning: lag > 1000 messages or > 1 minute
Critical: lag > 10000 messages or > 5 minutes
```

---

### Chapter 20: Failure Modes and Recovery

**Learning Objectives**
- Handle common failures
- Plan disaster recovery
- Test failure scenarios

**Failure Scenarios**

| Scenario | Impact | Recovery |
|----------|--------|----------|
| Single broker failure | Partitions failover | Automatic (if RF>1) |
| All brokers down | Complete outage | Restart cluster |
| Controller failure | New controller elected | Automatic |
| Disk failure | Partition data loss | Replace, replicate |
| Network partition | Split brain risk | Configure min.isr |
| Consumer crash | Rebalance, reprocess | Automatic |
| Producer timeout | Retry or error | Application handles |

**Disaster Recovery**
```bash
# Backup topics using MirrorMaker 2
# Source cluster → Target cluster

# Or use Confluent Replicator

# Manual: consume all, produce to new cluster
kafka-console-consumer --topic orders \
  --bootstrap-server source:9092 \
  --from-beginning | \
kafka-console-producer --topic orders \
  --bootstrap-server target:9092
```

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

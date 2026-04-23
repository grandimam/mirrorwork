# Chapter 10: Transactions

## Overview

Kafka transactions enable atomic read-process-write patterns across topics and partitions. This chapter dives deeper into transaction mechanics and patterns.

## Learning Objectives

By the end of this chapter, you will:

- Use read-process-write patterns
- Consume and produce atomically
- Handle transaction failures
- Design transactional applications

## Resources

| Resource | Time |
|----------|------|
| Read: Kafka transactions deep dive | 30 min |
| Hands-on: Implement transactional processing | 45 min |

## Core Concepts

### Read-Process-Write Pattern

The classic exactly-once pattern:

```
┌─────────────────────────────────────────────────────────────┐
│                     TRANSACTION                              │
│                                                              │
│  ┌──────────┐     ┌─────────┐     ┌──────────┐             │
│  │  Consume │ ──► │ Process │ ──► │ Produce  │             │
│  │  offset  │     │         │     │ to output│             │
│  └──────────┘     └─────────┘     └──────────┘             │
│       │                                 │                   │
│       └──────── Atomic commit ──────────┘                   │
│                                                              │
└─────────────────────────────────────────────────────────────┘

If any part fails → entire transaction aborts
Offsets not committed, output not written
Consumer will re-read input on restart
```

### Transaction States

```
                    ┌─────────────┐
                    │   Empty     │
                    └──────┬──────┘
                           │ begin_transaction()
                           ▼
                    ┌─────────────┐
                    │  In-flight  │ ◄──────────────┐
                    └──────┬──────┘                │
                           │                        │
              ┌────────────┼────────────┐          │
              │            │            │          │
              ▼            ▼            ▼          │
       ┌──────────┐ ┌──────────┐ ┌──────────┐    │
       │Committing│ │ Aborting │ │  Error   │    │
       └────┬─────┘ └────┬─────┘ └────┬─────┘    │
            │            │            │          │
            ▼            ▼            │          │
       ┌──────────┐ ┌──────────┐      │          │
       │Committed │ │ Aborted  │ ─────┴──────────┘
       └──────────┘ └──────────┘     (retry)
```

## Hands-On Exercises

### Exercise 1: Complete Transactional Application

```python
from confluent_kafka import Consumer, Producer, KafkaException
import json

class TransactionalProcessor:
    def __init__(self, input_topic: str, output_topic: str, group_id: str):
        self.input_topic = input_topic
        self.output_topic = output_topic

        self.consumer = Consumer({
            'bootstrap.servers': 'localhost:9092',
            'group.id': group_id,
            'isolation.level': 'read_committed',
            'enable.auto.commit': False,
            'auto.offset.reset': 'earliest',
        })

        self.producer = Producer({
            'bootstrap.servers': 'localhost:9092',
            'transactional.id': f'{group_id}-producer',
        })

    def start(self):
        self.consumer.subscribe([self.input_topic])
        self.producer.init_transactions()

        try:
            while True:
                self.process_batch()
        finally:
            self.consumer.close()

    def process_batch(self):
        msgs = self.consumer.consume(100, timeout=1.0)
        if not msgs:
            return

        self.producer.begin_transaction()

        try:
            for msg in msgs:
                if msg.error():
                    continue

                # Process
                input_data = json.loads(msg.value())
                output_data = self.transform(input_data)

                # Produce to output
                self.producer.produce(
                    self.output_topic,
                    key=msg.key(),
                    value=json.dumps(output_data).encode()
                )

            # Commit offsets within transaction
            self.producer.send_offsets_to_transaction(
                self.consumer.position(self.consumer.assignment()),
                self.consumer.consumer_group_metadata()
            )

            self.producer.commit_transaction()

        except KafkaException as e:
            self.producer.abort_transaction()
            raise

    def transform(self, data: dict) -> dict:
        # Your transformation logic
        return {'processed': data, 'timestamp': time.time()}


# Usage
processor = TransactionalProcessor(
    input_topic='orders',
    output_topic='processed-orders',
    group_id='order-processor'
)
processor.start()
```

### Exercise 2: Multi-Topic Transaction

```python
def process_order_transaction(order):
    producer.begin_transaction()

    try:
        # Write to multiple topics atomically
        producer.produce('orders', value=json.dumps(order))
        producer.produce('inventory-updates', value=json.dumps({
            'product_id': order['product_id'],
            'delta': -order['quantity']
        }))
        producer.produce('notifications', value=json.dumps({
            'user_id': order['user_id'],
            'message': 'Order placed'
        }))

        producer.commit_transaction()

    except Exception as e:
        producer.abort_transaction()
        raise
```

### Exercise 3: Handling Transactional Failures

```python
from confluent_kafka import KafkaException
from confluent_kafka.error import KafkaError

def safe_transactional_process():
    while True:
        try:
            msgs = consumer.consume(100, timeout=1.0)
            if not msgs:
                continue

            producer.begin_transaction()

            for msg in msgs:
                # Process and produce
                pass

            producer.send_offsets_to_transaction(
                consumer.position(consumer.assignment()),
                consumer.consumer_group_metadata()
            )

            producer.commit_transaction()

        except KafkaException as e:
            error = e.args[0]

            if error.retriable():
                # Retriable error - abort and retry
                print(f'Retriable error: {error}')
                try:
                    producer.abort_transaction()
                except:
                    pass
                continue

            elif error.txn_requires_abort():
                # Must abort transaction
                print(f'Transaction requires abort: {error}')
                producer.abort_transaction()
                continue

            else:
                # Fatal error - need to recreate producer
                print(f'Fatal error: {error}')
                raise
```

### Exercise 4: Transaction Fencing

```python
# Fencing prevents zombie producers

# Producer 1 starts with transactional.id = 'processor-1'
producer1 = Producer({
    'transactional.id': 'processor-1',
    'bootstrap.servers': 'localhost:9092',
})
producer1.init_transactions()
producer1.begin_transaction()
producer1.produce('topic', value='msg1')
# Producer 1 hangs (network issue, GC pause, etc.)

# Producer 2 starts with same transactional.id
producer2 = Producer({
    'transactional.id': 'processor-1',  # Same ID!
    'bootstrap.servers': 'localhost:9092',
})
producer2.init_transactions()  # This fences producer1

# Producer 1 tries to commit
producer1.commit_transaction()  # FAILS! ProducerFencedException

# Only producer2 can proceed
producer2.begin_transaction()
producer2.produce('topic', value='msg2')
producer2.commit_transaction()  # Succeeds
```

## Transaction Configuration

```properties
# Producer settings
transactional.id=my-txn-id          # Required for transactions
transaction.timeout.ms=60000         # Max transaction duration
max.in.flight.requests.per.connection=5  # With idempotence

# Consumer settings
isolation.level=read_committed       # Only see committed
enable.auto.commit=false             # Required for transactional

# Broker settings
transaction.state.log.replication.factor=3
transaction.state.log.min.isr=2
```

## Transaction Coordinator

```
Each broker hosts a Transaction Coordinator
Coordinator is determined by: hash(transactional.id) % 50

Transaction Coordinator responsibilities:
1. Assign producer epochs (for fencing)
2. Track transaction state
3. Write to __transaction_state topic
4. Coordinate two-phase commit
5. Handle timeout and recovery

__transaction_state topic:
- 50 partitions by default
- Stores transaction metadata
- Compacted topic
```

## Two-Phase Commit

```
Phase 1: Prepare
─────────────────
Coordinator writes PREPARE marker to all partitions involved

Partition 0: [msg1, msg2, PREPARE]
Partition 1: [msg3, PREPARE]
Partition 2: [msg4, msg5, PREPARE]

Phase 2: Commit
───────────────
Coordinator writes COMMIT marker

Partition 0: [msg1, msg2, PREPARE, COMMIT]
Partition 1: [msg3, PREPARE, COMMIT]
Partition 2: [msg4, msg5, PREPARE, COMMIT]

Now messages visible to read_committed consumers
```

## Interview Questions

- "How do Kafka transactions work?"
  - "Kafka uses a two-phase commit protocol. Producer writes messages with transaction markers, then coordinator writes PREPARE to all partitions, then COMMIT. Consumers with read_committed only see messages after COMMIT marker."

- "What happens if a transactional producer crashes mid-transaction?"
  - "Transaction times out (default 60s). Coordinator writes ABORT markers. Any written messages are invisible to read_committed consumers. When producer restarts with same transactional.id, it gets new epoch and can start fresh."

- "How do you scale transactional processing?"
  - "Use different transactional.id per instance. Each handles different partitions. Key insight: transactions are per-producer, not global. Multiple producers can have concurrent transactions."

## Common Pitfalls

1. **Same transactional.id on multiple instances** - Fencing issues
2. **Long transactions** - Risk timeout
3. **Not handling abort properly** - Leaves transaction in bad state
4. **Forgetting isolation.level on consumer** - Sees uncommitted
5. **Transaction across consumer groups** - Not supported

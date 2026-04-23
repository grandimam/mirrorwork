# Chapter 20: Failure Modes and Recovery

## Overview

Understanding failure modes and recovery procedures is essential for operating Kafka in production. This chapter covers common failures, their impact, and how to handle them.

## Learning Objectives

By the end of this chapter, you will:

- Handle common failures
- Plan disaster recovery
- Test failure scenarios
- Implement backup strategies

## Resources

| Resource | Time |
|----------|------|
| Read: Kafka failure scenarios | 30 min |
| Hands-on: Simulate failures | 45 min |

## Core Concepts

### Failure Scenarios Overview

| Scenario | Impact | Recovery |
|----------|--------|----------|
| Single broker failure | Partitions failover | Automatic (if RF>1) |
| All brokers down | Complete outage | Restart cluster |
| Controller failure | New controller elected | Automatic |
| Disk failure | Partition data loss | Replace, replicate |
| Network partition | Split brain risk | Configure min.isr |
| Consumer crash | Rebalance, reprocess | Automatic |
| Producer timeout | Retry or error | Application handles |

### Single Broker Failure

```
Before:
Partition 0: Leader=Broker1, ISR=[Broker1, Broker2, Broker3]

Broker 1 crashes...

Recovery (automatic):
1. Controller detects via heartbeat timeout
2. Controller removes Broker 1 from ISR
3. Controller elects Broker 2 as new leader
4. Clients get new leader from metadata refresh

After:
Partition 0: Leader=Broker2, ISR=[Broker2, Broker3]

Time: typically < 5 seconds
Data loss: None (if acks=all with min.isr=2)
```

### Controller Failure

```
Controller (Broker 1) crashes...

1. Other brokers detect via heartbeat
2. Controller election triggered
3. Broker with lowest ID in quorum wins
4. New controller reads metadata from log
5. Cluster operations resume

Time: 1-5 seconds
Impact: Temporary inability to create topics, elect leaders
```

### All Brokers Down

```
Complete outage!

Recovery:
1. Investigate root cause
2. Fix underlying issue
3. Start brokers one by one
4. First broker becomes controller
5. Leader election for all partitions
6. Consumers reconnect

Data integrity:
- Data safe if persisted (RDB/AOF style for Kafka = always)
- Check for disk corruption
- Verify replication before accepting writes
```

## Hands-On Exercises

### Exercise 1: Simulate Broker Failure

```bash
# Check initial state
kafka-topics --describe --topic orders --bootstrap-server localhost:9092

# Note the leader for partition 0
# Output: Leader: 1

# Stop broker 1
docker stop kafka-1

# Observe leader election
kafka-topics --describe --topic orders --bootstrap-server localhost:9092

# Leader should have changed to another broker
# Output: Leader: 2

# Restart broker 1
docker start kafka-1

# Watch it rejoin ISR
watch -n 1 'kafka-topics --describe --topic orders --bootstrap-server localhost:9092'
```

### Exercise 2: Test min.insync.replicas

```bash
# Set min.insync.replicas
kafka-configs --alter --topic orders \
  --bootstrap-server localhost:9092 \
  --add-config min.insync.replicas=2

# With 3 brokers, stop 2
docker stop kafka-2 kafka-3

# Try to produce with acks=all
kafka-console-producer --topic orders \
  --bootstrap-server localhost:9092 \
  --producer-property acks=all

# Should fail with NotEnoughReplicasException
# This protects data integrity!
```

### Exercise 3: Consumer Failure Recovery

```python
from confluent_kafka import Consumer
import signal
import sys

def graceful_shutdown(consumer):
    """Handle shutdown gracefully."""
    def handler(signum, frame):
        print("Shutting down...")
        consumer.close()  # Commits offsets, leaves group cleanly
        sys.exit(0)

    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)

consumer = Consumer({
    'bootstrap.servers': 'localhost:9092',
    'group.id': 'order-processor',
    'auto.offset.reset': 'earliest',
    'enable.auto.commit': False,
})

graceful_shutdown(consumer)
consumer.subscribe(['orders'])

while True:
    msg = consumer.poll(1.0)
    if msg is None:
        continue

    try:
        process(msg)
        consumer.commit(msg)  # Commit after successful processing
    except Exception as e:
        # Don't commit - message will be redelivered
        log_error(e)
        # Optionally: send to dead letter topic
```

### Exercise 4: Producer Failure Handling

```python
from confluent_kafka import Producer, KafkaException
import time

class ResilientProducer:
    def __init__(self, config):
        self.config = {
            **config,
            'acks': 'all',
            'retries': 3,
            'retry.backoff.ms': 100,
            'enable.idempotence': True,
        }
        self.producer = Producer(self.config)
        self.failed_messages = []

    def produce(self, topic, key, value, max_retries=3):
        retries = 0
        while retries < max_retries:
            try:
                self.producer.produce(
                    topic=topic,
                    key=key,
                    value=value,
                    callback=self._delivery_callback
                )
                self.producer.flush(timeout=10)
                return True
            except BufferError:
                # Buffer full, wait and retry
                self.producer.poll(1)
                retries += 1
            except KafkaException as e:
                if e.args[0].retriable():
                    retries += 1
                    time.sleep(0.1 * retries)
                else:
                    # Non-retriable error
                    self.failed_messages.append((topic, key, value))
                    return False

        self.failed_messages.append((topic, key, value))
        return False

    def _delivery_callback(self, err, msg):
        if err:
            print(f"Delivery failed: {err}")
            self.failed_messages.append((msg.topic(), msg.key(), msg.value()))
```

## Disaster Recovery

### Backup Strategies

```bash
# 1. MirrorMaker 2 (Cross-cluster replication)
# Primary cluster → Secondary cluster

# connect-mirror-maker.properties
clusters = primary, secondary
primary.bootstrap.servers = primary-kafka:9092
secondary.bootstrap.servers = secondary-kafka:9092
primary->secondary.enabled = true
primary->secondary.topics = .*

# Start MirrorMaker
connect-mirror-maker.sh connect-mirror-maker.properties

# 2. Manual backup (for cold storage)
kafka-console-consumer --topic orders \
  --bootstrap-server localhost:9092 \
  --from-beginning > orders-backup.json

# 3. Topic-level backup
kafka-dump-log --files /data/kafka/orders-0/00000000000000000000.log \
  --print-data-log > orders-0-backup.json
```

### Recovery Procedures

```bash
# Scenario: Complete data center failure

# 1. Activate secondary cluster (MirrorMaker setup)
# Update DNS to point to secondary
# Consumers/producers connect to new cluster

# 2. From backup files
# Create topics
kafka-topics --create --topic orders \
  --bootstrap-server localhost:9092 \
  --partitions 3 --replication-factor 3

# Restore data
kafka-console-producer --topic orders \
  --bootstrap-server localhost:9092 < orders-backup.json

# 3. From disk backup
# Stop Kafka
# Restore log directories
# Start Kafka
# Verify data integrity
kafka-topics --describe --bootstrap-server localhost:9092
```

### Multi-Region Setup

```
Region A (Primary)          Region B (Secondary)
┌─────────────────┐        ┌─────────────────┐
│ Kafka Cluster   │───────▶│ Kafka Cluster   │
│ (Read/Write)    │ Mirror │ (Read-only)     │
└─────────────────┘ Maker  └─────────────────┘
        ▲                          │
        │                          │
    Producers                  Consumers
    Consumers                 (backup/analytics)

Failover:
1. Detect primary failure
2. Promote secondary to read/write
3. Update client configurations
4. Resume operations
```

## Testing Failure Scenarios

```python
# Chaos testing framework
import random
import subprocess
import time

class KafkaChaosTest:
    def __init__(self, broker_containers):
        self.brokers = broker_containers

    def kill_random_broker(self):
        """Kill a random broker."""
        broker = random.choice(self.brokers)
        subprocess.run(['docker', 'kill', broker])
        return broker

    def restart_broker(self, broker):
        """Restart a broker."""
        subprocess.run(['docker', 'start', broker])

    def network_partition(self, broker):
        """Simulate network partition."""
        subprocess.run([
            'docker', 'network', 'disconnect', 'kafka-network', broker
        ])

    def heal_network(self, broker):
        """Heal network partition."""
        subprocess.run([
            'docker', 'network', 'connect', 'kafka-network', broker
        ])

    def run_chaos_test(self, duration_minutes=30):
        """Run random failures for duration."""
        end_time = time.time() + duration_minutes * 60

        while time.time() < end_time:
            action = random.choice(['kill', 'partition', 'none'])

            if action == 'kill':
                broker = self.kill_random_broker()
                time.sleep(60)  # Let system recover
                self.restart_broker(broker)

            elif action == 'partition':
                broker = random.choice(self.brokers)
                self.network_partition(broker)
                time.sleep(30)
                self.heal_network(broker)

            time.sleep(random.randint(60, 300))
```

## Interview Questions

- "How does Kafka handle broker failures?"
  - Not: "It replicates data"
  - But: "With RF=3 and min.isr=2, when a broker fails: controller detects via heartbeat, removes from ISR, elects new leader from remaining ISR. Clients refresh metadata and connect to new leader. With acks=all, no data loss. Recovery is automatic in seconds."

- "What's your disaster recovery strategy for Kafka?"
  - "Multi-region with MirrorMaker 2. Secondary cluster receives replicated data. RPO depends on replication lag (typically seconds). RTO depends on failover automation. Regular testing of failover procedure. Also maintain cold backups for compliance."

- "How do you test Kafka resilience?"
  - "Chaos engineering. Randomly kill brokers during load tests, verify no data loss and acceptable latency impact. Test network partitions. Verify consumer group rebalancing. Test producer retry behavior. Run these tests regularly, not just once."

## Common Pitfalls

1. **Not testing failures** - Assume it works until it doesn't
2. **RF=1 in production** - No fault tolerance
3. **min.isr=1** - Data loss possible
4. **No monitoring during failures** - Can't assess impact
5. **Manual failover only** - Too slow, error-prone
6. **No backup validation** - Backups may be corrupt

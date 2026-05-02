# Chapter 19: Consumer Lag and Monitoring

## Overview

Monitoring consumer lag and cluster health is critical for maintaining reliable Kafka systems. This chapter covers key metrics, alerting strategies, and debugging slow consumers.

## Learning Objectives

By the end of this chapter, you will:

- Monitor consumer lag
- Set up alerting
- Debug slow consumers
- Understand key Kafka metrics

## Resources

| Resource | Time |
|----------|------|
| Hands-on: Set up lag monitoring | 30 min |
| Read: Kafka metrics guide | 30 min |

## Core Concepts

### Consumer Lag

```
Partition:  [0] [1] [2] [3] [4] [5] [6] [7] [8] [9]
                                          ↑
                                    Log End Offset = 9

Consumer committed offset = 5

Lag = Log End Offset - Committed Offset = 9 - 5 = 4 messages

Partition 0: lag = 4 (behind)
Partition 1: lag = 0 (caught up)
Partition 2: lag = 100 (falling behind!)
```

### Why Lag Matters

```
Low lag (< 100):
✓ Real-time processing
✓ Fresh data
✓ System healthy

High lag (> 10,000):
✗ Delayed processing
✗ Stale data
✗ Consumer overwhelmed
✗ May indicate issues

Growing lag:
⚠ Produce rate > consume rate
⚠ Consumer will never catch up
⚠ Requires investigation
```

## Hands-On Exercises

### Exercise 1: Check Consumer Lag (CLI)

```bash
# Describe consumer group
kafka-consumer-groups --describe --group order-processor \
  --bootstrap-server localhost:9092

# Output:
GROUP           TOPIC    PARTITION  CURRENT-OFFSET  LOG-END-OFFSET  LAG
order-processor orders   0          100             150             50
order-processor orders   1          95              95              0
order-processor orders   2          80              200             120

# Total lag = 50 + 0 + 120 = 170 messages
```

### Exercise 2: Monitor Lag with Python

```python
from confluent_kafka.admin import AdminClient, ConsumerGroupTopicPartitions
from confluent_kafka import TopicPartition

admin = AdminClient({'bootstrap.servers': 'localhost:9092'})

def get_consumer_lag(group_id: str, topic: str) -> dict:
    """Get lag for each partition."""
    # Get committed offsets
    topic_partitions = [TopicPartition(topic, p) for p in range(3)]
    committed = admin.list_consumer_group_offsets([
        ConsumerGroupTopicPartitions(group_id, topic_partitions)
    ])

    # Get end offsets
    consumer = Consumer({
        'bootstrap.servers': 'localhost:9092',
        'group.id': 'lag-checker',
    })

    lag = {}
    for tp in topic_partitions:
        low, high = consumer.get_watermark_offsets(tp)
        committed_offset = committed[group_id][tp].offset
        lag[tp.partition] = high - committed_offset

    consumer.close()
    return lag

# Monitor periodically
while True:
    lag = get_consumer_lag('order-processor', 'orders')
    total_lag = sum(lag.values())
    print(f"Total lag: {total_lag}, Per partition: {lag}")

    if total_lag > 10000:
        alert("High consumer lag!")

    time.sleep(60)
```

### Exercise 3: Prometheus/Grafana Monitoring

```yaml
# kafka-exporter for Prometheus
# docker-compose.yml addition:
kafka-exporter:
  image: danielqsj/kafka-exporter
  command:
    - --kafka.server=kafka:9092
  ports:
    - "9308:9308"
```

```promql
# Prometheus queries

# Total consumer lag per group
sum(kafka_consumergroup_lag) by (consumergroup)

# Lag by topic
sum(kafka_consumergroup_lag{topic="orders"}) by (consumergroup)

# Rate of lag change (growing or shrinking)
rate(kafka_consumergroup_lag[5m])

# Alert rule
groups:
- name: kafka-alerts
  rules:
  - alert: HighConsumerLag
    expr: sum(kafka_consumergroup_lag) by (consumergroup) > 10000
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High consumer lag for {{ $labels.consumergroup }}"
```

### Exercise 4: Debug Slow Consumer

```python
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def monitored_consumer():
    consumer = Consumer({
        'bootstrap.servers': 'localhost:9092',
        'group.id': 'order-processor',
    })
    consumer.subscribe(['orders'])

    message_count = 0
    processing_times = []

    while True:
        start = time.time()

        # Poll
        poll_start = time.time()
        msg = consumer.poll(1.0)
        poll_time = time.time() - poll_start

        if msg is None:
            continue

        # Process
        process_start = time.time()
        process_message(msg)
        process_time = time.time() - process_start

        # Commit
        commit_start = time.time()
        consumer.commit(msg)
        commit_time = time.time() - commit_start

        total_time = time.time() - start
        processing_times.append(total_time)
        message_count += 1

        # Log every 100 messages
        if message_count % 100 == 0:
            avg_time = sum(processing_times[-100:]) / 100
            logger.info(f"Avg processing time: {avg_time:.3f}s")
            logger.info(f"Last: poll={poll_time:.3f}s, "
                       f"process={process_time:.3f}s, "
                       f"commit={commit_time:.3f}s")

            if avg_time > 0.1:  # 100ms threshold
                logger.warning("Processing too slow!")
```

## Key Metrics to Monitor

### Broker Metrics

```
# Under-replicated partitions (should be 0)
kafka.server:type=ReplicaManager,name=UnderReplicatedPartitions

# Active controller count (should be 1)
kafka.controller:type=KafkaController,name=ActiveControllerCount

# Request latency
kafka.network:type=RequestMetrics,name=TotalTimeMs,request=Produce

# Bytes in/out
kafka.server:type=BrokerTopicMetrics,name=BytesInPerSec
kafka.server:type=BrokerTopicMetrics,name=BytesOutPerSec

# ISR shrink/expand rate
kafka.server:type=ReplicaManager,name=IsrShrinksPerSec
kafka.server:type=ReplicaManager,name=IsrExpandsPerSec
```

### Consumer Metrics

```
# Consumer lag
kafka.consumer:type=consumer-fetch-manager-metrics,client-id=*,topic=*,partition=*,name=records-lag

# Fetch rate
kafka.consumer:type=consumer-fetch-manager-metrics,name=fetch-rate

# Commit latency
kafka.consumer:type=consumer-coordinator-metrics,name=commit-latency-avg
```

### Producer Metrics

```
# Request latency
kafka.producer:type=producer-metrics,name=request-latency-avg

# Record error rate
kafka.producer:type=producer-metrics,name=record-error-rate

# Buffer available bytes
kafka.producer:type=producer-metrics,name=buffer-available-bytes
```

## Alert Thresholds

| Metric | Warning | Critical |
|--------|---------|----------|
| Consumer lag | > 1000 or > 1 min | > 10000 or > 5 min |
| Under-replicated partitions | > 0 for 5 min | > 0 for 15 min |
| Active controllers | != 1 | != 1 for 1 min |
| Request latency (p99) | > 100ms | > 500ms |
| ISR shrinks | > 0 | > 10/min |
| Disk usage | > 70% | > 85% |

## Debugging Slow Consumers

```
Symptom: Consumer lag growing

Step 1: Check processing time
- Is message processing slow?
- External service calls?
- Database queries?

Step 2: Check consumer configuration
- max.poll.records too high?
- Processing not keeping up?

Step 3: Check partition distribution
- Hot partition?
- Uneven workload?

Step 4: Check infrastructure
- Network issues?
- Disk I/O saturation?
- Memory pressure?

Step 5: Scale out
- Add more consumers (up to partition count)
- Add more partitions if needed
```

## Interview Questions

- "How do you monitor Kafka?"
  - Not: "Check consumer lag"
  - But: "Key metrics: consumer lag (both absolute and rate of change), under-replicated partitions, active controller count, request latency. I'd use Prometheus + Grafana with alerts for lag > threshold, any under-replicated partitions, and controller changes."

- "Consumer lag is growing, what do you do?"
  - "First, check if it's all partitions or specific ones (hot partition). Check processing time per message. If processing is slow, optimize or scale consumers. If it's network/infra, fix that. If produce rate spiked, may need more partitions/consumers."

- "What's the difference between lag in messages vs time?"
  - "Messages lag is offset difference. Time lag considers message timestamps. A lag of 1000 messages is different if those messages span 1 second vs 1 hour. Time-based lag is better for SLAs. Calculate: timestamp of latest message - timestamp at consumer offset."

## Common Pitfalls

1. **Only monitoring total lag** - Per-partition lag shows hot spots
2. **Alert on absolute lag only** - Rate of change matters too
3. **Not monitoring producers** - Spike in produce rate affects consumers
4. **Ignoring ISR metrics** - Under-replication precedes data loss
5. **No baseline** - Need to know normal lag to detect anomalies

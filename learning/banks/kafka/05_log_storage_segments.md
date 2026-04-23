# Chapter 5: Log Storage and Segments

## Overview

Understanding how Kafka stores data on disk is crucial for capacity planning, performance tuning, and debugging. Kafka's storage model is one of its key differentiators.

## Learning Objectives

By the end of this chapter, you will:

- Understand how Kafka stores messages on disk
- Know segment files and indexes
- Understand retention policies
- Configure storage for your use case

## Resources

| Resource | Time |
|----------|------|
| Read: Kafka storage internals | 30 min |
| Hands-on: Explore log directory structure | 30 min |

## Core Concepts

### Why Sequential Writes Matter

```
Random I/O (traditional DB):
Seek → Read → Seek → Write → Seek → Read
~10ms per operation

Sequential I/O (Kafka):
Write → Write → Write → Write → Write
~0.03ms per operation (300x faster)
```

Kafka achieves high throughput by:
- Append-only writes (no random seeks)
- Leveraging OS page cache
- Zero-copy transfer to network

### Log Directory Structure

```
/var/lib/kafka/data/
├── orders-0/                        # Topic-partition directory
│   ├── 00000000000000000000.log    # Segment file (messages)
│   ├── 00000000000000000000.index  # Offset index
│   ├── 00000000000000000000.timeindex  # Timestamp index
│   ├── 00000000000000005000.log    # New segment after offset 5000
│   ├── 00000000000000005000.index
│   ├── 00000000000000005000.timeindex
│   └── leader-epoch-checkpoint
├── orders-1/
│   └── ...
└── orders-2/
    └── ...
```

### Segment Files

A partition is split into segments for efficient management:

```
Partition 0:
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ Segment 0       │  │ Segment 1       │  │ Segment 2       │
│ offset 0-4999   │  │ offset 5000-9999│  │ offset 10000+   │
│ (closed)        │  │ (closed)        │  │ (active)        │
└─────────────────┘  └─────────────────┘  └─────────────────┘
     ↓                     ↓                     ↓
Can be deleted       Can be deleted       Currently writing
```

**Active segment:** Currently being written to
**Closed segments:** Immutable, can be deleted based on retention

### Index Files

Kafka uses sparse indexes for fast lookups:

```
Offset Index (.index):
Offset 0    → Position 0
Offset 100  → Position 4096
Offset 200  → Position 8192
...

To find offset 150:
1. Binary search index → find entry for 100
2. Scan forward from position 4096
```

**Time Index (.timeindex):**
Maps timestamps to offsets for time-based lookups.

## Key Questions to Understand

- Why does Kafka write sequentially to disk?
- What's in a segment file vs an index file?
- How does log compaction work?

## Retention Policies

### Time-Based Retention (Default)

```properties
# Retain messages for 7 days (default)
log.retention.hours=168
log.retention.minutes=
log.retention.ms=

# More precise control
log.retention.ms=604800000  # 7 days in ms
```

### Size-Based Retention

```properties
# Retain up to 1GB per partition
log.retention.bytes=1073741824

# Combined with time: delete when EITHER condition met
```

### Segment Configuration

```properties
# Create new segment after 1GB
log.segment.bytes=1073741824

# Create new segment after 7 days
log.segment.ms=604800000

# Minimum time before segment can be deleted
log.retention.check.interval.ms=300000
```

## Hands-On Exercises

### Exercise 1: Explore Log Directory

```bash
# Find Kafka data directory
docker exec -it kafka bash
ls -la /var/lib/kafka/data/

# Look at a partition
ls -la /var/lib/kafka/data/orders-0/

# Check segment sizes
du -h /var/lib/kafka/data/orders-0/*.log
```

### Exercise 2: View Segment Contents

```bash
# Dump segment contents
kafka-dump-log --files /var/lib/kafka/data/orders-0/00000000000000000000.log \
  --print-data-log

# Check index
kafka-dump-log --files /var/lib/kafka/data/orders-0/00000000000000000000.index
```

### Exercise 3: Configure Retention

```bash
# Set retention for a topic
kafka-configs --alter --topic orders \
  --bootstrap-server localhost:9092 \
  --add-config retention.ms=86400000  # 1 day

# Set segment size
kafka-configs --alter --topic orders \
  --bootstrap-server localhost:9092 \
  --add-config segment.bytes=536870912  # 512MB

# View current config
kafka-configs --describe --topic orders \
  --bootstrap-server localhost:9092
```

### Exercise 4: Force Segment Roll

```bash
# Set very small segment size to observe rolling
kafka-configs --alter --topic test \
  --bootstrap-server localhost:9092 \
  --add-config segment.bytes=1024

# Produce messages and watch new segments appear
kafka-console-producer --topic test \
  --bootstrap-server localhost:9092

# Check segments
ls -la /var/lib/kafka/data/test-0/
```

## Storage Sizing

```
Storage needed =
  (message_rate * avg_message_size * retention_period * replication_factor)

Example:
- 10,000 msg/sec
- 1KB avg size
- 7 days retention
- RF=3

= 10,000 * 1KB * 86400 * 7 * 3
= 18.1 TB
```

## Log Compaction

Alternative to time-based retention for certain use cases:

```
Before compaction:
key=A:v1, key=B:v1, key=A:v2, key=C:v1, key=B:v2, key=A:v3

After compaction:
key=A:v3, key=B:v2, key=C:v1

Only latest value per key retained
```

**Configuration:**

```properties
# Enable compaction
cleanup.policy=compact

# Or both delete and compact
cleanup.policy=compact,delete

# Compaction settings
min.cleanable.dirty.ratio=0.5  # Trigger when 50% dirty
min.compaction.lag.ms=0        # Min time before compaction
```

## Interview Questions

- "How does Kafka achieve high throughput with disk storage?"
  - Not: "It's optimized"
  - But: "Sequential writes only - append to end of log. Leverages OS page cache so hot data is in memory. Zero-copy from page cache to network socket. No random seeks."

- "What happens when retention is exceeded?"
  - "Kafka deletes entire segments, not individual messages. A segment is deleted when ALL messages in it exceed retention. This is why segment size affects when data is actually deleted."

## Common Pitfalls

1. **Disk full** - Monitor and alert on disk usage
2. **Too large segments** - Delayed deletion, slow recovery
3. **Too small segments** - Many files, FD exhaustion
4. **Forgetting replication** - Storage = raw * RF
5. **Not monitoring log cleaner** - Compaction may fall behind

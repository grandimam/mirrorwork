# Chapter 7: Leader Election

## Overview

Leader election determines which broker handles reads and writes for each partition. Understanding this process is crucial for operating Kafka in production.

## Learning Objectives

By the end of this chapter, you will:

- Understand how leaders are elected
- Know the role of the controller
- Handle leader failures
- Configure for availability vs durability

## Resources

| Resource | Time |
|----------|------|
| Read: Kafka controller deep dive | 30 min |

## Core Concepts

### The Controller

One broker is elected as the controller - it manages cluster state:

```
Kafka Cluster
┌─────────────────────────────────────────────────────┐
│                                                     │
│  Broker 1          Broker 2          Broker 3      │
│  ┌──────────┐      ┌──────────┐      ┌──────────┐  │
│  │Controller│      │          │      │          │  │
│  │  ★       │      │ Follower │      │ Follower │  │
│  └──────────┘      └──────────┘      └──────────┘  │
│       │                                             │
│       ▼                                             │
│  Manages:                                          │
│  - Partition leaders                               │
│  - Replica assignments                             │
│  - Broker membership                               │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### Controller Election

With ZooKeeper (older):
```
1. All brokers race to create /controller znode
2. Winner becomes controller
3. Others watch for controller failure
4. If controller dies, race again
```

With KRaft (newer, ZooKeeper-less):
```
1. Raft consensus among controller nodes
2. Leader election via Raft protocol
3. No external dependency on ZooKeeper
```

### Partition Leader Election

When a leader fails:

```
Before failure:
Partition 0: Leader=Broker1, ISR=[Broker1, Broker2, Broker3]

Broker 1 fails...

Controller detects failure (via heartbeat)
    ↓
Controller selects new leader from ISR
    ↓
Controller updates metadata
    ↓
New leader announced to all brokers

After election:
Partition 0: Leader=Broker2, ISR=[Broker2, Broker3]

Time: typically < 1 second
```

### Leader Election Process

```
1. Controller monitors all brokers via heartbeats
2. Broker 1 (leader) stops sending heartbeats
3. After controller.socket.timeout.ms, controller marks Broker 1 dead
4. Controller looks at ISR for partition: [Broker1, Broker2, Broker3]
5. Controller removes Broker1 from ISR: [Broker2, Broker3]
6. Controller elects new leader: Broker2 (first in ISR)
7. Controller updates cluster metadata
8. Clients receive new leader info on next metadata refresh
```

## Key Questions to Understand

- Who decides which broker is the leader?
- What happens during leader election?
- What's "unclean leader election" and why is it dangerous?

## Unclean Leader Election

What if ALL ISR replicas are down?

```
Partition 0: Leader=Broker1, ISR=[Broker1]
Broker 1 crashes...

Broker 2 and Broker 3 are alive but NOT in ISR (lagging)

Options:
1. Wait for Broker 1 to recover (unavailable)
2. Elect Broker 2 as leader (DATA LOSS - messages only on Broker 1)
```

**Configuration:**

```properties
# Allow non-ISR replica to become leader (risk of data loss)
unclean.leader.election.enable=false  # recommended default

# If true: availability over durability
# If false: durability over availability (may become unavailable)
```

### When to Enable Unclean Election

| Scenario | Setting | Reason |
|----------|---------|--------|
| Financial data | false | Never lose transactions |
| Metrics/logs | true | Availability more important |
| User sessions | depends | Assess impact of loss |
| CDC/audit | false | Must maintain integrity |

## Preferred Leader Election

Kafka tries to balance leaders across brokers:

```
Initial assignment (balanced):
Partition 0: Leader=Broker1, Replicas=[1,2,3]
Partition 1: Leader=Broker2, Replicas=[2,3,1]
Partition 2: Leader=Broker3, Replicas=[3,1,2]

After Broker 1 crash and recovery:
Partition 0: Leader=Broker2, Replicas=[1,2,3]  ← Unbalanced
Partition 1: Leader=Broker2, Replicas=[2,3,1]
Partition 2: Leader=Broker3, Replicas=[3,1,2]

Preferred leader election restores balance:
Partition 0: Leader=Broker1, Replicas=[1,2,3]  ← Rebalanced
```

**Configuration:**

```properties
# Enable automatic preferred leader election
auto.leader.rebalance.enable=true

# Check interval
leader.imbalance.check.interval.seconds=300

# Threshold for triggering rebalance
leader.imbalance.per.broker.percentage=10
```

## Hands-On Exercises

### Exercise 1: Observe Controller

```bash
# Find current controller
kafka-metadata --snapshot /path/to/metadata --command "controllers"

# Or via ZooKeeper (older clusters)
zookeeper-shell localhost:2181 get /controller
```

### Exercise 2: Simulate Leader Failure

```bash
# Check current leaders
kafka-topics --describe --topic orders \
  --bootstrap-server localhost:9092

# Stop the leader broker
docker stop kafka-1

# Observe new leader election
kafka-topics --describe --topic orders \
  --bootstrap-server localhost:9092

# Check election happened quickly
# Leader should have changed
```

### Exercise 3: Trigger Preferred Leader Election

```bash
# Check leader distribution
kafka-topics --describe --bootstrap-server localhost:9092 | grep Leader

# Trigger preferred leader election
kafka-leader-election --bootstrap-server localhost:9092 \
  --election-type PREFERRED \
  --all-topic-partitions

# Verify leaders rebalanced
kafka-topics --describe --bootstrap-server localhost:9092 | grep Leader
```

### Exercise 4: Test Unclean Election

```bash
# Create topic with RF=1 for testing
kafka-topics --create --topic test-unclean \
  --bootstrap-server localhost:9092 \
  --replication-factor 1 \
  --partitions 1

# Produce some messages
kafka-console-producer --topic test-unclean \
  --bootstrap-server localhost:9092
> message 1
> message 2

# Stop the only broker with data
docker stop kafka-1

# Topic is now unavailable
# With unclean.leader.election.enable=false, it stays unavailable
# With unclean.leader.election.enable=true, another broker could take over (losing data)
```

## Controller Failover

```
1. Controller (Broker 1) crashes
2. Other brokers detect via heartbeat timeout
3. New controller election begins
4. Broker with lowest ID in pool typically wins
5. New controller reads metadata from log
6. New controller resumes cluster management

Duration: typically 1-5 seconds
```

## Interview Questions

- "What happens when a Kafka leader fails?"
  - Not: "Another broker takes over"
  - But: "Controller detects failure via missed heartbeats, selects new leader from ISR, updates cluster metadata. Clients get new leader on metadata refresh. Takes < 1 second typically. During election, partition is briefly unavailable for writes."

- "What is unclean leader election?"
  - "When all ISR replicas are down, Kafka can elect a non-ISR replica as leader. This risks data loss because that replica may be missing recent messages. It's a tradeoff: availability vs durability. I'd disable it for critical data."

- "How does Kafka avoid split-brain?"
  - "Only one controller manages elections, coordinated via ZooKeeper or KRaft consensus. min.insync.replicas ensures writes aren't acknowledged without quorum. Even if network partitions, only ISR replicas can become leader."

## Common Pitfalls

1. **Unclean election enabled for critical data** - Silent data loss
2. **Not monitoring controller health** - Delayed failure detection
3. **Too aggressive heartbeat timeout** - Unnecessary elections
4. **Unbalanced leaders** - Hotspots on certain brokers
5. **Single controller node** - Controller is SPOF

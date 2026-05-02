# Chapter 20: Replication

## Overview

PostgreSQL replication creates copies of your database for high availability, disaster recovery, and read scaling. Understanding streaming and logical replication helps you design resilient database architectures.

## Learning Objectives

By the end of this chapter, you will:

- Set up streaming replication
- Understand logical replication
- Monitor replication lag
- Handle failover scenarios

## Resources

| Resource | Time |
|----------|------|
| Read: PostgreSQL replication docs | 45 min |
| Hands-on: Set up replica | 1 hr |

## Core Concepts

### Replication Types

| Type | What's Replicated | Use Cases |
|------|------------------|-----------|
| Streaming | Entire cluster (WAL) | HA, disaster recovery, read replicas |
| Logical | Selected tables/data | Multi-master, data migration, CDC |

### Streaming Replication

```
Primary writes WAL → Streams to Standby → Standby replays WAL

┌─────────────┐     WAL Stream      ┌─────────────┐
│   Primary   │ ─────────────────► │   Standby   │
│  (writes)   │                     │  (replica)  │
└─────────────┘                     └─────────────┘
      │                                   │
      │ read/write                        │ read-only
      │                                   │
   [App Write]                        [App Read]
```

**Setting Up Primary:**

```sql
-- postgresql.conf on primary
wal_level = replica                    -- Enable replication
max_wal_senders = 10                   -- Max replication connections
wal_keep_size = 1GB                    -- WAL to keep for lagging replicas
hot_standby = on                       -- Allow queries on standby

-- Create replication user
CREATE ROLE replicator WITH REPLICATION LOGIN PASSWORD 'secret';

-- pg_hba.conf - allow replication connections
-- host replication replicator replica_ip/32 md5
```

**Setting Up Standby:**

```bash
# Take base backup from primary
pg_basebackup -h primary_host -D /var/lib/postgresql/data \
  -U replicator -P --wal-method=stream

# Create standby.signal file (PG 12+)
touch /var/lib/postgresql/data/standby.signal

# Or recovery.conf (PG 11 and earlier)
# standby_mode = on
# primary_conninfo = 'host=primary_host user=replicator password=secret'
```

```sql
-- postgresql.conf on standby
primary_conninfo = 'host=primary_host port=5432 user=replicator password=secret'
hot_standby = on  -- Allow read queries

-- Start PostgreSQL - it connects and streams WAL
```

### Synchronous Replication

```sql
-- Asynchronous (default): primary doesn't wait for standby
-- Synchronous: primary waits for standby to confirm

-- On primary postgresql.conf
synchronous_commit = on
synchronous_standby_names = 'standby1'  -- or 'FIRST 1 (standby1, standby2)'

-- Modes:
-- remote_write: standby received WAL (in memory)
-- on: standby wrote WAL to disk
-- remote_apply: standby applied WAL (visible to queries)

synchronous_commit = remote_apply  -- Strongest guarantee
```

**Trade-offs:**

| Mode | Durability | Performance | Use Case |
|------|-----------|-------------|----------|
| off | Possible loss | Fastest | Non-critical data |
| local | Primary only | Fast | Default |
| on (sync) | Primary + standby disk | Slower | Critical data |
| remote_apply | Primary + standby applied | Slowest | Read-your-writes |

### Monitoring Replication

```sql
-- On primary: check replication status
SELECT
    application_name,
    client_addr,
    state,
    sent_lsn,
    write_lsn,
    flush_lsn,
    replay_lsn,
    pg_wal_lsn_diff(sent_lsn, replay_lsn) as lag_bytes
FROM pg_stat_replication;

-- On standby: check replication status
SELECT
    pg_is_in_recovery() as is_replica,
    pg_last_wal_receive_lsn() as received,
    pg_last_wal_replay_lsn() as replayed,
    pg_last_xact_replay_timestamp() as last_replay_time,
    NOW() - pg_last_xact_replay_timestamp() as replay_lag;

-- Calculate lag in seconds (on standby)
SELECT EXTRACT(EPOCH FROM (NOW() - pg_last_xact_replay_timestamp())) as lag_seconds;
```

### Failover

```sql
-- Manual failover: promote standby to primary

-- On standby, run:
-- pg_ctl promote -D /var/lib/postgresql/data
-- Or:
SELECT pg_promote();

-- Standby becomes standalone primary
-- Original primary must be rebuilt as standby

-- Automated failover: use Patroni, repmgr, or pg_auto_failover
```

### Logical Replication

```sql
-- Publish/Subscribe model - selective replication

-- On publisher (source)
-- postgresql.conf
wal_level = logical

CREATE PUBLICATION mypub FOR TABLE orders, users;
-- Or: FOR ALL TABLES

-- On subscriber (destination)
CREATE SUBSCRIPTION mysub
CONNECTION 'host=publisher_host dbname=mydb user=replicator password=secret'
PUBLICATION mypub;

-- Check subscription status
SELECT * FROM pg_stat_subscription;

-- Check publication status
SELECT * FROM pg_stat_replication;
```

**Logical Replication Use Cases:**

```
1. Selective table replication
2. Cross-version replication (upgrade path)
3. Consolidating data from multiple sources
4. Real-time data integration
5. Zero-downtime migrations
```

### Handling Replication Lag

```sql
-- Check lag on standby
SELECT
    CASE
        WHEN pg_last_wal_receive_lsn() = pg_last_wal_replay_lsn()
        THEN 0
        ELSE EXTRACT(EPOCH FROM NOW() - pg_last_xact_replay_timestamp())
    END as lag_seconds;

-- Application: route critical reads to primary
-- Route reporting/analytics to replicas

-- If lag is too high:
-- 1. Check network between primary and standby
-- 2. Check standby I/O capacity
-- 3. Increase wal_keep_size if WAL is being recycled
-- 4. Check for long-running queries on standby blocking replay
```

## Key Questions to Understand

- What's the difference between streaming and logical replication?
- How much replication lag is acceptable?
- What happens during failover?

## Hands-On Exercises

### Exercise 1: Check Replication Status

```sql
-- On primary
SELECT
    application_name,
    state,
    sent_lsn,
    replay_lsn,
    pg_size_pretty(pg_wal_lsn_diff(sent_lsn, replay_lsn)) as lag
FROM pg_stat_replication;

-- On standby
SELECT
    pg_is_in_recovery() as is_replica,
    NOW() - pg_last_xact_replay_timestamp() as lag;
```

### Exercise 2: Logical Replication Setup

```sql
-- Publisher (primary)
CREATE TABLE events (
    id SERIAL PRIMARY KEY,
    event_type TEXT,
    data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE PUBLICATION events_pub FOR TABLE events;

-- Subscriber (different database/server)
CREATE TABLE events (
    id SERIAL PRIMARY KEY,
    event_type TEXT,
    data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE SUBSCRIPTION events_sub
CONNECTION 'host=publisher port=5432 dbname=mydb user=replicator'
PUBLICATION events_pub;

-- Insert on publisher
INSERT INTO events (event_type, data) VALUES ('test', '{"key": "value"}');

-- Check subscriber received it
SELECT * FROM events;
```

### Exercise 3: Measure Replication Lag

```sql
-- Create function to measure lag
CREATE OR REPLACE FUNCTION replication_lag_bytes()
RETURNS BIGINT AS $$
BEGIN
    RETURN pg_wal_lsn_diff(
        pg_current_wal_lsn(),
        (SELECT replay_lsn FROM pg_stat_replication LIMIT 1)
    );
END;
$$ LANGUAGE plpgsql;

-- Monitor lag over time
SELECT
    NOW() as time,
    replication_lag_bytes() / 1024 as lag_kb,
    (SELECT count(*) FROM pg_stat_replication) as replicas;
```

## Interview Deep Dive

### Question: "How does PostgreSQL streaming replication work?"

**Answer:**
> "Streaming replication sends Write-Ahead Log (WAL) records from primary to standby in real-time. The primary writes WAL as usual, and a WAL sender process streams these to standbys over TCP. Standbys have a WAL receiver process that applies the records, keeping them in sync.
>
> Key settings: wal_level=replica enables it, max_wal_senders limits connections, wal_keep_size prevents recycling WAL that standbys need. By default it's asynchronous - primary doesn't wait for standby confirmation. For higher durability, synchronous_commit=on makes primary wait for standby to write WAL, trading latency for guaranteed durability."

### Question: "When would you use logical replication vs streaming replication?"

**Answer:**
> "Streaming replication copies the entire cluster byte-for-byte - great for HA, disaster recovery, and read replicas of the whole database. But it requires same PostgreSQL major version and replicates everything.
>
> Logical replication is publish/subscribe at table level - replicate specific tables to different databases, different PostgreSQL versions, or consolidate from multiple sources. Use it for: cross-version upgrades (replicate to new version), selective replication, multi-master setups, or as CDC for data pipelines. Trade-off: more complex setup, doesn't replicate DDL automatically, potential for conflicts in multi-master."

## Key Takeaways

1. **Streaming replication** copies entire cluster via WAL
2. **Logical replication** is table-level, publish/subscribe
3. **Synchronous mode** trades performance for durability
4. **Monitor lag** to ensure replicas are current
5. **Failover** requires promoting standby to primary

## Self-Assessment Questions

1. What's wal_level and why does it matter for replication?
2. How do you check replication lag?
3. What happens if standby falls too far behind?
4. When would you use synchronous replication?
5. How does logical replication differ from streaming?

## Next Chapter

[Chapter 21: Partitioning →](./21_partitioning.md)

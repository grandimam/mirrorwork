# Chapter 21: Partitioning

## Overview

Table partitioning divides large tables into smaller, more manageable pieces while maintaining a single logical table interface. This improves query performance, simplifies maintenance, and enables efficient data lifecycle management.

## Learning Objectives

By the end of this chapter, you will:

- Implement table partitioning
- Choose the right partition strategy
- Query partitioned tables efficiently
- Manage partition lifecycle

## Resources

| Resource | Time |
|----------|------|
| Read: PostgreSQL partitioning | 30 min |
| Hands-on: Create partitioned table | 45 min |

## Core Concepts

### Why Partition?

```
Benefits:
1. Query performance - scan only relevant partitions
2. Bulk operations - drop partition instead of DELETE
3. Maintenance - VACUUM/REINDEX individual partitions
4. Storage tiering - older partitions on slower storage
5. Parallel operations - work on partitions concurrently

When to partition:
- Tables > 100M rows
- Clear partitioning key (date, tenant_id, region)
- Queries naturally filter by partition key
- Need to efficiently purge old data
```

### Partitioning Strategies

| Type | Best For | Example |
|------|----------|---------|
| Range | Time-series, sequential data | Monthly logs, yearly data |
| List | Categorical data | Status, region, tenant |
| Hash | Even distribution | User ID, random access |

### Range Partitioning

```sql
-- Create partitioned table
CREATE TABLE events (
    id BIGSERIAL,
    event_type VARCHAR(50),
    data JSONB,
    created_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (id, created_at)  -- Partition key must be in PK
) PARTITION BY RANGE (created_at);

-- Create partitions
CREATE TABLE events_2024_01 PARTITION OF events
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

CREATE TABLE events_2024_02 PARTITION OF events
    FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');

CREATE TABLE events_2024_03 PARTITION OF events
    FOR VALUES FROM ('2024-03-01') TO ('2024-04-01');

-- Default partition for unmatched values
CREATE TABLE events_default PARTITION OF events DEFAULT;

-- Insert goes to appropriate partition automatically
INSERT INTO events (event_type, data, created_at)
VALUES ('click', '{}', '2024-02-15');
-- Goes to events_2024_02

-- Query with partition pruning
EXPLAIN ANALYZE
SELECT * FROM events
WHERE created_at >= '2024-02-01' AND created_at < '2024-03-01';
-- Only scans events_2024_02
```

### List Partitioning

```sql
-- Partition by category
CREATE TABLE orders (
    id BIGSERIAL,
    status VARCHAR(20) NOT NULL,
    total DECIMAL(10,2),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (id, status)
) PARTITION BY LIST (status);

CREATE TABLE orders_pending PARTITION OF orders
    FOR VALUES IN ('pending', 'processing');

CREATE TABLE orders_completed PARTITION OF orders
    FOR VALUES IN ('completed', 'delivered');

CREATE TABLE orders_cancelled PARTITION OF orders
    FOR VALUES IN ('cancelled', 'refunded');

-- Multi-tenant partitioning
CREATE TABLE tenant_data (
    id BIGSERIAL,
    tenant_id INTEGER NOT NULL,
    data JSONB,
    PRIMARY KEY (id, tenant_id)
) PARTITION BY LIST (tenant_id);

CREATE TABLE tenant_1_data PARTITION OF tenant_data
    FOR VALUES IN (1);

CREATE TABLE tenant_2_data PARTITION OF tenant_data
    FOR VALUES IN (2);
```

### Hash Partitioning

```sql
-- Even distribution across partitions
CREATE TABLE users (
    id BIGSERIAL,
    email VARCHAR(255),
    data JSONB,
    PRIMARY KEY (id)
) PARTITION BY HASH (id);

-- Create 4 hash partitions
CREATE TABLE users_p0 PARTITION OF users
    FOR VALUES WITH (MODULUS 4, REMAINDER 0);

CREATE TABLE users_p1 PARTITION OF users
    FOR VALUES WITH (MODULUS 4, REMAINDER 1);

CREATE TABLE users_p2 PARTITION OF users
    FOR VALUES WITH (MODULUS 4, REMAINDER 2);

CREATE TABLE users_p3 PARTITION OF users
    FOR VALUES WITH (MODULUS 4, REMAINDER 3);

-- Rows distributed based on hash(id) % 4
```

### Partition Pruning

```sql
-- Enable partition pruning (on by default)
SET enable_partition_pruning = on;

-- Check pruning in action
EXPLAIN ANALYZE
SELECT * FROM events
WHERE created_at >= '2024-02-15' AND created_at < '2024-02-20';

-- Output shows:
--   ->  Seq Scan on events_2024_02 events_1  (...)
-- Other partitions not scanned!

-- Pruning also works at runtime
EXPLAIN ANALYZE
SELECT * FROM events
WHERE created_at >= $1 AND created_at < $2;
-- Partitions pruned based on parameter values
```

### Managing Partitions

```sql
-- Add new partition
CREATE TABLE events_2024_04 PARTITION OF events
    FOR VALUES FROM ('2024-04-01') TO ('2024-05-01');

-- Detach partition (keeps data, removes from partitioned table)
ALTER TABLE events DETACH PARTITION events_2024_01;
-- Now events_2024_01 is a standalone table

-- Attach existing table as partition
ALTER TABLE events ATTACH PARTITION events_2024_01
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

-- Drop old partition (deletes data)
DROP TABLE events_2024_01;

-- Efficient data purge: detach + drop
ALTER TABLE events DETACH PARTITION events_2024_01;
DROP TABLE events_2024_01;
-- Much faster than DELETE!
```

### Indexes on Partitioned Tables

```sql
-- Create index on parent - applies to all partitions
CREATE INDEX idx_events_type ON events(event_type);
-- Automatically creates index on each partition

-- Create index on specific partition
CREATE INDEX idx_events_2024_02_data ON events_2024_02 USING GIN (data);

-- Check partition indexes
SELECT
    schemaname,
    tablename,
    indexname
FROM pg_indexes
WHERE tablename LIKE 'events%'
ORDER BY tablename, indexname;
```

### Partitioned Table Constraints

```sql
-- Primary key must include partition key
CREATE TABLE bad_pk (
    id SERIAL PRIMARY KEY,  -- ERROR!
    created_at DATE NOT NULL
) PARTITION BY RANGE (created_at);
-- ERROR: unique constraint must include partition key

-- Correct:
CREATE TABLE good_pk (
    id SERIAL,
    created_at DATE NOT NULL,
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

-- Foreign keys pointing TO partitioned table
-- Now supported in PG 12+

-- Foreign keys FROM partitioned table
-- Each partition has its own FK constraint
```

## Key Questions to Understand

- When should you partition a table?
- How does partition pruning work?
- What's the overhead of partitioning?

## Hands-On Exercises

### Exercise 1: Time-Series Partitioning

```sql
-- Create monthly partitioned events table
CREATE TABLE log_events (
    id BIGSERIAL,
    level VARCHAR(10),
    message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

-- Create partitions for several months
DO $$
DECLARE
    start_date DATE := '2024-01-01';
    end_date DATE;
    partition_name TEXT;
BEGIN
    FOR i IN 0..11 LOOP
        end_date := start_date + INTERVAL '1 month';
        partition_name := 'log_events_' || to_char(start_date, 'YYYY_MM');

        EXECUTE format(
            'CREATE TABLE %I PARTITION OF log_events
             FOR VALUES FROM (%L) TO (%L)',
            partition_name, start_date, end_date
        );

        start_date := end_date;
    END LOOP;
END $$;

-- Insert test data
INSERT INTO log_events (level, message, created_at)
SELECT
    (ARRAY['INFO', 'WARN', 'ERROR'])[floor(random() * 3 + 1)::int],
    'Log message ' || i,
    '2024-01-01'::TIMESTAMPTZ + (random() * 365 || ' days')::INTERVAL
FROM generate_series(1, 100000) i;

-- Test partition pruning
EXPLAIN ANALYZE
SELECT * FROM log_events
WHERE created_at >= '2024-06-01' AND created_at < '2024-07-01';
```

### Exercise 2: Partition Maintenance

```sql
-- Check partition sizes
SELECT
    child.relname AS partition,
    pg_size_pretty(pg_relation_size(child.oid)) AS size,
    pg_stat_user_tables.n_live_tup AS rows
FROM pg_inherits
JOIN pg_class parent ON pg_inherits.inhparent = parent.oid
JOIN pg_class child ON pg_inherits.inhrelid = child.oid
LEFT JOIN pg_stat_user_tables ON child.relname = pg_stat_user_tables.relname
WHERE parent.relname = 'log_events'
ORDER BY child.relname;

-- Drop old partition
ALTER TABLE log_events DETACH PARTITION log_events_2024_01;
DROP TABLE log_events_2024_01;
```

### Exercise 3: Query Performance Comparison

```sql
-- Create non-partitioned copy
CREATE TABLE log_events_flat AS SELECT * FROM log_events;
CREATE INDEX idx_flat_created ON log_events_flat(created_at);

-- Compare query plans
EXPLAIN ANALYZE
SELECT * FROM log_events WHERE created_at >= '2024-06-15' AND created_at < '2024-06-16';

EXPLAIN ANALYZE
SELECT * FROM log_events_flat WHERE created_at >= '2024-06-15' AND created_at < '2024-06-16';

-- Compare aggregation
EXPLAIN ANALYZE
SELECT date_trunc('day', created_at), count(*)
FROM log_events
WHERE created_at >= '2024-06-01' AND created_at < '2024-07-01'
GROUP BY 1;
```

## Interview Deep Dive

### Question: "When would you partition a table?"

**Answer:**
> "I'd partition when: table is very large (100M+ rows), queries have a natural filter on potential partition key (like date ranges), need to efficiently purge old data (DROP partition vs DELETE), or want parallel maintenance operations.
>
> Partitioning has overhead - more tables to manage, query planning complexity, constraints around primary keys. I wouldn't partition small tables or tables without clear partitioning patterns. For time-series data, range partitioning by month/day is common. For multi-tenant, list partitioning by tenant_id. Hash for even distribution when no natural key."

### Question: "How does partition pruning work?"

**Answer:**
> "Partition pruning eliminates partitions that can't contain matching rows based on the WHERE clause. If my table is partitioned by month and I query WHERE created_at BETWEEN '2024-06-01' AND '2024-06-30', PostgreSQL only scans the June partition.
>
> Pruning works at planning time with constant values, and at execution time with parameter values (runtime pruning in PG 11+). Check with EXPLAIN - it shows which partitions are scanned. If all partitions are scanned, the query isn't filtering on the partition key effectively."

## Key Takeaways

1. **Range** partitioning for time-series data
2. **List** partitioning for categories/tenants
3. **Hash** partitioning for even distribution
4. **Partition pruning** eliminates unnecessary scans
5. **DROP partition** is much faster than DELETE

## Self-Assessment Questions

1. What must be included in a partitioned table's primary key?
2. How do you efficiently purge old data from a partitioned table?
3. What's the difference between DETACH and DROP partition?
4. When does partition pruning happen?
5. How many partitions is too many?

## Next Chapter

[Chapter 22: Read Replicas →](./22_read_replicas.md)

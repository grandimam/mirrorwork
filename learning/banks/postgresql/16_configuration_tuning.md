# Chapter 23: Configuration Tuning

## Overview

PostgreSQL's default configuration is conservative, designed to work on minimal hardware. Proper tuning based on your workload and hardware can dramatically improve performance. This chapter covers the most important configuration parameters.

## Learning Objectives

By the end of this chapter, you will:

- Tune memory parameters for your workload
- Configure for different workload types
- Set appropriate connection limits
- Understand the impact of each setting

## Resources

| Resource | Time |
|----------|------|
| Read: PostgreSQL configuration documentation | 30 min |
| Hands-on: Tune a test instance | 30 min |

## Core Concepts

### Memory Configuration

```ini
# postgresql.conf

# Shared Buffers - PostgreSQL's buffer cache
# Recommendation: 25% of total RAM (up to ~8GB, more can have diminishing returns)
shared_buffers = 4GB  # Default: 128MB

# Effective Cache Size - Estimate of OS + PostgreSQL cache
# Helps planner estimate cost of index scans
# Recommendation: 75% of total RAM
effective_cache_size = 12GB  # Default: 4GB

# Work Mem - Memory for sorts and hashes PER OPERATION
# Careful: can be used multiple times per query
# Recommendation: Total RAM / max_connections / 4
work_mem = 256MB  # Default: 4MB

# Maintenance Work Mem - Memory for VACUUM, CREATE INDEX, etc.
# Can be higher since these run less frequently
maintenance_work_mem = 1GB  # Default: 64MB

# Example for 16GB RAM server with 100 connections:
# shared_buffers = 4GB (25%)
# effective_cache_size = 12GB (75%)
# work_mem = 40MB (16GB / 100 / 4)
# maintenance_work_mem = 1GB
```

### work_mem Caution

```sql
-- work_mem can be used multiple times per query!
EXPLAIN ANALYZE
SELECT * FROM orders o
JOIN users u ON u.id = o.user_id
JOIN products p ON p.id = o.product_id
WHERE o.created_at > '2024-01-01'
ORDER BY o.created_at;

-- This query might use work_mem for:
-- 1. Hash join for users
-- 2. Hash join for products
-- 3. Sort for ORDER BY
-- Total: 3 * work_mem

-- Set per-query for large operations
SET work_mem = '512MB';
CREATE INDEX ...;
RESET work_mem;
```

### WAL Configuration

```ini
# WAL Buffers - Buffer for write-ahead log
# Recommendation: 3% of shared_buffers, up to 64MB
wal_buffers = 64MB  # Default: -1 (auto)

# Checkpoint settings
checkpoint_completion_target = 0.9  # Default: 0.9
# Spread checkpoint over this fraction of checkpoint_timeout

max_wal_size = 4GB  # Default: 1GB
# Maximum WAL size between checkpoints

min_wal_size = 1GB  # Default: 80MB
# Minimum WAL to keep

# Synchronous commit
synchronous_commit = on  # Default: on
# off = faster, risk of losing last few transactions on crash
```

### Connection Settings

```ini
# Maximum connections
max_connections = 200  # Default: 100
# Keep this low if using connection pooler (PgBouncer)
# Each connection uses memory even when idle

# Superuser reserved connections
superuser_reserved_connections = 3  # Default: 3
# Ensure admin can connect even when full
```

### Planner Settings

```ini
# For SSD storage, reduce random_page_cost
random_page_cost = 1.1  # Default: 4.0
# Default assumes HDD (random 4x slower than sequential)
# For SSD, random is nearly as fast as sequential

seq_page_cost = 1.0  # Default: 1.0
# Baseline for sequential I/O cost

# Parallel queries
max_parallel_workers_per_gather = 4  # Default: 2
max_parallel_workers = 8  # Default: 8
max_parallel_maintenance_workers = 4  # Default: 2
# Parallel index builds, vacuum

# Effective I/O concurrency (for SSDs)
effective_io_concurrency = 200  # Default: 1
# Number of concurrent I/O operations
# Set higher for SSD (200), lower for HDD (2-4)
```

### Autovacuum Tuning

```ini
# Autovacuum settings
autovacuum = on  # Default: on

# When to trigger vacuum
autovacuum_vacuum_threshold = 50  # Default: 50
autovacuum_vacuum_scale_factor = 0.2  # Default: 0.2
# Vacuum when: dead_tuples > threshold + scale_factor * table_rows

# When to trigger analyze
autovacuum_analyze_threshold = 50  # Default: 50
autovacuum_analyze_scale_factor = 0.1  # Default: 0.1

# Worker settings
autovacuum_max_workers = 3  # Default: 3
autovacuum_naptime = 1min  # Default: 1min

# Cost-based throttling
autovacuum_vacuum_cost_limit = 2000  # Default: -1 (uses vacuum_cost_limit)
autovacuum_vacuum_cost_delay = 2ms  # Default: 2ms
# Higher limit = faster vacuum, more I/O impact
```

### Logging Configuration

```ini
# Log slow queries
log_min_duration_statement = 1000  # Log queries > 1 second
# Set to 0 to log all queries (high overhead)

# Log checkpoints
log_checkpoints = on

# Log connections
log_connections = on
log_disconnections = on

# Log lock waits
log_lock_waits = on
deadlock_timeout = 1s

# Statement statistics
shared_preload_libraries = 'pg_stat_statements'
pg_stat_statements.track = all
```

### Workload-Specific Tuning

**OLTP (Many small transactions):**

```ini
# OLTP: fast commits, many connections
shared_buffers = 25% of RAM
work_mem = low (16-64MB)  # Many concurrent queries
checkpoint_completion_target = 0.9
synchronous_commit = on  # Data durability matters
random_page_cost = 1.1  # Assuming SSD
max_connections = 200-500  # Or use pooler
```

**OLAP (Analytics, few large queries):**

```ini
# OLAP: large queries, full table scans
shared_buffers = 25% of RAM
work_mem = high (256MB-1GB)  # Few concurrent queries
effective_cache_size = 75% of RAM
max_parallel_workers_per_gather = 8  # Parallel queries
random_page_cost = 4.0  # Seq scans often better
max_connections = 20-50  # Few concurrent users
```

**Mixed Workload:**

```ini
# Balance between OLTP and OLAP
shared_buffers = 25% of RAM
work_mem = 64-128MB
# Use SET work_mem for specific large queries
max_parallel_workers_per_gather = 4
```

## Key Questions to Understand

- How much should shared_buffers be?
- Why is work_mem dangerous to set too high?
- What settings differ for SSD vs HDD?

## Hands-On Exercises

### Exercise 1: Check Current Configuration

```sql
-- View memory settings
SELECT name, setting, unit, context
FROM pg_settings
WHERE name IN (
    'shared_buffers', 'effective_cache_size',
    'work_mem', 'maintenance_work_mem'
);

-- View connection settings
SELECT name, setting, unit
FROM pg_settings
WHERE name IN ('max_connections', 'superuser_reserved_connections');

-- View planner settings
SELECT name, setting
FROM pg_settings
WHERE name IN ('random_page_cost', 'seq_page_cost', 'effective_io_concurrency');

-- Check settings that need restart vs reload
SELECT name, setting, context
FROM pg_settings
WHERE context = 'postmaster';  -- Needs restart
```

### Exercise 2: Test work_mem Impact

```sql
-- Set low work_mem
SET work_mem = '4MB';

EXPLAIN ANALYZE
SELECT * FROM orders ORDER BY created_at;
-- Look for: Sort Method: external merge Disk: XXXkB

-- Set higher work_mem
SET work_mem = '256MB';

EXPLAIN ANALYZE
SELECT * FROM orders ORDER BY created_at;
-- Look for: Sort Method: quicksort Memory: XXXkB
```

### Exercise 3: Estimate Memory Usage

```sql
-- Estimate total potential memory usage
SELECT
    current_setting('max_connections')::int *
    pg_size_bytes(current_setting('work_mem')) as max_work_mem_total,
    pg_size_pretty(
        current_setting('max_connections')::int *
        pg_size_bytes(current_setting('work_mem'))
    ) as max_work_mem_pretty;

-- With shared_buffers
SELECT
    pg_size_pretty(pg_size_bytes(current_setting('shared_buffers'))) as shared_buffers,
    pg_size_pretty(
        pg_size_bytes(current_setting('shared_buffers')) +
        current_setting('max_connections')::int * pg_size_bytes(current_setting('work_mem'))
    ) as potential_total;
```

## Interview Deep Dive

### Question: "How would you tune PostgreSQL for a 64GB RAM server?"

**Answer:**
> "I'd start with: shared_buffers = 16GB (25%), effective_cache_size = 48GB (75%), maintenance_work_mem = 2GB. For work_mem, it depends on max_connections - with 200 connections and assuming 4 operations per query, I'd start with 16-32MB.
>
> For SSD storage: random_page_cost = 1.1, effective_io_concurrency = 200. For parallel queries, max_parallel_workers = 8 or more.
>
> I'd also enable pg_stat_statements to track query performance, set log_min_duration_statement = 1000 to log slow queries, and tune autovacuum based on write patterns. Then monitor and adjust based on actual workload."

### Question: "What's the risk of setting work_mem too high?"

**Answer:**
> "work_mem is per-operation, not per-query. A complex query with multiple sorts and hash joins might use work_mem 5-10 times. With 100 concurrent connections and work_mem = 1GB, theoretical peak is 500GB-1TB of memory!
>
> This causes OOM kills or swap thrashing. I keep the default low (16-64MB for OLTP) and either increase it per-session for analytics queries or use connection pooling to limit concurrent queries. Better to have sorts spill to disk occasionally than risk OOM."

## Key Takeaways

1. **shared_buffers** = 25% of RAM (up to ~8GB)
2. **work_mem** caution - multiplied by operations and connections
3. **random_page_cost** = 1.1 for SSD, 4.0 for HDD
4. **effective_cache_size** = 75% of RAM
5. **Enable pg_stat_statements** for query analysis

## Self-Assessment Questions

1. Why shouldn't shared_buffers be 75% of RAM?
2. How is work_mem multiplied in a single query?
3. What settings require a restart vs reload?
4. How do you tune for SSD vs HDD?
5. What does effective_cache_size actually do?

## Next Chapter

[Chapter 24: Monitoring and pg_stat Views →](./24_monitoring.md)

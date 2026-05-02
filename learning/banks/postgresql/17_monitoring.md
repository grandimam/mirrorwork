# Chapter 24: Monitoring and pg_stat Views

## Overview

PostgreSQL provides extensive statistics through system views. Monitoring these metrics helps you identify performance issues, track resource usage, and plan capacity. This chapter covers the essential monitoring queries and patterns.

## Learning Objectives

By the end of this chapter, you will:

- Monitor query performance with pg_stat_statements
- Track table and index statistics
- Identify performance bottlenecks
- Set up effective alerting

## Resources

| Resource | Time |
|----------|------|
| Read: PostgreSQL statistics collector | 30 min |
| Hands-on: Build monitoring queries | 30 min |

## Core Concepts

### pg_stat_statements

```sql
-- Enable the extension (in postgresql.conf)
-- shared_preload_libraries = 'pg_stat_statements'

CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Top queries by total time
SELECT
    LEFT(query, 60) as query,
    calls,
    ROUND(total_exec_time::numeric, 2) as total_ms,
    ROUND(mean_exec_time::numeric, 2) as mean_ms,
    ROUND((100 * total_exec_time / SUM(total_exec_time) OVER ())::numeric, 2) as pct
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 20;

-- Top queries by calls
SELECT
    LEFT(query, 60) as query,
    calls,
    ROUND(total_exec_time::numeric / 1000, 2) as total_sec,
    ROUND(mean_exec_time::numeric, 2) as mean_ms
FROM pg_stat_statements
ORDER BY calls DESC
LIMIT 20;

-- Queries with high mean time (slow queries)
SELECT
    LEFT(query, 80) as query,
    calls,
    ROUND(mean_exec_time::numeric, 2) as mean_ms,
    ROUND(stddev_exec_time::numeric, 2) as stddev_ms
FROM pg_stat_statements
WHERE calls > 100
ORDER BY mean_exec_time DESC
LIMIT 20;

-- Reset statistics (do periodically)
SELECT pg_stat_statements_reset();
```

### Table Statistics

```sql
-- Table activity
SELECT
    relname as table,
    seq_scan,
    seq_tup_read,
    idx_scan,
    idx_tup_fetch,
    n_tup_ins as inserts,
    n_tup_upd as updates,
    n_tup_del as deletes,
    n_live_tup as live_rows,
    n_dead_tup as dead_rows
FROM pg_stat_user_tables
ORDER BY seq_tup_read DESC;

-- Tables needing index (high seq scans)
SELECT
    relname as table,
    seq_scan,
    seq_tup_read,
    seq_tup_read / seq_scan as avg_seq_tup,
    idx_scan
FROM pg_stat_user_tables
WHERE seq_scan > 100
  AND seq_tup_read / seq_scan > 10000
ORDER BY seq_tup_read DESC;

-- Tables with bloat (high dead tuples)
SELECT
    relname as table,
    n_live_tup,
    n_dead_tup,
    ROUND(n_dead_tup * 100.0 / NULLIF(n_live_tup + n_dead_tup, 0), 2) as dead_pct,
    last_vacuum,
    last_autovacuum
FROM pg_stat_user_tables
WHERE n_dead_tup > 1000
ORDER BY n_dead_tup DESC;
```

### Index Statistics

```sql
-- Index usage
SELECT
    relname as table,
    indexrelname as index,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch,
    pg_size_pretty(pg_relation_size(indexrelid)) as size
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;

-- Unused indexes (candidates for removal)
SELECT
    relname as table,
    indexrelname as index,
    idx_scan,
    pg_size_pretty(pg_relation_size(indexrelid)) as size
FROM pg_stat_user_indexes
WHERE idx_scan = 0
  AND indexrelname NOT LIKE '%_pkey'
ORDER BY pg_relation_size(indexrelid) DESC;

-- Index efficiency (rows read vs fetched)
SELECT
    indexrelname as index,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch,
    CASE WHEN idx_tup_read > 0
         THEN ROUND(idx_tup_fetch::numeric / idx_tup_read, 2)
         ELSE 0 END as efficiency
FROM pg_stat_user_indexes
WHERE idx_scan > 1000
ORDER BY efficiency ASC;
```

### Connection and Activity

```sql
-- Current connections by state
SELECT
    state,
    count(*) as count,
    ROUND(count(*) * 100.0 / SUM(count(*)) OVER (), 1) as pct
FROM pg_stat_activity
WHERE backend_type = 'client backend'
GROUP BY state
ORDER BY count DESC;

-- Long-running queries
SELECT
    pid,
    NOW() - query_start as duration,
    state,
    LEFT(query, 60) as query
FROM pg_stat_activity
WHERE state != 'idle'
  AND query_start < NOW() - INTERVAL '1 minute'
ORDER BY query_start;

-- Blocked queries
SELECT
    blocked.pid as blocked_pid,
    blocked.query as blocked_query,
    blocking.pid as blocking_pid,
    blocking.query as blocking_query,
    NOW() - blocked.query_start as blocked_duration
FROM pg_stat_activity blocked
JOIN pg_stat_activity blocking
    ON blocking.pid = ANY(pg_blocking_pids(blocked.pid))
WHERE blocked.pid != blocking.pid;

-- Connection by application
SELECT
    application_name,
    count(*) as connections,
    count(*) FILTER (WHERE state = 'active') as active,
    count(*) FILTER (WHERE state = 'idle') as idle,
    count(*) FILTER (WHERE state = 'idle in transaction') as idle_in_txn
FROM pg_stat_activity
WHERE backend_type = 'client backend'
GROUP BY application_name
ORDER BY connections DESC;
```

### Cache Performance

```sql
-- Buffer cache hit ratio (should be > 99%)
SELECT
    ROUND(
        SUM(heap_blks_hit) * 100.0 / NULLIF(SUM(heap_blks_hit + heap_blks_read), 0),
        2
    ) as buffer_cache_hit_ratio
FROM pg_statio_user_tables;

-- Per-table cache hit ratio
SELECT
    relname as table,
    heap_blks_read,
    heap_blks_hit,
    ROUND(
        heap_blks_hit * 100.0 / NULLIF(heap_blks_hit + heap_blks_read, 0),
        2
    ) as hit_ratio
FROM pg_statio_user_tables
WHERE heap_blks_hit + heap_blks_read > 1000
ORDER BY hit_ratio ASC;

-- Index cache hit ratio
SELECT
    ROUND(
        SUM(idx_blks_hit) * 100.0 / NULLIF(SUM(idx_blks_hit + idx_blks_read), 0),
        2
    ) as index_cache_hit_ratio
FROM pg_statio_user_indexes;
```

### Database-Wide Metrics

```sql
-- Database statistics
SELECT
    datname,
    numbackends as connections,
    xact_commit,
    xact_rollback,
    blks_read,
    blks_hit,
    ROUND(blks_hit * 100.0 / NULLIF(blks_hit + blks_read, 0), 2) as cache_hit_ratio,
    tup_returned,
    tup_fetched,
    tup_inserted,
    tup_updated,
    tup_deleted,
    conflicts,
    deadlocks
FROM pg_stat_database
WHERE datname = current_database();

-- Checkpoint statistics
SELECT
    checkpoints_timed,
    checkpoints_req,
    checkpoint_write_time,
    checkpoint_sync_time,
    buffers_checkpoint,
    buffers_clean,
    buffers_backend
FROM pg_stat_bgwriter;
```

### Key Metrics to Alert On

```sql
-- Metrics dashboard query
SELECT
    -- Connections
    (SELECT count(*) FROM pg_stat_activity WHERE backend_type = 'client backend') as total_connections,
    (SELECT count(*) FROM pg_stat_activity WHERE state = 'active') as active_queries,
    (SELECT count(*) FROM pg_stat_activity WHERE state = 'idle in transaction') as idle_in_txn,

    -- Long queries
    (SELECT count(*) FROM pg_stat_activity
     WHERE state = 'active' AND query_start < NOW() - INTERVAL '1 minute') as long_queries,

    -- Replication lag (if replica)
    (SELECT EXTRACT(EPOCH FROM NOW() - pg_last_xact_replay_timestamp())
     WHERE pg_is_in_recovery()) as replication_lag_seconds,

    -- Cache hit ratio
    (SELECT ROUND(SUM(heap_blks_hit) * 100.0 / NULLIF(SUM(heap_blks_hit + heap_blks_read), 0), 2)
     FROM pg_statio_user_tables) as cache_hit_ratio,

    -- Dead tuples
    (SELECT SUM(n_dead_tup) FROM pg_stat_user_tables) as total_dead_tuples;

-- Alert thresholds:
-- connections > 80% of max_connections: WARNING
-- idle_in_txn > 10: WARNING (potential lock issues)
-- long_queries > 5: WARNING
-- replication_lag_seconds > 10: WARNING
-- cache_hit_ratio < 95: WARNING
```

## Key Questions to Understand

- How do you find the slowest queries?
- What indicates a table needs an index?
- How do you identify unused indexes?

## Hands-On Exercises

### Exercise 1: Build a Health Check Query

```sql
CREATE OR REPLACE FUNCTION database_health_check()
RETURNS TABLE (
    metric TEXT,
    value TEXT,
    status TEXT
) AS $$
BEGIN
    -- Connection usage
    RETURN QUERY
    SELECT
        'Connection Usage'::TEXT,
        (count(*) || '/' || current_setting('max_connections'))::TEXT,
        CASE WHEN count(*) > current_setting('max_connections')::INT * 0.8
             THEN 'CRITICAL'
             WHEN count(*) > current_setting('max_connections')::INT * 0.6
             THEN 'WARNING'
             ELSE 'OK'
        END::TEXT
    FROM pg_stat_activity;

    -- Cache hit ratio
    RETURN QUERY
    SELECT
        'Cache Hit Ratio'::TEXT,
        ROUND(SUM(heap_blks_hit) * 100.0 / NULLIF(SUM(heap_blks_hit + heap_blks_read), 0), 2)::TEXT || '%',
        CASE WHEN SUM(heap_blks_hit) * 100.0 / NULLIF(SUM(heap_blks_hit + heap_blks_read), 0) < 95
             THEN 'WARNING'
             ELSE 'OK'
        END::TEXT
    FROM pg_statio_user_tables;

    -- Dead tuples
    RETURN QUERY
    SELECT
        'Dead Tuples'::TEXT,
        SUM(n_dead_tup)::TEXT,
        CASE WHEN SUM(n_dead_tup) > 1000000 THEN 'WARNING' ELSE 'OK' END::TEXT
    FROM pg_stat_user_tables;
END;
$$ LANGUAGE plpgsql;

SELECT * FROM database_health_check();
```

### Exercise 2: Query Performance Report

```sql
-- Weekly query performance report
WITH query_stats AS (
    SELECT
        query,
        calls,
        total_exec_time,
        mean_exec_time,
        rows
    FROM pg_stat_statements
    WHERE calls > 100
)
SELECT
    LEFT(query, 80) as query,
    calls,
    ROUND(total_exec_time::numeric / 1000, 2) as total_seconds,
    ROUND(mean_exec_time::numeric, 2) as mean_ms,
    rows,
    ROUND(rows::numeric / calls, 2) as rows_per_call
FROM query_stats
ORDER BY total_exec_time DESC
LIMIT 50;
```

### Exercise 3: Table Maintenance Report

```sql
-- Tables needing attention
SELECT
    relname as table_name,
    pg_size_pretty(pg_relation_size(relid)) as size,
    n_live_tup as live_rows,
    n_dead_tup as dead_rows,
    ROUND(n_dead_tup * 100.0 / NULLIF(n_live_tup + n_dead_tup, 0), 2) as dead_pct,
    last_vacuum,
    last_autovacuum,
    last_analyze,
    CASE
        WHEN last_vacuum IS NULL AND last_autovacuum IS NULL THEN 'NEVER VACUUMED'
        WHEN n_dead_tup > n_live_tup * 0.2 THEN 'HIGH BLOAT'
        WHEN last_analyze < NOW() - INTERVAL '7 days' THEN 'STALE STATS'
        ELSE 'OK'
    END as status
FROM pg_stat_user_tables
WHERE n_live_tup > 10000
ORDER BY
    CASE
        WHEN last_vacuum IS NULL AND last_autovacuum IS NULL THEN 1
        WHEN n_dead_tup > n_live_tup * 0.2 THEN 2
        ELSE 3
    END,
    n_dead_tup DESC;
```

## Interview Deep Dive

### Question: "How do you identify slow queries in PostgreSQL?"

**Answer:**
> "Primary tool is pg_stat_statements extension - it tracks execution statistics for all queries. I sort by total_exec_time to find queries consuming the most time, and by mean_exec_time to find individually slow queries. I also set log_min_duration_statement to log queries over a threshold.
>
> For investigation, I use EXPLAIN ANALYZE to see actual execution. Key things to look for: sequential scans on large tables, high rows removed by filter (missing index), sorts spilling to disk (work_mem issue), and large differences between estimated and actual rows (stale statistics)."

### Question: "What metrics would you alert on for a PostgreSQL database?"

**Answer:**
> "Critical alerts: connection count approaching max_connections, replication lag exceeding threshold, disk space, long-running transactions blocking vacuum. Warning alerts: cache hit ratio below 95%, high dead tuple counts, long-running queries, elevated checkpoint frequency.
>
> I'd use pg_stat_activity for connections and blocking, pg_stat_replication for lag, pg_stat_user_tables for bloat, and pg_stat_bgwriter for checkpoint issues. For dashboards, I aggregate these into a health score and trend over time to catch gradual degradation."

## Key Takeaways

1. **pg_stat_statements** is essential for query analysis
2. **Cache hit ratio** should be > 95%
3. **Monitor idle in transaction** to catch lock issues
4. **Track dead tuples** to identify vacuum problems
5. **Unused indexes** waste resources

## Self-Assessment Questions

1. How do you find the most expensive queries?
2. What does low cache hit ratio indicate?
3. How do you identify tables needing indexes?
4. What's dangerous about "idle in transaction" connections?
5. How do you find unused indexes?

## Next Chapter

[Chapter 25: Backup and Recovery →](./25_backup_recovery.md)

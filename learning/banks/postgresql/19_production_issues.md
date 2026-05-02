# Chapter 26: Common Production Issues

## Overview

Production databases face predictable challenges. This chapter covers the most common issues, how to diagnose them quickly, and how to resolve them. Use this as a troubleshooting guide when things go wrong.

## Learning Objectives

By the end of this chapter, you will:

- Diagnose common performance issues
- Fix urgent production problems
- Handle database emergencies
- Prevent issues proactively

## Resources

| Resource | Time |
|----------|------|
| Read: PostgreSQL troubleshooting guides | 30 min |
| Practice: Simulate and resolve issues | 45 min |

## Core Concepts

### Issue Quick Reference

| Symptom | Likely Cause | Quick Fix |
|---------|-------------|-----------|
| Slow queries | Missing indexes, bad stats | EXPLAIN ANALYZE, ANALYZE |
| High CPU | Bad query, seq scans | Find slow query, add index |
| High memory | Too many connections | Use PgBouncer |
| Disk full | WAL bloat, table bloat | Check pg_wal, VACUUM |
| Connection refused | max_connections | Use pooler, increase limit |
| Replication lag | Slow replica, network | Check replica I/O |
| Locks/blocking | Long transaction | Kill query, add timeouts |
| Crash/restart | OOM, disk full | Check logs, free resources |

### Issue 1: Slow Queries

```sql
-- Find slow queries
SELECT
    LEFT(query, 80) as query,
    calls,
    ROUND(mean_exec_time::numeric, 2) as mean_ms,
    ROUND(total_exec_time::numeric / 1000, 2) as total_sec
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 20;

-- Currently running slow queries
SELECT
    pid,
    NOW() - query_start as duration,
    state,
    LEFT(query, 60) as query
FROM pg_stat_activity
WHERE state = 'active'
  AND query NOT LIKE '%pg_stat_activity%'
ORDER BY query_start;

-- Diagnose with EXPLAIN ANALYZE
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM orders WHERE user_id = 123;

-- Common fixes:
-- 1. Add missing index
CREATE INDEX idx_orders_user ON orders(user_id);

-- 2. Update statistics
ANALYZE orders;

-- 3. Rewrite query
-- See Chapter 13: Query Anti-Patterns
```

### Issue 2: Connection Exhaustion

```sql
-- Check connection count
SELECT count(*) FROM pg_stat_activity;
SHOW max_connections;

-- Connections by state
SELECT state, count(*)
FROM pg_stat_activity
GROUP BY state;

-- Connections by application
SELECT application_name, count(*)
FROM pg_stat_activity
GROUP BY application_name
ORDER BY count DESC;

-- Find idle in transaction (potential lock holders)
SELECT
    pid,
    NOW() - xact_start as txn_duration,
    NOW() - query_start as query_duration,
    state,
    LEFT(query, 50) as query
FROM pg_stat_activity
WHERE state = 'idle in transaction'
ORDER BY xact_start;

-- Kill idle in transaction connections
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE state = 'idle in transaction'
  AND xact_start < NOW() - INTERVAL '10 minutes';

-- Solutions:
-- 1. Use connection pooler (PgBouncer)
-- 2. Increase max_connections (with more RAM)
-- 3. Add connection timeout in application
-- 4. Set idle_in_transaction_session_timeout
SET idle_in_transaction_session_timeout = '5min';
```

### Issue 3: Disk Space

```sql
-- Check database sizes
SELECT
    datname,
    pg_size_pretty(pg_database_size(datname)) as size
FROM pg_database
ORDER BY pg_database_size(datname) DESC;

-- Check table sizes
SELECT
    relname as table,
    pg_size_pretty(pg_total_relation_size(relid)) as total_size,
    pg_size_pretty(pg_relation_size(relid)) as data_size,
    pg_size_pretty(pg_indexes_size(relid)) as index_size
FROM pg_stat_user_tables
ORDER BY pg_total_relation_size(relid) DESC
LIMIT 20;

-- Check WAL size
SELECT pg_size_pretty(SUM(size)) as wal_size
FROM pg_ls_waldir();

-- Check for bloat
SELECT
    relname,
    n_dead_tup,
    pg_size_pretty(pg_relation_size(relid)) as size
FROM pg_stat_user_tables
ORDER BY n_dead_tup DESC
LIMIT 10;

-- Solutions:
-- 1. VACUUM to allow space reuse
VACUUM VERBOSE large_table;

-- 2. VACUUM FULL to reclaim space (exclusive lock!)
VACUUM FULL large_table;

-- 3. Drop old data
DELETE FROM logs WHERE created_at < NOW() - INTERVAL '90 days';
VACUUM logs;

-- 4. Check WAL retention
SHOW wal_keep_size;
-- Reduce if too high

-- 5. Check for long-running transactions blocking cleanup
SELECT pid, xact_start, query
FROM pg_stat_activity
WHERE xact_start < NOW() - INTERVAL '1 hour';
```

### Issue 4: Locks and Blocking

```sql
-- Find blocked queries
SELECT
    blocked.pid AS blocked_pid,
    blocked.query AS blocked_query,
    blocking.pid AS blocking_pid,
    blocking.query AS blocking_query,
    NOW() - blocked.query_start AS blocked_duration
FROM pg_stat_activity blocked
JOIN pg_stat_activity blocking
    ON blocking.pid = ANY(pg_blocking_pids(blocked.pid))
WHERE blocked.pid != blocking.pid;

-- Detailed lock information
SELECT
    pg_locks.pid,
    pg_class.relname,
    pg_locks.mode,
    pg_locks.granted,
    pg_stat_activity.query
FROM pg_locks
LEFT JOIN pg_class ON pg_locks.relation = pg_class.oid
LEFT JOIN pg_stat_activity ON pg_locks.pid = pg_stat_activity.pid
WHERE NOT pg_locks.granted
ORDER BY pg_locks.pid;

-- Kill blocking query
SELECT pg_cancel_backend(blocking_pid);  -- graceful
SELECT pg_terminate_backend(blocking_pid);  -- force

-- Prevent future issues:
-- 1. Set lock timeout
SET lock_timeout = '10s';

-- 2. Set statement timeout
SET statement_timeout = '30s';

-- 3. Use NOWAIT where appropriate
SELECT * FROM orders WHERE id = 1 FOR UPDATE NOWAIT;
```

### Issue 5: Replication Lag

```sql
-- On primary: check replication status
SELECT
    application_name,
    client_addr,
    state,
    pg_size_pretty(pg_wal_lsn_diff(sent_lsn, replay_lsn)) as lag
FROM pg_stat_replication;

-- On replica: check lag
SELECT
    CASE WHEN pg_last_wal_receive_lsn() = pg_last_wal_replay_lsn()
         THEN 0
         ELSE EXTRACT(EPOCH FROM NOW() - pg_last_xact_replay_timestamp())
    END AS lag_seconds;

-- Causes and solutions:
-- 1. Network issues: check connectivity, bandwidth
-- 2. Replica I/O bottleneck: check disk utilization
-- 3. Long-running queries on replica blocking replay
SELECT pid, query FROM pg_stat_activity
WHERE backend_type = 'client backend'
  AND state = 'active';

-- 4. max_standby_streaming_delay too low
SHOW max_standby_streaming_delay;
-- Increase if reads are more important than lag

-- 5. Increase wal_keep_size if replica disconnects
SHOW wal_keep_size;
```

### Issue 6: High CPU

```sql
-- Find CPU-intensive queries
SELECT
    pid,
    NOW() - query_start as duration,
    state,
    LEFT(query, 80) as query
FROM pg_stat_activity
WHERE state = 'active'
ORDER BY query_start;

-- Often caused by:
-- 1. Sequential scans on large tables
-- 2. Inefficient queries (N+1, correlated subqueries)
-- 3. Missing indexes

-- Check for sequential scans
SELECT
    relname,
    seq_scan,
    seq_tup_read,
    idx_scan,
    idx_tup_fetch
FROM pg_stat_user_tables
WHERE seq_scan > 100
ORDER BY seq_tup_read DESC;

-- Solutions:
-- 1. Add indexes for common queries
-- 2. Rewrite inefficient queries
-- 3. Cancel runaway queries
SELECT pg_cancel_backend(pid);
```

### Issue 7: Memory Issues (OOM)

```bash
# Check PostgreSQL logs for OOM
grep -i "out of memory\|oom" /var/log/postgresql/*.log

# Check Linux dmesg for OOM killer
dmesg | grep -i "killed process"
```

```sql
-- Check memory-related settings
SELECT name, setting, unit
FROM pg_settings
WHERE name IN ('shared_buffers', 'work_mem', 'maintenance_work_mem', 'max_connections');

-- work_mem issue: too high with many connections
-- Reduce work_mem or use connection pooling

-- Many parallel workers
SELECT count(*) FROM pg_stat_activity WHERE backend_type LIKE '%worker%';

-- Solutions:
-- 1. Reduce work_mem
-- 2. Reduce max_connections + use pooler
-- 3. Reduce max_parallel_workers
-- 4. Increase server RAM or add swap (temporary)
```

### Emergency Procedures

```sql
-- Kill all non-superuser connections
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE pid != pg_backend_pid()
  AND usename != 'postgres';

-- Cancel all active queries
SELECT pg_cancel_backend(pid)
FROM pg_stat_activity
WHERE state = 'active'
  AND pid != pg_backend_pid();

-- Put database in single-user mode (requires restart)
-- Stop PostgreSQL, start with:
-- postgres --single -D /var/lib/postgresql/data mydb
```

## Key Questions to Understand

- How do you quickly identify a production issue?
- What's the safest way to kill a blocking query?
- How do you prevent common issues proactively?

## Hands-On Exercises

### Exercise 1: Create and Resolve a Blocking Situation

```sql
-- Terminal 1: Start a blocking transaction
BEGIN;
UPDATE accounts SET balance = 100 WHERE id = 1;
-- Don't commit!

-- Terminal 2: Try to update same row
UPDATE accounts SET balance = 200 WHERE id = 1;
-- This blocks

-- Terminal 3: Diagnose and resolve
SELECT blocked.pid, blocking.pid, blocking.query
FROM pg_stat_activity blocked
JOIN pg_stat_activity blocking
    ON blocking.pid = ANY(pg_blocking_pids(blocked.pid));

-- Kill blocking query
SELECT pg_terminate_backend(<blocking_pid>);
```

### Exercise 2: Simulate and Fix Disk Space Issue

```sql
-- Create a large table
CREATE TABLE space_test AS
SELECT i, repeat('x', 1000) as data
FROM generate_series(1, 1000000) i;

-- Create bloat
UPDATE space_test SET data = repeat('y', 1000);

-- Check size
SELECT pg_size_pretty(pg_table_size('space_test'));

-- Fix
VACUUM FULL space_test;
SELECT pg_size_pretty(pg_table_size('space_test'));

-- Clean up
DROP TABLE space_test;
```

### Exercise 3: Build Monitoring Dashboard

```sql
-- Create a health check view
CREATE VIEW database_health AS
SELECT
    (SELECT count(*) FROM pg_stat_activity) as total_connections,
    (SELECT count(*) FROM pg_stat_activity WHERE state = 'active') as active_queries,
    (SELECT count(*) FROM pg_stat_activity WHERE state = 'idle in transaction') as idle_in_txn,
    (SELECT ROUND(SUM(heap_blks_hit) * 100.0 / NULLIF(SUM(heap_blks_hit + heap_blks_read), 0), 2)
     FROM pg_statio_user_tables) as cache_hit_ratio,
    (SELECT SUM(n_dead_tup) FROM pg_stat_user_tables) as total_dead_tuples,
    (SELECT pg_size_pretty(pg_database_size(current_database()))) as db_size;

SELECT * FROM database_health;
```

## Interview Deep Dive

### Question: "The database is slow. How do you diagnose it?"

**Answer:**
> "Systematic approach: 1) Check pg_stat_activity for long-running or blocked queries. 2) Check pg_stat_statements for queries with high total_time or mean_time. 3) Look at system metrics - CPU (bad queries), memory (too many connections), disk I/O (missing indexes, bloat).
>
> For slow queries: EXPLAIN ANALYZE to see the plan. Common causes: missing indexes (seq scans), outdated statistics (wrong estimates), N+1 queries, correlated subqueries. Quick wins: run ANALYZE, add obvious missing indexes, kill any runaway queries. For persistent issues, deeper query optimization needed."

### Question: "How do you handle a database emergency?"

**Answer:**
> "First, assess severity - is the database up? Can users write? Then stabilize: kill any obvious runaway queries with pg_cancel_backend, check for blocking and resolve with pg_terminate_backend if needed. Check disk space - if critical, drop old data or stop archiving temporarily.
>
> Communicate status to stakeholders. Once stable, diagnose root cause: check PostgreSQL logs, review recent changes (deployments, data migrations), check monitoring trends. Document what happened and implement preventive measures - better monitoring, query timeouts, connection limits. Post-mortem to prevent recurrence."

## Key Takeaways

1. **Monitor proactively** - catch issues before users notice
2. **Know the quick fixes** - indexes, ANALYZE, VACUUM
3. **Timeout everything** - lock_timeout, statement_timeout
4. **Connection pool** - PgBouncer prevents connection exhaustion
5. **Test on staging** - catch issues before production

## Self-Assessment Questions

1. How do you find and kill a blocking query?
2. What causes disk space to fill up?
3. How do you diagnose high CPU usage?
4. When would you use pg_cancel_backend vs pg_terminate_backend?
5. What are the first things to check when "the database is slow"?

## Conclusion

Congratulations on completing the PostgreSQL curriculum! You now have the knowledge to:

- Design efficient schemas and write optimized queries
- Create and maintain effective indexes
- Understand and tune transaction behavior
- Scale PostgreSQL with partitioning and replication
- Monitor, backup, and troubleshoot production databases

Keep practicing with real databases, and refer back to these chapters when you encounter specific challenges. Good luck with your interviews and production systems!

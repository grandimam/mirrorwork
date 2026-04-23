# Chapter 18: Vacuum and Bloat

## Overview

VACUUM is PostgreSQL's garbage collector - it reclaims space from dead tuples and prevents transaction ID wraparound. Understanding VACUUM is critical for maintaining database performance over time.

## Learning Objectives

By the end of this chapter, you will:

- Understand why VACUUM is necessary
- Configure autovacuum for your workload
- Diagnose and fix table bloat
- Prevent transaction ID wraparound

## Resources

| Resource | Time |
|----------|------|
| Read: https://www.postgresql.org/docs/current/routine-vacuuming.html | 30 min |
| Hands-on: Monitor and tune autovacuum | 30 min |

## Core Concepts

### Why VACUUM is Necessary

```
MVCC creates multiple row versions:
- UPDATE: creates new version, old version becomes dead
- DELETE: marks row as dead
- Dead tuples accumulate until VACUUM

Without VACUUM:
1. Table bloat - files grow, more I/O
2. Index bloat - indexes contain dead pointers
3. Transaction ID wraparound - eventually catastrophic
```

### VACUUM Operations

```sql
-- Basic VACUUM: marks dead tuples as reusable
VACUUM accounts;

-- VACUUM ANALYZE: also updates statistics
VACUUM ANALYZE accounts;

-- VACUUM VERBOSE: shows detailed progress
VACUUM VERBOSE accounts;

-- VACUUM FULL: rewrites table (exclusive lock!)
VACUUM FULL accounts;  -- Use only as last resort

-- What VACUUM does:
-- 1. Scans table for dead tuples
-- 2. Marks their space as available for reuse
-- 3. Updates visibility map (enables index-only scans)
-- 4. Updates free space map
-- 5. Freezes old tuples (prevents wraparound)

-- What VACUUM does NOT do:
-- - Shrink file size (space reused, not returned to OS)
-- - Block normal operations (concurrent access OK)
```

### VACUUM vs VACUUM FULL

| Operation | Table Lock | Disk Space | Speed | Use When |
|-----------|-----------|------------|-------|----------|
| VACUUM | No lock | No change | Fast | Regular maintenance |
| VACUUM FULL | Exclusive lock | Reclaims | Slow | Severe bloat only |

```sql
-- Alternative to VACUUM FULL: pg_repack
-- Rewrites table without exclusive lock
-- Install: CREATE EXTENSION pg_repack;
-- Use: pg_repack -t accounts
```

### Autovacuum

```sql
-- Autovacuum runs automatically based on thresholds

-- Check autovacuum settings
SELECT name, setting
FROM pg_settings
WHERE name LIKE '%autovacuum%';

-- Key settings:
-- autovacuum = on                        -- enabled by default
-- autovacuum_vacuum_threshold = 50       -- base dead tuples
-- autovacuum_vacuum_scale_factor = 0.2   -- 20% of table
-- autovacuum_analyze_threshold = 50
-- autovacuum_analyze_scale_factor = 0.1  -- 10% of table

-- Vacuum triggers when:
-- dead_tuples > autovacuum_vacuum_threshold +
--               autovacuum_vacuum_scale_factor * table_rows

-- For 1M row table: 50 + 0.2 * 1000000 = 200,050 dead tuples
```

### Tuning Autovacuum per Table

```sql
-- High-write tables may need more aggressive settings
ALTER TABLE hot_table SET (
    autovacuum_vacuum_threshold = 50,
    autovacuum_vacuum_scale_factor = 0.01,    -- 1% instead of 20%
    autovacuum_analyze_threshold = 50,
    autovacuum_analyze_scale_factor = 0.01,
    autovacuum_vacuum_cost_delay = 0          -- no throttling
);

-- For append-only tables (insert only, no updates/deletes)
ALTER TABLE log_table SET (
    autovacuum_enabled = false  -- no dead tuples anyway
);
-- Still need periodic VACUUM FREEZE for wraparound prevention!
```

### Monitoring Autovacuum

```sql
-- Check vacuum status per table
SELECT
    relname,
    n_live_tup,
    n_dead_tup,
    n_dead_tup * 100.0 / NULLIF(n_live_tup + n_dead_tup, 0) as dead_pct,
    last_vacuum,
    last_autovacuum,
    last_analyze,
    last_autoanalyze
FROM pg_stat_user_tables
ORDER BY n_dead_tup DESC;

-- Check autovacuum workers
SELECT
    datname,
    usename,
    pid,
    state,
    backend_type,
    query
FROM pg_stat_activity
WHERE backend_type = 'autovacuum worker';

-- Check vacuum progress
SELECT
    relid::regclass as table,
    phase,
    heap_blks_total,
    heap_blks_scanned,
    heap_blks_vacuumed,
    ROUND(100.0 * heap_blks_vacuumed / NULLIF(heap_blks_total, 0), 1) as pct_complete
FROM pg_stat_progress_vacuum;
```

### Transaction ID Wraparound

```sql
-- PostgreSQL uses 32-bit transaction IDs (2 billion usable)
-- Old transactions must be "frozen" to prevent wraparound

-- Check wraparound risk
SELECT
    datname,
    age(datfrozenxid) as xid_age,
    current_setting('autovacuum_freeze_max_age')::INT as freeze_max,
    ROUND(100.0 * age(datfrozenxid) / current_setting('autovacuum_freeze_max_age')::INT, 1) as pct
FROM pg_database
WHERE datname NOT LIKE 'template%'
ORDER BY age(datfrozenxid) DESC;

-- Check table-level
SELECT
    c.relname,
    age(c.relfrozenxid) as xid_age,
    pg_size_pretty(pg_table_size(c.oid)) as size
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind = 'r' AND n.nspname NOT IN ('pg_catalog', 'information_schema')
ORDER BY age(c.relfrozenxid) DESC
LIMIT 10;

-- Emergency freeze if needed
VACUUM FREEZE accounts;
```

### Diagnosing Bloat

```sql
-- Estimate table bloat using pgstattuple
CREATE EXTENSION IF NOT EXISTS pgstattuple;

SELECT
    table_len,
    tuple_count,
    dead_tuple_count,
    dead_tuple_len,
    ROUND(dead_tuple_len * 100.0 / table_len, 2) as dead_pct,
    free_space,
    ROUND(free_space * 100.0 / table_len, 2) as free_pct
FROM pgstattuple('accounts');

-- Quick estimate without scanning whole table
SELECT
    relname,
    pg_size_pretty(pg_table_size(relid)) as table_size,
    n_live_tup,
    n_dead_tup
FROM pg_stat_user_tables
WHERE n_dead_tup > 10000
ORDER BY n_dead_tup DESC;

-- Compare actual vs estimated size
SELECT
    relname,
    pg_size_pretty(pg_table_size(relid)) as actual_size,
    pg_size_pretty(n_live_tup * avg_row_width) as estimated_live_size
FROM pg_stat_user_tables
JOIN (
    SELECT relid, AVG(length(t.*::text)) as avg_row_width
    FROM pg_stat_user_tables, accounts t  -- replace 'accounts' with table
    GROUP BY relid
) a USING (relid);
```

## Key Questions to Understand

- Why do dead tuples accumulate?
- What's the difference between VACUUM and VACUUM FULL?
- How do you configure autovacuum for high-write tables?

## Hands-On Exercises

### Exercise 1: Create and Clean Bloat

```sql
-- Create bloat
CREATE TABLE bloat_test (id INT, data TEXT);
INSERT INTO bloat_test SELECT i, repeat('x', 100) FROM generate_series(1, 100000) i;

-- Check initial size
SELECT pg_size_pretty(pg_table_size('bloat_test'));

-- Create dead tuples
UPDATE bloat_test SET data = repeat('y', 100);

-- Check dead tuples
SELECT n_dead_tup FROM pg_stat_user_tables WHERE relname = 'bloat_test';

-- Regular vacuum
VACUUM VERBOSE bloat_test;

-- Size unchanged, but space is reusable
SELECT pg_size_pretty(pg_table_size('bloat_test'));

-- VACUUM FULL to reclaim
VACUUM FULL bloat_test;
SELECT pg_size_pretty(pg_table_size('bloat_test'));
```

### Exercise 2: Monitor Autovacuum

```sql
-- Create high-churn table
CREATE TABLE churn_test (id SERIAL PRIMARY KEY, value INT);

-- Watch autovacuum in action
-- Terminal 1:
WATCH 1 "SELECT relname, n_dead_tup, last_autovacuum FROM pg_stat_user_tables WHERE relname = 'churn_test'"

-- Terminal 2:
INSERT INTO churn_test (value) SELECT i FROM generate_series(1, 100000) i;
UPDATE churn_test SET value = value + 1;
-- Wait for autovacuum to kick in
```

### Exercise 3: Tune Autovacuum

```sql
-- Set aggressive autovacuum for hot table
ALTER TABLE churn_test SET (
    autovacuum_vacuum_threshold = 100,
    autovacuum_vacuum_scale_factor = 0.01
);

-- Now triggers at: 100 + 0.01 * 100000 = 1100 dead tuples
-- Instead of: 50 + 0.2 * 100000 = 20050 dead tuples

-- Verify settings
SELECT relname, reloptions
FROM pg_class
WHERE relname = 'churn_test';
```

## Interview Deep Dive

### Question: "What is VACUUM and why is it important?"

**Answer:**
> "VACUUM is PostgreSQL's garbage collector. Due to MVCC, UPDATE and DELETE don't immediately remove rows - they leave dead tuples. VACUUM marks this space as reusable, updates the visibility map for index-only scans, and freezes old tuples to prevent transaction ID wraparound.
>
> Without VACUUM: tables bloat (more storage, slower scans), indexes contain dead pointers, and eventually you hit wraparound where the database refuses writes. Autovacuum runs automatically based on dead tuple thresholds. For high-write tables, I tune autovacuum to run more aggressively."

### Question: "How do you handle severe table bloat?"

**Answer:**
> "First, I diagnose with pg_stat_user_tables (n_dead_tup) or pgstattuple extension. If autovacuum is keeping up, space is reusable even if not reclaimed.
>
> For severe bloat: VACUUM FULL rewrites the table and reclaims space, but requires exclusive lock - downtime. Better options: pg_repack does the same without exclusive lock, or CREATE TABLE AS then swap names. I also investigate root cause - maybe autovacuum can't keep up (tune it), or long-running transactions are blocking cleanup. Prevention is better: tune autovacuum for high-churn tables, monitor dead tuple ratios, avoid patterns creating excessive updates."

## Key Takeaways

1. **VACUUM** marks dead space as reusable (doesn't shrink)
2. **VACUUM FULL** reclaims space but locks table
3. **Autovacuum** runs automatically based on thresholds
4. **Tune per table** for high-write workloads
5. **Transaction ID wraparound** is prevented by VACUUM FREEZE

## Self-Assessment Questions

1. Why doesn't regular VACUUM shrink table files?
2. How do you calculate when autovacuum will run?
3. What causes transaction ID wraparound?
4. When would you use VACUUM FULL?
5. How do you tune autovacuum for a hot table?

## Next Chapter

[Chapter 19: Connection Pooling (PgBouncer) →](./19_connection_pooling.md)

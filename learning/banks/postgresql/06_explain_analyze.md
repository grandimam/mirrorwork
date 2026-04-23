# Chapter 10: EXPLAIN and EXPLAIN ANALYZE

## Overview

EXPLAIN is your primary tool for understanding query performance. Learning to read and interpret query plans is essential for optimizing PostgreSQL queries. This chapter teaches you to identify bottlenecks and understand planner decisions.

## Learning Objectives

By the end of this chapter, you will:

- Read and interpret EXPLAIN output
- Use EXPLAIN ANALYZE for actual timing
- Identify performance bottlenecks
- Understand cost estimates and actual execution

## Resources

| Resource | Time |
|----------|------|
| Read: https://www.postgresql.org/docs/current/using-explain.html | 30 min |
| Hands-on: Analyze real queries | 1 hr |

## Core Concepts

### EXPLAIN vs EXPLAIN ANALYZE

```sql
-- EXPLAIN: shows plan WITHOUT executing
EXPLAIN SELECT * FROM orders WHERE user_id = 100;
-- Shows estimated costs and row counts
-- Safe for slow queries (doesn't run them)

-- EXPLAIN ANALYZE: executes and shows actual metrics
EXPLAIN ANALYZE SELECT * FROM orders WHERE user_id = 100;
-- Shows actual time and row counts
-- Actually runs the query!

-- WARNING: EXPLAIN ANALYZE runs the query!
EXPLAIN ANALYZE DELETE FROM orders;  -- THIS DELETES DATA!
-- Use transaction to prevent:
BEGIN;
EXPLAIN ANALYZE DELETE FROM orders;
ROLLBACK;
```

### Reading EXPLAIN Output

```sql
EXPLAIN ANALYZE
SELECT * FROM orders
WHERE user_id = 123 AND created_at > '2024-01-01'
ORDER BY created_at DESC
LIMIT 10;

-- Output:
Limit  (cost=0.43..25.32 rows=10 width=48) (actual time=0.052..0.089 rows=10 loops=1)
  ->  Index Scan Backward using idx_orders_user_created on orders
        (cost=0.43..12345.67 rows=5000 width=48) (actual time=0.051..0.085 rows=10 loops=1)
        Index Cond: ((user_id = 123) AND (created_at > '2024-01-01'))
Planning Time: 0.234 ms
Execution Time: 0.112 ms
```

**Breaking Down the Output:**

```
Limit  (cost=0.43..25.32 rows=10 width=48) (actual time=0.052..0.089 rows=10 loops=1)
       ├─────────────────────────────────┤ ├────────────────────────────────────────┤
               ESTIMATED                              ACTUAL

cost=0.43..25.32
  └─ startup cost: 0.43 (time before first row)
  └─ total cost: 25.32 (arbitrary units, not milliseconds!)

rows=10
  └─ estimated rows to return

width=48
  └─ estimated average row size in bytes

actual time=0.052..0.089
  └─ actual wall-clock time in milliseconds
  └─ 0.052ms to first row, 0.089ms total

rows=10
  └─ actual rows returned

loops=1
  └─ how many times this node executed
```

### EXPLAIN Options

```sql
-- All options together
EXPLAIN (ANALYZE, BUFFERS, COSTS, TIMING, FORMAT TEXT)
SELECT * FROM orders WHERE user_id = 100;

-- ANALYZE: actually run the query
-- BUFFERS: show buffer usage (cache hits/misses)
-- COSTS: show cost estimates (default on)
-- TIMING: show timing per node (default on with ANALYZE)
-- FORMAT: TEXT (default), JSON, YAML, XML

-- JSON format (for tools like explain.depesz.com)
EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
SELECT * FROM orders WHERE user_id = 100;

-- Verbose (shows column details)
EXPLAIN (ANALYZE, VERBOSE)
SELECT * FROM orders WHERE user_id = 100;
```

### Common Plan Node Types

```sql
-- Sequential Scan: reads entire table
Seq Scan on orders  (cost=0.00..15406.00 rows=1000000 width=48)
-- When: no suitable index, or returning most rows

-- Index Scan: uses index, then fetches from heap
Index Scan using idx_orders_user on orders  (cost=0.43..8.45 rows=1 width=48)
  Index Cond: (user_id = 123)
-- When: good selectivity, need columns not in index

-- Index Only Scan: reads only index
Index Only Scan using idx_covering on orders  (cost=0.43..8.45 rows=1 width=48)
  Index Cond: (user_id = 123)
  Heap Fetches: 0
-- When: all needed columns in index, pages all-visible

-- Bitmap Index Scan + Bitmap Heap Scan
Bitmap Heap Scan on orders  (cost=42.12..3902.45 rows=2000 width=48)
  Recheck Cond: (user_id = 123)
  ->  Bitmap Index Scan on idx_orders_user  (cost=0.00..41.62 rows=2000 width=0)
        Index Cond: (user_id = 123)
-- When: moderate selectivity, random I/O would be inefficient

-- Nested Loop: for each outer row, scan inner
Nested Loop  (cost=0.43..16.53 rows=1 width=96)
  ->  Index Scan using users_pkey on users  (cost=0.00..8.02 rows=1 width=48)
  ->  Index Scan using idx_orders_user on orders  (cost=0.43..8.50 rows=1 width=48)
-- When: small outer set, indexed inner

-- Hash Join: build hash table, probe it
Hash Join  (cost=15.00..3902.00 rows=10000 width=96)
  Hash Cond: (orders.user_id = users.id)
  ->  Seq Scan on orders  (cost=0.00..3500.00 rows=100000 width=48)
  ->  Hash  (cost=10.00..10.00 rows=100 width=48)
        ->  Seq Scan on users  (cost=0.00..10.00 rows=100 width=48)
-- When: medium-sized tables, equality join

-- Merge Join: both sides sorted
Merge Join  (cost=42.12..88.32 rows=1000 width=96)
  Merge Cond: (orders.user_id = users.id)
  ->  Index Scan using idx_orders_user on orders  (cost=...)
  ->  Index Scan using users_pkey on users  (cost=...)
-- When: both inputs already sorted

-- Sort
Sort  (cost=100.00..102.50 rows=1000 width=48)
  Sort Key: created_at DESC
  Sort Method: quicksort  Memory: 71kB
-- When: ORDER BY without supporting index

-- Aggregate
Aggregate  (cost=15406.00..15406.01 rows=1 width=8)
  ->  Seq Scan on orders
-- When: COUNT, SUM, AVG, etc.
```

### Identifying Bottlenecks

```sql
-- Look for these warning signs:

-- 1. Seq Scan on large tables
Seq Scan on orders  (cost=0.00..154060.00 rows=10000000 width=48)
  Filter: (user_id = 123)
  Rows Removed by Filter: 9999000  -- filtered 99.99% of rows!
-- Solution: Add index on user_id

-- 2. Large difference between estimated and actual rows
Index Scan using idx on orders  (cost=... rows=100) (actual ... rows=50000)
-- estimated 100, got 50000 - statistics outdated!
-- Solution: ANALYZE orders

-- 3. High buffer reads vs hits
Buffers: shared hit=10 read=5000  -- 5000 disk reads!
-- Solution: Increase shared_buffers, optimize query

-- 4. Sort using disk
Sort Method: external merge  Disk: 100000kB
-- Sorting spilled to disk (work_mem too small)
-- Solution: Increase work_mem for this query

-- 5. Many loops
->  Index Scan  (... loops=10000)
-- Nested loop executed 10000 times
-- Consider if hash join would be better
```

### Comparing Plans

```sql
-- Before optimization
EXPLAIN ANALYZE
SELECT * FROM orders WHERE status = 'pending';
-- Seq Scan, 500ms

-- After adding index
CREATE INDEX idx_orders_status ON orders(status);
EXPLAIN ANALYZE
SELECT * FROM orders WHERE status = 'pending';
-- Index Scan, 50ms

-- Compare key metrics:
-- 1. Total execution time
-- 2. Number of rows processed vs returned
-- 3. Buffer hits vs reads
-- 4. Scan type (seq vs index)
```

## Key Questions to Understand

- What's the difference between EXPLAIN and EXPLAIN ANALYZE?
- How do you interpret cost numbers?
- What do actual vs estimated rows tell you?

## Hands-On Exercises

### Exercise 1: Analyze a Slow Query

```sql
CREATE TABLE large_orders AS
SELECT
    i as id,
    (random() * 10000)::INTEGER as user_id,
    (ARRAY['pending', 'processing', 'completed', 'cancelled'])[floor(random() * 4 + 1)::INTEGER] as status,
    (random() * 1000)::DECIMAL(10,2) as amount,
    NOW() - (random() * 365 || ' days')::INTERVAL as created_at
FROM generate_series(1, 1000000) i;

-- Query without indexes
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM large_orders
WHERE user_id = 100 AND status = 'pending'
ORDER BY created_at DESC
LIMIT 10;

-- Identify issues and fix
CREATE INDEX idx_large_orders_composite ON large_orders(user_id, status, created_at DESC);

-- Compare plans
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM large_orders
WHERE user_id = 100 AND status = 'pending'
ORDER BY created_at DESC
LIMIT 10;
```

### Exercise 2: Statistics Mismatch

```sql
-- Create data with skewed distribution
CREATE TABLE skewed_data (
    id SERIAL PRIMARY KEY,
    category VARCHAR(10)
);

INSERT INTO skewed_data (category)
SELECT
    CASE WHEN random() < 0.99 THEN 'common' ELSE 'rare' END
FROM generate_series(1, 1000000);

CREATE INDEX idx_skewed_category ON skewed_data(category);

-- Before ANALYZE
EXPLAIN ANALYZE SELECT * FROM skewed_data WHERE category = 'rare';
-- Check estimated vs actual rows

-- Update statistics
ANALYZE skewed_data;

-- After ANALYZE
EXPLAIN ANALYZE SELECT * FROM skewed_data WHERE category = 'rare';
-- Estimates should be more accurate
```

### Exercise 3: Use explain.depesz.com

```sql
-- Generate JSON explain output
EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
SELECT o.*, u.email
FROM large_orders o
JOIN users u ON u.id = o.user_id
WHERE o.status = 'pending'
ORDER BY o.created_at DESC
LIMIT 100;

-- Copy output and paste at https://explain.depesz.com
-- for visual analysis
```

## Interview Deep Dive

### Question: "How do you use EXPLAIN to optimize a query?"

**Answer:**
> "I start with EXPLAIN ANALYZE BUFFERS to see actual execution. Key things I check: 1) Scan types - seq scans on large tables suggest missing indexes. 2) Estimated vs actual rows - large differences mean outdated statistics, fix with ANALYZE. 3) Buffer reads vs hits - high reads mean poor caching or large working set. 4) Sort methods - external merge means work_mem is too small. 5) Rows removed by filter - high numbers mean we're scanning too much data. I look for the slowest nodes and work backwards to optimize."

### Question: "What does cost mean in EXPLAIN output?"

**Answer:**
> "Cost is an arbitrary unit representing estimated resource usage, not time. It's based on seq_page_cost (1.0), random_page_cost (4.0), cpu_tuple_cost, etc. The format is cost=startup..total where startup is cost before first row and total is cost for all rows. The planner chooses plans with lowest estimated total cost. It's useful for comparing plans but not for predicting actual time - use EXPLAIN ANALYZE for actual milliseconds."

## Key Takeaways

1. **EXPLAIN** shows plan without executing
2. **EXPLAIN ANALYZE** actually runs the query - be careful!
3. **Cost** is arbitrary units, not milliseconds
4. **Estimated vs actual rows** reveals statistics issues
5. **BUFFERS** shows cache effectiveness
6. **Seq Scan with filters** usually means missing index

## Self-Assessment Questions

1. What does "Rows Removed by Filter" indicate?
2. Why might estimated rows differ from actual rows?
3. When is a Seq Scan appropriate?
4. What does "Sort Method: external merge" mean?
5. How do you safely EXPLAIN ANALYZE a DELETE?

## Next Chapter

[Chapter 11: Query Planner Decisions →](./11_query_planner.md)

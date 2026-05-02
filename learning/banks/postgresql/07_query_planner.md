# Chapter 11: Query Planner Decisions

## Overview

The PostgreSQL query planner decides how to execute your query by estimating costs of different approaches. Understanding its cost model helps you write queries it can optimize and diagnose when it makes suboptimal choices.

## Learning Objectives

By the end of this chapter, you will:

- Understand the planner's cost model
- Influence planner decisions appropriately
- Update and maintain statistics
- Diagnose plan regressions

## Resources

| Resource | Time |
|----------|------|
| Read: PostgreSQL planner documentation | 30 min |
| Hands-on: Experiment with planner settings | 30 min |

## Core Concepts

### The Planner's Cost Model

```sql
-- View cost parameters
SHOW seq_page_cost;          -- 1.0 (baseline)
SHOW random_page_cost;       -- 4.0 (random I/O 4x more expensive)
SHOW cpu_tuple_cost;         -- 0.01 (per-row CPU cost)
SHOW cpu_index_tuple_cost;   -- 0.005 (per-index-entry CPU cost)
SHOW cpu_operator_cost;      -- 0.0025 (per-operator CPU cost)
SHOW effective_cache_size;   -- estimate of OS + PG cache

-- Cost calculation example:
-- Seq Scan cost = (pages * seq_page_cost) + (rows * cpu_tuple_cost)
-- Index Scan cost = (index_pages * random_page_cost) +
--                   (index_rows * cpu_index_tuple_cost) +
--                   (heap_pages * random_page_cost) +
--                   (rows * cpu_tuple_cost)
```

### Why Seq Scan Over Index Scan?

```sql
-- Planner chooses seq scan when it estimates it's cheaper
-- Common reasons:

-- 1. Low selectivity (returning many rows)
EXPLAIN ANALYZE
SELECT * FROM users WHERE active = true;  -- 90% of rows
-- Seq Scan cheaper than index + random heap lookups

-- 2. Small table
EXPLAIN ANALYZE
SELECT * FROM small_table WHERE id = 5;
-- Table fits in a few pages, seq scan is fast

-- 3. Outdated statistics
-- Planner thinks query returns 100 rows, actually returns 1
ANALYZE users;  -- Update statistics

-- 4. random_page_cost set too high for SSDs
-- Default assumes HDD (random = 4x sequential)
-- For SSD: random ~ 1.1-1.5x sequential
SET random_page_cost = 1.1;  -- for SSD
```

### Statistics Collection

```sql
-- Table-level statistics
SELECT
    relname,
    reltuples,         -- estimated row count
    relpages,          -- number of pages
    relallvisible      -- pages in visibility map
FROM pg_class
WHERE relname = 'orders';

-- Column-level statistics
SELECT
    attname,
    n_distinct,        -- number of distinct values (-1 = unique)
    null_frac,         -- fraction of nulls
    avg_width,         -- average column width in bytes
    most_common_vals,  -- most common values
    most_common_freqs, -- their frequencies
    histogram_bounds   -- value distribution
FROM pg_stats
WHERE tablename = 'orders' AND attname = 'status';

-- Update statistics
ANALYZE orders;              -- single table
ANALYZE orders(status);      -- single column
ANALYZE;                     -- entire database
```

### Statistics Target

```sql
-- default_statistics_target: how many values to sample (default 100)
-- Higher = more accurate but slower ANALYZE

-- Check current target
SELECT attname, attstattarget
FROM pg_attribute
WHERE attrelid = 'orders'::regclass AND attnum > 0;

-- Increase for important columns
ALTER TABLE orders ALTER COLUMN status SET STATISTICS 1000;
ANALYZE orders;

-- Global setting
SET default_statistics_target = 200;
```

### Extended Statistics

```sql
-- Correlation between columns (PostgreSQL 10+)
-- Example: city and zip_code are correlated

CREATE STATISTICS orders_status_user (dependencies)
ON status, user_id FROM orders;

ANALYZE orders;

-- View extended stats
SELECT * FROM pg_statistic_ext;

-- Multi-column distinct values
CREATE STATISTICS orders_multi_distinct (ndistinct)
ON status, user_id FROM orders;
```

### Influencing the Planner

```sql
-- WARNING: Usually you should fix the root cause, not force plans

-- Disable scan types (for testing/diagnosis)
SET enable_seqscan = off;       -- force index use
SET enable_indexscan = off;     -- force seq scan
SET enable_bitmapscan = off;    -- no bitmap scans

-- Disable join types
SET enable_hashjoin = off;
SET enable_mergejoin = off;
SET enable_nestloop = off;

-- Compare plans with different settings
SET enable_seqscan = off;
EXPLAIN ANALYZE SELECT ...;
SET enable_seqscan = on;

-- Cost adjustments for SSDs
SET random_page_cost = 1.1;
SET seq_page_cost = 1.0;
SET effective_io_concurrency = 200;

-- Per-query settings
BEGIN;
SET LOCAL random_page_cost = 1.1;
SELECT ...;
COMMIT;
```

### Join Planning

```sql
-- Planner considers all join orders for small number of tables
-- For many tables, uses genetic algorithm

SHOW geqo;                    -- genetic query optimizer on/off
SHOW geqo_threshold;          -- tables before GEQO kicks in (default 12)
SHOW join_collapse_limit;     -- explicit JOINs to flatten
SHOW from_collapse_limit;     -- subqueries to flatten

-- Force join order (rarely needed)
SET join_collapse_limit = 1;  -- preserve explicit JOIN order
SELECT ...
FROM a
JOIN b ON ...  -- a joins b first
JOIN c ON ...; -- then result joins c
```

### Common Statistics Issues

```sql
-- Problem: Estimated rows way off
EXPLAIN ANALYZE SELECT * FROM orders WHERE status = 'rare_status';
-- (cost=... rows=1000) (actual ... rows=5)

-- Solutions:
-- 1. Update statistics
ANALYZE orders;

-- 2. Increase statistics target
ALTER TABLE orders ALTER COLUMN status SET STATISTICS 500;
ANALYZE orders;

-- 3. Create extended statistics
CREATE STATISTICS orders_ext ON status, user_id FROM orders;
ANALYZE orders;

-- Problem: Correlations not detected
-- Table naturally sorted by created_at but planner doesn't know
SELECT correlation
FROM pg_stats
WHERE tablename = 'orders' AND attname = 'created_at';
-- correlation close to 1 or -1 means physical order matches logical
```

## Key Questions to Understand

- Why did the planner choose a seq scan over an index scan?
- How do you force an index to be used?
- When should you update statistics?

## Hands-On Exercises

### Exercise 1: Fix Statistics Issues

```sql
-- Create table with skewed data
CREATE TABLE skewed (
    id SERIAL PRIMARY KEY,
    category VARCHAR(20),
    value INTEGER
);

INSERT INTO skewed (category, value)
SELECT
    CASE floor(random() * 100)
        WHEN 0 THEN 'rare'
        ELSE 'common'
    END,
    random() * 1000
FROM generate_series(1, 1000000);

CREATE INDEX idx_skewed_category ON skewed(category);

-- Query rare category (should use index)
EXPLAIN ANALYZE
SELECT * FROM skewed WHERE category = 'rare';

-- If using seq scan, check statistics
SELECT most_common_vals, most_common_freqs
FROM pg_stats
WHERE tablename = 'skewed' AND attname = 'category';

-- Update statistics
ANALYZE skewed;

-- Check again
EXPLAIN ANALYZE
SELECT * FROM skewed WHERE category = 'rare';
```

### Exercise 2: SSD Configuration

```sql
-- Default settings assume HDD
SHOW random_page_cost;  -- 4.0

-- Test query with default
EXPLAIN ANALYZE
SELECT * FROM orders WHERE id IN (1, 100, 1000, 10000, 100000);

-- Adjust for SSD
SET random_page_cost = 1.1;

-- Same query - might choose different plan
EXPLAIN ANALYZE
SELECT * FROM orders WHERE id IN (1, 100, 1000, 10000, 100000);
```

### Exercise 3: Correlation Analysis

```sql
-- Create time-series table (naturally ordered)
CREATE TABLE time_series (
    id SERIAL PRIMARY KEY,
    recorded_at TIMESTAMPTZ NOT NULL,
    value NUMERIC
);

INSERT INTO time_series (recorded_at, value)
SELECT
    '2024-01-01'::TIMESTAMPTZ + (i || ' seconds')::INTERVAL,
    random() * 100
FROM generate_series(1, 1000000) i;

ANALYZE time_series;

-- Check correlation
SELECT attname, correlation
FROM pg_stats
WHERE tablename = 'time_series';
-- recorded_at should have correlation ~1.0 (physically ordered)

-- This knowledge helps BRIN indexes and range queries
CREATE INDEX idx_time_brin ON time_series USING BRIN (recorded_at);

EXPLAIN ANALYZE
SELECT * FROM time_series
WHERE recorded_at BETWEEN '2024-06-01' AND '2024-06-02';
```

## Interview Deep Dive

### Question: "The planner chose seq scan even with an index. Why?"

**Answer:**
> "Several reasons: 1) The query returns too many rows - if more than ~5-10% of the table, seq scan is cheaper than index + random heap lookups. 2) Statistics are outdated - run ANALYZE to update. 3) The predicate uses a function that doesn't match the index. 4) random_page_cost is set too high for SSDs. 5) The table is small enough that seq scan is faster anyway. I'd check EXPLAIN ANALYZE to compare estimated vs actual rows, run ANALYZE, and verify the index can actually be used for the query."

### Question: "How do you keep statistics up to date?"

**Answer:**
> "Autovacuum handles this automatically - it runs ANALYZE when enough rows change (default threshold: 50 rows + 10% of table). For critical tables or after bulk loads, I run ANALYZE manually. For columns with unusual distributions, I increase statistics_target. For correlated columns, I create extended statistics. I monitor pg_stat_user_tables to check last_analyze time and ensure autovacuum is keeping up."

## Key Takeaways

1. **Planner uses cost estimates** based on configurable parameters
2. **Statistics are crucial** - outdated stats cause bad plans
3. **ANALYZE updates statistics** - runs automatically via autovacuum
4. **random_page_cost** should be lowered for SSDs
5. **Don't blindly disable scan types** - fix root cause instead

## Self-Assessment Questions

1. What cost parameters affect index vs seq scan choice?
2. How does the planner know how many rows a query will return?
3. When would you increase statistics_target?
4. What are extended statistics for?
5. How do you safely test different planner settings?

## Next Chapter

[Chapter 12: Join Algorithms →](./12_join_algorithms.md)

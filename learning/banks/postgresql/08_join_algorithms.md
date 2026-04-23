# Chapter 12: Join Algorithms

## Overview

PostgreSQL uses three main join algorithms: Nested Loop, Hash Join, and Merge Join. Each has different performance characteristics depending on data size, order, and available indexes. Understanding these helps you write efficient queries and interpret EXPLAIN output.

## Learning Objectives

By the end of this chapter, you will:

- Understand the three join algorithms
- Know when each algorithm is chosen
- Optimize query performance for joins
- Interpret join nodes in EXPLAIN output

## Resources

| Resource | Time |
|----------|------|
| Read: PostgreSQL join methods | 30 min |
| Hands-on: Compare join performance | 30 min |

## Core Concepts

### Join Algorithms Overview

| Algorithm | Best For | Memory | Complexity |
|-----------|----------|--------|------------|
| Nested Loop | Small outer, indexed inner | Low | O(n × m) worst |
| Hash Join | Equality joins, medium tables | High | O(n + m) |
| Merge Join | Pre-sorted data, large tables | Low | O(n + m) |

### Nested Loop Join

```sql
-- Algorithm:
-- For each row in outer table:
--     For each row in inner table:
--         If join condition matches, output row

-- Best when:
-- - Outer table is small (after filtering)
-- - Inner table has index on join column
-- - Very selective conditions

-- Example query
EXPLAIN ANALYZE
SELECT o.*, u.email
FROM orders o
JOIN users u ON u.id = o.user_id
WHERE o.id = 123;

-- Output:
Nested Loop  (cost=0.43..16.48 rows=1 width=100) (actual time=0.025..0.027 rows=1 loops=1)
  ->  Index Scan using orders_pkey on orders o  (cost=0.29..8.31 rows=1 width=52)
        Index Cond: (id = 123)
  ->  Index Scan using users_pkey on users u  (cost=0.14..8.16 rows=1 width=48)
        Index Cond: (id = o.user_id)

-- Why chosen:
-- - orders filtered to 1 row (WHERE o.id = 123)
-- - users has index on id
-- - Only 1 iteration of inner loop needed
```

**Nested Loop Variations:**

```sql
-- Nested Loop with inner sequential scan (avoid!)
Nested Loop  (cost=0.00..12500025.00 rows=1000000 width=100) (actual time=...)
  ->  Seq Scan on orders o  (cost=0.00..25.00 rows=1000 width=52)
  ->  Seq Scan on users u  (cost=0.00..12500.00 rows=1 width=48)   ← loops=1000!
        Filter: (id = o.user_id)

-- This is O(n × m) - very slow!
-- Add index on users.id to fix
```

### Hash Join

```sql
-- Algorithm:
-- 1. Build: scan smaller table, build hash table on join key
-- 2. Probe: scan larger table, probe hash table for matches

-- Best when:
-- - Equality join (=, not <, >, etc.)
-- - No useful index on join column
-- - Enough memory for hash table

-- Example query
EXPLAIN ANALYZE
SELECT o.*, u.email
FROM orders o
JOIN users u ON u.id = o.user_id
WHERE o.created_at > '2024-01-01';

-- Output:
Hash Join  (cost=15.25..4521.50 rows=50000 width=100) (actual time=1.234..45.678 rows=48523 loops=1)
  Hash Cond: (o.user_id = u.id)
  ->  Seq Scan on orders o  (cost=0.00..4000.00 rows=50000 width=52)
        Filter: (created_at > '2024-01-01')
  ->  Hash  (cost=10.00..10.00 rows=1000 width=48) (actual time=1.000..1.000 rows=1000 loops=1)
        Buckets: 1024  Memory Usage: 72kB
        ->  Seq Scan on users u  (cost=0.00..10.00 rows=1000 width=48)

-- Why chosen:
-- - orders returns many rows (50000)
-- - users is smaller (1000), builds hash table
-- - Hash table fits in memory (72kB)
```

**Hash Join Memory:**

```sql
-- Hash table must fit in work_mem
SHOW work_mem;  -- default 4MB

-- If hash table exceeds work_mem, spills to disk (slower)
-- Look for "Batches: N" where N > 1
Hash  (cost=...) (actual time=...)
  Buckets: 65536  Batches: 4  Memory Usage: 4097kB
                  ^^^^^^^^^ spilled to disk!

-- Increase work_mem for this query
SET work_mem = '256MB';
```

### Merge Join

```sql
-- Algorithm:
-- 1. Sort both inputs on join key (or use pre-sorted data)
-- 2. Merge: walk through both sorted lists together

-- Best when:
-- - Both inputs already sorted (indexes, ORDER BY)
-- - Large tables
-- - Less memory than hash join needs

-- Example query
EXPLAIN ANALYZE
SELECT o.*, u.email
FROM orders o
JOIN users u ON u.id = o.user_id
ORDER BY o.user_id;

-- Output:
Merge Join  (cost=0.72..85123.45 rows=1000000 width=100) (actual time=0.056..789.123 rows=1000000 loops=1)
  Merge Cond: (o.user_id = u.id)
  ->  Index Scan using idx_orders_user on orders o  (cost=0.43..75000.00 rows=1000000 width=52)
  ->  Index Scan using users_pkey on users u  (cost=0.29..100.00 rows=1000 width=48)

-- Why chosen:
-- - ORDER BY o.user_id anyway
-- - Both sides have indexes producing sorted output
-- - No hash table needed
```

### Comparing Join Performance

```sql
-- Create test tables
CREATE TABLE big_orders AS
SELECT i as id, (random() * 10000)::int as user_id, NOW() as created_at
FROM generate_series(1, 1000000) i;

CREATE TABLE users_10k AS
SELECT i as id, 'user' || i || '@example.com' as email
FROM generate_series(1, 10000) i;

-- Add indexes
CREATE INDEX idx_big_orders_user ON big_orders(user_id);
CREATE INDEX idx_users_10k_id ON users_10k(id);

ANALYZE big_orders;
ANALYZE users_10k;

-- Test different join types
SET enable_hashjoin = on;
SET enable_mergejoin = on;
SET enable_nestloop = on;

EXPLAIN ANALYZE
SELECT o.*, u.email
FROM big_orders o
JOIN users_10k u ON u.id = o.user_id;
-- Likely Hash Join

SET enable_hashjoin = off;
EXPLAIN ANALYZE
SELECT o.*, u.email
FROM big_orders o
JOIN users_10k u ON u.id = o.user_id;
-- Likely Merge Join or Nested Loop

SET enable_hashjoin = on;
```

### Multiple Table Joins

```sql
-- With many tables, join order matters greatly
EXPLAIN ANALYZE
SELECT *
FROM orders o
JOIN users u ON u.id = o.user_id
JOIN products p ON p.id = o.product_id
JOIN categories c ON c.id = p.category_id
WHERE o.id = 123;

-- Planner evaluates all orderings for small number of tables
-- For many tables, uses genetic algorithm (GEQO)

-- To hint at join order (rarely needed)
SET join_collapse_limit = 1;
SELECT * FROM a JOIN b ON ... JOIN c ON ...;
-- Joins in written order: (a ⋈ b) ⋈ c
```

### Anti-Joins and Semi-Joins

```sql
-- NOT EXISTS (anti-join)
EXPLAIN ANALYZE
SELECT * FROM users u
WHERE NOT EXISTS (
    SELECT 1 FROM orders o WHERE o.user_id = u.id
);
-- Hash Anti Join or Nested Loop Anti Join

-- EXISTS (semi-join)
EXPLAIN ANALYZE
SELECT * FROM users u
WHERE EXISTS (
    SELECT 1 FROM orders o WHERE o.user_id = u.id
);
-- Hash Semi Join - stops at first match

-- NOT IN (careful with NULLs!)
SELECT * FROM users WHERE id NOT IN (SELECT user_id FROM orders);
-- If orders.user_id can be NULL, returns empty result!
-- Prefer NOT EXISTS
```

## Key Questions to Understand

- When does PostgreSQL choose Hash Join vs Nested Loop?
- Why might a Merge Join be better for sorted data?
- How can you help the planner choose better?

## Hands-On Exercises

### Exercise 1: Compare Join Algorithms

```sql
-- Setup
CREATE TABLE left_table (id INT PRIMARY KEY, data TEXT);
CREATE TABLE right_table (id INT PRIMARY KEY, left_id INT, data TEXT);

INSERT INTO left_table SELECT i, 'left-' || i FROM generate_series(1, 10000) i;
INSERT INTO right_table SELECT i, (random() * 10000)::INT, 'right-' || i FROM generate_series(1, 1000000) i;

CREATE INDEX idx_right_left_id ON right_table(left_id);
ANALYZE left_table;
ANALYZE right_table;

-- Force and compare each join type
SET enable_hashjoin = on; SET enable_mergejoin = off; SET enable_nestloop = off;
EXPLAIN ANALYZE SELECT * FROM left_table l JOIN right_table r ON r.left_id = l.id;

SET enable_hashjoin = off; SET enable_mergejoin = on; SET enable_nestloop = off;
EXPLAIN ANALYZE SELECT * FROM left_table l JOIN right_table r ON r.left_id = l.id;

SET enable_hashjoin = off; SET enable_mergejoin = off; SET enable_nestloop = on;
EXPLAIN ANALYZE SELECT * FROM left_table l JOIN right_table r ON r.left_id = l.id;

-- Reset
SET enable_hashjoin = on; SET enable_mergejoin = on; SET enable_nestloop = on;
```

### Exercise 2: work_mem Impact on Hash Join

```sql
-- Small work_mem causes batching
SET work_mem = '64kB';
EXPLAIN ANALYZE
SELECT * FROM big_orders o JOIN users_10k u ON u.id = o.user_id;
-- Look for Batches > 1

-- Larger work_mem
SET work_mem = '64MB';
EXPLAIN ANALYZE
SELECT * FROM big_orders o JOIN users_10k u ON u.id = o.user_id;
-- Batches: 1 (all in memory)

SET work_mem = '4MB';  -- Reset to default
```

### Exercise 3: Anti-Join Optimization

```sql
-- Find users without orders
-- Method 1: NOT IN (problematic with NULLs)
EXPLAIN ANALYZE
SELECT * FROM users_10k WHERE id NOT IN (SELECT user_id FROM big_orders);

-- Method 2: NOT EXISTS (recommended)
EXPLAIN ANALYZE
SELECT * FROM users_10k u
WHERE NOT EXISTS (SELECT 1 FROM big_orders o WHERE o.user_id = u.id);

-- Method 3: LEFT JOIN + IS NULL
EXPLAIN ANALYZE
SELECT u.* FROM users_10k u
LEFT JOIN big_orders o ON o.user_id = u.id
WHERE o.id IS NULL;
```

## Interview Deep Dive

### Question: "Explain the difference between Nested Loop, Hash, and Merge joins."

**Answer:**
> "Nested Loop iterates through the outer table and for each row, scans the inner table - O(n×m) worst case but fast with small outer and indexed inner. Hash Join builds a hash table from the smaller table and probes it with the larger - O(n+m) but needs memory for the hash table. Merge Join sorts both inputs and merges them - O(n+m) plus sort cost, but if data is already sorted (via indexes), it's very efficient. The planner chooses based on table sizes, available indexes, sort order, and memory settings."

### Question: "How would you optimize a slow join?"

**Answer:**
> "First EXPLAIN ANALYZE to see what's happening. If Nested Loop with seq scan on inner, add an index on the join column. If Hash Join shows batches > 1, increase work_mem for the query. If wrong table is used as outer in nested loop, check statistics with ANALYZE. For large tables, ensure join columns have indexes and consider if the join order is optimal. Sometimes restructuring the query or adding a covering index helps."

## Key Takeaways

1. **Nested Loop** - best with small outer + indexed inner
2. **Hash Join** - best for medium tables, needs memory
3. **Merge Join** - best when data already sorted
4. **work_mem** affects hash join batching
5. **NOT EXISTS preferred** over NOT IN for anti-joins

## Self-Assessment Questions

1. When would Nested Loop be faster than Hash Join?
2. What causes Hash Join to batch to disk?
3. Why is NOT IN problematic with NULLs?
4. How does the planner decide join order?
5. What does "loops=1000" mean in Nested Loop?

## Next Chapter

[Chapter 13: Common Query Anti-Patterns →](./13_query_antipatterns.md)

# Chapter 13: Common Query Anti-Patterns

## Overview

Certain query patterns consistently cause performance problems. Recognizing these anti-patterns helps you write efficient queries from the start and quickly diagnose slow queries in production.

## Learning Objectives

By the end of this chapter, you will:

- Recognize slow query patterns
- Fix N+1 queries and correlated subqueries
- Avoid common mistakes that prevent index use
- Write efficient queries by default

## Resources

| Resource | Time |
|----------|------|
| Read: Common SQL performance issues | 30 min |
| Hands-on: Identify and fix anti-patterns | 45 min |

## Core Concepts

### The N+1 Query Problem

```python
# Anti-pattern: N+1 queries
users = db.query("SELECT * FROM users LIMIT 100")
for user in users:
    # Executes 100 additional queries!
    orders = db.query("SELECT * FROM orders WHERE user_id = %s", user.id)
    print(user.name, len(orders))

# Total: 1 + 100 = 101 queries
```

```sql
-- Solution 1: JOIN
SELECT u.*, o.*
FROM users u
LEFT JOIN orders o ON o.user_id = u.id
LIMIT 100;

-- Solution 2: Subquery with IN
SELECT * FROM orders
WHERE user_id IN (SELECT id FROM users LIMIT 100);

-- Solution 3: Application-level batching
SELECT * FROM orders WHERE user_id IN (1, 2, 3, 4, 5, ...);
```

### SELECT * (Selecting All Columns)

```sql
-- Anti-pattern: SELECT *
SELECT * FROM orders WHERE user_id = 123;

-- Problems:
-- 1. Fetches unnecessary columns
-- 2. Prevents index-only scans
-- 3. More data transferred over network
-- 4. Breaks when schema changes

-- Solution: Select only needed columns
SELECT id, status, total_amount
FROM orders
WHERE user_id = 123;

-- With covering index, can be index-only scan
CREATE INDEX idx_orders_covering ON orders(user_id) INCLUDE (id, status, total_amount);
```

### Functions on Indexed Columns

```sql
-- Anti-pattern: Function prevents index use
SELECT * FROM users WHERE LOWER(email) = 'alice@example.com';
-- Seq Scan! Function applied to every row

SELECT * FROM orders WHERE YEAR(created_at) = 2024;
-- Seq Scan! YEAR() function on every row

SELECT * FROM users WHERE LEFT(name, 1) = 'A';
-- Seq Scan! LEFT() function on every row

-- Solutions:

-- 1. Functional index
CREATE INDEX idx_users_email_lower ON users(LOWER(email));
SELECT * FROM users WHERE LOWER(email) = 'alice@example.com';
-- Now uses index!

-- 2. Rewrite without function
SELECT * FROM orders
WHERE created_at >= '2024-01-01' AND created_at < '2025-01-01';
-- Uses index on created_at

-- 3. Use LIKE for prefix
SELECT * FROM users WHERE name LIKE 'A%';
-- Uses index (prefix search)
```

### Implicit Type Conversions

```sql
-- Anti-pattern: Type mismatch
CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    created_at TIMESTAMPTZ
);
CREATE INDEX idx_orders_user ON orders(user_id);

-- Passing string for integer
SELECT * FROM orders WHERE user_id = '123';
-- May still work but adds implicit cast

-- More problematic: comparing to wrong type
SELECT * FROM orders WHERE created_at = '2024-01-15';
-- String vs timestamp comparison

-- Solution: Use correct types
SELECT * FROM orders WHERE user_id = 123;
SELECT * FROM orders WHERE created_at = '2024-01-15'::TIMESTAMPTZ;
```

### Correlated Subqueries

```sql
-- Anti-pattern: Correlated subquery (executes for each row!)
SELECT
    u.id,
    u.name,
    (SELECT COUNT(*) FROM orders o WHERE o.user_id = u.id) as order_count,
    (SELECT MAX(created_at) FROM orders o WHERE o.user_id = u.id) as last_order
FROM users u;
-- Two subqueries × N users = 2N additional queries!

-- Solution: Use JOIN with aggregation
SELECT
    u.id,
    u.name,
    COUNT(o.id) as order_count,
    MAX(o.created_at) as last_order
FROM users u
LEFT JOIN orders o ON o.user_id = u.id
GROUP BY u.id, u.name;

-- Or: Lateral join (when you need multiple aggregates)
SELECT u.id, u.name, stats.*
FROM users u
LEFT JOIN LATERAL (
    SELECT
        COUNT(*) as order_count,
        MAX(created_at) as last_order
    FROM orders o
    WHERE o.user_id = u.id
) stats ON true;
```

### OR Conditions

```sql
-- Anti-pattern: OR may not use indexes efficiently
SELECT * FROM orders
WHERE status = 'pending' OR user_id = 123;
-- May do full scan even with indexes on both columns

-- Solution 1: UNION (if few ORs)
SELECT * FROM orders WHERE status = 'pending'
UNION
SELECT * FROM orders WHERE user_id = 123;

-- Solution 2: Composite index for common OR patterns
-- Not always possible

-- Solution 3: Array contains (for same column)
-- Instead of: status = 'pending' OR status = 'processing'
SELECT * FROM orders WHERE status = ANY(ARRAY['pending', 'processing']);
-- Or: status IN ('pending', 'processing')
```

### NOT IN with NULLs

```sql
-- Anti-pattern: NOT IN with nullable column
SELECT * FROM users
WHERE id NOT IN (SELECT user_id FROM orders);

-- If orders.user_id can be NULL, this returns EMPTY RESULT!
-- NULL compared with NOT IN causes issues

-- Solution: Use NOT EXISTS
SELECT * FROM users u
WHERE NOT EXISTS (
    SELECT 1 FROM orders o WHERE o.user_id = u.id
);

-- Or: Explicit NULL handling
SELECT * FROM users
WHERE id NOT IN (SELECT user_id FROM orders WHERE user_id IS NOT NULL);
```

### Missing LIMIT on Large Results

```sql
-- Anti-pattern: Unbounded queries
SELECT * FROM logs WHERE type = 'error';
-- Could return millions of rows!

-- Solution: Always LIMIT, especially in application code
SELECT * FROM logs WHERE type = 'error'
ORDER BY created_at DESC
LIMIT 100;

-- For pagination, use cursor-based (not offset)
-- Anti-pattern:
SELECT * FROM products ORDER BY id LIMIT 10 OFFSET 10000;
-- Must scan 10010 rows!

-- Solution: Cursor-based pagination
SELECT * FROM products
WHERE id > last_seen_id
ORDER BY id
LIMIT 10;
```

### Expensive DISTINCT

```sql
-- Anti-pattern: DISTINCT to hide JOIN issues
SELECT DISTINCT u.*
FROM users u
JOIN orders o ON o.user_id = u.id;
-- JOIN creates duplicates, DISTINCT removes them

-- Problem: DISTINCT sorts/hashes entire result set

-- Solution: Use EXISTS (no duplicates created)
SELECT u.*
FROM users u
WHERE EXISTS (SELECT 1 FROM orders o WHERE o.user_id = u.id);

-- Or fix the JOIN logic
SELECT u.*
FROM users u
JOIN (SELECT DISTINCT user_id FROM orders) o ON o.user_id = u.id;
```

### ORDER BY Without Index Support

```sql
-- Anti-pattern: Sorting large result sets
SELECT * FROM orders
ORDER BY created_at DESC;
-- Must load all rows, sort them all

-- Look for in EXPLAIN:
Sort Method: external merge  Disk: 500MB
-- Spilled to disk!

-- Solution 1: Index supports ordering
CREATE INDEX idx_orders_created ON orders(created_at DESC);

SELECT * FROM orders
ORDER BY created_at DESC
LIMIT 100;
-- Index Scan, no sort needed!

-- Solution 2: Limit before expensive operations
-- Use LIMIT when possible
```

## Key Questions to Understand

- What's the N+1 query problem?
- Why are SELECT * and functions on columns bad?
- How do you spot these patterns in production?

## Hands-On Exercises

### Exercise 1: Fix N+1 Query

```sql
-- Setup
CREATE TABLE authors (id SERIAL PRIMARY KEY, name TEXT);
CREATE TABLE books (id SERIAL PRIMARY KEY, author_id INT, title TEXT);

INSERT INTO authors (name) SELECT 'Author ' || i FROM generate_series(1, 100) i;
INSERT INTO books (author_id, title)
SELECT
    (random() * 100)::INT + 1,
    'Book ' || i
FROM generate_series(1, 10000) i;

-- Simulate N+1 (bad)
DO $$
DECLARE
    author RECORD;
    book_count INT;
BEGIN
    FOR author IN SELECT * FROM authors LOOP
        SELECT COUNT(*) INTO book_count FROM books WHERE author_id = author.id;
        -- This runs 100 queries!
    END LOOP;
END $$;

-- Fixed version (good)
SELECT a.name, COUNT(b.id) as book_count
FROM authors a
LEFT JOIN books b ON b.author_id = a.id
GROUP BY a.id, a.name;
-- Single query!
```

### Exercise 2: Function Index

```sql
-- Problem query
EXPLAIN ANALYZE
SELECT * FROM users WHERE LOWER(email) = 'alice@example.com';
-- Seq Scan

-- Create functional index
CREATE INDEX idx_users_email_lower ON users(LOWER(email));

EXPLAIN ANALYZE
SELECT * FROM users WHERE LOWER(email) = 'alice@example.com';
-- Index Scan
```

### Exercise 3: Replace Correlated Subquery

```sql
-- Slow version
EXPLAIN ANALYZE
SELECT
    id,
    (SELECT COUNT(*) FROM orders WHERE user_id = users.id) as cnt
FROM users;

-- Fast version
EXPLAIN ANALYZE
SELECT u.id, COUNT(o.id) as cnt
FROM users u
LEFT JOIN orders o ON o.user_id = u.id
GROUP BY u.id;

-- Compare execution times
```

## Interview Deep Dive

### Question: "What is the N+1 query problem and how do you fix it?"

**Answer:**
> "N+1 happens when you fetch a list of N items, then execute N additional queries to fetch related data for each item. For example, fetching 100 users then 100 queries for their orders. Fix it by: 1) Using JOINs to get everything in one query, 2) Using IN clause with all IDs, 3) ORM eager loading. In ORMs like Django, use select_related() or prefetch_related(). This changes 101 queries into 1-2 queries, dramatically improving performance."

### Question: "How do you find slow queries in production?"

**Answer:**
> "Enable pg_stat_statements extension to track query statistics - it shows calls, total_time, mean_time. Query it to find highest total_time queries. Also configure log_min_duration_statement to log queries over a threshold. Look for: sequential scans on large tables, high rows removed by filter (missing index), sort on disk (work_mem issue), nested loops with many loops. For real-time issues, check pg_stat_activity for long-running queries."

## Key Takeaways

1. **N+1 queries** - use JOINs or batch fetching
2. **SELECT *** - specify only needed columns
3. **Functions on columns** - use functional indexes
4. **Correlated subqueries** - rewrite as JOINs
5. **NOT IN with NULLs** - use NOT EXISTS instead
6. **Missing LIMIT** - always limit unbounded queries

## Self-Assessment Questions

1. How do you detect N+1 queries in an ORM?
2. Why does LOWER(column) prevent index use?
3. When would UNION be better than OR?
4. What's wrong with large OFFSET pagination?
5. How do you fix correlated subqueries?

## Next Chapter

[Chapter 14: ACID Properties →](./14_acid.md)

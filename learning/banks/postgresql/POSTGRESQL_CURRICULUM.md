# PostgreSQL Learning Curriculum

A comprehensive, hands-on learning strategy for PostgreSQL mastery. Focus on understanding, not memorization.

---

## Quick Start

```bash
# Run PostgreSQL locally
docker run -d --name postgres -p 5432:5432 \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=learn \
  postgres:15

# Connect
docker exec -it postgres psql -U postgres -d learn

# Or use psql directly
psql -h localhost -U postgres -d learn
```

---

## Module 1: Foundations

### Chapter 1: Relational Model Refresher

**Learning Objectives**
- Understand relational algebra basics
- Know normalization forms and when to denormalize
- Design schemas for real applications

| Resource | Time |
|----------|------|
| Read: Relational model basics | 30 min |
| Hands-on: Design a schema | 30 min |

**Key Questions to Understand**
- What problems does normalization solve?
- When should you denormalize?
- What's the difference between 3NF and BCNF?

**Schema Design Example**
```sql
-- Users and Orders (normalized)
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    total_amount DECIMAL(10,2) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE order_items (
    id SERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES orders(id),
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price DECIMAL(10,2) NOT NULL
);

-- Denormalized for read performance
CREATE TABLE order_summary (
    order_id INTEGER PRIMARY KEY,
    user_email VARCHAR(255),
    user_name VARCHAR(255),
    total_amount DECIMAL(10,2),
    item_count INTEGER
);
```

---

### Chapter 2: SQL Essentials (Beyond Basics)

**Learning Objectives**
- Master window functions
- Use CTEs effectively
- Write efficient subqueries

| Resource | Time |
|----------|------|
| Read: PostgreSQL window functions | 30 min |
| Hands-on: Practice complex queries | 1 hr |

**Key Questions to Understand**
- When do you use a CTE vs a subquery?
- What's the difference between RANK, DENSE_RANK, and ROW_NUMBER?
- When does a correlated subquery hurt performance?

**Window Functions**
```sql
-- Rank users by order count
SELECT
    user_id,
    COUNT(*) as order_count,
    RANK() OVER (ORDER BY COUNT(*) DESC) as rank,
    DENSE_RANK() OVER (ORDER BY COUNT(*) DESC) as dense_rank,
    ROW_NUMBER() OVER (ORDER BY COUNT(*) DESC) as row_num
FROM orders
GROUP BY user_id;

-- Running total
SELECT
    date,
    amount,
    SUM(amount) OVER (ORDER BY date) as running_total,
    AVG(amount) OVER (ORDER BY date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) as moving_avg_7d
FROM daily_sales;

-- Lag/Lead
SELECT
    date,
    amount,
    LAG(amount) OVER (ORDER BY date) as prev_day,
    amount - LAG(amount) OVER (ORDER BY date) as daily_change
FROM daily_sales;
```

**CTEs (Common Table Expressions)**
```sql
-- Readable complex query
WITH monthly_stats AS (
    SELECT
        DATE_TRUNC('month', created_at) as month,
        COUNT(*) as order_count,
        SUM(total_amount) as revenue
    FROM orders
    GROUP BY 1
),
ranked_months AS (
    SELECT
        month,
        order_count,
        revenue,
        RANK() OVER (ORDER BY revenue DESC) as rank
    FROM monthly_stats
)
SELECT * FROM ranked_months WHERE rank <= 5;

-- Recursive CTE (hierarchical data)
WITH RECURSIVE subordinates AS (
    SELECT id, name, manager_id, 0 as level
    FROM employees
    WHERE id = 1  -- CEO

    UNION ALL

    SELECT e.id, e.name, e.manager_id, s.level + 1
    FROM employees e
    JOIN subordinates s ON e.manager_id = s.id
)
SELECT * FROM subordinates;
```

---

### Chapter 3: Data Types and When to Use Them

**Learning Objectives**
- Choose appropriate data types
- Use PostgreSQL-specific types
- Understand storage implications

| Resource | Time |
|----------|------|
| Read: https://www.postgresql.org/docs/current/datatype.html | 30 min |

**Key Questions to Understand**
- When do you use NUMERIC vs REAL vs DOUBLE PRECISION?
- What's the difference between TEXT and VARCHAR?
- When should you use JSONB vs normalized tables?

**Type Selection Guide**

| Use Case | Type | Why |
|----------|------|-----|
| Money | NUMERIC(10,2) | Exact precision |
| Floating point | DOUBLE PRECISION | When precision loss OK |
| Free text | TEXT | No length limit, same perf as VARCHAR |
| UUID | UUID | Native type, efficient storage |
| Timestamp | TIMESTAMPTZ | Always store with timezone |
| JSON data | JSONB | Indexable, compressed |
| Arrays | INTEGER[] | Native array support |
| IP addresses | INET | Native type with functions |
| Ranges | INT4RANGE, TSTZRANGE | Range operations |

**JSONB Operations**
```sql
CREATE TABLE events (
    id SERIAL PRIMARY KEY,
    data JSONB NOT NULL
);

INSERT INTO events (data) VALUES
    ('{"type": "click", "page": "/home", "user_id": 123}'),
    ('{"type": "purchase", "amount": 99.99, "user_id": 123}');

-- Query JSON fields
SELECT data->>'type' as event_type FROM events;
SELECT data->'user_id' FROM events;  -- returns JSON
SELECT data->>'user_id' FROM events; -- returns TEXT

-- Filter
SELECT * FROM events WHERE data->>'type' = 'click';
SELECT * FROM events WHERE (data->>'amount')::numeric > 50;

-- Index JSONB
CREATE INDEX idx_events_type ON events ((data->>'type'));
CREATE INDEX idx_events_gin ON events USING GIN (data);
```

---

### Chapter 4: Constraints and Referential Integrity

**Learning Objectives**
- Use constraints for data integrity
- Handle constraint violations
- Design for performance and integrity

**Key Questions to Understand**
- When should you use CHECK vs application-level validation?
- What's the performance impact of foreign keys?
- How do you handle constraint violations gracefully?

**Constraints**
```sql
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    sku VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    price DECIMAL(10,2) CHECK (price > 0),
    status VARCHAR(20) DEFAULT 'active'
        CHECK (status IN ('active', 'inactive', 'discontinued')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Composite unique constraint
ALTER TABLE order_items
ADD CONSTRAINT unique_order_product UNIQUE (order_id, product_id);

-- Conditional unique (partial index)
CREATE UNIQUE INDEX unique_active_email
ON users (email)
WHERE deleted_at IS NULL;

-- Exclusion constraint (no overlapping ranges)
CREATE TABLE room_bookings (
    room_id INTEGER,
    during TSTZRANGE,
    EXCLUDE USING GIST (room_id WITH =, during WITH &&)
);
```

**Handling Violations**
```sql
-- Upsert (INSERT or UPDATE)
INSERT INTO products (sku, name, price)
VALUES ('SKU001', 'Widget', 9.99)
ON CONFLICT (sku)
DO UPDATE SET
    name = EXCLUDED.name,
    price = EXCLUDED.price;

-- Insert ignore (do nothing on conflict)
INSERT INTO products (sku, name, price)
VALUES ('SKU001', 'Widget', 9.99)
ON CONFLICT DO NOTHING;
```

---

## Module 2: Indexing Deep Dive

### Chapter 5: How B-Tree Indexes Work

**Learning Objectives**
- Understand B-tree structure
- Know when indexes help/hurt
- Analyze index usage

| Resource | Time |
|----------|------|
| Read: https://use-the-index-luke.com/ chapters 1-3 | 2 hrs |
| Hands-on: Create indexes, analyze queries | 1 hr |

**Key Questions to Understand**
- How does a B-tree find a row?
- Why is index order important for range queries?
- What's the difference between a scan and a seek?

**B-Tree Structure**
```
                    [50]
                   /    \
            [25,35]      [75,85]
           /   |   \    /   |   \
        [10,20][30][40,45][60,70][80][90,95]
                    │
                    └── Leaf nodes contain pointers to table rows
```

**Index Operations**
```sql
-- Create index
CREATE INDEX idx_orders_user ON orders(user_id);
CREATE INDEX idx_orders_created ON orders(created_at);

-- Analyze index usage
EXPLAIN ANALYZE
SELECT * FROM orders WHERE user_id = 123;

-- Check index size
SELECT pg_size_pretty(pg_relation_size('idx_orders_user'));

-- List unused indexes
SELECT
    schemaname,
    relname,
    indexrelname,
    idx_scan,
    pg_size_pretty(pg_relation_size(indexrelid)) as size
FROM pg_stat_user_indexes
WHERE idx_scan = 0
AND indexrelname NOT LIKE '%pkey%';
```

---

### Chapter 6: Index Types

**Learning Objectives**
- Choose the right index type
- Use specialized indexes
- Know limitations of each type

| Resource | Time |
|----------|------|
| Read: PostgreSQL index types | 30 min |
| Hands-on: Create and test different index types | 45 min |

**Index Types**

| Type | Use Case | Example |
|------|----------|---------|
| B-Tree | Equality, range, sorting | Most columns |
| Hash | Equality only | Exact lookups (rare) |
| GIN | Arrays, JSONB, full-text | tags[], JSONB data |
| GiST | Geometric, range, full-text | PostGIS, ltree |
| BRIN | Large sequential data | Time-series, logs |

```sql
-- B-Tree (default)
CREATE INDEX idx_btree ON orders(created_at);

-- Hash (equality only)
CREATE INDEX idx_hash ON users USING HASH (email);

-- GIN for arrays
CREATE INDEX idx_tags ON posts USING GIN (tags);
SELECT * FROM posts WHERE tags @> ARRAY['postgresql'];

-- GIN for JSONB
CREATE INDEX idx_data ON events USING GIN (data);
SELECT * FROM events WHERE data @> '{"type": "click"}';

-- GiST for ranges
CREATE INDEX idx_booking_range ON bookings USING GIST (during);

-- BRIN for time-series (very small, less precise)
CREATE INDEX idx_logs_time ON logs USING BRIN (created_at);
```

---

### Chapter 7: Composite and Partial Indexes

**Learning Objectives**
- Design effective composite indexes
- Use partial indexes to save space
- Understand index column order

**Key Questions to Understand**
- How does column order affect composite index usage?
- When would you use a partial index?
- Can a composite index satisfy multiple query patterns?

**Composite Index Order Matters**
```sql
-- Index on (a, b, c) can satisfy:
-- WHERE a = ?
-- WHERE a = ? AND b = ?
-- WHERE a = ? AND b = ? AND c = ?
-- WHERE a = ? ORDER BY b
-- ORDER BY a, b, c

-- But NOT efficiently:
-- WHERE b = ?  (no leading column)
-- WHERE a = ? AND c = ?  (skips b)
-- ORDER BY b, a  (wrong order)

CREATE INDEX idx_orders_user_status_date
ON orders(user_id, status, created_at);

-- Good: uses full index
SELECT * FROM orders
WHERE user_id = 1 AND status = 'completed'
ORDER BY created_at DESC;

-- Partial: uses first two columns
SELECT * FROM orders
WHERE user_id = 1 AND status = 'pending';

-- Bad: can't use index efficiently
SELECT * FROM orders WHERE status = 'pending';
```

**Partial Indexes**
```sql
-- Index only active orders (smaller, faster)
CREATE INDEX idx_active_orders
ON orders(created_at)
WHERE status = 'pending';

-- Query must match the WHERE clause
EXPLAIN ANALYZE
SELECT * FROM orders
WHERE status = 'pending' AND created_at > '2024-01-01';
-- Uses idx_active_orders

EXPLAIN ANALYZE
SELECT * FROM orders
WHERE status = 'completed' AND created_at > '2024-01-01';
-- Cannot use idx_active_orders (different status)
```

---

### Chapter 8: Index-Only Scans

**Learning Objectives**
- Enable index-only scans
- Understand visibility map
- Use covering indexes

**Key Questions to Understand**
- What prevents an index-only scan?
- How does the visibility map help?
- When should you use INCLUDE columns?

**Index-Only Scan**
```sql
-- Covering index (includes all needed columns)
CREATE INDEX idx_covering ON orders(user_id, status)
INCLUDE (total_amount);

-- This can be index-only
EXPLAIN ANALYZE
SELECT user_id, status, total_amount
FROM orders
WHERE user_id = 123;

-- Look for "Index Only Scan" in plan
-- "Heap Fetches: 0" means true index-only
```

**Visibility Map**
```
Index-only scan requires checking if row is visible to transaction.
Visibility map tracks which pages have all-visible tuples.

If page is marked all-visible → no heap access needed
If page is not all-visible → must check heap

Run VACUUM to update visibility map!
```

---

### Chapter 9: When Indexes Hurt

**Learning Objectives**
- Identify when indexes harm performance
- Balance read vs write performance
- Remove unused indexes

**Key Questions to Understand**
- Why would the planner ignore an available index?
- What's the write overhead of indexes?
- How do you identify redundant indexes?

**When Indexes Aren't Used**
```sql
-- 1. Low selectivity (returns too many rows)
SELECT * FROM users WHERE status = 'active';  -- 90% of rows
-- Full scan faster than index + heap lookups

-- 2. Type mismatch
SELECT * FROM users WHERE id = '123';  -- id is INTEGER
-- Cast prevents index use (sometimes)

-- 3. Function on indexed column
SELECT * FROM users WHERE LOWER(email) = 'test@example.com';
-- Won't use index on email

-- Solution: functional index
CREATE INDEX idx_email_lower ON users(LOWER(email));

-- 4. OR conditions (sometimes)
SELECT * FROM orders WHERE user_id = 1 OR total > 1000;
-- May not use either index efficiently

-- 5. Outdated statistics
ANALYZE orders;  -- Update statistics
```

**Index Write Overhead**
```sql
-- Each index adds ~30-50% write overhead
-- INSERT/UPDATE/DELETE must update all indexes

-- Find redundant indexes
SELECT
    a.indexrelid::regclass AS redundant_index,
    b.indexrelid::regclass AS covering_index
FROM pg_index a
JOIN pg_index b ON a.indrelid = b.indrelid
WHERE a.indexrelid != b.indexrelid
AND a.indkey <@ b.indkey;  -- a's columns subset of b's
```

---

## Module 3: Query Execution

### Chapter 10: EXPLAIN and EXPLAIN ANALYZE

**Learning Objectives**
- Read and interpret EXPLAIN output
- Use EXPLAIN ANALYZE for actual timing
- Identify performance bottlenecks

| Resource | Time |
|----------|------|
| Read: https://www.postgresql.org/docs/current/using-explain.html | 30 min |
| Hands-on: Analyze real queries | 1 hr |

**Key Questions to Understand**
- What's the difference between EXPLAIN and EXPLAIN ANALYZE?
- How do you interpret cost numbers?
- What do actual vs estimated rows tell you?

**Reading EXPLAIN Output**
```sql
EXPLAIN ANALYZE
SELECT * FROM orders
WHERE user_id = 123 AND created_at > '2024-01-01'
ORDER BY created_at DESC
LIMIT 10;

-- Output:
Limit  (cost=0.43..25.32 rows=10 width=48) (actual time=0.052..0.089 rows=10 loops=1)
  ->  Index Scan using idx_orders_user on orders  (cost=0.43..12345.67 rows=5000 width=48) (actual time=0.051..0.085 rows=10 loops=1)
        Index Cond: (user_id = 123)
        Filter: (created_at > '2024-01-01')
        Rows Removed by Filter: 0
Planning Time: 0.234 ms
Execution Time: 0.112 ms

-- Key things to look for:
-- - Seq Scan vs Index Scan
-- - actual rows vs estimated rows (mismatch = bad stats)
-- - Sort operations (are they using index?)
-- - Nested Loop vs Hash Join (appropriate for data size?)
```

**EXPLAIN Options**
```sql
-- Detailed with buffers
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT ...;

-- JSON format for tools
EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
SELECT ...;

-- Visual plan (paste JSON at explain.depesz.com)
```

---

### Chapter 11: Query Planner Decisions

**Learning Objectives**
- Understand planner cost model
- Influence planner decisions
- Update statistics

**Key Questions to Understand**
- Why did the planner choose a seq scan over an index scan?
- How do you force an index to be used?
- When should you update statistics?

**Planner Cost Model**
```sql
-- See planner cost parameters
SHOW seq_page_cost;      -- 1.0 (baseline)
SHOW random_page_cost;   -- 4.0 (random I/O more expensive)
SHOW cpu_tuple_cost;     -- 0.01
SHOW cpu_index_tuple_cost; -- 0.005

-- Seq scan cost:
-- (pages * seq_page_cost) + (rows * cpu_tuple_cost)

-- Index scan cost:
-- (index_pages * random_page_cost) + (rows * cpu_index_tuple_cost) + heap lookups
```

**Influencing the Planner**
```sql
-- Update statistics (crucial!)
ANALYZE orders;

-- See table statistics
SELECT
    attname,
    n_distinct,
    most_common_vals,
    histogram_bounds
FROM pg_stats
WHERE tablename = 'orders';

-- Increase statistics target for better estimates
ALTER TABLE orders ALTER COLUMN status SET STATISTICS 1000;
ANALYZE orders;

-- Hints (not recommended, but exists)
SET enable_seqscan = off;  -- force index usage
SET enable_hashjoin = off; -- force nested loop
```

---

### Chapter 12: Join Algorithms

**Learning Objectives**
- Understand three join types
- Know when each is used
- Optimize join performance

**Key Questions to Understand**
- When does PostgreSQL choose Hash Join vs Nested Loop?
- Why might a Merge Join be better for sorted data?
- How can you help the planner choose better?

**Join Types**

| Type | Best For | Memory | Notes |
|------|----------|--------|-------|
| Nested Loop | Small outer, indexed inner | Low | O(n*m) worst case |
| Hash Join | Equality joins, medium tables | High | Builds hash table |
| Merge Join | Pre-sorted data, large tables | Low | Requires sorted input |

```sql
-- Nested Loop: good for small outer + indexed inner
SELECT * FROM orders o
JOIN users u ON u.id = o.user_id
WHERE o.id = 123;  -- orders filtered to 1 row

-- Hash Join: builds hash table of smaller side
SELECT * FROM orders o
JOIN users u ON u.id = o.user_id
WHERE o.created_at > '2024-01-01';

-- Merge Join: both sides sorted
SELECT * FROM orders o
JOIN users u ON u.id = o.user_id
ORDER BY o.user_id;  -- already sorted by join key

-- View join choice
EXPLAIN ANALYZE
SELECT ...
-- Look for: "Nested Loop", "Hash Join", "Merge Join"
```

---

### Chapter 13: Common Query Anti-Patterns

**Learning Objectives**
- Recognize slow query patterns
- Fix N+1 queries
- Avoid common mistakes

**Key Questions to Understand**
- What's the N+1 query problem?
- Why are SELECT * and functions on columns bad?
- How do you spot these in production?

**Anti-Patterns and Fixes**

```sql
-- 1. N+1 Queries
-- Bad (in application loop):
for user in users:
    orders = db.query("SELECT * FROM orders WHERE user_id = ?", user.id)

-- Good (single query with join):
SELECT u.*, o.*
FROM users u
LEFT JOIN orders o ON o.user_id = u.id
WHERE u.created_at > '2024-01-01';

-- 2. SELECT * when you only need few columns
-- Bad:
SELECT * FROM orders WHERE user_id = 1;  -- fetches all columns

-- Good:
SELECT id, total_amount, status FROM orders WHERE user_id = 1;

-- 3. Functions preventing index use
-- Bad:
SELECT * FROM users WHERE YEAR(created_at) = 2024;

-- Good:
SELECT * FROM users
WHERE created_at >= '2024-01-01' AND created_at < '2025-01-01';

-- 4. Correlated subqueries
-- Bad:
SELECT *,
    (SELECT COUNT(*) FROM orders WHERE user_id = u.id) as order_count
FROM users u;

-- Good:
SELECT u.*, COALESCE(o.order_count, 0) as order_count
FROM users u
LEFT JOIN (
    SELECT user_id, COUNT(*) as order_count
    FROM orders
    GROUP BY user_id
) o ON o.user_id = u.id;

-- 5. Missing LIMIT
-- Bad:
SELECT * FROM logs WHERE type = 'error';  -- millions of rows

-- Good:
SELECT * FROM logs WHERE type = 'error'
ORDER BY created_at DESC
LIMIT 100;
```

---

## Module 4: Transactions and Concurrency

### Chapter 14: ACID Properties

**Learning Objectives**
- Understand each ACID property
- Know how PostgreSQL implements them
- Design for consistency

**ACID in PostgreSQL**
```
Atomicity:   Transaction is all-or-nothing
             Implementation: Write-ahead log (WAL)

Consistency: Database moves from valid state to valid state
             Implementation: Constraints, triggers

Isolation:   Concurrent transactions don't interfere
             Implementation: MVCC + locks

Durability:  Committed data survives crashes
             Implementation: WAL + checkpoints
```

**Transaction Basics**
```sql
BEGIN;

UPDATE accounts SET balance = balance - 100 WHERE id = 1;
UPDATE accounts SET balance = balance + 100 WHERE id = 2;

-- Check something
SELECT balance FROM accounts WHERE id = 1;

COMMIT;  -- or ROLLBACK to undo

-- Savepoints for partial rollback
BEGIN;
INSERT INTO orders (...);
SAVEPOINT before_items;
INSERT INTO order_items (...);  -- might fail
-- On error:
ROLLBACK TO SAVEPOINT before_items;
-- Continue with rest
COMMIT;
```

---

### Chapter 15: Isolation Levels

**Learning Objectives**
- Understand isolation levels
- Choose appropriate level
- Handle serialization failures

| Resource | Time |
|----------|------|
| Read: https://www.postgresql.org/docs/current/transaction-iso.html | 30 min |

**Key Questions to Understand**
- What anomalies does each level prevent?
- Why is SERIALIZABLE not the default?
- How do you handle serialization failures?

**Isolation Levels**

| Level | Dirty Read | Non-Repeatable Read | Phantom | Serialization Anomaly |
|-------|------------|---------------------|---------|----------------------|
| Read Uncommitted* | No | Yes | Yes | Yes |
| Read Committed | No | No | Yes | Yes |
| Repeatable Read | No | No | No | Yes |
| Serializable | No | No | No | No |

*PostgreSQL treats Read Uncommitted as Read Committed

```sql
-- Set isolation level
BEGIN ISOLATION LEVEL SERIALIZABLE;
-- or
SET TRANSACTION ISOLATION LEVEL REPEATABLE READ;

-- Read Committed (default): sees only committed data
-- Each statement sees latest committed data

-- Repeatable Read: snapshot at transaction start
-- Same query returns same results throughout transaction

-- Serializable: transactions appear to run one at a time
-- May throw serialization_failure error
```

**Handling Serialization Failures**
```python
max_retries = 3
for attempt in range(max_retries):
    try:
        with db.transaction(isolation_level='SERIALIZABLE'):
            # Your logic here
            db.execute("UPDATE accounts SET ...")
            db.execute("UPDATE accounts SET ...")
            break
    except SerializationFailure:
        if attempt == max_retries - 1:
            raise
        continue  # retry transaction
```

---

### Chapter 16: MVCC (Multi-Version Concurrency Control)

**Learning Objectives**
- Understand how MVCC works
- Know xmin/xmax transaction IDs
- Understand tuple visibility

**Key Questions to Understand**
- How does PostgreSQL provide isolation without read locks?
- What are dead tuples and why do they matter?
- What's the problem with long-running transactions?

**MVCC Basics**
```
Each row has:
- xmin: transaction ID that created this version
- xmax: transaction ID that deleted/updated (or 0)

When you UPDATE:
1. Old row gets xmax = current_txid
2. New row created with xmin = current_txid

Transaction sees row if:
- xmin committed AND xmin < snapshot
- xmax not committed OR xmax > snapshot

This means:
- Readers never block writers
- Writers never block readers
- Dead tuples accumulate until VACUUM
```

**Seeing MVCC in Action**
```sql
-- Show tuple metadata
SELECT xmin, xmax, * FROM orders WHERE id = 1;

-- Current transaction ID
SELECT txid_current();

-- Check for bloat
SELECT
    relname,
    n_live_tup,
    n_dead_tup,
    n_dead_tup * 100.0 / NULLIF(n_live_tup + n_dead_tup, 0) as dead_ratio
FROM pg_stat_user_tables
ORDER BY n_dead_tup DESC;
```

---

### Chapter 17: Locking

**Learning Objectives**
- Understand lock types
- Detect and prevent deadlocks
- Use advisory locks

| Resource | Time |
|----------|------|
| Read: https://www.postgresql.org/docs/current/explicit-locking.html | 30 min |

**Key Questions to Understand**
- What's the difference between row locks and table locks?
- How do you prevent deadlocks?
- When would you use advisory locks?

**Lock Types**
```sql
-- Row-level locks
SELECT * FROM orders WHERE id = 1 FOR UPDATE;  -- exclusive
SELECT * FROM orders WHERE id = 1 FOR SHARE;   -- shared
SELECT * FROM orders WHERE id = 1 FOR UPDATE NOWAIT;  -- fail if locked
SELECT * FROM orders WHERE id = 1 FOR UPDATE SKIP LOCKED;  -- skip locked rows

-- Table-level locks
LOCK TABLE orders IN ACCESS SHARE MODE;      -- SELECT
LOCK TABLE orders IN ROW EXCLUSIVE MODE;     -- UPDATE, DELETE
LOCK TABLE orders IN SHARE MODE;             -- Block writes
LOCK TABLE orders IN ACCESS EXCLUSIVE MODE;  -- Block everything

-- See current locks
SELECT
    pid,
    locktype,
    relation::regclass,
    mode,
    granted
FROM pg_locks
WHERE relation::regclass::text = 'orders';
```

**Preventing Deadlocks**
```sql
-- Deadlock: T1 locks A, then B; T2 locks B, then A

-- Solution 1: Always lock in same order
BEGIN;
SELECT * FROM orders WHERE id IN (1, 2) ORDER BY id FOR UPDATE;

-- Solution 2: Lock timeout
SET lock_timeout = '5s';

-- Solution 3: NOWAIT
SELECT * FROM orders WHERE id = 1 FOR UPDATE NOWAIT;
-- Returns error immediately if locked
```

**Advisory Locks**
```sql
-- Application-level locking
SELECT pg_advisory_lock(123);     -- wait for lock
SELECT pg_try_advisory_lock(123); -- non-blocking, returns boolean
SELECT pg_advisory_unlock(123);   -- release

-- Use case: ensure only one job processor runs
BEGIN;
SELECT pg_try_advisory_lock(hashtext('daily-report'));
-- Returns true if we got the lock
-- Do work...
COMMIT;  -- lock released
```

---

### Chapter 18: Vacuum and Bloat

**Learning Objectives**
- Understand why VACUUM is necessary
- Configure autovacuum
- Handle table bloat

| Resource | Time |
|----------|------|
| Read: https://www.postgresql.org/docs/current/routine-vacuuming.html | 30 min |

**Key Questions to Understand**
- Why do dead tuples accumulate?
- What's the difference between VACUUM and VACUUM FULL?
- How do you configure autovacuum for high-write tables?

**VACUUM Operations**
```sql
-- Regular VACUUM: marks dead tuples as reusable
VACUUM orders;

-- VACUUM ANALYZE: also update statistics
VACUUM ANALYZE orders;

-- VACUUM FULL: rewrites entire table (exclusive lock!)
VACUUM FULL orders;  -- Use only as last resort

-- Check autovacuum status
SELECT
    relname,
    last_vacuum,
    last_autovacuum,
    vacuum_count,
    autovacuum_count,
    n_dead_tup
FROM pg_stat_user_tables
ORDER BY n_dead_tup DESC;
```

**Autovacuum Tuning**
```sql
-- Default: vacuum when dead tuples > 50 + 0.2 * table_rows
-- For high-write tables, more aggressive:

ALTER TABLE orders SET (
    autovacuum_vacuum_threshold = 50,
    autovacuum_vacuum_scale_factor = 0.05,  -- 5% instead of 20%
    autovacuum_analyze_threshold = 50,
    autovacuum_analyze_scale_factor = 0.05
);

-- Global settings in postgresql.conf
autovacuum_max_workers = 3
autovacuum_naptime = 1min
autovacuum_vacuum_cost_limit = 400
```

**Transaction ID Wraparound**
```sql
-- PostgreSQL uses 32-bit transaction IDs
-- VACUUM prevents wraparound by freezing old tuples

-- Check wraparound danger
SELECT
    datname,
    age(datfrozenxid) as xid_age,
    current_setting('autovacuum_freeze_max_age') as freeze_max_age
FROM pg_database
ORDER BY age(datfrozenxid) DESC;

-- Force aggressive freeze
VACUUM FREEZE orders;
```

---

## Module 5: Scaling PostgreSQL

### Chapter 19: Connection Pooling (PgBouncer)

**Learning Objectives**
- Understand why connection pooling matters
- Configure PgBouncer
- Choose pooling mode

| Resource | Time |
|----------|------|
| Read: PgBouncer documentation | 30 min |
| Hands-on: Set up PgBouncer | 30 min |

**Key Questions to Understand**
- Why is PostgreSQL per-connection overhead high?
- What's the difference between session, transaction, and statement pooling?
- How many connections should you allow?

**Why Pool Connections?**
```
PostgreSQL forks a new process per connection
- Each connection: ~10MB RAM
- Connection overhead: ~10ms to establish
- Max connections: typically 100-500

With PgBouncer:
- App → PgBouncer (many connections)
- PgBouncer → PostgreSQL (few connections)
- 1000 app connections → 50 DB connections
```

**PgBouncer Config**
```ini
; pgbouncer.ini
[databases]
mydb = host=localhost port=5432 dbname=mydb

[pgbouncer]
listen_addr = 0.0.0.0
listen_port = 6432
auth_type = md5
auth_file = /etc/pgbouncer/userlist.txt

pool_mode = transaction    ; session, transaction, statement
max_client_conn = 1000
default_pool_size = 50
min_pool_size = 10
reserve_pool_size = 5
```

**Pooling Modes**

| Mode | Behavior | Compatible With |
|------|----------|-----------------|
| Session | Connection per session | Everything |
| Transaction | Connection per transaction | Most apps (no SET, PREPARE across tx) |
| Statement | Connection per statement | Simple queries only |

---

### Chapter 20: Replication

**Learning Objectives**
- Set up streaming replication
- Understand logical replication
- Handle failover

| Resource | Time |
|----------|------|
| Read: PostgreSQL replication docs | 45 min |
| Hands-on: Set up replica | 1 hr |

**Key Questions to Understand**
- What's the difference between streaming and logical replication?
- How much replication lag is acceptable?
- What happens during failover?

**Streaming Replication**
```sql
-- Primary configuration (postgresql.conf)
wal_level = replica
max_wal_senders = 5
wal_keep_size = 1GB

-- Create replication user
CREATE ROLE replicator WITH REPLICATION LOGIN PASSWORD 'secret';

-- Replica setup
pg_basebackup -h primary -D /var/lib/postgresql/data -U replicator -P

-- Replica configuration (postgresql.conf)
primary_conninfo = 'host=primary user=replicator password=secret'
```

**Logical Replication**
```sql
-- Publisher (source)
CREATE PUBLICATION mypub FOR TABLE orders, users;

-- Subscriber (destination)
CREATE SUBSCRIPTION mysub
CONNECTION 'host=source dbname=mydb user=postgres'
PUBLICATION mypub;

-- Check status
SELECT * FROM pg_stat_subscription;
SELECT * FROM pg_stat_replication;
```

**Replication Lag**
```sql
-- On primary
SELECT
    client_addr,
    state,
    sent_lsn,
    write_lsn,
    flush_lsn,
    replay_lsn,
    pg_wal_lsn_diff(sent_lsn, replay_lsn) as lag_bytes
FROM pg_stat_replication;

-- On replica
SELECT
    pg_is_in_recovery() as is_replica,
    pg_last_wal_receive_lsn() as received,
    pg_last_wal_replay_lsn() as replayed,
    pg_last_xact_replay_timestamp() as last_replayed_time;
```

---

### Chapter 21: Partitioning

**Learning Objectives**
- Implement table partitioning
- Choose partition strategy
- Query partitioned tables efficiently

| Resource | Time |
|----------|------|
| Read: PostgreSQL partitioning | 30 min |
| Hands-on: Create partitioned table | 45 min |

**Key Questions to Understand**
- When should you partition a table?
- How does partition pruning work?
- What's the overhead of partitioning?

**Partitioning Types**

| Type | Use Case | Example |
|------|----------|---------|
| Range | Time-series, ordered data | Monthly logs |
| List | Category-based | Status, region |
| Hash | Even distribution | User ID |

```sql
-- Range partitioning (by month)
CREATE TABLE orders (
    id SERIAL,
    user_id INTEGER,
    total DECIMAL(10,2),
    created_at TIMESTAMPTZ
) PARTITION BY RANGE (created_at);

CREATE TABLE orders_2024_01 PARTITION OF orders
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
CREATE TABLE orders_2024_02 PARTITION OF orders
    FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');

-- Query uses partition pruning
EXPLAIN ANALYZE
SELECT * FROM orders WHERE created_at >= '2024-01-15';
-- Only scans orders_2024_01 and later partitions

-- List partitioning
CREATE TABLE events (
    id SERIAL,
    type VARCHAR(50),
    data JSONB
) PARTITION BY LIST (type);

CREATE TABLE events_clicks PARTITION OF events FOR VALUES IN ('click');
CREATE TABLE events_views PARTITION OF events FOR VALUES IN ('view', 'impression');

-- Hash partitioning
CREATE TABLE users (
    id SERIAL,
    email VARCHAR(255)
) PARTITION BY HASH (id);

CREATE TABLE users_0 PARTITION OF users FOR VALUES WITH (MODULUS 4, REMAINDER 0);
CREATE TABLE users_1 PARTITION OF users FOR VALUES WITH (MODULUS 4, REMAINDER 1);
-- etc
```

---

### Chapter 22: Read Replicas

**Learning Objectives**
- Route reads to replicas
- Handle replication lag in application
- Scale read workload

**Read Replica Architecture**
```
Writes ──► Primary ──► Replica 1 ──► Reads
                   └──► Replica 2 ──► Reads

Application routes:
- Writes → Primary
- Reads → Replica (round-robin)
- Reads after writes → Primary (avoid lag issues)
```

**Application-Level Routing**
```python
# Example with SQLAlchemy
from sqlalchemy import create_engine

primary = create_engine("postgresql://primary:5432/mydb")
replicas = [
    create_engine("postgresql://replica1:5432/mydb"),
    create_engine("postgresql://replica2:5432/mydb"),
]

def get_read_engine():
    # Round-robin or random
    return random.choice(replicas)

def get_write_engine():
    return primary

# In application
with get_read_engine().connect() as conn:
    result = conn.execute("SELECT * FROM users")

with get_write_engine().connect() as conn:
    conn.execute("INSERT INTO users ...")
```

---

## Module 6: Production Operations

### Chapter 23: Configuration Tuning

**Learning Objectives**
- Tune memory parameters
- Configure for workload type
- Set up connection limits

**Key Parameters**
```ini
# Memory
shared_buffers = 4GB           # 25% of RAM
effective_cache_size = 12GB    # 75% of RAM
work_mem = 256MB               # Per-operation sort/hash memory
maintenance_work_mem = 1GB     # VACUUM, CREATE INDEX

# WAL
wal_buffers = 64MB
checkpoint_completion_target = 0.9
max_wal_size = 4GB

# Query planner
random_page_cost = 1.1         # Lower for SSD (default 4.0)
effective_io_concurrency = 200 # For SSD

# Connections
max_connections = 200          # Keep low, use pooler
```

---

### Chapter 24: Monitoring and pg_stat Views

**Learning Objectives**
- Monitor query performance
- Track table/index statistics
- Set up alerts

**Essential Monitoring Queries**
```sql
-- Slow queries
SELECT
    query,
    calls,
    mean_exec_time,
    total_exec_time
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 20;

-- Table statistics
SELECT
    relname,
    seq_scan,
    seq_tup_read,
    idx_scan,
    idx_tup_fetch,
    n_tup_ins,
    n_tup_upd,
    n_tup_del
FROM pg_stat_user_tables;

-- Cache hit ratio
SELECT
    sum(heap_blks_hit) / sum(heap_blks_hit + heap_blks_read) as cache_hit_ratio
FROM pg_statio_user_tables;

-- Connection count
SELECT count(*) FROM pg_stat_activity WHERE state = 'active';
```

---

### Chapter 25: Backup and Recovery

**Learning Objectives**
- Implement backup strategy
- Perform point-in-time recovery
- Test recovery procedures

**Backup Methods**
```bash
# Logical backup (pg_dump)
pg_dump -h localhost -U postgres mydb > backup.sql
pg_dump -Fc mydb > backup.dump  # custom format, compressed

# Restore
psql -h localhost -U postgres mydb < backup.sql
pg_restore -d mydb backup.dump

# Physical backup (pg_basebackup)
pg_basebackup -h primary -D /backup/base -Ft -z -P

# Continuous archiving (WAL)
archive_mode = on
archive_command = 'cp %p /archive/%f'
```

**Point-in-Time Recovery**
```bash
# 1. Stop server
# 2. Restore base backup
# 3. Create recovery.conf
restore_command = 'cp /archive/%f %p'
recovery_target_time = '2024-01-15 14:30:00'
# 4. Start server - replays WAL to target time
```

---

### Chapter 26: Common Production Issues

**Learning Objectives**
- Diagnose common problems
- Fix performance issues
- Handle emergencies

**Issue Checklist**

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Slow queries | Missing indexes, outdated stats | EXPLAIN ANALYZE, ANALYZE |
| High CPU | Bad query, seq scans | Find slow queries, add indexes |
| High memory | Too many connections | Use PgBouncer |
| Disk full | WAL bloat, table bloat | VACUUM, check archive |
| Connection refused | max_connections | Use pooler |
| Replication lag | Slow replica, network | Check replica, bandwidth |
| Locks | Long transaction | Kill query, add timeouts |

```sql
-- Kill long-running query
SELECT pg_cancel_backend(pid);  -- graceful
SELECT pg_terminate_backend(pid);  -- force

-- Find blocking queries
SELECT
    blocked.pid AS blocked_pid,
    blocking.pid AS blocking_pid,
    blocked.query AS blocked_query,
    blocking.query AS blocking_query
FROM pg_stat_activity blocked
JOIN pg_stat_activity blocking ON blocking.pid = ANY(pg_blocking_pids(blocked.pid))
WHERE blocked.pid != blocking.pid;
```

---

## What "Understanding" Looks Like

| Question | Not This | But This |
|----------|----------|----------|
| "How do indexes work?" | "They make queries fast" | "B-tree structure enables O(log n) lookups. The index stores sorted keys with pointers to heap tuples. For range queries, it does a single seek then sequential read. Write overhead is ~30% per index." |
| "When would an index not help?" | "When the table is small" | "When returning >5-10% of rows (full scan cheaper), when there's a function on the column preventing use, when statistics are outdated and planner estimates wrong selectivity." |
| "Explain MVCC" | "It's for concurrency" | "Each row version has xmin/xmax transaction IDs. Readers see rows based on their snapshot - no read locks needed. Trade-off is dead tuple accumulation requiring vacuum." |
| "Why connection pooling?" | "More connections" | "PostgreSQL forks per connection (~10MB each). Pooling amortizes connection cost, lets 1000 app connections share 50 DB connections in transaction mode." |

---

## Learning Timeline

| Time Available | Focus |
|----------------|-------|
| 1 week | Modules 1-2 (foundations + indexing) |
| 2 weeks | Modules 1-4 (add transactions) |
| 3 weeks | Full curriculum including production |

---

## Daily Practice Routine

| Time | Activity |
|------|----------|
| 20 min | Read one chapter section |
| 30 min | Hands-on with EXPLAIN ANALYZE |
| 10 min | Write down what you learned |

Total: ~1 hour/day

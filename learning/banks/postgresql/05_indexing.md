# PostgreSQL Indexing

## 1. Fundamentals

### What is an Index?

A separate data structure that maintains pointers to rows in a table (heap), enabling fast lookups without scanning every row.

```
Without index:  Scan all N rows         → O(n)
With index:     Tree lookup + heap fetch → O(log n)
```

### How PostgreSQL Stores Data

Every table row lives on the heap which disk-IO. Indexes don't store full rows, they store the indexed columns + a pointer (ctid) back to the heap.

```
Table (Heap):
┌────────┬────────┬────────┬────────┐
│ Page 0 │ Page 1 │ Page 2 │ Page 3 │  ← 8KB pages
│ rows   │ rows   │ rows   │ rows   │
└────────┴────────┴────────┴────────┘

Index:
Separate structure storing (indexed_value → ctid)
ctid = (page_number, offset) pointing to the heap row
```

### Creating and Managing Indexes

```sql
-- Create index (blocks writes)
CREATE INDEX idx_users_email ON users(email);

-- Create index in production (non-blocking)
CREATE INDEX CONCURRENTLY idx_users_email ON users(email);
-- Takes longer but doesn't lock the table for writes
-- If it fails, you get an INVALID index — drop it and retry

-- Create unique index
CREATE UNIQUE INDEX idx_users_email_unique ON users(email);

-- Drop index
DROP INDEX idx_users_email;
DROP INDEX CONCURRENTLY idx_users_email;  -- non-blocking

-- Rebuild index (reclaims space after heavy updates/deletes)
REINDEX INDEX idx_users_email;
REINDEX INDEX CONCURRENTLY idx_users_email;  -- non-blocking (PG 12+)
REINDEX TABLE users;  -- all indexes on table
```

---

## 2. B+ Tree Index (Default)

PostgreSQL uses a B+ tree (not a plain B-tree). In a plain B-tree, every node (root, internal, and leaf) stores both keys and data pointers — so internal nodes are bigger, fewer keys fit per node, the tree is deeper, and range scans require traversing up and down the tree. In a B+ tree, all data pointers live in the leaf nodes, and leaf nodes are linked together. Internal nodes only store keys for routing. This means internal nodes are smaller, more keys fit per node, the tree is shallower (fewer I/O ops), and range scans just follow the leaf-level linked list.

A balanced, self-balancing tree. When you insert or delete entries, the tree restructures itself (splits or merges nodes) to maintain this property. All leaf nodes are at exactly the same depth.

### Complexity

| Operation  | Time         | Notes                           |
| ---------- | ------------ | ------------------------------- |
| Lookup     | O(log n)     | traverse from root to leaf      |
| Insert     | O(log n)     | plus occasional node split      |
| Delete     | O(log n)     | plus occasional merge/rebalance |
| Range scan | O(log n + k) | k = number of matching rows     |
| **Space**  | O(n)         | one entry per indexed row       |

The branching factor is high (a single node fits many keys, typically filling an 8KB page), so in practice the tree is very shallow — often 3-4 levels even for millions of rows.

### Structure

```
                     [50]                    ← Root
                    /    \
               [25,35]    [75,85]           ← Internal nodes
              /   |   \   /   |   \
          [10,20][30][40,45][60,70][80][90]  ← Leaf nodes (linked list)
              │
              └── Each leaf entry:
                  - Indexed value
                  - ctid (pointer to heap row)
```

**Properties:**

- Balanced — all leaf nodes at the same depth → consistent O(log n)
- Sorted — enables range queries, ORDER BY, MIN/MAX
- Leaf nodes are doubly-linked — once you find the range start, walk sideways
- Self-balancing on inserts/deletes

### Lookup Flow

```
SELECT * FROM users WHERE id = 45;

Root [50]      → 45 < 50, go left
Internal [25,35] → 45 > 35, go to third child
Leaf [40,45]   → found 45, follow ctid → read heap page

Cost: 3 page reads (tree depth) + 1 heap page read
For 10M rows: depth ≈ 4 levels. That's 4 I/O ops vs 10M seq reads.
```

### What B-Tree Supports

```sql
-- Equality
WHERE email = 'alice@example.com'

-- Range
WHERE created_at > '2024-01-01'
WHERE id BETWEEN 100 AND 200

-- Sorting
ORDER BY email LIMIT 10

-- MIN/MAX (reads first/last leaf)
SELECT MAX(id) FROM users;

-- Prefix LIKE (rewritten as range: >= 'alice' AND < 'alicf')
WHERE email LIKE 'alice%'
```

### What B-Tree Cannot Do

```sql
-- Suffix/infix search (no sorted path to seek to)
WHERE email LIKE '%@gmail.com'

-- Functions on the column (breaks sort order)
WHERE LOWER(email) = 'alice@example.com'
-- Fix: CREATE INDEX idx ON users(LOWER(email));

-- NOT conditions (low selectivity)
WHERE email != 'test@example.com'

-- Low selectivity (planner picks seq scan)
WHERE active = true  -- if 90% are active
```

## 3. Scan Types

Scan types are the mechanisms how Postgres actually uses indexes.

| Scan Type         | How It Works                                                            | Best For                                                               | Selectivity |
| ----------------- | ----------------------------------------------------------------------- | ---------------------------------------------------------------------- | ----------- |
| Index Scan        | Traverses index to find ctids, fetches each row from heap one by one    | Small number of rows                                                   | < ~1-5%     |
| Index-Only Scan   | Reads data directly from the index, no heap access at all               | Queries where all columns are in the index                             | < ~1-5%     |
| Bitmap Index Scan | Builds a bitmap of matching pages, then reads those heap pages in order | Medium number of rows; combining multiple indexes (BitmapAnd/BitmapOr) | ~5-20%      |
| Sequential Scan   | Reads every page of the table, no index used                            | Most rows, small tables, or no useful index                            | > ~20%      |

These selectivity thresholds are rough heuristics. The planner uses cost estimates based on table statistics (`pg_stats`), page counts, and correlation.

**Index-Only Scan requirements:**

1. All SELECT + WHERE columns must be in the index
2. Visibility map must show pages as all-visible (maintained by VACUUM)

```sql
-- Index Scan
EXPLAIN ANALYZE SELECT * FROM users WHERE id = 1000;

-- Index-Only Scan
EXPLAIN ANALYZE SELECT id FROM users WHERE id = 1000;

-- Bitmap Index Scan
EXPLAIN ANALYZE SELECT * FROM users WHERE id BETWEEN 1000 AND 2000;

-- Sequential Scan
EXPLAIN ANALYZE SELECT * FROM users;
```

---

## 4. Index Types and Strategies

Index **types** and index **strategies** are two different dimensions — they're orthogonal, not alternatives.

- **Index type** (B+ tree, Hash, GIN, GiST, SP-GiST, BRIN) = the **data structure** used
- **Index strategy** (composite, partial, covering, unique, expression) = **how** the index is applied, regardless of type

They layer on top of each other. A partial composite unique B+ tree index is a valid thing:

```sql
CREATE UNIQUE INDEX idx ON orders(user_id, created_at)
WHERE status = 'pending';
-- type: B+ tree, strategies: unique + composite + partial
```

### Index Types

| Type    | Best For                        | Key Operators            |
| ------- | ------------------------------- | ------------------------ |
| B-Tree  | Equality, range, sorting        | =, <, >, <=, >=, BETWEEN |
| Hash    | Equality only                   | =                        |
| GIN     | Arrays, JSONB, full-text search | @>, &&, @@, ?, ?&, ?\|   |
| GiST    | Geometric, ranges, hierarchies  | &&, @>, <<, >>           |
| SP-GiST | Partitioned data (IP, phone)    | <<, >>                   |
| BRIN    | Large sequential/ordered data   | <, >, =                  |

### Hash Index

```sql
CREATE INDEX idx_email_hash ON users USING HASH (email);

-- Only supports equality
WHERE email = 'alice@example.com'  -- ✓
WHERE email > 'a'                  -- ✗
ORDER BY email                     -- ✗
```

Smaller than B-tree, lower write overhead. Rarely used — B-tree handles equality well enough. WAL-logged and crash-safe since PG 10.

### GIN (Generalized Inverted Index)

An inverted index: maps each element/key to a list of rows containing it.

```sql
-- Arrays
CREATE INDEX idx_tags ON posts USING GIN (tags);
SELECT * FROM posts WHERE tags @> ARRAY['postgresql'];    -- contains
SELECT * FROM posts WHERE tags && ARRAY['pg', 'mysql'];   -- overlaps

-- JSONB
CREATE INDEX idx_data ON events USING GIN (data);
SELECT * FROM events WHERE data @> '{"type": "click"}';   -- contains
SELECT * FROM events WHERE data ? 'user_id';              -- has key
SELECT * FROM events WHERE data ?& ARRAY['type', 'uid'];  -- has all keys
SELECT * FROM events WHERE data ?| ARRAY['type', 'uid'];  -- has any key

-- Full-text search
CREATE INDEX idx_search ON posts USING GIN (to_tsvector('english', title));
SELECT * FROM posts
WHERE to_tsvector('english', title) @@ to_tsquery('english', 'postgresql & tutorial');
```

**GIN operator classes for JSONB:**

```sql
-- jsonb_ops (default): supports all JSONB operators
CREATE INDEX idx ON events USING GIN (data);

-- jsonb_path_ops: smaller, only supports @> containment
CREATE INDEX idx ON events USING GIN (data jsonb_path_ops);
```

**Trade-offs:** GIN is slower to build and update than B-tree (uses a pending list for batched inserts). Fast for reads on complex data types.

### GiST (Generalized Search Tree)

Supports overlapping/containment queries on complex data types.

```sql
-- Range types (time ranges, numeric ranges)
CREATE INDEX idx_during ON reservations USING GIST (during);
SELECT * FROM reservations WHERE during && '[2024-01-15, 2024-01-16)';  -- overlaps
SELECT * FROM reservations WHERE during @> '2024-01-15 10:00'::timestamptz;

-- Geometric / PostGIS
CREATE INDEX idx_coords ON locations USING GIST (coordinates);
SELECT * FROM locations ORDER BY coordinates <-> POINT(0,0) LIMIT 5;  -- nearest neighbor

-- Hierarchical data (ltree)
CREATE EXTENSION ltree;
CREATE INDEX idx_path ON categories USING GIST (path);
SELECT * FROM categories WHERE path <@ 'electronics.computers';  -- descendants

-- Exclusion constraints (requires GiST)
CREATE TABLE room_bookings (
    room_id INTEGER,
    during TSTZRANGE,
    EXCLUDE USING GIST (room_id WITH =, during WITH &&)
);
-- Prevents overlapping bookings for the same room
```

### SP-GiST (Space-Partitioned GiST)

For data with natural partitioning structure — radix trees, quad trees, k-d trees.

```sql
-- IP addresses (trie/radix tree)
CREATE INDEX idx_ip ON connections USING SPGIST (client_ip inet_ops);
SELECT * FROM connections WHERE client_ip << '192.168.1.0/24';

-- Text with prefix queries (radix tree)
CREATE INDEX idx_phone ON contacts USING SPGIST (phone text_ops);
SELECT * FROM contacts WHERE phone LIKE '555%';
```

### BRIN (Block Range Index)

Stores min/max per block range (default 128 pages). Tiny index for huge ordered tables.

```sql
CREATE INDEX idx_logs_ts ON logs USING BRIN (created_at);
```

```
Works when data is physically ordered:
┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
│ Jan 1-5 │ │ Jan 5-9 │ │Jan 10-15│ │Jan 15-20│  ← correlation ≈ 1.0
└─────────┘ └─────────┘ └─────────┘ └─────────┘

BRIN stores: [min=Jan1, max=Jan5] [min=Jan5, max=Jan9] ...
Query: WHERE created_at > 'Jan 12' → skip first two block ranges entirely

Size comparison on 10M rows:
  BRIN: ~100 KB
  B-Tree: ~200 MB
```

**When to choose BRIN over B-tree:** Two conditions must hold: (1) high correlation — data is physically ordered on disk (append-only, never updated), and (2) large table where the size difference matters (BRIN ~100KB vs B-tree ~200MB on 100M rows). The trade-off is lower precision — BRIN may read some non-matching blocks within a matching range, but for append-only time-series data that cost is minimal.

**When BRIN fails:** randomly inserted data has wide min/max ranges per block, so BRIN can't exclude anything. Check correlation before choosing:

```sql
SELECT attname, correlation
FROM pg_stats
WHERE tablename = 'logs' AND attname = 'created_at';
-- correlation close to 1.0 or -1.0 → BRIN is effective
-- correlation close to 0 → BRIN is useless
```

### Choosing the Right Index Type

```
Equality/range on scalars       → B-Tree
Array containment/overlap       → GIN
JSONB queries                   → GIN
Full-text search                → GIN (read-heavy) or GiST (mixed)
Range overlap/containment       → GiST
Geometric/spatial/nearest       → GiST
Exclusion constraints           → GiST
Hierarchical (ltree)            → GiST
IP/phone prefix searches        → SP-GiST
Large ordered table, range scan → BRIN
Equality-only on large values   → Hash (rare)
```

## 5. Index Strategies

### Composite Indexes

An index on multiple columns: `CREATE INDEX idx ON orders(user_id, status, created_at);` The index is a sorted tree on `(A, B, C)` — sorted first by A, then B within A, then C within B.

```
Index (A, B, C) can serve:
  WHERE A = ?
  WHERE A = ? AND B = ?
  WHERE A = ? AND B = ? AND C = ?
  WHERE A = ? AND B = ? ORDER BY C
  ORDER BY A, B, C

Index (A, B, C) CANNOT serve:
  WHERE B = ?             ← no leading column
  WHERE C = ?             ← no leading columns
  WHERE A = ? AND C = ?   ← skips B (uses A only, filters C)
  ORDER BY B, C           ← no leading column
```

Following is the column ordering strategy

**Rule: equality columns first, range columns last.**

```sql
-- Query pattern:
WHERE user_id = 1 AND status = 'completed' AND created_at > '2024-01-01'

-- Bad order: (user_id, created_at, status)
-- created_at is range → stops further index traversal → status can't use index

-- Good order: (user_id, status, created_at)
-- user_id = equality, status = equality, created_at = range (at the end)
-- All three conditions use the index
```

**Why range stops traversal:** Once the B-tree hits a range condition, it can only scan forward — within `age > 25`, the next column's values are scattered across different age groups, so it can't seek on them.

**Design by query patterns, not selectivity:**

```sql
-- If queries always include user_id, sometimes include status:
CREATE INDEX idx ON orders(user_id, status, created_at);

-- This one index serves:
-- WHERE user_id = ?
-- WHERE user_id = ? AND status = ?
-- WHERE user_id = ? AND status = ? AND created_at > ?
-- WHERE user_id = ? AND status = ? ORDER BY created_at
```

---

### Partial Indexes

Index only a subset of rows using a WHERE clause.

```sql
-- Only index pending orders (maybe 5% of rows)
CREATE INDEX idx_pending ON orders(user_id, created_at)
WHERE status = 'pending';

-- 95% smaller than a full index
-- Faster to scan, faster to maintain
```

**The query must include the index condition for the planner to use it:**

```sql
-- ✓ Uses idx_pending
SELECT * FROM orders WHERE status = 'pending' AND user_id = 100;

-- ✗ Cannot use idx_pending
SELECT * FROM orders WHERE status = 'completed' AND user_id = 100;
```

### Common Patterns

```sql
-- Soft delete: index only non-deleted rows
CREATE INDEX idx_email_active ON users(email) WHERE deleted_at IS NULL;

-- Unique among a subset
CREATE UNIQUE INDEX idx_unique_email ON users(email) WHERE deleted_at IS NULL;

-- Null exclusion
CREATE INDEX idx_phone ON users(phone) WHERE phone IS NOT NULL;

-- Status-based (hot partition)
CREATE INDEX idx_processing ON orders(user_id, created_at)
WHERE status IN ('pending', 'processing');
```

### Covering Indexes and INCLUDE

### The Problem

```sql
CREATE INDEX idx ON orders(user_id, status);

SELECT user_id, status, total_amount FROM orders WHERE user_id = 1;
-- Index Scan → finds rows → must fetch total_amount from heap
```

### The Solution: INCLUDE (PG 11+)

```sql
CREATE INDEX idx ON orders(user_id, status) INCLUDE (total_amount);

SELECT user_id, status, total_amount FROM orders WHERE user_id = 1;
-- Index Only Scan → total_amount is in the leaf nodes → no heap access
```

**INCLUDE columns:**

- Stored in leaf nodes only (not internal nodes → smaller tree)
- Enable index-only scans
- Cannot be used for filtering or sorting

**When to use INCLUDE vs adding to key:**

```sql
-- Column is used in WHERE/ORDER BY → make it an index key
CREATE INDEX idx ON orders(user_id, status, created_at);

-- Column is only in SELECT → use INCLUDE
CREATE INDEX idx ON orders(user_id, status) INCLUDE (total_amount, created_at);
```

### Visibility Map and Heap Fetches

Index-only scans need to verify row visibility (MVCC). The visibility map tracks which heap pages have all-visible tuples.

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT user_id, status FROM orders WHERE user_id = 100;
-- Index Only Scan ...
-- Heap Fetches: 0     ← all pages all-visible, true index-only
-- Heap Fetches: 500   ← 500 rows needed heap check (recent inserts/updates)

-- Fix: run VACUUM to update visibility map
VACUUM orders;
```

### Trade-offs

```
Covering indexes are NOT free:
  - Larger index size (more data stored in leaves)
  - Slower writes (more data to update)
  - More memory needed to cache

When to use:
  ✓ High-frequency queries
  ✓ When heap fetches are a bottleneck
  ✗ Write-heavy tables
  ✗ Infrequent queries
```

---

## 8. When Indexes Hurt

### Write Overhead

Every index must be updated on INSERT, and on UPDATE of indexed columns. DELETE marks entries for cleanup.

```
Table with 0 extra indexes:  INSERT 100K rows → 500ms
Table with 5 extra indexes:  INSERT 100K rows → 1500ms (3x slower)
```

Each index adds ~20-30% write overhead.

### When the Planner Ignores Indexes

| Reason             | Why                                      | Fix                                                     |
| ------------------ | ---------------------------------------- | ------------------------------------------------------- |
| Low selectivity    | Returns >5-10% of rows, seq scan cheaper | Partial index for the rare value                        |
| Function on column | `LOWER(email)` breaks sort order         | Functional index: `CREATE INDEX idx ON t(LOWER(email))` |
| Type mismatch      | Implicit cast prevents index use         | Use correct types in queries                            |
| OR conditions      | Can't traverse single index path         | Rewrite as UNION, or use separate indexes (BitmapOr)    |
| Stale statistics   | Planner estimates are wrong              | `ANALYZE table_name;`                                   |
| Small table        | Everything fits in a few pages           | Don't index — seq scan is fine                          |
| NOT conditions     | `!=`, `NOT IN` — low selectivity         | Redesign query                                          |

### Finding Unused Indexes

```sql
SELECT
    schemaname || '.' || relname AS table,
    indexrelname AS index,
    pg_size_pretty(pg_relation_size(indexrelid)) AS size,
    idx_scan AS scans
FROM pg_stat_user_indexes
WHERE idx_scan = 0
AND indexrelname NOT LIKE '%_pkey'
ORDER BY pg_relation_size(indexrelid) DESC;
```

### Finding Redundant Indexes

```
Index (A) is redundant if index (A, B) exists.
Index (B) is NOT redundant if (A, B) exists — different leading column.
```

### Safe Removal Process

```sql
-- 1. Identify candidates (idx_scan = 0 or very low)
-- 2. Monitor for a week+ before dropping
-- 3. Drop non-blocking
DROP INDEX CONCURRENTLY idx_unused;
-- 4. If something breaks, recreate
CREATE INDEX CONCURRENTLY idx_unused ON table(column);
```

## 9. Index Maintenance

### Rebuilding Bloated Indexes

After heavy UPDATE/DELETE cycles, indexes accumulate dead space.

```sql
-- Check if index is larger than expected
SELECT
    indexrelname AS index,
    pg_size_pretty(pg_relation_size(indexrelid)) AS index_size,
    pg_size_pretty(pg_relation_size(relid)) AS table_size
FROM pg_stat_user_indexes
WHERE relname = 'orders';

-- Rebuild non-blocking (PG 12+)
REINDEX INDEX CONCURRENTLY idx_name;
```

### Statistics

```sql
-- Update statistics for the planner
ANALYZE orders;

-- Increase statistics granularity for important columns
ALTER TABLE orders ALTER COLUMN status SET STATISTICS 1000;
ANALYZE orders;

-- Check current statistics
SELECT attname, n_distinct, most_common_vals, most_common_freqs, correlation
FROM pg_stats
WHERE tablename = 'orders' AND attname = 'status';
```

### Analyzing Index Usage

```sql
-- Check if indexes are being used
SELECT
    schemaname,
    relname,
    indexrelname,
    idx_scan,          -- number of index scans
    idx_tup_read,      -- index entries read
    idx_tup_fetch      -- heap rows fetched
FROM pg_stat_user_indexes
WHERE relname = 'users';

-- Find tables with heavy seq scans (may need indexes)
SELECT
    relname,
    seq_scan,
    seq_tup_read,
    idx_scan,
    idx_tup_fetch
FROM pg_stat_user_tables
WHERE seq_scan > 0
ORDER BY seq_tup_read DESC
LIMIT 10;
```

---

## 10. Hands-On Exercises

### Exercise 1: Scan Type Comparison

```sql
CREATE TABLE test_index (
    id SERIAL PRIMARY KEY,
    category VARCHAR(50),
    value INTEGER
);

INSERT INTO test_index (category, value)
SELECT 'category_' || (i % 100), random() * 1000
FROM generate_series(1, 1000000) i;

-- Without index
EXPLAIN ANALYZE
SELECT * FROM test_index WHERE category = 'category_50';
-- Seq Scan, ~100ms

CREATE INDEX idx_test_category ON test_index(category);

-- With index
EXPLAIN ANALYZE
SELECT * FROM test_index WHERE category = 'category_50';
-- Index Scan, ~5ms

-- Observe selectivity threshold
CREATE INDEX idx_test_value ON test_index(value);

EXPLAIN ANALYZE SELECT * FROM test_index WHERE value < 10;   -- ~1% → index
EXPLAIN ANALYZE SELECT * FROM test_index WHERE value < 100;  -- ~10% → bitmap
EXPLAIN ANALYZE SELECT * FROM test_index WHERE value < 500;  -- ~50% → seq scan
```

### Exercise 2: Composite Index Column Order

```sql
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL,
    total_amount DECIMAL(10,2),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO orders (user_id, status, total_amount, created_at)
SELECT
    (random() * 10000)::INTEGER,
    (ARRAY['pending','processing','completed','cancelled'])[floor(random()*4+1)::INTEGER],
    (random() * 1000)::DECIMAL(10,2),
    NOW() - (random() * 365 || ' days')::INTERVAL
FROM generate_series(1, 1000000);

-- Create optimal index for this query pattern
CREATE INDEX idx_orders_optimal ON orders(user_id, status, created_at DESC);

EXPLAIN ANALYZE
SELECT * FROM orders
WHERE user_id = 100 AND status = 'completed' AND created_at > '2024-01-01'
ORDER BY created_at DESC
LIMIT 10;
```

### Exercise 3: Index-Only Scan with INCLUDE

```sql
-- Without INCLUDE
CREATE INDEX idx_no_include ON orders(user_id, status);

EXPLAIN (ANALYZE, BUFFERS)
SELECT user_id, status, total_amount FROM orders
WHERE user_id = 100 AND status = 'completed';
-- Index Scan with Heap Fetches

-- With INCLUDE
CREATE INDEX idx_with_include ON orders(user_id, status) INCLUDE (total_amount);
VACUUM orders;

EXPLAIN (ANALYZE, BUFFERS)
SELECT user_id, status, total_amount FROM orders
WHERE user_id = 100 AND status = 'completed';
-- Index Only Scan, Heap Fetches: 0
```

### Exercise 4: BRIN vs B-Tree on Time-Series

```sql
CREATE TABLE metrics (
    id SERIAL,
    sensor_id INTEGER,
    value NUMERIC,
    recorded_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO metrics (sensor_id, value, recorded_at)
SELECT
    (random() * 100)::INTEGER,
    random() * 1000,
    '2024-01-01'::TIMESTAMPTZ + (i || ' seconds')::INTERVAL
FROM generate_series(1, 5000000) i;

CREATE INDEX idx_metrics_brin ON metrics USING BRIN (recorded_at);
CREATE INDEX idx_metrics_btree ON metrics USING BTREE (recorded_at);

-- Compare sizes
SELECT indexrelname, pg_size_pretty(pg_relation_size(indexrelid)) as size
FROM pg_stat_user_indexes WHERE relname = 'metrics';
-- BRIN: ~50 KB vs B-Tree: ~100 MB

EXPLAIN ANALYZE
SELECT * FROM metrics WHERE recorded_at BETWEEN '2024-06-01' AND '2024-06-02';
```

### Exercise 5: GIN for JSONB

```sql
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    data JSONB
);

INSERT INTO products (data)
SELECT jsonb_build_object(
    'name', 'Product ' || i,
    'price', (random() * 100)::INTEGER,
    'category', (ARRAY['electronics','books','clothing'])[floor(random()*3+1)::INTEGER],
    'tags', ARRAY['tag' || (i % 10), 'tag' || (i % 5)]
)
FROM generate_series(1, 100000) i;

-- Without index
EXPLAIN ANALYZE
SELECT * FROM products WHERE data @> '{"category": "electronics"}';

-- With GIN
CREATE INDEX idx_products_data ON products USING GIN (data);

EXPLAIN ANALYZE
SELECT * FROM products WHERE data @> '{"category": "electronics"}';

-- Expression index for specific field (more efficient for known paths)
CREATE INDEX idx_products_category ON products ((data->>'category'));

EXPLAIN ANALYZE
SELECT * FROM products WHERE data->>'category' = 'electronics';
```

### Exercise 6: Partial Index Size Savings

```sql
-- Full index
CREATE INDEX idx_orders_full ON orders(user_id, created_at);

-- Partial index (only pending, ~25% of rows)
CREATE INDEX idx_orders_partial ON orders(user_id, created_at)
WHERE status = 'pending';

-- Compare sizes
SELECT indexrelname, pg_size_pretty(pg_relation_size(indexrelid)) as size
FROM pg_stat_user_indexes
WHERE relname = 'orders' AND indexrelname LIKE 'idx_orders_%';

-- Both serve this query
EXPLAIN ANALYZE
SELECT * FROM orders WHERE status = 'pending' AND user_id = 100;
```

---

## 11. Interview Questions

### "How do B-tree indexes work?"

> A B-tree is a balanced tree where each node contains sorted keys and child pointers. Leaf nodes store the indexed value + a ctid pointing to the heap row. Lookups are O(log n) — start at the root, compare values, follow the right child pointer down to the leaf. For range queries, leaf nodes are linked so you find the start and walk sideways. The tree self-balances on inserts/deletes to maintain consistent depth.

### "When would an index not be used?"

> Low selectivity (returning >5-10% of rows makes seq scan cheaper), functions on the indexed column breaking sort order, type mismatches causing implicit casts, stale statistics giving bad estimates, OR conditions that can't traverse a single index path, and small tables where seq scan is faster. I'd check EXPLAIN ANALYZE and run ANALYZE if statistics are stale.

### "How do you decide column order in a composite index?"

> Equality conditions first, range conditions last. A range condition (>, <, BETWEEN) stops further index traversal for subsequent columns. Leading columns must be present in the query — index (A, B, C) can't be used for WHERE B = ?. I design based on actual query patterns: the column that appears in every query goes first.

### "When would you use GIN vs B-tree for JSONB?"

> GIN for containment operators (@>, ?, ?&) and flexible querying of arbitrary keys. B-tree expression index like `(data->>'field')` for equality/range on specific known fields. GIN is more versatile for schemaless access patterns; B-tree expression indexes are smaller and support sorting.

### "What is BRIN and when would you use it?"

> BRIN stores min/max per block range. It's tiny (1000x smaller than B-tree) but requires data to be physically ordered — high correlation between column value and physical position. Perfect for time-series, logs, append-only tables. The trade-off is lower precision: it may read some non-matching blocks. Check column correlation in `pg_stats` before choosing BRIN.

### "What is an index-only scan?"

> It retrieves data directly from the index without touching the heap. Requires all query columns to be in the index (use INCLUDE for non-key columns) and the visibility map to show pages as all-visible. VACUUM maintains the visibility map. If EXPLAIN shows high Heap Fetches, run VACUUM. Can be 2-10x faster than a regular index scan.

### "When would you NOT create an index?"

> Write-heavy tables where each index adds ~20-30% write overhead. Low-cardinality columns where most rows share the same value. Small tables that fit in a few pages. Columns already covered by the leading prefix of an existing composite index. I always check pg_stat_user_indexes for unused indexes before adding more.

### "How do you find and remove bad indexes?"

> Query `pg_stat_user_indexes` for `idx_scan = 0` (never used) and check size. Look for redundant indexes where (A) exists alongside (A, B). Monitor candidates for a week, then `DROP INDEX CONCURRENTLY`. For production, always use CONCURRENTLY for both creates and drops to avoid blocking.

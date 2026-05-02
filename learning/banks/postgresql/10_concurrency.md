# PostgreSQL Concurrency and Locking

## 1. ACID Properties

### The Four Guarantees

```
A - Atomicity:   All operations in a transaction succeed or all fail
C - Consistency: Database moves from one valid state to another valid state
I - Isolation:   Concurrent transactions don't see each other's uncommitted changes
D - Durability:  Once COMMIT returns, data survives crashes
```

### How PostgreSQL Implements Each

```
Atomicity  → Write-Ahead Log (WAL)
             All changes logged before applied. On abort, nothing persists.

Consistency → Constraints, triggers, foreign keys
              Violations abort the transaction.

Isolation  → MVCC (Multi-Version Concurrency Control)
             Each transaction sees a snapshot. Readers don't block writers.

Durability → WAL synced to disk before COMMIT returns
             On crash, replay WAL to recover committed transactions.
```

### Transactions

```sql
-- Explicit transaction
BEGIN;
    UPDATE accounts SET balance = balance - 100 WHERE id = 1;
    UPDATE accounts SET balance = balance + 100 WHERE id = 2;
COMMIT;
-- Both succeed together, or neither does

-- Rollback
BEGIN;
    UPDATE accounts SET balance = balance - 100 WHERE id = 1;
ROLLBACK;
-- Nothing persisted

-- Implicit transactions (autocommit)
UPDATE accounts SET balance = 100 WHERE id = 1;
-- Automatically wrapped in BEGIN...COMMIT

-- Savepoints for partial rollback
BEGIN;
    INSERT INTO orders (user_id, total) VALUES (1, 100);
    SAVEPOINT before_items;
    INSERT INTO order_items (order_id, product_id, qty) VALUES (1, 1, 5);
    -- Oops, failed
    ROLLBACK TO SAVEPOINT before_items;
    INSERT INTO order_items (order_id, product_id, qty) VALUES (1, 2, 3);
COMMIT;  -- Order created, with second item
```

### WAL and Durability

```
Client                    PostgreSQL                    Disk
   |                          |                          |
   |--- BEGIN -------------->|                          |
   |--- UPDATE... ---------->|                          |
   |                          |--- Write to WAL buffer --|
   |--- COMMIT ------------->|                          |
   |                          |--- fsync WAL to disk --->|
   |                          |                          |--- WAL on disk
   |<-- COMMIT OK ------------|                          |
   |                          |--- Later: checkpoint     |
   |                          |    writes data pages --->|

synchronous_commit = on  (default) → safest, waits for disk
synchronous_commit = off → faster, up to ~600ms of commits could be lost on crash
```

## 2. Isolation Levels

### Isolation Anomalies

```
Dirty Read:
  T1 writes, T2 reads uncommitted data, T1 rolls back
  T2 saw data that never existed

Non-Repeatable Read:
  T1 reads row, T2 updates & commits, T1 reads again
  T1 sees different values for same row

Phantom Read:
  T1 queries rows matching condition, T2 inserts matching row & commits
  T1 queries again, sees new row
  The issue is new records appearing

Serialization Anomaly (Write Skew):
  Two transactions read the same data, make independent decisions, and write to different rows.
  T1 and T2 run concurrently, result differs from any serial execution
```

### What Each Level Prevents

| Level              | Dirty Read | Non-Repeatable Read | Phantom | Serialization Anomaly |
| ------------------ | ---------- | ------------------- | ------- | --------------------- |
| Read Uncommitted\* | No         | Yes                 | Yes     | Yes                   |
| Read Committed     | No         | Yes                 | Yes     | Yes                   |
| Repeatable Read    | No         | No                  | No      | Yes                   |
| Serializable       | No         | No                  | No      | No                    |

\*PostgreSQL treats Read Uncommitted as Read Committed.

### Read Committed (Default)

Each **statement** sees only data committed before that statement started. Different statements in the same transaction may see different data.

```sql
-- Session 1:
BEGIN;
SELECT balance FROM accounts WHERE id = 1;  -- Returns 1000

-- Session 2:
UPDATE accounts SET balance = 500 WHERE id = 1;
COMMIT;

-- Session 1:
SELECT balance FROM accounts WHERE id = 1;  -- Returns 500 (changed!)
COMMIT;
```

### Repeatable Read

Transaction sees a snapshot from its **first query**. Same query returns same results throughout.

```sql
-- Session 1:
BEGIN ISOLATION LEVEL REPEATABLE READ;
SELECT balance FROM accounts WHERE id = 1;  -- Returns 1000

-- Session 2:
UPDATE accounts SET balance = 500 WHERE id = 1;
COMMIT;

-- Session 1:
SELECT balance FROM accounts WHERE id = 1;  -- Still returns 1000!
COMMIT;
```

**Update conflict:** if you try to update a row that was modified by another committed transaction after your snapshot:

```sql
-- Session 1:
BEGIN ISOLATION LEVEL REPEATABLE READ;
SELECT balance FROM accounts WHERE id = 1;  -- 1000

-- Session 2:
UPDATE accounts SET balance = 500 WHERE id = 1;
COMMIT;

-- Session 1:
UPDATE accounts SET balance = balance + 100 WHERE id = 1;
-- ERROR: could not serialize access due to concurrent update
-- Must retry the entire transaction
```

### Serializable

Guarantees transactions behave as if run one after another. Prevents all anomalies including write skew.

```sql
-- Write Skew Example:
-- Two on-call doctors, at least one must remain on-call

-- With REPEATABLE READ (broken):
-- Session 1:
BEGIN ISOLATION LEVEL REPEATABLE READ;
SELECT count(*) FROM doctors WHERE on_call = true;  -- 2
UPDATE doctors SET on_call = false WHERE name = 'Alice';
COMMIT;  -- succeeds

-- Session 2 (concurrent):
BEGIN ISOLATION LEVEL REPEATABLE READ;
SELECT count(*) FROM doctors WHERE on_call = true;  -- 2 (snapshot)
UPDATE doctors SET on_call = false WHERE name = 'Bob';
COMMIT;  -- succeeds — both doctors now off-call!

-- With SERIALIZABLE (safe):
-- Same scenario, but one transaction gets:
-- ERROR: could not serialize access due to read/write dependencies
```

### Handling Serialization Failures

```python
import psycopg2
from psycopg2 import errors

def transfer_funds(from_id: int, to_id: int, amount: float) -> bool:
    max_retries = 3
    for attempt in range(max_retries):
        try:
            with connection.cursor() as cur:
                cur.execute("BEGIN ISOLATION LEVEL SERIALIZABLE")
                cur.execute(
                    "UPDATE accounts SET balance = balance - %s WHERE id = %s",
                    (amount, from_id)
                )
                cur.execute(
                    "UPDATE accounts SET balance = balance + %s WHERE id = %s",
                    (amount, to_id)
                )
                cur.execute("COMMIT")
                return True
        except errors.SerializationFailure:
            connection.rollback()
            if attempt == max_retries - 1:
                raise
        except Exception:
            connection.rollback()
            raise
```

### Choosing Isolation Level

| Use Case                | Level           | Why                                  |
| ----------------------- | --------------- | ------------------------------------ |
| Most OLTP operations    | Read Committed  | Good concurrency, handles most cases |
| Reports/analytics       | Repeatable Read | Consistent snapshot across queries   |
| Critical financial ops  | Serializable    | Prevents all anomalies               |
| Counters/idempotent ops | Read Committed  | Conflicts don't matter               |

### Performance Implications

```
Read Committed:
  - Minimal overhead, maximum concurrency
  - Each statement can see new committed data

Repeatable Read:
  - Holds snapshot for transaction duration
  - May fail on update conflicts → app retries needed
  - Long transactions hold back VACUUM

Serializable:
  - Tracks read/write dependencies (SSI)
  - More serialization failures → more retries
  - Some overhead for predicate locking
```

---

## 3. MVCC (Multi-Version Concurrency Control)

### How It Works

```
Traditional Locking:         MVCC:
  Reader blocks writer         Readers never block writers
  Writer blocks reader         Writers never block readers
  Poor concurrency             Multiple row versions coexist
                               Each transaction sees appropriate version
```

### Row Version Metadata

```sql
-- Each row has hidden system columns
SELECT xmin, xmax, ctid, * FROM accounts LIMIT 1;

-- xmin: Transaction ID that created this row version
-- xmax: Transaction ID that deleted/updated this version (0 if alive)
-- ctid: Physical location (page, item) of the row
```

### What Happens on UPDATE

```sql
-- Initial: (xmin=100, xmax=0, balance=1000)

BEGIN;  -- Transaction ID 105
UPDATE accounts SET balance = 500 WHERE id = 1;
-- Old row: (xmin=100, xmax=105, balance=1000)  ← marked deleted by 105
-- New row: (xmin=105, xmax=0,   balance=500)   ← new version by 105
COMMIT;

-- Both versions exist on disk!
-- Old version will be cleaned up by VACUUM later
```

### What Happens on DELETE

```sql
-- Row: (xmin=100, xmax=0, balance=1000)

BEGIN;  -- Transaction ID 110
DELETE FROM accounts WHERE id = 1;
-- Row: (xmin=100, xmax=110, balance=1000)  ← marked deleted
COMMIT;

-- Row still physically exists, just marked as deleted
-- VACUUM will reclaim the space
```

### Visibility Rules

```
A transaction can see a row version if:
  1. xmin is committed AND xmin started before our snapshot
  2. xmax is 0 (not deleted)
     OR xmax is not yet committed
     OR xmax started after our snapshot

Example:
  Row: xmin=100, xmax=105
  My snapshot: started after transaction 105 committed

  → xmin=100 committed before my snapshot: ✓
  → xmax=105 committed before my snapshot: row is DEAD for me ✗
```

### Dead Tuples and Bloat

```sql
-- Every UPDATE leaves behind a dead tuple (old version)
-- Dead tuples accumulate until VACUUM cleans them up

-- Check dead tuples
SELECT
    relname,
    n_live_tup,
    n_dead_tup,
    n_dead_tup * 100.0 / NULLIF(n_live_tup + n_dead_tup, 0) as dead_pct,
    last_vacuum,
    last_autovacuum
FROM pg_stat_user_tables
ORDER BY n_dead_tup DESC;

-- High dead_pct → table needs VACUUM
```

```
Without VACUUM:
┌─────────────────────────────────────┐
│ Live Row                            │
│ Dead Row (old version)              │
│ Dead Row                            │
│ Live Row                            │
│ Dead Row                            │
│ Live Row                            │
└─────────────────────────────────────┘

VACUUM:       marks dead space as reusable (NOT returned to OS)
VACUUM FULL:  rewrites table, returns space to OS (requires ACCESS EXCLUSIVE lock!)
pg_repack:    like VACUUM FULL but online (no exclusive lock)
```

### Long-Running Transactions Problem

```sql
-- Long-running transactions hold back VACUUM
-- Their snapshot might still need old row versions

-- Session 1: starts transaction, holds snapshot
BEGIN;
SELECT 1;
-- ... leaves running for hours ...

-- Session 2: does many updates
UPDATE accounts SET balance = balance + 1;  -- repeat many times

-- VACUUM can't clean up ANY dead tuples created after Session 1 started
-- because Session 1's snapshot might still need them

-- Find and kill old transactions
SELECT pid, state, xact_start, NOW() - xact_start as age, query
FROM pg_stat_activity
WHERE state != 'idle' AND xact_start < NOW() - INTERVAL '5 minutes'
ORDER BY xact_start;

SELECT pg_terminate_backend(pid);  -- kill it
```

### Transaction ID Wraparound

```sql
-- PostgreSQL uses 32-bit transaction IDs (~4 billion)
-- After ~2 billion, IDs wrap around
-- VACUUM freezes old tuples (sets xmin to "frozen") to prevent this

-- Check wraparound risk
SELECT
    datname,
    age(datfrozenxid) as xid_age,
    current_setting('autovacuum_freeze_max_age')::INT as freeze_max
FROM pg_database
WHERE datname NOT LIKE 'template%'
ORDER BY age(datfrozenxid) DESC;

-- If xid_age approaches freeze_max (200M default), emergency VACUUM needed
VACUUM FREEZE accounts;
```

---

## 4. Concurrency Control Strategies

### Pessimistic vs Optimistic Locking

```
Pessimistic Locking ("assume conflict will happen"):
┌──────────────────────────────────────────────────────────┐
│  1. Acquire lock on resource BEFORE reading/modifying    │
│  2. Hold lock for the duration of the operation          │
│  3. Other transactions WAIT (or fail) until lock freed   │
│  4. Release lock on COMMIT/ROLLBACK                      │
│                                                          │
│  Mechanism: SELECT ... FOR UPDATE, explicit LOCK TABLE   │
│  Best when: High contention, conflicts are frequent      │
│  Trade-off: Reduced concurrency, potential deadlocks     │
└──────────────────────────────────────────────────────────┘

Optimistic Locking ("assume conflict won't happen"):
┌──────────────────────────────────────────────────────────┐
│  1. Read resource WITHOUT acquiring any lock              │
│  2. Perform work in application memory                   │
│  3. At write time, CHECK if resource changed since read  │
│  4. If unchanged → commit. If changed → retry or abort   │
│                                                          │
│  Mechanism: Version column, timestamp, or CAS pattern    │
│  Best when: Low contention, conflicts are rare           │
│  Trade-off: Wasted work on conflict, retry logic needed  │
└──────────────────────────────────────────────────────────┘
```

### When to Use Which

```
Use Pessimistic When:                  Use Optimistic When:
─────────────────────                  ────────────────────
• High write contention                • Mostly reads, rare writes
• Conflict cost is high                • Conflicts are infrequent
• Short transactions                   • Long user think-time
• Database-centric logic               • Application-centric logic
• Financial transfers                  • User profile edits
• Inventory decrements                 • CMS content updates
• Seat/booking reservations            • Shopping cart modifications
```

### Comparison Table

```
                    Pessimistic (FOR UPDATE)      Optimistic (version column)
─────────────────   ────────────────────────      ──────────────────────────
Lock acquired       Before read                   Never (check at write)
Blocking            Yes — others wait             No — others proceed freely
Wasted work         Minimal                       Possible (redo on conflict)
Deadlock risk       Yes                           No
Retry logic         Not needed (waits)            Required (app handles it)
Network latency     Bad (lock held over network)  Fine (no lock held)
DB connection       Held during lock              Can be returned to pool
Best for            Short DB-only transactions    Long user-facing operations
```

---

## 5. PostgreSQL Lock Types

### Lock Hierarchy

```
┌────────────────────────────────────┐
│          Table-Level Locks          │   Coarse-grained
│  (acquired automatically by DML)   │   Controls access to entire table
├────────────────────────────────────┤
│          Row-Level Locks            │   Fine-grained
│  (acquired by UPDATE/DELETE/FOR..) │   Controls access to specific rows
├────────────────────────────────────┤
│          Page-Level Locks           │   Internal
│  (shared/exclusive, short-lived)   │   Used briefly during I/O
├────────────────────────────────────┤
│         Advisory Locks              │   Application-defined
│  (explicit, application-managed)   │   Not tied to any table or row
└────────────────────────────────────┘
```

### Table-Level Lock Modes

```
From weakest to strongest:

Mode                    Acquired By                         Conflicts With
─────────────────────   ───────────────────────────────────  ─────────────────────────────
ACCESS SHARE            SELECT                               ACCESS EXCLUSIVE
ROW SHARE               SELECT FOR UPDATE/SHARE              EXCLUSIVE, ACCESS EXCLUSIVE
ROW EXCLUSIVE           INSERT, UPDATE, DELETE                SHARE, SHARE ROW EXCLUSIVE,
                                                             EXCLUSIVE, ACCESS EXCLUSIVE
SHARE UPDATE EXCLUSIVE  VACUUM, CREATE INDEX CONCURRENTLY    SHARE UPDATE EXCLUSIVE, SHARE,
                                                             SHARE ROW EXCLUSIVE,
                                                             EXCLUSIVE, ACCESS EXCLUSIVE
SHARE                   CREATE INDEX (non-concurrent)        ROW EXCLUSIVE, SHARE UPDATE EXCL,
                                                             SHARE ROW EXCLUSIVE,
                                                             EXCLUSIVE, ACCESS EXCLUSIVE
SHARE ROW EXCLUSIVE     CREATE TRIGGER, ALTER TABLE (some)   ROW EXCLUSIVE, SHARE UPDATE EXCL,
                                                             SHARE, SHARE ROW EXCLUSIVE,
                                                             EXCLUSIVE, ACCESS EXCLUSIVE
EXCLUSIVE               REFRESH MAT VIEW CONCURRENTLY        ROW SHARE and everything stronger
ACCESS EXCLUSIVE        DROP TABLE, ALTER TABLE (most),       ALL lock modes (blocks everything
                        VACUUM FULL, TRUNCATE, REINDEX        including SELECT)
```

**Key insight:** A `SELECT` takes `ACCESS SHARE`, which only conflicts with `ACCESS EXCLUSIVE`. This is why `SELECT` never blocks other `SELECT`s and is only blocked by `DROP TABLE`, `VACUUM FULL`, `TRUNCATE`, etc.

### Table-Level Lock Conflict Matrix

```
                       Requested Lock Mode
                 AS   RS   RE   SUE   S   SRE   E   AE
Existing    AS   ✓    ✓    ✓    ✓     ✓    ✓    ✓    ✗
Lock        RS   ✓    ✓    ✓    ✓     ✓    ✓    ✗    ✗
Mode        RE   ✓    ✓    ✓    ✓     ✗    ✗    ✗    ✗
            SUE  ✓    ✓    ✓    ✗     ✗    ✗    ✗    ✗
            S    ✓    ✓    ✗    ✗     ✓    ✗    ✗    ✗
            SRE  ✓    ✓    ✗    ✗     ✗    ✗    ✗    ✗
            E    ✓    ✗    ✗    ✗     ✗    ✗    ✗    ✗
            AE   ✗    ✗    ✗    ✗     ✗    ✗    ✗    ✗

✓ = compatible    ✗ = conflict (must wait)
```

### Implicit Table-Level Locks

```sql
-- These are AUTOMATIC — PostgreSQL acquires them for you
-- Their purpose: prevent conflicting DDL while DML is running

SELECT * FROM accounts;                          -- ACCESS SHARE
INSERT INTO accounts (balance) VALUES (100);     -- ROW EXCLUSIVE
UPDATE accounts SET balance = 0 WHERE id = 1;   -- ROW EXCLUSIVE
DELETE FROM accounts WHERE id = 1;               -- ROW EXCLUSIVE
SELECT * FROM accounts WHERE id = 1 FOR UPDATE;  -- ROW SHARE
```

### Explicit Table-Level Locks

```sql
-- Rarely needed, but available for special cases
BEGIN;
LOCK TABLE accounts IN SHARE MODE;  -- blocks writes, allows reads
-- ... do work ...
COMMIT;

LOCK TABLE accounts IN ACCESS EXCLUSIVE MODE;  -- blocks everything
```

---

## 6. Row-Level Locks

### The Four Row Lock Modes

```
From weakest to strongest:

Mode                  Purpose                              Blocks
────────────────────  ───────────────────────────────────── ─────────────────────────
FOR KEY SHARE         Weakest. Protects against key        FOR UPDATE
                      changes. Acquired by FK checks.

FOR SHARE             Blocks modifications but allows      FOR UPDATE,
                      concurrent FOR SHARE locks.          FOR NO KEY UPDATE

FOR NO KEY UPDATE     Blocks modifications but allows      FOR UPDATE,
                      concurrent FOR KEY SHARE locks.      FOR NO KEY UPDATE,
                      Acquired by UPDATE of non-key cols.  FOR SHARE

FOR UPDATE            Strongest. Full exclusive access      All row lock modes
                      to the row. Blocks everything.
```

### Row Lock Conflict Matrix

```
                      Requested
                 FKS    FS    FNKU    FU
Held    FKS       ✓      ✓      ✓     ✗
        FS        ✓      ✓      ✗     ✗
        FNKU      ✓      ✗      ✗     ✗
        FU        ✗      ✗      ✗     ✗
```

### SELECT FOR UPDATE (Pessimistic Locking)

```sql
BEGIN;
SELECT * FROM accounts WHERE id = 1 FOR UPDATE;
-- Row is now locked — no other transaction can UPDATE or DELETE it
-- Other transactions CAN still SELECT it (MVCC — no read locks)
UPDATE accounts SET balance = balance - 100 WHERE id = 1;
COMMIT;  -- lock released

-- Multiple rows
SELECT * FROM accounts WHERE id IN (1, 2, 3) FOR UPDATE;

-- Lock specific table in a join
SELECT a.*, u.name
FROM accounts a
JOIN users u ON a.user_id = u.id
WHERE a.id = 1
FOR UPDATE OF a;  -- only locks rows in 'accounts'
```

### SELECT FOR SHARE

```sql
-- Allow concurrent reads but block writes
-- Multiple transactions CAN hold FOR SHARE on the same row

BEGIN;
SELECT * FROM orders WHERE id = 100 FOR SHARE;
-- Prevents the order from being modified/deleted
-- while we read related data
SELECT * FROM order_items WHERE order_id = 100;
COMMIT;
```

### FOR NO KEY UPDATE vs FOR UPDATE

```sql
-- A regular UPDATE of non-key columns acquires FOR NO KEY UPDATE
-- This allows concurrent FOR KEY SHARE locks (FK checks) to proceed

-- Session 1:
BEGIN;
UPDATE accounts SET balance = 500 WHERE id = 1;
-- Acquires FOR NO KEY UPDATE (balance is not a key column)

-- Session 2 (concurrent):
INSERT INTO transfers (from_account_id, amount) VALUES (1, 50);
-- FK check needs FOR KEY SHARE on accounts.id
-- FOR KEY SHARE is compatible with FOR NO KEY UPDATE → succeeds!

-- But if Session 1 updated the PK:
-- UPDATE accounts SET id = 99 WHERE id = 1;
-- That acquires FOR UPDATE → Session 2's FK check would BLOCK
```

### NOWAIT: Fail Fast

```sql
-- Default: wait (potentially forever) for lock
SELECT * FROM accounts WHERE id = 1 FOR UPDATE;

-- NOWAIT: error immediately if lock not available
SELECT * FROM accounts WHERE id = 1 FOR UPDATE NOWAIT;
-- ERROR: could not obtain lock on row in relation "accounts"
```

### SKIP LOCKED: Process Only Available Rows

```sql
-- Skip rows locked by other transactions
-- Perfect for job queues with multiple workers

SELECT * FROM job_queue
WHERE status = 'pending'
ORDER BY created_at
LIMIT 1
FOR UPDATE SKIP LOCKED;

-- Worker 1 gets job A, Worker 2 gets job B (skips A since it's locked)
-- No blocking, no deadlocks, natural work distribution
```

**Job queue pattern:**

```sql
CREATE TABLE jobs (
    id SERIAL PRIMARY KEY,
    payload JSONB NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    worker_id INTEGER,
    claimed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Worker claims next available job (atomic, no race conditions)
UPDATE jobs SET
    status = 'processing',
    worker_id = pg_backend_pid(),
    claimed_at = NOW()
WHERE id = (
    SELECT id FROM jobs
    WHERE status = 'pending'
    ORDER BY created_at
    LIMIT 1
    FOR UPDATE SKIP LOCKED
)
RETURNING *;
```

---

## 7. Deadlocks

### How Deadlocks Occur

```
Transaction A                    Transaction B
─────────────                    ─────────────
BEGIN;                           BEGIN;
UPDATE accounts SET ...          UPDATE accounts SET ...
  WHERE id = 1;                    WHERE id = 2;
-- Holds lock on id=1            -- Holds lock on id=2

UPDATE accounts SET ...          UPDATE accounts SET ...
  WHERE id = 2;                    WHERE id = 1;
-- WAITS for B's lock            -- WAITS for A's lock

         ┌──── A waits for B ────┐
         │                       │
         └──── B waits for A ────┘
                DEADLOCK!
```

### PostgreSQL Deadlock Detection

```sql
SHOW deadlock_timeout;  -- Default: 1s

-- PostgreSQL checks for deadlock cycles every deadlock_timeout
-- When detected: picks one transaction as victim, aborts it
-- Victim gets: ERROR: deadlock detected
-- Other transaction proceeds
```

### Preventing Deadlocks

**Strategy 1: Consistent Lock Ordering**

```sql
-- ALWAYS lock resources in the same order (e.g., ascending PK)
BEGIN;
SELECT * FROM accounts WHERE id IN (1, 2) ORDER BY id FOR UPDATE;
-- Both transactions lock id=1 first, then id=2 → no cycle possible
UPDATE accounts SET balance = balance - 100 WHERE id = 1;
UPDATE accounts SET balance = balance + 100 WHERE id = 2;
COMMIT;
```

**Strategy 2: Lock Timeout**

```sql
SET lock_timeout = '5s';
-- Query fails after 5 seconds if lock not acquired

-- Per-transaction
BEGIN;
SET LOCAL lock_timeout = '3s';
COMMIT;
```

**Strategy 3: Reduce Lock Duration**

```sql
-- BAD: hold lock while doing slow work
BEGIN;
SELECT * FROM accounts WHERE id = 1 FOR UPDATE;  -- Lock acquired
-- ... 5 seconds of application processing ...    -- Lock held!
UPDATE accounts SET balance = 500 WHERE id = 1;
COMMIT;

-- GOOD: do slow work first, then lock briefly
-- ... 5 seconds of application processing ...
BEGIN;
SELECT * FROM accounts WHERE id = 1 FOR UPDATE;
UPDATE accounts SET balance = 500 WHERE id = 1;
COMMIT;  -- Lock held ~milliseconds
```

**Strategy 4: Use NOWAIT or SKIP LOCKED**

```sql
-- NOWAIT: fail immediately, retry with backoff → no deadlock
SELECT * FROM accounts WHERE id = 1 FOR UPDATE NOWAIT;

-- SKIP LOCKED: skip contended rows → no deadlock
SELECT * FROM tasks WHERE status = 'pending' FOR UPDATE SKIP LOCKED LIMIT 10;
```

---

## 8. Optimistic Locking (Application-Level)

### Version Column Pattern

```sql
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    stock INTEGER NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
);

-- Step 1: Read (no lock acquired)
SELECT id, name, price, stock, version FROM products WHERE id = 42;
-- Returns: id=42, price=29.99, stock=10, version=5

-- Step 2: Update with version check (Compare-And-Swap)
UPDATE products
SET price = 34.99, version = version + 1
WHERE id = 42 AND version = 5;
-- 1 row affected → success, no conflict
-- 0 rows affected → someone else modified it, RETRY
```

### Application-Level Retry Pattern

```python
def update_product_price(product_id: int, new_price: float, max_retries: int = 3) -> bool:
    for attempt in range(max_retries):
        with conn.cursor() as cur:
            cur.execute(
                "SELECT price, version FROM products WHERE id = %s",
                (product_id,)
            )
            row = cur.fetchone()
            if not row:
                raise ValueError("Product not found")

            current_price, version = row

            cur.execute(
                """UPDATE products
                   SET price = %s, version = version + 1
                   WHERE id = %s AND version = %s""",
                (new_price, product_id, version)
            )
            conn.commit()

            if cur.rowcount == 1:
                return True
            # rowcount == 0 → conflict, retry

    raise Exception("Too many conflicts")
```

### Timestamp-Based Optimistic Locking

```sql
-- Alternative: use updated_at instead of version
UPDATE articles
SET title = 'New Title', updated_at = NOW()
WHERE id = 1 AND updated_at = '2026-04-20 10:00:00';
-- 0 rows → conflict, 1 row → success
```

---

## 9. Advisory Locks

### What Are Advisory Locks

```
Application-defined locks managed by PostgreSQL's lock manager.
NOT tied to any table, row, or schema object.
You assign meaning to them — PostgreSQL just handles the locking semantics.

Key properties:
• Identified by one 64-bit integer or two 32-bit integers
• Session-level (explicit release) or transaction-level (auto-release)
• Visible in pg_locks
• No automatic acquisition — your application must request them
```

### Session-Level Advisory Locks

```sql
-- Acquire (blocks if already held by another session)
SELECT pg_advisory_lock(12345);

-- Try to acquire (non-blocking)
SELECT pg_try_advisory_lock(12345);  -- returns true/false

-- Release
SELECT pg_advisory_unlock(12345);

-- WARNING: session-level locks are reentrant!
-- Call lock 3 times → must unlock 3 times

-- Release all
SELECT pg_advisory_unlock_all();
```

### Transaction-Level Advisory Locks

```sql
-- Automatically released at COMMIT or ROLLBACK — safer
BEGIN;
SELECT pg_advisory_xact_lock(12345);
-- ... do work ...
COMMIT;  -- lock released automatically

-- Non-blocking version
SELECT pg_try_advisory_xact_lock(12345);
```

### Shared vs Exclusive

```sql
-- Exclusive: only one session
SELECT pg_advisory_lock(12345);

-- Shared: multiple sessions can hold concurrently
SELECT pg_advisory_lock_shared(12345);

-- Shared blocks exclusive, exclusive blocks both
```

### Two-Key Pattern

```sql
-- (type, id) pattern
SELECT pg_advisory_lock(hashtext('order'), order_id);
SELECT pg_advisory_lock(hashtext('user'), user_id);
```

### Use Cases

**Singleton job execution:**

```sql
CREATE OR REPLACE FUNCTION run_daily_report()
RETURNS TEXT AS $$
BEGIN
    IF NOT pg_try_advisory_lock(hashtext('daily_report')) THEN
        RETURN 'Already running';
    END IF;
    PERFORM pg_sleep(60);  -- simulate work
    PERFORM pg_advisory_unlock(hashtext('daily_report'));
    RETURN 'Complete';
END;
$$ LANGUAGE plpgsql;
```

**Leader election:**

```sql
-- In application startup — only one instance becomes leader
SELECT pg_try_advisory_lock(hashtext('leader_election'));
-- true → this instance is the leader
-- false → another instance is leader
-- If leader crashes, connection closes, lock released
```

---

## 10. Lock Monitoring and Debugging

### View Current Locks

```sql
SELECT
    l.locktype,
    l.relation::regclass AS table_name,
    l.mode,
    l.granted,
    l.pid,
    a.query,
    a.state
FROM pg_locks l
JOIN pg_stat_activity a ON l.pid = a.pid
WHERE l.relation IS NOT NULL
ORDER BY l.relation, l.mode;
```

### Find Blocked Queries

```sql
SELECT
    blocked.pid AS blocked_pid,
    blocked.query AS blocked_query,
    NOW() - blocked.query_start AS waiting_duration,
    blocking.pid AS blocking_pid,
    blocking.query AS blocking_query,
    blocking.state AS blocking_state
FROM pg_stat_activity blocked
JOIN pg_stat_activity blocking
    ON blocking.pid = ANY(pg_blocking_pids(blocked.pid))
WHERE cardinality(pg_blocking_pids(blocked.pid)) > 0;
```

### Detect Lock Wait Chains

```sql
WITH RECURSIVE lock_chain AS (
    SELECT
        blocked.pid AS blocked_pid,
        blocking.pid AS blocking_pid,
        blocked.query AS blocked_query,
        1 AS depth
    FROM pg_stat_activity blocked
    JOIN pg_stat_activity blocking
        ON blocking.pid = ANY(pg_blocking_pids(blocked.pid))
    WHERE cardinality(pg_blocking_pids(blocked.pid)) > 0

    UNION ALL

    SELECT lc.blocked_pid, blocking.pid, lc.blocked_query, lc.depth + 1
    FROM lock_chain lc
    JOIN pg_stat_activity blocking
        ON blocking.pid = ANY(pg_blocking_pids(lc.blocking_pid))
    WHERE lc.depth < 10
)
SELECT DISTINCT blocked_pid, blocking_pid, blocked_query, depth
FROM lock_chain ORDER BY depth;
```

### Terminate Blocking Connections

```sql
SELECT pg_cancel_backend(12345);     -- cancel query (graceful)
SELECT pg_terminate_backend(12345);  -- kill connection (forceful)
```

### Configuration

```sql
SET lock_timeout = '10s';        -- max wait for any lock
SET statement_timeout = '30s';   -- max total statement time
SHOW deadlock_timeout;           -- how often to check for deadlocks (default 1s)

-- In postgresql.conf:
-- log_lock_waits = on           -- log when waiting longer than deadlock_timeout
-- idle_in_transaction_session_timeout = '5min'  -- kill idle-in-transaction sessions
```

### Find Idle-in-Transaction Connections

```sql
SELECT
    pid, state,
    NOW() - xact_start AS transaction_age,
    query AS last_query,
    count(l.*) AS lock_count
FROM pg_stat_activity a
JOIN pg_locks l ON a.pid = l.pid
WHERE a.state = 'idle in transaction'
  AND a.xact_start < NOW() - INTERVAL '1 minute'
GROUP BY a.pid, a.state, a.xact_start, a.query
ORDER BY transaction_age DESC;
```

---

## 11. Common Patterns and Pitfalls

### Pattern: Safe Balance Transfer

```sql
CREATE OR REPLACE FUNCTION transfer(
    from_id INTEGER, to_id INTEGER, amount DECIMAL
) RETURNS VOID AS $$
DECLARE
    lock_first INTEGER := LEAST(from_id, to_id);
    lock_second INTEGER := GREATEST(from_id, to_id);
BEGIN
    PERFORM * FROM accounts WHERE id = lock_first FOR UPDATE;
    PERFORM * FROM accounts WHERE id = lock_second FOR UPDATE;
    UPDATE accounts SET balance = balance - amount WHERE id = from_id;
    UPDATE accounts SET balance = balance + amount WHERE id = to_id;
END;
$$ LANGUAGE plpgsql;
```

### Pattern: Upsert Without Race Conditions

```sql
INSERT INTO counters (key, value) VALUES ('page_views', 1)
ON CONFLICT (key) DO UPDATE SET value = counters.value + 1;
-- Atomic, no explicit lock needed
```

### Pitfall: Lock Escalation Does NOT Happen

```
Unlike SQL Server, PostgreSQL NEVER escalates row locks to table locks.
Locking 1 million rows = 1 million row locks, never a table lock.
Good for concurrency, but high row-lock counts consume more memory.
```

### Pitfall: Foreign Keys Acquire Locks

```sql
-- INSERT into child table acquires FOR KEY SHARE on parent row
INSERT INTO order_items (order_id, product) VALUES (1, 'Widget');
-- Acquires FOR KEY SHARE on orders WHERE id = 1
-- Prevents the order from being DELETED
-- But allows non-key UPDATEs (e.g., changing order total)
-- Can cause unexpected blocking if another transaction holds FOR UPDATE
```

### Pitfall: Long Transactions Hold Locks

```sql
-- Common production issue: idle-in-transaction sessions holding locks
-- Prevention:
SET idle_in_transaction_session_timeout = '5min';
```

---

## 12. Hands-On Exercises

### Exercise 1: Non-Repeatable Read vs Repeatable Read

```sql
-- Terminal 1 (Read Committed):
BEGIN;
SELECT balance FROM accounts WHERE id = 1;  -- note value

-- Terminal 2:
UPDATE accounts SET balance = balance + 100 WHERE id = 1;

-- Terminal 1:
SELECT balance FROM accounts WHERE id = 1;  -- value changed!
COMMIT;

-- Now repeat with REPEATABLE READ:
-- Terminal 1:
BEGIN ISOLATION LEVEL REPEATABLE READ;
SELECT balance FROM accounts WHERE id = 1;  -- note value

-- Terminal 2:
UPDATE accounts SET balance = balance + 100 WHERE id = 1;

-- Terminal 1:
SELECT balance FROM accounts WHERE id = 1;  -- same value!
COMMIT;
```

### Exercise 2: Pessimistic vs Optimistic Locking

```sql
CREATE TABLE inventory (
    id SERIAL PRIMARY KEY,
    product VARCHAR(100),
    quantity INTEGER NOT NULL CHECK (quantity >= 0),
    version INTEGER NOT NULL DEFAULT 1
);
INSERT INTO inventory (product, quantity) VALUES ('Widget', 10);

-- PESSIMISTIC (two terminals):
-- T1: BEGIN; SELECT * FROM inventory WHERE id = 1 FOR UPDATE;
--     UPDATE inventory SET quantity = quantity - 3 WHERE id = 1; COMMIT;
-- T2: BEGIN; SELECT * FROM inventory WHERE id = 1 FOR UPDATE;
--     (blocks until T1 commits, then sees quantity = 7)
--     UPDATE inventory SET quantity = quantity - 2 WHERE id = 1; COMMIT;
-- Result: 5. Correct. No retries.

-- OPTIMISTIC (two terminals, reset to quantity=10, version=1):
-- T1: reads version=1, UPDATE ... SET quantity=7, version=2 WHERE version=1 → success
-- T2: reads version=1, UPDATE ... SET quantity=8, version=2 WHERE version=1 → 0 rows! Retry.
```

### Exercise 3: Deadlock and Prevention

```sql
CREATE TABLE bank (id INT PRIMARY KEY, balance INT);
INSERT INTO bank VALUES (1, 1000), (2, 1000);

-- CAUSE deadlock (two terminals):
-- T1: BEGIN; UPDATE bank SET balance=900 WHERE id=1;
-- T2: BEGIN; UPDATE bank SET balance=900 WHERE id=2;
-- T1: UPDATE bank SET balance=1100 WHERE id=2;  -- waits
-- T2: UPDATE bank SET balance=1100 WHERE id=1;  -- DEADLOCK!

-- FIX with consistent ordering:
-- T1: BEGIN; SELECT * FROM bank WHERE id IN (1,2) ORDER BY id FOR UPDATE;
-- T2: BEGIN; SELECT * FROM bank WHERE id IN (1,2) ORDER BY id FOR UPDATE;
-- T2 waits for T1 — no deadlock
```

### Exercise 4: Job Queue with SKIP LOCKED

```sql
CREATE TABLE task_queue (
    id SERIAL PRIMARY KEY,
    payload TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    claimed_by INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
INSERT INTO task_queue (payload) SELECT 'task_' || i FROM generate_series(1, 20) i;

-- Run in 3 terminals simultaneously:
BEGIN;
UPDATE task_queue SET status = 'processing', claimed_by = pg_backend_pid()
WHERE id = (
    SELECT id FROM task_queue
    WHERE status = 'pending'
    ORDER BY created_at LIMIT 1
    FOR UPDATE SKIP LOCKED
) RETURNING id, payload, claimed_by;
-- Each terminal gets a DIFFERENT task
COMMIT;
```

### Exercise 5: Advisory Lock Singleton

```sql
-- Terminal 1:
SELECT pg_try_advisory_lock(hashtext('heavy_job'));  -- true

-- Terminal 2:
SELECT pg_try_advisory_lock(hashtext('heavy_job'));  -- false

-- Terminal 1:
SELECT pg_advisory_unlock(hashtext('heavy_job'));

-- Terminal 2:
SELECT pg_try_advisory_lock(hashtext('heavy_job'));  -- true now
SELECT pg_advisory_unlock(hashtext('heavy_job'));
```

### Exercise 6: MVCC Row Versions

```sql
CREATE TABLE mvcc_demo (id INT PRIMARY KEY, data TEXT);
INSERT INTO mvcc_demo VALUES (1, 'v1');

SELECT xmin, xmax, ctid, * FROM mvcc_demo;  -- note xmin, xmax=0

UPDATE mvcc_demo SET data = 'v2' WHERE id = 1;
SELECT xmin, xmax, ctid, * FROM mvcc_demo;  -- xmin changed, ctid may change

SELECT n_live_tup, n_dead_tup FROM pg_stat_user_tables WHERE relname = 'mvcc_demo';
-- 1 live, 1 dead

VACUUM mvcc_demo;
SELECT n_live_tup, n_dead_tup FROM pg_stat_user_tables WHERE relname = 'mvcc_demo';
-- 1 live, 0 dead
```

---

## 13. Interview Questions

### "Explain the ACID properties and how PostgreSQL implements them."

> ACID: Atomicity (all or nothing via WAL), Consistency (constraints/triggers enforce valid states), Isolation (MVCC provides snapshots — readers don't block writers), Durability (WAL synced to disk before COMMIT returns — crash recovery replays committed transactions from WAL).

### "Explain the difference between Read Committed and Repeatable Read."

> Read Committed: each statement sees data committed before that statement started. Two SELECTs in the same transaction can see different data. Repeatable Read: snapshot at first statement, consistent reads throughout. Trade-off: if you try to update a row modified by another committed transaction, you get a serialization error and must retry.

### "When would you use SERIALIZABLE isolation?"

> When correctness requires transactions to behave as if run serially — like enforcing "at least one doctor on call." In lower levels, concurrent transactions can each see the constraint satisfied and violate it together (write skew). Trade-off: more serialization failures requiring retry logic and some performance overhead.

### "How does PostgreSQL MVCC work?"

> MVCC maintains multiple versions of each row. Each row has xmin (creating transaction) and xmax (deleting transaction). UPDATE marks the old row deleted and creates a new version. Each transaction sees rows based on its snapshot — visible if xmin committed before snapshot and xmax is 0 or uncommitted or after snapshot. Readers never block writers. Dead tuples accumulate until VACUUM cleans them up.

### "What is pessimistic vs optimistic locking?"

> Pessimistic: lock before read (SELECT FOR UPDATE), assumes conflicts are likely. Use for short, high-contention operations like balance transfers. Optimistic: no lock during read, check at write time via version column — if changed, retry. Use for low-contention scenarios or when transactions span user think-time.

### "How does PostgreSQL handle deadlocks?"

> Detects cycles in the wait graph every deadlock_timeout (1s default). Picks one transaction to abort. Prevent by: consistent lock ordering (always by ascending PK), lock_timeout, short transactions, SKIP LOCKED for queues.

### "What are advisory locks and when would you use them?"

> Application-defined locks not tied to any table — just a number. Use for: singleton job execution across app instances, leader election, rate limiting expensive operations. Session-level (explicit release) or transaction-level (auto-release on commit). The advantage over external tools is they share the same failure domain as your data.

### "How would you debug lock contention in production?"

> Enable `log_lock_waits`. Query `pg_stat_activity` joined with `pg_locks` to see who holds what. Use `pg_blocking_pids()` to find who blocks whom. Look for idle-in-transaction sessions (biggest offender). Set `idle_in_transaction_session_timeout`. Review app code for transactions holding locks across network calls.

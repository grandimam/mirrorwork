# System Design: Revolut-Optimized Guide

> A learning progression that builds intuition from a single machine to a fully distributed fintech system. Each phase introduces one new source of complexity and teaches you to reason about it.

## Table of Contents

1. [Phase 1: Single Machine, Single Process](#phase-1-single-machine-single-process)
   - 1.1 How a Request is Processed
   - 1.2 How a Relational Database Works
   - 1.3 ACID Transactions
   - 1.4 Isolation Levels
   - 1.5 Indexing
   - 1.6 Back-of-the-Envelope Estimation
2. [Phase 2: Single Service, Multiple Machines](#phase-2-single-service-multiple-machines)
   - 2.1 Why Replicate?
   - 2.2 Replication: Leader-Follower
   - 2.3 Replication Lag
   - 2.4 Failover
   - 2.5 CAP Theorem
   - 2.6 Consistency Models
3. [Phase 3: Data Doesn't Fit on One Machine](#phase-3-data-doesnt-fit-on-one-machine)
   - 3.1 Partitioning / Sharding
   - 3.2 Consistent Hashing
   - 3.3 What You Lose When You Shard
   - 3.4 Database Scaling Progression
4. [Phase 4: The Split](#phase-4-the-split)
   - 4.1 Where to Draw Service Boundaries _(microservices)_
   - 4.2 Data Ownership _(both)_
   - 4.3 Synchronous Communication — REST & gRPC _(microservices)_
   - 4.4 The Unknown State _(distributed systems)_
   - 4.5 Idempotency _(distributed systems)_
   - 4.6 Timeouts and Retries _(distributed systems)_
   - 4.7 Service Discovery _(microservices)_
   - 4.8 API Design _(microservices)_
5. [Phase 5: Independence](#phase-5-independence)
   - 5.1 Independent Deployability _(microservices)_
   - 5.2 Contract Testing _(microservices)_
   - 5.3 Deployment Strategies _(microservices)_
   - 5.4 Database Per Service _(both)_
   - 5.5 Asynchronous Communication _(both)_
   - 5.6 Sync vs Async Payment Flows _(both)_
   - 5.7 Avoiding the Distributed Monolith _(microservices)_
6. [Phase 6: Coordination](#phase-6-coordination)
   - 6.1 The Problem: No Cross-Service Transactions
   - 6.2 Two-Phase Commit (2PC) _(distributed systems)_
   - 6.3 Saga Pattern _(both)_
   - 6.4 Event-Driven Architecture _(both)_
   - 6.5 Ordering Guarantees _(distributed systems)_
   - 6.6 Exactly-Once Delivery _(distributed systems)_
   - 6.7 CQRS _(microservices + distributed systems)_
7. [Phase 7: Resilience](#phase-7-resilience)
   - 7.1 Failure Modes _(distributed systems)_
   - 7.2 Circuit Breaker _(both)_
   - 7.3 Bulkhead _(both)_
   - 7.4 Graceful Degradation _(both)_
   - 7.5 Health Checks _(microservices)_
   - 7.6 Dead-Letter Queues _(both)_
   - 7.7 Payment Provider Redundancy _(microservices)_
   - 7.8 Service Mesh _(microservices)_
8. [Phase 8: Consensus & Coordination](#phase-8-consensus--coordination)
   - 8.1 The Consensus Problem _(distributed systems)_
   - 8.2 Raft _(distributed systems)_
   - 8.3 Distributed Locking _(distributed systems)_
   - 8.4 Clocks & Ordering _(distributed systems)_
   - 8.5 Distributed Configuration _(microservices)_
   - 8.6 Conflict Resolution _(distributed systems)_
9. [Phase 9: The Money Path](#phase-9-the-money-path)
   - 9.1 Double-Entry Ledger
   - 9.2 Idempotency in Payments (End-to-End)
   - 9.3 Saga for Payment Flows
   - 9.4 Event Sourcing
   - 9.5 Reconciliation
   - 9.6 SQL vs NoSQL — Where Each Fits
10. [Phase 10: Observability & Security](#phase-10-observability--security)
    - 10.1 Three Pillars of Observability
    - 10.2 Key Metrics
    - 10.3 Distributed Tracing
    - 10.4 SLIs, SLOs, SLAs
    - 10.5 Alerting
    - 10.6 Authentication & Authorization
    - 10.7 Data Security & Compliance
11. [Phase 11: Practice](#phase-11-practice)
    - 11.1 Classic Problems (Revolut-Weighted)
    - 11.2 The 35-Minute Framework
    - 11.3 Clarifying Questions Checklist
    - 11.4 How to Talk About Your Design
    - 11.5 Common Mistakes
    - 11.6 Problem Deep-Dive Template

## Phase 1: Single Machine, Single Process

**Everything works. Learn why — because you're about to start losing these guarantees.**

### 1.1 How a Request is Processed

```
Client → TCP connection → Socket → Thread/Process → Handler → Database → Response

Within a single process:
  - Function calls are instant and reliable
  - Shared memory means shared state
  - One clock, one timeline, one order of events
  - Failure is total — process is up or down, no partial state
```

This is your baseline. Everything you learn after this is about what breaks when you leave this world.

### 1.2 How a Relational Database Works

**Where does data actually live?**

Your data exists in three places simultaneously, each serving a different purpose:

```
                    ┌─────────────────────────┐
                    │     RAM (Buffer Cache)   │
                    │                          │
                    │  Page 47: Alice = $500   │  ← dirty (updated here, not yet in table file)
                    │  Page 312: Bob = $300    │  ← clean (matches table file)
                    │  Page 8: Carol = $700    │  ← clean
                    │                          │
                    └───────────┬──────────────┘
                                │
                   checkpoint flushes dirty pages ↓
                                │
  ┌─────────────────────────────┼──────────────────────────────┐
  │                        Disk                                │
  │                                                            │
  │  WAL file (sequential, append-only)                        │
  │  [entry1][entry2]["Alice → $500"][entry4]...               │
  │                                                            │
  │  Table file: accounts (rows at fixed page locations)       │
  │  Page 47: Alice = $600   ← stale! checkpoint hasn't run   │
  │  Page 312: Bob = $300    ← matches memory                 │
  │  Page 8: Carol = $700    ← matches memory                 │
  │                                                            │
  └────────────────────────────────────────────────────────────┘
```

| Location           | What it is                      | Speed                          | Survives crash? |
| ------------------ | ------------------------------- | ------------------------------ | --------------- |
| WAL (disk)         | Change log: "set Alice to $500" | Fast write (sequential append) | Yes             |
| Buffer cache (RAM) | Live working copy of data pages | Fastest read/write             | No              |
| Table file (disk)  | Permanent home of actual rows   | Slow write (random I/O)        | Yes             |

**Table file** = where your rows live permanently. When you `CREATE TABLE accounts`, PostgreSQL creates a file on disk. This file holds your rows organized in 8KB pages. Page 47 has Alice's row, page 312 has Bob's. This is the permanent home of your data.

**Buffer cache** = a chunk of RAM where PostgreSQL keeps copies of recently accessed pages. When you query Alice's row, PostgreSQL loads page 47 into memory once. Subsequent reads hit memory (nanoseconds) instead of disk (microseconds). Most queries never touch the table file directly — they read from buffer cache. After a restart, the buffer cache is empty and pages are loaded from the table file on demand.

**WAL** = a sequential, append-only log file on disk. Every change is written here first (before memory or table file). It's the crash safety net — if the machine dies, PostgreSQL replays the WAL on restart to recover any changes that were in memory but not yet flushed to the table file.

**Storage engine (simplified):**

```
Write path:
  1. Write to WAL (Write-Ahead Log) on disk — sequential append, fast, durable
  2. Update in-memory buffer (page cache) — fast, but volatile
  3. Periodically flush dirty pages to their actual table location on disk (checkpoint)

  The order matters: WAL first, then memory, then table on disk.
  This is called "write-ahead" because the log is written AHEAD of the actual data.

  Crash recovery: replay WAL from last checkpoint → re-apply changes to table files

Read path:
  1. Check buffer cache (in-memory) — if the page is there, return it (fast)
  2. If miss → load page from table file on disk into buffer cache
  3. Use index (B-tree) to know which page to load
```

**Write path explained — why WAL is written first:**

The name "Write-Ahead Log" tells you everything: the log is written **ahead** of (before) the actual data. This is the single most important ordering guarantee in the database.

```
Timeline of a single UPDATE statement:

  1. Transaction begins
  2. Database writes WAL entry to disk: "change Alice balance from 600 to 500"
     → fsync to disk — this is now durable, survives any crash
  3. Database updates the page in memory (buffer cache): Alice balance = 500
     → memory is fast but volatile — lost on crash
  4. Database returns "COMMIT OK" to client
     → the client's transaction is confirmed

  At this point:
    WAL on disk:    "Alice balance → 500"  ← persisted (step 2)
    Buffer cache:   Alice balance = 500     ← updated (step 3)
    Table on disk:  Alice balance = 600     ← STALE (not yet flushed!)

  This is fine. If the machine crashes now:
    → On restart, database reads WAL
    → Finds entry: "change Alice balance to 500"
    → Applies it to the table file on disk
    → Alice balance = 500 on disk. No data lost.

  Much later (minutes), checkpoint runs:
    → Flushes dirty pages from buffer cache to table files on disk
    → Table on disk now says Alice balance = 500
    → WAL entries before this checkpoint can be recycled (no longer needed for recovery)
```

**Why not write directly to the table file on disk?**

The table file stores rows at specific locations — Alice's row might be at page 47, Bob's at page 312. Updating them means seeking to random disk locations (random I/O). Random I/O is slow:

| Operation      | HDD               | SSD                |
| -------------- | ----------------- | ------------------ |
| Random I/O     | ~10ms per seek    | ~150μs per read    |
| Sequential I/O | ~30MB/s sustained | ~500MB/s sustained |

The WAL is an append-only file — every write goes to the end, in order (sequential I/O). A WAL append takes microseconds. Writing to a random row location takes 100-1000x longer on HDD, 5-10x on SSD.

**The core trick: sequential write for safety (WAL), deferred random write for performance (checkpoint).** The client only waits for the sequential WAL append. The expensive random write to the actual table location happens later, in the background, batched together.

**What is a dirty page?**

A page in the buffer cache that has been updated in memory (step 3) but not yet flushed to the table file on disk (step 5). "Dirty" means memory and the table file disagree. This is always safe because the WAL (on disk) has the change recorded — if the machine crashes, the WAL replays the change.

```
Clean page:  memory says $500, table on disk says $500  ← in sync
Dirty page:  memory says $500, table on disk says $600  ← memory is ahead
             WAL on disk says "change to $500"          ← safety net
```

**B-Tree Index:**

```
                    [50]
                   /    \
              [20,30]   [70,80]
              / | \      / | \
           [10][25][35][60][75][90]  ← leaf nodes contain row pointers

  - Balanced: O(log n) lookups, range scans follow leaf pointers
  - Maintained on every write (split/merge nodes)
  - Default index type in PostgreSQL, MySQL, etc.
```

**How a B-tree lookup works:**

Think of it like a library catalogue. You don't scan every book — you narrow down by section, then shelf, then slot.

```
Query: SELECT * FROM transactions WHERE id = 25

Step 1: Start at root [50] → 25 < 50, go left
Step 2: Reach [20, 30] → 20 < 25 < 30, go to middle child
Step 3: Reach leaf [25] → found! Follow pointer to actual row on disk

3 steps to find a row in millions. That's O(log n).
```

**Range queries are efficient** because leaf nodes are linked in order:

```
Query: SELECT * FROM transactions WHERE id BETWEEN 25 AND 75

Find 25 (same walk as above), then follow leaf pointers forward:
  [25] → [35] → [60] → [75] → stop

No need to re-traverse the tree for each value.
```

**Write cost:** When you insert a value, the B-tree may need to split a node that's full. If [20, 25, 30, 35] is full and you insert 28, the node splits into two. This split can cascade upward. That's why indexes make writes slower — every insert/update/delete must update both the table AND every index on that table.

**Why "balanced" matters:** Every leaf is at the same depth. A B-tree with 1 million rows has ~3-4 levels. A B-tree with 1 billion rows has ~5-6 levels. The depth grows logarithmically, so lookup time barely increases with data size.

**WAL guarantees durability:** Even if the machine crashes after a write is acknowledged, the WAL ensures it survives. This is the "D" in ACID.

### 1.3 ACID Transactions

**What is a transaction?**

A transaction is a group of operations that the database treats as a single unit. Either all of them happen, or none of them happen. You can't see a halfway state.

```
BEGIN;
  debit Alice's account by $100
  credit Bob's account by $100
COMMIT;

These two operations are one transaction.
There is no moment where Alice lost $100 but Bob hasn't received it yet (from any observer's perspective).
```

Without transactions, you'd need to handle every partial failure in application code — "what if the debit succeeded but the credit failed?" With transactions, the database handles it: if anything fails, everything rolls back.

**What is ACID?**

ACID is the set of guarantees a transaction provides. Think of it as a contract: if your database is ACID-compliant, it promises these four things about every transaction.

- **Atomicity** — "all or nothing." If any part of the transaction fails, the entire transaction is undone. You never see a partial result.
- **Consistency** — "the rules are always followed." The database enforces constraints (no negative balances, no orphaned references) and rejects any transaction that would violate them.
- **Isolation** — "you can't see my work until I'm done." Concurrent transactions don't interfere with each other. The exact degree is configurable (see 1.4 Isolation Levels).
- **Durability** — "once I say it's done, it's done." A committed transaction survives power failures, crashes, and restarts.

**Why ACID matters for fintech:** Without atomicity, a transfer can debit the sender and crash before crediting the receiver — money vanishes. Without isolation, two concurrent withdrawals can both succeed against the same balance — money is created. Without durability, a confirmed payment disappears after a server restart — trust is destroyed. These aren't theoretical concerns; they're the exact bugs that happen when you build financial systems on databases without these guarantees.

| Property    | Guarantee                                  | What breaks without it                                  |
| ----------- | ------------------------------------------ | ------------------------------------------------------- |
| Atomicity   | All or nothing — partial writes impossible | Debit $100 succeeds, credit $100 fails → money vanishes |
| Consistency | Database moves between valid states        | Negative balance, orphaned foreign keys                 |
| Isolation   | Concurrent transactions don't interfere    | Two withdrawals read same balance → double-spend        |
| Durability  | Committed data survives crashes            | Confirmed payment disappears after restart              |

**How each property works under the hood:**

**Atomicity** uses the WAL. Before modifying any data, the database writes the intended changes to the WAL. If the transaction commits, all changes are applied. If it aborts (or the machine crashes mid-transaction), the database reads the WAL and rolls back any partial changes. There's no state where half a transaction is visible.

**Consistency** is enforced by constraints — CHECK, UNIQUE, FOREIGN KEY, NOT NULL. The database rejects any write that would violate these rules. If you define `CHECK (balance >= 0)`, no transaction can make a balance negative, regardless of application bugs.

**Isolation** is enforced by concurrency control. PostgreSQL uses MVCC (Multi-Version Concurrency Control): each transaction sees a snapshot of the database as of its start time. Writes create new versions of rows, not overwriting old ones. Concurrent readers see the old version; they don't block or see partial writes. For stricter isolation, the database adds locks or detects conflicts and aborts one transaction.

**Durability** is the WAL again. A transaction is only reported as committed after its WAL entry is `fsync`'d to disk. Even if the machine loses power one millisecond later, the WAL entry is on disk and will be replayed on recovery.

**Key insight:** On a single machine with a single database, you get all four for free (or near-free). Transactions are the most powerful primitive you have. Everything after Phase 1 is about losing transactions across boundaries and fighting to get them back.

### 1.4 Isolation Levels

**What is isolation?**

Isolation answers one question: **what happens when two transactions run at the same time on the same data?**

On a single-user system, this doesn't exist - one operation finishes, the next starts. But a payment system handles hundreds of concurrent requests. Two users might withdraw from a shared account simultaneously. Two fraud checks might read and update the same risk score. The database must decide: how much should these concurrent transactions see of each other's work?

**The spectrum:**

At one extreme: every transaction runs as if it's the only one. Perfect safety, but slow — transactions queue up and wait. At the other extreme: transactions see everything, including uncommitted work from other transactions. Fast, but dangerous — you might act on data that gets rolled back. Isolation levels are the knob between these extremes. You pick how much "interference" you tolerate in exchange for performance.

**Think of it like an office with shared documents:**

- **Read Uncommitted** — You can read a document while someone is still editing it. They might undo their edits, but you already saw them and acted on them.
- **Read Committed** — You can only read a document after someone saves it (commits). But if you read it twice, you might see different versions because someone saved changes between your two reads.
- **Repeatable Read** — When you open a document, you get a frozen copy. No matter how many times you read it, you see the same version. But repeatable reads do not solve phantom anamoly which occurs at the entity level - If you search "all documents" a new document could appear between searches (phantom).
- **Serializable** — You're in a private room with the documents. Nobody can change anything you're looking at until you're done. The system behaves as if transactions ran one-at-a-time, even though they're actually concurrent.

**Why this matters for fintech:** The isolation level determines whether a double-spend is possible. At Read Committed (PostgreSQL's default), two concurrent withdrawals can both read the same balance, both conclude there are sufficient funds, and both deduct — resulting in a negative balance. At Serializable, the database detects this conflict and aborts one. The choice of isolation level is a direct trade-off between throughput and financial correctness.

**Isolation Anamolies**

**Dirty Read:** You read data that another transaction wrote but hasn't committed yet. If that transaction rolls back, you read data that never existed.

```
T1: UPDATE accounts SET balance = 300 WHERE id = 'alice'  (not committed yet)
T2: SELECT balance FROM accounts WHERE id = 'alice' → 300  (dirty read!)
T1: ROLLBACK
T2 used a balance of 300 that was never real.
```

**Non-Repeatable Read:** You read the same row twice in one transaction and get different values because another transaction committed a change in between.

```
T1: SELECT balance FROM accounts WHERE id = 'alice' → 500
T2: UPDATE accounts SET balance = 300 WHERE id = 'alice'; COMMIT;
T1: SELECT balance FROM accounts WHERE id = 'alice' → 300  (different!)
T1 sees two different values within the same transaction.
```

**Phantom Read:** You run the same query twice and get different sets of rows because another transaction inserted/deleted rows in between.

```
T1: SELECT * FROM transactions WHERE account_id = 'alice' → 10 rows
T2: INSERT INTO transactions (account_id, ...) VALUES ('alice', ...); COMMIT;
T1: SELECT * FROM transactions WHERE account_id = 'alice' → 11 rows  (phantom!)
```

Here's the part that makes the distinction worth having: **they're prevented by different mechanisms.**

To prevent **non-repeatable reads**, a database can just lock the rows you read. T2 can't UPDATE those rows until you're done. Simple row-level lock, done.

To prevent **phantoms**, row locks don't help - the offending row _didn't exist_ when T1 started reading. You can't lock a row that doesn't exist yet. Databases need something more: range locks, predicate locks, or an MVCC snapshot that covers the whole predicate, not just the rows you touched. That's exactly why the SQL standard separates them:

- `REPEATABLE READ` prevents non-repeatable reads (locks rows you read) but traditionally still allows phantoms.
- `SERIALIZABLE` prevents both.

A practical case where phantoms bite you: suppose you're enforcing "no account can have more than 5 open transactions." You do:

```
T1: SELECT COUNT(*) FROM transactions
    WHERE account_id = 'alice' AND status = 'open' → 4
T1: (thinks "4 < 5, safe to insert")
T1: INSERT INTO transactions (account_id, status) VALUES ('alice', 'open');
```

If another transaction inserts one between your SELECT and your INSERT, you end up with 6. Row-level locking can't save you - the row you'd want to lock didn't exist when you checked. That's the phantom problem, and it's why it's treated as its own category of anomaly.

The one-line mnemonic: **non-repeatable read = "the row I was watching changed," phantom read = "new rows showed up that I wasn't watching."**

| Level            | Dirty Read | Non-Repeatable Read | Phantom Read | Performance |
| ---------------- | ---------- | ------------------- | ------------ | ----------- |
| Read Uncommitted | Possible   | Possible            | Possible     | Fastest     |
| Read Committed   | No         | Possible            | Possible     | Fast        |
| Repeatable Read  | No         | No                  | Possible     | Medium      |
| Serializable     | No         | No                  | No           | Slowest     |

**When to use each level:**

| Level            | Use Case                                                                                                                   | Fintech Example                                                                                                                              |
| ---------------- | -------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| Read Uncommitted | Almost never. No practical use                                                                                             | Don't use in fintech. Not even PostgreSQL supports it (silently upgrades to Read Committed)                                                  |
| Read Committed   | General-purpose default. Safe for most reads where you don't re-read the same row within a transaction                     | Fetching user profile, loading fraud rules, displaying exchange rates, reporting queries                                                     |
| Repeatable Read  | When your transaction reads a value and makes a decision based on it — you need that value to stay stable for the duration | Generating a monthly statement (don't want new transactions appearing mid-generation), computing aggregates across multiple queries          |
| Serializable     | When concurrent transactions touching the same data must behave as if they ran one-at-a-time. Maximum safety               | Balance updates, payment processing, inventory reservation — any case where two concurrent reads + writes on the same row could corrupt data |

**In practice at Revolut-scale:**

Most queries run at **Read Committed** (the PostgreSQL default) — it's fast and sufficient for reads that don't inform critical decisions. For the payment hot path (check balance → debit), you don't typically bump to Serializable for the whole transaction. Instead, you use **Read Committed + `SELECT FOR UPDATE`** — this gives you the safety of Serializable for the specific rows you care about (the balance row) without the overhead of tracking all read/write dependencies across the entire transaction. It's a surgical approach: lock exactly what matters, leave everything else fast.

```
-- Read Committed + SELECT FOR UPDATE (common fintech pattern):
BEGIN;
  SELECT balance FROM accounts WHERE id = 'alice' FOR UPDATE;  ← locks this row
  -- other transactions block on Alice's row, but can freely read/write other rows
  UPDATE accounts SET balance = balance - 100 WHERE id = 'alice';
COMMIT;

-- vs Serializable (heavier):
BEGIN TRANSACTION ISOLATION LEVEL SERIALIZABLE;
  SELECT balance FROM accounts WHERE id = 'alice';  ← no lock, but DB tracks the read
  UPDATE accounts SET balance = balance - 100 WHERE id = 'alice';
COMMIT;  ← DB checks for conflicts, may abort and force retry
```

**How PostgreSQL implements isolation (MVCC):**

Each row has a hidden `xmin` (transaction that created it) and `xmax` (transaction that deleted/updated it). When you start a transaction, PostgreSQL records which transactions are committed. Your reads only see rows where `xmin` is committed and `xmax` is not. Different isolation levels control _when_ that visibility snapshot is taken — at statement start (Read Committed) or transaction start (Repeatable Read/Serializable).

**Concurrency problems in practice:**

```
Double-spend (without proper isolation):
  T1: SELECT balance FROM accounts WHERE id = 'alice'  → $500
  T2: SELECT balance FROM accounts WHERE id = 'alice'  → $500
  T1: UPDATE accounts SET balance = 500 - 400 WHERE id = 'alice'  → $100
  T2: UPDATE accounts SET balance = 500 - 300 WHERE id = 'alice'  → $200
  Both succeed. Alice spent $700 from a $500 balance.
```

**Solutions:**

- **Serializable isolation:** Database tracks read/write dependencies between transactions. If it detects a cycle (T1 read what T2 wrote, T2 read what T1 wrote), it aborts one. No application code change needed, but some transactions will be retried.

- **Pessimistic locking:** `SELECT balance FROM accounts WHERE id = 'alice' FOR UPDATE` — grabs an exclusive lock on Alice's row. Any other transaction trying to read or update this row **blocks** until the first transaction commits or rolls back. Simple and safe, but concurrent requests to the same account queue up.

- **Optimistic locking:** `UPDATE accounts SET balance = new_val WHERE id = 'alice' AND balance = expected_val` — no lock is held. The UPDATE includes a WHERE clause on the expected current value. If another transaction changed the balance in between, the WHERE clause matches zero rows and the application knows to retry. Better throughput when conflicts are rare, but requires retry logic in application code.

### 1.5 Indexing

### HR-Level Quick Answer

> "Database indexes typically use a **B+ tree** — a balanced tree where all data pointers live in the leaf nodes, and leaves are linked together. This gives O(log n) lookups, range scans, and ordered access. That's why it's the default index type in Postgres, MySQL, etc."

- **Why B+ tree over B-tree?** Leaf-level linking makes range queries fast — no backtracking up the tree. All values at leaves means internal nodes are smaller, more keys fit per page, fewer disk reads.
- **Why not a hash index?** Hash gives O(1) point lookups but can't do range queries (`WHERE price > 100`). Most real queries need ranges, ordering, or prefix matching.
- **Why not BST/AVL/Red-Black?** Too deep — O(log₂ n) height means too many disk I/Os. B+ trees are wide and shallow (high branching factor), optimized for disk page reads.
- **One-liner if pressed:** "B+ tree is the right trade-off — O(log n) for reads, supports ranges, and minimizes disk I/O because it's wide and shallow."

### **Starting from the bottom: how data lives on disk**

Before understanding indexes, you need to understand what happens without one.

PostgreSQL stores table data in **pages** (also called blocks). Each page is **8KB**. A page contains multiple rows (tuples). A table with 1 million rows might occupy ~50,000 pages on disk.

```
Table "transactions" on disk:

Page 0:  [row1, row2, row3, ..., row40]
Page 1:  [row41, row42, ..., row80]
Page 2:  [row81, row82, ..., row120]
...
Page 49999: [row999961, ..., row1000000]

Each row's physical address = (page_number, slot_number)
  row42 lives at (1, 2) — page 1, slot 2
  This address is called a "tuple ID" or ctid in PostgreSQL
```

Rows are stored in **insertion order** (called a "heap"). There is no sorting by any column. The table is just a pile of pages, each containing rows wherever they fit.

### **What happens without an index: the sequential scan**

```sql
SELECT * FROM transactions WHERE account_id = 'acc_123';
```

PostgreSQL has no idea which pages contain `account_id = 'acc_123'`. It must:

```
1. Read page 0    → check every row → found 0 matches
2. Read page 1    → check every row → found 1 match
3. Read page 2    → check every row → found 0 matches
...
49,999. Read page 49999 → check every row → found 0 matches

Total: read ALL 50,000 pages = 400MB of disk I/O
Found: 50 matching rows
Wasted: read 999,950 irrelevant rows to find 50
```

This is a **sequential scan** (Seq Scan). It reads every page in the table, regardless of how many rows match. For a table with 1 million rows, it reads 1 million rows. For a table with 100 million rows, it reads 100 million rows.

Sequential scans are not always bad — if your query returns most of the table (e.g., 80% of rows), reading everything sequentially is actually faster than jumping around via an index. But for selective queries (returning <20% of rows), it's extremely wasteful.

### **What is an index?**

An index is a **separate data structure** that the database maintains alongside your table. It maps column values to row locations (ctids), so the database can jump directly to matching rows instead of scanning everything.

```
Without index (heap only):
  "Find account acc_123" → read ALL 50,000 pages → find 50 rows

With index on account_id:
  "Find account acc_123" → look up in index (3 page reads) → get 50 ctids
                         → fetch exactly those 50 rows from exactly those pages
                         → ~53 page reads total instead of 50,000
```

**The analogy:** The table is a book where pages are in random order. The index is the back-of-book index — an alphabetical list that tells you "topic X is on pages 47, 102, 339." Without it, finding topic X means reading every page.

**The cost:** Indexes speed up reads but slow down writes. Every INSERT, UPDATE, or DELETE must update both the table AND every index on that table. An index is not free — it's a trade-off.

```
Table with 0 indexes:  INSERT takes 1 unit of work
Table with 3 indexes:  INSERT takes ~4 units (table + 3 index updates)
Table with 10 indexes: INSERT takes ~11 units — writes are now 11x slower
```

Each index also consumes disk space and memory (PostgreSQL caches hot index pages in the buffer pool). A table with 5 indexes might use more space for indexes than for the actual data.

### **How PostgreSQL decides: the query planner**

PostgreSQL does not blindly use an index just because one exists. The **query planner** estimates the cost of different strategies and picks the cheapest:

```
Query: SELECT * FROM transactions WHERE status = 'COMPLETED';
-- 95% of rows are COMPLETED

Option A: Index Scan
  - Look up 'COMPLETED' in index → get 950,000 ctids
  - Fetch 950,000 rows from scattered pages (random I/O)
  - Cost: very high (random reads across most of the table)

Option B: Sequential Scan
  - Read all pages in order (sequential I/O)
  - Filter out the 5% that aren't COMPLETED
  - Cost: moderate (sequential reads are fast)

Planner picks: Option B — Seq Scan is cheaper
```

The planner uses **statistics** (row counts, value distribution, null fraction) collected by `ANALYZE` to make these estimates. Stale statistics → bad plans.

```sql
-- Force statistics refresh
ANALYZE transactions;

-- See what plan the planner chose
EXPLAIN ANALYZE SELECT * FROM transactions WHERE account_id = 'acc_123';
```

### Types of Indexes

#### B-Tree Index (the default, covers 90% of use cases)

Already covered in 1.2 at a high level. Here's the deeper picture.

**Why B-tree and not binary tree?** Because disk I/O is measured in **pages, not individual values**. Reading one byte from disk costs the same as reading 8KB — the disk gives you the whole page. A binary tree has branching factor 2 — for 1 billion rows, you'd need ~30 levels = 30 disk reads. A B-tree packs hundreds of keys into each 8KB node, giving a branching factor of ~300:

```
Binary tree (branching factor 2):
  Level 0:  1 node
  Level 1:  2 nodes
  Level 2:  4 nodes
  ...
  Level 30: 1 billion nodes → 30 disk reads per lookup

B-tree (branching factor ~300):
  Level 0 (root):  1 node          → 300 children
  Level 1:         300 nodes       → 90,000 children
  Level 2:         90,000 nodes    → 27,000,000 leaves
  Level 3:         27M leaves      → covers ~8 billion rows

  3-4 levels for billions of rows → 3-4 disk reads per lookup
```

In practice, the root node and first level are almost always **cached in RAM** (buffer pool), so a lookup is typically **1-2 actual disk reads**.

**B-tree properties:**

- O(log n) lookups — but with a very large base (log₃₀₀ n, not log₂ n)
- **Sorted** — supports equality (`WHERE id = 5`), range (`WHERE created_at > '2026-01-01'`), and ordering (`ORDER BY created_at DESC`)
- **Balanced** — every leaf is at the same depth. The tree auto-rebalances on inserts/deletes
- Default when you write `CREATE INDEX` in PostgreSQL

**Leaf nodes are linked:** The leaves form a doubly-linked list. This is why range queries are fast:

```
Query: SELECT * FROM transactions WHERE id BETWEEN 25 AND 75

Step 1: Walk tree to find leaf containing 25 (3 steps)
Step 2: Follow leaf → leaf → leaf pointers forward until id > 75

  [10,15,20] → [25,30,35] → [40,45,50] → [55,60,65] → [70,75,80] → stop
                ↑ start here                              ↑ stop here

No need to re-traverse the tree for each value.
```

**Write cost — node splits:** When you insert a value into a full leaf node, it **splits**:

```
Before insert 28:
  Leaf: [20, 25, 30, 35] (full)

After insert 28:
  Leaf A: [20, 25, 28]    Leaf B: [30, 35]
  Parent gets new key [30] pointing to Leaf B

If the parent is also full, it splits too → cascade upward.
Worst case: splits cascade to root, tree grows one level taller.
```

This is why indexes make writes slower — every insert/update/delete must update the table AND every index (and may trigger splits).

#### Composite Index (multiple columns)

When your query filters on more than one column, a single-column index isn't enough.

```sql
-- Query: "all transactions for account X in date range"
SELECT * FROM transactions
WHERE account_id = 'acc_123' AND created_at > '2026-01-01'
ORDER BY created_at DESC;
```

**Without composite index:** PostgreSQL uses the single-column index on `account_id` to find all of Alice's transactions (maybe 10,000 rows), then scans all 10,000 to filter by date. Slow.

**With composite index:**

```sql
CREATE INDEX idx_txn_account_date ON transactions (account_id, created_at DESC);
```

PostgreSQL walks the B-tree: find `account_id = 'acc_123'` (narrows to one subtree), then within that subtree, the dates are already sorted descending. It jumps directly to `2026-01-01` and scans forward. Finds 50 rows instead of scanning 10,000.

**Column order matters — the "leftmost prefix" rule:**

Think of it like a phone book sorted by (last_name, first_name, city). You can look up "Smith" (last name only) — they're all grouped together. You can look up "Smith, John" — within the Smiths, Johns are together. But you **cannot** efficiently look up "John" alone — the Johns are scattered across all last names.

```
Index on (account_id, created_at, status):

  ✅ WHERE account_id = 'acc_123'                           → uses index
  ✅ WHERE account_id = 'acc_123' AND created_at > '2026'   → uses index
  ✅ WHERE account_id = 'acc_123' AND created_at > '2026' AND status = 'DONE' → uses index
  ❌ WHERE created_at > '2026'                               → can't use index (account_id not specified)
  ❌ WHERE status = 'DONE'                                   → can't use index (account_id not specified)

The index is a sorted tree: first by account_id, then by created_at, then by status.
Skipping the first column is like looking for "page 47" in a book where pages are grouped by chapter first.
You can't skip chapters.
```

**Rule of thumb:** Put equality columns first (exact match narrows fast), range columns last (scanned within the narrowed subtree).

#### Partial Index (index only some rows)

```sql
-- Only 2% of transactions are PENDING, but you query them constantly
CREATE INDEX idx_pending ON transactions (user_id) WHERE status = 'PENDING';

-- vs full index:
CREATE INDEX idx_status ON transactions (user_id, status);
```

The partial index is ~50x smaller (indexes 2% of rows instead of 100%). Smaller index = fits in memory, faster lookups, less write overhead. Use when you have a common query that filters on a fixed condition.

**Fintech partial index examples:**

```sql
-- Payments awaiting processing
CREATE INDEX idx_processing ON payments (created_at) WHERE status = 'PROCESSING';

-- Flagged transactions for fraud review
CREATE INDEX idx_flagged ON transactions (user_id) WHERE fraud_flag = true;

-- Unresolved reconciliation discrepancies
CREATE INDEX idx_unresolved ON reconciliation (created_at) WHERE resolved = false;
```

#### Covering Index (index-only scan)

```sql
-- Query: just the payment_id and amount for a user
SELECT payment_id, amount FROM payments WHERE user_id = 'user_123';

-- Normal index: find rows via index → go to table to fetch payment_id and amount (heap fetch)
CREATE INDEX idx_user ON payments (user_id);

-- Covering index: includes the columns you need IN the index itself
CREATE INDEX idx_user_covering ON payments (user_id) INCLUDE (payment_id, amount);

-- Now PostgreSQL answers the query entirely from the index — never touches the table
-- Called an "index-only scan" — fastest possible read
```

The trade-off: the index is larger (stores more data), but eliminates the heap fetch entirely. Worth it for hot, frequently-run queries.

**The visibility map gotcha:** PostgreSQL uses MVCC — each row can have multiple versions. The index doesn't know which version is visible to your transaction. Even with a covering index, PostgreSQL checks the **visibility map** to confirm the row is visible.

```
Index-only scan works when:
  ✅ The table page has been VACUUMed (visibility map says "all tuples visible")

Falls back to heap fetch when:
  ❌ Page has recent updates/deletes (visibility map says "not all visible")
```

If you have a hot table with constant writes, your covering index might still do heap fetches until `VACUUM` runs. Tune `autovacuum` aggressively on tables where you rely on index-only scans.

#### Hash Index

Uses a hash function to map a key directly to a bucket. O(1) lookups for exact matches, but **destroys order** — no range queries, no sorting.

```
B-tree stores:  10, 20, 25, 30, 35 (sorted — can walk from 20 to 30)
Hash stores:    hash(25)=bucket7, hash(10)=bucket3, hash(30)=bucket1 (no order)

How it works:
  INSERT key=25:  compute hash(25) = 7 → store in bucket 7
  LOOKUP key=25:  compute hash(25) = 7 → go directly to bucket 7 → found

  RANGE key BETWEEN 20 AND 30:  impossible without scanning all buckets
```

Think of it like a dictionary — you can look up a word instantly, but you can't ask "give me all words between 'apple' and 'banana'" without scanning everything.

**When to use:** Only for exact-match lookups on columns you never range-scan. Examples: idempotency keys, session tokens, API keys.

```sql
CREATE INDEX idx_idempotency ON payments USING hash (idempotency_key);
```

**Fintech use:** Idempotency key lookups. You always search by exact key, never by range.

#### GIN Index (Generalized Inverted Index)

For "contains" queries — JSONB fields, arrays, full-text search.

```sql
-- Index on a JSONB column
CREATE INDEX idx_metadata ON payments USING gin (metadata);

-- Now this query uses the index:
SELECT * FROM payments WHERE metadata @> '{"currency": "USD"}';

-- Also works for array containment:
CREATE INDEX idx_tags ON transactions USING gin (tags);
SELECT * FROM transactions WHERE tags @> ARRAY['fraud', 'flagged'];
```

**How it works:** A GIN index is an inverted index — it maps each key (each JSON key-value pair, each array element) to a list of rows that contain it. Like the index at the back of a textbook: "USD → rows 5, 42, 789, 1203."

**Fintech use:** Indexing JSONB metadata columns (payment provider responses, webhook payloads). Query structured data without schema changes.

#### LSM Tree (Log-Structured Merge)

Not a PostgreSQL index type, but important to understand because it's what Cassandra, RocksDB, and LevelDB use under the hood. Unlike B-trees which update data in place (random I/O), LSM trees are write-optimized:

```
Write path:
  1. Write to in-memory sorted table (memtable) — fast, no disk I/O
  2. When memtable is full → flush to disk as a sorted file (SSTable)
  3. Background compaction merges SSTables to reduce the number of files

Read path:
  1. Check memtable first (in memory)
  2. Then check SSTables from newest to oldest (on disk)
  3. Bloom filters help skip SSTables that definitely don't have the key
```

**B-tree vs LSM:**

| Aspect      | B-tree                                 | LSM                                             |
| ----------- | -------------------------------------- | ----------------------------------------------- |
| Write speed | Slower (random I/O to update in place) | Faster (sequential writes, batched)             |
| Read speed  | Faster (one tree to check)             | Slower (may check memtable + multiple SSTables) |
| Space       | Compact (one copy)                     | Larger (multiple copies until compaction)       |
| Best for    | Read-heavy, mixed workloads            | Write-heavy workloads                           |
| Used in     | PostgreSQL, MySQL                      | Cassandra, RocksDB, LevelDB                     |

**Fintech relevance:** Core tables (accounts, balances) live in PostgreSQL (B-tree). High-volume append-only data (transaction event logs, audit trails, fraud detection events) might live in Cassandra or RocksDB-backed systems (LSM) where write throughput matters more than read latency.

### Scan Types — How PostgreSQL Uses (or Doesn't Use) an Index

When you run `EXPLAIN ANALYZE`, you'll see one of these scan types. Understanding them is critical for diagnosing performance:

```
                        Few rows match     Many rows match       Most rows match
                        ──────────────────────────────────────────────────────────
Plan chosen:            Index Scan         Bitmap Index Scan     Seq Scan
How it works:           Walk index →       Walk index →          Read every page
                        fetch each row     build bitmap of       sequentially
                        one at a time      page locations →
                                           sort by page →
                                           fetch pages in order
Disk I/O pattern:       Random I/O         Sequential I/O        Sequential I/O
Typical threshold:      < ~1% of table     ~1-20% of table       > ~20% of table
```

**Index Scan:** Walks the B-tree, finds a ctid, fetches the row from the heap, repeats. Each heap fetch may hit a different page (random I/O). Great when few rows match.

**Bitmap Index Scan:** Two-phase approach. Phase 1: walk the index, collect all matching ctids into a bitmap of page numbers. Phase 2: sort pages by number, read them in order. Converts random I/O to sequential I/O.

```
Index Scan for 5,000 rows:
  Read page 4791 → page 23 → page 8834 → page 102 → ... (random jumps)

Bitmap Index Scan for 5,000 rows:
  Phase 1: index says rows are on pages {23, 102, 4791, 8834, ...}
  Phase 2: sort → read page 23 → 102 → 4791 → 8834 → ... (sequential)
```

**Bitmap AND/OR:** PostgreSQL can combine multiple single-column indexes using bitmap operations:

```sql
-- Two separate indexes: idx_account_id and idx_status
SELECT * FROM transactions
WHERE account_id = 'acc_123' AND status = 'PENDING';

-- PostgreSQL does:
-- 1. Bitmap from idx_account_id → pages {2, 5, 8, 12, 15}
-- 2. Bitmap from idx_status     → pages {5, 8, 20, 30}
-- 3. Bitmap AND                 → pages {5, 8}
-- 4. Fetch only pages 5 and 8
```

This is why you don't always need a composite index — two single-column indexes + bitmap AND can be "good enough."

**Index Only Scan:** The best case. The index contains all columns the query needs (covering index). PostgreSQL reads only the index, never touches the heap. Shows as `Index Only Scan` in EXPLAIN output.

**Seq Scan:** Reads every page in the table. No index used. Not always bad — it's the right choice when the query touches most of the table.

### Index Bloat — The Silent Performance Killer

Indexes grow but don't automatically shrink. After heavy UPDATE/DELETE activity, dead tuples remain in the index. The pages aren't returned to the OS — the index gets sparse.

```
Fresh index:   100MB, 3 levels, tightly packed
Bloated index: 800MB, 5 levels, 85% dead space → more pages to read, more cache misses
```

**Detection:**

```sql
-- Check if indexes are being used at all
SELECT indexrelname, idx_scan, idx_tup_read
FROM pg_stat_user_indexes
WHERE schemaname = 'public' ORDER BY idx_scan;

-- Check bloat (requires pgstattuple extension)
SELECT * FROM pgstatindex('idx_txn_account_date');
-- avg_leaf_density < 50% = significant bloat
```

**Fix:** `REINDEX CONCURRENTLY idx_txn_account_date;` — rebuilds the index without locking the table.

### When NOT to index

- **Low cardinality columns** (boolean, status with 2-3 values) — the index doesn't narrow enough to be useful. Exception: partial index on the rare value (`WHERE status = 'PENDING'`)
- **Tables with extreme write volume and rare reads** — every index slows every write. If you write 10,000 rows/second but query once a minute, the index costs more than it saves
- **Small tables** (< 1,000 rows) — a full table scan reads a few pages. The overhead of maintaining an index exceeds the benefit
- **Columns you never filter, sort, or join on** — an index that no query uses is pure cost

### How to tell if your index is being used

```sql
EXPLAIN ANALYZE SELECT * FROM transactions WHERE account_id = 'acc_123';

-- Look for:
--   "Index Scan using idx_txn_account_date" → index is used ✅
--   "Seq Scan on transactions"              → full table scan, index not used ❌
--   "Index Only Scan"                        → covering index, fastest ✅✅
--   "Bitmap Index Scan"                      → index used partially, then heap fetch

-- Also check: "actual time" and "rows" to see real performance
```

`EXPLAIN ANALYZE` is your best friend. Never assume an index is being used — verify it. PostgreSQL's query planner may decide a full scan is cheaper (e.g., if the query returns 80% of the table, scanning is faster than index lookups + heap fetches).

### Functional Index

When your WHERE clause applies a function to a column, a normal B-tree index on that column **won't be used**:

```sql
-- This index exists:
CREATE INDEX idx_email ON users (email);

-- This query does NOT use it:
SELECT * FROM users WHERE LOWER(email) = 'alice@example.com';
-- PostgreSQL can't use the index because LOWER(email) ≠ email

-- Fix: create a functional index
CREATE INDEX idx_email_lower ON users (LOWER(email));
-- Now the query uses the index
```

The same applies to any expression: `WHERE DATE(created_at) = '2026-01-01'` won't use an index on `created_at`. Either rewrite the query (`WHERE created_at >= '2026-01-01' AND created_at < '2026-01-02'`) or create a functional index on `DATE(created_at)`.

### Interview: "Design the indexes for this table"

Think about the **queries first**, not the table:

```
1. "Get all transactions for a user in a date range"
   → Composite: (user_id, created_at DESC)

2. "Check if this payment is a duplicate"
   → Unique index on idempotency_key (or hash index)

3. "Get all pending payments for processing"
   → Partial: (created_at) WHERE status = 'PENDING'

4. "Dashboard showing user's recent payment amounts"
   → Covering: (user_id) INCLUDE (payment_id, amount, created_at)
```

### Interview: "Why is this query slow?" — the checklist

```
1. Run EXPLAIN ANALYZE — is it using the expected index?
2. Is the query returning too many rows? (>20% of table → planner prefers seq scan)
3. Is a function applied to the indexed column? (LOWER, DATE, etc.)
4. Are statistics stale? → run ANALYZE table_name
5. Is the index bloated? → check pgstatindex
6. Is the covering index doing heap fetches? → check visibility map / VACUUM
```

## Phase 2: Single Service, Multiple Machines

**You add a second machine. For the first time, things can disagree.**

### 2.1 Replication ?

Replication is a process of copying data to multiple machines to improve the throughput, durability, and latency.

1. **Durability** — if the primary dies, a copy exists
2. **Read throughput** — offload reads to replicas
3. **Latency** — place replicas closer to users

The moment you have two copies of the same data, you have a distributed system.

### 2.2 Replication: Leader-Follower

```
Client → Leader (writes + reads) → Follower 1 (reads)
                                 → Follower 2 (reads)
                                 → Follower 3 (reads)
```

All writes go to the leader. Leader replicates to followers. Followers serve reads.

**How replication actually works (PostgreSQL streaming replication):**

The leader doesn't send "insert this row" commands to followers. It sends **WAL records** - the same low-level change log that provides crash recovery. Followers apply these WAL records to their own data files, replaying the exact same changes the leader made. This is why it's called "physical replication" — followers are byte-for-byte identical to the leader (with a small time lag).

```
Leader writes WAL entry → WAL entry streamed to Follower → Follower replays entry
```

This means followers can't have different indexes or schemas — they're exact copies. Logical replication (sending higher-level change descriptions) allows more flexibility but is more complex.

**Synchronous replication:**

```
Client → Write to Leader → Leader sends to Follower → Follower ACKs → Leader ACKs client
  - Guarantees: follower has the data before client gets confirmation
  - Cost: every write waits for follower — slower
  - Use for: at least one follower (zero data loss on leader crash)
```

**Asynchronous replication:**

```
Client → Write to Leader → Leader ACKs client → Leader sends to Follower (eventually)
  - Guarantees: none — follower may lag behind
  - Cost: fast writes
  - Risk: leader crashes before replicating → data lost
  - Use for: remaining followers (performance)
```

### 2.3 Replication Lag — Your First Distributed Systems Problem

```
Timeline:
  T=0ms:  Client writes balance=$500 to Leader
  T=1ms:  Leader ACKs client "write successful"
  T=2ms:  Client reads balance from Follower → $520 (old value!)
  T=150ms: Follower receives replication → now has $500

The client wrote $500, immediately read $520. Their own write is invisible.
```

**This is not a bug. This is the fundamental cost of replication.**

**Solutions:**

| Strategy            | How                                                               | Trade-off              |
| ------------------- | ----------------------------------------------------------------- | ---------------------- |
| Read from leader    | Route reads to leader after a write                               | Leader takes more load |
| Read-your-writes    | Track "last write timestamp", read from replica only if caught up | Complex routing logic  |
| Synchronous replica | Read from sync follower (guaranteed up-to-date)                   | Slower writes          |
| Causal consistency  | Tag reads with the causal dependency                              | Complex implementation |

**Fintech application:** Balance reads after a payment MUST go to the leader. Transaction history for display can go to a replica (slightly stale is acceptable).

### 2.4 Failover

Failover is a process of promoting a follower to become a leader. It has three steps: detection, election, and promotion.

```
Leader dies.

  1. Detection: followers stop receiving heartbeats (timeout: 10-30s)
  2. Election: synchronous follower is promoted to leader
  3. Recovery: other followers point to new leader
  4. Problem: what about writes the old leader accepted but didn't replicate?

Scenarios:
  a) Sync follower promoted → zero data loss (had all committed writes)
  b) Async follower promoted → some writes lost (didn't receive them yet)
  c) Old leader comes back → its unreplicated writes conflict with new leader
```

**Split-brain:** Both old and new leader accept writes simultaneously. This is catastrophic — two leaders accepting writes means two divergent copies of truth. Must be prevented via fencing (revoke old leader's access to storage — e.g., STONITH: "Shoot The Other Node In The Head", which forcibly powers off the old leader's machine before promoting the new one).

**Why failover is hard in fintech:** During the detection window (10-30s), the system either rejects writes (CP — safe but unavailable) or risks split-brain (AP — available but potentially inconsistent). There is no free lunch. PostgreSQL patroni/pg_auto_failover automate this, but the trade-off remains.

### 2.5 CAP Theorem — Now You Feel It

```
         Consistency
            /\
           /  \
          /    \
         / CP   \
        /________\
       AP         CA
  Availability    (not possible
                   with partitions)
     Partition Tolerance
```

Network partitions are inevitable. During a partition, you choose:

- **CP:** Reject requests until partition heals (consistent but unavailable)
- **AP:** Serve requests with possibly stale data (available but inconsistent)

**What a partition actually looks like:**

```
Normal:    Leader ←──network──→ Follower     (both reachable)

Partition: Leader ←──  ✗  ──→ Follower     (can't communicate)

Now what?
  CP choice: Leader stops accepting writes (might be stale, can't confirm with follower)
             → Users see "service unavailable" until partition heals
  AP choice: Leader keeps accepting writes, Follower keeps serving reads
             → Follower serves stale data, and when partition heals, conflicting writes must merge
```

CAP is not about choosing two of three properties upfront — it's about what you sacrifice _during_ a partition. When there's no partition (the normal case), you have both consistency and availability.

**Fintech is CP for the money path:**

| System               | Choice | Why                                            |
| -------------------- | ------ | ---------------------------------------------- |
| Balance/Ledger       | CP     | Wrong balance = money created or destroyed     |
| Payment processing   | CP     | Duplicate/lost payments = regulatory liability |
| Transaction history  | AP     | Slightly stale read is acceptable              |
| Fraud scoring        | AP     | Stale score better than no score               |
| Exchange rate quotes | AP     | Short-lived stale quote is tolerable           |

### 2.6 Consistency Models

| Model                  | Guarantee                        | Latency | Fintech Use Case                            |
| ---------------------- | -------------------------------- | ------- | ------------------------------------------- |
| Strong/Linearizability | Read always returns latest write | Highest | Balance reads after write, payment status   |
| Sequential             | All nodes see same order         | High    | Distributed locks, transaction ordering     |
| Causal                 | Causally related ops ordered     | Medium  | Chat messages in support flow               |
| Read-your-writes       | Client sees its own writes       | Medium  | User sees their own transaction immediately |
| Eventual               | All replicas converge eventually | Lowest  | Analytics dashboards, notification status   |

**Understanding each model intuitively:**

**Strong/Linearizability:** Behaves as if there's only one copy of the data. After a write completes, every subsequent read from any node returns that write. The most expensive — every read must check the latest state, often requiring a round trip to the leader.

**Sequential:** All nodes agree on the same order of operations, but that order doesn't have to match real-time. Think of it as a single queue that everyone reads from — you all see the same order, but items might appear in the queue slightly after they happened in the real world.

**Causal:** If event A caused event B, everyone sees A before B. But unrelated events (Alice's payment and Bob's payment to different people) can appear in any order. This is enough for most applications — users rarely care about ordering of unrelated events.

**Read-your-writes:** You always see your own changes. Other users might see stale data, but you never do. The most common practical requirement — implemented by routing reads to the leader after a write, or tracking the write timestamp and only reading from replicas that have caught up.

**Eventual:** Given enough time without new writes, all replicas converge to the same state. The cheapest model — replicas update whenever they can. The window of inconsistency could be milliseconds or seconds depending on load and replication lag.

**Phase 2 summary:** Adding a replica gives you durability and read throughput, but costs you consistency. Reads can return stale data. Failover can lose writes. There is no "now" across machines. You must explicitly choose where to read (leader vs follower) based on how much staleness you can tolerate.

---

## Phase 3: Data Doesn't Fit on One Machine

**Your database is too large or too write-heavy for one server. You split the data itself.**

### 3.1 Partitioning / Sharding

Unlike replication (full copy on each node), sharding splits data across nodes. Each node holds a subset.

```
Replication:  Node A = [all data]    Node B = [all data]    (copies)
Sharding:     Node A = [accounts 1-1M]  Node B = [accounts 1M-2M]  (subsets)
```

**Strategies:**

| Strategy           | How                           | Pros                            | Cons                           |
| ------------------ | ----------------------------- | ------------------------------- | ------------------------------ |
| Range-based        | Shard by key range (A-M, N-Z) | Range queries efficient         | Hot spots if uneven            |
| Hash-based         | Hash(key) % N                 | Even distribution               | No range queries across shards |
| Consistent Hashing | Hash ring with virtual nodes  | Minimal redistribution on scale | More complex implementation    |
| Geographic         | By region/country             | Low latency, data residency     | Cross-region queries hard      |

### 3.2 Consistent Hashing

**Why naive `hash(key) % N` breaks:**

```
With 3 nodes: hash(key) % 3
  Add a 4th node: hash(key) % 4
  Almost every key maps to a different node → massive data migration

Consistent hashing:
        Node A (hash=10)
       /                \
  Node D (hash=350)    Node B (hash=120)
       \                /
        Node C (hash=250)

  Key hash → walk clockwise → first node encountered
  Virtual nodes: each physical node gets multiple positions on ring
  Add a node: only ~1/N keys need to move (not all of them)
```

**Why virtual nodes matter:**

With only 4 physical nodes on the ring, data distribution can be uneven — one node might own a huge arc and another a tiny one. Virtual nodes solve this by giving each physical node many positions (e.g., 150 virtual nodes per physical node). This creates a fine-grained distribution where each physical node owns many small arcs spread around the ring, resulting in near-even load distribution.

```
Without virtual nodes:     Node A owns 40%, B owns 10%, C owns 35%, D owns 15%
With 150 virtual nodes each: A owns ~25%, B owns ~25%, C owns ~25%, D owns ~25%
```

**How adding a node works:**

```
Before: Nodes A, B, C on ring
  Key "alice" hashes to position 100 → walks clockwise → hits Node B at 120

Add Node E at position 110:
  Key "alice" hashes to 100 → walks clockwise → hits Node E at 110 (new owner!)
  Key "bob" hashes to 200 → walks clockwise → still hits Node C at 250 (unchanged)

Only keys between the new node and its predecessor need to move.
All other keys stay where they are.
```

### 3.3 What You Lose When You Shard

**You lose cross-shard transactions:**

```
Before sharding (single DB):
  BEGIN;
    UPDATE accounts SET balance = balance - 100 WHERE id = 'alice';  -- shard A
    UPDATE accounts SET balance = balance + 100 WHERE id = 'bob';    -- shard B
  COMMIT;
  ← This worked as one atomic transaction

After sharding:
  Alice is on Shard A, Bob is on Shard B
  No single transaction can span both
  ← You need a saga or 2PC (Phase 6)
```

**You lose joins across shards:**

```
Before: SELECT * FROM users JOIN transactions ON users.id = transactions.user_id
After: users and transactions on different shards → application-level join or denormalize
```

**You lose global ordering:**

```
Before: auto-increment ID gives total order
After: each shard has its own sequence → need Snowflake IDs or UUIDs
```

**Fintech sharding decisions:**

- **Shard by account_id** — keeps all transactions for one user on one shard
- Same-user operations stay on one shard (balance check + debit = single transaction)
- Cross-user transfers (alice → bob) may cross shards → saga pattern
- **Data residency** (GDPR) may force geographic sharding (EU users in EU)

### 3.4 Database Scaling Progression

```
Stage 1: Single PostgreSQL (vertical — bigger machine)
    ↓ hitting ~5K write QPS or storage limits
Stage 2: Read replicas (offload reads)
    ↓ read replicas saturated or lag matters
Stage 3: Caching layer (Redis for hot data)
    ↓ single writer bottleneck
Stage 4: Vertical partitioning (separate DBs per domain)
    ↓ single domain outgrows one server
Stage 5: Horizontal sharding (shard by account_id)
    ↓ global presence required
Stage 6: Multi-region replication
```

**Don't jump to sharding.** A well-indexed PostgreSQL handles 10K+ read QPS and 5K+ write QPS. Start simple, scale when the numbers demand it.

**Phase 3 summary:** Sharding gives you write throughput and storage beyond one machine, but you lose transactions, joins, and ordering across shards. The cost is architectural complexity — sagas, denormalization, global ID generation. Only pay this cost when you must.

## Phase 4: The Split

**You break the monolith into services. Two things break simultaneously: data boundaries and communication.**

This is where the microservices axis and the distributed systems axis diverge. From this point forward, every topic lives on one or both axes.

### 4.1 Where to Draw Service Boundaries _(microservices)_

**Bounded contexts (from Domain-Driven Design):**

A service boundary should align with a business domain that:

- Has its own data (doesn't need joins into other domains)
- Has its own team (can deploy independently)
- Has its own language (an "account" in payments ≠ an "account" in authentication)

**Fintech example:**

```
┌─────────────┐  ┌──────────────┐  ┌───────────────┐
│  Account    │  │   Payment    │  │    Ledger     │
│  Service    │  │   Service    │  │    Service    │
│             │  │              │  │               │
│ - User accts│  │ - Initiate   │  │ - Double-entry│
│ - KYC status│  │ - Process    │  │ - Balances    │
│ - Limits    │  │ - Refund     │  │ - Statements  │
└─────────────┘  └──────────────┘  └───────────────┘

       ┌──────────┐  ┌─────────┐  ┌──────────────┐
       │  Fraud   │  │   FX    │  │ Notification │
       │  Service │  │ Service │  │   Service    │
       │          │  │         │  │              │
       │ - Rules  │  │ - Rates │  │ - Push/SMS   │
       │ - ML     │  │ - Swap  │  │ - Email      │
       │ - Alerts │  │ - Hedge │  │ - In-app     │
       └──────────┘  └─────────┘  └──────────────┘
```

**Signs you drew the boundary wrong:**

- Two services always deploy together → merge them
- Every request requires calling 3+ other services → boundaries too granular
- Services share a database table → not actually independent
- Circular dependencies → domain modeling is wrong

### 4.2 Data Ownership _(both axes)_

**Rule: each service owns its data. No shared databases.**

```
WRONG (shared database):
  Payment Service ──→ [Shared DB] ←── Account Service
  - Can't deploy independently (schema migration blocks both)
  - Can't scale independently
  - Implicit coupling through shared tables

RIGHT (database per service):
  Payment Service → [Payment DB]
  Account Service → [Account DB]
  Communication via APIs or events only
```

**The cost:** You lose cross-service joins. You can't `SELECT * FROM payments JOIN accounts`. You must:

- Denormalize (store account name in payment record)
- API call (payment service calls account service to get name)
- Event-driven (account service publishes events, payment service maintains its own copy)

### 4.3 Synchronous Communication — REST & gRPC _(microservices)_

| Aspect          | REST                        | gRPC                        |
| --------------- | --------------------------- | --------------------------- |
| Format          | JSON (text, human-readable) | Protobuf (binary, compact)  |
| Contract        | OpenAPI / Swagger           | .proto files (strict types) |
| Streaming       | No (need SSE/WS)            | Yes (bidirectional)         |
| Browser support | Native                      | Needs grpc-web proxy        |
| Performance     | Good                        | 2-10x faster                |
| Best for        | Public/mobile APIs          | Internal service-to-service |

**Fintech pattern:** REST externally (mobile app, partners), gRPC internally (payment ↔ ledger ↔ fraud). Protobuf's strict schema prevents field type mismatches that could corrupt financial data.

**Why gRPC is faster:**

REST sends JSON like `{"amount": 10000, "currency": "GBP"}` — text that must be parsed, with field names repeated in every message. gRPC sends Protobuf — a binary format where fields are identified by numbers, not names, and values are encoded compactly. A 1KB JSON payload might be 200 bytes in Protobuf. Multiply by millions of inter-service calls per day, and it matters. Additionally, gRPC uses HTTP/2 by default, enabling multiplexing (multiple requests over one connection) and header compression.

### 4.4 The Unknown State _(distributed systems)_

**The most important idea in this entire syllabus.**

In a monolith, a function call has three outcomes: success, failure, or hang.

Over a network, there's a fourth: **you don't know.**

```
Payment Service → [network] → Ledger Service

Three visible outcomes:
  1. Response: 200 OK → succeeded
  2. Response: 500 Error → failed
  3. No response (timeout) → ???

The "???" is the killer:
  - Maybe the request never arrived (safe to retry)
  - Maybe the request arrived, was processed, but the response was lost (NOT safe to retry naively)
  - Maybe the request arrived, is still processing (might succeed later)
```

**This is why idempotency is not optional in financial systems.** You will retry. The first attempt might have succeeded.

### 4.5 Idempotency _(distributed systems)_

Making every operation safe to repeat.

**Idempotency key pattern:**

```
Client sends: POST /payments
Headers: Idempotency-Key: client-generated-uuid-abc

Server:
  1. Check if idempotency_key exists in store
  2. If exists → return cached response (no re-execution)
  3. If not → execute payment, store key + response, return response
```

**Implementation:**

- Client generates the key (UUID v4) — server can't generate it (doesn't know if request is a retry)
- Store key → response with TTL (24-48 hours)
- Atomic check-and-set: `SET key value NX EX 86400` (Redis) or `INSERT ... ON CONFLICT DO NOTHING` (Postgres)
- Scope keys per user/API key to prevent collisions

**Idempotency at every layer:**

| Layer             | Mechanism                           | Why                             |
| ----------------- | ----------------------------------- | ------------------------------- |
| API Gateway       | Idempotency-Key header              | Client retries after timeout    |
| Service           | Transaction ID dedup                | Duplicate Kafka messages        |
| Database          | UNIQUE constraint on transaction_id | Last line of defense            |
| External provider | Pass-through idempotency key        | Provider retries (Stripe, Visa) |

### 4.6 Timeouts and Retries _(distributed systems)_

```
Payment Service → Fraud Service

  No timeout set → Payment Service hangs forever if Fraud Service is slow
  Timeout too short → Legitimate requests killed, unnecessary retries
  Timeout too long → Resources tied up waiting, cascading slowness
```

**Retry strategies:**

| Strategy             | How                     | Use Case                 |
| -------------------- | ----------------------- | ------------------------ |
| Immediate retry      | Retry instantly         | Transient network glitch |
| Fixed backoff        | Wait N seconds          | Simple, predictable      |
| Exponential backoff  | 1s, 2s, 4s, 8s...       | External API calls       |
| Exponential + jitter | Backoff + random offset | Prevent thundering herd  |

**Fintech retry rules:**

- Always pair retries with idempotency
- Max retries (3 attempts, then dead-letter queue)
- Distinguish retryable (500, 503, timeout) from non-retryable (400, 422)
- Dead-letter queue for failed payments → manual review or scheduled retry

### 4.7 Service Discovery _(microservices)_

**How does Payment Service find Fraud Service?**

| Approach       | How                                                  | Tools                    |
| -------------- | ---------------------------------------------------- | ------------------------ |
| DNS-based      | Service name → DNS → IP addresses                    | Kubernetes DNS, Route 53 |
| Registry-based | Services register themselves, clients query registry | Consul, Eureka, etcd     |
| Sidecar proxy  | Proxy handles routing transparently                  | Istio, Linkerd           |
| Load balancer  | All traffic through central LB                       | Nginx, HAProxy, AWS ALB  |

**Kubernetes DNS (most common today):**

```
Payment Service calls: http://fraud-service.payments.svc.cluster.local:8080/check
  → Kubernetes DNS resolves to pod IPs
  → kube-proxy or service mesh routes to healthy pod
```

### 4.8 API Design _(microservices)_

**Payment API example:**

```
POST /v1/payments
Headers:
  Authorization: Bearer <token>
  Idempotency-Key: <client-uuid>
Body:
  {
    "from_account": "acc_123",
    "to_account": "acc_456",
    "amount": 10000,
    "currency": "GBP",
    "reference": "Rent payment March"
  }

Response (201 Created):
  {
    "payment_id": "pay_abc",
    "status": "PROCESSING",
    "created_at": "2026-04-17T10:00:00Z"
  }
```

**Pagination (transaction history):**

- **Cursor-based** (preferred): `?cursor=eyJpZCI6MTAwMH0&limit=20` — stable with concurrent writes
- **Keyset-based**: `?after_id=pay_abc&limit=20` — efficient with indexed columns
- **Offset-based**: `?page=3&limit=20` — avoid for financial data (results shift as new transactions arrive)

**API versioning:**

- URL-based: `/v1/payments`, `/v2/payments` (most common, explicit)
- Header-based: `Accept: application/vnd.revolut.v2+json` (cleaner but harder to debug)
- Never break existing consumers — add fields, don't remove or rename

**Phase 4 summary:** Splitting the monolith gives you independent deployment and scaling, but you lose function calls (replaced by network calls with unknown outcomes), shared transactions (replaced by sagas), and shared data (replaced by APIs and events). The unknown state and idempotency are the most critical concepts to internalize.

---

## Phase 5: Independence

**How to make services truly independent — in deployment, data, and evolution.**

### 5.1 Independent Deployability _(microservices)_

The whole point of microservices. If you can't deploy Service A without also deploying Service B, you have a distributed monolith, not microservices.

**Requirements for independent deployment:**

- Database per service (no shared schema migrations)
- Backward-compatible APIs (new version serves old clients)
- No synchronous chains for deployment coordination
- Each service has its own CI/CD pipeline

### 5.2 Contract Testing _(microservices)_

**Problem:** Payment Service depends on Fraud Service's API. Fraud team deploys a breaking change. Payment Service breaks in production.

**Solution: consumer-driven contract tests.**

```
Payment Service (consumer) defines:
  "I call GET /v1/fraud-check/{txn_id} and expect { risk_score: number, decision: string }"

Fraud Service (provider) runs this contract in its CI pipeline.
If the contract fails → Fraud team knows they broke Payment Service before deploying.
```

**Tools:** Pact, Spring Cloud Contract

### 5.3 Deployment Strategies _(microservices)_

| Strategy     | How                                           | Risk     | Rollback     |
| ------------ | --------------------------------------------- | -------- | ------------ |
| Rolling      | Replace instances one by one                  | Low      | Redeploy old |
| Blue-Green   | Two identical envs, switch traffic atomically | Low      | Switch back  |
| Canary       | Route 5% to new version, watch metrics        | Very low | Route to old |
| Feature flag | Deploy code, enable feature separately        | Very low | Disable flag |

**Fintech preference:** Canary deployments for payment services. Route 1-5% of traffic to new version. Monitor payment success rate, latency, error rate. Auto-rollback if metrics degrade.

### 5.4 Database Per Service _(both axes)_

```
Monolith:
  [App] → [Single DB with users, payments, ledger, fraud tables]

Microservices:
  [Account Service] → [Account DB]
  [Payment Service] → [Payment DB]
  [Ledger Service]  → [Ledger DB]
  [Fraud Service]   → [Fraud DB]
```

**What each service stores:**

- Account Service: user profiles, KYC status, limits, preferences
- Payment Service: payment requests, statuses, idempotency keys
- Ledger Service: double-entry ledger, materialized balances
- Fraud Service: fraud rules, risk scores, blacklists, ML model metadata

**The cost (revisited):**

- No cross-service joins
- No cross-service transactions
- Data duplication (payment service stores sender name, not just sender_id)
- Eventual consistency between services

### 5.5 Asynchronous Communication _(both axes)_

**Message Queue (point-to-point):**

```
Producer → [Queue] → Consumer
  - Each message consumed by exactly one consumer
  - Use for: task distribution, notification dispatch, retry queues
  - Tools: RabbitMQ, Amazon SQS
```

**Event Streaming (log-based):**

```
Producer → [Partitioned Log] → Consumer Group A (fraud)
                             → Consumer Group B (notifications)
                             → Consumer Group C (analytics)

  - Ordered within partition, durable, replayable
  - Multiple consumer groups process independently
  - Tools: Kafka, Kinesis, Pulsar, Redpanda
```

**How Kafka works internally:**

```
Topic: "payments" (logical channel)
  ├── Partition 0: [event1, event2, event5, event8, ...]
  ├── Partition 1: [event3, event4, event6, ...]
  └── Partition 2: [event7, event9, event10, ...]

Each partition is an append-only log on disk (like a WAL).
Events are assigned to partitions by key: hash(account_id) % num_partitions
Each event gets an offset (sequential number) within its partition.

Consumer Group "fraud":
  Consumer A reads Partition 0
  Consumer B reads Partition 1
  Consumer C reads Partition 2
  → Each partition is read by exactly one consumer in a group
  → Add more consumers = more parallelism (up to num_partitions)

Consumer Group "analytics":
  Completely independent — reads same partitions from the start
  → Fan-out without affecting fraud consumers
```

Kafka is essentially a distributed, replicated, partitioned WAL. Events are appended, never modified or deleted (until retention expires). This is why it's durable, replayable, and ordered within partitions.

**Why Kafka is the fintech default:**

- Durability — events survive broker failures (replicated across brokers)
- Replayability — reprocess after bug fixes or new consumers
- Ordering — per-partition guarantees (partition by account_id)
- Exactly-once semantics (idempotent producers + transactional consumers)
- Natural audit trail

| Requirement               | Queue    | Event Stream                 |
| ------------------------- | -------- | ---------------------------- |
| Exactly-once per consumer | Yes      | Yes (within group)           |
| Fan-out to many consumers | No       | Yes (consumer groups)        |
| Message replay            | No       | Yes                          |
| Ordering guarantees       | FIFO     | Per-partition                |
| Persistence               | Optional | Yes (configurable retention) |

### 5.6 Sync vs Async Payment Flows _(both axes)_

**Synchronous (inline):**

```
Client → API → Fraud → Debit → Credit → Response

  Pros: Immediate confirmation
  Cons: Slow, any failure blocks everything
  Use for: Low-value instant payments, card authorizations
```

**Asynchronous (event-driven):**

```
Client → API → Validate + Accept → Response ("PROCESSING")
                    ↓
              [Kafka: payment.created]
                    ↓
              Fraud Service → [payment.fraud_checked]
                    ↓
              Ledger Service → [payment.settled]
                    ↓
              Notification Service → push to user

Client polls or receives push for final status
```

Pros: Resilient, each step retryable, scalable independently
Cons: User sees "PROCESSING" not "DONE", eventual consistency
Use for: Bank transfers, international payments, high-value transactions

### 5.7 Avoiding the Distributed Monolith _(microservices)_

**Anti-patterns that mean you didn't actually split:**

| Anti-pattern         | Symptom                                  | Fix                                             |
| -------------------- | ---------------------------------------- | ----------------------------------------------- |
| Shared database      | Services read/write the same tables      | Database per service, communicate via events    |
| Synchronous chains   | A → B → C → D, all blocking              | Make B→C→D async, or merge some services        |
| Lock-step deployment | Must deploy A and B together             | Backward-compatible APIs, contract tests        |
| God orchestrator     | One service coordinates everything       | Push logic to domain services, use choreography |
| Shared libraries     | Shared model jar/package across services | Each service defines its own models             |

**Phase 5 summary:** True independence means each service owns its data, deploys alone, and communicates through well-defined contracts (APIs) or events. If you can't deploy one service without touching another, you have the complexity of microservices without the benefits.

---

## Phase 6: Coordination

**Services need to work together on multi-step operations. No shared transactions exist. How do you coordinate?**

```
Monolith:
  BEGIN;
    debit(alice, 100);
    credit(bob, 100);
  COMMIT;
  ← Atomic. All-or-nothing. Done.

Microservices:
  Payment Service calls Ledger Service: debit(alice, 100) → OK
  Payment Service calls Ledger Service: credit(bob, 100)  → TIMEOUT
  ← Alice was debited. Bob may or may not be credited. Money may be gone.
```

### 6.1 Two-Phase Commit (2PC) — Why It Fails in Practice _(distributed systems)_

```
Phase 1 (Prepare): Coordinator → "Can you commit?" → All participants
Phase 2 (Commit):  Coordinator → "Commit" or "Abort" → All participants

Problems:
  - Coordinator fails during Phase 2 → all participants blocked indefinitely
  - Locks held across services for the duration → latency, deadlock risk
  - Not partition-tolerant
  - In practice: avoid for service-to-service coordination
```

### 6.2 Saga Pattern _(both axes)_

The practical alternative to distributed transactions. A saga is a sequence of local transactions, each with a compensating action.

**The core idea:** Since you can't wrap multiple services in one transaction, you break the work into steps. Each step is a local transaction that commits independently. If step 3 fails, you can't "rollback" steps 1 and 2 (they already committed). Instead, you run **compensating actions** — new transactions that semantically undo the effect. A compensating action for "charge the customer" is "refund the customer." It's not a database rollback — it's a new forward action that reverses the business effect.

**Choreography Saga (event-driven):**

```
Order Service → [OrderCreated]
  → Payment Service → [PaymentCharged]
    → Ledger Service → [LedgerEntryCreated]
      → Notification Service → [NotificationSent]

Compensation on failure (reverse order):
  LedgerFailed → RefundPayment → CancelOrder → NotifyUser("failed")
```

Each service listens for events and acts. Each service knows its own undo action.

**Orchestration Saga (coordinator-driven):**

For a complex payment flow, I'd use an orchestration saga. One service — the payment orchestrator — owns the entire workflow. It calls each step in order, tracks which steps succeeded, and knows exactly which compensations to run if something fails. With choreography across 5+ services, debugging becomes very hard — you're chasing events across logs with no single place that shows the full picture. Orchestration gives you one place to inspect, retry, and reason about the flow

```
Payment Orchestrator:
  Step 1: Validate order         → failure: done (nothing to undo)
  Step 2: Reserve funds (hold)   → failure: release hold
  Step 3: Debit sender           → failure: reverse debit
  Step 4: Credit receiver        → failure: reverse credit + reverse debit
  Step 5: Confirm to user        → failure: compensate steps 2-4
```

Central orchestrator manages the workflow. Easier to reason about and debug.

| Aspect     | Choreography              | Orchestration                     |
| ---------- | ------------------------- | --------------------------------- |
| Coupling   | Loose                     | Tighter (to orchestrator)         |
| Visibility | Scattered across services | Single place to inspect           |
| Debugging  | Follow events across logs | One service has full picture      |
| Best for   | Simple flows (2-4 steps)  | Complex flows (5+ steps)          |
| Fintech    | Notifications, analytics  | **Payment processing, transfers** |

### 6.3 Event-Driven Architecture _(both axes)_

```
Payment Service → Kafka → Fraud Service
                       → Ledger Service
                       → Notification Service
                       → Analytics Service
                       → Compliance Service
```

**Benefits (microservices axis):**

- Loose coupling — new consumer requires zero changes to producer
- Independent scaling — each consumer processes at its own pace
- Independent deployment — add/remove consumers without touching producer

**Challenges (distributed systems axis):**

- Eventual consistency — read model lags behind writes
- Event ordering — must partition by account_id for per-account ordering
- Duplicate delivery — events may arrive more than once → idempotent consumers
- Lost events — consumer crashes before ACK → at-least-once delivery, handle dupes

### 6.4 Ordering Guarantees _(distributed systems)_

**Global ordering is impossible (or impractically expensive) in a distributed system.**

```
Kafka partitioning:
  Topic: "payments" with 12 partitions
  Key: account_id
  Guarantee: all events for the same account_id go to the same partition
  Within a partition: events are strictly ordered (FIFO)
  Across partitions: no ordering guarantee

This is enough for fintech:
  - All of Alice's transactions are ordered (same partition)
  - Alice's and Bob's transactions are not ordered relative to each other (different partitions)
  - That's fine — they don't need to be
```

### 6.5 Exactly-Once Delivery _(distributed systems)_

**In theory:** Exactly-once is impossible in a distributed system.

**In practice:** Exactly-once _processing_ is achievable via idempotent consumers.

```
At-least-once delivery (Kafka default):
  Producer sends event → Broker ACKs → Consumer processes → Consumer ACKs
  If consumer crashes before ACK → broker redelivers → consumer processes AGAIN

Idempotent consumer:
  Consumer checks: "Have I already processed event with this ID?"
  If yes → skip
  If no → process + record the ID
  Result: effectively exactly-once processing
```

### 6.6 CQRS _(microservices pattern, distributed systems consequence)_

CQRS (Command Query Responsibility Segregation) separates the command model (handles writes/mutations) from the query model (handles reads). They can use different data stores, different schemas, and scale independently. The read model is kept in sync — either synchronously or via eventual consistency (events, CDC, etc.).

```
            ┌─── Command ──→ Write Model ──→ PostgreSQL (normalized, ACID)
            │                                    │
Client ─────┤                              Event published to Kafka
            │                                    │
            └─── Query ───→ Read Model  ←── Materialized view / ElasticSearch
```

**The consequence (distributed systems):** The read model is eventually consistent. It lags behind the write model by the time it takes for the event to be consumed and the read model to be updated.

**Fintech application:**

- Write: normalized ledger in PostgreSQL, `SELECT FOR UPDATE`, strict ACID
- Read: denormalized views for "show me my last 50 transactions with merchant names, categories, running balance"
- Lag: 100ms-5s depending on Kafka consumer lag
- Acceptable: for transaction history display
- Not acceptable: for balance check before approving a payment → read from write DB

**Phase 6 summary:** Without shared transactions, you coordinate through sagas (choreography or orchestration), communicate through events (Kafka), and accept eventual consistency. Every event can be duplicated, lost, or reordered — design for it with idempotent consumers and per-key partitioning.

---

## Phase 7: Resilience

To build a resilient distributed system we need to understand its failure modes.

| Failure           | Description                  | Fintech Impact                  | Mitigation                     |
| ----------------- | ---------------------------- | ------------------------------- | ------------------------------ |
| Crash failure     | Process dies                 | In-flight payment lost          | Restart, WAL, redundancy       |
| Omission failure  | Message lost                 | Payment debited but credit lost | Retries, ACKs, idempotency     |
| Timing failure    | Response too slow            | Timeout → retry → duplicate     | Timeouts + idempotency         |
| Byzantine failure | Arbitrary/malicious behavior | Fraudulent transactions         | Input validation, fraud checks |

**The worst fintech failure:** Debit succeeds, credit is lost (omission between services). This is why idempotency + saga compensation + reconciliation form a triple safety net.

### 7.1 Circuit Breaker _(both axes)_

```
States:
  CLOSED → (failures exceed threshold) → OPEN
  OPEN → (timeout expires) → HALF-OPEN
  HALF-OPEN → (test request succeeds) → CLOSED
  HALF-OPEN → (test request fails) → OPEN

Example: Payment Service → Fraud Service
  - 5 failures in 30 seconds → circuit opens
  - For 60 seconds, all fraud checks return fallback (BLOCK the payment, don't skip)
  - After 60s, send one test request
  - If it succeeds → circuit closes, resume normal operation
```

**Critical fintech rule:** When a circuit opens to the fraud service, you **block payments**, not skip fraud checks. Degrading fraud = allowing fraud.

**Why the circuit breaker exists — the cascade failure:**

Without a circuit breaker, if Fraud Service is down, every Payment Service request hangs for the full timeout (e.g., 10 seconds) waiting for Fraud Service to respond. Payment Service's thread pool fills up with waiting threads. Now Payment Service can't handle any requests — not even ones that don't need fraud checks. The failure cascaded from Fraud Service to Payment Service. Circuit breaker short-circuits this: after 5 failures, stop calling Fraud Service entirely (fail immediately instead of waiting), freeing threads to handle other work.

```
Without circuit breaker:
  Fraud Service down → Payment Service threads waiting → Payment Service unresponsive
  → API Gateway times out → User sees "something went wrong" on everything

With circuit breaker:
  Fraud Service down → Circuit opens → Payment Service immediately returns "fraud check unavailable"
  → Payment blocked but Payment Service stays responsive for other operations
```

### 7.2 Bulkhead _(both axes)_

Bulkhead pattern means isolating components so a failure in one doesn't cascade to others.

```
Without bulkhead:
  Shared thread pool (100 threads)
  Fraud Service is slow → all 100 threads waiting on Fraud
  Payment Service can't process anything → total outage

With bulkhead:
  Fraud pool: 20 threads
  Payment pool: 40 threads
  Ledger pool: 40 threads
  Fraud Service is slow → 20 threads blocked, 80 still working
  Payment processing continues for non-fraud paths
```

**Apply at every level:**

- Separate thread pools per external dependency
- Separate connection pools per database
- Separate Kafka consumer groups per domain
- Rate limit internal service-to-service calls

### 7.3 Graceful Degradation _(both axes)_

**What you CAN degrade in fintech:**

- Notifications (delay SMS/email/push)
- Analytics and reporting dashboards
- Non-essential UI features (spending insights, badges)
- Historical transaction search (serve cached results)
- Exchange rate precision (serve slightly stale rates)

**What you CANNOT degrade:**

- Payment correctness (never approximate a balance)
- Fraud checks (block the payment if fraud service is down)
- Ledger writes (queue if DB is down, never drop)
- Authentication and authorization

### 7.4 Health Checks _(microservices)_

- **Liveness:** Is the process alive? (restart if not)
- **Readiness:** Can the process serve traffic? (remove from LB if not)
- **Startup:** Has the process finished initializing? (wait before checking liveness)

**Deep health checks for fintech:**

```
/health/live   → process is running
/health/ready  → can reach DB, Redis, Kafka, payment provider
/health/deep   → all dependencies healthy, consumer lag < threshold
```

### 7.5 Dead-Letter Queues _(both axes)_

```
Normal flow:
  [Kafka topic: payments] → Consumer → Process → ACK

Consumer fails 3 times:
  [Kafka topic: payments] → Consumer → Fail → Fail → Fail
    → [DLQ: payments-dead-letter]
    → Alert operations team
    → Manual review or scheduled retry with backoff
```

**In fintech:** A dead-letter queue is not a trash bin. It's an inbox for the operations team. Every message in the DLQ represents a payment that might need manual intervention.

### 7.6 Service Mesh _(microservices)_

Service Mesh is a dedicated layer that handles service-to-service communication, pulling all networking concerns out of your application code.

```
Service A → [Sidecar Proxy] ←→ [Sidecar Proxy] → Service B

The sidecar handles:
  - mTLS (encryption + mutual authentication)
  - Retries with backoff
  - Circuit breaking
  - Load balancing
  - Observability (metrics, traces)

Service code doesn't handle any of this — it just makes a plain HTTP call to localhost.
Tools: Istio, Linkerd, Consul Connect
```

**Why service mesh in fintech:** Moves resilience patterns (retries, circuit breakers, mTLS) out of application code into infrastructure. Consistent behavior across all services regardless of language or framework.

**How the sidecar pattern actually works:**

Instead of Payment Service importing a retry library, an HTTP client with circuit breaker, and TLS certificate management — a sidecar proxy (Envoy) runs alongside it in the same pod/container. Payment Service makes a plain `http://localhost:8080` call. The sidecar intercepts it, adds mTLS, applies retry policy, checks circuit breaker state, collects latency metrics, and forwards to the destination's sidecar. The application code has zero networking logic — it just makes simple HTTP calls.

```
Pod A:                                    Pod B:
  [Payment Service] → [Envoy sidecar] ──network──→ [Envoy sidecar] → [Fraud Service]
       (plain HTTP)    (mTLS, retry,                (decrypt, route)   (plain HTTP)
                        circuit break)
```

The control plane (Istio) configures all sidecars: "retry 3 times for Fraud Service", "circuit break after 5 failures", "require mTLS for all traffic." You change policies centrally without touching any service code.

**Phase 7 summary:** Assume everything is partially broken. Circuit breakers prevent cascade failures. Bulkheads isolate blast radius. Graceful degradation keeps the money path running while non-critical features degrade. Dead-letter queues catch what can't be processed. Service mesh makes resilience consistent across all services.

---

## Phase 8: Consensus & Coordination

**When multiple nodes need to agree on something — who is the leader, is this lock held, what order did events happen.**

### 8.1 The Consensus Problem _(distributed systems)_

```
Three nodes need to agree on a value.
  - Any node can propose a value
  - Network messages can be delayed, lost, or reordered
  - Nodes can crash at any time

FLP Impossibility: In an asynchronous system, no consensus algorithm
can guarantee termination if even one node can crash.

In practice: Use timeouts to detect failures (technically synchronous assumption).
Raft, Paxos, ZAB all work in practice with this assumption.
```

### 8.2 Raft _(distributed systems)_

```
Roles: Leader, Follower, Candidate

Normal operation:
  1. Client sends write to Leader
  2. Leader appends to its log
  3. Leader replicates to Followers
  4. Majority ACK → Leader commits
  5. Leader responds to client

Leader failure:
  1. Followers stop receiving heartbeats
  2. Random timeout (150-300ms) triggers election
  3. Candidate requests votes
  4. Majority vote → new Leader
  5. New Leader serves clients

Used in: etcd, CockroachDB, TiKV, Consul
```

**Why Raft works intuitively:**

The key insight is **majority quorum**. In a 5-node cluster, 3 nodes must agree. If the network splits into a group of 3 and a group of 2, only the group of 3 can elect a leader and accept writes. The group of 2 can't reach majority, so it goes read-only. This guarantees at most one leader exists at any time — no split-brain.

**Why randomized timeouts matter:** If all followers timed out simultaneously and all became candidates, they'd split the vote (each votes for itself). Randomized timeouts (150-300ms) make it likely that one follower times out first, requests votes before others, and wins the election cleanly.

**Log replication guarantees:** A write is only committed when the leader has replicated it to a majority. If the leader crashes, the new leader (elected from the majority) is guaranteed to have all committed entries. Uncommitted entries on the crashed leader are discarded — they were never confirmed to the client.

**Fintech use cases:**

- Leader election for payment processors (one node processes a given account's payments)
- Distributed configuration store (feature flags, rate limits via etcd/Consul)
- Metadata coordination (which shard owns which account range)

### 8.3 Distributed Locking _(distributed systems)_

**Why needed:** Prevent two nodes from processing the same payment. Ensure only one instance updates a balance.

**Redis-based (Redlock):**

```
1. Acquire lock on N/2+1 Redis instances with same key + TTL
2. If majority acquired within timeout → lock held
3. Do work
4. Release: delete key on all instances

Example: "lock:payment:pay_abc" TTL=30s
```

- Fast, practical for most use cases
- Risk: not a consensus system — rare failure modes can violate lock safety
- Mitigation: fencing tokens

**Why Redlock can fail:**

```
1. Client A acquires lock on 3/5 Redis nodes (majority)
2. Client A pauses (long GC pause, or suspended by OS)
3. Lock TTL expires on all nodes
4. Client B acquires lock on 3/5 Redis nodes (majority)
5. Client A wakes up — thinks it still holds the lock
6. Both A and B believe they hold the lock simultaneously
```

**Fencing tokens solve this:** Each lock acquisition returns a monotonically increasing token (e.g., 42, then 43). The backend (database, service) records the highest token it's seen. If Client A sends token 42 after Client B sent token 43, the backend rejects A's request because a higher token has already been seen.

```
Client A: lock acquired, token=42 → pauses
Client B: lock acquired, token=43 → writes to DB with token=43
Client A: wakes up → writes to DB with token=42 → REJECTED (43 > 42)
```

**PostgreSQL advisory locks:**

```sql
SELECT pg_advisory_lock(hashtext('payment:pay_abc'));
-- do work
SELECT pg_advisory_unlock(hashtext('payment:pay_abc'));
```

- Backed by ACID — no split-brain
- Lock auto-released if connection drops
- Slower than Redis but safer for critical paths

**etcd / ZooKeeper (consensus-backed):**

- Strongest guarantees — backed by Raft/ZAB
- Higher latency but correct under network partitions
- Use when correctness > speed (leader election, payment coordination)

| Mechanism       | Speed  | Safety                | Best For                          |
| --------------- | ------ | --------------------- | --------------------------------- |
| Redis (Redlock) | Fast   | Good (not perfect)    | Rate limiting, dedup, soft locks  |
| PostgreSQL      | Medium | Strong (ACID)         | Balance locks, payment processing |
| etcd/ZooKeeper  | Slower | Strongest (consensus) | Leader election, coordination     |

### 8.4 Clocks & Ordering _(distributed systems)_

**Physical clocks lie:**

```
Server A clock: 10:00:00.003
Server B clock: 10:00:00.001
Server A's event happened AFTER Server B's, but timestamp says BEFORE.
NTP sync accuracy: ~1-10ms. Not enough for transaction ordering.
```

**Logical clocks (Lamport):**

```
Each node has a counter. On every event, increment.
On every message sent, attach counter. On receive, max(local, received) + 1.
Gives total order, but no real-time correspondence.
```

**Lamport clock example:**

```
Node A (counter=0)              Node B (counter=0)
  event → counter=1
  send msg to B (attach 1) ──→ receive msg, max(0,1)+1 = counter=2
                                event → counter=3
  receive msg (attach 3)  ←── send msg to A (attach 3)
  max(1,3)+1 = counter=4

Now we know: A's event(1) → B's event(2) → B's event(3) → A's event(4)
Limitation: if A has counter=5 and B has counter=5, we can't tell
which happened first — Lamport clocks can't detect concurrency.
```

**Vector clocks:**

Each node maintains a counter for every node in the system, not just itself.

```
Node A: [A=3, B=0, C=0]  — "I've done 3 things, haven't heard from B or C"
Node B: [A=2, B=4, C=1]  — "I've done 4 things, last heard from A at 2, from C at 1"

Comparison rules:
  [A=3, B=0] vs [A=2, B=4]
  A>2 but B<4 → neither dominates → these events are CONCURRENT

  [A=3, B=2] vs [A=3, B=4]
  A=3, B<4 → second dominates → second happened AFTER first

This is the key advantage over Lamport: vector clocks detect concurrency.
When two events are concurrent, you know a conflict exists and must be resolved.
Used in: Dynamo, Riak for conflict detection in eventually consistent systems.
```

**For fintech:**

- Don't use wall-clock timestamps for ordering transactions
- Use database sequence numbers (auto-increment on single leader) or Snowflake IDs
- Timestamps for display and audit — accept ms-level imprecision
- Cross-region ordering → need consensus (Raft) or bounded clocks (Spanner-style)

### 8.5 Distributed Configuration _(microservices)_

```
etcd / Consul / ZooKeeper as config store:
  - Feature flags: { "enable_instant_payments": true }
  - Rate limits: { "max_payments_per_user_per_hour": 100 }
  - Circuit breaker thresholds: { "fraud_service_failure_threshold": 5 }

Services watch for changes → update behavior without redeployment
```

**Why this matters for fintech:** Disable a payment method instantly (fraud detected), change rate limits during an incident, toggle features for canary testing — all without deploying code.

### 8.6 Conflict Resolution _(distributed systems)_

| Strategy              | How                      | Fintech Safety                        |
| --------------------- | ------------------------ | ------------------------------------- |
| Last-Write-Wins (LWW) | Timestamp comparison     | **Dangerous** — silently loses writes |
| Vector Clocks         | Causal ordering          | Surfaces conflicts, app must resolve  |
| CRDTs                 | Mathematically mergeable | Safe for counters/sets, limited types |
| Application-level     | Custom merge logic       | Must be carefully designed            |

**Fintech stance:** Avoid conflicts entirely for financial data. Single-leader writes for the ledger. If two things could conflict, serialize them through one writer. Conflicts on money = money created or destroyed.

**Phase 8 summary:** When nodes need to agree, use consensus (Raft via etcd/Consul). For locking, choose the mechanism that matches the safety requirement — Redis for soft locks, PostgreSQL for payment locks, etcd for leader election. Don't trust clocks for ordering — use sequence numbers. Avoid conflicts on financial data by design.

---

## Phase 9: The Money Path

**Apply everything from Phases 1-8 to financial systems.**

### 9.1 Double-Entry Ledger

The foundation of every financial system. Every movement of money is two entries summing to zero.

```
Transfer $100 from Alice to Bob:

  | entry_id | transaction_id | account_id | direction | amount | currency | created_at          |
  |----------|----------------|------------|-----------|--------|----------|---------------------|
  | 1        | txn_abc        | alice_123  | DEBIT     | 10000  | USD      | 2026-04-17 10:00:00 |
  | 2        | txn_abc        | bob_456    | CREDIT    | 10000  | USD      | 2026-04-17 10:00:00 |

Invariant: SUM(credits) - SUM(debits) = 0 for every transaction
```

**Why double-entry:**

- Self-auditing — any imbalance = bug, immediately detectable
- Regulatory requirement for licensed financial institutions
- Complete money trail — every cent traceable
- Append-only — entries are immutable, natural fit for event sourcing

**Materialized balance pattern:**

```sql
BEGIN;
  SELECT balance FROM account_balances WHERE account_id = 'alice' FOR UPDATE;
  -- check sufficient funds, ROLLBACK if insufficient

  INSERT INTO ledger_entries (transaction_id, account_id, direction, amount, currency)
  VALUES ('txn_abc', 'alice', 'DEBIT', 10000, 'USD');
  INSERT INTO ledger_entries (transaction_id, account_id, direction, amount, currency)
  VALUES ('txn_abc', 'bob',   'CREDIT', 10000, 'USD');

  UPDATE account_balances SET balance = balance - 10000 WHERE account_id = 'alice';
  UPDATE account_balances SET balance = balance + 10000 WHERE account_id = 'bob';
COMMIT;
```

**Schema design rules:**

- `BIGINT` for amounts (smallest unit — cents, pence). Never `FLOAT` or `DOUBLE`
- Always store currency alongside amount
- `TIMESTAMPTZ` (with timezone), never `TIMESTAMP`
- Ledger entries are append-only — never update or delete

### 9.2 Idempotency in Payments (End-to-End)

```
Client → API Gateway → Payment Service → Fraud → Ledger → Provider → Notification

Idempotency at every hop:
  1. Client → API: Idempotency-Key header
  2. API → Payment Service: transaction_id dedup
  3. Payment Service → Ledger: UNIQUE constraint on transaction_id
  4. Payment Service → Provider: pass idempotency key to Stripe/Visa
  5. Kafka events: consumer dedup by event_id
```

### 9.3 Saga for Payment Flows

```
Orchestration Saga (preferred for payments):

Payment Orchestrator:
  Step 1: Validate (check limits, KYC)     → fail: done
  Step 2: Fraud check                       → fail: done
  Step 3: Reserve funds (hold on balance)   → fail: done
  Step 4: Call external provider            → fail: release hold
  Step 5: Debit sender                      → fail: reverse debit, release hold
  Step 6: Credit receiver                   → fail: reverse credit + debit, release hold
  Step 7: Confirm + notify                  → fail: compensate steps 3-6

Each step is a local transaction in its own service.
Each step has a compensating action.
The orchestrator tracks which steps completed and runs compensations on failure.
```

### 9.4 Event Sourcing

Event Sourcing is a pattern where you store every state change as an immutable event rather than overwriting the current state. The data is stored in a dedicated event store — a database optimized for append-only, ordered event streams.

An events table with stream_id, event_type, payload (JSONB), version, created_at. Append-only by convention

```
Instead of:  { account: "alice", balance: 50000 }

Store events:
  1. AccountOpened(id=alice, balance=100000, currency=USD)
  2. PaymentSent(id=alice, amount=20000, to=bob)
  3. PaymentReceived(id=alice, amount=5000, from=carol)
  4. FeeCharged(id=alice, amount=500, reason=fx_conversion)
  5. PaymentSent(id=alice, amount=34500, to=dave)

Current balance = replay(events) → 50000
```

**Why it matters for fintech:**

- Regulatory compliance — complete audit trail
- Temporal queries — "balance at 3:42 PM on March 5th"
- Debugging — replay events to reproduce any state
- Reprocessing — fix logic, replay events through corrected code

**Snapshot optimization:**

Replaying millions of events per read is impractical. Periodically snapshot materialized state.

```
Event log for Alice (100,000 events over 3 years):
  Event 1:      AccountOpened(balance=0)
  Event 2:      Deposit(amount=50000)
  ...
  Event 50,000: PaymentSent(amount=1500)   ← snapshot taken here: { balance: 234000 }
  ...
  Event 100,000: Deposit(amount=3000)

To get current balance:
  Without snapshot: replay all 100,000 events → slow
  With snapshot: load snapshot at event 50,000 → replay events 50,001-100,000 → fast
```

Snapshots are like database checkpoints (Phase 1) — you trade storage for read speed. Take them every N events or on a schedule (daily).

**Challenges:**

- Event schema evolution — events are immutable but their shape changes (use versioning, upcasting)
- Storage growth — snapshots + cold storage tiering
- Ordering — per-account ordering via Kafka partition key

### 9.5 Reconciliation

The safety net. Reconciliation verifies internal records match external reality.

| Type          | Compares                                    | Frequency          |
| ------------- | ------------------------------------------- | ------------------ |
| Internal      | Ledger debits vs credits (must net to zero) | Real-time / hourly |
| External      | Internal ledger vs bank/provider statements | Daily / batch      |
| Cross-service | Payment service vs ledger service records   | Hourly             |
| Balance       | Materialized balance vs SUM(ledger entries) | Hourly / daily     |

```
Flow:
  1. Export internal records for period T
  2. Receive external statement for period T
  3. Match by: amount, currency, reference ID, timestamp (with tolerance)
  4. Flag unmatched:
     - Internal only → payment may have failed silently
     - External only → missed webhook, lost event
     - Amount mismatch → partial settlement, FX difference
  5. Alert operations team for discrepancies
  6. Auto-resolve known patterns (timing differences < 5 min)
```

**Interview tip:** Mentioning reconciliation unprompted shows you understand that distributed systems _will_ drift and you need detection + correction mechanisms.

### 9.6 SQL vs NoSQL — Where Each Fits

**SQL (PostgreSQL) for the money path:**

- Ledger, balances, transactions, payment records
- ACID transactions, strong consistency, foreign keys, constraints
- `SELECT FOR UPDATE` for pessimistic locking

**NoSQL where it fits (not on the money path):**

| Type        | Fintech Use Case                          | Tool        |
| ----------- | ----------------------------------------- | ----------- |
| Key-Value   | Session store, rate-limit counters, cache | Redis       |
| Document    | User profiles, KYC documents, configs     | MongoDB     |
| Wide-Column | Transaction event logs, audit trails      | Cassandra   |
| Time-Series | Fraud metrics, FX rates, monitoring       | TimescaleDB |
| Graph       | Fraud ring detection, AML graphs          | Neo4j       |

**Redis in fintech:**

- Rate limiting: `INCR` + `EXPIRE`
- Idempotency store: `SET key value NX EX 86400`
- Session management: fast lookup with TTL
- Distributed locking: Redlock
- **NOT for:** balances, ledger entries, anything that must survive restart

**Phase 9 summary:** The money path brings together every concept: ACID transactions (Phase 1), replication for durability (Phase 2), sharding by account (Phase 3), idempotency across services (Phase 4), event sourcing for audit (Phase 5), sagas for multi-step payments (Phase 6), circuit breakers on providers (Phase 7), locking on balances (Phase 8). Reconciliation is the final safety net that catches everything else.

---

## Phase 10: Observability & Security

### 10.1 Three Pillars of Observability

| Pillar      | What                              | Tools                         |
| ----------- | --------------------------------- | ----------------------------- |
| **Logs**    | Discrete events, structured JSON  | ELK Stack, Loki, CloudWatch   |
| **Metrics** | Aggregated numerical measurements | Prometheus, Grafana, Datadog  |
| **Traces**  | Request flow across services      | Jaeger, Zipkin, OpenTelemetry |

**Fintech logging rules:**

- Structured JSON (machine-parseable)
- Include: trace_id, user_id, transaction_id, service_name
- **NEVER log:** card numbers, passwords, full account numbers, PII
- Retain per regulatory requirements (often 5-7 years)

### 10.2 Key Metrics

**RED Method (request-driven):**

- **R**ate — requests per second
- **E**rrors — failed requests per second
- **D**uration — latency (p50, p95, p99)

**USE Method (infrastructure):**

- **U**tilization — % resource busy
- **S**aturation — work queued/waiting
- **E**rrors — error count

**Fintech-specific:**

| Metric                          | Why                                   |
| ------------------------------- | ------------------------------------- |
| Payment success rate            | Core business health                  |
| Payment latency (p99)           | User experience, SLA                  |
| Kafka consumer lag              | Event processing timeliness           |
| Fraud detection latency         | Within 100ms budget?                  |
| Reconciliation discrepancy rate | Systems drifting?                     |
| Provider-specific error rates   | Is Visa failing more than Mastercard? |
| Balance cache hit rate          | Hot path performance                  |

### 10.3 Distributed Tracing

```
Payment request → API Gateway (trace_id=abc, span_id=1)
  → Payment Service (span_id=2, parent=1)
    → Fraud Service (span_id=3, parent=2) [45ms]
    → Ledger Service (span_id=4, parent=2) [120ms]
      → PostgreSQL (span_id=5, parent=4) [15ms]
    → Notification Service (span_id=6, parent=2) [async]
```

**Fintech requirement:** Every payment must have a trace_id across all services. Ability to search "show me the full trace for payment pay_abc" — critical for debugging and support.

**Sampling:** 100% of failed/slow payments, 10% of successful ones.

### 10.4 SLIs, SLOs, SLAs

| Term            | Definition            | Fintech Example                    |
| --------------- | --------------------- | ---------------------------------- |
| SLI (Indicator) | Measurable metric     | 99.5% of payments complete < 500ms |
| SLO (Objective) | Target for SLI        | p99 payment latency < 2s           |
| SLA (Agreement) | Contract with penalty | 99.95% uptime or compensation      |

**Availability Nines:**

| Nines             | Downtime/year | Fintech Context                     |
| ----------------- | ------------- | ----------------------------------- |
| 99% (two 9s)      | 3.65 days     | Unacceptable for payments           |
| 99.9% (three 9s)  | 8.76 hours    | Minimum for non-critical services   |
| 99.99% (four 9s)  | 52.6 minutes  | Target for payment processing       |
| 99.999% (five 9s) | 5.26 minutes  | Aspirational, requires multi-region |

### 10.5 Alerting

| Level    | Example                    | Response                     |
| -------- | -------------------------- | ---------------------------- |
| Critical | Payment success rate < 95% | Page on-call immediately     |
| High     | Kafka lag > 10K messages   | Investigate within 15 min    |
| Medium   | p99 latency > 2x normal    | Investigate within 1 hour    |
| Low      | Disk usage > 80%           | Ticket for next business day |

### 10.6 Authentication & Authorization

| Pattern   | How                             | Fintech Use                      |
| --------- | ------------------------------- | -------------------------------- |
| JWT       | Stateless signed token          | Mobile app → API                 |
| OAuth 2.0 | Delegated authorization         | Open Banking, third-party access |
| API Keys  | Static key per client           | Partner/merchant API             |
| mTLS      | Mutual certificate verification | Service-to-service (zero trust)  |

**JWT in fintech:**

- Short-lived access tokens (5-15 min) + refresh tokens
- Sign with RS256 (asymmetric) — services verify without signing key
- Never store sensitive data in JWT (base64, not encrypted)
- Token revocation: short TTLs + Redis blacklist for force-logout

**OAuth 2.0 flows:**

| Flow                      | Use Case                         |
| ------------------------- | -------------------------------- |
| Authorization Code + PKCE | Mobile/SPA (Revolut app)         |
| Client Credentials        | Machine-to-machine, partner APIs |

### 10.7 Data Security & Compliance

**Encryption:**

- At rest: AES-256, key rotation via KMS
- In transit: TLS 1.3 for all communication
- Field-level: encrypt PII fields independently (SSN, passport)

**PCI-DSS:**

- Tokenize card numbers — never store raw PAN
- Limit systems touching cardholder data → reduce PCI scope
- Regular security audits, penetration testing

**Data residency (GDPR):**

- EU user data stored and processed in EU
- Drives geographic sharding decisions
- Right to be forgotten — must purge user data across all systems

**Secrets management:**

- HashiCorp Vault, AWS Secrets Manager
- Rotate secrets regularly
- Principle of least privilege per service

**Phase 10 summary:** Observability tells you when things are broken. Security ensures they're not broken by attackers. In fintech, never log PII, trace every payment end-to-end, alert on business metrics (not just infrastructure), encrypt everything, and tokenize card data.

---

## Phase 11: Practice

### 11.1 Classic Problems (Revolut-Weighted)

**Tier 1 — Expect these:**

| Problem                 | Key Concepts                                                           |
| ----------------------- | ---------------------------------------------------------------------- |
| **Payment System**      | Double-entry ledger, idempotency, saga, reconciliation, fraud hooks    |
| **Rate Limiter**        | Token bucket, sliding window, distributed (Redis), per-user/IP/API key |
| **Notification System** | Multi-channel (push/SMS/email), priority queues, rate limiting, retry  |
| **Key-Value Store**     | Consistent hashing, replication, conflict resolution, partitioning     |

**Tier 2 — Likely:**

| Problem                      | Key Concepts                                                      |
| ---------------------------- | ----------------------------------------------------------------- |
| **Chat System**              | WebSocket, presence, ordering, fanout, offline storage            |
| **Fraud Detection Pipeline** | Stream processing, ML serving, rules engine, real-time + batch    |
| **Currency Exchange**        | FX rate feeds, order book, spread, hedging, rate caching          |
| **E-commerce Checkout**      | Cart, inventory reservation, payment saga, distributed order flow |

**Tier 3 — Possible:**

| Problem                       | Key Concepts                                          |
| ----------------------------- | ----------------------------------------------------- |
| **Distributed Message Queue** | Partitioning, ordering, consumer groups, exactly-once |
| **Distributed Cache**         | Consistent hashing, eviction, coherence, hot keys     |
| **Stock Trading Platform**    | Order matching, FIFO, low latency, sequencer          |
| **Metrics / Monitoring**      | Time-series DB, aggregation, alerting                 |

### 11.2 The 35-Minute Framework

```
[0-5 min]   Requirements & Scope
  - Clarifying questions (see checklist below)
  - 3-5 functional requirements
  - Non-functional: scale, latency, consistency, availability
  - Agree on scope — don't design everything

[5-10 min]  Estimation & API Design
  - Back-of-envelope: QPS, storage, bandwidth (show the math)
  - Key API endpoints
  - Data model sketch

[10-25 min] High-Level Design + Deep Dive
  - Architecture diagram (clients, LB, services, DBs, caches, queues)
  - Walk through main data flow end-to-end
  - Deep dive 2-3 critical components
  - Database choice, schema, indexing, caching, queuing

[25-30 min] Bottlenecks & Trade-offs
  - Single points of failure
  - Scaling approach
  - Explicit trade-offs: consistency vs availability, latency vs throughput

[30-35 min] Failure Scenarios & Extensions
  - "What if X fails?"
  - Hot spots, thundering herds
  - Extensions the interviewer hints at
  - Monitoring and alerting
```

### 11.3 Clarifying Questions Checklist

**Users & Scale:**

- DAU/MAU?
- Read-heavy or write-heavy?
- Geographic distribution?
- Peak traffic patterns?

**Data:**

- What data, how long, how big?
- Access patterns (recent vs historical)?
- Regulatory retention?

**Consistency & Correctness:**

- Strong or eventual?
- Durability requirements?
- Idempotency required?
- Financial correctness?

**Performance:**

- Latency targets (p50, p99)?
- Throughput (QPS/TPS)?
- Real-time requirements?

**Compliance (fintech):**

- PCI-DSS scope?
- Data residency?
- Audit trail requirements?

### 11.4 How to Talk About Your Design

**Instead of:** "We can use a database"
**Say:** "PostgreSQL with a B-tree composite index on (account_id, created_at). BIGINT for amounts in cents. Serializable isolation or SELECT FOR UPDATE on balance rows to prevent double-spending."

**Instead of:** "We'll make it scale"
**Say:** "At 300 TPS, single Postgres handles this. At 3,000 TPS, add read replicas for reporting and shard writes by account_id with consistent hashing. Cross-shard transfers use orchestration saga."

**Instead of:** "We'll add a cache"
**Say:** "Cache-aside with Redis for balances. 5-second TTL, invalidated on write via Kafka event. ~95% hit rate. On miss, read from primary, not replica, to avoid stale balance."

**Instead of:** "We'll handle failures"
**Say:** "Exponential backoff with jitter, max 3 retries. Circuit breaker opens after 5 failures in 30s, half-opens at 60s. Exhausted retries go to dead-letter queue for ops review. All retries idempotent via idempotency key."

### 11.5 Common Mistakes

| Mistake                       | Fix                                            |
| ----------------------------- | ---------------------------------------------- |
| Jumping to solution           | Ask requirements first                         |
| Over-engineering from start   | Start simple, scale when numbers demand it     |
| Ignoring non-functional reqs  | Always discuss scale, latency, consistency     |
| No trade-off discussion       | Every choice has a cost — state it             |
| Monologue without checking in | "Does this make sense so far?"                 |
| Vague handwaving              | Be specific: "Redis LRU, 10GB, TTL 5s"         |
| Forgetting failure modes      | "What if this is down?" — always address       |
| Skipping monitoring           | "How do we know it's broken?" — always address |

### 11.6 Problem Deep-Dive Template

```
1.  Functional requirements (3-5 core features)
2.  Non-functional requirements (scale, latency, consistency)
3.  Estimation (QPS, storage, bandwidth)
4.  API design (endpoints, idempotency, pagination)
5.  Data model (schema, DB choice, indexes)
6.  High-level architecture (component diagram, data flow)
7.  Deep dive (2-3 critical components)
8.  Trade-offs (decisions + alternatives)
9.  Failure scenarios (what breaks, detect, recover)
10. Monitoring (metrics, alerts, SLOs)
```

---

## Reading List

### Books (Priority Order)

1. **Designing Data-Intensive Applications** — Martin Kleppmann
   - Chapters 5-9 cover 80% of what you need: replication, partitioning, transactions, consistency, streaming.
2. **System Design Interview (Vol 1 & 2)** — Alex Xu
   - Problem-focused. Vol 2 covers payment systems.
3. **Understanding Distributed Systems** — Roberto Vitillo
   - Concise, practical. Good for quick review.
4. **Database Internals** — Alex Petrov
   - B-trees, LSM trees, distributed DB internals.
5. **Building Microservices** — Sam Newman
   - Service decomposition, communication patterns, deployment.

### Papers

- **Dynamo** (Amazon) — Eventually consistent KV store
- **Kafka** (LinkedIn) — Distributed commit log
- **Raft** — Understandable consensus (read this one, it's short)
- **Spanner** (Google) — Globally consistent DB with TrueTime
- **TAO** (Facebook) — Distributed graph store

### Online Resources

- System Design Primer (GitHub)
- ByteByteGo (Alex Xu)
- Grokking System Design
- Engineering Blogs: Revolut, Stripe, Monzo, Square, Nubank

### Fintech-Specific

- Revolut Engineering Blog
- Stripe's idempotency key design
- Monzo's ledger architecture
- Martin Fowler on Event Sourcing
- PCI-DSS Quick Reference Guide

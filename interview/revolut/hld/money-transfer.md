# HLD — Money Transfer / Ledger

> Layer 3: a real payments ledger. This is Revolut's actual product surface — they will probe deepest here.

## 1. Requirements

**Functional**

- Transfer funds between two accounts atomically
- Idempotent — same `transfer_id` retried = same outcome
- Full audit log: every state change recorded, never deleted
- Reversal / refund support
- Statement / history queries (last 90 days hot, older cold)
- Holds / pending balances (auth → capture pattern, like card payments)

**Non-functional**

- 5k transfer/s sustained, 50k peak (Black Friday, payday)
- p99 transfer latency < 200 ms
- 99.99% availability for the transfer API
- **Zero tolerance for lost money** — RPO=0, RTO=minutes
- Strong consistency (no eventual consistency on balances)
- Regulatory: 7-yr retention, SOX-grade audit trail, AML hooks

**Out of scope:** card processing, wire transfers (different rails), KYC.

## 2. API

```
POST /api/v1/transfers
  Headers: Idempotency-Key: <uuid>
  Body:    { from_account, to_account, amount, currency, reference }
  → 201:   { transaction_id, status, balances }
  → 409:   InsufficientFunds | SameAccount | InvalidAmount

GET  /api/v1/accounts/{id}/balance
GET  /api/v1/accounts/{id}/transactions?from=…&to=…
POST /api/v1/transfers/{id}/reverse
```

## 3. Estimate

```
5k transfer/s × 86400 = 430M transfers/day
Each row: ~500 B ledger event + ~1 KB metadata
→ 700 GB/day, 250 TB/year, 1.7 PB / 7-yr retention

Reads (balance + history): 50k QPS aggregate
```

## 4. Architecture

```
                  ┌─────────────────────────────────┐
                  │       API gateway                │
                  │   (auth, rate limit, idempotency)│
                  └────────────────┬────────────────┘
                                   │
                       ┌───────────┼───────────┐
                       ▼           ▼           ▼
                  ┌────────┐  ┌────────┐  ┌────────┐
                  │Transfer│  │Transfer│  │Transfer│   stateless
                  │ svc #1 │  │ svc #2 │  │ svc #N │
                  └───┬────┘  └───┬────┘  └───┬────┘
                      │           │           │
                      └─────┬─────┴─────┬─────┘
                            │           │
                            ▼           ▼
                  ┌──────────────┐  ┌─────────────┐
                  │ Ledger DB     │  │ Idempotency │
                  │ (Postgres,    │  │ store       │
                  │  partitioned  │  │ (Redis +    │
                  │  by account)  │  │  Postgres)  │
                  └──────┬───────┘  └─────────────┘
                         │
                         │ logical replication
                         ▼
                  ┌──────────────┐
                  │ Event stream │ (Kafka, ordered per account)
                  └──────┬───────┘
                         ▼
                  ┌──────────────┐
                  │ Projections: │
                  │ - statements │
                  │ - reporting  │
                  │ - notifications│
                  │ - AML/fraud  │
                  └──────────────┘
```

## 5. Storage model — **double-entry ledger**

Don't store balances as the source of truth. Store **events** and derive balances. This is non-negotiable for a real ledger.

```sql
-- Events: append-only, never updated
CREATE TABLE ledger_entries (
    id            UUID PRIMARY KEY,
    txn_id        UUID NOT NULL,
    account_id    BIGINT NOT NULL,
    amount        NUMERIC(38, 4) NOT NULL,    -- + credit, - debit
    currency      CHAR(3) NOT NULL,
    direction     CHAR(1) NOT NULL,            -- 'D' or 'C'
    posted_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- One transfer = TWO entries: debit from, credit to (sums to 0)
CREATE TABLE transactions (
    id            UUID PRIMARY KEY,
    type          TEXT NOT NULL,
    status        TEXT NOT NULL,               -- pending | posted | reversed
    initiated_at  TIMESTAMPTZ,
    posted_at     TIMESTAMPTZ
);

-- Materialized balance — projection, can be rebuilt from ledger_entries
CREATE TABLE balances (
    account_id    BIGINT,
    currency      CHAR(3),
    balance       NUMERIC(38, 4) NOT NULL,
    updated_at    TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (account_id, currency)
);
```

**Invariant:** `SUM(ledger_entries.amount WHERE txn_id = X) = 0`. Run as a periodic check; alert on violation.

## 6. Concurrency: per-account row lock

Same pattern as the L1/L2:

```sql
BEGIN;
SELECT balance FROM balances
 WHERE account_id IN ($from, $to) AND currency = $cur
 ORDER BY account_id          -- sorted lock acquisition (deadlock-free)
   FOR UPDATE;

-- check balance >= amount

INSERT INTO ledger_entries (debit row);
INSERT INTO ledger_entries (credit row);
INSERT INTO transactions ($txn_id, 'posted', ...);
UPDATE balances SET balance = balance - $amt WHERE account_id = $from;
UPDATE balances SET balance = balance + $amt WHERE account_id = $to;
INSERT INTO idempotency ($idem_key, $txn_id);
COMMIT;
```

**ORDER BY account_id** is the deadlock prevention — same as L1's lock-sorting trick, in SQL.

The L2 [account_transfer_sql.py](../../../revolut/src/account_transfer_sql.py) implements exactly this pattern.

## 7. Idempotency — first-class

Two layers:

1. **Idempotency-Key header** (caller-supplied UUID, lives 24h in Redis + permanent in DB)
2. **Inside the transaction:** `INSERT INTO idempotency (key, txn_id)` — if it conflicts, the _other_ request won; rollback this txn and return the winner's result

The L2 SQL ledger handles this via `UniqueViolation` catch + lookup. Same pattern at HLD scale, just sharded.

## 8. Multi-currency

Each account has **per-currency balance rows**. A USD→EUR transfer is two ledger events:

```
T1: debit  $100 USD from sender
T1: credit $100 USD to FX-pool USD
T1: debit  €92  EUR from FX-pool EUR
T1: credit €92  EUR to receiver
```

Four entries, sum to zero per currency. FX rate captured in `transactions.metadata` for audit.

For real-time FX, plug in a pricing service with a quote_id (locked rate for ~10 s) — the transfer references the quote.

## 9. Sharding strategy

**Shard key:** `account_id` (hash). Both endpoints of a transfer might be on different shards → distributed transaction.

Options for cross-shard:

1. **2PC (two-phase commit)** — coordinator orchestrates prepare/commit across shards. Strong consistency, slow, blocking on coordinator failure.
2. **Saga pattern** — debit first, credit second; on failure, compensating reversal. Eventually consistent, no global lock.
3. **Co-locate by user** — for intra-user transfers (most volume), put both accounts on same shard.

**Recommendation:** Saga + co-location. Most transfers are intra-bank intra-user; cross-shard goes through a saga with explicit pending/posted/reversed states.

## 10. Saga in detail

```
1. INSERT transactions (status='pending')
2. Debit sender (atomic per shard)
   on failure → mark txn 'failed', return 4xx
3. Credit receiver (atomic per shard)
   on failure → reverse step 2 (compensating debit)
   mark txn 'reversed', return 5xx
4. UPDATE transactions SET status='posted'
```

Each step is its own atomic per-account txn. Saga state machine survives crashes (worker restart picks up `pending` txns and resumes). **Crucial:** sender sees the debit before the credit completes — UI must show "pending" state.

## 11. Reversals / refunds

Never UPDATE or DELETE a ledger entry. A reversal is a _new_ transaction with opposite direction, linked via `reverses_txn_id`.

```sql
INSERT INTO transactions (id, type='reversal', reverses_txn_id=$original);
INSERT INTO ledger_entries (... reverse direction ...);
```

This preserves audit invariant: history is replay-able.

## 12. Read paths

| Query                              | Source                                          |
| ---------------------------------- | ----------------------------------------------- |
| Current balance                    | `balances` projection (cached in Redis, TTL 1s) |
| Last 90d transactions              | Postgres, partitioned by month                  |
| Older transactions                 | Cold storage (S3 + Athena, or BigQuery)         |
| Statement export                   | Async job, projection from event stream         |
| Real-time aggregates (daily total) | Stream processor (Flink) on Kafka               |

## 13. Event streaming

Logical replication from Postgres → Kafka (Debezium). Every `ledger_entries` insert becomes a Kafka event, **ordered per account**.

Downstream consumers:

- **Notification service** — push to user's device on incoming credit
- **Fraud / AML service** — pattern detection, regulatory reports
- **Reporting / BI** — into ClickHouse / BigQuery
- **Reconciliation** — daily checks against partner banks

## 14. Failure modes

| Failure                                             | Mitigation                                                                                                          |
| --------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| Postgres master down                                | Synchronous replica → promote (RPO=0); writes pause ~30s                                                            |
| Network partition between shards mid-saga           | Saga state machine resumes after partition heals                                                                    |
| Duplicate transfer (client retry without idem key)  | Reject (require Idempotency-Key on production); deduplicate by (from, to, amount, ts within 60s) as belt-and-braces |
| Money "lost" (debit succeeds, credit fails forever) | Saga compensator runs; manual reconciliation alert if compensator also fails (rare, on-call escalation)             |
| Idempotency store down                              | Reject writes (fail closed) — never risk double-debit                                                               |
| Negative balance discovered post-hoc                | Alert + investigation; ledger replay tells you exactly when                                                         |

## 15. Compliance / audit

- **Immutability:** ledger_entries is append-only (DB-enforced via row-level rules or a stream-only WAL forwarder)
- **WORM storage:** for >1y old data, write-once-read-many (S3 Object Lock)
- **PII separation:** account holder data in a separate DB with stricter access; ledger uses opaque account_id
- **Audit log of audits:** who queried what statement, retained 7y
- **Regulatory holds:** can freeze an account (`balances.frozen=true`); `transfer` checks before debit

## 16. Capacity

```
430M txns/day × 4 ledger entries (with FX) = 1.7B entries/day
At 5k QPS sustained, peak 50k:
  → 100 transfer-svc pods × 500 QPS each (saga-driven, mostly waiting on DB)
  → ~50 Postgres shards (1k write QPS each, well within limits)
  → Redis idempotency: 5 GB hot keys, 10-node cluster
  → Kafka: 1.7B events/day × 1 KB = 1.7 TB/day, 7-day retention
```

## 17. What the L2 SQL ledger does well, and where it stops

The L2 [account_transfer_sql.py](../../../revolut/src/account_transfer_sql.py) covers:

- `SELECT … FOR UPDATE ORDER BY id` — deadlock-free row locks ✓
- Idempotency table with caller-supplied key ✓
- ACID transaction wrapping debit + credit + log + idempotency insert ✓
- Catch `UniqueViolation` on idempotency conflict → return cached winner ✓
- Foreign keys, CHECK constraints (balance >= 0, amount > 0) ✓

Stops at:

- Single Postgres instance — no sharding, no saga
- Single currency (`amount NUMERIC`, no `currency` column)
- Mutable `balances` as source of truth, no event-sourced ledger
- No reversal model
- No multi-region

Each is a layer-3 graduation. Volunteer them as "the next 4 things I'd add."

## 18. What the interviewer will probe

| Question                                                      | Where                                                                                                                   |
| ------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| "How do you guarantee no double-spend?"                       | §6 — `FOR UPDATE` row lock per account, sorted acquisition                                                              |
| "What if the network drops mid-transfer?"                     | §10 — saga with pending state, resumed by worker on recovery                                                            |
| "What if the same request is retried?"                        | §7 — Idempotency-Key, unique constraint, return cached result                                                           |
| "How do you scale beyond one Postgres?"                       | §9 — shard by account_id, saga across shards                                                                            |
| "How do you handle multi-currency?"                           | §8 — per-currency balance rows, FX as 4-leg ledger                                                                      |
| "How do you reverse a transfer?"                              | §11 — new transaction with opposite direction, linked                                                                   |
| "How do you audit?"                                           | §5 + §15 — append-only ledger is the source of truth, balances are projections                                          |
| "What about CAP?"                                             | We pick **CP**. Availability degrades during partitions; never lose consistency on money                                |
| "What's the difference between transactional outbox and CDC?" | Outbox = app writes event to outbox table in same txn; CDC reads WAL. Both achieve same goal — atomic event publication |

## 19. Tradeoffs to volunteer

- **Event-sourced ledger vs balance-as-truth** — event-sourced is auditable and replayable but slower reads (need projections); balance-as-truth is faster but loses audit trail
- **Saga vs 2PC** — saga is available under partition but eventually consistent and harder to reason about; 2PC is strongly consistent but blocks on coordinator failure
- **Sync replica vs async** — sync = RPO 0 but write latency ↑; async = lose recent writes on master crash
- **Per-account lock vs SERIALIZABLE isolation** — per-row lock is targeted (no false conflicts); SERIALIZABLE is simpler but causes more retries under contention
- **Pre-check balance vs let DB CHECK fail** — pre-check returns nicer error but adds a read; let CHECK fail is one round-trip but uglier client error

# Revolut Live Coding Round — Prep Plan

> Focused 7-day plan for the 45-60 min live-coding round. Grounded in [swe-stats.md](swe-stats.md) (frequency from 120+ interviews) and [REVOLUT_INTERVIEW_STUDY_GUIDE.md](REVOLUT_INTERVIEW_STUDY_GUIDE.md) (patterns + rejection feedback).

## Round format

- **Duration:** 45-60 min over Google Meet
- **IDE:** IntelliJ / VS Code allowed, **no AI tools**
- **Style:** TDD expected — bring a testing framework muscle-memory
- **Requirements:** delivered iteratively (you start simple, interviewer adds complexity)
- **Languages:** Java or Python (no Spring framework allowed)
- **Pass bar:** ~26% offer rate via recruiter channel; #1 rejection reason is **"not production-ready"**

## What gets graded

From actual rejection feedback in [REVOLUT_INTERVIEW_STUDY_GUIDE.md §2.1](REVOLUT_INTERVIEW_STUDY_GUIDE.md):

| Signal | Weight |
|--------|--------|
| Strategy pattern (extensibility) | High |
| Thread safety **with tests** | High |
| Exceptions, not string returns | High |
| All core methods present (esp. `get()` / `getServer()`) | Critical — frequently missed |
| `Decimal` / `BigDecimal` for money | Critical for transfer task |
| Lock ordering for multi-resource ops | Critical for transfer task |
| TDD flow (test → implement → refactor) | Medium |
| Time complexity discussion | Medium |
| Production scaffolding (FastAPI + Docker + uv) | Bonus, strong differentiator |

## The three canonical tasks

### Task 1 — Load Balancer (most common, 30+ reports)

**Required interface:**

```python
class LoadBalancer:
    def __init__(self, max_instances: int = 10, strategy: ServerSelectionStrategy = None)
    def register(self, instance: str) -> bool
    def unregister(self, instance: str) -> bool
    def get(self) -> str  # ← critical — frequently forgotten
```

**Iterative requirements (in order):**

1. Register/get with simple list
2. Pull selection out into a `ServerSelectionStrategy` Protocol (Random, RoundRobin)
3. Add `unregister`
4. Cap at `max_instances`, return `False` or raise `ServerLimitException`
5. Add thread safety with `threading.Lock`
6. Write 2-3 tests proving correctness under concurrent register/unregister
7. Follow-up: `LeastConnectionsStrategy`, weighted random, heartbeat-based eviction

**LeetCode foundations:** [LC 380](../../banks/coding/live-coding.json#L5-L45), [LC 381](../../banks/coding/live-coding.json#L46-L74), [LC 1845](../../banks/coding/live-coding.json#L106-L136)

**Reference implementation:** [revolut_coding/lib/load_balancer.py](../revolut_coding/)

### Task 2 — URL Shortener (second most common)

**Required interface:**

```python
class URLShortener:
    def __init__(self, strategy: ShorteningStrategy)
    def shorten(self, long_url: str) -> str
    def unshorten(self, short_url: str) -> str
```

**Iterative requirements:**

1. Shorten/unshorten with two maps (long→short, short→long)
2. Pull strategy out (`CounterStrategy`, `MD5Strategy`, `Base62RandomStrategy`)
3. **Idempotency** — same long URL must return same short URL
4. **Collision detection** — raise on collision (or retry)
5. URL format validation (regex)
6. Cap at 100 URLs (or LRU eviction beyond cap)
7. Thread safety with `Lock`
8. Tests for: idempotency, collision, cap enforcement, concurrent access

**LeetCode foundations:** [LC 535](../../banks/coding/live-coding.json#L262), [LC 379](../../banks/coding/live-coding.json#L75-L105), [LC 146](../../banks/coding/live-coding.json#L137-L168)

**Reference implementation:** [revolut_coding/lib/url_shortner.py](../revolut_coding/)

### Task 3 — Money Transfer

**Required interface:**

```python
class Account:
    def __init__(self, account_id: int, balance: Decimal)
    def deposit(self, amount: Decimal) -> None
    def withdraw(self, amount: Decimal) -> bool

class Ledger:
    @staticmethod
    def transfer(from_account: Account, to_account: Account, amount: Decimal) -> bool
```

**Iterative requirements:**

1. `Decimal` from String — **never `float`**
2. Validate amount > 0, raise `ValueError` otherwise
3. Per-account `RLock` for deposit/withdraw atomicity
4. Transfer = withdraw + deposit, both under both locks
5. **Lock ordering by account_id** to prevent deadlock
6. Insufficient funds: return `False` or raise (clarify with interviewer)
7. Tests: concurrent transfers in opposite directions (A→B and B→A simultaneously) — must not deadlock
8. Follow-up: idempotency keys, audit trail (event-sourced ledger), SQL pessimistic vs optimistic locking

**No LeetCode equivalent** — see [drill_plan session 8](../../banks/coding/live-coding.json#L308-L312)

**Reference implementation:** [revolut_coding/lib/account_transfer.py](../revolut_coding/)

## Patterns to internalize

These show up across all three tasks. Drill until they're muscle memory.

### Strategy pattern (the make-or-break signal)

```python
from abc import ABC, abstractmethod

class ServerSelectionStrategy(ABC):
    @abstractmethod
    def select(self, servers: list[str]) -> str: ...

class RandomStrategy(ServerSelectionStrategy):
    def select(self, servers: list[str]) -> str:
        if not servers: raise NoServersAvailableError()
        return random.choice(servers)

class LoadBalancer:
    def __init__(self, strategy: ServerSelectionStrategy):
        self._strategy = strategy  # injected, not hard-coded
```

### Lock ordering (deadlock prevention)

```python
def transfer(self, from_acc: Account, to_acc: Account, amount: Decimal) -> bool:
    first, second = sorted([from_acc, to_acc], key=lambda a: a.account_id)
    with first._lock, second._lock:
        if from_acc.withdraw(amount):
            to_acc.deposit(amount)
            return True
        return False
```

### Idempotency (URL shortener + transfer)

```python
def shorten(self, long_url: str) -> str:
    with self._lock:
        if long_url in self._long_to_short:
            return self._long_to_short[long_url]  # idempotent
        # ... generate, store, return
```

### Decimal-from-String (financial precision)

```python
from decimal import Decimal
balance = Decimal("100.10")          # ← from String
balance -= Decimal("0.10")
# 100.00 exactly. Decimal(100.10) loses precision — never do that.
```

### Custom exceptions over string returns

```python
class NoServersAvailableError(Exception): pass
class ServerLimitExceededError(Exception): pass
class CollisionDetectedError(Exception): pass

# return "Successfully added"  ← INSTANT REJECT
# raise ServerLimitExceededError("max 10 instances")  ← correct
```

## 45-minute time-box

| Minutes | Focus | Output |
|---------|-------|--------|
| 0-5 | Clarify requirements, sketch interface aloud | Class skeleton + method signatures |
| 5-20 | Core methods (make it WORK) | Happy-path code, no concurrency yet |
| 20-35 | Strategy pattern + thread safety (make it SOLID) | `Lock`, custom exceptions, abstraction |
| 35-45 | Tests + edge cases (prove it WORKS) | 2-3 unit tests including concurrent test |

**Priority order:** Working > SOLID > Thread-safe > Beautiful. Don't optimize prematurely.

## 7-day schedule

### Day 1 — Load Balancer end-to-end

- Read [revolut_coding/lib/load_balancer.py](../revolut_coding/) reference
- Implement from scratch with `register`/`unregister`/`get`
- Refactor: pull selection into `Strategy` Protocol, add `RandomStrategy` + `RoundRobinStrategy`
- Add `Lock`, write a concurrent register/unregister test using `threading`
- Drill [LC 380](../../banks/coding/live-coding.json#L5-L45) until <15 min

### Day 2 — URL Shortener end-to-end

- Implement `shorten`/`unshorten` with two maps
- Add `ShorteningStrategy` (Counter, MD5, Base62Random)
- Idempotency check, collision detection, 100-URL cap with FIFO eviction
- URL validation regex
- Tests: idempotency, collision, cap, concurrent shorten
- Warm-up: [LC 535](../../banks/coding/live-coding.json#L262), [LC 528 Random Pick with Weight](https://leetcode.com/problems/random-pick-with-weight/)

### Day 3 — Money Transfer

- Implement `Account` + `Ledger` with `Decimal`
- Per-account `RLock`
- `transfer` with lock-ordering by account_id
- Concurrent transfer test: 1000 transfers A→B and B→A simultaneously, assert sum invariant
- Warm-up: [LC 2043 Simple Bank System](https://leetcode.com/problems/simple-bank-system/)

### Day 4 — Concurrency depth

- Read [REVOLUT_INTERVIEW_STUDY_GUIDE.md §3](REVOLUT_INTERVIEW_STUDY_GUIDE.md)
- Quiz yourself: GIL impact, race conditions, deadlock conditions, `volatile` vs `synchronized`
- Add `Lock` (and an `RLock` variant) to your day-1/2/3 solutions
- Practice explaining: "I'm using `RLock` here because the same thread may re-enter via `transfer` calling `withdraw`."

### Day 5 — ACID + isolation levels (deep-dive prep)

- Read [REVOLUT_INTERVIEW_STUDY_GUIDE.md §4](REVOLUT_INTERVIEW_STUDY_GUIDE.md)
- Memorize the table: which isolation level prevents which anomaly
- Drill: "What level for payments?" → Serializable. "Why?" → prevents phantom reads in transfer batches.
- Drill: optimistic vs pessimistic — when to use each, the SQL syntax for `SELECT ... FOR UPDATE ORDER BY account_id`

### Day 6 — Strategy variants & follow-ups

- `LeastConnectionsStrategy` (heap-based) — [LC 1845](../../banks/coding/live-coding.json#L106-L136)
- `WeightedRandomStrategy` — cumulative-sum + bisect, or LC 528
- TTL-based heartbeat eviction for stale servers — [LC 1797](../../banks/coding/live-coding.json#L199-L229)
- Sliding-window rate limiter on the Load Balancer — [LC 362](../../banks/coding/live-coding.json#L297)

### Day 7 — Production scaffolding + mock interview

- Wrap Load Balancer in FastAPI ([REVOLUT_INTERVIEW_STUDY_GUIDE.md §9](REVOLUT_INTERVIEW_STUDY_GUIDE.md))
- `uv init` + `pyproject.toml` + multi-stage Dockerfile + healthcheck
- Mock interview: 45-min timer, do Load Balancer or URL Shortener cold, narrate aloud
- Self-grade against the Pre-Interview Checklist below

## Pre-interview checklist

**Coding mechanics:**

- [ ] Can scaffold a project in <2 min with `uv init` + `uv add`
- [ ] Can write `Strategy` pattern from memory (abstract base + 2 concrete)
- [ ] Can add thread safety with `Lock`/`RLock` without hesitation
- [ ] Can write a deadlock-free transfer with lock ordering by ID
- [ ] Can write a concurrent test using `threading.Thread` + `Barrier`
- [ ] Always raise custom exceptions, never return error strings
- [ ] Always use `Decimal("...")` from String for money

**Talking points:**

- [ ] Can explain why Strategy pattern (extensibility, OCP)
- [ ] Can explain why `Decimal` (float precision loss compounds)
- [ ] Can explain why lock ordering (breaks circular wait condition)
- [ ] Can explain `RLock` vs `Lock` (re-entrancy)
- [ ] Can explain GIL impact (CPU-bound vs I/O-bound)
- [ ] Can explain time complexity of every method you write

**Things you should NEVER do:**

- [ ] `return "Successfully added"` — return `bool` or raise
- [ ] `float balance = 100.0` — use `Decimal` from String
- [ ] Forget the `get()` / `getServer()` method — it's the core feature
- [ ] Skip thread safety because the interviewer didn't mention it yet
- [ ] Hard-code the selection algorithm — always Strategy
- [ ] `synchronized(accountA) { synchronized(accountB) }` without ID ordering
- [ ] Code without writing a single test

## What to say out loud during the interview

These phrases earn points (from [REVOLUT_INTERVIEW_STUDY_GUIDE.md §10](REVOLUT_INTERVIEW_STUDY_GUIDE.md)):

- "I'm using Strategy pattern so we can add new algorithms without modifying `LoadBalancer` — Open/Closed."
- "Lock ordering by `account_id` prevents the circular-wait deadlock condition."
- "`Decimal` from String, because `Decimal(100.10)` inherits the `float` precision loss before construction."
- "Let me write a concurrent test for this — I'll use a `Barrier` to make threads start at the same time."
- "Time complexity is O(1) average for register and get, because we use a hash set + list with index map."
- "I'd add an idempotency key here so client retries don't double-spend."

## Reference files in this repo

- [interview/banks/coding/live-coding.json](../../banks/coding/live-coding.json) — 15 LeetCode design problems with solutions
- [interview/revolut/banks/REVOLUT_INTERVIEW_STUDY_GUIDE.md](REVOLUT_INTERVIEW_STUDY_GUIDE.md) — full study guide with code samples
- [interview/revolut/banks/swe-stats.md](swe-stats.md) — interview frequency stats and questions bank
- [revolut/revolut_coding/lib/](../revolut_coding/) — reference implementations of all three canonical tasks
- [revolut/src/](../../../../revolut/src/) — your in-progress Revolut prep code

# Revolut Backend Engineer Interview Study Guide

> **Consolidated from 6 specialized guides with adversarial validation corrections applied**
>
> Based on analysis of 120+ interview reviews, 6 code repositories, and real rejection feedback

## Table of Contents

1. [Interview Overview](#1-interview-overview)
2. [Coding Challenges](#2-coding-challenges)
3. [Concurrency & Threading](#3-concurrency--threading)
4. [Database & Transactions](#4-database--transactions)
5. [System Design](#5-system-design)
6. [Language Internals](#6-language-internals)
7. [Design Patterns & SOLID](#7-design-patterns--solid)
8. [Quick Reference Cheatsheets](#8-quick-reference-cheatsheets)
9. [Production Setup](#9-production-setup)
10. [Interview Questions Bank](#10-interview-questions-bank)

## 1. Interview Overview

### Process Flow

1. **HR Screening** (20-45 min) - Background, motivation
2. **Live Coding** (45-60 min) - Usually Load Balancer or URL Shortener
3. **Technical Deep-dive** (1 hr) - Concurrency, DB, language internals
4. **System Design** (1 hr) - Event sourcing, distributed systems

### Success Statistics

- Success rate: 15-26% (recruiter channel better than online)
- Timeline: 2 weeks to 2 months
- Most common rejection: "Not production-ready"

### What Revolut Values Most

1. **Production-ready code** - Not toy implementations
2. **Thread safety** - With tests proving it
3. **Proper error handling** - Exceptions, not string returns
4. **Extensibility** - Strategy pattern, SOLID principles
5. **Financial precision** - BigDecimal/Decimal, never float

## 2. Coding Challenges

### 2.1 Load Balancer (Most Common - 30+ interviews)

#### Required Interface

```python
class LoadBalancer:
    def __init__(self, max_instances: int = 10, strategy: ServerSelectionStrategy = None)
    def register(self, instance: str) -> bool
    def unregister(self, instance: str) -> bool
    def get(self) -> str  # CRITICAL - This was missing in rejected code!
```

#### Production-Ready Implementation (Python)

```python
from abc import ABC, abstractmethod
from threading import Lock
from typing import List, Optional
from random import choice

class NoServersAvailableError(Exception):
    pass

class ServerSelectionStrategy(ABC):
    @abstractmethod
    def select_server(self, instances: List[str]) -> str:
        raise NotImplementedError()

class RoundRobinSelectionStrategy(ServerSelectionStrategy):
    def __init__(self):
        self.index = -1

    def select_server(self, instances: List[str]) -> str:
        if not instances:
            raise NoServersAvailableError("No servers registered")
        self.index = (self.index + 1) % len(instances)
        return instances[self.index]

class RandomSelectionStrategy(ServerSelectionStrategy):
    def select_server(self, instances: List[str]) -> str:
        if not instances:
            raise NoServersAvailableError("No servers registered")
        return choice(instances)

class LoadBalancer:
    def __init__(self, max_instances: int = 10,
                 strategy: Optional[ServerSelectionStrategy] = None):
        if max_instances <= 0:
            raise ValueError("max_instances must be positive")
        self.max_instances = max_instances
        self.strategy = strategy or RoundRobinSelectionStrategy()
        self.instances: List[str] = []
        self.lock = Lock()

    def register(self, instance: str) -> bool:
        with self.lock:
            if len(self.instances) >= self.max_instances:
                return False  # Or raise ServerLimitException
            if instance in self.instances:
                return False  # Duplicate
            self.instances.append(instance)
            return True

    def unregister(self, instance: str) -> bool:
        with self.lock:
            if instance not in self.instances:
                return False
            self.instances.remove(instance)
            return True

    def get(self) -> str:
        with self.lock:
            return self.strategy.select_server(self.instances)
```

#### Why Code Gets Rejected (From Actual Feedback)

| Rejection Reason                    | Fix                                             |
| ----------------------------------- | ----------------------------------------------- |
| No `getServer()` method             | Add the `get()` method - it's the core feature! |
| Returns "Successfully added" string | Return boolean or raise exception               |
| No Strategy pattern                 | Use abstract class + concrete strategies        |
| No `unregister()` method            | Add ability to remove servers                   |
| No thread-safety tests              | Add concurrent register/unregister tests        |

#### 45-Minute Time-Box Strategy

- **0-5 min**: Clarify requirements, sketch interface
- **5-20 min**: Core methods (register, unregister, get)
- **20-35 min**: Strategy pattern + thread safety
- **35-45 min**: 2-3 unit tests + error handling

---

### 2.2 URL Shortener

#### Production-Ready Implementation

```python
from abc import ABC, abstractmethod
import threading
import itertools
import hashlib
import base64
import re

class ShorteningStrategy(ABC):
    @abstractmethod
    def generate_short_url(self, long_url: str) -> str:
        pass

class CounterStrategy(ShorteningStrategy):
    def __init__(self):
        self.counter = itertools.count(1)
        self.lock = threading.Lock()

    def generate_short_url(self, long_url: str) -> str:
        with self.lock:
            return str(next(self.counter))

class MD5Strategy(ShorteningStrategy):
    def generate_short_url(self, long_url: str) -> str:
        return hashlib.md5(long_url.encode()).hexdigest()[:8]

class URLShortener:
    URL_PATTERN = re.compile(
        r'^(https?://)?([\da-z.-]+)\.([a-z.]{2,6})([/\w .-]*)*/?$'
    )

    def __init__(self, strategy: ShorteningStrategy):
        self.strategy = strategy
        self.url_map = {}  # long -> short
        self.short_to_url = {}  # short -> long
        self.lock = threading.Lock()

    def shorten(self, long_url: str) -> str:
        if not self._is_valid_url(long_url):
            raise ValueError(f"Invalid URL format: {long_url}")

        with self.lock:
            # Idempotency - return existing if already shortened
            if long_url in self.url_map:
                return self.url_map[long_url]

            short_url = self.strategy.generate_short_url(long_url)

            # Collision detection
            if short_url in self.short_to_url:
                raise ValueError(f"Collision detected for: {short_url}")

            self.url_map[long_url] = short_url
            self.short_to_url[short_url] = long_url
            return short_url

    def unshorten(self, short_url: str) -> str:
        with self.lock:
            if short_url not in self.short_to_url:
                raise KeyError(f"Short URL not found: {short_url}")
            return self.short_to_url[short_url]

    def _is_valid_url(self, url: str) -> bool:
        return bool(self.URL_PATTERN.match(url))
```

---

### 2.3 Money Transfer (Critical for Revolut)

#### Java Implementation (Production-Ready)

```java
import java.math.BigDecimal;

public class BankAccount {
    private final String accountId;
    private BigDecimal balance;  // ALWAYS BigDecimal for money!

    public BankAccount(String accountId, BigDecimal balance) {
        this.accountId = accountId;
        this.balance = balance;
    }

    public synchronized void deposit(BigDecimal amount) {
        if (amount.compareTo(BigDecimal.ZERO) <= 0) {
            throw new IllegalArgumentException("Amount must be positive");
        }
        balance = balance.add(amount);
    }

    public synchronized void withdraw(BigDecimal amount) {
        if (amount.compareTo(BigDecimal.ZERO) <= 0) {
            throw new IllegalArgumentException("Amount must be positive");
        }
        if (balance.compareTo(amount) < 0) {
            throw new IllegalArgumentException("Insufficient funds");
        }
        balance = balance.subtract(amount);
    }

    // CRITICAL: Deadlock prevention via consistent lock ordering
    public static void transferMoney(BankAccount from, BankAccount to,
                                     BigDecimal amount) {
        // Always lock lower ID first
        BankAccount firstLock = from;
        BankAccount secondLock = to;

        if (from.getAccountId().compareTo(to.getAccountId()) > 0) {
            firstLock = to;
            secondLock = from;
        }

        synchronized (firstLock) {
            synchronized (secondLock) {
                from.withdraw(amount);
                to.deposit(amount);
            }
        }
    }

    public String getAccountId() { return accountId; }
    public BigDecimal getBalance() { return balance; }
}
```

#### Python Implementation

```python
from threading import RLock
from decimal import Decimal

class Account:
    def __init__(self, account_id: int, balance: Decimal = Decimal('0')):
        self.account_id = account_id
        self.balance = balance
        self._lock = RLock()

    def deposit(self, amount: Decimal) -> None:
        if amount <= 0:
            raise ValueError("Amount must be positive")
        with self._lock:
            self.balance += amount

    def withdraw(self, amount: Decimal) -> bool:
        if amount <= 0:
            raise ValueError("Amount must be positive")
        with self._lock:
            if self.balance >= amount:
                self.balance -= amount
                return True
            return False

class Ledger:
    @staticmethod
    def transfer_money(from_account: Account, to_account: Account,
                       amount: Decimal) -> bool:
        # CRITICAL: Lock ordering by account_id prevents deadlock
        if from_account.account_id < to_account.account_id:
            first, second = from_account, to_account
        else:
            first, second = to_account, from_account

        with first._lock, second._lock:
            if from_account.withdraw(amount):
                to_account.deposit(amount)
                return True
            return False
```

---

## 3. Concurrency & Threading

### 3.1 Deadlock Prevention (Most Critical Pattern)

**The Four Conditions for Deadlock:**

1. Mutual Exclusion - Resource held exclusively
2. Hold and Wait - Thread holds resource while requesting another
3. No Preemption - Cannot forcibly take resources
4. **Circular Wait** - Circular chain of waiting threads

**Solution: Break Circular Wait with Consistent Lock Ordering**

```java
// BAD - Can deadlock
synchronized (accountA) {
    synchronized (accountB) { /* ... */ }
}
// Thread 1: A → B
// Thread 2: B → A → DEADLOCK!

// GOOD - Order by ID
if (accountA.getId() < accountB.getId()) {
    synchronized (accountA) {
        synchronized (accountB) { /* ... */ }
    }
} else {
    synchronized (accountB) {
        synchronized (accountA) { /* ... */ }
    }
}
// All threads: lower ID → higher ID (no circular wait)
```

### 3.2 Java Concurrency Primitives

| Primitive            | Use Case                        | Thread-Safe?     |
| -------------------- | ------------------------------- | ---------------- |
| `synchronized`       | Simple mutual exclusion         | Yes              |
| `ReentrantLock`      | More control (tryLock, timeout) | Yes              |
| `volatile`           | Single variable visibility      | Visibility only  |
| `AtomicInteger/Long` | Lock-free counters              | Yes              |
| `ConcurrentHashMap`  | Thread-safe map                 | Yes (per-bucket) |
| `Semaphore`          | Limiting concurrent access      | Yes              |

### 3.3 Python Concurrency

#### GIL (Global Interpreter Lock) - CRITICAL KNOWLEDGE

```python
# GIL Impact:
# - Only ONE thread executes Python bytecode at a time
# - Threading does NOT help CPU-bound tasks
# - Threading DOES help I/O-bound tasks (GIL released during I/O)

# CPU-bound: Use multiprocessing
from multiprocessing import Process
p1 = Process(target=cpu_work)
p1.start()  # True parallelism

# I/O-bound: Threading works
import threading
t1 = threading.Thread(target=fetch_url)
t1.start()  # GIL released during network I/O
```

### 3.4 Common Interview Questions

**Q: How to prevent shared resources from being accessed by multiple threads?**

```
A: Multiple approaches depending on use case:
1. synchronized keyword (Java) / Lock (Python) - simplest
2. ConcurrentHashMap for thread-safe collections
3. Immutable objects - thread-safe by design
4. Lock ordering - for multi-resource operations
5. Message passing / queues - avoid shared state entirely
```

**Q: What's the difference between volatile and synchronized?**

```
| volatile                    | synchronized                    |
|-----------------------------|--------------------------------|
| Visibility only             | Visibility + atomicity         |
| No mutual exclusion         | Provides mutual exclusion      |
| Single variable             | Block of code                  |
| No performance overhead     | Has locking overhead           |
```

---

## 4. Database & Transactions

### 4.1 ACID Properties

| Property        | Definition                              | Financial Example                        |
| --------------- | --------------------------------------- | ---------------------------------------- |
| **Atomicity**   | All-or-nothing                          | Debit AND credit both happen, or neither |
| **Consistency** | Valid state to valid state              | Balance >= 0 maintained                  |
| **Isolation**   | Concurrent transactions don't interfere | Two transfers don't corrupt              |
| **Durability**  | Committed = permanent                   | After COMMIT, survives crash             |

### 4.2 Transaction Isolation Levels

```
Read Uncommitted → Read Committed → Repeatable Read → Serializable
    (Weakest)                                          (Strongest)
    (Fastest)                                          (Safest)
```

| Level            | Prevents         | Allows               | Use Case               |
| ---------------- | ---------------- | -------------------- | ---------------------- |
| Read Uncommitted | Nothing          | Dirty reads          | Never for finance      |
| Read Committed   | Dirty reads      | Non-repeatable reads | Most OLTP              |
| Repeatable Read  | + Non-repeatable | Phantom reads        | Row-level consistency  |
| Serializable     | Everything       | Nothing              | Critical financial ops |

### 4.3 Pessimistic Locking (Correct Pattern)

```sql
-- CORRECT: Lock in consistent order to prevent deadlock
START TRANSACTION;

SELECT balance FROM accounts
WHERE account_id IN (1, 2)
ORDER BY account_id  -- CRITICAL: Consistent ordering!
FOR UPDATE;

-- Check balance
SELECT balance INTO @balance FROM accounts WHERE account_id = 1;
IF @balance < 100 THEN
    ROLLBACK;
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Insufficient funds';
END IF;

-- Perform transfer
UPDATE accounts SET balance = balance - 100 WHERE account_id = 1;
UPDATE accounts SET balance = balance + 100 WHERE account_id = 2;

-- Audit trail (required for financial systems!)
INSERT INTO transactions (from_id, to_id, amount, status, created_at)
VALUES (1, 2, 100, 'SUCCESS', NOW());

COMMIT;
```

### 4.4 Optimistic Locking (Version Fields)

```java
@Entity
public class Account {
    @Id
    private Long id;
    private BigDecimal balance;

    @Version  // Hibernate manages this automatically
    private Long version;
}

// On update, Hibernate generates:
// UPDATE accounts SET balance=?, version=version+1
// WHERE id=? AND version=?
// If version mismatch: OptimisticLockException thrown
```

### 4.5 When to Use Which

| Scenario             | Approach    | Why                                     |
| -------------------- | ----------- | --------------------------------------- |
| Money transfer       | Pessimistic | High contention, must succeed first try |
| User profile update  | Optimistic  | Low contention, retry acceptable        |
| Inventory decrement  | Pessimistic | Prevent overselling                     |
| Read-heavy reporting | Optimistic  | Better concurrency                      |

### 4.6 BigDecimal - Never Use Float/Double for Money

```java
// WRONG - Floating point errors compound
double balance = 100.10;
balance -= 0.1;
System.out.println(balance);  // 100.00000000000001 !!!

// CORRECT - Always construct from String
BigDecimal balance = new BigDecimal("100.10");  // From STRING!
balance = balance.subtract(new BigDecimal("0.10"));
System.out.println(balance);  // 100.00

// WRONG - Don't do this
BigDecimal wrong = new BigDecimal(100.10);  // Precision lost at double level
```

---

## 5. System Design

### 5.1 Event Sourcing (Revolut Uses This)

**What:** Store all state changes as immutable events, not just current state.

```
Traditional: Account balance = $500 (just current state)

Event Sourced:
  [AccountCreated, $1000] → [Withdrawal, $200] → [Deposit, $50] → [Withdrawal, $350]
  Can replay to get $500, or see full history
```

**Why Revolut Uses It:**

- Audit trail (regulatory requirement)
- Can replay events for recovery
- Natural fit for financial systems

### 5.2 CQRS (Command Query Responsibility Segregation)

```
Commands (Writes)              Queries (Reads)
     |                              |
     v                              v
Command Handler               Query Handler
     |                              |
     v                              v
Write Model DB                Read Model DB
(Normalized, ACID)            (Denormalized, fast)
     |
     +---> Event Bus (synchronizes read model)
```

**Why:** Payments need strong consistency, reports can be eventually consistent.

### 5.3 Idempotency (Critical for Payments)

```python
# Problem: User clicks "Send Money" twice rapidly
# Solution: Idempotency key

POST /transfers
Headers: Idempotency-Key: "abc-123-def"
Body: { from: "A", to: "B", amount: 100 }

# Server-side:
def transfer(request):
    key = request.headers['Idempotency-Key']

    # Check if already processed
    if cache.exists(key):
        return cache.get(key)  # Return same response

    # Process transfer
    result = process_transfer(request.body)

    # Cache result
    cache.set(key, result, ttl=24_hours)
    return result
```

### 5.4 5-Step System Design Framework

1. **Clarify Requirements** (5 min)
   - Functional: What are the main use cases?
   - Non-functional: Scale, latency, consistency?

2. **Back-of-Envelope Estimation** (3 min)
   - TPS calculation: Users × Actions / Seconds
   - Storage: Records × Size × Retention

3. **High-Level Architecture** (10 min)
   - Draw boxes: API Gateway, Services, Databases
   - Identify data flow

4. **Detailed Component Design** (15 min)
   - Database schema
   - API contracts
   - Critical algorithms

5. **Trade-offs & Failure Modes** (5 min)
   - What if X fails?
   - Consistency vs availability choice

### 5.5 CAP Theorem in Practice

**For Revolut:**

- **Payments:** Choose CP (Consistency + Partition Tolerance)
  - Cannot accept stale balance data
  - Accept temporary unavailability

- **Notifications:** Choose AP (Availability + Partition Tolerance)
  - User sees "Pending" until notification arrives
  - Eventually consistent is fine

---

## 6. Language Internals

### 6.1 Java HashMap Internals

**Structure:**

- Array of buckets (default 16)
- Each bucket: linked list OR red-black tree (Java 8+)
- Load factor: 0.75 (rehash when 75% full)

**Time Complexity:**

- Average: O(1) for get/put
- Worst case: O(n) with all collisions
- Java 8+: O(log n) with tree bins (when bucket size ≥ 8)

**equals() and hashCode() Contract:**

```java
// RULE 1: If a.equals(b), then a.hashCode() == b.hashCode()
// RULE 2: If a.hashCode() == b.hashCode(), a.equals(b) may be false

// Interview Question: "Can unequal objects have the same hashCode?"
// Answer: YES - this is a hash collision, resolved by equals()
```

### 6.2 Java Garbage Collection

**GC Roots (objects always reachable):**

1. Stack references (local variables)
2. Static fields
3. JNI references
4. Active threads

**Generational GC:**

- Young Generation: New objects, frequent GC
- Old Generation: Long-lived objects, infrequent GC

**Common Collectors:**

- G1 (default in Java 11+): Region-based, predictable pauses
- ZGC: Ultra-low latency (<10ms pauses)

### 6.3 Python Dict Internals

**Structure:**

- Hash table with open addressing (linear probing)
- Load factor triggers resize at 2/3 full
- Python 3.7+: Insertion order preserved

**Time Complexity:**

- Average: O(1) for get/set
- Worst case: O(n) with poor hash function

### 6.4 Python GIL (Global Interpreter Lock)

```python
# GIL = Mutex protecting Python object access
# Impact: Only ONE thread executes Python bytecode at a time

# CPU-bound work: Threading DOESN'T help
import threading
t1 = threading.Thread(target=cpu_intensive_work)
t2 = threading.Thread(target=cpu_intensive_work)
# Both threads take same time as running sequentially!

# Solution for CPU-bound: Use multiprocessing
from multiprocessing import Pool
with Pool(4) as p:
    p.map(cpu_intensive_work, data)  # True parallelism

# I/O-bound work: Threading DOES help (GIL released during I/O)
t1 = threading.Thread(target=fetch_from_network)  # Works!
```

---

## 7. Design Patterns & SOLID

### 7.1 Strategy Pattern (Load Balancer Example)

**Problem:** Hard-coded algorithm prevents extensibility.

**Solution:** Extract algorithm to pluggable interface.

```python
# BAD - Closed for extension
class LoadBalancer:
    def get(self):
        # Hard-coded round-robin
        self.index = (self.index + 1) % len(self.servers)
        return self.servers[self.index]

# GOOD - Open for extension via Strategy
class LoadBalancer:
    def __init__(self, strategy: ServerSelectionStrategy):
        self.strategy = strategy

    def get(self):
        return self.strategy.select_server(self.servers)

# Can add new strategies without modifying LoadBalancer
class LeastConnectionsStrategy(ServerSelectionStrategy):
    def select_server(self, servers):
        return min(servers, key=lambda s: s.connections)
```

### 7.2 SOLID Principles

| Principle                 | Definition                                  | Load Balancer Example                |
| ------------------------- | ------------------------------------------- | ------------------------------------ |
| **S**ingle Responsibility | One reason to change                        | LB manages servers, Strategy selects |
| **O**pen/Closed           | Open for extension, closed for modification | Add strategies without changing LB   |
| **L**iskov Substitution   | Subtypes substitutable                      | Any Strategy works in LB             |
| **I**nterface Segregation | Don't force unused methods                  | Strategy has only `select_server()`  |
| **D**ependency Inversion  | Depend on abstractions                      | LB depends on Strategy interface     |

### 7.3 From Rejection to Acceptance

**What Got Rejected (Java):**

```java
public class LoadBalancer {
    public String addInstance(Server server) {
        if (servers.size() >= 10) return "We can't add";  // String!
        servers.add(server);
        return "Successfully added";  // String!
    }
    // MISSING: getServer(), deRegister()
}
```

**What Gets Accepted:**

```java
public class LoadBalancer {
    private final ServerSelectionStrategy strategy;

    public LoadBalancer(ServerSelectionStrategy strategy) {
        this.strategy = strategy;
    }

    public void register(Server server) throws ServerLimitException {
        if (servers.size() >= maxServers) {
            throw new ServerLimitException("Max capacity reached");
        }
        servers.add(server);
    }

    public Server getServer() throws NoServerException {
        return strategy.select(servers);
    }

    public void deRegister(Server server) {
        servers.remove(server);
    }
}
```

---

## 8. Quick Reference Cheatsheets

### 8.1 Pre-Interview Checklist

**Coding Round:**

- [ ] Strategy pattern for extensibility
- [ ] Thread-safe with Lock/synchronized
- [ ] Exceptions, not string returns
- [ ] All core methods implemented
- [ ] 2-3 unit tests

**Technical Discussion:**

- [ ] Deadlock prevention via lock ordering
- [ ] ACID properties with examples
- [ ] Isolation levels (which prevents what)
- [ ] BigDecimal for money
- [ ] HashMap internals (Java 8+ tree bins)

**System Design:**

- [ ] Clarify requirements first
- [ ] Draw architecture diagram
- [ ] Discuss trade-offs
- [ ] Mention idempotency for payments
- [ ] Event sourcing for audit trails

**Production Setup:**

- [ ] `uv init` + `uv add` to scaffold project
- [ ] Multi-stage Dockerfile with non-root user
- [ ] Health check endpoint + Docker HEALTHCHECK
- [ ] Config via environment variables (pydantic-settings)
- [ ] `uv run pytest` and `uv run ruff` for tests/linting

### 8.2 Common Interview Questions

| Question                  | Key Points                                             |
| ------------------------- | ------------------------------------------------------ |
| Design load balancer      | Strategy pattern, thread-safe, get/register/unregister |
| Money transfer            | Lock ordering, BigDecimal, ACID                        |
| HashMap complexity        | O(1) avg, O(log n) worst with trees                    |
| Isolation levels          | Read Uncommitted → Serializable                        |
| Deadlock prevention       | Consistent lock ordering by ID                         |
| Python GIL                | Limits CPU parallelism, use multiprocessing            |
| Optimistic vs Pessimistic | Version fields vs SELECT FOR UPDATE                    |

### 8.3 Red Flags to Avoid

| Red Flag                                            | Fix                               |
| --------------------------------------------------- | --------------------------------- |
| `return "Successfully added"`                       | Return boolean or throw exception |
| `double balance = 100.0`                            | Use `BigDecimal("100.00")`        |
| No `getServer()` method                             | Core feature - must implement     |
| Hard-coded algorithm                                | Use Strategy pattern              |
| No thread-safety tests                              | Add concurrent access tests       |
| `synchronized(accountA) { synchronized(accountB) }` | Lock by ID order                  |

### 8.4 45-Minute Coding Template

```
Minutes 0-5:   Clarify requirements, sketch interface
Minutes 5-20:  Implement core functionality (make it WORK)
Minutes 20-35: Add thread-safety, error handling (make it SOLID)
Minutes 35-45: Write 2-3 tests, explain design choices
```

**Priority Order:** Working code > SOLID design > Thread-safe > Beautiful

---

## Appendix: Interview Process Tips

### What Interviewers Look For

1. **Communication:** Explain your thinking out loud
2. **Clarifying questions:** Don't assume, ask
3. **Trade-offs:** Acknowledge alternatives
4. **Testing mindset:** Mention edge cases
5. **Production awareness:** Consider failures

### Positive Signals

- "I'm using Strategy pattern so we can add new algorithms later"
- "Lock ordering by account ID prevents deadlock"
- "BigDecimal because float loses precision for money"
- "Let me write a test for the concurrent case"

### Negative Signals

- Coding without understanding requirements
- Ignoring thread safety in multi-user context
- Using double/float for financial data
- Not testing edge cases
- Over-engineering simple problems

---

## 9. Production Setup

> Revolut's #1 rejection reason is "not production-ready." Showing you can package, configure, and deploy your code as a real service is a strong signal.

### 9.1 Project Structure (uv + FastAPI)

```
load-balancer/
├── pyproject.toml
├── uv.lock
├── Dockerfile
├── docker-compose.yml
├── src/
│   └── load_balancer/
│       ├── __init__.py
│       ├── app.py           # FastAPI application
│       ├── models.py         # Pydantic schemas
│       ├── services.py       # Core business logic (LoadBalancer class)
│       ├── strategies.py     # Strategy pattern implementations
│       ├── exceptions.py     # Custom exceptions
│       └── config.py         # Settings via pydantic-settings
├── tests/
│   ├── __init__.py
│   ├── test_services.py
│   ├── test_strategies.py
│   └── test_api.py
└── README.md
```

### 9.2 pyproject.toml (uv)

```toml
[project]
name = "load-balancer"
version = "0.1.0"
description = "Production-ready load balancer service"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.34.0",
    "pydantic-settings>=2.7.0",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-cov>=6.0",
    "httpx>=0.28.0",
    "ruff>=0.9.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.ruff]
target-version = "py312"
line-length = 120

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "SIM"]
```

### 9.3 Configuration (pydantic-settings)

```python
# src/load_balancer/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    max_instances: int = 10
    default_strategy: str = "round_robin"
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"

    model_config = {"env_prefix": "LB_"}
```

### 9.4 FastAPI Application

```python
# src/load_balancer/app.py
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi import HTTPException

from load_balancer.config import Settings
from load_balancer.exceptions import NoServersAvailableError
from load_balancer.models import RegisterRequest
from load_balancer.models import ServerResponse
from load_balancer.models import StatusResponse
from load_balancer.services import LoadBalancer
from load_balancer.strategies import RoundRobinSelectionStrategy

settings = Settings()
lb: LoadBalancer

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    global lb
    lb = LoadBalancer(
        max_instances=settings.max_instances,
        strategy=RoundRobinSelectionStrategy(),
    )
    yield

app = FastAPI(title="Load Balancer", version="0.1.0", lifespan=lifespan)

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}

@app.post("/servers", status_code=201)
def register_server(request: RegisterRequest) -> StatusResponse:
    if not lb.register(request.address):
        raise HTTPException(status_code=409, detail="Server already registered or limit reached")
    return StatusResponse(success=True, message=f"Registered {request.address}")

@app.delete("/servers/{address}")
def unregister_server(address: str) -> StatusResponse:
    if not lb.unregister(address):
        raise HTTPException(status_code=404, detail="Server not found")
    return StatusResponse(success=True, message=f"Unregistered {address}")

@app.get("/servers/next")
def get_server() -> ServerResponse:
    try:
        server = lb.get()
        return ServerResponse(address=server)
    except NoServersAvailableError:
        raise HTTPException(status_code=503, detail="No servers available")
```

### 9.5 Pydantic Models

```python
# src/load_balancer/models.py
from pydantic import BaseModel

class RegisterRequest(BaseModel):
    address: str

class ServerResponse(BaseModel):
    address: str

class StatusResponse(BaseModel):
    success: bool
    message: str
```

### 9.6 Dockerfile (Multi-Stage with uv)

```dockerfile
# --- Build stage ---
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install dependencies first (layer caching)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy source and install project
COPY src/ src/
RUN uv sync --frozen --no-dev

# --- Runtime stage ---
FROM python:3.12-slim

WORKDIR /app

# Copy the virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH"

# Non-root user for security
RUN useradd --create-home appuser
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "load_balancer.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 9.7 Docker Compose (Local Dev)

```yaml
services:
  load-balancer:
    build: .
    ports:
      - "8000:8000"
    environment:
      - LB_MAX_INSTANCES=10
      - LB_DEFAULT_STRATEGY=round_robin
      - LB_LOG_LEVEL=debug
    healthcheck:
      test:
        [
          "CMD",
          "python",
          "-c",
          "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')",
        ]
      interval: 10s
      timeout: 3s
      retries: 3
    restart: unless-stopped
```

### 9.8 Common Commands

```bash
# Project setup
uv init load-balancer
cd load-balancer
uv add fastapi "uvicorn[standard]" pydantic-settings
uv add --group dev pytest pytest-cov httpx ruff

# Development
uv run uvicorn load_balancer.app:app --reload        # Dev server
uv run pytest --cov=load_balancer                     # Tests with coverage
uv run ruff check src/ tests/                         # Linting
uv run ruff format src/ tests/                        # Formatting

# Docker
docker build -t load-balancer .                       # Build image
docker run -p 8000:8000 load-balancer                 # Run container
docker compose up --build                             # Build + run with compose

# Testing the running service
curl http://localhost:8000/health
curl -X POST http://localhost:8000/servers -H "Content-Type: application/json" -d '{"address": "10.0.0.1:8080"}'
curl http://localhost:8000/servers/next
```

### 9.9 Why This Matters in the Interview

| Signal                              | What It Shows                                   |
| ----------------------------------- | ----------------------------------------------- |
| `pyproject.toml` with uv            | Modern Python tooling, reproducible builds      |
| Multi-stage Dockerfile              | Understands image size, build caching, security |
| Non-root user in container          | Security awareness                              |
| Health check endpoint               | Operability, production mindset                 |
| `pydantic-settings` with env prefix | 12-factor app config, no hardcoded values       |
| Separation: services / strategies   | Clean architecture matches the coding challenge |
| `uv.lock`                           | Deterministic dependency resolution             |
| `--frozen` in Dockerfile            | Ensures lock file is respected in CI/CD         |

### 9.10 Pre-Interview Checklist (Production Setup)

- [ ] Can scaffold a project with `uv init` + `uv add` in under 2 minutes
- [ ] Can write a multi-stage Dockerfile from memory
- [ ] Can explain why non-root user, health checks, and env-based config matter
- [ ] Can wrap any coding challenge (load balancer, URL shortener) in FastAPI
- [ ] Can run tests with `uv run pytest` and lint with `uv run ruff`
- [ ] Can explain the difference between `uv sync` and `uv sync --frozen`

---

## 10. Interview Questions Bank

> Sourced from 120+ Glassdoor reviews across Senior SWE, Senior Java, Senior Python, and Lead SWE roles.

### 10.1 HR / Recruiter Screening Questions

These are asked in the first 20-45 min call. Recruiters often follow a script and expect concise, keyword-rich answers.

**Technical Screening:**

1. What's the time complexity of a lookup in a HashMap?
2. Can elements be not equal if they have the same hashCode?
3. What is a database transaction?
4. List database transaction isolation levels.
5. What transaction isolation level would you use for online payment processing?
6. ACID principles — explain each, especially atomicity.
7. What are the problems of concurrency?
8. How can we implement concurrency in Java?
9. What does CQRS stand for? Explain it.
10. What is the GIL in Python?
11. What are the time complexity and worst-case for lookup in Python Dictionaries?
12. What data structures are used in DB indexes?
13. What is the difference between concurrency and parallelism?
14. What are the SOLID principles?
15. What is the worst-case complexity of Quicksort?
16. Computational complexity of common data structures.
17. Talk about the Memento pattern.
18. Describe a given pattern in microservices architectures.
19. How do you ensure and measure code quality?
20. TDD — what is it and what other approaches do you use?
21. What data structure would you use for DB search by ID?
22. Questions about metrics, traces, Prometheus, and Loki (observability team).

**Experience / Behavioural:**

1. Describe your previous work experiences.
2. Describe a project you delivered end-to-end in depth — focus on innovation and initiative.
3. What infrastructure was used on your last project?
4. What were your responsibilities?
5. What tech tasks did you solve?
6. What problem did the product solve?
7. What was the team structure?
8. Why have you decided to leave?

### 10.2 Live Coding Questions

The coding round is 45-60 min. Requirements are given iteratively. TDD is expected. The three recurring tasks:

**Load Balancer (most common — 30+ reports):**

1. Implement a Load Balancer with `register()`, `unregister()`, and `get()` methods.
2. Add random and round-robin server selection strategies.
3. Add thread safety to the registry.
4. Store up to N server instances (configurable max).
5. Implement with TDD style — tests alongside each step.
6. Extra requirements added once initial implementation is complete.
7. Questions about time complexity of your solution.
8. "Why did you use a Set instead of a List here?"
9. "How would you apply design patterns to this solution?"

**URL Shortener (second most common):**

1. Implement a URL shortener service with `shorten()` and `unshorten()` methods.
2. Add concurrent user support with thread safety.
3. Limit storage to 100 URLs.
4. Ensure duplicate full URLs return the existing short URL (idempotency).
5. Implement with TDD — write tests before methods.
6. Add input validation for URL format.

**Money Transfer / Banking:**

1. Implement money transfer method for a Java/Python library.
2. Implement a thread-safe Account Ledger given a skeleton.
3. Implement a simplified banking transaction system.
4. How to achieve consistency and avoid double-spending money?
5. Write concurrent code — implement using Java concurrency mechanisms, then using database locking mechanisms.

**Other Coding Tasks:**

1. Circuit breaker coding task.
2. Design a thread-safe service registry.
3. Implement a service with simple business logic and incrementally evolving requirements (TDD style).
4. Working with random String generators.

### 10.3 Technical Deep-Dive Questions

Asked in the 1-hour technical round. Expect deep follow-ups.

**Concurrency & Threading:**

1. Concurrent collections and their usage.
2. Java concurrency internals: locks, synchronized, volatile, thread pools.
3. How does HashMap work internally under concurrent access?
4. What is the difference between volatile and synchronized?
5. How to prevent shared resources from being accessed by multiple threads?
6. Race conditions and deadlock — explain and prevent.
7. How would you handle concurrent requests in a load balancer?
8. Add concurrency / thread-safety to an existing solution.

**Databases:**

1. ACID properties — explain with examples.
2. What are transaction isolation levels? Which prevents what?
3. What are the differences between optimistic and pessimistic locking?
4. What are DB indexes and when would you avoid them?
5. Internal database data structures (B-trees, LSM trees).
6. Sharding and partitioning strategies.
7. PostgreSQL isolation levels specifically.

**Language Internals:**

1. How does garbage collection work? (Java and/or Python)
2. How are Python dicts implemented internally?
3. HashMap internals — what happens at bucket size >= 8? (Java 8+ tree bins)
4. Python design patterns.
5. Java design patterns — especially Strategy, Observer, Memento.

### 10.4 System Design Questions

Asked in the 1-hour system design round. Expect to discuss APIs, schemas, trade-offs, and failure modes.

1. Build a top-level design for a system responsible for temporary debit card issuance.
2. System Design an Apartment Booking application with a 3rd party API integration.
3. Design a system for delivering physical cards to customers.
4. Design a payment notification service at scale.
5. Design a distributed rate limiter.
6. Design a notification service at scale.
7. Design a system to store and retrieve logging data — consider all components.
8. System design challenge for a payment and top-up system.
9. Design a URL shortener at scale (system design variant, not coding).
10. CQRS and Event-driven architecture — when and why?
11. CAP theorem — give examples for payment vs notification systems.
12. Multithreading, partitioning, sharding, transaction isolation levels, DB indexes (Designing Data-Intensive Applications style).

### 10.5 LeetCode Questions (Tagged to Revolut)

| #    | Problem                            | Difficulty | Acceptance |
| ---- | ---------------------------------- | ---------- | ---------- |
| 14   | Longest Common Prefix              | Easy       | 47.1%      |
| 21   | Merge Two Sorted Lists             | Easy       | 67.9%      |
| 83   | Remove Duplicates from Sorted List | Easy       | 56.2%      |
| 92   | Reverse Linked List II             | Medium     | 51.0%      |
| 257  | Binary Tree Paths                  | Easy       | 68.2%      |
| 268  | Missing Number                     | Easy       | 71.6%      |
| 279  | Perfect Squares                    | Medium     | 56.3%      |
| 438  | Find All Anagrams in a String      | Medium     | 53.3%      |
| 528  | Random Pick with Weight            | Medium     | 48.9%      |
| 535  | Encode and Decode TinyURL          | Medium     | 86.6%      |
| 1321 | Restaurant Growth                  | Medium     | 58.2%      |
| 2043 | Simple Bank System                 | Medium     | 69.8%      |

---

_Generated from analysis of 120+ Revolut interview reviews and 6 code repositories_
_Validated by adversarial review agents with corrections applied_

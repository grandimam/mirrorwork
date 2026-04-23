# Concurrency & Threading in Python — Complete Guide

## Table of Contents

### Part 1 — Foundations

1. [Threads & Processes](#1-threads--processes)
2. [Creating Your First Thread](#2-creating-your-first-thread)
3. [Shared State — It Breaks](#3-shared-state--it-breaks)
4. [The GIL](#4-the-gil-global-interpreter-lock)
5. [Atomic Operations](#5-atomic-operations--what-is-safe)
6. [Locks — The Fix](#6-locks--the-fix)

### Part 2 — Building Up

7. [Beyond Locks](#7-beyond-locks--more-synchronization-primitives)
8. [Thread-Safe Data Structures](#8-thread-safe-data-structures)
9. [Common Concurrency Patterns](#9-common-concurrency-patterns)

### Part 3 — Production Tools

10. [`concurrent.futures`](#10-concurrentfutures--high-level-interface)
11. [`asyncio`](#11-asyncio--cooperative-concurrency)
12. [`multiprocessing`](#12-multiprocessing--true-parallelism)
13. [Choosing the Right Tool](#13-choosing-the-right-tool)

### Part 4 — Interview Ready

14. [Concurrency Theory](#14-concurrency-theory)
    - [Race Conditions](#141-race-conditions)
    - [Deadlock](#142-deadlock)
    - [Starvation](#143-starvation)
    - [Livelock](#144-livelock)
15. [Testing Concurrent Code](#15-testing-concurrent-code)
16. [Real-World Patterns](#16-real-world-patterns)
17. [Applied Interview Problems (Revolut)](#17-applied-interview-problems-revolut)
18. [Interview Question Checklist](#18-interview-question-checklist)

# Part 1 — Foundations

## 1. Threads & Processes

A **process** is a running program — it has its own memory space, its own Python interpreter, its own everything. When you run `python app.py`, that's one process.

A **thread** is a lightweight unit of execution **within** a process. Multiple threads share the same memory space — same variables, same objects, same heap. This is both their power (easy data sharing) and their danger (concurrent access to shared state).

```
Process A                    Process B
┌──────────────────┐         ┌──────────────────┐
│ Memory Space A   │         │ Memory Space B   │
│ ┌──────┐┌──────┐ │         │ ┌──────┐         │
│ │Thread││Thread│ │         │ │Thread│         │
│ │  1   ││  2   │ │         │ │  1   │         │
│ └──────┘└──────┘ │         │ └──────┘         │
│  shared memory   │         │  own memory      │
└──────────────────┘         └──────────────────┘
     can't see each other's memory
```

### Concurrency vs Parallelism

Concurrency is about dealing with a lot of things. The execution is interleaved, and can be achived using a single-core. Parallelism is about doing a lot of things at the same time, execution is simultanous.

```
| Aspect      | Concurrency            | Parallelism       |
| ----------- | ---------------------- | ----------------- |
| Execution   | Interleaved            | Simultaneous      |
| CPU cores   | Can use 1              | Requires multiple |
| Python tool | `threading`, `asyncio` | `multiprocessing` |
| Best for    | I/O-bound              | CPU-bound         |
```

### Why Concurrency?

A single thread processes one thing at a time. When it hits I/O (network call, DB query, file read), it **blocks** — just sits there waiting. With 1000 incoming HTTP requests, a single-threaded server handles them one by one. If each takes 100ms of I/O wait, that's 100 seconds for 1000 requests. Concurrency lets other work happen during that wait time.

> **Interview hook**: "Why would you use threading in a payments API?" → Because the bottleneck is I/O (DB queries, external API calls), not computation. Threads let you overlap the waiting.

---

## 2. Creating Your First Thread

Before theory, let's use threads.

```python
import threading
from typing import Any

# Method 1: Pass a target function
def worker(name: str) -> None:
    print(f"Thread {name} running on {threading.current_thread().name}")

t: threading.Thread = threading.Thread(target=worker, args=("A",), name="worker-A")
t.start()
t.join()  # Block until thread completes

# Method 2: Subclass Thread
class WorkerThread(threading.Thread):
    def __init__(self, name: str) -> None:
        super().__init__(name=name)
        self.result: Any = None

    def run(self) -> None:
        self.result = f"Completed by {self.name}"

wt: WorkerThread = WorkerThread(name="worker-B")
wt.start()
wt.join()
print(wt.result)
```

### Daemon Threads

```python
# Daemon threads are killed when the main thread exits
# Non-daemon threads keep the program alive

daemon_t: threading.Thread = threading.Thread(target=worker, args=("bg",), daemon=True)
daemon_t.start()
# If main thread ends here, daemon_t is killed immediately

# Use case: background logging, heartbeat checks, cache cleanup
```

### Thread-Local Data

```python
# Each thread gets its own copy of thread-local data
local_data: threading.local = threading.local()

def process_request(request_id: int) -> None:
    local_data.request_id = request_id  # Each thread has its own value
    handle_request()

def handle_request() -> None:
    print(f"Handling request {local_data.request_id}")  # Reads thread's own value
```

---

## 3. Shared State — It Breaks

Now let's see what goes wrong when threads share state.

```python
import threading

counter: int = 0

def increment(n: int) -> None:
    global counter
    for _ in range(n):
        counter += 1  # Looks simple. What could go wrong?

threads: list[threading.Thread] = [
    threading.Thread(target=increment, args=(1_000_000,))
    for _ in range(4)
]

for t in threads:
    t.start()
for t in threads:
    t.join()

print(counter)  # Expected: 4_000_000, Actual: ~2_500_000 — WRONG!
```

Why? Because `counter += 1` is **not one operation**. It's three:

```
LOAD_GLOBAL   counter    # 1. read current value
BINARY_ADD    1          # 2. compute new value
STORE_GLOBAL  counter    # 3. write it back
```

And threads can interleave between any of these steps:

```
Thread A: LOAD counter  → gets 0
    ── thread switch ──
Thread B: LOAD counter  → gets 0 (stale!)
Thread B: ADD           → computes 1
Thread B: STORE counter → writes 1
    ── thread switch ──
Thread A: ADD           → computes 1 (from stale 0)
Thread A: STORE counter → writes 1  ← should be 2!
```

### Three Forms of Race Conditions

Every concurrency bug comes down to one thing: **a non-atomic read-modify-write on shared state**. It takes three forms in interviews:

```python
# Form 1: check-then-act
if name not in registry:     # Thread A checks
    registry.append(name)    # Thread B also checked, both insert → duplicate

# Form 2: read-modify-write
counter += 1                 # LOAD → ADD → STORE, interleaved

# Form 3: compound operation
if len(servers) > 0:         # Thread A checks
    return servers.pop()     # Thread B popped in between → IndexError
```

> **Every Revolut concurrency question is testing whether you can spot one of these three forms.**

---

## 4. The GIL (Global Interpreter Lock)

The GIL is a mutex in CPython that allows only **one thread to execute Python bytecode at a time**. GIL is released during I/O or time.sleep or any compound operations.

### Why it exists

- CPython's memory management (reference counting) is not thread-safe
- The GIL protects `ob_refcnt` on every Python object from race conditions
- Without it, even simple operations like `a = b` could corrupt memory

### What the GIL protects vs. what it doesn't

```
GIL protects:                          GIL does NOT protect:
  ✓ CPython internals (refcounts)        ✗ YOUR logic spanning multiple bytecodes
  ✓ Single bytecode instruction          ✗ Compound operations (+=, check-then-act)
  ✓ Interpreter data structures          ✗ Any operation during I/O (GIL released)
```

The GIL can switch threads **between** bytecode instructions. `counter += 1` is three instructions. That's where the race happens.

### When the GIL is released

```python
# GIL is released during:
# 1. I/O operations (file, network, database)
# 2. time.sleep()
# 3. C extension calls (numpy, pandas operations)
# 4. Waiting on locks/conditions

# This is why threading WORKS for I/O-bound tasks:
import urllib.request

def fetch(url: str) -> bytes:
    return urllib.request.urlopen(url).read()  # GIL released during network I/O
```

## 5. Atomic Operations — What IS Safe

Due to the GIL, some operations in CPython are **accidentally atomic** — but you should NOT rely on this.

```python
# These are atomic in CPython (but NOT guaranteed by the language spec):
x: int = 0
x = 42              # STORE_FAST — single bytecode
items: list = [1, 2, 3]
items.append(4)     # Atomic
items.pop()         # Atomic
d: dict = {}
d["key"] = "value"  # Atomic

# These are NOT atomic:
x += 1              # LOAD, ADD, STORE — three operations
d[k] = d.get(k, 0) + 1  # Read-modify-write
```

**The Two Rules:**

1. **Single operation on a built-in** (`append`, `pop`, `dict[k] = v`) → atomic in CPython, safe by accident. This is a CPython implementation detail, not a language guarantee — PyPy, Jython, free-threaded Python (3.13+) may not preserve this.

2. **Multiple operations that depend on each other** → always needs a lock, regardless of individual atomicity. The danger is the **gap between operations**, not any single operation:

```python
# Each line below is individually atomic, but the COMBINATION is not:
if server not in registry:   # atomic read
    registry.add(server)     # atomic write — but another thread could have added between these two lines
```

> **Interview answer for "is `list.append` thread-safe?"**: "Yes in CPython due to the GIL, but I wouldn't rely on it — it's an implementation detail. And it doesn't matter anyway, because the real danger is compound operations around it."

---

## 6. Locks — The Fix

Now that we understand the problem (Section 3) and why the GIL doesn't help (Section 4), here's the fix.

A lock makes a section of code **mutually exclusive** — only one thread can enter at a time.

Key insight: **lock the entire read-modify-write, not just the write**.

```python
# WRONG — lock only protects the write
if name not in registry:        # unprotected read
    with lock:
        registry.append(name)   # protected write — but the check wasn't!

# RIGHT — lock protects the whole operation
with lock:
    if name not in registry:
        registry.append(name)
```

> **Interview context**: when they ask "how do you make this thread-safe?" — identify the compound operation, wrap the entire thing in a lock.

### 6.1 Lock (Mutex)

The most basic synchronization primitive. Only one thread can hold it at a time.

```python
from threading import Lock

lock: Lock = Lock()
balance: int = 0

def deposit(amount: int) -> None:
    global balance
    lock.acquire()
    try:
        balance += amount
    finally:
        lock.release()  # ALWAYS release in finally

# Better: use as context manager
def withdraw(amount: int) -> None:
    global balance
    with lock:  # Automatically acquires and releases
        if balance >= amount:
            balance -= amount
```

**Non-blocking acquire:**

```python
if lock.acquire(blocking=False):
    try:
        # Got the lock, do work
        pass
    finally:
        lock.release()
else:
    # Lock is held by another thread, do something else
    pass

# With timeout
if lock.acquire(timeout=5.0):
    try:
        pass
    finally:
        lock.release()
```

### 6.2 RLock (Reentrant Lock)

A lock that can be acquired multiple times by the **same thread** without deadlocking.

```python
from threading import RLock

rlock: RLock = RLock()

def outer() -> None:
    with rlock:
        inner()  # Same thread can re-acquire

def inner() -> None:
    with rlock:  # Would DEADLOCK with regular Lock!
        print("Inner called")

# Use case: recursive functions, calling methods that also lock
```

**Lock vs RLock:**

| Feature                 | Lock                    | RLock                                |
| ----------------------- | ----------------------- | ------------------------------------ |
| Same thread re-acquire  | Deadlock                | Allowed                              |
| Must release same count | N/A                     | Yes (acquire count == release count) |
| Performance             | Faster                  | Slightly slower                      |
| Use when                | Simple mutual exclusion | Nested/recursive locking             |

---

# Part 2 — Building Up

## 7. Beyond Locks — More Synchronization Primitives

Locks solve mutual exclusion. But concurrency has more coordination problems. Each primitive below solves a specific one.

| Primitive     | Problem it solves                    | Interview scenario                   |
| ------------- | ------------------------------------ | ------------------------------------ |
| **Lock**      | Mutual exclusion                     | "Make this thread-safe"              |
| **RLock**     | Nested locking                       | "Method calls another locked method" |
| **Condition** | "Wait until X is true"               | Producer-consumer, bounded buffer    |
| **Semaphore** | "Allow N concurrent"                 | Connection pool, rate limiting       |
| **Event**     | "Signal once, many waiters"          | "Server ready" flag                  |
| **Barrier**   | "All must arrive before any proceed" | Phased computation                   |

### 7.1 Condition

Allows threads to wait for a specific condition to become true.

```python
from threading import Condition
from collections import deque
from typing import Any

condition: Condition = Condition()
queue: deque[Any] = deque()
MAX_SIZE: int = 10

def producer() -> None:
    while True:
        with condition:
            while len(queue) >= MAX_SIZE:
                condition.wait()  # Release lock and sleep until notified
            queue.append(produce_item())
            condition.notify()  # Wake one waiting consumer

def consumer() -> None:
    while True:
        with condition:
            while len(queue) == 0:
                condition.wait()  # Release lock and sleep until notified
            item = queue.popleft()
            condition.notify()  # Wake one waiting producer
        process(item)

def produce_item() -> str:
    return "item"

def process(item: Any) -> None:
    pass
```

**Why `while` not `if` before `wait()`:**

```python
# WRONG — spurious wakeups can occur
with condition:
    if len(queue) == 0:  # BUG: might wake up when queue is still empty
        condition.wait()

# CORRECT — re-check after wakeup
with condition:
    while len(queue) == 0:  # Re-check condition after every wakeup
        condition.wait()
```

### 7.2 Semaphore

Controls access to a shared resource with a limited number of slots.

```python
from threading import Semaphore, BoundedSemaphore

# Allow up to 5 concurrent connections
connection_pool: Semaphore = Semaphore(value=5)

def connect_to_db() -> None:
    connection_pool.acquire()  # Decrements counter; blocks if 0
    try:
        # Use connection (max 5 threads here simultaneously)
        pass
    finally:
        connection_pool.release()  # Increments counter

# BoundedSemaphore — raises ValueError if released more than acquired
bounded: BoundedSemaphore = BoundedSemaphore(value=3)
# bounded.release() without acquire → ValueError (catches bugs)
```

**Semaphore vs Lock:**

| Feature                | Lock               | Semaphore                       |
| ---------------------- | ------------------ | ------------------------------- |
| Max concurrent holders | 1                  | N (configurable)                |
| Use case               | Mutual exclusion   | Rate limiting, connection pools |
| Binary Semaphore(1)    | Equivalent to Lock | Same but no ownership tracking  |

### 7.3 Event

A simple flag that threads can wait on.

```python
from threading import Event

startup_complete: Event = Event()

def server() -> None:
    # Initialize server...
    startup_complete.set()  # Signal that server is ready

def client() -> None:
    startup_complete.wait()  # Block until server signals ready
    # Safe to connect now

def client_with_timeout() -> None:
    if startup_complete.wait(timeout=10.0):
        # Server started
        pass
    else:
        raise TimeoutError("Server did not start in time")

# Reset for reuse
startup_complete.clear()  # Reset to unset state
```

### 7.4 Barrier

Synchronization point where N threads must all arrive before any can proceed.

```python
from threading import Barrier

barrier: Barrier = Barrier(parties=3)

def worker(worker_id: int) -> None:
    # Phase 1: Initialize
    print(f"Worker {worker_id} initializing...")

    barrier.wait()  # All 3 workers must reach here before any proceed

    # Phase 2: Process (only starts after all workers initialized)
    print(f"Worker {worker_id} processing...")
```

### 7.5 Timer

Execute a function after a delay.

```python
from threading import Timer

def heartbeat() -> None:
    print("alive")
    # Schedule next heartbeat (recurring timer pattern)
    t: Timer = Timer(interval=5.0, function=heartbeat)
    t.daemon = True
    t.start()

# Start first heartbeat
heartbeat()

# Cancel a timer before it fires
t: Timer = Timer(interval=10.0, function=lambda: print("boom"))
t.start()
t.cancel()  # Prevent execution if not yet fired
```

---

## 8. Thread-Safe Data Structures

> **Interview tip**: if they ask you to coordinate producers and consumers, reach for `Queue` first, not raw locks + conditions. It shows you know the standard library.

### 8.1 `queue.Queue`

The go-to for producer-consumer patterns. Thread-safe by design.

```python
from queue import Queue, Empty, Full
from threading import Thread

q: Queue[str] = Queue(maxsize=100)

def producer() -> None:
    for i in range(10):
        q.put(f"item-{i}")  # Blocks if full
    q.put(None)  # Sentinel to signal done

def consumer() -> None:
    while True:
        item: str | None = q.get()  # Blocks if empty
        if item is None:
            break
        process(item)
        q.task_done()  # Signal that item processing is complete

def process(item: str) -> None:
    pass

# Non-blocking variants
try:
    q.put_nowait("item")  # Raises Full if queue is full
except Full:
    pass

try:
    item = q.get_nowait()  # Raises Empty if queue is empty
except Empty:
    pass

# Wait for all items to be processed
q.join()  # Blocks until task_done() called for every put()
```

**Queue variants:**

```python
from queue import Queue, LifoQueue, PriorityQueue

fifo: Queue[str] = Queue()           # First-In-First-Out
lifo: LifoQueue[str] = LifoQueue()   # Last-In-First-Out (stack)

pq: PriorityQueue[tuple[int, str]] = PriorityQueue()
pq.put((2, "low priority"))
pq.put((1, "high priority"))
print(pq.get())  # (1, "high priority") — lowest number first
```

### 8.2 `collections.deque`

Thread-safe for `append()` and `popleft()` (atomic in CPython due to GIL), but **not** for compound operations.

```python
from collections import deque

d: deque[int] = deque()
d.append(1)      # Thread-safe (atomic)
d.appendleft(2)  # Thread-safe (atomic)
d.pop()          # Thread-safe (atomic)
d.popleft()      # Thread-safe (atomic)

# NOT thread-safe:
# if len(d) > 0:  # Another thread might pop between check and pop
#     d.pop()      # Can raise IndexError
```

---

## 9. Common Concurrency Patterns

### 9.1 Producer-Consumer

```python
from threading import Thread
from queue import Queue
from typing import Any

def producer(q: Queue[Any], items: list[Any]) -> None:
    for item in items:
        q.put(item)
    q.put(None)  # Poison pill

def consumer(q: Queue[Any]) -> None:
    while True:
        item: Any = q.get()
        if item is None:
            break
        print(f"Processing {item}")
        q.task_done()

q: Queue[Any] = Queue(maxsize=50)
p: Thread = Thread(target=producer, args=(q, range(20)))
c: Thread = Thread(target=consumer, args=(q,))
p.start()
c.start()
p.join()
c.join()
```

### 9.2 Reader-Writer Lock

Multiple readers can read simultaneously, but writers need exclusive access.

```python
from threading import Lock, Condition

class ReadWriteLock:
    def __init__(self) -> None:
        self._readers: int = 0
        self._lock: Lock = Lock()
        self._condition: Condition = Condition(self._lock)

    def acquire_read(self) -> None:
        with self._condition:
            self._readers += 1

    def release_read(self) -> None:
        with self._condition:
            self._readers -= 1
            if self._readers == 0:
                self._condition.notify_all()

    def acquire_write(self) -> None:
        self._condition.acquire()
        while self._readers > 0:
            self._condition.wait()

    def release_write(self) -> None:
        self._condition.notify_all()
        self._condition.release()
```

### 9.3 Thread Pool (Manual)

```python
from threading import Thread
from queue import Queue
from typing import Callable, Any

class ThreadPool:
    def __init__(self, num_workers: int) -> None:
        self._tasks: Queue[Callable[..., Any] | None] = Queue()
        self._workers: list[Thread] = []
        for _ in range(num_workers):
            t: Thread = Thread(target=self._worker, daemon=True)
            t.start()
            self._workers.append(t)

    def _worker(self) -> None:
        while True:
            task: Callable[..., Any] | None = self._tasks.get()
            if task is None:
                break
            try:
                task()
            except Exception as e:
                print(f"Task failed: {e}")
            finally:
                self._tasks.task_done()

    def submit(self, task: Callable[..., Any]) -> None:
        self._tasks.put(task)

    def shutdown(self) -> None:
        for _ in self._workers:
            self._tasks.put(None)
        for w in self._workers:
            w.join()

    def wait(self) -> None:
        self._tasks.join()
```

### 9.4 Deadlock Prevention — Lock Ordering

```python
from threading import Lock
from decimal import Decimal

class Account:
    def __init__(self, account_id: int, balance: Decimal = Decimal("0")) -> None:
        self.account_id: int = account_id
        self.balance: Decimal = balance
        self.lock: Lock = Lock()

def transfer(from_acc: Account, to_acc: Account, amount: Decimal) -> bool:
    # ALWAYS acquire locks in a consistent order (by account_id)
    first: Account = from_acc if from_acc.account_id < to_acc.account_id else to_acc
    second: Account = to_acc if from_acc.account_id < to_acc.account_id else from_acc

    with first.lock, second.lock:
        if from_acc.balance >= amount:
            from_acc.balance -= amount
            to_acc.balance += amount
            return True
        return False

# Without lock ordering:
# Thread 1: lock(A) → lock(B)
# Thread 2: lock(B) → lock(A)  → DEADLOCK

# With lock ordering (by ID):
# Thread 1: lock(A) → lock(B)  (A.id < B.id)
# Thread 2: lock(A) → lock(B)  (A.id < B.id)  → No deadlock possible
```

### 9.5 Double-Checked Locking (Singleton)

```python
from threading import Lock
from typing import ClassVar, Self

class Singleton:
    _instance: ClassVar[Self | None] = None
    _lock: ClassVar[Lock] = Lock()

    def __new__(cls) -> Self:
        if cls._instance is None:  # First check (no lock)
            with cls._lock:
                if cls._instance is None:  # Second check (with lock)
                    cls._instance = super().__new__(cls)
        return cls._instance
```

---

# Part 3 — Production Tools

## 10. `concurrent.futures` — High-Level Interface

This is the "I write production code" answer. You almost never need raw `threading.Thread` in real applications.

> **Interview hook**: "How would you fetch 1000 URLs concurrently?" → `ThreadPoolExecutor` with a bounded pool. Not 1000 threads — that's wasteful. 10-50 workers, tasks queued internally.

### 10.1 ThreadPoolExecutor

```python
from concurrent.futures import ThreadPoolExecutor, Future, as_completed
from typing import Any
import urllib.request

URLS: list[str] = [
    "https://example.com",
    "https://httpbin.org/get",
    "https://jsonplaceholder.typicode.com/posts/1",
]

def fetch(url: str) -> tuple[str, int]:
    response = urllib.request.urlopen(url)
    return url, response.status

# Submit individual tasks
with ThreadPoolExecutor(max_workers=5) as executor:
    futures: list[Future[tuple[str, int]]] = [
        executor.submit(fetch, url) for url in URLS
    ]

    # Process as they complete (not in submission order)
    for future in as_completed(futures):
        try:
            url, status = future.result(timeout=10.0)
            print(f"{url}: {status}")
        except Exception as e:
            print(f"Error: {e}")

# Map (preserves order, simpler API)
with ThreadPoolExecutor(max_workers=5) as executor:
    results: list[tuple[str, int]] = list(executor.map(fetch, URLS))
```

Key distinction:

- `executor.map()` — preserves order, simpler
- `as_completed()` — process fastest first, more efficient

### 10.2 ProcessPoolExecutor

```python
from concurrent.futures import ProcessPoolExecutor
import math

NUMBERS: list[int] = [112272535095293, 112582705942171, 115280095190773]

def is_prime(n: int) -> bool:
    if n < 2:
        return False
    for i in range(2, int(math.sqrt(n)) + 1):
        if n % i == 0:
            return False
    return True

# True parallelism — bypasses the GIL
with ProcessPoolExecutor(max_workers=4) as executor:
    results = list(executor.map(is_prime, NUMBERS))
    for num, prime in zip(NUMBERS, results):
        print(f"{num}: {'prime' if prime else 'composite'}")
```

### 10.3 Future Object API

```python
from concurrent.futures import ThreadPoolExecutor, Future
import time

def slow_task(n: int) -> int:
    time.sleep(n)
    return n * 2

with ThreadPoolExecutor() as executor:
    future: Future[int] = executor.submit(slow_task, 3)

    print(future.done())          # False (still running)
    print(future.running())       # True
    print(future.cancelled())     # False

    result: int = future.result(timeout=10.0)  # Block until done (or timeout)
    print(future.done())          # True

    # Callbacks
    future2: Future[int] = executor.submit(slow_task, 1)
    future2.add_done_callback(lambda f: print(f"Result: {f.result()}"))

    # Cancel (only if not yet started)
    future3: Future[int] = executor.submit(slow_task, 100)
    future3.cancel()  # Returns True if successfully cancelled
```

---

## 11. `asyncio` — Cooperative Concurrency

Threading = OS switches threads preemptively (you don't control when). Asyncio = **you** yield control explicitly with `await`.

**Why asyncio over threading?** Coroutine: ~1KB memory. Thread: ~8MB stack. 10,000 concurrent connections? asyncio. 10,000 threads will OOM.

**Why threading over asyncio?** Blocking libraries (most DB drivers, file I/O, legacy code). `time.sleep` in async code blocks the **entire** event loop.

> **Interview trap**: "What happens if you do CPU-heavy work in an async handler?" → It blocks the event loop. All other coroutines starve. Use `await asyncio.to_thread(cpu_heavy_fn)` to offload.

### 11.1 Core Concepts

```python
import asyncio

# Coroutine — defined with async def, awaited with await
async def fetch_data(url: str) -> str:
    await asyncio.sleep(1)  # Simulates I/O — yields control to event loop
    return f"Data from {url}"

# Running coroutines
async def main() -> None:
    result: str = await fetch_data("https://example.com")
    print(result)

asyncio.run(main())  # Entry point — creates event loop, runs, then closes
```

### 11.2 Tasks and Gathering

```python
import asyncio

async def fetch(url: str, delay: float) -> str:
    await asyncio.sleep(delay)
    return f"Result from {url}"

async def main() -> None:
    # Method 1: gather — run concurrently, collect all results
    results: list[str] = await asyncio.gather(
        fetch("url1", 1.0),
        fetch("url2", 2.0),
        fetch("url3", 0.5),
    )
    # Takes ~2 seconds (not 3.5) — all run concurrently
    print(results)

    # Method 2: create_task — more control
    task1: asyncio.Task[str] = asyncio.create_task(fetch("url1", 1.0))
    task2: asyncio.Task[str] = asyncio.create_task(fetch("url2", 2.0))

    # Do other work while tasks run...
    result1: str = await task1
    result2: str = await task2

    # Method 3: TaskGroup (Python 3.11+) — structured concurrency
    async with asyncio.TaskGroup() as tg:
        t1: asyncio.Task[str] = tg.create_task(fetch("url1", 1.0))
        t2: asyncio.Task[str] = tg.create_task(fetch("url2", 2.0))
    # All tasks guaranteed complete here; exceptions propagate cleanly
    print(t1.result(), t2.result())

asyncio.run(main())
```

### 11.3 Timeouts and Cancellation

```python
import asyncio

async def slow_operation() -> str:
    await asyncio.sleep(10)
    return "done"

async def main() -> None:
    # Timeout with asyncio.wait_for
    try:
        result: str = await asyncio.wait_for(slow_operation(), timeout=2.0)
    except asyncio.TimeoutError:
        print("Operation timed out")

    # Timeout with asyncio.timeout (Python 3.11+)
    try:
        async with asyncio.timeout(2.0):
            result = await slow_operation()
    except TimeoutError:
        print("Timed out")

    # Manual cancellation
    task: asyncio.Task[str] = asyncio.create_task(slow_operation())
    await asyncio.sleep(1)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        print("Task was cancelled")

asyncio.run(main())
```

### 11.4 Async Synchronization Primitives

```python
import asyncio

# Lock
lock: asyncio.Lock = asyncio.Lock()

async def safe_write(data: str) -> None:
    async with lock:
        # Only one coroutine at a time
        pass

# Semaphore — limit concurrent operations
sem: asyncio.Semaphore = asyncio.Semaphore(10)

async def rate_limited_fetch(url: str) -> str:
    async with sem:  # Max 10 concurrent fetches
        await asyncio.sleep(1)
        return f"fetched {url}"

# Event
event: asyncio.Event = asyncio.Event()

async def waiter() -> None:
    await event.wait()
    print("Event fired!")

async def setter() -> None:
    await asyncio.sleep(1)
    event.set()

# Queue
queue: asyncio.Queue[str] = asyncio.Queue(maxsize=100)

async def async_producer() -> None:
    await queue.put("item")

async def async_consumer() -> None:
    item: str = await queue.get()
    queue.task_done()
```

### 11.5 Mixing Asyncio with Threads

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor
import time

def blocking_io(name: str) -> str:
    time.sleep(2)  # Blocking call — cannot be awaited
    return f"Result from {name}"

async def main() -> None:
    loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()

    # Run blocking function in a thread pool (don't block the event loop)
    result: str = await loop.run_in_executor(None, blocking_io, "task-1")
    print(result)

    # With a specific executor
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [
            loop.run_in_executor(pool, blocking_io, f"task-{i}")
            for i in range(4)
        ]
        results: list[str] = await asyncio.gather(*futures)
        print(results)

    # asyncio.to_thread (Python 3.9+) — simpler API
    result = await asyncio.to_thread(blocking_io, "task-2")
    print(result)

asyncio.run(main())
```

---

## 12. `multiprocessing` — True Parallelism

Bypasses the GIL entirely — separate memory spaces, separate Python interpreters. Use for CPU-bound work: image processing, number crunching, ML inference. Don't use for I/O-bound — the process overhead isn't worth it.

Trade-off: data must be **serialized** (pickled) to cross process boundaries. Sharing state requires `Value`, `Array`, or `Manager` — all slower than in-process access.

### 12.1 Process Basics

```python
from multiprocessing import Process, current_process
import os

def worker(name: str) -> None:
    print(f"Worker {name}, PID: {os.getpid()}, Parent: {os.getppid()}")

if __name__ == "__main__":
    processes: list[Process] = []
    for i in range(4):
        p: Process = Process(target=worker, args=(f"P-{i}",))
        p.start()
        processes.append(p)

    for p in processes:
        p.join()
```

### 12.2 Sharing State Between Processes

Processes have **separate memory spaces** — sharing requires explicit mechanisms.

```python
from multiprocessing import Process, Value, Array, Manager
from ctypes import c_int, c_double

# Method 1: Value and Array (shared memory — fast)
counter: Value = Value(c_int, 0)
scores: Array = Array(c_double, [0.0, 0.0, 0.0])

def increment(shared_counter: Value) -> None:
    for _ in range(1000):
        with shared_counter.get_lock():
            shared_counter.value += 1

# Method 2: Manager (proxy objects — slower but more flexible)
with Manager() as manager:
    shared_list: list = manager.list([1, 2, 3])
    shared_dict: dict = manager.dict({"key": "value"})

    def modify(sl: list, sd: dict) -> None:
        sl.append(4)
        sd["new_key"] = "new_value"

    p: Process = Process(target=modify, args=(shared_list, shared_dict))
    p.start()
    p.join()
    print(list(shared_list))  # [1, 2, 3, 4]
```

### 12.3 Inter-Process Communication

```python
from multiprocessing import Process, Queue, Pipe
from multiprocessing.connection import Connection

# Method 1: Queue (thread & process safe)
def producer(q: Queue) -> None:
    q.put("hello from producer")

def consumer(q: Queue) -> None:
    msg: str = q.get()
    print(msg)

q: Queue = Queue()
Process(target=producer, args=(q,)).start()
Process(target=consumer, args=(q,)).start()

# Method 2: Pipe (two-way communication between exactly 2 processes)
parent_conn: Connection
child_conn: Connection
parent_conn, child_conn = Pipe()

def child(conn: Connection) -> None:
    conn.send("hello from child")
    print(conn.recv())  # "hello from parent"
    conn.close()

p: Process = Process(target=child, args=(child_conn,))
p.start()
print(parent_conn.recv())  # "hello from child"
parent_conn.send("hello from parent")
p.join()
```

### 12.4 Pool

```python
from multiprocessing import Pool

def square(n: int) -> int:
    return n ** 2

if __name__ == "__main__":
    with Pool(processes=4) as pool:
        # map — ordered results
        results: list[int] = pool.map(square, range(10))

        # imap — lazy iterator (memory efficient)
        for result in pool.imap(square, range(10)):
            print(result)

        # imap_unordered — results as they complete
        for result in pool.imap_unordered(square, range(10)):
            print(result)

        # apply_async — single task, non-blocking
        future = pool.apply_async(square, (42,))
        print(future.get(timeout=5))  # 1764

        # starmap — multiple arguments
        pairs: list[tuple[int, int]] = [(1, 2), (3, 4), (5, 6)]
        results = pool.starmap(pow, pairs)  # [1, 81, 15625]
```

---

## 13. Choosing the Right Tool

| Dimension         | `threading`               | `asyncio`                      | `multiprocessing`         |
| ----------------- | ------------------------- | ------------------------------ | ------------------------- |
| Concurrency model | Preemptive (OS schedules) | Cooperative (you yield)        | Preemptive (OS schedules) |
| GIL impact        | Blocked for CPU work      | Single-threaded (no GIL issue) | Bypasses GIL              |
| Memory            | Shared                    | Shared                         | Separate (must serialize) |
| Best for          | I/O-bound + legacy libs   | I/O-bound + async libs         | CPU-bound                 |
| Overhead          | ~8MB per thread (stack)   | ~1KB per coroutine             | Full process              |
| Scalability       | Hundreds                  | Tens of thousands              | Tens (process limit)      |
| Debugging         | Hard (race conditions)    | Easier (single thread)         | Hardest (IPC + debugging) |
| Context switch    | OS-level (expensive)      | User-level (cheap)             | OS-level (very expensive) |

### Decision Flowchart

```
Is the bottleneck CPU-bound?
├── Yes → multiprocessing / ProcessPoolExecutor
└── No (I/O-bound)
    ├── Using async-compatible libraries? → asyncio
    └── Using blocking libraries? → threading / ThreadPoolExecutor
```

---

# Part 4 — Interview Ready

## 14. Concurrency Theory

The four classical concurrency hazards — **race conditions**, **deadlocks**, **starvation**, and **livelocks** — account for virtually every concurrency bug you'll encounter or be asked about. This section covers the theory behind each: what causes them, how to identify them, and the formal strategies to prevent them.

### 14.1 Race Conditions

A race condition is when two or more threads access shared mutable state concurrently, and the result depends on the execution order. The bug is that the outcome is non-deterministic — it works 99% of the time, then silently corrupts data on the 1% interleaving you didn't expect

**Data Race vs Race Condition:**

These terms are related but distinct:

| Term               | Definition                                                                                                     | Example                                                                                          |
| ------------------ | -------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| **Data race**      | Two threads access the same memory location concurrently, and at least one is a write, with no synchronization | Two threads doing `counter += 1` without a lock                                                  |
| **Race condition** | Program correctness depends on thread scheduling order                                                         | Check-then-act: `if not full: add()` — even with individual atomic ops, the compound logic races |

A data race is a _mechanism_ (unsynchronized memory access). A race condition is a _symptom_ (incorrect behavior under certain interleavings). You can have a race condition without a data race (when each individual operation is atomic but the compound logic isn't protected), and theoretically a data race without a race condition (benign races, though these are almost always bugs in practice).

**The Three Forms:**

Every concurrency bug in application code reduces to one of these patterns:

```python
# Form 1: Check-then-act (TOCTOU — Time of Check to Time of Use)
if name not in registry:     # Thread A checks → True
                             # Thread B checks → True (interleaved)
    registry.append(name)    # Both threads insert → DUPLICATE

# Form 2: Read-modify-write
counter += 1                 # LOAD → ADD → STORE (3 bytecodes, interleaved)

# Form 3: Compound operation on shared state
if len(servers) > 0:         # Thread A checks → True
                             # Thread B pops the last server
    return servers.pop()     # Thread A pops → IndexError
```

**Why the GIL doesn't prevent race conditions:**

The GIL guarantees that only one thread executes Python bytecode at a time, but it can release between any two bytecodes. `counter += 1` compiles to `LOAD_GLOBAL`, `BINARY_ADD`, `STORE_GLOBAL` — the GIL can switch threads between any of these. The GIL protects CPython's internal reference counts, not your application logic.

**The fix — always lock the entire compound operation:**

```python
from threading import Lock

# WRONG — lock only protects the write, not the check
if name not in registry:        # unprotected read
    with lock:
        registry.append(name)   # protected write — but the check wasn't!

# RIGHT — lock protects the entire check-then-act
with lock:
    if name not in registry:
        registry.append(name)
```

**Memory Visibility:**

In languages with weaker memory models (Java, C++), a thread may write a value that another thread never sees because the write stays in a CPU cache. This is a **visibility** problem, distinct from atomicity. In CPython, the GIL acts as a memory barrier on every thread switch, so visibility issues don't arise in practice. But in free-threaded Python (3.13+, `--disable-gil`), this guarantee disappears — explicit synchronization becomes mandatory for both atomicity and visibility.

### 14.2 Deadlock

A **deadlock** is a state where two or more threads are permanently blocked, each waiting for a resource held by another. No thread can proceed — the system hangs.

**The Four Coffman Conditions (1971):**

A deadlock can only occur if ALL four conditions hold simultaneously:

| Condition               | Definition                                                                | Example                                                                |
| ----------------------- | ------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| **1. Mutual Exclusion** | At least one resource is held in non-sharable mode                        | A lock can only be held by one thread                                  |
| **2. Hold and Wait**    | A thread holds a resource while waiting for another                       | Thread holds `lock_a`, requests `lock_b`                               |
| **3. No Preemption**    | Resources cannot be forcibly taken from a thread                          | Can't force a thread to release its lock                               |
| **4. Circular Wait**    | A circular chain of threads, each waiting for a resource held by the next | Thread 1 waits for Thread 2's lock, Thread 2 waits for Thread 1's lock |

**Classic deadlock example:**

```python
from threading import Lock

lock_a: Lock = Lock()
lock_b: Lock = Lock()

def thread_1() -> None:
    with lock_a:             # Holds lock_a
        with lock_b:         # Waits for lock_b → held by thread_2
            pass

def thread_2() -> None:
    with lock_b:             # Holds lock_b
        with lock_a:         # Waits for lock_a → held by thread_1 → DEADLOCK
            pass
```

**The circular wait is visualized as a resource graph:**

```
Thread 1 ──holds──→ lock_a ──wanted by──→ Thread 2
    ↑                                        │
    └──────── wanted by ← holds ← lock_b ←──┘

Cycle detected → Deadlock
```

**Prevention Strategies — break any one of the four conditions:**

| Strategy                  | Which Condition It Breaks | How                                                                                           |
| ------------------------- | ------------------------- | --------------------------------------------------------------------------------------------- |
| **Lock ordering**         | Circular Wait             | Always acquire locks in a globally consistent order (e.g., by resource ID)                    |
| **Try-lock with timeout** | Hold and Wait             | Use `lock.acquire(timeout=N)` — if you can't get the second lock, release the first and retry |
| **Lock-free algorithms**  | Mutual Exclusion          | Use atomic operations (`queue.Queue`, `collections.deque.append`) instead of locks            |
| **Single lock**           | Hold and Wait             | Use one coarse lock for all resources — simple but reduces concurrency                        |
| **Acquire all at once**   | Hold and Wait             | Request all needed locks atomically before proceeding                                         |

**Strategy 1: Lock Ordering (most important — Revolut's #1 pattern)**

```python
from threading import Lock
from decimal import Decimal

class Account:
    def __init__(self, account_id: int, balance: Decimal = Decimal("0")) -> None:
        self.account_id: int = account_id
        self.balance: Decimal = balance
        self.lock: Lock = Lock()

def transfer(from_acc: Account, to_acc: Account, amount: Decimal) -> bool:
    # ALWAYS acquire locks in consistent order by account_id
    first: Account = min(from_acc, to_acc, key=lambda a: a.account_id)
    second: Account = max(from_acc, to_acc, key=lambda a: a.account_id)

    with first.lock, second.lock:
        if from_acc.balance >= amount:
            from_acc.balance -= amount
            to_acc.balance += amount
            return True
        return False

# Without ordering:
#   Thread 1: lock(A) → lock(B)
#   Thread 2: lock(B) → lock(A)  → DEADLOCK (circular wait)

# With ordering (always lower ID first):
#   Thread 1: lock(A) → lock(B)  (A.id < B.id)
#   Thread 2: lock(A) → lock(B)  (A.id < B.id)  → no cycle possible
```

The ordering key must be **stable and globally unique** — account ID, object `id()`, or a UUID. Using mutable state (like balance) as the ordering key is a bug.

**Strategy 2: Try-Lock with Timeout**

```python
from threading import Lock
import time
import random

lock_a: Lock = Lock()
lock_b: Lock = Lock()

def safe_operation() -> bool:
    while True:
        if lock_a.acquire(timeout=1.0):
            try:
                if lock_b.acquire(timeout=1.0):
                    try:
                        # Do work with both locks
                        return True
                    finally:
                        lock_b.release()
            finally:
                lock_a.release()
        # Back off and retry — randomized to avoid livelock
        time.sleep(random.uniform(0.001, 0.01))
    return False
```

**Strategy 3: Single Coarse Lock**

```python
from threading import Lock

global_lock: Lock = Lock()

def transfer(from_acc: Account, to_acc: Account, amount: Decimal) -> bool:
    with global_lock:  # One lock for everything — no ordering needed
        if from_acc.balance >= amount:
            from_acc.balance -= amount
            to_acc.balance += amount
            return True
        return False

# Simple and correct, but all transfers are serialized — no concurrency benefit.
# Fine for low-contention scenarios. Bad for high-throughput systems.
```

**Detection vs Prevention:**

| Approach       | When        | How                                                                                                                                |
| -------------- | ----------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| **Prevention** | Design time | Eliminate one of the four conditions (lock ordering, timeouts)                                                                     |
| **Avoidance**  | Runtime     | Before granting a lock, check if it would lead to an unsafe state (Banker's Algorithm — theoretical, rarely used in practice)      |
| **Detection**  | Runtime     | Build a wait-for graph periodically; if a cycle exists, kill one thread (databases do this — `SHOW ENGINE INNODB STATUS` in MySQL) |

---

### 14.3 Starvation

Starvation occurs when one thread holds a resource and doesn't let it go even when there is a no deadlock.

**Starvation** occurs when a thread is perpetually denied access to a resource it needs, even though the system is not deadlocked. The resource is available — other threads just keep grabbing it first.

**Common causes:**

| Cause                       | Scenario                                                                                                                 |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| **Unfair scheduling**       | Priority-based scheduler always runs high-priority threads; low-priority thread never gets CPU time                      |
| **Reader-writer imbalance** | Readers keep arriving continuously; writer never gets exclusive access because there's always at least one active reader |
| **Lock convoys**            | Many threads contend for the same lock; one thread consistently loses the race to acquire it                             |

**Reader-Writer starvation — the classic example:**

```python
from threading import Lock, Condition

class ReaderPreferringRWLock:
    def __init__(self) -> None:
        self._readers: int = 0
        self._lock: Lock = Lock()
        self._condition: Condition = Condition(self._lock)

    def acquire_read(self) -> None:
        with self._condition:
            self._readers += 1       # Readers always succeed immediately

    def release_read(self) -> None:
        with self._condition:
            self._readers -= 1
            if self._readers == 0:
                self._condition.notify_all()

    def acquire_write(self) -> None:
        self._condition.acquire()
        while self._readers > 0:     # Writer waits for ALL readers to finish
            self._condition.wait()    # If readers keep arriving → STARVATION

    def release_write(self) -> None:
        self._condition.notify_all()
        self._condition.release()

# Problem: If readers arrive continuously, the reader count never drops to 0.
# The writer waits forever.
```

**Fix — Writer-Preferring RWLock:**

```python
from threading import Lock, Condition

class WriterPreferringRWLock:
    def __init__(self) -> None:
        self._readers: int = 0
        self._writers_waiting: int = 0
        self._writer_active: bool = False
        self._lock: Lock = Lock()
        self._condition: Condition = Condition(self._lock)

    def acquire_read(self) -> None:
        with self._condition:
            # Block new readers if a writer is waiting or active
            while self._writer_active or self._writers_waiting > 0:
                self._condition.wait()
            self._readers += 1

    def release_read(self) -> None:
        with self._condition:
            self._readers -= 1
            if self._readers == 0:
                self._condition.notify_all()

    def acquire_write(self) -> None:
        with self._condition:
            self._writers_waiting += 1
            while self._readers > 0 or self._writer_active:
                self._condition.wait()
            self._writers_waiting -= 1
            self._writer_active = True

    def release_write(self) -> None:
        with self._condition:
            self._writer_active = False
            self._condition.notify_all()
```

**Python's `threading.Lock` is fair (FIFO)** — threads that call `acquire()` are served in order. This prevents lock-level starvation but doesn't prevent application-level starvation (e.g., the reader-writer problem above).

**Priority Inversion — a special form of starvation:**

A high-priority thread is blocked waiting for a lock held by a low-priority thread. But the low-priority thread can't run because a medium-priority thread keeps getting CPU time. Result: the high-priority thread is effectively starved by a medium-priority thread.

```
High priority   → waiting for lock held by Low priority
Medium priority → running (preempts Low priority)
Low priority    → can't finish (never gets CPU) → can't release lock

Fix: Priority Inheritance — temporarily boost Low priority to High priority
     while it holds the lock that High priority needs.
     (This is an OS/scheduler concern, not typically handled in application code.)
```

---

### 14.4 Livelock

A **livelock** is like a deadlock, except the threads are not blocked — they're actively running, but making no progress because they keep reacting to each other's state changes in a loop.

**The hallway analogy:** Two people meet in a narrow hallway. Both step left to let the other pass. Then both step right. Then both step left again. They're moving, but neither makes progress.

**Livelock in code — two threads that keep yielding to each other:**

```python
from threading import Lock, Thread
import time

lock_a: Lock = Lock()
lock_b: Lock = Lock()

def worker_1() -> None:
    while True:
        lock_a.acquire()
        if not lock_b.acquire(blocking=False):
            lock_a.release()       # "I'll step aside"
            continue               # Try again → but worker_2 does the same → LIVELOCK
        try:
            # do work
            break
        finally:
            lock_b.release()
            lock_a.release()

def worker_2() -> None:
    while True:
        lock_b.acquire()
        if not lock_a.acquire(blocking=False):
            lock_b.release()       # "I'll step aside"
            continue               # Try again → but worker_1 does the same → LIVELOCK
        try:
            # do work
            break
        finally:
            lock_a.release()
            lock_b.release()
```

**Why it happens:** Both threads use the same "polite" strategy — back off and retry. If their timing aligns, they back off and retry in lockstep forever.

**Fix — Randomized Backoff:**

```python
import random
import time
from threading import Lock

lock_a: Lock = Lock()
lock_b: Lock = Lock()

def worker_with_backoff() -> None:
    while True:
        lock_a.acquire()
        if not lock_b.acquire(blocking=False):
            lock_a.release()
            time.sleep(random.uniform(0.001, 0.01))  # Random delay breaks the symmetry
            continue
        try:
            # do work
            break
        finally:
            lock_b.release()
            lock_a.release()
```

The random delay makes it statistically impossible for both threads to stay in lockstep. This is the same principle behind Ethernet's CSMA/CD collision backoff.

**Livelock vs Deadlock:**

| Property         | Deadlock                                 | Livelock                          |
| ---------------- | ---------------------------------------- | --------------------------------- |
| Threads blocked? | Yes — permanently waiting                | No — actively running             |
| CPU usage        | Zero (threads sleeping)                  | High (threads spinning)           |
| Detection        | Easier — thread dump shows waiting state | Harder — threads look alive       |
| Fix              | Lock ordering, timeouts                  | Randomized backoff, lock ordering |

---

### 14.5 Summary — Concurrency Hazards at a Glance

| Hazard                 | What Happens                                        | Root Cause                                              | Prevention                                  |
| ---------------------- | --------------------------------------------------- | ------------------------------------------------------- | ------------------------------------------- |
| **Race Condition**     | Non-deterministic, incorrect results                | Unsynchronized access to shared mutable state           | Locks around compound operations            |
| **Deadlock**           | Threads permanently blocked                         | Circular lock dependency (all 4 Coffman conditions met) | Lock ordering, timeouts, coarse locks       |
| **Starvation**         | One thread never gets the resource                  | Unfair scheduling or continuous preemption by others    | Fair locks (FIFO), writer-preferring RWLock |
| **Livelock**           | Threads running but making no progress              | Symmetric retry strategies that stay in lockstep        | Randomized backoff                          |
| **Priority Inversion** | High-priority thread blocked by low-priority thread | Medium-priority thread preempts lock holder             | Priority inheritance (OS-level)             |

---

## 15. Testing Concurrent Code

### 15.1 Stress Testing with Threads

```python
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

def stress_test(
    fn: Callable[[], None],
    num_threads: int = 100,
    iterations: int = 1000,
) -> None:
    barrier: threading.Barrier = threading.Barrier(num_threads)

    def worker() -> None:
        barrier.wait()  # All threads start at the same time
        for _ in range(iterations):
            fn()

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker) for _ in range(num_threads)]
        for f in as_completed(futures):
            f.result()  # Raises if any thread had an exception

# Usage
from threading import Lock

counter: int = 0
lock: Lock = Lock()

def increment() -> None:
    global counter
    with lock:
        counter += 1

stress_test(increment, num_threads=50, iterations=10_000)
assert counter == 500_000, f"Race condition! counter={counter}"
```

### 15.2 Testing with `unittest`

```python
import unittest
import threading
from concurrent.futures import ThreadPoolExecutor

class TestThreadSafety(unittest.TestCase):
    def test_concurrent_register(self) -> None:
        lb = LoadBalancer(max_instances=100)
        errors: list[Exception] = []

        def register_servers(start: int) -> None:
            try:
                for i in range(start, start + 10):
                    lb.register(f"server-{i}")
            except Exception as e:
                errors.append(e)

        threads: list[threading.Thread] = [
            threading.Thread(target=register_servers, args=(i * 10,))
            for i in range(10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0)
        self.assertEqual(len(lb.instances), 100)

    def test_no_duplicate_registration(self) -> None:
        lb = LoadBalancer(max_instances=100)

        def register_same() -> bool:
            return lb.register("server-1")

        with ThreadPoolExecutor(max_workers=20) as executor:
            results: list[bool] = list(executor.map(lambda _: register_same(), range(20)))

        self.assertEqual(sum(results), 1)  # Only one should succeed
```

## 16. Real-World Patterns

### 16.1 Rate Limiter (Token Bucket)

```python
import threading
import time

class TokenBucketRateLimiter:
    def __init__(self, rate: float, capacity: int) -> None:
        self._rate: float = rate          # Tokens per second
        self._capacity: int = capacity
        self._tokens: float = float(capacity)
        self._lock: threading.Lock = threading.Lock()
        self._last_refill: float = time.monotonic()

    def acquire(self) -> bool:
        with self._lock:
            now: float = time.monotonic()
            elapsed: float = now - self._last_refill
            self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
            self._last_refill = now

            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return True
            return False
```

### 16.2 Thread-Safe LRU Cache

```python
from threading import Lock
from collections import OrderedDict
from typing import Any

class ThreadSafeLRUCache:
    def __init__(self, capacity: int) -> None:
        self._capacity: int = capacity
        self._cache: OrderedDict[str, Any] = OrderedDict()
        self._lock: Lock = Lock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            if key not in self._cache:
                return None
            self._cache.move_to_end(key)
            return self._cache[key]

    def put(self, key: str, value: Any) -> None:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = value
            if len(self._cache) > self._capacity:
                self._cache.popitem(last=False)
```

### 16.3 Circuit Breaker

```python
import threading
import time
from enum import Enum
from typing import Callable, TypeVar, Any

T = TypeVar("T")

class CircuitState(Enum):
    CLOSED = "closed"        # Normal operation
    OPEN = "open"            # Failing — reject immediately
    HALF_OPEN = "half_open"  # Testing if service recovered

class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        expected_exception: type[Exception] = Exception,
    ) -> None:
        self._failure_threshold: int = failure_threshold
        self._recovery_timeout: float = recovery_timeout
        self._expected_exception: type[Exception] = expected_exception
        self._failure_count: int = 0
        self._last_failure_time: float = 0.0
        self._state: CircuitState = CircuitState.CLOSED
        self._lock: threading.Lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN:
                if time.monotonic() - self._last_failure_time >= self._recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
            return self._state

    def call(self, fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        current_state: CircuitState = self.state

        if current_state == CircuitState.OPEN:
            raise CircuitBreakerOpenError("Circuit is open")

        try:
            result: T = fn(*args, **kwargs)
            self._on_success()
            return result
        except self._expected_exception:
            self._on_failure()
            raise

    def _on_success(self) -> None:
        with self._lock:
            self._failure_count = 0
            self._state = CircuitState.CLOSED

    def _on_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()
            if self._failure_count >= self._failure_threshold:
                self._state = CircuitState.OPEN

class CircuitBreakerOpenError(Exception):
    pass
```

### 16.4 Async Web Scraper Pattern

```python
import asyncio
import aiohttp

async def fetch_page(
    session: aiohttp.ClientSession,
    url: str,
    semaphore: asyncio.Semaphore,
) -> str:
    async with semaphore:
        async with session.get(url) as response:
            return await response.text()

async def scrape(urls: list[str], max_concurrent: int = 10) -> list[str]:
    semaphore: asyncio.Semaphore = asyncio.Semaphore(max_concurrent)
    async with aiohttp.ClientSession() as session:
        tasks: list[asyncio.Task[str]] = [
            asyncio.create_task(fetch_page(session, url, semaphore))
            for url in urls
        ]
        return await asyncio.gather(*tasks)
```

---

## 17. Applied Interview Problems (Revolut)

### 17.1 Load Balancer (Most Frequently Asked)

> Appeared in ~8 Revolut interview reviews. Typically 45-60 minutes, live coding, no AI tools.

**Requirements as given**:

- `register_server(server)` — add a server, no duplicates
- `get_server()` — random selection from registered servers
- `get_server()` — round-robin variant
- All methods must be thread-safe

```python
import threading
import random
from typing import Protocol


class LoadBalancingStrategy(Protocol):
    def select(self, servers: list[str]) -> str: ...


class RandomStrategy:
    def select(self, servers: list[str]) -> str:
        return random.choice(servers)


class RoundRobinStrategy:
    def __init__(self) -> None:
        self._counter: int = 0
        self._lock: threading.Lock = threading.Lock()

    def select(self, servers: list[str]) -> str:
        with self._lock:
            index: int = self._counter % len(servers)
            self._counter += 1
            return servers[index]


class LoadBalancer:
    def __init__(self, strategy: LoadBalancingStrategy) -> None:
        self._servers: list[str] = []
        self._server_set: set[str] = set()
        self._lock: threading.Lock = threading.Lock()
        self._strategy: LoadBalancingStrategy = strategy

    def register_server(self, server: str) -> bool:
        with self._lock:
            # check-then-act — MUST be inside the same lock
            if server in self._server_set:
                return False
            self._server_set.add(server)
            self._servers.append(server)
            return True

    def get_server(self) -> str | None:
        with self._lock:
            if not self._servers:
                return None
            # snapshot the list under lock, select can happen outside
            servers: list[str] = list(self._servers)
        return self._strategy.select(servers)
```

**Follow-up questions they ask**:

- "Why do you copy the list?" → So `select()` doesn't hold the lock during computation. Readers don't block each other.
- "What if RoundRobin counter overflows?" → Python ints have arbitrary precision, no overflow.
- "How would you handle server removal?" → Add `deregister_server()`, update both set and list under lock.
- "What about read-heavy workloads?" → Use `ReadWriteLock` — multiple readers, exclusive writers.

### 17.2 URL Shortener

> Second most common Revolut live coding question.

**Requirements**:

- `shorten(url)` → short_code — generate unique short codes
- `resolve(short_code)` → url — lookup
- Thread-safe, handle collisions

```python
import threading
import random
import string


class URLShortener:
    def __init__(self, code_length: int = 6) -> None:
        self._url_to_code: dict[str, str] = {}
        self._code_to_url: dict[str, str] = {}
        self._lock: threading.Lock = threading.Lock()
        self._code_length: int = code_length
        self._chars: str = string.ascii_letters + string.digits

    def _generate_code(self) -> str:
        return "".join(random.choices(self._chars, k=self._code_length))

    def shorten(self, url: str) -> str:
        with self._lock:
            # idempotent — same URL always returns same code
            if url in self._url_to_code:
                return self._url_to_code[url]

            # generate unique code, handle collisions
            code: str = self._generate_code()
            while code in self._code_to_url:
                code = self._generate_code()

            self._url_to_code[url] = code
            self._code_to_url[code] = url
            return code

    def resolve(self, code: str) -> str | None:
        with self._lock:
            return self._code_to_url.get(code)
```

**Follow-up questions**:

- "Why lock `resolve` too?" → Without lock, `shorten` could be writing while `resolve` reads → torn read on dict resize (CPython-specific, but principle matters).
- "Is the lock too coarse?" → For an interview, coarse lock is correct. Mention `RWLock` as optimization for read-heavy workloads.
- "What about collision probability?" → 62^6 = ~56 billion codes. At 1M URLs, collision probability is negligible. But the `while` loop handles it.
- "How would you persist this?" → DB with unique constraint on code column. `INSERT ... ON CONFLICT DO NOTHING` for atomicity.

### 17.3 Money Transfer (Technical Round)

> Tests lock ordering, deadlock prevention, ACID understanding.

```python
import threading
from decimal import Decimal


class InsufficientFundsError(Exception):
    pass


class Account:
    def __init__(self, account_id: int, balance: Decimal = Decimal("0")) -> None:
        self.account_id: int = account_id
        self.balance: Decimal = balance
        self.lock: threading.Lock = threading.Lock()


def transfer(from_acc: Account, to_acc: Account, amount: Decimal) -> bool:
    if amount <= 0:
        raise ValueError("Transfer amount must be positive")

    # Lock ordering by account_id prevents deadlock
    # Without this: Thread 1 locks A→B, Thread 2 locks B→A → deadlock
    first: Account = min(from_acc, to_acc, key=lambda a: a.account_id)
    second: Account = max(from_acc, to_acc, key=lambda a: a.account_id)

    with first.lock, second.lock:
        if from_acc.balance < amount:
            raise InsufficientFundsError(
                f"Account {from_acc.account_id} has {from_acc.balance}, needs {amount}"
            )
        from_acc.balance -= amount
        to_acc.balance += amount
        return True
```

**Follow-up questions**:

- "Why `Decimal` not `float`?" → Floating point can't represent 0.1 exactly. In finance, use `Decimal` or integer cents.
- "What if the process crashes between debit and credit?" → In-memory: both operations are under the same lock, so both happen or neither. In a DB: wrap in a transaction.
- "How would you do this across microservices?" → Saga pattern — debit first, then credit. If credit fails, compensate (re-credit the source). Idempotency keys to prevent double-processing.
- "What about the same account transferring to itself?" → Add guard: `if from_acc.account_id == to_acc.account_id: raise ValueError`.

---

## 18. Interview Question Checklist

### Conceptual (HR Screening / Technical Round 1)

- [ ] What is the GIL? Why does it exist? Does it prevent race conditions?
- [ ] `threading` vs `asyncio` vs `multiprocessing` — when to use each?
- [ ] What is a race condition? Give an example.
- [ ] What is a deadlock? How do you prevent it?
- [ ] What's the difference between concurrency and parallelism?
- [ ] Is `list.append()` thread-safe? Should you rely on it?
- [ ] What happens if you run CPU-bound code in an async event loop?

### Design (Live Coding / Technical Round 2)

- [ ] "How would you guarantee thread safety / concurrent access to shared resources?"
- [ ] "How to prevent shared resources from being accessed by multiple threads simultaneously?"
- [ ] "How to implement thread safety in round-robin strategy?"
- [ ] "Design a LoadBalancer with `register()` and `get()` methods"
- [ ] "Design a URL shortener — `shorten()` and `resolve()`"
- [ ] "Write pseudocode to transfer money between bank accounts safely"

### Bug Spotting

- [ ] Spot the check-then-act race in `if x not in list: list.append(x)`
- [ ] Spot the deadlock in inconsistent lock ordering
- [ ] Spot the event loop blocking from `time.sleep()` in async code
- [ ] Spot the missing `task_done()` causing `queue.join()` to hang

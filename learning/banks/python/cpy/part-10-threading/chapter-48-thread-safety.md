# Chapter 48: Thread Safety Patterns

## 48.1 Understanding Thread Safety

A function or data structure is thread-safe if it behaves correctly when accessed from multiple threads:

```
┌─────────────────────────────────────────────────────────────────┐
│              Thread Safety Levels                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Level 0: Not Thread-Safe                                        │
│  • Concurrent access causes corruption                          │
│  • Must use external synchronization                            │
│  • Example: list.extend() from multiple threads                 │
│                                                                  │
│  Level 1: Thread-Compatible                                      │
│  • Different instances can be used concurrently                 │
│  • Same instance needs synchronization                          │
│  • Example: Most Python classes                                  │
│                                                                  │
│  Level 2: Conditionally Thread-Safe                              │
│  • Some operations are thread-safe, others aren't              │
│  • Example: dict (single ops safe, iteration not)               │
│                                                                  │
│  Level 3: Thread-Safe                                            │
│  • All operations safe without external sync                    │
│  • Example: queue.Queue                                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 48.2 Race Conditions

### Classic Race Condition

```python
import threading

# Race condition example
counter = 0

def increment():
    global counter
    for _ in range(100000):
        counter += 1  # Not atomic!

threads = [threading.Thread(target=increment) for _ in range(4)]
for t in threads:
    t.start()
for t in threads:
    t.join()

print(f"Expected: 400000, Got: {counter}")  # Usually less!
```

### Why Counter += 1 is Not Atomic

```python
# counter += 1 translates to:
# 1. LOAD_GLOBAL counter    # Read counter
# 2. LOAD_CONST 1
# 3. BINARY_ADD             # Add 1
# 4. STORE_GLOBAL counter   # Write back

# Thread switch can happen between any bytecodes!
# T1: LOAD_GLOBAL (reads 0)
# T2: LOAD_GLOBAL (reads 0)
# T1: BINARY_ADD, STORE_GLOBAL (writes 1)
# T2: BINARY_ADD, STORE_GLOBAL (writes 1)
# Result: counter = 1, lost one increment!
```

## 48.3 Thread-Safe Patterns

### Pattern 1: Lock Protection

```python
import threading

class ThreadSafeCounter:
    def __init__(self):
        self._value = 0
        self._lock = threading.Lock()

    def increment(self):
        with self._lock:
            self._value += 1

    def get(self):
        with self._lock:
            return self._value

# Usage
counter = ThreadSafeCounter()
threads = [threading.Thread(target=lambda: [counter.increment() for _ in range(100000)])
           for _ in range(4)]
for t in threads:
    t.start()
for t in threads:
    t.join()
print(f"Got: {counter.get()}")  # 400000
```

### Pattern 2: Thread-Local Storage

```python
import threading

# Each thread has its own copy
class ThreadLocalAccumulator:
    def __init__(self):
        self._local = threading.local()
        self._totals = []
        self._lock = threading.Lock()

    def add(self, value):
        if not hasattr(self._local, 'sum'):
            self._local.sum = 0
        self._local.sum += value

    def finish(self):
        """Call when thread is done."""
        if hasattr(self._local, 'sum'):
            with self._lock:
                self._totals.append(self._local.sum)
            self._local.sum = 0

    def total(self):
        with self._lock:
            return sum(self._totals)

# Each thread accumulates locally, then merges
acc = ThreadLocalAccumulator()

def worker():
    for i in range(1000):
        acc.add(i)
    acc.finish()

threads = [threading.Thread(target=worker) for _ in range(4)]
for t in threads:
    t.start()
for t in threads:
    t.join()
print(f"Total: {acc.total()}")
```

### Pattern 3: Immutable Objects

```python
import threading
from typing import NamedTuple

# Immutable data is inherently thread-safe
class Point(NamedTuple):
    x: float
    y: float

# Multiple threads can read Point safely
# To "modify", create a new instance
point = Point(1, 2)
new_point = Point(point.x + 1, point.y + 1)

# Even updating a reference is safe (atomic assignment)
current_point = Point(0, 0)

def update_point():
    global current_point
    for _ in range(1000):
        p = current_point
        current_point = Point(p.x + 1, p.y + 1)

# Note: This is safe but results are non-deterministic
```

### Pattern 4: Copy-on-Write

```python
import threading
import copy

class CopyOnWriteList:
    def __init__(self, initial=None):
        self._data = list(initial) if initial else []
        self._lock = threading.Lock()

    def append(self, item):
        with self._lock:
            # Create new copy with item
            new_data = self._data.copy()
            new_data.append(item)
            self._data = new_data

    def __iter__(self):
        # Snapshot for iteration (no lock needed)
        return iter(self._data)

    def __len__(self):
        return len(self._data)

# Readers don't block writers
# Each read sees consistent snapshot
```

## 48.4 Thread-Safe Data Structures

### Thread-Safe Queue

```python
from queue import Queue, Empty, Full
import threading

q = Queue(maxsize=10)

# Put with timeout
try:
    q.put(item, timeout=1.0)
except Full:
    print("Queue is full")

# Get with timeout
try:
    item = q.get(timeout=1.0)
except Empty:
    print("Queue is empty")

# Non-blocking
try:
    q.put_nowait(item)
except Full:
    pass

try:
    item = q.get_nowait()
except Empty:
    pass

# Task tracking
q.task_done()  # Signal task complete
q.join()       # Wait for all tasks done
```

### Thread-Safe Dictionary Operations

```python
import threading

# Single operations are thread-safe (with GIL)
d = {}
d['key'] = 'value'      # Safe
value = d.get('key')    # Safe

# But compound operations need locks
lock = threading.Lock()

def safe_update(d, key, func):
    """Atomically update dictionary value."""
    with lock:
        old_value = d.get(key, 0)
        d[key] = func(old_value)

# setdefault is atomic
d.setdefault('key', 'default')  # Safe

# But check-then-act is not
if 'key' not in d:      # Race!
    d['key'] = 'value'  # Another thread might have added it

# Safe version
with lock:
    if 'key' not in d:
        d['key'] = 'value'
```

## 48.5 Producer-Consumer Pattern

### Basic Implementation

```python
import threading
from queue import Queue

class ProducerConsumer:
    def __init__(self, num_workers=4):
        self.queue = Queue()
        self.results = []
        self.results_lock = threading.Lock()
        self.num_workers = num_workers

    def producer(self, items):
        for item in items:
            self.queue.put(item)
        # Signal workers to stop
        for _ in range(self.num_workers):
            self.queue.put(None)

    def worker(self):
        while True:
            item = self.queue.get()
            if item is None:
                self.queue.task_done()
                break
            result = self.process(item)
            with self.results_lock:
                self.results.append(result)
            self.queue.task_done()

    def process(self, item):
        # Override in subclass
        return item * 2

    def run(self, items):
        # Start workers
        workers = [threading.Thread(target=self.worker)
                   for _ in range(self.num_workers)]
        for w in workers:
            w.start()

        # Start producer
        producer = threading.Thread(target=self.producer, args=(items,))
        producer.start()

        # Wait for completion
        producer.join()
        for w in workers:
            w.join()

        return self.results
```

### With concurrent.futures

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def process_item(item):
    return item * 2

items = list(range(100))

with ThreadPoolExecutor(max_workers=4) as executor:
    # Submit all tasks
    futures = {executor.submit(process_item, item): item
               for item in items}

    # Process results as they complete
    for future in as_completed(futures):
        item = futures[future]
        try:
            result = future.result()
            print(f"{item} -> {result}")
        except Exception as e:
            print(f"{item} raised {e}")
```

## 48.6 Reader-Writer Lock Pattern

### Implementation

```python
import threading

class ReadWriteLock:
    """Multiple readers, single writer lock."""

    def __init__(self):
        self._read_ready = threading.Condition(threading.Lock())
        self._readers = 0

    def acquire_read(self):
        with self._read_ready:
            self._readers += 1

    def release_read(self):
        with self._read_ready:
            self._readers -= 1
            if self._readers == 0:
                self._read_ready.notify_all()

    def acquire_write(self):
        self._read_ready.acquire()
        while self._readers > 0:
            self._read_ready.wait()

    def release_write(self):
        self._read_ready.release()

# Context managers for convenience
class ReadLock:
    def __init__(self, rwlock):
        self.rwlock = rwlock

    def __enter__(self):
        self.rwlock.acquire_read()
        return self

    def __exit__(self, *args):
        self.rwlock.release_read()

class WriteLock:
    def __init__(self, rwlock):
        self.rwlock = rwlock

    def __enter__(self):
        self.rwlock.acquire_write()
        return self

    def __exit__(self, *args):
        self.rwlock.release_write()

# Usage
rwlock = ReadWriteLock()
data = {}

def reader():
    with ReadLock(rwlock):
        return dict(data)  # Copy while holding read lock

def writer(key, value):
    with WriteLock(rwlock):
        data[key] = value
```

## 48.7 Double-Checked Locking

### The Pattern (Use Carefully!)

```python
import threading

class Singleton:
    _instance = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:  # First check (no lock)
            with cls._lock:
                if cls._instance is None:  # Second check (with lock)
                    cls._instance = cls()
        return cls._instance

# Note: In Python, this is usually overkill
# Simple approach works due to GIL:
class SimpleSingleton:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
```

### Thread-Safe Lazy Initialization

```python
import threading
from functools import lru_cache

# Method 1: Using lru_cache (thread-safe)
@lru_cache(maxsize=1)
def get_expensive_resource():
    return ExpensiveResource()

# Method 2: Using Lock
class LazyResource:
    _resource = None
    _lock = threading.Lock()

    @classmethod
    def get(cls):
        if cls._resource is None:
            with cls._lock:
                if cls._resource is None:
                    cls._resource = ExpensiveResource()
        return cls._resource

# Method 3: Using module-level initialization
# (thread-safe due to import lock)
_resource = None

def get_resource():
    global _resource
    if _resource is None:
        _resource = ExpensiveResource()
    return _resource
```

## 48.8 Thread-Safe Caching

### Simple Thread-Safe Cache

```python
import threading
from functools import wraps

def thread_safe_cache(func):
    """Thread-safe memoization decorator."""
    cache = {}
    lock = threading.Lock()

    @wraps(func)
    def wrapper(*args):
        with lock:
            if args in cache:
                return cache[args]

        # Compute outside lock
        result = func(*args)

        with lock:
            cache[args] = result

        return result

    return wrapper

@thread_safe_cache
def expensive_computation(n):
    return sum(i**2 for i in range(n))
```

### LRU Cache with Size Limit

```python
import threading
from collections import OrderedDict

class ThreadSafeLRUCache:
    def __init__(self, maxsize=128):
        self.cache = OrderedDict()
        self.maxsize = maxsize
        self.lock = threading.Lock()

    def get(self, key):
        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key)
                return self.cache[key]
        return None

    def put(self, key, value):
        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key)
            self.cache[key] = value
            if len(self.cache) > self.maxsize:
                self.cache.popitem(last=False)
```

## 48.9 Testing Thread Safety

### Stress Testing

```python
import threading
import random
import time

def stress_test(operation, num_threads=10, iterations=10000):
    """Stress test an operation for thread safety."""
    errors = []
    error_lock = threading.Lock()

    def worker():
        try:
            for _ in range(iterations):
                operation()
        except Exception as e:
            with error_lock:
                errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(num_threads)]
    start = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = time.perf_counter() - start

    print(f"Completed in {elapsed:.2f}s")
    if errors:
        print(f"Errors: {len(errors)}")
        for e in errors[:5]:
            print(f"  {e}")
    return len(errors) == 0
```

### Detecting Race Conditions

```python
import threading
import sys

class RaceDetector:
    """Simple race condition detector."""

    def __init__(self):
        self.operations = []
        self.lock = threading.Lock()

    def record(self, operation, value):
        tid = threading.get_ident()
        with self.lock:
            self.operations.append((tid, operation, value))

    def analyze(self):
        """Look for suspicious patterns."""
        # Check for interleaved read-write sequences
        reads = {}
        for tid, op, value in self.operations:
            if op == 'read':
                reads[tid] = value
            elif op == 'write':
                # Check if any thread read an old value
                for other_tid, read_value in reads.items():
                    if other_tid != tid and read_value != value:
                        print(f"Potential race: T{other_tid} read {read_value}, "
                              f"T{tid} wrote {value}")
```

## 48.10 Common Pitfalls

### Pitfall 1: Forgetting to Release Lock

```python
# BAD
lock.acquire()
do_something()  # If this raises, lock is never released!
lock.release()

# GOOD
with lock:
    do_something()

# Or
lock.acquire()
try:
    do_something()
finally:
    lock.release()
```

### Pitfall 2: Lock in Wrong Scope

```python
# BAD: Lock per call doesn't help
def bad_increment(counter):
    lock = threading.Lock()  # New lock each call!
    with lock:
        counter.value += 1

# GOOD: Shared lock
class Counter:
    def __init__(self):
        self.value = 0
        self.lock = threading.Lock()

    def increment(self):
        with self.lock:
            self.value += 1
```

### Pitfall 3: Holding Lock During I/O

```python
# BAD: Holds lock during slow I/O
def bad_fetch(url, cache, lock):
    with lock:
        if url in cache:
            return cache[url]
        result = requests.get(url)  # Slow! Others blocked
        cache[url] = result
        return result

# GOOD: Minimize lock scope
def good_fetch(url, cache, lock):
    with lock:
        if url in cache:
            return cache[url]

    result = requests.get(url)  # No lock held

    with lock:
        cache[url] = result

    return result
```

## Summary

- **Race conditions** occur when multiple threads access shared state
- **Locks** protect critical sections
- **Thread-local storage** eliminates sharing
- **Immutable objects** are inherently thread-safe
- **Producer-consumer** pattern uses queues
- **Reader-writer locks** allow concurrent reads
- **Test thoroughly** with stress tests
- **Minimize lock scope** for performance

## Practice Exercises

1. Implement a thread-safe bounded queue
2. Create a read-write lock with writer preference
3. Build a thread-safe connection pool
4. Test your data structures with stress tests

---

[← Previous: Threading Primitives](chapter-47-threading-primitives.md) | [Next: Signal Handling →](chapter-49-signal-handling.md)

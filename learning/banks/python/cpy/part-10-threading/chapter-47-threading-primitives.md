# Chapter 47: Threading Primitives

## 47.1 Overview of Synchronization Primitives

Python provides several synchronization primitives:

```
┌─────────────────────────────────────────────────────────────────┐
│              Synchronization Primitives                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Lock (Mutex)           RLock (Reentrant)      Condition        │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐  │
│  │ • One owner  │      │ • Same thread│      │ • Wait/notify│  │
│  │ • Block if   │      │   can acquire│      │ • Based on   │  │
│  │   held       │      │   multiple   │      │   lock       │  │
│  └──────────────┘      └──────────────┘      └──────────────┘  │
│                                                                  │
│  Semaphore              Event                  Barrier          │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐  │
│  │ • Counting   │      │ • Set/clear  │      │ • N threads  │  │
│  │ • N permits  │      │ • Wait for   │      │   must wait  │  │
│  │              │      │   set        │      │   together   │  │
│  └──────────────┘      └──────────────┘      └──────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 47.2 Lock (Mutex)

### Basic Lock Usage

```python
import threading

lock = threading.Lock()
counter = 0

def increment():
    global counter
    for _ in range(100000):
        lock.acquire()
        try:
            counter += 1
        finally:
            lock.release()

# Better: Use context manager
def increment_safe():
    global counter
    for _ in range(100000):
        with lock:
            counter += 1
```

### Lock Implementation

```c
// Lock is implemented using OS primitives
// On POSIX: pthread_mutex_t
// On Windows: CRITICAL_SECTION or SRWLock

typedef struct {
    PyObject_HEAD
    PyThread_type_lock lock_lock;
    char locked;      // 1 if locked
} lockobject;

static PyObject *
lock_acquire(lockobject *self, PyObject *args, PyObject *kwds)
{
    int blocking = 1;
    double timeout = -1;

    // Parse arguments
    if (!PyArg_ParseTupleAndKeywords(args, kwds, "|pd", kwlist,
                                      &blocking, &timeout))
        return NULL;

    // Release GIL while waiting
    PyThreadState *tstate = PyEval_SaveThread();

    int result = PyThread_acquire_lock_timed(
        self->lock_lock,
        blocking ? timeout : 0,
        PY_LOCK_ACQUIRE
    );

    PyEval_RestoreThread(tstate);

    if (result == PY_LOCK_ACQUIRED) {
        self->locked = 1;
        Py_RETURN_TRUE;
    }
    Py_RETURN_FALSE;
}
```

### Lock Methods

```python
lock = threading.Lock()

# Non-blocking acquire
if lock.acquire(blocking=False):
    try:
        # Critical section
        pass
    finally:
        lock.release()
else:
    print("Lock not available")

# Acquire with timeout
if lock.acquire(timeout=1.0):
    try:
        pass
    finally:
        lock.release()
else:
    print("Timeout waiting for lock")

# Check if locked (may be racy)
if lock.locked():
    print("Lock is held by someone")
```

## 47.3 RLock (Reentrant Lock)

### Why RLock?

```python
import threading

# Problem with regular Lock
lock = threading.Lock()

def outer():
    with lock:
        inner()  # DEADLOCK! Lock already held

def inner():
    with lock:  # Blocks forever
        pass

# Solution: Use RLock
rlock = threading.RLock()

def outer_safe():
    with rlock:
        inner_safe()  # Works fine

def inner_safe():
    with rlock:  # Same thread can acquire again
        pass
```

### RLock Implementation

```c
typedef struct {
    PyObject_HEAD
    PyThread_type_lock rlock_lock;
    unsigned long rlock_owner;   // Thread ID of owner
    unsigned long rlock_count;   // Recursion count
} rlockobject;

static PyObject *
rlock_acquire(rlockobject *self, ...)
{
    unsigned long tid = PyThread_get_thread_ident();

    // Check if we already own it
    if (self->rlock_owner == tid) {
        self->rlock_count++;
        Py_RETURN_TRUE;
    }

    // Acquire the underlying lock
    // (release GIL while waiting)
    int result = acquire_lock(self->rlock_lock, ...);

    if (result == PY_LOCK_ACQUIRED) {
        self->rlock_owner = tid;
        self->rlock_count = 1;
        Py_RETURN_TRUE;
    }
    Py_RETURN_FALSE;
}

static PyObject *
rlock_release(rlockobject *self, ...)
{
    unsigned long tid = PyThread_get_thread_ident();

    if (self->rlock_owner != tid) {
        PyErr_SetString(PyExc_RuntimeError,
                        "cannot release un-acquired lock");
        return NULL;
    }

    self->rlock_count--;
    if (self->rlock_count == 0) {
        self->rlock_owner = 0;
        PyThread_release_lock(self->rlock_lock);
    }
    Py_RETURN_NONE;
}
```

## 47.4 Condition Variable

### Producer-Consumer Pattern

```python
import threading
import time
import random

class Buffer:
    def __init__(self, size):
        self.buffer = []
        self.size = size
        self.lock = threading.Lock()
        self.not_full = threading.Condition(self.lock)
        self.not_empty = threading.Condition(self.lock)

    def put(self, item):
        with self.not_full:
            while len(self.buffer) >= self.size:
                self.not_full.wait()  # Wait until not full
            self.buffer.append(item)
            self.not_empty.notify()   # Signal not empty

    def get(self):
        with self.not_empty:
            while len(self.buffer) == 0:
                self.not_empty.wait()  # Wait until not empty
            item = self.buffer.pop(0)
            self.not_full.notify()     # Signal not full
            return item

def producer(buf, count):
    for i in range(count):
        buf.put(i)
        print(f"Produced {i}")
        time.sleep(random.random() * 0.1)

def consumer(buf, count):
    for _ in range(count):
        item = buf.get()
        print(f"Consumed {item}")
        time.sleep(random.random() * 0.2)

buf = Buffer(5)
threading.Thread(target=producer, args=(buf, 10)).start()
threading.Thread(target=consumer, args=(buf, 10)).start()
```

### Condition Methods

```python
cond = threading.Condition()

# Wait with timeout
with cond:
    ready = cond.wait(timeout=5.0)
    if not ready:
        print("Timed out")

# Wait for predicate
with cond:
    cond.wait_for(lambda: some_condition())  # Atomically check and wait

# Notify one waiter
with cond:
    cond.notify()

# Notify all waiters
with cond:
    cond.notify_all()
```

## 47.5 Semaphore

### Counting Semaphore

```python
import threading
import time

# Limit concurrent access to resource
semaphore = threading.Semaphore(3)  # Allow 3 concurrent accesses

def access_resource(thread_id):
    print(f"Thread {thread_id} waiting...")
    with semaphore:
        print(f"Thread {thread_id} accessing resource")
        time.sleep(1)
        print(f"Thread {thread_id} releasing resource")

threads = [threading.Thread(target=access_resource, args=(i,))
           for i in range(10)]
for t in threads:
    t.start()
for t in threads:
    t.join()
```

### BoundedSemaphore

```python
# BoundedSemaphore prevents releasing more than acquired
sem = threading.BoundedSemaphore(3)

sem.acquire()
sem.release()
sem.release()  # ERROR: ValueError

# Regular Semaphore allows it (use with caution)
sem = threading.Semaphore(3)
sem.release()  # Now count is 4 (maybe a bug!)
```

### Semaphore Implementation

```c
typedef struct {
    PyObject_HEAD
    PyThread_type_lock lock;
    Py_ssize_t value;          // Current count
    Py_ssize_t max_value;      // For BoundedSemaphore
    condvar_t cond;
} semaphoreobject;

static PyObject *
semaphore_acquire(semaphoreobject *self, ...)
{
    while (1) {
        if (self->value > 0) {
            self->value--;
            Py_RETURN_TRUE;
        }

        // Wait on condition variable
        // (releases lock while waiting)
        cond_wait(&self->cond, &self->lock, timeout);
    }
}

static PyObject *
semaphore_release(semaphoreobject *self, ...)
{
    self->value++;
    cond_signal(&self->cond);  // Wake one waiter
    Py_RETURN_NONE;
}
```

## 47.6 Event

### Simple Signaling

```python
import threading
import time

event = threading.Event()

def waiter(name):
    print(f"{name} waiting for event...")
    event.wait()
    print(f"{name} received event!")

def signaler():
    time.sleep(2)
    print("Setting event")
    event.set()

threads = [threading.Thread(target=waiter, args=(f"W{i}",))
           for i in range(3)]
for t in threads:
    t.start()

signaler_thread = threading.Thread(target=signaler)
signaler_thread.start()

for t in threads:
    t.join()
```

### Event Methods

```python
event = threading.Event()

# Check state
if event.is_set():
    print("Event is set")

# Set the event (wake all waiters)
event.set()

# Clear the event
event.clear()

# Wait with timeout
if event.wait(timeout=5.0):
    print("Event was set")
else:
    print("Timed out")
```

## 47.7 Barrier

### Synchronizing Multiple Threads

```python
import threading
import time
import random

barrier = threading.Barrier(3)  # Wait for 3 threads

def worker(name):
    # Phase 1: Initialize
    print(f"{name} initializing...")
    time.sleep(random.random())

    # Wait for all threads
    print(f"{name} waiting at barrier...")
    barrier.wait()

    # Phase 2: All threads proceed together
    print(f"{name} proceeding!")

threads = [threading.Thread(target=worker, args=(f"T{i}",))
           for i in range(3)]
for t in threads:
    t.start()
for t in threads:
    t.join()
```

### Barrier with Action

```python
def barrier_action():
    print("All threads reached barrier!")

barrier = threading.Barrier(3, action=barrier_action)

def worker(name):
    barrier.wait()
    # action runs before any thread leaves wait()
```

### Barrier Abort

```python
barrier = threading.Barrier(3)

def worker(name):
    try:
        barrier.wait()
    except threading.BrokenBarrierError:
        print(f"{name}: Barrier was broken!")

# Break the barrier
barrier.abort()
# All waiting threads get BrokenBarrierError
```

## 47.8 Lock-Free Patterns

### Using `queue.Queue`

```python
import queue
import threading

# Queue is thread-safe
q = queue.Queue()

def producer():
    for i in range(10):
        q.put(i)
    q.put(None)  # Sentinel

def consumer():
    while True:
        item = q.get()
        if item is None:
            break
        print(f"Got {item}")
        q.task_done()

threading.Thread(target=producer).start()
threading.Thread(target=consumer).start()

q.join()  # Wait for all items to be processed
```

### Atomic Operations

```python
import threading

# Some operations are atomic (thread-safe without locks)

# Atomic assignment
x = 42  # Atomic
x = y   # Atomic (if y is simple type)

# NOT atomic (need locks)
counter += 1  # Read-modify-write
my_list.append(x)  # Depends on implementation

# Use Lock for compound operations
lock = threading.Lock()
with lock:
    if key not in my_dict:
        my_dict[key] = compute_value()
```

## 47.9 Deadlock Prevention

### Common Deadlock Patterns

```python
import threading

# Deadlock 1: Lock ordering violation
lock_a = threading.Lock()
lock_b = threading.Lock()

def thread1():
    with lock_a:
        with lock_b:  # Waits for lock_b
            pass

def thread2():
    with lock_b:
        with lock_a:  # Waits for lock_a → DEADLOCK!
            pass

# Solution: Always acquire locks in same order
def thread1_safe():
    with lock_a:
        with lock_b:
            pass

def thread2_safe():
    with lock_a:  # Same order as thread1
        with lock_b:
            pass
```

### Lock Timeout

```python
import threading

def try_acquire_both(lock1, lock2, timeout=1.0):
    """Try to acquire both locks, release on failure."""
    if not lock1.acquire(timeout=timeout):
        return False

    if not lock2.acquire(timeout=timeout):
        lock1.release()
        return False

    return True

# Usage
if try_acquire_both(lock_a, lock_b):
    try:
        # Critical section
        pass
    finally:
        lock_b.release()
        lock_a.release()
else:
    print("Could not acquire both locks")
```

## 47.10 Performance Considerations

### Lock Contention

```python
import threading
import time

def benchmark_lock_contention(num_threads, iterations):
    lock = threading.Lock()
    counter = 0

    def worker():
        nonlocal counter
        for _ in range(iterations):
            with lock:
                counter += 1

    start = time.perf_counter()
    threads = [threading.Thread(target=worker) for _ in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = time.perf_counter() - start

    print(f"{num_threads} threads: {elapsed:.3f}s, "
          f"{num_threads * iterations / elapsed:.0f} ops/sec")

# More threads = more contention = slower
for n in [1, 2, 4, 8]:
    benchmark_lock_contention(n, 100000)
```

### Lock Granularity

```python
# Coarse-grained: One lock for everything
class CoarseGrained:
    def __init__(self):
        self.lock = threading.Lock()
        self.data = {}

    def set(self, key, value):
        with self.lock:  # Blocks all operations
            self.data[key] = value

# Fine-grained: Separate locks
class FineGrained:
    def __init__(self, num_locks=16):
        self.locks = [threading.Lock() for _ in range(num_locks)]
        self.data = {}

    def get_lock(self, key):
        return self.locks[hash(key) % len(self.locks)]

    def set(self, key, value):
        with self.get_lock(key):  # Only blocks same hash bucket
            self.data[key] = value
```

## Summary

- **Lock/RLock**: Basic mutual exclusion
- **Condition**: Wait/notify pattern
- **Semaphore**: Limit concurrent access
- **Event**: Simple signaling
- **Barrier**: Synchronize multiple threads
- **Deadlock prevention**: Lock ordering, timeouts
- **Performance**: Balance granularity vs. complexity

## Practice Exercises

1. Implement a read-write lock using Lock and Condition
2. Create a thread-safe LRU cache
3. Build a thread pool using Queue and Lock
4. Measure lock contention with different strategies

---

[← Previous: Thread Lifecycle](chapter-46-thread-lifecycle.md) | [Next: Thread Safety Patterns →](chapter-48-thread-safety.md)

# Chapter 24: GIL Fundamentals

## 24.1 What is the GIL

The **Global Interpreter Lock (GIL)** is a mutex that protects access to Python objects, preventing multiple threads from executing Python bytecode simultaneously.

```
┌─────────────────────────────────────────────────────────────────┐
│                    The Global Interpreter Lock                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    Python Process                        │    │
│  │                                                          │    │
│  │    Thread 1        Thread 2        Thread 3             │    │
│  │       │               │               │                  │    │
│  │       │               │               │                  │    │
│  │       ▼               ▼               ▼                  │    │
│  │    ┌─────────────────────────────────────┐              │    │
│  │    │              GIL                     │              │    │
│  │    │    (Only ONE thread can hold it)    │              │    │
│  │    └─────────────────────────────────────┘              │    │
│  │                      │                                   │    │
│  │                      ▼                                   │    │
│  │    ┌─────────────────────────────────────┐              │    │
│  │    │     Python Interpreter State        │              │    │
│  │    │     (Protected by GIL)              │              │    │
│  │    └─────────────────────────────────────┘              │    │
│  │                                                          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Key Point: Multiple threads exist, but only ONE executes       │
│  Python bytecode at any given moment.                           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Simple Definition

The GIL is:
- A **mutex** (mutual exclusion lock)
- **Global** to the interpreter (one per Python process)
- Required to execute **any Python bytecode**
- **Not required** during I/O or C extension operations that release it

## 24.2 Why CPython Needs the GIL

### 1. Reference Counting Safety

Python uses reference counting for memory management:

```python
import sys

x = [1, 2, 3]
print(sys.getrefcount(x))  # Reference count

# Without GIL, this could race:
# Thread 1: reads refcount = 1
# Thread 2: reads refcount = 1
# Thread 1: writes refcount = 2
# Thread 2: writes refcount = 2
# Result: refcount = 2 (should be 3!)
```

```c
// In C, incrementing isn't atomic:
object->ob_refcnt++;

// This compiles to:
// 1. Load ob_refcnt into register
// 2. Increment register
// 3. Store back to ob_refcnt

// Without synchronization, threads can interleave these steps!
```

### 2. C Extension Safety

Many C extensions aren't thread-safe:

```c
// A typical C extension pattern
static PyObject* module_state;  // Global state

PyObject* my_function(PyObject* args) {
    // Without GIL, multiple threads could corrupt module_state
    module_state = process(args);
    return module_state;
}
```

### 3. Simplicity

The GIL simplifies:
- CPython implementation (no fine-grained locking)
- C extension development (authors can ignore threading)
- Debugging (no race conditions in pure Python)

## 24.3 What the GIL Protects

### Protected by the GIL

- Reference count modifications
- Object allocations/deallocations
- Access to Python object internals
- Dictionary/list/set modifications
- Global interpreter state
- Bytecode execution

### NOT Protected by the GIL

```python
# These still need explicit synchronization:
import threading

# Compound operations
counter = 0
def increment():
    global counter
    counter += 1  # NOT atomic! (load, add, store)

# Multiple operations
def transfer(from_account, to_account, amount):
    # GIL doesn't make this atomic
    from_account.balance -= amount
    to_account.balance += amount

# Use locks for these:
lock = threading.Lock()
def safe_increment():
    global counter
    with lock:
        counter += 1
```

## 24.4 GIL vs Fine-Grained Locking

Why not use fine-grained locks instead?

### Fine-Grained Locking Approach

```
┌─────────────────────────────────────────────────────────────────┐
│                    Fine-Grained Locking                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │ Object 1 │  │ Object 2 │  │ Object 3 │  │ Object 4 │        │
│  │ ┌──────┐ │  │ ┌──────┐ │  │ ┌──────┐ │  │ ┌──────┐ │        │
│  │ │ Lock │ │  │ │ Lock │ │  │ │ Lock │ │  │ │ Lock │ │        │
│  │ └──────┘ │  │ └──────┘ │  │ └──────┘ │  │ └──────┘ │        │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │
│                                                                  │
│  Problems:                                                       │
│  - Lock overhead for every object operation                     │
│  - Deadlock potential                                            │
│  - Memory overhead for locks                                     │
│  - 15-30% slower for single-threaded code (historical tests)    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### GIL Approach

```
┌─────────────────────────────────────────────────────────────────┐
│                         GIL Approach                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│     ┌─────────────────────────────────────────────────┐         │
│     │                    GIL                           │         │
│     │              (Single Lock)                       │         │
│     └─────────────────────────────────────────────────┘         │
│                          │                                       │
│     ┌────────────────────┼────────────────────┐                 │
│     │                    │                    │                  │
│     ▼                    ▼                    ▼                  │
│  Object 1            Object 2            Object 3               │
│  (no lock)           (no lock)           (no lock)              │
│                                                                  │
│  Benefits:                                                       │
│  - Fast single-threaded performance                             │
│  - Simple implementation                                         │
│  - No deadlock risk from Python objects                         │
│  - Easy C extension development                                  │
│                                                                  │
│  Drawbacks:                                                      │
│  - No CPU parallelism in pure Python                            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 24.5 Historical Context

### Timeline

```
1992: Python 1.0
      - Single-threaded only
      - No GIL needed

1997: Python 1.5
      - Threading support added
      - GIL introduced to protect interpreter

1999: Greg Stein's Free-Threading Patch
      - Removed GIL, added fine-grained locks
      - Result: 40% slower on single thread
      - 2x speedup with 2 threads (break-even)
      - Not merged

2008: Python 3.0
      - New GIL implementation considered but not done

2010: Python 3.2
      - New GIL implementation by Antoine Pitrou
      - Time-based instead of instruction-based
      - Better fairness between threads

2021: PEP 703 proposed (Free-Threading)
      - Sam Gross's nogil project
      - Accepted for Python 3.13+

2024: Python 3.13
      - Experimental free-threaded build available
```

### Why the GIL Persists

1. **Single-threaded performance**: Most Python code is single-threaded
2. **C extension compatibility**: Vast ecosystem assumes GIL
3. **Simplicity**: Easier to reason about
4. **Removal attempts failed**: Until recently, couldn't match performance

## GIL Impact Visualization

```python
import threading
import time

def cpu_bound(n):
    """CPU-intensive work."""
    count = 0
    for i in range(n):
        count += i
    return count

# Single-threaded
start = time.time()
cpu_bound(10_000_000)
cpu_bound(10_000_000)
single_time = time.time() - start

# Multi-threaded (with GIL)
start = time.time()
t1 = threading.Thread(target=cpu_bound, args=(10_000_000,))
t2 = threading.Thread(target=cpu_bound, args=(10_000_000,))
t1.start()
t2.start()
t1.join()
t2.join()
multi_time = time.time() - start

print(f"Single-threaded: {single_time:.2f}s")
print(f"Multi-threaded:  {multi_time:.2f}s")
# Multi-threaded is often SLOWER due to GIL contention!
```

## Summary

- **GIL** is a global mutex protecting Python interpreter state
- **Needed** for reference counting and C extension safety
- **Prevents** parallel CPU execution in pure Python
- **Doesn't prevent** parallel I/O operations
- **Historical attempts** to remove it failed on performance
- **Python 3.13+** offers experimental free-threaded mode

## Practice Exercises

1. Demonstrate that multi-threaded CPU-bound code isn't faster
2. Show that I/O-bound code can still benefit from threads
3. Use `sys.getswitchinterval()` to see the current switch interval
4. Research the "Gilectomy" project and why it was abandoned

---

[← Previous: Memory Debugging](../part-05-memory-management/chapter-23-memory-debugging.md) | [Next: GIL Implementation →](chapter-25-gil-implementation.md)

# Chapter 27: GIL and Threading

## 27.1 Python Threads vs OS Threads

Python threads are real OS threads, but they can't run Python code in parallel:

```
┌─────────────────────────────────────────────────────────────────┐
│              Python Threads vs OS Threads                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Python Process                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                                                          │    │
│  │  Python Thread 1    Python Thread 2    Python Thread 3  │    │
│  │        │                  │                  │          │    │
│  │        ▼                  ▼                  ▼          │    │
│  │  ┌──────────┐      ┌──────────┐      ┌──────────┐      │    │
│  │  │ OS Thread│      │ OS Thread│      │ OS Thread│      │    │
│  │  │  (real)  │      │  (real)  │      │  (real)  │      │    │
│  │  └──────────┘      └──────────┘      └──────────┘      │    │
│  │        │                  │                  │          │    │
│  │        └──────────────────┴──────────────────┘          │    │
│  │                          │                               │    │
│  │                          ▼                               │    │
│  │                    ┌──────────┐                         │    │
│  │                    │   GIL    │                         │    │
│  │                    └──────────┘                         │    │
│  │                                                          │    │
│  │  Only ONE thread can hold the GIL and execute Python    │    │
│  │  bytecode at any given time.                            │    │
│  │                                                          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Proof of Real OS Threads

```python
import threading
import os

def show_thread_info():
    print(f"Python thread: {threading.current_thread().name}")
    print(f"OS thread ID: {threading.get_native_id()}")
    print(f"Process ID: {os.getpid()}")

# Main thread
show_thread_info()

# New thread - gets its own OS thread ID
t = threading.Thread(target=show_thread_info)
t.start()
t.join()
```

## 27.2 Why Threads Don't Run in Parallel (CPU-Bound)

### The Problem

```python
import threading
import time

def cpu_intensive():
    """Pure CPU work."""
    total = 0
    for i in range(10_000_000):
        total += i
    return total

# Sequential execution
start = time.time()
cpu_intensive()
cpu_intensive()
sequential_time = time.time() - start

# Parallel execution (attempt)
start = time.time()
t1 = threading.Thread(target=cpu_intensive)
t2 = threading.Thread(target=cpu_intensive)
t1.start()
t2.start()
t1.join()
t2.join()
parallel_time = time.time() - start

print(f"Sequential: {sequential_time:.2f}s")
print(f"Parallel:   {parallel_time:.2f}s")
# Parallel is often SLOWER due to GIL contention overhead!
```

### What's Actually Happening

```
┌─────────────────────────────────────────────────────────────────┐
│           CPU-Bound Threading (GIL Effect)                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Expected (without GIL):                                         │
│                                                                  │
│  Core 1: [Thread 1 ████████████████]                            │
│  Core 2: [Thread 2 ████████████████]                            │
│  Time: ────────────────────────────▶                            │
│        Total time = T (parallel)                                 │
│                                                                  │
│  Reality (with GIL):                                            │
│                                                                  │
│  Core 1: [T1 ████][wait][T1 ████][wait][T1 ████]...            │
│  Core 2: [wait][T2 ████][wait][T2 ████][wait]...               │
│  Time: ────────────────────────────────────────▶                │
│        Total time ≈ 2T (plus switching overhead)                │
│                                                                  │
│  Result: Threads take turns, don't run simultaneously           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 27.3 I/O-Bound vs CPU-Bound Workloads

### I/O-Bound: Threading Helps!

```python
import threading
import time
import urllib.request

URLS = [
    'https://www.python.org',
    'https://docs.python.org',
    'https://pypi.org',
    'https://github.com',
] * 5  # 20 URLs

def fetch_url(url):
    try:
        urllib.request.urlopen(url, timeout=5)
        return True
    except:
        return False

# Sequential
start = time.time()
for url in URLS:
    fetch_url(url)
sequential = time.time() - start

# Parallel (GIL released during I/O!)
start = time.time()
threads = [threading.Thread(target=fetch_url, args=(url,)) for url in URLS]
for t in threads:
    t.start()
for t in threads:
    t.join()
parallel = time.time() - start

print(f"Sequential: {sequential:.2f}s")
print(f"Parallel:   {parallel:.2f}s")
# Parallel IS faster because GIL is released during I/O wait!
```

### Why I/O-Bound Threading Works

```
┌─────────────────────────────────────────────────────────────────┐
│           I/O-Bound Threading (GIL Released)                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Thread 1: [prep][─────I/O wait─────][process]                  │
│                   ↓ GIL released      ↑ GIL acquired            │
│                                                                  │
│  Thread 2:      [prep][─────I/O wait─────][process]             │
│                        ↓ GIL released                            │
│                                                                  │
│  Thread 3:           [prep][─────I/O wait─────][process]        │
│                                                                  │
│  I/O operations (network, disk) release the GIL                 │
│  Multiple threads can wait on I/O simultaneously                │
│  Result: True parallelism for I/O wait time                     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 27.4 When the GIL is Released

### Automatic GIL Release

```python
# GIL is released during:

# 1. File I/O
with open('file.txt', 'r') as f:
    data = f.read()  # GIL released during actual read

# 2. Network I/O
import socket
s = socket.socket()
s.connect(('host', 80))  # GIL released
s.recv(1024)              # GIL released

# 3. time.sleep()
import time
time.sleep(1)  # GIL released

# 4. Certain C extension operations
import hashlib
hashlib.sha256(b'x' * 10**6).hexdigest()  # May release GIL
```

### Manual GIL Release (C Extensions)

```c
// In C extension code
static PyObject* my_function(PyObject* self, PyObject* args) {
    PyObject* result;

    // Do Python stuff (need GIL)
    // ...

    // Release GIL for CPU-intensive C code
    Py_BEGIN_ALLOW_THREADS
    // C code here runs without GIL
    // Other Python threads can run!
    do_heavy_computation();
    Py_END_ALLOW_THREADS

    // Back to Python (GIL reacquired)
    result = PyLong_FromLong(42);
    return result;
}
```

## 27.5 Thread Safety Implications

### What GIL Guarantees

```python
# Single bytecode instruction execution is atomic
# But compound operations are NOT

import dis

# This is NOT atomic (multiple bytecodes):
counter = 0
def increment():
    global counter
    counter += 1

dis.dis(increment)
# LOAD_GLOBAL    counter
# LOAD_CONST     1
# BINARY_ADD
# STORE_GLOBAL   counter
# GIL can be released between any of these!
```

### GIL Doesn't Prevent All Races

```python
import threading

counter = 0

def increment():
    global counter
    for _ in range(100000):
        counter += 1  # NOT atomic!

threads = [threading.Thread(target=increment) for _ in range(10)]
for t in threads:
    t.start()
for t in threads:
    t.join()

print(f"Expected: 1000000")
print(f"Actual:   {counter}")  # Often less!
```

### Proper Synchronization

```python
import threading

counter = 0
lock = threading.Lock()

def safe_increment():
    global counter
    for _ in range(100000):
        with lock:  # Explicit synchronization
            counter += 1

threads = [threading.Thread(target=safe_increment) for _ in range(10)]
for t in threads:
    t.start()
for t in threads:
    t.join()

print(f"Expected: 1000000")
print(f"Actual:   {counter}")  # Correct!
```

## 27.6 Thread Safety Implications

### Data Structure Thread Safety

```python
# Generally thread-safe (single bytecode operations):
lst = []
lst.append(x)      # Single CALL instruction
dct = {}
dct[key] = value   # Single STORE_SUBSCR instruction

# NOT thread-safe (multiple operations):
lst = []
if x not in lst:   # Check
    lst.append(x)  # Then modify (race window!)

# Safe version:
import threading
lock = threading.Lock()
with lock:
    if x not in lst:
        lst.append(x)
```

### Atomic vs Non-Atomic Operations

| Operation | Atomic? | Notes |
|-----------|---------|-------|
| `x = 1` | Yes | Single STORE_FAST |
| `lst.append(x)` | Yes | Single method call |
| `dct[k] = v` | Yes | Single STORE_SUBSCR |
| `x += 1` | **No** | LOAD, ADD, STORE |
| `lst.extend(x)` | **No** | Multiple internal operations |
| `if k in d:` then `d[k]` | **No** | Check-then-act race |

## GIL and Threading Summary

```
┌─────────────────────────────────────────────────────────────────┐
│              When to Use Python Threading                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ✓ I/O-bound workloads                                          │
│    - Network requests                                            │
│    - File operations                                             │
│    - Database queries                                            │
│    - User input waiting                                          │
│                                                                  │
│  ✗ CPU-bound workloads                                          │
│    - Heavy computation                                           │
│    - Data processing                                             │
│    - Image/video processing                                      │
│    → Use multiprocessing or C extensions instead                │
│                                                                  │
│  Still need locks for:                                           │
│    - Compound operations                                         │
│    - Check-then-act patterns                                     │
│    - Shared mutable state                                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Summary

- Python threads are **real OS threads**
- GIL prevents **parallel Python execution** (CPU-bound)
- GIL is **released during I/O** (threading helps I/O-bound)
- **Not all operations are atomic** - still need locks
- Use `threading` for I/O-bound, `multiprocessing` for CPU-bound

## Practice Exercises

1. Benchmark I/O-bound vs CPU-bound threading performance
2. Demonstrate a race condition despite the GIL
3. Profile where time is spent in threaded code
4. Compare threading vs asyncio for I/O-bound work

---

[← Previous: GIL Scheduling](chapter-26-gil-scheduling.md) | [Next: GIL Atomicity →](chapter-28-gil-atomicity.md)

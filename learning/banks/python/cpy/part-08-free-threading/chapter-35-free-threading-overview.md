# Chapter 35: Free-Threading Overview (PEP 703)

## 35.1 What is Free-Threaded Python?

Free-threaded Python removes the Global Interpreter Lock (GIL), allowing true parallel execution:

```
┌─────────────────────────────────────────────────────────────────┐
│                Free-Threaded Python                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Traditional Python (with GIL):                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Thread 1: ████░░░░████░░░░████░░░░                     │    │
│  │  Thread 2: ░░░░████░░░░████░░░░████                     │    │
│  │  Thread 3: ░░░░░░░░░░░░░░░░████░░░░████                 │    │
│  │            ↑                                             │    │
│  │            Only ONE thread executes Python at a time    │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Free-Threaded Python (no GIL):                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Thread 1: ████████████████████████████████████         │    │
│  │  Thread 2: ████████████████████████████████████         │    │
│  │  Thread 3: ████████████████████████████████████         │    │
│  │            ↑                                             │    │
│  │            ALL threads execute Python simultaneously    │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Result: True CPU parallelism for Python code!                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 35.2 PEP 703: Making CPython Free-Threaded

### The Proposal

PEP 703, authored by Sam Gross, proposes making the GIL optional in CPython. Key goals:

1. **Optional**: Build flag to enable/disable GIL
2. **Backward Compatible**: Existing code should work
3. **Minimal Overhead**: Single-threaded performance ~5-10% slower
4. **Gradual Migration**: Extensions can opt-in over time

### Build Configuration

```bash
# Build free-threaded Python
./configure --disable-gil
make -j$(nproc)

# Check if GIL is disabled
python -c "import sys; print(sys._is_gil_enabled())"
# False (free-threaded)

# Traditional build
./configure
make -j$(nproc)

python -c "import sys; print(sys._is_gil_enabled())"
# True (GIL-enabled)
```

## 35.3 Key Technical Components

### Overview of Changes

```
┌─────────────────────────────────────────────────────────────────┐
│              PEP 703 Technical Components                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Biased Reference Counting                                    │
│     • Fast path for "owning" thread (no atomics)               │
│     • Slow path for cross-thread access (atomic + deferred)    │
│                                                                  │
│  2. Immortal Objects                                             │
│     • Common objects never deallocated                          │
│     • No refcount operations needed (None, True, etc.)          │
│                                                                  │
│  3. Per-Object Locks                                             │
│     • Fine-grained locking for mutable objects                  │
│     • Critical sections instead of GIL                          │
│                                                                  │
│  4. Deferred Reference Counting                                  │
│     • Cross-thread decrefs are queued                           │
│     • Processed in batches by owning thread                     │
│                                                                  │
│  5. Thread-Safe Data Structures                                  │
│     • dict, list, set redesigned for concurrency                │
│     • Lock-free where possible                                   │
│                                                                  │
│  6. Mimalloc Integration                                         │
│     • Thread-local allocation                                    │
│     • Reduces allocator contention                              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 35.4 Performance Characteristics

### Single-Threaded Performance

```python
import sys
import time

def benchmark():
    """CPU-bound benchmark."""
    total = 0
    for i in range(10_000_000):
        total += i * i
    return total

# Single-threaded performance comparison
start = time.perf_counter()
result = benchmark()
elapsed = time.perf_counter() - start

print(f"GIL enabled: {sys._is_gil_enabled()}")
print(f"Time: {elapsed:.2f}s")

# Expected results:
# GIL-enabled:   1.00s (baseline)
# Free-threaded: 1.05-1.10s (~5-10% slower)
```

### Multi-Threaded Performance

```python
import sys
import time
import threading

def cpu_work(n):
    total = 0
    for i in range(n):
        total += i * i
    return total

def benchmark_threads(num_threads):
    threads = []
    start = time.perf_counter()

    for _ in range(num_threads):
        t = threading.Thread(target=cpu_work, args=(5_000_000,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    return time.perf_counter() - start

print(f"GIL enabled: {sys._is_gil_enabled()}")

for n in [1, 2, 4, 8]:
    elapsed = benchmark_threads(n)
    print(f"{n} threads: {elapsed:.2f}s")

# Expected results (4-core machine):
# GIL-enabled:   1 thread: 1.0s, 4 threads: 4.0s (no speedup!)
# Free-threaded: 1 thread: 1.1s, 4 threads: 1.1s (4x speedup!)
```

## 35.5 Checking Free-Threaded Status

### Runtime Detection

```python
import sys

# Check if GIL is enabled
def is_free_threaded():
    """Check if running in free-threaded mode."""
    return not sys._is_gil_enabled()

if is_free_threaded():
    print("Running in free-threaded mode")
    print("True parallelism available!")
else:
    print("Running with GIL")
    print("Consider multiprocessing for CPU parallelism")

# Build information
print(f"Python version: {sys.version}")
print(f"Implementation: {sys.implementation.name}")
```

### Feature Detection

```python
import sys

# Check for specific free-threading features
def check_free_threading_features():
    features = {}

    # GIL status
    features['gil_disabled'] = not sys._is_gil_enabled()

    # Check for immortal objects
    features['immortal_objects'] = hasattr(sys, 'getallocatedblocks')

    # Check for per-interpreter GIL
    try:
        import _interpreters
        features['per_interpreter_gil'] = True
    except ImportError:
        features['per_interpreter_gil'] = False

    return features

print(check_free_threading_features())
```

## 35.6 Thread Safety Considerations

### What Changes

```python
# With GIL: These operations were "atomic"
# Without GIL: Need explicit synchronization

import threading

# UNSAFE without explicit synchronization
counter = 0

def increment():
    global counter
    for _ in range(100000):
        counter += 1  # Not atomic without GIL!

# Thread-safe version
counter_lock = threading.Lock()
counter = 0

def safe_increment():
    global counter
    for _ in range(100000):
        with counter_lock:
            counter += 1

# Or use atomic operations
from threading import atomic  # Python 3.13+
atomic_counter = atomic.AtomicInt(0)

def atomic_increment():
    for _ in range(100000):
        atomic_counter.add(1)
```

### Built-in Type Safety

```python
# Built-in types have internal synchronization
# These operations are still safe:

my_list = []
my_dict = {}

def thread_work():
    # append is thread-safe
    my_list.append(1)

    # dict operations are thread-safe
    my_dict['key'] = 'value'

# But compound operations still need locks!
def unsafe_compound():
    # Check-then-act is NOT safe
    if 'key' not in my_dict:  # Another thread might add it
        my_dict['key'] = 'value'  # Race condition!

# Safe version
dict_lock = threading.Lock()
def safe_compound():
    with dict_lock:
        if 'key' not in my_dict:
            my_dict['key'] = 'value'
```

## 35.7 Migration Guide

### Step 1: Check Compatibility

```python
# Test your code in free-threaded mode
# Run with: python --enable-gil=0 your_script.py (3.13+)

import warnings
import sys

if not sys._is_gil_enabled():
    warnings.warn(
        "Running without GIL - check for race conditions",
        RuntimeWarning
    )
```

### Step 2: Identify Shared State

```python
# Audit global and shared state
# Look for patterns like:

# Global mutable state (needs protection)
_cache = {}  # Shared cache
_counter = 0  # Shared counter

# Thread-local state (already safe)
import threading
_local = threading.local()
_local.value = 0  # Thread-local, no sharing
```

### Step 3: Add Synchronization

```python
import threading

# Use locks for shared mutable state
_cache_lock = threading.Lock()
_cache = {}

def get_or_compute(key, compute_func):
    with _cache_lock:
        if key in _cache:
            return _cache[key]

    # Compute outside lock
    value = compute_func(key)

    with _cache_lock:
        # Double-check pattern
        if key not in _cache:
            _cache[key] = value
        return _cache[key]
```

## 35.8 Python 3.13 and Beyond

### Timeline

```
┌─────────────────────────────────────────────────────────────────┐
│              Free-Threading Timeline                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Python 3.12 (2023)                                              │
│  └── Per-interpreter GIL (subinterpreters)                      │
│                                                                  │
│  Python 3.13 (2024)                                              │
│  └── Experimental free-threaded build (--disable-gil)           │
│  └── Opt-in, not default                                        │
│  └── C extension compatibility flags                            │
│                                                                  │
│  Python 3.14+ (2025+)                                            │
│  └── Performance optimizations                                   │
│  └── More extensions updated                                     │
│  └── Broader testing                                             │
│                                                                  │
│  Future                                                          │
│  └── Free-threaded may become default                           │
│  └── GIL build may be deprecated                                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Using Free-Threaded Python 3.13

```bash
# Download free-threaded installer (separate build)
# Or build from source:
git clone https://github.com/python/cpython
cd cpython
./configure --disable-gil --prefix=/opt/python313t
make -j$(nproc)
make install

# Run with GIL control
/opt/python313t/bin/python3.13t script.py

# Or control at runtime
/opt/python313t/bin/python3.13t -X gil=1 script.py  # Enable GIL
/opt/python313t/bin/python3.13t -X gil=0 script.py  # Disable GIL
```

## 35.9 When to Use Free-Threaded Python

### Good Use Cases

```python
# 1. CPU-bound parallel processing
def parallel_computation():
    import concurrent.futures
    import math

    def compute(n):
        return sum(math.sqrt(i) for i in range(n))

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(compute, [10_000_000] * 4))
    return results

# 2. Concurrent data processing
def parallel_data_pipeline():
    import queue
    import threading

    def producer(q, data):
        for item in data:
            q.put(process(item))
        q.put(None)

    def consumer(q, results):
        while True:
            item = q.get()
            if item is None:
                break
            results.append(item)

    # Multiple producers and consumers can run truly parallel

# 3. Scientific computing with NumPy
def parallel_numpy():
    import numpy as np
    from concurrent.futures import ThreadPoolExecutor

    def compute_chunk(arr):
        return np.sum(arr ** 2)

    data = np.random.random((1000000,))
    chunks = np.array_split(data, 4)

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(compute_chunk, chunks))
```

### Not Ideal For

```python
# 1. I/O-bound tasks (asyncio is better)
# Free-threading adds overhead for tasks that already parallelize well

# 2. Single-threaded applications
# ~5-10% overhead with no benefit

# 3. Code with many shared mutable objects
# Lock contention may negate parallelism benefits
```

## Summary

- **PEP 703** enables optional GIL removal in CPython
- **Free-threaded mode** allows true CPU parallelism with threads
- **Single-threaded overhead** is ~5-10% (acceptable trade-off)
- **Key techniques**: Biased reference counting, immortal objects, per-object locks
- **Migration** requires identifying and protecting shared state
- **Python 3.13+** offers experimental free-threaded builds
- **Gradual adoption** preserves ecosystem compatibility

## Practice Exercises

1. Build Python 3.13+ with `--disable-gil` and run benchmarks
2. Identify race conditions in existing threaded code
3. Compare performance of threading vs multiprocessing in free-threaded mode
4. Port a GIL-dependent extension to support free-threading

---

[← Previous: C Extensions and GIL](../part-07-concurrency/chapter-34-c-extensions-gil.md) | [Next: Biased Reference Counting →](chapter-36-biased-reference-counting.md)

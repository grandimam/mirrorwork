# Chapter 37: Immortal Objects

## 37.1 What Are Immortal Objects?

Immortal objects have a special reference count that never changes:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Immortal Objects                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Regular Object:                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  ob_refcnt: 5                                            │    │
│  │  Py_INCREF: ob_refcnt++ → 6                             │    │
│  │  Py_DECREF: ob_refcnt-- → 5                             │    │
│  │  When refcnt == 0: deallocated                          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Immortal Object:                                                │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  ob_refcnt: IMMORTAL_REFCNT (special value)             │    │
│  │  Py_INCREF: NOP (do nothing)                            │    │
│  │  Py_DECREF: NOP (do nothing)                            │    │
│  │  Never deallocated                                       │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Benefits:                                                       │
│  • No atomic operations needed for common objects               │
│  • No cache line bouncing between threads                       │
│  • Perfect for heavily shared objects (None, True, etc.)       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 37.2 Why Immortal Objects Matter

### The Problem with Common Objects

```python
# None is referenced MILLIONS of times
def example():
    x = None  # Py_INCREF(Py_None)
    return    # Py_DECREF(Py_None)

# Every function return, default argument, etc.
# Without immortality: Massive contention on None's refcount

# In a 4-thread program:
# Thread 1: INCREF(None) - needs exclusive cache line
# Thread 2: INCREF(None) - waits for cache line
# Thread 3: INCREF(None) - waits for cache line
# Thread 4: INCREF(None) - waits for cache line
# Result: Serial execution due to cache line bouncing!
```

### The Solution

```c
// Check if object is immortal
#define _Py_IsImmortal(op) (op->ob_refcnt == _Py_IMMORTAL_REFCNT)

// Optimized INCREF for free-threaded Python
static inline void Py_INCREF(PyObject *op) {
    if (_Py_IsImmortal(op)) {
        return;  // No-op for immortal objects
    }
    // Regular biased reference counting
    _Py_INCREF_BIASED(op);
}

static inline void Py_DECREF(PyObject *op) {
    if (_Py_IsImmortal(op)) {
        return;  // No-op for immortal objects
    }
    // Regular biased reference counting
    _Py_DECREF_BIASED(op);
}
```

## 37.3 Immortal Reference Count Value

### The Magic Number

```c
// The immortal reference count (Python 3.12+)
// Uses a value that's unlikely to be reached normally
// and easy to detect

#if SIZEOF_VOID_P == 8
// 64-bit: Use high bit pattern
#define _Py_IMMORTAL_REFCNT  ((Py_ssize_t)(1ULL << 62))
#else
// 32-bit: Use high bit pattern
#define _Py_IMMORTAL_REFCNT  ((Py_ssize_t)(1UL << 30))
#endif

// Quick check
#define _Py_IsImmortal(op) \
    ((op)->ob_refcnt >= _Py_IMMORTAL_REFCNT)

// Alternative: Use special bit
#define _Py_IMMORTAL_BIT     (1ULL << 63)
#define _Py_IsImmortal(op)   ((op)->ob_refcnt & _Py_IMMORTAL_BIT)
```

### Why This Value?

```
┌─────────────────────────────────────────────────────────────────┐
│              Immortal Reference Count Design                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  64-bit refcount (simplified):                                   │
│  ┌────────────────────────────────────────────────────────┐     │
│  │ Bit 63│ Bit 62 │ Bits 61-0                            │     │
│  │ Sign  │ Imm.   │ Actual count                         │     │
│  └────────────────────────────────────────────────────────┘     │
│                                                                  │
│  Regular object: 0 0 XXXXXX...X (normal count)                  │
│  Immortal:       0 1 XXXXXX...X (immortal, count ignored)       │
│                                                                  │
│  Check: if (refcnt >= (1 << 62)) → immortal                     │
│                                                                  │
│  Benefits:                                                       │
│  • Single comparison to detect                                   │
│  • Room for accidental increments (won't overflow)              │
│  • Backward compatible bit pattern                              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 37.4 Which Objects Are Immortal?

### Built-in Singletons

```c
// Always immortal (initialized at startup)
Py_None        // The None object
Py_True        // True
Py_False       // False
Py_Ellipsis    // ...
Py_NotImplemented

// Type objects (referenced by every instance)
&PyType_Type
&PyLong_Type
&PyUnicode_Type
&PyList_Type
&PyDict_Type
// ... all built-in types
```

### Small Integers

```c
// Small integers are cached and immortal
// Range: typically -5 to 256

#define NSMALLPOSINTS 257
#define NSMALLNEGINTS 5

static PyLongObject small_ints[NSMALLNEGINTS + NSMALLPOSINTS];

void _PyLong_Init(void) {
    for (int i = -NSMALLNEGINTS; i < NSMALLPOSINTS; i++) {
        PyLongObject *obj = &small_ints[i + NSMALLNEGINTS];
        // Initialize with immortal refcount
        obj->ob_base.ob_refcnt = _Py_IMMORTAL_REFCNT;
        // Set value...
    }
}
```

### Interned Strings

```c
// Interned strings can be immortal
PyObject* PyUnicode_InternInPlace(PyObject **p) {
    PyObject *s = *p;

    // Look up in intern dict
    PyObject *interned = lookup_interned(s);
    if (interned != NULL) {
        // Already interned - may be immortal
        Py_DECREF(s);
        Py_INCREF(interned);
        *p = interned;
        return interned;
    }

    // Intern new string
    // May be made immortal if it's a common string
    add_to_intern_dict(s);

    if (should_be_immortal(s)) {
        _Py_SetImmortal(s);
    }

    return s;
}
```

## 37.5 Making Objects Immortal

### At Initialization

```c
// During Python startup
void _Py_InitializeStaticObjects(void) {
    // None
    _Py_SetImmortal(Py_None);

    // Booleans
    _Py_SetImmortal(Py_True);
    _Py_SetImmortal(Py_False);

    // Type objects
    _Py_SetImmortal((PyObject*)&PyType_Type);
    _Py_SetImmortal((PyObject*)&PyLong_Type);
    // ... etc

    // Empty containers
    _Py_SetImmortal(PyTuple_New(0));  // Empty tuple
    _Py_SetImmortal(PyFrozenSet_New(NULL));  // Empty frozenset
}

static inline void _Py_SetImmortal(PyObject *op) {
    op->ob_refcnt = _Py_IMMORTAL_REFCNT;
}
```

### Runtime Immortalization

```c
// Objects can become immortal at runtime
// (e.g., heavily shared objects)

void _Py_MakeImmortalIfNeeded(PyObject *op) {
    // Heuristic: If object is shared across many threads
    // and referenced very frequently, make it immortal

    if (op->ob_refcnt > IMMORTAL_THRESHOLD &&
        _Py_IsSharedAcrossThreads(op)) {
        _Py_SetImmortal(op);
    }
}
```

## 37.6 Implementation in CPython

### Full INCREF/DECREF Implementation

```c
// Python 3.12+ implementation (simplified)

static inline void Py_INCREF(PyObject *op) {
    #ifdef Py_GIL_DISABLED
    // Free-threaded mode
    if (_Py_IsImmortal(op)) {
        return;  // Fast path: immortal
    }
    // Biased reference counting
    if (_Py_IsOwnedByCurrentThread(op)) {
        op->ob_refcnt_local++;
    } else {
        _Py_atomic_add(&op->ob_refcnt_shared, 1);
    }
    #else
    // Traditional mode (with GIL)
    op->ob_refcnt++;
    #endif
}

static inline void Py_DECREF(PyObject *op) {
    #ifdef Py_GIL_DISABLED
    // Free-threaded mode
    if (_Py_IsImmortal(op)) {
        return;  // Fast path: immortal
    }
    // Biased reference counting with deallocation
    if (_Py_IsOwnedByCurrentThread(op)) {
        if (--op->ob_refcnt_local == 0 &&
            op->ob_refcnt_shared == 0) {
            _Py_Dealloc(op);
        }
    } else {
        _Py_DECREF_SHARED(op);
    }
    #else
    // Traditional mode (with GIL)
    if (--op->ob_refcnt == 0) {
        _Py_Dealloc(op);
    }
    #endif
}
```

## 37.7 Impact on Memory Management

### Objects That Never Die

```
┌─────────────────────────────────────────────────────────────────┐
│              Immortal Objects and Memory                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Immortal objects are NEVER deallocated:                        │
│                                                                  │
│  Pros:                                                           │
│  ✓ No deallocation overhead                                     │
│  ✓ No reference count contention                                │
│  ✓ Perfect for fork() (shared pages stay shared)               │
│                                                                  │
│  Cons:                                                           │
│  ✗ Memory cannot be reclaimed                                   │
│  ✗ Must be careful about what becomes immortal                 │
│                                                                  │
│  In practice:                                                    │
│  • Immortal objects are small (None, True, ints)               │
│  • Total immortal memory: ~few MB                               │
│  • Benefit far outweighs cost                                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Copy-on-Write Benefits

```python
# Fork behavior with immortal objects

import os

# Before fork: Parent has loaded Python runtime
# Immortal objects (None, True, ints, etc.) are in shared pages

pid = os.fork()

if pid == 0:
    # Child process
    # Immortal objects: Refcount never changes
    # Shared memory pages stay shared (no COW)
    x = None  # No write to refcount → page stays shared
else:
    # Parent process
    y = None  # Same page, still shared

# Without immortal objects:
# Each Py_INCREF would trigger copy-on-write
# Doubling memory usage for forked processes
```

## 37.8 Debugging Immortal Objects

### Checking Immortality

```python
import sys
import ctypes

def is_immortal(obj):
    """Check if an object is immortal (CPython 3.12+)."""
    # Get the object's address
    obj_id = id(obj)

    # Read the refcount from memory
    # This is implementation-specific
    if sys.maxsize > 2**32:
        # 64-bit
        IMMORTAL_THRESHOLD = 1 << 62
    else:
        # 32-bit
        IMMORTAL_THRESHOLD = 1 << 30

    refcnt = sys.getrefcount(obj) - 1  # Subtract our reference

    # Actually need to read raw memory for true check
    # sys.getrefcount may return clamped value

    return refcnt >= IMMORTAL_THRESHOLD

# Test
print(f"None immortal: {is_immortal(None)}")  # True
print(f"True immortal: {is_immortal(True)}")  # True
print(f"42 immortal: {is_immortal(42)}")      # True (small int)
print(f"1000 immortal: {is_immortal(1000)}")  # False (not cached)
print(f"[] immortal: {is_immortal([])}")      # False
```

### Listing Immortal Objects

```python
import gc
import sys

def find_immortal_objects():
    """Find all immortal objects (approximation)."""
    immortal = []

    # Check built-in singletons
    singletons = [None, True, False, Ellipsis, NotImplemented]
    for obj in singletons:
        immortal.append((type(obj).__name__, repr(obj)[:50]))

    # Check small integers
    for i in range(-5, 257):
        immortal.append(('int', str(i)))

    # Check type objects
    for obj in gc.get_objects():
        if isinstance(obj, type):
            if sys.getrefcount(obj) > 10000:  # Heuristic
                immortal.append(('type', obj.__name__))

    return immortal

# Show some immortal objects
for typ, rep in find_immortal_objects()[:20]:
    print(f"{typ}: {rep}")
```

## 37.9 Performance Impact

### Benchmark: With vs Without Immortal Objects

```python
import time
import threading

def benchmark_none_refs(iterations):
    """Benchmark reference operations on None."""
    start = time.perf_counter()
    for _ in range(iterations):
        x = None
        del x
    return time.perf_counter() - start

def threaded_benchmark(num_threads, iterations):
    """Run benchmark in multiple threads."""
    threads = []
    results = []

    def worker():
        result = benchmark_none_refs(iterations)
        results.append(result)

    start = time.perf_counter()
    for _ in range(num_threads):
        t = threading.Thread(target=worker)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    total_time = time.perf_counter() - start
    return total_time, sum(results) / len(results)

# Single-threaded
single = benchmark_none_refs(10_000_000)
print(f"Single-threaded: {single:.3f}s")

# Multi-threaded
for n in [2, 4, 8]:
    total, avg = threaded_benchmark(n, 10_000_000 // n)
    print(f"{n} threads: {total:.3f}s total, {avg:.3f}s avg per thread")

# Expected results with immortal None:
# Single-threaded: 0.5s
# 2 threads: 0.3s (scales!)
# 4 threads: 0.15s (scales!)
# 8 threads: 0.08s (scales!)

# Without immortal None (hypothetical):
# Single-threaded: 0.5s
# 2 threads: 0.5s (no scaling - contention!)
# 4 threads: 0.6s (worse due to cache bouncing)
# 8 threads: 0.8s (terrible scaling)
```

## Summary

- **Immortal objects** have a special refcount that never changes
- **INCREF/DECREF are no-ops** for immortal objects
- **Eliminates contention** on frequently accessed objects
- **Common immortal objects**: None, True, False, small integers
- **Fork-friendly**: No copy-on-write for immortal object pages
- **Minimal memory cost**: Only a few MB of immortal objects
- **Critical for free-threaded** Python performance

## Practice Exercises

1. Identify which objects in your program would benefit from immortality
2. Measure cache line contention with and without immortal objects
3. Analyze fork() memory behavior with immortal objects
4. Benchmark multi-threaded code that heavily uses None

---

[← Previous: Biased Reference Counting](chapter-36-biased-reference-counting.md) | [Next: Per-Object Locks →](chapter-38-per-object-locks.md)

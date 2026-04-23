# Chapter 38: Per-Object Locks

## 38.1 From GIL to Fine-Grained Locking

Without the GIL, mutable objects need their own synchronization:

```
┌─────────────────────────────────────────────────────────────────┐
│              GIL vs Per-Object Locks                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  With GIL:                                                       │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Thread 1: list.append(x)                               │    │
│  │  Thread 2: list.append(y)   ← Must wait for GIL        │    │
│  │                                                          │    │
│  │  GIL protects ALL objects simultaneously                │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  With Per-Object Locks:                                          │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Thread 1: list1.append(x)  ← Holds list1's lock       │    │
│  │  Thread 2: list2.append(y)  ← Holds list2's lock       │    │
│  │            (Can run in parallel!)                        │    │
│  │                                                          │    │
│  │  Thread 3: list1.pop()      ← Waits for list1's lock   │    │
│  │            (Only waits if accessing same object)        │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Benefit: Parallelism when accessing different objects          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 38.2 Critical Sections

### What Are Critical Sections?

```c
// Critical sections protect object operations
// More lightweight than full locks

// Enter critical section (may block if contended)
Py_BEGIN_CRITICAL_SECTION(obj);

// ... mutate object ...

// Exit critical section
Py_END_CRITICAL_SECTION();

// For operations on two objects
Py_BEGIN_CRITICAL_SECTION2(obj1, obj2);
// ... mutate both objects ...
Py_END_CRITICAL_SECTION2();
```

### Implementation

```c
// Critical section implementation (simplified)
typedef struct {
    PyMutex mutex;
    int recursion_count;
    PyThreadState *owner;
} _PyCriticalSection;

// Object header includes critical section data
typedef struct _object {
    Py_ssize_t ob_refcnt;
    PyTypeObject *ob_type;
    // For mutable objects:
    PyMutex ob_mutex;  // Per-object lock
} PyObject;

#define Py_BEGIN_CRITICAL_SECTION(op) \
    do { \
        PyMutex_Lock(&(op)->ob_mutex); \
    } while (0)

#define Py_END_CRITICAL_SECTION() \
    do { \
        PyMutex_Unlock(&_current_critical_section.mutex); \
    } while (0)
```

## 38.3 Which Objects Have Locks?

### Mutable Built-in Types

```c
// Types that need per-object locks:

// List
typedef struct {
    PyObject_VAR_HEAD
    PyObject **ob_item;
    Py_ssize_t allocated;
    PyMutex ob_mutex;  // Protects modifications
} PyListObject;

// Dict
typedef struct {
    PyObject_HEAD
    Py_ssize_t ma_used;
    PyDictKeysObject *ma_keys;
    PyObject **ma_values;
    PyMutex ob_mutex;  // Protects modifications
} PyDictObject;

// Set
typedef struct {
    PyObject_HEAD
    Py_ssize_t fill;
    Py_ssize_t used;
    setentry *table;
    PyMutex ob_mutex;
} PySetObject;
```

### Immutable Types Don't Need Locks

```c
// These types are immutable - no locking needed:

// Tuple (immutable after creation)
typedef struct {
    PyObject_VAR_HEAD
    PyObject *ob_item[1];
    // No mutex - contents never change
} PyTupleObject;

// String (immutable)
typedef struct {
    PyObject_HEAD
    Py_ssize_t length;
    Py_hash_t hash;
    // No mutex - contents never change
} PyUnicodeObject;

// Integer (immutable)
// FrozenSet (immutable)
// Bytes (immutable)
```

## 38.4 List Operations with Locking

### Thread-Safe List Operations

```c
// list.append() implementation
static PyObject *
list_append(PyListObject *self, PyObject *obj)
{
    Py_BEGIN_CRITICAL_SECTION(self);

    if (list_resize(self, Py_SIZE(self) + 1) < 0) {
        Py_END_CRITICAL_SECTION();
        return NULL;
    }

    Py_INCREF(obj);
    self->ob_item[Py_SIZE(self) - 1] = obj;

    Py_END_CRITICAL_SECTION();
    Py_RETURN_NONE;
}

// list.pop() implementation
static PyObject *
list_pop(PyListObject *self, PyObject *args)
{
    Py_ssize_t i = -1;
    PyObject *v;

    if (!PyArg_ParseTuple(args, "|n", &i))
        return NULL;

    Py_BEGIN_CRITICAL_SECTION(self);

    if (Py_SIZE(self) == 0) {
        Py_END_CRITICAL_SECTION();
        PyErr_SetString(PyExc_IndexError, "pop from empty list");
        return NULL;
    }

    // Normalize negative index
    if (i < 0)
        i += Py_SIZE(self);

    v = self->ob_item[i];
    // ... remove item ...

    Py_END_CRITICAL_SECTION();
    return v;
}
```

## 38.5 Dict Operations with Locking

### Thread-Safe Dictionary

```c
// dict.__setitem__ implementation
static int
dict_setitem(PyDictObject *mp, PyObject *key, PyObject *value)
{
    Py_hash_t hash;

    // Compute hash outside critical section
    hash = PyObject_Hash(key);
    if (hash == -1)
        return -1;

    Py_BEGIN_CRITICAL_SECTION(mp);

    // Insert into dict
    int result = insertdict(mp, key, hash, value);

    Py_END_CRITICAL_SECTION();
    return result;
}

// dict.__getitem__ - often lock-free for reads
static PyObject *
dict_getitem(PyDictObject *mp, PyObject *key)
{
    Py_hash_t hash;
    PyObject *value;

    hash = PyObject_Hash(key);
    if (hash == -1)
        return NULL;

    // Read can be lock-free in many cases
    // Using careful memory ordering
    value = _PyDict_GetItem_LockFree(mp, key, hash);

    if (value == NULL && !PyErr_Occurred()) {
        // Key not found, need lock for certain checks
        Py_BEGIN_CRITICAL_SECTION(mp);
        value = lookdict(mp, key, hash);
        Py_END_CRITICAL_SECTION();
    }

    return value;
}
```

## 38.6 Avoiding Deadlocks

### Lock Ordering

```c
// When locking multiple objects, use consistent ordering
// to prevent deadlocks

Py_BEGIN_CRITICAL_SECTION2(obj1, obj2)
// Internally orders by memory address:
// if (obj1 < obj2) { lock(obj1); lock(obj2); }
// else { lock(obj2); lock(obj1); }

// Example: list.extend(other_list)
static PyObject *
list_extend(PyListObject *self, PyObject *iterable)
{
    if (PyList_Check(iterable)) {
        PyListObject *other = (PyListObject *)iterable;

        // Lock both lists in consistent order
        Py_BEGIN_CRITICAL_SECTION2(self, other);

        // ... copy elements ...

        Py_END_CRITICAL_SECTION2();
    } else {
        // Single lock for self
        Py_BEGIN_CRITICAL_SECTION(self);
        // Iterate without holding other's lock
        // ... iterate and append ...
        Py_END_CRITICAL_SECTION();
    }

    Py_RETURN_NONE;
}
```

### Avoiding Lock Hierarchy Violations

```c
// WRONG: Can deadlock
void bad_operation(PyObject *a, PyObject *b) {
    Py_BEGIN_CRITICAL_SECTION(a);
    // Some work...
    Py_BEGIN_CRITICAL_SECTION(b);  // Another thread might have b, waiting for a
    // ...
    Py_END_CRITICAL_SECTION();
    Py_END_CRITICAL_SECTION();
}

// CORRECT: Use ordered locking
void good_operation(PyObject *a, PyObject *b) {
    Py_BEGIN_CRITICAL_SECTION2(a, b);  // Ordered internally
    // ...
    Py_END_CRITICAL_SECTION2();
}
```

## 38.7 Lock-Free Techniques

### Read-Side Optimizations

```c
// Many read operations can be lock-free
// Using memory barriers and careful data structure design

// Lock-free dict lookup (simplified)
static PyObject *
_PyDict_GetItem_LockFree(PyDictObject *mp, PyObject *key, Py_hash_t hash)
{
    PyDictKeysObject *keys;
    PyObject *value;

    // Read keys pointer with acquire semantics
    keys = _Py_atomic_load_ptr_acquire(&mp->ma_keys);

    // Read values array
    PyObject **values = _Py_atomic_load_ptr_acquire(&mp->ma_values);

    // Find entry
    Py_ssize_t ix = lookdict_index(keys, hash);
    if (ix < 0) {
        return NULL;
    }

    // Read value with acquire semantics
    if (values != NULL) {
        value = _Py_atomic_load_ptr_acquire(&values[ix]);
    } else {
        value = _Py_atomic_load_ptr_acquire(&keys->dk_entries[ix].me_value);
    }

    return value;  // May need to verify it's still valid
}
```

### Atomic Operations

```c
// Use atomics for simple operations
#include <stdatomic.h>

// Atomic counter (doesn't need critical section)
typedef struct {
    _Atomic Py_ssize_t count;
} AtomicCounter;

void counter_increment(AtomicCounter *c) {
    atomic_fetch_add(&c->count, 1);
}

Py_ssize_t counter_get(AtomicCounter *c) {
    return atomic_load(&c->count);
}
```

## 38.8 Performance Considerations

### Lock Granularity Trade-offs

```
┌─────────────────────────────────────────────────────────────────┐
│              Lock Granularity Trade-offs                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Coarse-grained (GIL):                                           │
│  + Simple                                                        │
│  + Low overhead for single-threaded                             │
│  - No parallelism                                                │
│                                                                  │
│  Per-object locks:                                               │
│  + Good parallelism for different objects                       │
│  + Reasonable overhead                                           │
│  - Contention on hot objects                                    │
│                                                                  │
│  Per-field locks:                                                │
│  + Maximum parallelism                                           │
│  - High memory overhead                                          │
│  - Complex implementation                                        │
│                                                                  │
│  Choice: Per-object is the sweet spot for Python                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Lock Overhead

```python
import time
import threading

def benchmark_dict_ops(d, iterations):
    """Benchmark dictionary operations."""
    for i in range(iterations):
        d[i] = i
        _ = d.get(i)
        del d[i]

def single_threaded(iterations):
    d = {}
    start = time.perf_counter()
    benchmark_dict_ops(d, iterations)
    return time.perf_counter() - start

def multi_threaded(num_threads, iterations_per_thread):
    d = {}
    threads = []

    def worker():
        benchmark_dict_ops(d, iterations_per_thread)

    start = time.perf_counter()
    for _ in range(num_threads):
        t = threading.Thread(target=worker)
        threads.append(t)
        t.start()
    for t in threads:
        t.join()
    return time.perf_counter() - start

# Compare
single = single_threaded(100000)
multi_same = multi_threaded(4, 25000)  # Same dict
multi_diff = multi_threaded(4, 25000)  # Would be different dicts

print(f"Single-threaded: {single:.3f}s")
print(f"Multi-threaded (shared dict): {multi_same:.3f}s")
# Multi-threaded with shared dict may be slower due to lock contention
```

## 38.9 Python-Level Implications

### Explicit Synchronization Still Needed

```python
import threading

# Per-object locks make individual operations safe,
# but compound operations still need explicit locks

d = {}

# UNSAFE: Race condition between check and update
def unsafe_setdefault(d, key, value):
    if key not in d:  # Thread 1 checks
        d[key] = value  # Thread 2 might set between check and here

# SAFE: Use dict.setdefault (atomic operation)
def safe_setdefault(d, key, value):
    return d.setdefault(key, value)  # Single atomic operation

# For more complex operations, use explicit locks
lock = threading.Lock()

def safe_update_counter(d, key):
    with lock:
        d[key] = d.get(key, 0) + 1
```

### Thread-Safe Patterns

```python
import threading
from collections import defaultdict

# Pattern 1: Use thread-safe data structures
from queue import Queue
q = Queue()  # Already thread-safe

# Pattern 2: Lock for compound operations
class ThreadSafeCounter:
    def __init__(self):
        self._counts = {}
        self._lock = threading.Lock()

    def increment(self, key):
        with self._lock:
            self._counts[key] = self._counts.get(key, 0) + 1

    def get(self, key):
        with self._lock:
            return self._counts.get(key, 0)

# Pattern 3: Thread-local storage
local = threading.local()
local.cache = {}  # Each thread has own cache
```

## 38.10 Debugging Lock Issues

### Detecting Contention

```python
import threading
import time

class ContendedDict(dict):
    """Dict wrapper that tracks lock contention."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._lock = threading.Lock()
        self._contention_count = 0
        self._total_ops = 0

    def __setitem__(self, key, value):
        self._total_ops += 1
        acquired = self._lock.acquire(blocking=False)
        if not acquired:
            self._contention_count += 1
            self._lock.acquire()
        try:
            super().__setitem__(key, value)
        finally:
            self._lock.release()

    @property
    def contention_rate(self):
        if self._total_ops == 0:
            return 0
        return self._contention_count / self._total_ops

# Usage
d = ContendedDict()
# ... use in multi-threaded code ...
print(f"Contention rate: {d.contention_rate:.2%}")
```

## Summary

- **Per-object locks** replace the GIL for fine-grained synchronization
- **Critical sections** protect object mutations
- **Mutable types** (list, dict, set) have locks; immutable types don't
- **Lock ordering** prevents deadlocks
- **Lock-free reads** optimize common operations
- **Compound operations** still need explicit synchronization
- **Trade-off**: More parallelism vs. lock overhead

## Practice Exercises

1. Implement a thread-safe container using per-object locks
2. Analyze lock contention in a multi-threaded application
3. Compare performance with different lock granularities
4. Identify which operations are atomic vs. compound

---

[← Previous: Immortal Objects](chapter-37-immortal-objects.md) | [Next: Deferred Reference Counting →](chapter-39-deferred-reference-counting.md)

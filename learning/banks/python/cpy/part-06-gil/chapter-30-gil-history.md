# Chapter 30: GIL History and Removal Attempts

## 30.1 Original GIL Design (1992)

### Why the GIL Was Introduced

```
┌─────────────────────────────────────────────────────────────────┐
│                  Original Context (1992)                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1992 Computing Environment:                                     │
│  • Single-core CPUs were the norm                                │
│  • Multi-threading was rare                                      │
│  • Memory was expensive                                          │
│  • Simplicity valued over parallelism                           │
│                                                                  │
│  Python's Design Priorities:                                     │
│  • Simple implementation                                         │
│  • Easy to embed and extend in C                                 │
│  • Correct memory management                                     │
│  • Readable, maintainable code                                   │
│                                                                  │
│  The GIL Solution:                                               │
│  • Single lock protects everything                               │
│  • Reference counting remains simple                             │
│  • C extensions don't need to worry about threads               │
│  • No deadlock from object operations                            │
│                                                                  │
│  For the era, this was the RIGHT choice.                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### The Original Implementation

```c
// Simplified original GIL (Python 1.5, 1997)

static PyThread_type_lock interpreter_lock = NULL;

void PyEval_InitThreads(void) {
    interpreter_lock = PyThread_allocate_lock();
    PyThread_acquire_lock(interpreter_lock, 1);
}

void PyEval_AcquireLock(void) {
    PyThread_acquire_lock(interpreter_lock, 1);
}

void PyEval_ReleaseLock(void) {
    PyThread_release_lock(interpreter_lock);
}
```

## 30.2 Greg Stein's Free-Threading Patch (1999)

### The First Major Removal Attempt

```
┌─────────────────────────────────────────────────────────────────┐
│           Greg Stein's Free-Threading (1999)                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Approach:                                                       │
│  • Remove the GIL completely                                     │
│  • Add per-object locks (fine-grained locking)                  │
│  • Protect reference counts with atomic operations              │
│  • Add locks to all mutable data structures                     │
│                                                                  │
│  Results:                                                        │
│  • Single-threaded: ~40% SLOWER                                 │
│  • 2 threads: ~2x speedup (break-even)                          │
│  • Lock overhead was too high                                   │
│  • Memory usage increased significantly                          │
│  • Many subtle bugs introduced                                   │
│                                                                  │
│  Outcome: NOT MERGED                                             │
│  Reason: Unacceptable single-threaded performance penalty       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Why It Failed

```python
# Every object operation needed locking:

# Before (with GIL):
x.append(y)  # GIL already held, no additional locks

# After (fine-grained):
lock(x)          # Acquire x's lock
  lock(refcount) # Acquire refcount lock
  x.append(y)
  unlock(refcount)
unlock(x)

# This overhead on EVERY operation killed performance
```

## 30.3 "Gilectomy" Project (Larry Hastings, 2016)

### Larry Hastings' Attempt

```
┌─────────────────────────────────────────────────────────────────┐
│                Gilectomy Project (2016)                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Goals:                                                          │
│  • Remove GIL from CPython 3.6                                  │
│  • Keep backward compatibility with C extensions                │
│  • Minimal single-threaded performance loss                     │
│                                                                  │
│  Techniques:                                                     │
│  • Reference count changes (biased reference counting)          │
│  • Fine-grained locking where needed                            │
│  • Lock-free data structures                                    │
│  • Careful analysis of race conditions                          │
│                                                                  │
│  Results (2017):                                                 │
│  • Single-threaded: 20-30% slower                               │
│  • Multi-threaded: Scales with cores                            │
│  • Many C extension compatibility issues                        │
│  • Some segfaults and race conditions                           │
│                                                                  │
│  Outcome: NOT MERGED (but proved useful for research)           │
│                                                                  │
│  Larry's Conclusion:                                             │
│  "Making Python faster single-threaded is more valuable         │
│   than making it parallel"                                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 30.4 Why Removal Attempts Failed

### The Core Challenges

```
┌─────────────────────────────────────────────────────────────────┐
│            Why GIL Removal Is Hard                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Reference Counting                                           │
│     • Every assignment, every function call                     │
│     • Millions of refcount operations per second                 │
│     • Atomic operations are expensive                            │
│                                                                  │
│  2. C Extension Ecosystem                                        │
│     • Thousands of extensions assume GIL                        │
│     • NumPy, pandas, scikit-learn, PIL, etc.                   │
│     • Would all need auditing/rewriting                         │
│                                                                  │
│  3. Internal Data Structures                                     │
│     • dict, list, set assume single-threaded access             │
│     • Making them thread-safe adds overhead                     │
│                                                                  │
│  4. Global State                                                 │
│     • Module imports                                             │
│     • sys.modules                                                │
│     • Exception state                                            │
│                                                                  │
│  5. The 80/20 Rule                                               │
│     • Most Python code is single-threaded                       │
│     • Slowing everyone down for multi-threaded benefit?        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 30.5 Lessons Learned

### What We Learned From Failed Attempts

```python
# Lesson 1: Fine-grained locking has high overhead
# Every lock acquisition/release costs ~100 CPU cycles
# Python does millions of operations per second
# Overhead: 100 cycles × 10M ops = 1 billion cycles/second

# Lesson 2: Reference counting is pervasive
# Simple code:
x = y  # Incref y, potentially decref old x
# With per-object locks: 2-4 lock operations

# Lesson 3: C extension compatibility is crucial
# Breaking NumPy = breaking data science
# Breaking PIL = breaking web apps
# Etc.

# Lesson 4: Single-threaded performance is paramount
# 90%+ of Python code is single-threaded
# 30% slowdown affects EVERYONE
# Multi-threaded speedup helps FEW
```

### Evolution of Thinking

```
1999: "Remove the GIL!"
      Result: Too slow single-threaded

2010: "Make the GIL fairer"
      Result: Python 3.2's new GIL (success!)

2016: "Remove the GIL carefully"
      Result: Still too slow, too many bugs

2020: "What if we could have both?"
      Result: PEP 703 (Sam Gross's approach)

2023: "Gradual transition with build flag"
      Result: Python 3.13 experimental free-threaded mode
```

## 30.6 The Path Forward (PEP 703)

### Sam Gross's Breakthrough

```
┌─────────────────────────────────────────────────────────────────┐
│                PEP 703 Key Innovations                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Biased Reference Counting                                    │
│     • Each object has an "owning" thread                        │
│     • That thread's refcount ops are fast (no atomics)          │
│     • Other threads use deferred counting                       │
│     • Result: ~90% of ops are fast path                         │
│                                                                  │
│  2. Immortal Objects                                             │
│     • Common objects (None, True, False, small ints)            │
│     • Never need refcount changes                               │
│     • Eliminates contention on hot objects                      │
│                                                                  │
│  3. Deferred Reference Counting                                  │
│     • Cross-thread decrefs are queued                           │
│     • Processed in batches by owning thread                     │
│     • Avoids atomic operations on every decref                  │
│                                                                  │
│  4. Per-Object Locks (Minimal)                                   │
│     • Only for truly shared, mutable objects                    │
│     • Most objects never need locking                           │
│                                                                  │
│  5. Mimalloc Integration                                         │
│     • Thread-local memory allocation                            │
│     • Reduces allocator contention                              │
│                                                                  │
│  Performance:                                                    │
│  • Single-threaded: ~5-10% slower (acceptable!)                 │
│  • Multi-threaded: Scales with cores                            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Python 3.13+ Timeline

```
Python 3.13 (2024):
├── Experimental free-threaded build (--disable-gil)
├── Opt-in, not default
├── C extensions need updates (Py_mod_gil)
└── Performance being optimized

Python 3.14+ (2025+):
├── Continued optimization
├── More C extensions updated
└── Broader testing

Future (TBD):
├── Free-threaded may become default
├── GIL build may be deprecated
└── Gradual, careful transition
```

## Historical Timeline Summary

```
┌─────────────────────────────────────────────────────────────────┐
│                  GIL Timeline                                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1992 │ Python 1.0 - No threading                               │
│  1997 │ Python 1.5 - GIL introduced                             │
│  1999 │ Greg Stein - Free-threading attempt (failed)            │
│  2008 │ Python 3.0 - GIL unchanged                              │
│  2010 │ Python 3.2 - New GIL (time-based)                       │
│  2016 │ Gilectomy - Another removal attempt (failed)            │
│  2020 │ Sam Gross - nogil fork shows promise                     │
│  2021 │ PEP 703 - Making CPython Free-Threaded                  │
│  2023 │ PEP 703 accepted for Python 3.13                        │
│  2024 │ Python 3.13 - Experimental free-threaded build          │
│                                                                  │
│  ~30 years from GIL introduction to viable removal path         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Summary

- **GIL introduced** in 1997 for simplicity and correctness
- **Early removal attempts** (1999) failed due to performance
- **Gilectomy** (2016) showed it's possible but not practical
- **Key insight**: Must preserve single-threaded performance
- **PEP 703** brings breakthrough with biased reference counting
- **Python 3.13+** offers experimental free-threaded mode
- **Gradual transition** preserves ecosystem compatibility

## Practice Exercises

1. Research Greg Stein's free-threading patch details
2. Watch Larry Hastings' PyCon talks on Gilectomy
3. Read PEP 703 for technical details
4. Try Python 3.13's free-threaded build

---

[← Previous: GIL Performance Impact](chapter-29-gil-performance.md) | [Next: Multiprocessing →](../part-07-concurrency/chapter-31-multiprocessing.md)

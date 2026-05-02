# Appendix A: GIL Evolution Timeline

## Historical Timeline

### 1991-1994: Origins
- **1991**: Python 0.9.0 released by Guido van Rossum
- **1994**: Python 1.0 released with basic threading support
- GIL introduced to simplify memory management with reference counting

### 1999: First Removal Attempt
- **Greg Stein's Free-Threading Patch**
  - Replaced GIL with fine-grained locks
  - Result: 40-50% slower for single-threaded code
  - Rejected due to performance impact
  - Demonstrated the deep integration of GIL in CPython

### 2000-2010: Threading Improvements
```
┌─────────────────────────────────────────────────────────────┐
│ Python 2.x Era - Incremental GIL Improvements               │
├─────────────────────────────────────────────────────────────┤
│ 2000: Python 2.0                                            │
│   - Garbage collector for cycles                            │
│   - Better threading stability                              │
│                                                             │
│ 2001: Python 2.2                                            │
│   - New-style classes                                       │
│   - Iterators and generators                                │
│                                                             │
│ 2008: Python 2.6/3.0                                        │
│   - multiprocessing module introduced                       │
│   - Official workaround for GIL limitations                 │
└─────────────────────────────────────────────────────────────┘
```

### 2009: New GIL (Python 3.2)
- **Antoine Pitrou's New GIL Implementation**
  - Replaced tick-based switching with time-based (5ms default)
  - Introduced `sys.setswitchinterval()`
  - Better fairness between threads
  - Improved I/O-bound performance
  - PEP: Implementation detail (no PEP number)

### 2015-2017: Gilectomy Project
- **Larry Hastings' Attempt to Remove GIL**
  - Major effort to remove GIL from CPython
  - Challenges encountered:
    - Reference counting atomicity
    - C extension compatibility
    - Single-threaded performance regression
  - Project eventually abandoned
  - Key learning: Need fundamentally different approach

### 2020-2021: Subinterpreter Progress
- **PEP 554**: Multiple Interpreters in the Stdlib
- **PEP 684**: Per-Interpreter GIL
- Work toward isolating interpreters began

### 2022: Python 3.12
```
┌─────────────────────────────────────────────────────────────┐
│ Python 3.12 - Per-Interpreter GIL                           │
├─────────────────────────────────────────────────────────────┤
│ • Each subinterpreter can have its own GIL                  │
│ • True parallelism between interpreters                     │
│ • Limited data sharing between interpreters                 │
│ • Foundation for future improvements                        │
│                                                             │
│ Limitations:                                                │
│ • Not exposed in standard library                           │
│ • C extensions need updates for compatibility               │
│ • Communication overhead between interpreters               │
└─────────────────────────────────────────────────────────────┘
```

### 2023-2024: PEP 703 - Free-Threaded Python

**Key Innovations:**

| Feature | Description |
|---------|-------------|
| Biased Reference Counting | Thread-local ref counts for common case |
| Immortal Objects | Frequently used objects never deallocated |
| Per-Object Locks | Fine-grained locking for mutable objects |
| Deferred Reference Counting | Reduces atomic operations |
| Mimalloc Integration | Thread-safe memory allocator |

**Timeline:**
- **October 2023**: PEP 703 accepted
- **October 2024**: Python 3.13 released with experimental free-threading
- Build-time option: `--disable-gil`

### 2024-2025: Python 3.13
```
┌─────────────────────────────────────────────────────────────┐
│ Python 3.13 - Experimental Free-Threading                   │
├─────────────────────────────────────────────────────────────┤
│ Status: Experimental (opt-in)                               │
│                                                             │
│ Enable with: python3.13t (separate build)                   │
│              or: --disable-gil at build time                │
│                                                             │
│ Performance:                                                │
│ • ~10-15% overhead on single-threaded code                  │
│ • Near-linear scaling for CPU-bound parallel workloads      │
│                                                             │
│ Compatibility:                                              │
│ • Most pure Python code works                               │
│ • C extensions need updates for thread safety               │
│ • Some packages not yet compatible                          │
└─────────────────────────────────────────────────────────────┘
```

### 2025+: Future Plans
- **Python 3.14**: Improved free-threading support
- **Python 3.15**: Potential default enabling
- Long-term: Full removal of GIL build option

## GIL Removal Approaches Comparison

| Approach | Year | Outcome | Single-Thread Impact |
|----------|------|---------|---------------------|
| Greg Stein's Patch | 1999 | Rejected | -40% to -50% |
| Gilectomy | 2015-2017 | Abandoned | -30% estimated |
| Per-Interpreter GIL | 2022 | Shipped (3.12) | Minimal |
| Free-Threading (PEP 703) | 2023-2024 | Experimental (3.13) | -10% to -15% |

## Key Technical Decisions

### Why Reference Counting Made GIL Hard to Remove

```
Standard Reference Counting:
┌─────────────────────────────────────────┐
│ Thread 1: obj->refcount++               │
│ Thread 2: obj->refcount++               │
│                                         │
│ Without GIL, these can race:            │
│ - Read refcount (both see 1)            │
│ - Increment (both compute 2)            │
│ - Write (both write 2, but should be 3) │
└─────────────────────────────────────────┘

Solutions in PEP 703:
┌─────────────────────────────────────────┐
│ 1. Biased ref counting (local fast path)│
│ 2. Atomic operations (when needed)      │
│ 3. Deferred counting (reduce atomics)   │
│ 4. Immortal objects (skip counting)     │
└─────────────────────────────────────────┘
```

### C Extension Compatibility Strategy

**Old (GIL-Protected):**
```c
// Assumed single-threaded access
PyObject *result = PyDict_GetItem(dict, key);
// Use result...
```

**New (Thread-Safe):**
```c
// Must handle concurrent access
PyObject *result = PyDict_GetItem(dict, key);
Py_XINCREF(result);  // Protect before GIL release
// Use result...
Py_XDECREF(result);
```

## Related PEPs

| PEP | Title | Status |
|-----|-------|--------|
| PEP 554 | Multiple Interpreters in the Stdlib | Accepted |
| PEP 684 | A Per-Interpreter GIL | Accepted |
| PEP 703 | Making the GIL Optional | Accepted |
| PEP 734 | Multiple Interpreters in the Stdlib | Draft |

## Further Reading

- [PEP 703 Full Text](https://peps.python.org/pep-0703/)
- [Python 3.13 Release Notes](https://docs.python.org/3.13/whatsnew/3.13.html)
- [Sam Gross's nogil Fork](https://github.com/colesbury/nogil)
- [Larry Hastings - Gilectomy Talk](https://www.youtube.com/watch?v=P3AyI_u66Bw)
- [Antoine Pitrou - New GIL](https://mail.python.org/pipermail/python-dev/2009-October/093321.html)

---

[Back to Main Index →](../README.md)

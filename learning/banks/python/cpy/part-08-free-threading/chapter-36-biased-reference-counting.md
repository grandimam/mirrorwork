# Chapter 36: Biased Reference Counting

## 36.1 The Reference Counting Problem

Traditional reference counting requires atomic operations for thread safety:

```
┌─────────────────────────────────────────────────────────────────┐
│              Reference Counting Challenges                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Traditional (with GIL):                                         │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Py_INCREF(obj):                                        │    │
│  │      obj->ob_refcnt++    ← Simple, GIL protects        │    │
│  │                                                          │    │
│  │  Cost: ~1 CPU cycle                                     │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Naive Thread-Safe:                                              │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Py_INCREF(obj):                                        │    │
│  │      atomic_fetch_add(&obj->ob_refcnt, 1)              │    │
│  │                                                          │    │
│  │  Cost: ~100 CPU cycles (cache line bouncing!)          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Problem: Python does MILLIONS of refcount ops per second       │
│  100x overhead would make Python unusable                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 36.2 Biased Reference Counting Concept

Each object has an "owning" thread that can do fast refcount operations:

```
┌─────────────────────────────────────────────────────────────────┐
│              Biased Reference Counting                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  PyObject:                                                       │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  ob_refcnt_local   (uint32_t)  ← Owning thread only    │    │
│  │  ob_refcnt_shared  (uint32_t)  ← Other threads (atomic)│    │
│  │  ob_tid            (uintptr_t) ← Owner thread ID       │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Thread 1 (owner):                                               │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Py_INCREF:                                              │    │
│  │      if (current_tid == obj->ob_tid)                    │    │
│  │          obj->ob_refcnt_local++  ← FAST (no atomic)    │    │
│  │      else                                                │    │
│  │          ... use shared count ...                       │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Thread 2 (non-owner):                                           │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Py_INCREF:                                              │    │
│  │      if (current_tid == obj->ob_tid)  // False         │    │
│  │          ...                                             │    │
│  │      else                                                │    │
│  │          atomic_add(&obj->ob_refcnt_shared, 1) ← Slow  │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ~90% of operations are by owning thread = FAST PATH            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 36.3 Implementation Details

### Object Header Structure

```c
// Simplified from CPython 3.13+ free-threaded
typedef struct _object {
    // Biased reference counting fields
    union {
        Py_ssize_t ob_refcnt;  // Combined view
        struct {
            uint32_t ob_refcnt_local;   // Thread-local count
            uint32_t ob_refcnt_shared;  // Shared count (atomic)
        };
    };
    uintptr_t ob_tid;  // Owning thread ID
    PyTypeObject *ob_type;
} PyObject;
```

### Fast Path (Owning Thread)

```c
// When current thread is the owner
static inline void _Py_INCREF_FAST(PyObject *op) {
    uintptr_t current_tid = _Py_ThreadId();

    if (op->ob_tid == current_tid) {
        // Fast path: simple increment, no atomic
        op->ob_refcnt_local++;
    } else {
        // Slow path: atomic increment
        _Py_INCREF_SHARED(op);
    }
}

static inline void _Py_DECREF_FAST(PyObject *op) {
    uintptr_t current_tid = _Py_ThreadId();

    if (op->ob_tid == current_tid) {
        // Fast path: simple decrement
        if (--op->ob_refcnt_local == 0) {
            // Check shared count too
            if (op->ob_refcnt_shared == 0) {
                _Py_Dealloc(op);
            }
        }
    } else {
        // Slow path: deferred decrement
        _Py_DECREF_SHARED(op);
    }
}
```

### Slow Path (Other Threads)

```c
// Shared (atomic) reference count operations
void _Py_INCREF_SHARED(PyObject *op) {
    // Atomic increment of shared count
    _Py_atomic_add_uint32(&op->ob_refcnt_shared, 1);
}

void _Py_DECREF_SHARED(PyObject *op) {
    // Atomic decrement of shared count
    uint32_t old = _Py_atomic_add_uint32(&op->ob_refcnt_shared, -1);

    if (old == 1) {
        // Shared count reached zero
        // Queue for deferred processing by owner
        _Py_QueueDecref(op);
    }
}
```

## 36.4 Thread Ownership

### How Ownership is Determined

```c
// Object creation - current thread becomes owner
PyObject* _PyObject_New(PyTypeObject *type) {
    PyObject *op = PyObject_Malloc(type->tp_basicsize);
    if (op == NULL)
        return PyErr_NoMemory();

    // Set owning thread
    op->ob_tid = _Py_ThreadId();
    op->ob_refcnt_local = 1;
    op->ob_refcnt_shared = 0;
    op->ob_type = type;

    return op;
}
```

### Ownership Transfer

```c
// Transfer ownership to current thread
void _Py_SetOwner(PyObject *op) {
    // Merge shared count into local count
    uint32_t shared = _Py_atomic_exchange_uint32(
        &op->ob_refcnt_shared, 0
    );
    op->ob_refcnt_local += shared;

    // Set new owner
    op->ob_tid = _Py_ThreadId();
}
```

## 36.5 Why This Works

### Locality of Reference

```python
# Most objects are used primarily by one thread

def process_data(data):
    # All these objects are local to this thread
    result = []               # Created here, used here
    for item in data:
        processed = item * 2  # Temporary, local
        result.append(processed)
    return result  # Only returned object crosses threads

# Statistics from real programs:
# ~90-95% of refcount operations are by the creating thread
# Biased reference counting optimizes the common case
```

### Performance Comparison

```
┌─────────────────────────────────────────────────────────────────┐
│              Performance Comparison                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Approach                    │ Py_INCREF Cost │ Py_DECREF Cost │
│  ───────────────────────────────────────────────────────────────│
│  With GIL (current)          │ ~1 cycle       │ ~1-5 cycles    │
│  Naive atomic                │ ~100 cycles    │ ~100 cycles    │
│  Biased (owner thread)       │ ~3-5 cycles    │ ~3-5 cycles    │
│  Biased (other thread)       │ ~50-100 cycles │ ~50-100 cycles │
│                                                                  │
│  Biased average (90% owner): │ ~8 cycles      │ ~13 cycles     │
│                                                                  │
│  Result: ~5-10% single-threaded overhead (acceptable!)          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 36.6 Thread ID Optimization

### Fast Thread ID Access

```c
// Thread ID is stored in a thread-local variable
// Accessing it is very fast (single memory read)

#if defined(__GNUC__) && (defined(__x86_64__) || defined(__i386__))
// x86: Use segment register for thread-local storage
static inline uintptr_t _Py_ThreadId(void) {
    uintptr_t tid;
    #ifdef __x86_64__
    __asm__("movq %%fs:0, %0" : "=r"(tid));
    #else
    __asm__("movl %%gs:0, %0" : "=r"(tid));
    #endif
    return tid;
}
#else
// Fallback: pthread_self() or similar
static inline uintptr_t _Py_ThreadId(void) {
    return (uintptr_t)pthread_self();
}
#endif
```

### Comparison Optimization

```c
// The ownership check is very cheap
static inline int _Py_IsOwner(PyObject *op) {
    // Single comparison after fast thread ID lookup
    return op->ob_tid == _Py_ThreadId();
}
```

## 36.7 Handling Edge Cases

### Object Sharing

```c
// When an object is shared with another thread
void _Py_ShareObject(PyObject *op, PyThreadState *target) {
    // Increment shared count for the transfer
    _Py_atomic_add_uint32(&op->ob_refcnt_shared, 1);

    // Receiver will use shared count until/unless ownership transfers
}
```

### Thread Termination

```c
// When a thread exits, its owned objects need handling
void _PyThread_Cleanup(PyThreadState *tstate) {
    // Objects owned by this thread:
    // 1. Transfer ownership to main thread, or
    // 2. Queue for garbage collection if no references

    // This is handled by the thread-local heap cleanup
    _PyMem_FreeThreadHeap(tstate);
}
```

### Contended Objects

```c
// Some objects are heavily shared (module dicts, etc.)
// These can have ownership transferred frequently

void _Py_MaybeTransferOwnership(PyObject *op) {
    // Heuristic: If shared count is much higher than local count,
    // consider transferring ownership

    if (op->ob_refcnt_shared > op->ob_refcnt_local * 2) {
        // Transfer to most active thread (if determinable)
        // Or mark as "ownerless" (always use shared count)
    }
}
```

## 36.8 Memory Layout Considerations

### Cache Line Optimization

```c
// Object header layout is optimized for cache performance

typedef struct _object {
    // Hot fields (frequently accessed) together
    Py_ssize_t ob_refcnt;      // 8 bytes
    PyTypeObject *ob_type;      // 8 bytes

    // Thread ownership (accessed on refcount ops)
    uintptr_t ob_tid;           // 8 bytes

    // Total: 24 bytes - fits in partial cache line
    // Object data follows
} PyObject;
```

### False Sharing Avoidance

```
┌─────────────────────────────────────────────────────────────────┐
│              Cache Line Considerations                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Cache line: 64 bytes                                            │
│                                                                  │
│  Bad layout (false sharing):                                     │
│  ┌────────────────────────────────────────────────────────┐     │
│  │ obj1.refcnt │ obj2.refcnt │ obj3.refcnt │ ...         │     │
│  └────────────────────────────────────────────────────────┘     │
│  All objects in same cache line → contention                    │
│                                                                  │
│  Good layout (separate objects):                                 │
│  ┌────────────────────────────────────────────────────────┐     │
│  │ obj1 header │ obj1 data   │ padding...                │     │
│  └────────────────────────────────────────────────────────┘     │
│  ┌────────────────────────────────────────────────────────┐     │
│  │ obj2 header │ obj2 data   │ padding...                │     │
│  └────────────────────────────────────────────────────────┘     │
│  Objects in different cache lines → no contention               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 36.9 Debugging and Profiling

### Tracking Ownership Changes

```c
#ifdef Py_DEBUG
// Debug mode: Track ownership statistics
static _Py_atomic_int fast_incref_count = 0;
static _Py_atomic_int slow_incref_count = 0;

void _Py_INCREF_DEBUG(PyObject *op) {
    if (_Py_IsOwner(op)) {
        _Py_atomic_add_int(&fast_incref_count, 1);
        op->ob_refcnt_local++;
    } else {
        _Py_atomic_add_int(&slow_incref_count, 1);
        _Py_INCREF_SHARED(op);
    }
}

void _Py_PrintRefcountStats(void) {
    int fast = _Py_atomic_load_int(&fast_incref_count);
    int slow = _Py_atomic_load_int(&slow_incref_count);
    printf("Fast path: %d (%.1f%%)\n", fast, 100.0 * fast / (fast + slow));
    printf("Slow path: %d (%.1f%%)\n", slow, 100.0 * slow / (fast + slow));
}
#endif
```

### Python-Level Inspection

```python
import sys

def check_refcount_info(obj):
    """Get refcount information (debug builds only)."""
    # Basic refcount
    print(f"Reference count: {sys.getrefcount(obj) - 1}")

    # In debug builds, may have more info
    if hasattr(sys, '_getobjectinfo'):
        info = sys._getobjectinfo(obj)
        print(f"Local count: {info.get('local_refcnt', 'N/A')}")
        print(f"Shared count: {info.get('shared_refcnt', 'N/A')}")
        print(f"Owner thread: {info.get('owner_tid', 'N/A')}")
```

## Summary

- **Biased reference counting** optimizes for thread-local access
- **Owning thread** does fast non-atomic operations
- **Other threads** use slower atomic shared count
- **~90% of operations** hit the fast path
- **Result**: Only 5-10% overhead vs traditional refcounting
- **Thread ID access** is optimized with platform-specific code
- **Ownership can transfer** when access patterns change

## Practice Exercises

1. Implement a simple biased reference counting scheme
2. Measure the fast path vs slow path ratio in a threaded program
3. Analyze cache line effects on refcount operations
4. Profile ownership transfer frequency in real applications

---

[← Previous: Free-Threading Overview](chapter-35-free-threading-overview.md) | [Next: Immortal Objects →](chapter-37-immortal-objects.md)

# Chapter 39: Deferred Reference Counting

## 39.1 The Cross-Thread Decref Problem

When a non-owning thread decrements an object's reference count:

```
┌─────────────────────────────────────────────────────────────────┐
│              Cross-Thread Decref Problem                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Thread 1 (Owner):                                               │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  obj = create_object()  # refcnt = 1, owned by T1     │     │
│  │  share(obj, thread2)    # T2 now has reference        │     │
│  └────────────────────────────────────────────────────────┘     │
│                                                                  │
│  Thread 2 (Non-owner):                                           │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  use(obj)                                              │     │
│  │  del obj  # DECREF - what happens?                    │     │
│  │                                                        │     │
│  │  If refcnt == 0:                                       │     │
│  │    - T2 would deallocate obj                          │     │
│  │    - But T2 doesn't "own" the object                  │     │
│  │    - Memory allocated by T1's allocator               │     │
│  │    - Thread-local heaps don't mix!                    │     │
│  └────────────────────────────────────────────────────────┘     │
│                                                                  │
│  Solution: Deferred reference counting                           │
│  - T2 queues the decref                                         │
│  - T1 processes the queue and deallocates if needed             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 39.2 How Deferred Reference Counting Works

### The Mechanism

```c
// Each thread has a queue of deferred decrefs
typedef struct {
    PyObject **items;
    size_t size;
    size_t capacity;
    PyMutex mutex;
} _PyDecrefQueue;

// Thread state includes decref queue
typedef struct _ts {
    // ... other fields ...
    _PyDecrefQueue decref_queue;
} PyThreadState;
```

### Queueing a Decref

```c
// Called by non-owning threads
void _Py_DecrefShared(PyObject *op) {
    // Decrement shared count atomically
    uint32_t old = _Py_atomic_fetch_sub(&op->ob_refcnt_shared, 1);

    if (old == 1) {
        // Shared count reached zero
        // Queue for owner thread to process
        _Py_QueueDecref(op);
    }
}

void _Py_QueueDecref(PyObject *op) {
    // Find owner thread
    PyThreadState *owner = _Py_GetThreadState(op->ob_tid);

    if (owner == NULL) {
        // Owner thread has exited
        // Deallocate directly (or use orphan queue)
        _Py_Dealloc(op);
        return;
    }

    // Add to owner's decref queue
    _PyDecrefQueue *queue = &owner->decref_queue;

    PyMutex_Lock(&queue->mutex);
    if (queue->size >= queue->capacity) {
        // Grow queue
        _Py_GrowDecrefQueue(queue);
    }
    queue->items[queue->size++] = op;
    PyMutex_Unlock(&queue->mutex);
}
```

### Processing the Queue

```c
// Called periodically by the owning thread
void _Py_ProcessDecrefQueue(PyThreadState *tstate) {
    _PyDecrefQueue *queue = &tstate->decref_queue;

    PyMutex_Lock(&queue->mutex);

    // Swap out the queue items
    PyObject **items = queue->items;
    size_t size = queue->size;
    queue->items = NULL;
    queue->size = 0;
    queue->capacity = 0;

    PyMutex_Unlock(&queue->mutex);

    // Process items
    for (size_t i = 0; i < size; i++) {
        PyObject *op = items[i];

        // Check if object can be deallocated
        if (op->ob_refcnt_local == 0 && op->ob_refcnt_shared == 0) {
            _Py_Dealloc(op);
        }
        // Otherwise, some reference was added in the meantime
    }

    PyMem_Free(items);
}
```

## 39.3 When Deferred Decrefs Are Processed

### Processing Points

```c
// Deferred decrefs are processed at safe points:

// 1. Eval loop check interval
PyObject* _PyEval_EvalFrame(PyThreadState *tstate, PyFrameObject *f) {
    // ... bytecode execution ...

    if (--tstate->eval_breaker_check == 0) {
        tstate->eval_breaker_check = CHECK_INTERVAL;

        // Process deferred decrefs
        if (tstate->decref_queue.size > 0) {
            _Py_ProcessDecrefQueue(tstate);
        }

        // ... other periodic checks ...
    }

    // ... continue execution ...
}

// 2. Before blocking operations
void _Py_BeforeBlock(PyThreadState *tstate) {
    // Process pending work before blocking
    _Py_ProcessDecrefQueue(tstate);
}

// 3. At garbage collection
void _Py_GC_Collect(void) {
    // Process all threads' deferred decrefs first
    _Py_ProcessAllDecrefQueues();

    // Then do garbage collection
    // ...
}
```

### Queue Size Limits

```c
// If queue gets too large, process immediately
void _Py_DecrefShared(PyObject *op) {
    uint32_t old = _Py_atomic_fetch_sub(&op->ob_refcnt_shared, 1);

    if (old == 1) {
        PyThreadState *owner = _Py_GetThreadState(op->ob_tid);

        if (owner && owner->decref_queue.size > MAX_DEFERRED_DECREFS) {
            // Queue is full, wait for owner to process
            // Or signal owner thread to process
            _Py_SignalDecrefQueue(owner);
            _Py_WaitForDecrefProcessing(owner);
        }

        _Py_QueueDecref(op);
    }
}
```

## 39.4 Memory Ordering

### Ensuring Correctness

```c
// Memory barriers ensure visibility

void _Py_DecrefShared(PyObject *op) {
    // Release semantics: All prior writes visible before decrement
    uint32_t old = _Py_atomic_fetch_sub_release(&op->ob_refcnt_shared, 1);

    if (old == 1) {
        // Acquire semantics: See all writes before queuing
        _Py_atomic_thread_fence_acquire();
        _Py_QueueDecref(op);
    }
}

void _Py_ProcessDecrefQueue(PyThreadState *tstate) {
    // ... get items from queue ...

    // Acquire fence before reading object state
    _Py_atomic_thread_fence_acquire();

    for (size_t i = 0; i < size; i++) {
        PyObject *op = items[i];

        // Read refcounts with acquire semantics
        uint32_t local = _Py_atomic_load_acquire(&op->ob_refcnt_local);
        uint32_t shared = _Py_atomic_load_acquire(&op->ob_refcnt_shared);

        if (local == 0 && shared == 0) {
            _Py_Dealloc(op);
        }
    }
}
```

## 39.5 Handling Thread Exit

### When Owner Thread Exits

```c
// Thread cleanup
void _PyThread_Exit(PyThreadState *tstate) {
    // Process remaining deferred decrefs
    _Py_ProcessDecrefQueue(tstate);

    // Transfer ownership of still-live objects
    _Py_TransferOwnership(tstate);

    // Handle orphaned objects
    _Py_HandleOrphanedObjects(tstate);

    // ... thread cleanup ...
}

void _Py_TransferOwnership(PyThreadState *tstate) {
    // Objects owned by exiting thread need new owners

    // Option 1: Transfer to main thread
    PyThreadState *main = _PyRuntime.main_thread;

    // Option 2: Use "ownerless" mode (always shared counts)

    // Option 3: Mark for garbage collection
}

void _Py_HandleOrphanedObjects(PyThreadState *tstate) {
    // Objects with pending decrefs but no owner
    // Need special handling

    _PyDecrefQueue *queue = &tstate->decref_queue;

    for (size_t i = 0; i < queue->size; i++) {
        PyObject *op = queue->items[i];

        // Try to deallocate if no references
        if (op->ob_refcnt_local == 0 && op->ob_refcnt_shared == 0) {
            _Py_DeallocOrphaned(op);
        } else {
            // Transfer to orphan queue for GC
            _Py_AddToOrphanQueue(op);
        }
    }
}
```

## 39.6 Performance Implications

### Latency Considerations

```
┌─────────────────────────────────────────────────────────────────┐
│              Deferred Decref Latency                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Immediate Decref (with GIL):                                    │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  del obj  →  refcnt--  →  if 0: dealloc               │     │
│  │  Latency: ~1-10 microseconds                          │     │
│  └────────────────────────────────────────────────────────┘     │
│                                                                  │
│  Deferred Decref (free-threaded):                               │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  del obj  →  queue  →  ...later...  →  dealloc        │     │
│  │  Latency: ~10-1000 microseconds (depends on interval) │     │
│  └────────────────────────────────────────────────────────┘     │
│                                                                  │
│  Trade-off: Higher latency, but better throughput               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Memory Overhead

```c
// Queue memory usage

// Each queued decref: 8 bytes (pointer)
// Typical queue size: 1000-10000 items
// Memory per thread: 8-80 KB

// Compared to:
// - Thread stack: 1-8 MB
// - Python objects: hundreds of MB

// Conclusion: Minimal overhead
```

## 39.7 Interaction with Garbage Collection

### Ensuring Consistency

```c
// Before garbage collection, all deferred decrefs must be processed

void _Py_GC_Collect(int generation) {
    // Step 1: Stop the world (optional in some designs)
    _Py_StopTheWorld();

    // Step 2: Process all deferred decrefs
    for (PyThreadState *ts = _PyRuntime.threads; ts != NULL; ts = ts->next) {
        _Py_ProcessDecrefQueue(ts);
    }

    // Step 3: Run cycle detection
    gc_collect_main(generation);

    // Step 4: Resume threads
    _Py_ResumeTheWorld();
}
```

### Cycle Detection with Deferred Decrefs

```c
// Cycles involving objects with deferred decrefs

// Object A (owned by T1) references B (owned by T2)
// Object B references A
// Both are dropped by their non-owning threads

// Without processing queues first:
// - A's decref queued on T2
// - B's decref queued on T1
// - Neither deallocated yet
// - GC might not see the cycle correctly

// Solution: Process queues before GC

void _Py_GC_Collect(int generation) {
    // Ensure all reference counts are up-to-date
    _Py_ProcessAllDecrefQueues();

    // Now GC has accurate refcount view
    // ...
}
```

## 39.8 Debugging Deferred Decrefs

### Queue Inspection

```c
#ifdef Py_DEBUG
void _Py_DebugDecrefQueue(PyThreadState *tstate) {
    _PyDecrefQueue *queue = &tstate->decref_queue;

    printf("Thread %p decref queue:\n", tstate);
    printf("  Size: %zu\n", queue->size);
    printf("  Capacity: %zu\n", queue->capacity);

    for (size_t i = 0; i < queue->size; i++) {
        PyObject *op = queue->items[i];
        printf("  [%zu] %p (%s) local=%u shared=%u\n",
               i, op, Py_TYPE(op)->tp_name,
               op->ob_refcnt_local, op->ob_refcnt_shared);
    }
}
#endif
```

### Python-Level Inspection

```python
import sys

def get_deferred_decref_stats():
    """Get deferred decref statistics (if available)."""
    if hasattr(sys, '_get_decref_queue_stats'):
        stats = sys._get_decref_queue_stats()
        print(f"Queue size: {stats['size']}")
        print(f"Total queued: {stats['total_queued']}")
        print(f"Total processed: {stats['total_processed']}")
        print(f"Avg latency: {stats['avg_latency_us']:.1f} us")
    else:
        print("Deferred decref stats not available")

# Force queue processing (debug builds)
if hasattr(sys, '_process_decref_queue'):
    sys._process_decref_queue()
```

## 39.9 Alternative Approaches

### Epoch-Based Reclamation

```c
// Alternative: Epoch-based memory reclamation
// Used in some lock-free data structures

typedef struct {
    _Atomic uint64_t epoch;
    _Atomic uint64_t reservations[MAX_THREADS];
} EpochManager;

void retire_object(PyObject *op) {
    uint64_t current_epoch = _Py_atomic_load(&epoch_mgr.epoch);

    // Add to retirement list with epoch
    add_to_retire_list(op, current_epoch);

    // Object can be freed when all threads have
    // advanced past this epoch
}

void try_reclaim(void) {
    uint64_t min_epoch = UINT64_MAX;

    // Find minimum epoch among all threads
    for (int i = 0; i < num_threads; i++) {
        uint64_t e = _Py_atomic_load(&epoch_mgr.reservations[i]);
        if (e < min_epoch) min_epoch = e;
    }

    // Free objects retired before min_epoch
    free_retired_before(min_epoch);
}
```

### Hazard Pointers

```c
// Alternative: Hazard pointers
// More fine-grained than epochs

typedef struct {
    _Atomic(PyObject*) hazard[MAX_THREADS];
} HazardPointers;

PyObject* safe_read(PyObject **location) {
    PyObject *obj;

    do {
        obj = _Py_atomic_load(location);
        // Publish hazard
        _Py_atomic_store(&hazard_ptrs.hazard[my_id], obj);
        // Memory fence
        _Py_atomic_thread_fence_seq_cst();
        // Verify still valid
    } while (_Py_atomic_load(location) != obj);

    return obj;
}

void retire_object(PyObject *op) {
    // Can only free if no hazard pointer references it
    for (int i = 0; i < num_threads; i++) {
        if (_Py_atomic_load(&hazard_ptrs.hazard[i]) == op) {
            // Still in use, defer
            add_to_retire_list(op);
            return;
        }
    }
    // Safe to free
    _Py_Dealloc(op);
}
```

## Summary

- **Deferred reference counting** queues cross-thread decrefs
- **Owner thread processes** the queue at safe points
- **Memory ordering** with barriers ensures correctness
- **Thread exit** transfers ownership or handles orphans
- **GC integration** requires processing queues first
- **Trade-off**: Latency for throughput
- **Alternatives**: Epoch-based reclamation, hazard pointers

## Practice Exercises

1. Implement a simple deferred decref queue
2. Measure queue processing latency in different scenarios
3. Analyze memory usage of deferred decrefs
4. Compare deferred decrefs with epoch-based reclamation

---

[← Previous: Per-Object Locks](chapter-38-per-object-locks.md) | [Next: Mimalloc Integration →](chapter-40-mimalloc-integration.md)

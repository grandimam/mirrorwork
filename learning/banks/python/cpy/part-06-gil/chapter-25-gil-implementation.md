# Chapter 25: GIL Implementation

## 25.1 GIL Data Structures

The GIL is implemented in `Python/ceval_gil.c`:

```c
// Simplified GIL structure
struct _gil_runtime_state {
    // The actual lock (mutex + condition variable)
    unsigned long locked;           // 0 = unlocked, 1 = locked
    unsigned long switch_number;    // For fairness tracking
    _Py_atomic_int last_holder;     // Thread that last held GIL

    // Condition variables for waiting
    PyMUTEX_T mutex;
    PyCOND_T cond;

    // Timing for drops
    _PyTime_t switch_interval;      // How often to check for drops
};
```

### GIL Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                      GIL Structure                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  _gil_runtime_state                                              │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  locked: 1 (held by Thread A)                            │    │
│  │  switch_number: 1234                                     │    │
│  │  last_holder: Thread A's ID                              │    │
│  │  switch_interval: 5ms (default)                         │    │
│  │                                                          │    │
│  │  mutex: protects condition variable                      │    │
│  │  cond: threads wait here for GIL                        │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Waiting threads:                                                │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐                         │
│  │Thread B │  │Thread C │  │Thread D │                         │
│  │ waiting │  │ waiting │  │ waiting │                         │
│  └─────────┘  └─────────┘  └─────────┘                         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 25.2 `_PyRuntimeState` Structure

The runtime state contains the GIL:

```c
// Include/internal/pycore_runtime.h
typedef struct _PyRuntimeState {
    // GIL state
    struct _gil_runtime_state gil;

    // Interpreter state
    struct _ceval_runtime_state ceval;

    // Memory allocators
    struct _Py_mem_runtime_state memory;

    // Other runtime state...
} _PyRuntimeState;
```

### Accessing the GIL

```c
// Get the GIL state
#define _PyRuntimeGILState_GetLock() \
    (&_PyRuntime.gil)

// Check if GIL is locked
int gil_locked = _PyRuntime.gil.locked;
```

## 25.3 `PyThreadState` and Thread Management

Each Python thread has a `PyThreadState`:

```c
// Include/cpython/pystate.h
typedef struct _ts PyThreadState;

struct _ts {
    // Thread identification
    unsigned long thread_id;        // OS thread ID

    // Interpreter this thread belongs to
    PyInterpreterState *interp;

    // Current frame being executed
    _PyInterpreterFrame *current_frame;

    // Exception state
    _PyErr_StackItem *exc_info;

    // GIL state for this thread
    int gilstate_counter;           // Nested GIL acquisitions
    char _is_thread_state_current;  // Is this the current thread?

    // ... more fields ...
};
```

### Thread State Relationship

```
┌─────────────────────────────────────────────────────────────────┐
│                   Thread State Hierarchy                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  _PyRuntimeState (one per process)                              │
│       │                                                          │
│       ├── gil_runtime_state (THE GIL)                           │
│       │                                                          │
│       └── PyInterpreterState (one+ per process)                 │
│                │                                                 │
│                ├── PyThreadState (Thread 1)                     │
│                │       ├── thread_id                            │
│                │       ├── current_frame                        │
│                │       └── exc_info                             │
│                │                                                 │
│                ├── PyThreadState (Thread 2)                     │
│                │       └── ...                                  │
│                │                                                 │
│                └── PyThreadState (Thread N)                     │
│                        └── ...                                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 25.4 GIL Acquisition (`PyGILState_Ensure`)

### High-Level API

```c
// Acquire the GIL (from C extension or embedding)
PyGILState_STATE PyGILState_Ensure(void) {
    // 1. Get or create thread state
    PyThreadState *tstate = _PyThreadState_GET();
    if (tstate == NULL) {
        tstate = PyThreadState_New(interp);
    }

    // 2. Acquire the GIL
    if (!tstate->gilstate_counter) {
        PyEval_AcquireThread(tstate);
    }

    // 3. Increment nesting counter
    tstate->gilstate_counter++;

    return (prev_state);
}
```

### Low-Level Acquisition

```c
// Python/ceval_gil.c - Simplified
static void take_gil(PyThreadState *tstate) {
    _gil_runtime_state *gil = &_PyRuntime.gil;

    // Lock the mutex
    MUTEX_LOCK(gil->mutex);

    // Wait while GIL is locked
    while (gil->locked) {
        // Wait on condition variable with timeout
        COND_TIMED_WAIT(gil->cond, gil->mutex, switch_interval);

        // If still locked after timeout, request drop
        if (gil->locked) {
            SET_GIL_DROP_REQUEST(tstate->interp);
        }
    }

    // Acquire the GIL
    gil->locked = 1;
    gil->last_holder = tstate->thread_id;

    MUTEX_UNLOCK(gil->mutex);
}
```

## 25.5 GIL Release (`PyGILState_Release`)

### High-Level API

```c
void PyGILState_Release(PyGILState_STATE oldstate) {
    PyThreadState *tstate = _PyThreadState_GET();

    // Decrement nesting counter
    tstate->gilstate_counter--;

    if (tstate->gilstate_counter == 0) {
        // Actually release the GIL
        PyEval_ReleaseThread(tstate);

        // Clean up if thread state was created
        if (oldstate == PyGILState_UNLOCKED) {
            PyThreadState_Delete(tstate);
        }
    }
}
```

### Low-Level Release

```c
// Python/ceval_gil.c - Simplified
static void drop_gil(PyThreadState *tstate) {
    _gil_runtime_state *gil = &_PyRuntime.gil;

    MUTEX_LOCK(gil->mutex);

    // Release the GIL
    gil->locked = 0;
    gil->switch_number++;

    // Signal waiting threads
    COND_SIGNAL(gil->cond);

    MUTEX_UNLOCK(gil->mutex);
}
```

## 25.6 Condition Variables and Signaling

### Why Condition Variables?

```
┌─────────────────────────────────────────────────────────────────┐
│                  Condition Variable Usage                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Without condition variable (busy waiting):                      │
│  while (gil->locked) {                                          │
│      // Spin - wastes CPU!                                      │
│  }                                                               │
│                                                                  │
│  With condition variable (efficient waiting):                    │
│  while (gil->locked) {                                          │
│      COND_WAIT(gil->cond, gil->mutex);  // Sleep until signal   │
│  }                                                               │
│                                                                  │
│  Thread holding GIL:                                             │
│  gil->locked = 0;                                                │
│  COND_SIGNAL(gil->cond);  // Wake one waiting thread            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Signaling Flow

```
Thread A (holds GIL)         Thread B (waiting)
        │                           │
        │                    COND_WAIT(cond)
        │                           │ (sleeping)
        │                           │
    drop_gil()                      │
    locked = 0                      │
    COND_SIGNAL ─────────────────▶  │ (wakes up)
        │                           │
        │                    take_gil()
        │                    locked = 1
        │                           │
        ▼                           ▼
   (GIL released)            (GIL acquired)
```

## 25.7 GIL Implementation in `ceval_gil.c`

### Key Functions

```c
// Python/ceval_gil.c

// Initialize the GIL
static void create_gil(struct _gil_runtime_state *gil);

// Destroy the GIL
static void destroy_gil(struct _gil_runtime_state *gil);

// Acquire the GIL
static void take_gil(PyThreadState *tstate);

// Release the GIL
static void drop_gil(PyThreadState *tstate);

// Check if GIL should be released
static inline int
eval_breaker_bit_is_set(PyInterpreterState *interp, uint32_t bit);
```

### The Eval Breaker

```c
// Check in the main eval loop
if (_Py_atomic_load_relaxed(&interp->ceval.eval_breaker)) {
    // Handle:
    // - GIL drop requests from other threads
    // - Pending signals
    // - Async exceptions
    // - Periodic tasks

    if (eval_frame_handle_pending(tstate) < 0) {
        goto error;
    }
}
```

### Eval Breaker Bits

```c
// Bits in eval_breaker
#define _PY_GIL_DROP_REQUEST_BIT    (1 << 0)
#define _PY_SIGNALS_PENDING_BIT     (1 << 1)
#define _PY_CALLS_TO_DO_BIT         (1 << 2)
#define _PY_ASYNC_EXCEPTION_BIT     (1 << 3)
```

## GIL Acquisition Timeline

```
┌─────────────────────────────────────────────────────────────────┐
│                  GIL Acquisition Timeline                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Time ─────────────────────────────────────────────────────▶    │
│                                                                  │
│  Thread A: [==GIL HELD===][release][........wait........][=GIL=]│
│                                                                  │
│  Thread B: [....wait.....][=====GIL HELD=====][release][..wait..]│
│                                                                  │
│  Thread C: [.....wait................][===GIL HELD====][release]│
│                                                                  │
│  Note: Threads take turns holding the GIL                        │
│        Only ONE thread executes Python at a time                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Summary

- GIL state lives in `_PyRuntimeState.gil`
- Each thread has `PyThreadState` with GIL-related fields
- `PyGILState_Ensure()` / `PyGILState_Release()` for C code
- Internal `take_gil()` / `drop_gil()` for actual locking
- **Condition variables** enable efficient waiting
- **Eval breaker** signals GIL drop requests

## Practice Exercises

1. Read `Python/ceval_gil.c` in the CPython source
2. Trace GIL acquisition with `sys.settrace()`
3. Use `threading` module to observe GIL contention
4. Examine `PyThreadState` fields in a debugger

---

[← Previous: GIL Fundamentals](chapter-24-gil-fundamentals.md) | [Next: GIL Scheduling →](chapter-26-gil-scheduling.md)

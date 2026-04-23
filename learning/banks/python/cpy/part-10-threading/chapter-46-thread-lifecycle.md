# Chapter 46: Thread Creation and Lifecycle

## 46.1 Python Thread Architecture

Python threads wrap native OS threads:

```
┌─────────────────────────────────────────────────────────────────┐
│              Python Thread Architecture                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Python Level          C Level              OS Level            │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐    │
│  │   Thread     │     │ PyThreadState│     │  pthread     │    │
│  │   Object     │────>│              │────>│  (or Win32   │    │
│  │              │     │ - frame      │     │   thread)    │    │
│  │ - target     │     │ - thread_id  │     │              │    │
│  │ - args       │     │ - interp     │     │ - stack      │    │
│  │ - name       │     │ - dict       │     │ - TID        │    │
│  └──────────────┘     └──────────────┘     └──────────────┘    │
│                                                                  │
│  threading.Thread wraps PyThreadState wraps OS thread           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 46.2 Creating Threads

### Python Level API

```python
import threading

# Method 1: Pass a target function
def worker(name, delay):
    print(f"Worker {name} starting")
    time.sleep(delay)
    print(f"Worker {name} done")

thread = threading.Thread(
    target=worker,
    args=("A", 1.0),
    name="WorkerThread",
    daemon=False
)
thread.start()

# Method 2: Subclass Thread
class MyThread(threading.Thread):
    def __init__(self, name):
        super().__init__(name=name)
        self.result = None

    def run(self):
        self.result = self.do_work()

    def do_work(self):
        return "completed"

thread = MyThread("CustomThread")
thread.start()
thread.join()
print(thread.result)
```

### What Happens During Creation

```c
// Simplified thread creation in _threadmodule.c

static PyObject *
thread_PyThread_start_new_thread(PyObject *module, PyObject *args)
{
    PyObject *func, *func_args, *keyw = NULL;

    if (!PyArg_UnpackTuple(args, "start_new_thread", 2, 3,
                           &func, &func_args, &keyw))
        return NULL;

    // Create boot structure to pass to new thread
    struct bootstate *boot = PyMem_NEW(struct bootstate, 1);
    boot->func = func;
    boot->args = func_args;
    boot->keyw = keyw;
    boot->interp = PyInterpreterState_Get();

    Py_INCREF(func);
    Py_INCREF(func_args);
    Py_XINCREF(keyw);

    // Create the OS thread
    unsigned long thread_id = PyThread_start_new_thread(
        thread_run,  // Thread entry point
        (void *)boot
    );

    if (thread_id == PYTHREAD_INVALID_THREAD_ID) {
        // Cleanup on failure
        Py_DECREF(func);
        Py_DECREF(func_args);
        Py_XDECREF(keyw);
        PyMem_DEL(boot);
        PyErr_SetString(PyExc_RuntimeError, "can't start new thread");
        return NULL;
    }

    return PyLong_FromUnsignedLong(thread_id);
}
```

## 46.3 PyThreadState

### Structure Definition

```c
// The thread state structure
typedef struct _ts {
    // Thread linkage
    struct _ts *prev;
    struct _ts *next;

    // Interpreter this thread belongs to
    PyInterpreterState *interp;

    // Current frame being executed
    struct _frame *frame;

    // Recursion tracking
    int recursion_depth;
    int recursion_headroom;

    // Tracing/profiling
    int tracing;
    int use_tracing;
    Py_tracefunc c_profilefunc;
    Py_tracefunc c_tracefunc;
    PyObject *c_profileobj;
    PyObject *c_traceobj;

    // Exception state
    PyObject *curexc_type;
    PyObject *curexc_value;
    PyObject *curexc_traceback;

    // Thread-local dictionary
    PyObject *dict;

    // GIL tracking
    int gilstate_counter;

    // Async exception
    PyObject *async_exc;

    // Thread ID
    unsigned long thread_id;

    // ... more fields
} PyThreadState;
```

### Creating Thread State

```c
// Create a new thread state
PyThreadState *
PyThreadState_New(PyInterpreterState *interp)
{
    PyThreadState *tstate = PyMem_RawMalloc(sizeof(PyThreadState));
    if (tstate == NULL) {
        return NULL;
    }

    // Initialize fields
    tstate->interp = interp;
    tstate->frame = NULL;
    tstate->recursion_depth = 0;
    tstate->tracing = 0;
    tstate->use_tracing = 0;

    // Exception state
    tstate->curexc_type = NULL;
    tstate->curexc_value = NULL;
    tstate->curexc_traceback = NULL;

    // Thread-local dict
    tstate->dict = NULL;

    // Get thread ID
    tstate->thread_id = PyThread_get_thread_ident();

    // Link into interpreter's thread list
    HEAD_LOCK(interp);
    tstate->prev = NULL;
    tstate->next = interp->threads.head;
    if (tstate->next)
        tstate->next->prev = tstate;
    interp->threads.head = tstate;
    HEAD_UNLOCK(interp);

    return tstate;
}
```

## 46.4 Thread Bootstrap

### The Thread Entry Point

```c
// Thread entry point (runs in new OS thread)
static void
thread_run(void *boot_raw)
{
    struct bootstate *boot = (struct bootstate *)boot_raw;
    PyThreadState *tstate;
    PyObject *result;

    // Create thread state for this thread
    tstate = PyThreadState_New(boot->interp);
    if (tstate == NULL) {
        PyMem_DEL(boot);
        return;
    }

    // Acquire the GIL
    PyEval_AcquireThread(tstate);

    // Call the Python function
    result = PyObject_Call(boot->func, boot->args, boot->keyw);

    if (result == NULL) {
        // Exception occurred
        if (PyErr_ExceptionMatches(PyExc_SystemExit)) {
            // SystemExit is okay for threads
            PyErr_Clear();
        } else {
            // Print other exceptions
            PyErr_PrintEx(0);
        }
    } else {
        Py_DECREF(result);
    }

    // Cleanup
    Py_DECREF(boot->func);
    Py_DECREF(boot->args);
    Py_XDECREF(boot->keyw);
    PyMem_DEL(boot);

    // Release GIL and destroy thread state
    PyThreadState_Clear(tstate);
    PyThreadState_DeleteCurrent();
}
```

## 46.5 Thread Lifecycle States

```
┌─────────────────────────────────────────────────────────────────┐
│              Thread Lifecycle                                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Created ─────> Started ─────> Running ─────> Terminated        │
│     │              │              │              │               │
│     │              │              │              │               │
│  ┌──┴──┐       ┌──┴──┐       ┌──┴──┐       ┌──┴──┐            │
│  │     │       │     │       │     │       │     │            │
│  │ new │       │start│       │ run │       │join │            │
│  │     │       │     │       │     │       │     │            │
│  └─────┘       └─────┘       └──┬──┘       └─────┘            │
│                                  │                               │
│                                  ├── Waiting (I/O, lock)        │
│                                  ├── Sleeping                    │
│                                  └── Ready (waiting for GIL)     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Checking Thread State

```python
import threading
import time

def worker():
    time.sleep(2)

thread = threading.Thread(target=worker)

# Thread states
print(f"Before start: is_alive={thread.is_alive()}")  # False

thread.start()
print(f"After start: is_alive={thread.is_alive()}")   # True

thread.join()
print(f"After join: is_alive={thread.is_alive()}")    # False

# Check native thread ID
print(f"Thread ID: {thread.native_id}")  # OS thread ID (3.8+)
print(f"Ident: {thread.ident}")          # Python thread ID
```

## 46.6 Thread Termination

### Normal Termination

```python
import threading

def worker():
    # Thread ends when function returns
    return "done"

thread = threading.Thread(target=worker)
thread.start()
thread.join()  # Wait for completion
```

### Exception in Thread

```python
import threading
import sys

def worker_with_error():
    raise ValueError("Something went wrong")

# Default: exception is printed to stderr
thread = threading.Thread(target=worker_with_error)
thread.start()
thread.join()
# Output: Exception in thread Thread-1:
#         ValueError: Something went wrong

# Custom exception handler
def exception_handler(args):
    print(f"Thread {args.thread.name} raised {args.exc_type.__name__}")
    print(f"Value: {args.exc_value}")

threading.excepthook = exception_handler
```

### Thread Cleanup

```c
// Clean up thread state
void
PyThreadState_Clear(PyThreadState *tstate)
{
    // Clear exception state
    Py_CLEAR(tstate->curexc_type);
    Py_CLEAR(tstate->curexc_value);
    Py_CLEAR(tstate->curexc_traceback);

    // Clear tracing
    Py_CLEAR(tstate->c_profileobj);
    Py_CLEAR(tstate->c_traceobj);

    // Clear thread-local dict
    Py_CLEAR(tstate->dict);

    // Clear async exception
    Py_CLEAR(tstate->async_exc);
}

void
PyThreadState_Delete(PyThreadState *tstate)
{
    // Unlink from interpreter's thread list
    HEAD_LOCK(tstate->interp);
    if (tstate->prev)
        tstate->prev->next = tstate->next;
    else
        tstate->interp->threads.head = tstate->next;
    if (tstate->next)
        tstate->next->prev = tstate->prev;
    HEAD_UNLOCK(tstate->interp);

    // Free memory
    PyMem_RawFree(tstate);
}
```

## 46.7 Daemon Threads

### Daemon vs Non-Daemon

```python
import threading
import time

def daemon_worker():
    while True:
        print("Daemon working...")
        time.sleep(1)

def normal_worker():
    for i in range(3):
        print(f"Normal working {i}...")
        time.sleep(1)

# Daemon thread: Killed when main thread exits
daemon = threading.Thread(target=daemon_worker, daemon=True)
daemon.start()

# Normal thread: Program waits for it
normal = threading.Thread(target=normal_worker)
normal.start()

# Main thread exits after this
print("Main thread done")

# Output:
# Daemon working...
# Normal working 0...
# Main thread done
# Normal working 1...
# Normal working 2...
# (daemon is killed)
```

### Daemon Thread Behavior

```
┌─────────────────────────────────────────────────────────────────┐
│              Daemon vs Non-Daemon Threads                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Non-Daemon (default):                                           │
│  • Python waits for thread to complete before exiting           │
│  • Good for important background tasks                          │
│  • Guaranteed cleanup via atexit                                │
│                                                                  │
│  Daemon:                                                         │
│  • Python exits immediately when main thread ends               │
│  • Thread is abruptly killed                                    │
│  • No cleanup, no finally blocks executed                       │
│  • Good for background services (logging, monitoring)           │
│                                                                  │
│  Warning: Daemon threads may not flush buffers!                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 46.8 Thread Enumeration

### Listing All Threads

```python
import threading
import time

def worker(name):
    time.sleep(2)

# Start some threads
threads = [threading.Thread(target=worker, args=(f"T{i}",), name=f"Worker-{i}")
           for i in range(3)]
for t in threads:
    t.start()

# Enumerate all threads
print("Active threads:")
for thread in threading.enumerate():
    print(f"  {thread.name}: alive={thread.is_alive()}, daemon={thread.daemon}")

# Get count
print(f"Active count: {threading.active_count()}")

# Get current thread
current = threading.current_thread()
print(f"Current thread: {current.name}")

# Get main thread
main = threading.main_thread()
print(f"Main thread: {main.name}")
```

### Thread Identification

```python
import threading
import os

def show_ids():
    print(f"Thread name: {threading.current_thread().name}")
    print(f"Python thread ID: {threading.get_ident()}")
    print(f"Native thread ID: {threading.get_native_id()}")  # 3.8+
    print(f"Process ID: {os.getpid()}")

thread = threading.Thread(target=show_ids)
thread.start()
thread.join()
```

## 46.9 Thread-Local Storage

### Using `threading.local()`

```python
import threading

# Thread-local data
local_data = threading.local()

def worker(value):
    # Each thread has its own copy
    local_data.value = value
    time.sleep(0.1)
    print(f"Thread {threading.current_thread().name}: {local_data.value}")

threads = []
for i in range(3):
    t = threading.Thread(target=worker, args=(i,))
    threads.append(t)
    t.start()

for t in threads:
    t.join()

# Each thread sees its own value
```

### Thread-Local Implementation

```c
// Thread-local storage in CPython
// Uses thread state's dict

PyObject *
PyThreadState_GetDict(void)
{
    PyThreadState *tstate = PyThreadState_GET();
    if (tstate == NULL)
        return NULL;

    if (tstate->dict == NULL) {
        // Lazily create thread-local dict
        tstate->dict = PyDict_New();
        if (tstate->dict == NULL)
            PyErr_Clear();
    }
    return tstate->dict;
}
```

## 46.10 Thread Safety in Thread Management

### Thread-Safe Operations

```python
import threading

# These operations are thread-safe:

# Starting a thread (from any thread)
thread = threading.Thread(target=lambda: None)
thread.start()

# Joining a thread
thread.join()

# Checking thread state
is_alive = thread.is_alive()

# Enumerating threads
threads = threading.enumerate()

# Creating locks
lock = threading.Lock()
```

### Common Pitfalls

```python
import threading

# Pitfall 1: Joining from the same thread
def bad_self_join():
    threading.current_thread().join()  # Deadlock!

# Pitfall 2: Accessing thread attributes after termination
thread = threading.Thread(target=lambda: None)
thread.start()
thread.join()
# thread.native_id may be None after termination

# Pitfall 3: Creating too many threads
threads = []
for i in range(10000):  # May exhaust system resources!
    t = threading.Thread(target=lambda: time.sleep(10))
    t.start()
    threads.append(t)
```

## Summary

- **Python threads** wrap OS threads with PyThreadState
- **Thread creation** involves Python object, C thread state, and OS thread
- **Bootstrap process** sets up GIL and calls Python function
- **Lifecycle**: Created → Started → Running → Terminated
- **Daemon threads** are killed when main thread exits
- **Thread-local storage** via `threading.local()` or thread state dict
- **Thread enumeration** lists all active threads

## Practice Exercises

1. Trace thread creation with sys.settrace
2. Implement a thread pool from scratch
3. Measure thread creation overhead
4. Compare daemon vs non-daemon thread behavior

---

[← Previous: JIT Debugging](../part-09-jit/chapter-45-jit-debugging.md) | [Next: Threading Primitives →](chapter-47-threading-primitives.md)

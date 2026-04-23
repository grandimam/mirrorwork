# Chapter 34: C Extensions and the GIL

## 34.1 GIL Management in C Extensions

C extensions can release the GIL to allow true parallelism:

```
┌─────────────────────────────────────────────────────────────────┐
│              C Extension GIL Management                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Python Code                                                     │
│       │                                                          │
│       ▼                                                          │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  C Extension Function                                    │    │
│  │                                                          │    │
│  │  1. Acquire GIL (already held from Python)              │    │
│  │  2. Parse arguments (needs GIL)                         │    │
│  │  3. Py_BEGIN_ALLOW_THREADS  ← Release GIL               │    │
│  │  4. ... Do CPU/IO work ...   ← No Python objects!       │    │
│  │  5. Py_END_ALLOW_THREADS    ← Reacquire GIL             │    │
│  │  6. Build return value (needs GIL)                      │    │
│  │  7. Return to Python                                     │    │
│  │                                                          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  While GIL released: Other Python threads can run!              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 34.2 `Py_BEGIN_ALLOW_THREADS` and `Py_END_ALLOW_THREADS`

### Basic Usage

```c
#include <Python.h>

static PyObject* compute_heavy(PyObject* self, PyObject* args) {
    int n;
    long result;

    // Parse arguments (GIL held)
    if (!PyArg_ParseTuple(args, "i", &n)) {
        return NULL;
    }

    // Release GIL for CPU-intensive work
    Py_BEGIN_ALLOW_THREADS

    // No Python API calls allowed here!
    result = 0;
    for (long i = 0; i < n; i++) {
        result += i * i;
    }

    Py_END_ALLOW_THREADS

    // GIL reacquired, can use Python API
    return PyLong_FromLong(result);
}
```

### Macro Expansion

```c
// What the macros expand to:
#define Py_BEGIN_ALLOW_THREADS { \
    PyThreadState *_save; \
    _save = PyEval_SaveThread();  // Releases GIL

#define Py_END_ALLOW_THREADS \
    PyEval_RestoreThread(_save); \
}  // Reacquires GIL
```

## 34.3 Thread State Management

### PyThreadState Structure

```c
typedef struct _ts {
    struct _ts *prev;
    struct _ts *next;
    PyInterpreterState *interp;

    PyFrameObject *frame;        // Current frame
    int recursion_depth;
    int tracing;

    PyObject *dict;              // Thread-local storage
    PyObject *async_exc;         // Pending async exception

    // ... more fields
} PyThreadState;
```

### Managing Thread State

```c
// Save thread state and release GIL
PyThreadState* PyEval_SaveThread(void) {
    PyThreadState *tstate = PyThreadState_GET();
    if (tstate == NULL)
        Py_FatalError("NULL tstate");

    // Release the GIL
    drop_gil(tstate);
    return tstate;
}

// Restore thread state and acquire GIL
void PyEval_RestoreThread(PyThreadState *tstate) {
    if (tstate == NULL)
        Py_FatalError("NULL tstate");

    // Acquire the GIL
    take_gil(tstate);

    // Set as current thread state
    PyThreadState_Swap(tstate);
}
```

## 34.4 Safe Patterns for C Extensions

### Pattern 1: Simple GIL Release

```c
static PyObject* read_file_fast(PyObject* self, PyObject* args) {
    const char* filename;
    char* buffer = NULL;
    Py_ssize_t size = 0;
    FILE* fp;

    if (!PyArg_ParseTuple(args, "s", &filename)) {
        return NULL;
    }

    // Allocate buffer while holding GIL
    buffer = (char*)PyMem_Malloc(MAX_SIZE);
    if (buffer == NULL) {
        return PyErr_NoMemory();
    }

    Py_BEGIN_ALLOW_THREADS

    // File I/O without GIL
    fp = fopen(filename, "rb");
    if (fp) {
        size = fread(buffer, 1, MAX_SIZE, fp);
        fclose(fp);
    }

    Py_END_ALLOW_THREADS

    if (fp == NULL) {
        PyMem_Free(buffer);
        PyErr_SetFromErrno(PyExc_IOError);
        return NULL;
    }

    PyObject* result = PyBytes_FromStringAndSize(buffer, size);
    PyMem_Free(buffer);
    return result;
}
```

### Pattern 2: Conditional GIL Release

```c
static PyObject* process_data(PyObject* self, PyObject* args) {
    PyObject* data;
    Py_ssize_t length;

    if (!PyArg_ParseTuple(args, "O", &data)) {
        return NULL;
    }

    // Get buffer info while holding GIL
    Py_buffer view;
    if (PyObject_GetBuffer(data, &view, PyBUF_SIMPLE) < 0) {
        return NULL;
    }

    length = view.len;
    void* buf = view.buf;

    // Only release GIL for large data
    if (length > 10000) {
        long result;

        Py_BEGIN_ALLOW_THREADS
        result = heavy_computation(buf, length);
        Py_END_ALLOW_THREADS

        PyBuffer_Release(&view);
        return PyLong_FromLong(result);
    } else {
        // Small data: keep GIL, avoid overhead
        long result = heavy_computation(buf, length);
        PyBuffer_Release(&view);
        return PyLong_FromLong(result);
    }
}
```

### Pattern 3: Interruptible Long Operations

```c
static PyObject* long_operation(PyObject* self, PyObject* args) {
    int n;
    if (!PyArg_ParseTuple(args, "i", &n)) {
        return NULL;
    }

    long result = 0;
    int interrupted = 0;

    for (int i = 0; i < n; i += 1000) {
        // Process in chunks
        Py_BEGIN_ALLOW_THREADS

        for (int j = i; j < i + 1000 && j < n; j++) {
            result += j * j;
        }

        Py_END_ALLOW_THREADS

        // Check for signals/interrupts (GIL held)
        if (PyErr_CheckSignals() != 0) {
            return NULL;  // KeyboardInterrupt or other
        }
    }

    return PyLong_FromLong(result);
}
```

## 34.5 Common Pitfalls

### Pitfall 1: Accessing Python Objects Without GIL

```c
// WRONG - Crash or corruption!
static PyObject* bad_example(PyObject* self, PyObject* args) {
    PyObject* list;
    if (!PyArg_ParseTuple(args, "O", &list)) {
        return NULL;
    }

    Py_BEGIN_ALLOW_THREADS
    // DANGER: Accessing Python object without GIL!
    Py_ssize_t len = PyList_Size(list);  // CRASH!
    Py_END_ALLOW_THREADS

    return PyLong_FromSsize_t(len);
}

// CORRECT - Extract data first
static PyObject* good_example(PyObject* self, PyObject* args) {
    PyObject* list;
    if (!PyArg_ParseTuple(args, "O", &list)) {
        return NULL;
    }

    // Get data while holding GIL
    Py_ssize_t len = PyList_Size(list);

    Py_BEGIN_ALLOW_THREADS
    // Use extracted data (not Python objects)
    long result = some_computation(len);
    Py_END_ALLOW_THREADS

    return PyLong_FromLong(result);
}
```

### Pitfall 2: Callback into Python

```c
// WRONG - Calling Python without GIL
static PyObject* bad_callback(PyObject* self, PyObject* args) {
    PyObject* callback;
    if (!PyArg_ParseTuple(args, "O", &callback)) {
        return NULL;
    }

    Py_BEGIN_ALLOW_THREADS
    // DANGER: Calling Python callback without GIL!
    PyObject_Call(callback, NULL, NULL);  // CRASH!
    Py_END_ALLOW_THREADS

    Py_RETURN_NONE;
}

// CORRECT - Reacquire GIL for callback
static PyObject* good_callback(PyObject* self, PyObject* args) {
    PyObject* callback;
    if (!PyArg_ParseTuple(args, "O", &callback)) {
        return NULL;
    }

    Py_BEGIN_ALLOW_THREADS

    // Do heavy work without GIL
    heavy_work();

    // Temporarily reacquire GIL for callback
    PyGILState_STATE gstate = PyGILState_Ensure();
    PyObject_Call(callback, PyTuple_New(0), NULL);
    PyGILState_Release(gstate);

    // Continue without GIL
    more_heavy_work();

    Py_END_ALLOW_THREADS

    Py_RETURN_NONE;
}
```

### Pitfall 3: Memory Management

```c
// WRONG - PyMem functions need GIL
static PyObject* bad_memory(PyObject* self, PyObject* args) {
    Py_BEGIN_ALLOW_THREADS

    // DANGER: PyMem_* requires GIL!
    char* buffer = PyMem_Malloc(1000);  // Wrong!

    Py_END_ALLOW_THREADS

    return PyBytes_FromStringAndSize(buffer, 1000);
}

// CORRECT - Use standard malloc without GIL
static PyObject* good_memory(PyObject* self, PyObject* args) {
    char* buffer;

    Py_BEGIN_ALLOW_THREADS

    // Standard malloc is fine without GIL
    buffer = malloc(1000);
    if (buffer) {
        do_work(buffer);
    }

    Py_END_ALLOW_THREADS

    if (buffer == NULL) {
        return PyErr_NoMemory();
    }

    PyObject* result = PyBytes_FromStringAndSize(buffer, 1000);
    free(buffer);
    return result;
}
```

## 34.6 `PyGILState_Ensure` and `PyGILState_Release`

For threads not created by Python:

```c
#include <pthread.h>
#include <Python.h>

// Thread function (not created by Python)
void* worker_thread(void* arg) {
    // Ensure we have the GIL
    PyGILState_STATE gstate = PyGILState_Ensure();

    // Now safe to use Python API
    PyObject* result = PyObject_CallFunction(
        (PyObject*)arg, "s", "Hello from C thread"
    );
    Py_XDECREF(result);

    // Release the GIL
    PyGILState_Release(gstate);

    return NULL;
}

static PyObject* start_worker(PyObject* self, PyObject* args) {
    PyObject* callback;
    if (!PyArg_ParseTuple(args, "O", &callback)) {
        return NULL;
    }

    Py_INCREF(callback);  // Keep alive

    pthread_t thread;
    pthread_create(&thread, NULL, worker_thread, callback);
    pthread_detach(thread);

    Py_RETURN_NONE;
}
```

## 34.7 NumPy and GIL

NumPy releases the GIL for many operations:

```c
// Simplified NumPy pattern
static PyObject* array_operation(PyObject* self, PyObject* args) {
    PyArrayObject* arr;
    if (!PyArg_ParseTuple(args, "O!", &PyArray_Type, &arr)) {
        return NULL;
    }

    // Get array info while holding GIL
    npy_intp n = PyArray_SIZE(arr);
    double* data = (double*)PyArray_DATA(arr);

    // Release GIL for computation
    NPY_BEGIN_THREADS_DEF;
    NPY_BEGIN_THREADS;

    // Operate on raw memory (no Python API)
    for (npy_intp i = 0; i < n; i++) {
        data[i] = data[i] * data[i];
    }

    NPY_END_THREADS;

    Py_RETURN_NONE;
}
```

### NumPy GIL Macros

```c
// NumPy provides its own macros
#define NPY_BEGIN_THREADS_DEF PyThreadState *_save;
#define NPY_BEGIN_THREADS     _save = PyEval_SaveThread();
#define NPY_END_THREADS       PyEval_RestoreThread(_save);

// Conditional version (only if array is large)
#define NPY_BEGIN_THREADS_THRESHOLDED(n) \
    do { if ((n) > NPY_THRESHOLD) NPY_BEGIN_THREADS; } while(0)
```

## 34.8 Subinterpreter Compatibility

### Checking Support

```c
// Module slot for subinterpreter support
static struct PyModuleDef_Slot module_slots[] = {
    {Py_mod_multiple_interpreters, Py_MOD_PER_INTERPRETER_GIL_SUPPORTED},
    {0, NULL}
};

static struct PyModuleDef moduledef = {
    PyModuleDef_HEAD_INIT,
    .m_name = "mymodule",
    .m_doc = "My module",
    .m_size = 0,
    .m_methods = module_methods,
    .m_slots = module_slots,
};
```

### Global State Considerations

```c
// WRONG - Global state breaks subinterpreters
static PyObject* global_cache = NULL;  // Shared across interpreters!

// CORRECT - Per-interpreter state
typedef struct {
    PyObject* cache;
} module_state;

static module_state* get_module_state(PyObject* module) {
    return (module_state*)PyModule_GetState(module);
}

static PyObject* cached_operation(PyObject* module, PyObject* args) {
    module_state* state = get_module_state(module);
    // Use state->cache (interpreter-local)
    ...
}
```

## 34.9 Free-Threaded Python Compatibility

### Checking for Free-Threaded Build

```c
#ifdef Py_GIL_DISABLED
// Free-threaded Python (no GIL)
// Need explicit synchronization
#include <stdatomic.h>

static atomic_long counter = 0;

static PyObject* increment_counter(PyObject* self, PyObject* args) {
    atomic_fetch_add(&counter, 1);
    return PyLong_FromLong(atomic_load(&counter));
}

#else
// GIL-protected Python
static long counter = 0;

static PyObject* increment_counter(PyObject* self, PyObject* args) {
    counter++;  // Safe, GIL protects
    return PyLong_FromLong(counter);
}
#endif
```

### Module Definition for Free-Threaded

```c
static struct PyModuleDef_Slot module_slots[] = {
#ifdef Py_GIL_DISABLED
    {Py_mod_gil, Py_MOD_GIL_NOT_USED},  // Doesn't need GIL
#endif
    {0, NULL}
};
```

## 34.10 Best Practices Summary

```
┌─────────────────────────────────────────────────────────────────┐
│            C Extension GIL Best Practices                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  DO:                                                             │
│  ✓ Release GIL for long-running CPU/IO operations               │
│  ✓ Extract data from Python objects before releasing GIL        │
│  ✓ Use PyGILState_Ensure/Release for non-Python threads        │
│  ✓ Check PyErr_CheckSignals() periodically                     │
│  ✓ Use standard malloc/free without GIL (not PyMem_*)          │
│  ✓ Test with multiple threads                                   │
│                                                                  │
│  DON'T:                                                          │
│  ✗ Access Python objects without GIL                            │
│  ✗ Call Python API without GIL                                  │
│  ✗ Use PyMem_* without GIL                                      │
│  ✗ Keep GIL during blocking I/O                                 │
│  ✗ Assume single-threaded execution                             │
│  ✗ Use global state without synchronization                     │
│                                                                  │
│  CONSIDER:                                                       │
│  • Threshold for GIL release (overhead vs benefit)              │
│  • Subinterpreter compatibility                                  │
│  • Free-threaded Python compatibility                           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Summary

- **GIL macros** (`Py_BEGIN/END_ALLOW_THREADS`) enable parallelism
- **Thread state** must be managed properly
- **Never access Python objects** without the GIL
- **PyGILState_*** for non-Python threads
- **NumPy** demonstrates effective GIL release patterns
- **Subinterpreters** require per-interpreter state
- **Free-threaded Python** needs explicit synchronization

## Practice Exercises

1. Write a C extension that computes checksums with GIL released
2. Implement a thread-safe counter for free-threaded Python
3. Create a C extension compatible with subinterpreters
4. Benchmark GIL release overhead for different operation sizes

---

[← Previous: Subinterpreters](chapter-33-subinterpreters.md) | [Next: Free-Threaded Python Overview →](../part-08-free-threading/chapter-35-free-threading-overview.md)

# Chapter 41: Free-Threaded C Extensions

## 41.1 The Extension Compatibility Challenge

C extensions must adapt for free-threaded Python:

```
┌─────────────────────────────────────────────────────────────────┐
│              Extension Compatibility                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  With GIL:                                                       │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Extension code runs with GIL held                       │    │
│  │  • Global state is protected                             │    │
│  │  • No race conditions in Python API calls               │    │
│  │  • Extensions don't need internal synchronization       │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Without GIL:                                                    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Extension code runs WITHOUT GIL protection             │    │
│  │  • Global state is NOT protected                        │    │
│  │  • Python API calls must still be thread-safe          │    │
│  │  • Extensions MUST handle their own synchronization     │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Transition: Extensions must opt-in to free-threading           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 41.2 Module Flags for Free-Threading

### Declaring Free-Threading Support

```c
// Extension module definition
static struct PyModuleDef_Slot module_slots[] = {
    {Py_mod_exec, module_exec},

    // Declare free-threading compatibility
    #ifdef Py_GIL_DISABLED
    {Py_mod_gil, Py_MOD_GIL_NOT_USED},  // Module doesn't need GIL
    #endif

    {0, NULL}
};

static struct PyModuleDef moduledef = {
    PyModuleDef_HEAD_INIT,
    .m_name = "myextension",
    .m_doc = "My free-threading compatible extension",
    .m_size = sizeof(module_state),
    .m_methods = module_methods,
    .m_slots = module_slots,
};

PyMODINIT_FUNC
PyInit_myextension(void)
{
    return PyModuleDef_Init(&moduledef);
}
```

### GIL Flag Values

```c
// Module GIL flags (Python 3.13+)

// Py_MOD_GIL_USED (default)
// - Module needs the GIL
// - Python may enable GIL for this module's threads
{Py_mod_gil, Py_MOD_GIL_USED}

// Py_MOD_GIL_NOT_USED
// - Module is fully thread-safe
// - Doesn't need GIL protection
{Py_mod_gil, Py_MOD_GIL_NOT_USED}
```

## 41.3 Handling Global State

### The Problem with Global State

```c
// UNSAFE: Global state without protection
static PyObject *global_cache = NULL;
static int global_counter = 0;

static PyObject *
get_from_cache(PyObject *self, PyObject *key)
{
    // Race condition! Multiple threads read/write global_cache
    if (global_cache == NULL) {
        global_cache = PyDict_New();  // Race!
    }
    return PyDict_GetItem(global_cache, key);  // Race!
}
```

### Solution 1: Per-Module State

```c
// SAFE: Use per-module state
typedef struct {
    PyObject *cache;
    int counter;
} module_state;

static inline module_state *
get_module_state(PyObject *module)
{
    void *state = PyModule_GetState(module);
    assert(state != NULL);
    return (module_state *)state;
}

static PyObject *
get_from_cache(PyObject *module, PyObject *key)
{
    module_state *state = get_module_state(module);
    // state is per-module, but still needs synchronization
    // if accessed from multiple threads
    return PyDict_GetItem(state->cache, key);
}

static int
module_exec(PyObject *module)
{
    module_state *state = get_module_state(module);
    state->cache = PyDict_New();
    state->counter = 0;
    if (state->cache == NULL) {
        return -1;
    }
    return 0;
}
```

### Solution 2: Thread-Local State

```c
#include <pthread.h>

// Thread-local storage
static pthread_key_t tls_key;
static pthread_once_t tls_once = PTHREAD_ONCE_INIT;

typedef struct {
    PyObject *cache;
    int counter;
} thread_state;

static void
init_tls_key(void)
{
    pthread_key_create(&tls_key, free);
}

static thread_state *
get_thread_state(void)
{
    pthread_once(&tls_once, init_tls_key);

    thread_state *state = pthread_getspecific(tls_key);
    if (state == NULL) {
        state = malloc(sizeof(thread_state));
        state->cache = NULL;
        state->counter = 0;
        pthread_setspecific(tls_key, state);
    }
    return state;
}

static PyObject *
thread_local_operation(PyObject *self, PyObject *args)
{
    thread_state *state = get_thread_state();
    // No synchronization needed - thread-local!
    state->counter++;
    return PyLong_FromLong(state->counter);
}
```

### Solution 3: Explicit Locking

```c
#include <pthread.h>

static PyObject *global_cache = NULL;
static pthread_mutex_t cache_mutex = PTHREAD_MUTEX_INITIALIZER;

static PyObject *
safe_cache_operation(PyObject *self, PyObject *args)
{
    PyObject *key, *value;
    if (!PyArg_ParseTuple(args, "OO", &key, &value)) {
        return NULL;
    }

    pthread_mutex_lock(&cache_mutex);

    if (global_cache == NULL) {
        global_cache = PyDict_New();
        if (global_cache == NULL) {
            pthread_mutex_unlock(&cache_mutex);
            return NULL;
        }
    }

    int result = PyDict_SetItem(global_cache, key, value);

    pthread_mutex_unlock(&cache_mutex);

    if (result < 0) {
        return NULL;
    }
    Py_RETURN_NONE;
}
```

## 41.4 Thread-Safe Data Structures

### Using Atomic Operations

```c
#include <stdatomic.h>

// Atomic counter
static atomic_long counter = 0;

static PyObject *
atomic_increment(PyObject *self, PyObject *args)
{
    long old = atomic_fetch_add(&counter, 1);
    return PyLong_FromLong(old + 1);
}

static PyObject *
atomic_get(PyObject *self, PyObject *args)
{
    long value = atomic_load(&counter);
    return PyLong_FromLong(value);
}
```

### Lock-Free Data Structures

```c
#include <stdatomic.h>

// Simple lock-free stack
typedef struct node {
    PyObject *value;
    struct node *next;
} node_t;

static _Atomic(node_t*) stack_head = NULL;

static PyObject *
stack_push(PyObject *self, PyObject *value)
{
    node_t *new_node = malloc(sizeof(node_t));
    if (new_node == NULL) {
        return PyErr_NoMemory();
    }

    Py_INCREF(value);
    new_node->value = value;

    node_t *old_head;
    do {
        old_head = atomic_load(&stack_head);
        new_node->next = old_head;
    } while (!atomic_compare_exchange_weak(&stack_head, &old_head, new_node));

    Py_RETURN_NONE;
}

static PyObject *
stack_pop(PyObject *self, PyObject *args)
{
    node_t *old_head;
    node_t *new_head;

    do {
        old_head = atomic_load(&stack_head);
        if (old_head == NULL) {
            Py_RETURN_NONE;  // Stack empty
        }
        new_head = old_head->next;
    } while (!atomic_compare_exchange_weak(&stack_head, &old_head, new_head));

    PyObject *value = old_head->value;
    free(old_head);
    return value;  // Caller owns reference
}
```

## 41.5 Critical Sections in Extensions

### Using Python's Critical Section API

```c
// Python 3.13+ critical section API

static PyObject *
safe_dict_operation(PyObject *self, PyObject *args)
{
    PyObject *dict, *key, *value;
    if (!PyArg_ParseTuple(args, "OOO", &dict, &key, &value)) {
        return NULL;
    }

    // Enter critical section for dict
    Py_BEGIN_CRITICAL_SECTION(dict);

    int result = PyDict_SetItem(dict, key, value);

    Py_END_CRITICAL_SECTION();

    if (result < 0) {
        return NULL;
    }
    Py_RETURN_NONE;
}

// For operations on multiple objects
static PyObject *
safe_transfer(PyObject *self, PyObject *args)
{
    PyObject *source, *dest, *key;
    if (!PyArg_ParseTuple(args, "OOO", &source, &dest, &key)) {
        return NULL;
    }

    // Lock both dictionaries (ordered to prevent deadlock)
    Py_BEGIN_CRITICAL_SECTION2(source, dest);

    PyObject *value = PyDict_GetItem(source, key);
    if (value != NULL) {
        PyDict_SetItem(dest, key, value);
        PyDict_DelItem(source, key);
    }

    Py_END_CRITICAL_SECTION2();

    Py_RETURN_NONE;
}
```

## 41.6 Reference Counting Considerations

### Safe Reference Counting

```c
// With free-threading, be extra careful with borrowed references

// UNSAFE: Borrowed reference may become invalid
static PyObject *
unsafe_borrowed(PyObject *self, PyObject *dict)
{
    // PyDict_GetItem returns borrowed reference
    PyObject *value = PyDict_GetItem(dict, key);
    // Another thread might delete this key now!
    PyObject *result = PyObject_Str(value);  // May crash!
    return result;
}

// SAFE: Immediately incref borrowed reference
static PyObject *
safe_borrowed(PyObject *self, PyObject *dict)
{
    PyObject *value = PyDict_GetItem(dict, key);
    if (value == NULL) {
        Py_RETURN_NONE;
    }
    Py_INCREF(value);  // Protect the reference
    PyObject *result = PyObject_Str(value);
    Py_DECREF(value);  // Release protection
    return result;
}

// BETTER: Use PyDict_GetItemRef (Python 3.13+)
static PyObject *
better_borrowed(PyObject *self, PyObject *dict)
{
    PyObject *value;
    // Returns new reference (or NULL with exception)
    if (PyDict_GetItemRef(dict, key, &value) < 0) {
        return NULL;
    }
    if (value == NULL) {
        Py_RETURN_NONE;
    }
    PyObject *result = PyObject_Str(value);
    Py_DECREF(value);
    return result;
}
```

## 41.7 Porting Existing Extensions

### Step-by-Step Migration

```
┌─────────────────────────────────────────────────────────────────┐
│              Extension Migration Checklist                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Audit Global State                                           │
│     □ List all global/static variables                          │
│     □ Identify which are read-only vs mutable                   │
│     □ Plan migration (module state, TLS, or locking)            │
│                                                                  │
│  2. Review Python API Usage                                      │
│     □ Check borrowed reference handling                         │
│     □ Update to new APIs (PyDict_GetItemRef, etc.)             │
│     □ Add critical sections where needed                        │
│                                                                  │
│  3. Add Synchronization                                          │
│     □ Add locks for shared mutable state                        │
│     □ Use atomics for simple counters/flags                     │
│     □ Consider lock-free alternatives                           │
│                                                                  │
│  4. Update Module Definition                                     │
│     □ Add Py_mod_gil slot                                       │
│     □ Set Py_MOD_GIL_NOT_USED                                   │
│     □ Use per-module state (m_size > 0)                         │
│                                                                  │
│  5. Test Thoroughly                                              │
│     □ Run with multiple threads                                 │
│     □ Use thread sanitizer (TSan)                               │
│     □ Test with free-threaded Python build                      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Example Migration

```c
// BEFORE: GIL-dependent extension

static PyObject *cache = NULL;

static PyObject *
old_get_cached(PyObject *self, PyObject *key)
{
    if (cache == NULL) {
        cache = PyDict_New();
    }
    return PyDict_GetItem(cache, key);
}

static PyMethodDef methods[] = {
    {"get_cached", old_get_cached, METH_O, NULL},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef moduledef = {
    PyModuleDef_HEAD_INIT,
    .m_name = "myext",
    .m_methods = methods,
};

// AFTER: Free-threading compatible

typedef struct {
    PyObject *cache;
    pthread_mutex_t lock;
} module_state;

static int
module_traverse(PyObject *m, visitproc visit, void *arg)
{
    module_state *state = PyModule_GetState(m);
    Py_VISIT(state->cache);
    return 0;
}

static int
module_clear(PyObject *m)
{
    module_state *state = PyModule_GetState(m);
    Py_CLEAR(state->cache);
    return 0;
}

static void
module_free(void *m)
{
    module_state *state = PyModule_GetState((PyObject *)m);
    pthread_mutex_destroy(&state->lock);
}

static int
module_exec(PyObject *m)
{
    module_state *state = PyModule_GetState(m);
    state->cache = PyDict_New();
    pthread_mutex_init(&state->lock, NULL);
    if (state->cache == NULL) {
        return -1;
    }
    return 0;
}

static PyObject *
new_get_cached(PyObject *module, PyObject *key)
{
    module_state *state = PyModule_GetState(module);
    PyObject *value;

    pthread_mutex_lock(&state->lock);

    value = PyDict_GetItem(state->cache, key);
    Py_XINCREF(value);  // Protect borrowed reference

    pthread_mutex_unlock(&state->lock);

    return value;  // Returns new reference or NULL
}

static PyMethodDef methods[] = {
    {"get_cached", new_get_cached, METH_O, NULL},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef_Slot slots[] = {
    {Py_mod_exec, module_exec},
    #ifdef Py_GIL_DISABLED
    {Py_mod_gil, Py_MOD_GIL_NOT_USED},
    #endif
    {0, NULL}
};

static struct PyModuleDef moduledef = {
    PyModuleDef_HEAD_INIT,
    .m_name = "myext",
    .m_size = sizeof(module_state),
    .m_methods = methods,
    .m_slots = slots,
    .m_traverse = module_traverse,
    .m_clear = module_clear,
    .m_free = module_free,
};

PyMODINIT_FUNC
PyInit_myext(void)
{
    return PyModuleDef_Init(&moduledef);
}
```

## 41.8 Testing for Thread Safety

### Thread Sanitizer

```bash
# Build extension with thread sanitizer
CFLAGS="-fsanitize=thread" \
LDFLAGS="-fsanitize=thread" \
python setup.py build_ext --inplace

# Run tests
python -m pytest tests/ -v
# TSan will report any data races
```

### Stress Testing

```python
import threading
import myextension

def stress_test():
    """Run extension operations from many threads."""
    results = []
    errors = []

    def worker():
        try:
            for i in range(10000):
                myextension.operation()
                myextension.get_cached(f"key_{i}")
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(100)]

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    if errors:
        print(f"Errors: {len(errors)}")
        for e in errors[:5]:
            print(f"  {e}")
    else:
        print("All threads completed successfully")

stress_test()
```

## 41.9 Common Pitfalls

### Pitfall 1: Assuming GIL Protection

```c
// WRONG: Assumes GIL protects callback
static PyObject *callback = NULL;

void set_callback(PyObject *cb) {
    Py_XDECREF(callback);  // Race condition!
    Py_INCREF(cb);
    callback = cb;  // Race condition!
}

// CORRECT: Use locking
static pthread_mutex_t callback_lock = PTHREAD_MUTEX_INITIALIZER;

void set_callback_safe(PyObject *cb) {
    pthread_mutex_lock(&callback_lock);
    Py_XDECREF(callback);
    Py_INCREF(cb);
    callback = cb;
    pthread_mutex_unlock(&callback_lock);
}
```

### Pitfall 2: Double-Checked Locking

```c
// WRONG: Broken double-checked locking
static PyObject *singleton = NULL;

PyObject *get_singleton(void) {
    if (singleton == NULL) {  // Race!
        pthread_mutex_lock(&lock);
        if (singleton == NULL) {
            singleton = create_singleton();  // May not be visible!
        }
        pthread_mutex_unlock(&lock);
    }
    return singleton;
}

// CORRECT: Use atomic with proper ordering
static _Atomic(PyObject*) singleton = NULL;

PyObject *get_singleton_safe(void) {
    PyObject *result = atomic_load_explicit(&singleton, memory_order_acquire);
    if (result == NULL) {
        pthread_mutex_lock(&lock);
        result = atomic_load_explicit(&singleton, memory_order_relaxed);
        if (result == NULL) {
            result = create_singleton();
            atomic_store_explicit(&singleton, result, memory_order_release);
        }
        pthread_mutex_unlock(&lock);
    }
    return result;
}
```

## 41.10 Best Practices Summary

```
┌─────────────────────────────────────────────────────────────────┐
│              Free-Threading Best Practices                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  DO:                                                             │
│  ✓ Use per-module state instead of globals                      │
│  ✓ Protect borrowed references immediately                      │
│  ✓ Use critical sections for Python object mutations            │
│  ✓ Use atomics for simple counters and flags                    │
│  ✓ Test with thread sanitizer                                   │
│  ✓ Declare Py_MOD_GIL_NOT_USED when thread-safe                │
│                                                                  │
│  DON'T:                                                          │
│  ✗ Assume single-threaded execution                             │
│  ✗ Use global mutable state without synchronization             │
│  ✗ Hold locks while calling Python code (deadlock risk)         │
│  ✗ Ignore borrowed reference lifetimes                          │
│  ✗ Use broken patterns (naive double-checked locking)          │
│                                                                  │
│  CONSIDER:                                                       │
│  • Thread-local state for per-thread data                       │
│  • Lock-free data structures for high contention                │
│  • Read-copy-update for read-heavy workloads                    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Summary

- **Free-threading compatible** extensions declare `Py_MOD_GIL_NOT_USED`
- **Global state** must be protected or replaced with per-module/thread-local
- **Critical sections** protect Python object operations
- **Borrowed references** need immediate protection
- **Test thoroughly** with multiple threads and thread sanitizer
- **Migration** follows systematic audit and update process

## Practice Exercises

1. Port a simple C extension to be free-threading compatible
2. Implement a thread-safe cache using critical sections
3. Use thread sanitizer to find races in an extension
4. Benchmark extension performance with and without GIL

---

[← Previous: Mimalloc Integration](chapter-40-mimalloc-integration.md) | [Next: JIT Compilation Overview →](../part-09-jit/chapter-42-jit-overview.md)

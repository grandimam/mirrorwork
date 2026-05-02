# Chapter 20: Reference Counting

## 20.1 How Reference Counting Works

Python uses reference counting as its primary memory management strategy:

```
┌─────────────────────────────────────────────────────────────────┐
│                   Reference Counting Basics                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Every object has a reference count (ob_refcnt):                │
│                                                                  │
│  ┌──────────────────────────────────────────────────┐           │
│  │  PyObject                                         │           │
│  │  ├── ob_refcnt = 3  ◀── Number of references     │           │
│  │  ├── ob_type                                      │           │
│  │  └── ... data ...                                 │           │
│  └──────────────────────────────────────────────────┘           │
│            ▲         ▲         ▲                                │
│            │         │         │                                │
│          ref 1     ref 2     ref 3                              │
│                                                                  │
│  When count reaches 0 → Object is deallocated                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Observing Reference Counts

```python
import sys

# Create object
obj = [1, 2, 3]
print(sys.getrefcount(obj))  # 2 (obj + getrefcount argument)

# Add reference
another = obj
print(sys.getrefcount(obj))  # 3

# Remove reference
del another
print(sys.getrefcount(obj))  # 2

# In container
container = [obj]
print(sys.getrefcount(obj))  # 3

# Remove from container
container.clear()
print(sys.getrefcount(obj))  # 2
```

## 20.2 `Py_INCREF` and `Py_DECREF` Macros

At the C level, reference counts are managed with macros:

```c
// Include/object.h

// Increment reference count
#define Py_INCREF(op) do { \
    PyObject *_py_incref_tmp = (PyObject *)(op); \
    _Py_INCREF(_py_incref_tmp); \
} while (0)

static inline void _Py_INCREF(PyObject *op) {
    op->ob_refcnt++;
}

// Decrement reference count
#define Py_DECREF(op) do { \
    PyObject *_py_decref_tmp = (PyObject *)(op); \
    if (--_py_decref_tmp->ob_refcnt == 0) { \
        _Py_Dealloc(_py_decref_tmp);  // Deallocate!
    } \
} while (0)
```

### Variants

```c
// Safe increment (handles NULL)
Py_XINCREF(op);  // Does nothing if op is NULL

// Safe decrement (handles NULL)
Py_XDECREF(op);  // Does nothing if op is NULL

// Clear a pointer (decref and set to NULL)
Py_CLEAR(op);    // Atomically decrefs and NULLs
```

## 20.3 Borrowed vs Owned References

Understanding reference ownership is crucial:

### Owned References

```c
// Function RETURNS a NEW reference (caller must decref)
PyObject* PyList_New(Py_ssize_t len);

// Usage:
PyObject *list = PyList_New(0);  // refcnt = 1, caller owns it
// ... use list ...
Py_DECREF(list);  // Caller must release
```

### Borrowed References

```c
// Function RETURNS a BORROWED reference (caller must NOT decref)
PyObject* PyList_GetItem(PyObject *list, Py_ssize_t index);

// Usage:
PyObject *item = PyList_GetItem(list, 0);  // Borrowed!
// ... use item (but don't store long-term) ...
// Do NOT: Py_DECREF(item);  // Wrong! Borrowed reference

// To keep it, increment:
Py_INCREF(item);  // Now we own a reference
// ... can store item ...
Py_DECREF(item);  // When done
```

### Common Patterns

```c
// Functions that GIVE ownership (new reference):
PyLong_FromLong(42);      // Returns new reference
PyObject_Repr(obj);       // Returns new reference
PySequence_List(seq);     // Returns new reference

// Functions that BORROW (no ownership transfer):
PyList_GetItem(list, i);  // Returns borrowed
PyDict_GetItem(dict, key);// Returns borrowed
PyTuple_GetItem(tuple, i);// Returns borrowed

// Functions that STEAL (take ownership):
PyList_SetItem(list, i, item);  // Steals reference to item
PyTuple_SetItem(tuple, i, item);// Steals reference to item
```

## 20.4 Reference Counting Rules for C Extensions

### Golden Rules

```c
// Rule 1: If you create it, you own it
PyObject *obj = PyLong_FromLong(42);  // You own this
// ... use obj ...
Py_DECREF(obj);  // You must release

// Rule 2: If you receive a borrowed reference, don't decref
PyObject *item = PyList_GetItem(list, 0);  // Borrowed
// Just use it, don't decref

// Rule 3: If you want to keep a borrowed reference, incref it
PyObject *item = PyList_GetItem(list, 0);  // Borrowed
Py_INCREF(item);  // Now you own a reference
stored_item = item;  // Safe to store
// Later: Py_DECREF(stored_item);

// Rule 4: If you pass to a "stealing" function, don't decref
PyObject *item = PyLong_FromLong(42);  // You own this
PyList_SetItem(list, 0, item);  // SetItem steals it
// Do NOT: Py_DECREF(item);  // Reference was stolen!
```

### Common Mistakes

```c
// WRONG: Decrementing borrowed reference
PyObject *item = PyList_GetItem(list, 0);
Py_DECREF(item);  // BUG! Use-after-free or double-free

// WRONG: Forgetting to decrement owned reference
PyObject *obj = PyLong_FromLong(42);
return;  // BUG! Memory leak

// WRONG: Double decrement
PyObject *obj = PyLong_FromLong(42);
Py_DECREF(obj);
Py_DECREF(obj);  // BUG! Double-free

// CORRECT: Using Py_CLEAR to avoid issues
PyObject *obj = something;
Py_CLEAR(obj);  // Decrefs and sets to NULL
// Safe: obj is now NULL, won't double-free
```

## 20.5 Common Reference Counting Bugs

### Use After Free

```c
PyObject *list = PyList_New(1);
PyObject *item = PyLong_FromLong(42);
PyList_SetItem(list, 0, item);  // Steals item

// BUG: item's reference was stolen
printf("%ld\n", PyLong_AsLong(item));  // Use after potential free!

// FIX: Don't use item after SetItem steals it
```

### Memory Leak

```c
PyObject *result = NULL;
PyObject *temp = PyLong_FromLong(42);  // refcnt = 1

if (some_condition) {
    result = temp;
    return result;  // BUG: temp leaks if condition is false!
}

// FIX: Always clean up
if (some_condition) {
    result = temp;  // Transfer ownership
} else {
    Py_DECREF(temp);  // Clean up
}
return result;
```

### Double Free

```c
PyObject *obj = PyLong_FromLong(42);
PyList_Append(list, obj);  // Append increfs internally
Py_DECREF(obj);  // Correct: we're done with our reference

// Later...
Py_DECREF(obj);  // BUG! Already decremented

// FIX: Use Py_CLEAR
Py_CLEAR(obj);  // Sets obj to NULL after decref
// Later: Py_XDECREF(obj);  // Safe, does nothing for NULL
```

## 20.6 Weak References (`weakref` Module)

Weak references don't increment reference count:

```python
import weakref

class MyClass:
    pass

obj = MyClass()
print(sys.getrefcount(obj))  # 2

# Create weak reference (doesn't increment count)
weak = weakref.ref(obj)
print(sys.getrefcount(obj))  # Still 2!

# Access through weak reference
print(weak())  # Returns obj or None if dead

# Delete original
del obj
print(weak())  # None - object was collected
```

### Weak Reference Use Cases

```python
import weakref

# 1. Caching without preventing collection
class ExpensiveObject:
    pass

cache = weakref.WeakValueDictionary()

def get_expensive(key):
    obj = cache.get(key)
    if obj is None:
        obj = ExpensiveObject()
        cache[key] = obj  # Weak reference
    return obj

# 2. Observer pattern without preventing cleanup
class Observable:
    def __init__(self):
        self._observers = weakref.WeakSet()

    def add_observer(self, observer):
        self._observers.add(observer)

    def notify(self):
        for observer in self._observers:
            observer.update()
```

## 20.7 Reference Counting Limitations (Cycles)

Reference counting can't handle cycles:

```python
# Create a cycle
a = []
b = []
a.append(b)  # a references b
b.append(a)  # b references a

# Both have refcount > 0, but neither is reachable
del a
del b
# Memory leaked! (Without garbage collector)

# Python's cyclic garbage collector handles this
import gc
gc.collect()  # Finds and breaks cycles
```

### Cycle Visualization

```
┌─────────────────────────────────────────────────────────────────┐
│                    Reference Cycle                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Before del:                                                     │
│                                                                  │
│  Variable 'a' ──▶ list_a (refcnt=2) ──▶ list_b (refcnt=2)      │
│                         ▲                     │                  │
│                         └─────────────────────┘                  │
│  Variable 'b' ─────────────────────────────────┘                │
│                                                                  │
│  After del a, del b:                                            │
│                                                                  │
│               list_a (refcnt=1) ──▶ list_b (refcnt=1)           │
│                         ▲                     │                  │
│                         └─────────────────────┘                  │
│                                                                  │
│  Both still have refcnt > 0, but unreachable!                   │
│  Garbage collector must find and collect these.                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Summary

- Every object has **ob_refcnt** tracking references
- **Py_INCREF/DECREF** modify reference counts
- **Owned references** must be decremented
- **Borrowed references** must NOT be decremented
- **Weak references** don't affect reference counts
- **Cycles** require garbage collector (see next chapter)

## Practice Exercises

1. Use `sys.getrefcount()` to trace reference count changes
2. Create a reference cycle and observe garbage collection
3. Implement a class using `weakref` for caching
4. Read CPython code to identify owned vs borrowed references

---

[← Previous: pymalloc Allocator](chapter-19-pymalloc.md) | [Next: Garbage Collection →](chapter-21-garbage-collection.md)

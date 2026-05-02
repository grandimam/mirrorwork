# Chapter 13: Object Fundamentals

## 13.1 Everything is an Object

In Python, everything is an object - integers, strings, functions, classes, modules, even types themselves:

```python
# All of these are objects
print(type(42))           # <class 'int'>
print(type("hello"))      # <class 'str'>
print(type([1, 2, 3]))    # <class 'list'>
print(type(print))        # <class 'builtin_function_or_method'>
print(type(int))          # <class 'type'>
print(type(type))         # <class 'type'>

# Objects have attributes
print((42).bit_length())  # 6
print("hello".upper())    # "HELLO"

# Even None is an object
print(type(None))         # <class 'NoneType'>
```

### Object Hierarchy

```
┌─────────────────────────────────────────────────────────────────┐
│                    Python Object Hierarchy                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│                         object                                   │
│                            │                                     │
│            ┌───────────────┼───────────────┐                    │
│            │               │               │                     │
│          type            int            str    ... (all types)  │
│            │                                                     │
│     ┌──────┴──────┐                                             │
│     │             │                                              │
│  MyClass    OtherClass                                          │
│                                                                  │
│  Note: type is its own type: type(type) is type                 │
│        object is instance of type                                │
│        type is subclass of object                                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

```python
# The type/object relationship
print(isinstance(type, object))    # True - type IS an object
print(issubclass(type, object))    # True - type INHERITS from object
print(isinstance(object, type))    # True - object IS a type
print(type(object))                # <class 'type'>
print(type(type))                  # <class 'type'> (circular!)
```

## 13.2 `PyObject` Structure

Every Python object starts with a common structure:

```c
// Include/object.h - Simplified

// Basic object header
typedef struct _object {
    Py_ssize_t ob_refcnt;  // Reference count
    PyTypeObject *ob_type;  // Pointer to type object
} PyObject;

// Variable-size objects (lists, tuples, etc.)
typedef struct {
    PyObject ob_base;
    Py_ssize_t ob_size;    // Number of items
} PyVarObject;
```

### Memory Layout

```
┌─────────────────────────────────────────────────────────────────┐
│                    PyObject Memory Layout                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Basic Object (e.g., int):                                       │
│  ┌────────────────┬────────────────┬────────────────────┐       │
│  │   ob_refcnt    │    ob_type     │   object data      │       │
│  │   (8 bytes)    │   (8 bytes)    │   (varies)         │       │
│  └────────────────┴────────────────┴────────────────────┘       │
│                                                                  │
│  Variable Object (e.g., list):                                   │
│  ┌────────────────┬────────────────┬────────────┬───────────┐   │
│  │   ob_refcnt    │    ob_type     │  ob_size   │  items    │   │
│  │   (8 bytes)    │   (8 bytes)    │ (8 bytes)  │  (varies) │   │
│  └────────────────┴────────────────┴────────────┴───────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 13.3 `PyObject_HEAD` Macro

The `PyObject_HEAD` macro defines the common object header:

```c
// Include/object.h

#define PyObject_HEAD  PyObject ob_base;

#define PyObject_VAR_HEAD  PyVarObject ob_base;

// Example: Integer object structure
typedef struct {
    PyObject_HEAD
    // ob_digit contains the actual integer value
    digit ob_digit[1];  // Variable length array
} PyLongObject;

// Example: List object structure
typedef struct {
    PyObject_VAR_HEAD
    PyObject **ob_item;  // Array of pointers to items
    Py_ssize_t allocated;  // Allocated size
} PyListObject;
```

### Accessing Common Fields

```c
// Macros to access header fields
#define Py_REFCNT(ob)  (((PyObject*)(ob))->ob_refcnt)
#define Py_TYPE(ob)    (((PyObject*)(ob))->ob_type)
#define Py_SIZE(ob)    (((PyVarObject*)(ob))->ob_size)
```

## 13.4 `PyVarObject` for Variable-Size Objects

Objects with variable amounts of data use `PyVarObject`:

```python
import sys

# Fixed-size objects
print(sys.getsizeof(1))        # 28 bytes (small int)
print(sys.getsizeof(1.0))      # 24 bytes

# Variable-size objects - size depends on content
print(sys.getsizeof(""))       # 49 bytes (empty string)
print(sys.getsizeof("a" * 10)) # 59 bytes
print(sys.getsizeof("a" * 100)) # 149 bytes

print(sys.getsizeof([]))       # 56 bytes (empty list)
print(sys.getsizeof([1,2,3]))  # 88 bytes
```

### Variable Object Types

| Type | Variable Part |
|------|---------------|
| `str` | Character data |
| `bytes` | Byte data |
| `list` | Item pointers |
| `tuple` | Item pointers |
| `dict` | Hash table |
| `int` | Digit array (arbitrary precision) |

## 13.5 Object Identity (`id()` and `is`)

### The `id()` Function

```python
x = [1, 2, 3]
y = x
z = [1, 2, 3]

# id() returns the memory address (in CPython)
print(id(x))  # e.g., 140234567890
print(id(y))  # Same as x (same object)
print(id(z))  # Different (different object)

# is checks identity (same object)
print(x is y)  # True
print(x is z)  # False

# == checks equality (same value)
print(x == z)  # True
```

### Identity and Interning

```python
# Small integers are interned (cached)
a = 256
b = 256
print(a is b)  # True - same object!

a = 257
b = 257
print(a is b)  # False - different objects (outside cache range)

# But in the REPL or same code block, it might be True due to compiler optimization

# Short strings are also interned
s1 = "hello"
s2 = "hello"
print(s1 is s2)  # True (likely)

# Force interning
import sys
s3 = sys.intern("a" * 1000)
s4 = sys.intern("a" * 1000)
print(s3 is s4)  # True (forced interning)
```

### `id()` in CPython

```python
# In CPython, id() returns the memory address
x = object()
print(hex(id(x)))  # e.g., '0x7f8b8c0a1234'

# This is implementation-specific!
# Other implementations may not use memory addresses
```

## 13.6 Object Lifetime

### Object Creation

```python
# Object creation involves:
# 1. Memory allocation
# 2. Type assignment
# 3. Reference count = 1
# 4. Initialization (__init__)

class Example:
    def __new__(cls):
        print("1. __new__ called - allocating")
        instance = super().__new__(cls)
        print(f"   Reference count: {sys.getrefcount(instance) - 1}")
        return instance

    def __init__(self):
        print("2. __init__ called - initializing")

import sys
obj = Example()
print(f"3. Final reference count: {sys.getrefcount(obj) - 1}")
```

### Reference Count Changes

```python
import sys

x = [1, 2, 3]
print(sys.getrefcount(x) - 1)  # 1 (minus 1 for getrefcount's own reference)

y = x  # Another reference
print(sys.getrefcount(x) - 1)  # 2

del y  # Remove reference
print(sys.getrefcount(x) - 1)  # 1

# When count reaches 0, object is deallocated
```

### Object Destruction

```python
class Example:
    def __del__(self):
        print("Object being destroyed")

obj = Example()
obj = None  # Triggers __del__ (usually)
# Output: "Object being destroyed"

# Warning: __del__ timing is not guaranteed
# Circular references may delay or prevent __del__
```

## Inspecting Objects

### Using `dir()` and `vars()`

```python
class Person:
    species = "human"

    def __init__(self, name):
        self.name = name

p = Person("Alice")

# dir() - all attributes (including inherited)
print(dir(p))

# vars() - instance __dict__ only
print(vars(p))  # {'name': 'Alice'}

# __dict__ access
print(p.__dict__)  # {'name': 'Alice'}
print(Person.__dict__)  # Class attributes
```

### Object Inspection Functions

```python
import inspect

def example(x, y=10):
    """An example function."""
    return x + y

# Function inspection
print(inspect.signature(example))  # (x, y=10)
print(inspect.getsource(example))  # Source code
print(inspect.getfile(example))    # File location

# Object type checking
print(inspect.isfunction(example))  # True
print(inspect.ismethod(example))    # False
print(inspect.isclass(Person))      # True
```

## Summary

- **Everything in Python is an object** with type and identity
- **`PyObject`** is the common structure for all objects
- **`ob_refcnt`** tracks references for memory management
- **`ob_type`** points to the object's type
- **`id()`** returns object identity (memory address in CPython)
- **`is`** checks identity, **`==`** checks equality
- Object lifetime: creation → use → destruction (when refcount = 0)

## Practice Exercises

1. Use `sys.getrefcount()` to trace reference count changes
2. Explore the `__dict__` of various object types
3. Investigate which objects are interned by default
4. Create a class that logs all lifecycle events (`__new__`, `__init__`, `__del__`)

---

[← Previous: Function Calls](../part-03-virtual-machine/chapter-12-function-calls.md) | [Next: Type System →](chapter-14-type-system.md)

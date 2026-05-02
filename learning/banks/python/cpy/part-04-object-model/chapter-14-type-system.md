# Chapter 14: Type System

## 14.1 `PyTypeObject` Structure

Every type in Python is represented by a `PyTypeObject`:

```c
// Simplified PyTypeObject structure (Include/cpython/object.h)
typedef struct _typeobject {
    PyObject_VAR_HEAD
    const char *tp_name;           // Type name ("int", "list", etc.)
    Py_ssize_t tp_basicsize;       // Size for allocation
    Py_ssize_t tp_itemsize;        // Size per item (for var objects)

    // Methods
    destructor tp_dealloc;         // Destructor
    reprfunc tp_repr;              // __repr__
    PyNumberMethods *tp_as_number; // Numeric operations
    PySequenceMethods *tp_as_sequence; // Sequence operations
    PyMappingMethods *tp_as_mapping;   // Mapping operations

    hashfunc tp_hash;              // __hash__
    ternaryfunc tp_call;           // __call__
    reprfunc tp_str;               // __str__

    getattrofunc tp_getattro;      // __getattribute__
    setattrofunc tp_setattro;      // __setattr__

    // More slots...
    PyObject *tp_dict;             // Type's __dict__
    descrgetfunc tp_descr_get;     // Descriptor __get__
    descrsetfunc tp_descr_set;     // Descriptor __set__

    initproc tp_init;              // __init__
    allocfunc tp_alloc;            // Allocator
    newfunc tp_new;                // __new__

    PyObject *tp_bases;            // Base classes tuple
    PyObject *tp_mro;              // Method Resolution Order
    // ... and more
} PyTypeObject;
```

### Type Object Visualization

```
┌─────────────────────────────────────────────────────────────────┐
│                    PyTypeObject Layout                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  PyObject_VAR_HEAD (refcount, type, size)              │     │
│  ├────────────────────────────────────────────────────────┤     │
│  │  tp_name = "MyClass"                                   │     │
│  │  tp_basicsize = 48                                     │     │
│  │  tp_itemsize = 0                                       │     │
│  ├────────────────────────────────────────────────────────┤     │
│  │  tp_dealloc = my_dealloc_func                         │     │
│  │  tp_repr = my_repr_func                               │     │
│  │  tp_hash = my_hash_func                               │     │
│  │  ...                                                   │     │
│  ├────────────────────────────────────────────────────────┤     │
│  │  tp_dict = {...}  (class attributes)                   │     │
│  │  tp_bases = (BaseClass,)                              │     │
│  │  tp_mro = (MyClass, BaseClass, object)                │     │
│  └────────────────────────────────────────────────────────┘     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 14.2 Type Slots and Slot Functions

Type slots are function pointers that define type behavior:

### 14.2.1 `tp_new` - Allocation

```python
class Example:
    def __new__(cls, *args, **kwargs):
        print("__new__ called - allocating memory")
        instance = super().__new__(cls)
        return instance

    def __init__(self, value):
        print("__init__ called - initializing")
        self.value = value

obj = Example(42)
# Output:
# __new__ called - allocating memory
# __init__ called - initializing
```

### 14.2.2 `tp_init` - Initialization

```python
# __init__ corresponds to tp_init
class Counter:
    def __init__(self, start=0):
        self.count = start

# tp_init is called after tp_new
c = Counter(10)
print(c.count)  # 10
```

### 14.2.3 `tp_dealloc` - Destruction

```python
class Example:
    def __del__(self):
        print("Object destroyed")

obj = Example()
del obj  # Triggers tp_dealloc → __del__
```

### 14.2.4 `tp_repr` and `tp_str`

```python
class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __repr__(self):
        return f"Point({self.x}, {self.y})"

    def __str__(self):
        return f"({self.x}, {self.y})"

p = Point(3, 4)
print(repr(p))  # Point(3, 4)  - tp_repr
print(str(p))   # (3, 4)       - tp_str
print(p)        # (3, 4)       - uses __str__ if available
```

### 14.2.5 `tp_hash` and `tp_richcompare`

```python
class Item:
    def __init__(self, value):
        self.value = value

    def __hash__(self):
        return hash(self.value)

    def __eq__(self, other):
        if isinstance(other, Item):
            return self.value == other.value
        return NotImplemented

    def __lt__(self, other):
        if isinstance(other, Item):
            return self.value < other.value
        return NotImplemented

items = {Item(1), Item(2), Item(1)}  # Uses __hash__ and __eq__
print(len(items))  # 2 (Item(1) appears once)
```

### 14.2.6 `tp_call` - Callable Objects

```python
class Adder:
    def __init__(self, amount):
        self.amount = amount

    def __call__(self, x):
        return x + self.amount

add5 = Adder(5)
print(add5(10))  # 15 - tp_call invoked
print(callable(add5))  # True
```

### 14.2.7 `tp_getattro` and `tp_setattro`

```python
class Tracked:
    def __getattribute__(self, name):
        print(f"Getting: {name}")
        return super().__getattribute__(name)

    def __setattr__(self, name, value):
        print(f"Setting: {name} = {value}")
        super().__setattr__(name, value)

obj = Tracked()
obj.x = 10  # Setting: x = 10
print(obj.x)  # Getting: x, then 10
```

## 14.3 Heap Types vs Static Types

### Static Types

Built-in types are defined statically in C:

```c
// Example: int type (Objects/longobject.c)
PyTypeObject PyLong_Type = {
    PyVarObject_HEAD_INIT(&PyType_Type, 0)
    "int",                              /* tp_name */
    offsetof(PyLongObject, ob_digit),   /* tp_basicsize */
    sizeof(digit),                      /* tp_itemsize */
    // ... more initializations
};
```

### Heap Types

User-defined classes are heap types:

```python
# This creates a heap type
class MyClass:
    pass

# Check if it's a heap type
import sys
print(type(MyClass).__flags__ & 0x200)  # Heap type flag

# Heap types can be modified
MyClass.new_attr = 42  # OK

# Static types cannot (usually)
# int.new_attr = 42  # TypeError
```

### Differences

| Feature | Static Type | Heap Type |
|---------|-------------|-----------|
| Defined in | C code | Python code |
| Allocated | Data segment | Heap |
| Mutable | Limited | Yes |
| Reference counted | No | Yes |
| Examples | `int`, `str`, `list` | User classes |

## 14.4 Type Inheritance and MRO

### Method Resolution Order

```python
class A:
    def method(self):
        return "A"

class B(A):
    def method(self):
        return "B"

class C(A):
    def method(self):
        return "C"

class D(B, C):
    pass

# MRO determines method lookup order
print(D.__mro__)
# (<class 'D'>, <class 'B'>, <class 'C'>, <class 'A'>, <class 'object'>)

d = D()
print(d.method())  # "B" - B is before C in MRO
```

### Visualizing MRO

```
┌─────────────────────────────────────────────────────────────────┐
│                    Diamond Inheritance                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│                     object                                       │
│                        │                                         │
│                        A                                         │
│                       / \                                        │
│                      B   C                                       │
│                       \ /                                        │
│                        D                                         │
│                                                                  │
│  MRO: D → B → C → A → object                                    │
│  (C3 linearization ensures consistent order)                    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 14.5 C3 Linearization Algorithm

C3 linearization ensures:
1. Children come before parents
2. Order of parents is preserved
3. Consistent ordering

```python
# C3 algorithm in action
class A: pass
class B(A): pass
class C(A): pass
class D(B, C): pass

# D's MRO is computed as:
# 1. Start with D
# 2. Merge: [B, A, object] + [C, A, object] + [B, C]
# 3. Take heads that don't appear in tails
# Result: D, B, C, A, object

print(D.__mro__)
```

### Invalid MRO

```python
# Some inheritance patterns are impossible
class A: pass
class B(A): pass
class C(A, B): pass  # Error! Cannot create consistent MRO

# TypeError: Cannot create a consistent method resolution order (MRO)
```

## 14.6 Metaclasses Internally

### What is a Metaclass?

```python
# type is the default metaclass
class Regular:
    pass

print(type(Regular))  # <class 'type'>

# Custom metaclass
class Meta(type):
    def __new__(mcs, name, bases, namespace):
        print(f"Creating class: {name}")
        return super().__new__(mcs, name, bases, namespace)

class MyClass(metaclass=Meta):
    pass
# Output: Creating class: MyClass
```

### Metaclass Hierarchy

```
┌─────────────────────────────────────────────────────────────────┐
│                    Metaclass Relationship                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Instance ─────────────────▶ Class ─────────────────▶ Metaclass │
│  (object)      type of       (type)      type of      (type)    │
│                                                                  │
│  Example:                                                        │
│  42 ──────────────────────▶ int ────────────────────▶ type      │
│  MyClass() ───────────────▶ MyClass ────────────────▶ Meta      │
│                                                                  │
│  type is its own metaclass:                                      │
│  type ────────────────────▶ type                                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Using Metaclasses

```python
class SingletonMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]

class Singleton(metaclass=SingletonMeta):
    pass

a = Singleton()
b = Singleton()
print(a is b)  # True - same instance
```

## Type Creation Process

```
┌─────────────────────────────────────────────────────────────────┐
│                   Class Creation Steps                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  class MyClass(Base):                                            │
│      x = 1                                                       │
│                                                                  │
│  1. Determine metaclass                                          │
│     - From metaclass= argument                                  │
│     - From base classes                                          │
│     - Default: type                                              │
│                                                                  │
│  2. Prepare namespace                                            │
│     - metaclass.__prepare__(name, bases)                        │
│     - Usually returns empty dict                                │
│                                                                  │
│  3. Execute class body                                           │
│     - In prepared namespace                                      │
│     - Sets up class attributes                                   │
│                                                                  │
│  4. Create class object                                          │
│     - metaclass(name, bases, namespace)                         │
│     - Calls metaclass.__new__ then __init__                     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Summary

- **`PyTypeObject`** defines type behavior through slots
- **Type slots** are function pointers for operations
- **Static types** (built-ins) vs **heap types** (user classes)
- **MRO** determines method lookup order (C3 linearization)
- **Metaclasses** control class creation

## Practice Exercises

1. Implement a class with all special methods (`__repr__`, `__hash__`, etc.)
2. Create a metaclass that adds automatic property getters
3. Draw the MRO for a complex inheritance hierarchy
4. Explore `type.__dict__` to see available type slots

---

[← Previous: Object Fundamentals](chapter-13-object-fundamentals.md) | [Next: Descriptor Protocol →](chapter-15-descriptor-protocol.md)

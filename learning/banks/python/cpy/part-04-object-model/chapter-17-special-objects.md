# Chapter 17: Special Objects

## 17.1 None, True, False (Singletons)

Python has exactly one instance of `None`, `True`, and `False`:

```python
# None is a singleton
a = None
b = None
print(a is b)  # True - always the same object

# True and False are singletons
print(True is True)    # True
print(False is False)  # True

# Check identity
print(id(None))   # Always same address
print(id(True))   # Always same address
print(id(False))  # Always same address
```

### NoneType Implementation

```c
// Objects/object.c
PyObject _Py_NoneStruct = {
    _PyObject_EXTRA_INIT
    1, &_PyNone_Type  // Immortal, type is NoneType
};
```

### None Usage Patterns

```python
# None is often used as:
# 1. Default argument sentinel
def func(x=None):
    if x is None:
        x = []
    return x

# 2. Missing value indicator
result = cache.get('key')  # Returns None if missing

# 3. Explicit "no value" return
def no_return():
    pass  # Implicitly returns None

print(no_return())  # None
```

## 17.2 Ellipsis

The `Ellipsis` object (`...`) is also a singleton:

```python
# Ellipsis singleton
print(... is ...)  # True
print(type(...))   # <class 'ellipsis'>
print(...)         # Ellipsis

# Uses of Ellipsis
# 1. Type hints for variable-length tuples
from typing import Tuple
Vector = Tuple[float, ...]  # Any number of floats

# 2. NumPy multi-dimensional slicing
import numpy as np
arr = np.zeros((3, 4, 5))
print(arr[..., 0].shape)  # Select all but last dimension

# 3. Placeholder in stubs
def not_implemented_yet():
    ...  # Pass would work, but ... indicates "to be filled"
```

## 17.3 NotImplemented

`NotImplemented` signals that an operation isn't supported:

```python
class Vector:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __add__(self, other):
        if isinstance(other, Vector):
            return Vector(self.x + other.x, self.y + other.y)
        return NotImplemented  # Let other operand try

    def __radd__(self, other):
        return self.__add__(other)

v = Vector(1, 2)
result = v + "string"  # Vector returns NotImplemented
# Python then tries "string".__radd__(v)
# Which fails → TypeError
```

### NotImplemented vs NotImplementedError

```python
# NotImplemented: Return value for operators
def __add__(self, other):
    return NotImplemented  # "I can't handle this, try the other side"

# NotImplementedError: Exception for abstract methods
def abstract_method(self):
    raise NotImplementedError("Subclass must implement")
```

## 17.4 Module Objects

Modules are first-class objects:

```python
import sys
import math

# Module attributes
print(math.__name__)      # 'math'
print(math.__file__)      # '/path/to/math.cpython-312-darwin.so'
print(math.__doc__[:50])  # Documentation
print(type(math))         # <class 'module'>

# Module __dict__ contains all module attributes
print('pi' in math.__dict__)  # True

# Create module dynamically
import types
my_module = types.ModuleType('my_module')
my_module.x = 42
sys.modules['my_module'] = my_module

import my_module
print(my_module.x)  # 42
```

### Module State

```python
# sys.modules is the module cache
import sys
print('os' in sys.modules)  # True if os was imported

# Reloading modules
import importlib
import my_module
importlib.reload(my_module)  # Re-execute module code
```

## 17.5 Code Objects

Code objects contain compiled bytecode:

```python
def example(x, y):
    """Add two numbers."""
    return x + y

code = example.__code__

# Code object attributes
print(code.co_name)        # 'example'
print(code.co_filename)    # Source file
print(code.co_firstlineno) # First line number
print(code.co_argcount)    # 2 (x and y)
print(code.co_varnames)    # ('x', 'y')
print(code.co_consts)      # (None, 'Add two numbers.')
print(code.co_code)        # Bytecode bytes

# Disassemble
import dis
dis.dis(code)
```

### Creating Code Objects

```python
# Compile source to code object
code = compile('x + y', '<string>', 'eval')
print(type(code))  # <class 'code'>

# Execute code object
result = eval(code, {'x': 1, 'y': 2})
print(result)  # 3
```

## 17.6 Function Objects

Functions are objects with callable behavior:

```python
def greet(name, greeting="Hello"):
    """Greet someone."""
    return f"{greeting}, {name}!"

# Function attributes
print(greet.__name__)        # 'greet'
print(greet.__qualname__)    # 'greet'
print(greet.__doc__)         # 'Greet someone.'
print(greet.__module__)      # '__main__'
print(greet.__defaults__)    # ('Hello',)
print(greet.__code__)        # <code object>
print(greet.__globals__)     # Global namespace dict
print(greet.__annotations__) # {} (no annotations)

# Closure info
def outer():
    x = 1
    def inner():
        return x
    return inner

closure = outer()
print(closure.__closure__)        # (<cell ...>,)
print(closure.__closure__[0].cell_contents)  # 1
```

### Lambda Functions

```python
# Lambdas are functions too
f = lambda x: x * 2
print(type(f))         # <class 'function'>
print(f.__name__)      # '<lambda>'
print(f.__code__.co_varnames)  # ('x',)
```

## 17.7 Method Objects (Bound/Unbound)

### Bound Methods

```python
class Example:
    def method(self, x):
        return self, x

obj = Example()

# Bound method - self is already set
bound = obj.method
print(type(bound))    # <class 'method'>
print(bound.__self__) # <Example object>
print(bound.__func__) # <function Example.method>

# Call bound method
result = bound(10)  # self is automatically passed
```

### Method Internals

```python
# Methods are created on attribute access
class MyClass:
    def method(self):
        pass

obj = MyClass()

# Each access creates a new method object
m1 = obj.method
m2 = obj.method
print(m1 is m2)  # False - different method objects
print(m1 == m2)  # True - but equal

# The underlying function is the same
print(m1.__func__ is m2.__func__)  # True
```

## 17.8 Generator Objects

Generators are special iterators:

```python
def countdown(n):
    while n > 0:
        yield n
        n -= 1

gen = countdown(3)

# Generator attributes
print(type(gen))              # <class 'generator'>
print(gen.__name__)           # 'countdown'
print(gen.gi_frame)           # Frame object
print(gen.gi_frame.f_locals)  # {'n': 3}
print(gen.gi_code)            # Code object

# Iteration
print(next(gen))  # 3
print(gen.gi_frame.f_locals)  # {'n': 2}
print(next(gen))  # 2
print(next(gen))  # 1
# next(gen)  # StopIteration
```

### Generator State

```python
def example():
    yield 1
    yield 2

gen = example()

# Check state
import inspect
print(inspect.getgeneratorstate(gen))  # GEN_CREATED
next(gen)
print(inspect.getgeneratorstate(gen))  # GEN_SUSPENDED
list(gen)  # Exhaust
print(inspect.getgeneratorstate(gen))  # GEN_CLOSED
```

## 17.9 Coroutine Objects

Coroutines are similar to generators but for async:

```python
async def async_example():
    await some_async_function()
    return 42

coro = async_example()

# Coroutine attributes
print(type(coro))       # <class 'coroutine'>
print(coro.cr_frame)    # Frame object
print(coro.cr_code)     # Code object

# Must be awaited or closed
coro.close()  # Prevent "coroutine never awaited" warning
```

## Special Object Comparison

| Object | Singleton? | Hashable? | Callable? |
|--------|-----------|-----------|-----------|
| None | Yes | Yes | No |
| True/False | Yes | Yes | No |
| Ellipsis | Yes | Yes | No |
| NotImplemented | Yes | Yes | No |
| Module | No | No | No |
| Function | No | Yes | Yes |
| Method | No | Yes | Yes |
| Code | No | Yes | No |
| Generator | No | Yes | No |
| Coroutine | No | Yes | No |

## Summary

- **None, True, False, Ellipsis, NotImplemented** are singletons
- **NotImplemented** signals "try the other operand"
- **Modules** are objects with `__dict__` namespaces
- **Code objects** contain compiled bytecode
- **Functions** have code, globals, defaults, closures
- **Methods** bind functions to instances
- **Generators/Coroutines** maintain suspended execution state

## Practice Exercises

1. Explore all attributes of a function object
2. Create a module dynamically and import it
3. Inspect a generator's frame as it executes
4. Compare method objects created from the same function

---

[← Previous: Built-in Types Internals](chapter-16-builtin-types.md) | [Next: Memory Architecture →](../part-05-memory-management/chapter-18-memory-architecture.md)

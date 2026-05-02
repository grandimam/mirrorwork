# Chapter 11: Namespaces and Scopes

## 11.1 LEGB Rule (Local, Enclosing, Global, Built-in)

Python uses the LEGB rule to resolve names:

```
┌─────────────────────────────────────────────────────────────────┐
│                        LEGB Lookup Order                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Name lookup proceeds in this order:                             │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  L - Local        Function's local scope                 │    │
│  │                   (fastest lookup: LOAD_FAST)            │    │
│  └──────────────────────────┬──────────────────────────────┘    │
│                             │ not found                          │
│                             ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  E - Enclosing    Enclosing function's scope (closures) │    │
│  │                   (LOAD_DEREF)                           │    │
│  └──────────────────────────┬──────────────────────────────┘    │
│                             │ not found                          │
│                             ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  G - Global       Module-level scope                     │    │
│  │                   (LOAD_GLOBAL - checks globals dict)    │    │
│  └──────────────────────────┬──────────────────────────────┘    │
│                             │ not found                          │
│                             ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  B - Built-in     Python's built-in namespace            │    │
│  │                   (LOAD_GLOBAL - checks builtins dict)   │    │
│  └──────────────────────────┬──────────────────────────────┘    │
│                             │ not found                          │
│                             ▼                                    │
│                      NameError raised                            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### LEGB Example

```python
# Built-in scope
# len, print, etc. are here

# Global scope
x = "global"

def outer():
    # Enclosing scope
    x = "enclosing"

    def inner():
        # Local scope
        x = "local"
        print(x)  # "local" - found in L

    def inner2():
        print(x)  # "enclosing" - found in E

    inner()
    inner2()

outer()
print(x)  # "global" - found in G
print(len)  # <built-in function len> - found in B
```

## 11.2 Namespace Dictionaries

Namespaces are implemented as dictionaries:

### Accessing Namespaces

```python
# Global namespace
print(globals())  # Returns module's __dict__

# Local namespace
def example():
    x = 1
    y = 2
    print(locals())  # {'x': 1, 'y': 2}

example()

# Built-in namespace
import builtins
print(dir(builtins))  # All built-in names
```

### Namespace Hierarchy

```python
def show_namespaces():
    local_var = "I'm local"

    print("Local namespace:", locals())
    print("Global namespace has", len(globals()), "items")
    print("Builtins namespace has", len(dir(__builtins__)), "items")

show_namespaces()
```

### Modifying Namespaces

```python
# Modifying globals works
def modify_global():
    globals()['new_var'] = 42

modify_global()
print(new_var)  # 42

# Modifying locals() doesn't work reliably
def modify_local():
    x = 1
    locals()['x'] = 999  # This doesn't work!
    print(x)  # Still 1

modify_local()
```

## 11.3 `globals()` and `locals()` Internals

### `globals()`

```python
# globals() returns the module's actual __dict__
import sys

current_module = sys.modules[__name__]
print(globals() is current_module.__dict__)  # True

# Changes to globals() affect the module
globals()['dynamic_var'] = 100
print(dynamic_var)  # 100
```

### `locals()`

```python
# locals() behavior differs by context

# At module level: same as globals()
print(locals() is globals())  # True (at module level)

# In a function: returns a snapshot
def example():
    x = 1
    snapshot = locals()
    x = 2
    print(snapshot)  # {'x': 1} - snapshot, not live
    print(locals())  # {'x': 2, 'snapshot': {...}}

example()

# In a class body: returns the class namespace being built
class Example:
    x = 1
    print(locals())  # {'__module__': ..., '__qualname__': ..., 'x': 1}
```

### Why `locals()` Returns a Snapshot

```python
# Fast locals optimization means locals aren't in a dict
# locals() must build a dict from the fast locals array

import dis

def example():
    x = 1
    return x

dis.dis(example)
# LOAD_FAST 0 (x)  - Direct array access, no dict lookup
```

## 11.4 Closure Implementation

### How Closures Work

```python
def outer(x):
    def inner():
        return x  # x is a "free variable"
    return inner

closure = outer(10)
print(closure())  # 10

# The value is captured, not the variable name
```

### Cell Objects

```python
def outer():
    x = 10

    def inner():
        return x

    return inner

closure = outer()

# Inspect the closure
print(closure.__code__.co_freevars)  # ('x',)
print(closure.__closure__)  # (<cell at 0x...: int object at 0x...>,)
print(closure.__closure__[0].cell_contents)  # 10
```

### Closure Memory Model

```
┌─────────────────────────────────────────────────────────────────┐
│                     Closure Structure                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  def outer():                                                    │
│      x = 10        ───────▶  Cell Object                        │
│      def inner():            ┌─────────────────┐                │
│          return x  ◀─────────│ cell_contents ──┼──▶ 10          │
│      return inner            └─────────────────┘                │
│                                     ▲                            │
│  closure = outer()                  │                            │
│                              ┌──────┴──────┐                    │
│  closure.__closure__  ──────▶│ (cell, ...) │                    │
│                              └─────────────┘                    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 11.5 Cell Objects

Cell objects are the mechanism for sharing variables between scopes:

### Creating Cells

```python
def make_counter():
    count = 0  # This becomes a cell variable

    def increment():
        nonlocal count  # Access the cell
        count += 1
        return count

    def get():
        return count  # Read the cell

    return increment, get

inc, get = make_counter()
print(inc())  # 1
print(inc())  # 2
print(get())  # 2

# Both functions share the same cell
print(inc.__closure__[0] is get.__closure__[0])  # True
```

### Cell Variables vs Free Variables

```python
import dis

def outer():
    x = 1  # x is a CELL variable in outer

    def inner():
        return x  # x is a FREE variable in inner

    return inner

# Show variable classification
print(f"outer co_cellvars: {outer.__code__.co_cellvars}")  # ('x',)
print(f"outer co_freevars: {outer.__code__.co_freevars}")  # ()

inner = outer()
print(f"inner co_cellvars: {inner.__code__.co_cellvars}")  # ()
print(f"inner co_freevars: {inner.__code__.co_freevars}")  # ('x',)
```

### Bytecode for Closures

```python
import dis

def outer():
    x = 1
    def inner():
        return x
    return inner

print("outer bytecode:")
dis.dis(outer)
# MAKE_CELL 0 (x)         - Create cell for x
# LOAD_CONST 1 (1)
# STORE_DEREF 0 (x)       - Store in cell
# LOAD_CLOSURE 0 (x)      - Load cell reference
# BUILD_TUPLE 1           - For inner's closure
# LOAD_CONST 2 (<code>)
# MAKE_FUNCTION 8         - With closure

print("\ninner bytecode:")
dis.dis(outer())
# LOAD_DEREF 0 (x)        - Load from cell (free variable)
# RETURN_VALUE
```

## 11.6 `nonlocal` and `global` Statements

### `global` Statement

```python
x = 1  # Global variable

def modify_global():
    global x  # Declare intent to modify global
    x = 2

def read_global():
    print(x)  # Reading doesn't need declaration

modify_global()
print(x)  # 2

# Without global, assignment creates local
def create_local():
    x = 3  # Creates new local, doesn't affect global

create_local()
print(x)  # Still 2
```

### `nonlocal` Statement

```python
def outer():
    x = 1

    def inner():
        nonlocal x  # Modify enclosing scope's x
        x = 2

    inner()
    print(x)  # 2

outer()

# nonlocal vs global
y = 10

def outer2():
    y = 20

    def inner():
        nonlocal y  # Refers to outer2's y (20), not global y (10)
        y = 30

    inner()
    print(f"outer2's y: {y}")  # 30

outer2()
print(f"global y: {y}")  # 10 (unchanged)
```

### Scope Declaration Bytecode

```python
import dis

x = 1

def example():
    global x
    x = 2

dis.dis(example)
# LOAD_CONST 1 (2)
# STORE_GLOBAL 0 (x)  - Uses STORE_GLOBAL, not STORE_FAST

def outer():
    y = 1
    def inner():
        nonlocal y
        y = 2
    return inner

dis.dis(outer())
# LOAD_CONST 1 (2)
# STORE_DEREF 0 (y)  - Uses STORE_DEREF for cell variable
```

## Scope Determination at Compile Time

```python
# Scope is determined at compile time, not runtime

x = "global"

def example():
    print(x)  # This would print "global" if next line didn't exist
    x = "local"  # This makes x local for the ENTIRE function

# UnboundLocalError: local variable 'x' referenced before assignment
# example()

# The compiler sees 'x = ...' and marks x as local
import dis
dis.dis(example)
# LOAD_FAST 0 (x)  - Tries to load LOCAL x (which isn't set yet)
```

## Summary

- **LEGB** rule defines name resolution order
- **Namespaces** are dictionaries mapping names to objects
- **`globals()`** returns module's actual dict
- **`locals()`** returns a snapshot (in functions)
- **Cell objects** enable closures
- **`global`** and **`nonlocal`** control scope binding
- Scope is determined at **compile time**

## Practice Exercises

1. Create a closure that maintains a private counter
2. Write a decorator that adds variables to the decorated function's scope
3. Demonstrate the difference between global/nonlocal with nested functions
4. Use `dis` to show how different scopes use different bytecode instructions

---

[← Previous: Frame Objects](chapter-10-frame-objects.md) | [Next: Function Calls →](chapter-12-function-calls.md)

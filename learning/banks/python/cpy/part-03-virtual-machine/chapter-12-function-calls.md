# Chapter 12: Function Calls

## 12.1 Call Stack Mechanics

When a function is called, Python performs several steps:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Function Call Sequence                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Evaluate callable and arguments                              │
│     │                                                            │
│     ▼                                                            │
│  2. Create new frame object                                      │
│     - Link to caller frame (f_back)                              │
│     - Set code object                                            │
│     - Initialize namespaces                                      │
│     │                                                            │
│     ▼                                                            │
│  3. Bind arguments to parameters                                 │
│     - Positional args → parameters                              │
│     - Keyword args → named parameters                           │
│     - Apply defaults                                             │
│     │                                                            │
│     ▼                                                            │
│  4. Push frame onto call stack                                   │
│     │                                                            │
│     ▼                                                            │
│  5. Execute function body                                        │
│     │                                                            │
│     ▼                                                            │
│  6. Return value (or raise exception)                           │
│     │                                                            │
│     ▼                                                            │
│  7. Pop frame from stack                                         │
│     │                                                            │
│     ▼                                                            │
│  8. Resume caller with return value                             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Call Stack Visualization

```python
import traceback

def level1():
    level2()

def level2():
    level3()

def level3():
    # Print the call stack
    traceback.print_stack()

level1()
```

Output:
```
  File "example.py", line 14, in <module>
    level1()
  File "example.py", line 4, in level1
    level2()
  File "example.py", line 7, in level2
    level3()
  File "example.py", line 11, in level3
    traceback.print_stack()
```

## 12.2 Argument Passing

### Positional Arguments

```python
import dis

def func(a, b, c):
    return a + b + c

# Call bytecode
dis.dis(compile("func(1, 2, 3)", "", "eval"))
# PUSH_NULL
# LOAD_NAME 0 (func)
# LOAD_CONST 0 (1)
# LOAD_CONST 1 (2)
# LOAD_CONST 2 (3)
# CALL 3
```

### Keyword Arguments

```python
import dis

dis.dis(compile("func(a=1, b=2, c=3)", "", "eval"))
# PUSH_NULL
# LOAD_NAME 0 (func)
# LOAD_CONST 0 (1)
# LOAD_CONST 1 (2)
# LOAD_CONST 2 (3)
# KW_NAMES (('a', 'b', 'c'))  # Tuple of keyword names
# CALL 3
```

### `*args` and `**kwargs`

```python
def variadic(*args, **kwargs):
    print(f"args: {args}")
    print(f"kwargs: {kwargs}")

variadic(1, 2, 3, x=10, y=20)
# args: (1, 2, 3)
# kwargs: {'x': 10, 'y': 20}
```

### Unpacking Arguments

```python
import dis

dis.dis(compile("func(*args)", "", "eval"))
# PUSH_NULL
# LOAD_NAME 0 (func)
# LOAD_NAME 1 (args)
# CALL_FUNCTION_EX 0  # Unpack args

dis.dis(compile("func(**kwargs)", "", "eval"))
# PUSH_NULL
# LOAD_NAME 0 (func)
# BUILD_TUPLE 0
# LOAD_NAME 1 (kwargs)
# CALL_FUNCTION_EX 1  # Unpack kwargs
```

## 12.3 Default Argument Evaluation

Default arguments are evaluated once, at function definition time:

```python
# DANGER: Mutable default argument
def append_to(item, target=[]):
    target.append(item)
    return target

print(append_to(1))  # [1]
print(append_to(2))  # [1, 2] - Same list!
print(append_to(3))  # [1, 2, 3] - Still same list!

# The default [] is stored in the function object
print(append_to.__defaults__)  # ([1, 2, 3],)
```

### Correct Pattern for Mutable Defaults

```python
def append_to(item, target=None):
    if target is None:
        target = []  # Create new list each call
    target.append(item)
    return target

print(append_to(1))  # [1]
print(append_to(2))  # [2]
print(append_to(3))  # [3]
```

### When Defaults Are Created

```python
import dis

def create_func():
    def example(x, y=[], z={}):
        pass
    return example

dis.dis(create_func)
# BUILD_LIST 0          # Create default []
# BUILD_MAP 0           # Create default {}
# BUILD_TUPLE 2         # Package defaults
# ... MAKE_FUNCTION ... # Store in function
```

### Default Storage

```python
def func(a, b=10, c="hello"):
    pass

print(func.__defaults__)     # (10, 'hello')
print(func.__kwdefaults__)   # None (for kw-only defaults)

def func2(a, *, b=10, c="hello"):
    pass

print(func2.__defaults__)    # None
print(func2.__kwdefaults__)  # {'b': 10, 'c': 'hello'}
```

## 12.4 Vectorcall Protocol (PEP 590)

Python 3.9+ uses the vectorcall protocol for faster function calls:

### Traditional Call vs Vectorcall

```
┌─────────────────────────────────────────────────────────────────┐
│                Traditional vs Vectorcall                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Traditional (tp_call):                                          │
│  1. Create tuple for positional args                             │
│  2. Create dict for keyword args                                 │
│  3. Call function                                                │
│  4. Destroy tuple and dict                                       │
│                                                                  │
│  Vectorcall:                                                     │
│  1. Pass args as C array (no tuple)                              │
│  2. Pass kwnames as tuple                                        │
│  3. Call function                                                │
│  (No intermediate objects created)                               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Vectorcall Signature

```c
// C signature for vectorcall
typedef PyObject *(*vectorcallfunc)(
    PyObject *callable,
    PyObject *const *args,    // Array of arguments
    size_t nargsf,            // Number of args + flags
    PyObject *kwnames         // Tuple of keyword names
);
```

### Checking Vectorcall Support

```python
# Check if a callable supports vectorcall
import sys

def example():
    pass

# Python 3.9+
print(hasattr(example, '__vectorcalloffset__'))  # True for functions
print(hasattr(len, '__vectorcalloffset__'))  # True for builtins
```

## 12.5 Tail Call Optimization (Lack Thereof)

Python does NOT implement tail call optimization:

```python
# This will cause stack overflow for large n
def factorial_recursive(n, accumulator=1):
    if n <= 1:
        return accumulator
    return factorial_recursive(n - 1, n * accumulator)  # Tail call

# factorial_recursive(10000)  # RecursionError!
```

### Why No TCO?

1. **Stack traces**: Python preserves full stack for debugging
2. **Dynamic nature**: Hard to determine tail calls statically
3. **Philosophy**: Guido prefers explicit loops

### Manual Tail Call Elimination

```python
def factorial_iterative(n):
    """Manually converted to iteration."""
    accumulator = 1
    while n > 1:
        accumulator *= n
        n -= 1
    return accumulator

print(factorial_iterative(10000))  # Works fine
```

### Trampoline Pattern

```python
class TailCall:
    def __init__(self, func, *args, **kwargs):
        self.func = func
        self.args = args
        self.kwargs = kwargs

def trampoline(func, *args, **kwargs):
    """Execute tail-recursive function without growing stack."""
    result = func(*args, **kwargs)
    while isinstance(result, TailCall):
        result = result.func(*result.args, **result.kwargs)
    return result

def factorial_tail(n, acc=1):
    if n <= 1:
        return acc
    return TailCall(factorial_tail, n - 1, n * acc)

print(trampoline(factorial_tail, 10000))  # Works!
```

## Function Object Internals

### Function Attributes

```python
def example(a, b, c=10):
    """A docstring."""
    x = a + b
    return x + c

# Code object
print(example.__code__)
print(example.__code__.co_varnames)  # ('a', 'b', 'c', 'x')

# Metadata
print(example.__name__)        # 'example'
print(example.__qualname__)    # 'example'
print(example.__doc__)         # 'A docstring.'
print(example.__module__)      # '__main__'

# Namespaces
print(type(example.__globals__))  # <class 'dict'>

# Defaults
print(example.__defaults__)    # (10,)

# Annotations
def typed(a: int, b: str) -> bool:
    pass
print(typed.__annotations__)   # {'a': <class 'int'>, 'b': <class 'str'>, 'return': <class 'bool'>}
```

### Creating Functions Dynamically

```python
import types

# Create a code object
code = compile("return x + y", "<dynamic>", "eval")

# Create a function from code
dynamic_func = types.FunctionType(
    code,           # Code object
    globals(),      # Global namespace
    "dynamic_func"  # Name
)

# This won't work as-is (return outside function)
# Let's do it properly:

source = """
def dynamic(x, y):
    return x + y
"""
exec(compile(source, "<dynamic>", "exec"))
print(dynamic(1, 2))  # 3
```

## Calling Conventions Summary

```
┌─────────────────────────────────────────────────────────────────┐
│                  Python Calling Conventions                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  def func(pos1, pos2, /, pos_or_kw, *, kw_only, **kwargs):      │
│           ▲    ▲        ▲              ▲         ▲               │
│           │    │        │              │         │               │
│           │    │        │              │         └─ Catch-all    │
│           │    │        │              │            keyword args │
│           │    │        │              │                         │
│           │    │        │              └─ Keyword-only           │
│           │    │        │                 (after *)              │
│           │    │        │                                        │
│           │    │        └─ Positional or keyword                │
│           │    │           (default)                             │
│           │    │                                                 │
│           └────┴─ Positional-only (before /)                    │
│                   Python 3.8+                                    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

```python
def example(pos_only, /, standard, *, kw_only):
    pass

example(1, 2, kw_only=3)         # Valid
example(1, standard=2, kw_only=3)  # Valid
# example(pos_only=1, ...)       # Invalid - pos_only is positional-only
# example(1, 2, 3)               # Invalid - kw_only is keyword-only
```

## Summary

- Function calls create frames and push to call stack
- Arguments are passed by object reference
- Default arguments are evaluated at definition time
- Vectorcall protocol (3.9+) speeds up calls
- Python lacks tail call optimization
- Function objects store code, defaults, and metadata

## Practice Exercises

1. Trace a function call's complete lifecycle with `sys.settrace`
2. Benchmark vectorcall vs traditional call for built-in functions
3. Implement the trampoline pattern for a recursive algorithm
4. Create a function dynamically using `types.FunctionType`

---

[← Previous: Namespaces and Scopes](chapter-11-namespaces-scopes.md) | [Next: Object Fundamentals →](../part-04-object-model/chapter-13-object-fundamentals.md)

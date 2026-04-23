# Chapter 10: Frame Objects

## 10.1 `PyFrameObject` Structure

Every function call creates a frame object that holds execution context:

```
┌─────────────────────────────────────────────────────────────────┐
│                      Frame Object Structure                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  PyFrameObject                                          │     │
│  ├────────────────────────────────────────────────────────┤     │
│  │  f_back          → Previous frame (caller)             │     │
│  │  f_code          → Code object being executed          │     │
│  │  f_builtins      → Builtins namespace                  │     │
│  │  f_globals       → Global namespace                    │     │
│  │  f_locals        → Local namespace (dict or NULL)      │     │
│  │  f_lasti         → Last instruction index              │     │
│  │  f_lineno        → Current line number                 │     │
│  │  f_trace         → Trace function                      │     │
│  │  f_localsplus    → Locals + cells + stack (array)      │     │
│  └────────────────────────────────────────────────────────┘     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Accessing Frame Information

```python
import sys

def outer():
    x = 1
    inner()

def inner():
    frame = sys._getframe()

    print(f"Function: {frame.f_code.co_name}")
    print(f"Line: {frame.f_lineno}")
    print(f"Locals: {frame.f_locals}")
    print(f"Globals keys: {list(frame.f_globals.keys())[:5]}...")

    # Walk the call stack
    print("\nCall stack:")
    f = frame
    while f is not None:
        print(f"  {f.f_code.co_name} at line {f.f_lineno}")
        f = f.f_back

outer()
```

## 10.2 Frame Stack (Call Stack)

The frame stack represents the chain of active function calls:

```
┌─────────────────────────────────────────────────────────────────┐
│                        Call Stack                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  def main():                                                     │
│      first()           ┌─────────────┐                          │
│                        │   third()   │ ← Current (top)          │
│  def first():          │  f_back ────┼──┐                       │
│      second()          ├─────────────┤  │                       │
│                        │  second()   │◀─┘                       │
│  def second():         │  f_back ────┼──┐                       │
│      third()           ├─────────────┤  │                       │
│                        │   first()   │◀─┘                       │
│  def third():          │  f_back ────┼──┐                       │
│      pass  # here      ├─────────────┤  │                       │
│                        │   main()    │◀─┘                       │
│                        │  f_back ────┼──▶ None                  │
│                        └─────────────┘                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Stack Walking

```python
import sys
import traceback

def get_call_stack():
    """Get the current call stack."""
    stack = []
    frame = sys._getframe()
    while frame:
        stack.append({
            'function': frame.f_code.co_name,
            'filename': frame.f_code.co_filename,
            'lineno': frame.f_lineno,
        })
        frame = frame.f_back
    return stack

def level3():
    for entry in get_call_stack():
        print(f"{entry['function']}:{entry['lineno']}")

def level2():
    level3()

def level1():
    level2()

level1()
```

## 10.3 Local Variables and Fast Locals

### Fast Locals Array

Local variables are stored in a fixed-size array for fast access:

```python
def example(a, b):
    x = 1
    y = 2
    return a + b + x + y

code = example.__code__
print(f"varnames: {code.co_varnames}")  # ('a', 'b', 'x', 'y')
print(f"nlocals: {code.co_nlocals}")     # 4
```

```
┌─────────────────────────────────────────────────────────────────┐
│                    Fast Locals Array                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Index │ Name │ Access Instruction                              │
│  ──────┼──────┼─────────────────────────                        │
│  0     │ a    │ LOAD_FAST 0, STORE_FAST 0                       │
│  1     │ b    │ LOAD_FAST 1, STORE_FAST 1                       │
│  2     │ x    │ LOAD_FAST 2, STORE_FAST 2                       │
│  3     │ y    │ LOAD_FAST 3, STORE_FAST 3                       │
│                                                                  │
│  Access: O(1) - direct array indexing                           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### `locals()` vs Fast Locals

```python
def example():
    x = 1
    y = 2

    # locals() creates a snapshot dict
    local_dict = locals()
    print(local_dict)  # {'x': 1, 'y': 2}

    # Modifying locals() doesn't affect real locals
    local_dict['x'] = 999
    print(x)  # Still 1!

    # But you can use exec to modify locals (don't do this)
    exec('x = 999')  # This creates a new local in exec's frame

example()
```

### Why Fast Locals?

```python
import dis

# LOAD_FAST is faster than LOAD_NAME/LOAD_GLOBAL
def fast_locals():
    x = 0
    for i in range(1000):
        x += i
    return x

dis.dis(fast_locals)
# Uses LOAD_FAST and STORE_FAST - direct array access
```

## 10.4 Frame Introspection (`sys._getframe()`)

### Basic Usage

```python
import sys

def example():
    frame = sys._getframe()  # Current frame
    frame = sys._getframe(0)  # Same as above
    frame = sys._getframe(1)  # Caller's frame
    frame = sys._getframe(2)  # Caller's caller's frame
    return frame

# Note: sys._getframe() is CPython-specific
```

### Frame Attributes

```python
import sys

def inspect_frame():
    frame = sys._getframe()

    # Code object info
    print(f"Function: {frame.f_code.co_name}")
    print(f"Filename: {frame.f_code.co_filename}")
    print(f"First line: {frame.f_code.co_firstlineno}")

    # Execution state
    print(f"Current line: {frame.f_lineno}")
    print(f"Last instruction: {frame.f_lasti}")

    # Namespaces
    print(f"Locals: {frame.f_locals}")
    print(f"Globals: {type(frame.f_globals)}")
    print(f"Builtins: {type(frame.f_builtins)}")

    # Call chain
    print(f"Caller: {frame.f_back}")

inspect_frame()
```

### Frame for Debugging

```python
import sys

def debug_print(msg):
    """Print with caller's context."""
    frame = sys._getframe(1)  # Caller's frame
    filename = frame.f_code.co_filename
    lineno = frame.f_lineno
    func = frame.f_code.co_name
    print(f"[{filename}:{lineno} in {func}] {msg}")

def my_function():
    x = 42
    debug_print(f"x = {x}")  # Shows caller's location

my_function()
```

## 10.5 Frame Object Lifecycle

### Frame Creation

```
Function call
     │
     ▼
┌─────────────────────────────────────────────────────────────────┐
│  1. Allocate frame (or reuse from free list)                    │
│  2. Initialize f_code from function's __code__                  │
│  3. Set f_globals from function's __globals__                   │
│  4. Set f_back to caller's frame                                │
│  5. Initialize fast locals with arguments                       │
│  6. Enter evaluation loop                                        │
└─────────────────────────────────────────────────────────────────┘
     │
     ▼
Execution
     │
     ▼
┌─────────────────────────────────────────────────────────────────┐
│  7. Return value or raise exception                             │
│  8. Decrement reference count on frame                          │
│  9. If count reaches 0, deallocate (or add to free list)        │
└─────────────────────────────────────────────────────────────────┘
```

### Frame Caching

Python caches frame objects for reuse (zombie frames):

```python
# Internal optimization - frames are reused
def recursive(n):
    if n <= 0:
        return
    recursive(n - 1)

# Frame objects are reused rather than constantly allocated
recursive(100)
```

### Frame References and Memory

```python
import sys
import gc

def leaky():
    frame = sys._getframe()
    return frame  # Returning frame keeps it alive!

# This creates a reference cycle: frame -> locals -> frame
f = leaky()
# Frame is kept alive, along with all its locals

# Be careful with frame references
del f
gc.collect()
```

## 10.6 Generators and Frame Suspension

Generators demonstrate frame suspension:

```python
def counter():
    x = 0
    while True:
        yield x  # Frame suspended here
        x += 1

gen = counter()
print(next(gen))  # 0 - frame runs until yield
print(next(gen))  # 1 - frame resumes from yield

# Generator holds reference to its frame
print(gen.gi_frame)
print(gen.gi_frame.f_locals)  # {'x': 1}
```

### Generator Frame State

```
┌─────────────────────────────────────────────────────────────────┐
│                   Generator Frame States                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Created         Running          Suspended        Exhausted     │
│  ┌──────┐       ┌──────┐         ┌──────┐        ┌──────┐      │
│  │Frame │ next()│Frame │  yield  │Frame │ next() │Frame │      │
│  │Ready │──────▶│Active│────────▶│Paused│───────▶│ Done │      │
│  └──────┘       └──────┘         └──────┘        └──────┘      │
│                     │                               │            │
│                     └──── StopIteration ───────────┘            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Coroutine Frames

```python
async def async_example():
    await some_async_call()
    return 42

coro = async_example()
print(coro.cr_frame)  # Coroutine frame
print(coro.cr_frame.f_locals)
```

## Python 3.11+ Frame Changes

Python 3.11 introduced significant frame optimizations:

### Lazy Frame Creation

```python
# Before 3.11: Frame always fully created
# After 3.11: "Frame" is lightweight until accessed

def fast_function():
    return 42  # No full frame object created

# Full frame only created when needed:
# - sys._getframe() called
# - Exception raised
# - Debugger/profiler active
```

### Internal Frames

```python
# Python 3.11+ uses _PyInterpreterFrame internally
# PyFrameObject is created on-demand for Python access

import sys

def example():
    # This forces frame object creation
    return sys._getframe()

# Normal calls don't create PyFrameObject
def normal():
    return 42  # Faster - no frame object
```

## Summary

- Frame objects hold function execution context
- Call stack is a chain of frames via `f_back`
- Fast locals provide O(1) variable access
- `sys._getframe()` provides introspection
- Generators suspend and resume frames
- Python 3.11+ optimizes frame creation

## Practice Exercises

1. Write a function that prints the full call stack with local variables
2. Create a context manager that captures the caller's frame
3. Implement a simple stack trace formatter
4. Explore generator frame states through their lifecycle

---

[← Previous: Interpreter Loop](chapter-09-interpreter-loop.md) | [Next: Namespaces and Scopes →](chapter-11-namespaces-scopes.md)

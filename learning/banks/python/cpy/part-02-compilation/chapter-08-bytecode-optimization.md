# Chapter 8: Bytecode Optimization

## 8.1 Peephole Optimizer

The peephole optimizer examines small sequences of instructions and replaces them with more efficient equivalents:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Peephole Optimization                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Before:                        After:                          │
│  LOAD_CONST 1                   LOAD_CONST 6                    │
│  LOAD_CONST 2                                                   │
│  BINARY_ADD                                                      │
│  LOAD_CONST 3                                                   │
│  BINARY_ADD                                                      │
│                                                                  │
│  "Peephole" = looking at a small window of instructions         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Optimization Location in Pipeline

```
AST → Symbol Table → Code Generation → Peephole Optimizer → Code Object
                                              ↑
                                         We are here
```

## 8.2 Constant Folding

The compiler evaluates constant expressions at compile time:

### Arithmetic Constant Folding

```python
import dis

# Constants are folded
def example():
    x = 1 + 2 + 3  # Becomes x = 6
    y = 2 * 3 * 4  # Becomes y = 24
    z = 10 / 2     # Becomes z = 5.0
    return x + y + z

dis.dis(example)
# Notice: LOAD_CONST loads pre-computed values
```

### String Constant Folding

```python
import dis

def example():
    s = "Hello, " + "World!"  # Folded to "Hello, World!"
    return s

dis.dis(example)
# LOAD_CONST ('Hello, World!')
```

### What Gets Folded

| Expression | Folded? | Result |
|-----------|---------|--------|
| `1 + 2` | Yes | `3` |
| `"a" + "b"` | Yes | `"ab"` |
| `(1, 2, 3)` | Yes | Constant tuple |
| `[1, 2, 3]` | No | Built at runtime |
| `{1, 2, 3}` | No | Built at runtime |
| `1 + x` | No | Variable involved |
| `"a" * 3` | Yes | `"aaa"` |
| `"a" * 1000` | Limited | May not fold large strings |

### Folding Limits

```python
import dis

# Small multiplication: folded
def small():
    return "x" * 10

# Large multiplication: not folded (memory concern)
def large():
    return "x" * 10000

dis.dis(small)  # LOAD_CONST ('xxxxxxxxxx')
dis.dis(large)  # LOAD_CONST ('x'), LOAD_CONST (10000), BINARY_MULTIPLY
```

## 8.3 Dead Code Elimination

Code that can never execute is removed:

### After Return

```python
import dis

def example():
    return 1
    x = 2      # Dead code - removed
    print(x)   # Dead code - removed

dis.dis(example)
# Only shows: LOAD_CONST (1), RETURN_VALUE
```

### Conditional Dead Code

```python
import dis

def example():
    if True:
        return "yes"
    else:
        return "no"  # Dead code (condition is constant True)

dis.dis(example)
# May optimize away the else branch
```

### Note: Limited Analysis

```python
# Python does NOT do advanced dead code analysis
def example():
    x = False
    if x:          # NOT eliminated (x could be reassigned)
        print("never")
```

## 8.4 Instruction Specialization (Python 3.11+)

Python 3.11 introduced the **Specializing Adaptive Interpreter**:

### How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│                 Adaptive Specialization                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Code starts with generic instructions                        │
│                                                                  │
│  2. At runtime, interpreter tracks types:                        │
│     BINARY_ADD sees: int + int, int + int, int + int            │
│                                                                  │
│  3. After threshold, instruction specializes:                    │
│     BINARY_ADD → BINARY_ADD_INT                                  │
│                                                                  │
│  4. If type assumption fails, deoptimize back to generic        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Specialized Instructions

| Generic | Specialized |
|---------|------------|
| `LOAD_GLOBAL` | `LOAD_GLOBAL_MODULE`, `LOAD_GLOBAL_BUILTIN` |
| `LOAD_ATTR` | `LOAD_ATTR_INSTANCE_VALUE`, `LOAD_ATTR_MODULE` |
| `BINARY_OP` | `BINARY_OP_ADD_INT`, `BINARY_OP_ADD_FLOAT` |
| `COMPARE_OP` | `COMPARE_OP_INT`, `COMPARE_OP_STR` |
| `CALL` | `CALL_PY_EXACT_ARGS`, `CALL_BUILTIN_O` |

### Viewing Specialization

```python
import dis

def add_ints(a, b):
    return a + b

# Run the function to trigger specialization
for _ in range(100):
    add_ints(1, 2)

# Show adaptive instructions
dis.dis(add_ints, adaptive=True)  # Python 3.11+
```

## 8.5 Quickening and Adaptive Interpreter

### Quickening Process

```
┌─────────────────────────────────────────────────────────────────┐
│                      Quickening Process                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Original bytecode (shared, immutable)                           │
│         │                                                        │
│         ▼                                                        │
│  First execution triggers quickening                             │
│         │                                                        │
│         ▼                                                        │
│  Quickened bytecode (per-function copy)                          │
│  - CACHE entries for inline caches                               │
│  - Ready for specialization                                      │
│         │                                                        │
│         ▼                                                        │
│  Runtime specialization based on observed types                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Inline Caches

```python
import dis

def example(obj):
    return obj.attr

# Disassemble with caches shown
dis.dis(example, show_caches=True)
# LOAD_ATTR has CACHE entries following it
# These store type information for specialization
```

### Specialization Statistics

```python
import sys

# Get specialization stats (debug builds)
if hasattr(sys, '_getspecializationstats'):
    stats = sys._getspecializationstats()
    print(stats)
```

## 8.6 Inline Caching

Inline caches speed up repeated operations:

### Attribute Lookup Cache

```
┌─────────────────────────────────────────────────────────────────┐
│                   Attribute Lookup Cache                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  obj.attr lookup without cache:                                  │
│  1. Get type of obj                                              │
│  2. Search type's __dict__ for 'attr'                           │
│  3. Walk MRO if not found                                        │
│  4. Check for descriptors                                        │
│  5. Return value                                                 │
│                                                                  │
│  With inline cache (monomorphic site):                          │
│  1. Check: is obj's type same as cached type?                   │
│  2. If yes: return cached offset directly                        │
│  3. If no: slow path + update cache                             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Cache States

| State | Description |
|-------|-------------|
| **Uninitialized** | No type seen yet |
| **Monomorphic** | One type seen (optimal) |
| **Polymorphic** | Few types seen |
| **Megamorphic** | Many types, cache disabled |

```python
def example(obj):
    return obj.x  # Cache site

# Monomorphic: always same type
class A:
    def __init__(self):
        self.x = 1

for _ in range(100):
    example(A())  # Fast: monomorphic cache

# Polymorphic: multiple types
class B:
    def __init__(self):
        self.x = 2

example(A())
example(B())
example(A())  # Cache handles both A and B
```

## Optimization Comparison

```python
import dis
import timeit

# Compare optimized vs non-optimized patterns

# Pattern 1: Constant folding benefit
def optimized():
    x = 24 * 60 * 60  # Folded to 86400

def manual():
    x = 86400  # Same result

# Both produce identical bytecode!
print("Optimized:", dis.dis(optimized))
print("Manual:", dis.dis(manual))

# Pattern 2: Local variable vs global lookup
global_len = len

def use_global():
    for i in range(1000):
        global_len([1, 2, 3])

def use_local():
    local_len = len  # Cache in local variable
    for i in range(1000):
        local_len([1, 2, 3])

# use_local is faster due to LOAD_FAST vs LOAD_GLOBAL
print("Global:", timeit.timeit(use_global, number=1000))
print("Local:", timeit.timeit(use_local, number=1000))
```

## Optimization Tips Based on Bytecode Knowledge

### 1. Use Local Variables in Loops

```python
# Slower: LOAD_GLOBAL each iteration
def slow():
    for i in range(1000):
        len([1, 2, 3])

# Faster: LOAD_FAST each iteration
def fast():
    _len = len
    for i in range(1000):
        _len([1, 2, 3])
```

### 2. Avoid Attribute Lookup in Loops

```python
# Slower: LOAD_ATTR each iteration
def slow(obj):
    for i in range(1000):
        obj.method()

# Faster: Cache the method
def fast(obj):
    method = obj.method
    for i in range(1000):
        method()
```

### 3. Use Tuple for Constant Sequences

```python
# List: built at runtime
def with_list():
    return x in [1, 2, 3, 4, 5]

# Tuple: constant, faster lookup
def with_tuple():
    return x in (1, 2, 3, 4, 5)

# Set: even better for membership tests
VALID = {1, 2, 3, 4, 5}  # Define once
def with_set():
    return x in VALID
```

## Summary

- **Peephole optimizer** improves small instruction sequences
- **Constant folding** evaluates constants at compile time
- **Dead code elimination** removes unreachable code
- **Python 3.11+ specialization** adapts to runtime types
- **Inline caches** speed up repeated operations
- Understanding bytecode helps write faster code

## Practice Exercises

1. Compare bytecode before/after optimization for various expressions
2. Write a benchmark comparing specialized vs generic instruction paths
3. Measure the impact of monomorphic vs polymorphic call sites
4. Find examples where Python doesn't optimize but could

---

[← Previous: Bytecode Instructions](chapter-07-bytecode-instructions.md) | [Next: Interpreter Loop →](../part-03-virtual-machine/chapter-09-interpreter-loop.md)

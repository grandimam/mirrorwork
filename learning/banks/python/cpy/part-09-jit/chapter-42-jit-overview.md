# Chapter 42: JIT Compilation Overview

## 42.1 What is JIT Compilation?

Just-In-Time (JIT) compilation converts bytecode to native machine code at runtime:

```
┌─────────────────────────────────────────────────────────────────┐
│              Interpretation vs JIT                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Traditional Interpreter (CPython):                              │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Source → Bytecode → Interpret each instruction         │    │
│  │                       (dispatch loop overhead)           │    │
│  │                                                          │    │
│  │  for i in range(1000000):                               │    │
│  │      x = i * 2    # ~100 cycles per iteration          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  JIT Compilation:                                                │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Source → Bytecode → Detect hot code → Compile to native│    │
│  │                                         (machine code)   │    │
│  │                                                          │    │
│  │  for i in range(1000000):                               │    │
│  │      x = i * 2    # ~5 cycles per iteration            │    │
│  │                   # (after JIT compilation)              │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  JIT benefit: 10-100x speedup for hot loops                     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 42.2 Python's JIT History

### Pre-3.13: No Built-in JIT

```
┌─────────────────────────────────────────────────────────────────┐
│              Python JIT History                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Before Python 3.13:                                             │
│  • CPython: Pure interpreter, no JIT                            │
│  • PyPy: Separate implementation with tracing JIT               │
│  • Numba: JIT for numerical code (using LLVM)                   │
│  • Cython: Ahead-of-time compilation to C                       │
│                                                                  │
│  Python 3.11:                                                    │
│  • Specializing adaptive interpreter                            │
│  • Quickened bytecode (type specialization)                     │
│  • Foundation for JIT                                            │
│                                                                  │
│  Python 3.12:                                                    │
│  • More specializations                                          │
│  • Improved inline caching                                       │
│                                                                  │
│  Python 3.13:                                                    │
│  • Experimental copy-and-patch JIT                              │
│  • First official CPython JIT                                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 42.3 CPython 3.13 JIT Architecture

### Copy-and-Patch JIT

```
┌─────────────────────────────────────────────────────────────────┐
│              Copy-and-Patch JIT                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Traditional JIT:                                                │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Bytecode → IR → Optimizer → Code generator → Machine   │    │
│  │                                                          │    │
│  │  Complex, many compilation phases                        │    │
│  │  High compile time, high quality code                    │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Copy-and-Patch JIT:                                             │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Bytecode → Copy pre-compiled template → Patch operands │    │
│  │                                                          │    │
│  │  1. Pre-compile instruction templates at build time     │    │
│  │  2. At runtime, copy template for each instruction      │    │
│  │  3. Patch in actual operands (constants, addresses)     │    │
│  │                                                          │    │
│  │  Simple, very fast compile time, decent code quality    │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### How Templates Work

```c
// Pre-compiled template for LOAD_FAST
// (Generated at Python build time using Clang)

// Template with placeholders:
// mov rax, [frame + PLACEHOLDER_offset]
// push rax

// At runtime, PLACEHOLDER_offset is patched
// with the actual local variable index

void emit_load_fast(JITContext *ctx, int oparg) {
    // Copy template bytes
    memcpy(ctx->code_ptr, load_fast_template, LOAD_FAST_SIZE);

    // Patch the offset
    int offset = oparg * sizeof(PyObject*);
    patch_i32(ctx->code_ptr + OFFSET_PATCH_LOCATION, offset);

    ctx->code_ptr += LOAD_FAST_SIZE;
}
```

## 42.4 Enabling the JIT

### Build Configuration

```bash
# Build Python with JIT enabled
./configure --enable-experimental-jit
make -j$(nproc)

# Or with specific JIT options
./configure --enable-experimental-jit=yes
./configure --enable-experimental-jit=yes-off  # Build but off by default
```

### Runtime Control

```bash
# Enable JIT at runtime
PYTHON_JIT=1 python script.py

# Disable JIT
PYTHON_JIT=0 python script.py
```

```python
# Check JIT status
import sys

if hasattr(sys, '_jit'):
    jit_info = sys._jit
    print(f"JIT enabled: {jit_info.enabled}")
    print(f"JIT threshold: {jit_info.threshold}")
```

## 42.5 JIT Compilation Flow

### When Code Gets JIT-Compiled

```
┌─────────────────────────────────────────────────────────────────┐
│              JIT Compilation Trigger                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Function/loop executes                                       │
│       │                                                          │
│       ▼                                                          │
│  2. Execution counter incremented                                │
│       │                                                          │
│       ▼                                                          │
│  3. Counter > threshold?  ──No──→ Continue interpreting         │
│       │                                                          │
│      Yes                                                         │
│       │                                                          │
│       ▼                                                          │
│  4. Analyze bytecode (specializations)                          │
│       │                                                          │
│       ▼                                                          │
│  5. Copy templates for each instruction                         │
│       │                                                          │
│       ▼                                                          │
│  6. Patch operands                                               │
│       │                                                          │
│       ▼                                                          │
│  7. Install compiled code                                        │
│       │                                                          │
│       ▼                                                          │
│  8. Future calls use native code                                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Code Example

```python
import time

def hot_function(n):
    """This function will be JIT-compiled after threshold calls."""
    total = 0
    for i in range(n):
        total += i * i
    return total

# Warm-up phase (interpreter)
for _ in range(100):
    hot_function(100)  # Each call increments counter

# After threshold, function is JIT-compiled
# Subsequent calls use native code
start = time.perf_counter()
result = hot_function(10_000_000)
elapsed = time.perf_counter() - start

print(f"Result: {result}")
print(f"Time: {elapsed:.3f}s")
```

## 42.6 Specialization and JIT

### Type Specialization

```python
# The adaptive interpreter specializes bytecode
# JIT uses these specializations

def add_numbers(a, b):
    return a + b

# First calls: Generic BINARY_ADD
add_numbers(1, 2)      # int + int
add_numbers(1.0, 2.0)  # float + float

# After specialization:
# BINARY_ADD → BINARY_ADD_INT (if mostly ints)
# JIT generates optimized code for int addition
```

### Specialization Types

```
┌─────────────────────────────────────────────────────────────────┐
│              Bytecode Specializations                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Generic              │ Specialized                              │
│  ─────────────────────┼────────────────────────────────         │
│  BINARY_ADD           │ BINARY_ADD_INT, BINARY_ADD_FLOAT        │
│  BINARY_MULTIPLY      │ BINARY_MULTIPLY_INT, BINARY_MULTIPLY_FLOAT│
│  LOAD_ATTR            │ LOAD_ATTR_INSTANCE_VALUE                │
│  LOAD_GLOBAL          │ LOAD_GLOBAL_MODULE, LOAD_GLOBAL_BUILTIN │
│  CALL                 │ CALL_PY_EXACT_ARGS, CALL_BUILTIN_O     │
│  COMPARE_OP           │ COMPARE_OP_INT, COMPARE_OP_STR         │
│                                                                  │
│  Specialized instructions have:                                  │
│  • Type-specific fast paths                                      │
│  • Inline caching                                                │
│  • Guards for deoptimization                                     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 42.7 Performance Impact

### Benchmark Comparison

```python
import time
import sys

def benchmark_arithmetic():
    """CPU-bound arithmetic."""
    total = 0
    for i in range(10_000_000):
        total += i * i
    return total

def benchmark_attribute():
    """Attribute access."""
    class Point:
        def __init__(self, x, y):
            self.x = x
            self.y = y

    points = [Point(i, i*2) for i in range(100000)]
    total = 0
    for p in points:
        total += p.x + p.y
    return total

def run_benchmark(name, func, iterations=5):
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        func()
        times.append(time.perf_counter() - start)
    avg = sum(times) / len(times)
    print(f"{name}: {avg:.3f}s")

print(f"Python {sys.version}")
print(f"JIT enabled: {getattr(sys, '_jit', {}).get('enabled', 'N/A')}")

run_benchmark("Arithmetic", benchmark_arithmetic)
run_benchmark("Attribute", benchmark_attribute)

# Expected results:
# Without JIT: Arithmetic 2.5s, Attribute 0.8s
# With JIT:    Arithmetic 0.5s, Attribute 0.3s
# Speedup:     ~5x arithmetic, ~2.5x attributes
```

### Where JIT Helps Most

```
┌─────────────────────────────────────────────────────────────────┐
│              JIT Performance Gains                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Best speedups (5-20x):                                          │
│  • Numeric loops with primitives                                │
│  • Tight loops with predictable types                           │
│  • Repeated method calls on same types                          │
│                                                                  │
│  Moderate speedups (2-5x):                                       │
│  • Attribute access (when types stable)                         │
│  • Dictionary operations (with stable keys)                     │
│  • Built-in function calls                                       │
│                                                                  │
│  Minimal speedup (<2x):                                          │
│  • I/O-bound code                                                │
│  • Code with dynamic types                                       │
│  • Megamorphic call sites                                        │
│  • Short-running functions                                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 42.8 JIT vs Other Approaches

### Comparison Table

```
┌─────────────────────────────────────────────────────────────────┐
│              JIT Comparison                                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Approach        │ Compile Time │ Runtime Perf │ Compatibility │
│  ────────────────┼──────────────┼──────────────┼──────────────│
│  CPython Interp  │ None         │ 1x (baseline)│ 100%         │
│  CPython JIT     │ Very fast    │ 2-5x         │ ~99%         │
│  PyPy            │ Slow warm-up │ 5-50x        │ ~95%         │
│  Numba           │ Medium       │ 50-100x      │ Subset       │
│  Cython          │ Ahead-of-time│ 10-100x      │ Subset       │
│                                                                  │
│  CPython JIT goals:                                              │
│  • Near-zero compile time overhead                              │
│  • Full compatibility                                            │
│  • Foundation for future optimizations                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 42.9 Deoptimization

### When JIT Code Fails

```python
# JIT compiles with type assumptions
def add(a, b):
    return a + b

# Called with ints - JIT specializes for int
for i in range(1000):
    add(i, i)  # BINARY_ADD_INT

# Now called with different type
add("hello", "world")  # Deoptimize!

# JIT code has guards:
# if (!PyLong_Check(a)) goto deopt;
# if (!PyLong_Check(b)) goto deopt;
# ... fast int addition ...
# deopt:
#     return to interpreter
```

### Guard Failures

```
┌─────────────────────────────────────────────────────────────────┐
│              Deoptimization Flow                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  JIT Code                                                        │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  guard: check type is int                               │    │
│  │         │                                                │    │
│  │         ├── Pass → Execute optimized int path           │    │
│  │         │                                                │    │
│  │         └── Fail → Deoptimize                           │    │
│  │                    │                                     │    │
│  │                    ▼                                     │    │
│  │              Return to interpreter                       │    │
│  │              (interpreter handles all types)             │    │
│  │                                                          │    │
│  │  Note: After many deoptimizations, may re-specialize    │    │
│  │        or give up JIT for this code                     │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 42.10 Future Directions

### Planned Improvements

```
┌─────────────────────────────────────────────────────────────────┐
│              JIT Roadmap                                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Python 3.13 (Current):                                          │
│  • Basic copy-and-patch JIT                                     │
│  • Per-instruction compilation                                   │
│  • Limited optimizations                                         │
│                                                                  │
│  Python 3.14+:                                                   │
│  • More instruction templates                                    │
│  • Better specializations                                        │
│  • Trace-based optimization?                                     │
│                                                                  │
│  Future possibilities:                                           │
│  • Loop unrolling                                                │
│  • Inlining                                                      │
│  • Better register allocation                                    │
│  • LLVM backend (for higher quality code)?                      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Summary

- **JIT compilation** converts bytecode to native machine code at runtime
- **Copy-and-patch** approach provides fast compile time
- **Specializations** enable type-specific optimizations
- **Deoptimization** handles type changes gracefully
- **2-5x speedup** typical for suitable code
- **Foundation** for future Python performance improvements

## Practice Exercises

1. Build Python with JIT and benchmark your code
2. Identify which functions benefit most from JIT
3. Analyze specialization patterns with `dis` module
4. Compare JIT performance with PyPy and Numba

---

[← Previous: Free-Threaded Extensions](../part-08-free-threading/chapter-41-free-threaded-extensions.md) | [Next: Copy-and-Patch Technique →](chapter-43-copy-and-patch.md)

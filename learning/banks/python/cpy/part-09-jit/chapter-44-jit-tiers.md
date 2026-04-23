# Chapter 44: JIT Tier System

## 44.1 Multi-Tier Execution

Modern JIT systems use multiple execution tiers:

```
┌─────────────────────────────────────────────────────────────────┐
│              Multi-Tier JIT Execution                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Tier 0: Interpreter                                             │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  • All code starts here                                  │    │
│  │  • Zero compile time                                     │    │
│  │  • Collects profiling information                        │    │
│  │  • ~1x performance (baseline)                            │    │
│  └─────────────────────────────────────────────────────────┘    │
│       │                                                          │
│       │ Hot code detected (execution count > threshold)          │
│       ▼                                                          │
│  Tier 1: Baseline JIT                                            │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  • Copy-and-patch compilation                           │    │
│  │  • Fast compile time (microseconds)                     │    │
│  │  • Type-specialized code                                 │    │
│  │  • ~2-5x performance                                     │    │
│  └─────────────────────────────────────────────────────────┘    │
│       │                                                          │
│       │ Very hot code (future Python versions?)                 │
│       ▼                                                          │
│  Tier 2: Optimizing JIT (Future)                                │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  • Full optimization (inlining, etc.)                   │    │
│  │  • Slower compile time (milliseconds)                   │    │
│  │  • ~5-20x performance                                    │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 44.2 CPython's Current Tier System

### Python 3.13 Tiers

```python
# CPython 3.13 has two tiers:
# Tier 0: Adaptive interpreter (with quickening)
# Tier 1: Copy-and-patch JIT

# Tier 0: Adaptive Interpreter
def example(a, b):
    return a + b

# First few calls - generic bytecode
# LOAD_FAST, BINARY_ADD, RETURN_VALUE

# After threshold - specialized bytecode (quickening)
# LOAD_FAST, BINARY_ADD_INT, RETURN_VALUE

# After more calls - JIT compiled (Tier 1)
# Native machine code with type guards
```

### Execution Flow

```
┌─────────────────────────────────────────────────────────────────┐
│              CPython 3.13 Execution Flow                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Function Call                                                   │
│       │                                                          │
│       ▼                                                          │
│  Check: Has JIT code?                                            │
│       │                                                          │
│       ├── Yes → Execute JIT code                                │
│       │         │                                                │
│       │         ├── Guard passes → Continue in JIT              │
│       │         │                                                │
│       │         └── Guard fails → Deoptimize to interpreter     │
│       │                                                          │
│       └── No → Check: Is hot? (counter > threshold)             │
│                │                                                 │
│                ├── Yes → Compile to JIT, then execute           │
│                │                                                 │
│                └── No → Execute in interpreter                  │
│                         │                                        │
│                         └── Increment counter                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 44.3 Hot Code Detection

### Execution Counters

```c
// Each code object has an execution counter
typedef struct {
    PyObject_HEAD
    // ... other fields ...

    // Warmup counter
    _Py_BackoffCounter warmup_count;

    // JIT-compiled code (if any)
    void *jit_code;

    // Specialization state
    uint8_t _co_quickened;
} PyCodeObject;

// Counter structure
typedef struct {
    uint16_t value;     // Current count
    uint16_t threshold; // Trigger threshold
} _Py_BackoffCounter;

// On each call
void _Py_IncrementCounter(PyCodeObject *co) {
    if (co->warmup_count.value < co->warmup_count.threshold) {
        co->warmup_count.value++;
    } else {
        // Hot! Trigger JIT compilation
        _Py_JIT_Compile(co);
    }
}
```

### Threshold Configuration

```python
import sys

# Default threshold (may vary by version)
DEFAULT_THRESHOLD = 100  # Calls before JIT

# Can be configured via environment
# PYTHON_JIT_THRESHOLD=50 python script.py

# Or programmatically (if supported)
if hasattr(sys, '_jit_threshold'):
    sys._jit_threshold = 50
```

## 44.4 Tier Transitions

### Interpreter to JIT

```c
// Transition from interpreter to JIT
PyObject* _PyEval_EvalFrame(PyThreadState *tstate, PyFrameObject *f) {
    PyCodeObject *co = f->f_code;

    // Check for existing JIT code
    if (co->jit_code != NULL) {
        // Execute JIT code
        return _PyJIT_Execute(tstate, f, co->jit_code);
    }

    // Check warmup counter
    if (++co->warmup_count.value >= co->warmup_count.threshold) {
        // Compile to JIT
        void *jit_code = _PyJIT_Compile(co);
        if (jit_code != NULL) {
            co->jit_code = jit_code;
            return _PyJIT_Execute(tstate, f, jit_code);
        }
        // Compilation failed, continue interpreting
    }

    // Interpret
    return _PyEval_EvalFrameDefault(tstate, f);
}
```

### JIT to Interpreter (Deoptimization)

```c
// Deoptimization: Return from JIT to interpreter
void _PyJIT_Deoptimize(JITFrame *jit_frame, int reason) {
    PyFrameObject *f = jit_frame->py_frame;

    // Restore interpreter state
    f->f_lasti = jit_frame->bytecode_offset;

    // Copy stack from JIT frame to Python frame
    for (int i = 0; i < jit_frame->stack_depth; i++) {
        f->f_valuestack[i] = jit_frame->stack[i];
    }

    // Invalidate JIT code (optional, based on reason)
    if (reason == DEOPT_TYPE_CHANGED) {
        PyCodeObject *co = f->f_code;
        _PyJIT_Invalidate(co);
        co->jit_code = NULL;
    }

    // Continue in interpreter
    longjmp(jit_frame->deopt_target, 1);
}
```

## 44.5 On-Stack Replacement (OSR)

### What is OSR?

```
┌─────────────────────────────────────────────────────────────────┐
│              On-Stack Replacement (OSR)                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Problem: Long-running loop in interpreter                       │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  for i in range(10_000_000):  # Takes forever!          │    │
│  │      result += compute(i)                                │    │
│  │  # Loop becomes hot while still running                  │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Without OSR:                                                    │
│  • Must wait for function to return                             │
│  • JIT only helps next call                                     │
│  • First call is slow                                           │
│                                                                  │
│  With OSR:                                                       │
│  • Can switch to JIT mid-execution                              │
│  • Transfer state from interpreter to JIT                       │
│  • Loop runs fast for remaining iterations                      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### OSR Entry Points

```c
// Check for OSR at loop back-edges
void _PyEval_EvalFrameDefault(PyThreadState *tstate, PyFrameObject *f) {
    // ... dispatch loop ...

    case JUMP_BACKWARD:
        // Loop back-edge - potential OSR point
        if (co->warmup_count.value >= OSR_THRESHOLD) {
            // Try to compile and switch to JIT
            void *osr_entry = _PyJIT_CompileOSR(co, f->f_lasti);
            if (osr_entry != NULL) {
                return _PyJIT_EnterOSR(tstate, f, osr_entry);
            }
        }
        // Continue interpreting
        f->f_lasti = oparg;
        break;
}
```

## 44.6 Profiling and Feedback

### Type Profiling

```c
// Track types seen at each operation
typedef struct {
    PyTypeObject *types[4];  // Up to 4 observed types
    uint8_t count;           // Number of types seen
    uint32_t hits[4];        // Count per type
} TypeProfile;

// Record type at BINARY_ADD
void _Py_RecordTypeProfile(TypeProfile *profile, PyObject *left, PyObject *right) {
    PyTypeObject *left_type = Py_TYPE(left);

    for (int i = 0; i < profile->count; i++) {
        if (profile->types[i] == left_type) {
            profile->hits[i]++;
            return;
        }
    }

    // New type
    if (profile->count < 4) {
        profile->types[profile->count] = left_type;
        profile->hits[profile->count] = 1;
        profile->count++;
    }
}

// Use profile for JIT decisions
void _PyJIT_CompileWithProfile(PyCodeObject *co) {
    // For each instruction
    for (int i = 0; i < co->co_nlocals; i++) {
        TypeProfile *profile = &co->type_profiles[i];

        if (profile->count == 1) {
            // Monomorphic - generate specialized code
            emit_specialized_for_type(profile->types[0]);
        } else if (profile->count <= 4) {
            // Polymorphic - generate type switch
            emit_type_switch(profile->types, profile->count);
        } else {
            // Megamorphic - generate generic code
            emit_generic();
        }
    }
}
```

### Branch Profiling

```c
// Track branch taken/not-taken counts
typedef struct {
    uint32_t taken;
    uint32_t not_taken;
} BranchProfile;

// Record branch outcome
void _Py_RecordBranch(BranchProfile *profile, int taken) {
    if (taken) {
        profile->taken++;
    } else {
        profile->not_taken++;
    }
}

// Use for branch prediction hints
void emit_branch(BranchProfile *profile, int target) {
    if (profile->taken > profile->not_taken * 10) {
        // Strongly taken - predict taken
        emit_likely_branch(target);
    } else if (profile->not_taken > profile->taken * 10) {
        // Strongly not taken - predict not taken
        emit_unlikely_branch(target);
    } else {
        // No strong preference
        emit_branch_neutral(target);
    }
}
```

## 44.7 Compilation Policies

### When to Compile

```c
// Compilation policy decisions
typedef struct {
    int call_threshold;      // Calls before compile
    int loop_threshold;      // Loop iterations for OSR
    int deopt_threshold;     // Deopts before giving up
    int recompile_delay;     // Delay before recompile
} JITPolicy;

static JITPolicy default_policy = {
    .call_threshold = 100,
    .loop_threshold = 1000,
    .deopt_threshold = 10,
    .recompile_delay = 1000
};

int should_compile(PyCodeObject *co) {
    // Don't compile very short functions
    if (co->co_code_size < MIN_CODE_SIZE) {
        return 0;
    }

    // Don't recompile if recently failed
    if (co->last_deopt_time > current_time - policy.recompile_delay) {
        return 0;
    }

    // Don't keep recompiling unstable code
    if (co->deopt_count >= policy.deopt_threshold) {
        return 0;
    }

    return 1;
}
```

### Compilation Budget

```c
// Limit compilation time per unit time
typedef struct {
    int64_t budget_ns;       // Time budget per interval
    int64_t interval_ns;     // Budget interval
    int64_t last_reset;      // Last budget reset time
    int64_t used_ns;         // Time used this interval
} CompilationBudget;

int try_compile(PyCodeObject *co, CompilationBudget *budget) {
    int64_t now = get_time_ns();

    // Reset budget if interval passed
    if (now - budget->last_reset > budget->interval_ns) {
        budget->used_ns = 0;
        budget->last_reset = now;
    }

    // Check if we have budget
    if (budget->used_ns >= budget->budget_ns) {
        return 0;  // Over budget, skip compilation
    }

    // Compile and track time
    int64_t start = get_time_ns();
    void *code = _PyJIT_Compile(co);
    int64_t elapsed = get_time_ns() - start;

    budget->used_ns += elapsed;

    return code != NULL;
}
```

## 44.8 Future Tier 2 Optimizations

### Potential Optimizations

```
┌─────────────────────────────────────────────────────────────────┐
│              Potential Tier 2 Optimizations                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Inlining                                                     │
│     • Inline small, frequently-called functions                 │
│     • Reduces call overhead                                      │
│     • Enables further optimization                               │
│                                                                  │
│  2. Escape Analysis                                              │
│     • Detect objects that don't escape                          │
│     • Allocate on stack instead of heap                         │
│     • Eliminate unnecessary allocations                          │
│                                                                  │
│  3. Loop Optimizations                                           │
│     • Loop unrolling                                             │
│     • Loop invariant code motion                                 │
│     • Strength reduction                                         │
│                                                                  │
│  4. Global Value Numbering                                       │
│     • Eliminate redundant computations                          │
│     • Common subexpression elimination                          │
│                                                                  │
│  5. Type Propagation                                             │
│     • Infer types through data flow                             │
│     • Remove redundant type checks                              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Trace-Based Tier 2

```python
# Hypothetical trace-based optimization

# Hot loop detected:
for i in range(1000000):
    x = a[i]
    y = x * 2
    b[i] = y

# Trace recording captures:
# 1. LOAD_FAST (a), BINARY_SUBSCR (list)
# 2. LOAD_FAST (x), BINARY_MULTIPLY (int)
# 3. LOAD_FAST (b), STORE_SUBSCR (list)

# Trace compilation generates:
# - Fused array access
# - Loop unrolling (4x)
# - Vectorization (SIMD)
```

## 44.9 Monitoring JIT Activity

### JIT Statistics

```python
import sys

def get_jit_stats():
    """Get JIT compilation statistics."""
    if not hasattr(sys, '_jit_stats'):
        return None

    stats = sys._jit_stats()
    return {
        'compilations': stats.get('compilations', 0),
        'compile_time_ms': stats.get('compile_time_ms', 0),
        'deoptimizations': stats.get('deoptimizations', 0),
        'jit_code_size': stats.get('jit_code_size', 0),
        'cache_hits': stats.get('cache_hits', 0),
        'cache_misses': stats.get('cache_misses', 0),
    }

# Print stats periodically
import atexit
atexit.register(lambda: print(f"JIT stats: {get_jit_stats()}"))
```

### Function-Level Analysis

```python
def analyze_function(func):
    """Analyze JIT status of a function."""
    code = func.__code__

    if hasattr(code, '_jit_info'):
        info = code._jit_info()
        print(f"Function: {func.__name__}")
        print(f"  JIT compiled: {info['compiled']}")
        print(f"  Execution count: {info['exec_count']}")
        print(f"  Deopt count: {info['deopt_count']}")
        print(f"  Code size: {info['code_size']} bytes")
    else:
        print(f"JIT info not available for {func.__name__}")
```

## Summary

- **Multi-tier execution** balances compile time vs code quality
- **CPython 3.13** has interpreter (Tier 0) and copy-and-patch JIT (Tier 1)
- **Hot code detection** uses execution counters
- **OSR** enables switching to JIT mid-execution
- **Type profiling** guides specialization decisions
- **Compilation policies** control when and what to compile
- **Future Tier 2** may add more aggressive optimizations

## Practice Exercises

1. Measure warmup time for JIT compilation
2. Analyze deoptimization patterns in your code
3. Compare performance across different thresholds
4. Profile type stability in hot functions

---

[← Previous: Copy-and-Patch](chapter-43-copy-and-patch.md) | [Next: JIT Debugging →](chapter-45-jit-debugging.md)

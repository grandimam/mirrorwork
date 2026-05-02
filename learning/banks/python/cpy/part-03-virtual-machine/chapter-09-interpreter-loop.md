# Chapter 9: Interpreter Loop

## 9.1 The Evaluation Loop (`ceval.c`)

The interpreter loop is the heart of CPython. Located in `Python/ceval.c`, it fetches and executes bytecode instructions one at a time.

### Simplified Structure

```c
// Simplified view of the main loop (Python/ceval.c)
PyObject* _PyEval_EvalFrameDefault(PyThreadState *tstate, PyFrameObject *f) {
    // Local variables for speed
    PyObject **stack_pointer;
    const _Py_CODEUNIT *next_instr;
    int opcode;
    int oparg;

    // Main dispatch loop
    for (;;) {
        // Fetch instruction
        opcode = _Py_OPCODE(*next_instr);
        oparg = _Py_OPARG(*next_instr);
        next_instr++;

        switch (opcode) {
            case LOAD_CONST:
                value = GETITEM(consts, oparg);
                PUSH(value);
                break;

            case BINARY_ADD:
                right = POP();
                left = TOP();
                sum = PyNumber_Add(left, right);
                SET_TOP(sum);
                break;

            // ... hundreds more cases ...

            case RETURN_VALUE:
                retval = POP();
                goto exit_returning;
        }
    }
}
```

### Key Components

```
┌─────────────────────────────────────────────────────────────────┐
│                    Evaluation Loop Components                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Thread State (tstate)                                    │   │
│  │  - Current exception info                                 │   │
│  │  - Recursion depth                                        │   │
│  │  - GIL state                                              │   │
│  └──────────────────────────────────────────────────────────┘   │
│                          │                                       │
│                          ▼                                       │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Frame Object (f)                                         │   │
│  │  - Code object (bytecode, constants, names)              │   │
│  │  - Local variables (fast locals)                          │   │
│  │  - Value stack                                            │   │
│  │  - Instruction pointer                                    │   │
│  └──────────────────────────────────────────────────────────┘   │
│                          │                                       │
│                          ▼                                       │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Dispatch Loop                                            │   │
│  │  - Fetch opcode and argument                              │   │
│  │  - Execute instruction                                    │   │
│  │  - Handle exceptions                                      │   │
│  │  - Check for signals, GIL, etc.                          │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 9.2 `_PyEval_EvalFrameDefault`

This is the main interpreter function. Every Python code execution goes through it.

### Function Signature

```c
PyObject *
_PyEval_EvalFrameDefault(PyThreadState *tstate, _PyInterpreterFrame *frame, int throwflag)
```

### Parameters

| Parameter | Description |
|-----------|-------------|
| `tstate` | Current thread's state |
| `frame` | Frame containing code to execute |
| `throwflag` | Whether to throw an exception into the frame |

### What Happens Inside

```
1. Initialize local variables (for performance)
   - stack_pointer: pointer to value stack top
   - next_instr: pointer to next instruction
   - Local copies of frequently accessed data

2. Enter main loop
   ┌─────────────────────────────────────┐
   │  while (true) {                     │
   │      fetch instruction              │
   │      dispatch to handler            │
   │      handle result                  │
   │      check for interrupts           │
   │  }                                  │
   └─────────────────────────────────────┘

3. Exit when:
   - RETURN_VALUE is executed
   - Exception is raised
   - Generator yields
```

## 9.3 Computed Gotos vs Switch Statement

The interpreter can use two dispatch mechanisms:

### Switch Statement (Default)

```c
switch (opcode) {
    case LOAD_CONST:
        // ... handle LOAD_CONST ...
        break;
    case BINARY_ADD:
        // ... handle BINARY_ADD ...
        break;
    // ...
}
```

### Computed Gotos (When Available)

```c
// Dispatch table
static void *opcode_targets[] = {
    [LOAD_CONST] = &&TARGET_LOAD_CONST,
    [BINARY_ADD] = &&TARGET_BINARY_ADD,
    // ...
};

// Dispatch
goto *opcode_targets[opcode];

TARGET_LOAD_CONST:
    // ... handle LOAD_CONST ...
    DISPATCH();  // goto *opcode_targets[next_opcode]

TARGET_BINARY_ADD:
    // ... handle BINARY_ADD ...
    DISPATCH();
```

### Performance Comparison

| Method | Pros | Cons |
|--------|------|------|
| Switch | Portable, standard C | Branch prediction worse |
| Computed Goto | Better branch prediction, 15-20% faster | GCC/Clang extension |

```c
// In Python/ceval.c
#ifdef USE_COMPUTED_GOTOS
    // Uses computed gotos
#else
    // Uses switch statement
#endif
```

## 9.4 Instruction Dispatch

### Dispatch Macros

```c
// Simplified dispatch macros from ceval.c

// Fetch next instruction and dispatch
#define DISPATCH() \
    { \
        opcode = _Py_OPCODE(*next_instr); \
        oparg = _Py_OPARG(*next_instr); \
        next_instr++; \
        goto *opcode_targets[opcode]; \
    }

// Predict next instruction (optimization)
#define PREDICT(op) \
    if (*next_instr == op) { \
        next_instr++; \
        goto TARGET_##op; \
    }
```

### Instruction Prediction

Some instructions commonly follow others. Prediction avoids dispatch overhead:

```c
// After COMPARE_OP, often comes POP_JUMP_IF_FALSE
case COMPARE_OP:
    // ... do comparison ...
    PREDICT(POP_JUMP_IF_FALSE);  // Try to predict next
    DISPATCH();  // Fall back to normal dispatch

// If prediction succeeds, jump directly here
case POP_JUMP_IF_FALSE:
    // ...
```

## 9.5 Exception Handling in the Loop

### Exception State

```c
// Exception info stored in thread state
typedef struct _PyErr_StackItem {
    PyObject *exc_type;
    PyObject *exc_value;
    PyObject *exc_traceback;
} _PyErr_StackItem;
```

### Exception Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    Exception Handling Flow                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Error occurs (e.g., division by zero)                       │
│     │                                                            │
│     ▼                                                            │
│  2. C code calls PyErr_SetString(PyExc_ZeroDivisionError, ...)  │
│     │                                                            │
│     ▼                                                            │
│  3. Returns NULL to signal error                                 │
│     │                                                            │
│     ▼                                                            │
│  4. Eval loop detects NULL return                               │
│     │                                                            │
│     ▼                                                            │
│  5. Look for exception handler in current frame                  │
│     │                                                            │
│     ├─── Found: Jump to handler, continue execution             │
│     │                                                            │
│     └─── Not found: Unwind to caller frame, repeat from step 5  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Exception Table (Python 3.11+)

```python
# Python 3.11+ uses exception tables instead of block stack
def example():
    try:
        risky()
    except ValueError:
        handle()
```

```python
import dis
dis.dis(example)
# Shows exception table at the end:
# ExceptionTable:
#   2 to 4 -> 6 [0]
```

### Error Checking Pattern

```c
// Most operations return NULL on error
case BINARY_ADD:
    right = POP();
    left = TOP();
    sum = PyNumber_Add(left, right);
    Py_DECREF(left);
    Py_DECREF(right);
    if (sum == NULL) {
        goto error;  // Exception was set
    }
    SET_TOP(sum);
    DISPATCH();
```

## Interpreter Hooks

### Tracing

```python
import sys

def trace_calls(frame, event, arg):
    if event == 'call':
        print(f"Calling: {frame.f_code.co_name}")
    return trace_calls

sys.settrace(trace_calls)

def foo():
    return bar()

def bar():
    return 42

foo()  # Prints: Calling: foo, Calling: bar
sys.settrace(None)
```

### Profiling

```python
import sys

def profiler(frame, event, arg):
    print(f"{event}: {frame.f_code.co_name}")

sys.setprofile(profiler)

def example():
    return 42

example()
sys.setprofile(None)
```

### How Tracing Affects the Loop

```c
// In eval loop
if (tstate->c_tracefunc != NULL) {
    // Call trace function before each line
    // This significantly slows execution
}
```

## Performance Considerations

### Hot Path Optimization

The eval loop is heavily optimized:
- Local variables instead of struct access
- Inline caching
- Branch prediction hints
- Computed gotos

### Eval Breaker

Periodically, the loop checks for:
- Pending signals
- Other threads waiting for GIL
- Async exceptions

```c
// Check eval breaker
if (_Py_atomic_load_relaxed(&tstate->interp->ceval.eval_breaker)) {
    // Handle pending events
    if (handle_eval_breaker(tstate) < 0) {
        goto error;
    }
}
```

## Summary

- The eval loop in `ceval.c` is CPython's heart
- `_PyEval_EvalFrameDefault` executes bytecode
- Computed gotos provide ~15-20% speedup
- Exception handling integrates with the loop
- Tracing/profiling hooks slow execution
- Periodic checks handle signals and GIL

## Practice Exercises

1. Read through `Python/ceval.c` and identify the main loop
2. Write a trace function that logs all function calls
3. Measure the performance impact of `sys.settrace`
4. Find where GIL checks happen in the eval loop

---

[← Previous: Bytecode Optimization](../part-02-compilation/chapter-08-bytecode-optimization.md) | [Next: Frame Objects →](chapter-10-frame-objects.md)

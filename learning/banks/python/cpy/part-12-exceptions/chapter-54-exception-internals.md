# Chapter 54: Exception Handling Internals

## 54.1 Exception Object Structure

Exceptions are Python objects with special attributes:

```c
// Base exception structure
typedef struct {
    PyObject_HEAD
    PyObject *args;          // Exception arguments
    PyObject *traceback;     // Traceback object
    PyObject *context;       // __context__ (implicit chaining)
    PyObject *cause;         // __cause__ (explicit chaining)
    char suppress_context;   // __suppress_context__
} PyBaseExceptionObject;
```

```python
try:
    raise ValueError("error message")
except ValueError as e:
    print(e.args)           # ('error message',)
    print(e.__traceback__)  # <traceback object>
    print(e.__context__)    # Previous exception (if any)
    print(e.__cause__)      # Explicit cause (from "raise ... from")
```

## 54.2 Exception Handling Bytecode

```python
import dis

def example():
    try:
        risky()
    except ValueError:
        handle()

dis.dis(example)
# SETUP_FINALLY
# LOAD_GLOBAL (risky)
# CALL
# POP_TOP
# POP_BLOCK
# JUMP_FORWARD (to end)
# PUSH_EXC_INFO
# LOAD_GLOBAL (ValueError)
# CHECK_EXC_MATCH
# POP_JUMP_IF_FALSE
# ...
```

## 54.3 The Exception Stack

Python maintains an exception stack per thread:

```c
// Per-thread exception state
typedef struct _ts {
    // ... other fields ...

    // Current exception being handled
    PyObject *curexc_type;
    PyObject *curexc_value;
    PyObject *curexc_traceback;

    // Exception being raised
    PyObject *exc_state.exc_type;
    PyObject *exc_state.exc_value;
    PyObject *exc_state.exc_traceback;
} PyThreadState;
```

## 54.4 Exception Chaining

```python
# Implicit chaining (__context__)
try:
    1/0
except ZeroDivisionError:
    raise ValueError("new error")
# ValueError has __context__ = ZeroDivisionError

# Explicit chaining (__cause__)
try:
    1/0
except ZeroDivisionError as e:
    raise ValueError("new error") from e
# ValueError has __cause__ = ZeroDivisionError

# Suppress chaining
raise ValueError("new error") from None
# __suppress_context__ = True
```

## Summary

- Exceptions are objects with args, traceback, context, and cause
- Bytecode uses SETUP_FINALLY and PUSH_EXC_INFO
- Thread state tracks current exception
- Exception chaining supports debugging

---

[Next: Traceback Objects →](chapter-55-tracebacks.md)

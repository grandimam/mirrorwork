# Chapter 57: Debugging Tools

## 57.1 The pdb Debugger

```python
import pdb

def buggy_function(x):
    pdb.set_trace()  # Start debugger here
    result = x * 2
    return result

# Or use breakpoint() (Python 3.7+)
def another_function():
    breakpoint()  # Same as pdb.set_trace()
```

### pdb Commands
```
n(ext)      - Execute next line
s(tep)      - Step into function
c(ontinue)  - Continue execution
l(ist)      - Show current location
p expr      - Print expression
pp expr     - Pretty print
w(here)     - Show stack trace
b line      - Set breakpoint
q(uit)      - Quit debugger
```

## 57.2 sys.settrace

```python
import sys

def trace_calls(frame, event, arg):
    if event == 'call':
        print(f"Call: {frame.f_code.co_name}")
    elif event == 'line':
        print(f"Line: {frame.f_lineno}")
    elif event == 'return':
        print(f"Return: {arg}")
    return trace_calls

sys.settrace(trace_calls)
# All function calls are now traced
```

## 57.3 Frame Inspection

```python
import inspect

def get_caller_info():
    frame = inspect.currentframe()
    caller = frame.f_back

    return {
        'file': caller.f_code.co_filename,
        'line': caller.f_lineno,
        'function': caller.f_code.co_name,
        'locals': caller.f_locals.copy(),
    }
```

## Summary

- pdb provides interactive debugging
- sys.settrace enables custom tracing
- Frame inspection reveals execution state

---

[Next: Profiling →](chapter-58-profiling.md)

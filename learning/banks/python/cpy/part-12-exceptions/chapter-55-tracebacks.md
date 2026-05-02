# Chapter 55: Traceback Objects

## 55.1 Traceback Structure

```c
typedef struct _traceback {
    PyObject_HEAD
    struct _traceback *tb_next;  // Next frame in traceback
    PyFrameObject *tb_frame;     // Frame object
    int tb_lasti;                // Last instruction index
    int tb_lineno;               // Line number
} PyTracebackObject;
```

## 55.2 Accessing Tracebacks

```python
import sys
import traceback

try:
    1/0
except:
    # Get exception info
    exc_type, exc_value, exc_tb = sys.exc_info()

    # Walk traceback
    tb = exc_tb
    while tb is not None:
        frame = tb.tb_frame
        print(f"{frame.f_code.co_filename}:{tb.tb_lineno} in {frame.f_code.co_name}")
        tb = tb.tb_next

    # Format traceback
    lines = traceback.format_exception(exc_type, exc_value, exc_tb)
    print(''.join(lines))
```

## 55.3 Traceback Manipulation

```python
import types

# Create custom traceback (Python 3.7+)
def create_traceback(frame, lasti, lineno, next_tb=None):
    return types.TracebackType(next_tb, frame, lasti, lineno)

# Modify exception traceback
try:
    raise ValueError()
except ValueError as e:
    # Add or replace traceback
    e.__traceback__ = e.__traceback__.tb_next  # Skip first frame
```

## Summary

- Tracebacks are linked lists of frame references
- `sys.exc_info()` provides current exception details
- `traceback` module formats exception information
- Tracebacks can be manipulated programmatically

---

[Next: Custom Exceptions →](chapter-56-custom-exceptions.md)

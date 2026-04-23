# Chapter 65: PyPy and Alternative Implementations

## 65.1 PyPy Overview

PyPy is an alternative Python implementation with a JIT compiler:

```
┌─────────────────────────────────────────────────────────────────┐
│              PyPy Architecture                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Key Features:                                                   │
│  • Tracing JIT compiler                                         │
│  • Written in RPython (restricted Python)                       │
│  • Often 5-50x faster than CPython                              │
│  • ~95% compatible with CPython                                  │
│                                                                  │
│  Execution Flow:                                                 │
│  Python Code → Bytecode → Interpreter → Hot loops detected     │
│      → Trace recording → JIT compilation → Native code         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 65.2 When to Use PyPy

```python
# PyPy excels at:
# - Long-running programs
# - Numeric loops
# - Object-oriented code

# PyPy may not help with:
# - I/O-bound code
# - Short scripts (JIT warmup)
# - C extension heavy code (use cpyext)
```

## 65.3 Other Implementations

| Implementation | Use Case |
|---------------|----------|
| **Jython** | Java interop |
| **IronPython** | .NET interop |
| **MicroPython** | Microcontrollers |
| **GraalPython** | GraalVM ecosystem |
| **Pyston** | Performance-focused |

## Summary

- PyPy offers significant speedups via JIT
- Choose implementation based on use case
- CPython remains the reference implementation

---

[Next: Comparing Implementations →](chapter-66-implementation-comparison.md)

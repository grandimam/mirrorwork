# Chapter 66: Implementation Comparison

## 66.1 Feature Comparison

| Feature | CPython | PyPy | Jython | MicroPython |
|---------|---------|------|--------|-------------|
| GIL | Yes* | Yes | No (uses JVM) | Yes |
| JIT | Yes (3.13+) | Yes (tracing) | No (JVM JIT) | No |
| C Extensions | Native | cpyext | No | Limited |
| Memory | High | Lower | JVM managed | Very low |

*CPython 3.13+ has optional free-threading

## 66.2 Performance Characteristics

```
┌─────────────────────────────────────────────────────────────────┐
│              Typical Speedups vs CPython                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Benchmark Type      │ PyPy  │ Jython │ Pyston │ CPython 3.13 │
│  ────────────────────┼───────┼────────┼────────┼──────────────│
│  Numeric loops       │ 50x   │ 2x     │ 3x     │ 2-3x         │
│  Object manipulation │ 10x   │ 1.5x   │ 2x     │ 1.5x         │
│  String processing   │ 5x    │ 0.5x   │ 1.5x   │ 1.2x         │
│  I/O bound          │ 1x    │ 1x     │ 1x     │ 1x           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 66.3 Choosing an Implementation

```python
# Decision tree:
#
# Need maximum compatibility? → CPython
# Need raw speed for pure Python? → PyPy
# Need Java integration? → Jython
# Need .NET integration? → IronPython
# Embedded/IoT device? → MicroPython
# GraalVM ecosystem? → GraalPython
```

## Summary

- CPython is the reference, most compatible
- PyPy offers best pure-Python performance
- Choose based on ecosystem and requirements
- Always benchmark your specific workload

---

[Next: Lab 1 →](../part-16-labs/lab-01-bytecode.md)

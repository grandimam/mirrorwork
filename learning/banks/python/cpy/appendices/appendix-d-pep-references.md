# Appendix D: PEP References

## Core Interpreter PEPs

### Memory Management

| PEP | Title | Status | Python Version |
|-----|-------|--------|----------------|
| [PEP 442](https://peps.python.org/pep-0442/) | Safe object finalization | Final | 3.4 |
| [PEP 456](https://peps.python.org/pep-0456/) | Secure and interchangeable hash algorithm | Final | 3.4 |

### Threading and Concurrency

| PEP | Title | Status | Python Version |
|-----|-------|--------|----------------|
| [PEP 371](https://peps.python.org/pep-0371/) | Addition of the multiprocessing package | Final | 2.6/3.0 |
| [PEP 3148](https://peps.python.org/pep-3148/) | futures - execute computations asynchronously | Final | 3.2 |
| [PEP 3156](https://peps.python.org/pep-3156/) | Asynchronous IO Support Rebooted | Final | 3.4 |
| [PEP 492](https://peps.python.org/pep-0492/) | Coroutines with async and await syntax | Final | 3.5 |
| [PEP 525](https://peps.python.org/pep-0525/) | Asynchronous Generators | Final | 3.6 |
| [PEP 530](https://peps.python.org/pep-0530/) | Asynchronous Comprehensions | Final | 3.6 |
| [PEP 554](https://peps.python.org/pep-0554/) | Multiple Interpreters in the Stdlib | Draft | TBD |
| [PEP 684](https://peps.python.org/pep-0684/) | A Per-Interpreter GIL | Final | 3.12 |
| [PEP 703](https://peps.python.org/pep-0703/) | Making the Global Interpreter Lock Optional | Accepted | 3.13 |
| [PEP 734](https://peps.python.org/pep-0734/) | Multiple Interpreters in the Stdlib | Draft | TBD |

### Performance and Optimization

| PEP | Title | Status | Python Version |
|-----|-------|--------|----------------|
| [PEP 509](https://peps.python.org/pep-0509/) | Add a private version to dict | Final | 3.6 |
| [PEP 590](https://peps.python.org/pep-0590/) | Vectorcall: A fast calling protocol | Final | 3.9 |
| [PEP 659](https://peps.python.org/pep-0659/) | Specializing Adaptive Interpreter | Final | 3.11 |
| [PEP 669](https://peps.python.org/pep-0669/) | Low Impact Monitoring for CPython | Final | 3.12 |
| [PEP 744](https://peps.python.org/pep-0744/) | JIT Compilation | Draft | 3.13 |

### Import System

| PEP | Title | Status | Python Version |
|-----|-------|--------|----------------|
| [PEP 302](https://peps.python.org/pep-0302/) | New Import Hooks | Final | 2.3 |
| [PEP 328](https://peps.python.org/pep-0328/) | Imports: Multi-Line and Absolute/Relative | Final | 2.4 |
| [PEP 366](https://peps.python.org/pep-0366/) | Main module explicit relative imports | Final | 2.6 |
| [PEP 420](https://peps.python.org/pep-0420/) | Implicit Namespace Packages | Final | 3.3 |
| [PEP 451](https://peps.python.org/pep-0451/) | A ModuleSpec Type for the Import System | Final | 3.4 |
| [PEP 489](https://peps.python.org/pep-0489/) | Multi-phase extension module initialization | Final | 3.5 |

### Type System

| PEP | Title | Status | Python Version |
|-----|-------|--------|----------------|
| [PEP 484](https://peps.python.org/pep-0484/) | Type Hints | Final | 3.5 |
| [PEP 526](https://peps.python.org/pep-0526/) | Syntax for Variable Annotations | Final | 3.6 |
| [PEP 544](https://peps.python.org/pep-0544/) | Protocols: Structural subtyping | Final | 3.8 |
| [PEP 585](https://peps.python.org/pep-0585/) | Type Hinting Generics In Standard Collections | Final | 3.9 |
| [PEP 604](https://peps.python.org/pep-0604/) | Allow writing union types as X \| Y | Final | 3.10 |
| [PEP 612](https://peps.python.org/pep-0612/) | Parameter Specification Variables | Final | 3.10 |
| [PEP 613](https://peps.python.org/pep-0613/) | Explicit Type Aliases | Final | 3.10 |
| [PEP 673](https://peps.python.org/pep-0673/) | Self Type | Final | 3.11 |
| [PEP 695](https://peps.python.org/pep-0695/) | Type Parameter Syntax | Final | 3.12 |

### C API

| PEP | Title | Status | Python Version |
|-----|-------|--------|----------------|
| [PEP 384](https://peps.python.org/pep-0384/) | Defining a Stable ABI | Final | 3.2 |
| [PEP 573](https://peps.python.org/pep-0573/) | Module State Access from C Extension Methods | Final | 3.9 |
| [PEP 587](https://peps.python.org/pep-0587/) | Python Initialization Configuration | Final | 3.8 |
| [PEP 620](https://peps.python.org/pep-0620/) | Hide implementation details from the C API | Draft | TBD |
| [PEP 652](https://peps.python.org/pep-0652/) | Maintaining the Stable ABI | Final | 3.11 |
| [PEP 670](https://peps.python.org/pep-0670/) | Convert macros to functions in the Python C API | Final | 3.11 |
| [PEP 697](https://peps.python.org/pep-0697/) | Limited C API for Extending Opaque Types | Final | 3.12 |

## Key PEP Deep Dives

### PEP 703: Making the GIL Optional

```
Status: Accepted
Python Version: 3.13+ (experimental)
Author: Sam Gross

Key Mechanisms:
┌─────────────────────────────────────────────────────────────┐
│ 1. Biased Reference Counting                                │
│    - Local ref counts for owner thread (fast path)          │
│    - Shared ref counts for other threads (atomic ops)       │
│                                                             │
│ 2. Immortal Objects                                         │
│    - Objects that never get deallocated                     │
│    - Skip reference counting entirely                       │
│    - Examples: None, True, False, small ints               │
│                                                             │
│ 3. Deferred Reference Counting                              │
│    - Delay refcount updates for certain objects            │
│    - Batch updates to reduce atomic operations             │
│                                                             │
│ 4. Per-Object Locks                                         │
│    - Fine-grained locking for mutable objects              │
│    - Uses mimalloc's lock-free data structures             │
│                                                             │
│ 5. Thread-Safe Memory Allocation                            │
│    - Integration with mimalloc                              │
│    - Per-thread memory pools                               │
└─────────────────────────────────────────────────────────────┘

Build Option: --disable-gil or python3.13t
```

### PEP 659: Specializing Adaptive Interpreter

```
Status: Final
Python Version: 3.11
Author: Mark Shannon

Overview:
┌─────────────────────────────────────────────────────────────┐
│ Quickening Process:                                         │
│                                                             │
│ 1. Generic bytecode executes                                │
│ 2. Runtime collects type information                        │
│ 3. After warmup, instruction gets "quickened"               │
│ 4. Specialized instruction replaces generic one             │
│                                                             │
│ Example:                                                    │
│ BINARY_ADD + (int, int) → BINARY_ADD_INT                   │
│                                                             │
│ Benefits:                                                   │
│ - Skip type checking overhead                               │
│ - Inline small operations                                   │
│ - 10-60% speedup for 3.11                                  │
└─────────────────────────────────────────────────────────────┘
```

### PEP 684: Per-Interpreter GIL

```
Status: Final
Python Version: 3.12
Author: Eric Snow

Key Points:
┌─────────────────────────────────────────────────────────────┐
│ • Each subinterpreter can have its own GIL                  │
│ • True parallelism between interpreters                     │
│ • Limited data sharing (by design)                          │
│                                                             │
│ Limitations:                                                │
│ • Extension modules must opt-in                             │
│ • Communication overhead between interpreters               │
│ • Not all stdlib modules support per-interpreter GIL       │
│                                                             │
│ C API:                                                      │
│   Py_mod_multiple_interpreters slot                         │
│   Py_MOD_PER_INTERPRETER_GIL_SUPPORTED                      │
└─────────────────────────────────────────────────────────────┘
```

### PEP 669: Low Impact Monitoring

```
Status: Final
Python Version: 3.12
Author: Mark Shannon

Purpose:
┌─────────────────────────────────────────────────────────────┐
│ Replaces sys.settrace() with lower overhead monitoring      │
│                                                             │
│ Events:                                                     │
│ - PY_START, PY_RESUME, PY_RETURN, PY_YIELD                  │
│ - CALL, C_RAISE, C_RETURN                                   │
│ - RAISE, EXCEPTION_HANDLED                                  │
│ - LINE, INSTRUCTION, JUMP, BRANCH                           │
│                                                             │
│ API:                                                        │
│   sys.monitoring.use_tool_id(tool_id, name)                 │
│   sys.monitoring.register_callback(tool_id, event, func)   │
│   sys.monitoring.set_events(tool_id, events)               │
│                                                             │
│ Benefits:                                                   │
│ - ~100x less overhead than settrace                         │
│ - Event filtering at C level                                │
│ - Better for production profiling                           │
└─────────────────────────────────────────────────────────────┘
```

## PEP Status Legend

| Status | Description |
|--------|-------------|
| Draft | Under discussion |
| Accepted | Approved, pending implementation |
| Final | Implemented and released |
| Rejected | Proposal rejected |
| Withdrawn | Withdrawn by author |
| Deferred | Postponed for later |
| Superseded | Replaced by another PEP |

## Useful PEP Links

- [PEP Index](https://peps.python.org/)
- [PEP 0 – Index of PEPs](https://peps.python.org/pep-0000/)
- [PEP 1 – PEP Purpose and Guidelines](https://peps.python.org/pep-0001/)
- [Python Developer's Guide](https://devguide.python.org/)

---

[Back to Main Index →](../README.md)

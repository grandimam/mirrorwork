# Chapter 1: CPython Overview

## 1.1 What is CPython

CPython is the reference implementation of the Python programming language. Written in C (and Python itself), it is what most people mean when they say "Python." When you download Python from [python.org](https://python.org), you're getting CPython.

### Key Characteristics

```
┌─────────────────────────────────────────────────────────┐
│                     CPython                              │
├─────────────────────────────────────────────────────────┤
│  • Written in C (with some Python)                      │
│  • Reference implementation                              │
│  • Maintained by Python core developers                  │
│  • Uses bytecode compilation + interpretation            │
│  • Has the Global Interpreter Lock (GIL)                │
│  • Extensive C API for extensions                        │
└─────────────────────────────────────────────────────────┘
```

### Why "CPython"?

The name distinguishes it from other implementations:
- **C** + **Python** = CPython (implemented in C)
- Not to be confused with **Cython** (a compiler for writing C extensions)

### Version History

| Version | Release | Key Features |
|---------|---------|--------------|
| 0.9.0 | 1991 | First public release |
| 1.0 | 1994 | Lambda, map, filter |
| 2.0 | 2000 | List comprehensions, GC |
| 3.0 | 2008 | Unicode by default, print function |
| 3.11 | 2022 | Faster CPython, exception groups |
| 3.12 | 2023 | Per-interpreter GIL |
| 3.13 | 2024 | Free-threaded mode (experimental), JIT |

## 1.2 CPython vs Other Implementations

Python has multiple implementations, each with different characteristics:

### Comparison Table

| Implementation | Language | GIL | JIT | Use Case |
|---------------|----------|-----|-----|----------|
| **CPython** | C | Yes* | Experimental | General purpose |
| **PyPy** | RPython | Yes | Yes | Performance |
| **Jython** | Java | No | JVM JIT | Java integration |
| **IronPython** | C# | No | CLR JIT | .NET integration |
| **GraalPy** | Java | No | GraalVM | Polyglot |
| **MicroPython** | C | No | No | Embedded systems |

*Python 3.13+ has experimental free-threaded mode without GIL

### CPython Advantages

1. **Reference Implementation**: New features appear here first
2. **C Extension Ecosystem**: NumPy, pandas, etc. are CPython extensions
3. **Stability**: Most tested and debugged
4. **Documentation**: Best documented implementation
5. **Community**: Largest community support

### CPython Disadvantages

1. **GIL**: Limits CPU-bound parallelism (being addressed)
2. **Speed**: Slower than JIT implementations for some workloads
3. **Memory**: Higher memory usage than some alternatives

## 1.3 CPython Source Code Structure

The CPython source code is organized into several key directories:

```
cpython/
├── Grammar/           # Python grammar definition
│   └── python.gram    # PEG grammar file
├── Include/           # Public C header files
│   ├── Python.h       # Main include file
│   ├── object.h       # PyObject definition
│   └── cpython/       # CPython-specific headers
├── Lib/               # Standard library (Python)
│   ├── asyncio/
│   ├── collections/
│   └── ...
├── Modules/           # C extension modules
│   ├── _io/
│   ├── _json.c
│   └── ...
├── Objects/           # Built-in object implementations
│   ├── listobject.c   # list type
│   ├── dictobject.c   # dict type
│   ├── longobject.c   # int type
│   └── ...
├── Parser/            # Tokenizer and parser
│   ├── tokenizer.c
│   └── pegen.c        # PEG parser
├── Python/            # Core interpreter
│   ├── ceval.c        # Main evaluation loop
│   ├── compile.c      # Bytecode compiler
│   ├── pystate.c      # Interpreter/thread state
│   └── ceval_gil.c    # GIL implementation
├── Programs/          # Entry points
│   └── python.c       # Main executable
└── Tools/             # Development tools
```

### Key Files to Understand

| File | Purpose |
|------|---------|
| `Python/ceval.c` | The heart of the interpreter - evaluation loop |
| `Python/ceval_gil.c` | GIL implementation |
| `Include/object.h` | `PyObject` structure definition |
| `Objects/dictobject.c` | Dictionary implementation |
| `Python/compile.c` | Bytecode compiler |

## 1.4 Building CPython from Source

Building CPython helps understand its structure and enables experimentation.

### Prerequisites

**Linux (Debian/Ubuntu):**
```bash
sudo apt-get update
sudo apt-get install build-essential gdb lcov pkg-config \
    libbz2-dev libffi-dev libgdbm-dev libgdbm-compat-dev \
    liblzma-dev libncurses5-dev libreadline6-dev libsqlite3-dev \
    libssl-dev lzma lzma-dev tk-dev uuid-dev zlib1g-dev
```

**macOS:**
```bash
xcode-select --install
brew install openssl readline sqlite3 xz zlib
```

### Building Steps

```bash
# Clone the repository
git clone https://github.com/python/cpython.git
cd cpython

# Checkout a specific version (optional)
git checkout v3.12.0

# Configure (debug build for learning)
./configure --with-pydebug

# Build
make -j$(nproc)  # Linux
make -j$(sysctl -n hw.ncpu)  # macOS

# Test (optional but recommended)
make test

# Run your build
./python
```

### Configure Options

| Option | Description |
|--------|-------------|
| `--with-pydebug` | Debug build with assertions |
| `--enable-optimizations` | PGO optimized build |
| `--with-lto` | Link-time optimization |
| `--disable-gil` | Free-threaded build (3.13+) |
| `--enable-shared` | Build shared library |

### Debug Build Benefits

A debug build (`--with-pydebug`) provides:
- Runtime assertions that catch bugs
- Reference count checking
- Memory allocation debugging
- Slower but much more informative errors

```python
# With debug build, you get better error messages
# and can catch reference counting bugs early
```

## 1.5 Python Version History and Evolution

### The Journey of CPython

```
1989: Guido van Rossum starts Python development
  │
1991: Python 0.9.0 released (classes, exceptions, functions)
  │
1994: Python 1.0 (lambda, map, filter, reduce)
  │
2000: Python 2.0 (list comprehensions, garbage collection)
  │   └── GIL becomes significant as multi-core CPUs emerge
  │
2008: Python 3.0 (major breaking changes)
  │   ├── Print becomes a function
  │   ├── Strings are Unicode by default
  │   └── Integer division returns float
  │
2020: Python 2 end of life
  │
2022: Python 3.11 (Faster CPython project begins paying off)
  │   └── 10-60% faster than 3.10
  │
2023: Python 3.12 (Per-interpreter GIL)
  │
2024: Python 3.13 (Experimental free-threaded mode, JIT)
  │
Future: Full free-threading support planned
```

### Major Milestones for Internals

| Version | Internal Change |
|---------|-----------------|
| 2.0 | Garbage collection added |
| 3.2 | New GIL implementation (time-based) |
| 3.4 | `asyncio` added to stdlib |
| 3.6 | Compact dict implementation |
| 3.9 | New PEG parser |
| 3.11 | Specializing adaptive interpreter |
| 3.12 | Per-interpreter GIL (PEP 684) |
| 3.13 | Free-threaded mode (PEP 703), Copy-and-patch JIT |

## Summary

- CPython is the reference Python implementation, written in C
- It compiles Python source to bytecode, then interprets it
- The GIL is a key characteristic (being addressed in recent versions)
- Understanding the source structure helps navigate the codebase
- Building from source enables experimentation and learning

## Further Reading

- [CPython Developer Guide](https://devguide.python.org/)
- [CPython Source Code](https://github.com/python/cpython)
- [What's New in Python](https://docs.python.org/3/whatsnew/)

---

[Next Chapter: Python Execution Model →](chapter-02-execution-model.md)

# Chapter 6: Bytecode Compilation

## 6.1 The `compile()` Built-in

The `compile()` function converts source code (or an AST) into a code object:

```python
# Basic usage
code_obj = compile(source, filename, mode)

# Parameters:
# - source: String, bytes, or AST object
# - filename: Used in error messages and tracebacks
# - mode: 'exec' (module), 'eval' (expression), 'single' (interactive)
```

### Compilation Examples

```python
# Compile a module
module_code = compile("""
x = 1
y = 2
print(x + y)
""", "example.py", "exec")

# Compile an expression
expr_code = compile("1 + 2 * 3", "<expr>", "eval")

# Compile from AST
import ast
tree = ast.parse("x = 42")
ast_code = compile(tree, "<ast>", "exec")
```

### Compilation Flags

```python
import ast

# Available flags
flags = {
    ast.PyCF_ONLY_AST: "Return AST instead of code object",
    ast.PyCF_TYPE_COMMENTS: "Enable type comment parsing",
    ast.PyCF_ALLOW_TOP_LEVEL_AWAIT: "Allow await at top level",
}

# Using flags
tree = compile("x = 1", "", "exec", flags=ast.PyCF_ONLY_AST)
# Returns AST, not code object
```

## 6.2 Code Object Structure

A code object (`PyCodeObject` in C) contains everything needed to execute a function or module:

```python
def example(a, b):
    """Example function."""
    x = a + b
    return x * 2

code = example.__code__
```

### Code Object Attributes

```python
# Get all code object attributes
for attr in dir(code):
    if attr.startswith('co_'):
        print(f"{attr}: {getattr(code, attr)}")
```

### 6.2.1 `co_code` - Bytecode Instructions

```python
# Raw bytecode bytes
print(code.co_code)
# b'd\x01}\x02|\x02d\x02\x14\x00S\x00'

# Human-readable with dis
import dis
dis.dis(code)
```

### 6.2.2 `co_consts` - Constants

```python
print(code.co_consts)
# (None, 2, 'Example function.')

# Constants include:
# - None (default return)
# - Numeric literals
# - String literals
# - Tuple literals (at compile time)
# - Nested code objects (for nested functions)
```

### 6.2.3 `co_varnames` - Local Variables

```python
print(code.co_varnames)
# ('a', 'b', 'x')

# Order: parameters first, then locals
# This allows fast indexing with LOAD_FAST
```

### 6.2.4 `co_names` - Global Names

```python
def example():
    print(len(data))  # print, len, data are global names

print(example.__code__.co_names)
# ('print', 'len', 'data')
```

### 6.2.5 `co_freevars` and `co_cellvars` - Closures

```python
def outer():
    x = 1  # x is a cell variable in outer
    def inner():
        return x  # x is a free variable in inner
    return inner

outer_code = outer.__code__
inner_code = outer_code.co_consts[1]  # Nested code object

print(f"outer co_cellvars: {outer_code.co_cellvars}")  # ('x',)
print(f"inner co_freevars: {inner_code.co_freevars}")  # ('x',)
```

### Complete Code Object Reference

| Attribute | Description |
|-----------|-------------|
| `co_argcount` | Number of positional/keyword arguments |
| `co_posonlyargcount` | Number of positional-only arguments |
| `co_kwonlyargcount` | Number of keyword-only arguments |
| `co_nlocals` | Number of local variables |
| `co_stacksize` | Required stack size |
| `co_flags` | Flags (generator, coroutine, etc.) |
| `co_code` | Bytecode instructions |
| `co_consts` | Tuple of constants |
| `co_names` | Tuple of global names |
| `co_varnames` | Tuple of local variable names |
| `co_freevars` | Tuple of free variables (closures) |
| `co_cellvars` | Tuple of cell variables (closures) |
| `co_filename` | Source filename |
| `co_name` | Function/class name |
| `co_qualname` | Qualified name (3.11+) |
| `co_firstlineno` | First line number |
| `co_linetable` | Line number table |

## 6.3 `.pyc` Files and `__pycache__`

Python caches compiled bytecode to speed up subsequent imports:

```
project/
├── module.py
└── __pycache__/
    └── module.cpython-312.pyc
```

### `.pyc` File Format

```
┌─────────────────────────────────────────────────────────────────┐
│                      .pyc File Structure                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Offset  │ Size   │ Content                                     │
│  ────────┼────────┼─────────────────────────────────            │
│  0       │ 4      │ Magic number (version-specific)             │
│  4       │ 4      │ Bit field (PEP 552)                         │
│  8       │ 4      │ Modification timestamp                       │
│  12      │ 4      │ Source file size                            │
│  16      │ ...    │ Marshalled code object                      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Reading `.pyc` Files

```python
import marshal
import struct

def read_pyc(filepath):
    """Read a .pyc file and return the code object."""
    with open(filepath, 'rb') as f:
        magic = f.read(4)
        bit_field = struct.unpack('<I', f.read(4))[0]
        timestamp = struct.unpack('<I', f.read(4))[0]
        size = struct.unpack('<I', f.read(4))[0]
        code = marshal.load(f)
    return code

# Usage
# code = read_pyc('__pycache__/module.cpython-312.pyc')
```

### Controlling `.pyc` Generation

```bash
# Don't write .pyc files
python -B script.py
# or
export PYTHONDONTWRITEBYTECODE=1

# Specify cache directory
export PYTHONPYCACHEPREFIX=/tmp/pycache
```

## 6.4 Bytecode Versioning (Magic Numbers)

Each Python version has a unique magic number:

```python
import importlib.util

# Get current magic number
magic = importlib.util.MAGIC_NUMBER
print(f"Magic: {magic.hex()}")
```

### Magic Number History

| Python Version | Magic Number |
|----------------|--------------|
| 3.8 | 3413 |
| 3.9 | 3425 |
| 3.10 | 3439 |
| 3.11 | 3495 |
| 3.12 | 3531 |
| 3.13 | 3570 |

### Why Magic Numbers Change

- New bytecode instructions added
- Instruction format changes
- Code object structure changes
- Ensures incompatible `.pyc` files are rejected

## 6.5 The `marshal` Module

`marshal` is Python's internal serialization format for code objects:

```python
import marshal

def example():
    return 42

# Serialize code object
data = marshal.dumps(example.__code__)

# Deserialize
code = marshal.loads(data)

# Create function from code
import types
new_func = types.FunctionType(code, globals())
print(new_func())  # 42
```

### Marshal vs Pickle

| Feature | marshal | pickle |
|---------|---------|--------|
| Purpose | Code objects | General objects |
| Security | Internal use | Untrusted data risk |
| Stability | Not guaranteed across versions | More stable |
| Speed | Fast | Slower |
| Types | Limited | Extensive |

### Warning About marshal

```python
# DON'T use marshal for:
# - Data exchange between systems
# - Long-term storage
# - Untrusted data

# DO use marshal for:
# - Internal Python bytecode caching
# - Implementing your own code cache
```

## Bytecode Compilation Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                  Bytecode Compilation Pipeline                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  AST (from parser)                                               │
│       │                                                          │
│       ▼                                                          │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              Symbol Table Builder                        │    │
│  │  - Determine variable scopes (local/global/free/cell)   │    │
│  │  - Detect syntax errors (undefined names, etc.)         │    │
│  └─────────────────────────────────────────────────────────┘    │
│       │                                                          │
│       ▼                                                          │
│  Symbol Table                                                    │
│       │                                                          │
│       ▼                                                          │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                   Code Generator                         │    │
│  │  - Walk AST and emit bytecode instructions              │    │
│  │  - Build code object attributes                          │    │
│  └─────────────────────────────────────────────────────────┘    │
│       │                                                          │
│       ▼                                                          │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                  Peephole Optimizer                      │    │
│  │  - Constant folding                                      │    │
│  │  - Dead code elimination                                 │    │
│  │  - Instruction simplification                            │    │
│  └─────────────────────────────────────────────────────────┘    │
│       │                                                          │
│       ▼                                                          │
│  Code Object                                                     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Inspecting the Compilation Process

```python
import symtable
import dis

source = """
x = 1
def outer():
    y = 2
    def inner():
        return x + y
    return inner
"""

# Get symbol table
st = symtable.symtable(source, '<string>', 'exec')

def show_symbols(table, indent=0):
    """Recursively show symbol table."""
    prefix = "  " * indent
    print(f"{prefix}Scope: {table.get_name()} ({table.get_type()})")
    for sym in table.get_symbols():
        flags = []
        if sym.is_local(): flags.append("local")
        if sym.is_global(): flags.append("global")
        if sym.is_free(): flags.append("free")
        if sym.is_cell(): flags.append("cell")
        print(f"{prefix}  {sym.get_name()}: {', '.join(flags)}")
    for child in table.get_children():
        show_symbols(child, indent + 1)

show_symbols(st)
```

Output:
```
Scope: top (module)
  x: local
  outer: local
  Scope: outer (function)
    y: local, cell
    inner: local
    Scope: inner (function)
      x: global
      y: free
```

## Summary

- `compile()` converts source/AST to code objects
- Code objects contain bytecode and metadata
- `.pyc` files cache compiled bytecode
- Magic numbers ensure version compatibility
- `marshal` serializes code objects
- Symbol tables determine variable scopes

## Practice Exercises

1. Inspect code objects for different functions and compare attributes
2. Write a tool that extracts all constants from a Python file
3. Create a custom import hook that logs all `.pyc` operations
4. Analyze how closures affect `co_freevars` and `co_cellvars`

---

[← Previous: Abstract Syntax Tree](chapter-05-ast.md) | [Next: Bytecode Instructions →](chapter-07-bytecode-instructions.md)

# Chapter 7: Bytecode Instructions

## 7.1 Stack-Based Virtual Machine Model

Python's virtual machine uses a **stack-based** architecture. All operations manipulate a value stack:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Stack-Based Execution                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Expression: 3 + 4 * 2                                          │
│                                                                  │
│  Step 1: LOAD_CONST 3        Step 2: LOAD_CONST 4               │
│  Stack: [3]                  Stack: [3, 4]                       │
│                                                                  │
│  Step 3: LOAD_CONST 2        Step 4: BINARY_MULTIPLY            │
│  Stack: [3, 4, 2]            Stack: [3, 8]  (4*2=8)             │
│                                                                  │
│  Step 5: BINARY_ADD                                              │
│  Stack: [11]  (3+8=11)                                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Stack vs Register-Based VMs

| Feature | Stack-Based (Python) | Register-Based (Lua) |
|---------|---------------------|---------------------|
| Operand location | Implicit (stack top) | Explicit (register names) |
| Instruction size | Smaller | Larger |
| Instruction count | More | Fewer |
| Implementation | Simpler | More complex |

### The Value Stack

```python
# Each frame has its own stack
# Stack size is determined at compile time

def example():
    x = 1 + 2  # Stack grows and shrinks here
    return x

print(example.__code__.co_stacksize)  # Maximum stack depth needed
```

## 7.2 Opcode Categories

### 7.2.1 Stack Manipulation

| Opcode | Effect | Stack Before → After |
|--------|--------|---------------------|
| `POP_TOP` | Discard TOS | `[a]` → `[]` |
| `DUP_TOP` | Duplicate TOS | `[a]` → `[a, a]` |
| `DUP_TOP_TWO` | Duplicate top two | `[a, b]` → `[a, b, a, b]` |
| `ROT_TWO` | Swap top two | `[a, b]` → `[b, a]` |
| `ROT_THREE` | Rotate three | `[a, b, c]` → `[c, a, b]` |
| `ROT_FOUR` | Rotate four | `[a, b, c, d]` → `[d, a, b, c]` |

```python
import dis

# DUP_TOP example
dis.dis(compile("x = y = 1", "", "exec"))
#   LOAD_CONST 0 (1)
#   DUP_TOP           # Duplicate for multiple assignment
#   STORE_NAME 0 (y)
#   STORE_NAME 1 (x)
```

### 7.2.2 Load/Store Operations

```python
import dis

# Different LOAD instructions
code = """
global_var = 1  # STORE_NAME at module level

def example(param):  # param uses LOAD_FAST
    local = 2        # STORE_FAST
    return global_var + local + param  # Different loads
"""

exec(compile(code, "", "exec"))
dis.dis(example)
```

| Opcode | Purpose | Speed |
|--------|---------|-------|
| `LOAD_CONST` | Load constant | Fastest |
| `LOAD_FAST` | Load local variable | Fast (indexed) |
| `LOAD_GLOBAL` | Load global/builtin | Slower (name lookup) |
| `LOAD_NAME` | Load by name | Slowest |
| `LOAD_DEREF` | Load from closure | Moderate |
| `LOAD_ATTR` | Load attribute | Slow |

```python
import dis

def example():
    # LOAD_FAST is faster than LOAD_GLOBAL
    x = len  # LOAD_GLOBAL
    local_len = len
    for i in range(1000):
        local_len([1, 2, 3])  # LOAD_FAST (faster in loops)

dis.dis(example)
```

### 7.2.3 Binary Operations

```python
import dis

# Arithmetic operations
dis.dis(compile("a + b", "", "eval"))  # BINARY_ADD
dis.dis(compile("a - b", "", "eval"))  # BINARY_SUBTRACT
dis.dis(compile("a * b", "", "eval"))  # BINARY_MULTIPLY
dis.dis(compile("a / b", "", "eval"))  # BINARY_TRUE_DIVIDE
dis.dis(compile("a // b", "", "eval")) # BINARY_FLOOR_DIVIDE
dis.dis(compile("a % b", "", "eval"))  # BINARY_MODULO
dis.dis(compile("a ** b", "", "eval")) # BINARY_POWER
dis.dis(compile("a @ b", "", "eval"))  # BINARY_MATRIX_MULTIPLY

# Bitwise operations
dis.dis(compile("a & b", "", "eval"))  # BINARY_AND
dis.dis(compile("a | b", "", "eval"))  # BINARY_OR
dis.dis(compile("a ^ b", "", "eval"))  # BINARY_XOR
dis.dis(compile("a << b", "", "eval")) # BINARY_LSHIFT
dis.dis(compile("a >> b", "", "eval")) # BINARY_RSHIFT

# Subscript operations
dis.dis(compile("a[b]", "", "eval"))   # BINARY_SUBSCR
```

### 7.2.4 Control Flow

```python
import dis

# Conditional jump
def example(x):
    if x > 0:
        return "positive"
    else:
        return "non-positive"

dis.dis(example)
```

| Opcode | Description |
|--------|-------------|
| `JUMP_FORWARD` | Unconditional forward jump |
| `JUMP_BACKWARD` | Unconditional backward jump |
| `POP_JUMP_IF_TRUE` | Jump if TOS is true, pop |
| `POP_JUMP_IF_FALSE` | Jump if TOS is false, pop |
| `JUMP_IF_TRUE_OR_POP` | Jump if true, else pop |
| `JUMP_IF_FALSE_OR_POP` | Jump if false, else pop |
| `FOR_ITER` | Iterate, jump when exhausted |

```python
# Loop example
def loop_example():
    for i in range(3):
        print(i)

dis.dis(loop_example)
# GET_ITER
# FOR_ITER (to end)
# ... body ...
# JUMP_BACKWARD (to FOR_ITER)
```

### 7.2.5 Function Calls

```python
import dis

# Simple call
dis.dis(compile("func()", "", "eval"))
# PUSH_NULL
# LOAD_NAME (func)
# CALL 0

# Call with arguments
dis.dis(compile("func(a, b)", "", "eval"))
# PUSH_NULL
# LOAD_NAME (func)
# LOAD_NAME (a)
# LOAD_NAME (b)
# CALL 2

# Call with keyword arguments
dis.dis(compile("func(a, b=1)", "", "eval"))
# PUSH_NULL
# LOAD_NAME (func)
# LOAD_NAME (a)
# LOAD_CONST (1)
# KW_NAMES (('b',))
# CALL 2
```

### 7.2.6 Class Operations

```python
import dis

code = """
class MyClass:
    x = 1
    def method(self):
        pass
"""

dis.dis(compile(code, "", "exec"))
# PUSH_NULL
# LOAD_BUILD_CLASS
# ... class body as function ...
# CALL
# STORE_NAME (MyClass)
```

## 7.3 The `dis` Module

The `dis` module is your window into bytecode:

### Basic Disassembly

```python
import dis

def example(x, y):
    """Add two numbers."""
    return x + y

# Disassemble function
dis.dis(example)

# Disassemble with more detail
dis.dis(example, show_caches=True)  # Python 3.11+

# Get instruction objects
for instr in dis.get_instructions(example):
    print(f"{instr.offset:4d} {instr.opname:20s} {instr.argrepr}")
```

### Instruction Object Attributes

```python
import dis

def example(x):
    return x + 1

for instr in dis.get_instructions(example):
    print(f"""
    Offset: {instr.offset}
    Opcode: {instr.opcode}
    Opname: {instr.opname}
    Arg: {instr.arg}
    Argval: {instr.argval}
    Argrepr: {instr.argrepr}
    Line: {instr.starts_line}
    """)
```

### Bytecode Object

```python
import dis

def example(x):
    if x > 0:
        return x * 2
    return 0

bytecode = dis.Bytecode(example)

print(f"Code info:\n{bytecode.info()}")
print(f"\nDisassembly:")
for instr in bytecode:
    print(instr)
```

## 7.4 Stack Effects per Instruction

Each instruction has a defined effect on the stack:

```python
import dis

# Get stack effect of an instruction
print(dis.stack_effect(dis.opmap['LOAD_CONST'], 0))   # +1 (pushes)
print(dis.stack_effect(dis.opmap['BINARY_ADD']))       # -1 (pops 2, pushes 1)
print(dis.stack_effect(dis.opmap['POP_TOP']))          # -1 (pops)
print(dis.stack_effect(dis.opmap['DUP_TOP']))          # +1 (duplicates)
```

### Stack Effect Reference

| Category | Examples | Effect |
|----------|----------|--------|
| Load | `LOAD_CONST`, `LOAD_FAST` | +1 |
| Store | `STORE_FAST`, `STORE_NAME` | -1 |
| Binary ops | `BINARY_ADD`, `BINARY_MULTIPLY` | -1 (2→1) |
| Unary ops | `UNARY_NOT`, `UNARY_NEGATIVE` | 0 (1→1) |
| Build | `BUILD_LIST n` | -(n-1) |
| Call | `CALL n` | -n |

## 7.5 Instruction Arguments and Extended Args

### Instruction Format

```
┌─────────────────────────────────────────────────────────────────┐
│                   Instruction Format                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Standard instruction (2 bytes):                                 │
│  ┌──────────┬──────────┐                                        │
│  │  Opcode  │   Arg    │                                        │
│  │ (1 byte) │ (1 byte) │                                        │
│  └──────────┴──────────┘                                        │
│                                                                  │
│  Extended argument (for args > 255):                            │
│  ┌──────────┬──────────┬──────────┬──────────┐                 │
│  │EXTENDED_ │ High bits│  Opcode  │ Low bits │                 │
│  │   ARG    │          │          │          │                 │
│  └──────────┴──────────┴──────────┴──────────┘                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### EXTENDED_ARG Example

```python
import dis

# Create a function with many constants to trigger EXTENDED_ARG
code = "x = (" + ", ".join(str(i) for i in range(300)) + ")"
compiled = compile(code, "", "exec")

# Look for EXTENDED_ARG
for instr in dis.get_instructions(compiled):
    if instr.opname == 'EXTENDED_ARG':
        print(f"Found EXTENDED_ARG at offset {instr.offset}")
        break
```

### Argument Types

| Opcode Type | Argument Meaning |
|-------------|-----------------|
| `LOAD_CONST` | Index into `co_consts` |
| `LOAD_FAST` | Index into `co_varnames` |
| `LOAD_GLOBAL` | Index into `co_names` |
| `JUMP_*` | Target offset |
| `BUILD_*` | Count of items |
| `CALL` | Argument count |

## Python 3.11+ Instruction Changes

Python 3.11 introduced significant bytecode changes:

### Quickened Instructions

```python
# Python 3.11+ has adaptive/specialized instructions
# LOAD_GLOBAL can become:
# - LOAD_GLOBAL_MODULE (module attribute)
# - LOAD_GLOBAL_BUILTIN (builtin function)

# BINARY_OP can become:
# - BINARY_OP_ADD_INT
# - BINARY_OP_ADD_FLOAT
# - etc.
```

### Inline Caches

```python
import dis

def example():
    return len([1, 2, 3])

# Python 3.11+ shows cache entries
dis.dis(example, show_caches=True)
# CACHE entries follow instructions for specialization data
```

## Summary

- Python uses a **stack-based** virtual machine
- Instructions manipulate the **value stack**
- Different **LOAD_** instructions for different scopes
- The `dis` module reveals bytecode structure
- **EXTENDED_ARG** handles large arguments
- Python 3.11+ has **specialized instructions**

## Practice Exercises

1. Disassemble various expressions and trace stack operations
2. Compare bytecode for equivalent code written differently
3. Find the most common opcodes in a large Python file
4. Write a bytecode interpreter simulator for simple operations

---

[← Previous: Bytecode Compilation](chapter-06-bytecode-compilation.md) | [Next: Bytecode Optimization →](chapter-08-bytecode-optimization.md)

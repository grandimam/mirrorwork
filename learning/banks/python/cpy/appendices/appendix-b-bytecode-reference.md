# Appendix B: Bytecode Reference

## Bytecode Overview

Python bytecode is the intermediate representation executed by the Python Virtual Machine. This reference covers Python 3.11+ bytecode instructions.

## Instruction Format

```
┌─────────────────────────────────────────────────────────────┐
│ Python 3.11+ Instruction Format (16-bit words)              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌────────┬────────┐                                        │
│  │ opcode │  arg   │  Standard instruction (2 bytes)       │
│  │ 8 bits │ 8 bits │                                        │
│  └────────┴────────┘                                        │
│                                                             │
│  Extended argument (EXTENDED_ARG):                          │
│  ┌────────┬────────┬────────┬────────┐                      │
│  │EXTENDED│ high   │ opcode │  low   │                      │
│  │  ARG   │ 8 bits │        │ 8 bits │                      │
│  └────────┴────────┴────────┴────────┘                      │
│  Final arg = (high << 8) | low                              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Instruction Categories

### Stack Operations

| Opcode | Name | Stack Effect | Description |
|--------|------|--------------|-------------|
| 0 | CACHE | (0) | Placeholder for adaptive specialization |
| 1 | POP_TOP | (-1) | Remove top of stack |
| 2 | PUSH_NULL | (+1) | Push NULL onto stack |
| 3 | NOP | (0) | No operation |
| 4 | UNARY_POSITIVE | (0) | `TOS = +TOS` |
| 5 | UNARY_NEGATIVE | (0) | `TOS = -TOS` |
| 6 | UNARY_NOT | (0) | `TOS = not TOS` |
| 9 | UNARY_INVERT | (0) | `TOS = ~TOS` |

### Binary Operations (Python 3.11+)

| Opcode | Name | Stack Effect | Description |
|--------|------|--------------|-------------|
| 122 | BINARY_OP | (-1) | `TOS = TOS1 op TOS` |

**BINARY_OP sub-operations (arg):**
| Arg | Operation |
|-----|-----------|
| 0 | ADD (+) |
| 1 | AND (&) |
| 2 | FLOOR_DIVIDE (//) |
| 3 | LSHIFT (<<) |
| 4 | MATMUL (@) |
| 5 | MULTIPLY (*) |
| 6 | REMAINDER (%) |
| 7 | OR (\|) |
| 8 | POWER (**) |
| 9 | RSHIFT (>>) |
| 10 | SUBTRACT (-) |
| 11 | TRUE_DIVIDE (/) |
| 12 | XOR (^) |
| 13 | INPLACE_ADD (+=) |
| ... | ... |

### Load/Store Operations

| Opcode | Name | Stack Effect | Description |
|--------|------|--------------|-------------|
| 100 | LOAD_CONST | (+1) | Push `co_consts[arg]` |
| 101 | LOAD_NAME | (+1) | Push `name` from namespaces |
| 102 | BUILD_TUPLE | (-arg+1) | Build tuple from stack |
| 103 | BUILD_LIST | (-arg+1) | Build list from stack |
| 104 | BUILD_SET | (-arg+1) | Build set from stack |
| 105 | BUILD_MAP | (-2*arg+1) | Build dict from stack pairs |
| 106 | LOAD_ATTR | (0 or +1) | `TOS = TOS.attr` |
| 107 | COMPARE_OP | (-1) | Comparison operations |
| 108 | IMPORT_NAME | (-1) | Import module |
| 109 | IMPORT_FROM | (+1) | Import attribute from module |
| 116 | LOAD_GLOBAL | (+1 or +2) | Load global variable |
| 124 | LOAD_FAST | (+1) | Load local variable |
| 125 | STORE_FAST | (-1) | Store local variable |
| 126 | DELETE_FAST | (0) | Delete local variable |
| 136 | LOAD_DEREF | (+1) | Load from closure |
| 137 | STORE_DEREF | (-1) | Store to closure |
| 138 | DELETE_DEREF | (0) | Delete from closure |

### Control Flow

| Opcode | Name | Stack Effect | Description |
|--------|------|--------------|-------------|
| 93 | FOR_ITER | (+1 or -1) | Get next from iterator |
| 114 | POP_JUMP_IF_FALSE | (-1) | Jump if TOS is false |
| 115 | POP_JUMP_IF_TRUE | (-1) | Jump if TOS is true |
| 110 | JUMP_FORWARD | (0) | Jump forward by arg |
| 140 | JUMP_BACKWARD | (0) | Jump backward by arg |
| 171 | JUMP_BACKWARD_NO_INTERRUPT | (0) | Jump without interrupt check |

### Function Calls

| Opcode | Name | Stack Effect | Description |
|--------|------|--------------|-------------|
| 166 | PRECALL | (0) | Prepare for call |
| 171 | CALL | (-arg-1+1) | Call function |
| 132 | MAKE_FUNCTION | (-1-flags+1) | Create function object |
| 83 | RETURN_VALUE | (-1) | Return from function |
| 86 | YIELD_VALUE | (0) | Yield from generator |
| 75 | GET_AWAITABLE | (0) | Get awaitable |
| 72 | GET_AITER | (0) | Get async iterator |
| 73 | GET_ANEXT | (+1) | Get next from async iterator |

### Exception Handling

| Opcode | Name | Stack Effect | Description |
|--------|------|--------------|-------------|
| 49 | WITH_EXCEPT_START | (+1) | Start exception handling |
| 35 | BEFORE_WITH | (+1) | Prepare with block |
| 121 | PUSH_EXC_INFO | (+1) | Push exception info |
| 89 | POP_EXCEPT | (-1) | Pop exception handler |
| 119 | RERAISE | (-3) | Re-raise exception |
| 55 | RAISE_VARARGS | (-arg) | Raise exception |

### Specialized/Adaptive Instructions (Python 3.11+)

```
┌─────────────────────────────────────────────────────────────┐
│ Adaptive Specialization                                      │
├─────────────────────────────────────────────────────────────┤
│ Python 3.11+ uses adaptive specialization where generic     │
│ instructions are replaced with specialized versions based   │
│ on observed runtime types.                                  │
│                                                             │
│ Example: BINARY_OP                                          │
│   → BINARY_OP_ADD_INT (for int + int)                       │
│   → BINARY_OP_ADD_FLOAT (for float + float)                 │
│   → BINARY_OP_ADD_UNICODE (for str + str)                   │
│                                                             │
│ Specialization happens automatically after warmup.          │
└─────────────────────────────────────────────────────────────┘
```

| Specialized Opcode | Base | Specialization |
|-------------------|------|----------------|
| BINARY_OP_ADD_INT | BINARY_OP | int + int |
| BINARY_OP_ADD_FLOAT | BINARY_OP | float + float |
| BINARY_OP_ADD_UNICODE | BINARY_OP | str + str |
| BINARY_OP_SUBTRACT_INT | BINARY_OP | int - int |
| BINARY_OP_MULTIPLY_INT | BINARY_OP | int * int |
| LOAD_ATTR_INSTANCE_VALUE | LOAD_ATTR | Instance attribute |
| LOAD_ATTR_MODULE | LOAD_ATTR | Module attribute |
| LOAD_ATTR_SLOT | LOAD_ATTR | Slot attribute |
| LOAD_GLOBAL_MODULE | LOAD_GLOBAL | Module global |
| LOAD_GLOBAL_BUILTIN | LOAD_GLOBAL | Builtin |
| STORE_ATTR_INSTANCE_VALUE | STORE_ATTR | Instance attribute |
| STORE_ATTR_SLOT | STORE_ATTR | Slot attribute |
| CALL_PY_EXACT_ARGS | CALL | Python function |
| CALL_PY_WITH_DEFAULTS | CALL | Python with defaults |
| CALL_BUILTIN_CLASS | CALL | Builtin class call |
| CALL_BUILTIN_O | CALL | Builtin with 1 arg |
| COMPARE_OP_INT | COMPARE_OP | int comparison |
| COMPARE_OP_FLOAT | COMPARE_OP | float comparison |
| COMPARE_OP_STR | COMPARE_OP | str comparison |

## Code Object Structure

```python
# Accessing bytecode from code object
def example(x, y):
    return x + y

code = example.__code__

# Key attributes
code.co_code        # Raw bytecode bytes
code.co_consts      # Constant pool
code.co_names       # Names used
code.co_varnames    # Local variable names
code.co_freevars    # Free variables (closures)
code.co_cellvars    # Cell variables
code.co_stacksize   # Maximum stack depth needed
code.co_argcount    # Number of positional args
code.co_kwonlyargcount  # Number of keyword-only args
```

## Disassembly Example

```python
import dis

def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)

dis.dis(factorial)
```

Output:
```
  2           0 RESUME                   0

  3           2 LOAD_FAST                0 (n)
              4 LOAD_CONST               1 (1)
              6 COMPARE_OP               1 (<=)
             10 POP_JUMP_IF_FALSE       10 (to 22)

  4          12 LOAD_CONST               1 (1)
             14 RETURN_VALUE

  5     >>   16 LOAD_FAST                0 (n)
             18 LOAD_GLOBAL              1 (NULL + factorial)
             28 LOAD_FAST                0 (n)
             30 LOAD_CONST               1 (1)
             32 BINARY_OP               10 (-)
             36 PRECALL                  1
             40 CALL                     1
             50 BINARY_OP                5 (*)
             54 RETURN_VALUE
```

## Stack Effects Quick Reference

```
┌───────────────────────────────────────────────────┐
│ Stack Notation:                                    │
│   (+n)  - Pushes n items onto stack               │
│   (-n)  - Pops n items from stack                 │
│   (0)   - No net change                           │
│                                                   │
│ Common Patterns:                                  │
│   LOAD_*    : (+1)  Push one item                 │
│   STORE_*   : (-1)  Pop one item                  │
│   BINARY_OP : (-1)  Pop 2, push 1 = net -1        │
│   CALL n    : (-(n+1)+1) Pop func+args, push ret  │
│   BUILD_*   : Pop items, push container           │
└───────────────────────────────────────────────────┘
```

## Bytecode Changes by Version

| Version | Notable Changes |
|---------|----------------|
| 3.6 | Word-code (16-bit instructions) |
| 3.10 | Pattern matching opcodes |
| 3.11 | Adaptive specialization, BINARY_OP unification |
| 3.12 | Comprehension inlining |
| 3.13 | JIT compilation support |

## Useful dis Module Functions

```python
import dis

# Disassemble function
dis.dis(func)

# Get instruction objects
list(dis.get_instructions(func))

# Show code info
dis.show_code(func)

# Disassemble bytecode string
dis.disassemble(code_object)

# Get stack effect of opcode
dis.stack_effect(opcode, arg)
```

---

[Back to Main Index →](../README.md)

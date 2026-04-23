# Chapter 2: Python Execution Model

## 2.1 From Source Code to Execution

When you run a Python program, it goes through several stages before producing results:

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ Source Code  │───▶│    Lexer     │───▶│   Parser     │───▶│     AST      │
│   (.py)      │    │  (Tokens)    │    │              │    │              │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
                                                                   │
                                                                   ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Results    │◀───│     PVM      │◀───│   Bytecode   │◀───│   Compiler   │
│              │    │ (Execution)  │    │   (.pyc)     │    │              │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
```

### Stage 1: Lexical Analysis (Tokenization)

The source code is broken into tokens:

```python
# Source code
x = 42 + y

# Tokens produced:
# NAME 'x'
# EQUAL '='
# NUMBER '42'
# PLUS '+'
# NAME 'y'
# NEWLINE
```

You can see tokens using the `tokenize` module:

```python
import tokenize
import io

code = "x = 42 + y"
tokens = tokenize.generate_tokens(io.StringIO(code).readline)
for tok in tokens:
    print(tok)
```

### Stage 2: Parsing

Tokens are organized into a parse tree following Python's grammar:

```
        =
       / \
      x   +
         / \
        42  y
```

### Stage 3: AST (Abstract Syntax Tree)

The parse tree is converted to an AST, a cleaner representation:

```python
import ast

code = "x = 42 + y"
tree = ast.parse(code)
print(ast.dump(tree, indent=2))
```

Output:
```
Module(
  body=[
    Assign(
      targets=[Name(id='x', ctx=Store())],
      value=BinOp(
        left=Constant(value=42),
        op=Add(),
        right=Name(id='y', ctx=Load())
      )
    )
  ],
  type_ignores=[]
)
```

### Stage 4: Bytecode Compilation

The AST is compiled to bytecode instructions:

```python
import dis

code = "x = 42 + y"
compiled = compile(code, '<string>', 'exec')
dis.dis(compiled)
```

Output:
```
  1           0 LOAD_CONST               0 (42)
              2 LOAD_NAME                0 (y)
              4 BINARY_ADD
              6 STORE_NAME               1 (x)
              8 LOAD_CONST               1 (None)
             10 RETURN_VALUE
```

### Stage 5: Execution (PVM)

The Python Virtual Machine executes bytecode instructions using a stack-based model:

```
Stack operations for: x = 42 + y (assuming y = 8)

LOAD_CONST 42:    Stack: [42]
LOAD_NAME y:      Stack: [42, 8]
BINARY_ADD:       Stack: [50]        # Pops two, pushes result
STORE_NAME x:     Stack: []          # Pops value, stores in 'x'
```

## 2.2 Interactive Interpreter vs Script Execution

### Interactive Mode (REPL)

```python
$ python
>>> x = 1 + 2
>>> x
3
```

In interactive mode:
1. Each line is compiled and executed immediately
2. Expression results are automatically printed
3. `_` holds the last result
4. Compilation mode is `'single'`

```python
# Interactive mode uses 'single' mode
code = compile("1 + 2", "<stdin>", "single")
exec(code)  # Prints: 3
```

### Script Execution

```python
$ python script.py
```

In script mode:
1. Entire file is compiled at once
2. Results are not auto-printed
3. Compilation mode is `'exec'`

```python
# Script mode uses 'exec' mode
code = compile("1 + 2", "script.py", "exec")
exec(code)  # No output (expression result discarded)
```

### Compilation Modes

| Mode | Purpose | Auto-print |
|------|---------|------------|
| `'exec'` | Module/script execution | No |
| `'eval'` | Single expression | Returns value |
| `'single'` | Interactive statement | Yes |

```python
# eval mode - for expressions
result = eval(compile("1 + 2", "", "eval"))
print(result)  # 3

# exec mode - for statements
exec(compile("x = 1 + 2", "", "exec"))
print(x)  # 3

# single mode - interactive behavior
exec(compile("1 + 2", "", "single"))  # Prints: 3
```

## 2.3 The `__main__` Module

When Python runs a script, it sets up a special module called `__main__`:

```python
# script.py
print(__name__)  # Output: __main__
print(__file__)  # Output: script.py
```

### The `if __name__ == "__main__"` Pattern

```python
# mymodule.py

def main():
    print("Running as main program")

def helper():
    return 42

if __name__ == "__main__":
    main()
```

**Why this works:**

```python
# When run directly:
$ python mymodule.py
# __name__ is "__main__" → main() executes

# When imported:
>>> import mymodule
# __name__ is "mymodule" → main() doesn't execute
```

### `__main__.py` for Packages

Packages can have a `__main__.py` for direct execution:

```
mypackage/
├── __init__.py
├── __main__.py    # Runs with: python -m mypackage
└── core.py
```

```python
# mypackage/__main__.py
from . import core

if __name__ == "__main__":
    core.run()
```

```bash
python -m mypackage  # Executes __main__.py
```

## 2.4 REPL Internals

The Read-Eval-Print Loop (REPL) is implemented in `Lib/code.py`:

```
┌─────────────────────────────────────────┐
│               REPL Loop                  │
├─────────────────────────────────────────┤
│                                          │
│  ┌─────────┐                            │
│  │  Read   │◀─────────────────────┐     │
│  └────┬────┘                      │     │
│       │                           │     │
│       ▼                           │     │
│  ┌─────────┐                      │     │
│  │  Eval   │ (compile + exec)     │     │
│  └────┬────┘                      │     │
│       │                           │     │
│       ▼                           │     │
│  ┌─────────┐                      │     │
│  │  Print  │                      │     │
│  └────┬────┘                      │     │
│       │                           │     │
│       └───────────────────────────┘     │
│                                          │
└─────────────────────────────────────────┘
```

### Key REPL Components

```python
import code
import sys

class MyInterpreter(code.InteractiveConsole):
    def runsource(self, source, filename="<input>", symbol="single"):
        """Override to customize execution."""
        try:
            code_obj = compile(source, filename, symbol)
        except (OverflowError, SyntaxError, ValueError):
            # Syntax error - show it
            self.showsyntaxerror(filename)
            return False

        if code_obj is None:
            # Incomplete input (e.g., unclosed parenthesis)
            return True

        self.runcode(code_obj)
        return False

# Start custom REPL
# MyInterpreter().interact()
```

### `sys.ps1` and `sys.ps2`

```python
>>> import sys
>>> sys.ps1  # Primary prompt
'>>> '
>>> sys.ps2  # Continuation prompt
'... '

# Customize prompts
>>> sys.ps1 = "py> "
py> sys.ps2 = "..> "
py> def foo():
..>     pass
..>
py>
```

### Display Hook

The REPL uses `sys.displayhook` to print results:

```python
import sys

def custom_display(value):
    if value is not None:
        print(f"Result: {value!r}")
        __builtins__['_'] = value

sys.displayhook = custom_display

# Now in REPL:
# >>> 1 + 2
# Result: 3
```

### Exception Hook

`sys.excepthook` handles uncaught exceptions:

```python
import sys

def custom_excepthook(exc_type, exc_value, exc_tb):
    print(f"Error: {exc_type.__name__}: {exc_value}")

sys.excepthook = custom_excepthook
```

## Execution Flow Summary

```
┌─────────────────────────────────────────────────────────────────┐
│                    Python Execution Flow                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Source (.py)                                                    │
│       │                                                          │
│       ▼                                                          │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Compilation Pipeline (Covered in Part 2)                │    │
│  │   Lexer → Parser → AST → Compiler → Code Object         │    │
│  └─────────────────────────────────────────────────────────┘    │
│       │                                                          │
│       ▼                                                          │
│  Bytecode (.pyc cached)                                          │
│       │                                                          │
│       ▼                                                          │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Python Virtual Machine (Covered in Part 3)              │    │
│  │   Frame creation → Bytecode interpretation → Results     │    │
│  └─────────────────────────────────────────────────────────┘    │
│       │                                                          │
│       ▼                                                          │
│  Output / Side Effects                                           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Key Takeaways

1. **Multi-stage process**: Source → Tokens → AST → Bytecode → Execution
2. **Bytecode caching**: `.pyc` files in `__pycache__` speed up subsequent runs
3. **Stack-based VM**: The PVM uses a stack to evaluate expressions
4. **`__main__`**: The entry point module has special handling
5. **REPL customization**: `sys.displayhook`, `sys.excepthook`, `sys.ps1/ps2`

## Practice Exercises

1. Use `tokenize` to see tokens for various Python expressions
2. Use `ast.parse()` and `ast.dump()` to explore AST structures
3. Use `dis.dis()` to examine bytecode for different operations
4. Create a custom REPL with modified prompts and display hooks

---

[← Previous: CPython Overview](chapter-01-cpython-overview.md) | [Next: Lexical Analysis →](../part-02-compilation/chapter-03-lexical-analysis.md)

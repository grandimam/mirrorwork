# Chapter 5: Abstract Syntax Tree (AST)

## 5.1 AST Node Types

The Abstract Syntax Tree (AST) is a tree representation of Python source code that captures its structure without syntactic details like parentheses or commas.

### AST vs Parse Tree (CST)

```
Source: x = 1 + 2 * 3

Parse Tree (CST):                    AST:
file_input                           Module
└── simple_stmt                      └── Assign
    └── expr_stmt                        ├── targets: [Name('x')]
        ├── NAME 'x'                     └── value: BinOp
        ├── '='                                   ├── left: Constant(1)
        └── arith_expr                            ├── op: Add
            ├── term                              └── right: BinOp
            │   └── NUMBER '1'                            ├── left: Constant(2)
            ├── '+'                                       ├── op: Mult
            └── term                                      └── right: Constant(3)
                ├── NUMBER '2'
                ├── '*'
                └── NUMBER '3'

Note: AST is cleaner and captures semantics directly
```

### AST Node Categories

```python
import ast

# Expression nodes (ast.expr)
# - Return a value
# - Used in expression contexts

# Statement nodes (ast.stmt)
# - Perform actions
# - Don't return values

# Other nodes
# - Modules: Module, Interactive, Expression
# - Contexts: Load, Store, Del
# - Operators: Add, Sub, Mult, etc.
```

### All AST Node Types

```python
# Print all AST node types
import ast

print("Expression nodes:")
for name in dir(ast):
    obj = getattr(ast, name)
    if isinstance(obj, type) and issubclass(obj, ast.expr):
        print(f"  {name}")

print("\nStatement nodes:")
for name in dir(ast):
    obj = getattr(ast, name)
    if isinstance(obj, type) and issubclass(obj, ast.stmt):
        print(f"  {name}")
```

### Key Node Types

| Category | Nodes |
|----------|-------|
| **Literals** | `Constant`, `List`, `Dict`, `Set`, `Tuple` |
| **Variables** | `Name`, `Starred` |
| **Operations** | `BinOp`, `UnaryOp`, `BoolOp`, `Compare` |
| **Subscripting** | `Subscript`, `Slice` |
| **Calls** | `Call`, `keyword` |
| **Comprehensions** | `ListComp`, `DictComp`, `SetComp`, `GeneratorExp` |
| **Statements** | `Assign`, `AugAssign`, `AnnAssign`, `Return`, `Raise` |
| **Control Flow** | `If`, `For`, `While`, `Try`, `With`, `Match` |
| **Definitions** | `FunctionDef`, `AsyncFunctionDef`, `ClassDef` |
| **Imports** | `Import`, `ImportFrom` |

## 5.2 The `ast` Module

### Basic Usage

```python
import ast

# Parse source code
source = """
def greet(name):
    return f"Hello, {name}!"
"""

tree = ast.parse(source)
print(ast.dump(tree, indent=2))
```

Output:
```python
Module(
  body=[
    FunctionDef(
      name='greet',
      args=arguments(
        posonlyargs=[],
        args=[arg(arg='name', annotation=None)],
        vararg=None,
        kwonlyargs=[],
        kw_defaults=[],
        kwarg=None,
        defaults=[]),
      body=[
        Return(
          value=JoinedStr(
            values=[
              Constant(value='Hello, '),
              FormattedValue(
                value=Name(id='name', ctx=Load()),
                conversion=-1,
                format_spec=None),
              Constant(value='!')]))],
      decorator_list=[],
      returns=None,
      type_comment=None)],
  type_ignores=[])
```

### Parsing Options

```python
import ast

# Parse a module (multiple statements)
ast.parse("x = 1\ny = 2", mode='exec')

# Parse a single expression
ast.parse("1 + 2", mode='eval')

# Parse interactive input (like REPL)
ast.parse("x = 1", mode='single')

# Parse with type comments (Python 2 style annotations)
ast.parse("x = 1  # type: int", type_comments=True)

# Parse with feature version (for compatibility)
ast.parse("match x:\n  case 1: pass", feature_version=(3, 10))
```

### AST Node Attributes

All AST nodes have:
- `lineno`: Line number in source
- `col_offset`: Column offset in source
- `end_lineno`: End line (Python 3.8+)
- `end_col_offset`: End column (Python 3.8+)

```python
tree = ast.parse("x = 1 + 2")
assign = tree.body[0]
print(f"Line: {assign.lineno}, Column: {assign.col_offset}")
```

## 5.3 AST Transformations

### Walking the AST

```python
import ast

source = """
x = 1 + 2
y = x * 3
print(y)
"""

tree = ast.parse(source)

# Walk all nodes
for node in ast.walk(tree):
    print(type(node).__name__)
```

### NodeVisitor Pattern

```python
import ast

class NameCollector(ast.NodeVisitor):
    """Collect all variable names."""

    def __init__(self):
        self.names = set()

    def visit_Name(self, node):
        self.names.add(node.id)
        self.generic_visit(node)  # Visit children

# Usage
tree = ast.parse("x = y + z")
collector = NameCollector()
collector.visit(tree)
print(collector.names)  # {'x', 'y', 'z'}
```

### NodeTransformer Pattern

```python
import ast

class ConstantFolder(ast.NodeTransformer):
    """Fold constant expressions."""

    def visit_BinOp(self, node):
        # First, transform children
        self.generic_visit(node)

        # Check if both operands are constants
        if isinstance(node.left, ast.Constant) and \
           isinstance(node.right, ast.Constant):
            # Evaluate at compile time
            try:
                result = eval(compile(
                    ast.Expression(node), '<string>', 'eval'))
                return ast.Constant(value=result)
            except:
                pass
        return node

# Usage
tree = ast.parse("x = 1 + 2 + y", mode='eval')
transformer = ConstantFolder()
new_tree = transformer.visit(tree)
ast.fix_missing_locations(new_tree)
print(ast.dump(new_tree))
# Constant(3) + y instead of 1 + 2 + y
```

## 5.4 AST Optimization Passes

CPython performs optimizations on the AST before bytecode generation:

### Constant Folding

```python
# Before optimization:
x = 1 + 2 + 3

# After optimization:
x = 6
```

```python
import dis

def example():
    x = 1 + 2 + 3
    return x

dis.dis(example)
# Notice: LOAD_CONST 6 (not 1, 2, 3 separately)
```

### Dead Code Elimination

```python
# Code after return is eliminated
def example():
    return 1
    print("Never reached")  # Removed
```

### Tuple of Constants

```python
# Tuple of constants becomes a single constant
x = (1, 2, 3)  # Stored as single constant tuple
```

### Peephole Optimizations

Later stages perform additional optimizations:
- `not not x` → `bool(x)` (conceptually)
- Multiple `LOAD_CONST` followed by `BUILD_TUPLE` → single `LOAD_CONST`

## 5.5 Writing AST Visitors and Transformers

### Practical Example: Function Call Counter

```python
import ast
from collections import Counter

class FunctionCallCounter(ast.NodeVisitor):
    """Count function calls in code."""

    def __init__(self):
        self.calls = Counter()

    def visit_Call(self, node):
        # Get the function name
        if isinstance(node.func, ast.Name):
            self.calls[node.func.id] += 1
        elif isinstance(node.func, ast.Attribute):
            self.calls[node.func.attr] += 1

        # Continue visiting children
        self.generic_visit(node)

# Usage
code = """
print("Hello")
len([1, 2, 3])
print("World")
obj.method()
"""

tree = ast.parse(code)
counter = FunctionCallCounter()
counter.visit(tree)
print(counter.calls)
# Counter({'print': 2, 'len': 1, 'method': 1})
```

### Practical Example: Assert Remover

```python
import ast

class AssertRemover(ast.NodeTransformer):
    """Remove assert statements (like python -O)."""

    def visit_Assert(self, node):
        # Return None to remove the node
        return None

# Usage
code = """
def divide(a, b):
    assert b != 0, "Cannot divide by zero"
    return a / b
"""

tree = ast.parse(code)
transformer = AssertRemover()
new_tree = transformer.visit(tree)
ast.fix_missing_locations(new_tree)

# Compile and run
code_obj = compile(new_tree, '<string>', 'exec')
exec(code_obj)
# divide now has no assert statement
```

### Practical Example: Type Annotation Extractor

```python
import ast

class TypeExtractor(ast.NodeVisitor):
    """Extract type annotations from code."""

    def __init__(self):
        self.annotations = {}

    def visit_AnnAssign(self, node):
        """Handle: x: int = 5"""
        if isinstance(node.target, ast.Name):
            self.annotations[node.target.id] = ast.unparse(node.annotation)
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        """Handle function annotations."""
        func_annots = {}
        for arg in node.args.args:
            if arg.annotation:
                func_annots[arg.arg] = ast.unparse(arg.annotation)
        if node.returns:
            func_annots['return'] = ast.unparse(node.returns)
        if func_annots:
            self.annotations[node.name] = func_annots
        self.generic_visit(node)

# Usage
code = """
x: int = 5
y: str

def greet(name: str, times: int = 1) -> str:
    return name * times
"""

tree = ast.parse(code)
extractor = TypeExtractor()
extractor.visit(tree)
print(extractor.annotations)
# {'x': 'int', 'y': 'str', 'greet': {'name': 'str', 'times': 'int', 'return': 'str'}}
```

## 5.6 Macros and Metaprogramming with AST

### Creating AST Nodes Programmatically

```python
import ast

# Build: x = 1 + 2
assign = ast.Assign(
    targets=[ast.Name(id='x', ctx=ast.Store())],
    value=ast.BinOp(
        left=ast.Constant(value=1),
        op=ast.Add(),
        right=ast.Constant(value=2)
    )
)

# Wrap in a module
module = ast.Module(body=[assign], type_ignores=[])

# Fix line numbers
ast.fix_missing_locations(module)

# Compile and execute
code = compile(module, '<ast>', 'exec')
exec(code)
print(x)  # 3
```

### Simple Macro System

```python
import ast
import functools

def macro(transform_func):
    """Decorator to create AST macros."""
    @functools.wraps(transform_func)
    def wrapper(func):
        source = inspect.getsource(func)
        tree = ast.parse(source)
        new_tree = transform_func(tree)
        ast.fix_missing_locations(new_tree)
        code = compile(new_tree, '<macro>', 'exec')
        namespace = {}
        exec(code, namespace)
        return namespace[func.__name__]
    return wrapper
```

### Using `ast.unparse()` (Python 3.9+)

```python
import ast

# Parse and unparse (round-trip)
code = "x = 1 + 2"
tree = ast.parse(code)
reconstructed = ast.unparse(tree)
print(reconstructed)  # "x = 1 + 2"
```

## Summary

- **AST** represents code structure abstractly (no syntax details)
- **`ast` module** provides parsing, visiting, and transformation
- **NodeVisitor** for reading/analyzing the AST
- **NodeTransformer** for modifying the AST
- CPython performs **optimizations** on the AST
- AST enables **metaprogramming** and code analysis tools

## Practice Exercises

1. Write a visitor that finds all function definitions and their docstrings
2. Create a transformer that adds logging to all function calls
3. Build a complexity analyzer that counts branches and loops
4. Implement a simple linter rule using AST (e.g., no bare except)

---

[← Previous: Parsing](chapter-04-parsing.md) | [Next: Bytecode Compilation →](chapter-06-bytecode-compilation.md)

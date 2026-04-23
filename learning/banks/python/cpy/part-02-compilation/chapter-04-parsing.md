# Chapter 4: Parsing

## 4.1 Python Grammar (PEG Parser - Python 3.9+)

Starting with Python 3.9, CPython uses a **PEG (Parsing Expression Grammar)** parser, replacing the older LL(1) parser.

### What is PEG?

PEG (Parsing Expression Grammar) is a type of formal grammar that:
- Uses **ordered choice** (`/` or `|`) - tries alternatives in order
- Supports **unlimited lookahead** - can look ahead any number of tokens
- Is **unambiguous** by design - first match wins
- Supports **left recursion** (with special handling)

### PEG vs LL(1)

| Feature | LL(1) (Old) | PEG (New) |
|---------|-------------|-----------|
| Lookahead | 1 token | Unlimited |
| Left recursion | Not supported | Supported |
| Ambiguity | Possible | Impossible |
| Backtracking | No | Yes |
| Syntax flexibility | Limited | High |

### Why Python Switched to PEG

```python
# This syntax was hard to parse with LL(1):
with (
    open('a') as f1,
    open('b') as f2,
):
    pass

# Named expressions (walrus operator) - PEP 572
if (n := len(data)) > 10:
    print(f"Large: {n}")
```

## 4.2 Grammar File (`Grammar/python.gram`)

The Python grammar is defined in `Grammar/python.gram`. Here's a simplified view:

### Basic Grammar Syntax

```peg
# Rule definition
rule_name: expression

# Alternatives (ordered choice)
rule: alt1 | alt2 | alt3

# Sequence
rule: item1 item2 item3

# Optional (zero or one)
rule: [optional_item]

# Repetition (zero or more)
rule: item*

# One or more
rule: item+

# Lookahead (positive)
rule: &lookahead rest

# Negative lookahead
rule: !forbidden rest

# Grouping
rule: (a | b) c
```

### Sample Grammar Rules

```peg
# Simplified from Grammar/python.gram

# Statement
simple_stmt:
    | assignment
    | star_expressions
    | return_stmt
    | import_stmt
    | raise_stmt
    | 'pass'
    | 'break'
    | 'continue'

# Assignment
assignment:
    | NAME ':' expression ['=' annotated_rhs]
    | targets '=' annotated_rhs
    | target augassign ~ annotated_rhs

# If statement
if_stmt:
    | 'if' named_expression ':' block elif_stmt
    | 'if' named_expression ':' block [else_block]

# Function definition
function_def:
    | decorators function_def_raw
    | function_def_raw

function_def_raw:
    | 'def' NAME '(' [params] ')' ['->' expression] ':' block
    | 'async' 'def' NAME '(' [params] ')' ['->' expression] ':' block
```

### Viewing the Full Grammar

```bash
# In CPython source
cat Grammar/python.gram

# Or online
# https://github.com/python/cpython/blob/main/Grammar/python.gram
```

## 4.3 The Parser Generator (pegen)

CPython uses a parser generator called **pegen** to create the parser from the grammar.

### Parser Generation Process

```
┌─────────────────────────────────────────────────────────────────┐
│                   Parser Generation Flow                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Grammar/python.gram                                             │
│         │                                                        │
│         ▼                                                        │
│  ┌─────────────────┐                                            │
│  │  Parser Gen     │  Tools/peg_generator/                       │
│  │  (pegen)        │                                             │
│  └────────┬────────┘                                            │
│           │                                                      │
│           ▼                                                      │
│  Parser/parser.c (generated C code)                              │
│           │                                                      │
│           ▼                                                      │
│  ┌─────────────────┐                                            │
│  │   C Compiler    │                                             │
│  └────────┬────────┘                                            │
│           │                                                      │
│           ▼                                                      │
│  Python parser (in interpreter)                                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Key Files

| File | Purpose |
|------|---------|
| `Grammar/python.gram` | Grammar definition |
| `Grammar/Tokens` | Token definitions |
| `Parser/parser.c` | Generated parser (C) |
| `Tools/peg_generator/` | Parser generator tool |
| `Parser/pegen.c` | Parser runtime support |

## 4.4 Parse Tree Generation

The parser produces a **Concrete Syntax Tree (CST)** or parse tree:

```python
# For this code:
x = 1 + 2

# Parse tree structure (simplified):
file_input
└── simple_stmt
    └── assignment
        ├── NAME 'x'
        ├── '='
        └── expression
            └── term
                ├── NUMBER '1'
                ├── '+'
                └── NUMBER '2'
```

### Accessing the Parser Directly

```python
import _peg_parser  # CPython internal module

# This is internal and may change
# Use ast module for stable access
```

### Parser Memoization (Packrat Parsing)

The PEG parser uses memoization to achieve O(n) time complexity:

```
┌─────────────────────────────────────────────────────────────────┐
│                      Memoization Table                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Position │ Rule        │ Result                                │
│  ─────────┼─────────────┼─────────────────────────              │
│  0        │ expression  │ BinOp(...)                            │
│  0        │ term        │ Constant(1)                           │
│  2        │ term        │ Constant(2)                           │
│  ...      │ ...         │ ...                                   │
│                                                                  │
│  When a rule is attempted at a position:                        │
│  1. Check memo table                                            │
│  2. If cached, return immediately                               │
│  3. If not, parse and cache result                              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 4.5 Syntax Error Detection

The parser detects and reports syntax errors:

### Error Information

```python
try:
    compile("x = (1 + ", "<string>", "exec")
except SyntaxError as e:
    print(f"Message: {e.msg}")
    print(f"Line: {e.lineno}")
    print(f"Offset: {e.offset}")
    print(f"Text: {e.text!r}")
```

Output:
```
Message: '(' was never closed
Line: 1
Offset: 5
Text: 'x = (1 + '
```

### Error Recovery

The PEG parser provides better error messages than the old LL(1) parser:

```python
# Example: Missing colon
def foo()
    pass

# Error: expected ':'
```

### Common Syntax Errors

| Error | Cause |
|-------|-------|
| `unexpected EOF` | Unclosed bracket/quote |
| `invalid syntax` | General syntax error |
| `expected ':'` | Missing colon after def/if/etc |
| `cannot assign to` | Invalid assignment target |
| `'return' outside function` | Return in wrong scope |

### Soft Keywords (Python 3.10+)

Some keywords are "soft" - they're only keywords in certain contexts:

```python
# 'match' and 'case' are soft keywords
match = 1        # Valid - 'match' as variable name
match x:         # Valid - 'match' as keyword
    case 1:      # 'case' as keyword
        pass

case = 2         # Valid - 'case' as variable name
```

## Parser Implementation Details

### Recursive Descent

The generated parser uses recursive descent with memoization:

```c
// Simplified parser code structure (Parser/parser.c)

// Parse a simple statement
static stmt_ty
simple_stmt_rule(Parser *p)
{
    // Try assignment first
    stmt_ty assignment_var;
    if ((assignment_var = assignment_rule(p))) {
        return assignment_var;
    }

    // Try other alternatives...
    if ((star_expressions_var = star_expressions_rule(p))) {
        return star_expressions_var;
    }

    // ... more alternatives
    return NULL;  // No match
}
```

### Handling Left Recursion

PEG parsers typically don't support left recursion, but CPython's pegen handles it:

```peg
# Left-recursive rule (handled specially)
expr:
    | expr '+' term
    | expr '-' term
    | term
```

The parser generator detects left-recursive rules and generates iterative code instead of recursive.

## Summary

- Python 3.9+ uses a **PEG parser** (replaced LL(1))
- Grammar is defined in `Grammar/python.gram`
- **pegen** generates C parser code from the grammar
- Parser uses **memoization** for efficiency
- Better **error messages** compared to old parser
- Supports **soft keywords** for forward compatibility

## Practice Exercises

1. Read through `Grammar/python.gram` and identify rules for `for` loops
2. Compare error messages in Python 3.8 vs 3.10+ for the same syntax error
3. Write a tool that validates Python syntax without executing
4. Explore how the parser handles the walrus operator (`:=`)

---

[← Previous: Lexical Analysis](chapter-03-lexical-analysis.md) | [Next: Abstract Syntax Tree →](chapter-05-ast.md)

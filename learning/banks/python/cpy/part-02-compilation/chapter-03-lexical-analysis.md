# Chapter 3: Lexical Analysis

## 3.1 Tokenizer and Lexer

Lexical analysis is the first stage of compilation. The **lexer** (or **tokenizer**) reads source code character by character and groups them into meaningful units called **tokens**.

### What is a Token?

A token is the smallest unit of meaning in the source code:

```python
# Source code
result = 42 + value

# Tokens:
# NAME      'result'
# EQUAL     '='
# NUMBER    '42'
# PLUS      '+'
# NAME      'value'
# NEWLINE   '\n'
# ENDMARKER ''
```

### The Tokenization Process

```
┌─────────────────────────────────────────────────────────────┐
│                    Tokenization Flow                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Source: "x = 42 + y\n"                                      │
│             │                                                │
│             ▼                                                │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Character Stream                        │    │
│  │  ['x', ' ', '=', ' ', '4', '2', ' ', '+', ...]      │    │
│  └─────────────────────────────────────────────────────┘    │
│             │                                                │
│             ▼                                                │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                Tokenizer                             │    │
│  │  - Identify token boundaries                         │    │
│  │  - Classify token types                              │    │
│  │  - Track line/column positions                       │    │
│  └─────────────────────────────────────────────────────┘    │
│             │                                                │
│             ▼                                                │
│  ┌─────────────────────────────────────────────────────┐    │
│  │               Token Stream                           │    │
│  │  [NAME, OP, NUMBER, OP, NAME, NEWLINE, ENDMARKER]   │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### CPython's Tokenizer

The tokenizer is implemented in `Parser/tokenizer.c`. Key functions:

| Function | Purpose |
|----------|---------|
| `tok_get()` | Get the next token |
| `tok_new()` | Create a new tokenizer state |
| `tok_free()` | Free tokenizer resources |

## 3.2 Token Types and Categories

Python defines token types in `Grammar/Tokens`:

### Major Token Categories

```python
import token
import keyword

# List all token types
for name in dir(token):
    if name.isupper():
        print(f"{name}: {getattr(token, name)}")
```

### Token Type Reference

| Category | Tokens | Examples |
|----------|--------|----------|
| **Literals** | `NUMBER`, `STRING` | `42`, `3.14`, `"hello"` |
| **Identifiers** | `NAME` | `variable`, `my_func` |
| **Keywords** | `NAME` (special) | `if`, `for`, `class` |
| **Operators** | `OP` | `+`, `-`, `*`, `==` |
| **Delimiters** | `OP` | `(`, `)`, `[`, `]`, `:` |
| **Special** | `NEWLINE`, `INDENT`, `DEDENT` | Whitespace significance |
| **Comments** | `COMMENT` | `# comment` |
| **End Markers** | `ENDMARKER`, `ERRORTOKEN` | End of input, errors |

### Exploring Tokens Programmatically

```python
import tokenize
import io

code = '''
def greet(name):
    """Say hello."""
    return f"Hello, {name}!"
'''

tokens = list(tokenize.generate_tokens(io.StringIO(code).readline))

for tok in tokens:
    print(f"{token.tok_name[tok.type]:10} {tok.string!r:20} "
          f"line {tok.start[0]}, col {tok.start[1]}")
```

Output:
```
ENCODING   'utf-8'              line 1, col 0
NL         '\n'                 line 1, col 0
NAME       'def'                line 2, col 0
NAME       'greet'              line 2, col 4
OP         '('                  line 2, col 9
NAME       'name'               line 2, col 10
OP         ')'                  line 2, col 14
OP         ':'                  line 2, col 15
NEWLINE    '\n'                 line 2, col 16
INDENT     '    '               line 3, col 0
STRING     '"""Say hello."""'   line 3, col 4
NEWLINE    '\n'                 line 3, col 21
NAME       'return'             line 4, col 4
...
```

## 3.3 The `tokenize` Module

Python provides the `tokenize` module for programmatic access to tokenization:

### Basic Usage

```python
import tokenize

# Tokenize a file
with open('script.py', 'rb') as f:
    tokens = list(tokenize.tokenize(f.readline))

# Tokenize a string
import io
code = "x = 1 + 2"
tokens = list(tokenize.generate_tokens(io.StringIO(code).readline))
```

### Token Named Tuple

Each token is a named tuple:

```python
TokenInfo(
    type=1,           # Token type (e.g., NAME, NUMBER)
    string='hello',   # The actual string
    start=(1, 0),     # (line, column) start position
    end=(1, 5),       # (line, column) end position
    line='hello\n'    # The entire source line
)
```

### Untokenize: Reconstructing Source

```python
import tokenize
import io

code = "x=1+2"
tokens = tokenize.generate_tokens(io.StringIO(code).readline)
reconstructed = tokenize.untokenize(tokens)
print(reconstructed)  # "x=1+2"
```

### Practical Example: Token Counter

```python
import tokenize
import io
from collections import Counter

def count_tokens(code: str) -> Counter:
    """Count token types in code."""
    counter = Counter()
    tokens = tokenize.generate_tokens(io.StringIO(code).readline)
    for tok in tokens:
        counter[tokenize.tok_name[tok.type]] += 1
    return counter

code = """
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)
"""

counts = count_tokens(code)
for tok_type, count in counts.most_common():
    print(f"{tok_type}: {count}")
```

## 3.4 Encoding Declarations

Python supports encoding declarations for source files:

```python
# -*- coding: utf-8 -*-
# or
# coding: utf-8
# or
# vim: set fileencoding=utf-8 :
```

### How Encoding is Detected

```
┌─────────────────────────────────────────────────────────────┐
│                  Encoding Detection                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. Check for BOM (Byte Order Mark)                          │
│     └─ UTF-8 BOM: EF BB BF → utf-8                          │
│                                                              │
│  2. Check first two lines for encoding declaration           │
│     └─ Pattern: coding[=:]\s*([-\w.]+)                      │
│                                                              │
│  3. Default to UTF-8 (Python 3)                              │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Detecting Encoding Programmatically

```python
import tokenize

# Detect encoding of a file
with open('script.py', 'rb') as f:
    encoding = tokenize.detect_encoding(f.readline)
    print(f"Encoding: {encoding[0]}")  # e.g., 'utf-8'
```

### Unicode in Identifiers

Python 3 supports Unicode identifiers:

```python
# Valid Python 3 code
π = 3.14159
αβγ = "Greek"
日本語 = "Japanese"

def 挨拶():
    return "こんにちは"
```

## 3.5 Indentation Handling (INDENT/DEDENT Tokens)

Python's significant whitespace is handled at the tokenization level, not parsing.

### How INDENT/DEDENT Work

```python
code = '''
if True:
    x = 1
    y = 2
z = 3
'''
```

Token stream includes:
```
NAME       'if'
NAME       'True'
OP         ':'
NEWLINE    '\n'
INDENT     '    '      ← Indentation increased
NAME       'x'
...
NEWLINE    '\n'
DEDENT     ''          ← Indentation decreased
NAME       'z'
...
```

### The Indentation Stack

The tokenizer maintains an indentation stack:

```
Source:                          Indent Stack:
                                [0]
if True:                        [0]
    x = 1                       [0, 4]      ← INDENT emitted
    if y:                       [0, 4]
        z = 2                   [0, 4, 8]   ← INDENT emitted
    w = 3                       [0, 4]      ← DEDENT emitted
a = 4                           [0]         ← DEDENT emitted
```

### Visualizing Indentation

```python
import tokenize
import io

code = '''
def outer():
    def inner():
        pass
    return inner
'''

for tok in tokenize.generate_tokens(io.StringIO(code).readline):
    if tok.type in (tokenize.INDENT, tokenize.DEDENT, tokenize.NEWLINE):
        print(f"{tokenize.tok_name[tok.type]:10} at line {tok.start[0]}")
```

### Mixed Tabs and Spaces

Python 3 raises `TabError` for inconsistent indentation:

```python
# This raises TabError in Python 3
if True:
    x = 1     # 4 spaces
	y = 2     # 1 tab (inconsistent!)
```

The tokenizer detects this using consistent indentation tracking.

## Tokenizer State Machine

```
┌─────────────────────────────────────────────────────────────────┐
│                   Simplified Tokenizer FSM                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│                     ┌──────────┐                                │
│         ┌──────────▶│  START   │◀──────────┐                    │
│         │           └────┬─────┘           │                    │
│         │                │                 │                    │
│    ┌────┴────┐    ┌─────┴─────┐    ┌─────┴─────┐              │
│    │ NEWLINE │    │   SCAN    │    │  STRING   │              │
│    │  STATE  │    │   CHAR    │    │   STATE   │              │
│    └─────────┘    └─────┬─────┘    └───────────┘              │
│                         │                                       │
│         ┌───────────────┼───────────────┐                      │
│         ▼               ▼               ▼                      │
│    ┌─────────┐    ┌─────────┐    ┌─────────┐                  │
│    │  NAME   │    │ NUMBER  │    │OPERATOR │                  │
│    │  STATE  │    │  STATE  │    │  STATE  │                  │
│    └─────────┘    └─────────┘    └─────────┘                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Summary

- **Tokenization** converts source code into a stream of tokens
- **Tokens** include names, numbers, operators, keywords, and whitespace markers
- **INDENT/DEDENT** tokens encode Python's significant whitespace
- **Encoding declarations** specify source file encoding (default UTF-8)
- The `tokenize` module provides programmatic access to Python's lexer

## Practice Exercises

1. Write a token highlighter that colorizes different token types
2. Create a tool to detect mixing of tabs and spaces
3. Build a simple code formatter using tokenize/untokenize
4. Count keyword usage across a Python codebase

---

[← Previous: Execution Model](../part-01-introduction/chapter-02-execution-model.md) | [Next: Parsing →](chapter-04-parsing.md)

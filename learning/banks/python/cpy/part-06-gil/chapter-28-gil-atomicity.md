# Chapter 28: GIL Atomicity

## 28.1 Bytecode-Level Atomicity

The GIL provides atomicity at the **bytecode instruction** level, not the Python statement level:

```
┌─────────────────────────────────────────────────────────────────┐
│                  GIL Atomicity Scope                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Python statement:    x = y + z                                  │
│                                                                  │
│  Bytecode:            LOAD_FAST  (y)     ← Atomic               │
│                       LOAD_FAST  (z)     ← Atomic               │
│                       BINARY_ADD         ← Atomic               │
│                       STORE_FAST (x)     ← Atomic               │
│                                                                  │
│  GIL can be released between ANY of these instructions!         │
│                                                                  │
│  Single statement is NOT atomic as a whole.                      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Using `dis` to Analyze Atomicity

```python
import dis

# Single bytecode = atomic
def atomic_load():
    return x  # Just LOAD_GLOBAL

dis.dis(atomic_load)
# LOAD_GLOBAL 0 (x)
# RETURN_VALUE

# Multiple bytecodes = NOT atomic
def non_atomic_increment():
    global x
    x += 1

dis.dis(non_atomic_increment)
# LOAD_GLOBAL     0 (x)     ← Thread A reads x=5
# LOAD_CONST      1 (1)     ← Thread B reads x=5 (race!)
# BINARY_ADD                 ← Thread A computes 6
# STORE_GLOBAL    0 (x)     ← Thread A writes 6
#                           ← Thread B computes 6, writes 6
#                           ← Result: 6 (should be 7!)
```

## 28.2 Atomic Operations in Python

### Definitely Atomic Operations

```python
# Loading a variable (single LOAD_* instruction)
value = x          # LOAD_FAST or LOAD_GLOBAL

# Storing to a variable (single STORE_* instruction)
x = value          # STORE_FAST or STORE_GLOBAL

# Simple attribute access
obj.attr           # LOAD_ATTR

# Simple attribute assignment
obj.attr = value   # STORE_ATTR

# Simple indexing
lst[0]             # BINARY_SUBSCR

# Simple index assignment
lst[0] = value     # STORE_SUBSCR

# Method call (the call itself)
lst.append(x)      # CALL (single instruction)
```

### 28.2.1 `list.append()`

```python
import dis

def append_example(lst, x):
    lst.append(x)

dis.dis(append_example)
# LOAD_FAST     0 (lst)
# LOAD_METHOD   0 (append)
# LOAD_FAST     1 (x)
# CALL          1
# POP_TOP
# RETURN_VALUE

# The CALL itself is atomic
# But the whole sequence is multiple instructions
```

### 28.2.2 `dict[key] = value`

```python
import dis

def dict_set(d, k, v):
    d[k] = v

dis.dis(dict_set)
# LOAD_FAST     0 (d)
# LOAD_FAST     1 (k)
# LOAD_FAST     2 (v)
# STORE_SUBSCR          ← This single instruction is atomic
# RETURN_VALUE
```

### 28.2.3 `x = y` (Simple Assignment)

```python
import dis

def simple_assign():
    global x, y
    x = y

dis.dis(simple_assign)
# LOAD_GLOBAL   0 (y)   ← Atomic: load y
# STORE_GLOBAL  1 (x)   ← Atomic: store to x
# (But the pair is NOT atomic!)
```

## 28.3 Non-Atomic Operations

### 28.3.1 `x += 1` (Augmented Assignment)

```python
import dis

def increment():
    global x
    x += 1

dis.dis(increment)
# LOAD_GLOBAL     0 (x)
# LOAD_CONST      1 (1)
# BINARY_ADD
# STORE_GLOBAL    0 (x)
# (Four instructions - race condition possible!)
```

### 28.3.2 `list.extend()`

```python
import dis

def extend_example(lst, items):
    lst.extend(items)

dis.dis(extend_example)
# CALL to extend, but extend itself:
# - Iterates over items
# - Appends each one
# - Multiple internal operations
# Not atomic at Python level
```

### 28.3.3 Dictionary Iteration

```python
# NOT thread-safe during iteration
d = {1: 'a', 2: 'b', 3: 'c'}

def iterate_dict(d):
    for k in d:  # Creates iterator
        print(d[k])  # Access during iteration

# If another thread modifies d during iteration:
# RuntimeError: dictionary changed size during iteration
```

## 28.4 Using `dis` to Analyze Atomicity

### Practical Analysis Tool

```python
import dis
import sys

def analyze_atomicity(func):
    """Analyze if a function's body is atomic."""
    instructions = list(dis.get_instructions(func))

    # Filter out administrative instructions
    meaningful = [i for i in instructions
                  if i.opname not in ('RESUME', 'RETURN_VALUE', 'POP_TOP')]

    print(f"Function: {func.__name__}")
    print(f"Instructions: {len(meaningful)}")

    for instr in meaningful:
        print(f"  {instr.opname:20} {instr.argrepr}")

    if len(meaningful) <= 1:
        print("→ Likely ATOMIC")
    else:
        print("→ Likely NOT ATOMIC (multiple instructions)")
    print()

# Test various operations
def test_load():
    return x

def test_store():
    global x
    x = 1

def test_increment():
    global x
    x += 1

def test_append():
    global lst
    lst.append(1)

analyze_atomicity(test_load)
analyze_atomicity(test_store)
analyze_atomicity(test_increment)
analyze_atomicity(test_append)
```

## 28.5 Race Conditions Despite the GIL

### Classic Race Condition

```python
import threading

counter = 0

def unsafe_increment():
    global counter
    for _ in range(100000):
        counter += 1  # LOAD, ADD, STORE

# Create threads
threads = [threading.Thread(target=unsafe_increment) for _ in range(5)]

# Run
for t in threads:
    t.start()
for t in threads:
    t.join()

print(f"Expected: 500000, Got: {counter}")
# Almost always less than 500000!
```

### The Race Explained

```
┌─────────────────────────────────────────────────────────────────┐
│                   Race Condition Timeline                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  counter = 100 initially                                         │
│                                                                  │
│  Thread A                      Thread B                          │
│  ─────────                     ─────────                        │
│  LOAD_GLOBAL counter (100)                                       │
│  ── GIL released ──────────────────────────────────             │
│                                LOAD_GLOBAL counter (100)         │
│                                LOAD_CONST 1                      │
│                                BINARY_ADD (101)                  │
│                                STORE_GLOBAL counter (101)        │
│  ── GIL acquired ──────────────────────────────────             │
│  LOAD_CONST 1                                                    │
│  BINARY_ADD (101)              ← Still using old value!         │
│  STORE_GLOBAL counter (101)    ← Overwrites Thread B's work     │
│                                                                  │
│  Result: counter = 101 (should be 102)                          │
│  One increment was LOST                                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Safe Version

```python
import threading

counter = 0
lock = threading.Lock()

def safe_increment():
    global counter
    for _ in range(100000):
        with lock:  # Acquire lock
            counter += 1  # Now atomic as a group

threads = [threading.Thread(target=safe_increment) for _ in range(5)]
for t in threads:
    t.start()
for t in threads:
    t.join()

print(f"Expected: 500000, Got: {counter}")  # Always 500000
```

## Atomicity Quick Reference

```
┌─────────────────────────────────────────────────────────────────┐
│              Operation Atomicity Reference                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ATOMIC (single bytecode):                                       │
│  ───────────────────────                                        │
│  x = y            Load and store individually                    │
│  L[i]             Index access                                   │
│  L[i] = x         Index assignment                               │
│  L.append(x)      Method call                                    │
│  D[k] = v         Dictionary assignment                          │
│  D.get(k)         Method call                                    │
│                                                                  │
│  NOT ATOMIC (multiple bytecodes):                                │
│  ─────────────────────────────────                              │
│  x += 1           Load + compute + store                         │
│  x = y + z        Load + load + compute + store                  │
│  L.extend(M)      Multiple internal operations                   │
│  if k in D: D[k]  Check-then-act                                 │
│  D.setdefault()   Read + possibly write                          │
│                                                                  │
│  When in doubt: USE A LOCK                                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Summary

- GIL provides **bytecode-level atomicity**, not statement-level
- Single bytecode instructions are atomic
- **Compound operations** (`+=`, `if x: do_y()`) are NOT atomic
- **Use `dis` module** to analyze atomicity
- **Race conditions** still occur with the GIL
- **Always use locks** for shared mutable state

## Practice Exercises

1. Use `dis.dis()` to identify non-atomic operations in your code
2. Create a race condition demo and fix it with locks
3. Measure the performance impact of lock-protected operations
4. Identify all atomic operations for a `dict` object

---

[← Previous: GIL and Threading](chapter-27-gil-threading.md) | [Next: GIL Performance Impact →](chapter-29-gil-performance.md)

# Chapter 16: Built-in Types Internals

## 16.1 Integer (`PyLongObject`)

Python integers have arbitrary precision - they can be as large as memory allows.

### Internal Representation

```c
// Objects/longobject.c
typedef struct {
    PyObject_VAR_HEAD
    digit ob_digit[1];  // Variable-length array of digits
} PyLongObject;

// Each digit is typically 30 bits (on 64-bit systems)
// Number = sum(digit[i] * 2^(30*i))
```

### 16.1.1 Arbitrary Precision Arithmetic

```python
# Python handles arbitrary large integers
big = 2 ** 1000
print(len(str(big)))  # 302 digits

# Operations work on any size
result = (2 ** 500) * (3 ** 300)
print(type(result))  # <class 'int'>
```

### 16.1.2 Small Integer Cache

Python caches integers from -5 to 256:

```python
# Cached integers
a = 256
b = 256
print(a is b)  # True - same object

# Not cached
a = 257
b = 257
print(a is b)  # False - different objects

# Check cache
import sys
print(sys.getsizeof(1))     # Fixed size for small ints
print(sys.getsizeof(10**100))  # Larger for big ints
```

### Integer Memory Layout

```
┌─────────────────────────────────────────────────────────────────┐
│                    Integer Representation                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Small Integer (e.g., 42):                                       │
│  ┌────────────┬─────────┬────────┬─────────┐                    │
│  │  ob_refcnt │ ob_type │ob_size │ digit[0]│                    │
│  │     8      │    8    │   8    │  4-8    │                    │
│  └────────────┴─────────┴────────┴─────────┘                    │
│                          │                                       │
│                          └── ob_size encodes sign                │
│                              positive: ob_size > 0               │
│                              negative: ob_size < 0               │
│                              zero: ob_size = 0                   │
│                                                                  │
│  Large Integer (e.g., 2^100):                                    │
│  ┌────────────┬─────────┬────────┬─────────────────────┐        │
│  │  ob_refcnt │ ob_type │ob_size │ digit[0..n]        │        │
│  │     8      │    8    │   8    │  4-8 each          │        │
│  └────────────┴─────────┴────────┴─────────────────────┘        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 16.2 Float (`PyFloatObject`)

Floats use IEEE 754 double precision:

### 16.2.1 IEEE 754 Representation

```python
import struct

# Float internals
f = 3.14159
bytes_repr = struct.pack('d', f)
print(bytes_repr.hex())  # 64-bit IEEE 754

# Special values
print(float('inf'))   # Infinity
print(float('-inf'))  # Negative infinity
print(float('nan'))   # Not a Number

# Precision limits
print(1.0 + 1e-16 == 1.0)  # True (precision lost)
print(0.1 + 0.2)           # 0.30000000000000004
```

### 16.2.2 Float Free List

Python maintains a free list for float reuse:

```python
import sys

# Float object size
print(sys.getsizeof(3.14))  # 24 bytes

# Floats are not cached like small ints
a = 1.0
b = 1.0
print(a is b)  # False (usually)
```

## 16.3 String (`PyUnicodeObject`)

Python 3 strings are Unicode and use compact representations:

### 16.3.1 Unicode Representations

```python
# Python chooses representation based on content
import sys

ascii_str = "hello"          # ASCII - 1 byte/char
latin_str = "héllo"          # Latin-1 - 1 byte/char
bmp_str = "hello世界"         # UCS-2 - 2 bytes/char
full_str = "hello😀"          # UCS-4 - 4 bytes/char

print(sys.getsizeof(ascii_str))   # Smallest
print(sys.getsizeof(full_str))    # Largest
```

### 16.3.2 String Interning

```python
import sys

# Automatic interning for identifier-like strings
a = "hello"
b = "hello"
print(a is b)  # True

# Not interned (has space)
a = "hello world"
b = "hello world"
print(a is b)  # May be False

# Manual interning
a = sys.intern("hello world")
b = sys.intern("hello world")
print(a is b)  # True
```

### 16.3.3 String Hashing

```python
# Strings are hashable (immutable)
s = "hello"
print(hash(s))  # Consistent hash value

# Hash is cached after first computation
# Stored in the string object itself
```

### String Memory Layout

```
┌─────────────────────────────────────────────────────────────────┐
│                    String Representations                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Kind       │ Bytes/Char │ Characters Supported                 │
│  ───────────┼────────────┼──────────────────────                │
│  ASCII      │     1      │ U+0000 to U+007F                     │
│  Latin-1    │     1      │ U+0000 to U+00FF                     │
│  UCS-2      │     2      │ U+0000 to U+FFFF                     │
│  UCS-4      │     4      │ U+0000 to U+10FFFF                   │
│                                                                  │
│  Python automatically uses the smallest representation           │
│  that can hold all characters in the string.                    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 16.4 List (`PyListObject`)

Lists are dynamic arrays:

### 16.4.1 Dynamic Array Implementation

```c
// Objects/listobject.c
typedef struct {
    PyObject_VAR_HEAD
    PyObject **ob_item;    // Array of pointers
    Py_ssize_t allocated;  // Allocated size
} PyListObject;
```

### 16.4.2 Over-Allocation Strategy

```python
import sys

# List grows with over-allocation
lst = []
for i in range(20):
    lst.append(i)
    print(f"len={len(lst):2d}, size={sys.getsizeof(lst)} bytes")

# Over-allocation pattern: 0, 4, 8, 16, 24, 32, 40, 52, ...
# Formula approximately: new_size = old_size + (old_size >> 3) + 6
```

### 16.4.3 List Operations Complexity

| Operation | Average Case | Worst Case |
|-----------|-------------|------------|
| `lst[i]` | O(1) | O(1) |
| `lst.append(x)` | O(1) | O(n) amortized |
| `lst.insert(i, x)` | O(n) | O(n) |
| `lst.pop()` | O(1) | O(1) |
| `lst.pop(i)` | O(n) | O(n) |
| `x in lst` | O(n) | O(n) |

## 16.5 Tuple (`PyTupleObject`)

Tuples are immutable sequences:

### 16.5.1 Immutability Advantages

```python
# Tuples can be dict keys (hashable)
d = {(1, 2): "point"}

# Tuples can be set elements
s = {(1, 2), (3, 4)}

# Slight memory advantage
import sys
print(sys.getsizeof([1, 2, 3]))    # List: 88 bytes
print(sys.getsizeof((1, 2, 3)))    # Tuple: 64 bytes
```

### 16.5.2 Tuple Free Lists

```python
# Python caches small empty tuples
t1 = ()
t2 = ()
print(t1 is t2)  # True - same object

# Single-element tuples may be cached
t1 = (1,)
t2 = (1,)
# May or may not be same object (implementation detail)
```

## 16.6 Dictionary (`PyDictObject`)

Dictionaries are hash tables:

### 16.6.1 Hash Table Implementation

```python
# Dictionary uses open addressing with pseudo-random probing
d = {'a': 1, 'b': 2, 'c': 3}

# Keys must be hashable
hash('a')  # Works
# hash([1, 2])  # TypeError - lists not hashable
```

### 16.6.2 Compact Dict (Python 3.6+)

```
┌─────────────────────────────────────────────────────────────────┐
│                    Compact Dict Structure                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Old dict (pre-3.6):                                            │
│  ┌────────────────────────────────────────┐                     │
│  │ [hash│key│value] [hash│key│value] ... │  Sparse, wasteful    │
│  └────────────────────────────────────────┘                     │
│                                                                  │
│  Compact dict (3.6+):                                           │
│  ┌─────────────────┐  ┌───────────────────────┐                │
│  │ Indices         │  │ Entries (dense)       │                │
│  │ [2│0│-│1│-│-]   │  │ [hash│key│val]       │                │
│  └────────┬────────┘  │ [hash│key│val]       │                │
│           │           │ [hash│key│val]       │                │
│           │           └───────────────────────┘                │
│           └──────── Points to entries                          │
│                                                                  │
│  Benefits:                                                       │
│  - Preserves insertion order                                    │
│  - Less memory usage                                            │
│  - Better cache locality                                         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 16.6.3 Key-Sharing Dictionaries

```python
# Instances of the same class share key structure
class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

# p1.__dict__ and p2.__dict__ share key layout
p1 = Point(1, 2)
p2 = Point(3, 4)
# Memory efficient for many instances with same attributes
```

### 16.6.4 Collision Resolution

```python
# Python uses open addressing with perturbation
# Probe sequence: hash, then perturb >> 5 + hash + 1

# Collision handling is transparent to users
d = {}
d['a'] = 1  # hash('a') determines initial slot
d['b'] = 2  # If collision, probe for next slot
```

### 16.6.5 Dict Ordering Guarantee

```python
# Python 3.7+ guarantees insertion order
d = {}
d['z'] = 1
d['a'] = 2
d['m'] = 3

print(list(d.keys()))  # ['z', 'a', 'm'] - insertion order
```

## 16.7 Set (`PySetObject`)

Sets are hash tables without values:

### 16.7.1 Hash Set Implementation

```python
# Sets use similar structure to dicts (without values)
s = {1, 2, 3}

# Fast membership testing
print(2 in s)  # O(1) average

# Set operations
a = {1, 2, 3}
b = {2, 3, 4}
print(a | b)  # Union: {1, 2, 3, 4}
print(a & b)  # Intersection: {2, 3}
print(a - b)  # Difference: {1}
```

### 16.7.2 Set Operations Complexity

| Operation | Average Case |
|-----------|-------------|
| `x in s` | O(1) |
| `s.add(x)` | O(1) |
| `s.remove(x)` | O(1) |
| `s \| t` | O(len(s) + len(t)) |
| `s & t` | O(min(len(s), len(t))) |
| `s - t` | O(len(s)) |

## Memory Comparison

```python
import sys

# Compare sizes
data = list(range(1000))

print(f"List:  {sys.getsizeof(data):,} bytes")
print(f"Tuple: {sys.getsizeof(tuple(data)):,} bytes")
print(f"Set:   {sys.getsizeof(set(data)):,} bytes")
print(f"Dict:  {sys.getsizeof(dict.fromkeys(data)):,} bytes")
```

## Summary

- **int**: Arbitrary precision using digit arrays, small int cache
- **float**: IEEE 754 double precision, free list for reuse
- **str**: Unicode with compact representations, interning
- **list**: Dynamic array with over-allocation
- **tuple**: Immutable, memory efficient, hashable
- **dict**: Compact hash table, preserves order, key-sharing
- **set**: Hash table without values, fast membership testing

## Practice Exercises

1. Measure memory usage of different integer sizes
2. Explore string interning behavior with different string types
3. Visualize list over-allocation as items are added
4. Compare dict vs OrderedDict behavior in Python 3.7+

---

[← Previous: Descriptor Protocol](chapter-15-descriptor-protocol.md) | [Next: Special Objects →](chapter-17-special-objects.md)

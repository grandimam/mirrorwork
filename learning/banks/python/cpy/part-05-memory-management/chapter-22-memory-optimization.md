# Chapter 22: Memory Optimization

## 22.1 `__slots__` for Memory Savings

`__slots__` eliminates the per-instance `__dict__`:

```python
import sys

class Regular:
    def __init__(self, x, y):
        self.x = x
        self.y = y

class Slotted:
    __slots__ = ['x', 'y']

    def __init__(self, x, y):
        self.x = x
        self.y = y

# Compare sizes
regular = Regular(1, 2)
slotted = Slotted(1, 2)

print(f"Regular: {sys.getsizeof(regular)} bytes")  # ~48 bytes
print(f"Regular __dict__: {sys.getsizeof(regular.__dict__)} bytes")  # ~64 bytes
print(f"Slotted: {sys.getsizeof(slotted)} bytes")  # ~48 bytes
# Slotted has no __dict__ - saves ~64+ bytes per instance!
```

### Memory Savings at Scale

```python
import sys

class RegularPoint:
    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z

class SlottedPoint:
    __slots__ = ['x', 'y', 'z']

    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z

# Create many instances
regular_points = [RegularPoint(i, i+1, i+2) for i in range(100000)]
slotted_points = [SlottedPoint(i, i+1, i+2) for i in range(100000)]

# Measure total memory
import tracemalloc
tracemalloc.start()

regular_points = [RegularPoint(i, i+1, i+2) for i in range(100000)]
regular_mem = tracemalloc.get_traced_memory()[0]

tracemalloc.reset_peak()
slotted_points = [SlottedPoint(i, i+1, i+2) for i in range(100000)]
slotted_mem = tracemalloc.get_traced_memory()[0]

print(f"Regular: {regular_mem / 1024 / 1024:.2f} MB")
print(f"Slotted: {slotted_mem / 1024 / 1024:.2f} MB")
tracemalloc.stop()
```

### `__slots__` Caveats

```python
class Slotted:
    __slots__ = ['x', 'y']

obj = Slotted()
obj.x = 1
obj.y = 2
# obj.z = 3  # AttributeError - can't add new attributes

# To allow __dict__, include it in slots
class Flexible:
    __slots__ = ['x', 'y', '__dict__']

flex = Flexible()
flex.x = 1
flex.z = 3  # OK - uses __dict__
```

## 22.2 Interning Strategies

### String Interning

```python
import sys

# Automatic interning for identifier-like strings
a = "hello"
b = "hello"
print(a is b)  # True

# Force interning
s1 = sys.intern("hello world")
s2 = sys.intern("hello world")
print(s1 is s2)  # True

# Benefits: Fast comparison, memory sharing
# Use for: Dictionary keys, frequently compared strings
```

### Integer Caching

```python
# Small integers are pre-cached (-5 to 256)
a = 256
b = 256
print(a is b)  # True

# Large integers are not
a = 257
b = 257
print(a is b)  # False (usually)

# For repeated large integers, store in variables
LARGE_CONSTANT = 100000  # Single object
for _ in range(1000):
    use(LARGE_CONSTANT)  # Reuses same object
```

## 22.3 Memory-Efficient Data Structures

### Use Generators Instead of Lists

```python
# Memory-hungry: stores all items
def get_squares_list(n):
    return [x**2 for x in range(n)]

# Memory-efficient: yields one at a time
def get_squares_gen(n):
    for x in range(n):
        yield x**2

# List: O(n) memory
squares_list = get_squares_list(1000000)

# Generator: O(1) memory
squares_gen = get_squares_gen(1000000)
```

### Use Tuples Instead of Lists (When Immutable)

```python
import sys

lst = [1, 2, 3, 4, 5]
tpl = (1, 2, 3, 4, 5)

print(f"List: {sys.getsizeof(lst)} bytes")   # 88
print(f"Tuple: {sys.getsizeof(tpl)} bytes")  # 64
```

### Use Sets for Membership Testing

```python
# List membership: O(n)
items_list = [1, 2, 3, 4, 5]
x in items_list  # Scans entire list

# Set membership: O(1)
items_set = {1, 2, 3, 4, 5}
x in items_set  # Hash lookup

# Frozenset for immutable sets (can be dict keys)
immutable_set = frozenset([1, 2, 3])
```

## 22.4 `array` Module vs Lists

```python
import sys
import array

# List of integers
int_list = [1, 2, 3, 4, 5] * 1000
print(f"List: {sys.getsizeof(int_list)} bytes")

# Array of integers
int_array = array.array('i', [1, 2, 3, 4, 5] * 1000)
print(f"Array: {sys.getsizeof(int_array)} bytes")

# Array is much smaller because it stores raw values
# Not Python objects
```

### Array Type Codes

| Code | C Type | Python Type | Size |
|------|--------|-------------|------|
| 'b' | signed char | int | 1 |
| 'B' | unsigned char | int | 1 |
| 'i' | signed int | int | 2-4 |
| 'I' | unsigned int | int | 2-4 |
| 'f' | float | float | 4 |
| 'd' | double | float | 8 |

## 22.5 `memoryview` and Buffer Protocol

```python
# memoryview avoids copying data
data = bytearray(1000000)

# Without memoryview: creates copy
slice_copy = data[100:200]

# With memoryview: no copy
mv = memoryview(data)
slice_view = mv[100:200]  # Just a view, no copy

# Modify through view
slice_view[0] = 42
print(data[100])  # 42 - original modified
```

### Buffer Protocol

```python
import numpy as np

# NumPy arrays support buffer protocol
arr = np.array([1, 2, 3, 4, 5], dtype=np.int32)

# Create memoryview without copying
mv = memoryview(arr)
print(mv.format)  # 'i' (int)
print(mv.itemsize)  # 4 bytes
print(list(mv))  # [1, 2, 3, 4, 5]
```

## 22.6 Memory Mapping (`mmap`)

```python
import mmap

# Memory-map a file for efficient access
with open('large_file.bin', 'r+b') as f:
    # Map the file into memory
    mm = mmap.mmap(f.fileno(), 0)

    # Access like a bytearray
    print(mm[:100])  # Read first 100 bytes

    # Modify in place
    mm[0:5] = b'Hello'

    # Search
    index = mm.find(b'pattern')

    mm.close()

# Benefits:
# - File appears as memory, OS handles paging
# - Large files without loading entirely into RAM
# - Multiple processes can share mapped files
```

### Anonymous Memory Mapping

```python
import mmap

# Create anonymous mapping (not backed by file)
# Useful for large temporary buffers
size = 1024 * 1024 * 100  # 100 MB
mm = mmap.mmap(-1, size)  # -1 = anonymous

# Use like bytearray
mm[0:5] = b'Hello'
print(mm[0:5])

mm.close()
```

## Practical Optimization Patterns

### Pattern 1: Lazy Loading

```python
class LazyLoader:
    def __init__(self, filename):
        self.filename = filename
        self._data = None

    @property
    def data(self):
        if self._data is None:
            print("Loading data...")
            self._data = self._load_data()
        return self._data

    def _load_data(self):
        with open(self.filename) as f:
            return f.read()

# Data loaded only when accessed
loader = LazyLoader('large_file.txt')
# ... later ...
print(loader.data)  # Now it loads
```

### Pattern 2: Object Pool

```python
class ObjectPool:
    def __init__(self, factory, initial_size=10):
        self.factory = factory
        self.pool = [factory() for _ in range(initial_size)]

    def get(self):
        if self.pool:
            return self.pool.pop()
        return self.factory()

    def release(self, obj):
        self.pool.append(obj)

# Usage
class ExpensiveObject:
    def reset(self):
        pass  # Reset state for reuse

pool = ObjectPool(ExpensiveObject)
obj = pool.get()
# ... use obj ...
obj.reset()
pool.release(obj)  # Return to pool, don't delete
```

### Pattern 3: Flyweight Pattern

```python
class Flyweight:
    """Share common state between many objects."""
    _instances = {}

    def __new__(cls, shared_state):
        if shared_state not in cls._instances:
            instance = super().__new__(cls)
            instance.shared_state = shared_state
            cls._instances[shared_state] = instance
        return cls._instances[shared_state]

# All instances with same shared_state are same object
a = Flyweight("common")
b = Flyweight("common")
print(a is b)  # True
```

## Summary

- **`__slots__`** eliminates `__dict__` overhead
- **Interning** shares identical strings/small integers
- **Generators** use O(1) memory vs O(n) for lists
- **`array`** stores raw values, not Python objects
- **`memoryview`** provides zero-copy slicing
- **`mmap`** efficiently handles large files
- Design patterns (lazy loading, object pools) reduce memory

## Practice Exercises

1. Convert a class to use `__slots__` and measure savings
2. Compare memory usage of list vs generator for large sequences
3. Use `memoryview` to process large binary data efficiently
4. Implement an object pool for a frequently-created class

---

[← Previous: Garbage Collection](chapter-21-garbage-collection.md) | [Next: Memory Debugging →](chapter-23-memory-debugging.md)

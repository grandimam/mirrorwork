# Chapter 18: Memory Architecture

## 18.1 Python Memory Hierarchy

Python's memory management is organized in layers:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Python Memory Hierarchy                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Layer 3: Object-specific allocators                             │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  int allocator │ list allocator │ dict allocator │ ... │    │
│  └─────────────────────────────────────────────────────────┘    │
│                            │                                     │
│                            ▼                                     │
│  Layer 2: Python object allocator (pymalloc)                    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │               PyObject_Malloc/Free                       │    │
│  │           Pools → Blocks (≤512 bytes)                    │    │
│  └─────────────────────────────────────────────────────────┘    │
│                            │                                     │
│                            ▼                                     │
│  Layer 1: Python raw memory allocator                           │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │               PyMem_Malloc/Free                          │    │
│  │              (wraps system allocator)                    │    │
│  └─────────────────────────────────────────────────────────┘    │
│                            │                                     │
│                            ▼                                     │
│  Layer 0: System allocator                                       │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │         malloc/free (libc), mmap, VirtualAlloc          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 18.2 Raw Memory Layer (System Allocator)

The lowest layer uses the operating system's memory allocator:

```c
// Layer 0: System malloc/free
void* ptr = malloc(size);
free(ptr);

// On Unix: Uses libc malloc (glibc, jemalloc, etc.)
// On Windows: Uses HeapAlloc/HeapFree
// Can also use mmap for large allocations
```

### System Allocator Characteristics

| Aspect | Description |
|--------|-------------|
| Speed | Moderate (system call overhead) |
| Fragmentation | Can fragment over time |
| Thread Safety | Thread-safe in modern systems |
| Memory Overhead | Small metadata per allocation |

## 18.3 Object Memory Layer

Python wraps the system allocator with its own functions:

```c
// Objects/obmalloc.c

// Layer 1: Raw memory
void* PyMem_Malloc(size_t size);
void* PyMem_Realloc(void* ptr, size_t size);
void  PyMem_Free(void* ptr);

// Layer 2: Object memory (with type information)
void* PyObject_Malloc(size_t size);
void* PyObject_Realloc(void* ptr, size_t size);
void  PyObject_Free(void* ptr);
```

### Why Wrap System Allocator?

1. **Debugging**: Track allocations, detect leaks
2. **Performance**: Optimize for Python's allocation patterns
3. **Consistency**: Same behavior across platforms
4. **Hooks**: Allow custom allocators

```python
# Python exposes memory debugging
import sys

# Get memory allocator info
print(sys._debugmallocstats())  # Debug build only
```

## 18.4 Object-Specific Allocators

Many built-in types have their own allocators:

### Free Lists

```python
# Python maintains free lists for common objects
# When objects are deallocated, they go to free lists
# instead of returning memory to the system

# Examples:
# - Float free list
# - Tuple free lists (by size)
# - Frame free list
# - List free list

import sys

# Observe free list effect
floats = [float(i) for i in range(1000)]
del floats  # Objects go to free list

# Next allocations reuse free list
new_floats = [float(i) for i in range(1000)]  # Fast!
```

### Small Integer Cache

```python
# Integers -5 to 256 are pre-allocated
a = 256
b = 256
print(a is b)  # True - same cached object

# Large integers are not cached
a = 257
b = 257
print(a is b)  # False - different objects
```

## Memory Allocation Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                 Object Allocation Decision Tree                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│                    PyObject_Malloc(size)                         │
│                            │                                     │
│                            ▼                                     │
│                    size ≤ 512 bytes?                            │
│                     /          \                                 │
│                   Yes           No                               │
│                   /              \                               │
│                  ▼                ▼                              │
│           Use pymalloc      Use system malloc                    │
│           (pools/blocks)    (PyMem_Malloc)                       │
│                  │                                               │
│                  ▼                                               │
│            Find pool for                                         │
│            size class                                            │
│                  │                                               │
│                  ▼                                               │
│         Pool has free block?                                     │
│              /      \                                            │
│            Yes       No                                          │
│            /          \                                          │
│           ▼            ▼                                         │
│      Return block   Allocate new pool                            │
│                     from arena                                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Memory Configuration

### Environment Variables

```bash
# Use debug memory allocator
export PYTHONMALLOC=debug

# Use system malloc (disable pymalloc)
export PYTHONMALLOC=malloc

# Show memory allocation stats
export PYTHONMALLOCSTATS=1
```

### Runtime Configuration

```python
import sys

# Get allocator name
print(sys._get_memory_allocator_name())  # e.g., 'pymalloc'

# Memory statistics (debug builds)
# sys._debugmallocstats()
```

## Memory Usage Measurement

```python
import sys
import tracemalloc

# Basic size measurement
x = [1, 2, 3]
print(sys.getsizeof(x))  # Size of list object itself

# Deep size (including contents)
def deep_getsizeof(obj, seen=None):
    """Recursively calculate size of objects."""
    size = sys.getsizeof(obj)
    if seen is None:
        seen = set()
    obj_id = id(obj)
    if obj_id in seen:
        return 0
    seen.add(obj_id)

    if isinstance(obj, dict):
        size += sum(deep_getsizeof(v, seen) for v in obj.values())
        size += sum(deep_getsizeof(k, seen) for k in obj.keys())
    elif hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes)):
        size += sum(deep_getsizeof(i, seen) for i in obj)

    return size

data = {'a': [1, 2, 3], 'b': {'nested': [4, 5, 6]}}
print(f"Shallow: {sys.getsizeof(data)}")
print(f"Deep: {deep_getsizeof(data)}")
```

## Tracemalloc Module

```python
import tracemalloc

# Start tracing
tracemalloc.start()

# Your code here
data = [list(range(1000)) for _ in range(100)]

# Get memory snapshot
snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics('lineno')

print("Top 10 memory allocations:")
for stat in top_stats[:10]:
    print(stat)

# Compare snapshots
snapshot1 = tracemalloc.take_snapshot()
# ... more allocations ...
snapshot2 = tracemalloc.take_snapshot()

diff = snapshot2.compare_to(snapshot1, 'lineno')
for stat in diff[:5]:
    print(stat)

tracemalloc.stop()
```

## Summary

- Python has a **layered memory architecture**
- **Layer 0**: System allocator (malloc/free)
- **Layer 1**: Python raw memory (PyMem_*)
- **Layer 2**: Object allocator with pymalloc
- **Layer 3**: Type-specific allocators and free lists
- **Small objects** (≤512 bytes) use pymalloc
- **Large objects** use system malloc directly
- Use **tracemalloc** for memory profiling

## Practice Exercises

1. Use `sys.getsizeof()` to measure different object types
2. Profile a script with `tracemalloc` and find memory hotspots
3. Experiment with `PYTHONMALLOC` environment variable
4. Implement a deep size calculator for nested structures

---

[← Previous: Special Objects](../part-04-object-model/chapter-17-special-objects.md) | [Next: pymalloc Allocator →](chapter-19-pymalloc.md)

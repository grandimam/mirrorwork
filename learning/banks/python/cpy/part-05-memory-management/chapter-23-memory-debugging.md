# Chapter 23: Memory Debugging

## 23.1 `sys.getsizeof()` and `pympler`

### Basic Size Measurement

```python
import sys

# getsizeof returns direct size (not nested objects)
obj = [1, 2, 3]
print(sys.getsizeof(obj))  # Size of list object itself

# Doesn't include referenced objects
nested = [[1, 2], [3, 4], [5, 6]]
print(sys.getsizeof(nested))  # Only the outer list

# For nested structures, need recursive calculation
def total_size(obj, seen=None):
    """Calculate total size including nested objects."""
    size = sys.getsizeof(obj)
    if seen is None:
        seen = set()

    obj_id = id(obj)
    if obj_id in seen:
        return 0
    seen.add(obj_id)

    if isinstance(obj, dict):
        size += sum(total_size(k, seen) + total_size(v, seen)
                    for k, v in obj.items())
    elif hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes)):
        size += sum(total_size(i, seen) for i in obj)
    elif hasattr(obj, '__dict__'):
        size += total_size(obj.__dict__, seen)

    return size

data = {'a': [1, 2, 3], 'b': {'nested': [4, 5, 6]}}
print(f"Shallow: {sys.getsizeof(data)}")
print(f"Total: {total_size(data)}")
```

### Using pympler

```python
# pip install pympler
from pympler import asizeof, tracker, muppy

# asizeof - deep size calculation
obj = {'a': [1, 2, 3], 'b': [4, 5, 6]}
print(asizeof.asizeof(obj))  # Total memory including contents

# Compare objects
print(asizeof.asized(obj, detail=1).format())

# Track memory changes
tr = tracker.SummaryTracker()

# ... allocate objects ...
data = [list(range(1000)) for _ in range(100)]

tr.print_diff()  # Show what changed
```

## 23.2 `tracemalloc` Module

### Basic Usage

```python
import tracemalloc

# Start tracing
tracemalloc.start()

# Your code
data = [list(range(1000)) for _ in range(1000)]

# Take snapshot
snapshot = tracemalloc.take_snapshot()

# Get top allocations by line
top_stats = snapshot.statistics('lineno')
print("Top 10 allocations:")
for stat in top_stats[:10]:
    print(stat)
```

### Comparing Snapshots

```python
import tracemalloc

tracemalloc.start()

# Snapshot before
snapshot1 = tracemalloc.take_snapshot()

# Allocate some memory
leaky_list = []
for i in range(10000):
    leaky_list.append("x" * 1000)

# Snapshot after
snapshot2 = tracemalloc.take_snapshot()

# Compare
diff = snapshot2.compare_to(snapshot1, 'lineno')
print("Memory increase:")
for stat in diff[:10]:
    print(stat)
```

### Filtering Results

```python
import tracemalloc

tracemalloc.start()

# ... code ...

snapshot = tracemalloc.take_snapshot()

# Filter by filename
snapshot = snapshot.filter_traces([
    tracemalloc.Filter(True, "*/mymodule.py"),
])

# Exclude certain paths
snapshot = snapshot.filter_traces([
    tracemalloc.Filter(False, "<frozen importlib.*>"),
    tracemalloc.Filter(False, "<unknown>"),
])

for stat in snapshot.statistics('lineno')[:10]:
    print(stat)
```

### Getting Traceback

```python
import tracemalloc

tracemalloc.start(25)  # Store 25 frames per allocation

# ... code ...

snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics('traceback')

# Get traceback for biggest allocation
stat = top_stats[0]
print(f"\n{stat.count} memory blocks: {stat.size / 1024:.1f} KiB")
for line in stat.traceback.format():
    print(line)
```

## 23.3 Memory Profiling Tools

### memory_profiler

```python
# pip install memory_profiler

# Usage 1: Decorator
from memory_profiler import profile

@profile
def my_function():
    a = [1] * 1000000
    b = [2] * 2000000
    del b
    return a

my_function()
```

Output:
```
Line #    Mem usage    Increment   Line Contents
================================================
     3     38.5 MiB     38.5 MiB   @profile
     4                             def my_function():
     5     46.2 MiB      7.6 MiB       a = [1] * 1000000
     6     61.5 MiB     15.3 MiB       b = [2] * 2000000
     7     46.2 MiB    -15.3 MiB       del b
     8     46.2 MiB      0.0 MiB       return a
```

### memray (Modern Memory Profiler)

```bash
# pip install memray

# Run with profiling
python -m memray run script.py

# Generate report
python -m memray flamegraph memray-script.py.bin

# Live monitoring
python -m memray run --live script.py
```

## 23.4 Detecting Memory Leaks

### Common Leak Patterns

```python
import gc
import tracemalloc

# Pattern 1: Growing containers
class LeakyCache:
    _cache = []  # Class variable accumulates!

    def add(self, item):
        self._cache.append(item)  # Never cleaned

# Pattern 2: Circular references with __del__
class Node:
    def __init__(self):
        self.children = []
        self.parent = None

    def add_child(self, child):
        child.parent = self  # Circular reference!
        self.children.append(child)

    def __del__(self):
        print("Node deleted")  # May prevent GC in older Python

# Pattern 3: Closures capturing variables
def create_handlers():
    handlers = []
    for i in range(1000):
        large_data = [0] * 10000  # Captured by closure!
        handlers.append(lambda: large_data[0])
    return handlers

# Pattern 4: Global/class-level caches
_global_cache = {}

def get_data(key):
    if key not in _global_cache:
        _global_cache[key] = expensive_computation(key)
    return _global_cache[key]  # Cache grows forever!
```

### Leak Detection Workflow

```python
import gc
import tracemalloc

def detect_leaks():
    # Force collection to clean up
    gc.collect()

    # Start tracking
    tracemalloc.start()

    # Snapshot before
    before = tracemalloc.take_snapshot()

    # Run suspected code multiple times
    for _ in range(100):
        suspected_function()

    # Force collection again
    gc.collect()

    # Snapshot after
    after = tracemalloc.take_snapshot()

    # Compare
    diff = after.compare_to(before, 'lineno')

    print("Potential leaks (memory that grew):")
    for stat in diff[:10]:
        if stat.size_diff > 0:
            print(stat)

    tracemalloc.stop()
```

### Using gc to Find Leaks

```python
import gc

# Enable debug output
gc.set_debug(gc.DEBUG_LEAK)

# Collect and check for uncollectable
gc.collect()
print(f"Uncollectable: {gc.garbage}")

# Find objects by type
gc.collect()
all_lists = [obj for obj in gc.get_objects() if isinstance(obj, list)]
print(f"Lists in memory: {len(all_lists)}")

# Find objects referencing a target
target = suspected_leaky_object
referrers = gc.get_referrers(target)
print(f"Objects referencing target: {len(referrers)}")
for ref in referrers[:5]:
    print(f"  {type(ref)}: {repr(ref)[:100]}")
```

## 23.5 Heap Dumps and Analysis

### Creating Heap Dumps

```python
import gc
import json
from collections import Counter

def heap_summary():
    """Create summary of objects on heap."""
    gc.collect()
    objects = gc.get_objects()

    # Count by type
    type_counts = Counter(type(obj).__name__ for obj in objects)

    # Size by type (approximate)
    import sys
    type_sizes = {}
    for obj in objects:
        type_name = type(obj).__name__
        type_sizes[type_name] = type_sizes.get(type_name, 0) + sys.getsizeof(obj)

    return {
        'counts': dict(type_counts.most_common(20)),
        'sizes': dict(sorted(type_sizes.items(),
                            key=lambda x: x[1], reverse=True)[:20])
    }

summary = heap_summary()
print(json.dumps(summary, indent=2))
```

### objgraph Visualization

```python
# pip install objgraph
import objgraph

# Show most common types
objgraph.show_most_common_types(limit=20)

# Show growth since last call
objgraph.show_growth()

# Find reference chains to an object
obj = some_leaked_object
objgraph.show_backrefs(obj, max_depth=5, filename='refs.png')

# Find what keeps an object alive
objgraph.show_chain(
    objgraph.find_backref_chain(obj, objgraph.is_proper_module),
    filename='chain.png'
)
```

## 23.6 Valgrind with Python

### Running Python Under Valgrind

```bash
# Build Python with valgrind support
./configure --with-valgrind
make

# Run with valgrind
valgrind --tool=memcheck \
         --leak-check=full \
         --show-leak-kinds=all \
         python script.py
```

### Valgrind Suppression File

```bash
# Python has known "leaks" (intentional caches)
# Use suppression file:
valgrind --suppressions=Misc/valgrind-python.supp \
         --leak-check=full \
         python script.py
```

## Debugging Workflow Summary

```
┌─────────────────────────────────────────────────────────────────┐
│                Memory Debugging Workflow                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Identify symptoms                                            │
│     - Memory usage growing over time?                           │
│     - Out of memory errors?                                      │
│     - Performance degradation?                                   │
│                                                                  │
│  2. Measure baseline                                             │
│     - tracemalloc.start()                                       │
│     - Take snapshot before                                       │
│                                                                  │
│  3. Reproduce issue                                              │
│     - Run suspected code                                         │
│     - Multiple iterations if needed                              │
│                                                                  │
│  4. Compare snapshots                                            │
│     - What types are growing?                                    │
│     - Which lines allocate most?                                │
│                                                                  │
│  5. Find references                                              │
│     - gc.get_referrers()                                        │
│     - objgraph.show_backrefs()                                  │
│                                                                  │
│  6. Fix and verify                                               │
│     - Break references                                           │
│     - Use weak references                                        │
│     - Add explicit cleanup                                       │
│     - Re-test to confirm fix                                    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Summary

- **`sys.getsizeof()`** for shallow size, **pympler** for deep size
- **`tracemalloc`** tracks allocations and compares snapshots
- **memory_profiler** shows line-by-line memory usage
- **gc module** helps find reference cycles and leaks
- **objgraph** visualizes object references
- Common leaks: growing caches, closures, circular references

## Practice Exercises

1. Profile a script with `tracemalloc` and find the biggest allocations
2. Use `gc.get_referrers()` to trace why an object isn't being collected
3. Create and detect a memory leak using the patterns shown
4. Use `objgraph` to visualize references to a leaked object

---

[← Previous: Memory Optimization](chapter-22-memory-optimization.md) | [Next: GIL Fundamentals →](../part-06-gil/chapter-24-gil-fundamentals.md)

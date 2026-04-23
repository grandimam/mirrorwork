# Chapter 21: Garbage Collection

## 21.1 Why Reference Counting Isn't Enough

Reference counting fails with circular references:

```python
import gc

# Create circular reference
class Node:
    def __init__(self):
        self.ref = None

a = Node()
b = Node()
a.ref = b  # a → b
b.ref = a  # b → a (cycle!)

# Delete variables
del a, b

# Objects still exist (refcount > 0 due to cycle)
# This is where garbage collection helps
gc.collect()  # Finds and collects cycles
```

## 21.2 Cyclic Garbage Collector

Python's GC specifically handles reference cycles:

```
┌─────────────────────────────────────────────────────────────────┐
│                  Cyclic Garbage Collector                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Objects that CAN participate in cycles:                         │
│  - Containers (list, dict, set, tuple)                          │
│  - User-defined classes                                          │
│  - Functions with closures                                       │
│                                                                  │
│  Objects that CANNOT participate in cycles:                      │
│  - Immutable atomic types (int, float, str, bytes)              │
│  - None, True, False                                            │
│                                                                  │
│  GC only tracks container objects (potential cycle members)     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### GC Algorithm (Mark and Sweep variant)

```
┌─────────────────────────────────────────────────────────────────┐
│                      GC Algorithm                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Start with all tracked objects                               │
│                                                                  │
│  2. For each object, subtract internal references                │
│     (references from other tracked objects)                      │
│     ┌───────┐     ┌───────┐                                     │
│     │ A (2) │────▶│ B (2) │  A.refcnt=2, B.refcnt=2             │
│     └───────┘◀────└───────┘  After subtract: A=1, B=1           │
│                                                                  │
│  3. Objects with count > 0 are reachable (roots)                │
│                                                                  │
│  4. Trace from roots, mark reachable objects                     │
│                                                                  │
│  5. Unreachable objects are garbage → collect them               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 21.3 Generational GC

Python uses generational garbage collection with three generations:

### 21.3.1 Generation 0 (Young Objects)

```python
import gc

# New objects start in generation 0
obj = []  # Born in generation 0

# Check generation thresholds
print(gc.get_threshold())  # (700, 10, 10)
# 700: Gen 0 collects after 700 allocations
# 10: Gen 1 collects after 10 Gen 0 collections
# 10: Gen 2 collects after 10 Gen 1 collections
```

### 21.3.2 Generation 1 (Middle-Aged)

Objects that survive a Gen 0 collection move to Gen 1.

### 21.3.3 Generation 2 (Old Objects)

Objects that survive a Gen 1 collection move to Gen 2.

### Generation Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                   Generational GC Flow                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  New object                                                      │
│      │                                                           │
│      ▼                                                           │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Generation 0 (young)                                    │    │
│  │  - Collected frequently (every 700 allocations)         │    │
│  │  - Most objects die young                                │    │
│  └──────────────────────┬──────────────────────────────────┘    │
│                         │ survives                               │
│                         ▼                                        │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Generation 1 (middle)                                   │    │
│  │  - Collected less frequently                             │    │
│  │  - Objects likely to live longer                         │    │
│  └──────────────────────┬──────────────────────────────────┘    │
│                         │ survives                               │
│                         ▼                                        │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Generation 2 (old)                                      │    │
│  │  - Collected infrequently                                │    │
│  │  - Long-lived objects                                    │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 21.4 GC Thresholds and Tuning

### Getting and Setting Thresholds

```python
import gc

# Get current thresholds
print(gc.get_threshold())  # (700, 10, 10)

# Set custom thresholds
gc.set_threshold(1000, 15, 15)  # Less frequent collection

# Get collection counts
print(gc.get_count())  # (123, 5, 2) - allocations since last collection
```

### Tuning Strategies

```python
import gc

# For long-running services: increase thresholds
gc.set_threshold(50000, 500, 1000)

# For latency-sensitive: disable auto GC, collect manually
gc.disable()
# ... time-critical code ...
gc.collect()  # Collect when latency doesn't matter
gc.enable()

# For memory-constrained: lower thresholds
gc.set_threshold(100, 5, 5)  # More frequent collection
```

## 21.5 The `gc` Module

### Basic Operations

```python
import gc

# Manual collection
collected = gc.collect()  # Collect all generations
print(f"Collected {collected} objects")

# Collect specific generation
gc.collect(0)  # Only generation 0
gc.collect(1)  # Generations 0 and 1
gc.collect(2)  # All generations (default)

# Enable/disable GC
gc.disable()  # Disable automatic collection
gc.enable()   # Enable automatic collection
print(gc.isenabled())  # Check if enabled
```

### Inspecting Objects

```python
import gc

# Get all tracked objects
all_objects = gc.get_objects()
print(f"Tracking {len(all_objects)} objects")

# Get objects by generation
gen0 = gc.get_objects(generation=0)
gen1 = gc.get_objects(generation=1)
gen2 = gc.get_objects(generation=2)

# Find referrers (what references this object?)
obj = [1, 2, 3]
container = [obj]
print(gc.get_referrers(obj))  # Shows container

# Find referents (what does this object reference?)
print(gc.get_referents(container))  # Shows obj
```

## 21.6 `gc.collect()` and Forced Collection

### When to Use Manual Collection

```python
import gc

# 1. After deleting large data structures
huge_data = load_huge_dataset()
process(huge_data)
del huge_data
gc.collect()  # Immediately free memory

# 2. Before memory-intensive operations
gc.collect()
result = memory_intensive_operation()

# 3. In idle time for latency-sensitive apps
def on_idle():
    gc.collect()

# 4. When debugging memory issues
gc.set_debug(gc.DEBUG_LEAK)
# ... suspicious code ...
gc.collect()
```

## 21.7 Finalizers (`__del__`) and GC

### Finalizer Behavior

```python
class Resource:
    def __init__(self, name):
        self.name = name
        print(f"Created {name}")

    def __del__(self):
        print(f"Destroyed {self.name}")

# Normal case
r = Resource("test")
del r  # __del__ called immediately (refcount → 0)

# With cycle - __del__ complicates things
class Node:
    def __init__(self):
        self.ref = None

    def __del__(self):
        print("Node deleted")

a = Node()
b = Node()
a.ref = b
b.ref = a
del a, b
# __del__ will be called when GC collects the cycle
gc.collect()
```

### Resurrection Problem

```python
import gc

# Object can "resurrect" itself in __del__
saved = []

class Zombie:
    def __del__(self):
        saved.append(self)  # Resurrects itself!
        print("I'm not dead yet!")

z = Zombie()
del z
gc.collect()
print(len(saved))  # 1 - zombie survived!

# This is why finalizers are problematic
```

## 21.8 Weak References and GC

```python
import weakref
import gc

class MyClass:
    pass

obj = MyClass()
weak = weakref.ref(obj)

print(weak())  # <MyClass object>

del obj
gc.collect()

print(weak())  # None - object was collected
```

### Weak Reference Callbacks

```python
import weakref

def callback(ref):
    print(f"Object collected! Reference: {ref}")

obj = object()
weak = weakref.ref(obj, callback)

del obj
# Output: Object collected! Reference: <weakref at 0x...>
```

## 21.9 Uncollectable Objects

Some cycles can't be collected:

```python
import gc

# Objects with __del__ in cycles were uncollectable (Python < 3.4)
# Python 3.4+ can collect them, but in undefined order

class LegacyProblem:
    def __del__(self):
        print("Cleaning up")

a = LegacyProblem()
b = LegacyProblem()
a.ref = b
b.ref = a
del a, b

gc.collect()
print(gc.garbage)  # Was non-empty in older Python
```

### Modern Python (3.4+)

```python
import gc

# Python 3.4+ handles cycles with finalizers
# But order of __del__ calls is undefined

gc.collect()
print(gc.garbage)  # Usually empty now
```

## GC Debug Flags

```python
import gc

# Debug flags
gc.set_debug(gc.DEBUG_STATS)      # Print collection statistics
gc.set_debug(gc.DEBUG_COLLECTABLE) # Print collectable objects
gc.set_debug(gc.DEBUG_UNCOLLECTABLE) # Print uncollectable
gc.set_debug(gc.DEBUG_LEAK)        # Print objects that look like leaks

# Combine flags
gc.set_debug(gc.DEBUG_STATS | gc.DEBUG_LEAK)

gc.collect()

# Turn off debugging
gc.set_debug(0)
```

## Summary

- GC handles **reference cycles** that ref counting can't
- **Three generations**: young objects collected frequently
- **Thresholds** control collection frequency
- **`gc` module** provides control and inspection
- **Finalizers** (`__del__`) can complicate collection
- **Weak references** help avoid cycles

## Practice Exercises

1. Create reference cycles and observe GC behavior
2. Tune GC thresholds and measure impact on performance
3. Use `gc.get_referrers()` to debug memory issues
4. Implement a cache using weak references

---

[← Previous: Reference Counting](chapter-20-reference-counting.md) | [Next: Memory Optimization →](chapter-22-memory-optimization.md)

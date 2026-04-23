# Lab 2: Memory Profiler

## Objective

Build a memory profiling tool to track object allocations, memory usage, and identify memory leaks.

## Prerequisites

- Understanding of Python memory management (Part 5)
- Knowledge of reference counting and garbage collection

## Lab Setup

```python
# lab02_memory_profiler.py
import sys
import gc
import weakref
import tracemalloc
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Set, Any
import time
```

## Exercise 1: Object Size Analyzer

Implement deep size calculation:

```python
@dataclass
class SizeReport:
    """Report of object memory usage."""
    shallow_size: int
    deep_size: int
    object_count: int
    type_breakdown: Dict[str, int]

def get_deep_size(obj, seen: Set[int] = None) -> int:
    """
    Calculate the deep (total) size of an object.

    TODO: Implement recursive size calculation that:
    1. Tracks seen objects to avoid cycles
    2. Handles containers (list, dict, set, tuple)
    3. Handles object __dict__ attributes
    """
    if seen is None:
        seen = set()

    obj_id = id(obj)
    if obj_id in seen:
        return 0
    seen.add(obj_id)

    size = sys.getsizeof(obj)

    if isinstance(obj, dict):
        size += sum(get_deep_size(k, seen) + get_deep_size(v, seen)
                    for k, v in obj.items())
    elif isinstance(obj, (list, tuple, set, frozenset)):
        size += sum(get_deep_size(item, seen) for item in obj)
    elif hasattr(obj, '__dict__'):
        size += get_deep_size(obj.__dict__, seen)
    elif hasattr(obj, '__slots__'):
        size += sum(get_deep_size(getattr(obj, slot, None), seen)
                    for slot in obj.__slots__ if hasattr(obj, slot))

    return size

def analyze_size(obj) -> SizeReport:
    """Analyze memory usage of an object."""
    seen = set()
    type_breakdown = defaultdict(int)
    object_count = 0

    def _analyze(o):
        nonlocal object_count
        obj_id = id(o)
        if obj_id in seen:
            return 0
        seen.add(obj_id)

        object_count += 1
        size = sys.getsizeof(o)
        type_breakdown[type(o).__name__] += size

        if isinstance(o, dict):
            for k, v in o.items():
                size += _analyze(k)
                size += _analyze(v)
        elif isinstance(o, (list, tuple, set, frozenset)):
            for item in o:
                size += _analyze(item)
        elif hasattr(o, '__dict__'):
            size += _analyze(o.__dict__)

        return size

    deep_size = _analyze(obj)

    return SizeReport(
        shallow_size=sys.getsizeof(obj),
        deep_size=deep_size,
        object_count=object_count,
        type_breakdown=dict(type_breakdown)
    )

# Test
data = {
    'users': [
        {'name': 'Alice', 'scores': [95, 87, 92]},
        {'name': 'Bob', 'scores': [88, 91, 85]},
    ],
    'metadata': {'version': 1, 'timestamp': time.time()}
}

report = analyze_size(data)
print(f"Shallow size: {report.shallow_size} bytes")
print(f"Deep size: {report.deep_size} bytes")
print(f"Object count: {report.object_count}")
print(f"Type breakdown: {report.type_breakdown}")
```

## Exercise 2: Allocation Tracker

Track object allocations using tracemalloc:

```python
class AllocationTracker:
    """Track memory allocations."""

    def __init__(self):
        self.snapshots: List[tracemalloc.Snapshot] = []
        self.is_tracking = False

    def start(self):
        """Start tracking allocations."""
        tracemalloc.start()
        self.is_tracking = True
        self.snapshots.clear()
        print("Allocation tracking started")

    def snapshot(self, label: str = ""):
        """Take a memory snapshot."""
        if not self.is_tracking:
            raise RuntimeError("Tracking not started")

        snap = tracemalloc.take_snapshot()
        self.snapshots.append((label, snap))
        print(f"Snapshot taken: {label}")
        return snap

    def stop(self):
        """Stop tracking and return summary."""
        tracemalloc.stop()
        self.is_tracking = False
        print("Allocation tracking stopped")

    def compare(self, idx1: int = 0, idx2: int = -1):
        """
        Compare two snapshots.

        TODO: Implement comparison showing:
        1. Memory difference
        2. New allocations
        3. Top allocation sites
        """
        if len(self.snapshots) < 2:
            print("Need at least 2 snapshots to compare")
            return

        label1, snap1 = self.snapshots[idx1]
        label2, snap2 = self.snapshots[idx2]

        print(f"\nComparing '{label1}' vs '{label2}':")
        print("=" * 60)

        # Get top differences
        top_stats = snap2.compare_to(snap1, 'lineno')

        print("\nTop 10 memory changes:")
        for stat in top_stats[:10]:
            print(f"  {stat}")

    def top_allocations(self, snapshot_idx: int = -1, limit: int = 10):
        """Show top allocations in a snapshot."""
        _, snap = self.snapshots[snapshot_idx]

        print(f"\nTop {limit} allocations:")
        top_stats = snap.statistics('lineno')

        for stat in top_stats[:limit]:
            print(f"  {stat}")

# Test
tracker = AllocationTracker()
tracker.start()

tracker.snapshot("initial")

# Allocate some objects
big_list = [i ** 2 for i in range(10000)]
big_dict = {f"key_{i}": f"value_{i}" for i in range(5000)}

tracker.snapshot("after allocations")

# Clean up
del big_list
del big_dict
gc.collect()

tracker.snapshot("after cleanup")

tracker.compare(0, 1)
tracker.compare(1, 2)
tracker.stop()
```

## Exercise 3: Reference Cycle Detector

Detect and visualize reference cycles:

```python
class CycleDetector:
    """Detect reference cycles in objects."""

    def __init__(self):
        self.cycles: List[List[Any]] = []

    def find_cycles(self, obj, path: List = None, seen: Set[int] = None):
        """
        TODO: Find reference cycles starting from obj.

        Use gc.get_referents() to get objects referenced by obj.
        Track path to detect when we visit an object twice.
        """
        if path is None:
            path = []
        if seen is None:
            seen = set()

        obj_id = id(obj)

        # Check if we've seen this object in current path (cycle!)
        if obj_id in [id(p) for p in path]:
            cycle_start = next(i for i, p in enumerate(path) if id(p) == obj_id)
            cycle = path[cycle_start:] + [obj]
            self.cycles.append(cycle)
            return

        # Skip if already fully explored
        if obj_id in seen:
            return
        seen.add(obj_id)

        # Skip basic types
        if isinstance(obj, (int, float, str, bytes, type(None))):
            return

        # Explore references
        path = path + [obj]
        for ref in gc.get_referents(obj):
            self.find_cycles(ref, path, seen)

    def detect_all_cycles(self):
        """Detect all cycles using gc module."""
        # Force collection to find unreachable cycles
        gc.collect()

        # Get objects in each generation
        cycles = []
        for obj in gc.garbage:
            cycles.append(obj)

        return cycles

    def visualize_cycle(self, cycle: List):
        """Print ASCII visualization of a cycle."""
        print("\nCycle detected:")
        print("  ", end="")
        for i, obj in enumerate(cycle):
            type_name = type(obj).__name__
            print(f"[{type_name}]", end="")
            if i < len(cycle) - 1:
                print(" -> ", end="")
        print()

# Test - create intentional cycle
class Node:
    def __init__(self, value):
        self.value = value
        self.next = None

    def __repr__(self):
        return f"Node({self.value})"

# Create cycle
node1 = Node(1)
node2 = Node(2)
node3 = Node(3)
node1.next = node2
node2.next = node3
node3.next = node1  # Cycle!

detector = CycleDetector()
detector.find_cycles(node1)

print(f"Found {len(detector.cycles)} cycles")
for cycle in detector.cycles[:3]:  # Show first 3
    detector.visualize_cycle(cycle)
```

## Exercise 4: Memory Leak Detector

Build a tool to detect potential memory leaks:

```python
class LeakDetector:
    """Detect potential memory leaks."""

    def __init__(self):
        self.object_counts: Dict[str, List[int]] = defaultdict(list)
        self.timestamps: List[float] = []

    def sample(self):
        """Take a sample of current object counts by type."""
        gc.collect()

        counts = defaultdict(int)
        for obj in gc.get_objects():
            counts[type(obj).__name__] += 1

        self.timestamps.append(time.time())
        for type_name, count in counts.items():
            self.object_counts[type_name].append(count)

    def analyze(self, min_growth_rate: float = 0.1):
        """
        TODO: Analyze samples for potential leaks.

        A leak is suspected when object count grows consistently.
        """
        if len(self.timestamps) < 2:
            print("Need at least 2 samples")
            return

        print("\nPotential Memory Leaks:")
        print("=" * 60)

        suspects = []

        for type_name, counts in self.object_counts.items():
            if len(counts) < 2:
                continue

            # Calculate growth
            initial = counts[0]
            final = counts[-1]

            if initial == 0:
                continue

            growth_rate = (final - initial) / initial

            # Check for consistent growth
            is_growing = all(counts[i] <= counts[i+1]
                           for i in range(len(counts)-1))

            if growth_rate > min_growth_rate and is_growing:
                suspects.append((type_name, initial, final, growth_rate))

        # Sort by growth rate
        suspects.sort(key=lambda x: x[3], reverse=True)

        for type_name, initial, final, rate in suspects[:10]:
            print(f"  {type_name}: {initial} -> {final} ({rate:.1%} growth)")

    def track_type(self, type_name: str):
        """Track specific type over time."""
        if type_name not in self.object_counts:
            print(f"No data for type: {type_name}")
            return

        counts = self.object_counts[type_name]
        print(f"\n{type_name} count over time:")
        for i, count in enumerate(counts):
            bar = '#' * (count // 100)
            print(f"  Sample {i}: {count:6d} {bar}")

# Test
detector = LeakDetector()

# Simulate leak
leaked_objects = []

for i in range(5):
    detector.sample()

    # Leak some objects
    leaked_objects.extend([{'data': 'x' * 1000} for _ in range(100)])

    time.sleep(0.1)

detector.analyze()
detector.track_type('dict')
```

## Exercise 5: Weak Reference Monitor

Monitor object lifecycle using weak references:

```python
class LifecycleMonitor:
    """Monitor object lifecycle using weak references."""

    def __init__(self):
        self.tracked: Dict[int, weakref.ref] = {}
        self.creation_times: Dict[int, float] = {}
        self.death_times: Dict[int, float] = {}
        self.type_names: Dict[int, str] = {}

    def track(self, obj, label: str = None):
        """
        TODO: Track an object's lifecycle.

        Use weakref.ref with a callback to detect when object is collected.
        """
        obj_id = id(obj)

        def on_death(ref):
            self.death_times[obj_id] = time.time()
            lifetime = self.death_times[obj_id] - self.creation_times[obj_id]
            print(f"Object {label or obj_id} ({self.type_names[obj_id]}) "
                  f"collected after {lifetime:.3f}s")

        self.tracked[obj_id] = weakref.ref(obj, on_death)
        self.creation_times[obj_id] = time.time()
        self.type_names[obj_id] = type(obj).__name__

        print(f"Tracking object {label or obj_id} ({type(obj).__name__})")

    def is_alive(self, obj_id: int) -> bool:
        """Check if tracked object is still alive."""
        if obj_id not in self.tracked:
            return False
        return self.tracked[obj_id]() is not None

    def report(self):
        """Report on all tracked objects."""
        print("\nLifecycle Report:")
        print("=" * 60)

        alive = 0
        dead = 0

        for obj_id, ref in self.tracked.items():
            type_name = self.type_names[obj_id]
            if ref() is not None:
                alive += 1
                age = time.time() - self.creation_times[obj_id]
                print(f"  {obj_id}: {type_name} - ALIVE ({age:.3f}s)")
            else:
                dead += 1
                lifetime = self.death_times.get(obj_id, 0) - self.creation_times[obj_id]
                print(f"  {obj_id}: {type_name} - DEAD (lived {lifetime:.3f}s)")

        print(f"\nSummary: {alive} alive, {dead} dead")

# Test
monitor = LifecycleMonitor()

class TestObject:
    def __init__(self, name):
        self.name = name

# Create and track objects
obj1 = TestObject("persistent")
obj2 = TestObject("temporary")

monitor.track(obj1, "obj1")
monitor.track(obj2, "obj2")

# Delete one
del obj2
gc.collect()

time.sleep(0.1)
monitor.report()
```

## Challenge: Complete Memory Profiler

Build a complete profiler combining all components:

```python
class MemoryProfiler:
    """Complete memory profiling tool."""

    def __init__(self):
        self.tracker = AllocationTracker()
        self.leak_detector = LeakDetector()
        self.lifecycle_monitor = LifecycleMonitor()

    def profile(self, func, *args, **kwargs):
        """Profile a function's memory usage."""
        print(f"Profiling: {func.__name__}")
        print("=" * 60)

        # Start tracking
        self.tracker.start()
        self.tracker.snapshot("before")
        self.leak_detector.sample()

        # Run function
        start_time = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start_time

        # After tracking
        self.tracker.snapshot("after")
        self.leak_detector.sample()

        # Force GC and final snapshot
        gc.collect()
        self.tracker.snapshot("after_gc")
        self.leak_detector.sample()

        # Reports
        print(f"\nExecution time: {elapsed:.3f}s")
        self.tracker.compare(0, 1)
        self.tracker.compare(1, 2)
        self.leak_detector.analyze()

        self.tracker.stop()
        return result

# Test
def memory_hungry_function():
    """Function that allocates lots of memory."""
    data = []
    for i in range(1000):
        data.append({
            'id': i,
            'values': list(range(100)),
            'nested': {'a': 1, 'b': 2, 'c': [1, 2, 3]}
        })
    return len(data)

profiler = MemoryProfiler()
result = profiler.profile(memory_hungry_function)
print(f"\nResult: {result}")
```

## Expected Output

Your profiler should show:
- Memory usage before/after function execution
- Allocation sites and sizes
- Potential memory leaks
- Object lifecycle information

## Submission

1. Complete all TODO sections
2. Profile a real application or library
3. Identify and document any memory issues found
4. Bonus: Add memory usage plotting with matplotlib

---

[Next: Lab 3 - GIL Visualizer →](lab-03-gil-visualizer.md)

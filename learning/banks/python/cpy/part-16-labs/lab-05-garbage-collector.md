# Lab 5: Garbage Collector

## Objective

Build tools to understand, monitor, and interact with Python's garbage collector, including cycle detection and collection statistics.

## Prerequisites

- Understanding of memory management (Part 5)
- Knowledge of reference counting and cyclic garbage collection

## Lab Setup

```python
# lab05_garbage_collector.py
import gc
import sys
import weakref
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Set, Any, Optional
```

## Exercise 1: GC Statistics Monitor

Monitor garbage collection statistics:

```python
@dataclass
class GCStats:
    """Garbage collection statistics."""
    collections: int = 0
    collected: int = 0
    uncollectable: int = 0
    elapsed_time: float = 0.0
    generation: int = 0

class GCMonitor:
    """Monitor garbage collection activity."""

    def __init__(self):
        self.stats: List[GCStats] = []
        self.callbacks_installed = False
        self._gc_start_time = 0

    def _gc_callback(self, phase: str, info: dict):
        """
        TODO: Implement GC callback to track collection events.

        phase: 'start' or 'stop'
        info: {'generation': gen, 'collected': count, 'uncollectable': count}
        """
        if phase == 'start':
            self._gc_start_time = time.perf_counter()
        elif phase == 'stop':
            elapsed = time.perf_counter() - self._gc_start_time

            stats = GCStats(
                collections=1,
                collected=info.get('collected', 0),
                uncollectable=info.get('uncollectable', 0),
                elapsed_time=elapsed,
                generation=info.get('generation', 0)
            )
            self.stats.append(stats)

    def install(self):
        """Install GC callbacks."""
        if not self.callbacks_installed:
            gc.callbacks.append(self._gc_callback)
            self.callbacks_installed = True
            print("GC monitoring installed")

    def uninstall(self):
        """Remove GC callbacks."""
        if self.callbacks_installed:
            gc.callbacks.remove(self._gc_callback)
            self.callbacks_installed = False
            print("GC monitoring removed")

    def get_summary(self) -> dict:
        """Get summary of GC activity."""
        if not self.stats:
            return {'message': 'No GC activity recorded'}

        total_collections = len(self.stats)
        total_collected = sum(s.collected for s in self.stats)
        total_uncollectable = sum(s.uncollectable for s in self.stats)
        total_time = sum(s.elapsed_time for s in self.stats)

        by_generation = defaultdict(lambda: {'count': 0, 'collected': 0, 'time': 0})
        for s in self.stats:
            by_generation[s.generation]['count'] += 1
            by_generation[s.generation]['collected'] += s.collected
            by_generation[s.generation]['time'] += s.elapsed_time

        return {
            'total_collections': total_collections,
            'total_collected': total_collected,
            'total_uncollectable': total_uncollectable,
            'total_time_ms': total_time * 1000,
            'by_generation': dict(by_generation)
        }

    def report(self):
        """Print GC report."""
        summary = self.get_summary()

        print("\nGarbage Collection Report")
        print("=" * 50)
        print(f"Total collections: {summary.get('total_collections', 0)}")
        print(f"Objects collected: {summary.get('total_collected', 0)}")
        print(f"Uncollectable: {summary.get('total_uncollectable', 0)}")
        print(f"Total GC time: {summary.get('total_time_ms', 0):.2f}ms")

        if 'by_generation' in summary:
            print("\nBy Generation:")
            for gen, data in sorted(summary['by_generation'].items()):
                print(f"  Gen {gen}: {data['count']} collections, "
                      f"{data['collected']} objects, "
                      f"{data['time']*1000:.2f}ms")

gc_monitor = GCMonitor()
```

## Exercise 2: Object Graph Analyzer

Analyze object reference graphs:

```python
class ObjectGraphAnalyzer:
    """Analyze object reference graphs."""

    def __init__(self):
        self.visited: Set[int] = set()
        self.graph: Dict[int, List[int]] = {}

    def build_graph(self, root: Any, max_depth: int = 10):
        """
        TODO: Build reference graph starting from root object.

        Use gc.get_referents() to find objects referenced by root.
        Track edges in self.graph as adjacency list.
        """
        self.visited.clear()
        self.graph.clear()

        self._build_recursive(root, 0, max_depth)

        return self.graph

    def _build_recursive(self, obj: Any, depth: int, max_depth: int):
        """Recursively build graph."""
        if depth > max_depth:
            return

        obj_id = id(obj)

        if obj_id in self.visited:
            return

        self.visited.add(obj_id)
        self.graph[obj_id] = []

        # Skip primitive types
        if isinstance(obj, (int, float, str, bytes, type(None), bool)):
            return

        # Get referents
        try:
            referents = gc.get_referents(obj)
            for ref in referents:
                ref_id = id(ref)
                self.graph[obj_id].append(ref_id)
                self._build_recursive(ref, depth + 1, max_depth)
        except:
            pass

    def find_back_edges(self) -> List[tuple]:
        """Find back edges (potential cycles) in the graph."""
        back_edges = []

        color: Dict[int, str] = {}  # white, gray, black

        def dfs(node: int):
            color[node] = 'gray'

            for neighbor in self.graph.get(node, []):
                if neighbor not in color:
                    dfs(neighbor)
                elif color[neighbor] == 'gray':
                    # Back edge found!
                    back_edges.append((node, neighbor))

            color[node] = 'black'

        for node in self.graph:
            if node not in color:
                dfs(node)

        return back_edges

    def get_object_info(self, obj_id: int) -> dict:
        """Get information about an object by id."""
        for obj in gc.get_objects():
            if id(obj) == obj_id:
                return {
                    'type': type(obj).__name__,
                    'size': sys.getsizeof(obj),
                    'refcount': sys.getrefcount(obj) - 1,  # Subtract our reference
                    'repr': repr(obj)[:100]
                }
        return {'error': 'Object not found (may have been collected)'}

    def visualize(self, obj_id_to_name: Dict[int, str] = None):
        """Visualize graph as ASCII."""
        if not self.graph:
            print("No graph built")
            return

        print("\nObject Reference Graph:")
        print("=" * 50)

        for obj_id, refs in list(self.graph.items())[:20]:  # Limit output
            info = self.get_object_info(obj_id)
            name = obj_id_to_name.get(obj_id, '') if obj_id_to_name else ''

            print(f"\n[{info.get('type', '?')}] {name} (id={obj_id})")
            print(f"  size={info.get('size', '?')}, refcount={info.get('refcount', '?')}")

            if refs:
                print(f"  References: {len(refs)} objects")
                for ref_id in refs[:5]:
                    ref_info = self.get_object_info(ref_id)
                    print(f"    -> [{ref_info.get('type', '?')}] id={ref_id}")

graph_analyzer = ObjectGraphAnalyzer()
```

## Exercise 3: Cycle Collector Simulator

Simulate the cycle collection algorithm:

```python
class CycleCollectorSimulator:
    """Simulate Python's cycle collection algorithm."""

    def __init__(self):
        self.objects: Dict[int, dict] = {}  # id -> {refs, refcount, gc_refs}
        self.root_set: Set[int] = set()

    def add_object(self, obj_id: int, refs: List[int], external_refs: int = 1):
        """
        Add an object to the simulation.

        refs: list of object ids this object references
        external_refs: number of references from outside the tracked set
        """
        self.objects[obj_id] = {
            'refs': refs,
            'refcount': len([r for r in self.objects.values()
                           if obj_id in r.get('refs', [])]) + external_refs,
            'gc_refs': 0,
            'color': 'white'
        }

        if external_refs > 0:
            self.root_set.add(obj_id)

    def collect(self) -> List[int]:
        """
        TODO: Implement cycle collection algorithm.

        Steps:
        1. Set gc_refs = refcount for all objects
        2. For each object, decrement gc_refs of objects it references
        3. Objects with gc_refs > 0 are reachable from outside
        4. Mark reachable objects
        5. Collect unreachable objects
        """
        collected = []

        # Step 1: Initialize gc_refs
        for obj_id, obj in self.objects.items():
            obj['gc_refs'] = obj['refcount']
            obj['color'] = 'white'

        # Step 2: Subtract internal references
        for obj_id, obj in self.objects.items():
            for ref_id in obj['refs']:
                if ref_id in self.objects:
                    self.objects[ref_id]['gc_refs'] -= 1

        # Step 3 & 4: Mark reachable objects
        # Objects with gc_refs > 0 have external references
        to_visit = [obj_id for obj_id, obj in self.objects.items()
                   if obj['gc_refs'] > 0]

        while to_visit:
            obj_id = to_visit.pop()
            if self.objects[obj_id]['color'] == 'black':
                continue

            self.objects[obj_id]['color'] = 'black'

            for ref_id in self.objects[obj_id]['refs']:
                if ref_id in self.objects and self.objects[ref_id]['color'] == 'white':
                    to_visit.append(ref_id)

        # Step 5: Collect white objects
        for obj_id, obj in list(self.objects.items()):
            if obj['color'] == 'white':
                collected.append(obj_id)
                del self.objects[obj_id]

        return collected

    def visualize_state(self):
        """Visualize current object state."""
        print("\nObject State:")
        print("=" * 60)
        print(f"{'ID':>6} | {'RefCount':>8} | {'GC Refs':>7} | {'Color':>6} | Refs")
        print("-" * 60)

        for obj_id, obj in sorted(self.objects.items()):
            refs_str = ','.join(map(str, obj['refs'][:5]))
            if len(obj['refs']) > 5:
                refs_str += '...'

            print(f"{obj_id:>6} | {obj['refcount']:>8} | {obj['gc_refs']:>7} | "
                  f"{obj['color']:>6} | [{refs_str}]")

# Demo: Simulate cycle collection
def demo_cycle_collection():
    """Demonstrate cycle collection."""
    simulator = CycleCollectorSimulator()

    # Create objects forming a cycle
    # A -> B -> C -> A (cycle)
    # D -> A (external reference to A)

    simulator.add_object(1, [2], external_refs=0)  # A
    simulator.add_object(2, [3], external_refs=0)  # B
    simulator.add_object(3, [1], external_refs=0)  # C (points back to A)
    simulator.add_object(4, [1], external_refs=1)  # D (has external ref)

    print("Before collection:")
    simulator.visualize_state()

    # Now remove external reference to D
    simulator.objects[4]['refcount'] -= 1
    simulator.root_set.discard(4)

    print("\nAfter removing external reference to D:")
    collected = simulator.collect()

    print(f"\nCollected objects: {collected}")

    print("\nAfter collection:")
    simulator.visualize_state()

demo_cycle_collection()
```

## Exercise 4: Generation Analyzer

Analyze object distribution across generations:

```python
class GenerationAnalyzer:
    """Analyze GC generations."""

    def __init__(self):
        self.snapshots: List[dict] = []

    def snapshot(self, label: str = ""):
        """Take snapshot of generation state."""
        gc.collect()  # Ensure clean state

        snapshot = {
            'label': label,
            'time': time.perf_counter(),
            'thresholds': gc.get_threshold(),
            'counts': gc.get_count(),
            'generations': []
        }

        for gen in range(3):
            objects = gc.get_objects(gen) if hasattr(gc, 'get_objects') else []

            type_counts = defaultdict(int)
            total_size = 0

            for obj in objects[:10000]:  # Limit for performance
                type_counts[type(obj).__name__] += 1
                try:
                    total_size += sys.getsizeof(obj)
                except:
                    pass

            snapshot['generations'].append({
                'generation': gen,
                'object_count': len(objects),
                'total_size': total_size,
                'type_breakdown': dict(type_counts)
            })

        self.snapshots.append(snapshot)
        return snapshot

    def compare_snapshots(self, idx1: int = 0, idx2: int = -1):
        """
        TODO: Compare two snapshots to see what changed.

        Show: new objects, deleted objects, promoted objects
        """
        if len(self.snapshots) < 2:
            print("Need at least 2 snapshots")
            return

        snap1 = self.snapshots[idx1]
        snap2 = self.snapshots[idx2]

        print(f"\nComparing '{snap1['label']}' vs '{snap2['label']}'")
        print("=" * 60)

        for gen in range(3):
            gen1 = snap1['generations'][gen]
            gen2 = snap2['generations'][gen]

            count_diff = gen2['object_count'] - gen1['object_count']
            size_diff = gen2['total_size'] - gen1['total_size']

            print(f"\nGeneration {gen}:")
            print(f"  Objects: {gen1['object_count']} -> {gen2['object_count']} "
                  f"({count_diff:+d})")
            print(f"  Size: {gen1['total_size']:,} -> {gen2['total_size']:,} "
                  f"({size_diff:+,} bytes)")

            # Type changes
            types1 = gen1['type_breakdown']
            types2 = gen2['type_breakdown']

            all_types = set(types1.keys()) | set(types2.keys())
            significant_changes = []

            for t in all_types:
                diff = types2.get(t, 0) - types1.get(t, 0)
                if abs(diff) > 10:
                    significant_changes.append((t, diff))

            if significant_changes:
                print("  Significant type changes:")
                for t, diff in sorted(significant_changes, key=lambda x: -abs(x[1]))[:5]:
                    print(f"    {t}: {diff:+d}")

    def report(self):
        """Print generation analysis report."""
        gc.collect()

        print("\nGC Generation Analysis")
        print("=" * 60)

        thresholds = gc.get_threshold()
        counts = gc.get_count()

        print(f"\nThresholds: {thresholds}")
        print(f"Current counts: {counts}")

        print("\nGeneration breakdown:")
        for gen in range(3):
            try:
                objects = gc.get_objects(gen)

                type_counts = defaultdict(int)
                for obj in objects[:1000]:
                    type_counts[type(obj).__name__] += 1

                print(f"\n  Generation {gen}: {len(objects)} objects")
                print("  Top types:")
                for t, count in sorted(type_counts.items(),
                                       key=lambda x: -x[1])[:5]:
                    print(f"    {t}: {count}")
            except TypeError:
                # get_objects doesn't support generation arg in older Python
                pass

gen_analyzer = GenerationAnalyzer()
```

## Exercise 5: Complete GC Toolkit

Combine all components:

```python
class GCToolkit:
    """Complete garbage collection analysis toolkit."""

    def __init__(self):
        self.monitor = GCMonitor()
        self.graph_analyzer = ObjectGraphAnalyzer()
        self.gen_analyzer = GenerationAnalyzer()

    def start_monitoring(self):
        """Start GC monitoring."""
        self.monitor.install()

    def stop_monitoring(self):
        """Stop GC monitoring and report."""
        self.monitor.uninstall()
        self.monitor.report()

    def analyze_object(self, obj: Any, max_depth: int = 5):
        """Analyze an object's reference graph."""
        print(f"\nAnalyzing object: {type(obj).__name__}")
        print("=" * 50)

        # Basic info
        print(f"Size: {sys.getsizeof(obj)} bytes")
        print(f"Reference count: {sys.getrefcount(obj) - 1}")

        # Build and analyze graph
        self.graph_analyzer.build_graph(obj, max_depth)

        back_edges = self.graph_analyzer.find_back_edges()
        if back_edges:
            print(f"\nPotential cycles found: {len(back_edges)}")

        self.graph_analyzer.visualize()

    def find_leaks(self) -> List[Any]:
        """
        TODO: Find potential memory leaks.

        Look for:
        - Uncollectable objects
        - Large objects in gen2
        - Unexpected object accumulation
        """
        leaks = []

        # Check for uncollectable objects
        gc.collect()
        if gc.garbage:
            print(f"\nUncollectable objects: {len(gc.garbage)}")
            for obj in gc.garbage[:10]:
                print(f"  {type(obj).__name__}: {repr(obj)[:50]}")
                leaks.append(obj)

        # Check gen2 for unusual objects
        try:
            gen2_objects = gc.get_objects(2)

            type_counts = defaultdict(int)
            for obj in gen2_objects:
                type_counts[type(obj).__name__] += 1

            # Flag types with unusually high counts
            avg_count = sum(type_counts.values()) / len(type_counts) if type_counts else 0

            print("\nGen2 objects with high counts:")
            for t, count in sorted(type_counts.items(), key=lambda x: -x[1])[:5]:
                if count > avg_count * 2:
                    print(f"  {t}: {count} (potential leak)")
        except:
            pass

        return leaks

    def force_collection(self, verbose: bool = True):
        """Force garbage collection on all generations."""
        if verbose:
            print("\nForcing garbage collection...")

        collected = []
        for gen in range(3):
            count = gc.collect(gen)
            collected.append(count)
            if verbose:
                print(f"  Generation {gen}: collected {count} objects")

        return collected

    def full_report(self):
        """Generate comprehensive GC report."""
        print("\n" + "=" * 70)
        print("Complete Garbage Collection Report")
        print("=" * 70)

        # GC stats
        self.monitor.report()

        # Generation analysis
        self.gen_analyzer.report()

        # Check for issues
        self.find_leaks()

        # Collection stats
        self.force_collection()

# Demo usage
def demo_gc_toolkit():
    """Demonstrate the GC toolkit."""
    toolkit = GCToolkit()

    # Start monitoring
    toolkit.start_monitoring()
    toolkit.gen_analyzer.snapshot("initial")

    # Create some objects and cycles
    class Node:
        def __init__(self, value):
            self.value = value
            self.next = None

    # Create cycle
    nodes = [Node(i) for i in range(1000)]
    for i in range(len(nodes) - 1):
        nodes[i].next = nodes[i + 1]
    nodes[-1].next = nodes[0]  # Complete the cycle

    toolkit.gen_analyzer.snapshot("after_creation")

    # Analyze one node
    toolkit.analyze_object(nodes[0])

    # Break reference
    del nodes
    gc.collect()

    toolkit.gen_analyzer.snapshot("after_deletion")

    # Compare
    toolkit.gen_analyzer.compare_snapshots(0, -1)

    # Full report
    toolkit.stop_monitoring()
    toolkit.full_report()

if __name__ == "__main__":
    demo_gc_toolkit()
```

## Expected Output

```
Analyzing object: Node
==================================================
Size: 48 bytes
Reference count: 2

Potential cycles found: 1

Object Reference Graph:
==================================================
[Node] (id=4567890)
  size=48, refcount=2
  References: 2 objects
    -> [dict] id=4567891
    -> [Node] id=4567892

GC Generation Analysis
============================================================
Thresholds: (700, 10, 10)
Current counts: (523, 7, 2)

Generation 0: 523 objects
  Top types:
    dict: 156
    list: 89
    tuple: 67
```

## Submission

1. Complete all TODO sections
2. Create and detect a memory leak
3. Profile a real application's GC behavior
4. Bonus: Implement automatic leak detection

---

[Next: Lab 6 - Frame Inspector →](lab-06-frame-inspector.md)

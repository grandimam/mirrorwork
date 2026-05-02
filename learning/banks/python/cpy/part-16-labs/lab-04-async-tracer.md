# Lab 4: Async Tracer

## Objective

Build a tracing tool to visualize asyncio task execution, coroutine scheduling, and event loop behavior.

## Prerequisites

- Understanding of asyncio (Part 7)
- Knowledge of async/await syntax
- Familiarity with event loops

## Lab Setup

```python
# lab04_async_tracer.py
import asyncio
import sys
import time
import functools
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from contextlib import contextmanager
import weakref
```

## Exercise 1: Coroutine Lifecycle Tracker

Track coroutine creation, execution, and completion:

```python
@dataclass
class CoroutineEvent:
    """Event in coroutine lifecycle."""
    timestamp: float
    coro_id: int
    coro_name: str
    event_type: str  # 'create', 'start', 'suspend', 'resume', 'complete', 'error'
    task_name: Optional[str] = None
    metadata: dict = field(default_factory=dict)

class CoroutineTracker:
    """Track coroutine lifecycle events."""

    def __init__(self):
        self.events: List[CoroutineEvent] = []
        self.active_coros: Dict[int, dict] = {}
        self.start_time = time.perf_counter()

    def log_event(self, coro, event_type: str, **metadata):
        """Log a coroutine event."""
        coro_id = id(coro)

        event = CoroutineEvent(
            timestamp=time.perf_counter() - self.start_time,
            coro_id=coro_id,
            coro_name=coro.__qualname__ if hasattr(coro, '__qualname__') else str(coro),
            event_type=event_type,
            task_name=asyncio.current_task().get_name() if asyncio.current_task() else None,
            metadata=metadata
        )

        self.events.append(event)

        if event_type == 'create':
            self.active_coros[coro_id] = {
                'name': event.coro_name,
                'created': event.timestamp,
                'state': 'created'
            }
        elif event_type in ('complete', 'error'):
            if coro_id in self.active_coros:
                self.active_coros[coro_id]['state'] = event_type
                self.active_coros[coro_id]['ended'] = event.timestamp

    def wrap_coroutine(self, coro):
        """
        TODO: Wrap a coroutine to track its lifecycle.

        Create wrapper that logs: create, start, suspend, resume, complete/error
        """
        coro_id = id(coro)
        self.log_event(coro, 'create')

        async def wrapped():
            self.log_event(coro, 'start')

            try:
                result = await coro
                self.log_event(coro, 'complete', result_type=type(result).__name__)
                return result
            except Exception as e:
                self.log_event(coro, 'error', error=str(e))
                raise

        return wrapped()

    def get_timeline(self) -> str:
        """Generate timeline of events."""
        lines = ["Coroutine Timeline:", "=" * 60]

        for event in sorted(self.events, key=lambda e: e.timestamp):
            lines.append(
                f"{event.timestamp:8.4f}s | {event.event_type:10s} | "
                f"{event.coro_name[:30]:30s} | {event.task_name or '-'}"
            )

        return '\n'.join(lines)

tracker = CoroutineTracker()
```

## Exercise 2: Task Scheduler Visualizer

Visualize how tasks are scheduled on the event loop:

```python
class TaskSchedulerViz:
    """Visualize task scheduling."""

    def __init__(self):
        self.tasks: Dict[str, dict] = {}
        self.schedule_events: List[dict] = []
        self.start_time = time.perf_counter()

    def _now(self) -> float:
        return time.perf_counter() - self.start_time

    async def create_task(self, coro, name: str = None):
        """
        TODO: Create and track an asyncio task.

        Track: creation time, name, state transitions
        """
        task = asyncio.create_task(coro, name=name)
        task_id = name or f"task-{id(task)}"

        self.tasks[task_id] = {
            'created': self._now(),
            'started': None,
            'completed': None,
            'state': 'pending',
            'events': []
        }

        self.schedule_events.append({
            'time': self._now(),
            'type': 'create',
            'task': task_id
        })

        # Add done callback
        def on_done(t):
            self.tasks[task_id]['completed'] = self._now()
            self.tasks[task_id]['state'] = 'done' if not t.cancelled() else 'cancelled'
            self.schedule_events.append({
                'time': self._now(),
                'type': 'complete',
                'task': task_id
            })

        task.add_done_callback(on_done)

        return task

    def visualize(self, width: int = 50):
        """Create ASCII timeline of task execution."""
        if not self.tasks:
            return "No tasks recorded"

        # Find time bounds
        max_time = max(
            t.get('completed', t['created']) or t['created']
            for t in self.tasks.values()
        )

        if max_time == 0:
            return "No task activity"

        lines = ["Task Execution Timeline:", "=" * (width + 25)]

        for task_id, data in self.tasks.items():
            # Calculate positions
            start_pos = int(data['created'] / max_time * (width - 1))
            end_pos = int((data.get('completed') or max_time) / max_time * (width - 1))

            # Build timeline
            line = [' '] * width
            for i in range(start_pos, min(end_pos + 1, width)):
                if i == start_pos:
                    line[i] = '['
                elif i == end_pos:
                    line[i] = ']'
                else:
                    line[i] = '='

            state_char = {'done': '✓', 'cancelled': 'x', 'pending': '?'}.get(data['state'], '.')
            lines.append(f"{task_id:20s} |{''.join(line)}| {state_char}")

        lines.append(f"{'Time':20s} |0{' ' * (width - 6)}{max_time:.3f}s|")

        return '\n'.join(lines)

scheduler_viz = TaskSchedulerViz()
```

## Exercise 3: Event Loop Monitor

Monitor event loop iterations and callbacks:

```python
class EventLoopMonitor:
    """Monitor event loop behavior."""

    def __init__(self, loop: asyncio.AbstractEventLoop = None):
        self.loop = loop or asyncio.get_event_loop()
        self.iterations: List[dict] = []
        self.callbacks_executed: List[dict] = []
        self.current_iteration = 0
        self._original_run_once = None

    def install(self):
        """
        TODO: Install monitoring hooks on the event loop.

        Note: This is implementation-specific and may not work on all loops.
        """
        # We'll use a different approach - wrap time.sleep and other I/O
        self._original_run_once = getattr(self.loop, '_run_once', None)

        # Track using debug mode
        self.loop.set_debug(True)
        self.loop.slow_callback_duration = 0.001  # Log callbacks > 1ms

    def uninstall(self):
        """Remove monitoring hooks."""
        if self._original_run_once:
            self.loop._run_once = self._original_run_once

    async def monitor_execution(self, coro):
        """Monitor coroutine execution with timing."""
        start = time.perf_counter()

        try:
            result = await coro
            return result
        finally:
            elapsed = time.perf_counter() - start
            self.callbacks_executed.append({
                'coro': coro.__qualname__ if hasattr(coro, '__qualname__') else str(coro),
                'duration': elapsed,
                'time': time.perf_counter()
            })

    def report(self):
        """Generate event loop report."""
        lines = [
            "Event Loop Monitor Report",
            "=" * 50
        ]

        if self.callbacks_executed:
            lines.append(f"\nCallbacks executed: {len(self.callbacks_executed)}")

            total_time = sum(c['duration'] for c in self.callbacks_executed)
            lines.append(f"Total execution time: {total_time*1000:.2f}ms")

            # Top 5 slowest
            slowest = sorted(self.callbacks_executed,
                           key=lambda c: c['duration'],
                           reverse=True)[:5]

            lines.append("\nSlowest callbacks:")
            for cb in slowest:
                lines.append(f"  {cb['coro']}: {cb['duration']*1000:.2f}ms")

        return '\n'.join(lines)

loop_monitor = EventLoopMonitor()
```

## Exercise 4: Async Context Tracker

Track async context and task relationships:

```python
class AsyncContextTracker:
    """Track async context and task hierarchy."""

    def __init__(self):
        self.task_tree: Dict[str, List[str]] = defaultdict(list)
        self.task_contexts: Dict[str, dict] = {}

    async def traced_task(self, coro, name: str = None):
        """
        TODO: Create task with context tracking.

        Track:
        - Parent task (who created this task)
        - Child tasks (tasks created by this task)
        - Context variables
        """
        parent_task = asyncio.current_task()
        parent_name = parent_task.get_name() if parent_task else "root"

        task = asyncio.create_task(coro, name=name)
        task_name = task.get_name()

        # Track relationship
        self.task_tree[parent_name].append(task_name)

        # Track context
        self.task_contexts[task_name] = {
            'parent': parent_name,
            'created_at': time.perf_counter(),
            'children': []
        }

        return task

    def visualize_tree(self, root: str = "root", indent: int = 0) -> str:
        """Visualize task tree."""
        lines = []

        prefix = "  " * indent
        connector = "├── " if indent > 0 else ""

        lines.append(f"{prefix}{connector}{root}")

        children = self.task_tree.get(root, [])
        for i, child in enumerate(children):
            is_last = i == len(children) - 1
            child_prefix = "└── " if is_last else "├── "

            lines.append(f"{prefix}  {child_prefix}{child}")

            # Recurse for children's children
            grandchildren = self.task_tree.get(child, [])
            for gc in grandchildren:
                lines.append(f"{prefix}      └── {gc}")

        return '\n'.join(lines)

context_tracker = AsyncContextTracker()
```

## Exercise 5: Complete Async Tracer

Combine all components:

```python
class AsyncTracer:
    """Complete async tracing tool."""

    def __init__(self):
        self.coro_tracker = CoroutineTracker()
        self.scheduler_viz = TaskSchedulerViz()
        self.loop_monitor = EventLoopMonitor()
        self.context_tracker = AsyncContextTracker()
        self.start_time = time.perf_counter()

    def trace(self, func: Callable):
        """
        Decorator to trace async functions.

        TODO: Implement decorator that tracks all coroutine executions.
        """
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            coro = func(*args, **kwargs)

            # Log coroutine creation
            self.coro_tracker.log_event(coro, 'create',
                                        args=str(args)[:50],
                                        kwargs=str(kwargs)[:50])

            start = time.perf_counter()
            self.coro_tracker.log_event(coro, 'start')

            try:
                result = await coro
                self.coro_tracker.log_event(coro, 'complete',
                                           duration=time.perf_counter() - start)
                return result
            except Exception as e:
                self.coro_tracker.log_event(coro, 'error',
                                           exception=str(e))
                raise

        return wrapper

    async def create_traced_task(self, coro, name: str = None):
        """Create a task with full tracing."""
        # Track in scheduler viz
        task = await self.scheduler_viz.create_task(coro, name)

        # Track context
        await self.context_tracker.traced_task(coro, name)

        return task

    async def run_traced(self, main_coro):
        """Run a coroutine with full tracing enabled."""
        self.loop_monitor.install()

        try:
            result = await self.coro_tracker.wrap_coroutine(main_coro)
            return result
        finally:
            self.loop_monitor.uninstall()
            self._print_report()

    def _print_report(self):
        """Print comprehensive trace report."""
        print("\n" + "=" * 70)
        print("Async Execution Trace Report")
        print("=" * 70)

        # Coroutine timeline
        print("\n" + self.coro_tracker.get_timeline())

        # Task scheduling
        print("\n" + self.scheduler_viz.visualize())

        # Event loop stats
        print("\n" + self.loop_monitor.report())

        # Task tree
        print("\nTask Hierarchy:")
        print(self.context_tracker.visualize_tree())

tracer = AsyncTracer()
```

## Demo Application

```python
# Demo async application to trace

@tracer.trace
async def fetch_data(url: str, delay: float = 0.1):
    """Simulate fetching data."""
    await asyncio.sleep(delay)
    return f"data from {url}"

@tracer.trace
async def process_item(item: str):
    """Process a single item."""
    await asyncio.sleep(0.05)
    return item.upper()

@tracer.trace
async def main():
    """Main async function."""
    # Create parallel tasks
    urls = ['url1', 'url2', 'url3']

    # Fetch all URLs
    fetch_tasks = [
        await tracer.create_traced_task(fetch_data(url), name=f"fetch-{url}")
        for url in urls
    ]

    results = await asyncio.gather(*fetch_tasks)

    # Process results
    process_tasks = [
        await tracer.create_traced_task(process_item(r), name=f"process-{i}")
        for i, r in enumerate(results)
    ]

    final_results = await asyncio.gather(*process_tasks)

    return final_results

# Run traced
async def run():
    result = await tracer.run_traced(main())
    print(f"\nFinal result: {result}")

if __name__ == "__main__":
    asyncio.run(run())
```

## Expected Output

```
======================================================================
Async Execution Trace Report
======================================================================

Coroutine Timeline:
============================================================
  0.0000s | create     | main                           | Task-1
  0.0001s | start      | main                           | Task-1
  0.0002s | create     | fetch_data                     | Task-1
  0.0003s | create     | fetch_data                     | Task-1
  0.0003s | create     | fetch_data                     | Task-1
  0.1012s | complete   | fetch_data                     | fetch-url1
  0.1013s | complete   | fetch_data                     | fetch-url2
  0.1015s | complete   | fetch_data                     | fetch-url3
  0.1520s | complete   | process_item                   | process-0
  0.1521s | complete   | main                           | Task-1

Task Execution Timeline:
===========================================================
fetch-url1           |[=========]                        | ✓
fetch-url2           |[=========]                        | ✓
fetch-url3           |[=========]                        | ✓
process-0            |          [====]                   | ✓
process-1            |          [====]                   | ✓
process-2            |          [====]                   | ✓

Task Hierarchy:
root
  └── Task-1
      ├── fetch-url1
      ├── fetch-url2
      ├── fetch-url3
      ├── process-0
      ├── process-1
      └── process-2
```

## Submission

1. Complete all TODO sections
2. Trace a real async application (aiohttp, etc.)
3. Identify any task starvation or bottlenecks
4. Bonus: Add WebSocket-based real-time visualization

---

[Next: Lab 5 - Garbage Collector →](lab-05-garbage-collector.md)

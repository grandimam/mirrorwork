# Lab 3: GIL Visualizer

## Objective

Build a tool to visualize GIL acquisition patterns and thread contention in multi-threaded Python programs.

## Prerequisites

- Understanding of the GIL (Part 6)
- Threading basics
- Basic knowledge of tracing

## Lab Setup

```python
# lab03_gil_visualizer.py
import threading
import time
import sys
import ctypes
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from queue import Queue
import json
```

## Exercise 1: Thread Activity Logger

Create a logger to track thread activity:

```python
@dataclass
class ThreadEvent:
    """Represents a thread activity event."""
    timestamp: float
    thread_id: int
    thread_name: str
    event_type: str  # 'start', 'end', 'acquire', 'release', 'switch'
    duration: float = 0.0
    metadata: dict = field(default_factory=dict)

class ThreadActivityLogger:
    """Log thread activity events."""

    def __init__(self):
        self.events: List[ThreadEvent] = []
        self.lock = threading.Lock()
        self.start_time = time.perf_counter()

    def log(self, event_type: str, **metadata):
        """Log a thread event."""
        thread = threading.current_thread()
        event = ThreadEvent(
            timestamp=time.perf_counter() - self.start_time,
            thread_id=thread.ident,
            thread_name=thread.name,
            event_type=event_type,
            metadata=metadata
        )

        with self.lock:
            self.events.append(event)

    def get_events_by_thread(self) -> Dict[int, List[ThreadEvent]]:
        """Group events by thread."""
        by_thread = defaultdict(list)
        for event in self.events:
            by_thread[event.thread_id].append(event)
        return dict(by_thread)

    def get_timeline(self) -> List[ThreadEvent]:
        """Get events sorted by timestamp."""
        return sorted(self.events, key=lambda e: e.timestamp)

# Global logger
logger = ThreadActivityLogger()
```

## Exercise 2: GIL State Tracker

Track GIL acquisition using sys.settrace:

```python
class GILStateTracker:
    """
    Track GIL state transitions.

    Note: Python doesn't expose GIL state directly, so we infer it
    from trace events and thread switching patterns.
    """

    def __init__(self):
        self.thread_states: Dict[int, str] = {}
        self.acquisition_times: Dict[int, float] = {}
        self.hold_times: List[Tuple[int, float]] = []
        self.switches: List[Tuple[float, int, int]] = []
        self.logger = ThreadActivityLogger()
        self.last_thread = None

    def trace_calls(self, frame, event, arg):
        """
        TODO: Implement trace function to track thread activity.

        Track: 'call', 'return', 'line' events
        Detect thread switches by comparing current thread to last active
        """
        current_thread = threading.current_thread().ident
        current_time = time.perf_counter()

        # Detect thread switch
        if self.last_thread is not None and self.last_thread != current_thread:
            self.switches.append((current_time, self.last_thread, current_thread))
            self.logger.log('switch',
                          from_thread=self.last_thread,
                          to_thread=current_thread)

            # Record hold time for previous thread
            if self.last_thread in self.acquisition_times:
                hold_time = current_time - self.acquisition_times[self.last_thread]
                self.hold_times.append((self.last_thread, hold_time))

            # Mark new acquisition
            self.acquisition_times[current_thread] = current_time

        self.last_thread = current_thread
        self.thread_states[current_thread] = event

        return self.trace_calls

    def start_tracking(self):
        """Enable GIL tracking."""
        sys.settrace(self.trace_calls)
        threading.settrace(self.trace_calls)
        print("GIL tracking started")

    def stop_tracking(self):
        """Disable GIL tracking."""
        sys.settrace(None)
        threading.settrace(None)
        print("GIL tracking stopped")

    def report(self):
        """Generate GIL usage report."""
        print("\nGIL Usage Report:")
        print("=" * 60)

        print(f"\nTotal thread switches: {len(self.switches)}")

        if self.hold_times:
            avg_hold = sum(t for _, t in self.hold_times) / len(self.hold_times)
            max_hold = max(t for _, t in self.hold_times)
            print(f"Average GIL hold time: {avg_hold*1000:.3f}ms")
            print(f"Maximum GIL hold time: {max_hold*1000:.3f}ms")

        # Per-thread breakdown
        thread_totals = defaultdict(float)
        for thread_id, hold_time in self.hold_times:
            thread_totals[thread_id] += hold_time

        print("\nPer-thread GIL time:")
        for thread_id, total in sorted(thread_totals.items(),
                                        key=lambda x: x[1], reverse=True):
            print(f"  Thread {thread_id}: {total*1000:.3f}ms")

# Test
tracker = GILStateTracker()
```

## Exercise 3: Contention Analyzer

Analyze GIL contention patterns:

```python
class ContentionAnalyzer:
    """Analyze GIL contention between threads."""

    def __init__(self):
        self.thread_work = defaultdict(list)
        self.contention_events = []
        self.lock = threading.Lock()

    def record_work(self, thread_id: int, start: float, end: float,
                   work_type: str = 'compute'):
        """Record a period of work by a thread."""
        with self.lock:
            self.thread_work[thread_id].append({
                'start': start,
                'end': end,
                'duration': end - start,
                'type': work_type
            })

    def analyze_contention(self) -> Dict:
        """
        TODO: Analyze contention by finding overlapping work periods.

        Contention occurs when multiple threads want the GIL simultaneously.
        """
        results = {
            'total_contention_time': 0,
            'contention_periods': [],
            'thread_efficiency': {}
        }

        # Get all work periods
        all_periods = []
        for thread_id, periods in self.thread_work.items():
            for period in periods:
                all_periods.append({
                    'thread_id': thread_id,
                    **period
                })

        # Sort by start time
        all_periods.sort(key=lambda x: x['start'])

        # Find overlapping periods (contention)
        for i, period1 in enumerate(all_periods):
            for period2 in all_periods[i+1:]:
                if period2['start'] >= period1['end']:
                    break

                # Overlap found
                overlap_start = period2['start']
                overlap_end = min(period1['end'], period2['end'])
                overlap_duration = overlap_end - overlap_start

                results['total_contention_time'] += overlap_duration
                results['contention_periods'].append({
                    'threads': [period1['thread_id'], period2['thread_id']],
                    'start': overlap_start,
                    'end': overlap_end,
                    'duration': overlap_duration
                })

        # Calculate efficiency (actual work / total time)
        for thread_id, periods in self.thread_work.items():
            total_work = sum(p['duration'] for p in periods)
            if periods:
                span = periods[-1]['end'] - periods[0]['start']
                efficiency = total_work / span if span > 0 else 0
                results['thread_efficiency'][thread_id] = efficiency

        return results

    def visualize_contention(self, width: int = 60):
        """Create ASCII visualization of contention."""
        if not self.thread_work:
            print("No work recorded")
            return

        # Find time bounds
        all_times = []
        for periods in self.thread_work.values():
            for p in periods:
                all_times.extend([p['start'], p['end']])

        min_time = min(all_times)
        max_time = max(all_times)
        time_range = max_time - min_time

        if time_range == 0:
            return

        print("\nThread Activity Timeline:")
        print("=" * (width + 20))

        for thread_id in sorted(self.thread_work.keys()):
            periods = self.thread_work[thread_id]

            # Create timeline
            timeline = [' '] * width

            for period in periods:
                start_pos = int((period['start'] - min_time) / time_range * (width - 1))
                end_pos = int((period['end'] - min_time) / time_range * (width - 1))

                for i in range(start_pos, min(end_pos + 1, width)):
                    timeline[i] = '#'

            print(f"Thread {thread_id:5d}: |{''.join(timeline)}|")

        print(f"{'Time':>13}: |{min_time:.3f}{' ' * (width - 12)}{max_time:.3f}|")

# Test
analyzer = ContentionAnalyzer()
```

## Exercise 4: Real-Time Visualizer

Create a real-time visualization of GIL activity:

```python
class RealTimeVisualizer:
    """Real-time visualization of thread activity."""

    def __init__(self, num_threads: int, update_interval: float = 0.1):
        self.num_threads = num_threads
        self.update_interval = update_interval
        self.thread_states: Dict[int, str] = {}
        self.running = False
        self.state_queue = Queue()

    def update_state(self, thread_id: int, state: str):
        """Update thread state (call from worker threads)."""
        self.state_queue.put((thread_id, state, time.perf_counter()))

    def _render(self):
        """
        TODO: Render current state to console.

        Show each thread's state using ASCII art.
        """
        # Clear previous output
        print('\033[H\033[J', end='')  # Clear screen

        print("Real-Time Thread Monitor")
        print("=" * 50)
        print(f"Time: {time.strftime('%H:%M:%S')}")
        print()

        states = {
            'running': ('█', '\033[92m'),   # Green
            'waiting': ('░', '\033[93m'),   # Yellow
            'blocked': ('▒', '\033[91m'),   # Red
            'idle': (' ', '\033[90m'),      # Gray
        }

        for thread_id in sorted(self.thread_states.keys()):
            state = self.thread_states.get(thread_id, 'idle')
            char, color = states.get(state, (' ', '\033[0m'))

            # Create activity bar
            bar = char * 20
            print(f"{color}Thread {thread_id:3d}: [{bar}] {state:10s}\033[0m")

        print()
        print("Legend: █=running ░=waiting ▒=blocked")

    def run_display(self, duration: float):
        """Run the display for specified duration."""
        self.running = True
        end_time = time.perf_counter() + duration

        while time.perf_counter() < end_time:
            # Process state updates
            while not self.state_queue.empty():
                thread_id, state, _ = self.state_queue.get_nowait()
                self.thread_states[thread_id] = state

            self._render()
            time.sleep(self.update_interval)

        self.running = False
```

## Exercise 5: Complete GIL Visualizer

Combine all components into a complete tool:

```python
class GILVisualizer:
    """Complete GIL visualization tool."""

    def __init__(self):
        self.logger = ThreadActivityLogger()
        self.tracker = GILStateTracker()
        self.analyzer = ContentionAnalyzer()
        self.threads_data: Dict[int, dict] = {}
        self.lock = threading.Lock()

    def monitored_thread(self, func, *args, **kwargs):
        """Wrapper to monitor a thread's execution."""
        thread = threading.current_thread()
        thread_id = thread.ident

        with self.lock:
            self.threads_data[thread_id] = {
                'name': thread.name,
                'start_time': time.perf_counter(),
                'work_periods': []
            }

        self.logger.log('start', function=func.__name__)

        try:
            start = time.perf_counter()
            result = func(*args, **kwargs)
            end = time.perf_counter()

            self.analyzer.record_work(thread_id, start, end)

            return result
        finally:
            with self.lock:
                self.threads_data[thread_id]['end_time'] = time.perf_counter()
            self.logger.log('end', function=func.__name__)

    def run_test(self, workloads: List[callable], num_iterations: int = 5):
        """
        Run workloads and visualize GIL contention.

        TODO: Implement test runner that:
        1. Starts tracking
        2. Runs workloads in threads
        3. Collects data
        4. Generates visualization
        """
        self.tracker.start_tracking()

        threads = []

        for i, workload in enumerate(workloads):
            for j in range(num_iterations):
                t = threading.Thread(
                    target=self.monitored_thread,
                    args=(workload,),
                    name=f"Worker-{i}-{j}"
                )
                threads.append(t)

        # Start all threads
        start_time = time.perf_counter()
        for t in threads:
            t.start()

        # Wait for completion
        for t in threads:
            t.join()

        total_time = time.perf_counter() - start_time

        self.tracker.stop_tracking()

        # Generate report
        self._generate_report(total_time)

    def _generate_report(self, total_time: float):
        """Generate comprehensive report."""
        print("\n" + "=" * 70)
        print("GIL Visualization Report")
        print("=" * 70)

        # Timeline
        self.analyzer.visualize_contention()

        # Contention analysis
        contention = self.analyzer.analyze_contention()

        print(f"\nTotal execution time: {total_time*1000:.2f}ms")
        print(f"Total contention time: {contention['total_contention_time']*1000:.2f}ms")

        if contention['contention_periods']:
            print(f"Contention periods: {len(contention['contention_periods'])}")

        print("\nThread efficiency:")
        for thread_id, efficiency in contention['thread_efficiency'].items():
            print(f"  Thread {thread_id}: {efficiency:.1%}")

        # GIL stats
        self.tracker.report()

        # Event log
        print("\nEvent Log (first 20):")
        for event in self.logger.get_timeline()[:20]:
            print(f"  {event.timestamp:.4f}s - {event.thread_name}: {event.event_type}")

# Demo workloads
def cpu_bound_work():
    """CPU-bound workload."""
    total = 0
    for i in range(100000):
        total += i ** 2
    return total

def io_bound_work():
    """Simulated I/O-bound workload."""
    time.sleep(0.01)
    return "done"

def mixed_work():
    """Mixed workload."""
    total = 0
    for i in range(10000):
        total += i ** 2
    time.sleep(0.005)
    return total

# Test
visualizer = GILVisualizer()
visualizer.run_test([cpu_bound_work, cpu_bound_work], num_iterations=3)
```

## Challenge: Interactive Dashboard

Create an interactive dashboard showing real-time GIL metrics:

```python
def run_dashboard():
    """Run interactive GIL monitoring dashboard."""

    visualizer = GILVisualizer()

    # Start background workers
    def background_worker(work_type: str):
        while True:
            if work_type == 'cpu':
                cpu_bound_work()
            else:
                io_bound_work()
            time.sleep(0.1)

    workers = [
        threading.Thread(target=background_worker, args=('cpu',), daemon=True),
        threading.Thread(target=background_worker, args=('io',), daemon=True),
        threading.Thread(target=background_worker, args=('cpu',), daemon=True),
    ]

    for w in workers:
        w.start()

    # Run real-time display
    rt_viz = RealTimeVisualizer(len(workers))

    print("Starting real-time dashboard (press Ctrl+C to stop)...")
    try:
        while True:
            # Update states based on current activity
            for i, w in enumerate(workers):
                state = 'running' if w.is_alive() else 'idle'
                rt_viz.update_state(w.ident, state)

            rt_viz._render()
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nDashboard stopped")

if __name__ == "__main__":
    # Run basic test
    visualizer = GILVisualizer()
    visualizer.run_test(
        [cpu_bound_work, cpu_bound_work, io_bound_work],
        num_iterations=2
    )
```

## Expected Output

```
======================================================================
GIL Visualization Report
======================================================================

Thread Activity Timeline:
============================================================
Thread  1234: |#####    #####    ####               |
Thread  1235: |     ####     ####    ###            |
Thread  1236: |                         #  #  #  #  |
Time        : |0.000                          0.150|

Total execution time: 150.23ms
Total contention time: 45.67ms
Contention periods: 12

Thread efficiency:
  Thread 1234: 78.5%
  Thread 1235: 72.3%
  Thread 1236: 95.2%

GIL Usage Report:
============================================================
Total thread switches: 24
Average GIL hold time: 5.234ms
Maximum GIL hold time: 15.678ms
```

## Submission

1. Complete all TODO sections
2. Test with different workload mixes
3. Document observations about GIL behavior
4. Bonus: Export data to JSON for external visualization

---

[Next: Lab 4 - Async Tracer →](lab-04-async-tracer.md)

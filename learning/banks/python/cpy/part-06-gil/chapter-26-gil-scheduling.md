# Chapter 26: GIL Scheduling

## 26.1 Old GIL (Tick-Based, Pre-3.2)

Before Python 3.2, the GIL used a tick-based mechanism:

```
┌─────────────────────────────────────────────────────────────────┐
│                  Old GIL (Pre-Python 3.2)                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Every 100 bytecode instructions ("ticks"):                      │
│                                                                  │
│  for (tick = 0; tick < 100; tick++) {                           │
│      execute_one_bytecode();                                    │
│  }                                                               │
│  // After 100 ticks:                                            │
│  release_gil();                                                  │
│  acquire_gil();  // May be acquired by different thread         │
│                                                                  │
│  Problems:                                                       │
│  - 100 LOAD_CONST takes very different time than 100 CALL      │
│  - Unfair: thread can re-acquire immediately                    │
│  - Poor performance on multi-core systems                       │
│  - "Convoy effect" - threads pile up waiting                    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Tick Interval Setting (Old)

```python
# Python 2.x / early 3.x
import sys

# Get the check interval (in ticks)
print(sys.getcheckinterval())  # Default: 100

# Set the check interval
sys.setcheckinterval(1000)  # Less frequent switching
```

## 26.2 New GIL (Time-Based, 3.2+)

Python 3.2 introduced a time-based GIL (by Antoine Pitrou):

```
┌─────────────────────────────────────────────────────────────────┐
│                  New GIL (Python 3.2+)                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Thread A holds GIL:                                             │
│  ┌────────────────────────────────────────────────────┐         │
│  │ Execute bytecode until:                             │         │
│  │   1. I/O operation (voluntary release)              │         │
│  │   2. Another thread requests GIL (after timeout)    │         │
│  └────────────────────────────────────────────────────┘         │
│                                                                  │
│  Thread B waiting for GIL:                                       │
│  ┌────────────────────────────────────────────────────┐         │
│  │ Wait with timeout (default 5ms)                     │         │
│  │ If timeout expires:                                 │         │
│  │   Set "GIL drop request" flag                       │         │
│  │   Wait for Thread A to notice and release           │         │
│  └────────────────────────────────────────────────────┘         │
│                                                                  │
│  Benefits:                                                       │
│  - Fair: waiting thread signals need after timeout              │
│  - Predictable: time-based, not instruction-based               │
│  - Better multi-core behavior                                    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 26.3 `sys.setswitchinterval()`

### Getting and Setting the Interval

```python
import sys

# Get current switch interval (in seconds)
interval = sys.getswitchinterval()
print(f"Current interval: {interval * 1000:.1f} ms")  # 5.0 ms default

# Set new interval
sys.setswitchinterval(0.001)  # 1 ms - more responsive, more overhead
sys.setswitchinterval(0.010)  # 10 ms - less overhead, less responsive
sys.setswitchinterval(0.005)  # 5 ms - default (good balance)
```

### Interval Effects

```python
import sys
import threading
import time

def cpu_work(duration):
    """Do CPU-intensive work."""
    end = time.time() + duration
    while time.time() < end:
        sum(range(1000))

def benchmark_interval(interval):
    """Measure context switch overhead."""
    sys.setswitchinterval(interval)

    threads = [threading.Thread(target=cpu_work, args=(1,))
               for _ in range(4)]

    start = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = time.time() - start

    return elapsed

# Compare different intervals
for interval in [0.001, 0.005, 0.010, 0.050]:
    elapsed = benchmark_interval(interval)
    print(f"Interval {interval*1000:5.1f}ms: {elapsed:.2f}s")
```

## 26.4 Default Switch Interval (5ms)

### Why 5ms?

```
┌─────────────────────────────────────────────────────────────────┐
│              Switch Interval Trade-offs                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Shorter interval (e.g., 1ms):                                  │
│  + More responsive to other threads                              │
│  + Better latency for I/O-bound threads                         │
│  - More context switches → overhead                             │
│  - More time spent acquiring/releasing GIL                      │
│                                                                  │
│  Longer interval (e.g., 50ms):                                  │
│  + Less context switch overhead                                  │
│  + Better throughput for CPU-bound work                         │
│  - Less responsive                                               │
│  - Other threads wait longer                                     │
│                                                                  │
│  5ms is a balance:                                               │
│  - 200 switches per second maximum                               │
│  - Good for typical mixed workloads                             │
│  - Can be tuned for specific use cases                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 26.5 GIL Fairness Mechanism

### The Drop Request

```c
// When a waiting thread's timeout expires
if (timeout_expired) {
    // Set the drop request flag
    _Py_SET_GIL_DROP_REQUEST(interp);
}

// In the eval loop, thread holding GIL checks:
if (eval_breaker_bit_is_set(interp, _PY_GIL_DROP_REQUEST_BIT)) {
    // Must release GIL
    drop_gil(tstate);
    // Try to reacquire (might go to different thread)
    take_gil(tstate);
}
```

### Fairness in Action

```
┌─────────────────────────────────────────────────────────────────┐
│                  GIL Fairness Timeline                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Time: 0ms    5ms    10ms   15ms   20ms   25ms   30ms          │
│                                                                  │
│  Thread A: [=====][wait][=====][wait][=====][wait]              │
│                    ↑          ↑          ↑                      │
│  Thread B: [wait][=====][wait][=====][wait][=====]              │
│                                                                  │
│  At 5ms: Thread B's timeout expires                              │
│          Thread B sets drop request                              │
│          Thread A sees request, releases GIL                    │
│          Thread B acquires GIL                                   │
│                                                                  │
│  New GIL ensures threads get fair turns                         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 26.6 Priority and Starvation

### Starvation Scenario

```python
import threading
import time

results = []

def low_priority_work():
    """Simulated low-priority thread."""
    for i in range(10):
        start = time.time()
        # Some CPU work
        sum(range(100000))
        results.append(('low', time.time() - start))

def high_priority_work():
    """Simulated high-priority thread (more aggressive)."""
    for i in range(100):
        start = time.time()
        sum(range(10000))
        results.append(('high', time.time() - start))

# Run threads
threads = [
    threading.Thread(target=low_priority_work),
    threading.Thread(target=high_priority_work),
]

for t in threads:
    t.start()
for t in threads:
    t.join()

# Analyze fairness
low_count = sum(1 for r in results if r[0] == 'low')
high_count = sum(1 for r in results if r[0] == 'high')
print(f"Low priority completions: {low_count}")
print(f"High priority completions: {high_count}")
```

### Priority Inversion

The GIL doesn't respect OS thread priorities:

```python
import threading
import os

def work():
    while True:
        sum(range(10000))

# Even if we set OS priority, GIL doesn't care
t1 = threading.Thread(target=work)
t2 = threading.Thread(target=work)

# These priority settings are ignored by GIL scheduling
# os.setpriority(os.PRIO_PROCESS, t1.native_id, -10)  # Higher
# os.setpriority(os.PRIO_PROCESS, t2.native_id, 10)   # Lower

# GIL uses its own fairness mechanism, not OS priorities
```

## 26.7 GIL Drop Requests

### How Drop Requests Work

```c
// Thread B is waiting for GIL
static void take_gil(PyThreadState *tstate) {
    _gil_runtime_state *gil = &_PyRuntime.gil;

    MUTEX_LOCK(gil->mutex);

    while (gil->locked) {
        // Wait with timeout
        int result = COND_TIMED_WAIT(
            gil->cond,
            gil->mutex,
            gil->switch_interval  // 5ms default
        );

        if (result == ETIMEDOUT && gil->locked) {
            // Timeout! Request GIL drop
            _Py_SET_GIL_DROP_REQUEST(tstate->interp);
        }
    }

    // Got the GIL
    gil->locked = 1;
    MUTEX_UNLOCK(gil->mutex);
}
```

### Thread A Responding to Drop Request

```c
// In the evaluation loop (ceval.c)
main_loop:
    // Periodic check
    if (_Py_atomic_load_relaxed(&interp->ceval.eval_breaker)) {
        // Check for GIL drop request
        if (eval_breaker_bit_is_set(interp, _PY_GIL_DROP_REQUEST_BIT)) {
            // Clear the request
            _Py_UNSET_GIL_DROP_REQUEST(interp);

            // Release and reacquire (gives other thread a chance)
            drop_gil(tstate);
            take_gil(tstate);
        }
    }

    // Continue executing bytecode...
```

## Observing GIL Behavior

```python
import threading
import time
import sys

class GILMonitor:
    """Monitor GIL acquisition patterns."""

    def __init__(self):
        self.acquisitions = []
        self.lock = threading.Lock()

    def record(self, thread_name):
        with self.lock:
            self.acquisitions.append((time.time(), thread_name))

    def report(self):
        for t, name in self.acquisitions[-20:]:
            print(f"{t:.4f}: {name}")

monitor = GILMonitor()

def worker(name):
    for _ in range(100):
        monitor.record(name)
        sum(range(10000))  # Some work

threads = [
    threading.Thread(target=worker, args=(f"Thread-{i}",))
    for i in range(3)
]

for t in threads:
    t.start()
for t in threads:
    t.join()

monitor.report()
```

## Summary

- **Old GIL** (pre-3.2): tick-based, unfair, poor multi-core
- **New GIL** (3.2+): time-based, fair, 5ms default interval
- **`sys.setswitchinterval()`** adjusts the switch interval
- **Drop requests** ensure waiting threads get a turn
- **No priority support**: GIL ignores OS thread priorities
- Thread with GIL checks **eval_breaker** periodically

## Practice Exercises

1. Benchmark different switch intervals with CPU-bound threads
2. Observe GIL contention using timing measurements
3. Compare responsiveness with 1ms vs 50ms intervals
4. Create a visualization of GIL acquisition patterns

---

[← Previous: GIL Implementation](chapter-25-gil-implementation.md) | [Next: GIL and Threading →](chapter-27-gil-threading.md)

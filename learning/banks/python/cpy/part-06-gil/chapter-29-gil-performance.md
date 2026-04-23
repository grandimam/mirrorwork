# Chapter 29: GIL Performance Impact

## 29.1 Single-Threaded Performance

The GIL has minimal impact on single-threaded code:

```python
import time

def benchmark(func, iterations=1000000):
    start = time.perf_counter()
    for _ in range(iterations):
        func()
    return time.perf_counter() - start

# Single-threaded performance is excellent
def simple_operation():
    x = 1 + 2
    y = x * 3
    return y

elapsed = benchmark(simple_operation)
print(f"Single-threaded: {elapsed:.3f}s for 1M iterations")

# GIL overhead per iteration is negligible
# because GIL is never contended
```

### Why Single-Threaded is Fast

```
┌─────────────────────────────────────────────────────────────────┐
│              Single-Threaded GIL Behavior                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Thread 1: [════════════════════════════════════════════════]   │
│            No contention, no waiting, no switching              │
│                                                                  │
│  GIL: Always held by Thread 1                                    │
│       No acquisition/release overhead                            │
│                                                                  │
│  Result: GIL has ~0 cost for single-threaded code               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 29.2 Multi-Threaded CPU-Bound Scaling

CPU-bound multi-threading doesn't scale (and may be slower!):

```python
import threading
import time
import multiprocessing

def cpu_work(n):
    """CPU-intensive work."""
    total = 0
    for i in range(n):
        total += i * i
    return total

WORK_SIZE = 10_000_000

def benchmark_sequential():
    """Run sequentially."""
    start = time.perf_counter()
    cpu_work(WORK_SIZE)
    cpu_work(WORK_SIZE)
    cpu_work(WORK_SIZE)
    cpu_work(WORK_SIZE)
    return time.perf_counter() - start

def benchmark_threaded(num_threads):
    """Run with threads."""
    start = time.perf_counter()
    threads = []
    for _ in range(num_threads):
        t = threading.Thread(target=cpu_work, args=(WORK_SIZE,))
        threads.append(t)
        t.start()
    for t in threads:
        t.join()
    return time.perf_counter() - start

def benchmark_multiprocessing(num_processes):
    """Run with processes."""
    start = time.perf_counter()
    with multiprocessing.Pool(num_processes) as pool:
        pool.map(cpu_work, [WORK_SIZE] * num_processes)
    return time.perf_counter() - start

# Benchmark
print(f"CPU cores: {multiprocessing.cpu_count()}")
print(f"\nSequential (4 tasks): {benchmark_sequential():.2f}s")
print(f"4 Threads:            {benchmark_threaded(4):.2f}s")
print(f"4 Processes:          {benchmark_multiprocessing(4):.2f}s")
```

### Typical Results

```
CPU cores: 4

Sequential (4 tasks): 4.00s
4 Threads:            4.50s  ← Slower! GIL contention overhead
4 Processes:          1.10s  ← ~4x faster (true parallelism)
```

## 29.3 Multi-Threaded I/O-Bound Scaling

I/O-bound code scales well with threads:

```python
import threading
import time
import urllib.request

URLS = [
    'https://www.python.org/downloads/',
    'https://docs.python.org/',
    'https://pypi.org/project/pip/',
    'https://github.com/python/cpython',
] * 10  # 40 URLs

def fetch_url(url):
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return len(response.read())
    except:
        return 0

def sequential():
    start = time.perf_counter()
    for url in URLS:
        fetch_url(url)
    return time.perf_counter() - start

def threaded(num_threads):
    start = time.perf_counter()

    def worker(urls):
        for url in urls:
            fetch_url(url)

    # Divide work among threads
    chunk_size = len(URLS) // num_threads
    threads = []
    for i in range(num_threads):
        chunk = URLS[i*chunk_size:(i+1)*chunk_size]
        t = threading.Thread(target=worker, args=(chunk,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    return time.perf_counter() - start

print(f"Sequential:  {sequential():.2f}s")
print(f"4 Threads:   {threaded(4):.2f}s")
print(f"10 Threads:  {threaded(10):.2f}s")
print(f"40 Threads:  {threaded(40):.2f}s")
```

### Typical Results

```
Sequential:  20.00s
4 Threads:    5.00s  ← 4x speedup
10 Threads:   2.00s  ← 10x speedup
40 Threads:   0.60s  ← Near max parallelism
```

## 29.4 GIL Contention Measurement

### Measuring Contention

```python
import threading
import time
import sys

def contention_test(num_threads, work_per_thread):
    """Measure GIL contention effect."""
    results = []
    lock = threading.Lock()

    def worker():
        start = time.perf_counter()
        total = 0
        for i in range(work_per_thread):
            total += i
        elapsed = time.perf_counter() - start
        with lock:
            results.append(elapsed)

    threads = [threading.Thread(target=worker) for _ in range(num_threads)]
    total_start = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    total_elapsed = time.perf_counter() - total_start

    avg_work_time = sum(results) / len(results)
    return total_elapsed, avg_work_time

print("Threads | Total Time | Avg Work Time | Efficiency")
print("-" * 55)

for num_threads in [1, 2, 4, 8]:
    total, avg_work = contention_test(num_threads, 5_000_000)
    efficiency = avg_work / total * 100
    print(f"{num_threads:7} | {total:10.2f}s | {avg_work:13.2f}s | {efficiency:8.1f}%")
```

### Understanding the Results

```
┌─────────────────────────────────────────────────────────────────┐
│              GIL Contention Effects                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Threads │ Efficiency │ Explanation                             │
│  ────────┼────────────┼──────────────────────────────          │
│     1    │   ~100%    │ No contention                           │
│     2    │   ~50%     │ Each thread gets ~half the time        │
│     4    │   ~25%     │ Each thread gets ~quarter              │
│     8    │   ~12%     │ Plus overhead from switching           │
│                                                                  │
│  CPU-bound work doesn't parallelize with threads!               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 29.5 Benchmarking Methodology

### Proper Benchmarking

```python
import time
import statistics

def benchmark(func, runs=10, warmup=3):
    """Properly benchmark a function."""
    # Warmup runs (JIT, caches, etc.)
    for _ in range(warmup):
        func()

    # Timed runs
    times = []
    for _ in range(runs):
        start = time.perf_counter()
        func()
        times.append(time.perf_counter() - start)

    return {
        'min': min(times),
        'max': max(times),
        'mean': statistics.mean(times),
        'stdev': statistics.stdev(times) if len(times) > 1 else 0,
        'median': statistics.median(times),
    }

def cpu_work():
    sum(range(1000000))

results = benchmark(cpu_work)
print(f"Mean: {results['mean']:.4f}s ± {results['stdev']:.4f}s")
print(f"Min:  {results['min']:.4f}s")
print(f"Max:  {results['max']:.4f}s")
```

### Avoiding Common Mistakes

```python
# WRONG: Including setup time
def bad_benchmark():
    data = list(range(1000000))  # Setup!
    start = time.time()
    sum(data)
    return time.time() - start

# RIGHT: Separate setup
def good_benchmark():
    data = list(range(1000000))  # Setup outside timing
    start = time.time()
    sum(data)
    return time.time() - start

# WRONG: Too few iterations
result = sum(range(100))  # Too fast to measure accurately

# RIGHT: Enough iterations
result = sum(range(10000000))  # Meaningful duration

# WRONG: time.time() for short durations
# RIGHT: time.perf_counter() for precise timing
```

## 29.6 Amdahl's Law and the GIL

### Amdahl's Law

```
Speedup = 1 / (S + P/N)

Where:
- S = Sequential fraction (cannot be parallelized)
- P = Parallel fraction (can be parallelized)
- N = Number of processors
- S + P = 1

With GIL for CPU-bound code:
- Python bytecode execution is effectively S = 1 (all sequential)
- Only I/O and C extensions (with GIL released) contribute to P
```

### Visualization

```
┌─────────────────────────────────────────────────────────────────┐
│                 Amdahl's Law with GIL                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Pure CPU-bound Python:                                          │
│  [████████████████████████████] 100% sequential (GIL-bound)     │
│  Max speedup with N cores: 1x (no improvement)                   │
│                                                                  │
│  I/O-bound Python (50% I/O):                                    │
│  [██████████████][░░░░░░░░░░░░░░] 50% seq, 50% parallel         │
│  Max speedup with 4 cores: 1/(0.5 + 0.5/4) = 1.6x               │
│  Max speedup with ∞ cores: 1/0.5 = 2x                           │
│                                                                  │
│  I/O-bound Python (90% I/O):                                    │
│  [████][░░░░░░░░░░░░░░░░░░░░░░░░░░] 10% seq, 90% parallel       │
│  Max speedup with 4 cores: 1/(0.1 + 0.9/4) = 3.1x               │
│  Max speedup with ∞ cores: 1/0.1 = 10x                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Practical Implications

```python
import multiprocessing

# For CPU-bound: Use multiprocessing
def cpu_bound_work(data):
    return sum(x**2 for x in data)

if __name__ == '__main__':
    data_chunks = [range(i*1000000, (i+1)*1000000) for i in range(4)]

    # Parallel with multiprocessing
    with multiprocessing.Pool(4) as pool:
        results = pool.map(cpu_bound_work, data_chunks)

# For I/O-bound: Threading is fine
# For mixed: Consider asyncio or concurrent.futures
```

## Summary

- **Single-threaded**: GIL has ~0 performance cost
- **CPU-bound multi-threaded**: Doesn't scale (may be slower)
- **I/O-bound multi-threaded**: Scales well
- **Contention**: Efficiency drops with more threads for CPU work
- **Amdahl's Law**: Limits speedup based on parallel fraction
- **Solution**: Use `multiprocessing` for CPU-bound parallelism

## Practice Exercises

1. Benchmark your own code with different thread counts
2. Calculate the parallel fraction of your I/O-bound code
3. Compare threading vs multiprocessing for your use case
4. Use `py-spy` or similar profiler to visualize GIL contention

---

[← Previous: GIL Atomicity](chapter-28-gil-atomicity.md) | [Next: GIL History and Removal Attempts →](chapter-30-gil-history.md)

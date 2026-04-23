# Chapter 58: Profiling

## 58.1 cProfile

```python
import cProfile
import pstats

# Profile a function
cProfile.run('my_function()')

# Profile with output file
cProfile.run('my_function()', 'profile_output.prof')

# Analyze results
stats = pstats.Stats('profile_output.prof')
stats.strip_dirs()
stats.sort_stats('cumulative')
stats.print_stats(10)  # Top 10 functions
```

## 58.2 Line Profiler

```python
# pip install line_profiler
from line_profiler import LineProfiler

def slow_function():
    total = 0
    for i in range(1000):
        total += i ** 2
    return total

profiler = LineProfiler()
profiler.add_function(slow_function)
profiler.run('slow_function()')
profiler.print_stats()
```

## 58.3 Memory Profiling

```python
import tracemalloc

tracemalloc.start()

# Your code here
data = [i ** 2 for i in range(100000)]

snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics('lineno')

for stat in top_stats[:5]:
    print(stat)
```

## Summary

- cProfile shows function-level timing
- line_profiler shows line-by-line timing
- tracemalloc tracks memory allocations

---

[Next: Code Coverage →](chapter-59-coverage.md)

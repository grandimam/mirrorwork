# Chapter 31: Multiprocessing

## 31.1 `multiprocessing` Module Overview

The `multiprocessing` module bypasses the GIL by using separate processes:

```
┌─────────────────────────────────────────────────────────────────┐
│              Threading vs Multiprocessing                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Threading (shared memory, one GIL):                            │
│  ┌─────────────────────────────────────────┐                    │
│  │  Process                                 │                    │
│  │  ┌─────┐ ┌─────┐ ┌─────┐               │                    │
│  │  │ T1  │ │ T2  │ │ T3  │               │                    │
│  │  └──┬──┘ └──┬──┘ └──┬──┘               │                    │
│  │     └───────┼───────┘                   │                    │
│  │            GIL (bottleneck)             │                    │
│  └─────────────────────────────────────────┘                    │
│                                                                  │
│  Multiprocessing (separate memory, separate GILs):              │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐               │
│  │  Process 1  │ │  Process 2  │ │  Process 3  │               │
│  │  ┌───────┐  │ │  ┌───────┐  │ │  ┌───────┐  │               │
│  │  │  GIL  │  │ │  │  GIL  │  │ │  │  GIL  │  │               │
│  │  └───────┘  │ │  └───────┘  │ │  └───────┘  │               │
│  │  (own mem)  │ │  (own mem)  │ │  (own mem)  │               │
│  └─────────────┘ └─────────────┘ └─────────────┘               │
│  True parallelism! Each process runs independently.             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Basic Usage

```python
import multiprocessing as mp

def worker(x):
    return x * x

if __name__ == '__main__':
    # Create processes
    with mp.Pool(4) as pool:
        results = pool.map(worker, range(10))
    print(results)  # [0, 1, 4, 9, 16, 25, 36, 49, 64, 81]
```

## 31.2 Process vs Thread

| Aspect | Thread | Process |
|--------|--------|---------|
| Memory | Shared | Separate |
| GIL | Shared (bottleneck) | Per-process (no bottleneck) |
| Creation | Fast | Slower |
| Communication | Direct (shared memory) | Explicit (IPC) |
| CPU parallelism | No (due to GIL) | Yes |
| Overhead | Low | Higher |

### When to Use Each

```python
# Use threading for:
# - I/O-bound tasks
# - Shared state is needed
# - Low overhead required

# Use multiprocessing for:
# - CPU-bound tasks
# - True parallelism needed
# - Isolation required
```

## 31.3 Start Methods

### 31.3.1 Fork

```python
import multiprocessing as mp

mp.set_start_method('fork')  # Default on Unix

def worker():
    print(f"Worker PID: {mp.current_process().pid}")

if __name__ == '__main__':
    p = mp.Process(target=worker)
    p.start()
    p.join()
```

**Fork characteristics:**
- Copies parent process (fast)
- Inherits file descriptors, memory
- Can cause issues with threads
- Not available on Windows

### 31.3.2 Spawn

```python
import multiprocessing as mp

mp.set_start_method('spawn')  # Default on Windows, macOS (3.8+)

def worker():
    print(f"Worker PID: {mp.current_process().pid}")

if __name__ == '__main__':
    p = mp.Process(target=worker)
    p.start()
    p.join()
```

**Spawn characteristics:**
- Starts fresh Python interpreter
- Slower startup
- Safer with threads
- Available everywhere

### 31.3.3 Forkserver

```python
import multiprocessing as mp

mp.set_start_method('forkserver')

# A server process is forked once
# New processes are forked from the server
# Combines benefits of fork and spawn
```

### Comparison

```
┌─────────────────────────────────────────────────────────────────┐
│                Start Method Comparison                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Method     │ Speed  │ Safety │ Inheritance │ Platform          │
│  ───────────┼────────┼────────┼─────────────┼─────────────      │
│  fork       │ Fast   │ Low*   │ Full        │ Unix only         │
│  spawn      │ Slow   │ High   │ Minimal     │ All               │
│  forkserver │ Medium │ High   │ Minimal     │ Unix only         │
│                                                                  │
│  * Fork can cause issues with threads and some libraries        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 31.4 `Pool` and Worker Processes

### Using Pool

```python
import multiprocessing as mp
import time

def cpu_work(n):
    """Simulate CPU-intensive work."""
    total = sum(i*i for i in range(n))
    return total

if __name__ == '__main__':
    data = [1000000] * 8

    # Sequential
    start = time.time()
    results_seq = [cpu_work(n) for n in data]
    print(f"Sequential: {time.time() - start:.2f}s")

    # Parallel with Pool
    start = time.time()
    with mp.Pool(4) as pool:
        results_par = pool.map(cpu_work, data)
    print(f"Parallel (4 workers): {time.time() - start:.2f}s")
```

### Pool Methods

```python
import multiprocessing as mp

def square(x):
    return x * x

if __name__ == '__main__':
    with mp.Pool(4) as pool:
        # map: Apply function to iterable
        results = pool.map(square, range(10))

        # map_async: Non-blocking map
        async_result = pool.map_async(square, range(10))
        results = async_result.get()

        # imap: Lazy iteration (memory efficient)
        for result in pool.imap(square, range(10)):
            print(result)

        # imap_unordered: Results as completed
        for result in pool.imap_unordered(square, range(10)):
            print(result)

        # starmap: For functions with multiple args
        results = pool.starmap(pow, [(2, 3), (3, 4), (4, 5)])

        # apply: Single function call
        result = pool.apply(square, (5,))

        # apply_async: Non-blocking apply
        async_result = pool.apply_async(square, (5,))
        result = async_result.get()
```

## 31.5 Inter-Process Communication

### 31.5.1 Queues

```python
import multiprocessing as mp

def producer(queue):
    for i in range(5):
        queue.put(i)
    queue.put(None)  # Sentinel

def consumer(queue):
    while True:
        item = queue.get()
        if item is None:
            break
        print(f"Got: {item}")

if __name__ == '__main__':
    queue = mp.Queue()

    p = mp.Process(target=producer, args=(queue,))
    c = mp.Process(target=consumer, args=(queue,))

    p.start()
    c.start()

    p.join()
    c.join()
```

### 31.5.2 Pipes

```python
import multiprocessing as mp

def sender(conn):
    conn.send("Hello from sender!")
    conn.close()

def receiver(conn):
    msg = conn.recv()
    print(f"Received: {msg}")
    conn.close()

if __name__ == '__main__':
    parent_conn, child_conn = mp.Pipe()

    p1 = mp.Process(target=sender, args=(parent_conn,))
    p2 = mp.Process(target=receiver, args=(child_conn,))

    p1.start()
    p2.start()

    p1.join()
    p2.join()
```

### 31.5.3 Shared Memory

```python
import multiprocessing as mp
import ctypes

def worker(shared_array, index, value):
    shared_array[index] = value

if __name__ == '__main__':
    # Shared array
    shared_array = mp.Array(ctypes.c_double, 10)

    processes = []
    for i in range(10):
        p = mp.Process(target=worker, args=(shared_array, i, i * 2.0))
        processes.append(p)
        p.start()

    for p in processes:
        p.join()

    print(list(shared_array))  # [0.0, 2.0, 4.0, ..., 18.0]
```

## 31.6 `multiprocessing.shared_memory` (Python 3.8+)

```python
from multiprocessing import shared_memory
import numpy as np

# Create shared memory
shm = shared_memory.SharedMemory(create=True, size=1000)

# Use with NumPy
arr = np.ndarray((10, 10), dtype=np.float64, buffer=shm.buf)
arr[:] = np.random.random((10, 10))

# In another process, attach to existing shared memory
# shm2 = shared_memory.SharedMemory(name=shm.name)
# arr2 = np.ndarray((10, 10), dtype=np.float64, buffer=shm2.buf)

# Cleanup
shm.close()
shm.unlink()  # Delete the shared memory
```

## 31.7 Manager Objects and Proxies

```python
import multiprocessing as mp

def worker(shared_dict, shared_list, lock, key, value):
    with lock:
        shared_dict[key] = value
        shared_list.append(value)

if __name__ == '__main__':
    with mp.Manager() as manager:
        shared_dict = manager.dict()
        shared_list = manager.list()
        lock = manager.Lock()

        processes = []
        for i in range(5):
            p = mp.Process(target=worker,
                          args=(shared_dict, shared_list, lock, f'key{i}', i))
            processes.append(p)
            p.start()

        for p in processes:
            p.join()

        print(dict(shared_dict))  # {'key0': 0, 'key1': 1, ...}
        print(list(shared_list))  # [0, 1, 2, 3, 4] (order may vary)
```

## 31.8 Pickle Serialization Overhead

```python
import multiprocessing as mp
import pickle
import sys

# Arguments and results are pickled
def process_data(data):
    return sum(data)

# Large data = large pickle overhead
data = list(range(1000000))
print(f"Data size: {sys.getsizeof(data) / 1024 / 1024:.2f} MB")
print(f"Pickle size: {len(pickle.dumps(data)) / 1024 / 1024:.2f} MB")

# For large data, consider:
# 1. Shared memory
# 2. Memory-mapped files
# 3. Chunking data
```

## 31.9 `concurrent.futures.ProcessPoolExecutor`

```python
from concurrent.futures import ProcessPoolExecutor
import time

def cpu_work(n):
    return sum(i*i for i in range(n))

if __name__ == '__main__':
    data = [1000000] * 8

    with ProcessPoolExecutor(max_workers=4) as executor:
        # submit: Single task
        future = executor.submit(cpu_work, 1000000)
        print(future.result())

        # map: Multiple tasks
        results = list(executor.map(cpu_work, data))
        print(results)

        # as_completed: Results as they finish
        from concurrent.futures import as_completed
        futures = [executor.submit(cpu_work, n) for n in data]
        for future in as_completed(futures):
            print(future.result())
```

## Summary

- **multiprocessing** bypasses GIL with separate processes
- **Start methods**: fork (fast), spawn (safe), forkserver (balanced)
- **Pool** provides easy parallel execution
- **IPC**: Queues, Pipes, shared memory
- **Manager** provides synchronized shared objects
- **Pickle overhead** can be significant for large data
- **ProcessPoolExecutor** offers a simpler API

## Practice Exercises

1. Compare threading vs multiprocessing for CPU-bound work
2. Implement a parallel file processor using Pool
3. Use shared memory to share data between processes
4. Benchmark pickle overhead with different data sizes

---

[← Previous: GIL History](../part-06-gil/chapter-30-gil-history.md) | [Next: Asynchronous I/O →](chapter-32-async-io.md)

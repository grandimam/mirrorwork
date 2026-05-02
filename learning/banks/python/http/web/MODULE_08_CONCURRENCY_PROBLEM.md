# Module 8: The Concurrency Problem

## Overview

Your single-threaded server from Module 4 has a fatal flaw: it can only handle one client at a time. While serving Client A, Clients B through Z wait. This module examines why this is a problem, how serious it gets at scale, and surveys the solutions.

---

## Learning Objectives

By the end of this module, you will be able to:

1. Explain why single-threaded blocking fails
2. Understand the C10K problem and its evolution
3. Distinguish concurrency from parallelism
4. Measure server performance metrics
5. Choose appropriate concurrency models for different workloads

---

## 8.1 Why Single-Threaded Blocking Fails

### The Blocking Problem

```python
# Our current server (simplified)
while True:
    client = accept()      # Blocks until connection
    request = read(client) # Blocks until data arrives
    response = handle(request)  # May block on database, API, etc.
    write(client, response)     # Blocks until sent
    close(client)
```

**Timeline with one slow client:**

```
Time    Server                  Client A              Client B
─────────────────────────────────────────────────────────────────
0ms     accept() → Client A
10ms    read() waiting...       Sending slowly...     Waiting...
500ms   read() complete         Done sending          Still waiting...
510ms   handle() (DB query)                           Still waiting...
700ms   write()                                       Still waiting...
800ms   close()                                       Still waiting...
801ms   accept() → Client B                           Finally connected!
```

Client B waited **800ms** just because Client A was slow.

### The Math Gets Worse

If each request takes 100ms on average:
- 1 request: 100ms
- 10 requests: 1000ms (last request waits 900ms)
- 100 requests: 10,000ms (last waits 9.9 seconds)
- 1000 requests: queue grows indefinitely

**Throughput**: 10 requests/second maximum. Unacceptable for any real application.

---

## 8.2 The C10K Problem

### What is C10K?

In 1999, Dan Kegel posed the C10K problem: how do you handle 10,000 concurrent connections on a single machine?

At the time, this was considered extremely challenging:
- Memory per thread: ~1MB stack
- 10,000 threads = 10GB RAM (impossible then)
- Context switching overhead became prohibitive

### Evolution Beyond C10K

| Era | Challenge | Scale |
|-----|-----------|-------|
| 1990s | C1K | 1,000 connections |
| 2000s | C10K | 10,000 connections |
| 2010s | C100K | 100,000 connections |
| 2020s | C1M | 1,000,000 connections |

Modern solutions (async I/O, io_uring) can handle millions of connections on modest hardware.

---

## 8.3 Concurrency vs Parallelism

### Definitions

**Concurrency**: Dealing with multiple things at once (structure)
**Parallelism**: Doing multiple things at once (execution)

### Visual Comparison

```
Concurrency (single core):
Task A: ████░░░░████░░░░████
Task B: ░░░░████░░░░████░░░░

Parallelism (multi-core):
Core 1: ████████████████████ Task A
Core 2: ████████████████████ Task B
```

### Why the Distinction Matters

- **I/O-bound work** (web servers): Concurrency matters more
  - Most time spent waiting for network, disk, database
  - A single thread can manage many waiting operations

- **CPU-bound work** (computation): Parallelism matters more
  - Need multiple cores working simultaneously
  - Python's GIL limits this for threads

### Web Server Reality

```
Timeline of a typical request:

├─ Parse request ─┤   (CPU: 0.1ms)
                  ├─────── Query DB ───────┤   (I/O: 50ms, CPU idle)
                                           ├─ Build response ─┤  (CPU: 0.2ms)
                                                               ├─ Send ─┤ (I/O: 5ms)

CPU active: 0.3ms
Waiting for I/O: 55ms
I/O to CPU ratio: 183:1
```

A server doing I/O can theoretically handle **183 concurrent requests** with just one CPU core—if it can manage the concurrency properly.

---

## 8.4 Measuring Server Performance

### Key Metrics

| Metric | Description | Good Value |
|--------|-------------|------------|
| **Throughput (RPS)** | Requests per second | Higher is better |
| **Latency (p50/p95/p99)** | Response time at percentiles | Lower is better |
| **Concurrency** | Simultaneous connections | Depends on workload |
| **Error Rate** | Failed requests percentage | < 0.1% |
| **Memory Usage** | RAM per connection | Lower allows more connections |

### Benchmarking Tools

**wrk** (recommended):
```bash
# 10 threads, 100 connections, 30 seconds
wrk -t10 -c100 -d30s http://localhost:8080/
```

**ab** (Apache Bench):
```bash
# 10000 requests, 100 concurrent
ab -n 10000 -c 100 http://localhost:8080/
```

**hey**:
```bash
# 10000 requests, 100 concurrent
hey -n 10000 -c 100 http://localhost:8080/
```

### Interpreting Results

```
Running 30s test @ http://localhost:8080/
  10 threads and 100 connections
  Thread Stats   Avg      Stdev     Max   +/- Stdev
    Latency    45.23ms   12.34ms  234.56ms   89.12%
    Req/Sec   220.45     34.21    312.00     72.34%
  65432 requests in 30.00s, 12.34MB read
Requests/sec:   2181.07
Transfer/sec:    421.23KB
```

Key insights:
- **2181 RPS**: Throughput
- **45.23ms avg latency**: Typical response time
- **234.56ms max**: Worst case
- **+/- Stdev 89.12%**: Consistency (higher = more consistent)

---

## 8.5 Concurrency Models Overview

### Option 1: Threading

```
Main Thread          Worker Threads
     │
     ├──accept()───▶ Thread 1: handle(client1)
     │
     ├──accept()───▶ Thread 2: handle(client2)
     │
     └──accept()───▶ Thread 3: handle(client3)
```

**Pros**: Simple mental model, OS handles scheduling
**Cons**: Memory overhead, GIL limits parallelism, thread safety complexity

### Option 2: Multiprocessing

```
Master Process       Worker Processes
     │
     ├──fork()────▶ Process 1: accept() → handle()
     │
     ├──fork()────▶ Process 2: accept() → handle()
     │
     └──fork()────▶ Process 3: accept() → handle()
```

**Pros**: True parallelism, process isolation
**Cons**: Higher memory, IPC complexity, no shared state

### Option 3: Async I/O (Event-Driven)

```
Single Thread
     │
     ├─ accept() → register callback
     │
     ├─ poll() → client1 readable → read()
     │
     ├─ poll() → client2 ready → write()
     │
     └─ repeat...
```

**Pros**: Lowest memory, handles many connections, no locks
**Cons**: Callback complexity, can't block, requires async ecosystem

### Comparison Table

| Model | Memory per conn | Parallelism | Complexity | Best for |
|-------|----------------|-------------|------------|----------|
| Threading | ~1MB | Limited (GIL) | Medium | Moderate connections |
| Multiprocessing | ~Process size | Full | Medium | CPU-heavy work |
| Async I/O | ~KB | None (use with MP) | High | Many I/O-heavy connections |
| Hybrid | Varies | Full | Highest | Production systems |

---

## 8.6 Python's GIL

### What is the GIL?

The Global Interpreter Lock is a mutex that protects Python object access. Only one thread executes Python bytecode at a time.

```
Thread 1: [====GIL====]...........[====GIL====].........
Thread 2: ...........[====GIL====]...........[====GIL====]
                     ↑ Only one thread runs at a time
```

### When GIL Doesn't Matter

For I/O-bound work, the GIL is released during:
- `socket.recv()` / `socket.send()`
- `file.read()` / `file.write()`
- `time.sleep()`
- Database queries
- HTTP requests

This is why threading **still works** for web servers despite the GIL.

### When GIL Hurts

For CPU-bound work (image processing, cryptography, data crunching):
- Threads don't speed up computation
- May actually slow down due to lock contention
- Solution: Use multiprocessing or C extensions

---

## 8.7 Choosing a Model

### Decision Tree

```
Is your workload I/O-bound?
├── Yes → How many concurrent connections?
│         ├── < 100: Threading is fine
│         ├── 100-10,000: Async I/O recommended
│         └── > 10,000: Async + multiprocessing
│
└── No (CPU-bound) → Use multiprocessing
                     └── Can combine with async for I/O
```

### Real-World Architectures

**Simple API (< 1000 RPS)**:
- Thread pool with ~50 workers
- Example: Flask with Gunicorn sync workers

**High-Traffic API (> 10,000 RPS)**:
- Async I/O with multiprocessing
- Example: FastAPI with Uvicorn

**Hybrid (Mix of CPU and I/O)**:
- Async for I/O, process pool for CPU
- Example: FastAPI with background tasks

---

## Exercises

### Exercise 8.1: Benchmark Your Server

1. Run your Module 4 server
2. Benchmark with: `wrk -t4 -c100 -d10s http://localhost:8080/`
3. Record: RPS, latency, errors
4. Try with -c10, -c50, -c200
5. Plot the results

### Exercise 8.2: Simulate Slow Clients

Add a `/slow` endpoint that sleeps for 1 second:

```python
@app.get('/slow')
def slow(request):
    import time
    time.sleep(1)
    return Response.text("Slow response")
```

Benchmark it and observe the throughput collapse.

### Exercise 8.3: Calculate Theoretical Maximum

Given:
- Average request CPU time: 1ms
- Average I/O wait: 100ms
- Single thread

What's the theoretical maximum RPS? What if you have 100 threads?

---

## Deep Dive Questions

1. **Why can a single-threaded async server outperform a 100-thread server?**

2. **When would you choose multiprocessing over threading in Python?**

3. **How does HTTP/2 multiplexing relate to server-side concurrency?**

4. **Why do production servers like Gunicorn use a master/worker model?**

---

## Summary

Single-threaded blocking servers fail because:
1. One slow client blocks everyone
2. I/O wait time dominates
3. Throughput is limited to 1/latency

Solutions:
1. **Threading**: Simple, moderate scale
2. **Multiprocessing**: True parallelism, process isolation
3. **Async I/O**: Maximum concurrency, minimum memory

The next three modules dive deep into each approach.

---

## Next Module

**[Module 9: Threading Model →](./MODULE_09_THREADING.md)**

We'll build a thread pool server and understand threading in Python.

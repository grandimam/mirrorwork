# Module 9: Threading Model

## Overview

Threading is the most intuitive approach to concurrency: spawn a thread for each connection, let the OS handle scheduling. This module covers Python threading in depth, from basic threads to production thread pools.

---

## Learning Objectives

By the end of this module, you will be able to:

1. Implement thread-per-connection servers
2. Build efficient thread pool servers
3. Handle thread safety with locks and synchronization
4. Understand Python's GIL implications
5. Use thread-local storage for request context
6. Debug common threading issues

---

## 9.1 Python Threading Fundamentals

### Creating Threads

```python
import threading
import time


def worker(name: str, delay: float):
    """Thread worker function."""
    print(f"{name}: Starting")
    time.sleep(delay)
    print(f"{name}: Done")


# Method 1: Function-based
thread = threading.Thread(target=worker, args=("Thread-1", 1.0))
thread.start()
thread.join()  # Wait for completion


# Method 2: Class-based
class WorkerThread(threading.Thread):
    def __init__(self, name: str, delay: float):
        super().__init__()
        self.name = name
        self.delay = delay

    def run(self):
        print(f"{self.name}: Starting")
        time.sleep(self.delay)
        print(f"{self.name}: Done")


thread = WorkerThread("Thread-2", 1.0)
thread.start()
thread.join()
```

### Thread Attributes

```python
thread = threading.Thread(target=worker, args=("MyThread", 1.0))

# Set daemon (won't block program exit)
thread.daemon = True

# Set name
thread.name = "HTTPWorker-1"

# Check state
thread.is_alive()  # True if running
thread.ident       # Thread ID

# Current thread
threading.current_thread()
threading.main_thread()
threading.active_count()
```

---

## 9.2 Thread-Per-Connection Architecture

### Basic Implementation

```python
import socket
import threading


class ThreadedServer:
    """One thread per connection."""

    def __init__(self, host: str = '0.0.0.0', port: int = 8080):
        self.host = host
        self.port = port
        self.running = False

    def start(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.host, self.port))
        sock.listen(128)

        self.running = True
        print(f"Listening on {self.host}:{self.port}")

        try:
            while self.running:
                client, addr = sock.accept()

                # Spawn thread for each connection
                thread = threading.Thread(
                    target=self.handle_client,
                    args=(client, addr),
                    daemon=True
                )
                thread.start()
        finally:
            sock.close()

    def handle_client(self, client: socket.socket, addr: tuple):
        """Handle client in separate thread."""
        try:
            while True:
                data = client.recv(4096)
                if not data:
                    break
                # Process request and send response
                response = self.process_request(data)
                client.sendall(response)
        except Exception as e:
            print(f"Error handling {addr}: {e}")
        finally:
            client.close()

    def process_request(self, data: bytes) -> bytes:
        # Parse HTTP, route, generate response
        return b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nOK"
```

### Problems with Thread-Per-Connection

1. **Memory**: Each thread uses 1-8MB stack
2. **Overhead**: Thread creation is expensive
3. **Limits**: OS limits on number of threads
4. **Unbounded**: No limit on concurrent connections

---

## 9.3 Thread Pool Architecture

### Using ThreadPoolExecutor

```python
from concurrent.futures import ThreadPoolExecutor
import socket


class ThreadPoolServer:
    """Fixed thread pool for handling connections."""

    def __init__(
        self,
        host: str = '0.0.0.0',
        port: int = 8080,
        workers: int = 10
    ):
        self.host = host
        self.port = port
        self.workers = workers
        self.executor = None

    def start(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.host, self.port))
        sock.listen(128)

        # Create thread pool
        self.executor = ThreadPoolExecutor(
            max_workers=self.workers,
            thread_name_prefix='HTTPWorker'
        )

        print(f"Listening on {self.host}:{self.port} with {self.workers} workers")

        try:
            while True:
                client, addr = sock.accept()
                # Submit to thread pool
                self.executor.submit(self.handle_client, client, addr)
        except KeyboardInterrupt:
            print("Shutting down...")
        finally:
            self.executor.shutdown(wait=True)
            sock.close()

    def handle_client(self, client: socket.socket, addr: tuple):
        try:
            # ... handle request
            pass
        finally:
            client.close()
```

### Custom Thread Pool

```python
import queue
import threading
from typing import Callable, Any


class ThreadPool:
    """Custom thread pool with work queue."""

    def __init__(self, num_workers: int):
        self.num_workers = num_workers
        self.tasks: queue.Queue = queue.Queue()
        self.workers: list[threading.Thread] = []
        self.running = False

    def start(self):
        """Start worker threads."""
        self.running = True
        for i in range(self.num_workers):
            worker = threading.Thread(
                target=self._worker,
                name=f"Worker-{i}",
                daemon=True
            )
            worker.start()
            self.workers.append(worker)

    def submit(self, func: Callable, *args, **kwargs) -> None:
        """Submit task to pool."""
        self.tasks.put((func, args, kwargs))

    def _worker(self):
        """Worker thread main loop."""
        while self.running:
            try:
                func, args, kwargs = self.tasks.get(timeout=1.0)
                try:
                    func(*args, **kwargs)
                except Exception as e:
                    print(f"Task error: {e}")
                finally:
                    self.tasks.task_done()
            except queue.Empty:
                continue

    def shutdown(self, wait: bool = True):
        """Shutdown the pool."""
        self.running = False
        if wait:
            self.tasks.join()
            for worker in self.workers:
                worker.join(timeout=5.0)
```

---

## 9.4 Thread Safety

### Race Conditions

```python
# UNSAFE: Race condition
counter = 0

def increment():
    global counter
    for _ in range(100000):
        counter += 1  # NOT atomic!

# Two threads incrementing
t1 = threading.Thread(target=increment)
t2 = threading.Thread(target=increment)
t1.start(); t2.start()
t1.join(); t2.join()

print(counter)  # Not 200000! Probably ~150000
```

### Locks

```python
# SAFE: Using lock
counter = 0
lock = threading.Lock()

def increment():
    global counter
    for _ in range(100000):
        with lock:
            counter += 1

# Now counter will be 200000
```

### Lock Types

```python
# Basic Lock - simple mutual exclusion
lock = threading.Lock()

# RLock - reentrant, same thread can acquire multiple times
rlock = threading.RLock()

# Semaphore - allow N concurrent accesses
semaphore = threading.Semaphore(5)  # Max 5 threads

# BoundedSemaphore - error if released too many times
bounded = threading.BoundedSemaphore(5)

# Event - signal between threads
event = threading.Event()
event.set()      # Signal
event.wait()     # Wait for signal
event.clear()    # Reset

# Condition - complex synchronization
condition = threading.Condition()
with condition:
    condition.wait()      # Release lock and wait
    condition.notify()    # Wake one waiter
    condition.notify_all() # Wake all waiters
```

### Thread-Safe Collections

```python
import queue

# Thread-safe queues
q = queue.Queue()           # FIFO
q = queue.LifoQueue()       # LIFO (stack)
q = queue.PriorityQueue()   # Sorted by priority

q.put(item)                 # Add item
item = q.get()              # Remove and return (blocks if empty)
item = q.get_nowait()       # Raises queue.Empty if empty
q.task_done()               # Mark task complete
q.join()                    # Wait for all tasks done
```

---

## 9.5 Thread-Local Storage

### The Problem

```python
# Request context that's global but thread-specific
class RequestContext:
    request = None
    user = None

# PROBLEM: Threads share this!
```

### Solution: threading.local

```python
import threading

# Thread-local storage
context = threading.local()

def handle_request(request):
    # Each thread has its own context.request
    context.request = request
    context.user = get_user(request)

    # Any function can access it
    process_request()

def process_request():
    # Access current thread's context
    print(f"Processing for user: {context.user}")
```

### Context Class Pattern

```python
from contextvars import ContextVar
from typing import Optional


class RequestContext:
    """Request context using context variables (Python 3.7+)."""

    _request: ContextVar[Optional['HTTPRequest']] = ContextVar('request', default=None)
    _user: ContextVar[Optional['User']] = ContextVar('user', default=None)

    @classmethod
    def get_request(cls) -> Optional['HTTPRequest']:
        return cls._request.get()

    @classmethod
    def set_request(cls, request: 'HTTPRequest'):
        return cls._request.set(request)

    @classmethod
    def get_user(cls) -> Optional['User']:
        return cls._user.get()

    @classmethod
    def set_user(cls, user: 'User'):
        return cls._user.set(user)
```

---

## 9.6 Complete Threaded HTTP Server

```python
"""
Complete thread pool HTTP server.
"""

import socket
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional
import signal
import sys


class ThreadedHTTPServer:
    """Production-ready threaded HTTP server."""

    def __init__(
        self,
        host: str = '0.0.0.0',
        port: int = 8080,
        workers: int = 10,
        backlog: int = 128,
        timeout: float = 30.0
    ):
        self.host = host
        self.port = port
        self.workers = workers
        self.backlog = backlog
        self.timeout = timeout

        self.server_socket: Optional[socket.socket] = None
        self.executor: Optional[ThreadPoolExecutor] = None
        self.running = False

        self.router = Router()

        # Stats
        self.stats_lock = threading.Lock()
        self.requests_total = 0
        self.requests_active = 0

    def route(self, method: str, path: str):
        return self.router.route(method, path)

    def start(self):
        """Start the server."""
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # Create server socket
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(self.backlog)

        # Create thread pool
        self.executor = ThreadPoolExecutor(
            max_workers=self.workers,
            thread_name_prefix='HTTPWorker'
        )

        self.running = True
        print(f"Server started on http://{self.host}:{self.port}")
        print(f"Workers: {self.workers}")

        # Accept loop
        try:
            while self.running:
                try:
                    self.server_socket.settimeout(1.0)  # Allow checking running flag
                    client, addr = self.server_socket.accept()
                    self.executor.submit(self._handle_connection, client, addr)
                except socket.timeout:
                    continue
        finally:
            self.shutdown()

    def shutdown(self):
        """Graceful shutdown."""
        print("\nShutting down...")
        self.running = False

        if self.executor:
            self.executor.shutdown(wait=True, cancel_futures=False)

        if self.server_socket:
            self.server_socket.close()

        print(f"Served {self.requests_total} requests")

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        self.running = False

    def _handle_connection(self, client: socket.socket, addr: tuple):
        """Handle client connection in worker thread."""
        client.settimeout(self.timeout)

        with self.stats_lock:
            self.requests_active += 1

        try:
            # Keep-alive loop
            while self.running:
                try:
                    response = self._process_request(client)
                    if response is None:
                        break

                    client.sendall(response.serialize())

                    with self.stats_lock:
                        self.requests_total += 1

                    # Check connection header
                    if response.headers.get('Connection', '').lower() == 'close':
                        break

                except socket.timeout:
                    break  # Keep-alive timeout
                except ConnectionError:
                    break

        finally:
            with self.stats_lock:
                self.requests_active -= 1
            client.close()

    def _process_request(self, client: socket.socket) -> Optional[Response]:
        """Process single HTTP request."""
        try:
            reader = HTTPReader(client)
            parser = HTTPParser(reader)
            request = parser.parse()
        except ConnectionError:
            return None
        except HTTPParseError as e:
            return Response.error(e.status_code, str(e))

        # Route and handle
        try:
            match = self.router.match(request.method, request.path)
            if not match.handler:
                return Response.error(404)

            request.path_params = match.path_params
            return match.handler(request)

        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response.error(500)


# Usage
if __name__ == '__main__':
    server = ThreadedHTTPServer(workers=20)

    @server.route('GET', '/')
    def index(request):
        return Response.html("<h1>Threaded Server</h1>")

    @server.route('GET', '/stats')
    def stats(request):
        return Response.json({
            "requests_total": server.requests_total,
            "requests_active": server.requests_active,
            "workers": server.workers
        })

    server.start()
```

---

## 9.7 Lab: Build a Thread Pool Server

### Requirements

1. Fixed-size thread pool (configurable)
2. Graceful shutdown (wait for in-flight requests)
3. Request timeout handling
4. Basic stats endpoint
5. Benchmark and compare to single-threaded

### Benchmarking

```bash
# Single-threaded baseline
wrk -t4 -c100 -d30s http://localhost:8080/

# Threaded with 10 workers
wrk -t4 -c100 -d30s http://localhost:8080/

# Threaded with 50 workers
wrk -t4 -c100 -d30s http://localhost:8080/
```

Expected improvements:
- 10-50x throughput increase
- Much lower latency at high concurrency

---

## Exercises

### Exercise 9.1: Worker Scaling

Implement dynamic worker scaling based on load:
- Start with 5 workers
- Scale up to 50 under load
- Scale down when idle

### Exercise 9.2: Connection Limiting

Add a maximum connections limit:
- Reject new connections when at limit
- Return 503 Service Unavailable

### Exercise 9.3: Thread Metrics

Add per-worker metrics:
- Requests handled
- Average response time
- Idle time

---

## Deep Dive Questions

1. **Why use daemon threads for workers?**

2. **What happens if a worker thread raises an unhandled exception?**

3. **How do you debug deadlocks in a threaded server?**

4. **When would you choose threading over async?**

---

## Summary

You've learned:
1. Python threading basics
2. Thread-per-connection (simple but wasteful)
3. Thread pools (efficient, bounded)
4. Thread safety (locks, queues)
5. Thread-local storage (request context)
6. Production patterns (graceful shutdown, stats)

Next, we'll explore multiprocessing for true parallelism.

---

## Next Module

**[Module 10: Multiprocessing Model →](./MODULE_10_MULTIPROCESSING.md)**

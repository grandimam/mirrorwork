# Module 10: Multiprocessing Model

## Overview

Multiprocessing sidesteps Python's GIL entirely by using separate processes instead of threads. This module covers pre-fork servers, process pools, and inter-process communication—the architecture behind Gunicorn and other production servers.

---

## Learning Objectives

By the end of this module, you will be able to:

1. Explain when multiprocessing beats threading
2. Implement pre-fork server architecture
3. Use process pools effectively
4. Handle inter-process communication
5. Manage worker lifecycle (spawn, recycle, death)
6. Understand SO_REUSEPORT for load distribution

---

## 10.1 Process vs Thread

### Key Differences

| Aspect | Thread | Process |
|--------|--------|---------|
| Memory | Shared | Isolated |
| GIL | Shared (blocks) | Separate (parallel) |
| Creation | Fast (~1ms) | Slow (~100ms) |
| Communication | Direct | IPC required |
| Crash | May corrupt state | Isolated failure |
| Memory use | ~1MB stack | Full process (~50MB+) |

### When to Use Multiprocessing

- **CPU-bound work**: True parallelism needed
- **Isolation**: Worker crash shouldn't affect others
- **Mixed workload**: Some workers for CPU, some for I/O
- **Memory limits**: Workers can be recycled to prevent leaks

---

## 10.2 Pre-fork Server Architecture

### How It Works

```
┌─────────────────────────────────────────────────┐
│                  Master Process                  │
│  - Manages workers                               │
│  - Handles signals                               │
│  - Does not handle requests                      │
└─────────────────────┬───────────────────────────┘
                      │ fork()
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
   ┌─────────┐   ┌─────────┐   ┌─────────┐
   │ Worker 1│   │ Worker 2│   │ Worker 3│
   │ accept()│   │ accept()│   │ accept()│
   │ handle()│   │ handle()│   │ handle()│
   └─────────┘   └─────────┘   └─────────┘
```

### Basic Pre-fork Server

```python
import os
import socket
import signal
import sys
from typing import List, Optional


class PreForkServer:
    """Pre-fork server like Gunicorn."""

    def __init__(
        self,
        host: str = '0.0.0.0',
        port: int = 8080,
        workers: int = 4
    ):
        self.host = host
        self.port = port
        self.num_workers = workers
        self.workers: List[int] = []  # PIDs
        self.server_socket: Optional[socket.socket] = None
        self.running = True

    def start(self):
        """Start master process."""
        print(f"Master {os.getpid()} starting")

        # Create listening socket BEFORE forking
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(128)

        print(f"Listening on {self.host}:{self.port}")

        # Setup signal handlers
        signal.signal(signal.SIGINT, self._master_signal)
        signal.signal(signal.SIGTERM, self._master_signal)
        signal.signal(signal.SIGCHLD, self._child_signal)

        # Fork workers
        self._spawn_workers()

        # Master loop - just monitor workers
        while self.running:
            try:
                signal.pause()  # Wait for signals
            except InterruptedError:
                pass

            # Replace dead workers
            self._spawn_workers()

        self._shutdown()

    def _spawn_workers(self):
        """Spawn workers until we have enough."""
        while len(self.workers) < self.num_workers and self.running:
            pid = os.fork()

            if pid == 0:
                # Child process - become worker
                self._worker_main()
                sys.exit(0)
            else:
                # Parent - track child
                self.workers.append(pid)
                print(f"Spawned worker {pid}")

    def _worker_main(self):
        """Worker process main loop."""
        # Reset signal handlers in worker
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        signal.signal(signal.SIGTERM, self._worker_signal)
        signal.signal(signal.SIGCHLD, signal.SIG_DFL)

        worker_pid = os.getpid()
        print(f"Worker {worker_pid} started")

        requests_handled = 0

        while self.running:
            try:
                # Accept connection
                client, addr = self.server_socket.accept()

                # Handle request
                self._handle_client(client)
                requests_handled += 1

                # Optional: recycle after N requests
                if requests_handled >= 1000:
                    print(f"Worker {worker_pid} recycling after {requests_handled} requests")
                    break

            except OSError:
                break

        print(f"Worker {worker_pid} exiting")

    def _handle_client(self, client: socket.socket):
        """Handle client request."""
        try:
            client.settimeout(30)
            data = client.recv(4096)
            if data:
                # Simple response
                response = b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nOK"
                client.sendall(response)
        finally:
            client.close()

    def _master_signal(self, signum, frame):
        """Handle signals in master."""
        print(f"\nMaster received signal {signum}")
        self.running = False

    def _worker_signal(self, signum, frame):
        """Handle signals in worker."""
        self.running = False

    def _child_signal(self, signum, frame):
        """Handle SIGCHLD - worker died."""
        while True:
            try:
                pid, status = os.waitpid(-1, os.WNOHANG)
                if pid == 0:
                    break
                if pid in self.workers:
                    self.workers.remove(pid)
                    print(f"Worker {pid} exited with status {status}")
            except ChildProcessError:
                break

    def _shutdown(self):
        """Graceful shutdown."""
        print("Shutting down workers...")

        # Send SIGTERM to all workers
        for pid in self.workers:
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass

        # Wait for workers
        for pid in self.workers:
            try:
                os.waitpid(pid, 0)
                print(f"Worker {pid} terminated")
            except ChildProcessError:
                pass

        self.server_socket.close()
        print("Server stopped")


if __name__ == '__main__':
    server = PreForkServer(workers=4)
    server.start()
```

---

## 10.3 Process Pool Architecture

### Using multiprocessing.Pool

```python
from multiprocessing import Pool, cpu_count
import os


def handle_request(data: bytes) -> bytes:
    """Process request in worker process."""
    # This runs in a separate process
    return f"Handled by PID {os.getpid()}".encode()


class ProcessPoolServer:
    """Server using process pool for handling."""

    def __init__(self, workers: int = None):
        self.workers = workers or cpu_count()
        self.pool = None

    def start(self):
        self.pool = Pool(processes=self.workers)

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('0.0.0.0', 8080))
        sock.listen(128)

        try:
            while True:
                client, addr = sock.accept()
                data = client.recv(4096)

                # Submit to pool
                result = self.pool.apply_async(
                    handle_request,
                    (data,),
                    callback=lambda r: self._send_response(client, r)
                )
        finally:
            self.pool.close()
            self.pool.join()

    def _send_response(self, client, response):
        try:
            client.sendall(response)
        finally:
            client.close()
```

---

## 10.4 Inter-Process Communication

### Shared Memory

```python
from multiprocessing import Value, Array


# Shared counter
counter = Value('i', 0)  # 'i' = integer

def increment():
    with counter.get_lock():
        counter.value += 1


# Shared array
stats = Array('d', [0.0, 0.0, 0.0])  # 'd' = double
```

### Queues

```python
from multiprocessing import Queue, Process


def worker(task_queue: Queue, result_queue: Queue):
    while True:
        task = task_queue.get()
        if task is None:
            break
        result = process(task)
        result_queue.put(result)


# Main process
task_queue = Queue()
result_queue = Queue()

workers = [Process(target=worker, args=(task_queue, result_queue))
           for _ in range(4)]

for w in workers:
    w.start()

# Send tasks
for task in tasks:
    task_queue.put(task)

# Collect results
results = [result_queue.get() for _ in tasks]

# Shutdown
for _ in workers:
    task_queue.put(None)
for w in workers:
    w.join()
```

### Pipes

```python
from multiprocessing import Pipe, Process


def worker(conn):
    while True:
        msg = conn.recv()
        if msg == 'STOP':
            break
        conn.send(f"Echo: {msg}")
    conn.close()


parent_conn, child_conn = Pipe()
p = Process(target=worker, args=(child_conn,))
p.start()

parent_conn.send("Hello")
print(parent_conn.recv())  # "Echo: Hello"

parent_conn.send("STOP")
p.join()
```

---

## 10.5 SO_REUSEPORT

### The Problem

With pre-fork and a single socket:
- All workers compete for accept()
- "Thundering herd" problem
- Uneven load distribution

### Solution: SO_REUSEPORT

```python
import socket

# Each worker binds to same address
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)  # Key!
sock.bind(('0.0.0.0', 8080))
sock.listen(128)

# Kernel distributes connections across sockets
```

### Benefits

- Kernel-level load balancing
- No thundering herd
- Better cache locality
- Workers can be different processes

---

## 10.6 Worker Management

### Graceful Worker Recycling

```python
class ManagedWorker:
    """Worker with lifecycle management."""

    def __init__(self, max_requests: int = 1000, max_lifetime: int = 3600):
        self.max_requests = max_requests
        self.max_lifetime = max_lifetime
        self.start_time = time.time()
        self.request_count = 0

    def should_recycle(self) -> bool:
        """Check if worker should be recycled."""
        if self.request_count >= self.max_requests:
            return True
        if time.time() - self.start_time >= self.max_lifetime:
            return True
        return False

    def handle_request(self, client):
        self.request_count += 1
        # ... handle ...
        return self.should_recycle()
```

### Handling Worker Death

```python
def monitor_workers(workers: dict, target_count: int):
    """Monitor and replace dead workers."""
    while True:
        # Check for dead workers
        for pid in list(workers.keys()):
            try:
                result = os.waitpid(pid, os.WNOHANG)
                if result[0] != 0:
                    del workers[pid]
                    print(f"Worker {pid} died, respawning")
            except ChildProcessError:
                del workers[pid]

        # Spawn replacements
        while len(workers) < target_count:
            pid = spawn_worker()
            workers[pid] = time.time()

        time.sleep(1)
```

---

## 10.7 Copy-on-Write Optimization

### How It Works

After fork(), child processes share memory with parent until they write:

```python
# Before fork: Load large data
large_model = load_ml_model()  # 500MB
cache = load_cache()           # 100MB

# Fork workers
for _ in range(4):
    if os.fork() == 0:
        # Workers share the 600MB read-only
        # Only new allocations use extra memory
        handle_requests()
```

### Best Practices

1. Load read-only data before forking
2. Use immutable data structures where possible
3. Avoid modifying shared objects in workers

---

## 10.8 Complete Pre-fork Server

```python
"""
Production pre-fork HTTP server.
Similar architecture to Gunicorn.
"""

import os
import socket
import signal
import sys
import time
from dataclasses import dataclass
from typing import Dict, Optional, Callable


@dataclass
class WorkerConfig:
    max_requests: int = 1000
    max_lifetime: int = 3600
    timeout: int = 30


class ProductionPreForkServer:
    """Production-grade pre-fork server."""

    def __init__(
        self,
        app: Callable,
        host: str = '0.0.0.0',
        port: int = 8080,
        workers: int = 4,
        worker_config: WorkerConfig = None
    ):
        self.app = app
        self.host = host
        self.port = port
        self.num_workers = workers
        self.worker_config = worker_config or WorkerConfig()

        self.workers: Dict[int, float] = {}  # pid -> start_time
        self.server_socket: Optional[socket.socket] = None
        self.running = True

    def run(self):
        """Run the server."""
        self._setup_master()
        self._spawn_workers()
        self._master_loop()

    def _setup_master(self):
        """Setup master process."""
        print(f"Master PID: {os.getpid()}")

        # Create socket
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(2048)

        # Signals
        signal.signal(signal.SIGINT, self._handle_master_signal)
        signal.signal(signal.SIGTERM, self._handle_master_signal)
        signal.signal(signal.SIGCHLD, self._handle_sigchld)
        signal.signal(signal.SIGHUP, self._handle_sighup)

        print(f"Listening on http://{self.host}:{self.port}")
        print(f"Workers: {self.num_workers}")

    def _spawn_workers(self):
        """Spawn workers up to target count."""
        while len(self.workers) < self.num_workers:
            self._spawn_worker()

    def _spawn_worker(self):
        """Spawn a single worker."""
        pid = os.fork()

        if pid == 0:
            # Worker process
            self._worker_main()
            os._exit(0)
        else:
            # Master
            self.workers[pid] = time.time()
            print(f"Spawned worker {pid}")

    def _worker_main(self):
        """Worker process entry point."""
        # Reset signals
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        signal.signal(signal.SIGTERM, lambda s, f: sys.exit(0))
        signal.signal(signal.SIGCHLD, signal.SIG_DFL)

        pid = os.getpid()
        start_time = time.time()
        requests = 0

        print(f"Worker {pid} ready")

        while True:
            # Check limits
            if requests >= self.worker_config.max_requests:
                print(f"Worker {pid} max requests reached")
                break

            if time.time() - start_time >= self.worker_config.max_lifetime:
                print(f"Worker {pid} max lifetime reached")
                break

            try:
                # Accept with timeout for checking limits
                self.server_socket.settimeout(5.0)
                client, addr = self.server_socket.accept()
                client.settimeout(self.worker_config.timeout)

                # Handle request
                self._handle_request(client)
                requests += 1

            except socket.timeout:
                continue
            except Exception as e:
                print(f"Worker {pid} error: {e}")

        print(f"Worker {pid} exiting after {requests} requests")

    def _handle_request(self, client: socket.socket):
        """Handle HTTP request."""
        try:
            # Read request
            data = client.recv(8192)
            if not data:
                return

            # Simple parsing
            request = self._parse_request(data)

            # Call application
            response = self.app(request)

            # Send response
            client.sendall(response.serialize())

        except Exception as e:
            # Send error response
            error = b"HTTP/1.1 500 Internal Server Error\r\n\r\n"
            try:
                client.sendall(error)
            except:
                pass
        finally:
            client.close()

    def _parse_request(self, data: bytes) -> dict:
        """Parse HTTP request (simplified)."""
        lines = data.decode('utf-8', errors='replace').split('\r\n')
        method, path, _ = lines[0].split(' ')
        return {'method': method, 'path': path}

    def _master_loop(self):
        """Master monitoring loop."""
        while self.running:
            try:
                time.sleep(1)
                self._spawn_workers()  # Replace dead workers
            except InterruptedError:
                pass

        self._shutdown()

    def _handle_master_signal(self, signum, frame):
        """Handle SIGINT/SIGTERM in master."""
        print(f"\nReceived signal {signum}, shutting down...")
        self.running = False

    def _handle_sigchld(self, signum, frame):
        """Handle worker exit."""
        while True:
            try:
                pid, status = os.waitpid(-1, os.WNOHANG)
                if pid == 0:
                    break
                if pid in self.workers:
                    del self.workers[pid]
                    exit_code = os.WEXITSTATUS(status) if os.WIFEXITED(status) else -1
                    print(f"Worker {pid} exited (code={exit_code})")
            except ChildProcessError:
                break

    def _handle_sighup(self, signum, frame):
        """Handle SIGHUP - reload config."""
        print("Received SIGHUP, reloading...")
        # Could reload config, respawn workers, etc.

    def _shutdown(self):
        """Graceful shutdown."""
        print("Shutting down workers...")

        # Signal all workers
        for pid in list(self.workers.keys()):
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass

        # Wait with timeout
        deadline = time.time() + 30
        while self.workers and time.time() < deadline:
            self._handle_sigchld(None, None)
            time.sleep(0.1)

        # Force kill remaining
        for pid in self.workers:
            try:
                os.kill(pid, signal.SIGKILL)
                os.waitpid(pid, 0)
            except OSError:
                pass

        self.server_socket.close()
        print("Server stopped")


# Example app
def simple_app(request):
    from dataclasses import dataclass

    @dataclass
    class SimpleResponse:
        def serialize(self):
            body = f"Hello from PID {os.getpid()}\n".encode()
            return (
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: text/plain\r\n"
                b"Content-Length: " + str(len(body)).encode() + b"\r\n"
                b"\r\n" + body
            )

    return SimpleResponse()


if __name__ == '__main__':
    server = ProductionPreForkServer(
        app=simple_app,
        workers=4
    )
    server.run()
```

---

## Exercises

### Exercise 10.1: Hot Reload

Implement hot reload on SIGHUP:
- Spawn new workers
- Gracefully shutdown old workers
- Zero downtime deployment

### Exercise 10.2: Worker Stats

Add per-worker statistics shared via mmap:
- Requests handled
- Bytes transferred
- Average response time

### Exercise 10.3: Graceful Upgrade

Implement graceful binary upgrade:
- Start new master
- New master takes over socket
- Old master shuts down

---

## Summary

You've learned:
1. **Process vs Thread**: When isolation and true parallelism matter
2. **Pre-fork**: Fork workers before accepting connections
3. **Process Pools**: Managed worker pools
4. **IPC**: Queues, pipes, shared memory
5. **SO_REUSEPORT**: Kernel-level load balancing
6. **Worker lifecycle**: Spawn, recycle, monitor

Next, we explore the most scalable approach: async I/O.

---

## Next Module

**[Module 11: I/O Multiplexing →](./MODULE_11_IO_MULTIPLEXING.md)**

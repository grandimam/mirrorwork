# Module 11: I/O Multiplexing

## Overview

I/O multiplexing is the secret behind handling thousands of connections with a single thread. Instead of blocking on one socket, we ask the OS: "Which of these sockets are ready?" This module covers select, poll, epoll, and kqueue—the foundations of async I/O.

---

## Learning Objectives

By the end of this module, you will be able to:

1. Explain why blocking I/O limits scalability
2. Use select(), poll(), epoll(), and kqueue()
3. Understand edge-triggered vs level-triggered modes
4. Build a single-threaded concurrent server
5. Manage connection state efficiently

---

## 11.1 The Problem with Blocking I/O

### Blocking Calls

```python
data = sock.recv(4096)  # Blocks until data or close
sock.send(data)         # Blocks if buffer full
client = sock.accept()  # Blocks until connection
```

### What We Need

Instead of:
```python
while True:
    data = sock.recv(4096)  # Stuck here!
```

We want:
```python
ready_sockets = wait_for_any(all_sockets)
for sock in ready_sockets:
    data = sock.recv(4096)  # Won't block!
```

---

## 11.2 select()

### The First Solution (1983)

```python
import select

# Create socket sets
readable = [sock1, sock2, sock3]
writable = [sock1]
exceptional = [sock1, sock2, sock3]

# Wait for activity (with timeout)
ready_read, ready_write, ready_err = select.select(
    readable, writable, exceptional, timeout=1.0
)

for sock in ready_read:
    data = sock.recv(4096)  # Won't block
```

### select() Server Example

```python
import select
import socket


class SelectServer:
    """Single-threaded server using select()."""

    def __init__(self, host='0.0.0.0', port=8080):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.setblocking(False)
        self.server.bind((host, port))
        self.server.listen(128)

        self.clients = {}  # socket -> buffer

    def run(self):
        print(f"Select server on port {self.server.getsockname()[1]}")

        while True:
            # Build socket lists
            readable = [self.server] + list(self.clients.keys())
            writable = [s for s, buf in self.clients.items() if buf]

            # Wait for events
            ready_read, ready_write, _ = select.select(
                readable, writable, [], 1.0
            )

            # Handle readable sockets
            for sock in ready_read:
                if sock is self.server:
                    self._accept()
                else:
                    self._read(sock)

            # Handle writable sockets
            for sock in ready_write:
                self._write(sock)

    def _accept(self):
        client, addr = self.server.accept()
        client.setblocking(False)
        self.clients[client] = b''
        print(f"Connected: {addr}")

    def _read(self, sock):
        try:
            data = sock.recv(4096)
            if data:
                # Echo back
                self.clients[sock] += data
            else:
                self._close(sock)
        except (BlockingIOError, ConnectionError):
            self._close(sock)

    def _write(self, sock):
        try:
            sent = sock.send(self.clients[sock])
            self.clients[sock] = self.clients[sock][sent:]
        except (BlockingIOError, ConnectionError):
            self._close(sock)

    def _close(self, sock):
        print(f"Disconnected: {sock.getpeername()}")
        del self.clients[sock]
        sock.close()
```

### select() Limitations

1. **FD_SETSIZE limit**: Usually 1024 file descriptors
2. **O(n) scanning**: Kernel scans all FDs each call
3. **Copy overhead**: FD sets copied to/from kernel each call

---

## 11.3 poll()

### Improvements Over select()

```python
import select

# Create poll object
poll = select.poll()

# Register sockets
poll.register(sock1, select.POLLIN | select.POLLOUT)
poll.register(sock2, select.POLLIN)

# Wait for events
events = poll.poll(timeout=1000)  # milliseconds

for fd, event in events:
    if event & select.POLLIN:
        # Readable
        pass
    if event & select.POLLOUT:
        # Writable
        pass
    if event & (select.POLLERR | select.POLLHUP):
        # Error or hangup
        pass
```

### Event Flags

| Flag | Meaning |
|------|---------|
| POLLIN | Data available to read |
| POLLOUT | Ready for writing |
| POLLERR | Error condition |
| POLLHUP | Hang up (disconnected) |
| POLLNVAL | Invalid FD |

### poll() Benefits

- No FD_SETSIZE limit
- Cleaner API
- Still O(n) kernel scanning

---

## 11.4 epoll() (Linux)

### The Scalable Solution

```python
import select

# Create epoll instance
epoll = select.epoll()

# Register sockets
epoll.register(sock.fileno(), select.EPOLLIN | select.EPOLLET)

# Wait for events
events = epoll.poll(timeout=1.0)

for fd, event in events:
    if event & select.EPOLLIN:
        # Handle read
        pass

# Modify registration
epoll.modify(sock.fileno(), select.EPOLLOUT)

# Unregister
epoll.unregister(sock.fileno())

# Close
epoll.close()
```

### Why epoll Scales

1. **O(1) operations**: Add, modify, remove are constant time
2. **Only returns ready FDs**: No scanning inactive sockets
3. **Persistent state**: Kernel remembers registrations

### Edge-Triggered vs Level-Triggered

**Level-Triggered (default)**:
- Event fires as long as condition is true
- "There is data" → notified repeatedly until read

**Edge-Triggered (EPOLLET)**:
- Event fires only on state change
- "Data just arrived" → notified once
- Must read until EAGAIN

```python
# Level-triggered (safe, simpler)
epoll.register(fd, select.EPOLLIN)

# Edge-triggered (faster, tricky)
epoll.register(fd, select.EPOLLIN | select.EPOLLET)

# With edge-triggered, must drain the socket:
while True:
    try:
        data = sock.recv(4096)
        if not data:
            break
    except BlockingIOError:
        break  # No more data
```

### Complete epoll Server

```python
import select
import socket
from collections import defaultdict


class EpollServer:
    """High-performance epoll-based server."""

    def __init__(self, host='0.0.0.0', port=8080):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.setblocking(False)
        self.server.bind((host, port))
        self.server.listen(2048)

        self.epoll = select.epoll()
        self.epoll.register(self.server.fileno(), select.EPOLLIN)

        self.connections = {}      # fd -> socket
        self.read_buffers = defaultdict(bytes)
        self.write_buffers = defaultdict(bytes)

    def run(self):
        print(f"Epoll server on port {self.server.getsockname()[1]}")

        try:
            while True:
                events = self.epoll.poll(timeout=1.0)

                for fd, event in events:
                    if fd == self.server.fileno():
                        self._accept()
                    elif event & select.EPOLLIN:
                        self._read(fd)
                    elif event & select.EPOLLOUT:
                        self._write(fd)
                    elif event & (select.EPOLLERR | select.EPOLLHUP):
                        self._close(fd)
        finally:
            self.epoll.close()
            self.server.close()

    def _accept(self):
        while True:
            try:
                client, addr = self.server.accept()
                client.setblocking(False)
                fd = client.fileno()

                self.epoll.register(fd, select.EPOLLIN)
                self.connections[fd] = client
            except BlockingIOError:
                break

    def _read(self, fd):
        sock = self.connections[fd]
        try:
            while True:
                data = sock.recv(4096)
                if data:
                    self.read_buffers[fd] += data
                else:
                    self._close(fd)
                    return
        except BlockingIOError:
            pass

        # Process complete messages
        if b'\r\n\r\n' in self.read_buffers[fd]:
            request = self.read_buffers[fd]
            self.read_buffers[fd] = b''

            # Generate response
            response = b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nOK"
            self.write_buffers[fd] = response

            # Switch to write mode
            self.epoll.modify(fd, select.EPOLLOUT)

    def _write(self, fd):
        sock = self.connections[fd]
        try:
            while self.write_buffers[fd]:
                sent = sock.send(self.write_buffers[fd])
                self.write_buffers[fd] = self.write_buffers[fd][sent:]
        except BlockingIOError:
            return

        # Done writing, switch to read mode
        self.epoll.modify(fd, select.EPOLLIN)

    def _close(self, fd):
        self.epoll.unregister(fd)
        self.connections[fd].close()
        del self.connections[fd]
        del self.read_buffers[fd]
        del self.write_buffers[fd]
```

---

## 11.5 kqueue() (BSD/macOS)

### macOS/BSD Equivalent to epoll

```python
import select

# Create kqueue
kq = select.kqueue()

# Create kevent for reading
event = select.kevent(
    sock.fileno(),
    filter=select.KQ_FILTER_READ,
    flags=select.KQ_EV_ADD | select.KQ_EV_ENABLE
)

# Register event
kq.control([event], 0)

# Wait for events
events = kq.control([], 10, timeout=1.0)  # max 10 events

for event in events:
    fd = event.ident
    if event.filter == select.KQ_FILTER_READ:
        # Handle read
        pass
    elif event.filter == select.KQ_FILTER_WRITE:
        # Handle write
        pass
```

### kqueue Features

- Similar performance to epoll
- More flexible (timers, signals, file changes)
- Used on macOS, FreeBSD, OpenBSD

---

## 11.6 Python's selectors Module

### High-Level Abstraction

```python
import selectors
import socket

sel = selectors.DefaultSelector()  # Picks best for platform


def accept(sock, mask):
    client, addr = sock.accept()
    client.setblocking(False)
    sel.register(client, selectors.EVENT_READ, data=handle_client)


def handle_client(sock, mask):
    data = sock.recv(4096)
    if data:
        sock.sendall(data)
    else:
        sel.unregister(sock)
        sock.close()


# Setup server
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind(('0.0.0.0', 8080))
server.listen(128)
server.setblocking(False)
sel.register(server, selectors.EVENT_READ, data=accept)

# Event loop
while True:
    events = sel.select(timeout=1.0)
    for key, mask in events:
        callback = key.data
        callback(key.fileobj, mask)
```

### Selector Types

```python
selectors.SelectSelector   # select() - all platforms
selectors.PollSelector     # poll() - Unix
selectors.EpollSelector    # epoll() - Linux
selectors.KqueueSelector   # kqueue() - BSD/macOS
selectors.DefaultSelector  # Best available
```

---

## 11.7 Connection State Management

### State Machine

```python
from enum import Enum, auto
from dataclasses import dataclass, field


class ConnectionState(Enum):
    READING_REQUEST = auto()
    PROCESSING = auto()
    WRITING_RESPONSE = auto()
    CLOSING = auto()


@dataclass
class Connection:
    """State for a single connection."""
    socket: socket.socket
    state: ConnectionState = ConnectionState.READING_REQUEST
    read_buffer: bytes = b''
    write_buffer: bytes = b''
    request: dict = field(default_factory=dict)

    def wants_read(self) -> bool:
        return self.state == ConnectionState.READING_REQUEST

    def wants_write(self) -> bool:
        return self.state == ConnectionState.WRITING_RESPONSE and self.write_buffer


class ConnectionManager:
    """Manage multiple connections."""

    def __init__(self, selector):
        self.selector = selector
        self.connections = {}  # fd -> Connection

    def add(self, sock: socket.socket):
        sock.setblocking(False)
        conn = Connection(socket=sock)
        fd = sock.fileno()
        self.connections[fd] = conn
        self.selector.register(fd, selectors.EVENT_READ, data=conn)

    def remove(self, fd: int):
        conn = self.connections.pop(fd, None)
        if conn:
            self.selector.unregister(fd)
            conn.socket.close()

    def update_interest(self, fd: int):
        conn = self.connections[fd]
        events = 0
        if conn.wants_read():
            events |= selectors.EVENT_READ
        if conn.wants_write():
            events |= selectors.EVENT_WRITE
        self.selector.modify(fd, events, data=conn)
```

---

## Exercises

### Exercise 11.1: Benchmark Comparison

Benchmark select vs poll vs epoll:
- 100, 1000, 10000 connections
- Measure latency and throughput
- Plot the results

### Exercise 11.2: Timeout Handling

Add per-connection timeouts:
- Idle timeout (30s no activity)
- Request timeout (5s to send complete request)

### Exercise 11.3: Backpressure

Implement write backpressure:
- If write buffer exceeds limit, stop reading
- Resume reading when buffer drains

---

## Summary

You've learned:
1. **select()**: Universal but limited
2. **poll()**: No FD limit, still O(n)
3. **epoll()**: Linux, O(1), edge/level triggered
4. **kqueue()**: BSD/macOS, similar to epoll
5. **selectors**: Python's abstraction layer
6. **State management**: Per-connection state machines

This is the foundation for async I/O. Next, we'll build complete event loops.

---

## Next Module

**[Module 12: Event Loop Architecture →](./MODULE_12_EVENT_LOOP.md)**

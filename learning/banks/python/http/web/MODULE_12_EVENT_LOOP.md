# Module 12: Event Loop Architecture

## Overview

An event loop is the heart of async programming. It's a simple concept: wait for events, dispatch handlers, repeat. This module builds an event loop from scratch, understanding every component before using asyncio.

---

## Learning Objectives

By the end of this module, you will be able to:

1. Design event loop components
2. Implement callback registration and dispatch
3. Handle timers and scheduled callbacks
4. Build a complete event loop from scratch
5. Understand callback-based programming patterns

---

## 12.1 What is an Event Loop?

### The Core Concept

```python
while running:
    events = wait_for_events()
    for event in events:
        handler = get_handler(event)
        handler(event)
```

### Event Loop Components

```
┌─────────────────────────────────────────────────────────────┐
│                        Event Loop                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ I/O Poller  │  │   Timers    │  │  Callbacks  │         │
│  │  (epoll)    │  │   (heap)    │  │   (queue)   │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│         │                │                │                 │
│         └────────────────┴────────────────┘                 │
│                          │                                  │
│                          ▼                                  │
│                   ┌─────────────┐                           │
│                   │  Dispatch   │                           │
│                   └─────────────┘                           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 12.2 Building an Event Loop

### Basic Structure

```python
import selectors
import heapq
import time
from typing import Callable, Any, Optional
from dataclasses import dataclass, field


@dataclass(order=True)
class TimerHandle:
    """Scheduled callback."""
    when: float
    callback: Callable = field(compare=False)
    args: tuple = field(compare=False, default=())


class EventLoop:
    """Simple event loop implementation."""

    def __init__(self):
        self.selector = selectors.DefaultSelector()
        self.timers: list[TimerHandle] = []  # min-heap
        self.ready: list[tuple[Callable, tuple]] = []
        self.running = False

    def run_forever(self):
        """Run until stop() is called."""
        self.running = True
        while self.running:
            self._run_once()

    def run_until_complete(self, callback: Callable):
        """Run until callback completes."""
        done = False

        def on_done():
            nonlocal done
            done = True
            self.stop()

        self.call_soon(callback)
        self.call_soon(on_done)
        self.run_forever()

    def stop(self):
        """Stop the event loop."""
        self.running = False

    def _run_once(self):
        """Single iteration of event loop."""
        # Calculate timeout
        timeout = self._get_timeout()

        # Wait for I/O events
        events = self.selector.select(timeout)
        for key, mask in events:
            callback = key.data
            self.ready.append((callback, (key.fileobj, mask)))

        # Check timers
        now = time.monotonic()
        while self.timers and self.timers[0].when <= now:
            handle = heapq.heappop(self.timers)
            self.ready.append((handle.callback, handle.args))

        # Execute ready callbacks
        while self.ready:
            callback, args = self.ready.pop(0)
            try:
                callback(*args)
            except Exception as e:
                print(f"Callback error: {e}")

    def _get_timeout(self) -> Optional[float]:
        """Calculate select timeout."""
        if self.ready:
            return 0  # Immediate

        if self.timers:
            timeout = self.timers[0].when - time.monotonic()
            return max(0, timeout)

        return None  # Block indefinitely

    # I/O Registration
    def add_reader(self, fd, callback: Callable):
        """Register callback for readable fd."""
        try:
            self.selector.register(fd, selectors.EVENT_READ, callback)
        except KeyError:
            self.selector.modify(fd, selectors.EVENT_READ, callback)

    def remove_reader(self, fd):
        """Unregister fd."""
        try:
            self.selector.unregister(fd)
        except KeyError:
            pass

    def add_writer(self, fd, callback: Callable):
        """Register callback for writable fd."""
        try:
            self.selector.register(fd, selectors.EVENT_WRITE, callback)
        except KeyError:
            self.selector.modify(fd, selectors.EVENT_WRITE, callback)

    def remove_writer(self, fd):
        """Unregister fd."""
        try:
            self.selector.unregister(fd)
        except KeyError:
            pass

    # Timer Registration
    def call_soon(self, callback: Callable, *args):
        """Schedule callback for immediate execution."""
        self.ready.append((callback, args))

    def call_later(self, delay: float, callback: Callable, *args):
        """Schedule callback after delay seconds."""
        when = time.monotonic() + delay
        handle = TimerHandle(when, callback, args)
        heapq.heappush(self.timers, handle)
        return handle

    def call_at(self, when: float, callback: Callable, *args):
        """Schedule callback at specific time."""
        handle = TimerHandle(when, callback, args)
        heapq.heappush(self.timers, handle)
        return handle
```

---

## 12.3 Callback-Based Programming

### HTTP Server with Callbacks

```python
class CallbackHTTPServer:
    """HTTP server using callbacks."""

    def __init__(self, loop: EventLoop, host='0.0.0.0', port=8080):
        self.loop = loop
        self.host = host
        self.port = port
        self.server = None
        self.connections = {}

    def start(self):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.setblocking(False)
        self.server.bind((self.host, self.port))
        self.server.listen(128)

        self.loop.add_reader(self.server.fileno(), self._on_accept)
        print(f"Listening on {self.host}:{self.port}")

    def _on_accept(self, sock, mask):
        """Callback when server socket is readable."""
        while True:
            try:
                client, addr = self.server.accept()
                client.setblocking(False)

                conn = {'socket': client, 'buffer': b'', 'addr': addr}
                self.connections[client.fileno()] = conn

                self.loop.add_reader(client.fileno(), self._on_read)
            except BlockingIOError:
                break

    def _on_read(self, sock, mask):
        """Callback when client socket is readable."""
        fd = sock.fileno()
        conn = self.connections.get(fd)
        if not conn:
            return

        try:
            data = sock.recv(4096)
            if data:
                conn['buffer'] += data

                # Check for complete request
                if b'\r\n\r\n' in conn['buffer']:
                    self._process_request(fd)
            else:
                self._close_connection(fd)
        except (BlockingIOError, ConnectionError):
            self._close_connection(fd)

    def _process_request(self, fd):
        """Process complete request."""
        conn = self.connections[fd]

        # Generate response
        response = b"HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\nHello"
        conn['response'] = response
        conn['buffer'] = b''

        # Switch to write mode
        self.loop.remove_reader(fd)
        self.loop.add_writer(fd, self._on_write)

    def _on_write(self, sock, mask):
        """Callback when client socket is writable."""
        fd = sock.fileno()
        conn = self.connections.get(fd)
        if not conn:
            return

        try:
            sent = sock.send(conn['response'])
            conn['response'] = conn['response'][sent:]

            if not conn['response']:
                # Done writing
                self.loop.remove_writer(fd)
                self.loop.add_reader(fd, self._on_read)
        except (BlockingIOError, ConnectionError):
            self._close_connection(fd)

    def _close_connection(self, fd):
        """Close connection."""
        conn = self.connections.pop(fd, None)
        if conn:
            self.loop.remove_reader(fd)
            self.loop.remove_writer(fd)
            conn['socket'].close()


# Usage
loop = EventLoop()
server = CallbackHTTPServer(loop)
server.start()
loop.run_forever()
```

---

## 12.4 Callback Hell

### The Problem

```python
def handle_request(sock):
    def on_read(data):
        def on_db_query(result):
            def on_external_api(api_result):
                def on_write_done():
                    close_connection(sock)
                write_response(sock, api_result, on_write_done)
            call_external_api(result, on_external_api)
        query_database(data, on_db_query)
    read_request(sock, on_read)
```

This is callback hell—deeply nested, hard to read, error handling nightmare.

### Solutions

1. **Promises/Futures**: Chain callbacks
2. **Coroutines**: async/await syntax (next module)

---

## 12.5 Error Handling

### Robust Callback Dispatch

```python
def _run_once(self):
    # ... get events ...

    while self.ready:
        callback, args = self.ready.pop(0)
        try:
            callback(*args)
        except SystemExit:
            raise
        except BaseException as e:
            self._handle_exception(callback, e)

def _handle_exception(self, callback, exc):
    """Handle callback exception."""
    import traceback
    print(f"Exception in callback {callback}:")
    traceback.print_exc()

    # Could also:
    # - Call registered exception handler
    # - Log to monitoring system
    # - Stop the loop on critical errors
```

---

## 12.6 Complete Event Loop

```python
"""
Complete event loop implementation.
"""

import selectors
import heapq
import time
import socket
from typing import Callable, Optional, Any
from dataclasses import dataclass, field
from collections import deque


@dataclass(order=True)
class TimerHandle:
    when: float
    callback: Callable = field(compare=False)
    args: tuple = field(compare=False, default=())
    cancelled: bool = field(compare=False, default=False)

    def cancel(self):
        self.cancelled = True


class EventLoop:
    """
    Complete event loop with:
    - I/O multiplexing
    - Timers
    - Immediate callbacks
    - Exception handling
    """

    def __init__(self):
        self.selector = selectors.DefaultSelector()
        self.timers: list[TimerHandle] = []
        self.ready: deque = deque()
        self.running = False
        self._exception_handler = None

    # Running
    def run_forever(self):
        self.running = True
        try:
            while self.running:
                self._run_once()
        finally:
            self._cleanup()

    def stop(self):
        self.running = False

    def _run_once(self):
        # Process immediate callbacks
        self._process_ready()

        # Get timeout for select
        timeout = self._calculate_timeout()

        # Wait for I/O
        try:
            events = self.selector.select(timeout)
        except (OSError, ValueError):
            events = []

        # Queue I/O callbacks
        for key, mask in events:
            self.ready.append((key.data, (key.fileobj, mask)))

        # Queue timer callbacks
        self._process_timers()

        # Process all ready callbacks
        self._process_ready()

    def _process_ready(self):
        while self.ready:
            callback, args = self.ready.popleft()
            self._safe_call(callback, args)

    def _process_timers(self):
        now = time.monotonic()
        while self.timers and self.timers[0].when <= now:
            handle = heapq.heappop(self.timers)
            if not handle.cancelled:
                self.ready.append((handle.callback, handle.args))

    def _calculate_timeout(self) -> Optional[float]:
        if self.ready:
            return 0
        if not self.timers:
            return 1.0  # Max 1 second
        timeout = self.timers[0].when - time.monotonic()
        return max(0, min(timeout, 1.0))

    def _safe_call(self, callback: Callable, args: tuple):
        try:
            callback(*args)
        except SystemExit:
            raise
        except BaseException as e:
            if self._exception_handler:
                self._exception_handler(self, {'exception': e})
            else:
                import traceback
                traceback.print_exc()

    def _cleanup(self):
        self.selector.close()

    # I/O Methods
    def add_reader(self, fd, callback: Callable):
        key = self.selector.get_key(fd) if self._has_key(fd) else None
        events = selectors.EVENT_READ
        if key:
            events |= key.events
            self.selector.modify(fd, events, callback)
        else:
            self.selector.register(fd, events, callback)

    def remove_reader(self, fd):
        if self._has_key(fd):
            key = self.selector.get_key(fd)
            new_events = key.events & ~selectors.EVENT_READ
            if new_events:
                self.selector.modify(fd, new_events, key.data)
            else:
                self.selector.unregister(fd)

    def add_writer(self, fd, callback: Callable):
        key = self.selector.get_key(fd) if self._has_key(fd) else None
        events = selectors.EVENT_WRITE
        if key:
            events |= key.events
            self.selector.modify(fd, events, callback)
        else:
            self.selector.register(fd, events, callback)

    def remove_writer(self, fd):
        if self._has_key(fd):
            key = self.selector.get_key(fd)
            new_events = key.events & ~selectors.EVENT_WRITE
            if new_events:
                self.selector.modify(fd, new_events, key.data)
            else:
                self.selector.unregister(fd)

    def _has_key(self, fd) -> bool:
        try:
            self.selector.get_key(fd)
            return True
        except KeyError:
            return False

    # Timer Methods
    def call_soon(self, callback: Callable, *args) -> None:
        self.ready.append((callback, args))

    def call_later(self, delay: float, callback: Callable, *args) -> TimerHandle:
        when = time.monotonic() + delay
        return self.call_at(when, callback, *args)

    def call_at(self, when: float, callback: Callable, *args) -> TimerHandle:
        handle = TimerHandle(when, callback, args)
        heapq.heappush(self.timers, handle)
        return handle

    # Exception Handling
    def set_exception_handler(self, handler: Callable):
        self._exception_handler = handler


# Convenience function
def get_event_loop() -> EventLoop:
    """Get or create event loop."""
    global _loop
    if '_loop' not in globals() or _loop is None:
        _loop = EventLoop()
    return _loop
```

---

## 12.7 Lab: Build Your Own Event Loop

### Requirements

1. Implement EventLoop with:
   - I/O multiplexing (readers/writers)
   - Timer scheduling (call_later, call_at)
   - Immediate callbacks (call_soon)
   - Exception handling

2. Build echo server using your loop

3. Add features:
   - Cancellable timers
   - Signal handling
   - Debug mode with timing

### Test Your Loop

```python
def test_timer():
    loop = EventLoop()

    results = []

    loop.call_later(0.1, lambda: results.append(1))
    loop.call_later(0.2, lambda: results.append(2))
    loop.call_later(0.3, lambda: (results.append(3), loop.stop()))

    loop.run_forever()

    assert results == [1, 2, 3]


def test_io():
    loop = EventLoop()

    # Create socket pair for testing
    server, client = socket.socketpair()
    server.setblocking(False)
    client.setblocking(False)

    received = []

    def on_readable(sock, mask):
        data = sock.recv(1024)
        received.append(data)
        loop.stop()

    loop.add_reader(server.fileno(), on_readable)
    loop.call_soon(lambda: client.send(b"Hello"))

    loop.run_forever()

    assert received == [b"Hello"]
```

---

## Summary

You've built an event loop from scratch:

1. **Core loop**: Wait, dispatch, repeat
2. **I/O polling**: selectors for cross-platform
3. **Timers**: Heap-based scheduling
4. **Callbacks**: Queue and execute
5. **Error handling**: Don't crash the loop

This is exactly what asyncio does under the hood. Next, we'll add coroutines.

---

## Next Module

**[Module 13: Async/Await and Coroutines →](./MODULE_13_ASYNC_AWAIT.md)**

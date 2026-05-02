# Chapter 49: Signal Handling and Threads

## 49.1 Unix Signals Overview

Signals are asynchronous notifications sent to processes:

```
┌─────────────────────────────────────────────────────────────────┐
│              Common Unix Signals                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Signal     │ Number │ Default    │ Common Use                  │
│  ───────────┼────────┼────────────┼───────────────────────      │
│  SIGINT     │ 2      │ Terminate  │ Ctrl+C                      │
│  SIGTERM    │ 15     │ Terminate  │ Graceful shutdown           │
│  SIGKILL    │ 9      │ Terminate  │ Force kill (can't catch)    │
│  SIGSTOP    │ 19     │ Stop       │ Pause process (can't catch) │
│  SIGCONT    │ 18     │ Continue   │ Resume paused process       │
│  SIGHUP     │ 1      │ Terminate  │ Terminal hangup / reload    │
│  SIGUSR1    │ 10     │ Terminate  │ User-defined                │
│  SIGUSR2    │ 12     │ Terminate  │ User-defined                │
│  SIGALRM    │ 14     │ Terminate  │ Alarm timer expired         │
│  SIGCHLD    │ 17     │ Ignore     │ Child process changed       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 49.2 Signal Handling in Python

### Basic Signal Handler

```python
import signal
import sys
import time

def signal_handler(signum, frame):
    print(f"\nReceived signal {signum}")
    print("Cleaning up...")
    sys.exit(0)

# Register handler for SIGINT (Ctrl+C)
signal.signal(signal.SIGINT, signal_handler)

# Register handler for SIGTERM
signal.signal(signal.SIGTERM, signal_handler)

print("Running... Press Ctrl+C to stop")
while True:
    time.sleep(1)
    print(".", end="", flush=True)
```

### Available Signal Handlers

```python
import signal

# Default handler
signal.signal(signal.SIGINT, signal.SIG_DFL)

# Ignore signal
signal.signal(signal.SIGINT, signal.SIG_IGN)

# Custom handler
signal.signal(signal.SIGINT, my_handler)

# Get current handler
current = signal.getsignal(signal.SIGINT)
```

## 49.3 Signals and Threads

### The Main Thread Rule

```
┌─────────────────────────────────────────────────────────────────┐
│              Signals and Threads                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Key Rules:                                                      │
│                                                                  │
│  1. Only the MAIN thread can set signal handlers                │
│     (signal.signal() must be called from main thread)           │
│                                                                  │
│  2. Only the MAIN thread receives signals                       │
│     (Python's signal module behavior)                            │
│                                                                  │
│  3. Signals can interrupt system calls                          │
│     (may raise InterruptedError)                                │
│                                                                  │
│  4. Signal handlers run in the main thread                      │
│     (even if signal sent to different thread)                   │
│                                                                  │
│  Implication: Worker threads can't directly handle signals      │
│               Must communicate through other mechanisms         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Signal Handler Registration

```python
import signal
import threading

def setup_signals():
    # This MUST be called from main thread
    if threading.current_thread() is not threading.main_thread():
        raise RuntimeError("Must be called from main thread")

    signal.signal(signal.SIGINT, handle_interrupt)
    signal.signal(signal.SIGTERM, handle_terminate)

def handle_interrupt(signum, frame):
    print("Interrupt received in main thread")

def handle_terminate(signum, frame):
    print("Terminate received in main thread")

# This fails from worker thread
def worker():
    try:
        signal.signal(signal.SIGINT, handle_interrupt)
    except ValueError as e:
        print(f"Error: {e}")  # signal only works in main thread

threading.Thread(target=worker).start()
```

## 49.4 Coordinating Signals with Threads

### Using Event for Shutdown

```python
import signal
import threading
import time

shutdown_event = threading.Event()

def signal_handler(signum, frame):
    print(f"\nReceived signal {signum}, initiating shutdown...")
    shutdown_event.set()

def worker(name):
    while not shutdown_event.is_set():
        print(f"Worker {name} doing work...")
        # Check event periodically
        shutdown_event.wait(timeout=1.0)
    print(f"Worker {name} shutting down")

# Register signal handler (main thread)
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Start workers
threads = [threading.Thread(target=worker, args=(f"T{i}",))
           for i in range(3)]
for t in threads:
    t.start()

# Main thread waits
print("Press Ctrl+C to stop")
shutdown_event.wait()

# Wait for workers
for t in threads:
    t.join()
print("All workers stopped")
```

### Using Queue for Communication

```python
import signal
import threading
import queue
import time

command_queue = queue.Queue()

def signal_handler(signum, frame):
    command_queue.put(('shutdown', signum))

def worker(q):
    while True:
        try:
            cmd, arg = q.get(timeout=1.0)
            if cmd == 'shutdown':
                print(f"Worker received shutdown (signal {arg})")
                break
            elif cmd == 'task':
                print(f"Worker processing: {arg}")
        except queue.Empty:
            print("Worker waiting...")

signal.signal(signal.SIGINT, signal_handler)

thread = threading.Thread(target=worker, args=(command_queue,))
thread.start()

# Simulate some work
for i in range(5):
    command_queue.put(('task', f'item-{i}'))
    time.sleep(0.5)

thread.join()
```

## 49.5 Handling Interrupts During I/O

### InterruptedError

```python
import signal
import socket
import errno

def handle_sigalrm(signum, frame):
    pass  # Just interrupt the syscall

signal.signal(signal.SIGALRM, handle_sigalrm)

def recv_with_timeout(sock, timeout):
    signal.alarm(timeout)
    try:
        data = sock.recv(1024)
        signal.alarm(0)  # Cancel alarm
        return data
    except InterruptedError:
        return None  # Timeout
    except OSError as e:
        if e.errno == errno.EINTR:
            return None  # Timeout (older Python)
        raise
```

### Automatic Restart of System Calls

```python
import signal

def handler(signum, frame):
    print("Signal received")

# By default, system calls are restarted after signal
signal.signal(signal.SIGINT, handler)

# To prevent restart, use siginterrupt
signal.siginterrupt(signal.SIGINT, True)

# Now SIGINT will interrupt system calls with EINTR
```

## 49.6 Thread-Safe Signal Handling

### The signalfd Approach (Linux)

```python
# Using signalfd for thread-safe signal handling
# Requires: pip install signalfd

import signalfd
import signal
import select
import threading

def signal_reader_thread(sfd):
    """Read signals from signalfd."""
    while True:
        # Wait for signal
        r, _, _ = select.select([sfd], [], [])
        if sfd in r:
            info = sfd.read()
            print(f"Received signal: {info.ssi_signo}")
            if info.ssi_signo == signal.SIGTERM:
                break

# Block signals in main thread (they go to signalfd instead)
signal.pthread_sigmask(signal.SIG_BLOCK, [signal.SIGINT, signal.SIGTERM])

# Create signalfd
sfd = signalfd.signalfd(-1, [signal.SIGINT, signal.SIGTERM])

# Read signals in dedicated thread
reader = threading.Thread(target=signal_reader_thread, args=(sfd,))
reader.start()
```

### Using signal.set_wakeup_fd

```python
import signal
import os
import select
import threading

# Create a pipe for signal notification
read_fd, write_fd = os.pipe()

# Make write end non-blocking
os.set_blocking(write_fd, False)

# Set as wakeup fd
old_fd = signal.set_wakeup_fd(write_fd)

def signal_handler(signum, frame):
    pass  # Signal byte already written to pipe

signal.signal(signal.SIGINT, signal_handler)

def wait_for_signal():
    """Wait for signal using select."""
    readable, _, _ = select.select([read_fd], [], [])
    if read_fd in readable:
        signum = os.read(read_fd, 1)
        return signum[0]

# Now you can wait for signals with select
# (useful in event loops)
```

## 49.7 Async Signal Safety

### Signal Handler Restrictions

```
┌─────────────────────────────────────────────────────────────────┐
│              Signal Handler Safety                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  SAFE in signal handlers:                                        │
│  • Setting a flag/event                                         │
│  • Writing to pipe (non-blocking)                               │
│  • Calling async-signal-safe functions                          │
│  • sys.exit() (in Python)                                       │
│                                                                  │
│  UNSAFE in signal handlers:                                      │
│  • Allocating memory                                            │
│  • Acquiring locks                                               │
│  • I/O operations (print, file access)                          │
│  • Calling most library functions                                │
│                                                                  │
│  Python exception: Signal handlers run in "virtual time"        │
│  between bytecode instructions, so they're more flexible        │
│  than C signal handlers.                                         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Safe Signal Handler Pattern

```python
import signal
import threading

# Global flag that signal handler can safely set
shutdown_requested = False
shutdown_lock = threading.Lock()

def safe_signal_handler(signum, frame):
    global shutdown_requested
    # Just set a flag - minimal work in handler
    shutdown_requested = True

signal.signal(signal.SIGINT, safe_signal_handler)

def main_loop():
    while not shutdown_requested:
        # Do work
        do_some_work()

        # Periodically check flag
        if shutdown_requested:
            break

    # Clean shutdown outside signal handler
    cleanup()

def cleanup():
    # Safe to do complex operations here
    print("Cleaning up...")
    save_state()
    close_connections()
```

## 49.8 Sending Signals

### To Current Process

```python
import signal
import os

# Send signal to self
os.kill(os.getpid(), signal.SIGUSR1)

# Using raise
signal.raise_signal(signal.SIGUSR1)  # Python 3.8+
```

### To Another Process

```python
import os
import signal

# Send signal to specific process
pid = 12345
os.kill(pid, signal.SIGTERM)

# Send to process group
os.killpg(pgid, signal.SIGTERM)
```

### To Threads (Using Exceptions)

```python
import threading
import ctypes
import time

def set_thread_async_exception(thread_id, exception):
    """Raise exception in another thread."""
    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(
        ctypes.c_ulong(thread_id),
        ctypes.py_object(exception)
    )
    if res == 0:
        raise ValueError("Invalid thread id")
    elif res > 1:
        ctypes.pythonapi.PyThreadState_SetAsyncExc(
            ctypes.c_ulong(thread_id), None
        )
        raise SystemError("Exception raise failure")

def worker():
    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("Worker interrupted")

thread = threading.Thread(target=worker)
thread.start()

time.sleep(1)

# Interrupt the worker thread
set_thread_async_exception(thread.ident, KeyboardInterrupt)
thread.join()
```

## 49.9 Signal Timing

### Using Alarms

```python
import signal
import time

class TimeoutError(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutError("Operation timed out")

def with_timeout(func, timeout_seconds):
    """Run function with timeout."""
    # Set the signal handler
    old_handler = signal.signal(signal.SIGALRM, timeout_handler)

    # Set the alarm
    signal.alarm(timeout_seconds)

    try:
        result = func()
    finally:
        # Cancel the alarm
        signal.alarm(0)
        # Restore old handler
        signal.signal(signal.SIGALRM, old_handler)

    return result

def slow_function():
    time.sleep(10)
    return "done"

try:
    result = with_timeout(slow_function, 2)
except TimeoutError:
    print("Function timed out!")
```

### Interval Timer

```python
import signal
import time

counter = 0

def alarm_handler(signum, frame):
    global counter
    counter += 1
    print(f"Tick {counter}")

# Set up handler
signal.signal(signal.SIGALRM, alarm_handler)

# Set interval timer (value, interval) in seconds
signal.setitimer(signal.ITIMER_REAL, 1.0, 1.0)

# Do other work
time.sleep(5)

# Cancel timer
signal.setitimer(signal.ITIMER_REAL, 0, 0)
```

## 49.10 Cross-Platform Considerations

### Windows Differences

```python
import signal
import sys

if sys.platform == 'win32':
    # Windows only supports these signals:
    # SIGINT, SIGTERM, SIGABRT, SIGFPE, SIGILL, SIGSEGV

    # No SIGALRM, SIGUSR1, SIGUSR2, etc.

    # Use threading.Timer instead of SIGALRM
    import threading

    def timeout_callback():
        print("Timeout!")

    timer = threading.Timer(5.0, timeout_callback)
    timer.start()

    # Cancel if needed
    timer.cancel()
else:
    # Unix-specific signal handling
    signal.signal(signal.SIGALRM, alarm_handler)
    signal.alarm(5)
```

### Portable Signal Handling

```python
import signal
import sys

def setup_signal_handlers():
    """Set up signal handlers in a cross-platform way."""

    def shutdown_handler(signum, frame):
        print(f"Shutdown requested (signal {signum})")
        sys.exit(0)

    # These work on all platforms
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    # Unix-specific
    if hasattr(signal, 'SIGHUP'):
        signal.signal(signal.SIGHUP, shutdown_handler)

    if hasattr(signal, 'SIGUSR1'):
        signal.signal(signal.SIGUSR1, reload_handler)
```

## Summary

- **Signals** are async notifications to processes
- **Main thread only** can set handlers in Python
- **Signal handlers** should do minimal work
- **Use Events/Queues** to communicate with workers
- **InterruptedError** when signals interrupt I/O
- **signalfd/set_wakeup_fd** for thread-safe handling
- **Cross-platform** differences require care

## Practice Exercises

1. Implement graceful shutdown for a multi-threaded server
2. Create a timeout decorator using signals
3. Build a process supervisor that handles child signals
4. Implement a signal-based reload mechanism

---

[← Previous: Thread Safety Patterns](chapter-48-thread-safety.md) | [Next: Import System Overview →](../part-11-import/chapter-50-import-overview.md)

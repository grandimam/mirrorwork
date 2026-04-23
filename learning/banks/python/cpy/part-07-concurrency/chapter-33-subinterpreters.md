# Chapter 33: Subinterpreters

## 33.1 What Are Subinterpreters

Subinterpreters are isolated Python interpreters within the same process:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Subinterpreters                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Single Process                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                                                          │    │
│  │  Main Interpreter          Subinterpreter 1              │    │
│  │  ┌──────────────────┐     ┌──────────────────┐          │    │
│  │  │ • Own globals    │     │ • Own globals    │          │    │
│  │  │ • Own modules    │     │ • Own modules    │          │    │
│  │  │ • Own __main__   │     │ • Own __main__   │          │    │
│  │  │ • Own GIL*       │     │ • Own GIL*       │          │    │
│  │  └──────────────────┘     └──────────────────┘          │    │
│  │                                                          │    │
│  │  * Per-interpreter GIL in Python 3.12+                  │    │
│  │                                                          │    │
│  │  Shared: Memory space, C extensions (some), OS resources│    │
│  │  Isolated: Python objects, namespaces, import state     │    │
│  │                                                          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 33.2 `_xxsubinterpreters` Module

The internal module for subinterpreter management:

```python
import _xxsubinterpreters as interpreters

# Create a new subinterpreter
interp_id = interpreters.create()
print(f"Created interpreter: {interp_id}")

# Run code in the subinterpreter
interpreters.run_string(interp_id, """
import sys
print(f"Hello from subinterpreter!")
print(f"Interpreter ID: {id(sys)}")
""")

# Destroy the subinterpreter
interpreters.destroy(interp_id)
```

## 33.3 PEP 554: Multiple Interpreters in Stdlib

### High-Level API (Python 3.12+)

```python
# Note: API may vary by Python version
import interpreters

# Create interpreter
interp = interpreters.create()

# Run code
interp.run("x = 1 + 2")
interp.run("print(x)")

# Close interpreter
interp.close()
```

### Channel-Based Communication

```python
import interpreters

# Create a channel for communication
send_channel, recv_channel = interpreters.create_channel()

# In main interpreter
send_channel.send(b"Hello from main!")

# In subinterpreter
interp = interpreters.create()
interp.run(f"""
import interpreters
channel = interpreters.RecvChannel({recv_channel.id})
data = channel.recv()
print(f"Received: {{data}}")
""")
```

## 33.4 Per-Interpreter GIL (PEP 684, Python 3.12+)

### Before Python 3.12

```
┌─────────────────────────────────────────────────────────────────┐
│           Shared GIL (Pre-3.12)                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   Interp 1   │    │   Interp 2   │    │   Interp 3   │      │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘      │
│         │                   │                   │               │
│         └───────────────────┼───────────────────┘               │
│                             │                                    │
│                      ┌──────┴──────┐                            │
│                      │  SHARED GIL │                            │
│                      └─────────────┘                            │
│                                                                  │
│  All interpreters compete for the same GIL                      │
│  No parallelism benefit                                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Python 3.12+ Per-Interpreter GIL

```
┌─────────────────────────────────────────────────────────────────┐
│           Per-Interpreter GIL (3.12+)                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   Interp 1   │    │   Interp 2   │    │   Interp 3   │      │
│  │  ┌────────┐  │    │  ┌────────┐  │    │  ┌────────┐  │      │
│  │  │  GIL 1 │  │    │  │  GIL 2 │  │    │  │  GIL 3 │  │      │
│  │  └────────┘  │    │  └────────┘  │    │  └────────┘  │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│                                                                  │
│  Each interpreter has its own GIL                               │
│  TRUE parallelism for CPU-bound Python code!                    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Using Per-Interpreter GIL

```python
import interpreters
import threading

def run_in_interpreter():
    interp = interpreters.create()
    interp.run("""
import time
start = time.time()
total = sum(range(10**7))
print(f"Done in {time.time() - start:.2f}s")
""")
    interp.close()

# Run interpreters in threads - they can execute in parallel!
threads = [
    threading.Thread(target=run_in_interpreter)
    for _ in range(4)
]

for t in threads:
    t.start()
for t in threads:
    t.join()

# With per-interpreter GIL, all 4 can run CPU-bound code
# truly in parallel!
```

## 33.5 Data Sharing Between Interpreters

### Challenges

```python
# Objects CANNOT be directly shared between interpreters
# Each interpreter has its own object space

# WRONG - won't work:
shared_list = []  # Main interpreter's object
# subinterpreter.run("shared_list.append(1)")  # Error!
```

### Safe Sharing Methods

```python
# 1. Channels (bytes, simple types)
import interpreters

send_ch, recv_ch = interpreters.create_channel()
send_ch.send(b"serialized data")

# 2. Shared memory
from multiprocessing import shared_memory
shm = shared_memory.SharedMemory(create=True, size=1000)
# Pass shm.name to subinterpreter

# 3. Memory-mapped files
import mmap
# Both interpreters can map the same file

# 4. Pickle for complex objects
import pickle
data = pickle.dumps(complex_object)
# Send bytes through channel
```

## 33.6 Use Cases and Limitations

### Good Use Cases

```python
# 1. Parallel CPU-bound tasks (with per-interpreter GIL)
# 2. Isolated plugin execution
# 3. Multi-tenant applications
# 4. Sandboxing untrusted code
# 5. Testing module isolation
```

### Limitations

```python
# 1. Not all C extensions support subinterpreters
#    - Must check Py_mod_multiple_interpreters flag

# 2. Higher overhead than threads
#    - Each interpreter has own module imports
#    - Memory not shared efficiently

# 3. Limited data sharing
#    - Must serialize/deserialize objects

# 4. Some global state still shared
#    - File descriptors
#    - Environment variables
#    - Signal handlers
```

### Checking Extension Compatibility

```python
import sys

def check_subinterpreter_safe(module_name):
    """Check if a module is safe for subinterpreters."""
    module = sys.modules.get(module_name)
    if module is None:
        return "Not imported"

    # Check for multi-interpreter support flag
    spec = getattr(module, '__spec__', None)
    if spec:
        loader = getattr(spec, 'loader', None)
        # Check loader's multi-interpreter support
        pass

    return "Check module documentation"
```

## 33.7 `interpreters` Module (Python 3.13+)

```python
# Python 3.13+ provides cleaner API
import interpreters

# List all interpreters
for interp in interpreters.list_all():
    print(f"Interpreter: {interp.id}")

# Get current interpreter
current = interpreters.get_current()
print(f"Current: {current.id}")

# Get main interpreter
main = interpreters.get_main()
print(f"Main: {main.id}")

# Create with per-interpreter GIL
interp = interpreters.create()  # Has own GIL by default in 3.12+

# Check if interpreter is running
print(f"Running: {interp.is_running()}")
```

## Summary

- **Subinterpreters** provide isolation within a process
- **Per-interpreter GIL** (3.12+) enables true parallelism
- **Data sharing** requires serialization (channels, shared memory)
- **Not all extensions** support subinterpreters
- **Use cases**: Parallel CPU work, isolation, sandboxing
- **Trade-offs**: More overhead than threads, limited sharing

## Practice Exercises

1. Create multiple subinterpreters and run code in parallel
2. Implement data sharing via channels
3. Benchmark subinterpreters vs multiprocessing
4. Check which popular packages support subinterpreters

---

[← Previous: Asynchronous I/O](chapter-32-async-io.md) | [Next: C Extensions and GIL →](chapter-34-c-extensions-gil.md)

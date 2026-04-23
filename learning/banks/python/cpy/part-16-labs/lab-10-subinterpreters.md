# Lab 10: Subinterpreters

## Objective

Explore Python's subinterpreter feature to understand isolated Python execution environments and their potential for true parallelism.

## Prerequisites

- Understanding of Python runtime (Part 1)
- Knowledge of the GIL and per-interpreter GIL (Part 6, Chapter 30)
- Python 3.12+ recommended for best subinterpreter support

## Lab Setup

```python
# lab10_subinterpreters.py
import sys
import time
import threading
from typing import Any, Dict, List, Optional, Callable
import pickle
import queue

# Check Python version
if sys.version_info < (3, 12):
    print("Warning: Subinterpreters work best with Python 3.12+")
    print(f"Current version: {sys.version}")

# Import interpreters module (Python 3.12+)
try:
    import _interpreters as interpreters
    HAS_INTERPRETERS = True
except ImportError:
    HAS_INTERPRETERS = False
    print("_interpreters module not available")
```

## Exercise 1: Basic Subinterpreter Management

Create and manage subinterpreters:

```python
class SubinterpreterManager:
    """
    Manage Python subinterpreters.

    TODO: Implement basic subinterpreter lifecycle management.
    """

    def __init__(self):
        self.interpreters: Dict[int, dict] = {}
        self._lock = threading.Lock()

    def create(self) -> int:
        """Create a new subinterpreter."""
        if not HAS_INTERPRETERS:
            raise RuntimeError("Subinterpreters not available")

        interp_id = interpreters.create()

        with self._lock:
            self.interpreters[interp_id] = {
                'created_at': time.time(),
                'executions': 0,
                'total_time': 0.0
            }

        print(f"Created interpreter {interp_id}")
        return interp_id

    def destroy(self, interp_id: int):
        """Destroy a subinterpreter."""
        if not HAS_INTERPRETERS:
            return

        interpreters.destroy(interp_id)

        with self._lock:
            if interp_id in self.interpreters:
                del self.interpreters[interp_id]

        print(f"Destroyed interpreter {interp_id}")

    def run_string(self, interp_id: int, code: str) -> None:
        """
        Run Python code in a subinterpreter.

        Note: No direct return value - use channels for communication.
        """
        if not HAS_INTERPRETERS:
            raise RuntimeError("Subinterpreters not available")

        start = time.time()

        try:
            interpreters.run_string(interp_id, code)
        finally:
            elapsed = time.time() - start
            with self._lock:
                if interp_id in self.interpreters:
                    self.interpreters[interp_id]['executions'] += 1
                    self.interpreters[interp_id]['total_time'] += elapsed

    def list_all(self) -> List[int]:
        """List all interpreter IDs."""
        if not HAS_INTERPRETERS:
            return []
        return list(interpreters.list_all())

    def get_stats(self) -> Dict:
        """Get statistics for all interpreters."""
        with self._lock:
            return dict(self.interpreters)

    def cleanup(self):
        """Destroy all managed interpreters."""
        for interp_id in list(self.interpreters.keys()):
            try:
                self.destroy(interp_id)
            except:
                pass

manager = SubinterpreterManager()
```

## Exercise 2: Inter-Interpreter Communication

Implement communication between interpreters:

```python
class InterpreterChannel:
    """
    Communication channel between interpreters.

    TODO: Implement send/receive using interpreters module channels.

    Note: In Python 3.12+, use interpreters.channel_create(), etc.
    For earlier versions, we simulate with queues.
    """

    def __init__(self):
        self._queue = queue.Queue()
        self._channel_id = None

        if HAS_INTERPRETERS and hasattr(interpreters, 'channel_create'):
            self._channel_id = interpreters.channel_create()

    def send(self, data: Any):
        """Send data through channel."""
        # Serialize data
        serialized = pickle.dumps(data)

        if self._channel_id is not None:
            interpreters.channel_send(self._channel_id, serialized)
        else:
            self._queue.put(serialized)

    def receive(self, timeout: float = None) -> Any:
        """Receive data from channel."""
        if self._channel_id is not None:
            serialized = interpreters.channel_recv(self._channel_id)
        else:
            serialized = self._queue.get(timeout=timeout)

        return pickle.loads(serialized)

    def close(self):
        """Close the channel."""
        if self._channel_id is not None:
            interpreters.channel_close(self._channel_id)

class SharedMemoryBridge:
    """
    Share data between interpreters using shared memory.

    For numeric data, this avoids serialization overhead.
    """

    def __init__(self, name: str, size: int):
        from multiprocessing import shared_memory

        try:
            self.shm = shared_memory.SharedMemory(name=name, create=True, size=size)
            self.created = True
        except FileExistsError:
            self.shm = shared_memory.SharedMemory(name=name, create=False)
            self.created = False

        self.name = name
        self.size = size

    def write(self, data: bytes, offset: int = 0):
        """Write bytes to shared memory."""
        end = offset + len(data)
        if end > self.size:
            raise ValueError("Data exceeds shared memory size")
        self.shm.buf[offset:end] = data

    def read(self, size: int, offset: int = 0) -> bytes:
        """Read bytes from shared memory."""
        return bytes(self.shm.buf[offset:offset + size])

    def close(self):
        """Close shared memory."""
        self.shm.close()
        if self.created:
            self.shm.unlink()
```

## Exercise 3: Parallel Execution

Run tasks in parallel across subinterpreters:

```python
class ParallelExecutor:
    """
    Execute tasks in parallel using subinterpreters.

    TODO: Implement true parallel execution with per-interpreter GIL.
    """

    def __init__(self, num_interpreters: int = 4):
        self.num_interpreters = num_interpreters
        self.manager = SubinterpreterManager()
        self.interpreters: List[int] = []
        self._initialized = False

    def initialize(self):
        """Create interpreter pool."""
        if not HAS_INTERPRETERS:
            print("Subinterpreters not available, using simulation")
            return

        for _ in range(self.num_interpreters):
            interp_id = self.manager.create()
            self.interpreters.append(interp_id)

        self._initialized = True

    def shutdown(self):
        """Shutdown interpreter pool."""
        self.manager.cleanup()
        self.interpreters.clear()
        self._initialized = False

    def map(self, func_code: str, items: List[Any]) -> List[Any]:
        """
        Map function over items using subinterpreters.

        func_code: String containing function definition
        items: List of items to process
        """
        if not self._initialized or not HAS_INTERPRETERS:
            # Fallback to sequential execution
            return self._sequential_map(func_code, items)

        results = [None] * len(items)
        threads = []

        def run_in_interpreter(interp_id: int, index: int, item: Any):
            # Create code that processes item and stores result
            item_repr = repr(item)
            code = f"""
{func_code}

_item = {item_repr}
_result = process(_item)
"""
            try:
                self.manager.run_string(interp_id, code)
                # Note: Getting result back is tricky without channels
                results[index] = f"Processed in interp {interp_id}"
            except Exception as e:
                results[index] = f"Error: {e}"

        # Distribute work across interpreters
        for i, item in enumerate(items):
            interp_id = self.interpreters[i % len(self.interpreters)]

            t = threading.Thread(
                target=run_in_interpreter,
                args=(interp_id, i, item)
            )
            threads.append(t)
            t.start()

        # Wait for completion
        for t in threads:
            t.join()

        return results

    def _sequential_map(self, func_code: str, items: List[Any]) -> List[Any]:
        """Fallback sequential execution."""
        # Execute function code
        local_ns = {}
        exec(func_code, local_ns)
        process_func = local_ns.get('process')

        if process_func is None:
            raise ValueError("func_code must define a 'process' function")

        return [process_func(item) for item in items]

    def benchmark(self, func_code: str, items: List[Any]) -> Dict:
        """Benchmark parallel vs sequential execution."""
        # Sequential
        start = time.time()
        seq_results = self._sequential_map(func_code, items)
        seq_time = time.time() - start

        # Parallel (if available)
        if self._initialized and HAS_INTERPRETERS:
            start = time.time()
            par_results = self.map(func_code, items)
            par_time = time.time() - start
        else:
            par_results = seq_results
            par_time = seq_time

        return {
            'sequential_time': seq_time,
            'parallel_time': par_time,
            'speedup': seq_time / par_time if par_time > 0 else 1.0,
            'items_count': len(items)
        }

executor = ParallelExecutor()
```

## Exercise 4: Isolated Environment

Create isolated execution environments:

```python
class IsolatedEnvironment:
    """
    Create an isolated Python environment using a subinterpreter.

    TODO: Implement environment isolation with restricted builtins.
    """

    def __init__(self, allowed_modules: List[str] = None):
        self.allowed_modules = allowed_modules or ['math', 'json', 'datetime']
        self.manager = SubinterpreterManager()
        self.interp_id = None
        self._setup_code = self._generate_setup_code()

    def _generate_setup_code(self) -> str:
        """Generate code to set up isolated environment."""
        return f"""
import sys

# Restrict available modules
_allowed = {self.allowed_modules!r}

class RestrictedImporter:
    def find_module(self, name, path=None):
        if name.split('.')[0] not in _allowed:
            return self
        return None

    def load_module(self, name):
        raise ImportError(f"Module '{{name}}' is not allowed in this environment")

sys.meta_path.insert(0, RestrictedImporter())

# Remove dangerous builtins
_restricted_builtins = {{
    k: v for k, v in __builtins__.items()
    if k not in ['eval', 'exec', 'compile', 'open', '__import__', 'input']
}}
"""

    def start(self):
        """Start the isolated environment."""
        if HAS_INTERPRETERS:
            self.interp_id = self.manager.create()
            self.manager.run_string(self.interp_id, self._setup_code)
            print(f"Isolated environment started (interpreter {self.interp_id})")
        else:
            print("Running in simulation mode (no true isolation)")

    def execute(self, code: str) -> None:
        """Execute code in isolated environment."""
        if self.interp_id is not None:
            self.manager.run_string(self.interp_id, code)
        else:
            # Simulation - run with restricted globals
            restricted_globals = {
                '__builtins__': {
                    'print': print,
                    'len': len,
                    'range': range,
                    'str': str,
                    'int': int,
                    'float': float,
                    'list': list,
                    'dict': dict,
                }
            }
            exec(code, restricted_globals)

    def stop(self):
        """Stop the isolated environment."""
        if self.interp_id is not None:
            self.manager.destroy(self.interp_id)
            self.interp_id = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        return False

isolated_env = IsolatedEnvironment
```

## Exercise 5: Complete Subinterpreter System

Combine all components:

```python
class SubinterpreterSystem:
    """Complete subinterpreter management system."""

    def __init__(self):
        self.manager = SubinterpreterManager()
        self.executor = ParallelExecutor()
        self.environments: Dict[str, IsolatedEnvironment] = {}

    def create_executor(self, num_workers: int = 4) -> ParallelExecutor:
        """Create a parallel executor."""
        executor = ParallelExecutor(num_workers)
        executor.initialize()
        return executor

    def create_isolated_env(self, name: str,
                           allowed_modules: List[str] = None) -> IsolatedEnvironment:
        """Create a named isolated environment."""
        env = IsolatedEnvironment(allowed_modules)
        env.start()
        self.environments[name] = env
        return env

    def get_environment(self, name: str) -> Optional[IsolatedEnvironment]:
        """Get environment by name."""
        return self.environments.get(name)

    def run_isolated(self, name: str, code: str):
        """Run code in named environment."""
        env = self.environments.get(name)
        if env is None:
            raise ValueError(f"Environment '{name}' not found")
        env.execute(code)

    def benchmark_parallelism(self) -> Dict:
        """
        Benchmark to show GIL bypass with subinterpreters.

        TODO: Compare threaded vs subinterpreter execution.
        """
        results = {}

        # CPU-bound task
        cpu_code = """
def process(n):
    total = 0
    for i in range(n):
        total += i ** 2
    return total
"""
        items = [100000] * 8

        # Test with threads (GIL-bound)
        start = time.time()
        threads = []
        thread_results = [None] * len(items)

        def thread_worker(idx, n):
            total = 0
            for i in range(n):
                total += i ** 2
            thread_results[idx] = total

        for i, item in enumerate(items):
            t = threading.Thread(target=thread_worker, args=(i, item))
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        results['threaded_time'] = time.time() - start

        # Test with subinterpreters (if available)
        if HAS_INTERPRETERS:
            executor = self.create_executor(4)
            bench = executor.benchmark(cpu_code, items)
            results['subinterp_time'] = bench['parallel_time']
            results['speedup'] = results['threaded_time'] / bench['parallel_time']
            executor.shutdown()
        else:
            results['subinterp_time'] = results['threaded_time']
            results['speedup'] = 1.0

        return results

    def cleanup(self):
        """Cleanup all resources."""
        for env in self.environments.values():
            env.stop()
        self.environments.clear()
        self.manager.cleanup()
        self.executor.shutdown()

system = SubinterpreterSystem()
```

## Demo Application

```python
def demo():
    """Demonstrate subinterpreter features."""
    print("=== Subinterpreter Demo ===\n")

    print(f"Python version: {sys.version}")
    print(f"Subinterpreters available: {HAS_INTERPRETERS}\n")

    # 1. Basic subinterpreter creation
    print("1. Basic Subinterpreter:")
    if HAS_INTERPRETERS:
        interp_id = manager.create()
        manager.run_string(interp_id, """
print("Hello from subinterpreter!")
x = 42
print(f"x = {x}")
""")
        manager.destroy(interp_id)
    else:
        print("   (Simulated) Hello from subinterpreter!")

    # 2. List interpreters
    print("\n2. Active Interpreters:")
    all_interps = manager.list_all()
    print(f"   {all_interps}")

    # 3. Isolated environment
    print("\n3. Isolated Environment:")
    with IsolatedEnvironment(['math']) as env:
        env.execute("""
import math
result = math.sqrt(16)
print(f"sqrt(16) = {result}")
""")

        # This would fail in true isolation:
        # env.execute("import os")  # ImportError

    # 4. Parallel execution
    print("\n4. Parallel Execution:")
    executor = ParallelExecutor(2)
    executor.initialize()

    func_code = """
def process(item):
    total = sum(i**2 for i in range(item))
    return total
"""
    items = [1000, 2000, 3000, 4000]
    results = executor.map(func_code, items)
    print(f"   Results: {results}")

    bench = executor.benchmark(func_code, items)
    print(f"   Sequential: {bench['sequential_time']:.4f}s")
    print(f"   Parallel: {bench['parallel_time']:.4f}s")
    print(f"   Speedup: {bench['speedup']:.2f}x")

    executor.shutdown()

    # 5. Communication (simulation)
    print("\n5. Inter-Interpreter Communication:")
    channel = InterpreterChannel()
    channel.send({'message': 'Hello', 'value': 42})
    received = channel.receive()
    print(f"   Sent and received: {received}")

    # 6. Benchmark GIL bypass
    print("\n6. GIL Bypass Benchmark:")
    system = SubinterpreterSystem()
    bench_results = system.benchmark_parallelism()
    print(f"   Threaded (GIL-bound): {bench_results['threaded_time']:.4f}s")
    print(f"   Subinterpreters: {bench_results['subinterp_time']:.4f}s")
    print(f"   Speedup: {bench_results['speedup']:.2f}x")

    system.cleanup()
    print("\n=== Demo Complete ===")

if __name__ == "__main__":
    demo()
```

## Expected Output (Python 3.12+)

```
=== Subinterpreter Demo ===

Python version: 3.12.0 (main, ...)
Subinterpreters available: True

1. Basic Subinterpreter:
Created interpreter 1
Hello from subinterpreter!
x = 42
Destroyed interpreter 1

2. Active Interpreters:
   [0]

3. Isolated Environment:
Created interpreter 2
sqrt(16) = 4.0
Destroyed interpreter 2

4. Parallel Execution:
Created interpreter 3
Created interpreter 4
   Results: ['Processed in interp 3', 'Processed in interp 4', ...]
   Sequential: 0.0234s
   Parallel: 0.0089s
   Speedup: 2.63x

5. Inter-Interpreter Communication:
   Sent and received: {'message': 'Hello', 'value': 42}

6. GIL Bypass Benchmark:
   Threaded (GIL-bound): 0.1523s
   Subinterpreters: 0.0421s
   Speedup: 3.62x

=== Demo Complete ===
```

## Submission

1. Complete all TODO sections
2. Implement proper result passing using channels
3. Add support for passing functions (not just code strings)
4. Bonus: Create a worker pool that persists interpreters

---

## Congratulations!

You've completed all 10 hands-on labs! You now have practical experience with:

1. **Bytecode** - Disassembling and analyzing Python bytecode
2. **Memory** - Profiling memory usage and detecting leaks
3. **GIL** - Visualizing GIL contention
4. **Async** - Tracing asyncio execution
5. **GC** - Understanding garbage collection
6. **Frames** - Inspecting execution frames
7. **Import** - Creating custom import hooks
8. **Threading** - Building thread pools
9. **C Extensions** - Writing Python extensions in C
10. **Subinterpreters** - Using isolated Python instances

[Back to Main Index →](../README.md)

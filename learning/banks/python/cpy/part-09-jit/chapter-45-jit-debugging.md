# Chapter 45: JIT Debugging and Profiling

## 45.1 Debugging JIT-Compiled Code

Debugging JIT code presents unique challenges:

```
┌─────────────────────────────────────────────────────────────────┐
│              JIT Debugging Challenges                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Challenge 1: Code doesn't exist on disk                        │
│  • JIT code is generated at runtime                             │
│  • Standard debuggers can't find source                         │
│                                                                  │
│  Challenge 2: Optimization obscures logic                       │
│  • Variables may be optimized away                              │
│  • Control flow may be different                                │
│  • Inlining changes call stack                                   │
│                                                                  │
│  Challenge 3: Deoptimization                                     │
│  • Execution may switch between tiers                           │
│  • Breakpoints need to work in both                             │
│                                                                  │
│  Challenge 4: Type specialization                               │
│  • Multiple code versions for same function                     │
│  • Which version is executing?                                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 45.2 Disabling JIT for Debugging

### Environment Variables

```bash
# Disable JIT entirely
PYTHON_JIT=0 python script.py

# Or run with interpreter only
python -X jit=0 script.py

# Enable JIT but with debugging info
PYTHON_JIT_DEBUG=1 python script.py
```

### Programmatic Control

```python
import sys

# Check if JIT can be controlled
if hasattr(sys, '_jit'):
    # Disable JIT
    sys._jit.disable()

    # Run code in interpreter only
    problematic_function()

    # Re-enable JIT
    sys._jit.enable()
```

## 45.3 JIT Dump and Inspection

### Dumping Generated Code

```bash
# Dump JIT code to files
PYTHON_JIT_DUMP=1 python script.py

# Output:
# jit_dump/function_name_0x12345678.bin  (machine code)
# jit_dump/function_name_0x12345678.txt  (disassembly)
```

### Examining JIT Output

```python
import sys
import dis

def example_function(a, b):
    return a + b * 2

# Force JIT compilation
for _ in range(1000):
    example_function(1, 2)

# Get JIT info
if hasattr(sys, '_jit_code'):
    code_obj = example_function.__code__
    jit_info = sys._jit_code(code_obj)

    print(f"JIT compiled: {jit_info['compiled']}")
    print(f"Code address: {hex(jit_info['address'])}")
    print(f"Code size: {jit_info['size']} bytes")

    # Disassemble with objdump (if dump file exists)
    # objdump -b binary -m i386:x86-64 -D jit_dump/example_function.bin
```

### Using `dis` Module

```python
import dis
import sys

def analyze_jit_candidates(func):
    """Analyze bytecode for JIT compilation."""
    code = func.__code__

    print(f"Function: {func.__name__}")
    print(f"Bytecode size: {len(code.co_code)} bytes")
    print()

    # Show bytecode
    dis.dis(func)
    print()

    # Show specialized instructions (3.11+)
    if hasattr(dis, 'show_cache'):
        print("Specialized bytecode:")
        dis.dis(func, adaptive=True)
```

## 45.4 Profiling JIT Performance

### JIT Timing Analysis

```python
import time
import sys

def profile_jit_warmup(func, *args, iterations=1000):
    """Profile function warmup behavior."""

    # Cold execution (interpreter)
    cold_times = []
    for i in range(10):
        start = time.perf_counter()
        func(*args)
        cold_times.append(time.perf_counter() - start)

    # Warmup phase
    warmup_times = []
    for i in range(iterations):
        start = time.perf_counter()
        func(*args)
        warmup_times.append(time.perf_counter() - start)

    # Hot execution (JIT)
    hot_times = []
    for i in range(100):
        start = time.perf_counter()
        func(*args)
        hot_times.append(time.perf_counter() - start)

    print(f"Cold (interpreter): {sum(cold_times)/len(cold_times)*1e6:.2f} µs avg")
    print(f"Hot (JIT): {sum(hot_times)/len(hot_times)*1e6:.2f} µs avg")
    print(f"Speedup: {(sum(cold_times)/len(cold_times)) / (sum(hot_times)/len(hot_times)):.1f}x")

    return cold_times, warmup_times, hot_times

# Example
def compute(n):
    total = 0
    for i in range(n):
        total += i * i
    return total

profile_jit_warmup(compute, 1000)
```

### Visualizing Warmup

```python
import matplotlib.pyplot as plt

def plot_warmup(warmup_times, threshold=100):
    """Plot warmup behavior."""
    plt.figure(figsize=(12, 4))

    plt.subplot(1, 2, 1)
    plt.plot(warmup_times)
    plt.axvline(x=threshold, color='r', linestyle='--', label='JIT threshold')
    plt.xlabel('Iteration')
    plt.ylabel('Time (s)')
    plt.title('Warmup Profile')
    plt.legend()

    plt.subplot(1, 2, 2)
    plt.hist(warmup_times[:threshold], bins=20, alpha=0.5, label='Before JIT')
    plt.hist(warmup_times[threshold:], bins=20, alpha=0.5, label='After JIT')
    plt.xlabel('Time (s)')
    plt.ylabel('Count')
    plt.title('Time Distribution')
    plt.legend()

    plt.tight_layout()
    plt.savefig('warmup_profile.png')
    plt.show()
```

## 45.5 Deoptimization Tracking

### Monitoring Deopts

```python
import sys

def track_deoptimizations(func, *args, iterations=10000):
    """Track deoptimization events."""

    deopt_count = 0

    # Monkey-patch to track deopts (if supported)
    if hasattr(sys, '_jit_deopt_hook'):
        def deopt_hook(code, reason):
            nonlocal deopt_count
            deopt_count += 1
            print(f"Deopt #{deopt_count}: {reason}")

        sys._jit_deopt_hook = deopt_hook

    # Run function
    for i in range(iterations):
        func(*args)

    print(f"Total deoptimizations: {deopt_count}")
    return deopt_count

# Example: Polymorphic code causes deopts
def polymorphic_add(a, b):
    return a + b

# Mixed types cause deoptimization
track_deoptimizations(
    lambda: [
        polymorphic_add(1, 2),
        polymorphic_add("a", "b"),
        polymorphic_add(1.0, 2.0),
    ]
)
```

### Deopt Analysis

```python
import sys

def analyze_deopt_reasons():
    """Analyze common deoptimization reasons."""

    if not hasattr(sys, '_jit_stats'):
        print("JIT stats not available")
        return

    stats = sys._jit_stats()

    reasons = {
        'type_guard_fail': 'Type changed from expected',
        'bounds_check_fail': 'Array/sequence out of bounds',
        'attribute_error': 'Attribute access failed',
        'overflow': 'Numeric overflow',
        'side_effect': 'Unexpected side effect detected',
    }

    print("Deoptimization reasons:")
    for reason, description in reasons.items():
        count = stats.get(f'deopt_{reason}', 0)
        if count > 0:
            print(f"  {reason}: {count} ({description})")
```

## 45.6 Using GDB with JIT

### GDB JIT Interface

```bash
# Python can register JIT code with GDB
# Requires Python built with debug symbols

# Run Python under GDB
gdb python

# Inside GDB:
(gdb) run -c "
def hot_function(n):
    total = 0
    for i in range(n):
        total += i
    return total

for _ in range(1000):
    hot_function(100)

# Now set breakpoint in JIT code
"

# GDB commands for JIT debugging
(gdb) info functions jit_  # Show JIT functions (if registered)
(gdb) disassemble 0x7fff12345678  # Disassemble JIT code at address
```

### LLDB Alternative

```bash
# Similar debugging with LLDB (macOS)
lldb python

# Inside LLDB:
(lldb) run script.py
(lldb) process interrupt

# Examine JIT code
(lldb) disassemble --start-address 0x12345678 --count 50
```

## 45.7 Performance Counters

### Hardware Performance Monitoring

```python
import subprocess
import tempfile

def profile_with_perf(func, *args, iterations=10000):
    """Profile function with Linux perf."""

    # Create test script
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(f"""
import sys
sys.path.insert(0, '.')
from {func.__module__} import {func.__name__}

for _ in range({iterations}):
    {func.__name__}(*{args!r})
""")
        script = f.name

    # Run with perf
    result = subprocess.run(
        ['perf', 'stat', '-e',
         'cycles,instructions,cache-misses,branch-misses',
         'python', script],
        capture_output=True,
        text=True
    )

    print(result.stderr)

# Example
def compute(n):
    return sum(i*i for i in range(n))

# profile_with_perf(compute, 1000)  # Requires Linux with perf
```

### Python-Level Profiling

```python
import cProfile
import pstats
import io

def profile_jit_impact(func, *args):
    """Compare profiling with and without JIT."""

    def run_many(iterations):
        for _ in range(iterations):
            func(*args)

    # Profile with JIT disabled
    import os
    os.environ['PYTHON_JIT'] = '0'

    pr_no_jit = cProfile.Profile()
    pr_no_jit.enable()
    run_many(10000)
    pr_no_jit.disable()

    # Profile with JIT enabled
    os.environ['PYTHON_JIT'] = '1'

    # Warmup
    run_many(1000)

    pr_jit = cProfile.Profile()
    pr_jit.enable()
    run_many(10000)
    pr_jit.disable()

    # Compare
    print("Without JIT:")
    stats = pstats.Stats(pr_no_jit)
    stats.strip_dirs().sort_stats('cumulative').print_stats(10)

    print("\nWith JIT:")
    stats = pstats.Stats(pr_jit)
    stats.strip_dirs().sort_stats('cumulative').print_stats(10)
```

## 45.8 Memory Analysis

### JIT Code Memory Usage

```python
import sys

def analyze_jit_memory():
    """Analyze memory used by JIT code."""

    if not hasattr(sys, '_jit_stats'):
        print("JIT stats not available")
        return

    stats = sys._jit_stats()

    print("JIT Memory Usage:")
    print(f"  Code memory: {stats.get('code_bytes', 0) / 1024:.1f} KB")
    print(f"  Metadata: {stats.get('metadata_bytes', 0) / 1024:.1f} KB")
    print(f"  Templates: {stats.get('template_bytes', 0) / 1024:.1f} KB")
    print(f"  Total: {stats.get('total_jit_bytes', 0) / 1024:.1f} KB")
    print()
    print(f"  Compiled functions: {stats.get('compiled_count', 0)}")
    print(f"  Avg code size: {stats.get('code_bytes', 0) / max(stats.get('compiled_count', 1), 1):.0f} bytes/func")

# Compare with process memory
import resource
def get_memory_usage():
    """Get current process memory usage."""
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024  # KB

print(f"Process memory: {get_memory_usage():.0f} KB")
analyze_jit_memory()
```

## 45.9 Testing JIT Correctness

### Differential Testing

```python
import sys
import random

def test_jit_correctness(func, input_generator, iterations=1000):
    """Test that JIT produces same results as interpreter."""

    errors = []

    for i in range(iterations):
        args = input_generator()

        # Run in interpreter mode
        sys._jit.disable() if hasattr(sys, '_jit') else None
        try:
            result_interp = func(*args)
        except Exception as e:
            result_interp = ('exception', type(e).__name__)

        # Run in JIT mode
        sys._jit.enable() if hasattr(sys, '_jit') else None
        try:
            result_jit = func(*args)
        except Exception as e:
            result_jit = ('exception', type(e).__name__)

        # Compare
        if result_interp != result_jit:
            errors.append({
                'args': args,
                'interpreter': result_interp,
                'jit': result_jit
            })

    if errors:
        print(f"Found {len(errors)} mismatches!")
        for e in errors[:5]:
            print(f"  args={e['args']}: interp={e['interpreter']}, jit={e['jit']}")
    else:
        print(f"All {iterations} tests passed!")

    return errors

# Example
def arithmetic(a, b, c):
    return (a + b) * c - (a / max(b, 1))

test_jit_correctness(
    arithmetic,
    lambda: (random.randint(-100, 100),
             random.randint(-100, 100),
             random.randint(-100, 100))
)
```

### Stress Testing

```python
import threading
import random

def stress_test_jit(func, input_generator, threads=4, iterations=10000):
    """Stress test JIT under concurrent execution."""

    errors = []
    lock = threading.Lock()

    def worker():
        for _ in range(iterations // threads):
            args = input_generator()
            try:
                result = func(*args)
            except Exception as e:
                with lock:
                    errors.append({'args': args, 'error': str(e)})

    thread_list = [threading.Thread(target=worker) for _ in range(threads)]

    for t in thread_list:
        t.start()
    for t in thread_list:
        t.join()

    print(f"Completed with {len(errors)} errors")
    return errors
```

## 45.10 Best Practices

### Debugging Checklist

```
┌─────────────────────────────────────────────────────────────────┐
│              JIT Debugging Checklist                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Reproduce with JIT disabled                                  │
│     □ Does bug exist without JIT?                               │
│     □ If yes: Not a JIT bug                                     │
│     □ If no: Likely JIT bug                                     │
│                                                                  │
│  2. Isolate the problem                                          │
│     □ Find minimal reproducing case                             │
│     □ Identify which function is affected                       │
│     □ Check for type instability                                │
│                                                                  │
│  3. Gather information                                           │
│     □ Get bytecode (dis.dis)                                    │
│     □ Get JIT code (if dump available)                          │
│     □ Check specialization state                                │
│                                                                  │
│  4. Analyze                                                      │
│     □ Look for guard failures                                   │
│     □ Check deoptimization reasons                              │
│     □ Verify type assumptions                                   │
│                                                                  │
│  5. Report                                                       │
│     □ Include Python version                                    │
│     □ Include minimal reproducer                                │
│     □ Include bytecode/JIT dump                                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Summary

- **Disable JIT** for debugging with `PYTHON_JIT=0`
- **JIT dumps** show generated machine code
- **Warmup profiling** reveals JIT impact
- **Deoptimization tracking** identifies type instability
- **GDB/LLDB** can debug JIT code (with effort)
- **Differential testing** verifies JIT correctness
- **Performance counters** measure hardware-level behavior

## Practice Exercises

1. Profile warmup behavior of your hot functions
2. Identify causes of deoptimization in polymorphic code
3. Compare memory usage with and without JIT
4. Create a differential test suite for critical functions

---

[← Previous: JIT Tier System](chapter-44-jit-tiers.md) | [Next: Thread Creation and Lifecycle →](../part-10-threading/chapter-46-thread-lifecycle.md)

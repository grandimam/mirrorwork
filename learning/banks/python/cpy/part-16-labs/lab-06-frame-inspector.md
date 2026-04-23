# Lab 6: Frame Inspector

## Objective

Build a tool to inspect Python stack frames, analyze call stacks, and extract execution context for debugging.

## Prerequisites

- Understanding of Python Virtual Machine (Part 3)
- Knowledge of frame objects and execution model

## Lab Setup

```python
# lab06_frame_inspector.py
import sys
import types
import traceback
import dis
import inspect
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
```

## Exercise 1: Frame Data Extractor

Extract comprehensive data from frame objects:

```python
@dataclass
class FrameData:
    """Comprehensive frame information."""
    filename: str
    function_name: str
    line_number: int
    local_vars: Dict[str, Any]
    global_vars: Dict[str, str]  # Just names, to avoid huge output
    code_context: List[str]
    bytecode_offset: int
    stack_depth: int

class FrameExtractor:
    """Extract information from frame objects."""

    def extract(self, frame: types.FrameType) -> FrameData:
        """
        TODO: Extract all relevant information from a frame.

        Use frame attributes: f_code, f_locals, f_globals, f_lineno, etc.
        """
        code = frame.f_code

        # Get code context
        try:
            lines, start_line = inspect.getsourcelines(frame)
            current_offset = frame.f_lineno - start_line
            context_start = max(0, current_offset - 2)
            context_end = min(len(lines), current_offset + 3)
            code_context = lines[context_start:context_end]
        except:
            code_context = []

        # Calculate stack depth
        depth = 0
        f = frame
        while f is not None:
            depth += 1
            f = f.f_back

        return FrameData(
            filename=code.co_filename,
            function_name=code.co_name,
            line_number=frame.f_lineno,
            local_vars=dict(frame.f_locals),
            global_vars=list(frame.f_globals.keys()),
            code_context=code_context,
            bytecode_offset=frame.f_lasti,
            stack_depth=depth
        )

    def format_frame(self, data: FrameData) -> str:
        """Format frame data for display."""
        lines = [
            f"Frame: {data.function_name}",
            f"  File: {data.filename}:{data.line_number}",
            f"  Stack depth: {data.stack_depth}",
            f"  Bytecode offset: {data.bytecode_offset}",
            "",
            "  Local variables:"
        ]

        for name, value in list(data.local_vars.items())[:10]:
            value_str = repr(value)[:50]
            lines.append(f"    {name} = {value_str}")

        if data.code_context:
            lines.append("")
            lines.append("  Code context:")
            for i, line in enumerate(data.code_context):
                marker = ">>>" if i == 2 else "   "
                lines.append(f"    {marker} {line.rstrip()}")

        return '\n'.join(lines)

extractor = FrameExtractor()
```

## Exercise 2: Call Stack Analyzer

Analyze the complete call stack:

```python
class CallStackAnalyzer:
    """Analyze Python call stacks."""

    def __init__(self):
        self.extractor = FrameExtractor()

    def capture_stack(self, frame: types.FrameType = None) -> List[FrameData]:
        """
        TODO: Capture complete call stack.

        Walk up the frame chain using f_back until None.
        """
        if frame is None:
            frame = sys._getframe(1)

        stack = []
        current = frame

        while current is not None:
            data = self.extractor.extract(current)
            stack.append(data)
            current = current.f_back

        return stack

    def format_stack(self, stack: List[FrameData]) -> str:
        """Format stack trace nicely."""
        lines = ["Call Stack (most recent first):", "=" * 60]

        for i, frame_data in enumerate(stack):
            lines.append(f"\n[{i}] {frame_data.function_name}")
            lines.append(f"    {frame_data.filename}:{frame_data.line_number}")

            # Show locals summary
            if frame_data.local_vars:
                var_summary = ', '.join(f"{k}={repr(v)[:20]}"
                                       for k, v in list(frame_data.local_vars.items())[:3])
                lines.append(f"    Locals: {var_summary}")

        return '\n'.join(lines)

    def find_variable(self, name: str, frame: types.FrameType = None) -> Optional[tuple]:
        """
        Find a variable by name in the call stack.

        Returns (value, frame_index) or None.
        """
        if frame is None:
            frame = sys._getframe(1)

        stack = self.capture_stack(frame)

        for i, frame_data in enumerate(stack):
            if name in frame_data.local_vars:
                return (frame_data.local_vars[name], i)

        return None

    def get_caller_info(self, levels_up: int = 1) -> Dict:
        """Get information about caller N levels up."""
        frame = sys._getframe(levels_up + 1)
        data = self.extractor.extract(frame)

        return {
            'function': data.function_name,
            'file': data.filename,
            'line': data.line_number,
            'locals': data.local_vars
        }

stack_analyzer = CallStackAnalyzer()
```

## Exercise 3: Execution Tracer

Trace function execution:

```python
class ExecutionTracer:
    """Trace function execution with frame inspection."""

    def __init__(self):
        self.trace_log: List[dict] = []
        self.call_depth = 0
        self.enabled = False

    def trace_function(self, frame: types.FrameType, event: str, arg: Any):
        """
        TODO: Implement trace function for sys.settrace.

        Handle events: 'call', 'return', 'line', 'exception'
        """
        if not self.enabled:
            return None

        code = frame.f_code

        # Skip internal/library code
        if 'site-packages' in code.co_filename or '<' in code.co_filename:
            return self.trace_function

        entry = {
            'event': event,
            'function': code.co_name,
            'file': code.co_filename,
            'line': frame.f_lineno,
            'depth': self.call_depth,
        }

        if event == 'call':
            self.call_depth += 1
            entry['args'] = {k: repr(v)[:50] for k, v in frame.f_locals.items()}

        elif event == 'return':
            entry['return_value'] = repr(arg)[:100]
            self.call_depth = max(0, self.call_depth - 1)

        elif event == 'exception':
            entry['exception'] = str(arg[1])

        elif event == 'line':
            # Capture current locals
            entry['locals'] = {k: repr(v)[:30] for k, v in frame.f_locals.items()}

        self.trace_log.append(entry)

        return self.trace_function

    def start(self):
        """Start tracing."""
        self.enabled = True
        self.trace_log.clear()
        self.call_depth = 0
        sys.settrace(self.trace_function)
        print("Tracing started")

    def stop(self):
        """Stop tracing."""
        sys.settrace(None)
        self.enabled = False
        print("Tracing stopped")

    def report(self, max_entries: int = 50):
        """Print execution trace."""
        print("\nExecution Trace:")
        print("=" * 70)

        for entry in self.trace_log[:max_entries]:
            indent = "  " * entry['depth']
            event = entry['event']

            if event == 'call':
                print(f"{indent}→ {entry['function']}()")

            elif event == 'return':
                ret = entry.get('return_value', '')
                print(f"{indent}← {entry['function']} = {ret}")

            elif event == 'line':
                print(f"{indent}  line {entry['line']}")

            elif event == 'exception':
                print(f"{indent}✗ {entry['exception']}")

        if len(self.trace_log) > max_entries:
            print(f"\n... and {len(self.trace_log) - max_entries} more entries")

tracer = ExecutionTracer()
```

## Exercise 4: Frame Manipulator

Manipulate frame state (for debugging):

```python
class FrameManipulator:
    """Manipulate frame state for debugging."""

    def __init__(self):
        self.breakpoints: Dict[str, int] = {}  # filename:line -> count
        self.watches: List[str] = []

    def set_local(self, frame: types.FrameType, name: str, value: Any) -> bool:
        """
        TODO: Set a local variable in a frame.

        Note: This is tricky because f_locals may not directly modify locals.
        Use ctypes for CPython-specific manipulation.
        """
        try:
            frame.f_locals[name] = value
            # Force update of fast locals
            import ctypes
            ctypes.pythonapi.PyFrame_LocalsToFast(
                ctypes.py_object(frame),
                ctypes.c_int(0)
            )
            return True
        except Exception as e:
            print(f"Failed to set local: {e}")
            return False

    def add_breakpoint(self, filename: str, line: int):
        """Add a breakpoint."""
        key = f"{filename}:{line}"
        self.breakpoints[key] = 0
        print(f"Breakpoint added at {key}")

    def add_watch(self, expression: str):
        """Add a watch expression."""
        self.watches.append(expression)
        print(f"Watching: {expression}")

    def evaluate_in_frame(self, frame: types.FrameType, expression: str) -> Any:
        """Evaluate expression in frame's context."""
        try:
            return eval(expression, frame.f_globals, frame.f_locals)
        except Exception as e:
            return f"Error: {e}"

    def check_breakpoint(self, frame: types.FrameType) -> bool:
        """Check if current position is a breakpoint."""
        code = frame.f_code
        key = f"{code.co_filename}:{frame.f_lineno}"
        return key in self.breakpoints

    def display_watches(self, frame: types.FrameType):
        """Display all watch expressions."""
        if not self.watches:
            return

        print("\nWatch values:")
        for expr in self.watches:
            value = self.evaluate_in_frame(frame, expr)
            print(f"  {expr} = {value}")

manipulator = FrameManipulator()
```

## Exercise 5: Complete Frame Inspector

Combine all components:

```python
class FrameInspector:
    """Complete frame inspection tool."""

    def __init__(self):
        self.extractor = FrameExtractor()
        self.stack_analyzer = CallStackAnalyzer()
        self.tracer = ExecutionTracer()
        self.manipulator = FrameManipulator()
        self._debugging = False

    def inspect_current(self, levels_up: int = 1):
        """Inspect current execution context."""
        frame = sys._getframe(levels_up)
        data = self.extractor.extract(frame)
        print(self.extractor.format_frame(data))

    def show_stack(self):
        """Show current call stack."""
        frame = sys._getframe(1)
        stack = self.stack_analyzer.capture_stack(frame)
        print(self.stack_analyzer.format_stack(stack))

    def debug_break(self):
        """
        TODO: Interactive debugger break point.

        Allow user to inspect frame, evaluate expressions, etc.
        """
        frame = sys._getframe(1)
        data = self.extractor.extract(frame)

        print("\n" + "=" * 60)
        print("DEBUG BREAK")
        print("=" * 60)
        print(self.extractor.format_frame(data))

        # Display watches
        self.manipulator.display_watches(frame)

        print("\nCommands: 'c'=continue, 's'=stack, 'l'=locals, 'q'=quit")
        print("Or enter expression to evaluate")

        while True:
            try:
                cmd = input("debug> ").strip()

                if cmd == 'c':
                    break
                elif cmd == 's':
                    self.show_stack()
                elif cmd == 'l':
                    for k, v in frame.f_locals.items():
                        print(f"  {k} = {repr(v)[:60]}")
                elif cmd == 'q':
                    sys.exit(0)
                elif cmd:
                    result = self.manipulator.evaluate_in_frame(frame, cmd)
                    print(f"  => {result}")
            except EOFError:
                break
            except Exception as e:
                print(f"  Error: {e}")

    def trace_function(self, func):
        """Decorator to trace a function."""
        def wrapper(*args, **kwargs):
            self.tracer.start()
            try:
                return func(*args, **kwargs)
            finally:
                self.tracer.stop()
                self.tracer.report()
        return wrapper

    def profile_frame_usage(self, func, *args, **kwargs):
        """
        Profile frame creation and usage.
        """
        frame_count = [0]
        max_depth = [0]

        def counting_trace(frame, event, arg):
            if event == 'call':
                frame_count[0] += 1
                depth = 0
                f = frame
                while f:
                    depth += 1
                    f = f.f_back
                max_depth[0] = max(max_depth[0], depth)
            return counting_trace

        old_trace = sys.gettrace()
        sys.settrace(counting_trace)

        try:
            result = func(*args, **kwargs)
        finally:
            sys.settrace(old_trace)

        print(f"\nFrame Profile:")
        print(f"  Total frames created: {frame_count[0]}")
        print(f"  Maximum stack depth: {max_depth[0]}")

        return result

inspector = FrameInspector()
```

## Demo Application

```python
# Demo application to inspect

def factorial(n: int) -> int:
    """Calculate factorial recursively."""
    if n <= 1:
        # Uncomment to use debug break
        # inspector.debug_break()
        return 1
    return n * factorial(n - 1)

def fibonacci(n: int) -> int:
    """Calculate fibonacci number."""
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)

def complex_function(x: int, y: int) -> int:
    """A complex function for demonstration."""
    a = x + y
    b = x * y

    if a > b:
        result = a
    else:
        result = b

    # Show current frame
    inspector.inspect_current()

    return result

def demo():
    """Run demonstrations."""
    print("=== Frame Inspector Demo ===\n")

    # 1. Inspect current frame
    print("1. Inspecting current frame:")
    complex_function(5, 3)

    # 2. Show call stack
    print("\n2. Call stack from nested function:")

    def level3():
        inspector.show_stack()

    def level2():
        local_var = "in level2"
        level3()

    def level1():
        local_var = "in level1"
        level2()

    level1()

    # 3. Trace execution
    print("\n3. Tracing factorial(5):")

    @inspector.trace_function
    def traced_factorial(n):
        return factorial(n)

    traced_factorial(5)

    # 4. Profile frame usage
    print("\n4. Profiling fibonacci(10):")
    inspector.profile_frame_usage(fibonacci, 10)

    # 5. Find variable in stack
    print("\n5. Finding variable in stack:")

    def outer():
        target_var = "found me!"

        def inner():
            result = stack_analyzer.find_variable('target_var')
            if result:
                print(f"  Found target_var = '{result[0]}' at depth {result[1]}")

        inner()

    outer()

if __name__ == "__main__":
    demo()
```

## Expected Output

```
=== Frame Inspector Demo ===

1. Inspecting current frame:
Frame: complex_function
  File: lab06_frame_inspector.py:245
  Stack depth: 3
  Bytecode offset: 42

  Local variables:
    x = 5
    y = 3
    a = 8
    b = 15
    result = 15

  Code context:
       result = b

   >>> inspector.inspect_current()

       return result

2. Call stack from nested function:
Call Stack (most recent first):
============================================================

[0] level3
    lab06_frame_inspector.py:260
    Locals:

[1] level2
    lab06_frame_inspector.py:264
    Locals: local_var='in level2'

[2] level1
    lab06_frame_inspector.py:268
    Locals: local_var='in level1'
```

## Submission

1. Complete all TODO sections
2. Add support for async frame inspection
3. Implement conditional breakpoints
4. Bonus: Create a TUI debugger interface

---

[Next: Lab 7 - Import Hooks →](lab-07-import-hooks.md)

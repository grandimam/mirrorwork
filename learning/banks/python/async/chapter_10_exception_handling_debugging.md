# Chapter 10: Exception Handling and Debugging

## 10.1 Exception Propagation in Coroutines

Understanding how exceptions flow through async code is crucial for building robust applications. Exception handling in asyncio has unique characteristics that differ from synchronous code.

### Basic Exception Propagation

```python
import asyncio
import traceback
import logging

async def demonstrate_basic_exception_propagation():
    """Demonstrate how exceptions propagate through coroutines"""
    
    print("=== Basic Exception Propagation ===")
    
    async def failing_coroutine():
        """Coroutine that raises an exception"""
        print("   Failing coroutine: Starting...")
        await asyncio.sleep(0.1)
        print("   Failing coroutine: About to fail")
        raise ValueError("This is a test exception")
    
    async def calling_coroutine():
        """Coroutine that calls the failing coroutine"""
        print("   Calling coroutine: Starting...")
        try:
            result = await failing_coroutine()
            print(f"   Calling coroutine: Got result: {result}")
        except ValueError as e:
            print(f"   Calling coroutine: Caught exception: {e}")
            raise RuntimeError("Re-raised with additional context") from e
    
    async def top_level_coroutine():
        """Top-level coroutine that handles the chain"""
        print("   Top-level coroutine: Starting...")
        try:
            await calling_coroutine()
            print("   Top-level coroutine: Success")
        except RuntimeError as e:
            print(f"   Top-level coroutine: Final catch: {e}")
            print(f"   Original cause: {e.__cause__}")
            return "handled"
    
    print("1. Exception chain through coroutines:")
    result = await top_level_coroutine()
    print(f"   Final result: {result}")
    
    print("\n2. Unhandled exception in coroutine:")
    try:
        await failing_coroutine()
    except ValueError as e:
        print(f"   Caught at top level: {e}")
        print("   Traceback:")
        traceback.print_exc()

asyncio.run(demonstrate_basic_exception_propagation())
```

### Exception Context and Chaining

```python
import asyncio
import traceback

async def demonstrate_exception_chaining():
    """Demonstrate exception chaining and context in async code"""
    
    print("=== Exception Chaining and Context ===")
    
    async def database_operation():
        """Simulate database operation that fails"""
        await asyncio.sleep(0.1)
        raise ConnectionError("Database connection failed")
    
    async def business_logic():
        """Business logic that depends on database"""
        try:
            data = await database_operation()
            return process_data(data)
        except ConnectionError as e:
            # Re-raise with business context
            raise ValueError("Unable to process user request") from e
    
    async def api_handler():
        """API handler that calls business logic"""
        try:
            result = await business_logic()
            return {"status": "success", "data": result}
        except ValueError as e:
            # Add API context
            raise RuntimeError("API request failed") from e
    
    class ExceptionAnalyzer:
        """Helper to analyze exception chains"""
        
        @staticmethod
        def analyze_exception_chain(exc):
            """Analyze the complete exception chain"""
            print("   Exception chain analysis:")
            
            current = exc
            level = 0
            
            while current:
                indent = "     " * level
                print(f"{indent}Level {level}: {type(current).__name__}: {current}")
                
                if hasattr(current, '__cause__') and current.__cause__:
                    current = current.__cause__
                    level += 1
                elif hasattr(current, '__context__') and current.__context__:
                    print(f"{indent}  (context, not cause)")
                    current = current.__context__
                    level += 1
                else:
                    break
            
            return level + 1
    
    print("1. Testing exception chain:")
    try:
        await api_handler()
    except RuntimeError as e:
        print(f"   Final exception: {e}")
        chain_length = ExceptionAnalyzer.analyze_exception_chain(e)
        print(f"   Chain length: {chain_length}")
    
    print("\n2. Exception suppression example:")
    
    async def suppressing_coroutine():
        """Example of exception suppression"""
        try:
            await database_operation()
        except ConnectionError:
            # Suppress the original exception
            raise ValueError("New exception without context")
    
    try:
        await suppressing_coroutine()
    except ValueError as e:
        print(f"   Suppressed exception: {e}")
        print(f"   Has cause: {e.__cause__}")
        print(f"   Has context: {e.__context__}")
    
    print("\n3. Multiple exception contexts:")
    
    async def multiple_failures():
        """Example with multiple potential failure points"""
        exceptions = []
        
        operations = [
            ("Operation A", lambda: database_operation()),
            ("Operation B", lambda: ValueError("Validation error")),
            ("Operation C", lambda: TypeError("Type mismatch"))
        ]
        
        for name, operation in operations:
            try:
                if asyncio.iscoroutinefunction(operation):
                    await operation()
                else:
                    raise operation()
            except Exception as e:
                print(f"   {name} failed: {e}")
                exceptions.append((name, e))
        
        if exceptions:
            # Create composite exception
            main_error = RuntimeError("Multiple operations failed")
            main_error.failed_operations = exceptions
            raise main_error
    
    try:
        await multiple_failures()
    except RuntimeError as e:
        print(f"\n   Composite error: {e}")
        print("   Failed operations:")
        for name, exc in e.failed_operations:
            print(f"     {name}: {type(exc).__name__}: {exc}")

asyncio.run(demonstrate_exception_chaining())
```

### Exception Handling in Concurrent Operations

```python
import asyncio
import random

async def demonstrate_concurrent_exceptions():
    """Demonstrate exception handling in concurrent operations"""
    
    print("=== Concurrent Exception Handling ===")
    
    async def unreliable_operation(operation_id, failure_rate=0.3):
        """Operation that might fail randomly"""
        await asyncio.sleep(random.uniform(0.1, 0.5))
        
        if random.random() < failure_rate:
            raise ValueError(f"Operation {operation_id} failed")
        
        return f"Operation {operation_id} succeeded"
    
    print("1. gather() with exception handling:")
    
    # Default behavior: first exception stops everything
    try:
        tasks = [unreliable_operation(i) for i in range(5)]
        results = await asyncio.gather(*tasks)
        print(f"   All succeeded: {results}")
    except ValueError as e:
        print(f"   gather() failed: {e}")
    
    print("\n2. gather() with return_exceptions=True:")
    
    # Collect all results, including exceptions
    tasks = [unreliable_operation(i, failure_rate=0.4) for i in range(5)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    successes = []
    failures = []
    
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            failures.append((i, result))
        else:
            successes.append((i, result))
    
    print(f"   Successes: {len(successes)}")
    for i, result in successes:
        print(f"     Task {i}: {result}")
    
    print(f"   Failures: {len(failures)}")
    for i, exc in failures:
        print(f"     Task {i}: {type(exc).__name__}: {exc}")
    
    print("\n3. wait() with exception handling:")
    
    tasks = [
        asyncio.create_task(unreliable_operation(i, failure_rate=0.3)) 
        for i in range(5)
    ]
    
    done, pending = await asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED)
    
    print(f"   Completed tasks: {len(done)}")
    print(f"   Pending tasks: {len(pending)}")
    
    for task in done:
        try:
            result = task.result()
            print(f"   Task succeeded: {result}")
        except Exception as e:
            print(f"   Task failed: {type(e).__name__}: {e}")
    
    print("\n4. Manual concurrent exception collection:")
    
    class ConcurrentExceptionCollector:
        """Collect exceptions from concurrent operations"""
        
        def __init__(self):
            self.results = []
            self.exceptions = []
        
        async def run_with_collection(self, coroutines):
            """Run coroutines and collect all results/exceptions"""
            tasks = [asyncio.create_task(coro) for coro in coroutines]
            
            for i, task in enumerate(tasks):
                try:
                    result = await task
                    self.results.append((i, result))
                except Exception as e:
                    self.exceptions.append((i, e))
        
        def get_summary(self):
            """Get summary of results"""
            return {
                "total_operations": len(self.results) + len(self.exceptions),
                "successes": len(self.results),
                "failures": len(self.exceptions),
                "success_rate": len(self.results) / (len(self.results) + len(self.exceptions))
            }
    
    collector = ConcurrentExceptionCollector()
    operations = [unreliable_operation(i, failure_rate=0.4) for i in range(10)]
    
    await collector.run_with_collection(operations)
    summary = collector.get_summary()
    
    print(f"   Summary: {summary}")
    print(f"   Successful operations:")
    for i, result in collector.results:
        print(f"     {i}: {result}")
    
    print(f"   Failed operations:")
    for i, exc in collector.exceptions:
        print(f"     {i}: {type(exc).__name__}: {exc}")

asyncio.run(demonstrate_concurrent_exceptions())
```

## 10.2 Handling Task Exceptions

Tasks have special exception handling behavior. Understanding how to properly handle task exceptions is crucial for robust async applications.

### Task Exception Patterns

```python
import asyncio
import traceback
import logging

async def demonstrate_task_exceptions():
    """Demonstrate various patterns for handling task exceptions"""
    
    print("=== Task Exception Handling ===")
    
    async def failing_task(task_id, delay=0.1):
        """Task that will fail after some work"""
        print(f"   Task {task_id}: Starting")
        await asyncio.sleep(delay)
        print(f"   Task {task_id}: About to fail")
        raise RuntimeError(f"Task {task_id} failed")
    
    async def successful_task(task_id, delay=0.2):
        """Task that will succeed"""
        print(f"   Task {task_id}: Starting")
        await asyncio.sleep(delay)
        print(f"   Task {task_id}: Completed successfully")
        return f"Result from task {task_id}"
    
    print("1. Unhandled task exception (dangerous):")
    
    # Create task but don't await it immediately
    dangerous_task = asyncio.create_task(failing_task("dangerous"))
    
    # Do other work while task runs
    await asyncio.sleep(0.05)
    print("   Doing other work...")
    await asyncio.sleep(0.1)
    
    # Try to get result (will raise exception)
    try:
        result = await dangerous_task
    except RuntimeError as e:
        print(f"   Caught task exception: {e}")
    
    print("\n2. Task exception with done callback:")
    
    def task_done_callback(task):
        """Callback to handle task completion"""
        if task.cancelled():
            print(f"   Callback: Task was cancelled")
        elif task.exception():
            exc = task.exception()
            print(f"   Callback: Task failed with {type(exc).__name__}: {exc}")
        else:
            result = task.result()
            print(f"   Callback: Task succeeded with result: {result}")
    
    # Create tasks with callbacks
    callback_task1 = asyncio.create_task(failing_task("callback1"))
    callback_task2 = asyncio.create_task(successful_task("callback2"))
    
    callback_task1.add_done_callback(task_done_callback)
    callback_task2.add_done_callback(task_done_callback)
    
    # Wait for tasks to complete
    await asyncio.gather(callback_task1, callback_task2, return_exceptions=True)
    
    print("\n3. Task exception handling with task groups (Python 3.11+):")
    
    try:
        # Try to use task groups if available
        if hasattr(asyncio, 'TaskGroup'):
            async with asyncio.TaskGroup() as tg:
                task1 = tg.create_task(failing_task("group1"))
                task2 = tg.create_task(successful_task("group2"))
                task3 = tg.create_task(failing_task("group3"))
        else:
            print("   TaskGroup not available (Python < 3.11)")
    except* RuntimeError as eg:  # Exception group syntax (Python 3.11+)
        print(f"   Caught exception group with {len(eg.exceptions)} exceptions:")
        for exc in eg.exceptions:
            print(f"     {type(exc).__name__}: {exc}")
    except Exception as e:
        print(f"   Alternative handling: {e}")
    
    print("\n4. Manual task exception monitoring:")
    
    class TaskMonitor:
        """Monitor multiple tasks for exceptions"""
        
        def __init__(self):
            self.tasks = []
            self.results = {}
            self.exceptions = {}
        
        def add_task(self, coro, name=None):
            """Add a task to monitor"""
            task = asyncio.create_task(coro)
            task_name = name or f"task_{len(self.tasks)}"
            self.tasks.append((task_name, task))
            return task
        
        async def wait_all(self):
            """Wait for all tasks and collect results/exceptions"""
            for name, task in self.tasks:
                try:
                    result = await task
                    self.results[name] = result
                    print(f"   Monitor: {name} succeeded: {result}")
                except Exception as e:
                    self.exceptions[name] = e
                    print(f"   Monitor: {name} failed: {type(e).__name__}: {e}")
        
        def get_summary(self):
            """Get monitoring summary"""
            return {
                "total_tasks": len(self.tasks),
                "successful": len(self.results),
                "failed": len(self.exceptions),
                "results": self.results.copy(),
                "exceptions": {k: str(v) for k, v in self.exceptions.items()}
            }
    
    monitor = TaskMonitor()
    monitor.add_task(successful_task("monitored1", 0.1), "success_task")
    monitor.add_task(failing_task("monitored2", 0.15), "fail_task")
    monitor.add_task(successful_task("monitored3", 0.2), "another_success")
    
    await monitor.wait_all()
    summary = monitor.get_summary()
    print(f"   Monitoring summary: {summary}")

asyncio.run(demonstrate_task_exceptions())
```

### Fire-and-Forget Task Management

```python
import asyncio
import weakref
import atexit

class BackgroundTaskManager:
    """Manage fire-and-forget tasks properly"""
    
    def __init__(self):
        self.background_tasks = set()
        self.completed_tasks = []
        self.failed_tasks = []
        
        # Register cleanup on exit
        atexit.register(self._cleanup_on_exit)
    
    def create_background_task(self, coro, name=None):
        """Create a background task with proper exception handling"""
        task = asyncio.create_task(coro)
        task.task_name = name or f"bg_task_{id(task)}"
        
        # Add to tracking set
        self.background_tasks.add(task)
        
        # Add done callback for cleanup
        task.add_done_callback(self._task_done_callback)
        
        return task
    
    def _task_done_callback(self, task):
        """Handle task completion"""
        # Remove from active set
        self.background_tasks.discard(task)
        
        if task.cancelled():
            print(f"   BG Manager: Task {task.task_name} was cancelled")
        elif task.exception():
            exc = task.exception()
            self.failed_tasks.append((task.task_name, exc))
            print(f"   BG Manager: Task {task.task_name} failed: {exc}")
            
            # Log the exception
            import logging
            logging.error(f"Background task {task.task_name} failed", exc_info=exc)
        else:
            result = task.result()
            self.completed_tasks.append((task.task_name, result))
            print(f"   BG Manager: Task {task.task_name} completed: {result}")
    
    async def wait_for_all(self, timeout=None):
        """Wait for all background tasks to complete"""
        if not self.background_tasks:
            return
        
        print(f"   BG Manager: Waiting for {len(self.background_tasks)} tasks...")
        
        try:
            if timeout:
                await asyncio.wait_for(
                    asyncio.gather(*self.background_tasks, return_exceptions=True),
                    timeout=timeout
                )
            else:
                await asyncio.gather(*self.background_tasks, return_exceptions=True)
        
        except asyncio.TimeoutError:
            print(f"   BG Manager: Timeout waiting for tasks")
    
    def cancel_all(self):
        """Cancel all background tasks"""
        cancelled_count = 0
        for task in self.background_tasks.copy():
            if not task.done():
                task.cancel()
                cancelled_count += 1
        
        print(f"   BG Manager: Cancelled {cancelled_count} tasks")
    
    def get_stats(self):
        """Get task statistics"""
        return {
            "active_tasks": len(self.background_tasks),
            "completed_tasks": len(self.completed_tasks),
            "failed_tasks": len(self.failed_tasks),
            "total_created": len(self.completed_tasks) + len(self.failed_tasks) + len(self.background_tasks)
        }
    
    def _cleanup_on_exit(self):
        """Cleanup when process exits"""
        if self.background_tasks:
            print(f"Process exiting with {len(self.background_tasks)} active background tasks")

async def demonstrate_background_tasks():
    """Demonstrate proper background task management"""
    
    print("=== Background Task Management ===")
    
    manager = BackgroundTaskManager()
    
    async def background_worker(worker_id, work_duration, should_fail=False):
        """Background worker that simulates work"""
        print(f"   Worker {worker_id}: Starting work ({work_duration}s)")
        
        try:
            await asyncio.sleep(work_duration)
            
            if should_fail:
                raise RuntimeError(f"Worker {worker_id} encountered an error")
            
            result = f"Work completed by worker {worker_id}"
            print(f"   Worker {worker_id}: Finished successfully")
            return result
            
        except asyncio.CancelledError:
            print(f"   Worker {worker_id}: Cancelled")
            raise
        except Exception as e:
            print(f"   Worker {worker_id}: Failed with {e}")
            raise
    
    print("1. Creating background tasks:")
    
    # Create various background tasks
    manager.create_background_task(
        background_worker("A", 0.5, should_fail=False),
        name="worker_A"
    )
    
    manager.create_background_task(
        background_worker("B", 0.8, should_fail=True),
        name="worker_B"
    )
    
    manager.create_background_task(
        background_worker("C", 0.3, should_fail=False),
        name="worker_C"
    )
    
    manager.create_background_task(
        background_worker("D", 1.2, should_fail=False),
        name="worker_D"
    )
    
    print(f"   Created tasks, stats: {manager.get_stats()}")
    
    print("\n2. Doing other work while background tasks run:")
    
    # Simulate doing other work
    for i in range(3):
        await asyncio.sleep(0.2)
        stats = manager.get_stats()
        print(f"   Main work step {i+1}, bg stats: {stats}")
    
    print("\n3. Waiting for background tasks to complete:")
    
    try:
        await manager.wait_for_all(timeout=2.0)
    except asyncio.TimeoutError:
        print("   Some tasks didn't complete in time")
        manager.cancel_all()
        await manager.wait_for_all(timeout=1.0)
    
    final_stats = manager.get_stats()
    print(f"   Final stats: {final_stats}")
    
    print("\n4. Task completion details:")
    print(f"   Completed tasks: {len(manager.completed_tasks)}")
    for name, result in manager.completed_tasks:
        print(f"     {name}: {result}")
    
    print(f"   Failed tasks: {len(manager.failed_tasks)}")
    for name, exc in manager.failed_tasks:
        print(f"     {name}: {type(exc).__name__}: {exc}")

asyncio.run(demonstrate_background_tasks())
```

## 10.3 Exception Groups (Python 3.11+)

Exception groups provide a structured way to handle multiple exceptions that occur in concurrent operations.

### Working with Exception Groups

```python
import asyncio
import sys

# Note: Exception groups are available in Python 3.11+
# This section provides compatibility code for demonstration

if sys.version_info >= (3, 11):
    # Use built-in ExceptionGroup
    ExceptionGroup = ExceptionGroup
    BaseExceptionGroup = BaseExceptionGroup
else:
    # Provide compatibility implementation
    class ExceptionGroup(Exception):
        def __init__(self, message, exceptions):
            super().__init__(message)
            self.message = message
            self.exceptions = list(exceptions)
        
        def __str__(self):
            return f"{self.message} ({len(self.exceptions)} sub-exceptions)"
    
    BaseExceptionGroup = ExceptionGroup

async def demonstrate_exception_groups():
    """Demonstrate exception groups for handling multiple concurrent failures"""
    
    print("=== Exception Groups (Python 3.11+ feature) ===")
    
    async def worker_operation(worker_id, should_fail=False, failure_type=ValueError):
        """Worker operation that might fail"""
        await asyncio.sleep(0.1)
        
        if should_fail:
            raise failure_type(f"Worker {worker_id} failed")
        
        return f"Worker {worker_id} completed successfully"
    
    print("1. Manual exception group creation:")
    
    # Simulate collecting exceptions from multiple operations
    async def collect_exceptions_manually():
        """Manually collect exceptions and create exception group"""
        operations = [
            (worker_operation("A", should_fail=False), "Worker A"),
            (worker_operation("B", should_fail=True, failure_type=ValueError), "Worker B"),
            (worker_operation("C", should_fail=False), "Worker C"),
            (worker_operation("D", should_fail=True, failure_type=RuntimeError), "Worker D"),
            (worker_operation("E", should_fail=True, failure_type=TypeError), "Worker E"),
        ]
        
        results = []
        exceptions = []
        
        for operation, name in operations:
            try:
                result = await operation
                results.append((name, result))
            except Exception as e:
                exceptions.append(e)
        
        print(f"   Successful operations: {len(results)}")
        for name, result in results:
            print(f"     {name}: {result}")
        
        if exceptions:
            print(f"   Failed operations: {len(exceptions)}")
            for exc in exceptions:
                print(f"     {type(exc).__name__}: {exc}")
            
            # Create exception group
            raise ExceptionGroup("Multiple worker failures", exceptions)
        
        return results
    
    try:
        await collect_exceptions_manually()
    except ExceptionGroup as eg:
        print(f"   Caught exception group: {eg}")
        print(f"   Number of exceptions: {len(eg.exceptions)}")
        
        # Handle different exception types
        value_errors = [e for e in eg.exceptions if isinstance(e, ValueError)]
        runtime_errors = [e for e in eg.exceptions if isinstance(e, RuntimeError)]
        type_errors = [e for e in eg.exceptions if isinstance(e, TypeError)]
        
        print(f"   ValueError count: {len(value_errors)}")
        print(f"   RuntimeError count: {len(runtime_errors)}")
        print(f"   TypeError count: {len(type_errors)}")
    
    if sys.version_info >= (3, 11):
        print("\n2. TaskGroup with exception groups (Python 3.11+):")
        
        try:
            async with asyncio.TaskGroup() as tg:
                task1 = tg.create_task(worker_operation("TG1", should_fail=True))
                task2 = tg.create_task(worker_operation("TG2", should_fail=False))
                task3 = tg.create_task(worker_operation("TG3", should_fail=True))
                task4 = tg.create_task(worker_operation("TG4", should_fail=False))
        
        except* ValueError as eg:
            print(f"   Caught ValueError group: {len(eg.exceptions)} exceptions")
            for exc in eg.exceptions:
                print(f"     {exc}")
        
        except* Exception as eg:
            print(f"   Caught other exceptions: {len(eg.exceptions)} exceptions")
            for exc in eg.exceptions:
                print(f"     {type(exc).__name__}: {exc}")
    
    print("\n3. Exception group filtering and handling:")
    
    class ExceptionGroupHandler:
        """Helper for handling exception groups"""
        
        def __init__(self):
            self.handled_exceptions = []
            self.unhandled_exceptions = []
        
        def handle_exception_group(self, eg):
            """Handle exception group by type"""
            for exc in eg.exceptions:
                if isinstance(exc, ValueError):
                    self._handle_value_error(exc)
                elif isinstance(exc, RuntimeError):
                    self._handle_runtime_error(exc)
                elif isinstance(exc, TypeError):
                    self._handle_type_error(exc)
                else:
                    self.unhandled_exceptions.append(exc)
        
        def _handle_value_error(self, exc):
            """Handle ValueError specifically"""
            print(f"   Handler: Processing ValueError: {exc}")
            self.handled_exceptions.append(exc)
            # Could implement retry logic, logging, etc.
        
        def _handle_runtime_error(self, exc):
            """Handle RuntimeError specifically"""
            print(f"   Handler: Processing RuntimeError: {exc}")
            self.handled_exceptions.append(exc)
            # Could implement fallback logic
        
        def _handle_type_error(self, exc):
            """Handle TypeError specifically"""
            print(f"   Handler: Processing TypeError: {exc}")
            self.handled_exceptions.append(exc)
            # Could implement data correction
        
        def get_summary(self):
            """Get handling summary"""
            return {
                "handled_count": len(self.handled_exceptions),
                "unhandled_count": len(self.unhandled_exceptions),
                "handled_types": [type(e).__name__ for e in self.handled_exceptions],
                "unhandled_types": [type(e).__name__ for e in self.unhandled_exceptions]
            }
    
    # Create an exception group to handle
    test_exceptions = [
        ValueError("Test value error 1"),
        RuntimeError("Test runtime error"),
        ValueError("Test value error 2"),
        TypeError("Test type error"),
        ConnectionError("Test connection error")  # This won't be handled
    ]
    
    test_group = ExceptionGroup("Test exception group", test_exceptions)
    
    handler = ExceptionGroupHandler()
    handler.handle_exception_group(test_group)
    
    summary = handler.get_summary()
    print(f"   Exception handling summary: {summary}")
    
    if handler.unhandled_exceptions:
        print("   Unhandled exceptions:")
        for exc in handler.unhandled_exceptions:
            print(f"     {type(exc).__name__}: {exc}")
    
    print("\n4. Nested exception groups:")
    
    # Create nested exception groups
    inner_group1 = ExceptionGroup("Database errors", [
        ConnectionError("DB connection failed"),
        TimeoutError("DB query timed out")
    ])
    
    inner_group2 = ExceptionGroup("API errors", [
        ValueError("Invalid API response"),
        RuntimeError("API rate limit exceeded")
    ])
    
    outer_group = ExceptionGroup("Service errors", [inner_group1, inner_group2])
    
    def analyze_nested_groups(eg, level=0):
        """Recursively analyze nested exception groups"""
        indent = "  " * level
        print(f"{indent}Group: {eg.message} ({len(eg.exceptions)} exceptions)")
        
        for exc in eg.exceptions:
            if isinstance(exc, ExceptionGroup):
                analyze_nested_groups(exc, level + 1)
            else:
                print(f"{indent}  {type(exc).__name__}: {exc}")
    
    print("   Nested exception group structure:")
    analyze_nested_groups(outer_group)

asyncio.run(demonstrate_exception_groups())
```

This completes Chapter 10, covering exception handling and debugging fundamentals in asyncio. The chapter demonstrates:

1. **Exception Propagation** - How exceptions flow through coroutines and async call stacks
2. **Task Exceptions** - Proper handling of exceptions in asyncio tasks
3. **Exception Groups** - Modern structured exception handling for concurrent operations

Would you like me to continue with Chapter 11 (Timeouts and Cancellation) or focus on any specific aspect of exception handling?

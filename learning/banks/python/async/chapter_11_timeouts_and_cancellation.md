# Chapter 11: Timeouts and Cancellation

## 11.1 Timeout Patterns

Timeouts are essential for building robust async applications that don't hang indefinitely when operations fail or take too long. Understanding various timeout patterns helps you create responsive and reliable systems.

### Basic Timeout Mechanisms

```python
import asyncio
import time
import random

async def demonstrate_basic_timeouts():
    """Demonstrate fundamental timeout mechanisms in asyncio"""
    
    print("=== Basic Timeout Mechanisms ===")
    
    async def slow_operation(duration, name="operation"):
        """Simulate an operation that takes a specific amount of time"""
        print(f"   {name}: Starting (will take {duration}s)")
        start_time = time.time()
        
        try:
            await asyncio.sleep(duration)
            end_time = time.time()
            result = f"{name} completed in {end_time - start_time:.2f}s"
            print(f"   {name}: {result}")
            return result
        except asyncio.CancelledError:
            end_time = time.time()
            print(f"   {name}: Cancelled after {end_time - start_time:.2f}s")
            raise
    
    print("1. wait_for() timeout:")
    
    # Test successful operation within timeout
    try:
        result = await asyncio.wait_for(
            slow_operation(0.5, "FastOp"), 
            timeout=1.0
        )
        print(f"   Success: {result}")
    except asyncio.TimeoutError:
        print("   Operation timed out")
    
    # Test operation that times out
    try:
        result = await asyncio.wait_for(
            slow_operation(2.0, "SlowOp"), 
            timeout=1.0
        )
        print(f"   Success: {result}")
    except asyncio.TimeoutError:
        print("   Operation timed out as expected")
    
    print("\n2. timeout() context manager (Python 3.11+):")
    
    # Try to use the new timeout context manager if available
    if hasattr(asyncio, 'timeout'):
        try:
            async with asyncio.timeout(1.0):
                result = await slow_operation(0.7, "ContextOp")
                print(f"   Context success: {result}")
        except asyncio.TimeoutError:
            print("   Context operation timed out")
        
        try:
            async with asyncio.timeout(0.5):
                result = await slow_operation(1.0, "ContextTimeoutOp")
                print(f"   Context success: {result}")
        except asyncio.TimeoutError:
            print("   Context operation timed out as expected")
    else:
        print("   timeout() context manager not available (Python < 3.11)")
    
    print("\n3. Custom timeout implementation:")
    
    class TimeoutManager:
        """Custom timeout manager for demonstration"""
        
        def __init__(self, timeout_duration):
            self.timeout_duration = timeout_duration
            self.start_time = None
            self.timeout_task = None
        
        async def __aenter__(self):
            self.start_time = time.time()
            
            # Create timeout task
            async def timeout_handler():
                await asyncio.sleep(self.timeout_duration)
                raise asyncio.TimeoutError(f"Operation timed out after {self.timeout_duration}s")
            
            self.timeout_task = asyncio.create_task(timeout_handler())
            return self
        
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            if self.timeout_task and not self.timeout_task.done():
                self.timeout_task.cancel()
                
                # Wait for cancellation to complete
                try:
                    await self.timeout_task
                except asyncio.CancelledError:
                    pass
    
    try:
        async with TimeoutManager(1.0):
            result = await slow_operation(0.8, "CustomTimeoutOp")
            print(f"   Custom timeout success: {result}")
    except asyncio.TimeoutError as e:
        print(f"   Custom timeout: {e}")

asyncio.run(demonstrate_basic_timeouts())
```

### Advanced Timeout Patterns

```python
import asyncio
import time
from typing import Optional, Any

async def demonstrate_advanced_timeouts():
    """Demonstrate advanced timeout patterns and strategies"""
    
    print("=== Advanced Timeout Patterns ===")
    
    async def variable_duration_operation(min_duration=0.1, max_duration=2.0):
        """Operation with variable duration"""
        duration = random.uniform(min_duration, max_duration)
        operation_id = random.randint(1000, 9999)
        
        print(f"   Operation {operation_id}: Starting (will take {duration:.2f}s)")
        await asyncio.sleep(duration)
        
        return f"Operation {operation_id} completed in {duration:.2f}s"
    
    print("1. Progressive timeout strategy:")
    
    async def progressive_timeout_strategy(operation_coro, timeouts):
        """Try operation with progressively longer timeouts"""
        for attempt, timeout in enumerate(timeouts, 1):
            print(f"   Attempt {attempt}: Trying with {timeout}s timeout")
            
            try:
                result = await asyncio.wait_for(operation_coro, timeout=timeout)
                print(f"   Success on attempt {attempt}: {result}")
                return result
            except asyncio.TimeoutError:
                print(f"   Attempt {attempt} timed out")
                
                # Reset the coroutine for next attempt
                operation_coro = variable_duration_operation(0.1, 2.0)
                
                if attempt < len(timeouts):
                    print(f"   Retrying with longer timeout...")
                else:
                    print(f"   All attempts failed")
                    raise
    
    try:
        result = await progressive_timeout_strategy(
            variable_duration_operation(0.1, 2.0),
            timeouts=[0.5, 1.0, 1.5, 2.5]
        )
        print(f"   Progressive strategy result: {result}")
    except asyncio.TimeoutError:
        print("   Progressive strategy ultimately failed")
    
    print("\n2. Timeout with partial results:")
    
    async def multi_operation_with_timeout(operations, timeout):
        """Run multiple operations with timeout, collecting partial results"""
        tasks = [asyncio.create_task(op) for op in operations]
        results = {}
        completed_count = 0
        
        try:
            # Wait for all tasks with timeout
            await asyncio.wait_for(
                asyncio.gather(*tasks), 
                timeout=timeout
            )
            
            # If we get here, all completed successfully
            for i, task in enumerate(tasks):
                results[f"op_{i}"] = task.result()
                completed_count += 1
        
        except asyncio.TimeoutError:
            print(f"   Timeout occurred, collecting partial results...")
            
            # Collect results from completed tasks
            for i, task in enumerate(tasks):
                if task.done() and not task.cancelled():
                    try:
                        results[f"op_{i}"] = task.result()
                        completed_count += 1
                    except Exception as e:
                        results[f"op_{i}"] = f"Error: {e}"
                elif task.cancelled():
                    results[f"op_{i}"] = "Cancelled"
                else:
                    results[f"op_{i}"] = "Not completed"
                    # Cancel uncompleted tasks
                    task.cancel()
        
        print(f"   Completed {completed_count}/{len(tasks)} operations")
        return results
    
    operations = [
        variable_duration_operation(0.1, 0.5),  # Fast
        variable_duration_operation(0.5, 1.5),  # Medium
        variable_duration_operation(1.0, 2.0),  # Slow
        variable_duration_operation(0.2, 0.8),  # Fast-medium
    ]
    
    partial_results = await multi_operation_with_timeout(operations, timeout=1.0)
    print("   Partial results:")
    for op_name, result in partial_results.items():
        print(f"     {op_name}: {result}")
    
    print("\n3. Adaptive timeout based on historical performance:")
    
    class AdaptiveTimeoutManager:
        """Manage timeouts that adapt based on historical performance"""
        
        def __init__(self, initial_timeout=1.0, adaptation_factor=0.1):
            self.initial_timeout = initial_timeout
            self.adaptation_factor = adaptation_factor
            self.execution_times = []
            self.current_timeout = initial_timeout
        
        def _update_timeout(self, execution_time):
            """Update timeout based on execution time"""
            self.execution_times.append(execution_time)
            
            # Keep only recent execution times
            if len(self.execution_times) > 10:
                self.execution_times = self.execution_times[-10:]
            
            # Calculate statistics
            avg_time = sum(self.execution_times) / len(self.execution_times)
            max_time = max(self.execution_times)
            
            # Adapt timeout (average + buffer, but not more than 2x max)
            new_timeout = min(avg_time * 2.0, max_time * 1.5)
            
            # Smooth adjustment
            self.current_timeout = (
                self.current_timeout * (1 - self.adaptation_factor) + 
                new_timeout * self.adaptation_factor
            )
            
            print(f"   Timeout adapted: {self.current_timeout:.2f}s "
                  f"(avg: {avg_time:.2f}s, max: {max_time:.2f}s)")
        
        async def execute_with_adaptive_timeout(self, operation_coro):
            """Execute operation with adaptive timeout"""
            start_time = time.time()
            
            try:
                result = await asyncio.wait_for(
                    operation_coro, 
                    timeout=self.current_timeout
                )
                execution_time = time.time() - start_time
                self._update_timeout(execution_time)
                return result
            
            except asyncio.TimeoutError:
                # Even timeouts provide information about execution time
                execution_time = self.current_timeout
                self._update_timeout(execution_time)
                raise
    
    adaptive_manager = AdaptiveTimeoutManager(initial_timeout=0.5)
    
    print("   Testing adaptive timeout:")
    for i in range(6):
        try:
            result = await adaptive_manager.execute_with_adaptive_timeout(
                variable_duration_operation(0.1, 1.5)
            )
            print(f"   Attempt {i+1} succeeded: {result[:50]}...")
        except asyncio.TimeoutError:
            print(f"   Attempt {i+1} timed out")

asyncio.run(demonstrate_advanced_timeouts())
```

### Timeout Hierarchies and Nesting

```python
import asyncio
import time

async def demonstrate_timeout_hierarchies():
    """Demonstrate nested timeouts and timeout hierarchies"""
    
    print("=== Timeout Hierarchies ===")
    
    async def work_step(step_name, duration):
        """Individual work step"""
        print(f"     Step {step_name}: Starting ({duration}s)")
        await asyncio.sleep(duration)
        print(f"     Step {step_name}: Completed")
        return f"Step {step_name} result"
    
    print("1. Nested timeout contexts:")
    
    try:
        # Outer timeout for entire operation
        async with asyncio.timeout(3.0) if hasattr(asyncio, 'timeout') else asyncio.wait_for(asyncio.sleep(0), timeout=3.0):
            print("   Outer timeout: 3.0s for entire operation")
            
            try:
                # Inner timeout for first phase
                if hasattr(asyncio, 'timeout'):
                    async with asyncio.timeout(1.5):
                        print("   Inner timeout: 1.5s for phase 1")
                        await work_step("1A", 0.5)
                        await work_step("1B", 0.8)
                else:
                    # Fallback for older Python versions
                    await asyncio.wait_for(
                        asyncio.gather(
                            work_step("1A", 0.5),
                            work_step("1B", 0.8)
                        ),
                        timeout=1.5
                    )
                
            except asyncio.TimeoutError:
                print("   Phase 1 timed out, continuing to phase 2")
            
            # Phase 2 with remaining time
            await work_step("2A", 0.7)
            await work_step("2B", 0.5)
            
    except asyncio.TimeoutError:
        print("   Entire operation timed out")
    
    print("\n2. Timeout inheritance pattern:")
    
    class TimeoutContext:
        """Context that tracks timeout hierarchies"""
        
        def __init__(self, timeout_duration, name="operation"):
            self.timeout_duration = timeout_duration
            self.name = name
            self.start_time = None
            self.parent_context = None
        
        def get_remaining_time(self):
            """Get remaining time in this context"""
            if not self.start_time:
                return self.timeout_duration
            
            elapsed = time.time() - self.start_time
            remaining = self.timeout_duration - elapsed
            
            # Also check parent context
            if self.parent_context:
                parent_remaining = self.parent_context.get_remaining_time()
                remaining = min(remaining, parent_remaining)
            
            return max(0, remaining)
        
        async def __aenter__(self):
            self.start_time = time.time()
            
            # Set as current context
            if hasattr(asyncio.current_task(), 'timeout_context'):
                self.parent_context = asyncio.current_task().timeout_context
            
            asyncio.current_task().timeout_context = self
            print(f"   Entering timeout context '{self.name}': {self.timeout_duration}s")
            return self
        
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            # Restore parent context
            if self.parent_context:
                asyncio.current_task().timeout_context = self.parent_context
            else:
                if hasattr(asyncio.current_task(), 'timeout_context'):
                    delattr(asyncio.current_task(), 'timeout_context')
            
            elapsed = time.time() - self.start_time
            print(f"   Exiting timeout context '{self.name}': {elapsed:.2f}s elapsed")
    
    async def timeout_aware_operation(operation_name, duration):
        """Operation that's aware of timeout context"""
        # Check if we have a timeout context
        current_task = asyncio.current_task()
        
        if hasattr(current_task, 'timeout_context'):
            context = current_task.timeout_context
            remaining = context.get_remaining_time()
            
            print(f"   {operation_name}: Starting (needs {duration}s, "
                  f"remaining {remaining:.2f}s)")
            
            if duration > remaining:
                print(f"   {operation_name}: Not enough time remaining")
                raise asyncio.TimeoutError(f"Insufficient time for {operation_name}")
        
        await asyncio.sleep(duration)
        return f"{operation_name} completed"
    
    try:
        async with TimeoutContext(3.0, "main_operation"):
            async with TimeoutContext(1.5, "phase_1"):
                await timeout_aware_operation("Task_1A", 0.6)
                await timeout_aware_operation("Task_1B", 0.7)
            
            async with TimeoutContext(2.0, "phase_2"):  # This inherits remaining time
                await timeout_aware_operation("Task_2A", 0.8)
                await timeout_aware_operation("Task_2B", 0.9)  # This might fail
    
    except asyncio.TimeoutError as e:
        print(f"   Timeout hierarchy failed: {e}")
    
    print("\n3. Timeout with cancellation propagation:")
    
    class CancellableTimeoutContext:
        """Timeout context that properly handles cancellation"""
        
        def __init__(self, timeout_duration):
            self.timeout_duration = timeout_duration
            self.timeout_task = None
            self.operation_task = None
        
        async def run_with_timeout(self, operation_coro):
            """Run operation with timeout and proper cancellation"""
            
            async def timeout_handler():
                """Handle timeout by cancelling operation"""
                await asyncio.sleep(self.timeout_duration)
                
                if self.operation_task and not self.operation_task.done():
                    print(f"   Timeout: Cancelling operation after {self.timeout_duration}s")
                    self.operation_task.cancel()
            
            # Create both timeout and operation tasks
            self.timeout_task = asyncio.create_task(timeout_handler())
            self.operation_task = asyncio.create_task(operation_coro)
            
            try:
                # Race between timeout and operation
                done, pending = await asyncio.wait(
                    [self.timeout_task, self.operation_task],
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                # Cancel pending tasks
                for task in pending:
                    task.cancel()
                
                # Check which completed first
                if self.operation_task in done:
                    # Operation completed first
                    return self.operation_task.result()
                else:
                    # Timeout occurred
                    raise asyncio.TimeoutError(f"Operation timed out after {self.timeout_duration}s")
            
            finally:
                # Ensure cleanup
                if self.timeout_task and not self.timeout_task.done():
                    self.timeout_task.cancel()
                
                if self.operation_task and not self.operation_task.done():
                    self.operation_task.cancel()
                
                # Wait for cancellation to complete
                await asyncio.gather(
                    self.timeout_task, self.operation_task, 
                    return_exceptions=True
                )
    
    async def complex_operation():
        """Complex operation with multiple steps"""
        steps = [
            ("Initialization", 0.3),
            ("Data Processing", 0.8),
            ("Network Request", 1.2),
            ("Finalization", 0.4)
        ]
        
        results = []
        
        for step_name, duration in steps:
            print(f"   Complex operation: {step_name}")
            await asyncio.sleep(duration)
            results.append(f"{step_name} completed")
        
        return results
    
    timeout_context = CancellableTimeoutContext(2.0)
    
    try:
        result = await timeout_context.run_with_timeout(complex_operation())
        print(f"   Complex operation succeeded: {len(result)} steps completed")
    except asyncio.TimeoutError as e:
        print(f"   Complex operation timed out: {e}")

asyncio.run(demonstrate_timeout_hierarchies())
```

## 11.2 asyncio.timeout() Context Manager

The `asyncio.timeout()` context manager, introduced in Python 3.11, provides a clean and efficient way to handle timeouts.

### Modern Timeout Usage

```python
import asyncio
import sys
import time

async def demonstrate_timeout_context_manager():
    """Demonstrate the modern asyncio.timeout() context manager"""
    
    print("=== asyncio.timeout() Context Manager ===")
    
    if sys.version_info < (3, 11):
        print("Note: asyncio.timeout() requires Python 3.11+")
        print("Using asyncio.wait_for() for compatibility demonstrations")
    
    async def sample_operation(duration, name="operation"):
        """Sample operation that takes specified time"""
        print(f"   {name}: Starting (duration: {duration}s)")
        start = time.time()
        await asyncio.sleep(duration)
        elapsed = time.time() - start
        print(f"   {name}: Completed in {elapsed:.2f}s")
        return f"{name} result"
    
    if sys.version_info >= (3, 11):
        print("1. Basic timeout() usage:")
        
        # Successful operation within timeout
        try:
            async with asyncio.timeout(2.0):
                result = await sample_operation(1.0, "FastOp")
                print(f"   Success: {result}")
        except asyncio.TimeoutError:
            print("   Unexpected timeout")
        
        # Operation that times out
        try:
            async with asyncio.timeout(1.0):
                result = await sample_operation(2.0, "SlowOp")
                print(f"   Success: {result}")
        except asyncio.TimeoutError:
            print("   Expected timeout occurred")
        
        print("\n2. Nested timeout contexts:")
        
        try:
            async with asyncio.timeout(3.0):  # Outer timeout
                print("   Outer timeout: 3.0s")
                
                await sample_operation(0.5, "Step1")
                
                async with asyncio.timeout(1.0):  # Inner timeout
                    print("   Inner timeout: 1.0s")
                    await sample_operation(0.8, "Step2")
                
                await sample_operation(0.6, "Step3")
                
        except asyncio.TimeoutError:
            print("   Timeout in nested context")
        
        print("\n3. Timeout with resource management:")
        
        class ManagedResource:
            def __init__(self, name):
                self.name = name
                self.is_open = False
            
            async def __aenter__(self):
                print(f"   Opening resource: {self.name}")
                await asyncio.sleep(0.1)  # Simulate opening
                self.is_open = True
                return self
            
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                print(f"   Closing resource: {self.name}")
                self.is_open = False
                await asyncio.sleep(0.05)  # Simulate cleanup
                
                if exc_type == asyncio.TimeoutError:
                    print(f"   Resource {self.name} cleanup after timeout")
            
            async def do_work(self, duration):
                if not self.is_open:
                    raise RuntimeError(f"Resource {self.name} not open")
                
                print(f"   {self.name}: Doing work for {duration}s")
                await asyncio.sleep(duration)
                return f"Work done by {self.name}"
        
        try:
            async with asyncio.timeout(2.0):
                async with ManagedResource("DatabaseConnection") as db:
                    result1 = await db.do_work(0.5)
                    print(f"   Result 1: {result1}")
                    
                    result2 = await db.do_work(1.8)  # This will timeout
                    print(f"   Result 2: {result2}")
        
        except asyncio.TimeoutError:
            print("   Timeout with managed resource - resource was cleaned up")
        
        print("\n4. Timeout object inspection:")
        
        timeout_obj = asyncio.timeout(1.5)
        print(f"   Timeout object: {timeout_obj}")
        
        async with timeout_obj as tm:
            print(f"   Timeout manager: {tm}")
            print(f"   When (absolute time): {tm.when()}")
            print(f"   Expires in: {tm.when() - time.time():.2f}s")
            
            await sample_operation(0.5, "InspectedOp")
            
            print(f"   Remaining time: {tm.when() - time.time():.2f}s")
        
        print("\n5. Dynamic timeout adjustment:")
        
        class DynamicTimeout:
            def __init__(self, initial_timeout):
                self.timeout = initial_timeout
                self.start_time = None
            
            async def adjust_timeout(self, new_timeout):
                """Dynamically adjust timeout during operation"""
                if self.start_time:
                    elapsed = time.time() - self.start_time
                    remaining = self.timeout - elapsed
                    print(f"   Adjusting timeout: {remaining:.2f}s -> {new_timeout}s")
                    self.timeout = new_timeout
        
        # Note: asyncio.timeout() doesn't support dynamic adjustment
        # This is shown as a pattern for custom timeout implementations
        
    else:
        # Compatibility demonstrations using asyncio.wait_for()
        print("1. Compatibility timeout patterns:")
        
        try:
            result = await asyncio.wait_for(
                sample_operation(1.0, "CompatOp"),
                timeout=2.0
            )
            print(f"   Compatibility success: {result}")
        except asyncio.TimeoutError:
            print("   Compatibility timeout")
        
        print("\n2. Nested wait_for patterns:")
        
        try:
            await asyncio.wait_for(
                asyncio.wait_for(
                    sample_operation(2.0, "NestedOp"),
                    timeout=1.5  # Inner timeout
                ),
                timeout=3.0  # Outer timeout
            )
        except asyncio.TimeoutError:
            print("   Nested timeout occurred")

asyncio.run(demonstrate_timeout_context_manager())
```

### Timeout Best Practices and Patterns

```python
import asyncio
import time
from contextlib import asynccontextmanager

async def demonstrate_timeout_best_practices():
    """Demonstrate best practices for using timeouts"""
    
    print("=== Timeout Best Practices ===")
    
    print("1. Graceful degradation with timeouts:")
    
    async def primary_service():
        """Primary service that might be slow"""
        await asyncio.sleep(1.5)
        return "Primary service result"
    
    async def fallback_service():
        """Fallback service that's faster but less comprehensive"""
        await asyncio.sleep(0.3)
        return "Fallback service result"
    
    async def service_with_fallback(primary_timeout=1.0):
        """Service that falls back if primary is too slow"""
        try:
            if sys.version_info >= (3, 11):
                async with asyncio.timeout(primary_timeout):
                    result = await primary_service()
                    print(f"   Used primary service: {result}")
                    return result
            else:
                result = await asyncio.wait_for(primary_service(), timeout=primary_timeout)
                print(f"   Used primary service: {result}")
                return result
        
        except asyncio.TimeoutError:
            print("   Primary service timed out, using fallback")
            result = await fallback_service()
            print(f"   Used fallback service: {result}")
            return result
    
    result = await service_with_fallback()
    print(f"   Final result: {result}")
    
    print("\n2. Progressive timeout with exponential backoff:")
    
    async def unreliable_operation():
        """Operation that fails randomly"""
        import random
        failure_chance = 0.6
        
        if random.random() < failure_chance:
            await asyncio.sleep(2.0)  # Simulate hanging
            raise RuntimeError("Operation failed")
        else:
            await asyncio.sleep(0.5)
            return "Operation succeeded"
    
    async def progressive_timeout_retry(max_attempts=3):
        """Retry with progressively longer timeouts"""
        base_timeout = 0.5
        
        for attempt in range(max_attempts):
            timeout_duration = base_timeout * (2 ** attempt)  # Exponential increase
            print(f"   Attempt {attempt + 1}: timeout = {timeout_duration}s")
            
            try:
                if sys.version_info >= (3, 11):
                    async with asyncio.timeout(timeout_duration):
                        result = await unreliable_operation()
                        print(f"   Success on attempt {attempt + 1}: {result}")
                        return result
                else:
                    result = await asyncio.wait_for(
                        unreliable_operation(), 
                        timeout=timeout_duration
                    )
                    print(f"   Success on attempt {attempt + 1}: {result}")
                    return result
            
            except (asyncio.TimeoutError, RuntimeError) as e:
                print(f"   Attempt {attempt + 1} failed: {type(e).__name__}")
                
                if attempt == max_attempts - 1:
                    raise asyncio.TimeoutError("All attempts exhausted")
                
                # Brief delay before retry
                await asyncio.sleep(0.1)
    
    try:
        result = await progressive_timeout_retry()
        print(f"   Progressive retry result: {result}")
    except asyncio.TimeoutError as e:
        print(f"   Progressive retry failed: {e}")
    
    print("\n3. Timeout with progress tracking:")
    
    class ProgressTracker:
        """Track progress of long-running operations"""
        
        def __init__(self, total_steps):
            self.total_steps = total_steps
            self.completed_steps = 0
            self.start_time = time.time()
        
        def step_completed(self):
            """Mark a step as completed"""
            self.completed_steps += 1
            progress = self.completed_steps / self.total_steps
            elapsed = time.time() - self.start_time
            
            if progress > 0:
                estimated_total = elapsed / progress
                estimated_remaining = estimated_total - elapsed
                
                print(f"   Progress: {self.completed_steps}/{self.total_steps} "
                      f"({progress:.1%}) - ETA: {estimated_remaining:.1f}s")
            
            return progress
        
        def get_progress(self):
            """Get current progress"""
            return self.completed_steps / self.total_steps
    
    async def long_operation_with_progress(tracker):
        """Long operation that reports progress"""
        for i in range(tracker.total_steps):
            await asyncio.sleep(0.2)  # Simulate work
            tracker.step_completed()
            
            # Check if we should continue based on progress
            yield tracker.get_progress()
        
        return "Long operation completed"
    
    async def timeout_with_progress_monitoring():
        """Monitor progress and adjust timeout accordingly"""
        tracker = ProgressTracker(total_steps=8)
        operation_gen = long_operation_with_progress(tracker)
        
        timeout_duration = 3.0  # Initial timeout
        
        try:
            if sys.version_info >= (3, 11):
                async with asyncio.timeout(timeout_duration):
                    async for progress in operation_gen:
                        # If we're making good progress, we might extend timeout
                        if progress > 0.5 and time.time() - tracker.start_time > timeout_duration * 0.8:
                            print("   Good progress detected, would extend timeout in real implementation")
            else:
                # Fallback implementation
                start_time = time.time()
                async for progress in operation_gen:
                    elapsed = time.time() - start_time
                    if elapsed > timeout_duration:
                        raise asyncio.TimeoutError("Operation timed out")
        
        except asyncio.TimeoutError:
            final_progress = tracker.get_progress()
            print(f"   Operation timed out at {final_progress:.1%} completion")
    
    await timeout_with_progress_monitoring()
    
    print("\n4. Cooperative timeout handling:")
    
    @asynccontextmanager
    async def cooperative_timeout(duration):
        """Timeout that can be overridden by cooperative operations"""
        
        class CooperativeTimeoutManager:
            def __init__(self):
                self.original_duration = duration
                self.start_time = time.time()
                self.extensions = []
            
            def request_extension(self, additional_time, reason):
                """Request timeout extension"""
                self.extensions.append((additional_time, reason))
                print(f"   Timeout extension requested: +{additional_time}s ({reason})")
            
            def get_effective_timeout(self):
                """Get effective timeout including extensions"""
                total_extension = sum(ext[0] for ext in self.extensions)
                return self.original_duration + total_extension
            
            def time_remaining(self):
                """Get remaining time"""
                elapsed = time.time() - self.start_time
                effective = self.get_effective_timeout()
                return max(0, effective - elapsed)
        
        manager = CooperativeTimeoutManager()
        
        # Make manager available to the operation
        asyncio.current_task().timeout_manager = manager
        
        try:
            effective_timeout = manager.get_effective_timeout()
            
            if sys.version_info >= (3, 11):
                async with asyncio.timeout(effective_timeout):
                    yield manager
            else:
                start_time = time.time()
                
                class TimeoutChecker:
                    async def check_timeout(self):
                        while True:
                            remaining = manager.time_remaining()
                            if remaining <= 0:
                                raise asyncio.TimeoutError("Cooperative timeout expired")
                            await asyncio.sleep(0.1)
                
                checker = TimeoutChecker()
                timeout_task = asyncio.create_task(checker.check_timeout())
                
                try:
                    yield manager
                finally:
                    timeout_task.cancel()
                    await asyncio.gather(timeout_task, return_exceptions=True)
        
        finally:
            if hasattr(asyncio.current_task(), 'timeout_manager'):
                delattr(asyncio.current_task(), 'timeout_manager')
    
    async def cooperative_operation():
        """Operation that can request timeout extensions"""
        
        # Check if we have a cooperative timeout manager
        if hasattr(asyncio.current_task(), 'timeout_manager'):
            manager = asyncio.current_task().timeout_manager
            
            await asyncio.sleep(0.5)
            
            # Request extension for critical section
            manager.request_extension(1.0, "Critical data processing")
            
            await asyncio.sleep(1.2)  # This would normally timeout
            
            return "Cooperative operation completed"
        else:
            await asyncio.sleep(1.7)
            return "Standard operation completed"
    
    try:
        async with cooperative_timeout(1.0) as manager:
            result = await cooperative_operation()
            print(f"   Cooperative result: {result}")
            print(f"   Final timeout info: {manager.get_effective_timeout()}s total, "
                  f"{len(manager.extensions)} extensions")
    except asyncio.TimeoutError:
        print("   Cooperative operation timed out despite extensions")

asyncio.run(demonstrate_timeout_best_practices())
```

This completes the first part of Chapter 11 covering timeout patterns and the modern asyncio.timeout() context manager. The examples show practical timeout usage patterns from basic timeouts to advanced cooperative timeout management.

Would you like me to continue with sections 11.3 (Cancellation Mechanics) and 11.4 (CancelledError Handling)?
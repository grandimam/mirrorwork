# Chapter 4: Tasks and Futures

## 4.1 Understanding Futures

Futures are the foundation of asyncio's asynchronous execution model. A Future represents an eventual result of an asynchronous operation - a placeholder for a value that will be available in the future.

### What is a Future?

A Future is an awaitable object that represents the result of an asynchronous operation that may not have completed yet. Think of it as a "promise" that a value will be available later.

```python
import asyncio
import time

def demonstrate_basic_future():
    """Demonstrate basic Future usage"""
    
    async def basic_future_example():
        print("=== Basic Future Example ===")
        
        # Create a new Future
        future = asyncio.Future()
        print(f"1. Created future: {future}")
        print(f"   Done: {future.done()}")
        print(f"   Cancelled: {future.cancelled()}")
        
        # Schedule the future to be resolved
        def resolve_future():
            if not future.done():
                future.set_result("Future resolved!")
                print("3. Future resolved by callback")
        
        # Schedule callback to run after 1 second
        loop = asyncio.get_running_loop()
        loop.call_later(1.0, resolve_future)
        
        print("2. Waiting for future...")
        
        # Await the future
        result = await future
        print(f"4. Future result: {result}")
        print(f"   Done: {future.done()}")
        
        return result
    
    return asyncio.run(basic_future_example())

demonstrate_basic_future()
```

### Future States and Lifecycle

```python
import asyncio

def demonstrate_future_states():
    """Show different states of Future objects"""
    
    async def future_states_example():
        print("=== Future States ===")
        
        # State 1: Pending
        future = asyncio.Future()
        print(f"1. Initial state:")
        print(f"   Done: {future.done()}")
        print(f"   Cancelled: {future.cancelled()}")
        
        try:
            # This would raise an exception since future isn't done
            # result = future.result()  # InvalidStateError
            print("   Result: Not available (pending)")
        except asyncio.InvalidStateError:
            print("   Result: Not available (InvalidStateError)")
        
        # State 2: Completed with result
        future.set_result("Success!")
        print(f"\n2. After setting result:")
        print(f"   Done: {future.done()}")
        print(f"   Result: {future.result()}")
        
        # State 3: Future with exception
        future_with_error = asyncio.Future()
        future_with_error.set_exception(ValueError("Something went wrong"))
        
        print(f"\n3. Future with exception:")
        print(f"   Done: {future_with_error.done()}")
        print(f"   Cancelled: {future_with_error.cancelled()}")
        
        try:
            future_with_error.result()
        except ValueError as e:
            print(f"   Exception: {e}")
        
        # State 4: Cancelled future
        cancelled_future = asyncio.Future()
        cancelled_future.cancel()
        
        print(f"\n4. Cancelled future:")
        print(f"   Done: {cancelled_future.done()}")
        print(f"   Cancelled: {cancelled_future.cancelled()}")
        
        try:
            cancelled_future.result()
        except asyncio.CancelledError:
            print("   Result: CancelledError raised")
        
        return "States demonstration complete"
    
    return asyncio.run(future_states_example())

demonstrate_future_states()
```

### Creating and Resolving Futures

```python
import asyncio
import random

async def demonstrate_future_creation():
    """Show different ways to create and resolve futures"""
    
    print("=== Future Creation and Resolution ===")
    
    # Method 1: Manual future creation and resolution
    print("1. Manual creation and resolution:")
    
    manual_future = asyncio.Future()
    
    async def delayed_resolver(future, delay, value):
        """Resolve future after delay"""
        await asyncio.sleep(delay)
        if not future.done():
            future.set_result(value)
    
    # Start resolver task
    resolver_task = asyncio.create_task(
        delayed_resolver(manual_future, 0.5, "Manual result")
    )
    
    print("   Waiting for manual future...")
    result = await manual_future
    print(f"   Result: {result}")
    
    # Method 2: Future with multiple potential resolvers
    print("\n2. Future with race condition:")
    
    race_future = asyncio.Future()
    
    async def competitor(future, competitor_id, delay):
        """Compete to resolve the future first"""
        await asyncio.sleep(delay)
        try:
            future.set_result(f"Winner: Competitor {competitor_id}")
            print(f"   Competitor {competitor_id} won!")
        except asyncio.InvalidStateError:
            print(f"   Competitor {competitor_id} was too late")
    
    # Start multiple competitors
    competitors = [
        asyncio.create_task(competitor(race_future, i, random.uniform(0.1, 0.5)))
        for i in range(3)
    ]
    
    winner = await race_future
    print(f"   Race result: {winner}")
    
    # Wait for all competitors to finish
    await asyncio.gather(*competitors, return_exceptions=True)
    
    # Method 3: Future factory pattern
    print("\n3. Future factory pattern:")
    
    def create_timeout_future(delay, value):
        """Factory function to create futures with timeout"""
        future = asyncio.Future()
        
        def resolve():
            if not future.done():
                future.set_result(value)
        
        loop = asyncio.get_running_loop()
        loop.call_later(delay, resolve)
        
        return future
    
    # Create multiple timeout futures
    timeout_futures = [
        create_timeout_future(0.2, f"Value {i}")
        for i in range(3)
    ]
    
    # Wait for all of them
    results = await asyncio.gather(*timeout_futures)
    print(f"   Timeout results: {results}")
    
    return "Future creation demonstration complete"

asyncio.run(demonstrate_future_creation())
```

### Future Callbacks

```python
import asyncio

async def demonstrate_future_callbacks():
    """Show how to use Future callbacks"""
    
    print("=== Future Callbacks ===")
    
    # Example 1: Basic callbacks
    print("1. Basic callbacks:")
    
    future = asyncio.Future()
    
    def on_future_done(fut):
        """Callback when future completes"""
        if fut.cancelled():
            print("   Callback: Future was cancelled")
        elif fut.exception():
            print(f"   Callback: Future failed with {fut.exception()}")
        else:
            print(f"   Callback: Future completed with {fut.result()}")
    
    # Add callback
    future.add_done_callback(on_future_done)
    
    # Resolve the future
    future.set_result("Callback test result")
    
    # Await to show callback fired before await returns
    result = await future
    print(f"   Await result: {result}")
    
    # Example 2: Multiple callbacks
    print("\n2. Multiple callbacks:")
    
    multi_future = asyncio.Future()
    
    def callback_1(fut):
        print(f"   Callback 1: {fut.result()}")
    
    def callback_2(fut):
        print(f"   Callback 2: Processing {fut.result()}")
    
    def callback_3(fut):
        print(f"   Callback 3: Final step with {fut.result()}")
    
    # Add multiple callbacks
    multi_future.add_done_callback(callback_1)
    multi_future.add_done_callback(callback_2)
    multi_future.add_done_callback(callback_3)
    
    # Callbacks fire in the order they were added
    multi_future.set_result("Multi-callback result")
    await multi_future
    
    # Example 3: Callback chains
    print("\n3. Callback chains:")
    
    def create_callback_chain():
        """Create a chain of futures using callbacks"""
        
        future1 = asyncio.Future()
        future2 = asyncio.Future()
        future3 = asyncio.Future()
        
        def on_future1_done(fut):
            if not fut.exception():
                result = fut.result()
                processed = f"Processed: {result}"
                future2.set_result(processed)
        
        def on_future2_done(fut):
            if not fut.exception():
                result = fut.result()
                final = f"Final: {result}"
                future3.set_result(final)
        
        future1.add_done_callback(on_future1_done)
        future2.add_done_callback(on_future2_done)
        
        return future1, future2, future3
    
    chain_start, chain_middle, chain_end = create_callback_chain()
    
    # Start the chain
    chain_start.set_result("Initial value")
    
    # Wait for chain to complete
    final_result = await chain_end
    print(f"   Chain result: {final_result}")
    
    return "Future callbacks demonstration complete"

asyncio.run(demonstrate_future_callbacks())
```

### Future Error Handling

```python
import asyncio

async def demonstrate_future_error_handling():
    """Show error handling with futures"""
    
    print("=== Future Error Handling ===")
    
    # Example 1: Setting exceptions on futures
    print("1. Setting exceptions:")
    
    error_future = asyncio.Future()
    
    def error_callback(fut):
        if fut.exception():
            print(f"   Error callback: {type(fut.exception()).__name__}: {fut.exception()}")
    
    error_future.add_done_callback(error_callback)
    
    # Set an exception instead of result
    error_future.set_exception(ValueError("Something went wrong!"))
    
    try:
        await error_future
    except ValueError as e:
        print(f"   Caught exception: {e}")
    
    # Example 2: Exception propagation in callback chains
    print("\n2. Exception propagation:")
    
    def create_error_chain():
        """Chain that handles errors"""
        
        future1 = asyncio.Future()
        future2 = asyncio.Future()
        
        def safe_processor(fut):
            try:
                if fut.exception():
                    # Propagate the exception
                    future2.set_exception(fut.exception())
                else:
                    result = fut.result()
                    if "error" in result.lower():
                        future2.set_exception(RuntimeError(f"Error in: {result}"))
                    else:
                        future2.set_result(f"Processed: {result}")
            except Exception as e:
                future2.set_exception(e)
        
        future1.add_done_callback(safe_processor)
        return future1, future2
    
    # Test with normal value
    start, end = create_error_chain()
    start.set_result("normal value")
    
    try:
        result = await end
        print(f"   Normal processing: {result}")
    except Exception as e:
        print(f"   Error in normal processing: {e}")
    
    # Test with error-triggering value
    start_error, end_error = create_error_chain()
    start_error.set_result("error value")
    
    try:
        result = await end_error
        print(f"   Error processing: {result}")
    except RuntimeError as e:
        print(f"   Expected error: {e}")
    
    # Example 3: Timeout with futures
    print("\n3. Future timeouts:")
    
    timeout_future = asyncio.Future()
    
    # This future will never be resolved
    # We'll use wait_for to add timeout
    
    try:
        result = await asyncio.wait_for(timeout_future, timeout=0.5)
        print(f"   Timeout result: {result}")
    except asyncio.TimeoutError:
        print("   Future timed out as expected")
    
    # Clean up the timeout future
    if not timeout_future.done():
        timeout_future.cancel()
    
    return "Future error handling demonstration complete"

asyncio.run(demonstrate_future_error_handling())
```

## 4.2 Future States and Callbacks

Understanding Future states and how to use callbacks effectively is crucial for advanced asyncio programming.

### Detailed Future State Management

```python
import asyncio
import enum
from typing import Any, Callable, Optional

class FutureState(enum.Enum):
    """Enum representing future states"""
    PENDING = "pending"
    FINISHED = "finished"
    CANCELLED = "cancelled"

class FutureMonitor:
    """Monitor and track Future state changes"""
    
    def __init__(self):
        self.state_changes = []
        self.callbacks_executed = []
    
    def get_future_state(self, future: asyncio.Future) -> FutureState:
        """Get current state of future"""
        if future.cancelled():
            return FutureState.CANCELLED
        elif future.done():
            return FutureState.FINISHED
        else:
            return FutureState.PENDING
    
    def create_state_callback(self, name: str) -> Callable:
        """Create callback that tracks state changes"""
        def callback(future):
            state = self.get_future_state(future)
            self.callbacks_executed.append((name, state))
            print(f"   {name} callback: Future is {state.value}")
            
            if state == FutureState.FINISHED:
                if future.exception():
                    print(f"     Exception: {future.exception()}")
                else:
                    print(f"     Result: {future.result()}")
        
        return callback
    
    def monitor_future(self, future: asyncio.Future, name: str):
        """Add monitoring to a future"""
        callback = self.create_state_callback(name)
        future.add_done_callback(callback)
        
        # Track initial state
        initial_state = self.get_future_state(future)
        self.state_changes.append((name, initial_state))
        print(f"   {name} initial state: {initial_state.value}")

async def demonstrate_detailed_state_management():
    """Demonstrate detailed future state management"""
    
    print("=== Detailed Future State Management ===")
    
    monitor = FutureMonitor()
    
    # Example 1: Normal completion
    print("1. Normal completion:")
    
    normal_future = asyncio.Future()
    monitor.monitor_future(normal_future, "normal")
    
    # Simulate async resolution
    async def resolve_after_delay(future, delay, result):
        await asyncio.sleep(delay)
        if not future.done():
            future.set_result(result)
    
    # Start resolution
    asyncio.create_task(resolve_after_delay(normal_future, 0.1, "Normal result"))
    
    # Wait for completion
    result = await normal_future
    print(f"   Final result: {result}")
    
    # Example 2: Exception completion
    print("\n2. Exception completion:")
    
    error_future = asyncio.Future()
    monitor.monitor_future(error_future, "error")
    
    async def reject_after_delay(future, delay, error):
        await asyncio.sleep(delay)
        if not future.done():
            future.set_exception(error)
    
    # Start rejection
    asyncio.create_task(reject_after_delay(error_future, 0.1, ValueError("Test error")))
    
    try:
        await error_future
    except ValueError as e:
        print(f"   Caught: {e}")
    
    # Example 3: Cancellation
    print("\n3. Cancellation:")
    
    cancel_future = asyncio.Future()
    monitor.monitor_future(cancel_future, "cancel")
    
    # Cancel immediately
    cancel_future.cancel()
    
    try:
        await cancel_future
    except asyncio.CancelledError:
        print("   Future was cancelled")
    
    print(f"\nMonitor summary:")
    print(f"   State changes: {len(monitor.state_changes)}")
    print(f"   Callbacks executed: {len(monitor.callbacks_executed)}")
    
    return monitor

asyncio.run(demonstrate_detailed_state_management())
```

### Advanced Callback Patterns

```python
import asyncio
from typing import List, Callable, Any
import weakref

class CallbackManager:
    """Advanced callback management for futures"""
    
    def __init__(self):
        self.callback_groups = {}
        self.callback_stats = {
            'total_registered': 0,
            'total_executed': 0,
            'execution_times': []
        }
    
    def add_callback_group(self, future: asyncio.Future, group_name: str, 
                          callbacks: List[Callable]):
        """Add a group of related callbacks"""
        self.callback_groups[group_name] = callbacks
        
        for i, callback in enumerate(callbacks):
            # Wrap callback to track execution
            wrapped_callback = self._wrap_callback(callback, f"{group_name}_{i}")
            future.add_done_callback(wrapped_callback)
            self.callback_stats['total_registered'] += 1
    
    def _wrap_callback(self, callback: Callable, name: str) -> Callable:
        """Wrap callback with timing and error handling"""
        def wrapper(future):
            start_time = asyncio.get_event_loop().time()
            
            try:
                callback(future)
                self.callback_stats['total_executed'] += 1
            except Exception as e:
                print(f"Callback {name} failed: {e}")
            finally:
                execution_time = asyncio.get_event_loop().time() - start_time
                self.callback_stats['execution_times'].append(execution_time)
        
        return wrapper
    
    def get_stats(self):
        """Get callback execution statistics"""
        times = self.callback_stats['execution_times']
        return {
            'registered': self.callback_stats['total_registered'],
            'executed': self.callback_stats['total_executed'],
            'avg_execution_time': sum(times) / len(times) if times else 0,
            'total_execution_time': sum(times)
        }

async def demonstrate_advanced_callbacks():
    """Demonstrate advanced callback patterns"""
    
    print("=== Advanced Callback Patterns ===")
    
    manager = CallbackManager()
    
    # Example 1: Callback groups
    print("1. Callback groups:")
    
    future = asyncio.Future()
    
    # Create different groups of callbacks
    logging_callbacks = [
        lambda f: print(f"   LOG: Future completed with {f.result()}"),
        lambda f: print(f"   AUDIT: Operation finished at {asyncio.get_event_loop().time()}")
    ]
    
    notification_callbacks = [
        lambda f: print(f"   NOTIFY: Sending notification for {f.result()}"),
        lambda f: print(f"   EMAIL: Sending email about {f.result()}")
    ]
    
    cleanup_callbacks = [
        lambda f: print(f"   CLEANUP: Cleaning up resources"),
        lambda f: print(f"   CACHE: Invalidating cache")
    ]
    
    # Add callback groups
    manager.add_callback_group(future, "logging", logging_callbacks)
    manager.add_callback_group(future, "notification", notification_callbacks)
    manager.add_callback_group(future, "cleanup", cleanup_callbacks)
    
    # Resolve the future
    future.set_result("Important data")
    await future
    
    # Show statistics
    stats = manager.get_stats()
    print(f"   Callback stats: {stats}")
    
    # Example 2: Conditional callbacks
    print("\n2. Conditional callbacks:")
    
    conditional_future = asyncio.Future()
    
    def success_callback(fut):
        if not fut.exception():
            print(f"   SUCCESS: {fut.result()}")
    
    def error_callback(fut):
        if fut.exception():
            print(f"   ERROR: {fut.exception()}")
    
    def always_callback(fut):
        print(f"   ALWAYS: Operation completed")
    
    conditional_future.add_done_callback(success_callback)
    conditional_future.add_done_callback(error_callback)
    conditional_future.add_done_callback(always_callback)
    
    # Test with success
    conditional_future.set_result("Success value")
    await conditional_future
    
    # Example 3: Weak reference callbacks (avoid memory leaks)
    print("\n3. Weak reference callbacks:")
    
    class CallbackOwner:
        def __init__(self, name):
            self.name = name
        
        def my_callback(self, future):
            print(f"   {self.name}: Callback executed")
    
    weak_future = asyncio.Future()
    owner = CallbackOwner("WeakOwner")
    
    # Use weak reference to avoid keeping owner alive
    weak_ref = weakref.ref(owner)
    
    def weak_callback(fut):
        owner_instance = weak_ref()
        if owner_instance is not None:
            owner_instance.my_callback(fut)
        else:
            print("   Owner was garbage collected")
    
    weak_future.add_done_callback(weak_callback)
    
    # Resolve while owner exists
    weak_future.set_result("Weak test")
    await weak_future
    
    # Delete owner and test again
    del owner
    import gc
    gc.collect()
    
    # This would show owner was garbage collected if we created another future
    
    return "Advanced callback demonstration complete"

asyncio.run(demonstrate_advanced_callbacks())
```

### Future Composition with Callbacks

```python
import asyncio
from typing import List, Callable, TypeVar, Generic

T = TypeVar('T')
U = TypeVar('U')

class ComposableFuture(Generic[T]):
    """Future that supports functional composition"""
    
    def __init__(self, future: asyncio.Future[T]):
        self.future = future
    
    def then(self, callback: Callable[[T], U]) -> 'ComposableFuture[U]':
        """Chain a transformation callback"""
        new_future = asyncio.Future()
        
        def transform_callback(fut):
            try:
                if fut.exception():
                    new_future.set_exception(fut.exception())
                else:
                    result = callback(fut.result())
                    new_future.set_result(result)
            except Exception as e:
                new_future.set_exception(e)
        
        self.future.add_done_callback(transform_callback)
        return ComposableFuture(new_future)
    
    def catch(self, error_handler: Callable[[Exception], T]) -> 'ComposableFuture[T]':
        """Handle errors in the chain"""
        new_future = asyncio.Future()
        
        def error_callback(fut):
            try:
                if fut.exception():
                    result = error_handler(fut.exception())
                    new_future.set_result(result)
                else:
                    new_future.set_result(fut.result())
            except Exception as e:
                new_future.set_exception(e)
        
        self.future.add_done_callback(error_callback)
        return ComposableFuture(new_future)
    
    def finally_do(self, cleanup: Callable[[], None]) -> 'ComposableFuture[T]':
        """Add cleanup that always runs"""
        new_future = asyncio.Future()
        
        def cleanup_callback(fut):
            try:
                cleanup()
                if fut.exception():
                    new_future.set_exception(fut.exception())
                else:
                    new_future.set_result(fut.result())
            except Exception as e:
                new_future.set_exception(e)
        
        self.future.add_done_callback(cleanup_callback)
        return ComposableFuture(new_future)
    
    async def __await__(self):
        return await self.future

async def demonstrate_future_composition():
    """Demonstrate future composition patterns"""
    
    print("=== Future Composition ===")
    
    # Example 1: Basic chaining
    print("1. Basic chaining:")
    
    initial_future = asyncio.Future()
    
    # Create composable chain
    composable = (ComposableFuture(initial_future)
                  .then(lambda x: x * 2)
                  .then(lambda x: f"Result: {x}")
                  .then(lambda x: x.upper())
                  .catch(lambda e: f"Error: {e}")
                  .finally_do(lambda: print("   Cleanup executed")))
    
    # Resolve initial future
    initial_future.set_result(5)
    
    result = await composable
    print(f"   Chain result: {result}")
    
    # Example 2: Error handling in chain
    print("\n2. Error handling in chain:")
    
    error_future = asyncio.Future()
    
    error_chain = (ComposableFuture(error_future)
                   .then(lambda x: x / 0)  # This will cause error
                   .then(lambda x: f"Won't reach here: {x}")
                   .catch(lambda e: f"Handled error: {type(e).__name__}")
                   .finally_do(lambda: print("   Error cleanup executed")))
    
    error_future.set_result(10)
    
    error_result = await error_chain
    print(f"   Error chain result: {error_result}")
    
    # Example 3: Multiple future combination
    print("\n3. Multiple future combination:")
    
    def combine_futures(*composable_futures):
        """Combine multiple composable futures"""
        combined_future = asyncio.Future()
        results = {}
        completed_count = 0
        
        def on_completion(index, fut):
            nonlocal completed_count
            try:
                if fut.exception():
                    combined_future.set_exception(fut.exception())
                    return
                
                results[index] = fut.result()
                completed_count += 1
                
                if completed_count == len(composable_futures):
                    # All completed successfully
                    final_results = [results[i] for i in range(len(composable_futures))]
                    combined_future.set_result(final_results)
            except Exception as e:
                combined_future.set_exception(e)
        
        for i, comp_future in enumerate(composable_futures):
            comp_future.future.add_done_callback(
                lambda fut, idx=i: on_completion(idx, fut)
            )
        
        return ComposableFuture(combined_future)
    
    # Create multiple futures
    future1 = asyncio.Future()
    future2 = asyncio.Future()
    future3 = asyncio.Future()
    
    comp1 = ComposableFuture(future1).then(lambda x: x + 1)
    comp2 = ComposableFuture(future2).then(lambda x: x * 2)
    comp3 = ComposableFuture(future3).then(lambda x: x.upper())
    
    # Combine them
    combined = combine_futures(comp1, comp2, comp3)
    
    # Resolve individual futures
    future1.set_result(5)
    future2.set_result(3)
    future3.set_result("hello")
    
    combined_result = await combined
    print(f"   Combined result: {combined_result}")
    
    return "Future composition demonstration complete"

asyncio.run(demonstrate_future_composition())
```

## 4.3 Tasks: Scheduled Coroutines

Tasks are a subclass of Future that wrap coroutines and schedule them for execution. Understanding tasks is crucial for managing concurrent operations in asyncio.

### Basic Task Creation and Management

```python
import asyncio
import time

async def example_coroutine(name, duration):
    """Example coroutine for task demonstrations"""
    print(f"{name}: Starting")
    await asyncio.sleep(duration)
    print(f"{name}: Completed after {duration}s")
    return f"{name}_result"

async def demonstrate_basic_tasks():
    """Demonstrate basic task creation and management"""
    
    print("=== Basic Task Management ===")
    
    # Method 1: Creating tasks with asyncio.create_task()
    print("1. Creating tasks with create_task():")
    
    # Create a task (starts execution immediately)
    task1 = asyncio.create_task(example_coroutine("Task1", 1.0))
    print(f"   Created task: {task1}")
    print(f"   Task done: {task1.done()}")
    print(f"   Task cancelled: {task1.cancelled()}")
    
    # Wait a bit and check status
    await asyncio.sleep(0.5)
    print(f"   After 0.5s - Task done: {task1.done()}")
    
    # Wait for completion
    result1 = await task1
    print(f"   Task result: {result1}")
    print(f"   Final task done: {task1.done()}")
    
    # Method 2: Creating multiple tasks
    print("\n2. Creating multiple tasks:")
    
    start_time = time.time()
    
    # Create multiple tasks that run concurrently
    tasks = [
        asyncio.create_task(example_coroutine(f"Multi_{i}", 0.5))
        for i in range(3)
    ]
    
    print(f"   Created {len(tasks)} tasks")
    
    # Wait for all tasks to complete
    results = await asyncio.gather(*tasks)
    
    end_time = time.time()
    print(f"   All tasks completed in {end_time - start_time:.2f}s")
    print(f"   Results: {results}")
    
    # Method 3: Task with name (Python 3.8+)
    print("\n3. Named tasks:")
    
    named_task = asyncio.create_task(
        example_coroutine("Named", 0.2),
        name="MyNamedTask"
    )
    
    print(f"   Task name: {named_task.get_name()}")
    
    # Can change the name
    named_task.set_name("RenamedTask")
    print(f"   New task name: {named_task.get_name()}")
    
    await named_task
    
    return "Basic task demonstration complete"

asyncio.run(demonstrate_basic_tasks())
```

### Task Introspection and Monitoring

```python
import asyncio
import sys

class TaskMonitor:
    """Monitor running tasks"""
    
    def __init__(self):
        self.created_tasks = []
        self.completed_tasks = []
    
    def create_monitored_task(self, coro, name=None):
        """Create a task with monitoring"""
        task = asyncio.create_task(coro, name=name)
        self.created_tasks.append(task)
        
        # Add completion callback
        def on_completion(t):
            self.completed_tasks.append(t)
            print(f"   Monitor: Task {t.get_name()} completed")
        
        task.add_done_callback(on_completion)
        return task
    
    def get_active_tasks(self):
        """Get currently active tasks"""
        return [t for t in self.created_tasks if not t.done()]
    
    def get_stats(self):
        """Get monitoring statistics"""
        return {
            'created': len(self.created_tasks),
            'completed': len(self.completed_tasks),
            'active': len(self.get_active_tasks())
        }

async def demonstrate_task_introspection():
    """Demonstrate task introspection and monitoring"""
    
    print("=== Task Introspection ===")
    
    monitor = TaskMonitor()
    
    # Create some tasks
    task1 = monitor.create_monitored_task(
        example_coroutine("Monitored1", 0.3),
        name="MonitoredTask1"
    )
    
    task2 = monitor.create_monitored_task(
        example_coroutine("Monitored2", 0.5),
        name="MonitoredTask2"
    )
    
    task3 = monitor.create_monitored_task(
        example_coroutine("Monitored3", 0.2),
        name="MonitoredTask3"
    )
    
    print(f"1. Initial stats: {monitor.get_stats()}")
    
    # Get all currently running tasks in the event loop
    all_tasks = asyncio.all_tasks()
    print(f"   All tasks in event loop: {len(all_tasks)}")
    
    for task in all_tasks:
        print(f"   Task: {task.get_name()} - Done: {task.done()}")
    
    # Wait for some tasks to complete
    await asyncio.sleep(0.4)
    print(f"\n2. After 0.4s: {monitor.get_stats()}")
    
    # Show detailed task information
    print("\n3. Task details:")
    for task in monitor.created_tasks:
        print(f"   {task.get_name()}:")
        print(f"     Done: {task.done()}")
        print(f"     Cancelled: {task.cancelled()}")
        
        if task.done() and not task.cancelled():
            try:
                result = task.result()
                print(f"     Result: {result}")
            except Exception as e:
                print(f"     Exception: {e}")
        
        # Stack trace for running tasks
        if not task.done():
            print(f"     Stack: {task.get_stack()}")
    
    # Wait for remaining tasks
    await asyncio.gather(*monitor.get_active_tasks())
    
    print(f"\n4. Final stats: {monitor.get_stats()}")
    
    return monitor

asyncio.run(demonstrate_task_introspection())
```

### Task Lifecycle Management

```python
import asyncio
from enum import Enum

class TaskState(Enum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class TaskLifecycleManager:
    """Manage complete task lifecycle"""
    
    def __init__(self):
        self.tasks = {}
        self.state_history = {}
    
    def create_task(self, coro, task_id, name=None):
        """Create and track a task"""
        task = asyncio.create_task(coro, name=name or f"Task-{task_id}")
        
        self.tasks[task_id] = {
            'task': task,
            'created_at': asyncio.get_event_loop().time(),
            'state': TaskState.CREATED
        }
        
        self.state_history[task_id] = [TaskState.CREATED]
        
        # Add state tracking callback
        def track_completion(t):
            self._update_task_state(task_id, t)
        
        task.add_done_callback(track_completion)
        
        # Mark as running (since create_task starts immediately)
        self._update_state(task_id, TaskState.RUNNING)
        
        return task
    
    def _update_state(self, task_id, state):
        """Update task state"""
        if task_id in self.tasks:
            self.tasks[task_id]['state'] = state
            self.state_history[task_id].append(state)
    
    def _update_task_state(self, task_id, task):
        """Update state based on task completion"""
        if task.cancelled():
            self._update_state(task_id, TaskState.CANCELLED)
        elif task.exception():
            self._update_state(task_id, TaskState.FAILED)
        else:
            self._update_state(task_id, TaskState.COMPLETED)
    
    def get_task_info(self, task_id):
        """Get detailed task information"""
        if task_id not in self.tasks:
            return None
        
        info = self.tasks[task_id].copy()
        task = info['task']
        
        info.update({
            'current_state': info['state'],
            'state_history': self.state_history[task_id].copy(),
            'done': task.done(),
            'cancelled': task.cancelled(),
            'running_time': asyncio.get_event_loop().time() - info['created_at']
        })
        
        if task.done():
            if task.exception():
                info['exception'] = task.exception()
            elif not task.cancelled():
                info['result'] = task.result()
        
        return info
    
    def cancel_task(self, task_id):
        """Cancel a specific task"""
        if task_id in self.tasks:
            task = self.tasks[task_id]['task']
            if not task.done():
                task.cancel()
                return True
        return False
    
    async def shutdown_all(self):
        """Shutdown all managed tasks"""
        print("   Shutting down all tasks...")
        
        active_tasks = [
            info['task'] for info in self.tasks.values()
            if not info['task'].done()
        ]
        
        # Cancel all active tasks
        for task in active_tasks:
            task.cancel()
        
        # Wait for cancellation to complete
        if active_tasks:
            await asyncio.gather(*active_tasks, return_exceptions=True)
        
        print(f"   Shutdown complete: {len(active_tasks)} tasks cancelled")

async def demonstrate_task_lifecycle():
    """Demonstrate complete task lifecycle management"""
    
    print("=== Task Lifecycle Management ===")
    
    manager = TaskLifecycleManager()
    
    # Create tasks with different behaviors
    async def normal_task(duration):
        await asyncio.sleep(duration)
        return f"completed after {duration}s"
    
    async def failing_task(delay):
        await asyncio.sleep(delay)
        raise ValueError("Task failed!")
    
    async def long_running_task():
        for i in range(100):
            await asyncio.sleep(0.1)
            print(f"   Long task iteration {i}")
        return "long task done"
    
    # Create various tasks
    task1 = manager.create_task(normal_task(0.5), "task1", "NormalTask")
    task2 = manager.create_task(failing_task(0.3), "task2", "FailingTask")
    task3 = manager.create_task(long_running_task(), "task3", "LongTask")
    
    print("1. Created 3 tasks")
    
    # Monitor task progress
    await asyncio.sleep(0.2)
    print("\n2. After 0.2s:")
    for task_id in ["task1", "task2", "task3"]:
        info = manager.get_task_info(task_id)
        print(f"   {task_id}: {info['current_state'].value} "
              f"(running for {info['running_time']:.2f}s)")
    
    # Wait for some tasks to complete
    await asyncio.sleep(0.5)
    print("\n3. After 0.7s total:")
    for task_id in ["task1", "task2", "task3"]:
        info = manager.get_task_info(task_id)
        print(f"   {task_id}: {info['current_state'].value}")
        
        if 'result' in info:
            print(f"     Result: {info['result']}")
        elif 'exception' in info:
            print(f"     Exception: {info['exception']}")
        
        print(f"     State history: {[s.value for s in info['state_history']]}")
    
    # Cancel the long-running task
    print("\n4. Cancelling long-running task:")
    cancelled = manager.cancel_task("task3")
    print(f"   Cancellation requested: {cancelled}")
    
    # Wait for cancellation
    try:
        await task3
    except asyncio.CancelledError:
        print("   Long task was cancelled")
    
    # Final state
    print("\n5. Final states:")
    for task_id in ["task1", "task2", "task3"]:
        info = manager.get_task_info(task_id)
        print(f"   {task_id}: {info['current_state'].value}")
    
    return manager

asyncio.run(demonstrate_task_lifecycle())
```

## 4.4 Creating and Managing Tasks

Effective task management is crucial for building robust async applications. This section covers advanced patterns for creating and managing tasks.

### Task Creation Patterns

```python
import asyncio
from typing import List, Dict, Any, Optional, Callable
import functools

class TaskFactory:
    """Factory for creating different types of tasks"""
    
    def __init__(self):
        self.task_counter = 0
        self.task_registry = {}
    
    def create_simple_task(self, coro, name=None):
        """Create a simple task with automatic naming"""
        task_id = self._get_next_id()
        task_name = name or f"SimpleTask-{task_id}"
        
        task = asyncio.create_task(coro, name=task_name)
        self.task_registry[task_id] = task
        
        return task_id, task
    
    def create_retry_task(self, coro_func, max_retries=3, delay=1.0, name=None):
        """Create a task with built-in retry logic"""
        task_id = self._get_next_id()
        task_name = name or f"RetryTask-{task_id}"
        
        async def retry_wrapper():
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await coro_func()
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries:
                        print(f"   {task_name} attempt {attempt + 1} failed: {e}")
                        await asyncio.sleep(delay)
                    else:
                        print(f"   {task_name} exhausted all retries")
                        raise
        
        task = asyncio.create_task(retry_wrapper(), name=task_name)
        self.task_registry[task_id] = task
        
        return task_id, task
    
    def create_timeout_task(self, coro, timeout, name=None):
        """Create a task with timeout"""
        task_id = self._get_next_id()
        task_name = name or f"TimeoutTask-{task_id}"
        
        async def timeout_wrapper():
            try:
                return await asyncio.wait_for(coro, timeout=timeout)
            except asyncio.TimeoutError:
                print(f"   {task_name} timed out after {timeout}s")
                raise
        
        task = asyncio.create_task(timeout_wrapper(), name=task_name)
        self.task_registry[task_id] = task
        
        return task_id, task
    
    def create_periodic_task(self, coro_func, interval, max_iterations=None, name=None):
        """Create a task that runs periodically"""
        task_id = self._get_next_id()
        task_name = name or f"PeriodicTask-{task_id}"
        
        async def periodic_wrapper():
            iteration = 0
            results = []
            
            while max_iterations is None or iteration < max_iterations:
                try:
                    result = await coro_func()
                    results.append(result)
                    print(f"   {task_name} iteration {iteration + 1}: {result}")
                    
                    iteration += 1
                    
                    if max_iterations is None or iteration < max_iterations:
                        await asyncio.sleep(interval)
                
                except asyncio.CancelledError:
                    print(f"   {task_name} cancelled after {iteration} iterations")
                    break
                except Exception as e:
                    print(f"   {task_name} error in iteration {iteration + 1}: {e}")
                    results.append(f"error: {e}")
                    iteration += 1
                    
                    if max_iterations is None or iteration < max_iterations:
                        await asyncio.sleep(interval)
            
            return results
        
        task = asyncio.create_task(periodic_wrapper(), name=task_name)
        self.task_registry[task_id] = task
        
        return task_id, task
    
    def _get_next_id(self):
        """Get next task ID"""
        self.task_counter += 1
        return self.task_counter
    
    def get_task(self, task_id):
        """Get task by ID"""
        return self.task_registry.get(task_id)
    
    def get_all_tasks(self):
        """Get all created tasks"""
        return self.task_registry.copy()

async def demonstrate_task_creation_patterns():
    """Demonstrate different task creation patterns"""
    
    print("=== Task Creation Patterns ===")
    
    factory = TaskFactory()
    
    # Example 1: Simple task
    print("1. Simple task:")
    
    async def simple_work():
        await asyncio.sleep(0.3)
        return "Simple work done"
    
    simple_id, simple_task = factory.create_simple_task(simple_work())
    result = await simple_task
    print(f"   Result: {result}")
    
    # Example 2: Retry task
    print("\n2. Retry task:")
    
    attempt_count = 0
    async def unreliable_work():
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count < 3:
            raise ValueError(f"Attempt {attempt_count} failed")
        return f"Success on attempt {attempt_count}"
    
    retry_id, retry_task = factory.create_retry_task(
        unreliable_work, max_retries=3, delay=0.1, name="ReliableTask"
    )
    retry_result = await retry_task
    print(f"   Retry result: {retry_result}")
    
    # Example 3: Timeout task
    print("\n3. Timeout task:")
    
    async def slow_work():
        await asyncio.sleep(2.0)  # Takes too long
        return "Slow work done"
    
    timeout_id, timeout_task = factory.create_timeout_task(
        slow_work(), timeout=0.5, name="QuickTask"
    )
    
    try:
        timeout_result = await timeout_task
        print(f"   Timeout result: {timeout_result}")
    except asyncio.TimeoutError:
        print("   Task timed out as expected")
    
    # Example 4: Periodic task
    print("\n4. Periodic task:")
    
    counter = 0
    async def periodic_work():
        nonlocal counter
        counter += 1
        return f"Periodic work #{counter}"
    
    periodic_id, periodic_task = factory.create_periodic_task(
        periodic_work, interval=0.2, max_iterations=3, name="PeriodicWorker"
    )
    
    periodic_results = await periodic_task
    print(f"   Periodic results: {periodic_results}")
    
    return factory

asyncio.run(demonstrate_task_creation_patterns())
```

### Task Pools and Workers

```python
import asyncio
from asyncio import Queue
from typing import List, Callable, Any, Optional
import time

class TaskPool:
    """Pool of worker tasks that process jobs from a queue"""
    
    def __init__(self, worker_count: int = 3, queue_size: int = 10):
        self.worker_count = worker_count
        self.work_queue = Queue(maxsize=queue_size)
        self.result_queue = Queue()
        self.workers = []
        self.running = False
        self.stats = {
            'jobs_submitted': 0,
            'jobs_completed': 0,
            'jobs_failed': 0,
            'total_processing_time': 0
        }
    
    async def start(self):
        """Start the task pool"""
        if self.running:
            return
        
        self.running = True
        
        # Create worker tasks
        for i in range(self.worker_count):
            worker = asyncio.create_task(
                self._worker(f"Worker-{i+1}"),
                name=f"PoolWorker-{i+1}"
            )
            self.workers.append(worker)
        
        print(f"Task pool started with {self.worker_count} workers")
    
    async def submit(self, coro_func: Callable, *args, **kwargs):
        """Submit a job to the pool"""
        if not self.running:
            raise RuntimeError("Task pool not started")
        
        job_id = self.stats['jobs_submitted'] + 1
        job = {
            'id': job_id,
            'func': coro_func,
            'args': args,
            'kwargs': kwargs,
            'submitted_at': time.time()
        }
        
        await self.work_queue.put(job)
        self.stats['jobs_submitted'] += 1
        
        return job_id
    
    async def get_result(self, timeout=None):
        """Get a completed job result"""
        try:
            return await asyncio.wait_for(self.result_queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None
    
    async def _worker(self, worker_name: str):
        """Worker coroutine that processes jobs"""
        print(f"   {worker_name}: Started")
        
        while self.running:
            try:
                # Get job from queue
                job = await asyncio.wait_for(self.work_queue.get(), timeout=1.0)
                
                start_time = time.time()
                
                try:
                    # Execute the job
                    result = await job['func'](*job['args'], **job['kwargs'])
                    
                    # Calculate processing time
                    processing_time = time.time() - start_time
                    
                    # Put result in result queue
                    result_data = {
                        'job_id': job['id'],
                        'result': result,
                        'worker': worker_name,
                        'processing_time': processing_time,
                        'status': 'success'
                    }
                    
                    await self.result_queue.put(result_data)
                    
                    self.stats['jobs_completed'] += 1
                    self.stats['total_processing_time'] += processing_time
                    
                    print(f"   {worker_name}: Completed job {job['id']} in {processing_time:.3f}s")
                
                except Exception as e:
                    # Handle job failure
                    result_data = {
                        'job_id': job['id'],
                        'error': str(e),
                        'worker': worker_name,
                        'status': 'failed'
                    }
                    
                    await self.result_queue.put(result_data)
                    self.stats['jobs_failed'] += 1
                    
                    print(f"   {worker_name}: Job {job['id']} failed: {e}")
                
                finally:
                    self.work_queue.task_done()
            
            except asyncio.TimeoutError:
                # No jobs available, continue checking
                continue
            except asyncio.CancelledError:
                print(f"   {worker_name}: Cancelled")
                break
        
        print(f"   {worker_name}: Stopped")
    
    async def stop(self, timeout=5.0):
        """Stop the task pool"""
        if not self.running:
            return
        
        print("Stopping task pool...")
        self.running = False
        
        # Cancel all workers
        for worker in self.workers:
            worker.cancel()
        
        # Wait for workers to stop
        try:
            await asyncio.wait_for(
                asyncio.gather(*self.workers, return_exceptions=True),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            print("Warning: Some workers did not stop within timeout")
        
        self.workers.clear()
        print("Task pool stopped")
    
    def get_stats(self):
        """Get pool statistics"""
        stats = self.stats.copy()
        
        if stats['jobs_completed'] > 0:
            stats['avg_processing_time'] = (
                stats['total_processing_time'] / stats['jobs_completed']
            )
        else:
            stats['avg_processing_time'] = 0
        
        stats['queue_size'] = self.work_queue.qsize()
        stats['pending_results'] = self.result_queue.qsize()
        
        return stats

async def demonstrate_task_pools():
    """Demonstrate task pool usage"""
    
    print("=== Task Pool Demonstration ===")
    
    # Create task pool
    pool = TaskPool(worker_count=3, queue_size=5)
    
    # Start the pool
    await pool.start()
    
    # Define some work functions
    async def cpu_intensive_work(duration, data):
        """Simulate CPU-intensive work"""
        await asyncio.sleep(duration)  # Simulate work
        return f"Processed {data} in {duration}s"
    
    async def io_work(url):
        """Simulate I/O work"""
        await asyncio.sleep(0.2)  # Simulate I/O
        return f"Fetched data from {url}"
    
    async def unreliable_work(job_id):
        """Work that sometimes fails"""
        await asyncio.sleep(0.1)
        if job_id % 3 == 0:
            raise ValueError(f"Job {job_id} failed")
        return f"Job {job_id} succeeded"
    
    # Submit various jobs
    print("\n1. Submitting jobs:")
    
    job_ids = []
    
    # Submit CPU-intensive jobs
    for i in range(3):
        job_id = await pool.submit(cpu_intensive_work, 0.3, f"data_{i}")
        job_ids.append(job_id)
        print(f"   Submitted CPU job {job_id}")
    
    # Submit I/O jobs
    for i in range(4):
        job_id = await pool.submit(io_work, f"http://api{i}.example.com")
        job_ids.append(job_id)
        print(f"   Submitted I/O job {job_id}")
    
    # Submit unreliable jobs
    for i in range(5):
        job_id = await pool.submit(unreliable_work, i + 1)
        job_ids.append(job_id)
        print(f"   Submitted unreliable job {job_id}")
    
    print(f"   Total jobs submitted: {len(job_ids)}")
    
    # Collect results
    print("\n2. Collecting results:")
    
    results = []
    for _ in range(len(job_ids)):
        result = await pool.get_result(timeout=2.0)
        if result:
            results.append(result)
            status = result['status']
            if status == 'success':
                print(f"   Job {result['job_id']}: {result['result']}")
            else:
                print(f"   Job {result['job_id']}: FAILED - {result['error']}")
        else:
            print("   Timeout waiting for result")
            break
    
    # Show statistics
    print(f"\n3. Pool statistics:")
    stats = pool.get_stats()
    for key, value in stats.items():
        if key == 'avg_processing_time':
            print(f"   {key}: {value:.3f}s")
        else:
            print(f"   {key}: {value}")
    
    # Stop the pool
    await pool.stop()
    
    return pool

asyncio.run(demonstrate_task_pools())
```

This completes the first part of Chapter 4. The chapter comprehensively covers Futures and the beginning of Tasks. Would you like me to continue with the remaining sections (4.5 Task Cancellation, 4.6 Task Groups, 4.7 Gathering Results, and 4.8 Racing)?
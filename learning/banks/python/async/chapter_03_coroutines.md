# Chapter 3: Coroutines - The Building Blocks

## 3.1 Generator-Based Coroutines (Legacy)

Before diving into modern `async`/`await` syntax, it's important to understand the historical foundation of asyncio coroutines. Generator-based coroutines were the original implementation and understanding them provides insight into how modern asyncio works under the hood.

### What are Generator-Based Coroutines?

Generator-based coroutines use Python's generator functions with special decorators to create coroutine-like behavior:

```python
import asyncio
from asyncio import coroutine

# Legacy generator-based coroutine (Python 3.4-3.7)
@coroutine
def legacy_coroutine():
    print("Starting legacy coroutine")
    yield from asyncio.sleep(1)  # yield from instead of await
    print("Legacy coroutine completed")
    return "Legacy result"

def demonstrate_legacy_coroutines():
    """Show how legacy coroutines work"""
    
    # Multiple ways to define generator coroutines
    
    # Method 1: Using @asyncio.coroutine decorator
    @asyncio.coroutine
    def method_1():
        result = yield from asyncio.sleep(0.1, result="Method 1 done")
        return result
    
    # Method 2: Plain generator function (less common)
    def method_2():
        print("Method 2 starting")
        yield from asyncio.sleep(0.1)
        print("Method 2 completed")
        return "Method 2 done"
    
    # Method 3: Generator that yields futures
    def method_3():
        print("Method 3 starting")
        future = asyncio.Future()
        
        # Schedule future completion
        loop = asyncio.get_event_loop()
        loop.call_later(0.1, future.set_result, "Method 3 done")
        
        result = yield future  # Yield the future directly
        print("Method 3 completed")
        return result
    
    # Run legacy coroutines
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        result1 = loop.run_until_complete(method_1())
        print(f"Result 1: {result1}")
        
        result2 = loop.run_until_complete(method_2())
        print(f"Result 2: {result2}")
        
        result3 = loop.run_until_complete(method_3())
        print(f"Result 3: {result3}")
        
    finally:
        loop.close()

# Run demonstration (if you want to see legacy behavior)
# demonstrate_legacy_coroutines()
```

### yield from vs await

The `yield from` syntax in generator coroutines is the predecessor to `await`:

```python
import asyncio

# Legacy style with yield from
@asyncio.coroutine
def legacy_fetch_data(url):
    print(f"Fetching {url}")
    
    # yield from delegates to another coroutine/generator
    response = yield from asyncio.sleep(1, result=f"Data from {url}")
    
    # Process response
    processed = yield from process_data(response)
    
    return processed

@asyncio.coroutine
def process_data(data):
    print(f"Processing {data}")
    yield from asyncio.sleep(0.5)  # Simulate processing time
    return f"Processed: {data}"

# Modern style with async/await
async def modern_fetch_data(url):
    print(f"Fetching {url}")
    
    # await is cleaner and more intuitive
    response = await asyncio.sleep(1, result=f"Data from {url}")
    
    # Process response
    processed = await process_data_modern(response)
    
    return processed

async def process_data_modern(data):
    print(f"Processing {data}")
    await asyncio.sleep(0.5)  # Simulate processing time
    return f"Processed: {data}"

async def compare_syntax():
    """Compare legacy and modern syntax"""
    
    print("=== Legacy coroutine ===")
    legacy_result = await legacy_fetch_data("https://api.example.com/data")
    print(f"Legacy result: {legacy_result}")
    
    print("\n=== Modern coroutine ===")
    modern_result = await modern_fetch_data("https://api.example.com/data")
    print(f"Modern result: {modern_result}")

# asyncio.run(compare_syntax())
```

### Why Generator-Based Coroutines Were Used

Generator-based coroutines were necessary because:

1. **Python limitations**: Before Python 3.5, there was no `async`/`await` syntax
2. **Backwards compatibility**: Needed to work with existing generator-based code
3. **Gradual adoption**: Allowed incremental migration to async programming

```python
# Generator coroutines were built on Python's existing generator protocol
def understand_generator_protocol():
    """Understand how generators enable coroutine behavior"""
    
    def simple_generator():
        print("Generator starts")
        value = yield "First value"
        print(f"Received: {value}")
        
        value = yield "Second value"
        print(f"Received: {value}")
        
        return "Generator complete"
    
    # Manual generator driving (what the event loop does)
    gen = simple_generator()
    
    # Start generator
    first_value = next(gen)
    print(f"Generator yielded: {first_value}")
    
    # Send value back to generator
    try:
        second_value = gen.send("Hello from caller")
        print(f"Generator yielded: {second_value}")
        
        # Send final value
        gen.send("Goodbye")
        
    except StopIteration as e:
        print(f"Generator returned: {e.value}")

understand_generator_protocol()
```

### Legacy Patterns to Avoid

While understanding legacy coroutines is educational, avoid these patterns in new code:

```python
import asyncio

# DON'T: Mix generator and async syntax
@asyncio.coroutine  # Legacy decorator
def mixed_bad_example():
    # This mixing can cause issues
    result = yield from some_async_function()  # Legacy
    return result

async def some_async_function():
    await asyncio.sleep(0.1)
    return "result"

# DON'T: Use @asyncio.coroutine for new code
@asyncio.coroutine
def deprecated_pattern():
    yield from asyncio.sleep(1)
    return "Avoid this pattern"

# DO: Use modern async/await syntax
async def preferred_pattern():
    await asyncio.sleep(1)
    return "Use this pattern instead"

# DON'T: Manual generator manipulation in async code
def manual_generator_bad():
    async def coro():
        await asyncio.sleep(1)
        return "result"
    
    # Don't manually drive coroutines like generators
    c = coro()
    try:
        c.send(None)  # This is what the event loop should do
    except StopIteration:
        pass
    finally:
        c.close()

# DO: Let asyncio manage coroutines
async def proper_coroutine_usage():
    result = await some_async_function()
    return result
```

## 3.2 Native Coroutines with async/await

Modern asyncio uses native coroutines defined with `async def` and called with `await`. This is the preferred and only recommended way to write async code in Python 3.5+.

### Basic async/await Syntax

```python
import asyncio
import time

# Basic coroutine definition
async def simple_coroutine():
    """A simple async function"""
    print("Coroutine started")
    await asyncio.sleep(1)
    print("Coroutine completed")
    return "Simple result"

# Coroutine with parameters
async def parameterized_coroutine(name, delay):
    """Coroutine that accepts parameters"""
    print(f"{name}: Starting with {delay}s delay")
    await asyncio.sleep(delay)
    print(f"{name}: Completed")
    return f"{name} finished after {delay}s"

# Coroutine that calls other coroutines
async def composite_coroutine():
    """Coroutine that orchestrates other coroutines"""
    print("Starting composite operation")
    
    # Sequential execution
    result1 = await parameterized_coroutine("Task 1", 0.5)
    result2 = await parameterized_coroutine("Task 2", 0.3)
    
    # Concurrent execution
    task3 = asyncio.create_task(parameterized_coroutine("Task 3", 0.4))
    task4 = asyncio.create_task(parameterized_coroutine("Task 4", 0.2))
    
    # Wait for concurrent tasks
    result3 = await task3
    result4 = await task4
    
    return [result1, result2, result3, result4]

async def demonstrate_basic_syntax():
    """Demonstrate basic async/await usage"""
    
    print("=== Simple Coroutine ===")
    simple_result = await simple_coroutine()
    print(f"Result: {simple_result}")
    
    print("\n=== Parameterized Coroutine ===")
    param_result = await parameterized_coroutine("Demo", 0.5)
    print(f"Result: {param_result}")
    
    print("\n=== Composite Coroutine ===")
    start_time = time.time()
    composite_result = await composite_coroutine()
    end_time = time.time()
    
    print(f"Results: {composite_result}")
    print(f"Total time: {end_time - start_time:.2f}s")

# Run the demonstration
# asyncio.run(demonstrate_basic_syntax())
```

### async/await vs Regular Functions

Understanding the difference between regular functions and async functions:

```python
import asyncio

# Regular function - executes immediately
def regular_function(x):
    print(f"Regular function called with {x}")
    return x * 2

# Async function - returns a coroutine object
async def async_function(x):
    print(f"Async function called with {x}")
    await asyncio.sleep(0.1)  # Simulate async work
    return x * 2

def demonstrate_function_differences():
    """Show differences between regular and async functions"""
    
    print("=== Regular Function ===")
    # Regular function executes immediately
    regular_result = regular_function(5)
    print(f"Regular result: {regular_result}")
    print(f"Result type: {type(regular_result)}")
    
    print("\n=== Async Function ===")
    # Async function returns coroutine object (doesn't execute yet)
    coro = async_function(5)
    print(f"Coroutine object: {coro}")
    print(f"Coroutine type: {type(coro)}")
    
    # Must await or run to execute
    async def run_async():
        async_result = await async_function(5)
        print(f"Async result: {async_result}")
        return async_result
    
    # Execute the async function
    result = asyncio.run(run_async())
    print(f"Final result: {result}")

demonstrate_function_differences()
```

### Error Handling in Coroutines

```python
import asyncio
import random

async def risky_operation(operation_id):
    """Coroutine that might fail"""
    print(f"Operation {operation_id}: Starting")
    await asyncio.sleep(0.5)
    
    if random.random() < 0.3:  # 30% chance of failure
        raise ValueError(f"Operation {operation_id} failed!")
    
    print(f"Operation {operation_id}: Success")
    return f"Result {operation_id}"

async def demonstrate_error_handling():
    """Show different error handling patterns in coroutines"""
    
    # Pattern 1: Simple try/except
    print("=== Simple Error Handling ===")
    try:
        result = await risky_operation(1)
        print(f"Success: {result}")
    except ValueError as e:
        print(f"Caught error: {e}")
    
    # Pattern 2: Multiple operations with individual error handling
    print("\n=== Individual Error Handling ===")
    results = []
    for i in range(2, 5):
        try:
            result = await risky_operation(i)
            results.append(result)
        except ValueError as e:
            print(f"Operation failed: {e}")
            results.append(None)
    
    print(f"Results: {results}")
    
    # Pattern 3: Concurrent operations with error handling
    print("\n=== Concurrent Error Handling ===")
    
    async def safe_operation(op_id):
        """Wrapper that handles errors gracefully"""
        try:
            return await risky_operation(op_id)
        except ValueError as e:
            print(f"Handled error in wrapper: {e}")
            return f"Error: {e}"
    
    # Run multiple operations concurrently
    tasks = [safe_operation(i) for i in range(5, 8)]
    concurrent_results = await asyncio.gather(*tasks)
    print(f"Concurrent results: {concurrent_results}")
    
    # Pattern 4: Using return_exceptions=True
    print("\n=== Gather with Exceptions ===")
    raw_tasks = [risky_operation(i) for i in range(8, 11)]
    raw_results = await asyncio.gather(*raw_tasks, return_exceptions=True)
    
    for i, result in enumerate(raw_results):
        if isinstance(result, Exception):
            print(f"Task {i}: Failed with {result}")
        else:
            print(f"Task {i}: Succeeded with {result}")

# asyncio.run(demonstrate_error_handling())
```

### Coroutine Composition Patterns

```python
import asyncio
import aiohttp

async def fetch_url(session, url):
    """Fetch a single URL"""
    try:
        async with session.get(url) as response:
            return {
                'url': url,
                'status': response.status,
                'content': await response.text()
            }
    except Exception as e:
        return {
            'url': url,
            'status': None,
            'error': str(e)
        }

async def parallel_pattern():
    """Pattern: Parallel execution of independent operations"""
    urls = [
        "https://httpbin.org/delay/1",
        "https://httpbin.org/delay/2", 
        "https://httpbin.org/delay/1"
    ]
    
    async with aiohttp.ClientSession() as session:
        # All requests execute in parallel
        tasks = [fetch_url(session, url) for url in urls]
        results = await asyncio.gather(*tasks)
    
    return results

async def pipeline_pattern():
    """Pattern: Pipeline processing where each step depends on previous"""
    
    async def step_1():
        print("Step 1: Fetching initial data")
        await asyncio.sleep(0.5)
        return "initial_data"
    
    async def step_2(data):
        print(f"Step 2: Processing {data}")
        await asyncio.sleep(0.3)
        return f"processed_{data}"
    
    async def step_3(data):
        print(f"Step 3: Finalizing {data}")
        await asyncio.sleep(0.2)
        return f"final_{data}"
    
    # Sequential pipeline
    result = await step_1()
    result = await step_2(result)
    result = await step_3(result)
    
    return result

async def fan_out_fan_in_pattern():
    """Pattern: Fan-out work to multiple workers, then fan-in results"""
    
    async def worker(worker_id, work_item):
        """Simulate worker processing"""
        print(f"Worker {worker_id}: Processing {work_item}")
        await asyncio.sleep(random.uniform(0.1, 0.5))  # Variable work time
        return f"Worker {worker_id}: Completed {work_item}"
    
    # Fan-out: Distribute work to multiple workers
    work_items = ["task_A", "task_B", "task_C", "task_D"]
    worker_tasks = [
        worker(i, item) 
        for i, item in enumerate(work_items)
    ]
    
    # Fan-in: Collect all results
    results = await asyncio.gather(*worker_tasks)
    
    return results

async def producer_consumer_pattern():
    """Pattern: Producer-consumer with async queue"""
    
    queue = asyncio.Queue(maxsize=5)
    
    async def producer():
        """Produce items and add to queue"""
        for i in range(10):
            item = f"item_{i}"
            print(f"Producer: Creating {item}")
            await queue.put(item)
            await asyncio.sleep(0.1)  # Simulate production time
        
        # Signal completion
        await queue.put(None)
    
    async def consumer(consumer_id):
        """Consume items from queue"""
        while True:
            item = await queue.get()
            if item is None:
                # Requeue shutdown signal for other consumers
                await queue.put(None)
                break
            
            print(f"Consumer {consumer_id}: Processing {item}")
            await asyncio.sleep(0.2)  # Simulate processing time
            queue.task_done()
        
        print(f"Consumer {consumer_id}: Shutting down")
    
    # Start producer and multiple consumers
    producer_task = asyncio.create_task(producer())
    consumer_tasks = [
        asyncio.create_task(consumer(i)) 
        for i in range(3)
    ]
    
    # Wait for producer to finish
    await producer_task
    
    # Wait for all items to be processed
    await queue.join()
    
    # Cancel consumers (they'll finish current items)
    for task in consumer_tasks:
        task.cancel()
    
    await asyncio.gather(*consumer_tasks, return_exceptions=True)

async def demonstrate_composition_patterns():
    """Demonstrate different coroutine composition patterns"""
    
    print("=== Parallel Pattern ===")
    start_time = asyncio.get_event_loop().time()
    # parallel_results = await parallel_pattern()
    # print(f"Parallel completed in {asyncio.get_event_loop().time() - start_time:.2f}s")
    
    print("\n=== Pipeline Pattern ===")
    pipeline_result = await pipeline_pattern()
    print(f"Pipeline result: {pipeline_result}")
    
    print("\n=== Fan-Out Fan-In Pattern ===")
    fanout_results = await fan_out_fan_in_pattern()
    print(f"Fan-out results: {fanout_results}")
    
    print("\n=== Producer-Consumer Pattern ===")
    await producer_consumer_pattern()
    print("Producer-Consumer completed")

# asyncio.run(demonstrate_composition_patterns())
```

## 3.3 Coroutine Objects and States

Understanding coroutine objects and their lifecycle is crucial for debugging and advanced async programming.

### Coroutine Object Lifecycle

```python
import asyncio
import inspect

async def example_coroutine(name):
    """Example coroutine for state demonstration"""
    print(f"{name}: Coroutine started")
    await asyncio.sleep(0.5)
    print(f"{name}: After first sleep")
    await asyncio.sleep(0.5)
    print(f"{name}: Coroutine ending")
    return f"{name}: Completed"

def demonstrate_coroutine_states():
    """Show different states of coroutine objects"""
    
    print("=== Coroutine Object States ===")
    
    # State 1: Created but not started
    coro = example_coroutine("Demo")
    print(f"1. Created coroutine: {coro}")
    print(f"   Type: {type(coro)}")
    print(f"   State: {inspect.getcoroutinestate(coro)}")
    print(f"   Is coroutine: {asyncio.iscoroutine(coro)}")
    print(f"   Is coroutine function: {asyncio.iscoroutinefunction(example_coroutine)}")
    
    async def run_coroutine_states():
        # State 2: Running (inside event loop)
        print(f"\n2. Starting coroutine...")
        
        # Create task to see different object types
        task = asyncio.create_task(example_coroutine("Task"))
        print(f"   Task object: {task}")
        print(f"   Task type: {type(task)}")
        print(f"   Task done: {task.done()}")
        
        # Wait for completion
        result = await task
        
        # State 3: Completed
        print(f"\n3. After completion:")
        print(f"   Task done: {task.done()}")
        print(f"   Task result: {task.result()}")
        
        return result
    
    # Run the demonstration
    result = asyncio.run(run_coroutine_states())
    print(f"\nFinal result: {result}")
    
    # State 4: Coroutine object after completion/cleanup
    print(f"\n4. Original coroutine state: {inspect.getcoroutinestate(coro)}")
    
    # Clean up unused coroutine
    coro.close()

demonstrate_coroutine_states()
```

### Coroutine Introspection

```python
import asyncio
import inspect
import sys

async def introspectable_coroutine(param1, param2="default"):
    """Coroutine for introspection demonstration"""
    local_var = "I'm local"
    await asyncio.sleep(0.1)
    
    # Access coroutine frame information
    frame = sys._getframe()
    print(f"Current frame: {frame}")
    print(f"Local variables: {frame.f_locals}")
    
    return f"Processed {param1} with {param2}"

def demonstrate_coroutine_introspection():
    """Show how to introspect coroutine objects"""
    
    # Create coroutine for introspection
    coro = introspectable_coroutine("test_param", param2="custom")
    
    print("=== Coroutine Introspection ===")
    
    # Basic introspection
    print(f"Coroutine: {coro}")
    print(f"Coroutine name: {coro.__name__}")
    print(f"Coroutine qualname: {coro.__qualname__}")
    
    # Get coroutine frame (when available)
    if hasattr(coro, 'cr_frame') and coro.cr_frame:
        frame = coro.cr_frame
        print(f"Frame: {frame}")
        print(f"Code object: {frame.f_code}")
        print(f"Filename: {frame.f_code.co_filename}")
        print(f"Line number: {frame.f_lineno}")
    
    # Function signature introspection
    sig = inspect.signature(introspectable_coroutine)
    print(f"Signature: {sig}")
    print(f"Parameters: {list(sig.parameters.keys())}")
    
    # Check if coroutine
    print(f"Is coroutine: {inspect.iscoroutine(coro)}")
    print(f"Is generator: {inspect.isgenerator(coro)}")
    print(f"Is async generator: {inspect.isasyncgen(coro)}")
    
    # State information
    print(f"Coroutine state: {inspect.getcoroutinestate(coro)}")
    
    # Run the coroutine
    async def run_and_introspect():
        print("\n=== During Execution ===")
        result = await coro
        print(f"Result: {result}")
        return result
    
    asyncio.run(run_and_introspect())

demonstrate_coroutine_introspection()
```

### Coroutine Memory and Resource Management

```python
import asyncio
import weakref
import gc

class CoroutineResourceTracker:
    """Track coroutine resource usage"""
    
    def __init__(self):
        self.active_coroutines = weakref.WeakSet()
        self.completed_count = 0
    
    def track_coroutine(self, coro):
        """Add coroutine to tracking"""
        self.active_coroutines.add(coro)
        
        # Add completion callback if it's a task
        if isinstance(coro, asyncio.Task):
            coro.add_done_callback(self._on_completion)
    
    def _on_completion(self, task):
        """Called when task completes"""
        self.completed_count += 1
    
    def get_stats(self):
        """Get current statistics"""
        return {
            'active': len(self.active_coroutines),
            'completed': self.completed_count
        }

async def resource_demo_coroutine(tracker, coro_id, duration):
    """Coroutine for resource demonstration"""
    print(f"Coroutine {coro_id}: Starting")
    
    # Simulate resource allocation
    resource = f"Resource-{coro_id}"
    
    try:
        await asyncio.sleep(duration)
        print(f"Coroutine {coro_id}: Completed normally")
        return f"Result-{coro_id}"
    
    except asyncio.CancelledError:
        print(f"Coroutine {coro_id}: Cancelled, cleaning up")
        # Cleanup resources
        del resource
        raise
    
    finally:
        print(f"Coroutine {coro_id}: Finally block executed")

async def demonstrate_resource_management():
    """Demonstrate coroutine resource management"""
    
    tracker = CoroutineResourceTracker()
    
    print("=== Resource Management Demo ===")
    
    # Create multiple coroutines
    tasks = []
    for i in range(5):
        task = asyncio.create_task(
            resource_demo_coroutine(tracker, i, i * 0.2 + 0.1)
        )
        tracker.track_coroutine(task)
        tasks.append(task)
    
    print(f"Initial stats: {tracker.get_stats()}")
    
    # Let some complete normally
    await asyncio.sleep(0.5)
    print(f"After 0.5s: {tracker.get_stats()}")
    
    # Cancel remaining tasks
    for task in tasks:
        if not task.done():
            task.cancel()
    
    # Wait for cancellations to complete
    await asyncio.gather(*tasks, return_exceptions=True)
    
    print(f"Final stats: {tracker.get_stats()}")
    
    # Force garbage collection to clean up
    gc.collect()
    print(f"After GC: {tracker.get_stats()}")

# asyncio.run(demonstrate_resource_management())
```

## 3.4 Awaiting Coroutines

The `await` keyword is how you actually execute coroutines and retrieve their results. Understanding `await` is fundamental to async programming.

### Basic await Usage

```python
import asyncio
import time

async def basic_await_examples():
    """Demonstrate basic await usage"""
    
    # Example 1: Awaiting a simple coroutine
    async def simple_task(name, duration):
        print(f"{name}: Starting {duration}s task")
        start_time = time.time()
        await asyncio.sleep(duration)
        end_time = time.time()
        print(f"{name}: Completed in {end_time - start_time:.2f}s")
        return f"{name} result"
    
    print("=== Basic Await Examples ===")
    
    # Sequential execution
    print("1. Sequential execution:")
    start_time = time.time()
    
    result1 = await simple_task("Task-1", 0.5)
    result2 = await simple_task("Task-2", 0.3)
    result3 = await simple_task("Task-3", 0.2)
    
    total_time = time.time() - start_time
    print(f"Sequential results: {[result1, result2, result3]}")
    print(f"Total sequential time: {total_time:.2f}s")
    
    # Concurrent execution using tasks
    print("\n2. Concurrent execution:")
    start_time = time.time()
    
    # Create tasks (starts execution immediately)
    task1 = asyncio.create_task(simple_task("Concurrent-1", 0.5))
    task2 = asyncio.create_task(simple_task("Concurrent-2", 0.3))
    task3 = asyncio.create_task(simple_task("Concurrent-3", 0.2))
    
    # Await all tasks (they're already running)
    concurrent_result1 = await task1
    concurrent_result2 = await task2
    concurrent_result3 = await task3
    
    total_concurrent_time = time.time() - start_time
    print(f"Concurrent results: {[concurrent_result1, concurrent_result2, concurrent_result3]}")
    print(f"Total concurrent time: {total_concurrent_time:.2f}s")

# asyncio.run(basic_await_examples())
```

### What Can You await?

```python
import asyncio

def demonstrate_awaitable_objects():
    """Show different types of objects that can be awaited"""
    
    async def awaitable_examples():
        print("=== Awaitable Objects ===")
        
        # 1. Coroutines
        async def example_coroutine():
            await asyncio.sleep(0.1)
            return "Coroutine result"
        
        coro_result = await example_coroutine()
        print(f"1. Coroutine result: {coro_result}")
        
        # 2. Tasks
        task = asyncio.create_task(example_coroutine())
        task_result = await task
        print(f"2. Task result: {task_result}")
        
        # 3. Futures
        future = asyncio.Future()
        
        # Schedule future completion
        def complete_future():
            if not future.done():
                future.set_result("Future result")
        
        asyncio.get_event_loop().call_later(0.1, complete_future)
        future_result = await future
        print(f"3. Future result: {future_result}")
        
        # 4. Objects with __await__ method
        class CustomAwaitable:
            def __await__(self):
                # Must return an iterator
                yield from asyncio.sleep(0.1).__await__()
                return "Custom awaitable result"
        
        custom_result = await CustomAwaitable()
        print(f"4. Custom awaitable result: {custom_result}")
        
        # 5. Generator-based coroutines (legacy)
        @asyncio.coroutine
        def legacy_coro():
            yield from asyncio.sleep(0.1)
            return "Legacy coroutine result"
        
        legacy_result = await legacy_coro()
        print(f"5. Legacy coroutine result: {legacy_result}")
        
        return "All awaitable examples completed"
    
    return asyncio.run(awaitable_examples())

demonstrate_awaitable_objects()
```

### await with Exception Handling

```python
import asyncio
import random

async def unreliable_operation(operation_id, failure_rate=0.3):
    """Operation that might fail"""
    await asyncio.sleep(0.2)
    
    if random.random() < failure_rate:
        raise ValueError(f"Operation {operation_id} failed")
    
    return f"Operation {operation_id} succeeded"

async def demonstrate_await_error_handling():
    """Show error handling patterns with await"""
    
    print("=== Await Error Handling ===")
    
    # Pattern 1: Simple try/except around await
    print("1. Simple error handling:")
    try:
        result = await unreliable_operation(1)
        print(f"   Success: {result}")
    except ValueError as e:
        print(f"   Error: {e}")
    
    # Pattern 2: Multiple awaits with different error handling
    print("\n2. Multiple operations:")
    operations = []
    
    for i in range(3):
        try:
            result = await unreliable_operation(i + 2)
            operations.append(('success', result))
        except ValueError as e:
            operations.append(('error', str(e)))
    
    for status, result in operations:
        print(f"   {status.capitalize()}: {result}")
    
    # Pattern 3: Error handling with timeouts
    print("\n3. With timeout:")
    try:
        result = await asyncio.wait_for(
            unreliable_operation(5, failure_rate=0.1),
            timeout=0.5
        )
        print(f"   Timeout success: {result}")
    except asyncio.TimeoutError:
        print("   Operation timed out")
    except ValueError as e:
        print(f"   Operation error: {e}")
    
    # Pattern 4: Shielding critical operations
    print("\n4. Shielded operation:")
    try:
        # Shield protects operation from cancellation
        result = await asyncio.shield(
            unreliable_operation(6, failure_rate=0.1)
        )
        print(f"   Shielded success: {result}")
    except ValueError as e:
        print(f"   Shielded error: {e}")

# asyncio.run(demonstrate_await_error_handling())
```

### await vs yield from

Understanding the difference between `await` and `yield from`:

```python
import asyncio

def compare_await_and_yield_from():
    """Compare await and yield from"""
    
    # Modern async/await style
    async def modern_coroutine():
        print("Modern coroutine: Starting")
        
        # await automatically handles the __await__ protocol
        result = await asyncio.sleep(0.1, result="Modern result")
        
        print(f"Modern coroutine: Got {result}")
        return result
    
    # Legacy generator-based style  
    @asyncio.coroutine
    def legacy_coroutine():
        print("Legacy coroutine: Starting")
        
        # yield from manually delegates to sub-generator
        result = yield from asyncio.sleep(0.1, result="Legacy result")
        
        print(f"Legacy coroutine: Got {result}")
        return result
    
    async def demonstrate_differences():
        print("=== await vs yield from ===")
        
        print("1. Modern async/await:")
        modern_result = await modern_coroutine()
        print(f"   Result: {modern_result}")
        
        print("\n2. Legacy yield from:")
        legacy_result = await legacy_coroutine()
        print(f"   Result: {legacy_result}")
        
        # Key differences:
        print("\n3. Key differences:")
        print("   - await works only in async functions")
        print("   - yield from works in generators")
        print("   - await has better error messages")
        print("   - await is the modern, preferred syntax")
        
        return modern_result, legacy_result
    
    return asyncio.run(demonstrate_differences())

compare_await_and_yield_from()
```

## 3.5 Coroutine Chaining

Coroutine chaining involves composing multiple coroutines together to create more complex async workflows.

### Sequential Chaining

```python
import asyncio
import json

async def fetch_data(source_id):
    """Simulate fetching data from a source"""
    print(f"Fetching data from source {source_id}")
    await asyncio.sleep(0.3)  # Simulate network delay
    
    # Simulate different data from different sources
    data = {
        1: {"users": ["alice", "bob"], "count": 2},
        2: {"users": ["charlie", "dave", "eve"], "count": 3},
        3: {"users": ["frank"], "count": 1}
    }
    
    return data.get(source_id, {"users": [], "count": 0})

async def process_data(data):
    """Process fetched data"""
    print(f"Processing data: {data}")
    await asyncio.sleep(0.2)  # Simulate processing time
    
    # Process the data
    processed = {
        "total_users": data["count"],
        "user_list": [user.upper() for user in data["users"]],
        "processed_at": "2024-01-01T12:00:00Z"
    }
    
    return processed

async def save_result(processed_data):
    """Save processed result"""
    print(f"Saving result: {processed_data}")
    await asyncio.sleep(0.1)  # Simulate save time
    
    # Simulate saving to database/file
    saved_data = {
        **processed_data,
        "saved": True,
        "save_id": "12345"
    }
    
    return saved_data

async def sequential_chaining_example():
    """Demonstrate sequential coroutine chaining"""
    
    print("=== Sequential Chaining ===")
    
    # Chain 1: Simple sequential chain
    print("1. Simple sequential chain:")
    data = await fetch_data(1)
    processed = await process_data(data)
    result = await save_result(processed)
    
    print(f"   Final result: {result}")
    
    # Chain 2: Multiple data sources sequentially
    print("\n2. Multiple sources sequentially:")
    all_results = []
    
    for source_id in [1, 2, 3]:
        data = await fetch_data(source_id)
        processed = await process_data(data)
        result = await save_result(processed)
        all_results.append(result)
    
    print(f"   All results count: {len(all_results)}")
    
    return all_results

# asyncio.run(sequential_chaining_example())
```

### Parallel Chaining with Dependencies

```python
import asyncio

async def download_file(file_id, size_mb):
    """Simulate downloading a file"""
    print(f"Downloading file {file_id} ({size_mb}MB)")
    download_time = size_mb * 0.1  # 0.1s per MB
    await asyncio.sleep(download_time)
    
    return {
        "file_id": file_id,
        "size_mb": size_mb,
        "content": f"Content of file {file_id}"
    }

async def extract_metadata(file_data):
    """Extract metadata from downloaded file"""
    print(f"Extracting metadata from file {file_data['file_id']}")
    await asyncio.sleep(0.2)  # Simulate extraction time
    
    return {
        "file_id": file_data["file_id"],
        "metadata": {
            "size": file_data["size_mb"],
            "type": "document",
            "extracted_fields": ["title", "author", "date"]
        }
    }

async def virus_scan(file_data):
    """Perform virus scan on downloaded file"""
    print(f"Virus scanning file {file_data['file_id']}")
    await asyncio.sleep(0.5)  # Simulate scan time
    
    return {
        "file_id": file_data["file_id"],
        "scan_result": "clean",
        "scan_time": 0.5
    }

async def combine_results(file_data, metadata, scan_result):
    """Combine all results"""
    print(f"Combining results for file {file_data['file_id']}")
    await asyncio.sleep(0.1)
    
    return {
        "file_id": file_data["file_id"],
        "content": file_data["content"],
        "metadata": metadata["metadata"],
        "scan_result": scan_result["scan_result"],
        "processing_complete": True
    }

async def parallel_chaining_example():
    """Demonstrate parallel coroutine chaining with dependencies"""
    
    print("=== Parallel Chaining with Dependencies ===")
    
    # Process single file with parallel operations
    print("1. Single file with parallel operations:")
    
    # Download file first (required for both metadata and scan)
    file_data = await download_file("doc1.pdf", 5)
    
    # Extract metadata and virus scan can run in parallel
    metadata_task = asyncio.create_task(extract_metadata(file_data))
    scan_task = asyncio.create_task(virus_scan(file_data))
    
    # Wait for both to complete
    metadata, scan_result = await asyncio.gather(metadata_task, scan_task)
    
    # Combine results (depends on all previous operations)
    final_result = await combine_results(file_data, metadata, scan_result)
    
    print(f"   Final result: {final_result['file_id']} - {final_result['processing_complete']}")
    
    # Process multiple files with complex dependencies
    print("\n2. Multiple files with complex dependencies:")
    
    async def process_single_file(file_id, size_mb):
        """Process a single file through the entire pipeline"""
        # Step 1: Download
        file_data = await download_file(file_id, size_mb)
        
        # Step 2: Parallel processing
        metadata_task = asyncio.create_task(extract_metadata(file_data))
        scan_task = asyncio.create_task(virus_scan(file_data))
        
        metadata, scan_result = await asyncio.gather(metadata_task, scan_task)
        
        # Step 3: Combine
        result = await combine_results(file_data, metadata, scan_result)
        
        return result
    
    # Process multiple files in parallel
    file_tasks = [
        process_single_file("doc1.pdf", 3),
        process_single_file("doc2.pdf", 7),
        process_single_file("doc3.pdf", 2)
    ]
    
    all_results = await asyncio.gather(*file_tasks)
    
    print(f"   Processed {len(all_results)} files successfully")
    
    return all_results

# asyncio.run(parallel_chaining_example())
```

### Error Propagation in Chains

```python
import asyncio
import random

async def unreliable_step(step_name, failure_rate=0.2):
    """A step that might fail"""
    print(f"Executing {step_name}")
    await asyncio.sleep(0.1)
    
    if random.random() < failure_rate:
        raise RuntimeError(f"{step_name} failed!")
    
    print(f"{step_name} completed successfully")
    return f"{step_name}_result"

async def error_propagation_examples():
    """Demonstrate error propagation in coroutine chains"""
    
    print("=== Error Propagation in Chains ===")
    
    # Pattern 1: Let errors propagate up
    print("1. Error propagation:")
    try:
        step1_result = await unreliable_step("step_1", failure_rate=0.1)
        step2_result = await unreliable_step("step_2", failure_rate=0.8)  # High failure rate
        step3_result = await unreliable_step("step_3", failure_rate=0.1)
        
        print(f"   All steps succeeded: {[step1_result, step2_result, step3_result]}")
        
    except RuntimeError as e:
        print(f"   Chain failed: {e}")
    
    # Pattern 2: Handle errors at each step
    print("\n2. Per-step error handling:")
    results = []
    
    for step_name in ["step_A", "step_B", "step_C"]:
        try:
            result = await unreliable_step(step_name, failure_rate=0.3)
            results.append(("success", result))
        except RuntimeError as e:
            print(f"   {step_name} failed, continuing with default")
            results.append(("default", f"{step_name}_default"))
    
    print(f"   Results with error handling: {results}")
    
    # Pattern 3: Retry logic in chains
    print("\n3. Chain with retry logic:")
    
    async def retry_step(step_name, max_retries=3):
        """Step with retry logic"""
        for attempt in range(max_retries):
            try:
                return await unreliable_step(step_name, failure_rate=0.5)
            except RuntimeError as e:
                print(f"   {step_name} attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(0.1)  # Wait before retry
    
    try:
        retry_result = await retry_step("retry_step")
        print(f"   Retry step succeeded: {retry_result}")
    except RuntimeError as e:
        print(f"   Retry step exhausted: {e}")
    
    # Pattern 4: Partial failure handling
    print("\n4. Partial failure in parallel chains:")
    
    async def parallel_with_errors():
        """Parallel operations where some might fail"""
        tasks = [
            unreliable_step(f"parallel_{i}", failure_rate=0.4) 
            for i in range(5)
        ]
        
        # Use return_exceptions=True to handle partial failures
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        successes = []
        failures = []
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                failures.append((i, str(result)))
            else:
                successes.append((i, result))
        
        print(f"   Successes: {len(successes)}, Failures: {len(failures)}")
        return successes, failures
    
    successes, failures = await parallel_with_errors()
    
    return {
        "propagation_demo": "completed",
        "successes": len(successes),
        "failures": len(failures)
    }

# asyncio.run(error_propagation_examples())
```

## 3.6 Common Pitfalls with Coroutines

Understanding common mistakes helps you write more reliable async code.

### Pitfall 1: Forgetting to await

```python
import asyncio

def forgetting_await_pitfall():
    """Demonstrate the 'forgetting to await' pitfall"""
    
    async def async_operation():
        await asyncio.sleep(0.1)
        return "Operation result"
    
    async def correct_usage():
        """Correct way to call async functions"""
        print("=== Correct Usage ===")
        
        # Correct: await the coroutine
        result = await async_operation()
        print(f"Correct result: {result}")
        
        return result
    
    async def incorrect_usage():
        """Common mistake: forgetting to await"""
        print("\n=== Incorrect Usage (Common Mistake) ===")
        
        # WRONG: Forgot to await - this returns a coroutine object
        result = async_operation()  # This is a coroutine, not the result!
        print(f"Incorrect 'result': {result}")
        print(f"Type: {type(result)}")
        
        # This will cause a warning about unawaited coroutine
        # The coroutine never actually executes!
        
        # To get the actual result, we need to await:
        actual_result = await result
        print(f"Actual result after awaiting: {actual_result}")
        
        return actual_result
    
    async def demonstrate_pitfall():
        await correct_usage()
        await incorrect_usage()
        print("\nAlways remember to await coroutines!")
    
    # This will generate warnings about unawaited coroutines
    asyncio.run(demonstrate_pitfall())

# Uncomment to see the warnings:
# forgetting_await_pitfall()
```

### Pitfall 2: Blocking Operations in Async Code

```python
import asyncio
import time
import requests  # Blocking HTTP library

async def blocking_operations_pitfall():
    """Demonstrate blocking operations in async code"""
    
    print("=== Blocking Operations Pitfall ===")
    
    # WRONG: Using blocking operations in async code
    async def bad_example():
        """Don't do this - blocks the entire event loop"""
        print("Bad example: Starting blocking operations")
        start_time = time.time()
        
        # These are BLOCKING operations that freeze the event loop
        time.sleep(1)  # BAD: Blocks event loop
        response = requests.get("https://httpbin.org/delay/1")  # BAD: Blocking HTTP
        
        end_time = time.time()
        print(f"Bad example completed in {end_time - start_time:.2f}s")
        return response.json()
    
    # CORRECT: Using non-blocking alternatives
    async def good_example():
        """Correct way - use async alternatives"""
        print("Good example: Starting non-blocking operations")
        start_time = time.time()
        
        # Use async alternatives
        await asyncio.sleep(1)  # GOOD: Non-blocking sleep
        
        # Use async HTTP library
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get("https://httpbin.org/delay/1") as response:
                data = await response.json()
        
        end_time = time.time()
        print(f"Good example completed in {end_time - start_time:.2f}s")
        return data
    
    # Demonstrate the difference with concurrent operations
    async def concurrent_test():
        """Show how blocking operations affect concurrency"""
        print("\n=== Concurrency Test ===")
        
        # Test with non-blocking operations
        print("1. Non-blocking concurrent operations:")
        start_time = time.time()
        
        tasks = [good_example() for _ in range(3)]
        results = await asyncio.gather(*tasks)
        
        end_time = time.time()
        print(f"   3 concurrent non-blocking operations: {end_time - start_time:.2f}s")
        
        # Note: We don't test bad_example() concurrently because
        # it would block the entire event loop and make all operations sequential
        print("\n2. Blocking operations would run sequentially (~3 seconds)")
        print("   (Not demonstrated to avoid blocking the demo)")
    
    await concurrent_test()
    
    # Show how to handle unavoidable blocking operations
    print("\n=== Handling Unavoidable Blocking Operations ===")
    
    async def handle_blocking_correctly():
        """When you must use blocking operations, run them in executor"""
        
        def blocking_cpu_task():
            """Simulate CPU-intensive blocking work"""
            total = 0
            for i in range(5000000):  # CPU-intensive loop
                total += i * i
            return total
        
        # Run blocking operation in thread pool
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, blocking_cpu_task)
        
        print(f"   Blocking operation result: {result}")
        return result
    
    await handle_blocking_correctly()

# asyncio.run(blocking_operations_pitfall())
```

### Pitfall 3: Race Conditions and Shared State

```python
import asyncio

async def race_condition_pitfall():
    """Demonstrate race conditions in async code"""
    
    print("=== Race Condition Pitfall ===")
    
    # WRONG: Shared state without proper synchronization
    class BadCounter:
        """Counter with race condition"""
        def __init__(self):
            self.count = 0
        
        async def increment(self):
            """Increment with race condition"""
            # Race condition: read-modify-write is not atomic
            current = self.count
            await asyncio.sleep(0.01)  # Simulate async work
            self.count = current + 1
    
    # CORRECT: Proper synchronization
    class GoodCounter:
        """Counter with proper synchronization"""
        def __init__(self):
            self.count = 0
            self._lock = asyncio.Lock()
        
        async def increment(self):
            """Thread-safe increment"""
            async with self._lock:
                current = self.count
                await asyncio.sleep(0.01)  # Simulate async work
                self.count = current + 1
    
    # Demonstrate the race condition
    async def test_race_condition():
        print("1. Testing race condition:")
        
        bad_counter = BadCounter()
        
        # Create many concurrent increment operations
        tasks = [bad_counter.increment() for _ in range(100)]
        await asyncio.gather(*tasks)
        
        print(f"   Bad counter final value: {bad_counter.count}")
        print(f"   Expected: 100, Actual: {bad_counter.count}")
        print(f"   Race condition detected: {bad_counter.count != 100}")
    
    async def test_proper_synchronization():
        print("\n2. Testing proper synchronization:")
        
        good_counter = GoodCounter()
        
        # Same concurrent operations, but synchronized
        tasks = [good_counter.increment() for _ in range(100)]
        await asyncio.gather(*tasks)
        
        print(f"   Good counter final value: {good_counter.count}")
        print(f"   Expected: 100, Actual: {good_counter.count}")
        print(f"   Correctly synchronized: {good_counter.count == 100}")
    
    await test_race_condition()
    await test_proper_synchronization()

# asyncio.run(race_condition_pitfall())
```

### Pitfall 4: Memory Leaks with Unawaited Tasks

```python
import asyncio
import weakref

async def memory_leak_pitfall():
    """Demonstrate memory leaks from unawaited tasks"""
    
    print("=== Memory Leak Pitfall ===")
    
    # WRONG: Creating tasks but not waiting for them
    class TaskLeaker:
        """Class that creates tasks but doesn't manage them"""
        def __init__(self):
            self.created_tasks = []
        
        async def create_background_task(self, task_id):
            """Background task that runs for a while"""
            try:
                await asyncio.sleep(10)  # Long-running task
                return f"Task {task_id} completed"
            except asyncio.CancelledError:
                print(f"Task {task_id} was cancelled")
                raise
        
        def start_task_bad(self, task_id):
            """BAD: Creates task but doesn't track or await it"""
            task = asyncio.create_task(
                self.create_background_task(task_id)
            )
            # Task is created but never awaited - potential memory leak!
            return task
    
    # CORRECT: Proper task management
    class TaskManager:
        """Class that properly manages tasks"""
        def __init__(self):
            self.active_tasks = set()
        
        def start_task_good(self, task_id):
            """GOOD: Creates and tracks task properly"""
            task = asyncio.create_task(
                self.create_background_task(task_id)
            )
            
            # Track the task
            self.active_tasks.add(task)
            
            # Remove from tracking when done
            task.add_done_callback(self.active_tasks.discard)
            
            return task
        
        async def create_background_task(self, task_id):
            """Background task that runs for a while"""
            try:
                await asyncio.sleep(10)  # Long-running task
                return f"Task {task_id} completed"
            except asyncio.CancelledError:
                print(f"Task {task_id} was cancelled")
                raise
        
        async def shutdown(self):
            """Properly shutdown all tasks"""
            print(f"Cancelling {len(self.active_tasks)} active tasks")
            
            # Cancel all active tasks
            for task in self.active_tasks.copy():
                task.cancel()
            
            # Wait for cancellation to complete
            if self.active_tasks:
                await asyncio.gather(*self.active_tasks, return_exceptions=True)
    
    # Demonstrate the leak
    async def demonstrate_leak():
        print("1. Creating tasks without proper management:")
        
        leaker = TaskLeaker()
        
        # Create several tasks but don't await them
        for i in range(5):
            task = leaker.start_task_bad(i)
            # Tasks are running but not awaited - they'll be garbage collected
            # but might still consume memory
        
        print("   Created 5 unmanaged tasks")
        
        # Let them run briefly then clean up
        await asyncio.sleep(0.1)
        
        # Force cleanup of abandoned tasks
        tasks = [t for t in asyncio.all_tasks() if not t.done()]
        for task in tasks:
            if task != asyncio.current_task():
                task.cancel()
        
        await asyncio.gather(*tasks, return_exceptions=True)
        print("   Cleaned up abandoned tasks")
    
    async def demonstrate_proper_management():
        print("\n2. Proper task management:")
        
        manager = TaskManager()
        
        # Create managed tasks
        for i in range(5):
            task = manager.start_task_good(i)
        
        print(f"   Created {len(manager.active_tasks)} managed tasks")
        
        # Let them run briefly
        await asyncio.sleep(0.1)
        
        # Proper shutdown
        await manager.shutdown()
        print("   All tasks properly managed and shutdown")
    
    await demonstrate_leak()
    await demonstrate_proper_management()

# asyncio.run(memory_leak_pitfall())
```

### Pitfall 5: Mixing Sync and Async Code Incorrectly

```python
import asyncio

def sync_async_mixing_pitfall():
    """Demonstrate incorrect mixing of sync and async code"""
    
    print("=== Sync/Async Mixing Pitfall ===")
    
    async def async_function():
        await asyncio.sleep(0.1)
        return "Async result"
    
    def sync_function():
        time.sleep(0.1)
        return "Sync result"
    
    # WRONG: Trying to call async from sync without proper handling
    def bad_sync_calling_async():
        """DON'T DO THIS"""
        print("1. Bad: Trying to call async from sync incorrectly")
        
        try:
            # This WON'T WORK - can't await in non-async function
            # result = await async_function()  # SyntaxError
            
            # This also WON'T WORK as intended
            coro = async_function()
            print(f"   Got coroutine object: {coro}")
            print("   But this doesn't execute the async function!")
            
            # Clean up the coroutine
            coro.close()
            
        except Exception as e:
            print(f"   Error: {e}")
    
    # CORRECT: Proper ways to call async from sync
    def good_sync_calling_async():
        """Correct ways to call async from sync"""
        print("\n2. Good: Proper ways to call async from sync")
        
        # Method 1: Use asyncio.run()
        print("   Method 1: asyncio.run()")
        result1 = asyncio.run(async_function())
        print(f"   Result: {result1}")
        
        # Method 2: Create and run event loop manually
        print("   Method 2: Manual event loop")
        loop = asyncio.new_event_loop()
        try:
            result2 = loop.run_until_complete(async_function())
            print(f"   Result: {result2}")
        finally:
            loop.close()
    
    # WRONG: Trying to call sync blocking code in async
    async def bad_async_calling_sync():
        """Don't do this - it blocks the event loop"""
        print("\n3. Bad: Blocking sync code in async function")
        
        # This blocks the entire event loop
        import time
        time.sleep(1)  # BAD: Blocks event loop
        
        return "Bad result"
    
    # CORRECT: Proper way to run sync code in async
    async def good_async_calling_sync():
        """Correct way to run sync code from async"""
        print("\n4. Good: Running sync code from async properly")
        
        # Method 1: For I/O-bound operations, use run_in_executor
        loop = asyncio.get_running_loop()
        
        # Run blocking I/O in thread pool
        result = await loop.run_in_executor(None, sync_function)
        print(f"   Executor result: {result}")
        
        # Method 2: For CPU-bound work, use ProcessPoolExecutor
        import concurrent.futures
        
        def cpu_bound_work():
            return sum(i * i for i in range(1000000))
        
        with concurrent.futures.ProcessPoolExecutor() as executor:
            cpu_result = await loop.run_in_executor(executor, cpu_bound_work)
            print(f"   CPU-bound result: {cpu_result}")
        
        return result
    
    # Demonstrate the patterns
    bad_sync_calling_async()
    good_sync_calling_async()
    
    # For async patterns, we need to run them in event loop
    async def run_async_examples():
        # Note: We skip bad_async_calling_sync() to avoid blocking the demo
        await good_async_calling_sync()
    
    asyncio.run(run_async_examples())

sync_async_mixing_pitfall()
```

### Best Practices Summary

```python
async def coroutine_best_practices():
    """Summary of coroutine best practices"""
    
    print("=== Coroutine Best Practices ===")
    
    # 1. Always await coroutines
    print("1. ✅ Always await coroutines")
    async def good_awaiting():
        result = await some_async_operation()  # ✅ Good
        return result
    
    # 2. Use async libraries for I/O
    print("2. ✅ Use async libraries for I/O operations")
    async def good_io():
        # ✅ Use aiohttp instead of requests
        # ✅ Use aiofiles instead of built-in open()
        # ✅ Use asyncpg/aiomysql instead of blocking DB drivers
        pass
    
    # 3. Handle errors properly
    print("3. ✅ Handle errors at appropriate levels")
    async def good_error_handling():
        try:
            result = await risky_operation()
            return result
        except SpecificError as e:
            # Handle specific errors appropriately
            return default_value
    
    # 4. Use proper synchronization
    print("4. ✅ Use locks for shared state")
    async def good_synchronization():
        async with self._lock:
            # Modify shared state safely
            self.shared_resource += 1
    
    # 5. Manage task lifecycle
    print("5. ✅ Properly manage task lifecycle")
    class GoodTaskManager:
        def __init__(self):
            self.tasks = set()
        
        def create_task(self, coro):
            task = asyncio.create_task(coro)
            self.tasks.add(task)
            task.add_done_callback(self.tasks.discard)
            return task
        
        async def shutdown(self):
            for task in self.tasks.copy():
                task.cancel()
            await asyncio.gather(*self.tasks, return_exceptions=True)
    
    # 6. Use type hints
    print("6. ✅ Use type hints for clarity")
    async def well_typed_function(data: dict) -> str:
        result = await process_data(data)
        return result
    
    print("\nFollowing these practices will help you write robust async code!")

# Helper functions referenced in examples
async def some_async_operation():
    await asyncio.sleep(0.1)
    return "operation result"

async def risky_operation():
    await asyncio.sleep(0.1)
    if random.random() < 0.5:
        raise ValueError("Risky operation failed")
    return "risky result"

async def process_data(data):
    await asyncio.sleep(0.1)
    return f"processed {data}"

# asyncio.run(coroutine_best_practices())
```

This completes Chapter 3! You now have a comprehensive understanding of coroutines, from their historical origins to modern best practices. The next chapter will dive into Tasks and Futures - the mechanisms that schedule and manage coroutine execution.
# Chapter 2: The Event Loop - Heart of Asyncio

## 2.1 What is an Event Loop?

The event loop is the central execution mechanism of asyncio. It's a programming construct that waits for and dispatches events or messages in a program. Think of it as a traffic controller at a busy intersection - it manages the flow of execution, deciding which tasks get to run and when.

### Core Responsibilities

The event loop handles four main responsibilities:

1. **I/O Monitoring**: Watching for I/O operations to complete (network requests, file reads, etc.)
2. **Task Scheduling**: Deciding which coroutines to run and when
3. **Callback Execution**: Running callbacks when events occur
4. **Timer Management**: Handling delayed function calls and timeouts

```python
import asyncio

# The event loop in action
async def demonstrate_event_loop():
    print("1. Function starts")
    
    # This yields control back to the event loop
    await asyncio.sleep(1)
    print("2. After 1 second delay")
    
    # Another yield point
    await asyncio.sleep(0.5)
    print("3. After another 0.5 second delay")

# Run the coroutine
asyncio.run(demonstrate_event_loop())

# Output:
# 1. Function starts
# 2. After 1 second delay (after 1 second)
# 3. After another 0.5 second delay (after 1.5 seconds total)
```

### Event Loop vs Traditional Control Flow

```python
import time

# Traditional sequential execution
def traditional_approach():
    print("Starting task 1")
    time.sleep(1)  # Blocks the entire program
    print("Task 1 completed")
    
    print("Starting task 2")
    time.sleep(1)  # Blocks again
    print("Task 2 completed")
    
    total_time = 2  # Sequential execution

# Event loop approach
async def event_loop_approach():
    async def task_1():
        print("Starting task 1")
        await asyncio.sleep(1)  # Yields control, doesn't block
        print("Task 1 completed")
    
    async def task_2():
        print("Starting task 2")
        await asyncio.sleep(1)  # Yields control, doesn't block
        print("Task 2 completed")
    
    # Both tasks run concurrently
    await asyncio.gather(task_1(), task_2())
    total_time = 1  # Concurrent execution

# The event loop allows task_2 to start while task_1 is sleeping
```

## 2.2 How Event Loops Work Internally

Understanding the internal mechanics of the event loop helps you write more efficient async code.

### The Event Loop Cycle

The event loop follows a specific cycle:

```python
# Simplified event loop pseudocode
def simplified_event_loop():
    ready_queue = []      # Tasks ready to run
    waiting_queue = []    # Tasks waiting for I/O or timers
    io_selector = select.epoll()  # OS-level I/O monitoring
    
    while True:
        # Phase 1: Execute all ready tasks
        while ready_queue:
            task = ready_queue.pop(0)
            try:
                task.run()
            except StopIteration:
                # Task completed
                pass
            except Exception as e:
                # Handle task exception
                task.set_exception(e)
        
        # Phase 2: Check for completed I/O operations
        completed_io = io_selector.poll(timeout=0)
        for fd, events in completed_io:
            task = find_task_waiting_for(fd)
            ready_queue.append(task)
        
        # Phase 3: Check for expired timers
        current_time = time.time()
        for task in waiting_queue[:]:  # Copy to avoid modification during iteration
            if task.scheduled_time <= current_time:
                waiting_queue.remove(task)
                ready_queue.append(task)
        
        # Phase 4: If nothing to do, wait for next I/O or timer
        if not ready_queue and not waiting_queue:
            break  # No more work
        
        if not ready_queue:
            # Calculate timeout for next timer or I/O
            timeout = calculate_next_timeout(waiting_queue)
            io_selector.poll(timeout=timeout)

# This is a simplified version - the real event loop is more complex
```

### Demonstration of Event Loop Mechanics

```python
import asyncio
import time

async def demonstrate_event_loop_internals():
    """Show how the event loop switches between tasks"""
    
    async def task_with_io(name, duration):
        print(f"{name}: Started at {time.time():.2f}")
        await asyncio.sleep(duration)  # Simulates I/O operation
        print(f"{name}: Completed at {time.time():.2f}")
        return f"{name} result"
    
    async def task_with_computation(name):
        print(f"{name}: Computing...")
        # Simulate some quick computation
        for i in range(1000000):
            pass  # Computation doesn't yield
        print(f"{name}: Computation done at {time.time():.2f}")
        return f"{name} result"
    
    start_time = time.time()
    print(f"Starting at {start_time:.2f}")
    
    # Create multiple tasks
    tasks = [
        task_with_io("IO-1", 0.5),
        task_with_computation("CPU-1"),
        task_with_io("IO-2", 0.3),
        task_with_computation("CPU-2"),
    ]
    
    results = await asyncio.gather(*tasks)
    
    end_time = time.time()
    print(f"All tasks completed at {end_time:.2f}")
    print(f"Total duration: {end_time - start_time:.2f} seconds")
    
    return results

# You'll see that:
# 1. CPU tasks run to completion without interruption
# 2. I/O tasks yield control and other tasks can run
# 3. The event loop efficiently interleaves execution
```

### Yield Points and Control Flow

```python
import asyncio

async def demonstrate_yield_points():
    """Show where the event loop can switch between tasks"""
    
    print("1. Before first await")
    await asyncio.sleep(0)  # Yield point - control returns to event loop
    print("2. After first await")
    
    print("3. Before computation")
    # This doesn't yield - runs to completion
    result = sum(range(1000000))
    print("4. After computation")
    
    print("5. Before second await")
    await asyncio.sleep(0)  # Another yield point
    print("6. After second await")
    
    return result

async def concurrent_demonstration():
    """Show how tasks interleave at yield points"""
    
    async def task_a():
        for i in range(3):
            print(f"Task A - step {i}")
            await asyncio.sleep(0.1)  # Yield point
        return "A done"
    
    async def task_b():
        for i in range(3):
            print(f"Task B - step {i}")
            await asyncio.sleep(0.05)  # Yield point (shorter delay)
        return "B done"
    
    # Both tasks will interleave execution
    results = await asyncio.gather(task_a(), task_b())
    return results

# Run this to see how tasks switch at await points
```

### Event Loop and Operating System Integration

```python
import asyncio
import socket

async def demonstrate_os_integration():
    """Show how the event loop integrates with OS I/O facilities"""
    
    # Create a non-blocking socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setblocking(False)
    
    try:
        # This would normally block, but we make it async
        await asyncio.get_event_loop().sock_connect(sock, ("www.google.com", 80))
        print("Connection established")
        
        # Send HTTP request
        request = b"GET / HTTP/1.1\r\nHost: www.google.com\r\n\r\n"
        await asyncio.get_event_loop().sock_sendall(sock, request)
        print("Request sent")
        
        # Receive response
        response = await asyncio.get_event_loop().sock_recv(sock, 4096)
        print(f"Received {len(response)} bytes")
        
    finally:
        sock.close()
    
    # During each sock_* operation, the event loop:
    # 1. Registers the socket with the OS (epoll/kqueue/select)
    # 2. Yields control to other tasks
    # 3. Gets notified by OS when I/O is ready
    # 4. Resumes the coroutine
```

## 2.3 The Default Event Loop

Every asyncio program needs an event loop. Python provides a default event loop that handles most common scenarios.

### Getting the Event Loop

```python
import asyncio

def demonstrate_event_loop_access():
    """Show different ways to access the event loop"""
    
    # Method 1: Get the running event loop (Python 3.7+)
    async def inside_async_function():
        loop = asyncio.get_running_loop()
        print(f"Current loop: {loop}")
        print(f"Loop is running: {loop.is_running()}")
        return loop
    
    # Method 2: Get event loop (deprecated in favor of get_running_loop)
    def outside_async_function():
        try:
            loop = asyncio.get_running_loop()
            print("Loop is running")
        except RuntimeError:
            print("No running loop")
            loop = asyncio.new_event_loop()
            print(f"Created new loop: {loop}")
    
    # Method 3: Using asyncio.run() (recommended for main programs)
    async def main():
        loop = await inside_async_function()
        return loop
    
    # This creates and manages the event loop automatically
    result = asyncio.run(main())
    
    # Outside of asyncio.run(), there's no running loop
    outside_async_function()

# Run this to see different event loop access patterns
```

### Event Loop Properties and State

```python
import asyncio
import time

async def explore_event_loop_properties():
    """Explore event loop properties and state"""
    
    loop = asyncio.get_running_loop()
    
    print(f"Event loop: {loop}")
    print(f"Is running: {loop.is_running()}")
    print(f"Is closed: {loop.is_closed()}")
    print(f"Thread ID: {loop._thread_id}")  # Internal property
    
    # Schedule a callback to run on the next iteration
    def callback_function():
        print(f"Callback executed at {time.time():.3f}")
    
    # Schedule for immediate execution
    loop.call_soon(callback_function)
    
    # Schedule for execution after delay
    def delayed_callback():
        print(f"Delayed callback executed at {time.time():.3f}")
    
    start_time = time.time()
    print(f"Scheduling callback at {start_time:.3f}")
    loop.call_later(1.0, delayed_callback)
    
    # Schedule for execution at specific time
    def timed_callback():
        print(f"Timed callback executed at {time.time():.3f}")
    
    future_time = loop.time() + 2.0
    loop.call_at(future_time, timed_callback)
    
    # Wait for callbacks to execute
    await asyncio.sleep(2.5)
    
    # The loop automatically manages all these callbacks
```

### Event Loop Debug Mode

```python
import asyncio
import warnings

def demonstrate_debug_mode():
    """Show event loop debug features"""
    
    # Enable debug mode
    asyncio.get_event_loop().set_debug(True)
    
    # Or set via environment variable: PYTHONASYNCIODEBUG=1
    
    async def slow_coroutine():
        """This coroutine will trigger debug warnings"""
        print("Starting slow operation...")
        
        # This blocks the event loop - debug mode will warn about it
        time.sleep(0.2)  # DON'T DO THIS in real code
        
        print("Slow operation completed")
    
    async def proper_coroutine():
        """This coroutine yields properly"""
        print("Starting proper async operation...")
        await asyncio.sleep(0.2)  # This is correct
        print("Proper operation completed")
    
    async def main():
        print("Running in debug mode...")
        
        # This will generate warnings about blocking the event loop
        await slow_coroutine()
        
        # This won't generate warnings
        await proper_coroutine()
    
    # Enable debug mode and run
    loop = asyncio.new_event_loop()
    loop.set_debug(True)
    loop.run_until_complete(main())
    loop.close()

# Debug mode helps identify:
# - Blocking operations in async code
# - Unawaited coroutines
# - Long-running callbacks
```

## 2.4 Running the Event Loop

There are several ways to run an event loop. Understanding each method helps you choose the right approach for your use case.

### asyncio.run() - The Recommended Way

```python
import asyncio

async def simple_main():
    """Simple main coroutine"""
    print("Hello from async main!")
    await asyncio.sleep(1)
    print("Goodbye from async main!")
    return "Main completed"

# Method 1: asyncio.run() - Recommended for applications
def using_asyncio_run():
    """Using asyncio.run() to execute async code"""
    
    print("Starting with asyncio.run()")
    result = asyncio.run(simple_main())
    print(f"Result: {result}")
    print("Event loop is automatically closed")

# asyncio.run() does the following:
# 1. Creates a new event loop
# 2. Runs the coroutine
# 3. Closes the event loop
# 4. Handles KeyboardInterrupt gracefully
```

### Manual Event Loop Management

```python
import asyncio

def manual_event_loop():
    """Manually create and manage event loop"""
    
    # Create new event loop
    loop = asyncio.new_event_loop()
    
    # Set as the current event loop for this thread
    asyncio.set_event_loop(loop)
    
    try:
        # Run coroutine
        result = loop.run_until_complete(simple_main())
        print(f"Manual loop result: {result}")
        
        # Run multiple coroutines
        async def additional_work():
            print("Doing additional work...")
            await asyncio.sleep(0.5)
            return "Additional work done"
        
        additional_result = loop.run_until_complete(additional_work())
        print(f"Additional result: {additional_result}")
        
    finally:
        # Always close the loop
        loop.close()
        print("Manual loop closed")

def when_to_use_manual_management():
    """Examples of when manual management is needed"""
    
    # Example 1: Running in existing thread with event loop
    def run_in_thread():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(simple_main())
            return result
        finally:
            loop.close()
    
    # Example 2: Integration with other event loops (GUI frameworks)
    def integrate_with_gui():
        """Pseudocode for GUI integration"""
        # gui_framework.run() starts its own event loop
        # We need to integrate asyncio with it
        
        loop = asyncio.new_event_loop()
        
        def run_async_task():
            # Schedule async work on the asyncio loop
            asyncio.run_coroutine_threadsafe(simple_main(), loop)
        
        # gui_framework.schedule_callback(run_async_task)
        # gui_framework.run()
    
    # Example 3: Running multiple event loops (not recommended)
    def multiple_loops_example():
        """Generally not recommended - shown for completeness"""
        
        loop1 = asyncio.new_event_loop()
        loop2 = asyncio.new_event_loop()
        
        try:
            # Different loops in different threads
            import threading
            
            def run_loop1():
                asyncio.set_event_loop(loop1)
                loop1.run_until_complete(simple_main())
            
            def run_loop2():
                asyncio.set_event_loop(loop2)
                loop2.run_until_complete(simple_main())
            
            thread1 = threading.Thread(target=run_loop1)
            thread2 = threading.Thread(target=run_loop2)
            
            thread1.start()
            thread2.start()
            
            thread1.join()
            thread2.join()
            
        finally:
            loop1.close()
            loop2.close()
```

### Running Async Code from Sync Code

```python
import asyncio
import concurrent.futures
import threading

def calling_async_from_sync():
    """Different ways to call async code from synchronous code"""
    
    async def async_operation():
        await asyncio.sleep(1)
        return "Async result"
    
    # Method 1: asyncio.run() (creates new event loop)
    def method_1_new_loop():
        result = asyncio.run(async_operation())
        print(f"Method 1 result: {result}")
    
    # Method 2: Using existing event loop in another thread
    def method_2_threaded_loop():
        def run_in_thread():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(async_operation())
            finally:
                loop.close()
        
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(run_in_thread)
            result = future.result()
            print(f"Method 2 result: {result}")
    
    # Method 3: asyncio.run_coroutine_threadsafe() (if loop exists)
    def method_3_threadsafe():
        """Use when there's already a running loop in another thread"""
        
        def sync_function_in_thread():
            # This runs in a thread where we want to call async code
            # but there's already an event loop running in main thread
            
            # Get the event loop from main thread
            main_loop = asyncio.get_event_loop()  # This would be the main loop
            
            # Schedule coroutine on main loop
            future = asyncio.run_coroutine_threadsafe(async_operation(), main_loop)
            
            # Wait for result
            result = future.result(timeout=5)
            print(f"Method 3 result: {result}")
        
        # This is pseudocode - in practice you'd have the loop reference
    
    # Run the methods
    method_1_new_loop()
    method_2_threaded_loop()
```

### Error Handling in Event Loop Execution

```python
import asyncio

async def error_prone_coroutine():
    """Coroutine that might raise exceptions"""
    await asyncio.sleep(0.1)
    raise ValueError("Something went wrong!")

def error_handling_patterns():
    """Show different error handling patterns"""
    
    # Pattern 1: Simple try/catch with asyncio.run()
    def pattern_1_simple():
        try:
            asyncio.run(error_prone_coroutine())
        except ValueError as e:
            print(f"Caught error in asyncio.run(): {e}")
    
    # Pattern 2: Error handling inside coroutines
    async def pattern_2_internal():
        try:
            await error_prone_coroutine()
        except ValueError as e:
            print(f"Handled error inside coroutine: {e}")
            return "Error handled"
    
    # Pattern 3: Global exception handler
    def pattern_3_global_handler():
        def exception_handler(loop, context):
            print(f"Global handler caught: {context['exception']}")
            print(f"Message: {context['message']}")
        
        loop = asyncio.new_event_loop()
        loop.set_exception_handler(exception_handler)
        
        try:
            # Create a task that will fail
            async def failing_task():
                raise RuntimeError("Unhandled error in task")
            
            loop.run_until_complete(
                asyncio.create_task(failing_task())
            )
        except RuntimeError:
            pass  # Expected
        finally:
            loop.close()
    
    # Run error handling examples
    pattern_1_simple()
    asyncio.run(pattern_2_internal())
    pattern_3_global_handler()
```

## 2.5 Event Loop Lifecycle

Understanding the event loop lifecycle helps you manage resources properly and avoid common pitfalls.

### Event Loop States

```python
import asyncio

def demonstrate_event_loop_lifecycle():
    """Show the complete lifecycle of an event loop"""
    
    print("=== Event Loop Lifecycle Demo ===")
    
    # State 1: Not Created
    print("1. Before creation - no loop exists")
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError as e:
        print(f"   Expected error: {e}")
    
    # State 2: Created but not running
    print("\n2. Creating new event loop")
    loop = asyncio.new_event_loop()
    print(f"   Loop created: {loop}")
    print(f"   Is running: {loop.is_running()}")
    print(f"   Is closed: {loop.is_closed()}")
    
    # State 3: Set as current thread's loop
    print("\n3. Setting as current thread's loop")
    asyncio.set_event_loop(loop)
    current_loop = asyncio.get_event_loop()
    print(f"   Current loop is same: {current_loop is loop}")
    
    # State 4: Running
    print("\n4. Running the event loop")
    
    async def lifecycle_demo():
        print("   Inside running coroutine")
        running_loop = asyncio.get_running_loop()
        print(f"   Running loop is same: {running_loop is loop}")
        print(f"   Is running: {running_loop.is_running()}")
        
        # Schedule some work
        def callback():
            print("   Callback executed")
        
        running_loop.call_soon(callback)
        await asyncio.sleep(0.1)  # Let callback run
        
        return "Demo completed"
    
    result = loop.run_until_complete(lifecycle_demo())
    print(f"   Result: {result}")
    
    # State 5: Stopped but not closed
    print("\n5. Loop stopped but not closed")
    print(f"   Is running: {loop.is_running()}")
    print(f"   Is closed: {loop.is_closed()}")
    
    # Can still run more coroutines
    async def additional_work():
        await asyncio.sleep(0.1)
        return "Additional work done"
    
    additional_result = loop.run_until_complete(additional_work())
    print(f"   Additional result: {additional_result}")
    
    # State 6: Closed
    print("\n6. Closing the event loop")
    loop.close()
    print(f"   Is closed: {loop.is_closed()}")
    
    # Cannot run coroutines on closed loop
    try:
        loop.run_until_complete(additional_work())
    except RuntimeError as e:
        print(f"   Expected error on closed loop: {e}")
```

### Resource Management and Cleanup

```python
import asyncio
import aiohttp
import aiofiles

async def demonstrate_resource_cleanup():
    """Show proper resource management patterns"""
    
    print("=== Resource Management Demo ===")
    
    # Pattern 1: Manual resource management
    async def manual_cleanup():
        print("1. Manual cleanup pattern")
        
        # Create resources
        session = aiohttp.ClientSession()
        
        try:
            # Use resources
            async with session.get('https://httpbin.org/get') as response:
                data = await response.json()
                print(f"   Response status: {response.status}")
        
        finally:
            # Always cleanup
            await session.close()
            print("   Session closed manually")
    
    # Pattern 2: Context manager (preferred)
    async def context_manager_cleanup():
        print("2. Context manager pattern")
        
        # Resources automatically managed
        async with aiohttp.ClientSession() as session:
            async with session.get('https://httpbin.org/get') as response:
                data = await response.json()
                print(f"   Response status: {response.status}")
        
        print("   Session automatically closed")
    
    # Pattern 3: Multiple resources
    async def multiple_resources():
        print("3. Multiple resource management")
        
        async with aiohttp.ClientSession() as session:
            async with aiofiles.open('/tmp/test.txt', 'w') as f:
                # Use multiple async resources
                async with session.get('https://httpbin.org/json') as response:
                    data = await response.json()
                    await f.write(str(data))
                
                print("   Multiple resources used together")
        
        print("   All resources automatically closed")
    
    # Run cleanup demos
    await manual_cleanup()
    await context_manager_cleanup()
    await multiple_resources()

async def demonstrate_loop_cleanup():
    """Show event loop cleanup patterns"""
    
    # Get current loop
    loop = asyncio.get_running_loop()
    
    # Resources that need cleanup
    resources = []
    
    # Create some resources that need cleanup
    async def create_resource(name):
        print(f"Creating resource: {name}")
        resource = {"name": name, "closed": False}
        resources.append(resource)
        return resource
    
    # Cleanup function
    def cleanup_resources():
        print("Cleaning up resources...")
        for resource in resources:
            if not resource["closed"]:
                print(f"  Closing {resource['name']}")
                resource["closed"] = True
    
    # Register cleanup to run when loop shuts down
    loop.add_signal_handler(signal.SIGTERM, cleanup_resources)
    
    # Or use atexit for broader cleanup
    import atexit
    atexit.register(cleanup_resources)
    
    # Create some resources
    await create_resource("database_connection")
    await create_resource("file_handle")
    await create_resource("network_socket")
    
    print("Resources created, cleanup registered")
```

### Graceful Shutdown Patterns

```python
import asyncio
import signal

class GracefulShutdownExample:
    """Example of graceful shutdown handling"""
    
    def __init__(self):
        self.shutdown_event = asyncio.Event()
        self.running_tasks = set()
    
    async def worker_task(self, worker_id):
        """Simulate a long-running worker task"""
        try:
            while not self.shutdown_event.is_set():
                print(f"Worker {worker_id}: Working...")
                await asyncio.sleep(1)
        
        except asyncio.CancelledError:
            print(f"Worker {worker_id}: Received cancellation")
            # Cleanup work
            await asyncio.sleep(0.1)  # Simulate cleanup
            print(f"Worker {worker_id}: Cleanup completed")
            raise  # Re-raise to properly complete cancellation
    
    async def start_workers(self):
        """Start multiple worker tasks"""
        for i in range(3):
            task = asyncio.create_task(self.worker_task(i))
            self.running_tasks.add(task)
            
            # Remove completed tasks from set
            task.add_done_callback(self.running_tasks.discard)
    
    async def shutdown(self):
        """Graceful shutdown procedure"""
        print("Initiating graceful shutdown...")
        
        # Signal all tasks to stop
        self.shutdown_event.set()
        
        # Cancel all running tasks
        for task in self.running_tasks:
            task.cancel()
        
        # Wait for all tasks to complete cancellation
        if self.running_tasks:
            await asyncio.gather(*self.running_tasks, return_exceptions=True)
        
        print("Graceful shutdown completed")
    
    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        loop = asyncio.get_running_loop()
        
        def signal_handler():
            print("Received shutdown signal")
            # Create task to handle shutdown
            asyncio.create_task(self.shutdown())
        
        # Handle SIGTERM and SIGINT (Ctrl+C)
        for sig in [signal.SIGTERM, signal.SIGINT]:
            loop.add_signal_handler(sig, signal_handler)
    
    async def run(self):
        """Main application loop"""
        self.setup_signal_handlers()
        
        # Start workers
        await self.start_workers()
        
        # Wait for shutdown signal
        try:
            await self.shutdown_event.wait()
        except KeyboardInterrupt:
            await self.shutdown()

# Usage example
async def main():
    app = GracefulShutdownExample()
    await app.run()

# This would typically be run with: asyncio.run(main())
```

## 2.6 Event Loop Policies

Event loop policies determine how event loops are created and managed. Understanding policies helps with advanced scenarios like testing, GUI integration, and custom loop implementations.

### Default Event Loop Policy

```python
import asyncio

def explore_event_loop_policies():
    """Explore event loop policies"""
    
    print("=== Event Loop Policy Demo ===")
    
    # Get current policy
    current_policy = asyncio.get_event_loop_policy()
    print(f"Current policy: {current_policy}")
    print(f"Policy class: {current_policy.__class__.__name__}")
    
    # Get default loop for current thread
    default_loop = current_policy.get_event_loop()
    print(f"Default loop: {default_loop}")
    
    # Create new loop using policy
    new_loop = current_policy.new_event_loop()
    print(f"New loop from policy: {new_loop}")
    
    # Set as current loop
    current_policy.set_event_loop(new_loop)
    current_loop = current_policy.get_event_loop()
    print(f"Current loop after set: {current_loop}")
    print(f"Is same as new loop: {current_loop is new_loop}")
    
    # Cleanup
    new_loop.close()

def demonstrate_policy_differences():
    """Show differences between platforms"""
    
    import sys
    
    print(f"Platform: {sys.platform}")
    
    # Different platforms use different policies
    if sys.platform == 'win32':
        print("Windows uses ProactorEventLoopPolicy by default")
        # Windows supports both Proactor and Selector policies
        
        # Get current policy  
        policy = asyncio.get_event_loop_policy()
        print(f"Default policy: {policy.__class__.__name__}")
        
        # Can switch to SelectorEventLoopPolicy
        selector_policy = asyncio.WindowsSelectorEventLoopPolicy()
        print(f"Selector policy: {selector_policy.__class__.__name__}")
        
    else:
        print("Unix-like systems use DefaultEventLoopPolicy")
        # Unix systems use selector-based loops (epoll, kqueue)
        
        policy = asyncio.get_event_loop_policy()
        print(f"Default policy: {policy.__class__.__name__}")

# Run policy exploration
explore_event_loop_policies()
demonstrate_policy_differences()
```

### Custom Event Loop Policies

```python
import asyncio
import logging

class CustomEventLoopPolicy(asyncio.DefaultEventLoopPolicy):
    """Custom event loop policy for debugging/monitoring"""
    
    def new_event_loop(self):
        """Create a new event loop with custom configuration"""
        loop = super().new_event_loop()
        
        # Configure the loop
        loop.set_debug(True)
        
        # Add custom exception handler
        def custom_exception_handler(loop, context):
            logging.error(f"Custom handler: {context}")
        
        loop.set_exception_handler(custom_exception_handler)
        
        print(f"Created custom event loop: {loop}")
        return loop
    
    def get_event_loop(self):
        """Get event loop with logging"""
        loop = super().get_event_loop()
        print(f"Retrieved event loop: {loop}")
        return loop

class MonitoringEventLoopPolicy(asyncio.DefaultEventLoopPolicy):
    """Event loop policy that monitors loop usage"""
    
    def __init__(self):
        super().__init__()
        self.loop_count = 0
        self.active_loops = set()
    
    def new_event_loop(self):
        """Create monitored event loop"""
        loop = super().new_event_loop()
        self.loop_count += 1
        self.active_loops.add(loop)
        
        # Patch close method to track when loops are closed
        original_close = loop.close
        
        def monitored_close():
            self.active_loops.discard(loop)
            print(f"Loop closed. Active loops: {len(self.active_loops)}")
            original_close()
        
        loop.close = monitored_close
        
        print(f"Created loop #{self.loop_count}. Active: {len(self.active_loops)}")
        return loop
    
    def get_stats(self):
        """Get monitoring statistics"""
        return {
            'total_created': self.loop_count,
            'currently_active': len(self.active_loops)
        }

def demonstrate_custom_policies():
    """Demonstrate custom event loop policies"""
    
    print("=== Custom Policy Demo ===")
    
    # Save original policy
    original_policy = asyncio.get_event_loop_policy()
    
    try:
        # Install custom policy
        custom_policy = MonitoringEventLoopPolicy()
        asyncio.set_event_loop_policy(custom_policy)
        
        # Use the policy
        async def test_coroutine():
            await asyncio.sleep(0.1)
            return "Test completed"
        
        # Create and use multiple loops
        for i in range(3):
            print(f"\n--- Loop {i+1} ---")
            result = asyncio.run(test_coroutine())
            print(f"Result: {result}")
            print(f"Stats: {custom_policy.get_stats()}")
        
        print(f"\nFinal stats: {custom_policy.get_stats()}")
        
    finally:
        # Restore original policy
        asyncio.set_event_loop_policy(original_policy)

# Run custom policy demo
demonstrate_custom_policies()
```

### Testing with Event Loop Policies

```python
import asyncio
import pytest

class TestEventLoopPolicy(asyncio.DefaultEventLoopPolicy):
    """Special policy for testing that provides isolation"""
    
    def new_event_loop(self):
        loop = super().new_event_loop()
        
        # Enable debug mode for tests
        loop.set_debug(True)
        
        # Track created tasks for cleanup
        loop._created_tasks = set()
        original_create_task = loop.create_task
        
        def tracked_create_task(coro):
            task = original_create_task(coro)
            loop._created_tasks.add(task)
            task.add_done_callback(loop._created_tasks.discard)
            return task
        
        loop.create_task = tracked_create_task
        
        return loop

def demonstrate_testing_policy():
    """Show how custom policies help with testing"""
    
    # Install testing policy
    test_policy = TestEventLoopPolicy()
    asyncio.set_event_loop_policy(test_policy)
    
    async def test_function():
        """Function that creates background tasks"""
        
        async def background_task():
            await asyncio.sleep(1)
            return "Background task done"
        
        # Create background task
        task = asyncio.create_task(background_task())
        
        # Do some work
        await asyncio.sleep(0.1)
        
        # Check if we have tracking
        loop = asyncio.get_running_loop()
        if hasattr(loop, '_created_tasks'):
            print(f"Active background tasks: {len(loop._created_tasks)}")
        
        # Cancel background tasks for cleanup
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        
        return "Test completed"
    
    # Run test
    result = asyncio.run(test_function())
    print(f"Test result: {result}")

# This pattern is useful for pytest fixtures that manage event loops
```

## 2.7 Creating Custom Event Loops

While rarely needed, understanding how to create custom event loops provides deep insight into asyncio's architecture.

### Understanding Event Loop Interface

```python
import asyncio
from asyncio import AbstractEventLoop
import time

class SimpleEventLoop:
    """Simplified event loop to understand the interface"""
    
    def __init__(self):
        self._ready = []          # Tasks ready to run
        self._scheduled = []      # Tasks scheduled for future execution
        self._running = False
        self._closed = False
    
    def call_soon(self, callback, *args):
        """Schedule callback for immediate execution"""
        handle = Handle(callback, args, self)
        self._ready.append(handle)
        return handle
    
    def call_later(self, delay, callback, *args):
        """Schedule callback for execution after delay"""
        when = time.time() + delay
        handle = TimerHandle(when, callback, args, self)
        self._scheduled.append(handle)
        self._scheduled.sort(key=lambda h: h.when)
        return handle
    
    def time(self):
        """Current time for the event loop"""
        return time.time()
    
    def is_running(self):
        """Check if loop is running"""
        return self._running
    
    def is_closed(self):
        """Check if loop is closed"""
        return self._closed
    
    def run_until_complete(self, coro):
        """Run coroutine until completion"""
        if self._running:
            raise RuntimeError("Event loop is already running")
        
        if not asyncio.iscoroutine(coro):
            raise TypeError("Expected coroutine")
        
        task = self.create_task(coro)
        self._running = True
        
        try:
            return self._run_once_until_complete(task)
        finally:
            self._running = False
    
    def create_task(self, coro):
        """Create a task from coroutine"""
        # This is simplified - real implementation is more complex
        return SimpleTask(coro, self)
    
    def _run_once_until_complete(self, task):
        """Main event loop iteration"""
        while not task.done():
            self._run_once()
        
        return task.result()
    
    def _run_once(self):
        """Single iteration of event loop"""
        # Execute ready callbacks
        count = len(self._ready)
        for _ in range(count):
            if self._ready:
                handle = self._ready.pop(0)
                if not handle.cancelled:
                    handle.run()
        
        # Check scheduled callbacks
        now = time.time()
        while self._scheduled and self._scheduled[0].when <= now:
            handle = self._scheduled.pop(0)
            if not handle.cancelled:
                self._ready.append(handle)
        
        # In real implementation, this would also:
        # - Check for I/O events (select/epoll/kqueue)
        # - Handle timeouts properly
        # - Manage task scheduling
    
    def close(self):
        """Close the event loop"""
        self._closed = True

class Handle:
    """Callback handle"""
    def __init__(self, callback, args, loop):
        self.callback = callback
        self.args = args
        self.loop = loop
        self.cancelled = False
    
    def cancel(self):
        self.cancelled = True
    
    def run(self):
        if not self.cancelled:
            self.callback(*self.args)

class TimerHandle(Handle):
    """Timer callback handle"""
    def __init__(self, when, callback, args, loop):
        super().__init__(callback, args, loop)
        self.when = when

class SimpleTask:
    """Simplified task implementation"""
    def __init__(self, coro, loop):
        self.coro = coro
        self.loop = loop
        self._done = False
        self._result = None
        self._exception = None
        
        # Start the coroutine
        self._step()
    
    def _step(self):
        """Execute one step of the coroutine"""
        try:
            if self._exception is not None:
                result = self.coro.throw(self._exception)
            else:
                result = self.coro.send(self._result)
        
        except StopIteration as e:
            self._done = True
            self._result = e.value
        
        except Exception as e:
            self._done = True
            self._exception = e
        
        else:
            # Coroutine yielded something - handle it
            if result is None:
                # Yield to event loop
                self.loop.call_soon(self._step)
            else:
                # In real implementation, handle different yield types
                self.loop.call_soon(self._step)
    
    def done(self):
        return self._done
    
    def result(self):
        if self._exception:
            raise self._exception
        return self._result

def demonstrate_custom_loop():
    """Demonstrate the custom event loop"""
    
    loop = SimpleEventLoop()
    
    def callback():
        print("Callback executed")
    
    # Schedule immediate callback
    loop.call_soon(callback)
    
    # Schedule delayed callback
    loop.call_later(0.1, lambda: print("Delayed callback"))
    
    # Simple coroutine to test
    async def simple_coro():
        print("Coroutine start")
        # Note: our simple loop doesn't handle asyncio.sleep properly
        # This is just for demonstration
        print("Coroutine end")
        return "Simple result"
    
    result = loop.run_until_complete(simple_coro())
    print(f"Result: {result}")
    
    loop.close()

# Run the custom loop demo
demonstrate_custom_loop()
```

### Integrating with External Event Loops

```python
import asyncio
import tkinter as tk
from typing import Optional

class TkinterEventLoopIntegration:
    """Integration between asyncio and tkinter event loops"""
    
    def __init__(self, root: tk.Tk):
        self.root = root
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.running = False
    
    def run_asyncio_with_tkinter(self):
        """Run asyncio loop integrated with tkinter"""
        
        # Create asyncio loop
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        # Schedule periodic asyncio processing
        def process_asyncio():
            if self.loop and not self.loop.is_closed():
                # Process asyncio events
                self.loop.call_soon(lambda: None)  # Wake up the loop
                self.loop._run_once_impl()  # Process one iteration
                
                # Schedule next processing
                self.root.after(10, process_asyncio)  # 10ms intervals
        
        # Start the integration
        process_asyncio()
        
        # Run tkinter main loop
        self.root.mainloop()
        
        # Cleanup
        if self.loop:
            self.loop.close()
    
    def schedule_coroutine(self, coro):
        """Schedule coroutine on the asyncio loop"""
        if self.loop:
            return asyncio.run_coroutine_threadsafe(coro, self.loop)

def demonstrate_gui_integration():
    """Demonstrate GUI event loop integration"""
    
    # This is pseudocode - would require actual GUI framework
    
    root = tk.Tk()
    integration = TkinterEventLoopIntegration(root)
    
    async def async_background_task():
        """Background async task"""
        for i in range(10):
            print(f"Background task iteration {i}")
            await asyncio.sleep(1)
        print("Background task completed")
    
    def start_async_task():
        """Start async task from GUI"""
        integration.schedule_coroutine(async_background_task())
    
    # Add button to start async task
    button = tk.Button(root, text="Start Async Task", command=start_async_task)
    button.pack()
    
    # This would run the integrated event loops
    # integration.run_asyncio_with_tkinter()
```

The event loop is the foundation that makes asyncio possible. In the next chapter, we'll explore coroutines - the building blocks that run on top of the event loop.
# Chapter 12: Mixing Asyncio with Threads and Processes

## 12.1 When to Use Threads with Asyncio

Asyncio excels at I/O-bound operations, but sometimes you need to integrate with thread-based code or handle CPU-intensive tasks. Understanding when and how to mix asyncio with threads is crucial for building robust applications.

### Understanding the Use Cases

```python
import asyncio
import threading
import time
import concurrent.futures
import queue
import requests  # Blocking HTTP library

async def demonstrate_thread_integration_scenarios():
    """Demonstrate when to use threads with asyncio"""
    
    print("=== When to Use Threads with Asyncio ===")
    
    # Scenario 1: Blocking I/O operations that can't be made async
    print("1. Blocking I/O operations:")
    
    def blocking_http_request(url):
        """Blocking HTTP request using requests library"""
        print(f"   Thread {threading.current_thread().name}: Fetching {url}")
        response = requests.get(url, timeout=5)
        print(f"   Thread {threading.current_thread().name}: Got response {response.status_code}")
        return {"url": url, "status": response.status_code, "length": len(response.content)}
    
    async def fetch_multiple_urls():
        """Fetch multiple URLs using thread pool"""
        urls = [
            "https://httpbin.org/delay/1",
            "https://httpbin.org/delay/2", 
            "https://httpbin.org/get"
        ]
        
        loop = asyncio.get_event_loop()
        
        # Run blocking requests in thread pool
        tasks = []
        for url in urls:
            task = loop.run_in_executor(None, blocking_http_request, url)
            tasks.append(task)
        
        try:
            results = await asyncio.gather(*tasks)
            print(f"   Fetched {len(results)} URLs concurrently using threads")
            for result in results:
                print(f"     {result['url']}: {result['status']} ({result['length']} bytes)")
        except Exception as e:
            print(f"   Error fetching URLs: {e}")
    
    await fetch_multiple_urls()
    
    # Scenario 2: Legacy synchronous libraries
    print("\n2. Legacy synchronous libraries:")
    
    class LegacyDatabaseDriver:
        """Simulate legacy blocking database driver"""
        
        def __init__(self):
            self.connection_pool = None
        
        def connect(self):
            """Blocking connection setup"""
            print("   Legacy DB: Connecting (blocking)...")
            time.sleep(0.5)  # Simulate connection time
            self.connection_pool = "connected"
            print("   Legacy DB: Connected")
        
        def execute_query(self, query):
            """Blocking query execution"""
            if not self.connection_pool:
                raise RuntimeError("Not connected")
            
            print(f"   Legacy DB: Executing '{query}' (blocking)...")
            time.sleep(0.3)  # Simulate query time
            
            # Simulate different results
            if "SELECT" in query:
                return [{"id": i, "name": f"record_{i}"} for i in range(3)]
            elif "INSERT" in query:
                return {"inserted_id": 123}
            elif "UPDATE" in query:
                return {"affected_rows": 5}
            else:
                return {"result": "OK"}
        
        def disconnect(self):
            """Blocking disconnection"""
            print("   Legacy DB: Disconnecting...")
            time.sleep(0.1)
            self.connection_pool = None
    
    async def use_legacy_database():
        """Use legacy database driver from async code"""
        db = LegacyDatabaseDriver()
        loop = asyncio.get_event_loop()
        
        try:
            # Run blocking operations in executor
            await loop.run_in_executor(None, db.connect)
            
            # Execute multiple queries concurrently
            queries = [
                "SELECT * FROM users",
                "INSERT INTO logs VALUES (...)",
                "UPDATE users SET active=1",
                "SELECT COUNT(*) FROM sessions"
            ]
            
            query_tasks = [
                loop.run_in_executor(None, db.execute_query, query)
                for query in queries
            ]
            
            results = await asyncio.gather(*query_tasks)
            
            print(f"   Executed {len(results)} queries concurrently:")
            for i, result in enumerate(results):
                print(f"     Query {i+1}: {result}")
        
        finally:
            await loop.run_in_executor(None, db.disconnect)
    
    await use_legacy_database()
    
    # Scenario 3: CPU-bound computations
    print("\n3. CPU-bound computations:")
    
    def cpu_intensive_task(n, task_id):
        """CPU-intensive computation"""
        print(f"   CPU Task {task_id}: Starting computation for n={n}")
        
        # Simulate heavy computation
        result = 0
        for i in range(n * 100000):
            result += i * i
        
        print(f"   CPU Task {task_id}: Completed")
        return {"task_id": task_id, "input": n, "result": result}
    
    async def run_cpu_intensive_work():
        """Run CPU-intensive work without blocking event loop"""
        work_items = [1000, 1500, 800, 1200, 900]
        
        loop = asyncio.get_event_loop()
        
        # Use ProcessPoolExecutor for CPU-bound work
        with concurrent.futures.ProcessPoolExecutor(max_workers=3) as executor:
            tasks = [
                loop.run_in_executor(executor, cpu_intensive_task, n, i)
                for i, n in enumerate(work_items)
            ]
            
            start_time = time.time()
            results = await asyncio.gather(*tasks)
            end_time = time.time()
            
            print(f"   Completed {len(results)} CPU tasks in {end_time - start_time:.2f}s")
            for result in results:
                print(f"     Task {result['task_id']}: {result['input']} -> {result['result']}")
    
    await run_cpu_intensive_work()

asyncio.run(demonstrate_thread_integration_scenarios())
```

### Thread Safety Considerations

```python
import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor
import queue

async def demonstrate_thread_safety():
    """Demonstrate thread safety considerations when mixing asyncio and threads"""
    
    print("=== Thread Safety Considerations ===")
    
    print("1. Shared state between async and threaded code:")
    
    class ThreadSafeCounter:
        """Thread-safe counter for demonstration"""
        
        def __init__(self):
            self._value = 0
            self._lock = threading.Lock()
        
        def increment(self):
            """Thread-safe increment"""
            with self._lock:
                current = self._value
                time.sleep(0.001)  # Simulate work that could cause race condition
                self._value = current + 1
                return self._value
        
        def get_value(self):
            """Thread-safe read"""
            with self._lock:
                return self._value
    
    class UnsafeCounter:
        """Unsafe counter for comparison"""
        
        def __init__(self):
            self._value = 0
        
        def increment(self):
            """Non-thread-safe increment"""
            current = self._value
            time.sleep(0.001)  # Race condition opportunity
            self._value = current + 1
            return self._value
        
        def get_value(self):
            return self._value
    
    def thread_worker(counter, worker_id, increments):
        """Worker function that runs in thread"""
        print(f"   Worker {worker_id}: Starting {increments} increments")
        
        for i in range(increments):
            counter.increment()
        
        print(f"   Worker {worker_id}: Completed")
    
    async def test_thread_safety():
        """Test thread safety with concurrent workers"""
        
        # Test thread-safe counter
        safe_counter = ThreadSafeCounter()
        unsafe_counter = UnsafeCounter()
        
        loop = asyncio.get_event_loop()
        
        # Run multiple workers concurrently
        num_workers = 5
        increments_per_worker = 20
        expected_total = num_workers * increments_per_worker
        
        print(f"   Running {num_workers} workers, {increments_per_worker} increments each")
        print(f"   Expected total: {expected_total}")
        
        # Test safe counter
        safe_tasks = [
            loop.run_in_executor(None, thread_worker, safe_counter, i, increments_per_worker)
            for i in range(num_workers)
        ]
        
        await asyncio.gather(*safe_tasks)
        safe_result = safe_counter.get_value()
        print(f"   Thread-safe counter result: {safe_result}")
        
        # Test unsafe counter
        unsafe_tasks = [
            loop.run_in_executor(None, thread_worker, unsafe_counter, i, increments_per_worker)
            for i in range(num_workers)
        ]
        
        await asyncio.gather(*unsafe_tasks)
        unsafe_result = unsafe_counter.get_value()
        print(f"   Unsafe counter result: {unsafe_result}")
        
        print(f"   Race condition detected: {unsafe_result != expected_total}")
    
    await test_thread_safety()
    
    print("\n2. Communication between async and threaded code:")
    
    class AsyncThreadBridge:
        """Bridge for communication between async and threaded code"""
        
        def __init__(self):
            self.thread_to_async_queue = queue.Queue()
            self.async_to_thread_queue = asyncio.Queue()
            self.running = True
        
        async def start_bridge(self):
            """Start the communication bridge"""
            
            # Task to move data from thread queue to async queue
            async def bridge_thread_to_async():
                while self.running:
                    try:
                        # Check thread queue (non-blocking)
                        try:
                            item = self.thread_to_async_queue.get_nowait()
                            await self.async_to_thread_queue.put(item)
                            print(f"   Bridge: Moved item from thread to async: {item}")
                        except queue.Empty:
                            pass
                        
                        await asyncio.sleep(0.01)  # Small delay
                    except Exception as e:
                        print(f"   Bridge error: {e}")
                        break
            
            return asyncio.create_task(bridge_thread_to_async())
        
        def send_from_thread(self, data):
            """Send data from thread to async code"""
            self.thread_to_async_queue.put(data)
        
        async def receive_in_async(self, timeout=1.0):
            """Receive data in async code"""
            try:
                return await asyncio.wait_for(
                    self.async_to_thread_queue.get(),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                return None
        
        def stop(self):
            """Stop the bridge"""
            self.running = False
    
    def threaded_data_producer(bridge, worker_id):
        """Producer running in thread"""
        for i in range(5):
            data = f"data_{worker_id}_{i}"
            bridge.send_from_thread(data)
            print(f"   Thread Producer {worker_id}: Sent {data}")
            time.sleep(0.2)
    
    async def async_data_consumer(bridge, num_expected):
        """Consumer running in async code"""
        received_items = []
        
        for i in range(num_expected):
            item = await bridge.receive_in_async(timeout=2.0)
            if item:
                received_items.append(item)
                print(f"   Async Consumer: Received {item}")
            else:
                print(f"   Async Consumer: Timeout on item {i}")
        
        return received_items
    
    async def test_async_thread_communication():
        """Test communication between async and threaded code"""
        bridge = AsyncThreadBridge()
        
        # Start the bridge
        bridge_task = await bridge.start_bridge()
        
        try:
            loop = asyncio.get_event_loop()
            
            # Start thread producers
            num_producers = 3
            producer_tasks = [
                loop.run_in_executor(None, threaded_data_producer, bridge, i)
                for i in range(num_producers)
            ]
            
            # Start async consumer
            expected_items = num_producers * 5
            consumer_task = asyncio.create_task(
                async_data_consumer(bridge, expected_items)
            )
            
            # Wait for producers and consumer
            await asyncio.gather(*producer_tasks)
            received_items = await consumer_task
            
            print(f"   Communication test: Sent {expected_items}, Received {len(received_items)}")
        
        finally:
            bridge.stop()
            bridge_task.cancel()
            await asyncio.gather(bridge_task, return_exceptions=True)
    
    await test_async_thread_communication()

asyncio.run(demonstrate_thread_safety())
```

### Event Loop Thread Safety

```python
import asyncio
import threading
import time

async def demonstrate_event_loop_thread_safety():
    """Demonstrate event loop thread safety patterns"""
    
    print("=== Event Loop Thread Safety ===")
    
    print("1. run_coroutine_threadsafe() usage:")
    
    async def async_callback(data):
        """Async callback that will be called from thread"""
        print(f"   Async callback: Processing {data}")
        await asyncio.sleep(0.1)  # Simulate async work
        return f"Processed: {data}"
    
    def threaded_function(loop, data_items):
        """Function running in thread that needs to call async code"""
        print(f"   Thread {threading.current_thread().name}: Starting")
        results = []
        
        for data in data_items:
            print(f"   Thread: Scheduling async callback for {data}")
            
            # Schedule coroutine on event loop from thread
            future = asyncio.run_coroutine_threadsafe(
                async_callback(data), loop
            )
            
            try:
                # Wait for result (this blocks the thread)
                result = future.result(timeout=2.0)
                results.append(result)
                print(f"   Thread: Got result {result}")
            except Exception as e:
                print(f"   Thread: Error getting result: {e}")
        
        print(f"   Thread: Completed with {len(results)} results")
        return results
    
    async def test_threadsafe_coroutine_calls():
        """Test calling coroutines from threads"""
        loop = asyncio.get_event_loop()
        
        # Data for threads to process
        data_sets = [
            ["item_1_a", "item_1_b"],
            ["item_2_a", "item_2_b", "item_2_c"],
            ["item_3_a"]
        ]
        
        # Start threads
        thread_futures = []
        for i, data_set in enumerate(data_sets):
            future = asyncio.get_event_loop().run_in_executor(
                None, threaded_function, loop, data_set
            )
            thread_futures.append(future)
        
        # Wait for all threads to complete
        all_results = await asyncio.gather(*thread_futures)
        
        print(f"   All threads completed:")
        for i, results in enumerate(all_results):
            print(f"     Thread {i}: {len(results)} items processed")
    
    await test_threadsafe_coroutine_calls()
    
    print("\n2. Thread-safe event handling:")
    
    class ThreadSafeEventManager:
        """Event manager that can be used from both async and threaded code"""
        
        def __init__(self, loop):
            self.loop = loop
            self.event_handlers = {}
            self._handler_id = 0
        
        def register_handler(self, event_type, handler):
            """Register an event handler (thread-safe)"""
            handler_id = self._handler_id
            self._handler_id += 1
            
            if event_type not in self.event_handlers:
                self.event_handlers[event_type] = {}
            
            self.event_handlers[event_type][handler_id] = handler
            return handler_id
        
        def emit_from_thread(self, event_type, data):
            """Emit event from thread"""
            print(f"   Thread: Emitting {event_type} event with data: {data}")
            
            # Schedule event handling on event loop
            asyncio.run_coroutine_threadsafe(
                self._handle_event_async(event_type, data),
                self.loop
            )
        
        async def emit_from_async(self, event_type, data):
            """Emit event from async code"""
            print(f"   Async: Emitting {event_type} event with data: {data}")
            await self._handle_event_async(event_type, data)
        
        async def _handle_event_async(self, event_type, data):
            """Handle event in async context"""
            if event_type not in self.event_handlers:
                return
            
            handlers = self.event_handlers[event_type]
            tasks = []
            
            for handler_id, handler in handlers.items():
                if asyncio.iscoroutinefunction(handler):
                    task = asyncio.create_task(handler(data))
                    tasks.append(task)
                else:
                    # Run sync handler in executor
                    task = self.loop.run_in_executor(None, handler, data)
                    tasks.append(task)
            
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
    
    async def async_event_handler(data):
        """Async event handler"""
        await asyncio.sleep(0.1)
        print(f"   Async handler processed: {data}")
    
    def sync_event_handler(data):
        """Sync event handler"""
        time.sleep(0.05)
        print(f"   Sync handler processed: {data}")
    
    def thread_event_emitter(event_manager, thread_id):
        """Thread function that emits events"""
        for i in range(3):
            event_data = f"thread_{thread_id}_event_{i}"
            event_manager.emit_from_thread("test_event", event_data)
            time.sleep(0.1)
    
    async def test_threadsafe_events():
        """Test thread-safe event handling"""
        loop = asyncio.get_event_loop()
        event_manager = ThreadSafeEventManager(loop)
        
        # Register event handlers
        event_manager.register_handler("test_event", async_event_handler)
        event_manager.register_handler("test_event", sync_event_handler)
        
        # Start thread emitters
        emitter_tasks = [
            loop.run_in_executor(None, thread_event_emitter, event_manager, i)
            for i in range(2)
        ]
        
        # Also emit some events from async code
        async def async_emitter():
            for i in range(2):
                await event_manager.emit_from_async("test_event", f"async_event_{i}")
                await asyncio.sleep(0.15)
        
        async_emitter_task = asyncio.create_task(async_emitter())
        
        # Wait for all emitters
        await asyncio.gather(*emitter_tasks, async_emitter_task)
        
        # Give handlers time to complete
        await asyncio.sleep(0.5)
        
        print("   Thread-safe event handling completed")
    
    await test_threadsafe_events()
    
    print("\n3. Proper cleanup of threads and async tasks:")
    
    class ThreadPoolManager:
        """Manage thread pool with proper cleanup"""
        
        def __init__(self, max_workers=3):
            self.executor = ThreadPoolExecutor(max_workers=max_workers)
            self.active_futures = set()
        
        async def submit_task(self, func, *args):
            """Submit task to thread pool"""
            loop = asyncio.get_event_loop()
            future = loop.run_in_executor(self.executor, func, *args)
            
            # Track active futures
            self.active_futures.add(future)
            
            # Remove from tracking when done
            def cleanup(fut):
                self.active_futures.discard(fut)
            
            future.add_done_callback(cleanup)
            
            return future
        
        async def shutdown(self, timeout=5.0):
            """Shutdown thread pool with timeout"""
            print(f"   Shutting down thread pool with {len(self.active_futures)} active tasks")
            
            # Cancel pending futures
            for future in list(self.active_futures):
                if not future.done():
                    future.cancel()
            
            # Wait for remaining tasks with timeout
            if self.active_futures:
                try:
                    await asyncio.wait_for(
                        asyncio.gather(*self.active_futures, return_exceptions=True),
                        timeout=timeout
                    )
                except asyncio.TimeoutError:
                    print("   Some tasks didn't complete within timeout")
            
            # Shutdown executor
            self.executor.shutdown(wait=True)
            print("   Thread pool shutdown completed")
    
    def long_running_task(task_id, duration):
        """Long running task for testing cleanup"""
        print(f"   Task {task_id}: Starting ({duration}s)")
        
        start_time = time.time()
        while time.time() - start_time < duration:
            time.sleep(0.1)
            # Check if thread should exit (in real code, use proper cancellation)
        
        print(f"   Task {task_id}: Completed")
        return f"Task {task_id} result"
    
    async def test_proper_cleanup():
        """Test proper cleanup of threads and async tasks"""
        manager = ThreadPoolManager()
        
        try:
            # Submit various tasks
            tasks = [
                await manager.submit_task(long_running_task, i, 0.5)
                for i in range(5)
            ]
            
            # Wait for some tasks to complete
            await asyncio.sleep(0.3)
            
            print("   Starting shutdown...")
            
        finally:
            await manager.shutdown()
    
    await test_proper_cleanup()

asyncio.run(demonstrate_event_loop_thread_safety())
```

## 12.2 run_in_executor() for Blocking Code

The `run_in_executor()` method is the primary way to run blocking code from async functions without blocking the event loop.

### Basic run_in_executor() Usage

```python
import asyncio
import time
import concurrent.futures
import threading
import os
import hashlib

async def demonstrate_run_in_executor_basics():
    """Demonstrate basic run_in_executor usage patterns"""
    
    print("=== Basic run_in_executor Usage ===")
    
    print("1. Running blocking I/O operations:")
    
    def blocking_file_operation(filename, data):
        """Simulate blocking file operation"""
        thread_name = threading.current_thread().name
        print(f"   {thread_name}: Writing {len(data)} bytes to {filename}")
        
        # Simulate slow file write
        time.sleep(0.5)
        
        with open(filename, 'w') as f:
            f.write(data)
        
        print(f"   {thread_name}: Completed writing {filename}")
        return f"Wrote {len(data)} bytes to {filename}"
    
    async def async_file_operations():
        """Run multiple file operations concurrently"""
        loop = asyncio.get_event_loop()
        
        # Prepare test data
        files_data = [
            ("test1.txt", "Data for file 1\n" * 100),
            ("test2.txt", "Data for file 2\n" * 150),
            ("test3.txt", "Data for file 3\n" * 80),
        ]
        
        # Run all file operations concurrently in thread pool
        tasks = [
            loop.run_in_executor(None, blocking_file_operation, filename, data)
            for filename, data in files_data
        ]
        
        start_time = time.time()
        results = await asyncio.gather(*tasks)
        end_time = time.time()
        
        print(f"   Completed {len(results)} file operations in {end_time - start_time:.2f}s")
        
        # Cleanup
        for filename, _ in files_data:
            try:
                os.unlink(filename)
            except FileNotFoundError:
                pass
        
        return results
    
    await async_file_operations()
    
    print("\n2. Running CPU-intensive computations:")
    
    def cpu_intensive_computation(data, algorithm="sha256"):
        """CPU-intensive computation that shouldn't block event loop"""
        thread_name = threading.current_thread().name
        print(f"   {thread_name}: Starting {algorithm} computation")
        
        # Simulate CPU-intensive work
        hasher = hashlib.new(algorithm)
        
        for i in range(1000):
            hasher.update(f"{data}_{i}".encode())
            
            # Simulate more work
            if i % 100 == 0:
                time.sleep(0.001)  # Tiny delay to simulate real work
        
        result = hasher.hexdigest()
        print(f"   {thread_name}: Completed {algorithm} computation")
        return result
    
    async def async_cpu_work():
        """Run CPU work without blocking event loop"""
        loop = asyncio.get_event_loop()
        
        # Different computations to run
        computations = [
            ("data_set_1", "md5"),
            ("data_set_2", "sha1"),
            ("data_set_3", "sha256"),
            ("data_set_4", "sha224"),
        ]
        
        # Run computations in thread pool
        tasks = [
            loop.run_in_executor(None, cpu_intensive_computation, data, algo)
            for data, algo in computations
        ]
        
        start_time = time.time()
        results = await asyncio.gather(*tasks)
        end_time = time.time()
        
        print(f"   Completed {len(results)} computations in {end_time - start_time:.2f}s")
        for i, (data, algo) in enumerate(computations):
            print(f"     {algo}({data}): {results[i][:16]}...")
    
    await async_cpu_work()
    
    print("\n3. Different executor types:")
    
    def thread_work(worker_id, work_type="thread"):
        """Work function for different executor types"""
        thread_name = threading.current_thread().name
        process_id = os.getpid()
        
        print(f"   {work_type} worker {worker_id}: Thread={thread_name}, PID={process_id}")
        
        # Simulate work
        result = 0
        for i in range(1000000):
            result += i
        
        return {
            "worker_id": worker_id,
            "work_type": work_type,
            "thread": thread_name,
            "pid": process_id,
            "result": result
        }
    
    async def test_different_executors():
        """Test different executor types"""
        loop = asyncio.get_event_loop()
        
        print("   ThreadPoolExecutor:")
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as thread_executor:
            thread_tasks = [
                loop.run_in_executor(thread_executor, thread_work, i, "thread")
                for i in range(3)
            ]
            thread_results = await asyncio.gather(*thread_tasks)
            
            for result in thread_results:
                print(f"     Worker {result['worker_id']}: {result['thread']}")
        
        print("   ProcessPoolExecutor:")
        with concurrent.futures.ProcessPoolExecutor(max_workers=2) as process_executor:
            process_tasks = [
                loop.run_in_executor(process_executor, thread_work, i, "process")
                for i in range(2)
            ]
            process_results = await asyncio.gather(*process_tasks)
            
            for result in process_results:
                print(f"     Worker {result['worker_id']}: PID {result['pid']}")
        
        print("   Default executor (ThreadPoolExecutor):")
        default_tasks = [
            loop.run_in_executor(None, thread_work, i, "default")
            for i in range(2)
        ]
        default_results = await asyncio.gather(*default_tasks)
        
        for result in default_results:
            print(f"     Worker {result['worker_id']}: {result['thread']}")
    
    await test_different_executors()

asyncio.run(demonstrate_run_in_executor_basics())
```

### Advanced Executor Patterns

```python
import asyncio
import concurrent.futures
import threading
import time
import functools
from typing import Any, Callable

async def demonstrate_advanced_executor_patterns():
    """Demonstrate advanced patterns with run_in_executor"""
    
    print("=== Advanced Executor Patterns ===")
    
    print("1. Executor context management:")
    
    class ManagedExecutorService:
        """Managed executor service with resource tracking"""
        
        def __init__(self, max_workers=3):
            self.max_workers = max_workers
            self.thread_executor = None
            self.process_executor = None
            self.active_tasks = set()
            self.task_stats = {"submitted": 0, "completed": 0, "failed": 0}
        
        async def __aenter__(self):
            """Async context manager entry"""
            self.thread_executor = concurrent.futures.ThreadPoolExecutor(
                max_workers=self.max_workers
            )
            self.process_executor = concurrent.futures.ProcessPoolExecutor(
                max_workers=min(2, self.max_workers)
            )
            print(f"   Executor service started with {self.max_workers} thread workers")
            return self
        
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            """Async context manager exit"""
            print("   Shutting down executor service...")
            
            # Cancel active tasks
            for task in list(self.active_tasks):
                if not task.done():
                    task.cancel()
            
            # Wait for tasks to complete
            if self.active_tasks:
                await asyncio.gather(*self.active_tasks, return_exceptions=True)
            
            # Shutdown executors
            if self.thread_executor:
                self.thread_executor.shutdown(wait=False)
            if self.process_executor:
                self.process_executor.shutdown(wait=False)
            
            print(f"   Executor service shutdown. Stats: {self.task_stats}")
        
        async def submit_thread_task(self, func, *args, **kwargs):
            """Submit task to thread pool"""
            loop = asyncio.get_event_loop()
            
            self.task_stats["submitted"] += 1
            
            task = loop.run_in_executor(
                self.thread_executor,
                functools.partial(func, **kwargs) if kwargs else func,
                *args
            )
            
            self.active_tasks.add(task)
            
            # Add completion callback
            def on_completion(fut):
                self.active_tasks.discard(fut)
                if fut.exception():
                    self.task_stats["failed"] += 1
                else:
                    self.task_stats["completed"] += 1
            
            task.add_done_callback(on_completion)
            
            return task
        
        async def submit_process_task(self, func, *args, **kwargs):
            """Submit task to process pool"""
            loop = asyncio.get_event_loop()
            
            self.task_stats["submitted"] += 1
            
            task = loop.run_in_executor(
                self.process_executor,
                functools.partial(func, **kwargs) if kwargs else func,
                *args
            )
            
            self.active_tasks.add(task)
            
            # Add completion callback
            def on_completion(fut):
                self.active_tasks.discard(fut)
                if fut.exception():
                    self.task_stats["failed"] += 1
                else:
                    self.task_stats["completed"] += 1
            
            task.add_done_callback(on_completion)
            
            return task
    
    def sample_work_function(work_id, duration=0.1, should_fail=False):
        """Sample work function"""
        if should_fail:
            raise ValueError(f"Work {work_id} failed as requested")
        
        time.sleep(duration)
        return f"Work {work_id} completed"
    
    async def test_managed_executor():
        """Test managed executor service"""
        async with ManagedExecutorService(max_workers=4) as executor:
            # Submit various tasks
            tasks = []
            
            # Thread tasks
            for i in range(5):
                task = await executor.submit_thread_task(
                    sample_work_function, f"thread_{i}", duration=0.2
                )
                tasks.append(task)
            
            # Process tasks
            for i in range(3):
                task = await executor.submit_process_task(
                    sample_work_function, f"process_{i}", duration=0.1
                )
                tasks.append(task)
            
            # Some failing tasks
            for i in range(2):
                task = await executor.submit_thread_task(
                    sample_work_function, f"fail_{i}", should_fail=True
                )
                tasks.append(task)
            
            # Wait for all tasks
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            print(f"   Completed {len(tasks)} tasks:")
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    print(f"     Task {i}: FAILED - {result}")
                else:
                    print(f"     Task {i}: SUCCESS - {result}")
    
    await test_managed_executor()
    
    print("\n2. Rate-limited executor:")
    
    class RateLimitedExecutor:
        """Executor with rate limiting"""
        
        def __init__(self, max_workers=3, rate_limit=2.0):
            self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
            self.rate_limit = rate_limit  # Tasks per second
            self.last_submit_time = 0
        
        async def submit_with_rate_limit(self, func, *args):
            """Submit task with rate limiting"""
            # Calculate delay needed for rate limiting
            now = time.time()
            time_since_last = now - self.last_submit_time
            min_interval = 1.0 / self.rate_limit
            
            if time_since_last < min_interval:
                delay = min_interval - time_since_last
                print(f"   Rate limit: Delaying {delay:.3f}s")
                await asyncio.sleep(delay)
            
            self.last_submit_time = time.time()
            
            loop = asyncio.get_event_loop()
            return loop.run_in_executor(self.executor, func, *args)
        
        def shutdown(self):
            """Shutdown executor"""
            self.executor.shutdown(wait=False)
    
    def rate_limited_work(task_id):
        """Work function for rate limiting test"""
        print(f"   Rate limited task {task_id}: Starting")
        time.sleep(0.1)
        print(f"   Rate limited task {task_id}: Completed")
        return f"Task {task_id} result"
    
    async def test_rate_limited_executor():
        """Test rate limited executor"""
        executor = RateLimitedExecutor(max_workers=3, rate_limit=3.0)  # 3 tasks per second
        
        try:
            # Submit tasks rapidly
            start_time = time.time()
            tasks = []
            
            for i in range(8):
                task = await executor.submit_with_rate_limit(rate_limited_work, i)
                tasks.append(task)
            
            # Wait for all tasks
            results = await asyncio.gather(*tasks)
            
            end_time = time.time()
            print(f"   Rate limited execution: {len(results)} tasks in {end_time - start_time:.2f}s")
            print(f"   Expected minimum time: {len(results) / 3.0:.2f}s")
        
        finally:
            executor.shutdown()
    
    await test_rate_limited_executor()
    
    print("\n3. Adaptive executor sizing:")
    
    class AdaptiveExecutor:
        """Executor that adapts pool size based on load"""
        
        def __init__(self, min_workers=1, max_workers=8):
            self.min_workers = min_workers
            self.max_workers = max_workers
            self.current_workers = min_workers
            self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=min_workers)
            
            self.pending_tasks = 0
            self.completed_tasks = 0
            self.last_resize_time = time.time()
            self.resize_interval = 2.0  # Seconds between resize checks
        
        async def submit_adaptive(self, func, *args):
            """Submit task with adaptive sizing"""
            self._check_resize_needed()
            
            loop = asyncio.get_event_loop()
            self.pending_tasks += 1
            
            task = loop.run_in_executor(self.executor, func, *args)
            
            # Add completion callback
            def on_completion(fut):
                self.pending_tasks -= 1
                self.completed_tasks += 1
            
            task.add_done_callback(on_completion)
            
            return task
        
        def _check_resize_needed(self):
            """Check if executor should be resized"""
            now = time.time()
            
            if now - self.last_resize_time < self.resize_interval:
                return
            
            self.last_resize_time = now
            
            # Simple heuristic: if we have many pending tasks, scale up
            if self.pending_tasks > self.current_workers * 2 and self.current_workers < self.max_workers:
                self._scale_up()
            # If we have few pending tasks, scale down
            elif self.pending_tasks < self.current_workers / 2 and self.current_workers > self.min_workers:
                self._scale_down()
        
        def _scale_up(self):
            """Scale up the executor"""
            new_workers = min(self.current_workers * 2, self.max_workers)
            if new_workers != self.current_workers:
                print(f"   Scaling up: {self.current_workers} -> {new_workers} workers")
                self.executor.shutdown(wait=False)
                self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=new_workers)
                self.current_workers = new_workers
        
        def _scale_down(self):
            """Scale down the executor"""
            new_workers = max(self.current_workers // 2, self.min_workers)
            if new_workers != self.current_workers:
                print(f"   Scaling down: {self.current_workers} -> {new_workers} workers")
                self.executor.shutdown(wait=False)
                self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=new_workers)
                self.current_workers = new_workers
        
        def get_stats(self):
            """Get executor statistics"""
            return {
                "current_workers": self.current_workers,
                "pending_tasks": self.pending_tasks,
                "completed_tasks": self.completed_tasks
            }
        
        def shutdown(self):
            """Shutdown executor"""
            self.executor.shutdown(wait=False)
    
    def adaptive_work(task_id, duration=0.2):
        """Work function for adaptive executor test"""
        time.sleep(duration)
        return f"Adaptive task {task_id} completed"
    
    async def test_adaptive_executor():
        """Test adaptive executor"""
        executor = AdaptiveExecutor(min_workers=1, max_workers=6)
        
        try:
            # Phase 1: Light load
            print("   Phase 1: Light load")
            light_tasks = [
                await executor.submit_adaptive(adaptive_work, i, 0.1)
                for i in range(3)
            ]
            await asyncio.gather(*light_tasks)
            print(f"   Light load stats: {executor.get_stats()}")
            
            await asyncio.sleep(2.5)  # Wait for resize check
            
            # Phase 2: Heavy load
            print("   Phase 2: Heavy load")
            heavy_tasks = [
                await executor.submit_adaptive(adaptive_work, i + 10, 0.3)
                for i in range(12)
            ]
            
            # Check stats during heavy load
            await asyncio.sleep(1.0)
            print(f"   Heavy load stats (during): {executor.get_stats()}")
            
            await asyncio.gather(*heavy_tasks)
            print(f"   Heavy load stats (after): {executor.get_stats()}")
            
            await asyncio.sleep(2.5)  # Wait for potential scale down
            print(f"   Final stats: {executor.get_stats()}")
        
        finally:
            executor.shutdown()
    
    await test_adaptive_executor()

asyncio.run(demonstrate_advanced_executor_patterns())
```

This completes the first part of Chapter 12, covering when to use threads with asyncio and the run_in_executor() method. The examples demonstrate practical patterns for integrating blocking code with async applications.

Would you like me to continue with the remaining sections covering ThreadPoolExecutor integration, ProcessPoolExecutor for CPU-bound work, and calling async from sync code?
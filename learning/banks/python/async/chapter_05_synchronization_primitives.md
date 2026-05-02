# Chapter 5: Synchronization Primitives

## 5.1 Why Synchronization in Single-Threaded Code?

At first glance, synchronization in asyncio might seem unnecessary since asyncio runs on a single thread. However, even though coroutines run cooperatively on one thread, they can still face race conditions when accessing shared state at different await points.

### Understanding the Need for Synchronization

```python
import asyncio
import random

# Demonstrating race conditions in async code
class BankAccount:
    """Bank account with race condition"""
    
    def __init__(self, balance=0):
        self.balance = balance
    
    async def deposit(self, amount):
        """Deposit money (with race condition)"""
        print(f"Depositing {amount}")
        
        # Race condition: another coroutine might modify balance here
        current_balance = self.balance
        await asyncio.sleep(0.01)  # Simulate processing time
        
        # When we resume, balance might have changed!
        self.balance = current_balance + amount
        print(f"Balance after deposit: {self.balance}")
    
    async def withdraw(self, amount):
        """Withdraw money (with race condition)"""
        print(f"Withdrawing {amount}")
        
        current_balance = self.balance
        await asyncio.sleep(0.01)  # Simulate processing time
        
        if current_balance >= amount:
            self.balance = current_balance - amount
            print(f"Balance after withdrawal: {self.balance}")
            return True
        else:
            print("Insufficient funds")
            return False

async def demonstrate_race_condition():
    """Show race condition in action"""
    
    print("=== Race Condition Demonstration ===")
    
    account = BankAccount(100)
    print(f"Initial balance: {account.balance}")
    
    # Simulate concurrent operations
    tasks = [
        account.deposit(50),
        account.withdraw(30),
        account.deposit(25),
        account.withdraw(40),
        account.deposit(20)
    ]
    
    await asyncio.gather(*tasks)
    
    print(f"Final balance: {account.balance}")
    print("Expected balance: 125 (100 + 50 - 30 + 25 - 40 + 20)")
    print(f"Actual balance: {account.balance}")
    print(f"Race condition detected: {account.balance != 125}")

asyncio.run(demonstrate_race_condition())
```

### When Synchronization is Needed

```python
import asyncio

def when_synchronization_needed():
    """Examples of when synchronization is required"""
    
    print("=== When Synchronization is Needed ===")
    
    # Scenario 1: Shared counter
    class SharedCounter:
        def __init__(self):
            self.value = 0
        
        async def increment(self):
            # Race condition between read and write
            temp = self.value
            await asyncio.sleep(0.001)  # Yield point
            self.value = temp + 1
    
    # Scenario 2: Resource pool
    class ResourcePool:
        def __init__(self, max_resources=3):
            self.available = max_resources
            self.in_use = set()
        
        async def acquire_resource(self, user_id):
            if self.available > 0:
                await asyncio.sleep(0.01)  # Simulate allocation
                # Another coroutine might have taken the resource!
                self.available -= 1
                self.in_use.add(user_id)
                return f"resource_{user_id}"
            return None
    
    # Scenario 3: State machine
    class StateMachine:
        def __init__(self):
            self.state = "idle"
            self.data = {}
        
        async def transition_to_processing(self, task_id):
            if self.state == "idle":
                self.state = "processing"
                await asyncio.sleep(0.1)  # Async work
                # State might have been changed by another coroutine
                self.data[task_id] = "processed"
                self.state = "idle"
    
    print("Common scenarios requiring synchronization:")
    print("1. Shared counters or accumulators")
    print("2. Resource pools or connection management")
    print("3. State machines with async transitions")
    print("4. Producer-consumer patterns")
    print("5. Caching mechanisms")
    print("6. Rate limiting or throttling")

when_synchronization_needed()
```

### Async Context vs Threading Context

```python
import asyncio
import threading
import time

def compare_async_vs_threading():
    """Compare synchronization needs in async vs threading"""
    
    print("=== Async vs Threading Context ===")
    
    # Threading example (true parallelism)
    class ThreadingCounter:
        def __init__(self):
            self.value = 0
            self.lock = threading.Lock()
        
        def increment_unsafe(self):
            """Unsafe increment (race condition)"""
            temp = self.value
            time.sleep(0.001)  # Simulate work
            self.value = temp + 1
        
        def increment_safe(self):
            """Safe increment with lock"""
            with self.lock:
                temp = self.value
                time.sleep(0.001)  # Simulate work
                self.value = temp + 1
    
    # Async example (cooperative concurrency)
    class AsyncCounter:
        def __init__(self):
            self.value = 0
            self.lock = asyncio.Lock()
        
        async def increment_unsafe(self):
            """Unsafe increment (race condition)"""
            temp = self.value
            await asyncio.sleep(0.001)  # Yield point
            self.value = temp + 1
        
        async def increment_safe(self):
            """Safe increment with async lock"""
            async with self.lock:
                temp = self.value
                await asyncio.sleep(0.001)  # Yield point
                self.value = temp + 1
    
    # Demonstrate threading race condition
    def test_threading():
        counter = ThreadingCounter()
        threads = []
        
        for _ in range(10):
            thread = threading.Thread(target=counter.increment_unsafe)
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        print(f"Threading unsafe result: {counter.value} (expected: 10)")
        
        # Test with lock
        safe_counter = ThreadingCounter()
        threads = []
        
        for _ in range(10):
            thread = threading.Thread(target=safe_counter.increment_safe)
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        print(f"Threading safe result: {safe_counter.value} (expected: 10)")
    
    # Demonstrate async race condition
    async def test_async():
        counter = AsyncCounter()
        
        # Test unsafe version
        tasks = [counter.increment_unsafe() for _ in range(10)]
        await asyncio.gather(*tasks)
        
        print(f"Async unsafe result: {counter.value} (expected: 10)")
        
        # Test with lock
        safe_counter = AsyncCounter()
        tasks = [safe_counter.increment_safe() for _ in range(10)]
        await asyncio.gather(*tasks)
        
        print(f"Async safe result: {safe_counter.value} (expected: 10)")
    
    print("1. Threading context (true parallelism):")
    test_threading()
    
    print("\n2. Async context (cooperative concurrency):")
    asyncio.run(test_async())
    
    print("\nKey differences:")
    print("- Threading: Preemptive multitasking, race conditions due to interruption")
    print("- Async: Cooperative multitasking, race conditions due to yield points")
    print("- Both need synchronization for shared state!")

compare_async_vs_threading()
```

## 5.2 Locks (asyncio.Lock)

Locks are the most fundamental synchronization primitive. They ensure that only one coroutine can access a critical section at a time.

### Basic Lock Usage

```python
import asyncio
import time

async def demonstrate_basic_locks():
    """Demonstrate basic asyncio.Lock usage"""
    
    print("=== Basic Lock Usage ===")
    
    # Shared resource
    shared_resource = {"counter": 0, "log": []}
    lock = asyncio.Lock()
    
    async def worker(worker_id, iterations):
        """Worker that modifies shared resource"""
        
        for i in range(iterations):
            # Critical section - needs synchronization
            async with lock:
                # Only one worker can execute this at a time
                current = shared_resource["counter"]
                shared_resource["log"].append(f"Worker {worker_id} read: {current}")
                
                # Simulate some work
                await asyncio.sleep(0.01)
                
                shared_resource["counter"] = current + 1
                shared_resource["log"].append(f"Worker {worker_id} wrote: {shared_resource['counter']}")
    
    print("1. Running workers with lock protection:")
    
    start_time = time.time()
    
    # Create multiple workers
    tasks = [
        worker(1, 3),
        worker(2, 3),
        worker(3, 3)
    ]
    
    await asyncio.gather(*tasks)
    
    end_time = time.time()
    
    print(f"   Final counter: {shared_resource['counter']}")
    print(f"   Expected: 9, Actual: {shared_resource['counter']}")
    print(f"   Execution time: {end_time - start_time:.3f}s")
    
    # Show the execution log
    print("\n2. Execution log (showing serialization):")
    for entry in shared_resource["log"][-10:]:  # Show last 10 entries
        print(f"   {entry}")

asyncio.run(demonstrate_basic_locks())
```

### Lock Acquisition Patterns

```python
import asyncio

async def demonstrate_lock_patterns():
    """Show different patterns for acquiring locks"""
    
    print("=== Lock Acquisition Patterns ===")
    
    lock = asyncio.Lock()
    
    # Pattern 1: Context manager (recommended)
    async def pattern_context_manager():
        """Using async with (recommended)"""
        print("1. Context manager pattern:")
        
        async with lock:
            print("   Inside critical section (context manager)")
            await asyncio.sleep(0.1)
            print("   Still in critical section")
        
        print("   Lock automatically released")
    
    # Pattern 2: Manual acquire/release
    async def pattern_manual():
        """Manual acquire and release"""
        print("\n2. Manual acquire/release pattern:")
        
        await lock.acquire()
        try:
            print("   Inside critical section (manual)")
            await asyncio.sleep(0.1)
            print("   Still in critical section")
        finally:
            lock.release()
            print("   Lock manually released")
    
    # Pattern 3: Timeout with try_lock (if available)
    async def pattern_timeout():
        """Lock with timeout"""
        print("\n3. Lock with timeout:")
        
        # This pattern requires implementing timeout manually
        try:
            # Wait for lock with timeout
            await asyncio.wait_for(lock.acquire(), timeout=0.5)
            
            try:
                print("   Acquired lock within timeout")
                await asyncio.sleep(0.1)
            finally:
                lock.release()
                
        except asyncio.TimeoutError:
            print("   Failed to acquire lock within timeout")
    
    # Pattern 4: Non-blocking attempt (custom implementation)
    async def pattern_try_lock():
        """Try to acquire lock without blocking"""
        print("\n4. Non-blocking lock attempt:")
        
        class TryLock:
            def __init__(self, lock):
                self.lock = lock
                self.acquired = False
            
            async def __aenter__(self):
                # Try to acquire without blocking
                if self.lock.locked():
                    print("   Lock is busy, not waiting")
                    return False
                
                await self.lock.acquire()
                self.acquired = True
                print("   Lock acquired (non-blocking)")
                return True
            
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                if self.acquired:
                    self.lock.release()
                    print("   Lock released")
        
        async with TryLock(lock) as acquired:
            if acquired:
                print("   Doing work with lock")
                await asyncio.sleep(0.05)
            else:
                print("   Doing alternative work without lock")
    
    # Run patterns sequentially
    await pattern_context_manager()
    await pattern_manual()
    await pattern_timeout()
    await pattern_try_lock()

asyncio.run(demonstrate_lock_patterns())
```

### Advanced Lock Usage

```python
import asyncio
from collections import defaultdict
import time

class AdvancedLockManager:
    """Advanced lock management with features"""
    
    def __init__(self):
        self.locks = defaultdict(asyncio.Lock)
        self.lock_stats = defaultdict(lambda: {
            'acquisitions': 0,
            'total_wait_time': 0,
            'total_hold_time': 0,
            'current_holder': None
        })
    
    async def acquire_named_lock(self, lock_name, holder_name=None):
        """Acquire a named lock with statistics"""
        lock = self.locks[lock_name]
        stats = self.lock_stats[lock_name]
        
        wait_start = time.time()
        await lock.acquire()
        wait_end = time.time()
        
        # Update statistics
        stats['acquisitions'] += 1
        stats['total_wait_time'] += wait_end - wait_start
        stats['current_holder'] = holder_name
        
        return LockContext(lock, lock_name, self, time.time())
    
    def release_lock_stats(self, lock_name, hold_time):
        """Update statistics when lock is released"""
        stats = self.lock_stats[lock_name]
        stats['total_hold_time'] += hold_time
        stats['current_holder'] = None
    
    def get_stats(self, lock_name):
        """Get lock statistics"""
        return dict(self.lock_stats[lock_name])
    
    def get_all_stats(self):
        """Get all lock statistics"""
        return {name: dict(stats) for name, stats in self.lock_stats.items()}

class LockContext:
    """Context manager for advanced lock with statistics"""
    
    def __init__(self, lock, lock_name, manager, acquire_time):
        self.lock = lock
        self.lock_name = lock_name
        self.manager = manager
        self.acquire_time = acquire_time
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        hold_time = time.time() - self.acquire_time
        self.manager.release_lock_stats(self.lock_name, hold_time)
        self.lock.release()

async def demonstrate_advanced_locks():
    """Demonstrate advanced lock usage"""
    
    print("=== Advanced Lock Usage ===")
    
    manager = AdvancedLockManager()
    
    # Simulate different types of work
    async def database_work(worker_id, duration):
        """Simulate database work requiring lock"""
        async with await manager.acquire_named_lock("database", f"Worker-{worker_id}"):
            print(f"   Worker {worker_id}: Accessing database")
            await asyncio.sleep(duration)
            print(f"   Worker {worker_id}: Database work complete")
    
    async def file_work(worker_id, duration):
        """Simulate file work requiring lock"""
        async with await manager.acquire_named_lock("file_system", f"Worker-{worker_id}"):
            print(f"   Worker {worker_id}: Accessing file system")
            await asyncio.sleep(duration)
            print(f"   Worker {worker_id}: File work complete")
    
    # Create workload
    tasks = []
    
    # Database workers
    for i in range(3):
        tasks.append(database_work(i + 1, 0.2))
    
    # File system workers
    for i in range(2):
        tasks.append(file_work(i + 1, 0.3))
    
    # Mixed workers
    for i in range(2):
        if i % 2 == 0:
            tasks.append(database_work(f"M{i+1}", 0.1))
        else:
            tasks.append(file_work(f"M{i+1}", 0.15))
    
    print("1. Running concurrent workers with named locks:")
    start_time = time.time()
    
    await asyncio.gather(*tasks)
    
    end_time = time.time()
    print(f"   Total execution time: {end_time - start_time:.3f}s")
    
    # Show statistics
    print("\n2. Lock statistics:")
    all_stats = manager.get_all_stats()
    
    for lock_name, stats in all_stats.items():
        print(f"   {lock_name}:")
        print(f"     Acquisitions: {stats['acquisitions']}")
        print(f"     Avg wait time: {stats['total_wait_time']/stats['acquisitions']:.3f}s")
        print(f"     Avg hold time: {stats['total_hold_time']/stats['acquisitions']:.3f}s")
        print(f"     Total contention: {stats['total_wait_time']:.3f}s")

asyncio.run(demonstrate_advanced_locks())
```

### Lock Deadlock Prevention

```python
import asyncio

async def demonstrate_deadlock_prevention():
    """Show deadlock scenarios and prevention"""
    
    print("=== Deadlock Prevention ===")
    
    lock_a = asyncio.Lock()
    lock_b = asyncio.Lock()
    
    # DEADLOCK SCENARIO - DON'T DO THIS
    async def deadlock_worker_1():
        """Worker that can cause deadlock"""
        print("   Worker 1: Acquiring lock A")
        async with lock_a:
            print("   Worker 1: Got lock A, waiting...")
            await asyncio.sleep(0.1)
            
            print("   Worker 1: Trying to acquire lock B")
            async with lock_b:
                print("   Worker 1: Got both locks")
    
    async def deadlock_worker_2():
        """Worker that can cause deadlock"""
        print("   Worker 2: Acquiring lock B")
        async with lock_b:
            print("   Worker 2: Got lock B, waiting...")
            await asyncio.sleep(0.1)
            
            print("   Worker 2: Trying to acquire lock A")
            async with lock_a:
                print("   Worker 2: Got both locks")
    
    # SOLUTION 1: Ordered lock acquisition
    async def ordered_worker_1():
        """Worker using ordered lock acquisition"""
        print("   Ordered Worker 1: Acquiring locks in order (A then B)")
        async with lock_a:
            async with lock_b:
                print("   Ordered Worker 1: Got both locks")
                await asyncio.sleep(0.1)
    
    async def ordered_worker_2():
        """Worker using ordered lock acquisition"""
        print("   Ordered Worker 2: Acquiring locks in order (A then B)")
        async with lock_a:
            async with lock_b:
                print("   Ordered Worker 2: Got both locks")
                await asyncio.sleep(0.1)
    
    # SOLUTION 2: Timeout-based acquisition
    async def timeout_worker(worker_id):
        """Worker using timeout to avoid deadlock"""
        try:
            print(f"   Timeout Worker {worker_id}: Trying lock A")
            async with asyncio.timeout(0.5):
                async with lock_a:
                    print(f"   Timeout Worker {worker_id}: Got lock A")
                    
                    try:
                        async with asyncio.timeout(0.2):
                            async with lock_b:
                                print(f"   Timeout Worker {worker_id}: Got both locks")
                                await asyncio.sleep(0.1)
                    
                    except asyncio.TimeoutError:
                        print(f"   Timeout Worker {worker_id}: Couldn't get lock B, backing off")
        
        except asyncio.TimeoutError:
            print(f"   Timeout Worker {worker_id}: Couldn't get lock A")
    
    # SOLUTION 3: Context manager for multiple locks
    class OrderedLocks:
        def __init__(self, *locks):
            self.locks = sorted(locks, key=lambda x: id(x))  # Sort by object id
        
        async def __aenter__(self):
            for lock in self.locks:
                await lock.acquire()
            return self
        
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            # Release in reverse order
            for lock in reversed(self.locks):
                lock.release()
    
    async def safe_worker(worker_id):
        """Worker using ordered locks context manager"""
        print(f"   Safe Worker {worker_id}: Acquiring ordered locks")
        async with OrderedLocks(lock_a, lock_b):
            print(f"   Safe Worker {worker_id}: Got both locks safely")
            await asyncio.sleep(0.1)
    
    # Demonstrate solutions (skipping deadlock demo for safety)
    print("1. Ordered lock acquisition:")
    await asyncio.gather(ordered_worker_1(), ordered_worker_2())
    
    print("\n2. Timeout-based acquisition:")
    await asyncio.gather(timeout_worker(1), timeout_worker(2))
    
    print("\n3. Context manager for multiple locks:")
    await asyncio.gather(safe_worker(1), safe_worker(2))
    
    print("\nDeadlock prevention strategies:")
    print("- Always acquire locks in the same order")
    print("- Use timeouts to avoid indefinite blocking")
    print("- Create context managers for multiple locks")
    print("- Minimize lock scope and holding time")

asyncio.run(demonstrate_deadlock_prevention())
```

## 5.3 Events (asyncio.Event)

Events are synchronization primitives that allow coroutines to wait for something to happen. They're perfect for coordinating between producer and consumer coroutines.

### Basic Event Usage

```python
import asyncio
import random

async def demonstrate_basic_events():
    """Demonstrate basic asyncio.Event usage"""
    
    print("=== Basic Event Usage ===")
    
    # Create an event
    event = asyncio.Event()
    
    print(f"Initial event state: {event.is_set()}")
    
    async def waiter(waiter_id):
        """Coroutine that waits for event"""
        print(f"   Waiter {waiter_id}: Waiting for event...")
        await event.wait()
        print(f"   Waiter {waiter_id}: Event received!")
        return f"Waiter {waiter_id} done"
    
    async def setter():
        """Coroutine that sets the event"""
        print("   Setter: Working...")
        await asyncio.sleep(1.0)  # Simulate work
        print("   Setter: Setting event")
        event.set()
        return "Setter done"
    
    print("1. Multiple waiters, one setter:")
    
    # Create multiple waiters
    waiters = [waiter(i) for i in range(3)]
    
    # Create setter
    setter_task = asyncio.create_task(setter())
    
    # Wait for all to complete
    results = await asyncio.gather(*waiters, setter_task)
    
    print(f"   Results: {results}")
    print(f"   Final event state: {event.is_set()}")
    
    # Clear event for next demo
    event.clear()
    print(f"   Event cleared: {event.is_set()}")

asyncio.run(demonstrate_basic_events())
```

### Event-Based Coordination Patterns

```python
import asyncio
import time

class EventCoordinator:
    """Coordinator using events for complex workflows"""
    
    def __init__(self):
        self.events = {}
        self.results = {}
    
    def create_event(self, name):
        """Create a named event"""
        self.events[name] = asyncio.Event()
        return self.events[name]
    
    def set_event(self, name, result=None):
        """Set an event and store result"""
        if name in self.events:
            self.results[name] = result
            self.events[name].set()
    
    async def wait_for_event(self, name, timeout=None):
        """Wait for named event with optional timeout"""
        if name not in self.events:
            raise ValueError(f"Event '{name}' not found")
        
        if timeout:
            await asyncio.wait_for(self.events[name].wait(), timeout=timeout)
        else:
            await self.events[name].wait()
        
        return self.results.get(name)

async def demonstrate_event_coordination():
    """Demonstrate event-based coordination patterns"""
    
    print("=== Event-Based Coordination ===")
    
    coordinator = EventCoordinator()
    
    # Pattern 1: Sequential workflow coordination
    print("1. Sequential workflow coordination:")
    
    async def data_fetcher():
        """Fetch initial data"""
        print("   Fetcher: Fetching data...")
        await asyncio.sleep(0.5)
        data = {"users": 100, "orders": 250}
        
        coordinator.set_event("data_ready", data)
        print("   Fetcher: Data ready event set")
        return data
    
    async def data_processor():
        """Process data after it's fetched"""
        print("   Processor: Waiting for data...")
        data = await coordinator.wait_for_event("data_ready")
        
        print(f"   Processor: Processing {data}")
        await asyncio.sleep(0.3)
        
        processed = {k: v * 2 for k, v in data.items()}
        coordinator.set_event("processing_done", processed)
        print("   Processor: Processing complete event set")
        return processed
    
    async def report_generator():
        """Generate report after processing"""
        print("   Reporter: Waiting for processing...")
        processed_data = await coordinator.wait_for_event("processing_done")
        
        print(f"   Reporter: Generating report from {processed_data}")
        await asyncio.sleep(0.2)
        
        report = f"Report: Users={processed_data['users']}, Orders={processed_data['orders']}"
        coordinator.set_event("report_ready", report)
        print("   Reporter: Report ready event set")
        return report
    
    # Create events
    coordinator.create_event("data_ready")
    coordinator.create_event("processing_done")
    coordinator.create_event("report_ready")
    
    # Start all components
    tasks = [
        asyncio.create_task(data_fetcher()),
        asyncio.create_task(data_processor()),
        asyncio.create_task(report_generator())
    ]
    
    results = await asyncio.gather(*tasks)
    print(f"   Workflow results: {results}")

asyncio.run(demonstrate_event_coordination())
```

### Producer-Consumer with Events

```python
import asyncio
import random
from asyncio import Queue

async def demonstrate_producer_consumer_events():
    """Demonstrate producer-consumer pattern with events"""
    
    print("=== Producer-Consumer with Events ===")
    
    # Shared state
    queue = Queue(maxsize=5)
    items_produced = 0
    items_consumed = 0
    
    # Events for coordination
    production_started = asyncio.Event()
    production_finished = asyncio.Event()
    consumption_finished = asyncio.Event()
    
    async def producer(producer_id, item_count):
        """Producer that creates items"""
        nonlocal items_produced
        
        print(f"   Producer {producer_id}: Starting production")
        production_started.set()
        
        for i in range(item_count):
            item = f"item_{producer_id}_{i}"
            
            # Wait for space in queue
            await queue.put(item)
            items_produced += 1
            
            print(f"   Producer {producer_id}: Produced {item} (total: {items_produced})")
            await asyncio.sleep(random.uniform(0.1, 0.3))
        
        print(f"   Producer {producer_id}: Finished")
        
        # Check if all producers are done
        if items_produced >= 10:  # Total items we expect
            production_finished.set()
    
    async def consumer(consumer_id):
        """Consumer that processes items"""
        nonlocal items_consumed
        
        print(f"   Consumer {consumer_id}: Waiting for production to start")
        await production_started.wait()
        
        print(f"   Consumer {consumer_id}: Starting consumption")
        
        while True:
            try:
                # Wait for item or production to finish
                item_task = asyncio.create_task(queue.get())
                finish_task = asyncio.create_task(production_finished.wait())
                
                done, pending = await asyncio.wait(
                    [item_task, finish_task],
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                # Cancel pending tasks
                for task in pending:
                    task.cancel()
                
                if item_task in done:
                    item = item_task.result()
                    items_consumed += 1
                    
                    print(f"   Consumer {consumer_id}: Consumed {item} (total: {items_consumed})")
                    
                    # Simulate processing
                    await asyncio.sleep(random.uniform(0.05, 0.2))
                    
                    queue.task_done()
                
                if finish_task in done and queue.empty():
                    break
                
            except asyncio.CancelledError:
                break
        
        print(f"   Consumer {consumer_id}: Finished")
        
        # Signal consumption finished
        if items_consumed >= items_produced:
            consumption_finished.set()
    
    async def monitor():
        """Monitor the producer-consumer process"""
        print("   Monitor: Started")
        
        # Wait for production to start
        await production_started.wait()
        print("   Monitor: Production started")
        
        # Wait for production to finish
        await production_finished.wait()
        print(f"   Monitor: Production finished ({items_produced} items)")
        
        # Wait for consumption to finish
        await consumption_finished.wait()
        print(f"   Monitor: Consumption finished ({items_consumed} items)")
        
        return "Monitor complete"
    
    # Start producers, consumers, and monitor
    tasks = [
        asyncio.create_task(producer(1, 5)),
        asyncio.create_task(producer(2, 5)),
        asyncio.create_task(consumer(1)),
        asyncio.create_task(consumer(2)),
        asyncio.create_task(monitor())
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    print(f"\n   Final state:")
    print(f"   Items produced: {items_produced}")
    print(f"   Items consumed: {items_consumed}")
    print(f"   Queue size: {queue.qsize()}")

asyncio.run(demonstrate_producer_consumer_events())
```

### Event-Based State Machine

```python
import asyncio
from enum import Enum
import time

class State(Enum):
    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"

class EventDrivenStateMachine:
    """State machine using events for transitions"""
    
    def __init__(self):
        self.state = State.IDLE
        self.events = {}
        self.transitions = {
            State.IDLE: [State.STARTING],
            State.STARTING: [State.RUNNING, State.ERROR],
            State.RUNNING: [State.STOPPING, State.ERROR],
            State.STOPPING: [State.IDLE, State.ERROR],
            State.ERROR: [State.IDLE]
        }
        
        # Create events for each state
        for state in State:
            self.events[state] = asyncio.Event()
        
        # Set initial state
        self.events[State.IDLE].set()
    
    async def transition_to(self, new_state):
        """Transition to a new state"""
        if new_state not in self.transitions[self.state]:
            raise ValueError(f"Invalid transition from {self.state} to {new_state}")
        
        print(f"   State machine: {self.state.value} -> {new_state.value}")
        
        # Clear old state event
        self.events[self.state].clear()
        
        # Update state
        old_state = self.state
        self.state = new_state
        
        # Set new state event
        self.events[self.state].set()
        
        return old_state, new_state
    
    async def wait_for_state(self, state, timeout=None):
        """Wait for machine to reach specific state"""
        if timeout:
            await asyncio.wait_for(self.events[state].wait(), timeout=timeout)
        else:
            await self.events[state].wait()
    
    def is_in_state(self, state):
        """Check if machine is in specific state"""
        return self.state == state

async def demonstrate_event_state_machine():
    """Demonstrate event-driven state machine"""
    
    print("=== Event-Driven State Machine ===")
    
    machine = EventDrivenStateMachine()
    
    async def controller():
        """Controller that drives state transitions"""
        print("   Controller: Starting state machine")
        
        try:
            # Start the machine
            await machine.transition_to(State.STARTING)
            await asyncio.sleep(0.5)  # Simulate startup time
            
            # Transition to running
            await machine.transition_to(State.RUNNING)
            await asyncio.sleep(1.0)  # Simulate running time
            
            # Stop the machine
            await machine.transition_to(State.STOPPING)
            await asyncio.sleep(0.3)  # Simulate shutdown time
            
            # Back to idle
            await machine.transition_to(State.IDLE)
            
        except Exception as e:
            print(f"   Controller: Error occurred: {e}")
            await machine.transition_to(State.ERROR)
    
    async def monitor():
        """Monitor that watches for specific states"""
        print("   Monitor: Watching for RUNNING state")
        
        # Wait for running state
        await machine.wait_for_state(State.RUNNING)
        start_time = time.time()
        print("   Monitor: Machine is now RUNNING")
        
        # Wait for machine to stop running
        while machine.is_in_state(State.RUNNING):
            await asyncio.sleep(0.1)
        
        end_time = time.time()
        print(f"   Monitor: Machine ran for {end_time - start_time:.2f}s")
    
    async def safety_monitor():
        """Safety monitor that watches for errors"""
        print("   Safety Monitor: Watching for errors")
        
        try:
            # Wait for error state with timeout
            await machine.wait_for_state(State.ERROR, timeout=5.0)
            print("   Safety Monitor: ERROR detected!")
        except asyncio.TimeoutError:
            print("   Safety Monitor: No errors detected")
    
    async def logger():
        """Logger that tracks all state changes"""
        current_state = machine.state
        state_times = {current_state: time.time()}
        
        print(f"   Logger: Initial state {current_state.value}")
        
        while not machine.is_in_state(State.IDLE) or len(state_times) == 1:
            await asyncio.sleep(0.05)  # Check frequently
            
            if machine.state != current_state:
                now = time.time()
                duration = now - state_times[current_state]
                
                print(f"   Logger: {current_state.value} lasted {duration:.2f}s")
                
                current_state = machine.state
                state_times[current_state] = now
        
        # Log final state duration
        final_duration = time.time() - state_times[current_state]
        print(f"   Logger: {current_state.value} lasted {final_duration:.2f}s")
    
    # Run all components
    tasks = [
        asyncio.create_task(controller()),
        asyncio.create_task(monitor()),
        asyncio.create_task(safety_monitor()),
        asyncio.create_task(logger())
    ]
    
    await asyncio.gather(*tasks, return_exceptions=True)
    
    print(f"   Final state: {machine.state.value}")

asyncio.run(demonstrate_event_state_machine())
```

This completes the first part of Chapter 5, covering the fundamentals of synchronization in asyncio and detailed coverage of Locks and Events. The chapter shows why synchronization is needed even in single-threaded async code and provides practical examples of using these primitives effectively.

Would you like me to continue with the remaining sections (5.4 Conditions, 5.5 Semaphores, 5.6 Barriers, and 5.7 Best Practices)?
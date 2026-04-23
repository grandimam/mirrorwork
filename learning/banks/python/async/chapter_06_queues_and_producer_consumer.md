# Chapter 6: Queues and Producer-Consumer Patterns

## 6.1 asyncio.Queue Fundamentals

Queues are essential data structures for coordinating work between coroutines. They provide thread-safe (and coroutine-safe) communication channels that enable producer-consumer patterns and help manage backpressure in async systems.

### Understanding asyncio.Queue

```python
import asyncio
import time
import random

async def demonstrate_basic_queue():
    """Demonstrate basic asyncio.Queue operations"""
    
    print("=== Basic Queue Operations ===")
    
    # Create a queue with limited capacity
    queue = asyncio.Queue(maxsize=3)
    
    print(f"1. Queue created with maxsize=3")
    print(f"   Empty: {queue.empty()}")
    print(f"   Size: {queue.qsize()}")
    print(f"   Full: {queue.full()}")
    
    # Basic put and get operations
    print("\n2. Basic put/get operations:")
    
    # Put some items
    await queue.put("item1")
    await queue.put("item2")
    print(f"   After putting 2 items - Size: {queue.qsize()}")
    
    # Get items
    item1 = await queue.get()
    item2 = await queue.get()
    print(f"   Got items: {item1}, {item2}")
    print(f"   After getting items - Size: {queue.qsize()}")
    
    # Non-blocking operations
    print("\n3. Non-blocking operations:")
    
    # Try to get from empty queue (non-blocking)
    try:
        item = queue.get_nowait()
    except asyncio.QueueEmpty:
        print("   Queue is empty (QueueEmpty exception)")
    
    # Put items to capacity
    queue.put_nowait("item3")
    queue.put_nowait("item4")
    queue.put_nowait("item5")
    print(f"   Filled queue to capacity - Size: {queue.qsize()}")
    
    # Try to put when full (non-blocking)
    try:
        queue.put_nowait("item6")
    except asyncio.QueueFull:
        print("   Queue is full (QueueFull exception)")
    
    # Clear queue
    while not queue.empty():
        queue.get_nowait()
    
    print(f"   Cleared queue - Size: {queue.qsize()}")

asyncio.run(demonstrate_basic_queue())
```

### Queue Blocking Behavior

```python
import asyncio
import time

async def demonstrate_queue_blocking():
    """Demonstrate blocking behavior of queues"""
    
    print("=== Queue Blocking Behavior ===")
    
    queue = asyncio.Queue(maxsize=2)
    
    async def producer(name, items):
        """Producer that puts items in queue"""
        for i, item in enumerate(items):
            start_time = time.time()
            print(f"   {name}: Putting {item} (queue size: {queue.qsize()})")
            
            await queue.put(item)  # This may block if queue is full
            
            end_time = time.time()
            wait_time = end_time - start_time
            
            if wait_time > 0.01:  # Significant wait time
                print(f"   {name}: Waited {wait_time:.3f}s for queue space")
            
            # Small delay between items
            await asyncio.sleep(0.1)
        
        print(f"   {name}: Finished producing")
    
    async def consumer(name, delay):
        """Consumer that gets items from queue"""
        consumed_items = []
        
        while len(consumed_items) < 6:  # Expect 6 total items
            start_time = time.time()
            print(f"   {name}: Getting item (queue size: {queue.qsize()})")
            
            item = await queue.get()  # This may block if queue is empty
            
            end_time = time.time()
            wait_time = end_time - start_time
            
            consumed_items.append(item)
            print(f"   {name}: Got {item} (waited {wait_time:.3f}s)")
            
            # Simulate processing time
            await asyncio.sleep(delay)
            
            # Mark task as done
            queue.task_done()
        
        print(f"   {name}: Finished consuming {len(consumed_items)} items")
        return consumed_items
    
    print("1. Demonstrating producer blocking (queue fills up):")
    
    # Start fast producer and slow consumer
    producer_task = asyncio.create_task(
        producer("FastProducer", ["item1", "item2", "item3", "item4"])
    )
    
    # Slow consumer that causes producer to block
    consumer_task = asyncio.create_task(
        consumer("SlowConsumer", 0.3)  # Takes 0.3s per item
    )
    
    await asyncio.gather(producer_task, consumer_task)
    
    print("\n2. Demonstrating consumer blocking (queue empties):")
    
    # Clear any remaining items
    while not queue.empty():
        queue.get_nowait()
    
    # Start slow producer and fast consumer
    producer_task = asyncio.create_task(
        producer("SlowProducer", ["item5", "item6"])
    )
    
    consumer_task = asyncio.create_task(
        consumer("FastConsumer", 0.05)  # Takes 0.05s per item
    )
    
    await asyncio.gather(producer_task, consumer_task)

asyncio.run(demonstrate_queue_blocking())
```

### Queue with task_done() and join()

```python
import asyncio
import random

async def demonstrate_queue_task_done():
    """Demonstrate queue.task_done() and queue.join()"""
    
    print("=== Queue task_done() and join() ===")
    
    queue = asyncio.Queue()
    
    async def producer(num_items):
        """Producer that adds work items"""
        print(f"   Producer: Adding {num_items} work items")
        
        for i in range(num_items):
            work_item = {
                'id': i,
                'data': f"work_data_{i}",
                'priority': random.randint(1, 5)
            }
            
            await queue.put(work_item)
            print(f"   Producer: Added work item {i}")
        
        print("   Producer: All items queued")
    
    async def worker(worker_id):
        """Worker that processes items"""
        processed_count = 0
        
        while True:
            try:
                # Get work item with timeout
                work_item = await asyncio.wait_for(queue.get(), timeout=1.0)
                
                print(f"   Worker {worker_id}: Processing item {work_item['id']}")
                
                # Simulate work based on priority
                work_time = work_item['priority'] * 0.1
                await asyncio.sleep(work_time)
                
                processed_count += 1
                print(f"   Worker {worker_id}: Completed item {work_item['id']} "
                      f"(processed {processed_count} total)")
                
                # IMPORTANT: Mark task as done
                queue.task_done()
                
            except asyncio.TimeoutError:
                print(f"   Worker {worker_id}: No more work, stopping")
                break
        
        return processed_count
    
    async def coordinator():
        """Coordinator that manages the workflow"""
        print("   Coordinator: Starting workflow")
        
        # Start producer
        producer_task = asyncio.create_task(producer(5))
        
        # Start workers
        workers = [
            asyncio.create_task(worker(i))
            for i in range(3)
        ]
        
        # Wait for all items to be queued
        await producer_task
        print("   Coordinator: All items queued, waiting for completion")
        
        # Wait for all work to be done
        await queue.join()  # Blocks until all tasks are done
        print("   Coordinator: All work completed!")
        
        # Cancel workers (they're waiting for more work)
        for worker_task in workers:
            worker_task.cancel()
        
        # Collect results
        results = await asyncio.gather(*workers, return_exceptions=True)
        
        total_processed = sum(r for r in results if isinstance(r, int))
        print(f"   Coordinator: Total items processed: {total_processed}")
        
        return results
    
    results = await coordinator()
    print(f"\nWorkflow complete. Results: {results}")

asyncio.run(demonstrate_queue_task_done())
```

### Queue Error Handling and Timeouts

```python
import asyncio
import random

async def demonstrate_queue_error_handling():
    """Demonstrate error handling with queues"""
    
    print("=== Queue Error Handling ===")
    
    queue = asyncio.Queue(maxsize=3)
    
    async def reliable_producer(name, items):
        """Producer with error handling"""
        for item in items:
            max_retries = 3
            retry_count = 0
            
            while retry_count < max_retries:
                try:
                    # Try to put with timeout
                    await asyncio.wait_for(queue.put(item), timeout=2.0)
                    print(f"   {name}: Successfully queued {item}")
                    break
                
                except asyncio.TimeoutError:
                    retry_count += 1
                    print(f"   {name}: Timeout queuing {item}, retry {retry_count}/{max_retries}")
                    
                    if retry_count >= max_retries:
                        print(f"   {name}: Failed to queue {item} after {max_retries} retries")
                        return False
                    
                    await asyncio.sleep(0.5)  # Wait before retry
        
        return True
    
    async def unreliable_consumer(name):
        """Consumer that sometimes fails"""
        processed_items = []
        
        while len(processed_items) < 6:
            try:
                # Get item with timeout
                item = await asyncio.wait_for(queue.get(), timeout=3.0)
                
                # Simulate processing that might fail
                if random.random() < 0.3:  # 30% failure rate
                    print(f"   {name}: Processing {item} failed!")
                    
                    # Put item back in queue for retry
                    await queue.put(f"RETRY_{item}")
                    queue.task_done()  # Still mark original as done
                    continue
                
                # Successful processing
                await asyncio.sleep(0.2)
                processed_items.append(item)
                print(f"   {name}: Successfully processed {item}")
                
                queue.task_done()
                
            except asyncio.TimeoutError:
                print(f"   {name}: Timeout waiting for item")
                break
            
            except Exception as e:
                print(f"   {name}: Unexpected error: {e}")
                queue.task_done()  # Mark as done to avoid hanging
        
        return processed_items
    
    async def queue_monitor():
        """Monitor queue state"""
        print("   Monitor: Starting queue monitoring")
        
        for _ in range(20):  # Monitor for a while
            await asyncio.sleep(0.5)
            print(f"   Monitor: Queue size: {queue.qsize()}, "
                  f"Empty: {queue.empty()}, Full: {queue.full()}")
    
    print("1. Running producer-consumer with error handling:")
    
    # Start components
    tasks = [
        asyncio.create_task(reliable_producer("Producer1", ["item1", "item2", "item3"])),
        asyncio.create_task(reliable_producer("Producer2", ["item4", "item5", "item6"])),
        asyncio.create_task(unreliable_consumer("Consumer1")),
        asyncio.create_task(queue_monitor())
    ]
    
    # Run and collect results
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    print("\n2. Results:")
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            print(f"   Task {i}: Error - {result}")
        else:
            print(f"   Task {i}: Result - {result}")
    
    print(f"\nFinal queue state: size={queue.qsize()}, empty={queue.empty()}")

asyncio.run(demonstrate_queue_error_handling())
```

## 6.2 PriorityQueue and LifoQueue

asyncio provides specialized queue types for different use cases. Understanding when and how to use them is important for building efficient systems.

### PriorityQueue Usage

```python
import asyncio
import heapq
import dataclasses
from typing import Any
import time

@dataclasses.dataclass
class PriorityItem:
    """Item for priority queue with proper comparison"""
    priority: int
    item: Any
    timestamp: float = dataclasses.field(default_factory=time.time)
    
    def __lt__(self, other):
        # Lower priority number = higher priority
        if self.priority != other.priority:
            return self.priority < other.priority
        # If same priority, use timestamp (FIFO)
        return self.timestamp < other.timestamp

async def demonstrate_priority_queue():
    """Demonstrate PriorityQueue usage"""
    
    print("=== PriorityQueue Demonstration ===")
    
    # Create priority queue
    pq = asyncio.PriorityQueue(maxsize=10)
    
    async def task_producer():
        """Producer that creates tasks with different priorities"""
        tasks = [
            (1, "critical_task_1"),      # Highest priority
            (3, "normal_task_1"),
            (2, "high_task_1"),
            (5, "low_task_1"),           # Lowest priority
            (1, "critical_task_2"),      # Highest priority
            (3, "normal_task_2"),
            (2, "high_task_2"),
            (4, "background_task_1"),
        ]
        
        print("   Producer: Adding tasks to priority queue")
        
        for priority, task_name in tasks:
            priority_item = PriorityItem(priority, task_name)
            await pq.put(priority_item)
            print(f"   Producer: Added {task_name} (priority {priority})")
            await asyncio.sleep(0.1)  # Small delay
        
        print("   Producer: All tasks queued")
    
    async def task_processor(processor_id):
        """Processor that handles tasks by priority"""
        processed_count = 0
        
        print(f"   Processor {processor_id}: Starting")
        
        while processed_count < 4:  # Each processor handles 4 tasks
            try:
                priority_item = await asyncio.wait_for(pq.get(), timeout=2.0)
                
                task_name = priority_item.item
                priority = priority_item.priority
                
                print(f"   Processor {processor_id}: Processing {task_name} "
                      f"(priority {priority})")
                
                # Simulate work time based on priority
                work_time = 0.1 + (priority * 0.05)
                await asyncio.sleep(work_time)
                
                processed_count += 1
                print(f"   Processor {processor_id}: Completed {task_name}")
                
                pq.task_done()
                
            except asyncio.TimeoutError:
                print(f"   Processor {processor_id}: Timeout, stopping")
                break
        
        return processed_count
    
    print("1. Processing tasks by priority:")
    
    # Start producer and processors
    tasks = [
        asyncio.create_task(task_producer()),
        asyncio.create_task(task_processor("P1")),
        asyncio.create_task(task_processor("P2"))
    ]
    
    results = await asyncio.gather(*tasks)
    print(f"   Processing results: {results}")
    
    # Wait for all tasks to be done
    await pq.join()
    print("   All priority tasks completed")

asyncio.run(demonstrate_priority_queue())
```

### LifoQueue (Last-In-First-Out) Usage

```python
import asyncio

async def demonstrate_lifo_queue():
    """Demonstrate LifoQueue (stack-like behavior)"""
    
    print("=== LifoQueue Demonstration ===")
    
    # Create LIFO queue (stack)
    lifo = asyncio.LifoQueue(maxsize=5)
    
    async def stack_builder():
        """Build a stack of operations"""
        operations = [
            "initialize_database",
            "load_config",
            "start_services",
            "connect_clients",
            "ready_for_requests"
        ]
        
        print("   Builder: Building operation stack")
        
        for operation in operations:
            await lifo.put(operation)
            print(f"   Builder: Pushed {operation}")
            await asyncio.sleep(0.1)
        
        print("   Builder: Stack building complete")
    
    async def stack_executor():
        """Execute operations from stack (LIFO order)"""
        print("   Executor: Starting execution (LIFO order)")
        executed_operations = []
        
        while len(executed_operations) < 5:
            try:
                operation = await asyncio.wait_for(lifo.get(), timeout=2.0)
                
                print(f"   Executor: Executing {operation}")
                
                # Simulate execution
                await asyncio.sleep(0.2)
                
                executed_operations.append(operation)
                print(f"   Executor: Completed {operation}")
                
                lifo.task_done()
                
            except asyncio.TimeoutError:
                print("   Executor: Timeout, stopping")
                break
        
        return executed_operations
    
    print("1. Building and executing with LIFO order:")
    
    # Run builder and executor
    builder_task = asyncio.create_task(stack_builder())
    executor_task = asyncio.create_task(stack_executor())
    
    results = await asyncio.gather(builder_task, executor_task)
    executed_ops = results[1]
    
    print(f"\n2. Execution order (LIFO): {executed_ops}")
    print("   Note: Last operation pushed ('ready_for_requests') was executed first")

asyncio.run(demonstrate_lifo_queue())
```

### Comparing Queue Types

```python
import asyncio
import time
from dataclasses import dataclass

@dataclass
class QueueComparison:
    """Class to compare different queue behaviors"""
    
    async def compare_queue_types(self):
        """Compare FIFO, LIFO, and Priority queues"""
        
        print("=== Queue Type Comparison ===")
        
        # Create all three queue types
        fifo_queue = asyncio.Queue()
        lifo_queue = asyncio.LifoQueue()
        priority_queue = asyncio.PriorityQueue()
        
        # Test data
        items = ["first", "second", "third", "fourth", "fifth"]
        priorities = [3, 1, 4, 2, 5]  # For priority queue
        
        # Fill all queues with same data
        print("1. Adding items to all queues:")
        for i, item in enumerate(items):
            await fifo_queue.put(item)
            await lifo_queue.put(item)
            
            # For priority queue, use priority
            priority_item = PriorityItem(priorities[i], item)
            await priority_queue.put(priority_item)
            
            print(f"   Added: {item} (priority {priorities[i]} for PriorityQueue)")
        
        # Extract from FIFO queue
        print("\n2. FIFO Queue output (First-In-First-Out):")
        fifo_output = []
        while not fifo_queue.empty():
            item = fifo_queue.get_nowait()
            fifo_output.append(item)
            print(f"   Got: {item}")
        
        # Extract from LIFO queue
        print("\n3. LIFO Queue output (Last-In-First-Out):")
        lifo_output = []
        while not lifo_queue.empty():
            item = lifo_queue.get_nowait()
            lifo_output.append(item)
            print(f"   Got: {item}")
        
        # Extract from Priority queue
        print("\n4. Priority Queue output (Priority order):")
        priority_output = []
        while not priority_queue.empty():
            priority_item = priority_queue.get_nowait()
            priority_output.append(priority_item.item)
            print(f"   Got: {priority_item.item} (priority {priority_item.priority})")
        
        # Summary
        print("\n5. Summary:")
        print(f"   Input order:    {items}")
        print(f"   FIFO output:    {fifo_output}")
        print(f"   LIFO output:    {lifo_output}")
        print(f"   Priority output: {priority_output}")
        
        return {
            'input': items,
            'fifo': fifo_output,
            'lifo': lifo_output,
            'priority': priority_output
        }

comparison = QueueComparison()
results = asyncio.run(comparison.compare_queue_types())
```

### Real-World Queue Usage Patterns

```python
import asyncio
import logging
from datetime import datetime
from enum import Enum

class TaskType(Enum):
    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4
    BACKGROUND = 5

class TaskManager:
    """Real-world task manager using different queue types"""
    
    def __init__(self):
        self.priority_queue = asyncio.PriorityQueue()
        self.batch_queue = asyncio.Queue()
        self.undo_stack = asyncio.LifoQueue()
        self.stats = {
            'tasks_processed': 0,
            'critical_tasks': 0,
            'failed_tasks': 0
        }
    
    async def submit_task(self, task_type: TaskType, task_data: dict):
        """Submit task to appropriate queue"""
        timestamp = datetime.now()
        
        task = PriorityItem(
            priority=task_type.value,
            item={
                'type': task_type,
                'data': task_data,
                'submitted_at': timestamp,
                'id': f"task_{self.stats['tasks_processed'] + 1}"
            }
        )
        
        await self.priority_queue.put(task)
        print(f"   TaskManager: Submitted {task.item['id']} "
              f"({task_type.name} priority)")
    
    async def process_tasks(self, worker_id):
        """Process tasks from priority queue"""
        while True:
            try:
                priority_task = await asyncio.wait_for(
                    self.priority_queue.get(), timeout=2.0
                )
                
                task_info = priority_task.item
                task_id = task_info['id']
                task_type = task_info['type']
                
                print(f"   Worker {worker_id}: Processing {task_id} "
                      f"({task_type.name})")
                
                # Simulate processing
                processing_time = 0.1 + (task_type.value * 0.05)
                await asyncio.sleep(processing_time)
                
                # Update statistics
                self.stats['tasks_processed'] += 1
                if task_type == TaskType.CRITICAL:
                    self.stats['critical_tasks'] += 1
                
                # Add to undo stack for possible rollback
                await self.undo_stack.put(task_info)
                
                print(f"   Worker {worker_id}: Completed {task_id}")
                self.priority_queue.task_done()
                
            except asyncio.TimeoutError:
                print(f"   Worker {worker_id}: No tasks, stopping")
                break
            except Exception as e:
                print(f"   Worker {worker_id}: Error processing task: {e}")
                self.stats['failed_tasks'] += 1
                self.priority_queue.task_done()
    
    async def undo_last_tasks(self, count=1):
        """Undo last N tasks using LIFO stack"""
        print(f"   UndoManager: Undoing last {count} tasks")
        
        undone_tasks = []
        for i in range(count):
            if not self.undo_stack.empty():
                task_info = self.undo_stack.get_nowait()
                undone_tasks.append(task_info['id'])
                print(f"   UndoManager: Undid {task_info['id']}")
            else:
                print("   UndoManager: No more tasks to undo")
                break
        
        return undone_tasks
    
    def get_stats(self):
        """Get processing statistics"""
        return self.stats.copy()

async def demonstrate_real_world_queues():
    """Demonstrate real-world queue usage"""
    
    print("=== Real-World Queue Usage ===")
    
    task_manager = TaskManager()
    
    # Submit various tasks
    print("1. Submitting mixed priority tasks:")
    
    tasks_to_submit = [
        (TaskType.NORMAL, {'action': 'update_user_profile', 'user_id': 123}),
        (TaskType.CRITICAL, {'action': 'security_breach_response', 'alert_id': 'SEC001'}),
        (TaskType.LOW, {'action': 'cleanup_temp_files', 'directory': '/tmp'}),
        (TaskType.HIGH, {'action': 'process_payment', 'payment_id': 'PAY001'}),
        (TaskType.BACKGROUND, {'action': 'generate_report', 'report_type': 'monthly'}),
        (TaskType.CRITICAL, {'action': 'database_backup', 'backup_id': 'BK002'}),
        (TaskType.NORMAL, {'action': 'send_notification', 'user_id': 456}),
    ]
    
    for task_type, task_data in tasks_to_submit:
        await task_manager.submit_task(task_type, task_data)
    
    # Start workers
    print("\n2. Processing tasks with priority workers:")
    workers = [
        asyncio.create_task(task_manager.process_tasks(f"W{i}"))
        for i in range(2)
    ]
    
    # Wait for all tasks to be processed
    await task_manager.priority_queue.join()
    
    # Cancel workers
    for worker in workers:
        worker.cancel()
    
    await asyncio.gather(*workers, return_exceptions=True)
    
    # Show statistics
    print("\n3. Processing statistics:")
    stats = task_manager.get_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    # Demonstrate undo functionality
    print("\n4. Undo functionality:")
    undone = await task_manager.undo_last_tasks(3)
    print(f"   Undone tasks: {undone}")

asyncio.run(demonstrate_real_world_queues())
```

## 6.3 Producer-Consumer Pattern

The producer-consumer pattern is one of the most common and useful patterns in async programming. It helps decouple data generation from data processing and provides natural backpressure control.

### Basic Producer-Consumer Pattern

```python
import asyncio
import random
import time
from typing import List, Dict, Any

class ProducerConsumerDemo:
    """Demonstration of producer-consumer patterns"""
    
    def __init__(self, queue_size=5):
        self.queue = asyncio.Queue(maxsize=queue_size)
        self.stats = {
            'items_produced': 0,
            'items_consumed': 0,
            'production_time': 0,
            'consumption_time': 0
        }
    
    async def producer(self, producer_id: str, item_count: int, 
                      production_rate: float):
        """Producer that generates items at specified rate"""
        print(f"   Producer {producer_id}: Starting production of {item_count} items")
        
        for i in range(item_count):
            start_time = time.time()
            
            # Create work item
            item = {
                'id': f"{producer_id}_item_{i}",
                'producer': producer_id,
                'sequence': i,
                'data': f"data_{random.randint(100, 999)}",
                'created_at': time.time()
            }
            
            # Put item in queue (may block if queue is full)
            print(f"   Producer {producer_id}: Producing {item['id']}")
            await self.queue.put(item)
            
            end_time = time.time()
            
            # Update stats
            self.stats['items_produced'] += 1
            self.stats['production_time'] += (end_time - start_time)
            
            print(f"   Producer {producer_id}: Queued {item['id']} "
                  f"(queue size: {self.queue.qsize()})")
            
            # Wait before producing next item
            await asyncio.sleep(1.0 / production_rate)
        
        print(f"   Producer {producer_id}: Finished production")
    
    async def consumer(self, consumer_id: str, processing_time: float):
        """Consumer that processes items"""
        print(f"   Consumer {consumer_id}: Starting consumption")
        processed_items = []
        
        while True:
            try:
                start_time = time.time()
                
                # Get item from queue (may block if queue is empty)
                item = await asyncio.wait_for(self.queue.get(), timeout=3.0)
                
                get_time = time.time()
                
                print(f"   Consumer {consumer_id}: Got {item['id']} "
                      f"(queue size: {self.queue.qsize()})")
                
                # Simulate processing
                await asyncio.sleep(processing_time)
                
                end_time = time.time()
                
                # Update stats
                self.stats['items_consumed'] += 1
                self.stats['consumption_time'] += (end_time - start_time)
                
                processed_items.append(item)
                print(f"   Consumer {consumer_id}: Processed {item['id']} "
                      f"in {end_time - get_time:.3f}s")
                
                # Mark task as done
                self.queue.task_done()
                
            except asyncio.TimeoutError:
                print(f"   Consumer {consumer_id}: No more items, stopping")
                break
        
        print(f"   Consumer {consumer_id}: Processed {len(processed_items)} items")
        return processed_items
    
    async def run_demo(self, producers: List[tuple], consumers: List[tuple]):
        """Run producer-consumer demo"""
        print("=== Basic Producer-Consumer Pattern ===")
        
        # Start all producers and consumers
        tasks = []
        
        # Start producers
        for producer_id, item_count, rate in producers:
            task = asyncio.create_task(
                self.producer(producer_id, item_count, rate)
            )
            tasks.append(task)
        
        # Start consumers
        for consumer_id, processing_time in consumers:
            task = asyncio.create_task(
                self.consumer(consumer_id, processing_time)
            )
            tasks.append(task)
        
        # Wait for all tasks
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Wait for queue to be empty
        await self.queue.join()
        
        return results

async def demonstrate_basic_producer_consumer():
    """Demonstrate basic producer-consumer pattern"""
    
    demo = ProducerConsumerDemo(queue_size=3)
    
    # Define producers: (id, item_count, production_rate per second)
    producers = [
        ("P1", 5, 2.0),  # Producer 1: 5 items at 2/second
        ("P2", 3, 1.5),  # Producer 2: 3 items at 1.5/second
    ]
    
    # Define consumers: (id, processing_time per item)
    consumers = [
        ("C1", 0.3),  # Consumer 1: 0.3s per item
        ("C2", 0.5),  # Consumer 2: 0.5s per item
    ]
    
    print("1. Starting producers and consumers:")
    print(f"   Queue capacity: 3 items")
    print(f"   Producers: {len(producers)}")
    print(f"   Consumers: {len(consumers)}")
    
    start_time = time.time()
    results = await demo.run_demo(producers, consumers)
    end_time = time.time()
    
    print(f"\n2. Demo completed in {end_time - start_time:.2f}s")
    print(f"   Final stats: {demo.stats}")
    
    # Calculate efficiency metrics
    if demo.stats['items_consumed'] > 0:
        avg_production_time = demo.stats['production_time'] / demo.stats['items_produced']
        avg_consumption_time = demo.stats['consumption_time'] / demo.stats['items_consumed']
        
        print(f"   Avg production time per item: {avg_production_time:.3f}s")
        print(f"   Avg consumption time per item: {avg_consumption_time:.3f}s")

asyncio.run(demonstrate_basic_producer_consumer())
```

### Advanced Producer-Consumer with Backpressure

```python
import asyncio
import time
from enum import Enum

class BackpressureStrategy(Enum):
    BLOCK = "block"
    DROP = "drop" 
    THROTTLE = "throttle"

class AdvancedProducerConsumer:
    """Advanced producer-consumer with backpressure handling"""
    
    def __init__(self, queue_size=5, backpressure_strategy=BackpressureStrategy.BLOCK):
        self.queue = asyncio.Queue(maxsize=queue_size)
        self.backpressure_strategy = backpressure_strategy
        self.stats = {
            'produced': 0,
            'consumed': 0,
            'dropped': 0,
            'throttled': 0,
            'backpressure_events': 0
        }
        self.throttle_factor = 1.0
    
    async def adaptive_producer(self, producer_id: str, target_rate: float, 
                               duration: float):
        """Producer that adapts to backpressure"""
        print(f"   Producer {producer_id}: Starting adaptive production")
        
        start_time = time.time()
        item_count = 0
        
        while time.time() - start_time < duration:
            item = {
                'id': f"{producer_id}_item_{item_count}",
                'producer': producer_id,
                'timestamp': time.time()
            }
            
            # Handle backpressure based on strategy
            if await self._handle_backpressure(item, producer_id):
                self.stats['produced'] += 1
                print(f"   Producer {producer_id}: Produced {item['id']}")
            
            item_count += 1
            
            # Adjust rate based on throttle factor
            adjusted_rate = target_rate * self.throttle_factor
            await asyncio.sleep(1.0 / adjusted_rate)
        
        print(f"   Producer {producer_id}: Finished production "
              f"({item_count} items attempted)")
    
    async def _handle_backpressure(self, item: dict, producer_id: str) -> bool:
        """Handle backpressure according to strategy"""
        
        if self.backpressure_strategy == BackpressureStrategy.BLOCK:
            # Block until space available (default asyncio.Queue behavior)
            await self.queue.put(item)
            return True
        
        elif self.backpressure_strategy == BackpressureStrategy.DROP:
            # Drop items if queue is full
            try:
                self.queue.put_nowait(item)
                return True
            except asyncio.QueueFull:
                self.stats['dropped'] += 1
                self.stats['backpressure_events'] += 1
                print(f"   Producer {producer_id}: Dropped {item['id']} (queue full)")
                return False
        
        elif self.backpressure_strategy == BackpressureStrategy.THROTTLE:
            # Throttle production rate when queue is full
            if self.queue.full():
                self.throttle_factor *= 0.8  # Reduce rate by 20%
                self.stats['throttled'] += 1
                self.stats['backpressure_events'] += 1
                print(f"   Producer {producer_id}: Throttling (factor: {self.throttle_factor:.2f})")
            else:
                # Gradually increase rate when queue has space
                self.throttle_factor = min(1.0, self.throttle_factor * 1.05)
            
            await self.queue.put(item)
            return True
        
        return False
    
    async def variable_consumer(self, consumer_id: str, initial_rate: float,
                               rate_variation: float):
        """Consumer with variable processing rate"""
        print(f"   Consumer {consumer_id}: Starting variable consumption")
        
        current_rate = initial_rate
        processed = []
        
        while True:
            try:
                # Get item with timeout
                item = await asyncio.wait_for(self.queue.get(), timeout=2.0)
                
                # Variable processing time
                processing_time = 1.0 / current_rate
                await asyncio.sleep(processing_time)
                
                processed.append(item)
                self.stats['consumed'] += 1
                
                print(f"   Consumer {consumer_id}: Processed {item['id']} "
                      f"(rate: {current_rate:.1f}/s)")
                
                # Vary the processing rate
                import random
                rate_change = random.uniform(-rate_variation, rate_variation)
                current_rate = max(0.5, min(5.0, current_rate + rate_change))
                
                self.queue.task_done()
                
            except asyncio.TimeoutError:
                print(f"   Consumer {consumer_id}: Timeout, stopping")
                break
        
        print(f"   Consumer {consumer_id}: Processed {len(processed)} items")
        return processed

async def demonstrate_backpressure_strategies():
    """Demonstrate different backpressure strategies"""
    
    print("=== Backpressure Strategies ===")
    
    strategies = [
        BackpressureStrategy.BLOCK,
        BackpressureStrategy.DROP,
        BackpressureStrategy.THROTTLE
    ]
    
    for strategy in strategies:
        print(f"\n{strategy.value.upper()} Strategy:")
        
        system = AdvancedProducerConsumer(
            queue_size=3,
            backpressure_strategy=strategy
        )
        
        # Fast producer, slow consumer (creates backpressure)
        tasks = [
            asyncio.create_task(
                system.adaptive_producer("FastP", target_rate=5.0, duration=3.0)
            ),
            asyncio.create_task(
                system.variable_consumer("SlowC", initial_rate=2.0, rate_variation=0.5)
            )
        ]
        
        await asyncio.gather(*tasks, return_exceptions=True)
        await system.queue.join()
        
        print(f"   Strategy: {strategy.value}")
        print(f"   Stats: {system.stats}")
        
        # Calculate metrics
        total_attempted = system.stats['produced'] + system.stats['dropped']
        if total_attempted > 0:
            efficiency = system.stats['produced'] / total_attempted
            print(f"   Efficiency: {efficiency:.2%}")

asyncio.run(demonstrate_backpressure_strategies())
```

### Multi-Stage Producer-Consumer Pipeline

```python
import asyncio
import json
from typing import Optional, Callable, Any

class PipelineStage:
    """A stage in a processing pipeline"""
    
    def __init__(self, name: str, processor: Callable, 
                 input_queue: Optional[asyncio.Queue] = None,
                 output_queue: Optional[asyncio.Queue] = None,
                 worker_count: int = 1):
        self.name = name
        self.processor = processor
        self.input_queue = input_queue or asyncio.Queue()
        self.output_queue = output_queue or asyncio.Queue()
        self.worker_count = worker_count
        self.stats = {
            'processed': 0,
            'errors': 0,
            'processing_time': 0
        }
        self.workers = []
    
    async def start(self):
        """Start the stage workers"""
        for i in range(self.worker_count):
            worker = asyncio.create_task(self._worker(f"{self.name}_W{i+1}"))
            self.workers.append(worker)
    
    async def stop(self):
        """Stop the stage workers"""
        for worker in self.workers:
            worker.cancel()
        
        await asyncio.gather(*self.workers, return_exceptions=True)
        self.workers.clear()
    
    async def _worker(self, worker_id: str):
        """Worker that processes items through this stage"""
        while True:
            try:
                # Get input item
                item = await self.input_queue.get()
                
                start_time = time.time()
                
                try:
                    # Process the item
                    result = await self.processor(item)
                    
                    processing_time = time.time() - start_time
                    self.stats['processing_time'] += processing_time
                    self.stats['processed'] += 1
                    
                    print(f"   {worker_id}: Processed item {item.get('id', 'unknown')} "
                          f"in {processing_time:.3f}s")
                    
                    # Send to output queue
                    if result is not None:
                        await self.output_queue.put(result)
                
                except Exception as e:
                    self.stats['errors'] += 1
                    print(f"   {worker_id}: Error processing item: {e}")
                
                finally:
                    self.input_queue.task_done()
                
            except asyncio.CancelledError:
                break

class ProcessingPipeline:
    """Multi-stage processing pipeline"""
    
    def __init__(self):
        self.stages = []
        self.running = False
    
    def add_stage(self, stage: PipelineStage):
        """Add a stage to the pipeline"""
        self.stages.append(stage)
        
        # Connect stages
        if len(self.stages) > 1:
            previous_stage = self.stages[-2]
            previous_stage.output_queue = stage.input_queue
    
    async def start(self):
        """Start all pipeline stages"""
        print("   Pipeline: Starting all stages")
        self.running = True
        
        for stage in self.stages:
            await stage.start()
    
    async def stop(self):
        """Stop all pipeline stages"""
        print("   Pipeline: Stopping all stages")
        self.running = False
        
        for stage in reversed(self.stages):
            await stage.stop()
    
    async def put(self, item):
        """Put item into the pipeline"""
        if self.stages:
            await self.stages[0].input_queue.put(item)
    
    async def get(self, timeout=None):
        """Get processed item from the pipeline"""
        if self.stages:
            if timeout:
                return await asyncio.wait_for(
                    self.stages[-1].output_queue.get(), timeout=timeout
                )
            else:
                return await self.stages[-1].output_queue.get()
    
    def get_stats(self):
        """Get statistics for all stages"""
        return {stage.name: stage.stats.copy() for stage in self.stages}

async def demonstrate_processing_pipeline():
    """Demonstrate multi-stage processing pipeline"""
    
    print("=== Multi-Stage Processing Pipeline ===")
    
    # Define processing functions for each stage
    async def extract_stage(item):
        """Extract and validate data"""
        await asyncio.sleep(0.1)  # Simulate work
        
        if 'raw_data' not in item:
            raise ValueError("Missing raw_data")
        
        return {
            'id': item['id'],
            'extracted_data': item['raw_data'].upper(),
            'stage': 'extracted'
        }
    
    async def transform_stage(item):
        """Transform the data"""
        await asyncio.sleep(0.15)  # Simulate work
        
        transformed_data = item['extracted_data'][::-1]  # Reverse string
        
        return {
            'id': item['id'],
            'transformed_data': transformed_data,
            'original_data': item['extracted_data'],
            'stage': 'transformed'
        }
    
    async def load_stage(item):
        """Load/save the processed data"""
        await asyncio.sleep(0.05)  # Simulate work
        
        return {
            'id': item['id'],
            'final_data': f"FINAL_{item['transformed_data']}",
            'metadata': {
                'original': item['original_data'],
                'processed_at': time.time()
            },
            'stage': 'loaded'
        }
    
    # Create pipeline
    pipeline = ProcessingPipeline()
    
    # Add stages
    extract_stage_obj = PipelineStage("Extract", extract_stage, worker_count=2)
    transform_stage_obj = PipelineStage("Transform", transform_stage, worker_count=2)
    load_stage_obj = PipelineStage("Load", load_stage, worker_count=1)
    
    pipeline.add_stage(extract_stage_obj)
    pipeline.add_stage(transform_stage_obj)
    pipeline.add_stage(load_stage_obj)
    
    # Start pipeline
    await pipeline.start()
    
    # Create data producer
    async def data_producer():
        """Produce raw data items"""
        for i in range(10):
            item = {
                'id': f"data_{i}",
                'raw_data': f"raw_content_{i}_hello_world"
            }
            
            print(f"   Producer: Sending {item['id']}")
            await pipeline.put(item)
            await asyncio.sleep(0.2)
        
        print("   Producer: All data sent")
    
    # Create result consumer
    async def result_consumer():
        """Consume processed results"""
        results = []
        
        for _ in range(10):
            try:
                result = await pipeline.get(timeout=5.0)
                results.append(result)
                print(f"   Consumer: Received {result['id']}: {result['final_data']}")
            
            except asyncio.TimeoutError:
                print("   Consumer: Timeout waiting for result")
                break
        
        return results
    
    # Run producer and consumer
    print("1. Running pipeline with producer and consumer:")
    
    tasks = [
        asyncio.create_task(data_producer()),
        asyncio.create_task(result_consumer())
    ]
    
    results = await asyncio.gather(*tasks)
    processed_items = results[1]
    
    # Wait for pipeline to finish processing
    for stage in pipeline.stages:
        await stage.input_queue.join()
    
    # Stop pipeline
    await pipeline.stop()
    
    # Show statistics
    print(f"\n2. Pipeline statistics:")
    stats = pipeline.get_stats()
    
    for stage_name, stage_stats in stats.items():
        print(f"   {stage_name}:")
        for key, value in stage_stats.items():
            if key == 'processing_time':
                avg_time = value / max(1, stage_stats['processed'])
                print(f"     {key}: {value:.3f}s (avg: {avg_time:.3f}s)")
            else:
                print(f"     {key}: {value}")
    
    print(f"\n3. Pipeline processed {len(processed_items)} items successfully")

asyncio.run(demonstrate_processing_pipeline())
```

This completes the first part of Chapter 6, covering queue fundamentals, different queue types, and producer-consumer patterns. The chapter demonstrates practical usage patterns that are essential for building robust async applications.

Would you like me to continue with the remaining sections (6.4 Fan-Out/Fan-In Patterns, 6.5 Backpressure and Flow Control, and 6.6 Building Pipeline Architectures)?
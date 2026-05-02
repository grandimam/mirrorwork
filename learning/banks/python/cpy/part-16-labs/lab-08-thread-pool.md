# Lab 8: Thread Pool

## Objective

Build a custom thread pool implementation from scratch to understand thread management, work queuing, and the challenges of concurrent Python programming.

## Prerequisites

- Understanding of threading internals (Part 10)
- Knowledge of the GIL (Part 6)
- Familiarity with thread synchronization primitives

## Lab Setup

```python
# lab08_thread_pool.py
import threading
import queue
import time
import sys
import weakref
from dataclasses import dataclass, field
from typing import Callable, Any, List, Dict, Optional, Tuple
from concurrent.futures import Future
import traceback
```

## Exercise 1: Basic Work Queue

Implement a thread-safe work queue:

```python
@dataclass
class WorkItem:
    """Represents a unit of work."""
    id: int
    func: Callable
    args: Tuple
    kwargs: Dict
    future: Future
    priority: int = 0
    submitted_at: float = field(default_factory=time.time)

class WorkQueue:
    """
    Thread-safe work queue with priorities.

    TODO: Implement a priority-based work queue.
    """

    def __init__(self, maxsize: int = 0):
        self._queue = queue.PriorityQueue(maxsize)
        self._lock = threading.Lock()
        self._item_counter = 0

    def put(self, item: WorkItem, block: bool = True, timeout: float = None):
        """Add work item to queue."""
        # Priority queue uses (priority, counter, item) tuple
        # Counter ensures FIFO for same priority
        with self._lock:
            self._item_counter += 1
            counter = self._item_counter

        self._queue.put((-item.priority, counter, item), block, timeout)

    def get(self, block: bool = True, timeout: float = None) -> Optional[WorkItem]:
        """Get next work item."""
        try:
            priority, counter, item = self._queue.get(block, timeout)
            return item
        except queue.Empty:
            return None

    def task_done(self):
        """Mark task as done."""
        self._queue.task_done()

    def qsize(self) -> int:
        """Get queue size."""
        return self._queue.qsize()

    def empty(self) -> bool:
        """Check if queue is empty."""
        return self._queue.empty()
```

## Exercise 2: Worker Thread

Implement worker threads:

```python
class Worker(threading.Thread):
    """
    Worker thread that processes tasks from a queue.

    TODO: Implement worker that:
    1. Pulls tasks from queue
    2. Executes them
    3. Handles exceptions
    4. Sets results on futures
    """

    def __init__(self, pool: 'ThreadPool', work_queue: WorkQueue, name: str):
        super().__init__(name=name, daemon=True)
        self.pool = pool
        self.work_queue = work_queue
        self._shutdown = threading.Event()
        self._current_task: Optional[WorkItem] = None
        self._tasks_completed = 0
        self._total_time = 0.0

    def run(self):
        """Main worker loop."""
        while not self._shutdown.is_set():
            try:
                # Get task with timeout to allow shutdown checks
                task = self.work_queue.get(block=True, timeout=0.1)

                if task is None:
                    continue

                self._current_task = task
                start_time = time.time()

                try:
                    # Execute the task
                    result = task.func(*task.args, **task.kwargs)
                    task.future.set_result(result)

                except Exception as e:
                    # Set exception on future
                    task.future.set_exception(e)

                finally:
                    elapsed = time.time() - start_time
                    self._total_time += elapsed
                    self._tasks_completed += 1
                    self._current_task = None
                    self.work_queue.task_done()

            except Exception as e:
                # Worker loop exception - log and continue
                print(f"Worker {self.name} error: {e}")

    def shutdown(self):
        """Signal worker to shutdown."""
        self._shutdown.set()

    def get_stats(self) -> Dict:
        """Get worker statistics."""
        return {
            'name': self.name,
            'tasks_completed': self._tasks_completed,
            'total_time': self._total_time,
            'avg_time': self._total_time / self._tasks_completed if self._tasks_completed else 0,
            'is_busy': self._current_task is not None
        }
```

## Exercise 3: Thread Pool Manager

Implement the main thread pool:

```python
class ThreadPool:
    """
    Custom thread pool implementation.

    TODO: Implement thread pool with:
    1. Dynamic worker scaling
    2. Task submission
    3. Graceful shutdown
    4. Statistics tracking
    """

    def __init__(self, min_workers: int = 2, max_workers: int = 10,
                 queue_size: int = 100):
        self.min_workers = min_workers
        self.max_workers = max_workers

        self.work_queue = WorkQueue(maxsize=queue_size)
        self.workers: List[Worker] = []
        self._lock = threading.Lock()
        self._task_counter = 0
        self._shutdown = False

        # Statistics
        self.stats = {
            'submitted': 0,
            'completed': 0,
            'failed': 0,
        }

        # Start minimum workers
        self._start_workers(min_workers)

    def _start_workers(self, count: int):
        """Start worker threads."""
        with self._lock:
            for i in range(count):
                worker = Worker(
                    self,
                    self.work_queue,
                    name=f"Worker-{len(self.workers)}"
                )
                worker.start()
                self.workers.append(worker)

    def _scale_workers(self):
        """
        Scale workers based on queue size.

        TODO: Implement auto-scaling logic.
        """
        queue_size = self.work_queue.qsize()
        active_workers = sum(1 for w in self.workers if w.is_alive())

        # Scale up if queue is backing up
        if queue_size > active_workers * 2 and active_workers < self.max_workers:
            to_add = min(2, self.max_workers - active_workers)
            self._start_workers(to_add)
            print(f"Scaled up: added {to_add} workers")

    def submit(self, func: Callable, *args, priority: int = 0, **kwargs) -> Future:
        """Submit a task to the pool."""
        if self._shutdown:
            raise RuntimeError("Pool is shutdown")

        future = Future()

        with self._lock:
            self._task_counter += 1
            task_id = self._task_counter

        work_item = WorkItem(
            id=task_id,
            func=func,
            args=args,
            kwargs=kwargs,
            future=future,
            priority=priority
        )

        self.work_queue.put(work_item)
        self.stats['submitted'] += 1

        # Check if we need to scale
        self._scale_workers()

        return future

    def map(self, func: Callable, items: List, timeout: float = None) -> List:
        """Map function over items."""
        futures = [self.submit(func, item) for item in items]

        results = []
        for future in futures:
            try:
                results.append(future.result(timeout=timeout))
                self.stats['completed'] += 1
            except Exception as e:
                self.stats['failed'] += 1
                results.append(e)

        return results

    def shutdown(self, wait: bool = True, timeout: float = 30):
        """Shutdown the pool."""
        print("Shutting down thread pool...")
        self._shutdown = True

        # Signal all workers to stop
        for worker in self.workers:
            worker.shutdown()

        if wait:
            # Wait for workers to finish
            deadline = time.time() + timeout

            for worker in self.workers:
                remaining = deadline - time.time()
                if remaining > 0:
                    worker.join(timeout=remaining)

        print(f"Shutdown complete. Stats: {self.stats}")

    def get_stats(self) -> Dict:
        """Get pool statistics."""
        worker_stats = [w.get_stats() for w in self.workers]

        return {
            'pool': self.stats,
            'queue_size': self.work_queue.qsize(),
            'active_workers': sum(1 for w in self.workers if w.is_alive()),
            'total_workers': len(self.workers),
            'workers': worker_stats
        }

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown(wait=True)
        return False
```

## Exercise 4: Task Scheduler

Add scheduled task execution:

```python
class ScheduledTask:
    """A task scheduled for future execution."""

    def __init__(self, func: Callable, args: Tuple, kwargs: Dict,
                 run_at: float, interval: float = 0, repeat: bool = False):
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.run_at = run_at
        self.interval = interval
        self.repeat = repeat
        self.cancelled = False

class TaskScheduler:
    """
    Schedule tasks for future execution.

    TODO: Implement task scheduling with:
    1. One-time delayed execution
    2. Periodic execution
    3. Cancellation
    """

    def __init__(self, pool: ThreadPool):
        self.pool = pool
        self.scheduled_tasks: List[ScheduledTask] = []
        self._lock = threading.Lock()
        self._scheduler_thread: Optional[threading.Thread] = None
        self._shutdown = threading.Event()

    def schedule(self, func: Callable, delay: float, *args, **kwargs) -> ScheduledTask:
        """Schedule a task to run after delay seconds."""
        task = ScheduledTask(
            func=func,
            args=args,
            kwargs=kwargs,
            run_at=time.time() + delay
        )

        with self._lock:
            self.scheduled_tasks.append(task)
            self.scheduled_tasks.sort(key=lambda t: t.run_at)

        self._ensure_scheduler_running()
        return task

    def schedule_periodic(self, func: Callable, interval: float,
                         *args, **kwargs) -> ScheduledTask:
        """Schedule a task to run periodically."""
        task = ScheduledTask(
            func=func,
            args=args,
            kwargs=kwargs,
            run_at=time.time() + interval,
            interval=interval,
            repeat=True
        )

        with self._lock:
            self.scheduled_tasks.append(task)
            self.scheduled_tasks.sort(key=lambda t: t.run_at)

        self._ensure_scheduler_running()
        return task

    def cancel(self, task: ScheduledTask):
        """Cancel a scheduled task."""
        task.cancelled = True
        with self._lock:
            if task in self.scheduled_tasks:
                self.scheduled_tasks.remove(task)

    def _ensure_scheduler_running(self):
        """Ensure scheduler thread is running."""
        if self._scheduler_thread is None or not self._scheduler_thread.is_alive():
            self._scheduler_thread = threading.Thread(
                target=self._scheduler_loop,
                name="Scheduler",
                daemon=True
            )
            self._scheduler_thread.start()

    def _scheduler_loop(self):
        """Main scheduler loop."""
        while not self._shutdown.is_set():
            now = time.time()

            with self._lock:
                # Find due tasks
                due_tasks = []
                remaining = []

                for task in self.scheduled_tasks:
                    if task.cancelled:
                        continue

                    if task.run_at <= now:
                        due_tasks.append(task)
                        if task.repeat:
                            # Reschedule
                            task.run_at = now + task.interval
                            remaining.append(task)
                    else:
                        remaining.append(task)

                self.scheduled_tasks = sorted(remaining, key=lambda t: t.run_at)

            # Submit due tasks to pool
            for task in due_tasks:
                self.pool.submit(task.func, *task.args, **task.kwargs)

            # Sleep until next task or check interval
            sleep_time = 0.1
            with self._lock:
                if self.scheduled_tasks:
                    next_run = self.scheduled_tasks[0].run_at
                    sleep_time = min(sleep_time, max(0, next_run - time.time()))

            time.sleep(sleep_time)

    def shutdown(self):
        """Shutdown scheduler."""
        self._shutdown.set()
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=1)
```

## Exercise 5: Complete Thread Pool System

Combine all components:

```python
class ThreadPoolSystem:
    """Complete thread pool system with scheduling and monitoring."""

    def __init__(self, min_workers: int = 2, max_workers: int = 10):
        self.pool = ThreadPool(min_workers, max_workers)
        self.scheduler = TaskScheduler(self.pool)
        self._monitor_thread: Optional[threading.Thread] = None
        self._monitoring = False

    def submit(self, func: Callable, *args, **kwargs) -> Future:
        """Submit task for immediate execution."""
        return self.pool.submit(func, *args, **kwargs)

    def schedule(self, func: Callable, delay: float, *args, **kwargs) -> ScheduledTask:
        """Schedule task for delayed execution."""
        return self.scheduler.schedule(func, delay, *args, **kwargs)

    def schedule_periodic(self, func: Callable, interval: float,
                         *args, **kwargs) -> ScheduledTask:
        """Schedule periodic task."""
        return self.scheduler.schedule_periodic(func, interval, *args, **kwargs)

    def map(self, func: Callable, items: List) -> List:
        """Map function over items in parallel."""
        return self.pool.map(func, items)

    def start_monitoring(self, interval: float = 1.0):
        """
        TODO: Start background monitoring.

        Print stats periodically.
        """
        self._monitoring = True

        def monitor_loop():
            while self._monitoring:
                stats = self.pool.get_stats()
                print(f"\n--- Pool Stats ---")
                print(f"Queue: {stats['queue_size']}")
                print(f"Workers: {stats['active_workers']}/{stats['total_workers']}")
                print(f"Submitted: {stats['pool']['submitted']}")
                print(f"Completed: {stats['pool']['completed']}")
                time.sleep(interval)

        self._monitor_thread = threading.Thread(
            target=monitor_loop,
            name="Monitor",
            daemon=True
        )
        self._monitor_thread.start()

    def stop_monitoring(self):
        """Stop monitoring."""
        self._monitoring = False

    def shutdown(self, wait: bool = True):
        """Shutdown everything."""
        self.stop_monitoring()
        self.scheduler.shutdown()
        self.pool.shutdown(wait=wait)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()
        return False
```

## Demo Application

```python
def cpu_task(n: int) -> int:
    """CPU-bound task."""
    total = 0
    for i in range(n):
        total += i ** 2
    return total

def io_task(duration: float) -> str:
    """I/O-bound task (simulated)."""
    time.sleep(duration)
    return f"Slept for {duration}s"

def failing_task():
    """Task that fails."""
    raise ValueError("Intentional failure")

def demo():
    """Demonstrate the thread pool system."""
    print("=== Thread Pool Demo ===\n")

    with ThreadPoolSystem(min_workers=2, max_workers=5) as system:
        # 1. Basic submission
        print("1. Basic task submission:")
        future = system.submit(cpu_task, 10000)
        print(f"   Result: {future.result()}")

        # 2. Multiple tasks
        print("\n2. Multiple parallel tasks:")
        futures = [system.submit(cpu_task, 10000) for _ in range(5)]

        for i, f in enumerate(futures):
            print(f"   Task {i}: {f.result()}")

        # 3. Map operation
        print("\n3. Map operation:")
        results = system.map(cpu_task, [1000, 2000, 3000, 4000, 5000])
        print(f"   Results: {results}")

        # 4. Priority tasks
        print("\n4. Priority tasks:")
        low_priority = system.pool.submit(io_task, 0.1, priority=1)
        high_priority = system.pool.submit(io_task, 0.1, priority=10)

        print(f"   High priority: {high_priority.result()}")
        print(f"   Low priority: {low_priority.result()}")

        # 5. Scheduled tasks
        print("\n5. Scheduled execution:")
        scheduled = system.schedule(
            lambda: print("   Delayed task executed!"),
            delay=1.0
        )
        time.sleep(1.5)

        # 6. Periodic tasks
        print("\n6. Periodic execution:")
        counter = [0]

        def periodic_func():
            counter[0] += 1
            print(f"   Periodic task #{counter[0]}")

        periodic = system.schedule_periodic(periodic_func, interval=0.5)
        time.sleep(2)
        system.scheduler.cancel(periodic)
        print("   Periodic task cancelled")

        # 7. Error handling
        print("\n7. Error handling:")
        error_future = system.submit(failing_task)
        try:
            error_future.result()
        except Exception as e:
            print(f"   Caught exception: {e}")

        # 8. Statistics
        print("\n8. Pool statistics:")
        stats = system.pool.get_stats()
        print(f"   Total submitted: {stats['pool']['submitted']}")
        print(f"   Total completed: {stats['pool']['completed']}")
        print(f"   Total failed: {stats['pool']['failed']}")
        print(f"   Active workers: {stats['active_workers']}")

    print("\nPool shutdown complete")

if __name__ == "__main__":
    demo()
```

## Expected Output

```
=== Thread Pool Demo ===

1. Basic task submission:
   Result: 333283335000

2. Multiple parallel tasks:
   Task 0: 333283335000
   Task 1: 333283335000
   Task 2: 333283335000
   Task 3: 333283335000
   Task 4: 333283335000

3. Map operation:
   Results: [332833500, 1333333000, 4499998500, 10666660000, 20833325000]

5. Scheduled execution:
   Delayed task executed!

6. Periodic execution:
   Periodic task #1
   Periodic task #2
   Periodic task #3
   Periodic task cancelled

7. Error handling:
   Caught exception: Intentional failure

8. Pool statistics:
   Total submitted: 15
   Total completed: 13
   Total failed: 1
   Active workers: 3

Pool shutdown complete
```

## Submission

1. Complete all TODO sections
2. Add support for task cancellation
3. Implement worker thread health monitoring
4. Bonus: Add task dependencies (task A waits for task B)

---

[Next: Lab 9 - C Extension →](lab-09-c-extension.md)

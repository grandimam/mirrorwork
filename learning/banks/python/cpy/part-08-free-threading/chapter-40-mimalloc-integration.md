# Chapter 40: Mimalloc Integration

## 40.1 Why a New Allocator?

The default Python allocator (pymalloc) wasn't designed for multi-threaded use:

```
┌─────────────────────────────────────────────────────────────────┐
│              Allocator Challenges                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Traditional pymalloc (with GIL):                                │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  • Global arenas and pools                               │    │
│  │  • GIL protects all allocation/deallocation              │    │
│  │  • Single-threaded: Very fast                            │    │
│  │  • Multi-threaded: GIL serializes everything            │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Without GIL - need thread-safe allocator:                       │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Option 1: Add locks to pymalloc                        │    │
│  │    • Heavy contention on global pools                   │    │
│  │    • Performance disaster                               │    │
│  │                                                          │    │
│  │  Option 2: Use mimalloc                                 │    │
│  │    • Thread-local heaps                                 │    │
│  │    • Designed for concurrency                           │    │
│  │    • Excellent performance                              │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 40.2 What is Mimalloc?

Mimalloc is Microsoft's high-performance allocator:

```
┌─────────────────────────────────────────────────────────────────┐
│              Mimalloc Overview                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Key Features:                                                   │
│  • Thread-local free lists                                       │
│  • Lock-free allocation (fast path)                              │
│  • Efficient cross-thread deallocation                          │
│  • Excellent cache locality                                      │
│  • Low fragmentation                                             │
│                                                                  │
│  Performance:                                                    │
│  • Single-threaded: Competitive with best allocators           │
│  • Multi-threaded: Excellent scaling                            │
│  • Allocation: ~50 cycles (fast path)                           │
│  • Deallocation: ~30 cycles (same thread)                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 40.3 Mimalloc Architecture

### Thread-Local Heaps

```
┌─────────────────────────────────────────────────────────────────┐
│              Mimalloc Thread-Local Heaps                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Thread 1                Thread 2                Thread 3       │
│  ┌──────────┐           ┌──────────┐           ┌──────────┐    │
│  │  Heap 1  │           │  Heap 2  │           │  Heap 3  │    │
│  │ ┌──────┐ │           │ ┌──────┐ │           │ ┌──────┐ │    │
│  │ │Pages │ │           │ │Pages │ │           │ │Pages │ │    │
│  │ └──────┘ │           │ └──────┘ │           │ └──────┘ │    │
│  │ ┌──────┐ │           │ ┌──────┐ │           │ ┌──────┐ │    │
│  │ │ Free │ │           │ │ Free │ │           │ │ Free │ │    │
│  │ │ List │ │           │ │ List │ │           │ │ List │ │    │
│  │ └──────┘ │           │ └──────┘ │           │ └──────┘ │    │
│  └──────────┘           └──────────┘           └──────────┘    │
│       │                      │                      │           │
│       └──────────────────────┼──────────────────────┘           │
│                              │                                   │
│                    ┌─────────────────┐                          │
│                    │  Global Arenas  │                          │
│                    └─────────────────┘                          │
│                                                                  │
│  Allocation: Thread uses own heap (no locks!)                   │
│  Deallocation: Same thread → direct free                        │
│                Other thread → delayed free list                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Page-Based Organization

```c
// Mimalloc organizes memory into pages
typedef struct mi_page_s {
    uint8_t segment_idx;      // Index in segment
    uint8_t segment_in_use:1; // Is this segment in use?
    uint8_t is_reset:1;       // Has the page been reset?

    uint16_t capacity;        // Number of blocks
    uint16_t reserved;        // Reserved blocks

    mi_block_t* free;         // Free list
    mi_block_t* local_free;   // Thread-local free list

    _Atomic(mi_block_t*) thread_free;  // Cross-thread free list

    size_t block_size;        // Size of each block
    mi_heap_t* heap;          // Owning heap
} mi_page_t;
```

## 40.4 Integration with CPython

### Replacing the Allocator

```c
// Python's allocation functions redirect to mimalloc

// Configure Python to use mimalloc
#ifdef Py_GIL_DISABLED

// Small object allocator
void* _PyObject_Malloc(size_t size) {
    return mi_malloc(size);
}

void _PyObject_Free(void *ptr) {
    mi_free(ptr);
}

void* _PyObject_Realloc(void *ptr, size_t new_size) {
    return mi_realloc(ptr, new_size);
}

// Raw memory allocator
void* _PyMem_RawMalloc(size_t size) {
    return mi_malloc(size);
}

void _PyMem_RawFree(void *ptr) {
    mi_free(ptr);
}

#endif
```

### Heap Per Thread

```c
// Each Python thread has a mimalloc heap
typedef struct _ts {
    // ... other fields ...

    #ifdef Py_GIL_DISABLED
    mi_heap_t *mi_heap;  // Thread's mimalloc heap
    #endif
} PyThreadState;

// Initialize heap when thread is created
void _PyThread_Init(PyThreadState *tstate) {
    #ifdef Py_GIL_DISABLED
    tstate->mi_heap = mi_heap_new();
    #endif
}

// Destroy heap when thread exits
void _PyThread_Fini(PyThreadState *tstate) {
    #ifdef Py_GIL_DISABLED
    mi_heap_destroy(tstate->mi_heap);
    #endif
}
```

## 40.5 Allocation Patterns

### Fast Path: Same Thread

```c
// Allocation within same thread - very fast

void* mi_heap_malloc(mi_heap_t* heap, size_t size) {
    // Find appropriate page for this size
    mi_page_t* page = mi_heap_find_page(heap, size);

    if (page->free != NULL) {
        // Fast path: Pop from free list
        mi_block_t* block = page->free;
        page->free = block->next;
        return block;
    }

    // Slow path: Get new page or expand
    return mi_heap_malloc_slow(heap, size);
}
```

### Cross-Thread Deallocation

```c
// Freeing object allocated by another thread

void mi_free(void* ptr) {
    if (ptr == NULL) return;

    mi_page_t* page = mi_ptr_page(ptr);
    mi_heap_t* owning_heap = page->heap;

    if (owning_heap == mi_get_current_heap()) {
        // Same thread: Direct free
        mi_page_free(page, ptr);
    } else {
        // Different thread: Add to thread_free list
        mi_block_t* block = (mi_block_t*)ptr;
        mi_block_t* old_free;
        do {
            old_free = mi_atomic_load(&page->thread_free);
            block->next = old_free;
        } while (!mi_atomic_cas(&page->thread_free, &old_free, block));

        // Owner thread will process thread_free later
    }
}
```

### Processing Cross-Thread Frees

```c
// Owning thread collects cross-thread frees

void mi_heap_collect(mi_heap_t* heap) {
    for (mi_page_t* page = heap->pages; page != NULL; page = page->next) {
        // Atomically grab thread_free list
        mi_block_t* tfree = mi_atomic_exchange(&page->thread_free, NULL);

        // Append to local free list
        if (tfree != NULL) {
            mi_block_t* tail = tfree;
            while (tail->next != NULL) {
                tail = tail->next;
            }
            tail->next = page->local_free;
            page->local_free = tfree;
        }
    }
}
```

## 40.6 Performance Benefits

### Comparison with Other Allocators

```
┌─────────────────────────────────────────────────────────────────┐
│              Allocator Performance Comparison                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Single-Threaded Allocation (ops/sec, higher is better):        │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  glibc malloc:     10M                                 │     │
│  │  jemalloc:         15M                                 │     │
│  │  tcmalloc:         14M                                 │     │
│  │  mimalloc:         18M                                 │     │
│  │  pymalloc (GIL):   20M (optimized for Python)         │     │
│  └────────────────────────────────────────────────────────┘     │
│                                                                  │
│  8-Thread Allocation (ops/sec/thread):                          │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  glibc malloc:     2M   (heavy contention)            │     │
│  │  jemalloc:         12M  (good scaling)                │     │
│  │  tcmalloc:         11M  (good scaling)                │     │
│  │  mimalloc:         16M  (excellent scaling)           │     │
│  │  pymalloc (GIL):   2.5M (GIL bottleneck)              │     │
│  └────────────────────────────────────────────────────────┘     │
│                                                                  │
│  mimalloc: Best combination of speed and scaling                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Python-Specific Benefits

```python
import time
import threading

def allocation_benchmark(iterations):
    """Benchmark object allocation."""
    objects = []
    for _ in range(iterations):
        # Create various Python objects
        obj = {'key': [1, 2, 3], 'value': 'string'}
        objects.append(obj)
        if len(objects) > 1000:
            objects.pop(0)

def threaded_benchmark(num_threads, iterations_per_thread):
    threads = []
    start = time.perf_counter()

    for _ in range(num_threads):
        t = threading.Thread(
            target=allocation_benchmark,
            args=(iterations_per_thread,)
        )
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    return time.perf_counter() - start

# Single-threaded
single = threaded_benchmark(1, 100000)
print(f"Single-threaded: {single:.2f}s")

# Multi-threaded with mimalloc
for n in [2, 4, 8]:
    elapsed = threaded_benchmark(n, 100000 // n)
    print(f"{n} threads: {elapsed:.2f}s")

# Expected results with mimalloc (free-threaded Python):
# 1 thread: 1.0s
# 2 threads: 0.55s (good scaling)
# 4 threads: 0.30s (excellent scaling)
# 8 threads: 0.20s (near-linear scaling)
```

## 40.7 Memory Fragmentation

### Mimalloc's Approach

```c
// Mimalloc uses size-segregated pages

// Each page contains blocks of one size
// Reduces fragmentation significantly

// Size classes (simplified):
// 8, 16, 24, 32, 48, 64, 80, 96, 128, 192, 256, ...

mi_page_t* mi_heap_find_page(mi_heap_t* heap, size_t size) {
    // Round up to size class
    size_t size_class = mi_size_class(size);

    // Get page for this size class
    mi_page_t* page = heap->pages[size_class];

    if (page == NULL || page->free == NULL) {
        // Need new page for this size class
        page = mi_page_new(heap, size_class);
    }

    return page;
}
```

### Comparison with pymalloc

```
┌─────────────────────────────────────────────────────────────────┐
│              Fragmentation Comparison                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  pymalloc:                                                       │
│  • Pool size: 4KB                                                │
│  • Block sizes: 8, 16, 24, ... 512 bytes                        │
│  • Arenas: 256KB                                                 │
│  • Fragmentation: Low (good size classes)                       │
│                                                                  │
│  mimalloc:                                                       │
│  • Page size: 64KB (default)                                    │
│  • More size classes (better fit)                               │
│  • Segments: 4MB                                                 │
│  • Fragmentation: Very low                                       │
│                                                                  │
│  Both are good; mimalloc slightly better for varied sizes       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 40.8 Configuration Options

### Tuning Mimalloc

```c
// Mimalloc can be tuned for different workloads

// Set options before any allocation
void configure_mimalloc(void) {
    // Enable debug output
    mi_option_enable(mi_option_verbose);

    // Set eager page commit (trade memory for speed)
    mi_option_set(mi_option_eager_commit, 1);

    // Configure page reset delay
    mi_option_set(mi_option_reset_delay, 100);  // milliseconds

    // Enable secure mode (more checks, slower)
    // mi_option_enable(mi_option_secure);
}
```

### Python Configuration

```python
# Environment variables for mimalloc (if supported)
import os

# Verbose output
os.environ['MIMALLOC_VERBOSE'] = '1'

# Show statistics on exit
os.environ['MIMALLOC_SHOW_STATS'] = '1'

# Reserve more virtual memory
os.environ['MIMALLOC_RESERVE_HUGE_OS_PAGES'] = '1'
```

## 40.9 Debugging Memory Issues

### Using Mimalloc Stats

```c
// Print mimalloc statistics
void print_memory_stats(void) {
    mi_stats_print(NULL);
}

// Sample output:
// heap stats:    peak      total      freed     unit      count
//   reserved:   64.0 MiB   64.0 MiB      -          -         -
//  committed:   16.0 MiB   16.0 MiB      -          -         -
//      reset:       -          -          -          -         -
//     purged:       -          -          -          -         -
//      total:    2.0 MiB    4.0 MiB    2.0 MiB      -         -
//
// malloc requested:         1.5 MiB
```

### Python-Level Inspection

```python
import sys

def get_memory_stats():
    """Get memory allocation statistics."""
    if hasattr(sys, 'get_allocator_stats'):
        stats = sys.get_allocator_stats()
        print(f"Allocated: {stats['allocated'] / 1024 / 1024:.2f} MB")
        print(f"Peak: {stats['peak'] / 1024 / 1024:.2f} MB")
        print(f"Allocations: {stats['num_allocs']}")
        print(f"Frees: {stats['num_frees']}")
    else:
        # Fallback to tracemalloc
        import tracemalloc
        tracemalloc.start()
        # ... run code ...
        current, peak = tracemalloc.get_traced_memory()
        print(f"Current: {current / 1024 / 1024:.2f} MB")
        print(f"Peak: {peak / 1024 / 1024:.2f} MB")
```

## 40.10 Alternatives Considered

### Other Allocators

```
┌─────────────────────────────────────────────────────────────────┐
│              Allocator Alternatives                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  jemalloc:                                                       │
│  • Good multi-threaded performance                              │
│  • Used by Firefox, Facebook                                    │
│  • More complex than mimalloc                                   │
│  • Larger code size                                             │
│                                                                  │
│  tcmalloc (Google):                                              │
│  • Thread-caching malloc                                        │
│  • Good performance                                              │
│  • Higher memory overhead                                        │
│                                                                  │
│  snmalloc:                                                       │
│  • Microsoft Research                                            │
│  • Message-passing design                                        │
│  • Very scalable                                                 │
│                                                                  │
│  Why mimalloc?                                                   │
│  • Best overall performance/complexity ratio                    │
│  • Small code footprint                                         │
│  • Actively maintained                                           │
│  • Liberal license                                               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Summary

- **Mimalloc** is a high-performance, thread-safe allocator
- **Thread-local heaps** minimize contention
- **Cross-thread deallocation** uses lock-free queues
- **Excellent scaling** with number of threads
- **Low fragmentation** with size-segregated pages
- **Replaces pymalloc** in free-threaded Python
- **Configurable** for different workloads

## Practice Exercises

1. Benchmark allocation performance with different numbers of threads
2. Compare memory usage between pymalloc and mimalloc
3. Profile a multi-threaded application's allocation patterns
4. Experiment with mimalloc configuration options

---

[← Previous: Deferred Reference Counting](chapter-39-deferred-reference-counting.md) | [Next: Free-Threaded C Extensions →](chapter-41-free-threaded-extensions.md)

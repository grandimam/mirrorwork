# Chapter 19: pymalloc Allocator

## 19.1 Arena, Pool, Block Hierarchy

pymalloc organizes memory in three levels:

```
┌─────────────────────────────────────────────────────────────────┐
│                    pymalloc Hierarchy                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Arena (256 KB)                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Pool    Pool    Pool    Pool    ...    Pool            │    │
│  │  (4KB)   (4KB)   (4KB)   (4KB)          (4KB)           │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Pool (4 KB) - dedicated to one size class                      │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Block  Block  Block  Block  ...  Block                 │    │
│  │  (8-512 bytes each, all same size in one pool)          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Block - individual allocation unit                              │
│  ┌──────────────────┐                                           │
│  │  User Data       │  Sizes: 8, 16, 24, 32, ..., 512 bytes    │
│  └──────────────────┘  (multiple of 8, called "size classes")   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Dimensions

| Unit | Size | Contains |
|------|------|----------|
| Block | 8-512 bytes | Single allocation |
| Pool | 4 KB | Many blocks of same size class |
| Arena | 256 KB | 64 pools |

## 19.2 Size Classes

pymalloc uses size classes in 8-byte increments:

```
┌────────────────────────────────────────────────────────────┐
│                    Size Classes                             │
├────────────────────────────────────────────────────────────┤
│                                                             │
│  Index │ Block Size │ Request Range                        │
│  ──────┼────────────┼────────────────────                  │
│    0   │     8      │    1 -   8 bytes                     │
│    1   │    16      │    9 -  16 bytes                     │
│    2   │    24      │   17 -  24 bytes                     │
│    3   │    32      │   25 -  32 bytes                     │
│   ...  │   ...      │   ...                                │
│   63   │   512      │  505 - 512 bytes                     │
│                                                             │
│  Request 7 bytes  → Size class 0 → Block of 8 bytes        │
│  Request 17 bytes → Size class 2 → Block of 24 bytes       │
│  Request 513 bytes → System malloc (too large)             │
│                                                             │
└────────────────────────────────────────────────────────────┘
```

### Size Class Calculation

```python
# How Python calculates size class
def size_to_class(size):
    """Calculate size class index for a given size."""
    if size <= 0:
        return 0
    return (size - 1) // 8

# Examples
print(size_to_class(7))    # 0 → 8-byte block
print(size_to_class(8))    # 0 → 8-byte block
print(size_to_class(9))    # 1 → 16-byte block
print(size_to_class(512))  # 63 → 512-byte block
```

## 19.3 Pool Allocation Strategy

### Pool States

```
┌─────────────────────────────────────────────────────────────────┐
│                       Pool States                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐           │
│  │   EMPTY     │   │   USED      │   │   FULL      │           │
│  │  (no blocks │   │ (some free  │   │  (no free   │           │
│  │  allocated) │   │  blocks)    │   │   blocks)   │           │
│  └──────┬──────┘   └──────┬──────┘   └──────┬──────┘           │
│         │                 │                 │                    │
│         ▼                 ▼                 ▼                    │
│    Can be reused    In "usedpools"    Removed from              │
│    for different    list for size     usedpools list            │
│    size class       class                                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Pool Allocation

```c
// Simplified pool structure
struct pool_header {
    union { block *_padding;
            uint count; } ref;          // Block count
    block *freeblock;                    // First free block
    struct pool_header *nextpool;        // Next pool
    struct pool_header *prevpool;        // Previous pool
    uint arenaindex;                     // Arena this pool belongs to
    uint szidx;                          // Size class index
    uint nextoffset;                     // Next block offset
    uint maxnextoffset;                  // Max offset
};
```

### Pool Lists (usedpools)

```
┌─────────────────────────────────────────────────────────────────┐
│                       usedpools Array                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Index 0 (8 bytes):   Pool ←→ Pool ←→ Pool                      │
│  Index 1 (16 bytes):  Pool ←→ Pool                              │
│  Index 2 (24 bytes):  Pool                                       │
│  Index 3 (32 bytes):  (empty)                                    │
│  ...                                                             │
│  Index 63 (512 bytes): Pool ←→ Pool ←→ Pool                     │
│                                                                  │
│  Each entry is head of doubly-linked list of partially-used     │
│  pools for that size class.                                      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 19.4 Arena Management

### Arena Structure

```c
// Simplified arena structure
struct arena_object {
    uintptr_t address;           // Arena memory address
    block* pool_address;         // First pool's address
    uint nfreepools;             // Number of free pools
    uint ntotalpools;            // Total pools (64)
    struct pool_header* freepools;  // List of free pools
    struct arena_object* nextarena; // Linked list
    struct arena_object* prevarena;
};
```

### Arena Lifecycle

```
┌─────────────────────────────────────────────────────────────────┐
│                       Arena Lifecycle                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Allocation needed, no pools available                        │
│     │                                                            │
│     ▼                                                            │
│  2. Check for arena with free pools                              │
│     │                                                            │
│     ├── Found: Use existing arena                                │
│     │                                                            │
│     └── Not found: Allocate new arena (256 KB from system)      │
│                                                                  │
│  3. Arena is fully used (all pools allocated)                    │
│     │                                                            │
│     ▼                                                            │
│  4. Objects deallocated, pools become free                       │
│     │                                                            │
│     ▼                                                            │
│  5. When arena has all pools free:                               │
│     - Arena can be released to system (mmap)                     │
│     - Or kept for future use                                     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 19.5 Memory Fragmentation

### Internal Fragmentation

```python
import sys

# Request 17 bytes, get 24-byte block
# Internal fragmentation: 7 bytes wasted

obj = object()  # Approximately 16 bytes
print(sys.getsizeof(obj))  # Actual size

# The allocator rounds up to size class
# Wasted space = block_size - actual_size
```

### External Fragmentation

```
┌─────────────────────────────────────────────────────────────────┐
│                   External Fragmentation                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Pool (partially used, cannot be reused for different size):    │
│  ┌────┬────┬────┬────┬────┬────┬────┬────┐                     │
│  │USED│free│USED│free│free│USED│free│USED│                     │
│  └────┴────┴────┴────┴────┴────┴────┴────┘                     │
│        ▲         ▲    ▲         ▲                               │
│        └─────────┴────┴─────────┘                               │
│              Free blocks scattered                               │
│                                                                  │
│  pymalloc maintains free list within pool to find free blocks   │
│  quickly, but the pool cannot be returned to the system until   │
│  ALL blocks are free.                                            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Mitigating Fragmentation

```python
# pymalloc strategies:
# 1. Size classes reduce internal fragmentation
# 2. Free lists enable quick reuse
# 3. Arena-based allocation improves locality

# Application strategies:
# 1. Reuse objects instead of creating/destroying
# 2. Use object pools for frequent allocations
# 3. Process data in batches
```

## 19.6 `PYTHONMALLOC` Environment Variable

Control allocator behavior:

```bash
# Use default allocator
export PYTHONMALLOC=default

# Use system malloc (disable pymalloc)
export PYTHONMALLOC=malloc

# Use debug allocator
export PYTHONMALLOC=debug
# Adds: check buffer overflows, use-after-free

# Use malloc with debug
export PYTHONMALLOC=malloc_debug

# Use pymalloc with debug
export PYTHONMALLOC=pymalloc_debug
```

### Debug Allocator Features

```python
# Debug allocator detects:
# 1. Buffer overflows (writing beyond allocated size)
# 2. Use after free
# 3. Memory leaks (with tracemalloc)
# 4. Double free

# Enable with PYTHONMALLOC=debug
# Adds padding and patterns to detect corruption

# Pattern bytes:
# 0xFD: "Forbidden" - padding around allocations
# 0xCD: "Clean" - freshly allocated memory
# 0xDD: "Dead" - freed memory
```

## 19.7 Debug Allocators

### Using Debug Mode

```bash
# Run with debug allocator
PYTHONMALLOC=debug python script.py

# Also enable tracemalloc
PYTHONMALLOC=debug PYTHONTRACEMALLOC=1 python script.py
```

### Debug Statistics

```python
# In debug build, get allocation statistics
import sys

# This only works in debug builds
try:
    sys._debugmallocstats()
except AttributeError:
    print("Not available in release build")
```

### Example Debug Output

```
Small block threshold = 512, in 64 size classes.

class   size   num pools   blocks in use  avail blocks
-----   ----   ---------   -------------  ------------
    0      8           1              62           442
    1     16          10            1847           673
    2     24          23            3711           153
   ...

# Arenas allocated total           =                   28
# Arenas reclaimed                 =                    3
# Arenas highwater mark            =                   25
# Arenas allocated current         =                   25
```

## Summary

- **pymalloc** optimizes allocations ≤512 bytes
- Three-level hierarchy: **Arena → Pool → Block**
- **Size classes** in 8-byte increments (8, 16, ..., 512)
- **Pools** dedicated to one size class
- **Arenas** (256 KB) manage groups of pools
- **usedpools** array tracks partially-used pools
- **PYTHONMALLOC** controls allocator selection
- **Debug allocators** detect memory corruption

## Practice Exercises

1. Calculate which size class different objects use
2. Run Python with `PYTHONMALLOC=debug` and observe behavior
3. Use `sys._debugmallocstats()` (debug build) to see pool usage
4. Measure memory usage patterns in a real application

---

[← Previous: Memory Architecture](chapter-18-memory-architecture.md) | [Next: Reference Counting →](chapter-20-reference-counting.md)

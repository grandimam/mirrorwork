# Chapter 43: Copy-and-Patch Technique

## 43.1 Understanding Copy-and-Patch

Copy-and-patch is a fast code generation technique:

```
┌─────────────────────────────────────────────────────────────────┐
│              Copy-and-Patch Concept                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Traditional JIT:                                                │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Bytecode                                                │    │
│  │      │                                                   │    │
│  │      ▼                                                   │    │
│  │  Parse/Analyze                                           │    │
│  │      │                                                   │    │
│  │      ▼                                                   │    │
│  │  Generate IR                                             │    │
│  │      │                                                   │    │
│  │      ▼                                                   │    │
│  │  Optimize IR                                             │    │
│  │      │                                                   │    │
│  │      ▼                                                   │    │
│  │  Register Allocation                                     │    │
│  │      │                                                   │    │
│  │      ▼                                                   │    │
│  │  Emit Machine Code    ← Complex, slow                   │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Copy-and-Patch:                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Bytecode                                                │    │
│  │      │                                                   │    │
│  │      ▼                                                   │    │
│  │  Lookup Template                                         │    │
│  │      │                                                   │    │
│  │      ▼                                                   │    │
│  │  Copy Template + Patch Holes  ← Simple, fast            │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 43.2 Template Generation (Build Time)

### How Templates Are Created

```c
// At Python build time, templates are generated using Clang

// 1. Write instruction implementation in C
void template_LOAD_FAST(JITFrame *frame, int oparg) {
    PyObject *value = frame->localsplus[oparg];
    Py_INCREF(value);
    PUSH(value);
}

// 2. Compile with special flags to produce relocatable code
// clang -c template.c -o template.o -fno-omit-frame-pointer -fPIC

// 3. Extract machine code with relocation info
// The "holes" (relocations) are where runtime values go

// Generated template (x86-64, simplified):
// mov rax, [rbx + HOLE_1]    # rbx = frame, HOLE_1 = oparg * 8
// inc qword ptr [rax]        # Py_INCREF
// push rax                   # PUSH
```

### Template Structure

```c
// Template metadata structure
typedef struct {
    const uint8_t *code;      // Template machine code
    size_t code_size;         // Size in bytes
    size_t num_holes;         // Number of relocations

    struct {
        size_t offset;        // Where in template
        int kind;             // What kind of patch
        const char *symbol;   // Symbol name (if needed)
    } holes[];
} JITTemplate;

// Example template
static const JITTemplate load_fast_template = {
    .code = (uint8_t[]){
        0x48, 0x8b, 0x43, 0x00,  // mov rax, [rbx + 0]  <- HOLE
        0xff, 0x00,              // inc dword ptr [rax]
        0x50,                    // push rax
    },
    .code_size = 7,
    .num_holes = 1,
    .holes = {
        { .offset = 3, .kind = HOLE_i8, .symbol = "oparg_offset" }
    }
};
```

## 43.3 Patching at Runtime

### The Patching Process

```c
// Runtime: compile a sequence of bytecode instructions
uint8_t* jit_compile(PyCodeObject *code, int start, int end) {
    // Allocate executable memory
    size_t total_size = estimate_size(code, start, end);
    uint8_t *buffer = allocate_executable(total_size);

    uint8_t *ptr = buffer;

    // For each bytecode instruction
    for (int i = start; i < end; i++) {
        uint8_t opcode = code->co_code[i * 2];
        uint8_t oparg = code->co_code[i * 2 + 1];

        // Get the template
        const JITTemplate *tmpl = get_template(opcode);

        // Copy template
        memcpy(ptr, tmpl->code, tmpl->code_size);

        // Patch holes
        for (int j = 0; j < tmpl->num_holes; j++) {
            patch_hole(ptr, &tmpl->holes[j], oparg, code);
        }

        ptr += tmpl->code_size;
    }

    // Make executable (remove write permission)
    protect_executable(buffer, total_size);

    return buffer;
}

// Patch a single hole
void patch_hole(uint8_t *code, Hole *hole, int oparg, PyCodeObject *co) {
    switch (hole->kind) {
        case HOLE_i8:
            // 8-bit immediate
            code[hole->offset] = oparg * sizeof(PyObject*);
            break;

        case HOLE_i32:
            // 32-bit immediate
            *(int32_t*)(code + hole->offset) = oparg * sizeof(PyObject*);
            break;

        case HOLE_addr:
            // 64-bit address
            *(uint64_t*)(code + hole->offset) = (uint64_t)get_address(hole->symbol);
            break;

        case HOLE_reloc:
            // Relative address (for calls)
            int64_t target = (int64_t)get_address(hole->symbol);
            int64_t from = (int64_t)(code + hole->offset + 4);
            *(int32_t*)(code + hole->offset) = target - from;
            break;
    }
}
```

## 43.4 Example: BINARY_ADD Template

### Template Code Generation

```c
// C implementation for template
void template_BINARY_ADD_INT(JITFrame *frame) {
    PyObject *right = POP();
    PyObject *left = TOP();

    // Fast path for small integers
    if (PyLong_CheckExact(left) && PyLong_CheckExact(right)) {
        // Check for overflow
        long a = ((PyLongObject*)left)->ob_digit[0];
        long b = ((PyLongObject*)right)->ob_digit[0];

        // Signs
        int sign_a = Py_SIZE(left);
        int sign_b = Py_SIZE(right);

        if (sign_a == 1 && sign_b == 1) {
            // Both positive single-digit
            long result = a + b;
            if (result < PyLong_BASE) {
                // No overflow - fast path
                PyObject *res = PyLong_FromLong(result);
                SET_TOP(res);
                Py_DECREF(left);
                Py_DECREF(right);
                return;
            }
        }
    }

    // Slow path - call generic function
    DEOPTIMIZE();
}
```

### Generated Machine Code (x86-64)

```asm
; BINARY_ADD_INT template (simplified)
template_binary_add_int:
    ; Pop right operand
    mov     rax, [rsp]           ; right = TOP()
    add     rsp, 8               ; POP()

    ; Load left operand
    mov     rcx, [rsp]           ; left = TOP()

    ; Type checks
    mov     rdx, [rax]           ; right->ob_type
    cmp     rdx, HOLE_PyLong_Type  ; Compare with PyLong_Type
    jne     .deopt

    mov     rdx, [rcx]           ; left->ob_type
    cmp     rdx, HOLE_PyLong_Type
    jne     .deopt

    ; Check for single-digit positive
    mov     esi, [rax + 16]      ; Py_SIZE(right)
    cmp     esi, 1
    jne     .deopt

    mov     edi, [rcx + 16]      ; Py_SIZE(left)
    cmp     edi, 1
    jne     .deopt

    ; Load digits
    mov     rsi, [rax + 24]      ; right->ob_digit[0]
    mov     rdi, [rcx + 24]      ; left->ob_digit[0]

    ; Add
    add     rdi, rsi
    cmp     rdi, 0x3FFFFFFF      ; Check overflow (30-bit)
    jae     .deopt

    ; Create result (inline small int cache)
    ; ... allocate or get cached int ...

    ; Decref operands
    ; ...

    ret

.deopt:
    ; Return to interpreter
    mov     rax, HOLE_deopt_addr
    jmp     rax
```

## 43.5 Handling Complex Instructions

### Instructions with Multiple Templates

```c
// Some instructions have multiple specialized templates

// CALL instruction variants:
JITTemplate* get_call_template(int opcode, CallSite *site) {
    switch (opcode) {
        case CALL_PY_EXACT_ARGS:
            // Python function with exact argument count
            return &call_py_exact_template;

        case CALL_BUILTIN_O:
            // Built-in function with single argument
            return &call_builtin_o_template;

        case CALL_BUILTIN_FAST:
            // Built-in function with METH_FASTCALL
            return &call_builtin_fast_template;

        case CALL_METHOD_DESCRIPTOR_O:
            // Method descriptor with single argument
            return &call_method_o_template;

        default:
            // Generic call
            return &call_generic_template;
    }
}
```

### Inline Caching in Templates

```c
// Template with inline cache
void template_LOAD_ATTR_cached(JITFrame *frame, int oparg) {
    PyObject *owner = TOP();

    // Inline cache: expected type and offset
    PyTypeObject *cached_type = HOLE_cached_type;
    Py_ssize_t cached_offset = HOLE_cached_offset;

    // Quick type check
    if (Py_TYPE(owner) == cached_type) {
        // Fast path: direct attribute access
        PyObject *value = *(PyObject**)((char*)owner + cached_offset);
        Py_INCREF(value);
        SET_TOP(value);
        Py_DECREF(owner);
        return;
    }

    // Cache miss - deoptimize
    DEOPTIMIZE();
}
```

## 43.6 Memory Management for JIT Code

### Executable Memory Allocation

```c
#include <sys/mman.h>

// Allocate memory that can be made executable
void* allocate_executable(size_t size) {
    // Allocate with read/write permissions
    void *mem = mmap(
        NULL,
        size,
        PROT_READ | PROT_WRITE,
        MAP_PRIVATE | MAP_ANONYMOUS,
        -1,
        0
    );

    if (mem == MAP_FAILED) {
        return NULL;
    }

    return mem;
}

// Make memory executable (remove write permission)
void protect_executable(void *mem, size_t size) {
    // W^X: Memory is either writable or executable, never both
    mprotect(mem, size, PROT_READ | PROT_EXEC);
}

// Free JIT code memory
void free_executable(void *mem, size_t size) {
    munmap(mem, size);
}
```

### Code Cache Management

```c
// JIT code cache
typedef struct {
    PyCodeObject *py_code;    // Source code object
    void *jit_code;           // JIT-compiled code
    size_t code_size;         // Size of JIT code
    int entry_offset;         // Offset of entry point
    int valid;                // Is this cache entry valid?
} JITCacheEntry;

#define JIT_CACHE_SIZE 1024
static JITCacheEntry jit_cache[JIT_CACHE_SIZE];

// Invalidate cache when code changes
void jit_invalidate(PyCodeObject *code) {
    int index = hash_code(code) % JIT_CACHE_SIZE;
    JITCacheEntry *entry = &jit_cache[index];

    if (entry->py_code == code && entry->valid) {
        entry->valid = 0;
        free_executable(entry->jit_code, entry->code_size);
        entry->jit_code = NULL;
    }
}
```

## 43.7 Advantages and Trade-offs

### Advantages of Copy-and-Patch

```
┌─────────────────────────────────────────────────────────────────┐
│              Copy-and-Patch Advantages                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Very Fast Compilation                                        │
│     • No IR generation                                           │
│     • No optimization passes                                     │
│     • Just memcpy + patch                                        │
│     • ~100x faster than LLVM                                    │
│                                                                  │
│  2. High-Quality Templates                                       │
│     • Templates compiled by production compiler (Clang)         │
│     • Full compiler optimizations at build time                 │
│     • Register allocation done once                              │
│                                                                  │
│  3. Simple Implementation                                        │
│     • No complex JIT infrastructure                             │
│     • Easier to maintain                                         │
│     • Less code to audit for security                           │
│                                                                  │
│  4. Predictable Performance                                      │
│     • No compilation pauses                                      │
│     • Consistent behavior                                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Trade-offs

```
┌─────────────────────────────────────────────────────────────────┐
│              Copy-and-Patch Trade-offs                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. No Cross-Instruction Optimization                            │
│     • Can't optimize across instruction boundaries              │
│     • No constant folding of runtime values                     │
│     • No dead code elimination                                   │
│                                                                  │
│  2. Template Explosion                                           │
│     • Many instruction variants need templates                  │
│     • Binary size increases                                      │
│                                                                  │
│  3. Limited Adaptivity                                           │
│     • Can't adapt to specific runtime patterns                  │
│     • Fixed template code                                        │
│                                                                  │
│  4. Platform-Specific Templates                                  │
│     • Need separate templates per architecture                  │
│     • Build complexity                                           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 43.8 Comparison with Other JIT Techniques

### Method-Based vs Tracing JIT

```
┌─────────────────────────────────────────────────────────────────┐
│              JIT Technique Comparison                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Copy-and-Patch (CPython 3.13):                                  │
│  • Unit: Single instruction                                      │
│  • Optimization: Per-instruction only                           │
│  • Compile time: Microseconds                                   │
│  • Code quality: Good (template quality)                        │
│                                                                  │
│  Method-Based JIT (V8, HotSpot):                                │
│  • Unit: Entire function/method                                 │
│  • Optimization: Inlining, constant prop, etc.                 │
│  • Compile time: Milliseconds                                   │
│  • Code quality: Excellent                                       │
│                                                                  │
│  Tracing JIT (PyPy, LuaJIT):                                    │
│  • Unit: Hot execution traces                                   │
│  • Optimization: Loop-focused, speculative                     │
│  • Compile time: Milliseconds                                   │
│  • Code quality: Excellent for traces                           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 43.9 Building Templates

### Template Build Process

```makefile
# Build process for templates

# 1. Compile template C code
templates.o: templates.c
    $(CC) -c templates.c -o templates.o \
        -fno-omit-frame-pointer \
        -fPIC \
        -O2

# 2. Extract template bytes and relocations
templates.h: templates.o extract_templates.py
    python extract_templates.py templates.o > templates.h

# 3. Include in Python build
Python/jit.o: Python/jit.c templates.h
    $(CC) -c Python/jit.c -o Python/jit.o
```

### Template Extraction

```python
# extract_templates.py
import struct
from elftools.elf.elffile import ELFFile

def extract_template(elf, symbol_name):
    """Extract machine code and relocations for a template."""

    # Find the symbol
    symtab = elf.get_section_by_name('.symtab')
    symbol = None
    for sym in symtab.iter_symbols():
        if sym.name == symbol_name:
            symbol = sym
            break

    if symbol is None:
        raise ValueError(f"Symbol {symbol_name} not found")

    # Get the code section
    section = elf.get_section(symbol['st_shndx'])
    offset = symbol['st_value'] - section['sh_addr']
    size = symbol['st_size']

    code = section.data()[offset:offset + size]

    # Find relocations
    rela_section = elf.get_section_by_name('.rela.text')
    holes = []

    for rela in rela_section.iter_relocations():
        if offset <= rela['r_offset'] < offset + size:
            holes.append({
                'offset': rela['r_offset'] - offset,
                'type': rela['r_info_type'],
                'symbol': symtab.get_symbol(rela['r_info_sym']).name
            })

    return code, holes
```

## Summary

- **Copy-and-patch** pre-compiles instruction templates at build time
- **Runtime compilation** is just memcpy + patching holes
- **Very fast** compile time (microseconds)
- **Templates** are optimized by production compilers
- **Trade-off**: No cross-instruction optimization
- **Good fit** for CPython's goals (fast compile, good enough code)

## Practice Exercises

1. Examine template generation with objdump
2. Trace the JIT compilation path in CPython source
3. Compare template sizes across architectures
4. Measure JIT compilation time overhead

---

[← Previous: JIT Overview](chapter-42-jit-overview.md) | [Next: JIT Tier System →](chapter-44-jit-tiers.md)

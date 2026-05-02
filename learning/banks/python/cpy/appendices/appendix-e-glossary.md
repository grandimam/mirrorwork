# Appendix E: Glossary

## A

**Adaptive Specialization**
: The process by which CPython 3.11+ dynamically replaces generic bytecode instructions with specialized versions based on observed runtime types.

**Arena**
: A 256KB block of memory managed by pymalloc, divided into pools for efficient small object allocation.

**AST (Abstract Syntax Tree)**
: Tree representation of Python source code structure, created by the parser and transformed into bytecode.

**Atomic Operation**
: An operation that completes in a single step from the perspective of other threads, without possibility of interruption.

## B

**Biased Reference Counting**
: PEP 703 technique where objects have thread-local reference counts for the "owner" thread, reducing atomic operations.

**Block**
: In pymalloc, a fixed-size unit of memory within a pool. Blocks range from 8 to 512 bytes.

**Bytecode**
: The low-level instructions executed by the Python Virtual Machine, compiled from source code.

## C

**C API**
: The interface for writing C extensions or embedding Python in C applications.

**CFG (Control Flow Graph)**
: Graph representation of all possible execution paths through bytecode, used for optimization.

**Closure**
: A function that captures variables from its enclosing scope.

**Code Object**
: Python object containing compiled bytecode and metadata (constants, variable names, etc.).

**Copy-and-Patch**
: JIT compilation technique used in Python 3.13+ that copies pre-compiled code templates and patches in dynamic values.

**CPython**
: The reference implementation of Python, written in C.

## D

**Deferred Reference Counting**
: PEP 703 optimization that delays reference count updates to reduce overhead.

**Descriptor**
: Object that defines `__get__`, `__set__`, or `__delete__` methods, controlling attribute access.

## E

**Evaluation Stack**
: The stack data structure used by the PVM to hold intermediate values during bytecode execution.

**Event Loop**
: The core of asyncio that manages and dispatches coroutines and callbacks.

## F

**Finalizer**
: Method (`__del__`) called when an object is about to be destroyed.

**Frame Object**
: Python object representing a single execution context (function call), containing local variables and execution state.

**Free-Threading**
: Python execution without the Global Interpreter Lock, allowing true parallelism (PEP 703).

**Free Variables**
: Variables used in a function but defined in an enclosing scope (closures).

## G

**Garbage Collection (GC)**
: Automatic memory management that reclaims memory from unreachable objects. Python uses reference counting plus cyclic GC.

**Generation**
: In generational GC, a group of objects based on survival time. Python has 3 generations (0, 1, 2).

**GIL (Global Interpreter Lock)**
: Mutex that prevents multiple threads from executing Python bytecode simultaneously in CPython.

## H

**Heap**
: Memory region for dynamically allocated objects.

## I

**Immortal Objects**
: Objects in PEP 703/Python 3.12+ that are never deallocated and skip reference counting entirely (e.g., `None`, `True`, `False`).

**Import Hook**
: Custom finder or loader that extends Python's import machinery.

**Interpreter**
: The component that executes bytecode instructions.

## J

**JIT (Just-In-Time) Compilation**
: Compiling code to machine instructions at runtime. Python 3.13+ includes experimental JIT.

## K

**Keyword-Only Arguments**
: Function arguments that must be passed by name, appearing after `*` in the function signature.

## L

**Lexer (Tokenizer)**
: Component that breaks source code into tokens.

**Loader**
: Import system component responsible for loading module code.

**Locals**
: Variables defined within the current scope, stored efficiently in frame's `f_locals`.

## M

**Meta Path**
: List of import finders (`sys.meta_path`) consulted when importing modules.

**Metaclass**
: Class whose instances are themselves classes. Controls class creation.

**MRO (Method Resolution Order)**
: Order in which base classes are searched for methods, using C3 linearization.

**Mutex**
: Mutual exclusion lock preventing concurrent access to shared resources.

## N

**Namespace**
: Mapping from names to objects (e.g., local, global, builtin namespaces).

## O

**Object Model**
: The system of types, objects, and their relationships in Python.

**Opcode**
: Operation code - the numeric identifier for a bytecode instruction.

## P

**Parser**
: Component that builds AST from tokens.

**Per-Interpreter GIL**
: Python 3.12+ feature allowing each subinterpreter to have its own GIL.

**Pool**
: In pymalloc, a 4KB chunk of memory containing fixed-size blocks.

**PyMalloc**
: CPython's specialized memory allocator for small objects.

**PyObject**
: C structure that forms the base of all Python objects.

**PVM (Python Virtual Machine)**
: The component that executes Python bytecode.

## Q

**Quickening**
: Process in Python 3.11+ where bytecode is dynamically specialized based on runtime types.

## R

**Reference Counting**
: Memory management technique tracking how many references point to each object.

**Reference Cycle**
: Circular chain of object references that prevents automatic deallocation.

**Refcount**
: The `ob_refcnt` field in PyObject tracking reference count.

## S

**Slot**
: Pre-allocated attribute storage (`__slots__`) that avoids per-instance dictionary.

**Specialization**
: Optimizing generic bytecode for specific types (e.g., `BINARY_ADD` → `BINARY_ADD_INT`).

**Stack Frame**
: See Frame Object.

**Subinterpreter**
: Separate Python interpreter instance within the same process.

**Switch Interval**
: Time between GIL release checks (default 5ms), set via `sys.setswitchinterval()`.

## T

**Thread State**
: (`PyThreadState`) C structure containing per-thread information for the interpreter.

**Tier**
: JIT compilation level (Tier 0 = interpreted, Tier 1 = basic JIT, Tier 2 = optimized).

**Trace Function**
: Function called for each bytecode execution event, set via `sys.settrace()`.

**Tracing JIT**
: JIT technique that records and compiles frequently executed code paths.

## U

**Uop (Micro-op)**
: Low-level operation used in Python 3.13+ JIT, simpler than bytecode.

## V

**Vectorcall**
: Optimized calling protocol (PEP 590) reducing overhead for function calls.

## W

**Weak Reference**
: Reference that doesn't prevent garbage collection, useful for caches.

**Word-code**
: Python 3.6+ bytecode format using 16-bit words (opcode + arg).

## Common Acronyms

| Acronym | Full Form |
|---------|-----------|
| ABI | Application Binary Interface |
| API | Application Programming Interface |
| AST | Abstract Syntax Tree |
| CFG | Control Flow Graph |
| GC | Garbage Collection/Collector |
| GIL | Global Interpreter Lock |
| JIT | Just-In-Time (compilation) |
| MRO | Method Resolution Order |
| PEP | Python Enhancement Proposal |
| PVM | Python Virtual Machine |
| REPL | Read-Eval-Print Loop |
| SSA | Static Single Assignment |

---

[Back to Main Index →](../README.md)

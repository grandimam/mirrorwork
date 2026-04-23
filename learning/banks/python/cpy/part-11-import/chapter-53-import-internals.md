# Chapter 53: Import Internals

## 53.1 The Import Machinery

Deep dive into how imports work internally:

```
┌─────────────────────────────────────────────────────────────────┐
│              Import Machinery Layers                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Python Level:                                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  import foo                                              │    │
│  │      ↓                                                   │    │
│  │  builtins.__import__(name, globals, locals, fromlist)   │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  importlib Level:                                                │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  importlib._bootstrap._find_and_load()                  │    │
│  │      ↓                                                   │    │
│  │  _find_and_load_unlocked()                              │    │
│  │      ↓                                                   │    │
│  │  _find_spec() → _load_unlocked()                        │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  C Level:                                                        │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  PyImport_ImportModuleLevelObject()                     │    │
│  │      ↓                                                   │    │
│  │  import_find_and_load()                                 │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 53.2 The __import__ Function

### Implementation

```c
// Python/bltinmodule.c
static PyObject *
builtin___import__(PyObject *self, PyObject *args, PyObject *kwds)
{
    PyObject *name, *globals = NULL, *locals = NULL;
    PyObject *fromlist = NULL;
    int level = 0;

    // Parse arguments
    if (!PyArg_ParseTupleAndKeywords(args, kwds, "U|OOOi:__import__",
            &name, &globals, &locals, &fromlist, &level))
        return NULL;

    // Call the actual import implementation
    return PyImport_ImportModuleLevelObject(
        name, globals, locals, fromlist, level);
}
```

### The Parameters

```python
# __import__(name, globals, locals, fromlist, level)

# name: module name string
# globals: calling module's globals (for __package__)
# locals: unused (for future)
# fromlist: tuple of names for "from X import a, b"
# level: 0 = absolute, 1 = current package, 2 = parent, etc.

# Examples:
__import__('json')  # Absolute import
__import__('json', fromlist=['loads'])  # from json import loads
__import__('.sub', globals(), level=1)  # Relative import
```

## 53.3 Import Lock

### Thread Safety

```c
// Import lock protects the import machinery
// Python/import.c

static PyThread_type_lock import_lock = NULL;
static unsigned long import_lock_thread = PYTHREAD_INVALID_THREAD_ID;
static int import_lock_level = 0;

// Acquire the import lock
void
_PyImport_AcquireLock(void)
{
    unsigned long me = PyThread_get_thread_ident();
    if (me == import_lock_thread) {
        // Already holding lock, just increment level
        import_lock_level++;
        return;
    }

    // Wait for lock
    PyThread_acquire_lock(import_lock, 1);
    import_lock_thread = me;
    import_lock_level = 1;
}

void
_PyImport_ReleaseLock(void)
{
    import_lock_level--;
    if (import_lock_level == 0) {
        import_lock_thread = PYTHREAD_INVALID_THREAD_ID;
        PyThread_release_lock(import_lock);
    }
}
```

### Deadlock Prevention

```python
# The import lock is reentrant to prevent deadlocks
# during module initialization

# module_a.py
import module_b  # Acquires lock

# module_b.py
import module_a  # Same thread, lock count increases

# Without reentrancy, this would deadlock
```

## 53.4 Module Caching

### sys.modules Implementation

```c
// sys.modules is a regular dict
// Python/pystate.c

PyObject *
PyImport_GetModuleDict(void)
{
    PyInterpreterState *interp = PyInterpreterState_Get();
    return interp->modules;  // Returns sys.modules
}

// Check cache during import
PyObject *
PyImport_GetModule(PyObject *name)
{
    PyObject *modules = PyImport_GetModuleDict();
    return PyDict_GetItemWithError(modules, name);
}
```

### Cache Behavior

```python
import sys

# Import populates cache
import json
assert 'json' in sys.modules

# Subsequent imports return cached module
json2 = __import__('json')
assert json is json2

# Partial initialization handling
# During import, module is added to cache BEFORE execution
# This allows circular imports to partially work

# Example:
# module_a starts importing
# sys.modules['module_a'] = <partially initialized>
# module_a imports module_b
# module_b imports module_a
# module_b gets partially initialized module_a
# Both finish initialization
```

## 53.5 Bytecode Caching (.pyc Files)

### Cache Location

```
__pycache__/
├── module.cpython-311.pyc    # Python 3.11
├── module.cpython-310.pyc    # Python 3.10
└── module.cpython-39.pyc     # Python 3.9
```

### .pyc File Format

```python
import struct
import marshal

def read_pyc(path):
    with open(path, 'rb') as f:
        # Magic number (4 bytes) - Python version
        magic = f.read(4)

        # Bit field (4 bytes) - Python 3.7+
        bit_field = struct.unpack('<I', f.read(4))[0]

        # If hash-based (PEP 552):
        if bit_field & 0x01:
            source_hash = f.read(8)
        else:
            # Timestamp-based
            timestamp = struct.unpack('<I', f.read(4))[0]
            source_size = struct.unpack('<I', f.read(4))[0]

        # Code object
        code = marshal.load(f)

    return code
```

### Cache Invalidation

```python
import importlib.util

# Check if source has changed
def is_cache_valid(source_path, cache_path):
    source_stat = os.stat(source_path)
    cache_stat = os.stat(cache_path)

    # Read cache header
    with open(cache_path, 'rb') as f:
        magic = f.read(4)
        bit_field = struct.unpack('<I', f.read(4))[0]

        if bit_field & 0x01:
            # Hash-based
            stored_hash = f.read(8)
            with open(source_path, 'rb') as src:
                actual_hash = hashlib.sha256(src.read()).digest()[:8]
            return stored_hash == actual_hash
        else:
            # Timestamp-based
            stored_mtime = struct.unpack('<I', f.read(4))[0]
            stored_size = struct.unpack('<I', f.read(4))[0]
            return (stored_mtime == int(source_stat.st_mtime) and
                    stored_size == source_stat.st_size)
```

## 53.6 The Import Machinery Bootstrap

### Frozen Bootstrap

```python
# importlib._bootstrap is "frozen" (pre-compiled into Python)
# It can't import other modules during its initialization

# Bootstrap process:
# 1. _frozen_importlib is executed (bootstrap)
# 2. sys.modules is created
# 3. builtins module is created
# 4. sys module is created
# 5. importlib is properly initialized
# 6. External imports now work
```

### importlib._bootstrap Structure

```python
# Key functions in _bootstrap.py:

def _find_and_load(name, import_):
    """Find and load a module, managing the import lock."""
    with _ModuleLockManager(name):
        return _find_and_load_unlocked(name, import_)

def _find_and_load_unlocked(name, import_):
    """Core import logic."""
    # Check cache
    module = sys.modules.get(name)
    if module is not None:
        return module

    # Find the module
    parent = name.rpartition('.')[0]
    if parent:
        parent_module = import_(parent)
        path = parent_module.__path__
    else:
        path = None

    spec = _find_spec(name, path)
    if spec is None:
        raise ModuleNotFoundError(name)

    # Load the module
    module = _load_unlocked(spec)
    return module
```

## 53.7 Module Spec Internals

### ModuleSpec Structure

```python
class ModuleSpec:
    def __init__(self, name, loader, *, origin=None, loader_state=None,
                 is_package=None):
        self.name = name
        self.loader = loader
        self.origin = origin
        self.loader_state = loader_state
        self.submodule_search_locations = [] if is_package else None

        # Derived attributes
        self._cached = None
        self._initializing = False

    @property
    def cached(self):
        if self._cached is None:
            if self.origin is not None:
                self._cached = _get_cached(self.origin)
        return self._cached

    @property
    def parent(self):
        if self.submodule_search_locations is None:
            return self.name.rpartition('.')[0]
        else:
            return self.name

    @property
    def has_location(self):
        return self.origin is not None
```

### Creating Modules from Specs

```python
def module_from_spec(spec):
    """Create a module based on the provided spec."""
    module = None

    if hasattr(spec.loader, 'create_module'):
        module = spec.loader.create_module(spec)

    if module is None:
        module = types.ModuleType(spec.name)

    # Set module attributes from spec
    module.__name__ = spec.name
    module.__loader__ = spec.loader
    module.__package__ = spec.parent
    module.__spec__ = spec

    if spec.origin is not None:
        module.__file__ = spec.origin

    if spec.cached is not None:
        module.__cached__ = spec.cached

    if spec.submodule_search_locations is not None:
        module.__path__ = spec.submodule_search_locations

    return module
```

## 53.8 Import Hooks Deep Dive

### Hook Installation Order

```python
import sys

# Meta path finders (sys.meta_path)
# Checked in order for EVERY import

# 1. BuiltinImporter - handles built-in modules
# 2. FrozenImporter - handles frozen modules
# 3. PathFinder - handles sys.path

# Path hooks (sys.path_hooks)
# Used by PathFinder for each sys.path entry

# Path importer cache (sys.path_importer_cache)
# Caches PathEntryFinder for each path entry
```

### Implementing Complete Hook

```python
import sys
import importlib.abc
import importlib.machinery
import importlib.util

class FullFeaturedFinder(importlib.abc.MetaPathFinder):
    """Complete example of a meta path finder."""

    def __init__(self):
        self.module_cache = {}

    def find_spec(self, fullname, path, target=None):
        """
        Find a module spec.

        Args:
            fullname: Fully qualified module name
            path: Parent package's __path__ (or None)
            target: Module object for reload (or None)
        """
        # Check if we handle this module
        if not self._handles(fullname):
            return None

        # Get module source
        source = self._get_source(fullname)
        if source is None:
            return None

        # Determine if package
        is_package = self._is_package(fullname)

        # Create loader
        loader = FullFeaturedLoader(fullname, source)

        # Create spec
        spec = importlib.machinery.ModuleSpec(
            name=fullname,
            loader=loader,
            origin=self._get_origin(fullname),
            is_package=is_package,
        )

        if is_package:
            spec.submodule_search_locations = self._get_submodule_path(fullname)

        return spec

    def find_module(self, fullname, path=None):
        """Legacy method for Python < 3.4."""
        spec = self.find_spec(fullname, path)
        if spec is not None:
            return spec.loader
        return None

    def invalidate_caches(self):
        """Clear any cached data."""
        self.module_cache.clear()

class FullFeaturedLoader(importlib.abc.InspectLoader):
    """Complete example of a loader."""

    def __init__(self, fullname, source):
        self.fullname = fullname
        self.source = source

    def create_module(self, spec):
        """Create module object. Return None for default."""
        return None

    def exec_module(self, module):
        """Execute module code."""
        code = compile(self.source, module.__file__, 'exec')
        exec(code, module.__dict__)

    def get_code(self, fullname):
        """Return compiled code object."""
        source = self.get_source(fullname)
        return compile(source, self._get_filename(fullname), 'exec')

    def get_source(self, fullname):
        """Return source code as string."""
        return self.source

    def is_package(self, fullname):
        """Return True if module is a package."""
        return False
```

## 53.9 Reloading Modules

### importlib.reload()

```python
import importlib

# Reload a module
import mymodule
importlib.reload(mymodule)

# What reload does:
# 1. Re-executes module code
# 2. Uses SAME module object
# 3. Existing references still work
# 4. But may have stale references to old objects
```

### Reload Caveats

```python
# Objects defined before reload still exist
import mymodule

old_class = mymodule.MyClass
instance = old_class()

importlib.reload(mymodule)

# instance is still an old_class instance
# mymodule.MyClass is a NEW class
isinstance(instance, mymodule.MyClass)  # False!

# Functions and classes are replaced
old_func = mymodule.my_function
importlib.reload(mymodule)
old_func is mymodule.my_function  # False
```

## 53.10 Debugging Import Internals

### Verbose Mode

```python
import sys

# Enable verbose import
sys.flags.verbose = 1  # Read-only, use -v flag

# Or use environment variable
# PYTHONVERBOSE=1 python script.py
```

### Tracing Imports

```python
import sys

class ImportTracer:
    def __init__(self):
        self.depth = 0

    def find_spec(self, name, path, target=None):
        indent = "  " * self.depth
        print(f"{indent}Finding: {name}")
        self.depth += 1
        return None

    def __del__(self):
        self.depth -= 1

# Install tracer
sys.meta_path.insert(0, ImportTracer())
```

### Import Timings

```python
import importlib
import time

def timed_import(name):
    start = time.perf_counter()
    module = importlib.import_module(name)
    elapsed = time.perf_counter() - start
    print(f"Import {name}: {elapsed*1000:.2f}ms")
    return module

# Or use python -X importtime
# python -X importtime script.py
```

## Summary

- **__import__** is the core function called by import statements
- **Import lock** ensures thread safety during imports
- **sys.modules** caches all imported modules
- **Bytecode caching** uses `.pyc` files in `__pycache__`
- **Bootstrap** uses frozen modules to avoid circular dependencies
- **ModuleSpec** contains all metadata for loading
- **Reload** re-executes but keeps same module object

## Practice Exercises

1. Implement a custom bytecode caching system
2. Create an import tracer that logs timing information
3. Build a module that handles its own reload gracefully
4. Implement a finder that validates module signatures

---

[← Previous: Packages and Namespaces](chapter-52-packages-namespaces.md) | [Next: Exception Handling Internals →](../part-12-exceptions/chapter-54-exception-internals.md)

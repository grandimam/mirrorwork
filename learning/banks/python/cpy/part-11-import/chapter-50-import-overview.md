# Chapter 50: Import System Overview

## 50.1 The Import Statement

The `import` statement triggers a complex machinery:

```
┌─────────────────────────────────────────────────────────────────┐
│              Import Statement Flow                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  import foo                                                      │
│      │                                                          │
│      ▼                                                          │
│  1. Check sys.modules (cache)                                   │
│      │                                                          │
│      ├── Found → Return cached module                           │
│      │                                                          │
│      └── Not found → Continue                                   │
│              │                                                   │
│              ▼                                                   │
│  2. Find module spec (finders)                                  │
│      │                                                          │
│      ▼                                                          │
│  3. Load module (loaders)                                       │
│      │                                                          │
│      ▼                                                          │
│  4. Execute module code                                         │
│      │                                                          │
│      ▼                                                          │
│  5. Add to sys.modules                                          │
│      │                                                          │
│      ▼                                                          │
│  6. Bind name in importing module's namespace                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 50.2 Import Forms

### Different Import Syntaxes

```python
# Basic import
import foo                # Import module, bind as 'foo'
import foo.bar            # Import submodule, bind as 'foo'

# Import with alias
import foo as f           # Import module, bind as 'f'
import foo.bar as fb      # Import submodule, bind as 'fb'

# From import
from foo import bar       # Import attribute 'bar' from module 'foo'
from foo import bar, baz  # Import multiple attributes
from foo import *         # Import all public names

# From import with alias
from foo import bar as b  # Import attribute with alias

# Relative imports (in packages)
from . import bar         # Import from current package
from .. import baz        # Import from parent package
from .sub import qux      # Import from subpackage
```

### Bytecode Translation

```python
import dis

# import foo
dis.dis(compile("import foo", "<string>", "exec"))
# LOAD_CONST 0 (0)
# LOAD_CONST 1 (None)
# IMPORT_NAME 0 (foo)
# STORE_NAME 0 (foo)

# from foo import bar
dis.dis(compile("from foo import bar", "<string>", "exec"))
# LOAD_CONST 0 (0)
# LOAD_CONST 1 (('bar',))
# IMPORT_NAME 0 (foo)
# IMPORT_FROM 1 (bar)
# STORE_NAME 1 (bar)
# POP_TOP
```

## 50.3 sys.modules Cache

### The Module Cache

```python
import sys

# sys.modules is the central cache of all imported modules
print(type(sys.modules))  # <class 'dict'>
print(len(sys.modules))   # ~hundreds of modules

# Check if module is cached
if 'json' in sys.modules:
    print("json already imported")

# Get a cached module
json_module = sys.modules.get('json')

# Remove from cache (force reimport)
if 'mymodule' in sys.modules:
    del sys.modules['mymodule']
    import mymodule  # Reimported fresh
```

### Cache Manipulation

```python
import sys

# Pre-populate cache with custom module
class FakeModule:
    def hello(self):
        return "Hello from fake!"

sys.modules['fake_module'] = FakeModule()

# Now import works
import fake_module
print(fake_module.hello())  # "Hello from fake!"

# Caution: Modifying sys.modules can cause issues
# - Circular import problems
# - Inconsistent state
# - Memory leaks (modules never garbage collected)
```

## 50.4 The Import Protocol

### Finders and Loaders

```
┌─────────────────────────────────────────────────────────────────┐
│              Import Protocol Components                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Finder (find_spec):                                             │
│  • Locates a module by name                                     │
│  • Returns ModuleSpec or None                                   │
│  • Types: MetaPathFinder, PathEntryFinder                       │
│                                                                  │
│  Loader (exec_module):                                           │
│  • Creates module object                                        │
│  • Executes module code                                         │
│  • Populates module namespace                                   │
│                                                                  │
│  ModuleSpec:                                                     │
│  • Contains all info needed to load module                      │
│  • name, loader, origin, submodule_search_locations            │
│                                                                  │
│  Import Flow:                                                    │
│  sys.meta_path → find_spec() → ModuleSpec → loader.exec_module()│
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### sys.meta_path

```python
import sys

# Meta path finders (checked in order)
for finder in sys.meta_path:
    print(f"{finder.__class__.__name__}")

# Output:
# BuiltinImporter      - for built-in modules (sys, builtins)
# FrozenImporter       - for frozen modules
# PathFinder           - for file system modules

# Add custom finder (first in list = highest priority)
class MyFinder:
    @classmethod
    def find_spec(cls, name, path, target=None):
        print(f"Looking for: {name}")
        return None  # Not found, try next finder

sys.meta_path.insert(0, MyFinder)
```

## 50.5 ModuleSpec

### Understanding ModuleSpec

```python
import importlib.util

# Get spec for a module
spec = importlib.util.find_spec('json')

print(f"Name: {spec.name}")                    # json
print(f"Loader: {spec.loader}")                # SourceFileLoader
print(f"Origin: {spec.origin}")                # /path/to/json/__init__.py
print(f"Cached: {spec.cached}")                # /path/to/__pycache__/...
print(f"Parent: {spec.parent}")                # (empty for top-level)
print(f"Submodule locations: {spec.submodule_search_locations}")  # ['/path/to/json']

# For packages
spec = importlib.util.find_spec('email')
print(f"Is package: {spec.submodule_search_locations is not None}")
```

### Creating ModuleSpec

```python
from importlib.machinery import ModuleSpec

spec = ModuleSpec(
    name='mymodule',
    loader=my_loader,
    origin='/path/to/mymodule.py',
    is_package=False
)
```

## 50.6 Built-in Import Functions

### __import__

```python
# The fundamental import function
module = __import__('json')

# With fromlist (import specific names)
module = __import__('os.path', fromlist=['join', 'exists'])

# Equivalent to:
# import os.path
# from os.path import join, exists

# __import__ is low-level, prefer importlib
```

### importlib

```python
import importlib

# Import a module by name
json = importlib.import_module('json')

# Import a submodule
path = importlib.import_module('os.path')

# Relative import
submodule = importlib.import_module('.submodule', package='mypackage')

# Reload a module
importlib.reload(json)
```

## 50.7 Module Objects

### Module Attributes

```python
import json

# Standard attributes
print(json.__name__)        # 'json'
print(json.__file__)        # '/path/to/json/__init__.py'
print(json.__doc__)         # Module docstring
print(json.__package__)     # 'json'
print(json.__spec__)        # ModuleSpec
print(json.__loader__)      # SourceFileLoader
print(json.__cached__)      # Path to .pyc file

# For packages
print(json.__path__)        # ['/path/to/json']

# Custom attributes
print(json.__all__)         # Public names for 'from json import *'
```

### Module Creation

```python
import types

# Create module manually
module = types.ModuleType('mymodule')
module.__file__ = '/fake/path.py'
module.my_function = lambda: "Hello"

# Execute code in module
code = compile("x = 42", "<string>", "exec")
exec(code, module.__dict__)

print(module.x)  # 42
```

## 50.8 Import Hooks

### Meta Path Hooks

```python
import sys
import importlib.abc
import importlib.machinery

class CustomFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname == 'virtual_module':
            return importlib.machinery.ModuleSpec(
                fullname,
                CustomLoader(),
                origin='<virtual>'
            )
        return None

class CustomLoader(importlib.abc.Loader):
    def create_module(self, spec):
        return None  # Use default module creation

    def exec_module(self, module):
        module.message = "I'm virtual!"
        module.greet = lambda name: f"Hello, {name}!"

# Install the hook
sys.meta_path.insert(0, CustomFinder())

# Now we can import virtual modules
import virtual_module
print(virtual_module.message)  # "I'm virtual!"
print(virtual_module.greet("World"))  # "Hello, World!"
```

### Path Hooks

```python
import sys

# Path hooks handle entries in sys.path
def my_path_hook(path):
    if path == '/special/path':
        return MyPathFinder(path)
    raise ImportError("Not my path")

sys.path_hooks.insert(0, my_path_hook)
sys.path.append('/special/path')

# Now modules in /special/path use MyPathFinder
```

## 50.9 Import Process in Detail

### Step-by-Step

```python
def detailed_import(name, globals=None, locals=None, fromlist=(), level=0):
    """Detailed view of import process."""

    # Step 1: Resolve name (handle relative imports)
    if level > 0:
        # Relative import
        package = globals['__package__']
        name = resolve_relative(name, package, level)

    # Step 2: Check cache
    if name in sys.modules:
        module = sys.modules[name]
    else:
        # Step 3: Find module
        spec = None
        for finder in sys.meta_path:
            spec = finder.find_spec(name, parent_path)
            if spec is not None:
                break

        if spec is None:
            raise ModuleNotFoundError(f"No module named '{name}'")

        # Step 4: Create module
        module = importlib.util.module_from_spec(spec)

        # Step 5: Add to cache BEFORE executing
        sys.modules[name] = module

        # Step 6: Execute module
        spec.loader.exec_module(module)

    # Step 7: Handle fromlist
    if fromlist:
        for attr in fromlist:
            if not hasattr(module, attr):
                # Try to import submodule
                subname = f"{name}.{attr}"
                __import__(subname)

    return module
```

## 50.10 Common Import Patterns

### Lazy Import

```python
class LazyModule:
    """Import module on first access."""

    def __init__(self, name):
        self._name = name
        self._module = None

    def __getattr__(self, attr):
        if self._module is None:
            self._module = importlib.import_module(self._name)
        return getattr(self._module, attr)

# Usage
pandas = LazyModule('pandas')
# pandas not imported yet

df = pandas.DataFrame()  # Now it's imported
```

### Conditional Import

```python
# Try to import optional dependency
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    np = None
    HAS_NUMPY = False

def process_data(data):
    if HAS_NUMPY:
        return np.array(data)
    return list(data)
```

### Import-Time Side Effects

```python
# module_with_side_effects.py
print("Module is being imported!")  # Runs on import

# Avoid side effects at import time!
# Instead:
def initialize():
    print("Explicit initialization")

# Good pattern: only define, don't execute
_initialized = False

def ensure_initialized():
    global _initialized
    if not _initialized:
        initialize()
        _initialized = True
```

## Summary

- **Import** checks cache, finds, loads, executes, and caches modules
- **sys.modules** is the central module cache
- **Finders** locate modules, **loaders** execute them
- **ModuleSpec** contains all metadata for loading
- **Meta path hooks** customize the entire import process
- **importlib** provides high-level import utilities

## Practice Exercises

1. Create a finder that loads modules from a database
2. Implement a lazy module loader
3. Build an import hook that logs all imports
4. Create a module that reloads itself on file change

---

[← Previous: Signal Handling](../part-10-threading/chapter-49-signal-handling.md) | [Next: Finders and Loaders →](chapter-51-finders-loaders.md)

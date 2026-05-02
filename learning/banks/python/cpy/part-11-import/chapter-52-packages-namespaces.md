# Chapter 52: Packages and Namespace Packages

## 52.1 Regular Packages

A regular package is a directory with `__init__.py`:

```
┌─────────────────────────────────────────────────────────────────┐
│              Package Structure                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  mypackage/                                                      │
│  ├── __init__.py          # Makes it a package                  │
│  ├── module1.py                                                  │
│  ├── module2.py                                                  │
│  └── subpackage/                                                 │
│      ├── __init__.py      # Subpackage                          │
│      └── submodule.py                                            │
│                                                                  │
│  Key attributes of package:                                      │
│  • __name__ = 'mypackage'                                       │
│  • __file__ = '/path/to/mypackage/__init__.py'                  │
│  • __path__ = ['/path/to/mypackage']                            │
│  • __package__ = 'mypackage'                                     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Package Initialization

```python
# mypackage/__init__.py

# Package-level imports
from .module1 import func1
from .module2 import Class2

# Package-level code runs on import
print(f"Initializing {__name__}")

# Define package's public API
__all__ = ['func1', 'Class2', 'subpackage']

# Package version
__version__ = '1.0.0'

# Lazy submodule loading
def __getattr__(name):
    if name == 'expensive_module':
        from . import expensive_module
        return expensive_module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

### The `__path__` Attribute

```python
import mypackage

# __path__ is a list of directories to search for submodules
print(mypackage.__path__)  # ['/path/to/mypackage']

# Can modify __path__ to add search locations
mypackage.__path__.append('/another/location')

# Now submodules can be found in both locations
from mypackage import something  # Searches both paths
```

## 52.2 Namespace Packages (PEP 420)

Namespace packages have no `__init__.py` and can span multiple directories:

```
┌─────────────────────────────────────────────────────────────────┐
│              Namespace Package                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Directory 1:              Directory 2:                          │
│  /path1/                   /path2/                               │
│  └── mynamespace/          └── mynamespace/                      │
│      └── module1.py            └── module2.py                    │
│      (no __init__.py!)         (no __init__.py!)                 │
│                                                                  │
│  With sys.path = ['/path1', '/path2']:                          │
│                                                                  │
│  import mynamespace.module1  # From /path1                      │
│  import mynamespace.module2  # From /path2                      │
│                                                                  │
│  mynamespace.__path__ = ['/path1/mynamespace',                  │
│                          '/path2/mynamespace']                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Creating Namespace Packages

```
# Structure on disk:

# Location 1: /site-packages/company/
company/
├── product_a/
│   ├── __init__.py
│   └── core.py

# Location 2: /other/packages/company/
company/
├── product_b/
│   ├── __init__.py
│   └── helpers.py

# NO __init__.py in 'company' directories!

# Usage:
import company.product_a.core
import company.product_b.helpers
```

### Namespace Package Detection

```python
import company

# Check if namespace package
print(hasattr(company, '__file__'))  # False
print(company.__path__)  # _NamespacePath([...])

# Iterate all locations
for path in company.__path__:
    print(f"Location: {path}")
```

## 52.3 Relative Imports

### Import Types

```python
# package/subpackage/module.py

# Absolute import (starts from top-level)
from package.other import something

# Relative imports (relative to current package)
from . import sibling           # Same package
from .. import parent_module    # Parent package
from ..other import something   # Sibling package
from ...top import thing        # Grandparent package

# Leading dots:
# .   = current package
# ..  = parent package
# ... = grandparent package
```

### Relative Import Resolution

```python
# Given: package/sub1/module.py
# __package__ = 'package.sub1'

# from . import other
# Resolves to: package.sub1.other

# from .. import utils
# Resolves to: package.utils

# from ..sub2 import helper
# Resolves to: package.sub2.helper
```

### When Relative Imports Fail

```python
# Relative imports require __package__ to be set
# They FAIL when running a module directly as a script

# This fails:
# python package/subpackage/module.py
# Error: ImportError: attempted relative import with no known parent package

# Solutions:
# 1. Run as module: python -m package.subpackage.module
# 2. Use absolute imports
# 3. Set up proper package installation
```

## 52.4 `__all__` and Star Imports

### Defining `__all__`

```python
# mymodule.py

# Public API
__all__ = ['public_func', 'PublicClass']

def public_func():
    pass

def _private_func():
    pass

class PublicClass:
    pass

class _PrivateClass:
    pass

# from mymodule import *
# Only imports: public_func, PublicClass
```

### Package `__all__`

```python
# package/__init__.py

# Control what 'from package import *' imports
__all__ = ['module1', 'module2', 'subpackage']

# This causes module1, module2, and subpackage to be imported
# and their names bound in the importing namespace
```

### Submodule Auto-Import

```python
# package/__init__.py

# Don't rely on __all__ to import submodules automatically
# Explicitly import what you want available

from . import module1
from . import module2
from .module1 import important_func

__all__ = ['module1', 'module2', 'important_func']

# Now these work:
# from package import module1
# from package import important_func
```

## 52.5 Package Data and Resources

### Including Data Files

```python
# setup.py or pyproject.toml approach
# pyproject.toml:
# [tool.setuptools.package-data]
# mypackage = ["data/*.json", "templates/*.html"]

# Accessing package data
import importlib.resources

# Python 3.9+ (recommended)
files = importlib.resources.files('mypackage')
data_file = files / 'data' / 'config.json'
content = data_file.read_text()

# Python 3.7+
with importlib.resources.open_text('mypackage.data', 'config.json') as f:
    content = f.read()

# Alternative: pkg_resources (setuptools)
import pkg_resources
content = pkg_resources.resource_string('mypackage', 'data/config.json')
```

### `__file__` Based Access

```python
# Works but has limitations (zip imports, etc.)
import os.path

# Get path relative to module file
def get_data_path(filename):
    module_dir = os.path.dirname(__file__)
    return os.path.join(module_dir, 'data', filename)

data_file = get_data_path('config.json')
```

## 52.6 Circular Imports

### The Problem

```python
# module_a.py
from module_b import func_b

def func_a():
    return "A"

# module_b.py
from module_a import func_a  # Circular!

def func_b():
    return func_a()

# Import fails:
# ImportError: cannot import name 'func_a' from partially initialized module
```

### Solutions

```python
# Solution 1: Import at function level
# module_a.py
def func_a():
    from module_b import func_b
    return func_b()

# Solution 2: Import the module, not the name
# module_b.py
import module_a

def func_b():
    return module_a.func_a()

# Solution 3: Restructure to remove circular dependency
# common.py - shared code
# module_a.py - imports common
# module_b.py - imports common
```

### Detecting Circular Imports

```python
import sys

def check_circular():
    """Check for partially initialized modules."""
    for name, module in sys.modules.items():
        if module is not None:
            # Check if module is still being initialized
            if not hasattr(module, '__spec__'):
                continue
            if module.__spec__ and module.__spec__._initializing:
                print(f"Partially initialized: {name}")
```

## 52.7 Package Distribution Structure

### Modern Package Layout

```
myproject/
├── pyproject.toml          # Build configuration
├── README.md
├── LICENSE
├── src/                    # Source layout
│   └── mypackage/
│       ├── __init__.py
│       ├── core.py
│       ├── utils.py
│       └── data/
│           └── config.json
├── tests/
│   ├── __init__.py
│   ├── test_core.py
│   └── test_utils.py
└── docs/
    └── index.md
```

### pyproject.toml

```toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "mypackage"
version = "1.0.0"
description = "My awesome package"
readme = "README.md"
requires-python = ">=3.8"
dependencies = [
    "requests>=2.25.0",
    "numpy>=1.20.0",
]

[project.optional-dependencies]
dev = ["pytest", "black", "mypy"]

[tool.setuptools.packages.find]
where = ["src"]
```

## 52.8 Advanced Package Patterns

### Plugin System

```python
# Core package provides plugin discovery
# plugins/__init__.py
import importlib
import pkgutil

def discover_plugins():
    """Find all installed plugins."""
    plugins = {}
    for finder, name, ispkg in pkgutil.iter_modules(__path__):
        module = importlib.import_module(f'.{name}', __package__)
        if hasattr(module, 'register'):
            plugins[name] = module.register()
    return plugins

# Plugin module: plugins/my_plugin.py
def register():
    return {
        'name': 'My Plugin',
        'handler': my_handler
    }

def my_handler():
    pass
```

### Entry Points

```toml
# pyproject.toml
[project.entry-points.console_scripts]
mycommand = "mypackage.cli:main"

[project.entry-points."myapp.plugins"]
myplugin = "mypackage.plugins.myplugin:register"
```

```python
# Discovering entry points
from importlib.metadata import entry_points

# Python 3.10+
eps = entry_points(group='myapp.plugins')
for ep in eps:
    plugin = ep.load()
    plugin()

# Python 3.9
eps = entry_points()['myapp.plugins']
```

## 52.9 Import Optimization

### Lazy Loading

```python
# package/__init__.py
import importlib

# Define what should be lazily loaded
_lazy_imports = {
    'heavy_module': '.heavy_module',
    'another_heavy': '.subpackage.another_heavy',
}

def __getattr__(name):
    if name in _lazy_imports:
        module = importlib.import_module(_lazy_imports[name], __package__)
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

def __dir__():
    return list(globals().keys()) + list(_lazy_imports.keys())
```

### Conditional Imports

```python
# package/__init__.py
import sys

# Platform-specific imports
if sys.platform == 'win32':
    from .windows_impl import *
else:
    from .unix_impl import *

# Version-specific imports
if sys.version_info >= (3, 11):
    from .modern_impl import feature
else:
    from .compat_impl import feature
```

## Summary

- **Regular packages** have `__init__.py` and single location
- **Namespace packages** span multiple directories without `__init__.py`
- **Relative imports** use dots to refer to current/parent packages
- **`__all__`** controls star imports
- **Circular imports** need careful handling
- **Modern packages** use `src/` layout and `pyproject.toml`

## Practice Exercises

1. Create a namespace package split across two directories
2. Implement a plugin discovery system using entry points
3. Build a package with lazy-loaded submodules
4. Resolve circular import issues in existing code

---

[← Previous: Finders and Loaders](chapter-51-finders-loaders.md) | [Next: Import Internals →](chapter-53-import-internals.md)

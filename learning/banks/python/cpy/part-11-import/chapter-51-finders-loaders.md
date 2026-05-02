# Chapter 51: Finders and Loaders

## 51.1 The Finder Interface

Finders are responsible for locating modules:

```
┌─────────────────────────────────────────────────────────────────┐
│              Finder Types                                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  MetaPathFinder (sys.meta_path):                                │
│  • First consulted for all imports                              │
│  • Can find any type of module                                  │
│  • Method: find_spec(fullname, path, target=None)              │
│                                                                  │
│  PathEntryFinder (sys.path_hooks):                              │
│  • Handles specific path entries                                │
│  • Created by path hooks for each sys.path entry               │
│  • Method: find_spec(fullname, target=None)                    │
│                                                                  │
│  Standard Finders:                                               │
│  • BuiltinImporter - for built-in modules                       │
│  • FrozenImporter - for frozen modules                          │
│  • PathFinder - delegates to path entry finders                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 51.2 Implementing a MetaPathFinder

### Basic Finder

```python
import sys
import importlib.abc
import importlib.machinery
import importlib.util

class SimpleMetaFinder(importlib.abc.MetaPathFinder):
    """A simple meta path finder."""

    MODULES = {
        'hello': 'message = "Hello, World!"',
        'goodbye': 'message = "Goodbye, World!"',
    }

    def find_spec(self, fullname, path, target=None):
        if fullname in self.MODULES:
            return importlib.machinery.ModuleSpec(
                fullname,
                SimpleLoader(self.MODULES[fullname]),
                origin='<memory>'
            )
        return None

class SimpleLoader(importlib.abc.Loader):
    def __init__(self, source):
        self.source = source

    def create_module(self, spec):
        return None  # Use default

    def exec_module(self, module):
        exec(self.source, module.__dict__)

# Install and use
sys.meta_path.insert(0, SimpleMetaFinder())

import hello
print(hello.message)  # "Hello, World!"
```

### Finder with Submodule Support

```python
class PackageFinder(importlib.abc.MetaPathFinder):
    """Finder that supports packages."""

    PACKAGE = 'mypkg'
    MODULES = {
        'mypkg': '__init__.py code...',
        'mypkg.sub1': 'sub1 code...',
        'mypkg.sub2': 'sub2 code...',
    }

    def find_spec(self, fullname, path, target=None):
        if fullname not in self.MODULES:
            return None

        is_package = fullname == self.PACKAGE

        return importlib.machinery.ModuleSpec(
            fullname,
            PackageLoader(self.MODULES[fullname]),
            origin=f'<{fullname}>',
            is_package=is_package,
            submodule_search_locations=[fullname] if is_package else None
        )
```

## 51.3 The Loader Interface

### Loader Methods

```python
import importlib.abc
import types

class DetailedLoader(importlib.abc.Loader):
    """Loader with all methods implemented."""

    def __init__(self, source, origin):
        self.source = source
        self.origin = origin

    def create_module(self, spec):
        """Create the module object.

        Return None to use default module creation,
        or return a custom module object.
        """
        # Custom module creation
        module = types.ModuleType(spec.name)
        module.__file__ = self.origin
        module.__loader__ = self
        module.__package__ = spec.parent
        return module

    def exec_module(self, module):
        """Execute the module code.

        Populate the module's namespace.
        """
        code = compile(self.source, self.origin, 'exec')
        exec(code, module.__dict__)

    def load_module(self, fullname):
        """Legacy method (deprecated).

        Use create_module + exec_module instead.
        """
        spec = importlib.util.spec_from_loader(fullname, self)
        module = importlib.util.module_from_spec(spec)
        sys.modules[fullname] = module
        self.exec_module(module)
        return module
```

### Source Loader

```python
import importlib.abc

class SourceLoader(importlib.abc.SourceLoader):
    """Loader that reads source from custom location."""

    def __init__(self, fullname, source_map):
        self.fullname = fullname
        self.source_map = source_map

    def get_filename(self, fullname):
        """Return the 'filename' for the module."""
        return f'<{fullname}>'

    def get_data(self, path):
        """Return the source code as bytes."""
        # path is what get_filename returned
        name = path.strip('<>')
        source = self.source_map.get(name, '')
        return source.encode('utf-8')

    def path_stats(self, path):
        """Return mtime for caching (optional)."""
        return {'mtime': 0, 'size': 0}
```

## 51.4 Built-in Finders and Loaders

### BuiltinImporter

```python
import sys
from importlib.machinery import BuiltinImporter

# BuiltinImporter handles built-in modules
print(BuiltinImporter in type(sys).__mro__)  # Check if sys uses it

# Built-in module characteristics
print(sys.__file__)     # No file (None or raises AttributeError)
print(sys.__loader__)   # BuiltinImporter
print(sys.__spec__)     # ModuleSpec with BuiltinImporter

# List all built-in modules
print(sys.builtin_module_names)
```

### FrozenImporter

```python
from importlib.machinery import FrozenImporter

# Frozen modules are compiled into Python binary
# They have pre-compiled bytecode

# Check if a module is frozen
import _frozen_importlib
print(_frozen_importlib.__loader__)  # FrozenImporter
```

### PathFinder

```python
from importlib.machinery import PathFinder
import sys

# PathFinder handles sys.path
# It delegates to path entry finders

# For each entry in sys.path:
# 1. Check sys.path_importer_cache
# 2. If not cached, try sys.path_hooks
# 3. Store result in cache

print(sys.path_importer_cache)  # Cached path entry finders
```

## 51.5 Path Entry Finders

### FileFinder

```python
from importlib.machinery import FileFinder, SOURCE_SUFFIXES

# FileFinder handles file system directories
# It's automatically created by PathFinder

# Create a FileFinder manually
finder = FileFinder('/path/to/modules',
    (SourceFileLoader, SOURCE_SUFFIXES)
)

# Find a module
spec = finder.find_spec('mymodule')
if spec:
    print(f"Found: {spec.origin}")
```

### Custom Path Entry Finder

```python
import sys
import importlib.abc

class ZipFileFinder(importlib.abc.PathEntryFinder):
    """Find modules inside a zip file."""

    def __init__(self, zip_path):
        import zipfile
        self.zip_path = zip_path
        self.zip_file = zipfile.ZipFile(zip_path, 'r')
        self.names = set(self.zip_file.namelist())

    def find_spec(self, fullname, target=None):
        # Convert module name to path
        path = fullname.replace('.', '/') + '.py'

        if path in self.names:
            return importlib.machinery.ModuleSpec(
                fullname,
                ZipLoader(self.zip_file, path),
                origin=f'{self.zip_path}/{path}'
            )
        return None

    def invalidate_caches(self):
        pass

def zip_path_hook(path):
    if path.endswith('.zip'):
        return ZipFileFinder(path)
    raise ImportError()

# Install the hook
sys.path_hooks.insert(0, zip_path_hook)
sys.path.append('/path/to/modules.zip')
```

## 51.6 Resource Loaders

### Reading Package Resources

```python
import importlib.resources

# Read text file from package
with importlib.resources.open_text('mypackage', 'data.txt') as f:
    content = f.read()

# Read binary file
with importlib.resources.open_binary('mypackage', 'image.png') as f:
    data = f.read()

# Get path to resource (for legacy APIs)
with importlib.resources.path('mypackage', 'config.ini') as path:
    # path is a pathlib.Path
    legacy_function(str(path))

# Python 3.9+ traversable resources
files = importlib.resources.files('mypackage')
data_path = files / 'data'
for item in data_path.iterdir():
    print(item.name)
```

### Implementing Resource Access

```python
import importlib.abc

class ResourceLoader(importlib.abc.ResourceLoader):
    """Loader that provides resource access."""

    def __init__(self, resources):
        self.resources = resources  # dict of path -> bytes

    def get_data(self, path):
        """Return resource data as bytes."""
        if path in self.resources:
            return self.resources[path]
        raise FileNotFoundError(path)

    def get_resource_reader(self, fullname):
        """Return a ResourceReader for the package."""
        return ResourceReader(self.resources)

class ResourceReader(importlib.abc.ResourceReader):
    def __init__(self, resources):
        self.resources = resources

    def open_resource(self, resource):
        import io
        return io.BytesIO(self.resources.get(resource, b''))

    def resource_path(self, resource):
        raise FileNotFoundError(resource)

    def is_resource(self, name):
        return name in self.resources

    def contents(self):
        return iter(self.resources.keys())
```

## 51.7 Finder/Loader ABCs

### Abstract Base Classes

```python
import importlib.abc

# Finders
class MetaPathFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        """Find module spec."""
        raise NotImplementedError

    def invalidate_caches(self):
        """Clear any caches."""
        pass

class PathEntryFinder(importlib.abc.PathEntryFinder):
    def find_spec(self, fullname, target=None):
        """Find module spec for path entry."""
        raise NotImplementedError

    def invalidate_caches(self):
        pass

# Loaders
class Loader(importlib.abc.Loader):
    def create_module(self, spec):
        """Create module object (return None for default)."""
        return None

    def exec_module(self, module):
        """Execute module code."""
        raise NotImplementedError

class InspectLoader(importlib.abc.InspectLoader):
    def get_code(self, fullname):
        """Return compiled code object."""
        raise NotImplementedError

    def get_source(self, fullname):
        """Return source code as string."""
        raise NotImplementedError

class SourceLoader(importlib.abc.SourceLoader):
    def get_filename(self, fullname):
        """Return source file path."""
        raise NotImplementedError

    def get_data(self, path):
        """Return bytes of file at path."""
        raise NotImplementedError
```

## 51.8 Practical Examples

### Database Module Loader

```python
import sys
import importlib.abc
import importlib.machinery
import sqlite3

class DatabaseFinder(importlib.abc.MetaPathFinder):
    """Load modules from SQLite database."""

    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()

    def find_spec(self, fullname, path, target=None):
        self.cursor.execute(
            "SELECT source FROM modules WHERE name = ?",
            (fullname,)
        )
        row = self.cursor.fetchone()

        if row:
            return importlib.machinery.ModuleSpec(
                fullname,
                DatabaseLoader(row[0]),
                origin=f'db://{fullname}'
            )
        return None

class DatabaseLoader(importlib.abc.Loader):
    def __init__(self, source):
        self.source = source

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        exec(self.source, module.__dict__)

# Usage
db_finder = DatabaseFinder('/path/to/modules.db')
sys.meta_path.insert(0, db_finder)
```

### URL Module Loader

```python
import sys
import importlib.abc
import importlib.machinery
import urllib.request

class URLFinder(importlib.abc.MetaPathFinder):
    """Load modules from URLs."""

    def __init__(self, base_url):
        self.base_url = base_url.rstrip('/')

    def find_spec(self, fullname, path, target=None):
        url = f"{self.base_url}/{fullname.replace('.', '/')}.py"

        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                source = response.read().decode('utf-8')
                return importlib.machinery.ModuleSpec(
                    fullname,
                    URLLoader(source),
                    origin=url
                )
        except urllib.error.URLError:
            return None

class URLLoader(importlib.abc.Loader):
    def __init__(self, source):
        self.source = source

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        exec(self.source, module.__dict__)

# Usage (with caution - security implications!)
# sys.meta_path.insert(0, URLFinder('https://example.com/modules'))
```

## 51.9 Debugging Import Issues

### Verbose Import

```bash
# Enable verbose import output
python -v script.py

# Output shows:
# import system
# trying path/module.py
# code object from path/__pycache__/module.cpython-311.pyc
```

### Programmatic Debugging

```python
import sys

class ImportDebugger(importlib.abc.MetaPathFinder):
    """Log all import attempts."""

    def find_spec(self, fullname, path, target=None):
        print(f"Import: {fullname}")
        print(f"  Path: {path}")
        print(f"  Target: {target}")
        return None  # Always pass to next finder

sys.meta_path.insert(0, ImportDebugger())
```

## Summary

- **Finders** locate modules via `find_spec()`
- **Loaders** create and execute modules via `create_module()` and `exec_module()`
- **MetaPathFinders** handle all import types
- **PathEntryFinders** handle specific path entries
- **Built-in finders**: BuiltinImporter, FrozenImporter, PathFinder
- **Custom finders** enable importing from any source

## Practice Exercises

1. Create a finder that loads encrypted modules
2. Implement a finder that caches modules in Redis
3. Build a hot-reload system using custom loaders
4. Create a finder for importing from git repositories

---

[← Previous: Import Overview](chapter-50-import-overview.md) | [Next: Packages and Namespaces →](chapter-52-packages-namespaces.md)

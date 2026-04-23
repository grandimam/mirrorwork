# Lab 7: Import Hooks

## Objective

Build custom import hooks to intercept, modify, and extend Python's import system.

## Prerequisites

- Understanding of the import system (Part 11)
- Knowledge of finders, loaders, and meta path hooks

## Lab Setup

```python
# lab07_import_hooks.py
import sys
import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import types
import ast
from pathlib import Path
from typing import Optional, Dict, List, Any, Sequence
from dataclasses import dataclass
```

## Exercise 1: Import Logger

Create an import logger to track all imports:

```python
@dataclass
class ImportEvent:
    """Records an import event."""
    module_name: str
    parent: Optional[str]
    source: str  # 'builtin', 'frozen', 'file', 'namespace', 'c_extension'
    path: Optional[str]
    cached: bool
    timestamp: float

class ImportLogger:
    """Log all module imports."""

    def __init__(self):
        self.events: List[ImportEvent] = []
        self._original_import = None
        self.installed = False

    def _custom_import(self, name: str, globals=None, locals=None,
                       fromlist=(), level=0):
        """
        TODO: Custom import function that logs imports.

        Call original __import__ and log the result.
        """
        import time

        # Determine parent
        parent = None
        if globals:
            parent = globals.get('__name__')

        # Check if cached
        cached = name in sys.modules

        # Call original import
        start = time.perf_counter()
        module = self._original_import(name, globals, locals, fromlist, level)
        elapsed = time.perf_counter() - start

        # Determine source type
        source = self._determine_source(module)

        # Get path
        path = getattr(module, '__file__', None)

        event = ImportEvent(
            module_name=name,
            parent=parent,
            source=source,
            path=path,
            cached=cached,
            timestamp=elapsed
        )
        self.events.append(event)

        return module

    def _determine_source(self, module: types.ModuleType) -> str:
        """Determine the source type of a module."""
        if not hasattr(module, '__spec__') or module.__spec__ is None:
            return 'unknown'

        loader = module.__spec__.loader

        if loader is None:
            return 'namespace'
        if isinstance(loader, importlib.machinery.BuiltinImporter):
            return 'builtin'
        if isinstance(loader, importlib.machinery.FrozenImporter):
            return 'frozen'
        if isinstance(loader, importlib.machinery.ExtensionFileLoader):
            return 'c_extension'

        return 'file'

    def install(self):
        """Install the import logger."""
        if not self.installed:
            import builtins
            self._original_import = builtins.__import__
            builtins.__import__ = self._custom_import
            self.installed = True
            print("Import logger installed")

    def uninstall(self):
        """Remove the import logger."""
        if self.installed:
            import builtins
            builtins.__import__ = self._original_import
            self.installed = False
            print("Import logger removed")

    def report(self):
        """Print import report."""
        print("\nImport Report:")
        print("=" * 70)

        by_source = {}
        for event in self.events:
            by_source.setdefault(event.source, []).append(event)

        for source, events in sorted(by_source.items()):
            print(f"\n{source.upper()} ({len(events)} imports):")
            for e in events[:10]:
                cached_str = " (cached)" if e.cached else ""
                print(f"  {e.module_name}{cached_str}")
                if e.path:
                    print(f"    -> {e.path}")

        # Timing stats
        if self.events:
            total_time = sum(e.timestamp for e in self.events if not e.cached)
            slowest = sorted(self.events, key=lambda e: e.timestamp, reverse=True)[:5]

            print(f"\nTotal import time: {total_time*1000:.2f}ms")
            print("\nSlowest imports:")
            for e in slowest:
                print(f"  {e.module_name}: {e.timestamp*1000:.2f}ms")

import_logger = ImportLogger()
```

## Exercise 2: Module Finder

Create a custom module finder:

```python
class CustomFinder(importlib.abc.MetaPathFinder):
    """
    Custom meta path finder.

    TODO: Implement find_spec to locate modules.
    """

    def __init__(self, search_paths: List[str] = None):
        self.search_paths = search_paths or []
        self.found_modules: Dict[str, str] = {}

    def find_spec(
        self,
        fullname: str,
        path: Optional[Sequence[str]],
        target: Optional[types.ModuleType] = None
    ) -> Optional[importlib.machinery.ModuleSpec]:
        """Find a module specification."""
        print(f"CustomFinder.find_spec: {fullname}")

        # Check custom search paths
        for search_path in self.search_paths:
            module_file = Path(search_path) / f"{fullname.replace('.', '/')}.py"

            if module_file.exists():
                print(f"  Found at: {module_file}")
                self.found_modules[fullname] = str(module_file)

                return importlib.util.spec_from_file_location(
                    fullname,
                    module_file,
                    submodule_search_locations=[]
                )

        return None  # Not found, let other finders try

    def install(self):
        """Install finder on sys.meta_path."""
        if self not in sys.meta_path:
            sys.meta_path.insert(0, self)
            print(f"CustomFinder installed (search paths: {self.search_paths})")

    def uninstall(self):
        """Remove finder from sys.meta_path."""
        if self in sys.meta_path:
            sys.meta_path.remove(self)
            print("CustomFinder removed")
```

## Exercise 3: Code Transformer

Create an import hook that transforms code during import:

```python
class CodeTransformerLoader(importlib.abc.SourceLoader):
    """
    Loader that transforms source code during import.
    """

    def __init__(self, fullname: str, path: str, transformers: List[callable]):
        self.fullname = fullname
        self.path = path
        self.transformers = transformers

    def get_filename(self, fullname: str) -> str:
        return self.path

    def get_data(self, path: str) -> bytes:
        """Read and transform source code."""
        with open(path, 'rb') as f:
            source = f.read().decode('utf-8')

        # Apply transformers
        for transformer in self.transformers:
            source = transformer(source, self.fullname)

        return source.encode('utf-8')

class CodeTransformFinder(importlib.abc.MetaPathFinder):
    """
    Finder that uses CodeTransformerLoader.
    """

    def __init__(self):
        self.transformers: List[callable] = []
        self.patterns: List[str] = ['*']  # Module patterns to transform

    def add_transformer(self, func: callable):
        """Add a source code transformer."""
        self.transformers.append(func)
        print(f"Added transformer: {func.__name__}")

    def should_transform(self, fullname: str) -> bool:
        """Check if module should be transformed."""
        for pattern in self.patterns:
            if pattern == '*' or fullname.startswith(pattern):
                return True
        return False

    def find_spec(
        self,
        fullname: str,
        path: Optional[Sequence[str]],
        target: Optional[types.ModuleType] = None
    ) -> Optional[importlib.machinery.ModuleSpec]:
        """Find spec with transformer loader."""
        if not self.should_transform(fullname):
            return None

        if fullname in sys.modules:
            return None

        # Find the actual module file
        try:
            spec = importlib.util.find_spec(fullname)
            if spec is None or spec.origin is None:
                return None
        except (ModuleNotFoundError, ValueError):
            return None

        # Skip if not a source file
        if not spec.origin.endswith('.py'):
            return None

        # Create new spec with transformer loader
        loader = CodeTransformerLoader(fullname, spec.origin, self.transformers)

        return importlib.machinery.ModuleSpec(
            fullname,
            loader,
            origin=spec.origin,
            is_package=spec.submodule_search_locations is not None
        )

    def install(self):
        """Install on meta path."""
        if self not in sys.meta_path:
            sys.meta_path.insert(0, self)
            print("CodeTransformFinder installed")

    def uninstall(self):
        """Remove from meta path."""
        if self in sys.meta_path:
            sys.meta_path.remove(self)
            print("CodeTransformFinder removed")

# Example transformers
def add_debug_prints(source: str, module_name: str) -> str:
    """
    TODO: Transform source to add debug print statements.

    Add prints at function entry/exit.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source

    class DebugTransformer(ast.NodeTransformer):
        def visit_FunctionDef(self, node):
            # Add entry print
            entry_print = ast.Expr(
                value=ast.Call(
                    func=ast.Name(id='print', ctx=ast.Load()),
                    args=[ast.Constant(value=f"ENTER: {node.name}")],
                    keywords=[]
                )
            )

            node.body.insert(0, ast.fix_missing_locations(entry_print))
            self.generic_visit(node)
            return node

    transformer = DebugTransformer()
    new_tree = transformer.visit(tree)

    return ast.unparse(new_tree)

def add_timing(source: str, module_name: str) -> str:
    """Add timing to all functions."""
    # This would add import time and timing decorators
    header = "import time as _timing_module\n"
    return header + source

transform_finder = CodeTransformFinder()
```

## Exercise 4: Virtual Module System

Create virtual modules that don't exist on disk:

```python
class VirtualModuleLoader(importlib.abc.Loader):
    """Load modules from virtual sources."""

    def __init__(self, source: str, fullname: str):
        self.source = source
        self.fullname = fullname

    def create_module(self, spec):
        """Create the module object."""
        return None  # Use default module creation

    def exec_module(self, module):
        """Execute the module code."""
        exec(compile(self.source, f"<virtual:{self.fullname}>", 'exec'),
             module.__dict__)

class VirtualModuleFinder(importlib.abc.MetaPathFinder):
    """
    Finder for virtual (in-memory) modules.

    TODO: Implement virtual module system.
    """

    def __init__(self):
        self.modules: Dict[str, str] = {}  # name -> source code

    def register(self, name: str, source: str):
        """Register a virtual module."""
        self.modules[name] = source
        print(f"Registered virtual module: {name}")

    def register_package(self, name: str, modules: Dict[str, str]):
        """Register a virtual package."""
        # Register __init__
        self.modules[name] = modules.get('__init__', '')

        # Register submodules
        for subname, source in modules.items():
            if subname != '__init__':
                self.modules[f"{name}.{subname}"] = source

        print(f"Registered virtual package: {name}")

    def find_spec(
        self,
        fullname: str,
        path: Optional[Sequence[str]],
        target: Optional[types.ModuleType] = None
    ) -> Optional[importlib.machinery.ModuleSpec]:
        """Find virtual module spec."""
        if fullname not in self.modules:
            return None

        source = self.modules[fullname]
        loader = VirtualModuleLoader(source, fullname)

        # Check if it's a package
        is_package = any(
            name.startswith(f"{fullname}.")
            for name in self.modules
        )

        return importlib.machinery.ModuleSpec(
            fullname,
            loader,
            origin=f"<virtual:{fullname}>",
            is_package=is_package
        )

    def install(self):
        """Install finder."""
        if self not in sys.meta_path:
            sys.meta_path.insert(0, self)
            print("VirtualModuleFinder installed")

    def uninstall(self):
        """Remove finder."""
        if self in sys.meta_path:
            sys.meta_path.remove(self)

        # Remove virtual modules from sys.modules
        for name in list(self.modules.keys()):
            if name in sys.modules:
                del sys.modules[name]

        print("VirtualModuleFinder removed")

virtual_finder = VirtualModuleFinder()
```

## Exercise 5: Complete Import Hook System

Combine all components:

```python
class ImportHookSystem:
    """Complete import hook management system."""

    def __init__(self):
        self.logger = ImportLogger()
        self.custom_finder = CustomFinder()
        self.transform_finder = CodeTransformFinder()
        self.virtual_finder = VirtualModuleFinder()
        self._installed = False

    def install_all(self):
        """Install all hooks."""
        self.logger.install()
        self.custom_finder.install()
        self.transform_finder.install()
        self.virtual_finder.install()
        self._installed = True

    def uninstall_all(self):
        """Remove all hooks."""
        self.logger.uninstall()
        self.custom_finder.uninstall()
        self.transform_finder.uninstall()
        self.virtual_finder.uninstall()
        self._installed = False

    def add_search_path(self, path: str):
        """Add custom search path."""
        self.custom_finder.search_paths.append(path)

    def add_transformer(self, func: callable):
        """Add code transformer."""
        self.transform_finder.add_transformer(func)

    def register_virtual(self, name: str, source: str):
        """Register virtual module."""
        self.virtual_finder.register(name, source)

    def import_report(self):
        """Show import statistics."""
        self.logger.report()

    def list_meta_path(self):
        """Show current meta path."""
        print("\nCurrent sys.meta_path:")
        for i, finder in enumerate(sys.meta_path):
            print(f"  [{i}] {type(finder).__name__}")

    def reload_module(self, name: str):
        """
        TODO: Force reload a module through our hooks.
        """
        if name in sys.modules:
            del sys.modules[name]

        return importlib.import_module(name)

    def import_from_string(self, name: str, source: str):
        """Import module from source string."""
        self.virtual_finder.register(name, source)
        return importlib.import_module(name)

hook_system = ImportHookSystem()
```

## Demo Application

```python
def demo():
    """Demonstrate import hooks."""
    print("=== Import Hooks Demo ===\n")

    # 1. Import logging
    print("1. Import Logging:")
    hook_system.logger.install()

    import json
    import collections

    hook_system.logger.report()
    hook_system.logger.uninstall()

    # 2. Virtual modules
    print("\n2. Virtual Modules:")
    hook_system.virtual_finder.install()

    hook_system.register_virtual('myconfig', '''
# Virtual configuration module
DEBUG = True
VERSION = "1.0.0"

def get_settings():
    return {"debug": DEBUG, "version": VERSION}
''')

    import myconfig
    print(f"  myconfig.DEBUG = {myconfig.DEBUG}")
    print(f"  myconfig.VERSION = {myconfig.VERSION}")
    print(f"  myconfig.get_settings() = {myconfig.get_settings()}")

    hook_system.virtual_finder.uninstall()

    # 3. Virtual package
    print("\n3. Virtual Package:")
    hook_system.virtual_finder.install()

    hook_system.virtual_finder.register_package('mypack', {
        '__init__': 'PACKAGE_NAME = "mypack"',
        'utils': 'def helper(): return "I am a helper"',
        'core': 'class Engine: pass',
    })

    import mypack
    import mypack.utils

    print(f"  mypack.PACKAGE_NAME = {mypack.PACKAGE_NAME}")
    print(f"  mypack.utils.helper() = {mypack.utils.helper()}")

    hook_system.virtual_finder.uninstall()

    # 4. Code transformation
    print("\n4. Code Transformation (conceptual):")
    print("  Transformers can modify code during import")
    print("  Example: add_debug_prints() adds function entry logging")

    # 5. Show meta path
    print("\n5. Current Meta Path:")
    hook_system.list_meta_path()

    # 6. Import from string
    print("\n6. Import from String:")
    hook_system.virtual_finder.install()

    math_utils = hook_system.import_from_string('math_utils', '''
def square(x):
    return x ** 2

def cube(x):
    return x ** 3
''')

    print(f"  math_utils.square(5) = {math_utils.square(5)}")
    print(f"  math_utils.cube(3) = {math_utils.cube(3)}")

    hook_system.virtual_finder.uninstall()

if __name__ == "__main__":
    demo()
```

## Expected Output

```
=== Import Hooks Demo ===

1. Import Logging:

Import Report:
======================================================================

BUILTIN (2 imports):
  sys
  _json

FILE (3 imports):
  json
    -> /usr/lib/python3.11/json/__init__.py
  collections
    -> /usr/lib/python3.11/collections/__init__.py

Total import time: 15.23ms

2. Virtual Modules:
  myconfig.DEBUG = True
  myconfig.VERSION = 1.0.0
  myconfig.get_settings() = {'debug': True, 'version': '1.0.0'}

3. Virtual Package:
  mypack.PACKAGE_NAME = mypack
  mypack.utils.helper() = I am a helper

5. Current Meta Path:
  [0] BuiltinImporter
  [1] FrozenImporter
  [2] PathFinder
```

## Submission

1. Complete all TODO sections
2. Create a transformer that adds type checking
3. Implement lazy module loading
4. Bonus: Build a module sandbox that restricts imports

---

[Next: Lab 8 - Thread Pool →](lab-08-thread-pool.md)

# Chapter 15: Descriptor Protocol

## 15.1 `__get__`, `__set__`, `__delete__`

Descriptors are objects that customize attribute access. They implement one or more of:

```python
class Descriptor:
    def __get__(self, obj, objtype=None):
        """Called when attribute is accessed."""
        pass

    def __set__(self, obj, value):
        """Called when attribute is assigned."""
        pass

    def __delete__(self, obj):
        """Called when attribute is deleted."""
        pass
```

### Basic Descriptor Example

```python
class Verbose:
    """A descriptor that logs all access."""

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self  # Accessed from class
        print(f"Getting {self.name}")
        return obj.__dict__.get(self.name)

    def __set__(self, obj, value):
        print(f"Setting {self.name} to {value}")
        obj.__dict__[self.name] = value

    def __delete__(self, obj):
        print(f"Deleting {self.name}")
        del obj.__dict__[self.name]

class MyClass:
    attr = Verbose()

obj = MyClass()
obj.attr = 42      # Setting attr to 42
print(obj.attr)    # Getting attr, then 42
del obj.attr       # Deleting attr
```

## 15.2 Data Descriptors vs Non-Data Descriptors

### Data Descriptor

Has both `__get__` and `__set__` (or `__delete__`):

```python
class DataDescriptor:
    def __get__(self, obj, objtype=None):
        return "from descriptor"

    def __set__(self, obj, value):
        pass  # Just having __set__ makes it a data descriptor

class Example:
    attr = DataDescriptor()

obj = Example()
obj.__dict__['attr'] = "from instance"  # Try to shadow
print(obj.attr)  # "from descriptor" - data descriptor wins!
```

### Non-Data Descriptor

Has only `__get__`:

```python
class NonDataDescriptor:
    def __get__(self, obj, objtype=None):
        return "from descriptor"

class Example:
    attr = NonDataDescriptor()

obj = Example()
print(obj.attr)  # "from descriptor"

obj.__dict__['attr'] = "from instance"  # Shadow the descriptor
print(obj.attr)  # "from instance" - instance attribute wins!
```

### Lookup Priority

```
┌─────────────────────────────────────────────────────────────────┐
│                  Attribute Lookup Order                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  obj.attr lookup:                                                │
│                                                                  │
│  1. Data descriptors from type(obj).__mro__                     │
│     (has __get__ AND __set__/__delete__)                        │
│     ↓ not found                                                  │
│  2. Instance __dict__ (obj.__dict__['attr'])                    │
│     ↓ not found                                                  │
│  3. Non-data descriptors and class attributes                    │
│     from type(obj).__mro__                                       │
│     ↓ not found                                                  │
│  4. __getattr__ (if defined)                                     │
│     ↓ not found                                                  │
│  5. AttributeError                                               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 15.3 Property Implementation

`property` is a built-in data descriptor:

```python
class property:
    """Pure Python implementation of property."""

    def __init__(self, fget=None, fset=None, fdel=None, doc=None):
        self.fget = fget
        self.fset = fset
        self.fdel = fdel
        self.__doc__ = doc or (fget.__doc__ if fget else None)

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        if self.fget is None:
            raise AttributeError("unreadable attribute")
        return self.fget(obj)

    def __set__(self, obj, value):
        if self.fset is None:
            raise AttributeError("can't set attribute")
        self.fset(obj, value)

    def __delete__(self, obj):
        if self.fdel is None:
            raise AttributeError("can't delete attribute")
        self.fdel(obj)

    def getter(self, fget):
        return type(self)(fget, self.fset, self.fdel, self.__doc__)

    def setter(self, fset):
        return type(self)(self.fget, fset, self.fdel, self.__doc__)

    def deleter(self, fdel):
        return type(self)(self.fget, self.fset, fdel, self.__doc__)
```

### Using Property

```python
class Circle:
    def __init__(self, radius):
        self._radius = radius

    @property
    def radius(self):
        """The radius of the circle."""
        return self._radius

    @radius.setter
    def radius(self, value):
        if value < 0:
            raise ValueError("Radius cannot be negative")
        self._radius = value

    @property
    def area(self):
        """Computed property - read only."""
        import math
        return math.pi * self._radius ** 2

c = Circle(5)
print(c.radius)  # 5
c.radius = 10    # Uses setter
print(c.area)    # 314.159...
# c.area = 100   # AttributeError - no setter
```

## 15.4 Method Binding

Functions are non-data descriptors that implement method binding:

```python
class Function:
    """Simplified function descriptor."""

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self  # Unbound - return function
        # Bound - return method
        return MethodType(self, obj)

# This is why methods work:
class Example:
    def method(self):
        return self

obj = Example()
print(Example.method)  # <function Example.method at 0x...>
print(obj.method)      # <bound method Example.method of <Example ...>>

# The function's __get__ creates a bound method
func = Example.__dict__['method']
print(func.__get__(obj, Example))  # <bound method ...>
```

### Bound vs Unbound Methods

```python
class MyClass:
    def method(self, x):
        return self, x

obj = MyClass()

# Unbound (from class) - Python 3 returns function
unbound = MyClass.method
print(unbound(obj, 10))  # Must pass self explicitly

# Bound (from instance) - self is already bound
bound = obj.method
print(bound(10))  # Self is automatically passed
```

## 15.5 `classmethod` and `staticmethod`

### classmethod Descriptor

```python
class classmethod:
    """Pure Python implementation."""

    def __init__(self, func):
        self.func = func

    def __get__(self, obj, objtype=None):
        if objtype is None:
            objtype = type(obj)

        def method(*args, **kwargs):
            return self.func(objtype, *args, **kwargs)

        return method

# Usage
class Example:
    count = 0

    @classmethod
    def increment(cls):
        cls.count += 1
        return cls.count

print(Example.increment())  # 1
print(Example().increment())  # 2
```

### staticmethod Descriptor

```python
class staticmethod:
    """Pure Python implementation."""

    def __init__(self, func):
        self.func = func

    def __get__(self, obj, objtype=None):
        return self.func  # Return function unchanged

# Usage
class Math:
    @staticmethod
    def add(a, b):
        return a + b

print(Math.add(1, 2))     # 3
print(Math().add(1, 2))   # 3
```

## 15.6 `__slots__` Implementation

`__slots__` creates member descriptors instead of using `__dict__`:

```python
class Point:
    __slots__ = ['x', 'y']

    def __init__(self, x, y):
        self.x = x
        self.y = y

p = Point(1, 2)
print(p.x, p.y)  # 1 2

# No __dict__
print(hasattr(p, '__dict__'))  # False

# Memory efficient
import sys
print(sys.getsizeof(p))  # Much smaller than dict-based

# Attributes are descriptors on the class
print(type(Point.x))  # <class 'member_descriptor'>
```

### How `__slots__` Works

```
┌─────────────────────────────────────────────────────────────────┐
│                    __slots__ Internals                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Without __slots__:                                              │
│  ┌─────────────────────────────┐                                │
│  │  Instance                    │                                │
│  │  ├── ob_refcnt              │                                │
│  │  ├── ob_type                │                                │
│  │  └── __dict__ ──▶ {'x': 1, 'y': 2}                          │
│  └─────────────────────────────┘                                │
│                                                                  │
│  With __slots__ = ['x', 'y']:                                   │
│  ┌─────────────────────────────┐                                │
│  │  Instance                    │                                │
│  │  ├── ob_refcnt              │                                │
│  │  ├── ob_type                │                                │
│  │  ├── x (at fixed offset)    │  No dict, just slots!         │
│  │  └── y (at fixed offset)    │                                │
│  └─────────────────────────────┘                                │
│                                                                  │
│  Class has member descriptors:                                   │
│  Point.x = <member_descriptor at offset 0>                      │
│  Point.y = <member_descriptor at offset 1>                      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### `__slots__` Caveats

```python
class Base:
    __slots__ = ['x']

class Derived(Base):
    __slots__ = ['y']  # Only add new slots

d = Derived()
d.x = 1  # From Base
d.y = 2  # From Derived

# If you forget __slots__ in derived class, it gets __dict__
class DerivedWithDict(Base):
    pass  # No __slots__ means __dict__ is added

d2 = DerivedWithDict()
d2.x = 1
d2.z = 3  # OK - has __dict__
```

## Custom Descriptor Examples

### Validated Attribute

```python
class Validated:
    def __set_name__(self, owner, name):
        self.name = name
        self.storage_name = f'_validated_{name}'

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return getattr(obj, self.storage_name, None)

    def __set__(self, obj, value):
        self.validate(value)
        setattr(obj, self.storage_name, value)

    def validate(self, value):
        pass  # Override in subclasses

class PositiveNumber(Validated):
    def validate(self, value):
        if value <= 0:
            raise ValueError(f"{self.name} must be positive")

class Person:
    age = PositiveNumber()

p = Person()
p.age = 25   # OK
# p.age = -5  # ValueError: age must be positive
```

### Cached Property

```python
class cached_property:
    """Compute once, then cache in instance __dict__."""

    def __init__(self, func):
        self.func = func
        self.__doc__ = func.__doc__

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        # Compute and cache in instance dict
        value = self.func(obj)
        obj.__dict__[self.name] = value  # Shadows descriptor
        return value

class DataLoader:
    @cached_property
    def data(self):
        print("Loading data...")
        return [1, 2, 3, 4, 5]

loader = DataLoader()
print(loader.data)  # Loading data... [1, 2, 3, 4, 5]
print(loader.data)  # [1, 2, 3, 4, 5] (cached, no "Loading...")
```

## Summary

- **Descriptors** customize attribute access via `__get__`, `__set__`, `__delete__`
- **Data descriptors** (have `__set__`) take priority over instance `__dict__`
- **Non-data descriptors** (only `__get__`) can be shadowed by instance attributes
- **property** is a built-in data descriptor
- **Functions** are non-data descriptors that bind methods
- **`__slots__`** creates member descriptors for memory efficiency

## Practice Exercises

1. Implement a `LazyProperty` descriptor that computes value on first access
2. Create a `TypedAttribute` descriptor that validates types
3. Build a `ReadOnly` descriptor that prevents modification after initial set
4. Understand why `property` is a data descriptor

---

[← Previous: Type System](chapter-14-type-system.md) | [Next: Built-in Types Internals →](chapter-16-builtin-types.md)

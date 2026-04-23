# OOP in Python — Deep Dive

## Table of Contents

- [1. Classes & Objects](#1-classes--objects)
- [2. The Four Pillars](#2-the-four-pillars)
- [3. MRO (Method Resolution Order)](#3-mro-method-resolution-order)
- [4. Dunder (Magic) Methods](#4-dunder-magic-methods)
- [5. classmethod vs staticmethod vs Instance Method](#5-classmethod-vs-staticmethod-vs-instance-method)
- [6. Descriptors](#6-descriptors)
- [7. Metaclasses](#7-metaclasses)
- [8. `__slots__`](#8-__slots__)
- [9. Dataclasses](#9-dataclasses)
- [10. Protocols (Structural Subtyping)](#10-protocols-structural-subtyping--python-38)
- [11. Mixins](#11-mixins)
- [12. `__new__` vs `__init__`](#12-__new__-vs-__init__)
- [13. Attribute Lookup Chain](#13-attribute-lookup-chain--__getattr__-vs-__getattribute__)
- [14. `__call__` — Callable Objects](#14-__call__--callable-objects)
- [15. Composition vs Inheritance](#15-composition-vs-inheritance)
- [16. Enum](#16-enum)
- [17. `isinstance()` vs `type()`](#17-isinstance-vs-type)
- [18. Abstract Properties](#18-abstract-properties)
- [19. Class Decorators](#19-class-decorators)
- [20. `__bool__` — Truthiness Protocol](#20-__bool__--truthiness-protocol)
- [21. Copy Protocol](#21-copy-protocol)
- [22. Weak References](#22-weak-references)
- [23. `__subclasshook__`](#23-__subclasshook__--abc-isinstance-customization)
- [24. Pickle Protocol](#24-pickle-protocol)
- [25. `__class_getitem__` — Generic Classes](#25-__class_getitem__--generic-classes)
- [Interview-Critical Summary](#interview-critical-summary)

---

## 1. Classes & Objects

A **class** is a blueprint that defines the structure (attributes) and behavior (methods) of objects. An **object** is a concrete instance of a class, with its own state stored in instance attributes. In Python, everything is an object — even classes themselves are objects (instances of `type`).

```python
class Account:
    bank_name: str = "Revolut"  # class attribute — shared across all instances

    def __init__(self, account_id: int, balance: Decimal = Decimal("0")):
        self.account_id = account_id  # instance attribute
        self.balance = balance

    def __repr__(self) -> str:
        return f"Account(id={self.account_id}, balance={self.balance})"
```

- `__init__` is the **initializer**, not the constructor — `__new__` is the actual constructor
- `self` is the instance reference, passed implicitly
- Class attributes live on the class object; instance attributes on the instance

---

## 2. The Four Pillars

### Encapsulation

Encapsulation is access control. It is the process of protecting or controlling access to the data by only exposing required attributes and methods.

- In Java, this can be achieved using access modifiers - private, public, protected access members
- In Python, we have things like @property. But no true way of creating private members. Python has no true private - it uses **name mangling**. When you add a double underscope python renames it using \_ClassName\_\_<attribute_name>, it prevents accidental access and name collisions in subclasses:

```python
class Account:
    def __init__(self, balance: Decimal):
        self._balance = balance        # "protected" by convention (single underscore)
        self.__internal_id = "secret"  # name-mangled to _Account__internal_id

a = Account(Decimal("100"))
a._balance          # works — convention only
a.__internal_id     # AttributeError
a._Account__internal_id  # works — mangling is not security
```

Use `@property` for controlled access:

```python
class Account:
    def __init__(self, balance: Decimal):
        self._balance = balance

    @property
    def balance(self) -> Decimal:
        return self._balance

    @balance.setter
    def balance(self, value: Decimal) -> None:
        if value < 0:
            raise ValueError("Balance cannot be negative")
        self._balance = value
```

### Inheritance

A mechanism where a child class acquires the attributes and methods of a parent class, enabling code reuse and hierarchical modeling.

- Python supports **multiple inheritance**, where a class can inherit from more than one parent — resolved via MRO (C3 Linearization).

```python
class Animal:
    def speak(self) -> str:
        raise NotImplementedError

class Dog(Animal):
    def speak(self) -> str:
        return "Woof"
```

Python supports **multiple inheritance** — this is where MRO matters.

### Polymorphism

Polymorphism means "Many forms". It means the same operation behaves differently depending on who is calling it. In Java you have static and dynamic polymorphism. Static is operator overloading - same method name, different signatures. The compiler picks which one to call based on argument types at compile time.

Python supports three forms:

**1. Duck typing** — Python's default. No inheritance or interface needed. If the object has the method, it works.

```python
class RoundRobin:
    def select_server(self, instances: list[str]) -> str:
        return instances[0]

class Random:
    def select_server(self, instances: list[str]) -> str:
        import random
        return random.choice(instances)

def process(strategy, servers: list[str]) -> str:
    return strategy.select_server(servers)  # works with ANY object that has this method

process(RoundRobin(), ["a", "b"])  # "a"
process(Random(), ["a", "b"])      # random pick
```

**2. Inheritance-based** — subclasses override a parent method. The caller codes against the parent type. This is also called dynamic polymorphism or methor overriding.

```python
class Animal:
    def speak(self) -> str:
        raise NotImplementedError

class Dog(Animal):
    def speak(self) -> str:
        return "Woof"

class Cat(Animal):
    def speak(self) -> str:
        return "Meow"

def make_noise(animal: Animal) -> str:
    return animal.speak()  # dispatches to the subclass implementation
```

**3. Operator overloading** — same operator, different behavior per type via dunders.

```python
1 + 2          # int.__add__ → 3
"a" + "b"      # str.__add__ → "ab"
[1] + [2]      # list.__add__ → [1, 2]
# same `+` operator, three different types, three different behaviors
```

**Interview framing:** "Polymorphism lets me write `process(strategy)` once and have it work with any object that satisfies the expected behavior. In Java you'd need an explicit interface; in Python, duck typing gives you this for free — but you can formalize it with `ABC` or `Protocol` when you want to be explicit."

### Abstraction

Abstraction is about hiding implementation details either using an interface or abstract classes. In Python, we can achieve this via `ABC` (Abstract Base Class) with `@abstractmethod` — subclasses must implement the abstract methods, and the ABC itself cannot be instantiated.

```python
from abc import ABC, abstractmethod

class ServerSelectionStrategy(ABC):
    @abstractmethod
    def select_server(self, instances: list[str]) -> str: ...
        # Can't instantiate ABC directly — forces subclassing
```

## 3. MRO (Method Resolution Order)

The order in which Python searches the class hierarchy for a method or attribute. Computed using **C3 Linearization** — a deterministic algorithm that guarantees: a class appears before its parents, left parents before right parents, and each class appears only once. Accessible via `ClassName.__mro__` or `ClassName.mro()`.

Python uses **C3 Linearization** to resolve the diamond problem:

```python
class A:
    def method(self) -> str:
        return "A"

class B(A):
    def method(self) -> str:
        return "B"

class C(A):
    def method(self) -> str:
        return "C"

class D(B, C):
    pass

d = D()
d.method()  # "B" — follows MRO
print(D.__mro__)
# (D, B, C, A, object)
# Left-to-right, children before parents, shared parents deferred until ALL children appear
# NOT depth-first — naive DFS would give D,B,A,C but C3 gives D,B,C,A (A waits for both B and C)
```

**Key rule:** A class always appears before its parents, and left parents before right parents. A shared parent is placed only after **all** of its children have appeared — this is what makes C3 different from naive depth-first.

### `super()` and MRO

```python
class A:
    def method(self) -> str:
        return "A"

class B(A):
    def method(self) -> str:
        return f"B -> {super().method()}"

class C(A):
    def method(self) -> str:
        return f"C -> {super().method()}"

class D(B, C):
    def method(self) -> str:
        return f"D -> {super().method()}"

D().method()  # "D -> B -> C -> A"
# super() follows MRO, NOT the parent class
# B.super() goes to C (next in MRO), not A (parent)
```

**Critical insight:** `super()` doesn't mean "parent" — it means "next in MRO". This is why cooperative multiple inheritance works.

## 4. Dunder (Magic) Methods

Special methods surrounded by double underscores (`__method__`) that Python calls implicitly for operators, built-in functions, and protocols. They define how objects behave with `+`, `==`, `len()`, `str()`, `in`, iteration, context managers, and more. You never call them directly — Python's syntax and built-ins dispatch to them.

### Representation

```python
class Money:
    def __init__(self, amount: Decimal, currency: str = "USD"):
        self.amount = amount
        self.currency = currency
d
    def __repr__(self) -> str:  # for developers — unambiguous
        return f"Money({self.amount}, '{self.currency}')"

    def __str__(self) -> str:   # for users — readable
        return f"${self.amount:.2f}"

    # repr is fallback when str is not defined
    # repr should ideally be valid Python that recreates the object
```

### Equality and Hashing

```python
class Money:
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Money):
            return NotImplemented  # not False — lets other side try
        return self.amount == other.amount and self.currency == other.currency

    def __hash__(self) -> int:
        return hash((self.amount, self.currency))
```

**Why `hash((tuple))`?** `hash()` needs a single immutable value. A tuple combines multiple fields into one hashable object, and Python's built-in tuple hashing produces well-distributed integers. This is the standard idiom — use exactly the same fields as `__eq__` (or a subset, never extra fields).

**Critical contract:**

- If `a == b`, then `hash(a) == hash(b)` — MUST hold
- If `hash(a) == hash(b)`, `a == b` MAY be false — collision
- If you define `__eq__`, Python sets `__hash__ = None` (unhashable)
- You **must** define `__hash__` explicitly if instances go in sets or dict keys

**Why mutable types are unhashable:**

Python's rule: **mutable → unhashable**. If you could hash a list and use it as a dict key, then mutate it, the hash would change but the dict still stores it under the old hash — the value becomes unreachable.

```python
hash([1, 2, 3])  # TypeError: unhashable type: 'list'
```

| Mutable (unhashable) | Immutable (hashable) |
| -------------------- | -------------------- |
| `list`               | `tuple`              |
| `dict`               | `tuple(d.items())`   |
| `set`                | `frozenset`          |

This is also why Python sets `__hash__ = None` when you define `__eq__` — it assumes if you're comparing by value, the object might be mutable, so it defensively makes it unhashable until you explicitly define `__hash__`.

### Comparison

```python
from functools import total_ordering

@total_ordering  # generates __le__, __gt__, __ge__ from __lt__ and __eq__
class Money:
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        return self.amount == other.amount

    def __lt__(self, other: "Money") -> bool:
        return self.amount < other.amount
```

### Arithmetic

```python
class Money:
    def __add__(self, other: "Money") -> "Money":
        self._check_currency(other)
        return Money(self.amount + other.amount, self.currency)

    def __radd__(self, other: "Money") -> "Money":  # reflected — when left side doesn't know how
        return self.__add__(other)

    def __iadd__(self, other: "Money") -> "Money":   # in-place: m += other
        self._check_currency(other)
        self.amount += other.amount
        return self
```

### Container Protocol

```python
class Portfolio:
    def __init__(self):
        self._assets: list[str] = []

    def __len__(self) -> int:               # len(portfolio)
        return len(self._assets)

    def __getitem__(self, index: int) -> str:  # portfolio[0]
        return self._assets[index]

    def __setitem__(self, index: int, value: str) -> None:  # portfolio[0] = "AAPL"
        self._assets[index] = value

    def __contains__(self, item: str) -> bool:  # "AAPL" in portfolio
        return item in self._assets

    def __iter__(self):                     # for asset in portfolio
        return iter(self._assets)
```

### Iterator Protocol

An **iterable** is any object with `__iter__` that returns an **iterator**. An **iterator** is an object with `__next__` that yields values one at a time and raises `StopIteration` when exhausted. Iterators are also iterables (their `__iter__` returns `self`). This is the protocol behind `for` loops, comprehensions, `list()`, `tuple()`, unpacking, and `*args`.

```python
class Countdown:
    def __init__(self, start: int):
        self.start = start

    def __iter__(self) -> "CountdownIterator":
        return CountdownIterator(self.start)  # returns a NEW iterator each time

class CountdownIterator:
    def __init__(self, current: int):
        self.current = current

    def __iter__(self) -> "CountdownIterator":
        return self  # iterators return themselves

    def __next__(self) -> int:
        if self.current <= 0:
            raise StopIteration
        val = self.current
        self.current -= 1
        return val

c = Countdown(3)
list(c)   # [3, 2, 1]
list(c)   # [3, 2, 1] — fresh iterator each time because __iter__ creates new CountdownIterator
```

**Why separate iterable from iterator?** So you can iterate multiple times. If the object itself is the iterator (returns `self` from `__iter__`), it exhausts after one pass:

```python
class OneShotRange:
    def __init__(self, n: int):
        self.n = n
        self.current = 0

    def __iter__(self) -> "OneShotRange":
        return self  # returns self — single-use

    def __next__(self) -> int:
        if self.current >= self.n:
            raise StopIteration
        val = self.current
        self.current += 1
        return val

r = OneShotRange(3)
list(r)  # [0, 1, 2]
list(r)  # [] — exhausted, __next__ immediately raises StopIteration
```

**Generator functions** are the Pythonic shortcut — `yield` handles `__iter__`, `__next__`, and `StopIteration` automatically:

```python
def countdown(start: int):
    while start > 0:
        yield start
        start -= 1

list(countdown(3))  # [3, 2, 1]

# Generator is an iterator — single use
gen = countdown(3)
list(gen)  # [3, 2, 1]
list(gen)  # [] — exhausted
```

**`__reversed__`** — called by `reversed()`. Without it, `reversed()` falls back to `__len__` + `__getitem__`:

```python
class Countdown:
    def __init__(self, start: int):
        self.start = start

    def __iter__(self):
        for i in range(self.start, 0, -1):
            yield i

    def __reversed__(self):
        for i in range(1, self.start + 1):
            yield i

list(reversed(Countdown(3)))  # [1, 2, 3]
```

| Concept       | Has                     | Returns                | Exhaustible                  |
| ------------- | ----------------------- | ---------------------- | ---------------------------- |
| **Iterable**  | `__iter__`              | A new iterator         | No — creates fresh iterators |
| **Iterator**  | `__iter__` + `__next__` | `self` from `__iter__` | Yes — one pass only          |
| **Generator** | Both (auto)             | Itself                 | Yes — one pass only          |

### Context Manager Protocol

```python
class DatabaseConnection:
    def __enter__(self) -> "DatabaseConnection":
        self.conn = connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.conn.close()
        return False  # True would suppress exceptions

# with DatabaseConnection() as db:
#     db.query(...)
# __exit__ always called, even on exception
```

## 5. classmethod vs staticmethod vs Instance Method

An **instance method** receives `self` and operates on instance state. A **classmethod** receives `cls` (the class itself) instead of an instance — used for alternative constructors and class-level state; it respects inheritance so `cls` refers to the subclass when called on one. A **staticmethod** receives neither `self` nor `cls` — a utility function that's logically grouped with the class but needs no access to class or instance state.

```python
class Account:
    _instances: list["Account"] = []

    def __init__(self, account_id: int):
        self.account_id = account_id
        Account._instances.append(self)

    def get_id(self) -> int:                        # instance method — gets self
        return self.account_id

    @classmethod
    def from_string(cls, data: str) -> "Account":   # gets cls, not self
        account_id = int(data.split(":")[1])
        return cls(account_id)                       # works with subclasses too!

    @classmethod
    def get_all(cls) -> list["Account"]:             # access class state
        return cls._instances

    @staticmethod
    def validate_id(account_id: int) -> bool:        # gets neither — utility
        return account_id > 0
```

| Type            | Receives | Use case                                                     |
| --------------- | -------- | ------------------------------------------------------------ |
| Instance method | `self`   | Needs instance state (most common)                           |
| `@classmethod`  | `cls`    | Alternative constructors, factory pattern, class-level state |
| `@staticmethod` | nothing  | Utility logically related to class but needs no state        |

**Key difference:** `@classmethod` respects inheritance — `cls` refers to the subclass when called on one. `@staticmethod` doesn't know which class it's on.

---

## 6. Descriptors

Decriptors are objects that allows you to customize attribute access by implementing `__get__`, `__set__`, or `__delete__`. Descriptors are the underlying mechanism behind `@property`, `@classmethod`, `@staticmethod`, and `__slots__`. A **data descriptor** (has `__set__` or `__delete__`) takes priority over instance `__dict__`; a **non-data descriptor** (only `__get__`) is overridden by instance `__dict__`.

The mechanism behind `@property`, `@classmethod`, `@staticmethod`, and `__slots__`.

```python
class Validator:
    def __init__(self, min_value: Decimal):
        self.min_value = min_value
        self.attr_name: str = ""

    def __set_name__(self, owner: type, name: str) -> None:
        self.attr_name = f"_{name}"

    def __get__(self, obj: object, objtype: type = None) -> Decimal:
        if obj is None:
            return self  # accessed on class, not instance
        return getattr(obj, self.attr_name)

    def __set__(self, obj: object, value: Decimal) -> None:
        if value < self.min_value:
            raise ValueError(f"Must be >= {self.min_value}")
        setattr(obj, self.attr_name, value)

class Account:
    balance = Validator(min_value=Decimal("0"))  # reusable validation

    def __init__(self, balance: Decimal):
        self.balance = balance  # triggers Validator.__set__
```

### Descriptor Protocol

| Method                            | Called when                    |
| --------------------------------- | ------------------------------ |
| `__get__(self, obj, type)`        | Attribute accessed             |
| `__set__(self, obj, value)`       | Attribute assigned             |
| `__delete__(self, obj)`           | Attribute deleted              |
| `__set_name__(self, owner, name)` | Class is created (Python 3.6+) |

`__set_name__` is called automatically by `type` metaclass during class creation. `owner` is the class the descriptor is attached to, and `name` is the attribute name it was assigned to. For example, `balance = Validator(...)` results in `balance.__set_name__(Account, "balance")`. Each descriptor instance learns its own name this way.

**Data descriptor** (has `__set__` or `__delete__`) takes priority over instance `__dict__`.
**Non-data descriptor** (only `__get__`) is overridden by instance `__dict__`.

### How `@property`, `@classmethod`, `@staticmethod` Are Built With Descriptors

All three are descriptors with different `__get__` behavior:

| Decorator      | `__get__` returns                          | Binding  |
| -------------- | ------------------------------------------ | -------- |
| `property`     | `fget(obj)` — calls the getter immediately | instance |
| `classmethod`  | wrapped func with `cls` injected           | class    |
| `staticmethod` | raw function, untouched                    | nothing  |

#### Pure Python `property`

```python
class property:
    def __init__(self, fget=None, fset=None, fdel=None):
        self.fget = fget
        self.fset = fset
        self.fdel = fdel

    def __get__(self, obj: object, objtype: type = None):
        if obj is None:
            return self          # Account.balance → returns the property object
        return self.fget(obj)    # account.balance → calls fget(account)

    def __set__(self, obj: object, value) -> None:
        if self.fset is None:
            raise AttributeError("can't set attribute")
        self.fset(obj, value)    # account.balance = 10 → calls fset(account, 10)

    def __delete__(self, obj: object) -> None:
        if self.fdel is None:
            raise AttributeError("can't delete attribute")
        self.fdel(obj)

    def setter(self, fset):
        return property(self.fget, fset, self.fdel)  # returns NEW property with fset added

    def deleter(self, fdel):
        return property(self.fget, self.fset, fdel)
```

`@property` replaces the function with a **data descriptor** (has `__set__`). That's why it wins over `__dict__` — and why `account.balance` runs your getter instead of returning a raw value.

```python
class Account:
    @property              # balance = property(fget=balance)
    def balance(self) -> Decimal:
        return self._balance

    @balance.setter        # balance = balance.setter(fset=new_func) → new property object
    def balance(self, value: Decimal) -> None:
        self._balance = value
```

#### Pure Python `classmethod`

```python
class classmethod:
    def __init__(self, func):
        self.func = func

    def __get__(self, obj: object, objtype: type = None):
        if objtype is None:
            objtype = type(obj)

        def bound(*args, **kwargs):
            return self.func(objtype, *args, **kwargs)  # injects the CLASS as first arg
        return bound
```

`__get__` always binds the **class** as the first argument, regardless of whether called on the class or an instance.

```python
class Foo:
    @classmethod           # from_str = classmethod(from_str)
    def from_str(cls, s: str) -> "Foo":
        return cls(int(s))

Foo.from_str("42")         # __get__(None, Foo) → binds cls=Foo
Foo().from_str("42")       # __get__(instance, Foo) → still binds cls=Foo
```

#### Pure Python `staticmethod`

```python
class staticmethod:
    def __init__(self, func):
        self.func = func

    def __get__(self, obj: object, objtype: type = None):
        return self.func  # returns the raw function — no binding at all
```

No `self`, no `cls` — just returns the unwrapped function.

### Data vs Non-Data Descriptors — Lookup Priority

The distinction matters because of where they sit in the attribute lookup chain:

```
1. Data descriptors from type(obj).__mro__     ← @property, __slots__, custom with __set__
2. Instance __dict__
3. Non-data descriptors from type(obj).__mro__  ← functions, @staticmethod, @classmethod
4. __getattr__() fallback
```

```python
class DataDesc:
    def __get__(self, obj, objtype=None) -> str:
        return "from data descriptor"
    def __set__(self, obj, value) -> None:
        pass  # having __set__ makes it a data descriptor

class NonDataDesc:
    def __get__(self, obj, objtype=None) -> str:
        return "from non-data descriptor"

class MyClass:
    data = DataDesc()
    nondata = NonDataDesc()

obj = MyClass()
obj.__dict__["data"] = "from instance"
obj.__dict__["nondata"] = "from instance"

obj.data      # "from data descriptor"  — data descriptor wins over instance __dict__
obj.nondata   # "from instance"         — instance __dict__ wins over non-data descriptor
```

This is why `@property` (a data descriptor) can intercept attribute access — it sits above `__dict__` in lookup priority. Regular methods (non-data descriptors) can be shadowed by instance attributes.

### `__set_name__` — Automatic Name Binding

Called at class creation time when the descriptor is assigned to a class variable. Eliminates the need to pass the attribute name manually.

```python
class Typed:
    def __init__(self, expected_type: type):
        self.expected_type = expected_type
        self.attr_name: str = ""

    def __set_name__(self, owner: type, name: str) -> None:
        self.attr_name = f"_{name}"  # owner=Person, name="age"

    def __get__(self, obj: object, objtype: type = None):
        if obj is None:
            return self
        return getattr(obj, self.attr_name, None)

    def __set__(self, obj: object, value) -> None:
        if not isinstance(value, self.expected_type):
            raise TypeError(f"{self.attr_name[1:]} must be {self.expected_type.__name__}")
        setattr(obj, self.attr_name, value)

class Person:
    name = Typed(str)   # __set_name__ called with name="name"
    age = Typed(int)    # __set_name__ called with name="age"

    def __init__(self, name: str, age: int):
        self.name = name  # triggers Typed.__set__
        self.age = age

p = Person("Alice", 30)
p.age = "old"  # TypeError: age must be int
```

Without `__set_name__`, you'd have to write `name = Typed(str, "name")` — duplicating the attribute name.

### `__delete__` — Controlling Attribute Deletion

```python
class Protected:
    def __set_name__(self, owner: type, name: str) -> None:
        self.attr_name = f"_{name}"

    def __get__(self, obj: object, objtype: type = None):
        if obj is None:
            return self
        return getattr(obj, self.attr_name)

    def __set__(self, obj: object, value) -> None:
        setattr(obj, self.attr_name, value)

    def __delete__(self, obj: object) -> None:
        raise AttributeError("Cannot delete this attribute")

class Config:
    api_key = Protected()

    def __init__(self, api_key: str):
        self.api_key = api_key

c = Config("secret")
del c.api_key  # AttributeError: Cannot delete this attribute
```

### Accessing Descriptor on Class vs Instance

When `obj` is `None` in `__get__`, the descriptor was accessed on the **class**, not an instance.

```python
class Verbose:
    def __get__(self, obj: object, objtype: type = None):
        if obj is None:
            return self          # class-level access: MyClass.attr
        return "instance value"  # instance-level access: obj.attr

class MyClass:
    attr = Verbose()

MyClass.attr      # returns the Verbose descriptor object itself
MyClass().attr    # returns "instance value"
```

This is the same pattern `property` uses — accessing a property on the class returns the property object, not calling the getter.

### How Functions Are Descriptors

Regular functions are **non-data descriptors**. Their `__get__` is what turns `func` into a bound method.

```python
class Dog:
    def bark(self) -> str:
        return "woof"

# When you call dog.bark(), Python does:
# type(dog).__dict__["bark"].__get__(dog, Dog)
# which returns a bound method with `self` = dog

dog = Dog()
Dog.__dict__["bark"]           # <function Dog.bark>  — raw function
Dog.__dict__["bark"].__get__(dog, Dog)  # <bound method Dog.bark of <Dog object>>
dog.bark                       # same as above — Python does this automatically
```

This is why you can shadow a method with an instance attribute:

```python
dog.__dict__["bark"] = lambda: "meow"
dog.bark()  # "meow" — instance __dict__ wins over non-data descriptor
```

### How `@staticmethod` and `@classmethod` Work

Both are descriptors that customize what `__get__` returns:

```python
class MyStaticMethod:
    def __init__(self, func):
        self.func = func

    def __get__(self, obj: object, objtype: type = None):
        return self.func  # returns the raw function — no binding

class MyClassMethod:
    def __init__(self, func):
        self.func = func

    def __get__(self, obj: object, objtype: type = None):
        if objtype is None:
            objtype = type(obj)
        return self.func.__get__(objtype, type)  # binds to the class, not instance
```

### Descriptor with `__slots__`

`__slots__` creates **data descriptors** at the class level — one `member_descriptor` per slot name. These descriptors store values in a compact internal array rather than an instance `__dict__`.

```python
class Point:
    __slots__ = ("x", "y")

type(Point.x)  # <class 'member_descriptor'> — a data descriptor
# Point.x has __get__ and __set__, so it's a data descriptor
# This is why slotted attributes beat instance __dict__ (which doesn't even exist)
```

### Reusable Validation Descriptors — Stacking Multiple

The real power of descriptors is reusability across many classes:

```python
class RangeChecked:
    def __init__(self, min_val: float = float("-inf"), max_val: float = float("inf")):
        self.min_val = min_val
        self.max_val = max_val

    def __set_name__(self, owner: type, name: str) -> None:
        self.attr_name = f"_{name}"

    def __get__(self, obj: object, objtype: type = None):
        if obj is None:
            return self
        return getattr(obj, self.attr_name)

    def __set__(self, obj: object, value: float) -> None:
        if not self.min_val <= value <= self.max_val:
            raise ValueError(f"Must be between {self.min_val} and {self.max_val}")
        setattr(obj, self.attr_name, value)

class Product:
    price = RangeChecked(min_val=0, max_val=10000)
    weight = RangeChecked(min_val=0, max_val=500)
    rating = RangeChecked(min_val=0, max_val=5)

class Employee:
    salary = RangeChecked(min_val=30000, max_val=500000)
    age = RangeChecked(min_val=18, max_val=120)
```

One descriptor class, used across multiple unrelated classes — this is what makes descriptors more powerful than `@property` for cross-cutting validation.

### Descriptor vs `@property` — When to Use Which

| Use case                                      | Preferred   |
| --------------------------------------------- | ----------- |
| One-off getter/setter on a single class       | `@property` |
| Same validation logic on multiple attributes  | Descriptor  |
| Same validation logic across multiple classes | Descriptor  |
| Controlling method binding behavior           | Descriptor  |
| Building a framework / ORM                    | Descriptor  |

`@property` is itself a descriptor — it's the convenient single-use wrapper. Write custom descriptors when you need reuse.

### Interview Pitfall: Descriptor on the Instance

Descriptors **must** be defined on the class, not the instance. Putting a descriptor in `__dict__` does nothing.

```python
class Desc:
    def __get__(self, obj, objtype=None):
        return 42

class Broken:
    def __init__(self):
        self.attr = Desc()  # stored in instance __dict__ — NOT a descriptor

Broken().attr  # returns the Desc object, not 42

class Working:
    attr = Desc()  # class variable — this IS a descriptor

Working().attr  # returns 42
```

Python only invokes the descriptor protocol for attributes found on the **type** (class), not the instance.

---

## 7. Metaclasses

Metaclasses are classes that allows you to control the behavior of creating other classes. They inherit from type, and are instance of the type. `type` is the default metaclass of all classes (including itself). The creation chain is: `metaclass.__call__()` → `cls.__new__()` → `cls.__init__()`. Custom metaclasses let you intercept class creation for patterns like singleton enforcement, automatic registration, or schema validation.

Classes are objects in Python. Metaclasses are classes that create classes.

```
type is the metaclass of all classes (including itself)
object is the base class of all classes
type is an instance of type
type is a subclass of object
object is an instance of type
```

### Object Creation Chain

```
metaclass.__call__()
    -> cls.__new__(cls)          # creates the instance
    -> cls.__init__(self)        # initializes the instance
```

### Custom Metaclass

```python
class SingletonMeta(type):
    _instances: dict[type, object] = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]

class Database(metaclass=SingletonMeta):
    def __init__(self):
        self.connection = "connected"

db1 = Database()
db2 = Database()
assert db1 is db2  # same instance
```

### `__init_subclass__` — Lightweight Alternative to Metaclasses (Python 3.6+)

```python
class Plugin:
    _registry: dict[str, type] = {}

    def __init_subclass__(cls, name: str = "", **kwargs):
        super().__init_subclass__(**kwargs)
        Plugin._registry[name or cls.__name__] = cls

class AuthPlugin(Plugin, name="auth"):
    pass

class CachePlugin(Plugin, name="cache"):
    pass

Plugin._registry  # {"auth": AuthPlugin, "cache": CachePlugin}
```

Prefer `__init_subclass__` over metaclasses when you just need to hook into subclass creation.

## 8. `__slots__`

A class-level declaration that replaces the per-instance `__dict__` with a fixed set of attribute slots. This saves ~40% memory and provides faster attribute access, at the cost of losing the ability to add arbitrary attributes at runtime. Best suited for classes with millions of instances (e.g., transaction records, data points).

```python
class HeavyAccount:
    def __init__(self, id: int, balance: Decimal):
        self.id = id
        self.balance = balance
    # Has __dict__ per instance — flexible but memory-heavy

class LightAccount:
    __slots__ = ("id", "balance")

    def __init__(self, id: int, balance: Decimal):
        self.id = id
        self.balance = balance
    # No __dict__ — ~40% less memory, faster attribute access
    # Cannot add arbitrary attributes at runtime
```

**Trade-offs:**

|                      | `__dict__`                 | `__slots__`                                        |
| -------------------- | -------------------------- | -------------------------------------------------- |
| Memory               | Higher (dict per instance) | ~40% less                                          |
| Attribute access     | Slightly slower            | Faster                                             |
| Dynamic attributes   | Yes                        | No                                                 |
| Multiple inheritance | Easy                       | Complex (only one parent can have non-empty slots) |
| Use case             | Default, most classes      | Millions of instances (e.g., transaction records)  |

## 9. Dataclasses

A decorator (`@dataclass`) that auto-generates `__init__`, `__repr__`, `__eq__`, and optionally `__hash__`, `__lt__`, etc. from annotated class fields. Reduces boilerplate for data-holding classes. Use `frozen=True` for immutability, `field(default_factory=...)` for mutable defaults, and `__post_init__` for validation after construction.

```python
from dataclasses import dataclass, field
from decimal import Decimal

@dataclass(frozen=True)  # frozen = immutable = hashable
class Transaction:
    from_account: int
    to_account: int
    amount: Decimal
    currency: str = "USD"
    tags: list[str] = field(default_factory=list)

    def __post_init__(self):
        if self.amount <= 0:
            raise ValueError("Amount must be positive")

# Auto-generates: __init__, __repr__, __eq__, __hash__ (if frozen)
t = Transaction(1, 2, Decimal("100"))
```

### Dataclass Parameters

| Parameter | Default | Effect                                 |
| --------- | ------- | -------------------------------------- |
| `init`    | True    | Generate `__init__`                    |
| `repr`    | True    | Generate `__repr__`                    |
| `eq`      | True    | Generate `__eq__`                      |
| `order`   | False   | Generate `__lt__`, `__le__`, etc.      |
| `frozen`  | False   | Make instances immutable               |
| `slots`   | False   | Generate `__slots__` (Python 3.10+)    |
| `kw_only` | False   | All fields keyword-only (Python 3.10+) |

### `field()` Options

```python
@dataclass
class Config:
    name: str                                       # required
    debug: bool = False                             # simple default
    items: list[str] = field(default_factory=list)  # mutable default — MUST use factory
    _cache: dict = field(repr=False, compare=False, default_factory=dict)  # excluded from repr/eq
    id: int = field(init=False)                     # not in __init__, set in __post_init__
```

### Dataclass vs NamedTuple

|              | `dataclass`                             | `NamedTuple`     |
| ------------ | --------------------------------------- | ---------------- |
| Mutable      | By default (use `frozen` for immutable) | Always immutable |
| Base class   | `object`                                | `tuple`          |
| Index access | No                                      | Yes (`t[0]`)     |
| Inheritance  | Full                                    | Limited          |
| Memory       | Normal object                           | Tuple (lighter)  |
| Unpacking    | No                                      | Yes (`a, b = t`) |

## 10. Protocols (Structural Subtyping) — Python 3.8+

A `typing.Protocol` subclass that defines **structural subtyping** — a class satisfies the protocol if it has the matching methods/attributes, with no inheritance required. This formalizes Python's duck typing for static type checkers (mypy/pyright). Use `@runtime_checkable` to also enable `isinstance()` checks at runtime.

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class Selectable(Protocol):
    def select_server(self, instances: list[str]) -> str: ...

class MyStrategy:  # no inheritance needed!
    def select_server(self, instances: list[str]) -> str:
        return instances[0]

def use_strategy(s: Selectable) -> str:
    return s.select_server(["a", "b"])

use_strategy(MyStrategy())  # type-checks fine — structural match
isinstance(MyStrategy(), Selectable)  # True at runtime with @runtime_checkable
```

### Protocol vs ABC

|              | `ABC`                                      | `Protocol`                               |
| ------------ | ------------------------------------------ | ---------------------------------------- |
| Subtyping    | Nominal — must explicitly inherit          | Structural — just match the shape        |
| `isinstance` | Always works                               | Only with `@runtime_checkable`           |
| Enforcement  | Runtime (can't instantiate ABC)            | Static (mypy/pyright)                    |
| Philosophy   | Java-style interfaces                      | Duck typing formalized                   |
| Use when     | Need runtime checks, shared implementation | Type checking, third-party compatibility |

---

## 11. Mixins

A small, focused class that provides a single reusable capability via multiple inheritance. Mixins should not hold state, should not define `__init__`, and should be named with a `Mixin` suffix. They add behavior (like serialization or logging) without creating tight coupling or deep hierarchies.

```python
class JsonMixin:
    def to_json(self) -> str:
        import json
        return json.dumps(self.__dict__)

class LogMixin:
    def log(self, message: str) -> None:
        print(f"[{self.__class__.__name__}] {message}")

class Account(JsonMixin, LogMixin):
    def __init__(self, id: int, balance: Decimal):
        self.id = id
        self.balance = balance

a = Account(1, Decimal("100"))
a.to_json()       # '{"id": 1, "balance": "100"}'
a.log("created")  # [Account] created
```

**Mixin rules:**

- Should not have `__init__` (or call `super().__init__`)
- Should provide a single, focused capability
- Should not hold state
- Name them with `Mixin` suffix for clarity

## 12. `__new__` vs `__init__`

`__new__` is the actual **constructor** — it allocates memory and returns a new instance. `__init__` is the **initializer** — it sets up state on the already-created object. `__new__` is the only way to customize creation of immutable types (`str`, `int`, `tuple`) because by the time `__init__` runs, the object is already frozen. Note: `__init__` is called every time even if `__new__` returns an existing instance (important for singletons).

`__new__` creates the instance. `__init__` initializes it.

```python
class Singleton:
    _instance: "Singleton | None" = None

    def __new__(cls, *args, **kwargs) -> "Singleton":
        if cls._instance is None:
            cls._instance = super().__new__(cls)  # actually creates the object
        return cls._instance

    def __init__(self, value: int):
        self.value = value  # called EVERY time, even if __new__ returns existing

s1 = Singleton(1)
s2 = Singleton(2)
assert s1 is s2        # same object
assert s1.value == 2   # __init__ ran again and overwrote
```

### Subclassing Immutables

`__new__` is the only way to customize immutable types because `__init__` runs after creation:

```python
class UpperStr(str):
    def __new__(cls, value: str) -> "UpperStr":
        return super().__new__(cls, value.upper())  # must set value here

    # __init__ is too late — str is already frozen

s = UpperStr("hello")
print(s)  # "HELLO"
```

```python
class PositiveInt(int):
    def __new__(cls, value: int) -> "PositiveInt":
        if value < 0:
            raise ValueError("Must be positive")
        return super().__new__(cls, value)

PositiveInt(-5)  # ValueError
```

### Creation Chain Summary

```
MyClass(args)
    -> MyMeta.__call__(cls, args)        # metaclass controls everything
        -> cls.__new__(cls, args)        # allocates memory, returns instance
        -> cls.__init__(instance, args)  # initializes instance
        -> return instance
```

---

## 13. Attribute Lookup Chain — `__getattr__` vs `__getattribute__`

`__getattribute__` is called on **every** attribute access unconditionally — it intercepts before the normal lookup chain. `__getattr__` is called **only** when normal attribute lookup fails — a fallback hook for missing attributes. The full lookup order is: data descriptors from MRO → instance `__dict__` → non-data descriptors/class attributes from MRO → `__getattr__()`. Override `__setattr__` and `__delattr__` to control attribute assignment and deletion.

```python
class LazyLoader:
    def __init__(self):
        self.name = "loaded"

    def __getattribute__(self, name: str):
        print(f"Accessing: {name}")        # called on EVERY attribute access
        return super().__getattribute__(name)  # must call super or infinite loop

    def __getattr__(self, name: str):
        print(f"Missing: {name}")          # called ONLY when normal lookup fails
        return f"default_{name}"

obj = LazyLoader()
obj.name     # prints "Accessing: name" -> "loaded"
obj.missing  # prints "Accessing: missing", then "Missing: missing" -> "default_missing"
```

### Lookup Order

```
1. Data descriptors from type(obj).__mro__  (e.g., @property, __slots__)
2. Instance __dict__
3. Non-data descriptors and other class attributes from __mro__
4. __getattr__() if all above fail
```

`__getattribute__` intercepts at step 0 — before everything.

### Practical Use: Proxy / Delegation Pattern

```python
class Proxy:
    def __init__(self, target: object):
        self._target = target

    def __getattr__(self, name: str):
        return getattr(self._target, name)  # delegate to wrapped object

class RealService:
    def process(self) -> str:
        return "processed"

proxy = Proxy(RealService())
proxy.process()  # "processed" — delegated transparently
```

### `__setattr__` and `__delattr__`

```python
class Frozen:
    def __init__(self, x: int):
        super().__setattr__("x", x)  # bypass our __setattr__ during init

    def __setattr__(self, name: str, value) -> None:
        raise AttributeError("Cannot modify frozen object")

    def __delattr__(self, name: str) -> None:
        raise AttributeError("Cannot delete from frozen object")

f = Frozen(42)
f.x      # 42
f.x = 1  # AttributeError
```

---

## 14. `__call__` — Callable Objects

Any object whose class defines `__call__` can be invoked with `()` like a function. This enables stateful callables — objects that carry inspectable, configurable state between invocations. Common use cases include decorators with configuration, rate limiters, and middleware. Prefer `__call__` over closures when state needs to be inspectable or tested; use closures for simple cases.

Any object with `__call__` can be used like a function.

```python
class RateLimiter:
    def __init__(self, max_calls: int, period: float):
        self.max_calls = max_calls
        self.period = period
        self.calls: list[float] = []

    def __call__(self, func):
        from functools import wraps
        import time

        @wraps(func)
        def wrapper(*args, **kwargs):
            now = time.time()
            self.calls = [t for t in self.calls if now - t < self.period]
            if len(self.calls) >= self.max_calls:
                raise RuntimeError("Rate limit exceeded")
            self.calls.append(now)
            return func(*args, **kwargs)
        return wrapper

@RateLimiter(max_calls=5, period=60.0)
def api_call() -> str:
    return "response"
```

### Stateful Callables vs Closures

```python
# Callable object — state is explicit, inspectable, testable
class Counter:
    def __init__(self):
        self.count = 0

    def __call__(self) -> int:
        self.count += 1
        return self.count

# Closure — state is hidden
def make_counter():
    count = 0
    def counter() -> int:
        nonlocal count
        count += 1
        return count
    return counter

c1 = Counter()
c1()       # 1
c1.count   # 1 — inspectable

c2 = make_counter()
c2()       # 1 — but can't access count
```

Use `__call__` when you need inspectable/configurable state. Use closures for simple cases.

---

## 15. Composition vs Inheritance

**Composition** builds complex objects by combining simpler ones ("has-a"), delegating behavior to contained objects. **Inheritance** models "is-a" relationships through class hierarchies. Composition is favored because it avoids fragile base class problems, supports runtime flexibility (swap strategies), and keeps hierarchies shallow. Use inheritance for genuine is-a relationships, defining interfaces (ABC), and when shared implementation is needed across a shallow (1-2 level) hierarchy.

### The Problem with Deep Inheritance

```python
# Fragile — changes to base break everything
class Animal:
    def move(self) -> str:
        return "moving"

class Bird(Animal):
    def move(self) -> str:
        return "flying"

class Penguin(Bird):  # penguins can't fly!
    def move(self) -> str:
        return "waddling"  # forced to override — LSP violation
```

### Composition: Has-A over Is-A

```python
from abc import ABC, abstractmethod

class MovementStrategy(ABC):
    @abstractmethod
    def move(self) -> str: ...

class FlyingMovement(MovementStrategy):
    def move(self) -> str:
        return "flying"

class WaddlingMovement(MovementStrategy):
    def move(self) -> str:
        return "waddling"

class SwimmingMovement(MovementStrategy):
    def move(self) -> str:
        return "swimming"

class Animal:
    def __init__(self, name: str, movement: MovementStrategy):
        self.name = name
        self.movement = movement

    def move(self) -> str:
        return self.movement.move()

penguin = Animal("penguin", WaddlingMovement())
eagle = Animal("eagle", FlyingMovement())

# can even change at runtime
penguin.movement = SwimmingMovement()
```

### When to Use Which

| Use Inheritance                   | Use Composition                  |
| --------------------------------- | -------------------------------- |
| True "is-a" relationship          | "Has-a" or "uses-a" relationship |
| Shared implementation needed      | Behavior varies independently    |
| Framework requires it (e.g., ABC) | Need runtime flexibility         |
| Shallow hierarchy (1-2 levels)    | Would create deep/wide hierarchy |

**Interview answer:** "I favor composition because it's more flexible and avoids fragile base class problems. I use inheritance for defining interfaces (ABC) and for genuine is-a relationships with shallow hierarchies."

---

## 16. Enum

A class of named, immutable constants that are **singletons** — each member is created once and identity-comparable with `is`. Enums are iterable, support lookup by name (`OrderStatus["PENDING"]`) and value (`OrderStatus(1)`), and prevent accidental duplicate values with `@unique`. Use `IntEnum`/`StrEnum` when you need enum members to behave like their primitive type in comparisons and string formatting.

```python
from enum import Enum, auto, unique

@unique  # ensures no duplicate values
class OrderStatus(Enum):
    PENDING = auto()     # auto-generates values: 1, 2, 3...
    PROCESSING = auto()
    COMPLETED = auto()
    FAILED = auto()

    @classmethod
    def active_statuses(cls) -> list["OrderStatus"]:
        return [cls.PENDING, cls.PROCESSING]

status = OrderStatus.PENDING
status.name   # "PENDING"
status.value  # 1

# Comparison
status == OrderStatus.PENDING  # True
status is OrderStatus.PENDING  # True — singletons

# Iteration
for s in OrderStatus:
    print(s)

# Lookup
OrderStatus(1)           # OrderStatus.PENDING
OrderStatus["PENDING"]   # OrderStatus.PENDING
```

### IntEnum and StrEnum

```python
from enum import IntEnum, StrEnum

class Priority(IntEnum):  # compares with int
    LOW = 1
    HIGH = 2

Priority.HIGH > 1  # True — acts like int

class Color(StrEnum):  # Python 3.11+
    RED = auto()    # "red" — lowercased name
    GREEN = auto()  # "green"

f"Color is {Color.RED}"  # "Color is red" — acts like str
```

### Enum Gotchas

```python
# Enums are singletons — can't instantiate new ones
OrderStatus.PENDING is OrderStatus.PENDING  # always True

# Enums are iterable but NOT subscriptable by index
list(OrderStatus)[0]  # works
OrderStatus[0]        # KeyError — use OrderStatus(1) for value lookup

# Enums with same value alias to first (unless @unique)
class Broken(Enum):
    A = 1
    B = 1  # B is an alias for A
    # len(Broken) == 1, not 2
```

---

## 17. `isinstance()` vs `type()`

`isinstance()` checks the **entire inheritance chain** — returns `True` if the object is an instance of the given class or any of its parents. `type()` checks the **exact type** only. Almost always prefer `isinstance()` — it respects polymorphism, works with ABCs and Protocols, and accepts tuples for OR logic. Use `type()` only when you need exact type matching (rare).

```python
class Animal: ...
class Dog(Animal): ...

d = Dog()

# isinstance checks the ENTIRE inheritance chain
isinstance(d, Dog)    # True
isinstance(d, Animal) # True
isinstance(d, object) # True

# type checks EXACT type only
type(d) == Dog     # True
type(d) == Animal  # False — d is Dog, not Animal
type(d) is Dog     # True (prefer `is` for type comparison)
```

**Rule:** Use `isinstance()` almost always. Use `type()` only when you need exact type matching (rare).

```python
# isinstance works with tuples (OR logic)
isinstance(d, (Dog, Cat))  # True if either

# isinstance works with ABC and Protocol
from abc import ABC
isinstance(d, ABC)  # checks registration too
```

---

## 18. Abstract Properties

Combining `@property` with `@abstractmethod` forces subclasses to implement a property — not just a method. This defines an interface that guarantees computed attributes exist on all implementations. Convention is `@property` on top, `@abstractmethod` below (either order works in Python 3.3+).

```python
from abc import ABC, abstractmethod

class Shape(ABC):
    @property
    @abstractmethod
    def area(self) -> float: ...

    @property
    @abstractmethod
    def perimeter(self) -> float: ...

    @abstractmethod
    def scale(self, factor: float) -> "Shape": ...

class Circle(Shape):
    def __init__(self, radius: float):
        self._radius = radius

    @property
    def area(self) -> float:
        return 3.14159 * self._radius ** 2

    @property
    def perimeter(self) -> float:
        return 2 * 3.14159 * self._radius

    def scale(self, factor: float) -> "Circle":
        return Circle(self._radius * factor)

# Shape()  # TypeError: Can't instantiate abstract class
Circle(5).area  # 78.53975
```

**Order matters:** `@property` must come before `@abstractmethod` in Python < 3.3, but either order works in 3.3+. Convention: `@property` on top.

---

## 19. Class Decorators

A function that takes a class, modifies or wraps it, and returns it. Class decorators are a simpler alternative to metaclasses for modifying classes at creation time — use them for registration, adding methods, wrapping `__init__`, or enforcing constraints. Prefer decorators over `__init_subclass__` over metaclasses (simplest tool that works).

Alternative to metaclasses for modifying classes at creation time.

```python
from typing import Any

def add_logging(cls: type) -> type:
    original_init = cls.__init__

    def new_init(self: Any, *args: Any, **kwargs: Any) -> None:
        print(f"Creating {cls.__name__} with {args}, {kwargs}")
        original_init(self, *args, **kwargs)

    cls.__init__ = new_init
    return cls

@add_logging
class Account:
    def __init__(self, id: int):
        self.id = id

Account(42)  # prints "Creating Account with (42,), {}"
```

### Registry Pattern

```python
_registry: dict[str, type] = {}

def register(cls: type) -> type:
    _registry[cls.__name__] = cls
    return cls

@register
class PaymentProcessor: ...

@register
class RefundProcessor: ...

_registry  # {"PaymentProcessor": ..., "RefundProcessor": ...}
```

### When to Use What

| Mechanism           | Use case                                    |
| ------------------- | ------------------------------------------- |
| Class decorator     | Simple class modification, registration     |
| `__init_subclass__` | Hook into subclass creation                 |
| Metaclass           | Deep control over class creation, namespace |

**Prefer:** decorator > `__init_subclass__` > metaclass (simplest that works)

---

## 20. `__bool__` — Truthiness Protocol

Controls the truth value of an object when used in boolean contexts (`if obj`, `while obj`, `not obj`). Python's fallback chain: first calls `__bool__()`, then `__len__() != 0`, then defaults to `True` (all objects are truthy by default). This is why empty containers are falsy — their `__len__` returns 0.

```python
class Queue:
    def __init__(self):
        self._items: list = []

    def __bool__(self) -> bool:
        return len(self._items) > 0

    def __len__(self) -> int:
        return len(self._items)

q = Queue()
if q:           # calls __bool__
    print("has items")
else:
    print("empty")  # prints "empty"

# Fallback chain:
# 1. __bool__() if defined
# 2. __len__() != 0 if defined
# 3. Always True (all objects are truthy by default)
```

---

## 21. Copy Protocol

Controls how objects are duplicated via `copy.copy()` and `copy.deepcopy()`. A **shallow copy** (`__copy__`) creates a new object but nested objects are shared references. A **deep copy** (`__deepcopy__`) recursively copies everything, creating fully independent objects. The `memo` dict in `__deepcopy__` tracks already-copied objects to handle circular references.

```python
import copy

class Config:
    def __init__(self, settings: dict, nested: list):
        self.settings = settings
        self.nested = nested

    def __copy__(self) -> "Config":
        # Shallow copy — nested objects are shared references
        return Config(self.settings, self.nested)

    def __deepcopy__(self, memo: dict) -> "Config":
        # Deep copy — everything is recursively copied
        return Config(
            copy.deepcopy(self.settings, memo),
            copy.deepcopy(self.nested, memo),
        )

original = Config({"a": 1}, [[1, 2]])
shallow = copy.copy(original)
deep = copy.deepcopy(original)

original.nested[0].append(3)
shallow.nested[0]  # [1, 2, 3] — shared reference
deep.nested[0]     # [1, 2]    — independent copy
```

### Shallow vs Deep — Interview Answer

|                | Shallow (`copy.copy`)               | Deep (`copy.deepcopy`)    |
| -------------- | ----------------------------------- | ------------------------- |
| Primitives     | Copied                              | Copied                    |
| Nested objects | Shared reference                    | Recursively copied        |
| Performance    | Fast                                | Slower                    |
| Use when       | Flat structures, immutable contents | Nested mutable structures |

---

## 22. Weak References

A `weakref.ref` is a reference that does **not** prevent garbage collection of the referenced object. When the last strong reference is deleted, the object is collected and the weak reference returns `None`. Use cases: caches that shouldn't prevent GC (`WeakValueDictionary`), observer patterns where observers shouldn't keep subjects alive, and breaking circular references.

```python
import weakref

class ExpensiveObject:
    def __init__(self, name: str):
        self.name = name

# Strong reference keeps object alive
obj = ExpensiveObject("heavy")

# Weak reference does NOT prevent garbage collection
weak = weakref.ref(obj)
weak()       # returns obj
del obj
weak()       # returns None — object was garbage collected

# WeakValueDictionary — cache that doesn't prevent GC
cache: weakref.WeakValueDictionary = weakref.WeakValueDictionary()
obj = ExpensiveObject("cached")
cache["key"] = obj
cache["key"]  # returns obj
del obj
# cache["key"]  # KeyError — garbage collected
```

**Use cases:**

- Caches that shouldn't prevent GC
- Observer pattern — observers shouldn't keep subjects alive
- Breaking circular references
- Parent-child relationships where child shouldn't keep parent alive

---

## 23. `__subclasshook__` — ABC isinstance Customization

An ABC classmethod that customizes how `isinstance()` and `issubclass()` checks work for that ABC. Return `True` to accept a class, `False` to reject, or `NotImplemented` to fall back to normal behavior. This is the mechanism behind `collections.abc` — e.g., `Iterable` checks for `__iter__`, `Hashable` checks for `__hash__`, without requiring explicit inheritance.

```python
from abc import ABC, abstractmethod

class Drawable(ABC):
    @abstractmethod
    def draw(self) -> None: ...

    @classmethod
    def __subclasshook__(cls, C: type) -> bool:
        if cls is Drawable:
            if hasattr(C, "draw"):
                return True  # any class with draw() is considered Drawable
        return NotImplemented

class Circle:  # no inheritance from Drawable
    def draw(self) -> None:
        print("drawing circle")

isinstance(Circle(), Drawable)  # True — because __subclasshook__
issubclass(Circle, Drawable)    # True
```

This is how `collections.abc` types work — `Iterable` checks for `__iter__`, `Hashable` checks for `__hash__`, etc.

---

## 24. Pickle Protocol

Controls how objects are serialized (`pickle.dumps`) and deserialized (`pickle.loads`). `__getstate__` returns the object's state for pickling — use it to exclude non-serializable fields (sockets, file handles, locks). `__setstate__` restores the object from that state — use it to reconnect resources on deserialization. Without these, pickle uses `__dict__` by default.

```python
import pickle

class Connection:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.socket = self._connect()

    def _connect(self):
        return f"socket({self.host}:{self.port})"

    def __getstate__(self) -> dict:
        state = self.__dict__.copy()
        del state["socket"]  # can't serialize socket
        return state

    def __setstate__(self, state: dict) -> None:
        self.__dict__.update(state)
        self.socket = self._connect()  # reconnect on unpickle

conn = Connection("localhost", 5432)
data = pickle.dumps(conn)
restored = pickle.loads(data)
restored.socket  # "socket(localhost:5432)" — reconnected
```

---

## 25. `__class_getitem__` — Generic Classes

Enables `MyClass[T]` subscription syntax for generic type hints. Typically used by inheriting from `Generic[T]`, which provides `__class_getitem__` automatically. You can also implement it directly on a class to allow bracket syntax without `Generic`. This is purely for type checking — at runtime, `Stack[int]` and `Stack[str]` are the same class (type erasure).

```python
from typing import TypeVar, Generic

T = TypeVar("T")

class Stack(Generic[T]):
    def __init__(self) -> None:
        self._items: list[T] = []

    def push(self, item: T) -> None:
        self._items.append(item)

    def pop(self) -> T:
        return self._items.pop()

# Type-checked usage
stack: Stack[int] = Stack()
stack.push(1)     # ok
stack.push("a")   # mypy error

# Or without Generic — implement __class_getitem__ directly
class Registry:
    def __class_getitem__(cls, item: type) -> type:
        return cls  # allows Registry[str] syntax for type hints
```

---

## Interview-Critical Summary

| Topic                      | What to know                                                     | When it comes up                    |
| -------------------------- | ---------------------------------------------------------------- | ----------------------------------- |
| ABC + Strategy             | Define interfaces with `@abstractmethod`                         | Load balancer coding                |
| `@property`                | Encapsulation without Java-style getters/setters                 | Code review discussions             |
| MRO                        | C3 linearization, `super()` follows MRO not parent               | "Explain multiple inheritance"      |
| `__eq__`/`__hash__`        | Contract, `NotImplemented`, unhashable default                   | Dict/HashMap internals              |
| Dunders                    | Container, comparison, arithmetic, context manager               | "How would you make this Pythonic?" |
| `@classmethod`             | Factory pattern, alternative constructors                        | "How would you design this?"        |
| Descriptors                | How property/staticmethod work under the hood                    | Deep Python internals               |
| Metaclasses                | type(), `__init_subclass__`, singleton                           | "How does Python create classes?"   |
| `__slots__`                | Memory optimization, trade-offs                                  | Performance questions               |
| `dataclasses`              | When to use, `frozen`, `field()` options                         | "How would you model this data?"    |
| Protocols                  | Structural subtyping vs nominal                                  | Design pattern discussions          |
| `__new__` vs `__init__`    | Immutable subclassing, singleton, creation chain                 | "How does object creation work?"    |
| Attribute lookup           | `__getattr__` vs `__getattribute__`, lookup order, proxy pattern | "How does attribute access work?"   |
| `__call__`                 | Callable objects, stateful decorators vs closures                | Decorator/middleware design         |
| Composition vs Inheritance | Favor composition, when to use which                             | "How would you structure this?"     |
| Enum                       | `auto()`, `@unique`, IntEnum/StrEnum, singleton behavior         | Modeling fixed value sets           |
| `isinstance` vs `type`     | Inheritance chain vs exact match                                 | Type checking discussions           |
| Abstract properties        | `@property` + `@abstractmethod` combo                            | Interface design                    |
| Class decorators           | Registration, logging, prefer over metaclasses                   | "Alternatives to metaclasses?"      |
| `__bool__`                 | Truthiness fallback chain: `__bool__` > `__len__` > True         | "How does `if obj` work?"           |
| Copy protocol              | Shallow vs deep, `__copy__`/`__deepcopy__`                       | Mutable object handling             |
| Weak references            | `weakref.ref`, WeakValueDictionary, breaking cycles              | Caches, observer pattern            |
| `__subclasshook__`         | How ABCs customize isinstance checks                             | Deep ABC internals                  |
| Pickle protocol            | `__getstate__`/`__setstate__`, non-serializable fields           | Serialization questions             |
| `__class_getitem__`        | Generic classes, `Generic[T]`                                    | Type system / generics              |

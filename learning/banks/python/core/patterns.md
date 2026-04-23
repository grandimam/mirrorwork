# Design Patterns in Python — Revolut Interview Guide

## Syllabus Overview

### Part 1 — Creational Patterns

| # | Pattern | Fintech Relevance |
|---|---------|-------------------|
| 1 | **Singleton** | Database connection pools, config managers, feature flag clients |
| 2 | **Factory Method** | Creating payment processors by type (card, bank transfer, crypto) |
| 3 | **Abstract Factory** | Families of related objects — e.g., region-specific KYC + compliance + tax handlers |
| 4 | **Builder** | Constructing complex transaction or report objects step-by-step |
| 5 | **Prototype** | Cloning template objects — recurring payment templates, notification configs |

### Part 2 — Structural Patterns

| # | Pattern | Fintech Relevance |
|---|---------|-------------------|
| 6 | **Adapter** | Wrapping third-party banking APIs behind a unified interface |
| 7 | **Decorator** | Adding retry, logging, auth, rate-limiting to service calls |
| 8 | **Facade** | Simplifying complex subsystems — single entry point for "transfer money" that orchestrates ledger, compliance, notification |
| 9 | **Proxy** | Lazy-loading, access control, caching for expensive resources |
| 10 | **Composite** | Tree structures — fee schedules, org hierarchies, nested permission groups |

### Part 3 — Behavioral Patterns

| # | Pattern | Fintech Relevance |
|---|---------|-------------------|
| 11 | **Strategy** | Swappable fraud detection algorithms, pricing engines, FX rate providers |
| 12 | **Observer / Event** | Event-driven architecture — transaction completed → notify, audit, update balance |
| 13 | **Chain of Responsibility** | Middleware pipelines — validation → fraud check → compliance → execution |
| 14 | **Command** | Encapsulating operations for undo/redo, task queues, audit trails |
| 15 | **State** | Transaction lifecycle (pending → processing → completed / failed / reversed) |
| 16 | **Template Method** | Base payment flow with hooks for provider-specific steps |
| 17 | **Iterator** | Paginated API responses, streaming large ledger datasets |

### Part 4 — Patterns Beyond GoF (Production Python)

| # | Pattern | Fintech Relevance |
|---|---------|-------------------|
| 18 | **Repository** | Data access abstraction — decoupling business logic from DB queries |
| 19 | **Unit of Work** | Grouping DB operations into atomic commits — critical for ledger consistency |
| 20 | **Circuit Breaker** | Protecting against cascading failures in external service calls |
| 21 | **Retry with Backoff** | Resilient calls to banking partners, card networks |
| 22 | **Dependency Injection** | Testable, decoupled services — FastAPI's `Depends()` |

---

## Part 1 — Creational Patterns

### 1. Singleton

Ensures a class has exactly one instance. In Python, modules are natural singletons, but the pattern matters when you need lazy initialization or controlled access.

#### When to use at Revolut scale
- Connection pools (Redis, PostgreSQL)
- Configuration/feature-flag clients
- Metrics collectors

#### Implementation — metaclass approach

```python
from typing import ClassVar, Self


class SingletonMeta(type):
    _instances: ClassVar[dict[type, Self]] = {}

    def __call__(cls, *args, **kwargs) -> Self:
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class DatabasePool(metaclass=SingletonMeta):
    def __init__(self, dsn: str, pool_size: int = 10) -> None:
        self.dsn = dsn
        self.pool_size = pool_size
        self._pool: list = []

    def get_connection(self): ...
```

```python
pool_a = DatabasePool("postgresql://localhost/revolut")
pool_b = DatabasePool("postgresql://localhost/revolut")
assert pool_a is pool_b  # same instance
```

#### Pythonic alternative — module-level instance

```python
# config.py
class _Config:
    def __init__(self) -> None:
        self.settings: dict[str, str] = {}

    def load(self, path: str) -> None: ...

config = _Config()  # module-level singleton, imported everywhere
```

#### Thread-safe singleton

```python
import threading
from typing import ClassVar, Self


class ThreadSafeSingleton(type):
    _instances: ClassVar[dict[type, Self]] = {}
    _lock: ClassVar[threading.Lock] = threading.Lock()

    def __call__(cls, *args, **kwargs) -> Self:
        if cls not in cls._instances:
            with cls._lock:
                if cls not in cls._instances:
                    cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]
```

#### Pitfalls
- Makes unit testing harder — mock the singleton or use dependency injection instead
- Hidden global state — prefer explicit DI in production codebases
- Thread safety requires double-checked locking

---

### 2. Factory Method

Defines an interface for creating objects, letting subclasses decide which class to instantiate.

#### When to use
- Creating payment processors by type without `if/elif` chains
- Instantiating region-specific handlers

```python
from abc import ABC, abstractmethod
from decimal import Decimal
from enum import StrEnum


class PaymentMethod(StrEnum):
    CARD = "card"
    BANK_TRANSFER = "bank_transfer"
    CRYPTO = "crypto"


class PaymentProcessor(ABC):
    @abstractmethod
    def charge(self, amount: Decimal, currency: str) -> str: ...

    @abstractmethod
    def refund(self, transaction_id: str) -> bool: ...


class CardProcessor(PaymentProcessor):
    def charge(self, amount: Decimal, currency: str) -> str:
        return f"card_txn_{amount}_{currency}"

    def refund(self, transaction_id: str) -> bool:
        return True


class BankTransferProcessor(PaymentProcessor):
    def charge(self, amount: Decimal, currency: str) -> str:
        return f"bank_txn_{amount}_{currency}"

    def refund(self, transaction_id: str) -> bool:
        return True


class CryptoProcessor(PaymentProcessor):
    def charge(self, amount: Decimal, currency: str) -> str:
        return f"crypto_txn_{amount}_{currency}"

    def refund(self, transaction_id: str) -> bool:
        return False


class PaymentProcessorFactory:
    _registry: dict[PaymentMethod, type[PaymentProcessor]] = {
        PaymentMethod.CARD: CardProcessor,
        PaymentMethod.BANK_TRANSFER: BankTransferProcessor,
        PaymentMethod.CRYPTO: CryptoProcessor,
    }

    @classmethod
    def create(cls, method: PaymentMethod) -> PaymentProcessor:
        processor_cls = cls._registry.get(method)
        if not processor_cls:
            raise ValueError(f"Unsupported payment method: {method}")
        return processor_cls()

    @classmethod
    def register(cls, method: PaymentMethod, processor: type[PaymentProcessor]) -> None:
        cls._registry[method] = processor
```

```python
processor = PaymentProcessorFactory.create(PaymentMethod.CARD)
txn_id = processor.charge(Decimal("49.99"), "EUR")
```

#### Pythonic alternative — registry decorator

```python
from typing import Callable

_PROCESSORS: dict[str, type[PaymentProcessor]] = {}


def register_processor(method: str) -> Callable:
    def decorator(cls: type[PaymentProcessor]) -> type[PaymentProcessor]:
        _PROCESSORS[method] = cls
        return cls
    return decorator


def get_processor(method: str) -> PaymentProcessor:
    return _PROCESSORS[method]()


@register_processor("card")
class CardProcessor(PaymentProcessor): ...
```

---

### 3. Abstract Factory

Creates families of related objects without specifying their concrete classes. Think of it as a factory of factories.

#### When to use
- Region-specific bundles: EU region needs EU-KYC + SEPA payments + GDPR compliance; US region needs US-KYC + ACH payments + SOX compliance

```python
from abc import ABC, abstractmethod


class KYCVerifier(ABC):
    @abstractmethod
    def verify(self, user_id: str) -> bool: ...

class PaymentGateway(ABC):
    @abstractmethod
    def send(self, amount: Decimal, dest: str) -> str: ...

class ComplianceChecker(ABC):
    @abstractmethod
    def check(self, transaction_id: str) -> bool: ...


class EUKYCVerifier(KYCVerifier):
    def verify(self, user_id: str) -> bool:
        return True  # EU ID verification logic

class SEPAGateway(PaymentGateway):
    def send(self, amount: Decimal, dest: str) -> str:
        return f"sepa_{dest}_{amount}"

class GDPRCompliance(ComplianceChecker):
    def check(self, transaction_id: str) -> bool:
        return True


class RegionFactory(ABC):
    @abstractmethod
    def create_kyc(self) -> KYCVerifier: ...
    @abstractmethod
    def create_gateway(self) -> PaymentGateway: ...
    @abstractmethod
    def create_compliance(self) -> ComplianceChecker: ...


class EUFactory(RegionFactory):
    def create_kyc(self) -> KYCVerifier:
        return EUKYCVerifier()

    def create_gateway(self) -> PaymentGateway:
        return SEPAGateway()

    def create_compliance(self) -> ComplianceChecker:
        return GDPRCompliance()
```

```python
def onboard_user(factory: RegionFactory, user_id: str) -> None:
    kyc = factory.create_kyc()
    kyc.verify(user_id)

onboard_user(EUFactory(), "user_123")
```

---

### 4. Builder

Constructs complex objects step-by-step, separating construction from representation.

#### When to use
- Building transaction objects with many optional fields
- Constructing compliance reports
- Assembling complex API requests

```python
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Self


@dataclass
class Transaction:
    sender_id: str
    receiver_id: str
    amount: Decimal
    currency: str
    timestamp: datetime
    reference: str = ""
    metadata: dict[str, str] = field(default_factory=dict)
    compliance_flags: list[str] = field(default_factory=list)
    fee: Decimal = Decimal("0")


class TransactionBuilder:
    def __init__(self, sender_id: str, receiver_id: str) -> None:
        self._sender_id = sender_id
        self._receiver_id = receiver_id
        self._amount = Decimal("0")
        self._currency = "EUR"
        self._reference = ""
        self._metadata: dict[str, str] = {}
        self._compliance_flags: list[str] = []
        self._fee = Decimal("0")

    def amount(self, value: Decimal, currency: str = "EUR") -> Self:
        self._amount = value
        self._currency = currency
        return self

    def reference(self, ref: str) -> Self:
        self._reference = ref
        return self

    def with_metadata(self, key: str, value: str) -> Self:
        self._metadata[key] = value
        return self

    def with_compliance_flag(self, flag: str) -> Self:
        self._compliance_flags.append(flag)
        return self

    def with_fee(self, fee: Decimal) -> Self:
        self._fee = fee
        return self

    def build(self) -> Transaction:
        if self._amount <= 0:
            raise ValueError("Transaction amount must be positive")
        return Transaction(
            sender_id=self._sender_id,
            receiver_id=self._receiver_id,
            amount=self._amount,
            currency=self._currency,
            timestamp=datetime.utcnow(),
            reference=self._reference,
            metadata=self._metadata,
            compliance_flags=self._compliance_flags,
            fee=self._fee,
        )
```

```python
txn = (
    TransactionBuilder("user_a", "user_b")
    .amount(Decimal("1000.00"), "GBP")
    .reference("Invoice #2024-001")
    .with_metadata("category", "b2b")
    .with_compliance_flag("large_transfer")
    .with_fee(Decimal("2.50"))
    .build()
)
```

#### Pythonic note
For simpler cases, `@dataclass` or Pydantic `BaseModel` with defaults often eliminates the need for a builder entirely. Use Builder when construction involves validation, conditional logic, or multi-step assembly.

---

### 5. Prototype

Creates new objects by cloning an existing instance rather than building from scratch.

#### When to use
- Recurring payment templates
- Cloning notification configurations
- Test fixture generation

```python
import copy
from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class RecurringPayment:
    sender_id: str
    receiver_id: str
    amount: Decimal
    currency: str
    schedule: str
    metadata: dict[str, str] = field(default_factory=dict)

    def clone(self, **overrides) -> "RecurringPayment":
        cloned = copy.deepcopy(self)
        for key, value in overrides.items():
            setattr(cloned, key, value)
        return cloned
```

```python
template = RecurringPayment(
    sender_id="user_a",
    receiver_id="landlord",
    amount=Decimal("1200.00"),
    currency="EUR",
    schedule="monthly",
    metadata={"type": "rent"},
)

january = template.clone(metadata={"type": "rent", "month": "jan"})
february = template.clone(metadata={"type": "rent", "month": "feb"})
```

---

## Part 2 — Structural Patterns

### 6. Adapter

Converts one interface into another that clients expect. Essential when integrating with third-party APIs.

#### When to use
- Wrapping different banking partner APIs behind a uniform interface
- Migrating from one vendor to another without changing business logic

```python
from abc import ABC, abstractmethod
from decimal import Decimal


class TransferService(ABC):
    @abstractmethod
    def send_money(self, from_acc: str, to_acc: str, amount: Decimal, currency: str) -> str: ...


class LegacySwiftAPI:
    def execute_wire(self, src: str, dst: str, amt: float, ccy: str, ref: str) -> dict:
        return {"wire_id": f"SW-{src}-{dst}", "status": "pending"}


class SwiftAdapter(TransferService):
    def __init__(self, swift_client: LegacySwiftAPI) -> None:
        self._client = swift_client

    def send_money(self, from_acc: str, to_acc: str, amount: Decimal, currency: str) -> str:
        result = self._client.execute_wire(
            src=from_acc,
            dst=to_acc,
            amt=float(amount),
            ccy=currency,
            ref=f"REV-{from_acc}",
        )
        return result["wire_id"]
```

```python
swift = SwiftAdapter(LegacySwiftAPI())
txn_id = swift.send_money("acc_1", "acc_2", Decimal("500"), "USD")
```

---

### 7. Decorator (Structural)

Adds behavior to objects dynamically without modifying their code. Python's `@decorator` syntax is the language-native version of this pattern.

#### When to use
- Adding retry logic, logging, rate limiting, auth checks, metrics to service calls
- Composable, stackable behaviors

#### Function decorator — retry with backoff

```python
import time
import functools
from typing import Callable, TypeVar, ParamSpec

P = ParamSpec("P")
R = TypeVar("R")


def retry(max_attempts: int = 3, backoff: float = 1.0) -> Callable:
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            last_exception: Exception | None = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    time.sleep(backoff * (2 ** attempt))
            raise last_exception
        return wrapper
    return decorator


@retry(max_attempts=3, backoff=0.5)
def call_partner_api(partner_id: str, payload: dict) -> dict:
    ...
```

#### Class-based decorator — adding audit logging

```python
class AuditedProcessor(PaymentProcessor):
    def __init__(self, wrapped: PaymentProcessor, audit_log: list[str]) -> None:
        self._wrapped = wrapped
        self._audit_log = audit_log

    def charge(self, amount: Decimal, currency: str) -> str:
        txn_id = self._wrapped.charge(amount, currency)
        self._audit_log.append(f"CHARGE {amount} {currency} -> {txn_id}")
        return txn_id

    def refund(self, transaction_id: str) -> bool:
        result = self._wrapped.refund(transaction_id)
        self._audit_log.append(f"REFUND {transaction_id} -> {result}")
        return result
```

```python
audit: list[str] = []
processor = AuditedProcessor(CardProcessor(), audit)
processor.charge(Decimal("100"), "EUR")
```

---

### 8. Facade

Provides a simplified interface to a complex subsystem.

#### When to use
- "Transfer money" involves ledger, compliance, FX, notifications — expose one clean method
- Simplifying microservice orchestration

```python
from decimal import Decimal


class LedgerService:
    def debit(self, account_id: str, amount: Decimal) -> str: ...
    def credit(self, account_id: str, amount: Decimal) -> str: ...

class ComplianceService:
    def screen_transaction(self, sender: str, receiver: str, amount: Decimal) -> bool: ...

class FXService:
    def convert(self, amount: Decimal, from_ccy: str, to_ccy: str) -> Decimal: ...

class NotificationService:
    def notify(self, user_id: str, message: str) -> None: ...


class TransferFacade:
    def __init__(
        self,
        ledger: LedgerService,
        compliance: ComplianceService,
        fx: FXService,
        notifications: NotificationService,
    ) -> None:
        self._ledger = ledger
        self._compliance = compliance
        self._fx = fx
        self._notifications = notifications

    def transfer(
        self,
        sender_id: str,
        receiver_id: str,
        amount: Decimal,
        from_ccy: str,
        to_ccy: str,
    ) -> str:
        if not self._compliance.screen_transaction(sender_id, receiver_id, amount):
            raise PermissionError("Transaction blocked by compliance")

        converted = self._fx.convert(amount, from_ccy, to_ccy)
        self._ledger.debit(sender_id, amount)
        self._ledger.credit(receiver_id, converted)
        self._notifications.notify(sender_id, f"Sent {amount} {from_ccy}")
        self._notifications.notify(receiver_id, f"Received {converted} {to_ccy}")
        return f"transfer_{sender_id}_{receiver_id}"
```

---

### 9. Proxy

Controls access to another object — for lazy loading, access control, or caching.

#### When to use
- Caching expensive API calls (FX rates, partner responses)
- Access control before expensive operations

```python
from decimal import Decimal
from datetime import datetime, timedelta


class FXRateProvider:
    def get_rate(self, from_ccy: str, to_ccy: str) -> Decimal:
        ...  # expensive API call


class CachedFXProxy:
    def __init__(self, provider: FXRateProvider, ttl_seconds: int = 30) -> None:
        self._provider = provider
        self._ttl = timedelta(seconds=ttl_seconds)
        self._cache: dict[tuple[str, str], tuple[Decimal, datetime]] = {}

    def get_rate(self, from_ccy: str, to_ccy: str) -> Decimal:
        key = (from_ccy, to_ccy)
        if key in self._cache:
            rate, cached_at = self._cache[key]
            if datetime.utcnow() - cached_at < self._ttl:
                return rate
        rate = self._provider.get_rate(from_ccy, to_ccy)
        self._cache[key] = (rate, datetime.utcnow())
        return rate
```

---

### 10. Composite

Composes objects into tree structures. Lets clients treat individual objects and compositions uniformly.

#### When to use
- Fee structures (base fee + percentage + regional surcharge)
- Permission trees
- Nested account groups

```python
from abc import ABC, abstractmethod
from decimal import Decimal


class FeeComponent(ABC):
    @abstractmethod
    def calculate(self, amount: Decimal) -> Decimal: ...


class FlatFee(FeeComponent):
    def __init__(self, fee: Decimal) -> None:
        self._fee = fee

    def calculate(self, amount: Decimal) -> Decimal:
        return self._fee


class PercentageFee(FeeComponent):
    def __init__(self, rate: Decimal) -> None:
        self._rate = rate

    def calculate(self, amount: Decimal) -> Decimal:
        return amount * self._rate


class CompositeFee(FeeComponent):
    def __init__(self) -> None:
        self._components: list[FeeComponent] = []

    def add(self, component: FeeComponent) -> None:
        self._components.append(component)

    def calculate(self, amount: Decimal) -> Decimal:
        return sum(c.calculate(amount) for c in self._components)
```

```python
fee_schedule = CompositeFee()
fee_schedule.add(FlatFee(Decimal("0.50")))           # base fee
fee_schedule.add(PercentageFee(Decimal("0.015")))     # 1.5% processing
total_fee = fee_schedule.calculate(Decimal("1000"))    # 0.50 + 15.00 = 15.50
```

---

## Part 3 — Behavioral Patterns

### 11. Strategy

Defines a family of interchangeable algorithms. The client picks one at runtime.

#### When to use
- Swappable fraud detection engines
- Different pricing models per user tier
- FX rate sourcing strategies

```python
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Protocol


class FraudDetector(Protocol):
    def is_suspicious(self, user_id: str, amount: Decimal, country: str) -> bool: ...


class RuleBasedFraud:
    def is_suspicious(self, user_id: str, amount: Decimal, country: str) -> bool:
        return amount > Decimal("10000") or country in {"KP", "IR"}


class MLFraudDetector:
    def __init__(self, model_path: str) -> None:
        self._model_path = model_path

    def is_suspicious(self, user_id: str, amount: Decimal, country: str) -> bool:
        ...  # run ML inference


class PaymentService:
    def __init__(self, fraud_detector: FraudDetector) -> None:
        self._fraud = fraud_detector

    def process(self, user_id: str, amount: Decimal, country: str) -> str:
        if self._fraud.is_suspicious(user_id, amount, country):
            raise ValueError("Transaction flagged as suspicious")
        return f"txn_{user_id}_{amount}"
```

```python
service = PaymentService(fraud_detector=RuleBasedFraud())
service.process("user_1", Decimal("500"), "DE")
```

#### Pythonic note
Using `Protocol` instead of ABC — structural (duck) typing. No need to inherit; just implement the method signature.

---

### 12. Observer / Event System

Objects subscribe to events and get notified when they occur. Foundation of event-driven architectures.

#### When to use
- Transaction completed → update balance, send notification, write audit log, trigger analytics
- Decoupling producers from consumers

```python
from typing import Callable, Any
from collections import defaultdict


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[Callable]] = defaultdict(list)

    def subscribe(self, event: str, handler: Callable) -> None:
        self._subscribers[event].append(handler)

    def publish(self, event: str, data: Any) -> None:
        for handler in self._subscribers[event]:
            handler(data)


bus = EventBus()


def send_receipt(data: dict) -> None:
    print(f"Receipt sent for {data['txn_id']}")

def update_analytics(data: dict) -> None:
    print(f"Analytics updated for {data['txn_id']}")

def write_audit(data: dict) -> None:
    print(f"Audit log written for {data['txn_id']}")


bus.subscribe("transaction.completed", send_receipt)
bus.subscribe("transaction.completed", update_analytics)
bus.subscribe("transaction.completed", write_audit)

bus.publish("transaction.completed", {"txn_id": "txn_123", "amount": 500})
```

#### Decorator-based registration

```python
class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[Callable]] = defaultdict(list)

    def on(self, event: str) -> Callable:
        def decorator(func: Callable) -> Callable:
            self._subscribers[event].append(func)
            return func
        return decorator

    def publish(self, event: str, data: Any) -> None:
        for handler in self._subscribers[event]:
            handler(data)


bus = EventBus()

@bus.on("transaction.completed")
def send_receipt(data: dict) -> None: ...

@bus.on("transaction.completed")
def write_audit(data: dict) -> None: ...
```

---

### 13. Chain of Responsibility

Passes a request along a chain of handlers. Each handler decides to process or pass it on.

#### When to use
- Middleware pipelines: validation → rate limit → auth → fraud check → execute
- Request processing in API frameworks

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class TransferRequest:
    sender_id: str
    receiver_id: str
    amount: Decimal
    currency: str
    approved: bool = True
    rejection_reason: str = ""


class TransferHandler(ABC):
    def __init__(self) -> None:
        self._next: TransferHandler | None = None

    def set_next(self, handler: "TransferHandler") -> "TransferHandler":
        self._next = handler
        return handler

    def handle(self, request: TransferRequest) -> TransferRequest:
        if self._next:
            return self._next.handle(request)
        return request


class ValidationHandler(TransferHandler):
    def handle(self, request: TransferRequest) -> TransferRequest:
        if request.amount <= 0:
            request.approved = False
            request.rejection_reason = "Invalid amount"
            return request
        return super().handle(request)


class FraudCheckHandler(TransferHandler):
    def handle(self, request: TransferRequest) -> TransferRequest:
        if request.amount > Decimal("50000"):
            request.approved = False
            request.rejection_reason = "Amount exceeds fraud threshold"
            return request
        return super().handle(request)


class SanctionsHandler(TransferHandler):
    _blocked_users: set[str] = {"blocked_user"}

    def handle(self, request: TransferRequest) -> TransferRequest:
        if request.receiver_id in self._blocked_users:
            request.approved = False
            request.rejection_reason = "Receiver is sanctioned"
            return request
        return super().handle(request)


class ComplianceHandler(TransferHandler):
    def handle(self, request: TransferRequest) -> TransferRequest:
        # log for compliance audit trail
        return super().handle(request)
```

```python
validation = ValidationHandler()
fraud = FraudCheckHandler()
sanctions = SanctionsHandler()
compliance = ComplianceHandler()

validation.set_next(fraud).set_next(sanctions).set_next(compliance)

request = TransferRequest("user_a", "user_b", Decimal("1000"), "EUR")
result = validation.handle(request)
```

---

### 14. Command

Encapsulates a request as an object, enabling undo, queuing, and logging.

#### When to use
- Task queues (Celery-like job dispatching)
- Undo/redo for account operations
- Audit trails where you store the command itself

```python
from abc import ABC, abstractmethod
from decimal import Decimal
from datetime import datetime


class Command(ABC):
    @abstractmethod
    def execute(self) -> None: ...

    @abstractmethod
    def undo(self) -> None: ...


class TransferCommand(Command):
    def __init__(self, ledger: dict[str, Decimal], from_acc: str, to_acc: str, amount: Decimal) -> None:
        self._ledger = ledger
        self._from = from_acc
        self._to = to_acc
        self._amount = amount
        self._executed_at: datetime | None = None

    def execute(self) -> None:
        self._ledger[self._from] -= self._amount
        self._ledger[self._to] += self._amount
        self._executed_at = datetime.utcnow()

    def undo(self) -> None:
        self._ledger[self._from] += self._amount
        self._ledger[self._to] -= self._amount


class CommandHistory:
    def __init__(self) -> None:
        self._history: list[Command] = []

    def execute(self, command: Command) -> None:
        command.execute()
        self._history.append(command)

    def undo_last(self) -> None:
        if self._history:
            command = self._history.pop()
            command.undo()
```

```python
ledger = {"alice": Decimal("1000"), "bob": Decimal("500")}
history = CommandHistory()

cmd = TransferCommand(ledger, "alice", "bob", Decimal("200"))
history.execute(cmd)    # alice=800, bob=700
history.undo_last()     # alice=1000, bob=500
```

---

### 15. State

Allows an object to change its behavior when its internal state changes.

#### When to use
- Transaction lifecycle: pending → processing → completed / failed / reversed
- Account states: active → frozen → closed

```python
from abc import ABC, abstractmethod


class TransactionState(ABC):
    @abstractmethod
    def process(self, txn: "Transaction") -> None: ...
    @abstractmethod
    def complete(self, txn: "Transaction") -> None: ...
    @abstractmethod
    def fail(self, txn: "Transaction") -> None: ...
    @abstractmethod
    def reverse(self, txn: "Transaction") -> None: ...


class PendingState(TransactionState):
    def process(self, txn: "Transaction") -> None:
        txn.state = ProcessingState()

    def complete(self, txn: "Transaction") -> None:
        raise InvalidTransition("Cannot complete a pending transaction")

    def fail(self, txn: "Transaction") -> None:
        txn.state = FailedState()

    def reverse(self, txn: "Transaction") -> None:
        raise InvalidTransition("Cannot reverse a pending transaction")


class ProcessingState(TransactionState):
    def process(self, txn: "Transaction") -> None:
        raise InvalidTransition("Already processing")

    def complete(self, txn: "Transaction") -> None:
        txn.state = CompletedState()

    def fail(self, txn: "Transaction") -> None:
        txn.state = FailedState()

    def reverse(self, txn: "Transaction") -> None:
        raise InvalidTransition("Cannot reverse while processing")


class CompletedState(TransactionState):
    def process(self, txn: "Transaction") -> None:
        raise InvalidTransition("Already completed")

    def complete(self, txn: "Transaction") -> None:
        raise InvalidTransition("Already completed")

    def fail(self, txn: "Transaction") -> None:
        raise InvalidTransition("Cannot fail a completed transaction")

    def reverse(self, txn: "Transaction") -> None:
        txn.state = ReversedState()


class FailedState(TransactionState):
    def process(self, txn: "Transaction") -> None:
        txn.state = ProcessingState()  # retry

    def complete(self, txn: "Transaction") -> None:
        raise InvalidTransition("Cannot complete a failed transaction")

    def fail(self, txn: "Transaction") -> None:
        raise InvalidTransition("Already failed")

    def reverse(self, txn: "Transaction") -> None:
        raise InvalidTransition("Cannot reverse a failed transaction")


class ReversedState(TransactionState):
    def process(self, txn: "Transaction") -> None:
        raise InvalidTransition("Cannot process a reversed transaction")

    def complete(self, txn: "Transaction") -> None:
        raise InvalidTransition("Cannot complete a reversed transaction")

    def fail(self, txn: "Transaction") -> None:
        raise InvalidTransition("Cannot fail a reversed transaction")

    def reverse(self, txn: "Transaction") -> None:
        raise InvalidTransition("Already reversed")


class InvalidTransition(Exception): ...


class Transaction:
    def __init__(self, txn_id: str) -> None:
        self.txn_id = txn_id
        self.state: TransactionState = PendingState()

    def process(self) -> None:
        self.state.process(self)

    def complete(self) -> None:
        self.state.complete(self)

    def fail(self) -> None:
        self.state.fail(self)

    def reverse(self) -> None:
        self.state.reverse(self)
```

```python
txn = Transaction("txn_001")
txn.process()    # pending → processing
txn.complete()   # processing → completed
txn.reverse()    # completed → reversed
```

---

### 16. Template Method

Defines the skeleton of an algorithm in a base class, letting subclasses override specific steps.

#### When to use
- Base payment flow with hooks for provider-specific steps
- ETL pipelines with different extract/transform/load steps

```python
from abc import ABC, abstractmethod
from decimal import Decimal


class PaymentFlow(ABC):
    def execute(self, user_id: str, amount: Decimal) -> str:
        self.validate(user_id, amount)
        self.check_compliance(user_id, amount)
        txn_id = self.process_payment(user_id, amount)
        self.post_process(txn_id)
        return txn_id

    def validate(self, user_id: str, amount: Decimal) -> None:
        if amount <= 0:
            raise ValueError("Amount must be positive")

    def check_compliance(self, user_id: str, amount: Decimal) -> None:
        pass  # default: no extra checks

    @abstractmethod
    def process_payment(self, user_id: str, amount: Decimal) -> str: ...

    def post_process(self, txn_id: str) -> None:
        pass  # optional hook


class CardPaymentFlow(PaymentFlow):
    def check_compliance(self, user_id: str, amount: Decimal) -> None:
        if amount > Decimal("5000"):
            raise ValueError("Card payments over 5000 require 3DS")

    def process_payment(self, user_id: str, amount: Decimal) -> str:
        return f"card_txn_{user_id}"

    def post_process(self, txn_id: str) -> None:
        ...  # send push notification


class CryptoPaymentFlow(PaymentFlow):
    def check_compliance(self, user_id: str, amount: Decimal) -> None:
        ...  # travel rule checks

    def process_payment(self, user_id: str, amount: Decimal) -> str:
        return f"crypto_txn_{user_id}"
```

---

### 17. Iterator

Provides a way to traverse a collection without exposing its internals.

#### When to use
- Paginated API responses
- Streaming large ledger datasets without loading all into memory

```python
from typing import Iterator, Generator
from dataclasses import dataclass


@dataclass
class LedgerEntry:
    entry_id: str
    amount: float
    description: str


class PaginatedLedger:
    def __init__(self, account_id: str, page_size: int = 100) -> None:
        self._account_id = account_id
        self._page_size = page_size

    def _fetch_page(self, offset: int) -> list[LedgerEntry]:
        ...  # database query with LIMIT/OFFSET

    def __iter__(self) -> Generator[LedgerEntry, None, None]:
        offset = 0
        while True:
            page = self._fetch_page(offset)
            if not page:
                break
            yield from page
            offset += self._page_size
```

```python
ledger = PaginatedLedger("acc_123", page_size=50)
for entry in ledger:
    print(entry.entry_id, entry.amount)
```

---

## Part 4 — Beyond GoF (Production Python Patterns)

### 18. Repository

Abstracts data access behind a collection-like interface. Business logic doesn't know about SQL.

#### When to use
- Decoupling domain logic from database queries
- Making services testable with in-memory fakes

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class Account:
    account_id: str
    user_id: str
    balance: Decimal
    currency: str


class AccountRepository(ABC):
    @abstractmethod
    def get(self, account_id: str) -> Account | None: ...

    @abstractmethod
    def save(self, account: Account) -> None: ...

    @abstractmethod
    def find_by_user(self, user_id: str) -> list[Account]: ...


class PostgresAccountRepository(AccountRepository):
    def __init__(self, connection) -> None:
        self._conn = connection

    def get(self, account_id: str) -> Account | None:
        row = self._conn.execute(
            "SELECT * FROM accounts WHERE id = %s", (account_id,)
        ).fetchone()
        return Account(**row._asdict()) if row else None

    def save(self, account: Account) -> None:
        self._conn.execute(
            "INSERT INTO accounts VALUES (%s, %s, %s, %s) ON CONFLICT (id) DO UPDATE SET balance = %s",
            (account.account_id, account.user_id, account.balance, account.currency, account.balance),
        )

    def find_by_user(self, user_id: str) -> list[Account]:
        rows = self._conn.execute(
            "SELECT * FROM accounts WHERE user_id = %s", (user_id,)
        ).fetchall()
        return [Account(**r._asdict()) for r in rows]


class InMemoryAccountRepository(AccountRepository):
    def __init__(self) -> None:
        self._store: dict[str, Account] = {}

    def get(self, account_id: str) -> Account | None:
        return self._store.get(account_id)

    def save(self, account: Account) -> None:
        self._store[account.account_id] = account

    def find_by_user(self, user_id: str) -> list[Account]:
        return [a for a in self._store.values() if a.user_id == user_id]
```

---

### 19. Unit of Work

Groups multiple repository operations into a single atomic transaction.

#### When to use
- Double-entry bookkeeping — debit and credit must both succeed or both fail
- Any multi-table mutation that must be atomic

```python
from types import TracebackType


class UnitOfWork:
    def __init__(self, connection) -> None:
        self._conn = connection
        self.accounts = PostgresAccountRepository(connection)

    def __enter__(self) -> "UnitOfWork":
        self._conn.begin()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if exc_type:
            self._conn.rollback()
        else:
            self._conn.commit()

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()
```

```python
with UnitOfWork(db_connection) as uow:
    sender = uow.accounts.get("acc_sender")
    receiver = uow.accounts.get("acc_receiver")
    sender.balance -= Decimal("100")
    receiver.balance += Decimal("100")
    uow.accounts.save(sender)
    uow.accounts.save(receiver)
# auto-commits if no exception, auto-rollbacks if exception
```

---

### 20. Circuit Breaker

Prevents cascading failures by short-circuiting calls to failing services.

#### When to use
- Calls to external banking partners, card networks, KYC providers
- Any external dependency that can go down

```python
import time
from enum import StrEnum
from typing import Callable, TypeVar, ParamSpec

P = ParamSpec("P")
R = TypeVar("R")


class CircuitState(StrEnum):
    CLOSED = "closed"        # normal operation
    OPEN = "open"            # failing, reject calls
    HALF_OPEN = "half_open"  # testing recovery


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 30.0) -> None:
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._failure_count: int = 0
        self._state: CircuitState = CircuitState.CLOSED
        self._last_failure_time: float = 0

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if time.monotonic() - self._last_failure_time > self._recovery_timeout:
                self._state = CircuitState.HALF_OPEN
        return self._state

    def call(self, func: Callable[P, R], *args: P.args, **kwargs: P.kwargs) -> R:
        if self.state == CircuitState.OPEN:
            raise CircuitOpenError("Circuit is open — service unavailable")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def _on_success(self) -> None:
        self._failure_count = 0
        self._state = CircuitState.CLOSED

    def _on_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self._failure_threshold:
            self._state = CircuitState.OPEN


class CircuitOpenError(Exception): ...
```

```python
breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
try:
    result = breaker.call(call_partner_api, "partner_1", {"amount": 100})
except CircuitOpenError:
    ...  # use fallback or return cached response
```

---

### 21. Retry with Exponential Backoff

Already shown in the Decorator section (#7). Key points:

- Always cap max retries
- Use exponential backoff: `delay * 2^attempt`
- Add jitter to prevent thundering herd: `delay * 2^attempt + random(0, delay)`
- Only retry on transient errors (network timeouts, 503s), not on 400s or business logic errors

---

### 22. Dependency Injection

Injects dependencies from the outside rather than creating them internally. Core to testable architecture.

#### FastAPI-native DI

```python
from fastapi import FastAPI, Depends
from decimal import Decimal

app = FastAPI()


def get_fraud_detector() -> FraudDetector:
    return RuleBasedFraud()


def get_payment_service(
    fraud: FraudDetector = Depends(get_fraud_detector),
) -> PaymentService:
    return PaymentService(fraud_detector=fraud)


@app.post("/payments")
def create_payment(
    amount: Decimal,
    currency: str,
    service: PaymentService = Depends(get_payment_service),
) -> dict:
    txn_id = service.process("current_user", amount, "DE")
    return {"transaction_id": txn_id}
```

#### Testing — swap the dependency

```python
def test_payment_with_mock_fraud():
    class AlwaysCleanFraud:
        def is_suspicious(self, user_id: str, amount: Decimal, country: str) -> bool:
            return False

    service = PaymentService(fraud_detector=AlwaysCleanFraud())
    assert service.process("user_1", Decimal("100"), "DE") == "txn_user_1_100"
```

---

## Quick Reference — When to Use What

| Problem | Pattern |
|---------|---------|
| Need exactly one instance | Singleton |
| Create objects by type without if/elif | Factory Method |
| Create families of related objects by region/config | Abstract Factory |
| Complex object with many optional parts | Builder |
| Clone existing objects as templates | Prototype |
| Wrap incompatible third-party API | Adapter |
| Add behavior (retry, logging) without modifying code | Decorator |
| Simplify a complex multi-service workflow | Facade |
| Cache, lazy-load, or guard access | Proxy |
| Tree structures (fees, permissions) | Composite |
| Swap algorithms at runtime | Strategy |
| React to events, decouple producers/consumers | Observer |
| Pipeline of checks/middleware | Chain of Responsibility |
| Encapsulate operations for undo/queue/audit | Command |
| Object changes behavior based on lifecycle state | State |
| Same algorithm skeleton, different steps | Template Method |
| Traverse large datasets without loading all | Iterator |
| Abstract away data storage | Repository |
| Atomic multi-operation commits | Unit of Work |
| Protect against cascading failures | Circuit Breaker |
| Testable, decoupled services | Dependency Injection |

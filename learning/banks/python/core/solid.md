# SOLID Principles in Python — Revolut Interview Guide

## 1. Single Responsibility Principle (SRP)

> A class must have only one reason to change, in other words, there must be only one source influencing the change.

### Bad — one class doing too much

```python
class PaymentService:
    def process_payment(self, user_id: int, amount: Decimal) -> bool:
        if amount <= 0:
            raise ValueError("Invalid amount")
        # debit the account
        self._update_balance(user_id, -amount)
        # send notification
        self._send_email(user_id, f"Payment of {amount} processed")
        # log for compliance
        self._write_audit_log(user_id, amount)
        return True

    def _update_balance(self, user_id: int, delta: Decimal) -> None: ...
    def _send_email(self, user_id: int, msg: str) -> None: ...
    def _write_audit_log(self, user_id: int, amount: Decimal) -> None: ...
```

**Problem**: changing the email provider, audit format, or payment logic all touch the same class.

### Good — split by responsibility

```python
class PaymentProcessor:
    def __init__(
        self,
        ledger: LedgerService,
        notifier: NotificationService,
        auditor: AuditService,
    ) -> None:
        self.ledger = ledger
        self.notifier = notifier
        self.auditor = auditor

    def process(self, user_id: int, amount: Decimal) -> bool:
        self.ledger.debit(user_id, amount)
        self.notifier.notify(user_id, f"Payment of {amount} processed")
        self.auditor.log(user_id, amount)
        return True
```

Each collaborator has exactly one reason to change.

**Revolut context**: fintech services deal with payments, compliance, notifications, and fraud detection — these should never be tangled in a single class. Regulators can change audit requirements without touching payment logic.

---

## 2. Open/Closed Principle (OCP)

> Open for extension, closed for modification.

### Bad — adding new currency conversion requires editing existing code

```python
class CurrencyConverter:
    def convert(self, amount: Decimal, source: str, target: str) -> Decimal:
        if source == "USD" and target == "EUR":
            return amount * Decimal("0.92")
        elif source == "EUR" and target == "GBP":
            return amount * Decimal("0.86")
        # every new pair = new elif branch
        raise ValueError(f"Unsupported: {source}->{target}")
```

### Good — extend via registration, not modification

```python
from typing import Protocol

class ExchangeRateProvider(Protocol):
    def supports(self, source: str, target: str) -> bool: ...
    def rate(self, source: str, target: str) -> Decimal: ...


class CurrencyConverter:
    def __init__(self, providers: list[ExchangeRateProvider]) -> None:
        self.providers = providers

    def convert(self, amount: Decimal, source: str, target: str) -> Decimal:
        for provider in self.providers:
            if provider.supports(source, target):
                return amount * provider.rate(source, target)
        raise ValueError(f"No provider for {source}->{target}")
```

New currency pairs = new provider class, zero changes to `CurrencyConverter`.

**Python-specific techniques for OCP**:

- `Protocol` / ABCs for defining extension points
- Plugin registries via decorators
- `functools.singledispatch` for type-based extension

```python
from functools import singledispatch
from dataclasses import dataclass

@dataclass
class CardPayment:
    card_number: str
    amount: Decimal

@dataclass
class BankTransfer:
    iban: str
    amount: Decimal

@singledispatch
def process_payment(payment: object) -> str:
    raise NotImplementedError(f"Unknown payment type: {type(payment)}")

@process_payment.register
def _(payment: CardPayment) -> str:
    return f"Charging card {payment.card_number[-4:]}: {payment.amount}"

@process_payment.register
def _(payment: BankTransfer) -> str:
    return f"Transferring to {payment.iban}: {payment.amount}"
```

---

## 3. Liskov Substitution Principle (LSP)

> Subtypes must be substitutable for their base types without breaking correctness. If code works with a base type, swapping in any subtype should not break it.

### Bad — subclass breaks the contract

```python
class Account:
    def withdraw(self, amount: Decimal) -> Decimal:
        self.balance -= amount
        return self.balance

class FixedDepositAccount(Account):
    def withdraw(self, amount: Decimal) -> Decimal:
        raise RuntimeError("Cannot withdraw from fixed deposit before maturity")
```

Any code doing `account.withdraw(amount)` will break if handed a `FixedDepositAccount`.

### Good — model the distinction in the type hierarchy

```python
from typing import Protocol

class Readable(Protocol):
    @property
    def balance(self) -> Decimal: ...

class Withdrawable(Protocol):
    def withdraw(self, amount: Decimal) -> Decimal: ...

class CurrentAccount:
    def __init__(self, balance: Decimal) -> None:
        self._balance = balance

    @property
    def balance(self) -> Decimal:
        return self._balance

    def withdraw(self, amount: Decimal) -> Decimal:
        self._balance -= amount
        return self._balance

class FixedDepositAccount:
    def __init__(self, balance: Decimal, maturity_date: date) -> None:
        self._balance = balance
        self.maturity_date = maturity_date

    @property
    def balance(self) -> Decimal:
        return self._balance
```

Now `FixedDepositAccount` is `Readable` but not `Withdrawable` — no broken contracts.

**The four classic LSP violations** (with examples):

### 1. Raising unexpected exceptions

The base promises a method works; the subtype throws.

```python
class Account:
    def withdraw(self, amount: Decimal) -> Decimal:
        self.balance -= amount
        return self.balance

class FixedDepositAccount(Account):
    def withdraw(self, amount: Decimal) -> Decimal:
        raise RuntimeError("Cannot withdraw before maturity")
```

### 2. Strengthening preconditions — requiring more from the caller

The base accepts any positive amount; the subtype demands more.

```python
class PaymentGateway:
    def charge(self, amount: Decimal) -> None:
        # accepts any positive amount
        ...

class PremiumGateway(PaymentGateway):
    def charge(self, amount: Decimal) -> None:
        if amount < Decimal("100"):
            raise ValueError("Minimum charge is 100")  # caller didn't expect this
        ...
```

### 3. Weakening postconditions — promising less than the base

The base guarantees a return value; the subtype doesn't.

```python
class Cache:
    def get(self, key: str) -> str:
        return self._store[key]  # raises KeyError if missing — caller expects this

class DefaultCache(Cache):
    def get(self, key: str) -> str:
        return self._store.get(key, "")  # silently returns "" — caller's KeyError handling never triggers
```

The caller's contract with `Cache.get()` includes "raises `KeyError` on miss." `DefaultCache` changes that behavior — code relying on catching `KeyError` to detect misses will silently get wrong data.

### 4. Breaking invariants — violating guarantees the base maintains

```python
class BankAccount:
    def withdraw(self, amount: Decimal) -> Decimal:
        if amount > self.balance:
            raise ValueError("Insufficient funds")
        self.balance -= amount
        return self.balance  # invariant: balance >= 0

class OverdraftAccount(BankAccount):
    def withdraw(self, amount: Decimal) -> Decimal:
        self.balance -= amount
        return self.balance  # balance can go negative — breaks the invariant
```

---

## 4. Interface Segregation Principle (ISP)

> Clients should not depend on interfaces they don't use. If a class is forced to implement methods it doesn't need because the interface bundles too much together, that's the violation.

### Bad — fat interface

```python
from abc import ABC, abstractmethod

class UserRepository(ABC):
    @abstractmethod
    def get_user(self, user_id: int) -> User: ...
    @abstractmethod
    def save_user(self, user: User) -> None: ...
    @abstractmethod
    def delete_user(self, user_id: int) -> None: ...
    @abstractmethod
    def generate_report(self) -> bytes: ...
    @abstractmethod
    def send_marketing_email(self, user_id: int) -> None: ...
```

A read-only analytics service is forced to implement `delete_user` and `send_marketing_email`.

### Good — small, cohesive protocols

```python
from typing import Protocol

class UserReader(Protocol):
    def get_user(self, user_id: int) -> User: ...

class UserWriter(Protocol):
    def save_user(self, user: User) -> None: ...
    def delete_user(self, user_id: int) -> None: ...

class UserReporter(Protocol):
    def generate_report(self) -> bytes: ...
```

Consumers declare only what they need:

```python
class FraudDetectionService:
    def __init__(self, users: UserReader) -> None:
        self.users = users

    def check(self, user_id: int) -> RiskScore:
        user = self.users.get_user(user_id)
        ...
```

**Python advantage**: `Protocol` gives structural (duck) typing — no explicit `implements` needed. A class satisfies a Protocol just by having the right methods.

```python
class PostgresUserStore:
    def get_user(self, user_id: int) -> User: ...
    def save_user(self, user: User) -> None: ...
    def delete_user(self, user_id: int) -> None: ...
    def generate_report(self) -> bytes: ...

# This works — PostgresUserStore satisfies UserReader structurally
fraud_service = FraudDetectionService(users=PostgresUserStore())
```

---

## 5. Dependency Inversion Principle (DIP)

> High-level modules should not depend on low-level modules. Both should depend on abstractions.

### Bad — high-level logic coupled to infrastructure

```python
import psycopg2

class TransactionService:
    def __init__(self) -> None:
        self.conn = psycopg2.connect("dbname=revolut")

    def transfer(self, from_id: int, to_id: int, amount: Decimal) -> None:
        cursor = self.conn.cursor()
        cursor.execute("UPDATE accounts SET balance = balance - %s WHERE id = %s", (amount, from_id))
        cursor.execute("UPDATE accounts SET balance = balance + %s WHERE id = %s", (amount, to_id))
        self.conn.commit()
```

Can't test without a real Postgres. Can't swap to DynamoDB. Business logic is buried in SQL.

### Good — depend on abstractions

```python
from typing import Protocol

class AccountRepository(Protocol):
    def debit(self, account_id: int, amount: Decimal) -> None: ...
    def credit(self, account_id: int, amount: Decimal) -> None: ...

class TransactionService:
    def __init__(self, repo: AccountRepository) -> None:
        self.repo = repo

    def transfer(self, from_id: int, to_id: int, amount: Decimal) -> None:
        self.repo.debit(from_id, amount)
        self.repo.credit(to_id, amount)


# infrastructure layer — implements the protocol
class PostgresAccountRepository:
    def __init__(self, conn: Any) -> None:
        self.conn = conn

    def debit(self, account_id: int, amount: Decimal) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE accounts SET balance = balance - %s WHERE id = %s",
                (amount, account_id),
            )

    def credit(self, account_id: int, amount: Decimal) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE accounts SET balance = balance + %s WHERE id = %s",
                (amount, account_id),
            )
```

**Wiring it together** — use a simple composition root (no DI frameworks needed in Python):

```python
def create_app() -> TransactionService:
    conn = psycopg2.connect("dbname=revolut")
    repo = PostgresAccountRepository(conn)
    return TransactionService(repo)
```

**Testing becomes trivial**:

```python
class FakeAccountRepository:
    def __init__(self) -> None:
        self.accounts: dict[int, Decimal] = {}

    def debit(self, account_id: int, amount: Decimal) -> None:
        self.accounts[account_id] -= amount

    def credit(self, account_id: int, amount: Decimal) -> None:
        self.accounts[account_id] = self.accounts.get(account_id, Decimal(0)) + amount

def test_transfer() -> None:
    repo = FakeAccountRepository()
    repo.accounts = {1: Decimal("100"), 2: Decimal("50")}
    svc = TransactionService(repo)
    svc.transfer(1, 2, Decimal("30"))
    assert repo.accounts[1] == Decimal("70")
    assert repo.accounts[2] == Decimal("80")
```

---

## Quick Reference: Python Tools for SOLID

| Principle | Python Tool                              | When to Use                                        |
| --------- | ---------------------------------------- | -------------------------------------------------- |
| SRP       | Composition, modules                     | Split classes that have multiple reasons to change |
| OCP       | `Protocol`, `singledispatch`, registries | Add behavior without modifying existing code       |
| LSP       | `Protocol`, proper hierarchy design      | Ensure subtypes honor the base contract            |
| ISP       | `Protocol` (structural typing)           | Define small, focused interfaces                   |
| DIP       | `Protocol` + constructor injection       | Decouple business logic from infrastructure        |

---

## Interview Tips

1. **Always use `Protocol` over ABC** when you can — it's more Pythonic (structural typing, no inheritance required) and shows modern Python knowledge

2. **Don't over-engineer**: SOLID isn't about having an interface for every class. It's about knowing when coupling will hurt you. In an interview, explain the trade-off: "For a small script, this is fine. For a production service handling millions of transactions, we want this separation because..."

3. **Revolut-specific angles**:
   - **SRP**: Compliance/audit logging must be separable from business logic (regulatory requirement)
   - **OCP**: New payment methods (Apple Pay, crypto) shouldn't require rewriting the payment engine
   - **LSP**: Different account types (current, savings, fixed deposit) must behave predictably in polymorphic code
   - **ISP**: Microservices should expose narrow interfaces — a read-only analytics service shouldn't need write permissions
   - **DIP**: Swapping databases, message queues, or third-party APIs (KYC providers, card networks) without touching business logic

4. **Connect to testing**: SOLID code is testable code. DIP + ISP means you can test business logic with fakes instead of spinning up infrastructure.

---

## Evaluation (2026-04-22)

| Principle | Rating   | Notes                                                                                                                                                                                                                                                |
| --------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| SRP       | Strong   | Solid understanding of stakeholders and extraction. Correctly identified email as a separate concern. Gap: unsure when to stop splitting — learn the heuristic: "if two things change together for the same reason, they belong together"            |
| OCP       | Strong   | Good strategy pattern example using `Protocol` and registry dict. Understood why if/else chains violate OCP                                                                                                                                          |
| LSP       | Moderate | Understood violations (Penguin/Bird), but first instinct was to weaken the parent contract rather than redesign the hierarchy. Needed prompting to arrive at composition with `Flyable`/`Walkable`. Study: preconditions, postconditions, invariants |
| ISP       | Weak     | Knew the definition but couldn't articulate practical consequences in Python beyond `@runtime_checkable`. Study: testing burden, implementation burden, coupling from fat interfaces                                                                 |
| DIP       | Moderate | Confused dependency injection (a technique) with dependency inversion (a design principle). Did not know that the high-level module owns the abstraction. Study: who owns the `Protocol` and why the dependency arrow flips                          |

### Key areas to revisit

- **Dependency injection vs. inversion**: injection is passing dependencies in; inversion is flipping who owns the abstraction so the low-level module conforms upward
- **Abstraction ownership**: the `Protocol` lives with the consumer, not the implementor
- **LSP contract rules**: subtypes must not strengthen preconditions or weaken postconditions
- **ISP in practice**: fat interfaces hurt testing (stub 10 methods to test 2), create implementation burden (`pass`/`NotImplementedError`), and increase coupling
- **When to violate SOLID**: at small scale / MVP stage, strict adherence creates complexity without payoff — apply when the pain of not having them exceeds the cost

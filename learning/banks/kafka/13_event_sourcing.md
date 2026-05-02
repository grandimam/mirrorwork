# Chapter 13: Event Sourcing

## Overview

Event sourcing is an architectural pattern where state is derived from a sequence of events. Kafka's immutable log makes it an excellent platform for event-sourced systems.

## Learning Objectives

By the end of this chapter, you will:

- Understand event sourcing pattern
- Build event-sourced systems with Kafka
- Handle event replay and snapshots
- Know trade-offs and challenges

## Resources

| Resource | Time |
|----------|------|
| Read: Event Sourcing pattern | 30 min |
| Hands-on: Build simple event-sourced system | 1 hr |

## Core Concepts

### Traditional CRUD vs Event Sourcing

```
Traditional CRUD:
─────────────────
Initial: balance = 0
UPDATE accounts SET balance = 100 WHERE id = 1
UPDATE accounts SET balance = 200 WHERE id = 1
UPDATE accounts SET balance = 150 WHERE id = 1

Current state: balance = 150
History: LOST - we only know current value

Event Sourcing:
───────────────
Event 1: AccountCreated { id: 1, balance: 0 }
Event 2: MoneyDeposited { id: 1, amount: 100 }
Event 3: MoneyDeposited { id: 1, amount: 100 }
Event 4: MoneyWithdrawn { id: 1, amount: 50 }

Current state = replay all events = balance: 150
History: PRESERVED - complete audit trail
```

### Why Kafka for Event Sourcing?

```
Kafka provides:
✓ Immutable log - events never change
✓ Retention - events kept for configurable time
✓ Replay - consumers can re-read from any offset
✓ Ordering - events ordered within partition
✓ Scalability - distribute across partitions
✓ Durability - replicated for fault tolerance
```

### Event Store Architecture

```
┌─────────────┐     Commands      ┌─────────────────┐
│   Client    │ ─────────────────►│  Command        │
└─────────────┘                   │  Handler        │
                                  └────────┬────────┘
                                           │
                                           │ Validate & Create Event
                                           ▼
                                  ┌─────────────────┐
                                  │  Event Store    │
                                  │  (Kafka Topic)  │
                                  └────────┬────────┘
                                           │
                        ┌──────────────────┼──────────────────┐
                        │                  │                  │
                        ▼                  ▼                  ▼
               ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
               │  Projection │    │  Projection │    │  Projection │
               │  (Read DB)  │    │  (Search)   │    │  (Analytics)│
               └─────────────┘    └─────────────┘    └─────────────┘
```

## Key Questions to Understand

- How is event sourcing different from CRUD?
- Why is Kafka a good fit for event sourcing?
- How do you rebuild state from events?

## Hands-On Exercises

### Exercise 1: Define Events

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Union
import json

@dataclass
class AccountCreated:
    account_id: str
    owner: str
    timestamp: datetime

@dataclass
class MoneyDeposited:
    account_id: str
    amount: float
    timestamp: datetime

@dataclass
class MoneyWithdrawn:
    account_id: str
    amount: float
    timestamp: datetime

Event = Union[AccountCreated, MoneyDeposited, MoneyWithdrawn]

def serialize_event(event: Event) -> bytes:
    data = {
        'type': event.__class__.__name__,
        'data': {
            'account_id': event.account_id,
            'timestamp': event.timestamp.isoformat(),
        }
    }
    if hasattr(event, 'owner'):
        data['data']['owner'] = event.owner
    if hasattr(event, 'amount'):
        data['data']['amount'] = event.amount
    return json.dumps(data).encode()
```

### Exercise 2: Event Store

```python
from confluent_kafka import Producer, Consumer

class EventStore:
    def __init__(self, bootstrap_servers: str):
        self.producer = Producer({
            'bootstrap.servers': bootstrap_servers,
            'enable.idempotence': True,
        })

    def append(self, stream: str, event: Event):
        """Append event to stream (Kafka topic)"""
        self.producer.produce(
            topic=stream,
            key=event.account_id.encode(),
            value=serialize_event(event),
        )
        self.producer.flush()

    def read_stream(self, stream: str, from_beginning: bool = True):
        """Read all events from stream"""
        consumer = Consumer({
            'bootstrap.servers': 'localhost:9092',
            'group.id': f'reader-{stream}-{time.time()}',
            'auto.offset.reset': 'earliest' if from_beginning else 'latest',
        })
        consumer.subscribe([stream])

        events = []
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                break
            events.append(deserialize_event(msg.value()))

        consumer.close()
        return events
```

### Exercise 3: Aggregate (State Rebuilding)

```python
@dataclass
class Account:
    id: str
    owner: str
    balance: float
    version: int

    @staticmethod
    def apply(state: 'Account', event: Event) -> 'Account':
        """Apply event to state, return new state"""
        if isinstance(event, AccountCreated):
            return Account(
                id=event.account_id,
                owner=event.owner,
                balance=0.0,
                version=1
            )
        elif isinstance(event, MoneyDeposited):
            return Account(
                id=state.id,
                owner=state.owner,
                balance=state.balance + event.amount,
                version=state.version + 1
            )
        elif isinstance(event, MoneyWithdrawn):
            return Account(
                id=state.id,
                owner=state.owner,
                balance=state.balance - event.amount,
                version=state.version + 1
            )
        return state

    @staticmethod
    def rebuild(events: list[Event]) -> 'Account':
        """Rebuild state from events"""
        state = None
        for event in events:
            state = Account.apply(state, event)
        return state
```

### Exercise 4: Command Handler

```python
class AccountCommandHandler:
    def __init__(self, event_store: EventStore):
        self.event_store = event_store

    def handle_create(self, account_id: str, owner: str):
        event = AccountCreated(
            account_id=account_id,
            owner=owner,
            timestamp=datetime.utcnow()
        )
        self.event_store.append('account-events', event)

    def handle_deposit(self, account_id: str, amount: float):
        # Load current state
        events = self.event_store.read_stream('account-events')
        account_events = [e for e in events if e.account_id == account_id]
        account = Account.rebuild(account_events)

        if account is None:
            raise ValueError(f'Account {account_id} not found')

        event = MoneyDeposited(
            account_id=account_id,
            amount=amount,
            timestamp=datetime.utcnow()
        )
        self.event_store.append('account-events', event)

    def handle_withdraw(self, account_id: str, amount: float):
        # Load current state
        events = self.event_store.read_stream('account-events')
        account_events = [e for e in events if e.account_id == account_id]
        account = Account.rebuild(account_events)

        if account is None:
            raise ValueError(f'Account {account_id} not found')

        if account.balance < amount:
            raise ValueError('Insufficient funds')

        event = MoneyWithdrawn(
            account_id=account_id,
            amount=amount,
            timestamp=datetime.utcnow()
        )
        self.event_store.append('account-events', event)
```

### Exercise 5: Projections

```python
class BalanceProjection:
    """Maintains current balances in a read-optimized store"""

    def __init__(self, bootstrap_servers: str, db):
        self.db = db
        self.consumer = Consumer({
            'bootstrap.servers': bootstrap_servers,
            'group.id': 'balance-projection',
            'auto.offset.reset': 'earliest',
        })

    def run(self):
        self.consumer.subscribe(['account-events'])

        while True:
            msg = self.consumer.poll(1.0)
            if msg is None:
                continue

            event = deserialize_event(msg.value())
            self.apply(event)

    def apply(self, event: Event):
        if isinstance(event, AccountCreated):
            self.db.execute(
                "INSERT INTO balances (account_id, owner, balance) VALUES (?, ?, 0)",
                (event.account_id, event.owner)
            )
        elif isinstance(event, MoneyDeposited):
            self.db.execute(
                "UPDATE balances SET balance = balance + ? WHERE account_id = ?",
                (event.amount, event.account_id)
            )
        elif isinstance(event, MoneyWithdrawn):
            self.db.execute(
                "UPDATE balances SET balance = balance - ? WHERE account_id = ?",
                (event.amount, event.account_id)
            )
```

## Snapshots

For long event streams, replay can be slow. Use snapshots:

```python
# Snapshot topic (compacted)
SNAPSHOT_TOPIC = 'account-snapshots'  # cleanup.policy=compact

class SnapshotStore:
    def save_snapshot(self, account: Account):
        producer.produce(
            SNAPSHOT_TOPIC,
            key=account.id.encode(),
            value=json.dumps({
                'id': account.id,
                'owner': account.owner,
                'balance': account.balance,
                'version': account.version,
                'event_offset': current_offset,  # Last applied event
            }).encode()
        )

    def load_snapshot(self, account_id: str) -> tuple[Account, int]:
        # Read from compacted topic
        snapshot_data = read_latest_for_key(SNAPSHOT_TOPIC, account_id)
        if snapshot_data:
            return Account(**snapshot_data), snapshot_data['event_offset']
        return None, 0

def rebuild_with_snapshot(account_id: str) -> Account:
    # Load snapshot
    snapshot, offset = snapshot_store.load_snapshot(account_id)

    # Apply events since snapshot
    events = event_store.read_stream_from_offset('account-events', offset)
    account_events = [e for e in events if e.account_id == account_id]

    account = snapshot
    for event in account_events:
        account = Account.apply(account, event)

    return account
```

## Interview Questions

- "What is event sourcing and why would you use it?"
  - Not: "It stores events instead of state"
  - But: "State is derived from a sequence of events. Benefits: complete audit trail, can replay to any point in time, supports multiple read models (projections), natural fit for event-driven architectures. Trade-offs: eventual consistency, complexity, storage growth."

- "How does Kafka support event sourcing?"
  - "Kafka is an immutable, append-only log - exactly what event sourcing needs. Retention keeps events, partitioning by entity ID ensures ordering, consumers can replay from any offset, compacted topics work for snapshots."

- "How do you handle long event streams?"
  - "Snapshots. Periodically capture current state in a compacted topic. On load, read latest snapshot then apply only events since snapshot. Balance between snapshot frequency and replay time."

## Common Pitfalls

1. **No snapshots for long streams** - Slow rebuilds
2. **Mutable events** - Breaks event sourcing contract
3. **Too granular events** - Explosion of events
4. **Missing event versioning** - Can't evolve schemas
5. **Eventual consistency surprises** - Projections lag behind

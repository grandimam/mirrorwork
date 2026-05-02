# Chapter 22: Read Replicas

## Overview

Read replicas distribute read traffic across multiple database instances while writes go to the primary. This scaling pattern improves read throughput and provides redundancy, but requires careful handling of replication lag.

## Learning Objectives

By the end of this chapter, you will:

- Route reads to replicas in your application
- Handle replication lag gracefully
- Design read/write split architectures
- Scale read-heavy workloads

## Resources

| Resource | Time |
|----------|------|
| Read: Read replica patterns | 30 min |
| Hands-on: Implement read/write splitting | 30 min |

## Core Concepts

### Read Replica Architecture

```
              ┌─────────────────────────────────┐
              │         Load Balancer            │
              │    (or Application Logic)        │
              └──────────────┬──────────────────┘
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
          ▼                  ▼                  ▼
    ┌──────────┐      ┌──────────┐      ┌──────────┐
    │ Primary  │ ───► │ Replica 1│      │ Replica 2│
    │  (R/W)   │ WAL  │   (R)    │      │   (R)    │
    └──────────┘      └──────────┘      └──────────┘
          │                                   ▲
          └───────────────────────────────────┘
                        WAL Stream
```

### Application-Level Routing

```python
# Python example with SQLAlchemy
from sqlalchemy import create_engine
from random import choice

class DatabaseRouter:
    def __init__(self):
        self.primary = create_engine(
            "postgresql://user:pass@primary:5432/mydb"
        )
        self.replicas = [
            create_engine("postgresql://user:pass@replica1:5432/mydb"),
            create_engine("postgresql://user:pass@replica2:5432/mydb"),
        ]

    def get_write_engine(self):
        return self.primary

    def get_read_engine(self):
        return choice(self.replicas)

# Usage
router = DatabaseRouter()

# Write operation - always to primary
with router.get_write_engine().connect() as conn:
    conn.execute("INSERT INTO users (email) VALUES (%s)", email)

# Read operation - to replica
with router.get_read_engine().connect() as conn:
    result = conn.execute("SELECT * FROM users WHERE id = %s", user_id)
```

### Handling Replication Lag

```python
# Problem: Write then immediate read might miss the write
router.get_write_engine().execute("UPDATE users SET name = 'Alice' WHERE id = 1")
# If replica is lagging, this might return old data:
router.get_read_engine().execute("SELECT name FROM users WHERE id = 1")

# Solution 1: Read from primary after writes
class SmartRouter:
    def __init__(self):
        self.primary = create_engine("postgresql://primary:5432/mydb")
        self.replicas = [create_engine("postgresql://replica:5432/mydb")]
        self._force_primary = threading.local()

    def force_primary_for_request(self):
        """Call after writes to ensure reads hit primary"""
        self._force_primary.value = True

    def get_read_engine(self):
        if getattr(self._force_primary, 'value', False):
            return self.primary
        return choice(self.replicas)

# Usage in web request
def update_user(user_id, name):
    router.get_write_engine().execute("UPDATE users SET name = %s WHERE id = %s", name, user_id)
    router.force_primary_for_request()
    # Subsequent reads in this request go to primary
```

```python
# Solution 2: Check replica lag before routing
def get_read_engine_with_lag_check(max_lag_seconds=1):
    for replica in replicas:
        lag = check_replica_lag(replica)
        if lag < max_lag_seconds:
            return replica
    # All replicas lagging, use primary
    return primary

def check_replica_lag(engine):
    result = engine.execute("""
        SELECT EXTRACT(EPOCH FROM NOW() - pg_last_xact_replay_timestamp())
        AS lag_seconds
    """)
    return result.scalar() or 0
```

### Read Replica in Different Frameworks

**Django:**

```python
# settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'HOST': 'primary',
        'PORT': '5432',
        'NAME': 'mydb',
    },
    'replica': {
        'ENGINE': 'django.db.backends.postgresql',
        'HOST': 'replica',
        'PORT': '5432',
        'NAME': 'mydb',
    }
}

# Database router
class PrimaryReplicaRouter:
    def db_for_read(self, model, **hints):
        return 'replica'

    def db_for_write(self, model, **hints):
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        return db == 'default'

DATABASE_ROUTERS = ['myapp.routers.PrimaryReplicaRouter']

# Force primary for specific queries
User.objects.using('default').get(id=1)
```

**Rails:**

```ruby
# config/database.yml
production:
  primary:
    <<: *default
    host: primary.host
  replica:
    <<: *default
    host: replica.host
    replica: true

# In code
ActiveRecord::Base.connected_to(role: :reading) do
  User.find(1)  # Uses replica
end

ActiveRecord::Base.connected_to(role: :writing) do
  User.create(name: 'Alice')  # Uses primary
end
```

### Load Balancing Replicas

```python
# Round-robin with health checks
class ReplicaPool:
    def __init__(self, replica_hosts):
        self.replicas = [create_engine(f"postgresql://{h}/mydb") for h in replica_hosts]
        self.current = 0
        self.healthy = set(range(len(self.replicas)))

    def get_replica(self):
        if not self.healthy:
            raise Exception("No healthy replicas")

        # Round-robin among healthy replicas
        attempts = len(self.replicas)
        while attempts > 0:
            idx = self.current % len(self.replicas)
            self.current += 1
            if idx in self.healthy:
                return self.replicas[idx]
            attempts -= 1

        raise Exception("No healthy replicas")

    def mark_unhealthy(self, idx):
        self.healthy.discard(idx)

    def mark_healthy(self, idx):
        self.healthy.add(idx)

    def health_check(self):
        for idx, replica in enumerate(self.replicas):
            try:
                replica.execute("SELECT 1")
                self.mark_healthy(idx)
            except:
                self.mark_unhealthy(idx)
```

### When to Read from Primary

```python
# Always read from primary when:
# 1. Just wrote data that must be immediately read
# 2. Strong consistency required
# 3. Transaction spans read and write
# 4. Replica lag exceeds acceptable threshold

def should_use_primary(context):
    # Just wrote in this request
    if context.get('wrote_to_db'):
        return True

    # Critical path requiring consistency
    if context.get('requires_consistency'):
        return True

    # User is viewing their own just-modified data
    if context.get('viewing_own_data') and context.get('recently_modified'):
        return True

    return False
```

## Key Questions to Understand

- How do you handle replication lag in the application?
- When should reads go to primary instead of replica?
- How do you load balance across multiple replicas?

## Hands-On Exercises

### Exercise 1: Implement Basic Read/Write Split

```python
# Simple read/write split implementation
import psycopg2
from contextlib import contextmanager

class DBPool:
    def __init__(self, primary_dsn, replica_dsns):
        self.primary_dsn = primary_dsn
        self.replica_dsns = replica_dsns
        self._replica_idx = 0

    @contextmanager
    def write_connection(self):
        conn = psycopg2.connect(self.primary_dsn)
        try:
            yield conn
            conn.commit()
        except:
            conn.rollback()
            raise
        finally:
            conn.close()

    @contextmanager
    def read_connection(self):
        # Round-robin replica selection
        dsn = self.replica_dsns[self._replica_idx % len(self.replica_dsns)]
        self._replica_idx += 1

        conn = psycopg2.connect(dsn)
        try:
            yield conn
        finally:
            conn.close()

# Usage
pool = DBPool(
    primary_dsn="postgresql://primary/mydb",
    replica_dsns=["postgresql://replica1/mydb", "postgresql://replica2/mydb"]
)

with pool.write_connection() as conn:
    conn.cursor().execute("INSERT INTO logs (msg) VALUES ('test')")

with pool.read_connection() as conn:
    cur = conn.cursor()
    cur.execute("SELECT * FROM logs")
    rows = cur.fetchall()
```

### Exercise 2: Lag-Aware Routing

```python
def get_replica_with_acceptable_lag(replicas, max_lag_ms=100):
    for replica in replicas:
        try:
            with replica.connect() as conn:
                result = conn.execute("""
                    SELECT
                        pg_wal_lsn_diff(
                            pg_last_wal_receive_lsn(),
                            pg_last_wal_replay_lsn()
                        ) as lag_bytes,
                        EXTRACT(EPOCH FROM NOW() - pg_last_xact_replay_timestamp()) * 1000
                        as lag_ms
                """)
                row = result.fetchone()
                if row and row['lag_ms'] < max_lag_ms:
                    return replica
        except Exception:
            continue

    return None  # No suitable replica, use primary
```

### Exercise 3: Sticky Session for Write-Then-Read

```python
# Flask middleware example
from flask import Flask, g, request
import time

app = Flask(__name__)

@app.before_request
def before_request():
    # Check if this user recently wrote
    user_id = get_current_user_id()
    last_write = cache.get(f"user:{user_id}:last_write")

    if last_write and (time.time() - last_write) < 5:  # 5 second window
        g.use_primary = True
    else:
        g.use_primary = False

def record_write():
    """Call after any write operation"""
    user_id = get_current_user_id()
    cache.set(f"user:{user_id}:last_write", time.time(), ex=10)
    g.use_primary = True

def get_db_connection():
    if g.use_primary:
        return primary_pool.getconn()
    return replica_pool.getconn()
```

## Interview Deep Dive

### Question: "How would you implement read replicas in an application?"

**Answer:**
> "I'd implement a database router that directs writes to primary and reads to replicas. Key considerations: 1) Handle replication lag - either by routing reads to primary immediately after writes (sticky session), or checking replica lag before routing. 2) Health checking - monitor replica health and remove unhealthy ones from rotation. 3) Load balancing - round-robin or weighted distribution across replicas.
>
> In practice, I'd use framework support (Django's database routers, Rails' multiple databases) or connection poolers like PgBouncer with multiple database definitions. Critical reads or reads-after-writes always go to primary to avoid stale data issues."

### Question: "How do you handle read-after-write consistency with replicas?"

**Answer:**
> "Several approaches: 1) Session affinity - after a write, route all reads from that user to primary for a short window (5-10 seconds). 2) Causal consistency - track the write's LSN and wait for replica to reach it before reading. 3) Hybrid routing - route critical paths to primary, non-critical to replicas.
>
> In most cases, session affinity is simplest - set a flag or cache entry after writes that forces subsequent reads to primary. The consistency window can be short because replication is usually sub-second. For truly critical paths, just always use primary."

## Key Takeaways

1. **Route writes to primary**, reads to replicas
2. **Handle replication lag** with sticky sessions or lag checks
3. **Health check replicas** and remove unhealthy ones
4. **Read from primary** after writes for consistency
5. **Use framework support** when available

## Self-Assessment Questions

1. How do you handle read-after-write consistency?
2. What happens if all replicas are lagging?
3. How do you load balance across multiple replicas?
4. When should reads always go to primary?
5. How do you monitor replica health?

## Next Chapter

[Chapter 23: Configuration Tuning →](./23_configuration_tuning.md)

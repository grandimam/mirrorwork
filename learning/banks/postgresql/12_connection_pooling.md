# Chapter 19: Connection Pooling (PgBouncer)

## Overview

PostgreSQL forks a new process for each connection, consuming significant memory. Connection pooling with tools like PgBouncer allows many application connections to share fewer database connections, dramatically improving scalability.

## Learning Objectives

By the end of this chapter, you will:

- Understand why connection pooling matters
- Configure PgBouncer
- Choose the right pooling mode
- Handle pooling limitations

## Resources

| Resource | Time |
|----------|------|
| Read: PgBouncer documentation | 30 min |
| Hands-on: Set up PgBouncer | 30 min |

## Core Concepts

### Why Connection Pooling?

```
PostgreSQL Connection Cost:
- Each connection = new process (fork)
- Memory: ~10MB per connection
- CPU: context switching overhead
- Typical max_connections: 100-500

Application Reality:
- 100 app servers × 10 connections = 1000 connections
- Exceeds max_connections
- Wastes memory (connections often idle)

With PgBouncer:
- App → PgBouncer (1000 connections) → PostgreSQL (50 connections)
- 95% less memory usage
- Same or better performance
```

### Connection Overhead

```sql
-- Check current connections
SELECT count(*) FROM pg_stat_activity;

-- Check connection settings
SHOW max_connections;  -- typically 100-200

-- Memory per connection
-- Approximately: shared_buffers/max_connections + work_mem
-- Example: 4GB/200 + 256MB = ~276MB potential per connection

-- View connection memory
SELECT
    sum(pg_total_relation_size(oid)) as total_size
FROM pg_class
WHERE relkind = 'r';
```

### PgBouncer Architecture

```
┌──────────────────────────────────────────────────────────┐
│                     Application Servers                   │
│ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐         │
│ │App 1│ │App 2│ │App 3│ │App 4│ │App 5│ │App N│         │
│ └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘         │
│    │       │       │       │       │       │             │
│    └───────┴───────┴───────┼───────┴───────┘             │
│                            │                              │
│                            ▼                              │
│                     ┌─────────────┐                       │
│                     │  PgBouncer  │                       │
│                     │  Pool: 50   │                       │
│                     └──────┬──────┘                       │
│                            │                              │
│                            ▼                              │
│                     ┌─────────────┐                       │
│                     │ PostgreSQL  │                       │
│                     │ max_conn:100│                       │
│                     └─────────────┘                       │
└──────────────────────────────────────────────────────────┘
```

### Pooling Modes

| Mode | Description | Use Case | Limitations |
|------|-------------|----------|-------------|
| Session | Connection per session | Everything works | Least efficient |
| Transaction | Connection per transaction | Most applications | No session state |
| Statement | Connection per statement | Simple queries | No transactions |

```ini
; pgbouncer.ini

; Session pooling - connection for entire session
; Most compatible, least efficient
pool_mode = session

; Transaction pooling - connection per transaction
; Most common for web apps
pool_mode = transaction

; Statement pooling - connection per statement
; Maximum efficiency, most limitations
pool_mode = statement
```

### PgBouncer Configuration

```ini
; /etc/pgbouncer/pgbouncer.ini

[databases]
; database_alias = connection_string
mydb = host=localhost port=5432 dbname=mydb
mydb_replica = host=replica.host port=5432 dbname=mydb

[pgbouncer]
listen_addr = 0.0.0.0
listen_port = 6432

; Authentication
auth_type = md5
auth_file = /etc/pgbouncer/userlist.txt

; Pool settings
pool_mode = transaction
max_client_conn = 1000      ; Max connections from apps
default_pool_size = 50       ; Connections to PostgreSQL per database
min_pool_size = 10          ; Minimum idle connections
reserve_pool_size = 5       ; Extra connections for burst

; Timeouts
query_timeout = 0           ; 0 = unlimited
client_idle_timeout = 0     ; 0 = unlimited
server_idle_timeout = 600   ; Close idle server connections
```

**userlist.txt:**

```
"postgres" "md5password_hash_here"
"app_user" "md5another_hash"
```

### Transaction Mode Limitations

```sql
-- These DON'T work with transaction pooling:

-- 1. SET commands (lost after transaction)
SET search_path = myschema;  -- Lost next transaction

-- 2. PREPARE statements
PREPARE stmt AS SELECT * FROM users WHERE id = $1;
EXECUTE stmt(1);  -- Might use different connection

-- 3. LISTEN/NOTIFY
LISTEN channel;  -- Connection changes between transactions

-- 4. Advisory locks (session-level)
SELECT pg_advisory_lock(123);  -- Released when connection returns to pool

-- 5. Temporary tables
CREATE TEMP TABLE tmp (id INT);  -- Gone next transaction

-- Solutions:
-- 1. Use session pooling for features that need session state
-- 2. Configure separate session pool for admin tasks
-- 3. Use transaction-level alternatives where available
```

### Monitoring PgBouncer

```sql
-- Connect to PgBouncer admin console
psql -h localhost -p 6432 -U pgbouncer pgbouncer

-- Show pools
SHOW POOLS;
-- database | user | cl_active | cl_waiting | sv_active | sv_idle | sv_used | sv_tested | sv_login | maxwait

-- Show stats
SHOW STATS;
-- Shows requests, bytes, query times

-- Show clients
SHOW CLIENTS;

-- Show servers (actual PostgreSQL connections)
SHOW SERVERS;

-- Show databases
SHOW DATABASES;
```

### Connection String

```python
# Application connects to PgBouncer port
# Before: postgresql://user:pass@db-host:5432/mydb
# After:  postgresql://user:pass@pgbouncer:6432/mydb

import psycopg2

# For transaction pooling, disable client-side connection prep
conn = psycopg2.connect(
    host='pgbouncer-host',
    port=6432,
    database='mydb',
    user='app_user',
    password='secret',
    options='-c statement_timeout=30000'  # OK, per-statement
)
```

### Application Considerations

```python
# Disable session-level features for transaction pooling

# SQLAlchemy example
from sqlalchemy import create_engine

engine = create_engine(
    'postgresql://user:pass@pgbouncer:6432/mydb',
    pool_pre_ping=True,  # Verify connection before use
    pool_size=10,        # App-level pool (PgBouncer does main pooling)
    pool_recycle=300,    # Recycle connections every 5 minutes
    connect_args={
        'options': '-c search_path=public'  # If needed
    }
)

# Django settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'HOST': 'pgbouncer-host',
        'PORT': '6432',
        'NAME': 'mydb',
        'USER': 'app_user',
        'PASSWORD': 'secret',
        'CONN_MAX_AGE': 0,  # Let PgBouncer handle pooling
    }
}
```

## Key Questions to Understand

- Why is PostgreSQL per-connection overhead high?
- What's the difference between session, transaction, and statement pooling?
- What breaks in transaction pooling mode?

## Hands-On Exercises

### Exercise 1: Set Up PgBouncer

```bash
# Docker setup
docker run -d --name pgbouncer \
  -e DATABASE_URL="postgres://user:pass@host:5432/mydb" \
  -e POOL_MODE=transaction \
  -e MAX_CLIENT_CONN=100 \
  -e DEFAULT_POOL_SIZE=20 \
  -p 6432:6432 \
  edoburu/pgbouncer

# Test connection
psql -h localhost -p 6432 -U user mydb -c "SELECT 1"
```

### Exercise 2: Monitor Connection Usage

```sql
-- Check PostgreSQL connections
SELECT
    count(*) as total,
    count(*) FILTER (WHERE state = 'active') as active,
    count(*) FILTER (WHERE state = 'idle') as idle,
    count(*) FILTER (WHERE state = 'idle in transaction') as idle_txn
FROM pg_stat_activity
WHERE backend_type = 'client backend';

-- In PgBouncer:
-- psql -h localhost -p 6432 pgbouncer
SHOW POOLS;
SHOW STATS;
```

### Exercise 3: Test Pooling Mode Differences

```sql
-- Test with session pooling
SET pool_mode TO session;  -- In pgbouncer admin

-- This works:
SET search_path = test_schema;
SELECT current_schema();  -- test_schema
-- (different transaction)
SELECT current_schema();  -- Still test_schema

-- Test with transaction pooling
SET pool_mode TO transaction;

-- This DOESN'T persist:
SET search_path = test_schema;
SELECT current_schema();  -- test_schema
-- (end transaction, start new)
SELECT current_schema();  -- public (default)
```

## Interview Deep Dive

### Question: "Why use connection pooling with PostgreSQL?"

**Answer:**
> "PostgreSQL forks a new backend process per connection - roughly 10MB each plus overhead. With many application servers, you can easily exceed max_connections or waste memory on idle connections. PgBouncer sits between apps and PostgreSQL, multiplexing many app connections onto fewer database connections.
>
> In transaction mode, a database connection is used only during a transaction then returned to the pool - 1000 app connections might only need 50 database connections. This dramatically reduces PostgreSQL memory usage, eliminates connection establishment overhead, and lets you scale horizontally without hitting connection limits."

### Question: "What are the limitations of transaction pooling?"

**Answer:**
> "Transaction pooling reassigns connections between transactions, so anything session-level breaks: SET commands (search_path, statement_timeout at session level), PREPARE/EXECUTE (prepared statements), LISTEN/NOTIFY, session-level advisory locks, and temporary tables.
>
> Workarounds: use statement-level options (SET LOCAL), use server-side connection setup, maintain a separate session pool for admin tasks, or use application-level caching for prepared statements. Most web applications work fine because they naturally execute discrete transactions."

## Key Takeaways

1. **Connection pooling** is essential for scaling PostgreSQL
2. **Transaction mode** offers best balance of efficiency and compatibility
3. **Session-level features** don't work with transaction pooling
4. **Monitor pools** to right-size default_pool_size
5. **Application-level pools** can be minimal when using PgBouncer

## Self-Assessment Questions

1. How much memory does each PostgreSQL connection use?
2. What happens to SET commands in transaction pooling?
3. When would you use session pooling instead of transaction?
4. How do you monitor PgBouncer pool usage?
5. What's the relationship between max_client_conn and default_pool_size?

## Next Chapter

[Chapter 20: Replication →](./20_replication.md)

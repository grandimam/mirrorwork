# Chapter 3: Data Types and When to Use Them

## Overview

PostgreSQL offers a rich set of data types beyond standard SQL. Choosing the right type affects storage efficiency, query performance, and data integrity. This chapter covers both standard and PostgreSQL-specific types.

## Learning Objectives

By the end of this chapter, you will:

- Choose appropriate data types for each use case
- Use PostgreSQL-specific types (JSONB, arrays, ranges)
- Understand storage implications
- Know when to use specialized types

## Resources

| Resource | Time |
|----------|------|
| Read: https://www.postgresql.org/docs/current/datatype.html | 30 min |
| Hands-on: Experiment with different types | 30 min |

## Core Concepts

### Type Selection Guide

| Use Case | Type | Why |
|----------|------|-----|
| Money | NUMERIC(10,2) | Exact precision, no floating point errors |
| Floating point | DOUBLE PRECISION | When precision loss OK |
| Free text | TEXT | No length limit, same performance as VARCHAR |
| Fixed-length codes | CHAR(n) | When all values are same length |
| Variable text | VARCHAR(n) | When max length constraint needed |
| Primary key | SERIAL/BIGSERIAL or UUID | Auto-generated unique IDs |
| Timestamp | TIMESTAMPTZ | Always store with timezone |
| Date only | DATE | No time component |
| Booleans | BOOLEAN | true/false/null |
| JSON data | JSONB | Indexable, compressed binary |
| Arrays | INTEGER[] | Native array support |
| IP addresses | INET/CIDR | Native type with functions |
| Ranges | INT4RANGE, TSTZRANGE | Range operations |

### Numeric Types

```sql
-- Integer types
SMALLINT    -- 2 bytes, -32768 to 32767
INTEGER     -- 4 bytes, -2B to 2B
BIGINT      -- 8 bytes, very large

-- Auto-increment
SERIAL      -- INTEGER with sequence
BIGSERIAL   -- BIGINT with sequence

-- Floating point (approximate)
REAL            -- 4 bytes, ~6 decimal digits precision
DOUBLE PRECISION -- 8 bytes, ~15 decimal digits precision

-- Exact numeric
NUMERIC(precision, scale)  -- up to 131072 digits
DECIMAL(10, 2)             -- same as NUMERIC

-- Examples
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    price NUMERIC(10, 2) NOT NULL,  -- $99,999,999.99 max
    weight REAL,                     -- approximate is OK
    quantity INTEGER DEFAULT 0
);

-- Floating point pitfall
SELECT 0.1::REAL + 0.2::REAL = 0.3::REAL;  -- FALSE!
SELECT 0.1::NUMERIC + 0.2::NUMERIC = 0.3::NUMERIC;  -- TRUE
```

### Text Types

```sql
-- TEXT vs VARCHAR vs CHAR
TEXT            -- unlimited length
VARCHAR(n)      -- variable, max n characters
CHAR(n)         -- fixed length, padded with spaces

-- Performance: TEXT and VARCHAR(n) are identical
-- Only difference: VARCHAR(n) enforces max length

-- When to use each:
-- TEXT: most cases, no artificial limit
-- VARCHAR(n): when business rule requires max length
-- CHAR(n): rarely, only for fixed-length codes like ISO country codes

CREATE TABLE users (
    email TEXT NOT NULL,  -- no artificial limit
    country_code CHAR(2), -- always 2 characters
    bio TEXT              -- unlimited
);

-- Text search
SELECT * FROM users WHERE email ILIKE '%@gmail.com';
```

### Date/Time Types

```sql
-- Always use TIMESTAMPTZ for timestamps!
TIMESTAMP           -- no timezone info (avoid!)
TIMESTAMPTZ         -- with timezone (preferred)
DATE                -- date only
TIME                -- time only
INTERVAL            -- duration

-- Examples
CREATE TABLE events (
    id SERIAL PRIMARY KEY,
    name TEXT,
    starts_at TIMESTAMPTZ NOT NULL,
    ends_at TIMESTAMPTZ NOT NULL,
    duration INTERVAL GENERATED ALWAYS AS (ends_at - starts_at) STORED
);

-- Timezone handling
SET timezone = 'America/New_York';
INSERT INTO events (name, starts_at, ends_at)
VALUES ('Meeting', '2024-01-15 10:00:00', '2024-01-15 11:00:00');

SET timezone = 'UTC';
SELECT starts_at FROM events;  -- Shows in UTC

-- Date arithmetic
SELECT
    NOW() as now,
    NOW() + INTERVAL '1 day' as tomorrow,
    NOW() - INTERVAL '1 week' as last_week,
    DATE_TRUNC('month', NOW()) as month_start,
    EXTRACT(YEAR FROM NOW()) as year;
```

### Boolean Type

```sql
BOOLEAN  -- TRUE, FALSE, or NULL

-- Accepted inputs
-- TRUE: true, 't', 'yes', 'y', '1', 'on'
-- FALSE: false, 'f', 'no', 'n', '0', 'off'

CREATE TABLE features (
    id SERIAL PRIMARY KEY,
    name TEXT,
    is_enabled BOOLEAN DEFAULT FALSE NOT NULL
);

-- Filtering
SELECT * FROM features WHERE is_enabled;        -- true values
SELECT * FROM features WHERE NOT is_enabled;    -- false values
SELECT * FROM features WHERE is_enabled IS NULL; -- null values
```

### UUID Type

```sql
-- Native UUID type (16 bytes, more efficient than TEXT)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE users (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    email TEXT NOT NULL
);

-- Or with gen_random_uuid() (built-in since PG 13)
CREATE TABLE sessions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- UUID vs SERIAL
-- UUID: globally unique, no sequence, good for distributed systems
-- SERIAL: sequential, simpler, better for B-tree (locality)
```

### JSONB Type

```sql
-- JSONB: binary JSON, indexable, compressed
-- JSON: text, preserves whitespace and order (rarely used)

CREATE TABLE events (
    id SERIAL PRIMARY KEY,
    event_type TEXT NOT NULL,
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO events (event_type, data) VALUES
    ('page_view', '{"page": "/home", "user_id": 123, "duration_ms": 1500}'),
    ('click', '{"element": "signup_button", "user_id": 123}'),
    ('purchase', '{"amount": 99.99, "user_id": 456, "items": ["SKU1", "SKU2"]}');

-- Accessing JSON fields
SELECT
    data->>'user_id' as user_id_text,     -- returns TEXT
    (data->>'user_id')::INTEGER as user_id_int,
    data->'items' as items_json,           -- returns JSONB
    data->'items'->>0 as first_item        -- returns TEXT
FROM events;

-- Filtering on JSON
SELECT * FROM events WHERE data->>'user_id' = '123';
SELECT * FROM events WHERE (data->>'amount')::NUMERIC > 50;
SELECT * FROM events WHERE data @> '{"user_id": 123}';  -- contains

-- JSON functions
SELECT
    jsonb_typeof(data->'items') as type,
    jsonb_array_length(data->'items') as item_count
FROM events
WHERE data ? 'items';  -- has key 'items'

-- Indexing JSONB
CREATE INDEX idx_events_user ON events ((data->>'user_id'));
CREATE INDEX idx_events_gin ON events USING GIN (data);

-- GIN index supports:
SELECT * FROM events WHERE data @> '{"user_id": 123}';
SELECT * FROM events WHERE data ? 'amount';
```

### Array Types

```sql
-- Native array support
CREATE TABLE posts (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    tags TEXT[] DEFAULT '{}',
    scores INTEGER[]
);

INSERT INTO posts (title, tags, scores) VALUES
    ('PostgreSQL Tips', ARRAY['postgresql', 'database', 'sql'], ARRAY[5, 4, 5]),
    ('Python Guide', '{"python", "programming"}', '{4, 3, 5}');

-- Querying arrays
SELECT * FROM posts WHERE 'postgresql' = ANY(tags);
SELECT * FROM posts WHERE tags @> ARRAY['postgresql', 'sql'];  -- contains both
SELECT * FROM posts WHERE tags && ARRAY['postgresql', 'python'];  -- overlap

-- Array functions
SELECT
    title,
    array_length(tags, 1) as tag_count,
    tags[1] as first_tag,  -- 1-indexed!
    array_to_string(tags, ', ') as tags_str
FROM posts;

-- Unnest arrays
SELECT title, unnest(tags) as tag FROM posts;

-- Index arrays
CREATE INDEX idx_posts_tags ON posts USING GIN (tags);
```

### Range Types

```sql
-- Built-in range types
INT4RANGE   -- integer range
INT8RANGE   -- bigint range
NUMRANGE    -- numeric range
TSRANGE     -- timestamp without timezone
TSTZRANGE   -- timestamp with timezone
DATERANGE   -- date range

-- Room booking with no overlaps
CREATE TABLE room_bookings (
    id SERIAL PRIMARY KEY,
    room_id INTEGER NOT NULL,
    during TSTZRANGE NOT NULL,
    booked_by TEXT NOT NULL,
    EXCLUDE USING GIST (room_id WITH =, during WITH &&)
);

-- Insert bookings
INSERT INTO room_bookings (room_id, during, booked_by) VALUES
    (1, '[2024-01-15 10:00, 2024-01-15 11:00)', 'Alice'),
    (1, '[2024-01-15 11:00, 2024-01-15 12:00)', 'Bob');

-- This will fail (overlaps with Alice's booking)
INSERT INTO room_bookings (room_id, during, booked_by) VALUES
    (1, '[2024-01-15 10:30, 2024-01-15 11:30)', 'Charlie');
-- ERROR: conflicting key value violates exclusion constraint

-- Range operations
SELECT * FROM room_bookings WHERE during @> '2024-01-15 10:30'::TIMESTAMPTZ;
SELECT * FROM room_bookings WHERE during && '[2024-01-15 10:00, 2024-01-15 12:00)';
```

### Network Address Types

```sql
-- INET: IP address with optional subnet
-- CIDR: network address
-- MACADDR: MAC address

CREATE TABLE access_logs (
    id SERIAL PRIMARY KEY,
    client_ip INET NOT NULL,
    requested_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO access_logs (client_ip) VALUES
    ('192.168.1.1'),
    ('10.0.0.50'),
    ('192.168.1.100');

-- Network queries
SELECT * FROM access_logs WHERE client_ip << '192.168.1.0/24';  -- in subnet
SELECT * FROM access_logs WHERE client_ip >= '192.168.1.1' AND client_ip <= '192.168.1.100';

-- Functions
SELECT
    client_ip,
    host(client_ip) as host,
    masklen(client_ip) as mask_length
FROM access_logs;
```

## Key Questions to Understand

- When do you use NUMERIC vs REAL vs DOUBLE PRECISION?
- What's the difference between TEXT and VARCHAR?
- When should you use JSONB vs normalized tables?

## Hands-On Exercises

### Exercise 1: Event Tracking Schema

```sql
-- Design a schema for event tracking with JSONB
CREATE TABLE analytics_events (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    event_type TEXT NOT NULL,
    user_id INTEGER,
    session_id UUID,
    properties JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for common queries
CREATE INDEX idx_events_type ON analytics_events (event_type);
CREATE INDEX idx_events_user ON analytics_events (user_id);
CREATE INDEX idx_events_created ON analytics_events (created_at);
CREATE INDEX idx_events_props ON analytics_events USING GIN (properties);

-- Insert events
INSERT INTO analytics_events (event_type, user_id, properties) VALUES
    ('page_view', 1, '{"path": "/home", "referrer": "google.com"}'),
    ('click', 1, '{"element": "signup", "position": {"x": 100, "y": 200}}');

-- Query nested JSON
SELECT * FROM analytics_events
WHERE properties->'position'->>'x' = '100';
```

### Exercise 2: Time-Based Data

```sql
-- Create a table with proper time handling
CREATE TABLE user_sessions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id INTEGER NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    duration INTERVAL GENERATED ALWAYS AS (ended_at - started_at) STORED
);

-- Calculate session statistics
SELECT
    DATE_TRUNC('day', started_at) as day,
    COUNT(*) as session_count,
    AVG(duration) as avg_duration,
    MAX(duration) as max_duration
FROM user_sessions
WHERE ended_at IS NOT NULL
GROUP BY 1
ORDER BY 1;
```

## Interview Deep Dive

### Question: "When would you use JSONB vs normalized tables?"

**Answer:**
> "JSONB is great for: schema-less data that varies per record, rapid prototyping, storing third-party API responses, and audit logs. I'd normalize when: the structure is stable, I need referential integrity, I'll query/join on nested fields frequently, or I need strong typing. JSONB has overhead - each key stored per row - so highly structured data is more efficient normalized. I often use both: core entities normalized, with a JSONB 'metadata' column for flexible attributes."

### Question: "Why TIMESTAMPTZ over TIMESTAMP?"

**Answer:**
> "TIMESTAMP WITHOUT TIME ZONE stores what you give it with no conversion - '10:00' in any timezone is stored as '10:00'. TIMESTAMPTZ converts to UTC on storage and back to session timezone on retrieval. With TIMESTAMP, if your server timezone changes or users are in different timezones, you get wrong times. Always use TIMESTAMPTZ - it's unambiguous and handles DST correctly. The only exception is when you truly mean 'this time in any timezone' like 'store opens at 9:00 AM' regardless of location."

## Key Takeaways

1. **NUMERIC** for money and exact calculations
2. **TEXT** over VARCHAR unless you need length enforcement
3. **TIMESTAMPTZ** always for timestamps
4. **JSONB** for flexible schema, GIN-indexable
5. **Arrays and ranges** are native - use them
6. **UUID** for distributed systems, SERIAL for simplicity

## Self-Assessment Questions

1. What happens with floating point arithmetic for money?
2. When would you use CHAR(n)?
3. How do you index a JSONB field?
4. What's the difference between -> and ->> operators?
5. How do range exclusion constraints work?

## Next Chapter

[Chapter 4: Constraints and Referential Integrity →](./04_constraints.md)

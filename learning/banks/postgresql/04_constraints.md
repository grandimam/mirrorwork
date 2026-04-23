# Chapter 4: Constraints and Referential Integrity

## Overview

Constraints are rules enforced by the database to maintain data integrity. They're your first line of defense against invalid data, catching errors at the database level rather than relying solely on application logic.

## Learning Objectives

By the end of this chapter, you will:

- Use constraints for data integrity
- Handle constraint violations gracefully
- Design schemas with appropriate constraints
- Know when to use database vs application validation

## Resources

| Resource | Time |
|----------|------|
| Read: PostgreSQL constraints documentation | 30 min |
| Hands-on: Create constraints and test violations | 30 min |

## Core Concepts

### Types of Constraints

| Constraint | Purpose | Example |
|------------|---------|---------|
| NOT NULL | Prevent null values | `email VARCHAR NOT NULL` |
| UNIQUE | No duplicate values | `email VARCHAR UNIQUE` |
| PRIMARY KEY | Unique + NOT NULL | `id SERIAL PRIMARY KEY` |
| FOREIGN KEY | Referential integrity | `user_id REFERENCES users(id)` |
| CHECK | Custom validation | `CHECK (age >= 0)` |
| EXCLUSION | Prevent overlaps | `EXCLUDE USING GIST (range WITH &&)` |

### NOT NULL Constraint

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL,      -- required
    name VARCHAR(255) NOT NULL,       -- required
    bio TEXT,                         -- optional (nullable)
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Adding NOT NULL to existing column
ALTER TABLE users ALTER COLUMN bio SET NOT NULL;

-- Removing NOT NULL
ALTER TABLE users ALTER COLUMN bio DROP NOT NULL;
```

### UNIQUE Constraint

```sql
-- Single column unique
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL
);

-- Composite unique (combination must be unique)
CREATE TABLE team_members (
    team_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    role VARCHAR(50),
    UNIQUE (team_id, user_id)
);

-- Named constraint (better error messages)
ALTER TABLE users
ADD CONSTRAINT users_email_unique UNIQUE (email);

-- Partial unique index (conditional uniqueness)
CREATE UNIQUE INDEX users_active_email_unique
ON users (email)
WHERE deleted_at IS NULL;  -- Only active users must have unique email
```

### PRIMARY KEY

```sql
-- Single column
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255)
);

-- Composite primary key
CREATE TABLE order_items (
    order_id INTEGER,
    line_number INTEGER,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    PRIMARY KEY (order_id, line_number)
);

-- UUID primary key
CREATE TABLE sessions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id INTEGER NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### FOREIGN KEY (Referential Integrity)

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL
);

CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    total DECIMAL(10,2) NOT NULL
);

-- Explicit syntax with options
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    total DECIMAL(10,2) NOT NULL,
    CONSTRAINT fk_orders_user
        FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE      -- Delete orders when user deleted
        ON UPDATE CASCADE      -- Update user_id when user.id changes
);
```

**Referential Actions:**

| Action | On DELETE | On UPDATE |
|--------|-----------|-----------|
| NO ACTION | Error if referenced | Error if referenced |
| RESTRICT | Error if referenced (immediate) | Error if referenced |
| CASCADE | Delete referencing rows | Update referencing rows |
| SET NULL | Set FK to NULL | Set FK to NULL |
| SET DEFAULT | Set FK to default | Set FK to default |

```sql
-- Common patterns
-- 1. Orders reference users - cascade delete (delete orders with user)
FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE

-- 2. Orders reference users - restrict delete (can't delete user with orders)
FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT

-- 3. Orders reference users - set null (orphan orders)
FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL

-- 4. Audit log - no action (preserve history)
FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE NO ACTION
```

### CHECK Constraint

```sql
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    price DECIMAL(10,2) NOT NULL CHECK (price > 0),
    quantity INTEGER DEFAULT 0 CHECK (quantity >= 0),
    status VARCHAR(20) CHECK (status IN ('draft', 'active', 'archived')),
    discount_pct INTEGER CHECK (discount_pct BETWEEN 0 AND 100)
);

-- Multi-column check
CREATE TABLE events (
    id SERIAL PRIMARY KEY,
    starts_at TIMESTAMPTZ NOT NULL,
    ends_at TIMESTAMPTZ NOT NULL,
    CHECK (ends_at > starts_at)
);

-- Named check constraint
ALTER TABLE products
ADD CONSTRAINT positive_price CHECK (price > 0);
```

### EXCLUSION Constraint

Exclusion constraints prevent overlapping values, commonly used with ranges.

```sql
-- Requires btree_gist extension for non-range types
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- Room booking: no overlapping times for same room
CREATE TABLE room_bookings (
    id SERIAL PRIMARY KEY,
    room_id INTEGER NOT NULL,
    during TSTZRANGE NOT NULL,
    booked_by VARCHAR(255) NOT NULL,
    EXCLUDE USING GIST (room_id WITH =, during WITH &&)
);

-- Valid bookings
INSERT INTO room_bookings (room_id, during, booked_by) VALUES
    (1, '[2024-01-15 10:00, 2024-01-15 11:00)', 'Alice'),
    (1, '[2024-01-15 11:00, 2024-01-15 12:00)', 'Bob'),
    (2, '[2024-01-15 10:00, 2024-01-15 11:00)', 'Charlie');

-- This fails: overlaps Alice's booking
INSERT INTO room_bookings (room_id, during, booked_by) VALUES
    (1, '[2024-01-15 10:30, 2024-01-15 11:30)', 'Dave');
-- ERROR: conflicting key value violates exclusion constraint
```

### Deferrable Constraints

```sql
-- Constraints can be deferred to end of transaction
CREATE TABLE nodes (
    id SERIAL PRIMARY KEY,
    parent_id INTEGER REFERENCES nodes(id) DEFERRABLE INITIALLY DEFERRED
);

-- This works because constraint is checked at COMMIT
BEGIN;
INSERT INTO nodes (id, parent_id) VALUES (1, 2);  -- parent doesn't exist yet
INSERT INTO nodes (id, parent_id) VALUES (2, 1);  -- circular reference
COMMIT;  -- constraint checked here

-- Immediate vs Deferred
SET CONSTRAINTS ALL IMMEDIATE;  -- check after each statement
SET CONSTRAINTS ALL DEFERRED;   -- check at commit
```

## Handling Constraint Violations

### UPSERT (INSERT ON CONFLICT)

```sql
-- Insert or update on conflict
INSERT INTO users (email, name)
VALUES ('alice@example.com', 'Alice')
ON CONFLICT (email)
DO UPDATE SET name = EXCLUDED.name;

-- Insert or do nothing
INSERT INTO users (email, name)
VALUES ('alice@example.com', 'Alice')
ON CONFLICT (email)
DO NOTHING;

-- With conditional update
INSERT INTO products (sku, price, updated_at)
VALUES ('SKU001', 19.99, NOW())
ON CONFLICT (sku)
DO UPDATE SET
    price = EXCLUDED.price,
    updated_at = EXCLUDED.updated_at
WHERE products.price != EXCLUDED.price;  -- only update if price changed
```

### Catching Violations in Application

```python
from psycopg2 import IntegrityError
from psycopg2.errors import UniqueViolation, ForeignKeyViolation, CheckViolation

try:
    cursor.execute("INSERT INTO users (email) VALUES (%s)", (email,))
except UniqueViolation:
    # Email already exists
    return {"error": "Email already registered"}
except ForeignKeyViolation:
    # Referenced record doesn't exist
    return {"error": "Invalid reference"}
except CheckViolation as e:
    # Check constraint failed
    return {"error": f"Validation failed: {e}"}
```

## Key Questions to Understand

- When should you use CHECK vs application-level validation?
- What's the performance impact of foreign keys?
- How do you handle constraint violations gracefully?

## Hands-On Exercises

### Exercise 1: E-Commerce Constraints

```sql
CREATE TABLE customers (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    phone VARCHAR(20),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    sku VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    price DECIMAL(10,2) NOT NULL CHECK (price >= 0),
    stock INTEGER NOT NULL DEFAULT 0 CHECK (stock >= 0)
);

CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE RESTRICT,
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'confirmed', 'shipped', 'delivered', 'cancelled')),
    total DECIMAL(10,2) NOT NULL CHECK (total >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE order_items (
    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price DECIMAL(10,2) NOT NULL CHECK (unit_price >= 0),
    PRIMARY KEY (order_id, product_id)
);
```

### Exercise 2: Soft Delete with Unique Constraint

```sql
-- Users with soft delete, but email must be unique among active users
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    deleted_at TIMESTAMPTZ
);

-- Only non-deleted users must have unique email
CREATE UNIQUE INDEX users_active_email_idx
ON users (email)
WHERE deleted_at IS NULL;

-- Test
INSERT INTO users (email) VALUES ('alice@example.com');
INSERT INTO users (email) VALUES ('alice@example.com');  -- ERROR: duplicate

-- Soft delete first user
UPDATE users SET deleted_at = NOW() WHERE email = 'alice@example.com' AND deleted_at IS NULL;

-- Now this works
INSERT INTO users (email) VALUES ('alice@example.com');  -- OK!
```

### Exercise 3: Version Control with Constraints

```sql
-- Ensure only one 'current' version per document
CREATE TABLE document_versions (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL,
    version_number INTEGER NOT NULL,
    content TEXT NOT NULL,
    is_current BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (document_id, version_number)
);

-- Only one current version per document
CREATE UNIQUE INDEX one_current_version
ON document_versions (document_id)
WHERE is_current = TRUE;
```

## Interview Deep Dive

### Question: "Database constraints vs application validation?"

**Answer:**
> "Use both. Database constraints are your safety net - they're always enforced regardless of which application or script touches the data. Application validation provides better user experience with immediate feedback and custom error messages. I put business rules like 'price > 0' in CHECK constraints, referential integrity in FKs, and more complex validations in application code. The database prevents bad data even if there's a bug in the application."

### Question: "What's the performance impact of foreign keys?"

**Answer:**
> "FKs add overhead: the referenced table is checked on INSERT/UPDATE (needs index lookup), and the referencing table is checked on UPDATE/DELETE of parent. With proper indexes this is usually negligible - O(log n) lookups. The bigger cost is ON DELETE CASCADE with many child rows. I always index FK columns and consider using ON DELETE RESTRICT for critical relationships where I want explicit handling. The integrity guarantees usually outweigh the small performance cost."

## Key Takeaways

1. **NOT NULL** - enforce required fields at DB level
2. **UNIQUE** - can be partial with WHERE clause
3. **FOREIGN KEY** - choose referential action carefully
4. **CHECK** - simple validation rules in the DB
5. **EXCLUSION** - prevent overlapping ranges/values
6. **ON CONFLICT** - handle violations gracefully with upsert

## Self-Assessment Questions

1. When would you use ON DELETE CASCADE vs RESTRICT?
2. How do you create a partial unique constraint?
3. What's the difference between DEFERRABLE INITIALLY DEFERRED and IMMEDIATE?
4. How do exclusion constraints work with GiST indexes?
5. When would you use a check constraint vs application validation?

## Next Chapter

[Chapter 5: How B-Tree Indexes Work →](./05_btree_indexes.md)

# Chapter 1: Relational Model Refresher

## Overview

The relational model is the foundation of PostgreSQL and all relational databases. Understanding relational theory, normalization, and schema design is essential before diving into PostgreSQL-specific features.

## Core Concepts

### What is the Relational Model?

The relational model organizes data into relations (tables) with:

- **Tuples** (rows) - Individual records
- **Attributes** (columns) - Properties of records
- **Keys** - Unique identifiers for tuples
- **Constraints** - Rules enforcing data integrity

```
Relation: users
┌────┬───────────┬──────────────────────┬────────────┐
│ id │ name      │ email                │ created_at │
├────┼───────────┼──────────────────────┼────────────┤
│ 1  │ Alice     │ alice@example.com    │ 2024-01-01 │
│ 2  │ Bob       │ bob@example.com      │ 2024-01-02 │
└────┴───────────┴──────────────────────┴────────────┘
```

### Keys

```sql
CREATE TABLE users {
    id SERIAL PRIMARY KEY,
    email VARCHAR(100) UNIQUE NOT NULL
}

CREATE TABLE orders {
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id)
}
```

```sql
-- Primary Key: uniquely identifies each row
CREATE TABLE users (
    id SERIAL PRIMARY KEY,  -- surrogate key
    email VARCHAR(255) UNIQUE NOT NULL  -- natural key candidate
);

-- Foreign Key: references another table
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id)
);

-- Composite Key: multiple columns
CREATE TABLE order_items (
    order_id INTEGER,
    product_id INTEGER,
    quantity INTEGER,
    PRIMARY KEY (order_id, product_id)
);
```

### Normalization Forms

| Form | Rule                                 | Eliminates                            |
| ---- | ------------------------------------ | ------------------------------------- |
| 1NF  | Atomic values, no repeating groups   | Multi-valued attributes               |
| 2NF  | 1NF + no partial dependencies        | Partial dependencies on composite key |
| 3NF  | 2NF + no transitive dependencies     | Dependencies on non-key attributes    |
| BCNF | Every determinant is a candidate key | Remaining anomalies                   |

**Example: Unnormalized to 3NF**

```sql
-- Unnormalized (violates 1NF)
CREATE TABLE orders_bad (
    order_id INTEGER,
    customer_name VARCHAR(255),
    customer_email VARCHAR(255),
    items TEXT  -- "item1,item2,item3" - multi-valued!
);

-- 1NF: Atomic values
CREATE TABLE orders_1nf (
    order_id INTEGER,
    customer_name VARCHAR(255),
    customer_email VARCHAR(255),
    item_name VARCHAR(255),
    item_price DECIMAL(10,2)
);

-- 2NF: Remove partial dependencies
CREATE TABLE customers (
    customer_id SERIAL PRIMARY KEY,
    name VARCHAR(255),
    email VARCHAR(255)
);

CREATE TABLE orders_2nf (
    order_id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(customer_id),
    item_name VARCHAR(255),
    item_price DECIMAL(10,2)
);

-- 3NF: Remove transitive dependencies
CREATE TABLE products (
    product_id SERIAL PRIMARY KEY,
    name VARCHAR(255),
    price DECIMAL(10,2)
);

CREATE TABLE orders_3nf (
    order_id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(customer_id)
);

CREATE TABLE order_items (
    order_id INTEGER REFERENCES orders_3nf(order_id),
    product_id INTEGER REFERENCES products(product_id),
    quantity INTEGER,
    PRIMARY KEY (order_id, product_id)
);
```

### When to Denormalize

Denormalization trades write complexity for read performance.

**Denormalize When:**

- Read-heavy workloads (reports, dashboards)
- Frequent expensive JOINs
- Data rarely changes
- Query patterns are well-known

**Stay Normalized When:**

- Write-heavy workloads
- Data changes frequently
- Query patterns are unpredictable
- Data integrity is critical

```sql
-- Normalized (requires JOIN)
SELECT o.id, u.name, u.email, o.total_amount
FROM orders o
JOIN users u ON u.id = o.user_id
WHERE o.id = 123;

-- Denormalized (no JOIN, but duplicated data)
CREATE TABLE order_summary (
    order_id INTEGER PRIMARY KEY,
    user_id INTEGER,
    user_name VARCHAR(255),  -- duplicated
    user_email VARCHAR(255), -- duplicated
    total_amount DECIMAL(10,2),
    item_count INTEGER
);

SELECT * FROM order_summary WHERE order_id = 123;
```

## Key Questions to Understand

- What problems does normalization solve?
- When should you denormalize?
- What's the difference between 3NF and BCNF?

## Hands-On Exercises

### Exercise 1: Design an E-Commerce Schema

```sql
-- Design tables for an e-commerce system with:
-- - Users (with addresses)
-- - Products (with categories)
-- - Orders (with multiple items)
-- - Reviews

-- Users
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Addresses (user can have multiple)
CREATE TABLE addresses (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    type VARCHAR(20) CHECK (type IN ('shipping', 'billing')),
    street VARCHAR(255),
    city VARCHAR(100),
    country VARCHAR(100),
    postal_code VARCHAR(20)
);

-- Categories
CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    parent_id INTEGER REFERENCES categories(id)
);

-- Products
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    sku VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    price DECIMAL(10,2) NOT NULL CHECK (price > 0),
    category_id INTEGER REFERENCES categories(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Orders
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    shipping_address_id INTEGER REFERENCES addresses(id),
    status VARCHAR(50) DEFAULT 'pending',
    total_amount DECIMAL(10,2),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Order Items
CREATE TABLE order_items (
    id SERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES orders(id),
    product_id INTEGER REFERENCES products(id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price DECIMAL(10,2) NOT NULL
);

-- Reviews
CREATE TABLE reviews (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    product_id INTEGER REFERENCES products(id),
    rating INTEGER CHECK (rating BETWEEN 1 AND 5),
    comment TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, product_id)  -- one review per user per product
);
```

### Exercise 2: Identify Normalization Issues

```sql
-- What's wrong with this table?
CREATE TABLE bad_orders (
    order_id INTEGER,
    customer_name VARCHAR(255),
    customer_email VARCHAR(255),
    customer_phone VARCHAR(50),
    product_name VARCHAR(255),
    product_price DECIMAL(10,2),
    product_category VARCHAR(100),
    quantity INTEGER,
    order_date DATE
);

-- Issues:
-- 1. Customer data duplicated for each order
-- 2. Product data duplicated for each order
-- 3. No primary key
-- 4. Same customer placing multiple orders = data duplication
-- 5. Updates require changing multiple rows
```

## Interview Deep Dive

### Question: "How do you decide between normalization and denormalization?"

**Answer:**

> "I start normalized (3NF) and denormalize strategically based on measured performance needs. Normalization reduces data duplication and update anomalies but requires JOINs. Denormalization speeds reads but complicates writes and risks inconsistency. I'd denormalize when: read patterns are predictable and frequent, data changes infrequently, and the performance gain is measurable. Common denormalization patterns include materialized views for reporting and cached aggregates."

### Question: "What's the difference between a surrogate key and a natural key?"

**Answer:**

> "A natural key uses existing business data (like email or SSN) while a surrogate key is system-generated (like auto-increment ID or UUID). I prefer surrogate keys because: natural keys can change (email changes), they may be composite and complex, and they couple schema to business rules. Natural keys are good when the value truly never changes and is simple. I often keep natural keys as unique constraints alongside surrogate primary keys."

## Key Takeaways

1. **Normalization** eliminates redundancy and update anomalies
2. **Denormalization** trades integrity for read performance
3. **Primary keys** uniquely identify rows (prefer surrogate)
4. **Foreign keys** enforce referential integrity
5. **Design for your access patterns** - start normalized, optimize as needed

## Self-Assessment Questions

1. What normalization form does your typical schema achieve?
2. Can you identify a transitive dependency?
3. When would you use a composite primary key?
4. How do you handle a many-to-many relationship?
5. What are the risks of denormalization?

## Next Chapter

[Chapter 2: SQL Essentials (Beyond Basics) →](./02_sql_essentials.md)

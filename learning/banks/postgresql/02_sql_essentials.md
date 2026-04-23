# Chapter 2: SQL Essentials (Beyond Basics)

## Overview

Moving beyond basic SELECT, INSERT, UPDATE, DELETE - this chapter covers advanced SQL features that separate proficient PostgreSQL users from beginners. Window functions, CTEs, and complex subqueries are essential for real-world data manipulation.

## Core Concepts

### Window Functions

Window functions perform calculations across a set of rows related to the current row, without collapsing rows like GROUP BY.

```sql
-- Basic syntax
SELECT
    column,
    window_function() OVER (
        PARTITION BY partition_column
        ORDER BY order_column
        ROWS BETWEEN frame_start AND frame_end
    )
FROM table;
```

**Ranking Functions**

```sql
-- Sample data
CREATE TABLE sales (
    id SERIAL PRIMARY KEY,
    salesperson VARCHAR(50),
    region VARCHAR(50),
    amount DECIMAL(10,2),
    sale_date DATE
);

INSERT INTO sales (salesperson, region, amount, sale_date) VALUES
    ('Alice', 'North', 1000, '2024-01-01'),
    ('Alice', 'North', 1500, '2024-01-02'),
    ('Bob', 'North', 1200, '2024-01-01'),
    ('Bob', 'South', 800, '2024-01-02'),
    ('Charlie', 'South', 1500, '2024-01-01'),
    ('Charlie', 'South', 1500, '2024-01-02');

-- Rank salespeople by total sales
SELECT
    salesperson,
    SUM(amount) as total_sales,
    RANK() OVER (ORDER BY SUM(amount) DESC) as rank,
    DENSE_RANK() OVER (ORDER BY SUM(amount) DESC) as dense_rank,
    ROW_NUMBER() OVER (ORDER BY SUM(amount) DESC) as row_num
FROM sales
GROUP BY salesperson;

-- Result:
-- salesperson | total_sales | rank | dense_rank | row_num
-- Charlie     | 3000        | 1    | 1          | 1
-- Alice       | 2500        | 2    | 2          | 2
-- Bob         | 2000        | 3    | 3          | 3
```

**Difference between RANK, DENSE_RANK, ROW_NUMBER:**

| Function   | Ties               | Gaps            |
| ---------- | ------------------ | --------------- |
| ROW_NUMBER | Each row unique    | No gaps         |
| RANK       | Same rank for ties | Gaps after ties |
| DENSE_RANK | Same rank for ties | No gaps         |

**Running Totals and Moving Averages**

```sql
-- Running total
SELECT
    sale_date,
    amount,
    SUM(amount) OVER (ORDER BY sale_date) as running_total
FROM sales;

-- Running total per salesperson
SELECT
    salesperson,
    sale_date,
    amount,
    SUM(amount) OVER (
        PARTITION BY salesperson
        ORDER BY sale_date
    ) as running_total
FROM sales;

-- 7-day moving average
SELECT
    sale_date,
    amount,
    AVG(amount) OVER (
        ORDER BY sale_date
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) as moving_avg_7d
FROM sales;
```

**LAG and LEAD**

```sql
-- Compare to previous row
SELECT
    sale_date,
    amount,
    LAG(amount) OVER (ORDER BY sale_date) as prev_amount,
    amount - LAG(amount) OVER (ORDER BY sale_date) as change
FROM sales;

-- Compare to next row
SELECT
    sale_date,
    amount,
    LEAD(amount) OVER (ORDER BY sale_date) as next_amount
FROM sales;

-- Look back 2 rows
SELECT
    sale_date,
    amount,
    LAG(amount, 2) OVER (ORDER BY sale_date) as two_days_ago
FROM sales;
```

**FIRST_VALUE and LAST_VALUE**

```sql
-- Compare each sale to the first and last of the day
SELECT
    sale_date,
    salesperson,
    amount,
    FIRST_VALUE(amount) OVER (
        PARTITION BY sale_date
        ORDER BY id
    ) as first_sale,
    LAST_VALUE(amount) OVER (
        PARTITION BY sale_date
        ORDER BY id
        ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
    ) as last_sale
FROM sales;
```

### CTEs (Common Table Expressions)

CTEs make complex queries readable and maintainable.

```sql
-- Basic CTE
WITH monthly_sales AS (
    SELECT
        DATE_TRUNC('month', sale_date) as month,
        SUM(amount) as total
    FROM sales
    GROUP BY 1
)
SELECT
    month,
    total,
    LAG(total) OVER (ORDER BY month) as prev_month,
    total - LAG(total) OVER (ORDER BY month) as growth
FROM monthly_sales;

-- Multiple CTEs
WITH
top_salespeople AS (
    SELECT salesperson, SUM(amount) as total
    FROM sales
    GROUP BY salesperson
    ORDER BY total DESC
    LIMIT 3
),
top_regions AS (
    SELECT region, SUM(amount) as total
    FROM sales
    GROUP BY region
    ORDER BY total DESC
    LIMIT 2
)
SELECT
    s.salesperson,
    s.region,
    s.amount
FROM sales s
WHERE s.salesperson IN (SELECT salesperson FROM top_salespeople)
  AND s.region IN (SELECT region FROM top_regions);
```

**Recursive CTEs**

```sql
-- Hierarchical data (org chart)
CREATE TABLE employees (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    manager_id INTEGER REFERENCES employees(id)
);

INSERT INTO employees (name, manager_id) VALUES
    ('CEO', NULL),
    ('VP Sales', 1),
    ('VP Engineering', 1),
    ('Sales Manager', 2),
    ('Engineer 1', 3),
    ('Engineer 2', 3),
    ('Sales Rep 1', 4);

-- Get all subordinates with level
WITH RECURSIVE org_hierarchy AS (
    -- Base case: start with CEO
    SELECT id, name, manager_id, 0 as level
    FROM employees
    WHERE manager_id IS NULL

    UNION ALL

    -- Recursive case: join employees to their managers
    SELECT e.id, e.name, e.manager_id, h.level + 1
    FROM employees e
    JOIN org_hierarchy h ON e.manager_id = h.id
)
SELECT
    REPEAT('  ', level) || name as org_chart,
    level
FROM org_hierarchy
ORDER BY level, name;

-- Result:
-- org_chart        | level
-- CEO              | 0
--   VP Engineering | 1
--   VP Sales       | 1
--     Engineer 1   | 2
--     Engineer 2   | 2
--     Sales Manager| 2
--       Sales Rep 1| 3
```

**Number Series with Recursive CTE**

```sql
-- Generate numbers 1-10
WITH RECURSIVE numbers AS (
    SELECT 1 as n
    UNION ALL
    SELECT n + 1 FROM numbers WHERE n < 10
)
SELECT * FROM numbers;

-- Generate dates
WITH RECURSIVE dates AS (
    SELECT DATE '2024-01-01' as d
    UNION ALL
    SELECT d + 1 FROM dates WHERE d < '2024-01-31'
)
SELECT * FROM dates;
```

### Subqueries

**Scalar Subquery**

```sql
-- Returns single value
SELECT
    salesperson,
    amount,
    (SELECT AVG(amount) FROM sales) as avg_amount,
    amount - (SELECT AVG(amount) FROM sales) as vs_avg
FROM sales;
```

**Table Subquery (Derived Table)**

```sql
-- Subquery in FROM clause
SELECT
    s.salesperson,
    s.amount,
    stats.avg_amount
FROM sales s
CROSS JOIN (
    SELECT AVG(amount) as avg_amount FROM sales
) stats;
```

**Correlated Subquery**

```sql
-- References outer query (can be slow!)
SELECT
    s1.salesperson,
    s1.sale_date,
    s1.amount,
    (
        SELECT COUNT(*)
        FROM sales s2
        WHERE s2.salesperson = s1.salesperson
          AND s2.sale_date <= s1.sale_date
    ) as running_count
FROM sales s1;

-- Better: Use window function instead
SELECT
    salesperson,
    sale_date,
    amount,
    COUNT(*) OVER (
        PARTITION BY salesperson
        ORDER BY sale_date
    ) as running_count
FROM sales;
```

**EXISTS and NOT EXISTS**

```sql
-- Find salespeople with sales > 1000
SELECT DISTINCT salesperson
FROM sales s1
WHERE EXISTS (
    SELECT 1 FROM sales s2
    WHERE s2.salesperson = s1.salesperson
      AND s2.amount > 1000
);

-- Find salespeople without any high-value sales
SELECT DISTINCT salesperson
FROM sales s1
WHERE NOT EXISTS (
    SELECT 1 FROM sales s2
    WHERE s2.salesperson = s1.salesperson
      AND s2.amount > 1000
);
```

## Key Questions to Understand

- When do you use a CTE vs a subquery?
- What's the difference between RANK, DENSE_RANK, and ROW_NUMBER?
- When does a correlated subquery hurt performance?

## Hands-On Exercises

### Exercise 1: Sales Analysis

```sql
-- Find top 2 sales per region
SELECT * FROM (
    SELECT
        region,
        salesperson,
        amount,
        ROW_NUMBER() OVER (
            PARTITION BY region
            ORDER BY amount DESC
        ) as rank
    FROM sales
) ranked
WHERE rank <= 2;

-- Percentage of regional total
SELECT
    salesperson,
    region,
    amount,
    SUM(amount) OVER (PARTITION BY region) as region_total,
    ROUND(amount * 100.0 / SUM(amount) OVER (PARTITION BY region), 2) as pct
FROM sales;
```

### Exercise 2: Gap Analysis

```sql
-- Find gaps in order IDs (missing numbers)
WITH all_ids AS (
    SELECT generate_series(
        (SELECT MIN(id) FROM orders),
        (SELECT MAX(id) FROM orders)
    ) as id
)
SELECT a.id as missing_id
FROM all_ids a
LEFT JOIN orders o ON o.id = a.id
WHERE o.id IS NULL;
```

### Exercise 3: Session Analysis

```sql
-- Group events into sessions (gap > 30 minutes = new session)
WITH events_with_gap AS (
    SELECT
        user_id,
        event_time,
        LAG(event_time) OVER (PARTITION BY user_id ORDER BY event_time) as prev_time,
        CASE
            WHEN event_time - LAG(event_time) OVER (PARTITION BY user_id ORDER BY event_time) > INTERVAL '30 minutes'
            THEN 1
            ELSE 0
        END as new_session
    FROM user_events
),
sessions AS (
    SELECT
        user_id,
        event_time,
        SUM(new_session) OVER (
            PARTITION BY user_id
            ORDER BY event_time
        ) + 1 as session_id
    FROM events_with_gap
)
SELECT
    user_id,
    session_id,
    MIN(event_time) as session_start,
    MAX(event_time) as session_end,
    COUNT(*) as event_count
FROM sessions
GROUP BY user_id, session_id;
```

## Interview Deep Dive

### Question: "When would you use a window function vs GROUP BY?"

**Answer:**

> "GROUP BY collapses rows and returns one row per group - you lose individual row data. Window functions perform calculations across rows but keep each row intact. Use GROUP BY for aggregated results, window functions when you need both the detail and the aggregate - like showing each employee's salary alongside the department average, or calculating running totals while keeping each transaction visible."

### Question: "CTEs vs Subqueries - which to use?"

**Answer:**

> "CTEs are better for readability and when you reference the same result multiple times. Subqueries can sometimes be inlined by the optimizer for better performance. In PostgreSQL, CTEs used to be optimization fences (not inlined), but since v12, non-recursive CTEs can be inlined. I default to CTEs for maintainability and only switch to subqueries if I identify a performance issue."

## Key Takeaways

1. **Window functions** - aggregate without collapsing rows
2. **PARTITION BY** - like GROUP BY for window functions
3. **CTEs** - improve readability, can be recursive
4. **Correlated subqueries** - often slow, prefer JOINs or window functions
5. **EXISTS** - efficient for checking existence without returning data

## Self-Assessment Questions

1. How do you calculate a running total partitioned by customer?
2. What's the difference between ROWS and RANGE in frame specification?
3. When would you use a recursive CTE?
4. How do you find the second-highest value per group?
5. Why might a correlated subquery be slow?

## Next Chapter

[Chapter 3: Data Types and When to Use Them →](./03_data_types.md)

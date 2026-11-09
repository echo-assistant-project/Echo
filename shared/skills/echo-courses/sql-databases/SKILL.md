---
name: sql-databases
description: Design databases and write SQL queries — SELECT, filtering, joins, grouping, indexes and safe changes. Use for "write a SQL query", "join these tables", "why is my query slow", "design a database for my shop", "what's a primary key".
audience: developers
field: Technology
courses: Stanford Databases: Relational Databases and SQL (Stanford Online) | https://online.stanford.edu/ ; Khan Academy Intro to SQL | https://www.khanacademy.org/computing/computer-programming/sql ; SQLBolt interactive lessons | https://sqlbolt.com/ ; PostgreSQL Tutorial (official docs) | https://www.postgresql.org/docs/current/tutorial.html
source: Echo (written for Echo from these courses' syllabi)
license: same as Echo
---

# SQL and databases

## 1. Thinking in tables
- A **table** is one kind of thing (customers, orders); a **row** is one item; a **column** is one fact.
- **Primary key**: a unique id per row. **Foreign key**: a column pointing to another table's key (orders.customer_id → customers.id).
- Normalise: don't repeat the same fact in many rows; split into related tables. Denormalise later only for proven speed needs.

## 2. Reading data
```sql
SELECT name, city FROM customers WHERE city = 'Vijayawada' ORDER BY name LIMIT 20;
```
- Filters: `=`, `<>`, `BETWEEN`, `IN (...)`, `LIKE 'Ra%'`, `IS NULL` (never `= NULL`).
- Aggregates: `COUNT, SUM, AVG, MIN, MAX` with `GROUP BY`; filter groups with `HAVING`.

## 3. Joins
- `INNER JOIN`: only matching rows. `LEFT JOIN`: every row from the left, matches or NULLs (find customers with no orders: `WHERE o.id IS NULL`).
- Always join on keys; check row counts before and after a join to catch duplicates.

## 4. Changing data safely
- `INSERT`, `UPDATE … WHERE`, `DELETE … WHERE`. Run the same `WHERE` as a `SELECT` first to see what will change.
- Wrap multi-step changes in a transaction (`BEGIN … COMMIT`, `ROLLBACK` on error). Back up before big changes.
- In application code always use **parameterised queries** (placeholders), never string concatenation — that's how SQL injection happens.

## 5. Speed
- Add an index on columns used in `WHERE`, `JOIN` and `ORDER BY` of frequent queries; don't index everything.
- Read the plan: `EXPLAIN` (or `EXPLAIN ANALYZE` in PostgreSQL). Look for full scans on big tables.
- Select only needed columns; avoid functions on indexed columns in `WHERE`.

## 6. Designing a small database (example: a shop)
customers(id, name, phone), products(id, name, price), orders(id, customer_id, created_at), order_items(order_id, product_id, qty, price_at_sale). Store money as integer paise or `NUMERIC`, never float. SQLite is enough for one app on one machine; PostgreSQL for multi-user apps.

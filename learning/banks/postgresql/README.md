# PostgreSQL Learning Curriculum

A comprehensive, hands-on learning strategy for PostgreSQL mastery. Focus on understanding, not memorization.

## Quick Start

```bash
# Run PostgreSQL locally
docker run -d --name postgres -p 5432:5432 \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=learn \
  postgres:15

# Connect
docker exec -it postgres psql -U postgres -d learn
```

## Curriculum Structure

### Module 1: Foundations (Chapters 1-4)
- [Chapter 1: Relational Model Refresher](./01_relational_model.md)
- [Chapter 2: SQL Essentials (Beyond Basics)](./02_sql_essentials.md)
- [Chapter 3: Data Types and When to Use Them](./03_data_types.md)
- [Chapter 4: Constraints and Referential Integrity](./04_constraints.md)

### Module 2: Indexing Deep Dive (Chapters 5-9)
- [Chapter 5: How B-Tree Indexes Work](./05_btree_indexes.md)
- [Chapter 6: Index Types](./06_index_types.md)
- [Chapter 7: Composite and Partial Indexes](./07_composite_partial_indexes.md)
- [Chapter 8: Index-Only Scans](./08_index_only_scans.md)
- [Chapter 9: When Indexes Hurt](./09_when_indexes_hurt.md)

### Module 3: Query Execution (Chapters 10-13)
- [Chapter 10: EXPLAIN and EXPLAIN ANALYZE](./10_explain_analyze.md)
- [Chapter 11: Query Planner Decisions](./11_query_planner.md)
- [Chapter 12: Join Algorithms](./12_join_algorithms.md)
- [Chapter 13: Common Query Anti-Patterns](./13_query_antipatterns.md)

### Module 4: Transactions and Concurrency (Chapters 14-18)
- [Chapter 14: ACID Properties](./14_acid.md)
- [Chapter 15: Isolation Levels](./15_isolation_levels.md)
- [Chapter 16: MVCC (Multi-Version Concurrency Control)](./16_mvcc.md)
- [Chapter 17: Locking](./17_locking.md)
- [Chapter 18: Vacuum and Bloat](./18_vacuum_bloat.md)

### Module 5: Scaling PostgreSQL (Chapters 19-22)
- [Chapter 19: Connection Pooling (PgBouncer)](./19_connection_pooling.md)
- [Chapter 20: Replication](./20_replication.md)
- [Chapter 21: Partitioning](./21_partitioning.md)
- [Chapter 22: Read Replicas](./22_read_replicas.md)

### Module 6: Production Operations (Chapters 23-26)
- [Chapter 23: Configuration Tuning](./23_configuration_tuning.md)
- [Chapter 24: Monitoring and pg_stat Views](./24_monitoring.md)
- [Chapter 25: Backup and Recovery](./25_backup_recovery.md)
- [Chapter 26: Common Production Issues](./26_production_issues.md)

## What "Understanding" Looks Like

| Question | Not This | But This |
|----------|----------|----------|
| "How do indexes work?" | "They make queries fast" | "B-tree structure enables O(log n) lookups. The index stores sorted keys with pointers to heap tuples. For range queries, it does a single seek then sequential read. Write overhead is ~30% per index." |
| "When would an index not help?" | "When the table is small" | "When returning >5-10% of rows (full scan cheaper), when there's a function on the column preventing use, when statistics are outdated and planner estimates wrong selectivity." |
| "Explain MVCC" | "It's for concurrency" | "Each row version has xmin/xmax transaction IDs. Readers see rows based on their snapshot - no read locks needed. Trade-off is dead tuple accumulation requiring vacuum." |
| "Why connection pooling?" | "More connections" | "PostgreSQL forks per connection (~10MB each). Pooling amortizes connection cost, lets 1000 app connections share 50 DB connections in transaction mode." |

## Learning Timeline

| Time Available | Focus |
|----------------|-------|
| 1 week | Modules 1-2 (foundations + indexing) |
| 2 weeks | Modules 1-4 (add transactions) |
| 3 weeks | Full curriculum including production |

## Daily Practice Routine

| Time | Activity |
|------|----------|
| 20 min | Read one chapter section |
| 30 min | Hands-on with EXPLAIN ANALYZE |
| 10 min | Write down what you learned |

**Total: ~1 hour/day**

## Key Tools

- **psql** - PostgreSQL command-line client
- **EXPLAIN ANALYZE** - Query plan analysis
- **pg_stat_statements** - Query performance tracking
- **pgBadger** - Log analysis
- **explain.depesz.com** - Visual EXPLAIN plans

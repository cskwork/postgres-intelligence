# PostgreSQL Best Practices

Use this reference only when `postgres-intelligence` needs deeper query, schema, or performance guidance.

## Connections

- Keep agent database sessions short-lived.
- Long-running applications should use pooling such as PgBouncer, pgPool, or an application pool.
- Credentials belong in `.env` or a secret store. Do not print passwords or full DSNs.
- Use `connect_timeout`, `statement_timeout`, and, when needed, `lock_timeout`.

## Read Queries

- Prefer explicit columns over `SELECT *`.
- Add `WHERE`, `ORDER BY`, and `LIMIT` for exploratory reads on large tables.
- Confirm JOIN keys from foreign keys or business rules before joining.
- Use `IS NULL` and `IS NOT NULL`; do not compare with `= NULL`.

## Performance

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT ...
```

- `Seq Scan` is not always wrong, but on large tables with selective predicates it usually deserves review.
- Large gaps between estimated and actual rows suggest stale statistics, skewed data, or a bad predicate.
- High buffer reads suggest I/O pressure. High buffer hits with slow runtime suggests CPU, join, sort, or function cost.
- If `pg_stat_statements` is installed, inspect mean execution time, calls, rows, and total time.

## Indexes

- B-tree: default choice for equality, range, joins, and ordering.
- GIN: JSONB containment, arrays, full-text search, trigram patterns.
- GiST/SP-GiST: geometric, range, and specialized extension workloads.
- BRIN: large append-only tables where data is naturally ordered, often by time.
- For large production tables, prefer `CREATE INDEX CONCURRENTLY`; it cannot run inside a transaction block.
- Verify planner usage with `EXPLAIN` before and after adding an index.

## Maintenance

- Run `ANALYZE` after large data changes.
- Do not disable autovacuum globally.
- For high-churn tables, tune table-level autovacuum settings instead.
- Monitor dead tuples and analyze/vacuum timestamps in `pg_stat_user_tables`.

## Sources Used

- Supabase `supabase-postgres-best-practices`, generalized for plain PostgreSQL.
- Jeff Allan `postgres-pro`, especially EXPLAIN, index, JSONB, VACUUM, and monitoring guidance.
- PostgreSQL official docs: `EXPLAIN`, `ANALYZE`, `CREATE INDEX`, `pg_stat_statements`, and `information_schema`.
- Psycopg 3 docs: `psycopg[binary]`, row factories, cursor usage, and connection patterns.


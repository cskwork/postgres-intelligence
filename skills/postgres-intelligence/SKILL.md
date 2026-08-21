---
name: postgres-intelligence
description: 'PostgreSQL for LLM agents: inspect schemas, run safe SQL, translate natural language to queries. Use when connecting to a PostgreSQL database, exploring an unfamiliar schema, debugging a SQL error, or investigating query performance.'
---


# postgres-intelligence

Credential-safe PostgreSQL access for LLM coding agents. The scripts load credentials from `.env` at runtime and print only safe summaries, schema metadata, query results, and errors. The agent writes SQL, calls the scripts, and reads that output; it never opens or prints `.env` itself.

## Install

`.env`, `scripts/`, and `schema_metadata.json` all live in the skill directory. Run every command in this file from there.

```bash
cd postgres-intelligence           # repo root
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
cd skills/postgres-intelligence    # the skill directory
cp ../../.env.example .env
python scripts/config.py
python scripts/db_connector.py
python scripts/schema_extractor.py
```

## Configure

Fill `.env` from the keys in `../../.env.example`, the public template: connections `DB1_` through `DB10_`, or `DB1_DSN`, which takes precedence over the host/port fields. `DB*_NAME` is the connection key `--db` expects. Keep real `.env`, `.venv`, and `schema_metadata.json` out of git.

## Commands

```bash
# Validate loaded config; prints host, user, and database, never passwords or DSNs
python scripts/config.py

# Test all configured connections
python scripts/db_connector.py

# Extract schema metadata for every connection into schema_metadata.json
python scripts/schema_extractor.py

# Run a read-only query against the default connection
python scripts/query_executor.py "SELECT current_database(), current_schema();"

# Select a named connection
python scripts/query_executor.py --db analytics "SELECT count(*) FROM public.events;"

# Agent-friendly JSON output
python scripts/query_executor.py --json-only "SELECT now();"

# Raise the 30000 ms statement_timeout for a long analytical query
python scripts/query_executor.py --statement-timeout-ms 120000 "SELECT count(*) FROM public.events;"

# Writes require explicit user approval
python scripts/query_executor.py --allow-write "UPDATE table_name SET flag = true WHERE id = 1;"

# DDL requires explicit user approval
python scripts/query_executor.py --allow-ddl "CREATE INDEX CONCURRENTLY idx_name ON table_name (col);"
```

## Agent Workflow

1. Identify the target connection, schema, table, time range, and result limit.
2. Run `python scripts/config.py` to confirm the connection is configured; it validates `.env` without printing secrets.
3. Read `schema_metadata.json` in the skill directory before generating SQL; if it is absent or stale, run `python scripts/schema_extractor.py` to rewrite it.
4. If the target table is still missing from that metadata, query `information_schema` or `pg_catalog` for it first.
5. Prefer explicit columns over `SELECT *`; add `LIMIT` for exploratory reads.
6. On errors, use `sqlstate` and suggestions to refine the query, with a maximum of three attempts.
7. Report the executed SQL, key rows, row count, and reasoning. Do not report credentials.

## Safety Model

- Read-only by default: `SELECT`, `WITH`, `SHOW`, and `EXPLAIN` run with no flag.
- Writes require `--allow-write`.
- DDL and maintenance commands require `--allow-ddl`.
- `UPDATE` and `DELETE` without `WHERE` are blocked.
- Multiple SQL statements in one call are blocked.
- Every query runs under a `statement_timeout` of 30000 ms unless `--statement-timeout-ms` raises it.
- Passwords and full DSNs are never printed.

## PostgreSQL Guidance

- Use `EXPLAIN (ANALYZE, BUFFERS)` for performance work.
- Verify index usage before and after adding indexes.
- Use `CREATE INDEX CONCURRENTLY` for large production tables when appropriate.
- Run `ANALYZE` after bulk data changes.
- Use B-tree for common equality/range access, GIN for JSONB containment and full-text patterns, BRIN for large append-only time-series tables.
- Use connection pooling such as PgBouncer for long-running applications; agent scripts are short-lived.

Read `../../references/postgres_best_practices.md` before recommending an index, a partitioning or schema change, or a maintenance job.


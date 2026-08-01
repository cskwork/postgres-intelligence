---
name: postgres-intelligence
description: 'PostgreSQL for LLM agents: inspect schemas, run safe SQL, translate natural language to queries. Use when connecting to a database.'
---


# postgres-intelligence

PostgreSQL intelligence for LLM coding agents. It gives Claude Code, Codex, and other local agents a credential-safe way to discover PostgreSQL schemas, run read-first SQL, inspect query errors, and reason about performance.

The core rule is simple: the agent should not open or print `.env` directly. Scripts load credentials at runtime, and the agent only sees safe summaries, query results, and metadata.

## What It Does

- Loads one or more PostgreSQL connections from `.env` using `DB1_...DB10_...`.
- Tests connectivity without printing passwords or full DSNs.
- Extracts schema metadata from `information_schema` and `pg_catalog`.
- Executes read-only SQL by default: `SELECT`, `WITH`, `SHOW`, and `EXPLAIN`.
- Blocks writes and DDL unless explicit flags are passed after user approval.
- Returns structured JSON that any LLM agent can parse.
- Provides PostgreSQL-specific guidance for indexes, JSONB, `EXPLAIN`, and maintenance.

## Install

```bash
cd postgres-intelligence
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python scripts/config.py
python scripts/db_connector.py
python scripts/schema_extractor.py
```

Use `.env.example` as the public template. Keep real `.env`, `.venv`, and `schema_metadata.json` out of git.

## Configure

```bash
DB1_HOST=localhost
DB1_PORT=5432
DB1_USER=your_username
DB1_PASSWORD=your_password
DB1_DATABASE=your_database
DB1_NAME=primary
DB1_SSLMODE=prefer
DB1_CONNECT_TIMEOUT=10
DB1_APPLICATION_NAME=postgres-intelligence
```

Use `DB*_NAME` as the connection key for `--db`.

## Commands

```bash
# Validate loaded config without printing secrets
python scripts/config.py

# Test all configured connections
python scripts/db_connector.py

# Extract schema metadata
python scripts/schema_extractor.py

# Run a read-only query against the default connection
python scripts/query_executor.py "SELECT current_database(), current_schema();"

# Select a named connection
python scripts/query_executor.py --db analytics "SELECT count(*) FROM public.events;"

# Agent-friendly JSON output
python scripts/query_executor.py --json-only "SELECT now();"

# Writes require explicit user approval
python scripts/query_executor.py --allow-write "UPDATE table_name SET flag = true WHERE id = 1;"

# DDL requires explicit user approval
python scripts/query_executor.py --allow-ddl "CREATE INDEX CONCURRENTLY idx_name ON table_name (col);"
```

## Agent Workflow

1. Identify the target connection, schema, table, time range, and result limit.
2. Confirm `.env` exists, but do not open or print it.
3. Load or refresh `schema_metadata.json` before generating SQL.
4. If schema context is missing, query `information_schema` or `pg_catalog` first.
5. Prefer explicit columns over `SELECT *`; add `LIMIT` for exploratory reads.
6. On errors, use `sqlstate` and suggestions to refine the query, with a maximum of three attempts.
7. Report the executed SQL, key rows, row count, and reasoning. Do not report credentials.

## Safety Model

- The agent generates SQL and calls scripts.
- Scripts load credentials from `.env`.
- Passwords and full DSNs are never printed.
- `UPDATE` and `DELETE` without `WHERE` are blocked.
- Multiple SQL statements in one call are blocked.
- DDL and maintenance commands require `--allow-ddl`.
- Writes require `--allow-write`.

## PostgreSQL Guidance

- Use `EXPLAIN (ANALYZE, BUFFERS)` for performance work.
- Verify index usage before and after adding indexes.
- Use `CREATE INDEX CONCURRENTLY` for large production tables when appropriate.
- Run `ANALYZE` after bulk data changes.
- Use B-tree for common equality/range access, GIN for JSONB containment and full-text patterns, BRIN for large append-only time-series tables.
- Use connection pooling such as PgBouncer for long-running applications; agent scripts are short-lived.

Read `references/postgres_best_practices.md` only when deeper PostgreSQL-specific guidance is needed.


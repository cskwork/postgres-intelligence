<p align="center"><img src="logo.png" width="120" alt="logo" /></p>

# postgres-intelligence

PostgreSQL intelligence skill for LLM coding agents.

Use it with Claude Code, Codex, Cursor, Windsurf, or any local agent that needs to safely connect to PostgreSQL, inspect schemas, run read-first SQL, and reason about query performance without exposing credentials.

## Why This Exists

LLM agents are useful for database exploration, but they should not read or print secrets. `postgres-intelligence` keeps the contract clear:

- humans configure `.env`
- scripts load credentials at runtime
- agents see only safe summaries, metadata, query results, and errors

## Features

- Multi-connection PostgreSQL config with `DB1_...DB10_...`
- Safe connection testing without printing passwords or full DSNs
- Schema metadata extraction from `information_schema` and `pg_catalog`
- Read-only SQL by default: `SELECT`, `WITH`, `SHOW`, `EXPLAIN`
- Write/DDL guards with explicit `--allow-write` and `--allow-ddl`
- Structured JSON output for LLM agents
- PostgreSQL guidance for `EXPLAIN`, indexes, JSONB, and maintenance

## Install

```bash
git clone https://github.com/cskwork/postgres-intelligence.git
cd postgres-intelligence
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` with your PostgreSQL connection details.

## Quick Start

```bash
# Validate config without printing secrets
python scripts/config.py

# Test all configured connections
python scripts/db_connector.py

# Extract schema metadata
python scripts/schema_extractor.py

# Run read-only SQL
python scripts/query_executor.py --json-only "SELECT current_database(), current_schema();"
```

## Agent Rule

Do not open or print `.env` directly. Let scripts load credentials.

## Layout

```text
SKILL.md
.env.example
requirements.txt
scripts/
  config.py
  db_connector.py
  query_executor.py
  schema_extractor.py
  setup.py
references/
  postgres_best_practices.md
```

## License

MIT


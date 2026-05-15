#!/usr/bin/env python3
"""
PostgreSQL query executor.
Default execution is read-only. Writes and DDL require explicit flags.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import get_config
from db_connector import PostgresConnector


try:
    import psycopg
except ImportError as exc:  # pragma: no cover - db_connector usually guides first
    raise SystemExit(
        'Missing dependency: install with python3 -m pip install "psycopg[binary]"'
    ) from exc


ALIAS_DESCRIPTIONS = {
    "total_cnt": "total count",
    "cnt": "count",
    "row_cnt": "row count",
    "count": "count",
    "avg_score": "average score",
    "max_score": "maximum score",
    "min_score": "minimum score",
    "rate": "rate",
    "pct": "percentage",
    "ratio": "ratio",
}


class QueryExecutor:
    """Execute PostgreSQL queries and analyze database errors."""

    def __init__(self, connection):
        self.conn = connection
        self.execution_history: List[Dict[str, Any]] = []

    def _json_default(self, value: Any) -> Any:
        if isinstance(value, Decimal):
            return float(value)
        return str(value)

    def _get_column_descriptions(self, column_names: List[str]) -> Dict[str, str]:
        if not column_names:
            return {}

        descriptions: Dict[str, str] = {}
        lowered = [column.lower() for column in column_names]

        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT a.attname AS column_name, d.description AS comment
                    FROM pg_catalog.pg_attribute a
                    JOIN pg_catalog.pg_class c ON c.oid = a.attrelid
                    JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                    JOIN pg_catalog.pg_description d
                      ON d.objoid = c.oid AND d.objsubid = a.attnum
                    WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
                      AND a.attnum > 0
                      AND NOT a.attisdropped
                      AND lower(a.attname) = ANY(%s::text[])
                      AND d.description IS NOT NULL
                    """,
                    (lowered,),
                )
                for row in cursor.fetchall():
                    name = row["column_name"]
                    if name not in descriptions:
                        descriptions[name] = row["comment"]
        except Exception:
            descriptions = {}

        for column in column_names:
            key = column.lower()
            if column not in descriptions and key in ALIAS_DESCRIPTIONS:
                descriptions[column] = ALIAS_DESCRIPTIONS[key]
            elif column not in descriptions and key.endswith("_cnt"):
                descriptions[column] = f"{column} (count)"
            elif column not in descriptions and (
                key.endswith("_rate") or key.endswith("_pct")
            ):
                descriptions[column] = f"{column} (rate)"

        return descriptions

    def execute_query(self, query: str) -> Tuple[bool, Any]:
        execution_record = {"query": query, "timestamp": time.time()}

        try:
            with self.conn.cursor() as cursor:
                cursor.execute(query)
                if cursor.description:
                    rows = cursor.fetchall()
                    columns = [column.name for column in cursor.description]
                    result = {
                        "data": rows,
                        "columns": columns,
                        "column_descriptions": self._get_column_descriptions(columns),
                        "row_count": len(rows),
                    }
                else:
                    result = {
                        "message": "Query executed successfully.",
                        "rows_affected": cursor.rowcount,
                    }

            execution_record["success"] = True
            execution_record["row_count"] = result.get(
                "row_count", result.get("rows_affected")
            )
            self.execution_history.append(execution_record)
            return True, result
        except psycopg.Error as error:
            execution_record["success"] = False
            execution_record["error"] = str(error)
            execution_record["sqlstate"] = error.sqlstate
            self.execution_history.append(execution_record)
            return False, self._analyze_error(error, query)

    def _get_all_tables(self) -> List[str]:
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT table_schema || '.' || table_name AS qualified_name
                    FROM information_schema.tables
                    WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
                    ORDER BY table_schema, table_name
                    """
                )
                return [row["qualified_name"] for row in cursor.fetchall()]
        except Exception:
            return []

    def _get_table_columns(self, schema_name: str, table_name: str) -> List[str]:
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = %s
                      AND table_name = %s
                    ORDER BY ordinal_position
                    """,
                    (schema_name, table_name),
                )
                return [row["column_name"] for row in cursor.fetchall()]
        except Exception:
            return []

    def _extract_table_from_query(
        self, query: str, default_schema: str = "public"
    ) -> Optional[Tuple[str, str]]:
        patterns = [
            r"\bFROM\s+((?:[A-Za-z_][\w$]*\.)?[A-Za-z_][\w$]*)",
            r"\bJOIN\s+((?:[A-Za-z_][\w$]*\.)?[A-Za-z_][\w$]*)",
            r"\bUPDATE\s+((?:[A-Za-z_][\w$]*\.)?[A-Za-z_][\w$]*)",
            r"\bINTO\s+((?:[A-Za-z_][\w$]*\.)?[A-Za-z_][\w$]*)",
        ]

        for pattern in patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if not match:
                continue
            name = match.group(1).strip('"')
            if "." in name:
                schema_name, table_name = name.split(".", 1)
                return schema_name.strip('"'), table_name.strip('"')
            return default_schema, name.strip('"')

        return None

    def _analyze_error(self, error: psycopg.Error, query: str) -> Dict[str, Any]:
        sqlstate = error.sqlstate
        message = str(error)
        analysis: Dict[str, Any] = {
            "sqlstate": sqlstate,
            "error_message": message,
            "query": query,
            "suggestions": [],
            "fix_type": "unknown",
        }

        if sqlstate == "42P01":
            analysis["fix_type"] = "undefined_table"
            tables = self._get_all_tables()
            analysis["suggestions"].append(
                "Table not found. Check schema qualification and table spelling."
            )
            if tables:
                analysis["available_table_sample"] = tables[:30]
        elif sqlstate == "42703":
            analysis["fix_type"] = "undefined_column"
            analysis["suggestions"].append("Column not found. Check table columns.")
            table = self._extract_table_from_query(query)
            if table:
                columns = self._get_table_columns(*table)
                if columns:
                    analysis["table"] = f"{table[0]}.{table[1]}"
                    analysis["available_columns"] = columns
        elif sqlstate == "42702":
            analysis["fix_type"] = "ambiguous_column"
            analysis["suggestions"].append(
                "Ambiguous column. Use table aliases and qualify the column."
            )
        elif sqlstate == "42601":
            analysis["fix_type"] = "syntax_error"
            analysis["suggestions"].append("SQL syntax error. Check PostgreSQL syntax.")
        elif sqlstate in {"40P01", "40001"}:
            analysis["fix_type"] = "retryable_transaction"
            analysis["suggestions"].append("Deadlock or serialization failure. Retry.")
        elif sqlstate and sqlstate.startswith("08"):
            analysis["fix_type"] = "connection_error"
            analysis["suggestions"].append("Connection error. Reconnect and retry.")
        elif sqlstate == "57014":
            analysis["fix_type"] = "query_canceled"
            analysis["suggestions"].append(
                "Query canceled, likely by statement_timeout. Narrow the query."
            )
        else:
            analysis["suggestions"].append("Unexpected PostgreSQL error.")

        return analysis

    def execute_with_retry(
        self, query: str, max_retries: int = 3
    ) -> Tuple[bool, Any]:
        retryable_sqlstates = {"40P01", "40001"}

        for attempt in range(max_retries):
            success, result = self.execute_query(query)
            if success:
                return True, result

            if (
                isinstance(result, dict)
                and result.get("sqlstate") in retryable_sqlstates
                and attempt < max_retries - 1
            ):
                time.sleep(2**attempt)
                continue

            return False, result

        return False, {"error": "Max retries exceeded"}

    def validate_query(
        self, query: str, allow_write: bool = False, allow_ddl: bool = False
    ) -> Tuple[bool, str]:
        normalized = query.strip().rstrip(";")
        if not normalized:
            return False, "Query is empty"

        if ";" in normalized:
            return False, "Multiple SQL statements are not allowed"

        first_token_match = re.match(r"^\s*([A-Za-z]+)", normalized)
        if not first_token_match:
            return False, "Query must start with a SQL keyword"

        first_token = first_token_match.group(1).upper()
        read_tokens = {"SELECT", "WITH", "SHOW", "EXPLAIN"}
        write_tokens = {"INSERT", "UPDATE", "DELETE"}
        ddl_tokens = {"CREATE", "ALTER", "DROP", "TRUNCATE", "REINDEX", "VACUUM", "ANALYZE"}

        if first_token in read_tokens:
            return True, "Query validation passed"

        if first_token in write_tokens:
            if not allow_write:
                return False, (
                    f"{first_token} requires --allow-write and prior user approval"
                )
            if first_token in {"UPDATE", "DELETE"} and " WHERE " not in f" {normalized.upper()} ":
                return False, f"{first_token} without WHERE is blocked"
            return True, "Write query validation passed"

        if first_token in ddl_tokens:
            if not allow_ddl:
                return False, f"{first_token} requires --allow-ddl and prior user approval"
            return True, "DDL query validation passed"

        return False, f"Unsupported SQL statement: {first_token}"

    def get_execution_stats(self) -> Dict[str, Any]:
        total = len(self.execution_history)
        successful = sum(1 for record in self.execution_history if record["success"])
        failed = total - successful
        return {
            "total_queries": total,
            "successful": successful,
            "failed": failed,
            "success_rate": f"{(successful / total * 100):.1f}%" if total else "0%",
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Execute a PostgreSQL query")
    parser.add_argument("query", help="SQL query to execute")
    parser.add_argument("--db", dest="db_name", help="DB*_NAME to use")
    parser.add_argument("--json-only", action="store_true", help="Print only JSON result")
    parser.add_argument(
        "--allow-write",
        action="store_true",
        help="Allow INSERT/UPDATE/DELETE after user approval",
    )
    parser.add_argument(
        "--allow-ddl",
        action="store_true",
        help="Allow DDL/maintenance statements after user approval",
    )
    parser.add_argument(
        "--statement-timeout-ms",
        type=int,
        default=30000,
        help="PostgreSQL statement_timeout in milliseconds",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        config = get_config(args.db_name)
        if not args.json_only:
            print("=== PostgreSQL Query Execution ===\n")
            print(f"Connecting to: {config.name} ({config.safe_summary()['host']})")

        connector = PostgresConnector(config)
        with connector.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('statement_timeout', %s, false)",
                    (str(args.statement_timeout_ms),),
                )

            executor = QueryExecutor(conn)
            valid, message = executor.validate_query(
                args.query,
                allow_write=args.allow_write,
                allow_ddl=args.allow_ddl,
            )
            if not valid:
                payload = {
                    "success": False,
                    "error": {"sqlstate": "-1", "error_message": message},
                }
                print(json.dumps(payload, ensure_ascii=False))
                return 1

            if not args.json_only:
                print(f"Executing: {args.query}\n")

            success, result = executor.execute_with_retry(args.query)
            payload = {"success": success}
            if success:
                payload["result"] = result
            else:
                payload["error"] = result

            print(json.dumps(payload, ensure_ascii=False, default=executor._json_default))

            if not args.json_only:
                print(f"\nExecution Stats: {executor.get_execution_stats()}")

            return 0 if success else 1
    except Exception as error:
        print(
            json.dumps(
                {"success": False, "error": {"sqlstate": "-1", "error_message": str(error)}},
                ensure_ascii=False,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

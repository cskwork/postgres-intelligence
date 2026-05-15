#!/usr/bin/env python3
"""
postgres-intelligence PostgreSQL connector.
Creates short-lived PostgreSQL connections with psycopg 3.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import DatabaseConfig, get_all_configs, get_config


try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError as exc:  # pragma: no cover - dependency guidance
    raise SystemExit(
        'Missing dependency: install with python3 -m pip install "psycopg[binary]"'
    ) from exc


class PostgresConnector:
    """PostgreSQL connection factory."""

    def __init__(self, config: Optional[DatabaseConfig] = None):
        self.db_config = config or get_config()

    def get_connection(self):
        return psycopg.connect(
            **self.db_config.to_connect_kwargs(),
            autocommit=True,
            row_factory=dict_row,
        )

    def test_connection(self):
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT
                            1 AS ok,
                            current_database() AS database_name,
                            current_schema() AS schema_name,
                            version() AS version
                        """
                    )
                    row = cursor.fetchone()
            return True, row
        except Exception as error:
            return False, str(error)


if __name__ == "__main__":
    print("=== PostgreSQL Connection Test ===\n")
    try:
        configs = get_all_configs()
        print(f"Found {len(configs)} database configuration(s)\n")

        overall_success = True
        for name, config in configs.items():
            summary = config.safe_summary()
            print(f"Testing connection: {name}")
            print(f"  Host: {summary['host']}:{summary['port']}")
            print(f"  Database: {summary['database']}")

            connector = PostgresConnector(config)
            success, result = connector.test_connection()
            if success:
                print("  Connection successful")
                print(
                    "  "
                    + json.dumps(
                        {
                            "database": result["database_name"],
                            "schema": result["schema_name"],
                            "version": result["version"].split(" on ")[0],
                        },
                        ensure_ascii=False,
                    )
                )
            else:
                overall_success = False
                print(f"  Connection failed: {result}")
            print()

        if not overall_success:
            raise SystemExit(1)
    except Exception as error:
        print(f"Error: {error}")
        raise SystemExit(1)

#!/usr/bin/env python3
"""
PostgreSQL schema extractor.
Extracts schema, column, key, and index metadata from information_schema and pg_catalog.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import get_all_configs
from db_connector import PostgresConnector


class SchemaExtractor:
    """PostgreSQL schema metadata extractor."""

    def __init__(self, connection):
        self.conn = connection

    def get_all_schemas(self) -> List[str]:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT schema_name
                FROM information_schema.schemata
                WHERE schema_name NOT IN ('pg_catalog', 'information_schema')
                  AND schema_name NOT LIKE 'pg_toast%'
                ORDER BY schema_name
                """
            )
            return [row["schema_name"] for row in cursor.fetchall()]

    def get_relations_in_schema(self, schema_name: str) -> List[Dict[str, Any]]:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    n.nspname AS table_schema,
                    c.relname AS table_name,
                    CASE c.relkind
                        WHEN 'r' THEN 'BASE TABLE'
                        WHEN 'p' THEN 'PARTITIONED TABLE'
                        WHEN 'v' THEN 'VIEW'
                        WHEN 'm' THEN 'MATERIALIZED VIEW'
                        WHEN 'f' THEN 'FOREIGN TABLE'
                        ELSE c.relkind::text
                    END AS table_type,
                    pg_catalog.obj_description(c.oid, 'pg_class') AS table_comment,
                    COALESCE(s.n_live_tup, 0) AS estimated_rows,
                    pg_catalog.pg_total_relation_size(c.oid) AS total_size_bytes
                FROM pg_catalog.pg_class c
                JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                LEFT JOIN pg_catalog.pg_stat_user_tables s ON s.relid = c.oid
                WHERE n.nspname = %s
                  AND c.relkind IN ('r', 'p', 'v', 'm', 'f')
                ORDER BY c.relname
                """,
                (schema_name,),
            )
            return cursor.fetchall()

    def get_columns(self, schema_name: str, table_name: str) -> List[Dict[str, Any]]:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    c.column_name,
                    c.ordinal_position,
                    c.data_type,
                    c.udt_name,
                    c.is_nullable,
                    c.column_default,
                    c.character_maximum_length,
                    c.numeric_precision,
                    c.numeric_scale,
                    d.description AS column_comment
                FROM information_schema.columns c
                LEFT JOIN pg_catalog.pg_namespace n
                  ON n.nspname = c.table_schema
                LEFT JOIN pg_catalog.pg_class cls
                  ON cls.relnamespace = n.oid AND cls.relname = c.table_name
                LEFT JOIN pg_catalog.pg_attribute a
                  ON a.attrelid = cls.oid AND a.attname = c.column_name
                LEFT JOIN pg_catalog.pg_description d
                  ON d.objoid = cls.oid AND d.objsubid = a.attnum
                WHERE c.table_schema = %s
                  AND c.table_name = %s
                ORDER BY c.ordinal_position
                """,
                (schema_name, table_name),
            )
            return cursor.fetchall()

    def get_constraints(self, schema_name: str, table_name: str) -> List[Dict[str, Any]]:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    con.conname AS constraint_name,
                    CASE con.contype
                        WHEN 'p' THEN 'PRIMARY KEY'
                        WHEN 'u' THEN 'UNIQUE'
                        WHEN 'f' THEN 'FOREIGN KEY'
                        WHEN 'c' THEN 'CHECK'
                        WHEN 'x' THEN 'EXCLUDE'
                        ELSE con.contype::text
                    END AS constraint_type,
                    pg_catalog.pg_get_constraintdef(con.oid, true) AS definition
                FROM pg_catalog.pg_constraint con
                JOIN pg_catalog.pg_class rel ON rel.oid = con.conrelid
                JOIN pg_catalog.pg_namespace nsp ON nsp.oid = rel.relnamespace
                WHERE nsp.nspname = %s
                  AND rel.relname = %s
                ORDER BY con.conname
                """,
                (schema_name, table_name),
            )
            return cursor.fetchall()

    def get_foreign_keys(self, schema_name: str, table_name: str) -> List[Dict[str, Any]]:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    tc.constraint_name,
                    kcu.column_name,
                    ccu.table_schema AS referenced_table_schema,
                    ccu.table_name AS referenced_table_name,
                    ccu.column_name AS referenced_column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                 AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage ccu
                  ON ccu.constraint_name = tc.constraint_name
                 AND ccu.table_schema = tc.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_schema = %s
                  AND tc.table_name = %s
                ORDER BY tc.constraint_name, kcu.ordinal_position
                """,
                (schema_name, table_name),
            )
            return cursor.fetchall()

    def get_indexes(self, schema_name: str, table_name: str) -> List[Dict[str, Any]]:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    schemaname AS schema_name,
                    tablename AS table_name,
                    indexname AS index_name,
                    indexdef AS index_definition
                FROM pg_catalog.pg_indexes
                WHERE schemaname = %s
                  AND tablename = %s
                ORDER BY indexname
                """,
                (schema_name, table_name),
            )
            return cursor.fetchall()

    def get_relation_definition(
        self,
        schema_name: str,
        table_name: str,
        columns: List[Dict[str, Any]],
        constraints: List[Dict[str, Any]],
    ) -> str:
        column_lines = []
        for column in columns:
            data_type = column["data_type"]
            if column["data_type"] == "USER-DEFINED":
                data_type = column["udt_name"]
            elif column["character_maximum_length"]:
                data_type = f"{data_type}({column['character_maximum_length']})"
            elif column["numeric_precision"]:
                precision = column["numeric_precision"]
                scale = column["numeric_scale"]
                data_type = f"{data_type}({precision},{scale})" if scale else f"{data_type}({precision})"

            nullable = "" if column["is_nullable"] == "YES" else " NOT NULL"
            default = (
                f" DEFAULT {column['column_default']}"
                if column["column_default"] is not None
                else ""
            )
            column_lines.append(
                f"    {column['column_name']} {data_type}{default}{nullable}"
            )

        constraint_lines = [
            f"    CONSTRAINT {item['constraint_name']} {item['definition']}"
            for item in constraints
            if item.get("definition")
        ]
        body = ",\n".join(column_lines + constraint_lines)
        return f"CREATE TABLE {schema_name}.{table_name} (\n{body}\n);"

    def extract_full_schema(
        self, schemas: Optional[Iterable[str]] = None
    ) -> Dict[str, Any]:
        target_schemas = list(schemas) if schemas is not None else self.get_all_schemas()
        metadata: Dict[str, Any] = {
            "extraction_timestamp": datetime.now().isoformat(),
            "schemas": {},
        }

        for schema_name in target_schemas:
            schema_data: Dict[str, Any] = {"relations": {}}
            relations = self.get_relations_in_schema(schema_name)

            for relation in relations:
                table_name = relation["table_name"]
                columns = self.get_columns(schema_name, table_name)
                constraints = self.get_constraints(schema_name, table_name)
                table_data = {
                    "metadata": {
                        "type": relation["table_type"],
                        "estimated_rows": relation["estimated_rows"],
                        "total_size_bytes": relation["total_size_bytes"],
                        "comment": relation["table_comment"],
                    },
                    "columns": columns,
                    "constraints": constraints,
                    "foreign_keys": self.get_foreign_keys(schema_name, table_name),
                    "indexes": self.get_indexes(schema_name, table_name),
                    "ddl": self.get_relation_definition(
                        schema_name, table_name, columns, constraints
                    )
                    if relation["table_type"] in {"BASE TABLE", "PARTITIONED TABLE"}
                    else None,
                }
                schema_data["relations"][table_name] = table_data

            metadata["schemas"][schema_name] = schema_data

        return metadata


def output_path() -> Path:
    return Path(__file__).resolve().parent.parent / "schema_metadata.json"


if __name__ == "__main__":
    try:
        print("=== PostgreSQL Schema Extraction ===\n")
        configs = get_all_configs()
        all_metadata: Dict[str, Any] = {
            "extraction_timestamp": datetime.now().isoformat(),
            "databases": {},
        }

        for name, config in configs.items():
            summary = config.safe_summary()
            print(f"Extracting schema from: {name} ({summary['host']})")

            connector = PostgresConnector(config)
            with connector.get_connection() as conn:
                extractor = SchemaExtractor(conn)
                metadata = extractor.extract_full_schema()

            relation_count = sum(
                len(schema["relations"]) for schema in metadata["schemas"].values()
            )
            all_metadata["databases"][name] = {
                "host": summary["host"],
                "database": summary["database"],
                "schemas": metadata["schemas"],
            }
            print(f"  Extracted {relation_count} relations")
            print(f"  Schemas: {', '.join(metadata['schemas'].keys())}\n")

        path = output_path()
        with path.open("w", encoding="utf-8") as file:
            json.dump(all_metadata, file, indent=2, ensure_ascii=False, default=str)

        print(f"Metadata saved to: {path}")
        print(
            json.dumps(
                {
                    "success": True,
                    "databases": len(all_metadata["databases"]),
                    "total_schemas": sum(
                        len(db["schemas"]) for db in all_metadata["databases"].values()
                    ),
                    "total_relations": sum(
                        sum(len(schema["relations"]) for schema in db["schemas"].values())
                        for db in all_metadata["databases"].values()
                    ),
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    except Exception as error:
        print(
            json.dumps(
                {"success": False, "error": str(error)},
                indent=2,
                ensure_ascii=False,
            )
        )
        raise SystemExit(1)

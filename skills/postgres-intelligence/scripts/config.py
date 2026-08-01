#!/usr/bin/env python3
"""
postgres-intelligence configuration loader.
Loads PostgreSQL connection settings from .env at script runtime.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional


def find_env_file() -> Optional[Path]:
    """Find .env in the script directory or up to three parent directories."""
    current = Path(__file__).resolve().parent

    for _ in range(3):
        env_path = current / ".env"
        if env_path.exists():
            return env_path
        current = current.parent

    return None


def load_env_file() -> None:
    """Load simple KEY=VALUE lines from .env into environment variables."""
    env_path = find_env_file()
    if env_path is None:
        return

    with env_path.open("r", encoding="utf-8") as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()

            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            elif value.startswith("'") and value.endswith("'"):
                value = value[1:-1]

            os.environ[key] = value


load_env_file()


@dataclass(frozen=True)
class DatabaseConfig:
    """PostgreSQL connection settings. repr never exposes passwords."""

    name: str
    host: Optional[str] = None
    port: int = 5432
    user: Optional[str] = None
    password: Optional[str] = None
    database: Optional[str] = None
    dsn: Optional[str] = None
    sslmode: str = "prefer"
    connect_timeout: int = 10
    application_name: str = "postgres-intelligence"

    def to_connect_kwargs(self) -> Dict[str, object]:
        if self.dsn:
            return {
                "conninfo": self.dsn,
                "connect_timeout": self.connect_timeout,
                "application_name": self.application_name,
            }

        kwargs: Dict[str, object] = {
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "password": self.password,
            "dbname": self.database,
            "sslmode": self.sslmode,
            "connect_timeout": self.connect_timeout,
            "application_name": self.application_name,
        }
        return {key: value for key, value in kwargs.items() if value not in (None, "")}

    def safe_summary(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "host": self.host or "(dsn)",
            "port": self.port if not self.dsn else "(dsn)",
            "user": self.user or "(dsn)",
            "database": self.database or "(dsn)",
            "sslmode": self.sslmode,
            "connect_timeout": self.connect_timeout,
            "application_name": self.application_name,
        }

    def __repr__(self) -> str:
        return (
            "DatabaseConfig("
            f"name={self.name}, host={self.host or '(dsn)'}, "
            f"database={self.database or '(dsn)'}, user={self.user or '(dsn)'})"
        )


def _int_env(name: str, default: int) -> int:
    value = os.environ.get(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer: {value}") from exc


def load_database_configs() -> Dict[str, DatabaseConfig]:
    """Return DB1..DB10 connection configs keyed by friendly name."""
    configs: Dict[str, DatabaseConfig] = {}

    for index in range(1, 11):
        prefix = f"DB{index}_"
        dsn = os.environ.get(f"{prefix}DSN")
        host = os.environ.get(f"{prefix}HOST")
        user = os.environ.get(f"{prefix}USER")
        password = os.environ.get(f"{prefix}PASSWORD")
        database = os.environ.get(f"{prefix}DATABASE")

        if not dsn and not (host and user and password and database):
            continue

        name = os.environ.get(f"{prefix}NAME", f"db{index}")
        config = DatabaseConfig(
            name=name,
            host=host,
            port=_int_env(f"{prefix}PORT", 5432),
            user=user,
            password=password,
            database=database,
            dsn=dsn,
            sslmode=os.environ.get(f"{prefix}SSLMODE", "prefer"),
            connect_timeout=_int_env(f"{prefix}CONNECT_TIMEOUT", 10),
            application_name=os.environ.get(
                f"{prefix}APPLICATION_NAME", "postgres-intelligence"
            ),
        )
        configs[name] = config

    if not configs:
        raise ValueError(
            "No PostgreSQL configurations found. "
            "Create .env from .env.example and fill DB1_* values."
        )

    return configs


def get_all_configs() -> Dict[str, DatabaseConfig]:
    return load_database_configs()


def get_primary_config() -> DatabaseConfig:
    return next(iter(load_database_configs().values()))


def get_config(name: Optional[str] = None) -> DatabaseConfig:
    configs = load_database_configs()
    if name is None:
        return next(iter(configs.values()))
    if name not in configs:
        known = ", ".join(configs.keys())
        raise KeyError(f"Unknown DB name '{name}'. Known DB names: {known}")
    return configs[name]


try:
    DB_CONFIGS = load_database_configs()
    PRIMARY_CONFIG = next(iter(DB_CONFIGS.values()))
except ValueError:
    DB_CONFIGS = {}
    PRIMARY_CONFIG = None


if __name__ == "__main__":
    print("=== PostgreSQL Intelligence Configuration ===\n")
    try:
        configs = load_database_configs()
        print(f"Found {len(configs)} database configuration(s):\n")
        for index, config in enumerate(configs.values(), 1):
            summary = config.safe_summary()
            print(f"{index}. {summary['name']}")
            print(f"   Host: {summary['host']}:{summary['port']}")
            print(f"   User: {summary['user']}")
            print(f"   Database: {summary['database']}")
            print(f"   SSL mode: {summary['sslmode']}")
            print(f"   Connect timeout: {summary['connect_timeout']}s")
            print()
        print("Configuration loaded. Passwords were not displayed.")
    except ValueError as error:
        print(f"Error: {error}")
        raise SystemExit(1)

from __future__ import annotations

import sqlite3


def sqlite_table_columns(connection: sqlite3.Connection, table: str) -> list[str]:
    """Read column names for an existing SQLite table."""
    return [row[1] for row in connection.execute(f"PRAGMA table_info({table})")]

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from ffvaluation.sources.sleeper.common import dumps_json
from ffvaluation.sources.sleeper.save.sqlite import sqlite_table_columns


ROSTER_COLUMNS = [
    "captured_at",
    "league_id",
    "roster_id",
    "user_id",
    "co_owners",
    "players",
    "starters",
    "settings",
    "metadata",
    "owner_id_raw",
]


def upsert_rosters_sqlite(rows: list[dict[str, Any]], path: str | Path) -> Path:
    """Upsert Sleeper roster rows into SQLite."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    placeholders = ", ".join("?" for _ in ROSTER_COLUMNS)
    update_columns = [column for column in ROSTER_COLUMNS if column not in {"league_id", "roster_id"}]
    update_sql = ", ".join(f"{column}=excluded.{column}" for column in update_columns)
    sql = (
        f"INSERT INTO rosters ({', '.join(ROSTER_COLUMNS)}) VALUES ({placeholders}) "
        f"ON CONFLICT(league_id, roster_id) DO UPDATE SET {update_sql}"
    )
    with sqlite3.connect(path) as connection:
        if sqlite_table_columns(connection, "rosters") not in ([], ROSTER_COLUMNS):
            connection.execute("DROP TABLE rosters")
        create_rosters_table(connection)
        connection.executemany(
            sql,
            [tuple(format_roster_value(row.get(column)) for column in ROSTER_COLUMNS) for row in rows],
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_rosters_user ON rosters(user_id)")
    return path


def read_sample_league_ids_sqlite(path: str | Path) -> list[str]:
    """Read distinct league IDs from a sample SQLite database."""
    with sqlite3.connect(path) as connection:
        return [
            str(row[0])
            for row in connection.execute(
                """
                SELECT league_id FROM trades
                UNION
                SELECT league_id FROM leagues
                ORDER BY league_id
                """
            )
        ]


def create_rosters_table(connection: sqlite3.Connection) -> None:
    """Create the roster bridge table and indexes."""
    column_sql = ", ".join(f"{column} {roster_sqlite_type(column)}" for column in ROSTER_COLUMNS)
    connection.execute(
        "CREATE TABLE IF NOT EXISTS rosters "
        f"({column_sql}, PRIMARY KEY (league_id, roster_id)) WITHOUT ROWID"
    )


def roster_sqlite_type(column: str) -> str:
    """Return the SQLite type for a roster column."""
    if column in {"league_id", "roster_id", "user_id"}:
        return "INTEGER"
    return "TEXT"


def format_roster_value(value: Any) -> Any:
    """Format roster values for SQLite storage."""
    if isinstance(value, (dict, list)):
        return dumps_json(value)
    return value

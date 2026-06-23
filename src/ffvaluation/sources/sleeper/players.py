from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ffvaluation.sources.sleeper.common import (
    FetchJson,
    dumps_json,
    fetch_json as default_fetch_json,
    optional_float,
    optional_str,
    players_url,
)


PLAYER_COLUMNS = [
    "captured_at",
    "player_id",
    "full_name",
    "first_name",
    "last_name",
    "position",
    "team",
    "age",
    "status",
    "active",
    "fantasy_positions",
    "search_full_name",
]


def fetch_nfl_players(fetch_json: FetchJson | None = None) -> dict[str, dict[str, Any]]:
    """Fetch the full Sleeper NFL player catalog keyed by player ID."""
    fetch_json = fetch_json or default_fetch_json
    payload = fetch_json(players_url())
    if not isinstance(payload, dict):
        raise ValueError("Sleeper players payload must be a JSON object keyed by player ID.")
    return {
        str(player_id): player
        for player_id, player in payload.items()
        if isinstance(player, dict)
    }


def copy_trade_sample_players_sqlite(
    *,
    sample_db_path: str | Path,
    players_db_path: str | Path,
) -> int:
    """Copy sample-referenced players from the raw player catalog into the sample DB."""
    sample_db_path = Path(sample_db_path)
    players_db_path = Path(players_db_path)
    if not players_db_path.exists():
        raise FileNotFoundError(
            f"{players_db_path} not found. Run `ffvaluation pull-sleeper-players` first."
        )

    player_ids = read_trade_player_ids_sqlite(sample_db_path)
    if not player_ids:
        return 0

    placeholders = ", ".join("?" for _ in player_ids)
    with sqlite3.connect(sample_db_path) as connection:
        if sqlite_table_columns(connection, "players") not in ([], PLAYER_COLUMNS):
            connection.execute("DROP TABLE players")
        create_players_table(connection)
        connection.execute("ATTACH DATABASE ? AS player_catalog", (str(players_db_path),))
        connection.execute(
            f"INSERT OR REPLACE INTO players ({', '.join(PLAYER_COLUMNS)}) "
            f"SELECT {', '.join(PLAYER_COLUMNS)} "
            "FROM player_catalog.players "
            f"WHERE player_id IN ({placeholders})",
            sorted(player_ids),
        )
        copied = int(connection.execute("SELECT changes()").fetchone()[0])
        connection.commit()
        connection.execute("DETACH DATABASE player_catalog")
    return copied


def pull_nfl_players_sqlite(
    *,
    path: str | Path,
    captured_at: datetime | None = None,
    fetch_json: FetchJson | None = None,
) -> int:
    """Fetch the Sleeper NFL player catalog and upsert it into SQLite."""
    captured_at = captured_at or datetime.now(UTC)
    players = fetch_nfl_players(fetch_json=fetch_json)
    rows = [
        format_player_row(captured_at=captured_at, player_id=player_id, player=player)
        for player_id, player in players.items()
    ]
    upsert_players_sqlite(rows=rows, path=path)
    return len(rows)


def read_trade_player_ids_sqlite(path: str | Path) -> set[str]:
    """Read all player IDs referenced by trade add/drop payloads in SQLite."""
    player_ids: set[str] = set()
    with sqlite3.connect(path) as connection:
        for adds, drops in connection.execute("SELECT adds, drops FROM trades"):
            player_ids.update(json_object_keys(adds))
            player_ids.update(json_object_keys(drops))
    return player_ids


def json_object_keys(value: str | None) -> set[str]:
    """Return keys from a JSON object string, or an empty set for non-objects."""
    if not value:
        return set()
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        return set()
    return {str(key) for key in parsed}


def upsert_players_sqlite(*, rows: list[dict[str, Any]], path: str | Path) -> Path:
    """Upsert player lookup rows into a SQLite database."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    placeholders = ", ".join("?" for _ in PLAYER_COLUMNS)
    update_columns = [column for column in PLAYER_COLUMNS if column != "player_id"]
    update_sql = ", ".join(f"{column}=excluded.{column}" for column in update_columns)
    sql = (
        f"INSERT INTO players ({', '.join(PLAYER_COLUMNS)}) VALUES ({placeholders}) "
        f"ON CONFLICT(player_id) DO UPDATE SET {update_sql}"
    )
    with sqlite3.connect(path) as connection:
        if sqlite_table_columns(connection, "players") not in ([], PLAYER_COLUMNS):
            connection.execute("DROP TABLE players")
        create_players_table(connection)
        connection.executemany(
            sql,
            [tuple(row.get(column) for column in PLAYER_COLUMNS) for row in rows],
        )
    return path


def create_players_table(connection: sqlite3.Connection) -> None:
    """Create the player catalog table and indexes."""
    column_sql = ", ".join(f"{column} {player_sqlite_type(column)}" for column in PLAYER_COLUMNS)
    connection.execute(
        "CREATE TABLE IF NOT EXISTS players "
        f"({column_sql}, PRIMARY KEY (player_id)) WITHOUT ROWID"
    )
    connection.execute("CREATE INDEX IF NOT EXISTS idx_players_name ON players(full_name)")


def sqlite_table_columns(connection: sqlite3.Connection, table: str) -> list[str]:
    """Read column names for an existing SQLite table."""
    return [row[1] for row in connection.execute(f"PRAGMA table_info({table})")]


def player_sqlite_type(column: str) -> str:
    """Return the SQLite type for a player column."""
    if column == "age":
        return "REAL"
    if column == "active":
        return "INTEGER"
    return "TEXT"


def format_player_row(
    *,
    captured_at: datetime,
    player_id: str,
    player: dict[str, Any],
) -> dict[str, Any]:
    """Format one Sleeper player payload for SQLite storage."""
    full_name = optional_str(player.get("full_name")) or player_name(player)
    active = player.get("active")
    return {
        "captured_at": captured_at.isoformat(),
        "player_id": player_id,
        "full_name": full_name,
        "first_name": optional_str(player.get("first_name")) or "",
        "last_name": optional_str(player.get("last_name")) or "",
        "position": optional_str(player.get("position")) or "",
        "team": optional_str(player.get("team")) or "",
        "age": optional_float(player.get("age")),
        "status": optional_str(player.get("status")) or "",
        "active": int(active) if active is not None else None,
        "fantasy_positions": dumps_json(player.get("fantasy_positions") or []),
        "search_full_name": optional_str(player.get("search_full_name")) or full_name.lower(),
    }


def player_name(player: dict[str, Any]) -> str:
    """Build a display name from first and last name fields."""
    return " ".join(
        part
        for part in [
            optional_str(player.get("first_name")),
            optional_str(player.get("last_name")),
        ]
        if part
    )


def trade_way_distribution(rows: Iterable[tuple[str, str]]) -> dict[int, int]:
    """Count sample trades by number of consenting rosters."""
    counts: dict[int, int] = {}
    for _transaction_id, consenter_ids in rows:
        way = len(json.loads(consenter_ids or "[]"))
        counts[way] = counts.get(way, 0) + 1
    return dict(sorted(counts.items()))

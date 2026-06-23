from __future__ import annotations

import csv
import sqlite3
from collections.abc import Iterable
from pathlib import Path

from ffvaluation.sources.sleeper.common import dumps_json
from ffvaluation.sources.sleeper.discovery import discovery_sqlite_type
from ffvaluation.sources.sleeper.load.sqlite import sqlite_table_columns
from ffvaluation.sources.sleeper.models import (
    LEAGUE_DISCOVERY_COLUMNS,
    TRADE_HISTORY_COLUMNS,
    SleeperTradeRow,
)


def upsert_trade_history_sqlite(rows: list[SleeperTradeRow], path: str | Path) -> Path:
    """Upsert Sleeper trade rows into a SQLite sample database."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = TRADE_HISTORY_COLUMNS
    column_sql = ", ".join(f"{column} TEXT" for column in columns)
    placeholders = ", ".join("?" for _ in columns)
    update_columns = [column for column in columns if column not in {"league_id", "transaction_id"}]
    update_sql = ", ".join(f"{column}=excluded.{column}" for column in update_columns)
    sql = (
        f"INSERT INTO trades ({', '.join(columns)}) VALUES ({placeholders}) "
        "ON CONFLICT(league_id, transaction_id) DO UPDATE SET "
        f"{update_sql}"
    )
    with sqlite3.connect(path) as connection:
        if sqlite_table_columns(connection, "trades") not in ([], columns):
            connection.execute("DROP TABLE trades")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS trades "
            f"({column_sql}, PRIMARY KEY (league_id, transaction_id))"
        )
        connection.executemany(
            sql,
            [tuple(format_trade_row(row)[column] for column in columns) for row in rows],
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_trades_created_at ON trades(created_at)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_trades_league ON trades(league_id)")
    return path


def copy_trade_sample_leagues_sqlite(
    *,
    discovery_db_path: str | Path,
    sample_db_path: str | Path,
    league_ids: Iterable[str],
) -> Path:
    """Copy sampled league rows from discovery SQLite into the trade sample database."""
    sample_db_path = Path(sample_db_path)
    sample_db_path.parent.mkdir(parents=True, exist_ok=True)
    league_ids = sorted({str(league_id) for league_id in league_ids})
    if not league_ids:
        return sample_db_path

    column_sql = ", ".join(
        f"{column} {discovery_sqlite_type(column)}" for column in LEAGUE_DISCOVERY_COLUMNS
    )
    placeholders = ", ".join("?" for _ in league_ids)
    with sqlite3.connect(sample_db_path) as connection:
        if sqlite_table_columns(connection, "leagues") not in ([], LEAGUE_DISCOVERY_COLUMNS):
            connection.execute("DROP TABLE leagues")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS leagues "
            f"({column_sql}, PRIMARY KEY (league_id)) WITHOUT ROWID"
        )
        connection.execute("ATTACH DATABASE ? AS discovery", (str(discovery_db_path),))
        connection.execute(
            f"INSERT OR REPLACE INTO leagues ({', '.join(LEAGUE_DISCOVERY_COLUMNS)}) "
            f"SELECT {', '.join(LEAGUE_DISCOVERY_COLUMNS)} "
            "FROM discovery.leagues "
            f"WHERE league_id IN ({placeholders})",
            league_ids,
        )
        connection.commit()
        connection.execute("DETACH DATABASE discovery")
    return sample_db_path


def write_trade_history_csv(rows: list[SleeperTradeRow], path: str | Path) -> Path:
    """Write Sleeper trade rows to a CSV file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=TRADE_HISTORY_COLUMNS)
        writer.writeheader()
        writer.writerows(format_trade_row(row) for row in rows)

    return path


def upsert_trade_history_csv(rows: list[SleeperTradeRow], path: str | Path) -> Path:
    """Upsert Sleeper trade rows into the trade-history CSV."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    merged_rows: dict[str, dict[str, str]] = {}

    if path.exists():
        with path.open(newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                transaction_id = row.get("transaction_id", "")
                if transaction_id:
                    merged_rows[transaction_id] = {
                        field: row.get(field, "") for field in TRADE_HISTORY_COLUMNS
                    }

    for row in rows:
        formatted = format_trade_row(row)
        merged_rows[formatted["transaction_id"]] = formatted

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=TRADE_HISTORY_COLUMNS)
        writer.writeheader()
        writer.writerows(
            row
            for _transaction_id, row in sorted(
                merged_rows.items(),
                key=lambda item: (
                    item[1]["created_at"],
                    item[1]["league_id"],
                    item[1]["transaction_id"],
                ),
            )
        )

    return path


def format_trade_row(row: SleeperTradeRow) -> dict[str, str]:
    """Format a Sleeper trade row for CSV or SQLite output."""
    return {
        "captured_at": row.captured_at.isoformat(),
        "league_id": row.league_id,
        "round": str(row.round),
        "transaction_id": row.transaction_id,
        "status": row.status,
        "created": "" if row.created is None else str(row.created),
        "created_at": "" if row.created_at is None else row.created_at.isoformat(),
        "status_updated": "" if row.status_updated is None else str(row.status_updated),
        "status_updated_at": ""
        if row.status_updated_at is None
        else row.status_updated_at.isoformat(),
        "roster_ids": dumps_json(row.roster_ids),
        "consenter_ids": dumps_json(row.consenter_ids),
        "adds": dumps_json(row.adds),
        "drops": dumps_json(row.drops),
        "draft_picks": dumps_json(row.draft_picks),
        "waiver_budget": dumps_json(row.waiver_budget),
    }

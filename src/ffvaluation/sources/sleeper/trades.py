from __future__ import annotations

import csv
import json
import sqlite3
import time
from collections.abc import Callable, Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from ffvaluation.sources.sleeper.common import (
    FetchJson,
    dumps_json,
    fetch_json as default_fetch_json,
    is_dynasty,
    league_url,
    millis_to_datetime,
    optional_float,
    optional_int,
    optional_str,
    te_premium,
    transactions_url,
)
from ffvaluation.sources.sleeper.discovery import discovery_sqlite_type
from ffvaluation.sources.sleeper.models import TRADE_HISTORY_COLUMNS, SleeperTradeRow
from ffvaluation.sources.sleeper.models import LEAGUE_DISCOVERY_COLUMNS


TRADE_SIDE_COLUMNS = [
    "league_id",
    "transaction_id",
    "side_roster_id",
    "completed_date",
    "player_ids_in_json",
    "player_ids_out_json",
    "picks_in_json",
    "picks_out_json",
    "faab_in",
    "faab_out",
]


def fetch_trade_history(
    *,
    league_id: str,
    days: int | None = 365,
    rounds: Iterable[int] = range(1, 19),
    follow_previous: bool = True,
    max_leagues: int | None = None,
    captured_at: datetime | None = None,
    sleep_seconds: float = 0.1,
    fetch_json: FetchJson | None = None,
) -> list[SleeperTradeRow]:
    """Fetch completed Sleeper trades across a league chain."""
    captured_at = captured_at or datetime.now(UTC)
    since = None if days is None else captured_at - timedelta(days=days)
    fetch_json = fetch_json or default_fetch_json
    rows: list[SleeperTradeRow] = []

    for league in iter_league_chain(
        league_id=league_id,
        follow_previous=follow_previous,
        max_leagues=max_leagues,
        fetch_json=fetch_json,
    ):
        for round_number in rounds:
            transactions = fetch_json(transactions_url(str(league["league_id"]), round_number))
            for transaction in transactions:
                if transaction.get("type") != "trade" or transaction.get("status") != "complete":
                    continue

                created_at = millis_to_datetime(transaction.get("created"))
                status_updated_at = millis_to_datetime(transaction.get("status_updated"))
                trade_time = created_at or status_updated_at
                if since is not None and trade_time is not None and trade_time < since:
                    continue

                rows.append(
                    trade_row(
                        captured_at=captured_at,
                        league=league,
                        round_number=round_number,
                        transaction=transaction,
                    )
                )

            if sleep_seconds > 0:
                time.sleep(sleep_seconds)

    rows.sort(key=lambda row: (row.created_at or datetime.min.replace(tzinfo=UTC), row.league_id))
    return rows


def sample_league_ids_from_discovery(
    *,
    discovery_db_path: str | Path,
    season: str,
    limit: int,
    target_only: bool = True,
) -> list[str]:
    """Sample discovered Sleeper league IDs from the discovery SQLite database."""
    where_sql = "league_season = ?"
    parameters: list[str | int] = [season]
    if target_only:
        where_sql += " AND target_format_guess = 1"
    with sqlite3.connect(discovery_db_path) as connection:
        return [
            str(row[0])
            for row in connection.execute(
                "SELECT league_id FROM leagues "
                f"WHERE {where_sql} "
                "ORDER BY random() "
                "LIMIT ?",
                (*parameters, limit),
            )
        ]


def fetch_trade_sample(
    *,
    league_ids: Iterable[str],
    season: str,
    captured_at: datetime | None = None,
    rounds: Iterable[int] = range(1, 19),
    sleep_seconds: float = 0.1,
    fetch_json: FetchJson | None = None,
    progress_callback: Callable[[int, int, int, str], None] | None = None,
) -> list[SleeperTradeRow]:
    """Fetch completed trades for a set of sampled leagues in one season."""
    league_ids = list(league_ids)
    total = len(league_ids)
    captured_at = captured_at or datetime.now(UTC)
    rows: list[SleeperTradeRow] = []
    for index, league_id in enumerate(league_ids, start=1):
        league_rows = fetch_trade_history(
            league_id=league_id,
            days=None,
            rounds=rounds,
            follow_previous=False,
            max_leagues=1,
            captured_at=captured_at,
            sleep_seconds=sleep_seconds,
            fetch_json=fetch_json,
        )
        league_rows = [row for row in league_rows if row.league_season == season]
        rows.extend(league_rows)
        if progress_callback is not None:
            progress_callback(index, total, len(rows), league_id)
    return rows


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


def sqlite_table_columns(connection: sqlite3.Connection, table: str) -> list[str]:
    """Read column names for an existing SQLite table."""
    return [row[1] for row in connection.execute(f"PRAGMA table_info({table})")]


def trade_sides_from_sqlite(
    path: str | Path,
) -> list[dict[str, Any]]:
    """Build one roster-perspective side row per completed Sleeper trade participant."""
    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT
                t.league_id,
                t.transaction_id,
                t.status_updated_at,
                t.roster_ids,
                t.consenter_ids,
                t.adds,
                t.drops,
                t.draft_picks,
                t.waiver_budget
            FROM trades t
            ORDER BY t.status_updated_at, t.league_id, t.transaction_id
            """
        ).fetchall()

    side_rows: list[dict[str, Any]] = []
    for row in rows:
        side_rows.extend(trade_side_rows(row))
    return side_rows


def trade_sides_dataframe(path: str | Path):
    """Build a pandas DataFrame of roster-perspective trade side rows."""
    import pandas as pd

    return pd.DataFrame(trade_sides_from_sqlite(path), columns=TRADE_SIDE_COLUMNS)


def trade_side_rows(row: sqlite3.Row) -> list[dict[str, Any]]:
    """Build side rows for one raw trade row."""
    side_roster_ids = sorted(
        {
            int(roster_id)
            for roster_id in parse_json_value(row["consenter_ids"], [])
            or parse_json_value(row["roster_ids"], [])
        }
    )
    adds = parse_json_value(row["adds"], {}) or {}
    drops = parse_json_value(row["drops"], {}) or {}
    draft_picks = parse_json_value(row["draft_picks"], []) or []
    waiver_budget = parse_json_value(row["waiver_budget"], []) or []

    return [
        {
            "league_id": row["league_id"],
            "transaction_id": row["transaction_id"],
            "side_roster_id": side_roster_id,
            "completed_date": completed_date(row["status_updated_at"]),
            "player_ids_in_json": dumps_json(player_ids_for_roster(adds, side_roster_id)),
            "player_ids_out_json": dumps_json(player_ids_for_roster(drops, side_roster_id)),
            "picks_in_json": dumps_json(pick_tokens_for_roster(draft_picks, "owner_id", side_roster_id)),
            "picks_out_json": dumps_json(
                pick_tokens_for_roster(draft_picks, "previous_owner_id", side_roster_id)
            ),
            "faab_in": faab_total_for_roster(waiver_budget, "receiver", side_roster_id),
            "faab_out": faab_total_for_roster(waiver_budget, "sender", side_roster_id),
        }
        for side_roster_id in side_roster_ids
    ]


def completed_date(value: str | None) -> str:
    """Return the completed date portion of a Sleeper status-updated timestamp."""
    return "" if not value else value[:10]


def parse_json_value(value: str | None, fallback: Any) -> Any:
    """Parse a JSON SQLite value while returning a fallback for blanks/nulls."""
    if not value:
        return fallback
    parsed = json.loads(value)
    return fallback if parsed is None else parsed


def player_ids_for_roster(player_map: dict[str, Any], roster_id: int) -> list[str]:
    """Return player IDs whose trade payload value matches a roster ID."""
    return sorted(
        str(player_id)
        for player_id, mapped_roster_id in player_map.items()
        if optional_int(mapped_roster_id) == roster_id
    )


def pick_tokens_for_roster(
    draft_picks: list[dict[str, Any]],
    roster_field: str,
    roster_id: int,
) -> list[str]:
    """Return compact pick tokens for picks matching a roster field."""
    return sorted(
        pick_token(pick)
        for pick in draft_picks
        if optional_int(pick.get(roster_field)) == roster_id
    )


def pick_token(pick: dict[str, Any]) -> str:
    """Format a draft pick as a compact sortable token."""
    return f"{pick['season']}-{optional_int(pick['round']):02d}"


def faab_total_for_roster(
    waiver_budget: list[dict[str, Any]],
    roster_field: str,
    roster_id: int,
) -> int:
    """Sum FAAB amount entries matching a roster field."""
    return sum(
        optional_int(entry.get("amount")) or 0
        for entry in waiver_budget
        if optional_int(entry.get(roster_field)) == roster_id
    )


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


def iter_league_chain(
    *,
    league_id: str,
    follow_previous: bool,
    max_leagues: int | None,
    fetch_json: FetchJson,
) -> Iterable[dict[str, Any]]:
    """Yield a league and optionally its previous-season ancestors."""
    current_league_id: str | None = league_id
    seen: set[str] = set()
    league_count = 0

    while current_league_id:
        if current_league_id in seen:
            return
        if max_leagues is not None and league_count >= max_leagues:
            return

        league = fetch_json(league_url(current_league_id))
        seen.add(current_league_id)
        league_count += 1
        yield league

        current_league_id = str(league.get("previous_league_id") or "") or None
        if not follow_previous:
            return


def trade_row(
    *,
    captured_at: datetime,
    league: dict[str, Any],
    round_number: int,
    transaction: dict[str, Any],
) -> SleeperTradeRow:
    """Parse a completed Sleeper trade transaction into a row."""
    scoring_settings = league.get("scoring_settings") or {}
    league_settings = league.get("settings") or {}
    roster_positions = [str(position) for position in league.get("roster_positions") or []]
    ppr = optional_float(scoring_settings.get("rec"))
    premium = te_premium(scoring_settings, ppr)
    is_superflex = "SUPER_FLEX" in roster_positions
    total_rosters = optional_int(league.get("total_rosters"))
    dynasty = is_dynasty(league)

    return SleeperTradeRow(
        captured_at=captured_at,
        league_id=str(league["league_id"]),
        league_name=str(league.get("name") or ""),
        league_season=str(league.get("season") or ""),
        previous_league_id=optional_str(league.get("previous_league_id")),
        round=round_number,
        transaction_id=str(transaction["transaction_id"]),
        status=str(transaction.get("status") or ""),
        created=optional_int(transaction.get("created")),
        created_at=millis_to_datetime(transaction.get("created")),
        status_updated=optional_int(transaction.get("status_updated")),
        status_updated_at=millis_to_datetime(transaction.get("status_updated")),
        roster_ids=[int(roster_id) for roster_id in transaction.get("roster_ids") or []],
        consenter_ids=[int(roster_id) for roster_id in transaction.get("consenter_ids") or []],
        adds=transaction.get("adds"),
        drops=transaction.get("drops"),
        draft_picks=transaction.get("draft_picks") or [],
        waiver_budget=transaction.get("waiver_budget") or [],
        total_rosters=total_rosters,
        is_dynasty=dynasty,
        is_superflex=is_superflex,
        ppr=ppr,
        te_premium=premium,
        target_format_guess=(
            total_rosters == 12
            and dynasty is True
            and is_superflex
            and ppr == 1.0
            and premium == 0.0
        ),
        league_settings=league_settings,
        scoring_settings=scoring_settings,
        roster_positions=roster_positions,
    )


def format_trade_row(row: SleeperTradeRow) -> dict[str, str]:
    """Format a Sleeper trade row for CSV output."""
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

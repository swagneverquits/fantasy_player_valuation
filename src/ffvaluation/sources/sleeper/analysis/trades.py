from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from ffvaluation.sources.sleeper.common import dumps_json, optional_int


TRADE_SIDE_COLUMNS = [
    "league_id",
    "transaction_id",
    "user_id",
    "side_roster_id",
    "completed_date",
    "player_ids_in",
    "player_ids_out",
    "picks_in",
    "picks_out",
    "faab_in",
    "faab_out",
]


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


def trade_sides_from_sqlite(path: str | Path) -> list[dict[str, Any]]:
    """Build one roster-perspective side row per completed Sleeper trade participant."""
    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        has_rosters = bool(
            connection.execute(
                "SELECT count(*) FROM sqlite_master WHERE type = 'table' AND name = 'rosters'"
            ).fetchone()[0]
        )
        user_id_sql = "r.user_id" if has_rosters else "NULL"
        roster_join_sql = (
            "LEFT JOIN rosters r "
            "ON r.league_id = CAST(t.league_id AS INTEGER) "
            "AND r.roster_id = side_rosters.value"
            if has_rosters
            else ""
        )
        rows = connection.execute(
            f"""
            SELECT
                t.league_id,
                t.transaction_id,
                {user_id_sql} AS user_id,
                side_rosters.value AS side_roster_id,
                t.status_updated_at,
                t.roster_ids,
                t.consenter_ids,
                t.adds,
                t.drops,
                t.draft_picks,
                t.waiver_budget
            FROM trades t
            JOIN json_each(
                CASE
                    WHEN t.consenter_ids IS NULL OR t.consenter_ids IN ('null', '[]')
                    THEN t.roster_ids
                    ELSE t.consenter_ids
                END
            ) side_rosters
            {roster_join_sql}
            ORDER BY t.status_updated_at, t.league_id, t.transaction_id, side_rosters.value
            """
        ).fetchall()

    return [trade_side_row(row) for row in rows]


def trade_sides_dataframe(path: str | Path):
    """Build a pandas DataFrame of roster-perspective trade side rows."""
    import pandas as pd

    dataframe = pd.DataFrame(trade_sides_from_sqlite(path), columns=TRADE_SIDE_COLUMNS)
    for column in ["league_id", "transaction_id", "side_roster_id"]:
        dataframe[column] = dataframe[column].astype("int64")
    dataframe["user_id"] = dataframe["user_id"].astype("Int64")
    return dataframe


def trade_side_row(row: sqlite3.Row) -> dict[str, Any]:
    """Build one side row for one raw trade participant."""
    side_roster_id = required_int(row["side_roster_id"])
    adds = parse_json_value(row["adds"], {}) or {}
    drops = parse_json_value(row["drops"], {}) or {}
    draft_picks = parse_json_value(row["draft_picks"], []) or []
    waiver_budget = parse_json_value(row["waiver_budget"], []) or []

    return {
        "league_id": required_int(row["league_id"]),
        "transaction_id": required_int(row["transaction_id"]),
        "user_id": optional_int(row["user_id"]),
        "side_roster_id": side_roster_id,
        "completed_date": completed_date(row["status_updated_at"]),
        "player_ids_in": dumps_json(player_ids_for_roster(adds, side_roster_id)),
        "player_ids_out": dumps_json(player_ids_for_roster(drops, side_roster_id)),
        "picks_in": dumps_json(pick_tokens_for_roster(draft_picks, "owner_id", side_roster_id)),
        "picks_out": dumps_json(
            pick_tokens_for_roster(draft_picks, "previous_owner_id", side_roster_id)
        ),
        "faab_in": faab_total_for_roster(waiver_budget, "receiver", side_roster_id),
        "faab_out": faab_total_for_roster(waiver_budget, "sender", side_roster_id),
    }


def completed_date(value: str | None) -> str:
    """Return the completed date portion of a Sleeper status-updated timestamp."""
    return "" if not value else value[:10]


def parse_json_value(value: str | None, fallback: Any) -> Any:
    """Parse a JSON SQLite value while returning a fallback for blanks/nulls."""
    if not value:
        return fallback
    parsed = json.loads(value)
    return fallback if parsed is None else parsed


def required_int(value: Any) -> int:
    """Parse a required integer value."""
    parsed = optional_int(value)
    if parsed is None:
        raise ValueError("Expected a non-null integer value.")
    return parsed


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

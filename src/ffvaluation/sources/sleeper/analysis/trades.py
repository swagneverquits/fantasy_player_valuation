from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from ffvaluation.sources.sleeper.common import dumps_json, optional_int


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


def trade_sides_from_sqlite(path: str | Path) -> list[dict[str, Any]]:
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
            "picks_in_json": dumps_json(
                pick_tokens_for_roster(draft_picks, "owner_id", side_roster_id)
            ),
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

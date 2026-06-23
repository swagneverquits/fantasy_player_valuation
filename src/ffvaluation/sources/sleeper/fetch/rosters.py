from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from typing import Any

from ffvaluation.sources.sleeper.common import (
    FetchJson,
    fetch_json as default_fetch_json,
    league_rosters_url,
    optional_int,
    optional_str,
)


def fetch_league_rosters(
    *,
    league_id: str,
    captured_at: datetime | None = None,
    fetch_json: FetchJson | None = None,
) -> list[dict[str, Any]]:
    """Fetch Sleeper roster rows for one league."""
    captured_at = captured_at or datetime.now(UTC)
    fetch_json = fetch_json or default_fetch_json
    payload = fetch_json(league_rosters_url(league_id))
    if not isinstance(payload, list):
        raise ValueError("Sleeper rosters payload must be a JSON array.")
    return [
        roster_row(captured_at=captured_at, league_id=league_id, roster=roster)
        for roster in payload
        if isinstance(roster, dict)
    ]


def fetch_roster_sample(
    *,
    league_ids: Iterable[str],
    captured_at: datetime | None = None,
    fetch_json: FetchJson | None = None,
    sleep_seconds: float = 0.1,
    progress_callback: Callable[[int, int, int, str], None] | None = None,
) -> list[dict[str, Any]]:
    """Fetch roster rows for a set of sampled leagues."""
    captured_at = captured_at or datetime.now(UTC)
    league_ids = list(league_ids)
    total = len(league_ids)
    rows: list[dict[str, Any]] = []
    for index, league_id in enumerate(league_ids, start=1):
        league_rows = fetch_league_rosters(
            league_id=league_id,
            captured_at=captured_at,
            fetch_json=fetch_json,
        )
        rows.extend(league_rows)
        if progress_callback is not None:
            progress_callback(index, total, len(rows), league_id)
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)
    return rows


def roster_row(
    *,
    captured_at: datetime,
    league_id: str,
    roster: dict[str, Any],
) -> dict[str, Any]:
    """Format one Sleeper roster payload for SQLite storage."""
    return {
        "captured_at": captured_at.isoformat(),
        "league_id": optional_int(league_id),
        "roster_id": optional_int(roster.get("roster_id")),
        "user_id": optional_int(roster.get("owner_id")),
        "co_owners": roster.get("co_owners") or [],
        "players": roster.get("players") or [],
        "starters": roster.get("starters") or [],
        "settings": roster.get("settings") or {},
        "metadata": roster.get("metadata") or {},
        "owner_id_raw": optional_str(roster.get("owner_id")) or "",
    }

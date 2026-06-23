from __future__ import annotations

from typing import Any

from ffvaluation.sources.sleeper.common import (
    FetchJson,
    fetch_json as default_fetch_json,
    players_url,
)


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

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ffvaluation.ingestion.snapshots import ManualSnapshotRow
from ffvaluation.models import DEFAULT_FORMAT, Player, ValuationSnapshot


BASE_URL = "https://rosteraudit.com/wp-json/ra/v1"
SOURCE_NAME = "RosterAudit"

FetchJson = Callable[[str], dict[str, Any]]
ProgressCallback = Callable[[int, int, str], None]


@dataclass(frozen=True)
class ValueHistoryRow:
    source: str
    captured_at: datetime
    as_of_date: str
    player_id: str
    player_name: str
    position: str
    team: str | None
    sf_value: float | None
    one_qb_value: float | None


@dataclass(frozen=True)
class ValueHistoryPullResult:
    rows_written: int
    players_fetched: int
    players_skipped: int


def fetch_rankings_snapshot(
    *,
    captured_at: datetime | None = None,
    season: int | None = None,
    week: int | None = None,
    league_size: int = 12,
    per_page: int = 100,
    max_pages: int | None = None,
    fetch_json: FetchJson | None = None,
) -> list[ManualSnapshotRow]:
    captured_at = captured_at or datetime.now(UTC)
    season = season or captured_at.year
    fetch_json = fetch_json or _fetch_json

    players = list(
        _iter_rankings_players(
            league_size=league_size,
            per_page=per_page,
            max_pages=max_pages,
            fetch_json=fetch_json,
        )
    )
    players.sort(key=lambda player: _superflex_value(player), reverse=True)

    rows: list[ManualSnapshotRow] = []
    for rank, player_data in enumerate(players, start=1):
        player_id = _asset_id(player_data)
        rows.append(
            ManualSnapshotRow(
                player=Player(
                    player_id=player_id,
                    name=str(player_data["name"]),
                    position=str(player_data["position"]).upper(),
                    team=_optional_str(player_data.get("team")),
                    age=_optional_float(player_data.get("age")),
                ),
                valuation=ValuationSnapshot(
                    source=SOURCE_NAME,
                    captured_at=captured_at,
                    season=season,
                    week=week,
                    format=DEFAULT_FORMAT,
                    player_id=player_id,
                    rank=rank,
                    raw_value=_superflex_value(player_data),
                ),
            )
        )
    return rows


def fetch_value_history_snapshot(
    *,
    api_key: str,
    captured_at: datetime | None = None,
    league_size: int = 12,
    per_page: int = 100,
    max_pages: int | None = None,
    limit: int | None = None,
    sleep_seconds: float = 0.5,
    progress_callback: ProgressCallback | None = None,
    fetch_json: FetchJson | None = None,
) -> list[ValueHistoryRow]:
    captured_at = captured_at or datetime.now(UTC)
    rankings_fetch_json = fetch_json or _fetch_json

    players = _iter_rankings_players(
        league_size=league_size,
        per_page=per_page,
        max_pages=max_pages,
        fetch_json=rankings_fetch_json,
    )
    if limit is not None:
        players = players[:limit]

    rows: list[ValueHistoryRow] = []
    total_players = len(players)
    for index, player in enumerate(players):
        if index > 0 and sleep_seconds > 0:
            time.sleep(sleep_seconds)

        status, player_rows = _fetch_value_history_player_rows(
            player,
            api_key=api_key,
            captured_at=captured_at,
            fetch_json=fetch_json,
        )
        rows.extend(player_rows)
        if progress_callback:
            progress_callback(index + 1, total_players, status)

    return rows


def pull_value_history_csv_incremental(
    *,
    api_key: str,
    path: str | Path,
    captured_at: datetime | None = None,
    league_size: int = 12,
    per_page: int = 100,
    max_pages: int | None = None,
    limit: int | None = None,
    latest_as_of_date: str | None = None,
    sleep_seconds: float = 0.5,
    progress_callback: ProgressCallback | None = None,
    fetch_json: FetchJson | None = None,
) -> ValueHistoryPullResult:
    captured_at = captured_at or datetime.now(UTC)
    latest_as_of_date = latest_as_of_date or captured_at.date().isoformat()
    path = Path(path)
    rankings_fetch_json = fetch_json or _fetch_json
    existing_dates_by_player = read_value_history_dates_by_player(path)

    players = _iter_rankings_players(
        league_size=league_size,
        per_page=per_page,
        max_pages=max_pages,
        fetch_json=rankings_fetch_json,
    )
    if limit is not None:
        players = players[:limit]

    rows_written = 0
    players_fetched = 0
    players_skipped = 0
    total_players = len(players)
    for index, player in enumerate(players):
        player_id = _optional_str(player.get("sleeper_id"))
        if (
            player_id
            and latest_as_of_date
            in existing_dates_by_player.get(player_id, set())
        ):
            players_skipped += 1
            if progress_callback:
                progress_callback(index + 1, total_players, "latest saved")
            continue

        if index > 0 and sleep_seconds > 0:
            time.sleep(sleep_seconds)

        status, player_rows = _fetch_value_history_player_rows(
            player,
            api_key=api_key,
            captured_at=captured_at,
            fetch_json=fetch_json,
        )
        if player_rows:
            write_value_history_csv(player_rows, path)
            rows_written += len(player_rows)
            players_fetched += 1
            existing_dates_by_player.setdefault(player_rows[0].player_id, set()).update(
                row.as_of_date for row in player_rows
            )
        else:
            players_skipped += 1

        if progress_callback:
            progress_callback(index + 1, total_players, status)

    return ValueHistoryPullResult(
        rows_written=rows_written,
        players_fetched=players_fetched,
        players_skipped=players_skipped,
    )


def read_value_history_dates_by_player(path: str | Path) -> dict[str, set[str]]:
    import csv

    path = Path(path)
    if not path.exists():
        return {}

    with path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        dates_by_player: dict[str, set[str]] = {}
        for row in reader:
            player_id = row.get("player_id")
            as_of_date = row.get("as_of_date")
            if player_id and as_of_date:
                dates_by_player.setdefault(player_id, set()).add(as_of_date)
        return dates_by_player


def write_value_history_csv(rows: list[ValueHistoryRow], path: str | Path) -> Path:
    import csv

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "source",
        "captured_at",
        "as_of_date",
        "player_id",
        "player_name",
        "position",
        "team",
        "sf_value",
        "one_qb_value",
    ]
    merged_rows: dict[tuple[str, str], dict[str, str]] = {}

    if path.exists():
        with path.open(newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                key = (row["as_of_date"], row["player_id"])
                merged_rows[key] = {field: row.get(field, "") for field in fieldnames}

    for row in rows:
        merged_rows[(row.as_of_date, row.player_id)] = {
            "source": row.source,
            "captured_at": row.captured_at.isoformat(),
            "as_of_date": row.as_of_date,
            "player_id": row.player_id,
            "player_name": row.player_name,
            "position": row.position,
            "team": row.team or "",
            "sf_value": "" if row.sf_value is None else f"{row.sf_value:g}",
            "one_qb_value": "" if row.one_qb_value is None else f"{row.one_qb_value:g}",
        }

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(
            row
            for _key, row in sorted(
                merged_rows.items(),
                key=lambda item: (item[0][0], item[1]["player_name"], item[0][1]),
            )
        )

    return path


def _fetch_value_history_player_rows(
    player: dict[str, Any],
    *,
    api_key: str,
    captured_at: datetime,
    fetch_json: FetchJson | None,
) -> tuple[str, list[ValueHistoryRow]]:
    player_id = _optional_str(player.get("sleeper_id"))
    if not player_id or str(player.get("position")).upper() == "PICK":
        return "skipped", []

    try:
        payload = (
            fetch_json(_player_page_url(player_id))
            if fetch_json is not None
            else _fetch_json(_player_page_url(player_id), api_key=api_key)
        )
    except HTTPError as error:
        if error.code == 404:
            return "missing", []
        raise

    player_data = payload["player"]
    rows = [
        ValueHistoryRow(
            source=SOURCE_NAME,
            captured_at=captured_at,
            as_of_date=str(history_row["date"]),
            player_id=str(player_data["sleeper_id"]),
            player_name=str(player_data["name"]),
            position=str(player_data["position"]).upper(),
            team=_optional_str(player_data.get("team")),
            sf_value=_optional_float(history_row.get("sf")),
            one_qb_value=_optional_float(history_row.get("one_qb")),
        )
        for history_row in payload.get("value_history", [])
    ]
    return "fetched", rows


def _iter_rankings_players(
    *,
    league_size: int,
    per_page: int,
    max_pages: int | None,
    fetch_json: FetchJson,
) -> list[dict[str, Any]]:
    page = 1
    players: list[dict[str, Any]] = []

    while True:
        payload = fetch_json(
            _rankings_url(page=page, per_page=per_page, league_size=league_size)
        )
        players.extend(payload.get("players", []))

        total_pages = int(payload.get("total_pages") or page)
        if page >= total_pages or (max_pages is not None and page >= max_pages):
            return players
        page += 1


def _rankings_url(*, page: int, per_page: int, league_size: int) -> str:
    query = urlencode(
        {
            "format": "sf",
            "position": "all",
            "sort": "value",
            "league_size": league_size,
            "per_page": per_page,
            "page": page,
        }
    )
    return f"{BASE_URL}/rankings?{query}"


def _player_page_url(player_id: str) -> str:
    return f"{BASE_URL}/player-page/{player_id}"


def _fetch_json(url: str, *, api_key: str | None = None) -> dict[str, Any]:
    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0",
    }
    if api_key:
        headers["X-RA-Key"] = api_key

    request = Request(url, headers=headers)
    for attempt in range(4):
        try:
            with urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            if error.code != 429 or attempt == 3:
                raise

            retry_after = error.headers.get("Retry-After")
            wait_seconds = float(retry_after) if retry_after else 5.0 * (attempt + 1)
            time.sleep(wait_seconds)

    raise RuntimeError("unreachable RosterAudit retry state")


def _superflex_value(player: dict[str, Any]) -> float:
    value = player.get("val_sf_market", player.get("value"))
    if value in (None, ""):
        return 0.0
    return float(value)


def _asset_id(player: dict[str, Any]) -> str:
    sleeper_id = _optional_str(player.get("sleeper_id"))
    if sleeper_id:
        return sleeper_id

    name = str(player["name"]).strip().lower()
    slug = "".join(character if character.isalnum() else "-" for character in name)
    slug = "-".join(part for part in slug.split("-") if part)
    return f"rosteraudit-{slug}"


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _optional_str(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)

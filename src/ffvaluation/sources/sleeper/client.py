from __future__ import annotations

import csv
import json
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen


BASE_URL = "https://api.sleeper.app/v1"

FetchJson = Callable[[str], Any]
DiscoveryProgressCallback = Callable[[int, int, int, int], None]

TRADE_HISTORY_COLUMNS = [
    "captured_at",
    "league_id",
    "league_name",
    "league_season",
    "previous_league_id",
    "round",
    "transaction_id",
    "status",
    "created",
    "created_at",
    "status_updated",
    "status_updated_at",
    "roster_ids",
    "consenter_ids",
    "adds",
    "drops",
    "draft_picks",
    "waiver_budget",
    "total_rosters",
    "is_dynasty",
    "is_superflex",
    "ppr",
    "te_premium",
    "target_format_guess",
    "league_settings",
    "scoring_settings",
    "roster_positions",
]
USER_DISCOVERY_COLUMNS = [
    "captured_at",
    "user_id",
    "username",
    "display_name",
    "avatar",
]
LEAGUE_DISCOVERY_COLUMNS = [
    "captured_at",
    "league_id",
    "league_name",
    "league_season",
    "previous_league_id",
    "total_rosters",
    "is_dynasty",
    "is_superflex",
    "ppr",
    "te_premium",
    "target_format_guess",
    "league_settings",
    "scoring_settings",
    "roster_positions",
]
LEAGUE_USER_DISCOVERY_COLUMNS = [
    "captured_at",
    "league_id",
    "league_season",
    "user_id",
    "display_name",
]
USER_FRONTIER_COLUMNS = [
    "user_id",
    "username",
    "display_name",
    "discovered_at",
    "discovered_from_league_id",
    "expanded_at",
]


@dataclass(frozen=True)
class SleeperTradeRow:
    captured_at: datetime
    league_id: str
    league_name: str
    league_season: str
    previous_league_id: str | None
    round: int
    transaction_id: str
    status: str
    created: int | None
    created_at: datetime | None
    status_updated: int | None
    status_updated_at: datetime | None
    roster_ids: list[int]
    consenter_ids: list[int]
    adds: dict[str, int] | None
    drops: dict[str, int] | None
    draft_picks: list[dict[str, Any]]
    waiver_budget: list[dict[str, Any]]
    total_rosters: int | None
    is_dynasty: bool | None
    is_superflex: bool
    ppr: float | None
    te_premium: float
    target_format_guess: bool
    league_settings: dict[str, Any]
    scoring_settings: dict[str, Any]
    roster_positions: list[str]


@dataclass(frozen=True)
class SleeperUserRow:
    captured_at: datetime
    user_id: str
    username: str
    display_name: str
    avatar: str | None


@dataclass(frozen=True)
class SleeperLeagueRow:
    captured_at: datetime
    league_id: str
    league_name: str
    league_season: str
    previous_league_id: str | None
    total_rosters: int | None
    is_dynasty: bool | None
    is_superflex: bool
    ppr: float | None
    te_premium: float
    target_format_guess: bool
    league_settings: dict[str, Any]
    scoring_settings: dict[str, Any]
    roster_positions: list[str]


@dataclass(frozen=True)
class SleeperLeagueUserRow:
    captured_at: datetime
    league_id: str
    league_season: str
    user_id: str
    display_name: str


@dataclass(frozen=True)
class SleeperDiscoveryResult:
    users: list[SleeperUserRow]
    leagues: list[SleeperLeagueRow]
    league_users: list[SleeperLeagueUserRow]


@dataclass(frozen=True)
class SleeperFrontierRow:
    user_id: str
    username: str
    display_name: str
    discovered_at: datetime
    discovered_from_league_id: str | None
    expanded_at: datetime | None


@dataclass(frozen=True)
class SleeperFrontierExpansionResult:
    users: list[SleeperUserRow]
    leagues: list[SleeperLeagueRow]
    league_users: list[SleeperLeagueUserRow]
    frontier: list[SleeperFrontierRow]
    expanded_users: int


def discover_league_network(
    *,
    seed_user: str,
    seasons: Iterable[str],
    max_depth: int = 5,
    max_users: int | None = None,
    max_leagues: int | None = None,
    captured_at: datetime | None = None,
    sleep_seconds: float = 0.1,
    progress_callback: DiscoveryProgressCallback | None = None,
    fetch_json: FetchJson | None = None,
) -> SleeperDiscoveryResult:
    captured_at = captured_at or datetime.now(UTC)
    fetch_json = fetch_json or _fetch_json
    users_by_id: dict[str, SleeperUserRow] = {}
    leagues_by_id: dict[str, SleeperLeagueRow] = {}
    league_users_by_key: dict[tuple[str, str], SleeperLeagueUserRow] = {}
    queue: list[tuple[str, int]] = [(seed_user, 0)]
    seen_user_ids: set[str] = set()
    seen_user_refs: set[str] = set()
    fetched_league_users: set[str] = set()
    seasons = [str(season) for season in seasons]

    while (
        queue
        and (max_users is None or len(seen_user_ids) < max_users)
        and (max_leagues is None or len(leagues_by_id) < max_leagues)
    ):
        user_ref, depth = queue.pop(0)
        if user_ref in seen_user_refs or user_ref in seen_user_ids:
            continue
        seen_user_refs.add(user_ref)

        user = fetch_json(_user_url(user_ref))
        user_id = str(user["user_id"])
        if user_id in seen_user_ids:
            continue
        seen_user_ids.add(user_id)
        users_by_id[user_id] = _user_row(captured_at=captured_at, user=user)

        for season in seasons:
            leagues = fetch_json(_user_leagues_url(user_id=user_id, season=season))
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)

            for league in leagues:
                league_id = str(league["league_id"])
                leagues_by_id[league_id] = _league_row(captured_at=captured_at, league=league)
                if max_leagues is not None and len(leagues_by_id) >= max_leagues:
                    break

                if league_id in fetched_league_users:
                    continue
                fetched_league_users.add(league_id)
                league_users = fetch_json(_league_users_url(league_id))
                if sleep_seconds > 0:
                    time.sleep(sleep_seconds)

                for league_user in league_users:
                    league_user_id = str(league_user["user_id"])
                    league_users_by_key[(league_id, league_user_id)] = _league_user_row(
                        captured_at=captured_at,
                        league=league,
                        user=league_user,
                    )
                    if (
                        depth < max_depth
                        and (
                            max_users is None
                            or len(seen_user_ids) + len(queue) < max_users
                        )
                    ):
                        queue.append((league_user_id, depth + 1))

            if max_leagues is not None and len(leagues_by_id) >= max_leagues:
                break

        if progress_callback:
            progress_callback(
                len(seen_user_ids),
                len(leagues_by_id),
                len(league_users_by_key),
                len(queue),
            )

    return SleeperDiscoveryResult(
        users=sorted(users_by_id.values(), key=lambda row: row.user_id),
        leagues=sorted(leagues_by_id.values(), key=lambda row: (row.league_season, row.league_id)),
        league_users=sorted(
            league_users_by_key.values(),
            key=lambda row: (row.league_season, row.league_id, row.user_id),
        ),
    )


def seed_user_frontier(
    *,
    seed_user: str,
    path: str | Path,
    captured_at: datetime | None = None,
    fetch_json: FetchJson | None = None,
) -> SleeperFrontierRow:
    captured_at = captured_at or datetime.now(UTC)
    fetch_json = fetch_json or _fetch_json
    user = fetch_json(_user_url(seed_user))
    row = SleeperFrontierRow(
        user_id=str(user["user_id"]),
        username=str(user.get("username") or ""),
        display_name=str(user.get("display_name") or ""),
        discovered_at=captured_at,
        discovered_from_league_id=None,
        expanded_at=None,
    )
    upsert_user_frontier_csv([row], path)
    return row


def expand_user_frontier(
    *,
    frontier_path: str | Path,
    seasons: Iterable[str],
    users_path: str | Path | None = None,
    leagues_path: str | Path | None = None,
    league_users_path: str | Path | None = None,
    max_users: int | None = 1000,
    max_leagues: int | None = None,
    captured_at: datetime | None = None,
    sleep_seconds: float = 0.1,
    progress_callback: DiscoveryProgressCallback | None = None,
    fetch_json: FetchJson | None = None,
) -> SleeperFrontierExpansionResult:
    captured_at = captured_at or datetime.now(UTC)
    fetch_json = fetch_json or _fetch_json
    frontier = read_user_frontier_csv(frontier_path)
    frontier_by_id = {row.user_id: row for row in frontier}
    users_by_id: dict[str, SleeperUserRow] = {}
    leagues_by_id: dict[str, SleeperLeagueRow] = {}
    league_users_by_key: dict[tuple[str, str], SleeperLeagueUserRow] = {}
    expanded_users = 0
    seasons = [str(season) for season in seasons]

    for frontier_row in sorted(
        frontier_by_id.values(),
        key=lambda row: (row.expanded_at is not None, row.discovered_at, row.user_id),
    ):
        if frontier_row.expanded_at is not None:
            continue
        if max_users is not None and expanded_users >= max_users:
            break
        if max_leagues is not None and len(leagues_by_id) >= max_leagues:
            break

        user_id = frontier_row.user_id
        batch_users: list[SleeperUserRow] = []
        batch_leagues: list[SleeperLeagueRow] = []
        batch_league_users: list[SleeperLeagueUserRow] = []
        users_by_id[user_id] = SleeperUserRow(
            captured_at=captured_at,
            user_id=user_id,
            username=frontier_row.username,
            display_name=frontier_row.display_name,
            avatar=None,
        )
        batch_users.append(users_by_id[user_id])

        for season in seasons:
            leagues = fetch_json(_user_leagues_url(user_id=user_id, season=season))
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)

            for league in leagues:
                league_id = str(league["league_id"])
                league_row = _league_row(captured_at=captured_at, league=league)
                leagues_by_id[league_id] = league_row
                batch_leagues.append(league_row)
                if max_leagues is not None and len(leagues_by_id) >= max_leagues:
                    break

                league_users = fetch_json(_league_users_url(league_id))
                if sleep_seconds > 0:
                    time.sleep(sleep_seconds)

                for league_user in league_users:
                    league_user_id = str(league_user["user_id"])
                    league_user_row = _league_user_row(
                        captured_at=captured_at,
                        league=league,
                        user=league_user,
                    )
                    league_users_by_key[(league_id, league_user_id)] = league_user_row
                    batch_league_users.append(league_user_row)
                    user_row = _user_row(
                        captured_at=captured_at,
                        user=league_user,
                    )
                    users_by_id[league_user_id] = user_row
                    batch_users.append(user_row)
                    if league_user_id not in frontier_by_id:
                        frontier_by_id[league_user_id] = SleeperFrontierRow(
                            user_id=league_user_id,
                            username=str(league_user.get("username") or ""),
                            display_name=str(league_user.get("display_name") or ""),
                            discovered_at=captured_at,
                            discovered_from_league_id=league_id,
                            expanded_at=None,
                        )

            if max_leagues is not None and len(leagues_by_id) >= max_leagues:
                break

        frontier_by_id[user_id] = SleeperFrontierRow(
            user_id=frontier_row.user_id,
            username=frontier_row.username,
            display_name=frontier_row.display_name,
            discovered_at=frontier_row.discovered_at,
            discovered_from_league_id=frontier_row.discovered_from_league_id,
            expanded_at=captured_at,
        )
        expanded_users += 1
        frontier_rows = _sort_frontier_rows(frontier_by_id.values())

        if users_path is not None:
            upsert_user_discovery_csv(batch_users, users_path)
        if leagues_path is not None:
            upsert_league_discovery_csv(batch_leagues, leagues_path)
        if league_users_path is not None:
            upsert_league_user_discovery_csv(batch_league_users, league_users_path)
        upsert_user_frontier_csv(frontier_rows, frontier_path)

        if progress_callback:
            progress_callback(
                expanded_users,
                len(leagues_by_id),
                len(league_users_by_key),
                sum(1 for row in frontier_by_id.values() if row.expanded_at is None),
            )

    frontier_rows = _sort_frontier_rows(frontier_by_id.values())
    upsert_user_frontier_csv(frontier_rows, frontier_path)
    return SleeperFrontierExpansionResult(
        users=sorted(users_by_id.values(), key=lambda row: row.user_id),
        leagues=sorted(leagues_by_id.values(), key=lambda row: (row.league_season, row.league_id)),
        league_users=sorted(
            league_users_by_key.values(),
            key=lambda row: (row.league_season, row.league_id, row.user_id),
        ),
        frontier=frontier_rows,
        expanded_users=expanded_users,
    )


def read_user_frontier_csv(path: str | Path) -> list[SleeperFrontierRow]:
    path = Path(path)
    if not path.exists():
        return []

    with path.open(newline="", encoding="utf-8") as file:
        return [_parse_frontier_row(row) for row in csv.DictReader(file)]


def upsert_user_frontier_csv(rows: list[SleeperFrontierRow], path: str | Path) -> Path:
    return _upsert_csv(
        rows=(_format_frontier_row(row) for row in rows),
        path=path,
        fieldnames=USER_FRONTIER_COLUMNS,
        key_fields=("user_id",),
        sort_fields=("expanded_at", "discovered_at", "user_id"),
    )


def _sort_frontier_rows(rows: Iterable[SleeperFrontierRow]) -> list[SleeperFrontierRow]:
    return sorted(
        rows,
        key=lambda row: (
            row.expanded_at is not None,
            row.expanded_at or datetime.max.replace(tzinfo=UTC),
            row.discovered_at,
            row.user_id,
        ),
    )


def upsert_user_discovery_csv(rows: list[SleeperUserRow], path: str | Path) -> Path:
    return _upsert_csv(
        rows=(_format_user_row(row) for row in rows),
        path=path,
        fieldnames=USER_DISCOVERY_COLUMNS,
        key_fields=("user_id",),
        sort_fields=("user_id",),
    )


def upsert_league_discovery_csv(rows: list[SleeperLeagueRow], path: str | Path) -> Path:
    return _upsert_csv(
        rows=(_format_league_row(row) for row in rows),
        path=path,
        fieldnames=LEAGUE_DISCOVERY_COLUMNS,
        key_fields=("league_id",),
        sort_fields=("league_season", "league_id"),
    )


def upsert_league_user_discovery_csv(
    rows: list[SleeperLeagueUserRow],
    path: str | Path,
) -> Path:
    return _upsert_csv(
        rows=(_format_league_user_row(row) for row in rows),
        path=path,
        fieldnames=LEAGUE_USER_DISCOVERY_COLUMNS,
        key_fields=("league_id", "user_id"),
        sort_fields=("league_season", "league_id", "user_id"),
    )


def fetch_trade_history(
    *,
    league_id: str,
    days: int = 365,
    rounds: Iterable[int] = range(1, 19),
    follow_previous: bool = True,
    max_leagues: int | None = None,
    captured_at: datetime | None = None,
    sleep_seconds: float = 0.1,
    fetch_json: FetchJson | None = None,
) -> list[SleeperTradeRow]:
    captured_at = captured_at or datetime.now(UTC)
    since = captured_at - timedelta(days=days)
    fetch_json = fetch_json or _fetch_json
    rows: list[SleeperTradeRow] = []

    for league in _iter_league_chain(
        league_id=league_id,
        follow_previous=follow_previous,
        max_leagues=max_leagues,
        fetch_json=fetch_json,
    ):
        for round_number in rounds:
            transactions = fetch_json(_transactions_url(str(league["league_id"]), round_number))
            for transaction in transactions:
                if transaction.get("type") != "trade" or transaction.get("status") != "complete":
                    continue

                created_at = _millis_to_datetime(transaction.get("created"))
                status_updated_at = _millis_to_datetime(transaction.get("status_updated"))
                trade_time = created_at or status_updated_at
                if trade_time is not None and trade_time < since:
                    continue

                rows.append(
                    _trade_row(
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


def write_trade_history_csv(rows: list[SleeperTradeRow], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=TRADE_HISTORY_COLUMNS)
        writer.writeheader()
        writer.writerows(_format_trade_row(row) for row in rows)

    return path


def upsert_trade_history_csv(rows: list[SleeperTradeRow], path: str | Path) -> Path:
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
        formatted = _format_trade_row(row)
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


def _upsert_csv(
    *,
    rows: Iterable[dict[str, str]],
    path: str | Path,
    fieldnames: list[str],
    key_fields: tuple[str, ...],
    sort_fields: tuple[str, ...],
) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    merged_rows: dict[tuple[str, ...], dict[str, str]] = {}

    if path.exists():
        with path.open(newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                key = tuple(row.get(field, "") for field in key_fields)
                if all(key):
                    merged_rows[key] = {field: row.get(field, "") for field in fieldnames}

    for row in rows:
        key = tuple(row[field] for field in key_fields)
        merged_rows[key] = {field: row.get(field, "") for field in fieldnames}

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(
            row
            for _key, row in sorted(
                merged_rows.items(),
                key=lambda item: tuple(item[1][field] for field in sort_fields),
            )
        )

    return path


def _iter_league_chain(
    *,
    league_id: str,
    follow_previous: bool,
    max_leagues: int | None,
    fetch_json: FetchJson,
) -> Iterable[dict[str, Any]]:
    current_league_id: str | None = league_id
    seen: set[str] = set()
    league_count = 0

    while current_league_id:
        if current_league_id in seen:
            return
        if max_leagues is not None and league_count >= max_leagues:
            return

        league = fetch_json(_league_url(current_league_id))
        seen.add(current_league_id)
        league_count += 1
        yield league

        current_league_id = str(league.get("previous_league_id") or "") or None
        if not follow_previous:
            return


def _trade_row(
    *,
    captured_at: datetime,
    league: dict[str, Any],
    round_number: int,
    transaction: dict[str, Any],
) -> SleeperTradeRow:
    scoring_settings = league.get("scoring_settings") or {}
    league_settings = league.get("settings") or {}
    roster_positions = [str(position) for position in league.get("roster_positions") or []]
    ppr = _optional_float(scoring_settings.get("rec"))
    te_premium = _te_premium(scoring_settings, ppr)
    is_superflex = "SUPER_FLEX" in roster_positions
    total_rosters = _optional_int(league.get("total_rosters"))
    is_dynasty = _is_dynasty(league)

    return SleeperTradeRow(
        captured_at=captured_at,
        league_id=str(league["league_id"]),
        league_name=str(league.get("name") or ""),
        league_season=str(league.get("season") or ""),
        previous_league_id=_optional_str(league.get("previous_league_id")),
        round=round_number,
        transaction_id=str(transaction["transaction_id"]),
        status=str(transaction.get("status") or ""),
        created=_optional_int(transaction.get("created")),
        created_at=_millis_to_datetime(transaction.get("created")),
        status_updated=_optional_int(transaction.get("status_updated")),
        status_updated_at=_millis_to_datetime(transaction.get("status_updated")),
        roster_ids=[int(roster_id) for roster_id in transaction.get("roster_ids") or []],
        consenter_ids=[int(roster_id) for roster_id in transaction.get("consenter_ids") or []],
        adds=transaction.get("adds"),
        drops=transaction.get("drops"),
        draft_picks=transaction.get("draft_picks") or [],
        waiver_budget=transaction.get("waiver_budget") or [],
        total_rosters=total_rosters,
        is_dynasty=is_dynasty,
        is_superflex=is_superflex,
        ppr=ppr,
        te_premium=te_premium,
        target_format_guess=(
            total_rosters == 12
            and is_dynasty is True
            and is_superflex
            and ppr == 1.0
            and te_premium == 0.0
        ),
        league_settings=league_settings,
        scoring_settings=scoring_settings,
        roster_positions=roster_positions,
    )


def _user_row(*, captured_at: datetime, user: dict[str, Any]) -> SleeperUserRow:
    return SleeperUserRow(
        captured_at=captured_at,
        user_id=str(user["user_id"]),
        username=str(user.get("username") or ""),
        display_name=str(user.get("display_name") or ""),
        avatar=_optional_str(user.get("avatar")),
    )


def _league_row(*, captured_at: datetime, league: dict[str, Any]) -> SleeperLeagueRow:
    scoring_settings = league.get("scoring_settings") or {}
    league_settings = league.get("settings") or {}
    roster_positions = [str(position) for position in league.get("roster_positions") or []]
    ppr = _optional_float(scoring_settings.get("rec"))
    te_premium = _te_premium(scoring_settings, ppr)
    is_superflex = "SUPER_FLEX" in roster_positions
    total_rosters = _optional_int(league.get("total_rosters"))
    is_dynasty = _is_dynasty(league)

    return SleeperLeagueRow(
        captured_at=captured_at,
        league_id=str(league["league_id"]),
        league_name=str(league.get("name") or ""),
        league_season=str(league.get("season") or ""),
        previous_league_id=_optional_str(league.get("previous_league_id")),
        total_rosters=total_rosters,
        is_dynasty=is_dynasty,
        is_superflex=is_superflex,
        ppr=ppr,
        te_premium=te_premium,
        target_format_guess=(
            total_rosters == 12
            and is_dynasty is True
            and is_superflex
            and ppr == 1.0
            and te_premium == 0.0
        ),
        league_settings=league_settings,
        scoring_settings=scoring_settings,
        roster_positions=roster_positions,
    )


def _league_user_row(
    *,
    captured_at: datetime,
    league: dict[str, Any],
    user: dict[str, Any],
) -> SleeperLeagueUserRow:
    return SleeperLeagueUserRow(
        captured_at=captured_at,
        league_id=str(league["league_id"]),
        league_season=str(league.get("season") or ""),
        user_id=str(user["user_id"]),
        display_name=str(user.get("display_name") or ""),
    )


def _format_user_row(row: SleeperUserRow) -> dict[str, str]:
    return {
        "captured_at": row.captured_at.isoformat(),
        "user_id": row.user_id,
        "username": row.username,
        "display_name": row.display_name,
        "avatar": row.avatar or "",
    }


def _format_league_row(row: SleeperLeagueRow) -> dict[str, str]:
    return {
        "captured_at": row.captured_at.isoformat(),
        "league_id": row.league_id,
        "league_name": row.league_name,
        "league_season": row.league_season,
        "previous_league_id": row.previous_league_id or "",
        "total_rosters": "" if row.total_rosters is None else str(row.total_rosters),
        "is_dynasty": _optional_bool(row.is_dynasty),
        "is_superflex": str(row.is_superflex).lower(),
        "ppr": "" if row.ppr is None else f"{row.ppr:g}",
        "te_premium": f"{row.te_premium:g}",
        "target_format_guess": str(row.target_format_guess).lower(),
        "league_settings": _json(row.league_settings),
        "scoring_settings": _json(row.scoring_settings),
        "roster_positions": _json(row.roster_positions),
    }


def _format_league_user_row(row: SleeperLeagueUserRow) -> dict[str, str]:
    return {
        "captured_at": row.captured_at.isoformat(),
        "league_id": row.league_id,
        "league_season": row.league_season,
        "user_id": row.user_id,
        "display_name": row.display_name,
    }


def _format_frontier_row(row: SleeperFrontierRow) -> dict[str, str]:
    return {
        "user_id": row.user_id,
        "username": row.username,
        "display_name": row.display_name,
        "discovered_at": row.discovered_at.isoformat(),
        "discovered_from_league_id": row.discovered_from_league_id or "",
        "expanded_at": "" if row.expanded_at is None else row.expanded_at.isoformat(),
    }


def _parse_frontier_row(row: dict[str, str]) -> SleeperFrontierRow:
    expanded_at = row.get("expanded_at", "").strip()
    return SleeperFrontierRow(
        user_id=row["user_id"],
        username=row.get("username", ""),
        display_name=row.get("display_name", ""),
        discovered_at=datetime.fromisoformat(row["discovered_at"]),
        discovered_from_league_id=row.get("discovered_from_league_id") or None,
        expanded_at=datetime.fromisoformat(expanded_at) if expanded_at else None,
    )


def _format_trade_row(row: SleeperTradeRow) -> dict[str, str]:
    return {
        "captured_at": row.captured_at.isoformat(),
        "league_id": row.league_id,
        "league_name": row.league_name,
        "league_season": row.league_season,
        "previous_league_id": row.previous_league_id or "",
        "round": str(row.round),
        "transaction_id": row.transaction_id,
        "status": row.status,
        "created": "" if row.created is None else str(row.created),
        "created_at": "" if row.created_at is None else row.created_at.isoformat(),
        "status_updated": "" if row.status_updated is None else str(row.status_updated),
        "status_updated_at": ""
        if row.status_updated_at is None
        else row.status_updated_at.isoformat(),
        "roster_ids": _json(row.roster_ids),
        "consenter_ids": _json(row.consenter_ids),
        "adds": _json(row.adds),
        "drops": _json(row.drops),
        "draft_picks": _json(row.draft_picks),
        "waiver_budget": _json(row.waiver_budget),
        "total_rosters": "" if row.total_rosters is None else str(row.total_rosters),
        "is_dynasty": _optional_bool(row.is_dynasty),
        "is_superflex": str(row.is_superflex).lower(),
        "ppr": "" if row.ppr is None else f"{row.ppr:g}",
        "te_premium": f"{row.te_premium:g}",
        "target_format_guess": str(row.target_format_guess).lower(),
        "league_settings": _json(row.league_settings),
        "scoring_settings": _json(row.scoring_settings),
        "roster_positions": _json(row.roster_positions),
    }


def _league_url(league_id: str) -> str:
    return f"{BASE_URL}/league/{league_id}"


def _user_url(user_ref: str) -> str:
    return f"{BASE_URL}/user/{user_ref}"


def _user_leagues_url(*, user_id: str, season: str) -> str:
    return f"{BASE_URL}/user/{user_id}/leagues/nfl/{season}"


def _league_users_url(league_id: str) -> str:
    return f"{BASE_URL}/league/{league_id}/users"


def _transactions_url(league_id: str, round_number: int) -> str:
    return f"{BASE_URL}/league/{league_id}/transactions/{round_number}"


def _fetch_json(url: str) -> Any:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0",
        },
    )
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _millis_to_datetime(value: Any) -> datetime | None:
    timestamp = _optional_int(value)
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp / 1000, tz=UTC)


def _is_dynasty(league: dict[str, Any]) -> bool | None:
    settings = league.get("settings") or {}
    metadata = league.get("metadata") or {}
    if "type" in settings:
        return int(settings["type"]) == 2

    league_name = str(league.get("name") or "").lower()
    description = str(metadata.get("description") or "").lower()
    if "dynasty" in league_name or "dynasty" in description:
        return True
    return None


def _te_premium(scoring_settings: dict[str, Any], ppr: float | None) -> float:
    if "bonus_rec_te" in scoring_settings:
        return _optional_float(scoring_settings["bonus_rec_te"]) or 0.0
    if "rec_te" in scoring_settings and ppr is not None:
        return max(0.0, (_optional_float(scoring_settings["rec_te"]) or ppr) - ppr)
    return 0.0


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _optional_bool(value: bool | None) -> str:
    if value is None:
        return ""
    return str(value).lower()


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _optional_str(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)

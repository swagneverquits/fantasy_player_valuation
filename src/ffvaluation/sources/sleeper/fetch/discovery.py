from __future__ import annotations

import sqlite3
import time
from collections import Counter
from collections.abc import Iterable
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any

from ffvaluation.sources.sleeper.common import (
    DiscoveryProgressCallback,
    FetchJson,
    fetch_json as default_fetch_json,
    is_dynasty,
    league_users_url,
    optional_bool,
    optional_float,
    optional_int,
    optional_str,
    te_premium,
    user_id,
    user_leagues_url,
    user_url,
)
from ffvaluation.sources.sleeper.models import (
    LEAGUE_DISCOVERY_COLUMNS,
    LEAGUE_SETTING_KEYS,
    LEAGUE_USER_DISCOVERY_COLUMNS,
    ROSTER_POSITION_KEYS,
    SCORING_SETTING_KEYS,
    USER_DISCOVERY_COLUMNS,
    USER_FRONTIER_COLUMNS,
    SleeperFrontierExpansionResult,
    SleeperFrontierRow,
    SleeperLeagueRow,
    SleeperLeagueUserRow,
    SleeperUserRow,
)


def seed_user_frontier(
    *,
    seed_user: str,
    db_path: str | Path,
    captured_at: datetime | None = None,
    fetch_json: FetchJson | None = None,
) -> SleeperFrontierRow:
    """Add a Sleeper user to the SQLite discovery frontier."""
    captured_at = captured_at or datetime.now(UTC)
    fetch_json = fetch_json or default_fetch_json
    user = fetch_json(user_url(seed_user))
    row = SleeperFrontierRow(
        user_id=str(user["user_id"]),
        username=str(user.get("username") or ""),
        display_name=str(user.get("display_name") or ""),
        discovered_at=captured_at,
        discovered_from_league_id=None,
        expanded_at=None,
    )
    store = SleeperDiscoveryStore(db_path)
    store.upsert_discovery(
        users=[user_row(captured_at=captured_at, user=user)],
        leagues=[],
        league_users=[],
        frontier=[row],
    )
    store.close()
    return row


def expand_user_frontier_sqlite(
    *,
    db_path: str | Path,
    seasons: Iterable[str],
    max_users: int | None,
    captured_at: datetime | None = None,
    flush_every: int = 25,
    workers: int = 1,
    requests_per_minute: int = 500,
    frontier_order: str = "oldest",
    progress_callback: DiscoveryProgressCallback | None = None,
    timing_collector: DiscoveryTiming | None = None,
    fetch_json: FetchJson | None = None,
) -> SleeperFrontierExpansionResult:
    """Expand unprocessed Sleeper frontier users into leagues and league-user edges."""
    captured_at = captured_at or datetime.now(UTC)
    fetch_json = fetch_json or default_fetch_json
    if timing_collector is not None:
        fetch_json = instrument_fetch_json(fetch_json, timing_collector)

    store = SleeperDiscoveryStore(db_path)
    work_rows = store.read_unexpanded_frontier(limit=max_users, frontier_order=frontier_order)
    frontier_by_id = {row.user_id: row for row in work_rows}

    users_by_id: dict[str, SleeperUserRow] = {}
    leagues_by_id: dict[str, SleeperLeagueRow] = {}
    league_users_by_key: dict[tuple[str, str], SleeperLeagueUserRow] = {}
    league_users_fetched = store.read_league_user_ids()
    existing_league_ids = store.read_league_ids()
    existing_frontier_ids = store.read_frontier_ids()
    new_league_ids: set[str] = set()
    league_users_fetched_lock = Lock()
    throttle = RequestThrottle(requests_per_minute, timing_collector=timing_collector)
    seasons = [str(season) for season in seasons]
    flush_every = max(flush_every, 1)
    workers = max(workers, 1)
    pending_users: list[SleeperUserRow] = []
    pending_leagues: list[SleeperLeagueRow] = []
    pending_league_users: list[SleeperLeagueUserRow] = []
    pending_frontier_by_id: dict[str, SleeperFrontierRow] = {}
    unexpanded_frontier_count = store.count_unexpanded_frontier()
    expanded_users = 0

    def throttled_fetch_json(url: str) -> Any:
        """Fetch JSON through the shared request throttle."""
        throttle.acquire()
        return fetch_json(url)

    def merge_result(result: FrontierUserFetchResult) -> None:
        """Merge one fetched frontier user into pending in-memory state."""
        nonlocal expanded_users, unexpanded_frontier_count
        for user in result.users:
            users_by_id[user.user_id] = user
        for league in result.leagues:
            leagues_by_id[league.league_id] = league
            if league.league_id not in existing_league_ids:
                new_league_ids.add(league.league_id)
        for league_user in result.league_users:
            league_users_by_key[(league_user.league_id, league_user.user_id)] = league_user
        for frontier_row in result.discovered_frontier:
            if frontier_row.user_id not in existing_frontier_ids:
                existing_frontier_ids.add(frontier_row.user_id)
                frontier_by_id[frontier_row.user_id] = frontier_row
                pending_frontier_by_id[frontier_row.user_id] = frontier_row
                unexpanded_frontier_count += 1
        expanded_frontier_row = SleeperFrontierRow(
            user_id=result.frontier_row.user_id,
            username=result.frontier_row.username,
            display_name=result.frontier_row.display_name,
            discovered_at=result.frontier_row.discovered_at,
            discovered_from_league_id=result.frontier_row.discovered_from_league_id,
            expanded_at=captured_at,
        )
        if frontier_by_id[result.frontier_row.user_id].expanded_at is None:
            unexpanded_frontier_count -= 1
        frontier_by_id[result.frontier_row.user_id] = expanded_frontier_row
        pending_frontier_by_id[result.frontier_row.user_id] = expanded_frontier_row
        expanded_users += 1
        pending_users.extend(result.users)
        pending_leagues.extend(result.leagues)
        pending_league_users.extend(result.league_users)

    def flush_pending() -> None:
        """Persist pending discovery rows to SQLite."""
        nonlocal pending_users, pending_leagues, pending_league_users, pending_frontier_by_id
        start = time.perf_counter()
        try:
            store.upsert_discovery(
                users=pending_users,
                leagues=pending_leagues,
                league_users=pending_league_users,
                frontier=sort_frontier_rows(pending_frontier_by_id.values()),
            )
        finally:
            if timing_collector is not None:
                timing_collector.record_flush(time.perf_counter() - start)
        pending_users = []
        pending_leagues = []
        pending_league_users = []
        pending_frontier_by_id = {}

    work_iter = iter(work_rows)
    futures: set[Future[FrontierUserFetchResult]] = set()
    executor = ThreadPoolExecutor(max_workers=workers)
    interrupted = False

    def submit_until_full() -> None:
        """Submit frontier fetch jobs until the worker pool is full."""
        while len(futures) < workers:
            try:
                row = next(work_iter)
            except StopIteration:
                return
            futures.add(
                executor.submit(
                    fetch_frontier_user,
                    frontier_row=row,
                    seasons=seasons,
                    captured_at=captured_at,
                    fetch_json=throttled_fetch_json,
                    league_users_fetched=league_users_fetched,
                    league_users_fetched_lock=league_users_fetched_lock,
                )
            )

    try:
        submit_until_full()
        while futures:
            done, futures = wait(futures, timeout=0.5, return_when=FIRST_COMPLETED)
            if not done:
                continue
            for future in done:
                merge_result(future.result())
                if expanded_users % flush_every == 0:
                    flush_pending()
                if progress_callback:
                    progress_callback(
                        expanded_users,
                        len(leagues_by_id),
                        len(new_league_ids),
                        len(league_users_by_key),
                        unexpanded_frontier_count,
                    )
            submit_until_full()
    except KeyboardInterrupt:
        interrupted = True
        for future in futures:
            future.cancel()
        raise
    finally:
        executor.shutdown(wait=not interrupted, cancel_futures=interrupted)
        flush_pending()
        store.close()

    return SleeperFrontierExpansionResult(
        users=sorted(users_by_id.values(), key=lambda row: row.user_id),
        leagues=sorted(leagues_by_id.values(), key=lambda row: (row.league_season, row.league_id)),
        league_users=sorted(
            league_users_by_key.values(),
            key=lambda row: (row.league_season, row.league_id, row.user_id),
        ),
        expanded_users=expanded_users,
        remaining_frontier=unexpanded_frontier_count,
    )


@dataclass(frozen=True)
class FrontierUserFetchResult:
    frontier_row: SleeperFrontierRow
    users: list[SleeperUserRow]
    leagues: list[SleeperLeagueRow]
    league_users: list[SleeperLeagueUserRow]
    discovered_frontier: list[SleeperFrontierRow]


def fetch_frontier_user(
    *,
    frontier_row: SleeperFrontierRow,
    seasons: Iterable[str],
    captured_at: datetime,
    fetch_json: FetchJson,
    league_users_fetched: set[str],
    league_users_fetched_lock: Lock,
) -> FrontierUserFetchResult:
    """Fetch leagues and leaguemates for one frontier user."""
    users: dict[str, SleeperUserRow] = {
        frontier_row.user_id: SleeperUserRow(
            captured_at=captured_at,
            user_id=frontier_row.user_id,
            username=frontier_row.username,
            display_name=frontier_row.display_name,
        )
    }
    leagues_by_id: dict[str, SleeperLeagueRow] = {}
    league_users_by_key: dict[tuple[str, str], SleeperLeagueUserRow] = {}
    discovered_frontier_by_id: dict[str, SleeperFrontierRow] = {}

    for season in seasons:
        leagues = fetch_json(user_leagues_url(user_id=frontier_row.user_id, season=str(season)))
        for league in leagues:
            league_id = str(league["league_id"])
            parsed_league = league_row(captured_at=captured_at, league=league)
            leagues_by_id[league_id] = parsed_league

            with league_users_fetched_lock:
                if league_id in league_users_fetched:
                    should_fetch_league_users = False
                else:
                    league_users_fetched.add(league_id)
                    should_fetch_league_users = True
            if not should_fetch_league_users:
                continue

            league_users = fetch_json(league_users_url(league_id))
            for league_user in league_users:
                league_user_id = user_id(league_user)
                if not league_user_id:
                    continue
                parsed_league_user = league_user_row(
                    captured_at=captured_at,
                    league=league,
                    user=league_user,
                )
                league_users_by_key[(league_id, league_user_id)] = parsed_league_user
                users[league_user_id] = user_row(captured_at=captured_at, user=league_user)
                if league_user_id != frontier_row.user_id:
                    discovered_frontier_by_id[league_user_id] = SleeperFrontierRow(
                        user_id=league_user_id,
                        username=str(league_user.get("username") or ""),
                        display_name=str(league_user.get("display_name") or ""),
                        discovered_at=captured_at,
                        discovered_from_league_id=league_id,
                        expanded_at=None,
                    )

    return FrontierUserFetchResult(
        frontier_row=frontier_row,
        users=sorted(users.values(), key=lambda row: row.user_id),
        leagues=sorted(leagues_by_id.values(), key=lambda row: (row.league_season, row.league_id)),
        league_users=sorted(
            league_users_by_key.values(),
            key=lambda row: (row.league_season, row.league_id, row.user_id),
        ),
        discovered_frontier=sorted(
            discovered_frontier_by_id.values(),
            key=lambda row: (row.discovered_at, row.user_id),
        ),
    )


class RequestThrottle:
    def __init__(
        self,
        requests_per_minute: int,
        timing_collector: DiscoveryTiming | None = None,
    ) -> None:
        """Create a thread-safe fixed-interval request throttle."""
        self._spacing_seconds = 60 / max(requests_per_minute, 1)
        self._lock = Lock()
        self._next_request_at = 0.0
        self._timing_collector = timing_collector

    def acquire(self) -> None:
        """Wait until the next request is allowed."""
        with self._lock:
            now = time.monotonic()
            wait_seconds = max(0.0, self._next_request_at - now)
            self._next_request_at = max(now, self._next_request_at) + self._spacing_seconds
        if wait_seconds > 0:
            if self._timing_collector is not None:
                self._timing_collector.record_throttle_wait(wait_seconds)
            time.sleep(wait_seconds)


@dataclass(frozen=True)
class DiscoveryTimingSnapshot:
    elapsed_seconds: float
    request_count: int
    request_seconds: float
    throttle_wait_seconds: float
    flush_count: int
    flush_seconds: float
    retry_count: int
    retry_wait_seconds: float
    retry_reasons: dict[str, int]


class DiscoveryTiming:
    def __init__(self) -> None:
        """Start a thread-safe discovery timing collector."""
        self._started_at = time.perf_counter()
        self._lock = Lock()
        self._request_count = 0
        self._request_seconds = 0.0
        self._throttle_wait_seconds = 0.0
        self._flush_count = 0
        self._flush_seconds = 0.0
        self._retry_count = 0
        self._retry_wait_seconds = 0.0
        self._retry_reasons: Counter[str] = Counter()

    def record_request(self, seconds: float) -> None:
        """Record elapsed time for one HTTP request."""
        with self._lock:
            self._request_count += 1
            self._request_seconds += seconds

    def record_throttle_wait(self, seconds: float) -> None:
        """Record time spent waiting on the request throttle."""
        with self._lock:
            self._throttle_wait_seconds += seconds

    def record_flush(self, seconds: float) -> None:
        """Record elapsed time for one SQLite flush."""
        with self._lock:
            self._flush_count += 1
            self._flush_seconds += seconds

    def record_retry(self, reason: str, wait_seconds: float) -> None:
        """Record a retry reason and its backoff wait."""
        with self._lock:
            self._retry_count += 1
            self._retry_wait_seconds += wait_seconds
            self._retry_reasons[reason] += 1

    def snapshot(self) -> DiscoveryTimingSnapshot:
        """Return a consistent snapshot of timing counters."""
        with self._lock:
            return DiscoveryTimingSnapshot(
                elapsed_seconds=time.perf_counter() - self._started_at,
                request_count=self._request_count,
                request_seconds=self._request_seconds,
                throttle_wait_seconds=self._throttle_wait_seconds,
                flush_count=self._flush_count,
                flush_seconds=self._flush_seconds,
                retry_count=self._retry_count,
                retry_wait_seconds=self._retry_wait_seconds,
                retry_reasons=dict(self._retry_reasons),
            )


def instrument_fetch_json(fetch_json: FetchJson, timing_collector: DiscoveryTiming) -> FetchJson:
    """Wrap a JSON fetcher with request timing and retry telemetry."""
    def fetch(url: str) -> Any:
        """Fetch one URL and record elapsed request time."""
        start = time.perf_counter()
        try:
            if fetch_json is default_fetch_json:
                return default_fetch_json(url, retry_callback=timing_collector.record_retry)
            return fetch_json(url)
        finally:
            timing_collector.record_request(time.perf_counter() - start)

    return fetch


def sort_frontier_rows(rows: Iterable[SleeperFrontierRow]) -> list[SleeperFrontierRow]:
    """Sort frontier rows with unexpanded users first."""
    return sorted(
        rows,
        key=lambda row: (
            row.expanded_at is not None,
            row.expanded_at or datetime.max.replace(tzinfo=UTC),
            row.discovered_at,
            row.user_id,
        ),
    )


def user_row(*, captured_at: datetime, user: dict[str, Any]) -> SleeperUserRow:
    """Parse a Sleeper user payload into a discovery user row."""
    resolved_user_id = user_id(user)
    if not resolved_user_id:
        raise ValueError(f"Sleeper user payload is missing user_id: {user!r}")

    return SleeperUserRow(
        captured_at=captured_at,
        user_id=resolved_user_id,
        username=str(user.get("username") or ""),
        display_name=str(user.get("display_name") or ""),
    )


def league_row(*, captured_at: datetime, league: dict[str, Any]) -> SleeperLeagueRow:
    """Parse a Sleeper league payload into a discovery league row."""
    scoring_settings = league.get("scoring_settings") or {}
    league_settings = league.get("settings") or {}
    roster_positions = [str(position) for position in league.get("roster_positions") or []]
    ppr = optional_float(scoring_settings.get("rec"))
    premium = te_premium(scoring_settings, ppr)
    is_superflex = "SUPER_FLEX" in roster_positions
    total_rosters = optional_int(league.get("total_rosters"))
    dynasty = is_dynasty(league)

    return SleeperLeagueRow(
        captured_at=captured_at,
        league_id=str(league["league_id"]),
        league_name=str(league.get("name") or ""),
        league_season=str(league.get("season") or ""),
        previous_league_id=optional_str(league.get("previous_league_id")),
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


def league_user_row(
    *,
    captured_at: datetime,
    league: dict[str, Any],
    user: dict[str, Any],
) -> SleeperLeagueUserRow:
    """Parse one league-user membership edge."""
    return SleeperLeagueUserRow(
        captured_at=captured_at,
        league_id=str(league["league_id"]),
        league_season=str(league.get("season") or ""),
        user_id=user_id(user) or "",
    )


def format_user_row(row: SleeperUserRow) -> dict[str, Any]:
    """Format a discovery user row for SQLite upsert."""
    return {
        "captured_date": row.captured_at.date().isoformat(),
        "user_id": row.user_id,
        "display_name": row.display_name,
    }


def format_league_row(row: SleeperLeagueRow) -> dict[str, Any]:
    """Format a discovery league row for SQLite upsert."""
    position_counts = Counter(row.roster_positions)
    formatted: dict[str, Any] = {
        "captured_date": row.captured_at.date().isoformat(),
        "league_id": row.league_id,
        "league_name": row.league_name,
        "league_season": row.league_season,
        "previous_league_id": row.previous_league_id or "",
        "total_rosters": row.total_rosters,
        "is_dynasty": optional_bool(row.is_dynasty),
        "is_superflex": row.is_superflex,
        "ppr": row.ppr,
        "te_premium": row.te_premium,
        "target_format_guess": row.target_format_guess,
    }
    formatted.update(
        {f"league_setting_{key}": row.league_settings.get(key) for key in LEAGUE_SETTING_KEYS}
    )
    formatted.update(
        {f"scoring_{key}": row.scoring_settings.get(key) for key in SCORING_SETTING_KEYS}
    )
    formatted.update({f"roster_{key}": position_counts.get(key, 0) for key in ROSTER_POSITION_KEYS})
    return formatted


def format_league_user_row(row: SleeperLeagueUserRow) -> dict[str, Any]:
    """Format a league-user edge row for SQLite upsert."""
    return {
        "captured_date": row.captured_at.date().isoformat(),
        "league_id": row.league_id,
        "league_season": row.league_season,
        "user_id": row.user_id,
    }


def format_frontier_row(row: SleeperFrontierRow) -> dict[str, Any]:
    """Format a frontier row for SQLite upsert."""
    return {
        "user_id": row.user_id,
        "username": row.username,
        "display_name": row.display_name,
        "discovered_at": row.discovered_at.isoformat(),
        "discovered_from_league_id": row.discovered_from_league_id or "",
        "expanded_at": "" if row.expanded_at is None else row.expanded_at.isoformat(),
    }


def parse_frontier_row(row: dict[str, Any]) -> SleeperFrontierRow:
    """Parse a SQLite frontier record into a frontier row."""
    expanded_at = str(row.get("expanded_at") or "").strip()
    return SleeperFrontierRow(
        user_id=str(row.get("user_id") or "").strip(),
        username=str(row.get("username") or ""),
        display_name=str(row.get("display_name") or ""),
        discovered_at=datetime.fromisoformat(str(row["discovered_at"])),
        discovered_from_league_id=str(row.get("discovered_from_league_id") or "") or None,
        expanded_at=datetime.fromisoformat(expanded_at) if expanded_at else None,
    )


BOOLEAN_DISCOVERY_COLUMNS = {
    "is_dynasty",
    "is_superflex",
    "target_format_guess",
}
INTEGER_DISCOVERY_COLUMNS = {
    "league_season",
    "total_rosters",
    *[f"league_setting_{key}" for key in LEAGUE_SETTING_KEYS],
    *[f"roster_{key}" for key in ROSTER_POSITION_KEYS],
}
REAL_DISCOVERY_COLUMNS = {
    "ppr",
    "te_premium",
    *[f"scoring_{key}" for key in SCORING_SETTING_KEYS],
}


def discovery_sqlite_type(column: str) -> str:
    """Return the SQLite column type for a discovery column."""
    if column in BOOLEAN_DISCOVERY_COLUMNS or column in INTEGER_DISCOVERY_COLUMNS:
        return "INTEGER"
    if column in REAL_DISCOVERY_COLUMNS:
        return "REAL"
    return "TEXT"


def coerce_discovery_value(column: str, value: Any) -> str | int | float | None:
    """Coerce a discovery value into its SQLite storage type."""
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
    if value == "":
        return None
    if column in BOOLEAN_DISCOVERY_COLUMNS:
        if isinstance(value, bool):
            return int(value)
        value_text = str(value).lower()
        if value_text == "true":
            return 1
        if value_text == "false":
            return 0
        return int(float(value_text))
    if column in INTEGER_DISCOVERY_COLUMNS:
        return int(float(value))
    if column in REAL_DISCOVERY_COLUMNS:
        return float(value)
    return str(value)


def format_discovery_value(column: str, value: Any) -> str:
    """Format a SQLite discovery value back into flat text."""
    if value is None:
        return ""
    if column in BOOLEAN_DISCOVERY_COLUMNS:
        return "true" if int(value) else "false"
    if column in INTEGER_DISCOVERY_COLUMNS:
        return str(int(value))
    if column in REAL_DISCOVERY_COLUMNS:
        return f"{float(value):g}"
    return str(value)


class SleeperDiscoveryStore:
    def __init__(self, path: str | Path) -> None:
        """Open a SQLite discovery store and ensure its schema exists."""
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.path)
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA synchronous=NORMAL")
        self.init_schema()

    def init_schema(self) -> None:
        """Create discovery tables and indexes if they do not exist."""
        self.create_table("users", USER_DISCOVERY_COLUMNS, ("user_id",))
        self.create_table("leagues", LEAGUE_DISCOVERY_COLUMNS, ("league_id",))
        self.create_table(
            "league_users",
            LEAGUE_USER_DISCOVERY_COLUMNS,
            ("league_id", "user_id"),
        )
        self.create_table("frontier", USER_FRONTIER_COLUMNS, ("user_id",))
        self._connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_frontier_expanded_at_discovered_at_user_id "
            "ON frontier (expanded_at, discovered_at, user_id)"
        )
        self._connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_frontier_expanded_at_discovered_at_desc_user_id "
            "ON frontier (expanded_at, discovered_at DESC, user_id)"
        )

    def create_table(
        self,
        table: str,
        columns: list[str],
        key_columns: tuple[str, ...],
    ) -> None:
        """Create a typed WITHOUT ROWID table for discovery data."""
        column_sql = ", ".join(f"{column} {discovery_sqlite_type(column)}" for column in columns)
        key_sql = ", ".join(key_columns)
        self._connection.execute(
            f"CREATE TABLE IF NOT EXISTS {table} "
            f"({column_sql}, PRIMARY KEY ({key_sql})) WITHOUT ROWID"
        )

    def read_frontier(self) -> list[SleeperFrontierRow]:
        """Read all frontier rows from SQLite."""
        cursor = self._connection.execute(
            f"SELECT {', '.join(USER_FRONTIER_COLUMNS)} FROM frontier"
        )
        return self.parse_frontier_rows(cursor.fetchall())

    def read_unexpanded_frontier(
        self,
        limit: int | None,
        frontier_order: str = "oldest",
    ) -> list[SleeperFrontierRow]:
        """Read the next unexpanded frontier rows in the requested order."""
        if frontier_order not in {"oldest", "newest", "random"}:
            raise ValueError("frontier_order must be 'oldest', 'newest', or 'random'")
        limit_sql = "" if limit is None else " LIMIT ?"
        parameters: tuple[int, ...] = () if limit is None else (limit,)
        order_sql = (
            "random()"
            if frontier_order == "random"
            else f"discovered_at {'DESC' if frontier_order == 'newest' else 'ASC'}, user_id"
        )
        cursor = self._connection.execute(
            f"SELECT {', '.join(USER_FRONTIER_COLUMNS)} "
            "FROM frontier "
            "WHERE expanded_at IS NULL "
            f"ORDER BY {order_sql}{limit_sql}",
            parameters,
        )
        return self.parse_frontier_rows(cursor.fetchall())

    def parse_frontier_rows(self, rows: list[tuple[Any, ...]]) -> list[SleeperFrontierRow]:
        """Parse SQLite frontier tuples into frontier rows."""
        return [
            parse_frontier_row(
                {
                    column: format_discovery_value(column, value)
                    for column, value in zip(USER_FRONTIER_COLUMNS, row, strict=True)
                }
            )
            for row in rows
        ]

    def read_league_ids(self) -> set[str]:
        """Read all known league IDs."""
        return {
            row[0]
            for row in self._connection.execute("SELECT league_id FROM leagues")
            if row[0]
        }

    def read_league_user_ids(self) -> set[str]:
        """Read league IDs whose users have already been fetched."""
        return {
            row[0]
            for row in self._connection.execute("SELECT DISTINCT league_id FROM league_users")
            if row[0]
        }

    def read_frontier_ids(self) -> set[str]:
        """Read all known frontier user IDs."""
        return {
            row[0]
            for row in self._connection.execute("SELECT user_id FROM frontier")
            if row[0]
        }

    def count_unexpanded_frontier(self) -> int:
        """Count frontier users that have not been expanded."""
        return int(
            self._connection.execute(
                "SELECT COUNT(*) FROM frontier WHERE expanded_at IS NULL"
            ).fetchone()[0]
        )

    def count_leagues(self) -> int:
        """Count known leagues."""
        return self.count_table("leagues")

    def table_counts(self) -> dict[str, int]:
        """Return row counts for all discovery tables."""
        return {
            "users": self.count_table("users"),
            "leagues": self.count_table("leagues"),
            "league_users": self.count_table("league_users"),
            "frontier": self.count_table("frontier"),
        }

    def upsert_discovery(
        self,
        *,
        users: list[SleeperUserRow],
        leagues: list[SleeperLeagueRow],
        league_users: list[SleeperLeagueUserRow],
        frontier: list[SleeperFrontierRow],
    ) -> None:
        """Upsert a batch of discovery rows into SQLite."""
        with self._connection:
            self.upsert_rows(
                table="users",
                rows=[format_user_row(row) for row in users],
                columns=USER_DISCOVERY_COLUMNS,
                key_columns=("user_id",),
            )
            self.upsert_rows(
                table="leagues",
                rows=[format_league_row(row) for row in leagues],
                columns=LEAGUE_DISCOVERY_COLUMNS,
                key_columns=("league_id",),
            )
            self.upsert_rows(
                table="league_users",
                rows=[format_league_user_row(row) for row in league_users],
                columns=LEAGUE_USER_DISCOVERY_COLUMNS,
                key_columns=("league_id", "user_id"),
            )
            self.upsert_rows(
                table="frontier",
                rows=[format_frontier_row(row) for row in frontier],
                columns=USER_FRONTIER_COLUMNS,
                key_columns=("user_id",),
                update_sql=(
                    "username=excluded.username, "
                    "display_name=excluded.display_name, "
                    "discovered_from_league_id=COALESCE("
                    "frontier.discovered_from_league_id, excluded.discovered_from_league_id"
                    "), "
                    "expanded_at=COALESCE(excluded.expanded_at, frontier.expanded_at)"
                ),
            )

    def upsert_rows(
        self,
        *,
        table: str,
        rows: list[dict[str, Any]],
        columns: list[str],
        key_columns: tuple[str, ...],
        update_sql: str | None = None,
    ) -> None:
        """Upsert generic dictionaries into one SQLite table."""
        if not rows:
            return
        placeholders = ", ".join("?" for _ in columns)
        columns_sql = ", ".join(columns)
        update_columns = [column for column in columns if column not in key_columns]
        update_sql = update_sql or ", ".join(
            f"{column}=excluded.{column}" for column in update_columns
        )
        sql = (
            f"INSERT INTO {table} ({columns_sql}) VALUES ({placeholders}) "
            f"ON CONFLICT({', '.join(key_columns)}) DO UPDATE SET {update_sql}"
        )
        self._connection.executemany(
            sql,
            [
                tuple(coerce_discovery_value(column, row.get(column, "")) for column in columns)
                for row in rows
            ],
        )

    def count_table(self, table: str) -> int:
        """Count rows in a SQLite table."""
        return int(self._connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])

    def close(self) -> None:
        """Checkpoint pending WAL data and close the store."""
        self._connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        self._connection.close()

from __future__ import annotations

import csv
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
    optional_str,
    te_premium,
    upsert_csv,
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
    SleeperDiscoveryResult,
    SleeperFrontierExpansionResult,
    SleeperFrontierRow,
    SleeperLeagueRow,
    SleeperLeagueUserRow,
    SleeperUserRow,
)


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
    timing_collector: DiscoveryTiming | None = None,
    fetch_json: FetchJson | None = None,
) -> SleeperDiscoveryResult:
    captured_at = captured_at or datetime.now(UTC)
    fetch_json = fetch_json or default_fetch_json
    if timing_collector is not None:
        fetch_json = timed_fetch_json(fetch_json, timing_collector)
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

        user = fetch_json(user_url(user_ref))
        resolved_user_id = str(user["user_id"])
        if resolved_user_id in seen_user_ids:
            continue
        seen_user_ids.add(resolved_user_id)
        users_by_id[resolved_user_id] = user_row(captured_at=captured_at, user=user)

        for season in seasons:
            leagues = fetch_json(user_leagues_url(user_id=resolved_user_id, season=season))
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)

            for league in leagues:
                league_id = str(league["league_id"])
                leagues_by_id[league_id] = league_row(captured_at=captured_at, league=league)
                if max_leagues is not None and len(leagues_by_id) >= max_leagues:
                    break

                if league_id in fetched_league_users:
                    continue
                fetched_league_users.add(league_id)
                league_users = fetch_json(league_users_url(league_id))
                if sleep_seconds > 0:
                    time.sleep(sleep_seconds)

                for league_user in league_users:
                    league_user_id = user_id(league_user)
                    if not league_user_id:
                        continue
                    league_users_by_key[(league_id, league_user_id)] = league_user_row(
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
    flush_every: int = 25,
    workers: int = 1,
    requests_per_minute: int | None = None,
    progress_callback: DiscoveryProgressCallback | None = None,
    timing_collector: DiscoveryTiming | None = None,
    fetch_json: FetchJson | None = None,
) -> SleeperFrontierExpansionResult:
    captured_at = captured_at or datetime.now(UTC)
    fetch_json = fetch_json or default_fetch_json
    if timing_collector is not None:
        fetch_json = timed_fetch_json(fetch_json, timing_collector)
    workers = max(workers, 1)
    if workers > 1:
        if max_leagues is not None:
            raise ValueError("Concurrent frontier expansion does not support max_leagues.")
        return expand_user_frontier_parallel(
            frontier_path=frontier_path,
            seasons=seasons,
            users_path=users_path,
            leagues_path=leagues_path,
            league_users_path=league_users_path,
            max_users=max_users,
            captured_at=captured_at,
            flush_every=flush_every,
            workers=workers,
            requests_per_minute=requests_per_minute or 500,
            progress_callback=progress_callback,
            timing_collector=timing_collector,
            fetch_json=fetch_json,
        )

    frontier = read_user_frontier_csv(frontier_path)
    frontier_by_id = {row.user_id: row for row in frontier}
    users_by_id: dict[str, SleeperUserRow] = {}
    leagues_by_id: dict[str, SleeperLeagueRow] = {}
    league_users_by_key: dict[tuple[str, str], SleeperLeagueUserRow] = {}
    league_users_fetched = (
        read_league_user_ids_csv(league_users_path) if league_users_path is not None else set()
    )
    existing_league_ids = read_league_ids_csv(leagues_path) if leagues_path is not None else set()
    new_league_ids: set[str] = set()
    pending_users: list[SleeperUserRow] = []
    pending_leagues: list[SleeperLeagueRow] = []
    pending_league_users: list[SleeperLeagueUserRow] = []
    expanded_users = 0
    seasons = [str(season) for season in seasons]
    flush_every = max(flush_every, 1)

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

        resolved_user_id = frontier_row.user_id
        batch_users: list[SleeperUserRow] = []
        batch_leagues: list[SleeperLeagueRow] = []
        batch_league_users: list[SleeperLeagueUserRow] = []
        users_by_id[resolved_user_id] = SleeperUserRow(
            captured_at=captured_at,
            user_id=resolved_user_id,
            username=frontier_row.username,
            display_name=frontier_row.display_name,
        )
        batch_users.append(users_by_id[resolved_user_id])

        for season in seasons:
            leagues = fetch_json(user_leagues_url(user_id=resolved_user_id, season=season))
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)

            for league in leagues:
                league_id = str(league["league_id"])
                parsed_league = league_row(captured_at=captured_at, league=league)
                leagues_by_id[league_id] = parsed_league
                batch_leagues.append(parsed_league)
                if league_id not in existing_league_ids:
                    new_league_ids.add(league_id)
                if max_leagues is not None and len(leagues_by_id) >= max_leagues:
                    break

                if league_id in league_users_fetched:
                    continue
                league_users_fetched.add(league_id)
                league_users = fetch_json(league_users_url(league_id))
                if sleep_seconds > 0:
                    time.sleep(sleep_seconds)

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
                    batch_league_users.append(parsed_league_user)
                    parsed_user = user_row(captured_at=captured_at, user=league_user)
                    users_by_id[league_user_id] = parsed_user
                    batch_users.append(parsed_user)
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

        frontier_by_id[resolved_user_id] = SleeperFrontierRow(
            user_id=frontier_row.user_id,
            username=frontier_row.username,
            display_name=frontier_row.display_name,
            discovered_at=frontier_row.discovered_at,
            discovered_from_league_id=frontier_row.discovered_from_league_id,
            expanded_at=captured_at,
        )
        expanded_users += 1
        frontier_rows = sort_frontier_rows(frontier_by_id.values())
        pending_users.extend(batch_users)
        pending_leagues.extend(batch_leagues)
        pending_league_users.extend(batch_league_users)

        if expanded_users % flush_every == 0:
            flush_discovery_progress(
                users=pending_users,
                leagues=pending_leagues,
                league_users=pending_league_users,
                frontier=frontier_rows,
                users_path=users_path,
                leagues_path=leagues_path,
                league_users_path=league_users_path,
                frontier_path=frontier_path,
                timing_collector=timing_collector,
            )
            pending_users = []
            pending_leagues = []
            pending_league_users = []

        if progress_callback:
            progress_callback(
                expanded_users,
                len(leagues_by_id),
                len(new_league_ids),
                len(league_users_by_key),
                sum(1 for row in frontier_by_id.values() if row.expanded_at is None),
            )

    frontier_rows = sort_frontier_rows(frontier_by_id.values())
    flush_discovery_progress(
        users=pending_users,
        leagues=pending_leagues,
        league_users=pending_league_users,
        frontier=frontier_rows,
        users_path=users_path,
        leagues_path=leagues_path,
        league_users_path=league_users_path,
        frontier_path=frontier_path,
        timing_collector=timing_collector,
    )
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


def expand_user_frontier_parallel(
    *,
    frontier_path: str | Path,
    seasons: Iterable[str],
    users_path: str | Path | None,
    leagues_path: str | Path | None,
    league_users_path: str | Path | None,
    max_users: int | None,
    captured_at: datetime,
    flush_every: int,
    workers: int,
    requests_per_minute: int,
    progress_callback: DiscoveryProgressCallback | None,
    timing_collector: DiscoveryTiming | None,
    fetch_json: FetchJson,
) -> SleeperFrontierExpansionResult:
    frontier = read_user_frontier_csv(frontier_path)
    frontier_by_id = {row.user_id: row for row in frontier}
    work_rows = [
        row
        for row in sorted(
            frontier_by_id.values(),
            key=lambda row: (row.expanded_at is not None, row.discovered_at, row.user_id),
        )
        if row.expanded_at is None
    ]
    if max_users is not None:
        work_rows = work_rows[:max_users]

    users_by_id: dict[str, SleeperUserRow] = {}
    leagues_by_id: dict[str, SleeperLeagueRow] = {}
    league_users_by_key: dict[tuple[str, str], SleeperLeagueUserRow] = {}
    league_users_fetched = (
        read_league_user_ids_csv(league_users_path) if league_users_path is not None else set()
    )
    existing_league_ids = read_league_ids_csv(leagues_path) if leagues_path is not None else set()
    new_league_ids: set[str] = set()
    league_users_fetched_lock = Lock()
    throttle = RequestThrottle(requests_per_minute, timing_collector=timing_collector)
    seasons = [str(season) for season in seasons]
    flush_every = max(flush_every, 1)
    pending_users: list[SleeperUserRow] = []
    pending_leagues: list[SleeperLeagueRow] = []
    pending_league_users: list[SleeperLeagueUserRow] = []
    expanded_users = 0

    def throttled_fetch_json(url: str) -> Any:
        throttle.acquire()
        return fetch_json(url)

    def merge_result(result: FrontierUserFetchResult) -> None:
        nonlocal expanded_users
        for user in result.users:
            users_by_id[user.user_id] = user
        for league in result.leagues:
            leagues_by_id[league.league_id] = league
            if league.league_id not in existing_league_ids:
                new_league_ids.add(league.league_id)
        for league_user in result.league_users:
            league_users_by_key[(league_user.league_id, league_user.user_id)] = league_user
        for frontier_row in result.discovered_frontier:
            if frontier_row.user_id not in frontier_by_id:
                frontier_by_id[frontier_row.user_id] = frontier_row
        frontier_by_id[result.frontier_row.user_id] = SleeperFrontierRow(
            user_id=result.frontier_row.user_id,
            username=result.frontier_row.username,
            display_name=result.frontier_row.display_name,
            discovered_at=result.frontier_row.discovered_at,
            discovered_from_league_id=result.frontier_row.discovered_from_league_id,
            expanded_at=captured_at,
        )
        expanded_users += 1
        pending_users.extend(result.users)
        pending_leagues.extend(result.leagues)
        pending_league_users.extend(result.league_users)

    def flush_pending() -> None:
        nonlocal pending_users, pending_leagues, pending_league_users
        frontier_rows = sort_frontier_rows(frontier_by_id.values())
        flush_discovery_progress(
            users=pending_users,
            leagues=pending_leagues,
            league_users=pending_league_users,
            frontier=frontier_rows,
            users_path=users_path,
            leagues_path=leagues_path,
            league_users_path=league_users_path,
            frontier_path=frontier_path,
            timing_collector=timing_collector,
        )
        pending_users = []
        pending_leagues = []
        pending_league_users = []

    work_iter = iter(work_rows)
    futures: set[Future[FrontierUserFetchResult]] = set()
    executor = ThreadPoolExecutor(max_workers=workers)
    interrupted = False

    def submit_until_full() -> None:
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
                        sum(1 for row in frontier_by_id.values() if row.expanded_at is None),
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

    frontier_rows = sort_frontier_rows(frontier_by_id.values())
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
        self._spacing_seconds = 60 / max(requests_per_minute, 1)
        self._lock = Lock()
        self._next_request_at = 0.0
        self._timing_collector = timing_collector

    def acquire(self) -> None:
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


class DiscoveryTiming:
    def __init__(self) -> None:
        self._started_at = time.perf_counter()
        self._lock = Lock()
        self._request_count = 0
        self._request_seconds = 0.0
        self._throttle_wait_seconds = 0.0
        self._flush_count = 0
        self._flush_seconds = 0.0

    def record_request(self, seconds: float) -> None:
        with self._lock:
            self._request_count += 1
            self._request_seconds += seconds

    def record_throttle_wait(self, seconds: float) -> None:
        with self._lock:
            self._throttle_wait_seconds += seconds

    def record_flush(self, seconds: float) -> None:
        with self._lock:
            self._flush_count += 1
            self._flush_seconds += seconds

    def snapshot(self) -> DiscoveryTimingSnapshot:
        with self._lock:
            return DiscoveryTimingSnapshot(
                elapsed_seconds=time.perf_counter() - self._started_at,
                request_count=self._request_count,
                request_seconds=self._request_seconds,
                throttle_wait_seconds=self._throttle_wait_seconds,
                flush_count=self._flush_count,
                flush_seconds=self._flush_seconds,
            )


def timed_fetch_json(fetch_json: FetchJson, timing_collector: DiscoveryTiming) -> FetchJson:
    def fetch(url: str) -> Any:
        start = time.perf_counter()
        try:
            return fetch_json(url)
        finally:
            timing_collector.record_request(time.perf_counter() - start)

    return fetch


def read_user_frontier_csv(path: str | Path) -> list[SleeperFrontierRow]:
    path = Path(path)
    if not path.exists():
        return []

    with path.open(newline="", encoding="utf-8-sig") as file:
        rows = [parse_frontier_row(row) for row in csv.DictReader(file)]
        return [row for row in rows if row.user_id]


def upsert_user_frontier_csv(rows: list[SleeperFrontierRow], path: str | Path) -> Path:
    return upsert_csv(
        rows=(format_frontier_row(row) for row in rows),
        path=path,
        fieldnames=USER_FRONTIER_COLUMNS,
        key_fields=("user_id",),
        sort_fields=("expanded_at", "discovered_at", "user_id"),
    )


def flush_discovery_progress(
    *,
    users: list[SleeperUserRow],
    leagues: list[SleeperLeagueRow],
    league_users: list[SleeperLeagueUserRow],
    frontier: list[SleeperFrontierRow],
    users_path: str | Path | None,
    leagues_path: str | Path | None,
    league_users_path: str | Path | None,
    frontier_path: str | Path,
    timing_collector: DiscoveryTiming | None = None,
) -> None:
    start = time.perf_counter()
    try:
        if users_path is not None and users:
            upsert_user_discovery_csv(users, users_path)
        if leagues_path is not None and leagues:
            upsert_league_discovery_csv(leagues, leagues_path)
        if league_users_path is not None and league_users:
            upsert_league_user_discovery_csv(league_users, league_users_path)
        upsert_user_frontier_csv(frontier, frontier_path)
    finally:
        if timing_collector is not None:
            timing_collector.record_flush(time.perf_counter() - start)


def sort_frontier_rows(rows: Iterable[SleeperFrontierRow]) -> list[SleeperFrontierRow]:
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
    return upsert_csv(
        rows=(format_user_row(row) for row in rows),
        path=path,
        fieldnames=USER_DISCOVERY_COLUMNS,
        key_fields=("user_id",),
        sort_fields=("user_id",),
    )


def upsert_league_discovery_csv(rows: list[SleeperLeagueRow], path: str | Path) -> Path:
    return upsert_csv(
        rows=(format_league_row(row) for row in rows),
        path=path,
        fieldnames=LEAGUE_DISCOVERY_COLUMNS,
        key_fields=("league_id",),
        sort_fields=("league_season", "league_id"),
    )


def upsert_league_user_discovery_csv(
    rows: list[SleeperLeagueUserRow],
    path: str | Path,
) -> Path:
    return upsert_csv(
        rows=(format_league_user_row(row) for row in rows),
        path=path,
        fieldnames=LEAGUE_USER_DISCOVERY_COLUMNS,
        key_fields=("league_id", "user_id"),
        sort_fields=("league_season", "league_id", "user_id"),
    )


def read_league_user_ids_csv(path: str | Path) -> set[str]:
    path = Path(path)
    if not path.exists():
        return set()

    league_ids: set[str] = set()
    with path.open(newline="", encoding="utf-8-sig") as file:
        for row in csv.DictReader(file):
            league_id = row.get("league_id", "").strip()
            if league_id:
                league_ids.add(league_id)
    return league_ids


def read_league_ids_csv(path: str | Path) -> set[str]:
    path = Path(path)
    if not path.exists():
        return set()

    league_ids: set[str] = set()
    with path.open(newline="", encoding="utf-8-sig") as file:
        for row in csv.DictReader(file):
            league_id = row.get("league_id", "").strip()
            if league_id:
                league_ids.add(league_id)
    return league_ids


def user_row(*, captured_at: datetime, user: dict[str, Any]) -> SleeperUserRow:
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
    scoring_settings = league.get("scoring_settings") or {}
    league_settings = league.get("settings") or {}
    roster_positions = [str(position) for position in league.get("roster_positions") or []]
    ppr = optional_float(scoring_settings.get("rec"))
    premium = te_premium(scoring_settings, ppr)
    is_superflex = "SUPER_FLEX" in roster_positions
    total_rosters = _optional_int(league.get("total_rosters"))
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
    return SleeperLeagueUserRow(
        captured_at=captured_at,
        league_id=str(league["league_id"]),
        league_season=str(league.get("season") or ""),
        user_id=user_id(user) or "",
    )


def format_user_row(row: SleeperUserRow) -> dict[str, str]:
    return {
        "captured_date": row.captured_at.date().isoformat(),
        "user_id": row.user_id,
        "display_name": row.display_name,
    }


def format_league_row(row: SleeperLeagueRow) -> dict[str, str]:
    position_counts = Counter(row.roster_positions)
    formatted = {
        "captured_date": row.captured_at.date().isoformat(),
        "league_id": row.league_id,
        "league_name": row.league_name,
        "league_season": row.league_season,
        "previous_league_id": row.previous_league_id or "",
        "total_rosters": "" if row.total_rosters is None else str(row.total_rosters),
        "is_dynasty": optional_bool(row.is_dynasty),
        "is_superflex": str(row.is_superflex).lower(),
        "ppr": "" if row.ppr is None else f"{row.ppr:g}",
        "te_premium": f"{row.te_premium:g}",
        "target_format_guess": str(row.target_format_guess).lower(),
    }
    formatted.update(
        {
            f"league_setting_{key}": format_flat_value(row.league_settings.get(key))
            for key in LEAGUE_SETTING_KEYS
        }
    )
    formatted.update(
        {
            f"scoring_{key}": format_flat_value(row.scoring_settings.get(key))
            for key in SCORING_SETTING_KEYS
        }
    )
    formatted.update(
        {f"roster_{key}": str(position_counts.get(key, 0)) for key in ROSTER_POSITION_KEYS}
    )
    return formatted


def format_league_user_row(row: SleeperLeagueUserRow) -> dict[str, str]:
    return {
        "captured_date": row.captured_at.date().isoformat(),
        "league_id": row.league_id,
        "league_season": row.league_season,
        "user_id": row.user_id,
    }


def format_frontier_row(row: SleeperFrontierRow) -> dict[str, str]:
    return {
        "user_id": row.user_id,
        "username": row.username,
        "display_name": row.display_name,
        "discovered_at": row.discovered_at.isoformat(),
        "discovered_from_league_id": row.discovered_from_league_id or "",
        "expanded_at": "" if row.expanded_at is None else row.expanded_at.isoformat(),
    }


def parse_frontier_row(row: dict[str, str]) -> SleeperFrontierRow:
    row = {key.strip().lstrip("\ufeff"): value for key, value in row.items() if key}
    expanded_at = row.get("expanded_at", "").strip()
    return SleeperFrontierRow(
        user_id=row.get("user_id", "").strip(),
        username=row.get("username", ""),
        display_name=row.get("display_name", ""),
        discovered_at=datetime.fromisoformat(row["discovered_at"]),
        discovered_from_league_id=row.get("discovered_from_league_id") or None,
        expanded_at=datetime.fromisoformat(expanded_at) if expanded_at else None,
    )


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def format_flat_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)

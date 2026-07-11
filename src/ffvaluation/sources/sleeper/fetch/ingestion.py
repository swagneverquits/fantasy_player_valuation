from __future__ import annotations

import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Lock
from typing import Any

from ffvaluation.sources.sleeper.common import (
    FetchJson,
    fetch_json as default_fetch_json,
    league_url,
    transactions_url,
)
from ffvaluation.sources.sleeper.fetch.trades import trade_row
from ffvaluation.sources.sleeper.save.ingestion import (
    pending_trade_fetch_work,
    prepare_trade_ingestion_sqlite,
    update_trade_fetch_state,
)
from ffvaluation.sources.sleeper.save.trades import upsert_trade_history_sqlite


@dataclass(frozen=True)
class LeagueRoundResult:
    """Result for one league-round fetch."""

    league_id: str
    round_number: int
    rows: list[Any]
    error: str | None
    started_at: str
    completed_at: str


class RequestThrottle:
    """Limit all worker requests to a shared requests-per-minute rate."""

    def __init__(self, requests_per_minute: int) -> None:
        self.interval = 60.0 / max(requests_per_minute, 1)
        self.next_request = 0.0
        self.lock = Lock()

    def wait(self) -> None:
        """Wait for the next request slot."""
        with self.lock:
            now = time.monotonic()
            start = max(now, self.next_request)
            self.next_request = start + self.interval
        if start > now:
            time.sleep(start - now)


def ingest_sleeper_trades(
    *,
    discovery_db_path: str,
    output_path: str,
    season: str = "2025",
    min_rosters: int = 8,
    max_rosters: int = 16,
    first_round: int = 1,
    last_round: int = 18,
    max_leagues: int | None = None,
    workers: int = 10,
    requests_per_minute: int = 1000,
    progress_every: int = 100,
    fetch_json: FetchJson | None = None,
    progress_callback=None,
) -> dict[str, int]:
    """Fetch target-season completed trades into resumable raw SQLite."""
    fetch_json = fetch_json or default_fetch_json
    league_ids = prepare_trade_ingestion_sqlite(
        discovery_db_path=discovery_db_path,
        output_path=output_path,
        season=season,
        min_rosters=min_rosters,
        max_rosters=max_rosters,
        first_round=first_round,
        last_round=last_round,
    )
    if max_leagues is not None:
        league_ids = league_ids[:max_leagues]
    work = pending_trade_fetch_work(
        output_path,
        league_ids=league_ids,
        first_round=first_round,
        last_round=last_round,
    )
    throttle = RequestThrottle(requests_per_minute)
    total_work = sum(len(rounds) for rounds in work.values())
    completed = failed = trades = processed = 0

    def fetch_league(league_id: str, rounds: list[int]) -> list[LeagueRoundResult]:
        """Fetch league metadata once and all incomplete transaction rounds."""
        results: list[LeagueRoundResult] = []
        try:
            throttle.wait()
            league = fetch_json(league_url(league_id))
        except Exception as error:  # noqa: BLE001
            message = f"{type(error).__name__}: {error}"
            now = datetime.now(UTC).isoformat()
            return [LeagueRoundResult(league_id, r, [], message, now, now) for r in rounds]
        for round_number in rounds:
            started = datetime.now(UTC).isoformat()
            try:
                throttle.wait()
                transactions = fetch_json(transactions_url(league_id, round_number))
                rows = [
                    trade_row(
                        captured_at=datetime.now(UTC),
                        league=league,
                        round_number=round_number,
                        transaction=transaction,
                    )
                    for transaction in transactions
                    if transaction.get("type") == "trade"
                    and transaction.get("status") == "complete"
                ]
                results.append(
                    LeagueRoundResult(
                        league_id,
                        round_number,
                        rows,
                        None,
                        started,
                        datetime.now(UTC).isoformat(),
                    )
                )
            except Exception as error:  # noqa: BLE001
                results.append(
                    LeagueRoundResult(
                        league_id,
                        round_number,
                        [],
                        f"{type(error).__name__}: {error}",
                        started,
                        datetime.now(UTC).isoformat(),
                    )
                )
        return results

    futures: set[Future[list[LeagueRoundResult]]] = set()
    with ThreadPoolExecutor(max_workers=max(workers, 1)) as executor:
        work_items = iter(work.items())
        while True:
            while len(futures) < max(workers, 1):
                try:
                    league_id, rounds = next(work_items)
                except StopIteration:
                    break
                futures.add(executor.submit(fetch_league, league_id, rounds))
            if not futures:
                break
            done, futures = wait(futures, return_when=FIRST_COMPLETED)
            for future in done:
                for result in future.result():
                    if result.error is None:
                        upsert_trade_history_sqlite(result.rows, output_path)
                        update_trade_fetch_state(
                            output_path,
                            league_id=result.league_id,
                            round_number=result.round_number,
                            status="complete",
                            trade_count=len(result.rows),
                            started_at=result.started_at,
                            completed_at=result.completed_at,
                        )
                        completed += 1
                        trades += len(result.rows)
                    else:
                        update_trade_fetch_state(
                            output_path,
                            league_id=result.league_id,
                            round_number=result.round_number,
                            status="failed",
                            error=result.error,
                            started_at=result.started_at,
                            completed_at=result.completed_at,
                        )
                        failed += 1
                    processed += 1
                    if progress_callback is not None and (
                        processed == 1
                        or processed % max(progress_every, 1) == 0
                        or processed == total_work
                    ):
                        progress_callback(processed, total_work, completed, failed, trades)
    return {
        "leagues": len(league_ids),
        "work_items": total_work,
        "completed": completed,
        "failed": failed,
        "trades": trades,
    }

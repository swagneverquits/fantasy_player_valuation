from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from datetime import UTC, datetime, timedelta
from typing import Any

from ffvaluation.sources.sleeper.common import (
    FetchJson,
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
from ffvaluation.sources.sleeper.models import SleeperTradeRow


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

from __future__ import annotations

import csv
import time
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from ffvaluation.sources.sleeper.common import (
    FetchJson,
    dumps_json,
    fetch_json as default_fetch_json,
    is_dynasty,
    league_url,
    millis_to_datetime,
    optional_bool,
    optional_float,
    optional_int,
    optional_str,
    te_premium,
    transactions_url,
)
from ffvaluation.sources.sleeper.models import TRADE_HISTORY_COLUMNS, SleeperTradeRow


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
                if trade_time is not None and trade_time < since:
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


def write_trade_history_csv(rows: list[SleeperTradeRow], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=TRADE_HISTORY_COLUMNS)
        writer.writeheader()
        writer.writerows(format_trade_row(row) for row in rows)

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
        formatted = format_trade_row(row)
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


def iter_league_chain(
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


def format_trade_row(row: SleeperTradeRow) -> dict[str, str]:
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
        "roster_ids": dumps_json(row.roster_ids),
        "consenter_ids": dumps_json(row.consenter_ids),
        "adds": dumps_json(row.adds),
        "drops": dumps_json(row.drops),
        "draft_picks": dumps_json(row.draft_picks),
        "waiver_budget": dumps_json(row.waiver_budget),
        "total_rosters": "" if row.total_rosters is None else str(row.total_rosters),
        "is_dynasty": optional_bool(row.is_dynasty),
        "is_superflex": str(row.is_superflex).lower(),
        "ppr": "" if row.ppr is None else f"{row.ppr:g}",
        "te_premium": f"{row.te_premium:g}",
        "target_format_guess": str(row.target_format_guess).lower(),
        "league_settings": dumps_json(row.league_settings),
        "scoring_settings": dumps_json(row.scoring_settings),
        "roster_positions": dumps_json(row.roster_positions),
    }

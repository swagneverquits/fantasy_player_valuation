from __future__ import annotations

import sqlite3
from pathlib import Path

from ffvaluation.sources.sleeper.save.trades import copy_trade_sample_leagues_sqlite


STATE_COLUMNS = [
    "league_id",
    "round",
    "status",
    "attempts",
    "trade_count",
    "last_error",
    "started_at",
    "completed_at",
]


def target_league_ids_from_discovery(
    discovery_db_path: str | Path,
    *,
    season: str = "2025",
    min_rosters: int = 8,
    max_rosters: int = 16,
) -> list[str]:
    """Read target dynasty superflex league IDs from discovery SQLite."""
    with sqlite3.connect(discovery_db_path) as connection:
        return [
            str(row[0])
            for row in connection.execute(
                """
                SELECT league_id FROM leagues
                WHERE league_season = ?
                  AND is_dynasty = 1
                  AND is_superflex = 1
                  AND total_rosters BETWEEN ? AND ?
                ORDER BY league_id
                """,
                (season, min_rosters, max_rosters),
            )
        ]


def prepare_trade_ingestion_sqlite(
    *,
    discovery_db_path: str | Path,
    output_path: str | Path,
    season: str = "2025",
    min_rosters: int = 8,
    max_rosters: int = 16,
    first_round: int = 1,
    last_round: int = 18,
) -> list[str]:
    """Materialize target league context and league-round work in SQLite."""
    league_ids = target_league_ids_from_discovery(
        discovery_db_path,
        season=season,
        min_rosters=min_rosters,
        max_rosters=max_rosters,
    )
    copy_trade_sample_leagues_sqlite(
        discovery_db_path=discovery_db_path,
        sample_db_path=output_path,
        league_ids=league_ids,
    )
    with sqlite3.connect(output_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS trade_fetch_state (
                league_id TEXT NOT NULL,
                round INTEGER NOT NULL,
                status TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                trade_count INTEGER NOT NULL DEFAULT 0,
                last_error TEXT,
                started_at TEXT,
                completed_at TEXT,
                PRIMARY KEY (league_id, round)
            ) WITHOUT ROWID
            """
        )
        connection.executemany(
            "INSERT OR IGNORE INTO trade_fetch_state (league_id, round, status) "
            "VALUES (?, ?, 'pending')",
            [
                (league_id, round_number)
                for league_id in league_ids
                for round_number in range(first_round, last_round + 1)
            ],
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_trade_fetch_state_status "
            "ON trade_fetch_state(status, league_id, round)"
        )
    return league_ids


def pending_trade_fetch_work(
    path: str | Path,
    *,
    league_ids: list[str],
    first_round: int = 1,
    last_round: int = 18,
) -> dict[str, list[int]]:
    """Read incomplete league-round work grouped by league."""
    if len(league_ids) <= 900:
        placeholders = ", ".join("?" for _ in league_ids)
        league_filter = f"league_id IN ({placeholders})"
        parameters = (*league_ids, first_round, last_round)
    else:
        league_filter = "1 = 1"
        parameters = (first_round, last_round)
    with sqlite3.connect(path) as connection:
        rows = connection.execute(
            f"""
            SELECT league_id, round
            FROM trade_fetch_state
            WHERE {league_filter}
              AND round BETWEEN ? AND ?
              AND status <> 'complete'
            ORDER BY league_id, round
            """,
            parameters,
        ).fetchall()
    work: dict[str, list[int]] = {}
    for league_id, round_number in rows:
        work.setdefault(str(league_id), []).append(int(round_number))
    return work


def update_trade_fetch_state(
    path: str | Path,
    *,
    league_id: str,
    round_number: int,
    status: str,
    trade_count: int = 0,
    error: str | None = None,
    started_at: str | None = None,
    completed_at: str | None = None,
) -> None:
    """Update one league-round ingestion checkpoint."""
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            UPDATE trade_fetch_state
            SET status = ?, attempts = attempts + 1, trade_count = ?,
                last_error = ?, started_at = ?, completed_at = ?
            WHERE league_id = ? AND round = ?
            """,
            (
                status,
                trade_count,
                error,
                started_at,
                completed_at,
                league_id,
                round_number,
            ),
        )

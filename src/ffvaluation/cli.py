from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from ffvaluation.ingestion.snapshots import (
    upsert_snapshot_history_csv,
    write_snapshot_csv,
)
from ffvaluation.sources.rosteraudit import (
    fetch_rankings_snapshot,
    pull_value_history_csv_incremental,
)
from ffvaluation.sources.registry import list_sources

app = typer.Typer(no_args_is_help=True)
console = Console()


@app.command()
def sources() -> None:
    """List candidate valuation sources."""

    table = Table(title="Candidate valuation sources")
    table.add_column("Source")
    table.add_column("Type")
    table.add_column("Access")
    table.add_column("Notes")

    for source in list_sources():
        table.add_row(
            source.name,
            source.valuation_type.value,
            source.access_method,
            source.notes or "",
        )

    console.print(table)


@app.command("pull-rosteraudit")
def pull_rosteraudit(
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Snapshot CSV output path. Defaults to data/raw/rosteraudit/rankings/YYYYMMDD.csv.",
    ),
    max_pages: int | None = typer.Option(
        None,
        "--max-pages",
        help="Limit API pages for smoke runs. Omit to pull every page.",
    ),
    index_output: Path | None = typer.Option(
        None,
        "--index-output",
        help="Upserted rankings CSV path. Defaults to data/raw/rosteraudit/rankings/history.csv.",
    ),
) -> None:
    """Pull a current RosterAudit Superflex snapshot."""

    captured_at = datetime.now(UTC)
    as_of_date = captured_at.date().isoformat()
    output = output or Path(f"data/raw/rosteraudit/rankings/{captured_at:%Y%m%d}.csv")
    index_output = index_output or Path("data/raw/rosteraudit/rankings/history.csv")
    rows = fetch_rankings_snapshot(captured_at=captured_at, max_pages=max_pages)
    write_snapshot_csv(rows, output)
    upsert_snapshot_history_csv(rows, index_output, as_of_date=as_of_date)
    console.print(
        f"Wrote {len(rows)} RosterAudit rows to {output} "
        f"and upserted {index_output}"
    )


@app.command("pull-rosteraudit-history")
def pull_rosteraudit_history(
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Value-history CSV output path. Defaults to data/raw/rosteraudit/value_history/YYYYMMDD.csv.",
    ),
    api_key: str | None = typer.Option(
        None,
        "--api-key",
        help="RosterAudit API key. Defaults to ROSTERAUDIT_API_KEY from .env.",
    ),
    limit: int | None = typer.Option(
        None,
        "--limit",
        help="Limit players for smoke runs. Omit to pull every ranked player.",
    ),
    sleep_seconds: float = typer.Option(
        5.0,
        "--sleep-seconds",
        help="Delay between player-page calls.",
    ),
    progress_every: int = typer.Option(
        50,
        "--progress-every",
        help="Print progress every N ranking assets. Use 0 to disable.",
    ),
    latest_date: str | None = typer.Option(
        None,
        "--latest-date",
        help="Skip players only when this as_of_date is already saved. Defaults to today.",
    ),
) -> None:
    """Pull RosterAudit player value history."""

    captured_at = datetime.now(UTC)
    output = output or Path(f"data/raw/rosteraudit/value_history/{captured_at:%Y%m%d}.csv")
    api_key = api_key or _load_env_value("ROSTERAUDIT_API_KEY")
    if not api_key:
        raise typer.BadParameter("Set ROSTERAUDIT_API_KEY in .env or pass --api-key.")

    result = pull_value_history_csv_incremental(
        api_key=api_key,
        path=output,
        captured_at=captured_at,
        limit=limit,
        latest_as_of_date=latest_date,
        sleep_seconds=sleep_seconds,
        progress_callback=_progress_printer(progress_every),
    )
    console.print(
        "Upserted "
        f"{result.rows_written} RosterAudit value-history rows into {output} "
        f"({result.players_fetched} fetched, {result.players_skipped} skipped)"
    )


def _load_env_value(name: str, env_path: Path = Path(".env")) -> str | None:
    if not env_path.exists():
        return None

    for line in env_path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator and key.strip().lstrip("\ufeff") == name:
            return value.strip().strip("\"'")
    return None


def _progress_printer(every: int):
    if every <= 0:
        return None

    def print_progress(current: int, total: int, status: str) -> None:
        if current == 1 or current % every == 0 or current == total:
            console.print(f"RosterAudit history: {current}/{total} {status}")

    return print_progress

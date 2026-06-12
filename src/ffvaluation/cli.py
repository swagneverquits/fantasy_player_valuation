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
from ffvaluation.sources.sleeper import (
    discover_league_network,
    expand_user_frontier,
    fetch_trade_history,
    read_user_frontier_csv,
    seed_user_frontier,
    upsert_league_discovery_csv,
    upsert_league_user_discovery_csv,
    upsert_trade_history_csv,
    upsert_user_discovery_csv,
    write_trade_history_csv,
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


@app.command("pull-sleeper-trades")
def pull_sleeper_trades(
    league_id: str = typer.Option(
        ...,
        "--league-id",
        help="Sleeper league ID to use as the starting point.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Trade CSV output path. Defaults to data/raw/sleeper/trades/YYYYMMDD.csv.",
    ),
    index_output: Path | None = typer.Option(
        None,
        "--index-output",
        help="Upserted trade CSV path. Defaults to data/raw/sleeper/trades/history.csv.",
    ),
    days: int = typer.Option(
        365,
        "--days",
        help="Keep trades created within this many days.",
    ),
    first_round: int = typer.Option(
        1,
        "--first-round",
        help="First Sleeper transaction round/week to fetch.",
    ),
    last_round: int = typer.Option(
        18,
        "--last-round",
        help="Last Sleeper transaction round/week to fetch.",
    ),
    follow_previous: bool = typer.Option(
        True,
        "--follow-previous/--no-follow-previous",
        help="Follow previous_league_id links for older seasons.",
    ),
    max_leagues: int | None = typer.Option(
        2,
        "--max-leagues",
        help="Limit followed league seasons. Defaults to current plus one previous season.",
    ),
    sleep_seconds: float = typer.Option(
        0.1,
        "--sleep-seconds",
        help="Delay between Sleeper transaction calls.",
    ),
) -> None:
    """Pull completed Sleeper trades for a league history."""

    captured_at = datetime.now(UTC)
    output = output or Path(f"data/raw/sleeper/trades/{captured_at:%Y%m%d}.csv")
    index_output = index_output or Path("data/raw/sleeper/trades/history.csv")
    rows = fetch_trade_history(
        league_id=league_id,
        days=days,
        rounds=range(first_round, last_round + 1),
        follow_previous=follow_previous,
        max_leagues=max_leagues,
        captured_at=captured_at,
        sleep_seconds=sleep_seconds,
    )
    write_trade_history_csv(rows, output)
    upsert_trade_history_csv(rows, index_output)

    target_format_rows = sum(1 for row in rows if row.target_format_guess)
    console.print(
        f"Wrote {len(rows)} Sleeper trades to {output} and upserted {index_output} "
        f"({target_format_rows} target-format guesses)"
    )


@app.command("discover-sleeper-network")
def discover_sleeper_network(
    username: str = typer.Option(
        ...,
        "--username",
        help="Sleeper username or user ID to seed the crawl.",
    ),
    season: list[str] = typer.Option(
        ["2025", "2026"],
        "--season",
        help="NFL league season to inspect. Repeat for multiple seasons.",
    ),
    max_depth: int = typer.Option(
        5,
        "--max-depth",
        help="User graph depth. 5 branches from the seed through leaguemates' leagues.",
    ),
    max_users: int | None = typer.Option(
        None,
        "--max-users",
        help="Maximum users to resolve. Omit for no cap.",
    ),
    max_leagues: int | None = typer.Option(
        None,
        "--max-leagues",
        help="Maximum leagues to discover. Omit for no cap.",
    ),
    output_dir: Path = typer.Option(
        Path("data/raw/sleeper/discovery"),
        "--output-dir",
        help="Directory for users, leagues, and league_users history CSVs.",
    ),
    sleep_seconds: float = typer.Option(
        0.1,
        "--sleep-seconds",
        help="Delay between Sleeper discovery calls.",
    ),
    progress_every: int = typer.Option(
        25,
        "--progress-every",
        help="Print discovery progress every N resolved users. Use 0 to disable.",
    ),
) -> None:
    """Discover Sleeper users and leagues from a seed user."""

    captured_at = datetime.now(UTC)
    result = discover_league_network(
        seed_user=username,
        seasons=season,
        max_depth=max_depth,
        max_users=max_users,
        max_leagues=max_leagues,
        captured_at=captured_at,
        sleep_seconds=sleep_seconds,
        progress_callback=_discovery_progress_printer(progress_every),
    )
    users_path = output_dir / "users_history.csv"
    leagues_path = output_dir / "leagues_history.csv"
    league_users_path = output_dir / "league_users_history.csv"

    upsert_user_discovery_csv(result.users, users_path)
    upsert_league_discovery_csv(result.leagues, leagues_path)
    upsert_league_user_discovery_csv(result.league_users, league_users_path)

    target_leagues = sum(1 for league in result.leagues if league.target_format_guess)
    console.print(
        f"Discovered {len(result.users)} users, {len(result.leagues)} leagues, "
        f"and {len(result.league_users)} league-user edges "
        f"({target_leagues} target-format league guesses)"
    )
    console.print(f"Wrote {users_path}, {leagues_path}, and {league_users_path}")


@app.command("seed-sleeper-network")
def seed_sleeper_network(
    username: str = typer.Option(
        ...,
        "--username",
        help="Sleeper username or user ID to add to the discovery frontier.",
    ),
    output_dir: Path = typer.Option(
        Path("data/raw/sleeper/discovery"),
        "--output-dir",
        help="Directory for discovery CSVs.",
    ),
) -> None:
    """Add a Sleeper user to the persistent discovery frontier."""

    frontier_path = output_dir / "user_frontier.csv"
    row = seed_user_frontier(seed_user=username, path=frontier_path)
    console.print(f"Seeded {row.username or row.user_id} into {frontier_path}")


@app.command("expand-sleeper-network")
def expand_sleeper_network(
    season: list[str] = typer.Option(
        ["2025", "2026"],
        "--season",
        help="NFL league season to inspect. Repeat for multiple seasons.",
    ),
    output_dir: Path = typer.Option(
        Path("data/raw/sleeper/discovery"),
        "--output-dir",
        help="Directory for discovery CSVs.",
    ),
    max_users: int | None = typer.Option(
        1000,
        "--max-users",
        help="Maximum unexpanded frontier users to process in this run. Omit for no cap.",
    ),
    max_leagues: int | None = typer.Option(
        None,
        "--max-leagues",
        help="Maximum newly discovered leagues in this run. Omit for no cap.",
    ),
    sleep_seconds: float = typer.Option(
        0.1,
        "--sleep-seconds",
        help="Delay between Sleeper discovery calls.",
    ),
    progress_every: int = typer.Option(
        25,
        "--progress-every",
        help="Print discovery progress every N expanded users. Use 0 to disable.",
    ),
) -> None:
    """Expand the persistent Sleeper user frontier."""

    frontier_path = output_dir / "user_frontier.csv"
    if not read_user_frontier_csv(frontier_path):
        raise typer.BadParameter(
            f"No frontier users found at {frontier_path}. Run seed-sleeper-network first."
        )

    result = expand_user_frontier(
        frontier_path=frontier_path,
        seasons=season,
        max_users=max_users,
        max_leagues=max_leagues,
        sleep_seconds=sleep_seconds,
        progress_callback=_discovery_progress_printer(progress_every),
    )

    users_path = output_dir / "users_history.csv"
    leagues_path = output_dir / "leagues_history.csv"
    league_users_path = output_dir / "league_users_history.csv"
    upsert_user_discovery_csv(result.users, users_path)
    upsert_league_discovery_csv(result.leagues, leagues_path)
    upsert_league_user_discovery_csv(result.league_users, league_users_path)

    target_leagues = sum(1 for league in result.leagues if league.target_format_guess)
    remaining_frontier = sum(1 for row in result.frontier if row.expanded_at is None)
    console.print(
        f"Expanded {result.expanded_users} users, found {len(result.leagues)} leagues, "
        f"and wrote {len(result.league_users)} league-user edges "
        f"({target_leagues} target-format league guesses)"
    )
    console.print(f"Remaining unexpanded frontier users: {remaining_frontier}")
    console.print(f"Wrote {frontier_path}, {users_path}, {leagues_path}, and {league_users_path}")


def _discovery_progress_printer(every: int):
    if every <= 0:
        return None

    def print_progress(users: int, leagues: int, league_users: int, queued_users: int) -> None:
        if users == 1 or users % every == 0:
            console.print(
                "Sleeper discovery: "
                f"{users} users, {leagues} leagues, {league_users} league-user edges, "
                f"{queued_users} queued"
            )

    return print_progress


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

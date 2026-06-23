from __future__ import annotations

from collections import deque
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
    DiscoveryTiming,
    SleeperDiscoveryStore,
    copy_trade_sample_leagues_sqlite,
    copy_trade_sample_players_sqlite,
    expand_user_frontier_sqlite,
    fetch_roster_sample,
    fetch_trade_sample,
    pull_nfl_players_sqlite,
    read_sample_league_ids_sqlite,
    sample_league_ids_from_discovery,
    seed_user_frontier,
    upsert_rosters_sqlite,
    upsert_trade_history_sqlite,
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
    api_key = api_key or load_env_value("ROSTERAUDIT_API_KEY")
    if not api_key:
        raise typer.BadParameter("Set ROSTERAUDIT_API_KEY in .env or pass --api-key.")

    result = pull_value_history_csv_incremental(
        api_key=api_key,
        path=output,
        captured_at=captured_at,
        limit=limit,
        latest_as_of_date=latest_date,
        sleep_seconds=sleep_seconds,
        progress_callback=progress_printer(progress_every),
    )
    console.print(
        "Upserted "
        f"{result.rows_written} RosterAudit value-history rows into {output} "
        f"({result.players_fetched} fetched, {result.players_skipped} skipped)"
    )


@app.command("sample-sleeper-trades")
def sample_sleeper_trades(
    discovery_db_path: Path = typer.Option(
        Path("data/raw/sleeper/discovery/discovery.sqlite"),
        "--discovery-db-path",
        help="Sleeper discovery SQLite database path.",
    ),
    output: Path = typer.Option(
        Path("data/sample/sleeper/trades/sample.sqlite"),
        "--output",
        "-o",
        help="Sample trade SQLite output path.",
    ),
    players_db_path: Path = typer.Option(
        Path("data/raw/sleeper/players/players.sqlite"),
        "--players-db-path",
        help="Raw Sleeper player catalog SQLite path.",
    ),
    season: str = typer.Option(
        "2025",
        "--season",
        help="Sleeper league season to sample.",
    ),
    leagues: int = typer.Option(
        100,
        "--leagues",
        help="Number of discovered leagues to sample.",
    ),
    target_only: bool = typer.Option(
        True,
        "--target-only/--any-format",
        help="Sample only target-format leagues by default.",
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
    sleep_seconds: float = typer.Option(
        0.1,
        "--sleep-seconds",
        help="Delay between Sleeper transaction calls.",
    ),
    progress_every: int = typer.Option(
        10,
        "--progress-every",
        help="Print progress every N sampled leagues. Use 0 to disable.",
    ),
    include_players: bool = typer.Option(
        True,
        "--include-players/--no-players",
        help="Copy player lookup rows for trade add/drop IDs into the sample database.",
    ),
    include_rosters: bool = typer.Option(
        True,
        "--include-rosters/--no-rosters",
        help="Fetch roster_id to user_id mappings into the sample database.",
    ),
) -> None:
    """Sample completed Sleeper trades from discovered leagues into SQLite."""

    league_ids = sample_league_ids_from_discovery(
        discovery_db_path=discovery_db_path,
        season=season,
        limit=leagues,
        target_only=target_only,
    )
    if not league_ids:
        raise typer.BadParameter(f"No sampled leagues found in {discovery_db_path}.")

    rows = fetch_trade_sample(
        league_ids=league_ids,
        season=season,
        rounds=range(first_round, last_round + 1),
        sleep_seconds=sleep_seconds,
        progress_callback=trade_sample_progress_printer(progress_every),
    )
    upsert_trade_history_sqlite(rows, output)
    roster_count = 0
    if include_rosters:
        roster_rows = fetch_roster_sample(
            league_ids=league_ids,
            sleep_seconds=sleep_seconds,
            progress_callback=roster_sample_progress_printer(progress_every),
        )
        upsert_rosters_sqlite(roster_rows, output)
        roster_count = len(roster_rows)
    copy_trade_sample_leagues_sqlite(
        discovery_db_path=discovery_db_path,
        sample_db_path=output,
        league_ids=league_ids,
    )
    player_count = (
        copy_trade_sample_players_sqlite(
            sample_db_path=output,
            players_db_path=players_db_path,
        )
        if include_players
        else 0
    )

    console.print(
        f"Sampled {len(league_ids)} {season} Sleeper leagues, "
        f"wrote {len(rows)} completed trades, {roster_count} rosters, "
        f"and {player_count} players to {output}"
    )


@app.command("pull-sleeper-players")
def pull_sleeper_players(
    output: Path = typer.Option(
        Path("data/raw/sleeper/players/players.sqlite"),
        "--output",
        "-o",
        help="Raw Sleeper player catalog SQLite output path.",
    ),
) -> None:
    """Pull the Sleeper NFL player catalog into SQLite."""

    player_count = pull_nfl_players_sqlite(path=output)
    console.print(f"Upserted {player_count} Sleeper NFL players into {output}")


@app.command("hydrate-sleeper-sample-rosters")
def hydrate_sleeper_sample_rosters(
    sample_db_path: Path = typer.Option(
        Path("data/sample/sleeper/trades/sample.sqlite"),
        "--sample-db-path",
        help="Sleeper sample SQLite database path.",
    ),
    sleep_seconds: float = typer.Option(
        0.1,
        "--sleep-seconds",
        help="Delay between Sleeper roster calls.",
    ),
    progress_every: int = typer.Option(
        10,
        "--progress-every",
        help="Print progress every N sampled leagues. Use 0 to disable.",
    ),
) -> None:
    """Fetch roster_id to user_id mappings for an existing Sleeper sample DB."""

    league_ids = read_sample_league_ids_sqlite(sample_db_path)
    if not league_ids:
        raise typer.BadParameter(f"No leagues found in {sample_db_path}.")
    roster_rows = fetch_roster_sample(
        league_ids=league_ids,
        sleep_seconds=sleep_seconds,
        progress_callback=roster_sample_progress_printer(progress_every),
    )
    upsert_rosters_sqlite(roster_rows, sample_db_path)
    console.print(
        f"Hydrated {len(roster_rows)} Sleeper roster rows across "
        f"{len(league_ids)} leagues into {sample_db_path}"
    )


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
        help="Directory for the Sleeper discovery database.",
    ),
    db_path: Path | None = typer.Option(
        None,
        "--db-path",
        help="SQLite discovery database path. Defaults to <output-dir>/discovery.sqlite.",
    ),
) -> None:
    """Add a Sleeper user to the persistent discovery frontier."""

    db_path = db_path or output_dir / "discovery.sqlite"
    row = seed_user_frontier(seed_user=username, db_path=db_path)
    console.print(f"Seeded {row.username or row.user_id} into {db_path}")


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
        help="Directory for the Sleeper discovery database.",
    ),
    db_path: Path | None = typer.Option(
        None,
        "--db-path",
        help="SQLite discovery database path. Defaults to <output-dir>/discovery.sqlite.",
    ),
    max_users: int | None = typer.Option(
        None,
        "--max-users",
        help="Maximum unexpanded frontier users to process in this run. Omit for no cap.",
    ),
    progress_every: int = typer.Option(
        100,
        "--progress-every",
        help="Print discovery progress every N expanded users. Use 0 to disable.",
    ),
    flush_every: int = typer.Option(
        100,
        "--flush-every",
        help="Flush SQLite discovery state every N expanded users. Lower is safer; higher is faster.",
    ),
    workers: int = typer.Option(
        10,
        "--workers",
        help="Concurrent discovery workers. Use 1 for serial mode.",
    ),
    requests_per_minute: int = typer.Option(
        1000,
        "--requests-per-minute",
        help="Global Sleeper API request throttle.",
    ),
    frontier_order: str = typer.Option(
        "random",
        "--frontier-order",
        help="Unexpanded frontier order: oldest, newest, or random.",
    ),
    timing: bool = typer.Option(
        True,
        "--timing/--no-timing",
        help="Print request, throttle, and flush timing telemetry with progress.",
    ),
) -> None:
    """Expand the persistent Sleeper user frontier."""

    db_path = db_path or output_dir / "discovery.sqlite"
    if frontier_order not in {"oldest", "newest", "random"}:
        raise typer.BadParameter("--frontier-order must be oldest, newest, or random.")
    store = SleeperDiscoveryStore(db_path)
    if not store.read_frontier():
        store.close()
        raise typer.BadParameter(
            f"No frontier users found in {db_path}. Run seed-sleeper-network first."
        )
    initial_league_count = store.count_leagues()
    initial_queued_users = store.count_unexpanded_frontier()
    store.close()

    timing_collector = DiscoveryTiming() if timing else None
    result = expand_user_frontier_sqlite(
        db_path=db_path,
        seasons=season,
        max_users=max_users,
        flush_every=flush_every,
        workers=workers,
        requests_per_minute=requests_per_minute,
        frontier_order=frontier_order,
        progress_callback=discovery_progress_printer(
            progress_every,
            initial_leagues_history_count=initial_league_count,
            initial_queued_users=initial_queued_users,
            timing_collector=timing_collector,
        ),
        timing_collector=timing_collector,
    )

    target_leagues = sum(1 for league in result.leagues if league.target_format_guess)
    console.print(
        f"Expanded {result.expanded_users} users, found {len(result.leagues)} leagues, "
        f"and wrote {len(result.league_users)} league-user edges "
        f"({target_leagues} target-format league guesses)"
    )
    console.print(f"Remaining unexpanded frontier users: {result.remaining_frontier}")
    console.print(f"Wrote SQLite discovery state to {db_path}")


def discovery_progress_printer(
    every: int,
    initial_leagues_history_count: int | None = None,
    initial_queued_users: int | None = None,
    timing_collector: DiscoveryTiming | None = None,
):
    """Build a Sleeper discovery progress callback."""
    if every <= 0:
        return None
    rolling_window_users = 5000
    rolling_snapshots: deque[tuple[int, int, int | None]] = deque([(0, 0, 0)])

    def print_progress(
        users: int,
        leagues_seen: int,
        new_leagues: int,
        league_users: int,
        queued_users: int,
    ) -> None:
        """Print periodic Sleeper discovery progress."""
        if users % every == 0:
            snapshot = timing_collector.snapshot() if timing_collector is not None else None
            average_seconds_per_interval = (
                None if snapshot is None else safe_div(snapshot.elapsed_seconds * every, users)
            )
            estimated_rows = None
            if initial_leagues_history_count is not None:
                estimated_rows = initial_leagues_history_count + new_leagues
            new_users = (
                None if initial_queued_users is None else queued_users - initial_queued_users + users
            )
            new_users_per_user = (
                None
                if new_users is None
                else safe_div(new_users, users)
            )
            rolling_snapshots.append((users, new_leagues, new_users))
            while rolling_snapshots and users - rolling_snapshots[0][0] > rolling_window_users:
                rolling_snapshots.popleft()
            rolling_baseline = rolling_snapshots[0]
            rolling_users = users - rolling_baseline[0]
            rolling_new_leagues_per_user = (
                None
                if rolling_users <= 0
                else safe_div(new_leagues - rolling_baseline[1], rolling_users)
            )
            rolling_new_users_per_user = (
                None
                if rolling_users <= 0 or new_users is None or rolling_baseline[2] is None
                else safe_div(new_users - rolling_baseline[2], rolling_users)
            )
            if timing_collector is None:
                leagues_history_count = (
                    f", leagues_history ~{estimated_rows} rows"
                    if estimated_rows is not None
                    else ""
                )
                console.print(
                    "Sleeper discovery: "
                    f"{users} users, {leagues_seen} leagues seen, {new_leagues} new leagues, "
                    f"{league_users} league-user edges, "
                    f"{queued_users} queued"
                    f"{leagues_history_count}"
                )
                return

            console.print()
            console.print(
                discovery_timing_table(
                    users=users,
                    progress_every=every,
                    average_seconds_per_interval=average_seconds_per_interval,
                    leagues_seen=leagues_seen,
                    new_leagues=new_leagues,
                    rolling_new_leagues_per_user=rolling_new_leagues_per_user,
                    new_users=new_users,
                    league_users=league_users,
                    queued_users=queued_users,
                    new_users_per_user=new_users_per_user,
                    rolling_new_users_per_user=rolling_new_users_per_user,
                    estimated_rows=estimated_rows,
                    timing_collector=timing_collector,
                )
            )

    return print_progress


def discovery_timing_table(
    *,
    users: int,
    progress_every: int,
    average_seconds_per_interval: float | None,
    leagues_seen: int,
    new_leagues: int,
    rolling_new_leagues_per_user: float | None,
    new_users: int | None,
    league_users: int,
    queued_users: int,
    new_users_per_user: float | None,
    rolling_new_users_per_user: float | None,
    estimated_rows: int | None,
    timing_collector: DiscoveryTiming,
) -> Table:
    """Build a Rich table for Sleeper discovery timing metrics."""
    snapshot = timing_collector.snapshot()
    elapsed_minutes = max(snapshot.elapsed_seconds / 60, 1e-9)
    total_tracked_seconds = (
        snapshot.request_seconds + snapshot.throttle_wait_seconds + snapshot.flush_seconds
    )
    http_share = timing_share(snapshot.request_seconds, total_tracked_seconds)
    throttle_share = timing_share(snapshot.throttle_wait_seconds, total_tracked_seconds)
    flush_share = timing_share(snapshot.flush_seconds, total_tracked_seconds)
    table = Table(title="Sleeper Discovery Progress")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_column("Notes", justify="right")

    table.add_row("Uptime", format_duration(snapshot.elapsed_seconds), "")
    table.add_section()
    table.add_row(
        "Users expanded",
        str(users),
        format_interval_duration(average_seconds_per_interval, progress_every),
    )
    table.add_row(
        "New leagues",
        str(new_leagues),
        format_rate_with_rolling(
            safe_div(new_leagues, users),
            rolling_new_leagues_per_user,
        ),
    )
    table.add_row(
        "New users",
        "" if new_users is None else str(new_users),
        format_rate_with_rolling(new_users_per_user, rolling_new_users_per_user),
    )
    if estimated_rows is not None:
        table.add_row("Unique leagues", str(estimated_rows), "")
    table.add_row("Queued users", str(queued_users), "")
    table.add_section()
    table.add_row("Requests", str(snapshot.request_count), f"{snapshot.request_count / elapsed_minutes:.1f}/min")
    table.add_row(
        "Avg request",
        format_seconds(safe_div(snapshot.request_seconds, snapshot.request_count)),
        "",
    )
    table.add_row("HTTP time", format_seconds(snapshot.request_seconds), http_share or "")
    table.add_row(
        "Throttle wait time",
        format_seconds(snapshot.throttle_wait_seconds),
        throttle_share or "",
    )
    table.add_row("Flush time", format_seconds(snapshot.flush_seconds), flush_share or "")
    table.add_section()
    table.add_row("Flushes", str(snapshot.flush_count), "")
    table.add_row("Retries", str(snapshot.retry_count), format_seconds(snapshot.retry_wait_seconds))
    if snapshot.retry_reasons:
        retry_reasons = ", ".join(
            f"{reason}={count}" for reason, count in sorted(snapshot.retry_reasons.items())
        )
        table.add_row("Retry reasons", retry_reasons, "")
    return table


def safe_div(numerator: float, denominator: float) -> float:
    """Divide two numbers while returning zero for a zero denominator."""
    if denominator == 0:
        return 0.0
    return numerator / denominator


def format_seconds(seconds: float) -> str:
    """Format seconds as milliseconds or seconds for CLI output."""
    if seconds < 1:
        return f"{seconds * 1000:.0f} ms"
    return f"{seconds:.1f} s"


def format_interval_duration(seconds: float | None, progress_every: int) -> str:
    """Format elapsed time for one progress interval."""
    if seconds is None:
        return ""
    return f"{format_duration(seconds)}/{progress_every}"


def format_signed_rate(value: float | None) -> str:
    """Format an optional signed per-user rate for CLI notes."""
    if value is None:
        return ""
    return f"{value:+.2f}/user"


def format_new_user_rate(value: float | None) -> str:
    """Format an optional cumulative new-user discovery rate."""
    if value is None:
        return ""
    return f"+{value:.2f}/user"


def format_rate_with_rolling(cumulative: float | None, rolling: float | None) -> str:
    """Format cumulative and rolling per-user rates for progress notes."""
    cumulative_text = format_signed_rate(cumulative)
    if rolling is None:
        return cumulative_text
    rolling_text = format_signed_rate(rolling)
    if not cumulative_text:
        return f"({rolling_text})"
    return f"{cumulative_text} ({rolling_text})"


def timing_share(seconds: float, total_seconds: float) -> str | None:
    """Format one timing component's share of tracked runtime."""
    if total_seconds <= 0:
        return None
    return f"{seconds / total_seconds:.1%}"


def format_duration(seconds: float) -> str:
    """Format elapsed duration as hours, minutes, and seconds."""
    total_seconds = int(seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def load_env_value(name: str, env_path: Path = Path(".env")) -> str | None:
    """Load one key from a simple dotenv file."""
    if not env_path.exists():
        return None

    for line in env_path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator and key.strip().lstrip("\ufeff") == name:
            return value.strip().strip("\"'")
    return None


def progress_printer(every: int):
    """Build a generic periodic progress callback."""
    if every <= 0:
        return None

    def print_progress(current: int, total: int, status: str) -> None:
        """Print periodic current-total progress."""
        if current == 1 or current % every == 0 or current == total:
            console.print(f"RosterAudit history: {current}/{total} {status}")

    return print_progress


def trade_sample_progress_printer(every: int):
    """Build a periodic Sleeper trade sample progress callback."""
    if every <= 0:
        return None

    def print_progress(current: int, total: int, trades: int, league_id: str) -> None:
        """Print sampled trade ingestion progress."""
        if current == 1 or current % every == 0 or current == total:
            console.print(
                f"Sleeper trade sample: {current}/{total} leagues, "
                f"{trades} trades, latest league {league_id}"
            )

    return print_progress


def roster_sample_progress_printer(every: int):
    """Build a periodic Sleeper roster sample progress callback."""
    if every <= 0:
        return None

    def print_progress(current: int, total: int, rosters: int, league_id: str) -> None:
        """Print sampled roster ingestion progress."""
        if current == 1 or current % every == 0 or current == total:
            console.print(
                f"Sleeper roster sample: {current}/{total} leagues, "
                f"{rosters} rosters, latest league {league_id}"
            )

    return print_progress

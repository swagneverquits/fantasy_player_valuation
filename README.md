# Fantasy Player Valuation

Research tools for evaluating fantasy football player trade values and building better valuation models.

The project starts from two questions:

1. Which public valuation sources are actually good?
2. Can we improve on them with a transparent ensemble that accounts for format, scoring, market behavior, and future production?

## Scope

This project is about player valuation for trades in 12-team superflex PPR leagues. It is not a lineup optimizer. The first milestone is a reproducible research pipeline that compares public values against realized outcomes.

Default league assumptions:

- 12 teams.
- Superflex.
- Full PPR scoring: 1 point per reception.
- 4-point passing touchdowns.
- No tight end premium.
- Otherwise common/default fantasy scoring assumptions, not zero-PPR "standard scoring."

## Candidate Sources

Initial source universe:

- KeepTradeCut: crowdsourced keep/trade/cut rankings and values.
- RosterAudit: rankings and trade tools derived from real Sleeper trade data.

We can add other sources later, but the first research pass should stay narrow. KeepTradeCut and RosterAudit are useful together because they represent two different market lenses: stated crowd preference versus observed trade behavior.

Some sources may not have public APIs or may restrict scraping. The source registry should record access method and terms before ingestion.

## Research Direction

Public trade-value sites are measuring different things:

- Market price: what managers are currently willing to pay.
- Expert projection: what analysts think players should be worth.
- Production value: expected future fantasy points above replacement.
- Dynasty asset value: production plus age, insulation, role security, and liquidity.
- Trade utility: value conditional on roster needs, playoff window, and replacement level within the project league format.

A better system likely combines all of these instead of trying to find one universal chart.

## Quick Start

```powershell
cd C:\dev\fantasy_player_valuation
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
ffvaluation sources
```

## Project Layout

```text
data/
  raw/
    rosteraudit/
      rankings/
        history.csv
      value_history/
    sleeper/
      discovery/
        user_frontier.csv
        users_history.csv
        leagues_history.csv
        league_users_history.csv
      trades/
        history.csv
  scratch/
    rosteraudit/
    sleeper/
plans/
  20260608-valuation_research_plan.md
src/ffvaluation/
  models.py
  ingestion/
    snapshots.py
  sources/
    registry.py
    rosteraudit/
      client.py
    sleeper/
      client.py
  evaluation/
    metrics.py
```

Canonical source pulls go under `data/raw/<source>/<dataset>/YYYYMMDD.csv`.
Ad hoc smoke runs, debug exports, and partial samples go under `data/scratch/<source>/`.
Source-specific collectors and helpers live under `src/ffvaluation/sources/<source>/`.

RosterAudit current rankings are the normal daily pull:

```powershell
ffvaluation pull-rosteraudit
```

That writes a dated raw snapshot and upserts the same rows into:

```text
data/raw/rosteraudit/rankings/history.csv
```

RosterAudit value history is a slow backfill/recovery pull. By default it waits
5 seconds between player-page calls to avoid rate limits, writes after each
player, and can resume if a run is interrupted:

```powershell
ffvaluation pull-rosteraudit-history
```

If you need a different pace, override the delay:

```powershell
ffvaluation pull-rosteraudit-history --sleep-seconds 8
```

Sleeper trade history pulls require a league ID. The command fetches completed
trade transactions by round/week, follows `previous_league_id` for at most two
league seasons by default, keeps trades from the past 365 days, writes a dated
raw snapshot, and upserts:

```powershell
ffvaluation pull-sleeper-trades --league-id <league_id>
```

Default outputs:

```text
data/raw/sleeper/trades/YYYYMMDD.csv
data/raw/sleeper/trades/history.csv
```

To discover candidate Sleeper leagues from a seed username, seed the frontier
once and then expand it in repeatable batches:

```powershell
ffvaluation seed-sleeper-network --username <username>
ffvaluation expand-sleeper-network
```

Each expansion processes unexpanded frontier users, discovers their leagues,
adds league users back to the frontier, and upserts discovery CSVs after each
expanded user. For a larger batch:

```powershell
ffvaluation expand-sleeper-network --max-users 5000 --progress-every 50
```

Default outputs:

```text
data/raw/sleeper/discovery/users_history.csv
data/raw/sleeper/discovery/leagues_history.csv
data/raw/sleeper/discovery/league_users_history.csv
data/raw/sleeper/discovery/user_frontier.csv
```

Discovery history tables use date-level capture columns to keep the raw files
compact. `users_history.csv` stores `captured_date,user_id,display_name`, and
`league_users_history.csv` is a lean edge table:
`captured_date,league_id,league_season,user_id`. `leagues_history.csv` flattens
league settings, scoring settings, and roster slot counts into prefixed columns
instead of storing JSON blobs.

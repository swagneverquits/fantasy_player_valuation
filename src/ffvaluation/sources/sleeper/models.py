from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


TRADE_HISTORY_COLUMNS = [
    "captured_at",
    "league_id",
    "league_name",
    "league_season",
    "previous_league_id",
    "round",
    "transaction_id",
    "status",
    "created",
    "created_at",
    "status_updated",
    "status_updated_at",
    "roster_ids",
    "consenter_ids",
    "adds",
    "drops",
    "draft_picks",
    "waiver_budget",
    "total_rosters",
    "is_dynasty",
    "is_superflex",
    "ppr",
    "te_premium",
    "target_format_guess",
    "league_settings",
    "scoring_settings",
    "roster_positions",
]
USER_DISCOVERY_COLUMNS = [
    "captured_date",
    "user_id",
    "username",
    "display_name",
]
LEAGUE_DISCOVERY_COLUMNS = [
    "captured_date",
    "league_id",
    "league_name",
    "league_season",
    "previous_league_id",
    "total_rosters",
    "is_dynasty",
    "is_superflex",
    "ppr",
    "te_premium",
    "target_format_guess",
    "league_settings",
    "scoring_settings",
    "roster_positions",
]
LEAGUE_USER_DISCOVERY_COLUMNS = [
    "captured_date",
    "league_id",
    "league_season",
    "user_id",
]
USER_FRONTIER_COLUMNS = [
    "user_id",
    "username",
    "display_name",
    "discovered_at",
    "discovered_from_league_id",
    "expanded_at",
]


@dataclass(frozen=True)
class SleeperTradeRow:
    captured_at: datetime
    league_id: str
    league_name: str
    league_season: str
    previous_league_id: str | None
    round: int
    transaction_id: str
    status: str
    created: int | None
    created_at: datetime | None
    status_updated: int | None
    status_updated_at: datetime | None
    roster_ids: list[int]
    consenter_ids: list[int]
    adds: dict[str, int] | None
    drops: dict[str, int] | None
    draft_picks: list[dict[str, Any]]
    waiver_budget: list[dict[str, Any]]
    total_rosters: int | None
    is_dynasty: bool | None
    is_superflex: bool
    ppr: float | None
    te_premium: float
    target_format_guess: bool
    league_settings: dict[str, Any]
    scoring_settings: dict[str, Any]
    roster_positions: list[str]


@dataclass(frozen=True)
class SleeperUserRow:
    captured_at: datetime
    user_id: str
    username: str
    display_name: str


@dataclass(frozen=True)
class SleeperLeagueRow:
    captured_at: datetime
    league_id: str
    league_name: str
    league_season: str
    previous_league_id: str | None
    total_rosters: int | None
    is_dynasty: bool | None
    is_superflex: bool
    ppr: float | None
    te_premium: float
    target_format_guess: bool
    league_settings: dict[str, Any]
    scoring_settings: dict[str, Any]
    roster_positions: list[str]


@dataclass(frozen=True)
class SleeperLeagueUserRow:
    captured_at: datetime
    league_id: str
    league_season: str
    user_id: str


@dataclass(frozen=True)
class SleeperDiscoveryResult:
    users: list[SleeperUserRow]
    leagues: list[SleeperLeagueRow]
    league_users: list[SleeperLeagueUserRow]


@dataclass(frozen=True)
class SleeperFrontierRow:
    user_id: str
    username: str
    display_name: str
    discovered_at: datetime
    discovered_from_league_id: str | None
    expanded_at: datetime | None


@dataclass(frozen=True)
class SleeperFrontierExpansionResult:
    users: list[SleeperUserRow]
    leagues: list[SleeperLeagueRow]
    league_users: list[SleeperLeagueUserRow]
    frontier: list[SleeperFrontierRow]
    expanded_users: int

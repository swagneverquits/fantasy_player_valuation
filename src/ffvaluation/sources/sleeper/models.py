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
    "display_name",
]
LEAGUE_SETTING_KEYS = [
    "bench_lock",
    "best_ball",
    "capacity_override",
    "commissioner_direct_invite",
    "daily_waivers",
    "daily_waivers_base",
    "daily_waivers_days",
    "daily_waivers_hour",
    "daily_waivers_last_ran",
    "deleted",
    "disable_adds",
    "disable_elimination",
    "disable_trades",
    "divisions",
    "draft_rounds",
    "faab_suggestions",
    "last_chopped_leg",
    "last_report",
    "last_scored_leg",
    "league_average_match",
    "leg",
    "max_keepers",
    "max_subs",
    "num_teams",
    "offseason_adds",
    "pick_timer",
    "pick_trading",
    "playoff_round_type",
    "playoff_seed_type",
    "playoff_teams",
    "playoff_type",
    "playoff_week_start",
    "position_limit_db",
    "position_limit_def",
    "position_limit_dl",
    "position_limit_k",
    "position_limit_lb",
    "position_limit_qb",
    "position_limit_rb",
    "position_limit_te",
    "position_limit_wr",
    "reserve_allow_cov",
    "reserve_allow_dnr",
    "reserve_allow_doubtful",
    "reserve_allow_na",
    "reserve_allow_out",
    "reserve_allow_sus",
    "reserve_slots",
    "squads",
    "start_week",
    "sub_lock_if_starter_active",
    "sub_start_time_eligibility",
    "taxi_allow_vets",
    "taxi_deadline",
    "taxi_slots",
    "taxi_years",
    "trade_deadline",
    "trade_review_days",
    "type",
    "veto_auto_poll",
    "veto_show_votes",
    "veto_votes_needed",
    "waiver_bid_min",
    "waiver_budget",
    "waiver_clear_days",
    "waiver_day_of_week",
    "waiver_type",
    "was_auto_archived",
]
SCORING_SETTING_KEYS = [
    "blk_kick",
    "blk_kick_ret_yd",
    "bonus_def_fum_td_50p",
    "bonus_def_int_td_50p",
    "bonus_fd_qb",
    "bonus_fd_rb",
    "bonus_fd_te",
    "bonus_fd_wr",
    "bonus_pass_cmp_25",
    "bonus_pass_yd_300",
    "bonus_pass_yd_400",
    "bonus_rec_rb",
    "bonus_rec_te",
    "bonus_rec_wr",
    "bonus_rec_yd_100",
    "bonus_rec_yd_200",
    "bonus_rush_att_20",
    "bonus_rush_rec_yd_100",
    "bonus_rush_rec_yd_200",
    "bonus_rush_yd_100",
    "bonus_rush_yd_200",
    "bonus_sack_2p",
    "bonus_tkl_10p",
    "def_2pt",
    "def_3_and_out",
    "def_4_and_stop",
    "def_forced_punts",
    "def_kr_td",
    "def_kr_yd",
    "def_pass_def",
    "def_pr_td",
    "def_pr_yd",
    "def_st_ff",
    "def_st_fum_rec",
    "def_st_td",
    "def_st_tkl_solo",
    "def_td",
    "ff",
    "fg_ret_yd",
    "fgm",
    "fgm_0_19",
    "fgm_20_29",
    "fgm_30_39",
    "fgm_40_49",
    "fgm_50_59",
    "fgm_50p",
    "fgm_60p",
    "fgm_yds",
    "fgm_yds_over_30",
    "fgmiss",
    "fgmiss_0_19",
    "fgmiss_20_29",
    "fgmiss_30_39",
    "fgmiss_40_49",
    "fgmiss_50_59",
    "fgmiss_50p",
    "fgmiss_60p",
    "fum",
    "fum_lost",
    "fum_rec",
    "fum_rec_td",
    "fum_ret_yd",
    "idp_blk_kick",
    "idp_def_td",
    "idp_ff",
    "idp_fum_rec",
    "idp_fum_ret_yd",
    "idp_int",
    "idp_int_ret_yd",
    "idp_pass_def",
    "idp_pass_def_3p",
    "idp_qb_hit",
    "idp_sack",
    "idp_sack_yd",
    "idp_safe",
    "idp_tkl",
    "idp_tkl_ast",
    "idp_tkl_loss",
    "idp_tkl_solo",
    "int",
    "int_ret_yd",
    "kr_td",
    "kr_yd",
    "pass_2pt",
    "pass_att",
    "pass_cmp",
    "pass_cmp_40p",
    "pass_fd",
    "pass_inc",
    "pass_int",
    "pass_int_td",
    "pass_sack",
    "pass_td",
    "pass_td_40p",
    "pass_td_50p",
    "pass_yd",
    "pr_td",
    "pr_yd",
    "pts_allow",
    "pts_allow_0",
    "pts_allow_14_20",
    "pts_allow_1_6",
    "pts_allow_21_27",
    "pts_allow_28_34",
    "pts_allow_35p",
    "pts_allow_7_13",
    "qb_hit",
    "rec",
    "rec_0_4",
    "rec_10_19",
    "rec_20_29",
    "rec_2pt",
    "rec_30_39",
    "rec_40p",
    "rec_5_9",
    "rec_fd",
    "rec_td",
    "rec_td_40p",
    "rec_td_50p",
    "rec_yd",
    "rush_2pt",
    "rush_40p",
    "rush_att",
    "rush_fd",
    "rush_td",
    "rush_td_40p",
    "rush_td_50p",
    "rush_yd",
    "sack",
    "sack_yd",
    "safe",
    "st_ff",
    "st_fum_rec",
    "st_td",
    "st_tkl_solo",
    "tkl",
    "tkl_ast",
    "tkl_loss",
    "tkl_solo",
    "xpm",
    "xpmiss",
    "yds_allow",
    "yds_allow_0_100",
    "yds_allow_100_199",
    "yds_allow_200_299",
    "yds_allow_300_349",
    "yds_allow_350_399",
    "yds_allow_400_449",
    "yds_allow_450_499",
    "yds_allow_500_549",
    "yds_allow_550p",
]
ROSTER_POSITION_KEYS = [
    "BN",
    "DB",
    "DEF",
    "DL",
    "FLEX",
    "IDP_FLEX",
    "K",
    "LB",
    "QB",
    "RB",
    "REC_FLEX",
    "SUPER_FLEX",
    "TE",
    "WR",
    "WRRB_FLEX",
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
] + [f"league_setting_{key}" for key in LEAGUE_SETTING_KEYS]
LEAGUE_DISCOVERY_COLUMNS += [f"scoring_{key}" for key in SCORING_SETTING_KEYS]
LEAGUE_DISCOVERY_COLUMNS += [f"roster_{key}" for key in ROSTER_POSITION_KEYS]
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

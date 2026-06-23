"""Compatibility facade for Sleeper trade fetch/save/analysis helpers."""

from ffvaluation.sources.sleeper.analysis.trades import (
    TRADE_SIDE_COLUMNS,
    sample_league_ids_from_discovery,
    trade_sides_dataframe,
    trade_sides_from_sqlite,
)
from ffvaluation.sources.sleeper.fetch.trades import (
    fetch_trade_history,
    fetch_trade_sample,
    iter_league_chain,
    trade_row,
)
from ffvaluation.sources.sleeper.save.trades import (
    copy_trade_sample_leagues_sqlite,
    format_trade_row,
    upsert_trade_history_csv,
    upsert_trade_history_sqlite,
    write_trade_history_csv,
)

__all__ = [
    "TRADE_SIDE_COLUMNS",
    "copy_trade_sample_leagues_sqlite",
    "fetch_trade_history",
    "fetch_trade_sample",
    "format_trade_row",
    "iter_league_chain",
    "sample_league_ids_from_discovery",
    "trade_row",
    "trade_sides_dataframe",
    "trade_sides_from_sqlite",
    "upsert_trade_history_csv",
    "upsert_trade_history_sqlite",
    "write_trade_history_csv",
]

from __future__ import annotations

from ffvaluation.models import SourceDefinition, ValuationType


DEFAULT_SOURCES: list[SourceDefinition] = [
    SourceDefinition(
        name="KeepTradeCut",
        url="https://keeptradecut.com/",
        valuation_type=ValuationType.CROWD,
        supported_formats=["dynasty", "superflex", "ppr"],
        access_method=(
            "public rankings page embeds player valuation data in page HTML; robots.txt allows /; "
            "no documented public API or terms page found"
        ),
        notes=(
            "Crowdsourced keep/trade/cut voting produces rankings and values. "
            "Use conservative, low-frequency snapshot pulls unless written permission or a documented "
            "API is found."
        ),
    ),
    SourceDefinition(
        name="RosterAudit",
        url="https://rosteraudit.com/rankings/",
        valuation_type=ValuationType.MARKET,
        supported_formats=["dynasty", "superflex", "ppr"],
        access_method=(
            "documented public JSON API at https://rosteraudit.com/wp-json/ra/v1; "
            "rankings endpoint supports format, position, pagination, and league_size"
        ),
        notes=(
            "Public pages describe values derived from real Sleeper trade data. API terms allow "
            "personal and non-commercial use with attribution and rate limits."
        ),
        update_frequency="live/current public API",
    ),
]


def list_sources() -> list[SourceDefinition]:
    return DEFAULT_SOURCES.copy()

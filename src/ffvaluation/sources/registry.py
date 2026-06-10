from __future__ import annotations

from ffvaluation.models import SourceDefinition, ValuationType


DEFAULT_SOURCES: list[SourceDefinition] = [
    SourceDefinition(
        name="KeepTradeCut",
        url="https://keeptradecut.com/",
        valuation_type=ValuationType.CROWD,
        supported_formats=["dynasty", "superflex", "ppr"],
        access_method="public site; scraping/API terms to verify",
        notes="Crowdsourced keep/trade/cut voting produces rankings and values.",
    ),
    SourceDefinition(
        name="RosterAudit",
        url="https://rosteraudit.com/rankings/",
        valuation_type=ValuationType.MARKET,
        supported_formats=["dynasty", "superflex", "ppr"],
        access_method="public site; scraping/API terms to verify",
        notes="Public pages describe values derived from real Sleeper trade data.",
    ),
]


def list_sources() -> list[SourceDefinition]:
    return DEFAULT_SOURCES.copy()

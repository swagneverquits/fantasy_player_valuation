from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class ValuationType(StrEnum):
    MARKET = "market"
    EXPERT = "expert"
    PROJECTION = "projection"
    ADP = "adp"
    CROWD = "crowd"
    TRADE_DERIVED = "trade_derived"


class FantasyFormat(BaseModel):
    name: str = "12-team superflex PPR"
    dynasty: bool = False
    superflex: bool = True
    ppr: float = 1.0
    tight_end_premium: float = 0.0
    teams: int = 12
    passing_touchdown_points: float = 4.0
    scoring_notes: str = "Full PPR; otherwise common/default scoring, not zero-PPR standard."


DEFAULT_FORMAT = FantasyFormat()


class Player(BaseModel):
    player_id: str
    name: str
    position: str
    team: str | None = None
    age: float | None = None


class ValuationSnapshot(BaseModel):
    source: str
    captured_at: datetime
    season: int
    week: int | None = None
    format: FantasyFormat
    player_id: str
    rank: int | None = None
    raw_value: float | None = None
    normalized_value: float | None = None


class SourceDefinition(BaseModel):
    name: str
    url: str
    valuation_type: ValuationType
    supported_formats: list[str] = Field(default_factory=list)
    access_method: str
    update_frequency: str | None = None
    historical_access: str | None = None
    notes: str | None = None

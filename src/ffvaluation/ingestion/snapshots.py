from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

from ffvaluation.models import DEFAULT_FORMAT, Player, ValuationSnapshot
from ffvaluation.sources.registry import list_sources


SNAPSHOT_COLUMNS = [
    "source",
    "captured_at",
    "season",
    "week",
    "player_id",
    "player_name",
    "position",
    "team",
    "rank",
    "raw_value",
]


class ManualSnapshotRow(BaseModel):
    player: Player
    valuation: ValuationSnapshot


def load_manual_snapshot(path: str | Path) -> list[ManualSnapshotRow]:
    path = Path(path)
    with path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        validate_snapshot_columns(reader.fieldnames or [])
        return [_parse_row(row, row_number=index + 2) for index, row in enumerate(reader)]


def validate_snapshot_columns(columns: list[str]) -> None:
    missing = [column for column in SNAPSHOT_COLUMNS if column not in columns]
    if missing:
        raise ValueError(f"Missing required snapshot columns: {', '.join(missing)}")


def _parse_row(row: dict[str, str], *, row_number: int) -> ManualSnapshotRow:
    source = row["source"].strip()
    valid_sources = {source_definition.name for source_definition in list_sources()}
    if source not in valid_sources:
        raise ValueError(f"Row {row_number}: unsupported source {source!r}")

    player_id = row["player_id"].strip()
    if not player_id:
        raise ValueError(f"Row {row_number}: player_id is required")

    player = Player(
        player_id=player_id,
        name=row["player_name"].strip(),
        position=row["position"].strip().upper(),
        team=row["team"].strip() or None,
    )
    valuation = ValuationSnapshot(
        source=source,
        captured_at=datetime.fromisoformat(row["captured_at"].strip()),
        season=int(row["season"]),
        week=_optional_int(row["week"]),
        format=DEFAULT_FORMAT,
        player_id=player_id,
        rank=_optional_int(row["rank"]),
        raw_value=_optional_float(row["raw_value"]),
    )
    return ManualSnapshotRow(player=player, valuation=valuation)


def _optional_int(value: str) -> int | None:
    stripped = value.strip()
    return int(stripped) if stripped else None


def _optional_float(value: str) -> float | None:
    stripped = value.strip()
    return float(stripped) if stripped else None


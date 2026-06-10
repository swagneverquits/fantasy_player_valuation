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
SNAPSHOT_HISTORY_COLUMNS = [
    "source",
    "captured_at",
    "as_of_date",
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


def write_snapshot_csv(rows: list[ManualSnapshotRow], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=SNAPSHOT_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(_format_row(row))

    return path


def upsert_snapshot_history_csv(
    rows: list[ManualSnapshotRow],
    path: str | Path,
    *,
    as_of_date: str,
) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    merged_rows: dict[tuple[str, str, str], dict[str, str]] = {}

    if path.exists():
        with path.open(newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                key = (row["source"], row["as_of_date"], row["player_id"])
                merged_rows[key] = {
                    field: row.get(field, "") for field in SNAPSHOT_HISTORY_COLUMNS
                }

    for row in rows:
        formatted = _format_row(row)
        formatted["as_of_date"] = as_of_date
        key = (formatted["source"], formatted["as_of_date"], formatted["player_id"])
        merged_rows[key] = {
            field: formatted.get(field, "") for field in SNAPSHOT_HISTORY_COLUMNS
        }

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=SNAPSHOT_HISTORY_COLUMNS)
        writer.writeheader()
        writer.writerows(
            row
            for _key, row in sorted(
                merged_rows.items(),
                key=lambda item: (
                    item[1]["source"],
                    item[1]["as_of_date"],
                    _optional_sort_int(item[1]["rank"]),
                    item[1]["player_name"],
                    item[1]["player_id"],
                ),
            )
        )

    return path


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


def _optional_sort_int(value: str) -> int:
    stripped = value.strip()
    return int(stripped) if stripped else 1_000_000


def _format_row(row: ManualSnapshotRow) -> dict[str, str]:
    valuation = row.valuation
    return {
        "source": valuation.source,
        "captured_at": valuation.captured_at.isoformat(),
        "season": str(valuation.season),
        "week": "" if valuation.week is None else str(valuation.week),
        "player_id": row.player.player_id,
        "player_name": row.player.name,
        "position": row.player.position,
        "team": row.player.team or "",
        "rank": "" if valuation.rank is None else str(valuation.rank),
        "raw_value": "" if valuation.raw_value is None else f"{valuation.raw_value:g}",
    }

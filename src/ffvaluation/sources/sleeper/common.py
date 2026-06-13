from __future__ import annotations

import csv
import json
import os
import socket
import time
import uuid
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BASE_URL = "https://api.sleeper.app/v1"

FetchJson = Callable[[str], Any]
DiscoveryProgressCallback = Callable[[int, int, int, int], None]


def league_url(league_id: str) -> str:
    return f"{BASE_URL}/league/{league_id}"


def user_url(user_ref: str) -> str:
    return f"{BASE_URL}/user/{user_ref}"


def user_leagues_url(*, user_id: str, season: str) -> str:
    return f"{BASE_URL}/user/{user_id}/leagues/nfl/{season}"


def league_users_url(league_id: str) -> str:
    return f"{BASE_URL}/league/{league_id}/users"


def transactions_url(league_id: str, round_number: int) -> str:
    return f"{BASE_URL}/league/{league_id}/transactions/{round_number}"


def fetch_json(
    url: str,
    *,
    attempts: int = 5,
    timeout_seconds: float = 30,
    backoff_seconds: float = 2,
) -> Any:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0",
        },
    )
    for attempt in range(1, attempts + 1):
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            if error.code not in (429, 500, 502, 503, 504) or attempt == attempts:
                raise
            time.sleep(_retry_delay(attempt, backoff_seconds, error))
        except (TimeoutError, socket.timeout, URLError, ConnectionResetError) as error:
            if not _is_retryable_network_error(error) or attempt == attempts:
                raise
            time.sleep(_retry_delay(attempt, backoff_seconds))

    raise RuntimeError(f"Failed to fetch {url}")


def upsert_csv(
    *,
    rows: Iterable[dict[str, str]],
    path: str | Path,
    fieldnames: list[str],
    key_fields: tuple[str, ...],
    sort_fields: tuple[str, ...],
) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    merged_rows: dict[tuple[str, ...], dict[str, str]] = {}

    if path.exists():
        with path.open(newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                key = tuple(row.get(field, "") for field in key_fields)
                if all(key):
                    merged_rows[key] = {field: row.get(field, "") for field in fieldnames}

    for row in rows:
        key = tuple(row[field] for field in key_fields)
        merged_rows[key] = {field: row.get(field, "") for field in fieldnames}

    temp_path = path.with_name(f"{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    with temp_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(
            row
            for _key, row in sorted(
                merged_rows.items(),
                key=lambda item: tuple(item[1][field] for field in sort_fields),
            )
        )
    _replace_with_retry(temp_path, path)

    return path


def _replace_with_retry(source: Path, target: Path, *, attempts: int = 10) -> None:
    for attempt in range(attempts):
        try:
            source.replace(target)
            return
        except PermissionError as error:
            if attempt == attempts - 1:
                raise PermissionError(
                    f"Could not replace {target}. Close any program reading it "
                    "or stop other discovery runs, then retry. "
                    f"Completed temp file remains at {source}."
                ) from error
            time.sleep(0.5 * (attempt + 1))


def _retry_delay(
    attempt: int,
    backoff_seconds: float,
    error: HTTPError | None = None,
) -> float:
    retry_after = error.headers.get("Retry-After") if error is not None else None
    if retry_after is not None:
        try:
            return max(float(retry_after), 0.0)
        except ValueError:
            pass
    return backoff_seconds * attempt


def _is_retryable_network_error(error: BaseException) -> bool:
    if isinstance(error, (TimeoutError, socket.timeout, ConnectionResetError)):
        return True
    if isinstance(error, URLError):
        return isinstance(error.reason, (TimeoutError, socket.timeout, ConnectionResetError))
    return False


def millis_to_datetime(value: Any) -> datetime | None:
    timestamp = optional_int(value)
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp / 1000, tz=UTC)


def is_dynasty(league: dict[str, Any]) -> bool | None:
    settings = league.get("settings") or {}
    metadata = league.get("metadata") or {}
    if "type" in settings:
        return int(settings["type"]) == 2

    league_name = str(league.get("name") or "").lower()
    description = str(metadata.get("description") or "").lower()
    if "dynasty" in league_name or "dynasty" in description:
        return True
    return None


def te_premium(scoring_settings: dict[str, Any], ppr: float | None) -> float:
    if "bonus_rec_te" in scoring_settings:
        return optional_float(scoring_settings["bonus_rec_te"]) or 0.0
    if "rec_te" in scoring_settings and ppr is not None:
        return max(0.0, (optional_float(scoring_settings["rec_te"]) or ppr) - ppr)
    return 0.0


def dumps_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def optional_bool(value: bool | None) -> str:
    if value is None:
        return ""
    return str(value).lower()


def user_id(user: Any) -> str | None:
    if not isinstance(user, dict):
        return None
    return optional_str(user.get("user_id") or user.get("uid"))


def optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def optional_str(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)

from __future__ import annotations

from collections.abc import Callable, Collection
from datetime import UTC, datetime
from typing import Any


def parse_int_field(
    value: Any,
    *,
    field: str,
    error_factory: Callable[[str, str], Exception],
    minimum: int | None = None,
) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise error_factory(field, f"{field} must be an integer")
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = int(value)
        except ValueError as exc:
            raise error_factory(field, f"{field} must be an integer") from exc
    else:
        raise error_factory(field, f"{field} must be an integer")

    if minimum is not None and parsed < minimum:
        raise error_factory(field, f"{field} must be >= {minimum}")
    return parsed


def parse_string_field(
    value: Any,
    *,
    field: str,
    error_factory: Callable[[str, str], Exception],
) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise error_factory(field, f"{field} must be a string")
    normalized = value.strip()
    return normalized or None


def parse_bool_field(
    value: Any,
    *,
    field: str,
    error_factory: Callable[[str, str], Exception],
    true_values: Collection[str] = ("true", "1", "yes", "on"),
    false_values: Collection[str] = ("false", "0", "no", "off"),
) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in true_values:
            return True
        if normalized in false_values:
            return False
    raise error_factory(field, f"{field} must be a boolean")


def parse_timestamp_field(
    value: Any,
    *,
    field: str,
    error_factory: Callable[[str, str], Exception],
) -> datetime:
    if not isinstance(value, str):
        raise error_factory(field, f"{field} must be a valid ISO 8601 timestamp.")
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise error_factory(field, f"{field} must be a valid ISO 8601 timestamp.") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


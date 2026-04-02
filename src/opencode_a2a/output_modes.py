from __future__ import annotations

from collections.abc import Collection
from typing import Any


def normalize_accepted_output_modes(source: Any) -> tuple[str, ...] | None:
    accepted = getattr(source, "accepted_output_modes", None) or getattr(
        source, "acceptedOutputModes", None
    )
    if not isinstance(accepted, list):
        return None

    normalized: list[str] = []
    for value in accepted:
        if not isinstance(value, str):
            continue
        mode = value.strip().lower()
        if not mode or mode in normalized:
            continue
        normalized.append(mode)
    return tuple(normalized) or None


def accepts_output_mode(
    accepted_output_modes: Collection[str] | None,
    media_type: str,
) -> bool:
    return accepted_output_modes is None or media_type in accepted_output_modes

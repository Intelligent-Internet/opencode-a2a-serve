from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

_PROTOCOL_VERSION_PATTERN = re.compile(r"^(?P<major>\d+)\.(?P<minor>\d+)(?:\.\d+)?$")


class UnsupportedProtocolVersionError(ValueError):
    def __init__(
        self,
        requested_version: str,
        *,
        supported_protocol_versions: tuple[str, ...],
        default_protocol_version: str,
    ) -> None:
        self.requested_version = requested_version
        self.supported_protocol_versions = supported_protocol_versions
        self.default_protocol_version = default_protocol_version
        supported_display = ", ".join(supported_protocol_versions)
        super().__init__(
            f"Unsupported A2A protocol version {requested_version!r}. "
            f"Supported versions: {supported_display}."
        )


@dataclass(frozen=True)
class NegotiatedProtocolVersion:
    requested_version: str
    negotiated_version: str
    explicit: bool


def normalize_protocol_version(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("Protocol version must be a non-empty string.")
    match = _PROTOCOL_VERSION_PATTERN.fullmatch(normalized)
    if match is None:
        raise ValueError(
            "Protocol version must use Major.Minor or Major.Minor.Patch format."
        )
    return f"{match.group('major')}.{match.group('minor')}"


def normalize_protocol_versions(values: Iterable[str]) -> tuple[str, ...]:
    normalized_versions: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = normalize_protocol_version(str(value))
        if normalized in seen:
            continue
        seen.add(normalized)
        normalized_versions.append(normalized)
    if not normalized_versions:
        raise ValueError("At least one supported protocol version must be declared.")
    return tuple(normalized_versions)


def negotiate_protocol_version(
    *,
    header_value: str | None,
    query_value: str | None,
    default_protocol_version: str,
    supported_protocol_versions: Iterable[str],
) -> NegotiatedProtocolVersion:
    normalized_default = normalize_protocol_version(default_protocol_version)
    normalized_supported = normalize_protocol_versions(supported_protocol_versions)

    raw_header = (header_value or "").strip()
    raw_query = (query_value or "").strip()
    explicit = bool(raw_header or raw_query)
    raw_requested = raw_header or raw_query or normalized_default

    try:
        normalized_requested = normalize_protocol_version(raw_requested)
    except ValueError as exc:
        raise UnsupportedProtocolVersionError(
            raw_requested,
            supported_protocol_versions=normalized_supported,
            default_protocol_version=normalized_default,
        ) from exc

    if normalized_requested not in normalized_supported:
        raise UnsupportedProtocolVersionError(
            normalized_requested,
            supported_protocol_versions=normalized_supported,
            default_protocol_version=normalized_default,
        )

    return NegotiatedProtocolVersion(
        requested_version=normalized_requested,
        negotiated_version=normalized_requested,
        explicit=explicit,
    )


__all__ = [
    "NegotiatedProtocolVersion",
    "UnsupportedProtocolVersionError",
    "negotiate_protocol_version",
    "normalize_protocol_version",
    "normalize_protocol_versions",
]

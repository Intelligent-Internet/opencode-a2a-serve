from __future__ import annotations

from opencode_a2a.metadata_access import (
    extract_first_namespaced_string,
    extract_namespaced_value,
)


def test_extract_namespaced_value_returns_nested_metadata() -> None:
    metadata = {"opencode": {"workspace": {"id": "wrk-1"}}}

    assert (
        extract_namespaced_value(
            metadata,
            namespace="opencode",
            path=("workspace", "id"),
        )
        == "wrk-1"
    )


def test_extract_namespaced_value_returns_none_for_invalid_shape() -> None:
    metadata = {"opencode": {"workspace": "invalid"}}

    assert (
        extract_namespaced_value(
            metadata,
            namespace="opencode",
            path=("workspace", "id"),
        )
        is None
    )


def test_extract_first_namespaced_string_prefers_first_non_empty_value() -> None:
    sources = (
        {"opencode": {"directory": "  "}},
        {"opencode": {"directory": "services/api"}},
        {"opencode": {"directory": "services/worker"}},
    )

    assert (
        extract_first_namespaced_string(
            sources,
            namespace="opencode",
            path=("directory",),
        )
        == "services/api"
    )


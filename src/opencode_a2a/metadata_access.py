from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


def extract_namespaced_value(
    source: Mapping[str, Any] | None,
    *,
    namespace: str,
    path: tuple[str, ...],
) -> Any | None:
    if not isinstance(source, Mapping):
        return None

    current: Any = source.get(namespace)
    if not isinstance(current, Mapping):
        return None

    for part in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(part)
    return current


def extract_first_namespaced_string(
    sources: Iterable[Mapping[str, Any] | None],
    *,
    namespace: str,
    path: tuple[str, ...],
) -> str | None:
    for source in sources:
        candidate = extract_namespaced_value(source, namespace=namespace, path=path)
        if isinstance(candidate, str):
            value = candidate.strip()
            if value:
                return value
    return None

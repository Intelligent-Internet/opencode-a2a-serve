from __future__ import annotations

import logging
import re
import secrets
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any

TRACEPARENT_HEADER = "traceparent"
TRACESTATE_HEADER = "tracestate"
_MISSING_TRACE_ID = "-"
_TRACEPARENT_RE = re.compile(
    r"^(?P<version>[0-9a-f]{2})-(?P<trace_id>[0-9a-f]{32})-(?P<parent_id>[0-9a-f]{16})-(?P<flags>[0-9a-f]{2})$"
)
_current_trace_context: ContextVar[TraceContext | None] = ContextVar(
    "opencode_a2a_trace_context",
    default=None,
)
_log_record_factory_installed = False


@dataclass(frozen=True)
class TraceContext:
    traceparent: str
    trace_id: str
    tracestate: str | None = None


def _normalize_header_value(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def parse_traceparent(value: str | None) -> tuple[str, str] | None:
    normalized = _normalize_header_value(value)
    if normalized is None:
        return None
    lowered = normalized.lower()
    match = _TRACEPARENT_RE.fullmatch(lowered)
    if match is None:
        return None
    version = match.group("version")
    trace_id = match.group("trace_id")
    parent_id = match.group("parent_id")
    if version == "ff" or trace_id == ("0" * 32) or parent_id == ("0" * 16):
        return None
    return lowered, trace_id


def generate_traceparent() -> tuple[str, str]:
    trace_id = secrets.token_hex(16)
    parent_id = secrets.token_hex(8)
    return f"00-{trace_id}-{parent_id}-01", trace_id


def resolve_trace_context(
    traceparent_header: str | None,
    tracestate_header: str | None,
) -> TraceContext:
    parsed_traceparent = parse_traceparent(traceparent_header)
    if parsed_traceparent is None:
        traceparent, trace_id = generate_traceparent()
        return TraceContext(traceparent=traceparent, trace_id=trace_id, tracestate=None)
    traceparent, trace_id = parsed_traceparent
    return TraceContext(
        traceparent=traceparent,
        trace_id=trace_id,
        tracestate=_normalize_header_value(tracestate_header),
    )


def get_current_trace_context() -> TraceContext | None:
    return _current_trace_context.get()


def current_trace_headers() -> dict[str, str]:
    trace_context = get_current_trace_context()
    if trace_context is None:
        return {}
    headers = {TRACEPARENT_HEADER: trace_context.traceparent}
    if trace_context.tracestate:
        headers[TRACESTATE_HEADER] = trace_context.tracestate
    return headers


def set_current_trace_context(trace_context: TraceContext | None) -> Token[TraceContext | None]:
    return _current_trace_context.set(trace_context)


def reset_current_trace_context(token: Token[TraceContext | None]) -> None:
    _current_trace_context.reset(token)


@contextmanager
def bind_trace_context(trace_context: TraceContext | None) -> Iterator[None]:
    token = set_current_trace_context(trace_context)
    try:
        yield
    finally:
        reset_current_trace_context(token)


def install_log_record_factory() -> None:
    global _log_record_factory_installed
    if _log_record_factory_installed:
        return

    current_factory = logging.getLogRecordFactory()

    def _factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
        record = current_factory(*args, **kwargs)
        if not hasattr(record, "trace_id"):
            trace_context = get_current_trace_context()
            record.trace_id = (
                trace_context.trace_id if trace_context is not None else _MISSING_TRACE_ID
            )
        return record

    logging.setLogRecordFactory(_factory)
    _log_record_factory_installed = True

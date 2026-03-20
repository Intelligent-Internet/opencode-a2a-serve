from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import httpx
from a2a.types import Part, TaskState

from .opencode_client import UpstreamContractError

logger = logging.getLogger(__name__)


class BlockType(StrEnum):
    TEXT = "text"
    REASONING = "reasoning"
    TOOL_CALL = "tool_call"


@dataclass(frozen=True)
class _NormalizedStreamChunk:
    part: Part
    content_key: str
    accumulate_content: bool
    append: bool
    block_type: BlockType
    internal_source: str
    shared_source: str
    message_id: str | None
    role: str | None


@dataclass(frozen=True)
class _PendingDelta:
    field: str
    delta: str
    message_id: str | None


@dataclass
class _StreamPartState:
    block_type: BlockType
    message_id: str | None
    role: str | None
    buffer: str = ""
    saw_delta: bool = False


def _merge_token_usage(
    base: Mapping[str, Any] | None,
    incoming: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if base is None and incoming is None:
        return None
    merged: dict[str, Any] = dict(base) if base else {}
    if incoming:
        for key, value in incoming.items():
            if value is None:
                continue
            if key == "raw" and isinstance(value, Mapping):
                existing = merged.get("raw")
                if isinstance(existing, Mapping):
                    merged["raw"] = {**dict(existing), **dict(value)}
                else:
                    merged["raw"] = dict(value)
                continue
            merged[key] = value
    return merged or None


@dataclass
class _StreamOutputState:
    user_text: str
    stable_message_id: str
    event_id_namespace: str
    content_buffers: dict[BlockType, str] = field(default_factory=dict)
    progress_buffers: dict[str, str] = field(default_factory=dict)
    token_usage: dict[str, Any] | None = None
    upstream_error: _UpstreamInBandError | None = None
    pending_interrupt_request_ids: set[str] = field(default_factory=set)
    saw_any_chunk: bool = False
    emitted_stream_chunk: bool = False
    sequence: int = 0

    def should_drop_initial_user_echo(
        self,
        text: str,
        *,
        block_type: BlockType,
        role: str | None,
    ) -> bool:
        if role is not None:
            return False
        if block_type != BlockType.TEXT:
            return False
        if self.saw_any_chunk:
            return False
        user_text = self.user_text.strip()
        return bool(user_text) and text.strip() == user_text

    def register_chunk(
        self,
        *,
        block_type: BlockType,
        content_key: str,
        append: bool,
        accumulate_content: bool = True,
    ) -> tuple[bool, bool]:
        previous = self.content_buffers.get(block_type, "")
        next_value = f"{previous}{content_key}" if append and accumulate_content else content_key
        if next_value == previous:
            return False, False
        self.content_buffers[block_type] = next_value
        self.saw_any_chunk = True
        effective_append = self.emitted_stream_chunk
        self.emitted_stream_chunk = True
        return True, effective_append

    def register_progress(self, *, identity: str, content_key: str) -> bool:
        previous = self.progress_buffers.get(identity)
        if previous == content_key:
            return False
        self.progress_buffers[identity] = content_key
        return True

    def should_emit_final_snapshot(self, text: str) -> bool:
        if not text.strip():
            return False
        existing = self.content_buffers.get(BlockType.TEXT, "")
        if existing.strip() == text.strip():
            return False
        self.content_buffers[BlockType.TEXT] = text
        self.saw_any_chunk = True
        return True

    def next_sequence(self) -> int:
        self.sequence += 1
        return self.sequence

    def resolve_message_id(self, message_id: str | None) -> str:
        if isinstance(message_id, str):
            normalized = message_id.strip()
            if normalized:
                return normalized
        return self.stable_message_id

    def build_event_id(self, sequence: int) -> str:
        return f"{self.event_id_namespace}:{sequence}"

    def ingest_token_usage(self, usage: Mapping[str, Any] | None) -> None:
        self.token_usage = _merge_token_usage(self.token_usage, usage)

    def mark_interrupt_pending(self, request_id: str) -> bool:
        normalized = request_id.strip()
        if not normalized:
            return False
        if normalized in self.pending_interrupt_request_ids:
            return False
        self.pending_interrupt_request_ids.add(normalized)
        return True

    def clear_interrupt_pending(self, request_id: str) -> bool:
        normalized = request_id.strip()
        if not normalized:
            return False
        if normalized not in self.pending_interrupt_request_ids:
            return False
        self.pending_interrupt_request_ids.discard(normalized)
        return True


@dataclass(frozen=True)
class _StreamTerminalSignal:
    state: TaskState
    error_type: str | None = None
    message: str | None = None
    upstream_status: int | None = None


@dataclass(frozen=True)
class _UpstreamErrorProfile:
    error_type: str
    state: TaskState
    default_message: str


@dataclass(frozen=True)
class _UpstreamInBandError:
    error_type: str
    state: TaskState
    message: str
    upstream_status: int | None = None


_UPSTREAM_HTTP_ERROR_PROFILE_BY_STATUS: dict[int, _UpstreamErrorProfile] = {
    400: _UpstreamErrorProfile(
        "UPSTREAM_BAD_REQUEST",
        TaskState.failed,
        "OpenCode rejected the request due to invalid input",
    ),
    401: _UpstreamErrorProfile(
        "UPSTREAM_UNAUTHORIZED",
        TaskState.auth_required,
        "OpenCode rejected the request due to authentication failure",
    ),
    403: _UpstreamErrorProfile(
        "UPSTREAM_PERMISSION_DENIED",
        TaskState.failed,
        "OpenCode rejected the request due to insufficient permissions",
    ),
    404: _UpstreamErrorProfile(
        "UPSTREAM_RESOURCE_NOT_FOUND",
        TaskState.failed,
        "OpenCode rejected the request because the target resource was not found",
    ),
    429: _UpstreamErrorProfile(
        "UPSTREAM_QUOTA_EXCEEDED",
        TaskState.failed,
        "OpenCode rejected the request due to quota limits",
    ),
}


def _resolve_upstream_error_profile(status: int) -> _UpstreamErrorProfile:
    if status in _UPSTREAM_HTTP_ERROR_PROFILE_BY_STATUS:
        return _UPSTREAM_HTTP_ERROR_PROFILE_BY_STATUS[status]
    if 400 <= status < 500:
        return _UpstreamErrorProfile(
            "UPSTREAM_CLIENT_ERROR",
            TaskState.failed,
            f"OpenCode rejected the request with client error {status}",
        )
    if status >= 500:
        return _UpstreamErrorProfile(
            "UPSTREAM_SERVER_ERROR",
            TaskState.failed,
            f"OpenCode rejected the request with server error {status}",
        )
    return _UpstreamErrorProfile(
        "UPSTREAM_HTTP_ERROR",
        TaskState.failed,
        f"OpenCode rejected the request with HTTP status {status}",
    )


def _extract_upstream_error_detail(response: httpx.Response | None) -> str | None:
    if response is None:
        return None

    payload = None
    try:
        payload = response.json()
    except Exception:
        payload = None

    if isinstance(payload, dict):
        for key in ("detail", "error", "message"):
            value = payload.get(key)
            if isinstance(value, str):
                value = value.strip()
                if value:
                    return value

    text = response.text.strip()
    if text:
        return text[:512]
    return None


def _format_upstream_error(
    exc: httpx.HTTPStatusError, *, request: str
) -> tuple[str, TaskState, str]:
    status = exc.response.status_code
    profile = _resolve_upstream_error_profile(status)
    detail = _extract_upstream_error_detail(exc.response)
    if detail:
        return (
            profile.error_type,
            profile.state,
            f"{profile.default_message} ({request}, status={status}, detail={detail}).",
        )
    return (
        profile.error_type,
        profile.state,
        f"{profile.default_message} ({request}, status={status}).",
    )


def _format_stream_terminal_error(
    *,
    detail: str | None,
    status: int | None,
    error_name: str | None,
) -> _StreamTerminalSignal:
    if status is not None:
        profile = _resolve_upstream_error_profile(status)
        if detail:
            message = (
                f"{profile.default_message} (session.error, status={status}, detail={detail})."
            )
        else:
            message = f"{profile.default_message} (session.error, status={status})."
        return _StreamTerminalSignal(
            state=profile.state,
            error_type=profile.error_type,
            message=message,
            upstream_status=status,
        )

    if error_name == "ProviderAuthError":
        if detail:
            message = (
                "OpenCode rejected the request due to authentication failure "
                f"(session.error, detail={detail})."
            )
        else:
            message = "OpenCode rejected the request due to authentication failure (session.error)."
        return _StreamTerminalSignal(
            state=TaskState.auth_required,
            error_type="UPSTREAM_UNAUTHORIZED",
            message=message,
        )

    if detail:
        message = f"OpenCode execution failed (session.error, detail={detail})."
    elif error_name:
        message = f"OpenCode execution failed (session.error, error={error_name})."
    else:
        message = "OpenCode execution failed (session.error)."
    return _StreamTerminalSignal(
        state=TaskState.failed,
        error_type="UPSTREAM_EXECUTION_ERROR",
        message=message,
    )


def _format_inband_upstream_error(
    *,
    source: str,
    detail: str | None,
    status: int | None,
    error_name: str | None,
) -> _UpstreamInBandError:
    if status is not None:
        profile = _resolve_upstream_error_profile(status)
        if detail:
            message = f"{profile.default_message} ({source}, status={status}, detail={detail})."
        else:
            message = f"{profile.default_message} ({source}, status={status})."
        return _UpstreamInBandError(
            error_type=profile.error_type,
            state=profile.state,
            message=message,
            upstream_status=status,
        )

    if error_name == "ProviderAuthError":
        if detail:
            message = (
                "OpenCode rejected the request due to authentication failure "
                f"({source}, detail={detail})."
            )
        else:
            message = f"OpenCode rejected the request due to authentication failure ({source})."
        return _UpstreamInBandError(
            error_type="UPSTREAM_UNAUTHORIZED",
            state=TaskState.auth_required,
            message=message,
        )

    if detail:
        message = f"OpenCode execution failed ({source}, detail={detail})."
    elif error_name:
        message = f"OpenCode execution failed ({source}, error={error_name})."
    else:
        message = f"OpenCode execution failed ({source})."
    return _UpstreamInBandError(
        error_type="UPSTREAM_EXECUTION_ERROR",
        state=TaskState.failed,
        message=message,
    )


async def _await_stream_terminal_signal(
    *,
    stream_task: asyncio.Task[None] | None,
    terminal_signal: asyncio.Future[_StreamTerminalSignal],
    session_id: str,
) -> _StreamTerminalSignal:
    if terminal_signal.done():
        return terminal_signal.result()
    if stream_task is None:
        raise RuntimeError("Streaming task was not initialized")

    terminal_wait_task = asyncio.create_task(_wait_for_terminal_signal(terminal_signal))
    try:
        done, _pending = await asyncio.wait(
            {stream_task, terminal_wait_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        if terminal_wait_task in done:
            return terminal_wait_task.result()
        if stream_task in done:
            with suppress(asyncio.CancelledError):
                await stream_task
            if terminal_signal.done():
                return terminal_signal.result()
            raise UpstreamContractError(
                "OpenCode event stream ended before terminal signal "
                f"(session_id={session_id}, expected session.idle or session.error)"
            )
        return await terminal_wait_task
    finally:
        if not terminal_wait_task.done():
            terminal_wait_task.cancel()
            with suppress(asyncio.CancelledError):
                await terminal_wait_task


async def _wait_for_terminal_signal(
    terminal_signal: asyncio.Future[_StreamTerminalSignal],
) -> _StreamTerminalSignal:
    return await terminal_signal


class _TTLCache:
    """Bounded TTL cache for hashable key -> string value."""

    def __init__(
        self,
        *,
        ttl_seconds: int,
        maxsize: int,
        now: Callable[[], float] = time.monotonic,
        refresh_on_get: bool = False,
    ) -> None:
        self._ttl_seconds = int(ttl_seconds)
        self._maxsize = int(maxsize)
        self._now = now
        self._refresh_on_get = bool(refresh_on_get)
        self._store: dict[object, tuple[str, float]] = {}

    def get(self, key: object) -> str | None:
        if self._ttl_seconds <= 0 or self._maxsize <= 0:
            return None
        item = self._store.get(key)
        if not item:
            return None
        value, expires_at = item
        now = self._now()
        if expires_at <= now:
            self._store.pop(key, None)
            return None
        if self._refresh_on_get:
            self._store[key] = (value, now + float(self._ttl_seconds))
        return value

    def set(self, key: object, value: str) -> None:
        if self._ttl_seconds <= 0 or self._maxsize <= 0:
            return
        now = self._now()
        expires_at = now + float(self._ttl_seconds)
        self._store[key] = (value, expires_at)
        self._evict_if_needed(now=now)

    def pop(self, key: object) -> None:
        self._store.pop(key, None)

    def _evict_if_needed(self, *, now: float) -> None:
        if len(self._store) <= self._maxsize:
            return
        expired = [key for key, (_, exp) in self._store.items() if exp <= now]
        for key in expired:
            self._store.pop(key, None)
        if len(self._store) <= self._maxsize:
            return
        overflow = len(self._store) - self._maxsize
        by_expiry = sorted(self._store.items(), key=lambda item: item[1][1])
        for key, _ in by_expiry[:overflow]:
            self._store.pop(key, None)


def _preview_log_value(value: Any, *, limit: int) -> str:
    try:
        rendered = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except Exception:
        rendered = str(value)
    if limit > 0 and len(rendered) > limit:
        return f"{rendered[:limit]}...[truncated]"
    return rendered

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

logger = logging.getLogger(__name__)


def normalize_role(role: Any) -> str | None:
    if not isinstance(role, str):
        return None
    value = role.strip().lower()
    if not value:
        return None
    if value.startswith("role_"):
        value = value[5:]
    if value in {"assistant", "agent", "model", "ai"}:
        return "agent"
    if value in {"user", "human"}:
        return "user"
    if value == "system":
        return "system"
    return value


def extract_role(data: Mapping[str, Any], secondary: Mapping[str, Any] | None = None) -> str | None:
    """Extract and normalize role from OpenCode payload."""
    # Try multiple places where role might hide
    role = data.get("role")
    if role is None and secondary:
        role = secondary.get("role")

    if role is None:
        # Check nested message object
        for container in (data, secondary or {}):
            msg = container.get("message")
            if isinstance(msg, Mapping):
                role = msg.get("role")
                if role:
                    break
            info = container.get("info")
            if isinstance(info, Mapping):
                role = info.get("role")
                if role:
                    break

    return normalize_role(role)


def extract_session_id(
    data: Mapping[str, Any], secondary: Mapping[str, Any] | None = None
) -> str | None:
    """Extract session ID from OpenCode payload."""
    keys = ("sessionID", "sessionId", "session_id", "id")
    for container in (data, secondary or {}):
        for key in keys:
            val = container.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()

        # Check nested objects
        for nested_key in ("message", "info", "summary"):
            nested = container.get(nested_key)
            if isinstance(nested, Mapping):
                for key in keys:
                    val = nested.get(key)
                    if isinstance(val, str) and val.strip():
                        return val.strip()
    return None


def extract_message_id(
    data: Mapping[str, Any], secondary: Mapping[str, Any] | None = None
) -> str | None:
    """Extract message ID from OpenCode payload."""
    keys = ("messageID", "messageId", "message_id", "id")
    for container in (data, secondary or {}):
        for key in keys:
            val = container.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()

        # Check nested objects
        for nested_key in ("message", "info", "part"):
            nested = container.get(nested_key)
            if isinstance(nested, Mapping):
                for key in keys:
                    val = nested.get(key)
                    if isinstance(val, str) and val.strip():
                        return val.strip()
    return None


def extract_text_from_parts(parts: list[dict[str, Any]]) -> str:
    """Extract text from OpenCode-style message parts."""
    texts: list[str] = []
    for part in parts:
        if isinstance(part, dict) and part.get("type") == "text":
            val = part.get("text")
            if isinstance(val, str) and val:
                texts.append(val)
    return "".join(texts).strip()


def extract_text(data: Mapping[str, Any]) -> str:
    """Extract text from OpenCode payload."""
    text = data.get("text")
    if isinstance(text, str):
        return text.strip()

    parts = data.get("parts")
    if isinstance(parts, list):
        return extract_text_from_parts(parts)

    return ""

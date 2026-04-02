"""Helpers for outbound request metadata and call-context construction."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from a2a.client.middleware import ClientCallContext, ClientCallInterceptor

from ..protocol_versions import normalize_protocol_version
from .auth import encode_basic_auth


class HeaderInterceptor(ClientCallInterceptor):
    def __init__(self, default_headers: Mapping[str, str] | None = None) -> None:
        self._default_headers = {
            key: value for key, value in dict(default_headers or {}).items() if value is not None
        }

    async def intercept(
        self,
        method_name: str,
        request_payload: dict[str, Any],
        http_kwargs: dict[str, Any],
        agent_card: object | None,
        context: ClientCallContext | None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        del method_name, agent_card
        headers = dict(http_kwargs.get("headers") or {})
        headers.update(self._default_headers)
        if context is not None:
            dynamic_headers = context.state.get("headers")
            if isinstance(dynamic_headers, Mapping):
                for key, value in dynamic_headers.items():
                    if isinstance(key, str) and value is not None:
                        headers[key] = str(value)
        if headers:
            http_kwargs["headers"] = headers
        return request_payload, http_kwargs


def build_default_headers(
    bearer_token: str | None,
    basic_auth: str | None = None,
    protocol_version: str | None = None,
) -> dict[str, str]:
    headers: dict[str, str] = {}
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"
    elif basic_auth:
        headers["Authorization"] = f"Basic {encode_basic_auth(basic_auth)}"
    if protocol_version:
        headers["A2A-Version"] = normalize_protocol_version(protocol_version)
    return headers


def split_request_metadata(
    metadata: Mapping[str, Any] | None,
) -> tuple[dict[str, Any] | None, dict[str, str] | None]:
    request_metadata: dict[str, Any] = {}
    extra_headers: dict[str, str] = {}
    for key, value in dict(metadata or {}).items():
        if isinstance(key, str) and key.lower() == "authorization":
            if value is not None:
                extra_headers["Authorization"] = str(value)
            continue
        if isinstance(key, str) and key.lower() == "a2a-version":
            if value is not None:
                extra_headers["A2A-Version"] = normalize_protocol_version(str(value))
            continue
        request_metadata[key] = value
    return request_metadata or None, extra_headers or None


def build_call_context(
    bearer_token: str | None,
    extra_headers: Mapping[str, str] | None,
    basic_auth: str | None = None,
    protocol_version: str | None = None,
) -> ClientCallContext | None:
    merged_headers = build_default_headers(bearer_token, basic_auth, protocol_version)
    if extra_headers:
        merged_headers.update(extra_headers)
    if not merged_headers:
        return None
    return ClientCallContext(
        state={
            "headers": dict(merged_headers),
            "http_kwargs": {"headers": dict(merged_headers)},
        }
    )


def build_client_interceptors(
    bearer_token: str | None,
    basic_auth: str | None = None,
    protocol_version: str | None = None,
) -> list[ClientCallInterceptor]:
    return [HeaderInterceptor(build_default_headers(bearer_token, basic_auth, protocol_version))]


__all__ = [
    "HeaderInterceptor",
    "build_call_context",
    "build_client_interceptors",
    "build_default_headers",
    "split_request_metadata",
]

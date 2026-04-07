from __future__ import annotations

from base64 import b64encode

import pytest

from opencode_a2a.client.request_context import (
    ClientCallContext,
    HeaderInterceptor,
    build_call_context,
    build_client_interceptors,
    build_default_headers,
    split_request_metadata,
)
from opencode_a2a.trace_context import TraceContext, bind_trace_context


def test_split_request_metadata_and_default_headers() -> None:
    request_metadata, extra_headers = split_request_metadata(
        {
            "authorization": "Bearer explicit-token",
            "A2A-Version": "1.0.0",
            "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
            "tracestate": "vendor=value",
            "trace_id": "trace-1",
        }
    )

    assert request_metadata == {"trace_id": "trace-1"}
    assert extra_headers == {
        "Authorization": "Bearer explicit-token",
        "A2A-Version": "1.0",
        "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
        "tracestate": "vendor=value",
    }
    assert build_default_headers("peer-token") == {"Authorization": "Bearer peer-token"}


def test_build_default_headers_encodes_basic_auth_credentials() -> None:
    encoded = b64encode(b"user:pass").decode()

    assert build_default_headers(None, "user:pass") == {"Authorization": f"Basic {encoded}"}


def test_build_default_headers_accepts_pre_encoded_basic_auth() -> None:
    encoded = b64encode(b"user:pass").decode()

    assert build_default_headers(None, encoded) == {"Authorization": f"Basic {encoded}"}


def test_build_default_headers_rejects_invalid_basic_auth() -> None:
    with pytest.raises(ValueError, match="username:password"):
        build_default_headers(None, "not-basic-auth")


def test_build_default_headers_prefers_bearer_over_basic_auth() -> None:
    assert build_default_headers("peer-token", "user:pass") == {
        "Authorization": "Bearer peer-token"
    }


def test_build_default_headers_includes_protocol_version() -> None:
    assert build_default_headers("peer-token", protocol_version="1.0.0") == {
        "Authorization": "Bearer peer-token",
        "A2A-Version": "1.0",
    }


def test_build_call_context_without_headers_returns_none() -> None:
    assert build_call_context(None, None) is None


def test_build_call_context_includes_current_trace_headers() -> None:
    with bind_trace_context(
        TraceContext(
            traceparent="00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
            trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
            tracestate="vendor=value",
        )
    ):
        context = build_call_context(None, None)

    assert context is not None
    assert context.state["headers"] == {
        "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
        "tracestate": "vendor=value",
    }


def test_build_call_context_preserves_explicit_trace_headers_over_current_context() -> None:
    with bind_trace_context(
        TraceContext(
            traceparent="00-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-bbbbbbbbbbbbbbbb-01",
            trace_id="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            tracestate="upstream=1",
        )
    ):
        context = build_call_context(
            "peer-token",
            {
                "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
                "tracestate": "vendor=value",
            },
        )

    assert context is not None
    assert context.state["headers"] == {
        "Authorization": "Bearer peer-token",
        "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
        "tracestate": "vendor=value",
    }


def test_build_client_interceptors_uses_header_interceptor() -> None:
    interceptors = build_client_interceptors("peer-token")

    assert len(interceptors) == 1
    assert isinstance(interceptors[0], HeaderInterceptor)


@pytest.mark.asyncio
async def test_header_interceptor_merges_static_and_dynamic_headers() -> None:
    interceptor = HeaderInterceptor({"Authorization": "Bearer peer-token"})
    context = ClientCallContext(state={"headers": {"X-Trace-Id": "trace-1"}})

    request_payload, http_kwargs = await interceptor.intercept(
        "message/send",
        {"jsonrpc": "2.0"},
        {"headers": {"Accept": "application/json"}},
        agent_card=None,
        context=context,
    )

    assert request_payload == {"jsonrpc": "2.0"}
    assert http_kwargs["headers"] == {
        "Accept": "application/json",
        "Authorization": "Bearer peer-token",
        "X-Trace-Id": "trace-1",
    }

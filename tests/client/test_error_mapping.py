from __future__ import annotations

import httpx
from a2a.client.errors import A2AClientHTTPError, A2AClientJSONError, A2AClientJSONRPCError
from a2a.types import JSONRPCError, JSONRPCErrorResponse

from opencode_a2a.client.error_mapping import (
    map_agent_card_error,
    map_http_error,
    map_jsonrpc_error,
    map_operation_error,
)
from opencode_a2a.client.errors import (
    A2AAgentUnavailableError,
    A2AAuthenticationError,
    A2AClientResetRequiredError,
    A2APeerProtocolError,
    A2APermissionDeniedError,
    A2ATimeoutError,
    A2AUnsupportedOperationError,
)


def test_map_jsonrpc_error_variants() -> None:
    invalid_params_error = A2AClientJSONRPCError(
        JSONRPCErrorResponse(
            error=JSONRPCError(code=-32602, message="bad params"),
            id="req-1",
        )
    )
    internal_error = A2AClientJSONRPCError(
        JSONRPCErrorResponse(
            error=JSONRPCError(code=-32603, message="internal"),
            id="req-2",
        )
    )
    generic_error = A2AClientJSONRPCError(
        JSONRPCErrorResponse(
            error=JSONRPCError(code=-32000, message="generic"),
            id="req-3",
        )
    )

    mapped_invalid = map_jsonrpc_error(invalid_params_error)
    mapped_internal = map_jsonrpc_error(internal_error)
    mapped_generic = map_jsonrpc_error(generic_error)

    assert isinstance(mapped_invalid, A2APeerProtocolError)
    assert mapped_invalid.error_code == "invalid_params"
    assert isinstance(mapped_internal, A2AClientResetRequiredError)
    assert isinstance(mapped_generic, A2APeerProtocolError)
    assert mapped_generic.error_code == "peer_protocol_error"


def test_map_http_error_variants() -> None:
    auth_failed = map_http_error("message/send", A2AClientHTTPError(401, "denied"))
    permission_denied = map_http_error("message/send", A2AClientHTTPError(403, "forbidden"))
    unsupported = map_http_error("message/send", A2AClientHTTPError(405, "nope"))
    reset = map_http_error("message/send", A2AClientHTTPError(503, "busy"))
    unavailable = map_http_error("message/send", A2AClientHTTPError(500, "boom"))

    assert isinstance(auth_failed, A2AAuthenticationError)
    assert isinstance(permission_denied, A2APermissionDeniedError)
    assert isinstance(unsupported, A2AUnsupportedOperationError)
    assert isinstance(reset, A2AClientResetRequiredError)
    assert isinstance(unavailable, A2AAgentUnavailableError)


def test_map_operation_error_transport_and_timeout_variants() -> None:
    timeout = map_operation_error("message/send", httpx.ReadTimeout("timed out"))
    unavailable = map_operation_error("message/send", httpx.ConnectError("down"))

    assert isinstance(timeout, A2ATimeoutError)
    assert isinstance(unavailable, A2AAgentUnavailableError)


def test_map_agent_card_error_json_variant() -> None:
    mapped = map_agent_card_error(A2AClientJSONError("invalid json"))

    assert isinstance(mapped, A2APeerProtocolError)
    assert mapped.error_code == "invalid_agent_card"

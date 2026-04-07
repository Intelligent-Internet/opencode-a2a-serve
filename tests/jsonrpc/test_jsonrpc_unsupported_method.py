import httpx
import pytest

from opencode_a2a.server.application import create_app
from tests.support.helpers import make_settings


@pytest.mark.asyncio
async def test_unsupported_method_returns_unified_error() -> None:
    settings = make_settings(a2a_bearer_token="test-token")
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/",
            headers={"Authorization": "Bearer test-token"},
            json={"jsonrpc": "2.0", "id": 123, "method": "unsupported.method", "params": {}},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["jsonrpc"] == "2.0"
    assert body["id"] == 123
    assert "error" in body
    error = body["error"]
    assert error["code"] == -32601
    assert "Unsupported method" in error["message"]

    data = error["data"]
    assert data["type"] == "METHOD_NOT_SUPPORTED"
    assert data["method"] == "unsupported.method"
    assert "supported_methods" in data
    assert "message/send" in data["supported_methods"]
    assert "opencode.sessions.list" in data["supported_methods"]
    assert data["protocol_version"] == settings.a2a_protocol_version


@pytest.mark.asyncio
async def test_unsupported_method_uses_requested_protocol_version() -> None:
    settings = make_settings(a2a_bearer_token="test-token")
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/",
            headers={
                "Authorization": "Bearer test-token",
                "A2A-Version": "1.0",
            },
            json={"jsonrpc": "2.0", "id": 123, "method": "unsupported.method", "params": {}},
        )

    assert response.status_code == 200
    assert response.headers["A2A-Version"] == "1.0"
    body = response.json()
    assert body["error"]["message"] == "Method not found"
    assert body["error"]["data"] == {
        "method": "unsupported.method",
        "supportedMethods": body["error"]["data"]["supportedMethods"],
        "protocolVersion": "1.0",
    }
    assert "message/send" in body["error"]["data"]["supportedMethods"]


@pytest.mark.asyncio
async def test_pascalcase_jsonrpc_aliases_remain_unsupported_on_v03() -> None:
    settings = make_settings(a2a_bearer_token="test-token")
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/",
            headers={"Authorization": "Bearer test-token"},
            json={"jsonrpc": "2.0", "id": 123, "method": "SendMessage", "params": {}},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["error"]["code"] == -32601
    assert body["error"]["data"]["method"] == "SendMessage"
    assert "message/send" in body["error"]["data"]["supported_methods"]


@pytest.mark.asyncio
async def test_unsupported_v1_minor_version_returns_v1_error_details() -> None:
    settings = make_settings(a2a_bearer_token="test-token")
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/?A2A-Version=1.1",
            headers={"Authorization": "Bearer test-token"},
            json={"jsonrpc": "2.0", "id": 124, "method": "message/send", "params": {}},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["error"]["code"] == -32001
    assert body["error"]["data"][0] == {
        "@type": "type.googleapis.com/google.rpc.ErrorInfo",
        "reason": "VERSION_NOT_SUPPORTED",
        "domain": "a2a-protocol.org",
        "metadata": {
            "requestedVersion": "1.1",
            "supportedProtocolVersions": '["0.3","1.0"]',
            "defaultProtocolVersion": "0.3",
        },
    }


@pytest.mark.asyncio
async def test_unsupported_version_returns_version_error() -> None:
    settings = make_settings(a2a_bearer_token="test-token")
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/?A2A-Version=2.0",
            headers={"Authorization": "Bearer test-token"},
            json={"jsonrpc": "2.0", "id": 123, "method": "message/send", "params": {}},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["jsonrpc"] == "2.0"
    assert body["id"] == 123
    assert body["error"]["code"] == -32001
    assert body["error"]["data"] == {
        "type": "VERSION_NOT_SUPPORTED",
        "requested_version": "2.0",
        "supported_protocol_versions": ["0.3", "1.0"],
        "default_protocol_version": "0.3",
    }


@pytest.mark.asyncio
async def test_unsupported_method_notification_returns_204() -> None:
    settings = make_settings(a2a_bearer_token="test-token")
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/",
            headers={"Authorization": "Bearer test-token"},
            json={"jsonrpc": "2.0", "method": "unsupported.method", "params": {}},
        )

    # Even unsupported methods follow notification semantics: if id is missing, return 204.
    # Note: OpencodeSessionManagementJSONRPCApplication._handle_requests
    # returns 204 for notifications
    # if it catches the method. For unsupported methods, it now also returns 204 if id is None.
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_disabled_shell_reports_current_supported_methods() -> None:
    settings = make_settings(a2a_bearer_token="test-token", a2a_enable_session_shell=False)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/",
            headers={"Authorization": "Bearer test-token"},
            json={
                "jsonrpc": "2.0",
                "id": 124,
                "method": "opencode.sessions.shell",
                "params": {
                    "session_id": "s-1",
                    "request": {"agent": "code-reviewer", "command": "pwd"},
                },
            },
        )

    assert response.status_code == 200
    body = response.json()
    error = body["error"]
    assert error["code"] == -32601
    assert error["data"]["type"] == "METHOD_NOT_SUPPORTED"
    assert error["data"]["method"] == "opencode.sessions.shell"
    assert "opencode.sessions.shell" not in error["data"]["supported_methods"]


@pytest.mark.asyncio
async def test_policy_disabled_shell_reports_current_supported_methods() -> None:
    settings = make_settings(
        a2a_bearer_token="test-token",
        a2a_enable_session_shell=True,
        a2a_sandbox_mode="read-only",
        a2a_write_access_scope="workspace_only",
    )
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/",
            headers={"Authorization": "Bearer test-token"},
            json={
                "jsonrpc": "2.0",
                "id": 125,
                "method": "opencode.sessions.shell",
                "params": {
                    "session_id": "s-1",
                    "request": {"agent": "code-reviewer", "command": "pwd"},
                },
            },
        )

    assert response.status_code == 200
    body = response.json()
    error = body["error"]
    assert error["code"] == -32601
    assert error["data"]["type"] == "METHOD_NOT_SUPPORTED"
    assert error["data"]["method"] == "opencode.sessions.shell"
    assert "opencode.sessions.shell" not in error["data"]["supported_methods"]


@pytest.mark.asyncio
async def test_disabled_workspace_mutation_reports_current_supported_methods() -> None:
    settings = make_settings(a2a_bearer_token="test-token")
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/",
            headers={"Authorization": "Bearer test-token"},
            json={
                "jsonrpc": "2.0",
                "id": 126,
                "method": "opencode.workspaces.create",
                "params": {"request": {"type": "git"}},
            },
        )

    assert response.status_code == 200
    body = response.json()
    error = body["error"]
    assert error["code"] == -32601
    assert error["data"]["type"] == "METHOD_NOT_SUPPORTED"
    assert error["data"]["method"] == "opencode.workspaces.create"
    assert "opencode.workspaces.create" not in error["data"]["supported_methods"]

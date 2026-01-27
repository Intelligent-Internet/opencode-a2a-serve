import httpx
import pytest
from a2a.client.auth.credentials import InMemoryContextCredentialStore
from a2a.client.auth.interceptor import AuthInterceptor
from a2a.client.middleware import ClientCallContext
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    HTTPAuthSecurityScheme,
    SecurityScheme,
)

from opencode_a2a.a2a_client import PatchedRestTransport


@pytest.mark.asyncio
async def test_auth_interceptor_applies_bearer_token():
    """Test that AuthInterceptor correctly adds the Bearer token to requests."""
    # Setup
    store = InMemoryContextCredentialStore()
    session_id = "test-session"
    token = "test-secret-token"
    # We use "bearerAuth" as the security scheme ID, matching what's in app.py build_agent_card
    await store.set_credentials(session_id, "bearerAuth", token)

    interceptor = AuthInterceptor(store)
    context = ClientCallContext(state={"sessionId": session_id})

    agent_card = AgentCard(
        name="test-agent",
        description="test-description",
        url="http://test",
        version="0.1.0",
        protocol_version="0.3.0",
        capabilities=AgentCapabilities(streaming=False),
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        skills=[],
        security_schemes={
            "bearerAuth": SecurityScheme(
                root=HTTPAuthSecurityScheme(
                    description="Bearer token authentication",
                    scheme="bearer",
                    bearer_format="opaque",
                )
            )
        },
        security=[{"bearerAuth": []}],
    )

    async with httpx.AsyncClient() as httpx_client:
        transport = PatchedRestTransport(
            httpx_client=httpx_client,
            agent_card=agent_card,
            url="http://test",
            interceptors=[interceptor],
        )

        initial_payload = {"message": {"text": "hello"}}
        initial_kwargs = {"headers": {"Accept": "application/json"}}

        # Execute
        final_payload, final_kwargs = await transport._apply_interceptors(
            initial_payload, initial_kwargs, context
        )

        # Verify
        assert "Authorization" in final_kwargs["headers"]
        assert final_kwargs["headers"]["Authorization"] == f"Bearer {token}"
        assert final_payload == initial_payload
        assert final_kwargs["headers"]["Accept"] == "application/json"


@pytest.mark.asyncio
async def test_patched_rest_transport_multiple_interceptors():
    """Test that PatchedRestTransport applies multiple interceptors in order."""
    from typing import Any

    from a2a.client.middleware import ClientCallInterceptor

    class CustomInterceptor(ClientCallInterceptor):
        async def intercept(
            self,
            protocol: str,
            request_payload: dict[str, Any],
            http_kwargs: dict[str, Any],
            agent_card: AgentCard,
            context: ClientCallContext | None,
        ) -> tuple[dict[str, Any], dict[str, Any]]:
            http_kwargs["headers"]["X-Custom"] = "custom-value"
            return request_payload, http_kwargs

    # Setup
    store = InMemoryContextCredentialStore()
    session_id = "test-session"
    token = "test-token"
    await store.set_credentials(session_id, "bearerAuth", token)

    auth_interceptor = AuthInterceptor(store)
    custom_interceptor = CustomInterceptor()

    context = ClientCallContext(state={"sessionId": session_id})
    agent_card = AgentCard(
        name="test",
        description="test",
        url="http://test",
        version="0.1.0",
        protocol_version="0.3.0",
        capabilities=AgentCapabilities(streaming=False),
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        skills=[],
        security_schemes={
            "bearerAuth": SecurityScheme(
                root=HTTPAuthSecurityScheme(
                    description="Bearer token authentication",
                    scheme="bearer",
                    bearer_format="opaque",
                )
            )
        },
        security=[{"bearerAuth": []}],
    )

    async with httpx.AsyncClient() as httpx_client:
        transport = PatchedRestTransport(
            httpx_client=httpx_client,
            agent_card=agent_card,
            url="http://test",
            interceptors=[auth_interceptor, custom_interceptor],
        )

        # Execute
        _, final_kwargs = await transport._apply_interceptors({}, {"headers": {}}, context)

        # Verify
        assert final_kwargs["headers"]["Authorization"] == f"Bearer {token}"
        assert final_kwargs["headers"]["X-Custom"] == "custom-value"

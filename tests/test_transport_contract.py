from a2a.types import TransportProtocol

from opencode_a2a_serve.app import build_agent_card, create_app
from opencode_a2a_serve.config import Settings


def _settings() -> Settings:
    return Settings(
        opencode_base_url="http://127.0.0.1:4096",
        a2a_bearer_token="test-token",
    )


def test_agent_card_declares_dual_stack_with_http_json_preferred() -> None:
    card = build_agent_card(_settings())

    assert card.preferred_transport == TransportProtocol.http_json
    transports = {iface.transport for iface in card.additional_interfaces or []}
    assert TransportProtocol.http_json in transports
    assert TransportProtocol.jsonrpc in transports


def test_rest_subscription_route_matches_current_sdk_contract() -> None:
    app = create_app(_settings())
    route_paths = {route.path for route in app.router.routes if hasattr(route, "path")}

    assert "/v1/tasks/{id}:subscribe" in route_paths
    assert "/v1/tasks/{id}:resubscribe" not in route_paths

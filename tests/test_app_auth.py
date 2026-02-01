import dataclasses
import time

import jwt
import pytest
from fastapi.testclient import TestClient

from opencode_a2a.app import create_app
from opencode_a2a.config import Settings

TEST_JWT_SECRET = "super-secret-32-bytes-minimum-key!!"
TEST_JWT_WRONG_SECRET = "wrong-secret-32-bytes-minimum-key!!"


@pytest.fixture
def bearer_settings():
    return Settings(
        opencode_base_url="http://localhost:4096",
        opencode_directory=None,
        opencode_provider_id=None,
        opencode_model_id=None,
        opencode_agent=None,
        opencode_system=None,
        opencode_variant=None,
        opencode_timeout=120.0,
        opencode_timeout_stream=None,
        a2a_public_url="http://localhost:8000",
        a2a_title="Test Agent",
        a2a_description="Test Description",
        a2a_version="0.1.0",
        a2a_protocol_version="0.3.0",
        a2a_streaming=True,
        a2a_log_level="INFO",
        a2a_log_payloads=False,
        a2a_log_body_limit=0,
        a2a_host="127.0.0.1",
        a2a_port=8000,
        a2a_bearer_token="test-token",
        a2a_auth_mode="bearer",
        a2a_jwt_secret=None,
        a2a_jwt_algorithm="HS256",
        a2a_jwt_issuer=None,
        a2a_jwt_audience=None,
        a2a_oauth_authorization_url=None,
        a2a_oauth_token_url=None,
        a2a_oauth_metadata_url=None,
        a2a_oauth_scopes={},
    )


@pytest.fixture
def jwt_settings():
    return Settings(
        opencode_base_url="http://localhost:4096",
        opencode_directory=None,
        opencode_provider_id=None,
        opencode_model_id=None,
        opencode_agent=None,
        opencode_system=None,
        opencode_variant=None,
        opencode_timeout=120.0,
        opencode_timeout_stream=None,
        a2a_public_url="http://localhost:8000",
        a2a_title="Test Agent",
        a2a_description="Test Description",
        a2a_version="0.1.0",
        a2a_protocol_version="0.3.0",
        a2a_streaming=True,
        a2a_log_level="INFO",
        a2a_log_payloads=False,
        a2a_log_body_limit=0,
        a2a_host="127.0.0.1",
        a2a_port=8000,
        a2a_bearer_token=None,
        a2a_auth_mode="jwt",
        a2a_jwt_secret=TEST_JWT_SECRET,
        a2a_jwt_algorithm="HS256",
        a2a_jwt_issuer="test-issuer",
        a2a_jwt_audience="test-audience",
        a2a_oauth_authorization_url=None,
        a2a_oauth_token_url=None,
        a2a_oauth_metadata_url=None,
        a2a_oauth_scopes={},
    )


def _jwt_payload(**overrides):
    payload = {
        "iss": "test-issuer",
        "aud": "test-audience",
        "exp": int(time.time()) + 3600,
    }
    payload.update(overrides)
    return payload


def test_bearer_auth_success(bearer_settings):
    app = create_app(bearer_settings)
    client = TestClient(app)
    # We use a path that requires auth.
    # Since we didn't mock the whole agent, we expect 404 or other errors BUT NOT 401.
    response = client.get("/v1/tasks", headers={"Authorization": "Bearer test-token"})
    assert response.status_code != 401


def test_bearer_auth_failure(bearer_settings):
    app = create_app(bearer_settings)
    client = TestClient(app)
    response = client.get("/v1/tasks", headers={"Authorization": "Bearer wrong-token"})
    assert response.status_code == 401


def test_jwt_auth_success(jwt_settings):
    app = create_app(jwt_settings)
    client = TestClient(app)
    token = jwt.encode(_jwt_payload(), TEST_JWT_SECRET, algorithm="HS256")
    response = client.get("/v1/tasks", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code != 401


def test_jwt_auth_failure_invalid_secret(jwt_settings):
    app = create_app(jwt_settings)
    client = TestClient(app)
    token = jwt.encode(_jwt_payload(), TEST_JWT_WRONG_SECRET, algorithm="HS256")
    response = client.get("/v1/tasks", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_public_route_no_auth(bearer_settings):
    app = create_app(bearer_settings)
    client = TestClient(app)
    response = client.get("/.well-known/agent-card.json")
    assert response.status_code == 200


def test_jwt_auth_failure_missing_scope(jwt_settings):
    # Setup settings with required scopes
    jwt_settings = dataclasses.replace(jwt_settings, a2a_oauth_scopes={"required-scope": ""})
    app = create_app(jwt_settings)
    client = TestClient(app)
    # Token with wrong scope
    token = jwt.encode(
        _jwt_payload(scope="other-scope"),
        TEST_JWT_SECRET,
        algorithm="HS256",
    )
    response = client.get("/v1/tasks", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


def test_jwt_auth_success_with_scope(jwt_settings):
    # Setup settings with required scopes
    jwt_settings = dataclasses.replace(jwt_settings, a2a_oauth_scopes={"required-scope": ""})
    app = create_app(jwt_settings)
    client = TestClient(app)
    # Token with correct scope
    token = jwt.encode(
        _jwt_payload(scope="required-scope"),
        TEST_JWT_SECRET,
        algorithm="HS256",
    )
    response = client.get("/v1/tasks", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code != 401
    assert response.status_code != 403


def test_jwt_auth_failure_missing_exp(jwt_settings):
    app = create_app(jwt_settings)
    client = TestClient(app)
    token = jwt.encode(
        {"iss": "test-issuer", "aud": "test-audience"}, TEST_JWT_SECRET, algorithm="HS256"
    )
    response = client.get("/v1/tasks", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_jwt_auth_success_with_scope_list(jwt_settings):
    jwt_settings = dataclasses.replace(jwt_settings, a2a_oauth_scopes={"required-scope": ""})
    app = create_app(jwt_settings)
    client = TestClient(app)
    token = jwt.encode(
        _jwt_payload(scope=["required-scope", "other-scope"]),
        TEST_JWT_SECRET,
        algorithm="HS256",
    )
    response = client.get("/v1/tasks", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code != 401
    assert response.status_code != 403


def test_jwt_auth_success_with_scp_claim(jwt_settings):
    jwt_settings = dataclasses.replace(jwt_settings, a2a_oauth_scopes={"required-scope": ""})
    app = create_app(jwt_settings)
    client = TestClient(app)
    token = jwt.encode(
        _jwt_payload(scp=["required-scope"]),
        TEST_JWT_SECRET,
        algorithm="HS256",
    )
    response = client.get("/v1/tasks", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code != 401
    assert response.status_code != 403


def test_invalid_auth_mode(bearer_settings):
    settings = dataclasses.replace(bearer_settings, a2a_auth_mode="invalid")
    with pytest.raises(RuntimeError):
        create_app(settings)

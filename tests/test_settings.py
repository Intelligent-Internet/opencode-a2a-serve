
import pytest
from pydantic import ValidationError
from opencode_a2a.config import Settings
import os
from unittest import mock

def test_settings_missing_required():
    with mock.patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValidationError) as excinfo:
            Settings.from_env()
        # Should mention missing required fields
        errors = excinfo.value.errors()
        field_names = [e["loc"][0] for e in errors]
        assert "A2A_BEARER_TOKEN" in field_names
        assert "A2A_JWT_AUDIENCE" in field_names
        assert "A2A_JWT_ISSUER" in field_names

def test_settings_invalid_jwt_algo():
    env = {
        "A2A_BEARER_TOKEN": "test",
        "A2A_JWT_AUDIENCE": "test",
        "A2A_JWT_ISSUER": "test",
        "A2A_JWT_ALGORITHM": "HS256" # Invalid, should be asymmetric
    }
    with mock.patch.dict(os.environ, env, clear=True):
        with pytest.raises(ValidationError) as excinfo:
            Settings.from_env()
        assert "Only asymmetric algorithms are supported" in str(excinfo.value)

def test_settings_invalid_scope_match():
    env = {
        "A2A_BEARER_TOKEN": "test",
        "A2A_JWT_AUDIENCE": "test",
        "A2A_JWT_ISSUER": "test",
        "A2A_JWT_SCOPE_MATCH": "invalid"
    }
    with mock.patch.dict(os.environ, env, clear=True):
        with pytest.raises(ValidationError) as excinfo:
            Settings.from_env()
        assert "A2A_JWT_SCOPE_MATCH must be 'any' or 'all'" in str(excinfo.value)

def test_settings_valid():
    env = {
        "A2A_BEARER_TOKEN": "test-token",
        "A2A_JWT_AUDIENCE": "test-aud",
        "A2A_JWT_ISSUER": "test-iss",
        "OPENCODE_TIMEOUT": "300"
    }
    with mock.patch.dict(os.environ, env, clear=True):
        settings = Settings.from_env()
        assert settings.a2a_bearer_token == "test-token"
        assert settings.a2a_jwt_audience == "test-aud"
        assert settings.a2a_jwt_issuer == "test-iss"
        assert settings.opencode_timeout == 300.0
        assert settings.a2a_jwt_algorithm == "RS256" # Default

def test_parse_oauth_scopes():
    env = {
        "A2A_BEARER_TOKEN": "test",
        "A2A_JWT_AUDIENCE": "test",
        "A2A_JWT_ISSUER": "test",
        "A2A_OAUTH_SCOPES": "scope1, scope2,,scope3 "
    }
    with mock.patch.dict(os.environ, env, clear=True):
        settings = Settings.from_env()
        assert settings.a2a_oauth_scopes == {"scope1": "", "scope2": "", "scope3": ""}

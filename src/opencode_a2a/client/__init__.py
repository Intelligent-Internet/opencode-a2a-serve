"""Reusable A2A client utilities and facade types."""

from .client import A2AClient
from .config import A2AClientSettings, load_settings
from .errors import (
    A2AAgentUnavailableError,
    A2AClientError,
    A2AClientResetRequiredError,
    A2APeerProtocolError,
    A2AUnsupportedBindingError,
    A2AUnsupportedOperationError,
)

__all__ = [
    "A2AClient",
    "A2AClientError",
    "A2AAgentUnavailableError",
    "A2AClientResetRequiredError",
    "A2APeerProtocolError",
    "A2AUnsupportedBindingError",
    "A2AUnsupportedOperationError",
    "A2AClientSettings",
    "load_settings",
]

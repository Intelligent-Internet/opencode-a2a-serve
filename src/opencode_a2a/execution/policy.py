from __future__ import annotations

from ..sandbox_policy import SandboxPolicy


class PolicyEnforcer:
    def __init__(self, *, client) -> None:
        self._client = client
        self._policy = SandboxPolicy.from_settings(
            client.settings,
            workspace_root=client.directory,
        )

    def resolve_directory(self, requested: str | None) -> str | None:
        return self._policy.resolve_directory(
            requested,
            default_directory=self._client.directory,
        )

    def resolve_directory_for_control(self, requested: str | None) -> str | None:
        return self.resolve_directory(requested)

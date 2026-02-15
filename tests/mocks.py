from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from opencode_a2a_serve.config import Settings
from opencode_a2a_serve.opencode_client import OpencodeMessage


class DummyOpencodeClient:
    def __init__(self, settings: Settings | None = None) -> None:
        if settings is None:
            self.settings = Settings(
                A2A_BEARER_TOKEN="test",
                OPENCODE_BASE_URL="http://localhost",
            )
        else:
            self.settings = settings
        self.directory = None
        self.stream_timeout = None
        self.created_sessions = 0
        self.sent_session_ids: list[str] = []
        self._sessions_payload: Any = {"items": [{"id": "s-1"}]}
        self._messages_payload: Any = {"items": [{"id": "m-1", "text": "echo"}]}
        self.last_sessions_params: dict[str, Any] | None = None
        self.last_messages_params: dict[str, Any] | None = None

    async def close(self) -> None:
        return None

    async def create_session(
        self,
        title: str | None = None,
        *,
        directory: str | None = None,
    ) -> str:
        del title, directory
        self.created_sessions += 1
        return f"ses-created-{self.created_sessions}"

    async def send_message(
        self,
        session_id: str,
        text: str,
        *,
        directory: str | None = None,
        timeout_override: Any = None,
    ) -> OpencodeMessage:
        del directory, timeout_override
        self.sent_session_ids.append(session_id)
        return OpencodeMessage(
            text=f"echo:{text}",
            session_id=session_id,
            message_id="m-1",
            raw={},
        )

    async def list_sessions(self, *, params: dict[str, Any] | None = None) -> Any:
        self.last_sessions_params = params
        return self._sessions_payload

    async def list_messages(self, session_id: str, *, params: dict[str, Any] | None = None) -> Any:
        assert session_id
        self.last_messages_params = params
        return self._messages_payload

    async def stream_events(
        self, stop_event: Any = None, *, directory: str | None = None
    ) -> AsyncIterator[dict[str, Any]]:
        del stop_event, directory
        if False:
            yield {}


class DummyEventQueue:
    def __init__(self) -> None:
        self.events: list[Any] = []

    async def enqueue_event(self, event: Any) -> None:
        self.events.append(event)

    async def close(self) -> None:
        return None

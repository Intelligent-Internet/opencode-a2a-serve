from __future__ import annotations

from pathlib import Path

import pytest

from opencode_a2a.server.state_store import (
    build_interrupt_request_repository,
    build_session_state_repository,
    initialize_state_repository,
)
from opencode_a2a.server.task_store import build_database_engine
from tests.support.helpers import make_settings


@pytest.mark.asyncio
async def test_database_session_state_repository_persists_bindings(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'state.db'}"
    settings = make_settings(
        a2a_bearer_token="test-token",
        a2a_task_store_backend="database",
        a2a_task_store_database_url=database_url,
    )
    engine = build_database_engine(settings)

    writer = build_session_state_repository(settings, engine=engine)
    await initialize_state_repository(writer)
    await writer.set_session(identity="user-1", context_id="ctx-1", session_id="ses-1")
    await writer.set_owner(session_id="ses-1", identity="user-1")
    await writer.set_pending_claim(session_id="ses-2", identity="user-2")
    await engine.dispose()

    engine = build_database_engine(settings)
    reader = build_session_state_repository(settings, engine=engine)
    await initialize_state_repository(reader)

    assert await reader.get_session(identity="user-1", context_id="ctx-1") == "ses-1"
    assert await reader.get_owner(session_id="ses-1") == "user-1"
    assert await reader.get_pending_claim(session_id="ses-2") == "user-2"

    await engine.dispose()


@pytest.mark.asyncio
async def test_database_interrupt_request_repository_persists_active_binding(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'interrupt.db'}"
    settings = make_settings(
        a2a_bearer_token="test-token",
        a2a_task_store_backend="database",
        a2a_task_store_database_url=database_url,
    )
    engine = build_database_engine(settings)

    writer = build_interrupt_request_repository(settings, engine=engine)
    await initialize_state_repository(writer)
    await writer.remember(
        request_id="perm-1",
        session_id="ses-1",
        interrupt_type="permission",
        identity="user-1",
        task_id="task-1",
        context_id="ctx-1",
        ttl_seconds=30.0,
    )
    await engine.dispose()

    engine = build_database_engine(settings)
    reader = build_interrupt_request_repository(settings, engine=engine)
    await initialize_state_repository(reader)
    status, binding = await reader.resolve(request_id="perm-1")

    assert status == "active"
    assert binding is not None
    assert binding.session_id == "ses-1"
    assert binding.interrupt_type == "permission"
    assert binding.identity == "user-1"
    assert binding.task_id == "task-1"
    assert binding.context_id == "ctx-1"

    await engine.dispose()

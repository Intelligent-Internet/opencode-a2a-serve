import gc
import weakref
from unittest.mock import AsyncMock

import pytest

from opencode_a2a.execution.session_manager import SessionManager
from opencode_a2a.opencode_upstream_client import OpencodeUpstreamClient


@pytest.mark.asyncio
async def test_session_manager_reuses_live_lock_for_same_session() -> None:
    manager = SessionManager(client=AsyncMock(spec=OpencodeUpstreamClient))

    lock1 = await manager.get_session_lock("session-1")
    lock2 = await manager.get_session_lock("session-1")

    assert lock1 is lock2


@pytest.mark.asyncio
async def test_session_manager_does_not_strongly_retain_idle_locks() -> None:
    manager = SessionManager(client=AsyncMock(spec=OpencodeUpstreamClient))

    lock = await manager.get_session_lock("session-1")
    lock_ref = weakref.ref(lock)
    assert "session-1" in manager._session_locks

    del lock
    gc.collect()

    assert lock_ref() is None
    assert "session-1" not in manager._session_locks

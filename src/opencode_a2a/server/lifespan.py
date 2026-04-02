from __future__ import annotations

from contextlib import asynccontextmanager

from .state_store import initialize_state_repository
from .task_store import initialize_task_store


def build_lifespan(
    *,
    database_engine,
    task_store,
    session_state_repository,
    interrupt_request_repository,
    client_manager,
    upstream_client,
):
    @asynccontextmanager
    async def lifespan(_app):
        await initialize_task_store(task_store)
        await initialize_state_repository(session_state_repository)
        await initialize_state_repository(interrupt_request_repository)
        yield
        if database_engine is not None:
            await database_engine.dispose()
        await client_manager.close_all()
        await upstream_client.close()

    return lifespan

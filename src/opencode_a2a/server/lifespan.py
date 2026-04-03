from __future__ import annotations

import logging
from collections.abc import Mapping
from contextlib import asynccontextmanager

from .state_store import initialize_state_repository
from .task_store import initialize_task_store

logger = logging.getLogger(__name__)


def build_lifespan(
    *,
    database_engine,
    task_store,
    session_state_repository,
    interrupt_request_repository,
    client_manager,
    upstream_client,
    persistence_summary: Mapping[str, object] | None = None,
):
    @asynccontextmanager
    async def lifespan(_app):
        if persistence_summary is not None:
            logger.info(
                "Lightweight persistence configured backend=%s scope=%s "
                "database_url=%s sqlite_tuning=%s",
                persistence_summary.get("backend", "unknown"),
                persistence_summary.get("scope", "unknown"),
                persistence_summary.get("database_url", "n/a"),
                persistence_summary.get("sqlite_tuning", "not_applicable"),
            )
        await initialize_task_store(task_store)
        await initialize_state_repository(session_state_repository)
        await initialize_state_repository(interrupt_request_repository)
        yield
        if database_engine is not None:
            await database_engine.dispose()
        await client_manager.close_all()
        await upstream_client.close()

    return lifespan

from __future__ import annotations

import hashlib
import re
from typing import TYPE_CHECKING, cast

from a2a.server.tasks.inmemory_task_store import InMemoryTaskStore
from a2a.server.tasks.task_store import TaskStore

from ..config import Settings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

_CUSTOM_TASK_MODELS: dict[str, object] = {}


def _custom_task_model_class_name(table_name: str) -> str:
    sanitized = re.sub(r"\W+", "_", table_name).strip("_")
    if not sanitized:
        sanitized = "custom"
    if sanitized[0].isdigit():
        sanitized = f"table_{sanitized}"
    suffix = hashlib.sha1(table_name.encode("utf-8")).hexdigest()[:10]
    return f"TaskModel_{sanitized}_{suffix}"


def _build_custom_task_model(table_name: str):
    from a2a.server.models import Base, TaskMixin, TaskModel

    class_name = _custom_task_model_class_name(table_name)
    model = type(
        class_name,
        (TaskMixin, Base),
        {
            "__tablename__": table_name,
            "__module__": __name__,
        },
    )
    return cast("type[TaskModel]", model)


class _ConfiguredDatabaseTaskStore(TaskStore):
    def __init__(
        self,
        *,
        engine: AsyncEngine,
        create_table: bool,
        table_name: str,
    ) -> None:
        from a2a.server.models import TaskModel
        from a2a.server.tasks.database_task_store import DatabaseTaskStore
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

        self._delegate = DatabaseTaskStore.__new__(DatabaseTaskStore)
        self._delegate.engine = engine
        self._delegate.async_session_maker = async_sessionmaker(
            engine,
            expire_on_commit=False,
            class_=AsyncSession,
        )
        self._delegate.create_table = create_table
        self._delegate._initialized = False
        if table_name == "tasks":
            self._delegate.task_model = TaskModel
        else:
            task_model = cast("type[TaskModel] | None", _CUSTOM_TASK_MODELS.get(table_name))
            if task_model is None:
                task_model = _build_custom_task_model(table_name)
                _CUSTOM_TASK_MODELS[table_name] = task_model
            self._delegate.task_model = task_model

    @property
    def engine(self) -> AsyncEngine:
        return self._delegate.engine

    async def initialize(self) -> None:
        await self._delegate.initialize()

    async def save(self, task, context=None) -> None:  # noqa: ANN001
        await self._delegate.save(task, context)

    async def get(self, task_id, context=None):  # noqa: ANN001
        return await self._delegate.get(task_id, context)

    async def delete(self, task_id, context=None) -> None:  # noqa: ANN001
        await self._delegate.delete(task_id, context)


def build_task_store(
    settings: Settings,
    *,
    engine: AsyncEngine | None = None,
) -> TaskStore:
    if settings.a2a_task_store_backend == "memory":
        return InMemoryTaskStore()

    resolved_engine = engine or build_database_engine(settings)
    return _ConfiguredDatabaseTaskStore(
        engine=resolved_engine,
        create_table=settings.a2a_task_store_create_table,
        table_name=settings.a2a_task_store_table_name,
    )


def build_database_engine(settings: Settings) -> AsyncEngine:
    from sqlalchemy.ext.asyncio import create_async_engine

    database_url = cast(str, settings.a2a_task_store_database_url)
    return create_async_engine(database_url)


async def initialize_task_store(task_store: TaskStore) -> None:
    initialize = getattr(task_store, "initialize", None)
    if callable(initialize):
        await initialize()

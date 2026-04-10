from __future__ import annotations

from a2a.types import TaskState

TERMINAL_TASK_STATES = frozenset(
    {
        TaskState.completed,
        TaskState.canceled,
        TaskState.failed,
        TaskState.rejected,
    }
)

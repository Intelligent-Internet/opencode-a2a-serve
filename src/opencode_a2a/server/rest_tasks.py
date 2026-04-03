from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime, timezone

from a2a.server.tasks.task_store import TaskStore
from a2a.types import Task, TaskState
from fastapi import Request
from fastapi.responses import JSONResponse

from ..jsonrpc.error_responses import build_http_error_body
from .task_store import TaskStoreOperationError, list_stored_tasks

_DEFAULT_LIST_TASKS_PAGE_SIZE = 50
_MAX_LIST_TASKS_PAGE_SIZE = 100
_MIN_LIST_TASKS_PAGE_SIZE = 1


@dataclass(frozen=True)
class _ListTasksQuery:
    context_id: str | None
    include_artifacts: bool
    history_length: int
    page_offset: int
    requested_page_size: int
    status: TaskState | None
    status_timestamp_after: datetime | None


class _ListTasksValidationError(ValueError):
    def __init__(self, *, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field
        self.message = message


def build_list_tasks_route(
    *,
    task_store: TaskStore,
    default_protocol_version: str,
):
    async def list_tasks_route(request: Request) -> JSONResponse:
        protocol_version = getattr(
            request.state,
            "a2a_protocol_version",
            default_protocol_version,
        )
        try:
            query = _parse_list_tasks_query(request)
            tasks = await list_stored_tasks(task_store)
        except _ListTasksValidationError as error:
            return _invalid_argument_response(
                field=error.field,
                message=error.message,
                protocol_version=protocol_version,
            )
        except TaskStoreOperationError as error:
            return JSONResponse(
                build_http_error_body(
                    protocol_version=protocol_version,
                    status_code=500,
                    status="INTERNAL",
                    message="Task store unavailable while listing tasks.",
                    legacy_payload={
                        "error": "Task store unavailable while listing tasks.",
                        "operation": error.operation,
                    },
                    reason="TASK_STORE_UNAVAILABLE",
                    metadata={"operation": error.operation},
                ),
                status_code=500,
            )

        filtered_tasks = _filter_tasks(tasks, query=query)
        total_size = len(filtered_tasks)
        end_offset = min(query.page_offset + query.requested_page_size, total_size)
        page_tasks = filtered_tasks[query.page_offset:end_offset]
        next_page_token = _encode_page_token(end_offset) if end_offset < total_size else ""

        return JSONResponse(
            {
                "tasks": [
                    _serialize_task(
                        task,
                        history_length=query.history_length,
                        include_artifacts=query.include_artifacts,
                    )
                    for task in page_tasks
                ],
                "nextPageToken": next_page_token,
                "pageSize": len(page_tasks),
                "totalSize": total_size,
            }
        )

    return list_tasks_route


def _filter_tasks(tasks: list[Task], *, query: _ListTasksQuery) -> list[Task]:
    filtered = tasks

    if query.context_id is not None:
        filtered = [task for task in filtered if task.context_id == query.context_id]

    if query.status is not None:
        filtered = [task for task in filtered if task.status.state == query.status]

    if query.status_timestamp_after is not None:
        filtered = [
            task
            for task in filtered
            if _task_status_timestamp(task) >= query.status_timestamp_after
        ]

    return sorted(
        filtered,
        key=lambda task: (_task_status_timestamp(task), task.id),
        reverse=True,
    )


def _serialize_task(
    task: Task,
    *,
    history_length: int,
    include_artifacts: bool,
) -> dict:
    payload = task.model_dump(mode="json", by_alias=True, exclude_none=True)

    history = payload.get("history")
    if history_length <= 0:
        payload.pop("history", None)
    elif isinstance(history, list):
        payload["history"] = history[-history_length:]

    if not include_artifacts:
        payload.pop("artifacts", None)

    return payload


def _parse_list_tasks_query(request: Request) -> _ListTasksQuery:
    page_size_value = request.query_params.get("pageSize")
    if page_size_value is None:
        requested_page_size = _DEFAULT_LIST_TASKS_PAGE_SIZE
    else:
        requested_page_size = _parse_int(page_size_value, field="pageSize")
        if not (_MIN_LIST_TASKS_PAGE_SIZE <= requested_page_size <= _MAX_LIST_TASKS_PAGE_SIZE):
            raise _ListTasksValidationError(
                field="pageSize",
                message="pageSize must be between 1 and 100.",
            )

    history_length_value = request.query_params.get("historyLength")
    if history_length_value is None:
        history_length = 0
    else:
        history_length = _parse_int(history_length_value, field="historyLength")
        if history_length < 0:
            raise _ListTasksValidationError(
                field="historyLength",
                message="historyLength must be greater than or equal to 0.",
            )

    include_artifacts = _parse_bool(
        request.query_params.get("includeArtifacts"),
        field="includeArtifacts",
        default=False,
    )
    page_offset = _decode_page_token(request.query_params.get("pageToken"))

    status_value = request.query_params.get("status")
    status = None
    if status_value is not None:
        try:
            status = TaskState(status_value)
        except ValueError as exc:
            raise _ListTasksValidationError(
                field="status",
                message=f"Unsupported task status {status_value!r}.",
            ) from exc

    status_timestamp_after = None
    status_timestamp_after_value = request.query_params.get("statusTimestampAfter")
    if status_timestamp_after_value is not None:
        status_timestamp_after = _parse_timestamp(
            status_timestamp_after_value,
            field="statusTimestampAfter",
        )

    return _ListTasksQuery(
        context_id=request.query_params.get("contextId"),
        include_artifacts=include_artifacts,
        history_length=history_length,
        page_offset=page_offset,
        requested_page_size=requested_page_size,
        status=status,
        status_timestamp_after=status_timestamp_after,
    )


def _parse_int(raw_value: str, *, field: str) -> int:
    try:
        return int(raw_value)
    except ValueError as exc:
        raise _ListTasksValidationError(
            field=field,
            message=f"{field} must be an integer.",
        ) from exc


def _parse_bool(raw_value: str | None, *, field: str, default: bool) -> bool:
    if raw_value is None:
        return default
    normalized = raw_value.strip().lower()
    if normalized in {"true", "1"}:
        return True
    if normalized in {"false", "0"}:
        return False
    raise _ListTasksValidationError(
        field=field,
        message=f"{field} must be a boolean.",
    )


def _parse_timestamp(raw_value: str, *, field: str) -> datetime:
    normalized = raw_value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise _ListTasksValidationError(
            field=field,
            message=f"{field} must be a valid ISO 8601 timestamp.",
        ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _task_status_timestamp(task: Task) -> datetime:
    timestamp = task.status.timestamp
    if not timestamp:
        return datetime.min.replace(tzinfo=timezone.utc)
    return _parse_timestamp(timestamp, field="status.timestamp")


def _decode_page_token(raw_value: str | None) -> int:
    if raw_value is None or not raw_value.strip():
        return 0

    normalized = raw_value.strip()
    padding = "=" * (-len(normalized) % 4)
    try:
        decoded = base64.urlsafe_b64decode(normalized + padding).decode("utf-8")
        payload = json.loads(decoded)
        offset = payload["offset"]
        if not isinstance(offset, int) or offset < 0:
            raise ValueError("offset must be a non-negative integer")
    except Exception as exc:
        raise _ListTasksValidationError(
            field="pageToken",
            message="pageToken is invalid.",
        ) from exc
    return offset


def _encode_page_token(offset: int) -> str:
    payload = json.dumps(
        {"offset": offset},
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("utf-8").rstrip("=")


def _invalid_argument_response(
    *,
    field: str,
    message: str,
    protocol_version: str,
) -> JSONResponse:
    return JSONResponse(
        build_http_error_body(
            protocol_version=protocol_version,
            status_code=400,
            status="INVALID_ARGUMENT",
            message=message,
            legacy_payload={"error": message, "field": field},
            reason="INVALID_LIST_TASKS_REQUEST",
            metadata={"field": field},
        ),
        status_code=400,
    )

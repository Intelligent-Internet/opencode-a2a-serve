from __future__ import annotations

import asyncio
import logging
from functools import partial
from typing import TYPE_CHECKING, cast

import uvicorn
from a2a.server.apps.jsonrpc.fastapi_app import A2AFastAPI
from a2a.server.apps.jsonrpc.jsonrpc_app import DefaultCallContextBuilder
from a2a.server.apps.rest.rest_adapter import RESTAdapter
from a2a.server.events import EventConsumer
from a2a.server.request_handlers.default_request_handler import (
    TERMINAL_TASK_STATES,
    DefaultRequestHandler,
)
from a2a.types import (
    Artifact,
    InternalError,
    Message,
    Part,
    Role,
    Task,
    TaskArtifactUpdateEvent,
    TaskIdParams,
    TaskNotCancelableError,
    TaskNotFoundError,
    TaskQueryParams,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
    TextPart,
    UnsupportedOperationError,
)
from a2a.utils import are_modalities_compatible
from a2a.utils.errors import ServerError
from fastapi import FastAPI, Request
from pydantic_settings import BaseSettings
from starlette.middleware.gzip import GZipMiddleware

from ..config import Settings
from ..contracts.extensions import (
    COMPATIBILITY_PROFILE_EXTENSION_URI,
    INTERRUPT_CALLBACK_EXTENSION_URI,
    INTERRUPT_CALLBACK_METHODS,
    INTERRUPT_RECOVERY_EXTENSION_URI,
    INTERRUPT_RECOVERY_METHODS,
    MODEL_SELECTION_EXTENSION_URI,
    PROVIDER_DISCOVERY_EXTENSION_URI,
    PROVIDER_DISCOVERY_METHODS,
    SESSION_BINDING_EXTENSION_URI,
    SESSION_CONTROL_METHODS,
    SESSION_QUERY_EXTENSION_URI,
    SESSION_QUERY_METHODS,
    STREAMING_EXTENSION_URI,
    WIRE_CONTRACT_EXTENSION_URI,
    WORKSPACE_CONTROL_EXTENSION_URI,
    WORKSPACE_CONTROL_METHODS,
    build_capability_snapshot,
)
from ..execution.executor import OpencodeAgentExecutor
from ..invocation import call_with_supported_kwargs
from ..jsonrpc.application import (
    OpencodeSessionQueryJSONRPCApplication,
)
from ..opencode_upstream_client import OpencodeUpstreamClient
from ..output_modes import normalize_accepted_output_modes
from ..profile.runtime import build_runtime_profile
from .agent_card import (
    _CHAT_OUTPUT_MODES,
    _build_agent_card_description,
    _build_chat_examples,
    _build_session_query_skill_examples,
    build_agent_card,
    build_authenticated_extended_agent_card,
)
from .client_manager import A2AClientManager
from .lifespan import build_lifespan
from .middleware import (
    AUTHENTICATED_EXTENDED_CARD_CACHE_CONTROL,
    PUBLIC_AGENT_CARD_CACHE_CONTROL,
    build_agent_card_etag,
    emit_stream_request_metrics,
    install_runtime_middlewares,
)
from .openapi import (
    _build_jsonrpc_extension_openapi_description,
    _build_jsonrpc_extension_openapi_examples,
    _build_rest_message_openapi_examples,
    _patch_jsonrpc_openapi_contract,
)
from .request_parsing import (
    _decode_payload_preview,
    _detect_sensitive_extension_method,
    _is_json_content_type,
    _looks_like_jsonrpc_envelope,
    _looks_like_jsonrpc_message_payload,
    _normalize_content_type,
    _normalize_v1_jsonrpc_method_alias,
    _parse_content_length,
    _parse_json_body,
    _request_body_too_large_response,
    _RequestBodyTooLargeError,
)
from .state_store import (
    build_interrupt_request_repository,
    build_session_state_repository,
)
from .task_store import (
    TaskStoreOperationError,
    build_database_engine,
    build_task_store,
    describe_lightweight_persistence_backend,
)

logger = logging.getLogger(__name__)
TASK_STORE_ERROR_TYPE = "TASK_STORE_UNAVAILABLE"

__all__ = [
    "_RequestBodyTooLargeError",
    "COMPATIBILITY_PROFILE_EXTENSION_URI",
    "INTERRUPT_CALLBACK_EXTENSION_URI",
    "INTERRUPT_CALLBACK_METHODS",
    "INTERRUPT_RECOVERY_EXTENSION_URI",
    "INTERRUPT_RECOVERY_METHODS",
    "MODEL_SELECTION_EXTENSION_URI",
    "PUBLIC_AGENT_CARD_CACHE_CONTROL",
    "AUTHENTICATED_EXTENDED_CARD_CACHE_CONTROL",
    "PROVIDER_DISCOVERY_EXTENSION_URI",
    "PROVIDER_DISCOVERY_METHODS",
    "SESSION_BINDING_EXTENSION_URI",
    "SESSION_CONTROL_METHODS",
    "SESSION_QUERY_EXTENSION_URI",
    "SESSION_QUERY_METHODS",
    "STREAMING_EXTENSION_URI",
    "WIRE_CONTRACT_EXTENSION_URI",
    "WORKSPACE_CONTROL_EXTENSION_URI",
    "WORKSPACE_CONTROL_METHODS",
    "_build_agent_card_description",
    "_build_chat_examples",
    "_build_jsonrpc_extension_openapi_description",
    "_build_jsonrpc_extension_openapi_examples",
    "_build_rest_message_openapi_examples",
    "_build_session_query_skill_examples",
    "build_authenticated_extended_agent_card",
    "_configure_logging",
    "_decode_payload_preview",
    "_detect_sensitive_extension_method",
    "_is_json_content_type",
    "_looks_like_jsonrpc_envelope",
    "_looks_like_jsonrpc_message_payload",
    "_normalize_v1_jsonrpc_method_alias",
    "_normalize_content_type",
    "_normalize_log_level",
    "_parse_content_length",
    "_parse_json_body",
    "_request_body_too_large_response",
    "build_agent_card",
]

if TYPE_CHECKING:
    from a2a.server.context import ServerCallContext


class OpencodeRequestHandler(DefaultRequestHandler):
    """Custom request handler to gracefully handle client disconnects and prevent dead loops."""

    @staticmethod
    def _task_store_failure_message(operation: str) -> str:
        if operation == "get":
            return "Task store unavailable while loading task state."
        if operation == "save":
            return "Task store unavailable while persisting task state."
        if operation == "delete":
            return "Task store unavailable while deleting task state."
        return "Task store unavailable."

    @classmethod
    def _task_store_failure_metadata(cls, operation: str) -> dict[str, dict[str, dict[str, str]]]:
        return {
            "opencode": {
                "error": {
                    "type": TASK_STORE_ERROR_TYPE,
                    "operation": operation,
                }
            }
        }

    @classmethod
    def _task_store_server_error(cls, exc: TaskStoreOperationError) -> ServerError:
        return ServerError(
            error=InternalError(message=cls._task_store_failure_message(exc.operation))
        )

    @classmethod
    def _task_store_failure_task(
        cls,
        *,
        task_id: str,
        context_id: str,
        operation: str,
    ) -> Task:
        message_text = cls._task_store_failure_message(operation)
        error_message = Message(
            message_id=f"{task_id}:task-store-error",
            role=Role.agent,
            parts=[Part(root=TextPart(text=message_text))],
            task_id=task_id,
            context_id=context_id,
        )
        return Task(
            id=task_id,
            context_id=context_id,
            status=TaskStatus(state=TaskState.failed, message=error_message),
            history=[error_message],
            metadata=cls._task_store_failure_metadata(operation),
        )

    @classmethod
    def _task_store_failure_events(
        cls,
        *,
        task_id: str,
        context_id: str,
        operation: str,
    ) -> tuple[TaskArtifactUpdateEvent, TaskStatusUpdateEvent]:
        message_text = cls._task_store_failure_message(operation)
        return (
            TaskArtifactUpdateEvent(
                task_id=task_id,
                context_id=context_id,
                artifact=Artifact(
                    artifact_id=f"{task_id}:error",
                    parts=[Part(root=TextPart(text=message_text))],
                ),
                append=False,
                last_chunk=True,
            ),
            TaskStatusUpdateEvent(
                task_id=task_id,
                context_id=context_id,
                status=TaskStatus(state=TaskState.failed),
                metadata=cls._task_store_failure_metadata(operation),
                final=True,
            ),
        )

    @staticmethod
    def _resolve_context_id_from_params(params, task_id: str) -> str:  # noqa: ANN001
        message = getattr(params, "message", None)
        return (
            getattr(message, "contextId", None) or getattr(message, "context_id", None) or task_id
        )

    @staticmethod
    def _extract_accepted_output_modes(params) -> list[str] | None:  # noqa: ANN001
        configuration = getattr(params, "configuration", None)
        normalized = normalize_accepted_output_modes(configuration)
        return list(normalized) if normalized is not None else None

    @classmethod
    def _validate_chat_output_modes(cls, params) -> None:  # noqa: ANN001
        accepted_output_modes = cls._extract_accepted_output_modes(params)
        if not accepted_output_modes:
            return

        if not are_modalities_compatible(list(_CHAT_OUTPUT_MODES), accepted_output_modes):
            raise ServerError(
                error=UnsupportedOperationError(
                    message=(
                        "Requested acceptedOutputModes are not compatible "
                        "with OpenCode chat responses."
                    ),
                    data={
                        "accepted_output_modes": accepted_output_modes,
                        "supported_output_modes": list(_CHAT_OUTPUT_MODES),
                    },
                )
            )

        if "text/plain" not in accepted_output_modes:
            raise ServerError(
                error=UnsupportedOperationError(
                    message="OpenCode chat responses require text/plain in acceptedOutputModes.",
                    data={
                        "accepted_output_modes": accepted_output_modes,
                        "required_output_modes": ["text/plain"],
                        "supported_output_modes": list(_CHAT_OUTPUT_MODES),
                    },
                )
            )

    async def on_get_task(
        self,
        params: TaskQueryParams,
        context=None,
    ) -> Task | None:
        try:
            return await super().on_get_task(params, context)
        except TaskStoreOperationError as exc:
            raise self._task_store_server_error(exc) from exc

    async def on_cancel_task(
        self,
        params: TaskIdParams,
        context=None,
    ) -> Task | None:
        try:
            task = await self.task_store.get(params.id, context)
            if not task:
                raise ServerError(error=TaskNotFoundError())

            # Idempotent contract:
            # repeated cancel on already-canceled task returns current terminal state.
            if task.status.state == TaskState.canceled:
                return task

            if task.status.state in TERMINAL_TASK_STATES:
                raise ServerError(
                    error=TaskNotCancelableError(
                        message=f"Task cannot be canceled - current state: {task.status.state}"
                    )
                )
            try:
                return await super().on_cancel_task(params, context)
            except ServerError as exc:
                # Race-safe idempotency: task may become canceled between pre-check and super call.
                if isinstance(exc.error, TaskNotCancelableError):
                    refreshed = await self.task_store.get(params.id, context)
                    if refreshed and refreshed.status.state == TaskState.canceled:
                        return refreshed
                raise
        except TaskStoreOperationError as exc:
            raise self._task_store_server_error(exc) from exc

    async def on_resubscribe_to_task(
        self,
        params: TaskIdParams,
        context=None,
    ):
        try:
            task = await self.task_store.get(params.id, context)
            if not task:
                raise ServerError(error=TaskNotFoundError())

            # Subscribe contract: terminal tasks replay once and then close stream.
            if task.status.state in TERMINAL_TASK_STATES:
                yield task
                return

            async for event in super().on_resubscribe_to_task(params, context):
                yield event
        except TaskStoreOperationError as exc:
            raise self._task_store_server_error(exc) from exc

    async def on_message_send_stream(self, params, context=None):
        self._validate_chat_output_modes(params)
        (
            _task_manager,
            task_id,
            queue,
            result_aggregator,
            producer_task,
        ) = await self._setup_message_execution(params, context)
        emit_stream_request_metrics()
        emit_stream_request_metrics(active_delta=1.0)
        consumer = EventConsumer(queue)
        producer_task.add_done_callback(consumer.agent_task_callback)
        stream_completed = False

        try:
            async for event in result_aggregator.consume_and_emit(consumer):
                if hasattr(event, "id") and event.id:
                    self._validate_task_id_match(task_id, event.id)
                await self._send_push_notification_if_needed(task_id, result_aggregator)
                yield event
            stream_completed = True
        except TaskStoreOperationError as exc:
            logger.exception(
                "Task store operation failed during streaming task_id=%s operation=%s",
                task_id,
                exc.operation,
            )
            for event in self._task_store_failure_events(
                task_id=task_id,
                context_id=self._resolve_context_id_from_params(params, task_id),
                operation=exc.operation,
            ):
                yield event
        except (asyncio.CancelledError, GeneratorExit):
            logger.warning("Client disconnected. Cancelling producer task %s", task_id)
            producer_task.cancel()
            await queue.close(immediate=True)
            raise
        finally:
            emit_stream_request_metrics(active_delta=-1.0)
            logger.debug(
                "A2A stream request closed task_id=%s completed=%s",
                task_id,
                stream_completed,
            )
            cleanup_task = asyncio.create_task(self._cleanup_producer(producer_task, task_id))
            cleanup_task.set_name(f"cleanup_producer:{task_id}")
            self._track_background_task(cleanup_task)

    async def on_message_send(self, params, context=None):
        self._validate_chat_output_modes(params)
        (
            _task_manager,
            task_id,
            queue,
            result_aggregator,
            producer_task,
        ) = await self._setup_message_execution(params, context)

        consumer = EventConsumer(queue)
        producer_task.add_done_callback(consumer.agent_task_callback)

        blocking = True
        if params.configuration and params.configuration.blocking is False:
            blocking = False

        interrupted_or_non_blocking = False
        bg_consume_task: asyncio.Task | None = None
        try:

            async def push_notification_callback() -> None:
                await self._send_push_notification_if_needed(task_id, result_aggregator)

            (
                result,
                interrupted_or_non_blocking,
                bg_consume_task,
            ) = await result_aggregator.consume_and_break_on_interrupt(
                consumer,
                blocking=blocking,
                event_callback=push_notification_callback,
            )
            if bg_consume_task is not None:
                bg_consume_task.set_name(f"continue_consuming:{task_id}")
                self._track_background_task(bg_consume_task)
        except TaskStoreOperationError as exc:
            logger.exception(
                "Task store operation failed during message/send task_id=%s operation=%s",
                task_id,
                exc.operation,
            )
            return self._task_store_failure_task(
                task_id=task_id,
                context_id=self._resolve_context_id_from_params(params, task_id),
                operation=exc.operation,
            )
        except Exception:
            logger.exception("Agent execution failed")
            raise
        finally:
            if interrupted_or_non_blocking:
                cleanup_task = asyncio.create_task(self._cleanup_producer(producer_task, task_id))
                cleanup_task.set_name(f"cleanup_producer:{task_id}")
                self._track_background_task(cleanup_task)
            else:
                try:
                    current_task = asyncio.current_task()
                    if current_task is not None and current_task.cancelled():
                        logger.warning(
                            "Client disconnected from message request. Cancelling task %s", task_id
                        )
                        producer_task.cancel()
                        await queue.close(immediate=True)

                    await asyncio.shield(self._cleanup_producer(producer_task, task_id))
                except asyncio.CancelledError:
                    pass

        if not result:
            raise ServerError(error=InternalError())

        if hasattr(result, "id") and result.id:
            self._validate_task_id_match(task_id, result.id)
            if params.configuration and isinstance(result, Task):
                from a2a.utils.task import apply_history_length

                result = apply_history_length(result, params.configuration.history_length)

        await self._send_push_notification_if_needed(task_id, result_aggregator)

        return result


class IdentityAwareCallContextBuilder(DefaultCallContextBuilder):
    def build(self, request: Request) -> ServerCallContext:
        context = super().build(request)
        path = request.url.path
        raw_path = request.scope.get("raw_path")
        raw_value = ""
        if isinstance(raw_path, (bytes, bytearray)):
            raw_value = raw_path.decode(errors="ignore")
        is_stream = (
            path.endswith("/v1/message:stream")
            or path.endswith("/v1/message%3Astream")
            or raw_value.endswith("/v1/message:stream")
            or raw_value.endswith("/v1/message%3Astream")
        )
        if is_stream:
            context.state["a2a_streaming_request"] = True

        identity = getattr(request.state, "user_identity", None)
        if identity:
            context.state["identity"] = identity
        negotiated_protocol_version = getattr(request.state, "a2a_protocol_version", None)
        if negotiated_protocol_version:
            context.state["a2a_protocol_version"] = negotiated_protocol_version
        requested_protocol_version = getattr(request.state, "a2a_requested_protocol_version", None)
        if requested_protocol_version:
            context.state["a2a_requested_protocol_version"] = requested_protocol_version

        return context


def create_app(settings: Settings) -> FastAPI:
    database_engine = (
        build_database_engine(settings) if settings.a2a_task_store_backend == "database" else None
    )
    session_state_repository = build_session_state_repository(settings, engine=database_engine)
    interrupt_request_repository = build_interrupt_request_repository(
        settings,
        engine=database_engine,
    )
    upstream_client = call_with_supported_kwargs(
        OpencodeUpstreamClient,
        settings,
        interrupt_request_repository=interrupt_request_repository,
    )
    client_manager = A2AClientManager(settings)
    executor = call_with_supported_kwargs(
        OpencodeAgentExecutor,
        upstream_client,
        streaming_enabled=True,
        cancel_abort_timeout_seconds=settings.a2a_cancel_abort_timeout_seconds,
        pending_session_claim_ttl_seconds=settings.a2a_pending_session_claim_ttl_seconds,
        a2a_client_manager=client_manager,
        session_state_repository=session_state_repository,
    )
    task_store = call_with_supported_kwargs(
        build_task_store,
        settings,
        engine=database_engine,
    )
    handler = OpencodeRequestHandler(
        agent_executor=executor,
        task_store=task_store,
    )

    agent_card = build_agent_card(settings)
    extended_agent_card = build_authenticated_extended_agent_card(settings)
    context_builder = IdentityAwareCallContextBuilder()
    runtime_profile = build_runtime_profile(settings)
    capability_snapshot = build_capability_snapshot(runtime_profile=runtime_profile)

    jsonrpc_methods = {
        **capability_snapshot.session_query_methods(),
        **capability_snapshot.provider_discovery_methods(),
        **capability_snapshot.workspace_control_methods(),
        **capability_snapshot.interrupt_recovery_methods(),
        **capability_snapshot.interrupt_callback_methods(),
    }

    # Build JSON-RPC app (POST / by default) and attach REST endpoints (HTTP+JSON) to the same app.
    jsonrpc_app = OpencodeSessionQueryJSONRPCApplication(
        agent_card=agent_card,
        extended_agent_card=extended_agent_card,
        http_handler=handler,
        context_builder=context_builder,
        upstream_client=upstream_client,
        protocol_version=settings.a2a_protocol_version,
        supported_methods=capability_snapshot.supported_jsonrpc_methods(),
        directory_resolver=(
            partial(
                executor._sandbox_policy.resolve_directory,
                default_directory=upstream_client.directory,
            )
            if hasattr(executor, "_sandbox_policy")
            else None
        ),
        session_claim=getattr(executor._session_manager, "claim_preferred_session", None),
        session_claim_finalize=getattr(executor._session_manager, "finalize_session_claim", None),
        session_claim_release=getattr(
            executor._session_manager,
            "release_preferred_session_claim",
            None,
        ),
        methods=jsonrpc_methods,
    )
    rest_adapter = RESTAdapter(
        agent_card=agent_card,
        http_handler=handler,
        context_builder=context_builder,
    )
    public_card_etag = build_agent_card_etag(agent_card)
    extended_card_etag = build_agent_card_etag(extended_agent_card)
    persistence_summary = describe_lightweight_persistence_backend(settings)
    lifespan = build_lifespan(
        database_engine=database_engine,
        task_store=task_store,
        session_state_repository=session_state_repository,
        interrupt_request_repository=interrupt_request_repository,
        client_manager=client_manager,
        upstream_client=upstream_client,
        persistence_summary=persistence_summary,
    )

    app = A2AFastAPI(
        title=settings.a2a_title,
        version=settings.a2a_version,
        lifespan=lifespan,
    )
    app.add_middleware(GZipMiddleware, minimum_size=settings.a2a_http_gzip_minimum_size)
    jsonrpc_app.add_routes_to_app(app)
    for route, callback in rest_adapter.routes().items():
        app.add_api_route(route[0], callback, methods=[route[1]])
    app.state._jsonrpc_app = jsonrpc_app
    app.state.task_store = task_store
    app.state.persistence_summary = persistence_summary
    app.state.agent_executor = executor
    app.state.upstream_client = upstream_client
    app.state.a2a_client_manager = client_manager
    _patch_jsonrpc_openapi_contract(app, settings, runtime_profile=runtime_profile)
    install_runtime_middlewares(
        app,
        settings,
        public_card_etag=public_card_etag,
        extended_card_etag=extended_card_etag,
    )

    @app.get("/health")
    async def health_check():
        return runtime_profile.health_payload(
            service="opencode-a2a",
            version=settings.a2a_version,
            protocol_version=settings.a2a_protocol_version,
        )

    return app


def _normalize_log_level(value: str) -> str:
    normalized = (value or "").strip().upper()
    if normalized in {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}:
        return normalized
    return "WARNING"


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger("uvicorn.error").setLevel(level)
    logging.getLogger("uvicorn.access").setLevel(level)


def main() -> None:
    settings_cls: type[BaseSettings] = Settings
    settings = cast(Settings, settings_cls())
    app = create_app(settings)
    log_level = _normalize_log_level(settings.a2a_log_level)
    _configure_logging(log_level)
    uvicorn.run(app, host=settings.a2a_host, port=settings.a2a_port, log_level=log_level.lower())


if __name__ == "__main__":
    main()

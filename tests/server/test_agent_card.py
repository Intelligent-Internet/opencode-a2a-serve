import json

from opencode_a2a.contracts.extensions import (
    SESSION_QUERY_DEFAULT_LIMIT,
    SESSION_QUERY_MAX_LIMIT,
    build_service_behavior_contract_params,
)
from opencode_a2a.jsonrpc.application import SESSION_CONTEXT_PREFIX
from opencode_a2a.server.agent_card import build_authenticated_extended_agent_card
from opencode_a2a.server.application import (
    COMPATIBILITY_PROFILE_EXTENSION_URI,
    INTERRUPT_CALLBACK_EXTENSION_URI,
    INTERRUPT_RECOVERY_EXTENSION_URI,
    MODEL_SELECTION_EXTENSION_URI,
    PROVIDER_DISCOVERY_EXTENSION_URI,
    SESSION_BINDING_EXTENSION_URI,
    SESSION_QUERY_EXTENSION_URI,
    STREAMING_EXTENSION_URI,
    WIRE_CONTRACT_EXTENSION_URI,
    WORKSPACE_CONTROL_EXTENSION_URI,
    build_agent_card,
)
from tests.support.helpers import make_settings


def test_agent_card_description_reflects_actual_transport_capabilities() -> None:
    card = build_agent_card(make_settings(a2a_bearer_token="test-token"))
    skills_by_id = {skill.id: skill for skill in card.skills}

    assert "HTTP+JSON and JSON-RPC transports" in card.description
    assert "authenticated extended Agent Card discovery" in card.description
    assert (
        "all consumers share the same underlying OpenCode workspace/environment" in card.description
    )
    assert "Single-tenant deployment" in card.description
    assert card.capabilities.streaming is True
    assert card.supports_authenticated_extended_card is True
    assert card.default_input_modes == ["text/plain", "application/octet-stream"]
    assert card.default_output_modes == ["text/plain", "application/json"]
    assert list(card.security_schemes.keys()) == ["bearerAuth"]
    assert card.security == [{"bearerAuth": []}]
    assert skills_by_id["opencode.chat"].input_modes == ["text/plain", "application/octet-stream"]
    assert skills_by_id["opencode.chat"].output_modes == ["text/plain", "application/json"]
    assert skills_by_id["opencode.sessions.query"].input_modes == ["application/json"]
    assert skills_by_id["opencode.sessions.query"].output_modes == ["application/json"]
    assert skills_by_id["opencode.interrupt.callback"].input_modes == ["application/json"]
    assert skills_by_id["opencode.interrupt.callback"].output_modes == ["application/json"]


def test_public_agent_card_is_slimmed_but_keeps_core_shared_contract_hints() -> None:
    public_card = build_agent_card(make_settings(a2a_bearer_token="test-token"))
    extended_card = build_authenticated_extended_agent_card(
        make_settings(a2a_bearer_token="test-token")
    )
    ext_by_uri = {ext.uri: ext for ext in public_card.capabilities.extensions or []}

    for uri in ext_by_uri:
        assert uri.startswith("https://github.com/Intelligent-Internet/opencode-a2a/blob/main/")

    assert ext_by_uri[SESSION_BINDING_EXTENSION_URI].params == {
        "metadata_field": "metadata.shared.session.id",
        "behavior": "prefer_metadata_binding_else_create_session",
        "supported_metadata": [
            "shared.session.id",
            "opencode.directory",
            "opencode.workspace.id",
        ],
        "provider_private_metadata": [
            "opencode.directory",
            "opencode.workspace.id",
        ],
    }
    assert ext_by_uri[MODEL_SELECTION_EXTENSION_URI].params == {
        "metadata_field": "metadata.shared.model",
        "behavior": "prefer_metadata_model_else_upstream_default",
        "applies_to_methods": ["message/send", "message/stream"],
        "supported_metadata": [
            "shared.model.providerID",
            "shared.model.modelID",
        ],
        "provider_private_metadata": [],
        "fields": {
            "providerID": "metadata.shared.model.providerID",
            "modelID": "metadata.shared.model.modelID",
        },
    }
    assert ext_by_uri[STREAMING_EXTENSION_URI].params == {
        "artifact_metadata_field": "metadata.shared.stream",
        "progress_metadata_field": "metadata.shared.progress",
        "interrupt_metadata_field": "metadata.shared.interrupt",
        "session_metadata_field": "metadata.shared.session",
        "usage_metadata_field": "metadata.shared.usage",
        "block_types": ["text", "reasoning", "tool_call"],
        "stream_fields": {
            "block_type": "metadata.shared.stream.block_type",
            "message_id": "metadata.shared.stream.message_id",
            "sequence": "metadata.shared.stream.sequence",
        },
        "progress_fields": {
            "type": "metadata.shared.progress.type",
            "status": "metadata.shared.progress.status",
        },
        "interrupt_fields": {
            "request_id": "metadata.shared.interrupt.request_id",
            "type": "metadata.shared.interrupt.type",
            "phase": "metadata.shared.interrupt.phase",
        },
        "session_fields": {
            "id": "metadata.shared.session.id",
            "title": "metadata.shared.session.title",
        },
        "usage_fields": {
            "input_tokens": "metadata.shared.usage.input_tokens",
            "output_tokens": "metadata.shared.usage.output_tokens",
            "total_tokens": "metadata.shared.usage.total_tokens",
        },
    }
    assert ext_by_uri[INTERRUPT_CALLBACK_EXTENSION_URI].params == {
        "methods": {
            "reply_permission": "a2a.interrupt.permission.reply",
            "reply_question": "a2a.interrupt.question.reply",
            "reject_question": "a2a.interrupt.question.reject",
        },
        "supported_interrupt_events": [
            "permission.asked",
            "question.asked",
        ],
        "request_id_field": "metadata.shared.interrupt.request_id",
    }

    for uri in (
        SESSION_QUERY_EXTENSION_URI,
        PROVIDER_DISCOVERY_EXTENSION_URI,
        WORKSPACE_CONTROL_EXTENSION_URI,
        INTERRUPT_RECOVERY_EXTENSION_URI,
        COMPATIBILITY_PROFILE_EXTENSION_URI,
        WIRE_CONTRACT_EXTENSION_URI,
    ):
        assert ext_by_uri[uri].params is None

    public_size = len(
        json.dumps(
            public_card.model_dump(mode="json", by_alias=True, exclude_none=True),
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    extended_size = len(
        json.dumps(
            extended_card.model_dump(mode="json", by_alias=True, exclude_none=True),
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    assert public_size < extended_size
    assert public_size < 10000


def test_agent_card_injects_profile_into_extensions() -> None:
    card = build_authenticated_extended_agent_card(
        make_settings(
            a2a_bearer_token="test-token",
            a2a_project="alpha",
            opencode_workspace_root="/srv/workspaces/alpha",
            opencode_agent="code-reviewer",
            opencode_variant="safe",
            a2a_allow_directory_override=False,
            a2a_sandbox_mode="workspace-write",
            a2a_sandbox_filesystem_scope="workspace_and_declared_roots",
            a2a_sandbox_writable_roots=("/srv/workspaces/alpha", "/tmp/opencode"),
            a2a_network_access="restricted",
            a2a_network_allowed_domains=("api.openai.com", "github.com"),
            a2a_approval_policy="never",
            a2a_approval_escalation_behavior="unsupported",
            a2a_write_access_scope="workspace_and_declared_roots",
            a2a_write_access_outside_workspace="disallowed",
        )
    )
    ext_by_uri = {ext.uri: ext for ext in card.capabilities.extensions or []}

    binding = ext_by_uri[SESSION_BINDING_EXTENSION_URI]
    profile = binding.params["profile"]
    assert binding.params["metadata_field"] == "metadata.shared.session.id"
    assert binding.params["supported_metadata"] == [
        "shared.session.id",
        "opencode.directory",
        "opencode.workspace.id",
    ]
    assert binding.params["provider_private_metadata"] == [
        "opencode.directory",
        "opencode.workspace.id",
    ]
    assert profile["profile_id"] == "opencode-a2a-single-tenant-coding-v1"
    assert profile["deployment"] == {
        "id": "single_tenant_shared_workspace",
        "single_tenant": True,
        "shared_workspace_across_consumers": True,
        "tenant_isolation": "none",
    }
    assert profile["runtime_context"] == {
        "project": "alpha",
        "workspace_root": "/srv/workspaces/alpha",
        "agent": "code-reviewer",
        "variant": "safe",
    }
    assert profile["runtime_features"]["directory_binding"] == {
        "allow_override": False,
        "scope": "workspace_root_only",
        "metadata_field": "metadata.opencode.directory",
    }
    assert profile["runtime_features"]["workspace_binding"] == {
        "enabled": True,
        "metadata_field": "metadata.opencode.workspace.id",
        "upstream_query_param": "workspace",
        "precedence": "prefer_workspace_else_directory",
    }
    assert profile["runtime_features"]["execution_environment"] == {
        "sandbox": {
            "mode": "workspace-write",
            "filesystem_scope": "workspace_and_declared_roots",
            "writable_roots": ["/srv/workspaces/alpha", "/tmp/opencode"],
        },
        "network": {
            "access": "restricted",
            "allowed_domains": ["api.openai.com", "github.com"],
        },
        "approval": {
            "policy": "never",
            "escalation_behavior": "unsupported",
        },
        "write_access": {
            "scope": "workspace_and_declared_roots",
            "outside_workspace": "disallowed",
        },
    }

    model_selection = ext_by_uri[MODEL_SELECTION_EXTENSION_URI]
    assert model_selection.params["metadata_field"] == "metadata.shared.model"
    assert model_selection.params["fields"]["providerID"] == "metadata.shared.model.providerID"
    assert model_selection.params["fields"]["modelID"] == "metadata.shared.model.modelID"
    assert model_selection.params["applies_to_methods"] == ["message/send", "message/stream"]
    assert model_selection.params["behavior"] == "prefer_metadata_model_else_upstream_default"

    streaming = ext_by_uri[STREAMING_EXTENSION_URI]
    assert streaming.params["artifact_metadata_field"] == "metadata.shared.stream"
    assert streaming.params["progress_metadata_field"] == "metadata.shared.progress"
    assert streaming.params["interrupt_metadata_field"] == "metadata.shared.interrupt"
    assert streaming.params["session_metadata_field"] == "metadata.shared.session"
    assert streaming.params["usage_metadata_field"] == "metadata.shared.usage"
    assert streaming.params["block_types"] == ["text", "reasoning", "tool_call"]
    assert streaming.params["block_contracts"] == {
        "text": {
            "part_kind": "text",
            "payload_field": "artifact.parts[].text",
        },
        "reasoning": {
            "part_kind": "text",
            "payload_field": "artifact.parts[].text",
        },
        "tool_call": {
            "part_kind": "data",
            "payload_field": "artifact.parts[].data",
            "payload_fields": {
                "call_id": "artifact.parts[].data.call_id",
                "tool": "artifact.parts[].data.tool",
                "status": "artifact.parts[].data.status",
                "title": "artifact.parts[].data.title",
                "subtitle": "artifact.parts[].data.subtitle",
                "input": "artifact.parts[].data.input",
                "output": "artifact.parts[].data.output",
                "error": "artifact.parts[].data.error",
            },
        },
    }
    assert streaming.params["stream_fields"]["sequence"] == "metadata.shared.stream.sequence"
    assert streaming.params["progress_fields"]["type"] == "metadata.shared.progress.type"
    assert streaming.params["interrupt_fields"] == {
        "request_id": "metadata.shared.interrupt.request_id",
        "type": "metadata.shared.interrupt.type",
        "phase": "metadata.shared.interrupt.phase",
        "details": "metadata.shared.interrupt.details",
        "resolution": "metadata.shared.interrupt.resolution",
    }
    assert streaming.params["session_fields"] == {
        "id": "metadata.shared.session.id",
        "title": "metadata.shared.session.title",
    }
    assert streaming.params["usage_fields"] == {
        "input_tokens": "metadata.shared.usage.input_tokens",
        "output_tokens": "metadata.shared.usage.output_tokens",
        "total_tokens": "metadata.shared.usage.total_tokens",
        "reasoning_tokens": "metadata.shared.usage.reasoning_tokens",
        "cost": "metadata.shared.usage.cost",
        "cache_tokens": {
            "read_tokens": "metadata.shared.usage.cache_tokens.read_tokens",
            "write_tokens": "metadata.shared.usage.cache_tokens.write_tokens",
        },
    }

    session_query = ext_by_uri[SESSION_QUERY_EXTENSION_URI]
    assert session_query.params["profile"]["runtime_context"]["project"] == "alpha"
    assert session_query.params["control_methods"] == {
        "prompt_async": "opencode.sessions.prompt_async",
        "command": "opencode.sessions.command",
    }
    assert session_query.params["lifecycle_methods"] == {
        "status": "opencode.sessions.status",
        "get_session": "opencode.sessions.get",
        "get_session_children": "opencode.sessions.children",
        "get_session_todo": "opencode.sessions.todo",
        "get_session_diff": "opencode.sessions.diff",
        "get_session_message": "opencode.sessions.messages.get",
        "fork": "opencode.sessions.fork",
        "share": "opencode.sessions.share",
        "unshare": "opencode.sessions.unshare",
        "summarize": "opencode.sessions.summarize",
        "revert": "opencode.sessions.revert",
        "unrevert": "opencode.sessions.unrevert",
    }
    assert session_query.params["methods"]["status"] == "opencode.sessions.status"
    assert session_query.params["methods"]["get_session"] == "opencode.sessions.get"
    assert session_query.params["methods"]["prompt_async"] == "opencode.sessions.prompt_async"
    assert session_query.params["methods"]["command"] == "opencode.sessions.command"
    assert "shell" not in session_query.params["methods"]
    assert session_query.params["control_method_flags"]["opencode.sessions.shell"] == {
        "enabled_by_default": False,
        "config_key": "A2A_ENABLE_SESSION_SHELL",
    }
    assert session_query.params["pagination"]["default_limit"] == SESSION_QUERY_DEFAULT_LIMIT
    assert session_query.params["pagination"]["max_limit"] == SESSION_QUERY_MAX_LIMIT
    assert session_query.params["pagination"]["cursor_param"] == "before"
    assert session_query.params["pagination"]["result_cursor_field"] == "next_cursor"
    assert session_query.params["pagination"]["applies_to"] == [
        "opencode.sessions.list",
        "opencode.sessions.messages.list",
    ]
    assert session_query.params["pagination"]["cursor_applies_to"] == [
        "opencode.sessions.messages.list"
    ]
    prompt_contract = session_query.params["method_contracts"]["opencode.sessions.prompt_async"]
    command_contract = session_query.params["method_contracts"]["opencode.sessions.command"]
    status_contract = session_query.params["method_contracts"]["opencode.sessions.status"]
    get_contract = session_query.params["method_contracts"]["opencode.sessions.get"]
    diff_contract = session_query.params["method_contracts"]["opencode.sessions.diff"]
    message_get_contract = session_query.params["method_contracts"][
        "opencode.sessions.messages.get"
    ]
    fork_contract = session_query.params["method_contracts"]["opencode.sessions.fork"]
    summarize_contract = session_query.params["method_contracts"]["opencode.sessions.summarize"]
    revert_contract = session_query.params["method_contracts"]["opencode.sessions.revert"]
    unrevert_contract = session_query.params["method_contracts"]["opencode.sessions.unrevert"]
    list_contract = session_query.params["method_contracts"]["opencode.sessions.list"]
    messages_contract = session_query.params["method_contracts"]["opencode.sessions.messages.list"]
    assert status_contract["result"]["fields"] == ["items"]
    assert get_contract["params"]["required"] == ["session_id"]
    assert get_contract["result"]["fields"] == ["item"]
    assert diff_contract["params"]["optional"] == [
        "message_id",
        "directory",
        "metadata.opencode.directory",
        "metadata.opencode.workspace.id",
    ]
    assert message_get_contract["params"]["required"] == ["session_id", "message_id"]
    assert fork_contract["params"]["optional"] == [
        "request.messageID",
        "directory",
        "metadata.opencode.directory",
        "metadata.opencode.workspace.id",
    ]
    assert summarize_contract["params"]["optional"] == [
        "request.providerID",
        "request.modelID",
        "request.auto",
        "directory",
        "metadata.opencode.directory",
        "metadata.opencode.workspace.id",
    ]
    assert summarize_contract["result"]["fields"] == ["ok", "session_id"]
    assert revert_contract["params"]["required"] == ["session_id", "request.messageID"]
    assert revert_contract["params"]["optional"] == [
        "request.partID",
        "directory",
        "metadata.opencode.directory",
        "metadata.opencode.workspace.id",
    ]
    assert revert_contract["result"]["items_type"] == "SessionSummary"
    assert unrevert_contract["result"]["fields"] == ["item"]
    assert prompt_contract["params"]["required"] == ["session_id", "request.parts"]
    assert prompt_contract["result"]["fields"] == ["ok", "session_id"]
    assert command_contract["params"]["required"] == [
        "session_id",
        "request.command",
        "request.arguments",
    ]
    assert command_contract["result"]["fields"] == ["item"]
    assert list_contract["params"]["optional"] == [
        "limit",
        "directory",
        "metadata.opencode.workspace.id",
        "roots",
        "start",
        "search",
        "query.limit",
        "query.directory",
        "query.roots",
        "query.start",
        "query.search",
    ]
    assert messages_contract["params"]["optional"] == [
        "limit",
        "before",
        "metadata.opencode.workspace.id",
        "query.limit",
        "query.before",
    ]
    assert messages_contract["result"]["fields"] == ["items", "next_cursor"]
    assert list_contract["notification_response_status"] == 204
    assert messages_contract["notification_response_status"] == 204
    assert summarize_contract["notification_response_status"] == 204
    assert revert_contract["notification_response_status"] == 204
    assert unrevert_contract["notification_response_status"] == 204
    assert prompt_contract["notification_response_status"] == 204
    assert "result_envelope" not in session_query.params
    assert "opencode.sessions.shell" not in session_query.params["method_contracts"]
    assert (
        session_query.params["context_semantics"]["a2a_context_id_prefix"] == SESSION_CONTEXT_PREFIX
    )
    assert (
        session_query.params["context_semantics"]["upstream_session_id_field"]
        == "metadata.shared.session.id"
    )
    assert session_query.params["errors"]["business_codes"] == {
        "SESSION_NOT_FOUND": -32001,
        "SESSION_FORBIDDEN": -32006,
        "UPSTREAM_UNREACHABLE": -32002,
        "UPSTREAM_HTTP_ERROR": -32003,
        "UPSTREAM_PAYLOAD_ERROR": -32005,
    }
    assert session_query.params["errors"]["error_data_fields"] == [
        "type",
        "method",
        "session_id",
        "upstream_status",
        "detail",
    ]
    assert session_query.params["errors"]["invalid_params_data_fields"] == [
        "type",
        "field",
        "fields",
        "supported",
        "unsupported",
    ]

    provider_discovery = ext_by_uri[PROVIDER_DISCOVERY_EXTENSION_URI]
    assert provider_discovery.params["profile"]["runtime_context"]["project"] == "alpha"
    assert provider_discovery.params["methods"] == {
        "list_providers": "opencode.providers.list",
        "list_models": "opencode.models.list",
    }
    assert provider_discovery.params["supported_metadata"] == [
        "opencode.directory",
        "opencode.workspace.id",
    ]
    assert "result_envelope" not in provider_discovery.params
    assert provider_discovery.params["method_contracts"]["opencode.providers.list"]["result"] == {
        "fields": ["items", "default_by_provider", "connected"],
        "items_type": "ProviderSummary[]",
    }
    assert provider_discovery.params["method_contracts"]["opencode.models.list"]["params"] == {
        "optional": ["provider_id"]
    }
    assert provider_discovery.params["method_contracts"]["opencode.models.list"]["result"] == {
        "fields": ["items", "default_by_provider", "connected"],
        "items_type": "ModelSummary[]",
    }
    assert provider_discovery.params["errors"]["business_codes"] == {
        "UPSTREAM_UNREACHABLE": -32002,
        "UPSTREAM_HTTP_ERROR": -32003,
        "UPSTREAM_PAYLOAD_ERROR": -32005,
    }

    workspace_control = ext_by_uri[WORKSPACE_CONTROL_EXTENSION_URI]
    assert workspace_control.params["profile"]["runtime_context"]["project"] == "alpha"
    assert workspace_control.params["methods"] == {
        "list_projects": "opencode.projects.list",
        "get_current_project": "opencode.projects.current",
        "list_workspaces": "opencode.workspaces.list",
        "create_workspace": "opencode.workspaces.create",
        "remove_workspace": "opencode.workspaces.remove",
        "list_worktrees": "opencode.worktrees.list",
        "create_worktree": "opencode.worktrees.create",
        "remove_worktree": "opencode.worktrees.remove",
        "reset_worktree": "opencode.worktrees.reset",
    }
    assert workspace_control.params["routing_fields"]["workspace_id"] == (
        "metadata.opencode.workspace.id"
    )
    assert workspace_control.params["method_contracts"]["opencode.projects.list"]["result"] == {
        "fields": ["items"],
        "items_type": "Project[]",
    }
    assert workspace_control.params["method_contracts"]["opencode.workspaces.create"]["params"] == {
        "required": ["request.type"],
        "optional": ["request.id", "request.branch", "request.extra"],
    }
    assert workspace_control.params["method_contracts"]["opencode.worktrees.reset"]["result"] == {
        "fields": ["ok"],
        "items_type": "boolean",
    }

    interrupt_recovery = ext_by_uri[INTERRUPT_RECOVERY_EXTENSION_URI]
    assert interrupt_recovery.params["profile"]["runtime_context"]["project"] == "alpha"
    assert interrupt_recovery.params["methods"] == {
        "list_permissions": "opencode.permissions.list",
        "list_questions": "opencode.questions.list",
    }
    assert interrupt_recovery.params["method_contracts"]["opencode.permissions.list"]["result"] == {
        "fields": ["items"],
        "items_type": "InterruptRequest[]",
    }
    assert interrupt_recovery.params["item_fields"]["details"] == "items[].details"
    assert interrupt_recovery.params["errors"]["invalid_params_data_fields"] == [
        "type",
        "field",
        "fields",
    ]

    interrupt = ext_by_uri[INTERRUPT_CALLBACK_EXTENSION_URI]
    assert interrupt.params["profile"]["runtime_context"]["project"] == "alpha"
    assert interrupt.params["request_id_field"] == "metadata.shared.interrupt.request_id"
    assert interrupt.params["supported_metadata"] == [
        "opencode.directory",
        "opencode.workspace.id",
    ]
    assert interrupt.params["provider_private_metadata"] == [
        "opencode.directory",
        "opencode.workspace.id",
    ]
    assert interrupt.params["context_fields"]["directory"] == "metadata.opencode.directory"
    assert interrupt.params["context_fields"]["workspace_id"] == "metadata.opencode.workspace.id"
    assert interrupt.params["errors"]["business_codes"] == {
        "INTERRUPT_REQUEST_NOT_FOUND": -32004,
        "INTERRUPT_REQUEST_EXPIRED": -32007,
        "INTERRUPT_TYPE_MISMATCH": -32008,
        "UPSTREAM_UNREACHABLE": -32002,
        "UPSTREAM_HTTP_ERROR": -32003,
    }
    assert interrupt.params["errors"]["error_types"] == [
        "INTERRUPT_REQUEST_NOT_FOUND",
        "INTERRUPT_REQUEST_EXPIRED",
        "INTERRUPT_TYPE_MISMATCH",
        "UPSTREAM_UNREACHABLE",
        "UPSTREAM_HTTP_ERROR",
    ]
    assert interrupt.params["errors"]["error_data_fields"] == [
        "type",
        "request_id",
        "expected_interrupt_type",
        "actual_interrupt_type",
        "upstream_status",
        "detail",
    ]
    assert interrupt.params["errors"]["invalid_params_data_fields"] == [
        "type",
        "field",
        "fields",
        "request_id",
    ]
    for method_name in (
        "a2a.interrupt.permission.reply",
        "a2a.interrupt.question.reply",
        "a2a.interrupt.question.reject",
    ):
        assert (
            interrupt.params["method_contracts"][method_name]["notification_response_status"] == 204
        )

    compatibility = ext_by_uri[COMPATIBILITY_PROFILE_EXTENSION_URI]
    expected_service_behaviors = build_service_behavior_contract_params()
    assert compatibility.params["extension_retention"][MODEL_SELECTION_EXTENSION_URI] == {
        "surface": "core-runtime-metadata",
        "availability": "always",
        "retention": "stable",
    }
    assert compatibility.params["extension_retention"][PROVIDER_DISCOVERY_EXTENSION_URI] == {
        "surface": "jsonrpc-extension",
        "availability": "always",
        "retention": "stable",
    }
    shell_policy = compatibility.params["method_retention"]["opencode.sessions.shell"]
    assert compatibility.params["deployment"]["id"] == "single_tenant_shared_workspace"
    assert compatibility.params["runtime_features"]["session_shell"]["availability"] == "disabled"
    assert shell_policy["availability"] == "disabled"
    assert shell_policy["retention"] == "deployment-conditional"
    assert shell_policy["toggle"] == "A2A_ENABLE_SESSION_SHELL"
    assert compatibility.params["method_retention"]["agent/getAuthenticatedExtendedCard"] == {
        "surface": "core",
        "availability": "always",
        "retention": "required",
    }
    assert compatibility.params["method_retention"]["tasks/pushNotificationConfig/get"] == {
        "surface": "core",
        "availability": "always",
        "retention": "required",
    }
    assert compatibility.params["service_behaviors"] == expected_service_behaviors
    assert compatibility.params["service_behaviors"]["classification"] == (
        "service-level-semantic-enhancement"
    )
    assert compatibility.params["service_behaviors"]["methods"]["tasks/cancel"]["idempotency"] == {
        "already_canceled": {
            "behavior": "return_current_terminal_task",
            "returns_current_state": "canceled",
            "error": None,
        }
    }
    assert compatibility.params["service_behaviors"]["methods"]["tasks/resubscribe"][
        "terminal_state_behavior"
    ] == {
        "behavior": "replay_terminal_task_once_then_close",
        "delivery": "single_task_snapshot",
        "closes_stream": True,
    }
    assert compatibility.description.endswith("deployment-conditional methods.")

    wire_contract = ext_by_uri[WIRE_CONTRACT_EXTENSION_URI]
    assert wire_contract.params["profile"]["profile_id"] == "opencode-a2a-single-tenant-coding-v1"
    assert MODEL_SELECTION_EXTENSION_URI in wire_contract.params["extensions"]["extension_uris"]
    assert PROVIDER_DISCOVERY_EXTENSION_URI in wire_contract.params["extensions"]["extension_uris"]
    assert WORKSPACE_CONTROL_EXTENSION_URI in wire_contract.params["extensions"]["extension_uris"]
    assert INTERRUPT_RECOVERY_EXTENSION_URI in wire_contract.params["extensions"]["extension_uris"]
    assert "agent/getAuthenticatedExtendedCard" in wire_contract.params["all_jsonrpc_methods"]
    assert "tasks/pushNotificationConfig/get" in wire_contract.params["all_jsonrpc_methods"]
    assert "GET /v1/tasks" in wire_contract.params["core"]["http_endpoints"]
    assert (
        "GET /v1/tasks/{id}/pushNotificationConfigs"
        in wire_contract.params["core"]["http_endpoints"]
    )
    assert "opencode.sessions.shell" not in wire_contract.params["all_jsonrpc_methods"]
    assert wire_contract.params["service_behaviors"] == expected_service_behaviors
    assert wire_contract.params["extensions"]["conditionally_available_methods"] == {
        "opencode.sessions.shell": {
            "reason": "disabled_by_configuration",
            "toggle": "A2A_ENABLE_SESSION_SHELL",
        }
    }
    assert wire_contract.description.endswith("unified error contracts.")


def test_agent_card_chat_examples_include_project_hint_when_configured() -> None:
    card = build_agent_card(make_settings(a2a_bearer_token="test-token", a2a_project="alpha"))
    chat_skill = next(skill for skill in card.skills if skill.id == "opencode.chat")
    assert chat_skill.examples is None
    assert "shared session binding" in chat_skill.description
    assert "core-a2a" in chat_skill.tags
    assert "portable" in chat_skill.tags


def test_agent_card_contracts_include_shell_when_enabled() -> None:
    card = build_authenticated_extended_agent_card(
        make_settings(a2a_bearer_token="test-token", a2a_enable_session_shell=True)
    )
    ext_by_uri = {ext.uri: ext for ext in card.capabilities.extensions or []}

    session_query = ext_by_uri[SESSION_QUERY_EXTENSION_URI]
    assert session_query.params["control_methods"]["shell"] == "opencode.sessions.shell"
    assert session_query.params["methods"]["shell"] == "opencode.sessions.shell"
    assert "opencode.sessions.shell" in session_query.params["method_contracts"]

    compatibility = ext_by_uri[COMPATIBILITY_PROFILE_EXTENSION_URI]
    shell_policy = compatibility.params["method_retention"]["opencode.sessions.shell"]
    assert compatibility.params["runtime_features"]["session_shell"]["availability"] == "enabled"
    assert shell_policy["availability"] == "enabled"

    wire_contract = ext_by_uri[WIRE_CONTRACT_EXTENSION_URI]
    assert wire_contract.params["profile"]["runtime_features"]["session_shell"]["availability"] == (
        "enabled"
    )
    assert "opencode.sessions.shell" in wire_contract.params["all_jsonrpc_methods"]
    assert wire_contract.params["extensions"]["conditionally_available_methods"] == {}

    session_skill = next(skill for skill in card.skills if skill.id == "opencode.sessions.query")
    assert any("opencode.sessions.shell" in example for example in session_skill.examples)


def test_agent_card_skills_hide_shell_when_disabled_by_default() -> None:
    card = build_agent_card(make_settings(a2a_bearer_token="test-token"))

    session_skill = next(skill for skill in card.skills if skill.id == "opencode.sessions.query")
    provider_skill = next(skill for skill in card.skills if skill.id == "opencode.providers.query")
    workspace_skill = next(
        skill for skill in card.skills if skill.id == "opencode.workspace.control"
    )

    assert "provider-private" in session_skill.tags
    assert "provider-private" in session_skill.description
    assert session_skill.examples is None
    assert "provider-private" in provider_skill.tags
    assert provider_skill.examples is None
    assert workspace_skill.examples is None
    interrupt_recovery_skill = next(
        skill for skill in card.skills if skill.id == "opencode.interrupt.recovery"
    )
    assert interrupt_recovery_skill.examples is None


def test_agent_card_hides_shell_when_policy_disables_it() -> None:
    card = build_authenticated_extended_agent_card(
        make_settings(
            a2a_bearer_token="test-token",
            a2a_enable_session_shell=True,
            a2a_sandbox_mode="read-only",
            a2a_write_access_scope="workspace_only",
        )
    )
    ext_by_uri = {ext.uri: ext for ext in card.capabilities.extensions or []}

    session_query = ext_by_uri[SESSION_QUERY_EXTENSION_URI]
    compatibility = ext_by_uri[COMPATIBILITY_PROFILE_EXTENSION_URI]

    assert "shell" not in session_query.params["methods"]
    assert "opencode.sessions.shell" not in session_query.params["method_contracts"]
    assert compatibility.params["runtime_features"]["session_shell"]["availability"] == "disabled"

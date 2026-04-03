# External Conformance Triage

This document records the first local `./scripts/conformance.sh mandatory` run against the official `a2aproject/a2a-tck` using the repository's dummy-backed SUT.

## Standards Used For Triage

- `a2a-sdk==0.3.25` as installed in this repository:
  - `AgentCard` uses `additionalInterfaces`, not `supportedInterfaces`.
  - JSON-RPC request models use `message/send`, `tasks/get`, `tasks/cancel`, and `agent/getAuthenticatedExtendedCard`.
  - The installed SDK does not expose a JSON-RPC `ListTasks` request model.
- A2A v0.3.0 specification:
  - JSON-RPC methods use the `{category}/{action}` pattern such as `message/send` and `tasks/get`.
  - Transport declarations use `preferredTransport` plus `additionalInterfaces`.
  - The method mapping table lists `tasks/list` as gRPC/REST only.
- Repository compatibility policy:
  - `A2A-Version` negotiation supports both `0.3` and `1.0`.
  - Payloads still follow the shipped `0.3` SDK baseline.
  - `1.0` compatibility is currently documented as partial rather than complete.

## Classification Labels

- `TCK issue`: the failing expectation conflicts with `a2a-sdk==0.3.25` and the v0.3.0 baseline used by this repository.
- `TCK issue; also a repo v1.0 gap`: the exact failure is caused by a TCK mismatch, but the same area would still need extra work for stronger `1.0` compatibility.
- `TCK issue / local experiment artifact`: the failure comes from an aggressive heuristic or from local dummy-run characteristics and should not be treated as a runtime protocol bug.

## Per-Test Triage

- `tests/mandatory/authentication/test_auth_compliance_v030.py::test_security_scheme_structure_compliance`: `TCK issue`. The TCK expects each `securitySchemes` entry to be wrapped as `{httpAuthSecurityScheme: {...}}`, but `a2a-sdk==0.3.25` exposes the flattened OpenAPI-shaped object with fields like `type`, `scheme`, `description`, and `bearerFormat`.
- `tests/mandatory/authentication/test_auth_enforcement.py::test_authentication_scheme_consistency`: `TCK issue`. Same root cause as the previous test: the TCK validates a non-SDK wrapper shape instead of the installed SDK schema.
- `tests/mandatory/jsonrpc/test_a2a_error_codes_enhanced.py::test_push_notification_not_supported_error_32003_enhanced`: `TCK issue`. The failure is a TCK helper bug: `transport_create_task_push_notification_config()` is called with the wrong positional signature before the runtime behavior is even exercised.
- `tests/mandatory/jsonrpc/test_json_rpc_compliance.py::test_rejects_invalid_json_rpc_requests[invalid_request4--32602]`: `TCK issue`. The test sends JSON-RPC method `SendMessage`; under the v0.3.0 / SDK 0.3.25 baseline the correct method is `message/send`, so the runtime correctly returns `-32601` for an unknown method instead of `-32602`.
- `tests/mandatory/jsonrpc/test_json_rpc_compliance.py::test_rejects_invalid_params`: `TCK issue`. Same method-name mismatch as above; with the correct `message/send` method the runtime returns `-32602` for invalid parameters.
- `tests/mandatory/jsonrpc/test_protocol_violations.py::test_duplicate_request_ids`: `TCK issue`. The first request already fails because the TCK uses `SendMessage` instead of `message/send`, so the duplicate-ID assertion never reaches the actual duplicate-ID behavior.
- `tests/mandatory/protocol/test_a2a_v030_new_methods.py::TestMethodMappingCompliance::test_core_method_mapping_compliance`: `TCK issue; also a repo v1.0 gap`. The JSON-RPC client uses PascalCase methods (`SendMessage`, `GetTask`, `CancelTask`) that do not match the v0.3.0 JSON-RPC mapping, but the repository also does not currently provide PascalCase aliases even when `A2A-Version: 1.0` is negotiated.
- `tests/mandatory/protocol/test_message_send_method.py::test_message_send_valid_text`: `TCK issue; also a repo v1.0 gap`. The failing request uses `SendMessage` over JSON-RPC; the repository correctly supports `message/send` for the current SDK baseline, but not the PascalCase alias.
- `tests/mandatory/protocol/test_message_send_method.py::test_message_send_invalid_params`: `TCK issue; also a repo v1.0 gap`. Direct cause is the same PascalCase JSON-RPC method mismatch.
- `tests/mandatory/protocol/test_message_send_method.py::test_message_send_continue_task`: `TCK issue; also a repo v1.0 gap`. Direct cause is again `SendMessage` instead of `message/send`.
- `tests/mandatory/protocol/test_state_transitions.py::test_task_history_length`: `TCK issue; also a repo v1.0 gap`. Task creation fails only because the TCK uses `SendMessage` on JSON-RPC.
- `tests/mandatory/protocol/test_tasks_cancel_method.py::test_tasks_cancel_valid`: `TCK issue; also a repo v1.0 gap`. The fixture cannot create a task because the TCK uses `SendMessage`; the runtime's `tasks/cancel` behavior is not the direct failing cause in this run.
- `tests/mandatory/protocol/test_tasks_cancel_method.py::test_tasks_cancel_nonexistent`: `TCK issue; also a repo v1.0 gap`. The TCK calls JSON-RPC `CancelTask`; under the v0.3.0 baseline the method is `tasks/cancel`. With the correct method, the runtime returns `Task not found` / `-32001`.
- `tests/mandatory/protocol/test_tasks_get_method.py::test_tasks_get_valid`: `TCK issue; also a repo v1.0 gap`. The task-creation fixture fails first because the TCK uses `SendMessage`.
- `tests/mandatory/protocol/test_tasks_get_method.py::test_tasks_get_with_history_length`: `TCK issue; also a repo v1.0 gap`. Same fixture failure via `SendMessage`.
- `tests/mandatory/protocol/test_tasks_get_method.py::test_tasks_get_nonexistent`: `TCK issue; also a repo v1.0 gap`. The TCK calls JSON-RPC `GetTask`; under the v0.3.0 baseline the method is `tasks/get`. With the correct method, the runtime returns `Task not found` / `-32001`.
- `tests/mandatory/protocol/test_tasks_list_method.py::TestBasicListing::test_list_all_tasks`: `TCK issue; also a repo v1.0 gap`. The test suite uses JSON-RPC `ListTasks`, which is outside the `a2a-sdk==0.3.25` JSON-RPC surface and outside the v0.3.0 JSON-RPC mapping.
- `tests/mandatory/protocol/test_tasks_list_method.py::TestBasicListing::test_list_tasks_empty_when_none_exist`: `TCK issue; also a repo v1.0 gap`. Same JSON-RPC `ListTasks` mismatch.
- `tests/mandatory/protocol/test_tasks_list_method.py::TestBasicListing::test_list_tasks_validates_required_fields`: `TCK issue; also a repo v1.0 gap`. Same JSON-RPC `ListTasks` mismatch.
- `tests/mandatory/protocol/test_tasks_list_method.py::TestBasicListing::test_list_tasks_sorted_by_timestamp_descending`: `TCK issue; also a repo v1.0 gap`. Same JSON-RPC `ListTasks` mismatch.
- `tests/mandatory/protocol/test_tasks_list_method.py::TestFiltering::test_filter_by_context_id`: `TCK issue; also a repo v1.0 gap`. Same JSON-RPC `ListTasks` mismatch.
- `tests/mandatory/protocol/test_tasks_list_method.py::TestFiltering::test_filter_by_status`: `TCK issue; also a repo v1.0 gap`. Same JSON-RPC `ListTasks` mismatch.
- `tests/mandatory/protocol/test_tasks_list_method.py::TestFiltering::test_filter_by_last_updated_after`: `TCK issue; also a repo v1.0 gap`. Same JSON-RPC `ListTasks` mismatch.
- `tests/mandatory/protocol/test_tasks_list_method.py::TestFiltering::test_combined_filters`: `TCK issue; also a repo v1.0 gap`. Same JSON-RPC `ListTasks` mismatch.
- `tests/mandatory/protocol/test_tasks_list_method.py::TestPagination::test_default_page_size`: `TCK issue; also a repo v1.0 gap`. Same JSON-RPC `ListTasks` mismatch.
- `tests/mandatory/protocol/test_tasks_list_method.py::TestPagination::test_custom_page_size`: `TCK issue; also a repo v1.0 gap`. Same JSON-RPC `ListTasks` mismatch.
- `tests/mandatory/protocol/test_tasks_list_method.py::TestPagination::test_page_token_navigation`: `TCK issue; also a repo v1.0 gap`. Same JSON-RPC `ListTasks` mismatch.
- `tests/mandatory/protocol/test_tasks_list_method.py::TestPagination::test_last_page_detection`: `TCK issue; also a repo v1.0 gap`. Same JSON-RPC `ListTasks` mismatch.
- `tests/mandatory/protocol/test_tasks_list_method.py::TestPagination::test_total_size_accuracy`: `TCK issue; also a repo v1.0 gap`. Same JSON-RPC `ListTasks` mismatch.
- `tests/mandatory/protocol/test_tasks_list_method.py::TestHistoryLimiting::test_history_length_zero`: `TCK issue; also a repo v1.0 gap`. Same JSON-RPC `ListTasks` mismatch.
- `tests/mandatory/protocol/test_tasks_list_method.py::TestHistoryLimiting::test_history_length_custom`: `TCK issue; also a repo v1.0 gap`. Same JSON-RPC `ListTasks` mismatch.
- `tests/mandatory/protocol/test_tasks_list_method.py::TestHistoryLimiting::test_history_length_exceeds_actual`: `TCK issue; also a repo v1.0 gap`. Same JSON-RPC `ListTasks` mismatch.
- `tests/mandatory/protocol/test_tasks_list_method.py::TestArtifactInclusion::test_artifacts_excluded_by_default`: `TCK issue; also a repo v1.0 gap`. Same JSON-RPC `ListTasks` mismatch.
- `tests/mandatory/protocol/test_tasks_list_method.py::TestArtifactInclusion::test_artifacts_included_when_requested`: `TCK issue; also a repo v1.0 gap`. Same JSON-RPC `ListTasks` mismatch.
- `tests/mandatory/protocol/test_tasks_list_method.py::TestEdgeCasesAndErrors::test_invalid_page_token_error`: `TCK issue; also a repo v1.0 gap`. The assertion expects JSON-RPC param validation on `ListTasks`, but the direct failure is still that `ListTasks` is not a supported JSON-RPC method in the current SDK baseline.
- `tests/mandatory/protocol/test_tasks_list_method.py::TestEdgeCasesAndErrors::test_invalid_status_error`: `TCK issue; also a repo v1.0 gap`. Same JSON-RPC `ListTasks` mismatch.
- `tests/mandatory/protocol/test_tasks_list_method.py::TestEdgeCasesAndErrors::test_negative_page_size_error`: `TCK issue; also a repo v1.0 gap`. Same JSON-RPC `ListTasks` mismatch.
- `tests/mandatory/protocol/test_tasks_list_method.py::TestEdgeCasesAndErrors::test_zero_page_size_error`: `TCK issue; also a repo v1.0 gap`. Same JSON-RPC `ListTasks` mismatch.
- `tests/mandatory/protocol/test_tasks_list_method.py::TestEdgeCasesAndErrors::test_out_of_range_page_size_error`: `TCK issue; also a repo v1.0 gap`. Same JSON-RPC `ListTasks` mismatch.
- `tests/mandatory/protocol/test_tasks_list_method.py::TestEdgeCasesAndErrors::test_default_page_size_is_50`: `TCK issue; also a repo v1.0 gap`. Same JSON-RPC `ListTasks` mismatch.
- `tests/mandatory/protocol/test_tasks_list_method.py::TestEdgeCasesAndErrors::test_negative_history_length_error`: `TCK issue; also a repo v1.0 gap`. Same JSON-RPC `ListTasks` mismatch.
- `tests/mandatory/protocol/test_tasks_list_method.py::TestEdgeCasesAndErrors::test_invalid_timestamp_error`: `TCK issue; also a repo v1.0 gap`. Same JSON-RPC `ListTasks` mismatch.
- `tests/mandatory/security/test_agent_card_security.py::test_public_agent_card_access_control`: `TCK issue`. The TCK requires `supportedInterfaces`, but `a2a-sdk==0.3.25` and the v0.3.0 specification use `additionalInterfaces`.
- `tests/mandatory/security/test_agent_card_security.py::test_sensitive_information_protection`: `TCK issue / local experiment artifact`. The failure is driven by heuristic keyword scanning (`token`, `private`, `127.0.0.1`, non-standard port) against a local dummy-backed run. That is not a reliable indicator of protocol non-compliance.
- `tests/mandatory/security/test_agent_card_security.py::test_security_scheme_consistency`: `TCK issue`. Same schema mismatch as the earlier authentication tests: the TCK expects wrapped security scheme objects instead of the installed SDK shape.
- `tests/mandatory/transport/test_multi_transport_equivalence.py::test_message_sending_equivalence`: `TCK issue; also a repo v1.0 gap`. The transport client uses JSON-RPC `SendMessage`; under the v0.3.0 baseline the method is `message/send`, but stronger `1.0` compatibility would still require additional alias handling.
- `tests/mandatory/transport/test_multi_transport_equivalence.py::test_concurrent_operation_equivalence`: `TCK issue; also a repo v1.0 gap`. Same direct cause as the previous test: the JSON-RPC client sends `SendMessage`.

## Adjacent Repository Gaps Found During Triage

These did not directly cause the exact failed node IDs above, but they are real repository-side gaps revealed during follow-up probes:

- `A2A-Version: 1.0` still returns `-32601` for JSON-RPC `SendMessage` and `GetExtendedAgentCard`. That means current `1.0` support is still limited to negotiation and error-shaping rather than full method-surface compatibility.
- `GET /v1/tasks` currently returns `500 NotImplementedError` in a local probe, even though the route exists and repository docs describe the SDK-owned REST surface as including task listing. That behavior should be treated as a repository issue independent from the TCK's incorrect JSON-RPC `ListTasks` expectation.

## Summary

For the exact 47 failed/error cases in the first mandatory run:

- No failure is a clean `a2a-sdk==0.3.25` / v0.3.0 conformance bug in the current runtime.
- Most failures come from TCK method/schema assumptions that do not match the shipped SDK baseline.
- Several failures also highlight future repository work if stronger `1.0` compatibility becomes a goal.

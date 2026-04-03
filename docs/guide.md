# Usage Guide

This guide covers configuration, authentication, API behavior, streaming re-subscription, and A2A client examples. It is the canonical document for implementation-level protocol contracts and JSON-RPC extension details; README stays at overview level.

## Transport Contracts

- The service supports both transports:
  - HTTP+JSON (REST endpoints such as `/v1/message:send`)
  - JSON-RPC (`POST /`)
- Agent Card keeps `preferredTransport=HTTP+JSON` and also exposes JSON-RPC in `additional_interfaces`.
- The public Agent Card is intentionally slimmed to the minimum discovery surface; per-extension disclosure policy is defined in [`extension-specifications.md`](./extension-specifications.md).
- Detailed provider-private contracts are served through the authenticated extended card endpoint `/agent/authenticatedExtendedCard`.
- Agent Card responses emit weak `ETag` and `Cache-Control`; clients should revalidate cached cards instead of repeatedly fetching full payloads.
- Global HTTP gzip compression is enabled for eligible non-streaming HTTP responses larger than `A2A_HTTP_GZIP_MINIMUM_SIZE` bytes when clients send `Accept-Encoding: gzip`; the default threshold is `8192`, so the main benefit currently lands on larger responses such as the authenticated extended card.
- The current A2A prose specification may refer to `AgentCard.capabilities.extendedAgentCard`, but the official JSON schema and SDK types use the top-level `supportsAuthenticatedExtendedCard` field. This service follows the shipped schema/SDK surface.
- Payload schema is transport-specific and should not be mixed:
  - REST send payload usually uses `message.content` and role values like `ROLE_USER`
  - JSON-RPC `message/send` payload uses `params.message.parts` and role values `user` / `agent`

## Runtime Environment Variables

This section keeps only the protocol-relevant variables. For the full runtime variable catalog and defaults, see [`../src/opencode_a2a/config.py`](../src/opencode_a2a/config.py). Deployment supervision is intentionally out of scope for this project; use your own process manager, container runtime, or host orchestration.

Key variables to understand protocol behavior:

- `A2A_BEARER_TOKEN`: required for all authenticated runtime requests.
- `OPENCODE_BASE_URL`: upstream OpenCode HTTP endpoint. Default: `http://127.0.0.1:4096`. In two-process deployments, set it explicitly.
- `OPENCODE_WORKSPACE_ROOT`: service-level default workspace root exposed to OpenCode when clients do not request a narrower directory override.
- `A2A_ALLOW_DIRECTORY_OVERRIDE`: controls whether clients may pass `metadata.opencode.directory`.
- `A2A_ENABLE_SESSION_SHELL`: gates high-risk JSON-RPC method `opencode.sessions.shell`.
- `A2A_SANDBOX_MODE` / `A2A_SANDBOX_FILESYSTEM_SCOPE` / `A2A_SANDBOX_WRITABLE_ROOTS`: declarative execution-boundary metadata for sandbox mode, filesystem scope, and optional writable roots.
- `A2A_NETWORK_ACCESS` / `A2A_NETWORK_ALLOWED_DOMAINS`: declarative execution-boundary metadata for network policy and optional allowlist disclosure.
- `A2A_APPROVAL_POLICY` / `A2A_APPROVAL_ESCALATION_BEHAVIOR`: declarative execution-boundary metadata for approval workflow.
- `A2A_WRITE_ACCESS_SCOPE` / `A2A_WRITE_ACCESS_OUTSIDE_WORKSPACE`: declarative execution-boundary metadata for write scope and whether writes may extend outside the primary workspace boundary.
- `A2A_HOST` / `A2A_PORT`: runtime bind address. Defaults: `127.0.0.1:8000`.
- `A2A_PUBLIC_URL`: public base URL advertised by the Agent Card. Default: `http://127.0.0.1:8000`.
- `A2A_LOG_LEVEL`: runtime log level. Default: `WARNING`.
- `A2A_LOG_PAYLOADS` / `A2A_LOG_BODY_LIMIT`: payload logging behavior and truncation. When `A2A_LOG_LEVEL=DEBUG`, upstream OpenCode stream events are also logged with preview truncation controlled by `A2A_LOG_BODY_LIMIT`.
- `A2A_HTTP_GZIP_MINIMUM_SIZE`: minimum eligible response-body size in bytes for global non-streaming HTTP gzip compression. Default: `8192`.
- `A2A_MAX_REQUEST_BODY_BYTES`: runtime request-body limit. Oversized requests return HTTP `413`.
- `A2A_PENDING_SESSION_CLAIM_TTL_SECONDS`: lease duration for pending preferred session claims before they expire and stop blocking other identities.
- `A2A_INTERRUPT_REQUEST_TTL_SECONDS`: active retention window for the interrupt request binding registry used by `a2a.interrupt.*` callback methods. Default: `10800` seconds (`180` minutes).
- `A2A_INTERRUPT_REQUEST_TOMBSTONE_TTL_SECONDS`: retention window for expired interrupt tombstones after active TTL has elapsed. During this window, repeated replies keep returning `INTERRUPT_REQUEST_EXPIRED` instead of falling through to `INTERRUPT_REQUEST_NOT_FOUND`. Default: `600` seconds (`10` minutes).
- `A2A_CANCEL_ABORT_TIMEOUT_SECONDS`: best-effort timeout for upstream `session.abort` in cancel flow.
- `OPENCODE_TIMEOUT` / `OPENCODE_TIMEOUT_STREAM`: upstream request timeout and optional stream timeout override.
- `OPENCODE_MAX_CONCURRENT_REQUESTS`: optional fast-fail concurrency limit for unary/control upstream calls. `0` disables the limit.
- `OPENCODE_MAX_CONCURRENT_STREAMS`: optional fast-fail concurrency limit for long-lived upstream `/event` streams. `0` disables the limit.
- `A2A_CLIENT_TIMEOUT_SECONDS`: outbound client timeout. Default: `30` seconds.
- `A2A_CLIENT_CARD_FETCH_TIMEOUT_SECONDS`: outbound Agent Card fetch timeout. Default: `5` seconds.
- `A2A_CLIENT_USE_CLIENT_PREFERENCE`: whether the outbound client prefers its own transport choices.
- `A2A_CLIENT_BEARER_TOKEN`: optional bearer token attached to outbound peer calls made by the embedded A2A client and `a2a_call` tool path.
- `A2A_CLIENT_BASIC_AUTH`: optional Basic auth credential attached to outbound peer calls made by the embedded A2A client and `a2a_call` tool path.
- `A2A_CLIENT_SUPPORTED_TRANSPORTS`: ordered outbound transport preference list.
- `A2A_TASK_STORE_BACKEND`: unified lightweight persistence backend for SDK task rows plus adapter-managed session / interrupt state. Supported values: `database`, `memory`. Default: `database`.
- `A2A_TASK_STORE_DATABASE_URL`: database URL used by the unified durable backend when `A2A_TASK_STORE_BACKEND=database`. Default: `sqlite+aiosqlite:///./opencode-a2a.db`.
- Runtime authentication is bearer-token only via `A2A_BEARER_TOKEN`.
- Runtime authentication also applies to `/health`; the public unauthenticated discovery surface remains `/.well-known/agent-card.json` and `/.well-known/agent.json`.
- The authenticated extended card endpoint `/agent/authenticatedExtendedCard` is bearer-token protected.
- The same outbound client flags are also honored by the server-side embedded A2A client used for peer calls and `a2a_call` tool execution:
  - `A2A_CLIENT_TIMEOUT_SECONDS`
  - `A2A_CLIENT_CARD_FETCH_TIMEOUT_SECONDS`
  - `A2A_CLIENT_USE_CLIENT_PREFERENCE`
  - `A2A_CLIENT_BEARER_TOKEN`
  - `A2A_CLIENT_BASIC_AUTH`
  - `A2A_CLIENT_SUPPORTED_TRANSPORTS`

## Client Initialization Facade (Preview)

`opencode-a2a` now includes a minimal client bootstrap module in `src/opencode_a2a/client/` to support downstream consumer usage while keeping server and client concerns separate.

Boundary separation:

- Server code owns runtime request handling, transport orchestration, stream behavior, and public compatibility profile exposure.
- Client code owns peer card discovery, SDK client construction, operation call helpers, and protocol error normalization.

Current client facade API:

- `A2AClient.get_agent_card()`
- `A2AClient.send()` / `A2AClient.send_message()`
- `A2AClient.get_task()`
- `A2AClient.cancel_task()`
- `A2AClient.resubscribe_task()`

Server-side outbound peer calls read outbound credentials from environment variables. Configure `A2A_CLIENT_BEARER_TOKEN` or `A2A_CLIENT_BASIC_AUTH` when the remote agent protects its runtime surface. CLI outbound calls follow the same environment-only model.

`A2AClient.send()` returns the latest response event and keeps the default stream-first behavior. If a peer returns a non-terminal task snapshot and expects follow-up `tasks/get` polling, enable the optional facade fallback with:

- `A2A_CLIENT_POLLING_FALLBACK_ENABLED=true`
- `A2A_CLIENT_POLLING_FALLBACK_INITIAL_INTERVAL_SECONDS`
- `A2A_CLIENT_POLLING_FALLBACK_MAX_INTERVAL_SECONDS`
- `A2A_CLIENT_POLLING_FALLBACK_BACKOFF_MULTIPLIER`
- `A2A_CLIENT_POLLING_FALLBACK_TIMEOUT_SECONDS`

The fallback only applies to `send()`, keeps `send_message()` as a thin event stream wrapper, and stops polling once the task reaches a terminal state or a caller-intervention state such as `input-required` or `auth-required`.

Execution-boundary metadata is intentionally declarative deployment metadata: it is published through `RuntimeProfile`, Agent Card, OpenAPI, and `/health`, and should not be interpreted as a live per-request privilege snapshot or a runtime CLI self-inspection result.

Recommended two-process example:

```bash
opencode serve --hostname 127.0.0.1 --port 4096
```

Configure provider auth and the default model on the OpenCode side before starting that upstream process:

- Add credentials with `opencode auth login` or `/connect`.
- Check available model IDs with `opencode models` or `opencode models <provider>`.
- Set the default model in `opencode.json`, for example:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "model": "google/gemini-3-pro"
}
```

If your provider uses environment variables for auth, export them before starting `opencode serve`.

Do not assume startup-script env vars always erase previously persisted OpenCode auth state for the deployed user. When debugging provider-auth surprises, inspect the deployed user's HOME/XDG config directories and the OpenCode files stored there before concluding that `opencode-a2a` changed the credential selection.

Then start `opencode-a2a` against that explicit upstream URL:

```bash
OPENCODE_BASE_URL=http://127.0.0.1:4096 \
A2A_BEARER_TOKEN=dev-token \
A2A_HOST=127.0.0.1 \
A2A_PORT=8000 \
A2A_PUBLIC_URL=http://127.0.0.1:8000 \
OPENCODE_WORKSPACE_ROOT=/abs/path/to/workspace \
opencode-a2a
```

By default, the service uses a SQLite-backed durable state store:

```bash
OPENCODE_BASE_URL=http://127.0.0.1:4096 \
A2A_BEARER_TOKEN=dev-token \
A2A_TASK_STORE_DATABASE_URL=sqlite+aiosqlite:///./opencode-a2a.db \
opencode-a2a
```

With the default `database` backend, the unified lightweight persistence layer persists:

- task records
- session binding / ownership state
- pending preferred-session claims
- interrupt request bindings and tombstones

This project is SQLite-first for local single-instance deployments. The runtime configures local durability-oriented SQLite connection settings (`WAL`, `busy_timeout`, `synchronous=NORMAL`) and creates missing parent directories for file-backed database paths.

The runtime automatically applies lightweight schema migrations for its custom state tables and records the applied version in `a2a_schema_version`. Schema-version writes are idempotent across concurrent first-start races, pending preferred-session claims now persist absolute `expires_at` timestamps while remaining backward-compatible with legacy `updated_at` rows, and the built-in path currently targets the local SQLite deployment profile without requiring Alembic.

Database-backed task persistence also keeps the existing first-terminal-state-wins contract while tightening the SQLite path with an atomic terminal-write guard instead of relying only on process-local read-before-write checks. Any wider SQLAlchemy dialect compatibility should be treated as incidental implementation latitude rather than a documented deployment target.

At startup, the runtime logs a concise persistence summary covering the active backend, the redacted database URL when applicable, the shared persistence scope, and whether the SQLite local durability profile is active.

The A2A SDK task table remains managed by the SDK's own `DatabaseTaskStore` initialization path. The internal migration runner only owns the additional `opencode-a2a` state tables listed above, but both layers still share the same configured lightweight persistence backend.

In-flight asyncio locks, outbound A2A client caches, and stream-local aggregation buffers remain process-local runtime state.

To opt into an ephemeral development profile, set:

```bash
A2A_TASK_STORE_BACKEND=memory
```

## Troubleshooting Provider Auth State

If one deployment works while another fails against the same upstream provider, check the deployed OpenCode user's local state before assuming the difference comes from the `opencode-a2a` package itself.

- Provider auth and service-level model defaults belong to `opencode serve`.
- The deployed user's HOME/XDG config directories are operational input.
- Existing OpenCode auth/config files may still influence runtime behavior even when you also inject provider env vars from a process manager or shell wrapper.
- Compare the deployed user's OpenCode auth/config files, HOME/XDG values, and effective workspace directory before blaming the A2A adapter layer.
- For OpenCode-specific auth/config troubleshooting, inspect files such as `~/.local/share/opencode/auth.json` and `~/.config/opencode/opencode.json` (or the equivalent XDG-resolved paths for that service user).

## Core Behavior

- The service forwards A2A `message:send` to OpenCode session/message calls.
- Main chat requests may override the upstream model for one request through `metadata.shared.model`.
- Provider/model catalog discovery is available through `opencode.providers.list` and `opencode.models.list`.
- Main chat requests that explicitly send `configuration.acceptedOutputModes` must stay compatible with the declared chat output modes.
- Current main chat requests must continue accepting `text/plain`; requests that only accept `application/json` or other incompatible modes are rejected before execution starts.
- `application/json` is additive structured-output support for incremental `tool_call` payloads. It does not guarantee that ordinary assistant prose can always be losslessly represented as JSON, so consumers that expect normal chat text should keep accepting `text/plain`.
- Main chat input supports structured A2A `parts` passthrough:
  - `TextPart` is forwarded as an OpenCode text part.
  - `FilePart(FileWithBytes)` is forwarded as a `file` part with a `data:` URL.
  - `FilePart(FileWithUri)` is forwarded as a `file` part with the original URI.
  - `DataPart` is currently rejected explicitly; it is not silently downgraded.
- Task state defaults to `completed` for successful turns.
- The deployment profile is single-tenant and shared-workspace. For detailed isolation principles and security boundaries, see [SECURITY.md](../SECURITY.md).

## Streaming Contract

- Streaming is always enabled in this server profile; `message:stream` is part of the stable runtime baseline.
- Streaming (`/v1/message:stream`) emits incremental `TaskArtifactUpdateEvent` and then `TaskStatusUpdateEvent(final=true)`.
- Stream artifacts carry `artifact.metadata.shared.stream.block_type` with values `text` / `reasoning` / `tool_call`.
- All chunks share one stream artifact ID and preserve original timeline via `artifact.metadata.shared.stream.event_id`.
- `artifact.metadata.shared.stream.message_id` remains best-effort metadata: when upstream omits `message_id`, the service falls back to a stable request-scoped message identity.
- `artifact.metadata.shared.stream.sequence` carries the canonical per-request stream sequence.
- A final snapshot is emitted only when streaming chunks did not already produce the same final text.
- Stream routing is schema-first: the service classifies chunks primarily by OpenCode `part.type` and `part_id` state rather than inline text markers.
- `message.part.delta` and `message.part.updated` are merged per `part_id`; out-of-order deltas are buffered and replayed when the corresponding `part.updated` arrives.
- Structured `tool` parts are emitted as `tool_call` blocks backed by `DataPart(data={...})`, while `text` and `reasoning` continue to use `TextPart`.
- `tool_call` block payloads are normalized structured objects that may expose fields such as `call_id`, `tool`, `status`, `title`, `subtitle`, `input`, `output`, and `error`.
- Final status event metadata may include normalized token usage at `metadata.shared.usage` with fields such as `input_tokens`, `output_tokens`, `total_tokens`, optional `reasoning_tokens`, optional `cache_tokens.read_tokens` / `cache_tokens.write_tokens`, and optional `cost`.
- Usage is extracted from documented info payloads and supported usage parts such as `step-finish`; non-usage parts with similar fields are ignored.
- Interrupt events (`permission.asked` / `question.asked`) are mapped to `TaskStatusUpdateEvent(final=false, state=input-required)` with details at `metadata.shared.interrupt`, including `request_id`, interrupt `type`, `phase=asked`, and a normalized minimal callback payload.
- Resolved interrupt events (`permission.replied` / `question.replied` / `question.rejected`) are emitted as `TaskStatusUpdateEvent(final=false, state=working)` with `metadata.shared.interrupt.phase=resolved` and a normalized `metadata.shared.interrupt.resolution`.
- Duplicate or unknown resolved events are suppressed unless the matching request is still pending.
- Non-streaming requests return a `Task` directly.
- Non-streaming `message:send` responses may include normalized token usage at `Task.metadata.shared.usage` with the same field schema.

## Auth, Limits, and Failure Contract

- Requests require `Authorization: Bearer <token>`; otherwise `401` is returned. Agent Card endpoints are public.
- Requests above `A2A_MAX_REQUEST_BODY_BYTES` are rejected with HTTP `413` before transport handling.
- For validation failures, missing context (`task_id` / `context_id`), or internal errors, the service attempts to return standard A2A failure events via `event_queue`.
- Failure events include concrete error details with `failed` state.

## Directory Rules

- Clients can pass `metadata.opencode.directory`, but it must stay inside `${OPENCODE_WORKSPACE_ROOT}` or the service runtime root when no workspace root is configured.
- `OPENCODE_WORKSPACE_ROOT` is the service-level default workspace root used when clients do not request a narrower directory override.
- All paths are normalized with `realpath` to prevent `..` or symlink boundary bypass.
- If `A2A_ALLOW_DIRECTORY_OVERRIDE=false`, only the default directory is accepted.

## Wire Contract

The service publishes a machine-readable wire contract through Agent Card and OpenAPI metadata to describe the current runtime method boundary.

Use it to answer:

- which JSON-RPC methods are part of the current A2A core baseline
- which JSON-RPC methods are custom extensions
- which methods are deployment-conditional rather than currently active
- what error shape is returned for unsupported JSON-RPC methods

Current behavior:

- Core JSON-RPC methods are declared under `core.jsonrpc_methods`.
- Core HTTP endpoints are declared under `core.http_endpoints`.
- Extension JSON-RPC methods are declared under `extensions.jsonrpc_methods`.
- Deployment-conditional methods are declared under `extensions.conditionally_available_methods`.
- Shared metadata extension URIs such as session binding and streaming are listed under `extensions.extension_uris`.
- `all_jsonrpc_methods` is the runtime truth for the current deployment.
- The current SDK-owned core JSON-RPC surface includes `agent/getAuthenticatedExtendedCard` and `tasks/pushNotificationConfig/*`.
- The current SDK-owned REST surface also includes `GET /v1/tasks` and the task push notification config routes.

When `A2A_ENABLE_SESSION_SHELL=false`, `opencode.sessions.shell` is omitted from `all_jsonrpc_methods` and exposed only through `extensions.conditionally_available_methods`.

Unsupported method contract:

- JSON-RPC error code: `-32601`
- Error message: `Unsupported method: <method>`
- Error data fields:
  - `type=METHOD_NOT_SUPPORTED`
  - `method`
  - `supported_methods`
  - `protocol_version`

Consumer guidance:

- Discover custom JSON-RPC methods from Agent Card / OpenAPI before calling them.
- Treat `supported_methods` in `error.data` as the runtime truth for the current deployment, especially when a deployment-conditional method is disabled.

## Protocol Version Negotiation

- The runtime accepts `A2A-Version` from either the HTTP header or the query parameter of A2A transport requests.
- If both are omitted, the runtime falls back to the configured default protocol version.
- Current defaults declare `default_protocol_version=0.3` and `supported_protocol_versions=["0.3", "1.0"]`.
- Unsupported or invalid versions are rejected before request routing:
  - JSON-RPC returns a unified `VERSION_NOT_SUPPORTED` error envelope.
  - REST returns HTTP `400` with the same contract fields.
- Error shaping now follows the negotiated major line:
  - `0.3` keeps the existing legacy `error.data={...}` and flat REST error payloads.
  - `1.0` keeps standard JSON-RPC error codes for standard failures, but moves A2A-specific JSON-RPC errors to `google.rpc.ErrorInfo`-style `error.data[]` details and REST errors to AIP-193 `error.details[]`.
- The current transport payloads still follow the SDK-owned request/response shapes; version negotiation is introduced first so later issues can evolve error and payload compatibility without scattering version checks across handlers.

Current compatibility matrix:

| Area | `0.3` | `1.0` | Current note |
| --- | --- | --- | --- |
| Version negotiation | Supported | Supported | The runtime accepts `A2A-Version` and routes requests before handler dispatch. |
| Agent Card / interface version discovery | Default card protocol only | Partial | The service publishes `default_protocol_version` and `supported_protocol_versions`, but `AgentInterface.protocolVersion` cannot yet be declared with `a2a-sdk==0.3.25`. |
| Transport payloads and enums | Supported | Partial | Request/response payloads, enums, and schema details still follow the SDK-owned `0.3` baseline. |
| Error model | Supported | Partial | `0.3` keeps legacy `error.data={...}` / flat REST payloads; `1.0` uses protocol-aware JSON-RPC details and AIP-193-style REST errors. |
| Pagination and list semantics | Supported | Partial | Cursor/list behavior is stable, but the declared shape still follows the `0.3` SDK baseline. |
| Push notification surfaces | Supported | Partial | Core task push-notification routes are available, but no extra `1.0`-specific compatibility layer is declared yet. |
| Signatures and authenticated data | Supported | Partial | Security schemes and authenticated extended card discovery follow the shipped SDK schema rather than a dedicated `1.0` compatibility layer. |

## Compatibility Profile

The service also publishes a machine-readable compatibility profile through Agent Card and OpenAPI metadata.

Its purpose is to declare:

- the stable A2A core interoperability baseline
- which custom JSON-RPC methods are deployment extensions
- which extension surfaces are required runtime metadata contracts
- which methods are deployment-conditional rather than always available

Current profile shape:

- `profile_id=opencode-a2a-single-tenant-coding-v1`
- `default_protocol_version`
- `supported_protocol_versions`
- `protocol_compatibility`
  - `versions["0.3"].status=supported`
  - `versions["1.0"].status=partial`
  - `versions[*].supported_features[]`
  - `versions[*].known_gaps[]`
- Deployment semantics are declared under `deployment`:
  - `id=single_tenant_shared_workspace`
  - `single_tenant=true`
  - `shared_workspace_across_consumers=true`
  - `tenant_isolation=none`
- Runtime features are declared under `runtime_features`:
  - `directory_binding.allow_override=true|false`
  - `directory_binding.scope=workspace_root_or_descendant|workspace_root_only`
  - `session_shell.enabled=true|false`
  - `session_shell.availability=enabled|disabled`
  - `execution_environment.sandbox.mode=unknown|read-only|workspace-write|danger-full-access|custom`
  - `execution_environment.sandbox.filesystem_scope=unknown|workspace_only|workspace_and_declared_roots|unrestricted|custom`
  - `execution_environment.network.access=unknown|disabled|enabled|restricted|custom`
  - `execution_environment.approval.policy=unknown|never|on-request|on-failure|untrusted|custom`
  - `execution_environment.approval.escalation_behavior=unknown|manual|automatic|unsupported|custom`
  - `execution_environment.write_access.scope=unknown|none|workspace_only|workspace_and_declared_roots|unrestricted|custom`
  - `execution_environment.write_access.outside_workspace=unknown|allowed|disallowed|custom`
  - `service_features.streaming.enabled=true`
  - `service_features.health_endpoint.enabled=true`
- Optional disclosure fields are emitted only when explicitly configured:
  - `execution_environment.sandbox.writable_roots`
  - `execution_environment.network.allowed_domains`
- Core methods and endpoints are declared under `core`.
- Extension retention policy is declared under `extension_retention`.
- Per-method retention and availability are declared under `method_retention`.
- Extension params and `/health` expose the same structured `profile` object; there is no separate legacy deployment-context shape.
- Execution-environment values are deployment declarations, not a per-turn runtime approval or sandbox result.

Retention guidance:

- Treat core A2A methods as the generic client interoperability baseline.
- Treat session binding, request-scoped model selection, and streaming metadata contracts as required for the current deployment model.
- Treat `a2a.interrupt.*` methods as shared extensions.
- Treat `opencode.sessions.*`, `opencode.providers.*`, and `opencode.models.*` as provider-private OpenCode extensions rather than portable A2A baseline capabilities.
- Treat `opencode.sessions.shell` as deployment-conditional and discover it from the declared profile and current wire contract before calling it.
- Treat `protocol_compatibility` as the runtime truth for which protocol line is fully supported versus only partially adapted.

Extension boundary principles:

- Expose OpenCode-specific capabilities through A2A only when they fit the adapter boundary: the adapter may document, validate, route, and normalize stable upstream-facing behavior, but it should not become a general replacement for upstream private runtime internals or host-level control planes.
- Default new `opencode.*` methods to provider-private extension status. Do not present them as portable A2A baseline capabilities unless they truly align with shared protocol semantics.
- Prefer read-only discovery, stable compatibility surfaces, and low-risk control methods before introducing stronger mutating or destructive operations.
- Map results to A2A core objects only when the upstream payload is a stable, low-ambiguity read projection such as session-to-`Task` or message-to-`Message`. Otherwise prefer provider-private summary/result envelopes.
- Treat upstream internal execution mechanisms, including subtask/subagent fan-out and task-tool internals, as provider-private runtime behavior. The adapter may expose passthrough compatibility and observable output metadata, but should not promote those internals into a first-class A2A orchestration API by default.
- For any new extension proposal, require an explicit answer to all of the following before implementation:
  - What client value is added beyond the existing chat/session flow?
  - Is the upstream behavior stable enough to document as a maintained contract?
  - Should the surface remain provider-private, deployment-conditional, or not be exposed at all?
  - Are authorization, workspace/session ownership, and destructive-side-effect boundaries clear enough to enforce?
  - Can the result shape be expressed without overfitting OpenCode internals into fake A2A core semantics?

## Multipart Input Example

Minimal JSON-RPC example with text + file input:

```bash
curl -sS http://127.0.0.1:8000/ \
  -H 'content-type: application/json' \
  -H 'Authorization: Bearer <your-token>' \
  -d '{
    "jsonrpc": "2.0",
    "id": "req-1",
    "method": "message/send",
    "params": {
      "message": {
        "messageId": "msg-multipart-1",
        "role": "user",
        "parts": [
          {
            "kind": "text",
            "text": "Please summarize this file."
          },
          {
            "kind": "file",
            "file": {
              "name": "report.pdf",
              "mimeType": "application/pdf",
              "uri": "file:///workspace/report.pdf"
            }
          }
        ]
      }
    }
  }'
```

Current compatibility note:

- `TextPart` and `FilePart` are supported.
- `DataPart` input is not supported and is rejected with an explicit error.

## Extension Capability Overview

The README provides product positioning and quick start guidance. This guide focuses on how to consume the declared capabilities.

Important distinction:

- Agent Card extension declarations answer "what capability is available?"
- Runtime payload metadata answers "what happened on this request/stream?"
- Clients should not treat runtime metadata alone as a substitute for capability discovery when an extension URI is already declared.
- Treat the extension URI as the stable specification identifier.
- [`extension-specifications.md`](./extension-specifications.md) owns the stable URI catalog plus public-vs-extended disclosure policy.
- This guide owns runtime usage, request/response semantics, and client-facing examples.
- The authenticated extended card is the detailed deployment-specific contract view.

## Shared Session Binding Contract

Stable specification URI:

- `https://github.com/Intelligent-Internet/opencode-a2a/blob/main/docs/extension-specifications.md#shared-session-binding-v1`

This section focuses on how clients should use the binding at runtime. For the stable URI record and public-vs-extended disclosure policy, see [`extension-specifications.md`](./extension-specifications.md).

To continue a historical OpenCode session, include this metadata key in each invoke request:

- `metadata.shared.session.id`: target upstream session ID

Server behavior:

- If provided, the request is sent to that exact OpenCode session.
- If omitted, a new session is created and cached by `(identity, contextId) -> session_id`.
- `contextId` remains the A2A conversation context key for task continuity; it is not a replacement for the upstream session identifier.
- OpenCode-private context such as `metadata.opencode.directory` may be supplied alongside `metadata.shared.session.id`, but it does not change the shared session-binding key.

Consumer guidance:

- Use this extension declaration to decide whether the server explicitly supports shared session rebinding.
- On the request path, write the upstream session identity to `metadata.shared.session.id`.
- On the response/query path, treat `metadata.shared.session` as runtime metadata and not as a separate capability declaration.

Minimal example:

```bash
curl -sS http://127.0.0.1:8000/v1/message:send \
  -H 'content-type: application/json' \
  -H 'Authorization: Bearer <your-token>' \
  -d '{
    "message": {
      "messageId": "msg-continue-1",
      "role": "ROLE_USER",
      "content": [{"text": "Continue the previous session and restate the key conclusion."}]
    },
    "metadata": {
      "shared": {
        "session": {
          "id": "<session_id>"
        }
      }
    }
  }'
```

## Shared Model Selection Contract

Stable specification URI:

- `https://github.com/Intelligent-Internet/opencode-a2a/blob/main/docs/extension-specifications.md#shared-model-selection-v1`

This section focuses on request-scoped usage. For the stable URI record and public-vs-extended disclosure policy, see [`extension-specifications.md`](./extension-specifications.md).

This extension declares that the main chat path accepts a request-scoped model override through shared metadata:

- `metadata.shared.model.providerID`
- `metadata.shared.model.modelID`

Runtime payload:

- The actual request carries the override under `metadata.shared.model`.

Behavior:

- The override is optional and scoped to one main chat request.
- Both `providerID` and `modelID` must be present together.
- When both fields are present, the service forwards them to the upstream OpenCode request as a model preference.
- When the fields are absent, the upstream OpenCode default behavior applies.

Consumer guidance:

- Use Agent Card discovery to confirm the shared model-selection contract is available before sending overrides.
- Treat `metadata.shared.model` as request-scoped preference data rather than deployment configuration.
- Provider auth and service-level model defaults belong to `opencode serve`, not to `opencode-a2a`.

Minimal example:

```bash
curl -sS http://127.0.0.1:8000/v1/message:send \
  -H 'content-type: application/json' \
  -H 'Authorization: Bearer <your-token>' \
  -d '{
    "message": {
      "messageId": "msg-model-1",
      "role": "ROLE_USER",
      "content": [{"text": "Explain the current branch status."}]
    },
    "metadata": {
      "shared": {
        "model": {
          "providerID": "google",
          "modelID": "gemini-2.5-flash"
        }
      }
    }
  }'
```

## Shared Stream Hints Contract

Stable specification URI:

- `https://github.com/Intelligent-Internet/opencode-a2a/blob/main/docs/extension-specifications.md#shared-stream-hints-v1`

This section focuses on how clients should interpret runtime metadata. For the stable URI record and public-vs-extended disclosure policy, see [`extension-specifications.md`](./extension-specifications.md).

This extension declares that streaming and final task payloads use canonical shared metadata for block, usage, interrupt, and session hints.

Runtime payload:

- Request/stream payloads carry the hints under shared metadata fields.

Shared runtime fields:

- `metadata.shared.stream`
  - block-level stream metadata such as `block_type`, `source`, `message_id`, `event_id`, `sequence`, and `role`
- `metadata.shared.usage`
  - normalized usage data such as `input_tokens`, `output_tokens`, `total_tokens`, optional `reasoning_tokens`, optional `cache_tokens.read_tokens` / `cache_tokens.write_tokens`, and optional `cost`
- `metadata.shared.interrupt`
  - normalized interrupt request or resolution metadata including `request_id`, `type`, `phase`, optional `resolution`, and callback-safe details
- `metadata.shared.session`
  - session-level metadata such as the bound upstream session ID and session title when available

Consumer guidance:

- Use the extension declaration to know the server emits canonical shared stream hints.
- Use runtime metadata to render block timelines, token usage, and interactive interruptions.
- Do not infer capability support only from seeing one runtime field on one response; rely on Agent Card discovery first when possible.
- Treat `metadata.shared.interrupt` as observation data. Callback operations are a separate shared capability declared by `https://github.com/Intelligent-Internet/opencode-a2a/blob/main/docs/extension-specifications.md#shared-interactive-interrupt-v1`.

Minimal stream semantics summary:

- `text`, `reasoning`, and `tool_call` are emitted as canonical block types
- `text` and `reasoning` blocks use `TextPart`, while `tool_call` uses `DataPart`
- `message_id` and `event_id` preserve stable timeline identity where possible
- `sequence` is the per-request canonical stream sequence
- final task/status metadata may repeat normalized usage and interrupt context even after the streaming phase ends

## OpenCode Session Query A2A Extension

This service exposes OpenCode session lifecycle inspection, list/message-history queries, and low-risk session control methods via A2A JSON-RPC extension methods (default endpoint: `POST /`). No extra custom REST endpoint is introduced.

- Trigger: call extension methods through A2A JSON-RPC
- Auth: same `Authorization: Bearer <token>`
- Privacy guard: when `A2A_LOG_PAYLOADS=true`, request/response bodies are still suppressed for `method=opencode.sessions.*`
- Endpoint discovery: prefer `additional_interfaces[]` with `transport=jsonrpc` from Agent Card
- The runtime still delegates SDK-owned JSON-RPC methods such as `agent/getAuthenticatedExtendedCard` and `tasks/pushNotificationConfig/*` to the base A2A implementation; they are not OpenCode-specific extensions.
- Notification behavior: for `opencode.sessions.*`, requests without `id` return HTTP `204 No Content`
- Result format:
  - `opencode.sessions.status` => provider-private status summaries in `result.items`
  - `opencode.sessions.list` / `opencode.sessions.children` => A2A `Task[]`
  - `opencode.sessions.get` => A2A `Task`
  - `opencode.sessions.todo` / `opencode.sessions.diff` => provider-private summaries in `result.items`
  - `opencode.sessions.messages.list` => A2A `Message[]`
  - `opencode.sessions.messages.get` => A2A `Message`
  - `opencode.sessions.fork` / `opencode.sessions.share` / `opencode.sessions.unshare` => provider-private session summary in `result.item`
  - `opencode.sessions.summarize` => provider-private completion result in `result.ok` plus `result.session_id`
  - `opencode.sessions.revert` / `opencode.sessions.unrevert` => provider-private session summary in `result.item`
  - limit pagination defaults to `20`; requests above `100` are rejected
  - `opencode.sessions.messages.list` also returns `result.next_cursor` when older messages are available
  - `contextId` is an A2A context key derived by the adapter (format: `ctx:opencode-session:<session_id>`, not raw OpenCode session ID)
  - OpenCode session identity is exposed explicitly at `metadata.shared.session.id`
  - session title is available at `metadata.shared.session.title`
- Session list filters:
  - optional `directory`, `roots`, `start`, `search`, `limit`
  - optional `metadata.opencode.workspace.id`
  - `directory` is normalized through the same workspace-boundary rules used by other OpenCode directory overrides before reaching upstream
  - when `metadata.opencode.workspace.id` is present, the adapter routes by workspace and ignores `directory`
- Session message history filters:
  - optional `limit`, `before`
  - optional `metadata.opencode.workspace.id`
  - `before` is an opaque cursor for loading older messages and is only supported on `opencode.sessions.messages.list`
- Mutating lifecycle methods:
  - `opencode.sessions.fork`
  - `opencode.sessions.share`
  - `opencode.sessions.unshare`
  - `opencode.sessions.summarize`
  - `opencode.sessions.revert`
  - `opencode.sessions.unrevert`
  - these methods reuse the same owner guard as other session control methods

### Session Status (`opencode.sessions.status`)

```bash
curl -sS http://127.0.0.1:8000/ \
  -H 'content-type: application/json' \
  -H 'Authorization: Bearer <your-token>' \
  -d '{
    "jsonrpc": "2.0",
    "id": 11,
    "method": "opencode.sessions.status",
    "params": {
      "directory": "services/api"
    }
  }'
```

### Session List (`opencode.sessions.list`)

```bash
curl -sS http://127.0.0.1:8000/ \
  -H 'content-type: application/json' \
  -H 'Authorization: Bearer <your-token>' \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "opencode.sessions.list",
    "params": {
      "directory": "services/api",
      "roots": true,
      "search": "planner",
      "limit": 20
    }
  }'
```

### Session Messages (`opencode.sessions.messages.list`)

```bash
curl -sS http://127.0.0.1:8000/ \
  -H 'content-type: application/json' \
  -H 'Authorization: Bearer <your-token>' \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "opencode.sessions.messages.list",
    "params": {
      "session_id": "<session_id>",
      "before": "<next_cursor_from_previous_page>",
      "limit": 50
    }
  }'
```

Message history responses include:

- `result.items`: normalized A2A `Message[]`
- `result.next_cursor`: opaque cursor for the next older page, or `null` when no older page is available

### Session Get / Children / Todo / Diff / Message Get

- `opencode.sessions.get` => read one session and map it to A2A `Task`
- `opencode.sessions.children` => read child sessions and map them to A2A `Task[]`
- `opencode.sessions.todo` => read provider-private todo summaries
- `opencode.sessions.diff` => read provider-private diff summaries; optional `message_id`
- `opencode.sessions.messages.get` => read one message and map it to A2A `Message`

Example (`opencode.sessions.messages.get`):

```bash
curl -sS http://127.0.0.1:8000/ \
  -H 'content-type: application/json' \
  -H 'Authorization: Bearer <your-token>' \
  -d '{
    "jsonrpc": "2.0",
    "id": 16,
    "method": "opencode.sessions.messages.get",
    "params": {
      "session_id": "<session_id>",
      "message_id": "<message_id>"
    }
  }'
```

### Session Prompt Async (`opencode.sessions.prompt_async`)

Topology note:

- `A2A Task` remains the protocol-level execution object exposed by the adapter.
- `opencode.sessions.prompt_async` is a provider-private extension method, not part of the A2A core baseline.
- `request.parts[].type=subtask` is an upstream-compatible OpenCode input shape carried through that extension method.
- Downstream execution may fan out into upstream OpenCode task-tool / subagent runtime behavior, but that internal orchestration remains provider-private.
- The adapter documents passthrough compatibility and observable `tool_call` output blocks; it does not promote subtask/subagent execution into a first-class A2A orchestration API.

```bash
curl -sS http://127.0.0.1:8000/ \
  -H 'content-type: application/json' \
  -H 'Authorization: Bearer <your-token>' \
  -d '{
    "jsonrpc": "2.0",
    "id": 21,
    "method": "opencode.sessions.prompt_async",
    "params": {
      "session_id": "<session_id>",
      "request": {
        "parts": [{"type": "text", "text": "Continue and summarize next steps."}],
        "noReply": true,
        "model": {
          "providerID": "google",
          "modelID": "gemini-2.5-flash"
        }
      },
      "metadata": {
        "opencode": {
          "directory": "/path/inside/workspace"
        }
      }
    }
  }'
```

Response:

- success => `{"ok": true, "session_id": "<session_id>"}` (JSON-RPC result)
- notification (no `id`) => HTTP `204 No Content`
- error types:
  - `SESSION_NOT_FOUND`
  - `SESSION_FORBIDDEN`
  - `METHOD_DISABLED` (not applicable to prompt_async)
  - `UPSTREAM_UNREACHABLE`
  - `UPSTREAM_HTTP_ERROR`
  - `UPSTREAM_PAYLOAD_ERROR`

Validation notes:

- `metadata.opencode.directory` follows the same normalization and boundary rules as message send (`realpath` + workspace boundary check).
- `metadata.opencode.workspace.id` is a provider-private routing hint. When it is present, the adapter routes the request to that workspace and does not apply directory override resolution for the same call.
- `request.model` uses the same shape as `metadata.shared.model` and is scoped only to the current session-control request.
- `request.parts[]` currently accepts upstream-compatible provider-private part types `text`, `file`, `agent`, and `subtask`.
- `subtask` parts require `prompt`, `description`, and `agent`; they may also include optional `model` and `command`.
- For `subtask` parts, `request.parts[].agent` is the upstream subagent selector. `opencode-a2a` validates and forwards the shape but does not define a separate subagent discovery or orchestration API.
- Control methods enforce session owner guard based on request identity.

Example (`opencode.sessions.prompt_async` with a provider-private `subtask` part):

```bash
curl -sS http://127.0.0.1:8000/ \
  -H 'content-type: application/json' \
  -H 'Authorization: Bearer <your-token>' \
  -d '{
    "jsonrpc": "2.0",
    "id": 211,
    "method": "opencode.sessions.prompt_async",
    "params": {
      "session_id": "<session_id>",
      "request": {
        "parts": [
          {
            "type": "subtask",
            "prompt": "Inspect the auth middleware and list the highest-risk gaps.",
            "description": "Security-focused pass over request auth flow",
            "agent": "explore",
            "command": "review"
          }
        ]
      }
    }
  }'
```

### Session Command (`opencode.sessions.command`)

```bash
curl -sS http://127.0.0.1:8000/ \
  -H 'content-type: application/json' \
  -H 'Authorization: Bearer <your-token>' \
  -d '{
    "jsonrpc": "2.0",
    "id": 22,
    "method": "opencode.sessions.command",
    "params": {
      "session_id": "<session_id>",
      "request": {
        "command": "/review",
        "arguments": "focus on security findings",
        "model": {
          "providerID": "google",
          "modelID": "gemini-2.5-flash"
        }
      },
      "metadata": {
        "opencode": {
          "directory": "/path/inside/workspace"
        }
      }
    }
  }'
```

Response:

- success => `{"item": <A2A Message>}` (JSON-RPC result)
- notification (no `id`) => HTTP `204 No Content`

### Session Fork / Share / Unshare

These methods return provider-private session summaries in `result.item`.

Example (`opencode.sessions.fork`):

```bash
curl -sS http://127.0.0.1:8000/ \
  -H 'content-type: application/json' \
  -H 'Authorization: Bearer <your-token>' \
  -d '{
    "jsonrpc": "2.0",
    "id": 221,
    "method": "opencode.sessions.fork",
    "params": {
      "session_id": "<session_id>",
      "request": {
        "messageID": "<message_id>"
      }
    }
  }'
```

### Session Summarize / Revert / Unrevert

- `opencode.sessions.summarize` returns `{"ok": true, "session_id": "<session_id>"}`
- `opencode.sessions.revert` / `opencode.sessions.unrevert` return provider-private session summaries in `result.item`
- `opencode.sessions.revert` requires `request.messageID`; `request.partID` is optional

Example (`opencode.sessions.summarize`):

```bash
curl -sS http://127.0.0.1:8000/ \
  -H 'content-type: application/json' \
  -H 'Authorization: Bearer <your-token>' \
  -d '{
    "jsonrpc": "2.0",
    "id": 224,
    "method": "opencode.sessions.summarize",
    "params": {
      "session_id": "<session_id>",
      "request": {
        "providerID": "openai",
        "modelID": "gpt-5",
        "auto": true
      }
    }
  }'
```

Example (`opencode.sessions.revert`):

```bash
curl -sS http://127.0.0.1:8000/ \
  -H 'content-type: application/json' \
  -H 'Authorization: Bearer <your-token>' \
  -d '{
    "jsonrpc": "2.0",
    "id": 225,
    "method": "opencode.sessions.revert",
    "params": {
      "session_id": "<session_id>",
      "request": {
        "messageID": "<message_id>",
        "partID": "<part_id>"
      }
    }
  }'
```

Example (`opencode.sessions.share`):

```bash
curl -sS http://127.0.0.1:8000/ \
  -H 'content-type: application/json' \
  -H 'Authorization: Bearer <your-token>' \
  -d '{
    "jsonrpc": "2.0",
    "id": 222,
    "method": "opencode.sessions.share",
    "params": {
      "session_id": "<session_id>"
    }
  }'
```

### Session Shell (`opencode.sessions.shell`)

`opencode.sessions.shell` is disabled by default. Enable with `A2A_ENABLE_SESSION_SHELL=true`.

Security warning:

- This is a high-risk method because it can execute shell commands in the workspace context.
- Enable only for trusted operators/internal scenarios.
- Keep bearer-token rotation, owner/directory guard checks, and audit log monitoring enabled before turning it on.

```bash
curl -sS http://127.0.0.1:8000/ \
  -H 'content-type: application/json' \
  -H 'Authorization: Bearer <your-token>' \
  -d '{
    "jsonrpc": "2.0",
    "id": 23,
    "method": "opencode.sessions.shell",
    "params": {
      "session_id": "<session_id>",
      "request": {
        "agent": "code-reviewer",
        "command": "git status --short"
      }
    }
  }'
```

Response:

- success => `{"item": <A2A Message>}` (JSON-RPC result)
- disabled => JSON-RPC error `METHOD_DISABLED`
- notification (no `id`) => HTTP `204 No Content`

### Provider List (`opencode.providers.list`)

Returns normalized provider summaries from the upstream OpenCode provider catalog.

```bash
curl -sS http://127.0.0.1:8000/ \
  -H 'content-type: application/json' \
  -H 'Authorization: Bearer <your-token>' \
  -d '{
    "jsonrpc": "2.0",
    "id": 24,
    "method": "opencode.providers.list",
    "params": {}
  }'
```

Response:

- success => `{"items": [...], "default_by_provider": {...}, "connected": [...]}` (JSON-RPC result)
- optional `metadata.opencode.workspace.id` routes discovery against a specific OpenCode workspace; otherwise the adapter falls back to directory routing when `metadata.opencode.directory` is provided

### Model List (`opencode.models.list`)

Returns normalized, flattened model summaries. Supports optional provider filter:

- `params.provider_id`

```bash
curl -sS http://127.0.0.1:8000/ \
  -H 'content-type: application/json' \
  -H 'Authorization: Bearer <your-token>' \
  -d '{
    "jsonrpc": "2.0",
    "id": 25,
    "method": "opencode.models.list",
    "params": {
      "provider_id": "openai"
    }
  }'
```

Response:

- success => `{"items": [...], "default_by_provider": {...}, "connected": [...]}` (JSON-RPC result)

## Workspace Control (Provider-Private Extension)

The runtime also exposes the OpenCode project/workspace/worktree control plane through provider-private JSON-RPC methods:

- `opencode.projects.list`
- `opencode.projects.current`
- `opencode.workspaces.list`
- `opencode.workspaces.create`
- `opencode.workspaces.remove`
- `opencode.worktrees.list`
- `opencode.worktrees.create`
- `opencode.worktrees.remove`
- `opencode.worktrees.reset`

Behavior notes:

- These methods target the active OpenCode deployment project. They are not routed through per-request workspace forwarding.
- `metadata.opencode.workspace.id` is declared consistently across the adapter, but current workspace-control methods do not use it to change the target project.
- Mutating methods should be treated as operator-only control-plane actions.

### Project Discovery (`opencode.projects.list`, `opencode.projects.current`)

```bash
curl -sS http://127.0.0.1:8000/ \
  -H 'content-type: application/json' \
  -H 'Authorization: Bearer <your-token>' \
  -d '{
    "jsonrpc": "2.0",
    "id": 31,
    "method": "opencode.projects.current",
    "params": {}
  }'
```

Response:

- `opencode.projects.list` => `{"items": [...]}`
- `opencode.projects.current` => `{"item": {...}}`

### Workspace Discovery and Mutation

```bash
curl -sS http://127.0.0.1:8000/ \
  -H 'content-type: application/json' \
  -H 'Authorization: Bearer <your-token>' \
  -d '{
    "jsonrpc": "2.0",
    "id": 32,
    "method": "opencode.workspaces.create",
    "params": {
      "request": {
        "id": "wrk-api",
        "type": "git",
        "branch": "main"
      }
    }
  }'
```

Response:

- `opencode.workspaces.list` => `{"items": [...]}`
- `opencode.workspaces.create` => `{"item": {...}}`
- `opencode.workspaces.remove` => `{"item": {...}}`

### Worktree Discovery and Mutation

```bash
curl -sS http://127.0.0.1:8000/ \
  -H 'content-type: application/json' \
  -H 'Authorization: Bearer <your-token>' \
  -d '{
    "jsonrpc": "2.0",
    "id": 33,
    "method": "opencode.worktrees.reset",
    "params": {
      "request": {
        "directory": "/repo/services/api"
      }
    }
  }'
```

Response:

- `opencode.worktrees.list` => `{"items": [...]}`
- `opencode.worktrees.create` => `{"item": {...}}`
- `opencode.worktrees.remove` => `{"ok": true|false}`
- `opencode.worktrees.reset` => `{"ok": true|false}`

## Interrupt Recovery (Provider-Private Extension)

The runtime also exposes provider-private recovery queries for pending interactive interrupts:

- `opencode.permissions.list`
- `opencode.questions.list`

These methods return recovery views over the local interrupt binding registry. They do not replace the shared `a2a.interrupt.*` callback methods.

Response shape:

- success => `{"items": [{"request_id", "session_id", "interrupt_type", "task_id", "context_id", "details", "expires_at"}]}` (JSON-RPC result)

Notes:

- Recovery results are scoped to the current authenticated caller identity when the runtime can resolve one.
- The runtime stores normalized interrupt `details` alongside request bindings, so recovery results match the shape emitted in `metadata.shared.interrupt.details`.
- The first implementation stage reads from the local interrupt registry rather than proxying upstream global `/permission` or `/question` pending lists.
- Use recovery queries to rediscover pending requests after reconnecting; use `a2a.interrupt.*` methods to resolve them.

## Shared Interrupt Callback (A2A Extension)

When stream metadata reports an interrupt request at `metadata.shared.interrupt`, clients can reply through JSON-RPC extension methods:

- `a2a.interrupt.permission.reply`
  - required: `request_id`
  - required: `reply` (`once` / `always` / `reject`)
  - optional: `message`
  - optional: `metadata.opencode.directory`
- `a2a.interrupt.question.reply`
  - required: `request_id`
  - required: `answers` (`Array<Array<string>>`)
  - optional: `metadata.opencode.directory`
- `a2a.interrupt.question.reject`
  - required: `request_id`
  - optional: `metadata.opencode.directory`

Notes:

- `request_id` must be a live interrupt request observed from stream metadata (`metadata.shared.interrupt.request_id`) or rediscovered through `opencode.permissions.list` / `opencode.questions.list`.
- The server keeps an interrupt binding registry; callbacks with unknown or expired `request_id` are rejected.
- The cache retention windows are controlled by `A2A_INTERRUPT_REQUEST_TTL_SECONDS` (default: `10800` seconds / `180` minutes) and `A2A_INTERRUPT_REQUEST_TOMBSTONE_TTL_SECONDS` (default: `600` seconds / `10` minutes). After the active TTL elapses, the server keeps a short-lived tombstone so repeated replies continue to return `INTERRUPT_REQUEST_EXPIRED` before eventually aging out to `INTERRUPT_REQUEST_NOT_FOUND`.
- These values are deployment/runtime settings and are intentionally not part of the shared extension method contract.
- Callback requests are validated against interrupt type and caller identity.
- Callback context variables use the shared method contract plus OpenCode-private metadata when needed (`params.metadata.opencode.directory`).
- Successful callback responses are minimal: only `ok` and `request_id`.
- Error types:
  - `INTERRUPT_REQUEST_NOT_FOUND`
  - `INTERRUPT_REQUEST_EXPIRED`
  - `INTERRUPT_TYPE_MISMATCH`
  - `UPSTREAM_UNREACHABLE`
  - `UPSTREAM_HTTP_ERROR`

Permission reply example:

```bash
curl -sS http://127.0.0.1:8000/ \
  -H 'content-type: application/json' \
  -H 'Authorization: Bearer <your-token>' \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "a2a.interrupt.permission.reply",
    "params": {
      "request_id": "<request_id>",
      "reply": "once",
      "metadata": {
        "opencode": {
          "directory": "/path/inside/workspace"
        }
      }
    }
  }'
```

## Authentication Example (curl)

```bash
curl -sS http://127.0.0.1:8000/v1/message:send \
  -H 'content-type: application/json' \
  -H 'Authorization: Bearer <your-token>' \
  -d '{
    "message": {
      "messageId": "msg-1",
      "role": "ROLE_USER",
      "content": [{"text": "Explain what this repository does."}]
    }
  }'
```

## JSON-RPC Send Example (curl)

```bash
curl -sS http://127.0.0.1:8000/ \
  -H 'content-type: application/json' \
  -H 'Authorization: Bearer <your-token>' \
  -d '{
    "jsonrpc": "2.0",
    "id": 101,
    "method": "message/send",
    "params": {
      "message": {
        "messageId": "msg-1",
        "role": "user",
        "parts": [{"kind": "text", "text": "Explain what this repository does."}]
      }
    }
  }'
```

## Streaming Re-Subscription (`subscribe`)

If an SSE connection drops, use `GET /v1/tasks/{task_id}:subscribe` to re-subscribe while the task is still non-terminal.

## Cancellation Semantics (`tasks/cancel`)

- The service first marks the A2A task as `canceled` and keeps cancel requests responsive.
- For running tasks, the service attempts upstream OpenCode `POST /session/{sessionID}/abort` to stop generation.
- Upstream interruption is best-effort: if upstream returns 404, network errors, or other HTTP errors, A2A cancellation still completes with `TaskState.canceled`.
- Idempotency contract: repeated `tasks/cancel` on an already `canceled` task returns the current terminal task state without error.
- Terminal subscribe contract: calling `subscribe` on a terminal task replays one terminal `Task` snapshot and then closes the stream.
- These two semantics are also declared as machine-readable `service_behaviors` in the compatibility profile and wire contract extensions.
- The service emits lightweight metric log records (`logger=opencode_a2a.execution.executor`):
  - `a2a_stream_requests_total`
  - `a2a_stream_active` (`value=1` when a stream starts, `value=-1` when it closes)
  - `opencode_stream_retries_total`
  - `tool_call_chunks_emitted_total`
  - `interrupt_requests_total`
  - `interrupt_resolved_total`
- The cancel path also emits:
  - `a2a_cancel_requests_total`
  - `a2a_cancel_abort_attempt_total`
  - `a2a_cancel_abort_success_total`
  - `a2a_cancel_abort_timeout_total`
  - `a2a_cancel_abort_error_total`
  - `a2a_cancel_duration_ms` (with `abort_outcome` label)

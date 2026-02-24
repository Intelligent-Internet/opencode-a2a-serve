# opencode-a2a-serve

> Turn OpenCode into a stateful A2A service with a clear security boundary and production-friendly deployment workflow.

## Vision

Provide a practical adapter layer that lets teams expose OpenCode through standard A2A interfaces (REST + JSON-RPC) while keeping operations, auth, and session behavior explicit and auditable.

## Core Value

- Protocol bridge: map A2A message/task semantics to OpenCode session/message/event APIs.
- Stateful interaction: support session continuation and reconnection workflows.
- Operational readiness: include systemd multi-instance deployment scripts and guardrails.
- Security baseline: enforce bearer-token auth and document key risk boundaries.

## Core Capabilities

- A2A HTTP+JSON endpoints (`/v1/message:send`, `/v1/message:stream`, `GET /v1/tasks/{task_id}:subscribe`).
- A2A JSON-RPC endpoint (`POST /`) for standard methods and OpenCode-oriented extensions.
- Streaming with incremental task artifacts and terminal status events.
- Session continuation via `metadata.opencode.session_id`.
- Session query/control extension methods (`opencode.sessions.*`) and interrupt callback methods.

## Quick Start

1. Start OpenCode:

```bash
opencode serve
```

2. Install dependencies:

```bash
uv sync --all-extras
```

3. Start this service:

```bash
A2A_BEARER_TOKEN=dev-token uv run opencode-a2a-serve
```

Default address: `http://127.0.0.1:8000`

## Documentation Map

- Product/protocol behavior (single source):
  - [`docs/guide.md`](docs/guide.md)
- Script entry and operations:
  - [`scripts/README.md`](scripts/README.md)
  - [`scripts/about_deploy.md`](scripts/about_deploy.md)
  - [`scripts/about_init_system.md`](scripts/about_init_system.md)
  - [`scripts/about_start_services.md`](scripts/about_start_services.md)
  - [`scripts/about_uninstall.md`](scripts/about_uninstall.md)

## Security Boundary

- `A2A_BEARER_TOKEN` is required for startup.
- LLM provider keys are consumed by the OpenCode process. This model is best suited for trusted/internal environments unless stronger credential isolation is introduced.
- Within one service instance, consumers share the same underlying OpenCode workspace/environment (not tenant-isolated by default).

## Development & Validation

```bash
uv run pre-commit run --all-files
uv run mypy src/opencode_a2a_serve
uv run pytest
```

## License

Apache-2.0. See [`LICENSE`](LICENSE).

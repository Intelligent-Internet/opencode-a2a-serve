# Contributing

Thanks for contributing to `opencode-a2a-server`.

This repository maintains an A2A adapter service around OpenCode. Changes
should keep runtime behavior, Agent Card declarations, OpenAPI examples, and
machine-readable extension contracts aligned.

## Before You Start

- Read [README.md](README.md) for project scope and user/operator paths.
- Read [docs/guide.md](docs/guide.md) for runtime contracts and compatibility guidance.
- Read [SECURITY.md](SECURITY.md) before changing auth, deployment, or secret handling.

## Development Setup

Requirements:

- Python 3.11, 3.12, or 3.13
- `uv`
- A reachable OpenCode runtime if you need end-to-end manual checks

Install dependencies:

```bash
uv sync --all-extras
```

Start OpenCode in one terminal:

```bash
opencode serve --hostname 127.0.0.1 --port 4096
```

Then start the A2A server in another terminal:

```bash
A2A_BEARER_TOKEN=dev-token \
OPENCODE_BASE_URL=http://127.0.0.1:4096 \
OPENCODE_WORKSPACE_ROOT=/abs/path/to/workspace \
uv run opencode-a2a-server serve
```

## Validation

Run the primary validation entrypoint before opening a PR. This script runs `pre-commit`, `pytest`, and enforces coverage policy:

```bash
./scripts/doctor.sh
```

For more details on available scripts, see [scripts/README.md](scripts/README.md).

## Git and PR Workflow

- **Mainline Sync**: Branch from the latest `main`. Use `git fetch` and `git merge --ff-only` to sync mainline and avoid implicit merges.
- **Branching**: Implement each task on an independent branch. Do not push directly to protected branches (`main`, `master`, `release/*`).
- **History**: Do not rewrite shared history. Avoid `git push --force` or arbitrary `rebase` on public branches.
- **Commits**: Commit only files related to the current task. Link the relevant `#issue` in commit messages and PR descriptions.
- **Draft PRs**: Open PRs as Draft by default for iteration and review.

## Change Expectations

- **Language**: Keep code, comments, and documentation in English. Use Simplified Chinese for issues, PRs, and collaboration discussion.
- **Consistency**: Keep runtime behavior, Agent Card declarations, OpenAPI examples, and machine-readable extension contracts aligned.
- **Compatibility**: Prefer additive, explicit compatibility changes over silent behavior changes.
- **AI Agents**: If you are an AI agent, see [AGENTS.md](AGENTS.md) for additional coordination rules and CLI tool conventions.

## Documentation

Update docs together with code whenever you change:

- authentication or deployment behavior
- extension contracts or compatibility expectations
- user-facing request or response shapes
- operational scripts

Keep compatibility guidance centralized in [docs/guide.md](docs/guide.md) unless a
new standalone document is clearly necessary.

When changing extension contracts, update
[`src/opencode_a2a_server/contracts/extensions.py`](src/opencode_a2a_server/contracts/extensions.py)
first and keep these generated/documented surfaces aligned:

- Agent Card extension params
- OpenAPI `POST /` extension metadata and examples
- JSON-RPC notification behavior (`204 No Content`)

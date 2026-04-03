# Contributing

Thanks for contributing to `opencode-a2a`.

This repository maintains an OpenCode A2A runtime. Changes should keep runtime behavior, Agent Card declarations, OpenAPI examples, and machine-readable extension contracts aligned.

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

Then start the A2A runtime in another terminal:

```bash
A2A_BEARER_TOKEN=dev-token \
OPENCODE_BASE_URL=http://127.0.0.1:4096 \
OPENCODE_WORKSPACE_ROOT=/abs/path/to/workspace \
uv run opencode-a2a serve
```

## Validation

Run the default validation baseline before opening a PR:

```bash
uv run pre-commit run --all-files
uv run pytest
```

If you change shell scripts, also run `bash -n` on each modified script, for example:

```bash
bash -n scripts/doctor.sh
bash -n scripts/lint.sh
```

External interoperability experiments stay outside the default regression baseline. When you need to reproduce current official-tool behavior, run:

```bash
bash ./scripts/conformance.sh
```

Treat that output as investigation input. Do not fold it into `doctor.sh` or the default CI quality gate unless the repository explicitly decides to promote a specific experiment into a maintained policy.

If you change extension methods, extension metadata, or Agent Card/OpenAPI contract surfaces, also run:

```bash
uv run pytest tests/contracts/test_extension_contract_consistency.py
uv run mypy src/opencode_a2a
```

## Change Expectations

- Keep code, comments, and docs in English.
- Keep issue / PR discussion in Simplified Chinese when collaborating in this repository.
- Do not drift Agent Card, OpenAPI examples, wire contract metadata, and runtime behavior.
- Prefer additive, explicit compatibility changes over silent behavior changes.
- Treat `opencode.*` surfaces as provider-private unless the repository already defines them as shared A2A contracts.

## Git and PR Workflow

- Branch from the latest `main`.
- Use `git fetch` and `git merge --ff-only` to sync mainline.
- Do not push directly to protected branches.
- Link the relevant issue in commits and PR descriptions when applicable.
- Open PRs as Draft by default when the change still needs review or iteration.

## Release Recovery

`Publish` is the release workflow for tagged versions. It now supports both the normal tag-push path and explicit maintainer recovery runs.

- Tag pushes still perform the full release flow: regression checks, artifact builds, PyPI publish, and GitHub Release sync.
- Manual `workflow_dispatch` runs require a `release_tag` input so the workflow checks out and rebuilds the exact tagged revision instead of the current branch tip.
- Manual `workflow_dispatch` runs default `publish_to_pypi=false` so the safest recovery path is to repair the GitHub Release without attempting a duplicate PyPI publish.
- Set `publish_to_pypi=true` only when a maintainer intentionally needs the manual dispatch to publish artifacts to PyPI before syncing the GitHub Release.
- GitHub Release sync is idempotent for the tagged release: it creates the release when missing and uploads only missing wheel/sdist assets.

If a release run publishes to PyPI successfully but fails while creating or uploading the GitHub Release, recover with a manual dispatch against the same tag and set `publish_to_pypi=false`.

## Documentation

Update docs together with code whenever you change:

- authentication or deployment behavior
- extension contracts or compatibility expectations
- user-facing request or response shapes
- operational scripts

Keep compatibility guidance centralized in [docs/guide.md](docs/guide.md) unless a new standalone document is clearly necessary.

When changing extension contracts, update [`src/opencode_a2a/contracts/extensions.py`](src/opencode_a2a/contracts/extensions.py) first and keep these generated/documented surfaces aligned:

- Agent Card extension params
- OpenAPI `POST /` extension metadata and examples
- JSON-RPC notification behavior (`204 No Content`)

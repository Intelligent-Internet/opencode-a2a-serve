# Deploy Script Guide (`deploy.sh`)

This document explains `scripts/deploy.sh` and its helper scripts under `scripts/deploy/`.

Scope:

- systemd multi-instance deployment flow
- input variables, precedence, generated files
- operational commands and deployment-side security notes

Out of scope:

- protocol contract and runtime API semantics
- JSON-RPC extension behavior details

For protocol/runtime behavior, use [`../docs/guide.md`](../docs/guide.md) as the single source.

## Prerequisites

- host provides `systemd` and `sudo`
- shared OpenCode runtime path exists (default `/opt/.opencode`)
- this repository exists on host (default `/opt/opencode-a2a/opencode-a2a-serve`)
- A2A virtualenv exists (default `${OPENCODE_A2A_DIR}/.venv/bin/opencode-a2a-serve`)
- `uv` Python pool exists (default `/opt/uv-python`)

For one-time host bootstrap, see [`about_init_system.md`](./about_init_system.md).

## Quick Deploy

```bash
GH_TOKEN='<gh-token>' A2A_BEARER_TOKEN='<a2a-token>' \
./scripts/deploy.sh project=alpha a2a_port=8010 a2a_host=127.0.0.1
```

HTTPS public URL example:

```bash
GH_TOKEN='<gh-token>' A2A_BEARER_TOKEN='<a2a-token>' \
./scripts/deploy.sh project=alpha a2a_port=8010 a2a_public_url=https://a2a.example.com
```

Update shared code and restart one instance:

```bash
GH_TOKEN='<gh-token>' A2A_BEARER_TOKEN='<a2a-token>' \
./scripts/deploy.sh project=alpha update_a2a=true force_restart=true
```

## Secrets and Inputs

Required secret env vars:

- `GH_TOKEN`
- `A2A_BEARER_TOKEN`

Optional provider key env vars:

- `GOOGLE_GENERATIVE_AI_API_KEY`
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `AZURE_OPENAI_API_KEY`
- `OPENROUTER_API_KEY`

Common CLI keys (case-insensitive):

- `project` / `project_name`
- `data_root`
- `a2a_port`, `a2a_host`, `a2a_public_url`
- `a2a_streaming`, `a2a_log_level`, `a2a_otel_instrumentation_enabled`
- `a2a_log_payloads`, `a2a_log_body_limit`
- `a2a_cancel_abort_timeout_seconds`, `a2a_enable_session_shell`
- `opencode_provider_id`, `opencode_model_id`, `opencode_lsp`
- `opencode_timeout`, `opencode_timeout_stream`
- `repo_url`, `repo_branch`
- `git_identity_name`, `git_identity_email`
- `update_a2a`, `force_restart`

Sensitive values are intentionally blocked from CLI keys.

## Input Precedence

For fields that support both env vars and CLI keys:

`CLI key=value` > process env > built-in default.

This precedence is implemented by `deploy.sh` and materialized into per-instance env files by `scripts/deploy/setup_instance.sh`.

## Generated Layout and Files

Per project instance (default root: `/data/opencode-a2a/<project>`):

- `workspace/`: OpenCode workspace
- `config/`: instance env files
- `logs/`: runtime logs
- `run/`: runtime data

Key generated env files:

- `config/opencode.env`
- `config/opencode.secret.env` (provider keys when provided)
- `config/a2a.env`

`A2A_PROJECT` is generated from `project=<name>` into `a2a.env`.

## Provider Coverage (Deploy Layer)

| Provider | Secret key persisted by deploy scripts | Startup key enforcement in `run_opencode.sh` |
| --- | --- | --- |
| Google / Gemini | `GOOGLE_GENERATIVE_AI_API_KEY` | Yes (explicit check for google/gemini patterns) |
| OpenAI | `OPENAI_API_KEY` | No explicit provider-specific check |
| Anthropic | `ANTHROPIC_API_KEY` | No explicit provider-specific check |
| Azure OpenAI | `AZURE_OPENAI_API_KEY` | No explicit provider-specific check |
| OpenRouter | `OPENROUTER_API_KEY` | No explicit provider-specific check |

Known gap: provider/model validation is partial at deploy-script level.

## Service Operations

Status:

```bash
sudo systemctl status opencode@<project>.service
sudo systemctl status opencode-a2a@<project>.service
```

Recent logs:

```bash
sudo journalctl -u opencode@<project>.service -n 200 --no-pager
sudo journalctl -u opencode-a2a@<project>.service -n 200 --no-pager
```

Follow logs:

```bash
sudo journalctl -u opencode@<project>.service -f
sudo journalctl -u opencode-a2a@<project>.service -f
```

Uninstall one instance:

```bash
./scripts/uninstall.sh project=<project>
./scripts/uninstall.sh project=<project> confirm=UNINSTALL
```

## Security Notes

- `a2a_enable_session_shell=true` enables `opencode.sessions.shell`, a high-risk capability that can run shell commands in workspace context.
- Keep token governance, audit logs, and strict access control in place before enabling shell control.
- This architecture does not provide hard credential isolation from agent behavior; treat it as trusted/internal deployment unless isolation controls are added.

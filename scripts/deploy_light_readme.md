# Lightweight Local Launcher (`deploy_light.sh`)

This document describes `scripts/deploy_light.sh`, a lightweight entry point for
starting one local OpenCode + A2A instance in the foreground.

## Convergence Notice (#181)

`deploy_light.sh` is converging into a foreground-only launcher. It no longer
manages background process lifecycles (nohup/stop/restart). It is designed to be
consumed by external process managers like `pm2`, `systemd`, or higher-level
orchestrators for **parameterized self-deployment** (#145).

Scope:

- stays in foreground (stdout/stderr direct output)
- supports the same machine-readable contract as `deploy.sh`
- does **not** create system users or isolated data roots
- best suited for local development or ephemeral agent-managed instances

## Usage

Required environment:

```bash
export A2A_BEARER_TOKEN='<a2a-token>'
```

Start one instance (foreground):

```bash
./scripts/deploy_light.sh start workdir=/abs/path/to/workspace
```

Recommended consumption with `pm2`:

```bash
pm2 start ./scripts/deploy_light.sh --name "a2a-alpha" -- start workdir=/data/alpha a2a_port=8010
```

## Key Inputs

- `workdir`:
  required for `start` / `restart`; becomes the default `OPENCODE_DIRECTORY`
  exposed to the A2A layer
- `instance`:
  instance identifier used to isolate pid/log directories
- `a2a_host` / `a2a_port` / `a2a_public_url`:
  A2A listen address and published URL
- `opencode_bind_host` / `opencode_bind_port`:
  local OpenCode bind address for the supervised `opencode serve`
- `opencode_provider_id` / `opencode_model_id`:
  default upstream provider/model selection
- `opencode_lsp`:
  whether to enable LSP in generated OpenCode config content
- `log_root` / `run_root`:
  root directories for per-instance logs and pid/metadata files
- `start_timeout_seconds`:
  readiness wait budget for both OpenCode and A2A startup

## Instance Layout

For `instance=demo`, the script writes:

- runtime metadata and pid files under `run/light/demo/`
- process logs under `logs/light/demo/`

Each instance uses separate files for:

- `opencode.pid`
- `a2a.pid`
- `metadata.env`
- `opencode.log`
- `a2a.log`

This avoids the broad `pgrep -f` matching used by the foreground local runner and reduces the risk of touching unrelated local processes.

## Readiness Behavior

On `start`, the script:

1. validates required inputs and local commands
2. starts `opencode serve`
3. waits until `GET /session` succeeds on the configured OpenCode bind address
4. starts `opencode-a2a-server`
5. waits until the local Agent Card endpoint responds successfully

If either process fails readiness, the script stops any already-started child process and exits non-zero.

## Security / Scope Notes

- `A2A_BEARER_TOKEN` is still required.
- Provider secrets are inherited from the current shell environment.
- The current Linux user remains the trust boundary.
- All consumers of one lightweight instance still share the same underlying workspace/environment.
- This flow is not tenant-isolated and is not a replacement for stronger deployment isolation.

## Related Docs

- runtime behavior and API contracts: [`../docs/guide.md`](../docs/guide.md)
- script index: [`./README.md`](./README.md)
- foreground local runner: [`./start_services_readme.md`](./start_services_readme.md)
- systemd deployment flow: [`./deploy_readme.md`](./deploy_readme.md)

# Release Deploy Smoke Test

This document defines a real-host smoke test plan for the release-based systemd
deployment path:

- [`../scripts/init_release_system.sh`](../scripts/init_release_system.sh)
- [`../scripts/deploy_release.sh`](../scripts/deploy_release.sh)

The goal is to validate that published package versions can be bootstrapped,
deployed, restarted, and removed on a real Linux host without relying on a
source checkout.

## Scope

This smoke test covers:

- release bootstrap on a real host
- first-time release-based systemd deploy
- service readiness checks
- fixed-version reinstall / update path
- uninstall / cleanup path

This smoke test does not replace protocol-level API tests or CI unit tests.

## Recommended Test Environment

- a clean Linux host or temporary VM
- `systemd`, `sudo`, outbound network access
- no reused `/opt/opencode-a2a-release` or `/data/opencode-a2a` state from prior experiments
- a published package version, for example `0.1.0`

## Test Matrix

Run at least these two variants:

1. exact release pin
   - `A2A_RELEASE_VERSION=0.1.0`
   - `release_version=0.1.0`
2. default latest release
   - no explicit `A2A_RELEASE_VERSION`
   - no explicit `release_version`

## Step 1: Host Bootstrap

Bootstrap the host with the release-based path:

```bash
A2A_RELEASE_VERSION=0.1.0 ./scripts/init_release_system.sh
```

Checks:

- `/opt/opencode-a2a-release/tool` exists
- `/opt/opencode-a2a-release/bin/opencode-a2a-server` exists and is executable
- `/opt/opencode-a2a-release/runtime/run_a2a.sh` exists
- `opencode` is available

Expected boundary:

- this path should not require a source checkout as the deployment runtime
- release helper scripts should live under `/opt/opencode-a2a-release/runtime`

## Step 2: First Deploy

Run the first deploy:

```bash
./scripts/deploy_release.sh project=alpha a2a_port=8010 a2a_host=127.0.0.1 release_version=0.1.0
```

Expected first-run behavior:

- project directories are created
- `*.example` secret templates are created
- services do not start until required secret files exist

Prepare secrets:

```bash
sudo cp /data/opencode-a2a/alpha/config/opencode.auth.env.example /data/opencode-a2a/alpha/config/opencode.auth.env
sudo cp /data/opencode-a2a/alpha/config/a2a.secret.env.example /data/opencode-a2a/alpha/config/a2a.secret.env
sudoedit /data/opencode-a2a/alpha/config/opencode.auth.env
sudoedit /data/opencode-a2a/alpha/config/a2a.secret.env
```

Re-run deploy:

```bash
./scripts/deploy_release.sh project=alpha a2a_port=8010 a2a_host=127.0.0.1 release_version=0.1.0
```

## Step 3: Service Readiness

Check systemd units:

```bash
sudo systemctl status opencode@alpha.service --no-pager
sudo systemctl status opencode-a2a-server@alpha.service --no-pager
```

Check health:

```bash
curl -fsS -H "Authorization: Bearer <token>" http://127.0.0.1:8010/health
```

Check Agent Card:

```bash
curl -fsS -H "Authorization: Bearer <token>" http://127.0.0.1:8010/.well-known/agent-card.json
```

Inspect generated unit configuration:

```bash
sudo systemctl cat opencode@alpha.service
sudo systemctl cat opencode-a2a-server@alpha.service
```

Inspect logs:

```bash
sudo journalctl -u opencode@alpha.service -n 100 --no-pager
sudo journalctl -u opencode-a2a-server@alpha.service -n 100 --no-pager
```

## Step 4: Update / Restart

Reinstall and restart the fixed version:

```bash
./scripts/deploy_release.sh project=alpha release_version=0.1.0 update_a2a=true force_restart=true
```

Then test the default latest-release path:

```bash
./scripts/deploy_release.sh project=alpha update_a2a=true force_restart=true
```

Checks:

- services restart cleanly
- no path/import errors appear in `journalctl`
- the runtime still serves `/health`

## Step 5: Uninstall / Cleanup

Preview:

```bash
./scripts/uninstall.sh project=alpha
```

Apply:

```bash
./scripts/uninstall.sh project=alpha confirm=UNINSTALL
```

Checks:

- instance services stop cleanly
- instance-specific systemd drop-ins are removed
- shared release runtime under `/opt/opencode-a2a-release` is not removed
- the same project name can be deployed again

## Minimum Pass Criteria

The release-based deployment path can be considered smoke-tested when all of
the following succeed on a real host:

- `init_release_system.sh`
- first deploy creates templates and stops safely before secrets are provisioned
- second deploy starts both systemd services
- `/health` returns HTTP 200
- `update_a2a=true` works
- `uninstall.sh` removes the instance without breaking the shared release runtime

## Failure Notes

When a smoke test fails, capture:

- exact command
- host OS / distribution
- relevant `systemctl status`
- relevant `journalctl` output
- whether the failure occurred in source-based or release-based mode

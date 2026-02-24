# scripts

Executable scripts live here. This file is the primary script-entry guide.

## Start Here

- [Usage guide](../docs/guide.md)
- [Deployment guide](../docs/deployment.md)

## Which Script to Use

- [`scripts/init_system.sh`](./init_system.sh):
  bootstrap host prerequisites for systemd deployment.
- [`scripts/deploy.sh`](./deploy.sh):
  create/update one long-running systemd instance.
- [`scripts/start_services.sh`](./start_services.sh):
  local foreground runner without systemd.
- [`scripts/uninstall.sh`](./uninstall.sh):
  remove one deployed instance (preview-first, explicit confirm required).
- [`scripts/doctor.sh`](./doctor.sh):
  one-command local environment consistency check (sync + pip check + lint + pytest).
- [`scripts/dependency_health.sh`](./dependency_health.sh):
  dependency health check (outdated list + vulnerability audit).

## Quick Links

- [`scripts/init_system.sh`](./init_system.sh)
- [`scripts/deploy.sh`](./deploy.sh)
- [`scripts/start_services.sh`](./start_services.sh)
- [`scripts/uninstall.sh`](./uninstall.sh)
- [`scripts/doctor.sh`](./doctor.sh)
- [`scripts/dependency_health.sh`](./dependency_health.sh)

## Notes

- `scripts/deploy/` contains helper scripts orchestrated by `scripts/deploy.sh`.
- Keep long-form documentation changes in `docs/` to avoid divergence.

# scripts

Executable scripts live in this directory. This file is the entry index for script usage and script-specific documentation.

## Product Contract vs Script Docs

- Product/API behavior (transport, protocol contracts, extension semantics):
  - [`../docs/guide.md`](../docs/guide.md)
- Script operational details (how to run and operate each script):
  - kept in this `scripts/` directory as `about_*.md`

## Script Docs Index

- [`about_init_system.md`](./about_init_system.md): host bootstrap and shared runtime preparation (`init_system.sh`)
- [`about_deploy.md`](./about_deploy.md): multi-instance systemd deployment (`deploy.sh`)
- [`about_start_services.md`](./about_start_services.md): local foreground runner (`start_services.sh`)
- [`about_uninstall.md`](./about_uninstall.md): preview-first instance removal (`uninstall.sh`)

## Script Quick Links

- [`init_system.sh`](./init_system.sh)
- [`deploy.sh`](./deploy.sh)
- [`start_services.sh`](./start_services.sh)
- [`uninstall.sh`](./uninstall.sh)
- [`doctor.sh`](./doctor.sh)
- [`dependency_health.sh`](./dependency_health.sh)

## Notes

- `deploy/` contains helper scripts orchestrated by `deploy.sh`.
- Keep script behavior details in `scripts/about_*.md` to avoid drift.

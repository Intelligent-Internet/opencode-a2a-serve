#!/usr/bin/env bash
set -euo pipefail

PROJECT_NAME="${1:-}"

if [[ -z "$PROJECT_NAME" ]]; then
  echo "Usage: $0 <project_name>" >&2
  exit 1
fi

sudo systemctl daemon-reload
sudo systemctl enable --now "opencode@${PROJECT_NAME}.service"
sudo systemctl enable --now "opencode-a2a@${PROJECT_NAME}.service"

sudo systemctl status "opencode-a2a@${PROJECT_NAME}.service" --no-pager

#!/usr/bin/env bash
# Enable and start systemd services for a project.
# Usage: ./enable_instance.sh <project_name>
# Requires sudo to manage systemd services.
set -euo pipefail

PROJECT_NAME="${1:-}"

if [[ -z "$PROJECT_NAME" ]]; then
  echo "Usage: $0 <project_name>" >&2
  exit 1
fi

sudo systemctl daemon-reload
if [[ -n "${GOOGLE_GENERATIVE_AI_API_KEY:-}" ]]; then
  sudo systemctl set-property --runtime "opencode@${PROJECT_NAME}.service" \
    "Environment=GOOGLE_GENERATIVE_AI_API_KEY=${GOOGLE_GENERATIVE_AI_API_KEY}"
fi
sudo systemctl enable --now "opencode@${PROJECT_NAME}.service"
sudo systemctl enable --now "opencode-a2a@${PROJECT_NAME}.service"

sudo systemctl status "opencode-a2a@${PROJECT_NAME}.service" --no-pager

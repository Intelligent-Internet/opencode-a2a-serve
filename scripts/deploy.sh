#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PROJECT_NAME="${1:-}"
GH_TOKEN="${2:-}"
A2A_BEARER_TOKEN="${3:-}"
A2A_PORT_INPUT="${4:-}"

if [[ -z "$PROJECT_NAME" || -z "$GH_TOKEN" || -z "$A2A_BEARER_TOKEN" ]]; then
  echo "Usage: $0 <project_name> <github_token> <a2a_bearer_token> [a2a_port]" >&2
  exit 1
fi

export OPENCODE_A2A_DIR="${OPENCODE_A2A_DIR:-/opt/opencode-a2a/opencode-a2a-serve}"
export OPENCODE_CORE_DIR="${OPENCODE_CORE_DIR:-/opt/.opencode}"
export UV_PYTHON_DIR="${UV_PYTHON_DIR:-/opt/uv-python}"
export DATA_ROOT="${DATA_ROOT:-/data/projects}"

export OPENCODE_BIND_HOST="${OPENCODE_BIND_HOST:-127.0.0.1}"
export OPENCODE_BIND_PORT="${OPENCODE_BIND_PORT:-4096}"
export OPENCODE_LOG_LEVEL="${OPENCODE_LOG_LEVEL:-INFO}"
export OPENCODE_EXTRA_ARGS="${OPENCODE_EXTRA_ARGS:-}"

export A2A_HOST="${A2A_HOST:-127.0.0.1}"
if [[ -n "$A2A_PORT_INPUT" ]]; then
  export A2A_PORT="$A2A_PORT_INPUT"
else
  export A2A_PORT="${A2A_PORT:-8000}"
fi
export A2A_PUBLIC_URL="${A2A_PUBLIC_URL:-http://${A2A_HOST}:${A2A_PORT}}"
export A2A_LOG_LEVEL="${A2A_LOG_LEVEL:-info}"

"${SCRIPT_DIR}/deploy/install_units.sh"
"${SCRIPT_DIR}/deploy/setup_instance.sh" "$PROJECT_NAME" "$GH_TOKEN" "$A2A_BEARER_TOKEN"
"${SCRIPT_DIR}/deploy/enable_instance.sh" "$PROJECT_NAME"

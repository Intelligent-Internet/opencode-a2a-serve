#!/usr/bin/env bash
set -euo pipefail

PROJECT_NAME="${1:-}"
GH_TOKEN="${2:-}"
A2A_BEARER_TOKEN="${3:-}"

if [[ -z "$PROJECT_NAME" || -z "$GH_TOKEN" || -z "$A2A_BEARER_TOKEN" ]]; then
  echo "Usage: $0 <project_name> <github_token> <a2a_bearer_token>" >&2
  exit 1
fi

: "${DATA_ROOT:?}"
: "${OPENCODE_BIND_HOST:?}"
: "${OPENCODE_BIND_PORT:?}"
: "${OPENCODE_LOG_LEVEL:?}"
: "${A2A_HOST:?}"
: "${A2A_PORT:?}"
: "${A2A_PUBLIC_URL:?}"

PROJECT_DIR="${DATA_ROOT}/${PROJECT_NAME}"
WORKSPACE_DIR="${PROJECT_DIR}/workspace"
CONFIG_DIR="${PROJECT_DIR}/config"
LOG_DIR="${PROJECT_DIR}/logs"
RUN_DIR="${PROJECT_DIR}/run"

if ! id "$PROJECT_NAME" &>/dev/null; then
  sudo adduser --system --group --home "$PROJECT_DIR" "$PROJECT_NAME"
fi

sudo install -d -m 711 -o root -g root "$DATA_ROOT"
sudo install -d -m 700 -o "$PROJECT_NAME" -g "$PROJECT_NAME" "$PROJECT_DIR" "$WORKSPACE_DIR" "$LOG_DIR" "$RUN_DIR"
sudo install -d -m 700 -o root -g root "$CONFIG_DIR"

opencode_env_tmp="$(mktemp)"
cat <<ENV >"$opencode_env_tmp"
OPENCODE_LOG_LEVEL=${OPENCODE_LOG_LEVEL}
OPENCODE_BIND_HOST=${OPENCODE_BIND_HOST}
OPENCODE_BIND_PORT=${OPENCODE_BIND_PORT}
OPENCODE_EXTRA_ARGS=${OPENCODE_EXTRA_ARGS:-}
ENV
sudo install -m 600 -o root -g root "$opencode_env_tmp" "$CONFIG_DIR/opencode.env"
rm -f "$opencode_env_tmp"

a2a_env_tmp="$(mktemp)"
cat <<ENV >"$a2a_env_tmp"
A2A_HOST=${A2A_HOST}
A2A_PORT=${A2A_PORT}
A2A_PUBLIC_URL=${A2A_PUBLIC_URL}
A2A_BEARER_TOKEN=${A2A_BEARER_TOKEN}
OPENCODE_BASE_URL=http://${OPENCODE_BIND_HOST}:${OPENCODE_BIND_PORT}
OPENCODE_DIRECTORY=${WORKSPACE_DIR}
OPENCODE_TIMEOUT=120
GH_TOKEN=${GH_TOKEN}
GIT_AUTHOR_NAME=OpenCode-${PROJECT_NAME}
GIT_COMMITTER_NAME=OpenCode-${PROJECT_NAME}
GIT_AUTHOR_EMAIL=${PROJECT_NAME}@internal
GIT_COMMITTER_EMAIL=${PROJECT_NAME}@internal
ENV
sudo install -m 600 -o root -g root "$a2a_env_tmp" "$CONFIG_DIR/a2a.env"
rm -f "$a2a_env_tmp"

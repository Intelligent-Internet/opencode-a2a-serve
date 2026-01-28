#!/usr/bin/env bash
# Wrapper to run opencode serve with configured host/port/logging.
set -euo pipefail

OPENCODE_CORE_DIR="${OPENCODE_CORE_DIR:-/opt/.opencode}"
OPENCODE_BIN="${OPENCODE_BIN:-${OPENCODE_CORE_DIR}/bin/opencode}"
OPENCODE_LOG_LEVEL="${OPENCODE_LOG_LEVEL:-INFO}"
OPENCODE_BIND_HOST="${OPENCODE_BIND_HOST:-127.0.0.1}"
OPENCODE_BIND_PORT="${OPENCODE_BIND_PORT:-4096}"
OPENCODE_EXTRA_ARGS="${OPENCODE_EXTRA_ARGS:-}"

if [[ ! -x "$OPENCODE_BIN" ]]; then
  echo "opencode binary not found at $OPENCODE_BIN" >&2
  exit 1
fi

cmd=("$OPENCODE_BIN" serve --log-level "$OPENCODE_LOG_LEVEL" --print-logs)

if [[ -n "$OPENCODE_BIND_HOST" ]]; then
  cmd+=(--hostname "$OPENCODE_BIND_HOST")
fi

if [[ -n "$OPENCODE_BIND_PORT" ]]; then
  cmd+=(--port "$OPENCODE_BIND_PORT")
fi

if [[ -n "$OPENCODE_EXTRA_ARGS" ]]; then
  read -r -a extra_args <<<"$OPENCODE_EXTRA_ARGS"
  cmd+=("${extra_args[@]}")
fi

exec "${cmd[@]}"

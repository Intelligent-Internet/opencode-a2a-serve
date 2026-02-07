#!/usr/bin/env bash
# Wrapper to run opencode-a2a from the shared venv.
set -euo pipefail

OPENCODE_A2A_DIR="${OPENCODE_A2A_DIR:-/opt/opencode-a2a/opencode-a2a-serve}"
A2A_BIN="${A2A_BIN:-${OPENCODE_A2A_DIR}/.venv/bin/opencode-a2a}"

if [[ ! -x "$A2A_BIN" ]]; then
  echo "opencode-a2a entrypoint not found at $A2A_BIN" >&2
  exit 1
fi

A2A_AUTH_MODE="${A2A_AUTH_MODE:-bearer}"

if [[ "$A2A_AUTH_MODE" == "bearer" ]]; then
  if [[ -z "${A2A_BEARER_TOKEN:-}" ]]; then
    echo "A2A_BEARER_TOKEN is required when A2A_AUTH_MODE is bearer" >&2
    exit 1
  fi
elif [[ "$A2A_AUTH_MODE" == "jwt" ]]; then
  if [[ -z "${A2A_JWT_SECRET:-}" ]]; then
    echo "A2A_JWT_SECRET is required when A2A_AUTH_MODE is jwt" >&2
    exit 1
  fi
  if [[ -z "${A2A_JWT_AUDIENCE:-}" ]]; then
    echo "A2A_JWT_AUDIENCE is required when A2A_AUTH_MODE is jwt" >&2
    exit 1
  fi
  if [[ "${A2A_JWT_REQUIRE_ISSUER:-}" =~ ^(1|true|yes|on)$ ]] && [[ -z "${A2A_JWT_ISSUER:-}" ]]; then
    echo "A2A_JWT_ISSUER is required when A2A_JWT_REQUIRE_ISSUER is true" >&2
    exit 1
  fi
  if [[ -n "${A2A_JWT_SCOPE_MATCH:-}" ]] && [[ "${A2A_JWT_SCOPE_MATCH}" != "any" && "${A2A_JWT_SCOPE_MATCH}" != "all" ]]; then
    echo "A2A_JWT_SCOPE_MATCH must be 'any' or 'all'" >&2
    exit 1
  fi
else
  echo "A2A_AUTH_MODE must be bearer or jwt" >&2
  exit 1
fi

exec "$A2A_BIN"

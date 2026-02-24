#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found in PATH" >&2
  exit 1
fi

echo "[dependency-health] sync locked environment"
uv sync --all-extras --frozen

echo "[dependency-health] verify dependency compatibility"
uv pip check

echo "[dependency-health] list outdated packages"
uv pip list --outdated

echo "[dependency-health] run vulnerability audit"
uv run pip-audit

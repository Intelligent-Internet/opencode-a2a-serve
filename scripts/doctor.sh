#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found in PATH" >&2
  exit 1
fi

echo "[doctor] sync locked environment"
uv sync --all-extras --frozen

echo "[doctor] verify dependency compatibility"
uv pip check

echo "[doctor] run lint"
uv run pre-commit run --all-files

echo "[doctor] run tests"
uv run pytest

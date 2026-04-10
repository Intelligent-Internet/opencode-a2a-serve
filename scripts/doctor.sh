#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=./health_common.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/health_common.sh"

run_shared_repo_health_prerequisites "doctor"

echo "[doctor] run lint"
uv run pre-commit run --all-files

echo "[doctor] run type checks"
uv run mypy src/opencode_a2a

echo "[doctor] run tests"
uv run pytest

echo "[doctor] enforce coverage policy"
uv run python ./scripts/check_coverage.py

echo "[doctor] build release artifacts"
rm -f dist/opencode_a2a-*.whl dist/opencode_a2a-*.tar.gz
uv build --no-sources

echo "[doctor] smoke test built wheel"
bash ./scripts/smoke_test_built_cli.sh dist/opencode_a2a-*.whl

#!/usr/bin/env bash
# Run a local-only external A2A conformance experiment without changing default repo regression gates.
set -euo pipefail

# shellcheck source=./health_common.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/health_common.sh"

usage() {
  cat <<'EOF'
Usage:
  bash ./scripts/conformance.sh [category]

Purpose:
  Run the official A2A TCK as a local/manual experiment.
  This script is intentionally separate from doctor.sh and CI quality gates.

Category:
  Defaults to "mandatory". Any category supported by a2aproject/a2a-tck run_tck.py is accepted.

Selected environment variables:
  CONFORMANCE_OUTPUT_DIR              Override artifact directory (default: run/conformance/<timestamp>)
  CONFORMANCE_TCK_DIR                 Override cached TCK checkout path (default: .cache/a2a-tck)
  CONFORMANCE_TCK_REPO                Override TCK repo URL (default: https://github.com/a2aproject/a2a-tck.git)
  CONFORMANCE_TCK_REF                 Override TCK git ref (default: main)
  CONFORMANCE_TRANSPORTS              Override requested transports (default: jsonrpc)
  CONFORMANCE_TRANSPORT_STRATEGY      Override TCK transport strategy (default: agent_preferred)
  CONFORMANCE_SUT_URL                 Use an already running SUT instead of the local dummy-backed runtime
  CONFORMANCE_SUT_PORT                Override local dummy-backed SUT port (default: 8011)
  CONFORMANCE_SKIP_REPO_SYNC=1        Skip uv sync/uv pip check for this repository
  CONFORMANCE_SKIP_TCK_SYNC=1         Skip uv sync inside the cached TCK checkout
  CONFORMANCE_AUTH_TYPE               Default auth type when A2A_AUTH_TYPE is unset (default: bearer)
  CONFORMANCE_AUTH_TOKEN              Default auth token when A2A_AUTH_TOKEN is unset (default: test-token)

Advanced authentication:
  The script preserves any caller-provided A2A_AUTH_* variables and only sets defaults
  for the common bearer-token case used by the local dummy-backed runtime.
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

if [[ "$#" -gt 1 ]]; then
  echo "Expected at most one positional argument: category" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

category="${1:-${CONFORMANCE_CATEGORY:-mandatory}}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
output_dir="${CONFORMANCE_OUTPUT_DIR:-${ROOT_DIR}/run/conformance/${timestamp}}"
tck_dir="${CONFORMANCE_TCK_DIR:-${ROOT_DIR}/.cache/a2a-tck}"
tck_repo="${CONFORMANCE_TCK_REPO:-https://github.com/a2aproject/a2a-tck.git}"
tck_ref="${CONFORMANCE_TCK_REF:-main}"
transport_strategy="${CONFORMANCE_TRANSPORT_STRATEGY:-agent_preferred}"
transports="${CONFORMANCE_TRANSPORTS:-jsonrpc}"
sut_port="${CONFORMANCE_SUT_PORT:-8011}"
repo_log="${output_dir}/repo-health.log"
tck_sync_log="${output_dir}/tck-sync.log"
sut_log="${output_dir}/sut.log"
tck_log="${output_dir}/tck.log"

mkdir -p "${output_dir}"

cleanup() {
  local exit_code="$1"
  if [[ -n "${sut_pid:-}" ]] && kill -0 "${sut_pid}" >/dev/null 2>&1; then
    kill "${sut_pid}" >/dev/null 2>&1 || true
    wait "${sut_pid}" >/dev/null 2>&1 || true
  fi
  exit "${exit_code}"
}

trap 'cleanup $?' EXIT

cd "${ROOT_DIR}"

if [[ "${CONFORMANCE_SKIP_REPO_SYNC:-0}" != "1" ]]; then
  run_shared_repo_health_prerequisites "conformance" >"${repo_log}" 2>&1
fi

mkdir -p "$(dirname "${tck_dir}")"
if [[ ! -d "${tck_dir}/.git" ]]; then
  git clone --depth 1 "${tck_repo}" "${tck_dir}" >"${output_dir}/tck-clone.log" 2>&1
fi

git -C "${tck_dir}" fetch --depth 1 origin "${tck_ref}" >"${output_dir}/tck-fetch.log" 2>&1
git -C "${tck_dir}" checkout --quiet FETCH_HEAD

if [[ "${CONFORMANCE_SKIP_TCK_SYNC:-0}" != "1" ]]; then
  (
    cd "${tck_dir}"
    uv sync
  ) >"${tck_sync_log}" 2>&1
fi

if [[ -z "${A2A_AUTH_TYPE:-}" ]]; then
  export A2A_AUTH_TYPE="${CONFORMANCE_AUTH_TYPE:-bearer}"
fi
if [[ -z "${A2A_AUTH_TOKEN:-}" && "${A2A_AUTH_TYPE}" == "bearer" ]]; then
  export A2A_AUTH_TOKEN="${CONFORMANCE_AUTH_TOKEN:-test-token}"
fi

sut_url="${CONFORMANCE_SUT_URL:-}"
if [[ -z "${sut_url}" ]]; then
  sut_url="http://127.0.0.1:${sut_port}"
  export CONFORMANCE_SUT_PORT="${sut_port}"
  export CONFORMANCE_SUT_URL="${sut_url}"
  uv run python - <<'PY' >"${sut_log}" 2>&1 &
import uvicorn
import opencode_a2a.server.application as app_module

from tests.support.helpers import DummyChatOpencodeUpstreamClient, make_settings

app_module.OpencodeUpstreamClient = DummyChatOpencodeUpstreamClient
settings = make_settings(
    a2a_host="127.0.0.1",
    a2a_port=int(__import__("os").environ["CONFORMANCE_SUT_PORT"]),
    a2a_public_url=__import__("os").environ["CONFORMANCE_SUT_URL"],
    a2a_bearer_token=__import__("os").environ.get("A2A_AUTH_TOKEN", "test-token"),
)
app = app_module.create_app(settings)
uvicorn.run(app, host="127.0.0.1", port=settings.a2a_port, log_level="warning")
PY
  sut_pid="$!"

  for _ in $(seq 1 50); do
    if curl -fsS "${sut_url}/.well-known/agent-card.json" >"${output_dir}/agent-card.json"; then
      if curl -fsS -H "Authorization: Bearer ${A2A_AUTH_TOKEN:-test-token}" "${sut_url}/health" \
        >"${output_dir}/health.json"; then
        break
      fi
    fi
    sleep 0.2
  done

  if [[ ! -f "${output_dir}/agent-card.json" || ! -f "${output_dir}/health.json" ]]; then
    echo "SUT did not become ready at ${sut_url}" >&2
    cat "${sut_log}" >&2 || true
    exit 1
  fi
else
  curl -fsS "${sut_url}/.well-known/agent-card.json" >"${output_dir}/agent-card.json"
fi

json_report_name="pytest-${category}.json"

set +e
(
  cd "${tck_dir}"
  CONFORMANCE_CATEGORY="${category}" \
  CONFORMANCE_SUT_URL="${sut_url}" \
  CONFORMANCE_JSON_REPORT_NAME="${json_report_name}" \
  CONFORMANCE_TRANSPORT_STRATEGY="${transport_strategy}" \
  CONFORMANCE_TRANSPORTS="${transports}" \
  uv run python - <<'PY'
from __future__ import annotations

import os
import run_tck

raise SystemExit(
    run_tck.run_test_category(
        category=os.environ["CONFORMANCE_CATEGORY"],
        sut_url=os.environ["CONFORMANCE_SUT_URL"],
        verbose=False,
        verbose_log=True,
        generate_report=False,
        json_report=os.environ["CONFORMANCE_JSON_REPORT_NAME"],
        transport_strategy=os.environ["CONFORMANCE_TRANSPORT_STRATEGY"],
        enable_equivalence_testing=None,
        transports=os.environ["CONFORMANCE_TRANSPORTS"],
    )
)
PY
) 2>&1 | tee "${tck_log}"
tck_exit="${PIPESTATUS[0]}"
set -e

report_path="${tck_dir}/reports/${json_report_name}"
if [[ -f "${report_path}" ]]; then
  cp "${report_path}" "${output_dir}/pytest-report.json"
fi

CONFORMANCE_CATEGORY="${category}" \
CONFORMANCE_OUTPUT_DIR="${output_dir}" \
CONFORMANCE_SUT_URL="${sut_url}" \
CONFORMANCE_TCK_DIR="${tck_dir}" \
CONFORMANCE_TCK_REF="${tck_ref}" \
CONFORMANCE_TRANSPORTS="${transports}" \
CONFORMANCE_TRANSPORT_STRATEGY="${transport_strategy}" \
uv run python - <<'PY'
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

output_dir = Path(os.environ["CONFORMANCE_OUTPUT_DIR"])
report_path = output_dir / "pytest-report.json"

metadata = {
    "category": os.environ["CONFORMANCE_CATEGORY"],
    "sut_url": os.environ["CONFORMANCE_SUT_URL"],
    "tck_dir": os.environ["CONFORMANCE_TCK_DIR"],
    "tck_ref": os.environ["CONFORMANCE_TCK_REF"],
    "transports": os.environ["CONFORMANCE_TRANSPORTS"],
    "transport_strategy": os.environ["CONFORMANCE_TRANSPORT_STRATEGY"],
    "repo_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
    "tck_commit": subprocess.check_output(
        ["git", "-C", os.environ["CONFORMANCE_TCK_DIR"], "rev-parse", "HEAD"],
        text=True,
    ).strip(),
}

(output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")

if report_path.exists():
    report = json.loads(report_path.read_text())
    failures = []
    for test in report.get("tests", []):
        outcome = test.get("outcome")
        if outcome in {"failed", "error"}:
            failures.append(
                {
                    "nodeid": test.get("nodeid"),
                    "outcome": outcome,
                    "keywords": sorted(test.get("keywords", [])),
                }
            )
    (output_dir / "failed-tests.json").write_text(json.dumps(failures, indent=2) + "\n")
PY

echo "Conformance artifacts: ${output_dir}"
echo "TCK log: ${tck_log}"
if [[ -f "${output_dir}/pytest-report.json" ]]; then
  echo "Pytest JSON report: ${output_dir}/pytest-report.json"
fi
if [[ -f "${output_dir}/failed-tests.json" ]]; then
  echo "Failed tests index: ${output_dir}/failed-tests.json"
fi

exit "${tck_exit}"

#!/usr/bin/env bash
# Update the shared released opencode-a2a-server runtime.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FORCE_A2A_RELEASE_INSTALL="true" "${SCRIPT_DIR}/install_release_runtime.sh"

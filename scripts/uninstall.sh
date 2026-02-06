#!/usr/bin/env bash
# Uninstall a single OpenCode + A2A instance created by scripts/deploy.sh.
# Safety defaults:
# - dry_run=true by default (prints actions)
# - requires confirm=UNINSTALL to actually delete files/users
#
# IMPORTANT: This script never removes systemd template units
# (/etc/systemd/system/opencode@.service, opencode-a2a@.service) because they
# are shared globally across all instances.
#
# Usage:
#   ./scripts/uninstall.sh project=<name> [data_root=/data/projects] [dry_run=true|false] confirm=UNINSTALL
#
# Examples:
#   ./scripts/uninstall.sh project=alpha confirm=UNINSTALL
#   ./scripts/uninstall.sh project=alpha dry_run=false confirm=UNINSTALL
set -euo pipefail

PROJECT_NAME=""
DATA_ROOT_INPUT=""
DRY_RUN_INPUT="true"
CONFIRM_INPUT=""

for arg in "$@"; do
  if [[ "$arg" == *=* ]]; then
    key="${arg%%=*}"
    value="${arg#*=}"
  else
    echo "Unknown argument format: $arg (expected key=value)" >&2
    exit 1
  fi

  case "${key,,}" in
    project|project_name)
      PROJECT_NAME="$value"
      ;;
    data_root)
      DATA_ROOT_INPUT="$value"
      ;;
    dry_run)
      DRY_RUN_INPUT="$value"
      ;;
    confirm)
      CONFIRM_INPUT="$value"
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      exit 1
      ;;
  esac
done

if [[ -z "$PROJECT_NAME" ]]; then
  echo "Usage: $0 project=<name> [data_root=/data/projects] [dry_run=true|false] confirm=UNINSTALL" >&2
  exit 1
fi

DATA_ROOT="${DATA_ROOT_INPUT:-${DATA_ROOT:-/data/projects}}"
PROJECT_DIR="${DATA_ROOT}/${PROJECT_NAME}"

is_truthy() {
  case "${1,,}" in
    1|true|yes|on) return 0 ;;
    *) return 1 ;;
  esac
}

DRY_RUN="true"
if [[ -n "$DRY_RUN_INPUT" ]] && ! is_truthy "$DRY_RUN_INPUT"; then
  DRY_RUN="false"
fi

if [[ "$DRY_RUN" != "true" ]]; then
  if [[ "${CONFIRM_INPUT}" != "UNINSTALL" ]]; then
    echo "Refusing to run destructive actions without confirm=UNINSTALL." >&2
    echo "Tip: run with dry_run=true first (default) to preview." >&2
    exit 1
  fi
fi

run() {
  # Print commands for auditability.
  echo "+ $*"
  if [[ "$DRY_RUN" == "true" ]]; then
    return 0
  fi
  "$@"
}

echo "Project: ${PROJECT_NAME}"
echo "DATA_ROOT: ${DATA_ROOT}"
echo "Project dir: ${PROJECT_DIR}"
echo "Dry run: ${DRY_RUN}"
echo "Note: systemd template units will NOT be removed."

UNIT_OPENCODE="opencode@${PROJECT_NAME}.service"
UNIT_A2A="opencode-a2a@${PROJECT_NAME}.service"

if command -v systemctl >/dev/null 2>&1; then
  # Stop/disable instance units (idempotent).
  run sudo systemctl disable --now "$UNIT_A2A" "$UNIT_OPENCODE" || true
  run sudo systemctl reset-failed "$UNIT_A2A" "$UNIT_OPENCODE" || true
else
  echo "systemctl not found; skipping systemd unit disable/stop." >&2
fi

# Remove project directory.
if [[ -e "$PROJECT_DIR" ]]; then
  run sudo rm -rf --one-file-system "$PROJECT_DIR"
else
  echo "Project dir not found; skipping: ${PROJECT_DIR}"
fi

# Remove project user and group.
if id "$PROJECT_NAME" &>/dev/null; then
  if command -v userdel >/dev/null 2>&1; then
    run sudo userdel "$PROJECT_NAME" || true
  elif command -v deluser >/dev/null 2>&1; then
    run sudo deluser "$PROJECT_NAME" || true
  else
    echo "Neither userdel nor deluser found; cannot remove user ${PROJECT_NAME} automatically." >&2
  fi
else
  echo "User not found; skipping: ${PROJECT_NAME}"
fi

if getent group "$PROJECT_NAME" >/dev/null 2>&1; then
  if command -v groupdel >/dev/null 2>&1; then
    run sudo groupdel "$PROJECT_NAME" || true
  elif command -v delgroup >/dev/null 2>&1; then
    run sudo delgroup "$PROJECT_NAME" || true
  else
    echo "Neither groupdel nor delgroup found; cannot remove group ${PROJECT_NAME} automatically." >&2
  fi
else
  echo "Group not found; skipping: ${PROJECT_NAME}"
fi

echo "Uninstall completed."


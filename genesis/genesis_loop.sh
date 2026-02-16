#!/usr/bin/env bash
set -euo pipefail

USER_LABEL="${1:-}"
INTERVAL="${GENESIS_INTERVAL:-1800}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
STOP_FILE="$SCRIPT_DIR/STOP"
LAUNCHER="$ROOT_DIR/run_forensics.sh"

if [[ -z "$USER_LABEL" ]]; then
  echo "Usage: $0 <house|fam>"
  exit 1
fi

if [[ "$USER_LABEL" != "house" && "$USER_LABEL" != "fam" ]]; then
  echo "Invalid user label: $USER_LABEL"
  exit 1
fi

CHOICE="12"
if [[ "$USER_LABEL" == "fam" ]]; then
  CHOICE="32"
fi

rm -f "$STOP_FILE" || true

echo "Genesis loop starting for $USER_LABEL. Interval: ${INTERVAL}s"

echo "Create $STOP_FILE to stop."

while true; do
  if [[ -f "$STOP_FILE" ]]; then
    echo "Genesis loop stopped."
    exit 0
  fi
  "$LAUNCHER" --choice "$CHOICE"
  sleep "$INTERVAL"
done

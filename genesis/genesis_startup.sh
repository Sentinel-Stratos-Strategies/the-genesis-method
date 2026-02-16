#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$ROOT_DIR/forensics_out/_logs"
BOOT_LOG="$LOG_DIR/genesis_startup.log"
TARGET_USER="${1:-house}"

mkdir -p "$LOG_DIR"
touch "$BOOT_LOG"

log_line() {
  printf "[%s] %s\n" "$(date '+%Y-%m-%d %H:%M:%S')" "$1" >>"$BOOT_LOG"
}

start_if_not_running() {
  local name="$1"
  local cmd="$2"
  if pgrep -f "$name" >/dev/null 2>&1; then
    log_line "already running: $name"
    return 0
  fi
  nohup bash -lc "$cmd" >>"$BOOT_LOG" 2>&1 &
  log_line "started: $name"
}

log_line "startup begin (target=$TARGET_USER)"
start_if_not_running "forensics_webui.py" "\"$ROOT_DIR/run_forensics.sh\" --choice 90"

if [[ "${GENESIS_START_LOOP:-1}" == "1" ]]; then
  start_if_not_running "genesis_loop.sh $TARGET_USER" "\"$ROOT_DIR/genesis/genesis_loop.sh\" \"$TARGET_USER\""
fi

log_line "startup end"

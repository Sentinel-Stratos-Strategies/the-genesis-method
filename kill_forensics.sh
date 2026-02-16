#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-all}"

kill_webui() {
  pkill -f "forensics_webui.py" >/dev/null 2>&1 || true
}

kill_gui() {
  pkill -f "forensics_gui.py" >/dev/null 2>&1 || true
}

case "$MODE" in
  webui) kill_webui ;;
  gui) kill_gui ;;
  all) kill_webui; kill_gui ;;
  *)
    echo "Usage: $0 [webui|gui|all]"
    exit 1
    ;;
esac

echo "Kill card executed: $MODE"

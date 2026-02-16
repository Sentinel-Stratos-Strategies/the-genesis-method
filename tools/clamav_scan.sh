#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-quick}"
TARGET="${2:-}"

if ! command -v clamscan >/dev/null 2>&1; then
  echo "clamscan not found. Install with: brew install clamav"
  exit 1
fi

if [[ -z "$TARGET" ]]; then
  echo "Usage: $0 [quick|full|path] <target-path>"
  exit 1
fi

OUT_DIR="$TARGET"
REPORT_DIR="$TARGET/_ClamAV"
mkdir -p "$REPORT_DIR"
STAMP=$(date +"%Y%m%d_%H%M%S")
REPORT="$REPORT_DIR/clamav_${MODE}_${STAMP}.log"

if [[ "$MODE" == "quick" ]]; then
  clamscan -r --infected --no-summary "$OUT_DIR" | tee "$REPORT"
elif [[ "$MODE" == "full" ]]; then
  clamscan -r --bell --log="$REPORT" "$OUT_DIR"
elif [[ "$MODE" == "path" ]]; then
  clamscan -r --log="$REPORT" "$OUT_DIR"
else
  echo "Unknown mode: $MODE"
  exit 1
fi

echo "ClamAV report: $REPORT"

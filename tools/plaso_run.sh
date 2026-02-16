#!/usr/bin/env bash
set -euo pipefail

INPUT="${1:-}"
OUTPUT_DIR="${2:-}"

if [[ -z "$INPUT" || -z "$OUTPUT_DIR" ]]; then
  echo "Usage: $0 <input-path> <output-dir>"
  exit 1
fi

mkdir -p "$OUTPUT_DIR"
STAMP=$(date +"%Y%m%d_%H%M%S")
OUTFILE="$OUTPUT_DIR/plaso_${STAMP}.plaso"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker not found. Install Docker Desktop."
  exit 1
fi

# Use official plaso image

docker run --rm -v "$INPUT":/evidence -v "$OUTPUT_DIR":/out log2timeline/plaso \
  log2timeline.py /out/$(basename "$OUTFILE") /evidence

echo "Plaso output: $OUTFILE"

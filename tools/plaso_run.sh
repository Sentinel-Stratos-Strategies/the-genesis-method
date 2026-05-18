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

# Official Docker Hub image is linux/amd64 ONLY. On OrbStack / Apple Silicon (linux/arm64),
# Docker runs it under QEMU emulation → startup + parsing are MUCH slower than native x86.
# This is expected; do not kill the container unless it sits at 0% CPU for a long time.
PLASO_IMAGE="${PLASO_IMAGE:-log2timeline/plaso:latest}"
DOCKER_PLATFORM="${PLASO_DOCKER_PLATFORM:-linux/amd64}"

echo "=== Genesis Plaso (Docker) ===" >&2
echo "Image: ${PLASO_IMAGE}  platform: ${DOCKER_PLATFORM}" >&2
echo "On Apple Silicon this uses CPU emulation — first lines of log may pause while artifact defs load." >&2

# Plaso CLI: --storage-file then SOURCE (see https://plaso.readthedocs.io/en/latest/sources/user/Installing-with-docker.html )
docker run --rm \
  --platform "${DOCKER_PLATFORM}" \
  -v "$INPUT":/evidence:ro \
  -v "$OUTPUT_DIR":/out \
  "${PLASO_IMAGE}" \
  log2timeline.py --storage-file "/out/$(basename "$OUTFILE")" /evidence

echo "Plaso output: $OUTFILE"

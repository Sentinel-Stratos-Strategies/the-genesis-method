#!/usr/bin/env bash
set -euo pipefail
# Sysdiagnose Analysis Framework (EC-DIGIT-CSIRC) — vendored under tools/sysdiagnose
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SD_VENV="$ROOT_DIR/tools/sysdiagnose/.venv/bin/sysdiag"
if [[ ! -x "$SD_VENV" ]]; then
  echo "Missing $SD_VENV — run: cd $ROOT_DIR/tools/sysdiagnose && python3.12 -m venv .venv && .venv/bin/pip install ." >&2
  exit 1
fi
export SYSDIAGNOSE_CASES_PATH="${SYSDIAGNOSE_CASES_PATH:-$ROOT_DIR/forensics_out/sysdiagnose_cases}"
export MAGIC="${MAGIC:-/Volumes/Stratos_Tools/homebrew/share/misc/magic.mgc}"
mkdir -p "$SYSDIAGNOSE_CASES_PATH"
exec "$SD_VENV" "$@"

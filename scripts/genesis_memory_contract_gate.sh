#!/usr/bin/env bash
# Runs during macOS app launch / install to snapshot memory-contract artifacts onto SENTINEL.
# Does not block Genesis if Node tooling or runtime dirs are missing (set STRICT=1 to fail).

set -uo pipefail

GENESIS_ROOT="${GENESIS_ROOT:-}"
if [[ -z "$GENESIS_ROOT" ]]; then
  GENESIS_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
fi

STRICT="${STRICT:-0}"
SNAP_BASE="${GENESIS_MEMORY_CONTRACT_SNAPSHOT:-/Volumes/SENTINEL/GENESIS_EVIDENCE_OUTPUT/memory_contract_snapshots}"
TS="$(date +%Y%m%dT%H%M%S)"
LOG="$SNAP_BASE/gate_${TS}.log"

mkdir -p "$SNAP_BASE"

_memory_contract_root() {
  if [[ -n "${MEMORY_CONTRACT_ROOT:-}" ]]; then
    printf '%s\n' "$MEMORY_CONTRACT_ROOT"
    return 0
  fi
  local j="$GENESIS_ROOT/config/genesis_paths.json"
  if [[ -f "$j" ]] && command -v python3 >/dev/null 2>&1; then
    python3 - <<PY
import json
from pathlib import Path
p = Path("$j")
try:
    v = json.loads(p.read_text(encoding="utf-8")).get("memory_contract_root", "")
    print(v or "", end="")
except Exception:
    print("", end="")
PY
    return 0
  fi
  printf '%s\n' "$GENESIS_ROOT/../GENESIS_OS-current/contracts/memory-contract"
}

MC="$(_memory_contract_root)"
MC="$(cd "$MC" 2>/dev/null && pwd || true)"

{
  echo "=== Genesis memory-contract gate $TS ==="
  echo "GENESIS_ROOT=$GENESIS_ROOT"
  echo "MEMORY_CONTRACT_ROOT=$MC"

  if [[ ! -d "$MC" ]]; then
    echo "WARN: memory-contract directory not found. Set MEMORY_CONTRACT_ROOT or genesis_paths.json memory_contract_root."
    [[ "$STRICT" == "1" ]] && exit 2
    exit 0
  fi

  FILES=(
    "manifest/memory_manifest.yaml"
    "manifest/routing_manifest.yaml"
    "manifest/tenant_manifest.yaml"
    "control_plane/registries/routing_registry.v1.json"
    "control_plane/registries/tenant_registry.v1.json"
    "docs/MEMORY_CONTRACT.md"
  )

  DST="$SNAP_BASE/$TS"
  mkdir -p "$DST"
  ok=0
  miss=0
  for rel in "${FILES[@]}"; do
    src="$MC/$rel"
    if [[ -f "$src" ]]; then
      install -d "$DST/$(dirname "$rel")"
      cp "$src" "$DST/$rel"
      echo "OK copied $rel"
      ok=$((ok + 1))
    else
      echo "MISSING $rel"
      miss=$((miss + 1))
    fi
  done
  echo "Summary: copied=$ok missing=$miss snapshot=$DST"

  if command -v node >/dev/null 2>&1 && [[ -f "$MC/package.json" ]]; then
    if [[ -d "$MC/node_modules" ]]; then
      echo "--- npm run memory:validate-ci ---"
      (cd "$MC" && npm run memory:validate-ci) || echo "WARN: memory-contract CI validators failed (non-fatal unless STRICT=1)"
    else
      echo "WARN: memory-contract has no node_modules; skipped JS validators. Run: cd \"$MC\" && npm install && npm run memory:validate-ci"
    fi
  else
    echo "WARN: node not available or package.json missing; YAML snapshot still copied."
  fi

  if [[ "$miss" -gt 0 && "$STRICT" == "1" ]]; then
    exit 3
  fi
} 2>&1 | tee "$LOG"

exit 0

#!/usr/bin/env bash
# Genesis wrapper for EC-DIGIT Sysdiagnose Analysis Framework (SAF).
# Usage: sysdiagnose_saf_run.sh <evidence_input_dir> <saf_workspace_root>
#
# Discovers either a .tar.gz/.tgz sysdiagnose archive or an unpacked folder
# containing sysdiagnose.log, runs `sysdiag create`, then `sysdiag -c <id> parse all`.
# Case database lives under <saf_workspace_root>/cases (SYSDIAGNOSE_CASES_PATH).

set -euo pipefail

INPUT_DIR="$(cd "${1:?evidence input dir}" && pwd)"
SAF_ROOT="$(mkdir -p "${2:?saf workspace}" && cd "$2" && pwd)"

REPO_TOOLS="$(cd "$(dirname "$0")" && pwd)"
SAF_SRC="$REPO_TOOLS/sysdiagnose"
SYSDIAG="$SAF_SRC/.venv/bin/sysdiag"

if [[ ! -x "$SYSDIAG" ]]; then
  echo "genesis_saf: missing executable: $SYSDIAG" >&2
  exit 2
fi

export SYSDIAGNOSE_CASES_PATH="$SAF_ROOT/cases"
mkdir -p "$SYSDIAGNOSE_CASES_PATH"

SOURCE=""
while IFS= read -r logf; do
  [[ -n "$logf" ]] || continue
  candidate="$(dirname "$logf")"
  base="$(basename "$candidate")"
  if [[ "$base" == sysdiagnose* ]]; then
    SOURCE="$candidate"
    break
  fi
done < <(find "$INPUT_DIR" -name sysdiagnose.log -print 2>/dev/null | sort)

if [[ -z "$SOURCE" ]]; then
  while IFS= read -r -d '' f; do
    SOURCE="$f"
    break
  done < <(find "$INPUT_DIR" \( -iname 'sysdiagnose*.tar.gz' -o -iname 'sysdiagnose*.tgz' \) -print0 2>/dev/null)
fi

if [[ -z "${SOURCE:-}" ]]; then
  echo "genesis_saf: no sysdiagnose archive (.tar.gz/.tgz) or unpacked tree with sysdiagnose.log under:" >&2
  echo "  $INPUT_DIR" >&2
  exit 3
fi

echo "[*] SAF source: $SOURCE"
echo "[*] Cases path: $SYSDIAGNOSE_CASES_PATH"

cd "$SAF_SRC"
OUT_CREATE="$("$SYSDIAG" create "$SOURCE" --force 2>&1)"
printf '%s\n' "$OUT_CREATE"

CASE_ID=""
if [[ "$OUT_CREATE" =~ Case\ \'([^\']+)\'\ created\ successfully ]]; then
  CASE_ID="${BASH_REMATCH[1]}"
fi

if [[ -z "$CASE_ID" ]]; then
  CASE_ID="$(SYSDIAGNOSE_CASES_PATH="$SYSDIAGNOSE_CASES_PATH" python3 - <<'PY'
import json
import os
import pathlib

root = pathlib.Path(os.environ["SYSDIAGNOSE_CASES_PATH"])
cf = root / "cases.json"
if not cf.exists():
    raise SystemExit("")
data = json.loads(cf.read_text(encoding="utf-8"))
best = None
best_t = -1.0
for cid in data:
    ddir = root / cid / "data"
    if not ddir.is_dir():
        continue
    times = [p.stat().st_mtime for p in ddir.rglob("*") if p.is_file()]
    t = max(times) if times else 0.0
    if t >= best_t:
        best_t = t
        best = cid
print(best or "")
PY
)"
fi

if [[ -z "$CASE_ID" ]]; then
  echo "genesis_saf: could not determine SAF case id; inspect output above." >&2
  exit 4
fi

echo "[*] Parsing SAF case: $CASE_ID"
"$SYSDIAG" -c "$CASE_ID" parse all

echo "[*] Done. Parsed artifacts: $SYSDIAGNOSE_CASES_PATH/$CASE_ID/parsed_data"

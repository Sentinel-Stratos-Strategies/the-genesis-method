#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
PY_MAIN="${PY_MAIN:-/usr/local/bin/python3}"
PY_ILEAPP="${PY_ILEAPP:-$ROOT_DIR/iLeap/iLEAPP/.venv/bin/python}"

# Load optional local env so GUI/WebUI-launched runs can still read API keys.
ENV_FILE="${GENESIS_ENV_FILE:-$ROOT_DIR/.env}"
PRESET_OPENAI_API_KEY="${OPENAI_API_KEY:-}"
PRESET_GENESIS_MODEL="${GENESIS_MODEL:-}"
is_placeholder_secret() {
  local v="$1"
  [[ -z "$v" ]] && return 0
  [[ "$v" == "your-api-key-here" ]] && return 0
  [[ "$v" == "replace-with-real-key" ]] && return 0
  [[ "$v" == your-api-key* ]] && return 0
  [[ "$v" == sk-proj-replace-with-real-key* ]] && return 0
  return 1
}
if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  set -a
  source "$ENV_FILE"
  set +a
fi
if [[ -n "$PRESET_OPENAI_API_KEY" ]] && ! is_placeholder_secret "$PRESET_OPENAI_API_KEY"; then
  OPENAI_API_KEY="$PRESET_OPENAI_API_KEY"
fi
if [[ -n "$PRESET_GENESIS_MODEL" ]]; then
  GENESIS_MODEL="$PRESET_GENESIS_MODEL"
fi

TOOLS_DIR="$ROOT_DIR/tools"
PROFILES_DIR="$ROOT_DIR/profiles"
OUT_DIR_HOUSE="${OUT_DIR_HOUSE:-/Users/House/EVIDENCE}"
PROJECT_NAME="$(basename "$ROOT_DIR")"
FAM_ROOT_BASE="${GENESIS_FAM_ROOT:-}"
if [[ -z "$FAM_ROOT_BASE" ]]; then
  if [[ -d "/Users/fam/Tools/$PROJECT_NAME" ]]; then
    FAM_ROOT_BASE="/Users/fam/Tools/$PROJECT_NAME"
  elif [[ -d "/Users/fam/$PROJECT_NAME" ]]; then
    FAM_ROOT_BASE="/Users/fam/$PROJECT_NAME"
  else
    FAM_ROOT_BASE="/Users/fam"
  fi
fi
OUT_DIR_FAM="${OUT_DIR_FAM:-$FAM_ROOT_BASE/forensics_out}"
LOG_DIR="$OUT_DIR_HOUSE/_logs"
LAST_OUTPUT_HOUSE="$ROOT_DIR/last_output_house.txt"
LAST_OUTPUT_FAM="$ROOT_DIR/last_output_fam.txt"

HOUSE_USER_PATH="/Users/house"
FAM_USER_PATH="/Users/fam"

HOUSE_IOS_INPUT="${HOUSE_ILEAPP_INPUT:-$ROOT_DIR/inputs/house}"
FAM_IOS_INPUT="${FAM_ILEAPP_INPUT:-$ROOT_DIR/inputs/fam}"
HOUSE_ILEAPP_TYPE="${HOUSE_ILEAPP_TYPE:-fs}"
FAM_ILEAPP_TYPE="${FAM_ILEAPP_TYPE:-fs}"

HOUSE_XLEAPP_INPUT="${HOUSE_XLEAPP_INPUT:-$ROOT_DIR/inputs/house}"
FAM_XLEAPP_INPUT="${FAM_XLEAPP_INPUT:-$ROOT_DIR/inputs/fam}"

HOUSE_INPUT_FILE="$ROOT_DIR/inputs/house_path.txt"
FAM_INPUT_FILE="$ROOT_DIR/inputs/fam_path.txt"

if [[ ! -x "$PY_MAIN" ]]; then
  PY_MAIN="$(command -v python3 || true)"
fi
if [[ -z "$PY_MAIN" ]]; then
  echo "python3 is required but was not found in PATH."
  exit 1
fi

mkdir -p "$OUT_DIR_HOUSE" "$OUT_DIR_FAM" "$LOG_DIR" "$HOUSE_IOS_INPUT" "$FAM_IOS_INPUT"

migrate_old_root_path() {
  local path_in="$1"
  if [[ "$path_in" == "/Users/house/Tools/hunting"* ]]; then
    echo "${path_in/\/Users\/house\/Tools\/hunting/$ROOT_DIR}"
    return
  fi
  echo "$path_in"
}

if [[ -f "$HOUSE_INPUT_FILE" ]]; then
  HOUSE_IOS_INPUT=$(migrate_old_root_path "$(cat "$HOUSE_INPUT_FILE")")
  HOUSE_XLEAPP_INPUT="$HOUSE_IOS_INPUT"
fi
if [[ -f "$FAM_INPUT_FILE" ]]; then
  FAM_IOS_INPUT=$(migrate_old_root_path "$(cat "$FAM_INPUT_FILE")")
  FAM_XLEAPP_INPUT="$FAM_IOS_INPUT"
fi

# Tool paths
ILEAPP_DIR="$ROOT_DIR/iLeap/iLEAPP"
XLEAPP_BIN="$TOOLS_DIR/xleapp_311/.venv/bin/xleapp"
XLEAPP_VENV_PY="$TOOLS_DIR/xleapp_311/.venv/bin/python"
XLEAPP_PLUGIN_PKG="${XLEAPP_PLUGIN_PKG:-xleapp-ios}"
MACAPT_BIN="$TOOLS_DIR/mac_apt/.venv/bin/python"
MACAPT_SCRIPT="$TOOLS_DIR/mac_apt-master/mac_apt.py"
MACAPT_TIMELINE="$TOOLS_DIR/macapt_timeline.py"
SUMMARY_SCRIPT="$TOOLS_DIR/summary_scan.py"
IDENTIFIERS_SCRIPT="$TOOLS_DIR/identifiers_scan.py"
HASH_SCRIPT="$TOOLS_DIR/hash_manifest.py"
SIGMA_RULES_DIR="$ROOT_DIR/rules/sigma"
YARA_RULES_FILE="$ROOT_DIR/rules/yara/sentinel_rules.yar"
SIGMA_SCRIPT="$TOOLS_DIR/sigma_scan.py"
YARA_SCRIPT="$TOOLS_DIR/yara_scan.py"
CLAMAV_SCRIPT="$TOOLS_DIR/clamav_scan.sh"
GENESIS_AGENT_SCRIPT="$TOOLS_DIR/genesis_agent.py"
PLUGIN_RUNNER="$TOOLS_DIR/plugin_runner.py"
PLUGIN_DIR="$ROOT_DIR/plugins"
CASE_DB="$ROOT_DIR/case.db"
CASE_DB_SCRIPT="$TOOLS_DIR/case_db.py"
IOC_ENRICH_SCRIPT="$TOOLS_DIR/ioc_enrich.py"
MERGE_TIMELINE_SCRIPT="$TOOLS_DIR/merge_timelines.py"
REPORT_SCRIPT="$TOOLS_DIR/build_report.py"
PLASO_SCRIPT="$TOOLS_DIR/plaso_run.sh"
TIMESKETCH_SCRIPT="$TOOLS_DIR/timesketch_start.sh"

# Profiles
ILEAPP_PROFILE="$PROFILES_DIR/ileapp_social_calls_snapchat.ilprofile"
MACAPT_CORE_PROFILE="$PROFILES_DIR/macapt_macos_core.txt"
MACAPT_COMMS_PROFILE="$PROFILES_DIR/macapt_macos_comms.txt"
MACAPT_SECURITY_PROFILE="$PROFILES_DIR/macapt_macos_security.txt"

print_header() {
  echo ""
  echo "========================================"
  echo "$1"
  echo "========================================"
}

check_exists() {
  local path="$1"
  if [[ ! -e "$path" ]]; then
    echo "Missing: $path"
    return 1
  fi
}

record_output() {
  local user_label="$1"
  local out="$2"
  local target="$LAST_OUTPUT_HOUSE"
  if [[ "$user_label" == "fam" ]]; then
    target="$LAST_OUTPUT_FAM"
  fi
  printf "%s\n" "$out" > "$target" || true
}

open_report_if_exists() {
  local path="$1"
  if [[ -e "$path" ]]; then
    open "$path" >/dev/null 2>&1 || true
  fi
}

post_process_output() {
  local out="$1"
  if [[ -x "$PY_MAIN" && -e "$SUMMARY_SCRIPT" ]]; then
    "$PY_MAIN" "$SUMMARY_SCRIPT" --output-dir "$out" >/dev/null 2>&1 || true
  fi
  if [[ -x "$PY_MAIN" && -e "$IDENTIFIERS_SCRIPT" ]]; then
    "$PY_MAIN" "$IDENTIFIERS_SCRIPT" --output-dir "$out" >/dev/null 2>&1 || true
  fi
  if [[ -x "$PY_MAIN" && -e "$HASH_SCRIPT" ]]; then
    "$PY_MAIN" "$HASH_SCRIPT" --output-dir "$out" >/dev/null 2>&1 || true
  fi
  if [[ -x "$PY_MAIN" && -e "$SIGMA_SCRIPT" && -d "$SIGMA_RULES_DIR" ]]; then
    "$PY_MAIN" "$SIGMA_SCRIPT" --output-dir "$out" --rules-dir "$SIGMA_RULES_DIR" >/dev/null 2>&1 || true
  fi
  if [[ -x "$PY_MAIN" && -e "$YARA_SCRIPT" && -e "$YARA_RULES_FILE" ]]; then
    "$PY_MAIN" "$YARA_SCRIPT" --output-dir "$out" --rules "$YARA_RULES_FILE" >/dev/null 2>&1 || true
  fi
  if [[ -x "$PY_MAIN" && -e "$IOC_ENRICH_SCRIPT" ]]; then
    "$PY_MAIN" "$IOC_ENRICH_SCRIPT" --output-dir "$out" >/dev/null 2>&1 || true
  fi
  if [[ -x "$PY_MAIN" && -e "$PLUGIN_RUNNER" && -d "$PLUGIN_DIR" ]]; then
    "$PY_MAIN" "$PLUGIN_RUNNER" --output-dir "$out" --plugin-dir "$PLUGIN_DIR" --context "post_process" >/dev/null 2>&1 || true
  fi
}

menu() {
  cat <<'MENU'
Choose a task:

House Section (/Users/house):
  1) macOS core (mac_apt)
  2) macOS comms (mac_apt)
  3) macOS security/malware (mac_apt)
  4) iLEAPP profile
  5) xLEAPP iOS core
  6) Open latest iLEAPP report (house)
  7) Open latest mac_apt output (house)
  8) Export latest iLEAPP timeline (house)
  9) Export latest mac_apt timeline (house)
  10) Full run (core + comms + security + iOS)
  11) Purge outputs (house)
  12) Full run + report (house)
  13) Generate report (house)
  14) Merge timelines (house)
  15) YARA scan latest (house)
  16) Sigma scan latest (house)
  17) ClamAV quick scan latest (house)
  18) ClamAV full scan latest (house)
  19) Plaso run (house)
  20) Genesis Analyst (OpenAI) (house)

Fam Section (/Users/fam):
  21) macOS core (mac_apt)
  22) macOS comms (mac_apt)
  23) macOS security/malware (mac_apt)
  24) iLEAPP profile
  25) xLEAPP iOS core
  26) Open latest iLEAPP report (fam)
  27) Open latest mac_apt output (fam)
  28) Export latest iLEAPP timeline (fam)
  29) Export latest mac_apt timeline (fam)
  30) Full run (core + comms + security + iOS)
  31) Purge outputs (fam)
  32) Full run + report (fam)
  33) Generate report (fam)
  34) Merge timelines (fam)
  35) YARA scan latest (fam)
  36) Sigma scan latest (fam)
  37) ClamAV quick scan latest (fam)
  38) ClamAV full scan latest (fam)
  39) Plaso run (fam)
  40) Genesis Analyst (OpenAI) (fam)

Common:
  90) Start Web UI (local)
  91) Start GUI (local)
  92) Start Timesketch (docker)
  93) Genesis Analyst (house + fam consolidated)
  99) Quit
MENU
}

latest_dir() {
  local glob="$1"
  ls -1dt $glob 2>/dev/null | head -1
}

xleapp_plugin_count() {
  if [[ ! -x "$XLEAPP_VENV_PY" ]]; then
    echo "0"
    return
  fi
  "$XLEAPP_VENV_PY" - <<'PY'
import importlib.metadata as m
try:
    eps = m.entry_points()
    if hasattr(eps, "select"):
        group = eps.select(group="xleapp.plugins")
    else:
        group = eps.get("xleapp.plugins", [])
    print(len(list(group)))
except Exception:
    print(0)
PY
}

ensure_xleapp_plugins() {
  local count
  count=$(xleapp_plugin_count)
  if [[ "$count" -ge 1 ]]; then
    return 0
  fi

  print_header "xLEAPP plugins missing - installing $XLEAPP_PLUGIN_PKG"
  if [[ ! -x "$XLEAPP_VENV_PY" ]]; then
    echo "Missing xLEAPP python env: $XLEAPP_VENV_PY"
    return 1
  fi

  "$XLEAPP_VENV_PY" -m pip install --upgrade "$XLEAPP_PLUGIN_PKG" || {
    echo "Failed to install xLEAPP plugin package: $XLEAPP_PLUGIN_PKG"
    return 1
  }

  count=$(xleapp_plugin_count)
  if [[ "$count" -lt 1 ]]; then
    echo "xLEAPP plugin install did not register entry points."
    return 1
  fi
  echo "xLEAPP plugins ready (count=$count)"
}

ensure_xleapp_parser_shim() {
  if [[ ! -x "$XLEAPP_VENV_PY" ]]; then
    return 0
  fi
  "$XLEAPP_VENV_PY" - <<'PY' || true
import importlib.util
from pathlib import Path
import sys

try:
    import astc_decomp  # noqa: F401
    print("xLEAPP ASTC parser is available.")
    raise SystemExit(0)
except Exception:
    pass

spec = importlib.util.find_spec("xleapp_ios.helpers.parsers")
if not spec or not spec.origin:
    print("xLEAPP parser package not found; skipping ASTC shim.")
    raise SystemExit(0)

target = Path(spec.origin)
content = target.read_text(encoding="utf-8")
if "GENESIS_ASTC_FALLBACK" in content:
    print("xLEAPP ASTC fallback already installed.")
    raise SystemExit(0)

shim = """# GENESIS_ASTC_FALLBACK
import types

# import the protobuf-decoder module
import blackboxprotobuf as pbparser

# import the ccl parser
import xleapp_ios.helpers.parsers.ccl.ccl_bplist as cclparser

# import the ktx parser (optional dependency on astc_decomp)
try:
    import xleapp_ios.helpers.parsers.ktx.ios_ktx2png as ktxparser
except Exception:
    class _MissingKTXReader:
        def __init__(self):
            self.error_message = (
                "KTX parser unavailable (missing optional dependency: astc_decomp)"
            )

        def validate_header(self, _f):
            return False

        def get_uncompressed_texture_data(self, _f):
            raise ValueError(self.error_message)

    class _MissingLibLzfse:
        class error(Exception):
            pass

    ktxparser = types.SimpleNamespace(
        KTX_reader=_MissingKTXReader,
        liblzfse=_MissingLibLzfse(),
    )
"""
target.write_text(shim, encoding="utf-8")
print(f"Installed xLEAPP ASTC fallback shim: {target}")
PY
}

ensure_xleapp_scandir_shim() {
  if [[ ! -x "$XLEAPP_VENV_PY" ]]; then
    return 0
  fi
  "$XLEAPP_VENV_PY" - <<'PY' || true
import importlib.util
from pathlib import Path

spec = importlib.util.find_spec("xleapp.helpers.search")
if not spec or not spec.origin:
    print("xLEAPP search module not found; skipping scandir shim.")
    raise SystemExit(0)

target = Path(spec.origin)
content = target.read_text(encoding="utf-8")
if "GENESIS_SKIP_SCANDIR_ERRORS" in content:
    print("xLEAPP scandir fallback already installed.")
    raise SystemExit(0)

old_block = """def build_files_list(self, folder):
        subfolders, files = [], []

        for item in os.scandir(folder):
            if item.is_dir():
                subfolders.append(item.path)
            if item.is_file():
                files.append(item.path)

        for folder in list(subfolders):
            sf, items = self.build_files_list(folder)
            subfolders.extend(sf)
            files.extend(items)

        return subfolders, files
"""

new_block = """def build_files_list(self, folder):
        # GENESIS_SKIP_SCANDIR_ERRORS
        subfolders, files = [], []

        try:
            iterator = os.scandir(folder)
        except OSError as ex:
            logger_log.warning(f"Skipping folder due to scan error: {folder} ({ex})")
            return subfolders, files

        with iterator:
            for item in iterator:
                try:
                    if item.is_dir(follow_symlinks=False):
                        subfolders.append(item.path)
                    if item.is_file(follow_symlinks=False):
                        files.append(item.path)
                except OSError as ex:
                    logger_log.debug(f"Skipping item due to stat error: {item.path} ({ex})")

        for child in list(subfolders):
            sf, items = self.build_files_list(child)
            subfolders.extend(sf)
            files.extend(items)

        return subfolders, files
"""

if old_block not in content:
    print("Could not patch xLEAPP search walker automatically; leaving as-is.")
    raise SystemExit(0)

updated = content.replace(old_block, new_block, 1)
target.write_text(updated, encoding="utf-8")
print(f"Installed xLEAPP scandir fallback shim: {target}")
PY
}

run_macapt_profile() {
  local user_label="$1"
  local user_path="$2"
  local profile_file="$3"
  local profile_label="$4"

  check_exists "$MACAPT_BIN"
  check_exists "$MACAPT_SCRIPT"
  check_exists "$MACAPT_TIMELINE"
  check_exists "$profile_file"

  local stamp
  stamp=$(date +"%Y%m%d_%H%M%S")
  local out_base="$OUT_DIR_HOUSE"
  if [[ "$user_label" == "fam" ]]; then
    out_base="$OUT_DIR_FAM"
  fi
  local out="$out_base/$user_label/macapt_${profile_label}_${stamp}"
  mkdir -p "$out"

  print_header "mac_apt run ($user_label): $profile_label"
  echo "Output: $out"
  echo "Using input: / (MOUNTED)"

  # shellcheck disable=SC2046
  sudo "$MACAPT_BIN" "$MACAPT_SCRIPT" MOUNTED "/" \
    $(tr '\n' ' ' < "$profile_file") \
    -o "$out" -c | tee "$LOG_DIR/macapt_${user_label}_${profile_label}_${stamp}.log"

  "$PY_MAIN" "$MACAPT_TIMELINE" --input "$out" --user-path "$user_path" || true
  post_process_output "$out"
  if [[ -x "$PY_MAIN" && -e "$CASE_DB_SCRIPT" ]]; then
    "$PY_MAIN" "$CASE_DB_SCRIPT" --db "$CASE_DB" --user "$user_label" --tool "macapt_${profile_label}" --output-dir "$out" >/dev/null 2>&1 || true
  fi
  record_output "$user_label" "$out"
  echo "Output folder: $out"
  open "$out" >/dev/null 2>&1 || true
}

run_ileapp_profile() {
  local user_label="$1"
  local input_type="$2"
  local input_path="$3"

  check_exists "$ILEAPP_DIR/ileapp.py"
  check_exists "$ILEAPP_PROFILE"

  if [[ ! -e "$input_path" ]]; then
    print_header "iLEAPP input missing"
    read -r -p "Enter input path for $user_label: " input_path
  fi
  if [[ -z "$input_path" ]]; then
    echo "Missing input path"
    return 1
  fi

  local stamp
  stamp=$(date +"%Y%m%d_%H%M%S")
  local out_base="$OUT_DIR_HOUSE"
  if [[ "$user_label" == "fam" ]]; then
    out_base="$OUT_DIR_FAM"
  fi
  local out="$out_base/$user_label/ileapp_${stamp}"
  mkdir -p "$out"

  "$PY_ILEAPP" "$ILEAPP_DIR/ileapp.py" \
    -t "$input_type" -i "$input_path" -o "$out" \
    -m "$ILEAPP_PROFILE" | tee "$LOG_DIR/ileapp_${user_label}_${stamp}.log"

  if [[ -e "$out/_Timeline/tl.db" ]]; then
    sqlite3 "$out/_Timeline/tl.db" ".mode csv" ".headers on" ".output $out/_Timeline/timeline.csv" "select * from data;" >/dev/null 2>&1 || true
  fi

  post_process_output "$out"
  if [[ -x "$PY_MAIN" && -e "$CASE_DB_SCRIPT" ]]; then
    "$PY_MAIN" "$CASE_DB_SCRIPT" --db "$CASE_DB" --user "$user_label" --tool "ileapp" --output-dir "$out" >/dev/null 2>&1 || true
  fi
  record_output "$user_label" "$out"
  echo "Output folder: $out"
  open_report_if_exists "$out/_HTML/index.html"
}

run_xleapp_core() {
  local user_label="$1"
  local input_path="$2"

  check_exists "$XLEAPP_BIN"
  ensure_xleapp_plugins
  ensure_xleapp_parser_shim
  ensure_xleapp_scandir_shim

  if [[ ! -e "$input_path" ]]; then
    print_header "xLEAPP input missing"
    read -r -p "Enter input path for $user_label: " input_path
  fi
  if [[ -z "$input_path" ]]; then
    echo "Missing input path"
    return 1
  fi

  local stamp
  stamp=$(date +"%Y%m%d_%H%M%S")
  local out_base="$OUT_DIR_HOUSE"
  if [[ "$user_label" == "fam" ]]; then
    out_base="$OUT_DIR_FAM"
  fi
  local out="$out_base/$user_label/xleapp_${stamp}"
  mkdir -p "$out"

  "$XLEAPP_BIN" -I -i "$input_path" -o "$out" --artifacts core | tee "$LOG_DIR/xleapp_${user_label}_${stamp}.log"

  if [[ -e "$out/_Timeline/tl.db" ]]; then
    sqlite3 "$out/_Timeline/tl.db" ".mode csv" ".headers on" ".output $out/_Timeline/timeline.csv" "select * from data;" >/dev/null 2>&1 || true
  fi

  post_process_output "$out"
  if [[ -x "$PY_MAIN" && -e "$CASE_DB_SCRIPT" ]]; then
    "$PY_MAIN" "$CASE_DB_SCRIPT" --db "$CASE_DB" --user "$user_label" --tool "xleapp_core" --output-dir "$out" >/dev/null 2>&1 || true
  fi
  record_output "$user_label" "$out"
  echo "Output folder: $out"
  open_report_if_exists "$out/_HTML/index.html"
}

run_full_profile() {
  local user_label="$1"
  local user_path="$2"
  print_header "Full run ($user_label): core + comms + security + iOS"
  run_macapt_profile "$user_label" "$user_path" "$MACAPT_CORE_PROFILE" "core"
  run_macapt_profile "$user_label" "$user_path" "$MACAPT_COMMS_PROFILE" "comms"
  run_macapt_profile "$user_label" "$user_path" "$MACAPT_SECURITY_PROFILE" "security"
  if [[ "$user_label" == "house" ]]; then
    run_ileapp_profile "$user_label" "$HOUSE_ILEAPP_TYPE" "$HOUSE_IOS_INPUT"
    run_xleapp_core "$user_label" "$HOUSE_XLEAPP_INPUT"
  else
    run_ileapp_profile "$user_label" "$FAM_ILEAPP_TYPE" "$FAM_IOS_INPUT"
    run_xleapp_core "$user_label" "$FAM_XLEAPP_INPUT"
  fi
}

purge_outputs() {
  local user_label="$1"
  local out_base="$OUT_DIR_HOUSE"
  if [[ "$user_label" == "fam" ]]; then
    out_base="$OUT_DIR_FAM"
  fi
  local target="$out_base/$user_label"
  echo "This will permanently delete outputs in: $target"
  read -r -p "Type DELETE to confirm: " confirm
  if [[ "$confirm" != "DELETE" ]]; then
    echo "Cancelled"
    return 1
  fi
  rm -rf "$target"
  mkdir -p "$target"
  echo "Purged: $target"
}

merge_latest_timelines() {
  local user_label="$1"
  local out_base="$OUT_DIR_HOUSE"
  if [[ "$user_label" == "fam" ]]; then
    out_base="$OUT_DIR_FAM"
  fi
  local user_root="$out_base/$user_label"
  local ileapp_latest
  local xleapp_latest
  local macapt_latest
  ileapp_latest=$(latest_dir "$user_root/ileapp_*")
  xleapp_latest=$(latest_dir "$user_root/xleapp_*")
  macapt_latest=$(latest_dir "$user_root/macapt_*")

  local inputs=()
  if [[ -n "$macapt_latest" && -e "$macapt_latest/_Timeline/macapt_timeline.csv" ]]; then
    inputs+=("$macapt_latest/_Timeline/macapt_timeline.csv")
  fi
  if [[ -n "$ileapp_latest" && -e "$ileapp_latest/_Timeline/timeline.csv" ]]; then
    inputs+=("$ileapp_latest/_Timeline/timeline.csv")
  fi
  if [[ -n "$xleapp_latest" && -e "$xleapp_latest/_Timeline/timeline.csv" ]]; then
    inputs+=("$xleapp_latest/_Timeline/timeline.csv")
  fi

  if [[ "${#inputs[@]}" -eq 0 ]]; then
    echo "No timeline CSVs found for $user_label"
    return 1
  fi

  "$PY_MAIN" "$MERGE_TIMELINE_SCRIPT" --output-dir "$user_root" --inputs "${inputs[@]}" || true
  open "$user_root/_Timeline" >/dev/null 2>&1 || true
}

generate_report() {
  local user_label="$1"
  local out_base="$OUT_DIR_HOUSE"
  if [[ "$user_label" == "fam" ]]; then
    out_base="$OUT_DIR_FAM"
  fi
  "$PY_MAIN" "$REPORT_SCRIPT" --user-label "$user_label" --out-base "$out_base" || true
  open "$out_base/$user_label/_Report" >/dev/null 2>&1 || true
}

run_full_with_report() {
  local user_label="$1"
  local user_path="$2"
  run_full_profile "$user_label" "$user_path"
  merge_latest_timelines "$user_label" || true
  generate_report "$user_label" || true
  if [[ -n "${OPENAI_API_KEY:-}" ]]; then
    run_genesis_agent "$user_label"
  else
    echo "OPENAI_API_KEY not set. Skipping Genesis Analyst."
  fi
}

run_genesis_agent() {
  local user_label="$1"
  local out_base="$OUT_DIR_HOUSE"
  local peer_label="fam"
  local peer_out_base="$OUT_DIR_FAM"
  if [[ "$user_label" == "fam" ]]; then
    out_base="$OUT_DIR_FAM"
    peer_label="house"
    peer_out_base="$OUT_DIR_HOUSE"
  fi
  if [[ ! -e "$GENESIS_AGENT_SCRIPT" ]]; then
    echo "Missing Genesis agent script: $GENESIS_AGENT_SCRIPT"
    return 1
  fi
  "$PY_MAIN" "$GENESIS_AGENT_SCRIPT" \
    --user-label "$user_label" \
    --out-base "$out_base" \
    --peer-label "$peer_label" \
    --peer-out-base "$peer_out_base"
  local rc=$?
  if [[ "$rc" -ne 0 ]]; then
    echo "Genesis Analyst failed for $user_label (code $rc)."
    return "$rc"
  fi
  open "$out_base/$user_label/_Report" >/dev/null 2>&1 || true
}

run_genesis_agent_combined() {
  if [[ ! -e "$GENESIS_AGENT_SCRIPT" ]]; then
    echo "Missing Genesis agent script: $GENESIS_AGENT_SCRIPT"
    return 1
  fi
  "$PY_MAIN" "$GENESIS_AGENT_SCRIPT" \
    --user-label "house" \
    --out-base "$OUT_DIR_HOUSE" \
    --peer-label "fam" \
    --peer-out-base "$OUT_DIR_FAM"
  local rc=$?
  if [[ "$rc" -ne 0 ]]; then
    echo "Genesis Analyst combined run failed (code $rc)."
    return "$rc"
  fi
  open "$OUT_DIR_HOUSE/house/_Report" >/dev/null 2>&1 || true
}
run_yara_scan() {
  local user_label="$1"
  local out_base="$OUT_DIR_HOUSE"
  if [[ "$user_label" == "fam" ]]; then
    out_base="$OUT_DIR_FAM"
  fi
  local latest=""
  if [[ "$user_label" == "house" && -f "$LAST_OUTPUT_HOUSE" ]]; then
    latest=$(cat "$LAST_OUTPUT_HOUSE")
  elif [[ "$user_label" == "fam" && -f "$LAST_OUTPUT_FAM" ]]; then
    latest=$(cat "$LAST_OUTPUT_FAM")
  else
    latest=$(latest_dir "$out_base/$user_label/*")
  fi
  if [[ -z "$latest" || ! -d "$latest" ]]; then
    echo "No output found for $user_label"
    return 1
  fi
  "$PY_MAIN" "$YARA_SCRIPT" --output-dir "$latest" --rules "$YARA_RULES_FILE" || true
}

run_sigma_scan() {
  local user_label="$1"
  local out_base="$OUT_DIR_HOUSE"
  if [[ "$user_label" == "fam" ]]; then
    out_base="$OUT_DIR_FAM"
  fi
  local latest=""
  if [[ "$user_label" == "house" && -f "$LAST_OUTPUT_HOUSE" ]]; then
    latest=$(cat "$LAST_OUTPUT_HOUSE")
  elif [[ "$user_label" == "fam" && -f "$LAST_OUTPUT_FAM" ]]; then
    latest=$(cat "$LAST_OUTPUT_FAM")
  else
    latest=$(latest_dir "$out_base/$user_label/*")
  fi
  if [[ -z "$latest" || ! -d "$latest" ]]; then
    echo "No output found for $user_label"
    return 1
  fi
  "$PY_MAIN" "$SIGMA_SCRIPT" --output-dir "$latest" --rules-dir "$SIGMA_RULES_DIR" || true
}

run_clamav_scan() {
  local user_label="$1"
  local mode="$2"
  local out_base="$OUT_DIR_HOUSE"
  if [[ "$user_label" == "fam" ]]; then
    out_base="$OUT_DIR_FAM"
  fi
  local latest=""
  if [[ "$user_label" == "house" && -f "$LAST_OUTPUT_HOUSE" ]]; then
    latest=$(cat "$LAST_OUTPUT_HOUSE")
  elif [[ "$user_label" == "fam" && -f "$LAST_OUTPUT_FAM" ]]; then
    latest=$(cat "$LAST_OUTPUT_FAM")
  else
    latest=$(latest_dir "$out_base/$user_label/*")
  fi
  if [[ -z "$latest" || ! -d "$latest" ]]; then
    echo "No output found for $user_label"
    return 1
  fi
  "$CLAMAV_SCRIPT" "$mode" "$latest" || true
}

run_plaso() {
  local user_label="$1"
  local out_base="$OUT_DIR_HOUSE"
  if [[ "$user_label" == "fam" ]]; then
    out_base="$OUT_DIR_FAM"
  fi
  read -r -p "Enter input path for Plaso (image or folder): " input_path
  if [[ -z "$input_path" ]]; then
    echo "Missing input path"
    return 1
  fi
  local out_dir="$out_base/$user_label/_Plaso"
  mkdir -p "$out_dir"
  "$PLASO_SCRIPT" "$input_path" "$out_dir" || true
}

start_timesketch() {
  read -r -p "Enter timesketch directory path: " ts_dir
  if [[ -z "$ts_dir" ]]; then
    echo "Missing timesketch path"
    return 1
  fi
  "$TIMESKETCH_SCRIPT" "$ts_dir" || true
}
open_latest_ileapp() {
  local user_label="$1"
  local latest
  local out_base="$OUT_DIR_HOUSE"
  if [[ "$user_label" == "fam" ]]; then
    out_base="$OUT_DIR_FAM"
  fi
  latest=$(latest_dir "$out_base/$user_label/ileapp_*")
  if [[ -z "$latest" ]]; then
    echo "No iLEAPP output found in $out_base/$user_label"
    return 1
  fi
  open_report_if_exists "$latest/_HTML/index.html"
}

open_latest_macapt() {
  local user_label="$1"
  local latest
  local out_base="$OUT_DIR_HOUSE"
  if [[ "$user_label" == "fam" ]]; then
    out_base="$OUT_DIR_FAM"
  fi
  latest=$(latest_dir "$out_base/$user_label/macapt_*")
  if [[ -z "$latest" ]]; then
    echo "No mac_apt output found in $out_base/$user_label"
    return 1
  fi
  open "$latest" >/dev/null 2>&1 || true
}

export_latest_ileapp_timeline() {
  local user_label="$1"
  local latest
  local out_base="$OUT_DIR_HOUSE"
  if [[ "$user_label" == "fam" ]]; then
    out_base="$OUT_DIR_FAM"
  fi
  latest=$(latest_dir "$out_base/$user_label/ileapp_*")
  if [[ -z "$latest" ]]; then
    echo "No iLEAPP output found in $out_base/$user_label"
    return 1
  fi
  if [[ ! -e "$latest/_Timeline/tl.db" ]]; then
    echo "No timeline DB found in $latest"
    return 1
  fi
  sqlite3 "$latest/_Timeline/tl.db" ".mode csv" ".headers on" ".output $latest/_Timeline/timeline.csv" "select * from data;" >/dev/null 2>&1 || true
  echo "Exported: $latest/_Timeline/timeline.csv"
  open "$latest/_Timeline" >/dev/null 2>&1 || true
}

export_latest_macapt_timeline() {
  local user_label="$1"
  local user_path="$2"
  local latest
  local out_base="$OUT_DIR_HOUSE"
  if [[ "$user_label" == "fam" ]]; then
    out_base="$OUT_DIR_FAM"
  fi
  latest=$(latest_dir "$out_base/$user_label/macapt_*")
  if [[ -z "$latest" ]]; then
    echo "No mac_apt output found in $out_base/$user_label"
    return 1
  fi
  if [[ ! -e "$latest/mac_apt.db" ]]; then
    echo "No mac_apt.db found in $latest"
    return 1
  fi
  "$PY_MAIN" "$MACAPT_TIMELINE" --input "$latest" --user-path "$user_path" || true
  open "$latest/_Timeline" >/dev/null 2>&1 || true
}

start_webui() {
  "$PY_MAIN" "$ROOT_DIR/forensics_webui.py"
}

start_gui() {
  "$PY_MAIN" "$ROOT_DIR/forensics_gui.py"
}

run_menu_choice() {
  local choice="$1"
  case "$choice" in
    1) run_macapt_profile "house" "$HOUSE_USER_PATH" "$MACAPT_CORE_PROFILE" "core" ;;
    2) run_macapt_profile "house" "$HOUSE_USER_PATH" "$MACAPT_COMMS_PROFILE" "comms" ;;
    3) run_macapt_profile "house" "$HOUSE_USER_PATH" "$MACAPT_SECURITY_PROFILE" "security" ;;
    4) run_ileapp_profile "house" "$HOUSE_ILEAPP_TYPE" "$HOUSE_IOS_INPUT" ;;
    5) run_xleapp_core "house" "$HOUSE_XLEAPP_INPUT" ;;
    6) open_latest_ileapp "house" ;;
    7) open_latest_macapt "house" ;;
    8) export_latest_ileapp_timeline "house" ;;
    9) export_latest_macapt_timeline "house" "$HOUSE_USER_PATH" ;;
    10) run_full_profile "house" "$HOUSE_USER_PATH" ;;
    11) purge_outputs "house" ;;
    12) run_full_with_report "house" "$HOUSE_USER_PATH" ;;
    13) generate_report "house" ;;
    14) merge_latest_timelines "house" ;;
    15) run_yara_scan "house" ;;
    16) run_sigma_scan "house" ;;
    17) run_clamav_scan "house" "quick" ;;
    18) run_clamav_scan "house" "full" ;;
    19) run_plaso "house" ;;
    20) run_genesis_agent "house" ;;

    21) run_macapt_profile "fam" "$FAM_USER_PATH" "$MACAPT_CORE_PROFILE" "core" ;;
    22) run_macapt_profile "fam" "$FAM_USER_PATH" "$MACAPT_COMMS_PROFILE" "comms" ;;
    23) run_macapt_profile "fam" "$FAM_USER_PATH" "$MACAPT_SECURITY_PROFILE" "security" ;;
    24) run_ileapp_profile "fam" "$FAM_ILEAPP_TYPE" "$FAM_IOS_INPUT" ;;
    25) run_xleapp_core "fam" "$FAM_XLEAPP_INPUT" ;;
    26) open_latest_ileapp "fam" ;;
    27) open_latest_macapt "fam" ;;
    28) export_latest_ileapp_timeline "fam" ;;
    29) export_latest_macapt_timeline "fam" "$FAM_USER_PATH" ;;
    30) run_full_profile "fam" "$FAM_USER_PATH" ;;
    31) purge_outputs "fam" ;;
    32) run_full_with_report "fam" "$FAM_USER_PATH" ;;
    33) generate_report "fam" ;;
    34) merge_latest_timelines "fam" ;;
    35) run_yara_scan "fam" ;;
    36) run_sigma_scan "fam" ;;
    37) run_clamav_scan "fam" "quick" ;;
    38) run_clamav_scan "fam" "full" ;;
    39) run_plaso "fam" ;;
    40) run_genesis_agent "fam" ;;

    90) start_webui ;;
    91) start_gui ;;
    92) start_timesketch ;;
    93) run_genesis_agent_combined ;;
    99) exit 0 ;;
    *) echo "Invalid option: $choice"; return 1 ;;
  esac
}

main() {
  local one_shot_choice=""
  if [[ "${1:-}" == "--choice" ]]; then
    one_shot_choice="${2:-}"
  fi

  print_header "The Genesis Method Launcher"
  echo "Root: $ROOT_DIR"
  echo "Python default: $PY_MAIN"
  echo "iLEAPP Python: $PY_ILEAPP"
  echo "Output base (house): $OUT_DIR_HOUSE"
  echo "Output base (fam): $OUT_DIR_FAM"
  if [[ -f "$LAST_OUTPUT_HOUSE" ]]; then
    echo "Last output (house): $(cat "$LAST_OUTPUT_HOUSE")"
  fi
  if [[ -f "$LAST_OUTPUT_FAM" ]]; then
    echo "Last output (fam): $(cat "$LAST_OUTPUT_FAM")"
  fi
  echo "House iOS input: $HOUSE_IOS_INPUT ($HOUSE_ILEAPP_TYPE)"
  echo "Fam iOS input: $FAM_IOS_INPUT ($FAM_ILEAPP_TYPE)"

  if [[ -n "$one_shot_choice" ]]; then
    run_menu_choice "$one_shot_choice"
    return $?
  fi

  while true; do
    menu
    read -r -p "> " choice
    run_menu_choice "$choice"
  done
}

main "$@"

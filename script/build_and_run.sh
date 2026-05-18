#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT="${ROOT_DIR}/macos/GenesisMethodHost/GenesisMethodHost.xcodeproj"
SCHEME="GenesisMethodHost"
CONFIGURATION="${CONFIGURATION:-Debug}"
APP_NAME="Genesis Method"
DESKTOP_APP="${HOME}/Desktop/${APP_NAME}.app"
LOG_MODE=0
VERIFY=0

for arg in "$@"; do
  case "${arg}" in
    --logs|--telemetry) LOG_MODE=1 ;;
    --verify) VERIFY=1 ;;
    *) ;;
  esac
done

/usr/bin/pkill -x GenesisMethodHost 2>/dev/null || true
/usr/bin/pkill -x "${APP_NAME}" 2>/dev/null || true
/usr/bin/pkill -f "${ROOT_DIR}/genesis_app_launcher.py" 2>/dev/null || true
/usr/bin/pkill -f "${ROOT_DIR}/forensics_webui.py" 2>/dev/null || true
/usr/bin/pkill -f "The_Genesis_Method.*genesis_app_launcher.py" 2>/dev/null || true
/usr/bin/pkill -f "The_Genesis_Method.*forensics_webui.py" 2>/dev/null || true
while IFS= read -r pid; do
  [[ -n "${pid}" ]] && /bin/kill "${pid}" 2>/dev/null || true
done < <(/usr/sbin/lsof -tiTCP:8123 -sTCP:LISTEN 2>/dev/null)
/bin/sleep 0.2

/usr/bin/xcodebuild \
  -project "${PROJECT}" \
  -scheme "${SCHEME}" \
  -configuration "${CONFIGURATION}" \
  -destination "generic/platform=macOS" \
  CODE_SIGNING_ALLOWED=NO \
  build

BUILT_PRODUCTS_DIR="$(
  /usr/bin/xcodebuild \
    -project "${PROJECT}" \
    -scheme "${SCHEME}" \
    -configuration "${CONFIGURATION}" \
    -showBuildSettings 2>/dev/null \
    | /usr/bin/sed -n 's/^[[:space:]]*BUILT_PRODUCTS_DIR = //p' \
    | /usr/bin/head -1 \
    | /usr/bin/xargs
)"

SOURCE_APP="${BUILT_PRODUCTS_DIR}/GenesisMethodHost.app"
if [[ ! -d "${SOURCE_APP}" ]]; then
  echo "Built app not found: ${SOURCE_APP}" >&2
  exit 1
fi

/bin/rm -rf "${DESKTOP_APP}"
/bin/cp -R "${SOURCE_APP}" "${DESKTOP_APP}"
/usr/bin/xattr -dr com.apple.quarantine "${DESKTOP_APP}" 2>/dev/null || true
/usr/bin/open -n "${DESKTOP_APP}"

if [[ "${VERIFY}" == "1" ]]; then
  for _ in {1..30}; do
    if /usr/bin/pgrep -x GenesisMethodHost >/dev/null; then
      echo "Verified: GenesisMethodHost is running from ${DESKTOP_APP}"
      break
    fi
    /bin/sleep 0.5
  done
  /usr/bin/pgrep -x GenesisMethodHost >/dev/null
fi

if [[ "${LOG_MODE}" == "1" ]]; then
  /usr/bin/log stream --style compact --predicate 'process == "GenesisMethodHost"' --info
fi

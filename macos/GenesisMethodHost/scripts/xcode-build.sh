#!/usr/bin/env bash
# Genesis Method native host — Xcode / Swift toolchain + Developer ID notarization (notarytool + stapler).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOST_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PROJECT="${HOST_ROOT}/GenesisMethodHost.xcodeproj"
SCHEME="GenesisMethodHost"
CONFIG="${CONFIGURATION:-Debug}"
BUILD_DIR="${HOST_ROOT}/build"
NOTARY_DIR="${BUILD_DIR}/notarize"

usage() {
  cat <<'USAGE'
Usage: macos/GenesisMethodHost/scripts/xcode-build.sh <command>

Build / analyze:
  doctor           Xcode + Swift + schemes
  build-debug      Debug build
  build-release    Release build (use Developer ID for distribution)
  analyze          xcodebuild static analyzer
  clean            xcodebuild clean
  archive          Release .xcarchive -> build/GenesisMethodHost.xcarchive

Notarization (Apple notarytool + stapler):
  package-zip      Release build + zip app -> build/notarize/GenesisMethodHost.zip
  notarize-submit  Submit ZIP only (waits for Apple). Requires NOTARY_KEYCHAIN_PROFILE.
  staple           Staple ticket onto GenesisMethodHost.app (run after accepted submission)
  validate-staple  xcrun stapler validate on the app
  notarize         package-zip + notarize-submit + staple + validate-staple (full lane)

Env — builds:
  CONFIGURATION          Debug|Release (some commands)
  CODE_SIGN_IDENTITY     e.g. "Developer ID Application: Your Name (TEAMID)"
  CODE_SIGNING_ALLOWED   YES|NO

Env — notarize-submit / notarize:
  NOTARY_KEYCHAIN_PROFILE  Required. Create once:
    xcrun notarytool store-credentials "genesis-notary" \
      --apple-id "you@example.com" \
      --team-id "YOUR_TEAM_ID" \
      --password "app-specific-password"
  SKIP_BUILD=1           Skip compile during package-zip (reuse existing Release build)
  CUSTOM_ZIP_PATH        Override zip output path
  CUSTOM_APP_PATH        Override path to GenesisMethodHost.app for staple

Examples:
  ./scripts/xcode-build.sh doctor

  # Signed Release (Developer ID) then ship pipeline:
  CODE_SIGN_IDENTITY="Developer ID Application: …" ./scripts/xcode-build.sh build-release

  NOTARY_KEYCHAIN_PROFILE="genesis-notary" ./scripts/xcode-build.sh notarize

  # Submit again without rebuilding:
  SKIP_BUILD=1 NOTARY_KEYCHAIN_PROFILE="genesis-notary" ./scripts/xcode-build.sh notarize-submit
USAGE
}

doctor() {
  echo "=== Xcode toolchain ==="
  xcodebuild -version || true
  echo ""
  echo "=== Swift ==="
  swift --version || true
  echo ""
  echo "=== xcode-select ==="
  xcode-select -p || true
  echo ""
  echo "=== notarytool ==="
  xcrun notarytool --help >/dev/null && echo "notarytool: OK" || echo "notarytool: missing"
  echo ""
  echo "=== Project ==="
  echo "PROJECT=${PROJECT}"
  xcodebuild -list -project "${PROJECT}" 2>/dev/null || xcodebuild -list -project "${PROJECT}"
}

built_products_dir() {
  local conf="$1"
  xcodebuild \
    -project "${PROJECT}" \
    -scheme "${SCHEME}" \
    -configuration "${conf}" \
    -showBuildSettings 2>/dev/null \
    | sed -n 's/^[[:space:]]*BUILT_PRODUCTS_DIR = //p' \
    | head -1 \
    | xargs
}

cmd_build() {
  local conf="$1"
  local sign_allow="${CODE_SIGNING_ALLOWED:-YES}"
  local sign_id="${CODE_SIGN_IDENTITY:-}"
  if [[ -z "${sign_id}" ]]; then
    if [[ "${sign_allow}" == "NO" ]]; then
      sign_id="-"
    else
      sign_id="Apple Development"
    fi
  fi

  echo "Building ${SCHEME} (${conf}) CODE_SIGN_IDENTITY=${sign_id} CODE_SIGNING_ALLOWED=${sign_allow}"
  xcodebuild \
    -project "${PROJECT}" \
    -scheme "${SCHEME}" \
    -configuration "${conf}" \
    -destination "generic/platform=macOS" \
    CODE_SIGN_IDENTITY="${sign_id}" \
    CODE_SIGNING_ALLOWED="${sign_allow}" \
    build
}

cmd_analyze() {
  xcodebuild \
    -project "${PROJECT}" \
    -scheme "${SCHEME}" \
    -configuration "${CONFIG}" \
    -destination "generic/platform=macOS" \
    analyze
}

cmd_clean() {
  xcodebuild \
    -project "${PROJECT}" \
    -scheme "${SCHEME}" \
    -configuration "${CONFIG}" \
    clean
}

cmd_archive() {
  mkdir -p "${BUILD_DIR}"
  local out="${BUILD_DIR}/GenesisMethodHost.xcarchive"
  rm -rf "${out}"
  echo "Archiving to ${out}"
  xcodebuild \
    -project "${PROJECT}" \
    -scheme "${SCHEME}" \
    -configuration Release \
    -destination "generic/platform=macOS" \
    -archivePath "${out}" \
    archive
}

require_notary_profile() {
  if [[ -z "${NOTARY_KEYCHAIN_PROFILE:-}" ]]; then
    echo "ERROR: Set NOTARY_KEYCHAIN_PROFILE (see ./scripts/xcode-build.sh help)."
    echo "Create profile: xcrun notarytool store-credentials \"genesis-notary\" --apple-id ... --team-id ... --password ..."
    exit 1
  fi
}

resolve_app_release() {
  local bp
  bp="$(built_products_dir Release)"
  if [[ -z "${bp}" ]]; then
    echo "ERROR: Could not read BUILT_PRODUCTS_DIR for Release."
    exit 1
  fi
  echo "${bp}/GenesisMethodHost.app"
}

cmd_package_zip() {
  mkdir -p "${NOTARY_DIR}"
  local conf="Release"
  if [[ "${SKIP_BUILD:-0}" != "1" ]]; then
    cmd_build "${conf}"
  fi

  local app
  if [[ -n "${CUSTOM_APP_PATH:-}" ]]; then
    app="${CUSTOM_APP_PATH}"
  else
    app="$(resolve_app_release)"
  fi

  if [[ ! -d "${app}" ]]; then
    echo "ERROR: App not found: ${app}"
    exit 1
  fi

  local zip_out="${CUSTOM_ZIP_PATH:-${NOTARY_DIR}/GenesisMethodHost.zip}"
  rm -f "${zip_out}"
  echo "Zipping (ditto) -> ${zip_out}"
  ditto -c -k --sequesterRsrc --keepParent "${app}" "${zip_out}"
  echo "APP=${app}"
  echo "ZIP=${zip_out}"
}

cmd_notarize_submit() {
  require_notary_profile
  local zip_out="${CUSTOM_ZIP_PATH:-${NOTARY_DIR}/GenesisMethodHost.zip}"
  if [[ ! -f "${zip_out}" ]]; then
    echo "ERROR: Missing ${zip_out}. Run package-zip or set CUSTOM_ZIP_PATH."
    exit 1
  fi

  echo "Submitting ${zip_out} with profile '${NOTARY_KEYCHAIN_PROFILE}' …"
  local log="${NOTARY_DIR}/last-submit-log.txt"
  # shellcheck disable=SC2086
  xcrun notarytool submit "${zip_out}" \
    --keychain-profile "${NOTARY_KEYCHAIN_PROFILE}" \
    --wait \
    2>&1 | tee "${log}"
  echo "Log saved: ${log}"
}

cmd_staple() {
  local app
  if [[ -n "${CUSTOM_APP_PATH:-}" ]]; then
    app="${CUSTOM_APP_PATH}"
  else
    app="$(resolve_app_release)"
  fi
  if [[ ! -d "${app}" ]]; then
    echo "ERROR: App not found: ${app}"
    exit 1
  fi
  echo "Stapling ${app} …"
  xcrun stapler staple "${app}"
}

cmd_validate_staple() {
  local app
  if [[ -n "${CUSTOM_APP_PATH:-}" ]]; then
    app="${CUSTOM_APP_PATH}"
  else
    app="$(resolve_app_release)"
  fi
  if [[ ! -d "${app}" ]]; then
    echo "ERROR: App not found: ${app}"
    exit 1
  fi
  echo "Validating staple on ${app} …"
  xcrun stapler validate "${app}"
}

cmd_notarize_all() {
  cmd_package_zip
  cmd_notarize_submit
  cmd_staple
  cmd_validate_staple
  echo ""
  echo "OK: notarize pipeline finished. Ship: $(resolve_app_release)"
}

main() {
  local cmd="${1:-}"
  case "${cmd}" in
    doctor) doctor ;;
    build-debug) cmd_build Debug ;;
    build-release) cmd_build Release ;;
    analyze) cmd_analyze ;;
    clean) cmd_clean ;;
    archive) cmd_archive ;;
    package-zip) cmd_package_zip ;;
    notarize-submit) cmd_notarize_submit ;;
    staple) cmd_staple ;;
    validate-staple) cmd_validate_staple ;;
    notarize) cmd_notarize_all ;;
    ""|-h|--help|help) usage ;;
    *) echo "Unknown: ${cmd}"; usage; exit 1 ;;
  esac
}

main "$@"

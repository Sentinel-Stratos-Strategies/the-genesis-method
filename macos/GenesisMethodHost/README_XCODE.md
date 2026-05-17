# Genesis Method — Xcode project (native host)

Open this in Xcode:

**`GenesisMethodHost.xcodeproj`** (in this folder)

Double-click that file, pick your **Team** under Signing & Capabilities (Debug/Release), then **⌘R**. The app starts Python (`genesis_app_launcher.py`: memory gate + WebUI), waits for port **8123**, and shows the dashboard inside **WKWebView** (no extra Safari tab).

## Layout

```
GenesisMethodHost/
├── GenesisMethodHost.xcodeproj/     ← open this
├── SwiftSources/                    ← SwiftUI + WKWebView + Process launcher
├── Resources/GENESIS_ROOT.txt       ← one line = absolute path to The_Genesis_Method clone
└── README_XCODE.md                  ← this file
```

Edit **`Resources/GENESIS_ROOT.txt`** if your repo lives somewhere other than `/Volumes/Stratos_Tools/projects/The_Genesis_Method`.  
Optional: **`SwiftSources/GenesisPaths.swift`** also has a hardcoded fallback path.

## Build settings (already set)

- **macOS 13+**, Swift 5  
- **App Sandbox: OFF** — allows localhost WebView + spawning `python3`  
- **Hardened Runtime: ON** — disable temporarily only if debugging blocks something  

### Xcode / Swift CLI (recommended)

From **`macos/GenesisMethodHost`**:

```bash
./scripts/xcode-build.sh doctor       # Xcode + Swift versions, schemes
./scripts/xcode-build.sh build-debug  # Debug build (uses your signing defaults)

# Unsigned / CI-style:
CODE_SIGN_IDENTITY="-" CODE_SIGNING_ALLOWED=NO ./scripts/xcode-build.sh build-release

# Static analyzer:
./scripts/xcode-build.sh analyze

# Shipping archive (needs a real signing identity):
./scripts/xcode-build.sh archive      # -> build/GenesisMethodHost.xcarchive
```

Metal and other GPU toolchains are whatever **Xcode 26.x** selects via `xcode-select`; no extra flags are required for this WKWebView host.

## Developer ID + notarization (CLI)

Shippable `.app` must be signed with **Developer ID Application** and stapled after Apple notarization.

**One-time:** store App Store Connect credentials in the Keychain (pick any profile label):

```bash
xcrun notarytool store-credentials "genesis-notary" \
  --apple-id "you@example.com" \
  --team-id "YOUR_TEAM_ID" \
  --password "@keychain:GENESIS_NOTARY_APP_SPECIFIC"
```

Use an **app-specific password** or `@keychain:…` as documented by Apple.

**Full pipeline:**

```bash
cd macos/GenesisMethodHost

export CODE_SIGN_IDENTITY="Developer ID Application: Your Name (TEAMID)"
export NOTARY_KEYCHAIN_PROFILE="genesis-notary"

./scripts/xcode-build.sh notarize
```

Outputs:

- **`build/notarize/GenesisMethodHost.zip`** — upload payload  
- **`build/notarize/last-submit-log.txt`** — `notarytool` transcript  

Steps broken out: **`package-zip`**, **`notarize-submit`**, **`staple`**, **`validate-staple`** (see `./scripts/xcode-build.sh help`).

## Python interpreter

Default: **`/usr/bin/python3`**.  
Change **`pythonExecutable`** in **`SwiftSources/PythonBackend.swift`** for Homebrew/pyenv (e.g. `/opt/homebrew/bin/python3`).

## LLM + memory

- Dashboard **AI Engine** + **`config/genesis_llm_config.json`**
- **`GENESIS_WEBUI_OPEN_BROWSER=0`** so only WKWebView loads the UI
- **`genesis_app_launcher.py`** runs **`scripts/genesis_memory_contract_gate.sh`** unless you add **`--skip-gate`** to the launched Process (not recommended)

## Bash `.app` (alternate)

`../GenesisMethod.app` is the lighter shell-only bundle.

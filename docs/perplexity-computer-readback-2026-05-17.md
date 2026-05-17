# Perplexity Computer Readback - 2026-05-17

Source: in-app browser, Perplexity `Computer` tasks and related spaces.

## High-Signal Threads Read

- `Mac Device Management Threat Research`
- `SCRIPTS` space overview
- `Computer` task dashboard thread list

## Ideas To Fold Into Genesis

### MDM / ABM / ADE Hunter

The `Mac Device Management Threat Research` thread calls for a dedicated `sentinel-mdm-hunter` lane with these modules:

- `enrollment-audit`
- `profile-forensics`
- `network-probe`
- `binary-trust-verify`
- `kerberos-sso-audit`
- `ioc-collector`
- `report-writer`

The thread also queues eight v2 research additions:

- WWDC / new declaration changes, return-to-service, and software update enforcement
- Account-Driven Device Enrollment vs ADE
- Return to Service / Erase All Content & Settings with ABM serial re-enrollment
- Vendor agent binary IOCs for Jamf, Kandji, Mosyle, Addigy, and similar platforms
- APNs topic enumeration using `com.apple.mgmt.External.<UUID>` style evidence
- macOS 26 / Tahoe build-specific changes
- Kerberos realm to IdP vendor fingerprinting
- Shadow installer pattern library for Atomic Stealer, Shlayer-style installers, fake MDM helpers, Developer ID abuse, notarization, and Team ID checks

Genesis impact:

- Keep MDM/ADE hunting as a first-class plugin category.
- Add a non-GUI-only artifact model: profiles UI can be empty while assignment, identity, declaration, APNs, and local artifacts still matter.
- Treat installer trust verification as evidence: `codesign`, `spctl`, notarization tickets, entitlements, certificate chain, Team ID, and postinstall behavior.

### OSINT / Recon Scripting

The `SCRIPTS` space references a hardened OSINT/recon engine and mini-app using:

- Perplexity SDK / Sonar style research
- local Llama/Ollama/GLM-style models
- Censys
- AssetNote
- API/service inventory
- older script references: `sentinel_ultimate_v3.py`, `main_osint_v2_backup_20260115_012401.py`

Genesis impact:

- Keep OSINT as a plugin lane, not a heavy always-loaded feature.
- Preserve target-builder and enrichment scripts, but expose them dynamically through plugins.
- Add prerequisite-aware plugin reports so missing keys or external tools produce clear skipped evidence instead of silent failure.

### Mini Terminal / Mac TUI

The Computer dashboard includes `Designing a Custom Macro Terminal App` with `sentinel-macos-bundle.zip`.

Genesis impact:

- The WebUI/GUI should remain a command deck, but the plugin registry should also support future TUI wrappers.
- Plugin metadata needs category, target, description, source, prerequisites, and command so a small terminal UI can render the same modules later.

## Local Build Decision

The rebuild should make Genesis a dynamic command deck:

- `plugins/*.py` for code-backed plugins.
- `plugins/*.json` for manifest-backed modules wrapping existing scripts and external tools.
- `tools/plugin_runner.py` as the single registry and runner.
- `tools/genesis_forensic_ops.py` as the Python-first evidence spine for case init, scope guard, inventory, anchor verification, sysdiagnose killcard, iCloud/Takeout ingest, canonical normalization, forensic index, confidence scoring, toolchain validation, and evidence diffing.

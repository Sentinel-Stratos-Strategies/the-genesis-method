# The Genesis Method (Operational README)

Sentinel Stratos Strategies forensic workflow for `house` + `fam`, with unified reporting and analyst output.

## 1) Project Root

```bash
cd /Users/house/genesis
```

Main launcher:

```bash
./run_forensics.sh
```

## 2) Output Locations

- House base output: `/Users/House/EVIDENCE`
- Fam base output: `/Users/fam/forensics_out`
- House report folder: `/Users/House/EVIDENCE/house/_Report`
- Fam report folder: `/Users/fam/forensics_out/fam/_Report`
- OSINT output folder: `/Users/House/EVIDENCE/house/_OSINT`
- Logs:
  - Launcher/web logs: `/Users/House/EVIDENCE/_logs`
  - GUI log: `/Users/House/EVIDENCE/_logs/gui_actions.log`

## 3) Proper Use Flow (Recommended)

Use this sequence when you want complete, defensible output:

1. Run House collection + report:
```bash
./run_forensics.sh --choice 12
```

2. Run Fam collection + report:
```bash
./run_forensics.sh --choice 32
```

3. Run combined analyst synthesis (House + Fam):
```bash
./run_forensics.sh --choice 93
```

4. Optional: generate OSINT targets + enrichment report:
```bash
./run_forensics.sh --choice 94   # build targets (limited + noise-filtered)
./run_forensics.sh --choice 96   # enrich + Sonar summaries
```

5. Open the newest consolidated outputs:
```bash
open "$(ls -1dt /Users/House/EVIDENCE/house/_Report/genesis_analyst_*.md | head -1)"
open "$(ls -1dt /Users/House/EVIDENCE/house/_Report/genesis_inventory_*.csv | head -1)"
```

## 4) Quick Kill Cards

### A) Combined analyst only (fastest)
```bash
cd /Users/house/genesis
./run_forensics.sh --choice 93
```

### B) Full forensic pass then analyst
```bash
cd /Users/house/genesis
./run_forensics.sh --choice 12
./run_forensics.sh --choice 32
./run_forensics.sh --choice 93
```

### C) Full run + OSINT enrichment (recommended)
```bash
cd /Users/house/genesis
./run_forensics.sh --choice 12
./run_forensics.sh --choice 32
./run_forensics.sh --choice 93
./run_forensics.sh --choice 98
```

### D) GUI / WebUI launch
```bash
cd /Users/house/genesis
./run_forensics.sh --choice 91   # GUI
./run_forensics.sh --choice 90   # WebUI
```

## 5) Analyst + Identifier Artifacts

Each run now auto-generates identifier extraction for each artifact folder.

Per-artifact identifier outputs:
- `_Identifiers/identifiers.csv`
- `_Identifiers/identifiers.json`
- `_Identifiers/identifiers.md`
- `_Identifiers/identifiers_summary.csv`

Global analyst outputs:
- `genesis_analyst_YYYYMMDD_HHMMSS.md`
- `genesis_analyst_YYYYMMDD_HHMMSS.json`
- `genesis_inventory_YYYYMMDD_HHMMSS.csv`

The analyst report includes:
- Accounts / emails / phones / UUIDs / IPv4 / IPv6 / domains / token categories
- Source references (`file:line`) for evidence traceability
- Security matches from YARA / Sigma / ClamAV / enrichment when present

## 6) Dynamic Forensic Modules

Genesis now supports lightweight dynamic modules through:

- `tools/plugin_runner.py`
- `plugins/*.py`
- `plugins/*.json`

List modules:

```bash
python3 tools/plugin_runner.py --plugin-dir plugins --list
```

Run one module:

```bash
python3 tools/plugin_runner.py \
  --plugin-dir plugins \
  --plugin validate_toolchain \
  --output-dir /Users/House/EVIDENCE
```

The GUI, WebUI, and `run_forensics.sh` all read the same plugin registry. Manifest-backed modules can wrap built-in Genesis scripts, SAF/sysdiag, MVT, UAC, osquery, Velociraptor, YARA/YARA-X, Plaso, Timesketch, or future Mac TUI modules. Missing external tools are reported as skipped modules instead of pretending a scan ran.

## 7) Genesis AI Engine

The WebUI includes a Genesis AI Engine section for analyst synthesis. It defaults to the local Ollama lane:

- provider: `ollama`
- model: `mistral-nemo:latest`
- base URL: `http://127.0.0.1:11436`
- runtime wrapper: `tools/ai/run_genesis_ollama_runtime.sh`
- config: `config/genesis_llm_config.json`
- optional local secret env file: `config/.genesis_llm_secrets.env` with mode `600`

The engine can also point at OpenAI-compatible providers by changing provider, model, base URL, and API key env name in the WebUI. The local config preserves the discovered Mistral Nemo, Ollama, OrbStack, Genesis memory, and Unsloth training paths.

## 8) Identifier Script Location

Identifier scanner script:

`/Users/house/genesis/tools/identifiers_scan.py`

Manual run (single artifact folder):

```bash
python3 /Users/house/genesis/tools/identifiers_scan.py \
  --output-dir "/path/to/specific/artifact_output"
```

## 9) Important Usage Notes

- If you are in a normal shell, typing just `36` or `39` will fail.  
  Use:
  - interactive menu: `./run_forensics.sh` then type option inside menu, or
  - one-shot mode: `./run_forensics.sh --choice 36`
- `house` and `fam` outputs are intentionally separate.
- Combined analyst (`93`) reads both sides and writes the consolidated report under House report folder.

## 10) Environment Variables (Optional)

- `GENESIS_LLM_CONFIG` to override the AI engine config path
- `GENESIS_LLM_SECRET_ENV` to override the local AI secret env file path
- `GENESIS_LLM_API_KEY` or the configured API-key env name for third-party AI providers
- `OPENAI_API_KEY` still works when the provider is OpenAI
- `GENESIS_MODEL` to temporarily override the configured model
- `GENESIS_MODEL_FALLBACKS` (comma-separated)
- `GENESIS_PPLX_ENV_FILE` path to a `KEY=value` env file containing Perplexity/Sonar + OSINT keys
  - default: `/Users/house/Tools/pplx/config/perplexity_api.env`
- `OUT_DIR_HOUSE` to override house output base (default is `/Users/House/EVIDENCE`)
- `OUT_DIR_FAM` to override fam output base
- `GENESIS_FAM_ROOT` to control fam root detection

## 11) Quick Sanity Check

```bash
cd /Users/house/genesis
bash -n run_forensics.sh
python3 -m py_compile tools/genesis_agent.py tools/plugin_runner.py tools/genesis_forensic_ops.py forensics_gui.py forensics_webui.py
```

If those pass, launch and run `--choice 93`.

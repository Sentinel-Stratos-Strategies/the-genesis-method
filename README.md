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

## 6) Identifier Script Location

Identifier scanner script:

`/Users/house/genesis/tools/identifiers_scan.py`

Manual run (single artifact folder):

```bash
python3 /Users/house/genesis/tools/identifiers_scan.py \
  --output-dir "/path/to/specific/artifact_output"
```

## 7) Important Usage Notes

- If you are in a normal shell, typing just `36` or `39` will fail.  
  Use:
  - interactive menu: `./run_forensics.sh` then type option inside menu, or
  - one-shot mode: `./run_forensics.sh --choice 36`
- `house` and `fam` outputs are intentionally separate.
- Combined analyst (`93`) reads both sides and writes the consolidated report under House report folder.

## 8) Environment Variables (Optional)

- `OPENAI_API_KEY` for analyst synthesis
- `GENESIS_MODEL` (default from script/env)
- `GENESIS_MODEL_FALLBACKS` (comma-separated)
- `GENESIS_PPLX_ENV_FILE` path to a `KEY=value` env file containing Perplexity/Sonar + OSINT keys
  - default: `/Users/house/Tools/pplx/config/perplexity_api.env`
- `OUT_DIR_HOUSE` to override house output base (default is `/Users/House/EVIDENCE`)
- `OUT_DIR_FAM` to override fam output base
- `GENESIS_FAM_ROOT` to control fam root detection

## 9) Quick Sanity Check

```bash
cd /Users/house/genesis
bash -n run_forensics.sh
python3 -m py_compile tools/genesis_agent.py forensics_gui.py forensics_webui.py
```

If those pass, launch and run `--choice 93`.

#!/usr/bin/env python3
"""
Sentinel IOC Search — targeted search across SAF parsed data
Usage: python3 sentinel_search.py
Outputs results to /Volumes/Stratos_Tools/forensics/SENTINEL_RESULTS/
"""

import os
import json
import re
from pathlib import Path
from datetime import datetime

# ── CONFIG ──────────────────────────────────────────────────────────────────
SAF_ROOT   = Path("/Volumes/Stratos_Tools/sysdiagnosis/AI1_Parser/input/SAF")
KILLCARD   = Path("/Volumes/Stratos_Tools/forensics/genesis_case_2026-05-17_164036/sysdiagnose_killcard/sysdiagnose_killcard_hits.jsonl")
OUT_DIR    = Path("/Volumes/Stratos_Tools/forensics/SENTINEL_RESULTS")
TIMESTAMP  = datetime.now().strftime("%Y%m%d_%H%M%S")
RUN_DIR    = OUT_DIR / f"run_{TIMESTAMP}"
RUN_DIR.mkdir(parents=True, exist_ok=True)

# ── IOCs TO HUNT ────────────────────────────────────────────────────────────
IOCS = {
    "dsid_marsha":    "18309627921",
    "hogan":          "hogan",
    "utun_tunnel":    "utun",
    "remote_pairing": "remotepairingd",
    "pegasus":        "pegasus",
    "ckks_breach":    "ckksctl",
    "mdm_enroll":     "mdmenrollment",
    "skylar":         "skylar",
    "lacey":          "lacey",
    "marsha":         "marsha",
}

# ── SMALL PARSEABLE FILES TO SEARCH (skip giant logarchive.jsonl) ────────────
TARGET_FILES = [
    "lockdownd.jsonl",
    "mobileinstallation.jsonl",
    "security_sysdiagnose.jsonl",
    "accessibility_tcc.jsonl",
    "wifinetworks.json",
    "networkextension.json",
    "shutdownlogs.jsonl",
    "crashlogs.jsonl",
    "ckks_status.json",
    "remotectl_dumpstate.txt",
    "otctl_status.txt",
    "pcsstatus.txt",
    "ps.txt",
    "taskSummary.csv",
    "brctl-dump.txt",
    "security-sysdiagnose.txt",
]

def search_file(filepath: Path, ioc_name: str, pattern: str) -> list:
    hits = []
    try:
        text = filepath.read_text(errors="replace")
        for i, line in enumerate(text.splitlines(), 1):
            if pattern.lower() in line.lower():
                hits.append({
                    "file": str(filepath),
                    "line": i,
                    "ioc": ioc_name,
                    "pattern": pattern,
                    "excerpt": line.strip()[:300]
                })
    except Exception as e:
        pass
    return hits

def search_killcard_spyware(killcard_path: Path) -> list:
    """Extract all spyware-bucket hits with paths and excerpts."""
    results = []
    try:
        with open(killcard_path) as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    if "spyware" in rec.get("buckets", []):
                        results.append({
                            "path": rec.get("path", ""),
                            "buckets": rec.get("buckets", []),
                            "identifier_count": len(rec.get("identifiers", [])),
                            "excerpt": rec.get("excerpt", "")[:400]
                        })
                except:
                    pass
    except Exception as e:
        print(f"[!] Killcard read error: {e}")
    return results

def main():
    print(f"[+] Sentinel IOC Search — {TIMESTAMP}")
    print(f"[+] SAF Root: {SAF_ROOT}")
    print(f"[+] Output:   {RUN_DIR}")
    print("")

    all_hits = {ioc: [] for ioc in IOCS}

    # ── Search SAF parsed data files ─────────────────────────────────────────
    captures = sorted([d for d in SAF_ROOT.iterdir() if d.is_dir()])
    print(f"[+] Found {len(captures)} SAF captures to search")
    print("")

    for capture in captures:
        capture_name = capture.name
        parsed = capture / "parsed_data"
        if not parsed.exists():
            parsed = capture  # fallback

        for target_file in TARGET_FILES:
            # Search both in parsed_data and raw data
            candidates = list(parsed.rglob(target_file)) + list(capture.rglob(target_file))
            for filepath in set(candidates):
                for ioc_name, pattern in IOCS.items():
                    hits = search_file(filepath, ioc_name, pattern)
                    if hits:
                        print(f"  [HIT] {ioc_name} in {capture_name}/{target_file} — {len(hits)} matches")
                        all_hits[ioc_name].extend(hits)

    # ── Extract spyware bucket hits from killcard ────────────────────────────
    print("")
    print("[+] Extracting spyware bucket entries from Genesis killcard...")
    spyware_hits = search_killcard_spyware(KILLCARD)
    print(f"  [+] {len(spyware_hits)} spyware-flagged entries found")

    # ── Write outputs ─────────────────────────────────────────────────────────
    print("")
    print("[+] Writing results...")

    # IOC hits per keyword
    for ioc_name, hits in all_hits.items():
        if hits:
            out = RUN_DIR / f"ioc_{ioc_name}.jsonl"
            with open(out, "w") as f:
                for hit in hits:
                    f.write(json.dumps(hit) + "\n")
            print(f"  [+] {ioc_name}: {len(hits)} hits → {out.name}")
        else:
            print(f"  [-] {ioc_name}: 0 hits in parsed files")

    # Spyware bucket summary
    spyware_out = RUN_DIR / "spyware_bucket_hits.jsonl"
    with open(spyware_out, "w") as f:
        for hit in spyware_hits:
            f.write(json.dumps(hit) + "\n")

    # Human-readable summary
    summary = RUN_DIR / "SENTINEL_SUMMARY.md"
    with open(summary, "w") as f:
        f.write(f"# Sentinel IOC Search Results\n")
        f.write(f"- Run: {TIMESTAMP}\n")
        f.write(f"- SAF Captures Searched: {len(captures)}\n")
        f.write(f"- Spyware Bucket Entries: {len(spyware_hits)}\n\n")
        f.write(f"## IOC Hit Counts\n")
        for ioc_name, hits in all_hits.items():
            status = "🚨" if hits else "✅"
            f.write(f"- {status} **{ioc_name}** (`{IOCS[ioc_name]}`): {len(hits)} hits\n")
        f.write(f"\n## Top Spyware Files (first 20)\n")
        for entry in spyware_hits[:20]:
            fname = Path(entry['path']).name
            buckets = ", ".join(entry['buckets'])
            f.write(f"- `{fname}` — [{buckets}] — {entry['identifier_count']} identifiers\n")

    print("")
    print(f"[+] Summary: {summary}")
    print(f"[+] Done. Results in: {RUN_DIR}")

if __name__ == "__main__":
    main()

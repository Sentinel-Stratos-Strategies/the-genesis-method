#!/usr/bin/env python3
"""Terminal UI for Genesis manifest plugins (enterprise paths)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from genesis_paths import load_paths, save_paths  # noqa: E402

PLUGIN_RUNNER = ROOT / "tools" / "plugin_runner.py"
PLUGIN_DIR = ROOT / "plugins"
MANIFEST = PLUGIN_DIR / "genesis_core_modules.json"


def clear():
    os.system("clear" if os.name != "nt" else "cls")


def pick_case_name(default: str) -> str:
    raw = input(f"Case / output folder name [{default}]: ").strip()
    return raw or default


def main() -> int:
    paths = load_paths(ROOT)
    inp = paths["evidence_input_root"]
    out_root = paths["evidence_output_root"]

    clear()
    print("The Genesis Method — Terminal Console")
    print("Evidence INPUT root (Stratos): ", inp)
    print("Evidence OUTPUT root (SENTINEL):", out_root)
    print()

    if not MANIFEST.is_file():
        print("Missing plugins manifest:", MANIFEST)
        return 1

    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    plugs = data.get("plugins", [])
    enterprise = [p for p in plugs if p.get("target") == "enterprise"]
    if not enterprise:
        enterprise = plugs

    for i, p in enumerate(enterprise, 1):
        print(f"  {i:2}. [{p.get('category')}] {p.get('name')} — {p.get('id')}")

    print("\n  p. Edit paths (save to config/genesis_paths.json)")
    print("  q. Quit")
    choice = input("\nSelect number or command: ").strip().lower()

    if choice == "q":
        return 0
    if choice == "p":
        n_in = input(f"Input root [{inp}]: ").strip() or inp
        n_out = input(f"Output root [{out_root}]: ").strip() or out_root
        save_paths(ROOT, {"evidence_input_root": n_in, "evidence_output_root": n_out})
        print("Saved config/genesis_paths.json — restart TUI.")
        return 0

    try:
        idx = int(choice)
    except ValueError:
        print("Invalid choice.")
        return 1

    if idx < 1 or idx > len(enterprise):
        print("Out of range.")
        return 1

    plug = enterprise[idx - 1]
    pid = plug["id"]
    default_case = plug.get("id", "run")[:40]
    case = pick_case_name(default_case)
    output_dir = Path(out_root) / case
    output_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        str(PLUGIN_RUNNER),
        "--plugin-dir",
        str(PLUGIN_DIR),
        "--plugin",
        pid,
        "--output-dir",
        str(output_dir),
        "--input-dir",
        inp,
    ]
    print("Running:\n ", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=str(ROOT))
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())

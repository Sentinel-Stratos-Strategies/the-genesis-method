#!/usr/bin/env python3
"""
Genesis Method macOS / CLI entry: runs memory-contract snapshot gate, then WebUI (default), GUI, or TUI.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _run_gate() -> None:
    gate = ROOT / "scripts" / "genesis_memory_contract_gate.sh"
    if not gate.is_file():
        return
    env = os.environ.copy()
    env.setdefault("GENESIS_ROOT", str(ROOT))
    subprocess.run(["bash", str(gate)], cwd=str(ROOT), env=env, check=False)


def _run_gate_background() -> None:
    """Snapshot gate without blocking the GUI (npm validators can take a long time)."""
    gate = ROOT / "scripts" / "genesis_memory_contract_gate.sh"
    if not gate.is_file():
        return
    env = os.environ.copy()
    env.setdefault("GENESIS_ROOT", str(ROOT))
    subprocess.Popen(
        ["bash", str(gate)],
        cwd=str(ROOT),
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def _exec_python(script: Path) -> int:
    os.execv(sys.executable, [sys.executable, str(script)])
    return 127


def main() -> int:
    parser = argparse.ArgumentParser(description="The Genesis Method launcher")
    parser.add_argument("--skip-gate", action="store_true", help="Skip memory-contract snapshot gate")
    parser.add_argument("--gui", action="store_true", help="Tkinter control center")
    parser.add_argument("--tui", action="store_true", help="Terminal menu")
    parser.add_argument("--webui", action="store_true", help="Enterprise WebUI (default)")
    args = parser.parse_args()

    if not args.skip_gate:
        if args.gui:
            _run_gate_background()
        else:
            _run_gate()

    if args.gui:
        return _exec_python(ROOT / "forensics_gui.py")
    if args.tui:
        return _exec_python(ROOT / "tools" / "genesis_tui.py")
    return _exec_python(ROOT / "forensics_webui.py")


if __name__ == "__main__":
    raise SystemExit(main())

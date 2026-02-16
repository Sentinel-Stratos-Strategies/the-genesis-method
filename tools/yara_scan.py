#!/usr/bin/env python3
import argparse
import os
import subprocess
from datetime import datetime


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--rules", required=True)
    args = parser.parse_args()

    if not os.path.exists(args.rules):
        print(f"Missing rules: {args.rules}")
        return 1

    if not shutil.which("yara"):
        print("yara not found. Install with: brew install yara")
        return 1

    out_dir = os.path.abspath(args.output_dir)
    report_dir = os.path.join(out_dir, "_YARA")
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, "yara_matches.txt")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"YARA scan report\nGenerated: {datetime.now().isoformat(timespec='seconds')}\n")
        f.write(f"Rules: {args.rules}\n")
        f.write(f"Target: {out_dir}\n\n")
        try:
            result = subprocess.run(
                ["yara", "-r", args.rules, out_dir],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
            f.write(result.stdout)
        except Exception as exc:
            f.write(f"Error running yara: {exc}\n")

    print(f"Wrote {report_path}")
    return 0


if __name__ == "__main__":
    import shutil
    raise SystemExit(main())

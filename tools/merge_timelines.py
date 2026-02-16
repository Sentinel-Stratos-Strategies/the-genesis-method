#!/usr/bin/env python3
import argparse
import csv
import os
from datetime import datetime


def load_csv(path):
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        rows = [row for row in reader]
    return reader.fieldnames or [], rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--inputs", nargs="+", required=True)
    args = parser.parse_args()

    headers = set()
    combined = []

    for inp in args.inputs:
        if not os.path.exists(inp):
            continue
        fields, rows = load_csv(inp)
        for row in rows:
            row["source_file"] = os.path.basename(inp)
            combined.append(row)
        headers.update(fields)

    headers = [h for h in headers if h]
    headers = ["source_file"] + sorted(set(headers))

    out_dir = os.path.join(args.output_dir, "_Timeline")
    os.makedirs(out_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(out_dir, f"merged_timeline_{stamp}.csv")

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for row in combined:
            writer.writerow(row)

    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()

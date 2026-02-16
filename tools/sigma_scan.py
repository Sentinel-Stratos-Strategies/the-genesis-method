#!/usr/bin/env python3
import argparse
import csv
import os
from datetime import datetime

TEXT_EXTS = {".txt", ".csv", ".tsv", ".json", ".log", ".html", ".htm", ".plist", ".xml"}


def extract_keywords(rule_path):
    keywords = []
    in_keywords = False
    with open(rule_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            stripped = line.strip()
            if stripped.startswith("keywords:"):
                in_keywords = True
                continue
            if in_keywords:
                if stripped.startswith("-"):
                    kw = stripped.lstrip("- ").strip().strip("\"")
                    if kw:
                        keywords.append(kw)
                elif stripped and not stripped.startswith("#"):
                    # exit keywords on next section
                    if not stripped.startswith("-"):
                        in_keywords = False
    return keywords


def scan_output(output_dir, rules_dir, max_bytes):
    rules = []
    for name in os.listdir(rules_dir):
        if name.endswith(".yml") or name.endswith(".yaml"):
            path = os.path.join(rules_dir, name)
            rules.append((name, extract_keywords(path)))

    results = []
    for root, _, files in os.walk(output_dir):
        for name in files:
            ext = os.path.splitext(name)[1].lower()
            if ext not in TEXT_EXTS:
                continue
            path = os.path.join(root, name)
            try:
                size = os.path.getsize(path)
            except OSError:
                continue
            if size > max_bytes:
                continue
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    data = f.read()
            except OSError:
                continue
            lower = data.lower()
            for rule_name, keywords in rules:
                for kw in keywords:
                    if kw and kw.lower() in lower:
                        results.append((rule_name, kw, os.path.relpath(path, output_dir)))
    return results


def write_report(output_dir, results):
    report_dir = os.path.join(output_dir, "_Sigma")
    os.makedirs(report_dir, exist_ok=True)
    csv_path = os.path.join(report_dir, "sigma_matches.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["rule", "keyword", "file"])
        writer.writerows(results)

    md_path = os.path.join(report_dir, "sigma_matches.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# Sigma Lite Matches\nGenerated: {datetime.now().isoformat(timespec='seconds')}\n\n")
        for rule, kw, path in results:
            f.write(f"- **{rule}** | `{kw}` | `{path}`\n")
    return csv_path, md_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--rules-dir", required=True)
    parser.add_argument("--max-bytes", type=int, default=5_000_000)
    args = parser.parse_args()

    if not os.path.isdir(args.rules_dir):
        print(f"Missing rules dir: {args.rules_dir}")
        return 1

    results = scan_output(args.output_dir, args.rules_dir, args.max_bytes)
    csv_path, md_path = write_report(args.output_dir, results)
    print(f"Wrote {csv_path}")
    print(f"Wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
import argparse
import csv
import ipaddress
import json
import os
import re
from collections import defaultdict
from datetime import datetime

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
UUID_RE = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b")
PHONE_RE = re.compile(r"\+?\d[\d\s().-]{7,}\d")
IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
IPV6_RE = re.compile(r"\b(?:[0-9A-Fa-f]{1,4}:){2,7}[0-9A-Fa-f]{1,4}\b")
DOMAIN_RE = re.compile(r"\b(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}\b")
ACCOUNT_KV_RE = re.compile(
    r"""(?ix)
    \b(?:account|username|user|appleid|icloud|login|caller_id|destination_caller_id)\b
    [^:=\n]{0,20}
    [:=]\s*
    ["']?([^\s,"']{3,120})
    """
)

TOKEN_PATTERNS = {
    "openai_keys": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "github_tokens": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    "aws_access_keys": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "gitlab_tokens": re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b"),
    "slack_tokens": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    "jwt_like_tokens": re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
}

TEXT_EXTS = {
    ".txt", ".csv", ".tsv", ".json", ".log", ".html", ".htm", ".plist", ".xml", ".md", ".yaml", ".yml"
}


def normalize_phone(raw):
    digits = re.sub(r"\D", "", raw)
    if 10 <= len(digits) <= 15:
        return digits
    return None


def is_valid_ipv4(ip):
    try:
        return ipaddress.ip_address(ip).version == 4
    except ValueError:
        return False


def is_valid_ipv6(ip):
    try:
        return ipaddress.ip_address(ip).version == 6
    except ValueError:
        return False


def sanitize_context(line, max_len=220):
    clean = " ".join(line.strip().split())
    if len(clean) > max_len:
        return clean[:max_len] + "..."
    return clean


def add_match(matches, dedupe, category, value, rel_path, line_no, context):
    value = value.strip()
    if not value:
        return
    key = (category, value, rel_path, line_no)
    if key in dedupe:
        return
    dedupe.add(key)
    matches.append(
        {
            "category": category,
            "value": value,
            "source": rel_path,
            "line": line_no,
            "context": context,
            "source_ref": f"{rel_path}:{line_no}",
        }
    )


def scan_output(output_dir, max_file_bytes):
    matches = []
    dedupe = set()
    files_scanned = 0
    bytes_scanned = 0
    skipped_large_files = 0

    for root, _, files in os.walk(output_dir):
        for name in files:
            path = os.path.join(root, name)
            ext = os.path.splitext(name)[1].lower()
            if ext not in TEXT_EXTS:
                continue

            try:
                size = os.path.getsize(path)
            except OSError:
                continue
            if size > max_file_bytes:
                skipped_large_files += 1
                continue

            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
            except OSError:
                continue

            files_scanned += 1
            bytes_scanned += size
            rel_path = os.path.relpath(path, output_dir)

            for line_no, line in enumerate(lines, 1):
                context = sanitize_context(line)

                for value in EMAIL_RE.findall(line):
                    add_match(matches, dedupe, "emails", value.lower(), rel_path, line_no, context)

                for value in UUID_RE.findall(line):
                    add_match(matches, dedupe, "uuids", value.lower(), rel_path, line_no, context)

                for value in PHONE_RE.findall(line):
                    normalized = normalize_phone(value)
                    if normalized:
                        add_match(matches, dedupe, "phones", normalized, rel_path, line_no, context)

                for value in IPV4_RE.findall(line):
                    if is_valid_ipv4(value):
                        add_match(matches, dedupe, "ipv4", value, rel_path, line_no, context)

                for value in IPV6_RE.findall(line):
                    if is_valid_ipv6(value):
                        add_match(matches, dedupe, "ipv6", value.lower(), rel_path, line_no, context)

                for value in DOMAIN_RE.findall(line):
                    if "@" in value:
                        continue
                    add_match(matches, dedupe, "domains", value.lower(), rel_path, line_no, context)

                for token_type, token_re in TOKEN_PATTERNS.items():
                    for value in token_re.findall(line):
                        add_match(matches, dedupe, f"tokens:{token_type}", value, rel_path, line_no, context)

                for value in ACCOUNT_KV_RE.findall(line):
                    add_match(matches, dedupe, "account_ids", value, rel_path, line_no, context)

    return {
        "files_scanned": files_scanned,
        "bytes_scanned": bytes_scanned,
        "skipped_large_files": skipped_large_files,
        "matches": matches,
    }


def write_outputs(output_dir, results, markdown_limit):
    out_dir = os.path.join(output_dir, "_Identifiers")
    os.makedirs(out_dir, exist_ok=True)

    json_path = os.path.join(out_dir, "identifiers.json")
    csv_path = os.path.join(out_dir, "identifiers.csv")
    summary_csv = os.path.join(out_dir, "identifiers_summary.csv")
    md_path = os.path.join(out_dir, "identifiers.md")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "output_dir": output_dir,
                "files_scanned": results["files_scanned"],
                "bytes_scanned": results["bytes_scanned"],
                "skipped_large_files": results["skipped_large_files"],
                "matches": results["matches"],
            },
            f,
            indent=2,
        )

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["category", "value", "source", "line", "source_ref", "context"])
        writer.writeheader()
        writer.writerows(results["matches"])

    grouped_values = defaultdict(set)
    grouped_rows = defaultdict(list)
    for row in results["matches"]:
        grouped_values[row["category"]].add(row["value"])
        grouped_rows[row["category"]].append(row)

    metrics = [
        ("generated_at", datetime.now().isoformat(timespec="seconds")),
        ("files_scanned", str(results["files_scanned"])),
        ("bytes_scanned", str(results["bytes_scanned"])),
        ("skipped_large_files", str(results["skipped_large_files"])),
    ]
    for category in sorted(grouped_values):
        safe_name = category.replace(":", "_")
        metrics.append((f"unique_{safe_name}", str(len(grouped_values[category]))))
        sample = ", ".join(sorted(grouped_values[category])[:10])
        metrics.append((f"sample_{safe_name}", sample))

    with open(summary_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["metric", "value"])
        writer.writerows(metrics)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Identifier Inventory\n\n")
        f.write(f"- Generated: {datetime.now().isoformat(timespec='seconds')}\n")
        f.write(f"- Files scanned: {results['files_scanned']}\n")
        f.write(f"- Bytes scanned: {results['bytes_scanned']}\n")
        f.write(f"- Skipped large files: {results['skipped_large_files']}\n\n")
        f.write(f"Full machine-readable exports:\n- `{csv_path}`\n- `{json_path}`\n\n")

        for category in sorted(grouped_rows):
            rows = grouped_rows[category]
            f.write(f"## {category} ({len(grouped_values[category])} unique)\n\n")
            f.write("| value | source |\n")
            f.write("|---|---|\n")
            count = 0
            for row in rows:
                f.write(f"| `{row['value']}` | `{row['source_ref']}` |\n")
                count += 1
                if count >= markdown_limit:
                    f.write(f"\n...truncated in markdown after {markdown_limit} rows; see CSV for full list.\n\n")
                    break
            f.write("\n")

    return json_path, csv_path, summary_csv, md_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--max-file-bytes", type=int, default=8_000_000)
    parser.add_argument("--markdown-limit", type=int, default=1500)
    args = parser.parse_args()

    if not os.path.isdir(args.output_dir):
        print(f"Output directory does not exist: {args.output_dir}")
        return 1

    results = scan_output(args.output_dir, args.max_file_bytes)
    json_path, csv_path, summary_csv, md_path = write_outputs(args.output_dir, results, args.markdown_limit)
    print(f"Wrote {json_path}")
    print(f"Wrote {csv_path}")
    print(f"Wrote {summary_csv}")
    print(f"Wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

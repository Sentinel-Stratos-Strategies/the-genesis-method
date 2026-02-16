#!/usr/bin/env python3
import argparse
import csv
import os
import re
from datetime import datetime

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
UUID_RE = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b")
PHONE_RE = re.compile(r"\+?\d[\d\s().-]{7,}\d")
IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
IPV6_RE = re.compile(r"\b(?:[0-9A-Fa-f]{1,4}:){2,7}[0-9A-Fa-f]{1,4}\b")
DOMAIN_RE = re.compile(r"\b(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}\b")
TOKEN_RE = re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b|\bghp_[A-Za-z0-9]{36}\b|\bglpat-[A-Za-z0-9\\-]{20,}\b|\bxox[baprs]-[A-Za-z0-9-]{10,}\b|\bsk-[A-Za-z0-9]{20,}\b")

TEXT_EXTS = {
    ".txt", ".csv", ".tsv", ".json", ".log", ".html", ".htm",
    ".plist", ".xml"
}


def normalize_phone(raw):
    digits = re.sub(r"\D", "", raw)
    if 10 <= len(digits) <= 15:
        return digits
    return None


def scan_output(output_dir, max_bytes):
    emails = set()
    phones = set()
    uuids = set()
    ipv4s = set()
    ipv6s = set()
    domains = set()
    tokens = set()
    files_scanned = 0
    bytes_scanned = 0

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
            if size > max_bytes:
                continue
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    data = f.read()
            except OSError:
                continue
            files_scanned += 1
            bytes_scanned += len(data)
            emails.update(EMAIL_RE.findall(data))
            uuids.update(UUID_RE.findall(data))
            ipv4s.update(IPV4_RE.findall(data))
            ipv6s.update(IPV6_RE.findall(data))
            for d in DOMAIN_RE.findall(data):
                if "@" not in d:
                    domains.add(d.lower())
            tokens.update(TOKEN_RE.findall(data))
            for match in PHONE_RE.findall(data):
                norm = normalize_phone(match)
                if norm:
                    phones.add(norm)

    return {
        "files_scanned": files_scanned,
        "bytes_scanned": bytes_scanned,
        "emails": sorted(emails),
        "phones": sorted(phones),
        "uuids": sorted(uuids),
        "ipv4s": sorted(ipv4s),
        "ipv6s": sorted(ipv6s),
        "domains": sorted(domains),
        "tokens": sorted(tokens),
    }


def write_summary(output_dir, data):
    summary_dir = os.path.join(output_dir, "_Summary")
    os.makedirs(summary_dir, exist_ok=True)
    csv_path = os.path.join(summary_dir, "summary.csv")
    md_path = os.path.join(summary_dir, "summary.md")

    def samples(values, max_items=5):
        return ", ".join(values[:max_items])

    rows = [
        ("output_dir", output_dir),
        ("generated_at", datetime.now().isoformat(timespec="seconds")),
        ("files_scanned", str(data["files_scanned"])),
        ("bytes_scanned", str(data["bytes_scanned"])),
        ("unique_emails", str(len(data["emails"]))),
        ("sample_emails", samples(data["emails"])),
        ("unique_phones", str(len(data["phones"]))),
        ("sample_phones", samples(data["phones"])),
        ("unique_uuids", str(len(data["uuids"]))),
        ("sample_uuids", samples(data["uuids"])),
        ("unique_ipv4", str(len(data["ipv4s"]))),
        ("sample_ipv4", samples(data["ipv4s"])),
        ("unique_ipv6", str(len(data["ipv6s"]))),
        ("sample_ipv6", samples(data["ipv6s"])),
        ("unique_domains", str(len(data["domains"]))),
        ("sample_domains", samples(data["domains"])),
        ("unique_tokens", str(len(data["tokens"]))),
        ("sample_tokens", samples(data["tokens"])),
    ]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["metric", "value"])
        writer.writerows(rows)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Output Summary\n\n")
        for metric, value in rows:
            f.write(f"- **{metric}**: {value}\n")

    return csv_path, md_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--max-bytes", type=int, default=5_000_000)
    args = parser.parse_args()

    data = scan_output(args.output_dir, args.max_bytes)
    csv_path, md_path = write_summary(args.output_dir, data)
    print(f"Wrote {csv_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()

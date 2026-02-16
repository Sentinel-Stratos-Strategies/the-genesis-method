#!/usr/bin/env python3
"""
Build OSINT targets from the latest Genesis inventory CSV.

This is designed to stay "legal-first" by default:
- Focuses on domains + public IPs + emails found in your own evidence outputs.
- Avoids person-level enrichment unless you explicitly add those targets yourself.

Output format (targets file):
  domain:example.com
  ipv4:1.2.3.4
  ipv6:2001:db8::1
  email:user@example.com

By default this script is intentionally conservative:
- It excludes common "background noise" domains (Apple + major CDNs/providers).
- It limits the number of domains written (so downstream APIs don't get hammered).

If you really want everything, pass a large `--max-domains`, but expect slow runs and rate limits.
"""

from __future__ import annotations

import argparse
import csv
import ipaddress
import os
import re
from datetime import datetime
from pathlib import Path


EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")

# TLDs that are almost always file extensions in forensic outputs (avoid false "domains").
FILELIKE_TLDS_EXCLUDE = {
    "mov",
    "mp4",
    "m4v",
    "avi",
    "mkv",
    "jpg",
    "jpeg",
    "png",
    "gif",
    "heic",
    "pdf",
    "txt",
    "json",
    "plist",
    "xml",
    "yaml",
    "yml",
    "log",
    "db",
    "sqlite",
    "csv",
    "tsv",
    "zip",
    "rar",
    "js",
    "py",
    "fs",
    "le",
    "so",
    "gz",
    "tar",
    "7z",
    "dmg",
    "iso",
    "aea",
    "app",
    "asset",
    "bundle",
    "html",
    "xlsx",
    "framework",
    "kext",
    "mtree",
    "trustcache",
    "history",
    "pluginpayloadattachment",
    "post",
}

# Small allowlist for gTLDs commonly seen in defensive OSINT.
# Everything else that isn't a country code (len==2) is treated as low-confidence noise.
COMMON_GTLD_ALLOWLIST = {
    "com",
    "net",
    "org",
    "edu",
    "gov",
    "mil",
    "int",
    "info",
    "biz",
    "pro",
    "io",
    "co",
    "me",
    "tv",
    "ai",
    "app",
    "dev",
    "cloud",
    "site",
    "online",
    "support",
    "store",
    "shop",
    "live",
}

# Reverse-DNS bundle IDs (com.apple.foo) are common in forensic outputs but
# are not useful as OSINT "domains" by default.
REVERSE_DNS_PREFIXES = {"com", "net", "org", "io", "edu", "gov"}

UUID_LABEL_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")

# Noise filters for "run everywhere" OSINT. You can override with --include-apple-domains.
DEFAULT_DOMAIN_SUFFIX_EXCLUDES = (
    ".apple.com",
    ".icloud.com",
    ".icloud-content.com",
    ".mzstatic.com",
    # Common OS noise / CDNs / large providers (keep OSINT focused).
    ".google.com",
    ".gstatic.com",
    ".googleapis.com",
    ".microsoft.com",
    ".windows.net",
    ".azure.com",
    ".azureedge.net",
    ".office.com",
    ".live.com",
    ".outlook.com",
    ".amazonaws.com",
    ".cloudfront.net",
    ".akamai.net",
    ".akamaiedge.net",
    ".fastly.net",
    ".cloudflare.com",
)
DEFAULT_DOMAIN_EXACT_EXCLUDES = {
    "apple.com",
    "icloud.com",
    "icloud-content.com",
    "mzstatic.com",
    "google.com",
    "microsoft.com",
    "amazonaws.com",
    "cloudflare.com",
}

SUSPICIOUS_TLDS = {
    # Commonly abused TLDs (heuristic).
    "top",
    "xyz",
    "ru",
    "su",
    "cn",
    "tk",
    "ml",
    "ga",
    "cf",
    "gq",
    "work",
    "click",
    "cam",
    "life",
    "lol",
    "zip",
    "mov",
}

SUSPICIOUS_KEYWORDS = (
    "login",
    "secure",
    "verify",
    "verification",
    "update",
    "account",
    "support",
    "helpdesk",
    "appleid",
    "icloud",
    "microsoft",
    "office",
    "outlook",
    "paypal",
)


def score_domain(domain: str) -> int:
    """
    Heuristic scoring to prioritize domains that are more likely to be relevant
    in compromise investigations (phishing / infra / unusual hosting).
    """
    d = domain.lower().rstrip(".")
    parts = d.split(".")
    if len(parts) < 2:
        return 0

    tld = parts[-1]
    score = 0

    if d.endswith(".onion"):
        score += 10
    if any(p.startswith("xn--") for p in parts):
        score += 6
    if tld in SUSPICIOUS_TLDS:
        score += 5
    if any(k in d for k in SUSPICIOUS_KEYWORDS):
        score += 3

    # Weird-looking labels are often higher signal than normal corp domains.
    longest = max((len(p) for p in parts[:-1]), default=0)
    if longest >= 20:
        score += 2
    if any(sum(c.isdigit() for c in p) >= 5 for p in parts[:-1]):
        score += 2
    if any(p.count("-") >= 2 for p in parts[:-1]):
        score += 1

    # Deep subdomains can be tracking/CDN noise, but can also indicate phishing.
    if d.count(".") >= 3:
        score += 1

    return score


def latest_inventory(report_dir: Path) -> Path | None:
    paths = sorted(report_dir.glob("genesis_inventory_*.csv"), reverse=True)
    return paths[0] if paths else None


def is_public_ip(value: str) -> bool:
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return False
    return not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved)


def is_domain(value: str) -> bool:
    v = value.strip().lower().rstrip(".")
    if not v or len(v) > 253:
        return False
    if "/" in v or " " in v:
        return False
    if v.endswith(".local"):
        return False
    if v.startswith("appdomain-") or v.startswith("appdomaingroup-"):
        return False
    parts = v.split(".")
    if len(parts) < 2:
        return False
    if len(parts) >= 3:
        if parts[0] in REVERSE_DNS_PREFIXES:
            return False
        # Some artifacts prefix reverse-DNS with a digit (e.g., "4com.apple...").
        for pre in REVERSE_DNS_PREFIXES:
            if parts[0].endswith(pre) and parts[0][:-len(pre)].isdigit():
                return False
    tld = parts[-1]
    if len(tld) < 2 or not tld.isalpha():
        return False
    if tld in FILELIKE_TLDS_EXCLUDE:
        return False
    if not (len(tld) == 2 or tld in COMMON_GTLD_ALLOWLIST or tld in SUSPICIOUS_TLDS):
        return False
    for lbl in parts[:-1]:
        if not lbl or len(lbl) > 63:
            return False
        if UUID_LABEL_RE.match(lbl):
            return False
        # Labels cannot start/end with hyphens.
        if lbl[0] == "-" or lbl[-1] == "-":
            return False
        if not re.fullmatch(r"[a-z0-9-]+", lbl):
            return False
    return True


def is_email(value: str) -> bool:
    v = value.strip().lower()
    return bool(EMAIL_RE.match(v))


def should_exclude_domain(domain: str, include_apple_domains: bool) -> bool:
    d = domain.lower().rstrip(".")
    if include_apple_domains:
        return False
    if d in DEFAULT_DOMAIN_EXACT_EXCLUDES:
        return True
    for suf in DEFAULT_DOMAIN_SUFFIX_EXCLUDES:
        if d.endswith(suf):
            return True
    return False


def read_inventory(csv_path: Path) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    with csv_path.open("r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cat = (row.get("category") or "").strip()
            val = (row.get("value") or "").strip()
            if cat and val:
                rows.append((cat, val))
    return rows


def write_targets(out_file: Path, source_inventory: Path, lines: list[str]) -> None:
    out_file.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with out_file.open("w", encoding="utf-8") as f:
        f.write("# The Genesis Method - Auto OSINT Targets\n")
        f.write(f"# Generated: {stamp}\n")
        f.write(f"# Source inventory: {source_inventory}\n")
        f.write("# Format: kind:value\n\n")
        for line in lines:
            f.write(line + "\n")


def merge_into_file(merge_path: Path, lines: list[str]) -> None:
    marker_begin = "# === GENESIS AUTO TARGETS BEGIN ==="
    marker_end = "# === GENESIS AUTO TARGETS END ==="
    payload = "\n".join([marker_begin] + lines + [marker_end]) + "\n"

    if not merge_path.exists():
        merge_path.parent.mkdir(parents=True, exist_ok=True)
        merge_path.write_text(payload, encoding="utf-8")
        return

    text = merge_path.read_text(encoding="utf-8", errors="ignore")
    if marker_begin in text and marker_end in text:
        pre = text.split(marker_begin, 1)[0].rstrip() + "\n"
        post = text.split(marker_end, 1)[1].lstrip("\n")
        merge_path.write_text(pre + payload + post, encoding="utf-8")
        return

    # Append if no markers exist.
    if not text.endswith("\n"):
        text += "\n"
    merge_path.write_text(text + "\n" + payload, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir-house", default=os.environ.get("OUT_DIR_HOUSE", "/Users/House/EVIDENCE"))
    parser.add_argument("--report-dir", default=None, help="Override report dir (defaults to <out-dir-house>/house/_Report).")
    parser.add_argument("--inventory-csv", default=None, help="Explicit inventory CSV (genesis_inventory_*.csv).")
    parser.add_argument("--out-file", default=None, help="Write targets file here (defaults to <out-dir-house>/house/_OSINT/targets_<stamp>.txt).")
    parser.add_argument("--include-apple-domains", action="store_true", help="Include apple.com / icloud.com etc.")
    parser.add_argument("--max-domains", type=int, default=250, help="Limit number of domains written (default: 250). Use -1 for no limit.")
    parser.add_argument("--max-ips", type=int, default=200, help="Limit total IPs written (v4 always included first). Use -1 for no limit.")
    parser.add_argument("--max-emails", type=int, default=50, help="Limit number of emails written. Use -1 for no limit.")
    parser.add_argument("--merge-into", default=None, help="Optional path to merge targets into (adds/replaces a GENESIS AUTO block).")
    args = parser.parse_args()

    out_dir_house = Path(args.out_dir_house)
    report_dir = Path(args.report_dir) if args.report_dir else (out_dir_house / "house" / "_Report")

    inv_path: Path | None
    if args.inventory_csv:
        inv_path = Path(args.inventory_csv)
    else:
        inv_path = latest_inventory(report_dir)

    if not inv_path or not inv_path.exists():
        print(f"No Genesis inventory CSV found in: {report_dir}")
        return 1

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = Path(args.out_file) if args.out_file else (out_dir_house / "house" / "_OSINT" / f"targets_{stamp}.txt")

    rows = read_inventory(inv_path)

    domains: set[str] = set()
    ipv4: set[str] = set()
    ipv6: set[str] = set()
    emails: set[str] = set()

    for cat, val in rows:
        cat = cat.strip().lower()
        v = val.strip()

        if cat == "domains":
            d = v.lower().rstrip(".")
            if is_domain(d) and not should_exclude_domain(d, args.include_apple_domains):
                domains.add(d)
        elif cat == "emails":
            e = v.lower()
            if is_email(e):
                emails.add(e)
        elif cat == "ipv4":
            ip = v.strip()
            if is_public_ip(ip):
                ipv4.add(ip)
        elif cat == "ipv6":
            ip = v.strip().lower()
            if is_public_ip(ip):
                ipv6.add(ip)

    # Apply limits (domain-heavy inventories can contain thousands of low-signal domains).
    domains_all = sorted(domains, key=lambda d: (-score_domain(d), d))
    if args.max_domains >= 0:
        domains_all = domains_all[: args.max_domains]

    ipv4_all = sorted(ipv4)
    ipv6_all = sorted(ipv6)
    if args.max_ips >= 0:
        ipv6_budget = max(0, int(args.max_ips) - len(ipv4_all))
        ipv6_all = ipv6_all[:ipv6_budget]

    emails_all = sorted(emails)
    if args.max_emails >= 0:
        emails_all = emails_all[: args.max_emails]

    lines: list[str] = []
    for d in domains_all:
        lines.append(f"domain:{d}")
    for ip in ipv4_all:
        lines.append(f"ipv4:{ip}")
    for ip in ipv6_all:
        lines.append(f"ipv6:{ip}")
    for e in emails_all:
        lines.append(f"email:{e}")

    write_targets(out_file, inv_path, lines)
    print(f"Wrote targets: {out_file}")
    print(f"Counts (raw): domains={len(domains)} ipv4={len(ipv4)} ipv6={len(ipv6)} emails={len(emails)}")
    print(f"Counts (written): domains={len(domains_all)} ipv4={len(ipv4_all)} ipv6={len(ipv6_all)} emails={len(emails_all)}")

    if args.merge_into:
        merge_path = Path(args.merge_into)
        merge_into_file(merge_path, lines)
        print(f"Merged targets into: {merge_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
import argparse
import json
import csv
import os
import urllib.request


def read_summary(summary_csv):
    data = {}
    if not os.path.exists(summary_csv):
        return data
    with open(summary_csv, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) != 2 or row[0] == "metric":
                continue
            data[row[0]] = row[1]
    return data


def vt_ip(ip, api_key):
    url = f"https://www.virustotal.com/api/v3/ip_addresses/{ip}"
    req = urllib.request.Request(url, headers={"x-apikey": api_key})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def abuse_ip(ip, api_key):
    url = f"https://api.abuseipdb.com/api/v2/check?ipAddress={ip}&maxAgeInDays=180"
    req = urllib.request.Request(url, headers={"Key": api_key, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    summary_csv = os.path.join(args.output_dir, "_Summary", "summary.csv")
    summary = read_summary(summary_csv)

    vt_key = os.environ.get("VT_API_KEY")
    abuse_key = os.environ.get("ABUSEIPDB_KEY")

    enrich_dir = os.path.join(args.output_dir, "_Enrichment")
    os.makedirs(enrich_dir, exist_ok=True)

    if not vt_key and not abuse_key:
        with open(os.path.join(enrich_dir, "README.txt"), "w", encoding="utf-8") as f:
            f.write("Set VT_API_KEY and/or ABUSEIPDB_KEY to enable enrichment.\n")
        return 0

    results = {"virustotal": {}, "abuseipdb": {}}
    ips = summary.get("sample_ipv4", "").split(", ") if summary.get("sample_ipv4") else []

    for ip in ips:
        if vt_key:
            try:
                results["virustotal"][ip] = vt_ip(ip, vt_key)
            except Exception as exc:
                results["virustotal"][ip] = {"error": str(exc)}
        if abuse_key:
            try:
                results["abuseipdb"][ip] = abuse_ip(ip, abuse_key)
            except Exception as exc:
                results["abuseipdb"][ip] = {"error": str(exc)}

    with open(os.path.join(enrich_dir, "ioc_enrichment.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("Wrote enrichment output")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

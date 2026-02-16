#!/usr/bin/env python3
import argparse
import csv
import os
from datetime import datetime


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


def latest_dir(glob_path):
    import glob
    matches = sorted(glob.glob(glob_path), reverse=True)
    return matches[0] if matches else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-label", required=True)
    parser.add_argument("--out-base", required=True)
    args = parser.parse_args()

    user_root = os.path.join(args.out_base, args.user_label)
    macapt = latest_dir(os.path.join(user_root, "macapt_*"))
    ileapp = latest_dir(os.path.join(user_root, "ileapp_*"))
    xleapp = latest_dir(os.path.join(user_root, "xleapp_*"))

    sections = []
    for label, path in [("macapt", macapt), ("ileapp", ileapp), ("xleapp", xleapp)]:
        if not path:
            continue
        summary = read_summary(os.path.join(path, "_Summary", "summary.csv"))
        sections.append((label, path, summary))

    report_dir = os.path.join(user_root, "_Report")
    os.makedirs(report_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_md = os.path.join(report_dir, f"report_{stamp}.md")
    report_html = os.path.join(report_dir, f"report_{stamp}.html")

    with open(report_md, "w", encoding="utf-8") as f:
        f.write(f"# Sentinel Report ({args.user_label})\n\n")
        f.write(f"Generated: {datetime.now().isoformat(timespec='seconds')}\n\n")
        for label, path, summary in sections:
            f.write(f"## {label.upper()}\n")
            f.write(f"Output: {path}\n\n")
            for key in ["unique_emails", "unique_phones", "unique_uuids", "unique_ipv4", "unique_ipv6", "unique_domains", "unique_tokens"]:
                if key in summary:
                    f.write(f"- {key}: {summary[key]}\n")
            f.write("\n")

    with open(report_html, "w", encoding="utf-8") as f:
        f.write("<html><head><meta charset='utf-8'><title>Sentinel Report</title></head><body>")
        f.write(f"<h1>Sentinel Report ({args.user_label})</h1>")
        f.write(f"<p>Generated: {datetime.now().isoformat(timespec='seconds')}</p>")
        for label, path, summary in sections:
            f.write(f"<h2>{label.upper()}</h2><p>Output: {path}</p><ul>")
            for key in ["unique_emails", "unique_phones", "unique_uuids", "unique_ipv4", "unique_ipv6", "unique_domains", "unique_tokens"]:
                if key in summary:
                    f.write(f"<li>{key}: {summary[key]}</li>")
            f.write("</ul>")
        f.write("</body></html>")

    print(f"Wrote {report_md}")
    print(f"Wrote {report_html}")


if __name__ == "__main__":
    main()

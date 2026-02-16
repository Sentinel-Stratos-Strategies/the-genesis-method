#!/usr/bin/env python3
import argparse
import csv
import glob
import json
import os
import re
import ssl
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import urllib.error
import urllib.request

CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")


def latest_dir(glob_path):
    matches = sorted(glob.glob(glob_path), reverse=True)
    return matches[0] if matches else None


def mask_value(category, value):
    if category.startswith("tokens:"):
        if len(value) <= 12:
            return value
        return f"{value[:6]}...{value[-4:]}"
    return value


def clean_text(value, max_len=500):
    if value is None:
        return ""
    text = str(value)
    text = CONTROL_CHARS_RE.sub(" ", text)
    text = " ".join(text.split())
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text


def read_text(path, max_chars=20000):
    try:
        data = Path(path).read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""
    if len(data) > max_chars:
        return data[:max_chars] + "\n\n[TRUNCATED]"
    return data


def read_metric_csv(path):
    data = {}
    if not Path(path).exists():
        return data
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) != 2:
                continue
            if row[0] == "metric":
                continue
            data[row[0]] = row[1]
    return data


def extract_output_text(resp_json):
    text_parts = []
    for item in resp_json.get("output", []) or []:
        for part in item.get("content", []) or []:
            if part.get("type") == "output_text":
                text_parts.append(part.get("text", ""))
    return "\n".join([t for t in text_parts if t])


def call_openai(api_key, payload):
    context = None
    custom_cafile = os.environ.get("SSL_CERT_FILE")
    if custom_cafile and Path(custom_cafile).exists():
        context = ssl.create_default_context(cafile=custom_cafile)
    else:
        try:
            import certifi  # type: ignore

            context = ssl.create_default_context(cafile=certifi.where())
        except Exception:
            context = ssl.create_default_context()

    req = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120, context=context) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="ignore")
        except Exception:
            body = ""
        detail = body.strip() if body else str(exc)
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc


def is_model_access_error(err_text):
    text = err_text.lower()
    return (
        "model_not_found" in text
        or "does not have access to model" in text
        or "requested model" in text and "does not exist" in text
    )


def collect_output_dirs(user_root):
    output_dirs = []
    root = Path(user_root)
    if not root.is_dir():
        return output_dirs
    for pattern in ("macapt_*", "ileapp_*", "xleapp_*"):
        for path in root.glob(pattern):
            if path.is_dir():
                output_dirs.append(path)
    output_dirs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return output_dirs


def candidate_user_roots(subject_label, out_base):
    roots = []
    primary = Path(out_base) / subject_label
    roots.append(primary)

    project_root = Path(__file__).resolve().parents[1]
    legacy_local = project_root / "forensics_out" / subject_label
    roots.append(legacy_local)

    if subject_label == "fam":
        roots.append(Path("/Users/fam/forensics_out") / subject_label)

    deduped = []
    seen = set()
    for root in roots:
        root_str = str(root)
        if root_str in seen:
            continue
        seen.add(root_str)
        deduped.append(root)
    return deduped


def ensure_identifiers(output_dir):
    identifiers_csv = Path(output_dir) / "_Identifiers" / "identifiers.csv"
    if identifiers_csv.exists():
        return
    scan_script = Path(__file__).resolve().parent / "identifiers_scan.py"
    if not scan_script.exists():
        return
    subprocess.run(
        [sys.executable, str(scan_script), "--output-dir", str(output_dir)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def parse_identifiers(output_dir, subject_label):
    rows = []
    id_csv = Path(output_dir) / "_Identifiers" / "identifiers.csv"
    if not id_csv.exists():
        return rows
    with open(id_csv, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for row in reader:
            category = clean_text(row.get("category") or "", max_len=120)
            value = clean_text(row.get("value") or "", max_len=300)
            source = clean_text(row.get("source") or "", max_len=300)
            line = clean_text(row.get("line") or "", max_len=40)
            context = clean_text(row.get("context") or "", max_len=300)
            if not category or not value:
                continue
            source_abs = str(Path(output_dir) / source) if source else str(Path(output_dir))
            source_ref = clean_text(f"{source_abs}:{line}" if line else source_abs, max_len=500)
            rows.append(
                {
                    "subject": subject_label,
                    "artifact_dir": str(output_dir),
                    "artifact_name": clean_text(Path(output_dir).name, max_len=120),
                    "category": category,
                    "value": value,
                    "source_ref": source_ref,
                    "context": context,
                }
            )
    return rows


def parse_sigma(output_dir, subject_label):
    out = []
    sigma_csv = Path(output_dir) / "_Sigma" / "sigma_matches.csv"
    if not sigma_csv.exists():
        return out
    with open(sigma_csv, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rel_file = (row.get("file") or "").strip()
            out.append(
                {
                    "type": "sigma",
                    "subject": subject_label,
                    "artifact_name": clean_text(Path(output_dir).name, max_len=120),
                    "rule": clean_text(row.get("rule") or "", max_len=180),
                    "keyword": clean_text(row.get("keyword") or "", max_len=180),
                    "evidence_ref": clean_text(str(sigma_csv), max_len=500),
                    "target_ref": clean_text(str(Path(output_dir) / rel_file) if rel_file else str(output_dir), max_len=500),
                }
            )
    return out


def parse_yara(output_dir, subject_label):
    out = []
    yara_txt = Path(output_dir) / "_YARA" / "yara_matches.txt"
    if not yara_txt.exists():
        return out
    with open(yara_txt, "r", encoding="utf-8", errors="ignore") as f:
        for line_no, raw in enumerate(f, 1):
            line = raw.strip()
            if not line:
                continue
            if line.startswith("YARA scan report") or line.startswith("Generated:") or line.startswith("Rules:") or line.startswith("Target:"):
                continue
            parts = line.split(maxsplit=1)
            if len(parts) == 2:
                rule, target = parts
            else:
                rule, target = "match", line
            out.append(
                {
                    "type": "yara",
                    "subject": subject_label,
                    "artifact_name": clean_text(Path(output_dir).name, max_len=120),
                    "rule": clean_text(rule, max_len=180),
                    "keyword": "",
                    "evidence_ref": clean_text(f"{yara_txt}:{line_no}", max_len=400),
                    "target_ref": clean_text(target, max_len=400),
                }
            )
    return out


def parse_clamav(output_dir, subject_label):
    out = []
    clam_dir = Path(output_dir) / "_ClamAV"
    if not clam_dir.exists():
        return out
    for log_file in sorted(clam_dir.glob("clamav_*.log"), key=lambda p: p.stat().st_mtime, reverse=True):
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            for line_no, raw in enumerate(f, 1):
                if " FOUND" not in raw:
                    continue
                line = raw.strip()
                sig = "FOUND"
                target = line
                if ": " in line:
                    target, sig = line.rsplit(": ", 1)
                out.append(
                    {
                    "type": "clamav",
                    "subject": subject_label,
                    "artifact_name": clean_text(Path(output_dir).name, max_len=120),
                    "rule": clean_text(sig, max_len=220),
                    "keyword": "",
                    "evidence_ref": clean_text(f"{log_file}:{line_no}", max_len=400),
                    "target_ref": clean_text(target, max_len=400),
                    }
                )
    return out


def parse_enrichment(output_dir, subject_label):
    out = []
    enrich_json = Path(output_dir) / "_Enrichment" / "ioc_enrichment.json"
    if not enrich_json.exists():
        return out
    try:
        data = json.loads(enrich_json.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return out

    for source_name in ("virustotal", "abuseipdb"):
        source_data = data.get(source_name, {})
        if not isinstance(source_data, dict):
            continue
        for indicator, details in source_data.items():
            if isinstance(details, dict):
                detail_text = json.dumps(details)[:280]
            else:
                detail_text = str(details)
            out.append(
                {
                    "type": "enrichment",
                    "subject": subject_label,
                    "artifact_name": clean_text(Path(output_dir).name, max_len=120),
                    "rule": clean_text(source_name, max_len=80),
                    "keyword": clean_text(detail_text, max_len=280),
                    "evidence_ref": clean_text(str(enrich_json), max_len=300),
                    "target_ref": clean_text(indicator, max_len=220),
                }
            )
    return out


def collect_subject_data(subject_label, out_base):
    user_root = Path(out_base) / subject_label
    output_dirs = []
    seen_dirs = set()
    for root in candidate_user_roots(subject_label, out_base):
        for output_dir in collect_output_dirs(root):
            out_str = str(output_dir)
            if out_str in seen_dirs:
                continue
            seen_dirs.add(out_str)
            output_dirs.append(output_dir)
    output_dirs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    artifacts = []
    identifier_rows = []
    security_rows = []
    source_docs = []

    for output_dir in output_dirs:
        ensure_identifiers(output_dir)
        artifact = {
            "subject": subject_label,
            "artifact_name": clean_text(output_dir.name, max_len=120),
            "output_dir": clean_text(str(output_dir), max_len=500),
            "summary": read_metric_csv(output_dir / "_Summary" / "summary.csv"),
            "identifier_summary": read_metric_csv(output_dir / "_Identifiers" / "identifiers_summary.csv"),
        }
        artifacts.append(artifact)

        source_docs.extend(
            [
                str(output_dir / "_Summary" / "summary.md"),
                str(output_dir / "_Summary" / "summary.csv"),
                str(output_dir / "_Identifiers" / "identifiers.md"),
                str(output_dir / "_Identifiers" / "identifiers.csv"),
                str(output_dir / "_Sigma" / "sigma_matches.csv"),
                str(output_dir / "_YARA" / "yara_matches.txt"),
            ]
        )

        identifier_rows.extend(parse_identifiers(output_dir, subject_label))
        security_rows.extend(parse_sigma(output_dir, subject_label))
        security_rows.extend(parse_yara(output_dir, subject_label))
        security_rows.extend(parse_clamav(output_dir, subject_label))
        security_rows.extend(parse_enrichment(output_dir, subject_label))

    source_docs = [p for p in source_docs if Path(p).exists()]

    return {
        "subject": subject_label,
        "out_base": str(out_base),
        "user_root": str(user_root),
        "artifacts": artifacts,
        "identifier_rows": identifier_rows,
        "security_rows": security_rows,
        "source_docs": source_docs,
    }


def aggregate_identifiers(identifier_rows):
    grouped = defaultdict(dict)
    for row in identifier_rows:
        category = row["category"]
        value = row["value"]
        if value not in grouped[category]:
            grouped[category][value] = {
                "value": value,
                "hits": 0,
                "subjects": set(),
                "artifacts": set(),
                "evidence_refs": [],
            }
        entry = grouped[category][value]
        entry["hits"] += 1
        entry["subjects"].add(row["subject"])
        entry["artifacts"].add(row["artifact_name"])
        if len(entry["evidence_refs"]) < 12:
            entry["evidence_refs"].append(row["source_ref"])

    category_counts = {}
    normalized = {}
    for category, values in grouped.items():
        normalized_rows = []
        for value, entry in values.items():
            normalized_rows.append(
                {
                    "value": value,
                    "hits": entry["hits"],
                    "subjects": sorted(entry["subjects"]),
                    "artifacts": sorted(entry["artifacts"]),
                    "evidence_refs": entry["evidence_refs"],
                }
            )
        normalized_rows.sort(key=lambda x: (-x["hits"], x["value"]))
        normalized[category] = normalized_rows
        category_counts[category] = len(normalized_rows)
    return normalized, category_counts


def write_inventory_csv(path, normalized_identifiers):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["category", "value", "hits", "subjects", "artifacts", "evidence_refs"])
        for category in sorted(normalized_identifiers):
            for row in normalized_identifiers[category]:
                writer.writerow(
                    [
                        category,
                        row["value"],
                        row["hits"],
                        ", ".join(row["subjects"]),
                        ", ".join(row["artifacts"]),
                        " | ".join(row["evidence_refs"]),
                    ]
                )


def build_ai_payload(primary_subject, subject_data, normalized_identifiers, category_counts, security_rows, model):
    condensed = {
        "primary_subject": primary_subject,
        "subjects": [s["subject"] for s in subject_data],
        "artifact_counts": {s["subject"]: len(s["artifacts"]) for s in subject_data},
        "identifier_category_counts": category_counts,
        "top_identifiers": {},
        "security_event_count": len(security_rows),
        "security_samples": [],
    }

    for category in sorted(normalized_identifiers):
        condensed["top_identifiers"][category] = [
            mask_value(category, row["value"]) for row in normalized_identifiers[category][:20]
        ]

    for row in security_rows[:80]:
        condensed["security_samples"].append(
            {
                "type": row["type"],
                "subject": row["subject"],
                "artifact": row["artifact_name"],
                "rule": row["rule"],
                "target": row["target_ref"],
                "evidence_ref": row["evidence_ref"],
            }
        )

    instructions = (
        "You are the Genesis Analyst. Provide a concise forensic synthesis using only supplied evidence. "
        "Focus on cross-subject overlaps, suspicious indicators, and high-priority follow-ups. "
        "Cite explicit evidence references exactly as provided. Do not invent data."
    )

    user_input = (
        f"Genesis consolidated analysis request for primary subject '{primary_subject}'.\n"
        f"Timestamp: {datetime.now().isoformat(timespec='seconds')}\n\n"
        "Evidence snapshot JSON:\n"
        + json.dumps(condensed, indent=2)
    )

    payload = {
        "model": model,
        "instructions": instructions,
        "input": user_input,
        "temperature": 0.1,
    }
    return payload


def call_openai_with_fallback(api_key, payload, requested_model):
    fallback_models = os.environ.get("GENESIS_MODEL_FALLBACKS", "gpt-4o-mini,gpt-4o")
    model_candidates = [requested_model]
    for m in [x.strip() for x in fallback_models.split(",") if x.strip()]:
        if m not in model_candidates:
            model_candidates.append(m)

    resp_json = None
    chosen_model = requested_model
    last_error = ""
    for candidate in model_candidates:
        payload["model"] = candidate
        try:
            resp_json = call_openai(api_key, payload)
            chosen_model = candidate
            break
        except RuntimeError as exc:
            err_text = str(exc)
            last_error = err_text
            if is_model_access_error(err_text):
                continue
            return None, None, err_text
        except Exception as exc:
            return None, None, str(exc)

    if resp_json is None:
        return None, None, last_error or "Model selection failed."
    return resp_json, chosen_model, ""


def write_markdown_report(
    out_path,
    primary_subject,
    subject_data,
    normalized_identifiers,
    category_counts,
    security_rows,
    source_docs,
    ai_text,
    ai_model,
    ai_error,
    max_per_category,
):
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"# Genesis Analyst ({primary_subject})\n\n")
        f.write(f"Generated: {datetime.now().isoformat(timespec='seconds')}\n\n")

        if ai_text:
            f.write("## Analyst Synthesis (OpenAI)\n\n")
            f.write(f"Model used: `{ai_model}`\n\n")
            f.write(ai_text.strip() + "\n\n")
        elif ai_error:
            f.write("## Analyst Synthesis (OpenAI)\n\n")
            f.write(f"OpenAI synthesis unavailable: `{ai_error}`\n\n")
        else:
            f.write("## Analyst Synthesis (OpenAI)\n\n")
            f.write("OpenAI synthesis skipped (no API key). Local evidence inventory generated below.\n\n")

        f.write("## Scope\n\n")
        f.write("| Subject | Artifact | Output Directory |\n")
        f.write("|---|---|---|\n")
        for sub in subject_data:
            for artifact in sub["artifacts"]:
                f.write(f"| {sub['subject']} | {artifact['artifact_name']} | `{artifact['output_dir']}` |\n")
        f.write("\n")

        f.write("## Identifier Category Counts\n\n")
        f.write("| Category | Unique Values |\n")
        f.write("|---|---|\n")
        for category in sorted(category_counts):
            f.write(f"| `{category}` | {category_counts[category]} |\n")
        f.write("\n")

        for category in sorted(normalized_identifiers):
            rows = normalized_identifiers[category]
            f.write(f"## {category}\n\n")
            f.write("| Value | Hits | Subject(s) | Artifact(s) | Source Reference(s) |\n")
            f.write("|---|---:|---|---|---|\n")
            for idx, row in enumerate(rows):
                if idx >= max_per_category:
                    f.write(
                        f"| _truncated_ | - | - | - | Showing first {max_per_category} values. See CSV for full inventory. |\n"
                    )
                    break
                refs = "<br>".join(f"`{ref}`" for ref in row["evidence_refs"][:8])
                value = row["value"].replace("|", "\\|")
                subjects = ", ".join(row["subjects"])
                artifacts = ", ".join(row["artifacts"])
                f.write(f"| `{value}` | {row['hits']} | {subjects} | {artifacts} | {refs} |\n")
            f.write("\n")

        f.write("## Security Findings\n\n")
        f.write("| Type | Subject | Artifact | Rule/Detector | Target | Evidence |\n")
        f.write("|---|---|---|---|---|---|\n")
        if security_rows:
            for row in security_rows:
                rule = (row.get("rule") or "").replace("|", "\\|")
                target = (row.get("target_ref") or "").replace("|", "\\|")
                ev = (row.get("evidence_ref") or "").replace("|", "\\|")
                f.write(
                    f"| {row['type']} | {row['subject']} | {row['artifact_name']} | `{rule}` | `{target}` | `{ev}` |\n"
                )
        else:
            f.write("| _none_ | - | - | - | - | - |\n")
        f.write("\n")

        f.write("## Source Documents Reviewed\n\n")
        for doc in sorted(set(source_docs)):
            f.write(f"- `{clean_text(doc, max_len=500)}`\n")
        f.write("\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-label", required=True)
    parser.add_argument("--out-base", required=True)
    parser.add_argument("--peer-label")
    parser.add_argument("--peer-out-base")
    parser.add_argument("--model", default=os.environ.get("GENESIS_MODEL", "gpt-4.1"))
    parser.add_argument("--max-per-category", type=int, default=2000)
    args = parser.parse_args()

    primary_subject = args.user_label
    primary_user_root = Path(args.out_base) / primary_subject
    report_dir = primary_user_root / "_Report"
    report_dir.mkdir(parents=True, exist_ok=True)

    subjects = [(args.user_label, args.out_base)]
    if args.peer_label and args.peer_out_base:
        subjects.append((args.peer_label, args.peer_out_base))

    subject_data = []
    all_identifier_rows = []
    all_security_rows = []
    all_source_docs = []

    for label, base in subjects:
        data = collect_subject_data(label, base)
        subject_data.append(data)
        all_identifier_rows.extend(data["identifier_rows"])
        all_security_rows.extend(data["security_rows"])
        all_source_docs.extend(data["source_docs"])

    normalized_identifiers, category_counts = aggregate_identifiers(all_identifier_rows)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_md = report_dir / f"genesis_analyst_{stamp}.md"
    out_json = report_dir / f"genesis_analyst_{stamp}.json"
    out_csv = report_dir / f"genesis_inventory_{stamp}.csv"

    write_inventory_csv(out_csv, normalized_identifiers)

    api_key = os.environ.get("OPENAI_API_KEY")
    ai_text = ""
    ai_model = ""
    ai_error = ""
    openai_raw = None

    if api_key:
        payload = build_ai_payload(
            primary_subject,
            subject_data,
            normalized_identifiers,
            category_counts,
            all_security_rows,
            args.model,
        )
        openai_raw, chosen_model, error_text = call_openai_with_fallback(api_key, payload, args.model)
        if openai_raw is not None:
            ai_text = extract_output_text(openai_raw)
            ai_model = chosen_model or args.model
        else:
            ai_error = error_text

    write_markdown_report(
        out_md,
        primary_subject,
        subject_data,
        normalized_identifiers,
        category_counts,
        all_security_rows,
        all_source_docs,
        ai_text,
        ai_model,
        ai_error,
        args.max_per_category,
    )

    output_bundle = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "primary_subject": primary_subject,
        "subjects": subject_data,
        "identifier_counts": category_counts,
        "identifiers": normalized_identifiers,
        "security_rows": all_security_rows,
        "report_markdown": str(out_md),
        "report_csv": str(out_csv),
        "openai_model": ai_model,
        "openai_error": ai_error,
        "openai_response": openai_raw,
    }
    out_json.write_text(json.dumps(output_bundle, indent=2), encoding="utf-8")

    print(f"Wrote {out_md}")
    print(f"Wrote {out_json}")
    print(f"Wrote {out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

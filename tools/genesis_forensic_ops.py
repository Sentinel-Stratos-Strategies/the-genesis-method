#!/usr/bin/env python3
import argparse
import csv
import hashlib
import io
import json
import os
import platform
import re
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SYSDIAG_ROOT = Path("/Volumes/Stratos_Tools/sysdiagnosis")
DEFAULT_SENTINEL_ROOT = Path("/Volumes/SENTINEL")


IDENTIFIER_PATTERNS = {
    "email": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),
    "uuid": re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I),
    "ipv4": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    "domain": re.compile(r"\b(?:[a-z0-9-]+\.)+(?:com|net|org|io|ai|dev|cloud|us|gov|edu)\b", re.I),
    "alt_dsid": re.compile(r"\b(?:altDSID|alt_dsid|DSID|dsid)[=: ]+([A-Za-z0-9._:-]{6,})\b", re.I),
    "spid": re.compile(r"\b(?:SPID|spid)[=: ]+([A-Za-z0-9._:-]{6,})\b"),
    "peer": re.compile(r"\b(?:peer|Peer|TrustedPeer|Octagon).*?([A-Fa-f0-9]{16,}|[A-Za-z0-9._:-]{12,})\b"),
}

KEYWORD_BUCKETS = {
    "mdm": ["mdm", "mobile device management", "deviceenrollment", "mdmenrollment", "iprofiles", "jamf", "kandji", "intune", "mosyle"],
    "ckks_octagon": ["ckks", "octagon", "trustedpeer", "trusted peer", "pcs", "spid", "altdsid"],
    "network": ["vpn", "dns proxy", "networkextension", "proxy", "content filter", "bssid"],
    "spyware": ["pegasus", "mvt", "stix", "yara", "spyware", "exploit"],
    "auth": ["authkit", "icloud", "cloudkit", "denied", "unauthorized", "trust failure"],
}


def now_id():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def ensure_dir(path):
    Path(path).mkdir(parents=True, exist_ok=True)
    return Path(path)


def sha256_file(path, block=1024 * 1024):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(block), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_read(path, limit=2_000_000):
    try:
        with open(path, "rb") as fh:
            data = fh.read(limit)
        return data.decode("utf-8", errors="replace")
    except Exception:
        return ""


def is_inside(path, root):
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except Exception:
        return False


def iter_files(root, max_files=200000):
    root = Path(root)
    count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in {".git", ".venv", "__pycache__", ".Spotlight-V100", ".Trashes"}]
        for filename in filenames:
            path = Path(dirpath) / filename
            count += 1
            if count > max_files:
                return
            yield path


def write_json(path, payload):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)


def write_directory_map(path: Path, input_roots):
    lines = []
    for root in input_roots:
        r = Path(root)
        lines.append(f"# root: {r}")
        if not r.exists():
            lines.append("  (missing)")
            continue
        for dirpath, dirnames, _filenames in os.walk(r):
            rel = Path(dirpath).relative_to(r)
            depth = len(rel.parts)
            if depth > 3:
                dirnames[:] = []
                continue
            lines.append(f"  {'  ' * depth}{Path(dirpath).name}/")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def case_init(args):
    out = ensure_dir(Path(args.output_dir) / "_Case")
    run_id = now_id()
    context = {
        "case_id": args.case_id,
        "run_id": run_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "operator": args.operator,
        "hostname": platform.node(),
        "platform": platform.platform(),
        "python": sys.version,
        "root": str(ROOT),
        "output_dir": str(Path(args.output_dir).resolve()),
        "inputs": args.input or [],
    }
    write_json(out / "CASE_CONTEXT.json", context)
    with (out / "RUN_LEDGER.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"event": "case_init", **context}, sort_keys=True) + "\n")
    with (out / "TOOL_VERSIONS.txt").open("w", encoding="utf-8") as fh:
        for tool in ["python3", "sqlite3", "log", "plutil", "sysdiag", "saf", "mvt-ios", "uac", "osqueryi", "velociraptor", "yara", "yarax", "log2timeline.py", "timesketch"]:
            resolved = shutil.which(tool)
            fh.write(f"{tool}: {resolved or 'missing'}\n")
    roots = [Path(p) for p in (args.input or []) if p]
    if roots:
        write_directory_map(out / "DIRECTORY_MAP.txt", roots)
    print(out / "CASE_CONTEXT.json")


def scope_guard(args):
    roots = [Path(p).resolve() for p in args.root]
    refused = []
    accepted = []
    for path in args.path:
        p = Path(path).resolve()
        if str(p) in {"/", "/Users", "/Volumes", str(Path.home())}:
            refused.append(f"{p}: broad live-system path")
        elif any(is_inside(p, root) for root in roots):
            accepted.append(str(p))
        else:
            refused.append(f"{p}: outside approved roots")
    report = {"approved_roots": [str(r) for r in roots], "accepted": accepted, "refused": refused}
    if args.output_dir:
        out = ensure_dir(Path(args.output_dir) / "_Validation")
        write_json(out / "SCOPE_GUARD.json", report)
    print(json.dumps(report, indent=2))
    return 1 if refused else 0


def evidence_inventory(args):
    source = Path(args.source).resolve()
    out = ensure_dir(Path(args.output_dir) / "inventory")
    csv_path = out / "evidence_inventory.csv"
    jsonl_path = out / "evidence_inventory.jsonl"
    manifest_path = out / "MANIFEST_SHA256.csv"
    rows = []
    with csv_path.open("w", newline="", encoding="utf-8") as csv_fh, jsonl_path.open("w", encoding="utf-8") as jsonl_fh:
        fieldnames = ["rel_path", "size", "mtime", "created", "extension", "sha256"]
        writer = csv.DictWriter(csv_fh, fieldnames=fieldnames)
        writer.writeheader()
        for path in iter_files(source):
            try:
                st = path.stat()
                row = {
                    "rel_path": str(path.relative_to(source)),
                    "size": st.st_size,
                    "mtime": datetime.fromtimestamp(st.st_mtime).isoformat(),
                    "created": datetime.fromtimestamp(getattr(st, "st_birthtime", st.st_ctime)).isoformat(),
                    "extension": path.suffix.lower(),
                    "sha256": sha256_file(path),
                }
            except Exception as exc:
                row = {"rel_path": str(path), "size": "", "mtime": "", "created": "", "extension": path.suffix.lower(), "sha256": f"ERROR:{exc}"}
            writer.writerow(row)
            jsonl_fh.write(json.dumps(row, sort_keys=True) + "\n")
            rows.append(row)
    with manifest_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["sha256", "rel_path"])
        for row in rows:
            writer.writerow([row["sha256"], row["rel_path"]])
    print(csv_path)


def canonical_manifest_normalizer(args):
    out = ensure_dir(Path(args.output_dir) / "canonical")
    csv_path = out / "CANONICAL_EVENTS.csv"
    jsonl_path = out / "CANONICAL_EVENTS.jsonl"
    fields = [
        "case_id", "run_id", "source_lane", "source_tool", "source_file", "artifact_path",
        "event_time", "event_time_source", "file_mtime", "file_created", "identifier_type",
        "identifier_value_redacted", "keyword_hits", "ioc_hits", "severity", "confidence", "raw_excerpt", "row_hash",
    ]
    aliases = {
        "artifact_path": ["artifact_path", "entry_path", "rel_path", "filename", "path", "source_file"],
        "file_mtime": ["file_mtime", "entry_mtime", "mtime"],
        "file_created": ["file_created", "created", "birthtime"],
        "event_time": ["event_time", "capture_date", "timestamp", "timestamp_field", "date"],
    }
    rows = []
    for input_path in args.input:
        path = Path(input_path)
        if not path.exists():
            continue
        if path.suffix.lower() == ".jsonl":
            raw_rows = [json.loads(line) for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]
        elif path.suffix.lower() == ".json":
            data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            raw_rows = data if isinstance(data, list) else data.get("rows", data.get("events", []))
        else:
            text = path.read_text(encoding="utf-8", errors="replace").replace("\x00", "")
            raw_rows = list(csv.DictReader(io.StringIO(text)))
        for raw in raw_rows:
            row = {key: "" for key in fields}
            row["case_id"] = args.case_id
            row["run_id"] = args.run_id or now_id()
            row["source_lane"] = args.source_lane
            row["source_tool"] = args.source_tool or path.stem
            row["source_file"] = str(path)
            for canonical, names in aliases.items():
                row[canonical] = next((str(raw.get(name, "")) for name in names if raw.get(name)), "")
            text = json.dumps(raw, sort_keys=True, default=str)
            row["keyword_hits"] = ",".join(bucket for bucket, words in KEYWORD_BUCKETS.items() if any(word.lower() in text.lower() for word in words))
            row["raw_excerpt"] = text[:700]
            row["confidence"] = "low" if row["keyword_hits"] else ""
            row["severity"] = "review" if row["keyword_hits"] else ""
            row["row_hash"] = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()
            rows.append(row)
    with csv_path.open("w", newline="", encoding="utf-8") as csv_fh, jsonl_path.open("w", encoding="utf-8") as jsonl_fh:
        writer = csv.DictWriter(csv_fh, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
            jsonl_fh.write(json.dumps(row, sort_keys=True) + "\n")
    print(csv_path)


def normalize_scan(args):
    """Discover AI1-style CSV manifests under scan-root and feed them to the canonical normalizer."""
    root = Path(args.scan_root).resolve()
    patterns = ["**/SYSDIAG_FOLDER_MANIFEST*.csv", "**/ICLOUD_SEARCH_MANIFEST*.csv"]
    found: list[Path] = []
    for pattern in patterns:
        for p in root.glob(pattern):
            if p.is_file() and ".git" not in p.parts and ".venv" not in p.parts:
                found.append(p)
    found = sorted(set(found))
    if args.limit:
        found = found[: int(args.limit)]
    meta_dir = ensure_dir(Path(args.output_dir) / "canonical")
    (meta_dir / "NORMALIZE_SCAN_MANIFESTS.txt").write_text("\n".join(str(p) for p in found) + "\n", encoding="utf-8")
    if not found:
        print(f"No CSV manifests matched under {root}")
        return

    class Tmp:
        pass

    t = Tmp()
    t.output_dir = args.output_dir
    t.case_id = args.case_id
    t.run_id = args.run_id
    t.source_lane = args.source_lane
    t.source_tool = args.source_tool
    t.input = [str(p) for p in found]
    canonical_manifest_normalizer(t)


def forensic_index_builder(args):
    db_path = Path(args.output_dir) / "forensic_index.db"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("create table if not exists files(rel_path text, size integer, mtime text, created text, extension text, sha256 text)")
    cur.execute("create table if not exists identifiers(identifier_type text, identifier_value text, source_file text, artifact_path text)")
    cur.execute("create table if not exists events(case_id text, run_id text, source_lane text, source_tool text, source_file text, artifact_path text, event_time text, keyword_hits text, severity text, confidence text, row_hash text)")
    cur.execute("create table if not exists findings(finding_id text primary key, severity text, confidence text, title text, explanation text, source_count integer)")
    inv = Path(args.output_dir) / "inventory" / "evidence_inventory.csv"
    if inv.exists():
        with inv.open("r", newline="", encoding="utf-8", errors="replace") as fh:
            cur.executemany("insert into files values (:rel_path, :size, :mtime, :created, :extension, :sha256)", csv.DictReader(fh))
    canonical = Path(args.output_dir) / "canonical" / "CANONICAL_EVENTS.csv"
    if canonical.exists():
        with canonical.open("r", newline="", encoding="utf-8", errors="replace") as fh:
            for row in csv.DictReader(fh):
                cur.execute(
                    "insert into events values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (row.get("case_id"), row.get("run_id"), row.get("source_lane"), row.get("source_tool"), row.get("source_file"), row.get("artifact_path"), row.get("event_time"), row.get("keyword_hits"), row.get("severity"), row.get("confidence"), row.get("row_hash")),
                )
    for source in args.scan_source or []:
        for path in iter_files(source, max_files=50000):
            text = safe_read(path, 500000)
            if not text:
                continue
            rel = str(path)
            for id_type, pattern in IDENTIFIER_PATTERNS.items():
                for match in pattern.finditer(text):
                    value = match.group(1) if match.groups() else match.group(0)
                    cur.execute("insert into identifiers values (?, ?, ?, ?)", (id_type, value[:256], rel, rel))
    conn.commit()
    conn.close()
    print(db_path)


def anchor_timeline_verify(args):
    anchor = Path(args.anchor)
    out = ensure_dir(Path(args.output_dir) / "anchors")
    result = {"anchor": str(anchor), "exists": anchor.exists(), "sha256_ok": None, "items": 0, "errors": []}
    if anchor.exists():
        try:
            data = json.loads(anchor.read_text(encoding="utf-8"))
            result["items"] = len(data if isinstance(data, list) else data.get("anchors", []))
        except Exception as exc:
            result["errors"].append(f"JSON parse failed: {exc}")
        sha_path = Path(str(anchor) + ".sha256") if not str(anchor).endswith(".sha256") else anchor
        if not sha_path.exists() and anchor.with_suffix(anchor.suffix + ".sha256").exists():
            sha_path = anchor.with_suffix(anchor.suffix + ".sha256")
        if sha_path.exists() and sha_path != anchor:
            expected = sha_path.read_text(encoding="utf-8", errors="replace").split()[0].strip()
            result["sha256_ok"] = expected == sha256_file(anchor)
    write_json(out / "ANCHOR_VALIDATION.json", result)
    with (out / "ANCHOR_VALIDATION_REPORT.md").open("w", encoding="utf-8") as fh:
        fh.write("# Anchor Timeline Validation\n\n")
        for key, value in result.items():
            fh.write(f"- {key}: {value}\n")
    print(out / "ANCHOR_VALIDATION_REPORT.md")


def validate_toolchain(args):
    out = ensure_dir(Path(args.output_dir) / "_Validation")
    tools = ["python3", "sysdiag", "saf", "mvt-ios", "uac", "osqueryi", "velociraptor", "yara", "yarax", "log2timeline.py", "timesketch", "plutil", "log"]
    rows = []
    for tool in tools:
        path = shutil.which(tool)
        version = ""
        if path:
            try:
                probe = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=5)
                version = (probe.stdout or probe.stderr).strip().splitlines()[0][:200]
            except Exception:
                version = "present"
        rows.append({"tool": tool, "path": path or "", "version": version or "missing"})
    write_json(out / "TOOLCHAIN_LOCK.json", {"generated_at": datetime.now(timezone.utc).isoformat(), "tools": rows})
    print(out / "TOOLCHAIN_LOCK.json")


def sysdiagnose_killcard(args):
    source = Path(args.source)
    out = ensure_dir(Path(args.output_dir) / "sysdiagnose_killcard")
    hits = []
    for path in iter_files(source, max_files=args.max_files):
        text = safe_read(path, args.bytes_per_file)
        if not text:
            continue
        lower = text.lower()
        buckets = [bucket for bucket, words in KEYWORD_BUCKETS.items() if any(word.lower() in lower for word in words)]
        ids = []
        for id_type, pattern in IDENTIFIER_PATTERNS.items():
            for match in pattern.finditer(text[: args.bytes_per_file]):
                ids.append({"type": id_type, "value": (match.group(1) if match.groups() else match.group(0))[:160]})
        if buckets or ids:
            hits.append({"path": str(path), "buckets": buckets, "identifiers": ids[:25], "excerpt": text[:500].replace("\n", " ")})
    jsonl = out / "sysdiagnose_killcard_hits.jsonl"
    with jsonl.open("w", encoding="utf-8") as fh:
        for hit in hits:
            fh.write(json.dumps(hit, sort_keys=True) + "\n")
    with (out / "SYSDIAGNOSE_KILLCARD.md").open("w", encoding="utf-8") as fh:
        fh.write("# Sysdiagnose Killcard\n\n")
        fh.write(f"- Source: `{source}`\n- Hits: {len(hits)}\n\n")
        for hit in hits[:200]:
            fh.write(f"## {hit['path']}\n- Buckets: {', '.join(hit['buckets']) or 'identifier-only'}\n- Identifiers: {len(hit['identifiers'])}\n\n")
    print(jsonl)


def icloud_takeout_ingest(args):
    out = ensure_dir(Path(args.output_dir) / "icloud_takeout")
    warnings = []
    events = []
    for source in args.input:
        path = Path(source)
        if not path.exists():
            warnings.append({"file": source, "warning": "missing"})
            continue
        if path.is_dir():
            files = list(path.rglob("*.csv"))
        else:
            files = [path]
        for csv_file in files:
            try:
                sample = csv_file.read_text(encoding="utf-8", errors="replace")[:4096]
                dialect = csv.Sniffer().sniff(sample) if sample.strip() else csv.excel
                with csv_file.open("r", newline="", encoding="utf-8", errors="replace") as fh:
                    reader = csv.DictReader(fh, dialect=dialect)
                    if not reader.fieldnames:
                        warnings.append({"file": str(csv_file), "warning": "no headers"})
                        continue
                    count = 0
                    for row in reader:
                        count += 1
                        events.append({"source_file": str(csv_file), **{k: v for k, v in row.items() if k}})
                    if count == 0:
                        warnings.append({"file": str(csv_file), "warning": "zero data rows", "headers": reader.fieldnames})
            except Exception as exc:
                warnings.append({"file": str(csv_file), "warning": str(exc)})
    keys = sorted({k for row in events for k in row.keys()})
    with (out / "ICLOUD_TAKEOUT_EVENTS.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=keys or ["source_file"])
        writer.writeheader()
        writer.writerows(events)
    with (out / "ICLOUD_TAKEOUT_WARNINGS.jsonl").open("w", encoding="utf-8") as fh:
        for warning in warnings:
            fh.write(json.dumps(warning, sort_keys=True) + "\n")
    print(out / "ICLOUD_TAKEOUT_EVENTS.csv")


def evidence_diff(args):
    out = ensure_dir(Path(args.output_dir) / "diff")
    seen = {}
    for label, source in zip(args.label, args.source):
        for path in iter_files(source, max_files=50000):
            text = safe_read(path, 300000)
            for id_type, pattern in IDENTIFIER_PATTERNS.items():
                for match in pattern.finditer(text):
                    value = match.group(1) if match.groups() else match.group(0)
                    seen.setdefault((id_type, value), set()).add(label)
    rows = [{"identifier_type": k[0], "identifier": k[1], "labels": ",".join(sorted(v)), "label_count": len(v)} for k, v in seen.items() if len(v) > 1]
    with (out / "EVIDENCE_DIFF_RECURRENT_IDENTIFIERS.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["identifier_type", "identifier", "labels", "label_count"])
        writer.writeheader()
        writer.writerows(rows)
    print(out / "EVIDENCE_DIFF_RECURRENT_IDENTIFIERS.csv")


def finding_confidence(args):
    source = Path(args.input)
    out = ensure_dir(Path(args.output_dir) / "findings")
    findings = []
    if source.exists():
        with source.open("r", newline="", encoding="utf-8", errors="replace") as fh:
            for row in csv.DictReader(fh):
                text = " ".join(str(row.get(k, "")) for k in row)
                buckets = [bucket for bucket, words in KEYWORD_BUCKETS.items() if any(word.lower() in text.lower() for word in words)]
                if not buckets:
                    continue
                confidence = "high" if len(buckets) >= 2 and (row.get("event_time") or row.get("file_mtime")) else "medium" if len(buckets) >= 2 else "low"
                findings.append({"severity": "review", "confidence": confidence, "buckets": ",".join(buckets), "artifact_path": row.get("artifact_path", ""), "source_file": row.get("source_file", "")})
    with (out / "FINDINGS_CONFIDENCE.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["severity", "confidence", "buckets", "artifact_path", "source_file"])
        writer.writeheader()
        writer.writerows(findings)
    print(out / "FINDINGS_CONFIDENCE.csv")


def run_folder(args):
    source = Path(args.source).resolve()
    out = ensure_dir(args.output_dir)
    pipeline = args.pipeline
    if not source.is_dir():
        raise SystemExit(f"Source folder not found: {source}")

    class Obj:
        pass

    def call(func, **kwargs):
        item = Obj()
        for key, value in kwargs.items():
            setattr(item, key, value)
        return func(item)

    call(case_init, output_dir=str(out), case_id=args.case_id, operator=os.environ.get("USER", "unknown"), input=[str(source)])
    call(scope_guard, root=[str(source)], path=[str(source)], output_dir=str(out))
    call(evidence_inventory, source=str(source), output_dir=str(out))

    if pipeline in {"full", "sysdiagnose"}:
        call(sysdiagnose_killcard, source=str(source), output_dir=str(out), max_files=args.max_files, bytes_per_file=args.bytes_per_file)

    if pipeline in {"full", "cloud"}:
        call(icloud_takeout_ingest, input=[str(source)], output_dir=str(out))

    if pipeline in {"full", "index"}:
        call(forensic_index_builder, output_dir=str(out), scan_source=[str(source)])

    call(validate_toolchain, output_dir=str(out))
    summary = {
        "case_id": args.case_id,
        "pipeline": pipeline,
        "source": str(source),
        "output_dir": str(out),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    write_json(out / "RUN_SUMMARY.json", summary)
    print(out / "RUN_SUMMARY.json")


def main():
    parser = argparse.ArgumentParser(description="Genesis forensic helper operations")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("case-init")
    p.add_argument("--output-dir", required=True)
    p.add_argument("--case-id", default="GENESIS")
    p.add_argument("--operator", default=os.environ.get("USER", "unknown"))
    p.add_argument("--input", action="append")
    p.set_defaults(func=case_init)

    p = sub.add_parser("scope-guard")
    p.add_argument("--root", action="append", required=True)
    p.add_argument("--path", action="append", required=True)
    p.add_argument("--output-dir")
    p.set_defaults(func=scope_guard)

    p = sub.add_parser("inventory")
    p.add_argument("--source", required=True)
    p.add_argument("--output-dir", required=True)
    p.set_defaults(func=evidence_inventory)

    p = sub.add_parser("normalize")
    p.add_argument("--input", action="append", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--case-id", default="GENESIS")
    p.add_argument("--run-id")
    p.add_argument("--source-lane", default="unknown")
    p.add_argument("--source-tool")
    p.set_defaults(func=canonical_manifest_normalizer)

    p = sub.add_parser("normalize-scan")
    p.add_argument("--scan-root", required=True, help="Root to recursively search for AI1 manifest CSVs")
    p.add_argument("--output-dir", required=True)
    p.add_argument("--case-id", default="GENESIS")
    p.add_argument("--run-id")
    p.add_argument("--source-lane", default="ai1-scan")
    p.add_argument("--source-tool")
    p.add_argument("--limit", type=int, default=48, help="Max number of manifest files to merge")
    p.set_defaults(func=normalize_scan)

    p = sub.add_parser("index")
    p.add_argument("--output-dir", required=True)
    p.add_argument("--scan-source", action="append")
    p.set_defaults(func=forensic_index_builder)

    p = sub.add_parser("anchor-verify")
    p.add_argument("--anchor", required=True)
    p.add_argument("--output-dir", required=True)
    p.set_defaults(func=anchor_timeline_verify)

    p = sub.add_parser("validate-toolchain")
    p.add_argument("--output-dir", required=True)
    p.set_defaults(func=validate_toolchain)

    p = sub.add_parser("sysdiagnose-killcard")
    p.add_argument("--source", default=str(DEFAULT_SYSDIAG_ROOT / "AI1_Parser" / "input"))
    p.add_argument("--output-dir", required=True)
    p.add_argument("--max-files", type=int, default=25000)
    p.add_argument("--bytes-per-file", type=int, default=500000)
    p.set_defaults(func=sysdiagnose_killcard)

    p = sub.add_parser("icloud-takeout-ingest")
    p.add_argument("--input", action="append", required=True)
    p.add_argument("--output-dir", required=True)
    p.set_defaults(func=icloud_takeout_ingest)

    p = sub.add_parser("evidence-diff")
    p.add_argument("--source", action="append", required=True)
    p.add_argument("--label", action="append", required=True)
    p.add_argument("--output-dir", required=True)
    p.set_defaults(func=evidence_diff)

    p = sub.add_parser("finding-confidence")
    p.add_argument("--input", required=True)
    p.add_argument("--output-dir", required=True)
    p.set_defaults(func=finding_confidence)

    p = sub.add_parser("run-folder")
    p.add_argument("--pipeline", choices=["full", "inventory", "sysdiagnose", "cloud", "index"], default="full")
    p.add_argument("--source", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--case-id", default="GENESIS")
    p.add_argument("--max-files", type=int, default=25000)
    p.add_argument("--bytes-per-file", type=int, default=500000)
    p.set_defaults(func=run_folder)

    args = parser.parse_args()
    return args.func(args) or 0


if __name__ == "__main__":
    raise SystemExit(main())

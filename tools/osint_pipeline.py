#!/usr/bin/env python3
"""
Legal-first OSINT pipeline for Genesis targets (stdlib-only).

This script is designed for *defensive* investigation and attribution support:
- Enrich domains/IPs found in your own forensic outputs.
- Produce a report that helps you triage suspicious infrastructure and likely entry points.
- Avoids exploit guidance and does not attempt access to private systems.

Inputs:
- targets file (kind:value), typically produced by tools/osint_targets.py

Outputs:
- osint_results.json (raw API results + errors)
- osint_report.md (readable triage summary)

Optional integrations (only if API keys are present):
- VirusTotal v3 (domains, IPs)
- AbuseIPDB (IPs)
- Hunter.io (emails, domains)
- Perplexity / Sonar (text synthesis)
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pplx_client import PplxClient, extract_text, load_kv_env_file


def _http_json(url: str, headers: dict[str, str], timeout: int, method: str = "GET", payload: dict | None = None) -> dict:
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        method = "POST"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="ignore").strip()
        except Exception:
            detail = ""
        raise RuntimeError(f"HTTP {exc.code}: {detail or exc.reason}") from exc


def read_targets(path: Path) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {"domain": set(), "ipv4": set(), "ipv6": set(), "ip": set(), "email": set(), "url": set(), "keyword": set()}
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        kind, value = line.split(":", 1)
        kind = kind.strip().lower()
        value = value.strip()
        if not value:
            continue
        if kind in ("domain", "domains"):
            out["domain"].add(value.lower().rstrip("."))
        elif kind in ("ipv4", "ipv6"):
            out[kind].add(value)
        elif kind in ("ip",):
            out["ip"].add(value)
        elif kind in ("email", "emails"):
            out["email"].add(value.lower())
        elif kind in ("url", "urls"):
            out["url"].add(value)
        elif kind in ("keyword", "keywords"):
            out["keyword"].add(value)
    # Normalize "ip" into v4/v6 buckets if possible (best-effort).
    for ip in list(out["ip"]):
        if ":" in ip:
            out["ipv6"].add(ip.lower())
        else:
            out["ipv4"].add(ip)
    out["ip"].clear()
    return out


def vt_key(env: dict[str, str] | None = None) -> str | None:
    env = env or {}
    return os.environ.get("VT_API_KEY") or os.environ.get("VIRUS_TOTAL") or env.get("VT_API_KEY") or env.get("VIRUS_TOTAL")


def abuseipdb_key(env: dict[str, str] | None = None) -> str | None:
    env = env or {}
    return (
        os.environ.get("ABUSEIPDB_KEY")
        or os.environ.get("ABUSE_IP_DB")
        or env.get("ABUSEIPDB_KEY")
        or env.get("ABUSE_IP_DB")
        or env.get("ABUSE_IP_DB_KEY")
    )


def hunter_key(env: dict[str, str] | None = None) -> str | None:
    env = env or {}
    return os.environ.get("HUNTER_API_KEY") or env.get("HUNTER_API_KEY")


def hunter_base_url(env: dict[str, str] | None = None) -> str:
    env = env or {}
    return (os.environ.get("HUNTER_BASE_URL") or env.get("HUNTER_BASE_URL") or "https://api.hunter.io/v2").rstrip("/")


def vt_domain(domain: str, api_key: str, timeout: int) -> dict:
    url = f"https://www.virustotal.com/api/v3/domains/{urllib.parse.quote(domain)}"
    return _http_json(url, headers={"x-apikey": api_key, "accept": "application/json"}, timeout=timeout)


def vt_ip(ip: str, api_key: str, timeout: int) -> dict:
    url = f"https://www.virustotal.com/api/v3/ip_addresses/{urllib.parse.quote(ip)}"
    return _http_json(url, headers={"x-apikey": api_key, "accept": "application/json"}, timeout=timeout)


def vt_ip_analyse(ip: str, api_key: str, timeout: int) -> dict:
    url = f"https://www.virustotal.com/api/v3/ip_addresses/{urllib.parse.quote(ip)}/analyse"
    return _http_json(url, headers={"x-apikey": api_key, "accept": "application/json"}, timeout=timeout, method="POST")


def vt_ip_related_objects(ip: str, relationship: str, api_key: str, timeout: int, limit: int = 10, cursor: str | None = None) -> dict:
    """
    Get objects related to an IP address (full objects).
    Endpoint: /ip_addresses/{ip}/{relationship}
    """
    qs = {"limit": str(max(1, int(limit)))}
    if cursor:
        qs["cursor"] = cursor
    q = urllib.parse.urlencode(qs)
    url = f"https://www.virustotal.com/api/v3/ip_addresses/{urllib.parse.quote(ip)}/{urllib.parse.quote(relationship)}?{q}"
    return _http_json(url, headers={"x-apikey": api_key, "accept": "application/json"}, timeout=timeout)


def vt_ip_related_descriptors(
    ip: str, relationship: str, api_key: str, timeout: int, limit: int = 10, cursor: str | None = None
) -> dict:
    """
    Get object descriptors related to an IP address (IDs + context).
    Endpoint: /ip_addresses/{ip}/relationships/{relationship}
    """
    qs = {"limit": str(max(1, int(limit)))}
    if cursor:
        qs["cursor"] = cursor
    q = urllib.parse.urlencode(qs)
    url = f"https://www.virustotal.com/api/v3/ip_addresses/{urllib.parse.quote(ip)}/relationships/{urllib.parse.quote(relationship)}?{q}"
    return _http_json(url, headers={"x-apikey": api_key, "accept": "application/json"}, timeout=timeout)


def abuseipdb_check(ip: str, api_key: str, timeout: int) -> dict:
    url = f"https://api.abuseipdb.com/api/v2/check?ipAddress={urllib.parse.quote(ip)}&maxAgeInDays=365"
    return _http_json(url, headers={"Key": api_key, "Accept": "application/json"}, timeout=timeout)


def hunter_verify(email: str, api_key: str, timeout: int, env: dict[str, str] | None = None) -> dict:
    url = f"{hunter_base_url(env)}/email-verifier?email={urllib.parse.quote(email)}&api_key={urllib.parse.quote(api_key)}"
    return _http_json(url, headers={}, timeout=timeout)


def hunter_combined(email: str, api_key: str, timeout: int, env: dict[str, str] | None = None) -> dict:
    url = f"{hunter_base_url(env)}/combined/find?email={urllib.parse.quote(email)}&api_key={urllib.parse.quote(api_key)}"
    return _http_json(url, headers={}, timeout=timeout)


def hunter_company(domain: str, api_key: str, timeout: int, env: dict[str, str] | None = None) -> dict:
    url = f"{hunter_base_url(env)}/companies/find?domain={urllib.parse.quote(domain)}&api_key={urllib.parse.quote(api_key)}"
    return _http_json(url, headers={}, timeout=timeout)


def hunter_domain_search(domain: str, api_key: str, timeout: int, env: dict[str, str] | None = None) -> dict:
    url = f"{hunter_base_url(env)}/domain-search?domain={urllib.parse.quote(domain)}&api_key={urllib.parse.quote(api_key)}"
    return _http_json(url, headers={}, timeout=timeout)


def sonar_summarize_domain(client: PplxClient, domain: str) -> dict:
    prompt = (
        "You are a defensive OSINT analyst. Using publicly available sources, summarize:\n"
        f"- What is this domain used for: {domain}\n"
        "- Ownership/organization (if known)\n"
        "- Any reputation signals (phishing, malware, spam) if present\n"
        "- Why it might matter in an account/device compromise investigation\n"
        "Return a short bulleted summary. Do not provide any hacking instructions."
    )
    resp = client.chat_completions(messages=[{"role": "user", "content": prompt}])
    return {"raw": resp, "text": extract_text(resp)}


def sonar_summarize_ip(client: PplxClient, ip: str) -> dict:
    prompt = (
        "You are a defensive OSINT analyst. Using publicly available sources, summarize:\n"
        f"- What is known about this IP: {ip}\n"
        "- Hosting/ASN/region (if known)\n"
        "- Any reputation signals (abuse, scanning, botnet, spam) if present\n"
        "- Why it might matter in an account/device compromise investigation\n"
        "Return a short bulleted summary. Do not provide any hacking instructions."
    )
    resp = client.chat_completions(messages=[{"role": "user", "content": prompt}])
    return {"raw": resp, "text": extract_text(resp)}


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_md(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def md_line(s: str) -> str:
    return s.replace("\r", " ").strip()


@dataclass
class RunConfig:
    vt: bool
    abuseipdb: bool
    hunter: bool
    sonar: bool
    vt_ip_analyse: bool
    vt_ip_relationships: list[str]
    vt_ip_relationship_mode: str
    vt_ip_relationship_limit: int
    vt_ip_relationship_include_ipv6: bool
    timeout: int
    sleep_s: float
    max_sonar_items: int
    pplx_env_file: str | None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--targets-file", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--sleep-s", type=float, default=0.35, help="Sleep between API calls (rate-limit friendly).")
    parser.add_argument("--with-sonar", action="store_true", help="Enable Perplexity/Sonar synthesis (costs API calls).")
    parser.add_argument("--max-sonar-items", type=int, default=20, help="Limit number of domain/ip summaries to reduce spend.")
    parser.add_argument("--vt-ip-analyse", action="store_true", help="Trigger VirusTotal IP reanalysis (extra API calls).")
    parser.add_argument(
        "--vt-ip-relationship",
        action="append",
        default=[],
        help="VirusTotal IP relationship to fetch (repeatable). Example: --vt-ip-relationship resolutions",
    )
    parser.add_argument(
        "--vt-ip-relationship-mode",
        choices=("descriptors", "objects"),
        default="descriptors",
        help="Use descriptors (IDs only) or full objects for VT relationships.",
    )
    parser.add_argument("--vt-ip-relationship-limit", type=int, default=10, help="VT relationship limit (default: 10).")
    parser.add_argument("--vt-ip-relationship-include-ipv6", action="store_true", help="Also fetch VT relationships for IPv6 targets.")
    parser.add_argument("--pplx-env-file", default=os.environ.get("GENESIS_PPLX_ENV_FILE") or os.environ.get("PPLX_ENV_FILE"))
    args = parser.parse_args()

    targets_path = Path(args.targets_file)
    if not targets_path.exists():
        print(f"Targets file not found: {targets_path}")
        return 1

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    targets = read_targets(targets_path)

    env_kv: dict[str, str] = {}
    env_file = args.pplx_env_file
    if env_file:
        try:
            env_kv = load_kv_env_file(env_file)
        except Exception:
            env_kv = {}

    vt_api = vt_key(env_kv)
    abuse_api = abuseipdb_key(env_kv)
    hunter_api = hunter_key(env_kv)

    cfg = RunConfig(
        vt=bool(vt_api),
        abuseipdb=bool(abuse_api),
        hunter=bool(hunter_api),
        sonar=bool(args.with_sonar),
        vt_ip_analyse=bool(args.vt_ip_analyse),
        vt_ip_relationships=sorted({r.strip() for r in (args.vt_ip_relationship or []) if r and r.strip()}),
        vt_ip_relationship_mode=str(args.vt_ip_relationship_mode),
        vt_ip_relationship_limit=max(1, int(args.vt_ip_relationship_limit)),
        vt_ip_relationship_include_ipv6=bool(args.vt_ip_relationship_include_ipv6),
        timeout=args.timeout,
        sleep_s=max(0.0, float(args.sleep_s)),
        max_sonar_items=max(0, int(args.max_sonar_items)),
        pplx_env_file=env_file,
    )

    pplx_client = None
    if cfg.sonar:
        try:
            pplx_client = PplxClient.from_env(env_file=cfg.pplx_env_file, timeout=max(60, cfg.timeout))
        except Exception as exc:
            cfg.sonar = False
            pplx_client = None
            print(f"Sonar disabled (missing config): {exc}")

    results: dict = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "targets_file": str(targets_path),
        "counts": {k: len(v) for k, v in targets.items()},
        "integrations": {
            "virustotal": cfg.vt,
            "abuseipdb": cfg.abuseipdb,
            "hunter": cfg.hunter,
            "sonar": cfg.sonar,
            "virustotal_ip_analyse": bool(cfg.vt and cfg.vt_ip_analyse),
            "virustotal_ip_relationships": cfg.vt_ip_relationships,
            "virustotal_ip_relationship_mode": cfg.vt_ip_relationship_mode,
            "virustotal_ip_relationship_limit": cfg.vt_ip_relationship_limit,
            "virustotal_ip_relationship_include_ipv6": cfg.vt_ip_relationship_include_ipv6,
        },
        "domains": {},
        "ips": {},
        "emails": {},
        "errors": [],
    }

    # Domains
    for d in sorted(targets["domain"]):
        item: dict = {}
        if cfg.vt and vt_api:
            try:
                item["virustotal"] = vt_domain(d, vt_api, cfg.timeout)
            except Exception as exc:
                item["virustotal"] = {"error": str(exc)}
        if cfg.hunter and hunter_api:
            try:
                item["hunter_company"] = hunter_company(d, hunter_api, cfg.timeout, env=env_kv)
            except Exception as exc:
                item["hunter_company"] = {"error": str(exc)}
            try:
                item["hunter_domain_search"] = hunter_domain_search(d, hunter_api, cfg.timeout, env=env_kv)
            except Exception as exc:
                item["hunter_domain_search"] = {"error": str(exc)}
        results["domains"][d] = item
        if cfg.sleep_s:
            time.sleep(cfg.sleep_s)

    # IPs
    ip_list = sorted(set(targets["ipv4"]).union(targets["ipv6"]))
    for ip in ip_list:
        item: dict = {}
        if cfg.vt and vt_api:
            try:
                item["virustotal"] = vt_ip(ip, vt_api, cfg.timeout)
            except Exception as exc:
                item["virustotal"] = {"error": str(exc)}
            if cfg.vt_ip_analyse:
                try:
                    item["virustotal_analyse"] = vt_ip_analyse(ip, vt_api, cfg.timeout)
                except Exception as exc:
                    item["virustotal_analyse"] = {"error": str(exc)}
            if cfg.vt_ip_relationships and (":" not in ip or cfg.vt_ip_relationship_include_ipv6):
                rels: dict[str, dict] = {}
                for rel in cfg.vt_ip_relationships:
                    try:
                        if cfg.vt_ip_relationship_mode == "objects":
                            rels[rel] = vt_ip_related_objects(ip, rel, vt_api, cfg.timeout, limit=cfg.vt_ip_relationship_limit)
                        else:
                            rels[rel] = vt_ip_related_descriptors(ip, rel, vt_api, cfg.timeout, limit=cfg.vt_ip_relationship_limit)
                    except Exception as exc:
                        rels[rel] = {"error": str(exc)}
                    if cfg.sleep_s:
                        time.sleep(cfg.sleep_s)
                item["virustotal_relationships"] = {
                    "mode": cfg.vt_ip_relationship_mode,
                    "limit": cfg.vt_ip_relationship_limit,
                    "relationships": rels,
                }
        if cfg.abuseipdb and abuse_api:
            try:
                item["abuseipdb"] = abuseipdb_check(ip, abuse_api, cfg.timeout)
            except Exception as exc:
                item["abuseipdb"] = {"error": str(exc)}
        results["ips"][ip] = item
        if cfg.sleep_s:
            time.sleep(cfg.sleep_s)

    # Emails
    for e in sorted(targets["email"]):
        item: dict = {}
        if cfg.hunter and hunter_api:
            try:
                item["hunter_verify"] = hunter_verify(e, hunter_api, cfg.timeout, env=env_kv)
            except Exception as exc:
                item["hunter_verify"] = {"error": str(exc)}
            try:
                item["hunter_combined"] = hunter_combined(e, hunter_api, cfg.timeout, env=env_kv)
            except Exception as exc:
                item["hunter_combined"] = {"error": str(exc)}
        results["emails"][e] = item
        if cfg.sleep_s:
            time.sleep(cfg.sleep_s)

    # Sonar summaries (limited)
    if cfg.sonar and pplx_client:
        domain_budget = min(cfg.max_sonar_items, len(results["domains"]))
        ip_budget = max(0, cfg.max_sonar_items - domain_budget)
        sonar: dict = {"domains": {}, "ips": {}}
        for d in list(sorted(results["domains"]))[:domain_budget]:
            try:
                sonar["domains"][d] = sonar_summarize_domain(pplx_client, d)
            except Exception as exc:
                sonar["domains"][d] = {"error": str(exc)}
            if cfg.sleep_s:
                time.sleep(cfg.sleep_s)
        for ip in list(sorted(results["ips"]))[:ip_budget]:
            try:
                sonar["ips"][ip] = sonar_summarize_ip(pplx_client, ip)
            except Exception as exc:
                sonar["ips"][ip] = {"error": str(exc)}
            if cfg.sleep_s:
                time.sleep(cfg.sleep_s)
        results["sonar"] = sonar

    # Write outputs
    json_path = out_dir / "osint_results.json"
    md_path = out_dir / "osint_report.md"
    write_json(json_path, results)

    lines: list[str] = []
    lines.append("# Genesis OSINT Report\n")
    lines.append(f"- Generated: {results['generated_at']}")
    lines.append(f"- Targets: `{targets_path}`\n")

    lines.append("## Integrations\n")
    for k, v in results["integrations"].items():
        if isinstance(v, bool):
            lines.append(f"- {k}: {'enabled' if v else 'disabled'}")
        else:
            lines.append(f"- {k}: {md_line(str(v))}")
    lines.append("")

    def vt_stats(obj: dict) -> str:
        try:
            attrs = obj.get("data", {}).get("attributes", {})
            stats = attrs.get("last_analysis_stats", {}) if isinstance(attrs, dict) else {}
            mal = stats.get("malicious")
            susp = stats.get("suspicious")
            harm = stats.get("harmless")
            if mal is None and susp is None and harm is None:
                return ""
            return f"VT stats: malicious={mal} suspicious={susp} harmless={harm}"
        except Exception:
            return ""

    lines.append("## Domains\n")
    for d in sorted(results["domains"]):
        item = results["domains"][d]
        lines.append(f"### {d}")
        vt = item.get("virustotal")
        if isinstance(vt, dict):
            if "error" in vt:
                lines.append(f"- VirusTotal: error: {md_line(str(vt.get('error')))}")
            else:
                s = vt_stats(vt)
                if s:
                    lines.append(f"- {s}")
        hc = item.get("hunter_company")
        if isinstance(hc, dict) and isinstance(hc.get("data"), dict) and hc["data"].get("name"):
            lines.append(f"- Hunter company: {md_line(str(hc['data'].get('name')))}")
        if cfg.sonar and isinstance(results.get("sonar"), dict):
            stext = (results.get("sonar", {}).get("domains", {}) or {}).get(d, {}).get("text")
            if stext:
                lines.append("- Sonar summary:")
                for raw_line in str(stext).splitlines():
                    if raw_line.strip():
                        lines.append(f"  {md_line(raw_line)}")
        lines.append("")

    lines.append("## IPs\n")
    for ip in sorted(results["ips"]):
        item = results["ips"][ip]
        lines.append(f"### {ip}")
        vt = item.get("virustotal")
        if isinstance(vt, dict):
            if "error" in vt:
                lines.append(f"- VirusTotal: error: {md_line(str(vt.get('error')))}")
            else:
                s = vt_stats(vt)
                if s:
                    lines.append(f"- {s}")
        vta = item.get("virustotal_analyse")
        if isinstance(vta, dict):
            if "error" in vta:
                lines.append(f"- VT analyse: error: {md_line(str(vta.get('error')))}")
            else:
                aid = (vta.get("data") or {}).get("id") if isinstance(vta.get("data"), dict) else None
                if aid:
                    lines.append(f"- VT analyse id: {md_line(str(aid))}")
        vtr = item.get("virustotal_relationships")
        if isinstance(vtr, dict):
            mode = vtr.get("mode")
            limit = vtr.get("limit")
            rels = vtr.get("relationships") if isinstance(vtr.get("relationships"), dict) else {}
            parts: list[str] = []
            errors: list[str] = []
            for rel_name, rel_obj in sorted(rels.items()):
                if isinstance(rel_obj, dict) and "error" in rel_obj:
                    errors.append(f"{rel_name}=error")
                    continue
                data = rel_obj.get("data") if isinstance(rel_obj, dict) else None
                if isinstance(data, list):
                    parts.append(f"{rel_name}={len(data)}")
                else:
                    parts.append(f"{rel_name}=0")
            if parts:
                lines.append(f"- VT relationships ({mode}, limit={limit}): " + ", ".join(parts))
            if errors:
                lines.append(f"- VT relationships errors: " + ", ".join(errors))
        ab = item.get("abuseipdb")
        if isinstance(ab, dict):
            if "error" in ab:
                lines.append(f"- AbuseIPDB: error: {md_line(str(ab.get('error')))}")
            else:
                data = ab.get("data") if isinstance(ab.get("data"), dict) else {}
                score = data.get("abuseConfidenceScore")
                reports = data.get("totalReports")
                if score is not None or reports is not None:
                    lines.append(f"- AbuseIPDB: score={score} reports={reports}")
        if cfg.sonar and isinstance(results.get("sonar"), dict):
            stext = (results.get("sonar", {}).get("ips", {}) or {}).get(ip, {}).get("text")
            if stext:
                lines.append("- Sonar summary:")
                for raw_line in str(stext).splitlines():
                    if raw_line.strip():
                        lines.append(f"  {md_line(raw_line)}")
        lines.append("")

    lines.append("## Emails\n")
    for e in sorted(results["emails"]):
        item = results["emails"][e]
        lines.append(f"### {e}")
        hv = item.get("hunter_verify")
        if isinstance(hv, dict):
            data = hv.get("data") if isinstance(hv.get("data"), dict) else {}
            status = data.get("status")
            score = data.get("score")
            if status or score is not None:
                lines.append(f"- Hunter verify: status={status} score={score}")
        lines.append("")

    write_md(md_path, "\n".join(lines).rstrip() + "\n")
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

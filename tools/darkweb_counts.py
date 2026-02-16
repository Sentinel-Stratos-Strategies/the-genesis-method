#!/usr/bin/env python3
"""
Counts-only "dark web" keyword monitor via Apify (defensive).

Important:
- This is intended for *defensive monitoring* of your own domains/keywords.
- This script stores only hit counts + run metadata (no page content).
- Your Apify account/actor configuration determines what is fetched server-side.

Inputs:
- A Genesis targets file (kind:value), usually produced by tools/osint_targets.py

Outputs:
- darkweb_counts.json
- darkweb_counts.md
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pplx_client import load_kv_env_file


def _http_json(url: str, headers: dict[str, str], payload: dict | None, timeout: int, method: str = "GET") -> dict:
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        method = "POST"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", errors="ignore")
        return json.loads(body) if body else {}


def parse_domains_from_targets(path: Path) -> list[str]:
    domains: list[str] = []
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        kind, value = line.split(":", 1)
        if kind.strip().lower() != "domain":
            continue
        d = value.strip().lower().rstrip(".")
        if d and d not in domains:
            domains.append(d)
    return domains


def apify_key(env: dict[str, str] | None = None) -> str | None:
    env = env or {}
    return os.environ.get("APIFY_API_KEY") or env.get("APIFY_API_KEY")


def apify_actor_run(token: str, actor_id: str, run_input: dict, timeout: int) -> dict:
    # Body is the run input; Apify returns run metadata including runId and defaultDatasetId.
    url = f"https://api.apify.com/v2/acts/{urllib.parse.quote(actor_id)}/runs?token={urllib.parse.quote(token)}"
    return _http_json(url, headers={"Content-Type": "application/json"}, payload=run_input, timeout=timeout, method="POST")


def apify_run_get(token: str, run_id: str, timeout: int) -> dict:
    url = f"https://api.apify.com/v2/actor-runs/{urllib.parse.quote(run_id)}?token={urllib.parse.quote(token)}"
    return _http_json(url, headers={}, payload=None, timeout=timeout, method="GET")


def apify_dataset_get(token: str, dataset_id: str, timeout: int) -> dict:
    url = f"https://api.apify.com/v2/datasets/{urllib.parse.quote(dataset_id)}?token={urllib.parse.quote(token)}"
    return _http_json(url, headers={}, payload=None, timeout=timeout, method="GET")


def dataset_item_count(dataset_obj: dict) -> int | None:
    data = dataset_obj.get("data") if isinstance(dataset_obj, dict) else None
    if not isinstance(data, dict):
        return None
    for k in ("itemCount", "itemsCount", "itemCountTotal", "itemsCountTotal"):
        v = data.get(k)
        if isinstance(v, int):
            return v
    return None


@dataclass
class Cfg:
    token: str
    actor_id: str
    timeout: int
    poll_s: float
    max_wait_s: int
    max_domains: int
    sleep_s: float


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--targets-file", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--actor-id", default=os.environ.get("APIFY_DARKWEB_ACTOR_ID") or "rtTDcOeK0k1nLWHyJ")
    p.add_argument("--timeout", type=int, default=30)
    p.add_argument("--poll-s", type=float, default=5.0)
    p.add_argument("--max-wait-s", type=int, default=180, help="Max time to wait for each actor run to finish.")
    p.add_argument("--max-domains", type=int, default=25)
    p.add_argument("--sleep-s", type=float, default=1.0, help="Sleep between domain runs.")
    p.add_argument("--env-file", default=os.environ.get("GENESIS_PPLX_ENV_FILE") or os.environ.get("PPLX_ENV_FILE"))
    args = p.parse_args()

    targets_path = Path(args.targets_file)
    if not targets_path.exists():
        print(f"Targets file not found: {targets_path}")
        return 1

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    env_kv: dict[str, str] = {}
    if args.env_file:
        try:
            env_kv = load_kv_env_file(args.env_file)
        except Exception:
            env_kv = {}

    token = apify_key(env_kv)
    if not token:
        print("APIFY_API_KEY is missing. Set it in your env or in GENESIS_PPLX_ENV_FILE.")
        return 1

    cfg = Cfg(
        token=token,
        actor_id=str(args.actor_id),
        timeout=max(5, int(args.timeout)),
        poll_s=max(0.5, float(args.poll_s)),
        max_wait_s=max(10, int(args.max_wait_s)),
        max_domains=max(0, int(args.max_domains)),
        sleep_s=max(0.0, float(args.sleep_s)),
    )

    domains = parse_domains_from_targets(targets_path)
    if cfg.max_domains and len(domains) > cfg.max_domains:
        domains = domains[: cfg.max_domains]

    results: dict = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "targets_file": str(targets_path),
        "actor_id": cfg.actor_id,
        "domains": domains,
        "counts": {},
        "errors": {},
    }

    for idx, d in enumerate(domains):
        if idx == 0 or (idx + 1) % 5 == 0 or (idx + 1) == len(domains):
            print(f"[darkweb] {idx+1}/{len(domains)}: {d}")

        # Based on the pplx toolchain's actor input, but with screenshots disabled.
        run_input = {
            "mode": "monitoring",
            "query": d,
            "targets": [],
            "keywords": [d],
            "region": "US",
            "maxPagesPerTarget": 5,
            "saveScreenshots": False,
            "saveVideo": False,
            "concurrency": 1,
        }

        try:
            run_resp = apify_actor_run(cfg.token, cfg.actor_id, run_input, timeout=cfg.timeout)
            run_data = run_resp.get("data") if isinstance(run_resp.get("data"), dict) else {}
            run_id = run_data.get("id")
            dataset_id = run_data.get("defaultDatasetId")
            if not run_id:
                raise RuntimeError("Apify run did not return a run id")

            # Poll run until finished (or timeout).
            start = time.time()
            status = None
            while True:
                run_obj = apify_run_get(cfg.token, str(run_id), timeout=cfg.timeout)
                run_data2 = run_obj.get("data") if isinstance(run_obj.get("data"), dict) else {}
                status = run_data2.get("status")
                if status in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
                    if not dataset_id:
                        dataset_id = run_data2.get("defaultDatasetId")
                    break
                if time.time() - start > cfg.max_wait_s:
                    status = "TIMEOUT_LOCAL"
                    break
                time.sleep(cfg.poll_s)

            hits = None
            if dataset_id:
                ds = apify_dataset_get(cfg.token, str(dataset_id), timeout=cfg.timeout)
                hits = dataset_item_count(ds)

            results["counts"][d] = {
                "status": status,
                "hits": hits,
                "run_id": run_id,
                "dataset_id": dataset_id,
            }
        except Exception as exc:
            results["errors"][d] = str(exc)

        if cfg.sleep_s:
            time.sleep(cfg.sleep_s)

    json_path = out_dir / "darkweb_counts.json"
    md_path = out_dir / "darkweb_counts.md"
    json_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    lines: list[str] = []
    lines.append("# Genesis Dark Web Keyword Monitor (Counts Only)\n")
    lines.append(f"- Generated: {results['generated_at']}")
    lines.append(f"- Targets: `{targets_path}`")
    lines.append(f"- Actor: `{cfg.actor_id}`\n")

    lines.append("## Results\n")
    for d in domains:
        if d in results["errors"]:
            lines.append(f"- `{d}`: error: {results['errors'][d]}")
            continue
        row = results["counts"].get(d, {}) if isinstance(results["counts"].get(d), dict) else {}
        hits = row.get("hits")
        status = row.get("status")
        lines.append(f"- `{d}`: status={status} hits={hits}")

    md_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


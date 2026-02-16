#!/usr/bin/env python3
"""
macos_account_audit.py

Privacy-preserving macOS account + messaging footprint audit.

Goal: help diagnose "multiple macOS users, iCloud/Messages/FaceTime confusion" without
dumping Apple IDs, phone numbers, or message contents.

What it collects:
- OS version + basic host info
- MDM enrollment / configuration profile status (via `profiles`)
- Local user list + per-user UUID + home directory
- Existence + metadata + SHA-256 for common Apple account + Messages artifacts
- SQLite row-count summaries for Accounts and Messages databases (no identifiers)

This script intentionally does NOT extract Apple IDs, handles, phone numbers, or message text.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import socket
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, Iterable


ARTIFACTS: dict[str, str] = {
    "accounts_db": "Library/Accounts/Accounts4.sqlite",
    "mobileme_accounts_plist": "Library/Preferences/MobileMeAccounts.plist",
    "madrid_plist": "Library/Preferences/com.apple.madrid.plist",
    "facetime_plist": "Library/Preferences/com.apple.FaceTime.plist",
    "ids_facetime_plist": "Library/Preferences/com.apple.imservice.ids.FaceTime.plist",
    "ids_imessage_plist": "Library/Preferences/com.apple.imservice.ids.iMessage.plist",
    "messages_db": "Library/Messages/chat.db",
}


@dataclass(frozen=True)
class CmdResult:
    argv: list[str]
    returncode: int
    stdout: str
    stderr: str


def run_cmd(argv: list[str]) -> CmdResult:
    p = subprocess.run(argv, text=True, capture_output=True)
    return CmdResult(argv=argv, returncode=p.returncode, stdout=p.stdout, stderr=p.stderr)


def parse_sw_vers(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        out[k.strip()] = v.strip()
    return out


def dscl_list_users() -> list[dict[str, Any]]:
    res = run_cmd(["dscl", ".", "-list", "/Users", "UniqueID"])
    users: list[dict[str, Any]] = []
    if res.returncode != 0:
        return users
    for line in res.stdout.splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        name, uid_s = parts
        try:
            uid = int(uid_s)
        except ValueError:
            continue
        # On macOS, human users usually start at 501.
        if uid < 501:
            continue
        users.append({"name": name, "uid": uid})
    users.sort(key=lambda u: u["uid"])
    return users


def dscl_read_key(username: str, key: str) -> str | None:
    res = run_cmd(["dscl", ".", "-read", f"/Users/{username}", key])
    if res.returncode != 0:
        return None
    prefix = f"{key}:"
    for line in res.stdout.splitlines():
        if line.startswith(prefix):
            return line.split(":", 1)[1].strip()
    return None


def sha256_file(path: str, *, chunk_bytes: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_bytes)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def safe_stat(path: str) -> dict[str, Any]:
    st = os.stat(path)
    return {
        "size_bytes": st.st_size,
        "mtime": dt.datetime.fromtimestamp(st.st_mtime, tz=dt.timezone.utc).isoformat(),
        "mode_octal": oct(st.st_mode & 0o777),
        "uid": st.st_uid,
        "gid": st.st_gid,
    }


def sqlite_tables(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "select name from sqlite_master where type='table' order by name"
    ).fetchall()
    return [r[0] for r in rows]


def sqlite_scalar(conn: sqlite3.Connection, query: str) -> int | None:
    try:
        row = conn.execute(query).fetchone()
        if row is None:
            return None
        val = row[0]
        if val is None:
            return None
        return int(val)
    except Exception:
        return None


def sqlite_try_query(conn: sqlite3.Connection, query: str) -> list[tuple[Any, ...]] | None:
    try:
        return conn.execute(query).fetchall()
    except Exception:
        return None


def audit_messages_db(path: str) -> dict[str, Any]:
    out: dict[str, Any] = {"type": "messages_db"}
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        tables = sqlite_tables(conn)
        out["tables_present"] = tables
        counts: dict[str, int] = {}
        for table in ("message", "handle", "chat", "attachment"):
            if table in tables:
                n = sqlite_scalar(conn, f"select count(*) from {table}")
                if n is not None:
                    counts[f"{table}_rows"] = n
        out["counts"] = counts
    finally:
        conn.close()
    return out


def audit_accounts_db(path: str) -> dict[str, Any]:
    out: dict[str, Any] = {"type": "accounts_db"}
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        tables = sqlite_tables(conn)
        out["tables_present"] = tables
        counts: dict[str, int] = {}
        for table in ("ZACCOUNT", "ZACCOUNTTYPE", "ZCREDENTIALITEM", "ZAUTHORIZATION"):
            if table in tables:
                n = sqlite_scalar(conn, f"select count(*) from {table}")
                if n is not None:
                    counts[f"{table}_rows"] = n
        out["counts"] = counts

        # Helpful, non-PII breakdown: number of accounts by account-type identifier.
        if "ZACCOUNT" in tables and "ZACCOUNTTYPE" in tables:
            rows = sqlite_try_query(
                conn,
                """
                select t.ZIDENTIFIER as account_type, count(*) as n
                from ZACCOUNT a
                join ZACCOUNTTYPE t on t.Z_PK = a.ZACCOUNTTYPE
                group by t.ZIDENTIFIER
                order by n desc, t.ZIDENTIFIER asc
                """.strip(),
            )
            if rows is not None:
                out["account_type_counts"] = [
                    {"account_type": r[0], "count": int(r[1])} for r in rows
                ]
    finally:
        conn.close()
    return out


def audit_artifacts_for_home(home: str, *, do_hash: bool) -> dict[str, Any]:
    artifacts: dict[str, Any] = {}
    for key, rel in ARTIFACTS.items():
        path = os.path.join(home, rel)
        entry: dict[str, Any] = {"path": path}
        try:
            entry["stat"] = safe_stat(path)
            entry["exists"] = True
        except Exception as exc:
            if isinstance(exc, FileNotFoundError):
                entry["exists"] = False
            elif isinstance(exc, PermissionError):
                # PermissionError can happen when another user's home is not accessible.
                entry["exists"] = True
                entry["readable"] = False
            else:
                entry["exists"] = None
            entry["stat_error"] = f"{type(exc).__name__}: {exc}"
            artifacts[key] = entry
            continue

        entry["readable"] = os.access(path, os.R_OK)
        if entry["readable"] and do_hash:
            try:
                entry["sha256"] = sha256_file(path)
            except Exception as exc:
                entry["sha256_error"] = f"{type(exc).__name__}: {exc}"
        if entry["readable"] and key == "messages_db" and path.endswith(".db"):
            try:
                entry["sqlite_summary"] = audit_messages_db(path)
            except Exception as exc:
                entry["sqlite_error"] = f"{type(exc).__name__}: {exc}"
        if entry["readable"] and key == "accounts_db" and path.endswith(".sqlite"):
            try:
                entry["sqlite_summary"] = audit_accounts_db(path)
            except Exception as exc:
                entry["sqlite_error"] = f"{type(exc).__name__}: {exc}"
        artifacts[key] = entry
    return artifacts


def write_json(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Privacy-preserving macOS account audit.")
    p.add_argument(
        "--out",
        default=None,
        help="Write report JSON to this path (default: ./audit/<timestamp>/report.json)",
    )
    p.add_argument(
        "--include-other-users",
        action="store_true",
        help="Attempt to audit all local human users (may require sudo for other homes).",
    )
    p.add_argument(
        "--no-hash",
        action="store_true",
        help="Skip SHA-256 hashing (faster; still collects file existence/stat).",
    )
    return p.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    timestamp = dt.datetime.now(tz=dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = args.out or os.path.join("audit", timestamp, "report.json")

    sw = run_cmd(["sw_vers"])
    uname = run_cmd(["uname", "-a"])
    profiles_status = run_cmd(["profiles", "status", "-type", "enrollment"])
    profiles_list = run_cmd(["profiles", "list"])

    users = dscl_list_users()
    current_user = os.environ.get("USER") or ""

    report: dict[str, Any] = {
        "generated_at": dt.datetime.now(tz=dt.timezone.utc).isoformat(),
        "host": {
            "hostname": socket.gethostname(),
            "sw_vers": parse_sw_vers(sw.stdout),
            "uname": uname.stdout.strip(),
        },
        "mdm": {
            "profiles_status_enrollment": {
                "returncode": profiles_status.returncode,
                "stdout": profiles_status.stdout.strip(),
                "stderr": profiles_status.stderr.strip(),
            },
            "profiles_list_current_user": {
                "returncode": profiles_list.returncode,
                "stdout": profiles_list.stdout.strip(),
                "stderr": profiles_list.stderr.strip(),
            },
        },
        "users": [],
        "notes": [
            "This report intentionally omits Apple IDs, phone numbers, iMessage handles, and message contents.",
            "If you need account identifiers, use System Settings under each macOS user, or consult Apple/IT.",
        ],
    }

    for u in users:
        name = u["name"]
        if not args.include_other_users and name != current_user:
            continue
        home = dscl_read_key(name, "NFSHomeDirectory") or f"/Users/{name}"
        generated_uid = dscl_read_key(name, "GeneratedUID")
        entry: dict[str, Any] = {
            "name": name,
            "uid": u["uid"],
            "generated_uid": generated_uid,
            "home": home,
        }
        entry["artifacts"] = audit_artifacts_for_home(home, do_hash=not args.no_hash)
        report["users"].append(entry)

    write_json(out_path, report)

    # Minimal stdout (safe to show). The full report lives on disk.
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

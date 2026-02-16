#!/usr/bin/env python3
import argparse
import csv
import datetime as dt
import os
import re
import sqlite3
from typing import Optional, Tuple

try:
    from dateutil import parser as date_parser  # type: ignore
except Exception:
    date_parser = None

TIME_COL_RE = re.compile(r"(time|date|created|modified|accessed|last|first|timestamp|ts)", re.IGNORECASE)
SKIP_COL_RE = re.compile(r"(timezone|time_zone|offset)", re.IGNORECASE)

SUMMARY_HINTS = [
    "name", "path", "title", "user", "account", "process", "url", "host",
    "bundle", "app", "sender", "recipient", "contact", "number", "id",
    "domain", "ssid",
]


def is_time_column(col: str) -> bool:
    if SKIP_COL_RE.search(col):
        return False
    return bool(TIME_COL_RE.search(col))


def to_iso_utc(d: dt.datetime) -> str:
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return d.astimezone(dt.timezone.utc).isoformat()


def parse_time_value(value) -> Tuple[Optional[str], Optional[str]]:
    if value is None:
        return None, None

    if isinstance(value, (bytes, bytearray)):
        try:
            value = value.decode("utf-8", errors="replace")
        except Exception:
            value = str(value)

    if isinstance(value, (int, float)):
        n = float(value)
        return convert_epoch(n)

    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None, None
        if re.fullmatch(r"[-+]?\d+(\.\d+)?", s):
            try:
                n = float(s)
                return convert_epoch(n)
            except Exception:
                pass

        try:
            s2 = s.replace("Z", "+00:00")
            d = dt.datetime.fromisoformat(s2)
            return to_iso_utc(d), "string_iso"
        except Exception:
            pass

        if date_parser is not None:
            try:
                d = date_parser.parse(s)
                return to_iso_utc(d), "string_parse"
            except Exception:
                pass

        for fmt in (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M:%S.%f",
            "%m/%d/%Y %H:%M:%S",
            "%m/%d/%Y %H:%M",
            "%Y-%m-%d",
        ):
            try:
                d = dt.datetime.strptime(s, fmt)
                return to_iso_utc(d), "string_fmt"
            except Exception:
                continue

    return None, None


def convert_epoch(n: float) -> Tuple[Optional[str], Optional[str]]:
    try:
        if n > 1e17:
            d = dt.datetime.fromtimestamp(n / 1e9, tz=dt.timezone.utc)
            return to_iso_utc(d), "unix_ns"
        if n > 1e14:
            d = dt.datetime.fromtimestamp(n / 1e6, tz=dt.timezone.utc)
            return to_iso_utc(d), "unix_us"
        if n > 1e12:
            d = dt.datetime.fromtimestamp(n / 1e3, tz=dt.timezone.utc)
            return to_iso_utc(d), "unix_ms"
        if n > 1e9:
            d = dt.datetime.fromtimestamp(n, tz=dt.timezone.utc)
            return to_iso_utc(d), "unix_s"

        mac_epoch = dt.datetime(2001, 1, 1, tzinfo=dt.timezone.utc)
        d = mac_epoch + dt.timedelta(seconds=n)
        return to_iso_utc(d), "mac_absolute"
    except Exception:
        return None, None


def pick_summary_columns(columns):
    picks = []
    for hint in SUMMARY_HINTS:
        for c in columns:
            if c not in picks and hint in c.lower():
                picks.append(c)
            if len(picks) >= 4:
                return picks
    return picks


def build_summary(row, summary_cols):
    parts = []
    for c in summary_cols:
        try:
            v = row[c]
        except Exception:
            v = None
        if v is None:
            continue
        if isinstance(v, (bytes, bytearray)):
            v = v.decode("utf-8", errors="replace")
        s = str(v)
        if len(s) > 200:
            s = s[:200] + "..."
        parts.append(f"{c}={s}")
    return " | ".join(parts)


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def main():
    parser = argparse.ArgumentParser(description="Build a unified timeline CSV from mac_apt sqlite output")
    parser.add_argument("--input", required=True, help="mac_apt output folder or mac_apt.db path")
    parser.add_argument("--output", required=False, help="Output CSV path")
    parser.add_argument("--user-path", required=False, help="Filter rows to this user path")
    args = parser.parse_args()

    input_path = args.input
    user_path = args.user_path

    if os.path.isdir(input_path):
        db_path = os.path.join(input_path, "mac_apt.db")
        if not os.path.exists(db_path):
            raise SystemExit(f"No mac_apt.db found in {input_path}")
        if args.output:
            out_csv = args.output
        else:
            out_dir = os.path.join(input_path, "_Timeline")
            ensure_dir(out_dir)
            out_csv = os.path.join(out_dir, "macapt_timeline.csv")
    else:
        db_path = input_path
        if args.output:
            out_csv = args.output
        else:
            out_csv = os.path.join(os.path.dirname(db_path), "macapt_timeline.csv")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    tables = [r[0] for r in cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()]

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["iso_utc", "time_guess", "raw_time", "table", "column", "rowid", "summary"])

        for table in tables:
            cols_info = cur.execute(f"PRAGMA table_info({table});").fetchall()
            colnames = [c[1] for c in cols_info]
            time_cols = [c for c in colnames if is_time_column(c)]
            if not time_cols:
                continue

            summary_cols = pick_summary_columns(colnames)
            select_cols = ["rowid"] + time_cols + summary_cols
            select_sql = f"SELECT {', '.join(select_cols)} FROM {table}"

            try:
                for row in cur.execute(select_sql):
                    summary = build_summary(row, summary_cols)
                    if user_path and user_path not in summary:
                        continue
                    rowid = row["rowid"]
                    for tc in time_cols:
                        iso, guess = parse_time_value(row[tc])
                        if not iso:
                            continue
                        writer.writerow([iso, guess, row[tc], table, tc, rowid, summary])
            except sqlite3.Error:
                continue

    conn.close()
    print(f"Timeline CSV written to: {out_csv}")


if __name__ == "__main__":
    main()

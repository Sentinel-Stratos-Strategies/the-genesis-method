#!/usr/bin/env python3
import argparse
import os
import sqlite3
from datetime import datetime

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_label TEXT NOT NULL,
  tool TEXT NOT NULL,
  output_dir TEXT NOT NULL,
  created_at TEXT NOT NULL
);
"""


def init_db(db_path):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(SCHEMA)
    conn.commit()
    return conn


def register_run(db_path, user_label, tool, output_dir):
    conn = init_db(db_path)
    conn.execute(
        "INSERT INTO runs (user_label, tool, output_dir, created_at) VALUES (?, ?, ?, ?)",
        (user_label, tool, output_dir, datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()
    conn.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument("--tool", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    register_run(args.db, args.user, args.tool, args.output_dir)
    print("Recorded run")


if __name__ == "__main__":
    main()

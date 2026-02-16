#!/usr/bin/env python3
import argparse
import hashlib
import os


def sha256_file(path, chunk_size=1024 * 1024):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    output_dir = os.path.abspath(args.output_dir)
    manifest_path = os.path.join(output_dir, "manifest_sha256.txt")

    entries = []
    for root, _, files in os.walk(output_dir):
        for name in files:
            path = os.path.join(root, name)
            if os.path.abspath(path) == manifest_path:
                continue
            rel = os.path.relpath(path, output_dir)
            try:
                digest = sha256_file(path)
            except OSError:
                continue
            entries.append((rel, digest))

    entries.sort()
    with open(manifest_path, "w", encoding="utf-8") as f:
        for rel, digest in entries:
            f.write(f"{digest}  {rel}\n")

    print(f"Wrote {manifest_path}")


if __name__ == "__main__":
    main()

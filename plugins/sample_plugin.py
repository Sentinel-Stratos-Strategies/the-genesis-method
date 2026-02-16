#!/usr/bin/env python3
import os
from datetime import datetime


def run(output_dir, context):
    summary_dir = os.path.join(output_dir, "_Summary")
    os.makedirs(summary_dir, exist_ok=True)
    out_path = os.path.join(summary_dir, "plugin_sample.txt")

    file_count = 0
    for _, _, files in os.walk(output_dir):
        file_count += len(files)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"Plugin: sample_plugin\n")
        f.write(f"Context: {context}\n")
        f.write(f"File count: {file_count}\n")
        f.write(f"Generated: {datetime.now().isoformat(timespec='seconds')}\n")

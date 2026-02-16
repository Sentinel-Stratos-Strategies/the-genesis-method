__artifacts_v2__ = {
    "snapchatAppFiles": {
        "name": "Snapchat - App Files (Inventory)",
        "description": "Lists Snapchat app container files and timestamps. No message reconstruction.",
        "author": "@codex",
        "creation_date": "2026-02-15",
        "last_update_date": "2026-02-15",
        "requirements": "none",
        "category": "Snapchat",
        "notes": "Inventory only; does not parse message content.",
        "paths": (
            "*/com.toyopagroup.picaboo/*",
            "*/group.com.toyopagroup.picaboo/*",
        ),
        "output_types": "standard",
        "artifact_icon": "camera",
    }
}

import datetime
from pathlib import Path

from scripts.ilapfuncs import artifact_processor


@artifact_processor
def snapchatAppFiles(context):
    data_list = []

    for file_found in context.get_files_found():
        file_path = Path(str(file_found))
        try:
            stat = file_path.stat()
        except OSError:
            continue

        size_bytes = stat.st_size
        modified_utc = datetime.datetime.fromtimestamp(
            stat.st_mtime, tz=datetime.timezone.utc
        )

        suffix = file_path.suffix.lower()
        if suffix in (".db", ".sqlite", ".sqlite3", ".sqlitedb"):
            file_type = "sqlite"
        elif suffix == ".plist":
            file_type = "plist"
        else:
            file_type = suffix[1:] if suffix else "file"

        data_list.append((modified_utc, file_type, size_bytes, str(file_path)))

    data_headers = (("Modified (UTC)", "datetime"), "Type", "Size (bytes)", "Source Path")

    return data_headers, data_list, "Paths matching Snapchat app containers"

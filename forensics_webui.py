#!/usr/bin/env python3
import http.server
import json
import mimetypes
import os
import socketserver
import subprocess
import threading
import time
import webbrowser
from pathlib import Path
from urllib.parse import urlparse


ROOT_HOUSE = str(Path(__file__).resolve().parent)
PROJECT_NAME = Path(ROOT_HOUSE).name
HOUSE_OUT_BASE = os.environ.get("OUT_DIR_HOUSE", "/Users/House/EVIDENCE")
DEFAULT_FAM_TOOLS = os.path.join("/Users/fam/Tools", PROJECT_NAME)
DEFAULT_FAM_USER = os.path.join("/Users/fam", PROJECT_NAME)

if "GENESIS_FAM_ROOT" in os.environ:
    ROOT_FAM = os.environ["GENESIS_FAM_ROOT"]
elif os.path.isdir(DEFAULT_FAM_TOOLS):
    ROOT_FAM = DEFAULT_FAM_TOOLS
elif os.path.isdir(DEFAULT_FAM_USER):
    ROOT_FAM = DEFAULT_FAM_USER
else:
    ROOT_FAM = "/Users/fam"
FAM_OUT_BASE = os.environ.get("OUT_DIR_FAM", os.path.join(ROOT_FAM, "forensics_out"))

WEBUI_DIR = os.path.join(ROOT_HOUSE, "webui")
ASSETS_DIR = os.path.join(ROOT_HOUSE, "assets")
LAUNCHER = os.path.join(ROOT_HOUSE, "run_forensics.sh")
API_LOG = os.path.join(HOUSE_OUT_BASE, "_logs", "webui_actions.log")
PORT = 8123

RUN_LOCK = threading.Lock()
RUN_STATE = {
    "running": False,
    "choice": None,
    "pid": None,
    "started_at": None,
    "last_choice": None,
    "last_rc": None,
    "last_finished_at": None,
    "log": API_LOG,
}


def ensure_log_dir():
    os.makedirs(os.path.dirname(API_LOG), exist_ok=True)


def launch_choice(choice: str):
    ensure_log_dir()
    with RUN_LOCK:
        if RUN_STATE["running"]:
            return False, "A run is already in progress."
        if not choice.isdigit():
            return False, "Choice must be numeric."

        env = os.environ.copy()
        env["GENESIS_FAM_ROOT"] = ROOT_FAM
        log_handle = open(API_LOG, "a", encoding="utf-8")
        log_handle.write(f"\n=== {time.strftime('%Y-%m-%d %H:%M:%S')} choice={choice} ===\n")
        log_handle.flush()

        proc = subprocess.Popen(
            [LAUNCHER, "--choice", choice],
            cwd=ROOT_HOUSE,
            env=env,
            stdout=log_handle,
            stderr=log_handle,
            text=True,
        )
        RUN_STATE["running"] = True
        RUN_STATE["choice"] = choice
        RUN_STATE["pid"] = proc.pid
        RUN_STATE["started_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

    def _watch():
        rc = proc.wait()
        log_handle.write(f"=== completed rc={rc} ===\n")
        log_handle.flush()
        log_handle.close()
        with RUN_LOCK:
            RUN_STATE["running"] = False
            RUN_STATE["last_choice"] = choice
            RUN_STATE["last_rc"] = rc
            RUN_STATE["last_finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            RUN_STATE["choice"] = None
            RUN_STATE["pid"] = None
            RUN_STATE["started_at"] = None

    threading.Thread(target=_watch, daemon=True).start()
    return True, f"Started choice {choice} (pid {proc.pid})."


class Handler(http.server.SimpleHTTPRequestHandler):
    def _send_json(self, status_code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_file(self, fs_path, content_type):
        if not os.path.exists(fs_path):
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-type", content_type)
        self.end_headers()
        with open(fs_path, "rb") as f:
            self.wfile.write(f.read())

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ["/", "/index.html"]:
            return self._serve_file(os.path.join(WEBUI_DIR, "index.html"), "text/html")
        if parsed.path == "/app.css":
            return self._serve_file(os.path.join(WEBUI_DIR, "app.css"), "text/css")
        if parsed.path == "/app.js":
            return self._serve_file(os.path.join(WEBUI_DIR, "app.js"), "application/javascript")
        if parsed.path == "/api/status":
            with RUN_LOCK:
                return self._send_json(200, RUN_STATE)
        if parsed.path.startswith("/assets/"):
            rel = parsed.path.replace("/assets/", "", 1)
            asset_path = os.path.join(ASSETS_DIR, rel)
            content_type = mimetypes.guess_type(asset_path)[0] or "application/octet-stream"
            return self._serve_file(asset_path, content_type)
        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/run/"):
            choice = parsed.path.split("/")[-1]
            ok, msg = launch_choice(choice)
            if ok:
                return self._send_json(200, {"ok": True, "message": msg})
            return self._send_json(409, {"ok": False, "message": msg})
        self.send_error(404)

    def translate_path(self, path):
        clean_path = urlparse(path).path.lstrip("/")
        if clean_path == "evidence-house" or clean_path.startswith("evidence-house/"):
            rel = clean_path[15:] if clean_path.startswith("evidence-house/") else ""
            return os.path.join(HOUSE_OUT_BASE, rel)
        if clean_path == "evidence-fam" or clean_path.startswith("evidence-fam/"):
            rel = clean_path[13:] if clean_path.startswith("evidence-fam/") else ""
            return os.path.join(FAM_OUT_BASE, rel)
        if clean_path == "fam" or clean_path.startswith("fam/"):
            rel = clean_path[4:] if clean_path.startswith("fam/") else ""
            return os.path.join(ROOT_FAM, rel)
        if clean_path == "house" or clean_path.startswith("house/"):
            rel = clean_path[6:] if clean_path.startswith("house/") else ""
            return os.path.join(ROOT_HOUSE, rel)
        return os.path.join(ROOT_HOUSE, clean_path)


os.chdir(ROOT_HOUSE)
with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as httpd:
    print(f"Serving {ROOT_HOUSE} at http://127.0.0.1:{PORT}/")
    print(f"Serving {ROOT_FAM} at http://127.0.0.1:{PORT}/fam/")
    print(f"Serving house evidence at http://127.0.0.1:{PORT}/evidence-house/")
    print(f"Serving fam evidence at http://127.0.0.1:{PORT}/evidence-fam/")
    webbrowser.open(f"http://127.0.0.1:{PORT}/")
    httpd.serve_forever()

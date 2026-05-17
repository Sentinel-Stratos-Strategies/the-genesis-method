#!/usr/bin/env python3
import http.server
import json
import mimetypes
import os
import socketserver
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path
from urllib.parse import unquote, urlparse


ROOT_HOUSE = str(Path(__file__).resolve().parent)
ROOT_PATH = Path(ROOT_HOUSE)
PROJECT_NAME = ROOT_PATH.name

sys.path.insert(0, os.path.join(ROOT_HOUSE, "tools"))
from genesis_paths import load_paths as _load_genesis_paths  # noqa: E402

_GP = _load_genesis_paths(ROOT_PATH)
HOUSE_OUT_BASE = os.environ.get("OUT_DIR_HOUSE", "/Users/House/EVIDENCE")
ENTERPRISE_OUT_BASE = os.environ.get(
    "GENESIS_OUTPUT_BASE",
    _GP.get("evidence_output_root") or os.path.join(ROOT_HOUSE, "outputs"),
)
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
PLUGIN_RUNNER = os.path.join(ROOT_HOUSE, "tools", "plugin_runner.py")
PLUGIN_DIR = os.path.join(ROOT_HOUSE, "plugins")
CONFIG_DIR = os.path.join(ROOT_HOUSE, "config")
LLM_CONFIG_PATH = os.path.join(CONFIG_DIR, "genesis_llm_config.json")
LLM_SECRET_ENV_PATH = os.path.join(CONFIG_DIR, ".genesis_llm_secrets.env")
PORT = 8123
DEFAULT_INPUT_DIR = os.environ.get("GENESIS_DEFAULT_INPUT", _GP.get("evidence_input_root") or "/Volumes/Stratos_Tools/GENESIS_EVIDENCE_INPUT/staging")
DEFAULT_OUTPUT_BASE = ENTERPRISE_OUT_BASE
API_LOG = os.path.join(DEFAULT_OUTPUT_BASE, "_logs", "webui_actions.log")

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


def _safe_case_name(value: str) -> str:
    value = (value or "").strip() or time.strftime("genesis_case_%Y%m%d_%H%M%S")
    return "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in value)[:80]


def _read_json_body(handler):
    length = int(handler.headers.get("Content-Length", "0") or 0)
    if length <= 0:
        return {}
    raw = handler.rfile.read(length)
    try:
        return json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        return {}


def _resolve_run_config(payload):
    input_dir = os.path.abspath(os.path.expanduser(payload.get("inputDir") or DEFAULT_INPUT_DIR))
    output_base = os.path.abspath(os.path.expanduser(payload.get("outputBase") or DEFAULT_OUTPUT_BASE))
    output_name = _safe_case_name(payload.get("outputName") or "")
    output_dir = os.path.join(output_base, output_name)
    return input_dir, output_base, output_name, output_dir


def _default_llm_config():
    return {
        "provider": "ollama",
        "model": "mistral-nemo:latest",
        "base_url": "http://127.0.0.1:11436",
        "api_key_env": "GENESIS_LLM_API_KEY",
        "temperature": 0.1,
        "memory_roots": [
            "/Volumes/SENTINEL/memory",
            "/Volumes/SENTINEL/Developer",
            "/Volumes/SENTINEL/SENTINEL_MistralNemo",
            "/Volumes/Stratos_Tools/projects/GENESIS_MEMORY",
        ],
        "runtime": {
            "type": "ollama",
            "ollama_bin": "/Volumes/Stratos_Tools/homebrew/bin/ollama",
            "runtime_script": os.path.join(ROOT_HOUSE, "tools", "ai", "run_genesis_ollama_runtime.sh"),
            "orbstack_app": "/Applications/OrbStack.app",
            "host": "127.0.0.1",
            "port": 11436,
        },
        "training": {
            "framework": "unsloth",
            "repo": "/Volumes/SENTINEL/AgentWork/training/unsloth",
            "job_manifest": "/Volumes/Stratos_Tools/projects/GENESIS_MEMORY/ops/genesis_autoapprove/unsloth_job_manifest.json",
            "train_script": "/Volumes/Stratos_Tools/projects/GENESIS_MEMORY/ops/genesis_autoapprove/train_unsloth_jobs.sh",
            "mistral_training_run": "/Volumes/Stratos_Tools/projects/GENESIS_MEMORY/training_runs/mistral",
        },
    }


def load_llm_config():
    config = _default_llm_config()
    if os.path.exists(LLM_CONFIG_PATH):
        try:
            with open(LLM_CONFIG_PATH, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                config.update(loaded)
                config["runtime"] = {**_default_llm_config()["runtime"], **loaded.get("runtime", {})}
                config["training"] = {**_default_llm_config()["training"], **loaded.get("training", {})}
        except Exception as exc:
            config["load_error"] = str(exc)
    return config


def _mask_secret(value):
    if not value:
        return ""
    if len(value) <= 10:
        return "configured"
    return f"{value[:4]}...{value[-4:]}"


def _read_secret_env_file():
    values = {}
    if not os.path.exists(LLM_SECRET_ENV_PATH):
        return values
    with open(LLM_SECRET_ENV_PATH, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def _llm_secret_status(config):
    env_name = (config.get("api_key_env") or "GENESIS_LLM_API_KEY").strip()
    secrets = _read_secret_env_file()
    value = os.environ.get(env_name) or secrets.get(env_name) or ""
    return {
        "env": env_name,
        "present": bool(value),
        "masked": _mask_secret(value),
    }


def save_llm_config(payload):
    config = load_llm_config()
    allowed_top = {"provider", "model", "base_url", "api_key_env", "temperature", "memory_roots"}
    for key in allowed_top:
        if key in payload:
            config[key] = payload[key]

    for section in ("runtime", "training"):
        if isinstance(payload.get(section), dict):
            existing = config.get(section, {})
            if not isinstance(existing, dict):
                existing = {}
            existing.update(payload[section])
            config[section] = existing

    api_key = (payload.get("api_key") or "").strip()
    if api_key:
        env_name = (config.get("api_key_env") or "GENESIS_LLM_API_KEY").strip()
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(LLM_SECRET_ENV_PATH, "w", encoding="utf-8") as f:
            f.write(f"{env_name}={api_key}\n")
        os.chmod(LLM_SECRET_ENV_PATH, 0o600)

    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(LLM_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
        f.write("\n")
    return config


def llm_status():
    config = load_llm_config()
    runtime = config.get("runtime", {}) if isinstance(config.get("runtime"), dict) else {}
    training = config.get("training", {}) if isinstance(config.get("training"), dict) else {}
    provider = config.get("provider", "ollama")
    base_url = str(config.get("base_url") or "")
    status = {
        "config": config,
        "secret": _llm_secret_status(config),
        "paths": {
            "config": LLM_CONFIG_PATH,
            "secret_env": LLM_SECRET_ENV_PATH,
            "runtime_script_exists": os.path.exists(str(runtime.get("runtime_script", ""))),
            "ollama_bin_exists": os.path.exists(str(runtime.get("ollama_bin", ""))),
            "orbstack_exists": os.path.exists(str(runtime.get("orbstack_app", ""))),
            "unsloth_repo_exists": os.path.exists(str(training.get("repo", ""))),
            "training_manifest_exists": os.path.exists(str(training.get("job_manifest", ""))),
        },
        "runtime": {
            "reachable": False,
            "models": [],
            "error": "",
        },
    }
    if provider == "ollama" and base_url:
        try:
            req = urllib.request.Request(base_url.rstrip("/") + "/api/tags")
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            status["runtime"]["reachable"] = True
            status["runtime"]["models"] = [
                item.get("name") for item in data.get("models", []) if isinstance(item, dict) and item.get("name")
            ]
        except Exception as exc:
            status["runtime"]["error"] = str(exc)
    return status


def start_llm_runtime(payload=None):
    ensure_log_dir()
    config = save_llm_config(payload or {}) if payload else load_llm_config()
    runtime = config.get("runtime", {}) if isinstance(config.get("runtime"), dict) else {}
    script = str(runtime.get("runtime_script") or "")
    model = str(config.get("model") or "mistral-nemo:latest")
    if not script or not os.path.exists(script):
        return False, f"Runtime script not found: {script}"
    with RUN_LOCK:
        if RUN_STATE["running"]:
            return False, "A run is already in progress."
        env = os.environ.copy()
        env["GENESIS_QWEN_MODEL"] = model
        env["GENESIS_LLM_MODEL"] = model
        log_handle = open(API_LOG, "a", encoding="utf-8")
        log_handle.write(f"\n=== {time.strftime('%Y-%m-%d %H:%M:%S')} llm-runtime model={model} script={script} ===\n")
        log_handle.flush()
        proc = subprocess.Popen(
            [script, model],
            cwd=os.path.dirname(script),
            env=env,
            stdout=log_handle,
            stderr=log_handle,
            text=True,
        )
        RUN_STATE["running"] = True
        RUN_STATE["choice"] = f"llm:{model}"
        RUN_STATE["pid"] = proc.pid
        RUN_STATE["started_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

    def _watch():
        rc = proc.wait()
        log_handle.write(f"=== llm runtime completed rc={rc} ===\n")
        log_handle.flush()
        log_handle.close()
        with RUN_LOCK:
            RUN_STATE["running"] = False
            RUN_STATE["last_choice"] = f"llm:{model}"
            RUN_STATE["last_rc"] = rc
            RUN_STATE["last_finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            RUN_STATE["choice"] = None
            RUN_STATE["pid"] = None
            RUN_STATE["started_at"] = None

    threading.Thread(target=_watch, daemon=True).start()
    return True, f"Started local LLM runtime for {model} (pid {proc.pid})."


def list_plugins():
    try:
        res = subprocess.run(
            [sys.executable, PLUGIN_RUNNER, "--plugin-dir", PLUGIN_DIR, "--list"],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(res.stdout)
    except Exception as exc:
        print(f"Error listing plugins: {exc}")
        return []


def launch_plugin(plugin_id: str, payload=None):
    payload = payload or {}
    ensure_log_dir()
    with RUN_LOCK:
        if RUN_STATE["running"]:
            return False, "A run is already in progress."

        plugins = list_plugins()
        plugin = next((p for p in plugins if p["id"] == plugin_id), None)
        if not plugin:
            return False, f"Plugin not found: {plugin_id}"

        input_dir, _output_base, _output_name, target_dir = _resolve_run_config(payload)
        os.makedirs(target_dir, exist_ok=True)

        env = os.environ.copy()
        env["GENESIS_FAM_ROOT"] = ROOT_FAM
        env["GENESIS_INPUT_DIR"] = input_dir
        env["GENESIS_OUTPUT_DIR"] = target_dir
        log_handle = open(API_LOG, "a", encoding="utf-8")
        log_handle.write(f"\n=== {time.strftime('%Y-%m-%d %H:%M:%S')} plugin={plugin_id} input={input_dir} output={target_dir} ===\n")
        log_handle.flush()

        proc = subprocess.Popen(
            [
                sys.executable,
                PLUGIN_RUNNER,
                "--plugin-dir",
                PLUGIN_DIR,
                "--plugin",
                plugin_id,
                "--output-dir",
                target_dir,
                "--input-dir",
                input_dir,
            ],
            cwd=ROOT_HOUSE,
            env=env,
            stdout=log_handle,
            stderr=log_handle,
            text=True,
        )
        RUN_STATE["running"] = True
        RUN_STATE["choice"] = f"plugin:{plugin_id}"
        RUN_STATE["pid"] = proc.pid
        RUN_STATE["started_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

    def _watch():
        rc = proc.wait()
        log_handle.write(f"=== plugin completed rc={rc} ===\n")
        log_handle.flush()
        log_handle.close()
        with RUN_LOCK:
            RUN_STATE["running"] = False
            RUN_STATE["last_choice"] = f"plugin:{plugin_id}"
            RUN_STATE["last_rc"] = rc
            RUN_STATE["last_finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            RUN_STATE["choice"] = None
            RUN_STATE["pid"] = None
            RUN_STATE["started_at"] = None

    threading.Thread(target=_watch, daemon=True).start()
    return True, f"Started plugin {plugin_id} (pid {proc.pid})."


def launch_folder_pipeline(payload):
    ensure_log_dir()
    input_dir, _output_base, output_name, output_dir = _resolve_run_config(payload or {})
    pipeline = (payload or {}).get("pipeline") or "full"
    if not os.path.isdir(input_dir):
        return False, f"Input folder not found: {input_dir}"
    os.makedirs(output_dir, exist_ok=True)

    with RUN_LOCK:
        if RUN_STATE["running"]:
            return False, "A run is already in progress."

        env = os.environ.copy()
        env["GENESIS_INPUT_DIR"] = input_dir
        env["GENESIS_OUTPUT_DIR"] = output_dir
        log_handle = open(API_LOG, "a", encoding="utf-8")
        log_handle.write(f"\n=== {time.strftime('%Y-%m-%d %H:%M:%S')} folder-pipeline={pipeline} input={input_dir} output={output_dir} ===\n")
        log_handle.flush()

        cmd = [
            sys.executable,
            os.path.join(ROOT_HOUSE, "tools", "genesis_forensic_ops.py"),
            "run-folder",
            "--pipeline",
            pipeline,
            "--source",
            input_dir,
            "--output-dir",
            output_dir,
            "--case-id",
            output_name,
        ]

        proc = subprocess.Popen(
            cmd,
            cwd=ROOT_HOUSE,
            env=env,
            stdout=log_handle,
            stderr=log_handle,
            text=True,
        )
        RUN_STATE["running"] = True
        RUN_STATE["choice"] = f"folder:{pipeline}"
        RUN_STATE["pid"] = proc.pid
        RUN_STATE["started_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

    def _watch():
        rc = proc.wait()
        log_handle.write(f"=== folder pipeline completed rc={rc} ===\n")
        log_handle.flush()
        log_handle.close()
        with RUN_LOCK:
            RUN_STATE["running"] = False
            RUN_STATE["last_choice"] = f"folder:{pipeline}"
            RUN_STATE["last_rc"] = rc
            RUN_STATE["last_finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            RUN_STATE["choice"] = None
            RUN_STATE["pid"] = None
            RUN_STATE["started_at"] = None

    threading.Thread(target=_watch, daemon=True).start()
    return True, f"Started {pipeline} folder pipeline for {input_dir} -> {output_dir} (pid {proc.pid})."


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
        if parsed.path == "/api/plugins":
            return self._send_json(200, list_plugins())
        if parsed.path == "/api/config":
            return self._send_json(200, {
                "defaultInputDir": DEFAULT_INPUT_DIR,
                "defaultOutputBase": DEFAULT_OUTPUT_BASE,
                "root": ROOT_HOUSE,
                "log": API_LOG,
                "evidenceInputRoot": _GP.get("evidence_input_root", DEFAULT_INPUT_DIR),
                "evidenceOutputRoot": _GP.get("evidence_output_root", DEFAULT_OUTPUT_BASE),
                "memoryContractRoot": _GP.get("memory_contract_root", ""),
            })
        if parsed.path == "/api/llm/config":
            return self._send_json(200, llm_status())
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
        if parsed.path.startswith("/api/plugins/run/"):
            plugin_id = parsed.path.split("/")[-1]
            ok, msg = launch_plugin(plugin_id, _read_json_body(self))
            if ok:
                return self._send_json(200, {"ok": True, "message": msg})
            return self._send_json(409, {"ok": False, "message": msg})
        if parsed.path == "/api/folder/run":
            ok, msg = launch_folder_pipeline(_read_json_body(self))
            if ok:
                return self._send_json(200, {"ok": True, "message": msg})
            return self._send_json(409, {"ok": False, "message": msg})
        if parsed.path == "/api/llm/save":
            config = save_llm_config(_read_json_body(self))
            return self._send_json(200, {"ok": True, "message": "AI engine configuration saved.", "status": llm_status(), "config": config})
        if parsed.path == "/api/llm/start":
            ok, msg = start_llm_runtime(_read_json_body(self))
            if ok:
                return self._send_json(200, {"ok": True, "message": msg})
            return self._send_json(409, {"ok": False, "message": msg})
        if parsed.path == "/api/llm/test":
            return self._send_json(200, {"ok": True, "status": llm_status()})
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
        if clean_path == "outputs" or clean_path.startswith("outputs/"):
            rel = unquote(clean_path[8:]) if clean_path.startswith("outputs/") else ""
            return os.path.join(DEFAULT_OUTPUT_BASE, rel)
        if clean_path == "workspace" or clean_path.startswith("workspace/"):
            rel = unquote(clean_path[10:]) if clean_path.startswith("workspace/") else ""
            return os.path.join(ROOT_HOUSE, rel)
        return os.path.join(ROOT_HOUSE, clean_path)


os.chdir(ROOT_HOUSE)


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


with ReusableTCPServer(("127.0.0.1", PORT), Handler) as httpd:
    print(f"Serving {ROOT_HOUSE} at http://127.0.0.1:{PORT}/")
    print(f"Serving enterprise outputs at http://127.0.0.1:{PORT}/outputs/")
    _open_browser = os.environ.get("GENESIS_WEBUI_OPEN_BROWSER", "1").strip().lower()
    if _open_browser not in ("0", "false", "no"):
        webbrowser.open(f"http://127.0.0.1:{PORT}/")
    else:
        print("GENESIS_WEBUI_OPEN_BROWSER=0 — not opening system browser (embedded host expected).")
    httpd.serve_forever()

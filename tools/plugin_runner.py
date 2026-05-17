#!/usr/bin/env python3
import argparse
import importlib.util
import json
import os
import shlex
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def plugin_report_dir(output_dir):
    path = Path(output_dir) / "_Plugins"
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_plugin_report(output_dir, plugin_id, title, lines):
    report = plugin_report_dir(output_dir) / f"{plugin_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    with report.open("w", encoding="utf-8") as fh:
        fh.write(f"# {title}\n\n")
        for line in lines:
            fh.write(f"{line}\n")
    print(f"Plugin report: {report}")
    return str(report)


def _format_value(value, output_dir, context, input_dir=""):
    if not isinstance(value, str):
        return value
    values = {
        "root": str(ROOT_DIR),
        "tools": str(ROOT_DIR / "tools"),
        "plugins": str(ROOT_DIR / "plugins"),
        "python": sys.executable,
        "output_dir": output_dir or "",
        "context": context or "",
        "input_dir": input_dir or "",
    }
    return value.format(**values)


def _path_exists(path, output_dir, context, input_dir=""):
    resolved = Path(_format_value(path, output_dir, context, input_dir)).expanduser()
    if not resolved.is_absolute():
        resolved = ROOT_DIR / resolved
    return resolved.exists(), str(resolved)


def _command_exists(command, output_dir, context, input_dir=""):
    resolved = _format_value(command, output_dir, context, input_dir)
    if os.path.sep in resolved:
        return os.path.exists(os.path.expanduser(resolved)), resolved
    return shutil.which(resolved) is not None, resolved


def _manifest_plugin_run(plugin, output_dir, context, input_dir=""):
    missing = []
    for required_path in plugin.get("required_paths", []):
        ok, resolved = _path_exists(required_path, output_dir, context, input_dir)
        if not ok:
            missing.append(f"Missing path: `{resolved}`")
    for required_command in plugin.get("required_commands", []):
        ok, resolved = _command_exists(required_command, output_dir, context, input_dir)
        if not ok:
            missing.append(f"Missing command: `{resolved}`")

    if missing:
        write_plugin_report(
            output_dir,
            plugin["id"],
            f"{plugin['name']} - Skipped",
            [
                f"- Plugin ID: `{plugin['id']}`",
                f"- Category: `{plugin.get('category', 'General')}`",
                f"- Target: `{plugin.get('target', 'common')}`",
                "- Status: skipped because prerequisites were not present.",
                "",
                *missing,
            ],
        )
        return

    command = [_format_value(part, output_dir, context, input_dir) for part in plugin.get("command", [])]
    if not command:
        write_plugin_report(
            output_dir,
            plugin["id"],
            f"{plugin['name']} - Registered",
            [
                f"- Plugin ID: `{plugin['id']}`",
                f"- Category: `{plugin.get('category', 'General')}`",
                f"- Target: `{plugin.get('target', 'common')}`",
                "- Status: registry-only module. No command configured.",
                "",
                plugin.get("description", ""),
            ],
        )
        return

    print(f"Running command: {shlex.join(command)}")
    env = os.environ.copy()
    env.setdefault("GENESIS_ROOT", str(ROOT_DIR))
    env.setdefault("GENESIS_OUTPUT_DIR", output_dir)
    if input_dir:
        env.setdefault("GENESIS_INPUT_DIR", input_dir)
    for key, value in plugin.get("env", {}).items():
        env[key] = _format_value(value, output_dir, context, input_dir)

    result = subprocess.run(command, cwd=str(ROOT_DIR), env=env, text=True)
    if result.returncode:
        raise RuntimeError(f"Command exited with status {result.returncode}: {shlex.join(command)}")


def load_plugins(plugin_dir):
    plugins = []
    if not os.path.exists(plugin_dir):
        return plugins
    for name in sorted(os.listdir(plugin_dir)):
        if not name.endswith(".py") or name.startswith("__"):
            continue
        path = os.path.join(plugin_dir, name)
        spec = importlib.util.spec_from_file_location(name[:-3], path)
        if not spec or not spec.loader:
            continue
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception:
            # Silently skip failed loads during discovery
            continue
        if hasattr(module, "run"):
            meta = {
                "id": name[:-3],
                "filename": name,
                "name": getattr(module, "PLUGIN_NAME", name[:-3]),
                "category": getattr(module, "PLUGIN_CATEGORY", "General"),
                "target": getattr(module, "PLUGIN_TARGET", "common"),
                "description": getattr(module, "PLUGIN_DESCRIPTION", ""),
                "default_enabled": bool(getattr(module, "PLUGIN_DEFAULT_ENABLED", True)),
                "source": "python",
                "module": module,
            }
            plugins.append(meta)
    for name in sorted(os.listdir(plugin_dir)):
        if not name.endswith(".json"):
            continue
        path = os.path.join(plugin_dir, name)
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception as exc:
            print(f"Manifest load failed: {name}: {exc}", file=sys.stderr)
            continue
        entries = data.get("plugins", data if isinstance(data, list) else [])
        for entry in entries:
            if not isinstance(entry, dict) or not entry.get("id"):
                continue
            meta = {
                "id": entry["id"],
                "filename": name,
                "name": entry.get("name", entry["id"]),
                "category": entry.get("category", "General"),
                "target": entry.get("target", "common"),
                "description": entry.get("description", ""),
                "default_enabled": bool(entry.get("default_enabled", False)),
                "source": "manifest",
                "manifest": entry,
            }
            plugins.append(meta)
    deduped = {}
    for plugin in plugins:
        deduped[plugin["id"]] = plugin
    plugins = list(deduped.values())
    plugins.sort(key=lambda p: (p.get("target", "common"), p.get("category", ""), p.get("name", "")))
    return plugins


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", help="Forensics output directory")
    parser.add_argument("--plugin-dir", required=True, help="Directory containing plugins")
    parser.add_argument("--context", default="", help="Execution context")
    parser.add_argument("--input-dir", default=os.environ.get("GENESIS_INPUT_DIR", ""), help="Evidence input folder for folder-scoped modules")
    parser.add_argument("--list", action="store_true", help="List available plugins as JSON")
    parser.add_argument("--plugin", help="Execute only this specific plugin (by ID)")
    args = parser.parse_args()

    plugins = load_plugins(args.plugin_dir)

    if args.list:
        # Strip module objects from JSON output
        serializable = []
        for p in plugins:
            d = p.copy()
            d.pop("module", None)
            d.pop("manifest", None)
            serializable.append(d)
        print(json.dumps(serializable, indent=2))
        return 0

    if not args.output_dir:
        print("Error: --output-dir is required for execution")
        return 1

    if not plugins:
        print("No plugins found")
        return 0

    to_run = [p for p in plugins if p.get("default_enabled")]
    if args.plugin:
        to_run = [p for p in plugins if p["id"] == args.plugin]
        if not to_run:
            print(f"Plugin not found: {args.plugin}")
            return 1

    for p in to_run:
        name = p["name"]
        try:
            if p.get("source") == "manifest":
                _manifest_plugin_run(p["manifest"], args.output_dir, args.context, args.input_dir)
            else:
                mod = p["module"]
                mod.run(args.output_dir, args.context)
            print(f"Plugin ok: {name}")
        except Exception as exc:
            print(f"Plugin failed: {name}: {exc}")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

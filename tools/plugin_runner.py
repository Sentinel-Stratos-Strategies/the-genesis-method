#!/usr/bin/env python3
import argparse
import importlib.util
import os
import sys


def load_plugins(plugin_dir):
    plugins = []
    for name in os.listdir(plugin_dir):
        if not name.endswith(".py") or name.startswith("__"):
            continue
        path = os.path.join(plugin_dir, name)
        spec = importlib.util.spec_from_file_location(name[:-3], path)
        if not spec or not spec.loader:
            continue
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception as exc:
            print(f"Plugin load failed: {name}: {exc}")
            continue
        if hasattr(module, "run"):
            plugins.append((name, module))
    return plugins


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--plugin-dir", required=True)
    parser.add_argument("--context", default="")
    args = parser.parse_args()

    plugins = load_plugins(args.plugin_dir)
    if not plugins:
        print("No plugins found")
        return 0

    for name, mod in plugins:
        try:
            mod.run(args.output_dir, args.context)
            print(f"Plugin ok: {name}")
        except Exception as exc:
            print(f"Plugin failed: {name}: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

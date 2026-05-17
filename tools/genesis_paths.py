#!/usr/bin/env python3
"""Shared Genesis evidence path defaults (Stratos input / SENTINEL output — never inside the repo)."""

from __future__ import annotations

import json
import os
from pathlib import Path


DEFAULT_INPUT_ROOT = "/Volumes/Stratos_Tools/GENESIS_EVIDENCE_INPUT/staging"
DEFAULT_OUTPUT_ROOT = "/Volumes/SENTINEL/GENESIS_EVIDENCE_OUTPUT/runs"


def _candidate_memory_contract_roots(repo_root: Path) -> list[Path]:
    env = os.environ.get("MEMORY_CONTRACT_ROOT", "").strip()
    roots = []
    if env:
        roots.append(Path(env))
    roots.extend(
        [
            repo_root.parent / "memory-contract",
            Path("/Volumes/Stratos_Tools/projects/memory-contract"),
            repo_root / "external" / "memory-contract",
            repo_root.parent / "GENESIS_OS-current" / "contracts" / "memory-contract",
            repo_root.parent.parent / "GENESIS_OS-current" / "contracts" / "memory-contract",
            Path("/Volumes/Stratos_Tools/projects/GENESIS_OS-current/contracts/memory-contract"),
        ]
    )
    return roots


def resolve_memory_contract_root(repo_root: Path) -> Path | None:
    for p in _candidate_memory_contract_roots(repo_root):
        if (p / "manifest" / "memory_manifest.yaml").is_file():
            return p.resolve()
    return None


def paths_config_file(repo_root: Path) -> Path:
    return repo_root / "config" / "genesis_paths.json"


def default_paths(repo_root: Path) -> dict:
    mc = resolve_memory_contract_root(repo_root)
    return {
        "evidence_input_root": os.environ.get("GENESIS_DEFAULT_INPUT", DEFAULT_INPUT_ROOT),
        "evidence_output_root": os.environ.get("GENESIS_DEFAULT_OUTPUT", DEFAULT_OUTPUT_ROOT),
        "default_case_name": "",
        "memory_contract_root": str(mc) if mc else "",
    }


def load_paths(repo_root: Path) -> dict:
    cfg = paths_config_file(repo_root)
    base = default_paths(repo_root)
    if cfg.is_file():
        try:
            data = json.loads(cfg.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                base.update({k: v for k, v in data.items() if isinstance(v, str)})
        except Exception:
            pass
    return base


def save_paths(repo_root: Path, data: dict) -> None:
    cfg = paths_config_file(repo_root)
    cfg.parent.mkdir(parents=True, exist_ok=True)
    merged = default_paths(repo_root)
    merged.update({k: str(v) for k, v in data.items() if isinstance(v, str)})
    cfg.write_text(json.dumps(merged, indent=2), encoding="utf-8")

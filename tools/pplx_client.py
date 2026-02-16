#!/usr/bin/env python3
"""
Perplexity / Sonar minimal SDK (stdlib-only).

This module intentionally avoids third-party dependencies so it can run under the
same Python that drives Genesis.

Security notes:
- Reads API keys from environment variables or an optional env file (KEY=value).
- Never prints secrets. Callers should avoid logging request headers.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path


def load_kv_env_file(path: str | Path) -> dict[str, str]:
    p = Path(path)
    if not p.exists():
        return {}
    out: dict[str, str] = {}
    for raw in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k:
            out[k] = v
    return out


def resolve_pplx_api_key(env: dict[str, str] | None = None) -> str | None:
    env = env or {}

    direct = os.environ.get("PPLX_API_KEY") or env.get("PPLX_API_KEY")
    if direct:
        return direct

    active_name = os.environ.get("PPLX_ACTIVE_KEY") or env.get("PPLX_ACTIVE_KEY")
    if active_name:
        active = os.environ.get(active_name) or env.get(active_name)
        if active:
            return active

    for k in ("PPLX_API_KEY_PRIMARY", "PPLX_API_KEY_2", "PPLX_API_KEY_3", "PPLX_API_KEY_4"):
        v = os.environ.get(k) or env.get(k)
        if v:
            return v
    return None


def resolve_base_url(env: dict[str, str] | None = None) -> str:
    env = env or {}
    return (os.environ.get("PPLX_BASE_URL") or env.get("PPLX_BASE_URL") or "https://api.perplexity.ai").rstrip("/")


def resolve_default_model(env: dict[str, str] | None = None) -> str:
    env = env or {}
    return os.environ.get("SONAR_MODEL") or env.get("SONAR_MODEL") or "sonar-pro"


def _http_json(url: str, headers: dict[str, str], payload: dict | None, timeout: int) -> dict:
    data = None
    method = "GET"
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        method = "POST"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="ignore").strip()
        except Exception:
            detail = ""
        raise RuntimeError(f"HTTP {exc.code}: {detail or exc.reason}") from exc


@dataclass
class PplxClient:
    api_key: str
    base_url: str = "https://api.perplexity.ai"
    default_model: str = "sonar-pro"
    timeout: int = 60

    @classmethod
    def from_env(cls, env_file: str | Path | None = None, timeout: int = 60) -> "PplxClient":
        env = load_kv_env_file(env_file) if env_file else {}
        api_key = resolve_pplx_api_key(env)
        if not api_key:
            raise RuntimeError("Missing Perplexity API key. Set PPLX_API_KEY (or PPLX_API_KEY_PRIMARY + PPLX_ACTIVE_KEY).")
        base_url = resolve_base_url(env)
        model = resolve_default_model(env)
        return cls(api_key=api_key, base_url=base_url, default_model=model, timeout=timeout)

    def chat_completions(self, messages: list[dict], model: str | None = None, extra: dict | None = None) -> dict:
        url = f"{self.base_url}/chat/completions"
        payload: dict = {
            "model": model or self.default_model,
            "messages": messages,
        }
        if extra:
            payload.update(extra)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        return _http_json(url, headers=headers, payload=payload, timeout=self.timeout)


def extract_text(resp_json: dict) -> str:
    # Best-effort to support both OpenAI-style and other shapes.
    if not isinstance(resp_json, dict):
        return ""
    choices = resp_json.get("choices")
    if isinstance(choices, list) and choices:
        msg = choices[0].get("message") if isinstance(choices[0], dict) else None
        if isinstance(msg, dict):
            return str(msg.get("content") or "")
    return ""


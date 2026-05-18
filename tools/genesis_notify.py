#!/usr/bin/env python3
"""Genesis Method notifications: macOS banners + email log delivery."""

from __future__ import annotations

import json
import os
import platform
import subprocess
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path


def default_notifications_config() -> dict:
    return {
        "enabled": True,
        "macos_desktop": True,
        "email": {
            "enabled": True,
            "recipients": [
                "joe@ellis-aegis.us",
                "joeellis@student.purdueglobal.edu",
            ],
            "method": "mail",
            "from_address": "",
            "include_log_tail_lines": 120,
            "attach_log_on_failure": True,
        },
        "events": {
            "run_started": True,
            "run_completed": True,
            "run_failed": True,
            "test_ping": True,
        },
    }


def load_notifications_config(path: str | Path) -> dict:
    path = Path(path)
    config = default_notifications_config()
    if not path.exists():
        return config
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            config.update({k: v for k, v in loaded.items() if k != "email" and k != "events"})
            if isinstance(loaded.get("email"), dict):
                config["email"] = {**config["email"], **loaded["email"]}
            if isinstance(loaded.get("events"), dict):
                config["events"] = {**config["events"], **loaded["events"]}
    except Exception as exc:
        config["load_error"] = str(exc)
    return config


def save_notifications_config(path: str | Path, payload: dict) -> dict:
    path = Path(path)
    config = load_notifications_config(path)
    for key in ("enabled", "macos_desktop"):
        if key in payload:
            config[key] = bool(payload[key])
    if isinstance(payload.get("email"), dict):
        email = config.get("email", {})
        if not isinstance(email, dict):
            email = {}
        allowed = {
            "enabled",
            "recipients",
            "method",
            "from_address",
            "include_log_tail_lines",
            "attach_log_on_failure",
            "smtp_host",
            "smtp_port",
            "smtp_user",
            "smtp_password_env",
            "smtp_use_tls",
        }
        for key in allowed:
            if key in payload["email"]:
                email[key] = payload["email"][key]
        if "recipients" in email and isinstance(email["recipients"], str):
            email["recipients"] = [r.strip() for r in email["recipients"].split(",") if r.strip()]
        config["email"] = email
    if isinstance(payload.get("events"), dict):
        events = config.get("events", {})
        if not isinstance(events, dict):
            events = {}
        events.update(payload["events"])
        config["events"] = events
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return config


def _notification_log_path(log_dir: str | Path) -> Path:
    return Path(log_dir) / "notifications.log"


def _append_notification_log(log_dir: str | Path, line: str) -> None:
    path = _notification_log_path(log_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {line}\n")


def tail_log_file(log_path: str | Path, lines: int = 120) -> str:
    log_path = Path(log_path)
    if not log_path.exists():
        return f"(log not found: {log_path})"
    try:
        content = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        return f"(could not read log: {exc})"
    if lines <= 0:
        return "\n".join(content)
    return "\n".join(content[-lines:])


def send_macos_notification(title: str, message: str) -> tuple[bool, str]:
    if platform.system() != "Darwin":
        return False, "macOS notifications unavailable on this platform"
    safe_title = title.replace('"', "'")[:120]
    safe_message = message.replace('"', "'")[:240]
    script = (
        f'display notification "{safe_message}" with title "{safe_title}" '
        'sound name "Glass"'
    )
    try:
        subprocess.run(
            ["/usr/bin/osascript", "-e", script],
            check=True,
            capture_output=True,
            text=True,
            timeout=8,
        )
        return True, "macOS notification sent"
    except Exception as exc:
        return False, f"macOS notification failed: {exc}"


def _write_outbox_eml(outbox_dir: Path, recipients: list[str], subject: str, body: str) -> Path:
    outbox_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    path = outbox_dir / f"genesis_{stamp}.eml"
    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(body, "plain", "utf-8"))
    path.write_bytes(msg.as_bytes())
    return path


def _send_email_mail(recipients: list[str], subject: str, body: str) -> tuple[bool, str]:
    if not recipients:
        return False, "no recipients configured"
    proc = subprocess.run(
        ["/usr/bin/mail", "-s", subject, *recipients],
        input=body,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode == 0:
        return True, f"mail sent to {', '.join(recipients)}"
    return False, (proc.stderr or proc.stdout or f"mail exited {proc.returncode}").strip()


def _send_email_smtp(email_cfg: dict, recipients: list[str], subject: str, body: str) -> tuple[bool, str]:
    import smtplib

    host = (email_cfg.get("smtp_host") or "").strip()
    if not host:
        return False, "smtp_host not configured"
    port = int(email_cfg.get("smtp_port") or 587)
    user = (email_cfg.get("smtp_user") or "").strip()
    password_env = (email_cfg.get("smtp_password_env") or "GENESIS_SMTP_PASSWORD").strip()
    password = os.environ.get(password_env, "")
    use_tls = bool(email_cfg.get("smtp_use_tls", True))
    from_addr = (email_cfg.get("from_address") or user or "genesis@localhost").strip()

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = ", ".join(recipients)

    try:
        if use_tls:
            server = smtplib.SMTP(host, port, timeout=20)
            server.starttls()
        else:
            server = smtplib.SMTP(host, port, timeout=20)
        if user and password:
            server.login(user, password)
        server.sendmail(from_addr, recipients, msg.as_string())
        server.quit()
        return True, f"smtp sent to {', '.join(recipients)}"
    except Exception as exc:
        return False, f"smtp failed: {exc}"


def send_email(
    email_cfg: dict,
    recipients: list[str],
    subject: str,
    body: str,
    outbox_dir: str | Path,
) -> dict:
    results = {"attempts": [], "outbox": None, "ok": False}
    method = (email_cfg.get("method") or "mail").strip().lower()
    if method == "smtp":
        ok, detail = _send_email_smtp(email_cfg, recipients, subject, body)
        results["attempts"].append({"method": "smtp", "ok": ok, "detail": detail})
        results["ok"] = ok
    else:
        ok, detail = _send_email_mail(recipients, subject, body)
        results["attempts"].append({"method": "mail", "ok": ok, "detail": detail})
        results["ok"] = ok

    if not results["ok"]:
        outbox = _write_outbox_eml(Path(outbox_dir), recipients, subject, body)
        results["outbox"] = str(outbox)
        results["attempts"].append(
            {"method": "outbox_eml", "ok": True, "detail": f"saved {outbox}"}
        )
    return results


def notify_event(
    config: dict,
    *,
    event: str,
    title: str,
    message: str,
    log_path: str | Path | None = None,
    log_dir: str | Path | None = None,
    success: bool | None = None,
) -> dict:
    """Dispatch configured notifications for a dashboard event."""
    log_dir = Path(log_dir or Path(log_path).parent if log_path else ".")
    result = {
        "event": event,
        "enabled": bool(config.get("enabled", True)),
        "delivered": [],
        "skipped": [],
        "errors": [],
    }
    if not config.get("enabled", True):
        result["skipped"].append("notifications disabled")
        return result

    events = config.get("events") if isinstance(config.get("events"), dict) else {}
    if events and not events.get(event, True):
        result["skipped"].append(f"event {event} disabled")
        return result

    email_cfg = config.get("email") if isinstance(config.get("email"), dict) else {}
    recipients = [
        r.strip()
        for r in (email_cfg.get("recipients") or [])
        if isinstance(r, str) and r.strip()
    ]
    tail_lines = int(email_cfg.get("include_log_tail_lines") or 120)
    body = message
    if log_path:
        attach_failure_only = bool(email_cfg.get("attach_log_on_failure", True))
        include_log = not attach_failure_only or success is False
        if include_log:
            body = (
                f"{message}\n\n"
                f"--- log tail ({log_path}) ---\n"
                f"{tail_log_file(log_path, tail_lines)}\n"
            )

    if config.get("macos_desktop", True):
        ok, detail = send_macos_notification(title, message)
        (result["delivered"] if ok else result["errors"]).append({"channel": "macos", "detail": detail})

    if email_cfg.get("enabled", True) and recipients:
        subject = f"[Genesis Method] {title}"
        email_result = send_email(
            email_cfg,
            recipients,
            subject,
            body,
            log_dir / "outbox",
        )
        for attempt in email_result.get("attempts", []):
            bucket = result["delivered"] if attempt.get("ok") else result["errors"]
            bucket.append({"channel": f"email:{attempt.get('method')}", "detail": attempt.get("detail")})
        if email_result.get("outbox"):
            result["delivered"].append({"channel": "email:outbox", "detail": email_result["outbox"]})
    elif email_cfg.get("enabled", True):
        result["skipped"].append("email enabled but no recipients")

    summary = (
        f"event={event} delivered={len(result['delivered'])} "
        f"errors={len(result['errors'])} skipped={len(result['skipped'])}"
    )
    _append_notification_log(log_dir, summary)
    return result

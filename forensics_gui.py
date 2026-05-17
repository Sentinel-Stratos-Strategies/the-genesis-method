#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog

ROOT = str(Path(__file__).resolve().parent)
ROOT_PATH = Path(ROOT)
PROJECT_NAME = ROOT_PATH.name

sys.path.insert(0, os.path.join(ROOT, "tools"))
from genesis_paths import load_paths, save_paths  # noqa: E402

_PATHS = load_paths(ROOT_PATH)
_DEFAULT_OUT_ROOT = _PATHS["evidence_output_root"]

LAUNCHER = os.path.join(ROOT, "run_forensics.sh")
LAST_RUN_FILE = os.path.join(ROOT, "last_enterprise_output.txt")
LOG_SUBDIR = "_logs"
GUI_LOG_FILE = os.path.join(_DEFAULT_OUT_ROOT, LOG_SUBDIR, "gui_actions.log")
LOGO_PNG = os.path.join(ROOT, "assets", "genesis-logo.png")
if not os.path.isfile(LOGO_PNG):
    LOGO_PNG = os.path.join(ROOT, "assets", "sentinel-logo.png")
PLUGIN_RUNNER = os.path.join(ROOT, "tools", "plugin_runner.py")
PLUGIN_DIR = os.path.join(ROOT, "plugins")


def list_plugins():
    try:
        res = subprocess.run(
            [sys.executable, PLUGIN_RUNNER, "--plugin-dir", PLUGIN_DIR, "--list"],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(res.stdout)
    except Exception:
        return []


BG = "#070312"
CARD = "#120723"
PANEL = "#0d051c"
TEXT = "#ffffff"
MUTED = "#d7efff"
ACCENT = "#1FC2D6"
ACCENT2 = "#F57442"
ACCENT3 = "#751E99"
BORDER = "#7f3ebd"
BTN_DARK = "#16092d"
BTN_GLOW = "#2f1038"
BTN_WARN = "#3a1223"

BTN_ORANGE_BG = "#2b1308"
BTN_ORANGE_BORDER = "#ff7b3f"
BTN_MAGENTA_BG = "#2a0d30"
BTN_MAGENTA_BORDER = "#d458ff"
BTN_CYAN_BG = "#0a2530"
BTN_CYAN_BORDER = "#33d8f0"

FONT_TITLE = ("Avenir Next", 24, "bold")
FONT_SUBTITLE = ("Avenir Next", 12, "bold")
FONT_STATUS = ("Avenir Next", 11, "bold")
FONT_SECTION = ("Avenir Next", 13, "bold")
FONT_BUTTON = ("Avenir Next", 10, "bold")
FONT_BODY = ("Avenir Next", 10)


class NeonButton(tk.Frame):
    def __init__(
        self,
        parent,
        text,
        command,
        fill,
        border,
        hover,
        font=FONT_BUTTON,
        wraplength=170,
        padx=10,
        pady=10,
    ):
        super().__init__(parent, bg=border, bd=0, highlightthickness=0)
        self._command = command
        self._fill = fill
        self._hover = hover

        self.label = tk.Label(
            self,
            text=text,
            bg=fill,
            fg=TEXT,
            font=font,
            wraplength=wraplength,
            justify="center",
            cursor="hand2",
            bd=0,
            padx=padx,
            pady=pady,
        )
        self.label.pack(fill="both", expand=True, padx=2, pady=2)

        for w in (self, self.label):
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)
            w.bind("<Button-1>", self._on_click)

    def _on_enter(self, _event):
        self.label.configure(bg=self._hover)

    def _on_leave(self, _event):
        self.label.configure(bg=self._fill)

    def _on_click(self, _event):
        if callable(self._command):
            self._command()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("The Genesis Method — Enterprise Control Center")
        self.geometry("1280x920")
        self.minsize(1100, 800)
        self.configure(bg=BG)

        paths = load_paths(ROOT_PATH)
        self.enterprise_input = tk.StringVar(value=paths["evidence_input_root"])
        self.enterprise_output_root = tk.StringVar(value=paths["evidence_output_root"])
        dc = paths.get("default_case_name") or ""
        self.enterprise_case = tk.StringVar(value=dc or f"case_{time.strftime('%Y%m%d_%H%M%S')}")

        self.output_hint = tk.StringVar(
            value=f"Evidence INPUT (Stratos area): {self.enterprise_input.get()} | OUTPUT root (SENTINEL): {self.enterprise_output_root.get()}"
        )
        self.last_run = tk.StringVar(value="Last enterprise run folder: (none)")
        self.status = tk.StringVar(value="Ready.")
        self._refresh_gui_log_path()
        self._load_last_run()

        self._build_ui()

    def _refresh_gui_log_path(self):
        global GUI_LOG_FILE
        root_out = self.enterprise_output_root.get().strip() or _DEFAULT_OUT_ROOT
        GUI_LOG_FILE = os.path.join(root_out, LOG_SUBDIR, "gui_actions.log")

    def _save_paths_config(self):
        save_paths(
            ROOT_PATH,
            {
                "evidence_input_root": self.enterprise_input.get().strip(),
                "evidence_output_root": self.enterprise_output_root.get().strip(),
                "default_case_name": self.enterprise_case.get().strip(),
            },
        )
        self.output_hint.set(
            f"Evidence INPUT: {self.enterprise_input.get()} | OUTPUT root: {self.enterprise_output_root.get()} (saved)"
        )
        self._refresh_gui_log_path()

    def _build_ui(self):
        header = tk.Frame(self, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        header.pack(pady=10, padx=14, fill="x")

        logo_frame = tk.Frame(header, bg=CARD)
        logo_frame.pack(side="left", padx=12, pady=12)
        self.logo_img = None
        if os.path.exists(LOGO_PNG):
            try:
                self.logo_img = tk.PhotoImage(file=LOGO_PNG)
                tk.Label(logo_frame, image=self.logo_img, bg=CARD).pack()
            except tk.TclError:
                tk.Label(logo_frame, text="S", font=("Avenir Next", 28, "bold"), bg=CARD, fg=ACCENT).pack()
        else:
            tk.Label(logo_frame, text="S", font=("Avenir Next", 28, "bold"), bg=CARD, fg=ACCENT).pack()

        title_frame = tk.Frame(header, bg=CARD)
        title_frame.pack(side="left", padx=8)
        tk.Label(title_frame, text="THE GENESIS METHOD", font=FONT_TITLE, bg=CARD, fg=ACCENT2).pack(anchor="w")
        tk.Label(
            title_frame,
            text="Enterprise Evidence Console — Sentinel Stratos Strategies",
            font=FONT_SUBTITLE,
            bg=CARD,
            fg=MUTED,
        ).pack(anchor="w")
        tk.Label(title_frame, textvariable=self.status, font=FONT_STATUS, bg=CARD, fg=ACCENT).pack(anchor="w", pady=(6, 0))

        paths_panel = tk.Frame(self, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        paths_panel.pack(fill="x", padx=14, pady=(0, 8))
        tk.Label(paths_panel, text="Evidence paths (keep case data out of the repo)", font=FONT_SECTION, bg=PANEL, fg=TEXT).pack(
            anchor="w", padx=10, pady=(10, 6)
        )
        self._input_row(paths_panel, "INPUT folder:", self.enterprise_input, self._browse_input)
        self._input_row(paths_panel, "OUTPUT root:", self.enterprise_output_root, self._browse_output_root)
        self._input_row(paths_panel, "Case subfolder:", self.enterprise_case, None)

        row_btns = tk.Frame(paths_panel, bg=PANEL)
        row_btns.pack(fill="x", padx=8, pady=(4, 12))
        NeonButton(
            row_btns,
            text="Save paths",
            command=self._save_paths_config,
            fill=BTN_DARK,
            border=BORDER,
            hover=BTN_GLOW,
            font=FONT_BUTTON,
            wraplength=120,
            padx=12,
            pady=8,
        ).pack(side="left", padx=4)

        content = tk.Frame(self, bg=BG)
        content.pack(fill="both", expand=True, padx=14)

        self._build_modules_section(content)

        footer = tk.Frame(self, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        footer.pack(fill="x", padx=14, pady=(10, 12))

        tk.Label(footer, textvariable=self.output_hint, bg=PANEL, fg=MUTED, font=FONT_SUBTITLE).pack(anchor="w", padx=10, pady=(8, 2))
        tk.Label(footer, textvariable=self.last_run, bg=PANEL, fg=TEXT, font=FONT_BODY).pack(anchor="w", padx=10, pady=(0, 6))

        common = tk.Frame(footer, bg=PANEL)
        common.pack(fill="x", padx=8, pady=(0, 10))
        NeonButton(
            common,
            text="Start Web UI",
            command=lambda: self._run_choice("90"),
            fill=BTN_GLOW,
            border=BORDER,
            hover=ACCENT3,
            font=FONT_BUTTON,
            wraplength=140,
            padx=14,
            pady=8,
        ).pack(side="left", padx=6)
        NeonButton(
            common,
            text="Timesketch",
            command=lambda: self._run_choice("92"),
            fill=BTN_GLOW,
            border=BORDER,
            hover=ACCENT3,
            font=FONT_BUTTON,
            wraplength=120,
            padx=14,
            pady=8,
        ).pack(side="left", padx=6)
        NeonButton(
            common,
            text="Terminal TUI",
            command=self._spawn_tui,
            fill=BTN_DARK,
            border=BORDER,
            hover=BTN_GLOW,
            font=FONT_BUTTON,
            wraplength=120,
            padx=14,
            pady=8,
        ).pack(side="left", padx=6)
        NeonButton(
            common,
            text="Refresh status",
            command=self._load_last_run,
            fill=BTN_DARK,
            border=BORDER,
            hover=BTN_GLOW,
            font=FONT_BUTTON,
            wraplength=120,
            padx=14,
            pady=8,
        ).pack(side="left", padx=6)

    def _spawn_tui(self):
        subprocess.Popen([sys.executable, os.path.join(ROOT, "tools", "genesis_tui.py")], cwd=ROOT)

    def _build_modules_section(self, parent):
        plugins = list_plugins()
        if not plugins:
            tk.Label(parent, text="No plugins discovered.", bg=BG, fg=MUTED, font=FONT_BODY).pack(pady=20)
            return

        inner = tk.Frame(parent, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        inner.pack(fill="both", expand=True)

        tk.Label(inner, text="Manifest + Python modules", font=FONT_SECTION, bg=PANEL, fg=TEXT).pack(anchor="w", padx=10, pady=(10, 8))

        canvas = tk.Canvas(inner, bg=PANEL, highlightthickness=0)
        scrollbar = tk.Scrollbar(inner, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=PANEL)

        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=5)
        scrollbar.pack(side="right", fill="y")

        for idx, p in enumerate(plugins):
            p_id = p["id"]
            p_name = p["name"]
            p_cat = p["category"]
            p_target = p.get("target", "common")

            btn_text = f"[{p_cat}] {p_name} ({p_target})"
            row = idx // 2
            col = idx % 2

            fill, border, hover = self._button_style("plugin", idx)
            NeonButton(
                scrollable_frame,
                text=btn_text,
                command=lambda pid=p_id: self._run_plugin(pid),
                fill=fill,
                border=border,
                hover=hover,
                font=FONT_BUTTON,
                wraplength=220,
                padx=10,
                pady=10,
            ).grid(row=row, column=col, sticky="nsew", padx=5, pady=5)

    def _run_plugin(self, plugin_id):
        self.status.set(f"Running module {plugin_id}...")
        thread = threading.Thread(target=self._run_plugin_bg, args=(plugin_id,), daemon=True)
        thread.start()

    def _enterprise_output_dir(self):
        base = self.enterprise_output_root.get().strip() or _DEFAULT_OUT_ROOT
        case = self.enterprise_case.get().strip() or f"case_{time.strftime('%Y%m%d_%H%M%S')}"
        target_dir = os.path.join(base, case)
        os.makedirs(target_dir, exist_ok=True)
        return target_dir

    def _run_plugin_bg(self, plugin_id):
        plugins = list_plugins()
        plugin = next((p for p in plugins if p["id"] == plugin_id), None)
        if not plugin:
            self.after(0, lambda: self.status.set(f"Error: Plugin {plugin_id} not found."))
            return

        target_dir = self._enterprise_output_dir()
        input_dir = self.enterprise_input.get().strip()
        self._refresh_gui_log_path()
        os.makedirs(os.path.dirname(GUI_LOG_FILE), exist_ok=True)

        env = os.environ.copy()
        env.setdefault("GENESIS_INPUT_DIR", input_dir)

        cmd = [
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
        ]

        with open(GUI_LOG_FILE, "a", encoding="utf-8") as log:
            log.write(f"\n=== Plugin {plugin_id} ===\n")
            log.write(f"cmd: {' '.join(cmd)}\n")
            proc = subprocess.run(cmd, cwd=ROOT, env=env, stdout=log, stderr=log, text=True)
            rc = proc.returncode

        Path(LAST_RUN_FILE).write_text(target_dir + "\n", encoding="utf-8")
        self.after(0, lambda: self._on_plugin_done(plugin_id, rc))

    def _on_plugin_done(self, plugin_id, rc):
        if rc == 0:
            self.status.set(f"Completed module {plugin_id}. Output: {self._enterprise_output_dir()}")
        else:
            self.status.set(f"Module {plugin_id} failed (code {rc}). Log: {GUI_LOG_FILE}")
        self._load_last_run()

    def _input_row(self, parent, label_text, var, browse_cb):
        row = tk.Frame(parent, bg=PANEL)
        row.pack(fill="x", pady=3)
        tk.Label(row, text=label_text, bg=PANEL, fg=TEXT, font=FONT_SUBTITLE, width=18, anchor="w").pack(side="left")
        tk.Entry(
            row,
            textvariable=var,
            width=86,
            bg="#090414",
            fg=TEXT,
            insertbackground=TEXT,
            highlightbackground=BORDER,
            highlightthickness=2,
            bd=0,
        ).pack(side="left", padx=6)
        if browse_cb:
            NeonButton(
                row,
                text="Browse",
                command=browse_cb,
                fill=BTN_DARK,
                border=BORDER,
                hover=BTN_GLOW,
                font=FONT_BUTTON,
                wraplength=80,
                padx=12,
                pady=6,
            ).pack(side="left")

    def _browse_input(self):
        path = filedialog.askdirectory()
        if path:
            self.enterprise_input.set(path)

    def _browse_output_root(self):
        path = filedialog.askdirectory()
        if path:
            self.enterprise_output_root.set(path)
            self._refresh_gui_log_path()

    def _button_style(self, choice, idx):
        if choice in {"11", "31"}:
            return BTN_WARN, "#ff5a7d", "#a32952"
        if choice in {"12", "20", "32", "40"}:
            return BTN_GLOW, "#ff9f44", "#f57442"
        if idx % 3 == 0:
            return BTN_ORANGE_BG, BTN_ORANGE_BORDER, "#f57442"
        if idx % 3 == 1:
            return BTN_MAGENTA_BG, BTN_MAGENTA_BORDER, "#a73dd6"
        return BTN_CYAN_BG, BTN_CYAN_BORDER, "#1fc2d6"

    def _load_last_run(self):
        if Path(LAST_RUN_FILE).exists():
            self.last_run.set(f"Last enterprise run folder: {Path(LAST_RUN_FILE).read_text(encoding='utf-8').strip()}")
        else:
            self.last_run.set("Last enterprise run folder: (none)")

    def _run_choice(self, choice):
        self.status.set(f"Running option {choice}...")
        thread = threading.Thread(target=self._run_choice_bg, args=(choice,), daemon=True)
        thread.start()

    def _run_choice_bg(self, choice):
        self._refresh_gui_log_path()
        os.makedirs(os.path.dirname(GUI_LOG_FILE), exist_ok=True)
        env = os.environ.copy()
        cmd = [LAUNCHER, "--choice", str(choice)]
        with open(GUI_LOG_FILE, "a", encoding="utf-8") as log:
            log.write(f"\n=== Option {choice} ===\n")
            if str(choice) in {"90", "91", "92"}:
                subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=log, stderr=log, text=True)
                rc = 0
            else:
                proc = subprocess.run(cmd, cwd=ROOT, env=env, stdout=log, stderr=log, text=True)
                rc = proc.returncode
        self.after(0, lambda: self._on_choice_done(choice, rc))

    def _on_choice_done(self, choice, rc):
        if rc == 0:
            self.status.set(f"Completed option {choice}.")
        else:
            self.status.set(f"Option {choice} failed (code {rc}). Log: {GUI_LOG_FILE}")


if __name__ == "__main__":
    app = App()
    app.mainloop()

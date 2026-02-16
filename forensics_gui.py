#!/usr/bin/env python3
import os
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog


ROOT = str(Path(__file__).resolve().parent)
PROJECT_NAME = Path(ROOT).name


def detect_fam_root() -> str:
    env_root = os.environ.get("GENESIS_FAM_ROOT")
    if env_root:
        return env_root
    tools_path = Path(f"/Users/fam/Tools/{PROJECT_NAME}")
    user_path = Path(f"/Users/fam/{PROJECT_NAME}")
    if tools_path.exists():
        return str(tools_path)
    if user_path.exists():
        return str(user_path)
    return "/Users/fam"


def migrate_old_root_path(path_in: str) -> str:
    if path_in.startswith("/Users/house/Tools/hunting"):
        return path_in.replace("/Users/house/Tools/hunting", ROOT, 1)
    return path_in


FAM_ROOT = detect_fam_root()
HOUSE_OUT_BASE = os.environ.get("OUT_DIR_HOUSE", "/Users/House/EVIDENCE")
FAM_OUT_BASE = os.environ.get("OUT_DIR_FAM", os.path.join(FAM_ROOT, "forensics_out"))
LAUNCHER = os.path.join(ROOT, "run_forensics.sh")
HOUSE_INPUT_FILE = os.path.join(ROOT, "inputs", "house_path.txt")
FAM_INPUT_FILE = os.path.join(ROOT, "inputs", "fam_path.txt")
LAST_HOUSE_FILE = os.path.join(ROOT, "last_output_house.txt")
LAST_FAM_FILE = os.path.join(ROOT, "last_output_fam.txt")
GUI_LOG_FILE = os.path.join(HOUSE_OUT_BASE, "_logs", "gui_actions.log")
LOGO_PNG = os.path.join(ROOT, "assets", "sentinel-logo.png")

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
        self.title("The Genesis Method - Control Center")
        self.geometry("1260x900")
        self.minsize(1160, 860)
        self.configure(bg=BG)

        self.house_input = tk.StringVar(value=os.path.join(ROOT, "inputs", "house"))
        if Path(HOUSE_INPUT_FILE).exists():
            self.house_input.set(migrate_old_root_path(Path(HOUSE_INPUT_FILE).read_text(encoding="utf-8").strip()))
        self.fam_input = tk.StringVar(value=os.path.join(ROOT, "inputs", "fam"))
        if Path(FAM_INPUT_FILE).exists():
            self.fam_input.set(migrate_old_root_path(Path(FAM_INPUT_FILE).read_text(encoding="utf-8").strip()))

        self.output_hint = tk.StringVar(
            value=f"Output base (house): {HOUSE_OUT_BASE} | Output base (fam): {FAM_OUT_BASE}"
        )
        self.last_house = tk.StringVar(value="Last output (house): (none)")
        self.last_fam = tk.StringVar(value="Last output (fam): (none)")
        self.status = tk.StringVar(value="Ready.")
        self._load_last_outputs()

        self._build_ui()

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
            text="Truth and Trust at Its Core | Sentinel Stratos Strategies",
            font=FONT_SUBTITLE,
            bg=CARD,
            fg=MUTED,
        ).pack(anchor="w")
        tk.Label(title_frame, textvariable=self.status, font=FONT_STATUS, bg=CARD, fg=ACCENT).pack(anchor="w", pady=(6, 0))

        content = tk.Frame(self, bg=BG)
        content.pack(fill="both", expand=True, padx=14)

        left = tk.Frame(content, bg=BG)
        right = tk.Frame(content, bg=BG)
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))
        right.pack(side="left", fill="both", expand=True, padx=(8, 0))

        self._build_column(
            left,
            "House Section",
            [
                ("1", "House Core"), ("2", "House Comms"), ("3", "House Security"),
                ("4", "House iLEAPP"), ("5", "House xLEAPP"), ("10", "House Full Run"),
                ("12", "House Full + Report"), ("13", "House Build Report"), ("14", "House Merge Timeline"),
                ("15", "House YARA"), ("16", "House Sigma"), ("17", "House ClamAV Quick"),
                ("18", "House ClamAV Full"), ("19", "House Plaso"), ("20", "House Genesis Analyst"),
                ("6", "Open House iLEAPP"), ("7", "Open House mac_apt"), ("8", "Export House iLEAPP TL"),
                ("9", "Export House mac_apt TL"), ("11", "Purge House"),
            ],
        )

        self._build_column(
            right,
            "Fam Section",
            [
                ("21", "Fam Core"), ("22", "Fam Comms"), ("23", "Fam Security"),
                ("24", "Fam iLEAPP"), ("25", "Fam xLEAPP"), ("30", "Fam Full Run"),
                ("32", "Fam Full + Report"), ("33", "Fam Build Report"), ("34", "Fam Merge Timeline"),
                ("35", "Fam YARA"), ("36", "Fam Sigma"), ("37", "Fam ClamAV Quick"),
                ("38", "Fam ClamAV Full"), ("39", "Fam Plaso"), ("40", "Fam Genesis Analyst"),
                ("26", "Open Fam iLEAPP"), ("27", "Open Fam mac_apt"), ("28", "Export Fam iLEAPP TL"),
                ("29", "Export Fam mac_apt TL"), ("31", "Purge Fam"),
            ],
        )

        footer = tk.Frame(self, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        footer.pack(fill="x", padx=14, pady=(10, 12))

        tk.Label(footer, textvariable=self.output_hint, bg=PANEL, fg=MUTED, font=FONT_SUBTITLE).pack(
            anchor="w", padx=10, pady=(8, 2)
        )
        tk.Label(footer, textvariable=self.last_house, bg=PANEL, fg=TEXT, font=FONT_BODY).pack(anchor="w", padx=10)
        tk.Label(footer, textvariable=self.last_fam, bg=PANEL, fg=TEXT, font=FONT_BODY).pack(anchor="w", padx=10, pady=(0, 6))

        input_frame = tk.Frame(footer, bg=PANEL)
        input_frame.pack(fill="x", padx=8, pady=(2, 10))
        self._input_row(input_frame, "House iOS input:", self.house_input, self._browse_house)
        self._input_row(input_frame, "Fam iOS input:", self.fam_input, self._browse_fam)

        common = tk.Frame(footer, bg=PANEL)
        common.pack(fill="x", padx=8, pady=(0, 10))
        self._common_button(common, "Genesis Analyst Combined", "93")
        self._common_button(common, "Start Web UI", "90")
        self._common_button(common, "Start Timesketch", "92")
        NeonButton(
            common,
            text="Refresh Last Outputs",
            command=self._load_last_outputs,
            fill=BTN_DARK,
            border=BORDER,
            hover=BTN_GLOW,
            font=FONT_BUTTON,
            wraplength=180,
            padx=14,
            pady=8,
        ).pack(side="left", padx=6)

    def _build_column(self, parent, title, actions):
        panel = tk.Frame(parent, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        panel.pack(fill="both", expand=True)
        tk.Label(panel, text=title, font=FONT_SECTION, bg=PANEL, fg=TEXT).pack(anchor="w", padx=10, pady=(10, 8))

        grid = tk.Frame(panel, bg=PANEL)
        grid.pack(fill="both", expand=True, padx=8, pady=(0, 10))
        for col in range(3):
            grid.grid_columnconfigure(col, weight=1)

        for idx, (choice, text) in enumerate(actions):
            row = idx // 3
            col = idx % 3
            fill, border, hover = self._button_style(choice, idx)
            NeonButton(
                grid,
                text=text,
                command=lambda c=choice: self._run_choice(c),
                fill=fill,
                border=border,
                hover=hover,
                font=FONT_BUTTON,
                wraplength=170,
                padx=10,
                pady=10,
            ).grid(row=row, column=col, sticky="nsew", padx=5, pady=5)

    def _common_button(self, parent, label, choice):
        NeonButton(
            parent,
            text=label,
            command=lambda c=choice: self._run_choice(c),
            fill=BTN_GLOW,
            border=BORDER,
            hover=ACCENT3,
            font=FONT_BUTTON,
            wraplength=180,
            padx=14,
            pady=8,
        ).pack(side="left", padx=6)

    def _input_row(self, parent, label_text, var, browse_cb):
        row = tk.Frame(parent, bg=PANEL)
        row.pack(fill="x", pady=3)
        tk.Label(row, text=label_text, bg=PANEL, fg=TEXT, font=FONT_SUBTITLE, width=16, anchor="w").pack(side="left")
        tk.Entry(
            row,
            textvariable=var,
            width=80,
            bg="#090414",
            fg=TEXT,
            insertbackground=TEXT,
            highlightbackground=BORDER,
            highlightthickness=2,
            bd=0,
        ).pack(side="left", padx=6)
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

    def _write_input_file(self, path, target_file):
        os.makedirs(os.path.dirname(target_file), exist_ok=True)
        with open(target_file, "w", encoding="utf-8") as f:
            f.write(path)

    def _browse_house(self):
        path = filedialog.askdirectory()
        if path:
            self.house_input.set(path)
            self._write_input_file(path, HOUSE_INPUT_FILE)

    def _browse_fam(self):
        path = filedialog.askdirectory()
        if path:
            self.fam_input.set(path)
            self._write_input_file(path, FAM_INPUT_FILE)

    def _load_last_outputs(self):
        if Path(LAST_HOUSE_FILE).exists():
            self.last_house.set(f"Last output (house): {Path(LAST_HOUSE_FILE).read_text(encoding='utf-8').strip()}")
        else:
            self.last_house.set("Last output (house): (none)")
        if Path(LAST_FAM_FILE).exists():
            self.last_fam.set(f"Last output (fam): {Path(LAST_FAM_FILE).read_text(encoding='utf-8').strip()}")
        else:
            self.last_fam.set("Last output (fam): (none)")

    def _run_choice(self, choice):
        self.status.set(f"Running option {choice}...")
        thread = threading.Thread(target=self._run_choice_bg, args=(choice,), daemon=True)
        thread.start()

    def _run_choice_bg(self, choice):
        os.makedirs(os.path.dirname(GUI_LOG_FILE), exist_ok=True)
        env = os.environ.copy()
        env["GENESIS_FAM_ROOT"] = FAM_ROOT
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
            self.status.set(f"Option {choice} failed (code {rc}). See gui_actions.log.")
        self._load_last_outputs()


if __name__ == "__main__":
    app = App()
    app.mainloop()

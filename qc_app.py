"""
qc_app.py
=========
Achira Beta Cartridge QC — Desktop GUI
DWG: ACMCTA001  |  Material: PMMA  |  Microscope: 5X, stitched PNG

Run:
    py qc_app.py
or double-click run_qc_app.bat
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import queue
import os
import csv
import sys
import io
import json
import subprocess
import contextlib
from pathlib import Path
from datetime import datetime


# ── stdout capture: forwards print() from detect modules → GUI log ────────────
class _QueueStream(io.TextIOBase):
    """Write-only stream that forwards lines to a queue as ("log", msg, tag) tuples."""
    def __init__(self, q: queue.Queue, tag: str = "dim"):
        self._q   = q
        self._tag = tag
        self._buf = ""

    def write(self, s: str) -> int:
        self._buf += s
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            if line.strip():
                self._q.put(("log", line, self._tag))
        return len(s)

    def flush(self):
        if self._buf.strip():
            self._q.put(("log", self._buf, self._tag))
            self._buf = ""

# ── Lazy-import QC modules so the window opens instantly ─────────────────────
_detect_mod    = None
_calibrate_mod = None

def _load_qc_modules():
    global _detect_mod, _calibrate_mod
    if _detect_mod is None:
        sys.path.insert(0, str(Path(__file__).parent))
        import detect_features as _d
        import calibrate as _c
        _detect_mod    = _d
        _calibrate_mod = _c


# ── Colour palette (dark theme) ───────────────────────────────────────────────
BG       = "#1e1e2e"
BG_PANEL = "#2a2a3e"
BG_INPUT = "#313145"
FG       = "#cdd6f4"
FG_DIM   = "#7f849c"
ACCENT   = "#89b4fa"
GREEN    = "#a6e3a1"
RED      = "#f38ba8"
YELLOW   = "#f9e2af"
ORANGE   = "#fab387"


# ═════════════════════════════════════════════════════════════════════════════
class QCApp(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("Achira Beta Cartridge QC — ACMCTA001")
        self.configure(bg=BG)
        self.resizable(True, True)
        self.minsize(960, 860)
        self.geometry("1140x980")

        # ── State variables ───────────────────────────────────────────────────
        self.batch_folder  = tk.StringVar()
        self.cal_file      = tk.StringVar(value="calibration.json")
        self.do_holes      = tk.BooleanVar(value=True)
        self.do_neck       = tk.BooleanVar(value=True)
        self.do_dab        = tk.BooleanVar(value=False)
        self.do_mixing     = tk.BooleanVar(value=False)
        self.save_images   = tk.BooleanVar(value=True)
        self.save_csv_var  = tk.BooleanVar(value=True)

        # Calibration state
        self.cal_ref_path  = tk.StringVar()
        self.cal_img_type  = tk.StringVar(value="holes")
        self.cal_n_meas    = tk.IntVar(value=1)

        self._q           = queue.Queue()
        self._running     = False
        self._results     = []
        self._cal_running = False

        self._build_ui()
        self._poll_queue()

    # ─────────────────────────────────────────────────────────────────────────
    # UI construction
    # ─────────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        # Accent stripe at top
        tk.Frame(self, bg=ACCENT, height=4).pack(fill="x")

        # Title
        tf = tk.Frame(self, bg=BG, pady=10)
        tf.pack(fill="x", padx=20)
        tk.Label(tf, text="Achira Beta Cartridge QC",
                 font=("Segoe UI", 17, "bold"), bg=BG, fg=ACCENT).pack(side="left")
        tk.Label(tf, text="   DWG ACMCTA001  ·  5X stitched PNG",
                 font=("Segoe UI", 10), bg=BG, fg=FG_DIM).pack(side="left", pady=5)

        # ── Input section ─────────────────────────────────────────────────────
        inp = self._panel("  Input  ")
        inp.pack(fill="x", padx=20, pady=(0, 6))

        self._browse_row(inp, "Batch folder:",      self.batch_folder, self._browse_folder, 0)
        self._browse_row(inp, "Calibration file:",  self.cal_file,     self._browse_cal,    1)
        inp.columnconfigure(1, weight=1)

        # ── Image types ───────────────────────────────────────────────────────
        typ = self._panel("  Image types  ")
        typ.pack(fill="x", padx=20, pady=(0, 6))

        for col, (lbl, var, desc) in enumerate([
            ("Holes",  self.do_holes,  "Ø0.50 mm × 12"),
            ("Neck",   self.do_neck,   "0.20 mm channel"),
            ("DAB",    self.do_dab,    "pending"),
            ("Mixing", self.do_mixing, "pending"),
        ]):
            f = tk.Frame(typ, bg=BG_PANEL)
            f.grid(row=0, column=col, padx=16, pady=6, sticky="w")
            tk.Checkbutton(f, text=lbl, variable=var,
                           font=("Segoe UI", 12, "bold"),
                           bg=BG_PANEL, fg=FG,
                           selectcolor=BG_INPUT,
                           activebackground=BG_PANEL,
                           activeforeground=FG).pack(anchor="w")
            tk.Label(f, text=desc, font=("Segoe UI", 8),
                     bg=BG_PANEL, fg=FG_DIM).pack(anchor="w")

        # Options row
        opt_f = tk.Frame(typ, bg=BG_PANEL)
        opt_f.grid(row=1, column=0, columnspan=4, sticky="w", padx=8, pady=(4, 6))
        for lbl, var in [("Save annotated images", self.save_images),
                         ("Auto-save CSV report",  self.save_csv_var)]:
            tk.Checkbutton(opt_f, text=lbl, variable=var,
                           font=("Segoe UI", 9), bg=BG_PANEL, fg=FG_DIM,
                           selectcolor=BG_INPUT,
                           activebackground=BG_PANEL).pack(side="left", padx=12)

        # ── Calibration panel ─────────────────────────────────────────────────
        self._build_calibrate_panel()

        # ── Run / Stop / Progress ─────────────────────────────────────────────
        run_f = tk.Frame(self, bg=BG)
        run_f.pack(fill="x", padx=20, pady=(2, 8))

        self._run_btn = tk.Button(run_f, text="▶   Run QC",
                                  font=("Segoe UI", 13, "bold"),
                                  bg=ACCENT, fg=BG, relief="flat",
                                  padx=30, pady=9,
                                  cursor="hand2",
                                  command=self._run)
        self._run_btn.pack(side="left")

        self._stop_btn = tk.Button(run_f, text="■  Stop",
                                   font=("Segoe UI", 11),
                                   bg=BG_PANEL, fg=RED, relief="flat",
                                   padx=14, pady=9,
                                   cursor="hand2",
                                   command=self._stop,
                                   state="disabled")
        self._stop_btn.pack(side="left", padx=8)

        self._status_lbl = tk.Label(run_f, text="Ready",
                                    font=("Segoe UI", 10),
                                    bg=BG, fg=FG_DIM)
        self._status_lbl.pack(side="left", padx=12)

        self._progress = ttk.Progressbar(run_f, length=220, mode="determinate")
        self._progress.pack(side="right")

        # ── Results table ──────────────────────────────────────────────────────
        res_outer = self._panel("  Results  ")
        res_outer.pack(fill="both", expand=True, padx=20, pady=(0, 6))

        cols = ("Cartridge", "Holes", "Neck", "DAB", "Mixing", "Overall", "Details")
        self._tree = ttk.Treeview(res_outer, columns=cols, show="headings", height=9)

        sty = ttk.Style()
        sty.theme_use("clam")
        sty.configure("Treeview",
                       background=BG_INPUT, fieldbackground=BG_INPUT,
                       foreground=FG, rowheight=28,
                       font=("Segoe UI", 10))
        sty.configure("Treeview.Heading",
                       background=BG_PANEL, foreground=ACCENT,
                       font=("Segoe UI", 10, "bold"),
                       relief="flat")
        sty.map("Treeview", background=[("selected", "#45475a")])

        col_widths = {"Cartridge": 90, "Holes": 85, "Neck": 85,
                      "DAB": 85, "Mixing": 85, "Overall": 90, "Details": 380}
        for c in cols:
            self._tree.heading(c, text=c)
            anchor = "center" if c != "Details" else "w"
            self._tree.column(c, width=col_widths[c], anchor=anchor, minwidth=60)

        self._tree.tag_configure("pass",    foreground=GREEN)
        self._tree.tag_configure("fail",    foreground=RED)
        self._tree.tag_configure("pending", foreground=YELLOW)
        self._tree.tag_configure("error",   foreground=ORANGE)

        vsb = ttk.Scrollbar(res_outer, orient="vertical",
                             command=self._tree.yview)
        hsb = ttk.Scrollbar(res_outer, orient="horizontal",
                             command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set,
                              xscrollcommand=hsb.set)
        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        self._tree.pack(fill="both", expand=True)

        # Export button under table
        exp_f = tk.Frame(self, bg=BG)
        exp_f.pack(fill="x", padx=20, pady=(0, 4))
        tk.Button(exp_f, text="💾  Export CSV",
                  font=("Segoe UI", 9), bg=BG_PANEL, fg=ACCENT,
                  relief="flat", padx=12, pady=5,
                  cursor="hand2",
                  command=self._export_csv).pack(side="right")
        tk.Button(exp_f, text="🗑  Clear",
                  font=("Segoe UI", 9), bg=BG_PANEL, fg=FG_DIM,
                  relief="flat", padx=12, pady=5,
                  cursor="hand2",
                  command=self._clear).pack(side="right", padx=6)

        # ── Log ───────────────────────────────────────────────────────────────
        log_outer = self._panel("  Log  ")
        log_outer.pack(fill="x", padx=20, pady=(0, 14))

        self._log = scrolledtext.ScrolledText(
            log_outer, height=7,
            font=("Consolas", 9),
            bg="#11111b", fg=FG,
            insertbackground=FG,
            state="disabled", bd=0, wrap="word")
        self._log.pack(fill="both", padx=4, pady=4)

        for tag, color in [("pass", GREEN), ("fail", RED),
                            ("warn", YELLOW), ("section", ACCENT),
                            ("dim", FG_DIM), ("error", ORANGE)]:
            self._log.tag_config(tag, foreground=color)

    def _panel(self, title: str) -> tk.LabelFrame:
        return tk.LabelFrame(self, text=title,
                             font=("Segoe UI", 9, "bold"),
                             bg=BG_PANEL, fg=ACCENT,
                             bd=1, relief="solid",
                             padx=10, pady=6)

    def _browse_row(self, parent, label, var, cmd, row):
        tk.Label(parent, text=label, font=("Segoe UI", 10),
                 bg=BG_PANEL, fg=FG_DIM,
                 width=17, anchor="e").grid(row=row, column=0,
                                            sticky="e", pady=5)
        e = tk.Entry(parent, textvariable=var,
                     font=("Segoe UI", 10),
                     bg=BG_INPUT, fg=FG,
                     insertbackground=FG,
                     relief="flat")
        e.grid(row=row, column=1, sticky="ew", padx=8, pady=5)
        tk.Button(parent, text="Browse…",
                  font=("Segoe UI", 9),
                  bg=BG_INPUT, fg=ACCENT,
                  relief="flat", padx=10,
                  cursor="hand2",
                  command=cmd).grid(row=row, column=2, padx=(0, 2))

    # ─────────────────────────────────────────────────────────────────────────
    # Browse callbacks
    # ─────────────────────────────────────────────────────────────────────────

    def _browse_folder(self):
        d = filedialog.askdirectory(title="Select batch folder (parent of cartridge sub-folders)")
        if not d:
            return
        self.batch_folder.set(d)
        # Auto-find calibration.json
        for candidate in [Path(d) / "calibration.json",
                          Path(__file__).parent / "calibration.json"]:
            if candidate.exists():
                self.cal_file.set(str(candidate))
                self._log_write(f"  Auto-loaded calibration: {candidate}", "dim")
                break

    def _browse_cal(self):
        f = filedialog.askopenfilename(
            title="Select calibration.json",
            filetypes=[("JSON", "*.json"), ("All files", "*.*")])
        if f:
            self.cal_file.set(f)

    # ─────────────────────────────────────────────────────────────────────────
    # Calibration panel
    # ─────────────────────────────────────────────────────────────────────────

    # Image type → (calibrate.py feature arg, nominal_mm, hint filename)
    _CAL_INFO = {
        "holes":  ("hole",  0.50, "Holes_ch00.png"),
        "neck":   ("neck",  0.20, "neck_ch00.png"),
        "dab":    ("hole",  0.50, "DAB_ch00.png"),
        "mixing": ("hole",  0.50, "Mixing_ch00.png"),
    }

    def _build_calibrate_panel(self):
        cal = self._panel("  Calibrate  ")
        cal.pack(fill="x", padx=20, pady=(0, 6))

        # ── Row 0: image type + reference image ───────────────────────────────
        tk.Label(cal, text="Image type:", font=("Segoe UI", 10),
                 bg=BG_PANEL, fg=FG_DIM, anchor="e").grid(
                 row=0, column=0, sticky="e", pady=5, padx=(0, 6))

        type_cb = ttk.Combobox(cal, textvariable=self.cal_img_type,
                               values=["holes", "neck", "dab", "mixing"],
                               state="readonly", width=9,
                               font=("Segoe UI", 10))
        type_cb.grid(row=0, column=1, sticky="w", pady=5, padx=(0, 14))
        type_cb.bind("<<ComboboxSelected>>", self._on_cal_type_change)

        tk.Label(cal, text="Reference image:", font=("Segoe UI", 10),
                 bg=BG_PANEL, fg=FG_DIM, anchor="e").grid(
                 row=0, column=2, sticky="e", pady=5, padx=(0, 6))

        tk.Entry(cal, textvariable=self.cal_ref_path,
                 font=("Segoe UI", 10), bg=BG_INPUT, fg=FG,
                 insertbackground=FG, relief="flat").grid(
                 row=0, column=3, sticky="ew", pady=5, padx=(0, 6))

        tk.Button(cal, text="Browse…", font=("Segoe UI", 9),
                  bg=BG_INPUT, fg=ACCENT, relief="flat", padx=10,
                  cursor="hand2",
                  command=self._browse_cal_ref).grid(row=0, column=4, padx=(0, 2))

        # ── Row 1: n clicks + start button ───────────────────────────────────
        tk.Label(cal, text="# clicks:", font=("Segoe UI", 10),
                 bg=BG_PANEL, fg=FG_DIM, anchor="e").grid(
                 row=1, column=0, sticky="e", pady=4, padx=(0, 6))

        tk.Spinbox(cal, from_=1, to=5, textvariable=self.cal_n_meas,
                   width=4, font=("Segoe UI", 10),
                   bg=BG_INPUT, fg=FG,
                   relief="flat").grid(row=1, column=1, sticky="w", pady=4)

        tk.Label(cal,
                 text="per feature  ·  scroll=zoom  ·  right-drag=pan  ·  S=save  ·  Q=quit",
                 font=("Segoe UI", 8), bg=BG_PANEL, fg=FG_DIM).grid(
                 row=1, column=2, columnspan=2, sticky="w", padx=(0, 8))

        self._cal_btn = tk.Button(cal, text="🔬  Start Calibration",
                                  font=("Segoe UI", 10, "bold"),
                                  bg=YELLOW, fg="#1e1e2e",
                                  relief="flat", padx=16, pady=6,
                                  cursor="hand2",
                                  command=self._start_calibration)
        self._cal_btn.grid(row=1, column=4, pady=4, sticky="e")

        # ── Row 2: current calibration summary ───────────────────────────────
        tk.Label(cal, text="Current cal:", font=("Segoe UI", 9),
                 bg=BG_PANEL, fg=FG_DIM, anchor="e").grid(
                 row=2, column=0, sticky="e", padx=(0, 6), pady=(0, 4))

        self._cal_status_lbl = tk.Label(
            cal, text="—", font=("Consolas", 9),
            bg=BG_PANEL, fg=FG_DIM, anchor="w")
        self._cal_status_lbl.grid(row=2, column=1, columnspan=4,
                                   sticky="w", padx=(0, 8), pady=(0, 4))

        cal.columnconfigure(3, weight=1)
        self._refresh_cal_status()

    def _on_cal_type_change(self, _event=None):
        """When type changes, auto-hint the expected filename."""
        hint = self._CAL_INFO.get(self.cal_img_type.get(), ("hole", 0.5, ""))[2]
        current = self.cal_ref_path.get()
        # Only auto-fill if the box is empty OR still contains a previous hint
        hints = [v[2] for v in self._CAL_INFO.values()]
        if not current or any(current.endswith(h) for h in hints):
            self.cal_ref_path.set(hint)

    def _browse_cal_ref(self):
        f = filedialog.askopenfilename(
            title="Select reference calibration image",
            filetypes=[("PNG images", "*.png *.PNG"), ("All files", "*.*")])
        if not f:
            return
        self.cal_ref_path.set(f)
        # Auto-detect image type from filename
        stem = Path(f).stem.lower()
        for t, (_, _, hint) in self._CAL_INFO.items():
            if hint.lower().replace("_ch00.png", "") in stem:
                self.cal_img_type.set(t)
                break

    def _refresh_cal_status(self):
        """Read calibration.json and show a one-line status summary."""
        cal_path = self.cal_file.get().strip()
        if not cal_path or not os.path.exists(cal_path):
            # Try next to this script
            fallback = Path(__file__).parent / "calibration.json"
            if fallback.exists():
                cal_path = str(fallback)
            else:
                self._cal_status_lbl.configure(
                    text="calibration.json not found — run calibration first",
                    fg=ORANGE)
                return
        try:
            with open(cal_path) as fh:
                cal = json.load(fh)
            parts = []
            for t in ["holes", "neck", "dab", "mixing"]:
                entry = cal.get(t) or cal.get(t.upper())
                if isinstance(entry, dict) and "scale_factor_um_per_px" in entry:
                    um   = entry["scale_factor_um_per_px"]
                    date = (entry.get("calibration_date", "")[:10]
                            if entry.get("calibration_date") else "?")
                    parts.append(f"{t.capitalize()}: {um:.3f} µm/px ({date})")
                else:
                    parts.append(f"{t.capitalize()}: —")
            self._cal_status_lbl.configure(
                text="   |   ".join(parts), fg=FG_DIM)
        except Exception as e:
            self._cal_status_lbl.configure(
                text=f"Error reading calibration: {e}", fg=RED)

    def _start_calibration(self):
        if self._cal_running:
            messagebox.showinfo("Busy", "Calibration already in progress.")
            return

        ref = self.cal_ref_path.get().strip()
        if not ref:
            messagebox.showwarning("No image",
                                   "Please select a reference image to calibrate against.")
            return
        if not os.path.exists(ref):
            messagebox.showwarning("Not found",
                                   f"Image not found:\n{ref}\n\nPlease browse to the correct file.")
            return

        img_type          = self.cal_img_type.get()
        feature, nom, _   = self._CAL_INFO.get(img_type, ("hole", 0.5, ""))
        n_meas            = self.cal_n_meas.get()

        # Resolve calibration.json output path (absolute so subprocess finds it)
        cal_out = self.cal_file.get().strip()
        if not cal_out:
            cal_out = str(Path(__file__).parent / "calibration.json")
        cal_out = str(Path(cal_out).resolve())

        self._cal_running = True
        self._cal_btn.configure(state="disabled", text="⏳  Calibrating…")
        self._log_write("", "")
        self._log_write(f"── Calibration: {img_type.upper()} ──", "section")
        self._log_write(f"  Ref image : {Path(ref).name}", "dim")
        self._log_write(f"  Feature   : {feature}  (nominal {nom} mm)", "dim")
        self._log_write(f"  Clicks    : {n_meas}  (click both edges of the feature)", "dim")
        self._log_write("  A console window will open for the measurement prompt.", "dim")
        self._log_write("  Controls  : Scroll=zoom  |  Right-drag=pan  |  S=save  |  Q=quit", "dim")

        threading.Thread(
            target=self._cal_worker,
            args=(ref, feature, n_meas, cal_out),
            daemon=True
        ).start()

    def _cal_worker(self, ref, feature, n_meas, cal_out):
        """Run calibrate.py in a new console window and wait for completion."""
        script = str(Path(__file__).parent / "calibrate.py")
        cmd    = [
            sys.executable, script,
            "calibrate",
            "--ref",     ref,
            "--feature", feature,
            "--n_holes", str(n_meas),
            "--output",  cal_out,
        ]

        kwargs = {"cwd": str(Path(__file__).parent)}
        if sys.platform == "win32":
            # Open in a new visible console so the engineer can type the
            # measured value at the "Enter your measurement" prompt.
            kwargs["creationflags"] = subprocess.CREATE_NEW_CONSOLE

        try:
            proc = subprocess.Popen(cmd, **kwargs)
            proc.wait()          # block until the user closes the window
            success = (proc.returncode == 0)
        except Exception as e:
            self._q.put(("log", f"  Calibration error: {e}", "error"))
            success = False

        self._q.put(("cal_done", success))

    # ─────────────────────────────────────────────────────────────────────────
    # Run / Stop
    # ─────────────────────────────────────────────────────────────────────────

    def _run(self):
        folder = self.batch_folder.get().strip()
        cal    = self.cal_file.get().strip()

        if not folder:
            messagebox.showwarning("No folder", "Please select a batch folder.")
            return
        if not os.path.isdir(folder):
            messagebox.showwarning("Not found", f"Folder not found:\n{folder}")
            return
        if not os.path.exists(cal):
            messagebox.showwarning("No calibration",
                                   f"Calibration file not found:\n{cal}\n\n"
                                   "Run calibrate.py first.")
            return

        types = ([t for t, v in [("holes", self.do_holes),
                                  ("neck",  self.do_neck),
                                  ("dab",   self.do_dab),
                                  ("mixing",self.do_mixing)]
                  if v.get()])
        if not types:
            messagebox.showwarning("No types", "Tick at least one image type.")
            return

        self._clear()
        self._run_btn.configure(state="disabled")
        self._stop_btn.configure(state="normal")
        self._running = True

        threading.Thread(
            target=self._worker,
            args=(folder, cal, types, self.save_images.get()),
            daemon=True
        ).start()

    def _stop(self):
        self._running = False
        self._set_status("Stopping…")

    # ─────────────────────────────────────────────────────────────────────────
    # Background worker (runs in a separate thread)
    # ─────────────────────────────────────────────────────────────────────────

    def _worker(self, folder, cal_path, types, save_imgs):

        def log(msg, tag=""):
            self._q.put(("log", msg, tag))

        def status(msg):
            self._q.put(("status", msg))

        # Load modules + calibration
        try:
            _load_qc_modules()
            cal = _calibrate_mod.load_calibration(cal_path)
        except Exception as e:
            self._q.put(("error", f"Failed to load calibration:\n{e}"))
            return

        # Discover cartridge sub-folders
        batch      = Path(folder)
        subfolders = _find_cartridge_folders(batch)

        if not subfolders:
            self._q.put(("error",
                         "No cartridge folders found.\n\n"
                         "Expected structure:\n"
                         "  batch_folder/\n"
                         "    1/  Holes_ch00.png  neck_ch00.png …\n"
                         "    2/  …"))
            return

        self._q.put(("progress_max", len(subfolders)))
        log(f"Batch : {folder}", "section")
        log(f"Found : {len(subfolders)} cartridge folder(s)", "dim")
        log(f"Types : {', '.join(types)}", "dim")
        log("")

        for i, sf in enumerate(subfolders):
            if not self._running:
                log("── Stopped by user ──", "warn")
                break

            status(f"Processing {sf.name}  ({i+1}/{len(subfolders)})")
            log(f"── Cartridge: {sf.name} ──", "section")

            row = {k: "N/A" for k in ("name","holes","neck","dab","mixing","overall")}
            row["name"]    = sf.name
            row["details"] = []
            cart_results   = {}   # img_type → detect() result, for detailed CSV

            # Find PNG images in the sub-folder
            # Exclude annotated outputs (_detected.png) from previous runs
            # so re-running doesn't feed annotated images back into detection.
            # Deduplicated by resolved path: on case-insensitive filesystems
            # (Windows), "*.png" and "*.PNG" match the same files, which
            # previously caused every image to be processed twice.
            seen_paths = set()
            imgs = []
            for p in sorted(list(sf.glob("*.png")) + list(sf.glob("*.PNG"))):
                if (p.stem.endswith("_detected")
                        or p.stem.endswith("_debug")
                        or p.stem.endswith("_annotated")):
                    continue
                key = p.resolve()
                if key in seen_paths:
                    continue
                seen_paths.add(key)
                imgs.append(p)

            for img_path in imgs:
                img_type = _detect_mod.detect_image_type(str(img_path))
                if img_type not in types:
                    continue

                ann = str(sf / f"{img_path.stem}_detected.png") if save_imgs else None

                try:
                    # Capture all print() from detect modules → GUI log
                    stream = _QueueStream(self._q, tag="dim")
                    with contextlib.redirect_stdout(stream):
                        result = _detect_mod.detect(
                            str(img_path), cal,
                            save_annotated=save_imgs,
                            annotated_path=ann)
                    stream.flush()

                    cart_results[img_type] = result   # save for detailed CSV

                    pf      = result["overall_pass"]
                    sym     = "✓" if pf else "✗"
                    mmpx    = result.get("mm_per_px", 0)
                    row[img_type] = "PASS" if pf else "FAIL"

                    f = result["features"]
                    if img_type == "holes":
                        det = (f"holes {f.get('n_detected','?')}"
                               f"/{f.get('n_expected','?')}")
                    elif img_type == "neck" and "error" not in f:
                        det = (f"neck {f.get('trimmed_mean_mm', f.get('mean_width_mm','?')):.4f} mm"
                               f"  dev={f.get('tolerance',{}).get('deviation_mm',0):+.5f}")
                    elif img_type == "neck":
                        det = f"neck ERR: {f['error']}"
                    elif img_type == "dab":
                        if "diameter_mm" in f:
                            det = (f"DAB {f['diameter_mm']:.4f} mm"
                                   f"  dev={f.get('deviation_mm',0):+.5f}")
                        else:
                            det = "DAB ERR"
                    elif img_type == "mixing":
                        holes = f.get("holes", [])
                        n_p = sum(1 for h in holes if h.get("pass"))
                        if holes:
                            dvals = "/".join(f"{h['diameter_mm']:.4f}" for h in holes)
                            det = f"mixing {n_p}/{len(holes)} PASS  [{dvals}]mm"
                        else:
                            det = "mixing ERR"
                    else:
                        det = img_type

                    row["details"].append(det)
                    log(f"  {sym} {img_path.name}:  "
                        f"{'PASS' if pf else 'FAIL'}  "
                        f"({det})  "
                        f"[{mmpx*1000:.3f} µm/px]",
                        "pass" if pf else "fail")

                except Exception as e:
                    row[img_type] = "ERR"
                    row["details"].append(f"{img_type} ERR")
                    log(f"  ✗ {img_path.name}: ERROR — {e}", "error")

            # Save one detail CSV per image type so re-runs don't overwrite each other
            for img_type, result in cart_results.items():
                try:
                    detail_rows = _detect_mod.results_to_rows(sf.name, {img_type: result})
                    detail_path = str(sf / f"qc_detail_{sf.name}_{img_type}.csv")
                    _detect_mod.export_csv(detail_rows, detail_path)
                    log(f"  Detail CSV ({img_type}): {detail_path}", "dim")
                except Exception as e:
                    log(f"  Detail CSV error ({img_type}): {e}", "warn")

            # Overall
            vals = [row[t] for t in types if row[t] != "N/A"]
            if not vals:
                row["overall"] = "N/A"
            elif all(v == "PASS" for v in vals):
                row["overall"] = "PASS"
            elif any(v in ("FAIL", "ERR") for v in vals):
                row["overall"] = "FAIL"
            else:
                row["overall"] = "N/A"

            row["details"] = "   ".join(row["details"])
            self._q.put(("result", row))
            self._q.put(("progress", i + 1))
            log("")

        self._q.put(("done", None))

    # ─────────────────────────────────────────────────────────────────────────
    # Queue polling (main thread)
    # ─────────────────────────────────────────────────────────────────────────

    def _poll_queue(self):
        try:
            while True:
                item = self._q.get_nowait()
                t    = item[0]

                if t == "log":
                    _, msg, tag = item
                    self._log_write(msg, tag)

                elif t == "status":
                    self._set_status(item[1])

                elif t == "progress_max":
                    self._progress.configure(maximum=item[1])

                elif t == "progress":
                    self._progress["value"] = item[1]

                elif t == "result":
                    self._add_row(item[1])
                    self._results.append(item[1])

                elif t == "error":
                    messagebox.showerror("Error", item[1])
                    self._finish()

                elif t == "done":
                    n_pass = sum(1 for r in self._results if r["overall"] == "PASS")
                    n_fail = sum(1 for r in self._results if r["overall"] == "FAIL")
                    self._log_write("")
                    self._log_write(
                        f"Complete:  {n_pass} PASS   {n_fail} FAIL   "
                        f"(total {len(self._results)} cartridges)",
                        "pass" if n_fail == 0 else "fail")
                    if self.save_csv_var.get() and self._results:
                        self._auto_save_csv()
                    self._finish()

                elif t == "cal_done":
                    self._cal_running = False
                    self._cal_btn.configure(state="normal",
                                            text="🔬  Start Calibration")
                    if item[1]:   # success
                        self._log_write("  ✓ Calibration saved to calibration.json", "pass")
                        self._refresh_cal_status()
                    else:
                        self._log_write("  ✗ Calibration was cancelled or failed", "warn")

        except queue.Empty:
            pass

        self.after(50, self._poll_queue)

    # ─────────────────────────────────────────────────────────────────────────
    # Results table
    # ─────────────────────────────────────────────────────────────────────────

    def _add_row(self, r):
        def fmt(v):
            if v == "PASS": return "✓ PASS"
            if v == "FAIL": return "✗ FAIL"
            if v == "ERR":  return "⚠  ERR"
            return v

        tag = ("pass"  if r["overall"] == "PASS"         else
               "fail"  if r["overall"] in ("FAIL","ERR") else
               "pending")

        self._tree.insert("", "end", tags=(tag,), values=(
            r["name"],
            fmt(r["holes"]), fmt(r["neck"]),
            fmt(r["dab"]),   fmt(r["mixing"]),
            fmt(r["overall"]), r["details"]))

    # ─────────────────────────────────────────────────────────────────────────
    # CSV export
    # ─────────────────────────────────────────────────────────────────────────

    def _auto_save_csv(self):
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = str(Path(self.batch_folder.get()) / f"qc_report_{ts}.csv")
        self._write_csv(path)
        self._log_write(f"  CSV saved: {path}", "dim")

    def _export_csv(self):
        if not self._results:
            messagebox.showinfo("No results", "Run QC first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile=f"qc_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        if path:
            self._write_csv(path)
            self._log_write(f"  Exported: {path}", "dim")

    def _write_csv(self, path):
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["Cartridge", "Holes", "Neck", "DAB",
                        "Mixing", "Overall", "Details", "Timestamp"])
            ts = datetime.now().isoformat()
            for r in self._results:
                w.writerow([r["name"], r["holes"], r["neck"],
                             r["dab"],  r["mixing"], r["overall"],
                             r["details"], ts])

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _log_write(self, msg, tag=""):
        self._log.configure(state="normal")
        self._log.insert("end", msg + "\n", tag)
        self._log.see("end")
        self._log.configure(state="disabled")

    def _set_status(self, msg):
        self._status_lbl.configure(text=msg)

    def _finish(self):
        self._running = False
        self._run_btn.configure(state="normal")
        self._stop_btn.configure(state="disabled")
        n = len(self._results)
        self._set_status(f"Done — {n} cartridge{'s' if n != 1 else ''} processed")

    def _clear(self):
        for row in self._tree.get_children():
            self._tree.delete(row)
        self._results.clear()
        self._log.configure(state="normal")
        self._log.delete("1.0", "end")
        self._log.configure(state="disabled")
        self._progress["value"] = 0
        self._set_status("Ready")


# ── Folder discovery ──────────────────────────────────────────────────────────

def _find_cartridge_folders(batch: Path):
    """
    Return cartridge sub-folders sorted numerically.
    Handles two structures:
      A) batch/1/  batch/2/  …          (numbered)
      B) batch/BASEPLATE/1/  …          (nested BASEPLATE folder)
    Also handles the case where batch IS a single cartridge folder
    (contains PNG files directly — wraps it in a list).
    """
    # Check if the folder itself has PNGs — single-cartridge mode
    direct_pngs = list(batch.glob("*.png")) + list(batch.glob("*.PNG"))
    if direct_pngs:
        return [batch]

    # Look for numbered sub-folders one or two levels deep
    candidates = []
    for item in batch.iterdir():
        if item.is_dir():
            # Direct numbered child
            if item.name.isdigit() or _has_pngs(item):
                candidates.append(item)
            else:
                # One level deeper (e.g. BASEPLATE/1/)
                for sub in item.iterdir():
                    if sub.is_dir() and (sub.name.isdigit() or _has_pngs(sub)):
                        candidates.append(sub)

    return sorted(candidates, key=lambda d: (
        not d.name.isdigit(),
        int(d.name) if d.name.isdigit() else d.name))


def _has_pngs(folder: Path) -> bool:
    return bool(list(folder.glob("*.png")) + list(folder.glob("*.PNG")))


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = QCApp()
    app.mainloop()

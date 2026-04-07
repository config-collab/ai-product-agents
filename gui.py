"""
Design to Intent — Desktop GUI
================================
Launches the design pipeline with a form-based interface.
Streams agent output live into a log window.

Usage:
    python gui.py
"""

import json
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext

# ── Colour palette (matches the HTML report) ─────────────────────
C_BG       = "#f1f5f9"
C_PANEL    = "#ffffff"
C_DARK     = "#0f172a"
C_BLUE     = "#1e40af"
C_BLUE_LT  = "#2563eb"
C_MUTED    = "#64748b"
C_BORDER   = "#e2e8f0"
C_OK       = "#166534"
C_ERR      = "#991b1b"
C_WARN     = "#92400e"
C_TEXT     = "#1e293b"

FONT       = ("Segoe UI", 10)
FONT_SM    = ("Segoe UI", 9)
FONT_MONO  = ("Consolas", 9)
FONT_HEAD  = ("Segoe UI", 22, "bold")
FONT_SUB   = ("Segoe UI", 10)


class DesignToIntentApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Design to Intent")
        self.geometry("860x720")
        self.minsize(700, 560)
        self.configure(bg=C_BG)
        self._proc   = None
        self._q      = queue.Queue()
        self._report = None

        self._build_ui()
        self._poll_output()

    # ── UI construction ───────────────────────────────────────────

    def _build_ui(self):
        # Header
        hdr = tk.Frame(self, bg=C_DARK, pady=18)
        hdr.pack(fill="x")
        tk.Label(hdr, text="DESIGN TO INTENT",
                 font=("Segoe UI", 8, "bold"), fg="#94a3b8", bg=C_DARK,
                 letterSpacing=4).pack()
        tk.Label(hdr, text="AI-driven product design — from idea to optimised BOM",
                 font=FONT_HEAD, fg="white", bg=C_DARK).pack()

        # Main area: form left, log right
        main = tk.Frame(self, bg=C_BG)
        main.pack(fill="both", expand=True, padx=16, pady=12)
        main.columnconfigure(0, weight=1, minsize=300)
        main.columnconfigure(1, weight=2)
        main.rowconfigure(0, weight=1)

        self._build_form(main)
        self._build_log(main)

    def _build_form(self, parent):
        form = tk.Frame(parent, bg=C_PANEL, bd=0,
                        highlightbackground=C_BORDER, highlightthickness=1)
        form.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        inner = tk.Frame(form, bg=C_PANEL, padx=18, pady=18)
        inner.pack(fill="both", expand=True)

        def section(text):
            tk.Label(inner, text=text, font=("Segoe UI", 7, "bold"),
                     fg=C_MUTED, bg=C_PANEL, anchor="w").pack(fill="x", pady=(14, 2))
            ttk.Separator(inner).pack(fill="x", pady=(0, 6))

        # ── Product idea ─────────────────────────────────────────
        section("PRODUCT IDEA")
        self._idea = tk.StringVar()
        e = tk.Entry(inner, textvariable=self._idea, font=FONT,
                     fg=C_TEXT, bg=C_BG, relief="flat",
                     highlightbackground=C_BORDER, highlightthickness=1, bd=4)
        e.pack(fill="x")
        tk.Label(inner, text="e.g. modular home energy storage system",
                 font=FONT_SM, fg=C_MUTED, bg=C_PANEL, anchor="w").pack(fill="x")

        # ── Intent ───────────────────────────────────────────────
        section("INTENT  (leave blank for auto-recommendation)")
        tk.Label(inner, text="Goal", font=FONT_SM, fg=C_MUTED,
                 bg=C_PANEL, anchor="w").pack(fill="x")
        self._goal = tk.StringVar()
        tk.Entry(inner, textvariable=self._goal, font=FONT,
                 fg=C_TEXT, bg=C_BG, relief="flat",
                 highlightbackground=C_BORDER, highlightthickness=1, bd=4).pack(fill="x")

        tk.Label(inner, text="Hard constraints  (comma-separated)",
                 font=FONT_SM, fg=C_MUTED, bg=C_PANEL, anchor="w").pack(fill="x", pady=(8,0))
        self._constraints = tk.StringVar()
        tk.Entry(inner, textvariable=self._constraints, font=FONT,
                 fg=C_TEXT, bg=C_BG, relief="flat",
                 highlightbackground=C_BORDER, highlightthickness=1, bd=4).pack(fill="x")

        tk.Label(inner, text="Context  (use case, environment, user)",
                 font=FONT_SM, fg=C_MUTED, bg=C_PANEL, anchor="w").pack(fill="x", pady=(8,0))
        self._context = tk.StringVar()
        tk.Entry(inner, textvariable=self._context, font=FONT,
                 fg=C_TEXT, bg=C_BG, relief="flat",
                 highlightbackground=C_BORDER, highlightthickness=1, bd=4).pack(fill="x")

        # ── Output options ───────────────────────────────────────
        section("OUTPUT")
        self._vis = tk.StringVar(value="skip")
        for label, val in [("Skip (report only)", "skip"),
                            ("DALL-E 3 image render", "image"),
                            ("Onshape 3D model (CAD)", "cad")]:
            tk.Radiobutton(inner, text=label, variable=self._vis, value=val,
                           font=FONT_SM, fg=C_TEXT, bg=C_PANEL,
                           activebackground=C_PANEL, selectcolor=C_PANEL).pack(anchor="w")

        # ── Run button ───────────────────────────────────────────
        tk.Frame(inner, bg=C_PANEL, height=10).pack()
        self._run_btn = tk.Button(inner, text="Run Design Pipeline",
                                  font=("Segoe UI", 11, "bold"),
                                  fg="white", bg=C_BLUE, activebackground=C_BLUE_LT,
                                  relief="flat", padx=12, pady=10, cursor="hand2",
                                  command=self._run)
        self._run_btn.pack(fill="x")

        self._report_btn = tk.Button(inner, text="View Last Report",
                                     font=FONT_SM, fg=C_BLUE, bg=C_PANEL,
                                     activebackground=C_BG, relief="flat",
                                     cursor="hand2", command=self._open_report)
        self._report_btn.pack(fill="x", pady=(4, 0))
        self._report_btn.config(state="disabled")

        self._status = tk.Label(inner, text="", font=FONT_SM,
                                fg=C_MUTED, bg=C_PANEL, wraplength=240, justify="left")
        self._status.pack(fill="x", pady=(8, 0))

    def _build_log(self, parent):
        log_frame = tk.Frame(parent, bg=C_PANEL,
                             highlightbackground=C_BORDER, highlightthickness=1)
        log_frame.grid(row=0, column=1, sticky="nsew")

        tk.Label(log_frame, text="Agent output", font=("Segoe UI", 7, "bold"),
                 fg=C_MUTED, bg=C_PANEL, anchor="w", padx=10, pady=8).pack(fill="x")
        ttk.Separator(log_frame).pack(fill="x")

        self._log = scrolledtext.ScrolledText(
            log_frame, font=FONT_MONO, bg=C_DARK, fg="#e2e8f0",
            insertbackground="white", relief="flat", padx=10, pady=10,
            wrap="word", state="disabled")
        self._log.pack(fill="both", expand=True)

        # colour tags
        self._log.tag_config("sep",      foreground="#6366f1")
        self._log.tag_config("ok",       foreground="#4ade80")
        self._log.tag_config("warn",     foreground="#fbbf24")
        self._log.tag_config("err",      foreground="#f87171")
        self._log.tag_config("dim",      foreground="#64748b")

    # ── Pipeline execution ────────────────────────────────────────

    def _run(self):
        idea = self._idea.get().strip()
        if not idea:
            self._set_status("Enter a product idea first.", C_ERR)
            return

        self._clear_log()
        self._run_btn.config(state="disabled")
        self._report_btn.config(state="disabled")
        self._report = None
        self._set_status("Running...", C_MUTED)

        cmd = [sys.executable, "plm_agents.py", "--idea", idea]
        if self._goal.get().strip():
            cmd += ["--goal", self._goal.get().strip()]
        if self._constraints.get().strip():
            cmd += ["--constraints", self._constraints.get().strip()]
        if self._context.get().strip():
            cmd += ["--context", self._context.get().strip()]

        # inject visualisation choice via env var read by the subprocess
        env = os.environ.copy()
        env["DTI_VIS_CHOICE"] = {"skip": "3", "image": "2", "cad": "1"}[self._vis.get()]

        self._proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, env=env,
            cwd=os.path.dirname(os.path.abspath(__file__)))

        threading.Thread(target=self._stream, daemon=True).start()

    def _stream(self):
        for line in self._proc.stdout:
            self._q.put(("line", line))
        self._proc.wait()
        self._q.put(("done", self._proc.returncode))

    def _poll_output(self):
        try:
            while True:
                kind, val = self._q.get_nowait()
                if kind == "line":
                    self._append(val)
                    # detect report path
                    if "Saved →" in val and "report_" in val:
                        path = val.split("Saved →")[-1].strip()
                        self._report = path
                elif kind == "done":
                    self._on_done(val)
        except queue.Empty:
            pass
        self.after(80, self._poll_output)

    def _on_done(self, returncode):
        self._run_btn.config(state="normal")
        if returncode == 0:
            self._set_status("Done.", C_OK)
            if self._report:
                self._report_btn.config(state="normal")
        else:
            self._set_status("Pipeline ended with errors — see log.", C_ERR)

    def _open_report(self):
        if self._report and os.path.exists(self._report):
            import webbrowser
            webbrowser.open(f"file:///{self._report.replace(os.sep, '/')}")

    # ── Log helpers ───────────────────────────────────────────────

    def _append(self, text):
        self._log.config(state="normal")
        tag = None
        t = text.strip()
        if t.startswith("═"):
            tag = "sep"
        elif "✓" in t or "✅" in t or "Done" in t:
            tag = "ok"
        elif "⚠" in t or "↺" in t or "warning" in t.lower():
            tag = "warn"
        elif "error" in t.lower() or "traceback" in t.lower() or "✗" in t:
            tag = "err"
        elif t.startswith("#") or t.startswith("//"):
            tag = "dim"
        self._log.insert("end", text, tag or "")
        self._log.see("end")
        self._log.config(state="disabled")

    def _clear_log(self):
        self._log.config(state="normal")
        self._log.delete("1.0", "end")
        self._log.config(state="disabled")

    def _set_status(self, msg, colour=C_MUTED):
        self._status.config(text=msg, fg=colour)


if __name__ == "__main__":
    app = DesignToIntentApp()
    app.mainloop()

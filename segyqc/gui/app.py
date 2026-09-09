"""
app.py
------
Main Tkinter application window. This is the orchestrator: it wires
together file selection, format detection, the existing QC engine, and
all the display panels (trace viewer, header inspector, QC results,
batch, rules, compare). No QC calculation happens in this file - every
number shown comes from segyqc.qc / segyqc.format_detect / segyqc.compare.

Launch with:
    python -m segyqc.gui.app
or, after `pip install -e .`:
    segy-qc
"""

import os
import sys
import threading
import queue
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from ..qc import run_qc
from ..format_detect import detect_format, REVISION_OVERRIDE_OPTIONS
from ..compare import compare_reports

from .trace_viewer import TraceViewerFrame
from .header_panel import HeaderPanel
from .qc_panel import QCResultsPanel
from .batch_panel import BatchPanel
from .rules_panel import RulesPanel


class SegyQCApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SEG-Y QC Toolkit")
        self.geometry("1100x700")

        self.current_path = None
        self.current_report = None
        self._compare_reports = {"before": None, "after": None}
        self._qc_queue = queue.Queue()
        self._detected_format_info = None

        self._build_top_bar()
        self._build_notebook()

    # ---------------- Top bar: file selection + format info ----------------

    def _build_top_bar(self):
        bar = ttk.Frame(self)
        bar.pack(side="top", fill="x", padx=8, pady=6)

        ttk.Button(bar, text="Open SEG-Y File...", command=self.open_file_dialog).pack(side="left", padx=(0, 6))
        self.run_qc_button = ttk.Button(bar, text="Run QC", command=self.run_qc_on_current, state="disabled")
        self.run_qc_button.pack(side="left", padx=(0, 6))

        self.file_label = ttk.Label(bar, text="No file loaded")
        self.file_label.pack(side="left", padx=10)

        self.format_label = ttk.Label(bar, text="", foreground="#555")
        self.format_label.pack(side="left", padx=10)

        ttk.Label(bar, text="Revision:").pack(side="left", padx=(10, 2))
        self.revision_override_var = tk.StringVar(value=REVISION_OVERRIDE_OPTIONS[0])
        self.revision_override_box = ttk.Combobox(
            bar, textvariable=self.revision_override_var, width=16, state="readonly",
            values=REVISION_OVERRIDE_OPTIONS,
        )
        self.revision_override_box.pack(side="left")
        self.revision_override_box.bind("<<ComboboxSelected>>", lambda e: self._refresh_format_label())

    # ---------------- Tabs ----------------

    def _build_notebook(self):
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(side="top", fill="both", expand=True, padx=8, pady=(0, 8))

        self.qc_panel = QCResultsPanel(self.notebook)
        self.notebook.add(self.qc_panel, text="QC Results")

        self.trace_viewer = TraceViewerFrame(self.notebook)
        self.notebook.add(self.trace_viewer, text="Trace Viewer")

        self.header_panel = HeaderPanel(self.notebook)
        self.notebook.add(self.header_panel, text="Header Inspector")

        self.rules_panel = RulesPanel(self.notebook)
        self.notebook.add(self.rules_panel, text="QC Rules")

        self.batch_panel = BatchPanel(
            self.notebook,
            on_file_selected=self._on_batch_row_selected,
            config_provider=self.rules_panel.get_config,
        )
        self.notebook.add(self.batch_panel, text="Batch QC")

        self._build_compare_tab()

    def _build_compare_tab(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Compare")

        controls = ttk.Frame(frame)
        controls.pack(side="top", fill="x", padx=8, pady=8)

        ttk.Button(controls, text="Set current file as 'Before'", command=lambda: self._set_compare_slot("before")).pack(
            side="left", padx=(0, 6))
        ttk.Button(controls, text="Set current file as 'After'", command=lambda: self._set_compare_slot("after")).pack(
            side="left", padx=(0, 6))
        ttk.Button(controls, text="Compare", command=self._run_compare).pack(side="left", padx=(12, 0))

        self.compare_status = ttk.Label(frame, text="Before: (none)   After: (none)")
        self.compare_status.pack(side="top", fill="x", padx=8)

        columns = ("metric", "before", "after", "delta")
        self.compare_tree = ttk.Treeview(frame, columns=columns, show="headings", height=12)
        for col in columns:
            self.compare_tree.heading(col, text=col.title())
            self.compare_tree.column(col, width=150, anchor="w")
        self.compare_tree.pack(side="top", fill="both", expand=True, padx=8, pady=8)

    # ---------------- File loading ----------------

    def open_file_dialog(self):
        path = filedialog.askopenfilename(filetypes=[("SEG-Y files", "*.sgy *.segy"), ("All files", "*.*")])
        if path:
            self.load_file(path)

    def load_file(self, path):
        self.current_path = path
        self.current_report = None
        self.file_label.config(text=os.path.basename(path))
        self.run_qc_button.config(state="normal")
        self.revision_override_var.set(REVISION_OVERRIDE_OPTIONS[0])

        try:
            self._detected_format_info = detect_format(path)
        except Exception as e:
            self._detected_format_info = None
            self.format_label.config(text=f"Format detection failed: {e}")
        else:
            self._refresh_format_label()

        try:
            self.trace_viewer.load_file(path)
        except Exception as e:
            messagebox.showwarning("Trace viewer", f"Could not load traces for viewing: {e}")

        try:
            self.header_panel.load_file(path)
        except Exception as e:
            messagebox.showwarning("Header inspector", f"Could not load headers: {e}")

    def _refresh_format_label(self):
        if not self._detected_format_info:
            return
        info = self._detected_format_info
        override = self.revision_override_var.get()

        if override == REVISION_OVERRIDE_OPTIONS[0]:
            revision_text = info.revision
            standard_note = "" if info.is_standard else "  [byte says non-standard/unspecified - override above if you know the real revision]"
        else:
            revision_text = f"{override} (user override - byte 0x{info.revision_raw:04x} not trusted)"
            standard_note = ""

        self.format_label.config(
            text=f"{revision_text} | {info.sample_format_name} | "
                 f"{info.byte_order}-endian | {info.samples_per_trace} samples/trace{standard_note}"
        )

    # ---------------- Running QC ----------------

    def run_qc_on_current(self):
        if not self.current_path:
            return
        self.run_qc_button.config(state="disabled", text="Running...")
        config = self.rules_panel.get_config()
        thread = threading.Thread(target=self._run_qc_worker, args=(self.current_path, config), daemon=True)
        thread.start()
        self.after(100, self._poll_qc_queue)

    def _run_qc_worker(self, path, config):
        try:
            report = run_qc(path, config=config)
            self._qc_queue.put(("done", report))
        except Exception as e:
            self._qc_queue.put(("error", str(e)))

    def _poll_qc_queue(self):
        try:
            kind, payload = self._qc_queue.get_nowait()
            if kind == "done":
                self.current_report = payload
                self.qc_panel.show_report(payload, self.current_path)
                self.notebook.select(self.qc_panel)
            else:
                messagebox.showerror("QC failed", payload)
            self.run_qc_button.config(state="normal", text="Run QC")
            return
        except queue.Empty:
            self.after(100, self._poll_qc_queue)

    # ---------------- Batch -> main panels ----------------

    def _on_batch_row_selected(self, path, report):
        self.current_path = path
        self.current_report = report
        self.file_label.config(text=os.path.basename(path))
        self.qc_panel.show_report(report, path)
        try:
            self.trace_viewer.load_file(path)
            self.header_panel.load_file(path)
        except Exception:
            pass
        self.notebook.select(self.qc_panel)

    # ---------------- Compare ----------------

    def _set_compare_slot(self, slot):
        if not self.current_report or not self.current_path:
            messagebox.showinfo("No QC results", "Run QC on a file first.")
            return
        self._compare_reports[slot] = (self.current_path, self.current_report)
        self._update_compare_status()

    def _update_compare_status(self):
        b = self._compare_reports["before"]
        a = self._compare_reports["after"]
        b_name = os.path.basename(b[0]) if b else "(none)"
        a_name = os.path.basename(a[0]) if a else "(none)"
        self.compare_status.config(text=f"Before: {b_name}   After: {a_name}")

    def _run_compare(self):
        b = self._compare_reports["before"]
        a = self._compare_reports["after"]
        if not b or not a:
            messagebox.showinfo("Compare", "Set both a 'Before' and an 'After' file first.")
            return
        rows = compare_reports(b[1], a[1])
        for row in self.compare_tree.get_children():
            self.compare_tree.delete(row)
        for r in rows:
            self.compare_tree.insert("", "end", values=(r.metric, r.before, r.after, r.delta))


def main():
    app = SegyQCApp()
    app.mainloop()


if __name__ == "__main__":
    main()

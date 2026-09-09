"""
batch_panel.py
--------------
Batch QC: select multiple files or a folder, run QC across all of them
sequentially (via segyqc.batch.run_batch_qc, in a background thread so
the GUI stays responsive), and show progress + a per-file results table.
"""

import os
import threading
import queue
import tkinter as tk
from tkinter import ttk, filedialog

from ..batch import run_batch_qc


class BatchPanel(ttk.Frame):
    def __init__(self, parent, on_file_selected=None, config_provider=None, *args, **kwargs):
        """
        on_file_selected: optional callable(path, report) invoked when the
            user double-clicks a completed row, so the main app can load
            that file into the QC/trace/header panels.
        config_provider: optional callable() -> QCConfig, so batch runs
            respect whatever rules config is currently set in the GUI.
        """
        super().__init__(parent, *args, **kwargs)
        self.on_file_selected = on_file_selected
        self.config_provider = config_provider
        self.selected_paths = []
        self._queue = queue.Queue()
        self._batch_result = None

        top = ttk.Frame(self)
        top.pack(side="top", fill="x", padx=6, pady=4)
        ttk.Button(top, text="Add Files...", command=self.add_files).pack(side="left", padx=(0, 6))
        ttk.Button(top, text="Add Folder...", command=self.add_folder).pack(side="left", padx=(0, 6))
        ttk.Button(top, text="Clear", command=self.clear_selection).pack(side="left", padx=(0, 6))
        self.run_button = ttk.Button(top, text="Run Batch QC", command=self.run_batch)
        self.run_button.pack(side="left", padx=(12, 0))

        self.selection_label = ttk.Label(self, text="No files selected.")
        self.selection_label.pack(side="top", fill="x", padx=6)

        progress_frame = ttk.Frame(self)
        progress_frame.pack(side="top", fill="x", padx=6, pady=4)
        self.progress = ttk.Progressbar(progress_frame, mode="determinate")
        self.progress.pack(side="left", fill="x", expand=True)
        self.status_label = ttk.Label(progress_frame, text="")
        self.status_label.pack(side="left", padx=10)

        columns = ("file", "status", "critical", "warning")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=12)
        for col, w in zip(columns, (420, 100, 80, 80)):
            self.tree.heading(col, text=col.title())
            self.tree.column(col, width=w, anchor="w")
        self.tree.tag_configure("failed", background="#fed7d7")
        self.tree.tag_configure("has_critical", background="#feebc8")
        self.tree.pack(side="top", fill="both", expand=True, padx=6, pady=(0, 6))
        self.tree.bind("<Double-1>", self._on_row_double_click)

        self._row_reports = {}

    def add_files(self):
        paths = filedialog.askopenfilenames(filetypes=[("SEG-Y files", "*.sgy *.segy"), ("All files", "*.*")])
        if paths:
            self.selected_paths.extend(paths)
            self._refresh_selection_label()

    def add_folder(self):
        path = filedialog.askdirectory()
        if path:
            self.selected_paths.append(path)
            self._refresh_selection_label()

    def clear_selection(self):
        self.selected_paths = []
        self._refresh_selection_label()

    def _refresh_selection_label(self):
        if not self.selected_paths:
            self.selection_label.config(text="No files selected.")
        else:
            self.selection_label.config(text=f"{len(self.selected_paths)} path(s) selected.")

    def run_batch(self):
        if not self.selected_paths:
            return
        for row in self.tree.get_children():
            self.tree.delete(row)
        self._row_reports = {}
        self.run_button.config(state="disabled")
        self.progress.config(value=0, maximum=1)
        self.status_label.config(text="Starting...")

        config = self.config_provider() if self.config_provider else None
        thread = threading.Thread(target=self._run_batch_worker, args=(config,), daemon=True)
        thread.start()
        self.after(100, self._poll_queue)

    def _run_batch_worker(self, config):
        def progress_cb(i, total, path):
            self._queue.put(("progress", i, total, path))

        batch = run_batch_qc(self.selected_paths, config=config, progress_callback=progress_cb)
        self._queue.put(("done", batch))

    def _poll_queue(self):
        try:
            while True:
                item = self._queue.get_nowait()
                if item[0] == "progress":
                    _, i, total, path = item
                    self.progress.config(value=i, maximum=max(total, 1))
                    self.status_label.config(text=f"Processing {i+1}/{total}: {os.path.basename(path)}")
                elif item[0] == "done":
                    self._on_batch_done(item[1])
        except queue.Empty:
            pass

        if self.run_button["state"] == "disabled":
            self.after(100, self._poll_queue)

    def _on_batch_done(self, batch):
        self._batch_result = batch
        for result in batch.results:
            if result.ok():
                tag = "has_critical" if result.report.critical_count() > 0 else ""
                values = (result.path, "OK", result.report.critical_count(), result.report.warning_count())
                self._row_reports[result.path] = result.report
            else:
                tag = "failed"
                values = (result.path, f"ERROR: {result.error}", "-", "-")
            self.tree.insert("", "end", values=values, tags=(tag,) if tag else ())

        self.status_label.config(
            text=f"Done: {batch.n_ok()} OK, {batch.n_failed()} failed, "
                 f"{batch.total_critical()} total critical issues"
        )
        self.progress.config(value=self.progress["maximum"])
        self.run_button.config(state="normal")

    def _on_row_double_click(self, event):
        item = self.tree.identify_row(event.y)
        if not item:
            return
        values = self.tree.item(item, "values")
        path = values[0]
        report = self._row_reports.get(path)
        if report and self.on_file_selected:
            self.on_file_selected(path, report)

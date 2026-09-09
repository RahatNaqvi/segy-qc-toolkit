"""
qc_panel.py
-----------
Displays a QCReport (from the existing segyqc.qc.run_qc) as a summary +
sortable issue table. Also wires up "open HTML report" and "export"
buttons - the report/export logic itself lives in report.py / export.py,
this panel just calls it.
"""

import os
import webbrowser
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from ..report import generate_html_report
from .export import export_csv, export_pdf


class QCResultsPanel(ttk.Frame):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.report = None
        self.segy_path = None

        top = ttk.Frame(self)
        top.pack(side="top", fill="x", padx=6, pady=4)
        self.summary_label = ttk.Label(top, text="No QC results yet.", font=("", 10, "bold"))
        self.summary_label.pack(side="left")

        btns = ttk.Frame(self)
        btns.pack(side="top", fill="x", padx=6, pady=(0, 4))
        ttk.Button(btns, text="Open HTML Report", command=self.open_html_report).pack(side="left", padx=(0, 6))
        ttk.Button(btns, text="Export CSV", command=self.export_csv_dialog).pack(side="left", padx=(0, 6))
        ttk.Button(btns, text="Export PDF", command=self.export_pdf_dialog).pack(side="left", padx=(0, 6))

        columns = ("trace", "category", "severity", "message")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=16)
        widths = (70, 120, 90, 500)
        for col, w in zip(columns, widths):
            self.tree.heading(col, text=col.title())
            self.tree.column(col, width=w, anchor="w")
        self.tree.tag_configure("critical", background="#fed7d7")
        self.tree.tag_configure("warning", background="#feebc8")
        self.tree.pack(side="top", fill="both", expand=True, padx=6, pady=(0, 6))

        self._html_report_path = None

    def show_report(self, report, segy_path):
        self.report = report
        self.segy_path = segy_path
        self._html_report_path = None

        self.summary_label.config(
            text=f"{os.path.basename(segy_path)} - {report.n_traces} traces - "
                 f"{report.critical_count()} critical, {report.warning_count()} warning"
        )

        for row in self.tree.get_children():
            self.tree.delete(row)
        for issue in sorted(report.issues, key=lambda i: i.severity != "critical"):
            tag = issue.severity if issue.severity in ("critical", "warning") else ""
            self.tree.insert("", "end", values=(issue.trace_index, issue.category, issue.severity, issue.message),
                              tags=(tag,) if tag else ())

    def open_html_report(self):
        if not self.report or not self.segy_path:
            messagebox.showinfo("No report", "Run QC on a file first.")
            return
        os.makedirs("outputs", exist_ok=True)
        out_path = os.path.abspath(os.path.join("outputs", "qc_report.html"))
        generate_html_report(self.report, self.segy_path, out_path=out_path)
        self._html_report_path = out_path
        webbrowser.open(f"file://{out_path}")

    def export_csv_dialog(self):
        if not self.report:
            messagebox.showinfo("No report", "Run QC on a file first.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if path:
            export_csv(self.report, path)
            messagebox.showinfo("Exported", f"Issues exported to {path}")

    def export_pdf_dialog(self):
        if not self.report:
            messagebox.showinfo("No report", "Run QC on a file first.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if path:
            export_pdf(self.report, path)
            messagebox.showinfo("Exported", f"Report exported to {path}")

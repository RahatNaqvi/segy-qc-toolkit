"""
export.py
---------
CSV and PDF export of a QCReport. Deliberately uses only what's already a
project dependency: the stdlib csv module, and matplotlib's PdfPages
(matplotlib is already required by report.py) - no new dependency added
for export.
"""

import csv
from datetime import datetime, timezone

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages


def export_csv(report, out_path):
    """Writes one row per QC issue, plus a leading summary row block."""
    with open(out_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["file", report.filename])
        writer.writerow(["n_traces", report.n_traces])
        writer.writerow(["n_samples", report.n_samples])
        writer.writerow(["critical_count", report.critical_count()])
        writer.writerow(["warning_count", report.warning_count()])
        writer.writerow([])
        writer.writerow(["trace_index", "category", "severity", "message"])
        for issue in report.issues:
            writer.writerow([issue.trace_index, issue.category, issue.severity, issue.message])
    return out_path


def export_pdf(report, out_path):
    """A compact PDF: one summary/text page, one RMS-by-trace plot page.
    Intentionally simple - the full-fidelity report is the HTML one;
    this covers the common "need a PDF to email/print" case."""
    stats = report.trace_stats or {}
    with PdfPages(out_path) as pdf:
        fig = plt.figure(figsize=(8.5, 11))
        fig.text(0.1, 0.95, "SEG-Y QC Report", fontsize=18, fontweight="bold")
        fig.text(0.1, 0.91, f"File: {report.filename}", fontsize=10)
        fig.text(0.1, 0.885, f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}", fontsize=10)
        fig.text(0.1, 0.85,
                  f"{report.n_traces} traces, {report.n_samples} samples/trace, {report.dt_ms} ms interval",
                  fontsize=10)
        fig.text(0.1, 0.81, f"Critical issues: {report.critical_count()}", fontsize=11, color="#c53030")
        fig.text(0.1, 0.785, f"Warning issues: {report.warning_count()}", fontsize=11, color="#b7791f")

        y = 0.74
        fig.text(0.1, y, "Issues:", fontsize=12, fontweight="bold")
        y -= 0.03
        for issue in sorted(report.issues, key=lambda i: i.severity != "critical")[:40]:
            line = f"[{issue.severity.upper()}] trace {issue.trace_index} ({issue.category}): {issue.message}"
            fig.text(0.1, y, line[:110], fontsize=7)
            y -= 0.018
            if y < 0.05:
                break
        plt.axis("off")
        pdf.savefig(fig)
        plt.close(fig)

        if "rms" in stats and len(stats["rms"]):
            fig2, ax = plt.subplots(figsize=(8.5, 4))
            ax.plot(stats["rms"], linewidth=0.6, color="#2b6cb0")
            dead = np.where(stats.get("is_dead", []))[0] if "is_dead" in stats else []
            if len(dead):
                ax.scatter(dead, np.zeros_like(dead), color="red", s=10, label="dead trace")
                ax.legend()
            ax.set_title("Trace RMS Amplitude")
            ax.set_xlabel("Trace index")
            ax.set_ylabel("RMS")
            pdf.savefig(fig2)
            plt.close(fig2)

    return out_path

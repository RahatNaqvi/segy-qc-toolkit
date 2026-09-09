"""
compare.py
----------
Before/after comparison between two QCReport objects (e.g. the same line
before and after a processing step, or two files from different vintages).
Pure comparison logic - no QC calculation happens here, it only reads
fields already computed by qc.run_qc.
"""

from dataclasses import dataclass
import numpy as np


@dataclass
class ComparisonRow:
    metric: str
    before: float
    after: float

    @property
    def delta(self):
        return self.after - self.before

    @property
    def pct_change(self):
        if self.before == 0:
            return float("inf") if self.after != 0 else 0.0
        return 100.0 * self.delta / self.before


def compare_reports(before, after):
    """before, after: QCReport instances (from qc.run_qc). Returns a list
    of ComparisonRow covering issue counts and key trace statistics."""
    rows = []

    rows.append(ComparisonRow("critical_issues", before.critical_count(), after.critical_count()))
    rows.append(ComparisonRow("warning_issues", before.warning_count(), after.warning_count()))
    rows.append(ComparisonRow("n_traces", before.n_traces, after.n_traces))

    b_stats = before.trace_stats or {}
    a_stats = after.trace_stats or {}

    if "rms" in b_stats and "rms" in a_stats and len(b_stats["rms"]) and len(a_stats["rms"]):
        rows.append(ComparisonRow("mean_rms", float(np.mean(b_stats["rms"])), float(np.mean(a_stats["rms"]))))
    if "peak" in b_stats and "peak" in a_stats and len(b_stats["peak"]) and len(a_stats["peak"]):
        rows.append(ComparisonRow("mean_peak", float(np.mean(b_stats["peak"])), float(np.mean(a_stats["peak"]))))
    if "is_dead" in b_stats and "is_dead" in a_stats:
        rows.append(ComparisonRow("dead_traces", int(np.sum(b_stats["is_dead"])), int(np.sum(a_stats["is_dead"]))))

    return rows

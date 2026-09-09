"""
batch.py
--------
Batch QC: find SEG-Y files across a set of paths (files and/or folders)
and run the existing qc.run_qc against each one in turn. No QC logic
lives here - this is purely file discovery + sequencing + a progress
callback hook for the GUI.
"""

import os
from dataclasses import dataclass, field

from .qc import run_qc, QCReport

SEGY_EXTENSIONS = (".sgy", ".segy", ".seg", ".sgy2")


@dataclass
class BatchFileResult:
    path: str
    report: QCReport = None
    error: str = None

    def ok(self):
        return self.error is None


@dataclass
class BatchResult:
    results: list = field(default_factory=list)

    def n_ok(self):
        return sum(1 for r in self.results if r.ok())

    def n_failed(self):
        return sum(1 for r in self.results if not r.ok())

    def total_critical(self):
        return sum(r.report.critical_count() for r in self.results if r.ok())

    def total_warning(self):
        return sum(r.report.warning_count() for r in self.results if r.ok())


def find_segy_files(paths):
    """paths: iterable of file or folder path strings. Returns a sorted,
    de-duplicated list of SEG-Y file paths (by extension)."""
    found = set()
    for p in paths:
        if os.path.isdir(p):
            for root, _dirs, files in os.walk(p):
                for name in files:
                    if name.lower().endswith(SEGY_EXTENSIONS):
                        found.add(os.path.join(root, name))
        elif os.path.isfile(p):
            if p.lower().endswith(SEGY_EXTENSIONS):
                found.add(p)
    return sorted(found)


def run_batch_qc(paths, config=None, progress_callback=None):
    """
    paths: list of file/folder paths.
    config: optional QCConfig, forwarded to run_qc for every file.
    progress_callback: optional callable(index, total, current_path)
                        invoked before processing each file - the GUI
                        uses this to update a progress bar/status label.
    Returns a BatchResult.
    """
    files = find_segy_files(paths)
    batch = BatchResult()

    for i, path in enumerate(files):
        if progress_callback:
            progress_callback(i, len(files), path)
        try:
            report = run_qc(path, config=config)
            batch.results.append(BatchFileResult(path=path, report=report))
        except Exception as e:
            batch.results.append(BatchFileResult(path=path, error=str(e)))

    return batch

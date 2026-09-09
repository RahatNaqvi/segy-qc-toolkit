#!/usr/bin/env python3
"""
run_qc.py
---------
Command-line entry point: run the QC suite on a SEG-Y file and produce an
HTML report. Unchanged from prior versions - this keeps working exactly
as before regardless of the GUI added alongside it.

Usage:
    python run_qc.py path/to/file.sgy [--out outputs/qc_report.html]
"""

import argparse
import sys

from segyqc.qc import run_qc
from segyqc.report import generate_html_report


def main():
    parser = argparse.ArgumentParser(description="Run QC on a SEG-Y file and generate an HTML report.")
    parser.add_argument("segy_path", help="Path to the input SEG-Y (.sgy) file")
    parser.add_argument("--out", default="outputs/qc_report.html", help="Output HTML report path")
    args = parser.parse_args()

    print(f"Running QC on {args.segy_path} ...")
    report = run_qc(args.segy_path)

    print(f"  Traces:   {report.n_traces}")
    print(f"  Samples:  {report.n_samples}")
    print(f"  Critical: {report.critical_count()}")
    print(f"  Warning:  {report.warning_count()}")

    out = generate_html_report(report, args.segy_path, out_path=args.out)
    print(f"Report written to: {out}")

    if report.critical_count() > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()

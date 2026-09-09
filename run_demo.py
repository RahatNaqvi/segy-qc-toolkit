#!/usr/bin/env python3
"""
run_demo.py
-----------
One-command demo: generates a synthetic SEG-Y line with injected QC issues,
runs the full QC suite, and produces an HTML report you can open in a browser.

Usage:
    python run_demo.py
"""

import os
from segyqc.synth_generator import generate_synthetic_line
from segyqc.qc import run_qc
from segyqc.report import generate_html_report


def main():
    os.makedirs("data", exist_ok=True)
    os.makedirs("outputs", exist_ok=True)

    print("Step 1/3: Generating synthetic SEG-Y line with injected QC issues...")
    segy_path = generate_synthetic_line(out_path="data/synthetic_line.sgy")

    print("Step 2/3: Running QC suite...")
    report = run_qc(segy_path)
    print(f"  -> {report.n_traces} traces, {report.critical_count()} critical, "
          f"{report.warning_count()} warning issues found")

    print("Step 3/3: Generating HTML report...")
    out_path = generate_html_report(report, segy_path, out_path="outputs/qc_report.html")

    print(f"\nDone. Open {out_path} in a browser to view the report.")


if __name__ == "__main__":
    main()

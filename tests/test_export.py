import os
import sys
import csv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from segyqc.synth_generator import generate_synthetic_line
from segyqc.qc import run_qc
from segyqc.gui.export import export_csv, export_pdf


def test_export_csv_contains_all_issues(tmp_path):
    segy_path = generate_synthetic_line(out_path=str(tmp_path / "line.sgy"))
    report = run_qc(segy_path)
    out_path = tmp_path / "report.csv"
    export_csv(report, str(out_path))

    assert out_path.exists()
    with open(out_path) as f:
        rows = list(csv.reader(f))
    # header rows + blank + column header + one row per issue
    issue_rows = [r for r in rows if len(r) == 4 and r[0].isdigit() or (len(r) == 4 and r[0] == "-1")]
    assert len(issue_rows) == len(report.issues)


def test_export_pdf_creates_valid_file(tmp_path):
    segy_path = generate_synthetic_line(out_path=str(tmp_path / "line.sgy"))
    report = run_qc(segy_path)
    out_path = tmp_path / "report.pdf"
    export_pdf(report, str(out_path))

    assert out_path.exists()
    with open(out_path, "rb") as f:
        header = f.read(5)
    assert header == b"%PDF-"

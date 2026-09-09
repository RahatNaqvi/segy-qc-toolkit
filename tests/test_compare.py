import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from segyqc.synth_generator import generate_synthetic_line
from segyqc.qc import run_qc
from segyqc.compare import compare_reports


def test_compare_identical_reports_has_zero_deltas(tmp_path):
    path = generate_synthetic_line(out_path=str(tmp_path / "line.sgy"), n_shots=3, n_receivers=10)
    r1 = run_qc(path)
    r2 = run_qc(path)
    rows = compare_reports(r1, r2)
    assert all(row.delta == 0 for row in rows)


def test_compare_different_files_shows_deltas(tmp_path):
    path_a = generate_synthetic_line(out_path=str(tmp_path / "a.sgy"), n_shots=3, n_receivers=10, seed=1)
    path_b = generate_synthetic_line(out_path=str(tmp_path / "b.sgy"), n_shots=5, n_receivers=10, seed=1)
    r1 = run_qc(path_a)
    r2 = run_qc(path_b)
    rows = compare_reports(r1, r2)
    trace_row = next(r for r in rows if r.metric == "n_traces")
    assert trace_row.before == 30
    assert trace_row.after == 50
    assert trace_row.delta == 20


def test_compare_pct_change_handles_zero_before(tmp_path):
    path = generate_synthetic_line(out_path=str(tmp_path / "line.sgy"), n_shots=2, n_receivers=10)
    r1 = run_qc(path)
    r2 = run_qc(path)
    rows = compare_reports(r1, r2)
    for row in rows:
        if row.before == 0 and row.after == 0:
            assert row.pct_change == 0.0

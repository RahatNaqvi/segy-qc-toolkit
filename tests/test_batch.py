import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from segyqc.synth_generator import generate_synthetic_line
from segyqc.batch import find_segy_files, run_batch_qc


def test_find_segy_files_in_folder(tmp_path):
    generate_synthetic_line(out_path=str(tmp_path / "a.sgy"), n_shots=2)
    generate_synthetic_line(out_path=str(tmp_path / "b.sgy"), n_shots=2)
    (tmp_path / "not_segy.txt").write_text("ignore me")
    found = find_segy_files([str(tmp_path)])
    assert len(found) == 2
    assert all(f.endswith(".sgy") for f in found)


def test_find_segy_files_mixed_files_and_folders(tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    generate_synthetic_line(out_path=str(tmp_path / "a.sgy"), n_shots=2)
    generate_synthetic_line(out_path=str(sub / "b.sgy"), n_shots=2)
    found = find_segy_files([str(tmp_path / "a.sgy"), str(sub)])
    assert len(found) == 2


def test_run_batch_qc_processes_all_files(tmp_path):
    generate_synthetic_line(out_path=str(tmp_path / "a.sgy"), n_shots=2, n_receivers=10)
    generate_synthetic_line(out_path=str(tmp_path / "b.sgy"), n_shots=2, n_receivers=10)
    batch = run_batch_qc([str(tmp_path)])
    assert batch.n_ok() == 2
    assert batch.n_failed() == 0
    assert all(r.report is not None for r in batch.results)


def test_run_batch_qc_progress_callback_invoked(tmp_path):
    generate_synthetic_line(out_path=str(tmp_path / "a.sgy"), n_shots=2, n_receivers=10)
    calls = []
    run_batch_qc([str(tmp_path)], progress_callback=lambda i, total, path: calls.append((i, total, path)))
    assert len(calls) == 1
    assert calls[0][1] == 1


def test_run_batch_qc_handles_bad_file_gracefully(tmp_path):
    bad_path = tmp_path / "corrupt.sgy"
    bad_path.write_bytes(b"not a real segy file")
    batch = run_batch_qc([str(tmp_path)])
    assert batch.n_failed() == 1
    assert batch.results[0].error is not None

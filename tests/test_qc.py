import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from segyqc.synth_generator import generate_synthetic_line
from segyqc.qc import run_qc


@pytest.fixture(scope="module")
def synthetic_segy(tmp_path_factory):
    out_dir = tmp_path_factory.mktemp("data")
    path = generate_synthetic_line(out_path=str(out_dir / "test_line.sgy"))
    return path


@pytest.fixture(scope="module")
def report(synthetic_segy):
    return run_qc(synthetic_segy)


def test_trace_and_sample_counts(report):
    assert report.n_traces == 20 * 48
    assert report.n_samples == 1000


def test_dead_trace_detected(report):
    dead_issues = [i for i in report.issues if "Dead trace" in i.message]
    assert len(dead_issues) == 1
    assert dead_issues[0].trace_index == 300


def test_spiked_trace_detected(report):
    spike_issues = [i for i in report.issues if "spike" in i.message.lower()]
    assert len(spike_issues) == 1
    assert spike_issues[0].trace_index == 550


def test_duplicate_shot_point_detected(report):
    dup_issues = [i for i in report.issues if "duplicate/merged SP" in i.message]
    assert len(dup_issues) == 1
    assert dup_issues[0].category == "shot_sequence"


def test_shot_point_gap_detected(report):
    gap_issues = [i for i in report.issues if "Gap in shot point numbering" in i.message]
    assert len(gap_issues) == 1


def test_no_geometry_checks_present(report):
    # Geometry/coordinate QC was intentionally removed from this toolkit -
    # regression test to make sure it doesn't quietly come back.
    geometry_issues = [i for i in report.issues if i.category == "geometry"]
    assert len(geometry_issues) == 0
    assert not any("geometry bust" in i.message for i in report.issues)


def test_no_false_positive_flood(report):
    assert len(report.issues) < 10

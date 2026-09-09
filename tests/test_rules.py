import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
import numpy as np
from segyqc.synth_generator import generate_synthetic_line
from segyqc.qc import run_qc
from segyqc.rules import QCConfig


@pytest.fixture(scope="module")
def synthetic_segy(tmp_path_factory):
    out_dir = tmp_path_factory.mktemp("data")
    return generate_synthetic_line(out_path=str(out_dir / "test_line.sgy"))


def test_default_config_matches_no_config(synthetic_segy):
    r1 = run_qc(synthetic_segy)
    r2 = run_qc(synthetic_segy, config=QCConfig())
    assert r1.critical_count() == r2.critical_count()
    assert r1.warning_count() == r2.warning_count()


def test_disabling_spike_check_removes_spike_issues(synthetic_segy):
    config = QCConfig(enable_spike_check=False)
    report = run_qc(synthetic_segy, config=config)
    assert not any("spike" in i.message.lower() for i in report.issues)


def test_disabling_dead_trace_check_removes_dead_issues(synthetic_segy):
    config = QCConfig(enable_dead_trace_check=False)
    report = run_qc(synthetic_segy, config=config)
    assert not any("Dead trace" in i.message for i in report.issues)


def test_disabling_shot_sequence_check(synthetic_segy):
    config = QCConfig(enable_shot_sequence_check=False)
    report = run_qc(synthetic_segy, config=config)
    assert not any(i.category == "shot_sequence" for i in report.issues)


def test_spike_threshold_is_configurable(synthetic_segy):
    strict = run_qc(synthetic_segy, config=QCConfig(spike_z_threshold=1.0))
    lenient = run_qc(synthetic_segy, config=QCConfig(spike_z_threshold=50.0))
    strict_spikes = sum(1 for i in strict.issues if "spike" in i.message.lower())
    lenient_spikes = sum(1 for i in lenient.issues if "spike" in i.message.lower())
    assert strict_spikes >= lenient_spikes


def test_config_roundtrip_save_load(tmp_path):
    config = QCConfig(enable_spike_check=False, spike_z_threshold=4.5)
    path = tmp_path / "config.json"
    config.save(str(path))
    loaded = QCConfig.load(str(path))
    assert loaded.enable_spike_check is False
    assert loaded.spike_z_threshold == 4.5


def test_snr_check_flags_low_snr_trace(tmp_path):
    import segyio
    import numpy as np

    path = generate_synthetic_line(out_path=str(tmp_path / "line.sgy"), n_shots=3, n_receivers=10)
    with segyio.open(path, ignore_geometry=True, mode="r+") as f:
        n_samples = len(f.samples)
        rng = np.random.default_rng(1)
        f.trace[5] = rng.normal(0, 0.03, n_samples).astype(np.float32)

    report = run_qc(path)
    snr_issues = [i for i in report.issues if i.category == "signal_quality"]
    assert len(snr_issues) == 1
    assert snr_issues[0].trace_index == 5


def test_snr_check_disableable(tmp_path):
    import segyio
    import numpy as np

    path = generate_synthetic_line(out_path=str(tmp_path / "line.sgy"), n_shots=3, n_receivers=10)
    with segyio.open(path, ignore_geometry=True, mode="r+") as f:
        n_samples = len(f.samples)
        rng = np.random.default_rng(1)
        f.trace[5] = rng.normal(0, 0.03, n_samples).astype(np.float32)

    report = run_qc(path, config=QCConfig(enable_snr_check=False))
    assert not any(i.category == "signal_quality" for i in report.issues)
    assert "snr" not in report.trace_stats or np.all(np.isnan(report.trace_stats["snr"]))


def test_snr_threshold_is_configurable(tmp_path):
    path = generate_synthetic_line(out_path=str(tmp_path / "line.sgy"), n_shots=3, n_receivers=10)
    strict = run_qc(path, config=QCConfig(snr_low_threshold=100.0))
    lenient = run_qc(path, config=QCConfig(snr_low_threshold=0.01))
    strict_issues = sum(1 for i in strict.issues if i.category == "signal_quality")
    lenient_issues = sum(1 for i in lenient.issues if i.category == "signal_quality")
    assert strict_issues >= lenient_issues

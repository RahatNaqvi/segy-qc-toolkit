"""
qc.py
-----
Core SEG-Y QC routines: header validation, amplitude statistics, and
shot-point sequence checks. Designed to be readable and extensible rather
than exhaustive - it mirrors the kind of first-pass QC a processing
geophysicist runs before geometry merge / binning.

Note: coordinate/geometry QC (source-receiver coordinate bounds, bust
detection) has been intentionally removed from this toolkit - it now
lives in the separate geometry-qc-toolkit, which operates on
geometry-loaded data. This toolkit focuses on pure trace/header QC that
is meaningful even on raw, pre-geometry field tapes.
"""

from dataclasses import dataclass, field
from collections import Counter
import numpy as np
import segyio
from segyio import TraceField

from .rules import QCConfig


@dataclass
class QCIssue:
    category: str
    severity: str  # "info" | "warning" | "critical"
    trace_index: int
    message: str


@dataclass
class QCReport:
    filename: str
    n_traces: int
    n_samples: int
    dt_ms: float
    issues: list = field(default_factory=list)
    trace_stats: dict = field(default_factory=dict)

    def add(self, category, severity, trace_index, message):
        self.issues.append(QCIssue(category, severity, trace_index, message))

    def summary_counts(self):
        return Counter((i.category, i.severity) for i in self.issues)

    def critical_count(self):
        return sum(1 for i in self.issues if i.severity == "critical")

    def warning_count(self):
        return sum(1 for i in self.issues if i.severity == "warning")


def run_qc(segy_path, coord_bounds=None, config=None):
    """
    Run the QC suite on a SEG-Y file and return a QCReport.

    coord_bounds: deprecated / unused (kept only so old call sites that
    passed it positionally or by keyword don't break). Geometry/coordinate
    QC no longer lives in this toolkit.
    config: optional QCConfig controlling which checks run and their
    thresholds. Defaults to QCConfig() (all checks on, default thresholds)
    when not supplied, so existing calls to run_qc(path) behave exactly
    as before.
    """
    config = config or QCConfig()

    with segyio.open(segy_path, ignore_geometry=True) as f:
        n_traces = f.tracecount
        n_samples = len(f.samples)
        dt_ms = segyio.tools.dt(f) / 1000.0

        report = QCReport(
            filename=str(segy_path),
            n_traces=n_traces,
            n_samples=n_samples,
            dt_ms=dt_ms,
        )

        fields = f.attributes(TraceField.FieldRecord)[:]
        offsets = f.attributes(TraceField.offset)[:]

        rms = np.zeros(n_traces)
        peak = np.zeros(n_traces)
        is_dead = np.zeros(n_traces, dtype=bool)
        snr = np.full(n_traces, np.nan)

        noise_end_sample = max(1, int(n_samples * config.snr_noise_window_fraction))

        for i in range(n_traces):
            tr = f.trace[i]
            rms[i] = np.sqrt(np.mean(tr.astype(np.float64) ** 2))
            peak[i] = np.max(np.abs(tr))
            is_dead[i] = np.allclose(tr, 0.0)

            if config.enable_snr_check and n_samples > noise_end_sample:
                noise_win = tr[:noise_end_sample].astype(np.float64)
                signal_win = tr[noise_end_sample:].astype(np.float64)
                noise_rms = np.sqrt(np.mean(noise_win ** 2))
                signal_rms = np.sqrt(np.mean(signal_win ** 2))
                if noise_rms > 0:
                    snr[i] = signal_rms / noise_rms

        report.trace_stats = {
            "rms": rms,
            "peak": peak,
            "is_dead": is_dead,
            "field_record": fields,
            "offset": offsets,
            "snr": snr,
        }

        if config.enable_dead_trace_check or config.enable_spike_check:
            _check_dead_and_spiked_traces(report, rms, peak, config)
        if config.enable_shot_sequence_check:
            _check_shot_point_sequence(report, fields, config)
        if config.enable_sample_consistency_check:
            _check_sampling_consistency(f, report)
        if config.enable_snr_check:
            _check_signal_to_noise(report, snr, is_dead, config)

    return report


def _check_dead_and_spiked_traces(report, rms, peak, config):
    if config.enable_dead_trace_check:
        dead_idx = np.where(rms == 0.0)[0]
        for i in dead_idx:
            report.add("amplitude", "critical", int(i), "Dead trace (zero amplitude)")

    if not config.enable_spike_check:
        return

    nonzero_rms = rms[rms > 0]
    if len(nonzero_rms) <= 1:
        return

    # Real seismic amplitude distributions are heavy-tailed, not Gaussian -
    # a plain mean/std z-score is not robust to that and can flood the
    # report with false positives on real field data. Use a robust
    # (median/MAD-based) z-score instead.
    median_rms = np.median(nonzero_rms)
    mad = np.median(np.abs(nonzero_rms - median_rms))
    robust_std = mad * 1.4826  # MAD-to-std conversion for normal data
    if robust_std > 0:
        robust_z = (rms - median_rms) / robust_std
        spike_idx = np.where(robust_z > config.spike_z_threshold)[0]
        for i in spike_idx:
            report.add(
                "amplitude", "warning", int(i),
                f"Anomalously high RMS amplitude (robust z={robust_z[i]:.1f}) - "
                f"possible spike/noise burst",
            )


def _check_shot_point_sequence(report, fields, config):
    fields = np.asarray(fields)
    unique_sp, counts = np.unique(fields, return_counts=True)

    typical_block = np.median(counts)
    for sp, cnt in zip(unique_sp, counts):
        if cnt >= typical_block * config.duplicate_sp_multiplier:
            first_idx = int(np.where(fields == sp)[0][0])
            report.add(
                "shot_sequence", "critical", first_idx,
                f"Shot point {sp} has {cnt} traces (expected ~{typical_block:.0f}) - "
                f"likely duplicate/merged SP number",
            )

    sorted_sp = np.sort(unique_sp)
    diffs = np.diff(sorted_sp)
    if len(diffs):
        typical_step = np.median(diffs)
        gap_locs = np.where(diffs > typical_step * config.sp_gap_multiplier)[0]
        for g in gap_locs:
            report.add(
                "shot_sequence", "warning", -1,
                f"Gap in shot point numbering between SP {sorted_sp[g]} and SP {sorted_sp[g+1]} "
                f"(expected step ~{typical_step:.0f})",
            )


def _check_signal_to_noise(report, snr, is_dead, config):
    """S/N proxy that needs no geometry or velocity model: ratio of RMS
    in the back part of the trace (assumed signal-bearing) to RMS in the
    first snr_noise_window_fraction of the record (assumed noise-
    dominated, i.e. before useful energy typically arrives). This is a
    coarse field-QC heuristic, not a substitute for a proper S/N estimate
    with picked first breaks - it's meant to flag traces worth a closer
    look, not to make a final call.
    """
    valid = ~np.isnan(snr) & ~is_dead
    low_idx = np.where(valid & (snr < config.snr_low_threshold))[0]
    for i in low_idx:
        report.add(
            "signal_quality", "warning", int(i),
            f"Low signal-to-noise ratio (S/N={snr[i]:.1f}, threshold={config.snr_low_threshold}) - "
            f"signal window is not much stronger than the early/noise window",
        )


def _check_sampling_consistency(f, report):
    sample_counts = f.attributes(TraceField.TRACE_SAMPLE_COUNT)[:]
    expected = len(f.samples)
    bad = np.where(sample_counts != expected)[0]
    for i in bad:
        report.add(
            "header", "critical", int(i),
            f"Trace sample count ({sample_counts[i]}) does not match file sample count ({expected})",
        )

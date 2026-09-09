"""
synth_generator.py
-------------------
Generates small, fully synthetic SEG-Y datasets for testing/demoing the
QC toolkit. No real/proprietary field data is used or required anywhere
in this project.
"""

import numpy as np
import segyio
from segyio import TraceField, BinField


def _ricker(f, length, dt):
    t = np.arange(-length / 2, length / 2, dt)
    y = (1.0 - 2.0 * (np.pi ** 2) * (f ** 2) * (t ** 2)) * np.exp(
        -(np.pi ** 2) * (f ** 2) * (t ** 2)
    )
    return y


def generate_synthetic_line(
    out_path="data/synthetic_line.sgy",
    n_shots=20,
    n_receivers=48,
    n_samples=1000,
    dt_ms=2,
    receiver_spacing_m=25,
    shot_spacing_m=50,
    seed=42,
):
    """Synthetic 2D line with 5 deliberately injected QC issues: a dead
    trace, a spiked trace, a duplicate SP, and a gap in SP numbering.
    (Coordinate/geometry issues are no longer injected here - geometry QC
    moved to the separate geometry-qc-toolkit.)
    """
    rng = np.random.default_rng(seed)
    dt = dt_ms / 1000.0
    wavelet = _ricker(f=30, length=0.2, dt=dt)

    total_traces = n_shots * n_receivers

    spec = segyio.spec()
    spec.samples = np.arange(n_samples) * dt_ms
    spec.format = 1
    spec.tracecount = total_traces

    with segyio.create(out_path, spec) as f:
        trace_idx = 0
        sp_numbers = list(range(1001, 1001 + n_shots))
        # Only inject the SP-gap / duplicate-SP issues when there's enough
        # shots for them to make sense - smaller synthetic files (used by
        # batch/compare tests where the specific issues don't matter) skip
        # these rather than indexing out of range.
        if n_shots > 10:
            sp_numbers[10] += 5
        if n_shots > 15:
            sp_numbers[15] = sp_numbers[14]

        dead_trace_global_idx = 300 if total_traces > 300 else -1
        spike_trace_global_idx = 550 if total_traces > 550 else -1

        for shot_i in range(n_shots):
            sp = sp_numbers[shot_i]
            src_x = 1000 + shot_i * shot_spacing_m

            for rec_i in range(n_receivers):
                rec_x = src_x - (n_receivers / 2) * receiver_spacing_m + rec_i * receiver_spacing_m
                offset = int(rec_x - src_x)

                trace = np.zeros(n_samples, dtype=np.float32)
                reflector_times = [0.15, 0.35, 0.55, 0.75]
                for rt in reflector_times:
                    idx = int(rt / dt)
                    amp = 1.0 / (1.0 + abs(offset) / 2000.0)
                    if idx < n_samples:
                        end = min(n_samples, idx + len(wavelet))
                        trace[idx:end] += (amp * wavelet[: end - idx]).astype(np.float32)
                trace += rng.normal(0, 0.02, n_samples).astype(np.float32)

                if trace_idx == dead_trace_global_idx:
                    trace[:] = 0.0
                if trace_idx == spike_trace_global_idx:
                    trace[n_samples // 2] += 500.0

                f.trace[trace_idx] = trace
                f.header[trace_idx] = {
                    TraceField.FieldRecord: sp,
                    TraceField.TraceNumber: rec_i + 1,
                    TraceField.offset: offset,
                    TraceField.TRACE_SAMPLE_COUNT: n_samples,
                    TraceField.TRACE_SAMPLE_INTERVAL: dt_ms * 1000,
                }
                trace_idx += 1

        f.bin[BinField.Interval] = dt_ms * 1000
        f.bin[BinField.Samples] = n_samples

    return out_path


def generate_raw_field_tape(
    out_path="data/raw_no_geometry.sgy", n_shots=5, n_receivers=48,
    n_samples=500, dt_ms=2, seed=3,
):
    """A synthetic file simulating a genuinely raw field tape: no
    geometry populated at all. Useful for testing that the toolkit
    behaves sensibly on pre-geometry data (it no longer runs any
    geometry-specific checks at all, by design)."""
    rng = np.random.default_rng(seed)
    total_traces = n_shots * n_receivers
    spec = segyio.spec()
    spec.samples = np.arange(n_samples) * dt_ms
    spec.format = 1
    spec.tracecount = total_traces
    with segyio.create(out_path, spec) as f:
        idx = 0
        for shot_i in range(n_shots):
            for rec_i in range(n_receivers):
                trace = rng.normal(0, 0.05, n_samples).astype(np.float32)
                f.trace[idx] = trace
                f.header[idx] = {
                    TraceField.FieldRecord: 2001 + shot_i,
                    TraceField.TraceNumber: rec_i + 1,
                    TraceField.TRACE_SAMPLE_COUNT: n_samples,
                    TraceField.TRACE_SAMPLE_INTERVAL: dt_ms * 1000,
                }
                idx += 1
        f.bin[BinField.Interval] = dt_ms * 1000
        f.bin[BinField.Samples] = n_samples
    return out_path


if __name__ == "__main__":
    path = generate_synthetic_line()
    print(f"Synthetic SEG-Y written to: {path}")
    print("Injected QC issues: 1 dead trace, 1 spiked trace, 1 duplicate SP, 1 SP gap.")

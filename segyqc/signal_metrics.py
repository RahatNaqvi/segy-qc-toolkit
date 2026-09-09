"""
signal_metrics.py
------------------
Pure signal-processing functions with no segyio/Tkinter dependency, so
they're trivially unit-testable. Used by the trace viewer (for the
frequency-of-selection feature and AGC display) and available to qc.py
if a frequency-based check is added later.
"""

import numpy as np


def dominant_frequency(trace, dt_s):
    """Returns the frequency (Hz) of the largest non-DC component in the
    trace's amplitude spectrum. dt_s is the sample interval in seconds."""
    trace = np.asarray(trace, dtype=np.float64)
    n = len(trace)
    if n < 2 or dt_s <= 0:
        return 0.0
    spectrum = np.abs(np.fft.rfft(trace))
    freqs = np.fft.rfftfreq(n, d=dt_s)
    if len(spectrum) <= 1:
        return 0.0
    idx = int(np.argmax(spectrum[1:])) + 1  # skip DC (index 0)
    return float(freqs[idx])


def average_spectrum(traces, dt_s):
    """traces: 2D array (n_traces x n_samples). Returns (freqs, amplitude)
    for the average amplitude spectrum across all given traces."""
    traces = np.asarray(traces, dtype=np.float64)
    if traces.ndim == 1:
        traces = traces[np.newaxis, :]
    n_samples = traces.shape[1]
    freqs = np.fft.rfftfreq(n_samples, d=dt_s)
    spectra = np.abs(np.fft.rfft(traces, axis=1))
    return freqs, spectra.mean(axis=0)


def apply_agc(trace, window_samples, stabilize_fraction=0.01):
    """Automatic Gain Control via sliding-window RMS normalization.
    Each sample is divided by the local RMS computed in a centered window
    of window_samples, so weak late-time signal becomes visible at the
    same displayed amplitude as strong early arrivals. stabilize_fraction
    adds a small epsilon (relative to the window RMS's own peak) to avoid
    dividing by near-zero in quiet stretches, which would otherwise blow
    up noise."""
    trace = np.asarray(trace, dtype=np.float64)
    n = len(trace)
    window_samples = max(1, int(window_samples))
    if n == 0:
        return trace

    sq = trace ** 2
    kernel = np.ones(window_samples) / window_samples
    local_ms = np.convolve(sq, kernel, mode="same")
    local_rms = np.sqrt(local_ms)

    peak_rms = np.max(local_rms) if np.max(local_rms) > 0 else 1.0
    eps = stabilize_fraction * peak_rms
    return trace / (local_rms + eps)


def apply_manual_gain(trace, gain):
    return np.asarray(trace, dtype=np.float64) * gain

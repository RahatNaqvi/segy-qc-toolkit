import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
from segyqc.signal_metrics import dominant_frequency, average_spectrum, apply_agc, apply_manual_gain


def test_dominant_frequency_pure_sine():
    dt_s = 0.001  # 1 ms sample interval -> 1000 Hz Nyquist
    t = np.arange(0, 1.0, dt_s)
    freq_true = 40.0
    trace = np.sin(2 * np.pi * freq_true * t)
    detected = dominant_frequency(trace, dt_s)
    # FFT bin resolution over 1 second of data is 1 Hz - should be exact
    assert abs(detected - freq_true) <= 1.0


def test_dominant_frequency_picks_larger_amplitude_component():
    dt_s = 0.001
    t = np.arange(0, 1.0, dt_s)
    # low-amplitude 20 Hz + high-amplitude 150 Hz -> should detect 150
    trace = 0.1 * np.sin(2 * np.pi * 20 * t) + 5.0 * np.sin(2 * np.pi * 150 * t)
    detected = dominant_frequency(trace, dt_s)
    assert abs(detected - 150.0) <= 1.0


def test_dominant_frequency_handles_empty_or_degenerate_input():
    assert dominant_frequency([], 0.001) == 0.0
    assert dominant_frequency([1.0], 0.001) == 0.0
    assert dominant_frequency([1.0, 2.0], 0) == 0.0  # dt_s <= 0 guarded


def test_average_spectrum_shape_and_peak(): 
    dt_s = 0.001
    t = np.arange(0, 1.0, dt_s)
    traces = np.array([np.sin(2 * np.pi * 60 * t) for _ in range(5)])
    freqs, amp = average_spectrum(traces, dt_s)
    assert len(freqs) == len(amp)
    peak_freq = freqs[np.argmax(amp[1:]) + 1]
    assert abs(peak_freq - 60.0) <= 1.0


def test_agc_flattens_amplitude_envelope():
    n = 2000
    trace = np.zeros(n)
    trace[100:150] = 10.0    # strong early burst
    trace[1500:1550] = 0.1   # weak late burst
    agc = apply_agc(trace, window_samples=100)
    # After AGC, the weak late burst should be much more comparable in
    # amplitude to the strong early burst than it was originally.
    original_ratio = np.max(np.abs(trace[100:150])) / np.max(np.abs(trace[1500:1550]))
    agc_ratio = np.max(np.abs(agc[100:150])) / np.max(np.abs(agc[1500:1550]))
    assert agc_ratio < original_ratio / 5


def test_agc_handles_all_zero_trace_without_error():
    trace = np.zeros(500)
    result = apply_agc(trace, window_samples=50)
    assert len(result) == 500
    assert np.all(np.isfinite(result))


def test_manual_gain_scales_linearly():
    trace = np.array([1.0, -2.0, 3.0])
    result = apply_manual_gain(trace, 2.5)
    assert np.allclose(result, [2.5, -5.0, 7.5])

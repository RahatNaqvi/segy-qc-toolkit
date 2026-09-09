"""
trace_viewer.py
----------------
Interactive trace display, embedded in Tkinter via matplotlib's
FigureCanvasTkAgg. Reads traces directly with segyio - no QC logic here,
this is pure visualization (gain/AGC/display-mode math lives in
signal_metrics.py so it's unit-testable without a display).

Display modes: wiggle, variable-area (VA), wiggle+VA, and variable
density (VD) - the flooded-color display most QC geophysicists actually
use for scanning a shot quickly, rather than sparse wiggle traces alone.

Gain modes: none (raw, percentile-scaled), manual gain multiplier, or
AGC (sliding-window RMS normalization) - so weak late-time signal is
visible without clipping the strong early arrivals.

A "Frequency of selection" panel computes and shows the average
amplitude spectrum of whatever trace range is currently displayed, so a
processing geophysicist can quickly check the frequency content of a
particular part of a shot rather than only the whole-file average shown
in the HTML report.
"""

import tkinter as tk
from tkinter import ttk

import numpy as np
import segyio
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

from ..signal_metrics import apply_agc, apply_manual_gain, average_spectrum


class TraceViewerFrame(ttk.Frame):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.segy_path = None
        self.n_traces = 0
        self.n_samples = 0
        self.dt_ms = 2.0

        self._build_controls()
        self._build_plot_area()

    # ---------------- Controls ----------------

    def _build_controls(self):
        controls = ttk.Frame(self)
        controls.pack(side="top", fill="x", padx=6, pady=4)

        ttk.Label(controls, text="Start trace:").pack(side="left")
        self.start_var = tk.IntVar(value=0)
        self.start_spin = ttk.Spinbox(controls, from_=0, to=0, width=7, textvariable=self.start_var,
                                       command=self.redraw)
        self.start_spin.pack(side="left", padx=(2, 10))

        ttk.Label(controls, text="Count:").pack(side="left")
        self.count_var = tk.IntVar(value=20)
        self.count_spin = ttk.Spinbox(controls, from_=1, to=500, width=6, textvariable=self.count_var,
                                       command=self.redraw)
        self.count_spin.pack(side="left", padx=(2, 10))

        ttk.Label(controls, text="Display:").pack(side="left")
        self.mode_var = tk.StringVar(value="Variable Density")
        mode_box = ttk.Combobox(controls, textvariable=self.mode_var, width=16, state="readonly",
                                 values=["wiggle", "VA", "wiggle+VA", "Variable Density"])
        mode_box.pack(side="left", padx=(2, 10))
        mode_box.bind("<<ComboboxSelected>>", lambda e: self.redraw())

        ttk.Label(controls, text="Gain:").pack(side="left")
        self.gain_mode_var = tk.StringVar(value="None")
        gain_box = ttk.Combobox(controls, textvariable=self.gain_mode_var, width=10, state="readonly",
                                 values=["None", "Manual", "AGC"])
        gain_box.pack(side="left", padx=(2, 6))
        gain_box.bind("<<ComboboxSelected>>", lambda e: self.redraw())

        ttk.Label(controls, text="x").pack(side="left")
        self.gain_value_var = tk.DoubleVar(value=1.0)
        ttk.Spinbox(controls, from_=0.1, to=50.0, increment=0.1, width=6,
                    textvariable=self.gain_value_var, command=self.redraw).pack(side="left", padx=(2, 6))

        ttk.Label(controls, text="AGC window (ms):").pack(side="left")
        self.agc_window_var = tk.IntVar(value=200)
        ttk.Spinbox(controls, from_=10, to=2000, increment=10, width=7,
                    textvariable=self.agc_window_var, command=self.redraw).pack(side="left", padx=(2, 10))

        ttk.Button(controls, text="Redraw", command=self.redraw).pack(side="left", padx=(0, 10))

        controls2 = ttk.Frame(self)
        controls2.pack(side="top", fill="x", padx=6, pady=(0, 4))
        self.show_spectrum_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(controls2, text="Show frequency spectrum of current selection",
                         variable=self.show_spectrum_var, command=self.redraw).pack(side="left")

        self.status_label = ttk.Label(controls2, text="No file loaded")
        self.status_label.pack(side="left", padx=10)

    def _build_plot_area(self):
        self.fig = Figure(figsize=(8, 5), dpi=100)
        self.ax_trace = self.fig.add_subplot(111)
        self.ax_spectrum = None  # created on demand when spectrum view is toggled on

        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(side="top", fill="both", expand=True)
        toolbar = NavigationToolbar2Tk(self.canvas, self, pack_toolbar=False)
        toolbar.update()
        toolbar.pack(side="bottom", fill="x")

    # ---------------- File loading ----------------

    def load_file(self, segy_path):
        self.segy_path = segy_path
        with segyio.open(segy_path, ignore_geometry=True) as f:
            self.n_traces = f.tracecount
            self.n_samples = len(f.samples)
            self.dt_ms = segyio.tools.dt(f) / 1000.0
        self.start_spin.config(to=max(0, self.n_traces - 1))
        self.start_var.set(0)
        self.status_label.config(text=f"{self.n_traces} traces, {self.n_samples} samples, {self.dt_ms} ms")
        self.redraw()

    # ---------------- Gain application ----------------

    def _apply_gain(self, traces):
        mode = self.gain_mode_var.get()
        if mode == "Manual":
            return np.array([apply_manual_gain(tr, self.gain_value_var.get()) for tr in traces])
        if mode == "AGC":
            window_samples = max(1, int(self.agc_window_var.get() / self.dt_ms))
            return np.array([apply_agc(tr, window_samples) for tr in traces])
        return traces

    # ---------------- Drawing ----------------

    def redraw(self):
        self.fig.clear()
        want_spectrum = self.show_spectrum_var.get()

        if want_spectrum:
            self.ax_trace = self.fig.add_subplot(211)
            self.ax_spectrum = self.fig.add_subplot(212)
        else:
            self.ax_trace = self.fig.add_subplot(111)
            self.ax_spectrum = None

        if not self.segy_path or self.n_traces == 0:
            self.ax_trace.set_title("No file loaded")
            self.canvas.draw()
            return

        start = max(0, min(self.start_var.get(), self.n_traces - 1))
        count = max(1, min(self.count_var.get(), self.n_traces - start))
        mode = self.mode_var.get()

        with segyio.open(self.segy_path, ignore_geometry=True) as f:
            raw_traces = np.array([f.trace[i] for i in range(start, start + count)])

        if raw_traces.size == 0:
            self.canvas.draw()
            return

        traces = self._apply_gain(raw_traces)
        t_axis = np.arange(self.n_samples) * self.dt_ms / 1000.0  # seconds

        if mode == "Variable Density":
            self._draw_variable_density(traces, t_axis, start, count)
        else:
            self._draw_wiggle_va(traces, t_axis, start, count, mode)

        if want_spectrum:
            self._draw_spectrum(raw_traces, start, count)

        self.fig.tight_layout()
        self.canvas.draw()

    def _draw_wiggle_va(self, traces, t_axis, start, count, mode):
        scale = np.percentile(np.abs(traces), 98) or 1.0
        for i, tr in enumerate(traces):
            trace_norm = tr / scale
            x = i + trace_norm
            if mode in ("VA", "wiggle+VA"):
                self.ax_trace.fill_betweenx(t_axis, i, x, where=(x > i), color="black", linewidth=0)
            if mode in ("wiggle", "wiggle+VA"):
                self.ax_trace.plot(x, t_axis, color="black", linewidth=0.4)

        self.ax_trace.invert_yaxis()
        self.ax_trace.set_xlabel("Trace index (offset within window)")
        self.ax_trace.set_ylabel("Time (s)")
        self.ax_trace.set_title(f"Traces {start} to {start + count - 1}  [{mode}]")
        self.ax_trace.set_xlim(-1, count)

    def _draw_variable_density(self, traces, t_axis, start, count):
        # traces: (count, n_samples) -> display as (n_samples, count) so
        # time runs down the vertical axis, matching conventional seismic
        # display orientation.
        data = traces.T
        vmax = np.percentile(np.abs(data), 98) or 1.0
        im = self.ax_trace.imshow(
            data, aspect="auto", cmap="seismic", vmin=-vmax, vmax=vmax,
            extent=[start, start + count, t_axis[-1], t_axis[0]],
        )
        self.ax_trace.set_xlabel("Trace index")
        self.ax_trace.set_ylabel("Time (s)")
        self.ax_trace.set_title(f"Traces {start} to {start + count - 1}  [Variable Density]")
        self.fig.colorbar(im, ax=self.ax_trace, fraction=0.03, pad=0.02)

    def _draw_spectrum(self, raw_traces, start, count):
        dt_s = self.dt_ms / 1000.0
        freqs, amp = average_spectrum(raw_traces, dt_s)
        self.ax_spectrum.plot(freqs, amp, color="#c05621")
        self.ax_spectrum.set_title(f"Average Amplitude Spectrum - traces {start} to {start + count - 1}")
        self.ax_spectrum.set_xlabel("Frequency (Hz)")
        self.ax_spectrum.set_ylabel("Amplitude")
        if len(freqs):
            self.ax_spectrum.set_xlim(0, freqs.max())

"""
report.py
---------
Generates a self-contained HTML QC report from a QCReport object, with
embedded plots (base64 PNG) so the whole thing is a single portable file -
easy to attach to an email or open in any browser without a server.
"""

import base64
import io
from datetime import datetime, timezone

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import segyio


def _fig_to_base64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def _plot_rms_by_trace(stats):
    fig, ax = plt.subplots(figsize=(9, 3))
    ax.plot(stats["rms"], linewidth=0.6, color="#2b6cb0")
    dead = np.where(stats["is_dead"])[0]
    if len(dead):
        ax.scatter(dead, np.zeros_like(dead), color="red", s=15, label="dead trace", zorder=5)
        ax.legend(loc="upper right", fontsize=8)
    ax.set_title("Trace RMS Amplitude")
    ax.set_xlabel("Trace index")
    ax.set_ylabel("RMS")
    return _fig_to_base64(fig)


def _plot_traces_per_shot(stats):
    """Renamed from the old 'Fold per Shot Point' - this is a trace-count
    check (are all shots recording the expected number of channels?), not
    real CMP fold, which requires binned geometry this toolkit no longer
    computes. Kept because it's still a useful field-QC signal (spotting
    dropped/duplicated channels per shot) - just honestly labeled now."""
    fields = np.asarray(stats["field_record"])
    unique_sp = np.unique(fields)
    counts = [np.sum(fields == sp) for sp in unique_sp]
    fig, ax = plt.subplots(figsize=(9, 3))
    ax.bar(unique_sp, counts, color="#805ad5", width=0.8)
    ax.set_title("Trace Count per Shot Point (channels recorded per shot)")
    ax.set_xlabel("Shot Point (FFID)")
    ax.set_ylabel("Trace count")
    return _fig_to_base64(fig)


def _plot_snr(stats):
    snr = np.asarray(stats.get("snr", []))
    fig, ax = plt.subplots(figsize=(5, 3))
    valid = snr[~np.isnan(snr)] if len(snr) else np.array([])
    if len(valid):
        # IQR-based clip for display only - a single spiked trace (already
        # caught separately by the amplitude check) can otherwise produce
        # an extreme S/N value that squashes the whole histogram into one
        # bar. The clip only affects this plot, not the underlying QC.
        q1, q3 = np.percentile(valid, [25, 75])
        iqr = max(q3 - q1, 1e-9)
        hi = q3 + 3.0 * iqr
        display = valid[valid <= hi] if hi > valid.min() else valid
        n_clipped = len(valid) - len(display)
        ax.hist(display, bins=40, color="#2b6cb0")
        ax.axvline(np.median(valid), color="#c53030", linestyle="--", linewidth=1,
                   label=f"median={np.median(valid):.1f}")
        ax.legend(fontsize=8)
        title = "Signal-to-Noise Ratio Distribution"
        if n_clipped:
            title += f"  ({n_clipped} extreme value(s) clipped from view)"
        ax.set_title(title)
    else:
        ax.text(0.5, 0.5, "No S/N data (check disabled or too few samples)", ha="center", transform=ax.transAxes)
        ax.set_title("Signal-to-Noise Ratio Distribution")
    ax.set_xlabel("S/N (signal window RMS / noise window RMS)")
    ax.set_ylabel("Trace count")
    return _fig_to_base64(fig)


def _plot_spectrum(segy_path, n_sample_traces=50):
    with segyio.open(segy_path, ignore_geometry=True) as f:
        dt = segyio.tools.dt(f) / 1e6  # seconds
        step = max(1, f.tracecount // n_sample_traces)
        sampled = [
            f.trace[i] for i in range(0, f.tracecount, step)
            if not np.allclose(f.trace[i], 0.0)
        ]
        if not sampled:
            fig, ax = plt.subplots(figsize=(5, 3))
            ax.text(0.5, 0.5, "No non-zero traces to sample", ha="center", transform=ax.transAxes)
            return _fig_to_base64(fig)
        mean_trace = np.mean(sampled, axis=0)
        freqs = np.fft.rfftfreq(len(f.samples), d=dt)
        spectrum = np.abs(np.fft.rfft(mean_trace))
    fig, ax = plt.subplots(figsize=(5, 3))
    ax.plot(freqs, spectrum, color="#c05621")
    ax.set_title("Average Amplitude Spectrum (sampled traces)")
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("Amplitude")
    ax.set_xlim(0, freqs.max())
    return _fig_to_base64(fig)


def generate_html_report(qc_report, segy_path, out_path="outputs/qc_report.html"):
    stats = qc_report.trace_stats

    rms_img = _plot_rms_by_trace(stats)
    traces_per_shot_img = _plot_traces_per_shot(stats)
    snr_img = _plot_snr(stats)
    spectrum_img = _plot_spectrum(segy_path)

    counts = qc_report.summary_counts()
    rows = "".join(
        f"<tr><td>{cat}</td><td class='{sev}'>{sev.upper()}</td><td>{n}</td></tr>"
        for (cat, sev), n in sorted(counts.items())
    )

    issue_rows = "".join(
        f"<tr><td>{i.trace_index}</td><td>{i.category}</td>"
        f"<td class='{i.severity}'>{i.severity.upper()}</td><td>{i.message}</td></tr>"
        for i in sorted(qc_report.issues, key=lambda x: (x.severity != "critical", x.trace_index))
    )

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>SEG-Y QC Report</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 40px; color: #1a202c; background: #f7fafc; }}
  h1 {{ margin-bottom: 0; }}
  .meta {{ color: #718096; margin-bottom: 30px; }}
  .card {{ background: white; border-radius: 8px; padding: 20px 24px; margin-bottom: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ text-align: left; padding: 6px 10px; border-bottom: 1px solid #e2e8f0; font-size: 14px; }}
  th {{ background: #edf2f7; }}
  .critical {{ color: #c53030; font-weight: 600; }}
  .warning {{ color: #b7791f; font-weight: 600; }}
  .info {{ color: #2b6cb0; }}
  img {{ max-width: 100%; border-radius: 4px; }}
  .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
  .badge {{ display: inline-block; padding: 4px 12px; border-radius: 12px; font-size: 13px; font-weight: 600; margin-right: 8px; }}
  .badge.crit {{ background: #fed7d7; color: #c53030; }}
  .badge.warn {{ background: #feebc8; color: #b7791f; }}
</style>
</head>
<body>
  <h1>SEG-Y QC Report</h1>
  <div class="meta">
    File: {qc_report.filename} &nbsp;|&nbsp;
    Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}
  </div>

  <div class="card">
    <h2>Summary</h2>
    <p>
      <span class="badge crit">{qc_report.critical_count()} CRITICAL</span>
      <span class="badge warn">{qc_report.warning_count()} WARNING</span>
    </p>
    <p>{qc_report.n_traces} traces &middot; {qc_report.n_samples} samples/trace &middot; {qc_report.dt_ms} ms sample interval</p>
    <table>
      <tr><th>Category</th><th>Severity</th><th>Count</th></tr>
      {rows}
    </table>
  </div>

  <div class="card grid">
    <div><h3>Trace Count per Shot Point</h3><img src="data:image/png;base64,{traces_per_shot_img}"></div>
    <div><h3>Signal-to-Noise Ratio</h3><img src="data:image/png;base64,{snr_img}"></div>
  </div>

  <div class="card">
    <h3>Trace RMS Amplitude (dead traces marked)</h3>
    <img src="data:image/png;base64,{rms_img}">
  </div>

  <div class="card">
    <h3>Average Amplitude Spectrum</h3>
    <img src="data:image/png;base64,{spectrum_img}">
  </div>

  <div class="card">
    <h2>Issue Detail</h2>
    <table>
      <tr><th>Trace #</th><th>Category</th><th>Severity</th><th>Message</th></tr>
      {issue_rows}
    </table>
  </div>
</body>
</html>
"""
    with open(out_path, "w") as fh:
        fh.write(html)
    return out_path

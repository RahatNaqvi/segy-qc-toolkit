# SEG-Y QC Toolkit

A SEG-Y QC toolkit with both a Tkinter desktop GUI and the original
command-line interface, built around one shared QC engine. Runs first-pass
trace/header QC that's meaningful even on raw, pre-geometry field data:
dead/spiked traces, shot-point sequence integrity, and sample-count
consistency.

```
CLI (run_qc.py)  ─┐
segy-qc (GUI)  ────┼──>  segyqc/qc.py (QC engine)  ──>  segyqc/report.py (HTML report)
                    │            │
                    │            └──> segyqc/rules.py (configurable checks/thresholds)
segyqc/batch.py (multi-file/folder QC, reuses qc.py)
segyqc/compare.py (before/after diff between two QC runs)
segyqc/format_detect.py (SEG-Y revision/format detection)
```

## What changed from the CLI-only version

- **Geometry/coordinate QC removed.** Coordinate-bust and geometry checks
  now live in the separate `geometry-qc-toolkit`, which operates on
  geometry-loaded data. This toolkit is for pure trace/header QC that's
  valid on raw field tapes before any geometry merge - so it no longer
  assumes source/receiver coordinates are populated.
- **Everything else is additive.** The QC engine's dead-trace, spike, and
  shot-sequence logic is unchanged in substance (the spike check was
  made more robust to real-world amplitude distributions - see below).
  `run_qc(path)` still works exactly as before; `python run_qc.py file.sgy`
  still works exactly as before.

## What the GUI adds

- **Format detection with manual override** - SEG-Y revision (accurately
  labeled with real years: Rev 0/1975, Rev 1/2002, Rev 2.0/2017, Rev
  2.1/2023), byte order, sample format, and text header encoding
  (EBCDIC/ASCII), shown as soon as you load a file. Per the official
  spec, a revision byte of 0 formally means "traditional 1975 SEG-Y" -
  but in practice many modern acquisition systems just never populate
  this byte even though the file otherwise follows rev-1/rev-2
  conventions. A **Revision override dropdown** next to the format label
  lets you tell the tool what you know the file actually is, rather than
  trusting a byte that's routinely left at its default.
- **Interactive trace viewer** - wiggle, variable-area (VA), or
  **variable-density** display (the flooded-color view most QC work
  actually uses for scanning a shot quickly), with pan/zoom via
  matplotlib's toolbar and a trace-range navigator. Includes **manual
  gain** and **AGC** (sliding-window RMS normalization) so weak late-time
  signal is visible without clipping strong early arrivals, and an
  on-demand **frequency spectrum of whatever trace range is currently
  displayed** - not just a whole-file average.
- **Header inspector** - a table of key trace header fields (FFID,
  EnergySourcePoint, ShotPoint, trace ID code, recording timestamp
  fields, sample count/interval, coordinate words), flagging any that
  are constant or all-zero across the file. Note: **SL/RL/RP (source
  line, receiver line, receiver point) are geometry data that lives in
  SPS files, not native SEG-Y trace header words** - they're not
  available here by design (this toolkit intentionally has no geometry
  dependency). If your acquisition system writes them into non-standard
  header bytes, tell me the byte offsets and a custom reader can be
  added.
- **Configurable QC rules** - enable/disable each check and adjust
  thresholds (spike z-score, S/N ratio, duplicate/gap multipliers), with
  save/load to JSON.
- **Batch QC** - select multiple files or whole folders, processed in a
  background thread with a progress bar; double-click any completed row
  to load that file into the other tabs.
- **Before/after comparison** - pin a "before" and "after" QC run and see
  the metric deltas side by side.
- **Export** - the existing interactive HTML report (unchanged), plus new
  CSV (all issues) and PDF (summary + RMS plot) export.

No new dependencies were added for any of this: Tkinter is Python's
standard-library GUI toolkit, PDF export reuses matplotlib (already a
dependency via the HTML report), and CSV export uses the standard `csv`
module.

## HTML report: what changed and why

The original report carried over two geometry-flavored plots ("Fold per
Shot Point" and "Offset Distribution") from before geometry QC was
removed - misleading, since fold is a CMP-binning concept this toolkit
no longer computes, and offset is frequently unpopulated on raw field
tapes. Both are gone. In their place:

- **Trace Count per Shot Point** - the same bar chart, honestly relabeled:
  it's channel count per shot (useful for spotting dropped/duplicated
  channels), not CMP fold.
- **Signal-to-Noise Ratio Distribution** - a coarse S/N proxy (RMS of the
  back part of each trace vs. RMS of an early noise-dominated window)
  that needs no geometry or velocity model. It's a field-QC heuristic for
  flagging traces worth a closer look, not a substitute for a proper S/N
  estimate with picked first breaks - documented as such in the code.

## Requirements

- Python 3.9+
- **Tkinter** - bundled with the standard Python installer on Windows/macOS,
  but on Debian/Ubuntu Linux it's a separate system package:
  ```bash
  sudo apt install python3-tk
  ```
  If you see `ModuleNotFoundError: No module named 'tkinter'`, this is why.


## Setup

```bash
git clone https://github.com/<your-username>/segy-qc-toolkit.git
cd segy-qc-toolkit

python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

## GUI usage

Install the package in editable mode to get the `segy-qc` command:
```bash
pip install -e .
segy-qc
```
Or run it directly without installing:
```bash
python -m segyqc.gui.app
```

In the app: **Open SEG-Y File** to load one file (shows format info
immediately) → **Run QC** → results appear in the **QC Results** tab.
Use **Trace Viewer** and **Header Inspector** to look at the data itself,
**QC Rules** to change what gets checked, **Batch QC** to process a whole
folder, and **Compare** to diff two QC runs.

## CLI usage (unchanged)

```bash
python run_qc.py path/to/file.sgy --out outputs/qc_report.html
```
Exits non-zero if any critical issues are found - unchanged, so existing
scripts or CI steps built around this still work exactly as before.

```bash
python run_demo.py
```
Generates a synthetic line with injected issues and runs the demo QC +
report pipeline end to end.

## Verify it's working

```bash
python -m pytest tests/ -v
```
Expect `46 passed` - 6 original QC tests (updated for the geometry
removal) plus tests for rules, format detection, batch processing,
header inspection, export, and the signal-processing primitives (S/N,
dominant frequency, AGC) behind the trace viewer. None of these require
a display.

The GUI itself is smoke-tested separately (not via pytest, since it needs
a display):
```bash
xvfb-run -a python3 gui_smoke_test.py   # Linux, no monitor
python3 gui_smoke_test.py                # if you have a display
```
This drives the real app through file load → QC → every tab → batch →
rules → compare → export, and reports pass/fail.

## Project layout

```
segyqc/
  qc.py               # QC engine (dead/spike/shot-sequence/S-N/sample checks)
  report.py            # HTML report generator
  rules.py             # QCConfig - enable/disable checks, thresholds
  format_detect.py     # SEG-Y revision/format/encoding detection
  batch.py             # multi-file/folder QC runner
  compare.py           # before/after metric comparison
  signal_metrics.py     # dominant frequency, AGC, manual gain (pure functions)
  synth_generator.py   # synthetic test data (no real data needed)
  gui/
    app.py             # main Tkinter window - orchestrator only
    trace_viewer.py     # wiggle/VA/variable-density display, gain/AGC, spectrum-of-selection
    header_panel.py     # header inspection table
    qc_panel.py          # QC results + report/export buttons
    batch_panel.py       # batch file/folder selection + progress
    rules_panel.py        # QC rules configuration UI
    export.py             # CSV/PDF export
run_qc.py              # original CLI entry point (unchanged)
run_demo.py             # original demo script (unchanged)
gui_smoke_test.py        # headless end-to-end GUI verification script
tests/                    # pytest suite, 46 tests, no display required
pyproject.toml            # packaging + `segy-qc` console script
```

## Possible extensions

- Real-time trace viewer updates while a batch QC run is in progress
- Header inspector: per-trace drill-down, not just file-level summary
- PDF export with the full plot set (currently a compact summary)

## License

MIT — see [LICENSE](LICENSE).

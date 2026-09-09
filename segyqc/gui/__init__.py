"""
segyqc.gui
----------
Tkinter desktop GUI for the SEG-Y QC toolkit. This package is purely a
frontend/orchestrator: every actual QC calculation is delegated to the
existing segyqc modules (qc.py, report.py, batch.py, compare.py,
format_detect.py, rules.py). No QC logic lives here.
"""

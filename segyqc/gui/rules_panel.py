"""
rules_panel.py
--------------
GUI for segyqc.rules.QCConfig - lets the user enable/disable checks and
adjust thresholds. Purely reads/writes a QCConfig instance; the actual
check logic stays in qc.py.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from ..rules import QCConfig


class RulesPanel(ttk.Frame):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.config = QCConfig()

        self.dead_var = tk.BooleanVar(value=self.config.enable_dead_trace_check)
        self.spike_var = tk.BooleanVar(value=self.config.enable_spike_check)
        self.spike_thresh_var = tk.DoubleVar(value=self.config.spike_z_threshold)
        self.shot_seq_var = tk.BooleanVar(value=self.config.enable_shot_sequence_check)
        self.dup_mult_var = tk.DoubleVar(value=self.config.duplicate_sp_multiplier)
        self.gap_mult_var = tk.DoubleVar(value=self.config.sp_gap_multiplier)
        self.sample_var = tk.BooleanVar(value=self.config.enable_sample_consistency_check)

        pad = {"padx": 8, "pady": 4}

        ttk.Checkbutton(self, text="Dead trace check", variable=self.dead_var).grid(row=0, column=0, sticky="w", **pad)

        ttk.Checkbutton(self, text="Spike check", variable=self.spike_var).grid(row=1, column=0, sticky="w", **pad)
        ttk.Label(self, text="Spike z-threshold:").grid(row=1, column=1, sticky="e", **pad)
        ttk.Spinbox(self, from_=1.0, to=50.0, increment=0.5, textvariable=self.spike_thresh_var, width=8).grid(
            row=1, column=2, sticky="w", **pad)

        ttk.Checkbutton(self, text="Shot-sequence check", variable=self.shot_seq_var).grid(row=2, column=0, sticky="w", **pad)
        ttk.Label(self, text="Duplicate-SP multiplier:").grid(row=2, column=1, sticky="e", **pad)
        ttk.Spinbox(self, from_=1.1, to=5.0, increment=0.1, textvariable=self.dup_mult_var, width=8).grid(
            row=2, column=2, sticky="w", **pad)
        ttk.Label(self, text="SP-gap multiplier:").grid(row=3, column=1, sticky="e", **pad)
        ttk.Spinbox(self, from_=1.1, to=5.0, increment=0.1, textvariable=self.gap_mult_var, width=8).grid(
            row=3, column=2, sticky="w", **pad)

        ttk.Checkbutton(self, text="Sample-count consistency check", variable=self.sample_var).grid(
            row=4, column=0, sticky="w", **pad)

        btns = ttk.Frame(self)
        btns.grid(row=5, column=0, columnspan=3, sticky="w", pady=(10, 0), padx=8)
        ttk.Button(btns, text="Reset to defaults", command=self.reset_defaults).pack(side="left", padx=(0, 6))
        ttk.Button(btns, text="Save config...", command=self.save_dialog).pack(side="left", padx=(0, 6))
        ttk.Button(btns, text="Load config...", command=self.load_dialog).pack(side="left", padx=(0, 6))

    def get_config(self):
        return QCConfig(
            enable_dead_trace_check=self.dead_var.get(),
            enable_spike_check=self.spike_var.get(),
            spike_z_threshold=self.spike_thresh_var.get(),
            enable_shot_sequence_check=self.shot_seq_var.get(),
            duplicate_sp_multiplier=self.dup_mult_var.get(),
            sp_gap_multiplier=self.gap_mult_var.get(),
            enable_sample_consistency_check=self.sample_var.get(),
        )

    def set_config(self, config):
        self.dead_var.set(config.enable_dead_trace_check)
        self.spike_var.set(config.enable_spike_check)
        self.spike_thresh_var.set(config.spike_z_threshold)
        self.shot_seq_var.set(config.enable_shot_sequence_check)
        self.dup_mult_var.set(config.duplicate_sp_multiplier)
        self.gap_mult_var.set(config.sp_gap_multiplier)
        self.sample_var.set(config.enable_sample_consistency_check)

    def reset_defaults(self):
        self.set_config(QCConfig())

    def save_dialog(self):
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if path:
            self.get_config().save(path)
            messagebox.showinfo("Saved", f"Config saved to {path}")

    def load_dialog(self):
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if path:
            try:
                self.set_config(QCConfig.load(path))
            except Exception as e:
                messagebox.showerror("Error", f"Could not load config: {e}")

"""
rules.py
--------
Configurable QC rules. This module has no knowledge of SEG-Y or segyio -
it's a plain configuration object that qc.py reads to decide which checks
to run and with what thresholds. Kept separate from the QC engine so the
GUI (or any caller) can build/save/load a config without importing
anything QC-specific.
"""

from dataclasses import dataclass, asdict
import json


@dataclass
class QCConfig:
    enable_dead_trace_check: bool = True
    enable_spike_check: bool = True
    spike_z_threshold: float = 6.0

    enable_shot_sequence_check: bool = True
    duplicate_sp_multiplier: float = 1.5   # flag SP with trace count >= this x typical
    sp_gap_multiplier: float = 1.5         # flag SP gaps >= this x typical step

    enable_sample_consistency_check: bool = True

    enable_snr_check: bool = True
    snr_noise_window_fraction: float = 0.1   # first N% of record assumed noise-dominated
    snr_low_threshold: float = 2.0            # flag traces with S/N below this ratio

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        known = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**known)

    def save(self, path):
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path):
        with open(path, "r") as f:
            return cls.from_dict(json.load(f))

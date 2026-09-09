"""
header_panel.py
----------------
Trace header inspection: reads header words directly with segyio and
flags fields that are constant across all traces (often means "never
populated"), or missing/zero when they'd normally be expected. This is
presentation + light heuristics only - no QC severity scoring here, that
stays in qc.py; this panel is for a human to eyeball the raw headers.

Note on SL/RL/RP (source line, receiver line, receiver point): these are
SPS/geometry concepts, not standard SEG-Y trace header words. They only
exist in a SEG-Y file if the acquisition vendor wrote them into
non-standard header bytes (common with nodal systems like INOVA/Stryde/
GTI, but the byte layout is vendor-specific and not something this tool
can guess correctly). Use "Custom Fields" below to read them from
whatever byte offset your system actually uses - once you tell it where,
it'll display and QC them like any other field.
"""

import struct
import tkinter as tk
from tkinter import ttk, simpledialog, messagebox

import segyio
from segyio import TraceField


# Standard SEG-Y trace header fields worth surfacing by default.
INSPECTED_FIELDS = [
    ("FieldRecord (FFID)", TraceField.FieldRecord),
    ("TraceNumber", TraceField.TraceNumber),
    ("EnergySourcePoint", TraceField.EnergySourcePoint),
    ("ShotPoint", TraceField.ShotPoint),
    ("offset", TraceField.offset),
    ("SourceX", TraceField.SourceX),
    ("SourceY", TraceField.SourceY),
    ("GroupX", TraceField.GroupX),
    ("GroupY", TraceField.GroupY),
    ("CDP", TraceField.CDP),
    ("TraceIdentificationCode", TraceField.TraceIdentificationCode),
    ("TRACE_SAMPLE_COUNT", TraceField.TRACE_SAMPLE_COUNT),
    ("TRACE_SAMPLE_INTERVAL", TraceField.TRACE_SAMPLE_INTERVAL),
    ("YearDataRecorded", TraceField.YearDataRecorded),
    ("DayOfYear", TraceField.DayOfYear),
    ("HourOfDay", TraceField.HourOfDay),
    ("MinuteOfHour", TraceField.MinuteOfHour),
    ("SecondOfMinute", TraceField.SecondOfMinute),
    ("ElevationScalar", TraceField.ElevationScalar),
    ("SourceGroupScalar", TraceField.SourceGroupScalar),
]

# byte type -> struct format char, used only to interpret 2-byte fields
# and floats (segyio's native raw-offset access assumes 4-byte int by
# default, which covers most cases directly).
CUSTOM_FIELD_TYPES = {
    "int16": "h",
    "uint16": "H",
    "int32": "i",
    "uint32": "I",
    "float32": "f",
}


def read_custom_field(segy_path, byte_offset, type_name, n_total=None):
    """Reads a header word at an arbitrary byte offset (1-indexed, per
    the SEG-Y convention used in documentation and matching segyio's own
    TraceField enum values, e.g. byte 197 for ShotPoint). Use this for
    vendor-specific fields (SL/RL/RP, etc.) not covered by the standard
    segyio TraceField enum.

    For int32 (the most common trace header field width), this uses
    segyio's native raw-offset field access directly. For other widths
    (int16/float32/etc.), it falls back to unpacking the raw 240-byte
    header buffer at that offset, since segyio's raw-offset shortcut
    assumes 4-byte ints.
    """
    values = []
    with segyio.open(segy_path, ignore_geometry=True) as f:
        n = n_total or f.tracecount
        if type_name in ("int32", "uint32"):
            for i in range(n):
                v = f.header[i][byte_offset]
                if type_name == "uint32" and v < 0:
                    v += 2 ** 32
                values.append(v)
        else:
            fmt_char = CUSTOM_FIELD_TYPES[type_name]
            length = 2 if "16" in type_name else 4
            zero_idx = byte_offset - 1
            for i in range(n):
                raw = bytes(f.header[i].buf)
                chunk = raw[zero_idx:zero_idx + length]
                if len(chunk) < length:
                    values.append(None)
                    continue
                values.append(struct.unpack(">" + fmt_char, chunk)[0])
    return values


def summarize_headers(segy_path, max_traces_for_sample=5, custom_fields=None):
    """Returns a list of dicts, one per inspected field (standard +
    any user-defined custom fields): name, sample values (first few
    traces), whether it's constant across the file, whether it looks
    unpopulated (all zero)."""
    rows = []
    with segyio.open(segy_path, ignore_geometry=True) as f:
        n = f.tracecount
        for name, field in INSPECTED_FIELDS:
            values = f.attributes(field)[:]
            rows.append(_summarize_values(name, list(values), n))

    for cf in (custom_fields or []):
        values = read_custom_field(segy_path, cf["byte_offset"], cf["type"])
        clean = [v for v in values if v is not None]
        rows.append(_summarize_values(f"{cf['name']} (byte {cf['byte_offset']}, {cf['type']})",
                                       clean, len(clean), sample_override=values[:max_traces_for_sample]))

    return rows


def _summarize_values(name, values, n, sample_override=None):
    sample_vals = sample_override if sample_override is not None else values[:5]
    is_constant = bool(len(set(values)) == 1) if n > 0 and values else True
    is_all_zero = bool(all(v == 0 for v in values)) if n > 0 and values else True
    flag = ""
    if is_all_zero:
        flag = "unpopulated (all zero)"
    elif is_constant:
        flag = "constant across all traces"
    return {
        "field": name,
        "sample_values": sample_vals,
        "constant": is_constant,
        "all_zero": is_all_zero,
        "flag": flag,
    }


class HeaderPanel(ttk.Frame):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.segy_path = None
        self.custom_fields = []  # list of {"name", "byte_offset", "type"}

        top = ttk.Frame(self)
        top.pack(side="top", fill="x", padx=6, pady=4)
        ttk.Button(top, text="Refresh", command=self.refresh).pack(side="left")
        ttk.Button(top, text="Add Custom Field...", command=self.add_custom_field_dialog).pack(side="left", padx=(6, 0))
        ttk.Button(top, text="Clear Custom Fields", command=self.clear_custom_fields).pack(side="left", padx=(6, 0))
        self.status_label = ttk.Label(top, text="No file loaded")
        self.status_label.pack(side="left", padx=10)

        hint = ttk.Label(
            self,
            text="Tip: SL/RL/RP and other vendor-specific fields aren't standard SEG-Y bytes - "
                 "use 'Add Custom Field' with the byte offset your acquisition system uses for them.",
            foreground="#666", font=("", 8, "italic"),
        )
        hint.pack(side="top", fill="x", padx=6)

        columns = ("field", "sample_values", "flag")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=16)
        for col, width in zip(columns, (260, 320, 220)):
            self.tree.heading(col, text=col.replace("_", " ").title())
            self.tree.column(col, width=width, anchor="w")
        self.tree.tag_configure("flagged", background="#fff3cd")
        self.tree.pack(side="top", fill="both", expand=True, padx=6, pady=(0, 6))

    def load_file(self, segy_path):
        self.segy_path = segy_path
        self.refresh()

    def add_custom_field_dialog(self):
        name = simpledialog.askstring("Custom field", "Field name (e.g. 'SourceLine'):", parent=self)
        if not name:
            return
        byte_offset = simpledialog.askinteger("Custom field", "Byte offset (1-indexed, per SEG-Y docs, e.g. 197):", parent=self)
        if byte_offset is None:
            return
        type_name = simpledialog.askstring(
            "Custom field", f"Data type - one of {list(CUSTOM_FIELD_TYPES.keys())}:", parent=self, initialvalue="int32")
        if type_name not in CUSTOM_FIELD_TYPES:
            messagebox.showerror("Invalid type", f"Type must be one of {list(CUSTOM_FIELD_TYPES.keys())}")
            return
        self.custom_fields.append({"name": name, "byte_offset": byte_offset, "type": type_name})
        self.refresh()

    def clear_custom_fields(self):
        self.custom_fields = []
        self.refresh()

    def refresh(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        if not self.segy_path:
            self.status_label.config(text="No file loaded")
            return
        try:
            rows = summarize_headers(self.segy_path, custom_fields=self.custom_fields)
        except Exception as e:
            self.status_label.config(text=f"Error reading headers: {e}")
            return
        self.status_label.config(text=self.segy_path)
        for row in rows:
            tag = ("flagged",) if row["flag"] else ()
            self.tree.insert("", "end", values=(row["field"], row["sample_values"], row["flag"]), tags=tag)


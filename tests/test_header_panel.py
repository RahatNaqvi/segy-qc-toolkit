import os
import sys
import segyio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from segyqc.synth_generator import generate_synthetic_line
from segyqc.gui.header_panel import summarize_headers, read_custom_field


def test_summarize_headers_flags_unpopulated_fields(tmp_path):
    path = generate_synthetic_line(out_path=str(tmp_path / "line.sgy"), n_shots=3, n_receivers=10)
    rows = summarize_headers(path)
    by_field = {r["field"]: r for r in rows}
    # SourceX/GroupX are never set by the synthetic generator anymore
    # (geometry removed) - should be flagged unpopulated.
    assert by_field["SourceX"]["all_zero"] is True
    assert "unpopulated" in by_field["SourceX"]["flag"]


def test_summarize_headers_field_record_not_constant(tmp_path):
    path = generate_synthetic_line(out_path=str(tmp_path / "line.sgy"), n_shots=3, n_receivers=10)
    rows = summarize_headers(path)
    by_field = {r["field"]: r for r in rows}
    assert by_field["FieldRecord (FFID)"]["constant"] is False
    assert by_field["FieldRecord (FFID)"]["flag"] == ""


def test_summarize_headers_returns_all_inspected_fields(tmp_path):
    path = generate_synthetic_line(out_path=str(tmp_path / "line.sgy"), n_shots=2, n_receivers=5)
    rows = summarize_headers(path)
    fields = {r["field"] for r in rows}
    assert "FieldRecord (FFID)" in fields
    assert "TraceNumber" in fields
    assert "offset" in fields
    assert "YearDataRecorded" in fields
    assert "DayOfYear" in fields


def test_custom_field_reads_vendor_specific_byte_offset(tmp_path):
    path = generate_synthetic_line(out_path=str(tmp_path / "line.sgy"), n_shots=2, n_receivers=5)
    with segyio.open(path, ignore_geometry=True, mode="r+") as f:
        for i in range(f.tracecount):
            f.header[i][233] = 8001 + i  # simulate a vendor "SourceLine" word

    values = read_custom_field(path, byte_offset=233, type_name="int32")
    assert values[0] == 8001
    assert values[5] == 8006


def test_custom_field_appears_in_summarize_headers(tmp_path):
    path = generate_synthetic_line(out_path=str(tmp_path / "line.sgy"), n_shots=2, n_receivers=5)
    with segyio.open(path, ignore_geometry=True, mode="r+") as f:
        for i in range(f.tracecount):
            f.header[i][233] = 8001

    rows = summarize_headers(path, custom_fields=[{"name": "SourceLine", "byte_offset": 233, "type": "int32"}])
    custom_rows = [r for r in rows if "SourceLine" in r["field"]]
    assert len(custom_rows) == 1
    assert custom_rows[0]["constant"] is True
    assert custom_rows[0]["all_zero"] is False


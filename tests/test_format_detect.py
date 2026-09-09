import os
import sys
import struct

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from segyqc.format_detect import detect_format


def _make_raw_segy_headers(path, revision_raw=0x0100, sample_format=5,
                            samples_per_trace=1000, sample_interval=2000,
                            byte_order=">", text_ascii=True):
    """Write just the text + binary header bytes (no traces) - enough for
    detect_format, which never opens the file with segyio."""
    if text_ascii:
        text_header = b"C1 SYNTHETIC TEST HEADER" + b" " * (3200 - 24)
    else:
        text_header = ("C1 SYNTHETIC TEST HEADER").encode("cp500") + b"\x40" * (3200 - 24)

    binary_header = bytearray(400)
    struct.pack_into(byte_order + "H", binary_header, 16, sample_interval)
    struct.pack_into(byte_order + "H", binary_header, 20, samples_per_trace)
    struct.pack_into(byte_order + "H", binary_header, 24, sample_format)
    struct.pack_into(byte_order + "H", binary_header, 300, revision_raw)

    with open(path, "wb") as f:
        f.write(text_header[:3200])
        f.write(bytes(binary_header))


def test_detects_rev1_big_endian(tmp_path):
    path = tmp_path / "rev1.sgy"
    _make_raw_segy_headers(str(path), revision_raw=0x0100, sample_format=5)
    info = detect_format(str(path))
    assert info.revision == "Rev 1 (2002)"
    assert info.byte_order == "big"
    assert info.sample_format_code == 5
    assert info.sample_format_name == "4-byte IEEE float"
    assert info.is_standard


def test_detects_rev2(tmp_path):
    path = tmp_path / "rev2.sgy"
    _make_raw_segy_headers(str(path), revision_raw=0x0200, sample_format=1)
    info = detect_format(str(path))
    assert info.revision == "Rev 2.0 (2017)"
    assert info.sample_format_name == "4-byte IBM float"


def test_detects_rev2_1(tmp_path):
    path = tmp_path / "rev21.sgy"
    _make_raw_segy_headers(str(path), revision_raw=0x0201, sample_format=5)
    info = detect_format(str(path))
    assert info.revision == "Rev 2.1 (2023)"


def test_detects_rev0_unspecified(tmp_path):
    path = tmp_path / "rev0.sgy"
    _make_raw_segy_headers(str(path), revision_raw=0x0000, sample_format=1)
    info = detect_format(str(path))
    assert "Rev 0" in info.revision


def test_detects_little_endian_fallback(tmp_path):
    path = tmp_path / "little.sgy"
    # sample format 5 written little-endian; interpreting as big-endian
    # would give an implausible code (5 byte-swapped -> 1280), triggering
    # the little-endian fallback path.
    _make_raw_segy_headers(str(path), revision_raw=0x0100, sample_format=5, byte_order="<")
    info = detect_format(str(path))
    assert info.byte_order == "little"
    assert info.sample_format_code == 5


def test_detects_ascii_text_header(tmp_path):
    path = tmp_path / "ascii.sgy"
    _make_raw_segy_headers(str(path), text_ascii=True)
    info = detect_format(str(path))
    assert info.text_header_encoding == "ASCII"


def test_detects_ebcdic_text_header(tmp_path):
    path = tmp_path / "ebcdic.sgy"
    _make_raw_segy_headers(str(path), text_ascii=False)
    info = detect_format(str(path))
    assert info.text_header_encoding == "EBCDIC"


def test_non_standard_revision_flagged(tmp_path):
    path = tmp_path / "weird.sgy"
    _make_raw_segy_headers(str(path), revision_raw=0x9999, sample_format=1)
    info = detect_format(str(path))
    assert not info.is_standard
    assert "non-standard" in info.revision.lower() or "unknown" in info.revision.lower()


def test_too_short_file_raises(tmp_path):
    path = tmp_path / "truncated.sgy"
    with open(path, "wb") as f:
        f.write(b"\x00" * 100)
    with pytest.raises(ValueError):
        detect_format(str(path))

"""
format_detect.py
-----------------
Lightweight SEG-Y format/revision detection that reads the raw text and
binary file headers directly with struct, independent of segyio. This
lets the GUI show format info (and catch obviously non-standard files)
before attempting a full QC pass, and works even on files that are
non-conformant enough to give segyio trouble on open.

Byte layout (per SEG-Y rev 1 / rev 2, all offsets 0-indexed from start
of file):
  0-3199      Textual file header (3200 bytes, EBCDIC or ASCII)
  3200-3599   Binary file header (400 bytes)
    3200-3201   Job ID
    3216-3217   Sample interval
    3220-3221   Samples per trace
    3224-3225   Data sample format code
    3500-3501   SEG-Y format revision number
    3502-3503   Fixed length trace flag (rev 1+)
"""

from dataclasses import dataclass

TEXT_HEADER_SIZE = 3200
BINARY_HEADER_SIZE = 400

SAMPLE_FORMAT_NAMES = {
    1: "4-byte IBM float",
    2: "4-byte signed int",
    3: "2-byte signed int",
    4: "4-byte fixed-point with gain (obsolete)",
    5: "4-byte IEEE float",
    6: "8-byte IEEE double",
    7: "3-byte signed int",
    8: "1-byte signed int",
    9: "8-byte signed int",
    10: "4-byte unsigned int",
    11: "2-byte unsigned int",
    12: "8-byte unsigned int",
    15: "3-byte unsigned int",
    16: "1-byte unsigned int",
}

REVISION_NAMES = {
    0x0000: "Rev 0 (1975) - or a modern file whose writer simply left this byte at 0",
    0x0100: "Rev 1 (2002)",
    0x0200: "Rev 2.0 (2017)",
    0x0201: "Rev 2.1 (2023)",
}

# User-selectable override options, for when the byte is 0/ambiguous but
# the operator knows the acquisition system's real format (e.g. a modern
# system that never populated this header word).
REVISION_OVERRIDE_OPTIONS = [
    "Auto-detected",
    "Rev 0 (1975)",
    "Rev 1 (2002)",
    "Rev 2.0 (2017)",
    "Rev 2.1 (2023)",
]


@dataclass
class SegyFormatInfo:
    path: str
    text_header_encoding: str      # "EBCDIC" or "ASCII"
    revision: str
    revision_raw: int
    byte_order: str                 # "big" or "little"
    sample_format_code: int
    sample_format_name: str
    samples_per_trace: int
    sample_interval_us: int
    is_standard: bool               # False if anything looked non-conformant

    def summary(self):
        return (
            f"{self.revision} | {self.sample_format_name} | "
            f"{self.byte_order}-endian | {self.samples_per_trace} samples/trace"
        )


def _detect_text_encoding(raw_bytes):
    """Heuristic: count printable characters under each interpretation
    and pick whichever decodes to more plausible text. SEG-Y textual
    headers are traditionally EBCDIC (cp500) but many modern files use
    ASCII instead."""
    ascii_printable = sum(1 for b in raw_bytes if 32 <= b <= 126)
    try:
        ebcdic_decoded = raw_bytes.decode("cp500", errors="replace")
        ebcdic_printable = sum(1 for c in ebcdic_decoded if c.isprintable())
    except Exception:
        ebcdic_printable = 0
    return "ASCII" if ascii_printable >= ebcdic_printable else "EBCDIC"


def _classify_revision(raw_value):
    if raw_value in REVISION_NAMES:
        return REVISION_NAMES[raw_value], True
    # Some vendors write e.g. 1 instead of 0x0100 - be lenient
    lenient = {0: REVISION_NAMES[0x0000], 1: REVISION_NAMES[0x0100], 2: REVISION_NAMES[0x0200]}
    if raw_value in lenient:
        return lenient[raw_value], True
    # Decode as major.minor (per spec: high byte = major, low byte =
    # minor) for any revision not in our known table - covers future
    # revisions beyond 2.1 without misreporting them as "unknown".
    major, minor = (raw_value >> 8) & 0xFF, raw_value & 0xFF
    if 0 <= major <= 9 and 0 <= minor <= 99:
        return f"Rev {major}.{minor} (non-standard/uncatalogued exact value)", False
    return f"Unknown/non-standard (raw=0x{raw_value:04x})", False


def detect_format(path):
    """Read a SEG-Y file's text and binary headers and return a
    SegyFormatInfo. Raises OSError/struct errors if the file is too
    short to even contain a binary header - callers should catch that
    and treat it as "not a valid SEG-Y file"."""
    import struct

    with open(path, "rb") as f:
        text_header = f.read(TEXT_HEADER_SIZE)
        binary_header = f.read(BINARY_HEADER_SIZE)

    if len(binary_header) < BINARY_HEADER_SIZE:
        raise ValueError(
            f"File is too short to contain a valid SEG-Y binary header "
            f"({len(text_header) + len(binary_header)} bytes found, "
            f"need at least {TEXT_HEADER_SIZE + BINARY_HEADER_SIZE})"
        )

    encoding = _detect_text_encoding(text_header)

    # SEG-Y is big-endian per spec, but some vendor/legacy files are
    # written little-endian. Try big-endian first and sanity-check the
    # sample format code (should be a small positive integer); fall back
    # to little-endian if that looks implausible.
    def _unpack(order):
        fmt_char = ">" if order == "big" else "<"
        sample_fmt = struct.unpack(fmt_char + "H", binary_header[24:26])[0]
        samples_per_trace = struct.unpack(fmt_char + "H", binary_header[20:22])[0]
        sample_interval = struct.unpack(fmt_char + "H", binary_header[16:18])[0]
        revision_raw = struct.unpack(fmt_char + "H", binary_header[300:302])[0]
        return sample_fmt, samples_per_trace, sample_interval, revision_raw

    sample_fmt, samples_per_trace, sample_interval, revision_raw = _unpack("big")
    byte_order = "big"
    if sample_fmt not in SAMPLE_FORMAT_NAMES:
        alt_sample_fmt, alt_spt, alt_si, alt_rev = _unpack("little")
        if alt_sample_fmt in SAMPLE_FORMAT_NAMES:
            sample_fmt, samples_per_trace, sample_interval, revision_raw = (
                alt_sample_fmt, alt_spt, alt_si, alt_rev
            )
            byte_order = "little"

    revision_name, is_standard_rev = _classify_revision(revision_raw)
    sample_format_name = SAMPLE_FORMAT_NAMES.get(sample_fmt, f"Unknown code {sample_fmt}")
    is_standard = is_standard_rev and sample_fmt in SAMPLE_FORMAT_NAMES

    return SegyFormatInfo(
        path=str(path),
        text_header_encoding=encoding,
        revision=revision_name,
        revision_raw=revision_raw,
        byte_order=byte_order,
        sample_format_code=sample_fmt,
        sample_format_name=sample_format_name,
        samples_per_trace=samples_per_trace,
        sample_interval_us=sample_interval,
        is_standard=is_standard,
    )

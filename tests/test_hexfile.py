"""hexfile.py tests — a real, minimal Intel HEX file constructed by hand,
not derived from the parser's own output."""

import pytest

from blheli32proxy.protocol import hexfile


def _ihex_line(rectype: int, addr: int, payload: bytes) -> str:
    length = len(payload)
    body = bytes([length, (addr >> 8) & 0xFF, addr & 0xFF, rectype]) + payload
    checksum = (-sum(body)) & 0xFF
    return ":" + body.hex().upper() + f"{checksum:02X}"


def test_parse_intel_hex_data_record(tmp_path):
    data = bytes(range(16))
    lines = [
        _ihex_line(0x00, 0x2000, data),
        _ihex_line(0x01, 0x0000, b""),  # EOF
    ]
    path = tmp_path / "test.hex"
    path.write_text("\n".join(lines) + "\n")

    mem = hexfile.parse_intel_hex(str(path))
    assert len(mem) == 16
    for i, b in enumerate(data):
        assert mem[0x2000 + i] == b


def test_parse_intel_hex_extended_linear_address(tmp_path):
    # base 0x0001 << 16 = 0x10000; a data record at offset 0x0010 lands at 0x10010
    lines = [
        _ihex_line(0x04, 0x0000, bytes.fromhex("0001")),
        _ihex_line(0x00, 0x0010, bytes([0xAB])),
        _ihex_line(0x01, 0x0000, b""),
    ]
    path = tmp_path / "test.hex"
    path.write_text("\n".join(lines) + "\n")

    mem = hexfile.parse_intel_hex(str(path))
    assert mem[0x10010] == 0xAB


def test_chunk_at_returns_bytes_when_fully_covered(tmp_path):
    data = bytes(range(8))
    path = tmp_path / "test.hex"
    path.write_text(_ihex_line(0x00, 0x2000, data) + "\n" + _ihex_line(0x01, 0, b"") + "\n")
    mem = hexfile.parse_intel_hex(str(path))

    assert hexfile.chunk_at(mem, 0x2000, 8) == data


def test_chunk_at_returns_none_on_any_gap(tmp_path):
    """A single missing byte in the requested range must fail closed (None),
    never silently fabricate a placeholder — comparing real flash against
    invented filler instead of admitting no data was available produces
    false mismatch findings."""
    data = bytes(range(8))
    path = tmp_path / "test.hex"
    path.write_text(_ihex_line(0x00, 0x2000, data) + "\n" + _ihex_line(0x01, 0, b"") + "\n")
    mem = hexfile.parse_intel_hex(str(path))

    # request one byte past the end of the covered data -> must be None, not padded
    assert hexfile.chunk_at(mem, 0x2000, 9) is None
    assert hexfile.chunk_at(mem, 0x1000, 8) is None  # entirely uncovered region


def test_encode_intel_hex_round_trips_through_parse(tmp_path):
    data = bytes((i * 7) % 256 for i in range(40))  # arbitrary, not all-same-byte
    text = hexfile.encode_intel_hex(data, base_addr=0x2000, line_length=16)
    path = tmp_path / "roundtrip.hex"
    path.write_text(text)

    mem = hexfile.parse_intel_hex(str(path))
    assert hexfile.chunk_at(mem, 0x2000, len(data)) == data


def test_encode_intel_hex_matches_real_file_line_convention(tmp_path):
    """The real Furling32_Multi_32_95.Hex file is confirmed 16-bytes-per-line,
    LF-only line endings. A round-trip through our own
    encoder using the same parameters must reproduce that exact byte size for
    the same address range — this is a pure format check (text size depends
    only on range + line convention, never on the actual byte values), not a
    content-correctness check."""
    data = bytes(16)  # one full line's worth
    text = hexfile.encode_intel_hex(data, base_addr=0x2000, line_length=16)
    assert "\r\n" not in text
    lines = text.strip("\n").split("\n")
    # checksum = two's complement of (0x10 + 0x20 + 0x00 + 0x00 + 16*0x00) mod 256 = 256-48 = 0xD0
    assert lines[0] == ":10200000" + "00" * 16 + "D0"
    assert lines[-1] == ":00000001FF"


def test_encode_intel_hex_sparse_skips_a_real_gap_entirely():
    """A gap must produce NO line at all, not a padded/filler line — padding
    a gap with 0xFF and re-encoding it produces a file structurally
    different from the real one (which simply omits any record for missing
    data)."""
    mem = {0x2000: 0xAA, 0x2001: 0xBB}  # 0x2002 onward: nothing, then a separate run
    mem[0x3000] = 0xCC
    text = hexfile.encode_intel_hex_sparse(mem)
    lines = text.strip("\n").split("\n")
    assert lines[-1] == ":00000001FF"
    data_lines = lines[:-1]
    assert len(data_lines) == 2  # one run of 2 bytes, one run of 1 byte — never a line for the gap
    for line in data_lines:
        assert "3000" in line or "2000" in line  # only real addresses appear, never a filler line


def test_encode_intel_hex_sparse_round_trips_confirmed_bytes():
    mem = {0x2000: 1, 0x2001: 2, 0x2002: 3, 0x3000: 9}
    text = hexfile.encode_intel_hex_sparse(mem)
    from tempfile import NamedTemporaryFile

    with NamedTemporaryFile("w", suffix=".hex", delete=False) as f:
        f.write(text)
        path = f.name
    parsed = hexfile.parse_intel_hex(path)
    assert parsed == mem  # exactly the confirmed bytes, nothing fabricated for the gap between them


def test_encode_intel_hex_sparse_empty_mapping():
    assert hexfile.encode_intel_hex_sparse({}) == ":00000001FF\n"

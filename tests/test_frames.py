"""Frame builder/parser tests against real captured byte sequences.

Vectors from research/notes/BLHeli-Uart-Usb-Protocol.en.md's worked transcript.
"""

import pytest

from blheli32proxy.protocol import frames


def test_connect_request_body_matches_capture():
    # Both captures in the research agree on the 0x0D marker + "BLHeli" + CRC suffix,
    # even though the leading zero-run length differs between captures (see frames.py).
    expected_suffix = bytes.fromhex("0D424C48656C69F47D")
    assert frames.connect_request().endswith(expected_suffix)
    assert frames.connect_request(with_zero_preamble=False) == bytes.fromhex(
        "424C48656C69F47D"
    )


def test_keepalive_request():
    assert frames.keepalive_request() == bytes.fromhex("FD004090")


def test_disconnect_request():
    assert frames.disconnect_request() == bytes.fromhex("0001C1C0")


def test_set_address_requests():
    assert frames.set_address_request(0x7C00) == bytes.fromhex("FF007C0010D4")
    assert frames.set_address_request(0xEB00) == bytes.fromhex("FF00EB007EE4")
    assert frames.set_address_request(0xF7AC) == bytes.fromhex("FF00F7AC7659")


def test_set_address_rejects_out_of_range():
    with pytest.raises(ValueError):
        frames.set_address_request(0x10000)


def test_read_requests():
    assert frames.read_request(256) == bytes.fromhex("030000F0")
    assert frames.read_request(16) == bytes.fromhex("0310013C")


def test_read_request_rejects_unsupported_length():
    with pytest.raises(ValueError):
        frames.read_request(17)


def test_read_request_experimental_length_encoding():
    # length byte = value directly for 1-255, and 0x00 for the 256 special case,
    # per the two confirmed data points (16->0x10, 256->0x00).
    from blheli32proxy.protocol.crc import crc_bytes

    for length, expected_length_byte in [(1, 0x01), (100, 0x64), (255, 0xFF), (256, 0x00)]:
        frame = frames.read_request(length, allow_experimental=True)
        header = bytes((0x03, expected_length_byte))
        assert frame == header + crc_bytes(header)


def test_read_request_experimental_rejects_out_of_range():
    with pytest.raises(ValueError):
        frames.read_request(0, allow_experimental=True)
    with pytest.raises(ValueError):
        frames.read_request(257, allow_experimental=True)


def test_read_request_experimental_still_matches_confirmed_lengths():
    assert frames.read_request(256, allow_experimental=True) == frames.read_request(256)
    assert frames.read_request(16, allow_experimental=True) == frames.read_request(16)


def test_write_header_and_commit():
    assert frames.write_header_request() == bytes.fromhex("FE0001003078")
    assert frames.commit_request() == bytes.fromhex("0101C050")


def test_write_payload_round_trips_crc():
    payload = bytes([0xAA] * 256)
    framed = frames.write_payload(payload)
    assert len(framed) == 258
    assert framed[:256] == payload


def test_write_payload_rejects_wrong_length():
    with pytest.raises(ValueError):
        frames.write_payload(b"\x00" * 100)


def test_parse_connect_reply():
    # "34 37 31 6A 33 06 07 04 30" from the protocol capture. Bytes at position 3
    # and 6-7 are unexplained in the source material (see frames.py docstring) —
    # only prefix, device_type (found by scanning, not a fixed offset), and ack
    # are asserted here.
    reply = frames.parse_connect_reply(bytes.fromhex("3437316A3306070430"))
    assert reply.prefix == "471"
    assert reply.device_type == 0x3306
    assert reply.ok


def test_parse_connect_reply_with_no_known_device_type():
    reply = frames.parse_connect_reply(bytes.fromhex("3437310000000030"))
    assert reply.device_type is None
    assert reply.ok


def test_parse_connect_reply_rejects_too_short():
    with pytest.raises(ValueError):
        frames.parse_connect_reply(b"\x00\x00")


def test_parse_read_reply_16_bytes_device_info():
    # Address 0xF7AC capture, 16-byte payload + CRC "26 BF" + ACK "30" — verified by
    # recomputing the CRC directly against the raw transcript (see
    # research/notes/BLHeli-Uart-Usb-Protocol.en.md, which had this boundary wrong
    # until corrected during this verification pass).
    payload = bytes.fromhex("41004F001157424636363420DE06EC05")
    data = payload + bytes.fromhex("26BF") + bytes([frames.ACK])
    assert frames.parse_read_reply(data, 16) == payload


def test_parse_read_reply_16_bytes_activation_status():
    # Address 0xEB00 capture, 16-byte payload + CRC "46 34" + ACK "30".
    payload = bytes([0, 0, 0, 0x01, 0xF5, 0x02, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
    data = payload + bytes.fromhex("4634") + bytes([frames.ACK])
    assert frames.parse_read_reply(data, 16) == payload


def test_parse_read_reply_detects_crc_mismatch():
    payload = bytes(16)  # CRC-16/IBM of an all-zero payload is 0x0000, so use a
    bad = payload + b"\x12\x34" + bytes([frames.ACK])  # deliberately wrong CRC.
    with pytest.raises(ValueError):
        frames.parse_read_reply(bad, 16)


def test_parse_read_reply_detects_missing_ack():
    from blheli32proxy.protocol.crc import crc_bytes

    payload = bytes(16)
    bad = payload + crc_bytes(payload) + b"\x00"
    with pytest.raises(ValueError):
        frames.parse_read_reply(bad, 16)

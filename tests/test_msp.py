"""MSP v1 framing and ESC-passthrough-activation tests.

Byte values below are hand-computed from the MSP v1 spec (checksum = XOR of
size, cmd, and payload bytes), not copied from code under test.
"""

import pytest

from blheli32proxy.protocol import msp
from fakes import FakeTransport


def test_build_request_v1_matches_hand_computed_bytes():
    frame = msp.build_request_v1(msp.MSP_SET_PASSTHROUGH, bytes([msp.PROTOCOL_BLHELI, 3]))
    # size=2, cmd=245, payload=[1,3]; checksum = 2^245^1^3 = 245
    assert frame == b"$M<" + bytes([2, 245, 1, 3, 245])


def test_build_request_v1_empty_payload():
    frame = msp.build_request_v1(100)
    # size=0, cmd=100, no payload; checksum = 0^100 = 100
    assert frame == b"$M<" + bytes([0, 100, 100])


def test_parse_reply_v1_success():
    frame = b"$M>" + bytes([1, 245, 1, 245])  # checksum = 1^245^1 = 245
    cmd, payload = msp.parse_reply_v1(frame)
    assert cmd == 245
    assert payload == bytes([1])


def test_parse_reply_v1_error_direction_raises():
    frame = b"$M!" + bytes([1, 245, 0, 244])  # checksum = 1^245^0 = 244
    with pytest.raises(msp.MspError):
        msp.parse_reply_v1(frame)


def test_parse_reply_v1_bad_checksum_raises():
    frame = b"$M>" + bytes([1, 245, 1, 0])  # wrong checksum
    with pytest.raises(msp.MspError):
        msp.parse_reply_v1(frame)


def test_parse_reply_v1_too_short_raises():
    with pytest.raises(msp.MspError):
        msp.parse_reply_v1(b"$M>")


def test_enable_esc_passthrough_success():
    reply = b"$M>" + bytes([1, 245, 1, 245])
    transport = FakeTransport([reply])
    msp.enable_esc_passthrough(transport, motor_index=3)
    assert transport.sent[0] == msp.build_request_v1(msp.MSP_SET_PASSTHROUGH, bytes([1, 3]))


def test_enable_esc_passthrough_fc_refuses_raises():
    reply = b"$M>" + bytes([1, 245, 0, 244])
    transport = FakeTransport([reply])
    with pytest.raises(msp.MspError):
        msp.enable_esc_passthrough(transport, motor_index=99)


def test_enable_esc_passthrough_no_reply_raises():
    transport = FakeTransport([b""])
    with pytest.raises(msp.MspError):
        msp.enable_esc_passthrough(transport, motor_index=0)


def test_exit_esc_passthrough_sends_correct_frame_and_accepts_ack():
    reply = b"$M>" + bytes([0, 0xF4, 0xF4])  # checksum = 0^244 = 244
    transport = FakeTransport([reply])
    msp.exit_esc_passthrough(transport)
    assert transport.sent[0] == b"$M<" + bytes([0, 0xF4, 0xF4])


def test_exit_esc_passthrough_no_reply_raises():
    transport = FakeTransport([b""])
    with pytest.raises(msp.MspError):
        msp.exit_esc_passthrough(transport)

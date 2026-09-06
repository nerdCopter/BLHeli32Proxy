"""fourwayif tests using real byte sequences captured from BLHeliSuite32xl's
own traffic against real hardware (2026-09-04, see
docs/knowledge/protocol-reference.md) — not invented."""

import pytest

from blheli32proxy.protocol import fourwayif as fw


def test_build_request_matches_real_captured_get_version():
    # BLHeliSuite32xl's real cmd_ProtocolGetVersion request: 2f310000010065 85
    frame = fw.build_request(fw.CMD_PROTOCOL_GET_VERSION)
    assert frame == bytes.fromhex("2f31000001006585")


def test_build_request_rejects_empty_payload():
    with pytest.raises(ValueError):
        fw.build_request(fw.CMD_PROTOCOL_GET_VERSION, payload=b"")


def test_parse_reply_matches_real_captured_get_version_reply():
    # BLHeliSuite32xl's real reply: 2e310000016c004f25 (payload=[0x6c]=108=version)
    reply = fw.parse_reply(bytes.fromhex("2e310000016c004f25"))
    assert reply["cmd"] == fw.CMD_PROTOCOL_GET_VERSION
    assert reply["payload"] == bytes([108])
    assert reply["ack"] == fw.ACK_OK


def test_build_read_request_matches_real_captured_device_read():
    # real cmd_DeviceRead at 0x7C00 (Setup block): payload byte 0x00 means
    # "256 bytes" (matches the Setup block's real size), not "0 bytes"
    frame = fw.build_read_request(fw.CMD_DEVICE_READ, addr=0x7C00, length=256)
    assert frame == bytes.fromhex("2f3a7c000100843d")


def test_parse_reply_256_byte_length_zero_encoding():
    # length byte 0x00 in a reply means 256 payload bytes follow
    payload = bytes(range(256))[:256]
    body = bytes([fw.ESCAPE_DEVICE, fw.CMD_DEVICE_READ, 0x7C, 0x00, 0x00]) + payload + bytes([fw.ACK_OK])
    crc = fw._crc_xmodem(body)
    frame = body + bytes([(crc >> 8) & 0xFF, crc & 0xFF])
    reply = fw.parse_reply(frame)
    assert len(reply["payload"]) == 256
    assert reply["addr"] == 0x7C00


def test_parse_reply_bad_crc_raises():
    frame = bytearray(bytes.fromhex("2e310000016c004f25"))
    frame[-1] ^= 0xFF
    with pytest.raises(fw.FourWayError):
        fw.parse_reply(bytes(frame))


def test_parse_reply_non_ok_ack_raises():
    body = bytes([fw.ESCAPE_DEVICE, fw.CMD_DEVICE_RESET, 0, 0, 1, 0x00, fw.ACK_D_GENERAL_ERROR])
    crc = fw._crc_xmodem(body)
    frame = body + bytes([(crc >> 8) & 0xFF, crc & 0xFF])
    with pytest.raises(fw.FourWayError):
        fw.parse_reply(frame)


def test_parse_reply_wrong_escape_byte_raises():
    with pytest.raises(fw.FourWayError):
        fw.parse_reply(bytes.fromhex("2f31000001006c004f25"))


def test_parse_reply_too_short_raises():
    with pytest.raises(fw.FourWayError):
        fw.parse_reply(bytes.fromhex("2e31"))


def test_crc_xmodem_matches_published_test_vector():
    assert fw._crc_xmodem(b"123456789") == 0x31C3


def test_exit_interface_sends_correct_frame(monkeypatch=None):
    from fakes import FakeTransport

    # real-shaped exit ack: cmd=0x34, param_len=1, payload=[0], ack=OK
    body = bytes([fw.ESCAPE_DEVICE, fw.CMD_INTERFACE_EXIT, 0, 0, 1, 0x00, fw.ACK_OK])
    crc = fw._crc_xmodem(body)
    reply = body + bytes([(crc >> 8) & 0xFF, crc & 0xFF])
    transport = FakeTransport([reply])
    fw.exit_interface(transport)
    assert transport.sent[0] == fw.build_request(fw.CMD_INTERFACE_EXIT)


def test_exit_interface_no_reply_raises():
    from fakes import FakeTransport

    transport = FakeTransport([b""])
    with pytest.raises(fw.FourWayError):
        fw.exit_interface(transport)


def _ack_reply(cmd, payload=b"\x00", ack=None):
    body = bytes([fw.ESCAPE_DEVICE, cmd, 0, 0, len(payload)]) + payload + bytes([ack if ack is not None else fw.ACK_OK])
    crc = fw._crc_xmodem(body)
    return body + bytes([(crc >> 8) & 0xFF, crc & 0xFF])


def test_enter_4way_if_returns_esc_count():
    from fakes import FakeTransport

    # real captured MSP_SET_PASSTHROUGH reply from BLHeliSuite32xl: 4 ESCs found
    transport = FakeTransport([bytes.fromhex("244d3e01f504f0")])
    count = fw.enter_4way_if(transport)
    assert count == 4
    assert transport.sent[0] == bytes.fromhex("244d3c00f5f5")


def test_enter_4way_if_no_reply_raises():
    from fakes import FakeTransport

    transport = FakeTransport([b""])
    with pytest.raises(fw.FourWayError):
        fw.enter_4way_if(transport)


def test_connect_esc_sends_set_mode_reset_init_and_returns_signature():
    from fakes import FakeTransport

    set_mode_reply = _ack_reply(fw.CMD_INTERFACE_SET_MODE)
    reset_reply = _ack_reply(fw.CMD_DEVICE_RESET)
    # real captured cmd_DeviceInitFlash reply: signature 06 33 68 04
    init_flash_reply = bytes.fromhex("2e370000040633680400c74f")

    transport = FakeTransport([set_mode_reply, reset_reply, init_flash_reply])
    signature = fw.connect_esc(transport, esc_index=0)
    assert signature == bytes.fromhex("06336804")
    assert transport.sent[0] == fw.build_request(fw.CMD_INTERFACE_SET_MODE, payload=bytes([fw.DEVICE_ARM_BLB]))
    assert transport.sent[1] == fw.build_request(fw.CMD_DEVICE_RESET, payload=bytes([0]))
    assert transport.sent[2] == fw.build_request(fw.CMD_DEVICE_INIT_FLASH, payload=bytes([0]))


def test_connect_esc_no_esc_at_channel_raises_after_all_attempts():
    from fakes import FakeTransport

    transport = FakeTransport(
        [
            _ack_reply(fw.CMD_INTERFACE_SET_MODE),
            _ack_reply(fw.CMD_DEVICE_RESET),
            _ack_reply(fw.CMD_DEVICE_INIT_FLASH, ack=fw.ACK_D_GENERAL_ERROR),
            _ack_reply(fw.CMD_DEVICE_RESET),
            _ack_reply(fw.CMD_DEVICE_INIT_FLASH, ack=fw.ACK_D_GENERAL_ERROR),
        ]
    )
    with pytest.raises(fw.FourWayError):
        fw.connect_esc(transport, esc_index=1, attempts=2, retry_delay=0)


def test_connect_esc_single_attempt_raises_immediately():
    from fakes import FakeTransport

    transport = FakeTransport(
        [
            _ack_reply(fw.CMD_INTERFACE_SET_MODE),
            _ack_reply(fw.CMD_DEVICE_RESET),
            _ack_reply(fw.CMD_DEVICE_INIT_FLASH, ack=fw.ACK_D_GENERAL_ERROR),
        ]
    )
    with pytest.raises(fw.FourWayError):
        fw.connect_esc(transport, esc_index=1, attempts=1)
    # only one reset+init-flash pair sent, no retry
    assert len(transport.sent) == 3


def test_connect_esc_succeeds_on_retry_after_first_attempt_fails():
    from fakes import FakeTransport

    transport = FakeTransport(
        [
            _ack_reply(fw.CMD_INTERFACE_SET_MODE),
            _ack_reply(fw.CMD_DEVICE_RESET),
            _ack_reply(fw.CMD_DEVICE_INIT_FLASH, ack=fw.ACK_D_GENERAL_ERROR),
            _ack_reply(fw.CMD_DEVICE_RESET),
            bytes.fromhex("2e370000040633680400c74f"),  # real signature, second attempt
        ]
    )
    signature = fw.connect_esc(transport, esc_index=2, attempts=2, retry_delay=0)
    assert signature == bytes.fromhex("06336804")
    # set-mode once, then reset+init-flash twice (one failed, one succeeded)
    assert len(transport.sent) == 5


def test_read_flash_setup_block_request_and_payload():
    from fakes import FakeTransport

    payload = bytes(range(256))
    body = bytes([fw.ESCAPE_DEVICE, fw.CMD_DEVICE_READ, 0x7C, 0x00, 0x00]) + payload + bytes([fw.ACK_OK])
    crc = fw._crc_xmodem(body)
    reply = body + bytes([(crc >> 8) & 0xFF, crc & 0xFF])

    transport = FakeTransport([reply])
    result = fw.read_flash(transport, addr=0x7C00, length=256)
    assert result == payload
    # real captured cmd_DeviceRead request for the Setup block
    assert transport.sent[0] == bytes.fromhex("2f3a7c000100843d")

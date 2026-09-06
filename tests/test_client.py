"""BLHeliClient tests using a FakeTransport scripted with real captured replies."""

import pytest

from blheli32proxy.protocol.client import BLHeliClient, BLHeliProtocolError, SetupBlock
from blheli32proxy.protocol import frames
from fakes import FakeTransport


def test_connect_success():
    transport = FakeTransport([bytes.fromhex("3437316A3306070430")])
    client = BLHeliClient(transport)
    reply = client.connect()
    assert reply.prefix == "471"
    assert reply.device_type == 0x3306
    assert transport.sent[0].endswith(bytes.fromhex("0D424C48656C69F47D"))


def test_connect_no_reply_raises():
    transport = FakeTransport([b""])
    client = BLHeliClient(transport)
    with pytest.raises(BLHeliProtocolError):
        client.connect()


def test_prime_connection_swallows_failure_and_disconnects_on_success(monkeypatch):
    from blheli32proxy.protocol import client as client_module

    slept = []
    monkeypatch.setattr(client_module.time, "sleep", lambda s: slept.append(s))

    # First connect attempt fails (no reply), so prime_connection should not
    # attempt a disconnect afterward.
    transport = FakeTransport([b""])
    client = BLHeliClient(transport)
    client.prime_connection()
    assert len(transport.sent) == 1  # only the connect attempt, no disconnect
    assert client_module.POST_FAIL_RECONNECT_DELAY_S in slept

    # Second scenario: connect succeeds, so a disconnect should follow.
    transport2 = FakeTransport([bytes.fromhex("3437316A3306070430"), bytes([frames.ACK])])
    client2 = BLHeliClient(transport2)
    client2.prime_connection()
    assert len(transport2.sent) == 2
    assert transport2.sent[1] == frames.disconnect_request()


def test_keepalive_and_disconnect():
    transport = FakeTransport([bytes([0xC1]), bytes([frames.ACK])])
    client = BLHeliClient(transport)
    client.keepalive()
    client.disconnect()
    assert transport.sent[0] == frames.keepalive_request()
    assert transport.sent[1] == frames.disconnect_request()


def test_read_setup_block_full_cycle():
    ciphertext = bytes([0x42]) * 256
    from blheli32proxy.protocol.crc import crc_bytes

    read_reply = ciphertext + crc_bytes(ciphertext) + bytes([frames.ACK])
    transport = FakeTransport(
        [
            bytes([frames.ACK]),  # set-address ack
            read_reply,  # read reply
        ]
    )
    client = BLHeliClient(transport)
    block = client.read_setup_block()
    assert block.ciphertext == ciphertext
    assert transport.sent[0] == frames.set_address_request(frames.ADDR_SETUP_BLOCK)
    assert transport.sent[1] == frames.read_request(256)


def test_read_activation_status_and_device_info_addresses():
    transport = FakeTransport(
        [
            bytes([frames.ACK]),
            bytes(16) + bytes.fromhex("0000") + bytes([frames.ACK]),
        ]
    )
    client = BLHeliClient(transport)
    client.read_activation_status_raw()
    assert transport.sent[0] == frames.set_address_request(frames.ADDR_ACTIVATION_STATUS)

    transport2 = FakeTransport(
        [
            bytes([frames.ACK]),
            bytes(16) + bytes.fromhex("0000") + bytes([frames.ACK]),
        ]
    )
    client2 = BLHeliClient(transport2)
    client2.read_device_info_raw()
    assert transport2.sent[0] == frames.set_address_request(frames.ADDR_DEVICE_INFO)


def test_write_setup_block_full_cycle():
    transport = FakeTransport(
        [
            bytes([frames.ACK]),  # set-address ack
            bytes([frames.ACK]),  # write-payload ack (no ack for header alone)
            bytes([frames.ACK]),  # commit ack
        ]
    )
    client = BLHeliClient(transport)
    client.write_setup_block(SetupBlock(bytes([0x99] * 256)))
    assert transport.sent[0] == frames.set_address_request(frames.ADDR_SETUP_BLOCK)
    assert transport.sent[1] == frames.write_header_request()
    assert transport.sent[2] == frames.write_payload(bytes([0x99] * 256))
    assert transport.sent[3] == frames.commit_request()


def test_write_setup_block_raises_on_missing_ack():
    transport = FakeTransport([b"\x00", b"", b""])
    client = BLHeliClient(transport)
    with pytest.raises(BLHeliProtocolError):
        client.write_setup_block(SetupBlock(bytes(256)))


def test_flash_firmware_not_implemented():
    transport = FakeTransport([])
    client = BLHeliClient(transport)
    with pytest.raises(NotImplementedError):
        client.flash_firmware(b"\x00" * 100)


def test_read_flash_region_experimental_small_length():
    from blheli32proxy.protocol.crc import crc_bytes

    payload = bytes([0x11] * 16)
    transport = FakeTransport(
        [
            bytes([frames.ACK]),  # set-address ack
            payload + crc_bytes(payload) + bytes([frames.ACK]),  # read reply
        ]
    )
    client = BLHeliClient(transport)
    result = client.read_flash_region_experimental(0x0000, 16)
    assert result == payload
    assert transport.sent[0] == frames.set_address_request(0x0000)
    assert transport.sent[1] == frames.read_request(16, allow_experimental=True)


def test_read_flash_region_experimental_rejects_bad_length():
    client = BLHeliClient(FakeTransport([]))
    with pytest.raises(ValueError):
        client.read_flash_region_experimental(0x0000, 0)
    with pytest.raises(ValueError):
        client.read_flash_region_experimental(0x0000, 300)


def test_dump_flash_experimental_iterates_chunks():
    from blheli32proxy.protocol.crc import crc_bytes

    chunk_a = bytes([0xAA] * 10)
    chunk_b = bytes([0xBB] * 6)
    transport = FakeTransport(
        [
            bytes([frames.ACK]),
            chunk_a + crc_bytes(chunk_a) + bytes([frames.ACK]),
            bytes([frames.ACK]),
            chunk_b + crc_bytes(chunk_b) + bytes([frames.ACK]),
        ]
    )
    client = BLHeliClient(transport)
    chunks = list(client.dump_flash_experimental(0x0000, 0x0010, chunk_size=10))
    assert chunks == [(0x0000, chunk_a), (0x000A, chunk_b)]


def test_dump_flash_experimental_stops_on_failure():
    transport = FakeTransport([bytes([frames.ACK]), b""])  # second step: no reply at all
    client = BLHeliClient(transport)
    gen = client.dump_flash_experimental(0x0000, 0x0100, chunk_size=256)
    # parse_read_reply raises ValueError for a malformed/short reply (see frames.py) —
    # this propagates as-is rather than a partial/silently-truncated dump.
    with pytest.raises(ValueError):
        list(gen)

"""CRC-16/IBM tests using real byte sequences captured in the research notes.

Each vector is (payload, expected_crc_low_byte_first) taken verbatim from
research/notes/BLHeli-Uart-Usb-Protocol.en.md's worked frame captures. This is ground
truth from a real BLHeli32 ESC, not a value derived from the implementation itself.
"""

from blheli32proxy.protocol.crc import crc_bytes, crc16_ibm

VECTORS = [
    (bytes.fromhex("424C48656C69"), bytes.fromhex("F47D")),  # connect: "BLHeli"
    (bytes.fromhex("0001"), bytes.fromhex("C1C0")),  # disconnect header
    (bytes.fromhex("FD00"), bytes.fromhex("4090")),  # keep-alive
    (bytes.fromhex("FF007C00"), bytes.fromhex("10D4")),  # set address 0x7C00
    (bytes.fromhex("0300"), bytes.fromhex("00F0")),  # read 256 bytes
    (bytes.fromhex("FF00EB00"), bytes.fromhex("7EE4")),  # set address 0xEB00
    (bytes.fromhex("0310"), bytes.fromhex("013C")),  # read 16 bytes
    (bytes.fromhex("FF00F7AC"), bytes.fromhex("7659")),  # set address 0xF7AC
    (bytes.fromhex("FE000100"), bytes.fromhex("3078")),  # write header
    (bytes.fromhex("0101"), bytes.fromhex("C050")),  # commit to flash
]


def test_crc_vectors_match_captured_frames():
    for payload, expected in VECTORS:
        assert crc_bytes(payload) == expected, payload.hex()


def test_crc16_ibm_matches_bytes_helper():
    for payload, expected in VECTORS:
        crc = crc16_ibm(payload)
        assert bytes((crc & 0xFF, (crc >> 8) & 0xFF)) == expected

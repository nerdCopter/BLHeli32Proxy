"""BLHeli32 UART wire-protocol frame construction and parsing.

Reference: research/notes/BLHeli-Uart-Usb-Protocol.en.md (the master protocol spec) and
research/notes/BLH-Uart-Timeout.en.md (timing quirks). All byte sequences below were
taken verbatim from real captured traffic documented there.
"""

from __future__ import annotations

from dataclasses import dataclass

from .crc import append_crc

# The literal bytes that matter in the connect handshake: ASCII "BLHeli" + CRC.
# A run of 0x00 bytes may precede this to force the ESC into an all-zero-output
# state first; omit it if the caller's own output is already at zero (see
# BLHeli-Uart-Usb-Protocol.en.md, "Connect"). The exact zero-run length is NOT a
# fixed protocol constant: two independently captured transcripts in the research
# show 8 and 12 leading zero bytes respectively, both preceding the same 0x0D
# marker and "BLHeli" body — treat 12 below as a safe default, not a spec value.
_CONNECT_BODY = b"\x42\x4c\x48\x65\x6c\x69"  # "BLHeli"
CONNECT_ZERO_PREAMBLE = bytes(12)

ADDR_SETUP_BLOCK = 0x7C00  # 256-byte encrypted config/"Setup" block
ADDR_ACTIVATION_STATUS = 0xEB00  # 16 bytes; confirmed via BLHeliSuite32's own debug log
ADDR_DEVICE_INFO = 0xF7AC  # 16 bytes; constant, embeds an ASCII device-info string

SETUP_BLOCK_SIZE = 256
SHORT_BLOCK_SIZE = 16

ACK = 0x30


def connect_request(*, with_zero_preamble: bool = True) -> bytes:
    """Build the connect handshake frame."""
    body = append_crc(_CONNECT_BODY)
    if with_zero_preamble:
        return CONNECT_ZERO_PREAMBLE + b"\x0d" + body
    return body


def keepalive_request() -> bytes:
    return append_crc(b"\xfd\x00")


def disconnect_request() -> bytes:
    return append_crc(b"\x00\x01")


def set_address_request(address: int) -> bytes:
    """Build a 'set address' frame for a subsequent read or write."""
    if not 0 <= address <= 0xFFFF:
        raise ValueError(f"address out of range: {address:#x}")
    return append_crc(bytes((0xFF, 0x00, (address >> 8) & 0xFF, address & 0xFF)))


def read_request(length: int, *, allow_experimental: bool = False) -> bytes:
    """Build a 'read N bytes' frame.

    Only two lengths are CONFIRMED from real captured traffic: 256 (encoded as
    length byte 0x00) and 16 (encoded as length byte 0x10) — see
    research/notes/BLHeli-Uart-Usb-Protocol.en.md. Those two data points are
    consistent with a common embedded-firmware convention: an 8-bit count field
    where 0x00 means "256" (wraps) and any other value N (1-255) means N bytes
    directly. `allow_experimental=True` extends the frame builder to that
    inferred general rule for any length in 1-256 — this is EXTRAPOLATION, not
    confirmed protocol, and is used by protocol/client.py's explicitly-named
    experimental read functions only. A wrong guess here fails safely: the
    reply's CRC/ACK check (parse_read_reply) will reject a malformed response
    rather than silently accepting garbage.
    """
    if length == SETUP_BLOCK_SIZE:
        length_byte = 0x00
    elif length == SHORT_BLOCK_SIZE:
        length_byte = 0x10
    elif allow_experimental and 1 <= length <= 256:
        length_byte = 0 if length == 256 else length
    else:
        raise ValueError(
            f"unsupported read length: {length} (only 16/256 are confirmed; "
            f"pass allow_experimental=True for other lengths 1-256)"
        )
    return append_crc(bytes((0x03, length_byte)))


def write_header_request() -> bytes:
    """Header for a 256-byte write. No ACK follows this alone — send the
    256-byte payload (see write_payload) immediately after, without waiting."""
    return append_crc(bytes((0xFE, 0x00, 0x01, 0x00)))


def write_payload(data: bytes) -> bytes:
    """The 256-byte config payload plus its own CRC, sent right after the write header."""
    if len(data) != SETUP_BLOCK_SIZE:
        raise ValueError(f"write payload must be {SETUP_BLOCK_SIZE} bytes, got {len(data)}")
    return append_crc(data)


def commit_request() -> bytes:
    """Commit a previously-written config payload to flash/EEPROM."""
    return append_crc(bytes((0x01, 0x01)))


# Known device/bootloader-type codes (big-endian uint16), from the reference host
# source quoted in BLHeli-Uart-Usb-Protocol.en.md. The connect reply's only fully
# decoded real-world example places one of these values at bytes [4:6] of the reply,
# but bytes [3] and [6:8] in that same example are NOT explained by the source
# material at all (the original blog post glosses over them). Rather than assume a
# fixed offset that might not hold for other ESCs/bootloaders, this scans the whole
# reply for a matching code instead of hardcoding its position — see
# research/notes/BLHeli-Uart-Usb-Protocol.en.md for the full table and this caveat.
DEVICE_TYPE_ATM_BLB = {0x9307, 0x930A, 0x930F, 0x940B}
DEVICE_TYPE_SIL_BLB = {0xF310, 0xF330, 0xF410, 0xF390, 0xF850, 0xE8B1, 0xE8B2}
DEVICE_TYPE_ARM_BLB = {0x1F06, 0x3306, 0x3406, 0x3506, 0x2B06, 0x4706}
KNOWN_DEVICE_TYPES = DEVICE_TYPE_ATM_BLB | DEVICE_TYPE_SIL_BLB | DEVICE_TYPE_ARM_BLB


@dataclass(frozen=True)
class ConnectReply:
    prefix: str
    device_type: int | None
    raw: bytes
    ack: int

    @property
    def ok(self) -> bool:
        return self.ack == ACK


def parse_connect_reply(data: bytes) -> ConnectReply:
    """Parse a connect reply. No CRC is present on this reply (see protocol notes).

    `device_type` is best-effort: it's found by scanning the reply for a known
    device/bootloader-type code (see KNOWN_DEVICE_TYPES), not read from a fixed
    offset, because the one real capture this is based on has unexplained bytes
    around it. It is None if no known code is found — callers should not treat
    that as an error on its own.
    """
    if len(data) < 4:
        raise ValueError(f"connect reply too short: {len(data)} bytes")
    prefix = data[0:3].decode("ascii", errors="replace")
    ack = data[-1]
    device_type = None
    for i in range(len(data) - 1):
        candidate = (data[i] << 8) | data[i + 1]
        if candidate in KNOWN_DEVICE_TYPES:
            device_type = candidate
            break
    return ConnectReply(prefix=prefix, device_type=device_type, raw=data, ack=ack)


def parse_read_reply(data: bytes, length: int) -> bytes:
    """Validate and extract the payload from a read reply (payload + 2-byte CRC + 1-byte ACK)."""
    expected_len = length + 3
    if len(data) != expected_len:
        raise ValueError(f"read reply must be {expected_len} bytes, got {len(data)}")
    payload, crc_field, ack = data[:length], data[length : length + 2], data[length + 2]
    from .crc import crc_bytes

    if crc_bytes(payload) != crc_field:
        raise ValueError("read reply CRC mismatch")
    if ack != ACK:
        raise ValueError(f"read reply not ACKed: {ack:#x}")
    return payload

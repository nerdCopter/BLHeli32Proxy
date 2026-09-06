"""CRC-16/IBM (a.k.a. CRC-16/ARC) as used by the BLHeli32 UART protocol.

Reference: research/notes/BLHeli-Uart-Usb-Protocol.en.md. Transmitted low byte first,
then high byte.
"""

from __future__ import annotations


def crc16_ibm(data: bytes) -> int:
    """Compute CRC-16/IBM over data. Returns the 16-bit CRC value."""
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF


def append_crc(data: bytes) -> bytes:
    """Return data with its CRC-16/IBM appended, low byte first."""
    crc = crc16_ibm(data)
    return data + bytes((crc & 0xFF, (crc >> 8) & 0xFF))


def crc_bytes(data: bytes) -> bytes:
    """CRC-16/IBM of data as 2 wire bytes, low byte first."""
    crc = crc16_ibm(data)
    return bytes((crc & 0xFF, (crc >> 8) & 0xFF))

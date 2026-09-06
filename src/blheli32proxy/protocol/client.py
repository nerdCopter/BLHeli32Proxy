"""High-level BLHeli32 protocol client.

Implements the connect/keepalive/disconnect/read/write sequences documented in
research/notes/BLHeli-Uart-Usb-Protocol.en.md and the timing workaround from
research/notes/BLH-Uart-Timeout.en.md, on top of a Transport.

IMPORTANT SCOPE NOTE: this client can read and write the 256-byte Setup/config
block (address 0x7C00) — that protocol is fully documented and covered by tests
using real captured byte sequences. It CANNOT yet flash a full firmware image:
the research corpus documents the config-block write (256 bytes, one fixed
address) but never captured the byte-level protocol for writing a full firmware
image to flash (the debug log in BLHeliSuite32-Reverse.en.md shows a 1024-byte
flash page size, a different granularity than the config write, and the exact
command sequence for it was never captured live). See PLAN.md §5 phase 1 and §6.
`flash_firmware()` raises NotImplementedError until that protocol is captured
and verified against real hardware — it must not be guessed at, since a wrong
flash-write sequence risks bricking an ESC.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from . import frames
from .transport import Transport

CONNECT_TIMEOUT_S = 2.0
READ_TIMEOUT_S = 1.0
INTER_COMMAND_DELAY_S = 0.001  # 1ms; see BLHeli-Uart-Usb-Protocol.en.md
POST_FAIL_RECONNECT_DELAY_S = 5.0  # see BLH-Uart-Timeout.en.md


class BLHeliProtocolError(RuntimeError):
    """Raised when the ESC doesn't respond as the protocol requires."""


@dataclass
class SetupBlock:
    """The 256-byte Setup block, still encrypted. Use blheli32proxy.cipher.xtea to
    decrypt/encrypt its content — this client only moves bytes, it doesn't know
    about the cipher (see PLAN.md §3.3 for why those are kept separate)."""

    ciphertext: bytes


class BLHeliClient:
    def __init__(self, transport: Transport):
        self._transport = transport
        self._connected = False

    def _send(self, data: bytes) -> None:
        self._transport.write(data)
        time.sleep(INTER_COMMAND_DELAY_S)

    def prime_connection(self) -> None:
        """Send a throwaway connect+disconnect to absorb BLHeli 31.80+'s guaranteed
        first-attempt failure after power-on (see BLH-Uart-Timeout.en.md). Call this
        once right after power-on, before the real connect() you intend to use.

        Blocks for POST_FAIL_RECONNECT_DELAY_S: the firmware ignores any connect
        sent within that window after a failed attempt, so the caller's next
        connect() must land after it, not immediately after this call returns."""
        try:
            self.connect()
        except BLHeliProtocolError:
            pass
        else:
            self.disconnect()
        time.sleep(POST_FAIL_RECONNECT_DELAY_S)

    def connect(self) -> frames.ConnectReply:
        self._send(frames.connect_request())
        reply_bytes = self._transport.read(9, CONNECT_TIMEOUT_S)
        if len(reply_bytes) < 4:
            raise BLHeliProtocolError(
                f"no usable connect reply (got {len(reply_bytes)} bytes) — "
                f"if this is the first attempt after ESC power-on, call "
                f"prime_connection() first and wait {POST_FAIL_RECONNECT_DELAY_S}s"
            )
        reply = frames.parse_connect_reply(reply_bytes)
        if not reply.ok:
            raise BLHeliProtocolError(f"connect not ACKed: {reply}")
        self._connected = True
        return reply

    def keepalive(self) -> None:
        self._send(frames.keepalive_request())
        self._transport.read(1, READ_TIMEOUT_S)

    def disconnect(self) -> None:
        self._send(frames.disconnect_request())
        self._transport.read(1, READ_TIMEOUT_S)
        self._connected = False

    def _read_region(self, address: int, length: int, *, experimental: bool = False) -> bytes:
        self._send(frames.set_address_request(address))
        ack = self._transport.read(1, READ_TIMEOUT_S)
        if ack != bytes([frames.ACK]):
            raise BLHeliProtocolError(f"set-address({address:#x}) not ACKed: {ack!r}")
        self._send(frames.read_request(length, allow_experimental=experimental))
        reply = self._transport.read(length + 3, READ_TIMEOUT_S)
        return frames.parse_read_reply(reply, length)

    def read_setup_block(self) -> SetupBlock:
        """Read the 256-byte encrypted Setup/config block at 0x7C00."""
        return SetupBlock(self._read_region(frames.ADDR_SETUP_BLOCK, frames.SETUP_BLOCK_SIZE))

    def read_activation_status_raw(self) -> bytes:
        """Read the 16-byte block at 0xEB00 — confirmed activation-status data by
        BLHeliSuite32's own debug log, but its exact field layout is not decoded
        in the research corpus. Returns the raw bytes for further analysis."""
        return self._read_region(frames.ADDR_ACTIVATION_STATUS, frames.SHORT_BLOCK_SIZE)

    def read_device_info_raw(self) -> bytes:
        """Read the 16-byte block at 0xF7AC — constant per device, embeds an ASCII
        identifier string. See BLHeli-Uart-Usb-Protocol.en.md."""
        return self._read_region(frames.ADDR_DEVICE_INFO, frames.SHORT_BLOCK_SIZE)

    def write_setup_block(self, block: SetupBlock) -> None:
        """Write and commit a 256-byte encrypted Setup/config block to 0x7C00."""
        self._send(frames.set_address_request(frames.ADDR_SETUP_BLOCK))
        ack = self._transport.read(1, READ_TIMEOUT_S)
        if ack != bytes([frames.ACK]):
            raise BLHeliProtocolError(f"set-address(0x7C00) not ACKed: {ack!r}")

        # No ACK follows the header alone — send header + payload back to back
        # without waiting in between (see BLHeli-Uart-Usb-Protocol.en.md).
        self._transport.write(frames.write_header_request())
        self._transport.write(frames.write_payload(block.ciphertext))
        time.sleep(INTER_COMMAND_DELAY_S)
        ack = self._transport.read(1, READ_TIMEOUT_S)
        if ack != bytes([frames.ACK]):
            raise BLHeliProtocolError(f"write payload not ACKed: {ack!r}")

        self._send(frames.commit_request())
        ack = self._transport.read(1, READ_TIMEOUT_S)
        if ack != bytes([frames.ACK]):
            raise BLHeliProtocolError(f"commit not ACKed: {ack!r}")

    def read_flash_region_experimental(self, address: int, length: int = 256) -> bytes:
        """Read up to 256 bytes starting at an arbitrary address, using the
        EXPERIMENTAL length encoding (see frames.read_request) — not confirmed
        by the research beyond the two known addresses/lengths used elsewhere in
        this client. Safe to attempt (read-only; a wrong length-encoding guess
        is caught by the reply's CRC/ACK check, not by anything hardware-level),
        but may simply fail or return meaningless data if this ESC's bootloader
        restricts reads to specific whitelisted addresses (a common,
        intentional anti-cloning measure — see PLAN.md's firmware-extraction
        discussion). Always try a small length (e.g. 16) at the address you
        care about first, and sanity-check the result, before reading a large
        range with dump_flash_experimental().
        """
        if not 1 <= length <= 256:
            raise ValueError(f"length must be 1-256, got {length}")
        return self._read_region(address, length, experimental=True)

    def dump_flash_experimental(self, start: int, end: int, chunk_size: int = 256):
        """Yield (address, chunk_bytes) for consecutive chunks covering [start, end).
        EXPERIMENTAL — see read_flash_region_experimental(). Stops and re-raises
        on the first read failure rather than silently producing a partial/
        corrupt dump; the caller sees exactly how far it got via the exception
        context and whatever was already yielded.
        """
        if not 1 <= chunk_size <= 256:
            raise ValueError(f"chunk_size must be 1-256, got {chunk_size}")
        address = start
        while address < end:
            length = min(chunk_size, end - address)
            data = self.read_flash_region_experimental(address, length)
            yield address, data
            address += length

    def flash_firmware(self, firmware: bytes) -> None:
        """Not yet implemented — see the module docstring. Do not attempt to guess
        the flash-write protocol; capture and verify it against real hardware
        first (PLAN.md §5 phase 1), then implement and test it the same way the
        Setup-block read/write above were: against real captured byte sequences."""
        raise NotImplementedError(
            "Flashing a full firmware image is not yet implemented: the "
            "byte-level bootloader flash-write protocol was never captured in "
            "this project's research (only the 256-byte Setup-block write was). "
            "See PLAN.md §5 phase 1 and §6 before implementing this."
        )

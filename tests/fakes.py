"""Test doubles for the BLHeli32 protocol/client layer — no real hardware needed."""

from __future__ import annotations

from blheli32proxy.protocol.transport import Transport


class FakeTransport(Transport):
    """An in-memory Transport that plays back scripted replies.

    Construct with a list of reply bytes; each call to write() consumes the next
    scripted reply and makes it available to the following read() calls. This
    mirrors a real half-duplex link closely enough to test BLHeliClient's framing
    and timing logic without any real serial/HID device.
    """

    def __init__(self, scripted_replies: list[bytes] | None = None):
        self.sent: list[bytes] = []
        self._replies = list(scripted_replies or [])
        self._rx_buffer = bytearray()
        self.closed = False

    def write(self, data: bytes) -> None:
        self.sent.append(bytes(data))
        if self._replies:
            self._rx_buffer.extend(self._replies.pop(0))

    def read(self, size: int, timeout: float) -> bytes:
        result = bytes(self._rx_buffer[:size])
        del self._rx_buffer[:size]
        return result

    def close(self) -> None:
        self.closed = True

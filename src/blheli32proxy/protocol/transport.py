"""Transport abstraction for the BLHeli32 single-wire UART protocol.

Two real backends are provided: a plain serial port (works cross-platform via
pyserial, e.g. a Betaflight/Cleanflight passthrough exposed as a CDC-ACM port) and
a HID device (needed for adapters like the "FVT_linker" documented in
research/notes/BLHeliSuite32xl-local-binary-analysis.en.md, which use `hidraw`
rather than a plain serial port). Both are optional imports: only the backend
actually instantiated needs its library installed.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class Transport(ABC):
    """Byte-level duplex transport. All timing/protocol logic lives in BLHeliClient;
    a Transport only knows how to move bytes in and out."""

    @abstractmethod
    def write(self, data: bytes) -> None:
        """Send bytes to the device."""

    @abstractmethod
    def read(self, size: int, timeout: float) -> bytes:
        """Read up to `size` bytes, waiting at most `timeout` seconds. May return
        fewer bytes than requested if the timeout elapses first."""

    def close(self) -> None:  # pragma: no cover - default no-op
        pass

    def __enter__(self) -> "Transport":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()


class SerialTransport(Transport):
    """A plain serial port (e.g. /dev/ttyACM0, /dev/ttyUSB0, COM3) at 19200 8N1,
    per research/notes/BLHeli-Uart-Usb-Protocol.en.md."""

    def __init__(self, port: str, baudrate: int = 19200):
        try:
            import serial  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - exercised only without pyserial
            raise RuntimeError(
                "SerialTransport requires the 'pyserial' package (pip install pyserial)"
            ) from exc
        self._serial = serial.Serial(port, baudrate=baudrate, timeout=0)

    def write(self, data: bytes) -> None:
        self._serial.write(data)

    def read(self, size: int, timeout: float) -> bytes:
        self._serial.timeout = timeout
        return self._serial.read(size)

    def close(self) -> None:
        self._serial.close()


class HidTransport(Transport):
    """A HID-based single-wire adapter (e.g. the "FVT_linker", vendor 0x10c4).

    HID devices exchange fixed-size reports rather than a raw byte stream; this
    wrapper buffers received report data so callers can still read() arbitrary
    byte counts. The exact report framing is adapter-specific and not yet
    reverse-engineered in this project's research — see PLAN.md §6 open items.
    """

    def __init__(self, vendor_id: int, product_id: int, report_size: int = 64):
        try:
            import hid  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - exercised only without hidapi
            raise RuntimeError(
                "HidTransport requires the 'hid' package (pip install hid)"
            ) from exc
        self._report_size = report_size
        self._device = hid.device()
        self._device.open(vendor_id, product_id)
        self._device.set_nonblocking(True)
        self._buffer = bytearray()

    def write(self, data: bytes) -> None:
        padded = data.ljust(self._report_size, b"\x00")
        self._device.write(bytes([0]) + padded)  # leading 0 = no report ID

    def read(self, size: int, timeout: float) -> bytes:
        import time

        deadline = time.monotonic() + timeout
        while len(self._buffer) < size and time.monotonic() < deadline:
            chunk = self._device.read(self._report_size, timeout_ms=10)
            if chunk:
                self._buffer.extend(chunk)
        result = bytes(self._buffer[:size])
        del self._buffer[:size]
        return result

    def close(self) -> None:
        self._device.close()

"""MSP v1 framing, and the ESC-passthrough activation needed when talking to an
ESC through a flight controller's USB virtual COM port instead of a dedicated
USB-to-single-wire adapter.

Verified directly against real firmware source (not the blog research corpus,
which never covers FC-mediated access):
- EmuFlight 4.5-maintenance src/main/msp/msp.c (MSP_SET_PASSTHROUGH handling,
  mspFcSetPassthroughCommand) and src/main/drivers/serial_escserial.c
  (escEnablePassthrough, BAUDRATE_NORMAL = 19200).
- Betaflight (worktrees/review/pr-15496) src/main/msp/msp_protocol.h and
  src/main/drivers/serial_escserial.h — same command number and protocol
  constant, so this applies to either flight controller.

Once MSP_SET_PASSTHROUGH succeeds for PROTOCOL_BLHELI (mode=1), the flight
controller stops speaking MSP on that port and relays raw bytes to/from the
selected motor's signal wire at 19200 baud — the same wire-level protocol
protocol/frames.py and protocol/client.py already implement. No further MSP
framing applies after this point.

NOT THE REAL PATH: confirmed via usbmon capture (2026-09-04, see
docs/knowledge/protocol-reference.md) that this mode=1 relay never transmits a
single byte back to the host over USB CDC-ACM on real hardware, and needs a
physical power-cycle to recover from. BLHeliSuite32xl and AM32-Configurator
both use the *other* MSP_SET_PASSTHROUGH form instead — an empty-payload
request, which routes to MSP_PASSTHROUGH_ESC_4WAY (0xFF) and the framed
4-way-interface protocol (see protocol/fourwayif.py and
docs/knowledge/protocol-reference.md for the confirmed frame format). This
module's enable_esc_passthrough()/exit_esc_passthrough() are kept for
reference and tests only — do not wire them into the CLI's real ESC-access path.
"""

from __future__ import annotations

MSP_SET_PASSTHROUGH = 245
PROTOCOL_BLHELI = 1

# Exit-passthrough command byte, from serial_escserial.c's processExitCommand():
# an empty-payload MSP v1 request with this cmd byte breaks the firmware out of
# its passthrough relay loop and back to normal MSP — without it, the flight
# controller stays wedged in the relay loop until physically power-cycled.
MSP_EXIT_PASSTHROUGH = 0xF4


class MspError(RuntimeError):
    """Raised when an MSP request/reply doesn't parse or the FC rejects it."""


def build_request_v1(cmd: int, payload: bytes = b"") -> bytes:
    """Build an MSP v1 request frame: '$M<' + size + cmd + payload + checksum,
    checksum = XOR of size, cmd, and every payload byte."""
    body = bytes([len(payload), cmd]) + payload
    checksum = 0
    for byte in body:
        checksum ^= byte
    return b"$M<" + body + bytes([checksum])


def parse_reply_v1(data: bytes) -> tuple[int, bytes]:
    """Parse an MSP v1 reply frame ('$M>' success, '$M!' error), validating
    the checksum. Returns (cmd, payload); raises MspError on any mismatch."""
    if len(data) < 6:
        raise MspError(f"MSP reply too short ({len(data)} bytes)")
    if data[0:2] != b"$M":
        raise MspError(f"not an MSP v1 frame: {data[:3]!r}")
    direction = data[2:3]
    if direction not in (b">", b"!"):
        raise MspError(f"unexpected MSP direction byte {direction!r}")
    size = data[3]
    cmd = data[4]
    payload = data[5 : 5 + size]
    if len(payload) != size:
        raise MspError(f"MSP reply payload truncated: expected {size} bytes, got {len(payload)}")
    checksum_byte = data[5 + size]
    computed = 0
    for byte in bytes([size, cmd]) + payload:
        computed ^= byte
    if computed != checksum_byte:
        raise MspError(f"MSP checksum mismatch: computed {computed:#04x}, got {checksum_byte:#04x}")
    if direction == b"!":
        raise MspError(f"MSP command {cmd} returned an error reply")
    return cmd, payload


def enable_esc_passthrough(
    transport,
    motor_index: int,
    mode: int = PROTOCOL_BLHELI,
    timeout: float = 2.0,
) -> None:
    """Ask the flight controller on `transport` to relay motor `motor_index`'s
    signal wire as raw BLHeli UART. Must be called before any BLHeliClient use
    on the same transport; raises MspError if the FC doesn't ack."""
    transport.write(build_request_v1(MSP_SET_PASSTHROUGH, bytes([mode, motor_index])))
    header = transport.read(5, timeout)
    if len(header) < 5:
        raise MspError(
            f"no usable MSP passthrough reply (got {len(header)} bytes) — is --port "
            f"actually the flight controller's USB port, and is it armed/connected?"
        )
    size = header[3]
    rest = transport.read(size + 1, timeout)
    cmd, payload = parse_reply_v1(header + rest)
    if cmd != MSP_SET_PASSTHROUGH:
        raise MspError(f"unexpected MSP reply cmd {cmd}, expected {MSP_SET_PASSTHROUGH}")
    if not payload or payload[0] != 1:
        raise MspError(
            f"flight controller refused ESC passthrough for motor index {motor_index} "
            f"— check --motor-index is correct and that ESC is wired to that output"
        )


def exit_esc_passthrough(transport, timeout: float = 2.0) -> None:
    """Send the exit-passthrough command so the flight controller returns to
    normal MSP instead of staying wedged in its relay loop. Always call this
    (e.g. in a finally block) after enable_esc_passthrough, whether or not the
    BLHeli session that followed succeeded."""
    transport.write(build_request_v1(MSP_EXIT_PASSTHROUGH))
    header = transport.read(5, timeout)
    if len(header) < 5:
        raise MspError(f"no exit-passthrough reply (got {len(header)} bytes)")
    size = header[3]
    rest = transport.read(size + 1, timeout)
    parse_reply_v1(header + rest)

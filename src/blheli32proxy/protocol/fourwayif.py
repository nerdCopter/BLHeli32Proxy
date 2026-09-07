"""The framed 4-way-interface bootloader protocol, confirmed (2026-09-04, see
docs/knowledge/protocol-reference.md) as what BLHeliSuite32xl's "Betaflight/Cleanflight" option and
AM32-Configurator actually use over a flight controller's MSP_SET_PASSTHROUGH
(empty-payload request, routes to MSP_PASSTHROUGH_ESC_4WAY/esc4wayProcess) —
not protocol/msp.py's mode=1 raw relay, which is confirmed dead over USB.

Frame format, both directions: [ESCAPE][CMD][ADDR_H][ADDR_L][PARAM_LEN]
[PARAM_LEN bytes][ACK, reply only][CRC_HI][CRC_LO]. CRC is CRC-16/XMODEM
(poly 0x1021, init 0, no reflection) over every byte from ESCAPE through the
last payload/ACK byte, sent high-byte-first. ESCAPE is 0x2F host->FC,
0x2E FC->host.

Critical gotcha, confirmed against the real app's traffic: PARAM_LEN=0 hangs
the FC's parser (its payload read is a do-while that runs at least once
regardless of length, then underflows its countdown waiting for 254 more
bytes that never arrive). Argument-less commands always send PARAM_LEN=1 with
a single dummy 0x00 payload byte — build_request()'s default enforces this.
"""

from __future__ import annotations

ESCAPE_HOST = 0x2F
ESCAPE_DEVICE = 0x2E

CMD_PROTOCOL_GET_VERSION = 0x31
CMD_INTERFACE_GET_NAME = 0x32
CMD_INTERFACE_GET_VERSION = 0x33
CMD_INTERFACE_EXIT = 0x34
CMD_INTERFACE_SET_MODE = 0x3F

# device-type values for CMD_INTERFACE_SET_MODE, from serial_4way.h
DEVICE_SIL_BLB = 1
DEVICE_ATM_BLB = 2
DEVICE_ARM_BLB = 4
CMD_DEVICE_RESET = 0x35
CMD_DEVICE_INIT_FLASH = 0x37
CMD_DEVICE_ERASE_ALL = 0x38
CMD_DEVICE_PAGE_ERASE = 0x39
CMD_DEVICE_READ = 0x3A
CMD_DEVICE_WRITE = 0x3B
CMD_DEVICE_READ_EEPROM = 0x3D
CMD_DEVICE_WRITE_EEPROM = 0x3E
CMD_DEVICE_VERIFY = 0x40

FLASH_PAGE_SIZE = 1024  # DEFAULT for the STM32F0-family ESCs tested so far — not universal, a
# different MCU family may use a different page size. Callers targeting other hardware should
# pass an explicit page_size to page_erase() rather than assume this.
BOOTLOADER_END = 0x2000  # DEFAULT: every STM32F0-family firmware-update .Hex file checked so far
# starts no earlier than this. Not confirmed universal across every BLHeli32 MCU family — a
# different chip may have a differently-sized bootloader. The bootloader must never be written or
# erased regardless of chip; callers on different hardware should pass an explicit bootloader_end
# to write_flash()/page_erase() rather than trust this default.

ACK_OK = 0x00
ACK_I_INVALID_CMD = 0x02
ACK_I_INVALID_CRC = 0x03
ACK_D_GENERAL_ERROR = 0x0F


class FourWayError(RuntimeError):
    """Raised when a 4-way-if request/reply doesn't parse or isn't ACK_OK."""


def _crc_xmodem(data: bytes) -> int:
    crc = 0
    for byte in data:
        crc ^= byte << 8
        crc &= 0xFFFF
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def _length_byte(count: int) -> int:
    """0-255 maps directly; 256 (a full flash/Setup-block chunk) encodes as 0."""
    if count == 256:
        return 0
    if not 0 <= count <= 255:
        raise ValueError(f"length {count} out of range for a single 4-way-if frame")
    return count


def build_request(cmd: int, addr: int = 0, payload: bytes = b"\x00") -> bytes:
    """Build a host->FC request frame. `payload` defaults to a single dummy
    byte — never pass b"" (PARAM_LEN=0), it hangs the FC's parser."""
    if not payload:
        raise ValueError("payload must not be empty — PARAM_LEN=0 hangs the FC parser")
    addr_h, addr_l = (addr >> 8) & 0xFF, addr & 0xFF
    body = bytes([ESCAPE_HOST, cmd, addr_h, addr_l, _length_byte(len(payload))]) + payload
    crc = _crc_xmodem(body)
    return body + bytes([(crc >> 8) & 0xFF, crc & 0xFF])


def build_read_request(cmd: int, addr: int, length: int) -> bytes:
    """A device-read style request: a normal single-byte-payload request
    (PARAM_LEN=1) whose payload *value* carries the requested read length
    (1-255, or 0 meaning 256) — confirmed from a real captured cmd_DeviceRead
    frame, which is byte-identical to build_request()'s usual shape."""
    return build_request(cmd, addr, payload=bytes([_length_byte(length)]))


def parse_reply(data: bytes) -> dict:
    """Parse a FC->host reply frame. Returns a dict with cmd/addr/payload/ack.
    Raises FourWayError on a short frame, wrong escape byte, or bad CRC."""
    if len(data) < 8:
        raise FourWayError(f"4-way-if reply too short ({len(data)} bytes)")
    if data[0] != ESCAPE_DEVICE:
        raise FourWayError(f"not a 4-way-if reply frame: leading byte {data[0]:#04x}")
    cmd, addr_h, addr_l, param_len = data[1], data[2], data[3], data[4]
    param_count = 256 if param_len == 0 else param_len
    payload = data[5 : 5 + param_count]
    if len(payload) != param_count:
        raise FourWayError(
            f"4-way-if reply payload truncated: expected {param_count} bytes, got {len(payload)}"
        )
    if len(data) < 8 + param_count:
        raise FourWayError("4-way-if reply missing ACK/CRC bytes")
    ack = data[5 + param_count]
    crc_hi, crc_lo = data[6 + param_count], data[7 + param_count]
    body = data[0 : 6 + param_count]
    crc = _crc_xmodem(body)
    if (crc >> 8) != crc_hi or (crc & 0xFF) != crc_lo:
        raise FourWayError(f"4-way-if reply CRC mismatch: computed {crc:#06x}")
    if ack != ACK_OK:
        raise FourWayError(f"4-way-if command {cmd:#04x} returned ACK {ack:#04x} (not OK)")
    return {"cmd": cmd, "addr": (addr_h << 8) | addr_l, "payload": payload, "ack": ack}


def _send(transport, request: bytes, timeout: float = 2.0) -> dict:
    """Write a request and read back one parsed reply frame."""
    transport.write(request)
    header = transport.read(5, timeout)
    if len(header) < 5:
        raise FourWayError(f"no reply header (got {len(header)} bytes)")
    param_len = header[4]
    param_count = 256 if param_len == 0 else param_len
    rest = transport.read(param_count + 3, timeout)
    return parse_reply(header + rest)


def exit_interface(transport, timeout: float = 2.0) -> None:
    """Send cmd_InterfaceExit so the FC calls esc4wayRelease() and returns to
    normal MSP — always call this when done, in a finally block."""
    _send(transport, build_request(CMD_INTERFACE_EXIT), timeout)


def enter_4way_if(transport, timeout: float = 2.0) -> int:
    """Enter the 4-way-if bootloader protocol via an empty-payload
    MSP_SET_PASSTHROUGH request on an already-open Transport connected to a
    flight controller's USB port (see protocol/msp.py's MSP_SET_PASSTHROUGH
    for the raw frame). Returns the ESC count the FC reports. Caller must
    call exit_interface() when done, in a finally block."""
    from .msp import MspError, build_request_v1, parse_reply_v1, MSP_SET_PASSTHROUGH

    transport.write(build_request_v1(MSP_SET_PASSTHROUGH))
    header = transport.read(5, timeout)
    if len(header) < 5:
        raise FourWayError(f"no usable MSP passthrough reply (got {len(header)} bytes)")
    size = header[3]
    rest = transport.read(size + 1, timeout)
    try:
        _cmd, payload = parse_reply_v1(header + rest)
    except MspError as exc:
        raise FourWayError(f"MSP_SET_PASSTHROUGH failed: {exc}") from exc
    if not payload:
        raise FourWayError("MSP_SET_PASSTHROUGH reply carried no ESC-count byte")
    return payload[0]


def connect_esc(
    transport,
    esc_index: int,
    interface_mode: int = DEVICE_ARM_BLB,
    timeout: float = 2.0,
    attempts: int = 3,
    retry_delay: float = 5.5,
    reset_settle_delay: float = 0.1,
) -> bytes:
    """Select ESC `esc_index` (0-based) and connect to its bootloader: sets
    the interface mode, resets, then init-flashes. Returns the 4-byte device
    signature (confirmed layout: [sig_lo, sig_hi, device_id, interface_mode]
    — sig_lo is always 0x06 for a real BLHeli_32 ARM MCU). Raises
    FourWayError (ACK_D_GENERAL_ERROR under the hood) if no ESC answers at
    this channel index — a common, expected result on a multi-ESC board
    where only some outputs are wired to a real ESC.

    `reset_settle_delay` (100ms default) waits unconditionally between
    cmd_DeviceReset and cmd_DeviceInitFlash on every attempt — matches the
    real BLHeliSuite32xl app's own confirmed behavior (its saved debug log,
    2026-09-05, shows this exact wait on every connect, and zero connect
    failures across a full 4-ESC trace using it).

    Retries reset+init-flash up to `attempts` times. `retry_delay` defaults to
    5.5s, not a short backoff: the actual bootloader connect handshake
    (`serial_4way_avrootloader.c`'s `BL_ConnectEx`, the literal "BLHeli"
    connect string) has a documented real-firmware quirk
    (research/notes/BLH-Uart-Timeout.en.md) where the first attempt right
    after a reset reliably fails, and newer BLHeli firmware then enforces a
    ~5s lockout before it will honor a retry at all — confirmed live
    (2026-09-04) that a 0.3s retry delay failed consistently (still inside
    the lockout), while a 5.5s delay succeeded on the second attempt every
    time it was tried. Same ACK_D_GENERAL_ERROR as a genuinely empty channel
    either way, so that case can't be told apart from this one in advance."""
    import time

    _send(transport, build_request(CMD_INTERFACE_SET_MODE, payload=bytes([interface_mode])), timeout)
    last_error: FourWayError | None = None
    for attempt in range(attempts):
        if attempt:
            time.sleep(retry_delay)
        try:
            _send(transport, build_request(CMD_DEVICE_RESET, payload=bytes([esc_index])), timeout)
            time.sleep(reset_settle_delay)
            reply = _send(transport, build_request(CMD_DEVICE_INIT_FLASH, payload=bytes([esc_index])), timeout)
            return reply["payload"]
        except FourWayError as exc:
            last_error = exc
    raise last_error


def read_flash(transport, addr: int, length: int, timeout: float = 2.0) -> bytes:
    """Read up to 256 bytes starting at `addr` from the currently-connected
    ESC (call connect_esc() first). For the 256-byte Setup block, use
    read_flash(transport, 0x7C00, 256)."""
    reply = _send(transport, build_read_request(CMD_DEVICE_READ, addr, length), timeout)
    return reply["payload"]


def verify_flash(transport, addr: int, data: bytes, timeout: float = 2.0) -> bool:
    """Verify (cmd_DeviceVerify, 0x40) a candidate buffer against the ESC's
    real flash content at `addr`, without ever transmitting the real content
    back over the wire — the ESC's own bootloader compares internally and
    returns only ACK_OK (match) or an error ack (mismatch). Never writes or
    erases (confirmed, see docs/knowledge/hardware-findings.md's verify-oracle
    exploration). Returns True on a real match, False on any mismatch/error
    ack. Usable both for a normal same-content check and, address by address,
    as a byte-guessing oracle toward a firmware dump — RDP blocks raw
    cmd_DeviceRead, but this oracle still discriminates match/mismatch even
    at Read-blocked addresses (see docs/knowledge/hardware-findings.md's
    verify-oracle exploration)."""
    if not 1 <= len(data) <= 256:
        raise ValueError(f"verify length {len(data)} out of range (1-256 bytes per frame)")
    try:
        _send(transport, build_request(CMD_DEVICE_VERIFY, addr, payload=data), timeout)
        return True
    except FourWayError:
        return False


def discover_byte(transport, addr: int, timeout: float = 2.0) -> int | None:
    """Brute-force discover the real byte value at `addr` by trying every
    value 0-255 via verify_flash() until one matches — the last resort when
    no candidate covers this address at all. Up to 256 real round-trips for
    one byte; only reasonable for a small number of genuinely unresolved
    bytes, never a whole unknown region. Returns None (a real anomaly, not
    expected in normal operation) if no value 0-255 matches."""
    for value in range(256):
        if verify_flash(transport, addr, bytes([value]), timeout):
            return value
    return None


def page_erase(transport, page: int, timeout: float = 5.0, *, page_size: int = FLASH_PAGE_SIZE,
               bootloader_end: int = BOOTLOADER_END) -> None:
    """Erase one flash page (cmd_DevicePageErase, 0x39). Payload is the page
    number, not a byte address. NOT YET CONFIRMED against real hardware.

    `page_size` and `bootloader_end` default to the values confirmed for the
    STM32F0-family BLHeli32 ESCs tested so far (AK32, Furling32) — these are
    MCU-specific facts, not universal across every BLHeli32 ESC. A different
    ESC's MCU family may use a different flash page size or have its
    bootloader occupy a different address range; re-confirm both for any
    new hardware before trusting these defaults (Setup-block's ESC_CPU
    field, offset 0x60, identifies the real MCU — see hardware-findings.md).

    HARD SAFETY GUARD: refuses to erase any page overlapping the bootloader
    (below `bootloader_end`) — the bootloader must never be erased, no
    exceptions."""
    page_addr = page * page_size
    if page_addr < bootloader_end:
        raise ValueError(
            f"refusing to erase page {page} (addr {page_addr:#06x}) — overlaps the bootloader "
            f"region (below {bootloader_end:#06x}); the bootloader must never be erased"
        )
    _send(transport, build_request(CMD_DEVICE_PAGE_ERASE, payload=bytes([page])), timeout)


def write_flash(transport, addr: int, data: bytes, timeout: float = 5.0, *,
                 bootloader_end: int = BOOTLOADER_END) -> None:
    """Write up to 256 bytes starting at `addr` to the currently-connected
    ESC (call connect_esc() first). Caller is responsible for erasing the
    covering page(s) first via page_erase() — this function only writes.

    CONFIRMED against real hardware (2026-09-07, AK32, see
    docs/knowledge/hardware-findings.md): writing WITHOUT erasing first can
    silently corrupt a much larger region than the bytes given — a partial
    (8-byte) write of the 256-byte Setup block left the rest of that block
    at erased-flash sentinel values, consistent with an internal erase of a
    larger region (likely a full page) happening before the requested bytes
    are programmed. Confirmed repair strategy: write the COMPLETE structure
    (e.g. all 256 bytes of a Setup block) in one call rather than a partial
    range, so any such internal erase gets fully re-filled with valid data.
    The real BLHeliSuite32xl app never issues cmd_DeviceWrite at all in
    practice (see docs/knowledge/activation-licensing.md), for reasons
    traced to its own internal TFlashState logic, not the ESC bootloader
    itself — so this path has no vendor-app precedent to compare against.

    `bootloader_end` defaults to the value confirmed for the STM32F0-family
    BLHeli32 ESCs tested so far — a different ESC's MCU family may have its
    bootloader occupy a different range; re-confirm before trusting this
    default on new hardware.

    HARD SAFETY GUARD: refuses to write any range overlapping the bootloader
    (below `bootloader_end`) — the bootloader must never be overwritten, no
    exceptions."""
    if not 1 <= len(data) <= 256:
        raise ValueError(f"write length {len(data)} out of range (1-256 bytes per frame)")
    if addr < bootloader_end:
        raise ValueError(
            f"refusing to write at {addr:#06x} — overlaps the bootloader region (below "
            f"{bootloader_end:#06x}); the bootloader must never be overwritten"
        )
    _send(transport, build_request(CMD_DEVICE_WRITE, addr, payload=data), timeout)

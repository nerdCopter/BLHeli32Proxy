"""Minimal Intel HEX parser — enough to compare a .Hex file's contents against
real flash via cmd_DeviceVerify (see fourwayif.verify_flash), not to write or
assemble firmware. Read-only utility, no hardware access."""

from __future__ import annotations


def parse_intel_hex(path: str) -> dict[int, int]:
    """Returns {absolute_address: byte_value} for every data byte in the
    file. Only handles record types 0x00 (data), 0x01 (EOF), 0x04 (extended
    linear address) — the only ones BLHeli_32 test-firmware files use."""
    mem: dict[int, int] = {}
    base = 0
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line.startswith(":"):
                continue
            data = bytes.fromhex(line[1:])
            length = data[0]
            addr = int.from_bytes(data[1:3], "big")
            rectype = data[3]
            payload = data[4 : 4 + length]
            if rectype == 0x00:
                for i, b in enumerate(payload):
                    mem[base + addr + i] = b
            elif rectype == 0x04:
                base = int.from_bytes(payload, "big") << 16
            elif rectype == 0x01:
                break
    return mem


def encode_intel_hex(data: bytes, base_addr: int, line_length: int = 16) -> str:
    """Encode `data` (starting at `base_addr`) as Intel HEX text. Matches the
    convention confirmed against this project's own real candidate files
    (16 bytes/line, LF-only line endings, uppercase hex) — text size for a
    given address range depends only on this format, not on the actual byte
    values, so matching a candidate's exact text-file size is a FORMAT
    match, not by itself proof the bytes are correct."""
    lines = []
    addr = base_addr
    remaining = data
    current_bank = 0  # bank 0 is the implicit default — confirmed real files never emit an
    # extended-linear-address record for it, only when actually switching to a non-zero bank
    while remaining:
        bank = addr >> 16
        if bank != current_bank:
            payload = bank.to_bytes(2, "big")
            body = bytes([2, 0, 0, 0x04]) + payload
            checksum = (-sum(body)) & 0xFF
            lines.append(":" + body.hex().upper() + f"{checksum:02X}")
            current_bank = bank
        chunk, remaining = remaining[:line_length], remaining[line_length:]
        offset = addr & 0xFFFF
        body = bytes([len(chunk), (offset >> 8) & 0xFF, offset & 0xFF, 0x00]) + chunk
        checksum = (-sum(body)) & 0xFF
        lines.append(":" + body.hex().upper() + f"{checksum:02X}")
        addr += len(chunk)
    lines.append(":00000001FF")  # EOF record
    return "\n".join(lines) + "\n"


def encode_intel_hex_sparse(mem: dict[int, int], line_length: int = 16) -> str:
    """Encode a sparse {address: byte} mapping as Intel HEX text, emitting NO
    record at all for any address missing from `mem` — matches the real
    convention (a genuine gap in a real BLHeli_32 test-firmware file has no
    line for it, it isn't padded). Splits into contiguous runs first, then
    encodes each run the same way as encode_intel_hex(). Never call this
    with a dict built by padding gaps with a placeholder value — that would
    defeat the whole point."""
    if not mem:
        return ":00000001FF\n"
    addrs = sorted(mem)
    runs: list[tuple[int, bytes]] = []
    run_start = addrs[0]
    run_bytes = bytearray([mem[addrs[0]]])
    for a in addrs[1:]:
        if a == run_start + len(run_bytes):
            run_bytes.append(mem[a])
        else:
            runs.append((run_start, bytes(run_bytes)))
            run_start = a
            run_bytes = bytearray([mem[a]])
    runs.append((run_start, bytes(run_bytes)))

    text = ""
    for start, data in runs:
        encoded = encode_intel_hex(data, start, line_length)
        text += encoded.rsplit(":00000001FF", 1)[0]  # strip each run's own EOF, add one at the very end
    return text + ":00000001FF\n"


def chunk_at(mem: dict[int, int], addr: int, length: int) -> bytes | None:
    """Returns `length` bytes starting at `addr`, or None if any byte in that
    range is missing from the file (a real gap, not fabricated filler —
    never silently substitute a placeholder value here)."""
    out = bytearray(length)
    for i in range(length):
        b = mem.get(addr + i)
        if b is None:
            return None
        out[i] = b
    return bytes(out)

"""blheli32proxy command-line entry point.

See docs/USAGE.md for full usage and OS-level IP/domain redirection instructions.
Subcommands:
  serve               - run the approval/activation server (the actual project deliverable)
  gen-cert            - generate a self-signed TLS cert/key pair for `serve --tls`
  list-test-firmware  - list the user's archived test-firmware .Hex files (read-only)
  dump-config         - read+best-effort-decrypt an ESC's Setup block (needs real hardware)
  probe-flash         - read-only sanity check of one flash address (needs real hardware)
  dump-info-page      - read-only dump of the info page (0x7c00+: Setup block, activation
                        status, device info) to a NEW file (needs real hardware) — RDP blocks
                        reading anything below 0x7c00, use dump-firmware for that instead
  dump-firmware       - read-only extraction of app-code flash (0x2000-0x7bff) via the Verify
                        oracle against candidate .Hex file(s), never the bootloader or the info
                        page above (needs real hardware)

dump-config/probe-flash/dump-info-page/dump-firmware all take --motor-index when --port is a flight
controller's USB port rather than a dedicated ESC adapter — see
docs/knowledge/protocol-reference.md for the confirmed 4-way-if protocol this drives.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

ARCHIVE_DIR_ENV_VAR = "BLHELI32PROXY_ARCHIVE_DIR"
APP_DIR_ENV_VAR = "BLHELI32PROXY_APP_DIR"


def _archive_dir() -> Path | None:
    """User's broader personal firmware archive, from $BLHELI32PROXY_ARCHIVE_DIR
    — optional, for users who keep more versions than the vendor app itself
    bundles. No hardcoded default — machine-specific, lives outside this repo."""
    value = os.environ.get(ARCHIVE_DIR_ENV_VAR)
    return Path(value).expanduser().resolve() if value else None


def _app_dir() -> Path | None:
    """The vendor app's (BLHeliSuite32xl/.exe/.app) install folder, from
    $BLHELI32PROXY_APP_DIR — what most end users actually have (they need the
    app anyway to flash). Its BLHeli32_HexFiles/ subfolder is the fallback
    test-firmware catalog when $BLHELI32PROXY_ARCHIVE_DIR isn't set."""
    value = os.environ.get(APP_DIR_ENV_VAR)
    return Path(value).expanduser().resolve() if value else None


def _test_firmware_dir() -> Path | None:
    """The effective test-firmware catalog directory: $BLHELI32PROXY_ARCHIVE_DIR
    if set (a power-user's broader collection), else $BLHELI32PROXY_APP_DIR's
    own BLHeli32_HexFiles/ subfolder, else None (caller must ask for --dir)."""
    archive = _archive_dir()
    if archive is not None:
        return archive
    app = _app_dir()
    return (app / "BLHeli32_HexFiles") if app is not None else None

MOTOR_INDEX_HELP = (
    "0-based ESC channel index. Pass this when --port is a flight controller's "
    "USB port, not a dedicated ESC adapter — enters the real 4-way-if bootloader "
    "protocol (see docs/knowledge/protocol-reference.md) instead of talking to the ESC directly."
)


def _cmd_serve(args: argparse.Namespace) -> int:
    from .approval.policy import AllowAllPolicy, CountedLicensePolicy
    from .approval.server import create_server

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if args.policy == "allow-all":
        policy = AllowAllPolicy()
    else:
        policy = CountedLicensePolicy(Path(args.state_file), initial_count=args.initial_count)

    httpd = create_server(
        policy,
        host=args.host,
        port=args.port,
        certfile=args.cert,
        keyfile=args.key,
    )
    scheme = "https" if args.cert else "http"
    print(f"Approval server listening on {scheme}://{args.host}:{args.port}")
    print("See docs/USAGE.md to redirect the real activation hostname to this address.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0


def _cmd_gen_cert(args: argparse.Namespace) -> int:
    """Generate a self-signed certificate/key pair using only the stdlib
    (via a subprocess call to the system's `openssl`, which is present on
    essentially every Linux/macOS install and on Windows via Git-for-Windows
    or a manual install — see docs/USAGE.md)."""
    import subprocess

    cert_path = Path(args.out) / "approval.crt"
    key_path = Path(args.out) / "approval.key"
    cert_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "openssl",
        "req",
        "-x509",
        "-newkey",
        "rsa:2048",
        "-keyout",
        str(key_path),
        "-out",
        str(cert_path),
        "-days",
        str(args.days),
        "-nodes",
        "-subj",
        f"/CN={args.common_name}",
    ]
    try:
        subprocess.run(cmd, check=True)
    except FileNotFoundError:
        print(
            "openssl not found on PATH. Install it (see docs/USAGE.md) or generate a "
            "cert/key pair with another tool and pass them to `serve --cert/--key` directly.",
            file=sys.stderr,
        )
        return 1
    print(f"Wrote {cert_path} and {key_path}")
    return 0


def _cmd_list_test_firmware(args: argparse.Namespace) -> int:
    if args.dir is None:
        print(
            f"--dir not given, and neither ${ARCHIVE_DIR_ENV_VAR} nor ${APP_DIR_ENV_VAR} is set. "
            f"Pass --dir explicitly, or set one of those env vars.",
            file=sys.stderr,
        )
        return 1
    directory = Path(args.dir)
    if not directory.is_dir():
        print(f"Not a directory: {directory}", file=sys.stderr)
        return 1
    for path in sorted(directory.glob("*.Hex")):
        print(path.name)
    return 0


def _print_confirmed_fields(plaintext: bytes, esc_index: int, out_path: str | None) -> None:
    from .protocol import setup_fields

    fields = setup_fields.decode_confirmed_fields(plaintext)
    print(
        "\nConfirmed fields only (see protocol/setup_fields.py docstring — "
        "empirically verified against a real BLHeliSuite32xl backup, NOT a "
        "complete decode; many fields remain unknown and are omitted rather "
        "than guessed):"
    )
    for name, value in fields.items():
        print(f"  {name}={value}")
    if out_path is not None:
        _append_ixi_section(out_path, esc_index, fields)


def _append_ixi_section(out_path: str, esc_index: int, fields: dict) -> None:
    """Append one [ESCn] section to a partial-backup .ixi-style file, writing
    the not-a-real-.ixi warning header first if the file doesn't exist yet."""
    from .protocol import setup_fields

    path = Path(out_path)
    is_new = not path.exists()
    with path.open("a") as f:
        if is_new:
            f.write(setup_fields.IXI_PARTIAL_BACKUP_WARNING)
            f.write("\n")
        f.write(setup_fields.format_ixi_section(esc_index, fields))
        f.write("\n")
    print(f"Appended [ESC{esc_index + 1}] section to {path}")


def _print_defaults_comparison(plaintext: bytes, candidate_path: str, key) -> None:
    """Print a side-by-side comparison of this ESC's real confirmed field
    values against the factory-default Setup block baked into a firmware
    candidate .Hex file (0x7C00, 256 bytes, same XTEA key) — no pass/fail
    gate, just a per-field diff report. User-customized fields are expected
    to differ; that's information, not an error."""
    from .cipher import xtea
    from .protocol import hexfile
    from .protocol import setup_fields

    mem = hexfile.parse_intel_hex(candidate_path)
    default_ciphertext = hexfile.chunk_at(mem, 0x7C00, 256)
    if default_ciphertext is None:
        print(f"\n--show-defaults: {candidate_path} has no data at 0x7C00 — can't extract defaults.",
              file=sys.stderr)
        return
    default_plaintext = xtea.decrypt_setup_block(default_ciphertext, key=key)
    real_fields = setup_fields.decode_confirmed_fields(plaintext)
    default_fields = setup_fields.decode_confirmed_fields(default_plaintext)
    print(f"\nField comparison against factory defaults ({candidate_path}):")
    for name in real_fields:
        real_value = real_fields[name]
        default_value = default_fields.get(name)
        flag = "same" if real_value == default_value else "CHANGED"
        print(f"  {name}: real={real_value} default={default_value} ({flag})")


def _cmd_dump_config(args: argparse.Namespace) -> int:
    """Read an ESC's Setup block and print a best-effort decrypt. Not part of
    the normal flashing workflow (the real BLHeliSuite32xl app handles that)
    — see PLAN.md §4 and docs/knowledge/protocol-reference.md."""
    from .cipher import xtea
    from .protocol.transport import SerialTransport

    key = xtea.TEST_FIRMWARE_KEY if args.test_firmware else xtea.PRODUCTION_KEY
    transport = SerialTransport(args.port)

    if args.motor_index is not None:
        return _dump_config_via_fourwayif(transport, args.motor_index, key, args.out, args.show_defaults)

    from .protocol.client import BLHeliClient

    client = BLHeliClient(transport)
    try:
        client.prime_connection()
        reply = client.connect()
        print(f"Connected: prefix={reply.prefix!r} device_type={reply.device_type!r}")
        block = client.read_setup_block()
        plaintext = xtea.decrypt_setup_block(block.ciphertext, key=key)
        print(f"Decrypted {len(plaintext)} bytes:")
        print(plaintext.hex())
        _print_confirmed_fields(plaintext, esc_index=0, out_path=args.out)
        if args.show_defaults:
            _print_defaults_comparison(plaintext, args.show_defaults, key)
    finally:
        client.disconnect()
        transport.close()
    return 0


def _dump_config_via_fourwayif(
    transport, motor_index: int, key, out_path: str | None, show_defaults: str | None = None
) -> int:
    """FC-passthrough path (--motor-index): enter the real 4-way-if protocol
    BLHeliSuite32xl/AM32-Configurator actually use, live-verified end-to-end
    on real hardware 2026-09-04 (see docs/knowledge/protocol-reference.md) —
    connect(): reset+init-flash the selected ESC channel, read the 256-byte
    Setup block, decrypt, then always release the FC back to normal MSP."""
    from .cipher import xtea
    from .protocol import fourwayif as fw

    try:
        esc_count = fw.enter_4way_if(transport)
        print(f"Entered 4-way-if, FC reports {esc_count} ESC(s)")
        signature = fw.connect_esc(transport, motor_index)
        print(f"ESC {motor_index}: device signature {signature.hex()}")
        ciphertext = fw.read_flash(transport, addr=0x7C00, length=256)
        plaintext = xtea.decrypt_setup_block(ciphertext, key=key)
        print(f"Decrypted {len(plaintext)} bytes:")
        print(plaintext.hex())
        _print_confirmed_fields(plaintext, esc_index=motor_index, out_path=out_path)
        if show_defaults:
            _print_defaults_comparison(plaintext, show_defaults, key)
    finally:
        try:
            fw.exit_interface(transport)
        except fw.FourWayError as exc:
            print(f"Warning: could not cleanly exit 4-way-if: {exc}", file=sys.stderr)
        transport.close()
    return 0


def _print_vector_table_hint(address: int, data: bytes) -> None:
    if address == 0 and len(data) >= 8:
        sp = int.from_bytes(data[0:4], "little")
        reset_vec = int.from_bytes(data[4:8], "little")
        print(f"If this is a real Cortex-M vector table: initial SP={sp:#010x} "
              f"(expect ~0x2000xxxx for STM32F0 SRAM), reset vector={reset_vec:#010x} "
              f"(expect an odd address in flash, Thumb bit set). If these don't look "
              f"plausible, this ESC likely blocks flash readback at this address.")


def _cmd_probe_flash(args: argparse.Namespace) -> int:
    """Read a small chunk at an arbitrary flash address — a quick sanity
    check before attempting a full dump."""
    from .protocol.transport import SerialTransport

    address = int(args.address, 0)
    transport = SerialTransport(args.port)

    if args.motor_index is not None:
        return _probe_flash_via_fourwayif(transport, args.motor_index, address, args.length)

    from .protocol.client import BLHeliClient

    client = BLHeliClient(transport)
    try:
        client.prime_connection()
        reply = client.connect()
        print(f"Connected: prefix={reply.prefix!r} device_type={reply.device_type!r}")
        data = client.read_flash_region_experimental(address, args.length)
        print(f"Read {len(data)} bytes at {address:#06x}:")
        print(data.hex())
        _print_vector_table_hint(address, data)
    finally:
        client.disconnect()
        transport.close()
    return 0


def _probe_flash_via_fourwayif(transport, motor_index: int, address: int, length: int) -> int:
    """FC-passthrough path (--motor-index) — see _dump_config_via_fourwayif's
    docstring for the protocol this uses. A single 4-way-if frame can only
    carry up to 256 bytes; use dump-info-page for larger ranges."""
    from .protocol import fourwayif as fw

    if length > 256:
        print("--length must be <= 256 for a single 4-way-if read; use dump-info-page instead.", file=sys.stderr)
        return 1
    try:
        esc_count = fw.enter_4way_if(transport)
        print(f"Entered 4-way-if, FC reports {esc_count} ESC(s)")
        signature = fw.connect_esc(transport, motor_index)
        print(f"ESC {motor_index}: device signature {signature.hex()}")
        data = fw.read_flash(transport, address, length)
        print(f"Read {len(data)} bytes at {address:#06x}:")
        print(data.hex())
        _print_vector_table_hint(address, data)
    finally:
        try:
            fw.exit_interface(transport)
        except fw.FourWayError as exc:
            print(f"Warning: could not cleanly exit 4-way-if: {exc}", file=sys.stderr)
        transport.close()
    return 0


def _dump_output_archive_guard(out_path: Path) -> int | None:
    """Returns an exit code if the write should be refused, else None. Checks
    both $BLHELI32PROXY_ARCHIVE_DIR (power users) and $BLHELI32PROXY_APP_DIR
    (most users — the vendor app's own folder is just as wrong a place to
    dump into) — a typical user with only APP_DIR set still gets real
    protection, not just a warning."""
    roots = [(ARCHIVE_DIR_ENV_VAR, _archive_dir()), (APP_DIR_ENV_VAR, _app_dir())]
    roots = [(name, root) for name, root in roots if root is not None]
    if not roots:
        print(
            f"Warning: neither ${ARCHIVE_DIR_ENV_VAR} nor ${APP_DIR_ENV_VAR} is set — cannot check "
            f"whether --out lands inside your archived BLHeli material. Verify --out yourself.",
            file=sys.stderr,
        )
        return None
    for name, root in roots:
        try:
            out_path.relative_to(root)
        except ValueError:
            continue
        print(
            f"Refusing to write into the ${name} directory ({root}). "
            f"Choose a different --out path.",
            file=sys.stderr,
        )
        return 1
    return None


def _cmd_dump_info_page(args: argparse.Namespace) -> int:
    """Dump a flash address range to a NEW file via direct cmd_DeviceRead —
    only ever works at 0x7c00+ (RDP blocks everything below that). For
    application code below 0x7c00, use dump-firmware instead (a completely
    different mechanism, the Verify oracle, not a raw read). Refuses to
    write anywhere under the user's archived BLHeli material, as a safety
    backstop on top of just defaulting elsewhere. Read-only against the ESC."""
    from .protocol.transport import SerialTransport

    out_path = Path(args.out).expanduser().resolve()
    guard_result = _dump_output_archive_guard(out_path)
    if guard_result is not None:
        return guard_result
    if out_path.exists() and not args.overwrite:
        print(f"{out_path} already exists — pass --overwrite to replace it.", file=sys.stderr)
        return 1

    start = int(args.start, 0)
    end = int(args.end, 0)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    transport = SerialTransport(args.port)

    if args.motor_index is not None:
        return _dump_info_page_via_fourwayif(transport, args.motor_index, start, end, args.chunk_size, out_path)

    from .protocol.client import BLHeliClient

    client = BLHeliClient(transport)
    try:
        client.prime_connection()
        reply = client.connect()
        print(f"Connected: prefix={reply.prefix!r} device_type={reply.device_type!r}")
        print(f"Dumping {end - start} bytes [{start:#06x}, {end:#06x}) to {out_path} ...")
        with out_path.open("wb") as f:
            for address, chunk in client.dump_flash_experimental(start, end, args.chunk_size):
                f.write(chunk)
                print(f"  {address:#06x}: {len(chunk)} bytes", end="\r")
        print(f"\nWrote {out_path} ({end - start} bytes).")
    finally:
        client.disconnect()
        transport.close()
    return 0


def _dump_info_page_via_fourwayif(transport, motor_index, start, end, chunk_size, out_path) -> int:
    """FC-passthrough path (--motor-index) — see _dump_config_via_fourwayif's
    docstring for the protocol this uses. Each 4-way-if frame caps at 256
    bytes, so --chunk-size must not exceed that."""
    from .protocol import fourwayif as fw

    if chunk_size > 256:
        print("--chunk-size must be <= 256 for the 4-way-if path.", file=sys.stderr)
        return 1
    try:
        esc_count = fw.enter_4way_if(transport)
        print(f"Entered 4-way-if, FC reports {esc_count} ESC(s)")
        signature = fw.connect_esc(transport, motor_index)
        print(f"ESC {motor_index}: device signature {signature.hex()}")
        print(f"Dumping {end - start} bytes [{start:#06x}, {end:#06x}) to {out_path} ...")
        with out_path.open("wb") as f:
            address = start
            while address < end:
                length = min(chunk_size, end - address)
                chunk = fw.read_flash(transport, address, length)
                f.write(chunk)
                print(f"  {address:#06x}: {len(chunk)} bytes", end="\r")
                address += length
        print(f"\nWrote {out_path} ({end - start} bytes).")
    finally:
        try:
            fw.exit_interface(transport)
        except fw.FourWayError as exc:
            print(f"Warning: could not cleanly exit 4-way-if: {exc}", file=sys.stderr)
        transport.close()
    return 0


def _default_firmware_dump_name(candidate_path: str) -> str:
    """Derive a default --out filename from a candidate .Hex file's own name,
    matching this project's existing .ixi naming convention
    (`BLHeli32_<model> - Rev. <version> - <tag>_<date>.<ext>`, e.g.
    `BLHeli32_Furling32 - Rev. 32.9.5 - Multi_260905.ixi`) — never leave the
    caller to invent a name like "furling32-app-code.bin" by hand."""
    import re
    from datetime import date

    stem = Path(candidate_path).stem  # e.g. "Furling32_Multi_32_95"
    m = re.match(r"^(?P<model>.+)_Multi_32_(?P<version>\d+)$", stem)
    if not m:
        return f"dumps/{stem}-AppCode_{date.today():%y%m%d}.bin"
    model = m.group("model")
    digits = m.group("version")
    if len(digits) == 1:
        version = f"32.{digits}"
    elif len(digits) == 2:
        version = f"32.{digits[0]}.{digits[1]}"
    elif len(digits) == 3 and digits.startswith("10"):
        version = f"32.10.{digits[2]}"
    else:
        version = f"32.{digits}"
    return f"dumps/BLHeli32_{model} - Rev. {version} - AppCode_{date.today():%y%m%d}.bin"


def _cmd_dump_firmware(args: argparse.Namespace) -> int:
    """Extract application-code flash content via the cmd_DeviceVerify oracle
    (RDP blocks raw cmd_DeviceRead there, but Verify still discriminates
    match/mismatch — see docs/knowledge/hardware-findings.md's verify-oracle
    exploration). Compares real flash, chunk by chunk, against one or more candidate .Hex
    files; only records a byte as confirmed when some candidate's data for
    that exact chunk verifies as a real match. Never fabricates a value for
    an unconfirmed chunk (written as 0xFF in --out, and listed in the gap
    report) — same "leave undecoded rather than guess" rule as
    protocol/setup_fields.py. Read-only against the ESC; requires --motor-index
    (FC-passthrough only — no client.py path exists for this).

    Hard-refuses to start below the earliest address any given --candidate
    actually covers — a firmware-update file never includes the bootloader
    for any chip/model, so this derives the safe boundary from the
    candidate(s) themselves rather than a fixed MCU-specific constant,
    making this command correct for any BLHeli32 model without per-model
    configuration."""
    from .protocol import hexfile
    from .protocol.transport import SerialTransport

    if args.motor_index is None:
        print("dump-firmware requires --motor-index (FC-passthrough only).", file=sys.stderr)
        return 1

    candidates = [hexfile.parse_intel_hex(p) for p in args.candidate]
    # A firmware-UPDATE file never includes the bootloader, for any chip on any model — that's
    # what receives the update in the first place. So the candidates' own address range IS the
    # correct app-code boundary for whatever specific model these came from, no MCU-family lookup
    # table needed. This makes the tool correct across every model without per-model configuration.
    candidates_min = min(min(mem) for mem in candidates)
    candidates_max = max(max(mem) for mem in candidates)

    start = int(args.start, 0) if args.start is not None else candidates_min
    end = int(args.end, 0) if args.end is not None else candidates_max + 1
    if start < candidates_min:
        print(
            f"--start {start:#06x} is below every given --candidate's own data (earliest: "
            f"{candidates_min:#06x}) — nothing there could ever be confirmed, since a firmware "
            f"update file never covers its own bootloader. Use --start {candidates_min:#06x} or higher, "
            f"or pass a --candidate that actually covers the range you want.",
            file=sys.stderr,
        )
        return 1

    print(f"Loaded {len(candidates)} candidate file(s): {', '.join(args.candidate)}")

    from .protocol import fourwayif as fw

    transport = SerialTransport(args.port)
    confirmed: dict[int, int] = {}
    unresolved_ranges: list[tuple[int, int]] = []
    try:
        esc_count = fw.enter_4way_if(transport)
        print(f"Entered 4-way-if, FC reports {esc_count} ESC(s)")
        signature = fw.connect_esc(transport, args.motor_index)
        print(f"ESC {args.motor_index}: device signature {signature.hex()}")

        from .protocol.frames import ADDR_SETUP_BLOCK  # 0x7C00: RDP allows a direct read here on

        # Derive the output filename from the REAL connected hardware's own onboard identity
        # string (read directly from the Setup block), not from whichever --candidate file was
        # guessed as a comparison reference — the candidate might not even be the right model.
        out_arg = args.out
        if out_arg is None:
            from .cipher import xtea
            from .protocol import setup_fields

            try:
                identity_ciphertext = fw.read_flash(transport, ADDR_SETUP_BLOCK, 256)
                identity_plaintext = xtea.decrypt_setup_block(identity_ciphertext, key=xtea.PRODUCTION_KEY)
                layout, cpu = setup_fields.extract_identity_strings(identity_plaintext)
            except fw.FourWayError:
                layout, cpu = None, None
            if layout:
                from datetime import date

                out_arg = f"dumps/{layout}-AppCode_{date.today():%y%m%d}.bin"
                print(f"Hardware identity confirmed: {layout} ({cpu or 'unknown MCU'})")
            else:
                print("Could not read hardware identity — falling back to candidate-derived name.",
                      file=sys.stderr)
                out_arg = _default_firmware_dump_name(args.candidate[0])
        out_path = Path(out_arg).expanduser().resolve()
        guard_result = _dump_output_archive_guard(out_path)
        if guard_result is not None:
            return guard_result
        if out_path.exists() and not args.overwrite:
            print(f"{out_path} already exists — pass --overwrite to replace it.", file=sys.stderr)
            return 1
        out_path.parent.mkdir(parents=True, exist_ok=True)

        # Step through 256-byte pages aligned to `start` (matches the real app's own confirmed
        # usage pattern — sequential, round-address Verify calls, e.g. 0x2000, 0x2100, 0x2200...)
        # rather than naively bisecting the whole range, which produces chunks at arbitrary
        # non-aligned addresses. Only bisect *within* one 256-byte page when it fails whole —
        # that keeps every sub-split power-of-2 aligned too, never an arbitrary address.
        #
        # At/past ADDR_SETUP_BLOCK, skip the Verify-oracle guessing game entirely: cmd_DeviceRead
        # works there directly (RDP only blocks it below that address), so just read the real
        # bytes — no candidate needed, no ambiguity, and the Setup block itself is XTEA
        # ciphertext that would never match a plaintext firmware candidate anyway.
        page_addr = start
        while page_addr < min(end, ADDR_SETUP_BLOCK):
            page_len = min(256, min(end, ADDR_SETUP_BLOCK) - page_addr)
            _verify_region(transport, candidates, page_addr, page_len, confirmed, unresolved_ranges)
            page_addr += page_len

        read_addr = max(start, ADDR_SETUP_BLOCK)
        while read_addr < end:
            read_len = min(256, end - read_addr)
            chunk = fw.read_flash(transport, read_addr, read_len)
            for i, b in enumerate(chunk):
                confirmed[read_addr + i] = b
            print(f"  {read_addr:#06x}+{read_len}: read directly (info page, no candidate needed)", end="\r")
            read_addr += read_len

        total = end - start
        print(f"\nConfirmed {len(confirmed)}/{total} bytes ({100 * len(confirmed) / total:.1f}%).")
        if unresolved_ranges:
            print(f"{len(unresolved_ranges)} unresolved range(s): " + ", ".join(f"{a:#06x}+{n}" for a, n in unresolved_ranges))

        if args.discover_unresolved and unresolved_ranges:
            total_unresolved = sum(n for _, n in unresolved_ranges)
            print(f"\nBrute-force discovering {total_unresolved} unresolved byte(s) "
                  f"(up to 256 tries each — this is slow, real hardware round-trips)...")
            undiscoverable: list[int] = []
            done = 0
            for range_addr, range_len in unresolved_ranges:
                for offset in range(range_len):
                    a = range_addr + offset
                    done += 1
                    value = fw.discover_byte(transport, a)
                    if value is None:
                        undiscoverable.append(a)
                        print(f"  {a:#06x}: UNDISCOVERABLE (no value 0-255 matched — real anomaly) "
                              f"({done}/{total_unresolved})")
                    else:
                        confirmed[a] = value
                        print(f"  {a:#06x}: discovered {value:#04x} ({done}/{total_unresolved})", end="\r")
            print(f"\nDiscovered {total_unresolved - len(undiscoverable)}/{total_unresolved} unresolved byte(s).")
            if undiscoverable:
                print(f"{len(undiscoverable)} byte(s) genuinely undiscoverable: "
                      + ", ".join(f"{a:#06x}" for a in undiscoverable))
            print(f"Now {len(confirmed)}/{total} bytes known ({100 * len(confirmed) / total:.1f}%).")

        with out_path.open("wb") as f:
            for addr in range(start, end):
                f.write(bytes([confirmed.get(addr, 0xFF)]))
        print(f"Wrote {out_path} (padded, {total} bytes).")

        hex_path = out_path.with_suffix(".hex")
        hex_path.write_text(hexfile.encode_intel_hex_sparse(confirmed))
        print(f"Wrote {hex_path} (sparse — gaps skipped entirely, matching real .Hex file convention).")
    finally:
        try:
            fw.exit_interface(transport)
        except fw.FourWayError as exc:
            print(f"Warning: could not cleanly exit 4-way-if: {exc}", file=sys.stderr)
        transport.close()
    return 0


def _verify_region(
    transport,
    candidates: list[dict[int, int]],
    addr: int,
    length: int,
    confirmed: dict[int, int],
    unresolved_ranges: list[tuple[int, int]],
    min_mismatch_length: int = 32,
) -> None:
    """Recursively verify [addr, addr+length) against the candidates, bisecting
    whenever the full range can't be confirmed in one shot — recovers a
    genuinely-confirmed sub-range even when a candidate only partially covers
    a nominal chunk, instead of discarding the whole range as unconfirmed.

    Bisecting through a range no candidate has ANY data for costs zero
    hardware round-trips (chunk_at() is checked locally before ever calling
    verify_flash()). But a genuine content MISMATCH (some candidate has full
    data for the range, verify_flash() just returns False) costs one real
    round-trip per bisection level — for a real official-release ESC
    compared only against test-firmware candidates, large stretches can
    mismatch throughout, and localizing every mismatch down to 1 byte would
    cost a round-trip at every level (up to length/min_mismatch_length * 2
    calls). `min_mismatch_length` stops bisecting a MISMATCH (not a gap)
    below this size — reported as unresolved at that granularity instead of
    pinpointing the exact differing byte(s)."""
    from .protocol import fourwayif as fw
    from .protocol import hexfile

    any_candidate_data = False
    if length <= 256:  # cmd_DeviceVerify carries at most 256 bytes per frame
        for mem in candidates:
            data = hexfile.chunk_at(mem, addr, length)
            if data is None:
                continue
            any_candidate_data = True
            if fw.verify_flash(transport, addr, data):
                for i, b in enumerate(data):
                    confirmed[addr + i] = b
                print(f"  {addr:#06x}+{length}: confirmed", end="\r")
                return
        if length <= 1 or (any_candidate_data and length <= min_mismatch_length):
            unresolved_ranges.append((addr, length))
            return
    half = length // 2
    _verify_region(transport, candidates, addr, half, confirmed, unresolved_ranges, min_mismatch_length)
    _verify_region(transport, candidates, addr + half, length - half, confirmed, unresolved_ranges, min_mismatch_length)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="blheli32proxy")
    sub = parser.add_subparsers(dest="command", required=True)

    p_serve = sub.add_parser("serve", help="run the approval/activation server")
    p_serve.add_argument("--host", default="0.0.0.0", help="bind address (default: 0.0.0.0)")
    p_serve.add_argument("--port", type=int, default=8443, help="bind port (default: 8443)")
    p_serve.add_argument("--cert", help="TLS certificate file (enables HTTPS)")
    p_serve.add_argument("--key", help="TLS private key file (required with --cert)")
    p_serve.add_argument(
        "--policy", choices=["allow-all", "counted"], default="allow-all", help="approval policy"
    )
    p_serve.add_argument(
        "--state-file",
        default=str(Path.home() / ".blheli32proxy" / "license-state.json"),
        help="state file for --policy counted",
    )
    p_serve.add_argument("--initial-count", type=int, default=1000)
    p_serve.add_argument("--verbose", action="store_true")
    p_serve.set_defaults(func=_cmd_serve)

    p_cert = sub.add_parser("gen-cert", help="generate a self-signed TLS cert/key pair")
    p_cert.add_argument("--out", default=str(Path.home() / ".blheli32proxy"), help="output directory")
    p_cert.add_argument("--common-name", default="localhost")
    p_cert.add_argument("--days", type=int, default=825)
    p_cert.set_defaults(func=_cmd_gen_cert)

    p_list = sub.add_parser("list-test-firmware", help="list archived test-firmware .Hex files")
    _default_test_firmware_dir = _test_firmware_dir()
    p_list.add_argument(
        "--dir",
        default=str(_default_test_firmware_dir) if _default_test_firmware_dir else None,
        help=f"directory of test-firmware .Hex files (default: ${ARCHIVE_DIR_ENV_VAR} if set, else "
        f"${APP_DIR_ENV_VAR}'s own BLHeli32_HexFiles/ subfolder if that's set instead)",
    )
    p_list.set_defaults(func=_cmd_list_test_firmware)

    p_dumpcfg = sub.add_parser("dump-config", help="(experimental, needs hardware) read+decrypt a Setup block")
    p_dumpcfg.add_argument("--port", required=True, help="serial port, e.g. /dev/ttyACM0 or COM3")
    p_dumpcfg.add_argument("--test-firmware", action="store_true", help="use the test-firmware XTEA key")
    p_dumpcfg.add_argument(
        "--motor-index",
        type=int,
        default=None,
        help=MOTOR_INDEX_HELP,
    )
    p_dumpcfg.add_argument(
        "--show-defaults",
        default=None,
        metavar="CANDIDATE_HEX",
        help="also decrypt the factory-default Setup block baked into this firmware candidate "
        "(same 0x7C00 address, same XTEA key) and print a per-field real-vs-default comparison "
        "— a customized field showing CHANGED is expected, not an error",
    )
    p_dumpcfg.add_argument(
        "--out",
        default=None,
        help="append this ESC's confirmed fields as an [ESCn] section to a partial-backup "
        "file (creates it with a not-a-real-.ixi warning header if new) — confirmed fields "
        "only, never a complete or loadable .ixi",
    )
    p_dumpcfg.set_defaults(func=_cmd_dump_config)

    p_probe = sub.add_parser(
        "probe-flash", help="(experimental, needs hardware) read-only sanity check of a flash address"
    )
    p_probe.add_argument("--port", required=True, help="serial port, e.g. /dev/ttyACM0 or COM3")
    p_probe.add_argument("--address", default="0x0000", help="flash address to read (e.g. 0x0000)")
    p_probe.add_argument("--length", type=int, default=16, help="bytes to read (1-256, default 16)")
    p_probe.add_argument(
        "--motor-index",
        type=int,
        default=None,
        help=MOTOR_INDEX_HELP,
    )
    p_probe.set_defaults(func=_cmd_probe_flash)

    p_dumpinfo = sub.add_parser(
        "dump-info-page",
        help="(experimental, needs hardware) read-only dump of the 0x7c00+ info page to a NEW "
        "file via direct read (for app code below 0x7c00, use dump-firmware instead)",
    )
    p_dumpinfo.add_argument("--port", required=True, help="serial port, e.g. /dev/ttyACM0 or COM3")
    p_dumpinfo.add_argument("--start", default="0x0000", help="start address, inclusive")
    p_dumpinfo.add_argument("--end", required=True, help="end address, exclusive")
    p_dumpinfo.add_argument(
        "--out",
        required=True,
        help=f"output file path (refused if it falls under ${ARCHIVE_DIR_ENV_VAR}, when that env var is set)",
    )
    p_dumpinfo.add_argument("--chunk-size", type=int, default=256)
    p_dumpinfo.add_argument("--overwrite", action="store_true", help="allow overwriting an existing --out file")
    p_dumpinfo.add_argument(
        "--motor-index",
        type=int,
        default=None,
        help=MOTOR_INDEX_HELP,
    )
    p_dumpinfo.set_defaults(func=_cmd_dump_info_page)

    p_dumpfw = sub.add_parser(
        "dump-firmware",
        help="(experimental, needs hardware) extract application-code flash via the "
        "cmd_DeviceVerify oracle against candidate .Hex file(s) — read-only, works for any "
        "model/MCU since the safe address range is derived from the candidate file(s) "
        "themselves, never touches the bootloader or writes/erases anything",
    )
    p_dumpfw.add_argument("--port", required=True, help="serial port, e.g. /dev/ttyACM0 or COM3")
    p_dumpfw.add_argument(
        "--candidate",
        action="append",
        required=True,
        help="a candidate .Hex file to compare against (repeat for multiple; first match wins "
        "per chunk, in the order given)",
    )
    p_dumpfw.add_argument(
        "--start", default=None, help="start address, inclusive (default: the earliest address "
        "covered by any --candidate — never lower, since a firmware-update file never covers "
        "its own bootloader)"
    )
    p_dumpfw.add_argument(
        "--end", default=None, help="end address, exclusive (default: one past the latest address "
        "covered by any --candidate)"
    )
    p_dumpfw.add_argument(
        "--out",
        default=None,
        help="output file path (default: auto-derived from the first --candidate's own filename, "
        f"matching this project's .ixi naming convention — refused if it falls under "
        f"${ARCHIVE_DIR_ENV_VAR}, when that env var is set)",
    )
    p_dumpfw.add_argument("--overwrite", action="store_true", help="allow overwriting an existing --out file")
    p_dumpfw.add_argument(
        "--discover-unresolved",
        action="store_true",
        help="after comparing against candidates, brute-force discover every remaining unresolved "
        "byte by trying values 0-255 via cmd_DeviceVerify (no candidate needed, but slow — up to "
        "256 real round-trips per byte). Only reasonable when few bytes remain unresolved.",
    )
    p_dumpfw.add_argument(
        "--motor-index",
        type=int,
        default=None,
        help=MOTOR_INDEX_HELP,
    )
    p_dumpfw.set_defaults(func=_cmd_dump_firmware)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

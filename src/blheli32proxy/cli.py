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
dump-config defaults to dumping every ESC the FC reports when --motor-index is omitted (pass
--motor-index N to dump just one, or --direct for a standalone ESC not behind a flight controller).
"""

from __future__ import annotations

import argparse
import logging
import math
import os
import signal
import sys
import time
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
    name = setup_fields.decode_name(plaintext)
    layout = setup_fields.decode_esc_layout(plaintext)
    note_array = setup_fields.decode_note_array(plaintext)
    print(
        "\nConfirmed fields only (see protocol/setup_fields.py docstring — "
        "empirically verified against a real BLHeliSuite32xl backup, NOT a "
        "complete decode; many fields remain unknown and are omitted rather "
        "than guessed):"
    )
    print(f"  Eep_ESC_Layout={layout}")
    print(f"  Eep_Name={name}")
    for field_name, value in fields.items():
        print(f"  {field_name}={value}")
    print(f"  Eep_Note_Array={note_array}")
    if out_path is not None:
        _append_ixi_section(out_path, esc_index, fields, name, layout, note_array)


def _append_ixi_section(
    out_path: str,
    esc_index: int,
    fields: dict,
    name: str | None = None,
    layout: str | None = None,
    note_array: str | None = None,
) -> None:
    """Append one [ESCn] section to a partial-backup .ixi-style file, writing
    the not-a-real-.ixi warning header first if the file doesn't exist yet."""
    from .protocol import setup_fields

    path = Path(out_path)
    is_new = not path.exists()
    with path.open("a") as f:
        if is_new:
            f.write(setup_fields.IXI_PARTIAL_BACKUP_WARNING)
            f.write("\n")
        f.write(setup_fields.format_ixi_section(esc_index, fields, name, layout, note_array))
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


def _save_raw_setup_backup(ciphertext: bytes, raw_dir: str | None, esc_index: int) -> None:
    """Save one ESC's exact 256-byte Setup-block ciphertext to <raw_dir>/esc<N>-setup-<timestamp>.bin
    — a byte-exact backup usable for a full restore (unlike --out's decoded-fields-only file, which
    only covers the 45 confirmed fields). No-op if raw_dir is None. Refuses to write into
    $BLHELI32PROXY_ARCHIVE_DIR/$BLHELI32PROXY_APP_DIR, same guard as dump-info-page/dump-firmware."""
    if raw_dir is None:
        return
    from datetime import datetime

    path = Path(raw_dir).expanduser().resolve()
    guard_result = _dump_output_archive_guard(path / "placeholder.bin")
    if guard_result is not None:
        raise SystemExit(guard_result)
    path.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_file = path / f"esc{esc_index}-setup-{timestamp}.bin"
    out_file.write_bytes(ciphertext)
    print(f"Saved raw Setup-block backup: {out_file}")


def _cmd_dump_config(args: argparse.Namespace) -> int:
    """Read an ESC's Setup block and print a best-effort decrypt. Not part of
    the normal flashing workflow (the real BLHeliSuite32xl app handles that)
    — see PLAN.md §4 and docs/knowledge/protocol-reference.md."""
    from .cipher import xtea
    from .protocol.transport import SerialTransport

    key = xtea.TEST_FIRMWARE_KEY if args.test_firmware else xtea.PRODUCTION_KEY

    if args.direct and args.motor_index is not None:
        print("--direct and --motor-index are mutually exclusive.", file=sys.stderr)
        return 1

    transport = SerialTransport(args.port)

    if args.direct:
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
            _save_raw_setup_backup(block.ciphertext, args.raw_dir, esc_index=0)
            if args.show_defaults:
                _print_defaults_comparison(plaintext, args.show_defaults, key)
        finally:
            client.disconnect()
            transport.close()
        return 0

    if args.motor_index is not None:
        return _dump_config_via_fourwayif(
            transport, args.motor_index, key, args.out, args.show_defaults, args.raw_dir
        )

    return _dump_config_all_via_fourwayif(transport, key, args.out, args.show_defaults, args.raw_dir)


def _dump_config_via_fourwayif(
    transport, motor_index: int, key, out_path: str | None, show_defaults: str | None = None,
    raw_dir: str | None = None,
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
        _save_raw_setup_backup(ciphertext, raw_dir, esc_index=motor_index)
        if show_defaults:
            _print_defaults_comparison(plaintext, show_defaults, key)
    finally:
        try:
            fw.exit_interface(transport)
        except fw.FourWayError as exc:
            print(f"Warning: could not cleanly exit 4-way-if: {exc}", file=sys.stderr)
        transport.close()
    return 0


def _dump_config_all_via_fourwayif(
    transport, key, out_path: str | None, show_defaults: str | None = None, raw_dir: str | None = None
) -> int:
    """FC-passthrough path, default when --motor-index is omitted (and --direct
    isn't given): enters 4-way-if once, then dumps every ESC the FC reports —
    matches how the real BLHeliSuite32xl app's own "Checking Multiple ESC" scan
    works (one passthrough entry, one connect_esc() per channel in sequence),
    not a separate passthrough session per ESC."""
    from .cipher import xtea
    from .protocol import fourwayif as fw

    try:
        esc_count = fw.enter_4way_if(transport)
        print(f"Entered 4-way-if, FC reports {esc_count} ESC(s)")
        for motor_index in range(esc_count):
            signature = fw.connect_esc(transport, motor_index)
            print(f"\nESC {motor_index}: device signature {signature.hex()}")
            ciphertext = fw.read_flash(transport, addr=0x7C00, length=256)
            plaintext = xtea.decrypt_setup_block(ciphertext, key=key)
            print(f"Decrypted {len(plaintext)} bytes:")
            print(plaintext.hex())
            _print_confirmed_fields(plaintext, esc_index=motor_index, out_path=out_path)
            _save_raw_setup_backup(ciphertext, raw_dir, esc_index=motor_index)
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


def _load_checkpoint(path: Path) -> tuple[dict[int, int], set[int], dict[int, int]]:
    """Load a --discover-unresolved checkpoint file: one `<addr> <value>` or
    `<addr> UNDISCOVERABLE` line per byte a prior (possibly interrupted) run already resolved, or
    one `<window_addr> HYPOTHESIS_EXHAUSTED <max_combo>` line per window whose hypothesis search
    (see fw.discover_window()'s docstring) was fully exhausted up to that --max-combo with no
    match — resumed at a higher --max-combo, that window is retried from k=max_combo+1, not from
    scratch. Missing file is not an error (first run). A malformed line is skipped with a warning,
    never fatal — a checkpoint is a resume aid, not a source of truth that must be perfect."""
    discovered: dict[int, int] = {}
    undiscoverable: set[int] = set()
    hypothesis_exhausted: dict[int, int] = {}
    if not path.exists():
        return discovered, undiscoverable, hypothesis_exhausted
    for lineno, raw_line in enumerate(path.read_text().splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) == 3 and parts[1] == "HYPOTHESIS_EXHAUSTED":
            try:
                window_addr = int(parts[0], 0)
                max_combo_tried = int(parts[2], 0)
            except ValueError:
                print(f"Warning: checkpoint {path} line {lineno}: malformed, skipping: {line!r}", file=sys.stderr)
                continue
            hypothesis_exhausted[window_addr] = max(hypothesis_exhausted.get(window_addr, 0), max_combo_tried)
            continue
        if len(parts) != 2:
            print(f"Warning: checkpoint {path} line {lineno}: malformed, skipping: {line!r}", file=sys.stderr)
            continue
        try:
            addr = int(parts[0], 0)
        except ValueError:
            print(f"Warning: checkpoint {path} line {lineno}: bad address, skipping: {line!r}", file=sys.stderr)
            continue
        if parts[1] == "UNDISCOVERABLE":
            undiscoverable.add(addr)
            continue
        try:
            discovered[addr] = int(parts[1], 0)
        except ValueError:
            print(f"Warning: checkpoint {path} line {lineno}: bad value, skipping: {line!r}", file=sys.stderr)
    return discovered, undiscoverable, hypothesis_exhausted


def _append_checkpoint_window(path: Path, window_addr: int, max_combo: int) -> None:
    """Append one 'this window's hypothesis search is exhausted up to k=max_combo' line —
    see _load_checkpoint()'s docstring for the format and resume semantics."""
    with path.open("a") as f:
        f.write(f"{window_addr:#06x} HYPOTHESIS_EXHAUSTED {max_combo:#04x}\n")
        f.flush()
        os.fsync(f.fileno())


def _candidate_window_bytes(candidates: list[dict[int, int]], window_addr: int) -> bytes | None:
    """The first candidate (in order given) with full 8-byte data at this aligned window, or None
    if no candidate covers all 8 bytes — mirrors _verify_region's own "first candidate with data
    wins" convention."""
    from .protocol import hexfile

    for mem in candidates:
        data = hexfile.chunk_at(mem, window_addr, 8)
        if data is not None:
            return data
    return None


def _append_checkpoint(path: Path, addr: int, value: int | None) -> None:
    """Append one resolved byte to the checkpoint file, fsync'd immediately — a kill (SIGKILL, a
    power loss) right after this call still only re-does the one in-flight byte on resume, never
    more, since every prior line is already durable on disk."""
    with path.open("a") as f:
        f.write(f"{addr:#06x} UNDISCOVERABLE\n" if value is None else f"{addr:#06x} {value:#04x}\n")
        f.flush()
        os.fsync(f.fileno())


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

    checkpoint_path = Path(args.checkpoint).expanduser().resolve() if args.checkpoint else None
    checkpoint_discovered: dict[int, int] = {}
    checkpoint_undiscoverable: set[int] = set()
    hypothesis_exhausted: dict[int, int] = {}
    if checkpoint_path is not None:
        checkpoint_discovered, checkpoint_undiscoverable, hypothesis_exhausted = _load_checkpoint(checkpoint_path)
        if checkpoint_discovered or checkpoint_undiscoverable or hypothesis_exhausted:
            print(f"Resuming from checkpoint {checkpoint_path}: "
                  f"{len(checkpoint_discovered)} byte(s) already discovered, "
                  f"{len(checkpoint_undiscoverable)} already known undiscoverable, "
                  f"{len(hypothesis_exhausted)} window(s) with a prior hypothesis search recorded.")

    # Convert SIGTERM into the same KeyboardInterrupt Ctrl-C already raises, so a `timeout`
    # wrapper or `kill` (not -9) still unwinds through the finally block below and calls
    # exit_interface() -- confirmed missing this (2026-09-08) leaves the FC's own MSP passthrough
    # state stuck, recoverable only by a physical USB replug. See docs/knowledge/hardware-findings.md.
    def _raise_keyboard_interrupt(signum, frame):
        raise KeyboardInterrupt()

    previous_sigterm_handler = signal.signal(signal.SIGTERM, _raise_keyboard_interrupt)

    try:
        return _dump_firmware_body(
            args, candidates, start, end, checkpoint_path, checkpoint_discovered, checkpoint_undiscoverable,
            hypothesis_exhausted,
        )
    except KeyboardInterrupt:
        print("\nInterrupted — cleanly exited the 4-way-if session.", file=sys.stderr)
        if checkpoint_path is not None:
            print(f"Progress saved to checkpoint {checkpoint_path} — resume with the same "
                  f"--checkpoint {checkpoint_path} (and the same --candidate/--start/--end) to "
                  f"continue.", file=sys.stderr)
        return 130
    finally:
        signal.signal(signal.SIGTERM, previous_sigterm_handler)


def _dump_firmware_body(
    args: argparse.Namespace,
    candidates: list[dict[int, int]],
    start: int,
    end: int,
    checkpoint_path: Path | None,
    checkpoint_discovered: dict[int, int],
    checkpoint_undiscoverable: set[int],
    hypothesis_exhausted: dict[int, int],
) -> int:
    """The actual dump-firmware work, split out of _cmd_dump_firmware so the outer function can
    wrap it in one try/except KeyboardInterrupt (see _cmd_dump_firmware's SIGTERM handling)."""
    from .protocol import hexfile
    from .protocol.transport import SerialTransport
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
            _verify_region(
                transport, candidates, page_addr, page_len, confirmed, unresolved_ranges,
                args.min_mismatch_length,
            )
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
            import itertools

            unresolved_addrs = {
                range_addr + offset for range_addr, range_len in unresolved_ranges for offset in range(range_len)
            }
            total_unresolved = len(unresolved_addrs)
            print(f"\nBrute-force discovering {total_unresolved} unresolved byte(s) via real, "
                  f"8-byte-aligned cmd_DeviceVerify windows (fixed 2026-09-08 — see "
                  f"docs/knowledge/hardware-findings.md; bare 1-byte guessing is unsound). A window "
                  f"with k simultaneously-unknown bytes costs 256^k guesses. Windows with no partial "
                  f"knowledge but full candidate data use hypothesis mode instead: try every way "
                  f"exactly k of the 8 bytes could differ from the candidate (k=1 first, then 2, up "
                  f"to --max-combo={args.max_combo}), holding the rest at the candidate's own value.")
            undiscoverable: list[int] = []
            insufficient_data: list[int] = []
            too_many_unknowns: list[int] = []
            hypothesis_exhausted_bytes: list[int] = []
            from_checkpoint = 0
            done = 0
            campaign_start = time.time()
            budget_exceeded = False

            for window_addr in sorted({a - (a % 8) for a in unresolved_addrs}):
                if args.time_budget is not None and time.time() - campaign_start > args.time_budget:
                    budget_exceeded = True
                    break

                window_unresolved = [window_addr + i for i in range(8) if (window_addr + i) in unresolved_addrs]
                still_needed = [a for a in window_unresolved if a not in checkpoint_discovered and a not in checkpoint_undiscoverable]
                for a in window_unresolved:
                    if a not in still_needed:
                        done += 1
                        from_checkpoint += 1
                        if a in checkpoint_discovered:
                            confirmed[a] = checkpoint_discovered[a]
                        else:
                            undiscoverable.append(a)
                if not still_needed:
                    continue

                known: dict[int, int] = {}
                unknown_offsets: list[int] = []
                window_complete = True
                for i in range(8):
                    a = window_addr + i
                    if a in confirmed:
                        known[i] = confirmed[a]
                    elif a in checkpoint_discovered:
                        known[i] = checkpoint_discovered[a]
                    elif a in unresolved_addrs:
                        unknown_offsets.append(i)
                    else:
                        window_complete = False
                        break

                if not window_complete:
                    insufficient_data.extend(still_needed)
                    done += len(still_needed)
                    continue

                if len(unknown_offsets) <= args.max_combo:
                    # genuinely few unknowns already (e.g. a partial checkpoint from a prior run)
                    result = fw.discover_window(transport, window_addr, known, unknown_offsets)
                    done += len(still_needed)
                    if result is None:
                        for i in unknown_offsets:
                            a = window_addr + i
                            undiscoverable.append(a)
                            if checkpoint_path is not None:
                                _append_checkpoint(checkpoint_path, a, None)
                        print(f"  window {window_addr:#06x}: UNDISCOVERABLE for offset(s) "
                              + ", ".join(f"+{i}" for i in unknown_offsets) + f" ({done}/{total_unresolved})")
                    else:
                        for i in unknown_offsets:
                            a = window_addr + i
                            confirmed[a] = result[i]
                            if checkpoint_path is not None:
                                _append_checkpoint(checkpoint_path, a, result[i])
                        print(f"  window {window_addr:#06x}: discovered "
                              + ", ".join(f"+{i}={result[i]:#04x}" for i in unknown_offsets)
                              + f" ({done}/{total_unresolved})", end="\r")
                    continue

                # k > max_combo with no partial knowledge -- try hypothesis mode instead of just
                # skipping, if the candidate has full data for this window (2026-09-09, see
                # docs/knowledge/hardware-findings.md's real-hardware validation of this approach)
                window_candidate = _candidate_window_bytes(candidates, window_addr)
                already_tried = hypothesis_exhausted.get(window_addr, 0)
                if window_candidate is None or already_tried >= args.max_combo:
                    too_many_unknowns.extend(window_addr + i for i in unknown_offsets)
                    done += len(still_needed)
                    continue

                found = False
                result = None
                exhausted_fully = True
                for k in range(already_tried + 1, args.max_combo + 1):
                    if args.time_budget is not None and time.time() - campaign_start > args.time_budget:
                        exhausted_fully = False
                        budget_exceeded = True
                        break
                    for combo in itertools.combinations(range(8), k):
                        # check the budget between EVERY combo attempt, not just once per k-level --
                        # k=2 alone is up to C(8,2)=28 combos * 65536 guesses each (~30h worst case
                        # for one window), so a once-per-k check could block the whole session on a
                        # single unlucky window (confirmed live, 2026-09-09 -- see
                        # docs/knowledge/hardware-findings.md)
                        if args.time_budget is not None and time.time() - campaign_start > args.time_budget:
                            exhausted_fully = False
                            budget_exceeded = True
                            break
                        combo_known = {i: window_candidate[i] for i in range(8) if i not in combo}
                        result = fw.discover_window(transport, window_addr, combo_known, list(combo))
                        if result is not None:
                            found = True
                            break
                    if found or budget_exceeded:
                        break
                done += len(still_needed)
                if found:
                    for i in range(8):
                        a = window_addr + i
                        confirmed[a] = result[i]
                        if checkpoint_path is not None and a in unresolved_addrs:
                            _append_checkpoint(checkpoint_path, a, result[i])
                    print(f"  window {window_addr:#06x}: HYPOTHESIS MATCH (k={len(combo)}, offsets "
                          f"{combo} differ from candidate) ({done}/{total_unresolved})")
                elif exhausted_fully:
                    hypothesis_exhausted[window_addr] = args.max_combo
                    if checkpoint_path is not None:
                        _append_checkpoint_window(checkpoint_path, window_addr, args.max_combo)
                    hypothesis_exhausted_bytes.extend(still_needed)
                    print(f"  window {window_addr:#06x}: hypothesis search exhausted up to k="
                          f"{args.max_combo} ({math.comb(8, args.max_combo) if args.max_combo <= 8 else 0}+ "
                          f"combinations tried), no match ({done}/{total_unresolved})")
                # else: time budget ran out mid-window -- nothing recorded for it this round, the
                # current k-level restarts from scratch on resume (bounded re-work, not lost progress)
                if budget_exceeded:
                    break

            if budget_exceeded:
                print(f"\nTime budget ({args.time_budget}s) reached — stopping cleanly.")
                if checkpoint_path is not None:
                    print(f"Resume with the same --checkpoint {checkpoint_path} (and the same "
                          f"--candidate/--start/--end/--max-combo) to continue.")
            if from_checkpoint:
                print(f"\n{from_checkpoint} byte(s) resumed from checkpoint, no round-trip needed.")
            if too_many_unknowns:
                print(f"\n{len(too_many_unknowns)} byte(s) skipped — no candidate data for their window, "
                      f"or already hypothesis-exhausted at this --max-combo={args.max_combo}: "
                      + ", ".join(f"{a:#06x}" for a in too_many_unknowns))
            if insufficient_data:
                print(f"\n{len(insufficient_data)} byte(s) skipped — their 8-byte window extends "
                      f"outside the scanned [--start, --end) range: "
                      + ", ".join(f"{a:#06x}" for a in insufficient_data))
            resolved = (total_unresolved - len(undiscoverable) - len(too_many_unknowns)
                        - len(insufficient_data) - len(hypothesis_exhausted_bytes))
            print(f"\nDiscovered {resolved}/{total_unresolved} unresolved byte(s) via reliable "
                  f"8-byte-aligned windows.")
            if undiscoverable:
                print(f"{len(undiscoverable)} byte(s) genuinely UNDISCOVERABLE — exhaustively tried every "
                      f"combination via a real, aligned verify window (reliable, unlike the old bare "
                      f"1-byte method): " + ", ".join(f"{a:#06x}" for a in undiscoverable))
            if hypothesis_exhausted_bytes:
                print(f"{len(hypothesis_exhausted_bytes)} byte(s) in windows where every hypothesis up to "
                      f"k={args.max_combo} failed — the real divergence needs a higher --max-combo (cost "
                      f"256^k) or remains genuinely unknown: "
                      + ", ".join(f"{a:#06x}" for a in hypothesis_exhausted_bytes))
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

    # cmd_DeviceVerify is confirmed unreliable below 8 bytes (2026-09-08, see
    # docs/knowledge/hardware-findings.md's "CRITICAL: cmd_DeviceVerify is unreliable below 8
    # bytes / when misaligned") -- never issue one, regardless of caller-supplied
    # min_mismatch_length. A pure gap (no candidate has ANY data here) still bisects freely
    # down to 1 byte exactly as before -- that path never calls verify_flash at all, so the
    # unreliable-length risk doesn't apply to it.
    min_mismatch_length = max(min_mismatch_length, 8)

    any_candidate_data = False
    if length <= 256:  # cmd_DeviceVerify carries at most 256 bytes per frame
        for mem in candidates:
            if hexfile.chunk_at(mem, addr, length) is not None:
                any_candidate_data = True
                break

    if any_candidate_data and length < 8:
        # would need an unreliable sub-8-byte verify_flash call -- defer to the reliable
        # floor instead of ever issuing one; report unresolved rather than risk a wrong answer
        unresolved_ranges.append((addr, length))
        return

    if length <= 256:
        for mem in candidates:
            data = hexfile.chunk_at(mem, addr, length)
            if data is None:
                continue
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
        help=MOTOR_INDEX_HELP + " — omit to dump every ESC the FC reports (the default)",
    )
    p_dumpcfg.add_argument(
        "--direct",
        action="store_true",
        help="skip FC-passthrough auto-discovery; connect directly as a single standalone "
        "device (for an ESC wired to a dedicated adapter, not through a flight controller) "
        "— mutually exclusive with --motor-index",
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
    p_dumpcfg.add_argument(
        "--raw-dir",
        default=None,
        help="also save each dumped ESC's exact 256-byte Setup-block ciphertext to "
        "<raw-dir>/esc<N>-setup-<timestamp>.bin — a byte-exact backup usable for a full "
        "restore, unlike --out's decoded-fields-only file (see dumps/README.md)",
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
        "--min-mismatch-length",
        type=int,
        default=32,
        help="stop bisecting a genuine content MISMATCH once a chunk is this small (a pure "
        "gap -- no candidate has any data -- still bisects to 1 byte regardless, that path "
        "never touches hardware). Floored to 8 always — cmd_DeviceVerify is confirmed "
        "unreliable below 8 bytes. Pass 8 for the finest reliable breakdown (more real "
        "round-trips) before --discover-unresolved / --max-combo; the default 32 matches "
        "this project's original scans.",
    )
    p_dumpfw.add_argument(
        "--discover-unresolved",
        action="store_true",
        help="brute-force discover every remaining unresolved byte via real, 8-byte-aligned "
        "cmd_DeviceVerify windows (fw.discover_window()) — the fixed replacement (2026-09-08) for "
        "an earlier bare-1-byte-guess design confirmed unsound (see "
        "docs/knowledge/hardware-findings.md's \"CRITICAL: cmd_DeviceVerify is unreliable below 8 "
        "bytes\" section). A window with k simultaneously-unknown bytes costs 256^k guesses — see "
        "--max-combo. Only reasonable with --checkpoint for anything but a handful of bytes; a "
        "multi-day run needs to survive interruption.",
    )
    p_dumpfw.add_argument(
        "--max-combo",
        type=int,
        default=1,
        help="skip (not attempt) any 8-byte-aligned window with more than this many simultaneously "
        "-unknown bytes, since the cost is 256^k round-trips — 1 (default) costs the same 256 "
        "guesses as a single unknown byte always did; 2 costs up to 65,536 (~1 hour at the "
        "measured 0.06s/guess); 3+ is generally impractical. No effect without "
        "--discover-unresolved.",
    )
    p_dumpfw.add_argument(
        "--checkpoint",
        default=None,
        help="resume-support file for --discover-unresolved: appended to as each byte is "
        "resolved, and read back at startup to skip already-known bytes. Safe to Ctrl-C or kill "
        "and resume later with the same --checkpoint path (SIGTERM/SIGINT during the brute-force "
        "loop are caught to cleanly exit the 4-way-if session first, matching this project's own "
        "confirmed finding that an uncaught kill mid-session sticks the FC's passthrough state — "
        "see docs/knowledge/hardware-findings.md). No effect without --discover-unresolved.",
    )
    p_dumpfw.add_argument(
        "--time-budget",
        type=float,
        default=None,
        help="stop --discover-unresolved cleanly (same as Ctrl-C: exits the 4-way-if session "
        "properly, checkpoint fully saved) after this many seconds of wall-clock time, rather "
        "than running to completion. Checked once per window, so an in-progress window's "
        "current --max-combo k-level may run a bit over. Pass e.g. 15300 for a 4h15m session. "
        "No effect without --discover-unresolved; unlimited if omitted.",
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

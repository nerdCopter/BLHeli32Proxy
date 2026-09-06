"""blheli32proxy command-line entry point.

See docs/USAGE.md for full usage and OS-level IP/domain redirection instructions.
Subcommands:
  serve               - run the approval/activation server (the actual project deliverable)
  gen-cert            - generate a self-signed TLS cert/key pair for `serve --tls`
  list-test-firmware  - list the user's archived test-firmware .Hex files (read-only)
  dump-setup          - read+best-effort-decrypt an ESC's Setup block (needs real hardware)
  probe-flash         - read-only sanity check of one flash address (needs real hardware)
  dump-flash          - read-only dump of a flash address range to a NEW file (needs real hardware)

dump-setup/probe-flash/dump-flash all take --motor-index when --port is a flight
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


def _archive_dir() -> Path | None:
    """User's archived BLHeli material, from $BLHELI32PROXY_ARCHIVE_DIR. No
    hardcoded default — the archive lives outside this repo and its path is
    machine-specific."""
    value = os.environ.get(ARCHIVE_DIR_ENV_VAR)
    return Path(value).expanduser().resolve() if value else None

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
            f"--dir not given and ${ARCHIVE_DIR_ENV_VAR} is not set. "
            f"Pass --dir explicitly or set the env var.",
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


def _cmd_dump_setup(args: argparse.Namespace) -> int:
    """Read an ESC's Setup block and print a best-effort decrypt. Not part of
    the normal flashing workflow (the real BLHeliSuite32xl app handles that)
    — see PLAN.md §4 and docs/knowledge/protocol-reference.md."""
    from .cipher import xtea
    from .protocol.transport import SerialTransport

    key = xtea.TEST_FIRMWARE_KEY if args.test_firmware else xtea.PRODUCTION_KEY
    transport = SerialTransport(args.port)

    if args.motor_index is not None:
        return _dump_setup_via_fourwayif(transport, args.motor_index, key, args.out)

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
    finally:
        client.disconnect()
        transport.close()
    return 0


def _dump_setup_via_fourwayif(transport, motor_index: int, key, out_path: str | None) -> int:
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
    """FC-passthrough path (--motor-index) — see _dump_setup_via_fourwayif's
    docstring for the protocol this uses. A single 4-way-if frame can only
    carry up to 256 bytes; use dump-flash for larger ranges."""
    from .protocol import fourwayif as fw

    if length > 256:
        print("--length must be <= 256 for a single 4-way-if read; use dump-flash instead.", file=sys.stderr)
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


def _dump_flash_archive_guard(out_path: Path) -> int | None:
    """Returns an exit code if the write should be refused, else None."""
    archive_root = _archive_dir()
    if archive_root is None:
        print(
            f"Warning: ${ARCHIVE_DIR_ENV_VAR} is not set — cannot check whether --out lands "
            f"inside your archived BLHeli material. Verify --out yourself.",
            file=sys.stderr,
        )
        return None
    try:
        out_path.relative_to(archive_root)
    except ValueError:
        pass
    else:
        print(
            f"Refusing to write into the archived BLHeli directory ({archive_root}). "
            f"Choose a different --out path.",
            file=sys.stderr,
        )
        return 1
    return None


def _cmd_dump_flash(args: argparse.Namespace) -> int:
    """Dump a flash address range to a NEW file. Refuses to write anywhere under
    the user's archived BLHeli material, as a safety backstop on top of just
    defaulting elsewhere. Read-only against the ESC."""
    from .protocol.transport import SerialTransport

    out_path = Path(args.out).expanduser().resolve()
    guard_result = _dump_flash_archive_guard(out_path)
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
        return _dump_flash_via_fourwayif(transport, args.motor_index, start, end, args.chunk_size, out_path)

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


def _dump_flash_via_fourwayif(transport, motor_index, start, end, chunk_size, out_path) -> int:
    """FC-passthrough path (--motor-index) — see _dump_setup_via_fourwayif's
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
    _default_archive = _archive_dir()
    p_list.add_argument(
        "--dir",
        default=str(_default_archive) if _default_archive else None,
        help=f"directory of test-firmware .Hex files "
        f"(default: ${ARCHIVE_DIR_ENV_VAR} itself, if that env var is set — point it directly at "
        f"a flat folder of .Hex files, e.g. this repo's own testcode/)",
    )
    p_list.set_defaults(func=_cmd_list_test_firmware)

    p_dump = sub.add_parser("dump-setup", help="(experimental, needs hardware) read+decrypt a Setup block")
    p_dump.add_argument("--port", required=True, help="serial port, e.g. /dev/ttyACM0 or COM3")
    p_dump.add_argument("--test-firmware", action="store_true", help="use the test-firmware XTEA key")
    p_dump.add_argument(
        "--motor-index",
        type=int,
        default=None,
        help=MOTOR_INDEX_HELP,
    )
    p_dump.add_argument(
        "--out",
        default=None,
        help="append this ESC's confirmed fields as an [ESCn] section to a partial-backup "
        "file (creates it with a not-a-real-.ixi warning header if new) — confirmed fields "
        "only, never a complete or loadable .ixi",
    )
    p_dump.set_defaults(func=_cmd_dump_setup)

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

    p_dumpflash = sub.add_parser(
        "dump-flash",
        help="(experimental, needs hardware) read-only dump of a flash range to a NEW file",
    )
    p_dumpflash.add_argument("--port", required=True, help="serial port, e.g. /dev/ttyACM0 or COM3")
    p_dumpflash.add_argument("--start", default="0x0000", help="start address, inclusive")
    p_dumpflash.add_argument("--end", required=True, help="end address, exclusive")
    p_dumpflash.add_argument(
        "--out",
        required=True,
        help=f"output file path (refused if it falls under ${ARCHIVE_DIR_ENV_VAR}, when that env var is set)",
    )
    p_dumpflash.add_argument("--chunk-size", type=int, default=256)
    p_dumpflash.add_argument("--overwrite", action="store_true", help="allow overwriting an existing --out file")
    p_dumpflash.add_argument(
        "--motor-index",
        type=int,
        default=None,
        help=MOTOR_INDEX_HELP,
    )
    p_dumpflash.set_defaults(func=_cmd_dump_flash)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

# BLHeli32Proxy — Implementation Status

See [PLAN.md](PLAN.md) for the architecture and why it's shaped this way — in short: the user keeps using
the real, unmodified `BLHeliSuite32xl` app for all ESC communication (flashing, config). This
project's actual deliverable is the **approval server** (`src/blheli32proxy/approval/`) that stands
in for BLHeli's dead activation server, reached via an OS-level hostname *and port* redirect (see
`docs/USAGE.md` §4). **Real hostname and the status-check request/response CONFIRMED**, both via
traffic decryption and, separately, live against the real app through this project's own server
(see [Activation & Licensing](docs/knowledge/activation-licensing.md)): `GET/HEAD
https://blheli.org/BLHeli32_2017_1/status.php?p=BLHeliSuite32xl&v=1044`, response format
`SERVER>text=...;` (not JSON). The still-unconfirmed piece is the separate ESC-activation call
(needs an actual flash+activate attempt — see `MENU.md` item 6).

## What exists and is tested

All 116 tests pass (`.venv/bin/python -m pytest tests/`), all in a `.venv` created in the project
root (`python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"`).

| Module | Status | Verified how |
|---|---|---|
| `protocol/crc.py` | Done | 10 test vectors taken verbatim from real captured protocol bytes in the research (`tests/test_crc.py`) |
| `protocol/frames.py` | Done | Frame builders/parsers checked against the same real captures. **Found and fixed two real errors in the research notes while doing this** (see below) |
| `protocol/transport.py` | Done | `Transport` ABC + `SerialTransport` (pyserial) + `HidTransport` (hidapi). Both real backends are untested here (need real hardware); `tests/fakes.py`'s `FakeTransport` covers the abstraction itself |
| `protocol/client.py` | Partial, by design | Connect/keepalive/disconnect/read/write of the 256-byte Setup block: done, tested via `FakeTransport` against real byte sequences. `flash_firmware()` deliberately raises `NotImplementedError` — see "Known gap" below. **Not the flashing path** — kept as read-only diagnostic tooling only ([PLAN.md §4](PLAN.md#4-architecture-decision)). Also adds `read_flash_region_experimental()`/`dump_flash_experimental()` — arbitrary-address read-only flash access using an *extrapolated* (not confirmed) length encoding; see the module docstring and `cli.py`'s `probe-flash`/`dump-info-page` commands |
| `cipher/xtea.py` | Done, unverified against hardware | 32-round XTEA per the reverse-engineered reference algorithm (not textbook XTEA — the asymmetric key-index extraction between the two round-halves is deliberate, see the module docstring). Encrypt/decrypt round-trip tested; **not** validated against a real (plaintext, ciphertext) pair since none exists in the research — flagged clearly in the module docstring |
| `flash/` | Not started | No firmware-flashing implementation exists or is planned as a from-scratch client — the real app does this now ([PLAN.md §4](PLAN.md#4-architecture-decision)) |
| `approval/codec.py` | **One endpoint CONFIRMED**, one still placeholder | `is_status_check_request()`/`decode_status_check_query()`/`encode_status_check_response()` implement the real, captured `GET/HEAD /BLHeli32_2017_1/status.php?p=...&v=...` → `SERVER>text=...;` protocol exactly (see [Activation & Licensing](docs/knowledge/activation-licensing.md)). The empty-body response for the "no update needed" case is confirmed non-fatal against the real app (not just a guess anymore), though not necessarily the *ideal* response shape — see Activation & Licensing for the open detail. `decode_request()`/`encode_response()` remain JSON-based placeholders for the still-unconfirmed, separate ESC-activation endpoint |
| `approval/policy.py` | Done | `AllowAllPolicy` (default) and `CountedLicensePolicy` (JSON-file-backed, UUID-keyed, idempotent re-activation) — both tested, including cross-instance state persistence. Not used by the confirmed status-check endpoint (it isn't a licensing decision) |
| `approval/server.py` | Done | stdlib `http.server`-based, HTTP or HTTPS (via `ssl.SSLContext`), HEAD support added for the confirmed endpoint, verbose request logging. Tested with real socket connections, not mocked, including GET+HEAD against the confirmed path |
| `protocol/msp.py` | Done, but not the real path | MSP v1 framing + `enable_esc_passthrough()`/`exit_esc_passthrough()` for `MSP_SET_PASSTHROUGH` mode=1 (`PROTOCOL_BLHELI` raw relay). **Confirmed dead over USB CDC-ACM on real hardware** (`usbmon` capture) — never used by the CLI; kept for reference/tests only. See the module docstring and [Protocol Reference](docs/knowledge/protocol-reference.md) |
| `protocol/fourwayif.py` | Done, **live-verified on real hardware across 4 ESC families** | The real framed 4-way-if bootloader protocol BLHeliSuite32xl/AM32-Configurator actually use. Request/reply build+parse tested against real bytes captured from BLHeliSuite32xl's own traffic (not invented). `enter_4way_if()`/`connect_esc()`/`read_flash()`/`exit_interface()` live-tested end-to-end via a real flight controller against 4 different ESC families/firmware revisions: connected to each board's channels, read device signatures and 256-byte Setup blocks, decrypted with `cipher/xtea.py`, and cleanly exited every time — no power-cycle needed. `connect_esc()` includes a `reset_settle_delay` (100ms, unconditional between reset and init-flash) and a `retry_delay` (5.5s, after a failed attempt) — both derived from real BLHeli firmware timing behavior, see [Hardware Findings](docs/knowledge/hardware-findings.md) and [Protocol Reference](docs/knowledge/protocol-reference.md) |
| `protocol/setup_fields.py` | Done, partial by design, **live-verified against real backups on 3 MCU vendors / 4 firmware revisions** | Decodes 45 of 46 known Setup-block field names from the decrypted plaintext — every value matches a real BLHeliSuite32xl-produced `.ixi` backup file exactly. Byte offsets confirmed identical across 3 independent MCU vendors (STM32, GD32, AT32) and 4 firmware revisions (32.7 through 32.10), via differential capture, direct `.ixi` cross-reference, cross-board value correlation, and this project's own research corpus — see [Setup Block Fields](docs/knowledge/setup-block-fields.md) for the full method breakdown. Only `Eep_ESC_Mode` remains unconfirmed (checked exhaustively, not just deferred). Also provides `decode_name()`/`decode_esc_layout()`/`decode_note_array()` for the 3 string/array fields, and `format_ixi_section()`, a confirmed-fields-only `.ixi`-style section writer — never fabricates unconfirmed fields, and its output must never drive a write-back/restore path (see the module docstring) |
| `cli.py` | Done | `serve`, `gen-cert` (shells out to `openssl`), `dump-config`/`probe-flash`/`dump-info-page` — `--motor-index` drives `protocol/fourwayif.py` (the confirmed-real path); without it, the original direct-adapter `protocol/client.py` path (untested here beyond argument parsing and the archive-write refusal, which is tested). `dump-config --out FILE` appends a partial-backup `.ixi`-style section via `setup_fields.format_ixi_section()` |
| `cli.py: list-test-firmware` | Done, test-covered | Lists `*.Hex` filenames in a directory (read-only), sorted. Defaults `--dir` to `$BLHELI32PROXY_ARCHIVE_DIR` if set. Unit-tested (`tests/test_cli.py`): filters non-`.Hex` files, sorts output, honors the env-var default, and errors cleanly on a missing `--dir`/env var or a non-directory path |

## Known gap: firmware flash-write protocol was never captured

`protocol/client.py`'s `flash_firmware()` raises `NotImplementedError` on purpose. The research
corpus documents the 256-byte Setup/config-block write in full byte-level detail, but never
captured the byte-level protocol for writing a full firmware image to flash (the debug log in
`BLHeliSuite32-Reverse.en.md` shows a 1024-byte flash page size — a different granularity than the
256-byte config write, so it's very likely a different command sequence, not a trivial extension).
This is now moot for the actual project goal (the real app does the flashing), but the stub is left
in place, clearly documented, rather than removed — some future use might still want it, and it
should never be filled in by guessing.

## Experimental firmware extraction (read-only, opposite direction from the gap above)

`probe-flash` and `dump-info-page` CLI commands, backed by
`BLHeliClient.read_flash_region_experimental()`/`dump_flash_experimental()`. These read
(never write) an arbitrary flash address, extrapolating the read-length wire encoding from the
two confirmed data points (16 bytes ↔ length byte `0x10`, 256 bytes ↔ length byte `0x00`) to a
general "N bytes ↔ length byte N, with 0x00 meaning 256" rule. This extrapolation is **not**
confirmed by any captured traffic — a wrong guess fails safely (the existing CRC/ACK check in
`parse_read_reply` rejects a malformed reply) rather than doing anything to the hardware.

Two things worth remembering if this is used:
1. It may simply not work: ESC bootloaders commonly restrict reads to a small set of whitelisted
   addresses specifically to prevent firmware extraction/cloning — exactly the kind of protection
   a paid-activation firmware business would want. A refusal or garbage result at address `0x0000`
   is a legitimate, informative outcome, not a sign the tool is broken.
2. `dump-info-page` refuses at the path level to write into `$BLHELI32PROXY_ARCHIVE_DIR` (the user's
   read-only archive), when that env var is set, independent of whatever `--out` path is passed —
   automated test in `tests/test_cli.py`.

**Superseded for the `--motor-index` (FC-passthrough) case**: the paragraph above describes the
direct-adapter path (`protocol/client.py`'s extrapolated length encoding, still used when
`--motor-index` is omitted). When `--motor-index` **is** given, `cli.py` now uses
`protocol/fourwayif.py` instead — the real, confirmed bootloader protocol (not an extrapolation),
live-verified reading an actual ESC's Setup block through a real flight controller. See
[Protocol Reference](docs/knowledge/protocol-reference.md).

## Two research-note errors found and fixed during implementation

Building `tests/test_frames.py` against real captured bytes surfaced two mistakes in
`research/notes/BLHeli-Uart-Usb-Protocol.en.md` (both now corrected in that file, with a note left
in place explaining what was wrong):

1. The `0xF7AC` (device-info) read reply's payload/CRC boundary was mis-split at 12 bytes instead
   of the correct 16 — confirmed by recomputing CRC-16/IBM against both splits and finding only the
   16-byte split matches the captured trailer.
2. The connect reply's device-type field was assumed to sit at a fixed byte offset from a single
   example capture; the capture actually has 3 bytes (positions 3, 6-7 of a 9-byte reply) that the
   *original Chinese source itself* never explains. `parse_connect_reply()` scans for a known
   device-type code instead of assuming a fixed position, and the note now says so explicitly.

## Manual next steps (not automatable in this environment)

- **The real ESC-activation call is the one thing still not captured.** Real hostname
  (`blheli.org`) and the status-check endpoint are confirmed (see
  [Activation & Licensing](docs/knowledge/activation-licensing.md)); the separate per-ESC
  activation request/response is not. Note: `blheli.org`'s root path (`/`) serves only a static
  placeholder page, not evidence of any live backend — don't read anything into it. Capturing the
  real activation call needs an actual flash+activate attempt through the real app against a
  connected ESC — see `docs/USAGE.md` §7a/§7b for the capture method, and `MENU.md` item 6 for the
  guided, safety-gated procedure.
- Once the exact schema is captured: update `approval/codec.py`'s field-name lists and, if the
  format isn't JSON at all, its decode/encode logic — nothing else needs to change.
- Real-hardware verification of `protocol/` ([PLAN.md §5](PLAN.md#5-implementation-language-and-structure) phase-1-equivalent) if the diagnostic
  `dump-config` command is ever relied on.

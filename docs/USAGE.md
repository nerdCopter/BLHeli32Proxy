# BLHeli32Proxy — Usage

This tool does **not** flash ESCs itself. You keep using the real, unmodified `BLHeliSuite32xl`
app exactly as before for everything ESC-facing (flashing, reading/writing config). This project
runs a small local server that stands in for BLHeli's activation server, so the real app's
licensing/activation check gets answered locally. See [PLAN.md §4](../PLAN.md#4-architecture-decision) for why.

**Naming note**: this document uses `BLHeliSuite32xl` (the Linux executable's name) as shorthand
for the vendor configurator app throughout. The real executable name and folder are OS-specific —
Windows: `BLHeliSuite32.exe`; macOS: `BLHeliSuite32xm.app` — there's no folder-naming convention
this project enforces, only whatever your own install uses.

**Status note**: the real "check for updates" / Flash-tab request is fully confirmed, decrypted
live via `tshark` + `SSLKEYLOGFILE` ([PLAN.md §4](../PLAN.md#4-architecture-decision), "Third capture"):
```
GET/HEAD https://blheli.org/BLHeli32_2017_1/status.php?p=BLHeliSuite32xl&v=1044
→ SERVER>text=Server is down for maintenance. Please try again later. Thank you for your patience.;
```
This server now answers that exact confirmed path with that exact confirmed format (`approval/codec.py`).
What's **still unverified**: what a "no update needed, proceed normally" response looks like (this
server currently guesses an empty body — never observed for real), and the separate
**ESC-activation** request (needs an actual connected-ESC flash+activate attempt, not yet done).
[§7a](#7a-capturing-raw-traffic-with-tcpdump-no-redirect-needed-do-this-first)/[§7b](#7b-capturing-the-exact-request-via-this-projects-own-server-do-this-after-redirecting) below cover how to capture that next.

## Command reference

Every `blheli32proxy` subcommand, for quick lookup. Each links to the section with the full
how-to/example. Run `blheli32proxy <command> --help` any time for this same info from the tool
itself — the tables below are generated from that output, so they can't drift from what the code
actually does.

| Command | Purpose | Needs an ESC connected? |
|---|---|---|
| [`serve`](#3-run-the-approval-server) | Run the approval/activation server | No |
| [`gen-cert`](#2-generate-a-tls-certificate-needed-if-the-real-activation-call-is-https-which-is-likely) | Generate a self-signed TLS cert/key pair for `serve --cert/--key` | No |
| [`list-test-firmware`](#6a-listing-archived-test-firmware) | List your archived test-firmware `.Hex` files (read-only) | No |
| [`dump-config`](#6-diagnostics-experimental-needs-real-hardware) | Read + best-effort-decrypt an ESC's 256-byte Setup/config block | Yes |
| [`probe-flash`](#6b-extracting-a-firmware-backup-experimental-read-only) | Read a small chunk at an arbitrary flash address (sanity check before `dump-info-page`) | Yes |
| [`dump-info-page`](#6b-extracting-a-firmware-backup-experimental-read-only) | Dump a flash address range to a new file (never into your archive) | Yes |

### `serve`

```
usage: blheli32proxy serve [-h] [--host HOST] [--port PORT] [--cert CERT]
                           [--key KEY] [--policy {allow-all,counted}]
                           [--state-file STATE_FILE]
                           [--initial-count INITIAL_COUNT] [--verbose]

  --host HOST           bind address (default: 0.0.0.0)
  --port PORT           bind port (default: 8443)
  --cert CERT           TLS certificate file (enables HTTPS)
  --key KEY             TLS private key file (required with --cert)
  --policy {allow-all,counted}
                        approval policy (default: allow-all)
  --state-file STATE_FILE
                        state file for --policy counted
  --initial-count INITIAL_COUNT
                        starting count for --policy counted (default: 1000)
  --verbose             log full request/response detail
```
Full walkthrough: [§3](#3-run-the-approval-server) (running it), [§4](#4-redirect-the-activation-hostname-to-this-server-os-level) (pointing the real app at it), [§5](#5-running-the-server-automatically-optional) (running it as a background service).

### `gen-cert`

```
usage: blheli32proxy gen-cert [-h] [--out OUT] [--common-name COMMON_NAME] [--days DAYS]

  --out OUT             output directory (default: ~/.blheli32proxy)
  --common-name COMMON_NAME
                        certificate CN — should match the redirected hostname (default: localhost)
  --days DAYS           validity period (default: 825)
```
Shells out to `openssl` — see [§2](#2-generate-a-tls-certificate-needed-if-the-real-activation-call-is-https-which-is-likely) for install notes on each OS. Produces `approval.crt`/`approval.key` in `--out`.

### `list-test-firmware`

```
usage: blheli32proxy list-test-firmware [-h] [--dir DIR]

  --dir DIR   directory to list (default: $BLHELI32PROXY_ARCHIVE_DIR itself, if that env var is
              set; otherwise --dir is required)
```
Read-only — just prints matching `*.Hex` filenames, one per line. Useful for picking which
archived test-firmware file to flash *through the real `BLHeliSuite32xl` app* (this tool doesn't
flash anything itself — see [§6](#6-diagnostics-experimental-needs-real-hardware)). Example:
```bash
export BLHELI32PROXY_APP_DIR=~/path/to/BLHeliSuite32xl   # see §1a
blheli32proxy list-test-firmware
blheli32proxy list-test-firmware --dir /path/to/other/firmware/dir
```

### `dump-config`

```
usage: blheli32proxy dump-config [-h] --port PORT [--test-firmware]
                                  [--motor-index MOTOR_INDEX] [--direct]
                                  [--show-defaults CANDIDATE_HEX] [--out OUT]
                                  [--raw-dir RAW_DIR]

  --port PORT        serial port, e.g. /dev/ttyACM0 or COM3 (required)
  --test-firmware    use the test-firmware XTEA key instead of the production one
  --motor-index N    dump just this one ESC via FC-passthrough (omit to dump every
                      ESC the FC reports — the default)
  --direct           connect directly as a single standalone device instead of via
                      an FC's 4-way-if passthrough (mutually exclusive with --motor-index)
  --show-defaults    compare against a candidate firmware .Hex's factory-default Setup block
  --out OUT          append confirmed fields as an [ESCn] section to a partial-backup file
                      (decoded fields only, never a complete/loadable .ixi)
  --raw-dir RAW_DIR  also save each dumped ESC's exact 256-byte ciphertext to
                      <raw-dir>/esc<N>-setup-<timestamp>.bin — a byte-exact backup
                      usable for a full restore
```
See [§6](#6-diagnostics-experimental-needs-real-hardware) for what this does and its caveats
(cipher unverified against real hardware).

### `probe-flash`

```
usage: blheli32proxy probe-flash [-h] --port PORT [--address ADDRESS] [--length LENGTH]

  --port PORT        serial port, e.g. /dev/ttyACM0 or COM3 (required)
  --address ADDRESS  flash address to read, e.g. 0x0000 (default: 0x0000)
  --length LENGTH    bytes to read, 1-256 (default: 16)
```
See [§6b](#6b-extracting-a-firmware-backup-experimental-read-only) — always run this before `dump-info-page`.

### `dump-info-page`

```
usage: blheli32proxy dump-info-page [-h] --port PORT [--start START] --end END
                                --out OUT [--chunk-size CHUNK_SIZE] [--overwrite]

  --port PORT           serial port, e.g. /dev/ttyACM0 or COM3 (required)
  --start START         start address, inclusive (default: 0x0000)
  --end END             end address, exclusive (required)
  --out OUT             output file path — refused if it resolves inside
                        $BLHELI32PROXY_ARCHIVE_DIR, when that env var is set (required)
  --chunk-size CHUNK_SIZE
                        bytes read per transaction, 1-256 (default: 256)
  --overwrite           allow overwriting an existing --out file
```
See [§6b](#6b-extracting-a-firmware-backup-experimental-read-only) for the full how-to and safety notes.

### `dump-firmware`

```
usage: blheli32proxy dump-firmware [-h] --port PORT --candidate CANDIDATE
                                   [--start START] [--end END]
                                   [--out OUT] [--overwrite] [--motor-index MOTOR_INDEX]

  --port PORT           serial port, e.g. /dev/ttyACM0 or COM3 (required)
  --candidate CANDIDATE a candidate .Hex file to compare against (repeat for
                        multiple; first match wins per chunk, required)
  --start START         start address, inclusive (default: the earliest address any
                        --candidate covers — never lower, works for any model/MCU)
  --end END             end address, exclusive (default: one past the latest address
                        any --candidate covers)
  --out OUT             output file path — same archive-write refusal as dump-info-page
  --overwrite           allow overwriting an existing --out file
```
See [§6c](#6c-extracting-application-code-firmware-via-the-verify-oracle-experimental-read-only)
for the full how-to and safety notes.

## Next testing session checklist (do this when a BLHeli_32 ESC is available)

Follow **this document**, in this order, once you have a 32-bit ESC connected. Nothing past step 2
needs the ESC yet — do those first, any time.

1. [§1](#1-install)-[§4](#4-redirect-the-activation-hostname-to-this-server-os-level) below: install, generate a cert, run the server, redirect `blheli.org` to it, trust the
   cert. Can all be done today, no ESC needed.
2. [§7a](#7a-capturing-raw-traffic-with-tcpdump-no-redirect-needed-do-this-first): capture raw traffic with `tcpdump` **before** redirecting anything (or with the redirect
   removed), so you see what the app *actually* tries to reach for a real activation — don't
   assume it's the same `blheli.org` hostname the "check for updates" call used.
3. Re-enable the redirect ([§4](#4-redirect-the-activation-hostname-to-this-server-os-level)), connect the ESC, run `BLHeliSuite32xl`, and attempt to flash +
   activate the ESC normally, through the real app, exactly as you always would.
4. [§7b](#7b-capturing-the-exact-request-via-this-projects-own-server-do-this-after-redirecting): while doing step 3, watch this project's `blheli32proxy serve --verbose` log — that's the
   real activation request, captured for the first time. Compare it against
   `src/blheli32proxy/approval/codec.py`'s placeholder assumptions and update that one file to
   match (see [§7b](#7b-capturing-the-exact-request-via-this-projects-own-server-do-this-after-redirecting) for exactly what to change).
5. If the app accepts the server's response and reports the ESC activated/flashed successfully,
   the loop is closed — the approval server is doing its real job. If it doesn't, the
   [Troubleshooting](#troubleshooting) section at the bottom covers the two ways this can fail (wrong wire format vs.
   cert trust/pinning) and how to tell them apart.

Record what you find (the real request path/body, whether flashing itself worked) back into
[PLAN.md §4](../PLAN.md#4-architecture-decision) and `IMPLEMENTATION.md` — those still say this is unconfirmed as of now.

## 1. Install

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Requires Python 3.9+. Works on Linux, macOS, and Windows — the codebase is plain Python 3 with no
OS-specific code paths in the approval server itself (only the optional hardware-facing
`protocol/transport.py` backends touch OS-specific APIs, and those aren't needed to run the server).

## 1a. Point the tool at your test-firmware catalog

**Quick setup**: `scripts/setup-env.sh` checks what's already set, asks for whatever's missing, and
saves it to your shell rc file — safe to re-run any time.

```bash
./scripts/setup-env.sh
```

Or set them manually — details below.

`list-test-firmware`'s `--dir` default, `dump-firmware`'s `--candidate` search, and
`dump-info-page`'s archive-write safety check all read **two** environment variables — a **flat
folder of `.Hex` files** either way (no version subfolders needed; filenames already encode
manufacturer/layout/version):

- **`BLHELI32PROXY_APP_DIR`** — the vendor app's (`BLHeliSuite32xl`/`.exe`/`.app`) install folder.
  Most users only need this one: the tool derives its `BLHeli32_HexFiles/` subfolder automatically
  (the same folder the real app itself reads its Flash-tab dropdown from — see
  [§6](#6-diagnostics-experimental-needs-real-hardware) for why that folder must be populated
  anyway, independent of this project).
- **`BLHELI32PROXY_ARCHIVE_DIR`** — optional, for a broader personal collection kept separately
  from the app's own folder (e.g. every historical version, not just what the app currently
  bundles). Checked first when both are set.

A third, separate variable speeds up [§1b](#1b-obtaining-test-firmware-hex-files-from-the-official-source)'s
`scripts/fetch-testcode.sh` only (not read by anything else):

- **`BLHELI32PROXY_CLONE_DIR`** — optional, a local clone of `bitdump/BLHeli` to reuse (`git fetch`)
  instead of recloning the whole source history on every run.

```bash
export BLHELI32PROXY_APP_DIR=~/path/to/BLHeliSuite32xl        # most users: this alone is enough
export BLHELI32PROXY_ARCHIVE_DIR=~/path/to/a/broader/archive  # optional, power users only
export BLHELI32PROXY_CLONE_DIR=~/path/to/a/BLHeli/clone       # optional, speeds up fetch-testcode.sh
```

Add whichever you use to your shell profile (`~/.bashrc`, `~/.zshrc`) to persist it. This project
only ever reads from either directory (never writes into it, except the deliberate refusal check
below, which covers both). If neither is set: `list-test-firmware --dir` becomes required (no
default), and `dump-info-page`/`dump-firmware` still run but skip the archive-write safety check
with a warning — double-check `--out` yourself in that case.

## 1b. Obtaining test-firmware `.Hex` files from the official source

**Prerequisite**: `$BLHELI32PROXY_APP_DIR` or `$BLHELI32PROXY_ARCHIVE_DIR` must already be set (run
[§1a](#1a-point-the-tool-at-your-test-firmware-catalog)'s `scripts/setup-env.sh` first if not) — it
determines where the fetched files land.

**Quick path — no AI needed, plain reproducible script**:

```bash
./scripts/fetch-testcode.sh latest   # final snapshot only (~500 files, fastest)
./scripts/fetch-testcode.sh recent   # + every 32.7.x/32.8.x version commit (~2500 files)
./scripts/fetch-testcode.sh all      # + every version commit back to 32.31, 2018 (~4000 files)
```

This project never bundles or publishes BLHeli's copyrighted vendor firmware — the script above
fetches your own copy directly from BLHeli's own official GitHub history and copies the files into
whichever directory you configured (its `BLHeli32_HexFiles/` subfolder if using
`$BLHELI32PROXY_APP_DIR`, or directly into `$BLHELI32PROXY_ARCHIVE_DIR` if you use that instead).
Set `$BLHELI32PROXY_CLONE_DIR` (via `scripts/setup-env.sh`) to a persistent local clone of the
source repo to skip re-cloning on every run — the script reuses it (`git fetch`) instead of
recloning if it already exists there.

**Source**: `https://github.com/bitdump/BLHeli` — the `BLHeli_32 ARM/` folder held the full
per-manufacturer test-firmware collection until it was removed on 2024-06-04 (commit `26fbb46e41`,
"Removed testcodes"), after the vendor shut down mid-2024. Everything below recovers those files
from the repo's own history — nothing is bundled in this repo itself.

**Why three modes**: the repo organized test firmware by dedicated version-named folder
(`Rev32.7.1 SBUS and S.PORT testcode`, `Rev32.8.3 testcode`, etc.) from 32.31 (2018) through 32.8.3
(2022). After that it switched to purpose-named category folders (`Loaded startup testcode`, `Misc
testcodes`, `Dshot extended telemetry testcode`) that keep accumulating every manufacturer's newest
build without a per-version folder — so `latest`'s single snapshot already contains every 32.9.x
and 32.10.x file that exists, but misses the versioned 32.7.x/32.8.x (and older) folders that were
superseded and removed from the live tree. `recent`/`all` recover those by checking out each
version folder's introducing commit directly (via `git archive`, so this never touches the working
tree of a reused `$BLHELI32PROXY_CLONE_DIR`). `Plane nondamped testcode` (fixed-wing-specific
builds) is excluded from every mode — out of scope for this multirotor-focused project.

**Commits fetched by `recent`** (in addition to the `latest` snapshot, `9577152ca9`):

| Commit | Date | Version |
|---|---|---|
| `d33b11320491dec72239a4585b39e7bbe0ff9b3a` | 2020-05-16 | 32.7.1 |
| `b4cc04f5779af0e7cb3918c6f10cfbfff343e89e` | 2020-08-19 | 32.7.2 |
| `41967a136ba738198f41e53e5b473d0d38819a74` | 2020-10-25 | 32.7.3 |
| `118d19dd86a752292d911d96c747a82286839165` | 2021-02-08 | 32.7.4 |
| `845dd75091994ef448a8a0869c174e3ae29112db` | 2021-08-01 | 32.8.1 |
| `653782e83a77f9135914d74a59e8337088392185` | 2021-09-26 | 32.8.2 |
| `49948e301c47553db309c871b79d5c0689bae018` | 2022-03-30 | 32.8.3 |

**Additional commits fetched by `all`**:

| Commit | Date | Version |
|---|---|---|
| `87a9039a44e4491e1ca828dd6e81ef1df9b8ebcb` | 2018-01-07 | 32.31 |
| `871f70a42b4a2f1598891c2865cf4c26a8b837fd` | 2018-05-12 | 32.41 |
| `9570713045d3ad6f5f729659993fea33fb914377` | 2018-06-06 | 32.42 |
| `d389bf18fe4302f23fc58dde93bfb51944497d62` | 2018-06-14 | 32.43 |
| `26fa7477db2e32836866b42c0101ec837bd4fcdb` | 2018-07-06 | 32.5 |
| `482cb2cdf3cb03de37cb7c5e6cf26e00a6a1eed4` | 2018-07-12 | 32.51 |
| `b0b26936e7f7a9f404ae6f742207b615ea68008b` | 2018-07-20 | 32.52 |
| `d5f34b02ce8e1a71277a443e5df70eff8446a2f2` | 2018-08-21 | 32.6 |
| `dd24d5ddfa3122f1dc11d4456da4471abf53fa52` | 2019-01-05 | 32.61 |
| `f29edcdfc09809b864fafa471825a39237e14c14` | 2019-04-24 | 32.6.1 |
| `dbec3853f23785fb8165c9d1bf27d8ca65c06f23` | 2019-02-10 | 32.6.3 |
| `52b241588ee0b1fca3dce50ab3e9debd4207ff00` | 2019-06-02 | 32.6.2 |
| `e5a180ed40ac7d6bc20e1d67a98da2aad5730968` | 2019-02-19 | 32.6.5 |
| `4fc458c0681809182e9ad6eff08a3c28b62b6be9` | 2019-02-26 | 32.6.6 |
| `d7dd1b948912913a21cd6e000104a3e4b32df56f` | 2019-03-14 | 32.6.7 |
| `0c2024f4e75838b147c25ab3745b9877ce1335cd` | 2019-03-27 | 32.6.8 |
| `f2df802066df6e23b93ae953592abde742220c32` | 2019-03-31 | 32.6.9 |
| `4218a713c408e7f484a728b75922fa05daa68032` | 2019-09-28 | 32.6.4 |

Re-derive this list yourself if you need to double check it or extend it further back:

```bash
git clone https://github.com/bitdump/BLHeli.git /tmp/blheli-source
cd /tmp/blheli-source
git log --all --diff-filter=A --name-only --format="COMMIT|%H|%ad" --date=short -- "BLHeli_32 ARM" \
  | grep -B1 -iE "Rev32|Test ?code" | less
```

**Verifying it worked**:

```bash
blheli32proxy list-test-firmware   # uses whichever env var you set above
```

**For an AI assistant automating this**: confirm `latest`/`recent`/`all` with the user if
unstated (`latest` is the safe default); run `scripts/fetch-testcode.sh` directly rather than the
manual commands above — it is the reproducible, no-AI-needed path; report the file count it prints;
never commit the copied `.Hex` files to this project's own repo (see the Publishing Gate in
`AGENTS.md`).

## 2. Generate a TLS certificate (needed if the real activation call is HTTPS, which is likely)

```bash
blheli32proxy gen-cert --out ~/.blheli32proxy --common-name blheli.org
```

Replace `blheli.org` with the real hostname once known (see [PLAN.md §4](../PLAN.md#4-architecture-decision)) — the
certificate's Common Name should match the hostname the app will be connecting to, or most TLS
clients will reject it even if the issuing CA is otherwise trusted.

This shells out to `openssl` (present by default on Linux/macOS; on Windows, install via
[Git for Windows](https://gitforwindows.org/) which bundles it, or `winget install
ShiningLight.OpenSSL`). Produces `approval.crt` and `approval.key` in the output directory.

**Confirmed** (see [Activation & Licensing](knowledge/activation-licensing.md)):
`BLHeliSuite32xl` trusts the OS certificate store — a CA-trusted self-signed cert (trusted at the
OS level per step 4 below) was accepted with no pinning failure, live, against the real app. No
binary patching needed.

## 3. Run the approval server

```bash
blheli32proxy serve --host 0.0.0.0 --port 8443 \
    --cert ~/.blheli32proxy/approval.crt --key ~/.blheli32proxy/approval.key \
    --policy allow-all
```

- `--policy allow-all` (default): approves every request unconditionally — appropriate for
  personal use on your own hardware.
- `--policy counted --initial-count N --state-file ~/.blheli32proxy/license-state.json`: approves
  up to `N` distinct ESC UUIDs, then refuses; re-approving an already-seen UUID never consumes
  another count. Mirrors the real tool's per-UUID ledger behavior ([Activation & Licensing](knowledge/activation-licensing.md)) if you want
  metering rather than unconditional allow.
- Every request is logged in full (`--verbose` for more detail) — useful for confirming the real
  app is actually reaching this server, and as a second way to learn the real request format if
  you point the real app here speculatively before the format is otherwise known.

Leave this running in a terminal (or set it up as a system service — see [§5](#5-running-the-server-automatically-optional)) whenever you plan to
use `BLHeliSuite32xl`.

## 4. Redirect the activation hostname to this server (OS-level)

Once you know the real activation hostname (`blheli.org`, see [PLAN.md §4](../PLAN.md#4-architecture-decision)), point it at
the machine running the approval server. If the server runs on the **same machine** as
`BLHeliSuite32xl`, use `127.0.0.1`; if it's on another machine on your network, use that machine's
LAN IP instead everywhere below.

### Linux

Edit `/etc/hosts` (requires root):

```bash
echo "127.0.0.1  blheli.org" | sudo tee -a /etc/hosts
```

Remove that line (or comment it out with a leading `#`) to undo. No service restart needed — glibc
re-reads `/etc/hosts` on every lookup, no caching to worry about on most distros. If your system
runs `systemd-resolved` with its own cache and the change doesn't seem to take effect, flush it:
```bash
sudo resolvectl flush-caches
```

### macOS

Same file, same technique:
```bash
echo "127.0.0.1  blheli.org" | sudo tee -a /etc/hosts
sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder   # flush macOS's DNS cache
```

### Windows

Edit `C:\Windows\System32\drivers\etc\hosts` as Administrator (Notepad run as Administrator, or
from an elevated PowerShell):
```powershell
Add-Content -Path C:\Windows\System32\drivers\etc\hosts -Value "127.0.0.1  blheli.org"
ipconfig /flushdns
```

### If the app is on a different machine than the server

The hosts-file technique above only affects the machine whose hosts file you edit. If
`BLHeliSuite32xl` runs on a *different* computer than the approval server:
- Edit that computer's hosts file instead (same instructions, still pointing at the *server's* IP,
  not `127.0.0.1`), or
- Run a local DNS resolver (e.g. `dnsmasq` on a router or a Pi) that everyone on the network uses,
  and add the override there instead of editing every machine's hosts file individually.

### Redirecting the port too (required — the hosts-file change alone is not enough)

The hosts-file edit above only changes what IP address `blheli.org` resolves to — it does **not**
redirect the *port*. The real app connects to the implicit default HTTPS port (443), but `serve`
defaults to port 8443 (a normal, unprivileged port a non-root process can bind). Without a port
redirect, the hosts-file change silently does nothing: the app tries `127.0.0.1:443`, finds nothing
listening, and the approval server's log stays empty even though the hostname redirect looks
correct. **Confirmed necessary** — this exact silent-failure mode was hit and diagnosed live.

**Linux** (add a NAT redirect from 443 to `serve`'s port, requires root once):
```bash
sudo iptables -t nat -A OUTPUT -p tcp -d 127.0.0.1 --dport 443 -j REDIRECT --to-port 8443
```
Undo with `-D` instead of `-A` (same rule, otherwise identical) when you're done:
```bash
sudo iptables -t nat -D OUTPUT -p tcp -d 127.0.0.1 --dport 443 -j REDIRECT --to-port 8443
```
This rule only affects traffic to `127.0.0.1` — safe to leave in place across reboots’ worth of
testing sessions if you don't want to redo it each time (it does not persist across a reboot by
default on most distros; re-run it after rebooting, or use your distro's iptables-persistent
mechanism if you want it to survive one).

Alternatively, skip the redirect entirely by running `serve --port 443` directly — but that
requires root/`CAP_NET_BIND_SERVICE` to bind a port below 1024, which is more invasive than the
NAT-redirect approach above; not recommended unless you have a specific reason to prefer it.

### Trusting the certificate (all OSes)

For the real app to accept an HTTPS connection to the redirected hostname, its OS generally needs
to trust the certificate's issuing CA (unless the app ships its own separate trust store, which is
unconfirmed — see step 2's open question).

**Linux** (Debian/Ubuntu):
```bash
sudo cp ~/.blheli32proxy/approval.crt /usr/local/share/ca-certificates/blheli32proxy.crt
sudo update-ca-certificates
```
**Linux** (Fedora/RHEL):
```bash
sudo cp ~/.blheli32proxy/approval.crt /etc/pki/ca-trust/source/anchors/
sudo update-ca-trust
```
**macOS**:
```bash
sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain ~/.blheli32proxy/approval.crt
```
**Windows** (elevated PowerShell):
```powershell
Import-Certificate -FilePath "$env:USERPROFILE\.blheli32proxy\approval.crt" -CertStoreLocation Cert:\LocalMachine\Root
```

## 5. Running the server automatically (optional)

**Linux (systemd user service)**, `~/.config/systemd/user/blheli32proxy.service`:
```ini
[Unit]
Description=BLHeli32Proxy approval server

[Service]
ExecStart=%h/path/to/BLHeli32Proxy/.venv/bin/blheli32proxy serve --cert %h/.blheli32proxy/approval.crt --key %h/.blheli32proxy/approval.key --policy allow-all
Restart=on-failure

[Install]
WantedBy=default.target
```
Then:
```bash
systemctl --user daemon-reload
systemctl --user enable --now blheli32proxy
```

**macOS**: an equivalent `launchd` plist under `~/Library/LaunchAgents/`, `RunAtLoad`+`KeepAlive`
keys pointing at the same `blheli32proxy serve` command.

**Windows**: Task Scheduler, "run at log on," action = the venv's `blheli32proxy.exe serve ...`.

## 6a. Listing archived test firmware

```bash
blheli32proxy list-test-firmware
```

Prints every `*.Hex` filename in your archive (default: `$BLHELI32PROXY_ARCHIVE_DIR` itself, if
that env var is set), one per line — read-only, doesn't touch or modify
anything there. Use this to find the exact filename of the test firmware you want to flash, then
flash it *through the real `BLHeliSuite32xl` app* ([§6](#6-diagnostics-experimental-needs-real-hardware) below explains why this project never
flashes anything itself). Point it at a different directory with `--dir`:

```bash
blheli32proxy list-test-firmware --dir /path/to/other/firmware/dir
```

## 6. Diagnostics (experimental, needs real hardware)

`blheli32proxy dump-config --port /dev/ttyACM0` (or `COM3` on Windows) reads+decrypts every ESC's
256-byte Setup/config block, independent of `BLHeliSuite32xl` — through an FC's 4-way-if
passthrough by default (add `--direct` for a standalone ESC on a dedicated adapter, `--motor-index
N` for just one channel). This is read-only diagnostic tooling, **not** part of the normal
flash/activation workflow (see [PLAN.md §4](../PLAN.md#4-architecture-decision)). The cipher and
45 of 46 known field names are verified against real hardware (exact match to official `.ixi`
backups across 3 independent MCU vendors and multiple firmware revisions — see [Hardware
Findings](knowledge/hardware-findings.md)); the one remaining field (`Eep_ESC_Mode`) is a
genuinely exhausted gap, not guessed.
Pass `--raw-dir dumps` to also save a byte-exact backup of each ESC's Setup block — do this
routinely, not just before a risky experiment (see `dumps/README.md`).

**To actually flash an ESC, use the real `BLHeliSuite32xl` app, not this tool** — this project
never implements firmware flashing itself (see [PLAN.md §4](../PLAN.md#4-architecture-decision) and `IMPLEMENTATION.md`'s "Known gap"
section for why). This project's only job during a real flash is running in the background,
answering the app's activation call ([§3](#3-run-the-approval-server)-[§4](#4-redirect-the-activation-hostname-to-this-server-os-level)).

## 6b. Extracting a firmware backup (experimental, read-only)

`probe-flash` and `dump-info-page` read an arbitrary flash address on a connected ESC — separate from
`dump-config` above, which only reads the small config block. This is **read-only**: it cannot
corrupt or brick the ESC the way a bad *write* could, and `dump-info-page` refuses to write its output
anywhere under `$BLHELI32PROXY_ARCHIVE_DIR` (your archived BLHeli material), when that env var is
set, regardless of what path you give it. If the env var isn't set, this check is skipped with a
warning — verify `--out` yourself in that case.

**What isn't guaranteed**: whether this actually returns the real firmware. The "how many bytes"
encoding for anything beyond the two protocol-confirmed sizes (16/256 bytes) is this project's own
extrapolation, not confirmed by captured traffic — and it's common (arguably expected, for a
paid-activation firmware) for an ESC's bootloader to flat-out refuse reads outside a small
whitelist of addresses, specifically to prevent firmware extraction/cloning. Getting garbage or a
refusal back is a legitimate result, not a sign something is broken.

**Always probe before dumping**, at address `0x0000` (where a real ARM Cortex-M image starts with
a vector table — an initial stack pointer, then a reset vector):

```bash
blheli32proxy probe-flash --port /dev/ttyACM0 --address 0x0000 --length 16
```

The command prints whether the first 8 bytes look like a plausible vector table (stack pointer in
SRAM range, odd reset-vector address). If that looks right, dump a full range to a new file (pick
`--end` based on this ESC's actual app-flash size if you know it — the AK32 you're testing with
uses an STM32 F0, so check its datasheet/BLHeliSuite32xl's own "FLASH size for app" reporting
rather than assuming a value):

```bash
blheli32proxy dump-info-page --port /dev/ttyACM0 --start 0x0000 --end 0x6000 \
    --out dumps/ak32-32.7-backup.bin
```

`dumps/` (project root, see `dumps/README.md`) is the right place for this — this project's own
extractions from your own hardware are fine to commit and publish (see `AGENTS.md`'s Publishing
Gate), unlike vendor-released binaries. **This is also the recommended first step before any riskier
experiment** (a new firmware flash, an activation attempt, or the AM32-flashing backlog item in
`PLAN.md` §7) — have a known-good backup of the currently-flashed firmware before changing anything.

If the probe instead returns something that doesn't look like real code (all `0xFF`, all `0x00`,
or a refused/CRC-failed read), record that in `PLAN.md` — it answers the "can firmware even be
extracted" question either way, which matters for this project regardless of the answer.

**Update, confirmed 2026-09-06**: `cmd_DeviceRead` (what `probe-flash`/`dump-info-page` use) is refused
at every real application-code address tested (RDP) — it only works from `0x7C00` onward (the info
page: Setup block, activation status, device info). For application code below that, use
`dump-firmware` instead (next section), which works around this via a different command.

## 6c. Extracting application-code firmware via the Verify oracle (experimental, read-only)

`cmd_DeviceRead` is RDP-blocked below `0x7C00`, but `cmd_DeviceVerify` isn't — it never transmits
real flash content back over the wire, only a match/mismatch signal, and RDP doesn't block that
internal comparison the way it blocks a raw read (see
[Hardware Findings](knowledge/hardware-findings.md#the-verify-oracle-exploration)). `dump-firmware`
uses this: it compares real flash against one or more candidate `.Hex` files you already have (e.g.
from `BLHeli32_HexFiles/` or your `$BLHELI32PROXY_ARCHIVE_DIR`), bisecting down to whatever sub-range each candidate
actually confirms rather than treating a fixed chunk as all-or-nothing — a candidate that only
partially covers a range still confirms the part it does cover.

```bash
blheli32proxy dump-firmware --port /dev/ttyACM0 --motor-index 0 \
    --candidate BLHeli32_HexFiles/Furling32_Multi_32_95.Hex
```

Pass `--candidate` multiple times to try several files in order (first real match per chunk wins)
— useful when one candidate has gaps, or when comparing across firmware eras (e.g. 32.7.x's static
PWM vs 32.8.x+'s dynamic PWM — pass candidates from each era separately to see what actually
differs). **Never fabricates a value for a range no candidate can confirm** — unconfirmed ranges
are written as `0xFF` in the padded `.bin` output and omitted entirely from the sparse `.hex` twin
(both written automatically alongside each other), same "leave undecoded rather than guess" rule as
`protocol/setup_fields.py`. `--out` defaults to a name derived from the candidate's own filename,
matching this project's `.ixi` naming convention.

**`--start`/`--end` default to whatever the candidate(s) actually cover** — the safe boundary is
derived from the candidate files themselves (a firmware-update file never includes the bootloader,
for any chip on any model), not a fixed address. This is what makes the command work across every
BLHeli32 model without per-model configuration. Past the candidates' own upper range (the info
page), use `dump-info-page` instead, which already works there via direct reads.

## 7a. Capturing raw traffic with tcpdump (no redirect needed — do this first)

This is how the real `blheli.org` hostname was originally found ([PLAN.md §4](../PLAN.md#4-architecture-decision)), and it works
**without** any redirect or cert-trust setup in place — useful as a first look, or as a
cross-check if the redirect+server approach ([§7b](#7b-capturing-the-exact-request-via-this-projects-own-server-do-this-after-redirecting)) isn't producing results. It reveals the
hostname and TLS certificate details in plaintext (DNS queries and the TLS ClientHello/certificate
are never encrypted), but not the HTTP request path/body, which stay inside the encrypted
connection — for that, use [§7b](#7b-capturing-the-exact-request-via-this-projects-own-server-do-this-after-redirecting) instead.

1. Start a capture (needs root; this captures on all interfaces, DNS and HTTPS traffic only):
   ```bash
   sudo tcpdump -i any -n -s 0 'tcp port 443 or udp port 53' -w /tmp/blheli-capture.pcap
   ```
   (Windows: use [Wireshark](https://www.wireshark.org/) directly instead of `tcpdump` — same
   filter, `tcp port 443 or udp port 53`, "Capture > Start.")
2. Leave it running, then use `BLHeliSuite32xl` normally — try the action you want to observe
   (e.g. connecting/activating a real ESC). **Do this with any `/etc/hosts` redirect for
   `blheli.org` removed/commented out first**, so you see where the app *actually* tries to go,
   not where you've pointed it.
3. Stop the capture (Ctrl+C in the terminal running `tcpdump`, or Wireshark's stop button).
4. Read back the DNS queries (look for anything other than your own unrelated traffic):
   ```bash
   tcpdump -r /tmp/blheli-capture.pcap -n udp port 53
   ```
5. Read back the TLS handshake's plaintext fields (SNI hostname, certificate CN/SAN) for whatever
   IP the DNS query resolved to:
   ```bash
   tcpdump -r /tmp/blheli-capture.pcap -A -n 'host <IP_FROM_STEP_4> and tcp port 443' | less
   ```
   The hostname appears as plain readable text near the start of the capture (the ClientHello's
   SNI extension) and again in the server's certificate (`grep` for `.org`, `.com`, `.net` etc. if
   `less`ing through it by hand is tedious). If you have `tshark`/Wireshark available, this is
   easier via a display filter: `tls.handshake.type==1` (ClientHello) or
   `tls.handshake.certificate` for the cert.
6. If the resulting hostname is **not** `blheli.org`, update [PLAN.md §4](../PLAN.md#4-architecture-decision) and every "blheli.org"
   reference in this document ([§2](#2-generate-a-tls-certificate-needed-if-the-real-activation-call-is-https-which-is-likely), [§4](#4-redirect-the-activation-hostname-to-this-server-os-level)) to the real one before continuing.

**Important limit of this method**: `tcpdump`/Wireshark alone can only ever show the hostname
(via the TLS ClientHello's SNI, sent in plaintext before encryption starts) and the server's
certificate — never the HTTP request path, method, or body, which are inside the encrypted TLS
payload. This is by design (that's what HTTPS is for), not a tooling limitation. To see the actual
request, use one of the two methods below.

### Decrypting the capture with SSLKEYLOGFILE (try this before §7b — no redirect/cert-trust needed)

If `BLHeliSuite32xl`'s TLS stack is (or is layered on) OpenSSL — plausible here since it uses the
Indy networking library, which normally binds to OpenSSL for TLS — it may honor the standard
`SSLKEYLOGFILE` environment variable, which makes it write out the session decryption keys as it
connects. Combined with a capture from step 1 above, this lets Wireshark/`tshark` decrypt the
traffic and show the real HTTP request, full path included. This is unproven for this specific
app — cheap to try, and needs no redirect or certificate trust setup at all.

1. Install `tshark`/Wireshark if you don't have it (`sudo apt install tshark` on Debian/Ubuntu; on
   Windows/macOS, install [Wireshark](https://www.wireshark.org/) directly).
2. Start the capture as in step 1 above.
3. Launch the app with the environment variable set, instead of normally. Find your own copy's
   real executable first (`find` search, or wherever you installed/extracted it) — its name and
   folder differ by OS: **Linux** binary is named `BLHeliSuite32xl`, **Windows** is
   `BLHeliSuite32.exe`, **macOS** is the `BLHeliSuite32xm.app` bundle. There's no fixed folder
   convention this project enforces — substitute your own real path below:
   ```bash
   # Linux
   SSLKEYLOGFILE=/tmp/blheli-keylog.txt /path/to/your/BLHeliSuite32xl

   # Windows (PowerShell)
   $env:SSLKEYLOGFILE = "C:\temp\blheli-keylog.txt"; & "C:\path\to\your\BLHeliSuite32.exe"

   # macOS — run the binary inside the app bundle directly, not `open -a`,
   # so the env var actually reaches the process
   SSLKEYLOGFILE=/tmp/blheli-keylog.txt /path/to/your/BLHeliSuite32xm.app/Contents/MacOS/BLHeliSuite32xm
   ```
4. Trigger the action you want to see, then stop the capture.
5. If `/tmp/blheli-keylog.txt` was created and has content, decrypt and read the request:
   ```bash
   tshark -r /tmp/blheli-capture.pcap -o "tls.keylog_file:/tmp/blheli-keylog.txt" \
       -Y "http" -T fields -e http.request.full_uri -e http.request.method
   ```
   (or open the pcap in Wireshark's GUI, set the keylog file under Preferences → Protocols → TLS,
   then filter on `http`.)
6. If the keylog file is empty or never created, this app doesn't honor `SSLKEYLOGFILE` — fall
   back to [§7b](#7b-capturing-the-exact-request-via-this-projects-own-server-do-this-after-redirecting) instead, which works regardless of the app's TLS library, as long as it accepts
   this project's certificate ([§4](#4-redirect-the-activation-hostname-to-this-server-os-level)'s still-open question).

## 7b. Capturing the exact request via this project's own server (do this after redirecting)

The exact request/response schema this server answers with (`approval/codec.py`) is still a
placeholder for anything beyond what's been captured so far. You don't need a connected ESC to
capture more of it — any app action that triggers a network call can be captured this way:

1. Redirect `blheli.org` (or whatever [§7a](#7a-capturing-raw-traffic-with-tcpdump-no-redirect-needed-do-this-first) found) to `127.0.0.1` ([§4](#4-redirect-the-activation-hostname-to-this-server-os-level)) and trust this project's cert
   ([§4](#4-redirect-the-activation-hostname-to-this-server-os-level)'s trust step).
2. Run `blheli32proxy serve --cert ... --key ... --policy allow-all --verbose`.
3. Run `BLHeliSuite32xl` and trigger the action you want to capture (e.g. "check for updates"
   again, or anything under a Manufacturer/Activation menu that doesn't need a connected ESC — or
   a real ESC activation attempt, once you have hardware).
4. Watch the server's log output: it prints the exact method, path, headers, and raw body of
   every request it receives, and the response it sent back.
5. If the app accepts the response and proceeds normally, the placeholder schema happened to be
   close enough for that action — otherwise, compare the logged request against what
   `approval/codec.py` currently expects/returns and adjust it to match (see that file's
   docstring — it's deliberately isolated so this is the only file that needs to change).

If the app instead shows a TLS/certificate error at this point, see [Troubleshooting](#troubleshooting) below — that's
a separate, more fundamental problem (cert trust/pinning) from the wire-format question.

## 7c. Capturing raw USB traffic with usbmon (needs real flight-controller hardware)

This is a **different, separate capture domain from §7a/§7b above** — it captures USB-serial
traffic between your computer and a flight controller (the `--motor-index` / FC-passthrough path
this tool and `BLHeliSuite32xl`'s "Betaflight/Cleanflight" bootloader option both use), not network
traffic. **It will never show the activation/licensing HTTPS call** — that only ever crosses the
network, not the USB link. Use this to inspect or debug the 4-way-if bootloader protocol itself
(see [Protocol Reference](../docs/knowledge/protocol-reference.md)), not to hunt for the activation
endpoint.

Linux only (`usbmon` is a Linux kernel facility) — no Windows/macOS equivalent is documented here;
Wireshark's own USB capture support (Windows: USBPcap; macOS: not natively supported) may work
similarly but hasn't been verified by this project.

1. Find which USB bus the flight controller is on:
   ```bash
   lsusb | grep -i "STM\|0483"
   ```
   Note the bus number (e.g. `Bus 003 Device 083: ID 0483:5740 STMicroelectronics Virtual COM
   Port` → bus `003`).
2. Load the `usbmon` kernel module and confirm the matching device node appeared (substitute your
   own bus number for `3`):
   ```bash
   sudo modprobe usbmon
   ls -la /dev/usbmon3
   ```
3. Start the capture, chaining the ownership fix into the same command so the file is yours to
   read once you're done (don't split this into two separate steps — a stale/mismatched `chown`
   target is an easy mistake otherwise):
   ```bash
   sudo tshark -i usbmon3 -w /tmp/blheli-usb-capture.pcapng ; sudo chown $USER:$USER /tmp/blheli-usb-capture.pcapng
   ```
4. Trigger the action you want to observe, in either of two ways:
   - **Most reliable**: if your FC runs Betaflight/EmuFlight, its own CLI has a direct command for
     this — `escprog <mode [sk/bl/ki/cc]> <index>` (e.g. `escprog bl 0` enters the bootloader for
     motor 0) — this calls the exact same passthrough entry point the real app uses, without
     needing to navigate any GUI.
   - Or just run `BLHeliSuite32xl` for real (option matching your FC's firmware, e.g. "BLHeli32
     Bootloader (Betaflight/Cleanflight)"), connect, and read the ESC(s).
5. Stop the capture (Ctrl+C in the capture terminal).
6. Read it back — filter on the USB device address from step 1, or just open it in Wireshark:
   ```bash
   tshark -r /tmp/blheli-usb-capture.pcapng
   ```
   **Each captured frame has a ~64-byte `usbmon` header before the actual USB payload bytes** —
   strip that off before interpreting anything as protocol data (Wireshark's own USB dissector
   does this for you automatically; a raw hex-dump export won't).

## Troubleshooting

- **App still shows "Host not found"**: the hosts-file entry didn't take effect — check for typos,
  flush the relevant DNS cache (see [§4](#4-redirect-the-activation-hostname-to-this-server-os-level)), and confirm it now resolves to your server's IP:
  ```bash
  ping blheli.org
  ```
- **App shows a TLS/certificate error instead**: the redirect worked, but the cert isn't trusted or
  doesn't match — recheck the Common Name in step 2 and the CA-trust step in step 4. If this
  persists after both are correct, it's evidence of certificate pinning (see step 2's open
  question) — a materially larger problem to solve, not a redirect/cert-trust misconfiguration.
- **Server logs show the request but the app doesn't accept the response**: the placeholder wire
  format (`approval/codec.py`) doesn't match what the real app expects — compare the logged request
  body against what the app actually sent (also visible in the log) and adjust `codec.py`'s decode
  logic; the response shape likely needs the same treatment.

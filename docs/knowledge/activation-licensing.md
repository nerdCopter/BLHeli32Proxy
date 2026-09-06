# Activation & Licensing

The actual purpose of this project: intercept BLHeli's dead activation server so the real,
unmodified BLHeliSuite32xl app believes it's authorized to flash, without needing BLHeli's own
(defunct) backend.

## Why this exists

- BLHeli (vendor) is dead: sanctioned mid-2024, servers offline, no further development. See
  `research/notes/BLHeli-END.en.md`.
- Licensing model was pre-paid license pools: a manufacturer buys N activations, each
  flashed/activated ESC consumes one. The shutdown stranded manufacturers holding unconsumed,
  already-paid-for activations.
- No obligation to honor BLHeli's original licensing terms for the dead vendor (explicit user
  instruction) — other manufacturers have already independently reverse-engineered and resell
  BLHeli32 commercially.

## The confirmed activation-subsystem shape

From `BLHeliSuite32Activator` (manufacturer-only tool), verified against the tool's own screenshots
in `research/notes/BLHeli-END.en.md`:

```
[after normal firmware flash, ~76s, unrelated to licensing]
REMOTE: ADDED UUID <per-chip UUID> for ESC <name>  [Key good for another <N>]  [<round-trip ms>]
LOCAL:  Added UUID to csv
Activated ESC successfully.
```

i.e.: (1) read a per-chip UUID from the just-flashed ESC, (2) POST `{ESC type, UUID}` to BLHeli's
server, which replies with success plus a decrementing per-manufacturer-license-key counter, and
(3) the tool also keeps its own local CSV ledger of every UUID it has activated, independent of the
server. **A replacement activation server should replicate this exact shape**: accept
`(ESC-type, UUID)`, return success + a remaining count, expect the client to keep its own local
record regardless of server response.

Other confirmed facts:
- **On-device enforcement is a protocol lockout, not a hard disable**: an ESC that fails activation
  still boots and runs, but is restricted to plain 1-2ms PWM input only — no DShot/Oneshot/
  Multishot/telemetry. Directly observable without decrypting anything.
- **Activation state is audible, zero software/risk needed** — confirmed from the official
  `BLHeli_32 manual ARM Rev32.x.pdf` (page 12, image not text — the beep patterns are graphics):
  a normally-activated ESC gives the standard single power-up beep; a **never-activated** ESC gives
  6 identical, flat, evenly-spaced low beeps instead; an **activation-failed** ESC gives an
  alternating two-tone (high/low/high/low...) pattern, clearly distinct from both other cases —
  and in that case the ESC accepts only 1-2ms PWM input (matches the protocol-lockout fact above).
  **Practical use**: whenever a real test-firmware flash attempt happens (Goal 4), listen to the
  ESC's power-up beep afterward — tells you immediately whether activation succeeded, failed, or
  never ran, with no network capture needed.
- The client validates TLS certificates for real (a server cert rotation broke old client versions
  until patched, per the changelog).

## Real hostname & confirmed endpoint (2026-09-03/04)

**Hostname: `blheli.org`** — found by capturing real traffic (`tcpdump` + DNS/TLS SNI), not static
analysis (no hostname string exists in the binary; loaded at runtime). The domain resolves to
`92.204.216.227`, presenting a valid GoDaddy/Starfield certificate, with an Apache server
answering on port 443 — not a DNS-failure "dead server" state. **Verified directly with `curl`**:
the root path `/` serves only a static, 59-byte, empty HTML shell unchanged since 2021 — not the
"server down for maintenance" text the app displays, and not evidence of a live application
backend behind it. That maintenance message comes from the confirmed endpoint below specifically
(or may be the app's own generic fallback for an unrecognized response), not from anything served
at the bare root path. Further path-guessing against this real, third-party server was
deliberately not attempted beyond confirming what the real app itself contacts — see "Scope note"
below.

**One endpoint fully confirmed** via `tshark` + `SSLKEYLOGFILE` decryption (the connection is
HTTP/2, not HTTP/1.1 — filtering on plain `http` finds nothing):

```
GET/HEAD https://blheli.org/BLHeli32_2017_1/status.php?p=BLHeliSuite32xl&v=1044
```

Response (every observed case, status 200, `text/html`, not JSON):
```
SERVER>text=Server is down for maintenance. Please try again later. Thank you for your patience.;
```

This endpoint is a version/maintenance-notice ping, hit by both "check for updates" and simply
opening the Flash tab — **not** per-ESC activation. It's implemented in `approval/codec.py` /
`approval/server.py`, tested in `tests/test_codec.py` / `tests/test_approval_server.py`.

**Confirmed live, end-to-end (2026-09-05)**: full redirect chain (`/etc/hosts`, CA-trusted
self-signed cert, `iptables -t nat -A OUTPUT -p tcp -d 127.0.0.1 --dport 443 -j REDIRECT
--to-port 8443` — a hosts-file change alone does **not** redirect the port, this iptables rule is
required too) tested against the **real** `BLHeliSuite32xl` native Linux app, not just `curl`. The
real app successfully connected through the chain twice and hit this exact endpoint. New confirmed
detail: **User-Agent: `BLHeliSuite32 URI Client/1.0`** (not previously known). The app's TLS
validation trusts the OS certificate store — confirmed, not just "generally expected" — a
CA-trusted self-signed cert was accepted with no pinning failure.

The empty-200-body "no update needed" response is **no longer just a guess — confirmed
non-fatal**: the real app displayed it via a "Following Message received:" dialog with blank
message content (same message-box UI the real maintenance-text response uses, per the confirmed
`SERVER>text=...;` format above) and a "Time elapsed" readout, then returned to normal operation
(no crash, no retry loop). Still open: whether truly empty body is the *ideal* response or just a
tolerated one — the real `SERVER>text=...;` wrapper format might be expected even for a benign
message (e.g. `SERVER>text=;` with an empty text field) rather than a fully empty body; not yet
compared side-by-side.

**Still not captured**: the actual ESC-activation call (UUID + license-key exchange). Needs a real
flash+activate attempt through the real app against a connected ESC — not yet done. This is the
actual core deliverable this project exists for; everything else so far is supporting
infrastructure. **As of 2026-09-05 the app is sitting at the exact doorstep of this**: see
"Local firmware loading" section below — the Flash tab is fully populated and ready, "Flash
Selected ESC" is one click away. Deliberately not clicked yet — see the hard safety constraint in
PLAN.md.

## Local firmware loading via the real app — CONFIRMED not server-gated (2026-09-05)

**This resolves a real open question from this session**: the user hypothesized the real app's
logic doesn't allow loading local firmware until some server-side check passes ("the logic does
not allow loading local firmware before server checks"). **Confirmed false** — local firmware
loading works entirely independent of the approval server. Full sequence that proved it:

1. Set up the full redirect chain on the live-test machine (Ubuntu, this is a *different* machine
   than the original AK32/Betaflight testing — same hardware relocated, same `/dev/ttyACM0` FC):
   - `echo "127.0.0.1  blheli.org" | sudo tee -a /etc/hosts`
   - `sudo cp ~/.blheli32proxy/approval.crt /usr/local/share/ca-certificates/blheli32proxy.crt && sudo update-ca-certificates`
   - `sudo iptables -t nat -A OUTPUT -p tcp -d 127.0.0.1 --dport 443 -j REDIRECT --to-port 8443` —
     **this step is missing from `docs/USAGE.md`'s §4 redirect instructions** — a hosts-file
     change alone only changes what IP `blheli.org` resolves to; it does **not** redirect the
     port, and the real app connects to the implicit default HTTPS port 443, not `serve`'s default
     8443. Without this iptables rule, the redirect chain silently does nothing (confirmed: first
     attempt showed zero requests in the server log even though hosts/cert were both correctly set
     up). **`docs/USAGE.md` needs this iptables step added** — not yet done, tracked as an open
     item.
2. Ran `.venv/bin/blheli32proxy serve --host 0.0.0.0 --port 8443 --cert ~/.blheli32proxy/approval.crt --key ~/.blheli32proxy/approval.key --policy allow-all --verbose` in the background, logging to `/tmp/approval_server.log` (this exact log path/PID is ephemeral — gone once the process is killed or the machine reboots; nothing here persists past this session unless re-run).
3. Verified the full chain end-to-end with `curl -v --max-time 5 "https://blheli.org/BLHeli32_2017_1/status.php?p=BLHeliSuite32xl&v=1044"` **before** trusting the real app's behavior — confirmed TLS handshake succeeded, cert trusted, 200 response logged. This isolated "is our infrastructure broken" from "does the app behave as expected" — important because the very first live-app attempt showed **zero** requests in the log (see point 4).
4. **Root cause of that initial zero-requests result**: the real app almost certainly made its one startup status-check call before all three `sudo` setup steps were complete (a timing/ordering issue, not a broken chain) — confirmed once the user manually triggered "check for updates" from within the app's own menu afterward, which immediately appeared in the log (`GET /BLHeli32_2017_1/status.php?p=BLHeliSuite32xl&v=1044`, **User-Agent: `BLHeliSuite32 URI Client/1.0`** — new confirmed detail). The app displayed a "Following Message received:" dialog with blank content (matches the empty-body placeholder response) and a "Time elapsed: 41ms" readout, then continued normally — no crash, no retry loop. This is the same endpoint fires on: manual "check for updates", opening the Flash tab, clicking "Connect", clicking "Read" — confirmed by repeated identical log entries across all of these actions (13 total requests logged this session, every one hitting the exact same path).
5. **The firmware-version dropdown still did nothing after all of this** — ruling out the server call as the actual gate. Investigated the app's own directory
   (`$BLHELI32PROXY_ARCHIVE_DIR/BLHeliSuite32xl/` — this user's own Linux-build archive subfolder,
   named to match the Linux executable; not a path this project enforces) and found
   `BLHeli32_HexFiles/` — **the local
   firmware catalog folder the app reads from — was completely empty** (0 files). This is the same
   category of gap as the `hidapi.dll` sibling-file issue found with `TestActivator.exe` the day
   before (see below) — a missing local file, nothing to do with licensing.
6. **Fix**: copied the exact matching test-firmware file —
   `$BLHELI32PROXY_ARCHIVE_DIR/32.9.5_testcode/Aikon_AK32_4IN1_35A_6S_V1_0_Multi_32_95.Hex` — into
   `$BLHELI32PROXY_ARCHIVE_DIR/BLHeliSuite32xl/BLHeli32_HexFiles/`. **Confirmed working**: the
   ESC Flash tab now shows all 4 ESCs (`Aikon_AK32_4IN1_35A_6S_V1_0 Rev 32.7`) with the dropdown
   correctly populated: `32.9.5 (Test ver.) (ext. file)`, "Keep settings" checked, and both
   "Flash Selected ESC" and "Verify Selected ESC" buttons enabled. Screenshot confirms this exact
   state (BLHeliSuite32xl 1.0.4.4, ESC Flash tab).
7. **Interesting side observation, not yet explained**: clicking the Flash tab initially showed 8
   motor slots; after the status-check dialog + OK, it refreshed to the correct 4. Hypothesis
   (untested): the UI defaults to a generic max-motor display before a separate local FC query
   corrects it — likely unrelated to licensing/network, probably a local serial round-trip to the
   FC itself, not investigated further.
8. **User-recalled fact that motivated all of this**: when blheli.org's servers were live, the
   firmware-version dropdown was populated *online*, and IIRC also supported loading local files
   as a separate option. This session's local-file fix reproduces the "local file" path
   specifically — the online-catalog path (if it used a different, still-unidentified host) was
   never observed, since the real app never made any request other than the one confirmed
   `status.php` endpoint, from any UI action tried this session (connect, read, open Flash tab,
   manual update check). No second host has been found or ruled out — a broader
   `tcpdump -i any -n -s 0 'udp port 53 or tcp port 443'` capture during dropdown interaction was
   requested from the user but not yet completed (open item).

**"Flash Selected ESC" clicked, no write occurred (2026-09-06)**: with the approval server,
redirect, and cert trust all running, user clicked "Flash Selected ESC" on the AK32 (real firmware
v32.7) against the staged 32.9.5 test file. The saved `.xlg`
([BLHeliSuite32xl-Log-260906-flash-attempt01.xlg](BLHeliSuite32xl-Log-260906-flash-attempt01.xlg))
shows only `cmd_DeviceInitFlash` → `cmd_DeviceVerify` (erroring `armBLB:General Error` at `0x2400`,
same divergence point as the earlier confirmed Verify trace) → `cmd_DeviceReset` — **no
`cmd_DeviceWrite`/erase command appears anywhere in the log**. The ESC's firmware is confirmed
unchanged. **Confirmed by the user: this is not a version-mismatch gate** — BLHeli's bootloader
writes unconditionally regardless of source/target version, so a Verify mismatch does not by itself
block a write; the earlier write-up in this file drew that conclusion and was wrong.

The approval server's own log shows only the same 3 `status.php` empty-body pings during this
attempt — no new or different HTTP request arrived at all. Since nothing changed on the ESC and no
new request reached this project's server, the most likely explanation is the still-open item from
[Hardware Findings](hardware-findings.md#test-hardware-quirks--read-these-before-re-testing): **a
second, undiscovered host** the app may contact specifically to gate the flash/write action, which
the current `/etc/hosts` redirect (`blheli.org` only) would not catch — such traffic would go out
to the real (dead) host, get no reply, and could plausibly cause the app to silently decline to
write with no error dialog. Next step: re-check the `tcpdump` capture already running
(`/tmp/blheli-capture.pcap`) for **any** DNS query or TLS SNI other than `blheli.org` occurring
around the time of this Flash click — not yet done. **This is the single most important open item
for the next session**, and is what "developing the proxy" for Goal 4 actually depends on: finding
and answering that second endpoint, not the status-check ping this server already handles.

## BLHeliSuite32TestActivator — a second, more revealing binary (2026-09-04)

Found in the user's archive (`$BLHELI32PROXY_ARCHIVE_DIR`, inside
`SEQURE.BLHeliSuite32_..._configuration_tool.zip` → `BLHeliSuite32TestActivator_31.10.0.1.zip`),
alongside a similar `LEAK.flashlocal.BLHeliSuite32Test_31.10.0.1.zip` → `BLHeliSuite32Test.exe`.
Static `strings` analysis only so far (no execution yet) — see PLAN.md backlog for the in-progress
dynamic (Wine) attempt.

**This looks like a manufacturer/factory provisioning tool, not an end-user trial app** — despite
the "Test" naming. Confirmed strings:
- `Enter KEY code` / `Show KEY code` / `KEY Code is used up soon...` / `FrameManufKeyCodeExpires` —
  a purchased, consumable manufacturer license key, separate from per-ESC activation.
- `ManufPost_intf`, `actManufPostSerialNumbersExecute`, `FManufAutoCheckAndFlash` — an automated
  factory flash-and-register workflow, consistent with §"confirmed activation-subsystem shape"
  above (POST `{ESC-type, UUID}`, expect a remaining-count reply).
- `IsBannedFromFlashRevision` — a firmware-revision ban list.
- **`Eep_FlashCounter` / `Eep_FlashCounter_ID`** — a **new, previously-unknown ESC-side EEPROM
  field name**, not in `protocol/setup_fields.py`'s `CONFIRMED_FIELDS`. Worth hunting its offset
  the same way `Eep_Pgm_Direction` was found (see `setup-block-fields.md`'s Method section) —
  likely the mechanism behind the "100 boot/flash limit" the user recalled from a MadsTech/MadRC
  video (unconfirmed — see below).
- `TActivationStatus` enum: `ActivationOK`, `ActivationFAILED`, `ActivationNONE`,
  `ActivationREAD_FAILED`, `ActivationUNKNOWN`, `ActivationUNREAD` — gives semantic meaning to the
  activation-status byte this project already confirmed readable at address `0xEB00` (see
  [Hardware Findings](hardware-findings.md)), previously just "a byte we can read," now known to be
  one of these 6 named states.
- No plain-text hostname/URL found (same as the real app — likely assembled at runtime, needs live
  capture, not static analysis, to find).

**MadsTech/MadRC video claim — checked, NOT confirmed**: the user recalled a video by this channel
saying a "100 boot limit" on test firmware "did not trigger." Web search found the channel is real
and has two relevant videos (*"Blheli32 ESC PSA - Manufactures Shipping Non Licensed Firmware?"*
and *"DJI O3 & Goggles 3 Is Here - Blheli32 Test Version Scam..."*, 2024-07-28), but both appear to
cover manufacturers (DarwinFPV, SEQURE, Foxeer named in search results) shipping ESCs pre-flashed
with unlicensed/unreleased test firmware — a supply-chain/licensing story, not a boot-counter
bypass. No source found mentions a "100 boot" limit or `TestActivator` specifically. Transcripts
weren't fetchable (YouTube blocks it) — the exact claim in the videos is unverified, not
disproven. Treat as unconfirmed until watched directly.

**Official manual/changelog PDFs examined** (`Manuals/BLHeliSuite32TestHistory.pdf`,
`Manuals/BLHeli_32 manual ARM Rev32.x.pdf`, extracted from the `31.9.0.3` zip below) — no explicit
"100 boot limit" or `Eep_FlashCounter` mention found in either. Did find 3 relevant changelog
entries: "Added parameter 'Options... Connect ESC Retries...' to improve reliable bootloader
connection" — independent confirmation from the vendor's own changelog that the real app needed a
user-configurable retry count for the same connect flakiness this project root-caused (see
[Hardware Findings](hardware-findings.md)); "Improved automatic reflash handling for ESCs where
prior the activation failed"; and "Added indication of ESC activation state" — confirms
activation-state display is a real, used feature, consistent with the `TActivationStatus` enum
found in strings.

**Dynamic (Wine) analysis — completed, dead end for the network-capture goal, but several real
gotchas confirmed** for anyone running this Windows tool under Wine on Linux (a Wine 11.x AppImage
build was used; any similar Wine 11.x install should behave the same):

- **First attempt got no further than Wine's own first-run Mono/Gecko bootstrap**
  (`control.exe appwiz.cpl install_mono`) — this must finish completely, outside any time-boxed
  session, before the target app will even launch. Two connections observed at that stage
  (`172.67.69.38:80`, `151.101.2.217:80`, Cloudflare/Fastly ranges) were Wine's own Mono installer
  fetching redistributables, not the target app — confirmed via `ps aux` showing
  `control.exe`/`rundll32 setupapi` as the connection owner, a real false-positive risk to watch
  for when monitoring an app's traffic under Wine generally.
- **`wine: could not load kernel32.dll, status c0000135`** on a later attempt — root cause was a
  **corrupted `WINEPREFIX` from the earlier interrupted run**, not a missing 32-bit/WoW64
  component (the AppImage bundles full i386-windows support, 821 files, verified via
  `--appimage-mount`, `kernel32.dll` included). `WINEARCH=win32` is the wrong fix and actively
  fails (`"WINEARCH is set to 'win32' but this is not supported in wow64 mode"` — this Wine build
  uses the newer single-64-bit-prefix WoW64 architecture; there's no separate win32 prefix to
  select). **Fix**: a genuinely fresh `WINEPREFIX` (`wineboot --init` cleanly, never reused from an
  interrupted session) resolved it completely.
- **`File hidapi.dll does not exist`** dialog on next launch — caused by extracting only the `.exe`
  itself from its zip, not its sibling files. **Fix**: extract the full zip (`hidapi.dll` and other
  sibling DLLs/folders are required alongside the `.exe`, in the same directory).
- **Tiny, unreadable UI text** — fixed via Wine's DPI registry key:
  `wine reg add "HKEY_CURRENT_USER\Control Panel\Desktop" /v LogPixels /t REG_DWORD /d 192 /f`
  (192 = 200%/double scale; 288 = 300%/triple).
- **Serial connect to a real ESC from inside the app never worked, even after all of the above**:
  `WINEPREFIX/dosdevices/com3` → the real serial device symlink is reset by Wine's own serial
  auto-detection on its next boot cycle — it must be recreated immediately before each launch, not
  just once. Even with the mapping held correct, connect still failed:
  `WINEDEBUG=+comm` trace showed the full IOCTL sequence dispatching cleanly
  (`SET_BAUD_RATE`/`SET_LINE_CONTROL`/`SET_TIMEOUTS`/etc., zero `err:` lines across 463 trace
  lines), but the app's own higher-level logic then reported `"System Error. Code 6, Invalid
  handle"` — most likely Wine's overlapped/async serial I/O emulation (`WaitCommEvent` and
  similar), a known weak area in Wine generally, not a configuration mistake. This project's own
  tool connects to the exact same port/hardware instantly (proven working during the same
  debugging session) — the hardware and port are fine; this is purely a Wine-serial-emulation gap
  specific to running this particular Windows app under Wine.
- **Conclusion**: not pursued further after this — no clear next fix identified for the serial
  issue, and testing directly against the real native-Linux `BLHeliSuite32xl` app (see "Local
  firmware loading" above) fully superseded this as the actual path to Goal 4.

**A newer copy of this tool family was retrieved and verified from the official distribution
channel** (`sequremall.com/pages/blhelisuite32`) — its current download bundle contains 3 files;
2 are byte-identical (SHA-256 verified) to what was already archived, and the 3rd —
`BLHeliSuite32TestActivator_31.9.0.3.zip` (an older build, dated 2023-07-06 inside the zip) — was
new and was saved for reference. This is the build used for all the Wine work above (confirmed
32-bit PE32/i386 via the `file` command, same architecture as the originally-analyzed build).

## TLS trust — resolved, confirmed

The real app validates certificates for real — redirecting `blheli.org` to this project's server
is necessary but not sufficient; the app also needs to *trust* whatever certificate this server
presents. **Confirmed live against the real app** (see "Local firmware loading" above): it trusts
the OS certificate store — a CA-trusted self-signed cert was accepted with no pinning failure. No
binary patching needed.

## Scope note

Further probing of `blheli.org`'s other paths (path guessing/enumeration against a third party's
live server) was deliberately not done beyond confirming what the real app itself contacts — that
crosses from "confirming what the app calls" into active reconnaissance of someone else's
production server, which is the user's call to make, not a default action.

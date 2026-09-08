# BLHeli32Proxy — Plan

Status: **implementation in progress, real hardware confirmed working across 4 different ESC
families and 4 different BLHeli_32 firmware revisions.** See [`docs/knowledge/INDEX.md`](docs/knowledge/INDEX.md) for the
technical reference material this plan links to, `IMPLEMENTATION.md` for module-level build status,
and `research/README.en.md` / `research/README.zh.md` for the original research index.

---

## 1. Goal

Design and build a MITM/proxy/server that intercepts BLHeli32 ESC firmware flashing and
configuration, applying **our own** licensing/authorization scheme in place of BLHeli's now-defunct
cloud activation system — for installing test-firmware binaries onto owned hardware. The user keeps
using the real, unmodified `BLHeliSuite32xl` app for all ESC communication (flashing, config); this
project's server answers exactly the one HTTP(S) call that app makes to BLHeli's dead activation
server. See [Activation & Licensing](docs/knowledge/activation-licensing.md)
for the full architecture rationale and confirmed findings.

### Context

- BLHeli (vendor) is dead: sanctioned mid-2024, servers offline, no further development. See
  `research/notes/BLHeli-END.en.md`.
- No obligation to honor BLHeli's original licensing terms for a defunct vendor — other
  manufacturers have already independently reverse-engineered and resell BLHeli32 commercially.
- Test-firmware `.Hex` files are BLHeli's own copyrighted vendor binaries — this project never
  bundles them. See `docs/USAGE.md` §1b for how to fetch them yourself from BLHeli's official
  GitHub history, and `AGENTS.md`'s Publishing Gate for the rule governing this material.

---

## 2. Source material inventory

Primary research lives under `research/` in this project:

- `research/notes/*.en.md` — English technical notes, the actual reference material (not the
  `.zh.md` files or the live site). See `research/README.en.md` for the full index by subject.
- `research/images/<post-name>/NN.png` — every embedded diagram/screenshot, downloaded locally.
- `research/manuals/*.txt` — official BLHeli_32 manual and changelog, extracted from the vendor
  PDFs.

**Local software you need of your own** (never bundled here — see `docs/USAGE.md` §1a/§1b):
- The official `BLHeliSuite32xl` app (native Linux configurator) — your own copy, from BLHeli's
  official distribution channels. Point `$BLHELI32PROXY_APP_DIR` at it.
- Test-firmware `.Hex` files — populate its `BLHeli32_HexFiles/` subfolder (or a separate
  `$BLHELI32PROXY_ARCHIVE_DIR`) using `docs/USAGE.md` §1b's instructions.

---

## 3. Goals & status

See [Goals & Status](docs/knowledge/goals-status.md) for the full breakdown with a status diagram.
Summary:

| # | Goal | Status |
|---|---|---|
| 1 | Backups (config/Setup-block data) | Mostly complete |
| 2 | Firmware dumps (executable code) | Reopened 2026-09-08 — RDP still blocks direct reads, but the Verify-oracle brute-force path is now measured feasible (~2-4 days/board) and being pursued |
| 3 | Bootloader unlock (AM32, no soldering) | Closed — confirmed impossible as scoped |
| 4 | Proxy/licensing intercept (original goal) | In progress — fully staged, one decision from capturing the real activation call |

---

## 4. Architecture decision

**Pure MITM against the real, unmodified `BLHeliSuite32xl` app.** The user keeps running the
official app exactly as normal for everything ESC-facing; this project's server sits where BLHeli's
dead activation server used to be (via an OS-level hostname *and port* redirect — see
`docs/USAGE.md` §4) and answers the real licensing/activation HTTP(S) call. No from-scratch
wire-protocol client is needed for flashing — `protocol/`/`cipher/` are read-only diagnostic
tooling (backups, inspection), not the flashing path.

**Confirmed live, end-to-end, against the real app** (not just `curl`): the redirect chain works,
the app's status-check call (`GET /BLHeli32_2017_1/status.php?p=BLHeliSuite32xl&v=1044`, User-Agent
`BLHeliSuite32 URI Client/1.0`) is answered correctly, and the app trusts a CA-trusted self-signed
certificate with no pinning issue. See [Activation & Licensing](docs/knowledge/activation-licensing.md)
for the exact confirmed request/response and [Protocol Reference](docs/knowledge/protocol-reference.md)
for the confirmed wire protocols (both FC-passthrough and direct-adapter).

**Local test-firmware loading in the real app is not gated by any server check** — it only needs
`BLHeliSuite32xl`'s own `BLHeli32_HexFiles/` folder populated with a `.Hex` file matching the
connected ESC's layout name. An empty match here also triggers a real crash in the app's own
Flash-tab UI (a null-pointer bug, confirmed reproducible across 3 unrelated ESC
families/bootloaders) — always populate a matching file first. Full detail:
[Hardware Findings](docs/knowledge/hardware-findings.md).

---

## 5. Implementation — language and structure

**Language: Python 3** (cross-platform by construction). See `IMPLEMENTATION.md` for module layout
and `docs/USAGE.md` for day-to-day operation and OS-level redirection steps.

- **Protocol/cipher modules** (`protocol/`, `cipher/`) — done, read-only diagnostic tooling, not
  the flashing path. `flash_firmware()` deliberately raises `NotImplementedError` — the write
  protocol was never captured and this project will never guess at it.
- **Real request capture** — hostname and the status-check endpoint confirmed; the ESC-activation
  request/response schema is still not captured (needs an actual flash+activate attempt — see
  `MENU.md` item 6).
- **Approval-to-flash server** — done and confirmed working end-to-end against the real app. Small
  local HTTP(S) service, swappable request/response schema so the real one can replace the
  placeholder once captured.
- **TLS handling** — cert/key generation tooling done (`gen-cert`); the real app trusts the OS
  certificate store, confirmed live.
- **CLI tool** — done (`serve`, `gen-cert`, `list-test-firmware`, `dump-config`, `probe-flash`,
  `dump-info-page`), including a partial-backup `.ixi`-style file writer (`dump-config --out`).
- **Documentation** — `docs/USAGE.md` (day-to-day operation), `docs/knowledge/` (technical
  reference), `MENU.md` (guided task list).

---

## 6. Risks / open questions carried forward

- Legal: building a tool that flashes vendor firmware while bypassing the vendor's own activation
  gate sits in a gray area even with a dead vendor — scope stays to owned hardware and legitimately
  obtained archived firmware, not redistribution. **Revisit this note specifically before making
  the repo public** — see §8 for the exposure-change context.
- The XTEA keys and field offsets are confirmed to drift between configurator builds and between
  firmware revisions (see [Setup Block Fields](docs/knowledge/setup-block-fields.md)'s
  cross-version findings) — a real implementation needs a detection strategy, not hardcoded
  constants.
- Bidirectional-DSHOT/telemetry research is background-only; nothing in the licensing/flashing path
  depends on it.
- The real activation request/response wire format is unknown — the approval server is built
  against a placeholder schema; expect revision once real traffic is captured.
- **Confirmed real risk (2026-09-07)**: `write_flash()` without erasing first can silently corrupt
  a much larger flash region than the bytes written, not just the targeted bytes — see
  [Hardware Findings](docs/knowledge/hardware-findings.md#write_flash-without-erase-first-corrupts-far-more-than-the-targeted-bytes-2026-09-07).
  Confirmed recoverable for the small Setup block (full-block-copy repair from a known-good sibling
  ESC), but application firmware has no equivalent backup path since RDP blocks firmware dumps —
  raises the real stakes of Goal 4's "Flash Selected ESC" step from theoretical to demonstrated.

---

## 7. Backlog

- **Goal 2 (firmware dumps) reopened via Verify-oracle brute force — feasibility measured, not yet
  attempted at scale (2026-09-08).** RDP still blocks direct `cmd_DeviceRead`, but `dump-firmware`'s
  `--discover-unresolved` flag (already built, `fw.discover_byte()`, up to 256 `cmd_DeviceVerify`
  guesses/byte, no write/erase risk) makes byte-by-byte recovery genuinely possible. Ran a real
  verify-diff against the damaged Reaper (32.10.0) using the closest available candidate (32.9.5,
  no exact-version file exists) — only 9.4% matched (2,240/23,808 bytes), leaving 21,568 unresolved
  bytes. Measured real per-call latency directly: **0.060s/call**, giving a real estimate of
  **~2-4 days of continuous round-trips** for the full unresolved region (worst case 92h, average
  case 46h) — a genuine multi-day undertaking, but not the multi-week-or-more result the first,
  confounded timing attempt suggested. See [Hardware
  Findings](docs/knowledge/hardware-findings.md#goal-2-brute-force-feasibility--discover-unresolved-real-numbers-2026-09-08)
  for the full account, including a real robustness gap found along the way: killing a process
  mid-4-way-if session (even via a safety `timeout` wrapper) sticks the FC's MSP passthrough state,
  recoverable only by physically replugging its USB cable — no software recovery path exists.
  **Not yet attempted at full scale**: the current CLI has no checkpoint/resume support, so a
  multi-day unattended run risks losing all progress (and needing a physical replug) on any
  interruption. A resumable design should exist before attempting the real run.

- **AM32 flashing without soldering — closed, confirmed not possible.** BLHeli_32 sets the STM32's
  Read-Out Protection (RDP) fuse; converting to AM32 always requires physically soldering SWD
  wires (or clip leads) and clearing RDP via a real debugger first — no software-only path exists.
  See [Hardware Findings](docs/knowledge/hardware-findings.md#firmware-dump-blocker-rdp) for the
  technical detail. A 3-piece ST-Link V2 clone debugger set is available as a last-effort tool if
  this is ever revisited, but clearing RDP always mass-erases the flash first — the same
  firmware-loss trade-off as Goal 2's blocker, plus the soldering step, plus a learning curve on
  the tool itself. Closed unless the firmware-loss trade-off and the soldering/tooling effort are
  both explicitly accepted.

- **Cross-version Setup-block field validation — 45 of 46 known field names confirmed
  (2026-09-08).** Real raw `dump-config --raw-dir` reads (not just `.ixi`-decoded values) now exist
  for 2 boards: AK32 (STM32F051x6, firmware 32.7, 38 known field names) and Furling32 (GD32F350x6,
  firmware 32.9.5, 45 known field names) — a different MCU vendor and major firmware line, 46 total
  unique names between them. **21 of 22 originally AK32-derived offsets matched exactly** on
  Furling32 too; only `Eep_Pgm_Pwm_Freq` differs, and that's explained (same byte/offset, renamed
  `Eep_Pgm_Pwm_Frequency_Lo` on 32.9+, with a genuinely new `_Hi` field elsewhere for the added
  variable-PWM feature) rather than the struct having shifted. **5 more fields fully confirmed via
  real differential tests** on the same Furling32 (a temporary, reversible Setup-block edit via the
  real app, not this project's own `write_flash()`): `Eep_Pgm_Curr_Prot`, `Eep_Pgm_Curr_Sense_Cal`,
  `Eep_Pgm_LED_Control` (this closed the last of the original 3-offset AK32 chase), `Eep_Pgm_SBUS_Channel`,
  `Eep_Pgm_SPORT_Physical_ID`. See [Setup Block Fields](docs/knowledge/setup-block-fields.md)'s
  "Cross-version validation" section for the full method and evidence, including two disproven
  guesses along the way (kept, not deleted, per this project's own knowledge-retention standard).
  **Done (2026-09-08)**: raw-byte read against a 3rd real board/MCU vendor — a second, damaged
  FOXEER Reaper unit (`AT32F421`, Artery Technology — neither ST's STM32 nor GigaDevice's GD32).
  All 27 confirmed fields decoded correctly, matching its real `.ixi` exactly wherever that file
  has a corresponding line. Same session, same board: `Eep_Pgm_Pwm_Frequency_Hi` (offset 34)
  confirmed via a real differential test (128→48 kHz). Then, via a new third confirmation method —
  cross-board value correlation across all 3 boards' raw plaintext + `.ixi` values, no new hardware
  needed — 12 more fields closed: `Eep_FW_Main_Revision`, `Eep_FW_Sub_Revision`,
  `Eep_Layout_Revision`, all 4 `Eep_Hw_LED_Capable_N`, `Eep_Hw_Voltage_Sense_Capable`,
  `Eep_Hw_Current_Sense_Capable`, `Eep_Hw_Pwm_Freq_Min/Max`, `Eep_SPORT_Capable`,
  `Eep_Nondamped_Capable`. See [Hardware Findings](docs/knowledge/hardware-findings.md)'s "A
  second, damaged unit of the same model" section and [Setup Block
  Fields](docs/knowledge/setup-block-fields.md#method--12-more-fields-via-cross-board-value-correlation-2026-09-08).
  **Then, same day, `Eep_ESC_Layout` and `Eep_Note_Array` closed too** — no new hardware needed,
  the lead came from re-reading this project's own research corpus
  (`research/notes/BLHeliSuite32-Reverse3.en.md`, a real disassembly of the vendor's binary),
  which documents fixed wire-format offsets for both fields. Cross-checked against raw plaintext
  already captured from all 3 boards: `Eep_ESC_Layout` (offset 64, 32 bytes) matched byte-exact in
  all 3 cases; `Eep_Note_Array` (offset 144, 48 bytes) required deriving the actual note encoding,
  verified against 2 real Furling32 melodies plus AK32's melody plus the Reaper's empty state, all
  byte-for-byte exact. See [Setup Block Fields](docs/knowledge/setup-block-fields.md#method--eep_esc_layout-and-eep_note_array-closed-via-this-projects-own-research-corpus-2026-09-08).
  **`Eep_Note_Array`'s encoding fully closed same day**: a real differential test on the damaged
  Reaper, using the exact script syntax documented in the vendor app's own Music Editor tooltip
  (`C42 P1 P2 P4 P8 P16 P32 P64 P128`), confirmed the previously-untested half-note duration and
  revealed pauses support 8 lengths (wider than notes' 4) via a pitch-code acting as a x16 scale
  bit. Nothing about this field remains inferred. **45 of 46 known field names confirmed — only
  `Eep_ESC_Mode` remains, and that gap is genuinely exhausted** (checked against every research
  note in this project's corpus, the vendor manual, and raw bytes on 3 boards — closing it further
  needs new binary disassembly work, out of scope for this project's method).
  **Follow-up, not yet started**: same raw-byte check against Furling32_4in1_C (32.9, GD32F350x6 —
  already a confirmed MCU/firmware combo via `.ixi` alone, but never via raw bytes) whenever that
  hardware is available again.

- **BLHeliSuite32TestActivator — dead end, not pursued further.** A manufacturer/factory
  provisioning tool (not an end-user trial app) found in BLHeli's own distribution — has a
  purchased-KEY-code licensing scheme, firmware-revision ban lists, and a previously-unknown
  `Eep_FlashCounter` EEPROM field name (undecoded). Runs under Wine, but serial connect to a real
  ESC from inside it fails due to a Wine serial-I/O-emulation limitation (not a hardware issue —
  this project's own tool connects to the same hardware instantly). Fully superseded by testing
  directly against the real native-Linux `BLHeliSuite32xl` app instead (§4 above). Full detail:
  [Activation & Licensing](docs/knowledge/activation-licensing.md).

- **The single most important open item: capture the real ESC-activation network call.** This is
  Goal 4's actual remaining deliverable. The real app is fully staged on multiple tested boards —
  test firmware selected, "Flash Selected ESC" one click away. That click is real, irreversible
  risk (could overwrite the board's current firmware, with no way to restore it — firmware dumps
  are blocked, §6). See `MENU.md` item 6 for the guided, safety-gated procedure (explicit
  confirmation required every time, screen recording recommended).

- Secondary/lower-priority open items: a broader network capture (DNS + all HTTPS, not just the
  redirected host) during Flash-tab interaction was never completed — would confirm whether a
  second, unidentified host is involved in any online firmware-catalog behavior from when
  `blheli.org` was still live (local-file loading is confirmed to work regardless, so this is not
  blocking). A user-recalled online claim about a firmware trial "boot limit" remains unconfirmed
  by any source found — treat as unverified, not disproven.

---

## 8. Publishing

This project's own code/docs/research can be published following the repository owner's normal
approval before any push, PR, or visibility change — no extra restriction beyond that.
**Vendor-released binaries are different and permanent**: see `AGENTS.md`'s Publishing Gate — any
vendor-distributed firmware in a user's own app/archive folder (test firmware fetched via
`scripts/fetch-testcode.sh`, or bundled with the vendor app) is never committed or published. Each
user fetches their own copy of the vendor's test firmware directly from BLHeli's official upstream
repository (`docs/USAGE.md` §1b) — this project never needs to redistribute it, so there is no
publish decision to make about it.

**`dumps/*.bin`/`*.hex` are NOT covered by that restriction** (whitelisted 2026-09-07) — they're
this project's own extractions from a user's own owned hardware (Setup-block backups, and any
application-firmware dump if one is ever achieved), not a copy of a vendor-distributed file. Same
category as the `.ixi`/`.xlg` files already published under `docs/knowledge/`. Fine to commit and
publish, same approval process as any other push.

A `LICENSE` file is still needed before any public release and has not been added yet.

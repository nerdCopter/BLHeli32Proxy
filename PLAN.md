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
| 2 | Firmware dumps (executable code) | Closed — blocked by hardware RDP protection |
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

- **AM32 flashing without soldering — closed, confirmed not possible.** BLHeli_32 sets the STM32's
  Read-Out Protection (RDP) fuse; converting to AM32 always requires physically soldering SWD
  wires (or clip leads) and clearing RDP via a real debugger first — no software-only path exists.
  See [Hardware Findings](docs/knowledge/hardware-findings.md#firmware-dump-blocker-rdp) for the
  technical detail. A 3-piece ST-Link V2 clone debugger set is available as a last-effort tool if
  this is ever revisited, but clearing RDP always mass-erases the flash first — the same
  firmware-loss trade-off as Goal 2's blocker, plus the soldering step, plus a learning curve on
  the tool itself. Closed unless the firmware-loss trade-off and the soldering/tooling effort are
  both explicitly accepted.

- **Cross-version Setup-block field validation — partially done.** Real `.ixi` backups exist for 4
  ESC families/firmware revisions (a 6S 4-in-1 ESC on firmware 32.7, and 3 more boards on 32.9,
  32.9.5, and 32.10 — see [Hardware Findings](docs/knowledge/hardware-findings.md) for full
  per-board detail). Field *names*: 12 of the 13 confirmed fields are identical across all 4
  revisions; the one confirmed structural change is `Eep_Pgm_Pwm_Freq` (a single byte on 32.7,
  which only supported static PWM) splitting into `Eep_Pgm_Pwm_Frequency_Hi`/`_Lo` (two bytes) on
  firmware 32.9+, which added variable PWM. Byte *offsets* on the non-32.7 firmware are **not yet
  confirmed** — needs a fresh `dump-config --out` read via this project's own tool against one of
  those boards, since the real app's own debug logs elide the raw Setup-block payload and `.ixi`
  files only contain already-decoded values. See
  [Setup Block Fields](docs/knowledge/setup-block-fields.md) for the full method.

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
**Copyrighted vendor binaries are different and permanent**: see `AGENTS.md`'s Publishing Gate —
`dumps/*.bin`/`*.hex`, and any other vendor firmware in a user's own app/archive folder, are
gitignored and never committed or published. Each user fetches their own copy of the vendor's test
firmware directly from BLHeli's official upstream repository (`docs/USAGE.md` §1b) — this project
never needs to redistribute it, so there is no publish decision to make about it.

A `LICENSE` file is still needed before any public release and has not been added yet.

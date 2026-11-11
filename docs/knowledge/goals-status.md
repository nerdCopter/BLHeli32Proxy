# Goals & Status

Four goals, settled with the user (2026-09-04). Terminology: **"firmware dump"** = the ESC's own
executable code; **"backup"** = the config/Setup-block data (matches BLHeliSuite32xl's `.ixi`
format).

```mermaid
flowchart TD
    A[BLHeli32Proxy] --> G1[1. Backups]
    A --> G2[2. Firmware dumps]
    A --> G3[3. Bootloader unlock]
    A --> G4[4. Proxy / licensing intercept]

    G1 --> G1a[✅ Raw byte-exact Setup-block read, all 4 ESCs]
    G1 --> G1b[✅ 45 of 46 named fields decoded, match real .ixi]
    G1 --> G1c[⬜ Eep_ESC_Mode: exhausted, needs new binary disassembly]
    G1 --> G1d[⬜ No .ixi-style file writer yet]
    G1 --> G1e[✅ Write-back tested: full-block-copy repair confirmed working]

    G2 --> G2a[❌ Blocked: STM32 RDP protection, confirmed]
    G2 --> G2b[✅ 1-byte guess bug fixed: discover_window(), unit + live-tested]
    G2 --> G2c[❌ Real mismatches cluster 2+ bytes; k=1 brute force found none in 2 real windows]

    G3 --> G3a[❌ Confirmed impossible without soldering]

    G4 --> G4a[✅ Real hostname + version-check endpoint confirmed]
    G4 --> G4b[✅ Approval server built]
    G4 --> G4e[✅ Version-check response format solved: bare OK> tag, functionally confirmed]
    G4 --> G4c[⬜ Real ESC-activation/Flash-write behavior with correct response — untested]
    G4 --> G4d[⬜ TLS trust question untested]

    style G2a fill:#f66,color:#000
    style G2c fill:#f66,color:#000
    style G3a fill:#f66,color:#000
    style G4c fill:#fa0,color:#000
```

## 1. Backups — mostly complete

- Raw ciphertext/plaintext Setup-block dump: works reliably, all 4 ESCs (`protocol/fourwayif.py`).
- 45 of 46 known field names decoded (`protocol/setup_fields.py`) — every value matches a real
  BLHeliSuite32xl `.ixi` backup exactly, confirmed across 3 independent MCU vendors. See
  [Setup Block Fields](setup-block-fields.md).
- Wired into CLI (`dump-config`/`probe-flash`/`dump-info-page`).
- Not done: `Eep_ESC_Mode` (the one remaining field, a genuinely exhausted gap — see
  [Setup Block Fields](setup-block-fields.md#whats-not-decoded-and-why)); a dedicated backup-file
  writer that produces a `.ixi`-style multi-`[ESCn]` file (currently prints to stdout only).
- **Write-back tested on real hardware (2026-09-07)** — see
  [Hardware Findings](hardware-findings.md#write_flash-without-erase-first-corrupts-far-more-than-the-targeted-bytes-2026-09-07).
  Confirmed: a partial write (fewer than the full 256 bytes) without erasing first can silently
  corrupt the rest of the Setup block. Confirmed safe pattern instead: write the complete 256-byte
  block in one call — proven as a real repair, copying one ESC's known-good block onto another's
  corrupted one. No general-purpose "change just this one field" write path exists yet; would need
  either an erase-then-full-rewrite sequence, or the same full-block-copy pattern with the target
  field edited in the source plaintext before re-encrypting.
  - **Scope correction (2026-11-11)**: the proven repair above was motor 3 → motor 0 **on the same
    physical AK32 4-in-1 board** (one PCB, 4 ESC channels sharing one Setup-block layout except
    `Eep_Pgm_Direction`). **Not yet tested**: copying a full 256-byte Setup block between two
    *separate physical* 4-in-1 boards of the same model (e.g. two different AK32 units). Expected
    to work the same way (identical firmware/model → identical struct layout), but this is an
    assumption, not a hardware-confirmed result. Also unconfirmed: whether any undecoded byte in
    the Setup block (see [Setup Block Fields](setup-block-fields.md#whats-not-decoded-and-why))
    carries a per-unit identifier that a blind full-block copy would also overwrite — the 45
    decoded fields include no documented serial/UUID, but the block isn't 100% decoded.
  - **Current as of 2026-11-11**: both of the user's 4-in-1 boards (AK32, Foxeer Reaper) were reset
    to factory defaults and freshly backed up (all 4 channels each) — see
    [Hardware Findings](hardware-findings.md#post-reset-setup-block-backups-both-boards-2026-11-11).
    Both now have a current, valid Setup-block backup on file in `dumps/` (git-tracked).

## 2. Firmware dumps — reopened, bug fixed, but real data looks mostly unrecoverable this way (2026-09-08)

- Direct `cmd_DeviceRead` remains confirmed blocked by STM32 Read-Out Protection (RDP), a real
  hardware protection, not a code gap. See
  [Hardware Findings](hardware-findings.md#firmware-dump-blocker-rdp) for the address-map evidence.
- The Verify-oracle side channel (`cmd_DeviceVerify`, no write/erase risk) is confirmed live even
  inside RDP-protected flash (2026-09-06). Its byte-by-byte brute-force path
  (`dump-firmware --discover-unresolved`) gained checkpoint/resume support and a `SIGTERM` fix
  (2026-09-08, both confirmed working on real hardware) — but the same testing pass found
  `cmd_DeviceVerify` calls shorter than 8 bytes, or not 8-byte-aligned, can report a mismatch **even
  for the objectively correct byte**, specifically near real content divergences (exactly where
  brute-forcing is needed). The earlier "~2-4 days, feasible" estimate was retracted — it assumed a
  correct guess would be recognized, which is now known false.
- **Fixed, same day**: `fw.discover_window()` guesses within a real, reliable 8-byte-aligned window
  instead of a bare byte (`--max-combo` caps how many simultaneously-unknown bytes per window are
  attempted, since cost is `256^k`). Unit-tested, then **validated against real hardware**: bisected
  2 real 32-byte unresolved chunks down to their actual mismatching 8-byte window, tested all 16
  single-position (k=1) hypotheses (8 per window) — **all 16 came back with no match**. Confirms
  `discover_window()` itself works correctly (clean negatives, no false positives, no stuck FC), but
  suggests real cross-firmware-version differences cluster in multi-byte groups rather than isolated
  bytes — the opposite of what byte-by-byte brute-forcing assumes, so a real gap may stay mostly
  unrecoverable via this oracle without a much closer candidate file. Also found the "18
  undiscoverable bytes" claim itself needed two corrections (one region had zero candidate data at
  all — a gap, not a mismatch; the other's "unresolved" status was itself a false positive from the
  same bug, and actually matches). Full account: [Hardware
  Findings](hardware-findings.md#critical-cmd_deviceverify-is-unreliable-below-8-bytes--when-misaligned-2026-09-08).
- No path forward for *direct* reads without physical SWD hardware, which is out of scope for this
  project. One unproven, unconfirmed non-destructive lead exists for the STM32F0 family — see
  [Hardware Findings](hardware-findings.md#firmware-dump-blocker-rdp).

## 3. Bootloader unlock (AM32, no soldering) — closed, not possible as scoped

- Confirmed requires physical SWD access always — even the `am32-firmware/AM32-unlocker` tool's
  "no soldering" claim only means no *permanent* solder joint, not no physical access. Full org:
  `github.com/orgs/am32-firmware/repositories` — `AM32`, `am32-configurator`, `am32-wiki`,
  `AM32-unlocker`, `AM32-bootloader`, `ConfigTool`, `Offline-Configurator`, `ESCSim`.
- Backlog item closed unless the user reconsiders soldering acceptable.

## 4. Proxy / licensing intercept — the original project goal, least advanced

- Real hostname confirmed (`blheli.org`), one endpoint captured and implemented (version-check).
- Approval server built (HTTP/HTTPS, two policy modes).
- **Not yet done**: capturing the actual ESC-activation (UUID+license) endpoint — the core purpose
  of this project — needs a real flash/activate attempt through BLHeliSuite32xl. See
  [Activation & Licensing](activation-licensing.md).
- TLS trust question untested (does the app trust the OS cert store, or pin BLHeli's cert?).
- **Still not a way to flash test firmware** (2026-09-07): the Setup-block write-back tested this
  session (Goal 1, above) never touches the application-firmware region and doesn't advance this
  goal. A real "Flash Selected ESC" attempt through the vendor app with this project's placeholder
  approval server (2026-09-06) showed `cmd_DeviceInitFlash` → `cmd_DeviceVerify` → `cmd_DeviceReset`
  only — no `cmd_DeviceWrite` — meaning the app silently declines to write firmware even when the
  known `status.php` ping is answered. Attempting to flash firmware directly via this project's own
  `write_flash()` (bypassing the vendor app and its licensing gate entirely) is not recommended:
  this session confirmed a partial write can corrupt far more than intended, and unlike the small
  recoverable Setup block, application firmware has no backup path (RDP blocks firmware dumps, see
  Goal 2) — a bad write there would be unrecoverable.
- **Licensing is not actually the blocker for this project's own tooling** (clarified 2026-09-07):
  the ESC bootloader itself enforces no activation check on writes at all — confirmed already
  (`activation-licensing.md`: "BLHeli's bootloader writes unconditionally regardless of
  source/target version"). The licensing gate lives entirely in the vendor app's own `TFlashState`
  UI logic, which this project's scripts never go through (`cmd_DeviceWrite` is called directly via
  4-way-if). So a real firmware write via this project's own tooling would not be blocked by
  licensing — it is technically possible, not just risky-because-unlicensed.
- **Why a real firmware write is still not attempted, capability aside**: (1) `page_erase()` has
  never been tested against real hardware at all; (2) the confirmed corrupts-more-than-requested
  finding above was only demonstrated on the small 256-byte Setup/info page, which may be
  EEPROM-emulation-style flash with different write semantics than the actual multi-page
  application-code flash sectors — that difference is unconfirmed either way; (3) unlike the
  Setup-block repair (an identical sibling ESC existed to copy from), no backup of the current
  firmware exists or can exist (RDP blocks dumps) — a bad write here has no recovery path. This
  is the same "real, irreversible risk" the backlog's Goal 4 item already flags, now with a
  concrete demonstrated example (this session's Setup-block corruption) rather than a theoretical
  concern.
- **Confirmed by decompilation, not inference, 2026-11-10**: the consumer `BLHeliSuite32xl` app's
  entire Flash-click call chain (`actFlashBLHeliExecute` down through the write/retry/activation
  functions) contains no network call of any kind. "Activation" is read directly from the ESC's
  own EEPROM byte (local device read), not validated against a server. This fully explains the
  2026-09-06 "zero extra network calls" finding — there is no second host to find in this build.
  **The proxy approval server cannot unlock flashing via its reply, because nothing in this app's
  write path reads or branches on a server reply.** See
  [Activation & Licensing](activation-licensing.md#goal-4-core-mystery-resolved-with-a-surprising-answer--2026-11-10-session-2-continued)
  for the full traced call graph. The real explanation for the historical "no `cmd_DeviceWrite`
  sent" observation is most likely a write-buffer-size-zero condition in `FUN_00a27760` (confirmed
  present: a literal "Nothing to write (memory size = 0)." check) — not a licensing refusal. Not
  yet confirmed on real hardware; that's the concrete next step, and it needs a live capture, not
  more static analysis.
- **Correction (2026-11-11)**: no application-firmware flash has ever been completed by this
  project, by any method. Not via the vendor app — BLHeli's activation/version-check servers are
  confirmed dead, which blocks the real app's own flash path and is the entire reason this project
  exists. Not via this project's own tooling either — `write_flash()` has only ever been tested
  against the small 256-byte Setup/config page (Goal 1, above); it has never been run against the
  actual application-code flash sectors, and `page_erase()` has never been tested on real hardware
  at all. There is no "known-good official firmware image we can flash" capability today — do not
  state otherwise.
- **Second candidate explanation found, cross-platform (2026-11-11)**: the standard Windows
  consumer build (`BLHeliSuite32.exe` 32.10.0.0, newly found in the archive) also contains "Nothing
  to write. ESC already matches with the parameters." / "Nothing to write. ESC already updated." —
  a mundane, correct no-op distinct from the "memory size = 0" bug hypothesis above. The 2026-09-06
  "zero `cmd_DeviceWrite`" observation is at least as plausibly explained by the test having staged
  firmware already present on the ESC as by a real bug. Next hardware test must use a genuinely
  different firmware version to tell these apart — see
  [Activation & Licensing](activation-licensing.md#cross-platform-corroboration-the-standard-windows-consumer-build-2026-11-11).
  Also: this build has no networking DLLs in its import table at all, independent corroboration
  (Windows PE, separate from the already-decompiled Linux ELF) that the consumer Flash path makes
  no network call.
- **Version-check response format solved, functionally confirmed on real hardware (2026-11-11)**:
  the real protocol is a bare `OK>` tag (no `SERVER>` wrapper) — found via Ghidra decompilation of
  the real app's response parser, not guesswork. Two earlier guesses (empty body, `SERVER>text=;`)
  and one further guess (`SERVER>OK>`) were each tried live and confirmed wrong before landing on
  the bare tag. Confirmation isn't just the status bar text: the "Check" (multi-ESC detection)
  action, which never completed cleanly before, now reports "Found Multiple ESC configuration" and
  successful per-channel setup reads for all 4 ESCs. Full writeup:
  [Activation & Licensing](activation-licensing.md#status-check-response-format-solved--the-real-protocol-is-ok-not-server-2026-11-11).
  **Not yet done**: a real "Flash Selected ESC" attempt with this corrected response in place —
  user has not yet agreed to risk a flash on their current boards for this specific test.

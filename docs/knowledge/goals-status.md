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
    G2 --> G2b[❓ verify-oracle explored, inconclusive]

    G3 --> G3a[❌ Confirmed impossible without soldering]

    G4 --> G4a[✅ Real hostname + version-check endpoint confirmed]
    G4 --> G4b[✅ Approval server built]
    G4 --> G4c[⬜ Real ESC-activation endpoint not yet captured]
    G4 --> G4d[⬜ TLS trust question untested]

    style G2a fill:#f66,color:#000
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

## 2. Firmware dumps — closed, blocked

- Confirmed blocked by STM32 Read-Out Protection (RDP), a real hardware protection, not a code
  gap. See [Hardware Findings](hardware-findings.md#firmware-dump-blocker-rdp) for the address-map
  evidence and [Hardware Findings](hardware-findings.md#the-verify-oracle-exploration) for the
  explored (and inconclusive) verify-command side-channel idea.
- No path forward without physical SWD hardware, which is out of scope for this project. One
  unproven, unconfirmed non-destructive lead exists for the STM32F0 family — see [Hardware
  Findings](hardware-findings.md#firmware-dump-blocker-rdp).

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

# OX32 web configurator — client-side JS analysis (2026-09-06)

Source: `https://ox32.oxbot.com/` (a third-party, web-based BLHeli32 ESC configurator, Web
Serial API, Vite/Vuetify bundle). Raw assets saved under `research/raw/ox32/`:
`index-BJF2AmC2.js` (main bundle, minified/obfuscated with a numeric string-table indirection),
`OX32_configurator_manual_en.txt` (accompanying manual, plain-text extract).

## Why this matters for Goal 4

This is independent, real-world proof that a working BLHeli32 flasher can be built without any
network licensing/activation call — directly relevant to this project's own struggle to get
`BLHeliSuite32xl`'s "Flash Selected ESC" to ever issue a write (see
[Activation & Licensing](../../docs/knowledge/activation-licensing.md)'s 2026-09-06 entries).

## Confirmed findings

- **4-way-if command enum** (minified as `W$`/`Y$` in the bundle) contains exactly five named
  values: `EXIT=52 (0x34)`, `RESET=53 (0x35)`, `INITFLASH=55 (0x37)`, `READ=58 (0x3A)`,
  `WRITE=59 (0x3B)`. Every value matches this project's own confirmed
  [Protocol Reference](../../docs/knowledge/protocol-reference.md) table exactly — independent
  third-party cross-validation, not new information for the byte values themselves.
- **No `ERASE`/`PAGE_ERASE` command anywhere in the bundle** (`grep -i erase` on the full 1.1MB
  file: zero hits). The write path calls `sendFourWayCommand(WRITE, addr, data)` directly, with no
  visible erase call before it in the surrounding code. This suggests BLHeli32's ARM bootloader
  `WRITE` command may auto-erase the covering page internally, rather than requiring a caller-side
  erase step first — **not proven, only suggested by omission**; OX32's own write function wasn't
  traced further than confirming the call site.
- **No licensing/activation footprint anywhere**: `grep -i` for `blheli.org`, `status.php`,
  `SERVER>`, `uuid`, `licens` across the whole bundle returns zero relevant hits (only unrelated
  UI-framework noise like Vuetify's `activatorRef`/`activatorProps`, and a stray `LICENSE` string
  from a bundled dependency's own license text). The manual PDF likewise never mentions activation,
  licensing, internet, or network requirements anywhere in its 13 pages.
- **Confirms real firmware flashing, not just config writes**: UI strings include `"Using Local
  Firmware"`, `"Please select Firmware or Upload Firmware File!"`, and `"Do not exit this interface
  until flashing is complete"` — this is a genuine ESC-firmware flasher, not a Setup-block-only
  config tool.
- Also confirms standard Betaflight MSP command codes independently (`MSP_API_VERSION=1`,
  `MSP_FC_VARIANT=2`, `MSP_FC_VERSION=3`, `MSP_UID=160`, `MSP_SET_MOTOR=214`,
  `MSP_SET_PASSTHROUGH=245`) — matches `protocol/msp.py`'s own `MSP_SET_PASSTHROUGH = 245` exactly.

## Not investigated further

- The exact write-loop (chunk size, iteration over a full hex image, whether a verify pass follows
  each write) — only the single call site `sendFourWayCommand(WRITE, addr, data)` was confirmed,
  not the calling loop around it.
- Whether OX32 has actually been used to successfully flash a real BLHeli32 ESC (no user reports
  or changelog reviewed) — this analysis is static code reading only, no live testing against
  OX32 itself.
- The obfuscation scheme (numeric string-table lookups via helper functions like `Dj()`/`t()`)
  wasn't fully reverse-mapped — only the specific strings/constants relevant to this question were
  chased down.

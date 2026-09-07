# Session Handoff — 2026-09-06

Bridge document for the next session — delete once the open items below are resolved or absorbed
into permanent docs.

## Key findings this session

1. **"Flash Selected ESC" confirmed to never write, on every real attempt (AK32 x2, Furling32
   x1)** — full detail in `docs/knowledge/activation-licensing.md`. Root cause traced to the app's
   own internal `TFlashState` logic (string evidence: `_FlashStateActivationFailed`,
   `_FlashStateRevRemovedNeedUpdate`), confirmed unrelated to network/licensing (zero requests
   beyond the harmless `status.php` ping, checked repeatedly with full packet capture + server
   logs) and confirmed via raw USB `usbmon`/`tshark` capture (no `cmd_DeviceWrite` on the wire at
   all). **Still unresolved**: what inside the app actually blocks the write — see open item 1.
2. **RDP blocks `cmd_DeviceRead` below `0x7C00`, but `cmd_DeviceVerify` doesn't** — it never
   transmits real content, only a match/mismatch signal, and this project confirmed live that the
   oracle discriminates correctly even at Read-blocked addresses. Built `dump-firmware` (new CLI
   command) on this: extracts app-code flash via Verify against candidate `.Hex` files, works for
   any model/MCU (safe boundary derived from the candidates themselves, not a hardcoded address).
   **Real bug found and fixed**: naive bisection produces non-256-aligned addresses, which produced
   false mismatches against real hardware — fixed by stepping through aligned pages first. See
   `docs/knowledge/protocol-reference.md`'s alignment note.
3. **Furling32 confirmed at 98.8%** (23,520/23,808 app-code bytes) against its own `.Hex` test
   candidate — `dumps/BLHeli32_Furling32 - Rev. 32.9.5 - AppCode_260906.bin`/`.hex`. Remaining 288
   bytes are a genuine gap in the one candidate tried (`0x7AE0`–`0x7BFF`), not a real mismatch.
   Closing it needs brute-force `discover_byte()` (built, works, ~11 hours at the measured
   round-trip rate for that byte count) — **deferred**, not run.
4. **AK32 confirmed impractical for the same technique**: only ~5% match against the three
   non-official test-firmware candidates available (32.7.4/32.8.3/32.9.5) — no official 32.7
   release candidate exists anywhere checked (GitHub history, local archives, OX32). Full recovery
   would need brute-force across ~95% of the image — not realistic.
5. **`testcode/` fully deprecated and removed** (user decision) — `BLHeli32_HexFiles/` (the app's
   own folder) is now the sole working catalog, 1000+ `.Hex` files across every version/manufacturer
   the user's archive holds. All docs/`AGENTS.md` references updated to match.
6. **`dump-flash` renamed to `dump-info-page`** — clearer name (it only ever reads the `0x7C00`+
   info page; the old name read as if it dumped all flash, which it never could).
7. **`dump-config --show-defaults CANDIDATE_HEX`** — new: the candidate `.Hex` file itself contains
   a genuine decryptable factory-default Setup block (same XTEA key, `0x7C00`). Prints a per-field
   real-vs-default comparison. Confirmed working against real captured plaintext.
8. **OX32 (third-party web configurator) research**: confirmed independently, via its own client
   JS, that a real BLHeli32 flasher can write without any `ERASE` command and without any
   licensing/network call — see `research/notes/OX32-configurator-analysis.en.md`.
9. **This project's own `write_flash()`/`page_erase()` built** (fourwayif.py) — hard-guarded to
   never touch the bootloader (below `0x2000`, confirmed via every real firmware-update file
   checked). **Never tested against real hardware** — erase-before-write semantics unconfirmed.
10. **Furling32_4in1_C confirmed as a real 4th test board, MCU is GD32F350x6** (GigaDevice, not
    STM32 — confirmed live via the Setup block's ESC_CPU field, offset `0x60`). Real firmware
    32.9.0 against the closest available candidate (32.9.5, plus 32.8.3/32.7.4 as fallback) gave
    **44.8%** (10,656/23,808 bytes) — a real middle-ground result between Furling32's 98.8% (exact
    version match) and AK32's 5% (no close version available at all), consistent with the
    "point-release drift" hypothesis (a later patch in a version line can share less code with an
    earlier patch of the same line than expected). Saved:
    `dumps/BLHeli32_Furling32_4in1_C - Rev. 32.9.5 - AppCode_260906.bin`/`.hex`.
11. `_default_firmware_dump_name()` now defaults into `dumps/` (was landing in the project root
    before this fix — caught live when the Furling32_4in1_C run's output appeared there instead).
12. `dump-firmware`'s output filename is now derived from the REAL connected hardware's own
    onboard identity string (`setup_fields.extract_identity_strings()`, new — reads the Setup
    block's layout/MCU strings via delimiter search, not a fixed offset), not from the candidate
    file guessed for comparison — the candidate might not even be the right model.

## Open items, in priority order

1. **Reverse-engineer/research the `status.php` response format** — the working theory going into
   next session (per direct user instruction) is that our server's current response (an empty
   body, an unverified guess, see `approval/codec.py`) might not be what actually needs to be sent
   — the real "proceed to flash" signal might live in a differently-formatted `SERVER>key=value;`
   response to this same endpoint, not a separate request. A static-strings pass on the compiled
   app found no additional format hints; next step is either live experimentation (vary the
   server's response body against real hardware and watch for a behavior change) or real
   disassembly. **Do this on the bench AK32** (no VTX heat pressure), per user instruction.
2. `write_flash()`/`page_erase()` need real-hardware testing before they're trustworthy — start
   with a single small write attempt at a safe, non-bootloader address, with the user's fresh
   explicit confirmation of the firmware-loss risk (standing rule, no exceptions).
3. `enter_4way_if()` has zero retry logic (unlike `connect_esc()`'s 3-attempt/5.5s-delay design) —
   today's session hit several `enter_4way_if` failures that a retry loop (matching
   BLHeliSuite32xl's own 5-attempt default, 1–10 user-configurable) would likely absorb.
4. Furling32's remaining 288-byte gap — `--discover-unresolved` is built and works, just never run
   to completion (≈11 hours at the measured rate). Revisit only if it becomes worth the time.
5. `docs/knowledge/DNS-dump.txt` (untracked) — a raw tcpdump paste already fully analyzed and
   folded into `activation-licensing.md`'s findings; low standalone value, candidate for deletion
   rather than committing as-is. Not decided.

## Next session start

Re-read `docs/knowledge/activation-licensing.md` (TFlashState/no-network findings) and
`docs/knowledge/protocol-reference.md` (Verify-oracle + alignment findings), then start with open
item 1 (protocol research on the bench AK32) — that's the direct next step toward the actual Goal 4
deliverable, not another hardware-dump exercise.

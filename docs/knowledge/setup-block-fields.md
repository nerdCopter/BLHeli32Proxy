# Setup Block Fields

Named-field decoding of the 192-byte decrypted Setup block plaintext, matching what
BLHeliSuite32xl's own `.ixi` backup file contains for the same ESC.

## Ground truth used

The user provided a real `.ixi` backup produced by the official BLHeliSuite32xl app (Linux build;
found under the user's own archive at the time, `$BLHELI32PROXY_ARCHIVE_DIR/BLHeliSuite32xl/ini-backups/`
— that subfolder name is just this user's own Linux-executable-matching convention, not enforced by
this project; never modified — a copy is kept here as
[BLHeli32_Aikon_AK32_4IN1_35A_6S_V1_0 - Rev. 32.7 - Multi_260904.ixi](BLHeli32_Aikon_AK32_4IN1_35A_6S_V1_0%20-%20Rev.%2032.7%20-%20Multi_260904.ixi)
for reference), confirmed taken with all 4 ESC channels genuinely wired on the real Aikon AK32
4-in-1. Cross-referencing this project's own decrypted plaintext (read live from all 4 ESCs)
against that file byte-by-byte is the method behind every confirmed offset below — not guessing,
not a public spec.

## Method

`Eep_Pgm_Direction` is the *only* byte that differs across the 4 ESCs (offset 3, values `1,2,2,1`),
exactly matching the real per-motor direction settings in the `.ixi`. Extending from there by
matching literal integer values (e.g. byte `0x8c` = 140 = the real app's `Eep_Pgm_Temp_Prot_Enable`)
at their natural sequential position confirmed 13 fields total.

## Confirmed fields (`protocol/setup_fields.py`)

| Offset | Width | Field | Confirmed value (this hardware) |
|---|---|---|---|
| 3 | 1 | `Eep_Pgm_Direction` | 1 or 2, varies per ESC |
| 4 | 1 | `Eep_Pgm_Rampup_Pwr` | 50 |
| 5 | 1 | `Eep_Pgm_Pwm_Freq` | 48 |
| 6 | 1 | `Eep_Pgm_Comm_Timing` | 0 |
| 7 | 1 | `Eep_Pgm_Demag_Comp` | 2 |
| 8–9 | 2 (LE) | `Eep_Pgm_Ppm_Min_Throttle` | 1014 |
| 10–11 | 2 (LE) | `Eep_Pgm_Ppm_Center_Throttle` | 1500 |
| 12–13 | 2 (LE) | `Eep_Pgm_Ppm_Max_Throttle` | 1985 |
| 14 | 1 | `Eep_Pgm_Enable_Throttle_Cal` | 1 |
| 15 | 1 | `Eep_Pgm_Temp_Prot_Enable` | 140 |
| 20 | 1 | `Eep_Pgm_Beep_Strength` | 40 |
| 21 | 1 | `Eep_Pgm_Beacon_Strength` | 70 |
| 22–23 | 2 (LE) | `Eep_Pgm_Beacon_Delay` | 600 |

Live-verified: `dump-config --motor-index 0` against the real hardware prints all 13 confirmed
fields, every value matching the real `.ixi`'s `[ESC1]` section exactly.

## What's NOT decoded, and why

Research into BLHeli_S (the open-source predecessor, `bitdump/BLHeli`, `BLHeli_S.asm`) confirmed
matching field *names* but **not** offsets or widths — BLHeli_32 widened several fields (e.g.
throttle values: 1 scaled byte in BLHeli_S vs. 2 raw bytes here) and reordered others. **No public
source exists** for BLHeli_32-only fields, since BLHeli_32 is closed-source:

- `Eep_Note_Array`, `Eep_Note_Config`
- All `Eep_Hw_*` capability flags (`Voltage_Sense_Capable`, `Current_Sense_Capable`,
  `LED_Capable_0..3`, `Pwm_Freq_Min/Max`)
- `Eep_Pgm_Sine_Mode`, `Eep_Pgm_Auto_Tlm_Mode`, `Eep_Pgm_Stall_Prot`
- `Eep_ESC_Layout`, `Eep_ESC_Mode`, `Eep_Nondamped_Capable`, `Eep_Pgm_Nondamped_Mode`,
  `Eep_Pgm_Max_Acceleration`, `Eep_Pgm_Brake_On_Stop`, `Eep_Pgm_Enable_Power_Prot`,
  `Eep_Pgm_Volt_Prot`

Many of these are 0/255 flag-like values with no way to disambiguate their offset by value-matching
alone (too many candidate positions look identical against a field of repeated 0x00/0xFF bytes).
**Decided approach**: don't guess. `setup_fields.decode_confirmed_fields()` returns only the 13
confirmed fields, clearly labeled as partial everywhere it's surfaced (CLI output, module
docstring).

## Cross-version field-name check (2026-09-05) — names mostly stable, one confirmed structural change

Compared the 13 confirmed field *names* (not yet byte offsets — that needs raw Setup-block reads,
not yet done on these boards) against real `.ixi` backups from 3 more boards: Furling32 (rev
32.9.5), FOXEER Reaper4IN1 F4 65A (rev 32.10), Furling32_4in1_C (rev 32.9) — see
`hardware-findings.md`'s "Second/Third/Fourth real hardware unit" sections for how these were
captured. **12 of 13 confirmed field names are identical across all 4 firmware revisions and 3
vendors** — `Eep_Pgm_Direction`, `Rampup_Pwr`, `Comm_Timing`, `Demag_Comp`, `Ppm_Min/Center/Max_Throttle`,
`Enable_Throttle_Cal`, `Temp_Prot_Enable`, `Beep_Strength`, `Beacon_Strength`, `Beacon_Delay` all
appear unchanged.

**One confirmed structural change**: `Eep_Pgm_Pwm_Freq` (single byte, offset 5, confirmed value 48
on the AK32/32.7) does **not** exist on any of the 3 newer-firmware boards — instead they all
expose `Eep_Pgm_Pwm_Frequency_Hi=48` (same value, same apparent role) **and** a new
`Eep_Pgm_Pwm_Frequency_Lo` (24 on all 3) that has no AK32 equivalent at all. This means the
Setup-block byte layout genuinely differs starting somewhere around offset 5 between firmware
32.7 and 32.9+ — a real, direct example of the same kind of widening/reordering already known to
have happened between BLHeli_S and BLHeli_32 (see "What's NOT decoded" below), now confirmed to
also happen *between BLHeli_32 firmware revisions themselves*.

**Why, per the user (2026-09-05)**: AK32's 32.7 firmware only supported a single static PWM
frequency — no variable/dual PWM. The `_Hi`/`_Lo` split on 32.9+ corresponds to a real added
feature (variable PWM frequency, needing two values to encode), not an arbitrary renumbering — the
field width genuinely grew because the ESC gained a capability the byte didn't need to represent
before.

**What this does NOT prove yet**: the exact new byte offsets for 32.9+ firmware. This check only
compared the app's own already-decoded field names/values (from `.ixi` files) — it did not use raw
Setup-block bytes from these boards (this project's own tool was never run against them; the real
app's own debug logs elide the Setup-block payload as `[...]`). **To actually confirm offsets on
32.9+ firmware**: reconnect one of these boards, run `dump-config --port ... --motor-index N`, and
diff the raw decrypted plaintext against the corresponding `.ixi` section byte-by-byte, same method
as the original AK32 confirmation above. Not yet done — a good next step when hardware is
available again.

**Practical implication for `decode_confirmed_fields()`**: given the confirmed `Pwm_Freq` layout
change, **do not trust this function's output against non-AK32/32.7 firmware** until offsets are
reconfirmed — every field from offset 5 onward could be shifted by the width difference. This
reinforces the existing safety note below, not a new restriction.

## Safety note — read this before extending this module

The raw byte-exact ciphertext/plaintext dump (already working, `fourwayif.read_flash()`) remains
the actual restore-safe backup mechanism regardless of field-decode completeness — it can't
misinterpret anything since it's read back byte-for-byte, not reconstructed from named fields.
**This module's output must never drive a write-back/restore path** until/unless the remaining
fields are properly confirmed (e.g. via a deliberate differential test: change one real setting via
BLHeliSuite32xl, re-read, see which byte changed). It exists for read-only reporting and human
comparison against a real `.ixi`, nothing more.

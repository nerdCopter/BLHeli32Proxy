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

## Method — original 13 fields (2026-09-04)

`Eep_Pgm_Direction` is the *only* byte that differs across the 4 ESCs (offset 3, values `1,2,2,1`),
exactly matching the real per-motor direction settings in the `.ixi`. Extending from there by
matching literal integer values (e.g. byte `0x8c` = 140 = the real app's `Eep_Pgm_Temp_Prot_Enable`)
at their natural sequential position confirmed 13 fields total.

## Method — 8 more fields via differential capture (2026-09-07)

**General technique, reusable for any BLHeli32 hardware/firmware, not specific to this board**:
change every changeable setting to a distinct value in the real app at once (not one at a time —
far faster), Write Setup, then diff the raw Setup-block plaintext against a pre-change backup
byte-by-byte. Match each changed byte's new value against the `.ixi`'s new field values. This
resolved 7 of 8 new fields cleanly in one pass:

- `Eep_Pgm_Volt_Prot`, `Eep_Pgm_Enable_Power_Prot`, `Eep_Pgm_Brake_On_Stop`,
  `Eep_Pgm_Max_Acceleration` — each a unique changed value, unambiguous match.

**Where multiple boolean-like fields changed simultaneously and collided** (offsets 26/29/30/31 all
flipped `0`→`1` in the same pass — `Nondamped_Mode`, `Sine_Mode`, `Auto_Tlm_Mode`, `Stall_Prot`),
resolved with targeted follow-up single-field toggles: revert one field, re-diff against the
previous capture (not the original baseline) — whichever single offset changes is that field. Two
follow-up passes (revert `Nondamped_Mode`+`Stall_Prot` together but to *different* value shapes
— one flips a boolean back, the other lacked a third state so also just flipped — then revert
`Sine_Mode` alone) fully resolved all four. General lesson for future collisions: prefer giving
colliding candidates genuinely distinct target values in the first pass (not just "on") so a single
diff disambiguates without needing follow-ups at all — plan the distinct-value set with this in
mind before writing.

`Eep_Pgm_Volt_Prot` and `Eep_Pgm_Max_Acceleration` store the **raw on-flash byte** in this table
(27, 58) — the app UI divides by 10 for display ("2.70 V", "5.8% per ms"). That division is an
observed correlation (multiple values checked, consistent), not confirmed against the real `.ixi`
text file's own on-disk representation (never captured with a non-default value) — flagged as
inferred, not re-verified as literally what a `.ixi` file would contain on disk.

`Eep_Pgm_Stall_Prot` on this firmware (AK32 32.7) has only 2 UI states (Normal/Off encoded as 1/0)
— other hardware/firmware may expose more states at this same offset; re-confirm per-firmware
before trusting a wider enum range here.

**1 more field, same session**: `Eep_Note_Config` (offset 28) — changing just "Music Note Config"'s
Length/Interval numbers (not the full note sequence) changed exactly one byte: `0x50`→`0x37`.
Decoded as `Length<<4 | Interval` (0x50 = Length 5, Interval 0; 0x37 = Length 3, Interval 7) —
matches the app's display exactly, and matches the real `.ixi`'s own literal `Eep_Note_Config=80`
value (80 = 0x50) for the original state. This is strong confirmation that the raw on-flash byte
*is* the `.ixi` file's own on-disk representation for at least this field, not just a convenience
this module invented.

## Confirmed fields (`protocol/setup_fields.py`) — 22 of ~38 total `.ixi` fields

| Offset | Width | Field | Confirmed value (original baseline) | Confirmed 2026-09-07 |
|---|---|---|---|---|
| 3 | 1 | `Eep_Pgm_Direction` | 1 or 2, varies per ESC | |
| 4 | 1 | `Eep_Pgm_Rampup_Pwr` | 50 | |
| 5 | 1 | `Eep_Pgm_Pwm_Freq` | 48 | |
| 6 | 1 | `Eep_Pgm_Comm_Timing` | 0 | |
| 7 | 1 | `Eep_Pgm_Demag_Comp` | 2 | |
| 8–9 | 2 (LE) | `Eep_Pgm_Ppm_Min_Throttle` | 1014 | |
| 10–11 | 2 (LE) | `Eep_Pgm_Ppm_Center_Throttle` | 1500 | |
| 12–13 | 2 (LE) | `Eep_Pgm_Ppm_Max_Throttle` | 1985 | |
| 14 | 1 | `Eep_Pgm_Enable_Throttle_Cal` | 1 | |
| 15 | 1 | `Eep_Pgm_Temp_Prot_Enable` | 140 | |
| 16 | 1 | `Eep_Pgm_Volt_Prot` | 0 | ✅ raw byte, UI shows ÷10 volts |
| 18 | 1 | `Eep_Pgm_Enable_Power_Prot` | 1 | ✅ |
| 19 | 1 | `Eep_Pgm_Brake_On_Stop` | 0 | ✅ raw percent |
| 20 | 1 | `Eep_Pgm_Beep_Strength` | 40 | |
| 21 | 1 | `Eep_Pgm_Beacon_Strength` | 70 | |
| 22–23 | 2 (LE) | `Eep_Pgm_Beacon_Delay` | 600 | |
| 25 | 1 | `Eep_Pgm_Max_Acceleration` | 0 | ✅ raw byte, UI shows ÷10 %/ms |
| 26 | 1 | `Eep_Pgm_Nondamped_Mode` | 0 | ✅ |
| 28 | 1 | `Eep_Note_Config` | 80 | ✅ packed `Length<<4\|Interval` |
| 29 | 1 | `Eep_Pgm_Sine_Mode` | 0 | ✅ |
| 30 | 1 | `Eep_Pgm_Auto_Tlm_Mode` | 0 | ✅ |
| 31 | 1 | `Eep_Pgm_Stall_Prot` | 1 | ✅ 2 states on this firmware |

Offsets 17, 24, 27 remain unconfirmed gaps within this range (unchanged across every capture so
far — either padding, or a field not reachable through the settings changed this session; every
other visible ESC Setup tab control has now been mapped, so these are likely padding).

Live-verified: `dump-config` (all-ESC default, or `--motor-index N`) against the real hardware
prints all 22 confirmed fields, every value matching the real `.ixi`'s section exactly.

**Cross-ESC validation (2026-09-07)**: dumped all 4 ESCs after the differential-capture session
above and compared every confirmed field across all 4 independent physical chips. All 22 fields
decoded to sensible, consistent values on every chip — `Eep_Pgm_Direction` varied as expected
(`3,2,2,1`), every other field matched exactly across all 4 *except* `Eep_Note_Config` (ESC0=55,
ESC1-3=80), which correctly isolates to the one deliberate single-ESC change made that session
("ESC 1 music set... only"). This is independent confirmation the offset map is a real hardware
fact, not a coincidental match on one specific capture.

## What's NOT decoded, and why

Research into BLHeli_S (the open-source predecessor, `bitdump/BLHeli`, `BLHeli_S.asm`) confirmed
matching field *names* but **not** offsets or widths — BLHeli_32 widened several fields (e.g.
throttle values: 1 scaled byte in BLHeli_S vs. 2 raw bytes here) and reordered others. **No public
source exists** for BLHeli_32-only fields, since BLHeli_32 is closed-source. Remaining, after the
2026-09-07 differential-capture pass resolved 9 of the fields previously listed here:

- `Eep_Note_Array` — the actual melody note sequence (a separate field from `Eep_Note_Config`,
  confirmed above at offset 28), likely a substantially different byte layout (variable-length
  sequence); not attempted via the differential method above.
- All `Eep_Hw_*` capability flags (`Voltage_Sense_Capable`, `Current_Sense_Capable`,
  `LED_Capable_0..3`, `Pwm_Freq_Min/Max`), `Eep_Nondamped_Capable` — expected read-only hardware
  descriptors, not reachable via a settings-change differential capture (nothing to toggle in the
  app for these). Would need a different technique (e.g. comparing across boards with genuinely
  different hardware capabilities) to ever localize.
- `Eep_ESC_Layout`, `Eep_ESC_Mode`, `Eep_Name`, `Eep_FW_Main_Revision`, `Eep_FW_Sub_Revision`,
  `Eep_Layout_Revision` — identity/version fields, also not user-changeable via settings, so not
  reachable via this method either (though the layout/CPU strings ARE separately recoverable via
  `extract_identity_strings()`'s delimiter search, not a fixed offset).

Offsets 17, 24, 27 within the already-explored range are also still unconfirmed — see the
confirmed-fields table above.

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

The raw byte-exact ciphertext/plaintext dump (already working, `fourwayif.read_flash()`,
`dump-config --raw-dir`) remains the actual restore-safe backup mechanism regardless of
field-decode completeness — it can't misinterpret anything since it's read back byte-for-byte, not
reconstructed from named fields. **This module's output must still never drive a write-back/restore
path** — 22 of ~38 fields confirmed as of 2026-09-07 is real progress (the differential-capture
method above works and is reusable), but 16 remain unconfirmed. Reconstructing a full plaintext
from only the confirmed fields would still leave those unknown bytes as guesses (zero-fill or
whatever a template happens to contain) — exactly the kind of partial-write gap that caused real
data loss in the write-test incident (see [Hardware
Findings](hardware-findings.md#write_flash-without-erase-first-corrupts-far-more-than-the-targeted-bytes-2026-09-07)),
just via reconstruction gaps instead of an erase side effect. This module exists for read-only
reporting and human comparison against a real `.ixi`; a real restore should always start from a
genuine raw backup of that exact ESC, not a field-by-field rebuild — until the full 38 fields are
confirmed, if ever.

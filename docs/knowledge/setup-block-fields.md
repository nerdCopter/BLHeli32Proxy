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

## Confirmed fields (`protocol/setup_fields.py`) — 28 of 46 known `.ixi` field names (27 int-valued
in `CONFIRMED_FIELDS`, plus `Eep_Name` decoded separately — see below; 46 = the union of AK32's 38
and Furling32's 45 real `.ixi` field names — see the cross-version section for the precise count
and the one field, `Eep_Pgm_Pwm_Frequency_Lo`, that's really the same already-confirmed byte as
`Eep_Pgm_Pwm_Freq` under a different name)

| Offset | Width | Field | Confirmed value (AK32 baseline) | Confirmed 2026-09-07 |
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
| 17 | 1 | `Eep_Pgm_Curr_Prot` | 255 (AK32 has no current sensor) | ✅ literal Amps, cross-version |
| 18 | 1 | `Eep_Pgm_Enable_Power_Prot` | 1 | ✅ |
| 19 | 1 | `Eep_Pgm_Brake_On_Stop` | 0 | ✅ raw percent |
| 20 | 1 | `Eep_Pgm_Beep_Strength` | 40 | |
| 21 | 1 | `Eep_Pgm_Beacon_Strength` | 70 | |
| 22–23 | 2 (LE) | `Eep_Pgm_Beacon_Delay` | 600 | |
| 24 | 1 | `Eep_Pgm_LED_Control` | 0 | ✅ packed multi-LED state, cross-version |
| 25 | 1 | `Eep_Pgm_Max_Acceleration` | 0 | ✅ raw byte, UI shows ÷10 %/ms |
| 26 | 1 | `Eep_Pgm_Nondamped_Mode` | 0 | ✅ |
| 27 | 1 | `Eep_Pgm_Curr_Sense_Cal` | 100 (AK32 has no current sensor) | ✅ `raw-100=%`, cross-version |
| 28 | 1 | `Eep_Note_Config` | 80 | ✅ packed `Length<<4\|Interval` |
| 29 | 1 | `Eep_Pgm_Sine_Mode` | 0 | ✅ |
| 30 | 1 | `Eep_Pgm_Auto_Tlm_Mode` | 0 | ✅ |
| 31 | 1 | `Eep_Pgm_Stall_Prot` | 1 | ✅ 2 states on this firmware |
| 32 | 1 | `Eep_Pgm_SBUS_Channel` | 255 (AK32 has no SBUS support) | ✅ raw channel number, cross-version |
| 33 | 1 | `Eep_Pgm_SPORT_Physical_ID` | 255 (AK32 has no S.PORT support) | ✅ raw ID, cross-version |

`Eep_Pgm_Curr_Prot`, `Eep_Pgm_Curr_Sense_Cal`, `Eep_Pgm_LED_Control`, `Eep_Pgm_SBUS_Channel`, and
`Eep_Pgm_SPORT_Physical_ID` don't appear in AK32's own real `.ixi` export at all (it lacks
current-sense hardware and SBUS/S.PORT support, so the app never lists those keys) — but the
underlying bytes still physically exist and decode to real, stable sentinel values (255, 100, or 0)
on that hardware too. All confirmed via real differential tests on different hardware — see the
cross-version section below for the full account, including two earlier wrong guesses (offsets 17
and 24) that these findings disproved.

**All 3 gaps from the original AK32-only chase (offsets 17, 24, 27) are now closed** — none were
padding; all three are real fields only reachable by testing hardware AK32 doesn't have.

Live-verified: `dump-config` (all-ESC default, or `--motor-index N`) against the real hardware
prints all 27 `CONFIRMED_FIELDS` (plus `Eep_Name`), every value matching the real `.ixi`'s section
exactly (where that board's own `.ixi` has a corresponding line — AK32's omits the 5 hardware/
firmware-dependent fields above entirely, see above).

**Cross-ESC validation (2026-09-07)**: dumped all 4 ESCs after the differential-capture session
above and compared every confirmed field across all 4 independent physical chips. All fields
decoded to sensible, consistent values on every chip — `Eep_Pgm_Direction` varied as expected
(`3,2,2,1`), every other field matched exactly across all 4 *except* `Eep_Note_Config` (ESC0=55,
ESC1-3=80), which correctly isolates to the one deliberate single-ESC change made that session
("ESC 1 music set... only"). This is independent confirmation the offset map is a real hardware
fact, not a coincidental match on one specific capture.

**`Eep_Name` confirmed (2026-09-07)**: still chasing the 3 remaining gaps, tried the one other
untouched UI control — the app's "Name" text field (blank on every ESC so far, `Eep_Name=` in
every real `.ixi`). Setting it to a real 16-character string ("TESTNAME12345678") and Write Setup
changed exactly bytes **128-143**, nothing else — a 16-byte, space-padded ASCII field. Matches
BLHeli_S's own source comment for this same field name exactly (`Eep_Name: DB "                "
; Name tag (16 Bytes)`) — direct structural confirmation of the shared heritage, not just field
names. Decoding via `setup_fields.decode_name()`, kept separate from `CONFIRMED_FIELDS` (an
int-only table) since this is a string. Doesn't help the offset 17/24/27 chase (nowhere near that
region) but is a real, independent new field. `dump-config` and the partial-backup `--out` file
now include it.

**Bug found and fixed while confirming this**: the long-standing `REAL_PLAINTEXT_ESC0`/`_ESC1` test
fixtures (`tests/test_setup_fields.py`) were silently missing 5 space (`0x20`) bytes around offset
135-140 — a hand-transcription error in a long repeated-byte run, present since these fixtures were
first written. Never caught because no confirmed field read past offset 31 until `Eep_Name`'s
discovery at offset 128 finally exposed it (the fixtures decoded to 187 bytes instead of 192).
Re-verified byte-exact against fresh live captures and fixed. A reminder that even "real capture,
not invented" test fixtures need periodic verification against fresh hardware reads, not just
trusted forever once written.

## Cross-version validation: Furling32 32.9.5 (2026-09-07) — 21 of 22 held directly, 2 more found

Connected a completely different real aircraft — Furling32 (real flyable quad, not a test bench
unit), GD32F350x6 (not STM32), firmware 32.9.5 (not 32.7). Read both ESCs via `dump-config
--raw-dir dumps` (read-only), decoded with the AK32-derived `CONFIRMED_FIELDS` table unchanged,
and compared against a genuine same-session `.ixi` export from the real app
(`BLHeli32_Furling32 - Rev. 32.9.5 - Multi_260907.ixi`, user's own archive).

**Result: every field matched exactly except `Eep_Pgm_Pwm_Freq`.** `Eep_Pgm_Rampup_Pwr`,
`Comm_Timing`, `Demag_Comp`, `Ppm_Min/Center/Max_Throttle`, `Enable_Throttle_Cal`,
`Temp_Prot_Enable`, `Volt_Prot`, `Enable_Power_Prot`, `Brake_On_Stop`, `Beep_Strength`,
`Beacon_Strength`, `Beacon_Delay`, `Max_Acceleration`, `Nondamped_Mode`, `Note_Config`,
`Sine_Mode`, `Auto_Tlm_Mode`, `Stall_Prot` all decoded identical to the real `.ixi`'s values at
their original AK32-confirmed offsets — **on a different MCU vendor and a different major firmware
line**. This is much stronger evidence than the earlier "every field from offset 5 onward could be
shifted" caution assumed — these offsets are very likely universal BLHeli_32 facts across the whole
32.x line, not board-specific coincidences.

**`Pwm_Freq` explained, not just "different"**: the real `.ixi` calls the same byte (offset 5)
`Eep_Pgm_Pwm_Frequency_Lo=24` here — matches our old "Pwm_Freq" decode of 24 exactly, same offset,
just renamed for the newer firmware's dual-PWM feature. A separate, genuinely new field,
`Eep_Pgm_Pwm_Frequency_Hi=48`, exists elsewhere in the struct (not yet located) rather than the
struct having shifted in place. **`CONFIRMED_FIELDS`'s existing entry for offset 5 (labeled
`Eep_Pgm_Pwm_Freq`) is left unchanged** — that name is exactly correct for AK32/32.7, where no Hi
variant exists — per this project's standing instruction to never regress working, version-specific
knowledge when extending to a new one. A firmware-version-aware label (`Pwm_Freq` on ≤32.7,
`Pwm_Frequency_Lo` on ≥32.9) would need a real design decision (not made yet) before changing code;
this section is the durable record either way.

**2 more fields found and CONFIRMED via a real differential test, on the same flyable aircraft**:
the Furling32 `.ixi` lists two fields AK32's `.ixi` never has at all — `Eep_Pgm_Curr_Prot=0` and
`Eep_Pgm_Curr_Sense_Cal=100` (current-sense-related; AK32 has no current-sense hardware, so its own
`.ixi` omits both keys entirely, though the underlying bytes still exist and decode to stable
values there — 255, 100). The real app's own ESC Setup tab for Furling32 showed both as genuine,
distinct controls ("Current Protection", a literal Amp threshold; "Current Sense Calibration", a
±% trim) that AK32 never had at all — screenshot confirmed. User offered a temporary, reversible
change on ESC#1 only (a real flyable aircraft, but a normal reversible Setup-block edit via the
real app's own Write Setup — a different risk category from this project's own `write_flash()`
experiments): **Current Protection → 200 A, Current Sense Calibration → -99%.** Diffing against
the pre-change backup showed exactly 2 bytes changed:

- **offset 17: `0`→`200`** — matches "Current Protection: 200 A" exactly (literal Amp value).
- **offset 27: `100`→`1`** — matches "Current Sense Calibration: -99%" exactly via `raw-100=%`
  (1-100=-99), confirming the offset-encoded-percentage theory precisely.

**This disproves the earlier offset-17 hypothesis.** Offset 17 was originally guessed to be a
retired BLHeli_S-heritage placeholder (matched the "always `0xFF`" convention on AK32, which lacks
current-sense hardware) — wrong. It's `Eep_Pgm_Curr_Prot`, actively used on hardware that has the
feature. **Offset 24 was also not `Curr_Prot`** as first guessed from the name+value match alone —
it stayed unchanged (`0`→`0`) in this same diff, so it remains the one genuine unconfirmed gap.

**Working theory for why offset 17 looked like a placeholder on AK32** (user's hypothesis, not
proven): the same physical byte slot may go unused/inert on hardware lacking the corresponding
feature (no current sensor → firmware never writes a meaningful value there, defaults to the
erased-flash `0xFF`) and only becomes actively written on hardware that has it — not a genuine
retired/dead field, just conditionally live. Consistent with 21 of the 22 other confirmed fields
holding their exact offsets on both boards — this is the one place a real per-hardware difference
showed up, not evidence the whole map is board-specific.

Reverted both settings back afterward — this is the user's real flying aircraft.

**3 more fields confirmed, same aircraft, one more differential pass**: with the value-matching
method proven twice now, ran a same-capture analysis first (no hardware needed) on the raw bytes
already captured — found `offset 32 = 17` (exact match to `Eep_Pgm_SBUS_Channel=17`) as a strong
lead purely from inspection. Confirmed all three properly with a real differential test: set
**SBUS Channel → CH9, S.PORT Physical ID → 7, LED Control → On-Off-On** (all distinct values, one
combined pass) plus disabled Throttle Cal Enable. Diffing against the pre-change backup showed
exactly 6 bytes changed — `offset 14` (`Enable_Throttle_Cal`, already-confirmed, expected),
`offset 17`/`27` (the just-reverted `Curr_Prot`/`Curr_Sense_Cal` from the prior test, also
expected), and:

- **offset 32 (`17`→`9`)**: `Eep_Pgm_SBUS_Channel`, raw = channel number directly.
- **offset 33 (`0`→`7`)**: `Eep_Pgm_SPORT_Physical_ID`, raw = ID directly.
- **offset 24 (`0`→`51`)**: `Eep_Pgm_LED_Control` — **this closes the last of the original 3-gap
  chase.** `51 = 0b00110011`; splitting into 2-bit pairs per LED gives `[3, 0, 3, 0]` for LEDs 0-3
  — matches the requested "On, Off, On" pattern exactly (4th LED not present on this board,
  `Eep_Hw_LED_Capable_3=0`). The offset and general "packed multi-LED byte" nature are confirmed by
  this single clean, unambiguous diff; the exact per-LED bit-width/color-code table is inferred
  from one data point only, not exhaustively mapped (e.g. what a 3rd color state or a different
  brightness would encode to is untested).

**This also retroactively confirms offset 24 was never `Curr_Prot`** (an earlier guess from
name+value matching alone, before this differential test) — it stayed unchanged during the
Curr_Prot/Curr_Sense_Cal test specifically because it's a different field entirely.

Reverted all settings back again afterward.

**Observation, not yet explained (2026-09-07)**: user noticed `Enable_Throttle_Cal` ("Throttle Cal
Enable" checkbox) is not user-editable in the app's ESC Setup tab while genuinely connected to the
real ESC, but the same checkbox IS editable when the tab is in its disconnected/offline-editing
state. Plausible hypothesis, not confirmed: throttle calibration is a live, hardware-interactive
procedure (the ESC listens for min/max throttle stick positions in real time), so the app may
deliberately lock this checkbox while connected as a safety/consistency gate, only allowing the
flag to be set as part of a full offline profile edit. Not verified against source or a captured
network/serial trace — flag for whoever revisits this, don't treat as settled.

## What's NOT decoded, and why

Research into BLHeli_S (the open-source predecessor, `bitdump/BLHeli`, `BLHeli_S.asm`) confirmed
matching field *names* but **not** offsets or widths — BLHeli_32 widened several fields (e.g.
throttle values: 1 scaled byte in BLHeli_S vs. 2 raw bytes here) and reordered others. This
relationship is a confirmed historical fact, not inference — `bitdump/BLHeli`'s own top-level
README states BLHeli_32 is literally "the third code developed" by the same project, after BLHeli
(Atmel/SiLabs 8-bit, GPLv3) and BLHeli_S (SiLabs 8-bit, GPLv3, "focus was on making throttle
response smooth"): a real generational rewrite for 32-bit ARM MCUs, explaining why field *names*
persist while the byte layout was reworked for new hardware capability. **No public source
exists** for BLHeli_32-only fields, since BLHeli_32 itself is closed-source. Remaining, after the
2026-09-07 differential-capture pass resolved 9 of the fields previously listed here:

- `Eep_Note_Array` — the actual melody note sequence (a separate field from `Eep_Note_Config`,
  confirmed above at offset 28), likely a substantially different byte layout (variable-length
  sequence); not attempted via the differential method above.
- All `Eep_Hw_*` capability flags (`Voltage_Sense_Capable`, `Current_Sense_Capable`,
  `LED_Capable_0..3`, `Pwm_Freq_Min/Max`), `Eep_Nondamped_Capable` — expected read-only hardware
  descriptors, not reachable via a settings-change differential capture (nothing to toggle in the
  app for these). Would need a different technique (e.g. comparing across boards with genuinely
  different hardware capabilities) to ever localize.
- `Eep_ESC_Layout`, `Eep_ESC_Mode`, `Eep_FW_Main_Revision`, `Eep_FW_Sub_Revision`,
  `Eep_Layout_Revision` — identity/version fields, also not user-changeable via settings, so not
  reachable via this method either (though the layout/CPU strings ARE separately recoverable via
  `extract_identity_strings()`'s delimiter search, not a fixed offset; `Eep_Name` itself is
  confirmed, see the table above).
- `Eep_SPORT_Capable` — discovered 2026-09-07 in the Furling32 `.ixi` alongside `LED_Control`,
  `SBUS_Channel`, and `SPORT_Physical_ID` (all 3 of those are now confirmed, see the table above and
  the cross-version section). `SPORT_Capable` has no `Pgm_` prefix — same category as the
  `Eep_Hw_*` capability flags above, a firmware-reported hardware descriptor with no corresponding
  user-facing control, so this method can't reach it either.

No offsets within the already-explored range (0-33) remain unconfirmed — all 3 original gaps
(offsets 17, 24, 27) are closed, see the confirmed-fields table above.

Many of the still-undecoded fields above are 0/255 flag-like values with no way to disambiguate
their offset by value-matching alone (too many candidate positions look identical against a field
of repeated 0x00/0xFF bytes) or, like the `Eep_Hw_*`/identity fields, have no user-facing control to
differentially test at all. **Decided approach**: don't guess. `setup_fields.decode_confirmed_fields()`
returns only the confirmed fields, clearly labeled as partial everywhere it's surfaced (CLI output, module
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
path** — 28 of 46 known field names confirmed as of 2026-09-07 is real progress (the
differential-capture method above works and is reusable), but 18 remain unconfirmed (mostly
`Eep_Hw_*`/identity fields with no user-facing control to test, plus `Eep_Note_Array`'s melody
data and `Eep_SPORT_Capable`). Reconstructing a full plaintext
from only the confirmed fields would still leave those unknown bytes as guesses (zero-fill or
whatever a template happens to contain) — exactly the kind of partial-write gap that caused real
data loss in the write-test incident (see [Hardware
Findings](hardware-findings.md#write_flash-without-erase-first-corrupts-far-more-than-the-targeted-bytes-2026-09-07)),
just via reconstruction gaps instead of an erase side effect. This module exists for read-only
reporting and human comparison against a real `.ixi`; a real restore should always start from a
genuine raw backup of that exact ESC, not a field-by-field rebuild — until the full 38 fields are
confirmed, if ever.

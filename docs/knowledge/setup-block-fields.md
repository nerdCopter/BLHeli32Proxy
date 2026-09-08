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

## Confirmed fields (`protocol/setup_fields.py`) — 45 of 46 known `.ixi` field names (42 int-valued
in `CONFIRMED_FIELDS`, plus `Eep_Name`/`Eep_ESC_Layout`/`Eep_Note_Array` each decoded separately —
see below; 46 = the union of AK32's 38 and Furling32's 45 real `.ixi` field names — see the
cross-version section for the precise count and the one field, `Eep_Pgm_Pwm_Frequency_Lo`, that's
really the same already-confirmed byte as `Eep_Pgm_Pwm_Freq` under a different name). Only
`Eep_ESC_Mode` remains unconfirmed as of 2026-09-08 — see "What's NOT decoded" below.

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
| 0 | 1 | `Eep_FW_Main_Revision` | 32 | ✅ 2026-09-08, cross-board correlation |
| 1 | 1 | `Eep_FW_Sub_Revision` | 70 | ✅ 2026-09-08, cross-board correlation |
| 2 | 1 | `Eep_Layout_Revision` | 44 | ✅ 2026-09-08, cross-board correlation |
| 5 | 1 | `Eep_Pgm_Pwm_Frequency_Lo` | 48 | ✅ 2026-09-08, same byte as `Eep_Pgm_Pwm_Freq`, new name only |
| 34 | 1 | `Eep_Pgm_Pwm_Frequency_Hi` | 255 (AK32 has no dual-PWM firmware) | ✅ 2026-09-08, real differential test |
| 48 | 1 | `Eep_Hw_Voltage_Sense_Capable` | 0 | ✅ 2026-09-08, cross-board correlation |
| 49 | 1 | `Eep_Hw_Current_Sense_Capable` | 255 | ✅ 2026-09-08, cross-board correlation |
| 50 | 1 | `Eep_Hw_LED_Capable_0` | 0 | ✅ 2026-09-08, cross-board correlation |
| 51 | 1 | `Eep_Hw_LED_Capable_1` | 0 | ✅ 2026-09-08, cross-board correlation |
| 52 | 1 | `Eep_Hw_LED_Capable_2` | 0 | ✅ 2026-09-08, cross-board correlation |
| 53 | 1 | `Eep_Hw_LED_Capable_3` | 0 | ✅ 2026-09-08, cross-board correlation |
| 54 | 1 | `Eep_Hw_Pwm_Freq_Min` | 255 | ✅ 2026-09-08, cross-board correlation |
| 55 | 1 | `Eep_Hw_Pwm_Freq_Max` | 255 | ✅ 2026-09-08, cross-board correlation |
| 62 | 1 | `Eep_SPORT_Capable` | 255 | ✅ 2026-09-08, cross-board correlation |
| 63 | 1 | `Eep_Nondamped_Capable` | 1 | ✅ 2026-09-08, cross-board correlation |

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

## Cross-version validation: damaged FOXEER Reaper, AT32F421 (2026-09-08) — third MCU vendor, 2 more fields via differential test

Connected a third distinct MCU vendor (Artery Technology's AT32F421, after ST's STM32 and
GigaDevice's GD32) — a damaged FOXEER Reaper4IN1, firmware 32.10.0. All 22 fields confirmed on
AK32/Furling32 held exactly on this board too (see `hardware-findings.md`'s "damaged unit"
section for the full account). Changed "PWM Frequency High" from 128 kHz to 48 kHz via the real
app's ESC Setup tab on ESC1 (motor_index 0), Write Setup, diffed the raw plaintext against a
pre-change backup: exactly one byte changed.

- **offset 34: `128`→`48`** — `Eep_Pgm_Pwm_Frequency_Hi`, literal kHz value, same encoding as
  `_Lo` (offset 5). A genuinely new offset, not previously located.

`Eep_Pgm_Pwm_Frequency_Lo` (the real `.ixi`'s 32.9+ name for offset 5) is added to
`CONFIRMED_FIELDS` as a second dict entry for that same offset — the pre-existing AK32-only
`Eep_Pgm_Pwm_Freq` entry is untouched, per this project's standing instruction to never overwrite
a working version-specific mapping when extending to a new firmware version. Both names now
decode from the same byte; `dump-config` emits both.

## Method — 12 more fields via cross-board value correlation (2026-09-08)

**A third confirmation method, distinct from differential capture and direct real-`.ixi` value
matching**: with 3 independent real boards' raw plaintext AND their real `.ixi` values already on
hand (AK32, Furling32, the damaged Reaper), searched every offset 0-191 for a byte pattern
matching each remaining unconfirmed field's known per-board `.ixi` value, simultaneously across
all 3 boards. No new hardware interaction needed — pure analysis of already-captured data.

**7 fields resolved by a unique, unambiguous 3-way match** (exactly one offset out of 192 matched
all 3 boards' values simultaneously): `Eep_FW_Sub_Revision` (offset 1), `Eep_Layout_Revision` (2),
`Eep_Hw_LED_Capable_0/1/2` (50/51/52), `Eep_Hw_Pwm_Freq_Min/Max` (54/55).

**6 more resolved by elimination plus sequential-position corroboration**: `Eep_FW_Main_Revision`
(offset 0), `Eep_Hw_Voltage_Sense_Capable` (48), `Eep_Hw_Current_Sense_Capable` (49),
`Eep_Hw_LED_Capable_3` (53), `Eep_SPORT_Capable` (62), `Eep_Nondamped_Capable` (63) each had
multiple raw candidate offsets individually; eliminating any offset already assigned to a
different confirmed field left exactly one candidate in every case. Every resolved offset also
lands in a clean, unbroken sequential run matching the real `.ixi`'s own declared field order
exactly (`FW_Main_Revision, FW_Sub_Revision, Layout_Revision` at 0-2; `Hw_Voltage_Sense_Capable`
through `Hw_Pwm_Freq_Max` at 48-55; `SPORT_Capable, Nondamped_Capable` at 62-63) — structural
corroboration beyond the value match alone.

**`Eep_ESC_Mode` could NOT be located** (value `2` on all 3 boards' real `.ixi`) — the literal
byte value `2` does not appear anywhere at all in the Reaper's 192-byte plaintext. This suggests
`Eep_ESC_Mode` may not be a directly-stored byte in this structure — possibly derived by the app
from firmware/layout metadata it already has, rather than read from the ESC. Left unconfirmed
rather than guessed; a real negative result, not an oversight.

At this point in the session, 3 names remained: `Eep_Note_Array`, `Eep_ESC_Layout`,
`Eep_ESC_Mode`. The next two sections close the first two — see "What's NOT decoded" below for
the final, current state (only `Eep_ESC_Mode` remains).

## Method — `Eep_ESC_Layout` and `Eep_Note_Array` closed via this project's own research corpus (2026-09-08)

**No new hardware needed for this pass** — the lead came from re-reading this project's own
already-translated research notes. `research/notes/BLHeliSuite32-Reverse3.en.md` (a real
disassembly of the vendor's own `ReadSetupFromBinString`, done in 2021) documents a fixed
wire-format offset table straight from the vendor's own binary, including `Eep_ESC_Layout` (offset
0x40 = 64, 32 bytes) and `Eep_Note_Array` (offset 0x90 = 144, 48 bytes) — a lead not previously
connected to this module's own empirical offset-hunting work. `BLHeliSuite32-Reverse5.en.md`
(2024, a later recompiled build) shows these exact numbers drifting in the *in-memory* `TBLHeli`
object layout between binary versions, but explicitly confirms **"the wire protocol itself did
not change"** — the 256-byte on-flash format is stable even when the app's own internal struct
layout gets recompiled with different offsets.

**`Eep_ESC_Layout` (offset 64, 32 bytes, `#`-delimited ASCII, space-padded)**: cross-checked
against already-captured raw plaintext from all 3 real boards on file — byte-exact match to each
board's own real `.ixi` value in every case:

- AK32: `#Aikon_AK32_4IN1_35A_6S_V1_0#   ` → `Aikon_AK32_4IN1_35A_6S_V1_0`
- Furling32: `#Furling32#                     ` → `Furling32`
- Reaper: `#FOXEER_Reaper4IN1_F4_65A_128#  ` → `FOXEER_Reaper4IN1_F4_65A_128`

`decode_esc_layout()` implements this. `extract_identity_strings()`'s existing delimiter search is
kept as-is (more robust, also recovers the MCU string) — this fixed offset is an additional,
independently-confirmed fact, not a replacement.

**`Eep_Note_Array` (offset 144, 48 bytes)**: locating the offset was only half the problem — the
actual note *encoding* still had to be derived from scratch, since no source documents it. First
pass decoded against 2 distinct real Furling32 melodies (`esc0`/`esc1`-setup-20260907-17*.bin, 74
total note instances spanning octaves 4-6 and 3 different durations), the AK32's own melody
(duration-8 notes only), and the Reaper's empty state (all `0xFF`) — every single one matched its
board's own real `.ixi` Eep_Note_Array text byte-for-byte, using a partial formula covering notes
and one pause length (1/8) only. **The complete formula, confirmed by the real differential test
below and matching `decode_note_array()`'s actual implementation exactly:**

```
byte = (duration_index << 6) | pitch
pitch 0-59: a real note, pitch = 16*(octave-4) + chromatic_semitone (C=0, C#=1, D=2, ... B=11)
pitch 60/61: a rest/pause ("P" in .ixi text); pause_length =
    duration_for_index[duration_index] * (16 if pitch == 61 else 1)
duration_index: 0 = 8th, 1 = quarter, 2 = half, 3 = whole
```

Every repeated note token in every real melody mapped to the exact same byte value, and every
distinct token mapped to a distinct byte value — confirmed by internal cross-consistency across
~74 note instances, not a one-off coincidence. `decode_note_array()` implements this, emitting the
same concatenated text format a real `.ixi` shows (e.g. `C68G58C68...`).

**Fully closed via a real differential test, same day (2026-09-08)**: the vendor app's own Music
Editor has a tooltip documenting its exact script syntax (`[Note][Octave][Length]` for notes,
`P[Length]` for rests) — this itself is worth recording, since neither the manual nor this
project's research corpus mentions it: notes support 4 lengths (1/1, 1/2, 1/4, 1/8, matching the
2-bit duration field derived above exactly), but **pauses support 8 lengths** (1/1 through
1/128) — wider than notes get, a real detail this project hadn't anticipated from the byte data
alone. Typed the exact script `C42 P1 P2 P4 P8 P16 P32 P64 P128` into the damaged Reaper's ESC1,
Write Setup, read back
([`dumps/esc0-setup-20260908-103942.bin`](../../dumps/esc0-setup-20260908-103942.bin)). All 9
tokens decoded to an exact match:

- `C42` (the previously-untested half-note duration) → byte `0x80` = duration_index 2, pitch 0 —
  confirms the inferred half-note mapping exactly as predicted.
- `P1`/`P2`/`P4`/`P8` → bytes `0xfc/0xbc/0x7c/0x3c` — same 2-bit duration field as notes, pitch 60.
- `P16`/`P32`/`P64`/`P128` → bytes `0xfd/0xbd/0x7d/0x3d` — same duration bits, but **pitch 61**
  instead of 60: the extra pause range is a pitch-code acting as a x16 scale-extension bit, not a
  wider duration field. `pause_length = duration_for_index[duration_index] * (16 if pitch==61 else 1)`
  — an elegant encoding that fits the vendor's own documented 8 pause lengths exactly.

Nothing about `Eep_Note_Array`'s encoding remains inferred. `research/notes/BLHeli-Music.en.md`
(an unrelated public music-notation post, translated before this byte-level work) had already
independently stated 4 note lengths, 4 octaves, and rests going "down to 1/128" — all now
confirmed to match this board's real behavior exactly, resolving that note's earlier open caveat.

`Eep_ESC_Mode` is now the only field name from the original 46 that remains genuinely unconfirmed.

## What's NOT decoded, and why

Research into BLHeli_S (the open-source predecessor, `bitdump/BLHeli`, `BLHeli_S.asm`) confirmed
matching field *names* but **not** offsets or widths — BLHeli_32 widened several fields (e.g.
throttle values: 1 scaled byte in BLHeli_S vs. 2 raw bytes here) and reordered others. This
relationship is a confirmed historical fact, not inference — `bitdump/BLHeli`'s own top-level
README states BLHeli_32 is literally "the third code developed" by the same project, after BLHeli
(Atmel/SiLabs 8-bit, GPLv3) and BLHeli_S (SiLabs 8-bit, GPLv3, "focus was on making throttle
response smooth"): a real generational rewrite for 32-bit ARM MCUs, explaining why field *names*
persist while the byte layout was reworked for new hardware capability. **No public source
exists** for BLHeli_32-only fields, since BLHeli_32 itself is closed-source (except where this
project's own research corpus recovered offsets via disassembly — see `Eep_ESC_Layout` and
`Eep_Note_Array` above). After the 2026-09-07 differential-capture pass, the 2026-09-08 cross-board
correlation pass, and the 2026-09-08 research-corpus pass (all above) resolved every other known
field name, only 1 name remains unconfirmed:

- `Eep_ESC_Mode` — value `2` on all 3 boards tested, but that literal byte does not appear
  anywhere in the Reaper's 192-byte plaintext (see the cross-board correlation section above).
  **Checked exhaustively (2026-09-08), genuinely exhausted, not just deferred**: the symbol name
  `ESC_Mode`/`Eep_ESC_Mode` doesn't appear anywhere in this project's entire translated research
  corpus (every `.en.md` note, including the same 2021/2024 disassembly passes that DID recover
  `Eep_ESC_Layout`/`Eep_Note_Array`'s offsets — see the method section above); the vendor's own
  bundled manual never documents an "ESC Mode" setting by that name; and the offset 34-47 gap (the
  one unconfirmed stretch left in the already-explored region) is all `0xFF` sentinel on every
  board tested, not hiding the value anywhere either. **One new lead, not yet followed up**: a real
  screenshot of the app's read-only "ESC overview" tab (`Damaged_2026-09-08_090705.png`) shows a
  row simply labeled "Mode", displaying "Multi" uniformly across all 4 ESCs on the damaged Reaper —
  almost certainly this field's human-readable label for raw value `2`, though whether that tab's
  "Mode" is genuinely read from the wire or a per-layout constant the app displays regardless of
  device state is still unknown. Closing the byte-offset question further would need genuinely new
  binary disassembly work against the compiled app — a materially larger undertaking than this
  project's established method of translating already-published research, not attempted here.

No offsets within the already-explored range (0-34, 48-55, 62-63, 64-191) remain unconfirmed —
every gap closeable by differential capture, direct `.ixi` cross-reference, cross-board value
correlation, or this project's own research corpus has been closed, see the confirmed-fields table
above.

`Eep_ESC_Mode`'s value doesn't appear in the plaintext at all, so there's no byte pattern left to
search for. **Decided approach**: don't guess. `setup_fields.decode_confirmed_fields()` returns
only the confirmed fields, clearly labeled as partial everywhere it's surfaced (CLI output, module
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
path** — 45 of 46 known field names confirmed as of 2026-09-08 is real progress (differential
capture, direct `.ixi` cross-reference, cross-board value correlation, and this project's own
research corpus together), but 1 remains unconfirmed (`Eep_ESC_Mode`). Reconstructing a full
plaintext from only the confirmed fields would still leave that unknown byte (plus any padding
whose exact role isn't independently verified) as a guess — exactly the kind of partial-write gap
that caused real data loss in the write-test incident (see [Hardware
Findings](hardware-findings.md#write_flash-without-erase-first-corrupts-far-more-than-the-targeted-bytes-2026-09-07)),
just via reconstruction gaps instead of an erase side effect. This module exists for read-only
reporting and human comparison against a real `.ixi`; a real restore should always start from a
genuine raw backup of that exact ESC, not a field-by-field rebuild — until all 46 fields are
confirmed, if ever.

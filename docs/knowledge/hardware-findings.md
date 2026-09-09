# Hardware Findings

Empirical findings from real-hardware testing (2026-09-04): PyroDrone F7 (EmuFlight 0.4.3) + Aikon
AK32 4-in-1 35A 6S (BLHeli_32 firmware 32.7, STM32F051x6 — confirmed twice independently, 2026-09-06:
Aikon's own product page, `aikon-electronics.com/index.php?id=20`, states "MCU: STM32 F0" [family
only]; this board's own Setup-block `ESC_CPU` field, offset `0x60`, read live via `dump-config
--motor-index 0` [read-only: enter_4way_if → connect_esc → read_flash(0x7C00,256) → decrypt, no
write/erase], decodes to the literal ASCII string `#BLHeli_32*STM32F051x6#` — the exact sub-variant,
confirmed directly from this hardware, not inherited from the research blog post's different example
ESC as earlier assumed. Same read also confirmed `#Aikon_AK32_4IN1_35A_6S_V1_0#` at offset ~0x40).

## Test-hardware quirks — read these before re-testing

- **Port contention**: another process (your own BLHeliSuite32xl, or a leftover script) holding the
  serial port produces confusing, intermittent-looking failures that have nothing to do with the
  protocol. Check `fuser /dev/ttyACM0` before attributing a failure to a code bug.
  **Confirmed a real crash from this, not just a connect-time failure (2026-09-09)**: opening
  EmuFlight Configurator against the same FC mid-run, during a long unattended `dump-firmware
  --discover-unresolved` session, killed the whole process outright with an uncaught
  `serial.SerialException: device reports readiness to read but returned no data (device
  disconnected or multiple access on port?)` — raised from inside a live `verify_flash()` call, a
  different exception type than `fw.FourWayError`, so neither the `finally` block's
  `exit_interface()` guard nor the `KeyboardInterrupt` handler catches it. Progress up to that
  point was NOT lost (per-byte checkpointing had already saved 2 windows), but the process itself
  died ungracefully and no cleanup message printed. **Not yet fixed**: `_dump_firmware_body` should
  also catch `serial.SerialException` (or a broader base) alongside `KeyboardInterrupt` for any
  long unattended run, to fail as cleanly as an interrupt does. Practical rule until then: never run
  another serial client (BLHeliSuite32xl, EmuFlight/Betaflight Configurator, etc.) against the same
  FC while a long `dump-firmware` session is active — only one client can hold the port at a time,
  and this project's own error handling doesn't yet cover a mid-run steal cleanly.
- **Occasional `enter_4way_if` failure, unconfirmed cause**: twice during Betaflight testing
  (2026-09-04), the very first command of a fresh CLI invocation (`MSP_SET_PASSTHROUGH`) got no
  reply at all — a different failure than the `connect_esc()` timing issue below. Tried to
  reproduce deliberately (same motor, back-to-back invocations, zero delay) and couldn't — looks
  like an occasional USB/serial hiccup rather than a systematic timing bug. Not chased further; if
  it recurs often, revisit.
- **Real battery power matters**: with the FC on USB power only (no LiPo), some ESC channels
  connected unreliably. Once real 6S battery power was applied, all 4 channels connected
  consistently. If a channel behaves oddly, check power before debugging the protocol.
- **`connect_esc()` needs a retry, with a real ~5s delay, not a short one**: root-caused
  2026-09-04 (see the Betaflight cross-validation entry below for the full diagnosis) — the
  bootloader connect handshake reliably fails once right after a reset, and BLHeli firmware then
  enforces a documented ~5s lockout before it'll honor a retry
  ([BLH-Uart-Timeout.en.md](../../research/notes/BLH-Uart-Timeout.en.md)). `connect_esc()` defaults
  to `attempts=3`, `retry_delay=5.5` — a short delay (the original default was `0.3`) just retries
  inside the lockout and fails again. Same ack code (`ACK_D_GENERAL_ERROR`) as a genuinely empty
  channel either way, so that case can't be told apart from this one in advance.
- **Independent corroboration from the real app (2026-09-05)**: `BLHeliSuite32xl`'s own settings
  (`Settings/BLHeliSuite32xl.ini`, `[Interface] 4wifConnectDeviceRetry=5`) default to 5 retries too,
  user-configurable 1-10 in its UI. Matches this project's own `attempts` fix independently.
- **Killing a process mid-4-way-if session sticks the FC's passthrough state (2026-09-08)**: a
  `SIGTERM`'d `dump-firmware` process (via a `timeout` wrapper) never reached `exit_interface()`.
  Every fresh `enter_4way_if()` afterward (new process, new port open) got zero MSP reply, even
  after retries. Only fix found: physically unplug/replug the FC's USB cable (ESC power untouched).
  See "Goal 2 brute-force feasibility" below for the full incident — relevant to any long-running
  or interruptible command against this protocol, not just brute-forcing.
- **All 4 ESC channels confirmed working**: verified via the real BLHeliSuite32xl app's own status
  check (all 4 ESCs healthy, zero bad DShot frames each — raw output in
  [Suite-Check.txt](Suite-Check.txt)) and via this project's own code connecting to and reading all
  4 channels reliably, once the two issues above were accounted for.
- **Cross-validated through Betaflight passthrough (2026-09-04)**: same PyroDrone F7, this time
  running Betaflight instead of EmuFlight. `dump-config --motor-index N` decrypted all 4 channels correctly;
  `Eep_Pgm_Direction` read `1,2,2,1` for motors 0-3, exactly matching the AK32 `.ixi` ground truth
  (see [Setup Block Fields](setup-block-fields.md)) — confirms the 4-way-if protocol and field
  decode are FC-firmware-agnostic, not an EmuFlight-specific result.
  **New finding**: `connect_esc()`'s built-in 2 retries were often insufficient here — roughly half
  of ~20 individual attempts across motors 0-2 still failed outright (`ACK_D_GENERAL_ERROR`) and
  needed a full extra CLI invocation to succeed; motor 3 succeeded every time it was tried.

  Follow-up diagnosis (same session): tested whether re-sending `cmd_DeviceReset` on every retry
  was itself re-triggering a fresh-boot failure (motor 0, single reset then 5× `cmd_DeviceInitFlash`
  with no further reset) — motors 2/3 still succeeded instantly, motors 0/1 still failed all 5.
  Then tested whether a full session exit+re-enter (not just a device-level retry) was what actually
  recovered a stuck channel (motor 0, 5× independent fresh 4-way-if sessions) — failed all 5, even
  though that same channel had succeeded 3 of 8 times earlier this session using that exact
  approach. Battery voltage measured live via MSP_ANALOG at 22.9V both times, unchanged — ruled out
  as the variable explaining the difference between batches.

  **Root cause, confirmed against real Betaflight source** (github.com/betaflight/betaflight,
  `src/main/io/serial_4way.c` + `serial_4way_avrootloader.c`): `cmd_DeviceInitFlash` calls
  `Connect()` (`BL_ConnectEx()`), which sends the exact literal `"BLHeli"` connect handshake
  documented in [BLH-Uart-Timeout.en.md](../../research/notes/BLH-Uart-Timeout.en.md) — a real
  BLHeli firmware quirk where the first connect attempt right after the ESC's bootloader is
  (re-)entered reliably fails, and newer firmware then enforces a **~5s lockout** before it
  accepts a retry at all. Our `cmd_DeviceReset` request never sets the frame's `ADDR_L` byte to 1
  (it stays 0, the default), so it never triggers `serial_4way.c`'s hardware reboot-pulse path
  either — the ESC's bootloader is (re-)entered via the softer `BL_SendCMDRunRestartBootloader`
  path only, which is exactly the case this firmware quirk covers.

  This fully explains the earlier data: `connect_esc()`'s original `retry_delay` (0.3s) retried
  *inside* the ~5s lockout, so extra attempts (even 5 of them) mostly failed too — matching what
  was observed. Confirmed live: with `retry_delay` raised to 5.5s, motor 0 (previously 0/10 across
  two failing test batches) succeeded on the 2nd attempt 3 times in a row, no failures past
  attempt 2. Then all 4 motors connected via the real CLI (`dump-config`) on the first or second try
  with no further diagnosis needed. **Fix applied**: `connect_esc()` now defaults to `attempts=3`,
  `retry_delay=5.5` (down from the interim `attempts=5`/`retry_delay=0.3` mitigation, which treated
  the symptom without the correct delay). Whether the real BLHeliSuite32xl app avoids this by using
  the hardware reboot-pulse path (`ADDR_L=1`) instead, or just retries with a correct delay, is
  unconfirmed — would need a traffic capture of its own connect sequence to know, not pursued
  further since the fix above is already verified working.

## Second real hardware unit: Furling32 4-in-1 (2026-09-05)

A genuinely different aircraft/ESC, not the AK32 above — real quadcopter with propellers, powered
upside-down for safety, connected at **`/dev/ttyACM1`** (not `ACM0`). Real BLHeliSuite32xl status
check, saved verbatim: [Suite-Check-Furling32.txt](Suite-Check-Furling32.txt) — `Furling32 - Rev.
32.9.5 - Multi`, ESC#1 MASTER + ESC#2/3/4 SLAVE (2/3/4 reversed direction), all 4 channels healthy
(600k+ good DShot frames each, zero bad). This is the same firmware family as the second `.ixi`
already in the archive
(`2022-11-06-tekk32_BLHeli32_Furling32 - Rev. 32.9 - Multi_221106.ixi` — note: that file says
"Rev. 32.9", this live check says "Rev. 32.9.5"; a real firmware micro-version difference, not a
typo, both are genuinely from a Furling32 board) — a real opportunity for the still-not-done
cross-version Setup-block field validation (see `PLAN.md` backlog).

**New finding, root-caused (partially) from the app's own saved debug log
(`docs/knowledge/6inch-stellarh7dev.xlg` — user's own aircraft-based naming for this `.xlg` save,
not a fixed filename)**: opening the real app's Flash tab with this board connected produced
`Access violation at address 0000000000A34A7B, accessing address 0000000000000000` (a null-pointer
dereference, not a normal app error dialog) — after which only **ESC#1** showed as populated in
the Flash tab (identity `Furling32 Rev 32.9.5` shown, checkbox available); ESC#2-4 showed no
identity, no firmware dropdown, and both "Flash Selected ESC"/"Verify Selected ESC" were grayed
out.

**Confirmed this is a UI-layer bug, not a protocol/communication failure**: the saved log shows a
complete, successful "Checking Multiple ESC" cycle — all 4 ESCs connected, Setup block read,
activation status read (all `Activated OK`), device-info read — run **twice** in full, ending
cleanly at `Disconnect FlightCtrl:` with zero errors logged anywhere. The crash produced no log
output at all (an uncaught exception bypasses the app's own logger), so it happened strictly in UI
code, after the protocol work was already done successfully. **Likely cause (not confirmed)**:
`BLHeli32_HexFiles/` had no file matching the `Furling32` layout name (only an
`Aikon_AK32_4IN1_35A_6S_V1_0` file was ever added — see "Local firmware loading" in Activation &
Licensing) — the dropdown-population code plausibly hits a nil object when it finds zero matching
local firmware for ESC#2-4's layout.

## Third real hardware unit: FOXEER Reaper4IN1 F4 65A (2026-09-05) — crash confirmed reproducible

A third, unrelated aircraft/ESC family — `FOXEER_Reaper4IN1_F4_65A_128`, Rev 32.10, `BLHeli32
Bootloader m` (a different bootloader letter than the AK32/Furling32's `h`). **Correction
(2026-09-08, see below): the "F4" in the model name is NOT the MCU family** — the real MCU,
confirmed live via `extract_identity_strings()`, is `AT32F421` (Artery Technology), not an STM32 at
all. The guess below was wrong; kept, not deleted, per this project's own knowledge-retention
standard. Real status check saved verbatim:
[Suite-Check-FoxeerReaper.txt](Suite-Check-FoxeerReaper.txt) — ESC#1 MASTER + ESC#2-4 SLAVE
(2 and 4 reversed, not 3 — a different direction pattern than the AK32/Furling32's uniform
1,2,2,1-style layout), all 4 channels healthy (1.35M+ good DShot frames each, zero bad). A fresh
`.ixi` was also saved:
[BLHeli32_FOXEER_Reaper4IN1_F4_65A_128 - Rev. 32.10 - Multi_260905.ixi](BLHeli32_FOXEER_Reaper4IN1_F4_65A_128%20-%20Rev.%2032.10%20-%20Multi_260905.ixi) —
a third real ESC family and firmware revision for the still-not-done cross-version Setup-block
field validation (see `PLAN.md` backlog).

**The same Flash-tab crash reproduced, exact same address**: `Access violation at address
0000000000A34A7B, accessing address 0000000000000000` — byte-for-byte identical crash address to
the Furling32 case above, on a completely unrelated ESC family/bootloader/board. **This confirms
the crash is a deterministic, general bug in the app's dropdown-population code, not something
specific to either board.** Saved debug log
([5inch-foxeerf722v4+reaper.-ESC.xlg](5inch-foxeerf722v4%2Breaper.-ESC.xlg), user's own
aircraft-based naming) shows the identical pattern as Furling32: all 4 ESCs enumerated
successfully (`grep -c "New target ESC"` = 4), zero errors logged, log ends cleanly — the crash
happens strictly in UI code after protocol work already succeeded, and (both times) with no local
`.Hex` file in `BLHeli32_HexFiles/` matching the connected ESC's layout name. **The "add a matching
local test-firmware file first" hypothesis from the Furling32 finding above is now the leading
explanation, strengthened by this second identical reproduction — still not directly tested** (no
`FOXEER_Reaper4IN1_F4_65A_128`-layout file was added before this attempt either).

### A second, damaged unit of the same model — MCU identified, full raw-byte cross-validation (2026-09-08)

A different physical Reaper 4-in-1 (same layout, `FOXEER_Reaper4IN1_F4_65A_128`), known damaged —
user doesn't recall which motor power-train is burnt. Bench-tested safely: continuous DC power via
a low-amp AC/DC wall adapter at 9.5V (not LiPo), not soldered to motors. Connected to a FoxeerF722v4
FC running EmuFlight, `/dev/ttyACM0`. **All 4 channels fully readable** — config/communication side
is intact regardless of where the physical damage is, consistent with damage isolated to the
power/motor-drive stage, not the MCU or signal path. Real app confirmed all 4 healthy (10.3M+ good
DShot frames each, single-digit bad frames — noise, not a real fault): `[MASTER]`/`[SLAVE]` pattern
and Motor Direction `Normal/Reversed/Normal/Reversed` (ESC#2/#4 reversed) — matches the *existing*
Reaper's known 1,2,1,2-style direction pattern exactly, consistent given it's the same board design.
Exact firmware: `Eep_FW_Sub_Revision=100` → **32.10.0** (previously only known generically as
"32.10"). Real `.ixi`, debug log, and app screenshot saved:
[Damaged_BLHeli32_FOXEER_Reaper4IN1_F4_65A_128 - Rev. 32.10 - Multi_260908.ixi](Damaged_BLHeli32_FOXEER_Reaper4IN1_F4_65A_128%20-%20Rev.%2032.10%20-%20Multi_260908.ixi),
[...Log.xlg](Damaged_BLHeli32_FOXEER_Reaper4IN1_F4_65A_128%20-%20Rev.%2032.10%20-%20Multi_260908.Log.xlg),
[Damaged_2026-09-08_090705.png](Damaged_2026-09-08_090705.png).

**MCU confirmed via `extract_identity_strings()`, live**: `AT32F421` — **a third distinct silicon
vendor for BLHeli_32** (Artery Technology, after ST's STM32 on AK32 and GigaDevice's GD32 on
Furling32/Furling32_4in1_C). The "F4" in this model's name is unrelated to the MCU family — see the
correction above. Also confirmed from the saved debug log: device signature `$1506`, flash size
`$8000` (32KB), bootloader `"m" #109` — and `Activation: Activated OK` logged for all 4 ESCs.

**Full raw-byte cross-validation, completing part of the `PLAN.md` follow-up** (previously only
`.ixi`-decoded values existed for this board, never raw Setup-block bytes): read all 4 ESCs via
`dump-config --raw-dir dumps`, decoded with the same `CONFIRMED_FIELDS` table validated on AK32 and
Furling32. **Every one of the 27 confirmed fields decoded correctly on this third MCU vendor too**
— every value present in the real `.ixi` matched exactly (`Direction`, `Rampup_Pwr`, `Comm_Timing`,
`Demag_Comp`, `Ppm_Min/Center/Max_Throttle`, `Enable_Throttle_Cal`, `Temp_Prot_Enable`,
`Enable_Power_Prot`, `Brake_On_Stop`, `Beep_Strength`, `Beacon_Strength`, `Beacon_Delay`,
`Max_Acceleration`, `Nondamped_Mode`, `Note_Config`, `Sine_Mode`, `Auto_Tlm_Mode`, `Stall_Prot`,
`Pwm_Freq`/`Pwm_Frequency_Lo`, `SBUS_Channel`), and every field this board's `.ixi` omits entirely
(`Volt_Prot`, `Curr_Prot`, `Curr_Sense_Cal`, `LED_Control`, `SPORT_Physical_ID` — no
voltage/current-sense hardware, no LEDs, no S.PORT) decoded to the same sentinel pattern already
seen on AK32 (`255`, or `100` for `Curr_Sense_Cal`'s zero-point). This is now 3 of 3 independently
tested MCU vendors matching this offset map exactly — strong evidence it's a general BLHeli_32
fact, not coincidence.

**Refinement to `Eep_Pgm_Max_Acceleration`'s encoding**: this board's real app UI shows "Maximum
Acceleration: **Maximum**" for the raw value `0` — not "0%". The `raw/10 = %/ms` scaling confirmed
earlier (Furling32, `58` → "5.8% per ms") still holds for non-zero values; `0` itself is very
likely a distinct "unrestricted/no limit" sentinel rather than a literal 0%-per-ms limit (which
would nonsensically forbid all acceleration). Not re-tested with a differential change to fully
confirm the boundary, but the semantic reading is unambiguous from the UI label alone.

No new field names on this board from the initial 27-field pass — its full field set is a subset
of the 46 already catalogued across AK32 and Furling32. One new confirmed *value*, though:
`Eep_Note_Config=255` displays as "Music Off" in the real app (this board has an empty
`Eep_Note_Array`) — not previously observed, since both AK32 and Furling32 had actual melodies
configured.

**PWM Frequency High confirmed via real differential test, same session**: changed "PWM Frequency
High" from 128 kHz to 48 kHz on ESC1 (motor_index 0) via the real app's ESC Setup tab, Write
Setup, diffed the raw plaintext against a pre-change backup — exactly one byte changed: **offset
34, `128`→`48`**. This is `Eep_Pgm_Pwm_Frequency_Hi`, a genuinely new offset not previously
located (paired with `Eep_Pgm_Pwm_Frequency_Lo`, the 32.9+ name for the already-confirmed offset 5
— see [Setup Block Fields](setup-block-fields.md)).

**12 more fields confirmed, same session, via a new third method — cross-board value
correlation**: with all 3 real boards' raw plaintext AND `.ixi` values on hand (AK32, Furling32,
this Reaper), searched every offset 0-191 for a byte pattern matching each remaining unconfirmed
field's per-board `.ixi` value simultaneously across all 3 boards — no new hardware interaction
needed. Resolved `Eep_FW_Main_Revision` (offset 0), `Eep_FW_Sub_Revision` (1), `Eep_Layout_Revision`
(2), `Eep_Hw_Voltage_Sense_Capable` (48), `Eep_Hw_Current_Sense_Capable` (49),
`Eep_Hw_LED_Capable_0/1/2/3` (50-53), `Eep_Hw_Pwm_Freq_Min/Max` (54/55), `Eep_SPORT_Capable` (62),
`Eep_Nondamped_Capable` (63) — 7 via a unique unambiguous 3-way match, 6 more via elimination
against already-confirmed offsets plus sequential-position consistency with the real `.ixi`'s own
field order. Full method and confidence breakdown in [Setup Block
Fields](setup-block-fields.md#method--12-more-fields-via-cross-board-value-correlation-2026-09-08).

**`Eep_ESC_Mode` (value `2` on all 3 boards) could not be located** — the byte value `2` does not
appear anywhere in this board's 192-byte plaintext, suggesting it may not be a directly-stored
byte at all. Left unconfirmed.

This closes the field-name-confirmation effort to only 3 genuinely remaining names:
`Eep_Note_Array`, `Eep_ESC_Layout`, `Eep_ESC_Mode` — 43 of 46 known `.ixi` field names now
confirmed.

**`Eep_ESC_Layout` and `Eep_Note_Array` closed too, same day, via this project's own research
corpus**: re-reading `research/notes/BLHeliSuite32-Reverse3.en.md` (a real disassembly of the
vendor's own binary, done in 2021 and already translated into this repo) turned up a fixed
wire-format offset table straight from the vendor's own code — `Eep_ESC_Layout` at offset 64 (32
bytes) and `Eep_Note_Array` at offset 144 (48 bytes) — a lead not previously connected to this
project's own empirical offset-hunting. No new hardware interaction needed: cross-checked directly
against raw plaintext already captured from all 3 boards (AK32, Furling32, this Reaper).
`Eep_ESC_Layout` matched each board's own real `.ixi` value byte-exact in all 3 cases.
`Eep_Note_Array`'s actual note *encoding* (not just the offset) was derived from scratch and
verified against 2 distinct real Furling32 melodies (74 total note instances) plus AK32's melody
plus this Reaper's empty state — every one matched its board's own `.ixi` text byte-for-byte. At
this point one piece (duration index 2, "half note") was still inferred by pattern rather than
seen in a real capture — closed next, same day, see below.

**`Eep_Note_Array`'s encoding fully closed, same day**: the vendor app's own Music Editor has a
tooltip documenting its exact script syntax — a detail not in the manual or this project's
research corpus. It revealed pauses support 8 lengths (1/1 through 1/128), wider than notes' 4.
Typed the exact script `C42 P1 P2 P4 P8 P16 P32 P64 P128` into this Reaper's ESC1, Write Setup,
read back
([`dumps/esc0-setup-20260908-103942.bin`](../../dumps/esc0-setup-20260908-103942.bin)). All 9
tokens matched exactly — confirmed the previously-untested half-note duration and derived the
extended-pause encoding (a pitch-code acting as a x16 scale bit). Nothing about this field's
encoding remains inferred. Full formula in [Setup Block
Fields](setup-block-fields.md#method--eep_esc_layout-and-eep_note_array-closed-via-this-projects-own-research-corpus-2026-09-08).

**45 of 46 known `.ixi` field names now confirmed — only `Eep_ESC_Mode` remains, and that gap is
genuinely exhausted** (checked against every available technique — see [Setup Block
Fields](setup-block-fields.md#whats-not-decoded-and-why)), not just deferred.

**Fourth reproduction (2026-09-05)**: a fourth aircraft, `Furling32_4in1_C - Rev. 32.9`, bootloader
`k` (a third distinct bootloader letter, after `h` and `m`) — same exact crash address again.
Status check saved: [Suite-Check-Furling32-4in1-C.txt](Suite-Check-Furling32-4in1-C.txt) (this
board had minor real telemetry noise, 6-8 bad DShot frames per channel out of ~6300 — unrelated to
the crash). Fresh `.ixi`:
[BLHeli32_Furling32_4in1_C - Rev. 32.9 - Multi_260905.ixi](BLHeli32_Furling32_4in1_C%20-%20Rev.%2032.9%20-%20Multi_260905.ixi).
Debug log ([apexf7+apexESC.xlg](apexf7%2BapexESC.xlg)) shows the same clean pattern — all channels
enumerated, zero logged errors, crash unlogged. Four for four now, three unrelated ESC
families/bootloaders.

**ROOT CAUSE CONFIRMED (2026-09-05)**: copied the exact matching test-firmware files —
`Furling32_Multi_32_95.Hex`, `Furling32_4in1_C_Multi_32_95.Hex`,
`FOXEER_Reaper4IN1_F4_65A_128_Multi_32_95.Hex` (all from `32.9.5_testcode/`) — into
`BLHeli32_HexFiles/` alongside the AK32 file already there, then reconnected the Furling32 board
(plain layout) again. **Crash stopped, all 4 ESCs populated correctly in the Flash tab.** This
confirms definitively: the access violation happens specifically when zero local `.Hex` files
match the connected ESC's layout name — the app's dropdown-population code has a real bug (almost
certainly a nil-object dereference) for that case, present across at least 3 different ESC
layouts/bootloaders. **Fix for any future board**: always add a matching local `.Hex` file to
`BLHeli32_HexFiles/` for the specific connected ESC layout *before* opening the Flash tab.

**Furling32_4in1_C's MCU confirmed (2026-09-06): GD32F350x6, not STM32.** Read live from the
Setup block's `ESC_CPU` field (offset `0x60`): `#BLHeli_32*GD32F350x6#` — a GigaDevice chip, the
first non-ST silicon confirmed in this project (AK32 and Furling32 are both STM32F051x6). Real
firmware is 32.9.0. `dump-firmware` against the closest available candidate (32.9.5, with
32.8.3/32.7.4 as fallback) confirmed **44.8%** of the app-code region (10,656/23,808 bytes) —
between Furling32's 98.8% (exact version match available) and AK32's 5% (no close version
available at all). Consistent with the user's "point-release drift" hypothesis: a firmware line's
later patches can accumulate changes toward the *next* major version, making them less similar to
their own line's earlier patches than the version numbers alone would suggest. Saved:
`dumps/BLHeli32_Furling32_4in1_C - Rev. 32.9.5 - AppCode_260906.bin`/`.hex`.

**Damaged Reaper (32.10.0), 2026-09-08**: `dump-firmware` against the only available candidate
(`FOXEER_Reaper4IN1_F4_65A_128_Multi_32_95.Hex`, 32.9.5 — no 32.10 test-firmware file exists in the
archive, this exact layout's most recent one point-release behind the real 32.10.0 on the board)
confirmed only **9.4%** of the app-code region (2,240/23,808 bytes) —
[`dumps/reaper-32.10-vs-32.9.5-candidate.bin`](../../dumps/reaper-32.10-vs-32.9.5-candidate.bin).
Lower than Furling32_4in1_C's 44.8% one-point-release gap, consistent with the same "point-release
drift" pattern but evidently steeper for this particular layout/version jump — not yet explained
further. **2,450 unresolved chunks remain (21,568 bytes, ~91% of the image)** — divergence starts
immediately at `0x2400` and only 1-byte matching runs survive past roughly `0x74d8` onward, meaning
most of this board's actual app code differs meaningfully from the 32.9.5 candidate.

## Goal 2 brute-force feasibility — `--discover-unresolved`, real numbers (2026-09-08)

With 21,568 bytes unresolved on the damaged Reaper (above), measured the real cost of
`cmd_DeviceVerify`-based brute-forcing (`fw.discover_byte()`, up to 256 guesses/byte, no
write/erase risk — see "The verify-oracle exploration" below) instead of guessing at feasibility.

**Real per-call latency, measured directly**: 3 individual `verify_flash()` calls (2 known
mismatches at `0x2400`, 1 probe at the info-page address `0x7c00`) each took **0.060s**. Scaling to
the full 21,568-byte gap: **worst case ~92 hours (3.8 days)**, **average case ~46 hours (1.9 days)**
of continuous round-trips, assuming the correct byte value is uniformly distributed 0-255. Multi-day,
not multi-week — more tractable than the initial impression, but still a real commitment, and not
yet attempted at that scale.

**A real robustness gap found while measuring this**: an earlier attempt to time a small 32-byte
sample via `dump-firmware --discover-unresolved` was wrapped in a 5-minute `timeout` for
safety — it never completed even one byte's 256-guess search in that time (implying, wrongly, a
~1s+/call cost). Root cause, confirmed after the fact: `timeout`'s `SIGTERM` killed the process
mid-4-way-if-session, before it could call `exit_interface()` — this left the flight controller's
own MSP passthrough state stuck. Every subsequent `enter_4way_if()` attempt (fresh process, fresh
`SerialTransport`) got zero reply, even after 3 retries. **The only recovery found: physically
unplug and replug the FC's USB cable** (the ESC's own separate DC power did not need to be
touched) — after that, `enter_4way_if()`/`connect_esc()` succeeded immediately and the real
0.060s/call figure above was measured cleanly.

**Practical implication for any real multi-day brute-force run (superseded below)**: the CLI had no
checkpoint/resume support and no signal handling to cleanly exit the 4-way-if session on
interruption. Both were implemented and confirmed working the same day — see "Checkpoint/resume
implemented and confirmed working" below. **But the same testing pass also found a far more
important problem: the brute-force technique itself is unsound as designed — see "CRITICAL:
`cmd_DeviceVerify` is unreliable below 8 bytes / when misaligned" immediately below, which
supersedes the "~2-4 days, feasible" framing above.**

## CRITICAL: `cmd_DeviceVerify` is unreliable below 8 bytes / when misaligned (2026-09-08)

While testing the newly-added `--checkpoint` resume support (see below) against the damaged
Reaper, every single byte brute-forced came back `UNDISCOVERABLE` — 18 for 18, across two widely
separated regions (`0x74d8`-`0x74e7`, `0x2410`-`0x2411`). That's far too systematic to be 18
independent hardware anomalies. Investigated directly instead of accepting it:

- `fw.verify_flash(transport, 0x240f, bytes([0x19]))` returned **`False`** even though `0x19` is
  the confirmed-correct byte at that address (part of a 16-byte chunk that verifies `True` as a
  whole). Reproduced 3 times in a row, same session — not a one-off glitch.
- Systematically swept every offset in a known-good 16-byte window (`0x2408`-`0x2417`, candidate
  bytes confirmed correct via a whole-chunk verify): **only offset 0 (`0x2408`, the 8-byte-aligned
  start) succeeded with a 1-byte verify. Every other offset (`0x2409`-`0x2417`) failed, using the
  objectively correct byte value.**
- Ruled out state/ordering: verifying `0x2409` as the literal first call of a brand-new session
  (no preceding call at all) still returned `False`.
- By contrast, an *aligned, ≥8-byte* verify call using real content always works correctly —
  already proven by the original scan's successful whole-page/32-byte/8-byte matches, and
  reconfirmed directly here (`0x2400+8` and `0x2408+8`, both `True` with real content).
- Separately (same session): `fw.read_flash()` at the unprotected info-page address (`0x7c00`)
  also failed outright at length 1, 2, and 4 (`ACK_D_GENERAL_ERROR`), succeeding only at length 8+.
  So both `cmd_DeviceRead` and `cmd_DeviceVerify` share a minimum-length-8 requirement — but Verify
  additionally showed the alignment-dependent single-byte failure above, which Read wasn't tested
  for (Read is blocked entirely below `0x7c00` regardless of length, so this couldn't be isolated
  the same way in the protected region).

**Root cause not identified** — this needs more hardware time than a feasibility check justifies.
Plausible directions, none confirmed: an internal comparison window narrower than requested that
isn't being filled the way this project's code assumes; a bootloader-side bug specific to
sub-8-byte or misaligned Verify requests; something specific to being near a real content
divergence (the one region tested where 1-byte-aligned-at-offset-0 *did* work, `0x2000`-`0x2010`,
has no real mismatch nearby at all).

**Direct consequence: `discover_byte()`'s design (1-byte guesses) is unsound wherever it's actually
needed** — every genuinely-unresolved address is, by definition, inside a region with a real
mismatch, exactly the condition under which 1-byte verify was shown to fail even for the correct
answer. **The "18 undiscoverable bytes" found this session are very likely a tool bug, not 18 real
hardware anomalies** — do not treat them as confirmed unrecoverable. The `~2-4 days, feasible`
brute-force estimate above assumed `discover_byte()` would actually find a match when the guess is
right; that assumption is now known false for any address abutting a real divergence.

**What still works, and what a fix would need**: full-length (≥8 bytes), 8-byte-aligned verify
calls are confirmed reliable with real content. A corrected brute-force would need to guess in
8-byte-aligned windows, holding already-known bytes fixed and sweeping only the genuinely unknown
position(s). This is cheap (256 guesses, same cost as today) when exactly one byte in an aligned
window is unknown — but this project's own data already contains long runs of *multiple*
consecutive unknown bytes in the same aligned window (the 16-byte run at `0x74d8`-`0x74e7` spans
two fully-unknown 8-byte windows). Brute-forcing a window with `k` simultaneously-unknown bytes
costs `256^k` guesses — trivial at `k=1`, already impractical at `k=2` (65,536), and utterly
infeasible at `k=8` (`256^8` ≈ 1.8×10^19).

**Two corrections to the "18 undiscoverable bytes" claim above, found while double-checking it
properly:**

- **`0x74d8`-`0x74e7` never had a real byte to guess against in the first place**: the 32.9.5
  candidate file has **no data at all** for any address `0x74d8` and above (confirmed:
  `hexfile.parse_intel_hex(...)` has no key past `0x74d0`-ish; max candidate address is `0x7cff`
  but with real gaps before it). `_verify_region`'s own docstring already distinguishes this case
  ("a gap", zero-cost, no hardware call) from a genuine content mismatch — this region was always a
  gap, not 16 verified hardware anomalies. Brute-forcing it blind (no candidate-informed starting
  point at all) was never a meaningful test of the Verify oracle's reliability; the `0x240f`/
  `0x2408`-`0x2417` findings above (which DO have real candidate data) are the ones that actually
  demonstrate the bug.
- **`0x2410`-`0x2411`'s "unresolved" status was itself a false positive from this same bug, not a
  real mismatch.** It came from an earlier ad-hoc test using a bare 2-byte `--start 0x2410 --end
  0x2412` range — itself shorter than the reliable 8-byte minimum. Re-tested properly with a real
  aligned 8-byte verify (`fw.verify_flash(transport, 0x2410, <candidate's real 8 bytes>)`):
  **returned `True` — the whole window matches the candidate exactly.** This means `_verify_region`
  (used by every `dump-firmware` invocation, not just `--discover-unresolved`) can itself issue an
  unreliable sub-8-byte verify call whenever a caller's `--start`/`--end` range (or a remaining gap
  between them) is narrower than 8 bytes — a latent correctness gap in the tool generally, not just
  the brute-force feature. **Not yet fixed** — `_verify_region` has no guard against this today.
  Anyone re-running `dump-firmware` with a small custom `--start`/`--end` window should treat a
  reported mismatch there as unconfirmed until re-checked with a real ≥8-byte-aligned request.

**Fixed the same day**: `fw.discover_window()` replaces `discover_byte()`'s design — guesses within
a real, reliable 8-byte-aligned window instead of a bare byte, taking `known` values for already-
resolved offsets and a list of `unknown_offsets` to sweep combinatorially (`itertools.product`,
`256^len(unknown_offsets)` calls). `dump-firmware --discover-unresolved` now groups unresolved
bytes into their containing 8-byte windows and calls this instead; a new `--max-combo` flag (default
1) skips any window needing more simultaneous guesses than that, so a `k=8` window like the (now
understood to be a gap, not urgent) `0x74d8` region is correctly skipped rather than falsely
reported `UNDISCOVERABLE`. Unit-tested (`tests/test_fourwayif.py`) against a fake transport for the
k=1 and k=2 cases, the no-match case, and both input-validation errors.

**Validated against real hardware the same day, with a sobering result.** Bisected two of the
Reaper's real 32-byte "unresolved" chunks (`0x2400+32`, `0x2420+32`) down to the actual
mismatching 8-byte sub-window using real ≥8-byte-aligned verify calls (reliable, per the fix
above): `0x2400+32`'s real divergence lives entirely in `0x2418`-`0x241f` (the other 24 bytes of
that chunk, including `0x2410`-`0x2417`, fully match the candidate); `0x2420+32`'s lives entirely
in `0x2430`-`0x2437`. For each of these 2 real mismatching windows, tested all 8
"exactly this one position differs, the other 7 match candidate" hypotheses via
`discover_window()` with k=1 (256 guesses each, real 8-byte-aligned calls) — **all 16 hypotheses
(8 per window, 2 windows) came back with no match.** Every window with a confirmed real mismatch
tested so far has 2+ simultaneously-different bytes, not one isolated byte.

**This validates `discover_window()`'s correctness** (clean, consistent `None` results across 16
real exhaustive single-position searches — no false positives, no crashes, `exit_interface()` ran
cleanly every time) but **reveals a new, more fundamental feasibility problem than the byte-length
bug**: real content differences between two firmware *versions* likely cluster in multi-byte groups
(a changed instruction, an updated constant, a shifted reference) rather than isolated single
bytes — the opposite of what byte-by-byte brute-forcing assumes. With `--max-combo` capped at a
practical value (1 or 2), a real cross-version gap may turn out to be mostly unrecoverable via this
oracle regardless of the length/alignment fix, unless a much closer candidate is available (as with
Furling32's 98.8% match when an exact-version file existed) so there's little gap left to
brute-force in the first place. Not yet tried: `--max-combo 2` against either of these 2 confirmed
windows (65,536 guesses, ~1 hour each at the measured rate) — would confirm whether they're
genuinely 2-byte differences or something larger.

**Follow-up same day, k=1 now 3-for-3 real failures, plus a real structural finding**: rapidly
bisected 10 more real 32-byte unresolved chunks (candidate-compare only, ~0.06s/call, no brute
force — under a minute total for all 10) to find their true mismatching sub-window(s):
`0x2440+32` and `0x2820+32` each have 2 separate mismatching 8-byte windows; `0x2840+32` has
exactly one, cleanly isolated, at `0x2858`; **`0x2860+32` through `0x2920+32` (6 consecutive
chunks, ~216 bytes) mismatch in all 4 sub-windows each** — a large contiguous divergent span, not
scattered differences, consistent with a real code insertion/relocation between firmware versions
cascading into everything downstream. Ran the same k=1 single-position sweep against the newly
isolated `0x2858` window: **all 8 hypotheses failed again** — 3 for 3 real isolated windows now
confirmed to have 2+ simultaneous differences, strengthening the "real diffs cluster, not
isolated" finding above. `0x2858`'s exact divergence (2+ bytes, not yet which ones) remains
unresolved; a real next step would be `--max-combo 2` against `0x2858` specifically, since it's a
genuinely clean single 8-byte window (unlike the earlier two, which sit inside larger, messier
mismatch regions).

**Also confirmed (2026-09-08, unrelated to the above): a full power cycle (both FC USB and ESC's
separate DC power) recovers a wedged FC state that a USB-only replug did not.** Symptom was
different from the earlier stuck-passthrough case too: consistently a 3-byte reply instead of the
expected 5-byte MSP header (reproduced 3x), and the FC had already silently re-enumerated to a
different `/dev/ttyACM` number on its own before this was even noticed — suggesting a genuine
firmware-level wedge, not just a leftover passthrough flag. A full power cycle fixed it
immediately.

## Checkpoint/resume implemented and confirmed working (2026-09-08)

`dump-firmware --discover-unresolved` gained a `--checkpoint FILE` option: appends one line per
resolved byte (`<addr> <value>` or `<addr> UNDISCOVERABLE`), fsync'd immediately, and loads
existing entries on startup to skip already-known addresses. `SIGTERM` is now caught and converted
to the same `KeyboardInterrupt` `Ctrl-C` already raised, so the existing `finally` block (which
calls `exit_interface()`) runs on either — directly fixing the stuck-FC-passthrough gap found
earlier this session.

**Confirmed working end-to-end on real hardware**: started a small brute-force run, let it discover
one byte, sent `SIGTERM` mid-run — the process printed a clean "Interrupted" message, exited 0x0f
gracefully from `exit_interface()` (a normal warning, not a crash), and the checkpoint file had the
one completed byte. Resumed with the same `--checkpoint` path: **no physical USB replug was
needed** (confirming the SIGTERM fix works), the already-checkpointed byte was skipped with no
round-trip, and the run continued correctly. This part of the fix is solid, independent of the
Verify-reliability problem found in the same testing pass above.

## Real brute-force campaign attempt on the damaged Reaper (2026-09-09)

Attempted a real, hours-long `dump-firmware --discover-unresolved` run against the full remaining
gap, with two real problems found and fixed along the way — recorded here so neither repeats.

**`--max-combo 2`'s real cost was underestimated by ~30x.** The hypothesis-mode design (see
above) tries every `C(8,k)` combination of positions for a given `k`, each up to 256 guesses — for
`k=2` that's `C(8,2)=28` combinations × up to 65,536 guesses each = **up to 1,835,008 guesses
(~30 hours) to exhaust one window**, not the "~65,536 guesses, ~1 hour" figure this project
originally estimated (conflating "one combination's cost" with "the whole k-level's cost"). Worse,
the time-budget check inside the hypothesis loop only fired once per `k`-level, not between the 28
combination attempts within `k=2` — so a single unlucky window could consume the entire session
budget with no way to move on or stop cleanly. **Confirmed live**: a real `--max-combo 2` run spent
100 minutes stuck on the very first mismatching window (`0x2430`) with zero checkpoint entries
written and zero broader progress. **Fixed same day**: the time-budget check now runs before every
single combination attempt, not just once per `k`-level.

**A separate, unrelated crash**: opening EmuFlight Configurator against the same FC mid-run raised
an uncaught `serial.SerialException` that killed the process outright — see the port-contention
quirk entry above for the full account and the still-open follow-up (catching this exception class
too).

**Net result this session**: after the above, re-ran with `--max-combo 1` (cheap, ~15-25s/window,
broad coverage) for the remaining time before the session had to end. Confirmed 2,376/23,808 bytes
(10.0%) via the phase-1 candidate scan, narrowing the real gap to 4,282 distinct 8-byte windows
(vs. the earlier 2,450 32-byte-granularity chunks — this project now has the actual window-level
shape of the gap, not just a coarse chunk count). Only 2 windows were fully brute-force-tested
before the session ended: `0x2418` and `0x2430`, both already known (see above) — k=1 hypothesis
search exhausted, confirming they need k≥2 to resolve, consistent with everything else found. A
full `--max-combo 1` sweep of all 4,282 windows, then `--max-combo 2` targeted at whichever windows
that leaves, is the natural next session's starting point — `dumps/reaper-campaign-260909-k1.checkpoint`
carries the 2 confirmed results forward.

**New resource, not yet evaluated**: the user found [OpenOCD](https://openocd.org/) (open-source
on-chip debugger, JTAG/SWD, works with ST-Link/J-Link/CMSIS-DAP probes) as a general lead for the
SWD-based path Goal 2/Goal 3 already require. This doesn't change the confirmed "physical
soldering + a real debug probe is required regardless" finding (OpenOCD is software, not a way
around needing physical SWD access) — but it's the concrete, standard tool that would actually
drive flash-read/RDP-clear operations once that hardware step is taken, replacing the vaguer "a
3-piece ST-Link V2 clone debugger set" placeholder already noted in the backlog. Not evaluated
against this project's specific chips (STM32F051x6, GD32F350x6, AT32F421) — a real next step if
the soldering/physical-access trade-off is ever explicitly accepted.

## `write_flash()` without erase-first corrupts far more than the targeted bytes (2026-09-07)

**First real write to hardware via this project's own `write_flash()`.** Test: change
`Eep_Pgm_Pwm_Freq` (Setup block, plaintext offset 5) from 48 to 24 on AK32 motor 0 (ESC1), writing
only the single 8-byte ciphertext block covering that offset, deliberately **without erasing
first** — the intended test of whether erase-before-write is required. Full raw output, exact
field-by-field before/after comparison:
[ak32-motor0-writetest-260907.txt](ak32-motor0-writetest-260907.txt).

**The targeted byte wrote correctly** (`Eep_Pgm_Pwm_Freq` read back as 24, confirmed via this
project's own decrypt), but **8 other confirmed fields outside the written 8 bytes were also
clobbered** to erased-flash sentinel values (`Eep_Pgm_Comm_Timing`, `Demag_Comp`,
`Ppm_Min/Center/Max_Throttle`, `Enable_Throttle_Cal`, `Temp_Prot_Enable`, `Beep_Strength`,
`Beacon_Strength`, `Beacon_Delay` — all now `255`/`65535`/`0` instead of their real prior values).
**Root cause (inferred, not directly confirmed)**: the MCU/bootloader's write path silently erases
a region larger than the 8 bytes requested (likely a full flash page) before programming — directly
contradicting the assumption that a small `cmd_DeviceWrite` only touches the bytes it's given.

**Independently confirmed by the real app**: opening `BLHeliSuite32xl` afterward (same AK32, same
connection) showed ESC#1 as `***[INVALID]**` (ESC#2-4 unaffected, normal), with a built-in dialog:
"Now the memory content is most likely corrupted, so do not try to use this ESC. Do you want to try
to flash ESC#1 again with BLHeli, to remedy the failure?" — the app has its own repair-via-reflash
workflow for exactly this failure mode. The literal `***INVALID***` string the app displays matches
byte-for-byte a string found in this project's own raw plaintext readback — confirms this project's
read path reflects genuine device memory, not a decode artifact. DShot communication with ESC1 still
worked normally (1.14M+ good frames, zero bad) — only the Setup/config block is affected, not the
running application firmware or motor control.

**Practical implications**:
- Answers the original "does config-area write need erase-first?" question empirically: **yes** —
  and the failure mode when skipped is not a clean no-op or a single-byte miss, it's collateral
  corruption of a much larger region.
- This project's own tooling cannot fully repair this: the confirmed byte-offset map (see
  [Setup Block Fields](setup-block-fields.md)) only covers plaintext offsets 0-23, but the erased
  region extends across the whole 192-byte plaintext (verified: legible strings like
  `Aikon_AK32_4IN1_35A_6S_V1_0` and `BLHeli_32*STM32F051x6` persist further out, meaning the erase
  didn't wipe literally everything, but the fields this project can decode/restore are limited to
  that 24-byte range regardless). The real app's own "flash again to remedy" repair path is the
  safer recovery route — it has complete internal knowledge of the true struct layout.
- `write_flash()`'s docstring updated accordingly (see `protocol/fourwayif.py`) — no longer just
  "not yet confirmed", now documents this specific confirmed failure mode.

**Status: repaired, confirmed working.** BLHeliSuite32xl's own "flash again to remedy" dialog
failed with "cannot access server" — expected: no local approval server was running this session,
so the `/etc/hosts` redirect (already in place from an earlier session) sent the request to
localhost with nothing listening, connection refused. Not a deeper protocol failure — no
request/response cycle even occurred.

After that failed attempt, the app reported ESC#2 and ESC#4 (motor indices 1 and 3) as unreachable
too, surviving a full power cycle. **Read-only diagnostic via this project's own tooling (enter
4-way-if + connect_esc fresh per motor) showed all 4 motors connect fine at the protocol level with
identical valid device signatures, and motors 1/2/3's Setup blocks were completely intact,
byte-for-byte matching the known-good baseline.** Only motor 0 (ESC#1) was actually corrupted — the
app's "cannot access" for the other two was a UI-layer symptom, not real hardware/protocol failure,
consistent with the already-documented dropdown-population UI bug pattern above (Furling32/FOXEER
Reaper findings) where one bad ESC's state cascades into the app misreporting others.

**Repair performed**: motors 0-3 on this board share an identical Setup block except
`Eep_Pgm_Direction` (offset 3) — confirmed already in [Setup Block Fields](setup-block-fields.md).
Motor 3's `Direction=1` already matched motor 0's original value, so no field edit was needed: read
motor 3's full 256-byte ciphertext, verified the crypto round-trips it exactly (local check before
touching hardware), then wrote all 256 bytes to motor 0 in a single `cmd_DeviceWrite` frame (vs. the
original 8-byte write that left the rest of the page erased). **Confirmed working**: motor 0's full
192-byte plaintext now reads back byte-for-byte identical to motor 3's, and the real
`BLHeliSuite32xl` app confirms all 4 ESCs healthy again (ESC#1 back to `[MASTER]`, direction pattern
`1,2,2,1` intact, matching original state).

**New finding — supports the unverified "nonce theory" in `cipher/xtea.py`**: the write used
motor 3's real recovered "discarded low-16-bits" per block (not the zero-default), and the local
round-trip check confirmed this reproduced motor 3's exact ciphertext before sending. But after
writing to motor 0 and reading it back, the raw ciphertext differed from motor 3's in nearly every
byte — while the decrypted plaintext remained exactly identical. Since XTEA's block cipher makes
even a 1-bit change in those "discarded" bits cascade into an almost fully different 8-byte
ciphertext block (confirmed avalanche behavior), this strongly suggests **the device regenerates
those discarded bits itself on every write** (a real per-write nonce, counter, or similar) rather
than storing whatever raw value is supplied — new evidence for, not proof of, the nonce theory
`xtea.py` already flags as unverified.

## Firmware-dump blocker: RDP

Mapped the readable address range via `cmd_DeviceRead` against the real ESC. **Refused everywhere
across the actual application firmware** — tested `0x0000`, `0x0800`, `0x1000`, `0x2000`, `0x4000`,
`0x6000`, `0x7000`, `0x7800` (all `ACK_D_GENERAL_ERROR`) — and refused at the very top of flash
(`0xFFF0`). **Only readable**: roughly `0x7C00`–`0xF7BB`, an "info page" holding the Setup block
(`0x7C00`), activation status (`0xEB00`), and device info (`0xF7AC`, decodes to ASCII `W4P496` — a
device-model string; the research corpus's `BF664` example was a *different* ESC, so a different
string here is expected, not a bug).

`cmd_DeviceReadEEprom` returns `ACK_I_INVALID_CMD` for every address tried — this ARM device doesn't
implement EEPROM emulation as a separate memory space at all (an AVR/SimonK-only concept), so it
isn't a second protected channel to explore, just unsupported here.

**Root cause, confirmed by research** (not just inferred from the address map): BLHeli_32 sets the
STM32's hardware **Read-Out Protection (RDP)** fuse — confirmed directly from AM32's own Hacking
Guide ("the BLHeli_32 firmware has enabled the readout protection of the SWD port"). ST's own
UART-bootloader app notes confirm the chip's ROM bootloader refuses both Read and Write Memory
commands whenever RDP is active — enforced in silicon, not just BLHeli_32's application code.

No community-documented method exists to dump BLHeli_32 firmware via UART/bootloader alone; every
method found requires physical SWD wiring plus specialized fault-injection hardware. Most published
attacks target STM32F4. **One F0-family exception exists, unproven/unconfirmed here**: [Lucas
Teske's STM32F0x Protected Firmware Dumper](https://lucasteske.dev/2024/01/stm32f0x-protected-firmware-dumper)
(Jan 2024) — a Raspberry Pi Pico + soldered SWD wires (~$10), racing a flash read against RDP
enforcement on power-on, non-destructive, demonstrated against an STM32F042G6U6. Never attempted
against this ESC's exact chip (STM32F051x6, a different F0 part), against BLHeli_32 firmware
specifically, or by anyone in the RC/drone community as far as this project has found.

**Cross-validated through Betaflight passthrough (2026-09-04)**: same board, all 4 motors, using
the corrected `connect_esc()` retry timing above. `probe-flash --address 0x0000` refused identically
(`cmd_DeviceRead` → `ACK_D_GENERAL_ERROR`) on all 4 channels; `probe-flash --address 0x7C00` (the
readable info page) still succeeded. RDP is a hardware fuse, so this was expected to be
FC-firmware-agnostic — confirms it, doesn't change the "closed, blocked" status of this goal.

## The verify-oracle exploration

`cmd_DeviceVerify` (0x40) is a genuine oracle: submit a candidate buffer, get back `ACK_OK` (match)
or an error ack (mismatch) — confirmed from `BL_VerifyFlash()`'s source, which only sends
`CMD_VERIFY_FLASH_ARM` and checks the ACK, no write/erase command in that path.

**Why this might matter**: RDP protects against *external* debug-port memory access — it does not
prevent the chip's own running code from reading its own flash internally and reporting a
match/mismatch. If BLHeli_32's bootloader implements "verify" as an internal comparison (a normal
feature, used to confirm a flash write succeeded) without re-checking the same address whitelist
"read" enforces, it could in principle leak the protected firmware byte-by-byte without ever
touching real flash content.

**Tested, live, real hardware**:
1. Verify against known-correct bytes at an unprotected address (`0x7C00`) → `ACK_OK`. ✅
2. Verify against deliberately-wrong bytes at the same unprotected address → rejected with
   `ACK_D_GENERAL_ERROR` (0x0F) — notably *not* the more specific `ACK_I_VERIFY_ERROR` (0x04) that
   exists in the response-code table, worth remembering if revisiting this.
3. Verify against an arbitrary guess at a *protected* address (`0x0000`) → same `ACK_D_GENERAL_ERROR`
   (0x0F).

**Result: inconclusive.** Because a genuine mismatch and a protected-address refusal produce the
identical ack code, a single test (or any number of always-wrong guesses) can't distinguish "the
oracle is blocked here too" from "your guess was simply wrong." Resolving this would need either:
guessing at least one byte correctly and seeing whether the response changes at all, or a timing
side-channel (does an early-byte mismatch fail faster than a late-byte one, if the ESC's comparison
loop exits early?) — a substantially bigger undertaking, uncertain to even work over a noisy
USB-serial link, and many more hours of live hardware interaction. **Not pursued further** — this is
where the exploration stopped; revisit only with a clear plan for resolving the ambiguity, and only
with explicit approval given the stakes (the ESC's real, working firmware).

No writes or erases occurred during this exploration — every test used `cmd_DeviceVerify` only, the
FC recovered cleanly after each one.

**Update (2026-09-06) — ambiguity resolved, oracle confirmed live**: a real Flash-tab Verify
attempt on the AK32 (production v32.7 vs. a different test file) showed sequential chunks
`0x2000`–`0x2300` returning genuine `ACK_OK` before diverging at `0x2400` — see
[Protocol Reference](protocol-reference.md) and [Activation & Licensing](activation-licensing.md).
`0x2000` is one of the exact addresses confirmed *blocked* for raw `cmd_DeviceRead` above. A true
match response at a Read-blocked address proves the Verify oracle discriminates match/mismatch
even inside RDP-protected flash — it is not blanket-refusing there the way `0x0000` appeared to.
This resolves the earlier inconclusive verdict (which rested on a single always-wrong guess at
`0x0000`) in favor of "the oracle is live." **Practical implication**: a full firmware dump via
byte-by-byte Verify-guessing is theoretically possible (no write/erase risk, confirmed safe) but
would require up to 256 guesses per byte across the whole image (tens of thousands of round-trips)
— slow, never attempted, and a substantially different undertaking than anything tried so far. The
"closed, blocked" status for Goal 2 (firmware dumps) should be revisited with this in mind, not
treated as settled.

**External data point on bootloader size — raises a question, doesn't settle one**: the AM32
firmware project's own wiki (`am32-firmware/am32-wiki` on GitHub, fetched directly) documents its
own bootloader as occupying the first 4KB of flash (`0x08000000`–`0x08000FFF`), app code starting
at `0x08001000` (27KB reserved on a 32KB MCU). That's half the 8KB (`0x2000`) boundary this project
found empirically for BLHeli32 (every real firmware-update `.Hex` file checked, any
manufacturer/version, starts no earlier than `0x2000`). **AM32 and BLHeli32 are independently
developed** — AM32 replaces BLHeli32 on the same physical hardware but doesn't share source, so
there's no reason its bootloader must be the same size. What this does raise: what's actually in
`0x1000`–`0x1FFF` for a real BLHeli32 ESC — genuinely part of a larger proprietary bootloader, or
something else (e.g. manufacturing-provisioned per-unit data) that firmware-update files simply
never touch for an unrelated reason. Not resolved either way; `dump-firmware`'s Verify oracle
technique could test this at `0x1000`–`0x1FFF` specifically if a genuine need arises.

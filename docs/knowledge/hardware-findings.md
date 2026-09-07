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
Bootloader m` (a different bootloader letter than the AK32/Furling32's `h` — likely a different
STM32 variant, F4-based per the name vs. the others' F051x6). Real status check saved verbatim:
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

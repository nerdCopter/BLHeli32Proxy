# Session Handoff — 2026-09-05 (live proxy test + 4-board crash root-cause, session ending)

Bridge document for the next session — delete once the open items below are resolved or absorbed
into permanent docs.

## Repo state

- Branch: `master`. Last pushed commit: `9205c37` ("fix: add reset-settle delay, document redirect
  port + PWM field split"), pushed to `github.com/nerdCopter/BLHeli32Proxy` (**private**).
  **Uncommitted changes exist on top of that**: a repo-wide documentation restructuring
  (CLAUDE.md reduced to an `@AGENTS.md` import, a new `MENU.md`, a new `testcode/README.md`,
  staleness/PII fixes across `PLAN.md`/`README.md`/`IMPLEMENTATION.md`/`docs/knowledge/`) — not yet
  committed, needs the user's go-ahead.
- **This repo has an explicit exception to the global branch-per-change policy**: commit and push
  directly to `master` here, no feature branches/PRs/worktrees (private single-maintainer project —
  see `feedback_no-branches-this-repo.md` in this project's Claude memory).
- **New reference files added 2026-09-05** (all in `docs/knowledge/`, already committed):
  - `Suite-Check-Furling32.txt`, `Suite-Check-FoxeerReaper.txt`, `Suite-Check-Furling32-4in1-C.txt`
    — real BLHeliSuite32xl status-check output, verbatim, for 3 new boards.
  - `BLHeli32_Furling32 - Rev. 32.9.5 - Multi_260905.ixi`,
    `BLHeli32_FOXEER_Reaper4IN1_F4_65A_128 - Rev. 32.10 - Multi_260905.ixi`,
    `BLHeli32_Furling32_4in1_C - Rev. 32.9 - Multi_260905.ixi` — fresh real `.ixi` ground truth,
    one per new board.
  - `BLHeliSuite32xl-Log-260905.xlg` (AK32), `6inch-stellarh7dev.xlg` (Furling32, user's own
    naming), `5inch-foxeerf722v4+reaper.-ESC.xlg` (FOXEER Reaper), `apexf7+apexESC.xlg`
    (Furling32_4in1_C), `populated-furling.xlg` (Furling32, after the crash fix) — the real app's
    own saved debug logs, custom binary format, readable via `strings -n 4 <file>.xlg`.
- **This machine is a different machine than 2026-09-04's session** (same files, kept in sync
  across machines by a file-sync tool). `.venv` was stale here too (same symptom as the original
  repo-move) — already recreated (`python3 -m venv .venv --clear && .venv/bin/pip install -e ".[dev]"`), works.

## Key finding #1: live proxy test against the real app — CONFIRMED WORKING

Full detail: `docs/knowledge/activation-licensing.md` §"Local firmware loading via the real app —
CONFIRMED not server-gated". Summary:

1. Full redirect chain set up and confirmed working end-to-end against the **real,
   native-Linux `BLHeliSuite32xl`** binary (not just `curl`). **`docs/USAGE.md` §4 is missing a
   step**: a hosts-file redirect alone does not redirect the port — the real app connects to the
   implicit default HTTPS port 443, but this project's server defaults to 8443. Needed:
   `sudo iptables -t nat -A OUTPUT -p tcp -d 127.0.0.1 --dport 443 -j REDIRECT --to-port 8443`.
   **Not yet added to USAGE.md.**
2. Confirmed live: the real app's status-check call (`GET
   /BLHeli32_2017_1/status.php?p=BLHeliSuite32xl&v=1044`) hit this project's approval server
   repeatedly (every "check for updates," every Flash-tab open, every Connect/Read). New confirmed
   detail: **User-Agent: `BLHeliSuite32 URI Client/1.0`**. The empty-body "no update" response is
   confirmed non-fatal (was previously just a guess) — app shows a blank "Following Message
   received:" dialog, then continues normally.
3. **Disproved the working hypothesis that local firmware loading is server-gated.** Real cause:
   `BLHeliSuite32xl/BLHeli32_HexFiles/` (the app's own local firmware-catalog folder) was
   completely empty. Fixed by copying matching `.Hex` files in from `32.9.5_testcode/`.
4. "Verify Selected ESC" tried (safe, non-destructive) on the AK32 — failed as expected (comparing
   currently-flashed v32.7 against a different v32.9.5 test file can never byte-match). The real
   app's own debug log shows this mismatch starts at flash offset `0x2400` exactly — not a
   licensing signal, purely a version-content difference.
5. **The single most important open decision, still unresolved**: "Flash Selected ESC" is one
   click away on multiple boards now — the actual real-flash action Goal 4 needs, and the exact
   firmware-loss risk the standing hard safety constraint gates (a real flash could overwrite a
   board's current known-good firmware, with no way to back it up first since firmware dumps are
   RDP-blocked). **Do not click this without the user explicitly re-confirming the trade-off at
   that moment** — same rule as always, holds for every board tested today too.

## Key finding #2: the real app's debug log (`.xlg` files) — a goldmine

The app has a "Log" tab in its own UI (`ESC Setup | ESC overview | ESC Flash | Motors | Log`),
separate from file-based logging — `Settings/BLHeliSuite32xl.ini`'s `[Log] LogOn=1` alone does
**not** create a file; must manually "Save to file" from that tab. **User convention: each save
gets a distinct filename** — search `BLHeliSuite32xl/*.xlg` for all of them, don't assume a fixed
name. Custom binary format (Delphi/Lazarus length-prefixed strings, `file` reports just "data"),
readable via `strings -n 4 <file>.xlg`. **Do this again after any future real-hardware session.**
Full technical detail folded into `docs/knowledge/protocol-reference.md`; key points:

- **Real app waits 100ms between `cmd_DeviceReset` and `cmd_DeviceInitFlash`, every single
  connect, unconditionally** — not just after a failure. This project's own `connect_esc()`
  (`protocol/fourwayif.py`) doesn't do this — it only waits `retry_delay` (5.5s) *after* a failure,
  reactively. **Concrete, not-yet-applied fix**: add an unconditional `time.sleep(0.1)` between
  the reset and init-flash calls — likely improves first-attempt success rate on top of the
  existing reactive fix.
- **`ReadActivationStat` reads 16 bytes (not 1) at `0xEB00`**, reports literal `Activation:
  Activated OK` — this project's code has never read this address at all. Matches the
  `TActivationStatus` enum found in `TestActivator.exe`'s strings.
- **`cmd_DeviceVerify` confirmed behavior**: sequential 256-byte chunks from `0x2000` upward, stops
  at first mismatch.
- **Zero network activity during Connect/Read/Verify** (cross-checked against the approval-server
  log running in parallel). Narrows where Goal 4's real activation call must be: only possibly
  during an actual flash **write**, never observed.
- Real signature bytes (`06 33 68 04`) and full raw hex frames for every command match this
  project's own already-implemented frame format exactly — independent confirmation of
  byte-correctness.

## Key finding #3: Flash-tab crash — ROOT-CAUSED AND FIXED, closed

Reproduced 4 times across 3 unrelated ESC families/bootloaders (AK32-adjacent `h`, FOXEER Reaper
`m`, Furling32 `k`) — always the exact same `Access violation at address 0000000000A34A7B,
accessing address 0000000000000000`. Debug logs confirmed this is a **UI-layer bug, not a protocol
failure**: every log showed a complete, successful ESC connect/read cycle with zero errors; the
crash itself produced no log output (uncaught exception bypasses the app's logger).

**Root cause confirmed**: happens whenever zero local `.Hex` files in `BLHeli32_HexFiles/` match
the connected ESC's layout name — almost certainly a nil-object dereference in the app's
dropdown-population code. **Fix verified**: copied the exact matching `32.9.5_testcode/*.Hex`
files for the affected layouts into `BLHeli32_HexFiles/` — crash stopped completely, all 4 ESCs
populated correctly on reconnect (`docs/knowledge/populated-furling.xlg` confirms a clean run).
**This is closed — not an open item.** Standing rule for any future new board: always add a
matching local `.Hex` file to `BLHeli32_HexFiles/` *before* opening the Flash tab.

## Other findings (Wine/TestActivator — dead end, deprioritized)

Full detail in `PLAN.md`'s backlog. Short version: the 2026-09-04 Wine `kernel32.dll` failure was
a corrupted prefix, not missing 32-bit support (fixed with a fresh `WINEPREFIX`). Got
`BLHeliSuite32TestActivator.exe` running, but serial connect to a real ESC from inside it never
worked (Wine's serial I/O emulation, not a hardware issue — this project's own tool connects to
the same port instantly). **Not pursued further** — the real native-Linux app test fully
superseded this path to Goal 4.

## Open items, in priority order

1. **The big one**: decide Flash vs. hold on any of the now-staged boards (AK32, Furling32,
   FOXEER Reaper, Furling32_4in1_C all currently have working test-firmware dropdowns). Needs the
   user's explicit go-ahead on the firmware-loss trade-off before ever clicking "Flash Selected
   ESC" — this is the actual next step toward capturing Goal 4's core deliverable (the real
   ESC-activation network call).
2. ~~Add the missing iptables redirect step to `docs/USAGE.md` §4~~ — **done**, plus fixed 2 other
   stale open-question notes in USAGE.md (TLS trust confirmation) while there.
3. ~~Add the unconditional 100ms `cmd_DeviceReset`→`cmd_DeviceInitFlash` wait to `connect_esc()`~~ —
   **done** (`reset_settle_delay=0.1` param, `protocol/fourwayif.py`). **Not yet re-tested against
   real hardware** (no board connected when added) — confirm it measurably helps next session.
4. ~~Commit the 2026-09-04 code changes + today's doc updates~~ — **done**, `e662053`.
5. Cross-version Setup-block field validation — **partially done**: field *names* compared across
   all 4 boards (12/13 identical; `Eep_Pgm_Pwm_Freq` confirmed split into `_Hi`/`_Lo` on firmware
   32.9+ — see `setup-block-fields.md`'s new section). **Byte offsets still not confirmed** on
   non-AK32 firmware — needs a fresh `dump-setup` read via this project's own tool (the app's own
   logs elide the Setup-block payload, `.ixi` files only have decoded values, not raw bytes).
6. Broader `tcpdump -i any -n -s 0 'udp port 53 or tcp port 443'` capture during dropdown
   interaction — requested but never completed; would confirm/rule out a second host for the
   (recalled but unconfirmed) online firmware-catalog behavior from when blheli.org was live. Low
   priority now that local loading is confirmed working via the file-based fix.
7. MadsTech/MadRC "100 boot limit" video claim still unconfirmed (would need the actual video
   transcribed).
8. Cleanup (low priority, harmless to leave): the approval server process and
   `/tmp/approval_server.log` are ephemeral, already gone. The `sudo iptables` rule and
   `/etc/hosts` line added on this machine are still live — remove with `sudo iptables -t nat -D
   OUTPUT -p tcp -d 127.0.0.1 --dport 443 -j REDIRECT --to-port 8443` and by deleting the
   `blheli.org` line from `/etc/hosts`, whenever convenient.

## Next session start

Re-read `docs/knowledge/activation-licensing.md`'s "Local firmware loading" section and
`docs/knowledge/hardware-findings.md`'s crash-fix section, then pick: click "Flash Selected ESC"
on a staged board (with the user's explicit fresh confirmation of the firmware-loss trade-off) to
finally attempt capturing Goal 4's real activation call, or apply the two concrete low-risk fixes
first (iptables doc, 100ms delay) while deciding.

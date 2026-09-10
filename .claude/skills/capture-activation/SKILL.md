---
name: capture-activation
kind: skill
category: hardware
summary: "Goal 4 guided flash-and-capture. Safety-gated — irreversible firmware risk."
description: |
  Guided, safety-gated procedure for the project's core remaining goal: capture the real ESC-activation network call by triggering a real flash through BLHeliSuite32xl. The flash click can overwrite the ESC's firmware with no restore path. Never initiated by the AI; fresh explicit user confirmation required every time.
---

# capture-activation

**Trigger**: "capture the activation call", "do Goal 4", "capture-activation", MENU.md item 6/Goal 4.

Full reference: `PLAN.md` §7 (last item), `docs/USAGE.md` §7a-§7c, `docs/knowledge/activation-licensing.md`.

## The hard gate

- The AI never clicks "Flash Selected ESC" and never tells the user to click it as a step buried in a list.
- A past "go ahead" is never still valid. Get the user's fresh, explicit statement that they accept the firmware-loss trade-off **at the moment the click is about to happen**, every time.
- Firmware dumps are RDP-blocked (`docs/knowledge/hardware-findings.md`) — a bad flash has no restore path.
- Known so far (2026-09): every real flash attempt so far produced NO `cmd_DeviceWrite` and NO new network request — the block looks internal to the app (`TFlashState`), not licensing. Treat a "nothing captured" result as the expected outcome, not a failure.

## Steps

1. **Backup first.** Run `/esc-backup` for the target ESC. Confirm a raw `.bin` landed in `dumps/`.
2. **Proxy up.** Run `/proxy-up`. Confirm the server log shows the `status.php` ping from the app.
3. **Start captures** (both, in parallel):
   ```bash
   sudo tcpdump -i any -n -s 0 'tcp port 443 or udp port 53' -w /tmp/blheli-capture.pcap
   ```
   plus the app's own `.xlg` debug log (unique filename), plus `serve --verbose` already logging.
4. **Recommend a screen recording** before anything else happens — it catches details a text log misses.
5. **Stage** the test firmware in the app's Flash tab (a `.Hex` matching the connected ESC's layout name — an empty match crashes the app's Flash UI, `PLAN.md` §4).
6. **Hand control to the user for the click.** State plainly: this is the irreversible step; confirm now that you accept possibly overwriting this ESC's firmware with no way back. Wait for their explicit yes. Do not proceed on silence or a stale approval.
7. **After the click**, collect: `serve` request log, `/tmp/blheli-capture.pcap` (check for any DNS query or TLS SNI other than `blheli.org` around the click timestamp), the app's `.xlg`, the ESC's power-on beep pattern (3 audible states — a zero-risk state check).
8. **Fold findings** into `docs/knowledge/activation-licensing.md`. If a real activation request appeared, update `approval/codec.py` (`decode_request`/`encode_response`) — that is the only file that changes.

## Rules

- Every `sudo` / capture command: exact command to the user, get go-ahead.
- Report what was captured verbatim; mark confirmed vs. inferred.

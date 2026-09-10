---
name: esc-backup
kind: skill
category: hardware
summary: "Read, decrypt, decode, and archive a connected ESC's Setup block."
description: |
  Capture a full evidence set for a connected BLHeli32 ESC — raw byte-exact Setup-block backup plus decoded named fields — and cross-check it against docs/knowledge/setup-block-fields.md. Read-only. Run for every newly connected board or firmware revision.
---

# esc-backup

**Trigger**: "back up the ESC", "dump the config", "capture this board", "esc-backup", MENU.md item 5A.

Read-only. No approval server or redirect needed — just hardware connected. Full reference: `docs/USAGE.md` §6.

## Steps

1. **Confirm the serial port.** `/dev/ttyACM0`-style on Linux, `COMn` on Windows. Ask if not given.

2. **Dump every ESC the FC reports, with a raw backup:**
   ```bash
   blheli32proxy dump-config --port /dev/ttyACM0 --raw-dir dumps
   ```
   - `--motor-index N` — one channel only.
   - `--direct` — standalone ESC on a dedicated adapter instead of an FC passthrough.
   - `--raw-dir dumps` — always include it. Writes a byte-exact `.bin` per ESC under `dumps/` (`dumps/README.md`).

3. **Record board identity** from the output: layout name, MCU, `Eep_FW_Main_Revision` / `Eep_FW_Sub_Revision`. This scopes every finding.

4. **Cross-check** the decoded fields against `docs/knowledge/setup-block-fields.md`:
   - All values match a real `.ixi` from the same board? Note it.
   - A field decodes differently than the doc's offset map predicts? That is a real cross-version difference — do NOT edit the existing map. Add a new version-scoped entry (`AGENTS.md`, Technical knowledge standard).
   - 45 of 46 field names are confirmed; only `Eep_ESC_Mode` is an open, exhausted gap.

5. **If the app is also being used** for `.ixi` / `.xlg` capture: save each to a unique filename per session (never overwrite — comparing captures across boards is the point). Put board-evidence `.ixi`/`.xlg` under `docs/knowledge/`.

## Rules

- Never write into `$BLHELI32PROXY_ARCHIVE_DIR` — the tool refuses this by design; do not work around it.
- `dumps/*.bin` are the user's own hardware read-outs — committable and publishable (`AGENTS.md` Publishing Gate), unlike vendor binaries.
- Report actual field-match counts from the command output; do not assume.
- After the capture, update `docs/knowledge/setup-block-fields.md` / `hardware-findings.md` in the same change if anything new was confirmed.

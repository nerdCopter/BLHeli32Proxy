# dumps/

Local storage for firmware/config binaries extracted **by this project's own tooling**
(`probe-flash`, `dump-info-page`, `dump-config` — see `docs/USAGE.md` §6/§6b) from your own ESC
hardware. Distinct from `$BLHELI32PROXY_ARCHIVE_DIR` (the separate, pre-existing, read-only archive
— see `docs/USAGE.md` §1a; that directory is never written to or deleted from by this project,
under any circumstance).

Typical use: back up an ESC's currently-flashed firmware **before** trying anything that could
change it (a new firmware flash, an activation attempt, or backlog work like §7's AM32-flashing
investigation) — so there's a known-good image to revert to if something goes wrong. Example:

```bash
blheli32proxy probe-flash --port /dev/ttyACM0 --address 0x0000 --length 16
blheli32proxy dump-info-page --port /dev/ttyACM0 --start 0x0000 --end 0x6000 \
    --out dumps/ak32-32.7-backup.bin
```

Also the destination for raw Setup-block backups: `dump-config --raw-dir dumps` saves each dumped
ESC's exact 256-byte ciphertext to `esc<N>-setup-<timestamp>.bin` — a byte-exact backup usable for
a full restore, unlike `--out`'s decoded-fields-only partial-backup file. Confirmed valuable in
practice: 2026-09-07's real-hardware corruption incident (`docs/knowledge/hardware-findings.md`)
was only repairable because a byte-identical sibling ESC existed to copy from — capture these
routinely, not just before a risky experiment.

**Whitelisted, not gitignored (2026-09-07)** — see `AGENTS.md`'s Publishing Gate. Everything here
is this project's own extraction from the user's own owned hardware, not a vendor-released binary
— the same category as the `.ixi`/`.xlg` files under `docs/knowledge/`. Fine to commit and publish
like any other file in this repo, following the same approval process as any push.

**Not every capture gets committed.** A single differential-capture session (see
`docs/knowledge/setup-block-fields.md`'s method) can produce many timestamped
`esc<N>-setup-<timestamp>.bin` files in quick succession — one per settings change tested. Commit
only the ones that carry lasting evidentiary value (the final state of a session, or a capture a
doc specifically cites); leave the rest untracked locally, or move them out of the repo entirely
into `$BLHELI32PROXY_ARCHIVE_DIR`'s own backup folder (e.g. its `ini-xlg-backups/` subfolder,
alongside the `.ixi`/`.xlg` files already kept there) so the repo's untracked-file list doesn't
accumulate clutter session over session. That's a manual, one-off action the repository owner
directs explicitly each time — not something this project's own tooling ever does automatically
(the "never write into `$BLHELI32PROXY_ARCHIVE_DIR`" rule above still describes this project's own
automated behavior; a human deliberately organizing their own archive is a different action from
the tool silently writing there).

## Known mislabeled captures (2026-09-08 correction)

`esc2-setup-20260907-160717.bin` and `esc3-setup-20260907-160717.bin` were committed in
`38f6720` as if they were final-state Furling32 evidence (that commit's session was
testing on a Furling32, GD32F350x6, firmware 32.9.5). **They are not.** Verified via
`extract_identity_strings()`: both decode to `layout=Aikon_AK32_4IN1_35A_6S_V1_0`,
`cpu=STM32F051x6` — stale AK32 captures from earlier the same day, swept into that commit
by mistake. Left in place, not deleted or replaced — real capture data, just mislabeled by
which session it was attributed to, not by filename accuracy (the timestamp in each name is
correct; the *assumed hardware source* was wrong). No doc in this project cites these two
files by name, so no other correction was needed. Genuine raw-byte Furling32 evidence for
this offset map exists separately: `esc1-setup-20260907-170726.bin` (same repo, confirmed
`layout=Furling32`, `cpu=GD32F350x6`).

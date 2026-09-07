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

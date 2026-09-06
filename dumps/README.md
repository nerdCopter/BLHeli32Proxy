# dumps/

Local storage for firmware/config binaries extracted **by this project's own tooling**
(`probe-flash`, `dump-flash`, `dump-setup` — see `docs/USAGE.md` §6/§6b) from your own ESC
hardware. Distinct from `$BLHELI32PROXY_ARCHIVE_DIR` (the separate, pre-existing, read-only archive
— see `docs/USAGE.md` §1a; that directory is never written to or deleted from by this project,
under any circumstance).

Typical use: back up an ESC's currently-flashed firmware **before** trying anything that could
change it (a new firmware flash, an activation attempt, or backlog work like §7's AM32-flashing
investigation) — so there's a known-good image to revert to if something goes wrong. Example:

```bash
blheli32proxy probe-flash --port /dev/ttyACM0 --address 0x0000 --length 16
blheli32proxy dump-flash --port /dev/ttyACM0 --start 0x0000 --end 0x6000 \
    --out dumps/ak32-32.7-backup.bin
```

**Not committed to git for now** — `.gitignore` at the project root excludes `dumps/*.bin` and
`dumps/*.hex`. This is a temporary default, not a permanent rule: the project's actual intent
(`PLAN.md` §8) is to eventually publish official firmware dumps as a public community resource,
once extraction/re-flashing is confirmed reproducible. Publishing needs explicit approval at that
time (`PLAN.md` §8's hard gate) — not just deleting these `.gitignore` lines on momentum.

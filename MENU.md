# BLHeli32Proxy — Menu

Say or type "menu" any time to see this list again. Pick an item by number, or describe what you
want in your own words — either works.

**Platform support**: developed and verified on Linux. Windows, WSL, and macOS are supported in
the codebase and documented in `docs/USAGE.md`, but are **best-effort, not verified on real
hardware by this project** — if something doesn't work on your platform, please open an issue or
pull request; this is a community-maintained tool.

---

## 1. Populate BLHeli_32 test firmware (prerequisite for most other items)

Fetches the per-manufacturer test-firmware `.Hex` files this tool and the real `BLHeliSuite32xl`
app both need, from BLHeli's own official GitHub history (nothing is bundled in this repo — see
`docs/USAGE.md` §1b and `AGENTS.md`'s Publishing Gate for why), copying them into whichever
destination `$BLHELI32PROXY_APP_DIR`/`$BLHELI32PROXY_ARCHIVE_DIR` you have set (see `docs/USAGE.md`
§1a).

- **Latest only** (default, faster): one snapshot covering every manufacturer's most recent
  published build.
- **All historical versions** (slower): every version ever published, for when you need a specific
  older build a manufacturer hasn't re-published since.

**AI-actionable**: read `docs/USAGE.md` §1b and follow Option A or B exactly as written there —
ask the user which one if they haven't said, then run the commands and report the file count
copied in.

## 2. Environment prerequisites (OS-level software, per platform)

Checks for and helps install what this tool needs beyond Python itself: `openssl` (for
`gen-cert`), a serial port driver/permission setup (Linux: user in the `dialout` group; Windows:
correct COM-port driver; macOS: no special driver usually needed), and optionally `tcpdump`/
`Wireshark` for the traffic-capture workflows in `docs/USAGE.md` §7a/§7b.

**AI-actionable**: detect the current OS, check each prerequisite (`which openssl`, group
membership, etc.), report what's missing, and offer to install it using that OS's normal package
manager (`apt`/`dnf` on Linux, `brew` on macOS, pointing to installers on Windows) — always ask
before actually installing anything system-level, per this assistant's standing safety rules.

## 3. Run / manage the approval server

The actual deliverable of this project: generate a TLS cert, start the local server that answers
BLHeli's dead activation endpoint, and set up the OS-level hostname (and, on Linux, port) redirect
so the real app reaches it. See `docs/USAGE.md` §2-§4 for the full walkthrough, per-OS. **Do this
before item 4** — the real vendor app calls a licensing endpoint that only works once this is set
up.

**AI-actionable**: run through `gen-cert` → `serve` → redirect setup, checking at each step
whether it's already done (cert exists? server already running? redirect already in
`/etc/hosts`/equivalent?) rather than blindly repeating completed steps.

## 4. Run `BLHeliSuite32xl` (the real vendor app — flashing, backups, logs)

This project never flashes ESCs itself — this menu item is about running the **real, unmodified**
vendor configurator app (`BLHeliSuite32xl` on Linux, `BLHeliSuite32.exe` on Windows,
`BLHeliSuite32xm.app` on macOS — this doc uses the Linux name as shorthand throughout) for
whichever of these you need (not mutually exclusive):

- **A) Flashing** — install test firmware onto a connected ESC. Requires the approval server and
  OS-level redirect already running (item 3 above, or `docs/USAGE.md` §2-§4) — the real app calls
  a licensing endpoint that only works if that's set up.
- **B) `.ixi` backups and `.xlg` debug logs** — read-only config backup and protocol-trace capture.
  Always **save to file** with a **unique filename per session** (the app's own "Save to file"
  action in its Log tab, or its backup/export menu) — don't overwrite a previous capture, since
  comparing multiple captures across ESCs/sessions is often exactly the point (see
  `docs/knowledge/setup-block-fields.md`'s cross-version validation work for why this mattered).

**AI-actionable**: ask the user for the app's install path if not already known, or search common
locations for the current OS (Linux: wherever they extracted it, often alongside a `BLHeli32_HexFiles/`
subfolder — see `docs/knowledge/hardware-findings.md` for a real bug this folder needs to be
populated to avoid; Windows/macOS: standard install/Applications directories). Launch it, and if
doing (B), remind the user to use a unique output filename before they save.

## 5. Run the test suite

Quick sanity check that the tool's own code works in your environment:

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest tests/
```

**AI-actionable**: run this, report the actual pass/fail count from the output (never assume
"tests pass" without reading it), and if anything fails, investigate before reporting done.

## 6. Investigate / troubleshoot / develop known gaps

Pick up any open item from `PLAN.md`'s current status and backlog — e.g. cross-version
Setup-block field-offset confirmation, or anything else listed there as not yet done. **The single
most important remaining item** is capturing the real ESC-activation network call (Goal 4),
detailed below — this is this project's core remaining goal, and the last thing to attempt since
it carries real, irreversible risk.

**AI-actionable**: read `PLAN.md` for current status, `docs/knowledge/INDEX.md` for the technical
reference base, and work the specific gap the user names — or summarize the open items and ask
which one to pick up if they just say "investigate gaps" with no specifics.

### Goal 4: capture the real ESC-activation call

With the approval server and redirect already running (item 3), and a real ESC connected with test
firmware staged in `BLHeliSuite32xl`'s Flash tab (item 4), click "Flash Selected ESC" in the real
app and capture what actually gets sent. **This is the one action in this whole project with real,
irreversible risk** — it can overwrite the ESC's current firmware with no way to restore it
(firmware dumps are blocked by the ESC's own hardware protection, see
`docs/knowledge/hardware-findings.md`).

**AI-actionable**: never initiate the actual flash click on the user's behalf or treat a past
"go ahead" as still valid — get their explicit, freshly-stated confirmation of the firmware-loss
trade-off at the moment this is actually attempted, every time. Recommend a screen recording
running before it happens (this captures details a text log might miss). Afterward, capture the
approval server's request log and the real app's own saved `.xlg` debug log, and fold whatever the
real activation request looks like into `docs/knowledge/activation-licensing.md`.

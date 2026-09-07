# BLHeliSuite32Proxy — AI Project Standards

Applies to this repository, wherever it's cloned.

Status: implementation in progress, real hardware confirmed working across 4 different ESC
families/firmware revisions. See `PLAN.md` for goals/status/decisions, `docs/knowledge/INDEX.md`
for confirmed technical reference material (protocol, activation/licensing, Setup-block fields,
hardware findings), `IMPLEMENTATION.md` for build status/module layout, and `docs/USAGE.md` for how
to run and configure the tool (including OS-level IP/domain redirection) — read `PLAN.md` first,
every session.

---

## Menu system

`MENU.md` (project root) is a human-facing menu of common actions the user can invoke by name,
number, or by simply asking for "the menu." When the user asks for or commands `menu`, read
`MENU.md` fresh (its items evolve — never rely on a remembered copy) and print it, then act on
whichever item the user selects.

---

## Communication and documentation style

1. Session communication and reporting style: ASD-STE100, ELI5, Concise.
2. Documents style: ASD-STE100, Technical/Accurate, ELI5, prefer balanced or concise rather than
   verbose.
3. Documents describe current state, not a session-by-session log of what the assistant/user did
   and when — except `docs/knowledge/*.md` (dated-finding style) and `HANDOFF.md` (a temporary
   bridge doc). External citation dates (upstream commits, article dates, changelog entries) are
   fine everywhere — this rule targets session narrative, not technical citations.

---

## Session Boot

1. `PLAN.md` — current status, architecture decision pending, phase plan.
2. `research/notes/*.en.md` — the technical reference material (English). Read these, not the
   `.zh.md` files or the live `elmagnifico.tech` site, for any protocol/cipher/licensing question.
   The table in [PLAN.md §2](PLAN.md#2-source-material-inventory) ranks them by priority.
3. `research/manuals/*.txt` — official vendor manual + changelog (plain-text, extracted from the
   PDFs bundled with the user's own `BLHeliSuite32xl` copy).

---

## Source Material — Never Delete

- `research/` in this project (translations, images, manuals) — build artifacts of this project's
  own research, safe to regenerate, but treat as durable once written.
- Whatever your own copy of the vendor configurator app lives at — executable name and folder are
  OS-specific (`BLHeliSuite32xl` on Linux, `BLHeliSuite32.exe` on Windows, `BLHeliSuite32xm.app` on
  macOS; no folder-naming convention is enforced by this project, only by whichever user set one
  up) — pointed to via `$BLHELI32PROXY_APP_DIR` (see `docs/USAGE.md` §1a). Its own
  `BLHeli32_HexFiles/` subfolder is the test-firmware catalog most users need — this project has no
  in-repo `testcode/` folder of its own (removed 2026-09-07; every user fetches their own copy
  directly into their app folder or archive, see §1b).
- Whatever broader personal test-firmware archive you point `$BLHELI32PROXY_ARCHIVE_DIR` at, if you
  keep one separately from the app's own folder (optional, power users only — see `docs/USAGE.md`
  §1a).

Never delete any source material, program, binary, link, folder, or file under any of the above,
or anywhere referenced from this project — standing instruction, no exceptions.
`$BLHELI32PROXY_APP_DIR`/`$BLHELI32PROXY_ARCHIVE_DIR` are machine-specific env vars — never
hardcode their real values in project files, docs, or code; they're the user's own local paths, not
project data.

**Never delete any source material, program, binary, link, folder, or file under any path
above, or anywhere referenced from this project — standing instruction, no exceptions.**

---

## Research Sources

- Primary technical source: Chinese-language blog posts at
  `https://elmagnifico.tech/tags/#BLHeli` (and the `DSHOT`/`ESC` tags where relevant — not other,
  unrelated tags on that same site). The `Crack` tag also carries relevant posts not always tagged
  `BLHeli` (found one, part 5, missed by a first `BLHeli`-tag-only pass — cross-check both tags for
  any future post added to that site).
- `research/urls.txt` lists every post crawled so far with its date and canonical URL.
- Translate new posts the same way already done here: `curl` the page, extract the `<article>`
  body, `pandoc` to Markdown (`.zh.md`), download every embedded image locally
  (`research/images/<post-name>/NN.png`), then write a faithful English technical note
  (`.en.md`) — not a loose paraphrase — preserving exact hex/byte values, keeping code/asm
  snippets verbatim, and flagging licensing/activation-relevant findings explicitly.
- Local primary sources (the actual shipped binary/manuals) can outrank the blog posts where they
  conflict or add detail the posts don't cover — see
  `research/notes/BLHeliSuite32xl-local-binary-analysis.en.md` for the method (`file`, `strings`,
  `pdftotext` — read-only, nothing executed).
- **Always actually open embedded images with the Read tool before writing a note — never
  describe one from its filename or surrounding text alone.** Confirmed incident: an earlier pass
  on this project inferred generic captions for `BLHeli-END`'s images without opening them, and
  missed the single most important finding in the entire corpus (a real screenshot of the
  manufacturer `BLHeliSuite32Activator` tool's activation log, UUID+counter protocol and all) —
  caught later only because a second pass actually viewed the file.

---

## Technical Knowledge Standard — solve, don't settle; retain, never purge

The goal of this project's technical work is **comprehensive BLHeli32 knowledge — protocol,
cipher, Setup-block layout, hardware behavior — general to BLHeli32 across manufacturers, MCU
families, and firmware versions, not scoped to whatever hardware the current user happens to own.**
A finding confirmed on one board (AK32, Furling32, whichever) is a data point toward that general
picture, not the destination. When writing up a finding, default to framing it in general terms
(what's true of BLHeli32's protocol/cipher/format) and call out explicitly what's hardware-specific
(MCU-dependent addresses, per-manufacturer layout names) — don't leave a genuinely general finding
implicitly scoped to "this board" when nothing in the evidence suggests it's board-specific.

**Don't stop at "good enough" or declare something closed/not-pursued-further while a real,
reasonably-available technique remains untried.** Before writing off a gap as unknown or
unconfirmed, actively consider: differential/fingerprinting captures (change many things at once
with distinct values, diff once, correlate — not one slow field at a time), static analysis of the
compiled app/binaries, cross-referencing every available data source (research blog posts, real
`.ixi`/`.xlg` captures, multiple hardware units/firmware revisions), and whether a previous session
stopped short of what was actually achievable. "Not pursued further" is a legitimate outcome only
after real options are exhausted or explicitly deferred by the user — not a default.

**Never overclaim, and never understate effort to justify giving up early.** Every finding gets
marked confirmed (empirically verified, how) vs. inferred (reasoned from evidence, not directly
tested) vs. unconfirmed/guessed — consistently, so a reader can tell which is which. Don't state a
guess as fact, and don't quietly downgrade "we haven't tried yet" into "not possible."

**Keep `docs/knowledge/` (and confirmed-finding docstrings, e.g. `write_flash()`'s) reflecting
current valid understanding — never let a real finding go missing through carelessness.** When a
finding is superseded or wrong, fix it so the doc states what's actually true now; don't leave a
disproven claim standing as if still valid. What must never happen is a finding *disappearing*
silently — a rewrite/consolidation pass that drops detail nobody re-derived, or deletes a section
because it "looks resolved."

**Explicitly record what's known to be false, not just what's true** — a debunked hypothesis, a
technique that didn't work, an assumption disproven by a real incident. State it plainly as
confirmed-wrong (not just quietly removed) so a future session doesn't waste time re-trying it or,
worse, re-acting on it (e.g. `write_flash()`'s docstring now says plainly that writing without
erasing first can silently corrupt more than the targeted bytes — a future session reading only
"here's how to write" without that warning could repeat today's incident). Routine superseded
guesses don't need a permanent monument; hard-won confirmed facts, real incidents, and the wrong
assumptions that caused them do.

**Never assume a Setup-block byte-offset map validated on one firmware/hardware combination applies
unchanged to a different one.** Confirmed real, silent differences exist even among fields that
mostly line up: `Eep_Pgm_Pwm_Freq` (AK32/32.7) is the same physical byte as
`Eep_Pgm_Pwm_Frequency_Lo` on Furling32/32.9.5 but means something different (no `_Hi` companion
exists on 32.7); `Eep_Pgm_Curr_Prot` looked like an unused placeholder on AK32 (no current-sense
hardware) and turned out to be a live, actively-written field on Furling32. Any write-capable
script or tool (e.g. a repair/restore that copies or reconstructs Setup-block bytes) must be scoped
to the exact firmware/hardware it was validated against — check the connected ESC's identity
(`extract_identity_strings()`, `Eep_FW_Main_Revision`/`Eep_FW_Sub_Revision` once confirmed) before
reusing a byte-offset map across boards, rather than assuming "close enough" firmware means
"same struct." When extending confirmed knowledge to a new firmware/hardware combination, add new,
clearly version-scoped entries or a separate script/version rather than overwriting or silently
generalizing an existing confirmed mapping — see `docs/knowledge/setup-block-fields.md`'s
cross-version section for how this was handled in practice (kept the AK32-specific `Pwm_Freq` entry
unchanged, added new entries for the newly-confirmed fields, never overwrote working data).

---

## Scope Notes

- The user's own dev/test machine is Linux-only, but **the codebase itself must be cross-platform**
  (Linux/macOS/Windows) — Python 3 was chosen specifically for this. Any OS-specific step (serial
  port naming, HID backend, IP/domain redirection) needs a documented equivalent for all three OSes
  in `docs/USAGE.md`, not just Linux.
- No BLHeli vendor licensing/legal obligations apply (dead company, explicit user instruction) —
  see [PLAN.md §6](PLAN.md#6-risks-open-questions-carried-forward) Risks. Public redistribution of
  the tool itself is an actual project goal. The vendor's own firmware binaries are never
  redistributed by this project — each user fetches their own copy directly from BLHeli's official
  upstream repository (`docs/USAGE.md` §1b) — see this document's own Publishing Gate section
  below and [PLAN.md §8](PLAN.md#8-publishing).
- AI usage on this project is deliberately low-rate right now — prefer batching research/analysis
  work over many small back-and-forth turns, and work autonomously per the user's own stated
  preference (minimal interaction, they are frequently away from keyboard) rather than pausing for
  confirmation unless genuinely blocked.

---

## Workflow Order

1. **RESEARCH** — done; see [PLAN.md §2](PLAN.md#2-source-material-inventory), `research/README.en.md`/`README.zh.md`, and [docs/knowledge/INDEX.md](docs/knowledge/INDEX.md) for confirmed protocol/hardware findings.
2. **PLAN** — `PLAN.md` is the living plan document (goals, status, decisions); update it in place
   as understanding changes, don't create parallel/competing plan files. Dense technical reference
   material (confirmed protocol bytes, field offsets, hardware findings) belongs in
   `docs/knowledge/`, not inline in `PLAN.md` — link to it instead (see `docs/knowledge/INDEX.md`).
3. **IMPLEMENT** — in progress. `IMPLEMENTATION.md` (project root) tracks module layout and status;
   update it as code is added, don't let it drift from what actually exists.
4. **DOCUMENT** — `docs/USAGE.md` is the living how-to-run/how-to-configure doc, including
   per-OS IP/domain redirection steps. Update it in the same change that adds/changes a
   user-facing behavior — don't let code and usage docs drift apart. `docs/knowledge/*.md` is the
   technical reference base (protocol, activation/licensing, Setup-block fields, hardware
   findings) — update the relevant topic file when a new finding is confirmed, don't let it drift
   back into `PLAN.md` as an inline log.
5. **PUBLISH** — vendor-*released* binaries (test firmware fetched via `scripts/fetch-testcode.sh`,
   or any other vendor `.Hex`/`.bin` a user's own `$BLHELI32PROXY_APP_DIR`/`$BLHELI32PROXY_ARCHIVE_DIR`
   might contain — files the vendor itself distributed) are never committed or published — a
   permanent rule, not a case-by-case decision; see this document's own Publishing Gate section.
   This does **not** cover `dumps/*.bin`/`*.hex` (this project's own extractions from the user's own
   owned hardware, whitelisted 2026-09-07 — see the Publishing Gate section). Publishing the
   tool/codebase itself (this project's own code, docs, research) still needs the repository
   owner's explicit approval before any push, PR, or visibility change. Any future `/docs` pass or
   repo cleanup must preserve this distinction, not prune it as stale.

---

## Publishing Gate — Hard Rule (vendor-released binaries, permanent, no exceptions)

**Never commit or publish a binary the vendor itself released** — test firmware fetched via
`scripts/fetch-testcode.sh`, or any other vendor `.Hex`/`.bin` in a user's own
`$BLHELI32PROXY_APP_DIR`/`$BLHELI32PROXY_ARCHIVE_DIR` (official test firmware, see
`docs/USAGE.md` §1b) — anywhere externally reachable (a pushed commit, an uploaded file, or any
equivalent action). This is a **permanent rule, not a case-by-case decision**. Each user fetches
their own copy of the vendor's test firmware directly from BLHeli's official upstream repository
(`docs/USAGE.md` §1b) — this project never needs to redistribute the binaries itself, so there is
no publish decision to make about them.

**This does NOT cover `dumps/*.bin`/`*.hex`** (whitelisted 2026-09-07, not gitignored) — data this
project's own tooling extracts from a user's own owned hardware (Setup-block config backups, and
any application-firmware dump if one is ever achieved). This is the user's own property being
read out, not a copy of a file the vendor distributed — the same category the `.ixi`/`.xlg`
hardware-evidence files under `docs/knowledge/` already fall into, just a different file format.
These may be published if the user chooses, same approval process as any other push.

This does **not** restrict the tool/codebase itself — this project's own original Python code,
docs, research/translations, and the small `.ixi`/`.xlg` hardware-evidence files under
`docs/knowledge/` (this project's own generated data, not vendor material) are all fine to
publish. Publishing those still needs the repository owner's explicit approval before any push,
PR, or visibility change — standard practice for any action affecting shared/remote state, not a
project-specific extra gate.

This project deliberately sidesteps the question of whether BLHeli's own *released* binaries could
ever be legally redistributed, rather than resolving it — since it never attempts to. Revisit only
if something materially changes (e.g. a takedown notice, or a change in who holds BLHeli's IP).

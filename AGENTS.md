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
5. **PUBLISH** — vendor binaries (`dumps/*.bin`/`*.hex`, any other vendor `.Hex`/`.bin` a user's
   own `$BLHELI32PROXY_APP_DIR`/`$BLHELI32PROXY_ARCHIVE_DIR` might contain) are gitignored and
   never committed or published — a permanent rule, not a
   case-by-case decision; see this document's own Publishing Gate section. Publishing the
   tool/codebase itself (this project's own code, docs, research) still needs the repository
   owner's explicit approval before any push, PR, or visibility change. Any future `/docs` pass or
   repo cleanup must preserve this distinction, not prune it as stale.

---

## Publishing Gate — Hard Rule (vendor binaries, permanent, no exceptions)

**Never commit or publish copyrighted vendor binaries** — `dumps/*.bin`/`*.hex` (official BLHeli32
firmware extracted from hardware), or any vendor `.Hex`/`.bin` in a user's own
`$BLHELI32PROXY_APP_DIR`/`$BLHELI32PROXY_ARCHIVE_DIR` (official test firmware, see
`docs/USAGE.md` §1b) — anywhere externally reachable (a pushed commit, an uploaded file, or any
equivalent action). This is a **permanent rule, not a case-by-case decision**: `.gitignore` already
excludes these paths, and no approval process changes that. Each user fetches their own copy of the
vendor's test firmware directly from BLHeli's official upstream repository (`docs/USAGE.md` §1b) —
this project never needs to redistribute the binaries itself, so there is no publish decision to
make about them.

This does **not** restrict the tool/codebase itself — this project's own original Python code,
docs, research/translations, and the small `.ixi`/`.xlg` hardware-evidence files under
`docs/knowledge/` (this project's own generated data, not vendor material) are all fine to
publish. Publishing those still needs the repository owner's explicit approval before any push,
PR, or visibility change — standard practice for any action affecting shared/remote state, not a
project-specific extra gate.

This project deliberately sidesteps the question of whether BLHeli's own binaries could ever be
legally redistributed, rather than resolving it — since it never attempts to. Revisit only if
something materially changes (e.g. a takedown notice, or a change in who holds BLHeli's IP).

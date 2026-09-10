# BLHeliSuite32Proxy — AI Project Standards

Applies to this repository, wherever it's cloned. AI instruction for continued development —
read `PLAN.md` first, every session.

`PLAN.md` — goals, status, decisions. `docs/knowledge/INDEX.md` — confirmed technical reference
(protocol, activation/licensing, Setup-block fields, hardware findings). `IMPLEMENTATION.md` —
module layout and build status. `docs/USAGE.md` — how to run and configure the tool, including
per-OS IP/domain redirection.

---

## Menu system

`MENU.md` (project root) is a human-facing menu of common actions. When the user asks for or
commands `menu`, read `MENU.md` fresh (its items evolve — never rely on a remembered copy), print
it, then act on the selection.

---

## Communication and documentation style

1. Docs, code comments, commit messages, and PR/issue text: technical, accurate, concise over
   verbose. One fact per sentence; active voice.
2. Docs describe current state, not a session-by-session log of what the assistant or user did and
   when. Exceptions: `docs/knowledge/*.md` (dated-finding style), and a `HANDOFF.md` bridge doc if
   a session creates one (delete it once its content is absorbed into permanent docs). External
   citation dates (upstream commits, article dates, changelog entries) are fine everywhere — this
   rule targets session narrative, not technical citations.

---

## Session Boot

1. `PLAN.md` — current status, decisions, backlog.
2. `research/notes/*.en.md` — the technical reference material. Read the English `.en.md` files,
   not the `.zh.md` files or the live `elmagnifico.tech` site, for any protocol/cipher/licensing
   question. Priority ranking: [PLAN.md §2](PLAN.md#2-source-material-inventory).
3. `research/manuals/*.txt` — official vendor manual + changelog (plain text, extracted from the
   PDFs bundled with the user's own `BLHeliSuite32xl` copy).

---

## Source Material — Never Delete

Never delete, overwrite, or truncate any source material, program, binary, link, folder, or file
under the paths below, or anywhere referenced from this project. Standing instruction, no
exceptions.

- `research/` (translations, images, manuals) — safe to regenerate, but treat as durable once
  written.
- The user's own copy of the vendor configurator app, pointed to via `$BLHELI32PROXY_APP_DIR`
  ([`docs/USAGE.md`](docs/USAGE.md) §1a). Executable name is OS-specific: `BLHeliSuite32xl`
  (Linux), `BLHeliSuite32.exe` (Windows), `BLHeliSuite32xm.app` (macOS); no folder-naming
  convention is enforced. Its `BLHeli32_HexFiles/` subfolder is the test-firmware catalog most
  users need.
- `$BLHELI32PROXY_ARCHIVE_DIR` — an optional broader personal test-firmware archive kept
  separately from the app folder (power users — [`docs/USAGE.md`](docs/USAGE.md) §1a).

There is no in-repo `testcode/` folder — each user fetches their own test firmware
([`docs/USAGE.md`](docs/USAGE.md) §1b).

`$BLHELI32PROXY_APP_DIR` / `$BLHELI32PROXY_ARCHIVE_DIR` are machine-specific — never hardcode
their real values in project files, docs, or code.

---

## Research Sources

- Primary: Chinese-language blog posts at `https://elmagnifico.tech` — the `BLHeli`, `DSHOT`,
  `ESC`, and `Crack` tags (not other, unrelated tags on that site). Cross-check `Crack` too: it
  carried a relevant post (part 5) that a `BLHeli`-tag-only pass missed.
- `research/urls.txt` lists every post crawled so far, with its date and canonical URL.
- New-post workflow: `curl` the page → extract the `<article>` body → `pandoc` to Markdown
  (`.zh.md`) → download every embedded image to `research/images/<post-name>/NN.png` → write a
  faithful English `.en.md` note, not a loose paraphrase — preserve exact hex/byte values, keep
  code/asm snippets verbatim, flag licensing/activation-relevant findings explicitly.
- Local primary sources (the shipped binary, the manuals) can outrank the blog posts where they
  conflict or add detail the posts don't cover. Method:
  `research/notes/BLHeliSuite32xl-local-binary-analysis.en.md` (`file`, `strings`, `pdftotext` —
  read-only, nothing executed).
- Always open embedded images with the Read tool before writing a note — never describe one from
  its filename or surrounding text alone. A past pass skipped this for `BLHeli-END`'s images and
  missed the corpus's single most important finding: a screenshot of the manufacturer
  `BLHeliSuite32Activator` tool's activation log (UUID + counter protocol). Caught only on a
  second pass that actually viewed the file.

---

## Technical Knowledge Standard — solve, don't settle; retain, never purge

**Aim for general BLHeli32 knowledge** — protocol, cipher, Setup-block layout, hardware behavior —
across manufacturers, MCU families, and firmware versions, not scoped to whatever hardware the
current user owns. A finding confirmed on one board (AK32, Furling32, whichever) is a data point,
not the destination. Frame findings generally; call out explicitly what is hardware-specific
(MCU-dependent addresses, per-manufacturer layout names).

**Don't stop while a real, reasonably-available technique remains untried.** Before writing a gap
off as unknown, actively consider: differential/fingerprinting captures (change many things at
once with distinct values, diff once, correlate — not one field at a time); static analysis of
the compiled app/binaries; cross-referencing every data source (blog posts, real `.ixi`/`.xlg`
captures, multiple hardware units and firmware revisions); whether a previous session stopped
short of what was achievable. "Not pursued further" is legitimate only after real options are
exhausted or the user explicitly defers — not as a default.

**Mark every finding** confirmed (empirically verified — say how) / inferred (reasoned from
evidence, not directly tested) / guessed. Never state a guess as fact. Never downgrade "not tried
yet" into "not possible". Don't overclaim, and don't understate effort to justify giving up
early.

**Keep `docs/knowledge/` and confirmed-finding docstrings (e.g. `write_flash()`'s) reflecting
current understanding.** When a finding is superseded or wrong, fix it so the doc states what is
true now — don't leave a disproven claim standing. A real finding must never disappear silently
in a rewrite or consolidation pass.

**Record what is known false**, not just what is true — a debunked hypothesis, a technique that
failed, an assumption a real incident disproved. State it plainly as confirmed-wrong, not by
silent removal. Example: `write_flash()`'s docstring now states that writing without erasing
first can silently corrupt more than the targeted bytes — a future session reading only "here's
how to write" without that warning could repeat that incident.

**Never assume a Setup-block byte-offset map validated on one firmware/hardware combination
applies unchanged to another.** Confirmed real, silent differences:

- `Eep_Pgm_Pwm_Freq` (AK32 / firmware 32.7) is the same physical byte as
  `Eep_Pgm_Pwm_Frequency_Lo` on Furling32 / 32.9.5, but means something different — no `_Hi`
  companion exists on 32.7.
- `Eep_Pgm_Curr_Prot` looked like an unused placeholder on AK32 (no current-sense hardware); it
  is a live, actively-written field on Furling32.

Any write-capable script or tool (a repair/restore that copies or reconstructs Setup-block bytes)
must be scoped to the exact firmware/hardware it was validated against — check the connected
ESC's identity (`extract_identity_strings()`, `Eep_FW_Main_Revision` / `Eep_FW_Sub_Revision`)
before reusing a byte-offset map across boards. When extending confirmed knowledge to a new
firmware/hardware combination, ADD clearly version-scoped entries (or a separate script/version) —
never overwrite or silently generalize an existing confirmed mapping. See
[`setup-block-fields.md`](docs/knowledge/setup-block-fields.md)'s cross-version section for how
this was handled in practice (the AK32 `Pwm_Freq` entry kept unchanged, new entries added
alongside, working data never overwritten).

---

## Scope Notes

- The user's own dev/test machine is Linux-only, but **the codebase itself must be cross-platform**
  (Linux/macOS/Windows) — Python 3 was chosen for this. Any OS-specific step (serial port naming,
  HID backend, IP/domain redirection) needs a documented equivalent for all three OSes in
  `docs/USAGE.md`, not just Linux.
- No BLHeli vendor licensing or legal obligation applies (dead company, explicit user
  instruction — [PLAN.md §6](PLAN.md#6-risks-open-questions-carried-forward)). Public
  redistribution of the tool itself is a project goal. The vendor's own firmware binaries are
  never redistributed — each user fetches their own from BLHeli's official upstream
  ([`docs/USAGE.md`](docs/USAGE.md) §1b). See the Publishing Gate below and
  [PLAN.md §8](PLAN.md#8-publishing).
- AI usage on this project is deliberately low-rate — batch research and analysis over many small
  back-and-forth turns, and work autonomously unless genuinely blocked.

---

## Workflow Order

1. **RESEARCH** — done. See [PLAN.md §2](PLAN.md#2-source-material-inventory),
   `research/README.en.md`, [docs/knowledge/INDEX.md](docs/knowledge/INDEX.md).
2. **PLAN** — `PLAN.md` is the living plan (goals, status, decisions). Update it in place; no
   parallel or competing plan files. Dense technical reference (confirmed protocol bytes, field
   offsets, hardware findings) belongs in `docs/knowledge/`, linked from `PLAN.md`, not inline.
3. **IMPLEMENT** — `IMPLEMENTATION.md` tracks module layout and status. Keep it matching what
   actually exists.
4. **DOCUMENT** — `docs/USAGE.md` is the living how-to-run/configure doc, including per-OS
   redirection. Update it in the same change that adds or changes a user-facing behavior. Update
   the relevant `docs/knowledge/*.md` topic file when a finding is confirmed — don't let it drift
   back into `PLAN.md` as an inline log.
5. **PUBLISH** — see the Publishing Gate below.

---

## Publishing Gate — Hard Rule (vendor-released binaries, permanent, no exceptions)

**Never commit or publish a binary the vendor itself released** — test firmware fetched via
`scripts/fetch-testcode.sh`, or any other vendor `.Hex` / `.bin` in a user's
`$BLHELI32PROXY_APP_DIR` / `$BLHELI32PROXY_ARCHIVE_DIR` — anywhere externally reachable (a pushed
commit, an uploaded file, any equivalent action). This is a permanent rule, not a case-by-case
decision. Each user fetches their own copy from BLHeli's official upstream
([`docs/USAGE.md`](docs/USAGE.md) §1b); this project never redistributes it.

**Not covered by the gate:** `dumps/*.bin` / `*.hex` (whitelisted 2026-09-07, not gitignored) —
this project's own extractions from a user's own owned hardware (Setup-block config backups, and
any application-firmware dump if one is ever achieved). The user's own property, not a copy of a
vendor-distributed file — the same category as the `.ixi` / `.xlg` hardware-evidence files under
`docs/knowledge/`. Publishable if the user chooses, same approval process as any other push.

**The tool and codebase itself** — original Python code, docs, research/translations, and the
small `.ixi` / `.xlg` hardware-evidence files under `docs/knowledge/` — is fine to publish, with
the repository owner's explicit approval before any push, PR, or visibility change (standard
practice for any change to shared/remote state, not a project-specific extra gate).

This project deliberately sidesteps the question of whether BLHeli's own released binaries could
ever be legally redistributed, rather than resolving it — since it never attempts to. Revisit
only if something material changes (a takedown notice, a change in who holds BLHeli's IP).

---

## Skills

`.claude/skills/` holds this repo's reproducible procedures, versioned with the repo so
end-users can run them too. Invoke with `/name`, or ask.

- `/proxy-up` — start the approval server and the OS-level hostname + port redirect.
- `/esc-backup` — read, decrypt, decode, and archive a connected ESC's Setup block.
- `/capture-activation` — Goal 4 guided flash-and-capture. Safety-gated: irreversible firmware risk.
- `/pre-publish` — PII, stale-claim, vendor-binary, and LICENSE checks before a public push.
- `/doc-sync` — staleness sweep across docs (cached counts, CLI help text, anchor links, stray dates).

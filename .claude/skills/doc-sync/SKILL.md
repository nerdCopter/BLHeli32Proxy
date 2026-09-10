---
name: doc-sync
kind: skill
category: documentation
summary: "Staleness sweep across docs: cached counts, CLI help, anchor links, stray dates."
description: |
  Find and fix drift across the repo's docs. Checks that no fact is cached in two places out of sync (field counts, test counts, CLI help), that markdown section links resolve, and that docs describe current state rather than a session log. Run after any doc restructure or a batch of confirmed findings.
---

# doc-sync

**Trigger**: "sync the docs", "check for stale docs", "doc-sync", after a doc restructure or a run of new findings.

Enforces `AGENTS.md`'s doc map: one source of truth per fact, everything else links.

## Checks

1. **Cached-number drift.** For each fact that has one authoritative home:
   - Field count — authoritative: `docs/knowledge/setup-block-fields.md`. Grep `of 46` everywhere; every hit must match.
   - Test count — authoritative: live `pytest`. Grep `tests pass|passing`; run `.venv/bin/python -m pytest tests/ -q | tail -1`; reconcile `IMPLEMENTATION.md`.
   - CLI `--help` / command list — authoritative: `src/blheli32proxy/cli.py`. Compare against `README.md`, `docs/USAGE.md`, `MENU.md`.
   Fix by replacing the cached copy with a link, not by updating the number in place, wherever practical.

2. **Broken section links.** Every `](FILE#anchor)` and `§N` reference resolves:
   ```bash
   git grep -noE '\]\([A-Za-z0-9_./-]+\.md#[a-z0-9-]+\)'
   ```
   Slugify each target file's headings (lowercase, spaces→`-`, drop punctuation) and confirm the anchor exists. Report every miss.

3. **Command-name drift.** Grep for renamed commands (e.g. `dump-setup` → `dump-config`, `dump-flash` → `dump-info-page`). No stale name outside `.git/`.

4. **Current-state style.** Docs describe what is true now, not "this session did X". Flag stray dated session narrative in any doc EXCEPT `docs/knowledge/*.md` and a `HANDOFF.md` bridge doc if one exists (dated style is intentional in both). External citation dates (upstream commits, articles) are always fine.

5. **README vs. knowledge base.** `README.md`'s status/claims match `docs/knowledge/goals-status.md`.

## Rules

- Move detail, never delete it (`AGENTS.md` Technical knowledge standard). A consolidation pass must not drop a finding nobody re-derived.
- Report every fix made and every item left for the user.
- Commit before starting if the sweep will touch many files.

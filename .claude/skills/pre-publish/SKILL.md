---
name: pre-publish
kind: skill
category: release
summary: "PII, stale-claim, vendor-binary, and LICENSE checks before a public push."
description: |
  Run before any push that adds a public commit or changes repo visibility. Sweeps tracked files AND full git history for PII (the maintainer's username and any path containing it), scans for stale or false technical claims, confirms no vendor-released binary is staged, and checks LICENSE presence. Reports; the user decides and pushes.
---

# pre-publish

**Trigger**: "make it public", "push to the public repo", "pre-publish check", before any `git push` that is externally visible.

The repo is already public (`github.com/nerdCopter/BLHeli32Proxy`). This still runs before every public-facing push.

## 1. PII sweep — tracked tree AND full history

PII here = the maintainer's username `ndronet` and any absolute path containing it, plus any other real local path or hostname.

```bash
git grep -nI -e ndronet -e '/home/' -e '$BLHELI32PROXY_APP_DIR/' -- . ':!AGENTS.md' ':!*.md'
git log --all -p -S ndronet -- .        # any commit that ever added/removed the string
git log --all --format='%an <%ae>' | sort -u   # commit-author identities
```
- Env var *names* (`$BLHELI32PROXY_APP_DIR`) are fine. Their *values* are not.
- Anything ambiguous: list it for the user to decide, do not auto-scrub.
- History hits mean history, not just the tree, needs the user's call before a public push.

## 2. Stale / false-claim scan

- Cached numbers that must match their source of truth (`AGENTS.md` doc map): field count ("N of 46"), test count, CLI `--help` text. Grep each occurrence; confirm against the authoritative file.
  ```bash
  git grep -nE 'of 46|[0-9]+ tests? (pass|passing)'
  .venv/bin/python -m pytest tests/ -q | tail -1   # real current test count
  ```
- README claims vs. `docs/knowledge/goals-status.md` — proxy/flashing status especially.
- Stray session-narrative dates in docs that should be current-state (`AGENTS.md` style rule); `docs/knowledge/*.md` and any `HANDOFF.md` bridge doc are exempt.
- No overclaims: every "confirmed" is actually verified; no "impossible" that is really "not tried".

## 3. Vendor-binary scan

```bash
git ls-files | grep -iE '\.(hex|bin)$'
```
- `dumps/*.bin` / `*.hex` — allowed (user's own hardware read-outs).
- Anything from `fetch-testcode.sh` output, `BLHeli32_HexFiles/`, or an app/archive folder — MUST NOT be tracked. Publishing gate is permanent (`AGENTS.md`).

## 4. LICENSE

`test -f LICENSE` — required before public release. If missing, flag it; do not add one without the user choosing the license.

## Output

A short report: PII findings (tree + history), stale claims found, vendor-binary status, LICENSE status. End with a clear go / no-go and the specific items the user must decide. Do not push — the user does.

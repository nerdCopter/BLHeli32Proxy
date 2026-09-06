# testcode/ — How to populate this folder

This folder holds the per-manufacturer BLHeli_32 test-firmware `.Hex` files that
`blheli32proxy list-test-firmware` and the real `BLHeliSuite32xl` app's own Flash tab both read
from (see `docs/USAGE.md` §1a/§1b for how the tool points at this or another location).

**This folder is empty in a fresh clone, and stays that way in git** (`.gitignore` excludes
`testcode/*.Hex` — see the Publishing Gate in `AGENTS.md`: these are BLHeli's own copyrighted
vendor binaries, never bundled in this repo). You populate it yourself, once, from BLHeli's own
official GitHub repository.

## Source

Official repo: `https://github.com/bitdump/BLHeli` — the `BLHeli_32 ARM/` folder held the full
per-manufacturer test-firmware collection until it was removed on **2024-06-04** (commit
`26fbb46e41`, "Removed testcodes"), after the vendor shut down mid-2024. Everything below recovers
those files from the repo's own history — nothing here is copied into *this* repo.

## Option A — Latest only (smaller, faster; recommended default)

Gets the final snapshot of every manufacturer's most recently published test build, as of the
commit right before removal (`9577152ca9`, 2024-05-29).

```bash
git clone --depth 1 https://github.com/bitdump/BLHeli.git /tmp/blheli-source
cd /tmp/blheli-source
git fetch --unshallow   # GitHub rejects fetching an arbitrary commit SHA on a shallow clone
git checkout 9577152ca9 -- "BLHeli_32 ARM"
```

Copy every `.Hex` file found under `BLHeli_32 ARM/*/` (subfolders named things like
`Misc testcodes/`, `Half pwm low frequency testcode/`, `Loaded startup testcode/`, `Plane
nondamped testcode/`) into this `testcode/` folder, flat (no subfolders needed — filenames already
encode manufacturer, layout, and version, e.g.
`Aikon_AK32_4IN1_35A_6S_V1_0_Multi_32_95.Hex`):

```bash
find "/tmp/blheli-source/BLHeli_32 ARM" -iname "*.Hex" -exec cp -p {} /path/to/this/repo/testcode/ \;
```

**Note on "32.9.5"**: this snapshot is the most recent state the repo ever held, but individual
manufacturers' filenames may show an older version number (`_32_7`, `_32_8`, etc.) if that
manufacturer's own test build wasn't refreshed again before the repo was taken down — not every
file in this snapshot is actually a `32.9.5` build. If you need a specific manufacturer/layout at
a specific version and it's not here, use Option B.

## Option B — All historical versions (larger, slower; use if you need an older/specific version)

Test files were added incrementally over 2023-2024 and reorganized more than once (see the
`Cleanup` commits below) — a file present in an early commit may have been moved, renamed, or
removed by a later one, so the single latest snapshot (Option A) doesn't necessarily contain every
version that ever existed.

```bash
git clone https://github.com/bitdump/BLHeli.git /tmp/blheli-source
cd /tmp/blheli-source
git log --follow --diff-filter=A --name-only --pretty=format:"%h %ad %s" --date=short -- "BLHeli_32 ARM" | less
```

Known relevant commits, oldest first (re-verify with the command above — this repo may add more
after this was written):

| Commit | Date | What changed |
|---|---|---|
| `20c36c2695` | 2023-07-08 | Added testcode |
| `f11ef06901` | 2023-12-10 | Added testcodes |
| `73984a150c` | 2023-12-22 | Added testcodes |
| `1061b23218` | 2024-01-14 | Added testcode |
| `2a6262c5d6` | 2024-04-25 | Added HW codes |
| `3dfbc4bf50` | 2024-04-25 | Create FLASH_HOBBY_BLHELI_32_Multi_32_7.Hex |
| `9577152ca9` | 2024-05-29 | Last commit before removal (Option A's snapshot) |
| `26fbb46e41` | 2024-06-04 | **Removed testcodes** — everything gone after this |

For each commit of interest, check out that specific historical state of the folder into a
distinctly-named subdirectory, so files from different snapshots don't collide:

```bash
mkdir -p /tmp/blheli-source/by-commit
for c in 20c36c2695 f11ef06901 73984a150c 1061b23218 2a6262c5d6 3dfbc4bf50 9577152ca9; do
  git -C /tmp/blheli-source checkout "$c" -- "BLHeli_32 ARM"
  mkdir -p "/tmp/blheli-source/by-commit/$c"
  find "/tmp/blheli-source/BLHeli_32 ARM" -iname "*.Hex" -exec cp -p {} "/tmp/blheli-source/by-commit/$c/" \;
done
```

Then copy whichever specific files you actually need (by manufacturer/layout/version in the
filename) from `/tmp/blheli-source/by-commit/<commit>/` into this `testcode/` folder — don't just
copy everything from every commit, since later snapshots mostly superset earlier ones and you'd
end up with many duplicate/stale copies.

## Verifying it worked

```bash
ls testcode/*.Hex | wc -l
blheli32proxy list-test-firmware --dir testcode
```

**Optional but recommended**: set `BLHELI32PROXY_ARCHIVE_DIR` to this folder's absolute path (see
`docs/USAGE.md` §1a), so every command that reads the archive finds it without needing `--dir`
each time:

```bash
export BLHELI32PROXY_ARCHIVE_DIR=/path/to/this/repo/testcode
```

## For an AI assistant automating this

1. Confirm the user wants Option A (default, faster) or Option B (specific older version needed) —
   don't assume; ask if unstated.
2. Run the clone/checkout commands above directly (read-only against the upstream repo — no
   destructive git operations, this is a fresh temp clone each time).
3. Copy only `.Hex` files, flat, into this `testcode/` folder — never touch other file types from
   that repo (manuals, `.apk`, specs) unless the user separately asks for them.
4. Report the count of files copied and confirm with `blheli32proxy list-test-firmware --dir
   testcode` (or the project's configured `--dir`) that they're recognized.
5. Never commit the copied `.Hex` files to this project's own repo — `.gitignore` already excludes
   them, and the Publishing Gate in `AGENTS.md` covers why. If a `git status` ever shows one as
   untracked-but-about-to-be-added, stop and flag it rather than staging it.

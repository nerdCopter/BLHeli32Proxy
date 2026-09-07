#!/bin/bash
# Fetch BLHeli_32 test-firmware .Hex files from bitdump/BLHeli's own GitHub
# history (the vendor never republished after shutting down mid-2024) and
# copy them into your configured catalog directory. No AI needed — plain,
# reproducible, re-runnable any time.
#
# Usage: ./scripts/fetch-testcode.sh [latest|recent|all]
#   latest   (default): the final snapshot before removal — smaller, faster.
#            Includes 32.9.1-32.9.5 and 32.10.9 (filename-suffix only, no
#            dedicated folder ever existed for those in upstream history).
#   recent: latest snapshot plus every 32.7.x/32.8.x version-tagged commit —
#           matches a typical personal archive going back to 32.7.1.
#   all: "recent" plus every version-tagged commit back to 32.31 (2018).
#
# Excludes "Plane nondamped testcode" — fixed-wing-specific builds, out of
# scope for this multirotor-focused project.
#
# Commit list documented in docs/USAGE.md §1b.
set -e

MODE="${1:-latest}"
case "$MODE" in
    latest|recent|all) ;;
    *) echo "Usage: $0 [latest|recent|all]" >&2; exit 1 ;;
esac

# Prerequisite: an env var telling us where to put the files — see docs/USAGE.md §1a,
# or just run ./scripts/setup-env.sh first if neither is set yet.
if [ -n "$BLHELI32PROXY_ARCHIVE_DIR" ]; then
    DEST="$BLHELI32PROXY_ARCHIVE_DIR"
elif [ -n "$BLHELI32PROXY_APP_DIR" ]; then
    DEST="$BLHELI32PROXY_APP_DIR/BLHeli32_HexFiles"
else
    echo "Neither \$BLHELI32PROXY_ARCHIVE_DIR nor \$BLHELI32PROXY_APP_DIR is set." >&2
    echo "Run ./scripts/setup-env.sh first (see docs/USAGE.md §1a)." >&2
    exit 1
fi
mkdir -p "$DEST"
echo "Destination: $DEST"

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

if [ -n "$BLHELI32PROXY_CLONE_DIR" ]; then
    CLONE_DIR="$BLHELI32PROXY_CLONE_DIR"
    if [ -d "$CLONE_DIR/.git" ]; then
        echo "Reusing existing clone: $CLONE_DIR (fetching updates)..."
        git -C "$CLONE_DIR" fetch --quiet origin
    else
        echo "Cloning into $CLONE_DIR (persistent — reused on future runs)..."
        mkdir -p "$CLONE_DIR"
        git clone --quiet https://github.com/bitdump/BLHeli.git "$CLONE_DIR"
    fi
else
    CLONE_DIR="$WORKDIR/blheli-source"
    echo "Cloning to a temp folder (set \$BLHELI32PROXY_CLONE_DIR via ./scripts/setup-env.sh to reuse a persistent clone next time)..."
    git clone --quiet https://github.com/bitdump/BLHeli.git "$CLONE_DIR"
fi

# Extracts one commit's "BLHeli_32 ARM" tree via `git archive` — read-only,
# never touches CLONE_DIR's working tree, safe on a shared/persistent clone —
# and copies its .Hex files (excluding Plane nondamped testcode) into $DEST.
extract_commit() {
    local commit="$1" extract_dir="$WORKDIR/extract-$1"
    mkdir -p "$extract_dir"
    git -C "$CLONE_DIR" archive "$commit" -- "BLHeli_32 ARM" | tar -x -C "$extract_dir"
    find "$extract_dir/BLHeli_32 ARM" -path "*/Plane nondamped testcode" -prune -o \
        -iname "*.Hex" -exec cp -p -n {} "$DEST/" \; 2>/dev/null
}

LATEST_COMMIT="9577152ca9" # 2024-05-29, last snapshot before removal

# 32.7.1, 32.7.2, 32.7.3, 32.7.4, 32.8.1, 32.8.2, 32.8.3 — see docs/USAGE.md §1b.
COMMITS_32_7_8="d33b11320491dec72239a4585b39e7bbe0ff9b3a b4cc04f5779af0e7cb3918c6f10cfbfff343e89e \
41967a136ba738198f41e53e5b473d0d38819a74 118d19dd86a752292d911d96c747a82286839165 \
845dd75091994ef448a8a0869c174e3ae29112db 653782e83a77f9135914d74a59e8337088392185 \
49948e301c47553db309c871b79d5c0689bae018"

# 32.31, 32.41, 32.42, 32.43, 32.5, 32.51, 32.52, 32.6, 32.61, 32.6.1-32.6.9 — see docs/USAGE.md §1b.
COMMITS_32_3_6="87a9039a44e4491e1ca828dd6e81ef1df9b8ebcb 871f70a42b4a2f1598891c2865cf4c26a8b837fd \
9570713045d3ad6f5f729659993fea33fb914377 d389bf18fe4302f23fc58dde93bfb51944497d62 \
26fa7477db2e32836866b42c0101ec837bd4fcdb 482cb2cdf3cb03de37cb7c5e6cf26e00a6a1eed4 \
b0b26936e7f7a9f404ae6f742207b615ea68008b d5f34b02ce8e1a71277a443e5df70eff8446a2f2 \
dd24d5ddfa3122f1dc11d4456da4471abf53fa52 f29edcdfc09809b864fafa471825a39237e14c14 \
dbec3853f23785fb8165c9d1bf27d8ca65c06f23 52b241588ee0b1fca3dce50ab3e9debd4207ff00 \
e5a180ed40ac7d6bc20e1d67a98da2aad5730968 4fc458c0681809182e9ad6eff08a3c28b62b6be9 \
d7dd1b948912913a21cd6e000104a3e4b32df56f 0c2024f4e75838b147c25ab3745b9877ce1335cd \
f2df802066df6e23b93ae953592abde742220c32 4218a713c408e7f484a728b75922fa05daa68032"

case "$MODE" in
    latest)
        echo "Fetching latest snapshot ($LATEST_COMMIT, 2024-05-29)..."
        extract_commit "$LATEST_COMMIT"
        ;;
    recent)
        echo "Fetching latest snapshot plus every 32.7.x/32.8.x version commit..."
        extract_commit "$LATEST_COMMIT"
        for c in $COMMITS_32_7_8; do
            extract_commit "$c"
        done
        ;;
    all)
        echo "Fetching every version-tagged commit back to 32.31 (2018)..."
        extract_commit "$LATEST_COMMIT"
        for c in $COMMITS_32_7_8 $COMMITS_32_3_6; do
            extract_commit "$c"
        done
        ;;
esac

COUNT=$(find "$DEST" -iname "*.Hex" | wc -l)
echo "Done — $DEST now has $COUNT total .Hex file(s) (cumulative, including any already there)"
echo "Verify: blheli32proxy list-test-firmware"

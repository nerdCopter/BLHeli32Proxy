#!/bin/bash
# Interactive one-time setup for this project's env vars. Checks what's already
# set, asks for whatever's missing, and persists to your shell rc file.
# Safe to re-run any time — never duplicates an existing export line.
set -e

RC_FILE="$HOME/.bashrc"
if [ -n "$ZSH_VERSION" ] || [ "$(basename "$SHELL")" = "zsh" ]; then
    RC_FILE="$HOME/.zshrc"
fi

persist() {
    local var_name="$1" value="$2"
    if grep -q "^export ${var_name}=" "$RC_FILE" 2>/dev/null; then
        sed -i.bak "s|^export ${var_name}=.*|export ${var_name}=${value}|" "$RC_FILE"
    else
        echo "export ${var_name}=${value}" >> "$RC_FILE"
    fi
    export "${var_name}=${value}"
    echo "  ${var_name}=${value} (saved to ${RC_FILE})"
}

echo "=== BLHELI32PROXY_APP_DIR (required for most users) ==="
if [ -n "$BLHELI32PROXY_APP_DIR" ]; then
    echo "  already set: $BLHELI32PROXY_APP_DIR"
else
    echo "  This is your vendor configurator app's install folder — the one containing"
    echo "  BLHeliSuite32xl (Linux), BLHeliSuite32.exe (Windows), or BLHeliSuite32xm.app (macOS)."
    read -r -p "  Enter the full path to that folder: " app_dir
    app_dir="${app_dir/#\~/$HOME}"
    if [ ! -d "$app_dir" ]; then
        echo "  Warning: $app_dir does not exist yet — saving it anyway, create it before use." >&2
    fi
    persist BLHELI32PROXY_APP_DIR "$app_dir"
fi

echo
echo "=== BLHELI32PROXY_ARCHIVE_DIR (optional, only if you keep a broader personal collection) ==="
if [ -n "$BLHELI32PROXY_ARCHIVE_DIR" ]; then
    echo "  already set: $BLHELI32PROXY_ARCHIVE_DIR"
else
    read -r -p "  Do you have a separate test-firmware archive folder to use? [y/N] " answer
    if [ "$answer" = "y" ] || [ "$answer" = "Y" ]; then
        read -r -p "  Enter the full path: " archive_dir
        archive_dir="${archive_dir/#\~/$HOME}"
        persist BLHELI32PROXY_ARCHIVE_DIR "$archive_dir"
    else
        echo "  Skipped — this project's own \$BLHELI32PROXY_APP_DIR/BLHeli32_HexFiles/ will be used instead."
    fi
fi

echo
echo "Done. Restart your shell (or 'source $RC_FILE') for other terminals to pick this up."

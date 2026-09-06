#!/bin/bash
# Approval server on port 443 directly. No sudo needed after scripts/setup-cap.sh has run once.
set -e
cd "$(dirname "$0")/.."
.venv/bin/blheli32proxy serve --host 0.0.0.0 --port 443 \
  --cert ~/.blheli32proxy/approval.crt --key ~/.blheli32proxy/approval.key \
  --policy allow-all --verbose

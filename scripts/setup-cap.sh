#!/bin/bash
# One-time: let this venv's python bind port 443 without sudo/iptables.
# Re-run after recreating the venv (setcap is lost on a new binary).
set -e
cd "$(dirname "$0")/.."
sudo setcap 'cap_net_bind_service=+ep' "$(readlink -f .venv/bin/python3)"

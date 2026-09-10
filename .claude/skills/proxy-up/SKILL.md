---
name: proxy-up
kind: skill
category: operations
summary: "Bring up the approval server and the OS-level hostname + port redirect."
description: |
  Start the BLHeli32Proxy approval server and wire the real BLHeliSuite32xl app to it — TLS cert, serve, hostname redirect, port redirect, CA trust. Idempotent: checks each step before repeating it. Run before any flash or activation-capture work.
---

# proxy-up

**Trigger**: "start the proxy", "bring up the server", "set up the redirect", "proxy-up", MENU.md item 3.

Full reference: `docs/USAGE.md` §2-§4. This skill is the ordered checklist.

## Preconditions

- `.venv` exists and `blheli32proxy` runs (`.venv/bin/blheli32proxy --help`). If not: `python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"`.
- Real activation hostname is `blheli.org` (confirmed — `PLAN.md` §4).
- Server and app on the same machine → redirect target `127.0.0.1`. Different machines → the server's LAN IP, edited into the app machine's hosts file.

## Steps — check each before doing it

1. **TLS cert.** Exists at `~/.blheli32proxy/approval.crt` + `approval.key`? If not:
   ```bash
   blheli32proxy gen-cert --out ~/.blheli32proxy --common-name blheli.org
   ```
   Common Name must equal the hostname the app connects to, or TLS clients reject it.

2. **Server running?** Check for a live `blheli32proxy serve` process / port 8443 listener. If not, start it (leave it running):
   ```bash
   blheli32proxy serve --host 0.0.0.0 --port 8443 \
       --cert ~/.blheli32proxy/approval.crt --key ~/.blheli32proxy/approval.key \
       --policy allow-all --verbose
   ```
   `--policy counted --initial-count N --state-file ~/.blheli32proxy/license-state.json` instead, for per-UUID metering.

3. **Hostname redirect present?** `grep blheli.org /etc/hosts`. If absent (Linux/macOS):
   ```bash
   echo "127.0.0.1  blheli.org" | sudo tee -a /etc/hosts
   ```
   Windows: `Add-Content C:\Windows\System32\drivers\etc\hosts "127.0.0.1  blheli.org"` (elevated).
   Flush DNS if it does not take: `sudo resolvectl flush-caches` (Linux), `sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder` (macOS), `ipconfig /flushdns` (Windows).

4. **Port 443 → 8443 redirect present?** REQUIRED — the hosts edit alone silently does nothing. `sudo iptables -t nat -L OUTPUT -n | grep 8443`. If absent (Linux):
   ```bash
   sudo iptables -t nat -A OUTPUT -p tcp -d 127.0.0.1 --dport 443 -j REDIRECT --to-port 8443
   ```
   Undo with `-D` in place of `-A`. Does not persist across reboot by default.

5. **CA trust present?** Only needed for the app to accept the HTTPS connection. Debian/Ubuntu:
   ```bash
   sudo cp ~/.blheli32proxy/approval.crt /usr/local/share/ca-certificates/blheli32proxy.crt
   sudo update-ca-certificates
   ```
   Fedora/RHEL, macOS, Windows: `docs/USAGE.md` §4 "Trusting the certificate".

6. **Verify.** `ping blheli.org` resolves to the redirect target. Trigger a "check for updates" in the app; the server log must show `GET /BLHeli32_2017_1/status.php`. Empty log = port redirect missing (step 4).

## Rules

- Every `sudo` step: tell the user the exact command and get their go-ahead before running it (global safety rule).
- Report what was already done vs. what this run changed.
- Teardown when asked: remove the `/etc/hosts` line, `iptables -D` the rule, stop `serve`. Leave the cert and CA trust unless asked to remove them.

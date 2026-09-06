# BLHeli32Proxy

A local MITM/proxy server that answers BLHeli32's now-dead activation call, so the real,
unmodified `BLHeliSuite32xl` app keeps working for flashing/configuring owned BLHeli_32 ESCs. This
tool never flashes ESCs itself — you keep using the official app for everything ESC-facing. See
[PLAN.md §4](PLAN.md#4-architecture-decision) for the architecture rationale.

**Status**: implementation in progress, real hardware confirmed working across 4 different ESC
families and 4 different BLHeli_32 firmware revisions. This project's approval server is confirmed
working end-to-end against the real app — the one remaining step is capturing the actual
ESC-activation network call, which needs a real flash attempt (see `MENU.md` item 6). Not yet
public — see [Publishing](#publishing) below.

New here? Start with `MENU.md` for a guided list of things you can do, or jump straight to
[Quickstart](#quickstart) below.

## What it does

- **Proxy/licensing intercept** (primary goal) — runs a local HTTP(S) server standing in for
  BLHeli's dead activation server. Real hostname and the version-check endpoint are confirmed and
  implemented; the actual ESC-activation endpoint still needs to be captured from a real flash
  attempt.
- **Backups** — reads an ESC's Setup/config block over serial, decrypts it, and decodes confirmed
  named fields (13 of ~39, cross-checked against a real `.ixi` backup).
- **Diagnostics** — read-only flash-address probing and dumping, direct or through a flight
  controller's 4-way-if passthrough.

Firmware dumps (the ESC's executable code) and bootloader unlocking are both closed as goals —
confirmed blocked by real hardware protections (STM32 Read-Out Protection). See
[Goals & Status](docs/knowledge/goals-status.md) for the full breakdown.

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
blheli32proxy gen-cert --out ~/.blheli32proxy --common-name blheli.org
blheli32proxy serve --cert ~/.blheli32proxy/approval.crt --key ~/.blheli32proxy/approval.key
```

You'll also need your own copy of test-firmware `.Hex` files — this project never bundles BLHeli's
copyrighted vendor binaries. See [testcode/README.md](testcode/README.md) for how to fetch them
from BLHeli's official GitHub history.

Full walkthrough, including the OS-level hostname (and port) redirect that points
`BLHeliSuite32xl` at this server: [docs/USAGE.md](docs/USAGE.md). Or use [MENU.md](MENU.md) for a
guided, step-by-step task list instead of reading the full docs first.

## Documentation

| Doc | Purpose |
|---|---|
| [MENU.md](MENU.md) | Guided task list — start here if you're not sure what to do first |
| [PLAN.md](PLAN.md) | Goals, architecture decisions, status, open questions |
| [docs/USAGE.md](docs/USAGE.md) | CLI reference, install, OS-level redirect setup |
| [testcode/README.md](testcode/README.md) | How to populate test-firmware `.Hex` files yourself |
| [docs/knowledge/INDEX.md](docs/knowledge/INDEX.md) | Confirmed protocol/hardware/licensing reference |
| [IMPLEMENTATION.md](IMPLEMENTATION.md) | Module-by-module build status |
| [research/README.en.md](research/README.en.md) | Original translated research notes |
| [AGENTS.md](AGENTS.md) | Working conventions for AI-assisted sessions on this repo |

## Requirements

Python 3.9+. Cross-platform (Linux, macOS, Windows) — only the optional hardware-facing serial
transport touches OS-specific APIs, and it isn't needed to run the approval server itself.

## Publishing

This repo may be private or public depending on where you got it from — check your own remote
before assuming either way. It builds on dead-vendor BLHeli32 material — see [AGENTS.md](AGENTS.md)'s
Publishing Gate for the rule covering copyrighted vendor binaries specifically, and
[PLAN.md §8](PLAN.md#8-publishing) for the full context.

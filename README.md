# BLHeli32Proxy

A diagnostic and backup toolkit for BLHeli_32 ESCs, plus an in-progress local MITM/proxy server
aimed at BLHeli32's now-dead activation call. **The proxy does not currently enable firmware
flashing through the vendor app — see Status below.** This tool never flashes ESCs itself; all
ESC-facing work still goes through the official, unmodified `BLHeliSuite32xl` app. See
[PLAN.md §4](PLAN.md#4-architecture-decision) for the architecture rationale.

**Status**: implementation in progress, real hardware confirmed working across 4 different ESC
families and 4 different BLHeli_32 firmware revisions for backups/diagnostics. **The proxy/licensing
goal has not succeeded yet**: this project's server correctly answers the app's harmless
version-check call, but a real "Flash Selected ESC" attempt through the vendor app never sent any
ESC-activation network traffic at all — zero protocol surfaced beyond that one ping — and the app
silently declined to write firmware regardless. The actual block looks to be inside the app's own
internal state logic, not licensing at all. See [Goals & Status](docs/knowledge/goals-status.md#4-proxy--licensing-intercept--the-original-project-goal-least-advanced)
for the full finding. Public — see [Publishing](#publishing) below.

New here? Start with `MENU.md` for a guided list of things you can do, or jump straight to
[Quickstart](#quickstart) below.

## What it does

- **Proxy/licensing intercept** (original goal, not working yet) — runs a local HTTP(S) server
  standing in for BLHeli's dead activation server. The hostname redirect and version-check endpoint
  work; a real flash attempt through the vendor app never triggered any ESC-activation network call
  at all, and the app declined to write firmware regardless — see
  [Goals & Status](docs/knowledge/goals-status.md) for the full finding.
- **Backups** — reads an ESC's Setup/config block over serial, decrypts it, and decodes the named
  fields (every one except `Eep_ESC_Mode`), cross-checked against real `.ixi` backups across 3
  different MCU vendors. See [Setup Block Fields](docs/knowledge/setup-block-fields.md).
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
copyrighted vendor binaries. See [docs/USAGE.md](docs/USAGE.md) §1a/§1b for how to point this tool
at your files and fetch them from BLHeli's official GitHub history.

Full walkthrough, including the OS-level hostname (and port) redirect that points
`BLHeliSuite32xl` at this server: [docs/USAGE.md](docs/USAGE.md). Or use [MENU.md](MENU.md) for a
guided, step-by-step task list instead of reading the full docs first.

## Documentation

| Doc | Purpose |
|---|---|
| [MENU.md](MENU.md) | Guided task list — start here if you're not sure what to do first |
| [PLAN.md](PLAN.md) | Goals, architecture decisions, status, open questions |
| [docs/USAGE.md](docs/USAGE.md) | CLI reference, install, OS-level redirect setup, populating test-firmware `.Hex` files (§1a/§1b) |
| [docs/knowledge/INDEX.md](docs/knowledge/INDEX.md) | Confirmed protocol/hardware/licensing reference |
| [IMPLEMENTATION.md](IMPLEMENTATION.md) | Module-by-module build status |
| [research/README.en.md](research/README.en.md) | Original translated research notes |
| [AGENTS.md](AGENTS.md) | Working conventions for AI-assisted sessions on this repo |

## Requirements

Python 3.9+. Cross-platform (Linux, macOS, Windows) — only the optional hardware-facing serial
transport touches OS-specific APIs, and it isn't needed to run the approval server itself.

## Publishing

This repo is public on GitHub. It builds on dead-vendor BLHeli32 material — see
[AGENTS.md](AGENTS.md)'s Publishing Gate for the rule covering copyrighted vendor binaries
specifically (never committed here), and [PLAN.md §8](PLAN.md#8-publishing) for the full context.

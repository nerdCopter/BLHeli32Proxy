# Knowledge Base Index

Technical reference material for BLHeli32Proxy, split out of `PLAN.md` (2026-09-04) so the plan
stays a plan — goals, status, decisions — rather than a growing log of everything ever confirmed.
`PLAN.md` links into these files where relevant; these files are the durable reference.

- [Goals & Status](goals-status.md) — the 4 project goals, current state, a status diagram
- [Protocol Reference](protocol-reference.md) — confirmed wire protocol: single-wire UART frames,
  the framed 4-way-if bootloader protocol, XTEA cipher, command bytes
- [Activation & Licensing](activation-licensing.md) — the real `blheli.org` findings, confirmed
  endpoint, the activation-subsystem shape, TLS trust open question
- [Setup Block Fields](setup-block-fields.md) — named-field decode of the 256-byte config block,
  what's confirmed vs. unknown
- [Hardware Findings](hardware-findings.md) — real-hardware test log: RDP protection, the
  verify-oracle exploration, wiring/power lessons, per-ESC-channel quirks

## Diagram conventions

Diagrams use [Mermaid](https://mermaid.js.org/), which GitHub renders natively in Markdown — no
extra tooling needed to view them once this project is a public repo.

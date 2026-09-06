"""Data model for an activation/approval exchange.

This model is deliberately schema-agnostic: it's what the policy engine (policy.py)
reasons about, independent of the actual wire format a client sends. The wire
format itself is not yet known (see PLAN.md §4) — see codec.py for the
(currently placeholder) translation between real bytes and this model.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ActivationRequest:
    esc_type: str | None
    uuid: str | None
    firmware_name: str | None = None
    raw_body: bytes = b""
    raw_headers: dict[str, str] = field(default_factory=dict)
    raw_path: str = ""


@dataclass
class ActivationResponse:
    approved: bool
    remaining: int | None = None
    message: str = ""

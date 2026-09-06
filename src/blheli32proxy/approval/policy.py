"""Authorization policies: given an ActivationRequest, decide whether to approve it.

This is "our own licensing rule" (PLAN.md §5 phase 3) — independent of BLHeli's
original (dead) server logic, though CountedLicensePolicy's shape mirrors what
research/notes/BLHeli-END.en.md documented from the real BLHeliSuite32Activator
tool: a per-UUID activation that decrements a remaining-count, with a local
ledger of already-activated UUIDs so re-activating the same unit doesn't double-
count. There is no requirement to replicate that exactly — AllowAllPolicy is the
simpler default for personal use on owned hardware.
"""

from __future__ import annotations

import json
import threading
from abc import ABC, abstractmethod
from pathlib import Path

from .models import ActivationRequest, ActivationResponse


class ApprovalPolicy(ABC):
    @abstractmethod
    def evaluate(self, request: ActivationRequest) -> ActivationResponse: ...


class AllowAllPolicy(ApprovalPolicy):
    """Approves every request unconditionally. Default policy — appropriate when
    the only goal is to keep the user's own already-owned hardware/firmware
    working, with no metering."""

    def evaluate(self, request: ActivationRequest) -> ActivationResponse:
        return ActivationResponse(approved=True, remaining=None, message="allowed (AllowAllPolicy)")


class CountedLicensePolicy(ApprovalPolicy):
    """Approves up to `initial_count` distinct UUIDs, then refuses. Re-requests
    for an already-approved UUID are always re-approved without consuming
    another count (idempotent), mirroring the real tool's local CSV ledger.

    State is a small JSON file: {"remaining": int, "activated_uuids": [str, ...]}.
    Thread-safe for use from a threaded HTTP server.
    """

    def __init__(self, state_path: Path, initial_count: int = 1000):
        self._state_path = state_path
        self._lock = threading.Lock()
        if not state_path.exists():
            self._write_state({"remaining": initial_count, "activated_uuids": []})

    def _read_state(self) -> dict:
        with self._state_path.open() as f:
            return json.load(f)

    def _write_state(self, state: dict) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        with self._state_path.open("w") as f:
            json.dump(state, f, indent=2)

    def evaluate(self, request: ActivationRequest) -> ActivationResponse:
        if not request.uuid:
            return ActivationResponse(approved=False, remaining=None, message="missing UUID")
        with self._lock:
            state = self._read_state()
            if request.uuid in state["activated_uuids"]:
                return ActivationResponse(
                    approved=True,
                    remaining=state["remaining"],
                    message="already activated",
                )
            if state["remaining"] <= 0:
                return ActivationResponse(approved=False, remaining=0, message="no remaining activations")
            state["remaining"] -= 1
            state["activated_uuids"].append(request.uuid)
            self._write_state(state)
            return ActivationResponse(
                approved=True,
                remaining=state["remaining"],
                message="activated",
            )
